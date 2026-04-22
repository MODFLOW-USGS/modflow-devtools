# Working with definition files

MODFLOW 6 specifies input components and their variables in configuration files with a custom format. Such files are called definition (DFN) files and conventionally have suffix `.dfn`.

`modflow_devtools` provides two modules for working with MODFLOW 6 input specification files:

- **`modflow_devtools.dfn`** — stable module, available in all current releases
- **`modflow_devtools.dfns`** — experimental new API, subject to change without notice

---

## `modflow_devtools.dfn` (stable)

The stable `modflow_devtools.dfn` module provides basic utilities for parsing legacy `.dfn` files and downloading them from the MODFLOW 6 repository.

### Downloading definition files

```python
from modflow_devtools.dfn import get_dfns

get_dfns("MODFLOW-ORG", "modflow6", "6.6.0", "/tmp/dfns")
```

Downloads all `.dfn` files for the specified MODFLOW 6 release into the given output directory (returns `None`).

### Types

The core types are `TypedDict`s:

```python
from modflow_devtools.dfn import Dfn, Field

# Dfn: top-level component (e.g. "gwf-chd")
#   name: str
#   advanced: bool
#   multi: bool
#   <block name>: dict[str, Field]  (one key per block, e.g. "options", "period")

# Field: individual input variable within a block
#   name: str
#   type: str          (e.g. "keyword", "integer", "double precision", "string", ...)
#   block: str
#   shape: str | None  (e.g. "(naux)")
#   default: Any
#   children: dict[str, Field] | None
#   description: str | None
#   reader: str        (e.g. "urword")
```

### Converting to TOML

The `dfn` dependency group is required for the TOML conversion tool:

```shell
pip install modflow-devtools[dfn]
```

To convert legacy `.dfn` files to TOML:

```shell
python -m modflow_devtools.dfn2toml -i <dfn dir path> -o <output dir path>
```

The tool may also be used on individual files. To validate legacy format files, use the `--validate` flag.

---

## `modflow_devtools.dfns` (experimental)

> **Note**: This module is experimental. The API may change without following normal deprecation procedures.

The `modflow_devtools.dfns` module provides a richer API for working with MODFLOW 6 input specifications, including structured Python objects, a registry system for remote discovery and caching, and serialization to a single TOML document.

### Formats

MODFLOW 6 input specifications exist in two formats:

**Legacy DFN format** (`.dfn` files): The original text-based format, used in current MODFLOW 6 releases. Flat lists of variables with comments demarcating blocks.

**TOML format** (`.toml` files): A structured, hierarchical representation. Each component is a TOML document with blocks as top-level sections and variables as entries within each section. Variables may be scalar or composite — composites contain fields (if records), choices (if unions), or items (if lists). The MODFLOW 6 repository stores per-component TOML files alongside the legacy `.dfn` files.

Both formats are supported by `modflow_devtools.dfns`. The v2 schema (TOML) is the canonical target format; legacy `.dfn` files can be mapped to v2 schema with `map()`.

### Core classes

#### `Dfn`

Represents a single MODFLOW 6 input component (e.g. `gwf-chd`, `sim-nam`). A dataclass with attributes including `name`, `schema_version`, `blocks`, `parent`, `advanced`, `multi`, `subcomponents`, and optionally `children` (when part of a tree).

```python
from modflow_devtools.dfns import load

# Load a single component from a TOML file
with open("gwf-chd.toml", "rb") as f:
    dfn = load(f, format="toml")

print(dfn.name)           # "gwf-chd"
print(dfn.schema_version) # Version('2')
print(list(dfn.blocks))   # ['options', 'dimensions', 'period']
```

#### `DfnSpec`

Represents the full MODFLOW 6 input specification. Implements the `Mapping` protocol for flat dict-like access to components by name, and exposes the root component (simulation) with the full component hierarchy via `.root`.

