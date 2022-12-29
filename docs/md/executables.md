# Executables

The `Executables` class is just a mapping between executable names and paths on the filesystem. This can be useful to test multiple versions of the same program, and is easily injected into test functions as a fixture:

```python
from os import environ
from pathlib import Path
import subprocess
import sys

import pytest

from modflow_devtools.misc import get_suffixes
from modflow_devtools.executables import Executables

_bin_path = Path("~/.local/bin/modflow").expanduser()
_dev_path = Path(environ.get("BIN_PATH")).absolute()
_ext, _ = get_suffixes(sys.platform) 

@pytest.fixture
@pytest.mark.skipif(not (_bin_path.is_dir() and _dev_path.is_dir()))
def exes():
    return Executables(
        mf6_rel=_bin_path / f"mf6{_ext}",
        mf6_dev=_dev_path / f"mf6{_ext}"
    )

def test_exes(exes):
    print(subprocess.check_output([f"{exes.mf6_rel}", "-v"]).decode('utf-8'))
    print(subprocess.check_output([f"{exes.mf6_dev}", "-v"]).decode('utf-8'))
```