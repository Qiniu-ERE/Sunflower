"""Telegram 入口（#5）：手机私聊 bot，发文字 / 语音 / 点按钮，经灵矽软设备进同一条链路；进度原地刷新在一张卡片上。

    python3 -m sunflower.tg --profile tg-bridge

灵矽仍是大脑：文字走 listen.detect.text，语音转成 PCM 16k 按住说话一次送上去，意图识别和工具路由都在灵矽。
只出站（getUpdates 长轮询，无需公网 webhook）。只理白名单 SUNFLOWER_TG_ALLOW 里的 user_id，其余消息不回复。
"""
import argparse
import asyncio
import json
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid

from . import config, device

API = "https://api.telegram.org"
EDIT_GAP_S = 3  # 同一聊天官方上限约 1 条/秒；卡片 3 s 一刷足够看进度
POLL_BACKOFF_S = 3
LABELS = {"1": "🔍 检查", "2": "🛠 修复", "3": "⏱ 进度", "4": "⏹ 停下", "5": "↩️ 撤销"}
KEYBOARD = {"inline_keyboard": [[{"text": v, "callback_data": f"q:{k}"} for k, v in LABELS.items()]]}
HELP = ("太阳花 · 发文字或语音说需求，或者点下面的按钮。\n"
        "例：「检查一下代码有没有问题」「跑一下测试把失败的修好」「进度」「停」「撤」")


def log(*a):
    device.log("[tg]", *a)


class TgError(RuntimeError):
    pass


def multipart(fields, files):
    """files: {name: (filename, bytes, content_type)} → (body, content_type)."""
    b = uuid.uuid4().hex
    out = []
    for k, v in fields.items():
        out.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    for k, (fn, data, ct) in files.items():
        out.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{fn}"\r\n'
                   f'Content-Type: {ct}\r\n\r\n'.encode() + data + b"\r\n")
    out.append(f"--{b}--\r\n".encode())
    return b"".join(out), f"multipart/form-data; boundary={b}"


