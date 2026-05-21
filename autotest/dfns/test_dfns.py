from modflow_devtools.dfns import Dfns
from modflow_devtools.markers import requires_pkg


def test_load(dfn_dir):
    spec = Dfns.load(dfn_dir)
    assert spec.schema_version == "2"
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

    sim_children = spec.children("sim-nam")
    assert "gwf-nam" in sim_children

    gwf_children = spec.children("gwf-nam")
    assert "gwf-chd" in gwf_children


def test_load_empty_directory(function_tmpdir):
    spec = Dfns.load(function_tmpdir)
    assert len(spec.components) == 0


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

    def test_clean_command(self):
        from modflow_devtools.dfns.__main__ import main

        result = main(["clean"])
        assert result == 0
