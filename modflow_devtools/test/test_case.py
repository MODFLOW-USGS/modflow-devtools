import pytest
from modflow_devtools.case import Case
from pytest_cases import parametrize, parametrize_with_cases


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


template = Case(name="QA")
cases = [
    template.copy_update(
        name=template.name + "1",
        question="What's the meaning of life, the universe, and everything?",
        answer=42,
    ),
    template.copy_update(
        name=template.name + "2",
        question="Is a Case immutable?",
        answer="No, but it's probably best not to mutate it.",
    ),
]


@pytest.mark.parametrize("case", cases)
def test_cases(case):
    assert len(cases) == 2
    assert cases[0] != cases[1]


gen_cases = [
    template.copy_update(
        name=f"{template.name}{i}", question=f"Q{i}", answer=f"A{i}"
    )
    for i in range(3)
]
info = (
    "cases can be modified further in the generator function,"
    " or the function may construct and return another object"
)


@parametrize(case=gen_cases, ids=[c.name for c in gen_cases])
def qa_cases(case):
    return case.copy_update(info=info)


@parametrize_with_cases("case", cases=".", prefix="qa_")
def test_qa(case):
    assert "QA" in case.name
    assert info == case.info
    print(f"{case.name}:", f"{case.question}? {case.answer}")
    print(case.info)
