"""Find rule evidence in a validated, normalized matching view."""

from dataclasses import dataclass

from thai_ai._rule_metadata import INTENTS, is_rule_id
from thai_ai.guards import _Scope, _contextual_evidence
from thai_ai.normalization import normalize_text


@dataclass(frozen=True)
class Rule:
    """An authored rule with fixed literal alternatives and optional contextual signals."""

    rule_id: str
    intent: str
    priority: int
    specificity: int
    phrases: tuple[str, ...]
    contextual_signals: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not is_rule_id(self.rule_id):
            raise RuntimeError("invalid_rule: invalid rule_id")
        if type(self.intent) is not str or self.intent not in INTENTS or self.intent == "EMPTY_INPUT":
            raise RuntimeError("invalid_rule: expected a rule-eligible V0.1 intent")
        if type(self.priority) is not int:
            raise RuntimeError("invalid_rule: priority must be an integer")
        if type(self.specificity) is not int or self.specificity not in (0, 1, 2):
            raise RuntimeError("invalid_rule: specificity must be 0, 1, or 2")
        if type(self.phrases) is not tuple or not self.phrases:
            raise RuntimeError("invalid_rule: at least one literal phrase is required")
        for phrases in (self.phrases, self.contextual_signals):
            if type(phrases) is not tuple:
                raise RuntimeError("invalid_rule: literal alternatives must be a tuple")
            for phrase in phrases:
                try:
                    view = normalize_text(phrase)
                except (TypeError, ValueError) as error:
                    raise RuntimeError("invalid_rule: invalid literal phrase") from error
                if view.kind != "content" or view.matching_text != phrase:
                    raise RuntimeError("invalid_rule: literal phrases must be normalized content")
            if len(set(phrases)) != len(phrases):
                raise RuntimeError("invalid_rule: duplicate literal phrase")


@dataclass(frozen=True)
class _Match:
    rule: Rule
    span: tuple[int, int]
    scope: _Scope


def _match_clause(clause: str, offset: int, rules: tuple[Rule, ...]) -> tuple[_Match, ...]:
    span = (offset, offset + len(clause))
    contextual = _contextual_evidence(clause)
    if contextual is None:
        return tuple(_Match(rule, span, "direct") for rule in rules if clause in rule.phrases)

    start, end = contextual.span
    phrase = clause[start:end]
    scoped = tuple(
        _Match(rule, (offset + start, offset + end), contextual.scope)
        for rule in rules if phrase in rule.phrases or phrase in rule.contextual_signals
    )
    if contextual.scope != "specific_request":
        return scoped

    # A rule may explicitly identify the whole request as out of scope.
    return scoped + tuple(
        _Match(rule, span, "direct") for rule in rules
        if rule.intent == "UNKNOWN" and clause in rule.phrases
    )


def _find_matches(matching_text: str, rules: tuple[Rule, ...]) -> tuple[_Match, ...]:
    """Find whole-clause matches or matches in a pair of evidenced clauses."""
    whole = _match_clause(matching_text, 0, rules)
    if any(match.scope != "direct" for match in whole):
        return whole

    first, separator, second = matching_text.partition(" ")
    if separator:
        left = _match_clause(first, 0, rules)
        if left:
            right = _match_clause(second, len(first) + 1, rules)
            if right:
                return whole + left + right
    return whole


# Literal alternatives come from the approved direct cases or independent
# clauses of approved composite cases. Context-only terms never match alone.
_DEFAULT_RULES = (
    Rule("greeting.direct", "GREETING", 0, 1,
         ("สวัสดีครับ", "สวัสดีตอนเช้าค่ะ", "หวัดดี", "ทักทายครับ"), ("สวัสดี", "ทักทาย")),
    Rule("identity.direct", "BOT_IDENTITY", 0, 1,
         ("คุณคือใคร", "คุณชื่ออะไร", "คุณเป็นใครครับ")),
    Rule("identity.bot-reference", "BOT_IDENTITY", 0, 2,
         ("นี่คือบอตอะไร", "คุณเป็นบอตใช่ไหม")),
    Rule("capabilities.direct", "BOT_CAPABILITIES", 0, 1,
         ("คุณทำอะไรได้บ้าง", "ขอบเขตความสามารถของคุณคืออะไร",
          "คุณช่วยเรื่องอะไรได้บ้าง", "คุณช่วยอะไรได้บ้าง")),
    Rule("capabilities.bot-reference", "BOT_CAPABILITIES", 0, 2,
         ("ระบบนี้รองรับการสนทนาเรื่องอะไร", "บอตนี้ทำอะไรได้บ้าง")),
    Rule("thanks.direct", "THANKS", 0, 1,
         ("ขอบคุณครับ", "ขอบใจนะ", "ขอบคุณมากค่ะ", "ขอบคุณสำหรับความช่วยเหลือ", "ขอบคุณ")),
    Rule("farewell.direct", "FAREWELL", 0, 1,
         ("ลาก่อน", "แล้วพบกันใหม่ครับ", "ขอตัวก่อนนะ", "ไปก่อนนะคะ")),
    Rule("help.general", "HELP", 0, 1,
         ("ช่วยด้วยครับ", "ขอความช่วยเหลือหน่อยค่ะ", "ช่วยฉันหน่อย",
          "ช่วยแนะนำวิธีเริ่มต้นหน่อย", "ช่วยเริ่มให้หน่อย"), ("ช่วย",)),
)
