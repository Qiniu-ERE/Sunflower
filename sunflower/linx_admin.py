"""灵矽平台侧整备：按需创建/销毁智能体、预注册软设备、OTA 取 WebSocket 令牌。

    python3 -m sunflower.linx_admin up      [--profile dev-single-mac]
    python3 -m sunflower.linx_admin status
    python3 -m sunflower.linx_admin down    # 删除智能体（设备随之解绑）

设备身份只是 profile 里的一个 MAC 字符串：同一个名额可在 Mac / 树莓派之间迁移。
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid

from . import config

API = "https://xrobo.qiniu.com"
OTA = "https://xrobo.qiniuapi.com/v1/ota/"
STATE = "linx.json"
AGENT_NAME = "sunflower-voice-coder"
LLM_DEEPSEEK_V4_FLASH = "f3626c105383d71654a57f2bb8a973f3"

SYSTEM_PROMPT = """你是「太阳花」语音编程助手，住在一台带屏幕的小设备里。你自己不看代码、不写代码，所有和代码有关的事都交给编程代理 Codex，它已经打开了用户的项目，知道代码在哪。
工具选择（只看用户意图，不要追问细节）：
1. self.code.dispatch：凡是涉及代码、项目、测试、bug、功能、检查、审查、解释、重构、提交的请求，一律立刻调用，把用户原话完整放进 text（口头禅和语气词可以保留，不要改写）。
   例：「代码有没有逻辑问题」「跑一下测试把失败的修好」「看看项目是干什么的」「加个删除命令」「这个函数写得对吗」→ 全部 dispatch。
