"""ตรวจ Baseline และสูตรประเมินด้วยผลคาดหวังที่กำหนดไว้ล่วงหน้า."""

from hashlib import sha256
from pathlib import Path
import platform
import unittest

from scripts.evaluate_baseline import always_unknown, build_report, evaluate


def dataset_with(*cases):
    return {
        "version": "synthetic",
        "purpose": "กรณีจำลองสำหรับทดสอบสูตร",
        "samples": [
            {
                "id": f"CASE-{index}",
                "input": text,
                "expected_intent": intent,
                "expected_behavior": "ตอบให้สอดคล้องกับกรณีทดสอบ",
            }
            for index, (text, intent) in enumerate(cases, start=1)
        ],
    }


class BaselineTests(unittest.TestCase):
    def test_always_unknown_including_empty_input(self):
        for text in ("สวัสดี", "วันนี้ฝนจะตกไหม", "", " \t"):
            with self.subTest(text=text):
                self.assertEqual(always_unknown(text), "UNKNOWN")

    def test_accuracy_counts_and_confusion_matrix(self):
        dataset = dataset_with(
            ("สวัสดี", "GREETING"), ("หวัดดี", "GREETING"),
            ("ฝนจะตกไหม", "UNKNOWN"), ("", "EMPTY_INPUT"),
        )
        predictions = {
            "สวัสดี": "GREETING", "หวัดดี": "UNKNOWN",
            "ฝนจะตกไหม": "UNKNOWN", "": "GREETING",
        }
        metrics = evaluate(dataset, predictions.__getitem__)
        self.assertEqual(metrics["total_samples"], 4)
        self.assertEqual(metrics["correct_predictions"], 2)
        self.assertEqual(metrics["incorrect_predictions"], 2)
        self.assertEqual(metrics["intent_accuracy"], 0.5)
        self.assertEqual(
            metrics["per_intent"]["GREETING"], {"support": 2, "correct": 1, "accuracy": 0.5}
        )
        self.assertEqual(
            metrics["per_intent"]["UNKNOWN"], {"support": 1, "correct": 1, "accuracy": 1.0}
        )
        self.assertEqual(
            metrics["per_intent"]["EMPTY_INPUT"], {"support": 1, "correct": 0, "accuracy": 0.0}
        )
        self.assertEqual(
            metrics["per_intent"]["THANKS"], {"support": 0, "correct": 0, "accuracy": None}
        )
        matrix = metrics["confusion_matrix"]
        self.assertEqual(len(matrix), 8)
        self.assertTrue(all(row.keys() == matrix.keys() for row in matrix.values()))
        actual_counts = {
            (expected, predicted): count
            for expected, row in matrix.items()
            for predicted, count in row.items()
            if count
        }
        self.assertEqual(actual_counts, {
            ("GREETING", "GREETING"): 1, ("GREETING", "UNKNOWN"): 1,
            ("UNKNOWN", "UNKNOWN"): 1, ("EMPTY_INPUT", "GREETING"): 1,
        })

    def test_rejects_empty_dataset(self):
        with self.assertRaisesRegex(ValueError, "non-empty"):
            evaluate(dataset_with(), always_unknown)

    def test_rejects_invalid_expected_label(self):
        with self.assertRaisesRegex(ValueError, "CASE-1.*expected_intent"):
            evaluate(dataset_with(("สวัสดี", "BAD_LABEL")), always_unknown)

    def test_rejects_invalid_schema(self):
        for field, value in (("input", 42), ("expected_behavior", " "), ("id", None)):
            with self.subTest(field=field):
                dataset = dataset_with(("สวัสดี", "GREETING"))
                dataset["samples"][0][field] = value
                with self.assertRaisesRegex(ValueError, field):
                    evaluate(dataset, always_unknown)
        dataset = dataset_with(("สวัสดี", "GREETING"))
        del dataset["purpose"]
        with self.assertRaisesRegex(ValueError, "purpose"):
            evaluate(dataset, always_unknown)

    def test_rejects_duplicate_ids_and_inputs(self):
        dataset = dataset_with(("สวัสดี", "GREETING"), ("สวัสดี", "GREETING"))
        with self.assertRaisesRegex(ValueError, "duplicate input"):
            evaluate(dataset, always_unknown)
        dataset["samples"][1].update(id="CASE-1", input="หวัดดี")
        with self.assertRaisesRegex(ValueError, "duplicate id"):
            evaluate(dataset, always_unknown)

    def test_rejects_invalid_prediction(self):
        dataset = dataset_with(("สวัสดี", "GREETING"))
        for label in ("BAD_LABEL", None, []):
            with self.subTest(label=label):
                with self.assertRaisesRegex(ValueError, "CASE-1.*prediction"):
                    evaluate(dataset, lambda _text: label)

    def test_report_contains_metadata_and_metrics(self):
        root = Path(__file__).resolve().parents[1]
        path = root / "datasets/development/v0.1.json"
        report = build_report()
        self.assertEqual(report["baseline_strategy"], "Always-UNKNOWN")
        self.assertEqual(report["dataset"]["path"], "datasets/development/v0.1.json")
        self.assertEqual(report["dataset"]["version"], "v0.1")
        self.assertEqual(report["dataset"]["sha256"], sha256(path.read_bytes()).hexdigest())
        self.assertTrue(report["dataset"]["purpose"])
        self.assertTrue(report["evaluation_method"])
        self.assertEqual(report["confusion_matrix_axes"], {
            "rows": "expected_intent", "columns": "predicted_intent",
        })
        self.assertEqual(report["python_version"], platform.python_version())
        self.assertTrue(report["platform"])
        self.assertIn("Development Dataset", report["limitations"])
        self.assertIn("AI V0.1", report["limitations"])
        self.assertEqual(report["metrics"].keys(), {
            "total_samples", "correct_predictions", "incorrect_predictions",
            "intent_accuracy", "per_intent", "confusion_matrix",
        })
