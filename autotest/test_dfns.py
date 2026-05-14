import dataclasses
from pathlib import Path

import pytest
from packaging.version import Version

from modflow_devtools.dfn.mapper import (
    _apply_parent_inference,
    _dfn_to_plain_dict,
    _load_common,
    _toml_safe,
    load,
    load_flat,
    map as map_v1_1,
    to_flat,
    to_tree,
)
from modflow_devtools.dfn.v1_1 import Dfn, FieldV1, FieldV1_1
from modflow_devtools.dfns import is_valid
from modflow_devtools.dfns.fetch import fetch_dfns
from modflow_devtools.dfns.mapper import MapV1To2
from modflow_devtools.dfns.mapper import map as map_v2
from modflow_devtools.dfns.schema.v2 import (
    Array,
    Double,
    FieldBase,
    Integer,
    Keyword,
    Record,
    String,
)
from modflow_devtools.markers import requires_pkg

PROJ_ROOT = Path(__file__).parents[1]
DFN_DIR = PROJ_ROOT / "autotest" / "temp" / "dfns"
MF6_OWNER = "MODFLOW-ORG"
MF6_REPO = "modflow6"
MF6_REF = "develop"
EMPTY_DFNS = {"exg-gwfgwe", "exg-gwfgwt", "exg-gwfprt", "sln-ems"}


def pytest_generate_tests(metafunc):
    if "dfn_name" in metafunc.fixturenames:
        if not any(DFN_DIR.glob("*.dfn")):
            fetch_dfns(MF6_OWNER, MF6_REPO, MF6_REF, DFN_DIR, verbose=True)
        dfn_names = [
            dfn.stem for dfn in DFN_DIR.glob("*.dfn") if dfn.stem not in ["common", "flopy"]
        ]
        metafunc.parametrize("dfn_name", dfn_names, ids=dfn_names)


@requires_pkg("boltons")
def test_load_v1(dfn_name):
    with (
        (DFN_DIR / "common.dfn").open() as common_file,
        (DFN_DIR / f"{dfn_name}.dfn").open() as dfn_file,
    ):
        common = _load_common(common_file)
        dfn = load(dfn_file, name=dfn_name, format="dfn", common=common)
        assert any(dfn.fields) == (dfn.name not in EMPTY_DFNS)


@requires_pkg("boltons")
def test_load_all():
    dfns = load_flat(path=DFN_DIR)
    for dfn in dfns.values():
        assert any(dfn.fields) == (dfn.name not in EMPTY_DFNS)


def test_dfn_from_dict_ignores_extra_keys():
    d = {
        "schema_version": Version("2"),
        "name": "test-dfn",
        "extra_key": "should be allowed",
        "another_extra": 123,
    }
    dfn = Dfn.from_dict(d)
    assert dfn.name == "test-dfn"
    assert dfn.schema_version == Version("2")


def test_dfn_from_dict_strict_mode():
    d = {
        "schema_version": Version("2"),
        "name": "test-dfn",
        "extra_key": "should cause error",
    }
    with pytest.raises(ValueError, match="Unrecognized keys in DFN data"):
        Dfn.from_dict(d, strict=True)


def test_dfn_from_dict_strict_mode_nested():
    d = {
        "schema_version": Version("2"),
        "name": "test-dfn",
        "blocks": {
            "options": {
                "test_field": {
                    "name": "test_field",
                    "type": "keyword",
                    "extra_key": "should cause error",
                },
            },
        },
    }
    with pytest.raises(ValueError, match="Unrecognized keys in field data"):
        Dfn.from_dict(d, strict=True)


def test_dfn_from_dict_roundtrip():
    original = Dfn(
        schema_version=Version("2"),
        name="gwf-nam",
        parent="sim-nam",
        advanced=False,
        multi=True,
        blocks={"options": {}},
    )
    d = dataclasses.asdict(original)
    reconstructed = Dfn.from_dict(d)
    assert reconstructed.name == original.name
    assert reconstructed.schema_version == original.schema_version
    assert reconstructed.parent == original.parent
    assert reconstructed.advanced == original.advanced
    assert reconstructed.multi == original.multi
    assert reconstructed.blocks == original.blocks


