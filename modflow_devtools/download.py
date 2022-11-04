# pylint: disable=E1101

"""Utility functions to:

1. download and unzip software releases from the USGS and other organizations
   (triangle, MT3DMS).
2. download the latest MODFLOW-based applications and utilities for MacOS,
   Linux, and Windows from https://github.com/MODFLOW-USGS/executables
3. determine the latest version (GitHub tag) of a GitHub repository and a
   dictionary containing the file name and the link to a asset on
   contained in a github repository
4. compress all files in a list, files in a list of directories

"""
import os
import shutil
import sys
import tarfile
import timeit
import urllib.request
from os import PathLike
from pathlib import Path
from typing import Optional
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


class MFZipFile(ZipFile):
    """ZipFile file attributes are not being preserved. This class preserves
    file attributes as described on StackOverflow at
    https://stackoverflow.com/questions/39296101/python-zipfile-removes-execute-permissions-from-binaries

    """

    def extract(self, member, path=None, pwd=None):
        """

        Parameters
        ----------
        member : str
            individual file to extract. If member does not exist, all files
            are extracted.
        path : str
            directory path to extract file in a zip file (default is None,
            which results in files being extracted in the current directory)
        pwd : str
            zip file password (default is None)

        Returns
        -------
        ret_val : int
            return value indicating status of file extraction

        """
        if not isinstance(member, ZipInfo):
            member = self.getinfo(member)

        if path is None:
            path = os.getcwd()

        ret_val = self._extract_member(member, path, pwd)
        attr = member.external_attr >> 16
        if attr != 0:
            os.chmod(ret_val, attr)

        return ret_val

    def extractall(self, path=None, members=None, pwd=None):
        """Extract all files in the zipfile.

        Parameters
        ----------
        path : str
            directory path to extract files in a zip file (default is None,
            which results in files being extracted in the current directory)
        members : str
            individual files to extract (default is None, which extracts
            all members)
        pwd : str
            zip file password (default is None)

        Returns
        -------

        """
        if members is None:
            members = self.namelist()

        if path is None:
            path = os.getcwd()
        else:
            if hasattr(os, "fspath"):
                # introduced in python 3.6 and above
                path = os.fspath(path)

        for zipinfo in members:
            self.extract(zipinfo, path, pwd)

    @staticmethod
    def compressall(path, file_pths=None, dir_pths=None, patterns=None):
        """Compress selected files or files in selected directories.

        Parameters
        ----------
        path : str
            output zip file path
        file_pths : str or list of str
            file paths to include in the output zip file (default is None)
        dir_pths : str or list of str
            directory paths to include in the output zip file (default is None)
        patterns : str or list of str
            file patterns to include in the output zip file (default is None)

        Returns
        -------
        success : bool
            boolean indicating if the output zip file was created

        """

        # create an empty list
        if file_pths is None:
            file_pths = []
        # convert files to a list
        else:
            if isinstance(file_pths, str):
                file_pths = [file_pths]
            elif isinstance(file_pths, tuple):
                file_pths = list(file_pths)

        # remove directories from the file list
        if len(file_pths) > 0:
            file_pths = [e for e in file_pths if os.path.isfile(e)]

        # convert dirs to a list if a str (a tuple is allowed)
        if dir_pths is None:
            dir_pths = []
        else:
            if isinstance(dir_pths, str):
                dir_pths = [dir_pths]

        # convert find to a list if a str (a tuple is allowed)
        if patterns is not None:
            if isinstance(patterns, str):
                patterns = [patterns]

        # walk through dirs and add files to the list
        for dir_pth in dir_pths:
            for dirname, subdirs, files in os.walk(dir_pth):
                for filename in files:
                    fpth = os.path.join(dirname, filename)
                    # add the file if it does not exist in file_pths
                    if fpth not in file_pths:
                        file_pths.append(fpth)

        # remove file_paths that do not match the patterns
        if patterns is not None:
            tlist = []
            for file_pth in file_pths:
                if any(p in os.path.basename(file_pth) for p in patterns):
                    tlist.append(file_pth)
            file_pths = tlist

        # write the zipfile
        success = True
        if len(file_pths) > 0:
            zf = ZipFile(path, "w", ZIP_DEFLATED)

            # write files to zip file
            for file_pth in file_pths:
                arcname = os.path.basename(file_pth)
                zf.write(file_pth, arcname=arcname)

            # close the zip file
            zf.close()
        else:
            msg = "No files to add to the zip file"
            print(msg)
            success = False

        return success


