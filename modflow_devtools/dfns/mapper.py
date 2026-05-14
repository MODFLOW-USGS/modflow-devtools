"""
v2 schema mapping for MODFLOW 6 DFNs.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import asdict
from typing import Any, Literal, cast

from boltons.dictutils import OMD
from packaging.version import Version

from modflow_devtools.dfn.parse import (
    try_parse_bool,
)
from modflow_devtools.dfn.v1_1 import SCALAR_TYPES as V1_SCALAR_TYPES
from modflow_devtools.dfn.v1_1 import Dfn, FieldV1
from modflow_devtools.dfns.schema.v2 import (
    Array,
    Double,
    FieldBase,
    Integer,
    Keyword,
    List,
    Record,
    String,
    Union,
)
from modflow_devtools.misc import try_literal_eval

_IDENT_RE = re.compile(r"^[A-Za-z_]\w*$")


# =============================================================================
# Mapper
# =============================================================================


class MapV1To2:
    """Map a v1 Dfn (FieldV1 blocks) to a v2 Component."""

    @staticmethod
    def map_period_block(dfn: Dfn, block: dict) -> dict:
        """Convert a period block recarray to individual arrays, one per column."""
        block = dict(block)
        fields_list = list(block.values())

        if fields_list and isinstance(fields_list[0], List):
            assert len(fields_list) == 1
            list_field: List = fields_list[0]
            block.pop(list_field.name)
            item = list_field.item
            columns: dict = dict(item.fields if isinstance(item, Record) else item.arms)
        else:
            columns = dict(block)

        cellid = columns.pop("cellid", None)

        _SCALAR_DTYPES = {"keyword", "integer", "double", "double precision", "string"}

        for col_name, column in columns.items():
            if isinstance(column, Array):
                dtype = column.dtype
            elif getattr(column, "type", None) in _SCALAR_DTYPES:
                dtype = column.type
                if dtype == "double precision":
                    dtype = "double"
            else:
                block[col_name] = column
                continue

            from modflow_devtools.dfns.schema.v2 import GRID_DIM_NAMESPACE

            old_dims = list(column.shape) if isinstance(column, Array) else []
            new_dims = ["nper"]
            if cellid:
                new_dims.append("nodes")
            new_dims.extend(d for d in old_dims if d in GRID_DIM_NAMESPACE)

            block[col_name] = Array(
                name=column.name,
                longname=getattr(column, "longname", None),
                description=getattr(column, "description", None),
                optional=column.optional,
                default=getattr(column, "default", None),
                developmode=column.developmode,
                netcdf=getattr(column, "netcdf", False),
                dtype=dtype,
                shape=new_dims,
            )

        return block

    @staticmethod
    def map_field(dfn: Dfn, v1_field: FieldV1) -> FieldBase:
        """Convert a v1 field to the appropriate v2 concrete type."""
        fields = cast(OMD, dfn.fields)

        def _to_bool(v: Any, default: bool = False) -> bool:
            if isinstance(v, bool):
                return v
            if isinstance(v, str):
                s = v.strip().lower()
                if s == "true":
                    return True
                if s in ("false", ""):
                    return False
            return default

        def _map_field(f: FieldV1) -> FieldBase:
            fd = asdict(f)
            fd = {k: try_parse_bool(v) for k, v in fd.items()}

            _name: str = fd["name"]
            _type: str | None = fd.get("type")
            shape_str: str | None = fd.get("shape") or None
            description: str | None = fd.get("description") or None
            longname: str | None = fd.get("longname") or None
            optional: bool = _to_bool(fd.get("optional"), False)
            developmode: bool = _to_bool(fd.get("developmode"), False)
            netcdf: bool = _to_bool(fd.get("netcdf"), False)
            tagged: bool = _to_bool(fd.get("tagged"), False)
            preserve_case: bool = _to_bool(fd.get("preserve_case"), False)
            time_series: bool = _to_bool(fd.get("time_series"), False)
            valid = fd.get("valid")
            _default_raw = fd.get("default")
            default = (
                try_literal_eval(_default_raw)
                if _type != "string" and isinstance(_default_raw, str)
                else _default_raw
            )

            _COL_FK_RE = re.compile(r"^([A-Za-z_]\w*)\(([A-Za-z_]\w*)\)$")

            def _parse_shape(s: str) -> list[str]:
                result = []
                s_clean = s.strip()
                if s_clean.startswith("(") and s_clean.endswith(")"):
                    s_clean = s_clean[1:-1]
                for elem in (x.strip() for x in s_clean.split(",") if x.strip()):
                    if ";" in elem:
                        result.append("ncpl")
                    elif (
                        elem in ("any1d", "unknown") or elem.startswith("<") or elem.startswith(">")
                    ):
                        pass
                    elif m := _COL_FK_RE.fullmatch(elem):
                        col_name = m.group(1)
                        block_name = next(
                            (
                                fi.block
                                for fi in fields.values(multi=True)
                                if fi.name == col_name and fi.type == "integer" and fi.in_record
                            ),
                            None,
                        )
                        if block_name:
                            result.append(f"{block_name}.{elem}")
                    else:
                        provider = next(
                            (
                                fi.name
                                for fi in fields.values(multi=True)
                                if fi.type == "string"
                                and (fi.shape or "").strip() in (f"({elem})", elem)
                            ),
                            None,
                        )
                        result.append(provider if provider else elem)
                return result

            def _to_scalar() -> FieldBase:
                assert _type is not None
                if _type == "keyword":
                    return Keyword(
                        name=_name,
                        longname=longname,
                        description=description,
                        optional=optional,
                        default=default,
                        developmode=developmode,
                        netcdf=netcdf,
                    )
                if _type == "string":
                    return String(
                        name=_name,
                        longname=longname,
                        description=description,
                        optional=optional,
                        default=default,
                        developmode=developmode,
                        netcdf=netcdf,
                        tagged=tagged,
                        valid=list(valid) if valid else None,
                        case_sensitive=preserve_case,
                        time_series=time_series,
                    )
                if _type == "integer":
                    from modflow_devtools.dfns.schema.v2 import GRID_DIM_NAMESPACE

                    v = [int(x) for x in valid] if valid else None
                    if fd.get("block") == "dimensions":
                        if _name in GRID_DIM_NAMESPACE:
                            _dim_scope: (
                                Literal["record", "component", "model", "simulation"] | None
                            ) = "model"
                        elif dfn.name == "sim-tdis" and _name == "nper":
                            _dim_scope = "simulation"
                        else:
                            _dim_scope = "component"
                    else:
                        _dim_scope = None
                    return Integer(
                        name=_name,
                        longname=longname,
                        description=description,
                        optional=optional,
                        default=default,
                        developmode=developmode,
                        netcdf=netcdf,
                        tagged=tagged,
                        valid=v,
                        time_series=time_series,
                        dimension=_dim_scope,
                    )
                if _type in ("double", "double precision"):
                    return Double(
                        name=_name,
                        longname=longname,
                        description=description,
                        optional=optional,
                        default=default,
                        developmode=developmode,
                        netcdf=netcdf,
                        tagged=tagged,
                        time_series=time_series,
                    )
                raise TypeError(f"Unsupported scalar type: {_type!r}")

            def _row_field() -> Record | Union:
                item_names = (_type or "").split()[1:]
                if not item_names:
                    raise ValueError(f"Missing list item definition: {_type!r}")

                item_types = [
                    fi.type
                    for fi in fields.values(multi=True)
                    if fi.name in item_names and fi.in_record
                ]

                if (
                    len(item_names) == 1
                    and item_types
                    and (
                        (item_types[0] or "").startswith("record")
                        or (item_types[0] or "").startswith("keystring")
                    )
                ):
                    mapped = MapV1To2.map_field(dfn, next(iter(fields.getlist(item_names[0]))))
                    if isinstance(mapped, (Record, Union)):
                        return mapped
                    raise TypeError(
                        f"Expected Record or Union for list item, got {type(mapped).__name__}"
                    )

                if all(t in V1_SCALAR_TYPES for t in item_types):
                    rec_fields = _record_fields()
                    return Record(
                        name=_name,
                        description=(
                            (description or "").replace("is the list of", "is the record of")
                            or None
                        ),
                        fields=rec_fields,
                    )

                children = {
                    fi.name: MapV1To2.map_field(dfn, fi)
                    for fi in fields.values(multi=True)
                    if fi.name in item_names and fi.in_record
                }
                first = next(iter(children.values()))
                if len(children) == 1 and isinstance(first, Union):
                    return first
                return Record(
                    name=_name,
                    description=(
                        (description or "").replace("is the list of", "is the record of") or None
                    ),
                    fields=children,  # type: ignore[arg-type]
                )

            def _union_fields() -> dict:
                names = (_type or "").split()[1:]
                return {
                    fi.name: MapV1To2.map_field(dfn, fi)
                    for fi in fields.values(multi=True)
                    if fi.name in names and fi.in_record
                }

            def _record_fields() -> dict:
                names = (_type or "").split()[1:]
                result = {}
                for rname in names:
                    matches = [
                        fi
                        for fi in fields.values(multi=True)
                        if fi.name == rname
                        and fi.in_record
                        and not (fi.type or "").startswith("record")
                    ]
                    if matches:
                        result[rname] = _map_field(matches[0])
                return result

            if _type is None:
                raise ValueError(f"Missing type for v1 field: {_name!r}")

            if _type.startswith("recarray"):
                item = _row_field()
                return List(
                    name=_name,
                    longname=longname,
                    description=description,
                    optional=optional,
                    default=default,
                    developmode=developmode,
                    netcdf=netcdf,
                    item=item,
                )

            if _type.startswith("keystring"):
                arms = _union_fields()
                return Union(
                    name=_name,
                    longname=longname,
                    description=description,
                    optional=optional,
                    default=default,
                    developmode=developmode,
                    arms=arms,  # type: ignore[arg-type]
                )

            if _type.startswith("record"):
                rec_fields = _record_fields()
                return Record(
                    name=_name,
                    longname=longname,
                    description=description,
                    optional=optional,
                    default=default,
                    developmode=developmode,
                    fields=rec_fields,  # type: ignore[arg-type]
                )

            if shape_str is not None:
                dtype_map: dict[str, Literal["keyword", "integer", "double", "string"]] = {
                    "double precision": "double",
                    "double": "double",
                    "integer": "integer",
                    "string": "string",
                    "keyword": "keyword",
                }
                dtype = dtype_map.get(_type)
                if dtype is not None:
                    if dtype == "string":
                        return Array(
                            name=_name,
                            longname=longname,
                            description=description,
                            optional=optional,
                            default=default,
                            developmode=developmode,
                            netcdf=netcdf,
                            time_series=time_series,
                            dtype="string",
                            shape=[],
                        )
                    parsed_shape = _parse_shape(shape_str)
                    return Array(
                        name=_name,
                        longname=longname,
                        description=description,
                        optional=optional,
                        default=default,
                        developmode=developmode,
                        netcdf=netcdf,
                        time_series=time_series,
                        dtype=dtype,
                        shape=parsed_shape,
                    )

            return _to_scalar()

        return _map_field(v1_field)

    @staticmethod
    def _mark_dimension_fields(blocks: dict[str, dict]) -> dict[str, dict]:
        """
        Post-pass: annotate every field that provides a dimension count.

        String-array dim providers (e.g. ``auxiliary``): marked
        ``dimension="component"``.  Record-local dim integers: marked
        ``dimension="record"``.
        """
        from modflow_devtools.dfns.schema.v2 import GRID_DIM_NAMESPACE

        shape_refs: set[str] = set()
        string_array_names: set[str] = set()
        explicit_globals: set[str] = set(GRID_DIM_NAMESPACE)

        def _scan(fields: dict) -> None:
            for f in fields.values():
                if isinstance(f, Array):
                    if f.dtype != "string":
                        for elem in f.shape:
                            if _IDENT_RE.fullmatch(elem):
                                shape_refs.add(elem)
                    else:
                        string_array_names.add(f.name)
                scope = getattr(f, "dimension", None)
                if scope in ("component", "model", "simulation"):
                    explicit_globals.add(f.name)
                if isinstance(f, Record):
                    _scan(f.fields)
                elif isinstance(f, Union):
                    _scan(f.arms)
                elif isinstance(f, List):
                    item = f.item
                    _scan(item.fields if isinstance(item, Record) else item.arms)

        for block_fields in blocks.values():
            _scan(block_fields)

        if not shape_refs:
            return blocks

        string_provider_names: set[str] = string_array_names & shape_refs
        global_dims: set[str] = explicit_globals | string_provider_names

        def _record_local_dims(rec: Record) -> set[str]:
            to_mark: set[str] = set()
            for sf in rec.fields.values():
                if isinstance(sf, Array) and sf.dtype != "string":
                    for elem in sf.shape:
                        if _IDENT_RE.fullmatch(elem) and elem not in global_dims:
                            sibling = rec.fields.get(elem)
                            if isinstance(sibling, Integer) and sibling.dimension is None:
                                to_mark.add(elem)
            return to_mark

        def _mark(fields: dict) -> dict:
            result = {}
            for name, f in fields.items():
                if isinstance(f, Array) and f.dtype == "string" and name in string_provider_names:
                    f = f.model_copy(update={"dimension": "component"})
                elif isinstance(f, Record):
                    local_dims = _record_local_dims(f)
                    new_fields = _mark(f.fields)
                    if local_dims:
                        new_fields = {
                            fn: (
                                sf.model_copy(update={"dimension": "record"})
                                if fn in local_dims and isinstance(sf, Integer)
                                else sf
                            )
                            for fn, sf in new_fields.items()
                        }
                    f = f.model_copy(update={"fields": new_fields})
                elif isinstance(f, Union):
                    f = f.model_copy(update={"arms": _mark(f.arms)})
                elif isinstance(f, List):
                    item = f.item
                    new_item: Record | Union
                    if isinstance(item, Record):
                        local_dims = _record_local_dims(item)
                        new_item_fields = _mark(item.fields)
                        if local_dims:
                            new_item_fields = {
                                fn: (
                                    sf.model_copy(update={"dimension": "record"})
                                    if fn in local_dims and isinstance(sf, Integer)
                                    else sf
                                )
                                for fn, sf in new_item_fields.items()
                            }
                        new_item = item.model_copy(update={"fields": new_item_fields})
                    else:
                        new_item = item.model_copy(update={"arms": _mark(item.arms)})
                    f = f.model_copy(update={"item": new_item})
                result[name] = f
            return result

        return {bn: _mark(bf) for bn, bf in blocks.items()}

    @staticmethod
    def _infer_fk_from_shapes(blocks: dict[str, dict]) -> dict[str, dict]:
        """Post-pass: infer fk= and pk= from resolved lookup shape elements."""
        _lookup_re = re.compile(r"^(\w+)\.(\w+)\((\w+)\)$")

        fk_map: dict[tuple[str, str], str] = {}
        pk_set: set[tuple[str, str]] = set()

        def _scan_record(rec: Record, block_name: str) -> None:
            for sf in rec.fields.values():
                if isinstance(sf, Array):
                    for elem in sf.shape:
                        m = _lookup_re.fullmatch(elem)
                        if m:
                            pk_block, _col, fk_fname = m.groups()
                            sibling = rec.fields.get(fk_fname)
                            if sibling is not None and getattr(sibling, "fk", None) is None:
                                fk_map[(block_name, fk_fname)] = f"{pk_block}.{fk_fname}"
                                pk_set.add((pk_block, fk_fname))

        def _scan(fields: dict, block_name: str) -> None:
            for f in fields.values():
                if isinstance(f, Record):
                    _scan_record(f, block_name)
                elif isinstance(f, Union):
                    _scan(f.arms, block_name)
                elif isinstance(f, List):
                    item = f.item
                    if isinstance(item, Record):
                        _scan_record(item, block_name)
                    elif isinstance(item, Union):
                        _scan(item.arms, block_name)

        for block_name, block_fields in blocks.items():
            _scan(block_fields, block_name)

        if not fk_map and not pk_set:
            return blocks

        def _apply_record(rec: Record, block_name: str) -> Record:
            updates: dict = {}
            for fname, sf in rec.fields.items():
                updated = sf
                if (block_name, fname) in fk_map and getattr(sf, "fk", None) is None:
                    updated = updated.model_copy(update={"fk": fk_map[(block_name, fname)]})
                if (block_name, fname) in pk_set and not getattr(sf, "pk", False):
                    updated = updated.model_copy(update={"pk": True})
                if updated is not sf:
                    updates[fname] = updated
            if not updates:
                return rec
            return rec.model_copy(
                update={"fields": {fn: updates.get(fn, sf) for fn, sf in rec.fields.items()}}
            )

        def _apply(fields: dict, block_name: str) -> dict:
            result = {}
            for name, f in fields.items():
                if isinstance(f, Record):
                    f = _apply_record(f, block_name)
                elif isinstance(f, Union):
                    f = f.model_copy(update={"arms": _apply(f.arms, block_name)})
                elif isinstance(f, List):
                    item = f.item
                    new_item: Record | Union
                    if isinstance(item, Record):
                        new_item = _apply_record(item, block_name)
                    else:
                        new_item = item.model_copy(update={"arms": _apply(item.arms, block_name)})
                    f = f.model_copy(update={"item": new_item})
                result[name] = f
            return result

        return {bn: _apply(bf, bn) for bn, bf in blocks.items()}

    @staticmethod
    def map_blocks(dfn: Dfn) -> dict[str, dict]:
        """
        Convert all v1 fields in a Dfn to v2 types and return a block dict.

        Three phases:
        1. Field conversion (map_field per top-level field).
        2. Dimension annotation (_mark_dimension_fields).
        3. FK/PK inference (_infer_fk_from_shapes).
        """
        all_v1 = cast(OMD, dfn.fields)
        grouped: dict[str, dict] = {}
        for v1_field in all_v1.values(multi=True):
            if v1_field.in_record:  # type: ignore[attr-defined]
                continue
            block_name = v1_field.block
            mapped = MapV1To2.map_field(dfn, v1_field)
            grouped.setdefault(block_name, {})[v1_field.name] = mapped

        blocks: dict[str, dict] = {}
        if period := grouped.pop("period", None):
            blocks["period"] = MapV1To2.map_period_block(dfn, period)
        for block_name, block_data in grouped.items():
            blocks[block_name] = block_data

        blocks = MapV1To2._mark_dimension_fields(blocks)
        return MapV1To2._infer_fk_from_shapes(blocks)

    @staticmethod
    def to_component(dfn: Dfn) -> Any:
        """
        Convert a Dfn to the appropriate Component (Simulation, Model, or Package).

        For v1-mapped Dfns, variant_of is inferred from the component name: names
        ending in "g" (grid variant) or "a" (array variant) are treated as variants
        of the same name without the suffix (e.g. "gwf-welg" → "gwf-wel").
        """
        from modflow_devtools.dfns.schema.v2 import (
            Block,
            Model,
            Package,
            Simulation,
        )

        name = dfn.name
        blocks: dict[str, Block] | None = None
        if dfn.blocks:
            blocks = {
                block_name: Block(
                    name=block_name,
                    fields={k: v for k, v in block_fields.items() if isinstance(v, FieldBase)},  # type: ignore[misc]
                )
                for block_name, block_fields in dfn.blocks.items()
                if isinstance(block_fields, dict)
            }

        def _infer_variant_of(n: str) -> str | None:
            if n.endswith(("g", "a")):
                return n[:-1]
            return None

        common: dict[str, Any] = {
            "name": name,
            "blocks": blocks,
            "parent": dfn.parent,
            "schema_version": dfn.schema_version,
        }
        if name == "sim-nam":
            return Simulation(**common)
        if name.endswith("-nam"):
            return Model(**common)
        if name.startswith("sln-"):
            return Package(**common, subtype="solution", multi=dfn.multi)
        if name.startswith("exg-"):
            return Package(**common, subtype="exchange", multi=dfn.multi)
        if name.startswith("utl-"):
            return Package(
                **common,
                subtype="utility",
                multi=dfn.multi,
                variant_of=_infer_variant_of(name),
            )
        has_period = bool(blocks and any("period" in k for k in blocks))
        subtype: Literal["solution", "exchange", "stress", "advanced", "utility"] | None = (
            "advanced" if dfn.advanced else "stress" if has_period else None
        )
        return Package(
            **common,
            subtype=subtype,
            multi=dfn.multi,
            variant_of=_infer_variant_of(name),
        )

    def map(self, dfn: Dfn) -> Any:
        """Map a v1 (or v2) Dfn to a v2 Component."""
        if dfn.schema_version == Version("2"):
            return MapV1To2.to_component(dfn)
        mapped_blocks = MapV1To2.map_blocks(dfn)
        temp = dataclasses.replace(dfn, schema_version=Version("2"), blocks=mapped_blocks)
        return MapV1To2.to_component(temp)


def map(
    dfn: Dfn,
    schema_version: str | Version = "2",
) -> Any:
    """Map a MODFLOW 6 definition to v2 schema."""
    version = Version(str(schema_version))
    if version == Version("2"):
        return MapV1To2().map(dfn)
    raise ValueError(f"Unsupported schema version: {schema_version!r}. Expected '2'.")
