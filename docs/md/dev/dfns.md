# DFNs API

This document describes the design and architecture of the `modflow_devtools.dfns` module. It is intended for developers working on or extending `modflow-devtools`.

## Background

MODFLOW 6 describes its input format in *definition files* (DFNs). The `modflow_devtools.dfns` module provides a structured, typed Python API for loading and navigating those definitions.

The module complements the older `modflow_devtools.dfn` module, which provides simpler utilities for parsing the legacy flat text format. `modflow_devtools.dfn` remains stable; `modflow_devtools.dfns` is experimental and may change.

## Architecture overview

The module is split across three files:

| File | Responsibility |
|---|---|
| `schema.py` | Pydantic models for all field types, blocks, and components; the `Dfns` top-level class |
| `registry.py` | Registry classes for local and remote DFN sources |
| `mapper.py` | Maps v1 `.dfn`-format data to the v2 schema used by `schema.py` |
| `__main__.py` | CLI entry point (`sync`, `info`, `clean`) |
| `dfns.toml` | Bundled list of default remote release IDs |

## Schema (`schema.py`)

### Field types

Fields are Pydantic models, all inheriting from `FieldBase`. Scalar types are `Keyword`, `String`, `Integer`, `Double`, and `File`. Composite types are `Array`, `Record`, `Union`, and `List`. Each has a frozen `type` literal discriminator field, which drives Pydantic's discriminated-union validation.

`FieldBase.from_dict(d, strict=False)` is the low-level factory: it reads the `type` key and dispatches to the appropriate subclass.

### Blocks

`Block` is a Pydantic model with `name`, `fields` (ordered dict), and `repeats`. Its `optional` property is derived: a block is optional iff all its fields are optional.

`Blocks` is a type alias for `Mapping[str, Block]`.

### Components

Three component types are distinguished by a `type` discriminator:

- `Simulation` — always the root; `parent` is `null`
- `Model` — adds a `solution` field (compatible solution type)
- `Package` — adds `multi` (bool) and `subtype`

`Component` is an annotated discriminated union of the three.

`ComponentBase` is the shared Pydantic base class. It carries `name`, `blocks`, `parent`, `schema_version`, and `derived_dims`.

### `Dfns`

`Dfns` is a Pydantic model that holds a `components` dict. It is the top-level object produced by loading a directory of DFN files.

Key members:

| Member | Type | Description |
|---|---|---|
| `components` | `dict[str, Component]` | All components, keyed by name |
| `schema_version` | `str` (computed) | Version string from components, or `"2"` |
| `root` | `Simulation \| None` | The simulation component, or `None` |
| `children_of(name)` | `dict[str, Component]` | All components whose `parent == name` |
| `explicit_dims_for(name)` | `set[str]` | Explicit dimension names for a component |
| `grid_dims_for(name)` | `set[str]` | Dims inherited from other components |
| `load(path)` | classmethod | Load a directory of `.dfn` or `.toml` files |

`Dfns.load()` supports both formats in the same directory. `.dfn` files are parsed by the `modflow_devtools.dfn.schema` module and then mapped to v2 schema objects via `mapper.map`. TOML files carry v2 content directly and are loaded with `tomli` and passed straight to the Pydantic validator.

Two model validators run at construction time:
- `_validate_schema_version_consistency` — all non-null `schema_version` values must agree.
- `_validate_dims_and_shapes` — validates `derived_dims` expressions and all `Array.shape` elements.

### Array dimension validation

The validation logic in `schema.py` is non-trivial. Three resolution scopes are checked for each shape element:

1. **Local explicit dims** — `Integer` or `Array` fields with a `dimension` attribute.
2. **Local derived dims** — entries in `component.derived_dims`.
3. **Grid dims** — explicit dims from other components in the spec, filtered by scope.
4. **Intra-record sibling** — fallback for array subfields of records; resolves to a sibling `Integer` with `dimension="record"`.

Row-level column lookup expressions (`block.column(fk_field)`) are also validated structurally.

`derived_dims` expressions are validated for well-formedness (Python arithmetic syntax), operand scope, and absence of cycles (topological sort).

## Mapper (`mapper.py`)

The mapper converts a v1 `Dfn` object (from `modflow_devtools.dfn.schema`) to a v2 `Component`. The entry point is `map(dfn: v1.Dfn) -> Component`. It raises `ValueError` if the input schema version is not `"1"` or `"1.1"`.

Component type is inferred from the component name:
- `sim-nam` → `Simulation`
- `*-nam` → `Model`
- `sln-*` → `Package(subtype="solution")`
- `exg-*` → `Package(subtype="exchange")`
- `utl-*` → `Package(subtype="utility")`
- advanced flag set → `Package(subtype="advanced")`
- all others → `Package`

