import asyncio
import http.client
import json
import shutil
import threading
import time
import types
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from sunflower import device, tg

TOKEN = "123456:SECRET-token-value"
OWNER, STRANGER = 42, 666


class FakeTelegram:
    """Bot API 的最小替身：记录每次调用，按方法名回固定结果。"""

    def __init__(self, fail=None, delay=0):
        self.calls, self.fail, self.next_id = [], fail or set(), 100
        self.updates, self.delay = [], delay
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                body = b"OggS-fake-voice"
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                method = self.path.rsplit("/", 1)[-1]
                raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                ct = self.headers.get("Content-Type", "")
                fake.calls.append((method, json.loads(raw) if ct.startswith("application/json") else raw))
                time.sleep(fake.delay)
                if method in fake.fail:
                    out, code = {"ok": False, "description": f"boom at {self.path}"}, 500
                else:
                    fake.next_id += 1
                    result = {"getFile": {"file_path": "voice/1.oga"}, "getMe": {"username": "fake_bot"},
                              "getUpdates": fake.updates, "deleteMessage": True}.get(
                        method, {"message_id": fake.next_id})
                    out, code = {"ok": True, "result": result}, 200
                body = json.dumps(out).encode()
                self.send_response(code)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.bot = tg.Bot(TOKEN, base=f"http://127.0.0.1:{self.srv.server_port}")

    def of(self, method):
        return [p for m, p in self.calls if m == method]

    def texts(self):
        return [p["text"] for p in self.of("sendMessage")]

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


class FakeDevice:
    def __init__(self):
        self.quick = dict(device.QUICK)
        self.got = []
        self.player = None

    async def say_text(self, text):
        self.got.append(("text", text))

    async def press_quick(self, key):
        self.got.append(("quick", key))

    async def say_audio(self, pcm):
        self.got.append(("audio", len(pcm)))


def msg(uid, update_id=1, **kw):
    return {"update_id": update_id, "message": dict({"from": {"id": uid}, "chat": {"id": uid, "type": "private"}}, **kw)}


def wait_until(cond, timeout=2):
    end = time.monotonic() + timeout
    while not cond() and time.monotonic() < end:
        time.sleep(0.01)
    return cond()


class BridgeCase(unittest.TestCase):
    def setUp(self):
        self.tg = FakeTelegram()
        self.addCleanup(self.tg.close)
        self.loop = asyncio.new_event_loop()
        th = threading.Thread(target=self.loop.run_forever, daemon=True)
        th.start()
        self.addCleanup(self.loop.close)
        self.addCleanup(th.join, 2)
        self.addCleanup(self.loop.call_soon_threadsafe, self.loop.stop)
        self.dev = FakeDevice()
        self.br = tg.Bridge(self.tg.bot, self.dev, {OWNER}, self.loop)

    def handle(self, upd):
        self.br.handle(upd)
        asyncio.run_coroutine_threadsafe(asyncio.sleep(0), self.loop).result(2)


