#!/usr/bin/env python3
"""Report architecture, provenance, staleness, link, and safety issues without mutating the vault."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from common import (
    INBOX_DIR,
    ROOT_DIRS,
    SOURCES_DIR,
    SYSTEM_DIR,
    KnowledgeOSError,
    contains_placeholder,
    frontmatter_value,
    iter_markdown,
    load_json,
    safe_child,
    sha256_file,
)

FORMAL_DIRS = ("02-概念·Concepts", "03-方法论·Methodologies", "04-个人输出·Personal", "05-工具集·Toolkit")
WIKILINK = re.compile(r"\[\[([^\]|#]+)")
INVALID_PATH = re.compile(r"[<>:\"|?*\x00-\x1f]")


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None


def issue(level: str, code: str, path: str, message: str) -> dict[str, str]:
    return {"level": level, "code": code, "path": path, "message": message}


def run_lint(vault: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for directory in ROOT_DIRS:
        if not (vault / directory).is_dir():
            findings.append(issue("error", "missing-directory", directory, "缺少固定架构目录"))

    config_path = vault / SYSTEM_DIR / "config.json"
    config = None
    if not config_path.exists():
        findings.append(issue("error", "missing-config", f"{SYSTEM_DIR}/config.json", "缺少正式配置"))
    else:
        try:
            config = load_json(config_path)
            if contains_placeholder(config):
                findings.append(issue("error", "placeholder", str(config_path.relative_to(vault)), "配置残留占位符"))
            if config.get("onboarding", {}).get("status") != "complete":
                findings.append(issue("error", "onboarding-incomplete", str(config_path.relative_to(vault)), "引导状态不是 complete"))
        except KnowledgeOSError as exc:
            findings.append(issue("error", "invalid-config", str(config_path.relative_to(vault)), str(exc)))

    notes = list(iter_markdown(vault))
    by_stem: dict[str, list[Path]] = {}
    texts: dict[Path, str] = {}
    incoming: dict[Path, int] = {path: 0 for path in notes}
    for path in notes:
        by_stem.setdefault(path.stem, []).append(path)
        relative = path.relative_to(vault).as_posix()
        if any(INVALID_PATH.search(part.replace("·", "")) for part in path.relative_to(vault).parts):
            findings.append(issue("error", "cross-platform-path", relative, "路径包含 Windows 不支持的字符"))
        try:
            texts[path] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(issue("error", "encoding", relative, "Markdown 不是 UTF-8"))

    for path, text in texts.items():
        relative = path.relative_to(vault).as_posix()
        status = frontmatter_value(text, "status")
        is_template = "template" in path.stem.lower() or any("模板" in part for part in path.relative_to(vault).parts)
        if status == "candidate" and not is_template:
            try:
                path.relative_to(vault / INBOX_DIR)
            except ValueError:
                findings.append(issue("error", "candidate-outside-inbox", relative, "候选知识位于正式层或其他目录"))
        if any(relative.startswith(prefix + "/") for prefix in FORMAL_DIRS) and status == "candidate" and not is_template:
            findings.append(issue("error", "candidate-in-formal-layer", relative, "正式层不能包含 candidate 状态"))

        source_path = frontmatter_value(text, "source_path")
        declared_hash = frontmatter_value(text, "source_sha256")
        if status == "candidate" and not is_template:
            if not source_path or not declared_hash:
                findings.append(issue("error", "candidate-provenance", relative, "候选缺少 source_path 或 source_sha256"))
            else:
                try:
                    source = safe_child(vault, source_path)
                    source.relative_to(vault / SOURCES_DIR)
                    if not source.is_file():
                        findings.append(issue("error", "missing-source", relative, f"来源不存在：{source_path}"))
                    elif sha256_file(source) != declared_hash:
                        findings.append(issue("warning", "source-drift", relative, "来源全文哈希已变化，需要重新审核"))
                except (KnowledgeOSError, ValueError):
                    findings.append(issue("error", "unsafe-source-path", relative, "source_path 不在来源层或越出 Vault"))

        expires = parse_date(frontmatter_value(text, "expires_at"))
        review_after = frontmatter_value(text, "review_after_days")
        reviewed = parse_date(frontmatter_value(text, "reviewed_at") or frontmatter_value(text, "updated"))
        if expires and expires < date.today():
            findings.append(issue("warning", "expired", relative, f"知识已于 {expires.isoformat()} 过期"))
        if review_after and reviewed:
            try:
                due = reviewed + timedelta(days=int(review_after))
                if due < date.today():
                    findings.append(issue("warning", "review-due", relative, f"知识应于 {due.isoformat()} 前复查"))
            except ValueError:
                findings.append(issue("warning", "invalid-review-days", relative, "review_after_days 不是整数"))

        links = WIKILINK.findall(text)
        for link in links:
            target_name = Path(link.strip()).stem
            candidates = by_stem.get(target_name, [])
            if not candidates:
                findings.append(issue("warning", "unresolved-link", relative, f"未解析双链：{link.strip()}"))
            else:
                for target in candidates:
                    incoming[target] += 1
    # Compute orphans only after every inbound link has been counted.
    for path, count in incoming.items():
        relative = path.relative_to(vault).as_posix()
        is_template = "template" in path.stem.lower() or any("模板" in part for part in path.relative_to(vault).parts)
        if count == 0 and not is_template and not WIKILINK.findall(texts.get(path, "")) and any(relative.startswith(prefix + "/") for prefix in FORMAL_DIRS):
            findings.append(issue("warning", "possible-orphan", relative, "正式知识无入链也无出链"))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="有 warning 时也返回非零")
    args = parser.parse_args()
    try:
        vault = Path(args.vault).expanduser().resolve()
        if not vault.is_dir():
            raise KnowledgeOSError("Vault 目录不存在")
        findings = run_lint(vault)
        counts = {level: sum(1 for item in findings if item["level"] == level) for level in ("error", "warning")}
        report = {"vault": str(vault), "counts": counts, "findings": findings, "mutated": False}
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"errors={counts['error']} warnings={counts['warning']}")
            for item in findings:
                print(f"[{item['level']}] {item['code']} {item['path']}: {item['message']}")
        return 1 if counts["error"] or (args.strict and counts["warning"]) else 0
    except (KnowledgeOSError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
