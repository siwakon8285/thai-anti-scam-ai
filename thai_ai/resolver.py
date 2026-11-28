"""Select one intent from guarded candidates or record why none was selected."""

from dataclasses import InitVar, dataclass
from enum import StrEnum

from thai_ai._evidence import (
    ContextEvidence, EvidenceRole as EvidenceRole, EvidenceSource, RoleEvidence,
    Span, _QUESTION_INTENTS, roles_for_source,
)
from thai_ai._rule_metadata import is_rule_id, is_rule_intent
from thai_ai.candidates import Candidate, _collect_content, _collect_roles
from thai_ai.matching import Rule, _DEFAULT_RULES
from thai_ai.normalization import normalize_text
from thai_ai.registry import RuleRegistry


class DecisionState(StrEnum):
    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    NO_MATCH = "NO_MATCH"
    EMPTY = "EMPTY"
    FORMAT_ONLY = "FORMAT_ONLY"


class ReasonCode(StrEnum):
    MATCHED = "MATCHED"
    EXPLICIT_UNKNOWN = "EXPLICIT_UNKNOWN"
    AMBIGUOUS = "AMBIGUOUS"
    NO_MATCH = "NO_MATCH"
    EMPTY = "EMPTY"
    FORMAT_ONLY = "FORMAT_ONLY"


class SelectionBasis(StrEnum):
    SINGLE_CANDIDATE = "SINGLE_CANDIDATE"
    SAME_INTENT_PRIORITY = "SAME_INTENT_PRIORITY"
    SAME_INTENT_SPECIFICITY = "SAME_INTENT_SPECIFICITY"
    SAME_INTENT_ASCII_RULE_ID = "SAME_INTENT_ASCII_RULE_ID"
    C08_INTRO_QUESTION = "C08_INTRO_QUESTION"
    R6_MIXED_STARTUP_REQUEST = "R6_MIXED_STARTUP_REQUEST"


def _valid_span(span: object, matching_length: int | None) -> bool:
    return (
        type(span) is tuple and len(span) == 2
        and type(span[0]) is int and type(span[1]) is int
        and 0 <= span[0] < span[1]
        and (matching_length is None or span[1] <= matching_length)
    )


def _validate_candidates(candidates: tuple[Candidate, ...], matching_length: int | None) -> None:
    if type(candidates) is not tuple or any(
        type(item) is not Candidate or not is_rule_id(item.rule_id)
        or not is_rule_intent(item.intent) or type(item.priority) is not int
        or type(item.specificity) is not int or item.specificity not in (0, 1, 2)
        for item in candidates
    ):
        raise RuntimeError("invalid_candidate: expected candidates with valid rule metadata")
    for item in candidates:
        spans = item.spans
        if (
            type(spans) is not tuple or not spans
            or any(not _valid_span(span, matching_length) for span in spans)
            or any(left >= right for left, right in zip(spans, spans[1:]))
        ):
            raise RuntimeError("invalid_evidence_range: expected sorted, unique matching spans")


def _validate_membership(candidates: tuple[Candidate, ...], registry: RuleRegistry) -> None:
    unknown = min((item.rule_id for item in candidates if item.rule_id not in registry.by_id),
                  default=None)
    if unknown is not None:
        raise RuntimeError(f"unregistered_rule_id: {unknown}")

    mismatched = []
    for item in candidates:
        rule = registry.by_id[item.rule_id]
        if (item.intent, item.priority, item.specificity) != (rule.intent, rule.priority, rule.specificity):
            mismatched.append(item.rule_id)
    if mismatched:
        raise RuntimeError(f"candidate_metadata_mismatch: {min(mismatched)}")


