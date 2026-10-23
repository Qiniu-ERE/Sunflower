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
