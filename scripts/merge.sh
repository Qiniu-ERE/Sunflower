#!/usr/bin/env bash
# 唯一合入入口（私有免费仓没有 required check，门槛在这里）：
#   CI 在 PR 头提交上全绿 + 本地在干净检出上重跑门禁 → PR 下贴回执 → GitHub 生成合并提交。
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
  die "PR #$n 落后于 main：先在分支上 git merge origin/main 并推送，等 CI 重跑"

echo "== CI（PR 头 ${sha:0:7}）"
checks=$(gh pr checks "$n" --json name,bucket -q '.[] | "\(.bucket) \(.name)"' || true)
[ -n "$checks" ] || die "PR #$n 还没有 CI 结果"
echo "$checks"
if echo "$checks" | grep -qv '^pass '; then die "CI 未全绿"; fi

echo "== 本地门禁（干净检出 ${sha:0:7}）"
wt="$(mktemp -d)/pr"
git worktree add -q --detach "$wt" "$sha"
trap 'git worktree remove --force "$wt" 2>/dev/null || true' EXIT
for f in scripts/gate.sh scripts/gate_check.py; do
  if git cat-file -e "origin/main:$f" 2>/dev/null; then git show "origin/main:$f" >"$wt/$f"; fi
done
set +e
log=$(cd "$wt" && PR_BODY="$body" bash scripts/gate.sh --base origin/main 2>&1)
set -e
echo "$log"
[ "$(echo "$log" | tail -1)" = "EXIT=0" ] || die "本地门禁未通过"

receipt=$(printf '%s\n' "门禁回执 · ${sha:0:7}" "" "CI：" "$(echo "$checks" | sed 's/^/- /')" "" \
  "本地（main 上的 scripts/gate.sh，干净检出）：" '```' "$(echo "$log" | grep -vE '^\s*$')" '```')
gh pr comment "$n" --body "$receipt" >/dev/null
gh pr merge "$n" --merge --match-head-commit "$sha" --delete-branch \
  --subject "合并 #${n}：${title}" --body "$receipt"
git switch -q main && git pull -q --ff-only origin main
echo "✔ 已合入 #$n → main $(git rev-parse --short HEAD)"

# 主机服务已安装时，合入即部署；主机正在执行任务就跳过（不打断），status 会提示漂移
if [ -f "$HOME/Library/LaunchAgents/com.sunflower.host.plist" ]; then
  python3 -m sunflower.service deploy --wait 0 || echo "⚠ 未部署：主机忙或启动失败，稍后执行 python3 -m sunflower.service deploy"
fi
