import pytest
from pydantic import ValidationError

from db_tool.config.models import ConnectionProfile, ConnectorType, Environment, Settings


def test_connection_profile_production_is_not_writable():
    p = ConnectionProfile(
        alias="prod",
        environment=Environment.PRODUCTION,
        type=ConnectorType.MONGODB,
        connection_string="mongodb://host",
        database_name="db",
    )
    assert p.is_production
    assert not p.is_writable


def test_connection_profile_dev_is_writable():
    p = ConnectionProfile(
        alias="dev",
        environment=Environment.DEV,
        type=ConnectorType.MONGODB,
        connection_string="mongodb://host",
        database_name="db",
    )
    assert not p.is_production
    assert p.is_writable


def test_connection_profile_empty_alias_raises():
    with pytest.raises(ValidationError):
        ConnectionProfile(
            alias="   ",
            environment=Environment.DEV,
            type=ConnectorType.MONGODB,
            connection_string="mongodb://host",
        database_name="db",
        )


def test_allow_prod_writes_defaults_to_false():
    p = ConnectionProfile(
        alias="dev",
        environment=Environment.DEV,
        type=ConnectorType.MONGODB,
        connection_string="mongodb://host",
        database_name="db",
    )
    assert p.allow_prod_writes is False


def test_allow_prod_writes_can_be_set():
    p = ConnectionProfile(
        alias="dev",
        environment=Environment.DEV,
        type=ConnectorType.MONGODB,
        connection_string="mongodb://host",
        database_name="db",
        allow_prod_writes=True,
    )
    assert p.allow_prod_writes is True


def test_settings_defaults():
    s = Settings()
    assert s.batch_size == 1000
    assert s.throttle_rps == 0.0
    assert s.mongo_max_retries == 5


def test_settings_invalid_batch_size():
    with pytest.raises(ValidationError):
        Settings(batch_size=0)


def test_settings_invalid_throttle():
    with pytest.raises(ValidationError):
        Settings(throttle_rps=-1.0)
