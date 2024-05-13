import inspect
import platform
from pathlib import Path

import numpy as np
import pytest
from _pytest.config import ExitCode

system = platform.system()
proj_root = Path(__file__).parents[1]
module_path = Path(inspect.getmodulename(__file__))


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
        f"{inspect.currentframe().f_code.co_name}[{replaced1}]" in function_tmpdir.stem
        or f"{inspect.currentframe().f_code.co_name}[{replaced2}]"
        in function_tmpdir.stem
    )


class TestClassScopedTmpdir:
    fname = "hello.txt"

    @pytest.fixture(autouse=True)
    def setup(self, class_tmpdir):
        with open(class_tmpdir / self.fname, "w") as file:
            file.write("hello, class-scoped tmpdir")

    def test_class_scoped_tmpdir(self, class_tmpdir):
        assert isinstance(class_tmpdir, Path)
        assert class_tmpdir.is_dir()
        assert self.__class__.__name__ in class_tmpdir.stem
        assert Path(class_tmpdir / self.fname).is_file()


def test_module_scoped_tmpdir(module_tmpdir):
    assert isinstance(module_tmpdir, Path)
    assert module_tmpdir.is_dir()
    assert module_path.stem in module_tmpdir.name


def test_session_scoped_tmpdir(session_tmpdir):
    assert isinstance(session_tmpdir, Path)
    assert session_tmpdir.is_dir()


# test CLI arguments --keep (-K) and --keep-failed for temp dir fixtures

test_keep_fname = "hello.txt"


@pytest.mark.meta("test_keep")
def test_keep_function_scoped_tmpdir_inner(function_tmpdir):
    with open(function_tmpdir / test_keep_fname, "w") as f:
        f.write("hello, function-scoped tmpdir")


@pytest.mark.meta("test_keep")
class TestKeepClassScopedTmpdirInner:
    def test_keep_class_scoped_tmpdir_inner(self, class_tmpdir):
        with open(class_tmpdir / test_keep_fname, "w") as f:
            f.write("hello, class-scoped tmpdir")


@pytest.mark.meta("test_keep")
def test_keep_module_scoped_tmpdir_inner(module_tmpdir):
    with open(module_tmpdir / test_keep_fname, "w") as f:
        f.write("hello, module-scoped tmpdir")


@pytest.mark.meta("test_keep")
def test_keep_session_scoped_tmpdir_inner(session_tmpdir):
    with open(session_tmpdir / test_keep_fname, "w") as f:
        f.write("hello, session-scoped tmpdir")


@pytest.mark.parametrize("arg", ["--keep", "-K"])
def test_keep_function_scoped_tmpdir(function_tmpdir, arg):
    inner_fn = test_keep_function_scoped_tmpdir_inner.__name__
    file_path = Path(function_tmpdir / f"{inner_fn}0" / test_keep_fname)
    args = [
        __file__,
        "-v",
        "-s",
        "-k",
        inner_fn,
        "-M",
        "test_keep",
        "-K",
        function_tmpdir,
    ]
    assert pytest.main(args) == ExitCode.OK
    assert file_path.is_file()
    first_modified = file_path.stat().st_mtime

    assert pytest.main(args) == ExitCode.OK
    assert file_path.is_file()
    second_modified = file_path.stat().st_mtime

    # make sure contents were overwritten
    assert first_modified < second_modified


@pytest.mark.parametrize("arg", ["--keep", "-K"])
def test_keep_class_scoped_tmpdir(tmp_path, arg):
    args = [
        __file__,
        "-v",
        "-s",
        "-k",
        TestKeepClassScopedTmpdirInner.test_keep_class_scoped_tmpdir_inner.__name__,
        "-M",
        "test_keep",
        arg,
        tmp_path,
    ]
    assert pytest.main(args) == ExitCode.OK
    assert Path(
        tmp_path / f"{TestKeepClassScopedTmpdirInner.__name__}0" / test_keep_fname
    ).is_file()


@pytest.mark.parametrize("arg", ["--keep", "-K"])
def test_keep_module_scoped_tmpdir(tmp_path, arg):
    args = [
        __file__,
        "-v",
        "-s",
        "-k",
        test_keep_module_scoped_tmpdir_inner.__name__,
        "-M",
        "test_keep",
        arg,
        tmp_path,
    ]
    assert pytest.main(args) == ExitCode.OK
    this_path = Path(__file__)
    keep_path = tmp_path / f"{str(this_path.parent.name)}.{str(this_path.stem)}0"
    assert test_keep_fname in [f.name for f in keep_path.glob("*")]


@pytest.mark.parametrize("arg", ["--keep", "-K"])
def test_keep_session_scoped_tmpdir(tmp_path, arg, request):
    args = [
        __file__,
        "-v",
        "-s",
        "-k",
        test_keep_session_scoped_tmpdir_inner.__name__,
        "-M",
        "test_keep",
        arg,
        tmp_path,
    ]
    assert pytest.main(args) == ExitCode.OK
    assert Path(
        tmp_path / f"{request.config.rootpath.name}0" / test_keep_fname
    ).is_file()


@pytest.mark.meta("test_keep_failed")
def test_keep_failed_function_scoped_tmpdir_inner(function_tmpdir):
    with open(function_tmpdir / test_keep_fname, "w") as f:
        f.write("hello, function-scoped tmpdir")

    assert False, "oh no"


