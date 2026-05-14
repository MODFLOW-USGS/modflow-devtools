"""
v1 / v1.1 schema mapping, I/O helpers, and serialization utilities.
"""

from __future__ import annotations

import dataclasses
from dataclasses import asdict
from itertools import groupby
from os import PathLike
from pathlib import Path
from typing import Any

import tomli
from packaging.version import Version

from modflow_devtools.dfn.parse import (
    is_advanced_package,
    is_multi_package,
    parse_dfn,
    parse_mf6_subpackages,
    try_parse_parent,
)
from modflow_devtools.dfn.v1_1 import Dfn, Dfns, FieldV1, FieldV1_1

# =============================================================================
# Mappers
# =============================================================================


class MapV1To1_1:
    """Map a v1 Dfn (FieldV1 blocks) to a v1.1 Dfn (FieldV1_1 blocks)."""

    @staticmethod
    def map_field(field: FieldV1) -> FieldV1_1:
        return FieldV1_1(
            name=field.name,
            type=field.type,
            block=field.block,
            default=field.default,
            longname=field.longname,
            description=field.description,
            optional=field.optional,
            developmode=field.developmode,
            shape=field.shape,
            valid=field.valid,
            netcdf=field.netcdf,
            tagged=field.tagged,
        )

    def map(self, dfn: Dfn) -> Dfn:
        blocks: dict[str, dict] = {}
        for block_name, block_fields in (dfn.blocks or {}).items():
            blocks[block_name] = {
                fname: MapV1To1_1.map_field(f)
                for fname, f in block_fields.items()
                if isinstance(f, FieldV1)
            }
        return dataclasses.replace(
            dfn,
            schema_version=Version("1.1"),
            blocks=blocks if blocks else None,
        )


def map(
    dfn: Dfn,
    schema_version: str | Version = "1.1",
) -> Dfn:
    """Map a MODFLOW 6 v1 definition to v1 or v1.1 schema."""
    version = Version(str(schema_version))
    if version == Version("1"):
        raise NotImplementedError("Mapping to schema version 1 is not implemented.")
    if version == Version("1.1"):
        if dfn.schema_version >= Version("1.1"):
            return dfn
        return MapV1To1_1().map(dfn)
    raise ValueError(f"Unsupported schema version: {schema_version!r}. Expected '1' or '1.1'.")


# =============================================================================
# I/O helpers
# =============================================================================


def load(f: Any, format: str = "dfn", **kwargs: Any) -> Dfn:
    """Load a MODFLOW 6 definition file into a Dfn."""
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

    if format == "toml":
        from modflow_devtools.dfns.schema.v2 import FieldBase

        data = tomli.load(f)
        dfn_name = data.pop("name", kwargs.pop("name", None))

        dfn_fields: dict[str, Any] = {
            "name": dfn_name,
            "schema_version": Version(str(data.pop("schema_version", "2"))),
            "parent": data.pop("parent", None),
            "advanced": data.pop("advanced", False),
            "multi": data.pop("multi", False),
            "ftype": data.pop("ftype", None),
        }
        # variant_of is a v2 Component concept; consume but don't store on Dfn
        data.pop("variant_of", None)

        if (expected_name := kwargs.pop("name", None)) is not None:
            if dfn_fields["name"] != expected_name:
                raise ValueError(f"DFN name mismatch: {expected_name} != {dfn_fields['name']}")

        parsed_blocks: dict[str, Any] = {}
        for section_name, section_data in data.items():
            if isinstance(section_data, dict):
                block_fields: dict[str, Any] = {}
                for field_name, field_data in section_data.items():
                    if isinstance(field_data, dict):
                        block_fields[field_name] = FieldBase.from_dict(field_data)
                    else:
                        block_fields[field_name] = field_data
                parsed_blocks[section_name] = block_fields

        dfn_fields["blocks"] = parsed_blocks if parsed_blocks else None
        return Dfn(**dfn_fields)

    raise ValueError(f"Unsupported format: {format!r}. Expected 'dfn' or 'toml'.")


