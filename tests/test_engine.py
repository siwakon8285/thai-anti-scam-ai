"""Exercise approved Engine cases through the public V0.1 entry point."""

from contextlib import ExitStack
from dataclasses import FrozenInstanceError, asdict, replace
import json
import re
import unittest
from unittest.mock import Mock, patch

from tests.runtime_fixtures import load_cases
from tests.test_response import _APPROVED
from tests.test_validation import StringSubclass
from thai_ai import candidates, engine, normalization, resolver, response
from thai_ai.engine import process_text
from thai_ai.matching import Rule, _DEFAULT_RULES
from thai_ai.registry import RuleRegistry
from thai_ai.result import Result

_TEXT_CASES = {case["case_id"]: case for case in load_cases("intent")}
_RESOLVER_CASES = {case["case_id"]: case for case in load_cases("resolver")}
_RESPONSE_CASES = {case["case_id"]: case for case in load_cases("response")}


def fixture_input(fixture):
    match fixture["kind"]:
        case "text" | "json_value":
            return fixture["value"]
        case "str_subclass":
            return StringSubclass(fixture["value"])
        case "bytes_hex":
            return bytes.fromhex(fixture["hex"])
        case "code_points":
            return "".join(map(chr, fixture["values"]))
    raise AssertionError(f"unexpected input fixture: {fixture['kind']}")


class EngineBehaviorTests(unittest.TestCase):
    def test_approved_text_results(self):
        self.assertEqual(len(_TEXT_CASES), 57)
        observed_intents = set()
        for case_id, case in _TEXT_CASES.items():
            with self.subTest(case_id=case_id):
                text = fixture_input(case["fixture"])
                expected = case["expected_outcome"]
                result = process_text(text)
                self.assertIs(type(result), Result)
                self.assertEqual(result.intent, expected["intent"])
                self.assertEqual(result.response, _APPROVED[expected["response_template"]]["text"])
                if expected["rule_id"] == "must_be_none":
                    self.assertIsNone(result.rule_id)
                else:
                    winner = resolver.decide(text).winner
                    self.assertIsNotNone(winner)
                    self.assertEqual(result.rule_id, winner.rule_id)
                observed_intents.add(result.intent)
                if reference := case.get("same_result_as"):
                    self.assertEqual(result, process_text(fixture_input(_TEXT_CASES[reference]["fixture"])))
                if follow_up := case.get("follow_up_case"):
                    next_case = _TEXT_CASES[follow_up]
                    later = process_text(fixture_input(next_case["fixture"]))
                    self.assertEqual((later.intent, later.response, later.rule_id),
                                     ("GREETING", _APPROVED["greeting"]["text"], "greeting.direct"))
        self.assertEqual(observed_intents, {
            "GREETING", "BOT_IDENTITY", "BOT_CAPABILITIES", "THANKS", "FAREWELL",
            "HELP", "UNKNOWN", "EMPTY_INPUT",
        })

    def test_approved_raw_input_errors(self):
        cases = load_cases("input_validation")
        self.assertEqual(len(cases), 36)
        for case in cases:
            with self.subTest(case_id=case["case_id"]):
                expected = case["expected_outcome"]
                error_type = {"TypeError": TypeError, "ValueError": ValueError}[expected["type"]]
                with self.assertRaisesRegex(error_type, rf"^{re.escape(expected['reason'])}\b") as caught:
                    process_text(fixture_input(case["fixture"]))
                self.assertIs(type(caught.exception), error_type)
                if "code_point_offset" in expected:
                    self.assertIn(f"offset {expected['code_point_offset']} (", str(caught.exception))

    def test_approved_frozen_and_wire_results(self):
        specific_request = fixture_input(_TEXT_CASES["DEV-026"]["fixture"])
        for case_id, text in {
            "WIRE-EMPTY": "", "WIRE-UNKNOWN-NO-MATCH": specific_request,
            "WIRE-UNKNOWN-EXPLICIT": specific_request,
        }.items():
            with self.subTest(case_id=case_id):
                expected = _RESPONSE_CASES[case_id]["expected_outcome"]["fields"]
                if case_id == "WIRE-UNKNOWN-EXPLICIT":
                    explicit = Rule(expected["rule_id"], "UNKNOWN", 0, 2, (specific_request,))
                    result = process_text(text, rules=(*_DEFAULT_RULES, explicit))
                else:
                    result = process_text(text)
                self.assertIs(type(result), Result)
                with self.assertRaises(FrozenInstanceError):
                    result.rule_id = "not-a-winner"
                wire = json.dumps(asdict(result), ensure_ascii=False, allow_nan=False).encode("utf-8")
                self.assertEqual(json.loads(wire), expected)

    def test_deterministic_custom_winner_and_reordered_default_rules(self):
        text = "ข้อความทดสอบ"
        rules = (
            Rule("z-high-specificity", "GREETING", 1, 2, (text,)),
            Rule("b-more-specific", "GREETING", 2, 2, (text,)),
            Rule("a-winner", "GREETING", 2, 2, (text,)),
            Rule("a-less-specific", "GREETING", 2, 1, (text,)),
        )
        expected = Result("GREETING", _APPROVED["greeting"]["text"], "a-winner")
        mixed = fixture_input(_TEXT_CASES["INT-01"]["fixture"])
        mixed_expected = Result("BOT_IDENTITY", _APPROVED["identity"]["text"], "identity.direct")
        with patch.object(engine, "select_response", wraps=engine.select_response) as select:
            for _ in range(4):
                self.assertEqual(process_text(text, rules=rules), expected)
                self.assertEqual(process_text(text, rules=rules[::-1]), expected)
                self.assertIsNone(process_text(text, rules=()).rule_id)
                self.assertEqual(process_text(mixed, rules=_DEFAULT_RULES[::-1]), mixed_expected)
                self.assertEqual(process_text(mixed), mixed_expected)
        decisions = [call.args[0] for call in select.call_args_list]
        for start in range(0, len(decisions), 5):
            self.assertEqual(decisions[start:start + 5],
                             [decisions[0], decisions[0], decisions[2], decisions[3], decisions[3]])


