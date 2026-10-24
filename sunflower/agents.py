"""Headless code-agent adapter.

Both Codex (`codex exec --json` / `exec resume`) and Claude Code (`claude -p
--output-format stream-json` / `--resume`) expose a structured event stream plus
session resume, so the voice host never scrapes a TUI. v1 wires Codex.
"""
import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import threading
import time

VOICE_PREFIX = ("以下需求来自语音识别，可能有同音错字（尤其是英文文件名、函数名），"
                "请结合仓库实际内容理解并模糊匹配。提问、检查类需求只报告结论，不修改文件。\n需求：")
READ_ONLY_NOTE = "\n\n（这是只问不改的请求：可以跑测试，只报告发现，不要修改文件；即使改了也不会被提交。）"
# 只问不改（#15）：出现查看 / 提问类词、且没有任何动手类词，才走只读沙箱；拿不准时按可写处理
_READ_RE = re.compile(r"检查|看看|看一下|看下|有没有|是不是|是否|对不对|为什么|怎么回事|什么|哪里|哪些|哪个|"
                      r"解释|讲讲|说说|分析|评估|审查|review|explain", re.I)
_WRITE_RE = re.compile(r"修|改|加|增|删|去掉|写|实现|重构|提交|补|优化|换成|替换|更新|升级|新建|创建|生成|撤销|回滚|"
                       r"调整|处理|搞定|弄好|解决|跑|运行|fix|add|implement|refactor|run", re.I)
VOICE_SUFFIX = ("\n\n完成后在回复最后单独一行写「语音摘要：」加不超过 30 个字的中文总结"
                "（改了什么、验证结果如何），不要包含文件路径和代码。")
# 叫停（#35）：平台 ASR 常把「停下」听成「听下」「挺下」，灵矽 LLM 再把它当新需求 dispatch。
# 整句只有这些（去掉语气词和标点）才算，带了别的内容就是正常需求
_STOP_RE = re.compile(r"[停听挺亭婷庭](?:下|止|一下|下来)?|别做了|别弄了|不要做了|取消|算了")
_FILLER_RE = re.compile(r"[\s，。！？、,.!?~…嗯啊呃哦唉诶哎吧呀]")
_RECONNECT_RE = re.compile(r"Reconnecting\.\.\.\s*(\d+/\d+)")
_SUMMARY_RE = re.compile(r"语音摘要[:：]\s*(.+)")

def stop_intent(text):
    return bool(_STOP_RE.fullmatch(_FILLER_RE.sub("", text or "")))


def read_only_intent(text):
    return bool(_READ_RE.search(text or "")) and not _WRITE_RE.search(text or "")


def with_sandbox(argv, mode):
    """把 argv 里的 `-s <模式>` 换成 mode；没有就追加。"""
    argv = list(argv)
    if "-s" in argv:
        argv[argv.index("-s") + 1] = mode
    else:
        argv += ["-s", mode]
    return argv


def isolated_codex_home(src, dst):
    """给主机用的 CODEX_HOME：只放渠道配置（[model_providers.*] 和各渠道的 <名>.config.toml）。

    使用者的 ~/.codex 里还有个人 AGENTS.md、记忆、MCP 服务；演示时 Codex 会去读，
    既暴露在投屏上又让行为随机器而变（#15）。每次启动重建，渠道改动跟着 ~/.codex 走。
    ~/.agents/skills 下的个人技能不在 CODEX_HOME 里、隔离不掉，改用 skills.include_instructions=false
    不让技能清单进上下文（0.164 实测：清单为空，技能搜索也搜不到）。"""
    src, dst = pathlib.Path(src).expanduser(), pathlib.Path(dst)
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True, mode=0o700)
    keep, out = False, []
    for line in (src / "config.toml").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*\[+\s*([^\]]+?)\s*\]+\s*$", line)
        if m:
            keep = m.group(1).startswith("model_providers.")
        if keep:
            out.append(line)
    out = ["[skills]", "include_instructions = false", ""] + out
    _write_private(dst / "config.toml", "\n".join(out) + "\n")
    for f in src.glob("*.config.toml"):
        _write_private(dst / f.name, f.read_text(encoding="utf-8"))
    return dst


def _write_private(path, text):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)


def codex_argv(channel="qiniu-gpt", extra=()):
    """`codex exec` on one model channel: a Codex profile plus that channel's overrides."""
    return ["codex", "exec", "-s", "danger-full-access", "-c", 'approval_policy="never"',
            "--profile", channel, *extra, "--skip-git-repo-check"]


CODEX_BASE = codex_argv()


def voice_summary(last_message, limit=60):
    """Pick the line the agent wrote for TTS; fall back to its first sentence."""
    text = last_message or ""
    m = _SUMMARY_RE.search(text)
    if m:
        s = m.group(1).strip()
    else:
        plain = re.sub(r"```.*?```", "", text, flags=re.S)
        plain = re.sub(r"[`*#>\[\]]", "", plain).strip()
        s = re.split(r"(?<=[。！？!?])|\n", plain, maxsplit=1)[0].strip() if plain else ""
    return (s[:limit] + "…") if len(s) > limit else (s or "任务完成")


