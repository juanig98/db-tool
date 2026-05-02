from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from typing import Any

from db_tool.config.models import ConnectionProfile, Settings
from db_tool.connectors.base import AbstractConnector

_log = logging.getLogger("db_tool.connectors.mongodb")


class MongoDBConnector(AbstractConnector):
    def __init__(self, profile: ConnectionProfile, settings: Settings) -> None:
        super().__init__(profile, settings)
        self._client: Any = None
        self._db: Any = None

    def connect(self) -> None:
        from pymongo import MongoClient
        from pymongo.errors import ConnectionFailure

        _log.info(f"Connecting to MongoDB: {self.profile.alias}")
        uri = self.profile.connection_string
        self._client = MongoClient(
            uri,
            serverSelectionTimeoutMS=10_000,
            connectTimeoutMS=10_000,
            socketTimeoutMS=60_000,
        )
        try:
            self._client.admin.command("ping")
        except ConnectionFailure as exc:
            from db_tool.i18n import t
            raise ConnectionError(
                t("connector.mongodb.error.cannot_connect", alias=self.profile.alias, exc=exc)
            ) from exc
        self._db = self._client[self.profile.database_name]
        _log.info(f"Connected to MongoDB: {self.profile.alias}, database={self.profile.database_name}")

    def disconnect(self) -> None:
        if self._client is not None:
            _log.info(f"Disconnecting from MongoDB: {self.profile.alias}")
            self._client.close()
            self._client = None
            self._db = None

    def list_collections(self) -> list[str]:
        self._ensure_connected()
        return sorted(self._db.list_collection_names())

    def estimated_count(self, collection: str) -> int:
        self._ensure_connected()
        return self._db[collection].estimated_document_count()

    def iter_documents(
        self, collection: str, batch_size: int
    ) -> Iterator[list[dict[str, Any]]]:
        self._ensure_connected()
        cursor = self._db[collection].find(batch_size=batch_size).max_time_ms(300_000)
        batch: list[dict[str, Any]] = []
        for doc in cursor:
            batch.append(doc)
            if len(batch) == batch_size:
                yield batch
                batch = []
                self._throttle()
        if batch:
            yield batch

    def upsert_batch(
        self, collection: str, docs: list[dict[str, Any]]
    ) -> tuple[int, int]:
        self._ensure_connected()
        self.assert_write_allowed()
        from pymongo import UpdateOne
        from pymongo.errors import BulkWriteError

        ops = [
            UpdateOne(
                {"_id": doc["_id"]},
                {"$set": {k: v for k, v in doc.items() if k != "_id"}},
                upsert=True,
            )
            for doc in docs
        ]
        try:
            result = self._db[collection].bulk_write(ops, ordered=False)
            return result.upserted_count, result.modified_count
        except BulkWriteError as exc:
            details = exc.details
            upserted = len(details.get("upserted", []))
            modified = details.get("nModified", 0)
            return upserted, modified

    def delete_collection(self, collection: str) -> None:
        self._ensure_connected()
        self.assert_write_allowed()
        self._db[collection].drop()

    def copy_indexes(self, source: AbstractConnector, collection: str) -> int:
        self._ensure_connected()
        self.assert_write_allowed()
        if not isinstance(source, MongoDBConnector):
            # Cross-type: no index migration supported
            return 0
        source._ensure_connected()
        count = 0
        for index_info in source._db[collection].index_information().values():
            if index_info.get("name") == "_id_":
                continue
            keys = index_info["key"]
            options = {
                k: v for k, v in index_info.items()
                if k not in ("key", "ns", "v", "name")
            }
            try:
                self._db[collection].create_index(keys, **options)
                count += 1
            except Exception:
                pass
        return count

    def collection_exists(self, collection: str) -> bool:
        self._ensure_connected()
        return collection in self._db.list_collection_names()

    def get_document(self, collection: str, doc_id: Any) -> dict[str, Any] | None:
        self._ensure_connected()
        return self._db[collection].find_one({"_id": doc_id})

    def get_documents_by_ids(
        self, collection: str, doc_ids: list[Any]
    ) -> dict[Any, dict[str, Any]]:
        self._ensure_connected()
        cursor = self._db[collection].find({"_id": {"$in": doc_ids}})
        return {doc["_id"]: doc for doc in cursor}

    def get_doc_timestamps(
        self, collection: str, doc_ids: list[Any]
    ) -> dict[Any, Any]:
        self._ensure_connected()
        cursor = self._db[collection].find(
            {"_id": {"$in": doc_ids}},
            {"_id": 1, "updatedAt": 1},
        )
        result = {doc_id: None for doc_id in doc_ids}
        for doc in cursor:
            result[doc["_id"]] = doc.get("updatedAt")
        return result

    def _with_retry(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute fn with exponential backoff on CosmosDB 429 / TooManyRequests."""
        from pymongo.errors import OperationFailure

        max_retries = self.settings.mongo_max_retries
        backoff = self.settings.mongo_retry_backoff_base
        for attempt in range(max_retries + 1):
            try:
                return fn(*args, **kwargs)
            except OperationFailure as exc:
                # CosmosDB RU exhaustion returns error code 16500
                if exc.code != 16500 or attempt == max_retries:
                    raise
                sleep_time = backoff ** attempt
                time.sleep(sleep_time)
        return None  # unreachable

    def _throttle(self) -> None:
        if self.settings.throttle_rps > 0:
            time.sleep(1.0 / self.settings.throttle_rps)

    def _ensure_connected(self) -> None:
        if self._db is None:
            from db_tool.i18n import t
            raise RuntimeError(t("connector.mongodb.error.not_connected", alias=self.profile.alias))

