"""ตรวจข้อกำหนดของ Development Dataset V0.1."""

from collections import Counter
import json
from pathlib import Path
import unittest

from scripts.evaluate_baseline import validate_dataset


DATASET = Path(__file__).resolve().parents[1] / "datasets/development/v0.1.json"
INTENTS = {
    "GREETING", "BOT_IDENTITY", "BOT_CAPABILITIES", "THANKS",
    "FAREWELL", "HELP", "UNKNOWN", "EMPTY_INPUT",
}


class DevelopmentDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = json.loads(DATASET.read_text(encoding="utf-8"))
        cls.samples = cls.dataset["samples"]

    def test_utf8_and_schema(self):
        self.assertEqual(self.dataset["version"], "v0.1")
        self.assertIn("ชุดข้อมูลพัฒนา", self.dataset["purpose"])
        self.assertEqual(validate_dataset(self.dataset), self.samples)
        for sample in self.samples:
            self.assertEqual(
                set(sample), {"id", "input", "expected_intent", "expected_behavior"}
            )

    def test_sample_count_and_taxonomy(self):
        self.assertEqual(len(self.samples), 32)
        self.assertEqual(
            Counter(sample["expected_intent"] for sample in self.samples),
            {intent: 4 for intent in INTENTS},
        )

    def test_unique_ids_and_inputs(self):
        self.assertEqual(len({sample["id"] for sample in self.samples}), 32)
        self.assertEqual(len({sample["input"] for sample in self.samples}), 32)

    def test_empty_input_and_whitespace(self):
        inputs = [
            sample["input"] for sample in self.samples
            if sample["expected_intent"] == "EMPTY_INPUT"
        ]
        self.assertIn("", inputs)
        self.assertTrue(any(value and value.isspace() for value in inputs))
        self.assertTrue(all(not value.strip() for value in inputs))

    def test_behavior_describes_each_intent(self):
        expected_cues = {
            "GREETING": "ทักทาย", "BOT_IDENTITY": "แนะนำตัว",
            "BOT_CAPABILITIES": "ขอบเขต", "THANKS": "ขอบคุณ",
            "FAREWELL": "กล่าวลา", "HELP": "เริ่มต้น",
            "UNKNOWN": "ไม่แต่งข้อมูล", "EMPTY_INPUT": "ป้อนข้อความ",
        }
        for sample in self.samples:
            with self.subTest(sample=sample["id"]):
                self.assertIn(
                    expected_cues[sample["expected_intent"]], sample["expected_behavior"]
                )
