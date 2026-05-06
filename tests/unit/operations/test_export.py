from __future__ import annotations

import json
from pathlib import Path


def test_export_creates_jsonl(source_connector, settings, tmp_path):
    from db_tool.operations.export import run_export

    source_connector.seed("users", [{"_id": i, "name": f"u{i}"} for i in range(5)])
    result = run_export(source_connector, "users", tmp_path, settings)
    assert result.total_upserted == 5
    output = tmp_path / "users.jsonl"
    assert output.exists()
    lines = output.read_text().strip().splitlines()
    assert len(lines) == 5
    for line in lines:
        doc = json.loads(line)
        assert "_id" in doc


def test_export_multiple_collections(source_connector, settings, tmp_path):
    from db_tool.operations.export import run_export

    source_connector.seed("col-a", [{"_id": 1}])
    source_connector.seed("col-b", [{"_id": 2}])
    result = run_export(source_connector, r"col-.*", tmp_path, settings)
    assert len(result.collections) == 2
    assert (tmp_path / "col-a.jsonl").exists()
    assert (tmp_path / "col-b.jsonl").exists()


def test_export_with_obfuscation(source_connector, settings, tmp_path):
    from db_tool.operations.export import run_export

    source_connector.seed("users", [{"_id": 1, "email": "real@x.com"}])

    class MockEngine:
        def transform(self, doc, collection=None):
            return {**doc, "email": "fake@fake.com"}

    run_export(source_connector, "users", tmp_path, settings, obfuscation_engine=MockEngine())
    data = json.loads((tmp_path / "users.jsonl").read_text())
    assert data["email"] == "fake@fake.com"
