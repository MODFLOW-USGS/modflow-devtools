# DFNs API Design

This document describes the design of the DFNs (Definition Files) API ([GitHub issue #262](https://github.com/MODFLOW-ORG/modflow-devtools/issues/262)). It is intended to be developer-facing, not user-facing, though users may also find it informative.

This is a living document which will be updated as development proceeds.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->


- [Background](#background)
- [Objective](#objective)
- [Overview](#overview)
- [Architecture](#architecture)
  - [Bootstrap file](#bootstrap-file)
    - [Bootstrap file contents](#bootstrap-file-contents)
    - [Sample bootstrap file](#sample-bootstrap-file)
  - [DFN spec and registry files](#dfn-spec-and-registry-files)
    - [Registry file format](#registry-file-format)
    - [Sample files](#sample-files)
  - [Registry discovery](#registry-discovery)
    - [Discovery modes](#discovery-modes)
    - [Registry discovery procedure](#registry-discovery-procedure)
  - [Registry/DFN caching](#registrydfn-caching)
  - [Registry synchronization](#registry-synchronization)
    - [Manual sync](#manual-sync)
    - [Automatic sync](#automatic-sync)
  - [Source repository integration](#source-repository-integration)
  - [DFN addressing](#dfn-addressing)
  - [Registry classes](#registry-classes)
    - [DfnRegistry (base class)](#dfnregistry-base-class)
    - [RemoteDfnRegistry](#remotedfnregistry)
    - [LocalDfnRegistry](#localdfnregistry)
  - [Module-level API](#module-level-api)
- [Schema Versioning](#schema-versioning)
  - [Separating format from schema](#separating-format-from-schema)
  - [Schema evolution](#schema-evolution)
  - [Tentative v2 schema design](#tentative-v2-schema-design)
- [Component Hierarchy](#component-hierarchy)
- [Schema version support](#schema-version-support)
- [Implementation Dependencies](#implementation-dependencies)
  - [Completed work](#completed-work)
  - [Core components](#core-components)
  - [MODFLOW 6 repository integration](#modflow-6-repository-integration)
  - [Testing and documentation](#testing-and-documentation)
- [Relationship to Models and Programs APIs](#relationship-to-models-and-programs-apis)
- [Design Decisions](#design-decisions)
  - [Use Pooch for fetching](#use-pooch-for-fetching)
  - [Use Pydantic for schema validation](#use-pydantic-for-schema-validation)
  - [Schema versioning strategy](#schema-versioning-strategy)
  - [Future enhancements](#future-enhancements)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Background

The `modflow_devtools.dfns` module currently provides utilities for parsing and working with MODFLOW 6 definition files. Significant work already completed includes:

- Object models for DFN components (`Dfn`, `Block`, `Field` classes)
- Schema definitions for both v1 (legacy) and v2 (in development)
- Parsers for the old DFN format
- Schema mapping capabilities including utilities for converting between flat and hierarchical component representations
- A `fetch_dfns()` function for manually downloading DFN files from the MODFLOW 6 repository
- Validation tools

However, there is currently no registry-based API for:
- Automatically discovering and synchronizing DFN files from remote sources
- Managing multiple versions of definition files simultaneously
- Caching definition files locally for offline use

Users must manually download definition files or rely on whatever happens to be bundled with their installation. This creates similar problems to what the Models API addressed:
1. **Version coupling**: Users are locked to whatever DFN version is bundled
2. **Manual management**: Users must manually track and download DFN updates
3. **No multi-version support**: Difficult to work with multiple MODFLOW 6 versions simultaneously
4. **Maintenance burden**: Developers must manually update bundled DFNs

## Objective

Create a DFNs API that:
1. **Mirrors Models/Programs API patterns** for consistency and familiarity
2. **Leverages existing dfn module work** (parsers, schemas, object models)
3. **Provides automated discovery** of definition files from MODFLOW 6 repository
4. **Supports multiple versions** simultaneously with explicit version addressing
5. **Uses Pooch** for fetching and caching (avoiding custom HTTP client code)
6. **Handles schema evolution** with proper separation of file format vs schema version
7. **Maintains loose coupling** between devtools and remote DFN sources

## Overview

Make the MODFLOW 6 repository responsible for publishing a definition file registry.

Make `modflow-devtools` responsible for:
- Defining the DFN registry publication contract
- Providing registry-creation machinery
- Storing bootstrap information locating the MODFLOW 6 repository
- Discovering remote registries at install time or on demand
- Caching registry metadata and definition files
- Exposing a synchronized view of available definition files
- Parsing and validating definition files
- Mapping between schema versions

MODFLOW 6 is currently the only repository using the DFN specification system, but this leaves the door open for other repositories to begin using it.

## Architecture

The DFNs API will mirror the Models and Programs API architecture, adapted for definition file-specific concerns.

**Implementation approach**: Core classes are split across `modflow_devtools/dfns/__init__.py` (spec/parsing) and `modflow_devtools/dfns/registry.py` (registry infrastructure):
- `get_cache_dir()`: Cache directory path utility
- `BootstrapConfig` / `SourceConfig`: Pydantic models for bootstrap configuration
- `DfnRegistry`: Pydantic base class for registry access
- `RemoteDfnRegistry`: Remote fetching with Pooch integration
- `LocalDfnRegistry`: Local filesystem registry for development use
- `DfnRegistryMeta`: Pydantic model for `dfns.toml` registry file contents
- `DfnSpec`: Full specification with hierarchical and flat access
- `Dfn`, `Block`, `Field`: Core component dataclasses

### Bootstrap file

The **bootstrap** file tells `modflow-devtools` where to look for DFN registries. This file will be checked into the repository at `modflow_devtools/dfns/dfns.toml` and distributed with the package.

#### Bootstrap file contents

At the top level, the bootstrap file consists of a table of `sources`, each describing a repository that publishes definition files.

Each source has:
- `repo`: Repository identifier (owner/name)
- `dfn_path`: Path within the repository to the directory containing DFN files (defaults to `doc/mf6io/mf6ivar/dfn`)
- `registry_path`: Path within the repository to the registry metadata file (defaults to `.registry/dfns.toml`)
- `refs`: List of git refs (branches, tags, or commit hashes) to sync by default

#### User config overlay

Users can customize or extend the bundled bootstrap configuration by creating a user config file at:
- Linux/macOS: `~/.config/modflow-devtools/dfns.toml` (respects `$XDG_CONFIG_HOME`)
- Windows: `%APPDATA%/modflow-devtools/dfns.toml`

The user config follows the same format as the bundled bootstrap file. Sources defined in the user config will override or extend those in the bundled config, allowing users to:
- Add custom DFN repositories
- Point to forks of existing repositories (useful for testing experimental schema versions)
- Override default refs for existing sources

**Implementation note**: The user config path logic (`get_user_config_path("dfn")`) is shared across all three APIs (Models, Programs, DFNs) via `modflow_devtools.config`, but each API implements its own `merge_bootstrap()` function using API-specific bootstrap schemas.

#### Sample bootstrap file

```toml
[sources.modflow6]
repo = "MODFLOW-ORG/modflow6"
dfn_path = "doc/mf6io/mf6ivar/dfn"
registry_path = ".registry/dfns.toml"
refs = [
    "6.6.0",
    "6.5.0",
    "6.4.4",
    "develop",
]
```

### DFN spec and registry files

The registry file (`dfns.toml`) is the metadata file that supports the DFNs API for discovery and distribution.

#### Registry file format

A **`dfns.toml`** registry file for **discovery and distribution** (the specific naming distinguishes it from `models.toml` and `programs.toml`):

```toml
# Registry metadata (top-level, optional)
schema_version = "1.0"
generated_at = "2025-01-02T10:30:00Z"
devtools_version = "1.9.0"

[metadata]
ref = "6.6.0"  # Optional, known from discovery context

# File listings (filenames and hashes, URLs constructed as needed)
[files]
"sim-nam.dfn" = {hash = "sha256:..."}
"sim-tdis.dfn" = {hash = "sha256:..."}
"gwf-nam.dfn" = {hash = "sha256:..."}
"gwf-chd.dfn" = {hash = "sha256:..."}
# ... all DFN files
```

**Notes**:
- Registry is purely **infrastructure** for discovery and distribution
- The `files` section maps filenames to hashes for verification
- URLs are constructed dynamically from bootstrap metadata (repo, ref, dfn_path) + filename
- This allows using personal forks by changing the bootstrap file
- **All registry metadata is optional** - registries can be handwritten minimally

**Minimal handwritten registry**:
```toml
[files]
"sim-nam.dfn" = {hash = "sha256:def456..."}
"gwf-nam.dfn" = {hash = "sha256:789abc..."}
```

#### Sample files

**Per-component TOML files** (current format in the MODFLOW 6 repository):

Each component has its own `.toml` file named by component, e.g. `gwf-chd.toml`:

```toml
name = "gwf-chd"
advanced = false
multi = true

[options.auxiliary]
block = "options"
name = "auxiliary"
type = "string"
shape = "(naux)"
optional = true
description = "..."
# ...
```

The registry lists all component files:
```toml
[files]
"sim-nam.toml" = {hash = "sha256:..."}
"gwf-nam.toml" = {hash = "sha256:..."}
"gwf-chd.toml" = {hash = "sha256:..."}
# ... all component files
```

**Single-blob TOML** (output of `DfnSpec.dump()`, used for `mf6 --spec`):

`DfnSpec.dump()` serializes the entire spec as a single TOML document with each component as a top-level key:

```toml
schema_version = "2"

["gwf-chd"]
name = "gwf-chd"
advanced = false
multi = true

["gwf-chd".options.auxiliary]
block = "options"
name = "auxiliary"
# ...

["gwf-dis"]
name = "gwf-dis"
# ...
```

This format requires no preprocessing — consumers can pipe `mf6 --spec` output directly into `tomllib`. Hierarchy is preserved via `parent` attributes embedded in each component's data, and can be reconstructed by `DfnSpec.load()` using naming convention inference (`to_tree()`).

### Registry discovery

DFN registries can be discovered in two modes, similar to the Models API.

#### Discovery modes

**1. Registry as version-controlled file**:

Registry files can be versioned in the repository at a conventional path, in which case discovery uses GitHub raw content URLs:

```
https://raw.githubusercontent.com/{org}/{repo}/{ref}/.registry/dfns.toml
```

This mode supports any git ref (branches, tags, commit hashes).

**2. Registry as release asset**:

Registry files can also be published as release assets:

```
https://github.com/{org}/{repo}/releases/download/{tag}/dfns.toml
```

This mode:
- Requires release tags only
- Allows registry generation in CI without committing to repo
- Provides faster discovery (no need to check multiple ref types)

**Discovery precedence**: Release asset mode takes precedence if both exist (same as Models API).

#### Registry discovery procedure

At sync time, `modflow-devtools` discovers remote registries for each configured ref:

1. **Check for release tag** (if release asset mode enabled):
   - Look for a GitHub release with the specified tag
   - Try to fetch `dfns.toml` from release assets
   - If found, use it and skip step 2
   - If release exists but lacks registry asset, fall through to step 2

2. **Check for version-controlled registry**:
   - Look for a commit hash, tag, or branch matching the ref
   - Try to fetch registry from `{registry_path}` via raw content URL
   - If found, use it
   - If ref exists but lacks registry file, raise error:
     ```python
     DfnRegistryDiscoveryError(
         f"Registry file not found in {registry_path} for 'modflow6@{ref}'"
     )
     ```

3. **Failure case**:
   - If no matching ref found at all, raise error:
     ```python
     DfnRegistryDiscoveryError(
         f"Registry discovery failed, ref 'modflow6@{ref}' does not exist"
     )
     ```

**Note**: For initial implementation, focus on version-controlled mode. Release asset mode requires MODFLOW 6 to start distributing DFN files with releases (currently they don't), but would be a natural addition once that happens.

### Registry/DFN caching

Cache structure mirrors the Models API pattern:

```
~/.cache/modflow-devtools/
├── dfn/
│   ├── registries/
│   │   └── modflow6/              # by source repo
│   │       ├── 6.6.0/
│   │       │   └── dfns.toml
│   │       ├── 6.5.0/
│   │       │   └── dfns.toml
│   │       └── develop/
│   │           └── dfns.toml
│   └── files/                     # Actual DFN files, managed by Pooch
│       └── modflow6/
│           ├── 6.6.0/
│           │   ├── sim-nam.dfn
│           │   ├── gwf-nam.dfn
│           │   └── ...
│           ├── 6.5.0/
│           │   └── ...
│           └── develop/
│               └── ...
```

**Cache management**:
- Registry files cached per source repository and ref
- DFN files fetched and cached individually by Pooch, verified against registry hashes
- Cache persists across Python sessions for offline use
- Cache can be cleared with `dfn clean` command
- Users can check cache status with `dfn info`

### Registry synchronization

Synchronization updates the local registry cache with remote metadata.

#### Manual sync

Exposed as a CLI command and Python API:

```bash
# Sync all configured refs
python -m modflow_devtools.dfns sync

# Sync specific ref
python -m modflow_devtools.dfns sync --ref 6.6.0

# Sync to any git ref (branch, tag, commit hash)
python -m modflow_devtools.dfns sync --ref develop
python -m modflow_devtools.dfns sync --ref f3df630a

# Force re-download
python -m modflow_devtools.dfns sync --force

# Show sync status
python -m modflow_devtools.dfns info

# List available DFNs for a ref
python -m modflow_devtools.dfns list --ref 6.6.0

# List all synced refs
python -m modflow_devtools.dfns list
```

Or via Python API:

```python
from modflow_devtools.dfns import sync_dfns, get_sync_status

# Sync all configured refs
sync_dfns()

# Sync specific ref
sync_dfns(ref="6.6.0")

# Check sync status
status = get_sync_status()
```

#### Automatic sync

- **At install time**: Best-effort sync to default refs during package installation (fail silently on network errors)
- **On first use**: If registry cache is empty for requested ref, attempt to sync before raising errors
- **Lazy loading**: Don't sync until DFN access is actually requested
- **Configurable (Experimental)**: Auto-sync is opt-in via environment variable: `MODFLOW_DEVTOOLS_AUTO_SYNC=1` (set to "1", "true", or "yes")

### Source repository integration

For the MODFLOW 6 repository to integrate:

1. **Generate registry** in CI:
   ```bash
   # In MODFLOW 6 repository CI
   python -m modflow_devtools.dfns.make_registry \
     --dfn-path doc/mf6io/mf6ivar/dfn \
     --output .registry/dfns.toml \
     --ref ${{ github.ref_name }}
   ```

2. **Commit registry** to `.registry/dfns.toml`

3. **Example CI integration** (GitHub Actions):
   ```yaml
   - name: Generate DFN registry
     run: |
       pip install modflow-devtools
       python -m modflow_devtools.dfns.make_registry \
         --dfn-path doc/mf6io/mf6ivar/dfn \
         --output .registry/dfns.toml \
         --ref ${{ github.ref_name }}

   - name: Commit registry
     run: |
       git config user.name "github-actions[bot]"
       git config user.email "github-actions[bot]@users.noreply.github.com"
       git add .registry/dfns.toml
       git diff-index --quiet HEAD || git commit -m "chore: update DFN registry"
       git push
   ```

**Note**: Initially generate registries for version-controlled mode. Release asset mode would require MODFLOW 6 to start distributing DFNs with releases.

### DFN addressing

**Format**: `mf6@{ref}/{component}`

Components include:
- `ref`: Git ref (branch, tag, or commit hash) corresponding to a MODFLOW 6 version
- `component`: DFN component name (without file extension)

Examples:
- `mf6@6.6.0/sim-nam` - Simulation name file definition for MODFLOW 6 v6.6.0
- `mf6@6.6.0/gwf-chd` - GWF CHD package definition for v6.6.0
- `mf6@develop/gwf-wel` - GWF WEL package definition from develop branch
- `mf6@f3df630a/gwt-adv` - GWT ADV package definition from specific commit

**Benefits**:
- Explicit versioning prevents confusion
- Supports multiple MODFLOW 6 versions simultaneously
- Enables comparison between versions
- Works with any git ref (not just releases)

**Note**: The source is always "mf6" (MODFLOW 6), but the addressing scheme allows for future sources if needed.

### Registry classes

The registry class hierarchy is based on a Pydantic `DfnRegistry` base class (in `modflow_devtools/dfns/registry.py`):

**`DfnRegistry` (base class)**:
- Pydantic model with `source` and `ref` fields
- Abstract `spec` property and `get_dfn_path()` method for subclasses to implement
- Concrete helpers:
  - `get_dfn(component)` - convenience for `spec[component]`
  - `schema_version` - convenience for `spec.schema_version`
  - `components` - convenience for `dict(spec.items())`

**`RemoteDfnRegistry(DfnRegistry)`**:

Handles remote registry discovery, caching, and DFN fetching. Constructs DFN file URLs dynamically from `BootstrapConfig`/`SourceConfig` — URLs are never stored in the registry file itself.

Optional field overrides (`repo`, `dfn_path`, `registry_path`) allow bypassing the bootstrap config, e.g. for testing against a personal fork:

```python
# Use bootstrap config (normal usage)
registry = RemoteDfnRegistry(source="modflow6", ref="6.6.0")

# Override repo directly (e.g., testing a fork)
registry = RemoteDfnRegistry(
    source="modflow6",
    ref="registry",
    repo="wpbonelli/modflow6",
)
```

Key methods: `sync(force=False)`, `get_dfn_path(component)`, `registry_meta` property.

**`LocalDfnRegistry(DfnRegistry)`**:

For developers working with a local DFN directory:

```python
registry = LocalDfnRegistry(path="/path/to/mf6/doc/mf6io/mf6ivar/dfn")
dfn = registry.get_dfn("gwf-chd")
```

Loads `DfnSpec` lazily via `DfnSpec.load(path)` on first access.

**Supporting Pydantic models** (in `registry.py`):
- `BootstrapConfig` / `SourceConfig`: bootstrap file schema (sources, refs, paths)
- `DfnRegistryMeta`: `dfns.toml` registry file schema (schema_version, generated_at, files)
- `DfnRegistryFile`: per-file entry with SHA256 hash

**Design decisions**:
- **Pydantic-based** (not ABC) — allows Pydantic validation and field introspection
- **Dynamic URL construction** — DFN file URLs constructed at runtime from bootstrap metadata, not stored in registry files
- **No `MergedRegistry`** — users work with one MODFLOW 6 version at a time

### Module-level API

Convenient module-level functions:

```python
from modflow_devtools.dfns import (
    DfnSpec,
    get_dfn,
    get_dfn_path,
    list_components,
    sync_dfns,
    get_registry,
    map,
)

# Get individual DFNs (defaults to ref="develop")
dfn = get_dfn("gwf-chd")
dfn = get_dfn("gwf-chd", ref="6.5.0")  # Specific version

# Get file path
path = get_dfn_path("gwf-wel", ref="6.6.0")

# List available components
components = list_components(ref="6.6.0")

# Work with specific registry
registry = get_registry(ref="6.6.0")
gwf_nam = registry.get_dfn("gwf-nam")

# Load full specification - single canonical hierarchical representation
spec = DfnSpec.load("/path/to/dfns")  # Load from directory

# Hierarchical access
spec.schema_version  # Version('2') when loaded from legacy .dfn files (auto-mapped)
spec.root  # Root Dfn (simulation component)
spec.root.children["gwf-nam"]  # Navigate hierarchy
spec.root.children["gwf-nam"].children["gwf-chd"]

# Flat dict-like access via Mapping protocol
gwf_chd = spec["gwf-chd"]  # Get component by name
for name, dfn in spec.items():  # Iterate all components
    print(name)
len(spec)  # Total number of components

# Access spec through registry (registry provides the spec)
registry = get_registry(ref="6.6.0")
spec = registry.spec  # Registry wraps a DfnSpec
gwf_chd = registry.spec["gwf-chd"]

# Map between schema versions
dfn_v1 = get_dfn("gwf-chd", ref="6.4.4")  # Older version in v1 schema
dfn_v2 = map(dfn_v1, schema_version="2")  # Convert to v2 schema
```

**`DfnSpec` class**:

The `DfnSpec` dataclass represents the full specification with a single canonical hierarchical representation:

```python
from collections.abc import Mapping
from dataclasses import dataclass

@dataclass
class DfnSpec(Mapping):
    """Full DFN specification with hierarchical structure and flat dict access."""

    schema_version: str
    root: Dfn  # Hierarchical canonical representation (simulation component)

    # Mapping protocol - provides flat dict-like access
    def __getitem__(self, name: str) -> Dfn:
        """Get component by name (flattened lookup)."""
        ...

    def __iter__(self):
        """Iterate over all component names."""
        ...

    def __len__(self):
        """Total number of components in the spec."""
        ...

    @classmethod
    def load(cls, path: Path | str) -> "DfnSpec":
        """
        Load specification from a directory of DFN files.

        The specification is always loaded as a hierarchical tree,
        with flat access available via the Mapping protocol.
        """
        ...
```

**Design benefits**:
- **Single canonical representation**: Hierarchical tree is the source of truth
- **Flat access when needed**: Mapping protocol provides dict-like interface
- **Simple, focused responsibility**: `DfnSpec` only knows how to load from a directory
- **Clean layering**: Registries built on top of `DfnSpec`, not intertwined
- **Clean semantics**: `DfnSpec` = full specification, `Dfn` = individual component
- **Pythonic**: Implements standard `Mapping` protocol

**Separation of concerns**:
- **`DfnSpec`**: Canonical representation of the full specification (foundation)
  - Loads from a directory of DFN files via `load()` classmethod
  - Hierarchical tree via `.root` property
  - Flat dict access via `Mapping` protocol
  - No knowledge of registries, caching, or remote sources
- **Registries**: Handle discovery, distribution, and caching (built on DfnSpec)
  - Fetch and cache DFN files from remote sources
  - Internally use `DfnSpec` to represent the loaded specification
  - Provide access via `.spec` property
  - `get_dfn(component)` → convenience for `spec[component]`
  - `get_dfn_path(component)` → returns cached file path

Backwards compatibility with existing `fetch_dfns()`:

```python
# Old API — still works for manual downloads (stable modflow_devtools.dfn module)
from modflow_devtools.dfn import get_dfns
get_dfns("MODFLOW-ORG", "modflow6", "6.6.0", "/tmp/dfns")

# New API (preferred - uses registry and caching)
from modflow_devtools.dfns import sync_dfns, get_registry, DfnSpec
sync_dfns(ref="6.6.0")
registry = get_registry(ref="6.6.0")
spec = registry.spec  # Registry wraps a DfnSpec
```

## Schema Versioning

A key design consideration is properly handling schema evolution while separating file format from schema version.

### Separating format from schema

As discussed in [issue #259](https://github.com/MODFLOW-ORG/modflow-devtools/issues/259), **file format and schema version are orthogonal concerns**:

**File format** (serialization):
- `dfn` - Legacy DFN text format
- `toml` - Modern TOML format (or potentially YAML, see below)

The format is simply how the data is serialized to disk. Any schema version can be serialized in any supported format.

**Schema version** (structural specification):
- Defines what components exist and how they relate to each other
- Defines which variables each component contains
- Defines variable types, shapes, and constraints
- Separates structural specification from input format representation concerns

The schema describes the semantic structure and meaning of the specification, independent of how it's serialized.

**Key distinction**: The schema migration is about separating structural specification (components, relationships, variables, types) from input format representation. This is discussed in detail in [pyphoenix-project issue #246](https://github.com/modflowpy/pyphoenix-project/issues/246).

For example:
- **Input format issue** (v1): Period data defined as recarrays with artificial dimensions like `maxbound`
- **Structural reality** (v2): Each column is actually a variable living on (a subset of) the grid, using semantically meaningful dimensions

The v1 schema conflates:
- **Structural information**: Components, their relationships, and variables within each component
- **Format information**: How MF6 allows arrays to be provided, when keywords like `FILEIN`/`FILEOUT` are necessary

The v2 schema should treat these as **separate layers**, where consumers can selectively apply formatting details atop a canonical data model.

**Current state**:
- The code supports loading both `dfn` and `toml` formats
- The `Dfn.load()` function accepts a `format` parameter
- Schema version is determined independently of file format
- V1→V1.1 and V1→V2 schema mapping is implemented

**Implications for DFNs API**:
- Registry metadata includes both `format` and `schema_version` fields
- Registries can have different formats at different refs (some refs: dfn, others: toml)
- The same schema version can be serialized in different formats
- Schema mapping happens after loading, independent of file format
- Users can request specific schema versions via `map()` function

### Schema evolution

**v1 schema** (original):
- Current MODFLOW 6 releases through 6.6.x
- Flat structure with `in_record`, `tagged`, `preserve_case`, etc. attributes
- Mixes structural specification with input format representation (recarray/maxbound issue)
- Can be serialized as `.dfn` (original) or `.toml`

**v1.1 schema** (intermediate):
- Cleaned-up v1 with data normalization
- Removed unnecessary attributes (`in_record`, `tagged`, etc.)
- Structural improvements (period block arrays separated into individual variables)
- Better parent-child relationships inferred from naming conventions
- Can be serialized as `.dfn` or `.toml`
- **Recommendation from issue #259**: Use this as the mainline, not jump to v2

**v2 schema** (future - comprehensive redesign):
- For devtools 2.x / FloPy 4.x / eventually MF6
- **Explicit parent-child relationships** via `parent` attributes in per-component TOML files (no inference needed)
- **Complete separation of structural specification from input format concerns** (see [pyphoenix-project #246](https://github.com/modflowpy/pyphoenix-project/issues/246))
  - Structural layer: components, relationships, variables, data models
  - Format layer: how MF6 allows arrays to be provided, FILEIN/FILEOUT keywords, etc.
  - Consumers can selectively apply formatting details atop canonical data model
- **Explicit parent-child relationships in DFN files** (see Component Hierarchy section)
- Modern type system with proper array types and semantically meaningful dimensions
- Consolidated attribute representation (see Tentative v2 schema design)
- Likely serialized as TOML or YAML (with JSON-Schema validation via Pydantic)

**DFNs API strategy**:
- Support all schema versions via registry metadata
- Provide transparent schema mapping where needed
- Default to native schema version from registry
- Allow explicit schema version selection via API
- Maintain backwards compatibility during transitions

### Tentative v2 schema design

Based on feedback from mwtoews in [PR #229](https://github.com/MODFLOW-ORG/modflow-devtools/pull/229) and the structural/format separation discussed in [pyphoenix-project #246](https://github.com/modflowpy/pyphoenix-project/issues/246):

**Structural vs format separation**:
The v2 schema should cleanly separate:
- **Structural specification**: Component definitions, relationships, variable data models
  - Generated classes encode only structure and data models
  - Use semantically meaningful dimensions (grid dimensions, time periods)
- **Format specification**: How MF6 reads/writes the data (separate layer)
  - I/O layers exclusively handle input format concerns
  - FILEIN/FILEOUT keywords, array input methods, etc.

**Consolidated attributes**: Replace individual boolean fields with an `attrs` list:
```toml
# Instead of this (v1/v1.1):
optional = true
time_series = true
layered = false

# Use this (v2):
attrs = ["optional", "time_series"]
```

**Array syntax for shapes**: Use actual arrays instead of string representations:
```toml
# Instead of this (v1/v1.1):
shape = "(nper, nnodes)"

# Use this (v2):
shape = ["nper", "nnodes"]
```

**Format considerations**:
- **TOML vs YAML**: YAML's more forgiving whitespace better accommodates long descriptions (common for scientific parameters)
- **Validation approach**: Use Pydantic for both schema definition and validation
  - Pydantic provides rigorous validation (addresses pyphoenix-project #246 requirement for formal specification)
  - Built-in validation after parsing TOML/YAML to dict (no custom parsing logic)
  - Automatic JSON-Schema generation for documentation and external tooling
  - More Pythonic than using `python-jsonschema` directly

**Pydantic integration**:
```python
from pydantic import BaseModel, Field
from typing import Any

class FieldV2(BaseModel):
    name: str
    type: str
    block: str | None = None
    shape: list[str] | None = None
    attrs: list[str] = Field(default_factory=list)
    description: str = ""
    default: Any = None
    children: dict[str, "FieldV2"] | None = None

# Usage:
# 1. Parse TOML/YAML to dict (using tomli/pyyaml/etc)
# 2. Validate with Pydantic (built-in)
parsed = tomli.load(f)
field = FieldV2(**parsed)  # Validates automatically

# 3. Export JSON-Schema if needed (for docs, external tools)
schema = FieldV2.model_json_schema()
```

Benefits:
- **Validation and schema in one**: Pydantic handles both, no separate validation library needed
- **Type safety**: Full Python type hints and IDE support
- **JSON-Schema export**: Available for documentation and external tooling
- **Widely adopted**: Well-maintained, used throughout Python ecosystem
- **Better UX**: Clear error messages, better handling of multi-line descriptions (if using YAML)

## Component Hierarchy

Component parent-child relationships are inferred from naming conventions by `to_tree()`. No separate specification file is required.

**Current inference rules** (in `to_tree()`):
- `sim-nam` has no parent (root)
- `*-nam` components (e.g. `gwf-nam`, `gwt-nam`) are children of `sim-nam`
- `exg-*`, `sln-*`, `utl-*` components are children of `sim-nam`
- All other `<model>-<pkg>` components (e.g. `gwf-chd`) are children of `<model>-nam`

This inference is applied during `DfnSpec.load()` regardless of whether the underlying DFN files are legacy `.dfn` format or TOML. For v2 TOML files, `parent` attributes in individual component files are respected when present and take precedence over inference.

**Planned for v2**: Explicit parent-child relationships via `parent` attributes in per-component TOML files, eliminating reliance on naming conventions. The `to_tree()` inference will remain as a fallback for v1/v1.1 compatibility.

## Schema version support

The DFNs API will support **multiple schema versions simultaneously**:

```python
# Schema version is tracked per registry/ref
registry_v1 = get_registry(ref="6.4.4")  # MODFLOW 6.4.4 uses v1 schema
registry_v11 = get_registry(ref="6.6.0")  # MODFLOW 6.6.0 uses v1.1 schema
registry_v2 = get_registry(ref="develop")  # Future: develop uses v2 schema

# Get DFN in native schema version
dfn_v1 = registry_v1.get_dfn("gwf-chd")  # Returns v1 schema
dfn_v11 = registry_v11.get_dfn("gwf-chd")  # Returns v1.1 schema

# Transparently map to desired schema version
from modflow_devtools.dfns import map
dfn_v2 = map(dfn_v1, schema_version="2")  # v1 → v2
dfn_v2 = map(dfn_v11, schema_version="2")  # v1.1 → v2
```

**Registry support**:
- Each registry metadata includes `schema_version` (from component files or inferred)
- Different refs can have different schema versions
- `RemoteDfnRegistry` loads appropriate schema version for each ref
- `load()` function detects schema version and uses appropriate parser/validator

**Schema detection**:
```python
# In RemoteDfnRegistry or DfnSpec.load()
def _detect_schema_version(self) -> Version:
    # 1. Infer from component file content (schema_version field)
    sample_dfn = self._load_sample_dfn()
    return infer_schema_version(sample_dfn)

    # 2. Default to latest stable
    return Version("1.1")
```


## Implementation Dependencies

### Completed work

The `modflow_devtools.dfns` package is implemented in full. The following is a summary of what exists:

- ✅ `Dfn`, `Block`, `Field` dataclasses (in `__init__.py`)
- ✅ Schema definitions (`FieldV1`, `FieldV2`) (in `schema/`)
- ✅ Parsers for both DFN and TOML formats (`parse.py`, `load()`, `load_flat()`, `load_tree()`)
- ✅ Schema mapping (V1 → V2) with `MapV1To2`
- ✅ Hierarchy inference via `to_tree()` / `to_flat()`
- ✅ `DfnSpec` dataclass with `Mapping` protocol and `load()` classmethod
- ✅ `DfnSpec.dump()` / `DfnSpec.dumps()` — serialize full spec as single TOML blob
- ✅ Validation utilities (`is_valid()`)
- ✅ `dfn2toml` conversion tool (`dfn2toml.py`)
- ✅ Bootstrap file and registry schema (`BootstrapConfig`, `SourceConfig`, `DfnRegistryMeta`)
- ✅ Registry classes (`DfnRegistry`, `RemoteDfnRegistry`, `LocalDfnRegistry`) (in `registry.py`)
- ✅ Registry discovery and synchronization (`sync_dfns()`, `get_sync_status()`)
- ✅ Pooch integration for file caching
- ✅ Module-level convenience API (`get_dfn`, `get_dfn_path`, `list_components`, `get_registry`)
- ✅ CLI (`__main__.py`): `sync`, `info`, `list`, `clean`
- ✅ Registry generation tool (`make_registry.py`)
- ⚠️ Integration with MODFLOW 6 CI (requires registry branch merge in MF6 repo)

The legacy `modflow_devtools.dfn` module (`dfn.py`) remains alongside the new package for backwards compatibility.

**Implementation status** (DFNs API):
- ✅ Bootstrap file and registry schema (`BootstrapConfig`, `SourceConfig`, `DfnRegistryMeta`)
- ✅ Registry discovery and synchronization
- ✅ Pooch integration for file caching
- ✅ Registry classes (`DfnRegistry`, `RemoteDfnRegistry`, `LocalDfnRegistry`)
- ✅ CLI commands (sync, info, list, clean)
- ✅ Module-level convenience API (`get_dfn`, `get_dfn_path`, `list_components`, `sync_dfns`, `get_registry`)
- ✅ Registry generation tool (`make_registry.py`)
- ✅ `DfnSpec.dump()` / `DfnSpec.dumps()` — serialize full spec as single TOML blob
- ⚠️ Integration with MODFLOW 6 CI (requires registry branch merge in MF6 repo)

### Core components

**Foundation** (no dependencies):
1. ✅ Core dfns package (schema, parser, utility code) — already merged
2. Add bootstrap file (`modflow_devtools/dfns/dfns.toml`)
3. Define registry schema with Pydantic (handles validation and provides JSON-Schema export)
4. Implement registry discovery logic
5. Create cache directory structure utilities

**Registry infrastructure** (depends on Foundation):
1. Add Pooch as dependency
2. Implement `DfnRegistry` abstract base class
3. Implement `RemoteDfnRegistry` with Pooch for file fetching
4. Refactor existing code into `LocalDfnRegistry`
5. Implement `sync_dfns()` function
6. Add registry metadata caching with hash verification
7. Implement version-controlled registry discovery
8. Add auto-sync on first use (opt-in via `MODFLOW_DEVTOOLS_AUTO_SYNC` while experimental)
9. **Implement `DfnSpec` dataclass** with `Mapping` protocol for single canonical hierarchical representation with flat dict access

**CLI and module API** (depends on Registry infrastructure):
1. Create `modflow_devtools/dfns/__main__.py`
2. Add commands: `sync`, `info`, `list`, `clean`
3. Add `--ref` flag for version selection
4. Add `--force` flag for re-download
5. Add convenience functions (`get_dfn`, `get_dfn_path`, `list_components`, etc.)
6. Default `ref="develop"` in `get_registry()` / `get_dfn()` etc. for "latest" access
7. Maintain backwards compatibility with `fetch_dfns()`

**Registry generation tool** (depends on Foundation):
1. Implement `modflow_devtools/dfns/make_registry.py`
2. Scan DFN directory and generate **registry file** (`dfns.toml`): file listings with hashes
3. Compute file hashes (SHA256) for all DFN/TOML files
4. Registry output: just filename -> hash mapping (no URLs - constructed dynamically)
5. Support both full output (for CI) and minimal output (for handwriting)
6. For v1/v1.1: infer hierarchy from naming conventions for validation
7. For v2: read explicit `parent` attributes from component files for validation

### MODFLOW 6 repository integration

**CI workflow** (depends on Registry generation tool):
1. Install modflow-devtools in MODFLOW 6 CI
2. Generate registry on push to develop and release tags
3. Commit registry to `.registry/dfns.toml`
4. Test registry discovery and sync
5. **Note**: No separate `spec.toml` is needed — hierarchy is inferred from naming conventions for v1/v1.1, or read from `parent` attributes in component files for v2

**Bootstrap configuration** (depends on MODFLOW 6 CI):
1. Add stable MODFLOW 6 releases to bootstrap refs (6.6.0, 6.5.0, etc.)
2. Include `develop` branch for latest definitions
3. Test multi-ref discovery and sync

### Testing and documentation

**Testing** (depends on all core components):
1. Unit tests for registry classes
2. Integration tests for sync mechanism
3. Network failure scenarios
4. Multi-version scenarios
5. Schema mapping tests (v1 → v1.1 → v2)
6. Both file format tests (dfn and toml)
7. Backwards compatibility tests with existing FloPy usage

**Documentation** (can be done concurrently with implementation):
1. Update `docs/md/dfn.md` with API examples
2. Document format vs schema separation clearly
3. Document schema evolution roadmap (v1 → v1.1 → v2)
4. Document component hierarchy approach (explicit in DFN files for v2)
5. Add migration guide for existing code
6. CLI usage examples
7. MODFLOW 6 CI integration guide

## Relationship to Models and Programs APIs

The DFNs API deliberately mirrors the Models and Programs API architecture for consistency:

| Aspect | Models API | Programs API | **DFNs API** |
|--------|-----------|--------------|--------------|
| **Bootstrap file** | `models/models.toml` | `programs/programs.toml` | `dfns/dfns.toml` |
| **Registry format** | TOML with files/models/examples | TOML with programs/binaries | TOML with files/components/hierarchy |
| **Discovery** | Release assets or version control | Release assets only | Version control (+ release assets future) |
| **Caching** | `~/.cache/.../models` | `~/.cache/.../programs` | `~/.cache/.../dfn` |
| **Addressing** | `source@ref/path/to/model` | `program@version` | `mf6@ref/component` |
| **CLI** | `models sync/info/list` | `programs sync/info/install` | `dfns sync/info/list/clean` |
| **Primary use** | Access model input files | Install program binaries | Parse definition files |

**Key differences**:
- DFNs API focuses on metadata/parsing, not installation
- DFNs API leverages existing parser infrastructure (Dfn, Block, Field classes)
- DFNs API handles schema versioning/mapping (format vs schema separation)
- DFNs API supports both flat and hierarchical representations

**Shared patterns**:
- Bootstrap-driven discovery
- Remote sync with Pooch caching
- Ref-based versioning (branches, tags, commits)
- CLI command structure
- Lazy loading / auto-sync on first use
- Environment variable opt-out for auto-sync

This consistency benefits both developers and users with a familiar experience across all three APIs.

## Cross-API Consistency

The DFNs API follows the same design patterns as the Models and Programs APIs for consistency. See the **Cross-API Consistency** section in `models.md` for full details.

**Key shared patterns**:
- Pydantic-based registry classes (not ABCs)
- Dynamic URL construction (URLs built at runtime, not stored in registries)
- Bootstrap and user config files with identical naming (`dfns.toml`), distinguished by location
- Top-level `schema_version` metadata field
- Distinctly named registry file (`dfns.toml`)
- Shared config utility: `get_user_config_path("dfn")`

**Unique to DFNs API**:
- Discovery via version control (release assets mode planned for future)
- Extra `dfn_path` bootstrap field (location of DFN files within repo)
- Schema versioning and mapping capabilities
- No `MergedRegistry` (users work with one MF6 version at a time)

## Design Decisions

### Use Pooch for fetching

Following the recommendation in [issue #262](https://github.com/MODFLOW-ORG/modflow-devtools/issues/262), the DFNs API will use Pooch for fetching to avoid maintaining custom HTTP client code. This provides:

- **Automatic caching**: Pooch handles local caching with verification
- **Hash verification**: Ensures file integrity
- **Progress bars**: Better user experience for downloads
- **Well-tested**: Pooch is mature and widely used
- **Consistency**: Same approach as Models API

### Use Pydantic for schema validation

Pydantic will be used for defining and validating DFN schemas (both registry schemas and DFN content schemas):

- **Built-in validation**: No need for separate validation libraries like `python-jsonschema`
- **Type safety**: Full Python type hints and IDE support
- **JSON-Schema export**: Can generate JSON-Schema for documentation and external tooling
- **Developer experience**: Clear error messages, good Python integration
- **Justification**: Widely adopted, well-maintained, addresses the formal specification requirement from [pyphoenix-project #246](https://github.com/modflowpy/pyphoenix-project/issues/246)

### Schema versioning strategy

Based on [issue #259](https://github.com/MODFLOW-ORG/modflow-devtools/issues/259):

- **Separate format from schema**: Registry metadata includes both
- **Support v1.1 as mainline**: Don't jump straight to v2
- **Backwards compatible**: Continue supporting v1 for existing MODFLOW 6 releases
- **Schema mapping**: Provide transparent conversion via `map()` function
- **Future-proof**: Design allows for v2 when ready (devtools 2.x / FloPy 4.x)

### Future enhancements

1. **Release asset mode**: Add support for registries as release assets (in addition to version control)
2. **Registry compression**: Compress registry files for faster downloads
3. **Partial updates**: Diff-based registry synchronization
4. **Offline mode**: Explicit offline mode that never attempts sync
5. **Conda integration**: Coordinate with conda-forge for bundled DFN packages
6. **Multi-source support**: Support definition files from sources other than MODFLOW 6
7. **Validation API**: Expose validation functionality for user-provided input files
8. **Diff/compare API**: Compare DFNs across versions to identify changes
