"""Render approved V0.1 responses from a decision record."""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType

from thai_ai._rule_metadata import INTENTS
from thai_ai.matching import _DEFAULT_RULES
from thai_ai.registry import RuleRegistry
from thai_ai.resolver import DecisionEvidence, DecisionRecord, _validate_membership
from thai_ai.result import Result


type _TemplateKey = tuple[str, str]

_REQUIRED_TEMPLATES = frozenset((intent, "matched") for intent in INTENTS - {"EMPTY_INPUT"}) | {
    ("UNKNOWN", "no_match"), ("UNKNOWN", "ambiguity"), ("UNKNOWN", "format_only"),
    ("EMPTY_INPUT", "empty"),
}

# Verbatim TASK-005-R6 text. The regression JSON remains the independent test oracle.
_APPROVED_TEXTS = MappingProxyType({
    ("GREETING", "matched"): "สวัสดีครับ ยินดีที่ได้คุยด้วยครับ",
    ("BOT_IDENTITY", "matched"): "ผมเป็นต้นแบบบอตภาษาไทยแบบใช้กฎของโครงการ thai-anti-scam-ai ครับ",
    ("BOT_CAPABILITIES", "matched"): (
        "ผมเป็นต้นแบบบอตภาษาไทยแบบใช้กฎ รองรับการทักทาย แนะนำตัว และสนทนาพื้นฐาน "
        "รวมถึงสอบถามรายละเอียดเมื่อคุณต้องการความช่วยเหลือ รุ่นนี้ยังไม่สามารถตรวจจับการหลอกลวงได้ครับ"
    ),
    ("THANKS", "matched"): "ยินดีครับ",
    ("FAREWELL", "matched"): "แล้วพบกันใหม่ครับ",
    ("HELP", "matched"): "อยากให้ช่วยเรื่องอะไรครับ เล่าเพิ่มได้เลย เช่น อยากรู้ว่าบอตนี้ทำอะไรได้บ้าง",
    ("UNKNOWN", "matched"): "ผมยังตอบเรื่องนี้ไม่ได้ครับ ลองบอกได้ไหมว่าต้องการให้ช่วยเรื่องอะไร",
    ("UNKNOWN", "no_match"): "ผมยังตอบเรื่องนี้ไม่ได้ครับ ลองบอกได้ไหมว่าต้องการให้ช่วยเรื่องอะไร",
    ("UNKNOWN", "ambiguity"): "ข้อความนี้อาจมีหลายคำขอครับ คุณต้องการให้ช่วยเรื่องใดเป็นหลักครับ?",
    ("UNKNOWN", "format_only"): "ข้อความนี้ยังตีความไม่ได้ครับ กรุณาพิมพ์รายละเอียดเพิ่มเติมครับ",
    ("EMPTY_INPUT", "empty"): "กรุณาพิมพ์ข้อความก่อนครับ",
})


@dataclass(frozen=True, init=False)
class _TemplateRegistry:
    """A complete, read-only catalog of the approved response paths."""

    _texts: Mapping[_TemplateKey, str]

    def __init__(self, texts: Mapping[_TemplateKey, str]) -> None:
        if not isinstance(texts, Mapping):
            raise RuntimeError("invalid_template_configuration: expected a template mapping")
        snapshot = dict(texts)
        if snapshot.keys() - _REQUIRED_TEMPLATES:
            raise RuntimeError("invalid_template_configuration: unexpected response path")
        missing = _REQUIRED_TEMPLATES - snapshot.keys()
        if missing:
            intent, path = min(missing)
            raise RuntimeError(f"missing_template: {intent}/{path}")
        for (intent, path), text in snapshot.items():
            if (type(text) is not str or not text.strip()
                    or any(0xD800 <= ord(char) <= 0xDFFF for char in text)
                    or text != _APPROVED_TEXTS[intent, path]):
                raise RuntimeError(f"invalid_template_configuration: {intent}/{path}")
        object.__setattr__(self, "_texts", MappingProxyType(snapshot))

    def get(self, intent: str, path: str) -> str:
        try:
            return self._texts[intent, path]
        except KeyError as error:
            raise RuntimeError(f"missing_template: {intent}/{path}") from error


_TEMPLATES = _TemplateRegistry(_APPROVED_TEXTS)
_DEFAULT_REGISTRY = RuleRegistry(_DEFAULT_RULES)


def select_response(decision: DecisionRecord, *, registry: RuleRegistry = _DEFAULT_REGISTRY) -> Result:
    """Validate a decision and render its path using the rules for that decision."""
    if type(registry) is not RuleRegistry:
        raise RuntimeError("invalid_configuration: expected a validated rule registry")
    if type(decision) is not DecisionRecord or type(decision.evidence) is not DecisionEvidence:
        raise RuntimeError("invalid_decision: expected a decision record with evidence")

    # Reuse the resolver's invariant checks at the public Result boundary.
    checked = replace(decision, evidence=replace(decision.evidence))
    _validate_membership(checked.evidence.candidates, registry)
    response = _TEMPLATES.get(checked.intent, checked.path)
    return Result(checked.intent, response, checked.rule_id)
