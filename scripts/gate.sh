#!/usr/bin/env bash
# 门禁：本地、CI、merge.sh 跑的是同一条命令。最后一行 EXIT=<码>——别接 | tail，会吞退出码。
#
#   scripts/gate.sh               全量门：语法 + 全部单测
#   scripts/gate.sh --base <ref>  再加规格门（PR 用；PR 正文从环境变量 PR_BODY 读，判据见 gate_check.py）
set -uo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}
ROOT=$(pwd)
OUT=$(mktemp -d)
base=""
[ "${1:-}" = "--base" ] && base=${2:?--base 需要一个 git ref}

fail() { echo "✘ $*"; echo "EXIT=1"; exit 1; }

echo "== 语法"
$PY -m compileall -q sunflower scripts tests >/dev/null || fail "compileall 不通过"

echo "== 全量单测"
$PY scripts/run_tests.py "$OUT/head.json" >"$OUT/head.log" 2>&1
code=$?
tail -3 "$OUT/head.log"
if [ $code -ne 0 ]; then
  $PY -c 'import json,sys; [print("✘", k, v) for k, v in json.load(open(sys.argv[1])).items() if v not in ("ok", "skipped")]' "$OUT/head.json" 2>/dev/null
  fail "单测未全绿（完整日志 ${OUT}/head.log）"
fi

if [ -n "$base" ]; then
  echo "== 规格门（base=${base}）"
  mb=$(git merge-base "$base" HEAD) || fail "找不到 ${base} 与 HEAD 的 merge-base"
  if git diff --quiet "$mb" HEAD -- sunflower; then
    echo "未改动 sunflower/，规格门不适用"
  else
    # 本分支的测试 + base 的代码：点名的规格测试必须在这里不通过
    wt="$OUT/base"
    git worktree add -q --detach "$wt" "$mb" || fail "无法检出 base"
    rm -rf "$wt/tests" && git archive HEAD tests | tar -x -C "$wt"
    (cd "$wt" && $PY "$ROOT/scripts/run_tests.py" "$OUT/base.json" >"$OUT/base.log" 2>&1)
    git worktree remove --force "$wt"
    $PY scripts/gate_check.py "$OUT/base.json" "$OUT/head.json" || fail "规格门未通过"
  fi
fi
echo "EXIT=0"
