#!/usr/bin/env bash
# 克隆后跑一次：启用仓库自带的 git 钩子（禁止直推 main）。
set -euo pipefail
cd "$(dirname "$0")/.."
git config core.hooksPath scripts/git-hooks
echo "✔ core.hooksPath = scripts/git-hooks（pre-push：禁止直接推 main）"
