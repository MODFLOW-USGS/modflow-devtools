import os
import shutil
import sys
import zipfile
from os import environ
from pathlib import Path
from pprint import pprint
from zipfile import ZipFile

import pytest
from modflow_devtools.markers import excludes_platform
from modflow_devtools.misc import get_suffixes, set_dir
from modflow_devtools.zip import MFZipFile

_bin_path = Path(environ.get("BIN_PATH")).expanduser().absolute()
_ext, _ = get_suffixes(sys.platform)


@pytest.fixture(scope="module")
def empty_archive(module_tmpdir) -> Path:
    # https://stackoverflow.com/a/25195628/6514033
    data = b"PK\x05\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    path = module_tmpdir / "empty.zip"

    with open(path, "wb") as zip:
        zip.write(data)

    return path


@pytest.fixture(scope="module")
def nonempty_archive(module_tmpdir) -> Path:
    if not _bin_path.is_dir():
        pytest.skip(f"BIN_PATH ({_bin_path}) is not a directory")

    zip_path = module_tmpdir / "nonempty.zip"
    txt_path = module_tmpdir / "hw.txt"
    exe_path = _bin_path / f"mf6{_ext}"

    # create a zip file with a text file and an executable
    shutil.copy(exe_path, module_tmpdir)
    with open(txt_path, "w") as f:
        f.write("hello world")

    with set_dir(module_tmpdir):
        zip = MFZipFile(zip_path.name, "w")
        zip.write(txt_path.name, compress_type=zipfile.ZIP_DEFLATED)
        zip.write(exe_path.name, compress_type=zipfile.ZIP_DEFLATED)
        zip.close()

    return zip_path


def test_compressall(function_tmpdir):
    zip_file = function_tmpdir / "output.zip"
    input_dir = function_tmpdir / "input"
    input_dir.mkdir()

    with open(input_dir / "data.txt", "w") as f:
        f.write("hello world")

    MFZipFile.compressall(str(zip_file), dir_pths=str(input_dir))

    pprint(list(function_tmpdir.iterdir()))
    assert zip_file.exists()

    output_dir = function_tmpdir / "output"
    output_dir.mkdir()

    ZipFile(zip_file).extractall(path=str(output_dir))

    pprint(list(output_dir.iterdir()))
    assert (output_dir / "data.txt").is_file()


def test_extractall_empty(empty_archive, function_tmpdir):
    zf = MFZipFile(empty_archive, "r")
    zf.extractall(str(function_tmpdir))

    assert not any(function_tmpdir.iterdir())


@pytest.mark.parametrize("mf", [True, False])
@excludes_platform("Windows")
def test_preserves_execute_permission(function_tmpdir, nonempty_archive, mf):
    zip = MFZipFile(nonempty_archive) if mf else ZipFile(nonempty_archive)
    zip.extractall(path=str(function_tmpdir))

    exe_path = function_tmpdir / f"mf6{_ext}"

    assert exe_path.is_file()
    assert os.access(exe_path, os.X_OK) == mf
