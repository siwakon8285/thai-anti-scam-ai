"""Collect eligible rule candidates for a single message."""

from dataclasses import dataclass, field
from typing import Literal

from thai_ai.guards import passes_guard
from thai_ai.matching import Rule, _DEFAULT_RULES, _find_matches
from thai_ai.normalization import normalize_text


@dataclass(frozen=True)
class Candidate:
    """One eligible rule and its half-open code-point spans in matching text."""

    rule_id: str
    intent: str
    priority: int
    specificity: int
    spans: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class CandidateCollection:
    """A validated text view and its candidates in stable rule ID order."""

    raw_text: str = field(repr=False)
    matching_text: str = field(repr=False)
    kind: Literal["empty", "format_only", "content"]
    candidates: tuple[Candidate, ...]


def collect_candidates(
    text: str, *, rules: tuple[Rule, ...] = _DEFAULT_RULES,
) -> CandidateCollection:
    """Validate configuration and input, then return all rules that pass their guards."""
    if type(rules) is not tuple or any(type(rule) is not Rule for rule in rules):
        raise RuntimeError("invalid_configuration: expected a tuple of Rule objects")
    if len({rule.rule_id for rule in rules}) != len(rules):
        raise RuntimeError("duplicate_rule_id: configured rule IDs must be unique")

    view = normalize_text(text)
    spans_by_rule: dict[Rule, set[tuple[int, int]]] = {}
    if view.kind == "content":
        for match in _find_matches(view.matching_text, rules):
            if passes_guard(match):
                spans_by_rule.setdefault(match.rule, set()).add(match.span)
    candidates = tuple(
        Candidate(rule.rule_id, rule.intent, rule.priority, rule.specificity, tuple(sorted(spans)))
        for rule, spans in sorted(spans_by_rule.items(), key=lambda pair: pair[0].rule_id)
    )
    return CandidateCollection(view.raw_text, view.matching_text, view.kind, candidates)
