# Releasing Python packages

This repository provides a [reusable GitHub Actions workflow](https://docs.github.com/en/actions/using-workflows/reusing-workflows) for EC-related Python packages. This workflow is used by the `modflow-devtools` project itself, and can be used by other projects provided a few requirements are met.

## Requirements

1. Trusted publishing

The release workflow assumes the consuming repository is configured for [trusted publishing](https://docs.pypi.org/trusted-publishers/) to PyPI. As such, PyPI credentials need not be stored as repo secrets. Note that trusted publishing requires a [deployment environment](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment) named `pypi`. The environment may be empty.

2. Conventional commits

The workflow automatically generates a changelog for each release with [`git-cliff`](https://github.com/orhun/git-cliff). By default, this requires [conventional commits](https://www.conventionalcommits.org/en/about/). Custom [configuration](https://git-cliff.org/docs/configuration) may be provided to include unconventional commits in the changelog, but this leads to a less readable project history and is not recommended. By default, `git-cliff` configuration is expected in a `cliff.toml` file in the project root. A different file path/name (relative to the project root) may be provided with the `cliff_config` input.

3. Cumulative changelog

The workflow reserves the right to prepend each release's changelog to a version-controlled cumulative changelog file. By default, this is `HISTORY.md` in the project root. An alternative file path/name (relative to the project root) may be specified with the `cumulative_changelog` input.

4. Organization permissions

The organization to which a consuming repository belongs [must permit public reusable workflows](https://docs.github.com/en/actions/using-workflows/reusing-workflows#access-to-reusable-workflows).

5. Release branch naming

The release workflow is triggered when a release branch is pushed to the repository. The branch name *must* follow format `v{major}.{minor}.{patch}` ([semantic version](https://semver.org/) number with a leading 'v').

## Usage

Reusable workflows are [called directly from jobs](https://docs.github.com/en/actions/using-workflows/reusing-workflows#calling-a-reusable-workflow) rather than from steps within a job. For instance, to call the release workflow from a workflow in a repository containing a Python package named `mypackage` which should be built with Python 3.9, add a workflow like the following:

```yaml
name: Release
on:
  push:
    branches:
      # initial trigger on semver branch with leading 'v'
      - v[0-9]+.[0-9]+.[0-9]+*
      # second phase trigger after merging to trunk
      - main  # substitute 'master' if needed
  release:
    types:
      # third phase trigger after release is published
      - published
jobs:
  release:
    uses: MODFLOW-USGS/modflow-devtools/.github/workflows/reusable_release.yml@main
    with:
      package_name: mypackage
      python_version: 3.9
      trunk_branch: master
```