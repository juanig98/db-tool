from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml
from dotenv import dotenv_values

from db_tool.config.models import ConnectionProfile, Settings
import db_tool.i18n as _i18n

_log = logging.getLogger("db_tool.config.loader")


class ConfigError(Exception):
    pass


def _resolve_config_path(filename: str) -> Path:
    """Resolve a config file path.

    Priority:
    1. DB_TOOL_CONFIG env var (full path to connections.yaml; only applies when filename matches)
    2. DB_TOOL_CONFIG_DIR env var (directory containing config files)
    3. Walk up from cwd: check <dir>/config/<filename> then <dir>/<filename> (legacy)
    4. Fall back to <cwd>/config/<filename> so callers get a clear missing-file error
    """
    if filename == "connections.yaml":
        env_file = os.environ.get("DB_TOOL_CONFIG")
        if env_file:
            return Path(env_file)

    env_dir = os.environ.get("DB_TOOL_CONFIG_DIR")
    if env_dir:
        return Path(env_dir) / filename

    current = Path.cwd()
    for directory in [current, *current.parents]:
        candidate = directory / "config" / filename
        if candidate.exists():
            return candidate
        candidate = directory / filename
        if candidate.exists():
            return candidate

    return current / "config" / filename


class ConfigLoader:
    def __init__(
        self,
        connections_path: Path | None = None,
        settings_path: Path | None = None,
    ) -> None:
        self._connections_path = connections_path or _resolve_config_path("connections.yaml")
        self._settings_path = settings_path or _resolve_config_path("settings.env")
        self._connection_warnings: list = []

    def load_profiles(self) -> list[ConnectionProfile]:
        from db_tool.i18n import t
        if not self._connections_path.exists():
            raise ConfigError(t("config.error.connections_not_found", path=self._connections_path))
        with self._connections_path.open() as f:
            raw = yaml.safe_load(f)
        if not isinstance(raw, list):
            raise ConfigError(t("config.error.connections_not_list"))
        profiles: list[ConnectionProfile] = []
        for i, item in enumerate(raw):
            try:
                profiles.append(ConnectionProfile.model_validate(item))
            except Exception as exc:
                raise ConfigError(t("config.error.invalid_profile", index=i, exc=exc)) from exc
        aliases = [p.alias for p in profiles]
        if len(aliases) != len(set(aliases)):
            raise ConfigError(t("config.error.duplicate_aliases"))
        try:
            from db_tool.config.validator import check_connection_string_signals
            self._connection_warnings = check_connection_string_signals(profiles)
        except Exception:
            self._connection_warnings = []
        _log.info(f"Loaded {len(profiles)} connection profiles from {self._connections_path}")
        return profiles

    def get_connection_warnings(self) -> list:
        return list(self._connection_warnings)

    def load_settings(self) -> Settings:
        env_values: dict[str, str | None] = {}
        if self._settings_path.exists():
            env_values = dotenv_values(self._settings_path)
        # also read from process environment (overrides file)
        for key in ("BATCH_SIZE", "THROTTLE_RPS", "STATE_DIR", "MAPPINGS_DIR",
                    "OBFUSCATION_RULES_PATH", "REPLACEMENTS_PATH",
                    "MONGO_MAX_RETRIES", "MONGO_RETRY_BACKOFF_BASE", "LANGUAGE"):
            val = os.environ.get(key)
            if val is not None:
                env_values[key] = val
        raw: dict[str, object] = {}
        if env_values.get("BATCH_SIZE"):
            raw["batch_size"] = int(env_values["BATCH_SIZE"])  # type: ignore[arg-type]
        if env_values.get("THROTTLE_RPS"):
            raw["throttle_rps"] = float(env_values["THROTTLE_RPS"])  # type: ignore[arg-type]
        if env_values.get("STATE_DIR"):
            raw["state_dir"] = Path(env_values["STATE_DIR"]).expanduser()  # type: ignore[arg-type]
        if env_values.get("MAPPINGS_DIR"):
            raw["mappings_dir"] = Path(env_values["MAPPINGS_DIR"]).expanduser()  # type: ignore[arg-type]
        if env_values.get("OBFUSCATION_RULES_PATH"):
            raw["obfuscation_rules_path"] = Path(env_values["OBFUSCATION_RULES_PATH"])  # type: ignore[arg-type]
        if env_values.get("REPLACEMENTS_PATH"):
            raw["replacements_path"] = Path(env_values["REPLACEMENTS_PATH"])  # type: ignore[arg-type]
        if env_values.get("MONGO_MAX_RETRIES"):
            raw["mongo_max_retries"] = int(env_values["MONGO_MAX_RETRIES"])  # type: ignore[arg-type]
        if env_values.get("MONGO_RETRY_BACKOFF_BASE"):
            raw["mongo_retry_backoff_base"] = float(env_values["MONGO_RETRY_BACKOFF_BASE"])  # type: ignore[arg-type]
        if env_values.get("LANGUAGE"):
            raw["language"] = env_values["LANGUAGE"]  # type: ignore[arg-type]
        settings = Settings.model_validate(raw)
        _i18n.setup(settings.language)
        return settings

    def save_settings(self, settings: Settings) -> None:
        lines = [
            f"BATCH_SIZE={settings.batch_size}",
            f"THROTTLE_RPS={settings.throttle_rps}",
            f"STATE_DIR={settings.state_dir}",
            f"MAPPINGS_DIR={settings.mappings_dir}",
            f"OBFUSCATION_RULES_PATH={settings.obfuscation_rules_path}",
            f"REPLACEMENTS_PATH={settings.replacements_path}",
            f"MONGO_MAX_RETRIES={settings.mongo_max_retries}",
            f"MONGO_RETRY_BACKOFF_BASE={settings.mongo_retry_backoff_base}",
            f"LANGUAGE={settings.language}",
        ]
        self._settings_path.write_text("\n".join(lines) + "\n")

    def get_profile(self, alias: str) -> ConnectionProfile:
        from db_tool.i18n import t
        profiles = self.load_profiles()
        for p in profiles:
            if p.alias == alias:
                return p
        available = ", ".join(p.alias for p in profiles)
        raise ConfigError(t("config.error.connection_not_found", alias=alias, available=available))

    def add_profile(self, profile: ConnectionProfile) -> None:
        from db_tool.i18n import t
        profiles = self.load_profiles() if self._connections_path.exists() else []
        if any(p.alias == profile.alias for p in profiles):
            raise ConfigError(t("config.error.connection_already_exists", alias=profile.alias))
        profiles.append(profile)
        self._save_profiles(profiles)

    def remove_profile(self, alias: str) -> None:
        profiles = self.load_profiles()
        profile = self.get_profile(alias)
        from db_tool.config.validator import guard_connection_mutation
        guard_connection_mutation(profile)
        self._save_profiles([p for p in profiles if p.alias != alias])

    def update_profile(self, alias: str, updated: ConnectionProfile) -> None:
        profiles = self.load_profiles()
        profile = self.get_profile(alias)
        from db_tool.config.validator import guard_connection_mutation
        guard_connection_mutation(profile)
        self._save_profiles([updated if p.alias == alias else p for p in profiles])

    def _save_profiles(self, profiles: list[ConnectionProfile]) -> None:
        data = [p.model_dump() for p in profiles]
        for item in data:
            item["environment"] = item["environment"].value if hasattr(item["environment"], "value") else item["environment"]
            item["type"] = item["type"].value if hasattr(item["type"], "value") else item["type"]
        self._connections_path.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True))
