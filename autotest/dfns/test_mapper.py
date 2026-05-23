import pytest

from modflow_devtools.dfn import schema as v1
from modflow_devtools.dfns.mapper import map as map_v2
from modflow_devtools.dfns.schema import (
    Double,
    Keyword,
    List,
    Model,
    Package,
    Record,
    Simulation,
    String,
)


def _v1_field(**kwargs) -> v1.Field:
    base: dict = {
        "name": "test_field",
        "type": "keyword",
        "block": "options",
        "in_record": False,
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
    return v1.Field(**base)


def _v1_dfn(**kwargs) -> v1.Dfn:
    base: dict = {
        "schema_version": "1",
        "name": "test-dfn",
        "parent": None,
        "blocks": None,
        "advanced": False,
        "multi": False,
        "subcomponents": None,
    }
    base.update(kwargs)
    return v1.Dfn(**base)


def test_map_sim_nam_returns_simulation():
    dfn = _v1_dfn(name="sim-nam")
    result = map_v2(dfn)
    assert isinstance(result, Simulation)


def test_map_model_returns_model():
    dfn = _v1_dfn(name="gwf-nam")
    result = map_v2(dfn)
    assert isinstance(result, Model)

    dfn = _v1_dfn(name="gwt-nam")
    result = map_v2(dfn)
    assert isinstance(result, Model)


def test_map_solution_package():
    dfn = _v1_dfn(name="sln-ims")
    result = map_v2(dfn)
    assert isinstance(result, Package)
    assert result.subtype == "solution"


def test_map_exchange_package():
    dfn = _v1_dfn(name="exg-gwfgwf")
    result = map_v2(dfn)
    assert isinstance(result, Package)
    assert result.subtype == "exchange"


def test_map_utility_package():
    dfn = _v1_dfn(name="utl-obs")
    result = map_v2(dfn)
    assert isinstance(result, Package)
    assert result.subtype == "utility"


def test_map_advanced_package():
    dfn = _v1_dfn(name="gwf-sfr", advanced=True)
    result = map_v2(dfn)
    assert isinstance(result, Package)
    assert result.subtype == "advanced"


def test_map_wrong_schema_version_raises():
    dfn = _v1_dfn(schema_version="2")
    with pytest.raises(ValueError, match="schema version"):
        map_v2(dfn)


def test_map_keyword_field_conversion():
    dfn = _v1_dfn(
        name="gwf-chd",
        blocks={
            "options": {
                "save_flows": _v1_field(
                    name="save_flows",
                    type="keyword",
                    description="save calculated flows",
                    tagged=True,
                    in_record=False,
                ),
            }
        },
    )
    component = map_v2(dfn)
    assert component.blocks is not None
    options = component.blocks["options"].fields
    assert "save_flows" in options
    field = options["save_flows"]
    assert isinstance(field, Keyword)
    assert field.name == "save_flows"
    assert field.description == "save calculated flows"


def test_map_double_precision_field_conversion():
    dfn = _v1_dfn(
        name="gwf-chd",
        blocks={
            "options": {
                "some_float": _v1_field(
                    name="some_float",
                    type="double precision",
                    description="a floating point value",
                ),
            }
        },
    )
    component = map_v2(dfn)
    options = component.blocks["options"].fields
    field = options["some_float"]
    assert isinstance(field, Double)
    assert field.type == "double"


def test_map_record_conversion():
    dfn = _v1_dfn(
        name="test-dfn",
        blocks={
            "options": {
                "auxrecord": _v1_field(
                    name="auxrecord",
                    type="record auxiliary auxname",
                    in_record=False,
                ),
                "auxiliary": _v1_field(
                    name="auxiliary",
                    type="keyword",
                    in_record=True,
                ),
                "auxname": _v1_field(
                    name="auxname",
                    type="string",
                    in_record=True,
                ),
            }
        },
    )
    component = map_v2(dfn)
    auxrecord = component.blocks["options"].fields["auxrecord"]
    assert isinstance(auxrecord, Record)
    assert "auxiliary" in auxrecord.children
    assert "auxname" in auxrecord.children
    assert isinstance(auxrecord.children["auxiliary"], Keyword)
    assert isinstance(auxrecord.children["auxname"], String)


def test_map_recarray_conversion():
    dfn = _v1_dfn(
        name="test-pkg",
        blocks={
            "dimensions": {
                "maxbound": _v1_field(
                    name="maxbound",
                    type="integer",
                    block="dimensions",
                    in_record=False,
                ),
            },
            "period": {
                "stress_period_data": _v1_field(
                    name="stress_period_data",
                    type="recarray cellid q",
                    block="period",
                    shape="(maxbound)",
                ),
                "cellid": _v1_field(
                    name="cellid",
                    type="integer",
                    block="period",
                    shape="(ncelldim)",
                    in_record=True,
                ),
                "q": _v1_field(
                    name="q",
                    type="double precision",
                    block="period",
                    in_record=True,
                ),
            },
        },
    )
    component = map_v2(dfn)
    period_fields = component.blocks["period"].fields
    spd = period_fields["stress_period_data"]
    assert isinstance(spd, List)
    assert spd.shape == ["maxbound"]
    assert isinstance(spd.item, Record)
    assert "cellid" in spd.item.fields
    assert "q" in spd.item.fields


def test_map_recarray_missing_shape_inferred_from_maxbound():
    """Period list with empty shape gets shape=["maxbound"] when maxbound dim exists."""
    dfn = _v1_dfn(
        name="utl-spc",
        blocks={
            "dimensions": {
                "maxbound": _v1_field(
                    name="maxbound",
                    type="integer",
                    block="dimensions",
                    in_record=False,
                ),
            },
            "period": {
                "spd": _v1_field(
                    name="spd",
                    type="recarray bndno spcsetting",
                    block="period",
                    shape="",  # empty in v1
                ),
                "bndno": _v1_field(
                    name="bndno",
                    type="integer",
                    block="period",
                    in_record=True,
                ),
                "spcsetting": _v1_field(
                    name="spcsetting",
                    type="keystring concentration",
                    block="period",
                    in_record=True,
                ),
                "concentration": _v1_field(
                    name="concentration",
                    type="double precision",
                    block="period",
                    tagged=True,
                    in_record=True,
                ),
            },
        },
    )
    component = map_v2(dfn)
    period_fields = component.blocks["period"].fields
    spd = period_fields["spd"]
    assert isinstance(spd, List)
    assert spd.shape == ["maxbound"]


def test_map_recarray_no_shape_no_maxbound():
    """Period list with no shape and no maxbound dim keeps shape=[]."""
    dfn = _v1_dfn(
        name="gwf-sfr",
        advanced=True,
        blocks={
            "period": {
                "perioddata": _v1_field(
                    name="perioddata",
                    type="recarray ifno sfrsetting",
                    block="period",
                    shape="",
                ),
                "ifno": _v1_field(
                    name="ifno",
                    type="integer",
                    block="period",
                    in_record=True,
                ),
                "sfrsetting": _v1_field(
                    name="sfrsetting",
                    type="keystring status",
                    block="period",
                    in_record=True,
                ),
                "status": _v1_field(
                    name="status",
                    type="string",
                    block="period",
                    tagged=True,
                    in_record=True,
                ),
            },
        },
    )
    component = map_v2(dfn)
    period_fields = component.blocks["period"].fields
    lst = period_fields["perioddata"]
    assert isinstance(lst, List)
    assert lst.shape == []
