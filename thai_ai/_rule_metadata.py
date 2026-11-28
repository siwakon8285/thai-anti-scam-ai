"""Shared field constraints for registered rules and public results."""

import re


INTENTS = frozenset({
    "GREETING", "BOT_IDENTITY", "BOT_CAPABILITIES", "THANKS", "FAREWELL",
    "HELP", "UNKNOWN", "EMPTY_INPUT",
})
_RULE_ID = re.compile(r"[a-z0-9][a-z0-9.-]*")


def is_rule_id(value: object) -> bool:
    return type(value) is str and _RULE_ID.fullmatch(value) is not None


def is_rule_intent(value: object) -> bool:
    return type(value) is str and value in INTENTS and value != "EMPTY_INPUT"
