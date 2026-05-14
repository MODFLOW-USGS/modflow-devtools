from pathlib import Path

import pytest
from packaging.version import Version

from modflow_devtools.dfn import Dfn, get_dfns
from modflow_devtools.dfn2toml import convert
from modflow_devtools.markers import requires_pkg

PROJ_ROOT = Path(__file__).parents[1]
DFN_DIR = PROJ_ROOT / "autotest" / "temp" / "dfn"
TOML_DIR = DFN_DIR / "toml"
TOML_V1_1_DIR = DFN_DIR / "toml-v1_1"
TOML_V2_DIR = DFN_DIR / "toml-v2"
VERSIONS = {1: DFN_DIR, 2: TOML_DIR}
MF6_OWNER = "MODFLOW-ORG"
MF6_REPO = "modflow6"
MF6_REF = "develop"


def pytest_generate_tests(metafunc):
    if "dfn_name" in metafunc.fixturenames:
        if not any(DFN_DIR.glob("*.dfn")):
            get_dfns(MF6_OWNER, MF6_REPO, MF6_REF, DFN_DIR, verbose=True)
        dfn_names = [
            dfn.stem for dfn in DFN_DIR.glob("*.dfn") if dfn.stem not in ["common", "flopy"]
        ]
        metafunc.parametrize("dfn_name", dfn_names, ids=dfn_names)

    if "toml_name" in metafunc.fixturenames:
        # Only convert if TOML files don't exist yet (avoid repeated conversions)
        dfn_paths = [p for p in DFN_DIR.glob("*.dfn") if p.stem not in ["common", "flopy"]]
        if not TOML_DIR.exists() or not all(
            (TOML_DIR / f"{dfn.stem}.toml").is_file() for dfn in dfn_paths
        ):
            convert(DFN_DIR, TOML_DIR)
        # Verify all expected TOML files were created
        assert all((TOML_DIR / f"{dfn.stem}.toml").is_file() for dfn in dfn_paths)
        toml_names = [toml.stem for toml in TOML_DIR.glob("*.toml")]
        metafunc.parametrize("toml_name", toml_names, ids=toml_names)

    if "toml_v1_1_name" in metafunc.fixturenames:
        dfn_paths = [p for p in DFN_DIR.glob("*.dfn") if p.stem not in ["common", "flopy"]]
        if not TOML_V1_1_DIR.exists() or not all(
            (TOML_V1_1_DIR / f"{dfn.stem}.toml").is_file() for dfn in dfn_paths
        ):
            convert(DFN_DIR, TOML_V1_1_DIR, schema="1.1")
        assert all((TOML_V1_1_DIR / f"{dfn.stem}.toml").is_file() for dfn in dfn_paths)
        toml_names = [toml.stem for toml in TOML_V1_1_DIR.glob("*.toml")]
        metafunc.parametrize("toml_v1_1_name", toml_names, ids=toml_names)

    if "toml_v2_name" in metafunc.fixturenames:
        dfn_paths = [p for p in DFN_DIR.glob("*.dfn") if p.stem not in ["common", "flopy"]]
        if not TOML_V2_DIR.exists() or not all(
            (TOML_V2_DIR / f"{dfn.stem}.toml").is_file() for dfn in dfn_paths
        ):
            convert(DFN_DIR, TOML_V2_DIR, schema="2")
        assert all((TOML_V2_DIR / f"{dfn.stem}.toml").is_file() for dfn in dfn_paths)
        toml_names = [toml.stem for toml in TOML_V2_DIR.glob("*.toml")]
        metafunc.parametrize("toml_v2_name", toml_names, ids=toml_names)


@requires_pkg("boltons")
def test_load_v1(dfn_name):
    with (
        (DFN_DIR / "common.dfn").open() as common_file,
        (DFN_DIR / f"{dfn_name}.dfn").open() as dfn_file,
    ):
        common, _ = Dfn._load_v1_flat(common_file)
        dfn = Dfn.load(dfn_file, name=dfn_name, common=common)
        assert any(dfn)


@requires_pkg("boltons")
def test_load_v2(toml_name):
    with (TOML_DIR / f"{toml_name}.toml").open(mode="rb") as toml_file:
        toml = Dfn.load(toml_file, name=toml_name, version=2)
        assert any(toml)


@requires_pkg("boltons")
@pytest.mark.parametrize("version", list(VERSIONS.keys()))
def test_load_all(version):
    dfns = Dfn.load_all(VERSIONS[version], version=version)
    assert any(dfns)


@requires_pkg("boltons")
def test_convert_v1_1(toml_v1_1_name):
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    with (TOML_V1_1_DIR / f"{toml_v1_1_name}.toml").open("rb") as f:
        data = tomllib.load(f)
    assert data["name"] == toml_v1_1_name
    assert data["schema_version"] == "1.1"


@requires_pkg("boltons")
def test_convert_v2(toml_v2_name):
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]
    from pydantic import TypeAdapter
    from modflow_devtools.dfns.schema.v2 import Component

    with (TOML_V2_DIR / f"{toml_v2_name}.toml").open("rb") as f:
        data = tomllib.load(f)
    assert TypeAdapter(Component).validate_python(data).name == toml_v2_name
