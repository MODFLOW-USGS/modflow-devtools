"""
MODFLOW 6 definition file tools. Includes types for field
and component specification, a parser for the original
DFN format as well as for TOML definition files, and
a function to fetch DFNs from the MF6 repository.
"""

from ast import literal_eval
from collections.abc import Mapping
from itertools import groupby
from os import PathLike
from pathlib import Path
from typing import (
    Any,
    Literal,
    NotRequired,
    TypedDict,
)
from warnings import warn

import tomli
from boltons.dictutils import OMD
from boltons.iterutils import remap

from modflow_devtools.dfn import parser


def _try_literal_eval(value: str) -> Any:
    """
    Try to parse a string as a literal. If this fails,
    return the value unaltered.
    """
    try:
        return literal_eval(value)
    except (SyntaxError, ValueError):
        return value


def _try_parse_bool(value: Any) -> Any:
    """
    Try to parse a boolean from a string as represented
    in a DFN file, otherwise return the value unaltered.
    """
    if isinstance(value, str):
        value = value.lower()
        if value in ["true", "false"]:
            return value == "true"
    return value


def _field_attr_sort_key(item) -> int:
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


def block_sort_key(item: tuple[str, Any]) -> int:
    """Sort blocks in canonical MF6 order."""
    order = ["options", "dimensions", "griddata", "packagedata", "connectiondata", "period"]
    name = item[0]
    try:
        return order.index(name)
    except ValueError:
        return len(order)


FormatVersion = Literal[1, 2]
"""DFN format version number."""


DfnFormat = Literal["dfn", "toml", "yaml", "json"]
"""DFN serialization format."""


FieldType = Literal[
    "keyword",
    "integer",
    "double precision",
    "string",
    "record",
    "recarray",
    "keystring",
]


Reader = Literal[
    "urword",
    "u1ddbl",
    "u2ddbl",
    "readarray",
]


_SCALAR_TYPES = ("keyword", "integer", "double precision", "string")
SCALAR_TYPES = _SCALAR_TYPES  # public alias


class Field(TypedDict):
    """A field specification."""

    name: str
    type: FieldType
    block: NotRequired[str | None]
    default: NotRequired[Any | None]
    longname: NotRequired[str | None]
    description: NotRequired[str | None]
    optional: NotRequired[bool]
    developmode: NotRequired[bool]
    shape: NotRequired[str | None]
    valid: NotRequired[tuple[str, ...] | None]
    netcdf: NotRequired[bool]
    tagged: NotRequired[bool]
    reader: NotRequired[Reader]
    in_record: NotRequired[bool]
    layered: NotRequired[bool | None]
    preserve_case: NotRequired[bool]
    numeric_index: NotRequired[bool]
    deprecated: NotRequired[bool]
    removed: NotRequired[bool]
    mf6internal: NotRequired[str | None]
    block_variable: NotRequired[bool]
    just_data: NotRequired[bool]
    time_series: NotRequired[bool]
    children: NotRequired[Mapping[str, "Field"] | None]


Fields = Mapping[str, "Field"]
Blocks = Mapping[str, Fields]


class Ref(TypedDict):
    """
    A foreign-key-like reference between a file input variable
    in a referring input component and another input component
    referenced by it. Previously known as a "subpackage".

    A `Dfn` with a nonempty `ref` can be referred to by other
    component definitions, via a filepath variable which acts
    as a foreign key. If such a variable is detected when any
    component is loaded, the component's `__init__` method is
    modified, such that the variable named `val`, residing in
    the referenced component, replaces the variable with name
    `key` in the referencing component, i.e., the foreign key
    filepath variable, This forces a referencing component to
    accept a subcomponent's data directly, as if it were just
    a variable, rather than indirectly, with the subcomponent
    loaded up from a file identified by the filepath variable.
    """

    key: str
    val: str
    abbr: str
    param: str
    parent: str
    description: str | None


class Sln(TypedDict):
    """
    A solution package specification.
    """

    abbr: str
    pattern: str


Dfns = dict[str, "Dfn"]


