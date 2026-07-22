#!/usr/bin/env python3
"""Read-only inventory of an existing Markdown or Obsidian vault."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

from common import (
    CONCEPTS_DIR,
    METHODS_DIR,
    PERSONAL_DIR,
    ROOT_DIRS,
    SOURCES_DIR,
    SYSTEM_DIR,
    KnowledgeOSError,
    atomic_write_json,
    iter_markdown,
    load_json,
)


def parse_frontmatter(text: str) -> dict[str, object]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end < 0:
        return {}
    result: dict[str, object] = {}
    current_list: str | None = None
    for line in text[4:end].splitlines():
        item = re.match(r"^\s+-\s+(.+)$", line)
        if item and current_list:
            cast = result.setdefault(current_list, [])
            if isinstance(cast, list):
                cast.append(item.group(1).strip(" \"'"))
            continue
        pair = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if pair:
            key, value = pair.groups()
            current_list = key if not value else None
            if value.startswith("[") and value.endswith("]"):
                result[key] = [part.strip(" \"'") for part in value[1:-1].split(",") if part.strip()]
            else:
                result[key] = value.strip(" \"'")
    return result


def child_dirs(root: Path, dirname: str) -> list[str]:
    target = root / dirname
    return sorted(path.name for path in target.iterdir() if path.is_dir() and not path.name.startswith(".")) if target.is_dir() else []


def scan(vault: Path) -> dict[str, object]:
    if not vault.is_dir():
        raise KnowledgeOSError("目标不是目录")
    markdown = list(iter_markdown(vault))
    tags: Counter[str] = Counter()
    fields: Counter[str] = Counter()
    types: Counter[str] = Counter()
    unreadable: list[str] = []
    for path in markdown:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            unreadable.append(path.relative_to(vault).as_posix())
            continue
        meta = parse_frontmatter(text)
        fields.update(meta.keys())
        value = meta.get("type")
        if isinstance(value, str) and value:
            types[value] += 1
        raw_tags = meta.get("tags", [])
        if isinstance(raw_tags, list):
            tags.update(str(tag) for tag in raw_tags)
        elif isinstance(raw_tags, str) and raw_tags:
            tags.update(part.strip() for part in raw_tags.split(",") if part.strip())

    top_dirs = sorted(path.name for path in vault.iterdir() if path.is_dir() and not path.name.startswith("."))
    missing = [name for name in ROOT_DIRS if not (vault / name).is_dir()]
    legacy = [name for name in top_dirs if name not in ROOT_DIRS]
    config_path = vault / SYSTEM_DIR / "config.json"
    existing_config = None
    config_error = None
    if config_path.exists():
        try:
            existing_config = load_json(config_path)
        except KnowledgeOSError as exc:
            config_error = str(exc)

    return {
        "vault": str(vault.resolve()),
        "counts": {
            "markdown": len(markdown),
            "top_level_directories": len(top_dirs),
            "unreadable_markdown": len(unreadable),
        },
        "detected": {
            "obsidian": (vault / ".obsidian").is_dir(),
            "domains": sorted(set(child_dirs(vault, CONCEPTS_DIR) + child_dirs(vault, METHODS_DIR))),
            "source_types": child_dirs(vault, SOURCES_DIR),
            "personal_workflows": child_dirs(vault, PERSONAL_DIR),
            "top_tags": tags.most_common(30),
            "frontmatter_fields": fields.most_common(30),
            "note_types": types.most_common(30),
        },
        "architecture": {
            "present": [name for name in ROOT_DIRS if (vault / name).is_dir()],
            "missing": missing,
            "unmapped_existing_directories": legacy,
        },
        "configuration": {
            "present": config_path.exists(),
            "valid_json": config_path.exists() and config_error is None,
            "error": config_error,
            "profile": existing_config.get("profile") if isinstance(existing_config, dict) else None,
        },
        "risks": {
            "unreadable_files": unreadable,
            "automatic_moves_allowed": False,
            "needs_migration_plan": bool(legacy or missing),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True)
    parser.add_argument("--output", help="可选：把扫描报告写到 Vault 外部或临时路径")
    args = parser.parse_args()
    try:
        report = scan(Path(args.vault).expanduser())
        if args.output:
            atomic_write_json(Path(args.output).expanduser(), report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (KnowledgeOSError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
