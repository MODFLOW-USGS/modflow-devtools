# Web utilities 

Some utility functions are provided for common web requests. Most use the GitHub API to query information or download artifacts and assets. See this project's test cases (in particular `test_download.py`) for detailed usage examples.

**Note:** to avoid GitHub API rate limits when using these functions, it is recommended to set the `GITHUB_TOKEN` environment variable. If this variable is set, the token will be borne on requests sent to the API.

## Queries

The following functions ask the GitHub API for information about a repository. The singular functions generally return a dictionary, while the plural functions return a list of dictionaries, with dictionary contents parsed directly from the API response's JSON. The first parameter of each function is `repo`, a string whose format must be `owner/name`, as appearing in GitHub URLs.

For instance, to retrieve information about the latest executables release, then manually inspect available assets:

```python
from modflow_devtools.download import get_release

release = get_release("MODFLOW-USGS/executables")
assets = release["assets"]
print([asset["name"] for asset in assets])
```

This yields `['code.json', 'linux.zip', 'mac.zip', 'win64.zip']`.

Equivalently, using the `get_release_assets()` function to list the latest release assets directly:

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

## Downloads

The `download_artifact` function downloads and unzips the GitHub Actions artifact with the given ID to the given path, optionally deleting the zipfile afterwards. The `repo` format is `owner/name`, as in GitHub URLs. For instance:

```python
from modflow_devtools.download import list_artifacts, download_artifact

repo = "MODFLOW-USGS/modflow6"
artifacts = list_artifacts(repo, max_pages=1, verbose=True)
artifact = next(iter(artifacts), None)
if artifact:
    download_artifact(
        repo=repo,
        id=artifact["id"],
        path=function_tmpdir,
        delete_zip=False,
        verbose=False,
    )
```

The `download_and_unzip` function is a more generic alternative for downloading and unzipping files from arbitrary URLs.

For instance, to download a MODFLOW 6.4.1 Linux distribution and delete the zipfile after extracting:

```python
from modflow_devtools.download import download_and_unzip

url = f"https://github.com/MODFLOW-USGS/modflow6/releases/download/6.4.1/mf6.4.1_linux.zip"
download_and_unzip(url, "~/Downloads", delete_zip=True, verbose=True)
```

The function's return value is the `Path` the archive was extracted to.