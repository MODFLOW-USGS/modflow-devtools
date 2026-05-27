import pytest

from modflow_devtools.dfn import schema as v1
from modflow_devtools.dfns.migrate_v1_to_v2 import _DEPENDENT_VARS, _OC_RTYPE_VALID
from modflow_devtools.dfns.migrate_v1_to_v2 import v1_to_v2 as v1_to_v2
from modflow_devtools.dfns.schema import (
    Double,
    FieldBase,
    Keyword,
    List,
    Model,
    Package,
    Record,
    Simulation,
    String,
    Union,
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


def test_keyword():
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
    component = v1_to_v2(dfn)
    assert component.blocks is not None
    options = component.blocks["options"].fields
    assert "save_flows" in options
    field = options["save_flows"]
    assert isinstance(field, Keyword)
    assert field.name == "save_flows"
    assert field.description == "save calculated flows"


def test_double():
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
    component = v1_to_v2(dfn)
    options = component.blocks["options"].fields
    field = options["some_float"]
    assert isinstance(field, Double)
    assert field.type == "double"


def test_record():
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
    component = v1_to_v2(dfn)
    auxrecord = component.blocks["options"].fields["auxrecord"]
    assert isinstance(auxrecord, Record)
    assert "auxiliary" in auxrecord.children
    assert "auxname" in auxrecord.children
    assert isinstance(auxrecord.children["auxiliary"], Keyword)
    assert isinstance(auxrecord.children["auxname"], String)


def test_union():
    """Keystring (union) type conversion."""
    dfn = _v1_dfn(
        name="test-dfn",
        blocks={
            "options": {
                "obs_filerecord": _v1_field(
                    name="obs_filerecord",
                    type="record obs6 filein obs6_filename",
                    block="options",
                    tagged=True,
                ),
                "obs6": _v1_field(
                    name="obs6",
                    type="keyword",
                    block="options",
                    in_record=True,
                ),
                "filein": _v1_field(
                    name="filein",
                    type="keyword",
                    block="options",
                    in_record=True,
                ),
                "obs6_filename": _v1_field(
                    name="obs6_filename",
                    type="string",
                    block="options",
                    in_record=True,
                    preserve_case=True,
                ),
            }
        },
    )

    component = v1_to_v2(dfn)
    obs_rec = component.blocks["options"].fields["obs_filerecord"]
    assert isinstance(obs_rec, Record)
    assert obs_rec.type == "record"
    assert obs_rec.children is not None
    assert all(isinstance(child, FieldBase) for child in obs_rec.children.values())


def test_list():
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
    component = v1_to_v2(dfn)
    period_fields = component.blocks["period"].fields
    spd = period_fields["stress_period_data"]
    assert isinstance(spd, List)
    assert spd.shape == ["maxbound"]
    assert isinstance(spd.item, Record)
    assert "cellid" in spd.item.fields
    assert "q" in spd.item.fields


def test_list_missing_shape_inferred_from_maxbound():
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
    component = v1_to_v2(dfn)
    period_fields = component.blocks["period"].fields
    spd = period_fields["spd"]
    assert isinstance(spd, List)
    assert spd.shape == ["maxbound"]


def test_list_no_shape_no_maxbound():
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
    component = v1_to_v2(dfn)
    period_fields = component.blocks["period"].fields
    lst = period_fields["perioddata"]
    assert isinstance(lst, List)
    assert lst.shape == []


def test_options_block():
    dfn = _v1_dfn(
        name="test-dfn",
        blocks={
            "options": {
                "save_flows": _v1_field(
                    name="save_flows",
                    type="keyword",
                    block="options",
                    description="save calculated flows",
                    tagged=True,
                    in_record=False,
                ),
                "some_float": _v1_field(
                    name="some_float",
                    type="double precision",
                    block="options",
                    description="a floating point value",
                ),
            }
        },
    )

    component = v1_to_v2(dfn)
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


def test_period_block():
    dfn = _v1_dfn(
        name="test-pkg",
        blocks={
            "period": {
                "stress_period_data": _v1_field(
                    name="stress_period_data",
                    type="recarray cellid q",
                    block="period",
                    description="stress period data",
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
            }
        },
    )

    component = v1_to_v2(dfn)
    assert component.blocks is not None
    for block in component.blocks.values():
        for f in block.fields.values():
            assert isinstance(f, FieldBase)
            if f.children:
                for child in f.children.values():
                    assert isinstance(child, FieldBase)

    period_fields = component.blocks["period"].fields
    assert "stress_period_data" in period_fields
    spd = period_fields["stress_period_data"]
    assert isinstance(spd, List)
    assert isinstance(spd.item, Record)
    item_fields = spd.item.fields
    assert "cellid" in item_fields
    assert "q" in item_fields


def test_components():
    dfn = _v1_dfn(name="sim-nam")
    result = v1_to_v2(dfn)
    assert isinstance(result, Simulation)

    dfn = _v1_dfn(name="gwf-nam")
    result = v1_to_v2(dfn)
    assert isinstance(result, Model)

    dfn = _v1_dfn(name="sln-ims")
    result = v1_to_v2(dfn)
    assert isinstance(result, Package)
    assert result.subtype == "solution"

    dfn = _v1_dfn(name="exg-gwfgwf")
    result = v1_to_v2(dfn)
    assert isinstance(result, Package)
    assert result.subtype == "exchange"

    dfn = _v1_dfn(name="utl-obs")
    result = v1_to_v2(dfn)
    assert isinstance(result, Package)
    assert result.subtype == "utility"

    dfn = _v1_dfn(name="gwf-sfr", advanced=True)
    result = v1_to_v2(dfn)
    assert isinstance(result, Package)
    assert result.subtype == "advanced"


def _oc_dfn(prefix: str) -> v1.Dfn:
    """Minimal OC-like v1 DFN for testing rtype.valid migration."""
    return _v1_dfn(
        name=f"{prefix}-oc",
        parent=f"{prefix}-nam",
        blocks={
            "period": {
                "saverecord": _v1_field(
                    name="saverecord",
                    type="record save rtype ocsetting",
                    block="period",
                    optional=True,
                ),
                "save": _v1_field(name="save", type="keyword", block="period", in_record=True),
                "printrecord": _v1_field(
                    name="printrecord",
                    type="record print rtype ocsetting",
                    block="period",
                    optional=True,
                ),
                "print": _v1_field(name="print", type="keyword", block="period", in_record=True),
                "rtype": _v1_field(
                    name="rtype",
                    type="string",
                    block="period",
                    in_record=True,
                    tagged=False,
                ),
                "ocsetting": _v1_field(
                    name="ocsetting",
                    type="keystring all",
                    block="period",
                    in_record=True,
                ),
                "all": _v1_field(name="all", type="keyword", block="period", in_record=True),
            }
        },
    )


@pytest.mark.parametrize("prefix,expected", list(_OC_RTYPE_VALID.items()))
def test_oc_rtype_valid(prefix, expected):
    component = v1_to_v2(_oc_dfn(prefix))
    assert isinstance(component, Package)
    period = component.blocks["period"]
    output = period.fields["output"]
    assert isinstance(output, List)
    assert isinstance(output.item, Union)
    for arm in output.item.arms.values():
        assert isinstance(arm, Record)
        rtype = arm.fields["rtype"]
        assert isinstance(rtype, String)
        assert rtype.valid == expected


@pytest.mark.parametrize("prefix,expected", list(_DEPENDENT_VARS.items()))
def test_model_dependent_variable(prefix, expected):
    result = v1_to_v2(_v1_dfn(name=f"{prefix}-nam"))
    assert isinstance(result, Model)
    assert result.dependent_variable == expected


def test_model_no_dependent_variable():
    result = v1_to_v2(_v1_dfn(name="prt-nam"))
    assert isinstance(result, Model)
    assert result.dependent_variable is None
