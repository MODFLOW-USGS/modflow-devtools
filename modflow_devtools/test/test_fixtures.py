import inspect
import platform
from os import environ
from pathlib import Path
from shutil import which

import pytest
from modflow_devtools.misc import (
    excludes_platform,
    requires_exe,
    requires_pkg,
    requires_platform,
)

system = platform.system()
proj_root = Path(__file__).parent.parent.parent.parent


# temporary directory fixtures


def test_tmpdirs(function_tmpdir, module_tmpdir):
    # function-scoped temporary directory
    assert isinstance(function_tmpdir, Path)
    assert function_tmpdir.is_dir()
    assert inspect.currentframe().f_code.co_name in function_tmpdir.stem

    # module-scoped temp dir (accessible to other tests in the script)
    assert module_tmpdir.is_dir()
    assert "test" in module_tmpdir.stem


def test_function_scoped_tmpdir(function_tmpdir):
    assert isinstance(function_tmpdir, Path)
    assert function_tmpdir.is_dir()
    assert inspect.currentframe().f_code.co_name in function_tmpdir.stem


@pytest.mark.parametrize("name", ["noslash", "forward/slash", "back\\slash"])
def test_function_scoped_tmpdir_slash_in_name(function_tmpdir, name):
    assert isinstance(function_tmpdir, Path)
    assert function_tmpdir.is_dir()

    # node name might have slashes if test function is parametrized
    # (e.g., test_function_scoped_tmpdir_slash_in_name[a/slash])
    replaced1 = name.replace("/", "_").replace("\\", "_").replace(":", "_")
    replaced2 = name.replace("/", "_").replace("\\", "__").replace(":", "_")
    assert (
        f"{inspect.currentframe().f_code.co_name}[{replaced1}]"
        in function_tmpdir.stem
        or f"{inspect.currentframe().f_code.co_name}[{replaced2}]"
        in function_tmpdir.stem
    )


class TestClassScopedTmpdir:
    filename = "hello.txt"

    @pytest.fixture(autouse=True)
    def setup(self, class_tmpdir):
        with open(class_tmpdir / self.filename, "w") as file:
            file.write("hello, class-scoped tmpdir")

    def test_class_scoped_tmpdir(self, class_tmpdir):
        assert isinstance(class_tmpdir, Path)
        assert class_tmpdir.is_dir()
        assert self.__class__.__name__ in class_tmpdir.stem
        assert Path(class_tmpdir / self.filename).is_file()


def test_module_scoped_tmpdir(module_tmpdir):
    assert isinstance(module_tmpdir, Path)
    assert module_tmpdir.is_dir()
    assert Path(inspect.getmodulename(__file__)).stem in module_tmpdir.name


def test_session_scoped_tmpdir(session_tmpdir):
    assert isinstance(session_tmpdir, Path)
    assert session_tmpdir.is_dir()


# test fixtures to require/exclude executables & platforms


@requires_exe("mf6")
def test_mf6():
    assert which("mf6")


exes = ["mfusg", "mfnwt"]


@requires_exe(*exes)
def test_mfusg_and_mfnwt():
    assert all(which(exe) for exe in exes)


@requires_pkg("numpy")
def test_numpy():
    import numpy

    assert numpy is not None


@requires_pkg("numpy", "matplotlib")
def test_numpy_and_matplotlib():
    import matplotlib
    import numpy

    assert numpy is not None and matplotlib is not None


@requires_platform("Windows")
def test_needs_windows():
    assert system == "Windows"


@excludes_platform("Darwin", ci_only=True)
def test_breaks_osx_ci():
    if "CI" in environ:
        assert system != "Darwin"
