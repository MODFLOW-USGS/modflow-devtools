# MODFLOW developer tools

### Version 0.1.1 &mdash; release candidate
[![GitHub tag](https://img.shields.io/github/tag/MODFLOW-USGS/modflow-devtools.svg)](https://github.com/MODFLOW-USGS/modflow-devtools/tags/latest)
[![PyPI Version](https://img.shields.io/pypi/v/modflow-devtools.png)](https://pypi.python.org/pypi/modflow-devtools)
[![PyPI Versions](https://img.shields.io/pypi/pyversions/modflow-devtools.png)](https://pypi.python.org/pypi/modflow-devtools)
[![PyPI Status](https://img.shields.io/pypi/status/modflow-devtools.png)](https://pypi.python.org/pypi/modflow-devtools)
[![CI](https://github.com/MODFLOW-USGS/modflow-devtools/actions/workflows/ci.yml/badge.svg)](https://github.com/MODFLOW-USGS/modflow-devtools/actions/workflows/ci.yml)
[![Documentation Status](https://readthedocs.org/projects/modflow-devtools/badge/?version=latest)](https://modflow-devtools.readthedocs.io/en/latest/?badge=latest)

Python tools for MODFLOW development and testing.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Requirements](#requirements)
- [Installation](#installation)
- [Use cases](#use-cases)
- [Documentation](#documentation)
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

## Use cases

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

## Documentation

Usage documentation is available at [modflow-devtools.readthedocs.io](https://modflow-devtools.readthedocs.io/en/latest/).

## MODFLOW Resources

+ [MODFLOW and Related Programs](https://water.usgs.gov/ogw/modflow/)
+ [Online guide for MODFLOW-2000](https://water.usgs.gov/nrp/gwsoftware/modflow2000/Guide/)
+ [Online guide for MODFLOW-2005](https://water.usgs.gov/ogw/modflow/MODFLOW-2005-Guide/)
+ [Online guide for MODFLOW-NWT](https://water.usgs.gov/ogw/modflow-nwt/MODFLOW-NWT-Guide/)
