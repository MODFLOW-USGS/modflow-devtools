import ast
import re
from collections.abc import Mapping
from os import PathLike
from pathlib import Path
from typing import Annotated, Any, Literal

import tomli
from pydantic import (
    BaseModel,
    SerializationInfo,
    computed_field,
    model_serializer,
    model_validator,
)
from pydantic import (
    Field as PydanticField,
)


class FieldBase(BaseModel):
    name: str
    longname: str | None = None
    description: str | None = None
    optional: bool = False
    default: Any | None = None
    developmode: bool = False
    netcdf: bool = False
    tagged: bool = True

    @model_serializer(mode="wrap")
    def _serialize(self, handler: Any, info: SerializationInfo) -> dict[str, Any]:
        data = handler(self)
        if info.context and info.context.get("strip_names"):
            data.pop("name", None)
        # `type` has a frozen default so exclude_defaults=True drops it; restore it.
        if "type" not in data and "type" in type(self).model_fields:
            data = {"type": getattr(self, "type"), **data}
        return data

    def dump(self, *, strip_names: bool = True, **kwargs) -> dict[str, Any]:
        if strip_names:
            kwargs["context"] = {**(kwargs.get("context") or {}), "strip_names": True}
        return self.model_dump(**kwargs)

    def dump_json(self, *, strip_names: bool = True, **kwargs) -> str:
        if strip_names:
            kwargs["context"] = {**(kwargs.get("context") or {}), "strip_names": True}
        return self.model_dump_json(**kwargs)


class Keyword(FieldBase):
    type: Literal["keyword"] = PydanticField(default="keyword", frozen=True)


class String(FieldBase):
    type: Literal["string"] = PydanticField(default="string", frozen=True)
    valid: list[str] | None = None
    case_sensitive: bool = False
    time_series: bool = False
    pk: bool = False
    fk: str | None = None
    fk_ref: str | None = None


class Integer(FieldBase):
    type: Literal["integer"] = PydanticField(default="integer", frozen=True)
    valid: list[int] | None = None
    time_series: bool = False
    pk: bool = False
    fk: str | None = None
    fk_ref: str | None = None


class Double(FieldBase):
    type: Literal["double"] = PydanticField(default="double", frozen=True)
    time_series: bool = False


class File(FieldBase):
    type: Literal["file"] = PydanticField(default="file", frozen=True)
    mode: Literal["filein", "fileout"]


Scalar = Annotated[
    Keyword | String | Integer | Double | File,
    PydanticField(discriminator="type"),
]


class Array(FieldBase):
    type: Literal["array"] = PydanticField(default="array", frozen=True)
    dtype: Literal["keyword", "integer", "double", "string"]
    shape: list[str] = []
    time_series: bool = False
    repeat: str | None = None


class Record(FieldBase):
    type: Literal["record"] = PydanticField(default="record", frozen=True)
    fields: "dict[str, Scalar | Array | Record | Union]" = PydanticField(default_factory=dict)

    @property
    def children(self) -> "dict[str, Field]":
        return self.fields  # type: ignore[return-value]


class Union(FieldBase):
    type: Literal["union"] = PydanticField(default="union", frozen=True)
    arms: "dict[str, Scalar | Array | Record]" = PydanticField(default_factory=dict)

    @property
    def children(self) -> "dict[str, Field]":
        return self.arms  # type: ignore[return-value]


class List(FieldBase):
    type: Literal["list"] = PydanticField(default="list", frozen=True)
    tagged: Literal[False] = PydanticField(default=False, frozen=True)
    item: "Record | Union"
    shape: list[str] = []

    @model_serializer(mode="wrap")
    def _serialize(self, handler: Any, info: SerializationInfo) -> dict[str, Any]:
        data = handler(self)
        if info.context and info.context.get("strip_names"):
            data.pop("name", None)
        if "type" not in data:
            data = {"type": "list", **data}
        return data

    @model_validator(mode="after")
    def _check_shape_length(self) -> "List":
        if len(self.shape) > 1:
            raise ValueError(
                f"List {self.name!r}: shape must have at most one element "
                f"(lists are 1-dimensional), got {self.shape!r}"
            )
        return self

    @property
    def children(self) -> "dict[str, Field]":
        return {"item": self.item}  # type: ignore[return-value]


Field = Annotated[
    Keyword | String | Integer | Double | File | Array | Record | Union | List,
    PydanticField(discriminator="type"),
]


Record.model_rebuild()
Union.model_rebuild()
List.model_rebuild()


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


