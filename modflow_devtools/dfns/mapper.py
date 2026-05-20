from __future__ import annotations

import re
from typing import Any, Literal

from modflow_devtools.dfn import schema as v1
from modflow_devtools.dfn.parser import try_parse_bool
from modflow_devtools.dfns import schema as v2
from modflow_devtools.misc import try_literal_eval

_IDENT_RE = re.compile(r"^[A-Za-z_]\w*$")
_LOOKUP_RE = re.compile(r"^(\w+)\.(\w+)\((\w+)\)$")
_DIMS: frozenset[str] = frozenset(
    {"nodes", "nlay", "nrow", "ncol", "ncpl", "nja", "ncelldim", "nvert"}
)


def _resolve_dimensions(blocks: dict[str, v2.Block]) -> dict[str, v2.Block]:
    dims_referenced: set[str] = set()  # dims used in shape expressions
    dims_from_array: set[str] = set()  # self-sizing array dimensions
    dims_explicit: set[str] = set(_DIMS)  # integer dimension fields

    # shape expressions may reference dimensions from several providers:
    # - explicitly defined integer dimension fields
    # - dynamic dimensions: size of 1D arrays

    def _scan_fields(fields: dict[str, v2.Field]) -> None:
        for field in fields.values():
            if isinstance(field, v2.Array):
                for dim in field.shape:
                    if _IDENT_RE.fullmatch(dim):
                        dims_referenced.add(dim)
                else:
                    # no shape expr, self-sizing
                    dims_from_array.add(field.name)
            scope = getattr(field, "dimension", None)
            if scope in ("component", "model", "simulation"):
                dims_explicit.add(field.name)
            if isinstance(field, v2.Record):
                _scan_fields(field.fields)
            elif isinstance(field, v2.Union):
                _scan_fields(field.arms)
            elif isinstance(field, v2.List):
                item = field.item
                _scan_fields(item.fields if isinstance(item, v2.Record) else item.arms)

    for block in blocks.values():
        _scan_fields(block.fields)

    if not dims_referenced:
        return blocks

    dims_provided: set[str] = dims_from_array & dims_explicit

    def _get_dims(record: v2.Record) -> set[str]:
        found: set[str] = set()
        for field in record.fields.values():
            if isinstance(field, v2.Array):
                for dim in field.shape:
                    if _IDENT_RE.fullmatch(dim) and dim not in dims_provided:
                        # the shape expression of an array inside a record
                        # may reference a sibling integer subfield even if
                        # the integer is not marked as a dimension.
                        if (sibling := record.fields.get(dim, None)) is not None and isinstance(
                            sibling, v2.Integer
                        ):
                            found.add(dim)
        return found

    def _resolve_fields(fields: dict[str, v2.Field]) -> dict[str, v2.Field]:
        result = {}
        for name, field in fields.items():
            if isinstance(field, v2.Array) and name in dims_provided:
                field.dimension = "component"
            elif isinstance(field, v2.Record):
                local_dims = _get_dims(field)
                subfields = _resolve_fields(field.fields)
                if local_dims:
                    for subfield_name, subfield in subfields.items():
                        if subfield_name in local_dims and isinstance(subfield, v2.Integer):
                            subfield.dimension = "record"
                field.fields = subfields
            elif isinstance(field, v2.Union):
                field.arms = _resolve_fields(field.arms)
            elif isinstance(field, v2.List):
                if isinstance(field.item, v2.Record):
                    local_dims = _get_dims(field.item)
                    subfields = _resolve_fields(field.item.fields)
                    if local_dims:
                        for subfield_name, subfield in subfields.items():
                            if subfield_name in local_dims and isinstance(subfield, v2.Integer):
                                subfield.dimension = "record"
                    field.item.fields = subfields
                else:
                    field.item.arms = _resolve_fields(field.item.arms)
            result[name] = field
        return result

    def _resolve_block(block: v2.Block) -> v2.Block:
        block.fields = _resolve_fields(block.fields)
        return block

    return {block_name: _resolve_block(block) for block_name, block in blocks.items()}


