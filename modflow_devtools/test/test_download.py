from os import environ
from typing import List

import pytest
from conftest import get_github_user
from flaky import flaky
from modflow_devtools.download import (
    download_and_unzip,
    download_artifact,
    get_release,
    get_releases,
    list_artifacts,
)
from modflow_devtools.markers import requires_github


def get_repos(user):
    return [
        user + "/" + repo
        for repo in ["modflow6", "modflow6-nightly-build", "executables"]
    ]


@pytest.fixture
def repos(github_user) -> List[str]:
    return get_repos(github_user)


_github_user = get_github_user()
_repos = get_repos(_github_user)


@pytest.mark.parametrize("per_page", [-1, 0, 1.5, 101, 1000])
@pytest.mark.parametrize("retries", [-1, 0, 1.5])
def test_get_releases_bad_params(per_page, retries):
    with pytest.raises(ValueError):
        get_releases(
            "executables", per_page=per_page, retries=retries, verbose=True
        )


@flaky
@requires_github
@pytest.mark.parametrize("repo", _repos)
def test_get_releases(repo):
    releases = get_releases(repo, verbose=True)
    assert any(releases)
    assert all("created_at" in r for r in releases)

    assets = [a for aa in [r["assets"] for r in releases] for a in aa]
    assert all(repo in a["browser_download_url"] for a in assets)


@flaky
@requires_github
@pytest.mark.parametrize("github_repo", _repos)
def test_get_release(github_repo, github_user):
    tag = "latest"
    release = get_release(github_repo, tag, verbose=True)
    assets = release["assets"]
    expected_names = ["linux.zip", "mac.zip", "win64.zip"]
    expected_ostags = [a.replace(".zip", "") for a in expected_names]
    actual_names = [asset["name"] for asset in assets]

    if github_repo == f"{github_user}/modflow6":
        # can remove if modflow6 releases follow asset name conventions followed in executables and nightly build repos
        assert set([a.rpartition("_")[2] for a in actual_names]) >= set(
            [a for a in expected_names if not a.startswith("win")]
        )
    else:
        for ostag in expected_ostags:
            assert any(
                ostag in a for a in actual_names
            ), f"dist not found for {ostag}"


@flaky
@requires_github
@pytest.mark.parametrize("name", [None, "rtd-files", "run-time-comparison"])
@pytest.mark.parametrize("per_page", [None, 100])
def test_list_artifacts(github_user, name, per_page):
    artifacts = list_artifacts(
        f"{github_user}/modflow6",
        name=name,
        per_page=per_page,
        max_pages=2,
        verbose=True,
    )

    if any(artifacts) and name:
        assert all(name == a["name"] for a in artifacts)


@flaky
@requires_github
@pytest.mark.parametrize("delete_zip", [True, False])
def test_download_artifact(github_user, function_tmpdir, delete_zip):
    repo = f"{github_user}/modflow6"
    artifacts = list_artifacts(repo, max_pages=1, verbose=True)
    first = next(iter(artifacts), None)

    if not first:
        pytest.skip(f"No artifacts found for repo: {repo}")

    artifact_id = first["id"]
    download_artifact(
        repo=repo,
        id=artifact_id,
        path=function_tmpdir,
        delete_zip=delete_zip,
        verbose=False,
    )

    assert len(list(function_tmpdir.rglob("*"))) >= (0 if delete_zip else 1)
    assert any(list(function_tmpdir.rglob("*.zip"))) != delete_zip


@flaky
@requires_github
@pytest.mark.parametrize("delete_zip", [True, False])
def test_download_and_unzip(github_user, function_tmpdir, delete_zip):
    github_user = "MODFLOW-USGS"  # comment to use releases on a fork
    version = "6.3.0"
    ostag = "linux"
    zip_name = f"mf{version}_{ostag}.zip"
    dir_name = zip_name.replace(".zip", "")
    url = f"https://github.com/{github_user}/modflow6/releases/download/{version}/{zip_name}"
    download_and_unzip(
        url, function_tmpdir, delete_zip=delete_zip, verbose=True
    )
    assert (function_tmpdir / zip_name).is_file() != delete_zip

    dir_path = function_tmpdir / dir_name
    assert dir_path.is_dir()

    contents = list(dir_path.rglob("*"))
    assert len(contents) > 0
