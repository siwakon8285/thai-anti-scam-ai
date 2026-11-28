"""Raw input validation for the V0.1 runtime."""

from unicodedata import category


# Bidi_Control from Unicode 16.0.0 PropList.txt.
_BIDI_CONTROLS = frozenset({
    0x061C, 0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x2066, 0x206A),
})
_ALLOWED_CONTROLS = frozenset("\t\n\r")


def validate_input(text: object) -> None:
    """Raise TypeError for non-exact str or ValueError at the first invalid code point."""
    if type(text) is not str:
        raise TypeError("invalid_type: expected built-in str")

    for offset, char in enumerate(text):
        code_point = ord(char)
        if 0xD800 <= code_point <= 0xDFFF:
            reason = "surrogate"
        elif category(char) == "Cc" and char not in _ALLOWED_CONTROLS:
            reason = "disallowed_control"
        elif code_point in _BIDI_CONTROLS:
            reason = "bidi_control"
        else:
            continue
        raise ValueError(f"{reason} at code-point offset {offset} (U+{code_point:04X})")
