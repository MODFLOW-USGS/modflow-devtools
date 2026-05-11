"""
Tests for v2 schema types, DfnSpec dimension resolution, and Array shape validation.
"""

import pytest

from modflow_devtools.dfns.schema.v2 import (
    Array,
    Block,
    DfnSpec,
    Double,
    Integer,
    List,
    Model,
    Package,
    Record,
    Simulation,
    String,
    _collect_explicit_dims,
    _known_dims_for,
    _names_in_expr,
    _resolve_derived_dims,
    _validate_fk_fields,
    _validate_shape_element,
    _validate_sum_call,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _dim_block(*names: str) -> Block:
    """Build a dimensions Block with the named Integer dimension fields."""
    return Block(
        name="dimensions",
        fields={n: Integer(name=n, dimension=True) for n in names},
    )


def _pkg(name: str, blocks=None, derived_dims=None, parent=None, **kw) -> Package:
    return Package(name=name, blocks=blocks, derived_dims=derived_dims, parent=parent, **kw)


# ── _collect_explicit_dims ────────────────────────────────────────────────────


def test_collect_explicit_dims_basic():
    block = _dim_block("nlay", "nrow", "ncol")
    pkg = _pkg("gwf-dis", blocks={"dimensions": block})
    assert _collect_explicit_dims(pkg) == {"nlay", "nrow", "ncol"}


def test_collect_explicit_dims_ignores_non_dimension_integers():
    block = Block(
        name="options",
        fields={
            "maxbound": Integer(name="maxbound", dimension=False),
            "nlay": Integer(name="nlay", dimension=True),
        },
    )
    pkg = _pkg("test", blocks={"options": block})
    assert _collect_explicit_dims(pkg) == {"nlay"}


def test_collect_explicit_dims_ignores_non_integer_fields():
    block = Block(
        name="dimensions",
        fields={
            "nlay": Integer(name="nlay", dimension=True),
            "name": String(name="name"),
        },
    )
    pkg = _pkg("test", blocks={"dimensions": block})
    assert _collect_explicit_dims(pkg) == {"nlay"}


def test_collect_explicit_dims_empty_when_no_blocks():
    pkg = _pkg("test", blocks=None)
    assert _collect_explicit_dims(pkg) == set()


def test_collect_explicit_dims_across_multiple_blocks():
    b1 = Block(name="dimensions", fields={"nlay": Integer(name="nlay", dimension=True)})
    b2 = Block(name="griddata", fields={"ncol": Integer(name="ncol", dimension=True)})
    pkg = _pkg("test", blocks={"dimensions": b1, "griddata": b2})
    assert _collect_explicit_dims(pkg) == {"nlay", "ncol"}


# ── _names_in_expr ────────────────────────────────────────────────────────────


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


# ── _validate_sum_call ────────────────────────────────────────────────────────


def _make_sum_call(expr: str):
    import ast

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


def test_validate_sum_call_short_form():
    pkg = _pkg_with_list("packagedata", "nlakeconn")
    call = _make_sum_call("sum(packagedata.nlakeconn)")
    _validate_sum_call(call, pkg, "sum(packagedata.nlakeconn)")


def test_validate_sum_call_long_form():
    pkg = _pkg_with_list("packagedata", "nlakeconn")
    call = _make_sum_call("sum(packagedata.packagedata.nlakeconn)")
    _validate_sum_call(call, pkg, "sum(packagedata.packagedata.nlakeconn)")


def test_validate_sum_call_unknown_list():
    pkg = _pkg("test", blocks=None)
    call = _make_sum_call("sum(nolist.col)")
    with pytest.raises(ValueError, match="unknown list field"):
        _validate_sum_call(call, pkg, "sum(nolist.col)")


def test_validate_sum_call_wrong_block_qualifier():
    pkg = _pkg_with_list("packagedata", "nlakeconn")
    call = _make_sum_call("sum(wrongblock.packagedata.nlakeconn)")
    with pytest.raises(ValueError, match="block qualifier"):
        _validate_sum_call(call, pkg, "sum(wrongblock.packagedata.nlakeconn)")


def test_validate_sum_call_non_integer_column():
    pkg = _pkg_with_list("packagedata", "name", col_type=String)
    call = _make_sum_call("sum(packagedata.name)")
    with pytest.raises(ValueError, match="must be Integer"):
        _validate_sum_call(call, pkg, "sum(packagedata.name)")


def test_validate_sum_call_missing_column():
    pkg = _pkg_with_list("packagedata", "nlakeconn")
    call = _make_sum_call("sum(packagedata.nosuchcol)")
    with pytest.raises(ValueError, match="not found"):
        _validate_sum_call(call, pkg, "sum(packagedata.nosuchcol)")


# ── _resolve_derived_dims ─────────────────────────────────────────────────────


def test_resolve_derived_dims_single():
    block = _dim_block("nlay", "nrow", "ncol")
    pkg = _pkg("test", blocks={"dimensions": block}, derived_dims={"nodes": "nlay * nrow * ncol"})
    order = _resolve_derived_dims(pkg, {"nlay", "nrow", "ncol"})
    assert order == ["nodes"]


def test_resolve_derived_dims_chain():
    block = _dim_block("nlay", "nrow", "ncol")
    pkg = _pkg(
        "test",
        blocks={"dimensions": block},
        derived_dims={"nodes": "nlay * nrow * ncol", "nodouble": "nodes * 2"},
    )
    order = _resolve_derived_dims(pkg, {"nlay", "nrow", "ncol"})
    assert order.index("nodes") < order.index("nodouble")


def test_resolve_derived_dims_inherited_dim_operand_allowed():
    # A dim from another component (e.g. "nodes" from gwf-dis) is passed in via
    # known_dims and should be accepted as a valid derived-dim operand.
    pkg = _pkg("test", blocks=None, derived_dims={"derived": "nodes + 1"})
    order = _resolve_derived_dims(pkg, {"nodes"})
    assert order == ["derived"]


def test_resolve_derived_dims_sum_operand_allowed():
    pkg = _pkg_with_list("packagedata", "nlakeconn")
    pkg = Package(
        name="test",
        blocks=pkg.blocks,
        derived_dims={"total_conn": "sum(packagedata.nlakeconn)"},
    )
    order = _resolve_derived_dims(pkg, set())
    assert order == ["total_conn"]


def test_resolve_derived_dims_no_derived_returns_empty():
    pkg = _pkg("test", blocks=None, derived_dims=None)
    assert _resolve_derived_dims(pkg, set()) == []


def test_resolve_derived_dims_cycle_error():
    pkg = _pkg("test", blocks=None, derived_dims={"a": "b + 1", "b": "a + 1"})
    with pytest.raises(ValueError, match="Cycle in derived_dims"):
        _resolve_derived_dims(pkg, set())


def test_resolve_derived_dims_unknown_operand_error():
    pkg = _pkg("test", blocks=None, derived_dims={"nodes": "mystery_dim * 2"})
    with pytest.raises(ValueError, match="not a known dimension"):
        _resolve_derived_dims(pkg, set())


def test_resolve_derived_dims_invalid_expression_error():
    pkg = _pkg("test", blocks=None, derived_dims={"nodes": "nlay * ("})
    with pytest.raises(ValueError, match="Invalid derived_dims"):
        _resolve_derived_dims(pkg, set())


# ── DfnSpec construction and validation ───────────────────────────────────────


def test_dfnspec_construction_validates_dims():
    block = _dim_block("nlay", "nrow", "ncol")
    pkg = _pkg(
        "gwf-dis",
        blocks={"dimensions": block},
        derived_dims={"nodes": "nlay * nrow * ncol"},
    )
    spec = DfnSpec(components={"gwf-dis": pkg})
    assert "gwf-dis" in spec


def test_dfnspec_construction_cycle_raises():
    pkg = _pkg("bad", blocks=None, derived_dims={"a": "b + 1", "b": "a + 1"})
    with pytest.raises(ValueError, match="Cycle in derived_dims"):
        DfnSpec(components={"bad": pkg})


def test_dfnspec_construction_unknown_operand_raises():
    pkg = _pkg("bad", blocks=None, derived_dims={"nodes": "ghost_dim * 2"})
    with pytest.raises(ValueError, match="not a known dimension"):
        DfnSpec(components={"bad": pkg})


def test_dfnspec_no_derived_dims_constructs_fine():
    pkg = _pkg("gwf-chd", blocks=None, derived_dims=None)
    spec = DfnSpec(components={"gwf-chd": pkg})
    assert "gwf-chd" in spec


# ── DfnSpec.explicit_dims_for ─────────────────────────────────────────────────


def test_dfnspec_explicit_dims_for():
    block = _dim_block("nlay", "nrow", "ncol")
    pkg = _pkg("gwf-dis", blocks={"dimensions": block})
    spec = DfnSpec(components={"gwf-dis": pkg})
    assert spec.explicit_dims_for("gwf-dis") == {"nlay", "nrow", "ncol"}


def test_dfnspec_explicit_dims_for_empty():
    pkg = _pkg("gwf-chd", blocks=None)
    spec = DfnSpec(components={"gwf-chd": pkg})
    assert spec.explicit_dims_for("gwf-chd") == set()


# ── DfnSpec.grid_dims_for ─────────────────────────────────────────────────────


def test_dfnspec_grid_dims_for_no_parent_returns_namespace():
    from modflow_devtools.dfns.schema.v2 import GRID_DIM_NAMESPACE

    pkg = _pkg("sim-nam", blocks=None, parent=None)
    spec = DfnSpec(components={"sim-nam": pkg})
    result = spec.grid_dims_for("sim-nam")
    assert result == set(GRID_DIM_NAMESPACE)


def test_dfnspec_grid_dims_for_includes_dis_dims():
    dis_block = _dim_block("nlay", "nrow", "ncol")
    dis = _pkg("gwf-dis", parent="gwf-nam", blocks={"dimensions": dis_block})
    chd = _pkg("gwf-chd", parent="gwf-nam", blocks=None)
    gwf = Model(name="gwf-nam", blocks=None)
    spec = DfnSpec(components={"gwf-nam": gwf, "gwf-dis": dis, "gwf-chd": chd})

    grid_dims = spec.grid_dims_for("gwf-chd")
    assert "nlay" in grid_dims
    assert "nrow" in grid_dims
    assert "ncol" in grid_dims
    assert "nodes" in grid_dims  # from GRID_DIM_NAMESPACE


def test_dfnspec_grid_dims_for_disv():
    disv_block = _dim_block("nlay", "ncpl")
    disv = _pkg("gwf-disv", parent="gwf-nam", blocks={"dimensions": disv_block})
    chd = _pkg("gwf-chd", parent="gwf-nam", blocks=None)
    gwf = Model(name="gwf-nam", blocks=None)
    spec = DfnSpec(components={"gwf-nam": gwf, "gwf-disv": disv, "gwf-chd": chd})

    grid_dims = spec.grid_dims_for("gwf-chd")
    assert "nlay" in grid_dims
    assert "ncpl" in grid_dims


def test_dfnspec_grid_dims_for_disu():
    disu_block = _dim_block("nodes", "nja")
    disu = _pkg("gwf-disu", parent="gwf-nam", blocks={"dimensions": disu_block})
    chd = _pkg("gwf-chd", parent="gwf-nam", blocks=None)
    gwf = Model(name="gwf-nam", blocks=None)
    spec = DfnSpec(components={"gwf-nam": gwf, "gwf-disu": disu, "gwf-chd": chd})

    grid_dims = spec.grid_dims_for("gwf-chd")
    assert "nodes" in grid_dims
    assert "nja" in grid_dims


def test_dfnspec_grid_dims_for_non_dis_siblings_excluded():
    dis_block = _dim_block("nlay", "nrow", "ncol")
    dis = _pkg("gwf-dis", parent="gwf-nam", blocks={"dimensions": dis_block})

    other_block = Block(
        name="dimensions",
        fields={"secret_dim": Integer(name="secret_dim", dimension=True)},
    )
    other = _pkg("gwf-chd", parent="gwf-nam", blocks={"dimensions": other_block})
    gwf = Model(name="gwf-nam", blocks=None)
    spec = DfnSpec(components={"gwf-nam": gwf, "gwf-dis": dis, "gwf-chd": other})

    grid_dims = spec.grid_dims_for("gwf-chd")
    assert "nlay" in grid_dims
    assert "secret_dim" not in grid_dims


# ── DfnSpec Mapping protocol ──────────────────────────────────────────────────


def test_dfnspec_mapping_getitem():
    pkg = _pkg("gwf-chd", parent="gwf-nam")
    spec = DfnSpec(components={"gwf-chd": pkg})
    assert spec["gwf-chd"] is pkg


def test_dfnspec_mapping_iter():
    pkg = _pkg("gwf-chd", parent="gwf-nam")
    spec = DfnSpec(components={"gwf-chd": pkg})
    assert list(spec) == ["gwf-chd"]


def test_dfnspec_mapping_len():
    pkgs = {f"gwf-p{i}": _pkg(f"gwf-p{i}") for i in range(3)}
    spec = DfnSpec(components=pkgs)
    assert len(spec) == 3


def test_dfnspec_mapping_contains():
    pkg = _pkg("gwf-chd")
    spec = DfnSpec(components={"gwf-chd": pkg})
    assert "gwf-chd" in spec
    assert "gwf-rch" not in spec


# ── DfnSpec.schema_version ────────────────────────────────────────────────────


def test_dfnspec_schema_version_from_component():
    from packaging.version import Version

    pkg = Package(name="gwf-chd", schema_version=Version("2"))
    spec = DfnSpec(components={"gwf-chd": pkg})
    assert spec.schema_version == Version("2")


def test_dfnspec_schema_version_default():
    from packaging.version import Version

    pkg = _pkg("gwf-chd")
    spec = DfnSpec(components={"gwf-chd": pkg})
    assert spec.schema_version == Version("2")


# ── DfnSpec.children_of ───────────────────────────────────────────────────────


def test_dfnspec_children_of():
    gwf = Model(name="gwf-nam", blocks=None)
    chd = _pkg("gwf-chd", parent="gwf-nam")
    rch = _pkg("gwf-rch", parent="gwf-nam")
    sim = Simulation(name="sim-nam", blocks=None)
    spec = DfnSpec(components={"sim-nam": sim, "gwf-nam": gwf, "gwf-chd": chd, "gwf-rch": rch})
    children = spec.children_of("gwf-nam")
    assert set(children) == {"gwf-chd", "gwf-rch"}


def test_dfnspec_children_of_empty():
    pkg = _pkg("gwf-chd", parent="gwf-nam")
    spec = DfnSpec(components={"gwf-chd": pkg})
    assert spec.children_of("gwf-chd") == {}


# ── Shape validation helpers ──────────────────────────────────────────────────


def _dis_spec() -> DfnSpec:
    """A minimal gwf-dis + gwf-nam DfnSpec used as shared fixture scaffolding."""
    dis_block = _dim_block("nlay", "nrow", "ncol")
    gwf = Model(name="gwf-nam", blocks=None)
    dis = Package(name="gwf-dis", parent="gwf-nam", blocks={"dimensions": dis_block})
    return DfnSpec(components={"gwf-nam": gwf, "gwf-dis": dis})


def _lake_spec(period_item: Record) -> DfnSpec:
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
    return DfnSpec(components={"gwf-nam": gwf, "gwf-lak": lak})


# ── _known_dims_for ───────────────────────────────────────────────────────────


def test_known_dims_includes_explicit():
    spec = _dis_spec()
    known = _known_dims_for(spec, "gwf-dis")
    assert {"nlay", "nrow", "ncol"} <= known


def test_known_dims_includes_derived():
    dis_block = _dim_block("nlay", "nrow", "ncol")
    gwf = Model(name="gwf-nam", blocks=None)
    dis = Package(
        name="gwf-dis",
        parent="gwf-nam",
        blocks={"dimensions": dis_block},
        derived_dims={"nodes": "nlay * nrow * ncol"},
    )
    spec = DfnSpec(components={"gwf-nam": gwf, "gwf-dis": dis})
    known = _known_dims_for(spec, "gwf-dis")
    assert "nodes" in known


def test_known_dims_includes_grid_dims():
    spec = _dis_spec()
    # gwf-chd has no local dims but inherits grid dims via gwf-dis sibling
    chd = _pkg("gwf-chd", parent="gwf-nam")
    spec2 = DfnSpec(components=dict(spec.components) | {"gwf-chd": chd})
    known = _known_dims_for(spec2, "gwf-chd")
    assert "nodes" in known  # GRID_DIM_NAMESPACE
    assert "nlay" in known  # from gwf-dis (sibling dis package)


# ── _validate_shape_element: dim reference ────────────────────────────────────


def _make_ctx(dim_names: set[str], derived: dict | None = None):
    """Return (array, component, known_dims) for shape element tests."""
    dis_block = _dim_block(*dim_names)
    pkg = _pkg("test", blocks={"dimensions": dis_block}, derived_dims=derived)
    gwf = Model(name="gwf-nam", blocks=None)
    spec = DfnSpec(components={"gwf-nam": gwf, "test": pkg})
    known = _known_dims_for(spec, "test")
    arr = Array(name="arr", dtype="double", shape=[])
    return arr, pkg, known


def test_shape_element_valid_explicit_dim():
    arr, pkg, known = _make_ctx({"nlay", "nrow", "ncol"})
    _validate_shape_element("nlay", arr, pkg, None, known)  # no error


def test_shape_element_valid_grid_dim():
    arr, pkg, known = _make_ctx(set())
    # "nodes" is always in GRID_DIM_NAMESPACE → known
    _validate_shape_element("nodes", arr, pkg, None, known)


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


# ── _validate_shape_element: row-level lookup ─────────────────────────────────


def _lookup_ctx():
    """
    Returns (array, enclosing_record, component, known_dims) for a valid
    row-level lookup scenario mirroring the gwf-lak period table.

    packagedata block has a List with item Record(lakeno pk, nlakeconn int).
    The array lives inside a Record with sibling lakeno(fk='packagedata').
    """
    # packagedata list
    nlakeconn = Integer(name="nlakeconn")
    lakeno_pk = Integer(name="lakeno", pk=True)
    pkg_item = Record(name="item", fields={"lakeno": lakeno_pk, "nlakeconn": nlakeconn})
    pkg_list = List(name="packagedata", item=pkg_item)
    pkg_block = Block(name="packagedata", fields={"packagedata": pkg_list})

    # enclosing record with fk sibling + array
    fk_lakeno = Integer(name="lakeno", fk="packagedata")
    arr = Array(name="outflow", dtype="double", shape=[])
    enc_record = Record(name="item", fields={"lakeno": fk_lakeno, "outflow": arr})

    lak = Package(
        name="gwf-lak",
        parent="gwf-nam",
        blocks={"packagedata": pkg_block},
    )
    gwf = Model(name="gwf-nam", blocks=None)
    spec = DfnSpec(components={"gwf-nam": gwf, "gwf-lak": lak})
    known = _known_dims_for(spec, "gwf-lak")
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
    # Replace nlakeconn with a String column
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
    spec = DfnSpec(components={"gwf-nam": gwf, "gwf-lak": lak})
    known = _known_dims_for(spec, "gwf-lak")
    with pytest.raises(ValueError, match="must be Integer"):
        _validate_shape_element("packagedata.nlakeconn(lakeno)", arr, lak, enc, known)


def test_shape_element_lookup_missing_fk_sibling_raises():
    arr, enc, pkg, known = _lookup_ctx()
    with pytest.raises(ValueError, match="not a sibling field"):
        _validate_shape_element("packagedata.nlakeconn(nosuchfield)", arr, pkg, enc, known)


def test_shape_element_lookup_fk_not_set_raises():
    # lakeno has no fk attribute set
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
    spec = DfnSpec(components={"gwf-nam": gwf, "gwf-lak": lak})
    known = _known_dims_for(spec, "gwf-lak")
    with pytest.raises(ValueError, match=r"\.fk is not set"):
        _validate_shape_element("packagedata.nlakeconn(lakeno)", arr, lak, enc, known)


def test_shape_element_lookup_fk_block_mismatch_raises():
    # packagedata block exists (check 1 passes) but fk field points to 'otherblock'
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
    spec = DfnSpec(components={"gwf-nam": gwf, "gwf-lak": lak})
    known = _known_dims_for(spec, "gwf-lak")
    with pytest.raises(ValueError, match="does not reference block"):
        _validate_shape_element("packagedata.nlakeconn(lakeno)", arr, lak, enc, known)


# ── DfnSpec shape validation end-to-end ──────────────────────────────────────


def test_dfnspec_valid_top_level_array_shape():
    dis_block = _dim_block("nlay", "nrow", "ncol")
    arr = Array(name="botm", dtype="double", shape=["nlay", "nrow", "ncol"])
    grid_block = Block(name="griddata", fields={"botm": arr})
    dis = Package(
        name="gwf-dis",
        parent="gwf-nam",
        blocks={"dimensions": dis_block, "griddata": grid_block},
    )
    gwf = Model(name="gwf-nam", blocks=None)
    spec = DfnSpec(components={"gwf-nam": gwf, "gwf-dis": dis})
    assert "gwf-dis" in spec


def test_dfnspec_valid_array_in_record():
    dis_block = _dim_block("nlay", "nrow", "ncol")
    arr = Array(name="vals", dtype="double", shape=["ncol"])
    rec = Record(name="myrec", fields={"vals": arr})
    opt_block = Block(name="options", fields={"myrec": rec})
    dis = Package(
        name="gwf-dis",
        parent="gwf-nam",
        blocks={"dimensions": dis_block, "options": opt_block},
    )
    gwf = Model(name="gwf-nam", blocks=None)
    DfnSpec(components={"gwf-nam": gwf, "gwf-dis": dis})


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
    DfnSpec(components={"gwf-nam": gwf, "gwf-lak": lak})


def test_dfnspec_invalid_array_shape_raises():
    dis_block = _dim_block("nlay", "nrow", "ncol")
    arr = Array(name="botm", dtype="double", shape=["nlay", "no_such_dim"])
    grid_block = Block(name="griddata", fields={"botm": arr})
    dis = Package(
        name="gwf-dis",
        parent="gwf-nam",
        blocks={"dimensions": dis_block, "griddata": grid_block},
    )
    gwf = Model(name="gwf-nam", blocks=None)
    with pytest.raises(ValueError, match="does not resolve"):
        DfnSpec(components={"gwf-nam": gwf, "gwf-dis": dis})


def test_dfnspec_array_shape_resolves_via_derived_dim():
    dis_block = _dim_block("nlay", "nrow", "ncol")
    arr = Array(name="botm", dtype="double", shape=["nodes"])
    grid_block = Block(name="griddata", fields={"botm": arr})
    dis = Package(
        name="gwf-dis",
        parent="gwf-nam",
        blocks={"dimensions": dis_block, "griddata": grid_block},
        derived_dims={"nodes": "nlay * nrow * ncol"},
    )
    gwf = Model(name="gwf-nam", blocks=None)
    DfnSpec(components={"gwf-nam": gwf, "gwf-dis": dis})


def test_dfnspec_array_shape_resolves_via_sibling_dis():
    """An array in gwf-chd can reference nlay from sibling gwf-dis."""
    dis_block = _dim_block("nlay", "nrow", "ncol")
    dis = Package(name="gwf-dis", parent="gwf-nam", blocks={"dimensions": dis_block})
    chd_arr = Array(name="head", dtype="double", shape=["nlay", "nodes"])
    chd_block = Block(name="period", fields={"head": chd_arr})
    chd = Package(name="gwf-chd", parent="gwf-nam", blocks={"period": chd_block})
    gwf = Model(name="gwf-nam", blocks=None)
    DfnSpec(components={"gwf-nam": gwf, "gwf-dis": dis, "gwf-chd": chd})


# ── _validate_fk_fields ───────────────────────────────────────────────────────


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
    spec = DfnSpec(components={"gwf-nam": gwf, "gwf-lak": lak})
    assert "gwf-lak" in spec


def test_validate_fk_fields_unknown_block_raises():
    lak, gwf = _fk_pkg_and_spec("nosuchblock", pk_on_item=True)
    with pytest.raises(ValueError, match="is not a list block"):
        DfnSpec(components={"gwf-nam": gwf, "gwf-lak": lak})


def test_validate_fk_fields_no_pk_on_item_raises():
    lak, gwf = _fk_pkg_and_spec("packagedata", pk_on_item=False)
    with pytest.raises(ValueError, match="has no pk=True field"):
        DfnSpec(components={"gwf-nam": gwf, "gwf-lak": lak})


def test_validate_fk_fields_fk_ref_valid():
    lak, gwf = _fk_pkg_and_spec("packagedata", pk_on_item=True, fk_ref="gwf-nam")
    spec = DfnSpec(components={"gwf-nam": gwf, "gwf-lak": lak})
    assert "gwf-lak" in spec


def test_validate_fk_fields_fk_ref_unknown_raises():
    lak, gwf = _fk_pkg_and_spec("packagedata", pk_on_item=True, fk_ref="no-such-comp")
    with pytest.raises(ValueError, match="not found in spec"):
        DfnSpec(components={"gwf-nam": gwf, "gwf-lak": lak})


def test_validate_fk_fields_no_fk_set_passes():
    item = Record(name="item", fields={"val": Double(name="val")})
    lst = List(name="data", item=item)
    block = Block(name="data", fields={"data": lst})
    pkg = Package(name="gwf-test", blocks={"data": block})
    gwf = Model(name="gwf-nam", blocks=None)
    spec = DfnSpec(components={"gwf-nam": gwf, "gwf-test": pkg})
    assert "gwf-test" in spec


def test_validate_fk_fields_called_directly():
    lak, gwf = _fk_pkg_and_spec("packagedata", pk_on_item=True)
    spec = DfnSpec(components={"gwf-nam": gwf, "gwf-lak": lak})
    _validate_fk_fields(lak, spec)  # should not raise
