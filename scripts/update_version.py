import argparse
import sys
import textwrap
from datetime import datetime
from pathlib import Path

from filelock import FileLock
from packaging.version import Version

_project_name = "modflow-devtools"
_project_root_path = Path(__file__).parent.parent
_version_txt_path = _project_root_path / "version.txt"
_package_init_path = _project_root_path / "modflow_devtools" / "__init__.py"
_docs_config_path = _project_root_path / "docs" / "conf.py"
_current_version = Version(_version_txt_path.read_text().strip())


def release_version() -> Version:
    """The current development version with any development segment (e.g. '.dev0') removed."""
    return Version(_current_version.base_version)


def post_release_version() -> Version:
    """Development version for the next cycle, following a release.

    Targets the next anticipated minor version, with the development segment
    set to the micro (patch) number of the version just released: e.g. after
    1.9.2 comes 1.10.0.dev2, and after 1.11.0 comes 1.12.0.dev0. The counter
    marks how many releases into the series development has resumed.
    """
    version = Version(_current_version.base_version)
    return Version(f"{version.major}.{version.minor + 1}.0.dev{version.micro}")


def update_version_txt(version: Version):
    _version_txt_path.write_text(str(version))
    print(f"Updated {_version_txt_path} to version {version}", file=sys.stderr)


def update_init_py(timestamp: datetime, version: Version):
    lines = []
    for line in _package_init_path.read_text().splitlines():
        if "__date__" in line:
            line = f'__date__ = "{timestamp:%b %d, %Y}"'
        if "__version__" in line:
            line = f'__version__ = "{version}"'
        lines.append(line)
    _package_init_path.write_text("\n".join(lines) + "\n")
    print(f"Updated {_package_init_path} to version {version}", file=sys.stderr)


def update_docs_config(version: Version):
    lines = []
    for line in _docs_config_path.read_text().splitlines():
        if "release = " in line:
            line = f'release = "{version}"'
        lines.append(line)
    _docs_config_path.write_text("\n".join(lines) + "\n")
    print(f"Updated {_docs_config_path} to version {version}", file=sys.stderr)


def update_version(
    timestamp: datetime = datetime.now(),
    version: Version | None = None,
):
    lock_path = _version_txt_path.parent / (_version_txt_path.name + ".lock")
    lock = FileLock(lock_path)
    with lock:
        previous = Version(_version_txt_path.read_text().strip())
        version = (
            version if version else Version(f"{previous.major}.{previous.minor}.{previous.micro}")
        )

        update_version_txt(version)
        update_init_py(timestamp, version)
        update_docs_config(version)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog=f"Update {_project_name} version",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Update version information stored in version.txt in the project root,
            as well as several other files in the repository, and print the new
            version. If none of --version, --release or --post-release is
            provided, the version number is not changed. A file lock is held to
            synchronize file access. The version tag must comply with standard
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
        "-r",
        "--release",
        required=False,
        action="store_true",
        help=(
            "Use the current development version with its development segment "
            "(e.g. '.dev0') removed"
        ),
    )
    parser.add_argument(
        "-p",
        "--post-release",
        required=False,
        action="store_true",
        help=(
            "Use the development version for the next cycle: the next minor "
            "version, with a development segment set to the released patch number"
        ),
    )
    parser.add_argument(
        "--dry-run",
        required=False,
        action="store_true",
        help="Print the version that would be written, and exit without writing",
    )
    args = parser.parse_args()

    if args.post_release:
        version = post_release_version()
    elif args.release:
        version = release_version()
    elif args.version:
        version = Version(args.version)
    else:
        version = _current_version

    if not args.dry_run:
        update_version(timestamp=datetime.now(), version=version)
    print(version)
