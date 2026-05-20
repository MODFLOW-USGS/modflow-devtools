import dataclasses
from pathlib import Path

import pytest
from packaging.version import Version

from modflow_devtools.dfn import Dfn, fetch_dfns
from modflow_devtools.dfn.mapper import map as map_v1_1
from modflow_devtools.dfn2toml import convert
from modflow_devtools.markers import requires_pkg

PROJ_ROOT = Path(__file__).parents[1]
DFN_DIR = PROJ_ROOT / "autotest" / "temp" / "dfn"
TOML_V1_DIR = DFN_DIR / "toml"
TOML_V1_1_DIR = DFN_DIR / "toml-v1_1"
VERSIONS = {1: DFN_DIR, 2: TOML_V1_DIR}
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

    if "toml_name" in metafunc.fixturenames:
        # Only convert if TOML files don't exist yet (avoid repeated conversions)
        dfn_paths = [p for p in DFN_DIR.glob("*.dfn") if p.stem not in ["common", "flopy"]]
        if not TOML_V1_DIR.exists() or not all(
            (TOML_V1_DIR / f"{dfn.stem}.toml").is_file() for dfn in dfn_paths
        ):
            convert(DFN_DIR, TOML_V1_DIR)
        # Verify all expected TOML files were created
        assert all((TOML_V1_DIR / f"{dfn.stem}.toml").is_file() for dfn in dfn_paths)
        toml_names = [toml.stem for toml in TOML_V1_DIR.glob("*.toml")]
        metafunc.parametrize("toml_name", toml_names, ids=toml_names)

    if "toml_v1_1_name" in metafunc.fixturenames:
        dfn_paths = [p for p in DFN_DIR.glob("*.dfn") if p.stem not in ["common", "flopy"]]
        if not TOML_V1_1_DIR.exists() or not all(
            (TOML_V1_1_DIR / f"{dfn.stem}.toml").is_file() for dfn in dfn_paths
        ):
            convert(DFN_DIR, TOML_V1_1_DIR, schema_version="1.1")
        assert all((TOML_V1_1_DIR / f"{dfn.stem}.toml").is_file() for dfn in dfn_paths)
        toml_names = [toml.stem for toml in TOML_V1_1_DIR.glob("*.toml")]
        metafunc.parametrize("toml_v1_1_name", toml_names, ids=toml_names)

    if "toml_v2_name" in metafunc.fixturenames:
        dfn_paths = [p for p in DFN_DIR.glob("*.dfn") if p.stem not in ["common", "flopy"]]
        if not TOML_V2_DIR.exists() or not all(
            (TOML_V2_DIR / f"{dfn.stem}.toml").is_file() for dfn in dfn_paths
        ):
            convert(DFN_DIR, TOML_V2_DIR, schema_version="2")
        assert all((TOML_V2_DIR / f"{dfn.stem}.toml").is_file() for dfn in dfn_paths)
        toml_names = [toml.stem for toml in TOML_V2_DIR.glob("*.toml")]
        metafunc.parametrize("toml_v2_name", toml_names, ids=toml_names)


# =============================================================================
# dfn.v1.Dfn — high-level load
# =============================================================================


@requires_pkg("boltons")
def test_load_v1(dfn_name):
    with (
        (DFN_DIR / "common.dfn").open() as common_file,
        (DFN_DIR / f"{dfn_name}.dfn").open() as dfn_file,
    ):
        common, _ = Dfn._load_v1_flat(common_file)
        dfn = Dfn.load(dfn_file, name=dfn_name, common=common)
        assert any(dfn)


@requires_pkg("boltons")
def test_load_v2(toml_name):
    with (TOML_V1_DIR / f"{toml_name}.toml").open(mode="rb") as toml_file:
        toml = Dfn.load(toml_file, name=toml_name, version=2)
        assert any(toml)


@requires_pkg("boltons")
@pytest.mark.parametrize("version", list(VERSIONS.keys()))
def test_load_all(version):
    dfns = Dfn.load_all(VERSIONS[version], version=version)
    assert any(dfns)


@requires_pkg("boltons")
def test_convert_v1_1(toml_v1_1_name):
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    with (TOML_V1_1_DIR / f"{toml_v1_1_name}.toml").open("rb") as f:
        data = tomllib.load(f)
    assert data["name"] == toml_v1_1_name
    assert data["schema_version"] == "1.1"


# =============================================================================
# DfnSpec (dfn.v1_1.Dfn) — from_dict
# =============================================================================


def test_dfn_from_dict_ignores_extra_keys():
    d = {
        "schema_version": Version("2"),
        "name": "test-dfn",
        "extra_key": "should be allowed",
        "another_extra": 123,
    }
    dfn = DfnSpec.from_dict(d)
    assert dfn.name == "test-dfn"
    assert dfn.schema_version == Version("2")


def test_dfn_from_dict_strict_mode():
    d = {
        "schema_version": Version("2"),
        "name": "test-dfn",
        "extra_key": "should cause error",
    }
    with pytest.raises(ValueError, match="Unrecognized keys in DFN data"):
        DfnSpec.from_dict(d, strict=True)


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
        DfnSpec.from_dict(d, strict=True)


