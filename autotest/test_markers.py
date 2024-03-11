from os import environ
from platform import python_version, system
from shutil import which

from packaging.version import Version
import pytest

from modflow_devtools.markers import (
    requires_exe,
    require_exe,
    requires_program,
    require_program,
    requires_pkg,
    require_package,
    requires_platform,
    require_platform,
    excludes_platform,
    requires_python,
    require_python,
)

exe = "pytest"
pkg = exe


@requires_exe(exe)
def test_require_exe():
    assert which(exe)
    require_exe(exe)
    require_program(exe)
    requires_program(exe)


exes = [exe, "python"]


@require_exe(*exes)
def test_require_exe_multiple():
    assert all(which(exe) for exe in exes)


@requires_pkg(pkg)
def test_requires_pkg():
    import numpy

    assert numpy is not None
    require_package(pkg)


@requires_pkg(pkg, "pluggy")
def test_requires_pkg_multiple():
    import pluggy
    import pytest

    assert pluggy is not None and pytest is not None


@requires_platform("Windows")
def test_requires_platform():
    assert system() == "Windows"
    require_platform("Windows")


@excludes_platform("Darwin", ci_only=True)
def test_requires_platform_ci_only():
    if "CI" in environ:
        assert system() != "Darwin"


py_ver = python_version()


@pytest.mark.parametrize("version", ["3.12", "3.11"])
def test_requires_python(version):
    if Version(py_ver) >= Version(version):
        assert requires_python(version)
        assert require_python(version)
