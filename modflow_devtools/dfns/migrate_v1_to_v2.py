import re
from collections.abc import Mapping
from typing import Any, Literal

from modflow_devtools.dfn import schema as v1
from modflow_devtools.dfn.parser import try_parse_bool
from modflow_devtools.dfns import schema as v2
from modflow_devtools.misc import try_literal_eval

_IDENT_RE = re.compile(r"^[A-Za-z_]\w*$")
_LOOKUP_RE = re.compile(r"^(\w+)\.(\w+)\((\w+)\)$")

_DEPENDENT_VARS: dict[str, str] = {
    "gwf": "head",
    "gwt": "concentration",
    "gwe": "temperature",
    "chf": "stage",
    "olf": "stage",
    "swf": "stage",
    # prt: particle tracking; no scalar dependent variable
}

_OC_RTYPE_VALID: dict[str, list[str]] = {
    "gwf": ["HEAD", "BUDGET"],
    "gwt": ["CONCENTRATION", "BUDGET"],
    "gwe": ["TEMPERATURE", "BUDGET"],
    "chf": ["STAGE", "BUDGET"],
    "olf": ["STAGE", "BUDGET"],
    "swf": ["STAGE", "BUDGET"],
    "prt": ["BUDGET"],
}


def _scope_for(
    parent: "str | list[str] | None",
) -> "Literal['component', 'model', 'simulation']":
    """
    Derive the DimDef scope for dims in a component's dimensions block from its parent.

    - Parent is a model (``<type>-nam``) or a generic type (``"model"``,
      ``"package"``, ``"*"``) → ``"model"``
    - Parent is ``"sim-nam"`` (directly under simulation) → ``"simulation"``
    - Otherwise → ``"component"``
    """
    parents = ([parent] if isinstance(parent, str) else parent) if parent is not None else []
    for p in parents:
        if p == "sim-nam":
            return "simulation"
        if p.endswith("-nam") or p in ("model", "package", "*"):
            return "model"
    return "component"


def _raw_dim_names(blocks: dict[str, v2.Block]) -> set[str]:
    """Names of all Integer fields in the dimensions block."""
    dim_block = blocks.get("dimensions")
    if not dim_block:
        return set()
    return {fname for fname, f in dim_block.fields.items() if isinstance(f, v2.Integer)}


def _parse_list_shape(s: str) -> list[str]:
    """
    Parse a v1 recarray shape string into a ``List.shape`` value.

    Only a bare identifier is accepted — complex expressions such as
    ``sum(nlakeconn)`` cannot be represented in ``List.shape`` and are dropped.
    """
    if not s:
        return []
    s_clean = s.strip()
    if s_clean.startswith("(") and s_clean.endswith(")"):
        s_clean = s_clean[1:-1].strip()
    if _IDENT_RE.fullmatch(s_clean):
        return [s_clean]
    return []


def _normalize_n_prefix_shapes(
    blocks: dict[str, v2.Block],
    raw_dim_names: set[str],
) -> dict[str, v2.Block]:
    """
    Fix List shapes that use ``nFoo`` where the actual dimension is ``maxFoo``.

    Some v1 DFNs (e.g. ``gwf-mvr [packages]`` with ``shape (npackages)``) use
    an ``n``-prefixed name while the dimensions block defines the same quantity
    under a ``max``-prefixed name.  Normalise before building explicit dims.
    """
    result = {}
    for bname, block in blocks.items():
        new_fields = {}
        changed = False
        for fname, field in block.fields.items():
            if isinstance(field, v2.List) and field.shape:
                elem = field.shape[0]
                if elem not in raw_dim_names and elem.startswith("n") and len(elem) > 1:
                    candidate = "max" + elem[1:]
                    if candidate in raw_dim_names:
                        field = field.model_copy(update={"shape": [candidate]})
                        changed = True
            new_fields[fname] = field
        result[bname] = block.model_copy(update={"fields": new_fields}) if changed else block
    return result


