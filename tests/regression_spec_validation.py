"""Data validation for the V0.1 regression specification, used by unittest."""

import json
import re
import unicodedata

from scripts.evaluate_baseline import INTENTS, parse_dataset_json


REQUIREMENTS = frozenset({
    "BC-IN-01", "BC-IN-02", "BC-IN-03", "BC-SEL-01", "BC-OUT-01", "BC-OUT-02", "BC-ERR-01",
    *(f"BC-INT-{number:02}" for number in range(1, 9)),
})
CATEGORIES = frozenset({"input_validation", "normalization", "intent", "resolver", "response"})
NON_STRING = frozenset({"json_value", "bytes_hex", "str_subclass"})
BIDI_CONTROLS = frozenset({
    0x061C, 0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x2066, 0x206A),
})
CONTROL_ALLOWLIST = frozenset({0x09, 0x0A, 0x0D})
# Variation_Selector property from UCD 16.0.0, including the Mongolian selectors.
VARIATION_SELECTORS = frozenset({
    *range(0x180B, 0x180E), 0x180F, *range(0xFE00, 0xFE10), *range(0xE0100, 0xE01F0),
})
INTRO_QUESTION_INTENTS = frozenset({"BOT_IDENTITY", "BOT_CAPABILITIES"})
RESULT_KEYS = {"intent", "response", "rule_id"}
RULE_ID = re.compile(r"[a-z0-9][a-z0-9.-]*")
CASE_ID = re.compile(r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+")
PATHS = {
    "matched": set(INTENTS) - {"EMPTY_INPUT"},
    "no_match": {"UNKNOWN"},
    "format_only": {"UNKNOWN"},
    "ambiguity": {"UNKNOWN"},
    "empty": {"EMPTY_INPUT"},
}
MANDATORY_FIXTURES = {
    "input_validation": NON_STRING | {"text", "code_points"},
    "normalization": {"text"},
    "intent": {"text"},
    "resolver": {"candidates", "fault", "invalid_configuration"},
    "response": {"response_review", "wire_fields", "invalid_result"},
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(record, required, optional=()):
    require(type(record) is dict, "expected an object")
    keys = record.keys()
    require(required <= keys and keys <= required | set(optional), "unexpected or missing fields")


def nonblank(value):
    return isinstance(value, str) and bool(value.strip())


def rule_id(value):
    return isinstance(value, str) and RULE_ID.fullmatch(value) is not None


def character_reasons(cp):
    return {
        "surrogate": 0xD800 <= cp <= 0xDFFF,
        "disallowed_control": unicodedata.category(chr(cp)) == "Cc" and cp not in CONTROL_ALLOWLIST,
        "bidi_control": cp in BIDI_CONTROLS,
    }


def check_scalar_strings(value):
    """A surrogate is represented by integer code points, never by a JSON string."""
    if isinstance(value, str):
        require(not any(0xD800 <= ord(char) <= 0xDFFF for char in value),
                "surrogate in JSON string; use a code_points fixture")
    elif isinstance(value, list):
        for item in value:
            check_scalar_strings(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            check_scalar_strings(key)
            check_scalar_strings(item)


def result_fields(value):
    fields(value, RESULT_KEYS)
    require(value["intent"] in INTENTS, "result field intent is outside taxonomy")
    require(nonblank(value["response"]), "response must be a non-empty string")
    require(value["rule_id"] is None or rule_id(value["rule_id"]), "invalid result field rule_id")
    require(value["intent"] != "EMPTY_INPUT" or value["rule_id"] is None, "EMPTY_INPUT must have null rule_id")


def validate_candidates(candidates, *, expect_duplicates=False):
    require(type(candidates) is list, "candidates must be a list")
    ids = set()
    duplicate_found = False
    for candidate in candidates:
        fields(candidate, {"fixture_rule_id", "intent", "priority", "specificity", "guard_passes"})
        identifier = candidate["fixture_rule_id"]
        require(rule_id(identifier), "invalid fixture_rule_id")
        require(isinstance(candidate["intent"], str) and candidate["intent"] in PATHS["matched"],
                "invalid candidate intent")
        require(type(candidate["priority"]) is int, "priority must be an integer")
        level = candidate["specificity"]
        require(type(level) is int and level in (0, 1, 2), "invalid specificity")
        require(type(candidate["guard_passes"]) is bool, "guard_passes must be boolean")
        duplicate_found |= identifier in ids
        ids.add(identifier)
    require(duplicate_found == expect_duplicates, "unexpected duplicate candidate IDs or invalid fault fixture")


def validate_fixture(fixture, templates):
    require(type(fixture) is dict and isinstance(fixture.get("kind"), str), "invalid fixture kind")
    kind = fixture["kind"]
    if kind in {"text", "str_subclass", "json_value"}:
        fields(fixture, {"kind", "value"})
        value = fixture["value"]
        allowed = (type(None), bool, int, float, list, dict) if kind == "json_value" else (str,)
        require(type(value) in allowed, f"invalid {kind} fixture value")
    elif kind == "bytes_hex":
        fields(fixture, {"kind", "hex"})
        payload = fixture["hex"]
        require(isinstance(payload, str) and re.fullmatch(r"(?:[0-9a-f]{2})*", payload) is not None,
                "bytes_hex requires canonical hex byte pairs")
    elif kind == "code_points":
        fields(fixture, {"kind", "values"})
        points = fixture["values"]
        require(type(points) is list and all(type(cp) is int and 0 <= cp <= 0x10FFFF for cp in points),
                "invalid code_points fixture values")
        require(any(0xD800 <= cp <= 0xDFFF for cp in points), "use text for scalar-only strings")
    elif kind == "candidates":
        fields(fixture, {"kind", "candidates", "greeting_is_intro", "check_permutations"})
        validate_candidates(fixture["candidates"])
        require(type(fixture["greeting_is_intro"]) is bool, "greeting_is_intro must be boolean")
        require(type(fixture["check_permutations"]) is bool, "check_permutations must be boolean")
        if fixture["check_permutations"]:
            require(len(fixture["candidates"]) >= 2, "permutations need multiple candidates")
    elif kind == "invalid_configuration":
        fields(fixture, {"kind", "candidates"})
        validate_candidates(fixture["candidates"], expect_duplicates=True)
    elif kind == "fault":
        fields(fixture, {"kind", "stage"})
        require(fixture["stage"] in ("matching", "guard", "selection", "response"), "invalid fault stage")
    elif kind == "response_review":
        fields(fixture, {"kind", "template_id", "text"})
        require(isinstance(fixture["template_id"], str) and fixture["template_id"] in templates
                and nonblank(fixture["text"]), "invalid response review fixture")
    elif kind == "wire_fields":
        fields(fixture, {"kind", "fields"})
        result_fields(fixture["fields"])
    elif kind == "invalid_result":
        fields(fixture, {"kind", "values"})
        fields(fixture["values"], RESULT_KEYS)
        try:
            result_fields(fixture["values"])
        except ValueError:
            return kind
        raise ValueError("invalid_result fixture contains valid fields")
    else:
        raise ValueError(f"unknown fixture kind: {kind}")
    return kind


def validate_result(expected, fixture, templates):
    resolver = fixture["kind"] == "candidates"
    fields(expected, {"outcome", "intent", "path", "response_template", "rule_id"},
           {"winning_candidate"} if resolver else set())
    path = expected["path"]
    intent = expected["intent"]
    require(isinstance(path, str) and path in PATHS and isinstance(intent, str) and intent in PATHS[path],
            "incompatible intent or result path")
    response_id = expected["response_template"]
    require(isinstance(response_id, str) and response_id in templates, "unknown response template")
    template = templates[response_id]
    require((template["intent"], template["path"]) == (intent, path), "template does not match result path")
    matched = path == "matched"
    require(expected["rule_id"] == ("must_reference_winning_rule" if matched else "must_be_none"),
            "rule_id expectation does not match the result path")
    if resolver:
        require(path in ("matched", "no_match", "ambiguity"), "resolver fixture uses an input-only path")
        require(("winning_candidate" in expected) == matched, "resolver winner must be named only on match")


def validate_text_result_claim(text, path):
    """Check input-only invariants without assigning conversational intent."""
    require(not any(any(character_reasons(ord(char)).values()) for char in text),
            "text result requires valid input")
    content = [char for char in text if not char.isspace()]
    require((path == "empty") == (not content), "result path does not match blank input")
    format_only = bool(content) and all(
        unicodedata.category(char) == "Cf" or ord(char) in VARIATION_SELECTORS for char in content
    )
    require((path == "format_only") == format_only, "result path does not match format-only input")


def validate_resolver_claim(expected, fixture):
    """Check a supplied outcome against the decision table without selecting a winner."""
    eligible = [item for item in fixture["candidates"] if item["guard_passes"]]
    intents = {item["intent"] for item in eligible}
    intro_question = (
        fixture["greeting_is_intro"] and len(intents) == 2
        and "GREETING" in intents and bool(intents & INTRO_QUESTION_INTENTS)
    )
    if expected["path"] == "no_match":
        require(not eligible, "resolver no-match requires zero eligible candidates")
        return
    if expected["path"] == "ambiguity":
        require(len(intents) >= 2, "ambiguity needs multiple eligible intents")
        require(not intro_question, "ambiguity conflicts with declared cross-intent precedence")
        return

    intent = expected["intent"]
    winner = next((item for item in eligible
                   if item["fixture_rule_id"] == expected["winning_candidate"] and item["intent"] == intent), None)
    require(winner is not None, "winner must be an eligible candidate with the expected intent")
    require(len(intents) == 1 or (intro_question and intent in INTRO_QUESTION_INTENTS),
            "winner conflicts with declared cross-intent precedence")
    for peer in eligible:
        if peer["intent"] != intent:
            continue
        require(
            (-winner["priority"], -winner["specificity"], winner["fixture_rule_id"])
            <= (-peer["priority"], -peer["specificity"], peer["fixture_rule_id"]),
            "declared winner loses by priority, specificity or ASCII rule_id",
        )


def validate_exception(expected, fixture):
    kind = fixture["kind"]
    required = {"outcome", "type", "reason"}
    if kind in NON_STRING:
        fields(expected, required)
        require((expected["type"], expected["reason"]) == ("TypeError", "invalid_type"),
                "non-string and str subclass fixtures require TypeError")
    elif kind in {"text", "code_points"}:
        fields(expected, required | {"code_point_offset"})
        reason = expected["reason"]
        require(expected["type"] == "ValueError" and reason in
                ("surrogate", "disallowed_control", "bidi_control"), "invalid input exception")
        points = fixture["values"] if kind == "code_points" else list(map(ord, fixture["value"]))
        offset = expected["code_point_offset"]
        require(type(offset) is int and 0 <= offset < len(points), "invalid exception offset")
        require(character_reasons(points[offset])[reason], "exception reason does not match its code point")
        require(not any(any(character_reasons(cp).values()) for cp in points[:offset]),
                "exception must point to the first invalid code point")
    else:
        fields(expected, required)
        reason = {"fault": "propagate_fixture_fault", "invalid_configuration": "duplicate_rule_id",
                  "invalid_result": "invalid_result"}[kind]
        require((expected["type"], expected["reason"]) == ("RuntimeError", reason), "invalid internal exception")


def validate_expected(expected, fixture, templates):
    require(type(expected) is dict, "expected_outcome must be an object")
    kind = fixture["kind"]
    outcomes = {
        "text": ("result", "exception", "matching_view"),
        "candidates": ("result",),
        "wire_fields": ("serialization",),
        "response_review": ("manual_review",),
    }
    outcome = expected.get("outcome")
    require(outcome in outcomes.get(kind, ("exception",)), "outcome is incompatible with fixture")
    if outcome == "result":
        validate_result(expected, fixture, templates)
    elif outcome == "exception":
        validate_exception(expected, fixture)
    elif outcome == "matching_view":
        fields(expected, {"outcome", "value", "preserve_raw", "idempotent"})
        require(isinstance(expected["value"], str) and expected["preserve_raw"] is True
                and expected["idempotent"] is True, "invalid matching_view expectation")
    elif outcome == "serialization":
        fields(expected, {"outcome", "fields"})
        result_fields(expected["fields"])
        require(expected["fields"] == fixture["fields"], "serialization must preserve the three fields")
    elif outcome == "manual_review":
        fields(expected, {"outcome", "verdict"})
        require(expected["verdict"] in ("accept", "reject"), "unknown manual review verdict")
        template = templates[fixture["template_id"]]
        require((fixture["text"] == template["text"]) == (expected["verdict"] == "accept"),
                "review verdict conflicts with the stored template wording")


def validate_templates(templates):
    require(isinstance(templates, dict) and templates, "missing response templates")
    coverage = []
    for key, template in templates.items():
        require(re.fullmatch(r"[a-z][a-z_]*", key) is not None, "invalid response template ID")
        fields(template, {"intent", "path", "text", "rubric"})
        pair = (template["intent"], template["path"])
        require(all(isinstance(item, str) for item in pair), "invalid response template path or intent")
        require(nonblank(template["text"]) and nonblank(template["rubric"]), "empty response template or rubric")
        coverage.append(pair)
    required = {(intent, path) for path, intents in PATHS.items() for intent in intents}
    require(set(coverage) == required and len(coverage) == len(required), "template coverage is missing or repeated")


def validate_case(case, templates):
    fields(case, {"case_id", "category", "requirement_ids", "status", "fixture", "rationale"},
           {"expected_outcome", "source_scenarios", "source_sample_id", "open_decision",
            "same_result_as", "follow_up_case"})
    identifier = case["case_id"]
    require(isinstance(identifier, str) and CASE_ID.fullmatch(identifier), "invalid case_id")
    category = case["category"]
    require(isinstance(category, str) and category in CATEGORIES, "unknown category")
    require(nonblank(case["rationale"]), "rationale must be provided")
    requirements = case["requirement_ids"]
    require(type(requirements) is list and requirements and all(
        isinstance(identifier, str) and identifier in REQUIREMENTS for identifier in requirements
    ) and len(requirements) == len(set(requirements)), "invalid or duplicated Requirement ID")
    if "source_scenarios" in case:
        scenarios = case["source_scenarios"]
        require(type(scenarios) is list and scenarios and all(
            isinstance(item, str) and re.fullmatch(r"S(?:0[1-9]|1[0-9]|2[0-6])", item) for item in scenarios
        ) and len(scenarios) == len(set(scenarios)), "invalid or duplicated source scenario")
    for key in ("source_sample_id", "same_result_as", "follow_up_case"):
        if key in case:
            require(isinstance(case[key], str) and CASE_ID.fullmatch(case[key]), f"invalid {key}")
    kind = validate_fixture(case["fixture"], templates)
    status = case["status"]
    require(status in ("mandatory", "pending"), "unknown status")
    if status == "pending":
        require(kind == "text", "pending cases use a text fixture for review")
        require("expected_outcome" not in case and "same_result_as" not in case and
                "follow_up_case" not in case and "source_sample_id" not in case,
                "pending case cannot contain executable expectations")
        decision = case.get("open_decision")
        require(isinstance(decision, str) and re.fullmatch(r"Q-(?:0[0-9]|1[0-4])", decision),
                "pending case requires an Open Decision")
        return
    require("expected_outcome" in case and "open_decision" not in case, "invalid mandatory outcome fields")
    require(kind in MANDATORY_FIXTURES[category], "fixture does not belong to this category")
    expected = case["expected_outcome"]
    validate_expected(expected, case["fixture"], templates)
    if category in {"intent", "normalization", "input_validation"}:
        required_outcome = {"intent": "result", "normalization": "matching_view", "input_validation": "exception"}
        require(expected["outcome"] == required_outcome[category], "outcome does not belong to this category")
    if any(key in case for key in ("source_sample_id", "same_result_as", "follow_up_case")):
        require(category == "intent", "sample references and follow-up are for intent cases")


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def condition_key(case):
    fixture = case["fixture"].copy()
    if "candidates" in fixture:
        fixture["candidates"] = sorted(fixture["candidates"], key=canonical)
    fixture.pop("check_permutations", None)
    category = case["category"]
    if case["status"] == "pending":
        return ("pending", category), canonical(fixture)
    # Both categories invoke the Engine with the same configuration in this version.
    # Unit, wire and review fixtures represent separate execution targets.
    target = "engine" if category in {"input_validation", "intent"} else fixture["kind"]
    return target, canonical(fixture)


def assertion_key(case):
    return (case.get("same_result_as"), case.get("follow_up_case"),
            case["fixture"].get("check_permutations", False), case.get("open_decision"))


def validate_regression_spec(spec):
    check_scalar_strings(spec)
    fields(spec, {"version", "response_templates", "cases"})
    require(spec["version"] == "v0.1", "unsupported regression spec version")
    templates = spec["response_templates"]
    validate_templates(templates)
    require(isinstance(spec["cases"], list) and spec["cases"], "no Regression Cases")
    ids = {}
    conditions = {}
    mandatory_requirements = set()
    for index, case in enumerate(spec["cases"], 1):
        try:
            validate_case(case, templates)
            identifier = case["case_id"]
            require(identifier not in ids, "duplicate case_id")
            key = condition_key(case)
            group = conditions.setdefault(key, {})
            assertions = assertion_key(case)
            if group:
                previous = next(iter(group.values()))
                require(previous.get("expected_outcome") == case.get("expected_outcome"),
                        f"conflicting expected outcomes with {previous['case_id']}")
                if assertions in group:
                    raise ValueError(f"duplicate fixture conditions with {group[assertions]['case_id']}")
            ids[identifier] = case
            group[assertions] = case
            if case["status"] == "mandatory":
                mandatory_requirements.update(case["requirement_ids"])
        except ValueError as error:
            raise ValueError(f"case row {index}: {error}") from error
    require(mandatory_requirements == REQUIREMENTS,
            f"missing mandatory coverage: {sorted(REQUIREMENTS - mandatory_requirements)}")
    for case in ids.values():
        expected = case.get("expected_outcome", {})
        if expected.get("outcome") == "result":
            fixture = case["fixture"]
            try:
                if fixture["kind"] == "text":
                    validate_text_result_claim(fixture["value"], expected["path"])
                else:
                    validate_resolver_claim(expected, fixture)
            except ValueError as error:
                raise ValueError(f"case {case['case_id']}: {error}") from error
        for key in ("same_result_as", "follow_up_case"):
            if key not in case:
                continue
            target = ids.get(case[key])
            require(target is not None and target is not case and target["status"] == "mandatory"
                    and target["category"] == "intent" and key not in target, f"invalid {key} target")
            if key == "same_result_as":
                require(target["expected_outcome"] == case["expected_outcome"], "conflicting same_result_as")
    return spec


def parse_regression_spec(raw):
    """Read UTF-8 using the same strict JSON parser as the baseline evaluator."""
    return validate_regression_spec(parse_dataset_json(raw.decode("utf-8")))
