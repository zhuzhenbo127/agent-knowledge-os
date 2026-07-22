#!/usr/bin/env python3
"""Preview or apply confirmed personalization changes without moving directories."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path

from common import (
    CONCEPTS_DIR,
    METHODS_DIR,
    MOCS_DIR,
    SOURCES_DIR,
    SYSTEM_DIR,
    KnowledgeOSError,
    append_jsonl,
    atomic_write_json,
    atomic_write_text,
    bilingual_name,
    load_json,
    normalize_config,
    render_wiki,
    source_folder,
    utc_now,
)


def merge_dict(base: dict, patch: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_dict(result[key], value)
        else:
            result[key] = value
    return result


def differences(before: object, after: object, prefix: str = "") -> list[dict[str, object]]:
    if isinstance(before, dict) and isinstance(after, dict):
        result: list[dict[str, object]] = []
        for key in sorted(set(before) | set(after)):
            path = f"{prefix}.{key}" if prefix else key
            result.extend(differences(before.get(key), after.get(key), path))
        return result
    if before != after:
        return [{"field": prefix, "before": before, "after": after}]
    return []


def migration_plan(vault: Path, config: dict) -> list[dict[str, str]]:
    plan: list[dict[str, str]] = []
    for index, domain in enumerate(config["profile"]["domains"], 1):
        name = bilingual_name(domain, index)
        for parent in (CONCEPTS_DIR, METHODS_DIR):
            if not (vault / parent / name).exists():
                plan.append({"action": "create_directory", "path": f"{parent}/{name}"})
        moc = f"{MOCS_DIR}/{name}·MOC.md"
        if not (vault / moc).exists():
            plan.append({"action": "create_moc", "path": moc})
    for index, source_type in enumerate(config["profile"]["source_types"], 1):
        name = source_folder(source_type, index)
        if not (vault / SOURCES_DIR / name).exists():
            plan.append({"action": "create_directory", "path": f"{SOURCES_DIR}/{name}"})
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True)
    parser.add_argument("--profile", required=True, help="完整配置或仅包含待修改字段的 profile JSON")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--confirmed", action="store_true")
    args = parser.parse_args()
    try:
        vault = Path(args.vault).expanduser().resolve()
        config_path = vault / SYSTEM_DIR / "config.json"
        current = load_json(config_path)
        patch = load_json(Path(args.profile).expanduser())
        patch_profile = patch.get("profile", patch)
        if not isinstance(patch_profile, dict):
            raise KnowledgeOSError("待修改配置必须是 JSON 对象")
        merged_payload = {
            "onboarding": current.get("onboarding", {}),
            "profile": merge_dict(current.get("profile", {}), patch_profile),
        }
        updated = normalize_config(merged_payload)
        updated["onboarding"]["version"] = int(current.get("onboarding", {}).get("version", 1)) + 1
        updated["onboarding"]["completed_at"] = utc_now()
        diff = differences(current, updated)
        plan = migration_plan(vault, updated)
        report = {"changes": diff, "migration_plan": plan, "directories_changed": False}
        if args.dry_run:
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        stamp = utc_now().replace(":", "-")
        backup = vault / SYSTEM_DIR / f"config.backup.{stamp}.json"
        wiki_path = vault / "知识库说明·WIKI.md"
        wiki_backup = vault / SYSTEM_DIR / f"WIKI.backup.{stamp}.md"
        atomic_write_json(backup, current)
        if wiki_path.exists():
            atomic_write_text(wiki_backup, wiki_path.read_text(encoding="utf-8"))
        template_backups: dict[Path, str] = {}
        try:
            atomic_write_json(config_path, updated)
            atomic_write_text(wiki_path, render_wiki(updated))
            review_days = int(updated["profile"]["review_policy"].get("default_days", 180))
            for relative in (
                "00-收件箱·Inbox/候选知识模板·CANDIDATE_TEMPLATE.md",
                "05-工具集·Toolkit/笔记模板·Note Templates/候选知识模板·CANDIDATE.md",
            ):
                template = vault / relative
                if template.exists():
                    text = template.read_text(encoding="utf-8")
                    template_backups[template] = text
                    text = re.sub(r"(?m)^review_after_days:\s*\d+\s*$", f"review_after_days: {review_days}", text)
                    atomic_write_text(template, text)
            append_jsonl(vault / SYSTEM_DIR / "profile-change-log.jsonl", {
                "at": utc_now(), "changes": diff, "migration_plan": plan, "backup": backup.name
            })
        except Exception:
            atomic_write_json(config_path, current)
            if wiki_backup.exists():
                atomic_write_text(wiki_path, wiki_backup.read_text(encoding="utf-8"))
            for template, text in template_backups.items():
                atomic_write_text(template, text)
            raise
        report.update({"status": "complete", "backup": backup.name})
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (KnowledgeOSError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