def _build_explicit_dims(
    parent: "str | list[str] | None",
    blocks: dict[str, v2.Block],
) -> dict[str, v2.Dim]:
    """Build the dims section from a component's dimensions block."""
    dims: dict[str, v2.Dim] = {}
    dim_block = blocks.get("dimensions")
    if not dim_block:
        return dims

    scope = _scope_for(parent)
    for fname, field in dim_block.fields.items():
        if isinstance(field, v2.Integer):
            dims[fname] = v2.Dim(field=fname, scope=scope)

    if scope == "model":
        has = set(dims.keys())
        if {"nlay", "nrow", "ncol"} <= has:
            dims["ncpl"] = v2.Dim(expr="nrow * ncol", scope="model")
            dims["nodes"] = v2.Dim(expr="nlay * nrow * ncol", scope="model")
            dims["ncelldim"] = v2.Dim(expr="3", scope="model")
        elif {"nlay", "ncpl"} <= has:
            dims["nodes"] = v2.Dim(expr="nlay * ncpl", scope="model")
            dims["ncelldim"] = v2.Dim(expr="2", scope="model")
        elif {"nrow", "ncol"} <= has:
            dims["ncpl"] = v2.Dim(expr="nrow * ncol", scope="model")
            dims["nodes"] = v2.Dim(expr="nrow * ncol", scope="model")
            dims["ncelldim"] = v2.Dim(expr="2", scope="model")
        elif "nodes" in has:
            dims["ncelldim"] = v2.Dim(expr="1", scope="model")

    return dims


def _sanitize_list_shapes(
    blocks: dict[str, v2.Block],
    known_dims: set[str],
) -> dict[str, v2.Block]:
    """
    Clear the shape of any List whose shape element doesn't resolve to a known
    dim.

    Advanced packages (LAK, SFR, GNC, transport packages, etc.) often carry
    ``shape (maxbound)`` in their v1 DFNs as a convention even though
    ``maxbound`` is not declared as a dimension.  The structurally correct v2
    representation for such lists is ``shape=[]``.
    """
    result = {}
    for bname, block in blocks.items():
        new_fields = {}
        changed = False
        for fname, field in block.fields.items():
            if isinstance(field, v2.List) and field.shape:
                if any(elem not in known_dims for elem in field.shape):
                    field = field.model_copy(update={"shape": []})
                    changed = True
            new_fields[fname] = field
        result[bname] = block.model_copy(update={"fields": new_fields}) if changed else block
    return result


def _resolve_dimensions(
    blocks: dict[str, v2.Block],
) -> tuple[dict[str, v2.Block], dict[str, v2.Dim]]:
    """
    Detect self-sizing arrays whose name is referenced in another array's shape
    expression — those define a component-scoped dimension.

    Any array type qualifies (not just string). Returns the unchanged blocks
    alongside a dict of component-scoped DimDef entries.
    """
    self_sizing: set[str] = set()
    shape_refs: set[str] = set()

    def _scan(fields: Mapping[str, v2.Field]) -> None:
        for name, field in fields.items():
            if isinstance(field, v2.Array):
                if not field.shape:
                    self_sizing.add(name)
                else:
                    for elem in field.shape:
                        if _IDENT_RE.fullmatch(elem):
                            shape_refs.add(elem)
            if isinstance(field, v2.Record):
                _scan(field.fields)
            elif isinstance(field, v2.Union):
                _scan(field.arms)
            elif isinstance(field, v2.List):
                item = field.item
                _scan(item.fields if isinstance(item, v2.Record) else item.arms)

    for block in blocks.values():
        _scan(block.fields)

    array_dim_names = self_sizing & shape_refs
    array_dims = {n: v2.Dim(field=n, scope="component") for n in array_dim_names}
    return blocks, array_dims


