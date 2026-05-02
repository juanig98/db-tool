from __future__ import annotations

import re
from pathlib import Path

from db_tool.obfuscation.fixed_rules import FieldRule


def load_dynamic_rules(rules_path: Path) -> list[FieldRule]:
    """Parse obfuscation_rules.txt into FieldRule instances.

    Format per line: field_regex::value_regex::faker_type
    Lines starting with # or empty are ignored.
    """
    if not rules_path.exists():
        return []

    rules: list[FieldRule] = []
    for line_num, raw_line in enumerate(rules_path.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("::")
        if len(parts) != 3:
            from db_tool.i18n import t
            raise ValueError(t("obfuscation.error.invalid_rule", line_num=line_num, raw_line=raw_line))
        field_pat, value_pat, faker_type = (p.strip() for p in parts)
        try:
            compiled_field = re.compile(field_pat, re.IGNORECASE)
        except re.error as exc:
            from db_tool.i18n import t
            raise ValueError(t("obfuscation.error.invalid_field_regex", line_num=line_num, exc=exc)) from exc
        try:
            compiled_value = re.compile(value_pat, re.IGNORECASE) if value_pat and value_pat != ".*" else None
        except re.error as exc:
            from db_tool.i18n import t
            raise ValueError(t("obfuscation.error.invalid_value_regex", line_num=line_num, exc=exc)) from exc

        rules.append(FieldRule(
            field_pattern=compiled_field,
            value_pattern=compiled_value,
            faker_type=faker_type.strip(),
            source="dynamic",
        ))
    return rules
