import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from sunflower import service  # noqa: E402


class FakeClock:
    def __init__(self):
        self.t, self.sleeps = 0.0, []

    def time(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s


class PlistTest(unittest.TestCase):
    def test_plist_keeps_alive_without_secrets(self):
        p = service.plist("/usr/bin/python3", pathlib.Path("/h/.sunflower/app"),
                          pathlib.Path("/h/.sunflower/logs"), "/opt/homebrew/bin:/usr/bin")
        self.assertEqual(p["Label"], service.LABEL)
        self.assertTrue(p["KeepAlive"])
        self.assertTrue(p["RunAtLoad"])
        self.assertGreaterEqual(p["ThrottleInterval"], 5)
        self.assertEqual(p["ProgramArguments"], ["/usr/bin/python3", "-u", "-m", "sunflower.service", "run"])
        self.assertEqual(p["WorkingDirectory"], "/h/.sunflower/app")
        self.assertTrue(p["StandardOutPath"].endswith("logs/host.log"))
        self.assertEqual(p["StandardErrorPath"], p["StandardOutPath"])
        # 密钥只能运行时从钥匙串取，plist 里只允许这几个变量
        self.assertEqual(set(p["EnvironmentVariables"]), {"PATH", "PYTHONUNBUFFERED", "SUNFLOWER_HOME"})

    def test_service_path_includes_tool_dirs(self):
        which = {"codex": "/n/v22/bin/codex", "git": "/opt/homebrew/bin/git"}.get
        dirs = service.service_path(which).split(":")
        self.assertIn("/n/v22/bin", dirs)
        self.assertIn("/opt/homebrew/bin", dirs)
        self.assertIn("/usr/bin", dirs)
        self.assertEqual(len(dirs), len(set(dirs)))


class DrainTest(unittest.TestCase):
    def test_drain_waits_until_idle(self):
        seq = iter([{"busy": True}, {"busy": True}, {"busy": False}])
        clk = FakeClock()
        self.assertTrue(service.drain(lambda: next(seq), wait=60, poll=5, clock=clk))
        self.assertEqual(clk.sleeps, [5, 5])

    def test_drain_gives_up_while_busy(self):
        clk = FakeClock()
        self.assertFalse(service.drain(lambda: {"busy": True}, wait=0, poll=5, clock=clk))
        self.assertEqual(clk.sleeps, [])

    def test_drain_host_down_is_ok(self):
        self.assertTrue(service.drain(lambda: None, wait=0, clock=FakeClock()))


class DriftTest(unittest.TestCase):
    def test_all_in_sync(self):
        self.assertEqual(service.drift("abc", "abc", "abc", "abc"), [])

    def test_running_differs_from_deployed(self):
        msgs = service.drift(running="old", deployed="new", main="new", device="new")
        self.assertEqual(len(msgs), 1)
        self.assertIn("重启", msgs[0])

    def test_deployed_behind_main(self):
        msgs = service.drift(running="old", deployed="old", main="new", device="old")
        self.assertTrue(any("部署" in m for m in msgs))

    def test_device_on_old_code(self):
        msgs = service.drift(running="new", deployed="new", main="new", device="old")
        self.assertEqual(len(msgs), 1)
        self.assertIn("设备", msgs[0])

    def test_no_device_seen_is_not_drift(self):
        self.assertEqual(service.drift("abc", "abc", "abc", None), [])


class RunTest(unittest.TestCase):
    def test_run_injects_keychain_env_and_execs_host(self):
        calls = {}
        conf = {"profile": "dev-single-mac", "channel": "icodeeasy",
                "keychain_env": {"OPENAI_API_KEY": "sunflower-icodeeasy"}}

        def secret(svc):
            calls.setdefault("svc", []).append(svc)
            return "s3cr3t"

        def execve(path, argv, env):
            calls["argv"], calls["env"] = argv, env

        service.run(conf, secret=secret, execve=execve, python="/usr/bin/python3", environ={"PATH": "/usr/bin"})
        self.assertEqual(calls["svc"], ["sunflower-icodeeasy"])
        self.assertEqual(calls["argv"], ["/usr/bin/python3", "-u", "-m", "sunflower.host",
                                         "--profile", "dev-single-mac", "--channel", "icodeeasy"])
        self.assertEqual(calls["env"]["OPENAI_API_KEY"], "s3cr3t")
        self.assertNotIn("s3cr3t", " ".join(calls["argv"]))

    def test_run_without_channel_uses_profile_default(self):
        calls = {}
        service.run({"profile": "dev-single-mac"}, secret=None,
                    execve=lambda p, argv, env: calls.update(argv=argv), python="py", environ={})
        self.assertNotIn("--channel", calls["argv"])


class RotateTest(unittest.TestCase):
    def test_rotate_only_over_limit(self):
        d = pathlib.Path(tempfile.mkdtemp())
        log = d / "host.log"
        log.write_text("x" * 10)
        service.rotate(log, limit=100)
        self.assertTrue(log.exists())
        log.write_text("x" * 200)
        service.rotate(log, limit=100)
        self.assertFalse(log.exists())
        self.assertEqual((d / "host.log.1").stat().st_size, 200)


if __name__ == "__main__":
    unittest.main()
