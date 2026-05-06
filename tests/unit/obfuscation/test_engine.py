from __future__ import annotations

import pytest

from db_tool.config.models import Settings
from db_tool.obfuscation.engine import ObfuscationEngine


@pytest.fixture
def engine(tmp_path):
    settings = Settings(
        state_dir=tmp_path / "state",
        mappings_dir=tmp_path / "mappings",
        obfuscation_rules_path=tmp_path / "rules.txt",
    )
    return ObfuscationEngine(settings, seed=42)


def test_email_field_obfuscated(engine):
    doc = {"_id": 1, "email": "real@example.com"}
    result = engine.transform(doc)
    assert result["email"] != "real@example.com"
    assert "@" in result["email"]  # still looks like an email


def test_non_pii_field_unchanged(engine):
    doc = {"_id": 1, "status": "active", "count": 5}
    result = engine.transform(doc)
    assert result["status"] == "active"
    assert result["count"] == 5


def test_nested_doc_obfuscated(engine):
    doc = {"_id": 1, "contact": {"email": "real@x.com", "phone": "1234567890"}}
    result = engine.transform(doc)
    assert result["contact"]["email"] != "real@x.com"
    assert result["contact"]["phone"] != "1234567890"


def test_array_of_docs_obfuscated(engine):
    doc = {
        "_id": 1,
        "contacts": [
            {"email": "a@x.com"},
            {"email": "b@x.com"},
        ],
    }
    result = engine.transform(doc)
    assert result["contacts"][0]["email"] != "a@x.com"
    assert result["contacts"][1]["email"] != "b@x.com"


def test_referential_consistency(tmp_path):
    settings = Settings(
        state_dir=tmp_path / "state",
        mappings_dir=tmp_path / "mappings",
        obfuscation_rules_path=tmp_path / "rules.txt",
    )
    e1 = ObfuscationEngine(settings, seed=42)
    e2 = ObfuscationEngine(settings, seed=42)

    doc = {"email": "user@example.com"}
    r1 = e1.transform(doc)
    r2 = e2.transform(doc)
    assert r1["email"] == r2["email"]


def test_same_value_in_different_fields_consistent(engine):
    """Same real email in two different field names maps to same fake value."""
    doc1 = {"email": "same@x.com"}
    doc2 = {"user_email": "same@x.com"}
    r1 = engine.transform(doc1)
    r2 = engine.transform(doc2)
    assert r1["email"] == r2["user_email"]


def test_does_not_mutate_input(engine):
    doc = {"_id": 1, "email": "real@x.com", "name": "John"}
    original = dict(doc)
    engine.transform(doc)
    assert doc == original


def test_dynamic_rule_applied(tmp_path):
    rules_path = tmp_path / "rules.txt"
    rules_path.write_text(".*rfc.*::.*::numerify\n")
    settings = Settings(
        state_dir=tmp_path / "state",
        mappings_dir=tmp_path / "mappings",
        obfuscation_rules_path=rules_path,
    )
    engine = ObfuscationEngine(settings, seed=42)
    doc = {"rfc": "GALA980101ABC"}
    result = engine.transform(doc)
    assert result["rfc"] != "GALA980101ABC"


def test_empty_string_not_obfuscated(engine):
    doc = {"email": ""}
    result = engine.transform(doc)
    assert result["email"] == ""


def test_none_value_not_obfuscated(engine):
    doc = {"email": None}
    result = engine.transform(doc)
    assert result["email"] is None


def test_replacement_substring_matching(tmp_path):
    rules_path = tmp_path / "replacement_rules.txt"
    rules_path.write_text("coca-cola::koke-soda\n")
    settings = Settings(
        state_dir=tmp_path / "state",
        mappings_dir=tmp_path / "mappings",
        obfuscation_rules_path=tmp_path / "rules.txt",
        replacements_path=rules_path,
    )
    engine = ObfuscationEngine(settings, seed=42)
    doc = {"company": "works with coca-cola inc"}
    result = engine.transform(doc)
    assert result["company"] == "works with koke-soda inc"


def test_replacement_over_pii_priority(tmp_path):
    rules_path = tmp_path / "replacement_rules.txt"
    rules_path.write_text("test@example.com::replaced@test.com\n")
    settings = Settings(
        state_dir=tmp_path / "state",
        mappings_dir=tmp_path / "mappings",
        obfuscation_rules_path=tmp_path / "rules.txt",
        replacements_path=rules_path,
    )
    engine = ObfuscationEngine(settings, seed=42)
    doc = {"email": "test@example.com"}
    result = engine.transform(doc)
    assert result["email"] == "replaced@test.com"


