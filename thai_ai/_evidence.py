"""Evidence types for guarded matches and approved context pairs."""

from dataclasses import dataclass
from enum import StrEnum


type Span = tuple[int, int]


class EvidenceRole(StrEnum):
    INTRODUCTORY = "INTRODUCTORY"
    PRIMARY_QUESTION = "PRIMARY_QUESTION"
    COURTESY = "COURTESY"
    PRIMARY_REQUEST = "PRIMARY_REQUEST"


class EvidenceSource(StrEnum):
    C08_INTRO_QUESTION = "C08_INTRO_QUESTION"
    R6_MIXED_STARTUP_REQUEST = "R6_MIXED_STARTUP_REQUEST"


@dataclass(frozen=True)
class RoleEvidence:
    role: EvidenceRole
    rule_id: str
    span: Span


@dataclass(frozen=True)
class ContextEvidence:
    source: EvidenceSource
    context_span: Span
    roles: tuple[RoleEvidence, RoleEvidence]


_QUESTION_INTENTS = frozenset({"BOT_IDENTITY", "BOT_CAPABILITIES"})


def roles_for_source(source: EvidenceSource) -> tuple[EvidenceRole, EvidenceRole]:
    if source is EvidenceSource.C08_INTRO_QUESTION:
        return EvidenceRole.INTRODUCTORY, EvidenceRole.PRIMARY_QUESTION
    return EvidenceRole.COURTESY, EvidenceRole.PRIMARY_REQUEST
