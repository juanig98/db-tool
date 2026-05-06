from __future__ import annotations

import pytest

from db_tool.config.models import Environment
from db_tool.config.validator import ProductionWriteError
from db_tool.operations.copy import run_copy
from tests.conftest import FakeConnector


def test_copy_all_docs(source_connector, target_connector, settings):
    source_connector.seed("users", [{"_id": i, "name": f"user{i}"} for i in range(5)])
    result = run_copy(source_connector, target_connector, "users", settings)
    assert result.total_upserted == 5
    assert len(target_connector._store["users"]) == 5


def test_copy_pattern_filters_collections(source_connector, target_connector, settings):
    source_connector.seed("mydblocal-users", [{"_id": 1}])
    source_connector.seed("mydblocal-orders", [{"_id": 2}])
    source_connector.seed("unrelated", [{"_id": 3}])
    result = run_copy(source_connector, target_connector, r"mydblocal-.*", settings)
    assert len(result.collections) == 2
    assert "unrelated" not in target_connector._store


def test_copy_dry_run_does_not_write(source_connector, target_connector, settings):
    source_connector.seed("users", [{"_id": 1}])
    result = run_copy(source_connector, target_connector, "users", settings, dry_run=True)
    assert "users" not in target_connector._store
    assert result.total_upserted == 0


def test_copy_blocked_on_production_target(source_connector, settings):
    from db_tool.config.models import ConnectionProfile, ConnectorType
    prod_target = FakeConnector(
        ConnectionProfile(
            alias="prod-tgt",
            environment=Environment.PRODUCTION,
            type=ConnectorType.MONGODB,
            connection_string="mongodb://prod",
            database_name="db",
        ),
        settings,
    )
    prod_target.connect()
    source_connector.seed("users", [{"_id": 1}])
    with pytest.raises(ProductionWriteError):
        run_copy(source_connector, prod_target, "users", settings)


def test_copy_resume_skips_completed_collection(source_connector, target_connector, settings):
    from db_tool.state.manager import StateManager
    source_connector.seed("users", [{"_id": i} for i in range(3)])
    sm = StateManager(settings)
    sm.mark_collection_complete(source_connector.profile.alias, target_connector.profile.alias, "users")

    result = run_copy(source_connector, target_connector, "users", settings, resume=True)
    assert result.total_upserted == 0
    assert result.total_skipped > 0


def test_copy_with_obfuscation(source_connector, target_connector, settings):
    source_connector.seed("users", [{"_id": 1, "email": "real@example.com"}])

    class MockEngine:
        def transform(self, doc, collection=None):
            return {**doc, "email": "fake@fake.com"}

        def transform_collection_name(self, name):
            return name

    result = run_copy(source_connector, target_connector, "users", settings, obfuscation_engine=MockEngine())
    assert target_connector._store["users"][0]["email"] == "fake@fake.com"


def test_copy_max_docs_per_collection(source_connector, target_connector, settings):
    source_connector.seed("users", [{"_id": i} for i in range(10)])
    result = run_copy(source_connector, target_connector, "users", settings, max_docs_per_collection=3)
    assert len(target_connector._store["users"]) == 3


def test_copy_blacklisted_collections_ignored(source_connector, target_connector, settings):
    source_connector.seed("tmp_cache", [{"_id": 1}])
    source_connector.seed("users", [{"_id": 2}])
    # prod_profile has blacklist: ["^tmp_.*"]
    result = run_copy(source_connector, target_connector, r".*", settings)
    assert "tmp_cache" not in target_connector._store
    assert "users" in target_connector._store


def test_copy_progress_callback_called(source_connector, target_connector, settings):
    source_connector.seed("users", [{"_id": i} for i in range(3)])
    events = []
    run_copy(source_connector, target_connector, "users", settings, progress_callback=events.append)
    assert len(events) > 0
    phases = {e.phase for e in events}
    assert "complete" in phases


def test_copy_indexes_called_when_not_data_only(source_connector, target_connector, settings):
    source_connector.seed("users", [{"_id": 1}])
    source_connector._indexes["users"] = [{"key": [("name", 1)]}]
    run_copy(source_connector, target_connector, "users", settings, data_only=False)
    assert len(target_connector._indexes.get("users", [])) == 1


def test_copy_indexes_skipped_when_data_only(source_connector, target_connector, settings):
    source_connector.seed("users", [{"_id": 1}])
    source_connector._indexes["users"] = [{"key": [("name", 1)]}]
    run_copy(source_connector, target_connector, "users", settings, data_only=True)
    assert len(target_connector._indexes.get("users", [])) == 0
