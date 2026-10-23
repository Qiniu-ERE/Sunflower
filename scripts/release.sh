#!/usr/bin/env bash
# 发版：版本号只来自 sunflower/__init__.py（先用一个 PR 提升版本号并合入），再运行
#
#   scripts/release.sh
#
# 前提：在 main、工作区干净、与 origin/main 一致、该提交的 push CI 门禁为绿、tag 尚不存在。
# 产物：GitHub Release vX.Y.Z（tag 指向该提交），正文是上个版本以来合入的 PR。
set -euo pipefail
cd "$(dirname "$0")/.."
die() { echo "✘ $*" >&2; exit 1; }

git fetch -q --tags origin main
[ "$(git rev-parse --abbrev-ref HEAD)" = main ] || die "请在 main 上发版"
git diff --quiet && git diff --cached --quiet || die "工作区不干净"
sha=$(git rev-parse HEAD)
[ "$sha" = "$(git rev-parse origin/main)" ] || die "本地 main 与 origin/main 不一致"
ver=$(python3 -c 'import sunflower; print(sunflower.__version__)')
tag="v$ver"
if git rev-parse -q --verify "refs/tags/$tag" >/dev/null; then die "$tag 已存在：先用 PR 提升版本号"; fi

ci=$(gh run list --workflow gate.yml --commit "$sha" --event push --json status,conclusion \
  -q '.[0] | "\(.status) \(.conclusion)"')
[ "$ci" = "completed success" ] || die "main@${sha:0:7} 的 CI 门禁不是绿（${ci:-无记录}）"

prev=$(git describe --tags --abbrev=0 2>/dev/null || true)
notes=$(printf '%s\n' "## 合入的 PR" "$(git log --first-parent --merges --format='- %s' "${prev:+$prev..}HEAD")" \
  "" "门禁：main@${sha:0:7} CI 全绿")
gh release create "$tag" --target "$sha" --title "$tag" --notes "$notes"
git fetch -q --tags origin
echo "✔ 已发布 $tag（${sha:0:7}）"
