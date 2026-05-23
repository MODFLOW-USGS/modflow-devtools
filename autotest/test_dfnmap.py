import json
import tomllib
from pathlib import Path

import pytest
import yaml

from modflow_devtools.dfn import Dfn, fetch_dfns
from modflow_devtools.dfnmap import migrate
from modflow_devtools.markers import requires_pkg

FORMATS = ["yaml", "toml", "json"]
MF6_OWNER = "MODFLOW-ORG"
MF6_REPO = "modflow6"
MF6_REF = "develop"


def _load(path: Path, fmt: str) -> dict:
    if fmt == "toml":
        with path.open("rb") as f:
            return tomllib.load(f)
    elif fmt == "json":
        with path.open() as f:
            return json.load(f)
    else:
        with path.open() as f:
            return yaml.safe_load(f)


@pytest.fixture(scope="module")
def dfn_dir(module_tmpdir):
    pytest.importorskip("boltons")
    path = module_tmpdir / "dfn"
    path.mkdir()
    fetch_dfns(MF6_OWNER, MF6_REPO, MF6_REF, path, verbose=True)
    return path


@pytest.fixture(scope="module", params=FORMATS)
def converted_v2(request, dfn_dir, module_tmpdir):
    fmt = request.param
    out = module_tmpdir / f"v2-{fmt}"
    migrate(dfn_dir, out, schema_version="2", fmt=fmt)
    return out, fmt


@requires_pkg("boltons")
def test_convert_v2(converted_v2):
    out, fmt = converted_v2
    files = list(out.glob(f"*.{fmt}"))
    assert files
    for p in files:
        data = _load(p, fmt)
        assert data["name"] == p.stem
        assert data["schema_version"] == "2"


@requires_pkg("boltons")
def test_roundtrip(converted_v2):
    """Verify Dfn.load can read v2-schema files in any format."""
    out, fmt = converted_v2
    mode = "rb" if fmt == "toml" else "r"
    for p in out.glob(f"*.{fmt}"):
        with p.open(mode) as f:
            dfn = Dfn.load(f, name=p.stem, version=fmt)
        assert any(dfn)
