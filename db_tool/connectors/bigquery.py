from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any
from urllib.parse import urlparse

from db_tool.config.models import ConnectionProfile, Settings
from db_tool.connectors.base import AbstractConnector

_log = logging.getLogger("db_tool.connectors.bigquery")


class BigQueryConnector(AbstractConnector):
    """Connector for Google BigQuery. Connection string: bigquery://project/dataset"""

    def __init__(self, profile: ConnectionProfile, settings: Settings) -> None:
        super().__init__(profile, settings)
        self._client: Any = None
        self._project: str = ""
        self._dataset: str = ""

    def connect(self) -> None:
        from google.cloud import bigquery

        _log.info(f"Connecting to BigQuery: {self.profile.alias}")
        self._project, self._dataset = self._parse_uri(self.profile.connection_string)
        self._client = bigquery.Client(project=self._project)
        _log.info(f"Connected to BigQuery: {self.profile.alias}, project={self._project}, dataset={self._dataset}")

    def disconnect(self) -> None:
        if self._client is not None:
            _log.info(f"Disconnecting from BigQuery: {self.profile.alias}")
            self._client.close()
            self._client = None

    def list_collections(self) -> list[str]:
        self._ensure_connected()
        dataset_ref = self._client.dataset(self._dataset)
        tables = list(self._client.list_tables(dataset_ref))
        return sorted(t.table_id for t in tables)

    def estimated_count(self, collection: str) -> int:
        self._ensure_connected()
        table_ref = self._client.dataset(self._dataset).table(collection)
        table = self._client.get_table(table_ref)
        return table.num_rows or 0

    def iter_documents(
        self, collection: str, batch_size: int
    ) -> Iterator[list[dict[str, Any]]]:
        self._ensure_connected()
        query = f"SELECT * FROM `{self._project}.{self._dataset}.{collection}`"
        rows = self._client.query(query).result(page_size=batch_size)
        batch: list[dict[str, Any]] = []
        for row in rows:
            doc = dict(row.items())
            if "_id" not in doc:
                doc["_id"] = doc.get("id") or str(hash(frozenset(doc.items())))
            batch.append(doc)
            if len(batch) == batch_size:
                yield batch
                batch = []
        if batch:
            yield batch

    def upsert_batch(
        self, collection: str, docs: list[dict[str, Any]]
    ) -> tuple[int, int]:
        self._ensure_connected()
        self.assert_write_allowed()
        from google.cloud import bigquery

        # Serialize nested structures to JSON strings for BQ compatibility
        rows = [self._flatten_doc(doc) for doc in docs]
        table_ref = f"{self._project}.{self._dataset}.{collection}"
        errors = self._client.insert_rows_json(table_ref, rows)
        if errors:
            from db_tool.i18n import t
            raise RuntimeError(t("connector.bigquery.error.insert_errors", errors=errors))
        return len(docs), 0

    def delete_collection(self, collection: str) -> None:
        self._ensure_connected()
        self.assert_write_allowed()
        table_ref = self._client.dataset(self._dataset).table(collection)
        self._client.delete_table(table_ref, not_found_ok=True)

    def copy_indexes(self, source: AbstractConnector, collection: str, target_collection: str | None = None) -> int:
        return 0

    def collection_exists(self, collection: str) -> bool:
        self._ensure_connected()
        from google.cloud.exceptions import NotFound
        try:
            self._client.get_table(f"{self._project}.{self._dataset}.{collection}")
            return True
        except NotFound:
            return False

    def get_document(self, collection: str, doc_id: Any) -> dict[str, Any] | None:
        self._ensure_connected()
        query = (
            f"SELECT * FROM `{self._project}.{self._dataset}.{collection}` "
            f"WHERE _id = @doc_id LIMIT 1"
        )
        from google.cloud import bigquery
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("doc_id", "STRING", str(doc_id))]
        )
        rows = list(self._client.query(query, job_config=job_config).result())
        return dict(rows[0].items()) if rows else None

    def get_documents_by_ids(
        self, collection: str, doc_ids: list[Any]
    ) -> dict[Any, dict[str, Any]]:
        self._ensure_connected()
        if not doc_ids:
            return {}
        from google.cloud import bigquery
        placeholders = ", ".join(f"@id_{i}" for i in range(len(doc_ids)))
        query = (
            f"SELECT * FROM `{self._project}.{self._dataset}.{collection}` "
            f"WHERE _id IN ({placeholders})"
        )
        params = [
            bigquery.ScalarQueryParameter(f"id_{i}", "STRING", str(doc_ids[i]))
            for i in range(len(doc_ids))
        ]
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        rows = list(self._client.query(query, job_config=job_config).result())
        return {row["_id"]: dict(row.items()) for row in rows}

    def _flatten_doc(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Serialize nested dicts/lists to JSON strings (Option A cross-type handling)."""
        result: dict[str, Any] = {}
        for k, v in doc.items():
            if isinstance(v, (dict, list)):
                result[k] = json.dumps(v, ensure_ascii=False, default=str)
            else:
                result[k] = v
        return result

    def _ensure_connected(self) -> None:
        if self._client is None:
            from db_tool.i18n import t
            raise RuntimeError(t("connector.bigquery.error.not_connected", alias=self.profile.alias))

    @staticmethod
    def _parse_uri(uri: str) -> tuple[str, str]:
        """Parse bigquery://project/dataset → (project, dataset)."""
        parsed = urlparse(uri)
        project = parsed.netloc or parsed.hostname or ""
        dataset = parsed.path.lstrip("/")
        if not project or not dataset:
            from db_tool.i18n import t
            raise ValueError(t("connector.bigquery.error.invalid_uri", uri=uri))
        return project, dataset
