import asyncio
import gc
import struct
import sys
import time
import unittest
import warnings

from sunflower import device

FRAMES = 10
# 模拟麦克风：先吐 5 帧，停 0.3 s，再吐 5 帧
MIC = [sys.executable, "-c",
       "import sys,time;w=sys.stdout.buffer;"
       f"w.write(b'a'*{device.FRAME_BYTES}*5);w.flush();time.sleep(0.3);"
       f"w.write(b'b'*{device.FRAME_BYTES}*5);w.flush()"]


class FakeWs:
    class state:
        name = "OPEN"

    def __init__(self):
        self.frames, self.json = [], []

    async def send(self, m):
        (self.frames if isinstance(m, bytes) else self.json).append((time.monotonic(), m))


def make_device():
    d = device.Device({"device": {"mac": "02:00:00:00:00:00", "audio_in": MIC, "audio_out": ["true"],
                                  "earcons": False}}, host=None)
    d.ws = FakeWs()
    return d


class PumpTest(unittest.TestCase):
    def test_frames_buffered_until_listen_starts_then_flushed_in_order(self):
        async def go():
            d = make_device()
            ready = asyncio.Event()
            mic = device.subprocess.Popen(MIC, stdout=device.subprocess.PIPE)
            task = asyncio.ensure_future(d._pump_mic(mic, ready))
            await asyncio.sleep(0.15)
            t_ready = time.monotonic()
            ready.set()
            await task
            await d._reap(mic)
            return d.ws.frames, t_ready
        frames, t_ready = asyncio.run(go())
        self.assertEqual(len(frames), FRAMES)
        self.assertTrue(all(t >= t_ready for t, _ in frames), "sent before listen start")
        self.assertEqual([f[:1] for _, f in frames], [b"a"] * 5 + [b"b"] * 5)


class TalkTest(unittest.TestCase):
    def test_press_opens_mic_before_linx_connection_is_ready(self):
        async def go():
            d = make_device()
            seen = {}

            async def slow_ensure():
                seen["mic_open_while_connecting"] = d.mic is not None
                await asyncio.sleep(0.2)
            d.ensure = slow_ensure
            await d.toggle_talk()             # 开始
            await asyncio.sleep(0.4)
            await d.toggle_talk()             # 结束
            return d, seen
        d, seen = asyncio.run(go())
        self.assertTrue(seen["mic_open_while_connecting"])
        states = [__import__("json").loads(m).get("state") for _, m in d.ws.json]
        self.assertEqual(states, ["start", "stop"])
        self.assertEqual(len(d.ws.frames), FRAMES)


    def test_recording_hint_says_press_again_even_when_connecting(self):
        # 冷连接时也要提示再按一次结束，否则用户说完就等，录音一直开着像卡死（#23）
        async def go(cold):
            d = make_device()
            lines = []
            orig, device.log = device.log, lambda *a: lines.append(" ".join(map(str, a)))
            try:
                if cold:
                    ws, d.ws = d.ws, None

                    async def ensure():
                        d.ws = ws
                    d.ensure = ensure
                await d.toggle_talk()
                await d.toggle_talk()
            finally:
                device.log = orig
            return lines
        for cold in (False, True):
            hint = next(l for l in asyncio.run(go(cold)) if "录音中" in l)
            self.assertIn("再按一次结束", hint, f"cold={cold}")


class ReapTest(unittest.TestCase):
    def test_mic_process_reaped_after_stop(self):
        async def go():
            d = make_device()
            d.ensure = lambda: asyncio.sleep(0)
            await d.toggle_talk()
            mic = d.mic
            await asyncio.sleep(0.1)
            await d.toggle_talk()
            return mic
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            mic = asyncio.run(go())
            gc.collect()
        self.assertIsNotNone(mic.returncode, "mic process not reaped")
        self.assertTrue(mic.stdout.closed)
        self.assertEqual([x for x in w if issubclass(x.category, ResourceWarning)], [])


