"""Response Selection behavior at the public Result boundary."""

from dataclasses import FrozenInstanceError, asdict
from itertools import permutations
from pathlib import Path
import json
import unittest
from unittest.mock import patch

from tests.runtime_fixtures import load_cases
from tests.test_resolver import candidate, intro
from thai_ai.matching import Rule, _DEFAULT_RULES
from thai_ai.registry import RuleRegistry
from thai_ai.resolver import ReasonCode, decide, resolve_candidates
from thai_ai.response import _TemplateRegistry, _TEMPLATES, select_response
from thai_ai.result import Result


_SPEC = Path(__file__).resolve().parents[1] / "datasets/regression/v0.1.json"
_APPROVED = json.loads(_SPEC.read_text(encoding="utf-8"))["response_templates"]
_TEXT_CASES = {case["case_id"]: case for case in load_cases("intent")}
_RESPONSE_CASES = {case["case_id"]: case for case in load_cases("response")}
_TEMPLATE_INPUTS = {
    "greeting": "DEV-001", "identity": "INT-01", "capabilities": "INT-02",
    "thanks": "DEV-013", "farewell": "DEV-018", "help": "OPEN-MIXED-REQUEST",
    "unknown_no_match": "DEV-026", "unknown_ambiguity": "INT-14",
    "unknown_format_only": "INT-ZWSP-ONLY", "empty": "DEV-029",
}


def text_decision(case_id):
    return decide(_TEXT_CASES[case_id]["fixture"]["value"])


def template_decision(template_id, explicit_rule_id="fixture-a"):
    if template_id == "unknown_explicit":
        text = _TEXT_CASES["DEV-026"]["fixture"]["value"]
        rules = (Rule(explicit_rule_id, "UNKNOWN", 0, 2, (text,)),)
        return decide(text, rules=rules), RuleRegistry(rules)
    return text_decision(_TEMPLATE_INPUTS[template_id]), RuleRegistry(_DEFAULT_RULES)


def approved_catalog():
    return {(record["intent"], record["path"]): record["text"] for record in _APPROVED.values()}


def satisfies_rubric(template_id, response):
    """Check concrete conversational acts and claims in the fixed V0.1 fixtures."""
    match template_id:
        case "greeting":
            return response.startswith("สวัสดี") and "ยินดีที่ได้คุย" in response
        case "identity":
            return all(phrase in response for phrase in ("ต้นแบบบอตภาษาไทยแบบใช้กฎ", "thai-anti-scam-ai"))
        case "capabilities":
            return ("รองรับการทักทาย แนะนำตัว และสนทนาพื้นฐาน" in response
                    and "รุ่นนี้ยังไม่สามารถตรวจจับการหลอกลวงได้" in response
                    and "ปลอดภัย" not in response)
        case "thanks":
            return response.startswith("ยินดี") and response.endswith("ครับ")
        case "farewell":
            return response.startswith("แล้วพบกันใหม่") and response.endswith("ครับ")
        case "help":
            return ("อยากให้ช่วยเรื่องอะไร" in response and "เช่น อยากรู้ว่าบอตนี้ทำอะไรได้บ้าง" in response
                    and all(claim not in response for claim in ("เหตุฉุกเฉิน", "กำลังดำเนินการ")))
        case "unknown_explicit" | "unknown_no_match":
            return ("ยังตอบเรื่องนี้ไม่ได้" in response and "ต้องการให้ช่วยเรื่องอะไร" in response
                    and "เป็นมิจฉาชีพ" not in response)
        case "unknown_format_only":
            return "ยังตีความไม่ได้" in response and "กรุณาพิมพ์รายละเอียด" in response and "ว่าง" not in response
        case "unknown_ambiguity":
            return "อาจมีหลายคำขอ" in response and response.endswith("เรื่องใดเป็นหลักครับ?")
        case "empty":
            return response.startswith("กรุณาพิมพ์ข้อความ") and "ก่อน" in response
    raise AssertionError(f"missing rubric for {template_id}")


