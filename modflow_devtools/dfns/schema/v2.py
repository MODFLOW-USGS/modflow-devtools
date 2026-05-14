import ast
import re
from collections.abc import Mapping
from os import PathLike
from typing import Annotated, Any, Literal

from packaging.version import Version
from pydantic import (
    BaseModel,
    ConfigDict,
    GetCoreSchemaHandler,
    field_validator,
    model_validator,
)
from pydantic import (
    Field as PydanticField,
)
from pydantic_core import core_schema


class FieldBase(BaseModel):
    model_config = ConfigDict(frozen=True)

    @classmethod
    def from_dict(cls, d: dict, strict: bool = False) -> "FieldBase":
        type_ = d.get("type")
        type_map: dict[str | None, type[FieldBase]] = {
            "keyword": Keyword,
            "string": String,
            "integer": Integer,
            "double": Double,
            "path": Path,
            "array": Array,
            "record": Record,
            "union": Union,
            "list": List,
        }
        target = type_map.get(type_)
        if target is None:
            raise ValueError(f"Unknown or missing field type: {type_!r}")
        if strict:
            extra = set(d.keys()) - set(target.model_fields.keys())
            if extra:
                raise ValueError(f"Unrecognized keys in field data: {extra}")
        return target.model_validate(d)


class Keyword(FieldBase):
    type: Literal["keyword"] = "keyword"
    name: str
    longname: str | None = None
    description: str | None = None
    optional: bool = False
    default: Any | None = None
    developmode: bool = False
    netcdf: bool = False


class String(FieldBase):
    type: Literal["string"] = "string"
    name: str
    longname: str | None = None
    description: str | None = None
    optional: bool = False
    default: Any | None = None
    developmode: bool = False
    netcdf: bool = False
    tagged: bool = True
    valid: list[str] | None = None
    case_sensitive: bool = False
    time_series: bool = False
    pk: bool = False
    fk: str | None = None
    fk_ref: str | None = None


class Integer(FieldBase):
    type: Literal["integer"] = "integer"
    name: str
    longname: str | None = None
    description: str | None = None
    optional: bool = False
    default: Any | None = None
    developmode: bool = False
    netcdf: bool = False
    tagged: bool = True
    valid: list[int] | None = None
    dimension: Literal["record", "component", "model", "simulation"] | None = None
    time_series: bool = False
    pk: bool = False
    fk: str | None = None
    fk_ref: str | None = None

    @field_validator("dimension", mode="before")
    @classmethod
    def _coerce_dimension(cls, v: Any) -> Any:
        if v is True:
            return "component"
        if v is False:
            return None
        return v


class Double(FieldBase):
    type: Literal["double"] = "double"
    name: str
    longname: str | None = None
    description: str | None = None
    optional: bool = False
    default: Any | None = None
    developmode: bool = False
    netcdf: bool = False
    tagged: bool = True
    time_series: bool = False


class Path(FieldBase):
    type: Literal["path"] = "path"
    name: str
    longname: str | None = None
    description: str | None = None
    optional: bool = False
    default: Any | None = None
    developmode: bool = False
    mode: Literal["filein", "fileout"]


Scalar = Annotated[
    Keyword | String | Integer | Double | Path,
    PydanticField(discriminator="type"),
]


class Array(FieldBase):
    type: Literal["array"] = "array"
    name: str
    longname: str | None = None
    description: str | None = None
    optional: bool = False
    default: Any | None = None
    developmode: bool = False
    netcdf: bool = False
    dtype: Literal["keyword", "integer", "double", "string"]
    shape: list[str] = []
    time_series: bool = False
    repeat: str | None = None
    dimension: Literal["record", "component", "model", "simulation"] | None = None

    @field_validator("dimension", mode="before")
    @classmethod
    def _coerce_dimension(cls, v: Any) -> Any:
        if v is True:
            return "component"
        if v is False:
            return None
        return v

    @model_validator(mode="after")
    def _validate_dimension(self) -> "Array":
        if self.dimension is not None and self.dtype != "string":
            raise ValueError(f"Array {self.name!r}: dimension may only be set when dtype='string'")
        return self


