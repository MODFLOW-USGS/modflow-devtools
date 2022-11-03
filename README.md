# MODFLOW developer tools

[![Project Status: WIP – Initial development is in progress, but there has not yet been a stable, usable release suitable for the public.](https://www.repostatus.org/badges/latest/wip.svg)](https://www.repostatus.org/#wip)

Python tools for MODFLOW development and testing.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
  - [Regression test framework](#regression-test-framework)
  - [`MFZipFile` class and usage](#mfzipfile-class-and-usage)
  - [Keepable temporary directories](#keepable-temporary-directories)
  - [Example model test generation](#example-model-test-generation)
    - [Test model fixtures](#test-model-fixtures)
    - [Example model fixtures](#example-model-fixtures)
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

## Usage

This package contains shared tools for developing and testing MODFLOW 6 and FloPy, including standalone utilities as well as `pytest` fixtures, CLI options, and test parametrizations:

- a framework for MODFLOW regression test comparisons
- a `ZipFile` child class preserving file attributes
- various `pytest` fixtures and utilities
  - keepable temporary directories
  - fixtures/hooks to generate tests from example repos
  - markers to conditionally skip test cases based on
    - operating system
    - Python packages installed
    - executables available on the path

To import `pytest` configuration in a project consuming `modflow-devtools`, add the following to the project's top-level `conftest.py` file:

```python
pytest_plugins = [ "modflow_devtools" ]
```

Note that `pytest` requires that this `conftest.py` live in your project root. (You can create nested `conftest.py` files to override default behavior if needed.)

### Regression test framework

*TODO*

### `MFZipFile` class and usage

*TODO*

### Keepable temporary directories

Tests often need to exercise code that reads from and/or writes to disk. The test harness may also need to create test data during setup and clean up the filesystem on teardown. Temporary directories are built into `pytest` via the [`tmp_path`](https://docs.pytest.org/en/latest/how-to/tmp_path.html#the-tmp-path-fixture) and `tmp_path_factory` fixtures.

Several fixtures are provided in `modflow_devtools/test/conftest.py` to extend the behavior of temporary directories for test functions:

- `tmpdir`
- `module_tmpdir`
- `class_tmpdir`
- `session_tmpdir`

These are automatically created before test code runs and lazily removed afterwards, subject to the same [cleanup procedure](https://docs.pytest.org/en/latest/how-to/tmp_path.html#the-default-base-temporary-directory) used by the default `pytest` fixtures. Their purpose is to allow temporary test artifacts to be saved in a user-specified location when `pytest` is invoked with a `--keep` option &mdash; this can be useful to debug failing tests.

```python
from pathlib import Path
import inspect

def test_tmpdirs(tmpdir, module_tmpdir):
    # function-scoped temporary directory
    assert isinstance(tmpdir, Path)
    assert tmpdir.is_dir()
    assert inspect.currentframe().f_code.co_name in tmpdir.stem

    # module-scoped temp dir (accessible to other tests in the script)
    assert module_tmpdir.is_dir()
    assert "autotest" in module_tmpdir.stem
```

Any files written to the temporary directory will be saved to saved to subdirectories of `temp` named according to the test case, class or module. For instance, to store test outputs in a new folder named `temp` relative to the working directory (e.g., `<project root>/autotest`), run:

```shell
pytest <test file> --keep temp
```

### Example model test generation

Fixtures are provided to parametrize test functions dynamically from models in the MODFLOW 6 example and test model repositories:

- [`MODFLOW-USGS/modflow6-examples`](https://github.com/MODFLOW-USGS/modflow6-examples)
- [`MODFLOW-USGS/modflow6-testmodels`](https://github.com/MODFLOW-USGS/modflow6-testmodels)
- [`MODFLOW-USGS/modflow6-largetestmodels`](https://github.com/MODFLOW-USGS/modflow6-largetestmodels)

These can be requested like any other `pytest` fixture by adding one of the following test function arguments:

- `test_model_mf5to6`
- `test_model_mf6`
- `large_test_model`
- `example_scenario`

**Note**: test models for `mf5to6` and `mf6` both live in the `modflow6-testmodels` repository and must be requested separately.

**Note**: example models must be built with the `ci_build_files.py` script located in `modflow6-examples/etc` before running tests using the `example_scenario` fixture.

#### Test model fixtures

The `test_model_mf5to6`, `test_model_mf6` and `large_test_model` fixtures are the `Path` to the directory containing the model's namefile. These can be used straightforwardly, for instance:

```python
def test_mf5to6_model(
        tmpdir: Path,
        testmodel_mf5to6: Path):
    # load the model 
    # switch to temp workdir
    # run the model
    ...
```

#### Example model fixtures

The `example_scenario` fixture is an ordered list of model namefile `Path`s, representing models to be run in the specified order. (Order matters, as some models may depend on the outputs of others.)

### Conditionally skipping tests

Several `pytest` markers are provided to conditionally skip tests based on executable availability, Python package environment or operating system.

To skip tests if one or more executables are not available on the path:

```python
from shutil import which
from autotest.conftest import requires_exe

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
from autotest.conftest import requires_pkg

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
from autotest.conftest import requires_platform, excludes_platform

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

There is also a `@requires_github` marker, which will skip decorated tests if the GitHub API is unreachable.

### Miscellaneous

A few other useful tools for FloPy development include:

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