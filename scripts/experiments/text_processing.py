"""Reproducible synthetic text probes for TASK-005-R1."""

import argparse
from functools import partial
from hashlib import sha256
import json
from pathlib import Path
import platform
import re
from statistics import median
import timeit
import tracemalloc
import unicodedata


# Fixed oracles declared before measurement. These are research examples.
FORMS = ("NFC", "NFKC", "NFD", "NFKD")
UNICODE_WHITE_SPACE_16 = (
    *range(0x0009, 0x000E), 0x0020, 0x0085, 0x00A0, 0x1680,
    *range(0x2000, 0x200B), 0x2028, 0x2029, 0x202F, 0x205F, 0x3000,
)
PYTHON_WHITESPACE_EXTRA = (0x001C, 0x001D, 0x001E, 0x001F)

# id, raw, changed outputs (all other forms preserve raw), rationale
NORMALIZATION_CASES = (
    ("N01", "สวัสดีครับ", {}, "Standard Thai and polite ending."),
    ("N02", "หวัดดีน้าา", {}, "Informal spelling and repeated letters stay distinct."),
    ("N03", "กำ", {"NFKC": "ก\u0e4d\u0e32", "NFKD": "ก\u0e4d\u0e32"}, "SARA AM compatibility decomposition."),
    ("N04", "ก\u0e4d\u0e32", {}, "Explicit components of SARA AM."),
    ("N05", "Cafe\u0301 ค่ะ", {"NFC": "Café ค่ะ", "NFKC": "Café ค่ะ"}, "Canonical composition in mixed text."),
    ("N06", "Café ค่ะ", {"NFD": "Cafe\u0301 ค่ะ", "NFKD": "Cafe\u0301 ค่ะ"}, "Canonical decomposition in mixed text."),
    ("N07", "a\u0301\u0323", {"NFC": "ạ\u0301", "NFKC": "ạ\u0301", "NFD": "a\u0323\u0301", "NFKD": "a\u0323\u0301"}, "Canonical combining-mark reordering."),
    ("N08", "Ｈｅｌｐ", {"NFKC": "Help", "NFKD": "Help"}, "Fullwidth letter folding."),
    ("N09", "ป้าย ①", {"NFKC": "ป้าย 1", "NFKD": "ป้าย 1"}, "Circled digit carries presentation evidence."),
    ("N10", "ก\u00a0ข", {"NFKC": "ก ข", "NFKD": "ก ข"}, "NBSP to space changes a boundary representation."),
    ("N11", "👩\u200d💻 ✈\ufe0f", {}, "Emoji ZWJ and variation selector."),
    ("N12", "ดู https://example.org/A?ref=๑๒.๕", {}, "Synthetic URL and Thai decimal notation."),
)
# id, left, right, expected canonical / compatibility equality, rationale
RELATION_CASES = (
    ("U01", "é", "e\u0301", True, True, "Canonical pair."),
    ("U02", "กำ", "ก\u0e4d\u0e32", False, True, "Thai compatibility pair."),
    ("U03", "①", "1", False, True, "Compatibility allows a fold even when form is evidence."),
    ("U04", "ไม่ช่วย", "ช่วย", False, False, "Negation stays distinct."),
)

