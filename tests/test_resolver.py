"""Behavioral and integration tests for the V0.1 decision boundary."""

from dataclasses import FrozenInstanceError, replace
from itertools import permutations
from random import Random
import unittest
from unittest.mock import patch

from tests.runtime_fixtures import load_cases
from thai_ai.candidates import Candidate, _collect_content
from thai_ai.guards import passes_guard
from thai_ai.matching import Rule
from thai_ai.normalization import normalize_text
from thai_ai.registry import RuleRegistry
from thai_ai.resolver import (
    ContextEvidence, DecisionEvidence, DecisionRecord, EvidenceRole, EvidenceSource,
    RoleEvidence, decide, resolve_candidates,
)


def candidate(rule, *spans):
    return Candidate(rule.rule_id, rule.intent, rule.priority, rule.specificity, spans)


def intro(opening, question):
    left, right = opening.spans[0], question.spans[0]
    return ContextEvidence(
        EvidenceSource.C08_INTRO_QUESTION, (left[0], right[1]),
        (RoleEvidence(EvidenceRole.INTRODUCTORY, opening.rule_id, left),
         RoleEvidence(EvidenceRole.PRIMARY_QUESTION, question.rule_id, right)),
    )


class DecisionAssertions(unittest.TestCase):
    def assert_outcome(self, decision, expected):
        self.assertEqual((decision.intent, decision.path), (expected["intent"], expected["path"]))
        state, reason = {
            "matched": ("RESOLVED", "EXPLICIT_UNKNOWN" if expected["intent"] == "UNKNOWN" else "MATCHED"),
            "no_match": ("NO_MATCH", "NO_MATCH"),
            "ambiguity": ("AMBIGUOUS", "AMBIGUOUS"),
            "empty": ("EMPTY", "EMPTY"),
            "format_only": ("FORMAT_ONLY", "FORMAT_ONLY"),
        }[expected["path"]]
        self.assertEqual((decision.state, decision.reason_code), (state, reason))
        if expected["rule_id"] == "must_be_none":
            self.assertIsNone(decision.winner)
            self.assertIsNone(decision.rule_id)
            self.assertIsNone(decision.selection_basis)
        else:
            self.assertIsNotNone(decision.winner)
            self.assertIsNotNone(decision.selection_basis)
            self.assertEqual(decision.rule_id, decision.winner.rule_id)
            self.assertEqual(decision.winner.intent, expected["intent"])
            self.assertIn(decision.winner, decision.evidence.candidates)
            if "winning_candidate" in expected:
                self.assertEqual(decision.rule_id, expected["winning_candidate"])
        if state in ("NO_MATCH", "EMPTY", "FORMAT_ONLY"):
            self.assertEqual(decision.evidence, DecisionEvidence((), ()))