class Dim(BaseModel):
    """A named dimension, either backed by a field or derived from an expression."""

    field: str | None = None  # name of the field that provides this dimension
    expr: str | None = None  # derivation expression, e.g. "nlay * nrow * ncol"
    scope: Literal["component", "model", "simulation"] = "component"

    @model_validator(mode="after")
    def _check_exclusive(self) -> "Dim":
        if (self.field is None) == (self.expr is None):
            raise ValueError("Dim must have exactly one of 'field' or 'expr'")
        return self

    @property
    def is_derived(self) -> bool:
        return self.expr is not None


def _parents_as_set(parent: "str | list[str] | None") -> set[str]:
    if parent is None:
        return set()
    return {parent} if isinstance(parent, str) else set(parent)


def _can_share_model(
    req_parent: "str | list[str] | None",
    dim_parent: "str | list[str] | None",
) -> bool:
    """
    Return True if the requesting component (req_parent) can be in the same
    model as the dim-defining component (dim_parent).

    The dim-provider's parent identifies which model it belongs to (a concrete
    ``<type>-nam`` name, e.g. ``"gwf-nam"``).  The requesting component's parent
    determines whether it can be in that model: an explicit match, or a generic
    type like ``"model"`` or ``"package"`` meaning any model.
    """
    dim_parents = _parents_as_set(dim_parent)
    model_contexts = {p for p in dim_parents if p.endswith("-nam") and p != "sim-nam"}
    if not model_contexts:
        return False

    req_parents = _parents_as_set(req_parent)
    for rp in req_parents:
        if rp in ("model", "package", "*"):
            return True
        if rp in model_contexts:
            return True
    return False


def _resolve_derived_dims(component: "ComponentBase", known_dims: set[str]) -> list[str]:
    """
    Validate derived dims expressions and return their names in topological order.
    Raises ValueError on cycles or unresolvable operands.

    ``known_dims`` is the full set of dim names visible to this component;
    pass ``spec.dims(name)`` or an explicit set in tests.
    """
    derived = {n: d for n, d in (component.dims or {}).items() if d.is_derived}
    if not derived:
        return []

    derived_names = set(derived.keys())
    deps: dict[str, set[str]] = {}

    for name, dim_def in derived.items():
        expr = dim_def.expr
        assert expr is not None
        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError as e:
            raise ValueError(f"Invalid dims {name!r}: {expr!r}: {e}") from e

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
                raise ValueError(f"dims {name!r} operand {op!r} is not a known dimension")
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
        raise ValueError(f"Cycle in dims: {cyclic}")

    return order


class Block(BaseModel):
    name: str
    fields: dict[str, Field]
    repeats: bool = False

    @model_validator(mode="after")
    def _check_field_order(self) -> "Block":
        fields_list = list(self.fields.items())
        list_indices = [i for i, (_, f) in enumerate(fields_list) if isinstance(f, List)]
        if len(list_indices) > 1:
            names = [fields_list[i][0] for i in list_indices]
            raise ValueError(
                f"Block {self.name!r}: at most one list field is allowed; found: {names!r}"
            )
        if list_indices and list_indices[0] != len(fields_list) - 1:
            after = [n for n, _ in fields_list[list_indices[0] + 1 :]]
            raise ValueError(
                f"Block {self.name!r}: list field must be last (lists are untagged and "
                f"consume all remaining block content); found fields after it: {after!r}"
            )
        return self

    @model_serializer(mode="wrap")
    def _serialize(self, handler: Any) -> dict[str, Any]:
        data = handler(self)
        data.pop("name", None)  # name is the dict key in ComponentBase.blocks
        return data

    def dump(self, *, strip_names: bool = True, **kwargs) -> dict[str, Any]:
        if strip_names:
            kwargs["context"] = {**(kwargs.get("context") or {}), "strip_names": True}
        return self.model_dump(**kwargs)

    def dump_json(self, *, strip_names: bool = True, **kwargs) -> str:
        if strip_names:
            kwargs["context"] = {**(kwargs.get("context") or {}), "strip_names": True}
        return self.model_dump_json(**kwargs)

    @property
    def optional(self) -> bool:
        return all(f.optional for f in self.fields.values())


Blocks = Mapping[str, Block]


class ComponentBase(BaseModel):
    schema_version: str | None = None
    name: str
    parent: str | list[str] | None = None
    dims: dict[str, Dim] | None = None
    blocks: dict[str, Block] | None = None

    @model_serializer(mode="wrap")
    def _serialize(self, handler: Any) -> dict[str, Any]:
        data = handler(self)
        if "type" not in data:
            data = {"type": getattr(self, "type"), **data}
        return data

    @property
    def fields(self) -> dict[str, Field]:
        result: dict[str, Field] = {}
        for block in (self.blocks or {}).values():
            for name, field in block.fields.items():
                if name in result:
                    raise ValueError(f"Duplicate field name {name!r} in component {self.name!r}")
                result[name] = field
        return result


