"""
MODFLOW 6 definition file tools.
"""

import re
import warnings
from abc import ABC, abstractmethod
from dataclasses import asdict
from itertools import groupby
from os import PathLike
from pathlib import Path
from typing import (
    Annotated,
    Any,
    Literal,
    cast,
)

import tomli
from boltons.dictutils import OMD
from packaging.version import Version
from pydantic import BaseModel, ConfigDict, GetCoreSchemaHandler
from pydantic_core import core_schema

from modflow_devtools.dfns.parse import (
    is_advanced_package,
    is_multi_package,
    parse_dfn,
    parse_mf6_subpackages,
    try_parse_bool,
    try_parse_parent,
)
from modflow_devtools.dfns.schema.v1 import SCALAR_TYPES as V1_SCALAR_TYPES
from modflow_devtools.dfns.schema.v1 import FieldV1
from modflow_devtools.dfns.schema.v2 import (
    Array,
    Block,
    Blocks,
    Component,
    DfnSpec,
    Double,
    FieldBase,
    FieldV2,
    Integer,
    Keyword,
    List,
    Record,
    String,
    Union,
)
from modflow_devtools.dfns.schema.v2 import (
    Path as PathField,
)
from modflow_devtools.misc import try_literal_eval

_IDENT_RE = re.compile(r"^[A-Za-z_]\w*$")

# Experimental API warning
warnings.warn(
    "The modflow_devtools.dfns API is experimental and may change or be "
    "removed in future versions without following normal deprecation procedures. "
    "Use at your own risk. To suppress this warning, use:\n"
    "  warnings.filterwarnings('ignore', "
    "message='.*modflow_devtools.dfns.*experimental.*')",
    FutureWarning,
    stacklevel=2,
)

__all__ = [
    "Array",
    "Block",
    "Blocks",
    "Component",
    "Dfn",
    "DfnRegistry",
    "DfnRegistryDiscoveryError",
    "DfnRegistryError",
    "DfnRegistryNotFoundError",
    "DfnSpec",
    "Dfns",
    "Double",
    "FieldBase",
    "FieldV1",
    "FieldV2",
    "Integer",
    "Keyword",
    "List",
    "LocalDfnRegistry",
    "PathField",
    "Record",
    "RemoteDfnRegistry",
    "String",
    "Union",
    "get_dfn",
    "get_dfn_path",
    "get_registry",
    "get_sync_status",
    "is_valid",
    "list_components",
    "load",
    "load_flat",
    "load_tree",
    "map",
    "sync_dfns",
    "to_flat",
    "to_tree",
]


Format = Literal["dfn", "toml"]
"""DFN serialization format."""


Dfns = dict[str, "Dfn"]


class _VersionAnnotation:
    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler) -> Any:
        return core_schema.no_info_plain_validator_function(
            lambda v: Version(str(v)) if not isinstance(v, Version) else v,
            serialization=core_schema.to_string_ser_schema(),
        )


VersionField = Annotated[Version, _VersionAnnotation]