def test_fieldv1_from_dict_ignores_extra_keys():
    d = {
        "name": "test_field",
        "type": "keyword",
        "extra_key": "should be allowed",
        "another_extra": 123,
    }
    f = FieldV1.from_dict(d)
    assert f.name == "test_field"
    assert f.type == "keyword"


def test_fieldv1_from_dict_strict_mode():
    d = {
        "name": "test_field",
        "type": "keyword",
        "extra_key": "should cause error",
    }
    with pytest.raises(ValueError, match="Unrecognized keys in field data"):
        FieldV1.from_dict(d, strict=True)


def test_fieldv1_from_dict_roundtrip():
    original = FieldV1(
        name="maxbound",
        type="integer",
        block="dimensions",
        description="maximum number of cells",
        tagged=True,
    )
    d = dataclasses.asdict(original)
    reconstructed = FieldV1.from_dict(d)
    assert reconstructed.name == original.name
    assert reconstructed.type == original.type
    assert reconstructed.block == original.block
    assert reconstructed.description == original.description
    assert reconstructed.tagged == original.tagged


def test_fieldv2_from_dict_ignores_extra_keys():
    d = {
        "name": "test_field",
        "type": "keyword",
        "extra_key": "should be allowed",
        "another_extra": 123,
    }
    f = FieldBase.from_dict(d)
    assert f.name == "test_field"
    assert f.type == "keyword"
    assert isinstance(f, Keyword)


def test_fieldv2_from_dict_strict_mode():
    d = {
        "name": "test_field",
        "type": "keyword",
        "extra_key": "should cause error",
    }
    with pytest.raises(ValueError, match="Unrecognized keys in field data"):
        FieldBase.from_dict(d, strict=True)


def test_fieldv2_from_dict_roundtrip():
    original = Integer(
        name="nper",
        description="number of stress periods",
        optional=False,
    )
    d = original.model_dump()
    reconstructed = FieldBase.from_dict(d)
    assert isinstance(reconstructed, Integer)
    assert reconstructed.name == original.name
    assert reconstructed.type == original.type
    assert reconstructed.description == original.description
    assert reconstructed.optional == original.optional


def test_dfn_from_dict_with_v1_field_dicts():
    d = {
        "schema_version": Version("1"),
        "name": "test-dfn",
        "blocks": {
            "options": {
                "save_flows": {
                    "name": "save_flows",
                    "type": "keyword",
                    "tagged": True,
                    "in_record": False,
                },
            },
        },
    }
    dfn = Dfn.from_dict(d)
    assert dfn.schema_version == Version("1")
    assert dfn.name == "test-dfn"
    assert dfn.blocks is not None
    assert "options" in dfn.blocks
    assert "save_flows" in dfn.blocks["options"]

    f = dfn.blocks["options"]["save_flows"]
    assert isinstance(f, FieldV1)
    assert f.name == "save_flows"
    assert f.type == "keyword"
    assert f.tagged is True
    assert f.in_record is False


def test_dfn_from_dict_with_v2_field_dicts():
    d = {
        "schema_version": Version("2"),
        "name": "test-dfn",
        "blocks": {
            "dimensions": {
                "nper": {
                    "name": "nper",
                    "type": "integer",
                    "optional": False,
                },
            },
        },
    }
    dfn = Dfn.from_dict(d)
    assert dfn.schema_version == Version("2")
    assert dfn.name == "test-dfn"
    assert dfn.blocks is not None
    assert "dimensions" in dfn.blocks
    assert "nper" in dfn.blocks["dimensions"]

    f = dfn.blocks["dimensions"]["nper"]
    assert isinstance(f, Integer)
    assert f.name == "nper"
    assert f.type == "integer"
    assert f.optional is False