class ReloadTest(unittest.TestCase):
    """部署目录换了提交 → 设备空闲时原地 exec 新代码（#27）。"""

    @staticmethod
    def check(setup, head):
        async def go():
            d = make_device()
            d.ws = None
            setup(d)
            calls = []
            done = await d.reload_check(head=lambda: head, execv=lambda exe, argv: calls.append(argv))
            return done, calls
        return asyncio.run(go())

    def test_device_reexecs_when_deploy_moves_and_idle(self):
        done, calls = self.check(lambda d: None, "f" * 40)
        self.assertTrue(done)
        self.assertEqual(calls[0][1:3], ["-m", "sunflower.device"])
        self.assertEqual(self.check(lambda d: None, device.COMMIT), (False, []))  # 提交没变不动

    def test_device_defers_reexec_while_busy(self):
        busy = {"recording": lambda d: setattr(d, "mic", object()),
                "tool": lambda d: setattr(d, "pending_tools", 1),
                "speaking": lambda d: d.speaking.set(),
                "linx open": lambda d: setattr(d, "ws", FakeWs()),
                "typing": lambda d: setattr(d, "typing", True)}
        for name, make_busy in busy.items():
            self.assertEqual(self.check(make_busy, "f" * 40), (False, []), name)

    def test_failed_reexec_stops_watching_and_stops_claiming_reload(self):
        async def go():
            d = make_device()
            d.ws = None
            tries = []

            async def broken():
                tries.append(1)
                raise OSError("no such interpreter")
            d.reload_check = broken
            await asyncio.wait_for(d.reload_watch(), 1)
            return tries
        old = device.RELOAD_POLL_S, device.AUTO_RELOAD, device.log
        device.RELOAD_POLL_S, device.AUTO_RELOAD, device.log = 0, True, lambda *a: None
        try:
            self.assertEqual(asyncio.run(go()), [1])
            self.assertFalse(device.AUTO_RELOAD)
        finally:
            device.RELOAD_POLL_S, device.AUTO_RELOAD, device.log = old


class HandsFreeTest(unittest.TestCase):
    """不开口也能用：数字键快捷指令、静音只上屏（#10）。"""

    def test_quick_keys_send_preset_requests(self):
        async def go(quick=None):
            d = make_device()
            if quick:
                d.quick.update(quick)
            sent = []

            async def say(text):
                sent.append(text)
            d.say_text = say
            for k in "15x":
                await d.press_quick(k)
            return sent
        sent = asyncio.run(go())
        self.assertEqual(len(sent), 2)  # 未映射的键不发
        self.assertIn("检查", sent[0])
        self.assertIn("撤销", sent[1])
        self.assertEqual(asyncio.run(go({"1": "跑一下测试"}))[0], "跑一下测试")

    def test_quick_key_failure_is_visible(self):
        async def go():
            d = make_device()

            async def down(text):
                raise OSError("linx unreachable")
            d.say_text = down
            lines = []
            orig, device.log = device.log, lambda *a: lines.append(" ".join(map(str, a)))
            try:
                await d.press_quick("1")
            finally:
                device.log = orig
            return lines
        self.assertTrue(any("✘" in l and "再按一次" in l for l in asyncio.run(go())))
        self.assertEqual([device.evdev_action(c) for c in (57, 2, 6, 79, 30)],
                         ["toggle", "1", "5", "1", None])

    def test_muted_device_shows_but_does_not_speak(self):
        class Stream:
            def __init__(self, msgs):
                self.msgs = msgs

            def __aiter__(self):
                return self

            async def __anext__(self):
                if not self.msgs:
                    raise StopAsyncIteration
                return self.msgs.pop(0)

        async def go():
            d = make_device()
            played = []
            d.player.write = played.append
            d.ensure = lambda: asyncio.sleep(0)
            self.assertTrue(d.toggle_mute())
            await d.announce("任务完成")
            await d._recv(Stream([b"\x00" * 640]))
            return d, played
        d, played = asyncio.run(go())
        self.assertEqual(d.ws.json, [])  # 回执不送去合成
        self.assertEqual(played, [])     # 平台下行的语音也不放
        self.assertFalse(d.toggle_mute())


