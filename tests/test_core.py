import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from sunflower import agents, host  # noqa: E402

FAKE = [sys.executable, str(pathlib.Path(__file__).with_name("fake_codex.py"))]


class Recorder:
    def __init__(self):
        self.events, self.done = [], threading.Event()

    def __call__(self, event, data):
        self.events.append((event, data))
        if event == "announce":
            self.done.set()

    def of(self, name):
        return [d for e, d in self.events if e == name]


def git_repo():
    d = pathlib.Path(tempfile.mkdtemp())
    for cmd in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"],
                ["commit", "-q", "--allow-empty", "-m", "init"]):
        subprocess.run(["git", "-C", str(d), *cmd], check=True)
    return d


class VoiceSummaryTest(unittest.TestCase):
    def test_prefers_marked_line(self):
        self.assertEqual(agents.voice_summary("做完了\n语音摘要：加了三个测试，全部通过"), "加了三个测试，全部通过")

    def test_falls_back_to_first_sentence_without_markdown(self):
        self.assertEqual(agents.voice_summary("已创建 `hello.py`。细节如下"), "已创建 hello.py。")

    def test_truncates_and_never_empty(self):
        self.assertTrue(agents.voice_summary("语音摘要：" + "长" * 100).endswith("…"))
        self.assertEqual(agents.voice_summary(""), "任务完成")


class DescribeTest(unittest.TestCase):
    def test_strips_shell_wrapper(self):
        ev = {"type": "item.started", "item": {"type": "command_execution", "command": "/bin/zsh -lc 'pytest -q'"}}
        self.assertEqual(agents.describe(ev), ("cmd", "pytest -q"))

    def test_failed_command_kind(self):
        ev = {"type": "item.completed", "item": {"type": "command_execution", "command": "x", "exit_code": 1}}
        self.assertEqual(agents.describe(ev)[0], "cmd_fail")

    def test_reconnect_warning_is_chinese(self):
        ev = {"type": "error", "message": "Reconnecting... 2/5 (stream disconnected before completion: stream closed)"}
        self.assertEqual(agents.describe(ev), ("warn", "上游连接中断，自动重试 2/5"))
        self.assertEqual(agents.describe({"type": "error", "message": "boom"}), ("warn", "boom"))

    def test_message_hides_home_and_link_targets(self):
        home = os.path.expanduser("~")
        text = f"问题在 [todo.py 第 37 行]({home}/ws/todo.py:37)，另见 {home}/ws"
        kind, out = agents.describe({"type": "item.completed", "item": {"type": "agent_message", "text": text}})
        self.assertEqual((kind, out), ("msg", "问题在 todo.py 第 37 行，另见 ~/ws"))


class ChannelTest(unittest.TestCase):
    def test_codex_argv_selects_channel_profile_and_overrides(self):
        argv = agents.codex_argv("icodeeasy", ["-c", "model_providers.icodeeasy.supports_websockets=false"])
        i = argv.index("--profile")
        self.assertEqual(argv[i + 1], "icodeeasy")
        self.assertIn("model_providers.icodeeasy.supports_websockets=false", argv)
        self.assertNotIn("qiniu-gpt", argv)
        self.assertEqual(agents.CODEX_BASE[agents.CODEX_BASE.index("--profile") + 1], "qiniu-gpt")

    def test_resolve_channel_accepts_configured_or_existing_profile(self):
        home = pathlib.Path(tempfile.mkdtemp())
        (home / "openai.config.toml").write_text("model = 'x'\n")
        hcfg = {"codex_channels": {"icodeeasy": ["-c", "a=1"]}}
        self.assertIn("a=1", host.resolve_channel(hcfg, "icodeeasy", codex_home=home))
        self.assertIn("openai", host.resolve_channel(hcfg, "openai", codex_home=home))
        with self.assertRaises(ValueError):
            host.resolve_channel(hcfg, "nope", codex_home=home)


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.ws = git_repo()
        self.rec = Recorder()
        self.r = agents.CodexRunner(self.ws, self.rec, base_argv=FAKE, run_dir=tempfile.mkdtemp())

    def run_task(self, text):
        self.rec.done.clear()
        res = self.r.dispatch(text)
        self.assertTrue(self.rec.done.wait(10), "no announce")
        return res

    def test_dispatch_returns_immediately_then_announces_and_commits(self):
        t0 = time.time()
        res = self.r.dispatch("加功能")
        self.assertLess(time.time() - t0, 1.0)
        self.assertTrue(res["ok"])
        self.assertTrue(self.rec.done.wait(10))
        self.assertEqual(self.rec.of("announce")[-1]["text"], "新增功能，测试通过")
        idle = self.rec.of("state")[-1]
        self.assertEqual((idle["state"], idle["exit"]), ("idle", 0))
        self.assertTrue(idle["commit"])
        log = subprocess.run(["git", "-C", str(self.ws), "log", "-1", "--format=%s"], capture_output=True, text=True)
        self.assertEqual(log.stdout.strip(), "voice: 加功能")

    def test_second_task_resumes_thread(self):
        self.run_task("第一步")
        self.assertEqual(self.r.thread_id, "thread-123")
        self.run_task("第二步")
        self.assertTrue(self.rec.of("state")[-2]["resume"])
        self.assertEqual((self.ws / "feature.txt").read_text(), "resumed\n")

    def test_busy_rejects_and_undo_reverts(self):
        self.run_task("加功能")
        self.assertTrue(self.r.undo()["ok"])
        self.assertFalse((self.ws / "feature.txt").exists())
        self.assertFalse(self.r.undo()["ok"])  # HEAD is now a revert, not a voice commit

    def test_failure_is_announced_not_committed(self):
        self.run_task("FAIL")
        self.assertIn("失败", self.rec.of("announce")[-1]["text"])
        self.assertIsNone(self.rec.of("state")[-1]["commit"])


