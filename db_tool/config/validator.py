from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from db_tool.config.models import ConnectionProfile, Environment


class ProductionWriteError(Exception):
    """Raised when attempting a write operation on a production connection."""


class ProductionMutationError(Exception):
    """Raised when attempting to modify/delete a production connection config."""


ENVIRONMENT_SIGNALS: dict[Environment, list[str]] = {
    Environment.PRODUCTION: ["prod", "prd", "live", "master"],
    Environment.STAGE:      ["stage", "staging", "stg", "preprod", "pre-prod"],
    Environment.DEV:        ["dev", "develop", "development"],
    Environment.LOCAL:      ["local", "localhost", "127.0.0.1", "::1"],
}


@dataclass
class ConnectionStringWarning:
    alias: str
    declared_env: Environment
    detected_env: Environment
    matched_keyword: str
    severity: Literal["high", "medium"]


def check_connection_string_signals(
    profiles: list[ConnectionProfile],
) -> list[ConnectionStringWarning]:
    warnings: list[ConnectionStringWarning] = []
    for profile in profiles:
        cs_lower = profile.connection_string.lower()
        for env, keywords in ENVIRONMENT_SIGNALS.items():
            if env == profile.environment:
                continue
            for keyword in keywords:
                if keyword in cs_lower:
                    severity: Literal["high", "medium"] = (
                        "high"
                        if env == Environment.PRODUCTION
                        and profile.environment != Environment.PRODUCTION
                        else "medium"
                    )
                    warnings.append(ConnectionStringWarning(
                        alias=profile.alias,
                        declared_env=profile.environment,
                        detected_env=env,
                        matched_keyword=keyword,
                        severity=severity,
                    ))
                    break
    return warnings


def guard_write(profile: ConnectionProfile) -> None:
    """Raise if writing to this profile is not allowed."""
    from db_tool.i18n import t
    if profile.is_production:
        raise ProductionWriteError(t("validator.error.production_write", alias=profile.alias))


def guard_connection_mutation(profile: ConnectionProfile) -> None:
    """Raise if modifying/deleting this connection profile config is not allowed."""
    from db_tool.i18n import t
    if profile.is_production:
        raise ProductionMutationError(t("validator.error.production_mutation", alias=profile.alias))


def requires_stage_confirmation(profile: ConnectionProfile) -> bool:
    """Return True if the operation requires confirmation (stage environment)."""
    return profile.is_stage


def filter_blacklist(profile: ConnectionProfile, names: list[str]) -> list[str]:
    """Return names not matched by any blacklist pattern in the profile."""
    if not profile.blacklist:
        return names
    compiled = [re.compile(pattern) for pattern in profile.blacklist]
    return [
        name for name in names
        if not any(pattern.search(name) for pattern in compiled)
    ]
