from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "skills" / "agent-knowledge-os" / "scripts"
SYSTEM = "99-系统·System"

sys.path.insert(0, str(SCRIPTS))
INSTALL_OBSIDIAN_SPEC = importlib.util.spec_from_file_location("install_obsidian", SCRIPTS / "install_obsidian.py")
assert INSTALL_OBSIDIAN_SPEC and INSTALL_OBSIDIAN_SPEC.loader
INSTALL_OBSIDIAN = importlib.util.module_from_spec(INSTALL_OBSIDIAN_SPEC)
INSTALL_OBSIDIAN_SPEC.loader.exec_module(INSTALL_OBSIDIAN)


def run_script(name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPTS / name), *map(str, args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def profile(**overrides: object) -> dict:
    value = {
        "profile": {
            "vault_name": "测试知识库",
            "owner": "测试作者",
            "purpose": "支持研究与内容创作",
            "primary_workflows": ["内容创作", "学习研究"],
            "domains": [
                {"name_zh": "人工智能", "name_en": "AI"},
                {"name_zh": "内容系统", "name_en": "Content"},
                {"name_zh": "个人业务", "name_en": "Business"},
            ],
            "source_types": ["个人表达", "文章和书籍", "用户问题"],
            "asset_types": ["概念", "方法论", "案例", "模板"],
            "review_policy": {"default_days": 180, "platform_rule_days": 30},
            "privacy_policy": {"redact": ["客户资料", "私人聊天", "密钥"], "read_only_paths": [], "ai_write_requires_confirmation": True},
            "obsidian": {"app": "install_if_missing", "enable_core_plugins": True, "community_packs": []},
        }
    }
    value["profile"].update(overrides)
    return value


class AgentKnowledgeOSTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.profile_path = self.root / "profile.json"
        self.profile_path.write_text(json.dumps(profile(), ensure_ascii=False), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def bootstrap(self, vault: Path | None = None, mode: str = "setup") -> Path:
        target = vault or self.root / "知识库"
        result = run_script("bootstrap.py", "--vault", target, "--profile", self.profile_path, "--mode", mode, "--confirmed")
        self.assertEqual(result.returncode, 0, result.stderr)
        return target

    def test_confirmation_is_required_and_writes_nothing(self) -> None:
        vault = self.root / "未确认"
        result = run_script("bootstrap.py", "--vault", vault, "--profile", self.profile_path)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(vault.exists())

    def test_setup_generates_complete_personalized_vault(self) -> None:
        vault = self.bootstrap()
        expected = [
            "00-收件箱·Inbox", "01-原始素材·Sources", "02-概念·Concepts",
            "03-方法论·Methodologies", "04-个人输出·Personal",
            "05-工具集·Toolkit", "90-知识地图·MOCs", SYSTEM,
        ]
        for name in expected:
            self.assertTrue((vault / name).is_dir(), name)
        config = json.loads((vault / SYSTEM / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["onboarding"]["status"], "complete")
        self.assertEqual(config["profile"]["obsidian"]["app"], "install_if_missing")
        self.assertNotIn("{{", json.dumps(config, ensure_ascii=False))
        self.assertTrue((vault / "02-概念·Concepts" / "人工智能·AI").is_dir())
        self.assertTrue((vault / "90-知识地图·MOCs" / "人工智能·AI·MOC.md").is_file())
        self.assertTrue(json.loads((vault / SYSTEM / "state.json").read_text(encoding="utf-8"))["onboarding_complete"])
        linted = run_script("lint_vault.py", "--vault", vault, "--json")
        self.assertEqual(linted.returncode, 0, linted.stdout + linted.stderr)
        self.assertEqual(json.loads(linted.stdout)["counts"]["error"], 0)

    def test_unsafe_user_names_are_sanitized_and_cannot_escape(self) -> None:
        custom = profile(
            domains=["AI/安全", "产品:增长", "CON"],
            source_types=["客户/访谈"],
        )
        self.profile_path.write_text(json.dumps(custom, ensure_ascii=False), encoding="utf-8")
        vault = self.bootstrap()
        domain_names = [p.name for p in (vault / "02-概念·Concepts").iterdir()]
        self.assertTrue(any("AI-安全" in name for name in domain_names))
        self.assertFalse((vault / "安全").exists())
        self.assertFalse(any("/" in name or ":" in name for name in domain_names))

    def test_setup_rejects_nonempty_directory(self) -> None:
        vault = self.root / "已有"
        vault.mkdir()
        marker = vault / "keep.md"
        marker.write_text("keep", encoding="utf-8")
        result = run_script("bootstrap.py", "--vault", vault, "--profile", self.profile_path, "--confirmed")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_adopt_preserves_existing_files_and_does_not_move_directories(self) -> None:
        vault = self.root / "旧库"
        legacy = vault / "My Notes"
        legacy.mkdir(parents=True)
        note = legacy / "keep.md"
        note.write_text("original", encoding="utf-8")
        self.bootstrap(vault, "adopt")
        self.assertEqual(note.read_text(encoding="utf-8"), "original")
        self.assertTrue(legacy.is_dir())

    def test_reconfigure_dry_run_then_backup_without_directory_migration(self) -> None:
        vault = self.bootstrap()
        patch_path = self.root / "patch.json"
        patch_path.write_text(json.dumps({"purpose": "支持产品决策", "review_policy": {"default_days": 90}}, ensure_ascii=False), encoding="utf-8")
        before = (vault / SYSTEM / "config.json").read_text(encoding="utf-8")
        preview = run_script("apply_profile.py", "--vault", vault, "--profile", patch_path, "--dry-run")
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertEqual((vault / SYSTEM / "config.json").read_text(encoding="utf-8"), before)
        applied = run_script("apply_profile.py", "--vault", vault, "--profile", patch_path, "--confirmed")
        self.assertEqual(applied.returncode, 0, applied.stderr)
        updated = json.loads((vault / SYSTEM / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(updated["profile"]["purpose"], "支持产品决策")
        candidate_template = vault / "00-收件箱·Inbox" / "候选知识模板·CANDIDATE_TEMPLATE.md"
        self.assertIn("review_after_days: 90", candidate_template.read_text(encoding="utf-8"))
        self.assertTrue(list((vault / SYSTEM).glob("config.backup.*.json")))

    def test_obsidian_core_merge_preserves_existing_and_restricted_mode(self) -> None:
        vault = self.bootstrap()
        obsidian = vault / ".obsidian"
        obsidian.mkdir()
        (obsidian / "core-plugins.json").write_text(json.dumps(["canvas", "global-search"]), encoding="utf-8")
        (obsidian / "app.json").write_text(json.dumps({"safeMode": True}), encoding="utf-8")
        result = run_script("setup_obsidian.py", "--vault", vault)
        self.assertEqual(result.returncode, 0, result.stderr)
        enabled = json.loads((obsidian / "core-plugins.json").read_text(encoding="utf-8"))
        self.assertIn("canvas", enabled)
        self.assertIn("bases", enabled)
        self.assertEqual(json.loads((obsidian / "app.json").read_text(encoding="utf-8")), {"safeMode": True})
        self.assertFalse((obsidian / "community-plugins.json").exists())

    def test_community_pack_requires_explicit_confirmation(self) -> None:
        vault = self.bootstrap()
        result = run_script("setup_obsidian.py", "--vault", vault, "--community-pack", "dataview")
        self.assertEqual(result.returncode, 2)
        self.assertFalse((vault / ".obsidian").exists())

    def test_obsidian_app_install_requires_confirmation_and_has_safe_dry_run(self) -> None:
        refused = run_script("install_obsidian.py", "--install", "--platform", "linux")
        self.assertEqual(refused.returncode, 2)
        self.assertIn("--confirmed", refused.stderr)

        preview = run_script("install_obsidian.py", "--install", "--dry-run", "--platform", "linux")
        self.assertEqual(preview.returncode, 0, preview.stderr)
        payload = json.loads(preview.stdout)
        self.assertEqual(payload["plan"]["strategy"], "official-appimage-user")
        self.assertEqual(payload["plan"]["source"], "https://obsidian.md/download")

    def test_obsidian_profile_rejects_unapproved_community_plugins(self) -> None:
        invalid = profile(obsidian={"app": "install_if_missing", "community_packs": ["unknown-plugin"]})
        self.profile_path.write_text(json.dumps(invalid, ensure_ascii=False), encoding="utf-8")
        result = run_script("bootstrap.py", "--vault", self.root / "invalid", "--profile", self.profile_path, "--confirmed")
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.root / "invalid").exists())

    def test_obsidian_release_asset_selection_rejects_untrusted_urls(self) -> None:
        prefix = "https://github.com/obsidianmd/obsidian-releases/releases/download/v1.2.3/"
        release = {"assets": [
            {"name": "Obsidian-1.2.3.dmg", "browser_download_url": prefix + "Obsidian-1.2.3.dmg"},
            {"name": "Obsidian-1.2.3.exe", "browser_download_url": prefix + "Obsidian-1.2.3.exe"},
            {"name": "Obsidian-1.2.3.AppImage", "browser_download_url": prefix + "Obsidian-1.2.3.AppImage"},
            {"name": "Obsidian-1.2.3-arm64.AppImage", "browser_download_url": prefix + "Obsidian-1.2.3-arm64.AppImage"},
        ]}
        self.assertEqual(INSTALL_OBSIDIAN.asset_for(release, "linux", "x86_64")["name"], "Obsidian-1.2.3.AppImage")
        self.assertEqual(INSTALL_OBSIDIAN.asset_for(release, "linux", "arm64")["name"], "Obsidian-1.2.3-arm64.AppImage")

        release["assets"][1]["browser_download_url"] = "https://example.com/Obsidian-1.2.3.exe"
        with self.assertRaises(INSTALL_OBSIDIAN.KnowledgeOSError):
            INSTALL_OBSIDIAN.asset_for(release, "windows")

    def test_discover_verify_and_hash_based_dedup(self) -> None:
        vault = self.bootstrap()
        source = vault / "01-原始素材·Sources" / "个人表达·Personal" / "长文.md"
        source.write_text("完整原文\n" * 5000, encoding="utf-8")
        first = run_script("discover_sources.py", "--vault", vault, "--all")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(first.stdout)["counts"]["pending"], 1)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        candidate = vault / "00-收件箱·Inbox" / "候选.md"
        relative_source = source.relative_to(vault).as_posix()
        candidate.write_text(
            f'---\ntype: candidate\nstatus: candidate\nsource_path: "{relative_source}"\nsource_sha256: "{digest}"\n---\n\n# 候选\n',
            encoding="utf-8",
        )
        verified = run_script(
            "verify_run.py", "--vault", vault, "--source", relative_source,
            "--candidate", candidate.relative_to(vault).as_posix(),
        )
        self.assertEqual(verified.returncode, 0, verified.stderr)
        second = run_script("discover_sources.py", "--vault", vault, "--all")
        self.assertEqual(json.loads(second.stdout)["counts"]["pending"], 0)
        source.write_text(source.read_text(encoding="utf-8") + "变化", encoding="utf-8")
        changed = json.loads(run_script("discover_sources.py", "--vault", vault, "--all").stdout)
        self.assertEqual(changed["sources"][0]["status"], "changed")

    def test_candidate_cannot_be_verified_in_formal_layer(self) -> None:
        vault = self.bootstrap()
        source = vault / "01-原始素材·Sources" / "个人表达·Personal" / "s.md"
        source.write_text("source", encoding="utf-8")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        candidate = vault / "02-概念·Concepts" / "人工智能·AI" / "bad.md"
        rel = source.relative_to(vault).as_posix()
        candidate.write_text(f'---\nstatus: candidate\nsource_path: "{rel}"\nsource_sha256: "{digest}"\n---\n', encoding="utf-8")
        result = run_script("verify_run.py", "--vault", vault, "--source", rel, "--candidate", candidate.relative_to(vault).as_posix())
        self.assertEqual(result.returncode, 2)
        self.assertEqual((vault / SYSTEM / "ingest-ledger.jsonl").read_text(encoding="utf-8"), "")

    def test_long_source_requires_and_verifies_gapless_coverage(self) -> None:
        vault = self.bootstrap()
        source = vault / "01-原始素材·Sources" / "个人表达·Personal" / "very-long.md"
        source.write_bytes(("长文内容\n" * 50000).encode("utf-8"))
        rel = source.relative_to(vault).as_posix()
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        without = run_script("verify_run.py", "--vault", vault, "--source", rel, "--outcome", "保留原文·Preserve")
        self.assertEqual(without.returncode, 2)
        data = source.read_bytes()
        middle = len(data) // 2
        coverage = {
            "source_path": rel,
            "source_sha256": digest,
            "file_size": len(data),
            "ranges": [
                {"start": 0, "end": middle, "sha256": hashlib.sha256(data[:middle]).hexdigest()},
                {"start": middle, "end": len(data), "sha256": hashlib.sha256(data[middle:]).hexdigest()},
            ],
        }
        manifest = self.root / "coverage.json"
        manifest.write_text(json.dumps(coverage, ensure_ascii=False), encoding="utf-8")
        verified = run_script(
            "verify_run.py", "--vault", vault, "--source", rel,
            "--outcome", "保留原文·Preserve", "--coverage", manifest,
        )
        self.assertEqual(verified.returncode, 0, verified.stderr)
        record = json.loads(verified.stdout)["record"]
        self.assertEqual(record["coverage"]["ranges"], 2)

    def test_lint_finds_expired_and_candidate_layer_violations_without_mutation(self) -> None:
        vault = self.bootstrap()
        note = vault / "02-概念·Concepts" / "人工智能·AI" / "过期.md"
        expired = (date.today() - timedelta(days=1)).isoformat()
        note.write_text(f"---\nstatus: candidate\nexpires_at: {expired}\n---\n# test\n", encoding="utf-8")
        before = note.read_bytes()
        result = run_script("lint_vault.py", "--vault", vault, "--json")
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        codes = {item["code"] for item in report["findings"]}
        self.assertIn("candidate-in-formal-layer", codes)
        self.assertIn("expired", codes)
        self.assertEqual(note.read_bytes(), before)

    def test_scan_discovers_existing_metadata(self) -> None:
        vault = self.bootstrap()
        note = vault / "02-概念·Concepts" / "人工智能·AI" / "概念.md"
        note.write_text("---\ntype: concept\ntags: [AI, 知识库]\n---\n# 概念", encoding="utf-8")
        result = run_script("scan_existing_vault.py", "--vault", vault)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertIn("人工智能·AI", report["detected"]["domains"])
        self.assertIn(["concept", 1], report["detected"]["note_types"])

    def test_publishable_repository_has_required_files_and_no_private_markers(self) -> None:
        required = [
            REPO / "README.md",
            REPO / "AGENTS.md",
            REPO / "INSTALL.md",
            REPO / "从零开始·USER_GUIDE.md",
            REPO / "LICENSE",
            REPO / "skills" / "agent-knowledge-os" / "SKILL.md",
            REPO / "skills" / "agent-knowledge-os" / "agents" / "openai.yaml",
            REPO / ".github" / "workflows" / "validate.yml",
        ]
        self.assertTrue(all(path.is_file() for path in required))
        public_files = [
            REPO / "README.md", REPO / "AGENTS.md", REPO / "INSTALL.md",
            REPO / "从零开始·USER_GUIDE.md", REPO / "skills" / "agent-knowledge-os",
        ]
        content = ""
        for entry in public_files:
            text_suffixes = {".md", ".py", ".yaml", ".yml", ".json", ".txt"}
            paths = [entry] if entry.is_file() else [
                p for p in entry.rglob("*")
                if p.is_file() and p.suffix.lower() in text_suffixes and "__pycache__" not in p.parts
            ]
            for path in paths:
                content += path.read_text(encoding="utf-8")
        forbidden = [
            "/" + "Users" + "/",
            "i" + "Cloud",
            "019e" + "cfd6-abe3-7f70-87b0-66b472fbf9a1",
            "课程" + "内容开发",
        ]
        for marker in forbidden:
            self.assertNotIn(marker, content)
        skill_text = required[5].read_text(encoding="utf-8")
        frontmatter = skill_text.split("---", 2)[1]
        keys = [line.split(":", 1)[0] for line in frontmatter.splitlines() if ":" in line]
        self.assertEqual(keys, ["name", "description"])
        self.assertIn("name: agent-knowledge-os", frontmatter)
        openai_yaml = required[6].read_text(encoding="utf-8")
        self.assertIn("$agent-knowledge-os", openai_yaml)
        short_line = next(line for line in openai_yaml.splitlines() if "short_description:" in line)
        short_description = short_line.split(":", 1)[1].strip().strip('"')
        self.assertGreaterEqual(len(short_description), 25)
        self.assertLessEqual(len(short_description), 64)

        install_protocol = (REPO / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("npx --yes skills@latest add", install_protocol)
        self.assertIn("--skill agent-knowledge-os", install_protocol)
        self.assertIn("Do not ask the user to log in to GitHub", install_protocol)
        customer_install = (REPO / "INSTALL.md").read_text(encoding="utf-8")
        self.assertIn("安装并使用这个 Skill：https://github.com/zhuzhenbo127/agent-knowledge-os", customer_install)


if __name__ == "__main__":
    unittest.main()
