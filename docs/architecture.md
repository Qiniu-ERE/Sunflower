# 架构设计

本文是评审要求的架构设计文档：整体结构、模块规格、对外接口、分工，以及代码来源与过程说明。链路图和时序图在 [README「链路」](../README.md#链路)，这里不重复。

## 整体结构

```
设备（device.py / tg.py）──出站 wss──▶ 语音服务（灵矽：ASR → 意图路由 → TTS）
   │  端侧 MCP 工具 self.code.*                     ▲ text_response 播报
   ▼                                                │
主机（host.py :8787）── HTTP /api/* ─▶ CodexRunner（agents.py）── codex exec --json / resume ─▶ 工作区（独立 git 仓）
   └── SSE /events ─▶ 面板（web/panel.html，任意浏览器）/ 设备（announce、key）/ TG 卡片
```

三条边界决定了模块怎么切：

1. **语音平台的工具调用约 30 s 超时**：主机的写接口一律立即回执，Codex 在后台跑，完成后主机经 SSE 推 `announce`，设备再用 `text_response` 播报。
2. **设备只发起出站连接**：不需要公网地址，笔记本、树莓派、Telegram 入口走同一条链路；硬件差异只放在 `profiles/*.json`（录音、播放、按键、主机地址）。
3. **语音没有确认对话框**：每个任务落成工作区里的一个 `voice:` 提交，撤销就是 `git revert`；Codex 只改仓库外的一次性工作区，比赛仓本身不被改动。

## 模块规格

| 模块 | 职责 | 对外接口 | 不变量 | 测试 |
|---|---|---|---|---|
| `sunflower/device.py`（731 行） | 灵矽软设备：麦克风 / 扬声器、按键说话、端侧 MCP 工具、空闲断连、播报 | `python3 -m sunflower.device --profile <名>`；出站 wss 到灵矽，HTTP + SSE 到主机 | 只出站；工具调用转成对主机的 HTTP，远低于平台超时返回；空闲 20 s 主动断开，结果出来再冷连接播报 | `tests/test_device.py` |
| `sunflower/host.py`（312 行） | 一个进程一个端口服务三方：设备接口、面板页面、事件流 | HTTP API 与 SSE 事件见下节；`python3 -m sunflower.host --profile <名>` | 写接口要令牌（本机面板的按键接口除外，限回环 + 本机 Host + 同源）；SSE 带回放缓冲，面板刷新不丢进展 | `tests/test_core.py` |
| `sunflower/agents.py`（360 行） | `CodexRunner`：无头驱动 Codex，解析事件流，提交、撤销、生成语音摘要 | `dispatch / status / cancel / undo / new_session / set_agent` | 同一时刻只跑一个任务，忙时新派发被拒并提示可取消；多轮对话用 `exec resume` 复用同一会话；任务失败只播报不提交；撤销只回滚 `voice:` 开头的提交；「停下」及同音字按叫停处理 | `tests/test_core.py`（`fake_codex.py` 回放事件流，不连云） |
| `sunflower/linx_admin.py`（183 行） | 灵矽平台侧整备：建删智能体、预注册软设备、OTA 取 WebSocket 令牌 | `python3 -m sunflower.linx_admin up / status / down` | 智能体提示词规定不确定就派发、绝不反问；令牌落在 `~/.sunflower/`（600 权限），不进仓库 | 真机验证（依赖云端，单测不覆盖） |
| `sunflower/tg.py`（385 行） | Telegram 入口：手机发文字 / 语音，经第二台灵矽软设备进同一条链路，进度在一张卡片上原地刷新 | `python3 -m sunflower.tg --profile tg-bridge` | 只出站（长轮询）；只理白名单用户；意图路由仍在灵矽，不在本地另做一套 | `tests/test_tg.py` |
| `sunflower/service.py`（413 行） | 主机常驻：launchd 安装、从固定提交部署、不打断任务的重启、版本漂移检查 | `python3 -m sunflower.service install / deploy / restart / status / device-install …` | 重启等当前任务做完（可设超时）；`status` 显示运行中、已部署、main、设备四方的提交是否一致；桌面设备常驻后拒绝再起第二个设备进程 | `tests/test_service.py` |
| `sunflower/demo.py`（143 行） | 演示工作区重置与预览 | `python3 -m sunflower.demo reset / preview` | 工作区拒绝落在比赛仓内；`reset` 回到预埋 bug 的初始状态，演示可重复 | `tests/test_core.py` |
| `sunflower/tryout.py`（63 行） | 试音：念固定句子，记录平台听成什么、会调哪个工具，只记录不执行 | 面板「试音」页 → `POST /api/tryout`；结果写 `~/.sunflower/tryout.jsonl` | 试音那一轮的工具调用在设备里被拦下，不触发 Codex | `tests/test_core.py`、`tests/test_device.py` |
| `sunflower/config.py`（65 行） | `.env`、profile、运行态读写 | `load_env / load_profile / read_state / write_state` | 运行态文件 600 权限；密钥只来自 `.env` 或钥匙串 | 无专门单测，经 `test_core.py`、`test_service.py` 间接覆盖 |
| `sunflower/web/` | 进展面板 `panel.html`（1080p 投屏 / 7 寸屏自适应）、试音页 `tryout.html` | 浏览器打开 `http://<主机>:8787/` | 零依赖，只用 SSE 和按键接口；屏幕即任意浏览器，AirPlay 只是其中一种投屏方式 | `tests/test_panel.py` |
| `scripts/` | 门禁、合入、发版；演示计时；树莓派整备 | `gate.sh`、`merge.sh <PR号>`、`release.sh`、`bench_demo.py` | 合入只经 `merge.sh`：本机干净检出、用 main 上的门禁在 Python 3.9 + 3.12 各跑一遍；规格门要求点名测试在 main 上红、在分支上绿 | `tests/test_gate_check.py` |
| `docs/hardware/`、`docs/business/` | 硬件概念设计与 3D 打印原型；成本、盈亏平衡与竞品 | `draw.py`、`cost_model.py` 由数据生成图表 | README 里的数字与 CSV 一致 | `tests/test_business.py` |

## 接口

**端侧 MCP 工具**（设备向灵矽声明，平台的模型按意图调用；设备把调用转成主机 HTTP）

| 工具 | 何时调用 | 主机接口 |
|---|---|---|
| `self.code.dispatch(text)` | 凡涉及代码、测试、bug、功能、检查、解释的请求；原话照传 | `POST /api/dispatch` |
| `self.code.status` | 明确问进度 | `POST /api/status` |
| `self.code.cancel` | 停下、取消（含同音字「听下」） | `POST /api/cancel` |
| `self.code.undo` | 撤销、回滚 | `POST /api/undo` |

**主机 HTTP**：`GET /health`、`GET /`（面板）、`GET /tryout`、`GET /events`（SSE，本机免令牌、跨机带 `?t=<令牌>`）；写接口 `POST /api/{dispatch,status,cancel,undo,new-session,channel,key,tryout,device,voice}`，返回 `{"ok": …, "say": "<给语音念的一句话>"}`。

**SSE 事件**：`state`（空闲 / 运行中、任务、渠道）、`log`（用户原话、Codex 每一步）、`diff`（本次提交的改动统计）、`result`、`announce`（播报文本，设备收到后去念）、`key`（面板上的说话按键，只发给桌面设备）、`device`（设备录音状态）、`voice`、`tryout`。

## 分工

单人作品：设计、实现、测试、文档、硬件概念与成本分析均由 sunyifei83 完成。提交记录里的 `sunyifei <sunyifei@qiniu.com>` 和 `vincent.sun <…@users.noreply.github.com>` 是同一个人：前者是本机提交，后者是 GitHub 网页上的合并提交。

## 代码来源

**没有既有 codebase，因此没有 v0 tag。** 全部代码从 2026-10-23 14:56（北京时间）的首个提交 `a838abc` 开始为本次比赛编写。首个提交有 1400 行，是先对灵矽平台做接口实测（预注册设备、OTA 取令牌、WebSocket 上下行）、再一次写成的；实测脚本不在本仓，和本仓只共用平台的接口地址与字段名。唯一的第三方依赖是 `websockets`。

## 过程说明

- main 上一共 10 个提交没有经过 PR：
  - `a838abc` 到 `e036e82` 这 9 个，是 2026-10-23 14:56–19:36（北京时间）建仓初期、PR 流程还没建立时直接提交的。19:55 合入的 #4 建立了 issue → PR → 门禁合入的流程，并加上禁止直推 main 的 pre-push 钩子。
  - `681befc`（2026-10-24 22:07，北京时间）是在 GitHub 网页上直接改的 README 一行字，绕过了本地钩子。
- 其余变更都经 PR 合入，合并方式固定为合并提交，`git log --first-parent main` 就是 PR 列表。为保留过程痕迹，以上提交不改写历史。流程细节见 [CONTRIBUTING.md](../CONTRIBUTING.md)。
