import pytest
import yaml

from db_tool.config.loader import ConfigError, ConfigLoader
from db_tool.config.models import ConnectorType, Environment


def _write_connections(path, data):
    path.write_text(yaml.dump(data))


def test_load_profiles_success(tmp_path):
    f = tmp_path / "connections.yaml"
    _write_connections(f, [
        {"alias": "dev", "environment": "dev", "type": "mongodb",
         "connection_string": "mongodb://localhost", "database_name": "db", "blacklist": []},
    ])
    loader = ConfigLoader(connections_path=f, settings_path=tmp_path / "settings.env")
    profiles = loader.load_profiles()
    assert len(profiles) == 1
    assert profiles[0].alias == "dev"
    assert profiles[0].environment == Environment.DEV
    assert profiles[0].type == ConnectorType.MONGODB


def test_load_profiles_missing_file(tmp_path):
    loader = ConfigLoader(
        connections_path=tmp_path / "missing.yaml",
        settings_path=tmp_path / "settings.env",
    )
    with pytest.raises(ConfigError, match="not found"):
        loader.load_profiles()


def test_load_profiles_duplicate_alias(tmp_path):
    f = tmp_path / "connections.yaml"
    _write_connections(f, [
        {"alias": "same", "environment": "dev", "type": "mongodb", "connection_string": "m://a/b", "database_name": "db"},
        {"alias": "same", "environment": "local", "type": "mongodb", "connection_string": "m://c/d", "database_name": "db"},
    ])
    loader = ConfigLoader(connections_path=f, settings_path=tmp_path / "s.env")
    with pytest.raises(ConfigError, match="Duplicate"):
        loader.load_profiles()


def test_load_profiles_not_a_list(tmp_path):
    f = tmp_path / "connections.yaml"
    f.write_text(yaml.dump({"key": "value"}))
    loader = ConfigLoader(connections_path=f, settings_path=tmp_path / "s.env")
    with pytest.raises(ConfigError, match="list"):
        loader.load_profiles()


def test_load_settings_defaults(tmp_path):
    loader = ConfigLoader(
        connections_path=tmp_path / "c.yaml",
        settings_path=tmp_path / "missing.env",
    )
    settings = loader.load_settings()
    assert settings.batch_size == 1000


def test_load_settings_from_file(tmp_path):
    f = tmp_path / "settings.env"
    f.write_text("BATCH_SIZE=500\nTHROTTLE_RPS=10\n")
    loader = ConfigLoader(connections_path=tmp_path / "c.yaml", settings_path=f)
    settings = loader.load_settings()
    assert settings.batch_size == 500
    assert settings.throttle_rps == 10.0


def test_save_settings_roundtrip(tmp_path):
    from db_tool.config.models import Settings
    f = tmp_path / "settings.env"
    loader = ConfigLoader(connections_path=tmp_path / "c.yaml", settings_path=f)
    original = Settings(batch_size=250, throttle_rps=5.0)
    loader.save_settings(original)
    loaded = loader.load_settings()
    assert loaded.batch_size == 250
    assert loaded.throttle_rps == 5.0


def test_get_profile_not_found(tmp_path):
    f = tmp_path / "connections.yaml"
    _write_connections(f, [
        {"alias": "dev", "environment": "dev", "type": "mongodb", "connection_string": "m://a/b", "database_name": "db"},
    ])
    loader = ConfigLoader(connections_path=f, settings_path=tmp_path / "s.env")
    with pytest.raises(ConfigError, match="not found"):
        loader.get_profile("nonexistent")
