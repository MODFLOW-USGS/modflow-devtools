import pytest
from modflow_devtools.case import Case


def test_requires_name():
    with pytest.raises(ValueError):
        Case()


def test_defaults():
    assert not Case(name="test").xfail


def test_copy():
    case = Case(name="test", foo="bar")
    copy = case.copy()

    assert case is not copy
    assert case == copy


def test_copy_update():
    case = Case(name="test", foo="bar")
    copy = case.copy_update()

    assert case is not copy
    assert case == copy

    copy2 = case.copy_update(foo="baz")

    assert copy is not copy2
    assert copy.foo == "bar"
    assert copy2.foo == "baz"
