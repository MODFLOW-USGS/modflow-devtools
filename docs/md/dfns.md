# Working with definition files

MODFLOW 6 specifies input components and their variables in configuration files with a custom format. Such files are called definition (DFN) files and conventionally have suffix `.dfn`.

The `modflow_devtools.dfns` module provides a structured API for working with MODFLOW 6 input specifications, including typed Python objects representing each component and field type, tools for acquiring, loading and managing specification versions, and a utility to convert `.dfn` files to a revised v2 schema and standard file formats.

> **Note**: The `modflow_devtools.dfns` module is experimental. The API may change without following normal deprecation procedures. To suppress the warning emitted on import, use:
> ```python
> import warnings
> warnings.filterwarnings('ignore', message='.*modflow_devtools.dfns.*experimental.*')
> ```
> The `modflow_devtools.dfn` module is stable but not recommended.

Either the `ecosystem` or `dfn` dependency group is required to use either module:

```shell
pip install modflow-devtools[ecosystem]
```

### CLI

A command line interface is available to manage DFN file sets by release.

```shell
# Show sync status for all configured releases
python -m modflow_devtools.dfns info

# Sync all configured releases (downloads dfns.zip from GitHub releases)
python -m modflow_devtools.dfns sync

# Force re-download even if already cached
python -m modflow_devtools.dfns sync --force

# Clean the DFN cache
python -m modflow_devtools.dfns clean
```

A tool is also provided to convert `.dfn` files to the tentative v2 schema:

```shell
python -m modflow_devtools.dfnmap -i <dfn dir path> -o <output dir path>
```

The default output format is YAML. Use `--format` / `-f` to select `yaml` (default), `toml`, or `json`. The tool may also be used on individual files.

#### Configuration

The package ships with a built-in configuration (`modflow_devtools/dfns/dfns.toml`) that specifies default DFN release versions to support.

```toml
releases = [
    "MODFLOW-ORG/modflow6@latest",
    "MODFLOW-ORG/modflow6-nightly-build@latest"
]
```

You can extend or override the default registry configuration by creating:

- Linux/macOS: `~/.config/modflow-devtools/dfns.toml` (respects `$XDG_CONFIG_HOME`)
- Windows: `%APPDATA%/modflow-devtools/dfns.toml`

Entries in the user config are merged with (and take precedence over) the defaults. The file uses the same format as the bundled configuration file. For instance, to point to DFN releases on your own fork, substitute your GitHub username for "MODFLOW-ORG".

DFN files are expected in an asset called `dfns.zip` in configured releases.

#### Caching

DFN files are cached under:

- Linux/macOS: `$XDG_CACHE_HOME/modflow-devtools/dfns/` (default `~/.cache/`)
- Windows: `%LOCALAPPDATA%/modflow-devtools/dfns/`

The cache is organized by repository and release tag:

```
~/.cache/modflow-devtools/dfns/
└── MODFLOW-ORG/
    └── modflow6/
        ├── 6.6.0/
        │   ├── sim-nam.dfn
        │   ├── gwf-chd.dfn
        │   └── ...
        └── 6.5.0/
            └── ...
```

To get the base cache path programmatically:

```python
RemoteDfnRegistry.base_cache_path()
```

To check the cache contents:

```python
from modflow_devtools.dfns.registry import is_cached

is_cached("MODFLOW-ORG/modflow6@6.6.0")
```

When `MODFLOW_DEVTOOLS_AUTO_SYNC=1` is set, `RemoteDfnRegistry.from_ids()` will automatically call `sync()` for any release ID that has no cached files yet.

### Python API

#### Downloading definition files

```python
from modflow_devtools.dfns import fetch_dfns

fetch_dfns("MODFLOW-ORG", "modflow6", "6.6.0", "/tmp/dfns")
```

Downloads all `.dfn` files for the specified MODFLOW 6 release into the given output directory.

### Inspecting the specification

`Dfns` is a Pydantic model representing a set of component definitions.