def test_replacement_no_match_leaves_pii_applied(tmp_path):
    rules_path = tmp_path / "replacement_rules.txt"
    rules_path.write_text("not-found::replaced\n")
    settings = Settings(
        state_dir=tmp_path / "state",
        mappings_dir=tmp_path / "mappings",
        obfuscation_rules_path=tmp_path / "rules.txt",
        replacements_path=rules_path,
    )
    engine = ObfuscationEngine(settings, seed=42)
    doc = {"email": "real@email.com"}
    result = engine.transform(doc)
    assert result["email"] != "real@email.com"
    assert "@" in result["email"]


def test_transform_collection_name(tmp_path):
    rules_path = tmp_path / "replacement_rules.txt"
    rules_path.write_text("coca-cola::koke-soda\nold-::new-\n")
    settings = Settings(
        state_dir=tmp_path / "state",
        mappings_dir=tmp_path / "mappings",
        obfuscation_rules_path=tmp_path / "rules.txt",
        replacements_path=rules_path,
    )
    engine = ObfuscationEngine(settings, seed=42)
    assert engine.transform_collection_name("coca-cola-orders") == "koke-soda-orders"
    assert engine.transform_collection_name("old-users") == "new-users"
    assert engine.transform_collection_name("unaffected-collection") == "unaffected-collection"


def test_replacement_multiple_rules_order(tmp_path):
    rules_path = tmp_path / "replacement_rules.txt"
    rules_path.write_text("foo::baz\nbar::qux\n")
    settings = Settings(
        state_dir=tmp_path / "state",
        mappings_dir=tmp_path / "mappings",
        obfuscation_rules_path=tmp_path / "rules.txt",
        replacements_path=rules_path,
    )
    engine = ObfuscationEngine(settings, seed=42)
    doc = {"text": "foo and bar"}
    result = engine.transform(doc)
    assert result["text"] == "baz and qux"


def test_replacement_empty_string_not_touched(tmp_path):
    rules_path = tmp_path / "replacement_rules.txt"
    rules_path.write_text("test::replaced\n")
    settings = Settings(
        state_dir=tmp_path / "state",
        mappings_dir=tmp_path / "mappings",
        obfuscation_rules_path=tmp_path / "rules.txt",
        replacements_path=rules_path,
    )
    engine = ObfuscationEngine(settings, seed=42)
    doc = {"text": ""}
    result = engine.transform(doc)
    assert result["text"] == ""


def test_exclusion_global_rule_skips_obfuscation(tmp_path):
    excl_path = tmp_path / "exclusion_rules.txt"
    excl_path.write_text("name\n")
    settings = Settings(
        state_dir=tmp_path / "state",
        mappings_dir=tmp_path / "mappings",
        obfuscation_rules_path=tmp_path / "rules.txt",
        exclusion_rules_path=excl_path,
    )
    engine = ObfuscationEngine(settings, seed=42)
    doc = {"name": "John Doe", "email": "john@example.com"}
    result = engine.transform(doc)
    assert result["name"] == "John Doe"
    assert result["email"] != "john@example.com"


def test_exclusion_scoped_rule_skips_only_matching_collection(tmp_path):
    excl_path = tmp_path / "exclusion_rules.txt"
    excl_path.write_text(".*-environments.*::name\n")
    settings = Settings(
        state_dir=tmp_path / "state",
        mappings_dir=tmp_path / "mappings",
        obfuscation_rules_path=tmp_path / "rules.txt",
        exclusion_rules_path=excl_path,
    )
    engine = ObfuscationEngine(settings, seed=42)
    doc = {"name": "prod-env"}

    result_env = engine.transform(doc, collection="tenant-environments-v2")
    assert result_env["name"] == "prod-env"

    result_users = engine.transform(doc, collection="tenant-users")
    assert result_users["name"] != "prod-env"


def test_exclusion_scoped_rule_no_collection_context_not_excluded(tmp_path):
    excl_path = tmp_path / "exclusion_rules.txt"
    excl_path.write_text(".*-environments.*::name\n")
    settings = Settings(
        state_dir=tmp_path / "state",
        mappings_dir=tmp_path / "mappings",
        obfuscation_rules_path=tmp_path / "rules.txt",
        exclusion_rules_path=excl_path,
    )
    engine = ObfuscationEngine(settings, seed=42)
    doc = {"name": "some-value"}
    result = engine.transform(doc)
    assert result["name"] != "some-value"


def test_exclusion_replacement_takes_precedence_over_exclusion(tmp_path):
    excl_path = tmp_path / "exclusion_rules.txt"
    excl_path.write_text("name\n")
    repl_path = tmp_path / "replacement_rules.txt"
    repl_path.write_text("prod::staging\n")
    settings = Settings(
        state_dir=tmp_path / "state",
        mappings_dir=tmp_path / "mappings",
        obfuscation_rules_path=tmp_path / "rules.txt",
        replacements_path=repl_path,
        exclusion_rules_path=excl_path,
    )
    engine = ObfuscationEngine(settings, seed=42)
    doc = {"name": "prod-environment"}
    result = engine.transform(doc)
    assert result["name"] == "staging-environment"