def _valid_context(
    context: ContextEvidence, by_id: dict[str, Candidate], matching_length: int | None,
) -> bool:
    if (type(context) is not ContextEvidence or type(context.source) is not EvidenceSource
            or not _valid_span(context.context_span, matching_length)
            or type(context.roles) is not tuple or len(context.roles) != 2):
        return False
    for role, expected in zip(context.roles, roles_for_source(context.source), strict=True):
        if (type(role) is not RoleEvidence or role.role is not expected
                or not is_rule_id(role.rule_id) or role.rule_id not in by_id
                or not _valid_span(role.span, matching_length)
                or role.span not in by_id[role.rule_id].spans):
            return False
    opening, primary = context.roles
    if (opening.rule_id == primary.rule_id or opening.span[1] >= primary.span[0]
            or context.context_span != (opening.span[0], primary.span[1])):
        return False
    left, right = by_id[opening.rule_id].intent, by_id[primary.rule_id].intent
    if context.source is EvidenceSource.C08_INTRO_QUESTION:
        return left == "GREETING" and right in _QUESTION_INTENTS
    return (left, right) == ("THANKS", "HELP")


def _context_key(item: ContextEvidence) -> tuple:
    return (item.source, item.context_span, tuple((role.role, role.rule_id, role.span) for role in item.roles))


@dataclass(frozen=True)
class DecisionEvidence:
    """Canonical eligible candidates and context for one decision."""

    candidates: tuple[Candidate, ...]
    context: tuple[ContextEvidence, ...]
    _matching_length: InitVar[int | None] = None
    _registry: InitVar[RuleRegistry | None] = None

    def __post_init__(self, _matching_length: int | None, _registry: RuleRegistry | None) -> None:
        _validate_candidates(self.candidates, _matching_length)
        if _registry is not None:
            _validate_membership(self.candidates, _registry)
        by_id = {item.rule_id: item for item in self.candidates}
        if len(by_id) != len(self.candidates):
            raise RuntimeError("duplicate_candidate: expected one candidate per rule")
        if type(self.context) is not tuple or any(
            not _valid_context(item, by_id, _matching_length) for item in self.context
        ):
            raise RuntimeError("invalid_role_evidence: expected an approved pair of eligible spans")
        object.__setattr__(self, "candidates", tuple(by_id[key] for key in sorted(by_id)))
        object.__setattr__(self, "context", tuple(sorted(set(self.context), key=_context_key)))


def _rank(candidate: Candidate) -> tuple[int, int, str]:
    return -candidate.priority, -candidate.specificity, candidate.rule_id


def _selection_basis(winner: Candidate, peers: tuple[Candidate, ...]) -> SelectionBasis:
    if len(peers) == 1:
        return SelectionBasis.SINGLE_CANDIDATE
    tied = [item for item in peers if item is not winner and item.priority == winner.priority]
    if not tied:
        return SelectionBasis.SAME_INTENT_PRIORITY
    if any(item.specificity == winner.specificity for item in tied):
        return SelectionBasis.SAME_INTENT_ASCII_RULE_ID
    return SelectionBasis.SAME_INTENT_SPECIFICITY


def _select(evidence: DecisionEvidence) -> tuple[Candidate | None, SelectionBasis | None]:
    representatives: dict[str, Candidate] = {}
    for item in evidence.candidates:
        current = representatives.get(item.intent)
        if current is None or _rank(item) < _rank(current):
            representatives[item.intent] = item
    if len(representatives) == 1:
        winner, = representatives.values()
        return winner, _selection_basis(winner, evidence.candidates)
    if len(representatives) != 2:
        return None, None

    # Both approved precedence rules concern exactly two intents.
    by_id = {item.rule_id: item for item in evidence.candidates}
    coverage: dict[tuple[str, EvidenceSource], set[tuple[str, Span]]] = {}
    for pair in evidence.context:
        opening, primary = pair.roles
        primary_candidate = by_id[primary.rule_id]
        if representatives[primary_candidate.intent] is primary_candidate:
            coverage.setdefault((primary.rule_id, pair.source), set()).add((opening.rule_id, opening.span))
    for (rule_id, source), spans in coverage.items():
        winner = by_id[rule_id]
        if all((item.rule_id, span) in spans
               for item in evidence.candidates if item.intent != winner.intent
               for span in item.spans):
            return winner, SelectionBasis(source.value)
    return None, None