def test_dfn_from_dict_roundtrip():
    original = DfnSpec(
        schema_version=Version("2"),
        name="gwf-nam",
        parent="sim-nam",
        advanced=False,
        multi=True,
        blocks={"options": {}},
    )
    d = dataclasses.asdict(original)
    reconstructed = DfnSpec.from_dict(d)
    assert reconstructed.name == original.name
    assert reconstructed.schema_version == original.schema_version
    assert reconstructed.parent == original.parent
    assert reconstructed.advanced == original.advanced
    assert reconstructed.multi == original.multi
    assert reconstructed.blocks == original.blocks


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
    dfn = DfnSpec.from_dict(d)
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
    dfn = DfnSpec.from_dict(d)
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
    dfn = DfnSpec.from_dict(d)
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
    dfn = DfnSpec.from_dict(d)
    assert dfn.blocks is not None
    assert dfn.blocks["options"]["test"] is kw


# =============================================================================
# FieldV1 — from_dict
# =============================================================================


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


# =============================================================================
# map() v1 → v1.1
# =============================================================================


def test_mapv1to1_1_field_stripping():
    """map(dfn, '1.1') strips v1-specific attrs; shared base attrs are preserved."""
    dfn_v1 = DfnSpec(
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
    dfn_v1 = DfnSpec(
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


# =============================================================================
# map() dispatch edge cases
# =============================================================================


def test_map_dispatch_to_v1_raises():
    """map(dfn, '1') raises NotImplementedError."""
    dfn = DfnSpec(schema_version=Version("1"), name="test-dfn")
    with pytest.raises(NotImplementedError):
        map_v1_1(dfn, "1")


def test_map_dispatch_unsupported_version_raises():
    """map(dfn, unsupported version) raises ValueError."""
    dfn = DfnSpec(schema_version=Version("1"), name="test-dfn")
    with pytest.raises(ValueError):
        map_v1_1(dfn, "3")


def test_map_dispatch_already_v1_1_returns_same():
    """map(dfn, '1.1') when dfn is already v1.1 returns the same Dfn unchanged."""
    dfn = DfnSpec(schema_version=Version("1.1"), name="test-dfn")
    result = map_v1_1(dfn, "1.1")
    assert result is dfn


# =============================================================================
# to_tree / to_flat / _apply_parent_inference
# =============================================================================


def test_apply_parent_inference():
    """_apply_parent_inference infers parents from component names."""
    dfns = {
        "sim-nam": DfnSpec(schema_version=Version("1.1"), name="sim-nam"),
        "gwf-nam": DfnSpec(schema_version=Version("1.1"), name="gwf-nam"),
        "gwf-dis": DfnSpec(schema_version=Version("1.1"), name="gwf-dis"),
    }
    inferred = _infer_parents(dfns)
    assert inferred["sim-nam"].parent is None
    assert inferred["gwf-nam"].parent == "sim-nam"
    assert inferred["gwf-dis"].parent == "gwf-nam"


def test_apply_parent_inference_does_not_overwrite_explicit():
    """_apply_parent_inference does not overwrite an already-set parent."""
    dfns = {
        "gwf-dis": DfnSpec(schema_version=Version("1.1"), name="gwf-dis", parent="custom-parent"),
    }
    inferred = _infer_parents(dfns)
    assert inferred["gwf-dis"].parent == "custom-parent"


def test_to_tree_builds_hierarchy():
    """to_tree() builds children hierarchy from a flat Dfns dict."""
    dfns = {
        "sim-nam": DfnSpec(schema_version=Version("1.1"), name="sim-nam"),
        "gwf-nam": DfnSpec(schema_version=Version("1.1"), name="gwf-nam", parent="sim-nam"),
        "gwf-dis": DfnSpec(schema_version=Version("1.1"), name="gwf-dis", parent="gwf-nam"),
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
        "sim-nam": DfnSpec(schema_version=Version("1.1"), name="sim-nam"),
        "gwf-nam": DfnSpec(schema_version=Version("1.1"), name="gwf-nam", parent="sim-nam"),
        "gwf-dis": DfnSpec(schema_version=Version("1.1"), name="gwf-dis", parent="gwf-nam"),
    }
    root = to_tree(dfns)
    flat = to_flat(root)
    assert set(flat.keys()) == {"sim-nam", "gwf-nam", "gwf-dis"}
    for dfn in flat.values():
        assert dfn.children is None


def test_to_tree_raises_without_unique_root():
    """to_tree() raises ValueError when there is no root component."""
    dfns = {
        "gwf-nam": DfnSpec(schema_version=Version("1.1"), name="gwf-nam", parent="sim-nam"),
        "gwf-dis": DfnSpec(schema_version=Version("1.1"), name="gwf-dis", parent="gwf-nam"),
    }
    with pytest.raises(ValueError, match="root"):
        to_tree(dfns)


def test_to_tree_raises_for_v1_schema():
    """to_tree() raises NotImplementedError for v1 schema."""
    dfns = {
        "sim-nam": DfnSpec(schema_version=Version("1"), name="sim-nam"),
    }
    with pytest.raises(NotImplementedError):
        to_tree(dfns)


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
