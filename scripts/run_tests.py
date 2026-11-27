"""รันชุดทดสอบของโครงการและส่ง Exit Code ให้ Local CI หรือ GitHub Actions."""

from pathlib import Path
import sys
import unittest


class TestResult(unittest.TextTestResult):
    """นับผลผ่านโดยตรงเพื่อแยกจาก Test และ Subtest ที่ถูก Skip."""

    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.passed = 0

    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed += 1


def main():
    """ค้นหาและรัน Test จาก Repository แล้วคืน Exit Code."""
    root = Path(__file__).resolve().parents[1]
    suite = unittest.defaultTestLoader.discover(
        start_dir=str(root / "tests"),
        pattern="test_*.py",
        top_level_dir=str(root),
    )
    if suite.countTestCases() == 0:
        print("No tests discovered.", file=sys.stderr)
        return 1

    result = unittest.TextTestRunner(verbosity=2, resultclass=TestResult).run(suite)
    if not result.wasSuccessful():
        return 1
    if not (result.passed or result.expectedFailures):
        print("No tests completed without being skipped.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
