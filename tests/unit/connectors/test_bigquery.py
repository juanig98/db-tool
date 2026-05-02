from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from db_tool.config.models import ConnectionProfile, ConnectorType, Environment, Settings
from db_tool.config.validator import ProductionWriteError
from db_tool.connectors.bigquery import BigQueryConnector


@pytest.fixture
def dev_profile():
    return ConnectionProfile(
        alias="dev-bq",
        environment=Environment.DEV,
        type=ConnectorType.BIGQUERY,
        connection_string="bigquery://my-project",
        database_name="my-dataset",
    )


@pytest.fixture
def prod_profile():
    return ConnectionProfile(
        alias="prod-bq",
        environment=Environment.PRODUCTION,
        type=ConnectorType.BIGQUERY,
        connection_string="bigquery://my-project",
        database_name="prod-dataset",
    )


@pytest.fixture
def settings():
    return Settings()


def test_parse_uri_valid():
    project, dataset = BigQueryConnector._parse_uri("bigquery://my-project/my-dataset")
    assert project == "my-project"
    assert dataset == "my-dataset"


def test_parse_uri_invalid():
    with pytest.raises(ValueError, match="Invalid BigQuery URI"):
        BigQueryConnector._parse_uri("bigquery:///missing-project")


def test_flatten_doc_serializes_nested():
    connector = BigQueryConnector.__new__(BigQueryConnector)
    doc = {"_id": "1", "data": {"nested": True}, "tags": [1, 2, 3], "name": "test"}
    flat = connector._flatten_doc(doc)
    assert flat["name"] == "test"
    assert isinstance(flat["data"], str)
    assert json.loads(flat["data"]) == {"nested": True}
    assert isinstance(flat["tags"], str)
    assert json.loads(flat["tags"]) == [1, 2, 3]


def test_upsert_blocked_on_production(prod_profile, settings):
    connector = BigQueryConnector(prod_profile, settings)
    connector._client = MagicMock()
    with pytest.raises(ProductionWriteError):
        connector.upsert_batch("my_table", [{"_id": "1", "val": "x"}])


def test_delete_collection_blocked_on_production(prod_profile, settings):
    connector = BigQueryConnector(prod_profile, settings)
    connector._client = MagicMock()
    with pytest.raises(ProductionWriteError):
        connector.delete_collection("my_table")


def test_list_collections(dev_profile, settings):
    connector = BigQueryConnector(dev_profile, settings)
    mock_client = MagicMock()
    mock_client.dataset.return_value = MagicMock()
    table_a = MagicMock()
    table_a.table_id = "table_a"
    table_b = MagicMock()
    table_b.table_id = "table_b"
    mock_client.list_tables.return_value = [table_b, table_a]
    connector._client = mock_client
    connector._dataset = "my-dataset"
    assert connector.list_collections() == ["table_a", "table_b"]


def test_upsert_batch_success(dev_profile, settings):
    connector = BigQueryConnector(dev_profile, settings)
    mock_client = MagicMock()
    mock_client.insert_rows_json.return_value = []
    connector._client = mock_client
    connector._project = "my-project"
    connector._dataset = "my-dataset"

    upserted, modified = connector.upsert_batch("users", [{"_id": "1", "name": "test"}])
    assert upserted == 1
    assert modified == 0
    mock_client.insert_rows_json.assert_called_once()


def test_upsert_batch_raises_on_errors(dev_profile, settings):
    connector = BigQueryConnector(dev_profile, settings)
    mock_client = MagicMock()
    mock_client.insert_rows_json.return_value = [{"errors": "some error"}]
    connector._client = mock_client
    connector._project = "p"
    connector._dataset = "d"

    with pytest.raises(RuntimeError, match="BigQuery insert errors"):
        connector.upsert_batch("users", [{"_id": "1"}])
