"""跑全部单测，并把 {测试方法名: 状态} 写成 JSON——门禁的机读结果。

不解析 `unittest -v` 的文本：被测代码的打印和 ResourceWarning 会插进结果行（PR #9 实测）。

    python3 scripts/run_tests.py <result.json>
"""
import json
import sys
import unittest


class _Result(unittest.TextTestResult):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.status = {}

    def _mark(self, test, status):
        self.status[getattr(test, "_testMethodName", str(test))] = status

    def addSuccess(self, test):
        super().addSuccess(test)
        self._mark(test, "ok")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._mark(test, "FAIL")

    def addError(self, test, err):
        super().addError(test, err)
        self._mark(test, "ERROR")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._mark(test, "skipped")

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self._mark(test, "expected failure")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._mark(test, "unexpected success")


def main(out):
    suite = unittest.defaultTestLoader.discover("tests", top_level_dir=".")
    result = unittest.TextTestRunner(resultclass=_Result, verbosity=2).run(suite)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result.status, f, ensure_ascii=False, indent=1)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
