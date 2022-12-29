import importlib
import socket
import sys
from contextlib import contextmanager
from os import PathLike, chdir, environ, getcwd
from os.path import basename, normpath
from pathlib import Path
from shutil import which
from subprocess import PIPE, Popen
from typing import List, Optional, Tuple
from urllib import request

import pkg_resources
from _warnings import warn


@contextmanager
def set_dir(path: PathLike):
    origin = Path(getcwd()).absolute()
    wrkdir = Path(path).expanduser().absolute()

    try:
        chdir(path)
        print(f"Changed to working directory: {wrkdir} (previously: {origin})")
        yield
    finally:
        chdir(origin)
        print(f"Returned to previous directory: {origin}")


class add_sys_path:
    """
    Context manager for temporarily editing the system path
    (https://stackoverflow.com/a/39855753/6514033)
    """

    def __init__(self, path):
        self.path = path

    def __enter__(self):
        sys.path.insert(0, self.path)

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            sys.path.remove(self.path)
        except ValueError:
            pass


def get_ostag() -> str:
    """Determine operating system tag from sys.platform."""
    if sys.platform.startswith("linux"):
        return "linux"
    elif sys.platform.startswith("win"):
        return "win" + ("64" if sys.maxsize > 2**32 else "32")
    elif sys.platform.startswith("darwin"):
        return "mac"
    raise ValueError(f"platform {sys.platform!r} not supported")


def get_suffixes(ostag) -> Tuple[str, str]:
    """Returns executable and library suffixes for the given OS (as returned by sys.platform)"""

    tag = ostag.lower()

    if tag in ["win32", "win64"]:
        return ".exe", ".dll"
    elif tag == "linux":
        return "", ".so"
    elif tag == "mac" or tag == "darwin":
        return "", ".dylib"
    else:
        raise KeyError(f"unrecognized OS tag: {ostag!r}")


def run_cmd(*args, verbose=False, **kwargs):
    """
    Run any command, return tuple (stdout, stderr, returncode).

    Originally written by Mike Toews (mwtoews@gmail.com) for FloPy.
    """
    args = [str(g) for g in args]
    if verbose:
        print("running: " + " ".join(args))
    p = Popen(args, stdout=PIPE, stderr=PIPE, **kwargs)
    stdout, stderr = p.communicate()
    stdout = stdout.decode()
    stderr = stderr.decode()
    returncode = p.returncode
    if verbose:
        print(f"stdout:\n{stdout}")
        print(f"stderr:\n{stderr}")
        print(f"returncode: {returncode}")
    return stdout, stderr, returncode


def run_py_script(script, *args, verbose=False):
    """Run a Python script, return tuple (stdout, stderr, returncode)."""
    return run_cmd(
        sys.executable, script, *args, verbose=verbose, cwd=Path(script).parent
    )


def get_current_branch() -> str:
    # check if on GitHub Actions CI
    ref = environ.get("GITHUB_REF")
    if ref is not None:
        return basename(normpath(ref)).lower()

    # otherwise ask git about it
    if not which("git"):
        raise RuntimeError("'git' required to determine current branch")
    stdout, stderr, code = run_cmd("git", "rev-parse", "--abbrev-ref", "HEAD")
    if code == 0 and stdout:
        return stdout.strip().lower()
    raise ValueError(f"Could not determine current branch: {stderr}")


def get_packages(namefile_path: PathLike) -> List[str]:
    """
    Return a list of packages used by the model defined in the given namefile.

    Parameters
    ----------
    namefile_path : PathLike
        path to MODFLOW 6 name file
    Returns
    -------
        list of package types
    """
    with open(namefile_path, "r") as f:
        lines = f.readlines()

    ftypes = []
    for line in lines:
        # Skip over blank and commented lines
        ll = line.strip().split()
        if len(ll) < 2:
            continue

        l = ll[0].lower()
        if any(l.startswith(c) for c in ["#", "!", "data", "list"]) or l in [
            "begin",
            "end",
            "memory_print_option",
        ]:
            continue

        # strip "6" from package name
        l = l.replace("6", "")

        ftypes.append(l.lower())

    return list(set(ftypes))


def has_package(namefile_path: PathLike, package: str) -> bool:
    """Determines whether the model with the given namefile contains the selected package"""
    packages = get_packages(namefile_path)
    return package.lower in packages


