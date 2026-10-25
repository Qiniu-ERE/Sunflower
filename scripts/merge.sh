#!/usr/bin/env bash
# 唯一合入入口（私有免费仓没有 required check，门槛在这里）：
#   本机干净检出上跑门禁（Python 3.9 + 3.12）→ commit status「local-gate」贴回 GitHub → PR 下贴回执
#   → GitHub 生成合并提交。不依赖 GitHub Actions（2026-10-24 组织计费失败，托管 runner 一个 job 都不起）。
#
#   scripts/merge.sh <PR号>
#
# 判定用 origin/main 上的门禁脚本，而不是 PR 自带的那份：PR 不能把门禁改松再放自己过去。
set -euo pipefail
cd "$(dirname "$0")/.."
n=${1:?用法: scripts/merge.sh <PR号>}
die() { echo "✘ $*" >&2; exit 1; }

read -r state base sha < <(gh pr view "$n" --json state,baseRefName,headRefOid \
  -q '"\(.state) \(.baseRefName) \(.headRefOid)"')
title=$(gh pr view "$n" --json title -q .title)
body=$(gh pr view "$n" --json body -q .body)
[ "$state" = OPEN ] || die "PR #$n 状态是 $state"
[ "$base" = main ] || die "PR #${n} 的目标分支是 ${base}，不是 main"

git fetch -q origin main "pull/$n/head"
git merge-base --is-ancestor origin/main "$sha" ||
  die "PR #$n 落后于 main：先在分支上 git merge origin/main 并推送，再跑一次 merge.sh"

echo "== 本地门禁（干净检出 ${sha:0:7}，main 上的 scripts/gate.sh）"
wt="$(mktemp -d)/pr"
git worktree add -q --detach "$wt" "$sha"
trap 'git worktree remove --force "$wt" 2>/dev/null || true' EXIT
for f in scripts/gate.sh scripts/gate_check.py; do
  if git cat-file -e "origin/main:$f" 2>/dev/null; then git show "origin/main:$f" >"$wt/$f"; fi
done
# 解释器矩阵与原 CI 一致：3.9（树莓派 / macOS 自带）+ 3.12。各一个 uv venv，依赖按本 PR 的 requirements.txt 装
log=""
for v in 3.9 3.12; do
  venv="$HOME/.cache/sunflower-gate/py${v}"
  [ -x "$venv/bin/python" ] || uv venv -q --python "$v" "$venv" || die "建不了 Python ${v} 环境（uv venv）"
  uv pip install -q --python "$venv/bin/python" -r "$wt/requirements.txt" || die "Python ${v} 装依赖失败"
  set +e
  out=$(cd "$wt" && PYTHON="$venv/bin/python" PR_BODY="$body" bash scripts/gate.sh --base origin/main 2>&1)
  set -e
  echo "-- Python ${v}"
  echo "$out"
  [ "$(echo "$out" | tail -1)" = "EXIT=0" ] || die "本地门禁未通过（Python ${v}）"
  log+="-- Python ${v}"$'\n'"${out}"$'\n'
done

# GitHub 上留痕：PR 头和（合入后）合并提交都挂 local-gate 绿，release.sh 认这个
gate_status() {
  gh api -X POST "repos/{owner}/{repo}/statuses/$1" -f state=success -f context=local-gate \
    -f description="merge.sh 本机干净检出：Python 3.9 + 3.12 门禁通过" >/dev/null
}
gate_status "$sha"

receipt=$(printf '%s\n' "门禁回执 · ${sha:0:7}" "" \
  "本机干净检出，main 上的 scripts/gate.sh，Python 3.9 + 3.12（不依赖 GitHub Actions）：" \
  '```' "$(echo "$log" | grep -vE '^\s*$')" '```')
gh pr comment "$n" --body "$receipt" >/dev/null
# 判合入看 PR 状态，不看退出码：分支被某个 worktree 检出时 gh 删本地分支失败会非 0，曾让后面的部署被跳过（#33）
gh pr merge "$n" --merge --match-head-commit "$sha" --delete-branch \
  --subject "合并 #${n}：${title}" --body "$receipt" \
  || echo "⚠ gh pr merge 非 0 退出（常见：分支在 worktree 里，删不掉本地分支），按 PR 状态判定"
[ "$(gh pr view "$n" --json state -q .state)" = MERGED ] || die "合入失败：PR #$n 未处于 MERGED"
# PR 不落后于 main（上面已校验），合并提交的树就是刚验过的 PR 头
gate_status "$(gh pr view "$n" --json mergeCommit -q .mergeCommit.oid)"
git fetch -q origin main
# 在 worktree 里跑时 main 已在别的目录检出、切不过去，HEAD 还是 PR 分支；回执一律报 origin/main
git switch -q main 2>/dev/null && git pull -q --ff-only origin main || true
echo "✔ 已合入 #$n → main $(git rev-parse --short origin/main)"

# 主机服务已安装时，合入即部署；主机正在执行任务就跳过（不打断），status 会提示漂移
if [ -f "$HOME/Library/LaunchAgents/com.sunflower.host.plist" ]; then
  python3 -m sunflower.service deploy --wait 0 || echo "⚠ 未部署：主机忙或启动失败，稍后执行 python3 -m sunflower.service deploy"
fi
