"""Verify the regression specification and its fixtures without an AI Engine."""

from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path
import re
import unicodedata
import unittest

from tests.regression_spec_validation import (
    REQUIREMENTS, character_reasons, condition_key, parse_regression_spec,
)


ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "datasets/regression/v0.1.json"


class RegressionSpecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = parse_regression_spec(SPEC_PATH.read_bytes())
        cls.cases = {item["case_id"]: item for item in cls.spec["cases"]}

    def test_mandatory_coverage_and_separate_pending_cases(self):
        mandatory = [case for case in self.cases.values() if case["status"] == "mandatory"]
        pending = [case for case in self.cases.values() if case["status"] == "pending"]
        self.assertTrue(pending)
        self.assertTrue(all("expected_outcome" not in case for case in pending))
        self.assertEqual({req for case in mandatory for req in case["requirement_ids"]}, REQUIREMENTS)
        self.assertEqual({case["category"] for case in mandatory},
                         {"input_validation", "normalization", "intent", "resolver", "response"})

    def test_original_requirements_and_architecture_scenarios_trace_to_cases(self):
        analysis = (ROOT / "docs/v0.1-behavioral-contract-analysis.md").read_text(encoding="utf-8")
        self.assertEqual(set(re.findall(r"^\| (BC-[A-Z]+-\d{2}) \|", analysis, re.M)), REQUIREMENTS)
        design = (ROOT / "docs/v0.1-rule-architecture.md").read_text(encoding="utf-8")
        scenarios = re.findall(r"^\| (S\d{2}) · [^|]*\| ([^|]+) \|", design, re.M)
        self.assertEqual([identifier for identifier, _ in scenarios], [f"S{n:02}" for n in range(1, 27)])
        covered = defaultdict(set)
        for case in self.cases.values():
            if case["status"] == "mandatory":
                for identifier in case.get("source_scenarios", []):
                    covered[identifier].update(case["requirement_ids"])
        self.assertEqual(set(covered), {identifier for identifier, _ in scenarios})
        for identifier, source in scenarios:
            with self.subTest(scenario=identifier):
                self.assertLessEqual(set(source.strip().split(", ")), covered[identifier])

    def test_original_development_inputs_and_labels_are_retained(self):
        raw = (ROOT / "datasets/development/v0.1.json").read_bytes()
        original = json.loads(raw)["samples"]
        linked = [case for case in self.cases.values() if "source_sample_id" in case]
        self.assertEqual(Counter(case["source_sample_id"] for case in linked),
                         Counter(sample["id"] for sample in original))
        self.assertEqual(len(original), 32)
        by_id = {case["source_sample_id"]: case for case in linked}
        for sample in original:
            with self.subTest(sample=sample["id"]):
                case = by_id[sample["id"]]
                self.assertEqual(case["fixture"], {"kind": "text", "value": sample["input"]})
                self.assertEqual(case["expected_outcome"]["intent"], sample["expected_intent"])
                self.assertFalse(any(any(character_reasons(ord(char)).values()) for char in sample["input"]))
                self.assertEqual(not sample["input"].strip(), sample["expected_intent"] == "EMPTY_INPUT")

    def test_matching_view_oracles_agree_with_standard_library_evidence(self):
        for case in self.cases.values():
            expected = case.get("expected_outcome", {})
            if expected.get("outcome") == "matching_view":
                with self.subTest(case_id=case["case_id"]):
                    source = case["fixture"]["value"]
                    observed = unicodedata.normalize("NFC", source.strip())
                    self.assertEqual(observed, expected["value"])
                    self.assertEqual(unicodedata.normalize("NFC", observed.strip()), observed)

    def test_wire_examples_keep_null_and_string_rule_references(self):
        for identifier in ("WIRE-EMPTY", "WIRE-UNKNOWN-NO-MATCH", "WIRE-UNKNOWN-EXPLICIT"):
            with self.subTest(case_id=identifier):
                case = self.cases[identifier]
                wire = json.dumps(case["fixture"]["fields"])
                expected = case["expected_outcome"]["fields"]
                self.assertEqual(json.loads(wire), expected)
                if expected["rule_id"] is None:
                    self.assertIn('"rule_id": null', wire)
                else:
                    self.assertEqual(expected["rule_id"], "fixture-a")

    def check_rejection(self, mutation, message):
        invalid = deepcopy(self.spec)
        by_id = {item["case_id"]: item for item in invalid["cases"]}
        mutation(invalid, by_id)
        with self.assertRaisesRegex(ValueError, message):
            parse_regression_spec(json.dumps(invalid).encode("utf-8"))

    def test_rejects_malformed_json_duplicate_keys_and_nonfinite_numbers(self):
        for raw, message in (
            (b'{"cases":[}', "Expecting value"),
            (b'{"version":"old","version":"v0.1"}', "Duplicate JSON object key"),
            (br'{"cases":[{"id":0,"\u0069d":1}]}', "Duplicate JSON object key"),
            (b'{"field":NaN}', "Non-standard JSON constant"),
            (b'{"field":1e400}', "finite float range"),
            (b'"\xff"', "invalid start byte"),
        ):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(ValueError, message):
                    parse_regression_spec(raw)

    def test_rejects_unknown_fields_duplicate_ids_and_unknown_requirements(self):
        for mutation, message in (
            (lambda spec, _: spec.update(extra=True), "unexpected or missing fields"),
            (lambda spec, cases: spec["cases"].append(cases["DEV-001"]), "duplicate case_id"),
            (lambda _, cases: cases["DEV-001"].update(requirement_ids=["BC-INT-99"]), "invalid.*Requirement ID"),
            (lambda _, cases: cases["DEV-001"].update(requirement_ids=["BC-INT-01"] * 2),
             "duplicated Requirement ID"),
            (lambda _, cases: cases["DEV-001"]["expected_outcome"].update(intent="OTHER"), "taxonomy|incompatible intent"),
        ):
            with self.subTest(message=message):
                self.check_rejection(mutation, message)

    def test_rejects_contradictory_expectations_even_when_candidates_are_reordered(self):
        def conflict(spec, cases):
            original = deepcopy(cases["RES-06"])
            original["case_id"] = "CONFLICT-ORDER"
            original["fixture"]["candidates"].reverse()
            original["fixture"]["check_permutations"] = False
            original["expected_outcome"]["winning_candidate"] = "b.2"
            spec["cases"].append(original)

        self.check_rejection(conflict, "conflicting expected outcomes with RES-06")

    def test_rejects_repeated_conditions_with_a_new_id(self):
        def repeat(spec, cases):
            duplicate = dict(cases["DEV-001"], case_id="REPEATED-001")
            spec["cases"].append(duplicate)

        self.check_rejection(repeat, "duplicate fixture conditions")

    def test_rejects_engine_result_and_exception_for_the_same_input_across_categories(self):
        for index in (0, len(self.cases)):
            def conflict(spec, cases):
                case = deepcopy(cases["DEV-001"])
                case.update(case_id="CONFLICT-ENGINE", fixture=deepcopy(cases["IN-09"]["fixture"]))
                case.pop("source_sample_id")
                spec["cases"].insert(index, case)

            with self.subTest(index=index):
                self.check_rejection(conflict, "conflicting expected outcomes")

    def test_accepts_the_same_engine_result_with_a_distinct_follow_up_assertion(self):
        spec = deepcopy(self.spec)
        case = deepcopy(self.cases["DEV-001"])
        case.update(case_id="SAME-RESULT-FOLLOW-UP", follow_up_case="DEV-005")
        case.pop("source_sample_id")
        spec["cases"].append(case)
        validated = parse_regression_spec(json.dumps(spec).encode())
        self.assertEqual(validated["cases"][-1], case)

    def test_identity_preserves_types_raw_text_and_execution_target(self):
        def key(fixture, category="intent"):
            return condition_key({
                "category": category, "status": "mandatory", "fixture": fixture,
            })

        self.assertEqual(key(self.cases["IN-09"]["fixture"], "input_validation"),
                         key(self.cases["IN-09"]["fixture"]))
        self.assertNotEqual(key(self.cases["DEV-001"]["fixture"]),
                            key(self.cases["DEV-001"]["fixture"], "normalization"))
        fixtures = [
            {"kind": "json_value", "value": True}, {"kind": "json_value", "value": 1},
            {"kind": "json_value", "value": 1.0}, {"kind": "bytes_hex", "hex": "31"},
            {"kind": "str_subclass", "value": "1"}, {"kind": "text", "value": "1"},
            {"kind": "text", "value": " 1"}, {"kind": "text", "value": "\u00e9"},
            {"kind": "text", "value": "e\u0301"},
        ]
        self.assertEqual(len({key(fixture) for fixture in fixtures}), len(fixtures))

    def test_accepts_valid_candidate_permutations_and_distinct_resolver_context(self):
        spec = deepcopy(self.spec)
        cases = {case["case_id"]: case for case in spec["cases"]}
        for identifier in ("RES-04", "RES-05", "RES-06", "RES-07", "RES-09", "RES-12"):
            cases[identifier]["fixture"]["candidates"].reverse()
        different_context = deepcopy(cases["RES-09"])
        different_context.update(case_id="DIRECT-GREETING-CONTEXT", expected_outcome=cases["RES-13"]["expected_outcome"])
        different_context["fixture"]["greeting_is_intro"] = False
        spec["cases"].append(different_context)
        validated = parse_regression_spec(json.dumps(spec).encode())
        self.assertEqual(validated["cases"][-1], different_context)

    def test_rejects_claimed_winners_that_lose_the_same_intent_order(self):
        for identifier, wrong_winner in (("RES-04", "b"), ("RES-05", "a"), ("RES-06", "b.2")):
            with self.subTest(identifier=identifier):
                self.check_rejection(
                    lambda _, cases: cases[identifier]["expected_outcome"].update(winning_candidate=wrong_winner),
                    "priority, specificity or ASCII rule_id",
                )

    def test_rejects_cross_intent_claims_that_contradict_declared_precedence(self):
        self.check_rejection(
            lambda _, cases: cases["RES-09"].update(expected_outcome=cases["RES-13"]["expected_outcome"]),
            "precedence",
        )
        self.check_rejection(
            lambda _, cases: cases["RES-13"].update(expected_outcome=cases["RES-09"]["expected_outcome"]),
            "precedence",
        )

    def test_rejects_wrong_input_path_even_with_a_compatible_template(self):
        for identifier, changes, message in (
            ("INT-09", {"path": "no_match", "response_template": "unknown_no_match"}, "format-only"),
            ("INT-12", {"path": "format_only", "response_template": "unknown_format_only"}, "format-only"),
            ("DEV-029", {"path": "no_match", "intent": "UNKNOWN", "response_template": "unknown_no_match"}, "blank"),
        ):
            with self.subTest(identifier=identifier):
                self.check_rejection(
                    lambda _, cases: cases[identifier]["expected_outcome"].update(changes), message
                )

    def test_accepts_approved_standalone_zwsp_as_format_only_for_s15(self):
        case = self.cases["INT-ZWSP-ONLY"]
        self.assertEqual(case["fixture"], {"kind": "text", "value": "\u200b"})
        self.assertEqual(case["status"], "mandatory")
        self.assertIn("S15", case["source_scenarios"])
        self.assertEqual(case["expected_outcome"], {
            "outcome": "result", "intent": "UNKNOWN", "path": "format_only",
            "response_template": "unknown_format_only", "rule_id": "must_be_none",
        })

    def test_owner_approved_r6_results_preserve_the_original_inputs(self):
        for identifier, raw, intent, path, rule_reference in (
            ("OPEN-BOM-PREFIX", "\ufeffสวัสดีครับ", "UNKNOWN", "no_match", "must_be_none"),
            ("OPEN-ZWSP-IN-WORD", "สวัส\u200bดีครับ", "UNKNOWN", "no_match", "must_be_none"),
            ("OPEN-COMBINING-ONLY", "\u0301", "UNKNOWN", "no_match", "must_be_none"),
            ("OPEN-MIXED-REQUEST", "ขอบคุณครับ ช่วยเริ่มให้หน่อย", "HELP", "matched", "must_reference_winning_rule"),
        ):
            with self.subTest(case_id=identifier):
                case = self.cases[identifier]
                self.assertEqual(case["fixture"], {"kind": "text", "value": raw})
                self.assertEqual(case["status"], "mandatory")
                self.assertNotIn("open_decision", case)
                expected = case["expected_outcome"]
                self.assertEqual((expected["intent"], expected["path"], expected["rule_id"]),
                                 (intent, path, rule_reference))
        for identifier in ("OPEN-LENGTH-LIMIT", "OPEN-REGEX-BUDGET"):
            self.assertEqual(self.cases[identifier]["status"], "pending")
            self.assertNotIn("expected_outcome", self.cases[identifier])

    def test_rejects_invalid_fixture_encodings(self):
        for case_id, changes, message in (
            ("IN-07", {"hex": "abc"}, "hex byte pairs"),
            ("IN-08", {"value": 1}, "invalid str_subclass"),
            ("IN-01", {"value": "None"}, "invalid json_value"),
            ("IN-30", {"values": [0x110000]}, "invalid code_points"),
            ("DEV-001", {"value": "\ud800"}, "surrogate in JSON string"),
        ):
            with self.subTest(case_id=case_id, changes=changes):
                self.check_rejection(
                    lambda _, cases: cases[case_id]["fixture"].update(changes), message
                )

    def test_rejects_result_and_exception_field_mixing(self):
        self.check_rejection(
            lambda _, cases: cases["DEV-001"]["expected_outcome"].update(type="TypeError"),
            "unexpected or missing fields",
        )
        self.check_rejection(
            lambda _, cases: cases["IN-01"]["expected_outcome"].update(intent="UNKNOWN"),
            "unexpected or missing fields",
        )
        self.check_rejection(
            lambda _, cases: cases["IN-01"].update(expected_outcome=cases["DEV-001"]["expected_outcome"]),
            "outcome is incompatible with fixture",
        )

    def test_rejects_exception_that_points_past_the_first_invalid_code_point(self):
        self.check_rejection(
            lambda _, cases: cases["IN-33"]["expected_outcome"].update(
                reason="surrogate", code_point_offset=1
            ),
            "first invalid code point",
        )

    def test_rejects_pending_outcomes_and_pending_only_requirement_coverage(self):
        self.check_rejection(
            lambda _, cases: cases["OPEN-LENGTH-LIMIT"].update(expected_outcome=cases["DEV-001"]["expected_outcome"]),
            "pending case cannot contain executable expectations",
        )
        self.check_rejection(
            lambda _, cases: cases["OPEN-LENGTH-LIMIT"].pop("open_decision"),
            "pending case requires an Open Decision",
        )

        def remove_mandatory_coverage(spec, _):
            for case in spec["cases"]:
                if case["status"] == "mandatory" and "BC-INT-01" in case["requirement_ids"]:
                    ids = [req for req in case["requirement_ids"] if req != "BC-INT-01"]
                    case["requirement_ids"] = ids or ["BC-OUT-02"]

        self.check_rejection(remove_mandatory_coverage, "missing mandatory coverage.*BC-INT-01")

    def test_rejects_invalid_resolver_conditions_and_rule_id_expectations(self):
        for mutation, message in (
            (lambda _, cases: cases["RES-07"]["expected_outcome"].update(winning_candidate="a"), "eligible candidate"),
            (lambda _, cases: cases["RES-05"]["fixture"]["candidates"][0].update(priority=True), "priority must"),
            (lambda _, cases: cases["RES-05"]["fixture"]["candidates"][0].update(intent=[]), "invalid candidate intent"),
            (lambda _, cases: cases["RES-03"]["expected_outcome"].update(rule_id="must_be_none"), "rule_id expectation"),
            (lambda _, cases: cases["RES-11"]["expected_outcome"].update(winning_candidate="a"), "unexpected or missing fields|only on match"),
        ):
            with self.subTest(message=message):
                self.check_rejection(mutation, message)

    def test_rejects_empty_mismatched_and_overclaimed_template_expectations(self):
        for mutation, message in (
            (lambda spec, _: spec["response_templates"]["greeting"].update(text=" \t"), "empty response template"),
            (lambda _, cases: cases["DEV-001"]["expected_outcome"].update(response_template="thanks"), "template does not match"),
            (lambda _, cases: cases["REJECT-CAPABILITIES"]["expected_outcome"].update(verdict="accept"), "review verdict conflicts"),
        ):
            with self.subTest(message=message):
                self.check_rejection(mutation, message)