# id, raw, expected strip, collapse, casefold, punctuation, isspace, UTF-8,
# flagged (offset, kind), rationale
HANDLING_CASES = (
    ("H01", "", "", "", "", "", False, True, (), "Empty str is distinct from str.isspace()."),
    ("H02", " \t\r\n", "", "", " \t\r\n", " \t\r\n", True, True, ((1, "control"), (2, "control"), (3, "control")), "ASCII whitespace controls."),
    ("H03", "\u00a0\u2003\u3000", "", "", "\u00a0\u2003\u3000", "\u00a0\u2003\u3000", True, True, (), "Unicode whitespace."),
    ("H04", "\x1c", "", "", "\x1c", "\x1c", True, True, ((0, "control"),), "Python whitespace outside Unicode White_Space."),
    ("H05", "\ufeff", "\ufeff", "\ufeff", "\ufeff", "\ufeff", False, True, ((0, "format"),), "U+FEFF already present in decoded str."),
    ("H06", " \u200b ", "\u200b", "\u200b", " \u200b ", " \u200b ", False, True, ((1, "format"),), "Trimming whitespace exposes ZWSP."),
    ("H07", "👩\u200d💻", "👩\u200d💻", "👩\u200d💻", "👩\u200d💻", "👩\u200d💻", False, True, ((1, "format"),), "ZWJ participates in an emoji sequence."),
    ("H08", "ก\u200cข", "ก\u200cข", "ก\u200cข", "ก\u200cข", "ก\u200cข", False, True, ((1, "format"),), "ZWNJ within text."),
    ("H09", "ก\x00ข", "ก\x00ข", "ก\x00ข", "ก\x00ข", "ก\x00ข", False, True, ((1, "control"),), "NUL can encode even if a contract forbids it."),
    ("H10", "\ud800", "\ud800", "\ud800", "\ud800", "\ud800", False, False, ((0, "surrogate"),), "Unpaired high surrogate."),
    ("H11", "ก\udfff", "ก\udfff", "ก\udfff", "ก\udfff", "ก\udfff", False, False, ((1, "surrogate"),), "Unpaired low surrogate after Thai text."),
    ("H12", "✈\ufe0f", "✈\ufe0f", "✈\ufe0f", "✈\ufe0f", "✈\ufe0f", False, True, ((1, "variation_selector"),), "VS16 changes presentation."),
    ("H13", " สวัสดี\tHelp  ", "สวัสดี\tHelp", "สวัสดี Help", " สวัสดี\thelp  ", " สวัสดี\tHelp  ", False, True, ((7, "control"),), "Trim versus internal collapse; mixed case."),
    ("H14", "เขาพูดว่า “สวัสดี!”", "เขาพูดว่า “สวัสดี!”", "เขาพูดว่า “สวัสดี!”", "เขาพูดว่า “สวัสดี!”", "เขาพูดว่า สวัสดี", False, True, (), "Punctuation deletion loses quotation and emphasis."),
    ("H15", "ไม่ต้องช่วย\nขอบคุณ", "ไม่ต้องช่วย\nขอบคุณ", "ไม่ต้องช่วย ขอบคุณ", "ไม่ต้องช่วย\nขอบคุณ", "ไม่ต้องช่วย\nขอบคุณ", False, True, ((11, "control"),), "Newline separates clauses."),
    ("H16", "\x1b", "\x1b", "\x1b", "\x1b", "\x1b", False, True, ((0, "control"),), "ESC is a non-whitespace control."),
    ("H17", "Straße", "Straße", "Straße", "strasse", "Straße", False, True, (), "Casefold can expand a code point."),
    ("H18", "https://example.org/A?ref=๑๒.๕", "https://example.org/A?ref=๑๒.๕", "https://example.org/A?ref=๑๒.๕", "https://example.org/a?ref=๑๒.๕", "https//exampleorg/Aref=๑๒๕", False, True, (), "URL path case and number punctuation are evidence."),
    ("H19", "\u202eก", "\u202eก", "\u202eก", "\u202eก", "\u202eก", False, True, ((0, "format"),), "Bidi override is flagged without deletion."),
    ("H20", "\ud83d\udc69", "\ud83d\udc69", "\ud83d\udc69", "\ud83d\udc69", "\ud83d\udc69", False, False, ((0, "surrogate"), (1, "surrogate")), "Two surrogate code points are not a decoded scalar."),
)
# id, left, right, expected comparison equality (None is an open question), rationale
MATCHING_PAIRS = (
    ("M01", "Café ค่ะ", "Cafe\u0301 ค่ะ", True, "Canonical Latin letters in the same Thai sentence."),
    ("M02", "ạ\u0301", "a\u0301\u0323", True, "Canonical mark order."),
    ("M03", "กำลังอ่าน", "ก\u0e4d\u0e32ลังอ่าน", True, "Same intended Thai reading in this example."),
    ("M04", "เมนู Help", "เมนู Ｈｅｌｐ", True, "The fictional menu label is width-insensitive."),
    ("M05", "สวัสดีครับ", "\u00a0สวัสดีครับ\t", True, "Outer whitespace does not change the utterance."),
    ("M06", "ขอบคุณ มากค่ะ", "ขอบคุณ  มากค่ะ", True, "This internal space run does not mark a clause."),
    ("M07", "เมนู Help", "เมนู help", True, "The fictional menu label is case-insensitive."),
    ("M08", "สวัสดีครับ", "สวัสดีครับ!", True, "Terminal emphatic mark does not change this greeting."),
    ("M09", "ป้าย ①", "ป้าย 1", False, "Label artwork distinguishes circled and plain digits."),
    ("M10", "https://example.org/A", "https://example.org/a", False, "Synthetic URL paths have distinct case."),
    ("M11", "ราคา ๑๒.๕ บาท", "ราคา ๑๒๕ บาท", False, "Removing decimal point changes value."),
    ("M12", "เขาพูดว่า “สวัสดี”", "เขาพูดว่า สวัสดี", False, "Quotation marks are explicit evidence boundaries."),
    ("M13", "ช่วยครับ", "ไม่ต้องช่วยครับ", False, "Negation changes the request."),
    ("M14", "ไม่ต้องช่วย\nขอบคุณ", "ไม่ต้องช่วย ขอบคุณ", False, "Explicit line boundary is evidence to retain here."),
    ("M15", "👩\u200d💻", "👩💻", False, "Emoji sequence and separate characters differ."),
    ("M16", "✈\ufe0f", "✈", False, "Explicit presentation selector is evidence to retain."),
    ("M17", "หวัดดี", "หวัดดีน้าา", None, "Supported informal intensification awaits owner review."),
    ("M18", "สวัสดี", "สวัส\u200bดี", None, "ZWSP inside a word needs a boundary policy."),
    ("M19", "สวัสดี", "\ufeffสวัสดี", None, "Treatment of leading U+FEFF after decoding needs a policy."),
)
# Case ID, regex, raw, expected match after transform, rationale
REGEX_PROBES = (
    ("P01", "Café ค่ะ", "Cafe\u0301 ค่ะ", True, "Composition may recover a literal substring."),
    ("P02", "กำลัง", "ก\u0e4d\u0e32ลังอ่าน", True, "Composed Thai literal needs the same representation."),
    ("P03", r"\Aสวัสดีครับ\Z", "\u00a0สวัสดีครับ\t", True, "Trim may recover an anchored literal."),
    ("P04", "ไม่ต้องช่วย", "ไม่ต้องช่วย\nขอบคุณ", True, "Negation should remain visible."),
    ("P05", "“สวัสดี”", "เขาพูดว่า “สวัสดี”", True, "Preserve literal quotation boundaries."),
    ("P06", r"example\.org/A", "ดู https://example.org/A", True, "Preserve URL case and separators."),
    ("P07", "๑๒๕", "ราคา ๑๒.๕ บาท", False, "Punctuation deletion must not create another numeric literal."),
    ("P08", r"\Aช่วยครับ\Z", "ไม่ต้องช่วยครับ", False, "Anchored probe must not match a negated request."),
)
# id, raw, reference segmentation, expected split(), expected regex words
SEGMENTATION_CASES = (
    ("S01", "ภาษาไทย", ("ภาษา", "ไทย"), ("ภาษาไทย",), ("ภาษาไทย",)),
    ("S02", "สวัสดีครับ", ("สวัสดี", "ครับ"), ("สวัสดีครับ",), ("สว", "สด", "คร", "บ")),
    ("S03", "ภาษาไทย Help", ("ภาษา", "ไทย", "Help"), ("ภาษาไทย", "Help"), ("ภาษาไทย", "Help")),
)

