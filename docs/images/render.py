"""重渲染 README 里的三张截图：内容全部取自一次真实会话，不手写。

    # 1. 会话结束后、主机重启前，把主机的回放缓冲（最近 300 条事件）存下来
    curl -sN --max-time 4 'http://127.0.0.1:8787/events?replay=1' > /tmp/replay.sse
    # 2. 面板两张：只回放 [起, 止] 时间戳（事件里的 ts）之间的事件，用当前 panel.html 截 1920×1080 和 1024×600
    python3 docs/images/render.py panel /tmp/replay.sse <起ts> <止ts> docs/images
    # 3. 设备终端一张：取 ~/.sunflower/logs/device.log 的 [起行, 止行]，会话 id 只留前缀
    python3 docs/images/render.py terminal ~/.sunflower/logs/device.log <起行> <止行> docs/images/device-terminal.png

依赖 Playwright（pip install playwright && playwright install chromium），只是出图工具，不进 requirements.txt。
截图时关掉入场动画和平滑滚动并滚到底部，仓库里的 panel.html 不改。
"""
import html
import http.server
import json
import pathlib
import re
import sys
import threading

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
PANEL = ROOT / "sunflower" / "web" / "panel.html"
SIZES = (("panel-1080p", 1920, 1080), ("panel-7in", 1024, 600))


def read_sse(path, t0, t1):
    events = []
    for block in pathlib.Path(path).read_text(encoding="utf-8").split("\n\n"):
        name, data = "message", []
        for line in block.splitlines():
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data.append(line[5:].lstrip())
        if data and t0 <= json.loads("\n".join(data)).get("ts", 0) <= t1:
            events.append((name, "\n".join(data)))
    return events


def panel(dump, t0, t1, outdir):
    events = read_sse(dump, float(t0), float(t1))
    page = PANEL.read_text(encoding="utf-8").replace(
        "</head>", "<style>*{animation:none!important;scroll-behavior:auto!important}</style></head>")
    done = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *args):  # noqa: A002 —— 与基类同名
            pass

        def do_GET(self):
            self.send_response(200)
            if self.path.startswith("/events"):
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                for name, data in events:
                    self.wfile.write(f"event: {name}\ndata: {data}\n\n".encode())
                self.wfile.flush()
                done.wait(30)  # 连接不断，面板就不会显示「离线」
                return
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(page.encode())

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, w, h in SIZES:
            pg = browser.new_page(viewport={"width": w, "height": h})
            pg.goto(f"http://127.0.0.1:{srv.server_address[1]}/")
            pg.wait_for_timeout(2500)
            pg.evaluate("document.querySelectorAll('.scroll').forEach(e => e.scrollTop = e.scrollHeight)")
            pg.wait_for_timeout(300)
            pg.screenshot(path=str(pathlib.Path(outdir) / f"{name}.png"))
            pg.close()
        browser.close()
    done.set()
    srv.shutdown()
    print(f"回放 {len(events)} 条事件 → {outdir}")


TERM_CSS = """body{margin:0;background:#0d1117}
.win{width:1200px;background:#161b22;border-radius:10px;overflow:hidden;font:22px/1.95 "PingFang SC",sans-serif;color:#e6edf3}
.bar{height:38px;background:#21262d;display:flex;align-items:center;gap:8px;padding:0 14px;color:#8b949e;font-size:15px}
.dot{width:12px;height:12px;border-radius:50%} .t{margin-left:12px} .body{padding:14px 22px 20px}
.ts,code{font-family:Menlo,monospace} .ts{color:#8b949e} code{font-size:.95em}
.tool{color:#79c0ff} .say{color:#e3b341} .ack{color:#56d364;font-weight:700} .dim{color:#8b949e}"""


def terminal(log, first, last, out):
    rows = []
    for line in pathlib.Path(log).read_text(encoding="utf-8").splitlines()[int(first) - 1:int(last)]:
        ts, msg = re.match(r"(\[\d\d:\d\d:\d\d\]) (.*)", line).groups()
        msg = re.sub(r"(linx session \w{5})\w+", r"\1…", msg)  # 会话 id 只留前缀
        if msg.startswith("工具"):
            head, _, args = msg.partition(": ")
            body = f'<span class="tool">{html.escape(head)}: <code>{html.escape(args)}</code></span>'
        elif msg.startswith("linx session"):
            body = f'<span class="dim"><code>{html.escape(msg)}</code></span>'
        else:
            cls = "ack" if msg.startswith("回执") else "say" if msg.startswith("播报") else "dim" if msg.startswith("空闲") else ""
            body = f'<span class="{cls}">{html.escape(msg)}</span>'
        rows.append(f'<div><span class="ts">{ts}</span> {body}</div>')
    dots = "".join(f'<span class="dot" style="background:{c}"></span>' for c in ("#ff5f56", "#ffbd2e", "#27c93f"))
    page = (f'<!doctype html><meta charset="utf-8"><style>{TERM_CSS}</style><div class="win"><div class="bar">{dots}'
            f'<span class="t">python3 -m sunflower.device --profile dev-single-mac</span></div>'
            f'<div class="body">{"".join(rows)}</div></div>')
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(viewport={"width": 1200, "height": 800}, device_scale_factor=2)
        pg.set_content(page)
        pg.locator(".win").screenshot(path=out)
        browser.close()
    print(f"{len(rows)} 行 → {out}")


if __name__ == "__main__":
    cmd, *args = sys.argv[1:] or ["-h"]
    if cmd == "panel" and len(args) == 4:
        panel(*args)
    elif cmd == "terminal" and len(args) == 4:
        terminal(*args)
    else:
        sys.exit(__doc__)
