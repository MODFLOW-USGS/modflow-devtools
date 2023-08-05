"""
MODFLOW 6, Python3, and build servers may all refer to operating
systems by different names. This module contains conversion utilities.
"""


from enum import Enum
from platform import system

_system = system()


def get_modflow_ostag() -> str:
    if _system == "Windows":
        return "win64"
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