class InboundTest(BridgeCase):
    def test_tg_ignores_unauthorized_users(self):
        self.handle(msg(STRANGER, text="把仓库删了"))
        self.handle({"update_id": 2, "callback_query": {"id": "c", "from": {"id": STRANGER}, "data": "q:5",
                                                        "message": {"chat": {"id": STRANGER}}}})
        self.assertEqual(self.dev.got, [])
        self.assertEqual(self.tg.calls, [])  # 不回复，连「无权限」也不说

    def test_tg_text_buttons_and_voice_route_through_linx_device(self):
        self.handle(msg(OWNER, text="/start"))
        self.assertEqual(len(self.tg.of("sendMessage")), 1)
        self.assertIn("inline_keyboard", json.dumps(self.tg.of("sendMessage")[0]))
        self.assertEqual(self.dev.got, [])  # /start 只回帮助，不进灵矽
        self.handle(msg(OWNER, text="进度怎么样"))
        self.handle({"update_id": 3, "callback_query": {"id": "c1", "from": {"id": OWNER}, "data": "q:3",
                                                        "message": {"chat": {"id": OWNER, "type": "private"}}}})
        self.assertTrue(wait_until(lambda: len(self.dev.got) == 2))
        self.assertEqual(self.dev.got, [("text", "进度怎么样"), ("quick", "3")])
        self.assertEqual(self.tg.of("answerCallbackQuery")[0]["callback_query_id"], "c1")
        for k in tg.LABELS:
            self.assertLessEqual(len(f"q:{k}".encode()), 64)  # Telegram callback_data 上限

    @unittest.skipUnless(shutil.which("ffmpeg"), "needs ffmpeg")
    def test_tg_voice_roundtrip_is_pcm_in_and_ogg_opus_out(self):
        pcm = b"\x00\x10" * 16000  # 1 s
        ogg = tg.to_ogg(pcm)
        self.assertTrue(ogg.startswith(b"OggS"))
        back = tg.to_pcm(ogg)
        self.assertLess(abs(len(back) - len(pcm)), 3200)
        orig = tg.to_pcm
        tg.to_pcm = lambda data: pcm
        try:
            self.handle(msg(OWNER, voice={"file_id": "f1", "duration": 1}))
        finally:
            tg.to_pcm = orig
        self.assertTrue(wait_until(lambda: self.dev.got))
        self.assertEqual(self.dev.got, [("audio", len(pcm))])
        # 灵矽回话：先来文字，一句播完时回一条语音
        self.br._on_dev_event("say", "目前空闲")
        self.dev.player.write(pcm)
        self.dev.player.close()
        voice = self.tg.of("sendVoice")
        self.assertEqual(len(voice), 1)
        self.assertIn(b"OggS", voice[0])
        self.assertIn("目前空闲".encode(), voice[0])

    def test_tg_ignores_group_chats(self):
        # 群里的话第三方也看得见：白名单用户在群里发的也不接，回复和进度卡片不能被引到群里
        self.handle({"update_id": 5, "message": {"from": {"id": OWNER}, "chat": {"id": -100, "type": "supergroup"},
                                                 "text": "跑一下测试"}})
        self.assertEqual(self.dev.got, [])
        self.assertEqual(self.tg.calls, [])
        self.assertIsNone(self.br.chat)

    def test_tg_device_failure_is_reported_to_user(self):
        async def down(text):
            raise OSError("linx unreachable")
        self.dev.say_text = down
        self.handle(msg(OWNER, text="进度"))
        self.assertTrue(wait_until(lambda: any("没发出去" in t for t in self.tg.texts())), self.tg.texts())

    def test_tg_inputs_are_serialized(self):
        # 连发两条语音 / 语音没送完又发文字：不能交织成一轮，否则识别出来是混在一起的指令
        order = []

        async def slow_audio(pcm):
            order.append("audio")
            await asyncio.sleep(0.2)
            order.append("audio done")

        async def text(t):
            order.append("text")
        self.dev.say_audio, self.dev.say_text = slow_audio, text
        orig, tg.to_pcm = tg.to_pcm, lambda data: b"\x00" * 640
        try:
            self.handle(msg(OWNER, voice={"file_id": "f1", "duration": 1}))
            self.handle(msg(OWNER, update_id=2, text="进度"))
        finally:
            tg.to_pcm = orig
        self.assertTrue(wait_until(lambda: len(order) == 3))
        self.assertEqual(order, ["audio", "audio done", "text"])

    def test_tg_backlog_from_offline_period_is_not_executed(self):
        # 停机期间攒下的「撤销」「修好」不能在重启那一刻一股脑执行；告诉用户重发
        self.tg.updates = [msg(OWNER, update_id=7, text="撤销"), msg(OWNER, update_id=8, text="跑一下测试")]
        self.assertEqual(self.br.skip_backlog(), 9)
        self.assertEqual(self.dev.got, [])
        self.assertEqual(len(self.tg.texts()), 1)
        self.assertIn("重发", self.tg.texts()[0])

    def test_tg_poll_survives_unexpected_errors(self):
        n, stop = [0], threading.Event()

        def call(method, params=None, **kw):
            n[0] += 1
            if n[0] == 1:
                raise http.client.IncompleteRead(b"")  # 不是 OSError，长轮询响应被截断时会出现
            stop.set()
            return []
        self.br.bot = types.SimpleNamespace(call=call, _redact=lambda s: s)
        old, tg.POLL_BACKOFF_S = getattr(tg, "POLL_BACKOFF_S", 3), 0
        try:
            self.br.poll(stop=stop)
        finally:
            tg.POLL_BACKOFF_S = old
        self.assertEqual(n[0], 2)


