"""Host: one process, one port, three consumers.

    device  --POST /api/*-->  host  --codex exec-->  agent
    device  <--SSE /events--  host  --SSE /events-->  panel (any browser: big screen / kiosk / AirPlay mirror)

    python3 -m sunflower.host --profile dev-single-mac
"""
import argparse
import collections
import hmac
import json
import os
import pathlib
import queue
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import agents, config

WEB = pathlib.Path(__file__).resolve().parent / "web"
HEARTBEAT_S = 30


class Bus:
    """Fan-out of named events with a replay buffer so a reloaded panel catches up."""

    def __init__(self, history=300):
        self.lock = threading.Lock()
        self.subs = []
        self.history = collections.deque(maxlen=history)
        self.seq = 0

    def emit(self, event, data):
        with self.lock:
            self.seq += 1
            msg = (self.seq, event, dict(data, ts=time.time()))
            self.history.append(msg)
            for q in list(self.subs):
                q.put(msg)

    def subscribe(self, replay=True):
        q = queue.Queue()
        with self.lock:
            if replay:
                for m in self.history:
                    q.put(m)
            self.subs.append(q)
        return q

    def unsubscribe(self, q):
        with self.lock:
            if q in self.subs:
                self.subs.remove(q)


def channel_env_key(name, codex_home):
    """渠道的 provider 若用 env_key 取密钥，返回变量名；用 auth 命令（钥匙串）或查不到时返回 None。
    只认 Codex 配置里这两行，不引 TOML 库（3.9 无 tomllib）。"""
    home = pathlib.Path(codex_home)
    prof = home / f"{name}.config.toml"
    m = re.search(r'^model_provider\s*=\s*"([^"]+)"', prof.read_text(encoding="utf-8"), re.M) if prof.exists() else None
    if not m:
        return None
    for f in (prof, home / "config.toml"):
        if not f.exists():
            continue
        sec = re.search(r'^\[model_providers\.%s\]\s*$(.*?)(?=^\[)' % re.escape(m.group(1)),
                        f.read_text(encoding="utf-8") + "\n[", re.M | re.S)
        if sec:
            k = re.search(r'^env_key\s*=\s*"([^"]+)"', sec.group(1), re.M)
            return k.group(1) if k else None
    return None


def resolve_channel(hcfg, name, codex_home=None, environ=None):
    """Channel name -> codex argv. Known if listed in the profile's codex_channels or if a
    Codex profile file of that name exists (then it gets no extra overrides)."""
    chans = hcfg.get("codex_channels") or {}
    env = os.environ if environ is None else environ
    home = pathlib.Path(codex_home or env.get("CODEX_HOME") or "~/.codex").expanduser()
    if not name or (name not in chans and not (home / f"{name}.config.toml").exists()):
        raise ValueError(f"未知渠道「{name}」：profile 的 codex_channels 里没有，{home}/{name}.config.toml 也不存在")
    key = channel_env_key(name, home)
    if key and not env.get(key):
        raise ValueError(f"渠道「{name}」从环境变量 {key} 取密钥，本进程环境里没有（launchd 服务不继承 shell 变量）："
                         f"先 security add-generic-password -a $USER -s sunflower-{key} -w，"
                         f"再 python3 -m sunflower.service install --keychain-env {key}=sunflower-{key}")
    return agents.codex_argv(name, chans.get(name, []))


