"""Convert DFNs to TOML (v1.1 schema). Compatibility shim for consumers of the old API."""

from os import PathLike
from pathlib import Path

import tomli_w
from boltons.iterutils import remap

from modflow_devtools.dfn import Dfn


def _drop_none_or_empty(path, key, value):
    return not (value is None or value == "" or value == [] or value == {})


def convert(indir: str | PathLike, outdir: str | PathLike) -> None:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for dfn in Dfn.load_all(Path(indir)).values():  # type: ignore
        with (outdir / f"{dfn['name']}.toml").open("wb") as f:
            tomli_w.dump(remap(dfn, visit=_drop_none_or_empty), f)
