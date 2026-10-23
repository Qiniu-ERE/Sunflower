import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

from scripts import gate_check as gc

ROOT = pathlib.Path(__file__).resolve().parents[1]

HEAD = {"test_a": "ok", "test_b": "ok", "test_new": "ok"}
BASE = {"test_a": "ok", "test_b": "FAIL", "test_new": "ERROR"}

NOISY_SUITE = """\
import subprocess, sys, unittest

class T(unittest.TestCase):
    def test_noisy_but_ok(self):
        print("device log line")                                   # 被测代码的打印
        subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.2)"])  # 触发 ResourceWarning

    def test_fails(self):
        self.fail("x")
"""


class ParseTest(unittest.TestCase):
    def test_runner_reports_status_despite_prints_and_warnings(self):
        d = pathlib.Path(tempfile.mkdtemp())
        (d / "tests").mkdir()
        (d / "tests" / "__init__.py").write_text("")
        (d / "tests" / "test_noisy.py").write_text(NOISY_SUITE)
        out = d / "r.json"
        subprocess.run([sys.executable, "-W", "always", str(ROOT / "scripts/run_tests.py"), str(out)],
                       cwd=d, capture_output=True)
        self.assertEqual(json.loads(out.read_text()), {"test_noisy_but_ok": "ok", "test_fails": "FAIL"})

    def test_spec_tests_from_pr_body(self):
        body = "## 规格（不变量 → 测试）\n- 派发立即返回 → `test_new`\n- 撤销只动 voice 提交 → `test_b`\n\n## 验证\n`test_x`\n"
        self.assertEqual(gc.spec_tests(body), ["test_new", "test_b"])

    def test_exemption_reason(self):
        self.assertEqual(gc.exemption("x\n写红豁免: 纯重构，行为不变\n"), "纯重构，行为不变")
        self.assertIsNone(gc.exemption("写红豁免:   \n"))


class EvaluateTest(unittest.TestCase):
    def test_passes_when_spec_tests_red_on_base_green_on_head(self):
        ok, lines = gc.evaluate(["test_b", "test_new"], BASE, HEAD)
        self.assertTrue(ok, lines)

    def test_fails_when_spec_test_already_green_on_base(self):
        ok, lines = gc.evaluate(["test_a"], BASE, HEAD)
        self.assertFalse(ok)
        self.assertIn("test_a", "\n".join(lines))

    def test_fails_when_spec_test_missing_on_head(self):
        ok, _ = gc.evaluate(["test_ghost"], {}, HEAD)
        self.assertFalse(ok)

    def test_test_absent_on_base_counts_as_red(self):
        ok, _ = gc.evaluate(["test_new"], {}, HEAD)
        self.assertTrue(ok)

    def test_fails_without_any_spec(self):
        ok, _ = gc.evaluate([], BASE, HEAD)
        self.assertFalse(ok)


class ShellLintTest(unittest.TestCase):
    def test_vars_are_braced_before_non_ascii(self):
        # bash 在部分 locale 下把紧跟的全角字符算进变量名：「$n：」→ unbound variable `n：`
        bad = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*(?=[^\x00-\x7f])")
        scripts = list((ROOT / "scripts").rglob("*.sh")) + [ROOT / "scripts/git-hooks/pre-push"]
        hits = [f"{p.relative_to(ROOT)}:{i}" for p in scripts
                for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if bad.search(line)]
        self.assertEqual(hits, [], "改成 ${var} 写法")


class WorkflowLockTest(unittest.TestCase):
    def test_ci_runs_the_same_gate_on_pr_and_main(self):
        wf = (ROOT / ".github/workflows/gate.yml").read_text(encoding="utf-8")
        self.assertIn("pull_request", wf)
        self.assertIn("branches: [main]", wf)
        self.assertIn("scripts/gate.sh", wf)


if __name__ == "__main__":
    unittest.main()
