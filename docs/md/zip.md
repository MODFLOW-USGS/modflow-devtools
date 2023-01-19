# `MFZipFile`

Python's [`ZipFile`](https://docs.python.org/3/library/zipfile.html) doesn't [preserve file permissions at extraction time](https://bugs.python.org/issue15795). The `MFZipFile` subclass:

- modifies `ZipFile.extract()` to preserve permissions per the [recommendation here](https://stackoverflow.com/questions/39296101/python-zipfile-removes-execute-permissions-from-binaries)
- adds a static `ZipFile.compressall()` method to create a zip file from files and directories
- maintains an otherwise identical API

## `compressall`

The `compressall` method is a static method that creates a zip file from lists of files and/or directories. It is a convenience method that wraps `ZipFile.write()`, `ZipFile.close()`, etc.

```python
from zipfile import ZipFile
from modflow_devtools.zip import MFZipFile

def test_compressall(function_tmpdir):
    zip_file = function_tmpdir / "output.zip"
    
    input_dir = function_tmpdir / "input"
    input_dir.mkdir()

    with open(input_dir / "data.txt", "w") as f:
        f.write("hello world")

    MFZipFile.compressall(str(zip_file), dir_pths=str(input_dir))
    assert zip_file.exists()

    output_dir = function_tmpdir / "output"
    output_dir.mkdir()

    ZipFile(zip_file).extractall(path=str(output_dir))
    assert (output_dir / "data.txt").is_file()
```