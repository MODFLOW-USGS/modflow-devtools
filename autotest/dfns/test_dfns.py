from __future__ import annotations

from unittest.mock import patch

import pytest
from packaging.version import Version

from modflow_devtools.dfns import Dfns, LocalDfnRegistry
from modflow_devtools.markers import requires_pkg


@pytest.mark.parametrize("schema_version", [None, Version("2")])
def test_load(dfn_dir, schema_version):
    spec = Dfns.load(dfn_dir, schema_version=schema_version)
    assert spec.schema_version == Version("2")
    assert spec.root is not None
    assert spec.root.name == "sim-nam"
    assert len(spec.components) > 100
    assert "sim-nam" in spec.components
    assert "gwf-nam" in spec.components
    assert "gwf-chd" in spec.components
    assert "gwf-wel" in spec.components.keys()
    assert "garbage" not in spec.components

    gwf_chd = spec.components["gwf-chd"]
    assert gwf_chd.name == "gwf-chd"
    assert gwf_chd.parent == "gwf-nam"

    sim_children = spec.children_of("sim-nam")
    assert "gwf-nam" in sim_children

    gwf_children = spec.children_of("gwf-nam")
    assert "gwf-chd" in gwf_children


def test_load_empty_directory(function_tmpdir):
    with pytest.raises(ValueError, match="No DFN files found"):
        Dfns.load(function_tmpdir)


# =============================================================================
# Convenience functions with path
# =============================================================================


def test_get_dfn(dfn_dir):
    from modflow_devtools.dfns import get_dfn

    dfn = get_dfn("gwf-chd", path=dfn_dir)
    assert dfn.name == "gwf-chd"
    assert dfn.parent == "gwf-nam"


def test_get_dfn_path(dfn_dir):
    from modflow_devtools.dfns import get_dfn_path

    file_path = get_dfn_path("gwf-chd", path=dfn_dir)
    assert file_path.exists()
    assert file_path.name == "gwf-chd.dfn"


def test_list_components(dfn_dir):
    from modflow_devtools.dfns import list_components

    components = list_components(path=dfn_dir)
    assert len(components) > 100
    assert "gwf-chd" in components


# =============================================================================
# Module-level functions
# =============================================================================


@requires_pkg("boltons", "pydantic")
class TestModuleFunctions:
    def test_list_components_local(dfn_dir):
        registry = LocalDfnRegistry(path=dfn_dir)
        components = registry.list_components()
        assert len(components) > 100
        assert "gwf-chd" in components
        assert "sim-nam" in components


# =============================================================================
# CLI
# =============================================================================


@requires_pkg("pydantic")
class TestCLI:
    def test_main_help(self):
        from modflow_devtools.dfns.__main__ import main

        result = main([])
        assert result == 0

    def test_info_command(self):
        from modflow_devtools.dfns.__main__ import main

        result = main(["info"])
        assert result == 0

    def test_clean_command_no_cache(self, tmp_path):
        from modflow_devtools.dfns.__main__ import main

        with patch("modflow_devtools.dfns.__main__.get_cache_dir") as mock_cache_dir:
            mock_cache_dir.return_value = tmp_path / "nonexistent"
            result = main(["clean"])

        assert result == 0

    def test_sync_invalid_ref(self):
        from modflow_devtools.dfns.__main__ import main

        result = main(["sync", "--ref", "not-a-version"])
        assert result == 1


# =============================================================================
# Autodiscovery workflow
# =============================================================================


@requires_pkg("boltons", "pydantic")
def test_autodiscovery_workflow(dfn_dir):
    from modflow_devtools.dfns import get_dfn, get_registry, list_components

    registry = get_registry(path=dfn_dir, ref="local")

    components = registry.list_components()
    assert len(components) > 100

    gwf_chd = registry.get_dfn("gwf-chd")
    assert gwf_chd.name == "gwf-chd"
    assert gwf_chd.blocks is not None

    chd_path = registry.get_dfn_path("gwf-chd")
    assert chd_path.exists()

    components_list = list_components(path=dfn_dir)
    assert "gwf-chd" in components_list

    dfn = get_dfn("gwf-wel", path=dfn_dir)
    assert dfn.name == "gwf-wel"
