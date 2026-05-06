from dataclasses import dataclass
from typing import Any, Literal

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
class FieldV1:
    # Shared base attributes (inlined from the deleted field.py)
    name: str
    type: str | None = None
    block: str | None = None
    default: Any | None = None
    longname: str | None = None
    description: str | None = None
    optional: bool = False
    developmode: bool = False
    shape: str | None = None
    valid: tuple[str, ...] | None = None
    netcdf: bool = False
    tagged: bool = False
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
