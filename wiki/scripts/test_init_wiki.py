"""Offline CLI checks for general project document management."""
import csv
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("init_wiki.py")
TEMPLATES = SCRIPT.parents[1] / "templates"


class InitWikiTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="wiki-init-")
        self.root = Path(temporary.name).resolve()
        self.assertEqual(self.root.parent, Path(tempfile.gettempdir()).resolve())
        self.addCleanup(temporary.cleanup)

    def run_init(self, *arguments, force=False, success=True):
        command = [sys.executable, "-B", "-X", "utf8", str(SCRIPT), "--project-root", str(self.root)]
        if force:
            command.append("--force")
        result = subprocess.run(command + list(arguments), capture_output=True, text=True, encoding="utf-8")
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def test_selected_templates_are_created_without_other_documents(self):
        self.run_init("term,log")
        self.assertEqual({path.name for path in self.root.iterdir()}, {"docs", "AGENTS.md"})
        self.assertEqual({path.name for path in (self.root / "docs").iterdir()}, {"TERMS.md", "LOG.md"})
        for name in ("TERMS.md", "LOG.md"):
            self.assertEqual((self.root / "docs" / name).read_bytes(), (TEMPLATES / name).read_bytes())

    def test_arbitrary_document_names_and_locations_are_supported(self):
        self.run_init("ARCHITECTURE", "docs/operations.md", "README.md")
        self.assertTrue((self.root / "docs" / "ARCHITECTURE.md").is_file())
        self.assertTrue((self.root / "docs" / "operations.md").is_file())
        self.assertTrue((self.root / "README.md").is_file())
        agents = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("](docs/operations.md)", agents)
        self.assertIn("](README.md)", agents)

    def test_force_overwrites_only_selected_markdown_documents(self):
        self.run_init("TERMS", "LOG")
        terms = self.root / "docs" / "TERMS.md"
        log = self.root / "docs" / "LOG.md"
        terms.write_text("사용자 용어", encoding="utf-8")
        log.write_text("사용자 기록", encoding="utf-8")
        self.run_init("TERMS", force=True)
        self.assertEqual(terms.read_bytes(), (TEMPLATES / "TERMS.md").read_bytes())
        self.assertEqual(log.read_text(encoding="utf-8"), "사용자 기록")

    def test_custom_sections_and_fenced_headings_survive_instruction_merge(self):
        section = "## 위키 관리\r\n\r\n- 사용자 맞춤 규칙을 유지한다.\r\n\r\n### 메모\r\n\r\n~~~markdown\r\n## 코드 안의 제목\r\n~~~\r\n"
        suffix = "\r\n## 배포\r\n\r\n- 배포 규칙을 유지한다.\r\n"
        agents = self.root / "AGENTS.md"
        agents.write_bytes(("# 프로젝트\r\n\r\n" + section + suffix).encode("utf-8"))
        self.run_init("TERMS")
        updated = agents.read_bytes().decode("utf-8")
        self.assertTrue(updated.startswith("# 프로젝트\r\n\r\n" + section))
        self.assertTrue(updated.endswith(suffix))
        self.assertNotIn("\n", updated.replace("\r\n", ""))

    def test_repeated_initialization_is_idempotent_and_reuses_alternate_agents_name(self):
        agents = self.root / "AGENTs.md"
        agents.write_text("# 사용자 지침\n", encoding="utf-8")
        self.run_init("TERMS", "LOG")
        before = {
            path.relative_to(self.root): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in self.root.rglob("*") if path.is_file()
        }
        result = self.run_init("TERM", "LOG")
        after = {
            path.relative_to(self.root): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in self.root.rglob("*") if path.is_file()
        }
        self.assertEqual(after, before)
        self.assertIn("unchanged", result.stdout)

    def test_new_csv_uses_chosen_headers_and_adds_guide_link(self):
        self.run_init("data/TERMS.csv", "--csv-header", "data/TERMS.csv", "name,label,meaning")
        target = self.root / "data" / "TERMS.csv"
        with target.open(encoding="utf-8-sig", newline="") as stream:
            self.assertEqual(list(csv.reader(stream)), [["name", "label", "meaning"]])
        guide = self.root / "docs" / "CSV_GUIDE.md"
        self.assertEqual(guide.read_bytes(), (SCRIPT.parents[1] / "references" / "csv.md").read_bytes())
        agents = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("](data/TERMS.csv)", agents)
        self.assertIn("](docs/CSV_GUIDE.md)", agents)
        self.assertIn("infer_schema => false", agents)

    def test_existing_csv_is_preserved_even_with_force_and_another_header(self):
        target = self.root / "TASKS.csv"
        original = '\ufeffid,title\r\n0007,"한글, 따옴표와 줄바꿈\r\n내용"\r\n'.encode("utf-8")
        target.write_bytes(original)
        modified = target.stat().st_mtime_ns
        self.run_init("TASKS.csv", "--csv-header", "TASKS.csv", "different,header", force=True)
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(target.stat().st_mtime_ns, modified)

    def test_invalid_csv_requests_and_paths_are_rejected_before_writes(self):
        cases = (
            ("LOG", "new.csv"),
            ("new.csv", "--csv-header", "new.csv", "id,id"),
            ("new.csv", "--csv-header", "new.csv", "id,"),
            ("../outside-project.md",),
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                self.run_init(*arguments, success=False)
                self.assertEqual(list(self.root.iterdir()), [])

    def test_existing_non_markdown_document_can_be_registered_without_rewriting(self):
        target = self.root / "data.json"
        original = b'{"project": "existing document"}\n'
        target.write_bytes(original)
        self.run_init("data.json", force=True)
        self.assertEqual(target.read_bytes(), original)
        self.assertIn("](data.json)", (self.root / "AGENTS.md").read_text(encoding="utf-8"))

    def test_existing_nested_project_documents_are_connected(self):
        path = self.root / "docs" / "research" / "회의 기록.md"
        path.parent.mkdir(parents=True)
        path.write_text("# 기존 회의 기록\n", encoding="utf-8")
        self.run_init()
        content = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("](docs/research/%ED%9A%8C%EC%9D%98%20%EA%B8%B0%EB%A1%9D.md)", content)
        self.assertEqual(path.read_text(encoding="utf-8"), "# 기존 회의 기록\n")

    @unittest.skipUnless(shutil.which("qsv"), "qsv is not installed")
    def test_qsv_reference_workflow_preserves_strings_and_stages_changes(self):
        target = self.root / "ITEMS.csv"
        with target.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["id", "title", "status", "date"])
            writer.writerow(["0007", '한글, "따옴표"와\n줄바꿈', "open", "2026-11-10"])
        original = target.read_bytes()
        result = subprocess.run(
            ["qsv", "headers", str(target), "--just-names"],
            capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["id", "title", "status", "date"])
        result = subprocess.run(["qsv", "validate", str(target), "--quiet"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(target.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
