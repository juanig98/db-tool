from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from db_tool.config.models import Settings


class StateManager:
    """Persists per-run progress for copy/sync operations in ~/.db-tool/state/."""

    def __init__(self, settings: Settings) -> None:
        self._state_dir = settings.state_dir
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, dict[str, str]] = {}

    @staticmethod
    def make_key(source_alias: str, target_alias: str, collection: str) -> str:
        raw = f"{source_alias}::{target_alias}::{collection}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _path(self, key: str) -> Path:
        return self._state_dir / f"{key}.json"

    def _load(self, key: str) -> dict[str, str]:
        if key not in self._cache:
            path = self._path(key)
            if path.exists():
                self._cache[key] = json.loads(path.read_text())
            else:
                self._cache[key] = {}
        return self._cache[key]

    def _flush(self, key: str) -> None:
        self._path(key).write_text(json.dumps(self._cache[key], indent=2))

    def mark_batch_done(
        self, source_alias: str, target_alias: str, collection: str, batch_index: int
    ) -> None:
        key = self.make_key(source_alias, target_alias, collection)
        state = self._load(key)
        state[f"batch_{batch_index:06d}"] = "done"
        self._flush(key)

    def is_batch_done(
        self, source_alias: str, target_alias: str, collection: str, batch_index: int
    ) -> bool:
        key = self.make_key(source_alias, target_alias, collection)
        return self._load(key).get(f"batch_{batch_index:06d}") == "done"

    def mark_collection_complete(
        self, source_alias: str, target_alias: str, collection: str
    ) -> None:
        key = self.make_key(source_alias, target_alias, collection)
        state = self._load(key)
        state["complete"] = datetime.now(timezone.utc).isoformat()
        self._flush(key)

    def is_collection_complete(
        self, source_alias: str, target_alias: str, collection: str
    ) -> bool:
        key = self.make_key(source_alias, target_alias, collection)
        return "complete" in self._load(key)

    def clear_collection(
        self, source_alias: str, target_alias: str, collection: str
    ) -> None:
        key = self.make_key(source_alias, target_alias, collection)
        self._cache.pop(key, None)
        path = self._path(key)
        if path.exists():
            path.unlink()

    def clear_all(self) -> int:
        """Delete all state files. Returns count of deleted files."""
        count = 0
        for f in self._state_dir.glob("*.json"):
            f.unlink()
            count += 1
        self._cache.clear()
        return count
