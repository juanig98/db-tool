from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any
from urllib.parse import urlparse

from db_tool.config.models import ConnectionProfile, Settings
from db_tool.connectors.base import AbstractConnector

_log = logging.getLogger("db_tool.connectors.mysql")


class MySQLConnector(AbstractConnector):
    """Connector for MySQL. Connection string: mysql://user:pass@host:port/database"""

    def __init__(self, profile: ConnectionProfile, settings: Settings) -> None:
        super().__init__(profile, settings)
        self._conn: Any = None
        self._db_name: str = ""

    def connect(self) -> None:
        import mysql.connector

        _log.info(f"Connecting to MySQL: {self.profile.alias}")
        params = self._parse_uri(self.profile.connection_string)
        params.pop("database", None)  # ignore database in URI; use profile.database_name
        self._db_name = self.profile.database_name
        self._conn = mysql.connector.connect(**params)
        if self._db_name:
            cursor = self._conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{self._db_name}`")
            cursor.execute(f"USE `{self._db_name}`")
            cursor.close()
        _log.info(f"Connected to MySQL: {self.profile.alias}, database={self._db_name}")

    def disconnect(self) -> None:
        if self._conn is not None:
            _log.info(f"Disconnecting from MySQL: {self.profile.alias}")
            self._conn.close()
            self._conn = None

    def list_collections(self) -> list[str]:
        self._ensure_connected()
        cursor = self._conn.cursor()
        cursor.execute("SHOW TABLES")
        tables = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return sorted(tables)

    def estimated_count(self, collection: str) -> int:
        self._ensure_connected()
        cursor = self._conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM `{collection}`")
        count = cursor.fetchone()[0]
        cursor.close()
        return count

    def iter_documents(
        self, collection: str, batch_size: int
    ) -> Iterator[list[dict[str, Any]]]:
        self._ensure_connected()
        cursor = self._conn.cursor(dictionary=True)
        cursor.execute(f"SELECT * FROM `{collection}`")
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            yield [self._deserialize_row(row) for row in rows]
        cursor.close()

    def upsert_batch(
        self, collection: str, docs: list[dict[str, Any]]
    ) -> tuple[int, int]:
        self._ensure_connected()
        self.assert_write_allowed()
        if not docs:
            return 0, 0

        self._ensure_table(collection, docs[0])
        cursor = self._conn.cursor()
        upserted = 0
        modified = 0

        for doc in docs:
            flat = self._serialize_doc(doc)
            columns = ", ".join(f"`{k}`" for k in flat)
            placeholders = ", ".join(["%s"] * len(flat))
            updates = ", ".join(f"`{k}` = VALUES(`{k}`)" for k in flat if k != "_id")
            sql = (
                f"INSERT INTO `{collection}` ({columns}) VALUES ({placeholders}) "
                f"ON DUPLICATE KEY UPDATE {updates}"
            )
            cursor.execute(sql, list(flat.values()))
            # rowcount: 1 = insert, 2 = update, 0 = no change
            if cursor.rowcount == 1:
                upserted += 1
            elif cursor.rowcount == 2:
                modified += 1

        self._conn.commit()
        cursor.close()
        return upserted, modified

    def delete_collection(self, collection: str) -> None:
        self._ensure_connected()
        self.assert_write_allowed()
        cursor = self._conn.cursor()
        cursor.execute(f"DROP TABLE IF EXISTS `{collection}`")
        self._conn.commit()
        cursor.close()

    def copy_indexes(self, source: AbstractConnector, collection: str) -> int:
        # Cross-type index migration not supported; schema already created via upsert
        return 0

    def collection_exists(self, collection: str) -> bool:
        self._ensure_connected()
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = %s AND table_name = %s",
            (self._db_name, collection),
        )
        exists = cursor.fetchone()[0] > 0
        cursor.close()
        return exists

    def get_document(self, collection: str, doc_id: Any) -> dict[str, Any] | None:
        self._ensure_connected()
        cursor = self._conn.cursor(dictionary=True)
        cursor.execute(f"SELECT * FROM `{collection}` WHERE `_id` = %s LIMIT 1", (str(doc_id),))
        row = cursor.fetchone()
        cursor.close()
        return self._deserialize_row(row) if row else None

    def get_doc_timestamps(
        self, collection: str, doc_ids: list[Any]
    ) -> dict[Any, Any]:
        self._ensure_connected()
        if not doc_ids:
            return {}
        placeholders = ", ".join(["%s"] * len(doc_ids))
        cursor = self._conn.cursor(dictionary=True)
        cursor.execute(
            f"SELECT `_id`, `updatedAt` FROM `{collection}` WHERE `_id` IN ({placeholders})",
            [str(d) for d in doc_ids],
        )
        rows = cursor.fetchall()
        cursor.close()
        result = {doc_id: None for doc_id in doc_ids}
        for row in rows:
            result[row["_id"]] = row.get("updatedAt")
        return result

    def get_documents_by_ids(
        self, collection: str, doc_ids: list[Any]
    ) -> dict[Any, dict[str, Any]]:
        self._ensure_connected()
        if not doc_ids:
            return {}
        placeholders = ", ".join(["%s"] * len(doc_ids))
        cursor = self._conn.cursor(dictionary=True)
        cursor.execute(
            f"SELECT * FROM `{collection}` WHERE `_id` IN ({placeholders})",
            [str(d) for d in doc_ids],
        )
        rows = cursor.fetchall()
        cursor.close()
        return {row["_id"]: self._deserialize_row(row) for row in rows}

    def _ensure_table(self, collection: str, sample_doc: dict[str, Any]) -> None:
        """Create table if it doesn't exist, based on sample document keys."""
        if self.collection_exists(collection):
            return
        flat = self._serialize_doc(sample_doc)
        col_defs = []
        for k in flat:
            if k == "_id":
                col_defs.append("`_id` VARCHAR(255) PRIMARY KEY")
            else:
                col_defs.append(f"`{k}` LONGTEXT")
        cursor = self._conn.cursor()
        cursor.execute(
            f"CREATE TABLE IF NOT EXISTS `{collection}` ({', '.join(col_defs)})"
        )
        self._conn.commit()
        cursor.close()

    def _serialize_doc(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Serialize nested structures to JSON strings (Option A cross-type)."""
        result: dict[str, Any] = {}
        for k, v in doc.items():
            if isinstance(v, (dict, list)):
                result[k] = json.dumps(v, ensure_ascii=False, default=str)
            else:
                result[k] = v
        return result

    def _deserialize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Attempt to deserialize JSON strings back to Python objects."""
        result: dict[str, Any] = {}
        for k, v in row.items():
            if isinstance(v, str) and v.startswith(("{", "[")):
                try:
                    result[k] = json.loads(v)
                    continue
                except (json.JSONDecodeError, ValueError):
                    pass
            result[k] = v
        return result

    def _ensure_connected(self) -> None:
        if self._conn is None:
            from db_tool.i18n import t
            raise RuntimeError(t("connector.mysql.error.not_connected", alias=self.profile.alias))

    @staticmethod
    def _parse_uri(uri: str) -> dict[str, Any]:
        parsed = urlparse(uri)
        params: dict[str, Any] = {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 3306,
            "database": parsed.path.lstrip("/"),
        }
        if parsed.username:
            params["user"] = parsed.username
        if parsed.password:
            params["password"] = parsed.password
        return params