class Dfn(BaseModel):
    """
    MODFLOW 6 input component definition.

    Attributes
    ----------
    schema_version : Version
        Schema version of this definition.
    name : str
        Component name (e.g., "gwf-chd", "sim-nam").
    parent : str | list[str] | None
        Valid parent component type(s).
    advanced : bool
        Whether this is an advanced package.
    multi : bool
        Whether this is a multi-package.
    variant_of : str | None
        If set, names the canonical component this is a format variant of.
    blocks : dict[str, Any] | None
        Block definitions containing field specifications.
    children : dict[str, Dfn] | None
        Child component instances (populated by to_tree).
    subcomponents : list[str] | None
        Allowed child component types (schema-level constraint).
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    schema_version: VersionField
    name: str
    parent: str | list[str] | None = None
    advanced: bool = False
    multi: bool = False
    variant_of: str | None = None
    blocks: dict[str, Any] | None = None
    children: "dict[str, Dfn] | None" = None
    subcomponents: list[str] | None = None

    @property
    def fields(self) -> Any:
        """
        Combined map of fields from all blocks (flat, top-level only).

        Returns an OMD to support duplicate field names across v1 blocks.
        """
        items = []
        for block in (self.blocks or {}).values():
            for f in block.values():
                items.append((f.name, f))
        return OMD(items)

    @classmethod
    def from_dict(cls, d: dict, strict: bool = False) -> "Dfn":
        """
        Create a Dfn from a dictionary.

        Parameters
        ----------
        d : dict
            Dictionary containing DFN data.
        strict : bool, optional
            If True, raise ValueError for unrecognized keys at any level.
        """
        known_keys = set(cls.model_fields.keys())
        schema_version = Version(str(d.get("schema_version", "2")))
        is_v1 = schema_version == Version("1")

        if strict:
            extra = set(d.keys()) - known_keys
            if extra:
                raise ValueError(f"Unrecognized keys in DFN data: {extra}")

        data = {k: v for k, v in d.items() if k in known_keys}
        data.setdefault("schema_version", schema_version)

        if blocks_raw := data.get("blocks"):
            parsed_blocks: dict[str, Any] = {}
            for block_name, block_data in blocks_raw.items():
                if not isinstance(block_data, dict):
                    parsed_blocks[block_name] = block_data
                    continue
                block_fields: dict[str, Any] = {}
                for field_name, field_data in block_data.items():
                    if isinstance(field_data, dict):
                        if is_v1:
                            block_fields[field_name] = FieldV1.from_dict(field_data, strict=strict)
                        else:
                            block_fields[field_name] = FieldBase.from_dict(
                                field_data, strict=strict
                            )
                    else:
                        block_fields[field_name] = field_data
                parsed_blocks[block_name] = block_fields
            data["blocks"] = parsed_blocks

        return cls.model_validate(data)


def _dfn_to_plain_dict(dfn: "Dfn") -> dict:
    """Serialize a Dfn to a plain Python dict, serializing any Pydantic field instances."""
    d = dfn.model_dump(exclude_none=True)
    if blocks := d.get("blocks"):
        for block_name, block_fields in blocks.items():
            for field_name, field_val in list(block_fields.items()):
                if isinstance(field_val, BaseModel):
                    blocks[block_name][field_name] = field_val.model_dump(exclude_none=True)
    return d


def _toml_safe(obj: Any) -> Any:
    """Recursively coerce non-TOML-native types to str."""
    if isinstance(obj, BaseModel):
        return _toml_safe(obj.model_dump(exclude_none=True))
    if isinstance(obj, dict):
        return {k: _toml_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_toml_safe(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


class SchemaMap(ABC):
    @abstractmethod
    def map(self, dfn: Dfn) -> Dfn: ...


class MapV1To2(SchemaMap):
    @staticmethod
    def map_period_block(dfn: "Dfn", block: dict) -> dict:
        """
        Convert a period block recarray to individual arrays, one per column.
        """
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
                # Composite column (Record, Union, etc.) — keep as-is
                block[col_name] = column
                continue

            from modflow_devtools.dfns.schema.v2 import GRID_DIM_NAMESPACE

            old_dims = list(column.shape) if isinstance(column, Array) else []
            new_dims = ["nper"]
            if cellid:
                new_dims.append("nodes")
            # Only carry structural grid dims forward; runtime-only inline
            # counts (e.g. naux) are not declared shape dims in v2.
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
    def map_field(dfn: "Dfn", v1_field: FieldV1) -> FieldBase:
        """
        Convert a v1 field to the appropriate v2 concrete type.
        """
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
                # Strip exactly one pair of outer parentheses to avoid munging
                # nested forms like (ncon(ifno)).
                if s_clean.startswith("(") and s_clean.endswith(")"):
                    s_clean = s_clean[1:-1]
                for elem in (x.strip() for x in s_clean.split(",") if x.strip()):
                    if ";" in elem:
                        # v1 discretization-conditional (e.g. "ncol*nrow; ncpl")
                        # → canonical per-layer count; DIS derives ncpl = nrow*ncol.
                        result.append("ncpl")
                    elif (
                        elem in ("any1d", "unknown") or elem.startswith("<") or elem.startswith(">")
                    ):
                        # v1 pseudo-elements with no v2 shape equivalent:
                        #   any1d   — inline array of runtime-determined length
                        #             (read to end of record); dtype-agnostic.
                        #   <X / >X — bound annotations (e.g. "<nstp").
                        # TODO: preserve </>  once v1 DFN typos are fixed.
                        pass
                    elif m := _COL_FK_RE.fullmatch(elem):
                        # v1 shorthand: column(fk_field) with no block prefix.
                        # Resolve the block by searching for the integer field.
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
                        # else: unresolvable; drop with no shape element
                    else:
                        # Check if elem is an implicit count (e.g. "naux") for a
                        # string array whose v1 shape is (elem). If so, emit the
                        # string array's name so _mark_string_dim_arrays can mark
                        # it dimension="component" and validation resolves it.
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

            def _row_field() -> "Record | Union":
                item_names = (_type or "").split()[1:]
                if not item_names:
                    raise ValueError(f"Missing list item definition: {_type!r}")

                item_types = [
                    fi.type
                    for fi in fields.values(multi=True)
                    if fi.name in item_names and fi.in_record
                ]

                # Single explicit record or keystring
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

                # All scalars → implicit Record
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

                # Mixed composites
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
                        # String arrays are inline and self-sizing in v2; drop
                        # the v1 shape expression. dimension=True is set in a
                        # second pass if another array references this field.
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
    def _mark_dimension_fields(blocks: "dict[str, dict]") -> "dict[str, dict]":
        """
        Post-pass: annotate every field that provides a dimension count.

        Two concerns are handled in one pass because they share a scan phase
        and have an ordering dependency — string-array dim providers must be
        known before record-local dim integers can be identified (so their
        names are excluded from the "local" check).

        String-array dim providers (e.g. ``auxiliary``): a string Array whose
        name is referenced as a plain identifier in any non-string Array's
        shape.  Marked ``dimension="component"``.

        Record-local dim integers: an Integer field inside a Record that is
        named by a sibling non-string Array's shape element and does not
        resolve to any globally-scoped dim.  Marked ``dimension="record"``.
        """
        from modflow_devtools.dfns.schema.v2 import GRID_DIM_NAMESPACE

        # ── Phase 1: single scan ──────────────────────────────────────────
        # Collect plain-identifier shape refs from non-string Arrays, names
        # of all string Arrays, and any already-explicit global dim names.
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

        # ── Phase 2: derive complete global dim set ───────────────────────
        # String arrays referenced by name in a non-string array's shape are
        # dim providers; add them to global_dims so they are not mistakenly
        # identified as record-local dims in the mark phase below.
        string_provider_names: set[str] = string_array_names & shape_refs
        global_dims: set[str] = explicit_globals | string_provider_names

        # ── Phase 3: mark ─────────────────────────────────────────────────
        def _record_local_dims(rec: "Record") -> set[str]:
            """Integer field names in rec that serve as per-row inline counts."""
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
    def _infer_fk_from_shapes(blocks: "dict[str, dict]") -> "dict[str, dict]":
        """
        Post-pass 3: infer fk= and pk= from resolved lookup shape elements.

        When _parse_shape resolves a v1 shorthand like "col(fk_field)" to the
        canonical form "block.col(fk_field)", the fk_field sibling in the same
        enclosing record implicitly references that block. This pass:
          - infers fk = "block.fk_field" on that sibling (enables check 4 of
            _validate_shape_element), and
          - infers pk = True on the same-named field in the referenced block's
            list item (required by _validate_fk_fields).
        Both marks are only applied when the attribute is not already set.
        """
        _lookup_re = re.compile(r"^(\w+)\.(\w+)\((\w+)\)$")

        # Phase 1: collect inferred FK and PK pairs.
        # fk_map: (enclosing_block, fk_field_name) -> fk value string
        # pk_set: (pk_block, pk_field_name) pairs that need pk=True
        fk_map: dict[tuple[str, str], str] = {}
        pk_set: set[tuple[str, str]] = set()

        def _scan_record(rec: "Record", block_name: str) -> None:
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

        # Phase 2: apply FK and PK markings.
        def _apply_record(rec: "Record", block_name: str) -> "Record":
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
    def map_blocks(dfn: "Dfn") -> dict:
        """
        Convert all v1 fields in a DFN to v2 types and return a block dict.

        Structured as three phases; phases 2 and 3 are post-passes because
        cross-field relationships cannot be determined field-by-field:

        1. Field conversion (``map_field`` per top-level field): translate
           each FieldV1 to the appropriate v2 concrete type.  Per-field only;
           cross-field relationships are deferred.

        2. Dimension annotation (``_mark_dimension_fields``): scan the
           completed blocks and annotate every dimension-providing field:
           string Arrays referenced by non-string Array shapes (→
           ``dimension="component"``) and Record-local inline-count Integers
           (→ ``dimension="record"``).

        3. FK/PK inference (``_infer_fk_from_shapes``): scan for resolved
           ``block.col(fk_field)`` shape elements and infer the corresponding
           ``fk=`` and ``pk=`` annotations.  Only applies to components with
           implicit cross-block FK relationships (gwf-sfr in v1).
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
    def to_component(dfn: "Dfn") -> "Any":
        """
        Convert a v2 Dfn to the appropriate Component
        (Simulation, Model, or Package), inferring the type from the
        component name and parsed metadata.

        The Dfn must already be at schema version 2 (field types must be
        v2 concrete FieldBase instances, not FieldV1 dataclasses).
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
            return Package(**common, subtype="solution", multi=dfn.multi, variant_of=dfn.variant_of)
        if name.startswith("exg-"):
            return Package(**common, subtype="exchange", multi=dfn.multi, variant_of=dfn.variant_of)
        if name.startswith("utl-"):
            return Package(**common, subtype="utility", multi=dfn.multi, variant_of=dfn.variant_of)
        has_period = bool(blocks and any("period" in k for k in blocks))
        subtype: Literal["solution", "exchange", "stress", "advanced", "utility"] | None = (
            "advanced" if dfn.advanced else "stress" if has_period else None
        )
        return Package(**common, subtype=subtype, multi=dfn.multi, variant_of=dfn.variant_of)

    def map(self, dfn: "Dfn") -> "Dfn":
        if dfn.schema_version == Version("2"):
            return dfn
        return Dfn(
            name=dfn.name,
            schema_version=Version("2"),
            parent=dfn.parent,
            advanced=dfn.advanced,
            multi=dfn.multi,
            variant_of=dfn.variant_of,
            blocks=MapV1To2.map_blocks(dfn),
            subcomponents=dfn.subcomponents,
        )


def map(
    dfn: Dfn,
    schema_version: str | Version = "2",
) -> Dfn:
    """Map a MODFLOW 6 specification to another schema version."""
    version = Version(str(schema_version))
    if version == dfn.schema_version:
        return dfn
    elif version == Version("1"):
        raise NotImplementedError("Mapping to schema version 1 is not implemented yet.")
    elif version == Version("2"):
        return MapV1To2().map(dfn)
    raise ValueError(f"Unsupported schema version: {schema_version}. Expected 1 or 2.")


def load(f, format: str = "dfn", **kwargs) -> Dfn:
    """Load a MODFLOW 6 definition file."""
    if format == "dfn":
        name = kwargs.pop("name")
        fields_parsed, meta = parse_dfn(f, **kwargs)
        blocks = {
            block_name: {field_dict["name"]: FieldV1.from_dict(field_dict) for field_dict in block}
            for block_name, block in groupby(
                fields_parsed.values(multi=True), lambda fd: fd["block"]
            )
        }
        subcomponents = parse_mf6_subpackages(meta)
        return Dfn(
            name=name,
            schema_version=Version("1"),
            parent=try_parse_parent(meta),
            advanced=is_advanced_package(meta),
            multi=is_multi_package(meta),
            blocks=blocks,
            subcomponents=subcomponents if subcomponents else None,
        )

    elif format == "toml":
        data = tomli.load(f)
        dfn_name = data.pop("name", kwargs.pop("name", None))

        dfn_fields: dict[str, Any] = {
            "name": dfn_name,
            "schema_version": Version(str(data.pop("schema_version", "2"))),
            "parent": data.pop("parent", None),
            "advanced": data.pop("advanced", False),
            "multi": data.pop("multi", False),
            "variant_of": data.pop("variant_of", None),
        }

        if (expected_name := kwargs.pop("name", None)) is not None:
            if dfn_fields["name"] != expected_name:
                raise ValueError(f"DFN name mismatch: {expected_name} != {dfn_fields['name']}")

        blocks = {}
        for section_name, section_data in data.items():
            if isinstance(section_data, dict):
                block_fields: dict[str, Any] = {}
                for field_name, field_data in section_data.items():
                    if isinstance(field_data, dict):
                        block_fields[field_name] = FieldBase.from_dict(field_data)
                    else:
                        block_fields[field_name] = field_data
                blocks[section_name] = block_fields

        dfn_fields["blocks"] = blocks if blocks else None
        return Dfn(**dfn_fields)

    raise ValueError(f"Unsupported format: {format}. Expected 'dfn' or 'toml'.")


def _load_common(f) -> Any:
    common, _ = parse_dfn(f)
    return common


def load_flat(path: str | PathLike) -> Dfns:
    """
    Load a flat MODFLOW 6 specification from definition files in a directory.

    Returns a dictionary of unlinked DFNs, i.e. without `children` populated.
    """
    exclude = ["common", "flopy"]
    path = Path(path).expanduser().resolve()

    dfn_paths = {p.stem: p for p in path.glob("*.dfn") if p.stem not in exclude}
    toml_paths = {p.stem: p for p in path.glob("*.toml") if p.stem not in exclude}
    dfns = {}
    if dfn_paths:
        with (path / "common.dfn").open() as f:
            common = _load_common(f)
        for dfn_name, dfn_path in dfn_paths.items():
            with dfn_path.open() as f:
                dfns[dfn_name] = load(f, name=dfn_name, common=common, format="dfn")
    if toml_paths:
        for toml_name, toml_path in toml_paths.items():
            with toml_path.open("rb") as f:
                dfns[toml_name] = load(f, name=toml_name, format="toml")
    return dfns


def load_tree(path: str | PathLike) -> Dfn:
    """
    Load a structured MODFLOW 6 specification from definition files in a directory.

    A single root component definition (the simulation) is returned with
    nested children.
    """
    return to_tree(load_flat(path))


def _infer_parent(name: str) -> "str | None":
    """Infer the parent component name from a component name using MF6 conventions."""
    if name == "sim-nam":
        return None
    if name.endswith("-nam"):
        return "sim-nam"
    if name.startswith(("exg-", "sln-", "utl-")):
        return "sim-nam"
    if "-" in name:
        mdl = name.split("-")[0]
        return f"{mdl}-nam"
    return None


def _resolve_parent_for_tree(name: str, parent: "str | list[str] | None", dfns: Dfns) -> "str | None":
    """
    Resolve a parent value to a specific component name for tree placement.

    When parent is a type label (e.g. "model", ["model", "package"]) or any
    string not present in the known component dict, falls back to name-based
    inference so the DFN is still placed in the tree.
    """
    if parent is None:
        return None
    if isinstance(parent, str) and parent in dfns:
        return parent
    return _infer_parent(name)


def _apply_parent_inference(dfns: Dfns) -> Dfns:
    """Set parent on any Dfn where it is not already explicit."""
    result = {}
    for name, dfn in dfns.items():
        if dfn.parent is None:
            inferred = _infer_parent(name)
            result[name] = dfn.model_copy(update={"parent": inferred}) if inferred else dfn
        else:
            result[name] = dfn
    return result


def to_tree(dfns: Dfns) -> Dfn:
    """
    Infer the MODFLOW 6 input component hierarchy from a flat spec.

    Returns the root component. There must be exactly one root (no parent).
    Assumes DFNs are already in v2 schema.
    """
    dfns = _apply_parent_inference(dfns)
    first_dfn = next(iter(dfns.values()), None)

    match schema_version := str(first_dfn.schema_version if first_dfn else Version("1")):
        case "1":
            raise NotImplementedError("Tree inference from v1 schema not implemented")
        case "2":
            roots = {name: dfn for name, dfn in dfns.items() if dfn.parent is None}
            if (nroots := len(roots)) != 1:
                raise ValueError(f"Expected one root component, found {nroots}")

            def _build_tree(node_name: str) -> Dfn:
                node = dfns[node_name]
                children = {
                    name: dfn
                    for name, dfn in dfns.items()
                    if _resolve_parent_for_tree(name, dfn.parent, dfns) == node_name
                }
                if children:
                    node = node.model_copy(
                        update={"children": {name: _build_tree(name) for name in children}}
                    )
                return node

            return _build_tree(next(iter(roots.keys())))
        case _:
            raise ValueError(f"Unsupported schema version: {schema_version}. Expected 1 or 2.")


def to_flat(dfn: Dfn) -> Dfns:
    """
    Flatten a MODFLOW 6 input component hierarchy to a flat spec.

    Returns a dictionary of all components without `children` populated.
    """

    def _flatten(dfn: Dfn) -> Dfns:
        result: Dfns = {dfn.name: dfn.model_copy(update={"children": None})}
        for child in (dfn.children or {}).values():
            result.update(_flatten(child))
        return result

    return _flatten(dfn)


def is_valid(path: str | PathLike, format: str = "dfn", verbose: bool = False) -> bool:
    """Validate DFN file(s)."""
    path = Path(path).expanduser().absolute()
    try:
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        if path.is_file():
            common = {}  # type: ignore
            if (common_path := path.parent / "common.dfn").exists():
                with common_path.open() as f:
                    common, _ = parse_dfn(f)
                if path.name == "common.dfn":
                    return True
            with path.open() as f:
                load(f, name=path.stem, common=common, format=format)
        else:
            load_flat(path)
        return True
    except Exception as e:
        if verbose:
            print(f"Validation failed: {e}")
        return False


# =============================================================================
# Registry imports and convenience functions
# =============================================================================


def _get_registry_module():
    """Lazy import of registry module to avoid circular imports."""
    from modflow_devtools.dfns import registry

    return registry


def __getattr__(name: str):
    """Lazy attribute access for registry classes."""
    registry_exports = {
        "DfnRegistry",
        "DfnRegistryDiscoveryError",
        "DfnRegistryError",
        "DfnRegistryNotFoundError",
        "LocalDfnRegistry",
        "RemoteDfnRegistry",
        "get_registry",
        "get_sync_status",
        "sync_dfns",
    }
    if name in registry_exports:
        registry = _get_registry_module()
        return getattr(registry, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# =============================================================================
# Module-level convenience functions
# =============================================================================


def get_dfn(
    component: str,
    ref: str = "develop",
    source: str = "modflow6",
    path: str | PathLike | None = None,
) -> "Component":
    """
    Get a component definition by name from the registry.
    """
    registry = _get_registry_module()
    reg = registry.get_registry(source=source, ref=ref, path=path)
    return reg.get_dfn(component)


def get_dfn_path(
    component: str,
    ref: str = "develop",
    source: str = "modflow6",
    path: str | PathLike | None = None,
) -> Path:
    """
    Get the local cached file path for a DFN component.
    """
    registry = _get_registry_module()
    reg = registry.get_registry(source=source, ref=ref, path=path)
    return reg.get_dfn_path(component)


def list_components(
    ref: str = "develop",
    source: str = "modflow6",
    path: str | PathLike | None = None,
) -> list[str]:
    """
    List available components for a registry.
    """
    registry = _get_registry_module()
    reg = registry.get_registry(source=source, ref=ref, path=path)
    return list(reg.spec.components.keys())
