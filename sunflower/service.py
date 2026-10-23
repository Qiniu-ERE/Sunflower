"""主机服务维护：launchd 常驻、从固定提交部署、不打断任务地重启、版本漂移可见。

    python3 -m sunflower.service install [--profile dev-single-mac] [--channel X] [--keychain-env VAR=服务名]
    python3 -m sunflower.service deploy  [--ref origin/main] [--wait 600 | --force]
    python3 -m sunflower.service restart [--wait 600 | --force]
    python3 -m sunflower.service status
    python3 -m sunflower.service logs [-n 50]
    python3 -m sunflower.service uninstall

主机从部署目录 ~/.sunflower/app（开发仓的 detached worktree）启动，开发仓切分支不影响在跑的服务。
密钥不进 plist：`run` 在启动时从钥匙串取，再 exec 主机。
"""
import argparse
import json
import os
import pathlib
import plistlib
import shutil
import subprocess
import sys
import time
import urllib.request

from . import config

LABEL = "com.sunflower.host"
APP = config.HOME / "app"
LOGS = config.HOME / "logs"
CONF = "service.json"
PLIST = pathlib.Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
LOG_LIMIT = 5 * 1024 * 1024
BASE_PATH = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"]


def service_path(which=shutil.which):
    """launchd 的 PATH 只有系统目录；把 codex / git 所在目录放到前面（codex 常在 nvm 下）。"""
    dirs = [os.path.dirname(p) for p in (which("codex"), which("git")) if p]
    out = []
    for d in dirs + BASE_PATH:
        if d not in out:
            out.append(d)
    return ":".join(out)


def plist(python, app, logs, path_env):
    log = str(pathlib.Path(logs) / "host.log")
    return {
        "Label": LABEL,
        "ProgramArguments": [python, "-u", "-m", "sunflower.service", "run"],
        "WorkingDirectory": str(app),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
        "StandardOutPath": log,
        "StandardErrorPath": log,
        "EnvironmentVariables": {"PATH": path_env, "PYTHONUNBUFFERED": "1",
                                 "SUNFLOWER_HOME": str(config.HOME)},
    }


def keychain(svc):
    r = subprocess.run(["/usr/bin/security", "find-generic-password", "-a", os.environ.get("USER", ""),
                        "-s", svc, "-w"], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"钥匙串里没有服务「{svc}」：先执行 security add-generic-password -a $USER -s {svc} -w")
    return r.stdout.strip()


def run(conf, secret=keychain, execve=os.execve, python=sys.executable, environ=None):
    """launchd 入口：注入钥匙串里的环境变量，然后 exec 主机（pid 不变，launchd 直接看护主机进程）。"""
    env = dict(os.environ if environ is None else environ)
    for var, svc in (conf.get("keychain_env") or {}).items():
        env[var] = secret(svc)
    argv = [python, "-u", "-m", "sunflower.host", "--profile", conf.get("profile", "dev-single-mac")]
    if conf.get("channel"):
        argv += ["--channel", conf["channel"]]
    execve(python, argv, env)


def drain(health, wait=600, poll=5, clock=time):
    """等主机空闲。主机没起来也算可以重启；超过 wait 秒仍忙返回 False。"""
    start = clock.time()
    while True:
        h = health()
        if not h or not h.get("busy"):
            return True
        if clock.time() - start >= wait:
            return False
        clock.sleep(poll)


def drift(running, deployed, main, device=None):
    """比对四个提交，返回需要处理的事项；空列表表示一致。"""
    msgs = []
    if running and deployed and not _same(running, deployed):
        msgs.append(f"主机在跑 {running[:7]}，部署目录是 {deployed[:7]}：需要重启（service restart）")
    if deployed and main and not _same(deployed, main):
        msgs.append(f"部署目录 {deployed[:7]} 与 main {main[:7]} 不一致：需要部署（service deploy）")
    if device and deployed and not _same(device, deployed):
        msgs.append(f"设备进程在跑 {device[:7]}：在设备终端 Ctrl-C 后重新启动")
    return msgs


