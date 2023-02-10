# Downloads

Some utility functions are provided to query information and download artifacts and assets from the GitHub API. These are available in the `modflow_devtools.download` module and are briefly described below. See this project's test cases (in particular `test_download.py`) for more usage examples.

**Note:** to avoid GitHub API rate limits when using these functions, it is recommended to set the `GITHUB_TOKEN` environment variable. If this variable is set, the token will be borne on requests sent to the API.

## Retrieving information

The following functions ask the GitHub API for information about a repository. The singular functions generally return a dictionary, while the plural functions return a list of dictionaries, with dictionary contents parsed directly from the API response's JSON.

- `get_releases(repo, per_page=30, max_pages=10, retries=3, verbose=False)`
- `get_release(repo, tag="latest", retries=3, verbose=False)`
- `get_release_assets(repo, tag="latest", simple=False, retries=3, verbose=False)`
- `list_artifacts(repo, name, per_page=None, max_pages=None, verbose=False)`

The `repo` parameter's format is `owner/name`, as in GitHub URLs.

For instance, to retrieve information about the latest executables release, then manually inspect available assets:

```python
from modflow_devtools.download import get_release

release = get_release("MODFLOW-USGS/executables")
assets = release["assets"]
print([asset["name"] for asset in assets])
```

This yields `['code.json', 'linux.zip', 'mac.zip', 'win64.zip']`.

Equivalently, using the `list_release_assets()` function to list the latest release assets directly:

```python
from modflow_devtools.download import get_release_assets

assets = get_release_assets("MODFLOW-USGS/executables")
print([asset["name"] for asset in assets])
```

The `simple` parameter, defaulting to `False`, can be toggled to return a simple dictionary mapping asset names to download URLs:

```python
from pprint import pprint

assets = get_release_assets("MODFLOW-USGS/executables", simple=True)
pprint(assets)
```

This prints:

```
{'code.json': 'https://github.com/MODFLOW-USGS/executables/releases/download/12.0/code.json',
 'linux.zip': 'https://github.com/MODFLOW-USGS/executables/releases/download/12.0/linux.zip',
 'mac.zip': 'https://github.com/MODFLOW-USGS/executables/releases/download/12.0/mac.zip',
 'win64.zip': 'https://github.com/MODFLOW-USGS/executables/releases/download/12.0/win64.zip'}
```

## Downloading assets

The `download_artifact(repo, id, path=None, delete_zip=True, verbose=False)` function downloads and unzips the GitHub Actions artifact with the given ID to the given path, optionally deleting the zipfile afterwards. The `repo` format is `owner/name`, as in GitHub URLs.

The `download_and_unzip(url, path=None, delete_zip=True, verbose=False)` function is a more generic alternative for downloading and unzipping files from arbitrary URLs.

For instance, to download a MODFLOW 6.4.1 Linux distribution and delete the zipfile after extracting:

```python
from modflow_devtools.download import download_and_unzip

url = f"https://github.com/MODFLOW-USGS/modflow6/releases/download/6.4.1/mf6.4.1_linux.zip"
download_and_unzip(url, "~/Downloads", delete_zip=True, verbose=True)
```
