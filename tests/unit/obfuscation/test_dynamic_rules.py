from __future__ import annotations

import pytest

from db_tool.obfuscation.dynamic_rules import load_dynamic_rules


def test_load_empty_file(tmp_path):
    f = tmp_path / "rules.txt"
    f.write_text("")
    assert load_dynamic_rules(f) == []


def test_load_comments_and_blanks_ignored(tmp_path):
    f = tmp_path / "rules.txt"
    f.write_text("# comment\n\n# another\n")
    assert load_dynamic_rules(f) == []


def test_load_missing_file(tmp_path):
    assert load_dynamic_rules(tmp_path / "nonexistent.txt") == []


def test_load_valid_rule(tmp_path):
    f = tmp_path / "rules.txt"
    f.write_text(".*rfc.*::.*::numerify\n")
    rules = load_dynamic_rules(f)
    assert len(rules) == 1
    assert rules[0].faker_type == "numerify"
    assert rules[0].source == "dynamic"
    assert rules[0].field_pattern.fullmatch("rfc")


def test_load_rule_with_value_pattern(tmp_path):
    f = tmp_path / "rules.txt"
    f.write_text(r".*dni.*::\d{8}::numerify" + "\n")
    rules = load_dynamic_rules(f)
    assert rules[0].value_pattern is not None
    assert rules[0].value_pattern.search("12345678")
    assert not rules[0].value_pattern.search("abc")


def test_load_invalid_format_raises(tmp_path):
    f = tmp_path / "rules.txt"
    f.write_text("invalid_line_no_separators\n")
    with pytest.raises(ValueError, match="Invalid rule"):
        load_dynamic_rules(f)


def test_load_invalid_regex_raises(tmp_path):
    f = tmp_path / "rules.txt"
    f.write_text("[invalid::.*::email\n")
    with pytest.raises(ValueError, match="Invalid field regex"):
        load_dynamic_rules(f)
