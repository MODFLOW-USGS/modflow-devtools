from itertools import groupby
from typing import Any, cast
from warnings import warn

from boltons.dictutils import OMD

from modflow_devtools.dfn import SCALAR_TYPES
from modflow_devtools.dfn.schema import Dfn, Field, Fields, FieldType, Ref, Sln
from modflow_devtools.misc import try_literal_eval


def field_attr_sort_key(item) -> int:
    """
    Sort key for input field attributes. The order is:
    -1. block
    0. name
    1. type
    2. shape
    3. default
    4. reader
    5. optional
    6. longname
    7. description
    """

    k, _ = item
    if k == "block":
        return -1
    if k == "name":
        return 0
    if k == "type":
        return 1
    if k == "shape":
        return 2
    if k == "default":
        return 3
    if k == "reader":
        return 4
    if k == "optional":
        return 5
    if k == "longname":
        return 6
    if k == "description":
        return 7
    return 8


def is_advanced_package(comments: list[str]) -> bool:
    return any("package-type advanced" in line for line in comments)


# Transport and surface-water stress packages that are semantically BndType subclasses
# but whose v1 DFN files lack the "# package-type stress-package" header that GWF
# stress packages carry. Listed explicitly rather than inferred from block structure.
_STRESS_PKG_NAMES = frozenset(
    {
        "gwt-cnc",
        "gwt-src",
        "gwe-ctp",
        "gwe-esl",
        "chf-cdb",
        "chf-chd",
        "chf-flw",
        "chf-evp",
        "chf-pcp",
        "chf-zdg",
        "olf-cdb",
        "olf-chd",
        "olf-flw",
        "olf-evp",
        "olf-pcp",
        "olf-zdg",
        "swf-cdb",
        "swf-chd",
        "swf-flw",
        "swf-evp",
        "swf-pcp",
        "swf-zdg",
        "prt-prp",
    }
)


def is_stress_package(name: str, comments: list[str]) -> bool:
    return (
        any("package-type stress-package" in line for line in comments) or name in _STRESS_PKG_NAMES
    )


def is_multi_package(comments: list[str]) -> bool:
    return any("flopy multi-package" in line for line in comments)


def try_parse_parent(comments: list[str]) -> str | None:
    line = next(
        iter(
            line for line in comments if isinstance(line, str) and line.startswith("# flopy parent")
        ),
        None,
    )
    if not line:
        return None
    split = line.split()
    return split[3]


def try_parse_solution(comments: list[str]) -> Sln | None:
    sln = next(
        iter(
            line
            for line in comments
            if isinstance(line, str) and line.startswith("# flopy solution_package")
        ),
        None,
    )
    if sln:
        _, _, abbr, pattern = sln.split()[1:]
        return Sln(abbr=abbr, pattern=pattern)
    return None


def try_parse_flopy_subpackage(fields: dict, comments: list[str]) -> Ref | None:
    def _rest() -> dict[str, str | None] | None:
        line = next(
            iter(
                line
                for line in comments
                if isinstance(line, str) and line.startswith("# flopy subpackage")
            ),
            None,
        )
        if not line:
            return None
        _, _, _, key, abbr, param, val = line.split()
        matches = [v for v in fields.values() if v["name"] == val]
        if not any(matches):
            descr = None
        else:
            if len(matches) > 1:
                warn(f"Multiple matches for referenced variable {val}")
            match = matches[0]
            descr = match["description"]

        return {
            "key": key,
            "val": val,
            "abbr": abbr,
            "param": param,
            "description": descr,
        }

    parent = try_parse_parent(comments)
    rest = _rest()
    if parent and rest:
        return Ref(
            parent=parent,
            key=cast(str, rest["key"]),
            val=cast(str, rest["val"]),
            abbr=cast(str, rest["abbr"]),
            param=cast(str, rest["param"]),
            description=rest["description"],
        )
    return None


def try_parse_mf6_subpackages(comments: list[str]) -> list[str] | None:
    result = None
    for line in comments:
        if line.startswith("# mf6 subpackage "):
            if result is None:
                result = []
            abbr = line.removeprefix("# mf6 subpackage ").strip().lower()
            result.append(abbr)
    return result


