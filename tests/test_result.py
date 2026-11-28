"""Behavioral tests for the result object and its JSON wire fields."""

from dataclasses import FrozenInstanceError, asdict
import json
import unittest

from tests.runtime_fixtures import load_cases
from thai_ai.result import Result


class ResultTests(unittest.TestCase):
    def test_mandatory_serialization_cases(self):
        cases = [case for case in load_cases("response") if case["fixture"]["kind"] == "wire_fields"]
        self.assertEqual(len(cases), 3)
        for case in cases:
            expected = case["expected_outcome"]["fields"]
            with self.subTest(case_id=case["case_id"]):
                fields = asdict(Result(**case["fixture"]["fields"]))
                self.assertEqual(fields, expected)
                payload = json.dumps(fields, ensure_ascii=False, allow_nan=False)
                self.assertEqual(json.loads(payload.encode("utf-8")), expected)
                if expected["rule_id"] is None:
                    self.assertIn('"rule_id": null', payload)

    def test_mandatory_invalid_result(self):
        cases = [case for case in load_cases("response") if case["fixture"]["kind"] == "invalid_result"]
        self.assertEqual([case["case_id"] for case in cases], ["ERR-OUTPUT"])
        case = cases[0]
        expected = case["expected_outcome"]
        with self.subTest(case_id=case["case_id"]):
            with self.assertRaisesRegex(RuntimeError, expected["reason"]) as caught:
                Result(**case["fixture"]["values"])
            self.assertEqual(type(caught.exception).__name__, expected["type"])

    def test_all_eight_intents_and_matching_rule_shape(self):
        for intent in ("GREETING", "BOT_IDENTITY", "BOT_CAPABILITIES", "THANKS", "FAREWELL", "HELP"):
            with self.subTest(intent=intent):
                self.assertEqual(Result(intent, "ข้อความสมมติ", "a0.test-1").intent, intent)
                with self.assertRaisesRegex(RuntimeError, "invalid_result.*rule_id"):
                    Result(intent, "ข้อความสมมติ", None)
        self.assertEqual(Result("UNKNOWN", "ข้อความสมมติ", "0").rule_id, "0")
        self.assertIsNone(Result("UNKNOWN", "ข้อความสมมติ", None).rule_id)
        self.assertIsNone(Result("EMPTY_INPUT", "ข้อความสมมติ", None).rule_id)

    def test_invalid_field_types_and_values(self):
        class StringSubclass(str):
            pass

        for intent in (None, 0, [], "", "unknown", "UNKNOWN ", StringSubclass("UNKNOWN")):
            with self.subTest(field="intent", value=intent):
                with self.assertRaisesRegex(RuntimeError, "invalid_result.*intent"):
                    Result(intent, "ข้อความสมมติ", None)
        for response in (None, b"text", "", " \t\u3000", "\ud800", StringSubclass("ข้อความสมมติ")):
            with self.subTest(field="response", value=response):
                with self.assertRaisesRegex(RuntimeError, "invalid_result.*response"):
                    Result("UNKNOWN", response, None)
        for rule_id in (False, 1, b"a", [], "", "A", "ก", "a_1", "a\n", ".a", "-a",
                        " a", "a ", StringSubclass("a")):
            with self.subTest(field="rule_id", value=rule_id):
                with self.assertRaisesRegex(RuntimeError, "invalid_result.*rule_id"):
                    Result("UNKNOWN", "ข้อความสมมติ", rule_id)
        with self.assertRaisesRegex(RuntimeError, "invalid_result.*rule_id"):
            Result("EMPTY_INPUT", "ข้อความสมมติ", "a")

    def test_frozen_fields_and_independent_wire_dictionary(self):
        result = Result("HELP", " ข้อความสมมติไทย / V0.1 👩‍💻 ", "help.fixture")
        self.assertEqual(result, Result("HELP", " ข้อความสมมติไทย / V0.1 👩‍💻 ", "help.fixture"))
        for field in ("intent", "response", "rule_id"):
            with self.subTest(field=field):
                with self.assertRaises(FrozenInstanceError):
                    setattr(result, field, "changed")
                with self.assertRaises(FrozenInstanceError):
                    delattr(result, field)
        fields = asdict(result)
        fields["response"] = "changed"
        self.assertEqual(result.response, " ข้อความสมมติไทย / V0.1 👩‍💻 ")
