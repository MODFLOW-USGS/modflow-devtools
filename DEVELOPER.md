# Developing `modflow-devtools`

This document provides guidance to set up a development environment and discusses conventions used in this project.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->


- [Requirements](#requirements)
- [Installation](#installation)
- [Testing](#testing)
  - [Environment variables](#environment-variables)
  - [Running the tests](#running-the-tests)
  - [Writing new tests](#writing-new-tests)
    - [Temporary directories](#temporary-directories)
- [Releasing](#releasing)
  - [1. Start the release](#1-start-the-release)
  - [2. Review and approve](#2-review-and-approve)
  - [3. Publish](#3-publish)
  - [4. conda-forge](#4-conda-forge)
  - [Changelog conventions](#changelog-conventions)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Requirements

Python3.11+. This project has historically aimed to support several recent versions of Python, loosely following [NEP 29](https://numpy.org/neps/nep-0029-deprecation_policy.html#implementation). In current and future development this window may narrow to follow [SPEC 0](https://scientific-python.org/specs/spec-0000/#support-window) instead.

## Installation

To get started, first fork and clone this repository. Then install the project in "editable" mode, along with all of the dependencies needed for running and development:

```shell
pip install -e . --group dev
```

Developers that use a `uv` environment can "sync" the project to install the project with all dependencies:

```shell
uv sync
```

## Testing

This repository's tests use [`pytest`](https://docs.pytest.org/en/latest/) and several plugins.

### Environment variables

This repository's tests expect a few environment variables:

- `REPOS_PATH`: the path to MODFLOW 6 example model repositories
- `GITHUB_TOKEN`: a GitHub authentication token

These may be set manually, but the recommended approach is to configure environment variables in a `.env` file in the project root, for instance:

```
REPOS_PATH=/path/to/repos
GITHUB_TOKEN=yourtoken...
```

The tests use [`pytest-dotenv`](https://github.com/quiqua/pytest-dotenv) to detect and load variables from this file.

### Running the tests

Tests should be run from the `autotest` directory. To run the tests in parallel with verbose output:

```shell
pytest -v -n auto
```

### Writing new tests

Tests follow a few conventions for ease of use and maintenance.

#### Temporary directories

Tests which must write to disk use `pytest`'s built-in `temp_dir` fixture or one of this package's own scoped temporary directory fixtures.

## Releasing

Releases are automated by [`.github/workflows/release.yml`](.github/workflows/release.yml).
Publishing to PyPI uses [trusted publishing](https://docs.pypi.org/trusted-publishers/), so no
API token is needed, but the repository must have a `release` environment configured.

> [!IMPORTANT]
> PyPI matches a trusted publisher on the organisation name, the repository name, the workflow
> filename and the environment name. Renaming any of them silently invalidates the publisher, and
> nothing reports it until the next release fails with `invalid-publisher`. This happened to
> `modflowapi` when the organisation was renamed from `MODFLOW-USGS` to `MODFLOW-ORG`, and went
> unnoticed for eighteen months until the next release. After any such rename, update the publisher
> at https://pypi.org/manage/project/modflow-devtools/settings/publishing/ to match.

### 1. Start the release

From the [Actions tab](https://github.com/MODFLOW-ORG/modflow-devtools/actions/workflows/release.yml),
select **Run workflow** and fill in the form:

| Input | Description |
|:--|:--|
| `branch` | Branch to release from. Defaults to `develop`. |
| `version` | Explicit version number, e.g. `1.9.3`. Defaults to the version in `version.txt` with its `.dev` suffix removed. |
| `run_tests` | Run the test suite before drafting the release. Defaults to true. |

This can also be done from the command line, for instance:

```shell
gh workflow run release.yml -f branch=develop
```

The release version is normally the development version already set in `version.txt` (e.g.
`1.10.0.dev0` releases as `1.10.0`); pass `version` only to release something else. The workflow
creates a `v<version>` release branch, updates the version number, regenerates the changelog with
[git-cliff](https://git-cliff.org/) and prepends it to `HISTORY.md`, runs the CI suite against the
branch, and opens a draft pull request into `main`.

A release can alternatively be started by pushing a release branch named `v<major>.<minor>.<patch>`.

### 2. Review and approve

Review the release pull request, in particular `HISTORY.md`. Mark it ready for review and merge it
into `main`. Merge rather than squash: squashing drops the commit history from `main` and makes
`develop` and `main` diverge, which causes later `main` updates to replay old release commits.

Merging into `main` drafts a GitHub release, with notes taken from the generated changelog.

### 3. Publish

Review the draft release and publish it. Publishing it triggers the job that builds the package
and uploads it to [PyPI](https://pypi.org/project/modflow-devtools).

Then reset `develop`: branch from `main`, set the next development version, and open a pull request
back into `develop`.

```shell
git switch main && git pull
git switch -c post-x.y.z-release-reset
python scripts/update_version.py --post-release
```

`--post-release` increments the minor version and adds a `.dev0` suffix; pass `-v x.y.z.dev0`
instead to set it explicitly.

Merge (do not squash) that pull request to finish the release.

### 4. conda-forge

A few hours after the upload to PyPI, a bot opens a version pull request on the
[feedstock](https://github.com/conda-forge/modflow-devtools-feedstock). To start it immediately
instead, open an issue there titled `@conda-forge-admin, please update version`.

> [!IMPORTANT]
> The bot updates the version number and the checksum, and nothing else. Check the recipe's `host`
> and `run` requirements against the dependencies the release actually declares, which are the
> `Requires-Dist` lines of the sdist on PyPI. A maintainer can push a correction to the bot's
> branch.

Merging the feedstock pull request builds and uploads the package. It does not appear to a solver
until the channel index is regenerated, which takes up to about an hour; the package is visible on
anaconda.org before then.

### Changelog conventions

Release notes are generated from commit messages with git-cliff, so commits reaching `develop`
should follow the [conventional commits](https://www.conventionalcommits.org/) format (`feat:`,
`fix:`, `refactor:`, etc.). Commits that do not follow the convention are omitted from the
changelog without warning. See [`cliff.toml`](cliff.toml) for the commit groups and which ones are
skipped.

Pull requests are squash merged, so the title becomes the commit message the notes are generated
from. Nothing enforces the format on the title, so a user facing change merged with a `chore:` (or
non-conventional) title is dropped from the notes silently. Read the generated changelog on the
release pull request before merging it; add anything missing there, in the section for the version
being cut.