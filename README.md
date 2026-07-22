# Agent Knowledge OS

一套可安装到 Agent 的中文个人知识操作系统 Skill。它把 Markdown/Obsidian 资料库变成可追溯、可审核、可持续迭代的工作流：从首次个性化、原始素材 ingest、人工晋升，到内容生产与真实交付反馈。

它不是“一键自动整理全部资料”的承诺。AI 负责扫描、查重、候选草稿和重复劳动；人负责知识晋升、判断取舍、冲突解决与最终输出。

## 适合谁

- 第一次搭建个人知识库，希望得到清晰目录、规则和起步模板的人。
- 已经有 Obsidian 或 Markdown 资料库，但资料难以复用的人。
- 希望把知识库用于内容创作、研究、决策、产品或项目复盘的人。

## 安装

仓库发布到 GitHub 后，任何支持 Agent Skills 的客户端都可以从仓库安装。以 `npx skills` 为例：

```bash
npx skills add https://github.com/zhuzhenbo127/agent-knowledge-os --skill agent-knowledge-os
```

也可以克隆后从本地安装：

```bash
git clone https://github.com/zhuzhenbo127/agent-knowledge-os.git
npx skills add ./agent-knowledge-os --skill agent-knowledge-os
```

不同 Agent 的 Skill 安装目录不同；若客户端不支持 `npx skills`，把 `skills/agent-knowledge-os/` 复制到该客户端的 Skills 目录即可。

第一次使用建议直接阅读：[从零开始·USER_GUIDE.md](./从零开始·USER_GUIDE.md)。它按普通用户视角写明了安装、首次引导、第一份素材、第一次 ingest、人工审核、内容输出和日常维护。

## 快速开始

安装后对 Agent 说：

> 使用 `agent-knowledge-os` 帮我搭建知识库。

已有库：

> 使用 `agent-knowledge-os` 接管这个知识库，先检查现状，再引导我设置。

Agent 会逐题完成八步引导，最后先展示确认单。只有你确认后，它才会创建目录和正式配置。

## 你会得到什么

```text
知识库/
├── 知识库说明·WIKI.md
├── AGENTS.md
├── CLAUDE.md
├── 00-收件箱·Inbox/
├── 01-原始素材·Sources/
├── 02-概念·Concepts/
├── 03-方法论·Methodologies/
├── 04-个人输出·Personal/
├── 05-工具集·Toolkit/
├── 90-知识地图·MOCs/
└── 99-系统·System/
```

目录职责固定，领域、素材类型、资产类型、复查周期、隐私边界和二级目录可以个性化。

## 主要能力

- `diagnose`：判断现有资料是否能支持真实任务。
- `setup` / `adopt`：新建或接管已有库。
- `constitution`：生成或修改个性化章程。
- `ingest` / `review`：把来源转成候选知识并人工晋升。
- `produce`：先定义任务和证据，再生成内容。
- `feedback` / `lint`：记录真实交付、发现缺口与过期知识。

## Obsidian

默认只启用官方核心插件，并保留用户原有设置。Dataview 和 Templater 是可选白名单；只有用户明确选择后才安装。Skill 不安装 Obsidian 应用，也不自动更新社区插件。

## 本地验证

无需第三方 Python 包：

```bash
python3 -m unittest discover -s tests -v
python3 skills/agent-knowledge-os/scripts/lint_vault.py --help
```

## 隐私与边界

- 原始素材不可静默改写或删除。
- 候选知识不会自动进入正式层。
- 客户资料、私人聊天、账号和密钥必须先脱敏。
- 默认不抓网页、不做 OCR/PDF 转录、不使用向量数据库。

## 开源与服务

代码按 MIT License 开源。你可以自行使用和二次开发；围绕迁移、个性化、培训、知识库治理与工作流落地提供商业服务，不影响仓库本身的开放使用。

## 仓库结构

- `skills/agent-knowledge-os/SKILL.md`：Agent 主入口。
- `references/`：架构、铁律、引导、ingest、内容生产和反馈规范。
- `scripts/`：确定性的初始化、扫描、配置、发现与校验工具。
- `assets/`：Vault 与笔记模板。
- `tests/`：安全、幂等、跨路径和工作流测试。
