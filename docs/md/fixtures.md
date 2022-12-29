# Fixtures

Several `pytest` fixtures are provided to help with testing.

## Keepable temporary directories

Tests often need to exercise code that reads from and/or writes to disk. The test harness may also need to create test data during setup and clean up the filesystem on teardown. Temporary directories are built into `pytest` via the [`tmp_path`](https://docs.pytest.org/en/latest/how-to/tmp_path.html#the-tmp-path-fixture) and `tmp_path_factory` fixtures.

Several fixtures are provided in `modflow_devtools/fixtures.py` to extend the behavior of temporary directories for test functions:

- `function_tmpdir`
- `module_tmpdir`
- `class_tmpdir`
- `session_tmpdir`

These are automatically created before test code runs and lazily removed afterwards, subject to the same [cleanup procedure](https://docs.pytest.org/en/latest/how-to/tmp_path.html#the-default-base-temporary-directory) used by the default `pytest` temporary directory fixtures. Their purpose is to allow test artifacts to be saved in a user-specified location when `pytest` is invoked with a `--keep` option &mdash; this can be useful to debug failing tests.

```python
from pathlib import Path
import inspect

def test_tmpdirs(function_tmpdir, module_tmpdir):
    # function-scoped temporary directory
    assert function_tmpdir.is_dir()
    assert inspect.currentframe().f_code.co_name in function_tmpdir.stem

    # module-scoped temp dir (accessible to other tests in the script)
    assert module_tmpdir.is_dir()

    with open(function_tmpdir / "test.txt", "w") as f1, open(module_tmpdir / "test.txt", "w") as f2:
        f1.write("hello, function")
        f2.write("hello, module")
```

Any files written to the temporary directory will be saved to saved to subdirectories named according to the test case, class or module. To keep files created by a test case like above, run:

```shell
pytest --keep <path>
```

There is also a `--keep-failed <path>` option which preserves outputs only from failing test cases.

## Loading example models

Fixtures are provided to find and enumerate models from the MODFLOW 6 example and test model repositories and feed them to test functions. Models can be loaded from:

- [`MODFLOW-USGS/modflow6-examples`](https://github.com/MODFLOW-USGS/modflow6-examples)
- [`MODFLOW-USGS/modflow6-testmodels`](https://github.com/MODFLOW-USGS/modflow6-testmodels)
- [`MODFLOW-USGS/modflow6-largetestmodels`](https://github.com/MODFLOW-USGS/modflow6-largetestmodels)

These models can be requested like any other `pytest` fixture, by adding one of the following parameters to test functions:

- `test_model_mf5to6`
- `test_model_mf6`
- `large_test_model`
- `example_scenario`

To use these fixtures, the environment variable `REPOS_PATH` must point to the location of model repositories on the filesystem. Model repositories must live side-by-side in this location, and repository directories are expected to be named identically to GitHub repositories. If `REPOS_PATH` is not configured, test functions requesting these fixtures will be skipped.

**Note**: example models must be built by running the `ci_build_files.py` script in `modflow6-examples/etc` before running tests using the `example_scenario` fixture.

### Test models

The `test_model_mf5to6`, `test_model_mf6` and `large_test_model` fixtures are each a `Path` to the model's namefile. For example:, to load `mf5to6` models from the  repository:

```python
def test_mf5to6_model(test_model_mf5to6):
    assert test_model_mf5to6.is_file()
    assert test_model_mf5to6.suffix == ".nam"
```

This test function will be parametrized with all `mf5to6` models found in the [`MODFLOW-USGS/modflow6-testmodels`](https://github.com/MODFLOW-USGS/modflow6-testmodels).

### Example scenarios

The [`MODFLOW-USGS/modflow6-examples`](https://github.com/MODFLOW-USGS/modflow6-examples) repository contains a collection of scenarios, each consisting of 1 or more models. The `example_scenario` fixture is a `Tuple[str, List[Path]]`. The first item is the name of the scenario. The second item is a list of namefile `Path`s, ordered alphabetically by name. Model naming conventions are as follows:

- groundwater flow models begin with prefix `gwf*`
- transport models begin with `gwt*`

Ordering as above permits models to be run directly in the order provided, with transport models potentially consuming the outputs of flow models. A straightforward pattern is to loop over models and run each in a subdirectory of the same top-level working directory.

```python
def test_example_scenario(tmp_path, example_scenario):
    name, namefiles = example_scenario
    for namefile in namefiles:
        model_ws = tmp_path / namefile.parent.name
        model_ws.mkdir()
        # load and run model
        # ...
```

### Utility functions

Model-loading fixtures use a set of utility functions to find and enumerate models. These functions can be imported from `modflow_devtools.misc` for use in other contexts:

- `get_model_dir_paths()`
- `get_namefile_paths()`

See this project's test suite for usage examples.
