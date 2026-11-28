"""Behavioral tests for matching text and the early input categories."""

import unittest

from tests.runtime_fixtures import load_cases
from thai_ai.normalization import normalize_text


class NormalizationTests(unittest.TestCase):
    def test_mandatory_matching_views(self):
        cases = load_cases("normalization")
        self.assertEqual(len(cases), 17)
        for case in cases:
            raw = case["fixture"]["value"]
            expected = case["expected_outcome"]
            with self.subTest(case_id=case["case_id"]):
                normalized = normalize_text(raw)
                self.assertEqual(normalized.matching_text, expected["value"])
                if expected["preserve_raw"]:
                    self.assertEqual(normalized.raw_text, raw)
                if expected["idempotent"]:
                    self.assertEqual(
                        normalize_text(normalized.matching_text).matching_text,
                        normalized.matching_text,
                    )

    def test_early_paths_of_intent_cases(self):
        cases = [
            case for case in load_cases("intent")
            if case["expected_outcome"]["path"] in ("empty", "format_only")
        ]
        self.assertEqual(len(cases), 11)
        for case in cases:
            with self.subTest(case_id=case["case_id"]):
                normalized = normalize_text(case["fixture"]["value"])
                self.assertEqual(normalized.kind, case["expected_outcome"]["path"])

    def test_content_paths_of_selected_intent_cases(self):
        cases = {case["case_id"]: case for case in load_cases("intent")}
        for case_id in ("INT-12", "INT-13", "OPEN-BOM-PREFIX", "OPEN-ZWSP-IN-WORD",
                        "OPEN-COMBINING-ONLY"):
            with self.subTest(case_id=case_id):
                raw = cases[case_id]["fixture"]["value"]
                normalized = normalize_text(raw)
                self.assertEqual(normalized.kind, "content")
                self.assertEqual(normalized.matching_text, raw)

        padded = cases["INT-08"]
        reference_id = padded["same_result_as"]
        with self.subTest(case_id=padded["case_id"], reference_id=reference_id):
            self.assertEqual(
                normalize_text(padded["fixture"]["value"]).matching_text,
                normalize_text(cases[reference_id]["fixture"]["value"]).matching_text,
            )

    def test_validates_before_trimming_or_classification(self):
        with self.assertRaisesRegex(ValueError, r"disallowed_control.*offset 1 \("):
            normalize_text(" \x0b")
        with self.assertRaisesRegex(ValueError, r"bidi_control.*offset 1 \("):
            normalize_text("\u200b\u202e")
        # NFC would compose e + acute and shift the invalid raw code point.
        with self.assertRaisesRegex(ValueError, r"^surrogate.*offset 6 \("):
            normalize_text(" Cafe\u0301\udfff\u202e")
        with self.assertRaisesRegex(TypeError, "invalid_type"):
            normalize_text(None)

    def test_approved_whitespace_and_internal_spacing(self):
        whitespace = "\t\n\r \u00a0\u1680"
        whitespace += "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
        whitespace += "\u2028\u2029\u202f\u205f\u3000"
        self.assertEqual(len(whitespace), 22)
        for char in whitespace:
            with self.subTest(code_point=ord(char)):
                normalized = normalize_text(char)
                self.assertEqual((normalized.matching_text, normalized.kind), ("", "empty"))
        self.assertEqual(normalize_text("  ก\t \u00a0ข\r\nค  ").matching_text, "ก\t \u00a0ข\r\nค")

    def test_format_only_uses_cf_and_variation_selector_property(self):
        for text in ("\u00ad", "\u200c\u200d", "\u180b", "\u180d", "\u180f",
                     "\ufe00", "\ufe0f", "\U000e0100", "\U000e01ef", "\u200b \t\ufeff"):
            with self.subTest(text=text):
                normalized = normalize_text(text)
                self.assertEqual((normalized.matching_text, normalized.kind), (text, "format_only"))
        for text in ("\u0301", "ข\ufe0f", "👩‍💻", "\u17b4", "\u180a", "\ufe10",
                     "\U000e00ff", "\U000e01f0"):
            with self.subTest(text=text):
                self.assertEqual(normalize_text(text).kind, "content")