def describe(ev):
    """Codex JSONL event -> (kind, text) for the panel, or None to skip."""
    t = ev.get("type")
    item = ev.get("item") or {}
    it = item.get("type")
    if t == "thread.started":
        return ("system", "会话已建立")
    if t == "error":
        msg = ev.get("message", "error")
        m = _RECONNECT_RE.match(msg)
        return ("warn", f"上游连接中断，自动重试 {m.group(1)}" if m else msg)
    if t == "item.started" and it == "command_execution":
        return ("cmd", _short_cmd(item.get("command", "")))
    if t == "item.completed" and it == "command_execution":
        code = item.get("exit_code")
        return ("cmd_ok" if code == 0 else "cmd_fail", f"exit {code} · {_short_cmd(item.get('command', ''))}")
    if t == "item.completed" and it == "file_change":
        return ("file", ", ".join(f"{c.get('kind', '?')} {pathlib.Path(c.get('path', '')).name}"
                                  for c in item.get("changes") or []))
    if t == "item.completed" and it == "agent_message":
        return ("msg", _clean_text(item.get("text", "")))
    if t == "item.completed" and it == "reasoning":
        return ("think", _clean_text(item.get("text", ""))[:200])
    if t == "turn.completed":
        u = ev.get("usage") or {}
        return ("system", f"本轮完成 · 输出 {u.get('output_tokens', '?')} tokens")
    return None


_HOME = os.path.expanduser("~")


def _clean_text(text):
    # 屏幕会被投影/截图：markdown 链接只留文字，家目录折叠成 ~
    return re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text).replace(_HOME, "~")


def _short_cmd(cmd):
    m = re.match(r"^/bin/(?:ba|z)sh -lc (['\"])(.*)\1$", cmd, re.S)
    cmd = (m.group(2) if m else cmd).replace(_HOME, "~")
    return cmd if len(cmd) <= 120 else cmd[:117] + "..."


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


