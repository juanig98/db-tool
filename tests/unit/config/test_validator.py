import pytest

from db_tool.config.models import ConnectionProfile, ConnectorType, Environment
from db_tool.config.validator import (
    ProductionMutationError,
    ProductionWriteError,
    filter_blacklist,
    guard_connection_mutation,
    guard_write,
    requires_stage_confirmation,
)


def make_profile(env: Environment) -> ConnectionProfile:
    return ConnectionProfile(
        alias="test",
        environment=env,
        type=ConnectorType.MONGODB,
        connection_string="mongodb://host",
        database_name="db",
        blacklist=["^tmp_.*", "^audit_.*"],
    )


def test_guard_write_production_raises():
    with pytest.raises(ProductionWriteError):
        guard_write(make_profile(Environment.PRODUCTION))


@pytest.mark.parametrize("env", [Environment.STAGE, Environment.DEV, Environment.LOCAL])
def test_guard_write_non_production_passes(env):
    guard_write(make_profile(env))  # must not raise


def test_guard_connection_mutation_production_raises():
    with pytest.raises(ProductionMutationError):
        guard_connection_mutation(make_profile(Environment.PRODUCTION))


def test_guard_connection_mutation_non_production_passes():
    guard_connection_mutation(make_profile(Environment.DEV))  # must not raise


def test_requires_stage_confirmation_true():
    assert requires_stage_confirmation(make_profile(Environment.STAGE))


def test_requires_stage_confirmation_false():
    assert not requires_stage_confirmation(make_profile(Environment.DEV))


def test_filter_blacklist_removes_matches():
    profile = make_profile(Environment.DEV)
    names = ["users", "tmp_cache", "audit_log", "orders"]
    result = filter_blacklist(profile, names)
    assert result == ["users", "orders"]


def test_filter_blacklist_no_patterns():
    profile = ConnectionProfile(
        alias="test",
        environment=Environment.DEV,
        type=ConnectorType.MONGODB,
        connection_string="mongodb://host",
        database_name="db",
        blacklist=[],
    )
    names = ["a", "b", "tmp_x"]
    assert filter_blacklist(profile, names) == names
