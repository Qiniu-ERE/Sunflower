"""Linx (灵矽) soft device: mic + speaker + push-to-talk, exposing code tools over device-side MCP.

    python3 -m sunflower.device --profile dev-single-mac        # 按空格/翻页笔说话
    python3 -m sunflower.device --profile dev-single-mac --text "给项目加个单元测试"

Only outbound connections: wss to Linx cloud, http to the host on the LAN.
Facts this relies on (measured 2026-10-22):
  * listen/detect + text   -> the platform treats text as the user's utterance
  * listen/detect + text_response -> TTS of exactly that text, even on a cold connection
  * tools/call must answer within ~15s (platform gives up at ~30s), so dispatch only enqueues
"""
import argparse
import asyncio
import json
import math
import os
import struct
import subprocess
import sys
import threading
import time
import urllib.request

import websockets

from . import config, linx_admin

WS_URL = "wss://xrobo-io.qiniuapi.com/v1/ws/"
FRAME_BYTES = 640  # 20 ms of 16 kHz s16le mono
HELLO = {"type": "hello", "version": 1, "features": {"mcp": True}, "transport": "websocket",
         "audio_params": {"format": "pcm", "sample_rate": 16000, "channels": 1, "bit_depth": 16,
                          "endianness": "little", "frame_duration": 20, "frame_size": 320,
                          "sample_format": "signed_int16", "play_buffer_duration": 1000}}

TOOLS = [
    {"name": "self.code.dispatch",
     "description": "把用户的编程需求交给编程代理执行（写代码、改代码、修 bug、跑测试、提交）。用户提出任何编程需求时调用。",
     "inputSchema": {"type": "object", "properties": {"text": {"type": "string", "description": "用户原话，完整保留"}},
                     "required": ["text"]}},
    {"name": "self.code.status", "description": "查询编程代理当前进度。用户问进度、好了没有时调用。",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "self.code.cancel", "description": "让编程代理停止当前任务。用户说停下、取消时调用。",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "self.code.undo", "description": "撤销上一次语音任务的代码改动。用户说撤销、回滚时调用。",
     "inputSchema": {"type": "object", "properties": {}}},
]
TOOL_ROUTES = {"self.code.dispatch": "/api/dispatch", "self.code.status": "/api/status",
               "self.code.cancel": "/api/cancel", "self.code.undo": "/api/undo"}


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