class Record(FieldBase):
    type: Literal["record"] = "record"
    name: str
    longname: str | None = None
    description: str | None = None
    optional: bool = False
    default: Any | None = None
    developmode: bool = False
    fields: "dict[str, Scalar | Array | Record | Union]" = PydanticField(default_factory=dict)

    @property
    def children(self) -> "dict[str, Field]":
        return self.fields  # type: ignore[return-value]


class Union(FieldBase):
    type: Literal["union"] = "union"
    name: str
    longname: str | None = None
    description: str | None = None
    optional: bool = False
    default: Any | None = None
    developmode: bool = False
    arms: "dict[str, Scalar | Array | Record]" = PydanticField(default_factory=dict)

    @property
    def children(self) -> "dict[str, Field]":
        return self.arms  # type: ignore[return-value]


class List(FieldBase):
    type: Literal["list"] = "list"
    name: str
    longname: str | None = None
    description: str | None = None
    optional: bool = False
    default: Any | None = None
    developmode: bool = False
    netcdf: bool = False
    item: "Record | Union"

    @property
    def children(self) -> "dict[str, Field]":
        return {"item": self.item}  # type: ignore[return-value]


Field = Annotated[
    Keyword | String | Integer | Double | Path | Array | Record | Union | List,
    PydanticField(discriminator="type"),
]

# Backward-compat alias: all concrete v2 field types are FieldBase subclasses,
# so isinstance(field, FieldV2) remains True for any v2 field instance.
FieldV2 = FieldBase

Record.model_rebuild()
Union.model_rebuild()
List.model_rebuild()


# Fallback set of well-known grid dim names used by grid_dims_for and the v1
# mapper (map_period_block).  Once all dims in the v1 corpus carry explicit
# "model" scope, this constant becomes unnecessary and will be removed.
GRID_DIM_NAMESPACE: frozenset[str] = frozenset(
    {"nodes", "nlay", "nrow", "ncol", "ncpl", "nja", "ncelldim", "nvert"}
)


def _collect_explicit_dims(component: "ComponentBase") -> set[str]:
    """
    Gather all explicitly declared dimension names from a component.

    Collects Integer fields with ``dimension=True`` and string Array fields
    with ``dimension=True``, recursing into Records, Union arms, and List
    item records at any nesting depth.
    """
    dims: set[str] = set()

    _GLOBAL_SCOPES = ("component", "model", "simulation")

    def _scan(fields: "dict[str, Any]") -> None:
        for f in fields.values():
            if isinstance(f, Integer) and f.dimension in _GLOBAL_SCOPES:
                dims.add(f.name)
            elif isinstance(f, Array) and f.dtype == "string" and f.dimension in _GLOBAL_SCOPES:
                dims.add(f.name)
            elif isinstance(f, Record):
                _scan(f.fields)
            elif isinstance(f, Union):
                _scan(f.arms)
            elif isinstance(f, List):
                item = f.item
                _scan(item.fields if isinstance(item, Record) else item.arms)

    for block in (component.blocks or {}).values():
        _scan(block.fields)
    return dims


def _names_in_expr(expr: str) -> set[str]:
    """Return Name identifiers from expr, excluding those inside sum() calls."""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"Invalid expression {expr!r}: {e}") from e

    sum_interior_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "sum":
            for child in ast.walk(node):
                if child is not node:
                    sum_interior_ids.add(id(child))

    return {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and id(node) not in sum_interior_ids
    }


