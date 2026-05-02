from __future__ import annotations

import hashlib
import json
from pathlib import Path

from db_tool.config.models import Settings


class MappingStore:
    """Referential consistency store: same real value → same fake value, persisted to disk."""

    def __init__(self, settings: Settings) -> None:
        self._mappings_dir = settings.mappings_dir
        self._mappings_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, str] = {}
        self._dirty = False

    @staticmethod
    def _make_key(real_value: str, faker_type: str) -> str:
        raw = f"{faker_type}::{real_value}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _path(self, key: str) -> Path:
        # Shard by first 2 chars to avoid huge directories
        shard = key[:2]
        shard_dir = self._mappings_dir / shard
        shard_dir.mkdir(exist_ok=True)
        return shard_dir / f"{key}.json"

    def get_or_create(self, real_value: str, faker_type: str, faker_fn: object) -> str:
        """Return existing fake value or generate and persist a new one."""
        key = self._make_key(real_value, faker_type)
        if key in self._cache:
            return self._cache[key]

        path = self._path(key)
        if path.exists():
            data = json.loads(path.read_text())
            fake = data["fake"]
            self._cache[key] = fake
            return fake

        fake = str(faker_fn())  # type: ignore[operator]
        self._cache[key] = fake
        path.write_text(json.dumps({"real_hash": key, "fake": fake}))
        return fake

    def clear_all(self) -> int:
        """Delete all mapping files. Returns count of deleted files."""
        count = 0
        for f in self._mappings_dir.rglob("*.json"):
            f.unlink()
            count += 1
        self._cache.clear()
        return count
