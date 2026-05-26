import shutil
import tempfile
from os import PathLike
from pathlib import Path

from modflow_devtools.dfn.schema import (
    _SCALAR_TYPES,
    Dfn,
    Dfns,
    Field,
    Fields,
    FieldType,
    FormatVersion,
    Reader,
    Ref,
    Sln,
    get_fields,
)
from modflow_devtools.download import download_and_unzip

SCALAR_TYPES = _SCALAR_TYPES

__all__ = [
    "SCALAR_TYPES",
    "_SCALAR_TYPES",
    "Dfn",
    "Dfns",
    "Field",
    "FieldType",
    "Fields",
    "FormatVersion",
    "Reader",
    "Ref",
    "Sln",
    "fetch_dfns",
    "get_dfns",
    "get_fields",
]


def fetch_dfns(owner: str, repo: str, ref: str, outdir: str | PathLike, verbose: bool = False):
    """Fetch definition files from the MODFLOW 6 repository."""
    url = f"https://github.com/{owner}/{repo}/archive/{ref}.zip"
    if verbose:
        print(f"Downloading MODFLOW 6 repository from {url}")
    with tempfile.TemporaryDirectory() as tmp:
        dl_path = download_and_unzip(url, Path(tmp), verbose=verbose)
        contents = list(dl_path.glob("modflow6-*"))
        proj_path = next(iter(contents), None)
        if not proj_path:
            raise ValueError(f"Missing proj dir in {dl_path}, found {contents}")
        if verbose:
            print("Copying dfns from download dir to output dir")
        shutil.copytree(proj_path / "doc" / "mf6io" / "mf6ivar" / "dfn", outdir, dirs_exist_ok=True)


get_dfns = fetch_dfns  # backwards-compatible alias