class Host:
    """Blocking HTTP client for the host API (called via asyncio.to_thread)."""

    def __init__(self, url, token):
        self.url, self.token = url.rstrip("/"), token

    def post(self, path, body=None, timeout=12):
        req = urllib.request.Request(self.url + path, data=json.dumps(body or {}).encode(), method="POST",
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer " + self.token})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())

    def events(self):
        """Yield (event, data) from the host SSE stream (no replay)."""
        req = urllib.request.Request(self.url + "/events?replay=0",
                                     headers={"Authorization": "Bearer " + self.token,
                                              "X-Sunflower-Commit": COMMIT or "",
                                              "X-Sunflower-Reload": "1" if AUTO_RELOAD else "0"})
        with urllib.request.urlopen(req, timeout=HEARTBEAT_TIMEOUT) as r:
            event = None
            for raw in r:
                line = raw.decode("utf-8").rstrip("\n")
                if line.startswith("event: "):
                    event = line[7:]
                elif line.startswith("data: ") and event:
                    yield event, json.loads(line[6:])
                elif not line:
                    event = None


COMMIT = config.code_commit()  # 报给主机，service status 据此发现设备在跑旧代码
# 只有从部署目录启动的设备才随部署换代；开发仓切分支时不该把半成品 exec 进来
AUTO_RELOAD = config.ROOT.resolve() == config.APP.resolve()
RELOAD_POLL_S = 5
_tty = []  # stdin_trigger 改了终端模式；exec 前要还原，否则新进程会把 cbreak 当成原始模式
HEARTBEAT_TIMEOUT = 75  # host heartbeats every 30s


def tone(freq, ms, volume=0.2, rate=16000):
    """A short sine beep as s16le PCM, with 5 ms ramps so it doesn't click."""
    n = rate * ms // 1000
    ramp = rate // 200
    return b"".join(struct.pack("<h", int(32767 * volume * min(1.0, i / ramp, (n - 1 - i) / ramp)
                                          * math.sin(2 * math.pi * freq * i / rate))) for i in range(n))


# 本地提示音：演示者不看终端也知道开始 / 结束录音了（不经过灵矽）
EARCON_START = tone(880, 90)
EARCON_STOP = tone(660, 90)


class Player:
    """Streams downlink PCM into the profile's audio_out command."""

    def __init__(self, argv):
        self.argv, self.proc = argv, None

    def write(self, pcm):
        if self.proc is None or self.proc.poll() is not None:
            self.proc = subprocess.Popen(self.argv, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL)
        try:
            self.proc.stdin.write(pcm)
            self.proc.stdin.flush()
        except (BrokenPipeError, ValueError):
            self.proc = None

    def close(self):
        """End of one TTS burst: EOF lets the player drain and exit; next burst spawns a new one."""
        proc, self.proc = self.proc, None
        if proc and proc.poll() is None:
            try:
                proc.stdin.close()
            except (BrokenPipeError, ValueError):
                pass


class Device:
    def __init__(self, prof, host):
        self.prof, self.dev, self.host = prof, prof["device"], host
        self.ws = None
        self.sid = None
        self.ready = None
        self.lock = asyncio.Lock()
        self.player = Player(self.dev["audio_out"])
        self.mic = None
        self.mic_task = None
        self.toggling = False
        self.earcons = self.dev.get("earcons", True)
        self.quick = dict(QUICK, **self.dev.get("quick", {}))
        self.muted = bool(self.dev.get("mute", False))
        self.loop = None
        self.speaking = asyncio.Event()
        self.announcing = set()  # platform echoes text_response back as stt; don't show it as the user
        # we own the session length: close after a quiet spell instead of letting the platform's idle
        # timeout fire (it speaks a farewell, and billing counts connected seconds)
        self.idle_close_s = float(self.dev.get("idle_close_s", 20))
        self.last_activity = 0.0
        self.pending_tools = 0
        self.typing = False  # 「t」文字输入进行中：exec 会吞掉半行字，剩下的击键还会被当快捷键

    # -- self reload (#27) -------------------------------------------------
    def idle(self):
        return (self.mic is None and not self.toggling and not self.typing and self.pending_tools == 0
                and not self.speaking.is_set()
                and not self.lock.locked() and (self.ws is None or self.ws.state.name != "OPEN"))

    async def reload_check(self, head=config.code_commit, execv=os.execv):
        """部署目录换了提交且设备空闲 → 原地 exec 新代码。pid 不变，终端给的麦克风授权也不变。"""
        new = await asyncio.to_thread(head)
        if not new or new == COMMIT or not self.idle():
            return False
        log(f"部署已更新 {(COMMIT or '?')[:7]} → {new[:7]}，设备空闲，切到新代码")
        import termios
        import tty
        for fd, mode in _tty:
            termios.tcsetattr(fd, termios.TCSADRAIN, mode)
        self.player.close()
        try:
            execv(sys.executable, [sys.executable, "-m", "sunflower.device", *sys.argv[1:]])
        except OSError:
            for fd, _ in _tty:  # 回到按键模式，旧代码照常可用
                tty.setcbreak(fd)
            raise
        return True

    async def reload_watch(self):
        global AUTO_RELOAD
        while True:
            await asyncio.sleep(RELOAD_POLL_S)
            try:
                await self.reload_check()
            except Exception as e:  # 失败一次就停：不刷屏，也不再向主机报「会自动换代」
                AUTO_RELOAD = False
                log(f"✘ 自动换代失败：{type(e).__name__}: {e}；本次运行不再自动换代，"
                    "Ctrl-C 后用 python3 -m sunflower.service device 重启")
                return

    # -- connection ------------------------------------------------------
    async def ensure(self):
        async with self.lock:
            if self.ws is not None and self.ws.state.name == "OPEN" and self.ready.is_set():
                return
            st = config.read_state(linx_admin.STATE)
            if not st.get("ws_token") or st.get("mac") != self.dev["mac"]:
                st = await asyncio.to_thread(linx_admin.refresh_token, self.dev["mac"])
            hdr = {"Authorization": "Bearer " + st["ws_token"], "Protocol-Version": "1",
                   "Device-Id": st["mac"], "Client-Id": st["client_id"]}
            try:
                self.ws = await websockets.connect(WS_URL, additional_headers=hdr, max_size=None,
                                                   open_timeout=10)
            except websockets.InvalidStatus as e:
                if e.response.status_code in (401, 403):  # token rotated: refetch once
                    st = await asyncio.to_thread(linx_admin.refresh_token, self.dev["mac"])
                    hdr["Authorization"] = "Bearer " + st["ws_token"]
                    self.ws = await websockets.connect(WS_URL, additional_headers=hdr, max_size=None)
                else:
                    raise
            self.ready = asyncio.Event()
            await self.ws.send(json.dumps(HELLO))
            asyncio.ensure_future(self._recv(self.ws))
            await asyncio.wait_for(self.ready.wait(), timeout=10)
            self.last_activity = time.monotonic()
            asyncio.ensure_future(self._idle_watch(self.ws))
            log("linx session", self.sid)

    async def _idle_watch(self, ws):
        while ws.state.name == "OPEN":
            await asyncio.sleep(2)
            quiet = time.monotonic() - self.last_activity
            if (self.mic is None and not self.speaking.is_set() and self.pending_tools == 0
                    and not self.toggling and quiet > self.idle_close_s):
                log(f"空闲 {int(quiet)}s，断开灵矽会话（按键或播报时自动重连）")
                await ws.close()

    async def _send(self, obj):
        self.last_activity = time.monotonic()
        await self.ws.send(json.dumps(dict(obj, session_id=self.sid)))

    async def _recv(self, ws):
        try:
            async for m in ws:
                self.last_activity = time.monotonic()
                if isinstance(m, bytes):
                    if not self.muted:
                        self.player.write(m)
                    continue
                d = json.loads(m)
                t = d.get("type")
                if t == "hello":
                    self.sid = d.get("session_id")
                elif t == "mcp":
                    await self._mcp(d["payload"])
                elif t == "stt":
                    text = d.get("text", "")
                    if text in self.announcing:
                        self.announcing.discard(text)
                        continue
                    log("听到:", text)
                    self._mirror("user", text)
                elif t == "tts":
                    s = d.get("state")
                    if s == "start":
                        self.speaking.set()
                    elif s == "sentence_start":
                        log("播报:", d.get("text"))
                        self._mirror("assistant", d.get("text", ""))
                    elif s == "stop":
                        self.speaking.clear()
                        self.player.close()
        except websockets.ConnectionClosed as e:
            log("linx session closed", e.code, e.reason or "")
        finally:
            self.speaking.clear()
            self.player.close()

    async def _mcp(self, p):
        meth, rid = p.get("method"), p.get("id")
        if meth == "initialize":
            await self._send({"type": "mcp", "payload": {"jsonrpc": "2.0", "id": rid, "result": {
                "protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                "serverInfo": {"name": "sunflower", "version": "0.1.0"}}}})
        elif meth == "tools/list":
            await self._send({"type": "mcp", "payload": {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}})
            self.ready.set()
        elif meth == "tools/call":
            asyncio.ensure_future(self._tool(rid, p.get("params") or {}))

    async def _tool(self, rid, params):
        name, args = params.get("name"), params.get("arguments") or {}
        log("工具:", name, json.dumps(args, ensure_ascii=False))
        route = TOOL_ROUTES.get(name)
        self.pending_tools += 1
        try:
            if not route:
                raise ValueError(f"unknown tool {name}")
            res = await asyncio.to_thread(self.host.post, route, args)
            text, err = res.get("say", "好的"), False
        except Exception as e:  # host down / timeout must still answer within the platform budget
            text, err = f"主机连接失败：{type(e).__name__}，请检查电脑上的服务", True
        finally:
            self.pending_tools -= 1
        await self._send({"type": "mcp", "payload": {"jsonrpc": "2.0", "id": rid, "result": {
            "content": [{"type": "text", "text": text}], "isError": err}}})

    def _mirror(self, role, text):
        if text:
            threading.Thread(target=self._mirror_blocking, args=(role, text), daemon=True).start()

    def _mirror_blocking(self, role, text):
        try:
            self.host.post("/api/voice", {"role": role, "text": text}, timeout=3)
        except Exception:
            pass

    # -- user actions ----------------------------------------------------
    async def say_text(self, text):
        await self.ensure()
        await self._send({"type": "listen", "state": "detect", "text": text})

    async def press_quick(self, key):
        text = self.quick.get(key)
        if text:
            log(f"快捷键 {key}:", text)
            await self.say_text(text)

    def toggle_mute(self):
        self.muted = not self.muted
        log("🔇 静音：回执只上屏，不播报" if self.muted else "🔊 已恢复播报")
        return self.muted

    async def announce(self, text):
        if self.muted:  # 面板照常显示回执；不连灵矽，也不占通话时长
            return
        await self.ensure()
        self.announcing.add(text)
        await self._send({"type": "listen", "state": "detect", "text": "任务回执", "text_response": text})

    async def toggle_talk(self):
        # presses arriving while we connect / start / stop are dropped, never queued:
        # a queued press would spawn a second mic and interleave frames
        if self.toggling:
            return
        self.toggling = True
        try:
            if self.mic is None:
                # 先开麦再连灵矽：连接要 ~3 s，期间的话先攒着，listen start 之后补发
                connected = self.ws is not None and self.ws.state.name == "OPEN"
                ready = asyncio.Event()
                self.mic = subprocess.Popen(self.dev["audio_in"], stdout=subprocess.PIPE,
                                            stderr=subprocess.DEVNULL)
                self.mic_task = asyncio.ensure_future(self._pump_mic(self.mic, ready))
                self._earcon(EARCON_START)
                log("🎙 录音中…（再按一次结束）" if connected else "🎙 录音中…（连接灵矽中，可以直接说；说完再按一次结束）")
                await self.ensure()
                if self.speaking.is_set():
                    await self._send({"type": "abort", "reason": "wake_word_detected"})
                await self._send({"type": "listen", "state": "start", "mode": "manual"})
                ready.set()
            else:
                mic, self.mic = self.mic, None
                mic.terminate()
                await self.mic_task
                await self._reap(mic)
                await self._send({"type": "listen", "state": "stop"})
                self._earcon(EARCON_STOP)
                log("🎙 结束，识别中…")
        except Exception as e:
            log(f"✘ 说话失败：{type(e).__name__}: {e}")
            if self.mic is not None:
                mic, self.mic = self.mic, None
                await self._reap(mic)
        finally:
            self.toggling = False

    def _earcon(self, pcm):
        if self.earcons:
            self.player.write(pcm)
            self.player.close()

    async def _pump_mic(self, mic, ready):
        buf, pending = b"", []
        while True:
            chunk = await asyncio.to_thread(mic.stdout.read, FRAME_BYTES)
            if not chunk:
                break
            buf += chunk
            while len(buf) >= FRAME_BYTES:
                frame, buf = buf[:FRAME_BYTES], buf[FRAME_BYTES:]
                pending.append(frame)
            if ready.is_set() and not await self._flush(pending):
                return
        if ready.is_set():
            await self._flush(pending)

    @staticmethod
    async def _reap(mic):
        """Collect the mic process so stopped recorders never linger as zombies."""
        mic.terminate()
        await asyncio.to_thread(mic.wait)
        mic.stdout.close()

    async def _flush(self, frames):
        try:
            for f in frames:
                await self.ws.send(f)
        except websockets.ConnectionClosed:
            return False
        frames.clear()
        return True

    # -- host announcements ----------------------------------------------
    def watch_host(self):
        while True:
            try:
                for event, data in self.host.events():
                    if event == "announce" and data.get("text"):
                        log("回执:", data["text"])
                        asyncio.run_coroutine_threadsafe(self.announce(data["text"]), self.loop)
            except Exception as e:
                log("host events reconnect:", type(e).__name__)
                time.sleep(2)


# -- triggers ----------------------------------------------------------------
def stdin_trigger(loop, dev):
    """Space / Enter / presenter PageUp-PageDown toggle talking; 1-5 quick requests; `t` types a text request;
    `m` toggles mute; `q` quits."""
    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    _tty.append((fd, old))
    try:
        tty.setcbreak(fd)
        while True:
            ch = os.read(fd, 1)
            if ch == b"\x1b":  # escape sequence: PageUp \x1b[5~ / PageDown \x1b[6~ / arrows
                os.read(fd, 8)
                ch = b" "
            if ch in (b" ", b"\n", b"\r"):
                asyncio.run_coroutine_threadsafe(dev.toggle_talk(), loop)
            elif ch in (b"t", b"T"):
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
                dev.typing = True
                try:
                    text = input("\n文字需求> ").strip()
                finally:
                    dev.typing = False
                tty.setcbreak(fd)
                if text:
                    asyncio.run_coroutine_threadsafe(dev.say_text(text), loop)
            elif ch.decode(errors="ignore") in dev.quick:
                asyncio.run_coroutine_threadsafe(dev.press_quick(ch.decode()), loop)
            elif ch in (b"m", b"M"):
                dev.toggle_mute()
            elif ch in (b"q", b"Q"):
                loop.call_soon_threadsafe(loop.stop)
                return
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


EV_KEY = 1
TOGGLE_KEYS = {57, 28, 104, 109, 48, 63, 425}  # SPACE ENTER PAGEUP PAGEDOWN B(black) F5 presenter
DIGIT_KEYS = {2: "1", 3: "2", 4: "3", 5: "4", 6: "5", 79: "1", 80: "2", 81: "3", 75: "4", 76: "5"}  # 主键盘 / 小键盘
# 一个键代替一句话（#10）：走和说话同一条路，由灵矽路由到工具；profile 的 device.quick 可覆盖
QUICK = {"1": "检查一下代码有没有问题", "2": "跑一下测试，把失败的修好", "3": "进度怎么样了",
         "4": "停下", "5": "撤销刚才的改动"}


def evdev_action(code):
    return "toggle" if code in TOGGLE_KEYS else DIGIT_KEYS.get(code)


def evdev_trigger(loop, dev):
    """Read raw Linux input events (stdlib only); any presenter/keyboard toggle key = push-to-talk."""
    import glob
    import select
    fmt = "llHHi"
    size = struct.calcsize(fmt)
    fds = []
    for path in sorted(glob.glob("/dev/input/event*")):
        try:
            fds.append(os.open(path, os.O_RDONLY | os.O_NONBLOCK))
        except PermissionError:
            log(f"no access to {path}: sudo usermod -aG input $USER")
    if not fds:
        log("no input devices; fall back to stdin trigger")
        return stdin_trigger(loop, dev)
    while True:
        ready, _, _ = select.select(fds, [], [])
        for fd in ready:
            try:
                data = os.read(fd, size * 16)
            except BlockingIOError:
                continue
            for i in range(0, len(data) - size + 1, size):
                _, _, etype, code, value = struct.unpack(fmt, data[i:i + size])
                act = evdev_action(code) if etype == EV_KEY and value == 1 else None
                if act == "toggle":
                    asyncio.run_coroutine_threadsafe(dev.toggle_talk(), loop)
                elif act:
                    asyncio.run_coroutine_threadsafe(dev.press_quick(act), loop)


async def amain(a):
    prof = config.load_profile(a.profile)
    env = config.load_env()
    token = env.get("SUNFLOWER_TOKEN")
    if not token:
        raise SystemExit("SUNFLOWER_TOKEN 未配置（.env）")
    host = Host(a.host or env.get("SUNFLOWER_HOST_URL") or prof["device"]["host_url"], token)
    dev = Device(prof, host)
    dev.loop = asyncio.get_running_loop()
    threading.Thread(target=dev.watch_host, daemon=True).start()
    if a.text:
        await dev.say_text(a.text)
        await asyncio.sleep(a.linger)
        return
    if a.announce:
        await dev.announce(a.announce)
        await asyncio.sleep(8)
        return
    trig = evdev_trigger if prof["device"].get("trigger") == "evdev" else stdin_trigger
    threading.Thread(target=trig, args=(dev.loop, dev), daemon=True).start()
    if AUTO_RELOAD:
        asyncio.ensure_future(dev.reload_watch())
    log(f"太阳花设备就绪 · profile={prof['name']} · 按空格/翻页笔说话，1–5 快捷指令，t 输入文字，m 静音，q 退出"
        + (" · 随部署自动换代" if AUTO_RELOAD else "") + (" · 🔇 静音" if dev.muted else ""))
    log("快捷指令：" + " / ".join(f"{k} {v}" for k, v in sorted(dev.quick.items())))
    await asyncio.Event().wait()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sunflower.device")
    ap.add_argument("--profile", default="dev-single-mac")
    ap.add_argument("--host", help="override profile device.host_url")
    ap.add_argument("--text", help="send one text request, then exit after --linger seconds")
    ap.add_argument("--linger", type=float, default=40)
    ap.add_argument("--announce", help="speak this text once (cold connection test)")
    a = ap.parse_args(argv)
    try:
        asyncio.run(amain(a))
    except (KeyboardInterrupt, RuntimeError):
        pass


if __name__ == "__main__":
    main()
