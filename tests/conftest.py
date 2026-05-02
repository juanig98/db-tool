from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from db_tool.config.models import (
    ConnectionProfile,
    ConnectorType,
    Environment,
    Settings,
)
from db_tool.connectors.base import AbstractConnector


class FakeConnector(AbstractConnector):
    """In-memory connector for unit tests."""

    def __init__(self, profile: ConnectionProfile, settings: Settings) -> None:
        super().__init__(profile, settings)
        self._store: dict[str, list[dict[str, Any]]] = {}
        self._indexes: dict[str, list[Any]] = {}
        self.connected = False

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def list_collections(self) -> list[str]:
        return sorted(self._store.keys())

    def estimated_count(self, collection: str) -> int:
        return len(self._store.get(collection, []))

    def iter_documents(
        self, collection: str, batch_size: int
    ) -> Iterator[list[dict[str, Any]]]:
        docs = list(self._store.get(collection, []))
        for i in range(0, max(len(docs), 1), batch_size):
            chunk = docs[i : i + batch_size]
            if chunk:
                yield chunk

    def upsert_batch(
        self, collection: str, docs: list[dict[str, Any]]
    ) -> tuple[int, int]:
        self.assert_write_allowed()
        existing = {d["_id"]: d for d in self._store.get(collection, [])}
        upserted = 0
        modified = 0
        for doc in docs:
            if doc["_id"] in existing:
                existing[doc["_id"]] = doc
                modified += 1
            else:
                existing[doc["_id"]] = doc
                upserted += 1
        self._store[collection] = list(existing.values())
        return upserted, modified

    def delete_collection(self, collection: str) -> None:
        self.assert_write_allowed()
        self._store.pop(collection, None)

    def copy_indexes(self, source: AbstractConnector, collection: str) -> int:
        if not isinstance(source, FakeConnector):
            return 0
        src_indexes = source._indexes.get(collection, [])
        self._indexes[collection] = list(src_indexes)
        return len(src_indexes)

    def collection_exists(self, collection: str) -> bool:
        return collection in self._store

    def get_document(self, collection: str, doc_id: Any) -> dict[str, Any] | None:
        for doc in self._store.get(collection, []):
            if doc["_id"] == doc_id:
                return doc
        return None

    def get_documents_by_ids(
        self, collection: str, doc_ids: list[Any]
    ) -> dict[Any, dict[str, Any]]:
        id_set = set(doc_ids)
        return {doc["_id"]: doc for doc in self._store.get(collection, []) if doc["_id"] in id_set}

    def seed(self, collection: str, docs: list[dict[str, Any]]) -> None:
        """Helper to pre-populate data for tests."""
        self._store[collection] = list(docs)

    def clear(self) -> None:
        """Clear all data."""
        self._store.clear()
        self._indexes.clear()


@pytest.fixture
def settings(tmp_path: Any) -> Settings:
    return Settings(
        state_dir=tmp_path / "state",
        mappings_dir=tmp_path / "mappings",
        obfuscation_rules_path=tmp_path / "obfuscation_rules.txt",
    )


@pytest.fixture
def prod_profile() -> ConnectionProfile:
    return ConnectionProfile(
        alias="prod-db",
        environment=Environment.PRODUCTION,
        type=ConnectorType.MONGODB,
        connection_string="mongodb://prod:27017",
        database_name="proddb",
        blacklist=["^tmp_.*"],
    )


@pytest.fixture
def dev_profile() -> ConnectionProfile:
    return ConnectionProfile(
        alias="dev-db",
        environment=Environment.DEV,
        type=ConnectorType.MONGODB,
        connection_string="mongodb://localhost:27017",
        database_name="devdb",
        blacklist=[],
    )


@pytest.fixture
def source_connector(prod_profile: ConnectionProfile, settings: Settings) -> FakeConnector:
    c = FakeConnector(prod_profile, settings)
    c.connect()
    return c


@pytest.fixture
def target_connector(dev_profile: ConnectionProfile, settings: Settings) -> FakeConnector:
    c = FakeConnector(dev_profile, settings)
    c.connect()
    return c


@pytest.fixture(autouse=True)
def _cleanup_connectors(source_connector: FakeConnector, target_connector: FakeConnector) -> None:
    """Clear connectors before each test."""
    source_connector.clear()
    target_connector.clear()
