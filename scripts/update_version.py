import argparse
import textwrap
from datetime import datetime
from enum import Enum
from os import PathLike
from pathlib import Path
from typing import NamedTuple

from filelock import FileLock

_project_name = "modflow-devtools"
_project_root_path = Path(__file__).parent.parent
_version_txt_path = _project_root_path / "version.txt"
_package_init_path = _project_root_path / "modflow_devtools" / "__init__.py"
_readme_path = _project_root_path / "README.md"
_docs_config_path = _project_root_path / "docs" / "conf.py"


class Version(NamedTuple):
    """Semantic version number"""

    major: int = 0
    minor: int = 0
    patch: int = 0

    def __repr__(self):
        return f"{self.major}.{self.minor}.{self.patch}"

    @classmethod
    def from_string(cls, version: str) -> "Version":
        t = version.split(".")

        vmajor = int(t[0])
        vminor = int(t[1])
        vpatch = int(t[2])

        return cls(major=vmajor, minor=vminor, patch=vpatch)

    @classmethod
    def from_file(cls, path: PathLike) -> "Version":
        lines = [
            line.rstrip("\n")
            for line in open(Path(path).expanduser().absolute(), "r")
        ]
        vmajor = vminor = vpatch = None
        for line in lines:
            line = line.strip()
            if not any(line):
                continue
            t = line.split(".")
            vmajor = int(t[0])
            vminor = int(t[1])
            vpatch = int(t[2])

        assert (
            vmajor is not None and vminor is not None and vpatch is not None
        ), "version string must follow semantic version format: major.minor.patch"
        return cls(major=vmajor, minor=vminor, patch=vpatch)


class ReleaseType(Enum):
    CANDIDATE = "Release Candidate"
    APPROVED = "Production"


_initial_version = Version(0, 0, 1)
_current_version = Version.from_file(_version_txt_path)


def update_version_txt(
    release_type: ReleaseType, timestamp: datetime, version: Version
):
    with open(_version_txt_path, "w") as f:
        f.write(str(version))
    print(f"Updated {_version_txt_path} to version {version}")


def update_init_py(
    release_type: ReleaseType, timestamp: datetime, version: Version
):
    lines = _package_init_path.read_text().rstrip().split("\n")
    with open(_package_init_path, "w") as f:
        for line in lines:
            if "__date__" in line:
                line = f'__date__ = "{timestamp.strftime("%b %d, %Y")}"'
            if "__version__" in line:
                line = f'__version__ = "{version}"'
            f.write(f"{line}\n")
    print(f"Updated {_package_init_path} to version {version}")


def update_readme_markdown(
    release_type: ReleaseType, timestamp: datetime, version: Version
):
    # read README.md into memory
    lines = _readme_path.read_text().rstrip().split("\n")

    # rewrite README.md
    with open(_readme_path, "w") as f:
        for line in lines:
            if "### Version " in line:
                line = f"### Version {version}"
                if release_type != ReleaseType.APPROVED:
                    line += f" &mdash; {release_type.value.lower()}"

            f.write(f"{line}\n")

    print(f"Updated {_readme_path} to version {version}")


def update_docs_config(
    release_type: ReleaseType, timestamp: datetime, version: Version
):
    lines = _docs_config_path.read_text().rstrip().split("\n")
    with open(_docs_config_path, "w") as f:
        for line in lines:
            line = f"release = '{version}'" if "release = " in line else line
            f.write(f"{line}\n")

    print(f"Updated {_docs_config_path} to version {version}")


def update_version(
    release_type: ReleaseType,
    timestamp: datetime = datetime.now(),
    version: Version = None,
):
    lock_path = Path(_version_txt_path.name + ".lock")
    try:
        lock = FileLock(lock_path)
        previous = Version.from_file(_version_txt_path)
        version = (
            version
            if version
            else Version(previous.major, previous.minor, previous.patch)
        )

        with lock:
            update_version_txt(release_type, timestamp, version)
            update_init_py(release_type, timestamp, version)
            update_readme_markdown(release_type, timestamp, version)
            update_docs_config(release_type, timestamp, version)
    finally:
        try:
            lock_path.unlink()
        except:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog=f"Update {_project_name} version",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Update version information stored in version.txt in the project root,
            as well as several other files in the repository. If --version is not
            provided, the version number will not be changed. A file lock is held
            to synchronize file access. The version tag must comply with standard
            '<major>.<minor>.<patch>' format conventions for semantic versioning.
            """
        ),
    )
    parser.add_argument(
        "-v",
        "--version",
        required=False,
        help="Specify the release version",
    )
    parser.add_argument(
        "-a",
        "--approve",
        required=False,
        action="store_true",
        help="Indicate release is approved (defaults to false for preliminary/development distributions)",
    )
    parser.add_argument(
        "-g",
        "--get",
        required=False,
        action="store_true",
        help="Just get the current version number, don't update anything (defaults to false)",
    )
    args = parser.parse_args()

    if args.get:
        print(_current_version)
    else:
        update_version(
            release_type=ReleaseType.APPROVED
            if args.approve
            else ReleaseType.CANDIDATE,
            timestamp=datetime.now(),
            version=Version.from_string(args.version)
            if args.version
            else _current_version,
        )
