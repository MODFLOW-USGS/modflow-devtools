# Downloads

Some utility functions are provided to query information and download artifacts and assets from the GitHub API. These are available in the `modflow_devtools.download` module.

**Note:** to avoid GitHub API rate limits when using these functions, it is recommended to set the `GITHUB_TOKEN` environment variable. If this variable is set, the token will automatically be borne on requests sent to the API.

## Retrieving information

The following functions ask the GitHub API for information about a repository. The singular functions return a dictionary, while the plural functions return a list of dictionaries, with dictionary contents parsed directly from the API response's JSON.

- `get_releases(repo, per_page=None, quiet=False)`
- `get_release(repo, tag="latest", quiet=False)`
- `list_release_assets(repo, tag="latest", quiet=False)`
- `list_artifacts(repo, name, per_page=None, max_pages=None, quiet=False)`

The `repo` parameter's format is `owner/name`, as in GitHub URLs.

For instance, to download information about a release and inspect available assets:

```python
from modflow_devtools.download import get_release

release = get_release("MODFLOW-USGS/executables")
assets = release["assets"]
expected_names = ["linux.zip", "mac.zip", "win64.zip"]
actual_names = [asset["name"] for asset in assets]
assert set(expected_names) == set(actual_names)
```

## Downloading assets

The `download_artifact(repo, id, path=None, delete_zip=True, quiet=False)` function downloads and unzips the GitHub Actions artifact with the given ID to the given path, optionally deleting the zipfile afterwards. The `repo` format is `owner/name`, as in GitHub URLs.

The `download_and_unzip(url, path=None, delete_zip=True, verbose=False)` function is a more generic alternative for downloading and unzipping files from arbitrary URLs.

For instance, to download a MODFLOW 6.3.0 Linux distribution and delete the zipfile after extracting:

```python
from modflow_devtools.download import download_and_unzip

url = f"https://github.com/MODFLOW-USGS/modflow6/releases/download/6.3.0/mf6.3.0_linux.zip"
download_and_unzip(url, "some/download/path", delete_zip=True, verbose=True)
```