def get_request(url, params={}):
    """
    Get urllib.request.Request, with parameters and headers.

    This bears a GitHub API authentication token if github.com is
    in the URL and the GITHUB_TOKEN environment variable is set.
    """
    if isinstance(params, dict):
        if len(params) > 0:
            url += "?" + urllib.parse.urlencode(params)
    else:
        raise TypeError("data must be a dict")
    headers = {}

    if "github.com" in url:
        github_token = os.environ.get("GITHUB_TOKEN", None)
        if github_token:
            headers["Authorization"] = f"Bearer {github_token}"

    return urllib.request.Request(url, headers=headers)


def download_and_unzip(
    url: str,
    path: Optional[PathLike] = None,
    delete_zip=True,
    verbose=False,
):
    """Download and unzip a zip file from a url.

    Parameters
    ----------
    url : str
        url address for the zip file
    path : PathLike
        path where the zip file will be saved (default is the current path)
    delete_zip : bool
        boolean indicating if the zip file should be deleted after it is
        unzipped (default is True)
    verbose : bool
        boolean indicating if output will be printed to the terminal

    Returns
    -------

    """

    path = Path(path if path else os.getcwd())
    path.mkdir(exist_ok=True)

    if verbose:
        print(f"Downloading {url}")

    # download the file
    success = False
    tic = timeit.default_timer()

    def report(chunk, size, total):
        complete = chunk * size
        percent = round(complete / total * 100)
        if verbose:
            print(f"{percent}% complete ({complete} bytes of {total})")

    # download zip file
    file_path = path / url.split("/")[-1]
    _, headers = urllib.request.urlretrieve(
        url, filename=str(file_path), reporthook=report
    )

    # get content length, if available
    tag = "Content-length"
    if tag in headers:
        file_size = headers[tag]
        len_file_size = len(file_size)
        file_size = int(file_size)

        bfmt = "{:" + f"{len_file_size}" + ",d}"
        sbfmt = "{:>" + f"{len(bfmt.format(int(file_size)))}" + "s} bytes"
        msg = f"   file size: {sbfmt.format(bfmt.format(int(file_size)))}"
        if verbose:
            print(msg)
    else:
        file_size = 0.0

    # write the total download time
    toc = timeit.default_timer()
    tsec = round(toc - tic, 2)
    if verbose:
        print(f"\ntotal download time: {tsec} seconds")

    # Unzip the file, and delete zip file if successful.
    if "zip" in file_path.suffix or "exe" in file_path.suffix:
        z = MFZipFile(file_path)
        try:
            if verbose:
                print(f"Uncompressing: {file_path}")

            # extract the files
            z.extractall(str(path))
        except:
            p = "Could not unzip the file. Stopping."
            raise Exception(p)
        z.close()
    elif "tar" in file_path.suffix:
        ar = tarfile.open(file_path)
        ar.extractall(path=str(path))
        ar.close()

    # delete the zipfile
    if delete_zip:
        if verbose:
            print(f"Deleting zipfile {file_path}")
        file_path.unlink()

    if verbose:
        print(f"Done downloading and extracting {file_path.name} to {path}")

    return success