def _validate_sum_call(call: ast.Call, component: "ComponentBase", expr: str) -> None:
    """Validate a sum(list.col) or sum(block.list.col) call in a derived_dims expression."""
    if len(call.args) != 1:
        raise ValueError(f"sum() in derived_dims must have exactly one argument in {expr!r}")
    arg = call.args[0]
    if not isinstance(arg, ast.Attribute):
        raise ValueError(f"sum() argument must be an attribute expression in {expr!r}")

    col_name = arg.attr
    if isinstance(arg.value, ast.Name):
        list_name = arg.value.id
        block_qualifier: str | None = None
    elif isinstance(arg.value, ast.Attribute) and isinstance(arg.value.value, ast.Name):
        block_qualifier = arg.value.value.id
        list_name = arg.value.attr
    else:
        raise ValueError(f"Unrecognised sum() form in {expr!r}")

    found_block: str | None = None
    found_list: List | None = None
    for block_name, block in (component.blocks or {}).items():
        f = block.fields.get(list_name)
        if isinstance(f, List):
            found_block = block_name
            found_list = f
            break

    if found_list is None:
        raise ValueError(f"sum() references unknown list field {list_name!r} in {expr!r}")
    if block_qualifier is not None and block_qualifier != found_block:
        raise ValueError(
            f"sum() block qualifier {block_qualifier!r} does not match "
            f"actual block {found_block!r} in {expr!r}"
        )

    item = found_list.item
    item_fields: dict = item.fields if isinstance(item, Record) else item.arms
    col_field = item_fields.get(col_name)
    if col_field is None:
        raise ValueError(
            f"sum() column {col_name!r} not found in {list_name!r} item fields in {expr!r}"
        )
    if not isinstance(col_field, Integer):
        raise ValueError(
            f"sum() column {col_name!r} is {type(col_field).__name__}, must be Integer in {expr!r}"
        )


def _resolve_derived_dims(component: "ComponentBase", known_dims: set[str]) -> list[str]:
    """
    Validate derived_dims expressions and return their names in topological order.
    Raises ValueError on cycles or unresolvable operands.

    ``known_dims`` is the full set of dim names visible to this component
    (explicit + derived + inherited); pass ``_known_dims_for(spec, name)`` from
    ``DfnSpec._validate_dims_and_shapes``, or an explicit set in tests.
    """
    derived = component.derived_dims or {}
    if not derived:
        return []

    derived_names = set(derived.keys())
    deps: dict[str, set[str]] = {}

    for name, expr in derived.items():
        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError as e:
            raise ValueError(f"Invalid derived_dims {name!r}: {expr!r}: {e}") from e

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "sum"
            ):
                _validate_sum_call(node, component, expr)

        operands = _names_in_expr(expr)
        for op in operands:
            if op not in known_dims and op not in derived_names:
                raise ValueError(f"derived_dims {name!r} operand {op!r} is not a known dimension")
        deps[name] = operands & derived_names

    in_degree = dict.fromkeys(derived_names, 0)
    dependents: dict[str, set[str]] = {n: set() for n in derived_names}
    for name, dep_set in deps.items():
        for dep in dep_set:
            in_degree[name] += 1
            dependents[dep].add(name)

    queue = [n for n, d in in_degree.items() if d == 0]
    order: list[str] = []
    while queue:
        n = queue.pop(0)
        order.append(n)
        for dependent in dependents[n]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(order) != len(derived_names):
        cyclic = {n for n, d in in_degree.items() if d > 0}
        raise ValueError(f"Cycle in derived_dims: {cyclic}")

    return order


class Block(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    fields: dict[str, Field]
    repeats: bool = False
    optional: bool = False

    @field_validator("fields", mode="before")
    @classmethod
    def _coerce_field_instances(cls, v: Any) -> Any:
        if isinstance(v, dict):
            return {
                k: (val.model_dump() if isinstance(val, FieldBase) else val) for k, val in v.items()
            }
        return v


Blocks = Mapping[str, Block]


class _VersionPydanticAnnotation:
    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler: GetCoreSchemaHandler):
        return core_schema.no_info_plain_validator_function(
            lambda v: Version(str(v)) if not isinstance(v, Version) else v,
            serialization=core_schema.to_string_ser_schema(),
        )