class Simulation(ComponentBase):
    type: Literal["simulation"] = "simulation"


class Model(ComponentBase):
    type: Literal["model"] = "model"
    solution: Literal["ims", "ems", "sln-ims", "sln-ems"] | None = None


class Package(ComponentBase):
    type: Literal["package"] = "package"
    multi: bool = False  # whether multiple instances per parent are allowed
    subtype: Literal["solution", "exchange", "stress", "advanced", "utility"] | None = None


Component = Annotated[
    Simulation | Model | Package,
    PydanticField(discriminator="type"),
]

_DIM_RE = re.compile(r"^[A-Za-z_]\w*$")
_LOOKUP_RE = re.compile(r"^(?:([\w-]+)\.)?(\w+)\.(\w+)\((\w+)\)$")
_BOUND_RE = re.compile(r"^[<>]=?")
_ARITH_RE = re.compile(r"^([A-Za-z_]\w*)\s*[+-]\s*\d+$")


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
    spec: "Dfns | None" = None,
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
    # strip bounds (<, >, <=, >=) and validate the core identifier
    if bound_m := _BOUND_RE.match(element):
        core = element[bound_m.end() :]
        if not _DIM_RE.fullmatch(core):
            raise ValueError(
                f"Array {array_field.name!r} has invalid shape element {element!r}: "
                f"must be a plain identifier after the bound operator"
            )
        if core in known_dims:
            return
        if enclosing_record is not None:
            sibling = enclosing_record.fields.get(core)
            if isinstance(sibling, Integer):
                return
        raise ValueError(
            f"Array {array_field.name!r} shape element {element!r}: "
            f"{core!r} does not resolve to a known dim (explicit, derived, or grid)"
        )

    if _DIM_RE.fullmatch(element):
        if element in known_dims:
            return
        # Per-row varying shape: a sibling Integer with dimension="record" supplies
        # an inline count on the same line.
        if enclosing_record is not None:
            sibling = enclosing_record.fields.get(element)
            if isinstance(sibling, Integer):
                return
        raise ValueError(
            f"Array {array_field.name!r} shape element {element!r} "
            f"does not resolve to a known dim "
            f"(explicit, derived, or grid)"
        )

    if m := _LOOKUP_RE.fullmatch(element):
        component_ref, block_name, col_name, fk_field_name = m.groups()

        # array must be a subfield of a record, not a top-level block field
        if enclosing_record is None:
            raise ValueError(
                f"Array {array_field.name!r} shape element {element!r} is a "
                f"row-level lookup but the array is not inside a record"
            )

        # Resolve target component (cross-component reference or local)
        if component_ref is not None:
            if spec is None:
                raise ValueError(
                    f"Array {array_field.name!r} shape element {element!r}: "
                    f"cross-component reference requires a Dfns spec"
                )
            target = spec.components.get(component_ref)
            if target is None:
                raise ValueError(
                    f"Array {array_field.name!r} shape element {element!r}: "
                    f"component {component_ref!r} not found in spec"
                )
        else:
            target = component  # type: ignore

        # block_name must identify a list block in the target component
        list_field = _find_list_in_block(target, block_name)  # type: ignore
        if list_field is None:
            where = f"component {component_ref!r}" if component_ref else "this component"
            raise ValueError(
                f"Array {array_field.name!r} shape element {element!r}: "
                f"{block_name!r} is not a list block in {where}"
            )

        # col_name must be an Integer field in the list's item record
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

        # fk_field_name must be a sibling field in the enclosing record
        fk_field = enclosing_record.fields.get(fk_field_name)
        if fk_field is None:
            raise ValueError(
                f"Array {array_field.name!r} shape element {element!r}: "
                f"{fk_field_name!r} is not a sibling field in the enclosing record"
            )

        # fk_field.fk must be set and its block portion must match block_name
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

    # validate simple integer arithmetic
    if m := _ARITH_RE.fullmatch(element):
        dim_name = m.group(1)
        if dim_name in known_dims:
            return
        if enclosing_record is not None:
            sibling = enclosing_record.fields.get(dim_name)
            if isinstance(sibling, Integer):
                return
        raise ValueError(
            f"Array {array_field.name!r} shape element {element!r}: "
            f"{dim_name!r} does not resolve to a known dim "
            f"(explicit, derived, or grid)"
        )

    raise ValueError(
        f"Array {array_field.name!r} has invalid shape element {element!r}: "
        f"must be a dim reference (^[A-Za-z_]\\w*$), an arithmetic offset "
        f"(dim [+-] integer), or a row-level lookup (block.column(fk_field))"
    )