def zip_all(path, file_pths=None, dir_pths=None, patterns=None):
    """Compress all files in the user-provided list of file paths and directory
    paths that match the provided file patterns.

    Parameters
    ----------
    path : str
        path of the zip file that will be created
    file_pths : str or list
        file path or list of file paths to be compressed
    dir_pths : str or list
        directory path or list of directory paths to search for files that
        will be compressed
    patterns : str or list
        file pattern or list of file patterns s to match to when creating a
        list of files that will be compressed

    Returns
    -------

    """
    return MFZipFile.compressall(
        path, file_pths=file_pths, dir_pths=dir_pths, patterns=patterns
    )


def _get_zipname(platform):
    """Determine zipfile name for platform.

    Parameters
    ----------
    platform : str
        Platform that will run the executables.  Valid values include mac,
        linux, win32 and win64.  If platform is None, then routine will
        download the latest asset from the github repository.

    Returns
    -------
    zipfile : str
        Name of zipfile for platform

    """
    if platform is None:
        if sys.platform.lower() == "darwin":
            platform = "mac"
        elif sys.platform.lower().startswith("linux"):
            platform = "linux"
        elif "win" in sys.platform.lower():
            is_64bits = sys.maxsize > 2**32
            if is_64bits:
                platform = "win64"
            else:
                platform = "win32"
        else:
            errmsg = (
                f"Could not determine platform. sys.platform is {sys.platform}"
            )
            raise Exception(errmsg)
    else:
        msg = f"unknown platform detected ({platform})"
        success = platform in ["mac", "linux", "win32", "win64"]
        if not success:
            raise ValueError(msg)
    return f"{platform}.zip"


def _get_default_repo():
    """Return the default repo name.

    Returns
    -------
    default_repo : str
        default github repository repo name

    """
    return "MODFLOW-USGS/executables"


def _get_default_url():
    """Return the default executables url path.

    Returns
    -------
    default_url : str
        default url for executables repository repo name

    """

    return (
        f"https://github.com/{_get_default_repo()}/"
        + "releases/latest/download/"
    )


def _get_default_json(tag_name=None):
    """Return a default github api json for the provided release tag_name in a
    github repository.

    Parameters
    ----------
    tag_name : str
        github repository release tag

    Returns
    -------
    json_obj : dict
        json object (dictionary) with a tag_name and assets including
        file names and download links

    """
    # initialize json_obj dictionary
    json_obj = {"tag_name": tag_name}

    # create appropriate url
    if tag_name is not None:
        url = (
            f"https://github.com/{_get_default_repo()}/"
            + f"releases/latest/download/{tag_name}/"
        )
    else:
        url = (
            f"https://github.com/{_get_default_repo()}/"
            + "releases/latest/download/"
        )

    # define asset names and paths for assets
    names = ["mac.zip", "linux.zip", "win32.zip", "win64.zip"]
    paths = [url + p for p in names]

    assets_list = []
    for name, path in zip(names, paths):
        assets_list.append({"name": name, "browser_download_url": path})
    json_obj["assets"] = assets_list

    return json_obj


def _get_request_json(request_url, verbose=False, verify=True):
    """Process a url request and return a json if successful.

    Parameters
    ----------
    request_url : str
        url for request
    verbose : bool
        boolean indicating if output will be printed to the terminal
        default is false
    verify : bool
        boolean indicating if the url request should be verified

    Returns
    -------
    success : bool
        boolean indicating if the requat failed
    status_code: integer
        request status code
    json_obj : dict
        json object

    """
    import json

    max_requests = 10
    json_obj = None
    success = True

    # open request
    req = _request_get(
        request_url, max_requests=max_requests, verbose=verbose, verify=verify
    )

    # connection established - retrieve the json
    if req.ok:
        json_obj = json.loads(req.text or req.content)
    else:
        success = req.status_code == requests.codes.ok

    return success, req, json_obj


