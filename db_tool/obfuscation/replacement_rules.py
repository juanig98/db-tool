from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReplacementRule:
    source: str
    target: str


def load_replacement_rules(path: Path) -> list[ReplacementRule]:
    rules = []
    if not path.exists():
        return rules

    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if "::" not in stripped:
            continue

        source, target = stripped.split("::", 1)
        source = source.strip()
        target = target.strip()

        if source and target:
            rules.append(ReplacementRule(source=source, target=target))

    return rules