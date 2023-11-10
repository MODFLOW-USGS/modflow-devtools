from platform import system

import pytest

from modflow_devtools.ostags import (
    OSTag,
    get_binary_suffixes,
    get_github_ostag,
    get_modflow_ostag,
)

_system = system()


def test_get_modflow_ostag():
    t = get_modflow_ostag()
    if _system == "Windows":
        assert t == "win64"
    elif _system == "Linux":
        assert t == "linux"
    elif _system == "Darwin":
        assert t == "mac"
    else:
        pytest.skip(reason="Unsupported platform")


def test_get_github_ostag():
    t = get_github_ostag()
    if _system in ("Windows", "Linux"):
        assert t == _system
    elif _system == "Darwin":
        assert t == "macOS"
    else:
        pytest.skip(reason="Unsupported platform")


@pytest.mark.parametrize(
    "cvt,tag,exp",
    [
        ("py2mf", "Windows", "win64"),
        ("mf2py", "win64", "Windows"),
        ("py2mf", "Darwin", "mac"),
        ("mf2py", "mac", "Darwin"),
        ("py2mf", "Linux", "linux"),
        ("mf2py", "linux", "Linux"),
        ("gh2mf", "Windows", "win64"),
        ("mf2gh", "win64", "Windows"),
        ("gh2mf", "macOS", "mac"),
        ("mf2gh", "mac", "macOS"),
        ("gh2mf", "Linux", "linux"),
        ("mf2gh", "linux", "Linux"),
        ("py2gh", "Windows", "Windows"),
        ("gh2py", "Windows", "Windows"),
        ("py2gh", "Darwin", "macOS"),
        ("gh2py", "macOS", "Darwin"),
        ("py2gh", "Linux", "Linux"),
        ("gh2py", "Linux", "Linux"),
    ],
)
def test_ostag_convert(cvt, tag, exp):
    assert OSTag.convert(tag, cvt) == exp


def test_get_binary_suffixes():
    exe, lib = get_binary_suffixes()
    if _system == "Windows":
        assert exe == ".exe"
        assert lib == ".dll"
    elif _system == "Linux":
        assert exe == ""
        assert lib == ".so"
    elif _system == "Darwin":
        assert exe == ""
        assert lib == ".dylib"


@pytest.mark.parametrize(
    "tag,exe,lib",
    [
        ("win64", ".exe", ".dll"),
        ("win32", ".exe", ".dll"),
        ("Windows", ".exe", ".dll"),
        ("linux", "", ".so"),
        ("Linux", "", ".so"),
        ("mac", "", ".dylib"),
        ("macOS", "", ".dylib"),
        ("Darwin", "", ".dylib"),
    ],
)
def test_get_binary_suffixes_given_tag(tag, exe, lib):
    from modflow_devtools.misc import get_suffixes

    assert get_binary_suffixes(tag) == (exe, lib)
    if tag in ("win64", "win32", "linux", "mac"):
        assert get_suffixes(tag) == (exe, lib)