class DemoResetTest(unittest.TestCase):
    def test_reset_copies_template_as_fresh_repo_with_planted_bug(self):
        from sunflower import demo
        ws = pathlib.Path(tempfile.mkdtemp()) / "ws"
        demo.reset(ws)
        log = subprocess.run(["git", "-C", str(ws), "log", "--format=%s"], capture_output=True, text=True)
        self.assertEqual(log.stdout.strip(), "init demo workspace")
        r = subprocess.run([sys.executable, "-m", "unittest"], cwd=ws, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0, "planted bug must make the demo tests fail")

    def test_refuses_workspace_inside_repo(self):
        from sunflower import config, demo
        with self.assertRaises(SystemExit):
            demo.reset(config.ROOT / "demo" / "scratch")

    def test_new_session_forgets_thread(self):
        rec = Recorder()
        r = agents.CodexRunner(git_repo(), rec, base_argv=FAKE, run_dir=tempfile.mkdtemp())
        r.thread_id = "old"
        self.assertTrue(r.new_session()["ok"])
        self.assertIsNone(r.thread_id)


class HostApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bus = host.Bus()
        cls.runner = agents.CodexRunner(git_repo(), cls.bus.emit, base_argv=FAKE, run_dir=tempfile.mkdtemp())
        def resolve(name):
            if name != "alt":
                raise ValueError(name)
            return list(FAKE)
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), host.make_handler(cls.bus, cls.runner, "tok", resolve))
        cls.srv.daemon_threads = True
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def post(self, path, body, token="tok"):
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode(), method="POST",
                                     headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read())

    def test_rejects_bad_token(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.post("/api/status", {}, token="nope")
        self.assertEqual(cm.exception.code, 401)

    def test_dispatch_then_sse_carries_announce(self):
        self.assertTrue(self.post("/api/dispatch", {"text": "加功能"})["ok"])
        deadline, seen = time.time() + 10, []
        with urllib.request.urlopen(self.base + "/events?t=tok", timeout=10) as r:
            for raw in r:
                line = raw.decode().strip()
                if line.startswith("event: "):
                    seen.append(line[7:])
                if "announce" in seen or time.time() > deadline:
                    break
        self.assertIn("log", seen)
        self.assertIn("announce", seen)

    def test_health_reports_commits(self):
        with urllib.request.urlopen(self.base + "/health", timeout=5) as r:
            h = json.loads(r.read())
        self.assertRegex(h["commit"], r"^[0-9a-f]{7,}$")
        self.assertIn("pid", h)
        req = urllib.request.Request(self.base + "/events?replay=0", headers={
            "Authorization": "Bearer tok", "X-Sunflower-Commit": "dev1234"})
        with urllib.request.urlopen(req, timeout=5):
            with urllib.request.urlopen(self.base + "/health", timeout=5) as r:
                h = json.loads(r.read())
        self.assertEqual(h["device"]["commit"], "dev1234")

    def test_channel_switch_api(self):
        res = self.post("/api/channel", {"name": "alt"})
        self.assertTrue(res["ok"])
        self.assertEqual(self.runner.channel, "alt")
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.post("/api/channel", {"name": "nope"})
        self.assertEqual(cm.exception.code, 400)

    def test_empty_dispatch_asks_again(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.post("/api/dispatch", {"text": " "})
        self.assertEqual(cm.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
