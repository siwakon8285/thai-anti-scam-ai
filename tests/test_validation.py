"""Behavioral tests for the approved raw input policy."""

import re
import unittest

from tests.runtime_fixtures import load_cases
from thai_ai.validation import validate_input


class StringSubclass(str):
    def __iter__(self):
        raise AssertionError("validation must reject the subclass before inspecting it")


class InputValidationTests(unittest.TestCase):
    def test_mandatory_input_exceptions(self):
        cases = load_cases("input_validation")
        self.assertEqual(len(cases), 36)
        for case in cases:
            fixture = case["fixture"]
            expected = case["expected_outcome"]
            with self.subTest(case_id=case["case_id"]):
                match fixture["kind"]:
                    case "text" | "json_value":
                        value = fixture["value"]
                    case "str_subclass":
                        value = StringSubclass(fixture["value"])
                    case "bytes_hex":
                        value = bytes.fromhex(fixture["hex"])
                    case "code_points":
                        value = "".join(map(chr, fixture["values"]))
                    case other:
                        self.fail(f"Unexpected input fixture kind: {other}")
                error_type = {"TypeError": TypeError, "ValueError": ValueError}[expected["type"]]
                with self.assertRaises(error_type) as caught:
                    validate_input(value)
                self.assertIs(type(caught.exception), error_type)
                message = str(caught.exception)
                self.assertRegex(message, rf"^{re.escape(expected['reason'])}\b")
                if "code_point_offset" in expected:
                    self.assertIn(f"offset {expected['code_point_offset']} (", message)

    def test_accepted_text_including_rtl_and_control_boundaries(self):
        for text in ("", "\t\r\n", "ก\tข\r\nค", "مرحبا שלום", "👩‍💻", "\ud7ff\ue000",
                     "\u00a0\u3000", "\u00ad\ufeff\u200b\u200c\u200d\ufe0f"):
            with self.subTest(text=text):
                self.assertIsNone(validate_input(text))

    def test_disallowed_c1_boundaries_and_offset_after_supplementary_character(self):
        for char in ("\x7f", "\x80", "\x9f"):
            with self.subTest(char=char):
                with self.assertRaisesRegex(ValueError, r"disallowed_control.*offset 2 \(") as caught:
                    validate_input("👩ก" + char + "ข้อความสมมติ")
                self.assertNotIn("ข้อความสมมติ", str(caught.exception))
