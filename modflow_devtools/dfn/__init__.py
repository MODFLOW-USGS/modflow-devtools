"""
MODFLOW 6 definition file tools (v1 / v1.1 schema).
"""

from modflow_devtools.dfn.v1 import (
    Dfn,
    Dfns,
    Field,
    Fields,
    FieldType,
    FormatVersion,
    Reader,
    Ref,
    Sln,
    get_dfns,
)
from modflow_devtools.dfn.v1_1 import Dfn as DfnSpec
from modflow_devtools.dfn.v1_1 import FieldV1, FieldV1_1

__all__ = [
    "Dfn",
    "DfnSpec",
    "Dfns",
    "Field",
    "FieldType",
    "FieldV1",
    "FieldV1_1",
    "Fields",
    "FormatVersion",
    "Reader",
    "Ref",
    "Sln",
    "get_dfns",
]
