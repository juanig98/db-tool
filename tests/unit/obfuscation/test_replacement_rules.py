from __future__ import annotations

import pytest

from db_tool.obfuscation.replacement_rules import load_replacement_rules, ReplacementRule


def test_load_empty_file(tmp_path):
    f = tmp_path / "rules.txt"
    f.write_text("")
    assert load_replacement_rules(f) == []


def test_load_comments_and_blanks_ignored(tmp_path):
    f = tmp_path / "rules.txt"
    f.write_text("# comment\n\n# another\n")
    assert load_replacement_rules(f) == []


def test_load_missing_file(tmp_path):
    assert load_replacement_rules(tmp_path / "nonexistent.txt") == []


def test_load_valid_rule(tmp_path):
    f = tmp_path / "rules.txt"
    f.write_text("coca-cola::koke-soda\n")
    rules = load_replacement_rules(f)
    assert len(rules) == 1
    assert rules[0].source == "coca-cola"
    assert rules[0].target == "koke-soda"


def test_load_multiple_rules(tmp_path):
    f = tmp_path / "rules.txt"
    f.write_text("a::b\nc::d\n")
    rules = load_replacement_rules(f)
    assert len(rules) == 2
    assert rules[0].source == "a"
    assert rules[1].source == "c"


def test_load_rule_with_extra_colons(tmp_path):
    f = tmp_path / "rules.txt"
    f.write_text("http://example.com::https://example.com\n")
    rules = load_replacement_rules(f)
    assert len(rules) == 1
    assert rules[0].source == "http://example.com"
    assert rules[0].target == "https://example.com"


def test_load_ignores_invalid_format_no_colon(tmp_path):
    f = tmp_path / "rules.txt"
    f.write_text("no-colon-here\n")
    rules = load_replacement_rules(f)
    assert rules == []


def test_load_ignores_empty_source(tmp_path):
    f = tmp_path / "rules.txt"
    f.write_text("::target\n")
    rules = load_replacement_rules(f)
    assert rules == []


def test_load_ignores_empty_target(tmp_path):
    f = tmp_path / "rules.txt"
    f.write_text("source::\n")
    rules = load_replacement_rules(f)
    assert rules == []


def test_replacement_rule_is_frozen():
    rule = ReplacementRule(source="a", target="b")
    with pytest.raises(Exception):
        rule.source = "c"


def test_replacement_rule_equality():
    rule1 = ReplacementRule(source="a", target="b")
    rule2 = ReplacementRule(source="a", target="b")
    rule3 = ReplacementRule(source="a", target="c")
    assert rule1 == rule2
    assert rule1 != rule3