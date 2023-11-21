from os import environ
from platform import python_version, system
from shutil import which

from packaging.version import Version

from modflow_devtools.markers import *

exe = "pytest"


@requires_exe(exe)
def test_require_exe():
    assert which(exe)
    require_exe(exe)
    require_program(exe)


exes = [exe, "python"]


@require_exe(*exes)
def test_require_exe_multiple():
    assert all(which(exe) for exe in exes)


@requires_pkg("pytest")
def test_requires_pkg():
    import numpy

    assert numpy is not None


@requires_pkg("pytest", "pluggy")
def test_requires_pkg_multiple():
    import pluggy
    import pytest

    assert pluggy is not None and pytest is not None


@requires_platform("Windows")
def test_requires_platform():
    assert system() == "Windows"


@excludes_platform("Darwin", ci_only=True)
def test_requires_platform_ci_only():
    if "CI" in environ:
        assert system() != "Darwin"


py_ver = python_version()


@pytest.mark.parametrize("version", ["3.12", "3.11"])
def test_requires_python(version):
    if Version(py_ver) >= Version(version):
        assert requires_python(version)
