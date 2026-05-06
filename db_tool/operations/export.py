from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from db_tool.config.validator import filter_blacklist
from db_tool.connectors.base import AbstractConnector
from db_tool.config.models import Settings
from db_tool.operations import CollectionResult, OperationResult, ProgressEvent

_log = logging.getLogger("db_tool.operations.export")


def run_export(
    source: AbstractConnector,
    pattern: str,
    output_dir: Path,
    settings: Settings,
    obfuscation_engine: Any | None = None,
    progress_callback: Callable[[ProgressEvent], None] | None = None,
) -> OperationResult:
    """Export collections matching pattern to JSONL files in output_dir."""
    _log.info(f"Starting export operation: source={source.profile.alias}, pattern={pattern!r}, output_dir={output_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    result = OperationResult(operation="export")
    compiled = re.compile(pattern)
    start = time.monotonic()

    all_collections = source.list_collections()
    collections = filter_blacklist(source.profile, [
        c for c in all_collections if compiled.fullmatch(c)
    ])

    collections_total = len(collections)
    _log.info(f"Export operation: {collections_total} collections to export")
    for col_idx, collection in enumerate(collections):
        col_result = _export_collection(
            source=source,
            collection=collection,
            output_path=output_dir / f"{collection}.jsonl",
            settings=settings,
            obfuscation_engine=obfuscation_engine,
            progress_callback=progress_callback,
            collection_index=col_idx,
            collections_total=collections_total,
        )
        result.collections.append(col_result)
        _log.info(f"Collection '{collection}' exported: {col_result.upserted} documents")

    result.elapsed_seconds = time.monotonic() - start
    return result


def _export_collection(
    source: AbstractConnector,
    collection: str,
    output_path: Path,
    settings: Settings,
    obfuscation_engine: Any | None,
    progress_callback: Callable[[ProgressEvent], None] | None,
    collection_index: int = 0,
    collections_total: int = 1,
) -> CollectionResult:
    col_result = CollectionResult(collection=collection)
    total_docs = source.estimated_count(collection)
    docs_processed = 0
    batch_index = 0
    obfuscated_total = 0

    try:
        with output_path.open("w", encoding="utf-8") as f:
            for batch in source.iter_documents(collection, settings.batch_size):
                obfuscated_count = 0
                if obfuscation_engine is not None:
                    batch_original = batch.copy()
                    batch = [obfuscation_engine.transform(doc, collection=collection) for doc in batch]
                    obfuscated_count = sum(1 for orig, new in zip(batch_original, batch) if orig != new)
                    obfuscated_total += obfuscated_count
                    _log.info(f"[{collection}] [batch {batch_index}] {len(batch)} processed, {obfuscated_count} obfuscated")
                for doc in batch:
                    f.write(_serialize(doc) + "\n")
                    col_result.upserted += 1
                docs_processed += len(batch)

                if progress_callback:
                    progress_callback(ProgressEvent(
                        collection=collection,
                        batch_index=batch_index,
                        docs_processed=docs_processed,
                        docs_total=total_docs,
                        upserted=col_result.upserted,
                        modified=0,
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
                modified=0,
                        skipped=0,
                        obfuscated=obfuscated_total,
                phase="complete",
                collection_index=collection_index,
                collections_total=collections_total,
            ))

    except Exception as exc:
        col_result.error = str(exc)

    return col_result


def _serialize(doc: Any) -> str:
    return json.dumps(doc, default=_json_default, ensure_ascii=False)


def _json_default(obj: Any) -> Any:
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "__str__"):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