@pytest.mark.parametrize("keep", [True, False])
def test_keep_failed_function_scoped_tmpdir(function_tmpdir, keep):
    inner_fn = test_keep_failed_function_scoped_tmpdir_inner.__name__
    args = [__file__, "-v", "-s", "-k", inner_fn, "-M", "test_keep_failed"]
    if keep:
        args += ["--keep-failed", function_tmpdir]
    assert pytest.main(args) == ExitCode.TESTS_FAILED

    kept_file = Path(function_tmpdir / f"{inner_fn}0" / test_keep_fname).is_file()
    assert kept_file if keep else not kept_file


# test meta-test marker and CLI argument --meta (-M)


@pytest.mark.meta("test_meta")
def test_meta_inner():
    pass


class TestMeta:
    def pytest_terminal_summary(self, terminalreporter):
        stats = terminalreporter.stats
        assert "failed" not in stats

        passed = [test.head_line for test in stats["passed"]]
        assert len(passed) == 1
        assert test_meta_inner.__name__ in passed

        deselected = [fn.name for fn in stats["deselected"]]
        assert len(deselected) > 0


def test_meta():
    args = [
        __file__,
        "-v",
        "-s",
        "-k",
        test_meta_inner.__name__,
        "-M",
        "test_meta",
    ]
    assert pytest.main(args, plugins=[TestMeta()]) == ExitCode.OK


# test fixtures dynamically generated from examples and test models


def test_example_scenario(example_scenario):
    assert isinstance(example_scenario, tuple)
    name, namefiles = example_scenario
    assert isinstance(name, str)
    assert isinstance(namefiles, list)
    assert all(namefile.is_file() for namefile in namefiles)


def test_test_model_mf6(test_model_mf6):
    assert isinstance(test_model_mf6, Path)
    assert test_model_mf6.is_file()
    assert test_model_mf6.name == "mfsim.nam"


def test_test_model_mf5to6(test_model_mf5to6):
    assert isinstance(test_model_mf5to6, Path)
    assert test_model_mf5to6.is_file()
    assert test_model_mf5to6.suffix == ".nam"


def test_large_test_model(large_test_model):
    print(large_test_model)
    assert isinstance(large_test_model, Path)
    assert large_test_model.is_file()
    assert large_test_model.name == "mfsim.nam"


# test tabular data format fixture


test_tabular_fname = "tabular.txt"


@pytest.mark.meta("test_tabular")
def test_tabular_inner(function_tmpdir, tabular):
    with open(function_tmpdir / test_tabular_fname, "w") as f:
        f.write(str(tabular))


@pytest.mark.parametrize("tabular", ["raw", "recarray", "dataframe"])
@pytest.mark.parametrize("arg", ["--tabular", "-T"])
def test_tabular(tabular, arg, function_tmpdir):
    inner_fn = test_tabular_inner.__name__
    args = [
        __file__,
        "-v",
        "-s",
        "-k",
        inner_fn,
        arg,
        tabular,
        "--keep",
        function_tmpdir,
        "-M",
        "test_tabular",
    ]
    assert pytest.main(args) == ExitCode.OK
    res = open(next(function_tmpdir.rglob(test_tabular_fname))).readlines()[0]
    assert tabular == res


# test snapshot fixtures


snapshot_array = np.array([1.1, 2.2, 3.3])
snapshots_path = proj_root / "autotest" / "__snapshots__"


def test_binary_array_snapshot(array_snapshot):
    assert array_snapshot == snapshot_array
    snapshot_path = (
        snapshots_path
        / module_path.stem
        / f"{inspect.currentframe().f_code.co_name}.npy"
    )
    assert snapshot_path.is_file()
    assert np.allclose(np.load(snapshot_path), snapshot_array)


def test_multi_array_snapshot(multi_array_snapshot):
    arrays = {"ascending": snapshot_array, "descending": np.flip(snapshot_array)}
    assert multi_array_snapshot == arrays
    snapshot_path = (
        snapshots_path
        / module_path.stem
        / f"{inspect.currentframe().f_code.co_name}.npz"
    )
    assert snapshot_path.is_file()
    assert np.allclose(np.load(snapshot_path)["ascending"], snapshot_array)
    assert np.allclose(np.load(snapshot_path)["descending"], np.flip(snapshot_array))


def test_text_array_snapshot(text_array_snapshot):
    assert text_array_snapshot == snapshot_array
    snapshot_path = (
        snapshots_path
        / module_path.stem
        / f"{inspect.currentframe().f_code.co_name}.txt"
    )
    assert snapshot_path.is_file()
    assert np.allclose(np.loadtxt(snapshot_path), snapshot_array)


def test_readable_text_array_snapshot(readable_array_snapshot):
    assert readable_array_snapshot == snapshot_array
    snapshot_path = (
        snapshots_path
        / module_path.stem
        / f"{inspect.currentframe().f_code.co_name}.txt"
    )
    assert snapshot_path.is_file()
    assert np.allclose(
        np.fromstring(
            open(snapshot_path).readlines()[0].replace("[", "").replace("]", ""),
            sep=" ",
        ),
        snapshot_array,
    )
