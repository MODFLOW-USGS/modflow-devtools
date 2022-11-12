import os
from os import environ
from pathlib import Path
from typing import List

import pytest
from modflow_devtools.misc import get_model_paths, get_packages, set_dir


def test_set_dir(tmp_path):
    assert Path(os.getcwd()) != tmp_path
    with set_dir(tmp_path):
        assert Path(os.getcwd()) == tmp_path
    assert Path(os.getcwd()) != tmp_path


_repos_path = Path(environ.get("REPOS_PATH")).expanduser().absolute()
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


@pytest.mark.skipif(not any(_example_paths), reason="examples not found")
def test_get_model_paths():
    def get_expected(path, pattern="mfsim.nam") -> List[Path]:
        folders = []
        for root, dirs, files in os.walk(path):
            for d in dirs:
                p = Path(root) / d
                if any(p.glob(pattern)):
                    folders.append(p)
        return sorted(folders)

    expected_paths = get_expected(_examples_path)
    paths = get_model_paths(_examples_path)
    assert set(expected_paths) == set(paths)

    expected_paths = get_expected(_examples_path, "*.nam")
    paths = get_model_paths(_examples_path, namefile="*.nam")
    assert set(expected_paths) == set(paths)


def test_get_model_paths_exclude_patterns():
    paths = get_model_paths(_examples_path, excluded=["gwt"])
    assert len(paths) == 63


def test_get_model_paths_select_prefix():
    paths = get_model_paths(_examples_path, prefix="ex2")
    assert not any(paths)


def test_get_model_paths_select_patterns():
    paths = get_model_paths(_examples_path, selected=["gwf"])
    assert len(paths) == 70


def test_get_model_paths_select_packages():
    paths = get_model_paths(_examples_path, namefile="*.nam", packages=["wel"])
    assert len(paths) == 64
