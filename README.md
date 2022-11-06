# MODFLOW developer tools

[![Project Status: WIP – Initial development is in progress, but there has not yet been a stable, usable release suitable for the public.](https://www.repostatus.org/badges/latest/wip.svg)](https://www.repostatus.org/#wip)
[![CI](https://github.com/MODFLOW-USGS/modflow-devtools/actions/workflows/ci.yml/badge.svg)](https://github.com/MODFLOW-USGS/modflow-devtools/actions/workflows/ci.yml)

Python tools for MODFLOW development and testing.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Requirements](#requirements)
- [Installation](#installation)
- [Included](#included)
  - [`MFZipFile` class](#mfzipfile-class)
  - [Keepable temporary directories](#keepable-temporary-directories)
  - [Model-loading fixtures](#model-loading-fixtures)
    - [Test model fixtures](#test-model-fixtures)
    - [Example scenario fixtures](#example-scenario-fixtures)
  - [Reusable test case framework](#reusable-test-case-framework)
  - [Conditionally skipping tests](#conditionally-skipping-tests)
  - [Miscellaneous](#miscellaneous)
    - [Generating TOCs with `doctoc`](#generating-tocs-with-doctoc)
    - [Testing CI workflows with `act`](#testing-ci-workflows-with-act)
- [MODFLOW Resources](#modflow-resources)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Requirements

This package requires Python3.7+. Its only dependencies are `numpy` and `pytest`.

## Installation

This package is not yet published to PyPI or a Conda channel. To install it please see the [developer documentation](DEVELOPER.md).

## Included

This package contains shared tools for developing and testing MODFLOW 6 and FloPy, including standalone utilities as well as `pytest` fixtures, CLI options, and test parametrizations:

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

### Keepable temporary directories

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
    assert isinstance(function_tmpdir, Path)
    assert function_tmpdir.is_dir()
    assert inspect.currentframe().f_code.co_name in function_tmpdir.stem

    # module-scoped temp dir (accessible to other tests in the script)
    assert module_tmpdir.is_dir()
    assert "autotest" in module_tmpdir.stem
```

Any files written to the temporary directory will be saved to saved to subdirectories of `temp` named according to the test case, class or module. For instance, to store test outputs in a new folder named `temp` relative to the working directory (e.g., `<project root>/autotest`), run:

```shell
pytest <test file> --keep temp
```

There is also a `--keep-failed <path>` variant which only preserves outputs from failing test cases.

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

#### Test model fixtures

The `test_model_mf5to6`, `test_model_mf6` and `large_test_model` fixtures are each a `Path` to the directory containing the model's namefile. For instance, to load `mf5to6` models from the [`MODFLOW-USGS/modflow6-testmodels`](https://github.com/MODFLOW-USGS/modflow6-testmodels) repository:

```python
def test_mf5to6_model(tmpdir, testmodel_mf5to6):
    assert testmodel_mf5to6.is_dir()
```

This test function will be parametrized with all `mf5to6` models found in the `testmodels` repository (likewise for `mf6` models, and for large test models in their own repository).

#### Example scenario fixtures

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

For instance, to generate a set of similar test cases with `pytest-cases`:

```python
from pytest_cases import parametrize

from modflow_devtools.case import Case

template = Case(name="QA")
cases = [
  template.copy_update(name=template.name + "1", question="What's the meaning of life, the universe, and everything?", answer=42),
  template.copy_update(name=template.name + "2", question="Is a Case immutable?", answer="No, but it's better not to mutate it.")
]

@parametrize(data=cases, ids=[c.name for c in cases])
def case_qa(case):
    print(case.name, case.question, case.answer)
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