class Dfn(TypedDict):
    """
    MODFLOW 6 input definition. An input definition
    specifies a component in an MF6 simulation, e.g.
    a model or package. A component contains input
    variables, and may contain other metadata such
    as foreign key references to other components
    (i.e. subpackages), package-specific metadata
    (e.g. for solutions), advanced package status,
    and whether the component is a multi-package.

    An input definition must have a name. Other top-
    level keys are blocks, which must be mappings of
    `str` to `Field`, and metadata, of which only a
    limited set of keys are allowed. Block names and
    metadata keys may not overlap.

    Attributes
    ----------
    name : str
        Component name.
    advanced : bool
        Whether this is an advanced package.
    multi : bool
        Whether this is a multi-package.
    ref : Ref | None
        Metadata if this component is a subpackage (child's perspective).
        Populated from: # flopy subpackage <key> <abbr> <param> <val>
    sln : Sln | None
        Solution package metadata.
    fkeys : Dfns | None
        Field-level foreign key references to other components.
        Maps field names to Ref objects. Populated from flopy subpackage
        metadata when specific fields reference other components.
    subcomponents : list[str] | None
        Allowed child component types (schema-level constraint).
        Populated from: # mf6 subpackage <abbr>
        Example: ['UTL-NCF'] means this component can have utl-ncf children.
        Distinct from fkeys, which are field-level references.
    """

    schema_version: str
    name: str
    ftype: NotRequired[str | None]
    parent: NotRequired[str | list[str] | None]
    blocks: NotRequired[Blocks | None]
    children: NotRequired[Dfns | None]
    advanced: NotRequired[bool]
    multi: NotRequired[bool]
    ref: NotRequired[Ref | None]
    sln: NotRequired[Sln | None]
    fkeys: NotRequired[Dfns | None]  # deprecated
    subcomponents: NotRequired[list[str] | None]

    @staticmethod  # type: ignore[misc]
    def _load_v1_flat(f, common: dict | None = None) -> tuple[Mapping, list[str]]:
        field = {}
        flat = []
        meta = []
        common = common or {}

        for line in f:
            # remove whitespace/etc from the line
            line = line.strip()

            # record context name and flopy metadata
            # attributes, skip all other comment lines
            if line.startswith("#"):
                _, sep, tail = line.partition("flopy")
                if sep == "flopy":
                    if (
                        "multi-package" in tail
                        or "solution_package" in tail
                        or "subpackage" in tail
                        or "parent" in tail
                    ):
                        meta.append(tail.strip())
                _, sep, tail = line.partition("package-type")
                if sep == "package-type":
                    meta.append(f"package-type {tail.strip()}")
                # Parse mf6 subpackage declarations (schema-level composition constraints).
                # Distinct from flopy subpackage (field-level foreign keys, parsed above).
                _, sep, tail = line.partition("mf6 subpackage")
                if sep == "mf6 subpackage":
                    meta.append(f"mf6-subpackage {tail.strip()}")
                continue

            # if we hit a newline and the parameter dict
            # is nonempty, we've reached the end of its
            # block of attributes
            if not any(line):
                if any(field):
                    flat.append((field["name"], field))
                    field = {}
                continue

            # split the attribute's key and value and
            # store it in the parameter dictionary
            key, _, value = line.partition(" ")
            if key == "default_value":
                key = "default"
            field[key] = value

            # make substitutions from common variable definitions,
            # remove backslashes, TODO: generate/insert citations.
            descr = field.get("description", None)
            if descr:
                descr = descr.replace("\\", "").replace("``", "'").replace("''", "'")
                _, replace, tail = descr.strip().partition("REPLACE")
                if replace:
                    key, _, subs = tail.strip().partition(" ")
                    subs = literal_eval(subs)
                    cmmn = common.get(key, None)
                    if cmmn is None:
                        warn(f"Can't substitute description text, common variable not found: {key}")
                    else:
                        descr = cmmn.get("description", "")
                        if any(subs):
                            descr = descr.replace("\\", "").replace("{#1}", subs["{#1}"])
                field["description"] = descr

        # add the final parameter
        if any(field):
            flat.append((field["name"], field))

        # the point of the OMD is to losslessly handle duplicate variable names
        return OMD(flat), meta

    @classmethod  # type: ignore[misc]
    def _load_v1(cls, f, name, **kwargs) -> "Dfn":
        """
        Temporary load routine for the v1 DFN format.
        """

        fkeys = {}
        refs = kwargs.pop("refs", {})
        flat, meta = Dfn._load_v1_flat(f, **kwargs)

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
                field = {k: _try_parse_bool(v) for k, v in field.items()}

                _name = field.pop("name")
                _type = field.pop("type", None)
                shape = field.pop("shape", None)
                shape = None if shape == "" else shape
                block = field.pop("block", None)
                default = field.pop("default", None)
                default = _try_literal_eval(default) if _type != "string" else default
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
                        for v in flat.values(multi=True)
                        if v["name"] in item_names and v.get("in_record", False)
                    ]
                    n_item_names = len(item_names)
                    if n_item_names < 1:
                        raise ValueError(f"Missing list definition: {_type}")

                    # explicit record
                    if n_item_names == 1 and (
                        item_types[0].startswith("record") or item_types[0].startswith("keystring")
                    ):
                        return _convert_field(next(iter(flat.getlist(item_names[0]))))

                    # implicit simple record (no children)
                    if all(t in _SCALAR_TYPES for t in item_types):
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
                    fields = {
                        v["name"]: _convert_field(v)
                        for v in flat.values(multi=True)
                        if v["name"] in item_names and v.get("in_record", False)
                    }
                    first = next(iter(fields.values()))
                    single = len(fields) == 1
                    item_type = "keystring" if single and "keystring" in first["type"] else "record"
                    return Field(
                        name=first["name"] if single else _name,
                        type=item_type,
                        block=block,
                        fields=first["fields"] if single else fields,
                        description=description.replace("is the list of", f"is the {item_type} of"),
                        reader=reader,
                        **field,
                    )

                def _choices() -> Fields:
                    """Load keystring (union) choices."""
                    names = _type.split()[1:]
                    return {
                        v["name"]: _convert_field(v)
                        for v in flat.values(multi=True)
                        if v["name"] in names and v.get("in_record", False)
                    }

                def _fields() -> Fields:
                    """Load record fields."""
                    names = _type.split()[1:]
                    fields = {}
                    for name in names:
                        v = flat.get(name, None)
                        if not v or not v.get("in_record", False) or v["type"].startswith("record"):
                            continue
                        fields[name] = v
                    return fields

                var_ = Field(
                    name=_name,
                    shape=shape,
                    block=block,
                    description=description,
                    default=default,
                    reader=reader,
                    **field,
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
                elif shape is not None and _type not in _SCALAR_TYPES:
                    raise TypeError(f"Unsupported array type: {_type}")

                else:
                    var_["type"] = _type

                # if var is a foreign key, return subpkg var instead
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
                        ref=ref,
                        reader=reader,
                        **field,
                    )

                return var_

            return dict(sorted(_load(var).items(), key=_field_attr_sort_key))

        # load top-level fields. any nested
        # fields will be loaded recursively
        fields = {
            field["name"]: _convert_field(field)
            for field in flat.values(multi=True)
            if not field.get("in_record", False)
        }

        # group variables by block
        blocks = {
            block_name: {v["name"]: v for v in block}
            for block_name, block in groupby(fields.values(), lambda v: v["block"])
        }

        # mark transient blocks
        transient_index_vars = flat.getlist("iper")
        for transient_index in transient_index_vars:
            transient_block = transient_index["block"]
            blocks[transient_block]["transient_block"] = True

        # remove unneeded variable attributes
        def remove_attrs(path, key, value):
            if key in ["in_record", "tagged", "preserve_case"]:
                return False
            return True

        blocks = remap(blocks, visit=remove_attrs)

        def _advanced() -> bool | None:
            return any("package-type advanced" in m for m in meta)

        def _multi() -> bool:
            return any("multi-package" in m for m in meta)

        def _sln() -> Sln | None:
            sln = next(
                iter(m for m in meta if isinstance(m, str) and m.startswith("solution_package")),
                None,
            )
            if sln:
                abbr, pattern = sln.split()[1:]
                return Sln(abbr=abbr, pattern=pattern)
            return None

        def _sub() -> Ref | None:
            def _parent():
                line = next(
                    iter(m for m in meta if isinstance(m, str) and m.startswith("parent")),
                    None,
                )
                if not line:
                    return None
                split = line.split()
                return split[1]

            def _rest():
                line = next(
                    iter(m for m in meta if isinstance(m, str) and m.startswith("subpac")),
                    None,
                )
                if not line:
                    return None
                _, key, abbr, param, val = line.split()
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

            parent = _parent()
            rest = _rest()
            if parent and rest:
                return Ref(parent=parent, **rest)
            return None

        def _subcomponents() -> list[str] | None:
            """
            Extract allowed child component types from mf6 subpackage metadata.

            This parses '# mf6 subpackage <abbr>' declarations to determine
            schema-level composition constraints (which component types can be
            children). Distinct from fkeys, which are field-level foreign keys
            populated from '# flopy subpackage ...' declarations.
            """
            result = []
            for m in meta:
                if m.startswith("mf6-subpackage "):
                    abbr = m.removeprefix("mf6-subpackage ").strip().upper()
                    result.append(abbr)
            return result if result else None

        return cls(  # type: ignore[misc]
            name=name,
            fkeys=fkeys,
            advanced=_advanced(),
            multi=_multi(),
            sln=_sln(),
            ref=_sub(),
            subcomponents=_subcomponents(),
            **blocks,
        )

    @classmethod  # type: ignore[misc]
    def _load_v2(cls, f, name, fmt: str = "toml") -> "Dfn":
        if fmt == "toml":
            data = tomli.load(f)
        elif fmt == "json":
            import json

            data = json.load(f)
        elif fmt == "yaml":
            import yaml

            data = yaml.safe_load(f)
        else:
            raise ValueError(f"Unsupported format: {fmt!r}")
        if name and name != data.get("name", None):
            raise ValueError(f"Name mismatch, expected {name}")
        for block in (data.get("blocks") or {}).values():
            for field_name, field in block.items():
                field.setdefault("name", field_name)
        return cls(**data)

    @classmethod  # type: ignore[misc]
    def load(
        cls,
        f,
        name: str | None = None,
        version: FormatVersion | DfnFormat = "dfn",
        **kwargs,
    ) -> "Dfn":
        """
        Load a component definition from a definition file.
        """

        if version in ["dfn", 1]:
            return cls._load_v1(f, name, **kwargs)
        elif version in ["toml", 2]:
            return cls._load_v2(f, name, fmt="toml")
        elif version == "yaml":
            return cls._load_v2(f, name, fmt="yaml")
        elif version == "json":
            return cls._load_v2(f, name, fmt="json")
        else:
            raise ValueError(
                f"Unsupported version {version!r}, expected one of: 'dfn', 'toml', 'yaml', 'json'"
            )

    @staticmethod  # type: ignore[misc]
    def load_all(dfndir: PathLike, version: FormatVersion | None = None) -> Dfns:
        """Load all component definitions from the given directory."""

        if version:
            warn("load_all() argument 'version' is deprecated and ignored")

        dfns: Dfns = {}
        dfndir = Path(dfndir)
        _EXCLUDE = {"common", "flopy"}

        dfn_paths: list[Path] = [p for p in dfndir.glob("*.dfn") if p.stem not in _EXCLUDE]
        toml_paths: list[Path] = [p for p in dfndir.glob("*.toml") if p.stem not in _EXCLUDE]
        yaml_paths: list[Path] = [
            p for ext in ("*.yaml", "*.yml") for p in dfndir.glob(ext) if p.stem not in _EXCLUDE
        ]
        json_paths: list[Path] = [p for p in dfndir.glob("*.json") if p.stem not in _EXCLUDE]

        groups = [g for g in [dfn_paths, toml_paths, yaml_paths, json_paths] if g]
        if len(groups) > 1:
            raise ValueError("Directory contains definition files in multiple formats")
        if not groups:
            raise ValueError("Directory contains no definition files")

        if dfn_paths:
            # load common fields
            common_path: Path | None = dfndir / "common.dfn"
            if not common_path.is_file():
                common = None
            else:
                with common_path.open() as f:
                    common, _ = Dfn._load_v1_flat(f)

            # load subpackages
            refs = {}
            for path in dfn_paths:
                with path.open() as f:
                    dfn = Dfn.load(f, name=path.stem, common=common)
                    ref = dfn.get("ref", None)
                    if ref:
                        refs[ref["key"]] = ref

            # load definitions
            for path in dfn_paths:
                with path.open() as f:
                    dfn = Dfn.load(f, name=path.stem, common=common, refs=refs)
                    dfns[path.stem] = dfn
        elif toml_paths:
            for path in toml_paths:
                with path.open(mode="rb") as f:
                    dfn = Dfn.load(f, name=path.stem, version="toml")
                    dfns[path.stem] = dfn
        elif yaml_paths:
            for path in yaml_paths:
                with path.open() as f:
                    dfn = Dfn.load(f, name=path.stem, version="yaml")
                    dfns[path.stem] = dfn
        elif json_paths:
            for path in json_paths:
                with path.open() as f:
                    dfn = Dfn.load(f, name=path.stem, version="json")
                    dfns[path.stem] = dfn

        return dfns


