from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from db_tool.config.models import ConnectionProfile, ConnectorType, Environment, Settings
from db_tool.config.validator import ProductionWriteError
from db_tool.connectors.mongodb import MongoDBConnector


@pytest.fixture
def dev_profile():
    return ConnectionProfile(
        alias="dev",
        environment=Environment.DEV,
        type=ConnectorType.MONGODB,
        connection_string="mongodb://localhost:27017",
        database_name="testdb",
    )


@pytest.fixture
def prod_profile():
    return ConnectionProfile(
        alias="prod",
        environment=Environment.PRODUCTION,
        type=ConnectorType.MONGODB,
        connection_string="mongodb://prod:27017",
        database_name="proddb",
    )


@pytest.fixture
def settings():
    return Settings(mongo_max_retries=3, mongo_retry_backoff_base=1.0)



def test_upsert_batch_blocked_on_production(prod_profile, settings):
    connector = MongoDBConnector(prod_profile, settings)
    connector._db = MagicMock()
    with pytest.raises(ProductionWriteError):
        connector.upsert_batch("col", [{"_id": 1, "name": "test"}])


def test_upsert_batch_success(dev_profile, settings):
    connector = MongoDBConnector(dev_profile, settings)
    mock_db = MagicMock()
    mock_result = MagicMock()
    mock_result.upserted_count = 2
    mock_result.modified_count = 1
    mock_db["col"].bulk_write.return_value = mock_result
    connector._db = mock_db

    upserted, modified = connector.upsert_batch("col", [
        {"_id": 1, "x": "a"},
        {"_id": 2, "x": "b"},
        {"_id": 3, "x": "c"},
    ])
    assert upserted == 2
    assert modified == 1
    mock_db["col"].bulk_write.assert_called_once()


def test_upsert_batch_handles_bulk_write_error(dev_profile, settings):
    from pymongo.errors import BulkWriteError

    connector = MongoDBConnector(dev_profile, settings)
    mock_db = MagicMock()
    mock_db["col"].bulk_write.side_effect = BulkWriteError(
        {"upserted": [1], "nModified": 0, "writeErrors": []}
    )
    connector._db = mock_db

    upserted, modified = connector.upsert_batch("col", [{"_id": 1, "x": "a"}])
    assert upserted == 1
    assert modified == 0


def test_delete_collection_blocked_on_production(prod_profile, settings):
    connector = MongoDBConnector(prod_profile, settings)
    connector._db = MagicMock()
    with pytest.raises(ProductionWriteError):
        connector.delete_collection("users")


def test_throttle_called_between_batches(dev_profile, settings):
    settings = Settings(throttle_rps=10.0)
    connector = MongoDBConnector(dev_profile, settings)
    mock_db = MagicMock()
    # 3 docs, batch_size=2 → 2 batches
    fake_cursor = MagicMock()
    fake_cursor.max_time_ms.return_value = iter([
        {"_id": 1}, {"_id": 2}, {"_id": 3}
    ])
    mock_db["col"].find.return_value = fake_cursor
    connector._db = mock_db

    with patch("time.sleep") as mock_sleep:
        batches = list(connector.iter_documents("col", batch_size=2))

    assert len(batches) == 2
    # sleep called once between batches (after first full batch)
    assert mock_sleep.call_count == 1
    mock_sleep.assert_called_with(pytest.approx(0.1, abs=1e-3))


def test_retry_on_429(dev_profile, settings):
    from pymongo.errors import OperationFailure

    settings = Settings(mongo_max_retries=3, mongo_retry_backoff_base=1.0)
    connector = MongoDBConnector(dev_profile, settings)
    call_count = 0

    def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise OperationFailure("too many requests", code=16500)
        return "ok"

    with patch("time.sleep"):
        result = connector._with_retry(flaky)

    assert result == "ok"
    assert call_count == 3


def test_retry_exhausted_raises(dev_profile, settings):
    from pymongo.errors import OperationFailure

    settings = Settings(mongo_max_retries=2, mongo_retry_backoff_base=1.0)
    connector = MongoDBConnector(dev_profile, settings)

    def always_fails():
        raise OperationFailure("too many requests", code=16500)

    with patch("time.sleep"):
        with pytest.raises(OperationFailure):
            connector._with_retry(always_fails)
