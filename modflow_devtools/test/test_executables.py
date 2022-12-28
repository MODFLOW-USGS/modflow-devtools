import subprocess
import sys
from os import environ
from pathlib import Path

import pytest
from modflow_devtools.executables import Executables, build_default_exe_dict
from modflow_devtools.misc import add_sys_path, get_suffixes

_bin_path = Path(environ.get("BIN_PATH")).expanduser().absolute()
_ext, _ = get_suffixes(sys.platform)


@pytest.fixture
def exes():
    if not _bin_path.is_dir():
        pytest.skip(f"BIN_PATH ({_bin_path}) is not a directory")

    with add_sys_path(str(_bin_path)):
        yield Executables(**build_default_exe_dict(_bin_path))


def test_get_version(exes):
    ver_str = Executables.get_version(exes.mf6)
    version = (
        subprocess.check_output([f"{exes.mf6}", "-v"])
        .decode("utf-8")
        .split(":")[1]
        .strip()
    )
    assert ver_str == version
    assert int(ver_str[0].split(".")[0]) >= 6


def test_mapping(exes):
    print(exes.mf6)
    assert (
        exes.mf6 == exes["mf6"]
    )  # should support both attribute and dictionary access
    assert exes.mf6 == _bin_path / f"mf6{_ext}"  # should be the correct path
    assert exes.mf6_regression.parent.parent == _bin_path