class EnginePipelineTests(unittest.TestCase):
    def test_stage_order_snapshot_and_matching_view(self):
        calls = Mock()
        targets = {
            "registry": (engine, "RuleRegistry"),
            "normalize": (resolver, "normalize_text"),
            "validate": (normalization, "validate_input"),
            "collect": (resolver, "_collect_content"),
            "match": (candidates, "_find_matches"),
            "guard": (candidates, "passes_guard"),
            "roles": (resolver, "_collect_roles"),
            "resolve": (resolver, "resolve_candidates"),
            "respond": (engine, "select_response"),
            "result": (response, "Result"),
        }
        with ExitStack() as stack:
            spies = {}
            for name, (module, member) in targets.items():
                spy = stack.enter_context(patch.object(module, member, wraps=getattr(module, member)))
                calls.attach_mock(spy, name)
                spies[name] = spy
            raw = "  สวัสดีครับ คุณคือใคร  "
            result = process_text(raw)
        self.assertEqual([call[0] for call in calls.mock_calls],
                         ["registry", "normalize", "validate", "collect", "match", "guard", "guard",
                          "roles", "resolve", "respond", "result"])
        spies["normalize"].assert_called_once_with(raw)
        spies["validate"].assert_called_once_with(raw)
        view, registry = spies["collect"].call_args.args
        self.assertEqual(view, "สวัสดีครับ คุณคือใคร")
        self.assertIs(spies["match"].call_args.args[1], registry.rules)
        self.assertIs(spies["resolve"].call_args.kwargs["registry"], registry)
        self.assertIs(spies["respond"].call_args.kwargs["registry"], registry)
        self.assertEqual(spies["resolve"].call_args.kwargs["matching_length"], len(view))
        decision = spies["respond"].call_args.args[0]
        actual_spans = {item.rule_id: item.spans for item in decision.evidence.candidates}
        self.assertEqual(actual_spans, {"greeting.direct": ((0, 10),), "identity.direct": ((11, 20),)})
        self.assertEqual(result.rule_id, decision.winner.rule_id)
        self.assertEqual(spies["result"].call_args.args, (result.intent, result.response, result.rule_id))

    def test_early_routes_skip_collection_and_resolver(self):
        with (patch("thai_ai.resolver._collect_content", side_effect=AssertionError("collection called")),
              patch("thai_ai.resolver.resolve_candidates", side_effect=AssertionError("resolver called"))):
            for case_id, case in _TEXT_CASES.items():
                expected = case["expected_outcome"]
                if expected["path"] in ("empty", "format_only"):
                    with self.subTest(case_id=case_id):
                        result = process_text(fixture_input(case["fixture"]))
                        self.assertEqual(asdict(result), {
                            "intent": expected["intent"],
                            "response": _APPROVED[expected["response_template"]]["text"], "rule_id": None,
                        })

    def test_registry_errors_precede_all_input_processing(self):
        case = _RESOLVER_CASES["ERR-CONFIG"]
        rules = tuple(Rule(rule["fixture_rule_id"], rule["intent"], rule["priority"],
                           rule["specificity"], ("ข้อความทดสอบ",)) for rule in case["fixture"]["candidates"])
        with self.subTest(case_id=case["case_id"]):
            with (patch("thai_ai.resolver.normalize_text", side_effect=AssertionError("input processed")),
                  self.assertRaisesRegex(RuntimeError, "^" + case["expected_outcome"]["reason"] + ":") as caught):
                process_text(None, rules=rules)
            self.assertIs(type(caught.exception), RuntimeError)
        with self.assertRaisesRegex(RuntimeError, "^invalid_configuration:"):
            process_text(None, rules=list(rules))


