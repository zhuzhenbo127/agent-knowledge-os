#!/usr/bin/env python3
"""Create a new Agent Knowledge OS vault or safely adopt an existing one."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from common import (
    CONCEPTS_DIR,
    INBOX_DIR,
    METHODS_DIR,
    MOCS_DIR,
    PERSONAL_DIR,
    ROOT_DIRS,
    SOURCES_DIR,
    SYSTEM_DIR,
    TOOLKIT_DIR,
    KnowledgeOSError,
    atomic_write_json,
    atomic_write_text,
    bilingual_name,
    load_json,
    normalize_config,
    render_wiki,
    source_folder,
    utc_now,
    workflow_folder,
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--vault", required=True, help="目标 Vault 绝对或相对路径")
    result.add_argument("--profile", required=True, help="已确认的 JSON 个性化配置")
    result.add_argument("--mode", choices=("setup", "adopt"), default="setup")
    result.add_argument("--confirmed", action="store_true", help="确认已向用户展示并获批设置确认单")
    return result


def candidate_template(config: dict) -> str:
    review = config["profile"]["review_policy"]
    return f"""---
type: candidate
status: candidate
source_path: ""
source_sha256: ""
confidence: low
created_at: ""
review_after_days: {int(review.get('default_days', 180))}
tags: [候选知识]
---

# 候选知识标题

## 核心判断

## 来源与证据

## 适用场景与边界

## 与已有知识的关系

## 反例与待确认问题
"""


def source_template() -> str:
    return """---
type: source
source_type: ""
author: ""
source_url: ""
captured_at: ""
content_sha256: ""
immutable: true
---

# 原始素材标题

> 在下方保留原文。不要把摘要冒充成原文。
"""


def delivery_template() -> str:
    return """# 交付台账·Delivery Ledger

| 日期 | 交付物 | 使用场景 | 用到的库存知识 | 新判断/修正 | 反馈与数据 | 暴露缺口 |
|---|---|---|---|---|---|---|
"""


def gaps_template() -> str:
    return """# 知识缺口池·Knowledge Gaps

| 发现日期 | 来源任务 | 缺口 | 需要的证据 | 状态 | 下一步 |
|---|---|---|---|---|---|
"""


def handoff_template() -> str:
    return """# 处理接续·Handoff

- 上次成功运行：尚未运行
- 当前范围：未设置
- 下次起点：扫描全部来源并按哈希与台账去重
- 暂缓处理：无
- 敏感/只读范围：以 config.json 为准
"""


def review_queue_template() -> str:
    return """# 审核队列·Review Queue

候选知识只在此排队。人工确认新建、合并、补来源或拒绝后，才可进入正式层。

| 候选 | 来源 | 核心判断 | 置信状态 | 人工决定 |
|---|---|---|---|---|
"""


def start_here(config: dict) -> str:
    return f"""# 从这里开始·Start Here

欢迎进入 **{config['profile']['vault_name']}**。

1. 把未经整理的原文放入 `01-原始素材·Sources` 对应目录。
2. 调用 `agent-knowledge-os` 的 ingest；AI 只会把候选写入本收件箱。
3. 人工审核候选，再决定是否晋升到概念或方法论。
4. 真实输出后更新交付台账和知识缺口池。
5. 定期运行 lint，检查过期、孤立、断链和规则违规。
"""


def agent_rules() -> str:
    return """# Agent Knowledge OS Rules

每次操作前先读取 `知识库说明·WIKI.md` 与 `99-系统·System/config.json`。

