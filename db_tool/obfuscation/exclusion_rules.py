from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


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
            compiled_col: re.Pattern[str] | None = re.compile(collection_pat.strip(), re.IGNORECASE)
        else:
            compiled_col = None
            field_pat = line
        compiled_field = re.compile(field_pat.strip(), re.IGNORECASE)
        rules.append(ExclusionRule(collection_pattern=compiled_col, field_pattern=compiled_field))
    return rules
