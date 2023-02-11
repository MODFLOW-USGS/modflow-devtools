# Executables

The `Executables` class maps executable names to paths on the filesystem. This is useful mainly for testing multiple versions of the same program.

## Usage

For example, assuming development binaries live in `bin` relative to the project root (as is currently the convention for `modflow6`), the following `pytest` fixtures could be defined:

```python
from modflow_devtools.executables import build_default_exe_dict, Executables

@pytest.fixture(scope="session")
def bin_path() -> Path:
    return project_root_path / "bin"


@pytest.fixture(scope="session")
def targets(bin_path) -> Executables:
    return Executables(**build_default_exe_dict(bin_path))
```

The `targets` fixture can then be injected into test functions:

```python
def test_targets(targets):
    # attribute- and dictionary-style access is supported
    assert targets["mf6"] == targets.mf6
```

The `build_default_exe_dict` function is provided to create the default executable mapping used by MODFLOW 6 autotests.

There is also a convenience function for getting a program's version string. The function will automatically strip the program name from the output (assumed delimited with `:`).

```python
import subprocess

def test_executables_version(targets):
    # returns e.g. '6.4.1 Release 12/09/2022'
    assert targets.get_version(targets.mf6) == \  
           subprocess.check_output([f"{targets.mf6}", "-v"]).decode('utf-8').strip().split(":")[1].strip()
```
