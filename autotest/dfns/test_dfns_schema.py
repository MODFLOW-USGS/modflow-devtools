import ast

import pytest

from modflow_devtools.dfn import schema as v1
from modflow_devtools.dfns import Dfns
from modflow_devtools.dfns.mapper import map as map_v2
from modflow_devtools.dfns.schema import (
    Array,
    Block,
    Dim,
    Double,
    FieldBase,
    Integer,
    Keyword,
    List,
    Model,
    Package,
    Record,
    Simulation,
    String,
    _names_in_expr,
    _resolve_derived_dims,
    _validate_fk_fields,
    _validate_shape_element,
    _validate_sum_call,
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


def _dim_block(*names: str) -> Block:
    return Block(
        name="dimensions",
        fields={n: Integer(name=n) for n in names},
    )


def _pkg(name: str, blocks=None, dims=None, parent=None, **kw) -> Package:
    return Package(name=name, blocks=blocks, dims=dims, parent=parent, **kw)


def test_field_roundtrip():
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


def test_map_v2():
    dfn = _v1_dfn(name="sim-nam")
    result = map_v2(dfn)
    assert isinstance(result, Simulation)

    dfn = _v1_dfn(name="gwf-nam")
    result = map_v2(dfn)
    assert isinstance(result, Model)

    dfn = _v1_dfn(name="sln-ims")
    result = map_v2(dfn)
    assert isinstance(result, Package)
    assert result.subtype == "solution"

    dfn = _v1_dfn(name="exg-gwfgwf")
    result = map_v2(dfn)
    assert isinstance(result, Package)
    assert result.subtype == "exchange"

    dfn = _v1_dfn(name="utl-obs")
    result = map_v2(dfn)
    assert isinstance(result, Package)
    assert result.subtype == "utility"

    dfn = _v1_dfn(name="gwf-sfr", advanced=True)
    result = map_v2(dfn)
    assert isinstance(result, Package)
    assert result.subtype == "advanced"


def test_map_v2_field_conversion():
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

    component = map_v2(dfn)
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


def test_map_v2_period_block_conversion():
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

    component = map_v2(dfn)
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


def test_map_v2_record_conversion():
    """Record type with multiple scalar fields."""
    dfn = _v1_dfn(
        name="test-dfn",
        blocks={
            "options": {
                "auxrecord": _v1_field(
                    name="auxrecord",
                    type="record auxiliary auxname",
                    block="options",
                    in_record=False,
                ),
                "auxiliary": _v1_field(
                    name="auxiliary",
                    type="keyword",
                    block="options",
                    in_record=True,
                ),
                "auxname": _v1_field(
                    name="auxname",
                    type="string",
                    block="options",
                    in_record=True,
                ),
            }
        },
    )

    component = map_v2(dfn)
    auxrecord = component.blocks["options"].fields["auxrecord"]
    assert isinstance(auxrecord, Record)
    assert auxrecord.type == "record"
    assert auxrecord.children is not None
    assert "auxiliary" in auxrecord.children
    assert "auxname" in auxrecord.children
    assert isinstance(auxrecord.children["auxiliary"], Keyword)
    assert isinstance(auxrecord.children["auxname"], String)


def test_keystring_type_conversion():
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

    component = map_v2(dfn)
    obs_rec = component.blocks["options"].fields["obs_filerecord"]
    assert isinstance(obs_rec, Record)
    assert obs_rec.type == "record"
    assert obs_rec.children is not None
    assert all(isinstance(child, FieldBase) for child in obs_rec.children.values())


def test_local_dims():
    # dims section populated → local_dims returns those names
    block = _dim_block("nlay", "nrow", "ncol")
    pkg = Package(
        name="gwf-dis",
        blocks={"dimensions": block},
        dims={
            "nlay": Dim(field="nlay", scope="model"),
            "nrow": Dim(field="nrow", scope="model"),
            "ncol": Dim(field="ncol", scope="model"),
        },
    )
    spec = Dfns(components={"gwf-dis": pkg})
    assert spec.local_dims("gwf-dis") == {"nlay", "nrow", "ncol"}

    # no dims section → empty
    pkg2 = Package(name="gwf-chd", blocks=None, dims=None)
    spec2 = Dfns(components={"gwf-chd": pkg2})
    assert spec2.local_dims("gwf-chd") == set()

    # derived dims also included
    pkg3 = Package(
        name="test",
        blocks=None,
        dims={"nodes": Dim(expr="42", scope="component")},
    )
    spec3 = Dfns(components={"test": pkg3})
    assert spec3.local_dims("test") == {"nodes"}


def test_names_in_expr_simple_arithmetic():
    assert _names_in_expr("nlay * nrow * ncol") == {"nlay", "nrow", "ncol"}


def test_names_in_expr_single_name():
    assert _names_in_expr("nodes") == {"nodes"}


def test_names_in_expr_excludes_sum_internals():
    names = _names_in_expr("sum(packagedata.nlakeconn)")
    assert "packagedata" not in names
    assert "nlakeconn" not in names


def test_names_in_expr_mixed_sum_and_arithmetic():
    names = _names_in_expr("nlay * nrow + sum(packagedata.nlakeconn)")
    assert names == {"nlay", "nrow"}


def test_names_in_expr_excludes_sum_func_name_itself():
    names = _names_in_expr("sum(list.col)")
    assert "sum" not in names


def test_names_in_expr_invalid_syntax():
    with pytest.raises(ValueError, match="Invalid expression"):
        _names_in_expr("nlay * (")


def _make_sum_call(expr: str):
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            return node
    raise AssertionError("No Call node found")


def _pkg_with_list(list_field_name: str, col_name: str, col_type=None) -> Package:
    col = (col_type or Integer)(name=col_name)
    item = Record(name="item", fields={col_name: col})
    lst = List(name=list_field_name, item=item)
    block = Block(name=list_field_name, fields={list_field_name: lst})
    return _pkg("test", blocks={list_field_name: block})


def test_validate_sum_expr():
    pkg = _pkg_with_list("packagedata", "nlakeconn")
    call = _make_sum_call("sum(packagedata.nlakeconn)")
    _validate_sum_call(call, pkg, "sum(packagedata.nlakeconn)")

    # fully qualified
    pkg = _pkg_with_list("packagedata", "nlakeconn")
    call = _make_sum_call("sum(packagedata.packagedata.nlakeconn)")
    _validate_sum_call(call, pkg, "sum(packagedata.packagedata.nlakeconn)")

    # unrecognized
    pkg = _pkg("test", blocks=None)
    call = _make_sum_call("sum(nolist.col)")
    with pytest.raises(ValueError, match="unknown list field"):
        _validate_sum_call(call, pkg, "sum(nolist.col)")

    pkg = _pkg_with_list("packagedata", "nlakeconn")
    call = _make_sum_call("sum(wrongblock.packagedata.nlakeconn)")
    with pytest.raises(ValueError, match="block qualifier"):
        _validate_sum_call(call, pkg, "sum(wrongblock.packagedata.nlakeconn)")

    pkg = _pkg_with_list("packagedata", "name", col_type=String)
    call = _make_sum_call("sum(packagedata.name)")
    with pytest.raises(ValueError, match="must be Integer"):
        _validate_sum_call(call, pkg, "sum(packagedata.name)")

    pkg = _pkg_with_list("packagedata", "nlakeconn")
    call = _make_sum_call("sum(packagedata.nosuchcol)")
    with pytest.raises(ValueError, match="not found"):
        _validate_sum_call(call, pkg, "sum(packagedata.nosuchcol)")


def test_resolve_derived_dims():
    block = _dim_block("nlay", "nrow", "ncol")
    pkg = Package(
        name="test",
        blocks={"dimensions": block},
        dims={
            "nlay": Dim(field="nlay", scope="component"),
            "nrow": Dim(field="nrow", scope="component"),
            "ncol": Dim(field="ncol", scope="component"),
            "nodes": Dim(expr="nlay * nrow * ncol", scope="component"),
        },
    )
    order = _resolve_derived_dims(pkg, {"nlay", "nrow", "ncol"})
    assert order == ["nodes"]

    pkg = Package(
        name="test",
        blocks={"dimensions": block},
        dims={
            "nlay": Dim(field="nlay", scope="component"),
            "nrow": Dim(field="nrow", scope="component"),
            "ncol": Dim(field="ncol", scope="component"),
            "nodes": Dim(expr="nlay * nrow * ncol", scope="component"),
            "nodouble": Dim(expr="nodes * 2", scope="component"),
        },
    )
    order = _resolve_derived_dims(pkg, {"nlay", "nrow", "ncol"})
    assert order.index("nodes") < order.index("nodouble")

    pkg = Package(
        name="test",
        blocks=None,
        dims={"derived": Dim(expr="nodes + 1", scope="component")},
    )
    order = _resolve_derived_dims(pkg, {"nodes"})
    assert order == ["derived"]


def test_resolve_derived_dims_sum_operand_allowed():
    pkg = _pkg_with_list("packagedata", "nlakeconn")
    pkg = Package(
        name="test",
        blocks=pkg.blocks,
        dims={"total_conn": Dim(expr="sum(packagedata.nlakeconn)", scope="component")},
    )
    order = _resolve_derived_dims(pkg, set())
    assert order == ["total_conn"]


def test_resolve_derived_dims_no_derived_returns_empty():
    pkg = Package(name="test", blocks=None, dims=None)
    assert _resolve_derived_dims(pkg, set()) == []


def test_resolve_derived_dims_cycle_error():
    pkg = Package(
        name="test",
        blocks=None,
        dims={
            "a": Dim(expr="b + 1", scope="component"),
            "b": Dim(expr="a + 1", scope="component"),
        },
    )
    with pytest.raises(ValueError, match="Cycle in"):
        _resolve_derived_dims(pkg, set())


def test_resolve_derived_dims_unknown_operand_error():
    pkg = Package(
        name="test",
        blocks=None,
        dims={"nodes": Dim(expr="mystery_dim * 2", scope="component")},
    )
    with pytest.raises(ValueError, match="not a known dimension"):
        _resolve_derived_dims(pkg, set())


def test_resolve_derived_dims_invalid_expression_error():
    pkg = Package(
        name="test",
        blocks=None,
        dims={"nodes": Dim(expr="nlay * (", scope="component")},
    )
    with pytest.raises(ValueError, match="Invalid"):
        _resolve_derived_dims(pkg, set())


def test_dfnspec_construction_validates_dims():
    block = _dim_block("nlay", "nrow", "ncol")
    pkg = Package(
        name="gwf-dis",
        blocks={"dimensions": block},
        dims={
            "nlay": Dim(field="nlay", scope="model"),
            "nrow": Dim(field="nrow", scope="model"),
            "ncol": Dim(field="ncol", scope="model"),
            "nodes": Dim(expr="nlay * nrow * ncol", scope="model"),
        },
    )
    spec = Dfns(components={"gwf-dis": pkg})
    assert "gwf-dis" in spec.components


def test_dfnspec_construction_cycle_raises():
    pkg = Package(
        name="bad",
        blocks=None,
        dims={
            "a": Dim(expr="b + 1", scope="component"),
            "b": Dim(expr="a + 1", scope="component"),
        },
    )
    with pytest.raises(ValueError, match="Cycle in"):
        Dfns(components={"bad": pkg})


def test_dfnspec_construction_unknown_operand_raises():
    pkg = Package(
        name="bad",
        blocks=None,
        dims={"nodes": Dim(expr="ghost_dim * 2", scope="component")},
    )
    with pytest.raises(ValueError, match="not a known dimension"):
        Dfns(components={"bad": pkg})


def test_dfnspec_no_dims_constructs_fine():
    pkg = Package(name="gwf-chd", blocks=None, dims=None)
    spec = Dfns(components={"gwf-chd": pkg})
    assert "gwf-chd" in spec.components


# =============================================================================
# dfns.schema.v2 — DfnSpec.local_dims
# =============================================================================


def test_dfnspec_local_dims():
    block = _dim_block("nlay", "nrow", "ncol")
    pkg = Package(
        name="gwf-dis",
        blocks={"dimensions": block},
        dims={
            "nlay": Dim(field="nlay", scope="model"),
            "nrow": Dim(field="nrow", scope="model"),
            "ncol": Dim(field="ncol", scope="model"),
        },
    )
    spec = Dfns(components={"gwf-dis": pkg})
    assert spec.local_dims("gwf-dis") == {"nlay", "nrow", "ncol"}


def test_dfnspec_local_dims_empty():
    pkg = Package(name="gwf-chd", blocks=None, dims=None)
    spec = Dfns(components={"gwf-chd": pkg})
    assert spec.local_dims("gwf-chd") == set()


def test_dfnspec_inherited_dims_includes_dis_dims():
    dis_block = _dim_block("nlay", "nrow", "ncol")
    dis = Package(
        name="gwf-dis",
        parent="gwf-nam",
        blocks={"dimensions": dis_block},
        dims={
            "nlay": Dim(field="nlay", scope="model"),
            "nrow": Dim(field="nrow", scope="model"),
            "ncol": Dim(field="ncol", scope="model"),
            "nodes": Dim(expr="nlay * nrow * ncol", scope="model"),
        },
    )
    chd = _pkg("gwf-chd", parent="gwf-nam", blocks=None)
    gwf = Model(name="gwf-nam", blocks=None)
    spec = Dfns(components={"gwf-nam": gwf, "gwf-dis": dis, "gwf-chd": chd})

    inherited = spec.inherited_dims("gwf-chd")
    assert "nlay" in inherited
    assert "nrow" in inherited
    assert "ncol" in inherited
    assert "nodes" in inherited  # derived dim from gwf-dis, model-scoped


def test_dfnspec_inherited_dims_disv():
    disv_block = _dim_block("nlay", "ncpl")
    disv = Package(
        name="gwf-disv",
        parent="gwf-nam",
        blocks={"dimensions": disv_block},
        dims={
            "nlay": Dim(field="nlay", scope="model"),
            "ncpl": Dim(field="ncpl", scope="model"),
        },
    )
    chd = _pkg("gwf-chd", parent="gwf-nam", blocks=None)
    gwf = Model(name="gwf-nam", blocks=None)
    spec = Dfns(components={"gwf-nam": gwf, "gwf-disv": disv, "gwf-chd": chd})

    inherited = spec.inherited_dims("gwf-chd")
    assert "nlay" in inherited
    assert "ncpl" in inherited


def test_dfnspec_inherited_dims_disu():
    disu_block = _dim_block("nodes", "nja")
    disu = Package(
        name="gwf-disu",
        parent="gwf-nam",
        blocks={"dimensions": disu_block},
        dims={
            "nodes": Dim(field="nodes", scope="model"),
            "nja": Dim(field="nja", scope="model"),
        },
    )
    chd = _pkg("gwf-chd", parent="gwf-nam", blocks=None)
    gwf = Model(name="gwf-nam", blocks=None)
    spec = Dfns(components={"gwf-nam": gwf, "gwf-disu": disu, "gwf-chd": chd})

    inherited = spec.inherited_dims("gwf-chd")
    assert "nodes" in inherited
    assert "nja" in inherited


def test_dfnspec_inherited_dims_excludes_own():
    """Own dims appear in local_dims but not in inherited_dims."""
    dis_block = _dim_block("nlay", "nrow", "ncol")
    dis = Package(
        name="gwf-dis",
        parent="gwf-nam",
        blocks={"dimensions": dis_block},
        dims={
            "nlay": Dim(field="nlay", scope="model"),
            "nrow": Dim(field="nrow", scope="model"),
            "ncol": Dim(field="ncol", scope="model"),
        },
    )
    chd = Package(
        name="gwf-chd",
        parent="gwf-nam",
        blocks={"dimensions": _dim_block("secret_dim")},
        dims={"secret_dim": Dim(field="secret_dim", scope="model")},
    )
    gwf = Model(name="gwf-nam", blocks=None)
    spec = Dfns(components={"gwf-nam": gwf, "gwf-dis": dis, "gwf-chd": chd})

    inherited = spec.inherited_dims("gwf-chd")
    assert "nlay" in inherited
    assert "secret_dim" not in inherited  # own dim: not in inherited_dims


# =============================================================================
# dfns.schema.v2 — DfnSpec Mapping protocol
# =============================================================================


def test_dfnspec_components_getitem():
    pkg = _pkg("gwf-chd", parent="gwf-nam")
    spec = Dfns(components={"gwf-chd": pkg})
    assert spec.components["gwf-chd"] is pkg


def test_dfnspec_components_iter():
    pkg = _pkg("gwf-chd", parent="gwf-nam")
    spec = Dfns(components={"gwf-chd": pkg})
    assert list(spec.components) == ["gwf-chd"]


def test_dfnspec_components_len():
    pkgs = {f"gwf-p{i}": _pkg(f"gwf-p{i}") for i in range(3)}
    spec = Dfns(components=pkgs)
    assert len(spec.components) == 3


def test_dfnspec_components_contains():
    pkg = _pkg("gwf-chd")
    spec = Dfns(components={"gwf-chd": pkg})
    assert "gwf-chd" in spec.components
    assert "gwf-rch" not in spec.components


# =============================================================================
# dfns.schema.v2 — DfnSpec.schema_version
# =============================================================================


def test_dfnspec_schema_version_from_component():
    pkg = Package(name="gwf-chd", schema_version="2")
    spec = Dfns(components={"gwf-chd": pkg})
    assert spec.schema_version == "2"


def test_dfnspec_schema_version_default():
    pkg = _pkg("gwf-chd")
    spec = Dfns(components={"gwf-chd": pkg})
    assert spec.schema_version == "2"


# =============================================================================
# dfns.schema.v2 — DfnSpec.children_of
# =============================================================================


def test_dfnspec_children_of():
    gwf = Model(name="gwf-nam", blocks=None)
    chd = _pkg("gwf-chd", parent="gwf-nam")
    rch = _pkg("gwf-rch", parent="gwf-nam")
    sim = Simulation(name="sim-nam", blocks=None)
    spec = Dfns(components={"sim-nam": sim, "gwf-nam": gwf, "gwf-chd": chd, "gwf-rch": rch})
    children = spec.children("gwf-nam")
    assert set(children) == {"gwf-chd", "gwf-rch"}


def test_dfnspec_children_of_empty():
    pkg = _pkg("gwf-chd", parent="gwf-nam")
    spec = Dfns(components={"gwf-chd": pkg})
    assert spec.children("gwf-chd") == {}


# =============================================================================
# dfns.schema.v2 — Dfns.dims
# =============================================================================


def _dis_spec() -> Dfns:
    """A minimal gwf-dis + gwf-nam DfnSpec used as shared fixture scaffolding."""
    dis_block = _dim_block("nlay", "nrow", "ncol")
    gwf = Model(name="gwf-nam", blocks=None)
    dis = Package(
        name="gwf-dis",
        parent="gwf-nam",
        blocks={"dimensions": dis_block},
        dims={
            "nlay": Dim(field="nlay", scope="model"),
            "nrow": Dim(field="nrow", scope="model"),
            "ncol": Dim(field="ncol", scope="model"),
            "nodes": Dim(expr="nlay * nrow * ncol", scope="model"),
        },
    )
    return Dfns(components={"gwf-nam": gwf, "gwf-dis": dis})


def _lake_spec(period_item: Record) -> Dfns:
    """
    DfnSpec with a gwf-lak that has a packagedata list block and a
    period list block whose item is `period_item`.
    """
    nlakeconn = Integer(name="nlakeconn")
    lakeno_pk = Integer(name="lakeno", pk=True)
    pkg_item = Record(name="item", fields={"lakeno": lakeno_pk, "nlakeconn": nlakeconn})
    pkg_list = List(name="packagedata", item=pkg_item)
    pkg_block = Block(name="packagedata", fields={"packagedata": pkg_list})
    period_list = List(name="period", item=period_item)
    period_block = Block(name="period", fields={"period": period_list})
    gwf = Model(name="gwf-nam", blocks=None)
    lak = Package(
        name="gwf-lak",
        parent="gwf-nam",
        blocks={"packagedata": pkg_block, "period": period_block},
    )
    return Dfns(components={"gwf-nam": gwf, "gwf-lak": lak})


def test_dims_includes_own():
    spec = _dis_spec()
    known = spec.dims("gwf-dis")
    assert {"nlay", "nrow", "ncol", "nodes"} <= known


def test_dims_includes_derived():
    dis_block = _dim_block("nlay", "nrow", "ncol")
    gwf = Model(name="gwf-nam", blocks=None)
    dis = Package(
        name="gwf-dis",
        parent="gwf-nam",
        blocks={"dimensions": dis_block},
        dims={
            "nlay": Dim(field="nlay", scope="model"),
            "nrow": Dim(field="nrow", scope="model"),
            "ncol": Dim(field="ncol", scope="model"),
            "nodes": Dim(expr="nlay * nrow * ncol", scope="model"),
        },
    )
    spec = Dfns(components={"gwf-nam": gwf, "gwf-dis": dis})
    known = spec.dims("gwf-dis")
    assert "nodes" in known


def test_dims_includes_model_scoped():
    """A gwf-chd component inherits model-scoped dims from gwf-dis."""
    spec = _dis_spec()
    chd = _pkg("gwf-chd", parent="gwf-nam")
    spec2 = Dfns(components=dict(spec.components) | {"gwf-chd": chd})
    known = spec2.dims("gwf-chd")
    assert "nodes" in known  # derived dim from gwf-dis, scope="model"
    assert "nlay" in known  # field-backed dim from gwf-dis, scope="model"


# =============================================================================
# dfns.schema.v2 — _validate_shape_element: dim reference
# =============================================================================


def _make_ctx(dim_names: set[str], derived: dict | None = None):
    """Return (array, component, known_dims) for shape element tests."""
    dims: dict[str, Dim] = {n: Dim(field=n, scope="component") for n in dim_names}
    if derived:
        dims.update({n: Dim(expr=e, scope="component") for n, e in derived.items()})
    blocks = {"dimensions": _dim_block(*dim_names)} if dim_names else None
    pkg = Package(name="test", blocks=blocks, dims=dims or None)
    gwf = Model(name="gwf-nam", blocks=None)
    spec = Dfns(components={"gwf-nam": gwf, "test": pkg})
    known = spec.dims("test")
    arr = Array(name="arr", dtype="double", shape=[])
    return arr, pkg, known


def test_shape_element_valid_explicit_dim():
    arr, pkg, known = _make_ctx({"nlay", "nrow", "ncol"})
    _validate_shape_element("nlay", arr, pkg, None, known)  # no error


def test_shape_element_valid_inherited_dim():
    """A dim declared in a sibling component (model-scoped) is valid."""
    dis = Package(
        name="gwf-dis",
        parent="gwf-nam",
        blocks=None,
        dims={"nodes": Dim(expr="42", scope="model")},
    )
    test_pkg = Package(name="gwf-test", parent="gwf-nam", blocks=None)
    gwf = Model(name="gwf-nam", blocks=None)
    spec = Dfns(components={"gwf-nam": gwf, "gwf-dis": dis, "gwf-test": test_pkg})
    known = spec.dims("gwf-test")
    arr = Array(name="arr", dtype="double", shape=[])
    _validate_shape_element("nodes", arr, test_pkg, None, known)


def test_shape_element_valid_derived_dim():
    arr, pkg, known = _make_ctx({"nlay", "nrow", "ncol"}, derived={"nodes": "nlay * nrow * ncol"})
    _validate_shape_element("nodes", arr, pkg, None, known)


def test_shape_element_unknown_dim_raises():
    arr, pkg, known = _make_ctx({"nlay"})
    with pytest.raises(ValueError, match="does not resolve"):
        _validate_shape_element("mystery", arr, pkg, None, known)


def test_shape_element_invalid_syntax_raises():
    arr, pkg, known = _make_ctx({"nlay"})
    with pytest.raises(ValueError, match="invalid shape element"):
        _validate_shape_element("123bad", arr, pkg, None, known)


def test_shape_element_empty_string_raises():
    arr, pkg, known = _make_ctx({"nlay"})
    with pytest.raises(ValueError, match="invalid shape element"):
        _validate_shape_element("", arr, pkg, None, known)


# =============================================================================
# dfns.schema.v2 — _validate_shape_element: row-level lookup
# =============================================================================


def _lookup_ctx():
    """
    Returns (array, enclosing_record, component, known_dims) for a valid
    row-level lookup scenario mirroring the gwf-lak period table.

    packagedata block has a List with item Record(lakeno pk, nlakeconn int).
    The array lives inside a Record with sibling lakeno(fk='packagedata').
    """
    nlakeconn = Integer(name="nlakeconn")
    lakeno_pk = Integer(name="lakeno", pk=True)
    pkg_item = Record(name="item", fields={"lakeno": lakeno_pk, "nlakeconn": nlakeconn})
    pkg_list = List(name="packagedata", item=pkg_item)
    pkg_block = Block(name="packagedata", fields={"packagedata": pkg_list})

    fk_lakeno = Integer(name="lakeno", fk="packagedata")
    arr = Array(name="outflow", dtype="double", shape=[])
    enc_record = Record(name="item", fields={"lakeno": fk_lakeno, "outflow": arr})

    lak = Package(
        name="gwf-lak",
        parent="gwf-nam",
        blocks={"packagedata": pkg_block},
    )
    gwf = Model(name="gwf-nam", blocks=None)
    spec = Dfns(components={"gwf-nam": gwf, "gwf-lak": lak})
    known = spec.dims("gwf-lak")
    return arr, enc_record, lak, known


def test_shape_element_valid_row_level_lookup():
    arr, enc, pkg, known = _lookup_ctx()
    _validate_shape_element("packagedata.nlakeconn(lakeno)", arr, pkg, enc, known)


def test_shape_element_lookup_on_top_level_array_raises():
    arr, _enc, pkg, known = _lookup_ctx()
    with pytest.raises(ValueError, match="not inside a record"):
        _validate_shape_element("packagedata.nlakeconn(lakeno)", arr, pkg, None, known)


def test_shape_element_lookup_unknown_list_block_raises():
    arr, enc, pkg, known = _lookup_ctx()
    with pytest.raises(ValueError, match="not a list block"):
        _validate_shape_element("noblock.nlakeconn(lakeno)", arr, pkg, enc, known)


def test_shape_element_lookup_unknown_column_raises():
    arr, enc, pkg, known = _lookup_ctx()
    with pytest.raises(ValueError, match="is not a field"):
        _validate_shape_element("packagedata.nocol(lakeno)", arr, pkg, enc, known)


def test_shape_element_lookup_non_integer_column_raises():
    nlakeconn = String(name="nlakeconn")
    lakeno_pk = Integer(name="lakeno", pk=True)
    pkg_item = Record(name="item", fields={"lakeno": lakeno_pk, "nlakeconn": nlakeconn})
    pkg_list = List(name="packagedata", item=pkg_item)
    pkg_block = Block(name="packagedata", fields={"packagedata": pkg_list})
    fk_lakeno = Integer(name="lakeno", fk="packagedata")
    arr = Array(name="outflow", dtype="double", shape=[])
    enc = Record(name="item", fields={"lakeno": fk_lakeno, "outflow": arr})
    lak = Package(name="gwf-lak", parent="gwf-nam", blocks={"packagedata": pkg_block})
    gwf = Model(name="gwf-nam", blocks=None)
    spec = Dfns(components={"gwf-nam": gwf, "gwf-lak": lak})
    known = spec.dims("gwf-lak")
    with pytest.raises(ValueError, match="must be Integer"):
        _validate_shape_element("packagedata.nlakeconn(lakeno)", arr, lak, enc, known)


def test_shape_element_lookup_missing_fk_sibling_raises():
    arr, enc, pkg, known = _lookup_ctx()
    with pytest.raises(ValueError, match="not a sibling field"):
        _validate_shape_element("packagedata.nlakeconn(nosuchfield)", arr, pkg, enc, known)


def test_shape_element_lookup_fk_not_set_raises():
    nlakeconn = Integer(name="nlakeconn")
    lakeno_pk = Integer(name="lakeno", pk=True)
    pkg_item = Record(name="item", fields={"lakeno": lakeno_pk, "nlakeconn": nlakeconn})
    pkg_list = List(name="packagedata", item=pkg_item)
    pkg_block = Block(name="packagedata", fields={"packagedata": pkg_list})
    no_fk_lakeno = Integer(name="lakeno")  # fk=None
    arr = Array(name="outflow", dtype="double", shape=[])
    enc = Record(name="item", fields={"lakeno": no_fk_lakeno, "outflow": arr})
    lak = Package(name="gwf-lak", parent="gwf-nam", blocks={"packagedata": pkg_block})
    gwf = Model(name="gwf-nam", blocks=None)
    spec = Dfns(components={"gwf-nam": gwf, "gwf-lak": lak})
    known = spec.dims("gwf-lak")
    with pytest.raises(ValueError, match=r"\.fk is not set"):
        _validate_shape_element("packagedata.nlakeconn(lakeno)", arr, lak, enc, known)


def test_shape_element_lookup_fk_block_mismatch_raises():
    nlakeconn = Integer(name="nlakeconn")
    lakeno_pk = Integer(name="lakeno", pk=True)
    pkg_item = Record(name="item", fields={"lakeno": lakeno_pk, "nlakeconn": nlakeconn})
    pkg_list = List(name="packagedata", item=pkg_item)
    pkg_block = Block(name="packagedata", fields={"packagedata": pkg_list})
    fk_lakeno = Integer(name="lakeno", fk="otherblock")  # fk → wrong block
    arr = Array(name="outflow", dtype="double", shape=[])
    enc = Record(name="item", fields={"lakeno": fk_lakeno, "outflow": arr})
    lak = Package(name="gwf-lak", parent="gwf-nam", blocks={"packagedata": pkg_block})
    gwf = Model(name="gwf-nam", blocks=None)
    spec = Dfns(components={"gwf-nam": gwf, "gwf-lak": lak})
    known = spec.dims("gwf-lak")
    with pytest.raises(ValueError, match="does not reference block"):
        _validate_shape_element("packagedata.nlakeconn(lakeno)", arr, lak, enc, known)


# =============================================================================
# dfns.schema.v2 — DfnSpec shape validation end-to-end
# =============================================================================


def test_dfnspec_valid_top_level_array_shape():
    dis_block = _dim_block("nlay", "nrow", "ncol")
    arr = Array(name="botm", dtype="double", shape=["nlay", "nrow", "ncol"])
    grid_block = Block(name="griddata", fields={"botm": arr})
    dis = Package(
        name="gwf-dis",
        parent="gwf-nam",
        blocks={"dimensions": dis_block, "griddata": grid_block},
        dims={
            "nlay": Dim(field="nlay", scope="model"),
            "nrow": Dim(field="nrow", scope="model"),
            "ncol": Dim(field="ncol", scope="model"),
        },
    )
    gwf = Model(name="gwf-nam", blocks=None)
    spec = Dfns(components={"gwf-nam": gwf, "gwf-dis": dis})
    assert "gwf-dis" in spec.components


def test_dfnspec_valid_array_in_record():
    dis_block = _dim_block("nlay", "nrow", "ncol")
    arr = Array(name="vals", dtype="double", shape=["ncol"])
    rec = Record(name="myrec", fields={"vals": arr})
    opt_block = Block(name="options", fields={"myrec": rec})
    dis = Package(
        name="gwf-dis",
        parent="gwf-nam",
        blocks={"dimensions": dis_block, "options": opt_block},
        dims={
            "nlay": Dim(field="nlay", scope="model"),
            "nrow": Dim(field="nrow", scope="model"),
            "ncol": Dim(field="ncol", scope="model"),
        },
    )
    gwf = Model(name="gwf-nam", blocks=None)
    Dfns(components={"gwf-nam": gwf, "gwf-dis": dis})


def test_dfnspec_valid_row_level_lookup_in_list_item():
    nlakeconn = Integer(name="nlakeconn")
    lakeno_pk = Integer(name="lakeno", pk=True)
    pkg_item = Record(name="item", fields={"lakeno": lakeno_pk, "nlakeconn": nlakeconn})
    pkg_list = List(name="packagedata", item=pkg_item)
    pkg_block = Block(name="packagedata", fields={"packagedata": pkg_list})

    fk_lakeno = Integer(name="lakeno", fk="packagedata")
    outflow = Array(name="outflow", dtype="double", shape=["packagedata.nlakeconn(lakeno)"])
    period_item = Record(name="item", fields={"lakeno": fk_lakeno, "outflow": outflow})
    period_list = List(name="period", item=period_item)
    period_block = Block(name="period", fields={"period": period_list})

    gwf = Model(name="gwf-nam", blocks=None)
    lak = Package(
        name="gwf-lak",
        parent="gwf-nam",
        blocks={"packagedata": pkg_block, "period": period_block},
    )
    Dfns(components={"gwf-nam": gwf, "gwf-lak": lak})


def test_dfnspec_invalid_array_shape_raises():
    dis_block = _dim_block("nlay", "nrow", "ncol")
    arr = Array(name="botm", dtype="double", shape=["nlay", "no_such_dim"])
    grid_block = Block(name="griddata", fields={"botm": arr})
    dis = Package(
        name="gwf-dis",
        parent="gwf-nam",
        blocks={"dimensions": dis_block, "griddata": grid_block},
        dims={
            "nlay": Dim(field="nlay", scope="model"),
            "nrow": Dim(field="nrow", scope="model"),
            "ncol": Dim(field="ncol", scope="model"),
        },
    )
    gwf = Model(name="gwf-nam", blocks=None)
    with pytest.raises(ValueError, match="does not resolve"):
        Dfns(components={"gwf-nam": gwf, "gwf-dis": dis})


def test_dfnspec_array_shape_resolves_via_derived_dim():
    dis_block = _dim_block("nlay", "nrow", "ncol")
    arr = Array(name="botm", dtype="double", shape=["nodes"])
    grid_block = Block(name="griddata", fields={"botm": arr})
    dis = Package(
        name="gwf-dis",
        parent="gwf-nam",
        blocks={"dimensions": dis_block, "griddata": grid_block},
        dims={
            "nlay": Dim(field="nlay", scope="model"),
            "nrow": Dim(field="nrow", scope="model"),
            "ncol": Dim(field="ncol", scope="model"),
            "nodes": Dim(expr="nlay * nrow * ncol", scope="model"),
        },
    )
    gwf = Model(name="gwf-nam", blocks=None)
    Dfns(components={"gwf-nam": gwf, "gwf-dis": dis})


def test_dfnspec_array_shape_resolves_via_sibling_dis():
    """An array in gwf-chd can reference nlay and nodes from sibling gwf-dis."""
    dis_block = _dim_block("nlay", "nrow", "ncol")
    dis = Package(
        name="gwf-dis",
        parent="gwf-nam",
        blocks={"dimensions": dis_block},
        dims={
            "nlay": Dim(field="nlay", scope="model"),
            "nrow": Dim(field="nrow", scope="model"),
            "ncol": Dim(field="ncol", scope="model"),
            "nodes": Dim(expr="nlay * nrow * ncol", scope="model"),
        },
    )
    chd_arr = Array(name="head", dtype="double", shape=["nlay", "nodes"])
    chd_block = Block(name="period", fields={"head": chd_arr})
    chd = Package(name="gwf-chd", parent="gwf-nam", blocks={"period": chd_block})
    gwf = Model(name="gwf-nam", blocks=None)
    Dfns(components={"gwf-nam": gwf, "gwf-dis": dis, "gwf-chd": chd})


# =============================================================================
# dfns.schema.v2 — _validate_fk_fields
# =============================================================================


def _fk_pkg_and_spec(fk_val, pk_on_item=True, fk_ref=None):
    """
    Build a Package with a packagedata list block and a period block whose
    item record has a lakeno field with fk=fk_val (and optionally fk_ref).
    """
    nlakeconn = Integer(name="nlakeconn")
    lakeno_item = Integer(name="lakeno", pk=pk_on_item)
    pkg_item = Record(name="item", fields={"lakeno": lakeno_item, "nlakeconn": nlakeconn})
    pkg_list = List(name="packagedata", item=pkg_item)
    pkg_block = Block(name="packagedata", fields={"packagedata": pkg_list})

    fk_field = Integer(name="lakeno", fk=fk_val, fk_ref=fk_ref)
    period_item = Record(name="item", fields={"lakeno": fk_field})
    period_list = List(name="period", item=period_item)
    period_block = Block(name="period", fields={"period": period_list})

    gwf = Model(name="gwf-nam", blocks=None)
    lak = Package(
        name="gwf-lak",
        parent="gwf-nam",
        blocks={"packagedata": pkg_block, "period": period_block},
    )
    return lak, gwf


def test_validate_fk_fields_valid():
    lak, gwf = _fk_pkg_and_spec("packagedata", pk_on_item=True)
    spec = Dfns(components={"gwf-nam": gwf, "gwf-lak": lak})
    assert "gwf-lak" in spec.components


def test_validate_fk_fields_unknown_block_raises():
    lak, gwf = _fk_pkg_and_spec("nosuchblock", pk_on_item=True)
    with pytest.raises(ValueError, match="is not a list block"):
        Dfns(components={"gwf-nam": gwf, "gwf-lak": lak})


def test_validate_fk_fields_no_pk_on_item_raises():
    lak, gwf = _fk_pkg_and_spec("packagedata", pk_on_item=False)
    with pytest.raises(ValueError, match="has no pk=True field"):
        Dfns(components={"gwf-nam": gwf, "gwf-lak": lak})


def test_validate_fk_fields_fk_ref_valid():
    lak, gwf = _fk_pkg_and_spec("packagedata", pk_on_item=True, fk_ref="gwf-nam")
    spec = Dfns(components={"gwf-nam": gwf, "gwf-lak": lak})
    assert "gwf-lak" in spec.components


def test_validate_fk_fields_fk_ref_unknown_raises():
    lak, gwf = _fk_pkg_and_spec("packagedata", pk_on_item=True, fk_ref="no-such-comp")
    with pytest.raises(ValueError, match="not found in spec"):
        Dfns(components={"gwf-nam": gwf, "gwf-lak": lak})


def test_validate_fk_fields_no_fk_set_passes():
    item = Record(name="item", fields={"val": Double(name="val")})
    lst = List(name="data", item=item)
    block = Block(name="data", fields={"data": lst})
    pkg = Package(name="gwf-test", blocks={"data": block})
    gwf = Model(name="gwf-nam", blocks=None)
    spec = Dfns(components={"gwf-nam": gwf, "gwf-test": pkg})
    assert "gwf-test" in spec.components


def test_validate_fk_fields_called_directly():
    lak, gwf = _fk_pkg_and_spec("packagedata", pk_on_item=True)
    spec = Dfns(components={"gwf-nam": gwf, "gwf-lak": lak})
    _validate_fk_fields(lak, spec)  # should not raise


# =============================================================================
# dfns.schema.v2 — Block.optional
# =============================================================================


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


# =============================================================================
# dfns.schema.v2 — Array shape position-based rules
# =============================================================================


def test_top_level_array_empty_shape_valid():
    arr = Array(name="auxiliary", dtype="string", shape=[])
    block = Block(name="options", fields={"auxiliary": arr})
    pkg = Package(name="gwf-test", blocks={"options": block})
    gwf = Model(name="gwf-nam", blocks=None)
    Dfns(components={"gwf-nam": gwf, "gwf-test": pkg})


def test_non_rightmost_inline_array_empty_shape_raises():
    arr = Array(name="vals", dtype="double", shape=[])
    extra = Integer(name="extra")
    rec = Record(name="myrec", fields={"vals": arr, "extra": extra})
    block = Block(name="data", fields={"myrec": rec})
    pkg = Package(name="gwf-test", blocks={"data": block})
    gwf = Model(name="gwf-nam", blocks=None)
    with pytest.raises(ValueError, match="rightmost"):
        Dfns(components={"gwf-nam": gwf, "gwf-test": pkg})


def test_rightmost_inline_array_empty_shape_valid():
    arr = Array(name="auxvals", dtype="double", shape=[])
    rec = Record(name="myrec", fields={"auxvals": arr})
    block = Block(name="data", fields={"myrec": rec})
    pkg = Package(name="gwf-test", blocks={"data": block})
    gwf = Model(name="gwf-nam", blocks=None)
    Dfns(components={"gwf-nam": gwf, "gwf-test": pkg})


def test_rightmost_inline_string_array_empty_shape_valid():
    arr = Array(name="auxname", dtype="string", shape=[])
    rec = Record(name="aux_rec", fields={"auxname": arr})
    block = Block(name="options", fields={"aux_rec": rec})
    pkg = Package(name="gwf-test", blocks={"options": block})
    gwf = Model(name="gwf-nam", blocks=None)
    Dfns(components={"gwf-nam": gwf, "gwf-test": pkg})


# =============================================================================
# dfns.schema.v2 — DfnSpec schema version consistency
# =============================================================================


def test_dfnspec_schema_version_consistency_raises():
    pkg1 = Package(name="gwf-chd", schema_version="2")
    pkg2 = Package(name="gwf-wel", schema_version="3")
    with pytest.raises(ValueError, match="schema_version"):
        Dfns(components={"gwf-chd": pkg1, "gwf-wel": pkg2})


def test_dfnspec_schema_version_consistency_null_ignored():
    pkg1 = Package(name="gwf-chd", schema_version="2")
    pkg2 = Package(name="gwf-wel", schema_version=None)
    spec = Dfns(components={"gwf-chd": pkg1, "gwf-wel": pkg2})
    assert spec.schema_version == "2"


# =============================================================================
# dfns.schema.v2 — Bound-annotated shape elements
# =============================================================================


def test_shape_element_bound_lt():
    arr, pkg, known = _make_ctx({"nrow"})
    _validate_shape_element("<nrow", arr, pkg, None, known)


def test_shape_element_bound_gt():
    arr, pkg, known = _make_ctx({"nrow"})
    _validate_shape_element(">nrow", arr, pkg, None, known)


def test_shape_element_bound_lte():
    arr, pkg, known = _make_ctx({"ncol"})
    _validate_shape_element("<=ncol", arr, pkg, None, known)


def test_shape_element_bound_gte():
    arr, pkg, known = _make_ctx({"ncol"})
    _validate_shape_element(">=ncol", arr, pkg, None, known)


def test_shape_element_bound_unknown_dim_raises():
    arr, pkg, known = _make_ctx({"nlay"})
    with pytest.raises(ValueError, match="does not resolve"):
        _validate_shape_element("<unknown_dim", arr, pkg, None, known)


def test_shape_element_bound_invalid_core_raises():
    arr, pkg, known = _make_ctx({"nlay"})
    with pytest.raises(ValueError, match="plain identifier"):
        _validate_shape_element("<123bad", arr, pkg, None, known)
