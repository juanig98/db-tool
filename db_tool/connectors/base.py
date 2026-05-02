from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any

from db_tool.config.models import ConnectionProfile, Settings
from db_tool.config.validator import guard_write


class AbstractConnector(ABC):
    def __init__(self, profile: ConnectionProfile, settings: Settings) -> None:
        self.profile = profile
        self.settings = settings

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def list_collections(self) -> list[str]: ...

    @abstractmethod
    def estimated_count(self, collection: str) -> int: ...

    @abstractmethod
    def iter_documents(
        self, collection: str, batch_size: int
    ) -> Iterator[list[dict[str, Any]]]: ...

    @abstractmethod
    def upsert_batch(
        self, collection: str, docs: list[dict[str, Any]]
    ) -> tuple[int, int]:
        """Returns (upserted_count, modified_count)."""
        ...

    @abstractmethod
    def delete_collection(self, collection: str) -> None: ...

    @abstractmethod
    def copy_indexes(
        self, source: "AbstractConnector", collection: str, target_collection: str | None = None
    ) -> int:
        """Copy indexes from source connector for the given collection. Returns count."""
        ...

    @abstractmethod
    def collection_exists(self, collection: str) -> bool: ...

    @abstractmethod
    def get_document(
        self, collection: str, doc_id: Any
    ) -> dict[str, Any] | None: ...

    @abstractmethod
    def get_documents_by_ids(
        self, collection: str, doc_ids: list[Any]
    ) -> dict[Any, dict[str, Any]]:
        """Fetch multiple documents by _id. Returns mapping of id → document."""
        ...

    def get_doc_timestamps(
        self, collection: str, doc_ids: list[Any]
    ) -> dict[Any, Any]:
        """Fetch {_id: updatedAt} for the given ids. Returns None for missing/unknown."""
        docs = self.get_documents_by_ids(collection, doc_ids)
        return {doc_id: docs[doc_id].get("updatedAt") if doc_id in docs else None
                for doc_id in doc_ids}

    def is_write_allowed(self) -> bool:
        return self.profile.is_writable

    def assert_write_allowed(self) -> None:
        guard_write(self.profile)

    def __enter__(self) -> "AbstractConnector":
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.disconnect()
