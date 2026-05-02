from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from typer.testing import CliRunner

from db_tool.cli.commands import app

runner = CliRunner()


def make_connections_yaml(tmp_path: Path, profiles: list[dict]) -> Path:
    f = tmp_path / "connections.yaml"
    f.write_text(yaml.dump(profiles))
    return f


@pytest.fixture
def connections_file(tmp_path):
    return make_connections_yaml(tmp_path, [
        {"alias": "prod-db", "environment": "production", "type": "mongodb",
         "connection_string": "mongodb://prod", "database_name": "db", "blacklist": []},
        {"alias": "dev-db", "environment": "dev", "type": "mongodb",
         "connection_string": "mongodb://localhost", "database_name": "db", "blacklist": []},
    ])


@pytest.fixture(autouse=True)
def patch_loader(connections_file, tmp_path):
    settings_file = tmp_path / "settings.env"
    with patch("db_tool.cli.commands._loader") as mock_loader:
        from db_tool.config.loader import ConfigLoader
        real_loader = ConfigLoader(
            connections_path=connections_file,
            settings_path=settings_file,
        )
        mock_loader.get_profile.side_effect = real_loader.get_profile
        mock_loader.load_profiles.side_effect = real_loader.load_profiles
        mock_loader.load_settings.side_effect = real_loader.load_settings
        yield mock_loader


def test_config_list(patch_loader):
    result = runner.invoke(app, ["config", "list"])
    assert result.exit_code == 0
    assert "prod-db" in result.stdout
    assert "dev-db" in result.stdout


def test_delete_blocked_on_production(patch_loader):
    result = runner.invoke(app, ["delete", "--target", "prod-db", "--pattern", ".*"])
    assert result.exit_code == 1
    assert "PRODUCTION" in result.output


def test_copy_blocked_on_production_target(patch_loader):
    result = runner.invoke(app, ["copy", "--source", "dev-db", "--target", "prod-db"])
    assert result.exit_code == 1
    assert "PRODUCTION" in result.output


def test_copy_dry_run(patch_loader):
    with patch("db_tool.cli.commands.get_connector") as mock_gc:
        mock_src = MagicMock()
        mock_src.__enter__ = lambda s: s
        mock_src.__exit__ = MagicMock(return_value=False)
        mock_src.profile.alias = "dev-db"
        mock_src.list_collections.return_value = ["users"]
        mock_src.estimated_count.return_value = 0
        mock_src.iter_documents.return_value = iter([])

        mock_tgt = MagicMock()
        mock_tgt.__enter__ = lambda s: s
        mock_tgt.__exit__ = MagicMock(return_value=False)
        mock_tgt.profile.alias = "dev-db"
        mock_tgt.is_write_allowed.return_value = True
        mock_tgt.assert_write_allowed = MagicMock()

        mock_gc.side_effect = [mock_src, mock_tgt]

        result = runner.invoke(app, [
            "copy", "--source", "dev-db", "--target", "dev-db",
            "--pattern", "users", "--dry-run"
        ])
        assert result.exit_code == 0


def test_cleanup_mappings(patch_loader):
    with patch("db_tool.obfuscation.mappings.MappingStore.clear_all", return_value=3):
        result = runner.invoke(app, ["cleanup", "mappings"])
    assert result.exit_code == 0
    assert "3" in result.output


def test_cleanup_state(patch_loader):
    with patch("db_tool.state.manager.StateManager.clear_all", return_value=5):
        result = runner.invoke(app, ["cleanup", "state"])
    assert result.exit_code == 0
    assert "5" in result.output