2. self.code.status：只有用户明确问「进度怎么样 / 好了没 / 现在在干什么」时才调用。
3. self.code.cancel：用户说停下、取消、别做了。
4. self.code.undo：用户说撤销、回滚刚才的改动。
硬性规则：
- 不确定时选 dispatch，绝不反问「是什么代码、在哪里」——Codex 会自己找。
- 工具返回后用一句口语转述，不超过 25 个字，不读代码和路径。
- 只有完全与编程无关的闲聊才直接简短回答。"""


class LinxError(RuntimeError):
    pass


def _call(method, url, key=None, body=None, headers=None):
    h = {"Content-Type": "application/json"}
    if key:
        h["Authorization"] = "Bearer " + key
    h.update(headers or {})
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        raise LinxError(f"{method} {url} -> HTTP {e.code}: {e.read()[:300]!r}") from e
    except urllib.error.URLError as e:
        raise LinxError(f"{method} {url} unreachable: {e.reason} (检查网络/热点)") from e
    return json.loads(raw or b"null")


def _ok(resp, what):
    if isinstance(resp, dict) and resp.get("code") not in (0, None):
        raise LinxError(f"{what} failed: code={resp.get('code')} msg={resp.get('msg')}")
    return resp


def find_agent(key, name=AGENT_NAME):
    resp = _ok(_call("GET", f"{API}/xiaozhi/agent/list?limit=1000", key), "list agents")
    for a in resp.get("data") or []:
        if a.get("agentName") == name:
            return a
    return None


def ensure_agent(key, st):
    agent = find_agent(key)
    if agent is None and st.get("agent_id"):
        # 兼容探针阶段建的智能体：按 id 找回并改名
        resp = _ok(_call("GET", f"{API}/xiaozhi/agent/list?limit=1000", key), "list agents")
        agent = next((a for a in resp.get("data") or [] if a["id"] == st["agent_id"]), None)
    if agent is None:
        resp = _ok(_call("POST", f"{API}/xiaozhi/agent", key, {
            "agentName": AGENT_NAME, "assistantName": "太阳花",
            "llmModelId": LLM_DEEPSEEK_V4_FLASH, "intentModelId": "Intent_function_call",
            "memModelId": "Memory_nomem", "systemPrompt": SYSTEM_PROMPT}), "create agent")
        agent_id = resp["data"]
        print(f"created agent {agent_id}")
    else:
        agent_id = agent["id"]
        print(f"reuse agent {agent_id}")
    _ok(_call("PUT", f"{API}/xiaozhi/agent/{agent_id}", key, {
        "agentName": AGENT_NAME, "assistantName": "太阳花", "systemPrompt": SYSTEM_PROMPT,
        "llmModelId": LLM_DEEPSEEK_V4_FLASH, "intentModelId": "Intent_function_call",
        "memModelId": "Memory_nomem",
        "extra": {"disable_greeting": True, "goodbye": {"idle_timeout_seconds": 300}}}), "update agent")
    return agent_id


def ensure_device(key, agent_id, mac):
    bound = _ok(_call("GET", f"{API}/xiaozhi/device/bind/{agent_id}", key), "list devices").get("data") or []
    if any(d.get("macAddress", "").upper() == mac.upper() for d in bound):
        print(f"device {mac} already bound")
        return
    try:
        # 设备若已绑到别的智能体，先切过来（不迁移聊天记录）
        _ok(_call("PUT", f"{API}/v1/devices/{mac}/agent/{agent_id}", key,
                  {"disable_chat_history_migration": True}), "switch device")
        print(f"device {mac} switched to agent")
        return
    except LinxError:
        pass
    resp = _call("POST", f"{API}/xiaozhi/device/preregister", key,
                 {"agent_id": agent_id, "mac_addresses": [mac], "serial_numbers": []})
    print(f"preregister {mac}: {resp}")


def ota(mac, client_id):
    body = {"version": 0, "uuid": client_id,
            "application": {"name": "sunflower", "version": "0.1.0", "elf_sha256": "0" * 64},
            "board": {"type": "sunflower-device", "ssid": "", "rssi": 0, "mac": mac},
            "mac_address": mac, "chip_model_name": ""}
    resp = _call("POST", OTA, body=body, headers={
        "Activation-Version": "1", "Device-Id": mac, "Client-Id": client_id,
        "User-Agent": "sunflower/0.1.0", "Accept-Language": "zh-CN"})
    ws = resp.get("websocket") or {}
    if not ws.get("token"):
        code = (resp.get("activation") or {}).get("code")
        raise LinxError(f"OTA 未返回 token（设备未绑定）；activation={code}，先跑 `linx_admin up`")
    return ws["url"], ws["token"]


def refresh_token(mac):
    """Device-side: (re)fetch the WS token via OTA. Needs no API key."""
    st = config.read_state(STATE)
    st.setdefault("client_id", str(uuid.uuid4()))
    st["mac"] = mac
    st["ws_url"], st["ws_token"] = ota(mac, st["client_id"])
    config.write_state(STATE, st)
    return st


def main(argv=None):
    ap = argparse.ArgumentParser(prog="linx_admin")
    ap.add_argument("cmd", choices=["up", "status", "down"])
    ap.add_argument("--profile", default="dev-single-mac")
    a = ap.parse_args(argv)
    env = config.load_env()
    key = env.get("LINX_API_KEY")
    if not key:
        sys.exit("LINX_API_KEY 未配置：复制 .env.example 为 .env 并填写")
    prof = config.load_profile(a.profile)
    mac = prof["device"]["mac"]
    st = config.read_state(STATE)
    if a.cmd == "up":
        st["agent_id"] = ensure_agent(key, st)
        config.write_state(STATE, st)
        ensure_device(key, st["agent_id"], mac)
        st = refresh_token(mac)
        print(f"ready: agent={st['agent_id']} mac={mac} ws_token=<{len(st['ws_token'])} chars>")
    elif a.cmd == "status":
        agent = find_agent(key)
        print(json.dumps({"agent": agent and {k: agent.get(k) for k in
                          ("id", "agentName", "llmModelName", "deviceCount", "lastConnectedAt")},
                          "cached_mac": st.get("mac"), "has_ws_token": bool(st.get("ws_token"))},
                         ensure_ascii=False, indent=2))
    elif a.cmd == "down":
        agent = find_agent(key)
        if agent:
            _ok(_call("DELETE", f"{API}/xiaozhi/agent/{agent['id']}", key), "delete agent")
            print(f"deleted agent {agent['id']}")
        st.pop("ws_token", None)
        st.pop("agent_id", None)
        config.write_state(STATE, st)


if __name__ == "__main__":
    main()
