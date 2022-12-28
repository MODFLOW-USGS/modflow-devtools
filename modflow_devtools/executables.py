import sys
from os import PathLike
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, Optional

from modflow_devtools.misc import get_suffixes, run_cmd


class Executables(SimpleNamespace):
    """
    Container mapping executable names to their paths.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __setitem__(self, key, item):
        self.__dict__[key] = item

    def __getitem__(self, key):
        return self.__dict__[key]

    def as_dict(self) -> Dict[str, Path]:
        """
        Returns a dictionary mapping executable names to paths.
        """

        return self.__dict__.copy()

    @staticmethod
    def get_version(path: PathLike = None, flag: str = "-v") -> Optional[str]:
        """Get an executable's version string."""

        out, err, ret = run_cmd(str(path), flag)
        if ret == 0:
            out = "".join(out).strip()
            return out.split(":")[1].strip()
        else:
            return None


def build_default_exe_dict(bin_path: PathLike) -> Dict[str, Path]:
    d_bin = Path(bin_path)
    d = dict()

    # paths to executables for previous versions of MODFLOW
    dl_bin = d_bin / "downloaded"
    rb_bin = d_bin / "rebuilt"

    # get platform-specific filename extensions
    ext, so = get_suffixes(sys.platform)

    # downloaded executables
    d["mf2005"] = dl_bin / f"mf2005dbl{ext}"
    d["mfnwt"] = dl_bin / f"mfnwtdbl{ext}"
    d["mfusg"] = dl_bin / f"mfusgdbl{ext}"
    d["mflgr"] = dl_bin / f"mflgrdbl{ext}"
    d["mf2005s"] = dl_bin / f"mf2005{ext}"
    d["mt3dms"] = dl_bin / f"mt3dms{ext}"

    # executables rebuilt from last release
    d["mf6_regression"] = rb_bin / f"mf6{ext}"

    # local development version
    d["mf6"] = d_bin / f"mf6{ext}"
    d["libmf6"] = d_bin / f"libmf6{so}"
    d["mf5to6"] = d_bin / f"mf5to6{ext}"
    d["zbud6"] = d_bin / f"zbud6{ext}"

    return d