class CodexRunner:
    """One task at a time, multi-turn via `exec resume <thread_id>`."""

    def __init__(self, workspace, emit, base_argv=None, run_dir=None, channel=None, env=None):
        self.workspace = pathlib.Path(os.path.expanduser(workspace))
        self.emit = emit
        self.base_argv = list(base_argv or CODEX_BASE)
        self.channel = channel
        self.env = env  # None = 继承主机环境；主机传入隔离的 CODEX_HOME
        self.read_only = False
        self.run_dir = pathlib.Path(run_dir or self.workspace / ".sunflower")
        self.lock = threading.Lock()
        self.proc = None
        self.task = None
        self.thread_id = None
        self.started = None
        self.last_event = None
        self.files = []
        self.cancelled = False

    # -- queries ---------------------------------------------------------
    def busy(self):
        return self.proc is not None and self.proc.poll() is None

    def status(self):
        if not self.busy():
            return {"state": "idle", "say": "现在空闲，可以布置新任务"}
        secs = int(time.time() - self.started)
        last = self.last_event[1] if self.last_event else "刚开始"
        return {"state": "running", "task": self.task, "elapsed": secs,
                "say": f"正在做：{self.task[:20]}，已经{secs}秒，最近一步：{last[:30]}"}

    # -- commands --------------------------------------------------------
    def dispatch(self, text):
        if stop_intent(text):
            self.emit("log", {"kind": "system", "text": f"「{text}」按叫停处理"})
            return self.cancel()
        with self.lock:
            if self.busy():
                return {"ok": False, "say": f"上一个任务还在进行：{self.task[:20]}，可以说取消"}
            self.workspace.mkdir(parents=True, exist_ok=True)
            self.run_dir.mkdir(parents=True, exist_ok=True)
            last_file = self.run_dir / "last.txt"
            last_file.unlink(missing_ok=True)
            self.read_only = read_only_intent(text)
            prompt = VOICE_PREFIX + text + (READ_ONLY_NOTE if self.read_only else "") + VOICE_SUFFIX
            base = self.base_for(text)
            argv = list(base) + ["-C", str(self.workspace)]
            if self.thread_id:
                argv += ["resume", self.thread_id]
            argv += ["--json", "-o", str(last_file), prompt]
            self.task, self.started, self.files, self.cancelled = text, time.time(), [], False
            self.last_event = None
            # 行缓冲：Codex 卡住时 events.jsonl 要能看到它停在哪一步，不能攒到进程退出才落盘
            log = open(self.run_dir / "events.jsonl", "a", encoding="utf-8", buffering=1)
            # stdin 显式关掉：codex exec 见到非终端 stdin 会尝试读取附加输入
            self.proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=log,
                                         text=True, start_new_session=True, cwd=self.workspace, env=self.env)
            self.emit("state", {"state": "running", "task": text, "started": self.started,
                                "resume": bool(self.thread_id), "read_only": self.read_only})
            threading.Thread(target=self._pump, args=(self.proc, last_file, log), daemon=True).start()
            return {"ok": True, "say": "收到，已交给 Codex 开始处理"}

    def cancel(self):
        with self.lock:
            if not self.busy():
                return {"ok": False, "say": "当前没有在执行的任务"}
            self.cancelled = True
            try:
                os.killpg(self.proc.pid, signal.SIGINT)
            except ProcessLookupError:
                pass
            return {"ok": True, "say": "已让 Codex 停下"}

    def new_session(self):
        with self.lock:
            if self.busy():
                return {"ok": False, "say": "任务还在进行，先说取消"}
            self.thread_id, self.task = None, None
            self.emit("state", {"state": "idle", "reset": True})
            self.emit("log", {"kind": "system", "text": "已开启新会话（工作区已重置）"})
            return {"ok": True, "say": "已开启新会话"}

    def set_agent(self, argv, channel):
        """Switch model channel between tasks; the next task starts a new session on it."""
        with self.lock:
            if self.busy():
                return {"ok": False, "say": "任务还在进行，先说取消再切换渠道"}
            self.base_argv, self.channel, self.thread_id = list(argv), channel, None
            self.emit("state", {"state": "idle", "channel": channel})
            self.emit("log", {"kind": "system", "text": f"已切换渠道：{channel}"})
            return {"ok": True, "say": f"已切换到 {channel} 渠道"}

    def undo(self):
        with self.lock:
            if self.busy():
                return {"ok": False, "say": "任务还在进行，先说取消再撤销"}
            head = _git(self.workspace, "log", "-1", "--format=%s")
            if head.returncode or not head.stdout.startswith("voice: "):
                return {"ok": False, "say": "没有可撤销的语音任务提交"}
            r = _git(self.workspace, "revert", "--no-edit", "HEAD")
            if r.returncode:
                return {"ok": False, "say": "撤销失败，详情在屏幕上；可以说「检查一下工作区」"}
            self.emit("log", {"kind": "system", "text": f"已撤销：{head.stdout.strip()}"})
            self.emit("diff", self.diffstat())
            return {"ok": True, "say": "已撤销上一次改动"}

    # -- internals -------------------------------------------------------
    def diffstat(self):
        r = _git(self.workspace, "show", "--stat", "--format=%h %s", "HEAD")
        return {"stat": r.stdout.strip() if r.returncode == 0 else ""}

    def _pump(self, proc, last_file, log):
        for line in proc.stdout:
            log.write(line)
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get("type") == "thread.started":
                self.thread_id = ev.get("thread_id")
            d = describe(ev)
            if d:
                self.last_event = d
                if d[0] == "file":
                    self.files.append(d[1])
                self.emit("log", {"kind": d[0], "text": d[1]})
        code = proc.wait()
        proc.stdout.close()
        log.close()
        last = last_file.read_text(encoding="utf-8") if last_file.exists() else ""
        if self.cancelled:
            say = "任务已取消"
        elif code != 0:
            say = f"任务失败，退出码{code}，详情在屏幕上；可以说「再试一次」"
        else:
            say = voice_summary(last)
        if self.read_only:
            n = self._stash_check_edits()
            if n:
                say += f"；检查时改动的{n}个文件已收进 git stash，未提交"
        commit = self._commit() if code == 0 and not self.cancelled and not self.read_only else None
        self.emit("state", {"state": "idle", "task": self.task, "exit": code,
                            "elapsed": int(time.time() - self.started), "commit": commit})
        if last:
            self.emit("result", {"text": last})
        if commit:
            self.emit("diff", self.diffstat())
        self.emit("announce", {"text": say})

    def base_for(self, text):
        # 只读沙箱连临时文件都写不了，跑测试会全是环境错误（codex 0.164 实测）→ 用 workspace-write，
        # 「不改」由主机兜底：检查任务结束后工作区有改动就收进 stash（_stash_check_edits）
        return with_sandbox(self.base_argv, "workspace-write") if read_only_intent(text) else self.base_argv

    def _stash_check_edits(self):
        st = _git(self.workspace, "status", "--porcelain", "--", ".", ":!.sunflower")
        files = [l for l in st.stdout.splitlines() if l.strip()] if st.returncode == 0 else []
        if not files:
            return 0
        r = _git(self.workspace, "stash", "push", "-u", "-m", "voice-check: " + (self.task or "")[:60],
                 "--", ".", ":!.sunflower")
        if r.returncode:
            self.emit("log", {"kind": "error", "text": "检查任务改了文件，收进 stash 失败：" + r.stderr.strip()[:120]})
            return 0
        self.emit("log", {"kind": "system", "text": f"检查任务改动了 {len(files)} 个文件，已收进 git stash（git stash pop 可取回）"})
        return len(files)

    def _commit(self):
        if _git(self.workspace, "rev-parse", "--git-dir").returncode:
            return None
        _git(self.workspace, "add", "-A", "--", ".", ":!.sunflower")
        if _git(self.workspace, "diff", "--cached", "--quiet").returncode == 0:
            return None
        msg = "voice: " + (self.task or "")[:60]
        if _git(self.workspace, "commit", "-q", "-m", msg).returncode:
            return None
        return _git(self.workspace, "rev-parse", "--short", "HEAD").stdout.strip()
