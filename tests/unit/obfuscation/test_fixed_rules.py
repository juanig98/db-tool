from __future__ import annotations

import pytest

from db_tool.obfuscation.fixed_rules import FIXED_RULES


def find_rule(field_name: str, value: str = "test"):
    for rule in FIXED_RULES:
        if not rule.field_pattern.fullmatch(field_name):
            continue
        if rule.value_pattern and not rule.value_pattern.search(value):
            continue
        return rule
    return None


@pytest.mark.parametrize("field", ["email", "Email", "user_email", "emailAddress"])
def test_email_field_detected(field):
    rule = find_rule(field, "user@example.com")
    assert rule is not None
    assert rule.faker_type == "email"


def test_email_without_at_not_detected():
    assert find_rule("email", "notanemail") is None


@pytest.mark.parametrize("field", ["name", "nombre", "fullName", "full_name"])
def test_name_field_detected(field):
    rule = find_rule(field)
    assert rule is not None


@pytest.mark.parametrize("field", ["phone", "phone_number", "telefono", "mobile", "celular"])
def test_phone_field_detected(field):
    rule = find_rule(field, "1234567890")
    assert rule is not None
    assert rule.faker_type == "phone_number"


def test_phone_short_value_not_detected():
    assert find_rule("phone", "123") is None


@pytest.mark.parametrize("field", ["dni", "nid", "cedula"])
def test_identity_doc_detected(field):
    rule = find_rule(field)
    assert rule is not None


@pytest.mark.parametrize("field", ["address", "street", "city"])
def test_address_fields_detected(field):
    assert find_rule(field) is not None
