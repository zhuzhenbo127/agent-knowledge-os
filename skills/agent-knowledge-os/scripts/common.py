#!/usr/bin/env python3
"""Shared, standard-library-only helpers for Agent Knowledge OS scripts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# Windows runners may default redirected stdout/stderr to a legacy code page.
# Every command emits Chinese paths and JSON, so make the CLI contract UTF-8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

SCHEMA_VERSION = "1.0"
SYSTEM_DIR = "99-系统·System"
INBOX_DIR = "00-收件箱·Inbox"
SOURCES_DIR = "01-原始素材·Sources"
CONCEPTS_DIR = "02-概念·Concepts"
METHODS_DIR = "03-方法论·Methodologies"
PERSONAL_DIR = "04-个人输出·Personal"
TOOLKIT_DIR = "05-工具集·Toolkit"
MOCS_DIR = "90-知识地图·MOCs"

ROOT_DIRS = (
    INBOX_DIR,
    SOURCES_DIR,
    CONCEPTS_DIR,
    METHODS_DIR,
    PERSONAL_DIR,
    TOOLKIT_DIR,
    MOCS_DIR,
    SYSTEM_DIR,
)

CORE_PLUGINS = (
    "file-explorer",
    "global-search",
    "backlink",
    "outgoing-link",
    "graph",
    "tag-pane",
    "properties",
    "templates",
    "file-recovery",
    "bases",
)

SOURCE_NAMES = {
    "个人表达": "个人表达·Personal",
    "文章和书籍": "文章与书籍·Reading",
    "用户问题": "用户问题·Questions",
    "会议与访谈": "会议与访谈·Interviews",
    "项目资料": "项目资料·Projects",
    "案例与数据": "案例与数据·Cases",
}

WORKFLOW_NAMES = {
    "内容创作": "内容创作·Content",
    "学习研究": "学习研究·Research",
    "工作决策": "工作决策·Decisions",
    "产品与业务": "产品与业务·Business",
    "项目复盘": "项目复盘·Reviews",
}

WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class KnowledgeOSError(ValueError):
    """Raised when an operation would violate a vault safety rule."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise KnowledgeOSError(f"文件不存在：{path}") from exc
    except json.JSONDecodeError as exc:
        raise KnowledgeOSError(f"JSON 格式错误：{path}: {exc}") from exc


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def contains_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        return "{{" in value or "}}" in value
    if isinstance(value, dict):
        return any(contains_placeholder(k) or contains_placeholder(v) for k, v in value.items())
    if isinstance(value, list):
        return any(contains_placeholder(item) for item in value)
    return False


def sanitize_component(value: str, fallback: str = "未命名") -> str:
    text = str(value).strip()
    text = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "-", text)
    text = re.sub(r"\s+", " ", text).strip(" .-")
    if not text:
        text = fallback
    if text.upper() in WINDOWS_RESERVED:
        text = f"{text}-item"
    return text[:80].rstrip(" .") or fallback


def bilingual_name(value: Any, index: int, english_fallback: str = "Domain") -> str:
    if isinstance(value, dict):
        chinese = sanitize_component(value.get("name_zh") or value.get("name") or f"领域{index}")
        english = sanitize_component(value.get("name_en") or english_fallback, english_fallback)
        return f"{chinese}·{english}"
    text = sanitize_component(str(value), f"领域{index}")
    if "·" in text:
        left, right = text.split("·", 1)
        return f"{sanitize_component(left)}·{sanitize_component(right, english_fallback)}"
    if text.isascii():
        return f"{text}·{text}"
    return f"{text}·{english_fallback}"


def source_folder(value: Any, index: int) -> str:
    if isinstance(value, str) and value in SOURCE_NAMES:
        return SOURCE_NAMES[value]
    return bilingual_name(value, index, "Source")


def workflow_folder(value: Any, index: int) -> str:
    if isinstance(value, str) and value in WORKFLOW_NAMES:
        return WORKFLOW_NAMES[value]
    return bilingual_name(value, index, "Workflow")


def safe_child(root: Path, relative: str | Path) -> Path:
    root_resolved = root.resolve()
    candidate = (root_resolved / relative).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise KnowledgeOSError(f"路径越出知识库：{relative}") from exc
    return candidate


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise KnowledgeOSError(f"{label}不能为空")
    return value.strip()