```python
from modflow_devtools.dfns import Dfns

# Load all component definitions from a directory
spec = Dfns.load("/path/to/mf6/doc/mf6io/mf6ivar/dfn")

spec.schema_version         # e.g. "2"
spec.root                   # the Simulation component, or None
len(spec.components)        # total number of components

# Dict-like access to components
gwf_chd = spec.components["gwf-chd"]
gwf_chd.name                # "gwf-chd"
gwf_chd.parent              # "gwf-nam"

# Navigate the component hierarchy
sim_children = spec.children_of("sim-nam")   # {"gwf-nam": ..., ...}
gwf_children = spec.children_of("gwf-nam")   # {"gwf-chd": ..., "gwf-wel": ..., ...}
```

**Note**: Calling `Dfns.load()` on a directory of `.dfn` files will convert to the v2 schema automatically.

Each entry in `spec.components` is one of three component types, discriminated by a `type` field:

- `Simulation` — the root component (`sim-nam`)
- `Model` — a hydrologic process model (e.g. `gwf-nam`, `gwt-nam`)
- `Package` — any other input component (e.g. `gwf-chd`, `gwf-wel`)

```python
from modflow_devtools.dfns import Simulation, Model, Package

gwf_nam = spec.components["gwf-nam"]
assert isinstance(gwf_nam, Model)

gwf_chd = spec.components["gwf-chd"]
assert isinstance(gwf_chd, Package)
assert gwf_chd.multi is False
assert gwf_chd.subtype == "stress"
```

Each component has `blocks`, a dict mapping block names to `Block` objects. Each `Block` has a `fields` dict of typed field objects.

```python
from modflow_devtools.dfns import Block, Keyword, Double, List, Record

period = gwf_chd.blocks["period"]
assert period.repeats is True

spd = period.fields["stress_period_data"]
assert isinstance(spd, List)
assert isinstance(spd.item, Record)

cellid = spd.item.fields["cellid"]
assert isinstance(cellid, Array)
```

Available field types:

| Class | `type` value | Description |
|---|---|---|
| `Keyword` | `"keyword"` | Boolean presence/absence |
| `String` | `"string"` | String value |
| `Integer` | `"integer"` | Integer value |
| `Double` | `"double"` | Floating-point value |
| `File` | `"file"` (legacy `"path"`) | File path |
| `Array` | `"array"` | Fixed or dynamic array |
| `Record` | `"record"` | Single-line product type |
| `Union` | `"union"` | Tagged sum type |
| `List` | `"list"` | Tabular collection |

See [DFN specification](dfnspec.md) for full attribute documentation.

### Managing specifications

A registry system handles caching and accessing DFN files from MODFLOW 6 releases.

For working with DFN files on the local filesystem, there is `LocalDfnRegistry`.

```python
from modflow_devtools.dfns import LocalDfnRegistry

registry = LocalDfnRegistry(path="/path/to/mf6/doc/mf6io/mf6ivar/dfn")
spec = registry.spec                      # Dfns instance
path = registry.get_path("gwf-chd")      # Path to the component file
```

For fetching and caching DFN files from a MODFLOW 6 release, `RemoteDfnRegistry`:

```python
from modflow_devtools.dfns import RemoteDfnRegistry

registry = RemoteDfnRegistry(release_id="MODFLOW-ORG/modflow6@6.6.0")
registry.sync()  # download and cache DFN files
registry.sync(force=True)  # force re-download

spec = registry.spec  # get the specification

tag = registry.latest_tag()  # resolve "latest" to actual tag
tag = registry.cached_tag()  # return cached tag
```

The `release_id` takes the form `"owner/repo@tag"`, where `tag` may be a specific version or "latest".

For `@latest`, `latest_tag()` queries the GitHub API once and caches the result.

### Managing configurations

To load the default registry configuration, i.e. the bundled configuration with user overlay if present:

```python
registries = RemoteDfnRegistry.load_default()
```

To load specific releases:

```python
registries = RemoteDfnRegistry.from_ids(
    "MODFLOW-ORG/modflow6@6.6.0",
    "MODFLOW-ORG/modflow6@6.5.0",
)
```