class TemplateTests(unittest.TestCase):
    def test_all_approved_templates_and_winner_references(self):
        self.assertEqual(set(_APPROVED), {*_TEMPLATE_INPUTS, "unknown_explicit"})
        for template_id, expected in _APPROVED.items():
            with self.subTest(template=template_id):
                decision, registry = template_decision(template_id)
                result = select_response(decision, registry=registry)
                self.assertIs(type(result), Result)
                self.assertEqual((result.intent, result.response, result.rule_id),
                                 (expected["intent"], expected["text"], decision.rule_id))
                self.assertEqual(decision.path, expected["path"])

    def test_registry_rejects_missing_extra_or_unapproved_content(self):
        approved = approved_catalog()
        registry = _TemplateRegistry(approved)
        approved.pop(("UNKNOWN", "matched"))
        self.assertEqual(registry.get("UNKNOWN", "matched"), _APPROVED["unknown_explicit"]["text"])
        with self.assertRaises(FrozenInstanceError):
            registry._texts = approved
        with self.assertRaisesRegex(RuntimeError, "^missing_template:"):
            _TemplateRegistry(approved)
        with self.assertRaisesRegex(RuntimeError, "^invalid_template_configuration:"):
            _TemplateRegistry({**approved_catalog(), ("UNKNOWN", "empty"): "ตัวอย่าง"})
        for text in ("", " \t", "\ud800", "คำตอบที่ไม่ได้อนุมัติ"):
            with self.subTest(text=text), self.assertRaisesRegex(RuntimeError, "^invalid_template_configuration:"):
                _TemplateRegistry({**approved_catalog(), ("GREETING", "matched"): text})

    def test_missing_explicit_template_does_not_use_identical_no_match_wording(self):
        decision, registry = template_decision("unknown_explicit")
        with patch("thai_ai.response._TEMPLATES", _TemplateRegistry.__new__(_TemplateRegistry)) as broken:
            object.__setattr__(broken, "_texts", {("UNKNOWN", "no_match"): _APPROVED["unknown_no_match"]["text"]})
            with self.assertRaisesRegex(RuntimeError, "^missing_template:"):
                select_response(decision, registry=registry)

    def test_approved_and_rejected_rubric_fixtures(self):
        reviews = [case for case in _RESPONSE_CASES.values() if case["fixture"]["kind"] == "response_review"]
        self.assertEqual(len(reviews), 14)
        for case in reviews:
            with self.subTest(case_id=case["case_id"]):
                fixture = case["fixture"]
                template_id, text = fixture["template_id"], fixture["text"]
                accepted = case["expected_outcome"]["verdict"] == "accept"
                self.assertEqual(satisfies_rubric(template_id, text), accepted)
                if accepted:
                    decision, registry = template_decision(template_id)
                    result = select_response(decision, registry=registry)
                    self.assertTrue(satisfies_rubric(template_id, result.response))
                else:
                    key = (_APPROVED[template_id]["intent"], _APPROVED[template_id]["path"])
                    with self.assertRaisesRegex(RuntimeError, "^invalid_template_configuration:"):
                        _TemplateRegistry({**approved_catalog(), key: text})


class ResponseIntegrityTests(unittest.TestCase):
    def test_invalid_decisions_are_rejected_at_the_response_boundary(self):
        with self.assertRaisesRegex(RuntimeError, "^invalid_decision:"):
            select_response(object())
        for case_id, field, value in (
            ("DEV-001", "state", "RESOLVED"), ("DEV-001", "reason_code", "BOGUS"),
            ("DEV-001", "reason_code", ReasonCode.NO_MATCH),
            ("DEV-001", "winner", None), ("DEV-001", "winner", text_decision("DEV-005").winner),
            ("INT-14", "winner", text_decision("DEV-001").winner),
            ("DEV-026", "winner", text_decision("DEV-001").winner),
        ):
            with self.subTest(case_id=case_id, field=field):
                decision = text_decision(case_id)
                object.__setattr__(decision, field, value)
                with self.assertRaisesRegex(RuntimeError, "^invalid_decision:"):
                    select_response(decision)

    def test_registry_must_match_winner_id_and_metadata(self):
        decision = text_decision("DEV-001")
        with self.assertRaisesRegex(RuntimeError, "^invalid_configuration:"):
            select_response(decision, registry=None)
        with self.assertRaisesRegex(RuntimeError, "^unregistered_rule_id:"):
            select_response(decision, registry=RuleRegistry(()))
        for intent, priority, specificity in (("HELP", 0, 1), ("GREETING", 5, 1), ("GREETING", 0, 2)):
            rules = (Rule(decision.rule_id, intent, priority, specificity, ("ตัวอย่าง",)),)
            with self.subTest(metadata=(intent, priority, specificity)):
                with self.assertRaisesRegex(RuntimeError, "^candidate_metadata_mismatch:"):
                    select_response(decision, registry=RuleRegistry(rules))

    def test_response_fault_propagates_unchanged(self):
        case = next(case for case in load_cases("resolver") if case["case_id"] == "ERR-RESPONSE")
        fault = RuntimeError(case["expected_outcome"]["reason"])
        with self.subTest(case_id=case["case_id"]), patch.object(
            _TemplateRegistry, "get", side_effect=fault,
        ), self.assertRaises(RuntimeError) as caught:
            select_response(text_decision("DEV-001"))
        self.assertIs(caught.exception, fault)

    def test_result_validation_error_propagates(self):
        case = _RESPONSE_CASES["ERR-OUTPUT"]
        values = case["fixture"]["values"]
        rules = (Rule(values["rule_id"], values["intent"], 0, 1, ("สวัสดีครับ",)),)
        decision = decide("สวัสดีครับ", rules=rules)
        with self.subTest(case_id=case["case_id"]), patch.object(
            _TemplateRegistry, "get", return_value=values["response"],
        ), self.assertRaisesRegex(RuntimeError, "^" + case["expected_outcome"]["reason"] + ":"):
            select_response(decision, registry=RuleRegistry(rules))

    def test_public_results_are_frozen_and_serialize_to_approved_fields(self):
        sources = {"WIRE-EMPTY": "empty", "WIRE-UNKNOWN-NO-MATCH": "unknown_no_match",
                   "WIRE-UNKNOWN-EXPLICIT": "unknown_explicit"}
        for cid, template_id in sources.items():
            with self.subTest(case_id=cid):
                decision, registry = template_decision(template_id)
                result = select_response(decision, registry=registry)
                with self.assertRaises(FrozenInstanceError):
                    result.response = "ตัวอย่าง"
                expected = _RESPONSE_CASES[cid]["expected_outcome"]["fields"]
                wire = json.dumps(asdict(result), ensure_ascii=False, allow_nan=False).encode("utf-8")
                self.assertEqual(json.loads(wire), expected)


