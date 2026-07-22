---
name: agent-knowledge-os
description: 搭建、接管和维护基于 Markdown 与 Obsidian 的个人知识操作系统。用于新建知识库、扫描已有 Vault、引导式个性化、生成知识库章程、配置 Obsidian、处理原始素材、审核候选知识、用库存证据辅助内容生产、记录交付反馈，以及检查孤立、过期、占位符和规则违规。用户提到“搭建知识库”“接管现有知识库”“知识库个性化”“运行 ingest”“把资料变成可调用资产”“用知识库生产内容”“知识库体检”时使用。
---

# Agent Knowledge OS

把资料处理成可追溯、可审核、可复用的知识资产。坚持半自动：AI 处理重复劳动，人保留晋升、取舍、冲突解决和最终表达的责任。

## 先判断任务

| 用户意图 | 动作 | 必读参考 |
|---|---|---|
| 不确定资料是否可用 | `diagnose` | `references/architecture.md` |
| 新建知识库 | `setup` | `references/onboarding.md`、`references/constitution.md` |
| 接管已有库 | `adopt` | `references/onboarding.md`、`references/architecture.md` |
| 重新个性化 | `constitution` | `references/onboarding.md`、`references/constitution.md` |
| 处理新增素材 | `ingest` | `references/ingest.md` |
| 审核与晋升 | `review` | `references/ingest.md` |
| 生成内容 | `produce` | `references/content-production.md` |
| 记录真实交付 | `feedback` | `references/feedback-loop.md` |
| 检查健康状态 | `lint` | `references/lint-and-status.md` |
| 配置 Obsidian | Obsidian 设置 | `references/obsidian-setup.md` |

课程能力映射见 `references/course-map.md`。架构职责见 `references/architecture.md`。

## 固定铁律

1. 保留原始证据；不改写、删除、移动或重命名来源。
2. 候选知识只进入 `00-收件箱·Inbox`；不得自动晋升到正式层。
3. 每条知识保留来源、适用边界、置信状态和复查信息。
4. 不把标题、空链接、转录失败提示或常识补写成来源正文。
5. 不静默覆盖用户配置，不关闭已有插件，不自动解决冲突。
6. 涉及客户资料、私人聊天、账号或密钥时先停下并要求脱敏。
7. 写入后回读验证；逐源追加日志；整轮成功后才更新状态。
8. 知识库是证据库，不是作者；AI 是执行助手，不是主编。

这些规则不可通过首次引导关闭。完整规则见 `references/constitution.md`。

## Setup：新建知识库

1. 一次只问一个问题，按 `references/onboarding.md` 完成八步引导。
2. 收集完答案后输出“个性化设置确认单”。未获明确确认前不得运行写入脚本。
3. 把确认结果保存成临时 JSON；将 `onboarding.status` 设置为 `complete`，不得保留空字段或 `{{PLACEHOLDER}}`。
4. 运行：

```bash
python3 scripts/bootstrap.py --vault "/absolute/path/to/vault" --profile "/path/to/profile.json" --confirmed
```

5. 按 `references/obsidian-setup.md` 配置 Obsidian。社区插件只在用户明确选择后安装。
6. 运行 `lint_vault.py` 与 `verify_run.py`，回报文件清单和下一步 Todo。

## Adopt：接管已有知识库

1. 先扫描，不写入：

```bash
python3 scripts/scan_existing_vault.py --vault "/absolute/path/to/vault" --output "/tmp/vault-scan.json"
```

2. 向用户展示已发现的目录、领域、标签、素材类型和冲突；只询问缺失项。
3. 输出确认单并等待明确确认。
4. 使用 `bootstrap.py --mode adopt --confirmed` 创建缺失的系统入口。不得搬迁或重命名已有目录。
5. 如需目录调整，只生成迁移计划，另行确认。

## 再次个性化

1. 读取当前 `config.json` 和实际目录，显示当前设置。
2. 只询问用户想修改的字段。
3. 先生成差异，不写入：

```bash
python3 scripts/apply_profile.py --vault "/absolute/path/to/vault" --profile "/path/to/new-profile.json" --dry-run
```

4. 用户确认后改为 `--confirmed`。脚本先备份配置，再原子更新；目录变更只输出迁移计划。

## Ingest 与 Review

严格按 `references/ingest.md` 执行。先运行 `discover_sources.py` 发现未处理或已变化来源；全文读取每份来源后，只能给出 `跳过·Skip`、`保留原文·Preserve`、`更新建议·Update`、`候选草稿·Candidate` 之一。

候选写入后运行：

```bash
python3 scripts/verify_run.py --vault "/absolute/path/to/vault" --candidate "relative/path.md" --source "relative/source.md"
```

人工审核决定新建、合并、补充来源或拒绝。不得让脚本直接改写正式知识。

## Produce

按顺序确认对象、问题、核心判断、表达边界、证据、输出形式。先返回素材包供用户确认，再给结构，最后才写初稿。执行细则见 `references/content-production.md`。

## Feedback 与 Lint

真实交付后，按 `references/feedback-loop.md` 更新交付台账、反馈和缺口；新经验仍先进入候选区。

运行健康检查：

```bash
python3 scripts/lint_vault.py --vault "/absolute/path/to/vault" --json
```

Lint 只报告问题，不自动删除、晋升或修改正式知识。

## 安全操作

- 把所有用户路径视为数据，不拼接 shell 命令。
- 写入前解析目标路径，拒绝越出 Vault 的路径。
- 新建模式拒绝非空目录；接管模式只增量创建缺失文件。
- 失败时保留旧配置和备份，不把 onboarding 标成完成。
- 不将用户私有绝对路径、客户资料、密钥或课程内部标记写入可发布仓库。