def get_namefile_paths(
    path: PathLike,
    prefix: str = None,
    namefile: str = "mfsim.nam",
    excluded=None,
    selected=None,
    packages=None,
):
    """
    Find namefiles recursively in the given location.
    Namefiles can be filtered or excluded by pattern,
    by parent directory name prefix or pattern, or by
    packages used.
    """

    # if path doesn't exist, return empty list
    if not Path(path).is_dir():
        return []

    # find namefiles
    paths = [
        p
        for p in Path(path).rglob(
            f"{prefix}*/**/{namefile}" if prefix else namefile
        )
    ]

    # remove excluded
    paths = [
        p
        for p in paths
        if (not excluded or not any(e in str(p) for e in excluded))
    ]

    # filter by package
    if packages:
        filtered = []
        for nfp in paths:
            nf_pkgs = get_packages(nfp)
            shared = set(nf_pkgs).intersection(
                set([p.lower() for p in packages])
            )
            if any(shared):
                filtered.append(nfp)
        paths = filtered

    # filter by model name
    if selected:
        paths = [
            namfile_path
            for (namfile_path, model_path) in zip(
                paths, [p.parent for p in paths]
            )
            if any(s in model_path.name for s in selected)
        ]

    return sorted(paths)


def get_model_dir_paths(
    path: PathLike,
    prefix: str = None,
    namefile: str = "mfsim.nam",
    excluded=None,
    selected=None,
    packages=None,
) -> List[Path]:
    """
    Find model directories recursively in the given location.
    A model directory is any directory containing one or more
    namefiles. Model directories can be filtered or excluded,
    by prefix, pattern, namefile name, or packages used.
    """

    namefile_paths = get_namefile_paths(
        path, prefix, namefile, excluded, selected, packages
    )
    model_paths = sorted(
        list(set([p.parent for p in namefile_paths if p.parent.name]))
    )
    return model_paths


def is_connected(hostname):
    """
    Tests whether the given URL is accessible.
    See https://stackoverflow.com/a/20913928/."""
    try:
        host = socket.gethostbyname(hostname)
        s = socket.create_connection((host, 80), 2)
        s.close()
        return True
    except Exception:
        pass
    return False


def is_in_ci():
    """Determines whether the current process is running GitHub Actions CI"""

    # if running in GitHub Actions CI, "CI" variable always set to true
    # https://docs.github.com/en/actions/learn-github-actions/environment-variables#default-environment-variables
    return bool(environ.get("CI", None))


def is_github_rate_limited() -> Optional[bool]:
    """
    Determines if a GitHub API rate limit is applied to the current IP.
    Running this function will consume an API request!

    Returns
    -------
        True if rate-limiting is applied, otherwise False (or None if the connection fails).
    """
    try:
        with request.urlopen(
            "https://api.github.com/users/octocat"
        ) as response:
            remaining = int(response.headers["x-ratelimit-remaining"])
            if remaining < 10:
                warn(
                    f"Only {remaining} GitHub API requests remaining before rate-limiting"
                )
            return remaining > 0
    except:
        return None


_has_exe_cache = {}
_has_pkg_cache = {}


def has_exe(exe):
    """
    Determines if the given executable is available on the path.

    Originally written by Mike Toews (mwtoews@gmail.com) for FloPy.
    """
    if exe not in _has_exe_cache:
        _has_exe_cache[exe] = bool(which(exe))
    return _has_exe_cache[exe]


def has_pkg(pkg):
    """
    Determines if the given Python package is installed.

    Originally written by Mike Toews (mwtoews@gmail.com) for FloPy.
    """
    if pkg not in _has_pkg_cache:

        # for some dependencies, package name and import name are different
        # (e.g. pyshp/shapefile, mfpymake/pymake, python-dateutil/dateutil)
        # pkg_resources expects package name, importlib expects import name
        try:
            _has_pkg_cache[pkg] = bool(importlib.import_module(pkg))
        except (ImportError, ModuleNotFoundError):
            try:
                _has_pkg_cache[pkg] = bool(pkg_resources.get_distribution(pkg))
            except pkg_resources.DistributionNotFound:
                _has_pkg_cache[pkg] = False

    return _has_pkg_cache[pkg]