class SecondFrontendTest(unittest.TestCase):
    """TG 入口（#5）复用 Device：整段语音送上去、跟随听到 / 回话、自己的令牌文件。"""

    def test_say_audio_sends_one_manual_listen_turn(self):
        async def go():
            d = make_device()
            d.ensure = lambda: asyncio.sleep(0)
            await d.say_audio(b"x" * (device.FRAME_BYTES * 3 + 7), pace=0)
            return d
        d = asyncio.run(go())
        states = [__import__("json").loads(m).get("state") for _, m in d.ws.json]
        self.assertEqual(states, ["start", "stop"])
        self.assertEqual(len(d.ws.frames), 3)
        self.assertEqual(d.pending_tools, 0)

    def test_device_reports_heard_and_said_text_to_other_frontends(self):
        class Stream:
            def __init__(self, msgs):
                self.msgs = msgs

            def __aiter__(self):
                return self

            async def __anext__(self):
                if not self.msgs:
                    raise StopAsyncIteration
                return self.msgs.pop(0)
        J = __import__("json").dumps

        async def go():
            d = make_device()
            seen = []
            d.on_event = lambda k, t: seen.append((k, t))
            d.host = type("H", (), {"post": lambda *a, **k: None})()
            await d._recv(Stream([J({"type": "stt", "text": "进度"}),
                                  J({"type": "tts", "state": "sentence_start", "text": "目前空闲"})]))
            return seen
        self.assertEqual(asyncio.run(go()), [("stt", "进度"), ("say", "目前空闲")])

    def test_each_device_profile_keeps_its_own_token_file(self):
        async def go():  # Python 3.9：Device 里的 asyncio.Lock 要在事件循环里建
            d = device.Device({"device": {"mac": "02:00:00:00:00:09", "audio_out": ["true"],
                                          "state": "linx-tg.json"}}, host=None)
            return d.state, make_device().state
        self.assertEqual(asyncio.run(go()), ("linx-tg.json", "linx.json"))


class PanelKeyTest(unittest.TestCase):
    """面板接管说话按键（#40）：面板的键和终端的键走同一组动作；录音状态回报给面板。"""

    def test_panel_keys_drive_the_same_actions_as_terminal_keys(self):
        async def go():
            d = make_device()
            done = []

            async def talk(tryout=None):
                done.append("talk")

            async def quick(k):
                done.append("quick " + k)
            d.toggle_talk, d.press_quick = talk, quick
            for key in ("talk", "3", "mute", "bogus"):
                job = d.on_host("key", {"key": key})
                if job is not None:
                    await job
            return d, done
        d, done = asyncio.run(go())
        self.assertEqual(done, ["talk", "quick 3"])
        self.assertTrue(d.muted)

    def test_mic_state_is_reported_while_talking(self):
        class H:
            def __init__(self):
                self.posts = []

            def post(self, path, body=None, timeout=12):
                self.posts.append((path, body))
                return {"ok": True}

        async def go():
            d = make_device()
            d.host = H()
            d.ensure = lambda: asyncio.sleep(0)
            await d.toggle_talk()
            await asyncio.sleep(0.1)
            await d.toggle_talk()
            return d.host
        h = asyncio.run(go())
        deadline = time.time() + 3
        while time.time() < deadline and len([p for p in h.posts if p[0] == "/api/device"]) < 2:
            time.sleep(0.05)
        states = [b["state"] for p, b in h.posts if p == "/api/device"]
        self.assertEqual(states, ["recording", "recognizing"])


class TriggerPickTest(unittest.TestCase):
    """launchd 常驻（#40）：没有终端时不读 stdin，说话按键交给面板。"""

    def test_no_terminal_means_panel_keys_only(self):
        prof = {"trigger": "stdin"}
        self.assertIs(device.pick_trigger(prof, isatty=lambda: True), device.stdin_trigger)
        self.assertIsNone(device.pick_trigger(prof, isatty=lambda: False))
        self.assertIs(device.pick_trigger({"trigger": "evdev"}, isatty=lambda: False), device.evdev_trigger)