class ResolutionTests(DecisionAssertions):
    def test_approved_resolver_cases(self):
        cases = [case for case in load_cases("resolver") if case["fixture"]["kind"] == "candidates"]
        self.assertEqual({case["case_id"] for case in cases}, {f"RES-{n:02}" for n in range(1, 14)})
        bases = {
            "RES-02": "SINGLE_CANDIDATE", "RES-03": "SINGLE_CANDIDATE",
            "RES-04": "SAME_INTENT_PRIORITY", "RES-05": "SAME_INTENT_SPECIFICITY",
            "RES-06": "SAME_INTENT_ASCII_RULE_ID", "RES-07": "SINGLE_CANDIDATE",
            "RES-09": "C08_INTRO_QUESTION", "RES-10": "C08_INTRO_QUESTION",
        }
        for case in cases:
            fixture = case["fixture"]
            rules = tuple(Rule(item["fixture_rule_id"], item["intent"], item["priority"],
                               item["specificity"], ("ตัวอย่าง",)) for item in fixture["candidates"])
            eligible = tuple(candidate(rule, (2 * i, 2 * i + 1))
                             for i, (rule, item) in enumerate(zip(rules, fixture["candidates"], strict=True))
                             if item["guard_passes"])
            context = ()
            if fixture["greeting_is_intro"]:
                opening = next(item for item in eligible if item.intent == "GREETING")
                context = tuple(intro(opening, item) for item in eligible
                                if item.intent in ("BOT_IDENTITY", "BOT_CAPABILITIES"))
            registry = RuleRegistry(rules)
            orders = permutations(eligible) if fixture["check_permutations"] else (eligible,)
            with self.subTest(case_id=case["case_id"]):
                first = None
                for order in orders:
                    result = resolve_candidates(order, matching_length=8, context_evidence=context,
                                                registry=registry)
                    self.assert_outcome(result, case["expected_outcome"])
                    self.assertEqual(result.selection_basis, bases.get(case["case_id"]))
                    self.assertEqual(result.evidence.candidates,
                                     tuple(sorted(eligible, key=lambda item: item.rule_id)))
                    self.assertCountEqual(result.evidence.context, context)
                    if first is None:
                        first = result
                    self.assertEqual(result, first)
                    self.assertEqual(resolve_candidates(order, matching_length=8,
                                                        context_evidence=context[::-1],
                                                        registry=registry), first)

    def test_large_ascii_tie_is_deterministic(self):
        rules = tuple(Rule(f"r{i:04}", "GREETING", -1, 2, ("ทัก",)) for i in range(2048))
        candidates = tuple(candidate(rule, (0, 3)) for rule in rules)
        shuffled = list(candidates)
        Random(9).shuffle(shuffled)
        registry = RuleRegistry(rules)
        first = resolve_candidates(candidates, matching_length=3, registry=registry)
        self.assertEqual(first.rule_id, "r0000")
        for order in (candidates[::-1], tuple(shuffled)):
            self.assertEqual(resolve_candidates(order, matching_length=3, registry=registry), first)

    def test_same_intent_ascii_punctuation_and_explicit_unknown_conflict(self):
        rules = tuple(Rule(identifier, "GREETING", 0, 1, ("ทัก",))
                      for identifier in ("a0", "a.1", "a-1"))
        greeting = tuple(candidate(rule, (0, 3)) for rule in rules)
        self.assertEqual(resolve_candidates(greeting, matching_length=3,
                                            registry=RuleRegistry(rules)).rule_id, "a-1")
        unknown = Rule("origin", "UNKNOWN", 100, 2, ("ทัก",))
        result = resolve_candidates((*greeting, candidate(unknown, (0, 3))), matching_length=3,
                                    registry=RuleRegistry((*rules, unknown)))
        self.assertEqual((result.state, result.rule_id), ("AMBIGUOUS", None))

    def test_cross_intent_uses_role_coverage_and_ignores_rank_values(self):
        greeting = Rule("a", "GREETING", 90, 2, ("ทัก",))
        identity = Rule("b", "BOT_IDENTITY", -5, 0, ("ถาม",))
        for rules in ((greeting, identity), (replace(greeting, priority=-5, specificity=0),
                                            replace(identity, priority=90, specificity=2))):
            opening, question = (candidate(rule, span) for rule, span in zip(rules, ((0, 2), (3, 5))))
            context = intro(opening, question)
            registry = RuleRegistry(rules)
            decision = resolve_candidates((question, opening), matching_length=7,
                                          context_evidence=(context, context), registry=registry)
            self.assertEqual((decision.state, decision.rule_id, decision.evidence.context),
                             ("RESOLVED", "b", (context,)))
            independent = replace(opening, spans=((0, 2), (6, 7)))
            decision = resolve_candidates((question, independent), matching_length=7,
                                          context_evidence=(context,), registry=registry)
            self.assertEqual((decision.state, decision.rule_id), ("AMBIGUOUS", None))


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.rule = Rule("hello", "GREETING", 2, 1, ("ทัก",))
        self.candidate = candidate(self.rule, (0, 3))
        self.registry = RuleRegistry((self.rule,))

    def test_registry_is_read_only_and_rejects_invalid_configuration(self):
        with self.assertRaisesRegex(RuntimeError, "^invalid_configuration:"):
            RuleRegistry([self.rule])
        with self.assertRaisesRegex(RuntimeError, "^duplicate_rule_id:"):
            RuleRegistry((self.rule, self.rule))
        with self.assertRaises(TypeError):
            self.registry.by_id["other"] = self.rule
        with self.assertRaises(FrozenInstanceError):
            self.registry.rules = ()
        self.assertIs(self.registry.by_id["hello"], self.rule)

    def test_unknown_rule_and_metadata_mismatch(self):
        for fields in ({"intent": "HELP"}, {"priority": -9}, {"specificity": 2}):
            with self.subTest(fields=fields):
                with self.assertRaisesRegex(RuntimeError, "^candidate_metadata_mismatch:"):
                    resolve_candidates((replace(self.candidate, **fields),), matching_length=3,
                                       registry=self.registry)
        with self.assertRaisesRegex(RuntimeError, "^unregistered_rule_id:"):
            resolve_candidates((replace(self.candidate, rule_id="other"),), matching_length=3,
                               registry=self.registry)

    def test_invalid_candidates_spans_and_duplicate_candidate(self):
        for fields in ({"rule_id": "UPPER"}, {"intent": "EMPTY_INPUT"}, {"intent": []},
                       {"priority": True}, {"specificity": 3}):
            with self.subTest(fields=fields), self.assertRaisesRegex(RuntimeError, "^invalid_candidate:"):
                resolve_candidates((replace(self.candidate, **fields),), matching_length=8,
                                   registry=self.registry)
        for spans in ((), ((True, 2),), ((0, 9),), ((0, 3), (0, 3)), ((5, 8), (0, 3)), ([0, 3],)):
            with self.subTest(spans=spans), self.assertRaisesRegex(RuntimeError, "^invalid_evidence_range:"):
                resolve_candidates((replace(self.candidate, spans=spans),), matching_length=8,
                                   registry=self.registry)
        with self.assertRaisesRegex(RuntimeError, "^duplicate_candidate:"):
            resolve_candidates((self.candidate, replace(self.candidate, spans=((5, 8),))),
                               matching_length=8, registry=self.registry)

    def test_role_must_reference_an_eligible_rule_and_span(self):
        rule = Rule("identity", "BOT_IDENTITY", 1, 1, ("ถาม",))
        second = candidate(rule, (4, 7))
        good = intro(self.candidate, second)
        primary = good.roles[1]
        registry = RuleRegistry((self.rule, rule))
        for bad in (
            replace(good, context_span=(0, 6)),
            replace(good, roles=good.roles[::-1]),
            replace(good, roles=(good.roles[0], replace(primary, rule_id="unknown"))),
            replace(good, roles=(good.roles[0], replace(primary, span=(4, 6)))),
            replace(good, roles=(good.roles[0], replace(primary, role=EvidenceRole.PRIMARY_REQUEST))),
            replace(good, source=EvidenceSource.R6_MIXED_STARTUP_REQUEST),
        ):
            with self.subTest(bad=bad), self.assertRaisesRegex(RuntimeError, "^invalid_role_evidence:"):
                resolve_candidates((self.candidate, second), matching_length=7,
                                   context_evidence=(bad,), registry=registry)

    def test_validation_precedence_is_independent_of_order(self):
        cases = (replace(self.candidate, spans=((0, 9),)), replace(self.candidate, rule_id="other"),
                 replace(self.candidate, specificity=2), replace(self.candidate, priority=True))
        for order in permutations(cases):
            with self.assertRaisesRegex(RuntimeError, "^invalid_candidate:"):
                resolve_candidates(order, matching_length=8, registry=self.registry)
        for order in permutations(cases[1:3]):
            with self.assertRaisesRegex(RuntimeError, "^unregistered_rule_id:"):
                resolve_candidates(order, matching_length=8, registry=self.registry)

    def test_decision_frozen_and_checks_state_winner_and_reason(self):
        result = resolve_candidates((self.candidate,), matching_length=3, registry=self.registry)
        with self.assertRaises(FrozenInstanceError):
            result.winner = None
        with self.assertRaises(FrozenInstanceError):
            result.evidence.candidates = ()
        for changes in ({"winner": None}, {"state": "RESOLVED"}, {"reason_code": "EXPLICIT_UNKNOWN"},
                        {"reason_code": type(result.reason_code).EXPLICIT_UNKNOWN},
                        {"selection_basis": type(result.selection_basis).SAME_INTENT_PRIORITY},
                        {"evidence": DecisionEvidence((), ())}):
            with self.subTest(changes=changes), self.assertRaisesRegex(RuntimeError, "^invalid_decision:"):
                replace(result, **changes)
        with self.assertRaisesRegex(RuntimeError, "^invalid_decision:"):
            DecisionRecord(type(result.state).NO_MATCH, None, type(result.reason_code).NO_MATCH,
                           result.evidence)


