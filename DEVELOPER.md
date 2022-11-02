# Developing `modflow-devtools`

This document provides guidance to set up a development environment and discusses conventions used in this project.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Installation](#installation)
- [Testing](#testing)
  - [Running the tests](#running-the-tests)
  - [Writing new tests](#writing-new-tests)
    - [Temporary directories](#temporary-directories)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Installation

To get started, first fork and clone this repository. Then install the project and core packages as well as linting and testing dependencies:

```shell
pip install .
pip install ".[lint, test]"
```

## Testing

This repository's tests use [`pytest`](https://docs.pytest.org/en/latest/) and several plugins.

### Running the tests

Tests should be run from the project root. To run the tests in parallel with verbose output:

```shell
pytest -v -n auto
```

### Writing new tests

Tests should follow a few conventions for ease of use and maintenance.

#### Temporary directories

Tests which must write to disk should use `pytest`'s built-in `temp_dir` fixture or one of the scoped temporary directory fixtures defined in `conftest.py` (the latter are part of this package's public API and so are tested in `modflow_devtools/test/test_conftest.py`).
