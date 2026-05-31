from itertools import groupby
from typing import Any, cast

from boltons.dictutils import OMD
from boltons.iterutils import remap

from modflow_devtools.dfn.migrate_to_v2_0_0_dev0 import (
    is_advanced_package,
    is_multi_package,
    try_parse_mf6_subpackages,
    try_parse_parent,
    try_parse_solution,
)
from modflow_devtools.dfn.schema import SCALAR_TYPES, Dfn, Dfns, Field, Fields
from modflow_devtools.misc import drop_none_or_empty, try_literal_eval


def map_period_block(block: Fields) -> Fields:
    # Extracts recarray fields and creates separate array variables. Gives
    # each an appropriate grid- or tdis-aligned shape as opposed to sparse
    # list shape in terms of maxbound as in definition files.

    block = dict(block)
    fields = list(block.values())
    list_field = next((f for f in fields if cast(str, f.get("type")) == "list"), None)
    if list_field is not None:
        recarray_name = list_field["name"]
        block.pop(recarray_name, None)
        item = next(iter((list_field["children"] or {}).values()))
        columns = dict(item["children"] or {})
    else:
        recarray_name = None
        columns = block

    cellid = columns.pop("cellid", None)
    for col_name, column in columns.items():
        old_dims = column["shape"]
        if old_dims:
            old_dims = old_dims[1:-1].split(",")  # type: ignore
        new_dims = ["nper"]
        if cellid:
            new_dims.append("nnodes")
        if old_dims:
            new_dims.extend([dim for dim in old_dims if dim != "maxbound"])
        column["shape"] = f"({', '.join(new_dims)})"
        block[col_name] = column

    return block


def _map_field(fields: OMD, field: Field) -> Field:
    # parse booleans from strings. everything else can
    # stay a string except default values, which we'll
    # try to parse as arbitrary literals below, and at
    # some point types, once we introduce type hinting
    _attrs: dict[str, Any] = {
        k: v.strip().lower() == "true"
        if isinstance(v, str) and v.strip().lower() in ("true", "false")
        else v
        for k, v in field.items()
    }
    _name = _attrs.pop("name")
    _type = _attrs.pop("type", None)
    shape = _attrs.pop("shape", None)
    shape = None if shape == "" else shape
    block = _attrs.pop("block", None)
    default = _attrs.pop("default_value", None)
    default = try_literal_eval(default) if _type != "string" else default
    description = _attrs.pop("description", "")

    # Build the result dict before defining closures so that closures
    # capture the full field dict (matching the old behaviour where they
    # captured _field after its reassignment to the Field constructor result).
    _field: dict[str, Any] = {
        "name": _name,
        "shape": shape,
        "block": block,
        "description": description,
        "default": default,
        **_attrs,
    }

    def _row_field() -> Field:
        """Parse a table's record (row) field"""
        item_names = _type.split()[1:]
        item_types = [
            f["type"]
            for f in fields.values(multi=True)
            if f["name"] in item_names and f["in_record"]
        ]
        n_item_names = len(item_names)
        if n_item_names < 1:
            raise ValueError(f"Missing list definition: {_type}")

        # explicit record or keystring
        if n_item_names == 1 and (
            item_types[0].startswith("record") or item_types[0].startswith("keystring")
        ):
            return _map_field(fields, next(iter(fields.getlist(item_names[0]))))

        # implicit record with all scalar fields
        if all(t in SCALAR_TYPES for t in item_types):
            children = _record_fields()
            return cast(
                Field,
                {
                    **_field,
                    "name": _name,
                    "type": "record",
                    "block": block,
                    "children": children,
                    "description": description.replace("is the list of", "is the record of"),
                },
            )

        # implicit record with composite fields
        children = {
            f["name"]: _map_field(fields, f)
            for f in fields.values(multi=True)
            if f["name"] in item_names and f["in_record"]
        }
        first = next(iter(children.values()))
        if not first["type"]:
            raise ValueError(f"Missing type for field: {first['name']}")
        single = len(children) == 1
        item_type = "keystring" if single and "keystring" in first["type"] else "record"
        return cast(
            Field,
            {
                "name": first["name"] if single else _name,
                "type": item_type,
                "block": block,
                "children": first["children"] if single else children,
                "description": description.replace("is the list of", f"is the {item_type} of"),
                **_field,
            },
        )

    def _union_fields() -> Fields:
        """Parse a union's fields"""
        names = _type.split()[1:]
        return {
            f["name"]: _map_field(fields, f)
            for f in fields.values(multi=True)
            if f["name"] in names and f["in_record"]
        }

    def _record_fields() -> Fields:
        """Parse a record's fields"""
        names = _type.split()[1:]
        result = {}
        for name in names:
            matching = [
                f
                for f in fields.values(multi=True)
                if f["name"] == name
                and f.get("in_record", False)
                and not f["type"].startswith("record")
            ]
            if matching:
                result[name] = _map_field(fields, matching[0])
        return result

    if _type.startswith("recarray"):
        child = _row_field()
        _field["children"] = {child["name"]: child}
        _field["type"] = "list"

    elif _type.startswith("keystring"):
        _field["children"] = _union_fields()
        _field["type"] = "union"

    elif _type.startswith("record"):
        _field["children"] = _record_fields()
        _field["type"] = "record"

    # for now, we can tell a var is an array if its type
    # is scalar and it has a shape. once we have proper
    # typing, this can be read off the type itself.
    elif shape is not None and _type not in SCALAR_TYPES:
        raise TypeError(f"Unsupported array type: {_type}")

    else:
        # Map v1 type names to v2 type names
        type_map = {
            "double precision": "double",
        }
        _field["type"] = type_map.get(_type, _type)

    return cast(Field, _field)