def _content_state(
    evidence: DecisionEvidence, winner: Candidate | None,
) -> tuple[DecisionState, ReasonCode]:
    if winner is not None:
        reason = ReasonCode.EXPLICIT_UNKNOWN if winner.intent == "UNKNOWN" else ReasonCode.MATCHED
        return DecisionState.RESOLVED, reason
    if evidence.candidates:
        return DecisionState.AMBIGUOUS, ReasonCode.AMBIGUOUS
    return DecisionState.NO_MATCH, ReasonCode.NO_MATCH


@dataclass(frozen=True)
class DecisionRecord:
    """A decision and its evidence, independent of response rendering."""

    state: DecisionState
    winner: Candidate | None
    reason_code: ReasonCode
    evidence: DecisionEvidence
    selection_basis: SelectionBasis | None = None

    def __post_init__(self) -> None:
        if (type(self.state) is not DecisionState or type(self.reason_code) is not ReasonCode
                or type(self.evidence) is not DecisionEvidence
                or (self.winner is not None and type(self.winner) is not Candidate)
                or (self.selection_basis is not None and type(self.selection_basis) is not SelectionBasis)):
            raise RuntimeError("invalid_decision: invalid field types")
        if self.state in (DecisionState.EMPTY, DecisionState.FORMAT_ONLY) and not self.evidence.candidates:
            winner, basis = None, None
            state, reason = self.state, ReasonCode(self.state.value)
        else:
            winner, basis = _select(self.evidence)
            state, reason = _content_state(self.evidence, winner)
        if (self.state, self.winner, self.reason_code, self.selection_basis) != (state, winner, reason, basis):
            raise RuntimeError("invalid_decision: state, winner, reason and evidence must agree")
        # Retain the eligible instance from the evidence even if a caller supplies an equal copy.
        object.__setattr__(self, "winner", winner)

    @property
    def intent(self) -> str:
        if self.winner is not None:
            return self.winner.intent
        return "EMPTY_INPUT" if self.state is DecisionState.EMPTY else "UNKNOWN"

    @property
    def rule_id(self) -> str | None:
        return self.winner.rule_id if self.winner is not None else None

    @property
    def path(self) -> str:
        if self.state is DecisionState.RESOLVED:
            return "matched"
        if self.state is DecisionState.AMBIGUOUS:
            return "ambiguity"
        return self.state.value.lower()


def resolve_candidates(
    candidates: tuple[Candidate, ...], *, matching_length: int,
    registry: RuleRegistry, context_evidence: tuple[ContextEvidence, ...] = (),
) -> DecisionRecord:
    """Resolve guarded content using the registry snapshot that produced it."""
    if type(registry) is not RuleRegistry:
        raise RuntimeError("invalid_configuration: expected a validated rule registry")
    if type(matching_length) is not int or matching_length <= 0:
        raise RuntimeError("invalid_candidate: expected a positive content matching length")
    if type(context_evidence) is not tuple:
        raise RuntimeError("invalid_role_evidence: expected a tuple of context evidence")
    evidence = DecisionEvidence(candidates, context_evidence, matching_length, registry)
    winner, basis = _select(evidence)
    state, reason = _content_state(evidence, winner)
    return DecisionRecord(state, winner, reason, evidence, basis)


def decide(text: str, *, rules: tuple[Rule, ...] = _DEFAULT_RULES) -> DecisionRecord:
    """Validate and route one message through the decision boundary."""
    return _decide_with_registry(text, RuleRegistry(rules))


def _decide_with_registry(text: str, registry: RuleRegistry) -> DecisionRecord:
    """Run the decision stages with an already validated registry snapshot."""
    view = normalize_text(text)
    if view.kind == "empty":
        return DecisionRecord(DecisionState.EMPTY, None, ReasonCode.EMPTY, DecisionEvidence((), ()))
    if view.kind == "format_only":
        return DecisionRecord(DecisionState.FORMAT_ONLY, None, ReasonCode.FORMAT_ONLY, DecisionEvidence((), ()))
    candidates, eligible = _collect_content(view.matching_text, registry)
    return resolve_candidates(candidates, matching_length=len(view.matching_text), registry=registry,
                              context_evidence=_collect_roles(view.matching_text, eligible))