def _resolve_relations(blocks: dict[str, v2.Block]) -> dict[str, v2.Block]:
    pk_set: set[tuple[str, str]] = set()
    fk_map: dict[tuple[str, str], str] = {}

    def _scan_fields(block_name: str, fields: Mapping[str, v2.Field]) -> None:

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

    def _resolve_fields(block_name: str, fields: Mapping[str, v2.Field]) -> dict[str, v2.Field]:

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
                f.arms = _resolve_fields(block_name, f.arms)  # type: ignore[assignment]
            elif isinstance(f, v2.List):
                if isinstance(f.item, v2.Record):
                    f.item = _resolve_record(f.item)
                else:
                    f.item.arms = _resolve_fields(block_name, f.item.arms)  # type: ignore[assignment]
            result[name] = f
        return result

    return {
        block_name: block.model_copy(update={"fields": _resolve_fields(block_name, block.fields)})
        for block_name, block in blocks.items()
    }


def _fill_period_list_shapes(
    blocks: dict[str, v2.Block],
    explicit_dims: dict[str, v2.Dim],
) -> dict[str, v2.Block]:
    """
    For period blocks whose List field has no shape expression, infer the shape
    from the component's explicit dims.  Currently handles ``maxbound`` only:
    if the component defines a ``maxbound`` dimension but the period list omits
    it, add ``shape=["maxbound"]``.
    """
    if "maxbound" not in explicit_dims:
        return blocks
    result = {}
    for bname, block in blocks.items():
        if "period" not in bname:
            result[bname] = block
            continue
        new_fields = {}
        changed = False
        for fname, field in block.fields.items():
            if isinstance(field, v2.List) and not field.shape:
                field = field.model_copy(update={"shape": ["maxbound"]})
                changed = True
            new_fields[fname] = field
        result[bname] = block.model_copy(update={"fields": new_fields}) if changed else block
    return result


def _wrap_oc_period_records(
    blocks: dict[str, v2.Block],
) -> dict[str, v2.Block]:
    """
    OC packages define their period block as sibling optional Records (saverecord,
    printrecord) with no wrapping List, implying each appears at most once. Wrap
    them into a List[Union] so the repeatable nature is explicit in the schema.
    """
    result = {}
    for bname, block in blocks.items():
        if "period" not in bname:
            result[bname] = block
            continue
        fields = block.fields
        if not fields or any(isinstance(f, v2.List) for f in fields.values()):
            result[bname] = block
            continue
        if not all(isinstance(f, v2.Record) and f.optional for f in fields.values()):
            result[bname] = block
            continue
        union = v2.Union(
            name="output_record",
            arms=dict(fields),  # type: ignore[arg-type]
        )
        lst = v2.List(name="output", optional=True, item=union)
        result[bname] = block.model_copy(update={"fields": {"output": lst}})
    return result


def _collapse_sto_keywords(
    blocks: dict[str, v2.Block],
) -> dict[str, v2.Block]:
    """
    STO packages define their period block with two mutually exclusive optional
    Keywords (steady-state, transient). Replace them with a single optional
    String field named 'storage' with constrained valid values.
    """
    _STO_KEYWORDS = frozenset({"steady-state", "transient"})
    result = {}
    for bname, block in blocks.items():
        if "period" not in bname:
            result[bname] = block
            continue
        fields = block.fields
        present = {
            name
            for name, f in fields.items()
            if isinstance(f, v2.Keyword) and f.optional and name in _STO_KEYWORDS
        }
        if present != _STO_KEYWORDS:
            result[bname] = block
            continue
        non_sto = {name: f for name, f in fields.items() if name not in _STO_KEYWORDS}
        storage = v2.String(
            name="storage",
            longname="storage state",
            description=fields["steady-state"].description,
            optional=True,
            valid=["steady-state", "transient"],
        )
        result[bname] = block.model_copy(update={"fields": {**non_sto, "storage": storage}})
    return result


