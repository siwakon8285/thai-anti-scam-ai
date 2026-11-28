"""The public V0.1 entry point for processing one message."""

from thai_ai.matching import Rule, _DEFAULT_RULES
from thai_ai.registry import RuleRegistry
from thai_ai.response import select_response
from thai_ai.resolver import _decide_with_registry
from thai_ai.result import Result


__all__ = ("process_text",)


def process_text(text: str, *, rules: tuple[Rule, ...] = _DEFAULT_RULES) -> Result:
    """Process one built-in str with the supplied rules and return an approved reply."""
    registry = RuleRegistry(rules)
    decision = _decide_with_registry(text, registry)
    return select_response(decision, registry=registry)
