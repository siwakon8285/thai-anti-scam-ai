"""Collect eligible rule candidates for a single message."""

from dataclasses import dataclass, field
from typing import Literal

from thai_ai._evidence import (
    ContextEvidence, EvidenceSource, RoleEvidence, Span, _QUESTION_INTENTS, roles_for_source,
)
from thai_ai.guards import passes_guard
from thai_ai.matching import Rule, _DEFAULT_RULES, _Match, _find_matches
from thai_ai.normalization import normalize_text
from thai_ai.registry import RuleRegistry


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
    registry = RuleRegistry(rules)
    view = normalize_text(text)
    candidates = ()
    if view.kind == "content":
        candidates, _ = _collect_content(view.matching_text, registry)
    return CandidateCollection(view.raw_text, view.matching_text, view.kind, candidates)


def _collect_content(
    matching_text: str, registry: RuleRegistry,
) -> tuple[tuple[Candidate, ...], tuple[_Match, ...]]:
    eligible = tuple(match for match in _find_matches(matching_text, registry.rules) if passes_guard(match))
    spans_by_rule: dict[Rule, set[Span]] = {}
    for match in eligible:
        spans_by_rule.setdefault(match.rule, set()).add(match.span)
    candidates = tuple(
        Candidate(rule.rule_id, rule.intent, rule.priority, rule.specificity, tuple(sorted(spans)))
        for rule, spans in sorted(spans_by_rule.items(), key=lambda pair: pair[0].rule_id)
    )
    return candidates, eligible


def _collect_roles(matching_text: str, eligible: tuple[_Match, ...]) -> tuple[ContextEvidence, ...]:
    """Attach roles only to eligible matches of an approved pair of whole clauses."""
    openings = [match for match in eligible if match.pair_side == "opening"]
    following = [match for match in eligible if match.pair_side == "following"]
    if not openings or not following:
        return ()

    pairs = [(EvidenceSource.C08_INTRO_QUESTION, "GREETING", _QUESTION_INTENTS)]
    if matching_text == "ขอบคุณครับ ช่วยเริ่มให้หน่อย":
        pairs.append((EvidenceSource.R6_MIXED_STARTUP_REQUEST, "THANKS", frozenset({"HELP"})))

    evidence = []
    for source, opening_intent, primary_intents in pairs:
        first_role, second_role = roles_for_source(source)
        primary_matches = [match for match in following if match.rule.intent in primary_intents]
        for opening in openings:
            if opening.rule.intent != opening_intent:
                continue
            for primary in primary_matches:
                evidence.append(ContextEvidence(
                    source, (opening.span[0], primary.span[1]),
                    (RoleEvidence(first_role, opening.rule.rule_id, opening.span),
                     RoleEvidence(second_role, primary.rule.rule_id, primary.span)),
                ))
    return tuple(evidence)