def test_dfn_from_dict_defaults_to_v2_fields():
    d = {
        "name": "test-dfn",
        "blocks": {
            "options": {
                "some_field": {
                    "name": "some_field",
                    "type": "keyword",
                },
            },
        },
    }
    dfn = Dfn.from_dict(d)
    assert dfn.blocks is not None
    f = dfn.blocks["options"]["some_field"]
    assert isinstance(f, Keyword)
    assert isinstance(f, FieldBase)
    assert dfn.schema_version == Version("2")


def test_dfn_from_dict_with_already_deserialized_fields():
    kw = Keyword(name="test")
    d = {
        "schema_version": Version("2"),
        "name": "test-dfn",
        "blocks": {
            "options": {
                "test": kw,
            },
        },
    }
    dfn = Dfn.from_dict(d)
    assert dfn.blocks is not None
    assert dfn.blocks["options"]["test"] is kw


@requires_pkg("boltons")
def test_validate_directory():
    """Test validation on a directory of DFN files."""
    assert is_valid(DFN_DIR)


@requires_pkg("boltons")
def test_validate_single_file(dfn_name):
    """Test validation on a single DFN file."""
    if dfn_name == "common":
        pytest.skip("common.dfn is handled separately")
    assert is_valid(DFN_DIR / f"{dfn_name}.dfn")


@requires_pkg("boltons")
def test_validate_common_file():
    """Test validation on common.dfn."""
    assert is_valid(DFN_DIR / "common.dfn")


@requires_pkg("boltons")
def test_validate_invalid_file(function_tmpdir):
    """Test validation on an invalid DFN file."""
    invalid_dfn = function_tmpdir / "invalid.dfn"
    invalid_dfn.write_text("invalid content")
    assert not is_valid(invalid_dfn)


@requires_pkg("boltons")
def test_validate_nonexistent_file(function_tmpdir):
    """Test validation on a nonexistent file."""
    nonexistent = function_tmpdir / "nonexistent.dfn"
    assert not is_valid(nonexistent)


def test_fieldv1_to_fieldv2_conversion():
    """Test that FieldV1 instances are properly converted to typed v2 Component fields."""
    dfn_v1 = Dfn(
        schema_version=Version("1"),
        name="test-dfn",
        blocks={
            "options": {
                "save_flows": FieldV1(
                    name="save_flows",
                    type="keyword",
                    block="options",
                    description="save calculated flows",
                    tagged=True,
                    in_record=False,
                    reader="urword",
                ),
                "some_float": FieldV1(
                    name="some_float",
                    type="double precision",
                    block="options",
                    description="a floating point value",
                ),
            }
        },
    )

    component = map_v2(dfn_v1, schema_version="2")
    assert component.schema_version == Version("2")
    assert component.blocks is not None
    assert "options" in component.blocks

    options = component.blocks["options"].fields
    assert "save_flows" in options

    save_flows = options["save_flows"]
    assert isinstance(save_flows, Keyword)
    assert isinstance(save_flows, FieldBase)
    assert save_flows.name == "save_flows"
    assert save_flows.type == "keyword"
    assert save_flows.description == "save calculated flows"
    assert not hasattr(save_flows, "in_record")
    assert not hasattr(save_flows, "reader")

    some_float = options["some_float"]
    assert isinstance(some_float, Double)
    assert some_float.name == "some_float"
    assert some_float.type == "double"
    assert some_float.description == "a floating point value"


def test_fieldv1_to_fieldv2_conversion_with_children():
    """Test that FieldV1 with nested children are properly converted to typed v2 instances."""
    dfn_v1 = Dfn(
        schema_version=Version("1"),
        name="test-dfn",
        blocks={
            "period": {
                "stress_period_data": FieldV1(
                    name="stress_period_data",
                    type="recarray cellid",
                    block="period",
                    description="stress period data",
                    in_record=False,
                ),
                "cellid": FieldV1(
                    name="cellid",
                    type="integer",
                    block="period",
                    description="cell identifier",
                    in_record=True,
                    tagged=False,
                ),
            }
        },
    )

    component = map_v2(dfn_v1, schema_version="2")
    assert component.blocks is not None
    for block in component.blocks.values():
        for f in block.fields.values():
            assert isinstance(f, FieldBase)
            if f.children:
                for child in f.children.values():
                    assert isinstance(child, FieldBase)


