import tomllib

import pytest

from modflow_devtools.dfn import Dfn, fetch_dfns
from modflow_devtools.dfn2toml import convert
from modflow_devtools.markers import requires_pkg

MF6_OWNER = "MODFLOW-ORG"
MF6_REPO = "modflow6"
MF6_REF = "develop"


@pytest.fixture(scope="module")
def dfn_dir(module_tmpdir):
    pytest.importorskip("boltons")
    path = module_tmpdir / "dfn"
    path.mkdir()
    fetch_dfns(MF6_OWNER, MF6_REPO, MF6_REF, path, verbose=True)
    return path


@pytest.fixture(scope="module")
def toml_v1_dir(dfn_dir, module_tmpdir):
    out = module_tmpdir / "toml-v1"
    convert(dfn_dir, out, schema_version="1")
    return out


@pytest.fixture(scope="module")
def toml_v1_1_dir(dfn_dir, module_tmpdir):
    out = module_tmpdir / "toml-v1.1"
    convert(dfn_dir, out, schema_version="1.1")
    return out


@pytest.fixture(scope="module")
def toml_v2_dir(dfn_dir, module_tmpdir):
    out = module_tmpdir / "toml-v2"
    convert(dfn_dir, out, schema_version="2")
    return out


@requires_pkg("boltons")
def test_convert_v1(toml_v1_dir):
    tomls = list(toml_v1_dir.glob("*.toml"))
    assert tomls
    for p in tomls:
        with p.open("rb") as f:
            data = tomllib.load(f)
        assert data["name"] == p.stem
        assert data["schema_version"] == "1"


@requires_pkg("boltons")
def test_convert_v1_roundtrip(toml_v1_dir):
    """Verify Dfn.load can read v1-schema TOML files."""
    for p in toml_v1_dir.glob("*.toml"):
        with p.open("rb") as f:
            dfn = Dfn.load(f, name=p.stem, version=2)
        assert any(dfn)


@requires_pkg("boltons")
def test_convert_v1_1(toml_v1_1_dir):
    tomls = list(toml_v1_1_dir.glob("*.toml"))
    assert tomls
    for p in tomls:
        with p.open("rb") as f:
            data = tomllib.load(f)
        assert data["name"] == p.stem
        assert data["schema_version"] == "1.1"


@requires_pkg("boltons")
def test_convert_v2(toml_v2_dir):
    tomls = list(toml_v2_dir.glob("*.toml"))
    assert tomls
    for p in tomls:
        with p.open("rb") as f:
            data = tomllib.load(f)
        assert data["name"] == p.stem
        assert data["schema_version"] == "2"
