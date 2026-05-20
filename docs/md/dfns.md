# Working with definition files

MODFLOW 6 specifies input components and their variables in configuration files with a custom format. Such files are called definition (DFN) files and conventionally have suffix `.dfn`.

`modflow_devtools` provides two modules for working with MODFLOW 6 input specification files:

- **`modflow_devtools.dfn`:** stable, soon-to-be deprecated
- **`modflow_devtools.dfns`:** experimental, subject to change without notice

## `modflow_devtools.dfn` (stable)

The stable `modflow_devtools.dfn` module provides basic utilities for parsing legacy `.dfn` files and downloading them from the MODFLOW 6 repository.

### Downloading definition files

```python
from modflow_devtools.dfn import get_dfns

get_dfns("MODFLOW-ORG", "modflow6", "6.6.0", "/tmp/dfns")
```

Downloads all `.dfn` files for the specified MODFLOW 6 release into the given output directory (returns `None`).

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

The `modflow_devtools.dfns` module provides a richer API for working with MODFLOW 6 input specifications, including structured Python objects, a registry system for remote discovery and caching, and serialization to TOML.

### Formats

MODFLOW 6 input specifications exist in two formats:

**Legacy DFN format** (`.dfn` files): The original text-based format, used in current MODFLOW 6 releases. Flat lists of variables with comments demarcating blocks.

**TOML format** (`.toml` files): A structured, hierarchical representation. Each component is a TOML document with blocks as top-level sections and variables as entries within each section. Variables may be scalar or composite — composites contain fields (if records), choices (if unions), or items (if lists). The MODFLOW 6 repository stores per-component TOML files alongside the legacy `.dfn` files.

Both formats are supported by `modflow_devtools.dfns`. The v2 schema (TOML) is the canonical target format; legacy `.dfn` files can be mapped to v2 schema with `map()`.

### Core classes

#### `Dfn`

Represents a single MODFLOW 6 input component (e.g. `gwf-chd`, `sim-nam`). A dataclass with attributes including `name`, `schema_version`, `blocks`, `parent`, `advanced`, `multi`, `subcomponents`, and optionally `children` (when part of a tree).

```python
from modflow_devtools.dfns import DfnSpec

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

The registry system handles discovering, caching, and accessing DFN files from MODFLOW 6 releases. Only released versions are supported by `RemoteDfnRegistry`; for working with unreleased or local DFN files, use `LocalDfnRegistry`.

#### `LocalDfnRegistry`

For working with DFN files on the local filesystem. This is the right choice when working with a local MODFLOW 6 checkout, a CI environment with DFN files checked out, or any directory of DFN files not associated with a published release.

```python
from modflow_devtools.dfns import LocalDfnRegistry

registry = LocalDfnRegistry(path="/path/to/mf6/doc/mf6io/mf6ivar/dfn")
dfn = registry.get_dfn("gwf-chd")
spec = registry.spec
```

#### `RemoteDfnRegistry`

For fetching and caching DFN files from a MODFLOW 6 release. On first access for a given version, downloads the `mf{version}_dfns.zip` release asset from GitHub, extracts it to a local cache directory, and uses it for all subsequent access. Only accepts released version strings (e.g. `"6.6.0"`), not branch names or arbitrary git refs.

```python
from modflow_devtools.dfns import RemoteDfnRegistry

registry = RemoteDfnRegistry(source="modflow6", ref="6.6.0")
registry.sync()  # downloads and caches DFN files for 6.6.0

dfn = registry.get_dfn("gwf-chd")
spec = registry.spec
```

#### Convenience functions

```python
from modflow_devtools.dfns import (
    get_dfn,
    get_dfn_path,
    get_registry,
    list_components,
    list_releases,
    sync_dfns,
)

# List available releases
releases = list_releases()  # e.g. ["6.6.0", "6.5.0", "6.4.4"]

# Sync all available releases
sync_dfns()

# Sync a specific release
sync_dfns(ref="6.6.0")

# Get a component (auto-syncs if MODFLOW_DEVTOOLS_AUTO_SYNC=1)
dfn = get_dfn("gwf-chd", ref="6.6.0")

# Get the local cached path to a component file
path = get_dfn_path("gwf-wel", ref="6.6.0")

# List all components for a release
components = list_components(ref="6.6.0")

# Get a registry object for a release
registry = get_registry(ref="6.6.0")

# Use a local path instead of a remote release
registry = get_registry(path="/path/to/dfns")
dfn = get_dfn("gwf-chd", path="/path/to/dfns")
```

#### CLI

```shell
# List available releases
python -m modflow_devtools.dfns releases

# Sync all available releases
python -m modflow_devtools.dfns sync

# Sync a specific release
python -m modflow_devtools.dfns sync --ref 6.6.0

# Force re-download
python -m modflow_devtools.dfns sync --force

# Show sync status and cache info
python -m modflow_devtools.dfns info

# List available components for a release
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

When enabled, `get_registry()` will automatically sync if no cached files exist for the requested release.

#### Cache location

Downloaded DFN files are cached under:

```
~/.cache/modflow-devtools/dfns/
└── modflow6/
    ├── 6.6.0/
    │   ├── sim-nam.toml
    │   ├── gwf-chd.toml
    │   └── ...
    └── 6.5.0/
        ├── sim-nam.dfn
        ├── gwf-chd.dfn
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
