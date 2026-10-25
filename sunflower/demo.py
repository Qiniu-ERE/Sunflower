"""演示工作区：模板在仓库里（demo/todo-app），Codex 只改一次性副本。

    python3 -m sunflower.demo reset [--profile dev-single-mac]   # 每次彩排/演示前跑一次
    python3 -m sunflower.demo preview                            # 开讲前在一个终端里开着，不用管它

副本是独立 git 仓（每条语音任务一个 `voice:` 提交，撤销 = revert），比赛仓本身不被改动。
"""
import argparse
import json
import os
import pathlib
import signal
import shutil
import subprocess
import sys
import time
import urllib.request

from . import config

TEMPLATE = config.ROOT / "demo" / "todo-app"


def reset(workspace):
    ws = pathlib.Path(os.path.expanduser(workspace)).resolve()
    if ws == config.ROOT or config.ROOT in ws.parents:
        raise SystemExit(f"拒绝：工作区 {ws} 不能在比赛仓内部")
    if ws.exists():
        shutil.rmtree(ws)
    shutil.copytree(TEMPLATE, ws, ignore=shutil.ignore_patterns("__pycache__", "todos.json"))
    git = ["git", "-C", str(ws)]
    subprocess.run(git + ["init", "-q"], check=True)
    subprocess.run(git + ["add", "-A"], check=True)
    subprocess.run(git + ["-c", "user.name=sunflower", "-c", "user.email=sunflower@localhost",
                          "commit", "-q", "-m", "init demo workspace"], check=True)
    return ws


class Preview:
    """演示预览：工作区每换一个提交，就停掉旧网页服务、用当前代码重新跑 `python3 todo.py serve`。

    任务一提交，面板上 Codex 给的 127.0.0.1 链接就能点开；撤销 / 重置后代码里没有网页入口
    （初始版把 serve 当普通参数，打印完就退），服务跟着停，不会留下撤销前的旧页面。
    让 Codex 自己「运行服务」不行：serve 不退出，任务就结束不了，撤销后旧进程也还在。
    """

    def __init__(self, workspace, argv=None, settle=2.0, log=None):
        self.ws = pathlib.Path(os.path.expanduser(workspace))
        self.log = log  # 服务的输出（端口被占之类的报错在这里）；None = 丢弃
        self.argv = argv or [sys.executable, "todo.py", "serve"]
        self.settle = settle  # 启动后这么久还活着，才算有网页
        self.proc = None
        self.head = None

    def _head(self):
        if not self.ws.is_dir():
            return None
        r = subprocess.run(["git", "-C", str(self.ws), "rev-parse", "HEAD"], capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else None

    def stop(self):
        proc, self.proc = self.proc, None
        if proc is None or proc.poll() is not None:
            return
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(3)
        except ProcessLookupError:
            pass
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()

    def _start(self):
        out = open(self.log, "a", encoding="utf-8") if self.log else subprocess.DEVNULL
        try:
            self.proc = subprocess.Popen(self.argv, cwd=self.ws, stdin=subprocess.DEVNULL, stdout=out,
                                         stderr=subprocess.STDOUT, start_new_session=True)
        finally:
            if self.log:
                out.close()
        try:
            self.proc.wait(self.settle)  # 这么快就退了：这版代码没有网页（或端口被占，看 preview.log）
        except subprocess.TimeoutExpired:
            return True
        self.proc = None
        return False

    def tick(self):
        """看一眼当前提交：没变返回 None；变了就停旧服务、按新代码重启，返回一句状态。"""
        head = self._head()
        if head == self.head:
            return None
        self.head = head
        self.stop()
        if head is None:
            return "工作区不在（重置中），预览已停"
        if self._start():
            return f"{head[:7]}：网页已启动（pid {self.proc.pid}）"
        return f"{head[:7]}：这版代码没有网页，预览已停"


def preview(workspace, interval=1.0):
    log = config.HOME / "logs" / "preview.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    pv = Preview(workspace, log=log)
    print(f"演示预览：盯着 {pv.ws}，每次提交后重启网页服务（Ctrl-C 结束；服务输出在 {log}）", flush=True)
    try:
        while True:
            msg = pv.tick()
            if msg:
                print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
    finally:
        pv.stop()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sunflower.demo")
    ap.add_argument("cmd", choices=["reset", "preview"])
    ap.add_argument("--profile", default="dev-single-mac")
    a = ap.parse_args(argv)
    prof = config.load_profile(a.profile)
    if a.cmd == "preview":
        return preview(prof["host"]["workspace"])
    ws = reset(prof["host"]["workspace"])
    print(f"演示工作区已重置：{ws}")
    # 让正在运行的主机忘掉上一轮 Codex 会话（主机没开也没关系）
    token = config.load_env().get("SUNFLOWER_TOKEN", "")
    url = f"http://127.0.0.1:{prof['host'].get('port', 8787)}/api/new-session"
    try:
        req = urllib.request.Request(url, data=b"{}", method="POST", headers={
            "Authorization": "Bearer " + token, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as r:
            print("主机：", json.loads(r.read()).get("say"))
    except OSError:
        print("主机未运行（启动后即为新会话）")


if __name__ == "__main__":
    main()