def _load_common(f: Any) -> Any:
    common, _ = parse_dfn(f)
    return common


def load_flat(path: str | PathLike) -> Dfns:
    """
    Load a flat MODFLOW 6 specification from definition files in a directory.

    Returns a dictionary of unlinked Dfns (children not populated).
    """
    exclude = ["common", "flopy"]
    path = Path(path).expanduser().resolve()

    dfn_paths = {p.stem: p for p in path.glob("*.dfn") if p.stem not in exclude}
    toml_paths = {p.stem: p for p in path.glob("*.toml") if p.stem not in exclude}
    dfns: Dfns = {}
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


def _infer_parent(name: str) -> str | None:
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


def _resolve_parent_for_tree(
    name: str, parent: str | list[str] | None, dfns: Dfns
) -> str | None:
    """
    Resolve a parent value to a specific component name for tree placement.

    When parent is a type label or any string not present in the known component
    dict, falls back to name-based inference.
    """
    if parent is None:
        return None
    if isinstance(parent, str) and parent in dfns:
        return parent
    return _infer_parent(name)


def _apply_parent_inference(dfns: Dfns) -> Dfns:
    """Set parent on any Dfn where it is not already explicit."""
    result: Dfns = {}
    for name, dfn in dfns.items():
        if dfn.parent is None:
            inferred = _infer_parent(name)
            result[name] = dataclasses.replace(dfn, parent=inferred) if inferred else dfn
        else:
            result[name] = dfn
    return result


def to_tree(dfns: Dfns) -> Dfn:
    """
    Infer the MODFLOW 6 input component hierarchy from a flat spec.

    Returns the root component. There must be exactly one root (no parent).
    """
    dfns = _apply_parent_inference(dfns)
    first_dfn = next(iter(dfns.values()), None)

    match schema_version := str(first_dfn.schema_version if first_dfn else Version("1")):
        case "1":
            raise NotImplementedError("Tree inference from v1 schema not implemented")
        case "1.1" | "2":
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
                    node = dataclasses.replace(
                        node,
                        children={name: _build_tree(name) for name in children},
                    )
                return node

            return _build_tree(next(iter(roots.keys())))
        case _:
            raise ValueError(
                f"Unsupported schema version: {schema_version!r}. Expected '1.1' or '2'."
            )


def to_flat(dfn: Dfn) -> Dfns:
    """Flatten a MODFLOW 6 input component hierarchy to a flat spec."""

    def _flatten(d: Dfn) -> Dfns:
        result: Dfns = {d.name: dataclasses.replace(d, children=None)}
        for child in (d.children or {}).values():
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
            common: Any = {}
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
# Serialization helpers
# =============================================================================


def _dfn_to_plain_dict(dfn: Dfn) -> dict:
    """Serialize a Dfn (dataclass) to a plain Python dict."""
    from modflow_devtools.dfns.schema.v2 import FieldBase

    d: dict[str, Any] = {}
    for field_name in dfn.__dataclass_fields__:
        v = getattr(dfn, field_name)
        if v is None:
            continue
        if isinstance(v, Version):
            d[field_name] = str(v)
        else:
            d[field_name] = v

    if blocks := d.get("blocks"):
        serialized: dict[str, dict] = {}
        for block_name, block_fields in blocks.items():
            block_out: dict = {}
            for field_name, field_val in block_fields.items():
                if isinstance(field_val, FieldBase):
                    block_out[field_name] = field_val.model_dump(exclude_none=True)
                elif dataclasses.is_dataclass(field_val) and not isinstance(field_val, type):
                    block_out[field_name] = asdict(field_val)
                else:
                    block_out[field_name] = field_val
            serialized[block_name] = block_out
        d["blocks"] = serialized

    return d


def _toml_safe(obj: Any) -> Any:
    """Recursively coerce non-TOML-native types to str."""
    from modflow_devtools.dfns.schema.v2 import FieldBase

    if isinstance(obj, FieldBase):
        return _toml_safe(obj.model_dump(exclude_none=True))
    if isinstance(obj, dict):
        return {k: _toml_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_toml_safe(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)