def _resolve_relations(blocks: dict[str, v2.Block]) -> dict[str, v2.Block]:
    pk_set: set[tuple[str, str]] = set()
    fk_map: dict[tuple[str, str], str] = {}

    def _scan_fields(block_name: str, fields: dict[str, v2.Field]) -> None:

        def _scan_record(record: v2.Record) -> None:
            for field in record.fields.values():
                if isinstance(field, v2.Array):
                    for dim in field.shape:
                        if m := _LOOKUP_RE.fullmatch(dim):
                            pk_block, _, fk_fname = m.groups()
                            sibling = record.fields.get(fk_fname)
                            if sibling is not None and getattr(sibling, "fk", None) is None:
                                fk_map[(block_name, fk_fname)] = f"{pk_block}.{fk_fname}"
                                pk_set.add((pk_block, fk_fname))

        for field in fields.values():
            if isinstance(field, v2.Record):
                _scan_record(field)
            elif isinstance(field, v2.Union):
                _scan_fields(block_name, field.arms)
            elif isinstance(field, v2.List):
                item = field.item
                if isinstance(item, v2.Record):
                    _scan_record(item)
                elif isinstance(item, v2.Union):
                    _scan_fields(block_name, item.arms)

    for block_name, block in blocks.items():
        _scan_fields(block_name, block.fields)

    if not fk_map and not pk_set:
        return blocks

    def _resolve_fields(block_name: str, fields: dict[str, v2.Field]) -> dict[str, v2.Field]:

        def _resolve_record(record: v2.Record) -> v2.Record:
            updates: dict = {}
            for fname, sf in record.fields.items():
                updated = sf
                if (block_name, fname) in fk_map and getattr(sf, "fk", None) is None:
                    updated = updated.model_copy(update={"fk": fk_map[(block_name, fname)]})
                if (block_name, fname) in pk_set and not getattr(sf, "pk", False):
                    updated = updated.model_copy(update={"pk": True})
                if updated is not sf:
                    updates[fname] = updated
            if not updates:
                return record
            return record.model_copy(
                update={"fields": {fn: updates.get(fn, sf) for fn, sf in record.fields.items()}}
            )

        result = {}
        for name, f in fields.items():
            if isinstance(f, v2.Record):
                f = _resolve_record(f)
            elif isinstance(f, v2.Union):
                f.arms = _resolve_fields(block_name, f.arms)
            elif isinstance(f, v2.List):
                if isinstance(f.item, v2.Record):
                    f.item = _resolve_record(f.item)
                else:
                    f.item.arms = _resolve_fields(block_name, f.item.arms)
            result[name] = f
        return result

    return {block_name: _resolve_fields(block, block_name) for block_name, block in blocks.items()}


