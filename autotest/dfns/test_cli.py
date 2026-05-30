"""Tests for the DFNs CLI"""

from pathlib import Path
from unittest.mock import patch

import pytest
import tomli

from modflow_devtools.dfns.__main__ import main
from modflow_devtools.dfns.registry import RemoteDfnRegistry


@pytest.fixture
def cache_root(tmp_path):
    """Redirect the global DFN cache to a temp directory for test isolation."""
    with patch.object(RemoteDfnRegistry, "base_cache_path", return_value=tmp_path):
        yield tmp_path


@pytest.fixture
def user_config(tmp_path):
    """Redirect the user overlay config to a temp path for test isolation."""
    config_path = tmp_path / "modflow-devtools" / "dfns.toml"
    with patch.object(RemoteDfnRegistry, "user_config_path", return_value=config_path):
        yield config_path


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


def test_add_writes_user_config(cache_root, user_config, capsys):
    release_id = "MODFLOW-ORG/modflow6@6.6.0"

    with patch.object(RemoteDfnRegistry, "sync", side_effect=lambda force=False: None):
        result = main(["add", release_id])

    assert result == 0
    assert user_config.exists()
    with user_config.open("rb") as f:
        data = tomli.load(f)
    assert release_id in data["releases"]
    assert "Added" in capsys.readouterr().out


def test_add_already_present(cache_root, user_config, capsys):
    release_id = "MODFLOW-ORG/modflow6@6.6.0"
    user_config.parent.mkdir(parents=True, exist_ok=True)
    user_config.write_bytes(b'releases = ["MODFLOW-ORG/modflow6@6.6.0"]\n')

    with patch.object(RemoteDfnRegistry, "sync", side_effect=lambda force=False: None):
        result = main(["add", release_id])

    assert result == 0
    with user_config.open("rb") as f:
        data = tomli.load(f)
    assert data["releases"].count(release_id) == 1
    assert "Already" in capsys.readouterr().out


def test_add_appends_to_existing_config(cache_root, user_config, capsys):
    user_config.parent.mkdir(parents=True, exist_ok=True)
    user_config.write_bytes(b'releases = ["MODFLOW-ORG/modflow6@6.5.0"]\n')

    with patch.object(RemoteDfnRegistry, "sync", side_effect=lambda force=False: None):
        result = main(["add", "MODFLOW-ORG/modflow6@6.6.0"])

    assert result == 0
    with user_config.open("rb") as f:
        data = tomli.load(f)
    assert "MODFLOW-ORG/modflow6@6.5.0" in data["releases"]
    assert "MODFLOW-ORG/modflow6@6.6.0" in data["releases"]


def test_add_syncs_by_default(cache_root, user_config):
    release_id = "MODFLOW-ORG/modflow6@6.6.0"
    sync_calls: list[bool] = []

    with patch.object(
        RemoteDfnRegistry, "sync", side_effect=lambda force=False: sync_calls.append(force)
    ):
        result = main(["add", release_id])

    assert result == 0
    assert sync_calls == [False]


def test_add_no_sync_skips_sync(cache_root, user_config):
    release_id = "MODFLOW-ORG/modflow6@6.6.0"
    sync_calls: list = []

    with patch.object(
        RemoteDfnRegistry, "sync", side_effect=lambda force=False: sync_calls.append(force)
    ):
        result = main(["add", "--no-sync", release_id])

    assert result == 0
    assert sync_calls == []
    assert user_config.exists()


def test_add_creates_config_dir(cache_root, user_config):
    assert not user_config.parent.exists()

    with patch.object(RemoteDfnRegistry, "sync", side_effect=lambda force=False: None):
        result = main(["add", "MODFLOW-ORG/modflow6@6.6.0"])

    assert result == 0
    assert user_config.parent.exists()
    assert user_config.exists()


def test_add_invalid_release_id(cache_root, user_config, capsys):
    for bad in ["no-at-sign", "@no-repo", "owner/name", "owner/name@"]:
        result = main(["add", bad])
        assert result != 0
        assert "invalid" in capsys.readouterr().err.lower()


def test_add_error_returns_nonzero(cache_root, user_config, capsys):
    with patch.object(RemoteDfnRegistry, "sync", side_effect=ConnectionError("network down")):
        result = main(["add", "MODFLOW-ORG/modflow6@6.6.0"])

    assert result != 0
    assert "network down" in capsys.readouterr().err


def test_migrate_forwards_args(tmp_path):
    """CLI forwards -i, -o, -s, -f to migrate()."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    with patch("modflow_devtools.dfns.__main__.migrate") as mock_migrate:
        result = main(
            [
                "migrate",
                "-i",
                str(input_dir),
                "-o",
                str(output_dir),
                "-s",
                "2.0.0.dev2",
                "-f",
                "toml",
            ]
        )

    assert result == 0
    mock_migrate.assert_called_once_with(str(input_dir), str(output_dir), "2.0.0.dev2", "toml")


def test_migrate_default_format_is_yaml(tmp_path):
    """--format defaults to 'yaml' when not specified."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    with patch("modflow_devtools.dfns.__main__.migrate") as mock_migrate:
        main(["migrate", "-i", str(input_dir), "-o", str(output_dir), "-s", "2.0.0.dev2"])

    mock_migrate.assert_called_once_with(str(input_dir), str(output_dir), "2.0.0.dev2", "yaml")


@pytest.mark.parametrize("schema_version", ["2.0.0.dev0", "2.0.0.dev1", "2.0.0.dev2"])
def test_migrate_schema_versions(tmp_path, schema_version):
    """--schema-version is forwarded correctly for each supported version."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    with patch("modflow_devtools.dfns.__main__.migrate") as mock_migrate:
        result = main(
            ["migrate", "-i", str(input_dir), "-o", str(output_dir), "-s", schema_version]
        )

    assert result == 0
    mock_migrate.assert_called_once_with(str(input_dir), str(output_dir), schema_version, "yaml")


@pytest.mark.parametrize("fmt", ["yaml", "toml", "json"])
def test_migrate_output_formats(tmp_path, fmt):
    """--format is forwarded correctly for each supported format."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    with patch("modflow_devtools.dfns.__main__.migrate") as mock_migrate:
        result = main(
            ["migrate", "-i", str(input_dir), "-o", str(output_dir), "-s", "2.0.0.dev2", "-f", fmt]
        )

    assert result == 0
    mock_migrate.assert_called_once_with(str(input_dir), str(output_dir), "2.0.0.dev2", fmt)


def test_migrate_error_returns_nonzero(tmp_path, capsys):
    """Exceptions from migrate() produce a nonzero exit code and print to stderr."""
    with patch(
        "modflow_devtools.dfns.__main__.migrate", side_effect=ValueError("bad schema version")
    ):
        result = main(["migrate", "-i", str(tmp_path), "-o", str(tmp_path / "out"), "-s", "99"])

    assert result != 0
    assert "bad schema version" in capsys.readouterr().err
