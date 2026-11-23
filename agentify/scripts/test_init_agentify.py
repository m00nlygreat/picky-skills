"""Exercise agentify initialization against isolated workspaces."""

import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


SCRIPT = Path(__file__).with_name("init_agentify.py")
LINKS = ("SOUL.md", "MEMORY.md", "HEARTBEAT.md", "memory/INDEX.md")


class InitAgentifyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="agentify-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def run_init(self, *options, success=True):
        result = subprocess.run(
            [sys.executable, "-B", "-X", "utf8", str(SCRIPT), "--project-root", str(self.root), *options],
            capture_output=True, text=True, encoding="utf-8",
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def snapshot(self):
        return {
            path.relative_to(self.root): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in self.root.rglob("*")
            if path.is_file()
        }

    def test_empty_workspace_and_idempotent_rerun(self):
        self.run_init()
        expected = {"AGENTS.md", *LINKS}
        before = self.snapshot()
        self.assertEqual({path.as_posix() for path in before}, expected)
        guidance = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        for link in LINKS:
            self.assertIn(f"]({link})", guidance)
            self.assertTrue((self.root / link).is_file())
        self.assertNotIn("<!-- agentify:", guidance)
        self.assertNotIn("](USER.md)", guidance)
        self.assertIn("](memory/INDEX.md)", (self.root / "MEMORY.md").read_text(encoding="utf-8"))
        self.run_init()
        self.assertEqual(self.snapshot(), before)

    def test_user_module_is_idempotent_and_repairs_missing_profile(self):
        self.run_init("--with-user")
        profile = self.root / "USER.md"
        expected_profile = (SCRIPT.parent.parent / "assets" / "USER.md").read_bytes()
        self.assertEqual(profile.read_bytes(), expected_profile)
        guidance = self.root / "AGENTS.md"
        self.assertIn(b"](USER.md)", guidance.read_bytes())

        before = self.snapshot()
        self.run_init("--with-user")
        self.run_init()
        self.assertEqual(self.snapshot(), before)

        profile.unlink()
        self.run_init()
        self.assertEqual(profile.read_bytes(), expected_profile)
        self.assertEqual(self.snapshot()[Path("AGENTS.md")], before[Path("AGENTS.md")])

    def test_opt_in_connects_existing_profile_without_overwriting_it(self):
        profile = self.root / "USER.md"
        existing_profile = "# 기존 프로필\r\n".encode("utf-8")
        profile.write_bytes(existing_profile)

        self.run_init()
        guidance = self.root / "AGENTS.md"
        original = guidance.read_bytes()
        self.assertNotIn(b"](USER.md)", original)

        self.run_init("--with-user")
        connected = guidance.read_bytes()
        self.assertEqual(connected.count(b"](USER.md)"), 1)
        previous_lines = [line for line in connected.splitlines(keepends=True) if b"](USER.md)" not in line]
        self.assertEqual(b"".join(previous_lines), original)
        self.assertEqual(profile.read_bytes(), existing_profile)

    def test_invalid_profile_path_fails_before_writing_when_selected(self):
        profile = self.root / "USER.md"
        profile.mkdir()
        self.assertIn("Expected a file", self.run_init("--with-user", success=False).stderr)
        self.assertEqual(list(self.root.iterdir()), [profile])
        self.run_init()
        self.assertTrue(profile.is_dir())

    def test_keeps_existing_documents_and_repairs_only_missing_parts(self):
        guidance = self.root / "AGENTS.md"
        user_guidance = "\ufeff# 프로젝트\r\n\r\n~~~md\r\n<!-- agentify:start -->\r\n~~~\r\n"
        guidance.write_bytes(user_guidance.encode("utf-8"))
        soul = self.root / "SOUL.md"
        soul.write_bytes("# 기존 정체성\r\n".encode("utf-8"))
        self.run_init()
        connected = guidance.read_bytes().decode("utf-8")
        self.assertTrue(connected.startswith(user_guidance))
        self.assertNotIn("\n", connected.replace("\r\n", ""))

        memory = self.root / "MEMORY.md"
        memory.write_bytes("# 확정한 프로젝트 결정\r\n".encode("utf-8"))
        (self.root / "HEARTBEAT.md").unlink()
        broken = "".join(line for line in connected.splitlines(keepends=True) if "](HEARTBEAT.md)" not in line)
        manual_rule = "- 기존 운영 방식에 맞춘 규칙\r\n"
        guidance.write_bytes((broken + manual_rule).encode("utf-8"))
        self.run_init()
        repaired = guidance.read_bytes().decode("utf-8")
        self.assertEqual(repaired.count("](HEARTBEAT.md)"), 1)
        self.assertIn(manual_rule, repaired)
        self.assertTrue((self.root / "HEARTBEAT.md").is_file())
        self.assertEqual(soul.read_bytes(), "# 기존 정체성\r\n".encode("utf-8"))
        self.assertEqual(memory.read_bytes(), "# 확정한 프로젝트 결정\r\n".encode("utf-8"))

    def test_legacy_filename_respects_filesystem_case_rules(self):
        legacy = self.root / "AGENTs.md"
        canonical = self.root / "AGENTS.md"
        original = b"# Existing project guidance\n"
        legacy.write_bytes(original)
        same_file = canonical.exists()
        self.run_init()
        if same_file:
            self.assertEqual([p.name for p in self.root.iterdir() if p.name.casefold() == "agents.md"], ["AGENTs.md"])
            self.assertTrue(legacy.read_bytes().startswith(original))
        else:
            self.assertEqual(legacy.read_bytes(), original)
            self.assertIn("](AGENTs.md)", canonical.read_text(encoding="utf-8"))
        self.assertIn("](SOUL.md)", canonical.read_text(encoding="utf-8"))

    def test_invalid_paths_and_unclosed_fence_fail_before_writing(self):
        occupied = self.root / "memory"
        occupied.write_bytes(b"Existing file")
        self.assertIn("Expected a directory", self.run_init(success=False).stderr)
        self.assertEqual(self.snapshot().keys(), {Path("memory")})

        occupied.unlink()
        guidance = self.root / "AGENTS.md"
        guidance.write_bytes(b"```\n")
        self.assertIn("Unclosed fenced code block", self.run_init(success=False).stderr)
        self.assertEqual(self.snapshot().keys(), {Path("AGENTS.md")})

    def test_existing_legacy_markers_are_removed_without_changing_instructions(self):
        self.run_init("--with-user")
        guidance = self.root / "AGENTS.md"
        original = guidance.read_text(encoding="utf-8")
        legacy = original.replace("## 에이전트 운영\n", "<!-- agentify:start -->\n## 에이전트 운영\n")
        legacy += "<!-- agentify:end -->\n"
        guidance.write_text(legacy, encoding="utf-8")
        self.run_init()
        self.assertEqual(guidance.read_text(encoding="utf-8"), original)
        self.assertTrue((self.root / "USER.md").is_file())

    def test_incomplete_legacy_marker_does_not_block_initialization(self):
        guidance = self.root / "AGENTS.md"
        guidance.write_text("# 프로젝트\n\n<!-- agentify:start -->\n", encoding="utf-8")
        self.run_init()
        content = guidance.read_text(encoding="utf-8")
        self.assertNotIn("<!-- agentify:", content)
        self.assertIn("](SOUL.md)", content)

    def test_repairs_section_before_the_next_heading(self):
        self.run_init()
        guidance = self.root / "AGENTS.md"
        original = guidance.read_text(encoding="utf-8")
        missing = "\n".join(line for line in original.splitlines() if "](HEARTBEAT.md)" not in line)
        guidance.write_text(missing + "\n\n## 프로젝트 규칙\n\n- 기존 규칙\n", encoding="utf-8")
        self.run_init()
        repaired = guidance.read_text(encoding="utf-8")
        self.assertLess(repaired.index("](HEARTBEAT.md)"), repaired.index("## 프로젝트 규칙"))
        self.assertIn("## 프로젝트 규칙\n\n- 기존 규칙\n", repaired)

    def test_existing_empty_section_receives_all_operating_rules(self):
        guidance = self.root / "AGENTS.md"
        guidance.write_text("# 프로젝트\n\n## 에이전트 운영\n\n- 기존 규칙\n", encoding="utf-8")
        self.run_init()
        content = guidance.read_text(encoding="utf-8")
        template = (SCRIPT.parent.parent / "assets" / "AGENTS.section.md").read_text(encoding="utf-8")
        for line in template.splitlines():
            if line.startswith("- "):
                self.assertIn(line, content)
        self.assertIn("- 기존 규칙", content)
        self.assertEqual(content.count("## 에이전트 운영"), 1)

    def test_renamed_section_is_not_duplicated_and_user_module_can_be_added(self):
        self.run_init()
        guidance = self.root / "AGENTS.md"
        renamed = guidance.read_text(encoding="utf-8").replace("## 에이전트 운영", "## 내 운영 규칙")
        guidance.write_text(renamed, encoding="utf-8")
        before = self.snapshot()
        self.run_init()
        self.assertEqual(self.snapshot(), before)

        self.run_init("--with-user")
        connected = guidance.read_text(encoding="utf-8")
        self.assertEqual(connected.count("](USER.md)"), 1)
        for link in LINKS:
            self.assertEqual(connected.count(f"]({link})"), 1)
        before = self.snapshot()
        self.run_init()
        self.assertEqual(self.snapshot(), before)

    def test_existing_document_link_is_preserved_on_initial_install(self):
        guidance = self.root / "AGENTS.md"
        guidance.write_text("# 프로젝트\n\n[기존 정체성](SOUL.md)\n", encoding="utf-8")
        self.run_init()
        content = guidance.read_text(encoding="utf-8")
        template = (SCRIPT.parent.parent / "assets" / "AGENTS.section.md").read_text(encoding="utf-8")
        self.assertEqual(content.count("](SOUL.md)"), 1)
        for line in template.splitlines():
            if line.startswith("- ") and "](SOUL.md)" not in line:
                self.assertIn(line, content)

    def test_concurrent_initialization_leaves_one_complete_connection(self):
        # A concurrent writer can lose the race to create or update AGENTS.
        def attempt():
            return subprocess.run(
                [sys.executable, "-B", str(SCRIPT), "--project-root", str(self.root)],
                capture_output=True,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: attempt(), range(2)))
        self.assertIn(0, [result.returncode for result in results])
        connected = self.root / "AGENTS.md"
        self.assertNotIn(b"<!-- agentify:", connected.read_bytes())
        self.assertEqual(connected.read_text(encoding="utf-8").count("## 에이전트 운영"), 1)
        for link in LINKS:
            self.assertTrue((self.root / link).is_file())


if __name__ == "__main__":
    unittest.main()