def make_handler(bus, runner, token, resolve=None):
    commit, pid, started = config.code_commit(), os.getpid(), time.time()
    device = {}  # 最近一次连上 /events 的设备所报告的代码提交

    class H(BaseHTTPRequestHandler):
        server_version = "sunflower/0.1"

        def log_message(self, fmt, *args):  # keep stdout for our own log lines
            pass

        def _authed(self):
            got = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            if not got:
                got = (parse_qs(urlparse(self.path).query).get("t") or [""])[0]
            return bool(token) and hmac.compare_digest(got, token)

        def _loopback(self):
            return self.client_address[0] in ("127.0.0.1", "::1")

        def _json(self, code, obj):
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/health":
                return self._json(200, {"ok": True, "busy": runner.busy(), "channel": runner.channel,
                                        "commit": commit, "pid": pid, "started": int(started),
                                        "device": dict(device) or None})
            if path in ("/", "/panel"):
                body = (WEB / "panel.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                return self.wfile.write(body)
            if path == "/events":
                # read-only stream: loopback (the panel window on this machine) needs no token
                if not (self._loopback() or self._authed()):
                    return self._json(401, {"error": "token required"})
                if self.headers.get("X-Sunflower-Commit"):
                    device.update(commit=self.headers["X-Sunflower-Commit"][:40], seen=time.time())
                return self._sse(replay=parse_qs(urlparse(self.path).query).get("replay", ["1"])[0] == "1")
            self._json(404, {"error": "not found"})

        def do_POST(self):
            if not self._authed():
                return self._json(401, {"error": "token required"})
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return self._json(400, {"error": "bad json"})
            path = urlparse(self.path).path
            if path == "/api/dispatch":
                text = (body.get("text") or "").strip()
                if not text:
                    return self._json(400, {"ok": False, "say": "没听清需求，请再说一遍"})
                bus.emit("log", {"kind": "user", "text": text})
                return self._json(200, runner.dispatch(text))
            if path == "/api/status":
                return self._json(200, runner.status())
            if path == "/api/cancel":
                return self._json(200, runner.cancel())
            if path == "/api/undo":
                return self._json(200, runner.undo())
            if path == "/api/new-session":
                return self._json(200, runner.new_session())
            if path == "/api/channel":
                if resolve is None:
                    return self._json(400, {"ok": False, "say": "当前 profile 固定了 agent_argv，不能切换渠道"})
                name = (body.get("name") or "").strip()
                try:
                    argv = resolve(name)
                except ValueError as e:
                    return self._json(400, {"ok": False, "say": str(e)})
                res = runner.set_agent(argv, name)
                return self._json(200 if res["ok"] else 409, res)
            if path == "/api/voice":
                # device mirrors what it heard / is saying so the screen shows the conversation
                bus.emit("voice", {"role": body.get("role", "?"), "text": body.get("text", "")})
                return self._json(200, {"ok": True})
            self._json(404, {"error": "not found"})

        def _sse(self, replay):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            q = bus.subscribe(replay=replay)
            try:
                while True:
                    try:
                        seq, event, data = q.get(timeout=HEARTBEAT_S)
                        chunk = f"id: {seq}\nevent: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                    except queue.Empty:
                        chunk = ": heartbeat\n\n"
                    self.wfile.write(chunk.encode())
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                bus.unsubscribe(q)

    return H


class QuietServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        # clients (panel tabs, screenshot tools, the device) dropping a connection is routine
        import sys
        if isinstance(sys.exc_info()[1], (ConnectionResetError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sunflower.host")
    ap.add_argument("--profile", default="dev-single-mac")
    ap.add_argument("--channel", help="Codex 渠道（~/.codex/<名>.config.toml），覆盖 SUNFLOWER_CODEX_CHANNEL 与 profile")
    a = ap.parse_args(argv)
    prof = config.load_profile(a.profile)
    hcfg = prof["host"]
    token = config.load_env().get("SUNFLOWER_TOKEN")
    if not token:
        raise SystemExit("SUNFLOWER_TOKEN 未配置（.env）")
    bus = Bus()

    def emit(event, data):
        bus.emit(event, data)
        if event in ("state", "announce"):
            print(f"[{time.strftime('%H:%M:%S')}] {event} {json.dumps(data, ensure_ascii=False)}", flush=True)

    if hcfg.get("agent_argv"):  # pinned argv (tests, benchmarks): no channel switching
        base, channel, resolve = hcfg["agent_argv"], None, None
    else:
        channel = (a.channel or os.environ.get("SUNFLOWER_CODEX_CHANNEL")
                   or hcfg.get("codex_channel") or "qiniu-gpt")
        resolve = lambda name: resolve_channel(hcfg, name)  # noqa: E731
        base = resolve(channel)
    runner = agents.CodexRunner(hcfg["workspace"], emit, base_argv=base,
                                run_dir=config.HOME / "run", channel=channel)
    srv = QuietServer((hcfg.get("bind", "127.0.0.1"), int(hcfg.get("port", 8787))),
                      make_handler(bus, runner, token, resolve))
    srv.daemon_threads = True
    print(f"sunflower host on http://{srv.server_address[0]}:{srv.server_address[1]}  "
          f"workspace={runner.workspace}  channel={channel or '(pinned argv)'}  "
          f"panel=/panel?t=<SUNFLOWER_TOKEN>", flush=True)
    emit("state", {"state": "idle", "channel": channel})
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
