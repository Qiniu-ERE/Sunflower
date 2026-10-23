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

    def test_resolve_channel_requires_provider_env_key(self):
        # icodeeasy 的 provider 从环境变量取 key；launchd 服务环境里没有时，切换要当场失败并说清怎么补
        home = pathlib.Path(tempfile.mkdtemp())
        (home / "config.toml").write_text(
            '[model_providers.icodeeasy]\nname = "icodeeasy"\nenv_key = "OPENAI_API_KEY"\n\n'
            '[model_providers.qiniu-gpt]\nname = "q"\n[model_providers.qiniu-gpt.auth]\ncommand = "/usr/bin/security"\n')
        (home / "icodeeasy.config.toml").write_text('model = "m"\nmodel_provider = "icodeeasy"\n')
        (home / "qiniu-gpt.config.toml").write_text('model_provider = "qiniu-gpt"\n')
        hcfg = {"codex_channels": {"icodeeasy": [], "qiniu-gpt": []}}
        with self.assertRaises(ValueError) as cm:
            host.resolve_channel(hcfg, "icodeeasy", codex_home=home, environ={})
        self.assertIn("OPENAI_API_KEY", str(cm.exception))
        self.assertIn("--keychain-env", str(cm.exception))
        self.assertIn("icodeeasy", host.resolve_channel(hcfg, "icodeeasy", codex_home=home,
                                                        environ={"OPENAI_API_KEY": "x"}))
        self.assertIn("qiniu-gpt", host.resolve_channel(hcfg, "qiniu-gpt", codex_home=home, environ={}))


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
        self.assertIn("可以说", self.rec.of("announce")[-1]["text"])  # 出错带下一步（#10）
        self.assertNotIn("撤销", self.rec.of("announce")[-1]["text"])  # 失败不提交，撤销会撤掉上一次成功的
        self.assertIsNone(self.rec.of("state")[-1]["commit"])

    def test_misheard_stop_word_cancels_instead_of_dispatching(self):
        # 平台 ASR 常把「停下」听成「听下」，灵矽又可能把它当新需求 dispatch（#35）
        self.assertTrue(self.r.dispatch("SLOW 跑个大任务")["ok"])
        res = self.r.dispatch("嗯，听下。")
        self.assertTrue(res["ok"], res)
        self.assertTrue(self.rec.done.wait(10), "cancel did not stop the task")
        self.assertIn("取消", self.rec.of("announce")[-1]["text"])
        for said in ("听下", "挺下", "停止", "别做了"):
            res = self.r.dispatch(said)
            self.assertFalse(res["ok"], said)           # 空闲时也不派出一个叫「听下」的任务
            self.assertIn("没有在执行", res["say"], said)
        self.assertEqual(len([s for s in self.rec.of("state") if s.get("state") == "running"]), 1)
        for real in ("听一下测试结果", "停止按钮改成红色", "把下载停下来的逻辑修一下"):
            self.assertFalse(agents.stop_intent(real), real)  # 带了别的内容就是正常需求


class LinxPromptTest(unittest.TestCase):
    def test_prompt_maps_single_words_to_tools(self):
        # 说话费力时只说一两个字也要路由对（#10）
        from sunflower import linx_admin
        p = linx_admin.SYSTEM_PROMPT
        for word, tool in (("「停」", "cancel"), ("「撤」", "undo"), ("「进度」", "status"), ("「修」", "dispatch")):
            line = next((l for l in p.splitlines() if word in l), "")
            self.assertIn(tool, line, word)

    def test_prompt_routes_stop_homophones_to_cancel(self):
        from sunflower import linx_admin
        line = next(l for l in linx_admin.SYSTEM_PROMPT.splitlines() if "「停」" in l)
        for word in ("「听下」", "「挺下」"):
            self.assertIn(word, line)


