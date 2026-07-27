#!/usr/bin/env python3
"""Detect or install Obsidian from official release channels after confirmation."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from common import KnowledgeOSError


RELEASE_API = "https://api.github.com/repos/obsidianmd/obsidian-releases/releases/latest"
OFFICIAL_DOWNLOAD = "https://obsidian.md/download"
ALLOWED_ASSET_HOST = "github.com"
ALLOWED_ASSET_PREFIX = "/obsidianmd/obsidian-releases/releases/download/"


def current_system(override: str | None = None) -> str:
    value = override or platform.system()
    mapping = {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}
    if value in mapping:
        return mapping[value]
    if value in mapping.values():
        return value
    raise KnowledgeOSError(f"不支持的操作系统：{value}")


def detected_paths(system_name: str, home: Path | None = None) -> list[Path]:
    user_home = (home or Path.home()).expanduser()
    if system_name == "macos":
        return [Path("/Applications/Obsidian.app"), user_home / "Applications" / "Obsidian.app"]
    if system_name == "windows":
        candidates: list[Path] = []
        for variable in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
            value = os.environ.get(variable)
            if value:
                candidates.append(Path(value) / "Obsidian" / "Obsidian.exe")
        return candidates
    return [
        user_home / ".local" / "bin" / "obsidian",
        Path("/usr/bin/obsidian"),
        Path("/snap/bin/obsidian"),
    ]


def detect(system_name: str, home: Path | None = None) -> dict[str, Any]:
    executable = shutil.which("obsidian")
    if executable:
        return {"installed": True, "location": executable, "method": "command"}
    for path in detected_paths(system_name, home):
        if path.exists():
            return {"installed": True, "location": str(path), "method": "application"}
    return {"installed": False, "location": None, "method": None}


def choose_strategy(system_name: str) -> str:
    if system_name == "macos":
        return "homebrew-cask" if shutil.which("brew") else "official-dmg-user"
    if system_name == "windows":
        return "winget" if shutil.which("winget") else "official-exe"
    return "official-appimage-user"


def plan(system_name: str) -> dict[str, Any]:
    strategy = choose_strategy(system_name)
    actions = {
        "homebrew-cask": ["brew", "install", "--cask", "obsidian"],
        "official-dmg-user": ["下载 Obsidian 官方 DMG", "验证代码签名", "安装到 ~/Applications/Obsidian.app"],
        "winget": ["winget", "install", "--id", "Obsidian.Obsidian", "--exact", "--source", "winget", "--silent"],
        "official-exe": ["下载 Obsidian 官方 EXE", "验证 Authenticode 签名", "静默运行安装器"],
        "official-appimage-user": ["下载 Obsidian 官方 AppImage", "安装到 ~/.local/bin/obsidian"],
    }
    return {
        "system": system_name,
        "strategy": strategy,
        "scope": "user" if strategy.endswith("-user") or strategy == "official-exe" else "system-package-manager",
        "actions": actions[strategy],
        "source": OFFICIAL_DOWNLOAD,
    }


def run(command: list[str], timeout: int = 600) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise KnowledgeOSError(f"命令执行失败：{' '.join(command[:4])}\n{detail}")
    return completed


def latest_release() -> dict[str, Any]:
    request = urllib.request.Request(
        RELEASE_API,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "agent-knowledge-os"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise KnowledgeOSError(f"无法获取 Obsidian 官方版本信息：{exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("assets"), list):
        raise KnowledgeOSError("Obsidian 官方版本信息格式异常")
    return payload


def asset_for(release: dict[str, Any], system_name: str, machine_override: str | None = None) -> dict[str, Any]:
    machine = (machine_override or platform.machine()).lower()
    assets = release["assets"]
    if system_name == "macos":
        matches = [item for item in assets if str(item.get("name", "")).endswith(".dmg")]
    elif system_name == "windows":
        matches = [item for item in assets if str(item.get("name", "")).endswith(".exe")]
    elif machine in {"arm64", "aarch64"}:
        matches = [item for item in assets if str(item.get("name", "")).endswith("arm64.AppImage")]
    else:
        matches = [
            item for item in assets
            if str(item.get("name", "")).endswith(".AppImage")
            and "arm64" not in str(item.get("name", "")).lower()
        ]
    if len(matches) != 1:
        raise KnowledgeOSError(f"未能唯一确定 {system_name} 的 Obsidian 官方安装包")
    asset = matches[0]
    url = str(asset.get("browser_download_url", ""))
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_ASSET_HOST or not parsed.path.startswith(ALLOWED_ASSET_PREFIX):
        raise KnowledgeOSError("Obsidian 安装包不是允许的官方 GitHub Release 地址")
    return asset


def download_asset(asset: dict[str, Any], destination: Path) -> None:
    request = urllib.request.Request(
        str(asset["browser_download_url"]),
        headers={"User-Agent": "agent-knowledge-os"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise KnowledgeOSError(f"Obsidian 官方安装包下载失败：{exc}") from exc
    expected = asset.get("size")
    if isinstance(expected, int) and expected > 0 and destination.stat().st_size != expected:
        raise KnowledgeOSError("Obsidian 安装包大小校验失败")


def install_macos_dmg(asset_path: Path, home: Path) -> str:
    applications = home / "Applications"
    target = applications / "Obsidian.app"
    applications.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="agent-knowledge-os-mount-") as mount_name:
        mount = Path(mount_name)
        run(["hdiutil", "attach", str(asset_path), "-nobrowse", "-readonly", "-mountpoint", str(mount)])
        try:
            source = mount / "Obsidian.app"
            if not source.is_dir():
                raise KnowledgeOSError("DMG 中未找到 Obsidian.app")
            run(["codesign", "--verify", "--deep", "--strict", str(source)])
            run(["spctl", "--assess", "--type", "execute", str(source)])
            run(["ditto", str(source), str(target)])
        finally:
            subprocess.run(["hdiutil", "detach", str(mount)], capture_output=True, check=False)
    return str(target)


def install_windows_exe(asset_path: Path) -> str:
    escaped = str(asset_path).replace("'", "''")
    verify = (
        f"$s=Get-AuthenticodeSignature -LiteralPath '{escaped}'; "
        "if ($s.Status -ne 'Valid') { Write-Error $s.Status; exit 2 }"
    )
    run(["powershell", "-NoProfile", "-NonInteractive", "-Command", verify], timeout=60)
    run([str(asset_path), "/S"], timeout=600)
    return "Obsidian user installation"


def install_linux_appimage(asset_path: Path, home: Path) -> str:
    with asset_path.open("rb") as handle:
        if handle.read(4) != b"\x7fELF":
            raise KnowledgeOSError("AppImage 文件头校验失败")
    target = home / ".local" / "bin" / "obsidian"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(asset_path, target)
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return str(target)


def install(system_name: str, strategy: str, home: Path) -> dict[str, Any]:
    if strategy == "homebrew-cask":
        run(["brew", "install", "--cask", "obsidian"])
        return {"strategy": strategy, "target": "/Applications/Obsidian.app"}
    if strategy == "winget":
        run([
            "winget", "install", "--id", "Obsidian.Obsidian", "--exact", "--source", "winget",
            "--silent", "--accept-package-agreements", "--accept-source-agreements",
        ])
        return {"strategy": strategy, "target": "Obsidian.Obsidian"}

    release = latest_release()
    asset = asset_for(release, system_name)
    suffix = Path(str(asset["name"])).suffix
    with tempfile.TemporaryDirectory(prefix="agent-knowledge-os-obsidian-") as temp_name:
        package = Path(temp_name) / f"Obsidian{suffix}"
        download_asset(asset, package)
        if strategy == "official-dmg-user":
            target = install_macos_dmg(package, home)
        elif strategy == "official-exe":
            target = install_windows_exe(package)
        else:
            target = install_linux_appimage(package, home)
    return {"strategy": strategy, "target": target, "version": release.get("tag_name")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="只检查是否已安装（默认动作）")
    parser.add_argument("--install", action="store_true", help="自动安装 Obsidian")
    parser.add_argument("--confirmed", action="store_true", help="确认用户已授权安装 Obsidian")
    parser.add_argument("--dry-run", action="store_true", help="只输出安装策略，不下载或执行")
    parser.add_argument("--platform", choices=("macos", "windows", "linux"), help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.check and args.install:
            raise KnowledgeOSError("--check 与 --install 不能同时使用")
        if args.install and not args.dry_run and not args.confirmed:
            raise KnowledgeOSError("安装 Obsidian 必须先获得用户明确授权；确认后添加 --confirmed")
        system_name = current_system(args.platform)
        status = detect(system_name)
        install_plan = plan(system_name)
        if status["installed"]:
            print(json.dumps({"status": "already-installed", **status, "plan": install_plan}, ensure_ascii=False, indent=2))
            return 0
        if not args.install or args.dry_run:
            print(json.dumps({"status": "not-installed", **status, "plan": install_plan}, ensure_ascii=False, indent=2))
            return 0
        result = install(system_name, str(install_plan["strategy"]), Path.home())
        print(json.dumps({"status": "installed", "system": system_name, **result}, ensure_ascii=False, indent=2))
        return 0
    except (KnowledgeOSError, OSError, subprocess.SubprocessError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
