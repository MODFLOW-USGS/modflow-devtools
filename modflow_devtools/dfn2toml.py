"""Convert DFNs to TOML (v1.1 schema). Compatibility shim for consumers of the old API."""

from os import PathLike
from pathlib import Path

import tomli_w
from boltons.iterutils import remap

from modflow_devtools.dfn import Dfn
from modflow_devtools.misc import drop_none_or_empty


def _strip_field_name(data):
    """Recursively strip redundant 'name' key from field dicts (name is encoded in the table
    key)."""
    if isinstance(data, dict):
        result = {k: _strip_field_name(v) for k, v in data.items()}
        if "name" in result and "type" in result:
            del result["name"]
        return result
    if isinstance(data, list):
        return [_strip_field_name(v) for v in data]
    return data


def convert(indir: str | PathLike, outdir: str | PathLike) -> None:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for dfn in Dfn.load_all(Path(indir), schema_version="2.0.0.dev0").values():  # type: ignore
        with (outdir / f"{dfn['name']}.toml").open("wb") as f:
            data = remap(dfn, visit=drop_none_or_empty)
            tomli_w.dump(_strip_field_name(data), f)