def test_period_block_conversion():
    """Test period block recarray conversion to individual arrays."""
    dfn_v1 = Dfn(
        schema_version=Version("1"),
        name="test-pkg",
        blocks={
            "period": {
                "stress_period_data": FieldV1(
                    name="stress_period_data",
                    type="recarray cellid q",
                    block="period",
                    description="stress period data",
                ),
                "cellid": FieldV1(
                    name="cellid",
                    type="integer",
                    block="period",
                    shape="(ncelldim)",
                    in_record=True,
                ),
                "q": FieldV1(
                    name="q",
                    type="double precision",
                    block="period",
                    shape="(maxbound)",
                    in_record=True,
                ),
            }
        },
    )

    component = map_v2(dfn_v1, schema_version="2")

    period_fields = component.blocks["period"].fields
    assert "cellid" not in period_fields
    assert "q" in period_fields
    q = period_fields["q"]
    assert isinstance(q, Array)
    assert "nper" in q.shape
    assert "nodes" in q.shape
    assert "maxbound" not in q.shape


def test_record_type_conversion():
    """Test record type with multiple scalar fields."""
    dfn_v1 = Dfn(
        schema_version=Version("1"),
        name="test-dfn",
        blocks={
            "options": {
                "auxrecord": FieldV1(
                    name="auxrecord",
                    type="record auxiliary auxname",
                    block="options",
                    in_record=False,
                ),
                "auxiliary": FieldV1(
                    name="auxiliary",
                    type="keyword",
                    block="options",
                    in_record=True,
                ),
                "auxname": FieldV1(
                    name="auxname",
                    type="string",
                    block="options",
                    in_record=True,
                ),
            }
        },
    )

    component = map_v2(dfn_v1, schema_version="2")

    auxrecord = component.blocks["options"].fields["auxrecord"]
    assert isinstance(auxrecord, Record)
    assert auxrecord.type == "record"
    assert auxrecord.children is not None
    assert "auxiliary" in auxrecord.children
    assert "auxname" in auxrecord.children
    assert isinstance(auxrecord.children["auxiliary"], Keyword)
    assert isinstance(auxrecord.children["auxname"], String)


def test_keystring_type_conversion():
    """Test keystring (union) type conversion."""
    dfn_v1 = Dfn(
        schema_version=Version("1"),
        name="test-dfn",
        blocks={
            "options": {
                "obs_filerecord": FieldV1(
                    name="obs_filerecord",
                    type="record obs6 filein obs6_filename",
                    block="options",
                    tagged=True,
                ),
                "obs6": FieldV1(
                    name="obs6",
                    type="keyword",
                    block="options",
                    in_record=True,
                ),
                "filein": FieldV1(
                    name="filein",
                    type="keyword",
                    block="options",
                    in_record=True,
                ),
                "obs6_filename": FieldV1(
                    name="obs6_filename",
                    type="string",
                    block="options",
                    in_record=True,
                    preserve_case=True,
                ),
            }
        },
    )

    component = map_v2(dfn_v1, schema_version="2")

    obs_rec = component.blocks["options"].fields["obs_filerecord"]
    assert isinstance(obs_rec, Record)
    assert obs_rec.type == "record"
    assert obs_rec.children is not None
    assert all(isinstance(child, FieldBase) for child in obs_rec.children.values())


# =============================================================================
# Group 1: MapV1To1_1
# =============================================================================


def test_mapv1to1_1_field_stripping():
    """map(dfn, '1.1') strips v1-specific attrs; shared base attrs are preserved."""
    dfn_v1 = Dfn(
        schema_version=Version("1"),
        name="test-dfn",
        blocks={
            "options": {
                "save_flows": FieldV1(
                    name="save_flows",
                    type="keyword",
                    block="options",
                    description="save calculated flows",
                    tagged=True,
                    in_record=False,
                    reader="urword",
                ),
            }
        },
    )

    dfn_v1_1 = map_v1_1(dfn_v1, "1.1")
    assert dfn_v1_1.schema_version == Version("1.1")
    assert dfn_v1_1.blocks is not None

    f = dfn_v1_1.blocks["options"]["save_flows"]
    assert isinstance(f, FieldV1_1)
    assert not isinstance(f, FieldV1)
    assert f.name == "save_flows"
    assert f.type == "keyword"
    assert f.description == "save calculated flows"
    assert f.tagged is True
    assert not hasattr(f, "in_record")
    assert not hasattr(f, "reader")