class ReadOnlyIntentTest(unittest.TestCase):
    """只问不改：检查 / 看看 / 有没有问题 → 只读沙箱，不会生成 voice: 提交（#15）。"""

    def test_read_only_intent_classifier(self):
        for text in ("检查一下代码有没有逻辑问题", "看看测试为什么失败", "这个函数是干什么的", "帮我 review 一下"):
            self.assertTrue(agents.read_only_intent(text), text)
        for text in ("那就把它修好", "检查一下，有问题就修掉", "给待办清单加一个删除命令", "跑一下测试", "撤销刚才的改动"):
            self.assertFalse(agents.read_only_intent(text), text)

    def test_check_request_runs_read_only_and_never_commits(self):
        ws, rec = git_repo(), Recorder()
        r = agents.CodexRunner(ws, rec, base_argv=FAKE + ["-s", "danger-full-access"], run_dir=tempfile.mkdtemp())
        r.dispatch("检查一下代码有没有逻辑问题")
        self.assertTrue(rec.done.wait(10), "no announce")
        log = subprocess.run(["git", "-C", str(ws), "log", "--oneline"], capture_output=True, text=True).stdout
        self.assertNotIn("voice:", log)
        self.assertIsNone(rec.of("state")[-1]["commit"])
        self.assertTrue(rec.of("state")[0]["read_only"])

    def test_check_request_can_run_tests_and_edits_are_stashed_not_committed(self):
        # 只读沙箱连临时文件都写不了，演示测试会全红（0.164 实测）→ 检查类用 workspace-write；
        # Codex 若仍改了文件，主机收进 stash、不提交，工作区保持原样（#15）
        ws, rec = git_repo(), Recorder()
        r = agents.CodexRunner(ws, rec, base_argv=FAKE + ["-s", "danger-full-access"], run_dir=tempfile.mkdtemp())
        self.assertEqual(r.base_for("检查一下代码有没有逻辑问题")[-1:], ["workspace-write"])
        r.dispatch("检查一下代码有没有逻辑问题")
        self.assertTrue(rec.done.wait(10), "no announce")
        git = lambda *a: subprocess.run(["git", "-C", str(ws), *a], capture_output=True, text=True).stdout
        self.assertEqual(git("status", "--porcelain"), "")
        self.assertIn("voice-check:", git("stash", "list"))
        self.assertIn("stash", rec.of("announce")[-1]["text"])


class CodexHomeTest(unittest.TestCase):
    def test_isolated_codex_home_keeps_only_channel_config(self):
        # 演示用的 Codex 不该读到使用者的个人 AGENTS.md / 记忆 / 技能 / MCP（#15）
        src, dst = pathlib.Path(tempfile.mkdtemp()), pathlib.Path(tempfile.mkdtemp()) / "codex-home"
        (src / "config.toml").write_text(
            'model = "x"\nskills.max_context_tokens = 4000\n\n[model_providers.p]\nbase_url = "https://p"\n'
            '[model_providers.p.auth]\ncommand = "/usr/bin/security"\n\n[mcp_servers.notion]\ncommand = "npx"\n'
            '[[skills.config]]\npath = "/s/SKILL.md"\n[projects."/h"]\ntrust_level = "trusted"\n', encoding="utf-8")
        (src / "p.config.toml").write_text('model_provider = "p"\n', encoding="utf-8")
        (src / "AGENTS.md").write_text("个人约定", encoding="utf-8")
        (src / "memories").mkdir()
        home = agents.isolated_codex_home(src, dst)
        self.assertEqual(sorted(x.name for x in home.iterdir()), ["config.toml", "p.config.toml"])
        conf = (home / "config.toml").read_text(encoding="utf-8")
        self.assertIn("[model_providers.p.auth]", conf)
        for leaked in ("mcp_servers", "max_context_tokens", "skills.config", "/s/SKILL.md", "projects", "model = "):
            self.assertNotIn(leaked, conf)

    def test_isolated_codex_home_hides_personal_skills(self):
        # ~/.agents/skills 不在 CODEX_HOME 里，隔离不掉；0.164 的 skills.include_instructions=false
        # 让技能清单不进上下文，技能搜索也搜不到（2026-10-23 实测，#15）
        src = pathlib.Path(tempfile.mkdtemp())
        (src / "config.toml").write_text('[model_providers.p]\nbase_url = "https://p"\n', encoding="utf-8")
        conf = (agents.isolated_codex_home(src, src / "home") / "config.toml").read_text(encoding="utf-8")
        self.assertRegex(conf, r"(?m)^\[skills\]\ninclude_instructions = false$")


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
