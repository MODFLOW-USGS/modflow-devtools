"""Convert MODFLOW 6 DFN files to TOML."""

import argparse
from os import PathLike
from pathlib import Path
from typing import Any

import tomli_w as tomli
from pydantic import BaseModel

from modflow_devtools.dfn import schema as v1
from modflow_devtools.dfn.mapper import map as map_v1_1
from modflow_devtools.dfns.mapper import map as map_v2


def _toml_safe(obj: Any) -> Any:
    """
    Recursively coerce non-TOML-native types to containers
    and primitives suitable for TOML serialization.
    """

    if isinstance(obj, BaseModel):
        return obj.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude_defaults=True,
        )
    if isinstance(obj, dict):
        return {k: _toml_safe(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_toml_safe(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)  # Version → str, etc.


# mypy: ignore-errors


def migrate(inpath: str | PathLike, outdir: str | PathLike, schema_version: str = "2") -> None:
    """Migrate DFN files' schema version and convert to TOML.

    Parameters
    ----------
    inpath : str or PathLike
        Input file or directory.
    outdir : str or PathLike
        Output directory.
    schema_version : str, optional
        Target schema version: "1", "1.1", or "2". Default "2".
    """
    inpath = Path(inpath).expanduser().absolute()
    outdir = Path(outdir).expanduser().absolute()
    outdir.mkdir(exist_ok=True, parents=True)

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
            pass  # nothing to do
        elif schema_version == "1.1":
            dfn = map_v1_1(dfn)
        elif schema_version == "2":
            dfn = map_v2(dfn)
        else:
            raise ValueError(
                f"Got schema version {schema_version}, supported versions are: 1, 1.1, 2"
            )

        dfn_path = outdir / f"{inpath.stem}.toml"
        with Path.open(dfn_path, "wb") as f:
            tomli.dump(_toml_safe(dfn), f)
    else:
        dfns = v1.load_all(inpath)

        if schema_version == "1":
            pass  # nothing to do
        elif schema_version == "1.1":
            dfns = {name: map_v1_1(dfn, "1.1") for name, dfn in dfns.items()}
            dfns = v1.to_flat(v1.to_tree(dfns))
        elif schema_version == "2":
            dfns = {name: map_v2(dfn, "2") for name, dfn in dfns.items()}
        else:
            raise ValueError(
                f"Got schema version {schema_version}, supported versions are: 1, 1.1, 2"
            )

        for dfn_name, dfn in dfns.items():
            dfn_path = outdir / f"{dfn_name}.toml"
            with Path.open(dfn_path, "wb") as f:
                tomli.dump(_toml_safe(dfn), f)


convert = migrate  # backwards-compatible alias


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrate DFN files' schema version and convert to TOML.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--indir",
        "-i",
        type=str,
        help="Input file or directory containing DFN files.",
    )
    parser.add_argument(
        "--outdir",
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
    args = parser.parse_args()
    migrate(indir=args.indir, outdir=args.outdir, schema_version=args.schema_version)
