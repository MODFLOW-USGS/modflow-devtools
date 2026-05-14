from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from boltons.dictutils import OMD
from packaging.version import Version


@dataclass(kw_only=True)
class FieldV1_1:
    name: str
    type: str | None = None
    block: str | None = None
    default: Any | None = None
    longname: str | None = None
    description: str | None = None
    children: Mapping[str, FieldV1_1] | None = None
    optional: bool = False
    developmode: bool = False
    shape: str | None = None
    valid: tuple[str, ...] | None = None
    netcdf: bool = False
    tagged: bool = False

    @classmethod
    def from_dict(cls, d: dict, strict: bool = False) -> FieldV1_1:
        keys = set(cls.__dataclass_fields__.keys())
        if strict:
            if extra_keys := set(d.keys()) - keys:
                raise ValueError(f"Unrecognized keys in field data: {extra_keys}")
        return cls(**{k: v for k, v in d.items() if k in keys})


Block = Mapping[str, FieldV1_1]
Blocks = Mapping[str, Block]


def block_sort_key(item: tuple[str, Any]) -> int:
    """Sort blocks in canonical MF6 order."""
    order = ["options", "dimensions", "griddata", "packagedata", "connectiondata", "period"]
    name = item[0]
    try:
        return order.index(name)
    except ValueError:
        return len(order)


FieldType = Literal[
    "keyword",
    "integer",
    "double precision",
    "string",
    "record",
    "recarray",
    "keystring",
]

SCALAR_TYPES = ("keyword", "integer", "double precision", "string")

Reader = Literal[
    "urword",
    "u1ddbl",
    "u2ddbl",
    "readarray",
]


@dataclass(kw_only=True)
class FieldV1(FieldV1_1):
    # V1-specific attributes
    reader: Reader = "urword"
    in_record: bool = False
    layered: bool | None = None
    preserve_case: bool = False
    numeric_index: bool = False
    deprecated: bool = False
    removed: bool = False
    mf6internal: str | None = None
    block_variable: bool = False
    just_data: bool = False
    time_series: bool = False

    @classmethod
    def from_dict(cls, d: dict, strict: bool = False) -> "FieldV1":
        keys = set(cls.__dataclass_fields__.keys())
        if strict:
            if extra_keys := set(d.keys()) - keys:
                raise ValueError(f"Unrecognized keys in field data: {extra_keys}")
        return cls(**{k: v for k, v in d.items() if k in keys})


@dataclass(kw_only=True)
class Dfn:
    """
    MODFLOW 6 input component definition (v1 / v1.1 schema).

    Attributes
    ----------
    schema_version : Version
        Schema version of this definition.
    name : str
        Component name (e.g., "gwf-chd", "sim-nam").
    parent : str | list[str] | None
        Valid parent component type(s).
    advanced : bool
        Whether this is an advanced package.
    multi : bool
        Whether this is a multi-package.
    ftype : str | None
        MODFLOW 6 file type string, if applicable.
    blocks : Blocks | None
        Block definitions containing field specifications.
    children : Dfns | None
        Child component instances (populated by to_tree).
    subcomponents : list[str] | None
        Allowed child component types (schema-level constraint).
    """

    schema_version: Version
    name: str
    parent: str | list[str] | None = None
    advanced: bool = False
    multi: bool = False
    ftype: str | None = None
    blocks: Blocks | None = None
    children: Dfns | None = None
    subcomponents: list[str] | None = None

    def __post_init__(self) -> None:
        self.schema_version = Version(str(self.schema_version))
        if self.blocks is not None:
            self.blocks = dict(sorted(self.blocks.items(), key=block_sort_key))

    @property
    def fields(self) -> OMD:
        """Combined map of fields from all blocks (flat, top-level only)."""
        items = []
        for block in (self.blocks or {}).values():
            for f in block.values():
                items.append((f.name, f))
        return OMD(items)

    @classmethod
    def from_dict(cls, d: dict, strict: bool = False) -> Dfn:
        """
        Create a Dfn from a dictionary.

        Parameters
        ----------
        d : dict
            Dictionary containing DFN data.
        strict : bool, optional
            If True, raise ValueError for unrecognized keys at any level.
        """
        from modflow_devtools.dfns.schema.v2 import FieldBase

        known_keys = set(cls.__dataclass_fields__.keys())
        schema_version = Version(str(d.get("schema_version", "2")))
        is_v1 = schema_version == Version("1")

        if strict:
            extra = set(d.keys()) - known_keys
            if extra:
                raise ValueError(f"Unrecognized keys in DFN data: {extra}")

        data = {k: v for k, v in d.items() if k in known_keys}
        data.setdefault("schema_version", schema_version)

        if blocks_raw := data.get("blocks"):
            parsed_blocks: dict[str, Any] = {}
            for block_name, block_data in blocks_raw.items():
                if not isinstance(block_data, dict):
                    parsed_blocks[block_name] = block_data
                    continue
                block_fields: dict[str, Any] = {}
                for field_name, field_data in block_data.items():
                    if isinstance(field_data, dict):
                        if is_v1:
                            block_fields[field_name] = FieldV1.from_dict(field_data, strict=strict)
                        else:
                            block_fields[field_name] = FieldBase.from_dict(
                                field_data, strict=strict
                            )
                    else:
                        block_fields[field_name] = field_data
                parsed_blocks[block_name] = block_fields
            data["blocks"] = parsed_blocks

        return cls(**data)


Dfns = dict[str, Dfn]
