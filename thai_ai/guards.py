"""Recognize the contextual envelopes supported by the V0.1 contract."""

from dataclasses import dataclass
import re
from typing import Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from thai_ai.matching import _Match


_Scope = Literal["direct", "negated", "reported", "other_recipient", "specific_request"]


@dataclass(frozen=True)
class _ContextualEvidence:
    span: tuple[int, int]
    scope: _Scope


# Every pattern is matched against an entire clause. Captures are evidence
# spans, while the surrounding text identifies the scope of that evidence.
_CONTEXT_PATTERNS: tuple[tuple[_Scope, re.Pattern[str]], ...] = (
    ("negated", re.compile(r"(?:แต่ยัง)?ไม่ต้อง(ช่วย)(?:ครับ)?")),
    ("negated", re.compile(r"ไม่ได้(ขอบคุณครับ)")),
    ("reported", re.compile(r"เขาบอกว่า(สวัสดี)")),
    ("reported", re.compile(r"เขาพูดว่า “([^”\r\n]+)”")),
    ("other_recipient", re.compile(r"กรุณา(ทักทาย)เพื่อนให้หน่อย")),
    ("specific_request", re.compile(r"(ช่วย)บอกสูตร[^\r\n]+")),
)


def _contextual_evidence(clause: str) -> _ContextualEvidence | None:
    for scope, pattern in _CONTEXT_PATTERNS:
        found = pattern.fullmatch(clause)
        if found:
            return _ContextualEvidence(found.span(1), scope)
    return None


def passes_guard(match: "_Match") -> bool:
    """Only evidence directed to the bot without a blocking context qualifies."""
    return match.scope == "direct"