def test_mapv1to1_1_preserves_dfn_metadata():
    """map(dfn, '1.1') preserves DFN-level metadata (name, parent, advanced, multi)."""
    dfn_v1 = Dfn(
        schema_version=Version("1"),
        name="gwf-chd",
        parent="gwf-nam",
        advanced=False,
        multi=True,
        blocks={},
    )

    dfn_v1_1 = map_v1_1(dfn_v1, "1.1")
    assert dfn_v1_1.name == "gwf-chd"
    assert dfn_v1_1.parent == "gwf-nam"
    assert dfn_v1_1.advanced is False
    assert dfn_v1_1.multi is True


def test_block_sort_key_order():
    """block_sort_key orders blocks in canonical MF6 order."""
    from modflow_devtools.dfn.v1_1 import block_sort_key

    items = [
        ("period", {}),
        ("options", {}),
        ("packagedata", {}),
        ("dimensions", {}),
        ("custom_block", {}),
    ]
    sorted_items = sorted(items, key=block_sort_key)
    assert [k for k, _ in sorted_items] == [
        "options",
        "dimensions",
        "packagedata",
        "period",
        "custom_block",
    ]


# =============================================================================
# Group 2: map() dispatch edge cases
# =============================================================================


def test_map_dispatch_to_v1_raises():
    """map(dfn, '1') raises NotImplementedError."""
    dfn = Dfn(schema_version=Version("1"), name="test-dfn")
    with pytest.raises(NotImplementedError):
        map_v1_1(dfn, "1")


def test_map_dispatch_unsupported_version_raises():
    """map(dfn, unsupported version) raises ValueError."""
    dfn = Dfn(schema_version=Version("1"), name="test-dfn")
    with pytest.raises(ValueError):
        map_v1_1(dfn, "3")


def test_map_dispatch_already_v1_1_returns_same():
    """map(dfn, '1.1') when dfn is already v1.1 returns the same Dfn unchanged."""
    dfn = Dfn(schema_version=Version("1.1"), name="test-dfn")
    result = map_v1_1(dfn, "1.1")
    assert result is dfn


# =============================================================================
# Group 3: to_tree / to_flat / _apply_parent_inference
# =============================================================================


def test_apply_parent_inference():
    """_apply_parent_inference infers parents from component names."""
    dfns = {
        "sim-nam": Dfn(schema_version=Version("1.1"), name="sim-nam"),
        "gwf-nam": Dfn(schema_version=Version("1.1"), name="gwf-nam"),
        "gwf-dis": Dfn(schema_version=Version("1.1"), name="gwf-dis"),
    }
    inferred = _apply_parent_inference(dfns)
    assert inferred["sim-nam"].parent is None
    assert inferred["gwf-nam"].parent == "sim-nam"
    assert inferred["gwf-dis"].parent == "gwf-nam"


def test_apply_parent_inference_does_not_overwrite_explicit():
    """_apply_parent_inference does not overwrite an already-set parent."""
    dfns = {
        "gwf-dis": Dfn(
            schema_version=Version("1.1"), name="gwf-dis", parent="custom-parent"
        ),
    }
    inferred = _apply_parent_inference(dfns)
    assert inferred["gwf-dis"].parent == "custom-parent"


def test_to_tree_builds_hierarchy():
    """to_tree() builds children hierarchy from a flat Dfns dict."""
    dfns = {
        "sim-nam": Dfn(schema_version=Version("1.1"), name="sim-nam"),
        "gwf-nam": Dfn(schema_version=Version("1.1"), name="gwf-nam", parent="sim-nam"),
        "gwf-dis": Dfn(schema_version=Version("1.1"), name="gwf-dis", parent="gwf-nam"),
    }
    root = to_tree(dfns)
    assert root.name == "sim-nam"
    assert root.children is not None
    assert "gwf-nam" in root.children
    gwf_nam = root.children["gwf-nam"]
    assert gwf_nam.children is not None
    assert "gwf-dis" in gwf_nam.children


