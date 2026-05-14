"""
MODFLOW 6 definition file tools.
"""

import warnings
from os import PathLike
from pathlib import Path

from modflow_devtools.dfn.v1_1 import FieldV1
from modflow_devtools.dfns.schema.v2 import (
    Array,
    Block,
    Blocks,
    Component,
    DfnSpec,
    Double,
    FieldBase,
    FieldV2,
    Integer,
    Keyword,
    List,
    Record,
    String,
    Union,
)
from modflow_devtools.dfns.schema.v2 import (
    Path as PathField,
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
    "Array",
    "Block",
    "Blocks",
    "Component",
    "DfnRegistry",
    "DfnRegistryDiscoveryError",
    "DfnRegistryError",
    "DfnRegistryNotFoundError",
    "DfnSpec",
    "Double",
    "FieldBase",
    "FieldV1",
    "FieldV2",
    "Integer",
    "Keyword",
    "List",
    "LocalDfnRegistry",
    "PathField",
    "Record",
    "RemoteDfnRegistry",
    "String",
    "Union",
    "get_dfn",
    "get_dfn_path",
    "get_registry",
    "get_sync_status",
    "is_valid",
    "list_components",
    "sync_dfns",
]


def is_valid(path: "str | PathLike", format: str = "dfn", verbose: bool = False) -> bool:
    """Validate DFN file(s)."""
    from modflow_devtools.dfn.mapper import is_valid as _is_valid

    return _is_valid(path, format=format, verbose=verbose)


# =============================================================================
# Registry lazy-import machinery
# =============================================================================


def _get_registry_module():
    from modflow_devtools.dfns import registry

    return registry


def __getattr__(name: str):
    registry_exports = {
        "DfnRegistry",
        "DfnRegistryDiscoveryError",
        "DfnRegistryError",
        "DfnRegistryNotFoundError",
        "LocalDfnRegistry",
        "RemoteDfnRegistry",
        "get_registry",
        "get_sync_status",
        "sync_dfns",
    }
    if name in registry_exports:
        registry = _get_registry_module()
        return getattr(registry, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# =============================================================================
# Module-level convenience functions
# =============================================================================


def get_dfn(
    component: str,
    ref: str = "develop",
    source: str = "modflow6",
    path: "str | PathLike | None" = None,
) -> "Component":
    """Get a component definition by name from the registry."""
    registry = _get_registry_module()
    reg = registry.get_registry(source=source, ref=ref, path=path)
    return reg.get_dfn(component)


def get_dfn_path(
    component: str,
    ref: str = "develop",
    source: str = "modflow6",
    path: "str | PathLike | None" = None,
) -> Path:
    """Get the local cached file path for a DFN component."""
    registry = _get_registry_module()
    reg = registry.get_registry(source=source, ref=ref, path=path)
    return reg.get_dfn_path(component)


def list_components(
    ref: str = "develop",
    source: str = "modflow6",
    path: "str | PathLike | None" = None,
) -> list[str]:
    """List available components for a registry."""
    registry = _get_registry_module()
    reg = registry.get_registry(source=source, ref=ref, path=path)
    return list(reg.spec.components.keys())
