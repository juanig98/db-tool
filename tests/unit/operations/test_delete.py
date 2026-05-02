from __future__ import annotations

import pytest

from db_tool.config.models import ConnectionProfile, ConnectorType, Environment
from db_tool.config.validator import ProductionWriteError
from db_tool.operations.delete import run_delete
from tests.conftest import FakeConnector


def test_delete_matching_collections(target_connector, settings):
    target_connector.seed("mydblocal-users", [{"_id": 1}])
    target_connector.seed("mydblocal-orders", [{"_id": 2}])
    target_connector.seed("other", [{"_id": 3}])
    result = run_delete(target_connector, r"mydblocal-.*", settings)
    assert len(result.collections) == 2
    assert "mydblocal-users" not in target_connector._store
    assert "other" in target_connector._store


def test_delete_dry_run_does_not_delete(target_connector, settings):
    target_connector.seed("users", [{"_id": 1}])
    result = run_delete(target_connector, "users", settings, dry_run=True)
    assert "users" in target_connector._store
    assert result.collections[0].skipped == 1


def test_delete_blocked_on_production(settings):
    prod = FakeConnector(
        ConnectionProfile(
            alias="prod",
            environment=Environment.PRODUCTION,
            type=ConnectorType.MONGODB,
            connection_string="mongodb://prod",
            database_name="db",
        ),
        settings,
    )
    prod.connect()
    prod.seed("users", [{"_id": 1}])
    with pytest.raises(ProductionWriteError):
        run_delete(prod, "users", settings)


def test_delete_no_matching_collections(target_connector, settings):
    target_connector.seed("users", [{"_id": 1}])
    result = run_delete(target_connector, r"^nonexistent$", settings)
    assert len(result.collections) == 0
    assert "users" in target_connector._store


def test_delete_progress_callback(target_connector, settings):
    target_connector.seed("users", [{"_id": 1}])
    events = []
    run_delete(target_connector, "users", settings, progress_callback=events.append)
    assert len(events) == 1
    assert events[0].phase == "complete"
