# 开发流程

**需求和调研走 issue，代码走 PR，PR 过门槛才合入，发版只从绿的 main 打 tag。** 每一步在 GitHub 上都留痕。

```
issue（需求 / 调研 / 缺陷）
  → 分支 feat|fix|docs|chore|test/<issue号>-<主题>
  → 先写红：新测试在 main 的代码上失败
  → 实现到绿：scripts/gate.sh 输出 EXIT=0
  → PR（模板：为什么 / 改了什么 / 规格 / 验证 / 已知边界）
  → scripts/merge.sh <PR号>（本机门禁 Python 3.9 + 3.12 全绿才合）
  → GitHub 合并提交「合并 #N：标题」，回执贴在 PR 评论和合并提交正文
  → 攒够一版：PR 提升 sunflower/__init__.py 版本号 → scripts/release.sh
```

克隆后先跑一次 `scripts/setup-dev.sh`：启用 pre-push 钩子，禁止直接推 main。

## 门禁

| 命令 | 做什么 | 谁跑 |
|---|---|---|
| `scripts/gate.sh` | 语法检查 + 全部单测（解释器由 `PYTHON` 指定，默认 `python3`） | 本地、`merge.sh` |
| `scripts/gate.sh --base origin/main` | 再加**规格门**：PR 正文「规格」段点名的测试，在 main 的代码上必须失败、在本分支必须通过 | `merge.sh` |
| `scripts/merge.sh <PR号>` | 要求 PR 不落后于 main，用 **main 上的门禁脚本**在本机干净检出上按 Python 3.9、3.12 各跑一遍（uv venv，缓存在 `~/.cache/sunflower-gate`），都通过才合并；PR 头和合并提交挂 commit status `local-gate` | 合入时 |

门禁不依赖 GitHub Actions：2026-10-24 起组织计费失败，托管 runner 不起 job，`gate.yml` 只留手动触发。仓库私有期间 GitHub 不提供 required check，`merge.sh` 是唯一合入入口；公开后可把 `local-gate` 设为 required。

### 规格门在验证什么

改动 `sunflower/` 的 PR 要在正文里写「不变量 → 测试名」，例如：

```markdown
## 规格（不变量 → 测试）
- 派发在 1 秒内返回，执行在后台 → `test_dispatch_returns_immediately_then_announces_and_commits`
- 任务失败只播报、不提交 → `test_failure_is_announced_not_committed`
```

门禁把本分支的 `tests/` 放到 main 的代码上运行：点名的测试在那里**必须失败**（这条规格确实描述了这次改动，不是一句空话），在本分支上**必须通过**（实现满足规格）。这是把「代码 + 规格 + 可机检的证明」分开评估的思路落到单测上：规格是不变量，证明是在新旧代码上一红一绿的测试。

纯重构（行为不变）写一行 `写红豁免: <理由>`，但全量单测仍须全绿。

## 提交与 PR

- 提交信息：`<类型>: <描述>`，类型取 `feat` / `fix` / `docs` / `refactor` / `test` / `chore`。
- 一个 PR 只解决一件事；未完全交付 issue 时写 `关联 #N`，完全交付才写 `Closes #N`。
- 合入方式固定为合并提交（不 squash、不 rebase），`git log --first-parent main` 就是 PR 列表。

## 发版

1. 开 PR 修改 `sunflower/__init__.py` 的 `__version__`，按上面的流程合入。
2. 在最新的 main 上运行 `scripts/release.sh`：要求该提交挂着 `merge.sh` 贴的 `local-gate` 绿、tag 尚不存在，然后创建 GitHub Release `vX.Y.Z`，正文列出上个版本以来合入的 PR。
