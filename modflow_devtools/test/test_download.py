import pytest
from modflow_devtools.download import download_and_unzip


@pytest.mark.parametrize("delete_zip", [True, False])
def test_download_and_unzip(function_tmpdir, delete_zip):
    zip_name = "mf6.3.0_linux.zip"
    dir_name = zip_name.replace(".zip", "")
    url = f"https://github.com/MODFLOW-USGS/modflow6/releases/download/6.3.0/{zip_name}"
    download_and_unzip(
        url, function_tmpdir, delete_zip=delete_zip, verbose=True
    )

    assert (function_tmpdir / zip_name).is_file() != delete_zip

    dir_path = function_tmpdir / dir_name
    assert dir_path.is_dir()

    contents = list(dir_path.rglob("*"))
    assert len(contents) > 0
