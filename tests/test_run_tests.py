"""ตรวจ Exit Code ของ Test Runner ด้วยชุดทดสอบจำลอง."""

from contextlib import redirect_stderr
from io import StringIO
import unittest
from unittest.mock import patch

from scripts import run_tests


class TestRunnerTests(unittest.TestCase):
    def run_synthetic_suite(self, *checks):
        suite = unittest.TestSuite(unittest.FunctionTestCase(check) for check in checks)
        output = StringIO()
        with patch.object(unittest.defaultTestLoader, "discover", return_value=suite):
            with redirect_stderr(output):
                status = run_tests.main()
        return status, output.getvalue()

    def test_passing_suite_exits_zero(self):
        status, output = self.run_synthetic_suite(lambda: self.assertEqual(2 + 2, 4))
        self.assertEqual(status, 0)
        self.assertIn("Ran 1 test", output)
        self.assertIn("OK", output)

    def test_failure_exits_nonzero(self):
        def fail():
            self.fail("Synthetic failure")

        status, output = self.run_synthetic_suite(fail)
        self.assertNotEqual(status, 0)
        self.assertIn("failures=1", output)

    def test_error_exits_nonzero(self):
        def error():
            raise RuntimeError("Synthetic error")

        status, output = self.run_synthetic_suite(error)
        self.assertNotEqual(status, 0)
        self.assertIn("errors=1", output)

    def test_empty_suite_exits_nonzero(self):
        status, output = self.run_synthetic_suite()
        self.assertNotEqual(status, 0)
        self.assertIn("No tests discovered.", output)

    def test_all_skipped_suite_exits_nonzero(self):
        status, output = self.run_synthetic_suite(lambda: self.skipTest("Synthetic skip"))
        self.assertNotEqual(status, 0)
        self.assertIn("skipped=1", output)
        self.assertIn("No tests completed without being skipped.", output)

    def test_suite_with_pass_and_skip_exits_zero(self):
        status, output = self.run_synthetic_suite(
            lambda: self.assertEqual(2 + 2, 4),
            lambda: self.skipTest("Synthetic skip"),
        )
        self.assertEqual(status, 0)
        self.assertIn("Ran 2 tests", output)
        self.assertIn("OK (skipped=1)", output)
