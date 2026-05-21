from modflow_devtools.dfn.mapper import map as map_v1_1
from modflow_devtools.dfn.mapper import map_field
from modflow_devtools.dfn.schema import Dfn, Field


def _field(**kwargs) -> Field:
    """Build a complete v1 Field dict for testing."""
    base: dict = {
        "name": "test_field",
        "type": "keyword",
        "block": "options",
        "default": None,
        "longname": None,
        "description": None,
        "optional": False,
        "developmode": False,
        "shape": None,
        "valid": None,
        "netcdf": False,
        "tagged": False,
    }
    base.update(kwargs)
    return Field(**base)


def _dfn(**kwargs) -> Dfn:
    """Build a minimal v1 Dfn dict for testing."""
    base: dict = {
        "schema_version": "1",
        "name": "test-dfn",
        "parent": None,
        "blocks": None,
        "advanced": False,
        "multi": False,
    }
    base.update(kwargs)
    return Dfn(**base)


def test_map_field_preserves_base_attrs():
    field = _field(
        name="save_flows",
        type="keyword",
        description="save calculated flows",
        optional=True,
        tagged=True,
        longname="save flows flag",
    )
    result = map_field(field)
    assert result["name"] == "save_flows"
    assert result["type"] == "keyword"
    assert result["description"] == "save calculated flows"
    assert result["optional"] is True
    assert result["tagged"] is True
    assert result["longname"] == "save flows flag"


def test_map_field_strips_v1_specific_attrs():
    field = _field(in_record=True, reader="urword")
    result = map_field(field)
    assert "in_record" not in result
    assert "reader" not in result


def test_map_sets_schema_version():
    dfn = _dfn()
    result = map_v1_1(dfn)
    assert result["schema_version"] == "1.1"


def test_map_preserves_metadata():
    dfn = _dfn(name="gwf-chd", parent="gwf-nam")
    result = map_v1_1(dfn)
    assert result["name"] == "gwf-chd"
    assert result["schema_version"] == "1.1"


def test_map_empty_blocks():
    dfn = _dfn(blocks=None)
    result = map_v1_1(dfn)
    assert result["blocks"] is None


def test_map_maps_block_fields():
    field = _field(name="maxbound", type="integer", block="dimensions")
    dfn = _dfn(blocks={"dimensions": {"maxbound": field}})
    result = map_v1_1(dfn)
    assert result["blocks"] is not None
    assert "maxbound" in result["blocks"]["dimensions"]
    assert result["blocks"]["dimensions"]["maxbound"]["name"] == "maxbound"
    assert "in_record" not in result["blocks"]["dimensions"]["maxbound"]
