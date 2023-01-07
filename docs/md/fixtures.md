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

Fixtures are provided to find models from the MODFLOW 6 example and test model repositories and feed them to test functions. Models can be loaded from:

- [`MODFLOW-USGS/modflow6-examples`](https://github.com/MODFLOW-USGS/modflow6-examples)
- [`MODFLOW-USGS/modflow6-testmodels`](https://github.com/MODFLOW-USGS/modflow6-testmodels)
- [`MODFLOW-USGS/modflow6-largetestmodels`](https://github.com/MODFLOW-USGS/modflow6-largetestmodels)

These models can be requested like any other `pytest` fixture, by adding one of the following parameters to test functions:

- `test_model_mf5to6`: a `Path` to a MODFLOW 2005 model namefile, loaded from the `mf5to6` subdirectory of the `modflow6-testmodels` repository
- `test_model_mf6`: a `Path` to a MODFLOW 6 model namefile, loaded from the `mf6` subdirectory of the `modflow6-testmodels` repository
- `large_test_model`: a `Path` to a large MODFLOW 6 model namefile, loaded from the `modflow6-largetestmodels` repository
- `example_scenario`: a `Tuple[str, List[Path]]` containing the name of a MODFLOW 6 example scenario and a list of paths to its model namefiles, loaded from the `modflow6-examples` repository

### Configuration

Model repositories must first be cloned

It is recommended to set the environment variable `REPOS_PATH` to the location of the model repositories on the filesystem. Model repositories must live side-by-side in this location, and repository directories are expected to be named identically to GitHub repositories. If `REPOS_PATH` is not configured, `modflow-devtools` assumes tests are being run from an `autotest` subdirectory of the consuming project's root, and model repos live side-by-side with the consuming project. If this guess is incorrect and repositories cannot be found, tests requesting these fixtures will be skipped.

**Note:** by default, all models found in the respective external repository will be returned by these fixtures. It is up to the consuming project to exclude models if needed.

### MODFLOW 2005 test models

The `test_model_mf5to6` fixture are each a `Path` to the model's namefile. For example, to load `mf5to6` models from the `MODFLOW-USGS/modflow6-testmodels` repo:

```python
def test_mf5to6_model(test_model_mf5to6):
    assert isinstance(test_model_mf5to6, Path)
    assert test_model_mf5to6.is_file()
    assert test_model_mf5to6.suffix == ".nam"
```

This test function will be parametrized with all models found in the `mf5to6` subdirectory of the [`MODFLOW-USGS/modflow6-testmodels`](https://github.com/MODFLOW-USGS/modflow6-testmodels) repository. Note that MODFLOW-2005 namefiles need not be named `mfsim.nam`.

### MODFLOW 6 test models

The `test_model_mf6` fixture loads all MODFLOW 6 models found in the `mf6` subdirectory of the `MODFLOW-USGS/modflow6-testmodels` repository.

```python
def test_test_model_mf6(test_model_mf6):
    assert isinstance(test_model_mf6, Path)
    assert test_model_mf6.is_file()
    assert test_model_mf6.name == "mfsim.nam"
```

Because these are MODFLOW 6 models, each namefile will be named `mfsim.nam`. The model name can be inferred from the namefile's parent directory.

### Large test models

The `large_test_model` fixture loads all MODFLOW 6 models found in the `MODFLOW-USGS/modflow6-largetestmodels` repository.

```python
def test_large_test_model(large_test_model):
    print(large_test_model)
    assert isinstance(large_test_model, Path)
    assert large_test_model.is_file()
    assert large_test_model.name == "mfsim.nam"
```

### Example scenarios

The [`MODFLOW-USGS/modflow6-examples`](https://github.com/MODFLOW-USGS/modflow6-examples) repository contains a collection of example scenarios, each with 1 or more models. The `example_scenario` fixture is a `Tuple[str, List[Path]]`. The first item is the name of the scenario. The second item is a list of MODFLOW 6 namefile `Path`s, ordered alphabetically by name, with models generally named as follows:

- groundwater flow models begin with `gwf*`
- transport models begin with `gwt*`

This naming permits models to be run in the order provided, with transport models potentially consuming the outputs of flow models. One possible pattern is to loop over models and run each in a subdirectory of the same top-level working directory.

```python
def test_example_scenario(tmp_path, example_scenario):
    name, namefiles = example_scenario
    for namefile in namefiles:
        model_ws = tmp_path / namefile.parent.name
        model_ws.mkdir()
        # load and run model
        # ...
```

**Note**: example models must first be built by running the `ci_build_files.py` script in `modflow6-examples/etc` before running tests using the `example_scenario` fixture. See the [install docs](https://modflow-devtools.readthedocs.io/en/latest/md/install.html) for more info.

### Utility functions

Model-loading fixtures use a set of utility functions to find and enumerate models. These functions can be imported from `modflow_devtools.misc` for use in other contexts:

- `get_model_paths()`
- `get_namefile_paths()`

These functions are used internally in a `pytest_generate_tests` hook to implement the above model-parametrization fixtures. See `fixtures.py` and/or this project's test suite for usage examples.
