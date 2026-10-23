"""写红 / 规格门的判定逻辑（gate.sh 调用；本身有单测）。

PR 正文「规格」段每行一条不变量 + 反引号测试名。点名的每个测试必须：
  在 base 代码上不通过（FAIL / ERROR / 不存在）——证明规格不是空话；
  在本分支上 ok——证明实现满足规格。
纯重构可写「写红豁免: <理由>」跳过，但全量测试仍须全绿。

    python3 scripts/gate_check.py <base.log> <head.log>    # PR 正文从环境变量 PR_BODY 读
"""
import os
import re
import sys

_RESULT = re.compile(r"^(test\w*) \([\w.]+\) \.\.\. (ok|FAIL|ERROR|skipped.*|expected failure|unexpected success)$",
                     re.M)
_SPEC_HEAD = re.compile(r"^##\s*规格.*$", re.M)
_TEST_NAME = re.compile(r"`(test\w+)`")


def parse_results(log):
    return {name: status for name, status in _RESULT.findall(log)}


def spec_tests(body):
    m = _SPEC_HEAD.search(body or "")
    if not m:
        return []
    section = re.split(r"^##\s", body[m.end():], maxsplit=1, flags=re.M)[0]
    return _TEST_NAME.findall(section)


def exemption(body):
    m = re.search(r"^写红豁免[:：][ \t]*(\S.*)$", body or "", re.M)
    return m.group(1).strip() if m else None


def evaluate(specs, base, head):
    if not specs:
        return False, ["✘ PR 正文「## 规格」段没有点名任何测试（`test_xxx`）；纯重构请写「写红豁免: <理由>」"]
    ok, lines = True, []
    for t in specs:
        b, h = base.get(t, "absent"), head.get(t, "absent")
        if h != "ok":
            ok = False
            lines.append(f"✘ {t}: 本分支 {h}（规格未被实现满足）")
        elif b == "ok":
            ok = False
            lines.append(f"✘ {t}: base 上已经通过（规格没有写红，测不出这次改动）")
        else:
            lines.append(f"✔ {t}: base {b} → 本分支 ok")
    return ok, lines


def main(argv):
    base_log, head_log = (open(p, encoding="utf-8").read() for p in argv[1:3])
    body = os.environ.get("PR_BODY", "")
    reason = exemption(body)
    if reason:
        print(f"写红豁免：{reason}")
        return 0
    ok, lines = evaluate(spec_tests(body), parse_results(base_log), parse_results(head_log))
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
