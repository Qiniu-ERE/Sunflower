"""Headless code-agent adapter.

Both Codex (`codex exec --json` / `exec resume`) and Claude Code (`claude -p
--output-format stream-json` / `--resume`) expose a structured event stream plus
session resume, so the voice host never scrapes a TUI. v1 wires Codex.
"""
import json
import os
import pathlib
import re
import signal
import subprocess
import threading
import time

VOICE_PREFIX = ("以下需求来自语音识别，可能有同音错字（尤其是英文文件名、函数名），"
                "请结合仓库实际内容理解并模糊匹配。\n需求：")
VOICE_SUFFIX = ("\n\n完成后在回复最后单独一行写「语音摘要：」加不超过 30 个字的中文总结"
                "（改了什么、验证结果如何），不要包含文件路径和代码。")
_RECONNECT_RE = re.compile(r"Reconnecting\.\.\.\s*(\d+/\d+)")
_SUMMARY_RE = re.compile(r"语音摘要[:：]\s*(.+)")

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

    def __init__(self, workspace, emit, base_argv=None, run_dir=None, channel=None):
        self.workspace = pathlib.Path(os.path.expanduser(workspace))
        self.emit = emit
        self.base_argv = list(base_argv or CODEX_BASE)
        self.channel = channel
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
        with self.lock:
            if self.busy():
                return {"ok": False, "say": f"上一个任务还在进行：{self.task[:20]}，可以说取消"}
            self.workspace.mkdir(parents=True, exist_ok=True)
            self.run_dir.mkdir(parents=True, exist_ok=True)
            last_file = self.run_dir / "last.txt"
            last_file.unlink(missing_ok=True)
            prompt = VOICE_PREFIX + text + VOICE_SUFFIX
            argv = list(self.base_argv) + ["-C", str(self.workspace)]
            if self.thread_id:
                argv += ["resume", self.thread_id]
            argv += ["--json", "-o", str(last_file), prompt]
            self.task, self.started, self.files, self.cancelled = text, time.time(), [], False
            self.last_event = None
            log = open(self.run_dir / "events.jsonl", "a", encoding="utf-8")
            # stdin 显式关掉：codex exec 见到非终端 stdin 会尝试读取附加输入
            self.proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=log,
                                         text=True, start_new_session=True, cwd=self.workspace)
            self.emit("state", {"state": "running", "task": text, "started": self.started,
                                "resume": bool(self.thread_id)})
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
            say = f"任务失败，退出码{code}，详情在屏幕上；可以说「再试一次」或「撤销」"
        else:
            say = voice_summary(last)
        commit = self._commit() if code == 0 and not self.cancelled else None
        self.emit("state", {"state": "idle", "task": self.task, "exit": code,
                            "elapsed": int(time.time() - self.started), "commit": commit})
        if last:
            self.emit("result", {"text": last})
        if commit:
            self.emit("diff", self.diffstat())
        self.emit("announce", {"text": say})

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