def _validate_list_shape_element(
    element: str,
    list_field: "List",
    known_dims: set[str],
) -> None:
    """
    Validate one element of a List.shape.

    Valid forms are a strict subset of array shape forms — no row-level lookup
    and no intra-record sibling reference, since lists are not inside records:
      - Plain dim reference
      - Bound-annotated dim reference (<, >, <=, >=)
      - Arithmetic offset (dim [+-] integer)
    """
    if bound_m := _BOUND_RE.match(element):
        core = element[bound_m.end() :]
        if not _DIM_RE.fullmatch(core):
            raise ValueError(
                f"List {list_field.name!r} has invalid shape element {element!r}: "
                f"must be a plain identifier after the bound operator"
            )
        if core not in known_dims:
            raise ValueError(
                f"List {list_field.name!r} shape element {element!r}: "
                f"{core!r} does not resolve to a known dim"
            )
        return

    if _DIM_RE.fullmatch(element):
        if element not in known_dims:
            raise ValueError(
                f"List {list_field.name!r} shape element {element!r} "
                f"does not resolve to a known dim"
            )
        return

    if m := _ARITH_RE.fullmatch(element):
        dim_name = m.group(1)
        if dim_name not in known_dims:
            raise ValueError(
                f"List {list_field.name!r} shape element {element!r}: "
                f"{dim_name!r} does not resolve to a known dim"
            )
        return

    raise ValueError(
        f"List {list_field.name!r} has invalid shape element {element!r}: "
        f"must be a dim reference (^[A-Za-z_]\\w*$), an arithmetic offset "
        f"(dim [+-] integer), or a bound-annotated dim (</<=/>/>=dim)"
    )


