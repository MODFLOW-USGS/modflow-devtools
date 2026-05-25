"""Tests for the DFNs CLI"""

from pathlib import Path
from unittest.mock import patch

import pytest

from modflow_devtools.dfns.__main__ import main
from modflow_devtools.dfns.registry import RemoteDfnRegistry


@pytest.fixture
def cache_root(tmp_path):
    """Redirect the global DFN cache to a temp directory for test isolation."""
    with patch.object(RemoteDfnRegistry, "base_cache_path", return_value=tmp_path):
        yield tmp_path


def _populate_cache(cache_root: Path, release_id: str) -> Path:
    """Write a minimal fake DFN file so the registry looks cached."""
    repo, tag = release_id.split("@")
    tag_dir = cache_root / repo / tag
    tag_dir.mkdir(parents=True, exist_ok=True)
    (tag_dir / "gwf-chd.toml").write_text("name = 'gwf-chd'\n")
    return tag_dir


def _one_registry(release_id: str) -> dict:
    return {release_id: RemoteDfnRegistry(release_id=release_id)}


def test_main_help(capsys):
    result = main([])
    assert result == 0
    assert capsys.readouterr().out  # some help text printed


def test_info_not_cached(cache_root, capsys):
    with patch.object(
        RemoteDfnRegistry,
        "load_default",
        return_value=_one_registry("MODFLOW-ORG/modflow6@6.6.0"),
    ):
        result = main(["info"])
    assert result == 0
    assert "Not cached" in capsys.readouterr().out


def test_info_cached(cache_root, capsys):
    release_id = "MODFLOW-ORG/modflow6@6.6.0"
    _populate_cache(cache_root, release_id)
    with patch.object(RemoteDfnRegistry, "load_default", return_value=_one_registry(release_id)):
        result = main(["info"])
    assert result == 0
    assert "Cached" in capsys.readouterr().out


def test_info_latest_shows_resolved_tag(cache_root, capsys):
    """For @latest releases, info shows the resolved version that is cached."""
    release_id = "MODFLOW-ORG/modflow6@latest"
    # simulate a resolved "v6.7.0" tag already on disk
    repo, _ = release_id.split("@")
    tag_dir = cache_root / repo / "v6.7.0"
    tag_dir.mkdir(parents=True)
    (tag_dir / "gwf-chd.toml").write_text("name = 'gwf-chd'\n")

    with patch.object(RemoteDfnRegistry, "load_default", return_value=_one_registry(release_id)):
        result = main(["info"])
    assert result == 0
    out = capsys.readouterr().out
    assert "Cached" in out
    assert "latest" in out
    assert "v6.7.0" in out


def test_info_multiple_registries(cache_root, capsys):
    """info lists each registry entry."""
    ids = ["MODFLOW-ORG/modflow6@6.5.0", "MODFLOW-ORG/modflow6@6.6.0"]
    _populate_cache(cache_root, ids[0])
    # ids[1] deliberately not cached
    registries = {rid: RemoteDfnRegistry(release_id=rid) for rid in ids}
    with patch.object(RemoteDfnRegistry, "load_default", return_value=registries):
        result = main(["info"])
    assert result == 0
    out = capsys.readouterr().out
    assert "6.5.0" in out
    assert "6.6.0" in out


def test_clean_removes_cache(cache_root, capsys):
    release_id = "MODFLOW-ORG/modflow6@6.6.0"
    _populate_cache(cache_root, release_id)
    assert any(cache_root.rglob("*.toml"))

    result = main(["clean"])
    assert result == 0
    assert not cache_root.exists()
    assert "clean" in capsys.readouterr().out.lower()


def test_clean_idempotent(cache_root):
    """clean on a non-existent / empty cache silently succeeds."""
    result = main(["clean"])
    assert result == 0


def test_sync_populates_cache(cache_root, capsys):
    release_id = "MODFLOW-ORG/modflow6@6.6.0"
    registry = RemoteDfnRegistry(release_id=release_id)

    def _fake_sync(force=False):
        path = registry.cache_path
        path.mkdir(parents=True, exist_ok=True)
        (path / "gwf-chd.toml").write_text("name = 'gwf-chd'\n")

    with (
        patch.object(RemoteDfnRegistry, "load_default", return_value={release_id: registry}),
        patch.object(RemoteDfnRegistry, "sync", side_effect=_fake_sync),
    ):
        result = main(["sync"])

    assert result == 0
    assert registry.cache_path.exists()
    assert any(registry.cache_path.iterdir())
    assert "Synced" in capsys.readouterr().out


def test_sync_force_flag(cache_root):
    """--force is forwarded to registry.sync."""
    release_id = "MODFLOW-ORG/modflow6@6.6.0"
    registry = RemoteDfnRegistry(release_id=release_id)
    calls: list[bool] = []

    def _capturing_sync(force=False):
        calls.append(force)
        path = registry.cache_path
        path.mkdir(parents=True, exist_ok=True)
        (path / "gwf-chd.toml").write_text("name = 'gwf-chd'\n")

    with (
        patch.object(RemoteDfnRegistry, "load_default", return_value={release_id: registry}),
        patch.object(RemoteDfnRegistry, "sync", side_effect=_capturing_sync),
    ):
        main(["sync", "--force"])

    assert calls == [True]


def test_sync_default_no_force(cache_root):
    """sync without --force passes force=False."""
    release_id = "MODFLOW-ORG/modflow6@6.6.0"
    registry = RemoteDfnRegistry(release_id=release_id)
    calls: list[bool] = []

    def _capturing_sync(force=False):
        calls.append(force)
        path = registry.cache_path
        path.mkdir(parents=True, exist_ok=True)
        (path / "gwf-chd.toml").write_text("name = 'gwf-chd'\n")

    with (
        patch.object(RemoteDfnRegistry, "load_default", return_value={release_id: registry}),
        patch.object(RemoteDfnRegistry, "sync", side_effect=_capturing_sync),
    ):
        main(["sync"])

    assert calls == [False]


def test_sync_error_returns_nonzero(cache_root, capsys):
    release_id = "MODFLOW-ORG/modflow6@6.6.0"
    registry = RemoteDfnRegistry(release_id=release_id)

    with (
        patch.object(RemoteDfnRegistry, "load_default", return_value={release_id: registry}),
        patch.object(RemoteDfnRegistry, "sync", side_effect=ConnectionError("network down")),
    ):
        result = main(["sync"])

    assert result != 0
    assert "network down" in capsys.readouterr().err


def test_roundtrip(cache_root, capsys):
    """info (not cached) → sync → info (cached) → clean → info (not cached)."""
    release_id = "MODFLOW-ORG/modflow6@6.6.0"
    registry = RemoteDfnRegistry(release_id=release_id)
    registries = {release_id: registry}

    def _fake_sync(force=False):
        path = registry.cache_path
        path.mkdir(parents=True, exist_ok=True)
        (path / "gwf-chd.toml").write_text("name = 'gwf-chd'\n")

    with (
        patch.object(RemoteDfnRegistry, "load_default", return_value=registries),
        patch.object(RemoteDfnRegistry, "sync", side_effect=_fake_sync),
    ):
        main(["info"])
        assert "Not cached" in capsys.readouterr().out

        main(["sync"])
        capsys.readouterr()  # discard sync output

        main(["info"])
        assert "Cached" in capsys.readouterr().out

        main(["clean"])
        capsys.readouterr()  # discard clean output

        main(["info"])
        assert "Not cached" in capsys.readouterr().out