def _load_common(f: Any) -> tuple[OMD, list[str]]:
    common, _ = parser.parse_dfn(f)
    return common


load_common = _load_common  # public alias


def load(f: Any, format: str = "dfn", **kwargs: Any) -> Dfn:
    """Load a v1 definition file."""

    if format != "dfn":
        raise ValueError(f"Unsupported format: {format!r}. Expected 'dfn'.")

    name = kwargs.pop("name")
    fields, meta = parser.parse_dfn(f, **kwargs)
    parent = parser.try_get_parent(meta)
    blocks = {
        block_name: {field["name"]: Field(field) for field in block}  # type: ignore[misc]
        for block_name, block in groupby(fields.values(multi=True), lambda fd: fd["block"])
    }
    multi = parser.is_multi_package(meta)
    advanced = parser.is_advanced_package(meta)
    subcomponents = parser.get_subpackages(meta) or None

    return Dfn(
        schema_version="1",
        name=name,
        parent=parent,
        blocks=blocks,
        multi=multi,
        advanced=advanced,
        subcomponents=subcomponents,
    )


EXCLUDE_DFNS = ["common.dfn", "flopy.dfn"]


def load_all(path: str | PathLike) -> Dfns:
    """Load definition files in a directory."""
    path = Path(path).expanduser().resolve()
    dfn_paths = {p.stem: p for p in path.glob("*.dfn") if p.name not in EXCLUDE_DFNS}
    dfns: Dfns = {}
    if dfn_paths:
        with (path / "common.dfn").open() as f:
            common = _load_common(f)
        for dfn_name, dfn_path in dfn_paths.items():
            with dfn_path.open() as f:
                dfns[dfn_name] = load(f, name=dfn_name, common=common, format="dfn")
    return dfns