PUNCTUATION = re.compile(r"""[.!?,:"“”‘’]""")
WORD_CHUNKS = re.compile(r"\w+")
FLAG_CATEGORIES = {"Cc": "control", "Cf": "format", "Cs": "surrogate"}
SIZES = (128, 512, 2048, 8192, 32768)
PERF_INPUTS = {
    "thai": " สวัสดีครับ กำลังอ่านเอกสาร ไม่ต้องช่วยตอนนี้ค่ะ ",
    "english": "  Please review https://example.org/A?ref=12.5.\tThank you! ",
    "mixed": "  เมนู Ｈｅｌｐ\tCafe\u0301 ค่ะ ราคา ๑๒.๕ บาท ",
    "unicode_complex": " \u00a0ก\u0e4d\u0e32 a\u0301\u0323 👩\u200d💻 ✈\ufe0f \u200b \u200c \ufeff \u202e ① ",
}
WARMUP_CALLS = 8
TIME_ROUNDS = 7
ALLOCATION_ROUNDS = 3


def raw(text):
    return text


def collapse_whitespace(text):
    return " ".join(text.split())


def remove_selected_punctuation(text):
    return PUNCTUATION.sub("", text)


def scan_characters(text):
    flags = []
    for index, char in enumerate(text):
        category = FLAG_CATEGORIES.get(unicodedata.category(char))
        if category:
            flags.append((index, category))
        elif (
            "\ufe00" <= char <= "\ufe0f"
            or "\U000e0100" <= char <= "\U000e01ef"
            or char in "\u180b\u180c\u180d\u180f"
        ):
            flags.append((index, "variation_selector"))
    return flags


