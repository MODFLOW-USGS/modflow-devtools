# Installing `modflow-devtools`

## Official package

The `modflow-devtools` package is [available on PyPi](https://pypi.org/project/modflow-devtools/) and can be installed with `pip`:

```shell
pip install modflow-devtools
```

## Development version

To set up a `modflow-devtools` development environment, first clone the repository:

```shell
git clone https://github.com/MODFLOW-USGS/modflow-devtools.git
```

Then install the local copy as well as testing, linting, and docs dependencies:

```
pip install .
pip install ".[lint, test, docs]"
```

## Using `modflow-devtools` as a `pytest` plugin

Fixtures provided by `modflow-devtools` can be imported into a `pytest` test suite by adding the following to the consuming project's top-level `conftest.py` file:

```python
pytest_plugins = ["modflow_devtools.fixtures"]
```