def _patch_oc_rtype(
    name: str,
    blocks: dict[str, v2.Block],
) -> dict[str, v2.Block]:
    """Set valid values on rtype string fields in OC packages."""
    if not name.endswith("-oc"):
        return blocks
    prefix = name.split("-")[0]
    valid = _OC_RTYPE_VALID.get(prefix)
    if not valid:
        return blocks

    def _patch(fields: dict) -> tuple[dict, bool]:
        new_fields = {}
        changed = False
        for fname, field in fields.items():
            if isinstance(field, v2.String) and fname == "rtype":
                field = field.model_copy(update={"valid": valid})
                changed = True
            elif isinstance(field, v2.Record):
                patched, c = _patch(field.fields)
                if c:
                    field = field.model_copy(update={"fields": patched})
                    changed = True
            elif isinstance(field, v2.Union):
                patched, c = _patch(field.arms)
                if c:
                    field = field.model_copy(update={"arms": patched})
                    changed = True
            elif isinstance(field, v2.List):
                item = field.item
                if isinstance(item, v2.Record):
                    patched, c = _patch(item.fields)
                    if c:
                        field = field.model_copy(
                            update={"item": item.model_copy(update={"fields": patched})}
                        )
                        changed = True
                elif isinstance(item, v2.Union):
                    patched, c = _patch(item.arms)
                    if c:
                        field = field.model_copy(
                            update={"item": item.model_copy(update={"arms": patched})}
                        )
                        changed = True
            new_fields[fname] = field
        return new_fields, changed

    result = {}
    for bname, block in blocks.items():
        new_fields, changed = _patch(block.fields)
        result[bname] = block.model_copy(update={"fields": new_fields}) if changed else block
    return result


def _fix_prt_fmi(component: v2.Component) -> v2.Component:
    """
    Replace prt-fmi's heterogeneous packagedata recarray with three named
    optional File fields — one per flow type (GWFHEAD, GWFBUDGET, GWFSPDIS).
    """
    block = (component.blocks or {}).get("packagedata")
    if block is None:
        return component
    new_fields = {
        name: v2.File(name=name, longname=longname, optional=True, tagged=True, mode="filein")
        for name, longname in (
            ("gwfhead", "gwf head file"),
            ("gwfbudget", "gwf budget file"),
            ("gwfgrid", "gwf grid file"),
        )
    }
    new_blocks = dict(component.blocks or {})
    new_blocks["packagedata"] = block.model_copy(update={"fields": new_fields})
    return component.model_copy(update={"blocks": new_blocks})


