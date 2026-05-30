"""Basic tests for the DFN schema"""

import pytest

from modflow_devtools.dfns import Dfns
from modflow_devtools.dfns.schema import (
    Block,
    Integer,
    Model,
    Package,
    Simulation,
)


def test_field_dict_roundtrip():
    i = Integer(
        name="nper",
        description="number of stress periods",
        optional=False,
    )
    f = Integer.model_validate(i.model_dump())
    assert f.name == i.name
    assert f.type == i.type
    assert f.description == i.description
    assert f.optional == i.optional


def test_block_optional_all_optional_fields():
    from modflow_devtools.dfns.schema import Keyword

    block = Block(
        name="options",
        fields={
            "verbose": Keyword(name="verbose", optional=True),
            "maxiter": Integer(name="maxiter", optional=True),
        },
    )
    assert block.optional is True


def test_block_optional_has_required_field():
    block = Block(
        name="dimensions",
        fields={
            "nlay": Integer(name="nlay"),
            "nrow": Integer(name="nrow", optional=True),
        },
    )
    assert block.optional is False


def test_block_optional_empty_fields():
    block = Block(name="empty", fields={})
    assert block.optional is True


def _pkg(name: str, blocks=None, dims=None, parent=None, **kw) -> Package:
    return Package(name=name, blocks=blocks, dims=dims, parent=parent, **kw)


def test_schema_version():
    pkg = _pkg("gwf-chd")
    spec = Dfns(components={"gwf-chd": pkg})
    assert spec.schema_version == "2.0.0.dev2"  # default

    pkg = Package(name="gwf-chd", schema_version="2.0.0.dev2")
    spec = Dfns(components={"gwf-chd": pkg})
    assert spec.schema_version == "2.0.0.dev2"


def test_schema_version_inconsistency():
    pkg1 = Package(name="gwf-chd", schema_version="2.0.0.dev2")
    pkg2 = Package(name="gwf-wel", schema_version="3")
    with pytest.raises(ValueError, match="schema_version"):
        Dfns(components={"gwf-chd": pkg1, "gwf-wel": pkg2})


def test_schema_version_consistency_null_ignored():
    pkg1 = Package(name="gwf-chd", schema_version="2.0.0.dev2")
    pkg2 = Package(name="gwf-wel", schema_version=None)
    spec = Dfns(components={"gwf-chd": pkg1, "gwf-wel": pkg2})
    assert spec.schema_version == "2.0.0.dev2"


def test_children_of():
    gwf = Model(name="gwf-nam", blocks=None)
    chd = _pkg("gwf-chd", parent="gwf-nam")
    rch = _pkg("gwf-rch", parent="gwf-nam")
    sim = Simulation(name="sim-nam", blocks=None)
    spec = Dfns(components={"sim-nam": sim, "gwf-nam": gwf, "gwf-chd": chd, "gwf-rch": rch})
    children = spec.children("gwf-nam")
    assert set(children) == {"gwf-chd", "gwf-rch"}


def test_children_of_empty():
    pkg = _pkg("gwf-chd", parent="gwf-nam")
    spec = Dfns(components={"gwf-chd": pkg})
    assert spec.children("gwf-chd") == {}


def test_load(dfn_dir):
    spec = Dfns.load(dfn_dir)
    assert spec.schema_version == "2.0.0.dev2"
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


def test_component_fields_no_blocks():
    pkg = _pkg("gwf-chd")
    assert pkg.get_fields() == {}


def test_component_fields_none_blocks():
    pkg = Package(name="gwf-chd", blocks=None)
    assert pkg.get_fields() == {}


def test_component_fields_single_block():
    nlay = Integer(name="nlay")
    nrow = Integer(name="nrow")
    pkg = _pkg(
        "gwf-dis",
        blocks={"dimensions": Block(name="dimensions", fields={"nlay": nlay, "nrow": nrow})},
    )
    assert pkg.get_fields() == {"nlay": nlay, "nrow": nrow}


def test_component_fields_multiple_blocks():
    from modflow_devtools.dfns.schema import Keyword

    verbose = Keyword(name="verbose", optional=True)
    nlay = Integer(name="nlay")
    pkg = _pkg(
        "gwf-dis",
        blocks={
            "options": Block(name="options", fields={"verbose": verbose}),
            "dimensions": Block(name="dimensions", fields={"nlay": nlay}),
        },
    )
    assert pkg.get_fields() == {"verbose": verbose, "nlay": nlay}


def test_component_fields_duplicate_name():
    a1 = Integer(name="a")
    a2 = Integer(name="a", optional=True)
    pkg = _pkg(
        "gwf-dis",
        blocks={
            "block1": Block(name="block1", fields={"a": a1}),
            "block2": Block(name="block2", fields={"a": a2}),
        },
    )
    fields = pkg.get_fields()
    assert fields.getlist("a") == [a1, a2]


def test_get_block_no_blocks():
    pkg = _pkg("gwf-chd")
    assert pkg.get_block("nlay") is None


def test_get_block_none_blocks():
    pkg = Package(name="gwf-chd", blocks=None)
    assert pkg.get_block("nlay") is None


def test_get_block_field_not_found():
    nlay = Integer(name="nlay")
    pkg = _pkg(
        "gwf-dis",
        blocks={"dimensions": Block(name="dimensions", fields={"nlay": nlay})},
    )
    assert pkg.get_block("nrow") is None


def test_get_block_found():
    nlay = Integer(name="nlay")
    dim_block = Block(name="dimensions", fields={"nlay": nlay})
    pkg = _pkg("gwf-dis", blocks={"dimensions": dim_block})
    assert pkg.get_block("nlay") is dim_block


def test_get_block_found_in_second_block():
    from modflow_devtools.dfns.schema import Keyword

    verbose = Keyword(name="verbose", optional=True)
    nlay = Integer(name="nlay")
    opt_block = Block(name="options", fields={"verbose": verbose})
    dim_block = Block(name="dimensions", fields={"nlay": nlay})
    pkg = _pkg(
        "gwf-dis",
        blocks={"options": opt_block, "dimensions": dim_block},
    )
    assert pkg.get_block("verbose") is opt_block
    assert pkg.get_block("nlay") is dim_block


def test_component_fields_loaded(dfn_dir):
    spec = Dfns.load(dfn_dir)
    gwf_dis = spec.components["gwf-dis"]
    fields = gwf_dis.get_fields()
    assert isinstance(fields, dict)
    assert len(fields) > 0
    # every value is a Field instance, every key matches the field's name
    for name, field in fields.items():
        assert name == field.name
    # fields from all blocks are present (nlay is in dimensions, not options)
    assert "nlay" in fields
