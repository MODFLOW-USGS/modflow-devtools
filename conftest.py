from os import environ

import pytest

pytest_plugins = ["modflow_devtools.fixtures"]


def get_github_user():
    user = environ.get("GITHUB_USER", None)
    return user


@pytest.fixture
def github_user() -> str:
    user = get_github_user()
    if not user:
        pytest.skip(reason="GITHUB_USER required")
    return user
