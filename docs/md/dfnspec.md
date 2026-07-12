# DFN specification

This document describes the MODFLOW 6 component definition (DFN) system. This system is used to specify MODFLOW 6 components, including input fields and (optionally) API-accessible runtime memory variables.

- [Overview](#overview)
- [Components](#components)
  - [Shared attributes](#shared-attributes)
    - [`type`](#type)
    - [`name`](#name)
    - [`blocks`](#blocks)
    - [`parent`](#parent)
    - [`schema_version`](#schema_version)
    - [`dims`](#dims)
    - [`memory`](#memory)
  - [Component types](#component-types)
    - [Simulation](#simulation)
    - [Model](#model)
      - [Type-specific attributes](#type-specific-attributes)
        - [`solution`](#solution)
        - [`dependent_variable`](#dependent_variable)
    - [Package](#package)
      - [Type-specific attributes](#type-specific-attributes-1)
        - [`multi`](#multi)
        - [`subtype`](#subtype)
- [Blocks](#blocks-1)
  - [Attributes](#attributes)
    - [`name`](#name-1)
    - [`fields`](#fields)
    - [`repeats`](#repeats)
  - [Field ordering](#field-ordering)
- [Fields](#fields-1)
  - [Shared attributes](#shared-attributes-1)
    - [`name`](#name-2)
    - [`type`](#type-1)
    - [`longname`](#longname)
    - [`description`](#description)
    - [`optional`](#optional)
    - [`default`](#default)
    - [`developmode`](#developmode)
    - [`netcdf`](#netcdf)
    - [`tagged`](#tagged)
  - [Scalars](#scalars)
    - [Keyword](#keyword)
    - [String](#string)
      - [Type-specific attributes](#type-specific-attributes-2)
        - [`valid`](#valid)
        - [`case_sensitive`](#case_sensitive)
        - [`time_series`](#time_series)
        - [`pk`](#pk)
        - [`fk`](#fk)
        - [`fk_ref`](#fk_ref)
    - [Integer](#integer)
      - [Type-specific attributes](#type-specific-attributes-3)
        - [`valid`](#valid-1)
        - [`time_series`](#time_series-1)
        - [`pk`](#pk-1)
        - [`fk`](#fk-1)
        - [`fk_ref`](#fk_ref-1)
    - [Double](#double)
      - [Type-specific attributes](#type-specific-attributes-4)
        - [`time_series`](#time_series-2)
    - [File](#file)
      - [Type-specific attributes](#type-specific-attributes-5)
        - [`mode`](#mode)
  - [Composites](#composites)
    - [Array](#array)
      - [Type-specific attributes](#type-specific-attributes-6)
        - [`dtype`](#dtype)
        - [`shape`](#shape)
        - [`time_series`](#time_series-3)
        - [`repeat`](#repeat)
    - [Record](#record)
      - [Type-specific attributes](#type-specific-attributes-7)
        - [`fields`](#fields-2)
    - [Union](#union)
      - [Type-specific attributes](#type-specific-attributes-8)
        - [`arms`](#arms)
    - [List](#list)
      - [Type-specific attributes](#type-specific-attributes-9)
        - [`item`](#item)
        - [`shape`](#shape-1)
  - [Dimensions](#dimensions)
    - [Dimension sources](#dimension-sources)
    - [Dimension scope](#dimension-scope)
  - [Primary/foreign keys](#primary-and-foreign-keys)
    - [Examples](#examples)
- [Memory catalog](#memory-catalog)
  - [Attributes](#attributes-1)
    - [`type`](#type-2)
    - [`dtype`](#dtype-1)
    - [`shape`](#shape-2)
    - [`readonly`](#readonly)
    - [`set_in`](#set_in)
    - [`source`](#source)
    - [`description`](#description-1)
    - [`output`](#output)
    - [`budget`](#budget)
    - [`obs_type`](#obs_type)

## Overview

A MODFLOW 6 simulation consists of a hierarchy of modules, each one representing some functional element, such as a grid discretization, a hydrologic process (i.e. model), or a boundary condition.

Modules are specified by **component definitions** (DFNs), each of which describes the module's general properties, its input fields, its relationships to other modules, and (optionally) its internal memory variables. A module be represented by more than one component definition. A definition describes one way of representing a module; it may not be the only way. Any number of representational variants may exist, each of which reflects a certain tradeoff between properties like program runtime, memory or disk usage, and convenience.

This document refers to **components** instead of modules to emphasize this distinction.

## Components

Component definitions consist of a number of attributes:

- `type`: the component type (`"simulation"`, `"model"`, or `"package"`)
- `name`: the component's name
- `blocks`: block definitions
- `parent`: parent component(s)
- `schema_version`: DFN schema version
- `dims`: named dimensions (field-backed or derived) available for use in array shapes
- `memory`: API-accessible runtime variable definitions

Components may refer to, i.e. be constrained by, other components. Cross-component constraints include parent-child relations, model-solution compatibility restrictions, and primary/foreign keys.

### Shared attributes

#### `type`

The component's type. Required. One of:

- `"simulation"`: the root of the runtime hierarchy.
- `"model"`: a hydrologic process model.
- `"package"`: a model input package.

#### `name`

`string`. Required. The component's name. By convention the hyphenated `abc-xyz` stem of the DFN file name.

#### `blocks`

`{string: Block} (default: {})`. The component's input blocks. A component may be empty, i.e. have no blocks. See section below.

#### `parent`

Except for the simulation, which is the root of the runtime hierarchy, all MF6 components have a parent. Parent-child relations may range from fully constrained (e.g., a `gwf-chd` package must be a child of a `gwf-nam` model) to completely unconstrained. Components which may be attached to multiple possible parents are historically called **subpackages**.

Parent relationships are defined bottom-up with attribute `parent`:

- `null` — no parent; only valid for the root, i.e. simulation.
- `"*"` — unconstrained; any parent component type is allowed.
- A string or list of strings — declares the set of valid parent component types. Entries are either:
  - **Component type names:** `"simulation"`, `"model"`, or `"package"`.
  - **Concrete component names:** e.g. ``"gwf-nam"`

**Note:** Type names and concrete component names may be mixed. A type name subsumes any named component of the same type: e.g., `["gwf-sfr", "package"]` reduces to `["package"]` since `gwf-sfr` is a package.

#### `schema_version`

`string | null (default: null)`. The version of the DFN schema. When multiple component definitions are loaded together, all non-null `schema_version` values must agree; mixed versions are a validation error.

#### `dims`

`{string: Dim} (default: {})`. Named dimensions available for use in array and list shape expressions. Each entry has a `value` expression and a `scope` that controls visibility to other components. See [Dimensions](#dimensions).

#### `memory`

`{string: MemoryVariable} (default: {})`. The component's memory catalog. See section below.

If a component does not provide a `memory` catalog, all memory-managed variables in the component's runtime context will be readonly by default. To allow MODFLOW API access to runtime variables, they must be defined in the `memory` catalog.

### Component types

Three component types can be distinguished: simulation, model, and package.

#### Simulation

The simulation is the root of the MODFLOW 6 runtime module hierarchy. A simulation may contain one or more models, organized into one or more solutions. It has no parent (`parent: null`) and no type-specific attributes beyond those shared by all components.

#### Model

A model represents a hydrologic process. Models are managed and solved by the simulation.

##### Type-specific attributes

###### `solution`

`"ims" | "ems" | "sln-ims" | "sln-ems" | null (default: null)`. MF6 supports different solution schemes: implicit solutions (solve systems of coupled equations iteratively) and explicit solutions (used when closed-form solutions are available). A model declares which solution type it requires with the optional `solution` attribute. Solution packages do not redundantly declare which model types they support; compatibility is determined entirely from the model side.

###### `dependent_variable`

`string | null (default: null)`. The dependent variable this model type computes, e.g. `"head"` for GWF. The model's OC package `rtype` string field should also specify this variable's name as a `valid` value.

#### Package

A package is any component that is not a simulation or a model.

##### Type-specific attributes

###### `multi`

`boolean (default: false)`. Indicates that multiple instances of this component may be attached to the same parent component. Components of which multiple instances are allowed are called "multi-packages".

###### `subtype`

Optional discriminator indicating the package's functional role. Several package subtypes may be distinguished: solutions, exchanges, stress packages, advanced packages, and utility packages.

- `"solution"`: provides solving capability for models. Compatibility with a model is determined by the model's `solution` attribute.
- `"exchange"`: connects two models, enabling them to share boundary conditions or state at their interface. Parent is the simulation.
- `"stress"`: imposes boundary conditions on a model. Period data is provided per stress period; each period block replaces the full set of stresses for that period. Stress packages always declare a `maxbound` integer dimension (the maximum number of boundary entries per stress period) and their period block list carries `shape: ["maxbound"]`.
- `"advanced"`: an advanced stress package. Differs from `"stress"` in three key ways:
  1. Solves a continuity equation. Each feature (well, reach, lake cell, UZF cell) internally balances inflows, outflows, and change in storage. Traditional stress packages impose static conditions and do not have an internal water budget. **Note:** advanced packages can act as receivers in the Water Mover (MVR/MVE) package because they have an internal continuity equation to receive diverted water into. Traditional stress packages cannot.
  2. Has dynamic state variables. Advanced packages compute a dependent variable (e.g., lake stage, well head, reach stage) that is part of the solution. Traditional stress packages use fixed/user-specified values.
  3. Stress periods have feature replacement rather than block replacement semantics: when a new period block configuration is provided, traditional stress packages replace the entire previous configuration; advanced packages perform partial updates, modifying only features explicitly appearing in the new period block. **Note:** both simple and advanced packages fill-forward across omitted stress periods; the distinction is only in what happens when a new period block configuration is specified.

  Advanced packages do **not** declare a `maxbound` dimension. Their list lengths (packagedata rows, period entries per feature, etc.) are determined at runtime — typically derived from a linked flow package's budget object or internal state — and are not declared in the DFN. Accordingly, their list fields carry `shape: []`.
- `"utility"`: an auxiliary package that may be attached to models or packages, such as time series, time-array series, or observations. Utility packages (`utl-*`) are distinguished from primary model input packages by providing configurational or cross-cutting concerns rather than representing a first-class hydrologic process. They may support `multi`.

`subtype: null` (the default) covers packages that don't fall into any named category, such as output control packages.

## Blocks

A block is group of related fields, essentially a product type. Record fields are also product types; the distinction is that records occupy a single line in MF6 input files, while blocks are multiline constructs delimited by headers, e.g.

```
begin <block name>
   field1 value
   field2 value
end <block name>
```

Blocks are treated differently depending on the structural composition of their top-level fields. The sample above is typical of a block containing configuration options, which is essentially a dictionary mapping field names to values.

### Attributes

#### `name`

`string`. Required. The identifier used in `begin <name>` / `end <name>` delimiters in MF6 input files.

#### `fields`

`{string: Field} (default: {})`. The block's fields, in definition order.

#### `repeats`

`boolean (default: false)`. Whether the block may appear multiple times in an input file. When true, each occurrence is read independently and associated with a unique label. The canonical repeating block is the period block, whose label is the stress period number.

A block has no explicit `optional` attribute. Its optionality is derived from its fields: a block is optional if and only if all of its fields are optional (vacuously true for an empty block). This combines with `repeats` to give four configurations:

| `repeats` | derived optional | Meaning |
|---|---|---|
| `false` | `false` | must appear exactly once |
| `false` | `true` | may appear at most once |
| `true` | `false` | must appear at least once |
| `true` | `true` | may appear zero or more times |

### Field ordering

Field order within a block can be significant.

Tagged fields must precede untagged fields. Fields whose values are not preceded by their name (i.e., `tagged: false`) must come after all tagged fields. Among tagged fields, relative order is unconstrained. Untagged fields must appear in the same order of appearance as in the definition.

**Note:** the `tagged` attribute does not apply to `list` fields. A list cannot be tagged because lists span multiple rows in the block body with no keyword delimiter; once a parser reaches a list, it must continue to read lines as list items until the block's end tag. Therefore a list must be the last field in its block and a block may have at most one list.

## Fields

A field is conceptually a [union](https://en.wikipedia.org/wiki/Tagged_union) of concrete data types, discriminated by a `type` attribute. A field consists of a set of attributes, some shared, some type-specific.

Field definitions are not entirely self-contained. Some fields may refer to other fields, in the same component or in another. There are two cases of this:

- array dimensions
- primary/foreign keys

These cases are associated with type-specific attributes described below.

### Shared attributes

There is a core set of attributes shared by all field types:

- `name`
- `type`
- `longname`
- `description`
- `optional`
- `default`
- `developmode`
- `netcdf`
- `tagged`

#### `name`

`string`. Required.

#### `type`

Required. One of:

- `keyword`
- `integer`
- `double`
- `array`
- `string`
- `file`
- `record`
- `union`
- `list`

#### `longname`

`string | null (default: null)`. A longer, more descriptive name. From the [NetCDF conventions](https://docs.unidata.ucar.edu/nug/current/attribute_conventions.html#long_name). May contain spaces.

#### `description`

`string | null (default: null)`. A detailed description of the field.

#### `optional`

`boolean (default: false)`. Indicates that the field is not mandatory and may be omitted. May be applied to both composite and scalar fields.

#### `default`

The field's default value. Only relevant for optional fields. TODO: determine whether to keep. MF6 doesn't read DFN defaults, only flopy does. MF6 implements defaults internally, so care must be taken to keep DFNs in sync, or maybe IDM could read the default from the DFNs.

#### `developmode`

`boolean (default: false)`. Feature flag indicating that the field is not released yet, only allowed in develop mode builds.

#### `netcdf`

`boolean (default: false)`. Marks a field that can appear in NetCDF input files.

#### `tagged`

`boolean (default: true)`. Indicates that the field value should be preceded by the field name.

### Scalars

Scalar fields define a single value.

#### Keyword

Type `keyword`. Represents a boolean choice. In input files, the presence of a keyword indicates true, its absence false.

#### String

Type `string`.

##### Type-specific attributes

###### `valid`

`[string] | null`. Permitted values (enumeration constraint). Empty list is treated as absent.

###### `case_sensitive`

`boolean (default: false)`. Indicates that the string's case must be preserved. The MF6 parser uppercases strings by default.

###### `time_series`

`boolean (default: false)`. Marks fields where the parser accepts either a string literal or a time-series name (referencing a `utl-ts` object).

###### `pk`

`boolean (default: false)`. Marks this scalar as the primary key of its containing list's item record. Valid only on integer or string scalars that are columns in a list item record. Exactly one column per list item may be marked pk.

###### `fk`

`string | null (default: null)`. Marks this scalar as a foreign key. Valid only on integer or string scalars that are columns in a list item record. Three forms: (1) hierarchical path `"block.field"` or `"component.block.field"` — fully static, used without `fk_ref`; (2) sentinel `"node"` — grid cell reference, used without `fk_ref`; (3) bare block name (e.g., `"packagedata"`) — used together with `fk_ref` to name the block within the runtime-resolved target component, leaving only the pk field to be discovered. See "Primary/foreign keys".

###### `fk_ref`

`string | null (default: null)`. For FKs whose target component is only known at runtime. Names a sibling string field whose value identifies the target component. May be set alone (block within target also unknown) or together with `fk` as a bare block name (block known, component not). See "Primary/foreign keys".

#### Integer

Type `integer`.

##### Type-specific attributes

###### `valid`

`[integer] | null`. Permitted values (enumeration constraint). Empty list is treated as absent.

###### `time_series`

`boolean (default: false)`. Marks fields where the parser accepts either a numeric literal or a time-series name (referencing a `utl-ts` object). Not inferable from structural type. Also appears on array fields (where it references a `utl-tas` object instead). Note that `utl-tas` currently only works with layered arrays, not full-grid arrays, though generalizing has been considered.

###### `pk`

`boolean (default: false)`. Marks this scalar as the primary key of its containing list's item record. Valid only on integer or string scalars that are columns in a list item record. Exactly one column per list item may be marked pk.

###### `fk`

`string | null (default: null)`. Marks this scalar as a foreign key. Valid only on integer or string scalars that are columns in a list item record. Three forms: (1) hierarchical path `"block.field"` or `"component.block.field"` — fully static, used without `fk_ref`; (2) sentinel `"node"` — grid cell reference, used without `fk_ref`; (3) bare block name (e.g., `"packagedata"`) — used together with `fk_ref` to name the block within the runtime-resolved target component, leaving only the pk field to be discovered. See "Primary/foreign keys".

###### `fk_ref`

`string | null (default: null)`. For FKs whose target component is only known at runtime. Names a sibling string field whose value identifies the target component. May be set alone (block within target also unknown) or together with `fk` as a bare block name (block known, component not). See "Primary/foreign keys".

#### Double

Type `double`.

##### Type-specific attributes

###### `time_series`

`boolean (default: false)`. Marks fields where the parser accepts either a numeric literal or a time-series name (referencing a `utl-ts` object). Not inferable from structural type. Also appears on array fields (where it references a `utl-tas` object instead). Note that `utl-tas` currently only works with layered arrays, not full-grid arrays, though generalizing has been considered.

#### File

Type `file`.

##### Type-specific attributes

###### `mode`

`"filein" | "fileout"`. Whether the path is to an input or output file. Required.

### Composites

Three kinds of composite type are relevant to MF6: [product](https://en.wikipedia.org/wiki/Product_type) (record), [sum](https://en.wikipedia.org/wiki/Tagged_union) (union), and collection (array, list).

Composite fields are explicitly nested so that the composite structure is reflected in the schema. Product and sum types have multiple nested subfields. Lists have a single nested subfield. Arrays have no nested subfields; see below.

#### Array

Type `array`.

Arrays are not proper composites. An array does not have an item subfield as does a list. Instead, it has a `dtype` attribute identifying its scalar element type. An array may not contain composite elements; `dtype` must be a scalar type.

A 1D array may have absent or empty `shape`, indicating no constraint on its size, in which case it is called **self-sizing**. Self-sizing arrays are parsed by MF6 dynamically at runtime. The size of a self-sizing array may serve as a dimension for other arrays (see below).

A 1D array appearing as a subfield of a record is called an **inline array**. Inline arrays with a declared shape are self-explanatory. An inline array may only be self-sizing if it is the right-most subfield of the record; in this case the record is essentially a variadic tuple.

##### Type-specific attributes

###### `dtype`

`string`. The array's data type. Must be one of the scalar types.

###### `shape`

`[string] (default: [])`. The array's shape, as a list of shape expressions, one per dimension. An empty list means the array is 1-dimensional and **self-sizing** (see above).

###### `time_series`

`boolean (default: false)`. Marks fields where the READARRAY invocation may be replaced by a TAS name referencing a `utl-tas` time-array series object. At any model time, the TAS provides an interpolated grid-shaped array. Distinct from the scalar case: references `utl-tas`, not `utl-ts`. Note that `utl-tas` currently only works with layered arrays, not full-grid arrays, though generalizing has been considered.

###### `repeat`

`string | null (default: null)`. Names the field (within the same component) whose runtime length determines how many times this field is read sequentially within an array block, with each reading appended to an accumulated sequence. See `repeat` section below.

#### Record

Type `record`. Product type. In MF6 input files, records appear on a single line. Record subfields may or may not be `tagged`. While blocks can be considered product types also, in the DFN specification only records are considered fields; blocks are considered named collections of related fields.

##### Type-specific attributes

###### `fields`

`{string: Scalar | Array | Record | Union}`. Subfields, required.

**Note:** An array appearing as a subfield of a record is read inline on the same line, not in the READARRAY format. If the array's `shape` uses a row-level column lookup, the record is effectively a variadic tuple: its width varies per row as determined by a column in a FK-linked list. See [Row-level column lookups](#row-level-column-lookups).

**Note:** if a nested record appears inside another record, the inner record's contents should appear inline inside the outer record's contents, on the same line.

#### Union

Type `union`. Sum type.

##### Type-specific attributes

###### `arms`

`{string: Scalar | Array | Record}`. Subfields, required.

#### List

Type `list`. Collection type. Unlimited but for one rule: a list may not contain another list. Lists are distinct from arrays in two ways: a list element may be a composite type and a list admits sparse representations.

##### Type-specific attributes

###### `item`

`record | union`. Item type, required.

###### `shape`

`[string] (default: [])`. The list's shape, as a list of at most one shape expression (lists are necessarily 1-dimensional).

An **empty `shape`** means the list length is unconstrained at schema-definition time. This is the correct representation for any list whose length is determined at runtime rather than from a declared dimension — including all list fields in advanced packages (LAK, SFR, MAW, UZF, and their transport-side counterparts), whose lengths are derived from a linked flow package's budget or internal state and are never declared in the DFN.

A **non-empty `shape`** (exactly one element) names a declared dimension that bounds the list. The canonical case is a stress package's period block list, which carries `shape: ["maxbound"]`. The `maxbound` dimension is explicitly declared in the stress package's `dimensions` block as an integer field the user must supply.

**Note:** Some non-period lists in stress-type packages (e.g. `utl-spc`) also reference `maxbound`; these follow the same rule — `maxbound` must be an explicitly declared dimension for the shape to be meaningful.

### Dimensions

Dimensions may be declared by a component with a `dims` map. Each entry in `dims` has a `value` expression, a `scope`, and an optional `set_in`:

```yaml
dims:
  nlay:
    value: nlay                  # backed by integer field 'nlay'
    scope: model
  nodes:
    value: "nlay * nrow * ncol"  # derived from other dims
    scope: model
  nper:
    value: nper
    scope: simulation
  auxiliary:
    value: "len(auxiliary)"      # backed by self-sizing array field 'auxiliary'
    scope: component
  nbound:
    set_in: rp                    # runtime-only: set each stress period
  njas:
    set_in: ar                    # runtime-only: set once at grid allocation
```

Dimensions may be used in the `shape` expression of `list` and `array` fields.

#### Dimension sources

The `value` attribute defines the dimension source as a Python expression. Three forms are distinguished:

- **Bare identifier** `nlay` — backed by an integer field of that name in this component. The dimension takes the runtime value of that field.
- **`len(name)`** — backed by a self-sizing array field of that name. The dimension equals the runtime length of the array.
- **Arithmetic expression** `nlay * nrow * ncol` — derived from other dims. May not use bare field names; all operands must be declared dimensions.

If `value` is absent, the dimension is **runtime-only**: its value cannot be derived from DFN input fields. The optional `set_in` attribute then indicates when MODFLOW first establishes the value:

- **`"ar"`** — set once during Allocate and Read (grid allocation). The value is constant for the lifetime of the simulation. Examples: `njas` (number of cell-to-cell connections, computed from grid topology), `nodes` (total active cells, when inherited from a discretization package), `ncolbnd` (number of bound columns, fixed by package structure).
- **`"rp"`** — reset at the start of each stress period from user input. Examples: `nbound` (number of active boundary entries in the current period).

Runtime dims are valid in memory variable shapes but not in input field shapes.

Canonical examples of dimensions:

```yaml
dims:
  # sim-tdis
  nper: {value: nper, scope: simulation}

  # gwf-dis
  nlay: {value: nlay, scope: model}
  nrow: {value: nrow, scope: model}
  ncol: {value: ncol, scope: model}
  ncpl: {value: "nrow * ncol", scope: model}
  nodes: {value: "nlay * nrow * ncol", scope: model}
  ncelldim: {value: "3", scope: model}

  # gwf-disv
  ncpl: {value: ncpl, scope: model}
  nodes: {value: "nlay * ncpl", scope: model}
  ncelldim: {value: "2", scope: model}

  # gwf-disu: njas is expressible because nja is a user-supplied DFN field
  njas: {value: "(nja - nodes) / 2"}

  # any package with an auxiliary array
  auxiliary: {value: "len(auxiliary)"}

  # stress package runtime dims
  nbound: {set_in: rp}   # active BCs this period, not derivable from input
  njas: {set_in: ar}     # cell connections, set at grid allocation (DIS/DISV)
```

An inline array may have its size determined by an integer subfield in the same record, or if the record it is within is the item type of a list, by a column in another list.

If a record contains an `integer` field followed by an `array` whose shape expression names that field, the record is self-describing: it carries its own sizing information. Inline array dimensions of this kind need not be declared at the component level. For instance:

```yaml
connectiondata:
  type: list
  item:
    type: record
    fields:
      icno:
        type: integer
        fk: "packagedata.icno"
      ncvert:
        type: integer
      icvert:
        type: array
        dtype: integer
        shape: ["ncvert"]
```

If an inline array appears in a record which is the item type of a list, the array's size may be specified by a column in another regular list. This is a form of primary-/foreign-key relation; see [Primary/foreign keys](#primaryforeign-keys). The syntax for this form is `[component.]block.column(fk_field)`. If the list is in the same component, the dimension need not be declared in `dims`.

- `component`: the component name. Only required if in a different component.
- `block`: the name of the block containing the list. In all current cases the list field has the same name as its containing block, so this also serves as the list name.
- `column`: an integer subfield in the list's record item type.
- `fk_field`: an integer subfield in the referring array's record whose `fk` attribute resolves to a `pk` subfield in the dimension-providing record.

The parenthetical `(fk_field)` serves as the row selector, distinguishing this form from a derived dimension expression over the same path, e.g. `[component.]block.column`

The canonical example of this is `gwf-sfr.connectiondata.ic`, an array field whose length varies per reach according to the `ncon` column in `packagedata`:

```yaml
packagedata:
  type: list
  item:
    type: record
    fields:
      ifno:
        type: integer
        pk: true
      ncon:
        type: integer
      # ...

connectiondata:
  type: list
  item:
    type: record
    fields:
      ifno:
        type: integer
        fk: "packagedata.ifno"
      ic:
        type: array
        dtype: integer
        shape: ["packagedata.ncon(ifno)"]
```

`packagedata.ncon(ifno)` means: follow `ifno`'s FK to identify the `packagedata` row, then read `ncon` from it. Each `connectiondata` row has a different number of `ic` values; each record is a variadic tuple, making the list jagged.

#### Dimension scope

Dimensions may specify a `scope` attribute controlling which other components can inherit the dimension:

- **`"component"`**: only visible within this component (or to subpackages that list this component as their explicit parent). The default scope.
- **`"model"`**: visible to any component that can share the same model instance, as determined by component `parent` attributes. A dimension defined in component A with `scope: "model"` is visible to component B if:
  - A's `parent` contains a concrete model-name entry (e.g. `"gwf-nam"`, `"chf-nam"`), and
  - B's `parent` contains either that same model-name entry (meaning B can belong to the same model type), a generic type (`"model"` or `"package"`, meaning B can be attached to any such type), or a wildcard pattern (`"*"`, meaning B can be attached to any component).
- **`"simulation"`**: always visible to all components.

Examples:
- `gwf-dis.dims.nrow`, `ncol`, `nlay` have `scope: "model"`: accessible to `gwf-chd`, `gwf-wel`, and any other component whose parent is `gwf-nam`, but also to e.g. `utl-spca` (which has `parent: "package"`).
- `sim-tdis.dims.nper` has `scope: "simulation"`: accessible from all components.

### Primary and foreign keys

Sometimes a column in one list identifies a row in another list, or a grid cell. This can be conceptualized as a primary key (PK) / foreign key (FK) relation. Integers and strings may encode PK/FK semantics with attributes `pk`, `fk`, and `fk_ref`.

**Note**: PK/FK attributes are only valid on integer and string fields appearing as columns in a tabular (i.e. regular) list's record item type.

The `fk` attribute can take one of three forms:

- **Hierarchical path**: A path of the form `"[component.]block.field"`, for use when the primary key field is statically known. The `component` segment is necessary for cross-component references; it may be omitted for within-component references. The hierarchical path form may not be used with `fk_ref`.
- **Grid cell sentinel**: A value `"node"` indicates a grid cell reference, resolve from the parent model's grid at runtime. This form may not be used with `fk_ref`.
- **Bare block name**: The name of a block in which there is exactly one `pk` field. In this case, `fk_ref` is required to resolve the target component at runtime. Note that blocks must not be named "node" to avoid interference with the grid cell sentinel.

The `fk_ref` attribute names a string field whose runtime value identifies the component containing the `pk` field. Two sub-cases exist:

- **With `fk`**: The `fk` must be a bare block name. The component containing the block is resolved with `fk_ref`, then the block (identified by `fk`) is searched for a unique `pk` field. For all current corpus cases where `fk_ref` identifies an integer "feature number" PK (e.g. SFR, MAW, UZF, LAK via `gwf-mvr`), the block is `packagedata`; `fk: "packagedata"` should therefore always be set alongside `fk_ref` for these cases.
- **Without `fk`**: the target block varies by component (e.g. `utl-obs.continuous.id`, where the target is a boundary name whose block varies by package type).

#### Examples

| Field | `pk` | `fk` | `fk_ref` | Notes |
|---|---|---|---|---|
| `gwf-sfr.packagedata.rno` | `true` | — | — | PK of the reach list |
| `gwf-sfr.connectiondata.rno` | — | `"packagedata.rno"` | — | FK; also row selector for ic's shape lookup |
| `gwf-sfr.connectiondata.ic` | — | — | — | inline array; `shape: ["packagedata.ncon(rno)"]`; elements are signed reach refs (sign encodes upstream/downstream direction) |
| `gwf-sfr.period.rno` | — | `"packagedata.rno"` | — | within-component |
| `gwf-mvr.packages.pname` | `true` | — | — | string PK of the package list |
| `gwf-mvr.period.pname1` | — | `"packages.pname"` | — | string FK, within-component |
| `gwf-mvr.period.id1` | — | `"packagedata"` | `"pname1"` | component resolved from pname1; codec finds unique pk in packagedata |
| `utl-obs.continuous.id` (string arm) | — | — | `"obstype"` | **Open:** target block varies by package type; codec must handle case-by-case |
| `utl-obs.continuous.id` (integer arm) | — | `"node"` | — | grid cell reference |
| `gwf-wel.period.cellid` | — | `"node"` | — | grid cell reference |

## Memory catalog

Each component may declare a `memory` catalog describing runtime variables accessible via the MODFLOW API. Memory variables correspond to values in the MODFLOW 6 memory manager that can be read or written at runtime using hierarchical `/`-delimited memory addresses.

The `memory` section complements the `blocks` section: `blocks` specifies user-facing input, while `memory` specifies the runtime representation. The two sections may overlap when a memory variable is loaded directly from an input field, and may diverge when a variable is derived or computed internally.

The `memory` section documents:

- What API-accessible variables exists for each component
- If a variable may be written with the API, or only read
- When each variable is (re)computed or overwritten by MF6
- How a derived variable relates to contributing variables
- If a variable is an output, budget term, or observation

The `memory` section is optional, but highly recommended. If a component definition lacks a `memory` section, all memory-managed variables are readonly by default.

### Attributes

#### `type`

`"integer" | "double" | "string" | "logical" | "array"`. Required. The memory variable's data type.

#### `dtype`

`string`. An array's data type. Must be one of the scalar types: `"integer" | "double" | "string" | "logical"`. Only meaningful/required for array variables.

#### `shape`

`[string] (default: [])`. The variable's shape, as a list of dimension names. An empty list means the shape is determined at runtime and is not specified in the DFN. Shape expressions follow the same syntax as array and list `shape` attributes in `blocks`, but may only reference named dimensions; expressions are not permitted.

#### `readonly`

`boolean (default: false)`. Indicates that this variable may only be read by API consumers, not written. When `false`, the variable may be both read and written. Structural variables, such as grid geometry, are typically `readonly = true`. Variables that influence the solution, e.g. initial or boundary conditions, are typically writable.

#### `set_in`

`string | [string] | null (default: null)`. Identifies the simulation framework hook(s) in which MODFLOW overwrites the variable. Answers the questions: *When I set a value with the API, will it have an effect on the simulation? If so, for how long?* While this information is not programmatically verifiable/actionable, it is critical for the user to understand how to interact with the simulation.

A single string names the routine. A list indicates the variable may be written at more than one hook, as can occur if modification is conditional on input configuration (i.e., a variable is recomputed only when some input option is enabled).

Allowed values:

- `"ar"`: Allocate and Read. The variable is set once during initialisation. A value written via the API persists for the remainder of the simulation.
- `"mc"`: Map Connections. Called once during solution initialisation to map local matrix positions to the global sparse system matrix. Variables set here are structural integer arrays (e.g. `idxglo`) that are constant for the lifetime of the simulation.
- `"rp"`: Read and Prepare. The variable is overwritten at the start of each stress period. A value written via the API persists for one stress period.
- `"ad"`: Advance. The variable is overwritten at the start of each time step. A value written via the API persists for one time step.
- `"fc"`: Formulate. The variable is assembled from scratch each solver iteration (e.g. `hcof`, `rhs`). Any API write is overwritten before it can affect the solution. **Note:** a variable with `set_in = "fc"` must have `readonly = true`.
- `"ca"`: Calculate. The variable (e.g. head, `x`) is updated by the solver in each solver iteration. Writing a value between time steps provides an initial guess for the next solve; any write within the solve loop is overwritten by the next linear solve and has no effect.
- `"cq"`: Calculate Flows. The variable is computed after solution convergence. Writing to it has no effect on the solution. **Note:** a variable with `set_in = "cq"` must have `readonly = true`.

The order of presentation above is the same as that in which the framework hooks are invoked at runtime: `"ar"` → `"mc"` → `"rp"` → `"ad"` → `"fc"` → `"ca"` → `"cq"`.

#### `source`

`string | [string] | null (default: null)`. Identifies the source(s) of a derived variable's.

Allowed values:

- A single string names an input field from which the variable is loaded directly.
- A list of strings names multiple contributing memory variables from which this variable is derived.
- Absent means the variable has no direct input or memory-variable counterpart; it is computed internally.

#### `description`

`string | null (default: null)`. A detailed description of the variable, including relevant usage notes for API consumers.

#### `output`

`boolean | null (default: null)`. Indicates that this is a model output variable. Registers the variable as an output to be returned by [BMI's `get_output_var_names()`](https://bmi.csdms.io/en/stable/bmi.info_funcs.html#get-output-var-names).

#### `budget`

`string | null (default: null)`. The budget file term name for variables that contribute to budget (e.g., `"WEL"` for `simvals` in a WEL package, `"FLOW-JA-FACE"` for `flowja`). Absent means the variable is not a budget term. Registers the variable as an output to be returned by [BMI's `get_output_var_names()`](https://bmi.csdms.io/en/stable/bmi.info_funcs.html#get-output-var-names).

#### `obs_type`

`string | null (default: null)`. The OBS package observation type name for variables observable through the `utl-obs` utility package (e.g., `"HEAD"` on `x`, `"WEL"` on `simvals` in the WEL package). Absent means the variable is not directly observable via OBS. Registers the variable as an output to be returned by [BMI's `get_output_var_names()`](https://bmi.csdms.io/en/stable/bmi.info_funcs.html#get-output-var-names).