def _same(a, b):
    n = min(len(a), len(b))
    return a[:n] == b[:n]


def rotate(log, limit=LOG_LIMIT):
    log = pathlib.Path(log)
    if log.exists() and log.stat().st_size > limit:
        os.replace(log, log.with_name(log.name + ".1"))


# -- 以下是真机操作（launchctl / git / HTTP），由 status/restart 等子命令调用 ----------------

def _uid_target():
    return f"gui/{os.getuid()}"


def _git(*args, cwd=config.ROOT):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout.strip()


def _health(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3) as r:
            return json.loads(r.read())
    except Exception:
        return None


def _conf():
    return config.read_state(CONF, {"profile": "dev-single-mac"})


def _port(conf):
    return int(config.load_profile(conf.get("profile", "dev-single-mac"))["host"].get("port", 8787))


def _loaded():
    return subprocess.run(["launchctl", "print", f"{_uid_target()}/{LABEL}"],
                          capture_output=True, text=True).returncode == 0


def checkout(ref):
    """把部署目录切到 ref（默认 origin/main）。部署目录有本地改动时拒绝。"""
    subprocess.run(["git", "-C", str(config.ROOT), "fetch", "-q", "origin"], check=False)
    sha = _git("rev-parse", ref)
    if not (APP / ".git").exists():
        _git("worktree", "add", "-q", "--detach", str(APP), sha)
    else:
        if _git("status", "--porcelain", cwd=APP):
            raise SystemExit(f"{APP} 有本地改动，拒绝部署（部署目录只读，改代码去开发仓走 PR）")
        _git("checkout", "-q", "--detach", sha, cwd=APP)
    env = APP / ".env"
    if not env.exists():  # 密钥文件留在开发仓（不入库），部署目录用软链接
        repo = pathlib.Path(_git("rev-parse", "--path-format=absolute", "--git-common-dir")).parent
        env.symlink_to(repo / ".env")
    return sha


def restart(conf, wait=600, force=False):
    port = _port(conf)
    if not force and not drain(lambda: _health(port), wait=wait):
        print(f"主机正在执行任务，等了 {wait} s 仍未空闲，本次没有重启（--force 可强制）")
        return False
    want = _git("rev-parse", "HEAD", cwd=APP)
    rotate(LOGS / "host.log")
    subprocess.run(["launchctl", "kickstart", "-k", f"{_uid_target()}/{LABEL}"], check=True)
    for _ in range(40):
        h = _health(port)
        if h and h.get("commit") and _same(h["commit"], want):
            print(f"✔ 主机已重启：pid {h.get('pid')}，提交 {want[:7]}，渠道 {h.get('channel')}")
            return True
        time.sleep(0.5)
    print(f"✘ 20 s 内主机没有在 {want[:7]} 上起来，最近日志：")
    logs(20)
    return False


def logs(n=50):
    p = LOGS / "host.log"
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()[-n:] if p.exists() else ["（无日志）"]
    print("\n".join(lines))


def status(conf):
    h = _health(_port(conf))
    deployed = _git("rev-parse", "HEAD", cwd=APP) if (APP / ".git").exists() else None
    try:
        main = _git("rev-parse", "origin/main")
    except subprocess.CalledProcessError:
        main = None
    dev = (h or {}).get("device") or {}
    print(f"launchd   {'已加载' if _loaded() else '未安装'}（{LABEL}）")
    print(f"主机      {'无响应' if not h else ('执行中' if h.get('busy') else '空闲')}"
          f"  pid={(h or {}).get('pid')}  渠道={(h or {}).get('channel')}  提交={((h or {}).get('commit') or '?')[:7]}")
    print(f"部署目录  {APP}  提交={(deployed or '?')[:7]}；origin/main={(main or '?')[:7]}")
    if dev:
        ago = int(time.time() - dev.get("seen", 0))
        print(f"设备      提交={dev.get('commit', '?')[:7]}  最近连接 {ago} s 前")
    msgs = drift((h or {}).get("commit"), deployed, main, dev.get("commit"))
    print("\n".join("⚠ " + m for m in msgs) if msgs else "✔ 一致")
    return not msgs


