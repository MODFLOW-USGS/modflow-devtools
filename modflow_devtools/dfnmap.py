"""Map MODFLOW 6 DFN files to a new schema version and serialize to YAML, TOML, or JSON."""

import argparse
import json
from os import PathLike
from pathlib import Path
from typing import Any, Literal

import pyaml
import tomli_w
from pydantic import BaseModel

from modflow_devtools.dfn import schema as v1
from modflow_devtools.dfn.mapper import map as map_v1_1
from modflow_devtools.dfns.mapper import map as map_v2

Format = Literal["yaml", "toml", "json"]

_EXT: dict[str, str] = {"yaml": ".yaml", "toml": ".toml", "json": ".json"}


def _serialize_safe(obj: Any) -> Any:
    """Recursively coerce non-native types to primitives suitable for serialization."""

    if isinstance(obj, BaseModel):
        return obj.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude_defaults=True,
        )
    if isinstance(obj, dict):
        return {k: _serialize_safe(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_serialize_safe(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)  # Version → str, etc.


def _write(data: dict, path: Path, fmt: Format) -> None:
    if fmt == "toml":
        with path.open("wb") as f:
            tomli_w.dump(data, f)
    elif fmt == "json":
        with path.open("w") as f:
            json.dump(data, f, indent=2)
    elif fmt == "yaml":
        with path.open("w") as f:
            pyaml.dump(data, f)


# mypy: ignore-errors


def migrate(
    inpath: str | PathLike,
    outdir: str | PathLike,
    schema_version: str = "2",
    fmt: Format = "yaml",
) -> None:
    """Migrate DFN files' schema version and serialize to the given format.

    Parameters
    ----------
    inpath : str or PathLike
        Input file or directory.
    outdir : str or PathLike
        Output directory.
    schema_version : str, optional
        Target schema version: "1", "1.1", or "2". Default "2".
    fmt : str, optional
        Output format: "yaml", "toml", or "json". Default "yaml".
    """
    inpath = Path(inpath).expanduser().absolute()
    outdir = Path(outdir).expanduser().absolute()
    outdir.mkdir(exist_ok=True, parents=True)
    ext = _EXT[fmt]

    if inpath.is_file():
        if inpath.name == "common.dfn":
            raise ValueError("Cannot convert common.dfn as a standalone file")

        common = {}
        if (common_path := inpath.parent / "common.dfn").is_file():
            with common_path.open() as f:
                common = v1.load_common(f)

        with inpath.open() as f:
            dfn = v1.Dfn.load(f, name=inpath.stem, common=common)

        if schema_version == "1":
            pass
        elif schema_version == "1.1":
            dfn = map_v1_1(dfn)
        elif schema_version == "2":
            dfn = map_v2(dfn)
        else:
            raise ValueError(
                f"Got schema version {schema_version}, supported versions are: 1, 1.1, 2"
            )

        _write(_serialize_safe(dfn), outdir / f"{inpath.stem}{ext}", fmt)
    else:
        dfns = v1.load_all(inpath)

        if schema_version == "1":
            pass
        elif schema_version == "1.1":
            dfns = v1.to_flat(v1.to_tree(dfns))
            dfns = {name: map_v1_1(dfn) for name, dfn in dfns.items()}
        elif schema_version == "2":
            dfns = {name: map_v2(dfn) for name, dfn in dfns.items()}
        else:
            raise ValueError(
                f"Got schema version {schema_version}, supported versions are: 1, 1.1, 2"
            )

        for dfn_name, dfn in dfns.items():
            _write(_serialize_safe(dfn), outdir / f"{dfn_name}{ext}", fmt)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrate DFN files' schema version and serialize to YAML, TOML, or JSON.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        help="Input file or directory containing DFN files.",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output directory.",
    )
    parser.add_argument(
        "--schema-version",
        "-s",
        default="2",
        choices=["1", "1.1", "2"],
        help="Target schema version (default: 2).",
    )
    parser.add_argument(
        "--format",
        "-f",
        default="yaml",
        choices=["yaml", "toml", "json"],
        help="Output format (default: yaml).",
    )
    args = parser.parse_args()
    migrate(
        inpath=args.input,
        outdir=args.output,
        schema_version=args.schema_version,
        fmt=args.format,
    )
