"""Convert DFNs to TOML."""

import argparse
import sys
import textwrap
from os import PathLike
from pathlib import Path

import tomli_w as tomli
from boltons.iterutils import remap

from modflow_devtools.dfns import (
    Dfn,
    _dfn_to_plain_dict,
    _toml_safe,
    is_valid,
    load,
    load_flat,
    map,
    to_flat,
    to_tree,
)
from modflow_devtools.dfns.parse import parse_dfn
from modflow_devtools.misc import drop_none_or_empty

# mypy: ignore-errors


def convert(inpath: PathLike, outdir: PathLike, schema_version: str = "2") -> None:
    """
    Convert DFN files in `inpath` to TOML files in `outdir`.
    By default, convert the definitions to schema version 2.
    """
    inpath = Path(inpath).expanduser().absolute()
    outdir = Path(outdir).expanduser().absolute()
    outdir.mkdir(exist_ok=True, parents=True)

    if inpath.is_file():
        if inpath.name == "common.dfn":
            raise ValueError("Cannot convert common.dfn as a standalone file")

        common_path = inpath.parent / "common.dfn"
        if common_path.exists():
            with common_path.open() as f:
                common, _ = parse_dfn(f)
        else:
            common = {}

        with inpath.open() as f:
            dfn = load(f, name=inpath.stem, common=common, format="dfn")

        dfn = map(dfn, schema_version=schema_version)
        _convert(dfn, outdir / f"{inpath.stem}.toml")
    else:
        dfns = {
            name: map(dfn, schema_version=schema_version) for name, dfn in load_flat(inpath).items()
        }
        tree = to_tree(dfns)
        flat = to_flat(tree)
        for dfn_name, dfn in flat.items():
            _convert(dfn, outdir / f"{dfn_name}.toml")


def _convert(dfn: Dfn, outpath: Path) -> None:
    with Path.open(outpath, "wb") as f:
        dfn_dict = _dfn_to_plain_dict(dfn)
        if blocks := dfn_dict.pop("blocks", None):
            for block_name, block_fields in blocks.items():
                dfn_dict.setdefault(block_name, {})
                for field_name, field_data in block_fields.items():
                    dfn_dict[block_name][field_name] = field_data

        tomli.dump(_toml_safe(remap(dfn_dict, visit=drop_none_or_empty)), f)


if __name__ == "__main__":
    """
    Convert DFN files in the original format and schema version 1
    to TOML files, by default also converting to schema version 2.
    """

    parser = argparse.ArgumentParser(
        description="Convert DFN files to TOML.",
        epilog=textwrap.dedent(
            """\
Convert DFN files in the original format and schema version 1
to TOML files, by default also converting to schema version 2.
"""
        ),
    )
    parser.add_argument(
        "--indir",
        "-i",
        type=str,
        help="Directory containing DFN files, or a single DFN file.",
    )
    parser.add_argument(
        "--outdir",
        "-o",
        help="Output directory.",
    )
    parser.add_argument(
        "--schema-version",
        "-s",
        type=str,
        default="2",
        help="Schema version to convert to.",
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
        convert(args.indir, args.outdir, args.schema_version)
