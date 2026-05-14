"""Convert MODFLOW 6 DFN files to TOML (v1, v1.1, or v2 schema)."""

import argparse
import sys
import textwrap
from os import PathLike
from pathlib import Path

import tomli_w as tomli
from boltons.iterutils import remap

from modflow_devtools.dfn.mapper import (
    _dfn_to_plain_dict,
    _load_common,
    _toml_safe,
    is_valid,
    load,
    load_flat,
    to_flat,
    to_tree,
)
from modflow_devtools.dfn.v1_1 import Dfn
from modflow_devtools.misc import drop_none_or_empty

# mypy: ignore-errors


def convert(inpath: PathLike, outdir: PathLike, schema: str = "1") -> None:
    """Convert DFN file(s) to TOML.

    Parameters
    ----------
    inpath : PathLike
        Input file or directory.
    outdir : PathLike
        Output directory.
    schema : str
        Target schema version: "1", "1.1", or "2".
    """
    inpath = Path(inpath).expanduser().absolute()
    outdir = Path(outdir).expanduser().absolute()
    outdir.mkdir(exist_ok=True, parents=True)

    if schema not in ("1", "1.1", "2"):
        raise ValueError(f"Unsupported schema version: {schema!r}. Expected '1', '1.1', or '2'.")

    if inpath.is_file():
        if inpath.name == "common.dfn":
            raise ValueError("Cannot convert common.dfn as a standalone file")

        common = {}
        if (common_path := inpath.parent / "common.dfn").exists():
            with common_path.open() as f:
                common = _load_common(f)

        with inpath.open() as f:
            dfn = load(f, name=inpath.stem, common=common, format="dfn")

        _convert(dfn, outdir / f"{inpath.stem}.toml", schema=schema)
    else:
        if schema == "1":
            # v1: iterate files directly (no tree building)
            dfns = load_flat(inpath)
            for dfn_name, dfn in dfns.items():
                _convert(dfn, outdir / f"{dfn_name}.toml", schema=schema)
        else:
            # v1.1 / v2: map all, build tree, flatten, convert
            if schema == "1.1":
                from modflow_devtools.dfn.mapper import map as map_v1_1

                dfns = {name: map_v1_1(dfn, "1.1") for name, dfn in load_flat(inpath).items()}
            else:
                from modflow_devtools.dfns.mapper import map as map_v2

                dfns = {name: map_v2(dfn, "2") for name, dfn in load_flat(inpath).items()}

            if schema == "1.1":
                tree = to_tree(dfns)
                flat = to_flat(tree)
                for dfn_name, dfn in flat.items():
                    _convert(dfn, outdir / f"{dfn_name}.toml", schema=schema)
            else:
                for dfn_name, component in dfns.items():
                    _convert(component, outdir / f"{dfn_name}.toml", schema=schema)


def _convert(dfn_or_component: object, outpath: Path, schema: str = "1") -> None:
    with Path.open(outpath, "wb") as f:
        if schema == "2":
            # Component is a Pydantic model
            d = dfn_or_component.model_dump(exclude_none=True)  # type: ignore[union-attr]
            tomli.dump(_toml_safe(remap(d, visit=drop_none_or_empty)), f)
        else:
            # Dfn dataclass (v1 or v1.1)
            dfn_dict = _dfn_to_plain_dict(dfn_or_component)  # type: ignore[arg-type]
            if blocks := dfn_dict.pop("blocks", None):
                for block_name, block_fields in blocks.items():
                    dfn_dict.setdefault(block_name, {})
                    for field_name, field_data in block_fields.items():
                        dfn_dict[block_name][field_name] = field_data
            tomli.dump(_toml_safe(remap(dfn_dict, visit=drop_none_or_empty)), f)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert MODFLOW 6 DFN files to TOML.",
        epilog=textwrap.dedent(
            """\
Convert MODFLOW 6 definition files (.dfn format) to TOML files.

Schema versions:
  1   — v1 TOML: all original DFN attributes preserved, no schema change.
  1.1 — v1.1 TOML: v1-specific attributes stripped; shared base fields only.
  2   — v2 TOML: fully typed v2 Component schema (Pydantic model serialization).
"""
        ),
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
        "--schema",
        "-s",
        default="1",
        choices=["1", "1.1", "2"],
        help="Target schema version (default: 1).",
    )
    parser.add_argument(
        "--validate",
        "-v",
        action="store_true",
        help="Validate DFN files without converting them.",
    )
    args = parser.parse_args()

    if args.validate:
        if not is_valid(args.indir):
            sys.exit(1)
    else:
        convert(args.indir, args.outdir, schema=args.schema)
