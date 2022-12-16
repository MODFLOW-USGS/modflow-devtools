import subprocess
import sys
from os import environ
from pathlib import Path

import pytest
from modflow_devtools.executables import Executables
from modflow_devtools.misc import add_sys_path, get_suffixes

_bin_path = Path(environ.get("BIN_PATH")).expanduser().absolute()
_ext, _ = get_suffixes(sys.platform)


@pytest.mark.skipif(not _bin_path.is_dir(), reason="bin directory not found")
def test_get_path():
    with add_sys_path(str(_bin_path)):
        ext, _ = get_suffixes(sys.platform)
        assert (
            Executables.get_path("mf6", path=_bin_path)
            == _bin_path / f"mf6{ext}"
        )


def test_get_version():
    with add_sys_path(str(_bin_path)):
        ver_str = Executables.get_version("mf6", path=_bin_path).partition(" ")
        print(ver_str)
        version = int(ver_str[0].split(".")[0])
        assert version >= 6


@pytest.fixture
def exes():
    return Executables(mf6=_bin_path / f"mf6{_ext}")


def test_executables_mapping(exes):
    print(exes.mf6)
    assert exes.mf6 == _bin_path / f"mf6{_ext}"


def test_executables_usage(exes):
    output = subprocess.check_output([f"{exes.mf6}", "-v"]).decode("utf-8")
    print(output)
    assert "mf6" in output