def trim_and_normalize(form, text):
    return unicodedata.normalize(form, text.strip())


def trim_nfkc_casefold(text):
    return trim_and_normalize("NFKC", text).casefold()


def utf8_encode(text):
    return text.encode("utf-8", errors="strict")


def text_view(text):
    # Avoid serializing lone surrogates as JSON strings. Code points preserve them.
    return {
        "text": None if any("\ud800" <= char <= "\udfff" for char in text) else text,
        "code_points": [f"U+{ord(char):04X}" for char in text],
        "length": len(text),
    }


NORMALIZERS = {
    "raw": raw,
    **{form: partial(unicodedata.normalize, form) for form in FORMS},
}
MATCH_TRANSFORMS = {
    **NORMALIZERS,
    "strip": str.strip,
    "collapse": collapse_whitespace,
    "casefold": str.casefold,
    "drop_selected_punctuation": remove_selected_punctuation,
    "strip+NFC": partial(trim_and_normalize, "NFC"),
    "strip+NFKC": partial(trim_and_normalize, "NFKC"),
    "strip+NFKC+casefold": trim_nfkc_casefold,
}
PERF_OPERATIONS = {
    **MATCH_TRANSFORMS,
    "isspace": str.isspace,
    "scan_characters": scan_characters,
    "strict_utf8_encode": utf8_encode,
    "whitespace_split": str.split,
    "regex_word_chunks": WORD_CHUNKS.findall,
}


def normalization_experiment():
    cases = []
    for case_id, text, changes, rationale in NORMALIZATION_CASES:
        results = {}
        for name, transform in NORMALIZERS.items():
            expected = changes.get(name, text)
            observed = transform(text)
            idempotent = transform(observed) == observed
            results[name] = {
                "expected": {"view": text_view(expected), "idempotent": True},
                "observed": {
                    "view": text_view(observed),
                    "equals_raw": observed == text,
                    "length_delta": len(observed) - len(text),
                    "idempotent": idempotent,
                },
                "matches_expected": observed == expected and idempotent,
            }
        cases.append({
            "id": case_id, "rationale": rationale, "input": text_view(text), "results": results,
        })

    relations = []
    for case_id, left, right, canonical, compatibility, rationale in RELATION_CASES:
        expected = {"raw": left == right, "NFC": canonical, "NFD": canonical,
                    "NFKC": compatibility, "NFKD": compatibility}
        observed = {name: op(left) == op(right) for name, op in NORMALIZERS.items()}
        relations.append({
            "id": case_id, "rationale": rationale, "left": text_view(left), "right": text_view(right),
            "expected": expected, "observed": observed, "matches_expected": observed == expected,
        })

    return {
        "method": {
            "case_unit": "Exact output and idempotence per form; one check per relation row.",
            "canonical_equivalence": "Equality under NFC and NFD.",
            "compatibility_equivalence": "Equality under NFKC and NFKD; not an application policy.",
        },
        "cases": cases,
        "relations": relations,
        "checks": len(cases) * len(NORMALIZERS) + len(relations),
        "mismatches": sum(
            not result["matches_expected"] for case in cases for result in case["results"].values()
        ) + sum(not relation["matches_expected"] for relation in relations),
    }


def observe_handling(text):
    try:
        utf8_encode(text)
        encoding_error = None
    except UnicodeEncodeError as error:
        encoding_error = {"type": type(error).__name__, "start": error.start, "end": error.end}
    return {
        "strip": str.strip(text),
        "collapse": collapse_whitespace(text),
        "casefold": str.casefold(text),
        "drop_selected_punctuation": remove_selected_punctuation(text),
        "isspace": text.isspace(),
        "utf8_encodes": encoding_error is None,
        "flags": scan_characters(text),
    }, encoding_error


def show_handling(result):
    return {key: text_view(value) if isinstance(value, str) else value for key, value in result.items()}