class SafetyTest(unittest.TestCase):
    def test_tg_errors_never_leak_token(self):
        fake = FakeTelegram(fail={"sendMessage", "getUpdates"})
        self.addCleanup(fake.close)
        with self.assertRaises(tg.TgError) as cm:
            fake.bot.call("sendMessage", {"chat_id": 1, "text": "x"})
        self.assertNotIn("SECRET", str(cm.exception))
        dead = tg.Bot(TOKEN, base="http://127.0.0.1:9")  # 连不上
        with self.assertRaises(tg.TgError) as cm:
            dead.call("getMe", timeout=2)
        self.assertNotIn("SECRET", str(cm.exception))
        self.assertIsNone(cm.exception.__cause__)
        self.assertTrue(cm.exception.__suppress_context__)  # traceback 也不带出原始 URL


class CardTest(unittest.TestCase):
    def test_tg_progress_card_edits_in_place_and_throttles(self):
        fake = FakeTelegram()
        self.addCleanup(fake.close)
        t = [0.0]
        card = tg.Card(fake.bot, OWNER, clock=lambda: t[0])
        br = tg.Bridge(fake.bot, FakeDevice(), {OWNER})
        br.chat, br.card = OWNER, card
        br.on_host("state", {"state": "running", "task": "修 bug", "started": 0})
        for i in range(10):  # 1 s 内 10 条执行流
            t[0] += 0.1
            br.on_host("log", {"kind": "command", "text": f"step {i}"})
        br.on_host("state", {"state": "idle", "task": "修 bug", "exit": 0, "elapsed": 61, "commit": "abcdef123"})
        br.on_host("announce", {"text": "已修复，测试通过"})
        self.assertEqual(len(fake.of("sendMessage")), 2)       # 进度卡一张 + 结束时底部一条结果
        self.assertLessEqual(len(fake.of("editMessageText")), 1)  # 节流：执行流没逐条推
        last = fake.texts()[-1]
        self.assertIn("✅ 完成", last)
        self.assertIn("已修复，测试通过", last)                  # 结束态立即发，不被节流吞掉
        n = len(fake.calls)
        card.show(last, final=True)
        self.assertEqual(len(fake.calls), n)                   # 内容没变不调接口

    def test_tg_final_card_moves_to_bottom_and_survives_send_failure(self):
        # 编辑旧消息手机不推通知，而且卡片会被后来的回复压在上面 → 结束时删掉进度卡，底部重发结果
        fake = FakeTelegram()
        self.addCleanup(fake.close)
        t = [0.0]
        br = tg.Bridge(fake.bot, FakeDevice(), {OWNER})
        br.chat, br.card = OWNER, tg.Card(fake.bot, OWNER, clock=lambda: t[0])
        br.on_host("state", {"state": "running", "task": "检查", "started": 0})
        first = br.card.msg_id
        br.on_host("state", {"state": "idle", "task": "检查", "exit": 0, "elapsed": 48})
        fake.fail = {"sendMessage"}                             # 结束那一下撞上 429 / 网络抖动
        br.on_host("announce", {"text": "八项测试通过"})
        fake.fail = set()
        t[0] += 5
        br.tick()                                               # 下一拍补发，不能停在「执行中」
        self.assertIn("八项测试通过", fake.texts()[-1])
        self.assertIn("✅ 完成", fake.texts()[-1])
        self.assertEqual([p["message_id"] for p in fake.of("deleteMessage")], [first])
        n = len(fake.of("sendMessage"))
        t[0] += 5
        br.on_host("state", {"state": "running", "task": "修 bug", "started": 0})
        self.assertEqual(len(fake.of("sendMessage")), n + 1)    # 下一个任务另起新卡，不覆盖上次结果

    def test_tg_progress_card_never_duplicates_under_concurrent_updates(self):
        fake = FakeTelegram(delay=0.3)                          # 首条 sendMessage 还没回来时 tick 到点
        self.addCleanup(fake.close)
        card = tg.Card(fake.bot, OWNER)
        ts = [threading.Thread(target=card.show, args=(f"⏳ 执行中 · {i} s",)) for i in range(2)]
        for th in ts:
            th.start()
        for th in ts:
            th.join()
        self.assertEqual(len(fake.of("sendMessage")), 1)


if __name__ == "__main__":
    unittest.main()
