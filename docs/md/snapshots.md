# Snapshot testing

Snapshot testing is a form of regression testing in which a "snapshot" of the results of some computation is verified and captured by the developer to be compared against when tests are subsequently run. This is accomplished with [`syrupy`](https://github.com/tophat/syrupy), which provides a `snapshot` fixture overriding the equality operator to allow comparison with e.g. `snapshot == result`. A few custom fixtures for snapshots of NumPy arrays are also provided:

- `array_snapshot`: saves an array in a binary file for compact storage, can be inspected programmatically with `np.load()`
- `text_array_snapshot`: flattens an array and stores it in a text file, compromise between readability and disk usage
- `readable_array_snapshot`: stores an array in a text file in its original shape, easy to inspect but largest on disk

By default, tests run in comparison mode. This means a newly written test using any of the snapshot fixtures will fail until a snapshot is created. Snapshots can be created/updated by running pytest with the `--snapshot-update` flag.

## Using snapshot fixtures

To use snapshot fixtures, add the following line to a test file or `conftest.py` file:

```python
pytest_plugins = ["modflow_devtools.snapshots"]
```

## Disable snapshots

Snapshot comparisons can be disabled by invoked `pytest` with the `--snapshot-disable` flag.

## Caveats & gotchas

### NumPy version compatibility

Snapshot files are tied to the NumPy major version used to generate them. Upgrading NumPy may cause snapshot failures.

- **`array_snapshot` (binary)**: `np.save()` uses `.npy` format version 3.0 in NumPy 2.0+ for arrays whose dtype description cannot be encoded as Latin-1 (e.g. structured arrays with unicode field names). Snapshots generated with NumPy 1.x will not match bytes produced by NumPy 2.x for these arrays. For plain numeric dtypes (`float64`, `int32`, etc.) the format is stable across versions.
- **`readable_array_snapshot` (text)**: `np.array2string()` array printing is stable across NumPy major versions. However, scalar `__repr__` changed in NumPy 2.0 (e.g. `np.float64(1.1)` instead of `1.1`), which does not affect array element printing but may affect snapshot output if scalars are passed directly rather than as arrays.
- **`text_array_snapshot` (text)**: `np.savetxt()` output is stable across NumPy versions and is the safest choice when version-portability matters.

As such, snapshot fixtures should ideally be used in a dependency-locked environment. At minimum, NumPy should be pinned, and after upgrading NumPy, all snapshots regenerated:

```shell
pytest --snapshot-update
```

To make NumPy version mismatches easier to notice, a warning will be emitted at the start of a test session if the NumPy major version differs from the one used to create the snapshots. This mechanism works by storing a `.numpy_snapshot_version` file in the `__snapshots__` directory. This file should be committed alongside snapshot files.