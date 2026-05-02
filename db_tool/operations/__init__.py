from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class CollectionResult:
    collection: str
    upserted: int = 0
    modified: int = 0
    skipped: int = 0
    error: str | None = None


@dataclass
class OperationResult:
    operation: str
    collections: list[CollectionResult] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    @property
    def total_upserted(self) -> int:
        return sum(c.upserted for c in self.collections)

    @property
    def total_modified(self) -> int:
        return sum(c.modified for c in self.collections)

    @property
    def total_skipped(self) -> int:
        return sum(c.skipped for c in self.collections)

    @property
    def had_errors(self) -> bool:
        return any(c.error for c in self.collections)


@dataclass
class ProgressEvent:
    collection: str
    batch_index: int
    docs_processed: int
    docs_total: int
    upserted: int
    modified: int
    skipped: int
    obfuscated: int
    phase: Literal["reading", "writing", "indexing", "complete", "error"]
    error: str | None = None
    collection_index: int = 0
    collections_total: int = 1
