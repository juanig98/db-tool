from __future__ import annotations

import pytest

from db_tool.obfuscation.exclusion_rules import ExclusionRule, load_exclusion_rules


def test_returns_empty_when_file_missing(tmp_path):
    rules = load_exclusion_rules(tmp_path / "nonexistent.txt")
    assert rules == []


def test_returns_empty_for_empty_file(tmp_path):
    f = tmp_path / "rules.txt"
    f.write_text("")
    assert load_exclusion_rules(f) == []


def test_comments_and_blank_lines_ignored(tmp_path):
    f = tmp_path / "rules.txt"
    f.write_text("# this is a comment\n\n# another comment\n")
    assert load_exclusion_rules(f) == []


def test_global_rule_no_collection(tmp_path):
    f = tmp_path / "rules.txt"
    f.write_text("name\n")
    rules = load_exclusion_rules(f)
    assert len(rules) == 1
    assert rules[0].collection_pattern is None
    assert rules[0].field_pattern.fullmatch("name")


def test_scoped_rule_with_collection(tmp_path):
    f = tmp_path / "rules.txt"
    f.write_text(".*-environments.*::name\n")
    rules = load_exclusion_rules(f)
    assert len(rules) == 1
    assert rules[0].collection_pattern is not None
    assert rules[0].collection_pattern.fullmatch("tenant-environments-v2")
    assert not rules[0].collection_pattern.fullmatch("tenant-users")
    assert rules[0].field_pattern.fullmatch("name")


def test_multiple_rules_loaded(tmp_path):
    f = tmp_path / "rules.txt"
    f.write_text(
        ".*-environments.*::name\n"
        ".*-channels.*::name\n"
        "slug\n"
    )
    rules = load_exclusion_rules(f)
    assert len(rules) == 3


def test_field_pattern_is_case_insensitive(tmp_path):
    f = tmp_path / "rules.txt"
    f.write_text("Name\n")
    rules = load_exclusion_rules(f)
    assert rules[0].field_pattern.fullmatch("name")
    assert rules[0].field_pattern.fullmatch("NAME")
