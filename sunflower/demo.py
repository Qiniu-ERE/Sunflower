"""演示工作区：模板在仓库里（demo/todo-app），Codex 只改一次性副本。

    python3 -m sunflower.demo reset [--profile dev-single-mac]   # 每次彩排/演示前跑一次

副本是独立 git 仓（每条语音任务一个 `voice:` 提交，撤销 = revert），比赛仓本身不被改动。
"""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
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


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sunflower.demo")
    ap.add_argument("cmd", choices=["reset"])
    ap.add_argument("--profile", default="dev-single-mac")
    a = ap.parse_args(argv)
    prof = config.load_profile(a.profile)
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
