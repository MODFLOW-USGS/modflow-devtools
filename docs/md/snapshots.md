# Snapshot testing

Snapshot testing is a form of regression testing in which a "snapshot" of the results of some computation is verified and captured by the developer to be compared against when tests are subsequently run. This is accomplished with [`syrupy`](https://github.com/tophat/syrupy), which provides a `snapshot` fixture overriding the equality operator to allow comparison with e.g. `snapshot == result`. A few custom fixtures for snapshots of NumPy arrays are also provided:

- `array_snapshot`: saves an array in a binary file for compact storage, can be inspected programmatically with `np.load()`
- `text_array_snapshot`: flattens an array and stores it in a text file, compromise between readability and disk usage
- `readable_array_snapshot`: stores an array in a text file in its original shape, easy to inspect but largest on disk

By default, tests run in comparison mode. This means a newly written test using any of the snapshot fixtures will fail until a snapshot is created. Snapshots can be created/updated by running pytest with the `--snapshot-update` flag.

## Using snapshot fixtures

To use snapshot fixtures, add the following line to a test file or `conftest.py` file:

```python
pytest_plugins = [ "modflow_devtools.snapshots" ]
```

## Disable snapshots

Snapshot comparisons can be disabled by invoked `pytest` with the `--snapshot-disable` flag.

## Caveats & gotchas

NumPy major versions may introduce changes to `np.save()`'s binary format, causing binary array snapshot failures for arrays with object dtypes. To avoid this, check object (e.g. string) columns explicitly and then omit them from the comparison array.