def to_v2_0_0_dev1(name: str, fields: OMD, meta: list[str]) -> Dfn:
    blocks: dict[str, Fields] = {
        block_name: {
            field["name"]: _map_field(fields, cast(Field, field))
            for field in block
            if field.get("in_record") != "true"
        }
        for block_name, block in groupby(fields.values(multi=True), lambda field: field["block"])
    }

    if (period_block := blocks.get("period", None)) is not None:
        blocks["period"] = map_period_block(period_block)

    def remove_unneeded_attrs(path, key, value):
        if key in ["in_record", "tagged", "preserve_case"]:
            return False
        return True

    blocks = remap(blocks, visit=remove_unneeded_attrs)

    return Dfn(
        name=name,
        schema_version="2.0.0.dev1",
        parent=try_parse_parent(meta),
        advanced=is_advanced_package(meta),
        multi=is_multi_package(meta),
        sln=try_parse_solution(meta),
        ftype=(name.split("-", 1)[1].upper() if "-" in name else None) if name else None,
        subcomponents=try_parse_mf6_subpackages(meta),
        blocks=blocks,
    )


def to_tree(dfns: Dfns) -> Dfn:
    """
    Infer the MODFLOW 6 input component hierarchy from a flat spec:
    unlinked DFNs, i.e. without `children` populated, only `parent`.

    Returns the root component. There must be exactly one root, i.e.
    component with no `parent`. Composite components have `children`
    populated.

    Assumes DFNs are already in v2 schema, just lacking parent-child
    links; before calling this function, map them first with `map()`.
    """

    def set_parent(dfn):
        if (dfn_name := dfn["name"]) == "sim-nam":
            pass
        elif dfn_name.endswith("-nam"):
            dfn["parent"] = "sim-nam"
        elif (
            dfn_name.startswith("exg-")
            or dfn_name.startswith("sln-")
            or dfn_name.startswith("utl-")
        ):
            dfn["parent"] = "sim-nam"
        elif "-" in dfn_name:
            mdl = dfn_name.split("-")[0]
            dfn["parent"] = f"{mdl}-nam"

        return Dfn(**remap(dfn, visit=drop_none_or_empty))

    dfns = {name: set_parent(dfn) for name, dfn in dfns.items()}
    if not any(dfns):
        raise ValueError("No definitions provided")

    if str(next(iter(dfns.values())).get("schema_version", None)) != "2.0.0.dev1":
        raise ValueError("Expected schema version 2.0.0.dev1")

    if (
        nroots := len(
            roots := {name: dfn for name, dfn in dfns.items() if dfn.get("parent", None) is None}
        )
    ) != 1:
        raise ValueError(f"Expected one root component, found {nroots}")

    def _build_tree(node_name: str) -> Dfn:
        node = dfns[node_name]
        children = {name: dfn for name, dfn in dfns.items() if dfn.get("parent", None) == node_name}
        if any(children):
            node["children"] = {name: _build_tree(name) for name in sorted(children.keys())}
        return node

    return _build_tree(next(iter(roots.keys())))


def to_flat(dfn: Dfn) -> Dfns:
    """
    Flatten a MODFLOW 6 input component hierarchy to a flat spec:
    unlinked DFNs, i.e. without `children` populated, only `parent`.

    Returns a dictionary of all components in the specification.
    """

    def _flatten(dfn: Dfn) -> Dfns:
        dfns = {dfn["name"]: {**dfn, "children": None}}
        for child in (dfn["children"] or {}).values():
            dfns.update(_flatten(child))  # type: ignore
        return dfns  # type: ignore

    return _flatten(dfn)
