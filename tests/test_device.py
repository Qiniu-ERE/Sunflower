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