- 不修改、移动或删除原始素材。
- 候选只写入 `00-收件箱·Inbox`。
- 不自动晋升、合并、删除或解决冲突。
- 写入后回读验证；逐源记录；整轮成功后更新状态。
- 敏感信息先脱敏；遵守只读目录和 AI 写入边界。
- 内容生产先确认对象、问题、判断、边界、证据和形式。
"""


def create_tree(root: Path, config: dict, adopt: bool) -> list[str]:
    created: list[str] = []

    def mkdir(relative: str) -> None:
        path = root / relative
        if not path.exists():
            path.mkdir(parents=True)
            created.append(relative + "/")

    def write_missing(relative: str, content: str) -> None:
        path = root / relative
        if path.exists():
            return
        atomic_write_text(path, content)
        created.append(relative)

    for directory in ROOT_DIRS:
        mkdir(directory)

    for index, domain in enumerate(config["profile"]["domains"], 1):
        name = bilingual_name(domain, index)
        mkdir(f"{CONCEPTS_DIR}/{name}")
        mkdir(f"{METHODS_DIR}/{name}")
        write_missing(
            f"{MOCS_DIR}/{name}·MOC.md",
            f"# {name}\n\n## 核心概念\n\n## 方法论\n\n## 真实输出\n\n## 待验证问题\n",
        )

    for index, source_type in enumerate(config["profile"]["source_types"], 1):
        mkdir(f"{SOURCES_DIR}/{source_folder(source_type, index)}")

    for index, workflow in enumerate(config["profile"]["primary_workflows"], 1):
        mkdir(f"{PERSONAL_DIR}/{workflow_folder(workflow, index)}")

    mkdir(f"{TOOLKIT_DIR}/笔记模板·Note Templates")
    write_missing("知识库说明·WIKI.md", render_wiki(config))
    write_missing("AGENTS.md", agent_rules())
    write_missing("CLAUDE.md", agent_rules())
    write_missing(f"{INBOX_DIR}/从这里开始·START_HERE.md", start_here(config))
    write_missing(f"{INBOX_DIR}/候选知识模板·CANDIDATE_TEMPLATE.md", candidate_template(config))
    write_missing(f"{TOOLKIT_DIR}/笔记模板·Note Templates/原始素材模板·SOURCE.md", source_template())
    write_missing(f"{TOOLKIT_DIR}/笔记模板·Note Templates/候选知识模板·CANDIDATE.md", candidate_template(config))
    write_missing(f"{SYSTEM_DIR}/处理接续·HANDOFF.md", handoff_template())
    write_missing(f"{SYSTEM_DIR}/审核队列·REVIEW_QUEUE.md", review_queue_template())
    write_missing(f"{SYSTEM_DIR}/交付台账·DELIVERY_LEDGER.md", delivery_template())
    write_missing(f"{SYSTEM_DIR}/知识缺口池·KNOWLEDGE_GAPS.md", gaps_template())
    write_missing(f"{SYSTEM_DIR}/ingest-ledger.jsonl", "")

    state_path = root / SYSTEM_DIR / "state.json"
    if not state_path.exists():
        atomic_write_json(state_path, {
            "schema_version": config["schema_version"],
            "last_successful_ingest": None,
            "last_verified_at": None,
            "onboarding_complete": False,
        })
        created.append(f"{SYSTEM_DIR}/state.json")

    config_path = root / SYSTEM_DIR / "config.json"
    if config_path.exists() and adopt:
        raise KnowledgeOSError("已有 config.json；请使用 apply_profile.py 重新个性化")
    atomic_write_json(config_path, config)
    if f"{SYSTEM_DIR}/config.json" not in created:
        created.append(f"{SYSTEM_DIR}/config.json")

    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["onboarding_complete"] = True
    state["last_verified_at"] = utc_now()
    atomic_write_json(state_path, state)
    return created


def setup_new(vault: Path, config: dict) -> list[str]:
    if vault.exists() and any(vault.iterdir()):
        raise KnowledgeOSError("setup 模式拒绝写入非空目录；已有库请使用 --mode adopt")
    parent = vault.parent.resolve()
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{vault.name}.staging-", dir=str(parent)))
    try:
        created = create_tree(staging, config, adopt=False)
        if vault.exists():
            vault.rmdir()
        os.replace(staging, vault)
        return created
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def adopt_existing(vault: Path, config: dict) -> list[str]:
    if not vault.is_dir():
        raise KnowledgeOSError("adopt 模式要求目标目录已经存在")
    before = {path for path in vault.rglob("*")}
    try:
        return create_tree(vault, config, adopt=True)
    except Exception:
        after = sorted((path for path in vault.rglob("*") if path not in before), key=lambda p: len(p.parts), reverse=True)
        for path in after:
            if path.is_file():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass
        raise


def main() -> int:
    args = parser().parse_args()
    try:
        if not args.confirmed:
            raise KnowledgeOSError("未收到明确确认；不会写入。请先展示个性化设置确认单，再加 --confirmed")
        config = normalize_config(load_json(Path(args.profile)))
        vault = Path(args.vault).expanduser()
        created = setup_new(vault, config) if args.mode == "setup" else adopt_existing(vault, config)
        print(json.dumps({
            "status": "complete",
            "mode": args.mode,
            "vault": str(vault.resolve()),
            "created": created,
            "next": ["配置 Obsidian", "添加第一份原始素材", "运行 lint"],
        }, ensure_ascii=False, indent=2))
        return 0
    except (KnowledgeOSError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
