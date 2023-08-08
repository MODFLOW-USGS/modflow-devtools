# OS Tags

MODFLOW 6, Python3, build servers, and other systems may refer to operating systems by different names. Utilities are provided in the `modflow_devtools.ostags` module to convert between

- the output of `platform.system()`
- GitHub Actions `runner.os` tags
- MODFLOW 6 release asset OS tags

Only Linux, Mac and Windows are supported.

## Tag specification

Python3's `platform.system()` returns "Linux", "Darwin", and "Windows", respectively.

GitHub Actions (e.g. `runner.os` context) use "Linux", "macOS" and "Windows".

MODFLOW 6 release asset names end with "linux", "mac" or "win64".

## Getting tags

To get the MODFLOW 6 or GitHub tag for the current OS, use:

- `get_modflow_ostag()`
- `get_github_ostag()`

## Converting tags

Conversion functions are available for each direction:

- `python_to_modflow_ostag(tag)`
- `modflow_to_python_ostag(tag)`
- `modflow_to_github_ostag(tag)`
- `github_to_modflow_ostag(tag)`
- `python_to_github_ostag(tag)`
- `github_to_python_ostag(tag)`

Alternatively:

```python
OSTag.convert(platform.system(), "py2mf")
```

The second argument specifies the mapping in format `<source>2<target>`, where `<source>` and `<target>` may take values `py`, `mf`, or `gh`.

**Note**: source and target must be different.

## Getting suffixes

A convenience function is available to get the appropriate binary file extensions for a given operating system, identified by tag (or the current operating system if no tag is provided). The return value is a 2-tuple containing the executable and library extensions, respectively.

```python
get_binary_suffixes()  # get extensions for current OS
get_binary_suffixes("linux")  # returns ("", ".so")
get_binary_suffixes("linux")  # returns ("", ".so")
get_binary_suffixes("win64")  # returns (".exe", ".dll")
```
