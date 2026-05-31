"""Convert DFNs to TOML (v1.1 schema). Compatibility shim for consumers of the old API."""

import shutil
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


def convert(indir: str | PathLike, outdir: str | PathLike, copy: bool = True) -> None:
    """
    Convert DFN files to the 2.0.0.dev0 schema version. Deprecated.

    The ``copy`` parameter is a backwards-compatibility hack. This
    function only converts the schema if ``False``. By default, it
    just copies DFNs to ``outdir``. As of modflow-devtools 1.10.0,
    ``Dfn.load()`` does its own conversion.
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    if copy:
        shutil.copytree(indir, outdir, dirs_exist_ok=True)
    else:
        for dfn in Dfn.load_all(Path(indir), schema_version="2.0.0.dev0").values():  # type: ignore
            with (outdir / f"{dfn['name']}.toml").open("wb") as f:
                data = remap(dfn, visit=drop_none_or_empty)
                tomli_w.dump(_strip_field_name(data), f)
