from pathlib import Path

import pytest
from packaging.version import Version

from modflow_devtools.dfns import Dfn, _load_common, load, load_flat
from modflow_devtools.dfns.dfn2toml import convert, is_valid
from modflow_devtools.dfns.fetch import fetch_dfns
from modflow_devtools.dfns.schema.v1 import FieldV1
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
TOML_DIR = DFN_DIR / "toml"
SPEC_DIRS = {1: DFN_DIR, 2: TOML_DIR}
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
        dfn_paths = [p for p in DFN_DIR.glob("*.dfn") if p.stem not in ["common", "flopy"]]
        if not TOML_DIR.exists() or not all(
            (TOML_DIR / f"{dfn.stem}.toml").is_file() for dfn in dfn_paths
        ):
            convert(DFN_DIR, TOML_DIR)
        assert all((TOML_DIR / f"{dfn.stem}.toml").is_file() for dfn in dfn_paths)
        toml_names = [toml.stem for toml in TOML_DIR.glob("*.toml")]
        metafunc.parametrize("toml_name", toml_names, ids=toml_names)


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
def test_load_v2(toml_name):
    with (TOML_DIR / f"{toml_name}.toml").open(mode="rb") as toml_file:
        dfn = load(toml_file, name=toml_name, format="toml")
        assert any(dfn.fields) == (dfn.name not in EMPTY_DFNS)


@requires_pkg("boltons")
@pytest.mark.parametrize("schema_version", list(SPEC_DIRS.keys()))
def test_load_all(schema_version):
    dfns = load_flat(path=SPEC_DIRS[schema_version])
    for dfn in dfns.values():
        assert any(dfn.fields) == (dfn.name not in EMPTY_DFNS)


@requires_pkg("boltons", "tomli")
def test_convert(function_tmpdir):
    import tomli

    convert(DFN_DIR, function_tmpdir)

    assert (function_tmpdir / "sim-nam.toml").exists()
    assert (function_tmpdir / "gwf-nam.toml").exists()

    with (function_tmpdir / "sim-nam.toml").open("rb") as f:
        sim_data = tomli.load(f)
    assert sim_data["name"] == "sim-nam"
    assert sim_data["schema_version"] == "2"
    assert "parent" not in sim_data

    with (function_tmpdir / "gwf-nam.toml").open("rb") as f:
        gwf_data = tomli.load(f)
    assert gwf_data["name"] == "gwf-nam"
    assert gwf_data["parent"] == "sim-nam"
    assert gwf_data["schema_version"] == "2"

    _COMPONENT_TYPES = {"simulation", "model", "package"}
    dfns = load_flat(function_tmpdir)
    roots = []
    for dfn in dfns.values():
        parent = dfn.parent
        if parent:
            if isinstance(parent, list):
                assert all(t in _COMPONENT_TYPES for t in parent)
            else:
                assert parent in dfns or parent in _COMPONENT_TYPES
        else:
            roots.append(dfn.name)
    assert len(roots) == 1
    root = dfns[roots[0]]
    assert root.name == "sim-nam"

    models = root.children or {}
    for mdl in models:
        assert models[mdl].name == mdl
        assert models[mdl].parent == "sim-nam"

    if gwf := models.get("gwf-nam", None):
        pkgs = gwf.children or {}
        pkgs = {k: v for k, v in pkgs.items() if k.startswith("gwf-")}
        assert len(pkgs) > 0
        if dis := pkgs.get("gwf-dis", None):
            assert dis.name == "gwf-dis"
            assert dis.parent == "gwf-nam"
            assert "options" in (dis.blocks or {})
            assert "dimensions" in (dis.blocks or {})


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
    d = original.model_dump()
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
    from dataclasses import asdict

    original = FieldV1(
        name="maxbound",
        type="integer",
        block="dimensions",
        description="maximum number of cells",
        tagged=True,
    )
    d = asdict(original)
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
    """Test that FieldV1 instances are properly converted to typed v2 instances."""
    from modflow_devtools.dfns import map

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

    dfn_v2 = map(dfn_v1, schema_version="2")
    assert dfn_v2.schema_version == Version("2")
    assert dfn_v2.blocks is not None
    assert "options" in dfn_v2.blocks
    assert "save_flows" in dfn_v2.blocks["options"]

    save_flows = dfn_v2.blocks["options"]["save_flows"]
    assert isinstance(save_flows, Keyword)
    assert isinstance(save_flows, FieldBase)
    assert save_flows.name == "save_flows"
    assert save_flows.type == "keyword"
    assert save_flows.description == "save calculated flows"
    assert not hasattr(save_flows, "in_record")
    assert not hasattr(save_flows, "reader")

    some_float = dfn_v2.blocks["options"]["some_float"]
    assert isinstance(some_float, Double)
    assert some_float.name == "some_float"
    assert some_float.type == "double"
    assert some_float.description == "a floating point value"


def test_fieldv1_to_fieldv2_conversion_with_children():
    """Test that FieldV1 with nested children are properly converted to typed v2 instances."""
    from modflow_devtools.dfns import map

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

    dfn_v2 = map(dfn_v1, schema_version="2")
    assert dfn_v2.blocks is not None
    for block_fields in dfn_v2.blocks.values():
        for f in block_fields.values():
            assert isinstance(f, FieldBase)
            if f.children:
                for child in f.children.values():
                    assert isinstance(child, FieldBase)


def test_period_block_conversion():
    """Test period block recarray conversion to individual arrays."""
    from modflow_devtools.dfns import map

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

    dfn_v2 = map(dfn_v1, schema_version="2")

    period_block = dfn_v2.blocks["period"]
    assert "cellid" not in period_block
    assert "q" in period_block
    q = period_block["q"]
    assert isinstance(q, Array)
    assert "nper" in q.shape
    assert "nodes" in q.shape
    assert "maxbound" not in q.shape


def test_record_type_conversion():
    """Test record type with multiple scalar fields."""
    from modflow_devtools.dfns import map

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

    dfn_v2 = map(dfn_v1, schema_version="2")

    auxrecord = dfn_v2.blocks["options"]["auxrecord"]
    assert isinstance(auxrecord, Record)
    assert auxrecord.type == "record"
    assert auxrecord.children is not None
    assert "auxiliary" in auxrecord.children
    assert "auxname" in auxrecord.children
    assert isinstance(auxrecord.children["auxiliary"], Keyword)
    assert isinstance(auxrecord.children["auxname"], String)


def test_keystring_type_conversion():
    """Test keystring (union) type conversion."""
    from modflow_devtools.dfns import map

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

    dfn_v2 = map(dfn_v1, schema_version="2")

    obs_rec = dfn_v2.blocks["options"]["obs_filerecord"]
    assert isinstance(obs_rec, Record)
    assert obs_rec.type == "record"
    assert obs_rec.children is not None
    assert all(isinstance(child, FieldBase) for child in obs_rec.children.values())
