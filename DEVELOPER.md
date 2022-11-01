# Developing `modflow-devtools`

This document provides guidance to set up a development environment and discusses conventions used in this project.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Developing `modflow-devtools`](#developing-modflow-devtools)
  - [Installation](#installation)
  - [Testing](#testing)
    - [Environment variables](#environment-variables)
    - [Running the tests](#running-the-tests)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Installation

To get started, first fork and clone this repository.

## Testing

This project uses [`pytest`](https://docs.pytest.org/en/latest/) and several plugins. [`PyGithub`](https://github.com/PyGithub/PyGithub) is used to communicate with the GitHub API.

### Environment variables

#### `GITHUB_TOKEN`

Tests require access to the GitHub API &mdash; in order to avoid rate limits, the tests attempt to authenticate with an access token. In C, this is the `GITHUB_TOKEN` provided by GitHub Actions. For local development a personal access token must be used. Setting the `GITHUB_TOKEN` variable manually will work, but the recommended approach is to use a `.env` file in your project root (the tests will automatically discover and use any environment variables configured here courtesy of [`pytest-dotenv`](https://github.com/quiqua/pytest-dotenv)).

#### `MODFLOW6_PATH`

By default, ths project's tests look for the `modflow6` repository side-by-side with `modflow-devtools` on the filesystem. The `MODFLOW6_PATH` variable is optional and can be used to configure a different location for the `modflow6` repo.

### Running the tests

To run the tests in parallel with verbose output, run from the project root:

```shell
pytest -v -n auto
```

### Writing new tests

Tests should follow a few conventions for ease of use and maintenance.

#### Temporary directories

If tests must write to disk, they should use `pytest`'s built-in `temp_dir` fixture or one of the scoped temporary directory fixtures defined in `conftest.py`.

#### Using the GitHub API

To access the GitHub API from a test case, just construct a `Github` object:

```python
api = Github(environ.get("GITHUB_TOKEN"))
```