VersionField = Annotated[Version, _VersionPydanticAnnotation]


class ComponentBase(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    blocks: dict[str, Block] | None = None
    parent: str | list[str] | None = None
    schema_version: VersionField | None = None
    derived_dims: dict[str, str] | None = None


class Simulation(ComponentBase):
    type: Literal["simulation"] = "simulation"


class Model(ComponentBase):
    type: Literal["model"] = "model"
    solution: str | list[str] | None = None  # compatible solution type(s)


class Package(ComponentBase):
    type: Literal["package"] = "package"
    multi: bool = False
    subtype: Literal["solution", "exchange", "stress", "advanced", "utility"] | None = None
    variant_of: str | None = None


Component = Annotated[
    Simulation | Model | Package,
    PydanticField(discriminator="type"),
]

# Shape element patterns
_DIM_RE = re.compile(r"^[A-Za-z_]\w*$")
_LOOKUP_RE = re.compile(r"^(\w+)\.(\w+)\((\w+)\)$")


def _known_dims_for(spec: "DfnSpec", component_name: str) -> set[str]:
    """
    Return the full set of dim names valid for shape references in a component.
    Scope chain (levels 1-3; level 4 is intra-record sibling, checked per-field):
      1. local explicit dims: Integer(dimension=True) and Array(dtype="string", dimension=True)
      2. local derived dims (keys of component.derived_dims)
      3. inherited grid dims (from all other components in the spec)
    """
    component = spec.components[component_name]
    return (
        _collect_explicit_dims(component)
        | set((component.derived_dims or {}).keys())
        | spec.grid_dims_for(component_name)
    )


def _find_list_in_block(component: "ComponentBase", block_name: str) -> "List | None":
    """Return the first List field in the named block, or None."""
    block = (component.blocks or {}).get(block_name)
    if block is None:
        return None
    for f in block.fields.values():
        if isinstance(f, List):
            return f
    return None


def _validate_shape_element(
    element: str,
    array_field: "Array",
    component: "ComponentBase",
    enclosing_record: "Record | None",
    known_dims: set[str],
) -> None:
    """
    Validate one element of an Array.shape list.

    Valid forms:
      - Dim reference  ``^[A-Za-z_]\\w*$``
        Must resolve in the 3-level scope: explicit → derived → grid dims.
      - Row-level column lookup  ``^(\\w+)\\.(\\w+)\\((\\w+)\\)$``
        Structural checks (see plan §Shape element parsing).

    Raises ValueError on any violation.
    """
    if _DIM_RE.fullmatch(element):
        if element in known_dims:
            return
        # Per-row varying shape: a sibling field in the same enclosing record
        # supplies the inline count for this row. Valid when the sibling has
        # dimension="record" (or, for string Arrays, is a record-scoped dim).
        if enclosing_record is not None:
            sibling = enclosing_record.fields.get(element)
            if isinstance(sibling, (Integer, Array)) and sibling.dimension == "record":
                return
        raise ValueError(
            f"Array {array_field.name!r} shape element {element!r} "
            f"does not resolve to a known dim "
            f"(explicit, derived, or grid)"
        )

    if m := _LOOKUP_RE.fullmatch(element):
        block_name, col_name, fk_field_name = m.groups()

        # Check 5: array must be a subfield of a record, not a top-level block field
        if enclosing_record is None:
            raise ValueError(
                f"Array {array_field.name!r} shape element {element!r} is a "
                f"row-level lookup but the array is not inside a record"
            )

        # Check 1: block_name must identify a list block in this component
        list_field = _find_list_in_block(component, block_name)
        if list_field is None:
            raise ValueError(
                f"Array {array_field.name!r} shape element {element!r}: "
                f"{block_name!r} is not a list block in this component"
            )

        # Check 2: col_name must be an Integer field in the list's item record
        item = list_field.item
        item_fields: dict = item.fields if isinstance(item, Record) else item.arms
        col_field = item_fields.get(col_name)
        if col_field is None:
            raise ValueError(
                f"Array {array_field.name!r} shape element {element!r}: "
                f"{col_name!r} is not a field in {list_field.name!r} item"
            )
        if not isinstance(col_field, Integer):
            raise ValueError(
                f"Array {array_field.name!r} shape element {element!r}: "
                f"{col_name!r} is {type(col_field).__name__}, must be Integer"
            )

        # Check 3: fk_field_name must be a sibling field in the enclosing record
        fk_field = enclosing_record.fields.get(fk_field_name)
        if fk_field is None:
            raise ValueError(
                f"Array {array_field.name!r} shape element {element!r}: "
                f"{fk_field_name!r} is not a sibling field in the enclosing record"
            )

        # Check 4: fk_field.fk must be set and its block portion must match block_name
        fk = getattr(fk_field, "fk", None)
        if fk is None:
            raise ValueError(
                f"Array {array_field.name!r} shape element {element!r}: "
                f"{fk_field_name!r}.fk is not set"
            )
        fk_block = fk.split(".")[0] if "." in fk else fk
        if fk_block != block_name:
            raise ValueError(
                f"Array {array_field.name!r} shape element {element!r}: "
                f"{fk_field_name!r}.fk = {fk!r} does not reference block {block_name!r}"
            )
        return

    raise ValueError(
        f"Array {array_field.name!r} has invalid shape element {element!r}: "
        f"must be a dim reference (^[A-Za-z_]\\w*$) or a row-level "
        f"lookup (block.column(fk_field))"
    )


def _validate_fk_fields(component: "ComponentBase", spec: "DfnSpec") -> None:
    """
    For every Integer/String field with fk or fk_ref set, validate structural
    consistency:
      - fk must reference a list block in this component, and that list's item
        must have at least one pk=True field.
      - fk_ref must name a component that exists in the spec.
    """
    if not component.blocks:
        return

    def _check_fields(fields: dict) -> None:
        for field in fields.values():
            fk: str | None = getattr(field, "fk", None)
            fk_ref: str | None = getattr(field, "fk_ref", None)

            if fk is not None:
                block_name = fk.split(".")[0] if "." in fk else fk
                list_field = _find_list_in_block(component, block_name)
                if list_field is None:
                    raise ValueError(
                        f"Field {field.name!r} fk={fk!r}: "
                        f"{block_name!r} is not a list block in this component"
                    )
                item = list_field.item
                item_fields: dict = item.fields if isinstance(item, Record) else item.arms
                has_pk = any(getattr(f, "pk", False) for f in item_fields.values())
                if not has_pk:
                    raise ValueError(
                        f"Field {field.name!r} fk={fk!r}: "
                        f"list {list_field.name!r} item has no pk=True field"
                    )

            if fk_ref is not None and fk_ref not in spec.components:
                raise ValueError(
                    f"Field {field.name!r} fk_ref={fk_ref!r}: "
                    f"component {fk_ref!r} not found in spec"
                )

            if isinstance(field, Record):
                _check_fields(field.fields)
            elif isinstance(field, Union):
                _check_fields(field.arms)
            elif isinstance(field, List):
                item = field.item
                if isinstance(item, Record):
                    _check_fields(item.fields)

    for block in component.blocks.values():
        _check_fields(block.fields)


def _validate_array_shapes(
    component: "ComponentBase",
    component_name: str,
    spec: "DfnSpec",
) -> None:
    """
    Validate all Array.shape elements in a component.

    Arrays are found at three nesting levels:
      - Top-level block fields (no enclosing record)
      - Fields within a top-level Record (enclosing_record = the Record)
      - Fields within a List item Record (enclosing_record = the item Record)
    """
    if not component.blocks:
        return

    known_dims = _known_dims_for(spec, component_name)

    def _check_array(arr: "Array", enclosing: "Record | None") -> None:
        if arr.dtype == "string":
            return  # inline string arrays are self-sizing; no declared dim needed
        for elem in arr.shape:
            _validate_shape_element(elem, arr, component, enclosing, known_dims)

    for block in component.blocks.values():
        for field in block.fields.values():
            if isinstance(field, Array):
                _check_array(field, None)

            elif isinstance(field, Record):
                for subfield in field.fields.values():
                    if isinstance(subfield, Array):
                        _check_array(subfield, field)

            elif isinstance(field, List):
                item = field.item
                if isinstance(item, Record):
                    for subfield in item.fields.values():
                        if isinstance(subfield, Array):
                            _check_array(subfield, item)


class DfnSpec(BaseModel):
    model_config = ConfigDict(frozen=True)
    components: dict[str, Component]

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def schema_version(self) -> Version:
        for c in self.components.values():
            if c.schema_version is not None:
                return c.schema_version
        return Version("2")

    @property
    def root(self) -> "Simulation | None":
        """Return the single Simulation component, or None if not present."""
        for c in self.components.values():
            if isinstance(c, Simulation):
                return c
        return None

    # ── Query helpers ─────────────────────────────────────────────────────────

    def children_of(self, name: str) -> "dict[str, Component]":
        """Return all components whose parent matches `name`."""
        return {n: c for n, c in self.components.items() if c.parent == name}

    def explicit_dims_for(self, component_name: str) -> set[str]:
        """Return the set of explicit dim names for a component."""
        return _collect_explicit_dims(self.components[component_name])

    def grid_dims_for(self, component_name: str) -> set[str]:
        """
        Return dim names inherited by ``component_name`` from the rest of the spec.

        For v1-mapped specs (no explicit parent chain), this is a permissive
        superset: it scans every other component for explicit dims (any scope
        except "record") and derived dim names, then unions in
        ``GRID_DIM_NAMESPACE`` as a fallback for dims not yet explicitly scoped
        in the corpus.  Native v2 specs with ``parent`` populated will
        eventually use exact parent-chain resolution instead.
        """
        dims: set[str] = set(GRID_DIM_NAMESPACE)
        for name, c in self.components.items():
            if name != component_name:
                dims |= _collect_explicit_dims(c)
                dims |= set((c.derived_dims or {}).keys())
        return dims

    # ── Validation ────────────────────────────────────────────────────────────

    @model_validator(mode="after")
    def _validate_dims_and_shapes(self) -> "DfnSpec":
        """
        At construction time, for every component:
          1. Validate derived_dims expressions (topological sort, operand scope).
          2. Validate every Array.shape element (dim reference or row-level lookup).
        Shape validation runs after dims so the derived dim names are available
        as part of the known scope when checking dim references.
        """
        for name, component in self.components.items():
            if component.derived_dims:
                _resolve_derived_dims(component, _known_dims_for(self, name))
        for name, component in self.components.items():
            _validate_fk_fields(component, self)
        for name, component in self.components.items():
            _validate_array_shapes(component, name, self)
        return self

    # ── Loading ───────────────────────────────────────────────────────────────

    @classmethod
    def load(
        cls,
        path: "str | PathLike",
        schema_version: "str | Version | None" = None,
    ) -> "DfnSpec":
        """Load a DfnSpec from a directory of DFN or TOML files."""
        from pathlib import Path as _Path

        from modflow_devtools.dfn.mapper import _apply_parent_inference, load_flat
        from modflow_devtools.dfns.mapper import map as map_dfn

        _path = _Path(path).expanduser().resolve()
        dfns = load_flat(_path)
        if not dfns:
            raise ValueError(f"No DFN files found in {_path}")

        first = next(iter(dfns.values()))
        if first.schema_version == Version("1"):
            dfns = _apply_parent_inference(dfns)

        components: dict[str, Component] = {n: map_dfn(d, "2") for n, d in dfns.items()}
        return cls(components=components)