def normalize_config(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise KnowledgeOSError("配置必须是 JSON 对象")
    profile = payload.get("profile", payload)
    if not isinstance(profile, dict):
        raise KnowledgeOSError("profile 必须是 JSON 对象")

    workflows = profile.get("primary_workflows", [])
    domains = profile.get("domains", [])
    source_types = profile.get("source_types", [])
    asset_types = profile.get("asset_types", [])
    if not isinstance(workflows, list) or not 1 <= len(workflows) <= 3:
        raise KnowledgeOSError("primary_workflows 必须选择 1—3 项")
    if not isinstance(domains, list) or not 3 <= len(domains) <= 7:
        raise KnowledgeOSError("domains 必须包含 3—7 个长期领域")
    if not isinstance(source_types, list) or not source_types:
        raise KnowledgeOSError("source_types 至少选择一项")
    if not isinstance(asset_types, list):
        raise KnowledgeOSError("asset_types 必须是列表")
    required_assets = ["概念", "方法论"]
    for item in required_assets:
        if item not in asset_types:
            asset_types.append(item)

    review_policy = profile.get("review_policy") or {
        "default_days": 180,
        "tool_days": 60,
        "platform_rule_days": 30,
        "methodology_days": 180,
        "personal_values_expire": False,
    }
    privacy_policy = profile.get("privacy_policy") or {
        "redact": ["客户资料", "私人聊天", "账号", "密钥"],
        "read_only_paths": [],
        "ai_write_requires_confirmation": True,
    }
    obsidian = profile.get("obsidian") or {
        "app": "install_if_missing",
        "enable_core_plugins": True,
        "community_packs": [],
    }
    if not isinstance(obsidian, dict):
        raise KnowledgeOSError("obsidian 必须是 JSON 对象")
    app_mode = obsidian.get("app", "use_existing")
    if app_mode not in {"install_if_missing", "use_existing", "skip"}:
        raise KnowledgeOSError("obsidian.app 必须是 install_if_missing、use_existing 或 skip")
    community_packs = obsidian.get("community_packs", [])
    if not isinstance(community_packs, list) or any(item not in {"dataview", "templater"} for item in community_packs):
        raise KnowledgeOSError("obsidian.community_packs 只能包含 dataview 或 templater")
    obsidian = {
        "app": app_mode,
        "enable_core_plugins": bool(obsidian.get("enable_core_plugins", True)),
        "community_packs": list(dict.fromkeys(community_packs)),
    }

    config = {
        "schema_version": SCHEMA_VERSION,
        "onboarding": {
            "status": "complete",
            "version": int(payload.get("onboarding", {}).get("version", 1)),
            "completed_at": payload.get("onboarding", {}).get("completed_at") or utc_now(),
        },
        "profile": {
            "vault_name": _nonempty_string(profile.get("vault_name"), "vault_name"),
            "owner": _nonempty_string(profile.get("owner"), "owner"),
            "purpose": _nonempty_string(profile.get("purpose"), "purpose"),
            "primary_workflows": workflows,
            "domains": domains,
            "source_types": source_types,
            "asset_types": asset_types,
            "review_policy": review_policy,
            "privacy_policy": privacy_policy,
            "obsidian": obsidian,
        },
    }
    if contains_placeholder(config):
        raise KnowledgeOSError("配置中不能残留 {{PLACEHOLDER}}")
    return config


def yaml_list(items: Iterable[Any]) -> str:
    return "\n".join(f"  - {json.dumps(item, ensure_ascii=False)}" for item in items)


def render_wiki(config: dict[str, Any]) -> str:
    p = config["profile"]
    return f"""---
title: {json.dumps(p['vault_name'], ensure_ascii=False)}
owner: {json.dumps(p['owner'], ensure_ascii=False)}
schema_version: {json.dumps(config['schema_version'])}
onboarding_status: complete
---

# {p['vault_name']}

> 服务目标：{p['purpose']}

## 首要任务

{yaml_list(p['primary_workflows'])}

## 长期领域

{yaml_list([bilingual_name(item, i + 1) for i, item in enumerate(p['domains'])])}

## 知识流

`原始素材 → 候选知识 → 人工审核 → 正式概念/方法论 → 真实输出 → 反馈回流`

## 不可修改的铁律

1. 原始来源保留原貌并可追溯。
2. 候选只进入收件箱，正式知识必须人工晋升。
3. 不静默删除、移动、覆盖或解决冲突。
4. 写入后回读验证，整轮成功后才更新状态。
5. 敏感内容先脱敏；AI 写入遵守隐私边界。

## 复查策略

```json
{json.dumps(p['review_policy'], ensure_ascii=False, indent=2)}
```

## 隐私边界

```json
{json.dumps(p['privacy_policy'], ensure_ascii=False, indent=2)}
```
"""


def frontmatter_value(text: str, key: str) -> str | None:
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    match = re.search(rf"(?m)^{re.escape(key)}:\s*[\"']?(.+?)[\"']?\s*$", text[3:end])
    return match.group(1).strip() if match else None


def iter_markdown(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return (path for path in root.rglob("*.md") if not any(part.startswith(".") for part in path.parts))
