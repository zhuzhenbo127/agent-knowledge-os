#!/usr/bin/env python3
"""Verify one ingest outcome, append provenance, then update successful state."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from pathlib import Path

from common import (
    INBOX_DIR,
    SOURCES_DIR,
    SYSTEM_DIR,
    KnowledgeOSError,
    append_jsonl,
    atomic_write_json,
    frontmatter_value,
    load_json,
    safe_child,
    sha256_file,
    utc_now,
)

OUTCOMES = ("跳过·Skip", "保留原文·Preserve", "更新建议·Update", "候选草稿·Candidate")
LONG_SOURCE_BYTES = 200_000


def verify_coverage(path: Path, source_relative: str, source_hash: str, manifest_path: Path | None) -> dict | None:
    if manifest_path is None:
        if path.stat().st_size >= LONG_SOURCE_BYTES:
            raise KnowledgeOSError(f"来源超过 {LONG_SOURCE_BYTES} 字节，必须提供 --coverage 全文分块覆盖清单")
        return None
    manifest = load_json(manifest_path)
    if manifest.get("source_path") != source_relative:
        raise KnowledgeOSError("coverage source_path 与实际来源不一致")
    if manifest.get("source_sha256") != source_hash:
        raise KnowledgeOSError("coverage source_sha256 与实际来源不一致")
    size = path.stat().st_size
    if manifest.get("file_size") != size:
        raise KnowledgeOSError("coverage file_size 与实际来源不一致")
    ranges = manifest.get("ranges")
    if not isinstance(ranges, list) or not ranges:
        raise KnowledgeOSError("coverage ranges 不能为空")
    cursor = 0
    with path.open("rb") as handle:
        for index, item in enumerate(ranges, 1):
            if not isinstance(item, dict):
                raise KnowledgeOSError(f"coverage 第 {index} 块格式错误")
            start, end, declared = item.get("start"), item.get("end"), item.get("sha256")
            if not isinstance(start, int) or not isinstance(end, int) or start != cursor or end <= start or end > size:
                raise KnowledgeOSError(f"coverage 第 {index} 块存在缺口、重叠或越界")
            handle.seek(start)
            actual = hashlib.sha256(handle.read(end - start)).hexdigest()
            if actual != declared:
                raise KnowledgeOSError(f"coverage 第 {index} 块哈希不一致")
            cursor = end
    if cursor != size:
        raise KnowledgeOSError("coverage 未覆盖来源结尾")
    return {"file_size": size, "ranges": len(ranges), "manifest_sha256": sha256_file(manifest_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True)
    parser.add_argument("--source", required=True, help="Vault 内的来源相对路径")
    parser.add_argument("--outcome", choices=OUTCOMES, default="候选草稿·Candidate")
    parser.add_argument("--candidate", help="Candidate 结果对应的 Vault 内候选相对路径")
    parser.add_argument("--coverage", help="长文分块覆盖 JSON；超过 200000 字节时必填")
    parser.add_argument("--note", default="")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    try:
        vault = Path(args.vault).expanduser().resolve()
        source = safe_child(vault, args.source)
        try:
            source.relative_to(vault / SOURCES_DIR)
        except ValueError as exc:
            raise KnowledgeOSError("来源必须位于 01-原始素材·Sources") from exc
        if not source.is_file():
            raise KnowledgeOSError("来源文件不存在")
        source_hash = sha256_file(source)
        source_relative = source.relative_to(vault).as_posix()
        coverage = verify_coverage(source, source_relative, source_hash, Path(args.coverage).expanduser() if args.coverage else None)
        candidate_relative = None
        candidate_hash = None
        if args.outcome == "候选草稿·Candidate":
            if not args.candidate:
                raise KnowledgeOSError("Candidate 结果必须提供 --candidate")
            candidate = safe_child(vault, args.candidate)
            try:
                candidate.relative_to(vault / INBOX_DIR)
            except ValueError as exc:
                raise KnowledgeOSError("候选草稿只能位于 00-收件箱·Inbox") from exc
            if not candidate.is_file():
                raise KnowledgeOSError("候选文件不存在")
            text = candidate.read_text(encoding="utf-8")
            if frontmatter_value(text, "status") != "candidate":
                raise KnowledgeOSError("候选 frontmatter 必须包含 status: candidate")
            declared_source = frontmatter_value(text, "source_path")
            declared_hash = frontmatter_value(text, "source_sha256")
            if declared_source != args.source:
                raise KnowledgeOSError("候选 source_path 与实际来源不一致")
            if declared_hash != source_hash:
                raise KnowledgeOSError("候选 source_sha256 与来源全文哈希不一致")
            candidate_relative = candidate.relative_to(vault).as_posix()
            candidate_hash = sha256_file(candidate)
        elif args.candidate:
            raise KnowledgeOSError("只有 Candidate 结果可以提供 --candidate")

        run_id = args.run_id or str(uuid.uuid4())
        ledger = vault / SYSTEM_DIR / "ingest-ledger.jsonl"
        row = {
            "schema_version": "1.0",
            "run_id": run_id,
            "verified_at": utc_now(),
            "source_path": source_relative,
            "source_sha256": source_hash,
            "coverage": coverage,
            "outcome": args.outcome,
            "candidate_path": candidate_relative,
            "candidate_sha256": candidate_hash,
            "note": args.note,
        }
        append_jsonl(ledger, row)
        if json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1]) != row:
            raise KnowledgeOSError("ingest ledger 回读校验失败")

        state_path = vault / SYSTEM_DIR / "state.json"
        state = load_json(state_path) if state_path.exists() else {"schema_version": "1.0"}
        state.update({"last_successful_ingest": row["verified_at"], "last_verified_at": row["verified_at"], "last_run_id": run_id})
        atomic_write_json(state_path, state)
        print(json.dumps({"status": "verified", "record": row}, ensure_ascii=False, indent=2))
        return 0
    except (KnowledgeOSError, OSError, UnicodeDecodeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
