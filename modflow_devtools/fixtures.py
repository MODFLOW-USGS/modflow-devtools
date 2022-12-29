from collections import OrderedDict
from itertools import groupby
from os import PathLike, environ
from pathlib import Path
from shutil import copytree
from typing import Dict, List, Optional

import pytest
from modflow_devtools.misc import (
    get_model_dir_paths,
    get_namefile_paths,
    get_packages,
)

# temporary directory fixtures


@pytest.fixture(scope="function")
def function_tmpdir(tmpdir_factory, request) -> Path:
    node = (
        request.node.name.replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
    )
    temp = Path(tmpdir_factory.mktemp(node))
    yield Path(temp)

    keep = request.config.getoption("--keep")
    if keep:
        copytree(temp, Path(keep) / temp.name)

    keep_failed = request.config.getoption("--keep-failed")
    if keep_failed and request.node.rep_call.failed:
        copytree(temp, Path(keep_failed) / temp.name)


@pytest.fixture(scope="class")
def class_tmpdir(tmpdir_factory, request) -> Path:
    assert (
        request.cls is not None
    ), "Class-scoped temp dir fixture must be used on class"
    temp = Path(tmpdir_factory.mktemp(request.cls.__name__))
    yield temp

    keep = request.config.getoption("--keep")
    if keep:
        copytree(temp, Path(keep) / temp.name)


@pytest.fixture(scope="module")
def module_tmpdir(tmpdir_factory, request) -> Path:
    temp = Path(tmpdir_factory.mktemp(request.module.__name__))
    yield temp

    keep = request.config.getoption("--keep")
    if keep:
        copytree(temp, Path(keep) / temp.name)
        print(list((Path(keep) / temp.name).rglob("*")))


@pytest.fixture(scope="session")
def session_tmpdir(tmpdir_factory, request) -> Path:
    temp = Path(tmpdir_factory.mktemp(request.session.name))
    yield temp

    keep = request.config.getoption("--keep")
    if keep:
        copytree(temp, Path(keep) / temp.name)


# environment-dependent fixtures


@pytest.fixture
def repos_path() -> Optional[Path]:
    """Path to directory containing test model and example repositories"""
    return environ.get("REPOS_PATH", None)


# pytest configuration hooks


def pytest_addoption(parser):
    parser.addoption(
        "-K",
        "--keep",
        action="store",
        default=None,
        help="Move the contents of temporary test directories to correspondingly named subdirectories at the given "
        "location after tests complete. This option can be used to exclude test results from automatic cleanup, "
        "e.g. for manual inspection. The provided path is created if it does not already exist. An error is "
        "thrown if any matching files already exist.",
    )

    parser.addoption(
        "--keep-failed",
        action="store",
        default=None,
        help="Move the contents of temporary test directories to correspondingly named subdirectories at the given "
        "location if the test case fails. This option automatically saves the outputs of failed tests in the "
        "given location. The path is created if it doesn't already exist. An error is thrown if files with the "
        "same names already exist in the given location.",
    )

    parser.addoption(
        "-S",
        "--smoke",
        action="store_true",
        default=False,
        help="Run only smoke tests (should complete in <1 minute).",
    )

    parser.addoption(
        "-M",
        "--meta",
        action="store",
        metavar="NAME",
        help="Indicates a test should only be run by other tests (e.g., to test framework or fixtures).",
    )

    parser.addoption(
        "--model",
        action="append",
        type=str,
        help="Select a subset of models to run.",
    )

    parser.addoption(
        "--package",
        action="append",
        type=str,
        help="Select a subset of packages to run.",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "meta(name): run only by other tests",
    )


def pytest_runtest_setup(item):
    # skip meta-tests unless specified
    meta = item.config.getoption("--meta")
    metagroups = [mark.args[0] for mark in item.iter_markers(name="meta")]
    if metagroups and meta not in metagroups:
        pytest.skip()

    # smoke tests are \ {slow U example U regression}
    smoke = item.config.getoption("--smoke")
    slow = list(item.iter_markers(name="slow"))
    example = list(item.iter_markers(name="example"))
    regression = list(item.iter_markers(name="regression"))
    if smoke and (slow or example or regression):
        pytest.skip()


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    # this is necessary so temp dir fixtures can
    # inspect test results and check for failure
    # (see https://doc.pytest.org/en/latest/example/simple.html#making-test-result-information-available-in-fixtures)

    outcome = yield
    rep = outcome.get_result()

    # report attribute for each phase (setup, call, teardown)
    # we're only interested in result of the function call
    setattr(item, "rep_" + rep.when, rep)


