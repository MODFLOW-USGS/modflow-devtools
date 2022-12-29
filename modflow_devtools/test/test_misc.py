import os
from os import environ
from pathlib import Path
from typing import List

import pytest
from modflow_devtools.misc import (
    get_model_dir_paths,
    get_namefile_paths,
    get_packages,
    set_dir,
)


def test_set_dir(tmp_path):
    assert Path(os.getcwd()) != tmp_path
    with set_dir(tmp_path):
        assert Path(os.getcwd()) == tmp_path
    assert Path(os.getcwd()) != tmp_path


_repos_path = Path(environ.get("REPOS_PATH")).expanduser().absolute()
_largetestmodels_repo_path = _repos_path / "modflow6-largetestmodels"
_largetestmodel_paths = sorted(list(_largetestmodels_repo_path.glob("test*")))
_examples_repo_path = _repos_path / "modflow6-examples"
_examples_path = _examples_repo_path / "examples"
_example_paths = (
    sorted(list(_examples_path.glob("ex-*")))
    if _examples_path.is_dir()
    else []
)


@pytest.mark.skipif(not any(_example_paths), reason="examples not found")
def test_has_packages():
    example_path = _example_paths[0]
    packages = get_packages(example_path / "mfsim.nam")
    assert set(packages) == {"tdis", "gwf", "ims"}


def get_expected_model_dirs(path, pattern="mfsim.nam") -> List[Path]:
    folders = []
    for root, dirs, files in os.walk(path):
        for d in dirs:
            p = Path(root) / d
            if any(p.glob(pattern)):
                folders.append(p)
    return sorted(list(set(folders)))


def get_expected_namefiles(path, pattern="mfsim.nam") -> List[Path]:
    folders = []
    for root, dirs, files in os.walk(path):
        for d in dirs:
            p = Path(root) / d
            found = list(p.glob(pattern))
            folders = folders + found
    return sorted(list(set(folders)))


@pytest.mark.skipif(
    not any(_example_paths), reason="modflow6-examples repo not found"
)
def test_get_model_dir_paths_examples():
    expected_paths = get_expected_model_dirs(_examples_path)
    paths = get_model_dir_paths(_examples_path)
    assert paths == sorted(list(set(paths)))  # no duplicates
    assert set(expected_paths) == set(paths)

    expected_paths = get_expected_model_dirs(_examples_path, "*.nam")
    paths = get_model_dir_paths(_examples_path, namefile="*.nam")
    assert paths == sorted(list(set(paths)))
    assert set(expected_paths) == set(paths)


@pytest.mark.skipif(
    not any(_largetestmodel_paths), reason="modflow6-largetestmodels not found"
)
def test_get_model_dir_paths_largetestmodels():
    expected_paths = get_expected_model_dirs(_examples_path)
    paths = get_model_dir_paths(_examples_path)
    assert paths == sorted(list(set(paths)))
    assert set(expected_paths) == set(paths)

    expected_paths = get_expected_model_dirs(_examples_path)
    paths = get_model_dir_paths(_examples_path)
    assert paths == sorted(list(set(paths)))
    assert set(expected_paths) == set(paths)


@pytest.mark.skipif(
    not any(_largetestmodel_paths) or not any(_example_paths),
    reason="repos not found",
)
@pytest.mark.parametrize(
    "models", [(_examples_path, 63), (_largetestmodels_repo_path, 15)]
)
def test_get_model_dir_paths_exclude_patterns(models):
    path, expected_count = models
    paths = get_model_dir_paths(path, excluded=["gwt"])
    assert len(paths) == expected_count


@pytest.mark.skipif(
    not any(_example_paths), reason="modflow6-examples repo not found"
)
def test_get_namefile_paths_examples():
    expected_paths = get_expected_namefiles(_examples_path)
    paths = get_namefile_paths(_examples_path)
    assert paths == sorted(list(set(paths)))
    assert set(expected_paths) == set(paths)

    expected_paths = get_expected_namefiles(_examples_path, "*.nam")
    paths = get_namefile_paths(_examples_path, namefile="*.nam")
    assert paths == sorted(list(set(paths)))
    assert set(expected_paths) == set(paths)


@pytest.mark.skipif(
    not any(_largetestmodel_paths), reason="modflow6-largetestmodels not found"
)
def test_get_namefile_paths_largetestmodels():
    expected_paths = get_expected_namefiles(_largetestmodels_repo_path)
    paths = get_namefile_paths(_largetestmodels_repo_path)
    assert paths == sorted(list(set(paths)))
    assert set(expected_paths) == set(paths)

    expected_paths = get_expected_namefiles(_largetestmodels_repo_path)
    paths = get_namefile_paths(_largetestmodels_repo_path)
    assert paths == sorted(list(set(paths)))
    assert set(expected_paths) == set(paths)


@pytest.mark.skipif(
    not any(_largetestmodel_paths) or not any(_example_paths),
    reason="repos not found",
)
@pytest.mark.parametrize(
    "models", [(_examples_path, 43), (_largetestmodels_repo_path, 18)]
)
def test_get_namefile_paths_exclude_patterns(models):
    path, expected_count = models
    paths = get_namefile_paths(path, excluded=["gwf"])
    assert len(paths) == expected_count


@pytest.mark.skipif(not any(_example_paths), reason="examples not found")
def test_get_namefile_paths_select_prefix():
    paths = get_namefile_paths(_examples_path, prefix="ex2")
    assert not any(paths)

    paths = get_namefile_paths(_examples_path, prefix="ex")
    assert any(paths)


@pytest.mark.skipif(not any(_example_paths), reason="examples not found")
def test_get_namefile_paths_select_patterns():
    paths = get_namefile_paths(_examples_path, selected=["gwf"])
    assert len(paths) == 70


@pytest.mark.skipif(not any(_example_paths), reason="examples not found")
def test_get_namefile_paths_select_packages():
    paths = get_namefile_paths(
        _examples_path, namefile="*.nam", packages=["wel"]
    )
    assert len(paths) == 64
