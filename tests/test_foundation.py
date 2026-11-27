"""ตรวจว่า Package และเอกสารพื้นฐานพร้อมสำหรับการพัฒนา."""

import importlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FoundationTests(unittest.TestCase):
    def test_thai_ai_imports_from_repository(self):
        package = importlib.import_module("thai_ai")
        self.assertEqual(Path(package.__file__).resolve(), ROOT / "thai_ai/__init__.py")

    def test_tests_imports_from_repository(self):
        package = importlib.import_module("tests")
        self.assertEqual(Path(package.__file__).resolve(), ROOT / "tests/__init__.py")

    def test_project_documents_are_readable_as_utf8(self):
        for name in ("README.md", "DESIGN.md", "AGENTS.md"):
            with self.subTest(document=name):
                self.assertTrue((ROOT / name).read_text(encoding="utf-8").strip())
