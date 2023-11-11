import subprocess
import sys
from pathlib import Path
from shutil import which

import pytest

from modflow_devtools.executables import Executables
from modflow_devtools.misc import add_sys_path, get_suffixes

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
