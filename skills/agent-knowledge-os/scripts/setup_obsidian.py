#!/usr/bin/env python3
"""Merge safe Obsidian core settings and optionally install approved community packs."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from common import CORE_PLUGINS, KnowledgeOSError, atomic_write_json, load_json, utc_now

COMMUNITY_PACKS = {
    "dataview": "dataview",
    "templater": "templater-obsidian",
}


def merge_core(obsidian_dir: Path) -> dict[str, object]:
    obsidian_dir.mkdir(parents=True, exist_ok=True)
    path = obsidian_dir / "core-plugins.json"
    existing: list[str] = []
    if path.exists():
        value = load_json(path)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise KnowledgeOSError(".obsidian/core-plugins.json 不是字符串数组，拒绝覆盖")
        existing = value
    merged = list(dict.fromkeys([*existing, *CORE_PLUGINS]))
    backup = None
    if path.exists() and merged != existing:
        backup = obsidian_dir / f"core-plugins.backup.{utc_now().replace(':', '-')}.json"
        atomic_write_json(backup, existing)
    atomic_write_json(path, merged)
    reread = load_json(path)
    if reread != merged:
        raise KnowledgeOSError("核心插件配置回读校验失败")
    return {"enabled": list(CORE_PLUGINS), "preserved": [item for item in existing if item not in CORE_PLUGINS], "backup": backup.name if backup else None}


def enable_core_with_cli(vault_name: str) -> bool:
    executable = shutil.which("obsidian")
    if not executable:
        return False
    for plugin_id in CORE_PLUGINS:
        completed = subprocess.run(
            [executable, f"vault={vault_name}", "plugin:enable", f"id={plugin_id}"],
            capture_output=True, text=True, timeout=15, check=False,
        )
        if completed.returncode != 0:
            return False
    return True


def install_pack(vault_name: str, pack: str) -> dict[str, str]:
    plugin_id = COMMUNITY_PACKS[pack]
    executable = shutil.which("obsidian")
    if not executable:
        raise KnowledgeOSError(f"已选择 {pack}，但未找到 Obsidian CLI；未关闭 Restricted Mode，也未安装插件")
    status = subprocess.run(
        [executable, f"vault={vault_name}", "plugins:restrict"],
        capture_output=True, text=True, timeout=30, check=False,
    )
    was_restricted = "on" in (status.stdout or "").lower() or "true" in (status.stdout or "").lower()
    unrestricted = subprocess.run(
        [executable, f"vault={vault_name}", "plugins:restrict", "off"],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if unrestricted.returncode != 0:
        detail = (unrestricted.stderr or unrestricted.stdout).strip()
        raise KnowledgeOSError(f"无法在用户已确认后关闭 Restricted Mode：{detail}")
    command = [executable, f"vault={vault_name}", "plugin:install", f"id={plugin_id}", "enable"]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
    if completed.returncode != 0:
        if was_restricted:
            subprocess.run(
                [executable, f"vault={vault_name}", "plugins:restrict", "on"],
                capture_output=True, text=True, timeout=30, check=False,
            )
        detail = (completed.stderr or completed.stdout).strip()
        raise KnowledgeOSError(f"Obsidian CLI 安装 {pack} 失败：{detail}")
    return {"pack": pack, "plugin_id": plugin_id, "status": "installed"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True)
    parser.add_argument("--vault-name", help="Obsidian 中显示的 Vault 名称；默认使用目录名")
    parser.add_argument("--community-pack", choices=tuple(COMMUNITY_PACKS), action="append", default=[])
    parser.add_argument("--community-confirmed", action="store_true", help="确认用户明确选择了社区插件")
    parser.add_argument("--no-cli", action="store_true", help="跳过 Obsidian CLI，直接安全合并核心配置")
    args = parser.parse_args()
    try:
        vault = Path(args.vault).expanduser().resolve()
        if not vault.is_dir():
            raise KnowledgeOSError("Vault 目录不存在")
        if args.community_pack and not args.community_confirmed:
            raise KnowledgeOSError("社区插件必须明确选择；请确认后添加 --community-confirmed")
        obsidian_dir = vault / ".obsidian"
        existed = obsidian_dir.exists()
        strategy = "config-merge"
        if existed and not args.no_cli and enable_core_with_cli(args.vault_name or vault.name):
            strategy = "obsidian-cli+config-verify"
        core = merge_core(obsidian_dir)
        core["strategy"] = strategy
        community = [install_pack(args.vault_name or vault.name, pack) for pack in dict.fromkeys(args.community_pack)]
        print(json.dumps({"status": "complete", "core": core, "community": community}, ensure_ascii=False, indent=2))
        return 0
    except (KnowledgeOSError, OSError, subprocess.SubprocessError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
