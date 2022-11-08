from os import environ
from platform import system
from shutil import which

from modflow_devtools.markers import (
    excludes_platform,
    requires_exe,
    requires_pkg,
    requires_platform,
)


@requires_exe("mf6")
def test_requires_exe():
    assert which("mf6")


exes = ["mfusg", "mfnwt"]


@requires_exe(*exes)
def test_requires_exe_multiple():
    assert all(which(exe) for exe in exes)


@requires_pkg("numpy")
def test_requires_pkg():
    import numpy

    assert numpy is not None


@requires_pkg("numpy", "matplotlib")
def test_requires_pkg_multiple():
    import matplotlib
    import numpy

    assert numpy is not None and matplotlib is not None


@requires_platform("Windows")
def test_requires_platform():
    assert system() == "Windows"


@excludes_platform("Darwin", ci_only=True)
def test_requires_platform_ci_only():
    if "CI" in environ:
        assert system() != "Darwin"