class Bot:
    def __init__(self, token, base=API):
        self.token, self.base = token, base

    def _redact(self, text):
        return text.replace(self.token, "<token>") if self.token else text

    def call(self, method, params=None, files=None, timeout=15):
        """出错一律抛 TgError，且信息里不带 token（URL 里有 token，异常文本和 traceback 都会带出来）。"""
        url = f"{self.base}/bot{self.token}/{method}"
        if files:
            data, ct = multipart({k: v if isinstance(v, str) else json.dumps(v) for k, v in (params or {}).items()},
                                 files)
        else:
            data, ct = json.dumps(params or {}).encode(), "application/json"
        req = urllib.request.Request(url, data=data, headers={"Content-Type": ct}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                resp = json.loads(r.read())
        except urllib.error.HTTPError as e:
            try:
                desc = json.loads(e.read()).get("description", "")
            except ValueError:
                desc = ""
            raise TgError(self._redact(f"{method}: HTTP {e.code} {desc}".strip())) from None
        except (OSError, ValueError) as e:
            raise TgError(self._redact(f"{method}: {type(e).__name__}: {e}")) from None
        if not resp.get("ok"):
            raise TgError(self._redact(f"{method}: {resp.get('description', 'not ok')}"))
        return resp.get("result")

    def download(self, file_id):
        path = self.call("getFile", {"file_id": file_id})["file_path"]
        try:
            with urllib.request.urlopen(f"{self.base}/file/bot{self.token}/{path}", timeout=30) as r:
                return r.read()
        except OSError as e:
            raise TgError(self._redact(f"download: {type(e).__name__}: {e}")) from None


def _ffmpeg(args, data):
    r = subprocess.run(["ffmpeg", "-loglevel", "error", *args], input=data, capture_output=True, timeout=60)
    if r.returncode:
        raise TgError("ffmpeg: " + r.stderr.decode(errors="replace").strip()[:200])
    return r.stdout


def to_pcm(ogg):
    return _ffmpeg(["-i", "pipe:0", "-f", "s16le", "-ac", "1", "-ar", "16000", "pipe:1"], ogg)


def to_ogg(pcm):
    return _ffmpeg(["-f", "s16le", "-ar", "16000", "-ac", "1", "-i", "pipe:0",
                    "-c:a", "libopus", "-b:a", "24k", "-f", "ogg", "pipe:1"], pcm)


def parse_allow(raw):
    return {int(x) for x in (raw or "").replace(" ", "").split(",") if x.lstrip("-").isdigit()}


class Card:
    """一张进度卡片，执行中原地编辑：内容没变不调接口，两次编辑至少隔 EDIT_GAP_S。

    结束态立即发，而且删掉进度卡、在底部另发一条：编辑旧消息手机不推通知，卡片也早被后来的回复压在上面。
    发失败的留在 pending，下一拍（tick）补发。主机事件线程和 tick 线程都会调，一把锁串起来。
    """

    def __init__(self, bot, chat_id, clock=time.monotonic, gap=EDIT_GAP_S):
        self.bot, self.chat_id, self.clock, self.gap = bot, chat_id, clock, gap
        self.msg_id, self.shown, self.pending, self.final, self.at = None, None, None, False, -1e9
        self.lock = threading.Lock()

    def show(self, text, final=False):
        with self.lock:
            self.pending, self.final = text, final
            if final or self.clock() - self.at >= self.gap:
                self._flush()

    def flush(self):
        with self.lock:
            self._flush()

    def _flush(self):
        text, final = self.pending, self.final
        if text is None or text == self.shown:
            self.pending = None
            return
        if final or self.msg_id is None:
            new = self.bot.call("sendMessage", {"chat_id": self.chat_id, "text": text,
                                                "reply_markup": KEYBOARD})["message_id"]
            old, self.msg_id = self.msg_id, None if final else new
            if final and old is not None:
                try:
                    self.bot.call("deleteMessage", {"chat_id": self.chat_id, "message_id": old})
                except TgError as e:  # 删不掉（超 48 h 等）只是多留一张旧卡
                    log("✘", e)
        else:
            self.bot.call("editMessageText", {"chat_id": self.chat_id, "message_id": self.msg_id, "text": text,
                                              "reply_markup": KEYBOARD})
        self.shown, self.pending, self.at = text, None, self.clock()


def render(st, now=time.time):
    """主机事件累积成的状态 → 卡片文字。"""
    if st.get("state") == "running":
        head = f"⏳ 执行中{' · 只读' if st.get('read_only') else ''} · {int(now() - st.get('started', now()))} s"
    elif st.get("exit") is None:
        head = "💤 空闲"
    else:
        head = ("✅ 完成" if st.get("exit") == 0 else f"✘ 失败（退出码 {st['exit']}）") + f" · {st.get('elapsed', 0)} s"
    lines = [head]
    if st.get("task"):
        lines.append(f"任务：{st['task']}")
    if st.get("step") and st.get("state") == "running":
        lines.append(f"最近：{st['step']}")
    if st.get("say"):
        lines.append(f"🔊 {st['say']}")
    if st.get("commit"):
        lines.append(f"提交：{st['commit'][:7]}")
    return "\n".join(lines)


class Capture:
    """替代 Player：把灵矽下行的 TTS PCM 攒起来，一句话播完（close）时交给回调。"""

    def __init__(self, sink):
        self.sink, self.buf = sink, bytearray()

    def write(self, pcm):
        self.buf += pcm

    def close(self):
        if self.buf:
            pcm, self.buf = bytes(self.buf), bytearray()
            self.sink(pcm)


class Bridge:
    def __init__(self, bot, dev, allow, loop=None, voice_reply=True):
        self.bot, self.dev, self.allow, self.loop = bot, dev, allow, loop
        self.voice_reply = voice_reply
        self.chat = None          # 最近一个说话的白名单聊天；回复和进度卡片都发到这里
        self.card = None
        self.st = {}
        self.said = []            # 灵矽这一轮的回复文字
        self.want_voice = False   # 这一轮是语音进来的 → 回语音
        self.ignored = set()
        self.serial = None        # 灵矽输入一次只送一条：两段语音交织成一轮会识别成混在一起的指令
        dev.player = Capture(self._on_tts_audio)
        dev.on_event = self._on_dev_event

    # -- inbound -----------------------------------------------------------
    async def _serially(self, coro, chat):
        if self.serial is None:
            self.serial = asyncio.Lock()
        async with self.serial:
            try:
                await coro
            except Exception as e:  # 灵矽连不上 / 未装配：用户那边不能石沉大海
                why = self.bot._redact(f"{type(e).__name__}: {e}")
                log("✘ 没发进灵矽：", why)
                await asyncio.to_thread(self._send_text, f"✘ 没发出去（{why[:120]}）；可以再发一次", chat)

    def _run(self, coro, chat):
        return asyncio.run_coroutine_threadsafe(self._serially(coro, chat), self.loop)

    def handle(self, upd):
        msg = upd.get("message") or (upd.get("callback_query") or {}).get("message") or {}
        who = ((upd.get("message") or upd.get("callback_query") or {}).get("from") or {}).get("id")
        kind = (msg.get("chat") or {}).get("type")
        if who not in self.allow or kind != "private":
            if (who, kind) not in self.ignored:
                self.ignored.add((who, kind))
                log(f"忽略 {kind} 聊天里的用户 {who}（只接白名单私聊，不回复）")
            return
        chat = (msg.get("chat") or {}).get("id")
        if chat != self.chat:
            self.chat, self.card = chat, Card(self.bot, chat)
        if "callback_query" in upd:
            cq = upd["callback_query"]
            key = (cq.get("data") or "").removeprefix("q:")
            self.bot.call("answerCallbackQuery", {"callback_query_id": cq["id"],
                                                  "text": self.dev.quick.get(key, "这个按钮已失效")})
            self.want_voice = False
            self._run(self.dev.press_quick(key), chat)
        elif msg.get("voice"):
            pcm = to_pcm(self.bot.download(msg["voice"]["file_id"]))
            self.want_voice = True
            self._run(self.dev.say_audio(pcm), chat)
        elif msg.get("text"):
            text = msg["text"].strip()
            if text in ("/start", "/help"):
                self.bot.call("sendMessage", {"chat_id": chat, "text": HELP, "reply_markup": KEYBOARD})
                return
            self.want_voice = False
            self._run(self.dev.say_text(text), chat)

    def skip_backlog(self):
        """启动时丢弃停机期间攒下的消息（不执行），告诉发消息的人重发；返回下一次轮询的 offset。"""
        ups = self.bot.call("getUpdates", {"timeout": 0, "allowed_updates": ["message", "callback_query"]})
        if not ups:
            return None
        chats = {}
        for u in ups:
            m = u.get("message") or (u.get("callback_query") or {}).get("message") or {}
            who = ((u.get("message") or u.get("callback_query") or {}).get("from") or {}).get("id")
            if who in self.allow and (m.get("chat") or {}).get("type") == "private":
                chats[m["chat"]["id"]] = chats.get(m["chat"]["id"], 0) + 1
        for chat, n in chats.items():
            self._send_text(f"太阳花刚重启：离线期间的 {n} 条消息没有执行，需要的话请重发。", chat)
        log(f"丢弃离线期间 {len(ups)} 条消息")
        return ups[-1]["update_id"] + 1

    def poll(self, offset=None, stop=None):
        while not (stop and stop.is_set()):
            try:
                params = {"timeout": 30, "allowed_updates": ["message", "callback_query"]}
                if offset is not None:
                    params["offset"] = offset
                ups = self.bot.call("getUpdates", params, timeout=40)
            except Exception as e:  # 截断的长轮询会抛 http.client 异常；轮询线程死了进程还活着 = 静默失聪
                log("✘", e if isinstance(e, TgError) else self.bot._redact(f"getUpdates: {type(e).__name__}: {e}"))
                time.sleep(POLL_BACKOFF_S)
                continue
            for u in ups:
                offset = u["update_id"] + 1
                try:
                    self.handle(u)
                except Exception as e:  # 单条消息处理失败不拖垮轮询
                    log(f"✘ 处理消息失败：{type(e).__name__}: {self.bot._redact(str(e))}")

    # -- linx replies --------------------------------------------------------
    def _on_dev_event(self, kind, text=""):
        if not self.chat:
            return
        if kind == "stt" and self.want_voice:
            self._send_text(f"🗣 听到：{text}")
        elif kind == "say":
            self.said.append(text)

    def _on_tts_audio(self, pcm):
        said, self.said = "".join(self.said), []
        if not self.chat:
            return
        if self.want_voice and self.voice_reply:
            try:
                self.bot.call("sendVoice", {"chat_id": self.chat, "caption": said[:1000]},
                              files={"voice": ("reply.ogg", to_ogg(pcm), "audio/ogg")}, timeout=30)
                return
            except TgError as e:
                log("✘ 回语音失败，改发文字：", e)
        if said:
            self._send_text(said)

    def _send_text(self, text, chat=None):
        try:
            self.bot.call("sendMessage", {"chat_id": chat or self.chat, "text": text})
        except TgError as e:
            log("✘", e)

    # -- host progress -------------------------------------------------------
    def on_host(self, event, data):
        if event == "state":
            if data.get("state") == "running":
                self.st = {}
            self.st.update({k: data[k] for k in ("state", "task", "started", "elapsed", "exit", "commit", "read_only")
                            if k in data})
        elif event == "log" and data.get("kind") not in ("user",):
            self.st["step"] = data.get("text", "")[:80]
        elif event == "announce":
            self.st["say"] = data.get("text", "")
        else:
            return
        if self.card and self.st.get("task"):
            final = event == "announce"
            try:
                self.card.show(render(self.st), final=final)
            except TgError as e:
                log("✘", e)

    def tick(self):
        """running 时每 EDIT_GAP_S 把累积的进度推一次（无新事件时也刷新用时）；上次没发出去的补发。"""
        if not self.card:
            return
        try:
            if self.st.get("state") == "running":
                self.card.show(render(self.st))
            elif self.card.pending is not None:
                self.card.flush()
        except TgError as e:
            log("✘", e)


def watch_host(host, bridge):
    while True:
        try:
            for event, data in host.events():
                bridge.on_host(event, data)
        except Exception as e:
            log("host events reconnect:", type(e).__name__)
            time.sleep(2)


async def amain(a):
    prof = config.load_profile(a.profile)
    env = config.load_env()
    token, allow = env.get("SUNFLOWER_TG_TOKEN"), parse_allow(env.get("SUNFLOWER_TG_ALLOW"))
    if not token or not allow:
        raise SystemExit("SUNFLOWER_TG_TOKEN / SUNFLOWER_TG_ALLOW 未配置（.env）")
    host = device.Host(a.host or env.get("SUNFLOWER_HOST_URL") or prof["device"]["host_url"], env["SUNFLOWER_TOKEN"])
    dev = device.Device(prof, host)
    dev.loop = asyncio.get_running_loop()
    bot = Bot(token)
    me = await asyncio.to_thread(bot.call, "getMe")
    bridge = Bridge(bot, dev, allow, dev.loop, voice_reply=prof.get("tg", {}).get("voice_reply", True))
    threading.Thread(target=watch_host, args=(host, bridge), daemon=True).start()
    offset = await asyncio.to_thread(bridge.skip_backlog)
    threading.Thread(target=bridge.poll, args=(offset,), daemon=True).start()
    log(f"太阳花 TG 入口就绪 · @{me.get('username')} · 白名单 {len(allow)} 人 · profile={prof['name']}")
    while True:
        await asyncio.sleep(EDIT_GAP_S)
        await asyncio.to_thread(bridge.tick)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sunflower.tg")
    ap.add_argument("--profile", default="tg-bridge")
    ap.add_argument("--host", help="override profile device.host_url")
    try:
        asyncio.run(amain(ap.parse_args(argv)))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