v1 field types are mapped to v2 equivalents. `recarray` fields become `List` with a nested `Record` item. `record` fields become `Record`. `in_record` fields are promoted into their enclosing record's `fields` dict.

## Registry (`registry.py`)

### `DfnRegistry`

Pydantic base class. Declares a `_spec` private attribute and stubs `spec` and `get_path()` for subclasses.

### `LocalDfnRegistry`

Takes a `path` field. On first access to `.spec`, calls `Dfns.load(self.path)` and caches the result. `get_path(component)` searches for `<component>.dfn` then `<component>.toml` in the directory.

### `RemoteDfnRegistry`

Takes a `release_id` string of the form `"owner/repo@tag"`, where `tag` may be a specific version string or `"latest"`.

**Tag resolution**: `latest_tag()` returns the tag part directly if it's not `"latest"`. For `"latest"`, it queries the GitHub API (`/releases/latest`) once and caches the result in `_latest`.

**Cache path**: `~/.cache/modflow-devtools/dfns/{owner}/{repo}/{resolved_tag}/` on Unix; `%LOCALAPPDATA%/...` on Windows. Respects `XDG_CACHE_HOME`.

**Sync**: `sync(force=False)` downloads `dfns.zip` from `https://github.com/{repo}/releases/download/{tag}/dfns.zip`, extracts it into `cache_path` using `pooch`. Skips if the cache dir already contains files and `force=False`.

**Spec access**: `.spec` calls `sync()` if the cache is empty, then calls `Dfns.load(cache_path)`.

**`load(path)`** classmethod: reads a TOML file with a `releases` list of release ID strings and returns a dict of `RemoteDfnRegistry` objects.

**`load_default()`** classmethod: loads the bundled `dfns.toml` config, then merges any user config overlay (see below). Returns a merged dict, with user config entries taking precedence.

**`from_ids(*ids)`** classmethod: creates registries from ID strings; auto-syncs if `MODFLOW_DEVTOOLS_AUTO_SYNC` is set and the cache is empty.

**`cached_tag()`**: returns the cached tag without network access. For exact tags, checks whether `cache_path` exists and is non-empty. For `@latest`, scans the repo's cache directory and returns the most-recently-modified tag directory's name.

### Bootstrap and user config

The bundled config is at `modflow_devtools/dfns/dfns.toml`:

```toml
releases = [
    "MODFLOW-ORG/modflow6@latest",
    "MODFLOW-ORG/modflow6-nightly-build@latest",
]
```

The user config path (`RemoteDfnRegistry.user_config_path()`) is:
- Linux/macOS: `$XDG_CONFIG_HOME/modflow-devtools/dfns.toml` (default `~/.config/`)
- Windows: `%APPDATA%/modflow-devtools/dfns.toml`

Both files use the same format. `load_default()` merges them with `base | user` (user entries override base entries of the same key).

### Auto-sync

`_auto_sync()` checks whether `MODFLOW_DEVTOOLS_AUTO_SYNC` is set to a truthy value (`"1"`, `"true"`, or `"yes"`). When true, `from_ids()` calls `sync()` for any registry whose cache is empty.

## CLI (`__main__.py`)

Three subcommands:

| Command | Action |
|---|---|
| `sync [--force/-f]` | Call `sync()` on each registry from `load_default()` |
| `info` | Call `cached_tag()` on each registry and print cache status |
| `clean` | Delete the entire base cache directory |

The CLI entry point is `main(argv=None)`.

## Relationship to `modflow_devtools.dfn`

The v1 `modflow_devtools.dfn` module remains the stable baseline. `modflow_devtools.dfns` builds on top of it: `Dfns.load()` imports `modflow_devtools.dfn.schema` to parse `.dfn` files, and `mapper.py` converts the resulting v1 objects to v2 schema. The v1 module's `fetch_dfns()` function is re-exported from `modflow_devtools.dfns.__init__` for convenience.

## Testing

Tests for the dfns module live under `autotest/dfns/`:

- `test_dfns.py` — tests for `Dfns.load()`, `children_of()`, and the CLI
- `test_dfns_registry.py` — tests for `LocalDfnRegistry`, `RemoteDfnRegistry`, and caching behavior
- `test_dfns_schema.py` — tests for schema validation (dims, shapes, fk/pk)
- `test_mapper.py` — unit tests for the v1→v2 mapper

Network-dependent tests (`test_latest_tag_live`, `test_remote_dfn_registry_sync`) are skipped by default with `@pytest.mark.skip`. The registry tests use `unittest.mock.patch` to avoid network calls.