def test_to_flat_strips_children():
    """to_flat() recovers the flat spec; no node has children set."""
    dfns = {
        "sim-nam": Dfn(schema_version=Version("1.1"), name="sim-nam"),
        "gwf-nam": Dfn(schema_version=Version("1.1"), name="gwf-nam", parent="sim-nam"),
        "gwf-dis": Dfn(schema_version=Version("1.1"), name="gwf-dis", parent="gwf-nam"),
    }
    root = to_tree(dfns)
    flat = to_flat(root)
    assert set(flat.keys()) == {"sim-nam", "gwf-nam", "gwf-dis"}
    for dfn in flat.values():
        assert dfn.children is None


def test_to_tree_raises_without_unique_root():
    """to_tree() raises ValueError when there is no single root component."""
    dfns = {
        "gwf-nam": Dfn(schema_version=Version("1.1"), name="gwf-nam", parent="sim-nam"),
        "gwf-dis": Dfn(schema_version=Version("1.1"), name="gwf-dis", parent="gwf-nam"),
    }
    with pytest.raises(ValueError, match="root"):
        to_tree(dfns)


def test_to_tree_raises_for_v1_schema():
    """to_tree() raises NotImplementedError for v1 schema."""
    dfns = {
        "sim-nam": Dfn(schema_version=Version("1"), name="sim-nam"),
    }
    with pytest.raises(NotImplementedError):
        to_tree(dfns)


# =============================================================================
# Group 4: to_component() branches
# =============================================================================


def test_to_component_simulation():
    """sim-nam maps to Simulation."""
    from modflow_devtools.dfns.schema.v2 import Simulation

    dfn = Dfn(schema_version=Version("2"), name="sim-nam")
    result = map_v2(dfn, "2")
    assert isinstance(result, Simulation)


def test_to_component_model():
    """*-nam (non-sim) maps to Model."""
    from modflow_devtools.dfns.schema.v2 import Model

    dfn = Dfn(schema_version=Version("2"), name="gwf-nam")
    result = map_v2(dfn, "2")
    assert isinstance(result, Model)


def test_to_component_solution_package():
    """sln-* maps to Package(subtype='solution')."""
    from modflow_devtools.dfns.schema.v2 import Package

    dfn = Dfn(schema_version=Version("2"), name="sln-ims")
    result = map_v2(dfn, "2")
    assert isinstance(result, Package)
    assert result.subtype == "solution"


def test_to_component_exchange_package():
    """exg-* maps to Package(subtype='exchange')."""
    from modflow_devtools.dfns.schema.v2 import Package

    dfn = Dfn(schema_version=Version("2"), name="exg-gwfgwf")
    result = map_v2(dfn, "2")
    assert isinstance(result, Package)
    assert result.subtype == "exchange"


def test_to_component_utility_package():
    """utl-* maps to Package(subtype='utility')."""
    from modflow_devtools.dfns.schema.v2 import Package

    dfn = Dfn(schema_version=Version("2"), name="utl-obs")
    result = map_v2(dfn, "2")
    assert isinstance(result, Package)
    assert result.subtype == "utility"


def test_to_component_advanced_package():
    """advanced=True maps to Package(subtype='advanced')."""
    from modflow_devtools.dfns.schema.v2 import Package

    dfn = Dfn(schema_version=Version("2"), name="gwf-sfr", advanced=True)
    result = map_v2(dfn, "2")
    assert isinstance(result, Package)
    assert result.subtype == "advanced"


def test_to_component_variant_of_g():
    """Names ending in 'g' infer variant_of to the name without the suffix."""
    from modflow_devtools.dfns.schema.v2 import Package

    dfn = Dfn(schema_version=Version("2"), name="gwf-welg")
    result = map_v2(dfn, "2")
    assert isinstance(result, Package)
    assert result.variant_of == "gwf-wel"


