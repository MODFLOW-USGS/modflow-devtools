"""Definition file tools"""

import warnings

from modflow_devtools.dfn import FieldType, fetch_dfns
from modflow_devtools.dfns.migrate import migrate
from modflow_devtools.dfns.registry import DfnRegistry, LocalDfnRegistry, RemoteDfnRegistry
from modflow_devtools.dfns.schema import (
    CURRENT_SCHEMA_VERSION,
    Array,
    Block,
    Blocks,
    Component,
    Dfns,
    Double,
    Field,
    FieldBase,
    File,
    Integer,
    Keyword,
    List,
    Model,
    Package,
    Record,
    Scalar,
    Simulation,
    String,
    Union,
)

# Experimental API warning
warnings.warn(
    "The modflow_devtools.dfns API is experimental and may change or be "
    "removed in future versions without following normal deprecation procedures. "
    "Use at your own risk. To suppress this warning, use:\n"
    "  warnings.filterwarnings('ignore', "
    "message='.*modflow_devtools.dfns.*experimental.*')",
    FutureWarning,
    stacklevel=2,
)

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "Array",
    "Block",
    "Blocks",
    "Component",
    "DfnRegistry",
    "Dfns",
    "Double",
    "Field",
    "FieldBase",
    "FieldType",
    "File",
    "Integer",
    "Keyword",
    "List",
    "LocalDfnRegistry",
    "Model",
    "Package",
    "Record",
    "RemoteDfnRegistry",
    "Scalar",
    "Simulation",
    "String",
    "Union",
    "fetch_dfns",
    "migrate",
]
