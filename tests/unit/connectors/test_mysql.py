from __future__ import annotations

import json
from unittest.mock import MagicMock, call

import pytest

from db_tool.config.models import ConnectionProfile, ConnectorType, Environment, Settings
from db_tool.config.validator import ProductionWriteError
from db_tool.connectors.mysql import MySQLConnector


@pytest.fixture
def dev_profile():
    return ConnectionProfile(
        alias="dev-mysql",
        environment=Environment.DEV,
        type=ConnectorType.MYSQL,
        connection_string="mysql://root:pass@localhost:3306",
        database_name="testdb",
    )


@pytest.fixture
def prod_profile():
    return ConnectionProfile(
        alias="prod-mysql",
        environment=Environment.PRODUCTION,
        type=ConnectorType.MYSQL,
        connection_string="mysql://root:pass@prod:3306",
        database_name="proddb",
    )


@pytest.fixture
def settings():
    return Settings()


def test_parse_uri():
    params = MySQLConnector._parse_uri("mysql://user:pass@host:3307/mydb")
    assert params["host"] == "host"
    assert params["port"] == 3307
    assert params["user"] == "user"
    assert params["password"] == "pass"
    assert params["database"] == "mydb"


def test_serialize_doc_flattens_nested():
    connector = MySQLConnector.__new__(MySQLConnector)
    doc = {"_id": "1", "data": {"x": 1}, "tags": [1, 2], "name": "test"}
    result = connector._serialize_doc(doc)
    assert result["name"] == "test"
    assert isinstance(result["data"], str)
    assert json.loads(result["data"]) == {"x": 1}
    assert isinstance(result["tags"], str)


def test_deserialize_row_parses_json():
    connector = MySQLConnector.__new__(MySQLConnector)
    row = {"_id": "1", "data": '{"x": 1}', "tags": "[1, 2]", "name": "test"}
    result = connector._deserialize_row(row)
    assert result["data"] == {"x": 1}
    assert result["tags"] == [1, 2]
    assert result["name"] == "test"


def test_upsert_blocked_on_production(prod_profile, settings):
    connector = MySQLConnector(prod_profile, settings)
    connector._conn = MagicMock()
    with pytest.raises(ProductionWriteError):
        connector.upsert_batch("users", [{"_id": "1"}])


def test_delete_blocked_on_production(prod_profile, settings):
    connector = MySQLConnector(prod_profile, settings)
    connector._conn = MagicMock()
    with pytest.raises(ProductionWriteError):
        connector.delete_collection("users")


def test_copy_indexes_returns_zero(dev_profile, settings):
    connector = MySQLConnector(dev_profile, settings)
    assert connector.copy_indexes(MagicMock(), "users") == 0
