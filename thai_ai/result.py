"""Result fields for the V0.1 runtime."""

from dataclasses import dataclass
import re


_INTENTS = frozenset({
    "GREETING", "BOT_IDENTITY", "BOT_CAPABILITIES", "THANKS", "FAREWELL",
    "HELP", "UNKNOWN", "EMPTY_INPUT",
})
_RULE_ID = re.compile(r"[a-z0-9][a-z0-9.-]*")


@dataclass(frozen=True)
class Result:
    """Validate result fields at construction and leave JSON encoding to the caller."""

    intent: str
    response: str
    rule_id: str | None

    def __post_init__(self) -> None:
        if type(self.intent) is not str or self.intent not in _INTENTS:
            raise RuntimeError("invalid_result: intent must be a V0.1 taxonomy value")

        if type(self.response) is not str or not self.response or self.response.isspace():
            raise RuntimeError("invalid_result: response must be a nonblank built-in str")
        if any(0xD800 <= ord(char) <= 0xDFFF for char in self.response):
            raise RuntimeError("invalid_result: response must contain only Unicode scalar values")

        if self.rule_id is None:
            if self.intent not in ("EMPTY_INPUT", "UNKNOWN"):
                raise RuntimeError("invalid_result: rule_id is required for this intent")
        elif self.intent == "EMPTY_INPUT":
            raise RuntimeError("invalid_result: rule_id must be None for EMPTY_INPUT")
        elif type(self.rule_id) is not str or not _RULE_ID.fullmatch(self.rule_id):
            raise RuntimeError("invalid_result: rule_id must match [a-z0-9][a-z0-9.-]*")