def _repo_json(
    github_repo, tag_name=None, error_return=False, verbose=False, verify=True
):
    """Return the github api json for the latest github release in a github
    repository.

    Parameters
    ----------
    github_repo : str
        Repository name, such as MODFLOW-USGS/modflow6
    tag_name : str
        github repository release tag
    error_return : bool
        boolean indicating if None will be returned if there are GitHub API
        issues
    verbose : bool
        boolean indicating if output will be printed to the terminal
    verify : bool
        boolean indicating if the url request should be verified

    Returns
    -------
    json_obj : dict
        json object (dictionary) with a tag_name and assets including
        file names and download links

    """
    repo_url = f"https://api.github.com/repos/{github_repo}"

    if tag_name is None:
        request_url = f"{repo_url}/releases/latest"
    else:
        request_url = f"{repo_url}/releases"
        success, _, json_cat = _get_request_json(
            request_url, verbose=verbose, verify=verify
        )
        if success:
            request_url = None
            for release in json_cat:
                if release["tag_name"] == tag_name:
                    request_url = release["url"]
                    break
            if request_url is None:
                msg = (
                    f"Could not find tag_name ('{tag_name}') "
                    + "in release catalog"
                )
                if error_return:
                    print(msg)
                    return None
                else:
                    raise Exception(msg)
        else:
            msg = "Could not get release catalog from " + request_url
            if error_return:
                if verbose:
                    print(msg)
                return None
            else:
                raise Exception(msg)

    msg = "Requesting asset data "
    if tag_name is not None:
        msg += f"for tag_name '{tag_name}' "
    msg += f"from: {request_url}"
    if verbose:
        print(msg)

    # process the request
    success, req, json_obj = _get_request_json(
        request_url, verbose=verbose, verify=verify
    )

    # evaluate request errors
    if not success:
        if github_repo == _get_default_repo():
            msg = f"will use default values for {github_repo}"
            if verbose:
                print(msg)
            json_obj = _get_default_json(tag_name)
        else:
            msg = "Could not find json from " + request_url
            if verbose:
                print(msg)
            if error_return:
                json_obj = None
            else:
                req.raise_for_status()

    # return json object
    return json_obj


def get_repo_assets(
    github_repo=None, version=None, error_return=False, verify=True
):
    """Return a dictionary containing the file name and the link to the asset
    contained in a github repository.

    Parameters
    ----------
    github_repo : str
        Repository name, such as MODFLOW-USGS/modflow6. If github_repo is
        None set to 'MODFLOW-USGS/executables'
    version : str
        github repository release tag
    error_return : bool
        boolean indicating if None will be returned if there are GitHub API
        issues
    verify : bool
        boolean indicating if the url request should be verified

    Returns
    -------
    result_dict : dict
        dictionary of file names and links

    """
    if github_repo is None:
        github_repo = _get_default_repo()

    # get json and extract assets
    json_obj = _repo_json(
        github_repo, tag_name=version, error_return=error_return, verify=verify
    )
    if json_obj is None:
        result_dict = None
    else:
        assets = json_obj["assets"]

        # build simple assets dictionary
        result_dict = {}
        for asset in assets:
            k = asset["name"]
            if version is None:
                value = github_repo + f"/{k}"
            else:
                value = asset["browser_download_url"]
            result_dict[k] = value

    return result_dict


def repo_latest_version(github_repo=None, verify=True):
    """Return a string of the latest version number (tag) contained in a github
    repository release.

    Parameters
    ----------
    github_repo : str
        Repository name, such as MODFLOW-USGS/modflow6. If github_repo is
        None set to 'MODFLOW-USGS/executables'

    Returns
    -------
    version : str
        string with the latest version/tag number

    """
    if github_repo is None:
        github_repo = _get_default_repo()

    # get json
    json_obj = _repo_json(github_repo, verify=verify)

    return json_obj["tag_name"]


