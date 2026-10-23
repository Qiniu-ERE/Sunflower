"""演示脚本计时：每个对照组起一个独立主机（生产同款：渠道 + 隔离 CODEX_HOME），按
docs/demo-script.md 的 1 → 2 → 3（撤销）→ 4 走 API，记录每步耗时、首步等待、输出 token 和对错。

    python3 scripts/bench_demo.py --channel icodeeasy --effort high medium --rounds 3

同一轮里各组并发跑（渠道拥堵对两边一样），轮与轮之间串行。渠道要的密钥按
`sunflower-<变量名>` 从钥匙串取，只进主机子进程环境，不打印、不落盘。#7 的推理强度对比就是这么跑的。
"""
import argparse
import glob
import json
import os
import pathlib
import re
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sunflower import demo, host, service  # noqa: E402

STEPS = ["检查一下代码有没有逻辑问题", "那就把它修好", "UNDO", "给待办清单加一个删除命令，按编号删除并补上测试"]
TOKEN = "bench-token"


class Arm:
    def __init__(self, work, port, channel, effort):
        self.work, self.port, self.ws = work, port, work / "ws"
        work.mkdir(parents=True, exist_ok=True)
        demo.reset(str(self.ws))
        extra = ["-c", f'model_reasoning_effort="{effort}"'] if effort else []
        prof = {"device": {}, "host": {"bind": "127.0.0.1", "port": port, "workspace": str(self.ws),
                                       "codex_channel": channel, "codex_channels": {channel: extra}}}
        (work / "profile.json").write_text(json.dumps(prof))
        env = dict(os.environ, SUNFLOWER_TOKEN=TOKEN, SUNFLOWER_HOME=str(work / "home"))
        key = host.channel_env_key(channel, pathlib.Path(os.environ.get("CODEX_HOME") or "~/.codex").expanduser())
        if key and not env.get(key):
            env[key] = service.keychain(f"sunflower-{key}")
        self.proc = subprocess.Popen([sys.executable, "-u", "-m", "sunflower.host", "--profile", str(work / "profile.json")],
                                     cwd=ROOT, env=env, stdout=open(work / "host.log", "w"), stderr=subprocess.STDOUT)
        self.events, self.cond = [], threading.Condition()
        for _ in range(50):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1).close()
                break
            except OSError:
                time.sleep(0.2)
        threading.Thread(target=self._listen, daemon=True).start()
        time.sleep(0.5)

    def _listen(self):
        cur = {}
        for raw in urllib.request.urlopen(f"http://127.0.0.1:{self.port}/events?replay=0&t={TOKEN}", timeout=3600):
            line = raw.decode().rstrip("\n")
            if line.startswith("event:"):
                cur["e"] = line[6:].strip()
            elif line.startswith("data:"):
                cur["d"] = json.loads(line[5:])
            elif not line and cur:
                with self.cond:
                    self.events.append(cur)
                    self.cond.notify_all()
                cur = {}

    def post(self, path, body=None):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=json.dumps(body or {}).encode(),
                                     method="POST", headers={"Authorization": "Bearer " + TOKEN,
                                                             "Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(req, timeout=10).read())

    def tests(self):
        p = subprocess.run([sys.executable, "-m", "unittest", "-q"], cwd=self.ws, capture_output=True, text=True)
        m = re.search(r"Ran (\d+) test", p.stderr)
        return p.returncode == 0, int(m.group(1)) if m else 0

    def step(self, text):
        if text == "UNDO":
            ok = self.post("/api/undo")["ok"]
            green, n = self.tests()
            return {"task": "撤销", "ok": ok, "green": green, "tests": n}
        start = len(self.events)
        assert self.post("/api/dispatch", {"text": text})["ok"]
        with self.cond:
            self.cond.wait_for(lambda: any(e["e"] == "announce" for e in self.events[start:]), timeout=1200)
        seg = self.events[start:]
        logs = [e["d"] for e in seg if e["e"] == "log"]
        run = next(e["d"]["ts"] for e in seg if e["e"] == "state" and e["d"].get("state") == "running")
        first = next((d["ts"] - run for d in logs if d.get("kind") in ("msg", "cmd")), None)
        idle = next(e["d"] for e in seg if e["e"] == "state" and "exit" in e["d"])
        green, n = self.tests()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=self.ws, capture_output=True, text=True).stdout
        return {"task": text, "elapsed": idle.get("elapsed"), "first": first and round(first),
                "out_tokens": sum(int(m.group(1)) for d in logs
                                  for m in [re.search(r"输出 (\d+) tokens", d.get("text", ""))] if m),
                "warn": sum(1 for d in logs if d.get("kind") == "warn"), "exit": idle.get("exit"),
                "commit": idle.get("commit"), "green": green, "tests": n, "dirty": bool(dirty.strip()),
                "announce": next((e["d"]["text"] for e in seg if e["e"] == "announce"), "")}

    def run(self):
        try:
            self.steps = [self.step(t) for t in STEPS]
        finally:
            self.proc.terminate()
        seen = set()
        for f in glob.glob(str(self.work / "home" / "codex-home" / "sessions" / "**" / "*.jsonl"), recursive=True):
            seen.update(re.findall(r'"(?:reasoning_)?effort":"(\w+)"', pathlib.Path(f).read_text(encoding="utf-8")))
        self.effort_seen = sorted(seen)


def correct(steps):
    """演示要的结果：检查不改代码且测试仍红；修复转绿；撤销后变红；新功能转绿。"""
    s1, s2, undo, s4 = steps
    return (s1["commit"] is None and not s1["dirty"] and not s1["green"] and s2["green"] and s2["commit"]
            and undo["ok"] and not undo["green"] and s4["green"] and s4["commit"])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="icodeeasy")
    ap.add_argument("--effort", nargs="*", default=[None], help="每个值一组；不给就按渠道配置")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--port", type=int, default=8788)
    ap.add_argument("--out", default=None, help="结果目录（默认临时目录）")
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out or tempfile.mkdtemp(prefix="sunflower-bench-"))
    name = lambda e: e or "渠道默认"  # noqa: E731
    results = {name(e): [] for e in a.effort}
    for r in range(1, a.rounds + 1):
        arms = {name(e): Arm(out / f"r{r}-{e}", a.port + i, a.channel, e) for i, e in enumerate(a.effort)}
        threads = [threading.Thread(target=arm.run) for arm in arms.values()]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        for name, arm in arms.items():
            results[name].append({"effort_seen": arm.effort_seen, "correct": bool(correct(arm.steps)), "steps": arm.steps})
        print(f"第 {r} 轮完成 {time.strftime('%H:%M')}", flush=True)
    (out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"\n渠道 {a.channel}，{a.rounds} 轮中位数（秒）；明细 {out / 'results.json'}")
    print("组 | 实际强度 | 演示正确 | 1 检查 | 2 修复 | 4 加功能 | 首步等待 | 输出 token")
    for name, runs in results.items():
        med = lambda i, k: statistics.median(run["steps"][i][k] or 0 for run in runs)  # noqa: E731
        seen = sorted({x for run in runs for x in run["effort_seen"]})
        print(f"{name} | {','.join(seen) or '?'} | {sum(run['correct'] for run in runs)}/{len(runs)} | "
              f"{med(0, 'elapsed')} | {med(1, 'elapsed')} | {med(3, 'elapsed')} | "
              f"{med(0, 'first')}/{med(1, 'first')}/{med(3, 'first')} | "
              f"{med(0, 'out_tokens')}/{med(1, 'out_tokens')}/{med(3, 'out_tokens')}")


if __name__ == "__main__":
    main()
