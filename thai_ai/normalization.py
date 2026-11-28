"""Build the V0.1 matching representation."""

from dataclasses import dataclass, field
from typing import Literal
from unicodedata import category, normalize

from thai_ai.validation import validate_input


# Variation_Selector from Unicode 16.0.0 PropList.txt.
_VARIATION_SELECTORS = frozenset({
    *range(0x180B, 0x180E), 0x180F, *range(0xFE00, 0xFE10), *range(0xE0100, 0xE01F0),
})


@dataclass(frozen=True)
class _NormalizedText:
    raw_text: str = field(repr=False)
    matching_text: str = field(repr=False)
    kind: Literal["empty", "format_only", "content"]


def normalize_text(text: str) -> _NormalizedText:
    """Validate raw text, classify its shape, and create the strip + NFC view."""
    validate_input(text)
    trimmed = text.strip()
    if not trimmed:
        kind = "empty"
    elif all(
        char.isspace() or category(char) == "Cf" or ord(char) in _VARIATION_SELECTORS
        for char in trimmed
    ):
        kind = "format_only"
    else:
        kind = "content"
    return _NormalizedText(text, normalize("NFC", trimmed), kind)