def handling_experiment():
    whitespace = [code for code in range(0x110000) if chr(code).isspace()]
    trimmed = [code for code in range(0x110000) if not chr(code).strip()]
    expected_whitespace = sorted((*UNICODE_WHITE_SPACE_16, *PYTHON_WHITESPACE_EXTRA))
    cases = []
    for case_id, text, strip, collapse, fold, punctuation, space, utf8, flags, rationale in HANDLING_CASES:
        expected = {
            "strip": strip, "collapse": collapse, "casefold": fold,
            "drop_selected_punctuation": punctuation, "isspace": space,
            "utf8_encodes": utf8, "flags": list(flags),
        }
        observed, encoding_error = observe_handling(text)
        cases.append({
            "id": case_id, "rationale": rationale, "input": text_view(text),
            "expected": show_handling(expected), "observed": show_handling(observed),
            "encoding_error": encoding_error, "matches_expected": observed == expected,
        })

    segmentation = []
    for case_id, text, reference, split, regex in SEGMENTATION_CASES:
        expected = {"whitespace_split": list(split), "regex_word_chunks": list(regex)}
        observed = {"whitespace_split": text.split(), "regex_word_chunks": WORD_CHUNKS.findall(text)}
        segmentation.append({
            "id": case_id, "input": text_view(text), "illustrative_manual_words": reference,
            "rationale": "Check whether generic Python tokens coincide with illustrative Thai words.",
            "expected": expected, "observed": observed, "matches_expected": observed == expected,
        })

    return {
        "method": {
            "collapse": "Split on Python whitespace, then join with one ASCII space.",
            "punctuation_regex": PUNCTUATION.pattern,
            "scan": "Record zero-based offsets for Cc, Cf, Cs and variation selectors; no deletion.",
            "encoding": "Encode as UTF-8 with strict errors; format or control characters can still encode.",
            "word_chunks_regex": WORD_CHUNKS.pattern,
        },
        "whitespace": {
            "unicode_white_space_16": UNICODE_WHITE_SPACE_16,
            "expected_python": expected_whitespace,
            "observed_isspace": whitespace,
            "observed_strip_to_empty_single_code_point": trimmed,
            "python_only": sorted(set(whitespace) - set(UNICODE_WHITE_SPACE_16)),
            "matches_expected": whitespace == trimmed == expected_whitespace,
        },
        "cases": cases,
        "segmentation": segmentation,
        "checks": 1 + len(cases) + len(segmentation),
        "mismatches": sum(not case["matches_expected"] for case in (*cases, *segmentation))
        + (whitespace != trimmed or whitespace != expected_whitespace),
    }


def matching_experiment():
    cases = []
    for case_id, left, right, expected, rationale in MATCHING_PAIRS:
        results = {}
        for name, transform in MATCH_TRANSFORMS.items():
            left_view, right_view = transform(left), transform(right)
            results[name] = {"left": left_view, "right": right_view, "equal": left_view == right_view}
        cases.append({
            "id": case_id, "rationale": rationale, "left": left, "right": right,
            "expected_equivalence": expected, "results": results,
        })

    probes = []
    for case_id, expression, text, expected, rationale in REGEX_PROBES:
        pattern = re.compile(expression)
        results = {}
        for name, transform in MATCH_TRANSFORMS.items():
            view = transform(text)
            match = pattern.search(view)
            results[name] = {
                "view": view, "matched": match is not None, "span": match.span() if match else None,
            }
        probes.append({
            "id": case_id, "rationale": rationale, "regex": expression, "input": text,
            "expected_match": expected, "results": results,
        })

    equivalent = [case for case in cases if case["expected_equivalence"] is True]
    distinct = [case for case in cases if case["expected_equivalence"] is False]
    summary = {}
    for name in MATCH_TRANSFORMS:
        recovered = sum(case["results"][name]["equal"] for case in equivalent)
        collisions = sum(case["results"][name]["equal"] for case in distinct)
        summary[name] = {
            "recovered_equivalences": recovered,
            "missed_equivalences": len(equivalent) - recovered,
            "unwanted_collisions": collisions,
            "protected_distinctions_retained": len(distinct) - collisions,
            "regex_expectations_met": sum(
                probe["results"][name]["matched"] == probe["expected_match"] for probe in probes
            ),
        }
    return {
        "method": {
            "comparison": "Compare transformed views; keep original synthetic inputs separately.",
            "regex": "Search the transformed view with fixed probes; spans refer to that view.",
            "information_preservation": "Count non-colliding protected pairs; review literal probes separately.",
            "scope": "Three open pairs are observed and excluded from the pair scores.",
        },
        "cases": cases, "regex_probes": probes, "summary": summary,
        "denominators": {
            "equivalent_pairs": len(equivalent), "protected_distinctions": len(distinct),
            "open_question_pairs_excluded": len(cases) - len(equivalent) - len(distinct),
            "regex_probes": len(probes),
        },
    }


