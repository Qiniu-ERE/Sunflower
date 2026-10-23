import asyncio
import json
import shutil
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from sunflower import device, tg

TOKEN = "123456:SECRET-token-value"
OWNER, STRANGER = 42, 666


class FakeTelegram:
    """Bot API 的最小替身：记录每次调用，按方法名回固定结果。"""

    def __init__(self, fail=None):
        self.calls, self.fail, self.next_id = [], fail or set(), 100
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
                if method in fake.fail:
                    out, code = {"ok": False, "description": f"boom at {self.path}"}, 500
                else:
                    fake.next_id += 1
                    result = {"getFile": {"file_path": "voice/1.oga"}, "getMe": {"username": "fake_bot"}}.get(
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


def msg(uid, **kw):
    return {"update_id": 1, "message": dict({"from": {"id": uid}, "chat": {"id": uid}}, **kw)}


class BridgeCase(unittest.TestCase):
    def setUp(self):
        self.tg = FakeTelegram()
        self.addCleanup(self.tg.close)
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()
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
                                                        "message": {"chat": {"id": OWNER}}}})
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
        self.assertEqual(self.dev.got, [("audio", len(pcm))])
        # 灵矽回话：先来文字，一句播完时回一条语音
        self.br._on_dev_event("say", "目前空闲")
        self.dev.player.write(pcm)
        self.dev.player.close()
        voice = self.tg.of("sendVoice")
        self.assertEqual(len(voice), 1)
        self.assertIn(b"OggS", voice[0])
        self.assertIn("目前空闲".encode(), voice[0])


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
        self.assertEqual(len(fake.of("sendMessage")), 1)       # 一张卡片
        self.assertLessEqual(len(fake.of("editMessageText")), 2)  # 节流：执行流没逐条推
        last = fake.of("editMessageText")[-1]["text"]
        self.assertIn("✅ 完成", last)
        self.assertIn("已修复，测试通过", last)                  # 结束态立即发，不被节流吞掉
        n = len(fake.calls)
        card.show(last, final=True)
        self.assertEqual(len(fake.calls), n)                   # 内容没变不调接口


if __name__ == "__main__":
    unittest.main()