def v1_to_v2(dfn: v1.Dfn) -> v2.Component:
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
            fd: dict[str, Any] = {k: try_parse_bool(v) for k, v in dict(f).items()}

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
                                and fi.get("in_record", False)
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
                                and (fi.get("shape") or "").strip() in (f"({elem})", elem)
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
                        valid=valid.split()
                        if isinstance(valid, str) and valid
                        else (list(valid) if valid else None),
                        case_sensitive=preserve_case,
                        time_series=time_series,
                    )
                if _type == "integer":
                    v = (
                        [int(x) for x in valid.split()]
                        if isinstance(valid, str) and valid
                        else ([int(x) for x in valid] if valid else None)
                    )
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
                    if fi["name"] in item_names and fi.get("in_record", False)
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
                    if fi["name"] in item_names and fi.get("in_record", False)
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
                    if fi["name"] in names and fi.get("in_record", False)
                }

            def _record_fields() -> dict:
                names = (_type or "").split()[1:]
                result = {}
                for rname in names:
                    matches = [
                        fi
                        for fi in fields.values(multi=True)
                        if fi["name"] == rname and fi.get("in_record", False)
                    ]
                    if matches:
                        result[rname] = __map_field(matches[0])
                return result

            if _type is None:
                raise ValueError(f"Missing type for v1 field: {_name!r}")

            if _type.startswith("recarray"):
                item = _row_field()
                list_shape = _parse_list_shape(shape_str) if shape_str else []
                return v2.List(
                    name=_name,
                    longname=longname,
                    description=description,
                    optional=optional,
                    default=default,
                    developmode=developmode,
                    netcdf=netcdf,
                    item=item,
                    shape=list_shape,
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
                subnames = (_type or "").split()[1:]
                # Detect filerecord: a subfield named 'filein' or 'fileout' with type keyword
                file_mode: str | None = None
                for sname in subnames:
                    if sname in ("filein", "fileout"):
                        m = next(
                            (
                                fi
                                for fi in fields.values(multi=True)
                                if fi["name"] == sname
                                and try_parse_bool(fi.get("in_record", False))
                            ),
                            None,
                        )
                        if m and (m.get("type") or "").strip() == "keyword":
                            file_mode = sname
                            break

                if file_mode:
                    # Filerecord pattern: <tag_kw> <filein|fileout> <path_string>
                    # In v2: drop the mode keyword and the untagged path string; promote
                    # the tag keyword to a File field (tagged=True, name=tag keyword name).
                    # Find the untagged string (the path value) so we can skip it.
                    path_field_name: str | None = None
                    for sname in subnames:
                        if sname == file_mode:
                            continue
                        m_s = next(
                            (
                                fi
                                for fi in fields.values(multi=True)
                                if fi["name"] == sname
                                and try_parse_bool(fi.get("in_record", False))
                            ),
                            None,
                        )
                        if (
                            m_s
                            and (m_s.get("type") or "").strip() == "string"
                            and not _to_bool(m_s.get("tagged"), True)
                        ):
                            path_field_name = sname
                            break

                    rec_fields = {}
                    for rname in subnames:
                        if rname in (file_mode, path_field_name):
                            continue  # drop mode keyword and path string
                        m = next(
                            (
                                fi
                                for fi in fields.values(multi=True)
                                if fi["name"] == rname
                                and try_parse_bool(fi.get("in_record", False))
                                and not (fi.get("type") or "").startswith("record")
                            ),
                            None,
                        )
                        if m is None:
                            continue
                        ftype = (m.get("type") or "").strip()
                        if ftype == "keyword":
                            # Tag keyword becomes the File field (tagged=True, name=keyword name)
                            rec_fields[rname] = v2.File(
                                name=rname,
                                longname=m.get("longname") or None,
                                description=m.get("description") or None,
                                optional=_to_bool(m.get("optional"), False),
                                developmode=_to_bool(m.get("developmode"), False),
                                netcdf=_to_bool(m.get("netcdf"), False),
                                tagged=True,
                                mode=file_mode,  # type: ignore[arg-type]
                            )
                        else:
                            rec_fields[rname] = __map_field(m)  # type: ignore
                else:
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
                        # String arrays in v1 are always self-sizing; whether the
                        # array defines a component dimension is detected generically
                        # by _resolve_dimensions (any self-sizing array referenced
                        # by name in a sibling shape expression is a dim source).
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
        if field.get("in_record", False):
            continue  # record subfields are handled recursively
        v2_field = _map_field(field)
        blocks.setdefault(field["block"], v2.Block(name=field["block"], fields={})).fields[
            field["name"]
        ] = v2_field
        blocks[field["block"]].repeats = field.get("block_variable", False)

    blocks, array_dims = _resolve_dimensions(blocks)
    blocks = _resolve_relations(blocks)
    raw_dim_names = _raw_dim_names(blocks)
    blocks = _normalize_n_prefix_shapes(blocks, raw_dim_names)
    explicit_dims = _build_explicit_dims(dfn["parent"], blocks)
    known_dims = set(explicit_dims) | set(array_dims)
    blocks = _sanitize_list_shapes(blocks, known_dims)
    blocks = _fill_period_list_shapes(blocks, explicit_dims)
    blocks = _wrap_oc_period_records(blocks)
    blocks = _collapse_sto_keywords(blocks)
    blocks = _patch_oc_rtype(name, blocks)
    dims = {**explicit_dims, **array_dims} or None

    d: dict[str, Any] = {
        "schema_version": "2",
        "name": name,
        "parent": dfn["parent"],
        "blocks": blocks or None,
        "dims": dims,
    }
    if name == "sim-nam":
        return v2.Simulation(**d)
    if name.endswith("-nam"):
        prefix = name.split("-")[0]
        return v2.Model(**d, dependent_variable=_DEPENDENT_VARS.get(prefix))

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
    pkg = v2.Package(**d, subtype=subtype, multi=dfn["multi"])
    if name == "prt-fmi":
        return _fix_prt_fmi(pkg)
    return pkg
