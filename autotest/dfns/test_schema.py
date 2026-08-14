"""Basic tests for the DFN schema"""

from pathlib import Path

import pytest

from modflow_devtools.dfns import Dfns
from modflow_devtools.dfns.schema import (
    Array,
    Block,
    File,
    Integer,
    Keyword,
    List,
    MemoryScalar,
    Model,
    Package,
    Record,
    Simulation,
    String,
    Union,
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
    assert spec.schema_version == "2.0.0.dev3"  # default

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


def test_memory_phase_permissions_fc_readonly_ok():
    pkg = _pkg("gwf-npf", memory={"hcof": MemoryScalar(type="double", set_in="fc", readonly=True)})
    Dfns(components={"gwf-npf": pkg})  # must not raise


def test_memory_phase_permissions_cq_readonly_ok():
    pkg = _pkg(
        "gwf-wel", memory={"simvals": MemoryScalar(type="double", set_in="cq", readonly=True)}
    )
    Dfns(components={"gwf-wel": pkg})  # must not raise


def test_memory_phase_permissions_fc_not_readonly_raises():
    pkg = _pkg("gwf-npf", memory={"hcof": MemoryScalar(type="double", set_in="fc", readonly=False)})
    with pytest.raises(Exception, match="readonly"):
        Dfns(components={"gwf-npf": pkg})


def test_memory_phase_permissions_cq_not_readonly_raises():
    pkg = _pkg(
        "gwf-wel", memory={"simvals": MemoryScalar(type="double", set_in="cq", readonly=False)}
    )
    with pytest.raises(Exception, match="readonly"):
        Dfns(components={"gwf-wel": pkg})


def test_memory_phase_permissions_list_with_fc_raises():
    pkg = _pkg(
        "gwf-npf", memory={"sat": MemoryScalar(type="double", set_in=["ar", "fc"], readonly=False)}
    )
    with pytest.raises(Exception, match="readonly"):
        Dfns(components={"gwf-npf": pkg})


def test_memory_output_bool_ok():
    pkg = _pkg(
        "gwf-npf",
        memory={"flowja": MemoryScalar(type="double", set_in="cq", readonly=True, output=True)},
    )
    Dfns(components={"gwf-npf": pkg})  # must not raise


def test_memory_output():
    pkg = _pkg(
        "gwf-wel",
        memory={
            "save_flows": MemoryScalar(type="logical", set_in="ar"),
            "simvals": MemoryScalar(type="double", set_in="cq", readonly=True, output=True),
        },
    )
    Dfns(components={"gwf-wel": pkg})


def test_memory_budget_accepted():
    pkg = _pkg(
        "gwf-wel",
        memory={"simvals": MemoryScalar(type="double", set_in="cq", readonly=True, budget="WEL")},
    )
    Dfns(components={"gwf-wel": pkg})  # must not raise
    assert pkg.memory["simvals"].budget == "WEL"


def test_memory_obs_type_accepted():
    pkg = _pkg(
        "gwf-wel",
        memory={"simvals": MemoryScalar(type="double", set_in="cq", readonly=True, obs_type="WEL")},
    )
    Dfns(components={"gwf-wel": pkg})  # must not raise
    assert pkg.memory["simvals"].obs_type == "WEL"


_DEV3_SNAPSHOT_DIR = Path(__file__).parent / "__snapshots__" / "v2.0.0.dev3"


@pytest.fixture(scope="module")
def dev3_spec():
    return Dfns.load(_DEV3_SNAPSHOT_DIR)


def test_memory_output_attributes_in_snapshot(dev3_spec):
    """Stress package simvals must carry budget, obs_type, and output in the migrated spec."""
    wel = dev3_spec.components["gwf-wel"]
    simvals = wel.memory["simvals"]
    assert simvals.budget == "WEL"
    assert simvals.obs_type == "WEL"
    assert simvals.output is True

    simtomvr = wel.memory["simtomvr"]
    assert simtomvr.budget == "WEL-TO-MVR"
    assert simtomvr.output is True
    assert simtomvr.obs_type is None  # to-mvr flows are not observable


def test_memory_output_attributes_rcha(dev3_spec):
    """RCHA budget term differs from its obs type (obs type is always RCH)."""
    rcha = dev3_spec.components["gwf-rcha"]
    simvals = rcha.memory["simvals"]
    assert simvals.budget == "RCHA"
    assert simvals.obs_type == "RCH"
    assert simvals.output is True


def test_render_respects_tagged_scalars_in_record(dev3_spec):
    """Tagged Integer/String subfields of a Record must keep their keyword on render()."""
    render = dev3_spec.components["gwf-oc"].blocks["options"].render()
    assert "HEAD PRINT_FORMAT COLUMNS <columns> WIDTH <width> DIGITS <digits> <format>" in render


def test_render_respects_untagged_arrays_in_record(dev3_spec):
    """Untagged Array subfields of a Record (e.g. cellid) must render without a keyword."""
    render = dev3_spec.components["gwf-chd"].blocks["period"].render()
    assert "<cellid(ncelldim)> <head>" in render
    assert "CELLID" not in render


def test_block_header_scalar(dev3_spec):
    """A block_variable scalar (e.g. iper) attaches to the block as `header`, not a body field."""
    period = dev3_spec.components["gwf-wel"].blocks["period"]
    assert "iper" not in period.fields
    assert isinstance(period.header, Integer)
    assert period.header.name == "iper"
    assert period.header.tagged is False


def test_block_header_record(dev3_spec):
    """A block_variable record (e.g. utl-obs's `output`) attaches to the block as `header`."""
    continuous = dev3_spec.components["utl-obs"].blocks["continuous"]
    assert "output" not in continuous.fields
    assert isinstance(continuous.header, Record)
    assert continuous.header.name == "output"


def test_get_fields_and_get_block_include_header(dev3_spec):
    """get_fields()/get_block() must see block.header, not just block.fields."""
    wel = dev3_spec.components["gwf-wel"]
    fields = wel.get_fields(recurse=True)
    assert "iper" in fields
    assert fields["iper"].tagged is False
    assert wel.get_block("iper") is wel.blocks["period"]


def test_render_block_header_scalar(dev3_spec):
    """render() attaches a scalar header to the BEGIN line, matching mf6io.pdf."""
    render = dev3_spec.components["gwf-wel"].blocks["period"].render()
    assert render.startswith("BEGIN PERIOD <iper>\n")


def test_render_block_header_record(dev3_spec):
    """render() attaches a record header to the BEGIN line, matching mf6io.pdf."""
    render = dev3_spec.components["utl-obs"].blocks["continuous"].render()
    assert render.startswith("BEGIN CONTINUOUS FILEOUT <obs_output_file_name> [BINARY]\n")


def test_render_file_field_named_after_path_not_tag(dev3_spec):
    """The File placeholder is named after the v1 path subfield, matching mf6io.pdf
    (e.g. <afrcsvfile>), not the tag keyword (e.g. <auto_flow_reduce_csv>)."""
    render = dev3_spec.components["gwf-wel"].blocks["options"].render()
    assert "AUTO_FLOW_REDUCE_CSV FILEOUT <afrcsvfile>" in render


def test_file_filerecord_not_collapsed(dev3_spec):
    """A v1 filerecord stays a Record of {tag Keyword(s), path File}; the tag
    keyword isn't folded into the File field itself (no File.tag)."""
    afrcsv = dev3_spec.components["gwf-wel"].blocks["options"].fields["afrcsv_filerecord"]
    assert isinstance(afrcsv, Record)
    assert list(afrcsv.fields.keys()) == ["auto_flow_reduce_csv", "afrcsvfile"]

    tag_field = afrcsv.fields["auto_flow_reduce_csv"]
    assert tag_field.type == "keyword"

    file_field = afrcsv.fields["afrcsvfile"]
    assert file_field.type == "file"
    assert file_field.tagged is False
    assert file_field.direction == "out"
    assert not hasattr(file_field, "tag")


def test_file_filerecord_multiword_tag_not_collapsed(dev3_spec):
    """A multi-word v1 tag (e.g. `CROSS_SECTION TAB6`) becomes two sibling
    Keyword fields, not a single synthetic File.tag string."""
    period = dev3_spec.components["gwf-sfr"].blocks["period"]
    item = period.fields["perioddata"].item
    union = item.children["sfrsetting"]
    xsrecord = union.arms["cross_sectionrecord"]
    assert isinstance(xsrecord, Record)
    assert list(xsrecord.fields.keys()) == ["cross_section", "tab6", "tab6_filename"]
    assert xsrecord.fields["cross_section"].type == "keyword"
    assert xsrecord.fields["tab6"].type == "keyword"
    assert xsrecord.fields["tab6_filename"].direction == "in"


def test_memory_output_attributes_chd_no_to_mvr(dev3_spec):
    """CHD does not support the Water Mover provider role; simtomvr has no budget."""
    chd = dev3_spec.components["gwf-chd"]
    simvals = chd.memory["simvals"]
    assert simvals.budget == "CHD"
    assert simvals.obs_type == "CHD"
    assert simvals.output is True

    simtomvr = chd.memory["simtomvr"]
    assert simtomvr.budget is None
    assert simtomvr.output is None


# --- FieldBase.render() -----------------------------------------------------


def test_render_keyword():
    field = Keyword(name="verbose")
    assert field.render() == "VERBOSE"
    assert field.render(inline=True) == "VERBOSE"


def test_render_keyword_optional():
    field = Keyword(name="verbose", optional=True)
    assert field.render() == "[VERBOSE]"
    assert field.render(inline=True) == "[VERBOSE]"


def test_render_scalar_tagged():
    field = String(name="fname", tagged=True)
    assert field.render() == "FNAME <fname>"
    assert field.render(inline=True) == "FNAME <fname>"


def test_render_scalar_untagged():
    field = Integer(name="nper", tagged=False)
    assert field.render() == "<nper>"
    assert field.render(inline=True) == "<nper>"


def test_render_file():
    filein = File(name="path", direction="in", tagged=False)
    assert filein.render() == "FILEIN <path>"
    assert filein.render(inline=True) == "FILEIN <path>"

    fileout = File(name="csvfile", direction="out", tagged=True)
    assert fileout.render() == "CSVFILE FILEOUT <csvfile>"
    assert fileout.render(inline=True) == "CSVFILE FILEOUT <csvfile>"


def test_render_array_no_shape():
    """A shapeless Array has no READARRAY annotation; inline is a no-op."""
    field = Array(name="aux", dtype="double", tagged=False)
    assert field.render() == "<aux>"
    assert field.render(inline=True) == "<aux>"


def test_render_array_with_shape():
    """Non-inline adds the NAME/READARRAY annotation; inline is the bare token."""
    field = Array(name="k", dtype="double", shape=["nodes"], tagged=True)
    assert field.render() == "K\n  <k(nodes)> -- READARRAY"
    assert field.render(inline=True) == "K <k(nodes)>"


def test_render_record():
    """Record inline-expands its children the same way whether inline or not."""
    field = Record(
        name="tabrecord",
        fields={
            "tab6": Keyword(name="tab6"),
            "fname": File(name="fname", direction="in", tagged=False),
        },
    )
    assert field.render() == "TAB6 FILEIN <fname>"
    assert field.render(inline=True) == "TAB6 FILEIN <fname>"


def test_render_union_default_expands_arms():
    """A standalone Union field's default render() is one row per arm, wrapped
    in [...] if the *Union* itself (not the arm) is optional."""
    field = Union(
        name="ocsetting",
        optional=True,
        arms={
            "save": Record(
                name="saverecord",
                fields={
                    "save": Keyword(name="save"),
                    "rtype": String(name="rtype", tagged=False),
                },
            ),
            "print": Record(
                name="printrecord",
                fields={
                    "print": Keyword(name="print"),
                    "rtype": String(name="rtype", tagged=False),
                },
            ),
        },
    )
    assert field.render() == "[SAVE <rtype>]\n[PRINT <rtype>]"


def test_render_union_inline_collapses():
    """A Union nested in a Record/List row collapses to a bare placeholder."""
    field = Union(
        name="ocsetting",
        arms={
            "save": Record(name="saverecord", fields={"save": Keyword(name="save")}),
            "print": Record(name="printrecord", fields={"print": Keyword(name="print")}),
        },
    )
    assert field.render(inline=True) == "<ocsetting>"


def test_render_union_default_scalar_arm():
    """A non-Record arm renders as its bare token (Keyword: NAME; else: <name>),
    ignoring the arm's own `tagged` — matches the pre-refactor behavior."""
    field = Union(
        name="releasesetting",
        arms={
            "all": Keyword(name="all"),
            "frequency": Integer(name="frequency", tagged=True),
        },
    )
    assert field.render() == "ALL\n<frequency>"


def test_render_list_inline_raises():
    """List has no inline form — it can never appear nested in a Record/Union,
    so `inline=True` is a caller misuse, not a reachable internal state."""
    field = List(
        name="stress_period_data",
        item=Record(name="stress_period_data", fields={"cellid": Keyword(name="cellid")}),
    )
    with pytest.raises(ValueError):
        field.render(inline=True)


def test_render_list_single_row_type():
    field = List(
        name="perioddata",
        item=Record(
            name="perioddata",
            fields={
                "cellid": Keyword(name="cellid"),
                "head": String(name="head", tagged=False),
            },
        ),
    )
    assert field.render() == "CELLID <head>\nCELLID <head>\n..."


def test_render_block_matches_per_field_assembly(dev3_spec):
    """Block.render() must equal BEGIN/END plus each field's own render(),
    indented by the block — guards the two entry points against drifting apart."""
    for component in dev3_spec.components.values():
        for block in (component.blocks or {}).values():
            begin = f"BEGIN {block.name.upper()}"
            if block.header is not None:
                begin = f"{begin} {block.header.render(inline=True)}"
            lines = [begin]
            for field in block.fields.values():
                lines.extend(f"  {line}" for line in field.render().split("\n"))
            lines.append(f"END {block.name.upper()}")
            assert block.render() == "\n".join(lines)
