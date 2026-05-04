from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, field_validator


class Environment(str, Enum):
    PRODUCTION = "production"
    STAGE = "stage"
    DEV = "dev"
    LOCAL = "local"


class ConnectorType(str, Enum):
    MONGODB = "mongodb"
    BIGQUERY = "bigquery"
    MYSQL = "mysql"


class ConnectionProfile(BaseModel):
    alias: str
    environment: Environment
    type: ConnectorType
    connection_string: str
    database_name: str
    blacklist: list[str] = []

    @field_validator("alias")
    @classmethod
    def alias_not_empty(cls, v: str) -> str:
        from db_tool.i18n import t
        if not v.strip():
            raise ValueError(t("config.model.error.alias_empty"))
        return v

    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION

    @property
    def is_stage(self) -> bool:
        return self.environment == Environment.STAGE

    @property
    def is_writable(self) -> bool:
        return self.environment != Environment.PRODUCTION


class Settings(BaseModel):
    batch_size: int = 1000
    throttle_rps: float = 0.0
    state_dir: Path = Path("~/.db-tool/state").expanduser()
    mappings_dir: Path = Path("~/.db-tool/mappings").expanduser()
    obfuscation_rules_path: Path = Path("./config/obfuscation_rules.txt")
    replacements_path: Path = Path("./config/replacement_rules.txt")
    mongo_max_retries: int = 5
    mongo_retry_backoff_base: float = 2.0

    language: str = "en"

    @field_validator("batch_size")
    @classmethod
    def batch_size_positive(cls, v: int) -> int:
        from db_tool.i18n import t
        if v < 1:
            raise ValueError(t("config.model.error.batch_size_min"))
        return v

    @field_validator("throttle_rps")
    @classmethod
    def throttle_non_negative(cls, v: float) -> float:
        from db_tool.i18n import t
        if v < 0:
            raise ValueError(t("config.model.error.throttle_min"))
        return v

    @field_validator("language")
    @classmethod
    def language_valid(cls, v: str) -> str:
        from db_tool.i18n import t
        if v not in ("en", "es"):
            raise ValueError(t("config.model.error.language_invalid"))
        return v
