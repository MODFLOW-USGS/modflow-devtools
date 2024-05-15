# Markers

Some broadly useful `pytest` markers are provided.

## Default markers

By default, the following markers are defined for any project consuming `modflow-devtools` as a `pytest` plugin:

- `slow`: tests taking more than a few seconds to complete
- `regression`: tests comparing results from different versions of a program

### Smoke testing

[Smoke testing](https://en.wikipedia.org/wiki/Smoke_testing_(software)) is a form of integration testing which aims to exercise a substantial subset of the codebase quickly enough to run often during development. This is useful to rapidly determine whether a refactor has broken any expectations before running slower, more extensive tests.

To run smoke tests, use the `--smoke` (short `-S`) CLI option. For instance:

```shell
pytest -v -S
```

## Conditionally skipping tests

Several `pytest` markers are provided to conditionally skip tests based on executable availability, Python package environment or operating system.

To skip tests if one or more executables are not available on the path:

```python
from shutil import which
from modflow_devtools.markers import requires_exe

@requires_exe("mf6")
def test_mf6():
    assert which("mf6")

@requires_exe("mf6", "mp7")
def test_mf6_and_mp7():
    assert which("mf6")
    assert which("mp7")
```

To skip tests if one or more Python packages are not available:

```python
from modflow_devtools.markers import requires_pkg

@requires_pkg("pandas")
def test_needs_pandas():
    import pandas as pd

@requires_pkg("pandas", "shapefile")
def test_needs_pandas():
    import pandas as pd
    from shapefile import Reader
```

To mark tests requiring or incompatible with particular operating systems:

```python
import os
import platform
from modflow_devtools.markers import requires_platform, excludes_platform

@requires_platform("Windows")
def test_needs_windows():
    assert platform.system() == "Windows"

@excludes_platform("Darwin", ci_only=True)
def test_breaks_osx_ci():
    if "CI" in os.environ:
        assert platform.system() != "Darwin"
```

Platforms must be specified as returned by `platform.system()`.

Both these markers accept a `ci_only` flag, which indicates whether the policy should only apply when the test is running on GitHub Actions CI.

Markers are also provided to ping network resources and skip if unavailable:

- `@requires_github`: skips if `github.com` is unreachable
- `@requires_spatial_reference`: skips if `spatialreference.org` is unreachable

A marker is also available to skip tests if `pytest` is running in parallel with [`pytest-xdist`](https://pytest-xdist.readthedocs.io/en/latest/):

```python
from os import environ
from modflow_devtools.markers import no_parallel

@no_parallel
def test_only_serially():
    # https://pytest-xdist.readthedocs.io/en/stable/how-to.html#identifying-the-worker-process-during-a-test.
    assert environ.get("PYTEST_XDIST_WORKER") is None
```

## Aliases

All markers are aliased to imperative mood, e.g. `require_github`. Some have other aliases as well:

- `requires_pkg` -> `require[s]_package`
- `requires_exe` -> `require[s]_program`