def get_fields(dfn: Dfn) -> OMD:
    """Combined map of fields from all blocks (flat, top-level only)."""
    items = []
    for block in (dfn["blocks"] or {}).values():
        for f in block.values():
            items.append((f["name"], f))
    return OMD(items)


def _has_grid_dependent_shapes(dfn: Dfn) -> bool:
    """Return True if any field uses a semicolon grid-type-dependent shape."""
    blocks = dfn.get("blocks", {})
    if not blocks:
        return False
    for block in blocks.values():
        for field in block.values():
            if ";" in str(field.get("shape") or ""):
                return True
    return False


def infer_parent(dfn: Dfn) -> str | None:
    """Infer a component's parent using naming conventions."""
    if dfn["name"] == "sim-nam":
        return None
    if dfn["name"].endswith("-nam"):
        return "sim-nam"
    if dfn["name"].startswith(("exg-", "sln-")):
        return "sim-nam"
    if dfn["name"].startswith("utl-"):
        # Grid-dependent shapes (semicolon notation) mean the utility must be
        # model-attached, not simulation-level.
        if _has_grid_dependent_shapes(dfn):
            return "package"
        return "sim-nam"
    if "-" in dfn["name"]:
        mdl = dfn["name"].split("-")[0]
        return f"{mdl}-nam"
    return None


def resolve_parent(dfn: Dfn) -> Dfn:
    """Infer and set a component's parent using naming conventions."""
    if dfn["parent"] is None:
        dfn["parent"] = infer_parent(dfn)
    return dfn


def resolve_parents(dfns: Dfns) -> Dfns:
    """Infer and set component parents using naming conventions."""
    return {name: resolve_parent(dfn) for name, dfn in dfns.items()}
