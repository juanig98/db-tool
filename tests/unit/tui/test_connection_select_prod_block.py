from __future__ import annotations

import pytest
from db_tool.config.models import ConnectionProfile, ConnectorType, Environment
from db_tool.config.validator import check_connection_string_signals


def _make_profile(alias: str, connection_string: str, allow_prod_writes: bool = False) -> ConnectionProfile:
    return ConnectionProfile(
        alias=alias,
        environment=Environment.DEV,
        type=ConnectorType.MONGODB,
        connection_string=connection_string,
        database_name="db",
        allow_prod_writes=allow_prod_writes,
    )


def _would_block(profile: ConnectionProfile) -> bool:
    """Replicates the block logic from ConnectionSelectScreen."""
    if profile.allow_prod_writes:
        return False
    high = [w for w in check_connection_string_signals([profile]) if w.severity == "high"]
    return bool(high)


def test_prod_signal_in_connection_string_blocks():
    profile = _make_profile("dev-wrong", "mongodb://user:pass@prod-host:27017/mydb")
    assert _would_block(profile)


def test_no_prod_signal_does_not_block():
    profile = _make_profile("dev-ok", "mongodb://localhost:27017/mydb")
    assert not _would_block(profile)


def test_allow_prod_writes_bypasses_block():
    profile = _make_profile("dev-bypass", "mongodb://user:pass@prod-host:27017/mydb", allow_prod_writes=True)
    assert not _would_block(profile)


def test_prd_keyword_also_blocks():
    profile = _make_profile("dev-prd", "mongodb://user:pass@prd-db.internal:27017/mydb")
    assert not profile.allow_prod_writes
    assert _would_block(profile)
