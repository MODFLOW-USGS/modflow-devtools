# Executables

The `Executables` class maps executable names to paths on the filesystem. This is useful mainly for testing multiple versions of the same program.

## Usage

For example, assuming development binaries live in `bin` relative to the project root (as is currently the convention for `modflow6`), the following `pytest` fixtures could be defined:

```python
from modflow_devtools.executables import Executables

@pytest.fixture(scope="session")
def bin_path() -> Path:
    return project_root_path / "bin"


@pytest.fixture(scope="session")
def targets(bin_path) -> Executables:
    exes = {
        # ...map names to paths
    }
    return Executables(**exes)
```

The `targets` fixture can then be injected into test functions:

```python
def test_targets(targets):
    # attribute- and dictionary-style access is supported
    assert targets["mf6"] == targets.mf6
    # .get() works too
    assert targets.get("not a target") is None
```
