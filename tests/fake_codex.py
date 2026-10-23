"""Stand-in for `codex exec --json`: replays the event shapes recorded from codex-cli 0.163."""
import json
import pathlib
import sys

args = sys.argv[1:]
out = pathlib.Path(args[args.index("-o") + 1])
ws = pathlib.Path(args[args.index("-C") + 1])
resumed = "resume" in args


def emit(obj):
    print(json.dumps(obj, ensure_ascii=False), flush=True)


if not resumed:
    emit({"type": "thread.started", "thread_id": "thread-123"})
emit({"type": "turn.started"})
emit({"type": "error", "message": "Reconnecting... 1/5"})
emit({"type": "item.started", "item": {"type": "command_execution", "command": "/bin/zsh -lc 'ls'"}})
emit({"type": "item.completed", "item": {"type": "command_execution", "command": "/bin/zsh -lc 'ls'", "exit_code": 0}})
if "read-only" not in args:  # 检查类任务跑在 workspace-write 里：Codex 仍可能改文件，由主机兜底
    (ws / "feature.txt").write_text("resumed\n" if resumed else "first\n", encoding="utf-8")
emit({"type": "item.completed", "item": {"type": "file_change", "changes": [{"path": str(ws / "feature.txt"), "kind": "add"}]}})
emit({"type": "item.completed", "item": {"type": "agent_message", "text": "完成。\n语音摘要：新增功能，测试通过"}})
emit({"type": "turn.completed", "usage": {"output_tokens": 42}})
out.write_text("完成。\n语音摘要：新增功能，测试通过", encoding="utf-8")
sys.exit(int("FAIL" in args[-1]))
