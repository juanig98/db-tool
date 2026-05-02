from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

from db_tool.config.validator import filter_blacklist
from db_tool.connectors.base import AbstractConnector
from db_tool.config.models import Settings
from db_tool.operations import CollectionResult, OperationResult, ProgressEvent
from db_tool.state.manager import StateManager

_log = logging.getLogger("db_tool.operations.sync")


def run_sync(
    source: AbstractConnector,
    target: AbstractConnector,
    pattern: str,
    settings: Settings,
    obfuscation_engine: Any | None = None,
    progress_callback: Callable[[ProgressEvent], None] | None = None,
) -> OperationResult:
    """Sync collections: only copy docs missing in target or with older updatedAt."""
    target.assert_write_allowed()

    _log.info(f"Starting sync operation: source={source.profile.alias}, target={target.profile.alias}, pattern={pattern!r}")

    result = OperationResult(operation="sync")
    compiled = re.compile(pattern)
    start = time.monotonic()

    all_collections = source.list_collections()
    collections = filter_blacklist(source.profile, [
        c for c in all_collections if compiled.fullmatch(c)
    ])

    collections_total = len(collections)
    _log.info(f"Sync operation: {collections_total} collections to sync")
    for col_idx, collection in enumerate(collections):
        col_result = _sync_collection(
            source=source,
            target=target,
            collection=collection,
            settings=settings,
            obfuscation_engine=obfuscation_engine,
            progress_callback=progress_callback,
            collection_index=col_idx,
            collections_total=collections_total,
        )
        result.collections.append(col_result)
        _log.info(f"Collection '{collection}' synced: {col_result.upserted} upserted")

    result.elapsed_seconds = time.monotonic() - start
    return result


def _sync_collection(
    source: AbstractConnector,
    target: AbstractConnector,
    collection: str,
    settings: Settings,
    obfuscation_engine: Any | None,
    progress_callback: Callable[[ProgressEvent], None] | None,
    collection_index: int = 0,
    collections_total: int = 1,
) -> CollectionResult:
    col_result = CollectionResult(collection=collection)
    total_docs = source.estimated_count(collection)
    batch_index = 0
    docs_processed = 0
    obfuscated_total = 0

    try:
        for batch in source.iter_documents(collection, settings.batch_size):
            to_upsert: list[dict[str, Any]] = []

            batch_ids = [doc.get("_id") for doc in batch if doc.get("_id") is not None]
            target_timestamps = target.get_doc_timestamps(collection, batch_ids)

            for doc in batch:
                doc_id = doc.get("_id")
                tgt_updated = target_timestamps.get(doc_id)
                if _should_sync_ts(doc, tgt_updated):
                    to_upsert.append(doc)
                else:
                    col_result.skipped += 1

            docs_processed += len(batch)

            obfuscated_count = 0
            if to_upsert:
                if obfuscation_engine is not None:
                    to_upsert_original = [d.copy() for d in to_upsert]
                    to_upsert = [obfuscation_engine.transform(d) for d in to_upsert]
                    obfuscated_count = sum(1 for orig, new in zip(to_upsert_original, to_upsert) if orig != new)
                    obfuscated_total += obfuscated_count
                    _log.info(f"[{collection}] [batch {batch_index}] {len(to_upsert)} processed, {obfuscated_count} obfuscated")

                upserted, modified = target.upsert_batch(collection, to_upsert)
                col_result.upserted += upserted
                col_result.modified += modified

            if progress_callback:
                progress_callback(ProgressEvent(
                    collection=collection,
                    batch_index=batch_index,
                    docs_processed=docs_processed,
                    docs_total=total_docs,
                    upserted=col_result.upserted,
                    modified=col_result.modified,
                    skipped=col_result.skipped,
                    obfuscated=obfuscated_total,
                    phase="writing",
                    collection_index=collection_index,
                    collections_total=collections_total,
                ))
            batch_index += 1

        if progress_callback:
            progress_callback(ProgressEvent(
                collection=collection,
                batch_index=batch_index,
                docs_processed=docs_processed,
                docs_total=total_docs,
                upserted=col_result.upserted,
                modified=col_result.modified,
                skipped=col_result.skipped,
                obfuscated=obfuscated_total,
                phase="complete",
                collection_index=collection_index,
                collections_total=collections_total,
            ))

    except Exception as exc:
        col_result.error = str(exc)

    return col_result


def _should_sync_ts(source_doc: dict[str, Any], tgt_updated: Any) -> bool:
    """Return True if source doc should be written to target."""
    if tgt_updated is None:
        # doc missing in target, or target has no updatedAt → always sync
        return True
    src_updated = source_doc.get("updatedAt")
    if src_updated is None:
        return True
    return _parse_dt(src_updated) > _parse_dt(tgt_updated)


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    # fallback: treat as epoch 0
    return datetime.min