class RoutingIntegrationTests(DecisionAssertions):
    def test_approved_text_cases_at_decision_boundary(self):
        cases = {case["case_id"]: case for case in load_cases("intent")}
        self.assertEqual(len(cases), 57)
        for case_id, case in cases.items():
            with self.subTest(case_id=case_id):
                result = decide(case["fixture"]["value"])
                self.assert_outcome(result, case["expected_outcome"])
                if reference := case.get("same_result_as"):
                    expected = decide(cases[reference]["fixture"]["value"])
                    self.assertEqual(result, expected)
                if follow_up := case.get("follow_up_case"):
                    next_case = cases[follow_up]
                    self.assert_outcome(decide(next_case["fixture"]["value"]), next_case["expected_outcome"])

    def test_role_evidence_from_actual_matches(self):
        expected = {
            "INT-01": ("C08_INTRO_QUESTION", "greeting.direct", (0, 10), "identity.direct", (11, 20)),
            "INT-02": ("C08_INTRO_QUESTION", "greeting.direct", (0, 10), "capabilities.direct", (11, 29)),
            "OPEN-MIXED-REQUEST": ("R6_MIXED_STARTUP_REQUEST", "thanks.direct", (0, 10),
                                   "help.general", (11, 28)),
        }
        for case in load_cases("intent"):
            if case["case_id"] not in expected:
                continue
            with self.subTest(case_id=case["case_id"]):
                source, left, left_span, right, right_span = expected[case["case_id"]]
                decision = decide("  " + case["fixture"]["value"] + "  ")
                evidence, = decision.evidence.context
                self.assertEqual((evidence.source, decision.selection_basis, evidence.context_span),
                                 (source, source, (left_span[0], right_span[1])))
                self.assertEqual([(role.rule_id, role.span) for role in evidence.roles],
                                 [(left, left_span), (right, right_span)])
                roles = (("INTRODUCTORY", "PRIMARY_QUESTION") if source == "C08_INTRO_QUESTION"
                         else ("COURTESY", "PRIMARY_REQUEST"))
                self.assertEqual(tuple(role.role for role in evidence.roles), roles)

    def test_unapproved_compositions_do_not_receive_precedence(self):
        greetings = ("คุณคือใคร สวัสดีครับ", "ขอบคุณครับ ช่วยฉันหน่อย", "ขอบคุณ ช่วยเริ่มให้หน่อย")
        for text in greetings:
            with self.subTest(text=text):
                result = decide(text)
                self.assertEqual((result.state, result.winner, result.evidence.context),
                                 ("AMBIGUOUS", None, ()))

    def test_early_routing_bypasses_matcher_and_resolver(self):
        with (patch("thai_ai.candidates._find_matches", side_effect=AssertionError("matcher called")),
              patch("thai_ai.resolver.resolve_candidates", side_effect=AssertionError("resolver called"))):
            for case in load_cases("intent"):
                if case["expected_outcome"]["path"] in ("empty", "format_only"):
                    with self.subTest(case_id=case["case_id"]):
                        self.assert_outcome(decide(case["fixture"]["value"]), case["expected_outcome"])
            with self.assertRaisesRegex(ValueError, "^disallowed_control.*offset 1"):
                decide(" \x0b")

    def test_duplicate_registry_is_rejected_before_input(self):
        case = next(case for case in load_cases("resolver") if case["case_id"] == "ERR-CONFIG")
        rules = tuple(Rule(item["fixture_rule_id"], item["intent"], item["priority"],
                           item["specificity"], ("ทัก",)) for item in case["fixture"]["candidates"])
        with self.subTest(case_id=case["case_id"]):
            with self.assertRaisesRegex(RuntimeError, "^" + case["expected_outcome"]["reason"] + ":"):
                decide(None, rules=rules)

    def test_routing_normalizes_once_and_shares_registry(self):
        with (patch("thai_ai.resolver.normalize_text", wraps=normalize_text) as normalize,
              patch("thai_ai.resolver._collect_content", wraps=_collect_content) as collect,
              patch("thai_ai.resolver.resolve_candidates", wraps=resolve_candidates) as resolve):
            result = decide("สวัสดีครับ คุณคือใคร")
        self.assertEqual(result.rule_id, "identity.direct")
        normalize.assert_called_once()
        collect.assert_called_once()
        resolve.assert_called_once()
        self.assertIs(collect.call_args.args[1], resolve.call_args.kwargs["registry"])

    def test_guard_rejection_prevents_role_evidence(self):
        def guard(match):
            return match.rule.intent != "BOT_IDENTITY" and passes_guard(match)

        with patch("thai_ai.candidates.passes_guard", side_effect=guard):
            result = decide("สวัสดีครับ คุณคือใคร")
        self.assertEqual((result.rule_id, result.evidence.context), ("greeting.direct", ()))

    def test_multiple_spans_and_explicit_unknown(self):
        matched = decide("สวัสดีครับ สวัสดีครับ")
        self.assertEqual(matched.winner.spans, ((0, 10), (11, 21)))
        raw = next(case["fixture"]["value"] for case in load_cases("intent") if case["case_id"] == "DEV-026")
        rule = Rule("explicit", "UNKNOWN", 0, 2, (raw,))
        matched = decide(raw, rules=(rule,))
        self.assertEqual((matched.state, matched.reason_code, matched.rule_id),
                         ("RESOLVED", "EXPLICIT_UNKNOWN", "explicit"))
