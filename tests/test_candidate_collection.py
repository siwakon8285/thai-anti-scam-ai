"""Component assertions derived from the approved V0.1 fixtures."""

from dataclasses import FrozenInstanceError
from itertools import permutations
import unittest
from unittest.mock import patch

from tests.runtime_fixtures import load_cases
from thai_ai.candidates import collect_candidates
from thai_ai.matching import Rule, _DEFAULT_RULES, _find_matches


# Additional eligible evidence stated in the R2 scenarios and the R6 rationale.
_MULTI_INTENTS = {
    "INT-01": {"GREETING", "BOT_IDENTITY"},
    "INT-02": {"GREETING", "BOT_CAPABILITIES"},
    "INT-14": {"BOT_IDENTITY", "BOT_CAPABILITIES"},
    "OPEN-MIXED-REQUEST": {"THANKS", "HELP"},
}
_BLOCKED_EVIDENCE = {
    "DEV-026": ("HELP", "specific_request", "ช่วย"),
    "INT-03": ("HELP", "negated", "ช่วย"),
    "INT-04": ("GREETING", "reported", "สวัสดี"),
    "INT-05": ("HELP", "negated", "ช่วย"),
    "INT-15": ("THANKS", "reported", "ขอบคุณครับ"),
    "INT-16": ("THANKS", "negated", "ขอบคุณครับ"),
    "INT-17": ("GREETING", "other_recipient", "ทักทาย"),
}


def fixture_rule(record, phrase):
    return Rule(record["fixture_rule_id"], record["intent"], record["priority"],
                record["specificity"], (phrase,))