class TryoutTurnTest(unittest.TestCase):
    """试音（#40）：试音那一轮的连接上，工具调用只记录、不执行；别的交互一开始就收掉这条连接，
    上一句迟到的调用既不会执行，也掐不断、记不到新一轮头上。"""
    T = {"cond": "quiet", "idx": 5}

    class H:
        def __init__(self):
            self.posts = []

        def post(self, path, body=None, timeout=12):
            self.posts.append((path, body))
            return {"ok": True, "say": "好的"}

    class Ws(FakeWs):
        def __init__(self):
            super().__init__()
            self.closed, self.state = False, type("S", (), {"name": "OPEN"})()

        async def send(self, m):
            if self.closed:
                raise ConnectionError("closed")
            await super().send(m)

        async def close(self):
            self.closed, self.state.name = True, "CLOSED"

    def device(self):
        d = make_device()
        d.host, d.ws, d.tryout_wait = self.H(), self.Ws(), (0.3, 0.3)

        async def ensure():
            if d.ws is None or d.ws.closed:
                d.ws = self.Ws()
        d.ensure = ensure
        return d

    @staticmethod
    def posted(d, path):
        return [b for p, b in list(d.host.posts) if p == path]

    async def settle(self, d, path):
        for _ in range(60):
            if self.posted(d, path):
                return
            await asyncio.sleep(0.05)

    def test_tryout_turn_records_tool_without_executing(self):
        J = __import__("json")

        async def go():
            d = self.device()
            await d.toggle_talk(tryout=self.T)
            await asyncio.sleep(0.05)
            await d.toggle_talk()
            t1 = d.ws
            d._heard("嗯，停下。")
            await d._tool(7, {"name": "self.code.cancel", "arguments": {}})
            reply = J.loads(t1.json[-1][1])["payload"]["result"]["content"][0]["text"]
            await self.settle(d, "/api/tryout")
            await d.say_text("进度怎么样了")  # 试音那轮之后照常执行
            await d._tool(8, {"name": "self.code.status", "arguments": {}})
            return d, t1, reply
        d, t1, reply = asyncio.run(go())
        self.assertEqual(self.posted(d, "/api/cancel"), [])
        self.assertTrue(self.posted(d, "/api/status"))
        body = self.posted(d, "/api/tryout")[0]
        self.assertEqual((body["cond"], body["idx"], body["hyp"], body["tool"]), ("quiet", 5, "嗯，停下。", "self.code.cancel"))
        self.assertIn("没有执行", reply)
        self.assertTrue(t1.closed)  # 下一句用新会话，不被上一句的上下文带偏

    def test_late_tool_call_of_tryout_cannot_execute_or_cut_next_turn(self):
        async def go():
            d = self.device()
            await d.toggle_talk(tryout=self.T)
            await asyncio.sleep(0.05)
            await d.toggle_talk()
            t1 = d.ws
            d._heard("撤销刚才的改动")
            await d.toggle_talk()  # 识别完马上在面板上开讲真任务
            t2 = d.ws
            await d._tool(9, {"name": "self.code.undo", "arguments": {}}, ws=t1)  # 上一句迟到的工具调用
            await asyncio.sleep(0.8)  # 超过试音的等待上限
            during = (t2 is not t1, t2.closed, d.mic is not None)
            await d.toggle_talk()
            await d._tool(10, {"name": "self.code.status", "arguments": {}}, ws=t2)
            return d, during
        d, during = asyncio.run(go())
        self.assertEqual(during, (True, False, True))  # 新一轮在新连接上，录音没被掐断
        self.assertEqual(self.posted(d, "/api/undo"), [])
        self.assertTrue(self.posted(d, "/api/status"))
        self.assertEqual([b["tool"] for b in self.posted(d, "/api/tryout")], [None])

    def test_tryout_waits_while_demo_turn_may_still_call_tools(self):
        async def go():
            d = self.device()
            await d.toggle_talk()  # 面板上说一句真命令
            await asyncio.sleep(0.05)
            await d.toggle_talk()
            w0 = d.ws
            d._heard("把 README 里的错字改掉")
            await d.toggle_talk(tryout=self.T)  # 工具调用还在路上就切到试音按下
            refused = (d.mic is None, d.ws is w0, dict(d.tryouts))
            await d._tool(12, {"name": "self.code.dispatch", "arguments": {"text": "改错字"}}, ws=w0)
            await asyncio.sleep(0.1)
            return d, refused
        d, refused = asyncio.run(go())
        self.assertEqual(refused, (True, True, {}))  # 不开口、不借演示连接
        self.assertIn({"state": "busy"}, self.posted(d, "/api/device"))
        self.assertTrue(self.posted(d, "/api/dispatch"))  # 演示那句照常执行

    def test_quiet_demo_connection_is_not_reused_for_tryout(self):
        async def go():
            d = self.device()
            w0 = d.ws  # 演示那句早已结束、连接还没到空闲断开
            await d.toggle_talk(tryout=self.T)
            await asyncio.sleep(0.01)  # 旧连接的关闭不阻塞开口
            fresh = (d.ws is not w0, w0.closed, d.ws in d.tryouts)
            await d.toggle_talk()
            return fresh
        self.assertEqual(asyncio.run(go()), (True, True, True))  # 试音一句用新会话，不被演示上下文带偏

    def test_next_press_waits_for_pending_tryout_result(self):
        async def go():
            d = self.device()
            d.tryout_wait = (0.5, 0.5)
            await d.toggle_talk(tryout=self.T)
            await asyncio.sleep(0.05)
            await d.toggle_talk()
            t1 = d.ws
            d._heard("进度怎么样了")
            await asyncio.sleep(0.1)
            early_idle = {"state": "idle"} in self.posted(d, "/api/device")
            await d.toggle_talk(tryout={"cond": "quiet", "idx": 6})  # 结果还没出就按下一句
            refused = (d.mic is None, d.ws is t1)
            await d._tool(13, {"name": "self.code.status", "arguments": {}}, ws=t1)
            await self.settle(d, "/api/tryout")
            await asyncio.sleep(0.1)
            return d, early_idle, refused
        d, early_idle, refused = asyncio.run(go())
        self.assertFalse(early_idle)  # 识别出字时按钮还不能回到可说
        self.assertEqual(refused, (True, True))
        self.assertEqual([(b["idx"], b["tool"]) for b in self.posted(d, "/api/tryout")], [(5, "self.code.status")])
        self.assertIn({"state": "idle"}, self.posted(d, "/api/device"))  # 结果出来才回到可说

    def test_empty_tryout_turn_reports_result_and_idle(self):
        async def go():
            d = self.device()
            await d.toggle_talk(tryout=self.T)
            await asyncio.sleep(0.05)
            await d.toggle_talk()  # 小声 / 气声：平台没听出字
            await self.settle(d, "/api/tryout")
            await asyncio.sleep(0.1)
            return d
        d = asyncio.run(go())
        self.assertIsNone(self.posted(d, "/api/tryout")[0]["hyp"])
        self.assertIn({"state": "idle"}, self.posted(d, "/api/device"))  # 面板按钮回到可说

    def test_failed_tryout_turn_leaves_later_requests_real(self):
        async def go():
            d = self.device()
            await d.toggle_talk(tryout=self.T)
            await asyncio.sleep(0.05)

            async def broken(m):
                raise ConnectionError("reset")
            d.ws.send = broken
            await d.toggle_talk()  # 松键时连接断了：这一轮失败
            await d.say_text("检查一下代码有没有逻辑问题")  # 之后按快捷键
            await d._tool(11, {"name": "self.code.dispatch", "arguments": {"text": "检查一下代码"}})
            await self.settle(d, "/api/tryout")
            return d
        d = asyncio.run(go())
        self.assertTrue(self.posted(d, "/api/dispatch"))
        self.assertEqual(len(self.posted(d, "/api/tryout")), 1)


class EarconTest(unittest.TestCase):
    def test_tone_is_short_audible_pcm_with_soft_edges(self):
        pcm = device.tone(880, 90)
        n = 16000 * 90 // 1000
        self.assertEqual(len(pcm), n * 2)
        samples = struct.unpack(f"<{n}h", pcm)
        self.assertGreater(max(samples), 3000)
        self.assertLess(abs(samples[0]), 200)
        self.assertLess(abs(samples[-1]), 200)
        self.assertNotEqual(device.EARCON_START, device.EARCON_STOP)


if __name__ == "__main__":
    unittest.main()
