from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable

from db_tool.config.validator import filter_blacklist
from db_tool.connectors.base import AbstractConnector
from db_tool.config.models import Settings
from db_tool.operations import CollectionResult, OperationResult, ProgressEvent

_log = logging.getLogger("db_tool.operations.delete")


def run_delete(
    target: AbstractConnector,
    pattern: str,
    settings: Settings,
    dry_run: bool = False,
    progress_callback: Callable[[ProgressEvent], None] | None = None,
) -> OperationResult:
    """Delete collections matching pattern from target."""
    target.assert_write_allowed()

    _log.info(f"Starting delete operation: target={target.profile.alias}, pattern={pattern!r}, dry_run={dry_run}")

    result = OperationResult(operation="delete")
    compiled = re.compile(pattern)
    start = time.monotonic()

    all_collections = target.list_collections()
    collections = filter_blacklist(target.profile, [
        c for c in all_collections if compiled.fullmatch(c)
    ])

    collections_total = len(collections)
    _log.info(f"Delete operation: {collections_total} collections to delete")
    for col_idx, collection in enumerate(collections):
        col_result = CollectionResult(collection=collection)
        try:
            if not dry_run:
                target.delete_collection(collection)
                _log.info(f"Deleted collection: {collection}")
            else:
                _log.info(f"Would delete collection (dry-run): {collection}")
            col_result.skipped = 1 if dry_run else 0
        except Exception as exc:
            _log.warning(f"Failed to delete collection '{collection}': {exc}")
            col_result.error = str(exc)
        result.collections.append(col_result)

        if progress_callback:
            progress_callback(ProgressEvent(
                collection=collection,
                batch_index=0,
                docs_processed=1,
                docs_total=1,
                upserted=0,
                modified=0,
                skipped=col_result.skipped,
                obfuscated=0,
                phase="complete" if not col_result.error else "error",
                error=col_result.error,
                collection_index=col_idx,
                collections_total=collections_total,
            ))

    result.elapsed_seconds = time.monotonic() - start
    return result
