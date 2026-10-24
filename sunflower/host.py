"""Host: one process, one port, three consumers.

    device  --POST /api/*-->  host  --codex exec-->  agent
    device  <--SSE /events--  host  --SSE /events-->  panel (any browser: big screen / kiosk / AirPlay mirror)
    device  <--SSE key------  host  <--POST /api/key--  panel (说话按键落在屏幕上的窗口，#40)

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
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import agents, config, tryout

WEB = pathlib.Path(__file__).resolve().parent / "web"
HEARTBEAT_S = 30
PANEL_KEYS = {"talk", "mute", "1", "2", "3", "4", "5"}  # 面板按键（#40）：与设备终端按键同一组动作
MIC_STATES = {"recording", "recognizing", "idle"}


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


def make_handler(bus, runner, token, resolve=None, tryout_log=None):
    commit, pid, started = config.code_commit(), os.getpid(), time.time()
    tryout_log = pathlib.Path(tryout_log or config.HOME / "tryout.jsonl")
    turns = {}  # 试音轮次：编号 → (条件, 第几句)；设备回报一次即销账
    device = {}  # 最近一次连上 /events 的桌面设备所报告的代码提交
    desks = []  # 正连着 /events 的桌面设备（TG 入口不算）；面板按键只发给它们

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

        def _local_screen(self):
            """本机浏览器里的面板：来源是回环、Host 是本机名（挡 DNS 重绑定）、Origin 缺省或同源（挡别的网页）。"""
            host = self.headers.get("Host", "")
            name = host.rsplit(":", 1)[0] if not host.endswith("]") else host
            origin = self.headers.get("Origin")
            return self._loopback() and name in ("127.0.0.1", "localhost", "[::1]") and \
                origin in (None, "http://" + host)

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
            if path == "/api/tryout/phrases":  # 公开的固定句子，不含密钥
                return self._json(200, {"phrases": [{"text": t, "expect": e} for t, e in tryout.PHRASES],
                                        "conds": [{"id": c, "name": n, "hint": h} for c, n, h in tryout.CONDS]})
            if path in ("/", "/panel", "/tryout"):
                body = (WEB / ("tryout.html" if path == "/tryout" else "panel.html")).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                return self.wfile.write(body)
            if path == "/events":
                # read-only stream: loopback (the panel window on this machine) needs no token
                if not (self._loopback() or self._authed()):
                    return self._json(401, {"error": "token required"})
                # 没带角色头的是 #40 之前的设备进程；TG 入口带 role=tg，不覆盖设备记录
                desk = bool(self.headers.get("X-Sunflower-Commit")) and \
                    self.headers.get("X-Sunflower-Role", "device") == "device"
                if desk:
                    device.update(commit=self.headers["X-Sunflower-Commit"][:40], seen=time.time(),
                                  reload=self.headers.get("X-Sunflower-Reload") == "1")
                return self._sse(replay=parse_qs(urlparse(self.path).query).get("replay", ["1"])[0] == "1",
                                 desk=desk)
            self._json(404, {"error": "not found"})

        def do_POST(self):
            # 按键是坐在屏幕前的人按的：本机面板不用令牌，和只读事件流一致；其余写接口仍要令牌
            if not (self._authed() or (urlparse(self.path).path == "/api/key" and self._local_screen())):
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
            if path == "/api/key":
                key = body.get("key")
                if key not in PANEL_KEYS:
                    return self._json(400, {"ok": False, "say": f"不认识的按键：{key}"})
                t = body.get("tryout")
                if t is not None and (key != "talk" or t.get("cond") not in {c[0] for c in tryout.CONDS}
                                      or t.get("idx") not in range(len(tryout.PHRASES))):
                    return self._json(400, {"ok": False, "say": f"试音参数不对：{t}"})
                if not desks:
                    return self._json(409, {"ok": False, "say": "桌面设备没在线：终端跑 python3 -m sunflower.service status 看「设备」一行"})
                ev = {"key": key}
                if t is not None:
                    ev["tryout"] = uuid.uuid4().hex[:8]
                    turns[ev["tryout"]] = (t["cond"], t["idx"])
                bus.emit("key", ev)
                return self._json(200, {"ok": True})
            if path == "/api/tryout":
                turn = turns.pop(body.get("id"), None)
                if turn is None:
                    return self._json(404, {"ok": False, "say": "没有这一轮试音"})
                row = tryout.score(*turn, body.get("hyp"), body.get("tool"), body.get("args"))
                tryout.append(tryout_log, row)
                bus.emit("tryout", row)
                return self._json(200, {"ok": True})
            if path == "/api/device":
                state, muted = body.get("state"), body.get("muted")
                if (state is not None and state not in MIC_STATES) or (muted is not None and not isinstance(muted, bool)):
                    return self._json(400, {"ok": False, "say": f"未知设备状态：{body}"})
                bus.emit("device", {k: v for k, v in (("state", state), ("muted", muted)) if v is not None})
                return self._json(200, {"ok": True})
            if path == "/api/voice":
                # device mirrors what it heard / is saying so the screen shows the conversation
                bus.emit("voice", {"role": body.get("role", "?"), "text": body.get("text", "")})
                return self._json(200, {"ok": True})
            self._json(404, {"error": "not found"})

        def _sse(self, replay, desk=False):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            q = bus.subscribe(replay=replay)
            if desk:
                desks.append(q)
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
                if q in desks:
                    desks.remove(q)

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

    env = home = None
    if hcfg.get("agent_argv"):  # pinned argv (tests, benchmarks): no channel switching
        base, channel, resolve = hcfg["agent_argv"], None, None
    else:
        if hcfg.get("isolate_codex_home", True):  # 不让演示读到使用者的个人 AGENTS.md / 记忆 / 技能（#15）
            home = agents.isolated_codex_home(os.environ.get("CODEX_HOME") or "~/.codex", config.HOME / "codex-home")
            env = dict(os.environ, CODEX_HOME=str(home))
        channel = (a.channel or os.environ.get("SUNFLOWER_CODEX_CHANNEL")
                   or hcfg.get("codex_channel") or "qiniu-gpt")
        resolve = lambda name: resolve_channel(hcfg, name, codex_home=home)  # noqa: E731
        base = resolve(channel)
    runner = agents.CodexRunner(hcfg["workspace"], emit, base_argv=base,
                                run_dir=config.HOME / "run", channel=channel, env=env)
    srv = QuietServer((hcfg.get("bind", "127.0.0.1"), int(hcfg.get("port", 8787))),
                      make_handler(bus, runner, token, resolve))
    srv.daemon_threads = True
    print(f"sunflower host on http://{srv.server_address[0]}:{srv.server_address[1]}  "
          f"workspace={runner.workspace}  channel={channel or '(pinned argv)'}  "
          f"panel=/panel  tryout=/tryout（本机不用令牌；别的机器加 ?t=<SUNFLOWER_TOKEN>）", flush=True)
    emit("state", {"state": "idle", "channel": channel})
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
