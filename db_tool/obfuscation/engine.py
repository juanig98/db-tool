from __future__ import annotations

from pathlib import Path
from typing import Any

from faker import Faker

from db_tool.config.models import Settings
from db_tool.obfuscation.dynamic_rules import load_dynamic_rules
from db_tool.obfuscation.exclusion_rules import ExclusionRule, load_exclusion_rules
from db_tool.obfuscation.fixed_rules import FIXED_RULES, FieldRule
from db_tool.obfuscation.mappings import MappingStore
from db_tool.obfuscation.replacement_rules import ReplacementRule, load_replacement_rules


class ObfuscationEngine:
    """Applies fixed + dynamic obfuscation rules recursively to documents."""

    def __init__(
        self,
        settings: Settings,
        locale: str = "es_ES",
        seed: int | None = None,
        replace_only: bool = False,
    ) -> None:
        self._faker = Faker(locale)
        if seed is not None:
            Faker.seed(seed)
        self._mapping_store = MappingStore(settings)
        self._fixed_rules: list[FieldRule] = [] if replace_only else list(FIXED_RULES)
        self._dynamic_rules: list[FieldRule] = []
        if not replace_only and settings.obfuscation_rules_path.exists():
            self._dynamic_rules = load_dynamic_rules(settings.obfuscation_rules_path)
        self._replacement_rules: list[ReplacementRule] = []
        if settings.replacements_path.exists():
            self._replacement_rules = load_replacement_rules(settings.replacements_path)
        self._exclusion_rules: list[ExclusionRule] = load_exclusion_rules(settings.exclusion_rules_path)

    def reload_dynamic_rules(self, rules_path: Path) -> None:
        self._dynamic_rules = load_dynamic_rules(rules_path)

    def transform(self, doc: dict[str, Any], collection: str | None = None) -> dict[str, Any]:
        """Return a new dict with PII fields obfuscated. Does not mutate input."""
        return self._transform_value("__root__", doc, collection)  # type: ignore[return-value]

    def _transform_value(self, field_name: str, value: Any, collection: str | None = None) -> Any:
        if isinstance(value, dict):
            return {k: self._transform_value(k, v, collection) for k, v in value.items()}
        if isinstance(value, list):
            return [self._transform_value(field_name, item, collection) for item in value]
        # scalar: apply direct replacements first (priority over PII rules)
        if isinstance(value, str) and value and self._replacement_rules:
            replaced = self._apply_replacements(value)
            if replaced != value:
                return replaced
        # scalar: skip if field is excluded for this collection
        if self._is_excluded(collection, field_name):
            return value
        # scalar: check if a rule matches
        rule = self._find_rule(field_name, value)
        if rule is not None and value is not None and value != "":
            return self._apply_rule(rule, str(value))
        return value

    def _is_excluded(self, collection: str | None, field_name: str) -> bool:
        for rule in self._exclusion_rules:
            if not rule.field_pattern.fullmatch(field_name):
                continue
            if rule.collection_pattern is None:
                return True
            if collection is not None and rule.collection_pattern.fullmatch(collection):
                return True
        return False

    def _find_rule(self, field_name: str, value: Any) -> FieldRule | None:
        # Fixed rules checked first, then dynamic
        for rule in self._fixed_rules + self._dynamic_rules:
            if not rule.field_pattern.fullmatch(field_name):
                continue
            if rule.value_pattern is not None:
                if not rule.value_pattern.search(str(value)):
                    continue
            return rule
        return None

    def _apply_rule(self, rule: FieldRule, real_value: str) -> str:
        faker_fn = self._get_faker_fn(rule.faker_type)
        return self._mapping_store.get_or_create(real_value, rule.faker_type, faker_fn)

    def _get_faker_fn(self, faker_type: str) -> Any:
        if faker_type == "random_element":
            return lambda: self._faker.random_element(elements=["M", "F", "X"])
        if faker_type == "numerify":
            # Use same length as original would be ideal, but we don't have it here
            return lambda: self._faker.numerify(text="########")
        if faker_type == "date_of_birth":
            return lambda: self._faker.date_of_birth().isoformat()
        fn = getattr(self._faker, faker_type, None)
        if fn is None:
            return lambda: self._faker.bothify(text="????-####")
        return fn

    def _apply_replacements(self, value: str) -> str:
        result = value
        for rule in self._replacement_rules:
            result = result.replace(rule.source, rule.target)
        return result

    def transform_collection_name(self, name: str) -> str:
        return self._apply_replacements(name)