class CandidateCollectionTests(unittest.TestCase):
    def test_all_approved_text_cases_at_collection_boundary(self):
        cases = {case["case_id"]: case for case in load_cases("intent")}
        self.assertEqual(len(cases), 57)
        for case_id, case in cases.items():
            with self.subTest(case_id=case_id):
                raw = case["fixture"]["value"]
                expected = case["expected_outcome"]
                collection = collect_candidates(raw)
                self.assertEqual(collection.raw_text, raw)
                candidates = collection.candidates
                if case_id in _MULTI_INTENTS:
                    self.assertEqual({candidate.intent for candidate in candidates}, _MULTI_INTENTS[case_id])
                elif expected["path"] == "matched":
                    self.assertEqual([candidate.intent for candidate in candidates], [expected["intent"]])
                else:
                    self.assertEqual(candidates, ())
                if expected["path"] in ("empty", "format_only"):
                    self.assertEqual(collection.kind, expected["path"])
                else:
                    self.assertEqual(collection.kind, "content")
                for candidate in candidates:
                    rule = next(rule for rule in _DEFAULT_RULES if rule.rule_id == candidate.rule_id)
                    self.assertEqual((candidate.intent, candidate.priority, candidate.specificity),
                                     (rule.intent, rule.priority, rule.specificity))
                    self.assertTrue(candidate.spans)
                    for start, end in candidate.spans:
                        self.assertTrue(0 <= start < end <= len(collection.matching_text))
                        self.assertIn(collection.matching_text[start:end], rule.phrases)
                if case.get("same_result_as"):
                    reference = collect_candidates(cases[case["same_result_as"]]["fixture"]["value"])
                    self.assertEqual(candidates, reference.candidates)
                if case.get("follow_up_case"):
                    follow_up = cases[case["follow_up_case"]]
                    next_candidates = collect_candidates(follow_up["fixture"]["value"]).candidates
                    self.assertEqual([item.intent for item in next_candidates],
                                     [follow_up["expected_outcome"]["intent"]])

    def test_guards_reject_actual_matched_evidence(self):
        cases = {case["case_id"]: case for case in load_cases("intent")}
        for case_id, (intent, scope, phrase) in _BLOCKED_EVIDENCE.items():
            with self.subTest(case_id=case_id):
                raw = cases[case_id]["fixture"]["value"]
                collection = collect_candidates(raw)
                matches = _find_matches(collection.matching_text, _DEFAULT_RULES)
                blocked = [match for match in matches if match.rule.intent == intent and match.scope == scope]
                self.assertEqual(len(blocked), 1)
                start, end = blocked[0].span
                self.assertEqual(collection.matching_text[start:end], phrase)
                self.assertNotIn(intent, {candidate.intent for candidate in collection.candidates})

    def test_resolver_fixtures_collect_every_eligible_rule_in_any_fixture_order(self):
        cases = [case for case in load_cases("resolver") if case["fixture"]["kind"] == "candidates"]
        self.assertEqual(len(cases), 13)
        phrase = "สวัสดีครับ"
        for case in cases:
            fixture = case["fixture"]
            records = fixture["candidates"]
            rules = tuple(fixture_rule(record, phrase) for record in records)
            allowed = {record["fixture_rule_id"]: record["guard_passes"] for record in records}
            expected = sorted(
                (record["fixture_rule_id"], record["intent"], record["priority"], record["specificity"])
                for record in records if record["guard_passes"]
            )
            orders = permutations(rules) if fixture["check_permutations"] else (rules,)
            with self.subTest(case_id=case["case_id"]):
                # Fixtures supply guard booleans, without any raw text for the guard itself.
                with patch("thai_ai.candidates.passes_guard", side_effect=lambda match: allowed[match.rule.rule_id]):
                    for order in orders:
                        candidates = collect_candidates(phrase, rules=order).candidates
                        self.assertEqual(
                            [(c.rule_id, c.intent, c.priority, c.specificity) for c in candidates],
                            expected,
                        )
                        self.assertTrue(all(c.spans == ((0, len(phrase)),) for c in candidates))

    def test_configured_explicit_unknown_can_match_a_specific_request(self):
        # S11 excludes HELP for this request. S12 adds an explicit UNKNOWN rule.
        request = next(case for case in load_cases("intent") if case["case_id"] == "DEV-026")
        explicit = next(case for case in load_cases("resolver") if case["case_id"] == "RES-03")
        raw = request["fixture"]["value"]
        record, = explicit["fixture"]["candidates"]
        rule = fixture_rule(record, raw)
        with self.subTest(case_id=explicit["case_id"]):
            collection = collect_candidates(raw, rules=(*_DEFAULT_RULES, rule))
            self.assertEqual(
                [(candidate.rule_id, candidate.intent, candidate.spans) for candidate in collection.candidates],
                [(record["fixture_rule_id"], explicit["expected_outcome"]["intent"], ((0, len(raw)),))],
            )

    def test_duplicate_rule_configuration_is_rejected_before_invalid_input(self):
        case, = [case for case in load_cases("resolver") if case["fixture"]["kind"] == "invalid_configuration"]
        rules = tuple(fixture_rule(record, "สวัสดีครับ") for record in case["fixture"]["candidates"])
        with self.subTest(case_id=case["case_id"]):
            with self.assertRaisesRegex(RuntimeError, case["expected_outcome"]["reason"]) as caught:
                collect_candidates(None, rules=rules)
            self.assertEqual(type(caught.exception).__name__, case["expected_outcome"]["type"])

    def test_matching_and_guard_faults_propagate(self):
        stages = {
            "matching": "thai_ai.candidates._find_matches",
            "guard": "thai_ai.candidates.passes_guard",
        }
        cases = [case for case in load_cases("resolver") if case["fixture"].get("stage") in stages]
        self.assertEqual(len(cases), 2)
        for case in cases:
            failure = RuntimeError(case["expected_outcome"]["reason"])
            with self.subTest(case_id=case["case_id"]):
                with patch(stages[case["fixture"]["stage"]], side_effect=failure) as failing_stage:
                    with self.assertRaises(RuntimeError) as caught:
                        collect_candidates("สวัสดีครับ")
                    self.assertIs(caught.exception, failure)
                    failing_stage.assert_called_once()

    def test_rule_metadata_and_literal_configuration(self):
        valid = ("demo-1.a", "UNKNOWN", -2, 0, ("Café",))
        for index, invalid in (
            (0, "UPPER"), (0, ".start"), (1, "EMPTY_INPUT"), (1, "NEW_INTENT"),
            (2, True), (2, 1.0), (3, True), (3, -1), (3, 3),
            (4, ()), (4, ["Café"]), (4, (" Cafe",)), (4, ("Café",)),
            (4, ("\u200b",)), (4, ("\ud800",)), (4, ("หนึ่ง", "หนึ่ง")),
        ):
            with self.subTest(index=index, invalid=invalid):
                fields = list(valid)
                fields[index] = invalid
                with self.assertRaises(RuntimeError):
                    Rule(*fields)

        rule = Rule(*valid)
        view = collect_candidates("  Café  ", rules=(rule,))
        self.assertEqual(view.raw_text, "  Café  ")
        self.assertEqual(view.matching_text, "Café")
        candidate, = view.candidates
        self.assertEqual((candidate.rule_id, candidate.intent, candidate.spans), ("demo-1.a", "UNKNOWN", ((0, 4),)))
        self.assertEqual(collect_candidates("café", rules=(rule,)).candidates, ())
        self.assertNotIn("Café", repr(view))
        for obj, field in ((candidate, "intent"), (rule, "intent"), (view, "raw_text")):
            with self.assertRaises(FrozenInstanceError):
                setattr(obj, field, "changed")

    def test_early_paths_do_not_enter_matcher_and_invalid_input_propagates(self):
        with patch("thai_ai.candidates._find_matches", side_effect=AssertionError("matcher called")):
            for text in (" \t", "\u200b"):
                self.assertEqual(collect_candidates(text).candidates, ())
            with self.assertRaisesRegex(ValueError, r"^disallowed_control.*offset 1"):
                collect_candidates(" \x0b")

    def test_literal_prefix_near_matches_do_not_become_candidates(self):
        for text in ("สวัสดีครับX", "สวัสดีครับ\r\nคุณคือใคร", "สวัสดีครับ คุณคือใครผิด",
                     "สวัสดีครับ คุณคือใคร คุณทำอะไรได้บ้าง"):
            with self.subTest(text=text):
                self.assertEqual(collect_candidates(text).candidates, ())
