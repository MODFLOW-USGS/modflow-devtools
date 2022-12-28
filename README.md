# MODFLOW developer tools

### Version 0.0.8 &mdash; release candidate
[![CI](https://github.com/MODFLOW-USGS/modflow-devtools/actions/workflows/ci.yml/badge.svg)](https://github.com/MODFLOW-USGS/modflow-devtools/actions/workflows/ci.yml)
[![GitHub tag](https://img.shields.io/github/tag/MODFLOW-USGS/modflow-devtools.svg)](https://github.com/MODFLOW-USGS/modflow-devtools/tags/latest)
[![PyPI Version](https://img.shields.io/pypi/v/modflow-devtools.png)](https://pypi.python.org/pypi/modflow-devtools)
[![PyPI Status](https://img.shields.io/pypi/status/modflow-devtools.png)](https://pypi.python.org/pypi/modflow-devtools)
[![PyPI Versions](https://img.shields.io/pypi/pyversions/modflow-devtools.png)](https://pypi.python.org/pypi/modflow-devtools)

Python tools for MODFLOW development and testing.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Requirements](#requirements)
- [Installation](#installation)
- [Included](#included)
  - [`MFZipFile` class](#mfzipfile-class)
  - [Keepable temporary directory fixtures](#keepable-temporary-directory-fixtures)
  - [Model-loading fixtures](#model-loading-fixtures)
    - [Test models](#test-models)
    - [Example scenarios](#example-scenarios)
  - [Reusable test case framework](#reusable-test-case-framework)
    - [Parametrizing with `Case`](#parametrizing-with-case)
    - [Generating cases dynamically](#generating-cases-dynamically)
  - [Executables container](#executables-container)
  - [Conditionally skipping tests](#conditionally-skipping-tests)
  - [Miscellaneous](#miscellaneous)
    - [Generating TOCs with `doctoc`](#generating-tocs-with-doctoc)
    - [Testing CI workflows with `act`](#testing-ci-workflows-with-act)
- [MODFLOW Resources](#modflow-resources)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Requirements

This package requires Python3.8+. Its only dependencies are `numpy` and `pytest`.

## Installation

The package is available on PyPI and can be installed with pip:

```shell
pip install modflow-devtools
```

To install from source and set up a development environment please see the [developer documentation](DEVELOPER.md).

## Included

This package contains shared tools for developing and testing MODFLOW 6 and FloPy, including standalone utilities as well as `pytest` fixtures, CLI options, and test cases:

- a `ZipFile` subclass preserving file attributes
- variably-scoped `pytest` temporary directory fixtures
- a `pytest` smoke test CLI option (to run a fast subset of cases)
- a minimal `pytest` framework for reusing test functions and data
- a `pytest_generate_tests` hook to load example/test model fixtures
- a set of `pytest` markers to conditionally skip test cases based on
  - operating system
  - Python packages installed
  - executables available on the path

To import `pytest` fixtures in a project consuming `modflow-devtools`, add the following to a `conftest.py` file in the project root:

```python
pytest_plugins = [ "modflow_devtools.fixtures" ]
```

Note that `pytest` requires this to be a top-level `conftest.py` living in your project root. Nested `conftest.py` files may override or extend this package's behavior.

### `MFZipFile` class

Python's `ZipFile` doesn't preserve execute permissions. The `MFZipFile` subclass modifies `ZipFile.extract()` to do so, as per the recommendation [here](https://stackoverflow.com/questions/39296101/python-zipfile-removes-execute-permissions-from-binaries).

### Keepable temporary directory fixtures

Tests often need to exercise code that reads from and/or writes to disk. The test harness may also need to create test data during setup and clean up the filesystem on teardown. Temporary directories are built into `pytest` via the [`tmp_path`](https://docs.pytest.org/en/latest/how-to/tmp_path.html#the-tmp-path-fixture) and `tmp_path_factory` fixtures.

Several fixtures are provided in `modflow_devtools/fixtures.py` to extend the behavior of temporary directories for test functions:

- `function_tmpdir`
- `module_tmpdir`
- `class_tmpdir`
- `session_tmpdir`

These are automatically created before test code runs and lazily removed afterwards, subject to the same [cleanup procedure](https://docs.pytest.org/en/latest/how-to/tmp_path.html#the-default-base-temporary-directory) used by the default `pytest` temporary directory fixtures. Their purpose is to allow test artifacts to be saved in a user-specified location when `pytest` is invoked with a `--keep` option &mdash; this can be useful to debug failing tests.

```python
from pathlib import Path
import inspect

def test_tmpdirs(function_tmpdir, module_tmpdir):
    # function-scoped temporary directory
    assert function_tmpdir.is_dir()
    assert inspect.currentframe().f_code.co_name in function_tmpdir.stem

    # module-scoped temp dir (accessible to other tests in the script)
    assert module_tmpdir.is_dir()

    with open(function_tmpdir / "test.txt", "w") as f1, open(module_tmpdir / "test.txt", "w") as f2:
        f1.write("hello, function")
        f2.write("hello, module")
```

Any files written to the temporary directory will be saved to saved to subdirectories named according to the test case, class or module. To keep files created by a test case like above, run:

```shell
pytest --keep <path>
```

There is also a `--keep-failed <path>` option which preserves outputs only from failing test cases.

### Model-loading fixtures

Fixtures are provided to load models from the MODFLOW 6 example and test model repositories and feed them to test functions. Models can be loaded from:

- [`MODFLOW-USGS/modflow6-examples`](https://github.com/MODFLOW-USGS/modflow6-examples)
- [`MODFLOW-USGS/modflow6-testmodels`](https://github.com/MODFLOW-USGS/modflow6-testmodels)
- [`MODFLOW-USGS/modflow6-largetestmodels`](https://github.com/MODFLOW-USGS/modflow6-largetestmodels)

These models can be requested like any other `pytest` fixture, by adding one of the following parameters to test functions:

- `test_model_mf5to6`
- `test_model_mf6`
- `large_test_model`
- `example_scenario`

To use these fixtures, the environment variable `REPOS_PATH` must point to the location of model repositories on the filesystem. Model repositories must live side-by-side in this location. If `REPOS_PATH` is not configured, test functions requesting these fixtures will be skipped.

**Note**: example models must be built by running the `ci_build_files.py` script in `modflow6-examples/etc` before running tests using the `example_scenario` fixture.

#### Test models

The `test_model_mf5to6`, `test_model_mf6` and `large_test_model` fixtures are each a `Path` to the directory containing the model's namefile. For instance, to load `mf5to6` models from the [`MODFLOW-USGS/modflow6-testmodels`](https://github.com/MODFLOW-USGS/modflow6-testmodels) repository:

```python
def test_mf5to6_model(tmpdir, testmodel_mf5to6):
    assert testmodel_mf5to6.is_dir()
```

This test function will be parametrized with all `mf5to6` models found in the `testmodels` repository (likewise for `mf6` models, and for large test models in their own repository).

#### Example scenarios

The [`MODFLOW-USGS/modflow6-examples`](https://github.com/MODFLOW-USGS/modflow6-examples) repository contains a collection of scenarios, each consisting of 1 or more models. The `example_scenario` fixture is a `Tuple[str, List[Path]]`. The first item is the name of the scenario. The second item is a list of namefile `Path`s, ordered alphabetically by name. Model naming conventions are as follows:

- groundwater flow models begin with prefix `gwf*`
- transport models begin with `gwt*`

Ordering as above permits models to be run directly in the order provided, with transport models potentially consuming the outputs of flow models. A straightforward pattern is to loop over models and run each in a subdirectory of the same top-level working directory.

```python
def test_example_scenario(tmpdir, example_scenario):
    name, namefiles = example_scenario
    for namefile in namefiles:
        model_ws = tmpdir / namefile.parent.name
        model_ws.mkdir()
        # load and run model
        # ...
```

### Reusable test case framework

A second approach to testing, more flexible than loading pre-existing models from a repository, is to construct test models in code. This typically involves defining variables or `pytest` fixtures in the same test script as the test function. While this pattern is effective for manually defined scenarios, it tightly couples test functions to test cases, prevents easy reuse of the test case by other tests, and tends to lead to duplication, as each test script may reproduce similar test functions and data-generation procedures.

This package provides a minimal framework for self-describing test cases which can be defined once and plugged into arbitrary test functions. At its core is the `Case` class, which is just a `SimpleNamespace` with a few defaults and a `copy_update()` method for easy modification. This pairs nicely with [`pytest-cases`](https://smarie.github.io/python-pytest-cases/), which is recommended but not required.

A `Case` requires only a `name`, and has a single default attribute, `xfail=False`, indicating whether the test case is expected to succeed. (Test functions may of course choose to use or ignore this.)

#### Parametrizing with `Case`

`Case` can be used with `@pytest.mark.parametrize()` as usual. For instance:

```python
import pytest
from modflow_devtools.case import Case

template = Case(name="QA")
cases = [
    template.copy_update(name=template.name + "1",
                         question="What's the meaning of life, the universe, and everything?",
                         answer=42),
    template.copy_update(name=template.name + "2",
                         question="Is a Case immutable?",
                         answer="No, but it's probably best not to mutate it.")
]


@pytest.mark.parametrize("case", cases)
def test_cases(case):
    assert len(cases) == 2
    assert cases[0] != cases[1]
```

#### Generating cases dynamically

One pattern possible with `pytest-cases` is to programmatically generate test cases by parametrizing a function. This can be a convenient way to produce several similar test cases from a template:

```python
from pytest_cases import parametrize, parametrize_with_cases
from modflow_devtools.case import Case


template = Case(name="QA")
gen_cases = [template.copy_update(name=f"{template.name}{i}", question=f"Q{i}", answer=f"A{i}") for i in range(3)]
info = "cases can be modified further in the generator function,"\
       " or the function may construct and return another object"


@parametrize(case=gen_cases, ids=[c.name for c in gen_cases])
def qa_cases(case):
    return case.copy_update(info=info)


@parametrize_with_cases("case", cases=".", prefix="qa_")
def test_qa(case):
    assert "QA" in case.name
    assert info == case.info
    print(f"{case.name}:", f"{case.question}? {case.answer}")
    print(case.info)
```

### Executables container

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

### Conditionally skipping tests

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

### Miscellaneous

A few other useful tools for MODFLOW 6 and FloPy development include:

- [`doctoc`](https://www.npmjs.com/package/doctoc): automatically generate table of contents sections for markdown files
- [`act`](https://github.com/nektos/act): test GitHub Actions workflows locally (requires Docker)

#### Generating TOCs with `doctoc`

The [`doctoc`](https://www.npmjs.com/package/doctoc) tool can be used to automatically generate table of contents sections for markdown files. `doctoc` is distributed with the [Node Package Manager](https://docs.npmjs.com/cli/v7/configuring-npm/install). With Node installed use `npm install -g doctoc` to install `doctoc` globally. Then just run `doctoc <file>`, e.g.:

```shell
doctoc DEVELOPER.md
```

This will insert HTML comments surrounding an automatically edited region, scanning for headers and creating an appropriately indented TOC tree.  Subsequent runs are idempotent, updating if the file has changed or leaving it untouched if not.

To run `doctoc` for all markdown files in a particular directory (recursive), use `doctoc some/path`.

#### Testing CI workflows with `act`

The [`act`](https://github.com/nektos/act) tool uses Docker to run containerized CI workflows in a simulated GitHub Actions environment. [Docker Desktop](https://www.docker.com/products/docker-desktop/) is required for Mac or Windows and [Docker Engine](https://docs.docker.com/engine/) on Linux.

With Docker installed and running, run `act -l` from the project root to see available CI workflows. To run all workflows and jobs, just run `act`. To run a particular workflow use `-W`:

```shell
act -W .github/workflows/commit.yml
```

To run a particular job within a workflow, add the `-j` option:

```shell
act -W .github/workflows/commit.yml -j build
```

**Note:** GitHub API rate limits are easy to exceed, especially with job matrices. Authenticated GitHub users have a much higher rate limit: use `-s GITHUB_TOKEN=<your token>` when invoking `act` to provide a personal access token. Note that this will log your token in shell history &mdash; leave the value blank for a prompt to enter it more securely.

The `-n` flag can be used to execute a dry run, which doesn't run anything, just evaluates workflow, job and step definitions. See the [docs](https://github.com/nektos/act#example-commands) for more.

**Note:** `act` can only run Linux-based container definitions, so Mac or Windows workflows or matrix OS entries will be skipped.


## MODFLOW Resources

+ [MODFLOW and Related Programs](https://water.usgs.gov/ogw/modflow/)
+ [Online guide for MODFLOW-2000](https://water.usgs.gov/nrp/gwsoftware/modflow2000/Guide/)
+ [Online guide for MODFLOW-2005](https://water.usgs.gov/ogw/modflow/MODFLOW-2005-Guide/)
+ [Online guide for MODFLOW-NWT](https://water.usgs.gov/ogw/modflow-nwt/MODFLOW-NWT-Guide/)
