"""Tests for DFN schema PK/FK relations"""

import pytest

from modflow_devtools.dfns.schema import (
    Block,
    Dfns,
    Double,
    Integer,
    List,
    Model,
    Package,
    Record,
    _validate_fk_fields,
)


def _fk_validation_ctx(fk_val, pk_on_item=True, fk_ref=None):
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


def test_dfns_validate_fk_fields():
    lak, gwf = _fk_validation_ctx("packagedata", pk_on_item=True)
    spec = Dfns(components={"gwf-nam": gwf, "gwf-lak": lak})
    assert "gwf-lak" in spec.components


def test_dfns_validate_fk_fields_unknown_block():
    lak, gwf = _fk_validation_ctx("nosuchblock", pk_on_item=True)
    with pytest.raises(ValueError, match="is not a list block"):
        Dfns(components={"gwf-nam": gwf, "gwf-lak": lak})


def test_dfns_validate_fk_fields_no_pk_on_item():
    lak, gwf = _fk_validation_ctx("packagedata", pk_on_item=False)
    with pytest.raises(ValueError, match="has no pk=True field"):
        Dfns(components={"gwf-nam": gwf, "gwf-lak": lak})


def test_dfns_validate_fk_fields_fk_ref():
    lak, gwf = _fk_validation_ctx("packagedata", pk_on_item=True, fk_ref="gwf-nam")
    spec = Dfns(components={"gwf-nam": gwf, "gwf-lak": lak})
    assert "gwf-lak" in spec.components


def test_dfns_validate_fk_fields_fk_ref_unknown():
    lak, gwf = _fk_validation_ctx("packagedata", pk_on_item=True, fk_ref="no-such-comp")
    with pytest.raises(ValueError, match="not found in spec"):
        Dfns(components={"gwf-nam": gwf, "gwf-lak": lak})


def test_dfns_validate_fk_fields_no_fk_set():
    item = Record(name="item", fields={"val": Double(name="val")})
    lst = List(name="data", item=item)
    block = Block(name="data", fields={"data": lst})
    pkg = Package(name="gwf-test", blocks={"data": block})
    gwf = Model(name="gwf-nam", blocks=None)
    spec = Dfns(components={"gwf-nam": gwf, "gwf-test": pkg})
    assert "gwf-test" in spec.components


def test_dfns_validate_fk_fields_called_directly():
    lak, gwf = _fk_validation_ctx("packagedata", pk_on_item=True)
    spec = Dfns(components={"gwf-nam": gwf, "gwf-lak": lak})
    _validate_fk_fields(lak, spec)  # should not raise
