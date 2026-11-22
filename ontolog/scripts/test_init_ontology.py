"""Offline checks for ontology initialization and project guidance links."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("init_ontology.py")


class InitOntologyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ontology-init-")
        self.root = Path(temporary.name).resolve()
        self.assertEqual(self.root.parent, Path(tempfile.gettempdir()).resolve())
        self.addCleanup(temporary.cleanup)

    def run_init(self, success=True):
        result = subprocess.run(
            [sys.executable, "-B", "-X", "utf8", str(SCRIPT), "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8",
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def test_new_project_gets_empty_canonical_and_guidance(self):
        self.run_init()
        ontology = (self.root / "ONTOLOGY.yaml").read_text(encoding="utf-8")
        self.assertIn("명세문서", ontology)
        self.assertIn("docs/ontology/<이름>.md", ontology)
        self.assertEqual(
            [line for line in ontology.splitlines() if line and not line.startswith("#")],
            ["개념: []", "관계: []", "소스: []"],
        )
        self.assertEqual({path.name for path in self.root.iterdir()}, {"ONTOLOGY.yaml", "AGENTS.md"})
        agents = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("](ONTOLOGY.yaml)", agents)
        self.assertIn("## 온톨로지 관리", agents)
        self.assertIn("모든 프로젝트 작업을 시작할 때 정본 전체를 읽고 작업 맥락에 포함한다.", agents)

    def test_existing_canonical_is_preserved_byte_for_byte(self):
        path = self.root / "ONTOLOGY.yaml"
        original = "# 사용자 정본\r\n기존구조:\r\n  유지: true\r\n".encode("utf-8")
        path.write_bytes(original)
        modified = path.stat().st_mtime_ns
        self.run_init()
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(path.stat().st_mtime_ns, modified)
        self.assertIn("skipped existing", self.run_init().stdout)

    def test_existing_entity_specs_are_linked_without_creating_others(self):
        specs = self.root / "docs" / "ontology"
        specs.mkdir(parents=True)
        session = specs / "session.md"
        course = specs / "course.md"
        session.write_text("# 회차 명세\n", encoding="utf-8")
        course.write_text("# 강의 명세\n", encoding="utf-8")
        (specs.parent / "operations.md").write_text("# 프로젝트 운영\n", encoding="utf-8")
        self.run_init()
        agents = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("](docs/ontology/session.md)", agents)
        self.assertIn("](docs/ontology/course.md)", agents)
        self.assertNotIn("](docs/operations.md)", agents)
        self.assertFalse((specs / "task.md").exists())
        self.assertEqual(session.read_text(encoding="utf-8"), "# 회차 명세\n")

    def test_repeated_initialization_is_idempotent(self):
        specs = self.root / "docs" / "ontology"
        specs.mkdir(parents=True)
        (specs / "task.md").write_text("# 할 일\n", encoding="utf-8")
        self.run_init()
        before = {
            path.relative_to(self.root): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in self.root.rglob("*") if path.is_file()
        }
        result = self.run_init()
        after = {
            path.relative_to(self.root): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in self.root.rglob("*") if path.is_file()
        }
        self.assertEqual(after, before)
        self.assertIn("unchanged", result.stdout)

    def test_existing_agent_section_and_crlf_content_are_preserved(self):
        agents = self.root / "AGENTs.md"
        original = (
            "# 프로젝트\r\n\r\n## 온톨로지 관리\r\n\r\n- 사용자 승인 규칙을 유지한다.\r\n\r\n"
            "~~~markdown\r\n## 코드 예시의 가짜 제목\r\n~~~\r\n\r\n## 배포\r\n- 배포 규칙\r\n"
        )
        agents.write_bytes(original.encode("utf-8"))
        self.run_init()
        updated = agents.read_bytes().decode("utf-8")
        self.assertTrue(updated.startswith(original.split("## 온톨로지 관리", 1)[0] + "## 온톨로지 관리\r\n"))
        self.assertTrue(updated.endswith("## 배포\r\n- 배포 규칙\r\n"))
        self.assertIn("- 사용자 승인 규칙을 유지한다.\r\n", updated)
        self.assertNotIn("\n", updated.replace("\r\n", ""))
        agent_files = [path for path in self.root.iterdir() if path.name.lower() == "agents.md"]
        self.assertEqual(len(agent_files), 1)

    def test_invalid_canonical_or_guidance_paths_are_rejected(self):
        (self.root / "ONTOLOGY.yaml").mkdir()
        self.run_init(success=False)
        self.assertFalse((self.root / "AGENTS.md").exists())


if __name__ == "__main__":
    unittest.main()