def timing_samples(operation, text, number):
    for _ in range(WARMUP_CALLS):
        operation(text)
    timer = timeit.Timer(partial(operation, text))
    return [seconds * 1e9 / number for seconds in timer.repeat(repeat=TIME_ROUNDS, number=number)]


def allocation_samples(operation, text):
    samples = []
    for _ in range(ALLOCATION_ROUNDS):
        tracemalloc.start()
        try:
            baseline = tracemalloc.get_traced_memory()[0]
            tracemalloc.reset_peak()
            result = operation(text)
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        samples.append(peak - baseline)
        del result
    return samples


def performance_experiment():
    if tracemalloc.is_tracing():
        raise RuntimeError("Run the experiment with tracemalloc disabled at Python startup.")

    inputs = []
    measurements = []
    for name, seed in PERF_INPUTS.items():
        for size in SIZES:
            text = (seed * ((size + len(seed) - 1) // len(seed)))[:size]
            number = 100 if size <= 2048 else 25
            inputs.append({
                "type": name, "code_points": len(text), "utf8_bytes": len(utf8_encode(text)),
                "utf8_sha256": sha256(utf8_encode(text)).hexdigest(), "iterations_per_round": number,
            })
            for label, operation in PERF_OPERATIONS.items():
                times = timing_samples(operation, text, number)
                allocations = allocation_samples(operation, text)
                middle = median(times)
                measurements.append({
                    "type": name, "code_points": size, "operation": label,
                    "nanoseconds_per_call": [round(value, 2) for value in times],
                    "median_ns": round(middle, 2),
                    "median_absolute_deviation_ns": round(median(abs(value - middle) for value in times), 2),
                    "peak_bytes_samples": allocations, "max_peak_traced_bytes": max(allocations),
                })
    return {
        "method": {
            "input_seeds": PERF_INPUTS,
            "generation": "Repeat seed and slice to exact code-point length; may end within a sequence.",
            "warmup_calls": WARMUP_CALLS, "timing_rounds": TIME_ROUNDS,
            "timer": "timeit (perf_counter), GC disabled during timing, callable overhead included.",
            "allocation_rounds": ALLOCATION_ROUNDS,
            "allocation_metric": "tracemalloc peak minus baseline, one operation per separately traced run; "
            "input and callable setup allocated outside tracing; retains output through peak reading.",
            "iterations_per_round": "100 for <= 2048 code points, otherwise 25.",
            "performance_scope": "Measurements of individual text operations, not process RAM or engine limits.",
        },
        "inputs": inputs,
        "measurements": measurements,
    }


def fixture_sha256():
    frozen = (
        NORMALIZATION_CASES, RELATION_CASES, UNICODE_WHITE_SPACE_16, PYTHON_WHITESPACE_EXTRA,
        HANDLING_CASES, MATCHING_PAIRS, REGEX_PROBES, SEGMENTATION_CASES,
    )
    data = json.dumps(frozen, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return sha256(data.encode("ascii")).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--behavior-only", action="store_true", help="Omit EXP-004 timing and allocation measurements.")
    args = parser.parse_args()

    normalization = normalization_experiment()
    handling = handling_experiment()
    report = {
        "task": "TASK-005-R1",
        "report_version": "v0.1",
        "environment": {
            "python": platform.python_version(), "unicode_database": unicodedata.unidata_version,
            "python_implementation": platform.python_implementation(),
            "system": platform.system(), "machine": platform.machine(), "macos": platform.mac_ver()[0],
        },
        "synthetic_fixture_sha256": fixture_sha256(),
        "script_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "EXP-001": normalization,
        "EXP-002": handling,
        "EXP-003": matching_experiment(),
    }
    if not args.behavior_only:
        report["EXP-004"] = performance_experiment()
    print(json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2))
    return int(bool(normalization["mismatches"] or handling["mismatches"]))


if __name__ == "__main__":
    raise SystemExit(main())
