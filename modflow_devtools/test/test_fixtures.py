import inspect
import platform
from pathlib import Path

import pytest

system = platform.system()
proj_root = Path(__file__).parent.parent.parent.parent


# test temporary directory fixtures


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


# test fixtures dynamically generated from examples and test models


def test_example_scenario(example_scenario):
    assert isinstance(example_scenario, tuple)
    name, namefiles = example_scenario
    assert isinstance(name, str)
    assert isinstance(namefiles, list)
    assert all(namefile.is_file() for namefile in namefiles)


def test_test_model_mf6(test_model_mf6):
    assert isinstance(test_model_mf6, Path)
    assert (test_model_mf6 / "mfsim.nam").is_file()


def test_test_model_mf5to6(test_model_mf5to6):
    assert isinstance(test_model_mf5to6, Path)
    assert len(list(test_model_mf5to6.glob("*.nam"))) >= 1


def test_large_test_model(large_test_model):
    assert isinstance(large_test_model, Path)
    assert (large_test_model / "mfsim.nam").is_file()
