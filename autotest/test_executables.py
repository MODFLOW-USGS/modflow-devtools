import subprocess
import sys
from pathlib import Path
from shutil import which

import pytest

from modflow_devtools.executables import Executables
from modflow_devtools.misc import get_suffixes, add_sys_path

ext, _ = get_suffixes(sys.platform)
exe_stem = "pytest"
exe_path = Path(which(exe_stem))
bin_path = exe_path.parent
exe = f"{exe_stem}{ext}"


@pytest.fixture
def exes():
    with add_sys_path(bin_path):
        yield Executables(**{exe_stem: bin_path / exe})


def test_access(exes):
    # support both attribute and dictionary style access
    assert exes.pytest == exes["pytest"] == exe_path


def test_get_version(exes):
    ver_str = Executables.get_version(exes.pytest)
    version = (
        subprocess.check_output([f"{exes.pytest}", "-v"])
        .decode("utf-8")
        .split(":")[1]
        .strip()
    )
    assert ver_str == version
    assert int(ver_str[0].split(".")[0]) >= 6
