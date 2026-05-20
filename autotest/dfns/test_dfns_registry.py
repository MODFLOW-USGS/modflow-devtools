import flaky
import pytest
from packaging.version import Version

from modflow_devtools.dfns.registry import LocalDfnRegistry, RemoteDfnRegistry


def test_local_dfn_registry(dfn_dir):
    registry = LocalDfnRegistry(path=dfn_dir)
    assert registry.source == "modflow6"
    assert registry.path == dfn_dir.resolve()

    spec = registry.spec
    assert spec.schema_version == Version("2")
    assert len(spec.components) > 100
    assert "gwf-chd" in spec.components
    assert "sim-nam" in spec.components

    dfn = spec.components("gwf-chd")
    assert dfn.name == "gwf-chd"
    assert dfn.parent == "gwf-nam"

    path = registry.get_path("gwf-chd")
    assert path.exists()
    assert path.name == "gwf-chd.dfn"

    with pytest.raises(FileNotFoundError, match="nonexistent"):
        registry.get_path("nonexistent")


def test_remote_dfn_registry_init():
    registry = RemoteDfnRegistry(source="modflow6", ref="6.6.0")
    assert registry.source == "modflow6"
    assert registry.ref == "6.6.0"

    with pytest.raises(ValueError, match="not a valid release version"):
        RemoteDfnRegistry(source="modflow6", ref="develop")

    with pytest.raises(ValueError, match="Unknown source"):
        RemoteDfnRegistry(source="nonexistent", ref="6.6.0")

    registry = RemoteDfnRegistry(source="modflow6", ref="6.6.0")
    cache_dir = registry.cache_path()
    assert "modflow6" in str(cache_dir)
    assert "6.6.0" in str(cache_dir)


@pytest.mark.skip(reason="Requires mf{version}_dfns.zip release asset on GitHub")
@flaky(max_runs=3, min_passes=1)
def test_remote_dfn_registry_sync():
    registry = RemoteDfnRegistry(source=DFNS_SOURCE, ref=DFNS_VERSION)
    registry.sync(force=True)

    cache_dir = registry.cache_path()
    assert cache_dir.exists()
    assert any(cache_dir.iterdir())

    path = registry.get_path("gwf-chd")
    assert path.exists()

    spec = registry.spec
    assert "gwf-chd" in spec.components
    assert "sim-nam" in spec.components

    dfn = spec.components["gwf-chd"]
    assert dfn.name == "gwf-chd"
