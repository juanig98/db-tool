from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from typing import Any

from db_tool.config.validator import filter_blacklist
from db_tool.connectors.base import AbstractConnector
from db_tool.config.models import Settings
from db_tool.operations import CollectionResult, OperationResult, ProgressEvent

_log = logging.getLogger("db_tool.operations.obfuscate")


def run_obfuscate(
    target: AbstractConnector,
    pattern: str,
    obfuscation_engine: Any,
    settings: Settings,
    dry_run: bool = False,
    progress_callback: Callable[[ProgressEvent], None] | None = None,
) -> OperationResult:
    """Apply obfuscation in-place to documents in target (non-prod only)."""
    target.assert_write_allowed()

    _log.info(f"Starting obfuscate operation: target={target.profile.alias}, pattern={pattern!r}, dry_run={dry_run}")

    result = OperationResult(operation="obfuscate")
    compiled = re.compile(pattern)
    start = time.monotonic()

    all_collections = target.list_collections()
    collections = filter_blacklist(target.profile, [
        c for c in all_collections if compiled.fullmatch(c)
    ])

    collections_total = len(collections)
    _log.info(f"Obfuscate operation: {collections_total} collections to process")
    for col_idx, collection in enumerate(collections):
        target_collection = obfuscation_engine.transform_collection_name(collection)

        if target_collection != collection and target.collection_exists(target_collection):
            _log.error(f"Cannot rename '{collection}' to '{target_collection}': target collection already exists")
            result.collections.append(CollectionResult(collection=collection, error=f"Target collection '{target_collection}' already exists"))
            continue

        col_result = _obfuscate_collection(
            target=target,
            collection=collection,
            target_collection=target_collection,
            obfuscation_engine=obfuscation_engine,
            settings=settings,
            dry_run=dry_run,
            progress_callback=progress_callback,
            collection_index=col_idx,
            collections_total=collections_total,
        )
        result.collections.append(col_result)
        _log.info(f"Collection '{collection}' obfuscated: {col_result.modified} modified")

    result.elapsed_seconds = time.monotonic() - start
    return result


def _obfuscate_collection(
    target: AbstractConnector,
    collection: str,
    target_collection: str,
    obfuscation_engine: Any,
    settings: Settings,
    dry_run: bool,
    progress_callback: Callable[[ProgressEvent], None] | None,
    collection_index: int = 0,
    collections_total: int = 1,
) -> CollectionResult:
    col_result = CollectionResult(collection=collection)
    total_docs = target.estimated_count(collection)
    docs_processed = 0
    batch_index = 0
    obfuscated_total = 0

    try:
        for batch in target.iter_documents(collection, settings.batch_size):
            batch_original = batch.copy()
            obfuscated = [obfuscation_engine.transform(doc, collection=collection) for doc in batch]
            obfuscated_count = sum(1 for orig, new in zip(batch_original, obfuscated) if orig != new)
            obfuscated_total += obfuscated_count
            _log.info(f"[{collection}] [batch {batch_index}] {len(batch)} processed, {obfuscated_count} obfuscated")

            if not dry_run:
                upserted, modified = target.upsert_batch(target_collection, obfuscated)
                col_result.upserted += upserted
                col_result.modified += modified
            docs_processed += len(batch)

            if progress_callback:
                progress_callback(ProgressEvent(
                    collection=collection,
                    batch_index=batch_index,
                    docs_processed=docs_processed,
                    docs_total=total_docs,
                    upserted=col_result.upserted,
                    modified=col_result.modified,
                    skipped=0,
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
                skipped=0,
                obfuscated=obfuscated_total,
                phase="complete",
                collection_index=collection_index,
                collections_total=collections_total,
            ))

        if target_collection != collection and not dry_run:
            target.delete_collection(collection)
            _log.info(f"Deleted original collection '{collection}' after rename to '{target_collection}'")

    except Exception as exc:
        col_result.error = str(exc)

    return col_result
