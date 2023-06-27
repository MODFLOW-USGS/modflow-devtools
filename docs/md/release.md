# Releasing Python packages

This repository provides a [reusable GitHub Actions workflow](https://docs.github.com/en/actions/using-workflows/reusing-workflows) for EC-related Python packages. This workflow is used by the `modflow-devtools` project itself, and can be used by other projects provided a few requirements are met.

## Overview

There are two reusable release workflows in this repository:

- `make_package.yml`: builds (and optionally tests) the Python package to be released
- `release.yml`: orchestrates optional release procedures after the package is built, including merging to trunk and back to `develop`, publishing to PyPI, creating a release post, and reinitializing the `develop` from trunk.

A third workflow, `release_dispatch.yml`, contains triggers to start the release procedure either on:

- manual dispatch from the GitHub UI or CLI
- push of a branch named `vx.y.z` or `vx.y.zrc`, where `x`, `y`, and `z` are semantic version numbers

## Requirements

A few assumptions are made about projects consuming the release workflows defined here.

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

Reusable workflows are [called directly from jobs](https://docs.github.com/en/actions/using-workflows/reusing-workflows#calling-a-reusable-workflow) rather than from steps within a job. For instance, to call the release workflow from a workflow in a repository containing a Python package named `mypackage` which should be built with Python 3.9:

```yaml
name: Release mypackage
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
  # configure options which may be set as dispatch
  # inputs or dynamically assigned default values
  set_options:
    name: Set release options
    if: github.ref_name != 'master'
    runs-on: ubuntu-22.04
    defaults:
      run:
        shell: bash -l {0}
    outputs:
      branch: ${{ steps.set_branch.outputs.branch }}
      version: ${{ steps.set_version.outputs.version }}
    steps:

      - name: Set branch
        id: set_branch
        run: |
          # if branch was provided explicitly via workflow_dispatch, use it
          if [[ ("${{ github.event_name }}" == "workflow_dispatch") && (-n "${{ inputs.branch }}") ]]; then
            branch="${{ inputs.branch }}"
            # prevent releases from develop or master
            if [[ ("$branch" == "develop") || ("$branch" == "master") ]]; then
              echo "error: releases may not be triggered from branch $branch"
              exit 1
            fi
            echo "using branch $branch from workflow_dispatch"
          elif [[ ("${{ github.event_name }}" == "push") && ("${{ github.ref_name }}" != "master") ]]; then
            # if release was triggered by pushing a release branch, use that branch
            branch="${{ github.ref_name }}"
            echo "using branch $branch from ref ${{ github.ref }}"
          else
            # otherwise exit with an error
            echo "error: this workflow should not have triggered for event ${{ github.event_name }} on branch ${{ github.ref_name }}"
            exit 1
          fi
          echo "branch=$branch" >> $GITHUB_OUTPUT

      - name: Set version
        id: set_version
        run: |
          # if version number was provided explicitly via workflow_dispatch, use it
          if [[ ("${{ github.event_name }}" == "workflow_dispatch") && (-n "${{ inputs.version }}") ]]; then
            ver="${{ inputs.version }}"
            echo "using version number $ver from workflow_dispatch"
          elif [[ ("${{ github.event_name }}" == "push") && ("${{ github.ref_name }}" != "master") ]]; then
            # if release was triggered by pushing a release branch, parse version number from branch name (sans leading 'v')
            ref="${{ github.ref_name }}"
            ver="${ref#"v"}"
            echo "parsed version number $ver from branch name $ref"
          else
            # otherwise exit with an error
            echo "error: version number not provided explicitly (via workflow_dispatch input) or implicitly (via branch name)"
            exit 1
          fi
          echo "version=$ver" >> $GITHUB_OUTPUT

  release:
    uses: MODFLOW-USGS/modflow-devtools/.github/workflows/release.yml@main
    with:
      branch: ${{ needs.set_options.outputs.branch }}
      draft_release: true
      package_name: mypackage
      publish_package: true
      python: '3.9'
      reset_develop: true
      run_tests: true
      trunk_branch: main  # substitute master if needed
      version: '0.1.2'
```