def pytest_generate_tests(metafunc):
    models_selected = metafunc.config.getoption("--model", None)
    packages_selected = metafunc.config.getoption("--package", None)
    repos_path = environ.get("REPOS_PATH")

    key = "test_model_mf6"
    if key in metafunc.fixturenames:
        models = (
            get_namefile_paths(
                Path(repos_path) / "modflow6-testmodels" / "mf6",
                prefix="test",
                excluded=["test205_gwtbuy-henrytidal"],
                selected=models_selected,
                packages=packages_selected,
            )
            if repos_path
            else []
        )
        metafunc.parametrize(key, models, ids=[str(m) for m in models])

    key = "test_model_mf5to6"
    if key in metafunc.fixturenames:
        models = (
            get_namefile_paths(
                Path(repos_path) / "modflow6-testmodels" / "mf5to6",
                prefix="test",
                namefile="*.nam",
                excluded=["test205_gwtbuy-henrytidal"],
                selected=models_selected,
                packages=packages_selected,
            )
            if repos_path
            else []
        )
        metafunc.parametrize(key, models, ids=[str(m) for m in models])

    key = "large_test_model"
    if key in metafunc.fixturenames:
        models = (
            get_namefile_paths(
                Path(repos_path) / "modflow6-largetestmodels",
                prefix="test",
                namefile="mfsim.nam",
                excluded=[],
                selected=models_selected,
                packages=packages_selected,
            )
            if repos_path
            else []
        )
        metafunc.parametrize(key, models, ids=[str(m) for m in models])

    key = "example_scenario"
    if key in metafunc.fixturenames:

        def is_nested(namfile_path: PathLike) -> bool:
            p = Path(namfile_path)
            if not p.is_file() or not p.name.endswith(".nam"):
                raise ValueError(f"Expected namefile path, got {p}")

            return p.parent.parent.name != "examples"

        def example_path_from_namfile_path(path: PathLike) -> Path:
            p = Path(path)
            if not p.is_file() or not p.name.endswith(".nam"):
                raise ValueError(f"Expected namefile path, got {p}")

            return p.parent.parent if is_nested(p) else p.parent

        def example_name_from_namfile_path(path: PathLike) -> str:
            return example_path_from_namfile_path(path).name

        def group_examples(namefile_paths) -> Dict[str, List[Path]]:
            d = OrderedDict()
            for name, paths in groupby(
                namefile_paths, key=example_name_from_namfile_path
            ):
                # sort alphabetically (gwf < gwt)
                nfpaths = sorted(list(paths))

                # skip if no models found
                if len(nfpaths) == 0:
                    continue

                d[name] = nfpaths

            return d

        def get_examples():
            # find and filter namfiles
            namfiles = [
                p
                for p in (
                    Path(repos_path) / "modflow6-examples" / "examples"
                ).rglob("mfsim.nam")
            ]

            # group example scenarios with multiple models
            examples = group_examples(namfiles)

            # filter by example name (optional)
            if models_selected:
                examples = {
                    name: nfps
                    for name, nfps in examples.items()
                    if any(s in name for s in models_selected)
                }

            # filter by package (optional)
            if packages_selected:
                filtered = []
                for name, namefiles in examples.items():
                    ftypes = []
                    for namefile in namefiles:
                        ftype = get_packages(namefile, packages_selected)
                        if ftype not in ftypes:
                            ftypes += ftype
                    if len(ftypes) > 0:
                        ftypes = [item.upper() for item in ftypes]
                        for pkg in packages_selected:
                            if pkg in ftypes:
                                filtered.append(name)
                                break
                examples = {
                    name: nfps
                    for name, nfps in examples.items()
                    if name in filtered
                }

            # remove mf6gwf and mf6gwt
            examples = {
                name: nfps
                for name, nfps in examples.items()
                if name not in ["mf6gwf", "mf6gwt"]
            }

            return examples

        example_scenarios = get_examples() if repos_path else dict()
        metafunc.parametrize(
            key,
            [(name, nfps) for name, nfps in example_scenarios.items()],
            ids=[name for name, ex in example_scenarios.items()],
        )
