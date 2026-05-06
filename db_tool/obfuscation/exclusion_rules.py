from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExclusionRule:
    collection_pattern: re.Pattern[str] | None  # None = applies to all collections
    field_pattern: re.Pattern[str]


def load_exclusion_rules(path: Path) -> list[ExclusionRule]:
    """Parse exclusion_rules.txt into ExclusionRule instances.

    Format per line:
        collection_regex::field_regex   (scoped to matching collections)
        field_regex                     (global — applies to all collections)
    Lines starting with # or empty are ignored.
    """
    if not path.exists():
        return []

    rules: list[ExclusionRule] = []
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "::" in line:
            collection_pat, field_pat = line.split("::", 1)
            try:
                compiled_col: re.Pattern[str] | None = re.compile(collection_pat.strip(), re.IGNORECASE)
            except re.error as exc:
                _log.warning("exclusion_rules: skipping malformed collection regex %r in line %r: %s", collection_pat.strip(), raw_line, exc)
                continue
        else:
            compiled_col = None
            field_pat = line
        try:
            compiled_field = re.compile(field_pat.strip(), re.IGNORECASE)
        except re.error as exc:
            _log.warning("exclusion_rules: skipping malformed field regex %r in line %r: %s", field_pat.strip(), raw_line, exc)
            continue
        rules.append(ExclusionRule(collection_pattern=compiled_col, field_pattern=compiled_field))
    return rules