def map(dfn: v1.Dfn) -> v2.Component:
    """Map a component definition from the v1 schema to v2."""

    if dfn["schema_version"] != "1":
        raise ValueError(f"Expected schema version 1, got {dfn['schema_version']!r}")

    fields = v1.get_fields(dfn)

    def _map_field(field: v1.Field) -> v2.Field:

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

        def __map_field(f: v1.Field) -> v2.Field:
            fd = dict(f)
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
                                fi["block"]
                                for fi in fields.values(multi=True)
                                if fi["name"] == col_name
                                and fi["type"] == "integer"
                                and fi["in_record"]
                            ),
                            None,
                        )
                        if block_name:
                            result.append(f"{block_name}.{elem}")
                    else:
                        provider = next(
                            (
                                fi["name"]
                                for fi in fields.values(multi=True)
                                if fi["type"] == "string"
                                and (fi["shape"] or "").strip() in (f"({elem})", elem)
                            ),
                            None,
                        )
                        result.append(provider if provider else elem)
                return result

            def _to_scalar() -> v2.Scalar:
                assert _type is not None
                if _type == "keyword":
                    return v2.Keyword(
                        name=_name,
                        longname=longname,
                        description=description,
                        optional=optional,
                        default=default,
                        developmode=developmode,
                        netcdf=netcdf,
                    )
                if _type == "string":
                    return v2.String(
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
                    v = [int(x) for x in valid] if valid else None
                    if fd.get("block") == "dimensions":
                        if _name in _DIMS:
                            _dim_scope: (
                                Literal["record", "component", "model", "simulation"] | None
                            ) = "model"
                        elif dfn["name"] == "sim-tdis" and _name == "nper":
                            _dim_scope = "simulation"
                        else:
                            _dim_scope = "component"
                    else:
                        _dim_scope = None
                    return v2.Integer(
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
                    return v2.Double(
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

            def _row_field() -> v2.Record | v2.Union:
                item_names = (_type or "").split()[1:]
                if not item_names:
                    raise ValueError(f"Missing list item definition: {_type!r}")

                item_types = [
                    fi["type"]
                    for fi in fields.values(multi=True)
                    if fi["name"] in item_names and fi["in_record"]
                ]

                if (
                    len(item_names) == 1
                    and item_types
                    and (
                        (item_types[0] or "").startswith("record")
                        or (item_types[0] or "").startswith("keystring")
                    )
                ):
                    mapped = __map_field(next(iter(fields.getlist(item_names[0]))))
                    if isinstance(mapped, (v2.Record, v2.Union)):
                        return mapped
                    raise TypeError(
                        f"Expected Record or Union for list item, got {type(mapped).__name__}"
                    )

                if all(t in v1.SCALAR_TYPES for t in item_types):
                    rec_fields = _record_fields()
                    return v2.Record(
                        name=_name,
                        description=(
                            (description or "").replace("is the list of", "is the record of")
                            or None
                        ),
                        fields=rec_fields,
                    )

                children = {
                    fi["name"]: __map_field(fi)
                    for fi in fields.values(multi=True)
                    if fi["name"] in item_names and fi["in_record"]
                }
                first = next(iter(children.values()))
                if len(children) == 1 and isinstance(first, v2.Union):
                    return first
                return v2.Record(
                    name=_name,
                    description=(
                        (description or "").replace("is the list of", "is the record of") or None
                    ),
                    fields=children,  # type: ignore[arg-type]
                )

            def _union_fields() -> dict:
                names = (_type or "").split()[1:]
                return {
                    fi["name"]: __map_field(fi)
                    for fi in fields.values(multi=True)
                    if fi["name"] in names and fi["in_record"]
                }

            def _record_fields() -> dict:
                names = (_type or "").split()[1:]
                result = {}
                for rname in names:
                    matches = [
                        fi
                        for fi in fields.values(multi=True)
                        if fi["name"] == rname
                        and fi["in_record"]
                        and not (fi["type"] or "").startswith("record")
                    ]
                    if matches:
                        result[rname] = __map_field(matches[0])
                return result

            if _type is None:
                raise ValueError(f"Missing type for v1 field: {_name!r}")

            if _type.startswith("recarray"):
                item = _row_field()
                return v2.List(
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
                return v2.Union(
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
                return v2.Record(
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
                        # If the v1 shape is a single count identifier that isn't
                        # an explicit integer field (e.g. naux for auxiliary), the
                        # array defines that dimension by its length.
                        _str_dim: Literal["component", "model", "simulation"] | None = None
                        _parsed_str = _parse_shape(shape_str)
                        if len(_parsed_str) == 1:
                            _count_name = _parsed_str[0]
                            _is_explicit_int = any(
                                fi["name"] == _count_name and fi["type"] == "integer"
                                for fi in fields.values(multi=True)
                            )
                            if not _is_explicit_int:
                                _str_dim = "component"
                        return v2.Array(
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
                            dimension=_str_dim,
                        )
                    parsed_shape = _parse_shape(shape_str)
                    return v2.Array(
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

        return __map_field(field)

    name = dfn["name"]
    blocks: dict[str, v2.Block] = {}

    for field in fields.values(multi=True):
        if field["in_record"]:  # type: ignore[attr-defined]
            continue  # record subfields are handled recursively
        v2_field = _map_field(field)
        blocks.setdefault(field["block"], v2.Block(name=field["block"], fields={})).fields[
            field["name"]
        ] = v2_field
        blocks[field["block"]].repeats = field.get("block_variable", False)

    blocks = _resolve_dimensions(blocks)
    blocks = _resolve_relations(blocks)

    d: dict[str, Any] = {
        "schema_version": "2",
        "name": name,
        "parent": dfn["parent"],
        "blocks": blocks or None,
    }
    if name == "sim-nam":
        return v2.Simulation(**d)
    if name.endswith("-nam"):
        return v2.Model(**d)

    subtype: Literal["solution", "exchange", "stress", "advanced", "utility"] | None = None
    if name.startswith("sln-"):
        subtype = "solution"
    elif name.startswith("exg-"):
        subtype = "exchange"
    elif name.startswith("utl-"):
        subtype = "utility"
    else:
        is_stress_pkg = bool(any(blocks) and any("period" in k for k in blocks))
        subtype = "advanced" if dfn["advanced"] else "stress" if is_stress_pkg else None
    return v2.Package(
        **d,
        subtype=subtype,
        multi=dfn["multi"],
    )
