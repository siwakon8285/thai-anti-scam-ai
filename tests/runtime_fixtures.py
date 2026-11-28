"""Read approved expectations without running the specification validator."""

from pathlib import Path

from scripts.evaluate_baseline import parse_dataset_json


_SPEC_PATH = Path(__file__).resolve().parents[1] / "datasets/regression/v0.1.json"


def load_cases(category: str) -> list[dict]:
    specification = parse_dataset_json(_SPEC_PATH.read_text(encoding="utf-8"))
    return [
        case for case in specification["cases"]
        if case["status"] == "mandatory" and case["category"] == category
    ]
