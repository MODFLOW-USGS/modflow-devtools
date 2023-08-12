"""
MODFLOW 6, Python3, and GitHub Actions refer to operating
systems differently. This module contains conversion utilities.
"""


import sys
from enum import Enum
from platform import system
from typing import Tuple

_system = system()


def get_modflow_ostag() -> str:
    if _system == "Windows":
        return "win" + ("64" if sys.maxsize > 2**32 else "32")
    elif _system == "Linux":
        return "linux"
    elif _system == "Darwin":
        return "mac"
    else:
        raise NotImplementedError(f"Unsupported system: {_system}")


def get_github_ostag() -> str:
    if _system in ("Windows", "Linux"):
        return _system
    elif _system == "Darwin":
        return "macOS"
    else:
        raise NotImplementedError(f"Unsupported system: {_system}")


def get_binary_suffixes(ostag: str = None) -> Tuple[str, str]:
    """
    Returns executable and library suffixes for the given OS tag, if provided,
    otherwise for the current operating system.

    Parameters
    ----------
    ostag : str, optional
        The OS tag. May be provided in modflow, python, or github format.

    Returns
    -------
    Tuple[str, str]
        The executable and library suffixes, respectively.
    """

    if ostag is None:
        ostag = get_modflow_ostag()

    def _suffixes(tag):
        if tag in ["win32", "win64"]:
            return ".exe", ".dll"
        elif tag == "linux":
            return "", ".so"
        elif tag == "mac" or tag == "darwin":
            return "", ".dylib"
        else:
            raise KeyError(f"unrecognized OS tag: {tag!r}")

    try:
        return _suffixes(ostag.lower())
    except:
        try:
            return _suffixes(python_to_modflow_ostag(ostag))
        except:
            return _suffixes(github_to_modflow_ostag(ostag))


def python_to_modflow_ostag(tag: str) -> str:
    """
    Convert a platform.system() string to an ostag as expected
    by MODFLOW 6.

    Parameters
    ----------
    platform_system : str
        The platform.system() string.

    Returns
    -------
    str
    """

    if tag == "Windows":
        return "win64"
    elif tag == "Linux":
        return "linux"
    elif tag == "Darwin":
        return "mac"
    else:
        raise ValueError(f"Invalid or unsupported tag: {tag}")


def modflow_to_python_ostag(tag: str) -> str:
    """
    Convert a MODFLOW os tag to a platform.system() string.

    Parameters
    ----------
    tag : str
        The MODFLOW os tag.

    Returns
    -------
    str
    """

    if tag == "win64":
        return "Windows"
    elif tag == "linux":
        return "Linux"
    elif tag == "mac":
        return "Darwin"
    else:
        raise ValueError(f"Invalid or unsupported tag: {tag}")


def modflow_to_github_ostag(tag: str) -> str:
    if tag == "win64":
        return "Windows"
    elif tag == "linux":
        return "Linux"
    elif tag == "mac":
        return "macOS"
    else:
        raise ValueError(f"Invalid modflow os tag: {tag}")


def github_to_modflow_ostag(tag: str) -> str:
    if tag == "Windows":
        return "win64"
    elif tag == "Linux":
        return "linux"
    elif tag == "macOS":
        return "mac"
    else:
        raise ValueError(f"Invalid github os tag: {tag}")


def python_to_github_ostag(tag: str) -> str:
    return modflow_to_github_ostag(python_to_modflow_ostag(tag))


def github_to_python_ostag(tag: str) -> str:
    return modflow_to_python_ostag(github_to_modflow_ostag(tag))


def get_ostag(kind: str = "modflow") -> str:
    if kind == "modflow":
        return get_modflow_ostag()
    elif kind == "github":
        return get_github_ostag()
    else:
        raise ValueError(f"Invalid kind: {kind}")


class OSTagCvt(Enum):
    py2mf = "py2mf"
    mf2py = "mf2py"
    gh2mf = "gh2mf"
    mf2gh = "mf2gh"
    py2gh = "py2gh"
    gh2py = "gh2py"


class OSTag:
    @staticmethod
    def convert(tag: str, cvt: str) -> str:
        cvt = OSTagCvt(cvt)
        if cvt == OSTagCvt.py2mf:
            return python_to_modflow_ostag(tag)
        elif cvt == OSTagCvt.mf2py:
            return modflow_to_python_ostag(tag)
        elif cvt == OSTagCvt.gh2mf:
            return github_to_modflow_ostag(tag)
        elif cvt == OSTagCvt.mf2gh:
            return modflow_to_github_ostag(tag)
        elif cvt == OSTagCvt.py2gh:
            return python_to_github_ostag(tag)
        elif cvt == OSTagCvt.gh2py:
            return github_to_python_ostag(tag)
        else:
            raise ValueError(f"Unsupported mapping: {cvt}")