def _validate_fk_fields(component: "ComponentBase", spec: "Dfns") -> None:
    """
    For every Integer/String field with fk or fk_ref set, validate structure:

    - fk must reference a list block whose item must have at least one pk field.
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
    spec: "Dfns",
) -> None:
    """
    Validate all Array.shape elements in a component.
    """
    if not component.blocks:
        return

    known_dims = spec.dims(component_name)

    def _check_list(lst: "List") -> None:
        for elem in lst.shape:
            _validate_list_shape_element(elem, lst, known_dims)

    def _check_array(arr: "Array", enclosing: "Record | None") -> None:
        if not arr.shape:
            # Self-sizing (shape=[]) is valid at the top level and as the rightmost
            # subfield of a record. The only invalid case is non-rightmost in a record:
            # subsequent fields on the same line would be unreadable.
            if enclosing is not None:
                fields_list = list(enclosing.fields.keys())
                if not fields_list or fields_list[-1] != arr.name:
                    raise ValueError(
                        f"Array {arr.name!r}: only the rightmost field in a record may "
                        f"have an undeclared shape (self-sizing)"
                    )
            return  # self-sizing: nothing to validate
        for elem in arr.shape:
            _validate_shape_element(elem, arr, component, enclosing, known_dims, spec)

    for block in component.blocks.values():
        for field in block.fields.values():
            if isinstance(field, Array):
                _check_array(field, None)

            elif isinstance(field, Record):
                for subfield in field.fields.values():
                    if isinstance(subfield, Array):
                        _check_array(subfield, field)

            elif isinstance(field, List):
                if field.shape:
                    _check_list(field)
                item = field.item
                if isinstance(item, Record):
                    for subfield in item.fields.values():
                        if isinstance(subfield, Array):
                            _check_array(subfield, item)


def _inject_field_names(fields: dict) -> None:
    """
    Recursively inject name from dict key into field dicts.
    Necessary to compensate for field names being absent in
    serialized DFN file data.
    """
    for field_name, field in fields.items():
        field.setdefault("name", field_name)
        _inject_field_names(field.get("fields") or {})  # Record.fields
        _inject_field_names(field.get("arms") or {})  # Union.arms
        item = field.get("item")
        if isinstance(item, dict):
            item.setdefault("name", field_name)
            _inject_field_names(item.get("fields") or {})
            _inject_field_names(item.get("arms") or {})


def _inject_names(comp_data: dict) -> None:
    """
    Inject block and field names from dict keys before Pydantic validation.
    Necessary to compensate for field and block names being absent in
    serialized DFN file data.
    """
    for block_name, block in (comp_data.get("blocks") or {}).items():
        block.setdefault("name", block_name)
        _inject_field_names(block.get("fields") or {})


class Dfns(BaseModel):
    """A set of component definitions."""

    components: dict[str, Component] = PydanticField(default_factory=dict)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def schema_version(self) -> str:
        for c in self.components.values():
            if c.schema_version is not None:
                return c.schema_version
        return "2"

    @property
    def root(self) -> "Simulation | None":
        """The root (simulation) component, or None if not present."""
        for c in self.components.values():
            if isinstance(c, Simulation):
                return c
        return None

    def children(self, name: str) -> "dict[str, Component]":
        """Components whose parent matches ``name``."""
        return {n: c for n, c in self.components.items() if c.parent == name}

    def local_dims(self, component_name: str) -> set[str]:
        """Dim names declared in this component's dims section."""
        return set((self.components[component_name].dims or {}).keys())

    def inherited_dims(self, component_name: str) -> set[str]:
        """
        Dim names visible to ``component_name`` from other components.

        - ``"simulation"`` scope: always visible.
        - ``"model"`` scope: visible when the requesting component can share a
          model with the dim-defining component, determined purely from parent
          attributes (no hardcoded model-type strings).
        - ``"component"`` scope: visible when the dim-defining component is
          explicitly listed as a parent of the requesting component (subpackage).
        """
        inherited: set[str] = set()
        component = self.components[component_name]
        req_parent = component.parent
        for cname, c in self.components.items():
            if cname == component_name:
                continue
            for dim_name, dim in (c.dims or {}).items():
                match dim.scope:
                    case "simulation":
                        inherited.add(dim_name)
                    case "model":
                        if _can_share_model(req_parent, c.parent):
                            inherited.add(dim_name)
                    case "component":
                        if cname in _parents_as_set(req_parent):
                            inherited.add(dim_name)
        return inherited

    def dims(self, component_name: str) -> set[str]:
        """
        Return all dim names visible to ``component_name`` for shape resolution.

        This is the union of the component's own declared dims (field-backed and
        derived) and any dims inherited from other components via scoping rules.
        """
        return self.local_dims(component_name) | self.inherited_dims(component_name)

    @model_validator(mode="after")
    def _validate_schema_version(self) -> "Dfns":
        versions = {
            c.schema_version for c in self.components.values() if c.schema_version is not None
        }
        if len(versions) > 1:
            raise ValueError(
                f"All components must share the same schema_version; "
                f"found: {sorted(str(v) for v in versions)}"
            )
        return self

    @model_validator(mode="after")
    def _validate_relations(self) -> "Dfns":
        for name, component in self.components.items():
            if component.dims and any(d.is_derived for d in component.dims.values()):
                _resolve_derived_dims(component, self.dims(name))
        for name, component in self.components.items():
            _validate_fk_fields(component, self)
        for name, component in self.components.items():
            _validate_array_shapes(component, name, self)
        return self

    @classmethod
    def load(cls, path: str | PathLike) -> "Dfns":
        """Load a directory of definition files."""
        import json

        import yaml

        from modflow_devtools.dfn import schema as v1
        from modflow_devtools.dfns.migrate_v1_to_v2 import v1_to_v2

        dfns: dict = {}
        path = Path(path).expanduser().resolve()
        exclude = {"common", "flopy"}

        dfn_paths = {p.stem: p for p in path.glob("*.dfn") if p.stem not in exclude}
        toml_paths = {p.stem: p for p in path.glob("*.toml") if p.stem not in exclude}
        yaml_paths = {
            p.stem: p
            for ext in ("*.yaml", "*.yml")
            for p in path.glob(ext)
            if p.stem not in exclude
        }
        json_paths = {p.stem: p for p in path.glob("*.json") if p.stem not in exclude}

        if dfn_paths:
            dfns = v1.resolve_parents(v1.load_all(path))
            dfns = {n: v1_to_v2(d) for n, d in dfns.items()}
        elif toml_paths:
            for toml_path in toml_paths.values():
                with toml_path.open("rb") as f:
                    dfn = tomli.load(f)
                _inject_names(dfn)
                dfns[dfn["name"]] = dfn
        elif yaml_paths:
            for yaml_path in yaml_paths.values():
                with yaml_path.open() as f:
                    dfn = yaml.safe_load(f)
                _inject_names(dfn)
                dfns[dfn["name"]] = dfn
        elif json_paths:
            for json_path in json_paths.values():
                with json_path.open() as f:
                    dfn = json.load(f)
                _inject_names(dfn)
                dfns[dfn["name"]] = dfn

        return cls(components=dfns)
