# Executables

The `Executables` class maps executable names to paths on the filesystem. This is useful mainly for testing multiple versions of the same program.

## Usage

For example, assuming you have some development binaries in `bin` relative to your current working directory, and an official installation of the same programs in `~/.local.bin`:

```python
from pathlib import Path
from modflow_devtools.executables import Executables

bindir_path = Path("~/.local/bin").expanduser()
executables = Executables(mf6=bindir_path / "mf6", mf6_dev=Path("mf6"))

# constructor also supports kwargs
executables = Executables(**{"mf6": bindir_path / "mf6", "mf6_dev": Path("mf6")})

def test_executables():
    assert executables.mf6.is_file()
    assert executables.mf6_dev.is_file()

    assert executables.mf6 == bindir_path / "mf6"
    assert executables.mf6_dev == Path("mf6")
```

The class is easily injected into test functions as a fixture:

```python
import pytest

@pytest.fixture
@pytest.mark.skipif(not bindir_path.is_dir())
def exes():
    return executables
```

Dictionary-style access is also supported:

```python
def test_executables_access(executables):
    assert executables["mf6"] == executables.mf6 == Path("mf6")
```

There is a convenience function for getting a program's version string. The function will automatically strip the program name from the output (assumed delimited with `:`).

```python
import subprocess

def test_executables_version(exes):
    # e.g. '6.4.1 Release 12/09/2022'
    assert exes.get_version(exes.mf6) == \  
           subprocess.check_output([f"{exes.mf6}", "-v"]).decode('utf-8').strip().split(":")[1].strip()
```

## Default mapping

A utility function is provided to create the default executable mapping used by MODFLOW 6 autotests:

```python
from modflow_devtools.executables import build_default_exe_dict, Executables

exes = Executables(**build_default_exe_dict())
```