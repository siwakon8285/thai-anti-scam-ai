"""ตรวจ Strict JSON Parsing และการเขียนรายงานผ่าน CLI."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from scripts import evaluate_baseline


ROOT = Path(__file__).resolve().parents[1]
VALID_DATASET = """{
    "version": "v0.1",
    "purpose": "ทดสอบ CLI",
    "samples": [{
        "id": "QA-1",
        "input": "ฝนจะตกไหม",
        "expected_intent": "UNKNOWN",
        "expected_behavior": "แจ้งขอบเขต"
    }]
}"""
INVALID_DATASETS = (
    ("syntax", '{"samples": [}', "Evaluation error:"),
    ("nan", VALID_DATASET[:-1] + ',"extra": NaN}', "Non-standard JSON constant: NaN"),
    (
        "duplicate",
        VALID_DATASET.replace(
            '"expected_intent": "UNKNOWN"',
            '"expected_intent": "INVALID_INTENT", "expected_intent": "UNKNOWN"',
        ),
        "Duplicate JSON object key: 'expected_intent'",
    ),
)


class StrictJsonTests(unittest.TestCase):
    def test_rejects_nonstandard_constants(self):
        for token in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(token=token):
                with self.assertRaisesRegex(ValueError, f"Non-standard JSON constant: {token}"):
                    evaluate_baseline.parse_dataset_json(f'{{"extra": {token}}}')

    def test_rejects_duplicate_sample_fields(self):
        for key, raw_pair in (
            ("expected_intent", '"expected_intent": "INVALID_INTENT", "expected_intent": "UNKNOWN"'),
            ("input", '"input": 42, "input": "ทดสอบ"'),
            ("id", '"id": null, "id": "QA-1"'),
            ("id", r'"id": null, "\u0069d": "QA-1"'),
        ):
            with self.subTest(raw_pair=raw_pair):
                with self.assertRaisesRegex(ValueError, f"Duplicate JSON object key: '{key}'"):
                    evaluate_baseline.parse_dataset_json(f'{{"samples": [{{{raw_pair}}}]}}')

    def test_rejects_duplicate_object_keys_at_any_depth(self):
        for raw_json in (
            '{"version": null, "version": "v0.1"}',
            '{"metadata": [{"nested": {"version": null, "version": "v0.1"}}]}',
        ):
            with self.subTest(raw_json=raw_json):
                with self.assertRaisesRegex(ValueError, "Duplicate JSON object key: 'version'"):
                    evaluate_baseline.parse_dataset_json(raw_json)

    def test_rejects_numbers_that_overflow_float(self):
        for number in ("1e400", "-1e400"):
            with self.subTest(number=number):
                with self.assertRaisesRegex(ValueError, "finite float range"):
                    evaluate_baseline.parse_dataset_json(f'{{"extra": {number}}}')

    def test_loads_valid_json(self):
        raw_json = '{"id": "top", "nested": {"id": "ชั้นใน", "number": 1e308}, "items": [null, 3]}'
        self.assertEqual(
            evaluate_baseline.parse_dataset_json(raw_json),
            {"id": "top", "nested": {"id": "ชั้นใน", "number": 1e308}, "items": [None, 3]},
        )


class BaselineCliTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(dir=ROOT, prefix=".baseline-cli-")
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name)
        scripts = self.workspace / "scripts"
        scripts.mkdir()
        for name in ("__init__.py", "evaluate_baseline.py"):
            shutil.copyfile(ROOT / "scripts" / name, scripts / name)
        self.dataset = self.workspace / "datasets/development/v0.1.json"
        self.dataset.parent.mkdir(parents=True)

    def run_cli(self, raw_json, output):
        self.dataset.write_text(raw_json, encoding="utf-8")
        return subprocess.run(
            [sys.executable, "-B", "-m", "scripts.evaluate_baseline", "--output", str(output)],
            cwd=self.workspace,
            capture_output=True,
            timeout=10,
        )

    def assert_rejected(self, result, message):
        error = result.stderr.decode("utf-8")
        self.assertEqual(result.returncode, 1, error)
        self.assertEqual(result.stdout, b"")
        self.assertIn("Evaluation error:", error)
        self.assertIn(message, error)

    def test_invalid_input_does_not_create_report(self):
        for case, raw_json, message in INVALID_DATASETS:
            with self.subTest(case=case):
                output = self.workspace / "reports" / f"{case}.json"
                self.assert_rejected(self.run_cli(raw_json, output), message)
                self.assertFalse(output.exists())

    def test_invalid_input_preserves_existing_report(self):
        original = b'{"preserve":true}\n'
        for case, raw_json, message in INVALID_DATASETS:
            with self.subTest(case=case):
                output = self.workspace / f"{case}.json"
                output.write_bytes(original)
                self.assert_rejected(self.run_cli(raw_json, output), message)
                self.assertEqual(output.read_bytes(), original)

    def test_valid_input_writes_report_matching_stdout(self):
        output = self.workspace / "reports/baseline.json"
        result = self.run_cli(VALID_DATASET, output)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
        self.assertEqual(result.stderr, b"")
        self.assertEqual(output.read_bytes(), result.stdout)
        metrics = json.loads(result.stdout)["metrics"]
        self.assertEqual(metrics["total_samples"], 1)
        self.assertEqual(metrics["correct_predictions"], 1)
        self.assertEqual(metrics["incorrect_predictions"], 0)
        self.assertEqual(metrics["intent_accuracy"], 1.0)
