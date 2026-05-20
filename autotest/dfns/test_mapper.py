import tomli
from pydantic import TypeAdapter

from modflow_devtools.dfns.schema import Component


def test_convert_v2(toml_v2_name):
    with (TOML_V2_DIR / f"{toml_v2_name}.toml").open("rb") as f:
        data = tomli.load(f)
    assert TypeAdapter(Component).validate_python(data).name == toml_v2_name