```python
from modflow_devtools.dfns import DfnSpec

# Load from a directory of DFN files (legacy or TOML)
spec = DfnSpec.load("/path/to/mf6/doc/mf6io/mf6ivar/dfn")

# Hierarchical access
spec.root.name                                         # "sim-nam"
spec.root.children["gwf-nam"]                         # GWF model name file Dfn
spec.root.children["gwf-nam"].children["gwf-chd"]     # GWF CHD package Dfn

# Flat dict-like access
gwf_chd = spec["gwf-chd"]
for name, dfn in spec.items():
    print(name)
len(spec)  # total number of components

# Serialize the full spec as a single TOML document
with open("mf6spec.toml", "wb") as f:
    spec.dump(f)

toml_str = spec.dumps()
```

### Registry

The registry system handles discovering, caching, and accessing DFN files from remote sources (primarily the MODFLOW 6 GitHub repository).

#### `LocalDfnRegistry`

For working with DFN files on the local filesystem:

```python
from modflow_devtools.dfns import LocalDfnRegistry

registry = LocalDfnRegistry(path="/path/to/mf6/doc/mf6io/mf6ivar/dfn")
dfn = registry.get_dfn("gwf-chd")
spec = registry.spec
```

#### `RemoteDfnRegistry`

For fetching and caching DFN files from a remote source. Uses [Pooch](https://www.fatiando.org/pooch/) for caching and hash verification.

```python
from modflow_devtools.dfns import RemoteDfnRegistry

registry = RemoteDfnRegistry(source="modflow6", ref="6.6.0")
registry.sync()  # downloads and caches the registry + DFN files

dfn = registry.get_dfn("gwf-chd")
spec = registry.spec
```

#### Convenience functions

```python
from modflow_devtools.dfns import get_dfn, get_dfn_path, get_registry, list_components, sync_dfns

# Sync all configured refs
sync_dfns()

# Sync a specific ref
sync_dfns(ref="6.6.0")

# Get a component (auto-syncs if MODFLOW_DEVTOOLS_AUTO_SYNC=1)
dfn = get_dfn("gwf-chd", ref="6.6.0")

# Get the local cached path to a component file
path = get_dfn_path("gwf-wel", ref="6.6.0")

# List all components for a ref
components = list_components(ref="6.6.0")

# Get a registry object
registry = get_registry(ref="6.6.0")

# Use a local path instead of remote
registry = get_registry(path="/path/to/dfns")
dfn = get_dfn("gwf-chd", path="/path/to/dfns")
```

#### CLI

```shell
# Sync all configured refs
python -m modflow_devtools.dfns sync

# Sync a specific ref
python -m modflow_devtools.dfns sync --ref 6.6.0

# Force re-download
python -m modflow_devtools.dfns sync --force

# Show sync status and cache info
python -m modflow_devtools.dfns info

# List available components for a ref
python -m modflow_devtools.dfns list --ref 6.6.0

# Clear cache
python -m modflow_devtools.dfns clean
python -m modflow_devtools.dfns clean --all
```

#### Auto-sync

Auto-sync is opt-in (off by default). Enable it by setting the environment variable:

```shell
MODFLOW_DEVTOOLS_AUTO_SYNC=1
```

When enabled, `get_registry()` will automatically sync if no cached registry exists for the requested ref.

#### Cache location

Cached registries and DFN files are stored under:

```
~/.cache/modflow-devtools/dfn/
├── registries/
│   └── modflow6/
│       └── 6.6.0/
│           └── dfns.toml
└── files/
    └── modflow6/
        └── 6.6.0/
            ├── sim-nam.toml
            ├── gwf-chd.toml
            └── ...
```

### Schema versioning and mapping

`modflow_devtools.dfns` supports multiple schema versions simultaneously:

- **v1**: Original MODFLOW 6 releases. Mixes structural specification with input format details. Serialized as `.dfn` files.
- **v1.1**: Cleaned-up v1 with normalized attributes, structural improvements, and better parent-child inference. Can be serialized as `.dfn` or `.toml`.
- **v2**: Current TOML schema. Separates structural specification from input format concerns. Per-component `.toml` files in the MODFLOW 6 repository use this schema.

Use `map()` to convert between schema versions:

```python
from modflow_devtools.dfns import get_dfn, map

dfn_v1 = get_dfn("gwf-chd", ref="6.4.4")  # v1 schema
dfn_v2 = map(dfn_v1, schema_version="2")   # convert to v2
```

`DfnSpec.load()` automatically maps v1 DFNs to v2 when loading from a directory of legacy `.dfn` files.
