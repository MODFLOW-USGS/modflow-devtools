# MODFLOW developer tools

[![GitHub tag](https://img.shields.io/github/tag/MODFLOW-USGS/modflow-devtools.svg)](https://github.com/MODFLOW-USGS/modflow-devtools/tags/latest)
[![PyPI Version](https://img.shields.io/pypi/v/modflow-devtools.png)](https://pypi.python.org/pypi/modflow-devtools)
[![PyPI Versions](https://img.shields.io/pypi/pyversions/modflow-devtools.png)](https://pypi.python.org/pypi/modflow-devtools)
[![PyPI Status](https://img.shields.io/pypi/status/modflow-devtools.png)](https://pypi.python.org/pypi/modflow-devtools)
[![CI](https://github.com/MODFLOW-USGS/modflow-devtools/actions/workflows/ci.yml/badge.svg)](https://github.com/MODFLOW-USGS/modflow-devtools/actions/workflows/ci.yml)
[![Documentation Status](https://readthedocs.org/projects/modflow-devtools/badge/?version=latest)](https://modflow-devtools.readthedocs.io/en/latest/?badge=latest)

Python development tools for MODFLOW 6.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->


- [Use cases](#use-cases)
- [Requirements](#requirements)
- [Installation](#installation)
- [Documentation](#documentation)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Use cases

This is a small toolkit for developing MODFLOW 6, FloPy, and related projects. It includes standalone utilities and optional [Pytest](https://github.com/pytest-dev/pytest) extensions.

Standalone utilities include a very minimal GitHub API client, mainly for retrieving release information and downloading asset, and a `ZipFile` subclass that [preserves file permissions](https://stackoverflow.com/questions/39296101/python-zipfile-removes-execute-permissions-from-binaries) (workaround for [Python #15795](https://bugs.python.org/issue15795))

Pytest features include:

- `--keep <path>` tempdir fixtures for [each scope](https://docs.pytest.org/en/stable/how-to/fixtures.html#scope-sharing-fixtures-across-classes-modules-packages-or-session)
- a [`--smoke` test](https://en.wikipedia.org/wiki/Smoke_testing_(software)) (abbrev. `-S`) CLI option shortcut
- markers to skip test cases conditional on
  - operating system
  - Python packages installed
  - executables available on the PATH
- test fixtures for example / test models in
  - `MODFLOW-USGS/modflow6-examples`
  - `MODFLOW-USGS/modflow6-testmodels`
  - `MODFLOW-USGS/modflow6-largetestmodels`

## Requirements

Python3.8+, dependency-free, but pairs well with `pytest` and select plugins, e.g.

- [`pytest-dotenv`](https://github.com/quiqua/pytest-dotenv)
- [`pytest-xdist`](https://github.com/pytest-dev/pytest-xdist)

## Installation

`modflow-devtools` is available on PyPI and can be installed with pip:

```shell
pip install modflow-devtools
```

Pytest, pytest plugins, and other optional dependencies can be installed with:

```shell
pip install "modflow-devtools[test]"
```

To install from source and set up a development environment please see the [developer documentation](DEVELOPER.md).

To import `pytest` fixtures in a project consuming `modflow-devtools`, add the following to a `conftest.py` file:

```python
pytest_plugins = [ "modflow_devtools.fixtures" ]
```

**Note**: this must be a top-level `conftest.py`, which nested `conftest.py` files may then override or extend.

## Documentation

Docs are available at [modflow-devtools.readthedocs.io](https://modflow-devtools.readthedocs.io/en/latest/).

For more info on MODFLOW 6 see [the USGS overview](https://water.usgs.gov/ogw/modflow/).
