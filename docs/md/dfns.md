# Working with definition files

MODFLOW 6 specifies input components and their variables in configuration files with a custom format. Such files are called definition (DFN) files and conventionally have suffix `.dfn`.

`modflow_devtools` provides two modules for working with MODFLOW 6 input specification files:

- **`modflow_devtools.dfn`:** stable utilities for parsing legacy `.dfn` files
- **`modflow_devtools.dfns`:** experimental structured API, subject to change without notice

## `modflow_devtools.dfn` (stable)

The stable `modflow_devtools.dfn` module provides basic utilities for parsing legacy `.dfn` files and downloading them from the MODFLOW 6 repository.

### Downloading definition files

```python
from modflow_devtools.dfn import fetch_dfns

fetch_dfns("MODFLOW-ORG", "modflow6", "6.6.0", "/tmp/dfns")
```

Downloads all `.dfn` files for the specified MODFLOW 6 release into the given output directory.

### Converting to TOML

The `dfn` dependency group is required for the conversion tool:

```shell
pip install modflow-devtools[dfn]
```

To convert legacy `.dfn` files (default output format is YAML):

```shell
python -m modflow_devtools.dfnmap -i <dfn dir path> -o <output dir path>
```

Use `--format` / `-f` to select `yaml` (default), `toml`, or `json`. The tool may also be used on individual files.

---

## `modflow_devtools.dfns` (experimental)

> **Note**: This module is experimental. The API may change without following normal deprecation procedures. To suppress the warning emitted on import, use:
> ```python
> import warnings
> warnings.filterwarnings('ignore', message='.*modflow_devtools.dfns.*experimental.*')
> ```

The `modflow_devtools.dfns` module provides a structured API for working with MODFLOW 6 input specifications, including typed Python objects representing each component and field type, a registry system for remote caching, and tools for loading and navigating the full specification.

### File format and schema version

These are two separate concerns.

**File format** is the serialization:

- **Legacy DFN format** (`.dfn`): flat text with comments demarcating blocks, used by MODFLOW 6 releases.
- **TOML format** (`.toml`): per-component TOML documents.
- **YAML format** (`.yaml`): per-component YAML documents.
- **JSON format** (`.json`): per-component JSON documents.

TOML, YAML, and JSON files are produced by the `dfnmap` conversion tool.

**Schema version** describes the structure and semantics of the content:

- **v1 schema**: the original structure embedded in legacy `.dfn` files. Mixes structural definitions with input format details (e.g., `in_record`, `tagged`).
- **v2 schema**: a cleaner, hierarchical representation. Each component has explicitly typed, nested fields; blocks and records are first-class objects; structural specification is separated from input format concerns.

`modflow_devtools.dfns` always works with v2 schema objects internally. When loading a directory of `.dfn` files, they are parsed as v1 and automatically mapped to v2. TOML, YAML, and JSON files carry v2 content directly and are loaded without mapping. All file formats are supported by `Dfns.load()`.

### Core classes

#### `Dfns`

`Dfns` is a Pydantic model representing the full set of component definitions for a release. It is the primary object returned by `Dfns.load()` (see also [Registry](#registry) below, which loads and caches DFN files from remote releases).

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

#### Component types

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

#### Blocks and fields

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

### Registry

The registry system handles caching and accessing DFN files from MODFLOW 6 releases.

#### `LocalDfnRegistry`

For working with DFN files on the local filesystem.

```python
from modflow_devtools.dfns import LocalDfnRegistry

registry = LocalDfnRegistry(path="/path/to/mf6/doc/mf6io/mf6ivar/dfn")
spec = registry.spec                      # Dfns instance
path = registry.get_path("gwf-chd")      # Path to the component file
```

#### `RemoteDfnRegistry`

For fetching and caching DFN files from a MODFLOW 6 release. The `release_id` takes the form `"owner/repo@tag"`, where `tag` may be a specific version or `"latest"`.

```python
from modflow_devtools.dfns import RemoteDfnRegistry

registry = RemoteDfnRegistry(release_id="MODFLOW-ORG/modflow6@6.6.0")
registry.sync()                           # download and cache DFN files
registry.sync(force=True)                 # force re-download

spec = registry.spec                      # Dfns (auto-syncs if needed)
path = registry.get_path("gwf-chd")      # Path to cached component file

tag = registry.latest_tag()              # resolve "latest" to actual tag (network)
tag = registry.cached_tag()              # return cached tag (no network)
```

For `@latest`, `latest_tag()` queries the GitHub API once and caches the result.

#### Default registries

The package ships with a built-in configuration (`modflow_devtools/dfns/dfns.toml`) that lists the default release IDs to track:

```toml
releases = [
    "MODFLOW-ORG/modflow6@latest",
    "MODFLOW-ORG/modflow6-nightly-build@latest",
]
```

To load these defaults:

```python
registries = RemoteDfnRegistry.load_default()
# {"MODFLOW-ORG/modflow6@latest": RemoteDfnRegistry(...), ...}
```

To load specific release IDs programmatically:

```python
registries = RemoteDfnRegistry.from_ids(
    "MODFLOW-ORG/modflow6@6.6.0",
    "MODFLOW-ORG/modflow6@6.5.0",
)
```

#### User config overlay

You can extend or override the default registry configuration by creating:

- Linux/macOS: `~/.config/modflow-devtools/dfns.toml` (respects `$XDG_CONFIG_HOME`)
- Windows: `%APPDATA%/modflow-devtools/dfns.toml`

The file uses the same format as the bundled config:

```toml
releases = [
    "my-org/my-mf6-fork@main",
]
```

Entries in the user config are merged with (and take precedence over) the defaults.

#### Cache location

Downloaded DFN files are cached under:

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

#### Checking cache status

```python
from modflow_devtools.dfns.registry import is_cached

is_cached("MODFLOW-ORG/modflow6@6.6.0")   # True/False (no network)
```

#### Auto-sync

When `MODFLOW_DEVTOOLS_AUTO_SYNC=1` is set, `RemoteDfnRegistry.from_ids()` will automatically call `sync()` for any release ID that has no cached files yet.

### CLI

```shell
# Show sync status for all configured releases
python -m modflow_devtools.dfns info

# Sync all configured releases (downloads dfns.zip from GitHub releases)
python -m modflow_devtools.dfns sync

# Force re-download even if already cached
python -m modflow_devtools.dfns sync --force

# Clean the entire DFN cache
python -m modflow_devtools.dfns clean
```