def getmfexes(
    pth=".",
    version=None,
    platform=None,
    exes=None,
    verbose=False,
    verify=True,
):
    """Get the latest MODFLOW binary executables from a github site
    (https://github.com/MODFLOW-USGS/executables) for the specified operating
    system and put them in the specified path.

    Parameters
    ----------
    pth : str
        Location to put the executables (default is current working directory)
    version : str
        Version of the MODFLOW-USGS/executables release to use. If version is
        None the github repo will be queried for the version number.
    platform : str
        Platform that will run the executables.  Valid values include mac,
        linux, win32 and win64.  If platform is None, then routine will
        download the latest asset from the github repository.
    exes : str or list of strings
        executable or list of executables to retain
    verbose : bool
        boolean indicating if output will be printed to the terminal
    verify : bool
        boolean indicating if the url request should be verified

    """
    # set download directory to path in case a selection of files
    download_dir = pth

    # Determine the platform in order to construct the zip file name
    zipname = _get_zipname(platform)

    # Evaluate exes keyword
    if exes is not None:
        download_dir = os.path.join(".", "download_dir")
        if isinstance(exes, str):
            exes = tuple(exes)
        elif isinstance(exes, (int, float)):
            msg = "exes keyword must be a string or a list/tuple of strings"
            raise TypeError(msg)

    # Determine path for file download and then download and unzip
    if version is None:
        download_url = _get_default_url() + zipname
    else:
        assets = get_repo_assets(
            github_repo=_get_default_repo(), version=version, verify=verify
        )
        download_url = assets[zipname]
    download_and_unzip(
        download_url,
        download_dir,
        verbose=verbose,
        verify=verify,
    )

    if exes is not None:
        # make sure pth exists
        if not os.path.exists(pth):
            if verbose:
                print(f"Creating the directory:\n    {pth}")
            os.makedirs(pth)

        # move select files to pth
        for f in os.listdir(download_dir):
            src = os.path.join(download_dir, f)
            dst = os.path.join(pth, f)
            for exe in exes:
                if exe in f:
                    shutil.move(src, dst)
                    break

        # remove the download directory
        if os.path.isdir(download_dir):
            if verbose:
                print("Removing folder " + download_dir)
            shutil.rmtree(download_dir)

    return


def getmfnightly(
    pth=".",
    platform=None,
    exes=None,
    verbose=False,
    verify=True,
):
    """Get the latest MODFLOW 6 binary nightly-build executables from github
    (https://github.com/MODFLOW-USGS/modflow6-nightly-build/) for the specified
    operating system and put them in the specified path.

    Parameters
    ----------
    pth : str
        Location to put the executables (default is current working directory)
    platform : str
        Platform that will run the executables.  Valid values include mac,
        linux, win32 and win64.  If platform is None, then routine will
        download the latest asset from the github repository.
    exes : str or list of strings
        executable or list of executables to retain
    verbose : bool
        boolean indicating if output will be printed to the terminal
    verify : bool
        boolean indicating if the url request should be verified

    """
    # set download directory to path in case a selection of files
    download_dir = pth

    # Determine the platform in order to construct the zip file name
    zipname = _get_zipname(platform)

    # Evaluate exes keyword
    if exes is not None:
        download_dir = os.path.join(".", "download_dir")
        if isinstance(exes, str):
            exes = tuple(exes)
        elif isinstance(exes, (int, float)):
            msg = "exes keyword must be a string or a list/tuple of strings"
            raise TypeError(msg)

    # Determine path for file download and then download and unzip
    # https://github.com/MODFLOW-USGS/modflow6-nightly-build/releases/latest/download/
    download_url = (
        "https://github.com/MODFLOW-USGS/"
        + "modflow6-nightly-build/releases/latest/download/"
        + zipname
    )
    download_and_unzip(
        download_url,
        download_dir,
        verbose=verbose,
        verify=verify,
    )

    if exes is not None:
        # make sure pth exists
        if not os.path.exists(pth):
            if verbose:
                print(f"Creating the directory:\n    {pth}")
            os.makedirs(pth)

        # move select files to pth
        for f in os.listdir(download_dir):
            src = os.path.join(download_dir, f)
            dst = os.path.join(pth, f)
            for exe in exes:
                if exe in f:
                    shutil.move(src, dst)
                    break

        # remove the download directory
        if os.path.isdir(download_dir):
            if verbose:
                print("Removing folder " + download_dir)
            shutil.rmtree(download_dir)
