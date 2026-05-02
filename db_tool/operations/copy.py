from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from typing import Any

from db_tool.config.validator import filter_blacklist, requires_stage_confirmation

_log = logging.getLogger("db_tool.operations.copy")
from db_tool.connectors.base import AbstractConnector
from db_tool.config.models import Settings
from db_tool.operations import CollectionResult, OperationResult, ProgressEvent
from db_tool.state.manager import StateManager


def run_copy(
    source: AbstractConnector,
    target: AbstractConnector,
    pattern: str,
    settings: Settings,
    obfuscation_engine: Any | None = None,
    data_only: bool = False,
    dry_run: bool = False,
    resume: bool = False,
    max_docs_per_collection: int = 0,
    progress_callback: Callable[[ProgressEvent], None] | None = None,
) -> OperationResult:
    """Copy collections matching pattern from source to target."""
    target.assert_write_allowed()

    _log.info(f"Starting copy operation: source={source.profile.alias}, target={target.profile.alias}, pattern={pattern!r}, dry_run={dry_run}")

    state_manager = StateManager(settings)
    result = OperationResult(operation="copy")
    compiled = re.compile(pattern)
    start = time.monotonic()

    all_collections = source.list_collections()
    collections = filter_blacklist(source.profile, [
        c for c in all_collections if compiled.fullmatch(c)
    ])

    collections_total = len(collections)
    _log.info(f"Copy operation: {collections_total} collections to copy")
    for col_idx, collection in enumerate(collections):
        col_result = _copy_collection(
            source=source,
            target=target,
            collection=collection,
            settings=settings,
            obfuscation_engine=obfuscation_engine,
            data_only=data_only,
            dry_run=dry_run,
            resume=resume,
            max_docs=max_docs_per_collection,
            state_manager=state_manager,
            progress_callback=progress_callback,
            collection_index=col_idx,
            collections_total=collections_total,
        )
        result.collections.append(col_result)
        _log.info(f"Collection '{collection}' copied: {col_result.upserted} upserted, {col_result.modified} modified")

    result.elapsed_seconds = time.monotonic() - start
    _log.info(f"Copy operation completed: {len(result.collections)} collections, {result.total_upserted} upserted, {result.elapsed_seconds:.2f}s")
    return result


def _copy_collection(
    source: AbstractConnector,
    target: AbstractConnector,
    collection: str,
    settings: Settings,
    obfuscation_engine: Any | None,
    data_only: bool,
    dry_run: bool,
    resume: bool,
    max_docs: int,
    state_manager: StateManager,
    progress_callback: Callable[[ProgressEvent], None] | None,
    collection_index: int = 0,
    collections_total: int = 1,
) -> CollectionResult:
    col_result = CollectionResult(collection=collection)
    src_alias = source.profile.alias
    tgt_alias = target.profile.alias

    if resume and state_manager.is_collection_complete(src_alias, tgt_alias, collection):
        col_result.skipped = source.estimated_count(collection)
        _emit(progress_callback, collection, 0, col_result.skipped, col_result.skipped, 0, 0, col_result.skipped, 0, "complete", None, collection_index, collections_total)
        return col_result

    total_docs = source.estimated_count(collection)
    batch_index = 0
    docs_processed = 0
    obfuscated_total = 0

    try:
        for batch in source.iter_documents(collection, settings.batch_size):
            if max_docs > 0 and docs_processed >= max_docs:
                break

            if max_docs > 0:
                remaining = max_docs - docs_processed
                batch = batch[:remaining]

            if resume and state_manager.is_batch_done(src_alias, tgt_alias, collection, batch_index):
                col_result.skipped += len(batch)
                docs_processed += len(batch)
                batch_index += 1
                continue

            _emit(progress_callback, collection, batch_index, docs_processed, total_docs, 0, 0, 0, 0, "reading", None, collection_index, collections_total)

            obfuscated_count = 0
            if obfuscation_engine is not None:
                batch_original = batch.copy()
                batch = [obfuscation_engine.transform(doc) for doc in batch]
                obfuscated_count = sum(1 for orig, new in zip(batch_original, batch) if orig != new)
                obfuscated_total += obfuscated_count
                _log.info(f"[{collection}] [batch {batch_index}] {len(batch)} processed, {obfuscated_count} obfuscated")

            if not dry_run:
                upserted, modified = target.upsert_batch(collection, batch)
                col_result.upserted += upserted
                col_result.modified += modified
                state_manager.mark_batch_done(src_alias, tgt_alias, collection, batch_index)

            docs_processed += len(batch)
            _emit(progress_callback, collection, batch_index, docs_processed, total_docs,
                  col_result.upserted, col_result.modified, col_result.skipped, obfuscated_total, "writing", None, collection_index, collections_total)
            batch_index += 1

        if not dry_run and not data_only:
            _emit(progress_callback, collection, batch_index, docs_processed, total_docs,
                  col_result.upserted, col_result.modified, col_result.skipped, obfuscated_total, "indexing", None, collection_index, collections_total)
            target.copy_indexes(source, collection)

        if not dry_run:
            state_manager.mark_collection_complete(src_alias, tgt_alias, collection)

        _emit(progress_callback, collection, batch_index, docs_processed, total_docs,
              col_result.upserted, col_result.modified, col_result.skipped, obfuscated_total, "complete", None, collection_index, collections_total)

    except Exception as exc:
        col_result.error = str(exc)
        _emit(progress_callback, collection, batch_index, docs_processed, total_docs,
              col_result.upserted, col_result.modified, col_result.skipped, obfuscated_total, "error", str(exc), collection_index, collections_total)

    return col_result


def _emit(
    callback: Callable[[ProgressEvent], None] | None,
    collection: str,
    batch_index: int,
    docs_processed: int,
    docs_total: int,
    upserted: int,
    modified: int,
    skipped: int,
    obfuscated: int,
    phase: str,
    error: str | None = None,
    collection_index: int = 0,
    collections_total: int = 1,
) -> None:
    if callback is not None:
        callback(ProgressEvent(
            collection=collection,
            batch_index=batch_index,
            docs_processed=docs_processed,
            docs_total=docs_total,
            upserted=upserted,
            modified=modified,
            skipped=skipped,
            obfuscated=obfuscated,
            phase=phase,  # type: ignore[arg-type]
            error=error,
            collection_index=collection_index,
            collections_total=collections_total,
        ))