def install(conf):
    port = _port(conf)
    if not _loaded() and _health(port):
        raise SystemExit(f"127.0.0.1:{port} 已被手动启动的主机占用：先停掉它，再 install")
    config.write_state(CONF, conf)
    sha = checkout(conf.get("ref", "origin/main"))
    LOGS.mkdir(parents=True, exist_ok=True)
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    PLIST.write_bytes(plistlib.dumps(plist(sys.executable, APP, LOGS, service_path())))
    subprocess.run(["launchctl", "bootout", f"{_uid_target()}/{LABEL}"], capture_output=True)
    subprocess.run(["launchctl", "bootstrap", _uid_target(), str(PLIST)], check=True)
    for _ in range(40):
        h = _health(port)
        if h and _same(h.get("commit") or "", sha):
            print(f"✔ 已安装：{PLIST}；主机 pid {h.get('pid')} 跑在 {sha[:7]}，日志 {LOGS / 'host.log'}")
            return
        time.sleep(0.5)
    logs(20)
    raise SystemExit("✘ 安装后 20 s 内主机没有起来")


def uninstall():
    subprocess.run(["launchctl", "bootout", f"{_uid_target()}/{LABEL}"], capture_output=True)
    if PLIST.exists():
        PLIST.unlink()
    print(f"已卸载 {LABEL}（部署目录 {APP} 保留）")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sunflower.service")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("install")
    p.add_argument("--profile", default="dev-single-mac")
    p.add_argument("--channel")
    p.add_argument("--keychain-env", action="append", default=[], metavar="VAR=服务名")
    p.add_argument("--ref", default="origin/main", help="部署哪个提交（试装分支时用 HEAD）")
    for name in ("deploy", "restart"):
        p = sub.add_parser(name)
        p.add_argument("--wait", type=int, default=600, help="等主机空闲的秒数；0 = 忙就跳过")
        p.add_argument("--force", action="store_true", help="不等任务结束，直接重启")
        if name == "deploy":
            p.add_argument("--ref", default="origin/main")
    sub.add_parser("status")
    sub.add_parser("run")
    sub.add_parser("uninstall")
    p = sub.add_parser("logs")
    p.add_argument("-n", type=int, default=50)
    a = ap.parse_args(argv)

    if a.cmd == "run":
        return run(_conf())
    if a.cmd == "install":
        kenv = dict(x.split("=", 1) for x in a.keychain_env)
        return install({"profile": a.profile, "channel": a.channel, "keychain_env": kenv, "ref": a.ref})
    if a.cmd == "uninstall":
        return uninstall()
    if a.cmd == "logs":
        return logs(a.n)
    conf = _conf()
    if a.cmd == "status":
        sys.exit(0 if status(conf) else 1)
    if not _loaded():
        raise SystemExit("服务未安装：先 python3 -m sunflower.service install")
    if a.cmd == "deploy":
        # 先等空闲再换代码：主机运行中会按请求读取 web/ 下的文件
        if not a.force and not drain(lambda: _health(_port(conf)), wait=a.wait):
            print(f"主机正在执行任务，本次没有部署；空闲后再跑 service deploy（或 --force）")
            sys.exit(1)
        sha = checkout(a.ref)
        print(f"部署目录 → {sha[:7]}")
        sys.exit(0 if restart(conf, force=True) else 1)
    sys.exit(0 if restart(conf, wait=a.wait, force=a.force) else 1)


if __name__ == "__main__":
    main()
