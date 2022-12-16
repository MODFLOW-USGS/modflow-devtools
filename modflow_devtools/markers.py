from platform import system

import pytest
from modflow_devtools.misc import (
    get_current_branch,
    has_exe,
    has_pkg,
    is_connected,
    is_in_ci,
)


def requires_exe(*exes):
    missing = {exe for exe in exes if not has_exe(exe)}
    return pytest.mark.skipif(
        missing,
        reason=f"missing executable{'s' if len(missing) != 1 else ''}: "
        + ", ".join(missing),
    )


def requires_pkg(*pkgs):
    missing = {pkg for pkg in pkgs if not has_pkg(pkg)}
    return pytest.mark.skipif(
        missing,
        reason=f"missing package{'s' if len(missing) != 1 else ''}: "
        + ", ".join(missing),
    )


def requires_platform(platform, ci_only=False):
    return pytest.mark.skipif(
        system().lower() != platform.lower()
        and (is_in_ci() if ci_only else True),
        reason=f"only compatible with platform: {platform.lower()}",
    )


def excludes_platform(platform, ci_only=False):
    return pytest.mark.skipif(
        system().lower() == platform.lower()
        and (is_in_ci() if ci_only else True),
        reason=f"not compatible with platform: {platform.lower()}",
    )


def requires_branch(branch):
    current = get_current_branch()
    return pytest.mark.skipif(
        current != branch, reason=f"must run on branch: {branch}"
    )


def excludes_branch(branch):
    current = get_current_branch()
    return pytest.mark.skipif(
        current == branch, reason=f"can't run on branch: {branch}"
    )


requires_github = pytest.mark.skipif(
    not is_connected("github.com"), reason="github.com is required."
)


requires_spatial_reference = pytest.mark.skipif(
    not is_connected("spatialreference.org"),
    reason="spatialreference.org is required.",
)
