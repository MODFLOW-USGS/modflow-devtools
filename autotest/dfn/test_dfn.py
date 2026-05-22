import tempfile
from pathlib import Path

from modflow_devtools.dfn import Dfn, fetch_dfns
from modflow_devtools.dfn2toml import convert
from modflow_devtools.markers import requires_pkg

MF6_OWNER = "MODFLOW-ORG"
MF6_REPO = "modflow6"
MF6_REF = "develop"

_DFN_DIR: Path | None = None
_TOML_V1_DIR: Path | None = None
_TOML_V1_1_DIR: Path | None = None
_TMPDIR: tempfile.TemporaryDirectory | None = None


def _ensure_dfns() -> Path:
    global _DFN_DIR, _TMPDIR
    if _DFN_DIR is None:
        _TMPDIR = tempfile.TemporaryDirectory()
        _DFN_DIR = Path(_TMPDIR.name) / "dfn"
        _DFN_DIR.mkdir()
        fetch_dfns(MF6_OWNER, MF6_REPO, MF6_REF, _DFN_DIR, verbose=True)
    return _DFN_DIR


def _ensure_toml_v1() -> Path:
    global _TOML_V1_DIR
    dfn_dir = _ensure_dfns()
    if _TOML_V1_DIR is None:
        _TOML_V1_DIR = dfn_dir / "toml"
        convert(dfn_dir, _TOML_V1_DIR, schema_version="1")
    return _TOML_V1_DIR


def _ensure_toml_v1_1() -> Path:
    global _TOML_V1_1_DIR
    dfn_dir = _ensure_dfns()
    if _TOML_V1_1_DIR is None:
        _TOML_V1_1_DIR = dfn_dir / "toml-v1_1"
        convert(dfn_dir, _TOML_V1_1_DIR, schema_version="1.1")
    return _TOML_V1_1_DIR


def pytest_generate_tests(metafunc):
    if "dfn_name" in metafunc.fixturenames:
        dfn_dir = _ensure_dfns()
        dfn_names = [p.stem for p in dfn_dir.glob("*.dfn") if p.stem not in ("common", "flopy")]
        metafunc.parametrize("dfn_name", dfn_names, ids=dfn_names)

    if "toml_name" in metafunc.fixturenames:
        toml_dir = _ensure_toml_v1()
        toml_names = [p.stem for p in toml_dir.glob("*.toml")]
        metafunc.parametrize("toml_name", toml_names, ids=toml_names)

    if "toml_v1_1_name" in metafunc.fixturenames:
        toml_dir = _ensure_toml_v1_1()
        toml_names = [p.stem for p in toml_dir.glob("*.toml")]
        metafunc.parametrize("toml_v1_1_name", toml_names, ids=toml_names)


@requires_pkg("boltons")
def test_load_v1(dfn_name):
    dfn_dir = _ensure_dfns()
    with (
        (dfn_dir / "common.dfn").open() as common_file,
        (dfn_dir / f"{dfn_name}.dfn").open() as dfn_file,
    ):
        common, _ = Dfn._load_v1_flat(common_file)
        dfn = Dfn.load(dfn_file, name=dfn_name, common=common)
        assert any(dfn)


@requires_pkg("boltons")
def test_load_v2(toml_name):
    toml_dir = _ensure_toml_v1()
    with (toml_dir / f"{toml_name}.toml").open(mode="rb") as toml_file:
        toml = Dfn.load(toml_file, name=toml_name, version=2)
        assert any(toml)


@requires_pkg("boltons")
def test_load_all():
    dfn_dir = _ensure_dfns()
    dfns = Dfn.load_all(dfn_dir)
    assert any(dfns)


@requires_pkg("boltons")
def test_convert_v1_1(toml_v1_1_name):
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    toml_dir = _ensure_toml_v1_1()
    with (toml_dir / f"{toml_v1_1_name}.toml").open("rb") as f:
        data = tomllib.load(f)
    assert data["name"] == toml_v1_1_name
    assert data["schema_version"] == "1.1"
