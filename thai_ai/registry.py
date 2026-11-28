"""Validated rule configuration shared by matching and resolution."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from thai_ai.matching import Rule


@dataclass(frozen=True)
class RuleRegistry:
    """A read-only snapshot of the rules and their ID index."""

    rules: tuple[Rule, ...]
    by_id: Mapping[str, Rule] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if type(self.rules) is not tuple or any(type(rule) is not Rule for rule in self.rules):
            raise RuntimeError("invalid_configuration: expected a tuple of Rule objects")
        for rule in self.rules:
            rule._validate_metadata()
        index = {rule.rule_id: rule for rule in self.rules}
        if len(index) != len(self.rules):
            raise RuntimeError("duplicate_rule_id: configured rule IDs must be unique")
        object.__setattr__(self, "by_id", MappingProxyType(index))