def test_to_component_variant_of_a():
    """Names ending in 'a' infer variant_of to the name without the suffix."""
    from modflow_devtools.dfns.schema.v2 import Package

    dfn = Dfn(schema_version=Version("2"), name="gwf-rcha")
    result = map_v2(dfn, "2")
    assert isinstance(result, Package)
    assert result.variant_of == "gwf-rch"


# =============================================================================
# Group 5: MapV1To2.map() fast-path
# =============================================================================


def test_mapv1to2_fastpath_skips_map_blocks():
    """map(dfn, '2') with schema_version=2 takes the fast path (no map_blocks call).

    If map_blocks were called, it would fail: FieldBase has no ``in_record`` attr,
    and asdict() on a Pydantic model raises TypeError.
    """
    dfn = Dfn(
        schema_version=Version("2"),
        name="gwf-chd",
        blocks={
            "options": {
                "save_flows": Keyword(name="save_flows", description="save flows"),
            }
        },
    )
    result = map_v2(dfn, "2")
    assert result.name == "gwf-chd"
    assert result.blocks is not None
    assert "save_flows" in result.blocks["options"].fields


# =============================================================================
# Group 6: _dfn_to_plain_dict / _toml_safe
# =============================================================================


def test_dfn_to_plain_dict_version_coerced_and_none_excluded():
    """Version is coerced to str; None fields are excluded from output."""
    dfn = Dfn(
        schema_version=Version("1.1"),
        name="test-dfn",
        parent=None,
        blocks=None,
    )
    d = _dfn_to_plain_dict(dfn)
    assert d["schema_version"] == "1.1"
    assert d["name"] == "test-dfn"
    assert "parent" not in d
    assert "blocks" not in d


def test_dfn_to_plain_dict_with_fieldbase_blocks():
    """FieldBase blocks are serialized via model_dump."""
    dfn = Dfn(
        schema_version=Version("2"),
        name="test-dfn",
        blocks={
            "options": {
                "nper": Integer(name="nper", description="number of periods"),
            }
        },
    )
    d = _dfn_to_plain_dict(dfn)
    block = d["blocks"]["options"]
    assert "nper" in block
    assert block["nper"]["type"] == "integer"
    assert block["nper"]["name"] == "nper"


def test_dfn_to_plain_dict_with_fieldv1_blocks():
    """FieldV1 blocks are serialized via dataclasses.asdict."""
    dfn = Dfn(
        schema_version=Version("1"),
        name="test-dfn",
        blocks={
            "options": {
                "save_flows": FieldV1(name="save_flows", type="keyword", block="options"),
            }
        },
    )
    d = _dfn_to_plain_dict(dfn)
    block = d["blocks"]["options"]
    assert "save_flows" in block
    assert block["save_flows"]["name"] == "save_flows"
    assert block["save_flows"]["type"] == "keyword"


def test_toml_safe_primitives_pass_through():
    """_toml_safe passes primitive types through unchanged."""
    assert _toml_safe("hello") == "hello"
    assert _toml_safe(42) == 42
    assert _toml_safe(3.14) == 3.14
    assert _toml_safe(True) is True
    assert _toml_safe(None) is None


def test_toml_safe_non_primitive_coerced_to_str():
    """_toml_safe coerces non-TOML-native types (e.g. Version) to str."""
    assert _toml_safe(Version("1.1")) == "1.1"


def test_toml_safe_fieldbase_via_model_dump():
    """_toml_safe converts FieldBase instances via model_dump recursively."""
    kw = Keyword(name="save_flows", description="save flows")
    result = _toml_safe(kw)
    assert isinstance(result, dict)
    assert result["name"] == "save_flows"
    assert result["type"] == "keyword"


def test_toml_safe_nested():
    """_toml_safe recurses into dicts and lists."""
    obj = {"a": [Version("2"), "plain"], "b": {"c": 99}}
    result = _toml_safe(obj)
    assert result["a"][0] == "2"
    assert result["a"][1] == "plain"
    assert result["b"]["c"] == 99
