"""试音（#10 候选 5，#40）：念固定的句子，看平台听成什么、智能体会调哪个工具；只记录，不执行。

和演示走同一条链路（面板按键 → 设备录音 → 灵矽 ASR → 智能体路由），只在设备里把这一轮的工具调用拦下。
结果逐行追加到 ~/.sunflower/tryout.jsonl，换条件（小声 / 气声 / 慢速）对比。
"""
import json
import re
import time

from . import agents

# (要念的话, 应路由到的工具)；与合成音探针同一组，结果可直接对比
PHRASES = [("检查一下代码有没有逻辑问题", "dispatch"), ("那就把它修好", "dispatch"), ("撤销刚才的改动", "undo"),
           ("给待办清单加一个删除命令", "dispatch"), ("进度怎么样了", "status"), ("停下", "cancel"),
           ("跑一下测试把失败的修好", "dispatch"), ("看看项目是干什么的", "dispatch"),
           ("把列表里已完成的事项标成绿色", "dispatch"), ("好了吗", "status")]
CONDS = [("normal", "正常", "平常说话的音量和语速"), ("quiet", "小声", "压低音量，但仍出声"),
         ("breathy", "气声", "只用气、不振动声带（耳语）"), ("slow", "慢速", "一个字一个字慢慢说")]
TOOLS = {"self.code.dispatch": "dispatch", "self.code.status": "status",
         "self.code.cancel": "cancel", "self.code.undo": "undo"}


def norm(s):
    return re.sub(r"[\s，。！？、,.!?]", "", s or "")


def cer(ref, hyp):
    """字错率：编辑距离 / 参考字数（标点、空格不计）。"""
    a, b = norm(ref), norm(hyp)
    d = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, cb in enumerate(b, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (ca != cb))
    return d[len(b)] / max(len(a), 1)


def effective_tool(name, args):
    """平台调的工具 → 实际会发生的动作。dispatch 的原话若是叫停，主机会按叫停处理（stop_intent）。"""
    tool = TOOLS.get(name)
    if tool == "dispatch" and agents.stop_intent((args or {}).get("text", "")):
        return "cancel"
    return tool


def score(cond, idx, hyp, tool_name, args, clock=time.time):
    ref, expect = PHRASES[idx]
    tool = effective_tool(tool_name, args)
    return {"ts": int(clock()), "cond": cond, "idx": idx, "ref": ref, "hyp": hyp, "heard": hyp is not None,
            "exact": hyp is not None and norm(hyp) == norm(ref), "cer": round(cer(ref, hyp), 3),
            "expect": expect, "tool": tool, "args": args or {}, "ok": tool == expect}


def append(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