def to_v2_0_0_dev0(name: str, fields: OMD, meta: list[str], refs: dict | None = None) -> Dfn:
    fkeys = {}
    refs = refs or {}

    def _convert_field(var: dict[str, Any]) -> Field:
        """
        Convert an input field specification from its representation
        in a v1 format definition file to the v2 (structured) format.

        Notes
        -----
        If the field does not have a `default` attribute, it will
        default to `False` if it is a keyword, otherwise to `None`.

        A filepath field whose name functions as a foreign key
        for a separate context will be given a reference to it.
        """

        def _load(field) -> Field:
            field = field.copy()

            # parse booleans from strings. everything else can
            # stay a string except default values, which we'll
            # try to parse as arbitrary literals below, and at
            # some point types, once we introduce type hinting
            field = {
                k: v.strip().lower() == "true"
                if isinstance(v, str) and v.strip().lower() in ("true", "false")
                else v
                for k, v in field.items()
            }

            _name = field.pop("name")
            _type = field.pop("type", None)
            shape = field.pop("shape", None)
            shape = None if shape == "" else shape
            block = field.pop("block", None)
            default = field.pop("default", None)
            default = try_literal_eval(default) if _type != "string" else default
            description = field.pop("description", "")
            reader = field.pop("reader", "urword")
            ref = refs.get(_name, None)

            # if the field is a foreign key, register it
            if ref:
                fkeys[_name] = ref

            def _item() -> Field:
                """Load list item."""

                item_names = _type.split()[1:]
                item_types = [
                    v["type"]
                    for v in fields.values(multi=True)
                    if v["name"] in item_names and v.get("in_record", False)
                ]
                n_item_names = len(item_names)
                if n_item_names < 1:
                    raise ValueError(f"Missing list definition: {_type}")

                # explicit record
                if n_item_names == 1 and (
                    item_types[0].startswith("record") or item_types[0].startswith("keystring")
                ):
                    return _convert_field(next(iter(fields.getlist(item_names[0]))))

                # implicit simple record (no children)
                if all(t in SCALAR_TYPES for t in item_types):
                    return Field(
                        name=_name,
                        type="record",
                        block=block,
                        fields=_fields(),
                        description=description.replace("is the list of", "is the record of"),
                        reader=reader,
                        **field,
                    )

                # implicit complex record (has children)
                record_fields = {
                    v["name"]: _convert_field(v)
                    for v in fields.values(multi=True)
                    if v["name"] in item_names and v.get("in_record", False)
                }
                first = next(iter(record_fields.values()))
                single = len(record_fields) == 1
                item_type: FieldType = (
                    "keystring" if single and "keystring" in first["type"] else "record"
                )
                return Field(
                    name=first["name"] if single else _name,
                    type=item_type,
                    block=block,
                    fields=first["fields"] if single else record_fields,
                    description=description.replace("is the list of", f"is the {item_type} of"),
                    reader=reader,
                    **field,
                )

            def _choices() -> Fields:
                """Load keystring (union) choices."""
                names = _type.split()[1:]
                return {
                    v["name"]: _convert_field(v)
                    for v in fields.values(multi=True)
                    if v["name"] in names and v.get("in_record", False)
                }

            def _fields() -> Fields:
                """Load record fields."""
                names = _type.split()[1:]
                return {
                    v["name"]: _convert_field(v)
                    for v in fields.values(multi=True)
                    if v["name"] in names
                    and v.get("in_record", False)
                    and not v["type"].startswith("record")
                }

            var_: Field = cast(
                Field,
                {
                    "name": _name,
                    "shape": shape,
                    "block": block,
                    "description": description,
                    "default": default,
                    "reader": reader,
                    **field,
                },
            )

            if _type.startswith("recarray"):
                var_["item"] = _item()
                var_["type"] = "recarray"

            elif _type.startswith("keystring"):
                var_["choices"] = _choices()
                var_["type"] = "keystring"

            elif _type.startswith("record"):
                var_["fields"] = _fields()
                var_["type"] = "record"

            # for now, we can tell a var is an array if its type
            # is scalar and it has a shape. once we have proper
            # typing, this can be read off the type itself.
            elif shape is not None and _type not in SCALAR_TYPES:
                raise TypeError(f"Unsupported array type: {_type}")

            else:
                var_["type"] = _type

            if ref:
                return Field(
                    name=ref["val"],
                    type=_type,
                    shape=shape,
                    block=block,
                    description=(
                        f"Contains data for the {ref['abbr']} package. Data can be "
                        f"passed as a dictionary to the {ref['abbr']} package with "
                        "variable names as keys and package data as values. Data "
                        f"for the {ref['val']} variable is also acceptable. See "
                        f"{ref['abbr']} package documentation for more information."
                    ),
                    default=None,
                    ref=ref,  # type: ignore[typeddict-unknown-key]
                    reader=reader,
                    **field,
                )

            return var_

        return cast(Field, dict(sorted(_load(var).items(), key=field_attr_sort_key)))

    # load top-level fields. nested fields load recursively
    fields_toplvl = {
        field["name"]: _convert_field(field)
        for field in fields.values(multi=True)
        if not field.get("in_record", False)
    }

    # group fields by block
    blocks = {
        block_name: {v["name"]: v for v in block}
        for block_name, block in groupby(fields_toplvl.values(), lambda v: v["block"])
    }

    # mark transient blocks
    transient_index_vars = fields.getlist("iper")
    for transient_index in transient_index_vars:
        transient_block = transient_index["block"]
        cast(dict[str, Any], blocks[transient_block])["transient_block"] = True

    return Dfn(
        name=name,
        advanced=is_advanced_package(meta),
        multi=is_multi_package(meta),
        schema_version="2.0.0.dev0",
        fkeys=fkeys,
        sln=try_parse_solution(meta),
        ref=try_parse_flopy_subpackage(fields_toplvl, meta),
        subcomponents=try_parse_mf6_subpackages(meta),
        # blocks as top-level attributes
        **cast(dict[str, Any], blocks),  # type: ignore[typeddict-item]
    )
