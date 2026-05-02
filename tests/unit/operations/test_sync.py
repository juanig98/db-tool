from __future__ import annotations

from datetime import datetime, timezone

import pytest

from db_tool.operations.sync import _should_sync_ts, run_sync


def dt(year, month, day):
    return datetime(year, month, day, tzinfo=timezone.utc)


def test_should_sync_target_missing():
    assert _should_sync_ts({"_id": 1}, None) is True


def test_should_sync_source_newer():
    src = {"_id": 1, "updatedAt": dt(2024, 6, 1)}
    assert _should_sync_ts(src, dt(2024, 5, 1)) is True


def test_should_sync_source_older():
    src = {"_id": 1, "updatedAt": dt(2024, 4, 1)}
    assert _should_sync_ts(src, dt(2024, 5, 1)) is False


def test_should_sync_same_date():
    d = dt(2024, 6, 1)
    assert _should_sync_ts({"_id": 1, "updatedAt": d}, d) is False


def test_should_sync_missing_src_updated_at():
    assert _should_sync_ts({"_id": 1}, dt(2024, 1, 1)) is True


def test_should_sync_missing_tgt_updated_at():
    assert _should_sync_ts({"_id": 1, "updatedAt": dt(2024, 1, 1)}, None) is True


def test_sync_copies_new_docs(source_connector, target_connector, settings):
    source_connector.seed("users", [{"_id": i, "name": f"u{i}"} for i in range(3)])
    result = run_sync(source_connector, target_connector, "users", settings)
    assert result.total_upserted == 3


def test_sync_skips_unchanged_docs(source_connector, target_connector, settings):
    d = dt(2024, 1, 1)
    docs = [{"_id": i, "updatedAt": d} for i in range(3)]
    source_connector.seed("users", docs)
    target_connector.seed("users", docs)
    result = run_sync(source_connector, target_connector, "users", settings)
    assert result.total_upserted == 0
    assert result.total_skipped == 3


def test_sync_updates_stale_docs(source_connector, target_connector, settings):
    source_connector.seed("users", [
        {"_id": 1, "updatedAt": dt(2024, 6, 1), "name": "new"},
    ])
    target_connector.seed("users", [
        {"_id": 1, "updatedAt": dt(2024, 1, 1), "name": "old"},
    ])
    run_sync(source_connector, target_connector, "users", settings)
    assert target_connector._store["users"][0]["name"] == "new"


def test_sync_with_obfuscation(source_connector, target_connector, settings):
    source_connector.seed("users", [{"_id": 1, "email": "real@x.com"}])

    class MockEngine:
        def transform(self, doc):
            return {**doc, "email": "fake@fake.com"}

    run_sync(source_connector, target_connector, "users", settings, obfuscation_engine=MockEngine())
    assert target_connector._store["users"][0]["email"] == "fake@fake.com"
