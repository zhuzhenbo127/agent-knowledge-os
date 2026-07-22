#!/usr/bin/env python3
"""Discover new or changed Markdown sources using content hashes and the ingest ledger."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import SOURCES_DIR, SYSTEM_DIR, KnowledgeOSError, iter_markdown, sha256_file


def latest_ledger(path: Path) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    if not path.exists():
        return latest
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise KnowledgeOSError(f"ingest ledger 第 {number} 行不是合法 JSON") from exc
        source = row.get("source_path")
        if isinstance(source, str):
            latest[source] = row
    return latest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True)
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument("--all", action="store_true", help="返回全部待处理来源，不应用单轮上限")
    args = parser.parse_args()
    try:
        vault = Path(args.vault).expanduser().resolve()
        source_root = vault / SOURCES_DIR
        if not source_root.is_dir():
            raise KnowledgeOSError(f"缺少来源目录：{SOURCES_DIR}")
        ledger = latest_ledger(vault / SYSTEM_DIR / "ingest-ledger.jsonl")
        pending = []
        processed = 0
        for path in sorted(iter_markdown(source_root), key=lambda item: (item.stat().st_mtime, item.as_posix())):
            relative = path.relative_to(vault).as_posix()
            digest = sha256_file(path)
            previous = ledger.get(relative)
            if previous and previous.get("source_sha256") == digest:
                processed += 1
                continue
            pending.append({
                "source_path": relative,
                "source_sha256": digest,
                "status": "changed" if previous else "new",
                "previous_outcome": previous.get("outcome") if previous else None,
                "bytes": path.stat().st_size,
            })
        selected = pending if args.all else pending[:max(0, args.limit)]
        print(json.dumps({
            "counts": {"total": processed + len(pending), "processed": processed, "pending": len(pending), "selected": len(selected)},
            "sources": selected,
            "has_more": len(selected) < len(pending),
        }, ensure_ascii=False, indent=2))
        return 0
    except (KnowledgeOSError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
