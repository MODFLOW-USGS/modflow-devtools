import sys
from os import PathLike
from pathlib import Path
from shutil import which
from types import SimpleNamespace
from typing import Dict, Optional
from warnings import warn

from modflow_devtools.misc import get_suffixes, run_cmd


class Executables(SimpleNamespace):
    """
    Container mapping executable names to their paths.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @staticmethod
    def get_version(
        exe="mf6", path: PathLike = None, flag: str = "-v"
    ) -> Optional[str]:
        """Get the version number of an executable."""

        pth = Executables.get_path(exe, path)
        if not pth:
            warn(
                f"Executable {exe} not found"
                + ("" if not pth else f" at path: {pth}")
            )
            return None

        out, err, ret = run_cmd(exe, flag)
        if ret == 0:
            out = "".join(out).strip()
            return out.split(":")[1].strip()
        else:
            return None

    @staticmethod
    def get_path(exe: str = "mf6", path: PathLike = None) -> Optional[Path]:
        pth = None
        found = None
        if path is not None:
            pth = Path(path)
            found = which(exe, path=str(pth))
        if found is None:
            found = which(exe)

        if found is None:
            warn(
                f"Executable {exe} not found"
                + ("" if not pth else f" at path: {pth}")
            )
            return found

        return Path(found)

    def as_dict(self) -> Dict[str, Path]:
        """
        Returns a dictionary mapping executable names to paths.
        """

        return self.__dict__.copy()


def build_default_exe_dict(bin_path: PathLike) -> Dict[str, Path]:
    p = Path(bin_path)
    d = dict()

    # paths to executables for previous versions of MODFLOW
    dl_bin = p / "downloaded"
    rb_bin = p / "rebuilt"

    # get platform-specific filename extensions
    ext, so = get_suffixes(sys.platform)

    # downloaded executables
    d["mf2005"] = Executables.get_path(f"mf2005dbl{ext}", dl_bin)
    d["mfnwt"] = Executables.get_path(f"mfnwtdbl{ext}", dl_bin)
    d["mfusg"] = Executables.get_path(f"mfusgdbl{ext}", dl_bin)
    d["mflgr"] = Executables.get_path(f"mflgrdbl{ext}", dl_bin)
    d["mf2005s"] = Executables.get_path(f"mf2005{ext}", dl_bin)
    d["mt3dms"] = Executables.get_path(f"mt3dms{ext}", dl_bin)

    # executables rebuilt from last release
    d["mf6_regression"] = Executables.get_path(f"mf6{ext}", rb_bin)

    # local development version
    d["mf6"] = p / f"mf6{ext}"
    d["libmf6"] = p / f"libmf6{so}"
    d["mf5to6"] = p / f"mf5to6{ext}"
    d["zbud6"] = p / f"zbud6{ext}"

    return d
