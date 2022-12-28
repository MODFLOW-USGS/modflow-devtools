# Cases

An alternative approach to testing, rather than loading pre-existing models from a repository, is to construct test models in code. This typically involves defining variables or `pytest` fixtures in the same test script as the test function. While this pattern is effective for manually defined scenarios, it tightly couples test functions to test cases, prevents easy reuse of the test case by other tests, and tends to lead to duplication, as each test script may reproduce similar test functions and data-generation procedures.

This package provides a minimal framework for self-describing test cases which can be defined once and plugged into arbitrary test functions. At its core is the `Case` class, which is just a `SimpleNamespace` with a few defaults and a `copy_update()` method for easy modification. This pairs nicely with [`pytest-cases`](https://smarie.github.io/python-pytest-cases/), which is recommended but not required.

## Overview

A `Case` requires only a `name`, and has a single default attribute, `xfail=False`, indicating whether the test case is expected to succeed. (Test functions may of course choose to use or ignore this.)

## Usage

### Parametrizing with `Case`

`Case` can be used with `@pytest.mark.parametrize()` as usual. For instance:

```python
import pytest
from modflow_devtools.case import Case

template = Case(name="QA")
cases = [
    template.copy_update(name=template.name + "1",
                         question="What's the meaning of life, the universe, and everything?",
                         answer=42),
    template.copy_update(name=template.name + "2",
                         question="Is a Case immutable?",
                         answer="No, but it's probably best not to mutate it.")
]


@pytest.mark.parametrize("case", cases)
def test_cases(case):
    assert len(cases) == 2
    assert cases[0] != cases[1]
```

### Generating cases dynamically

One pattern possible with `pytest-cases` is to programmatically generate test cases by parametrizing a function. This can be a convenient way to produce several similar test cases from a template:

```python
from pytest_cases import parametrize, parametrize_with_cases
from modflow_devtools.case import Case


template = Case(name="QA")
gen_cases = [template.copy_update(name=f"{template.name}{i}", question=f"Q{i}", answer=f"A{i}") for i in range(3)]
info = "cases can be modified further in the generator function,"\
       " or the function may construct and return another object"


@parametrize(case=gen_cases, ids=[c.name for c in gen_cases])
def qa_cases(case):
    return case.copy_update(info=info)


@parametrize_with_cases("case", cases=".", prefix="qa_")
def test_qa(case):
    assert "QA" in case.name
    assert info == case.info
    print(f"{case.name}:", f"{case.question}? {case.answer}")
    print(case.info)
```