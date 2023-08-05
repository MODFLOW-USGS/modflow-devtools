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