class ResolverResponseTests(unittest.TestCase):
    def assert_result(self, result, expected, decision):
        self.assertEqual((result.intent, result.response),
                         (expected["intent"], _APPROVED[expected["response_template"]]["text"]))
        if expected["rule_id"] == "must_be_none":
            self.assertIsNone(result.rule_id)
        else:
            self.assertIsNotNone(decision.winner)
            self.assertEqual(result.rule_id, expected.get("winning_candidate", decision.winner.rule_id))

    def test_text_cases_through_resolver_and_response(self):
        self.assertEqual(len(_TEXT_CASES), 57)
        for case_id, case in _TEXT_CASES.items():
            with self.subTest(case_id=case_id):
                decision = text_decision(case_id)
                result = select_response(decision)
                self.assert_result(result, case["expected_outcome"], decision)
                if reference := case.get("same_result_as"):
                    self.assertEqual(result, select_response(text_decision(reference)))
                if follow_up := case.get("follow_up_case"):
                    next_decision = text_decision(follow_up)
                    self.assert_result(select_response(next_decision),
                                       _TEXT_CASES[follow_up]["expected_outcome"], next_decision)

    def test_resolver_fixtures_through_response(self):
        cases = [case for case in load_cases("resolver") if case["fixture"]["kind"] == "candidates"]
        self.assertEqual(len(cases), 13)
        for case in cases:
            fixture = case["fixture"]
            inputs = fixture["candidates"]
            rules = tuple(Rule(item["fixture_rule_id"], item["intent"], item["priority"],
                               item["specificity"], ("ตัวอย่าง",)) for item in inputs)
            eligible = tuple(candidate(rule, (2 * i, 2 * i + 1))
                             for i, (rule, item) in enumerate(zip(rules, inputs, strict=True))
                             if item["guard_passes"])
            context = ()
            if fixture["greeting_is_intro"]:
                opening = next(item for item in eligible if item.intent == "GREETING")
                context = tuple(intro(opening, item) for item in eligible
                                if item.intent in ("BOT_IDENTITY", "BOT_CAPABILITIES"))
            registry = RuleRegistry(rules)
            orders = permutations(eligible) if fixture["check_permutations"] else (eligible,)
            with self.subTest(case_id=case["case_id"]):
                for order in orders:
                    decision = resolve_candidates(order, matching_length=8, registry=registry,
                                                  context_evidence=context)
                    self.assert_result(select_response(decision, registry=registry), case["expected_outcome"], decision)

    def test_routed_results_do_not_enter_matcher_or_resolver(self):
        with (patch("thai_ai.candidates._find_matches", side_effect=AssertionError("matcher called")),
              patch("thai_ai.resolver.resolve_candidates", side_effect=AssertionError("resolver called"))):
            for cid, case in _TEXT_CASES.items():
                if case["expected_outcome"]["path"] in ("empty", "format_only"):
                    with self.subTest(case_id=cid):
                        decision = text_decision(cid)
                        self.assert_result(select_response(decision), case["expected_outcome"], decision)
