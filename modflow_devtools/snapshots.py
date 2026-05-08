import warnings
from io import BytesIO, StringIO
from pathlib import Path
from typing import Optional, Union

from modflow_devtools.imports import import_optional_dependency

np = import_optional_dependency("numpy")
pytest = import_optional_dependency("pytest")
syrupy = import_optional_dependency("syrupy")

# ruff: noqa: E402
from syrupy import __import_extension
from syrupy.assertion import SnapshotAssertion
from syrupy.extensions.single_file import (
    SingleFileSnapshotExtension,
    WriteMode,
)
from syrupy.location import PyTestLocation
from syrupy.types import (
    PropertyFilter,
    PropertyMatcher,
    SerializableData,
    SerializedData,
)

# extension classes


class BinaryArrayExtension(SingleFileSnapshotExtension):
    """
    Binary snapshot of a NumPy array. Can be read back into NumPy with
    .load(), preserving dtype and shape. This is the recommended array
    snapshot approach if human-readability is not a necessity, as disk
    space is minimized.
    """

    _write_mode = WriteMode.BINARY
    _file_extension = "npy"

    def serialize(
        self,
        data,
        *,
        exclude=None,
        include=None,
        matcher=None,
    ):
        buffer = BytesIO()
        np.save(buffer, data)
        return buffer.getvalue()


class TextArrayExtension(SingleFileSnapshotExtension):
    """
    Text snapshot of a NumPy array. Flattens the array before writing.
    Can be read back into NumPy with .loadtxt() assuming you know the
    shape of the expected data and subsequently reshape it if needed.
    """

    _write_mode = WriteMode.TEXT
    _file_extension = "txt"

    def serialize(
        self,
        data: "SerializableData",
        *,
        exclude: Optional["PropertyFilter"] = None,
        include: Optional["PropertyFilter"] = None,
        matcher: Optional["PropertyMatcher"] = None,
    ) -> "SerializedData":
        buffer = StringIO()
        np.savetxt(buffer, data.ravel())
        return buffer.getvalue()


class ReadableArrayExtension(SingleFileSnapshotExtension):
    """
    Human-readable snapshot of a NumPy array. Preserves array shape
    at the expense of possible loss of precision (default 8 places)
    and more difficulty loading into NumPy than TextArrayExtension.
    """

    _write_mode = WriteMode.TEXT
    _file_extension = "txt"

    def serialize(
        self,
        data: "SerializableData",
        *,
        exclude: Optional["PropertyFilter"] = None,
        include: Optional["PropertyFilter"] = None,
        matcher: Optional["PropertyMatcher"] = None,
    ) -> "SerializedData":
        return np.array2string(data, threshold=np.inf)


class MatchAnything:
    def __eq__(self, _):
        return True


# fixtures


@pytest.fixture(scope="session")
def snapshot_disable(pytestconfig) -> bool:
    return pytestconfig.getoption("--snapshot-disable")


@pytest.fixture
def snapshot(request, snapshot_disable) -> Union[MatchAnything, "SnapshotAssertion"]:
    return (
        MatchAnything()
        if snapshot_disable
        else SnapshotAssertion(
            update_snapshots=request.config.option.update_snapshots,
            extension_class=__import_extension(request.config.option.default_extension),
            test_location=PyTestLocation(request.node),
            session=request.session.config._syrupy,
        )
    )


@pytest.fixture
def array_snapshot(snapshot, snapshot_disable):
    return MatchAnything() if snapshot_disable else snapshot.use_extension(BinaryArrayExtension)


@pytest.fixture
def text_array_snapshot(snapshot, snapshot_disable):
    return MatchAnything() if snapshot_disable else snapshot.use_extension(TextArrayExtension)


@pytest.fixture
def readable_array_snapshot(snapshot, snapshot_disable):
    return MatchAnything() if snapshot_disable else snapshot.use_extension(ReadableArrayExtension)


# pytest config hooks

_NUMPY_VERSION_FILENAME = ".numpy_snapshot_version"


def _find_snapshot_dirs(rootdir: Path) -> list:
    return [p for p in rootdir.rglob("__snapshots__") if p.is_dir()]


def pytest_sessionstart(session):
    if np is None:
        return
    current_major = int(np.__version__.split(".")[0])
    rootdir = Path(session.config.rootdir)
    for snap_dir in _find_snapshot_dirs(rootdir):
        version_file = snap_dir / _NUMPY_VERSION_FILENAME
        if not version_file.exists():
            continue
        stored = version_file.read_text().strip()
        try:
            stored_major = int(stored.split(".")[0])
        except (ValueError, IndexError):
            continue
        if stored_major != current_major:
            warnings.warn(
                f"NumPy major version changed from {stored_major} to {current_major}. "
                "Array snapshots may no longer match. "
                "Regenerate them with: pytest --snapshot-update",
                UserWarning,
                stacklevel=2,
            )
            break


def pytest_sessionfinish(session, exitstatus):
    if np is None:
        return
    if not getattr(session.config.option, "update_snapshots", False):
        return
    rootdir = Path(session.config.rootdir)
    for snap_dir in _find_snapshot_dirs(rootdir):
        (snap_dir / _NUMPY_VERSION_FILENAME).write_text(np.__version__ + "\n")


def pytest_addoption(parser):
    parser.addoption(
        "--snapshot-disable",
        action="store_true",
        default=False,
        help="Disable snapshot comparisons.",
    )
