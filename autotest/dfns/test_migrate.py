import json
import tomllib
from pathlib import Path

import pytest
import yaml

from modflow_devtools.dfns import fetch_dfns, migrate

FORMATS = ["yaml", "toml", "json"]
MF6_OWNER = "MODFLOW-ORG"
MF6_REPO = "modflow6"
MF6_REF = "6.7.0"


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
def dev0(request, dfn_dir, module_tmpdir):
    fmt = request.param
    out = module_tmpdir / f"dev0-{fmt}"
    migrate(dfn_dir, out, schema_version="2.0.0.dev0", fmt=fmt)
    return out, fmt


@pytest.fixture(scope="module", params=FORMATS)
def dev1(request, dfn_dir, module_tmpdir):
    fmt = request.param
    out = module_tmpdir / f"dev1-{fmt}"
    migrate(dfn_dir, out, schema_version="2.0.0.dev1", fmt=fmt)
    return out, fmt


@pytest.fixture(scope="module", params=FORMATS)
def dev2(request, dfn_dir, module_tmpdir):
    fmt = request.param
    out = module_tmpdir / f"dev2-{fmt}"
    migrate(dfn_dir, out, schema_version="2.0.0.dev2", fmt=fmt)
    return out, fmt


@pytest.fixture(scope="module", params=FORMATS)
def dev3(request, dfn_dir, module_tmpdir):
    fmt = request.param
    out = module_tmpdir / f"dev3-{fmt}"
    migrate(dfn_dir, out, schema_version="2.0.0.dev3", fmt=fmt)
    return out, fmt


def test_migrate_v2_0_0_dev0(dev0, snapshot):
    out, fmt = dev0
    files = sorted(out.glob(f"*.{fmt}"))
    assert files
    for p in files:
        data = _load(p, fmt)
        assert data["name"] == p.stem
        assert data["schema_version"] == "2.0.0.dev0"
        assert snapshot(name=p.stem) == p.read_text()


def test_migrate_v2_0_0_dev1(dev1, snapshot):
    out, fmt = dev1
    files = sorted(out.glob(f"*.{fmt}"))
    assert files
    for p in files:
        data = _load(p, fmt)
        assert data["name"] == p.stem
        assert data["schema_version"] == "2.0.0.dev1"
        assert snapshot(name=p.stem) == p.read_text()


def test_migrate_v2_0_0_dev2(dev2, snapshot):
    out, fmt = dev2
    files = sorted(out.glob(f"*.{fmt}"))
    assert files
    for p in files:
        data = _load(p, fmt)
        assert data["name"] == p.stem
        assert data["schema_version"] == "2.0.0.dev2"
        assert snapshot(name=p.stem) == p.read_text()


def test_migrate_v2_0_0_dev3(dev3, snapshot):
    out, fmt = dev3
    files = sorted(out.glob(f"*.{fmt}"))
    assert files
    for p in files:
        data = _load(p, fmt)
        assert data["name"] == p.stem
        assert data["schema_version"] == "2.0.0.dev3"
        assert snapshot(name=p.stem) == p.read_text()
