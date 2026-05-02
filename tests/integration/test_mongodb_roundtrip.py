"""
Integration test: full copy + sync roundtrip with a real MongoDB instance.
Run: MONGO_URI_TEST=mongodb://localhost:27017/test pytest -m integration
"""
from __future__ import annotations

import pytest

from db_tool.config.models import ConnectionProfile, ConnectorType, Environment, Settings
from db_tool.connectors.mongodb import MongoDBConnector
from db_tool.operations.copy import run_copy
from db_tool.operations.sync import run_sync


@pytest.fixture(scope="module")
def mongo_settings():
    import tempfile
    tmp = tempfile.mkdtemp()
    from pathlib import Path
    return Settings(
        state_dir=Path(tmp) / "state",
        mappings_dir=Path(tmp) / "mappings",
        batch_size=50,
    )


@pytest.fixture(scope="module")
def source_profile(mongo_uri):
    return ConnectionProfile(
        alias="test-source",
        environment=Environment.DEV,
        type=ConnectorType.MONGODB,
        connection_string=mongo_uri,
    )


@pytest.fixture(scope="module")
def target_profile(mongo_uri):
    return ConnectionProfile(
        alias="test-target",
        environment=Environment.LOCAL,
        type=ConnectorType.MONGODB,
        connection_string=mongo_uri,
    )


@pytest.mark.integration
def test_copy_and_sync_roundtrip(source_profile, target_profile, mongo_settings):
    from datetime import datetime, timezone

    with MongoDBConnector(source_profile, mongo_settings) as src:
        # Clean up test collections
        src._db["it_col_source"].drop()
        src._db["it_col_target"].drop()

        # Seed source
        docs = [{"_id": str(i), "value": i, "updatedAt": datetime(2024, 1, 1, tzinfo=timezone.utc)} for i in range(10)]
        src._db["it_col_source"].insert_many(docs)

    with MongoDBConnector(source_profile, mongo_settings) as src, \
         MongoDBConnector(target_profile, mongo_settings) as tgt:

        result = run_copy(src, tgt, "it_col_source", mongo_settings)
        assert result.total_upserted == 10

        # Sync: no changes → all skipped
        sync_result = run_sync(src, tgt, "it_col_source", mongo_settings)
        assert sync_result.total_skipped == 10
        assert sync_result.total_upserted == 0

    # Update one doc in source
    with MongoDBConnector(source_profile, mongo_settings) as src:
        src._db["it_col_source"].update_one(
            {"_id": "0"},
            {"$set": {"value": 999, "updatedAt": datetime(2025, 1, 1, tzinfo=timezone.utc)}}
        )

    with MongoDBConnector(source_profile, mongo_settings) as src, \
         MongoDBConnector(target_profile, mongo_settings) as tgt:
        sync_result = run_sync(src, tgt, "it_col_source", mongo_settings)
        assert sync_result.total_upserted + sync_result.total_modified == 1

    # Cleanup
    with MongoDBConnector(source_profile, mongo_settings) as src:
        src._db["it_col_source"].drop()


@pytest.mark.integration
def test_obfuscation_e2e(source_profile, target_profile, mongo_settings):
    from db_tool.obfuscation.engine import ObfuscationEngine

    with MongoDBConnector(source_profile, mongo_settings) as src:
        src._db["it_obf_test"].drop()
        src._db["it_obf_test"].insert_many([
            {"_id": str(i), "email": f"user{i}@real.com", "name": f"Real Name {i}"}
            for i in range(5)
        ])

    engine = ObfuscationEngine(mongo_settings, seed=42)

    with MongoDBConnector(source_profile, mongo_settings) as src, \
         MongoDBConnector(target_profile, mongo_settings) as tgt:
        tgt._db["it_obf_target"].drop()
        run_copy(src, tgt, "it_obf_test", mongo_settings, obfuscation_engine=engine)

    with MongoDBConnector(target_profile, mongo_settings) as tgt:
        docs = list(tgt._db["it_obf_target"].find())
        for doc in docs:
            assert "real.com" not in doc.get("email", ""), "Real email found in target"
            assert "Real Name" not in doc.get("name", ""), "Real name found in target"

    # Cleanup
    with MongoDBConnector(source_profile, mongo_settings) as src:
        src._db["it_obf_test"].drop()
        src._db["it_obf_target"].drop()
