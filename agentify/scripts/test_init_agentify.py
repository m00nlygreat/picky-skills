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

    def run_init(self, *, success=True):
        result = subprocess.run(
            [sys.executable, "-B", "-X", "utf8", str(SCRIPT), "--project-root", str(self.root)],
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
        self.assertIn("](memory/INDEX.md)", (self.root / "MEMORY.md").read_text(encoding="utf-8"))
        self.run_init()
        self.assertEqual(self.snapshot(), before)

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
        guidance.write_bytes(broken.replace("<!-- agentify:end -->", manual_rule + "<!-- agentify:end -->").encode("utf-8"))
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

    def test_invalid_paths_and_incomplete_section_fail_before_writing(self):
        occupied = self.root / "memory"
        occupied.write_bytes(b"Existing file")
        self.assertIn("Expected a directory", self.run_init(success=False).stderr)
        self.assertEqual(self.snapshot().keys(), {Path("memory")})

        occupied.unlink()
        guidance = self.root / "AGENTS.md"
        guidance.write_bytes(b"<!-- agentify:start -->\n")
        self.assertIn("Expected one complete", self.run_init(success=False).stderr)
        self.assertEqual(self.snapshot().keys(), {Path("AGENTS.md")})

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
        self.assertEqual(connected.read_bytes().count(b"<!-- agentify:start -->"), 1)
        self.assertEqual(connected.read_bytes().count(b"<!-- agentify:end -->"), 1)
        for link in LINKS:
            self.assertTrue((self.root / link).is_file())


if __name__ == "__main__":
    unittest.main()