class EngineFaultTests(unittest.TestCase):
    def test_stage_faults_propagate_with_identity_and_cause(self):
        targets = {
            "matching": "thai_ai.candidates._find_matches",
            "guard": "thai_ai.candidates.passes_guard",
            "selection": "thai_ai.resolver.resolve_candidates",
            "response": "thai_ai.engine.select_response",
        }
        for case_id, case in _RESOLVER_CASES.items():
            if case["fixture"]["kind"] != "fault":
                continue
            expected = case["expected_outcome"]
            fault = RuntimeError(expected["reason"])
            cause = ValueError("underlying stage error")
            fault.__cause__ = cause
            with self.subTest(case_id=case_id):
                with (patch(targets[case["fixture"]["stage"]], side_effect=fault) as stage,
                      self.assertRaisesRegex(RuntimeError, "^" + expected["reason"] + "$") as caught):
                    process_text("สวัสดีครับ")
                self.assertIs(caught.exception, fault)
                self.assertIs(caught.exception.__cause__, cause)
                stage.assert_called_once()

    def test_approved_result_construction_error_survives_engine(self):
        case = _RESPONSE_CASES["ERR-OUTPUT"]
        values = case["fixture"]["values"]
        rule = Rule(values["rule_id"], values["intent"], 0, 1, ("สวัสดีครับ",))
        with self.subTest(case_id=case["case_id"]):
            with (patch.object(response._TemplateRegistry, "get", return_value=values["response"]),
                  self.assertRaisesRegex(RuntimeError, "^" + case["expected_outcome"]["reason"] + ":") as caught):
                process_text("สวัสดีครับ", rules=(rule,))
            self.assertIs(type(caught.exception), RuntimeError)

    def test_invalid_candidate_is_rejected_before_response(self):
        registry = RuleRegistry(_DEFAULT_RULES)
        eligible, matches = candidates._collect_content("สวัสดีครับ", registry)
        for candidate, code in (
            (replace(eligible[0], priority=True), "invalid_candidate"),
            (replace(eligible[0], priority=9), "candidate_metadata_mismatch"),
        ):
            with (self.subTest(code=code),
                  patch("thai_ai.resolver._collect_content", return_value=((candidate,), matches)),
                  patch("thai_ai.engine.select_response", side_effect=AssertionError("response called")),
                  self.assertRaisesRegex(RuntimeError, "^" + code + ":")):
                process_text("สวัสดีครับ")

    def test_invalid_decision_or_reason_is_rejected_by_real_response_stage(self):
        for field, value in (("state", "UNKNOWN_STATE"), ("reason_code", "BAD_REASON"), ("winner", None)):
            malformed = resolver.decide("สวัสดีครับ")
            object.__setattr__(malformed, field, value)
            with (self.subTest(field=field),
                  patch("thai_ai.resolver.resolve_candidates", return_value=malformed),
                  self.assertRaisesRegex(RuntimeError, "^invalid_decision:")):
                process_text("สวัสดีครับ")

    def test_missing_template_keeps_original_lookup_cause(self):
        incomplete = object.__new__(response._TemplateRegistry)
        object.__setattr__(incomplete, "_texts", {("UNKNOWN", "no_match"): _APPROVED["unknown_no_match"]["text"]})
        with (patch("thai_ai.response._TEMPLATES", incomplete),
              self.assertRaisesRegex(RuntimeError, "^missing_template: GREETING/matched$") as caught):
            process_text("สวัสดีครับ")
        self.assertIs(type(caught.exception.__cause__), KeyError)
