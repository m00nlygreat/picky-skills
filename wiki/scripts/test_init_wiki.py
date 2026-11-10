"""Offline CLI checks for open document management and project file preservation."""
import csv
import json
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

    def run_init(self, *modules, force=False, success=True):
        command = [sys.executable, "-B", "-X", "utf8", str(SCRIPT), "--project-root", str(self.root)]
        if force:
            command.append("--force")
        result = subprocess.run(command + list(modules), capture_output=True, text=True, encoding="utf-8")
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def test_markdown_selection_preserves_templates_and_does_not_enable_ontology(self):
        self.run_init("term,log")
        self.assertFalse((self.root / "ONTOLOGY.yml").exists())
        self.assertEqual({path.name for path in (self.root / "wiki").iterdir()}, {"TERMS.md", "LOG.md"})
        for name in ("TERMS.md", "LOG.md"):
            self.assertEqual((self.root / "wiki" / name).read_bytes(), (TEMPLATES / name).read_bytes())

    def test_ontology_only_uses_project_root_without_creating_markdown_documents(self):
        self.run_init("ontology")
        self.assertEqual({path.name for path in self.root.iterdir()}, {"ONTOLOGY.yml", "AGENTS.md"})
        ontology = (self.root / "ONTOLOGY.yml").read_text(encoding="utf-8")
        self.assertNotIn("<", ontology)
        self.assertNotIn("primary_record", ontology)
        agents = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("](ONTOLOGY.yml)", agents)
        self.assertNotIn("](wiki/)", agents)

    def test_arbitrary_document_names_and_locations_are_supported(self):
        self.run_init("ARCHITECTURE", "docs/operations.md", "README.md")
        self.assertTrue((self.root / "wiki" / "ARCHITECTURE.md").is_file())
        self.assertTrue((self.root / "docs" / "operations.md").is_file())
        self.assertTrue((self.root / "README.md").is_file())
        self.assertFalse((self.root / "ONTOLOGY.yml").exists())
        self.assertFalse((self.root / "wiki" / "TERMS.md").exists())
        agents = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("](docs/operations.md)", agents)
        self.assertIn("](README.md)", agents)

    def test_existing_ontology_is_preserved_even_with_force(self):
        ontology = self.root / "ONTOLOGY.yml"
        original = "# 사용자 정본\r\n기존구조:\r\n  유지: true\r\n".encode("utf-8")
        ontology.write_bytes(original)
        modified = ontology.stat().st_mtime_ns
        self.run_init("ONTOLOGY", force=True)
        self.assertEqual(ontology.read_bytes(), original)
        self.assertEqual(ontology.stat().st_mtime_ns, modified)

    def test_force_overwrites_only_the_selected_markdown_documents(self):
        self.run_init("TERMS", "LOG", "ONTOLOGY")
        terms = self.root / "wiki" / "TERMS.md"
        log = self.root / "wiki" / "LOG.md"
        ontology = self.root / "ONTOLOGY.yml"
        terms.write_text("사용자 용어", encoding="utf-8")
        log.write_text("사용자 기록", encoding="utf-8")
        ontology.write_text("사용자 온톨로지", encoding="utf-8")
        self.run_init("TERMS", "ONTOLOGY")
        self.assertEqual(terms.read_text(encoding="utf-8"), "사용자 용어")
        self.run_init("TERMS", "ONTOLOGY", force=True)
        self.assertEqual(terms.read_bytes(), (TEMPLATES / "TERMS.md").read_bytes())
        self.assertEqual(log.read_text(encoding="utf-8"), "사용자 기록")
        self.assertEqual(ontology.read_text(encoding="utf-8"), "사용자 온톨로지")

    def test_existing_alternate_agents_filename_is_reused(self):
        agents = self.root / "AGENTs.md"
        agents.write_text("# 사용자 지침\n", encoding="utf-8")
        self.run_init("ONTOLOGY")
        agent_names = [path.name for path in self.root.iterdir() if path.name.lower() == "agents.md"]
        self.assertEqual(agent_names, ["AGENTs.md"])
        self.assertTrue(agents.read_text(encoding="utf-8").startswith("# 사용자 지침\n"))

    def test_custom_sections_and_fenced_headings_survive_instruction_merge(self):
        prefix = "# 프로젝트\r\n\r\n## 온톨로지 관리\r\n\r\n- 변경은 건별 사용자 승인 후 수행한다.\r\n\r\n"
        section = "## 위키 관리\r\n\r\n- 사용자 맞춤 규칙을 유지한다.\r\n\r\n### 메모\r\n\r\n~~~markdown\r\n## 코드 안의 제목\r\n~~~\r\n"
        suffix = "\r\n## 배포\r\n\r\n- 배포 규칙을 유지한다.\r\n"
        agents = self.root / "AGENTS.md"
        agents.write_bytes((prefix + section + suffix).encode("utf-8"))
        self.run_init("TERMS", "ONTOLOGY")
        updated = agents.read_bytes().decode("utf-8")
        self.assertTrue(updated.startswith(prefix + section))
        self.assertTrue(updated.endswith(suffix))
        self.assertNotIn("\n", updated.replace("\r\n", ""))
        self.assertLess(updated.index("](ONTOLOGY.yml)"), updated.index("## 배포"))
        self.assertGreater(updated.index("](ONTOLOGY.yml)"), updated.index("~~~\r\n"))

    def test_repeated_initialization_does_not_rewrite_any_project_file(self):
        self.run_init("TERMS", "LOG", "ONTOLOGY")
        before = {
            path.relative_to(self.root): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in self.root.rglob("*") if path.is_file()
        }
        result = self.run_init("ONTOLOGY", "TERM", "LOG")
        after = {
            path.relative_to(self.root): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in self.root.rglob("*") if path.is_file()
        }
        self.assertEqual(after, before)
        self.assertIn("unchanged", result.stdout)

    def test_adding_a_document_keeps_custom_instructions_for_existing_documents(self):
        self.run_init("TERMS")
        agents = self.root / "AGENTS.md"
        custom = "- [wiki/TERMS.md](wiki/TERMS.md)는 사용자가 승인한 별도 용어 규칙을 따른다."
        lines = agents.read_text(encoding="utf-8").splitlines()
        agents.write_text("\n".join(custom if "](wiki/TERMS.md)" in line else line for line in lines) + "\n", encoding="utf-8")
        self.run_init("ONTOLOGY", "LOG")
        content = agents.read_text(encoding="utf-8")
        self.assertIn(custom, content)
        self.assertEqual(content.count("](wiki/TERMS.md)"), 1)
        self.assertEqual(content.count("](ONTOLOGY.yml)"), 1)

    def test_known_legacy_generated_links_are_updated_without_removing_custom_text(self):
        wiki = self.root / "wiki"
        wiki.mkdir()
        (wiki / "TERMS.md").write_text("용어", encoding="utf-8")
        agents = self.root / "AGENTS.md"
        old = "## 위키 관리\n\n- 이 저장소의 간단한 위키는 `wiki/`에 둔다.\n- `wiki/TERMS.md`는 프로젝트 용어와 GUI 표시명의 유지본이다. 용어, 명명 기준, 화면 표시명을 정리하거나 갱신할 때 이 파일을 함께 관리한다.\n- 사용자 문구\n"
        agents.write_text(old, encoding="utf-8")
        self.run_init("ONTOLOGY")
        content = agents.read_text(encoding="utf-8")
        self.assertIn("- 사용자 문구\n", content)
        self.assertEqual(content.count("](wiki/TERMS.md)"), 1)
        self.assertNotIn("`wiki/TERMS.md`", content)

    def test_no_document_selection_does_not_force_suggested_documents(self):
        self.run_init()
        self.assertEqual({path.name for path in self.root.iterdir()}, {"AGENTS.md"})

    def test_existing_non_markdown_document_can_be_registered_without_rewriting(self):
        target = self.root / "data.json"
        original = b'{"project": "existing document"}\n'
        target.write_bytes(original)
        self.run_init("data.json", force=True)
        self.assertEqual(target.read_bytes(), original)
        self.assertIn("](data.json)", (self.root / "AGENTS.md").read_text(encoding="utf-8"))

    def test_new_csv_uses_chosen_headers_and_injects_portable_tool_guidance(self):
        self.run_init("data/TERMS.csv", "--csv-header", "data/TERMS.csv", "name,label,meaning")
        target = self.root / "data" / "TERMS.csv"
        with target.open(encoding="utf-8-sig", newline="") as stream:
            self.assertEqual(list(csv.reader(stream)), [["name", "label", "meaning"]])
        guide = self.root / "wiki" / "CSV_GUIDE.md"
        self.assertEqual(guide.read_bytes(), (SCRIPT.parents[1] / "references" / "csv.md").read_bytes())
        agents = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("](data/TERMS.csv)", agents)
        self.assertIn("](wiki/CSV_GUIDE.md)", agents)
        self.assertIn("infer_schema => false", agents)
        self.assertFalse((self.root / "ONTOLOGY.yml").exists())

    def test_existing_csv_is_preserved_even_with_force_and_another_header(self):
        target = self.root / "TASKS.csv"
        original = '\ufeffid,title\r\n0007,"한글, 따옴표와 줄바꿈\r\n내용"\r\n'.encode("utf-8")
        target.write_bytes(original)
        modified = target.stat().st_mtime_ns
        self.run_init("TASKS.csv", "--csv-header", "TASKS.csv", "different,header", force=True)
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(target.stat().st_mtime_ns, modified)

    def test_missing_or_invalid_csv_schema_is_rejected_before_creating_documents(self):
        cases = (
            ("LOG", "new.csv"),
            ("new.csv", "--csv-header", "new.csv", "id,id"),
            ("new.csv", "--csv-header", "new.csv", "id,"),
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                self.run_init(*arguments, success=False)
                self.assertEqual(list(self.root.iterdir()), [])

    def test_document_paths_outside_project_are_rejected_before_writes(self):
        self.run_init("../outside-project.md", success=False)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_existing_custom_wiki_documents_are_connected_without_a_fixed_list(self):
        path = self.root / "wiki" / "research" / "회의 기록.md"
        path.parent.mkdir(parents=True)
        path.write_text("# 기존 회의 기록\n", encoding="utf-8")
        self.run_init()
        content = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("](wiki/research/%ED%9A%8C%EC%9D%98%20%EA%B8%B0%EB%A1%9D.md)", content)
        self.assertEqual(path.read_text(encoding="utf-8"), "# 기존 회의 기록\n")

    @unittest.skipUnless(shutil.which("qsv"), "qsv is not installed")
    def test_qsv_reference_workflow_preserves_strings_and_stages_changes(self):
        target = self.root / "ITEMS.csv"
        title = '한글, "따옴표"와\n줄바꿈'
        with target.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["id", "title", "status", "date"])
            writer.writerow(["0007", title, "open", "2026-11-10"])
        original = target.read_bytes()

        def qsv(*arguments):
            result = subprocess.run(["qsv", *arguments], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout

        self.assertEqual(qsv("headers", str(target), "--just-names").splitlines(), ["id", "title", "status", "date"])
        qsv("validate", str(target), "--quiet")

        def read_row(path):
            sql_path = path.as_posix().replace("'", "''")
            query = f"SELECT * FROM read_csv('{sql_path}', infer_schema => false) WHERE id = '0007'"
            rows = json.loads(qsv("sqlp", "SKIP_INPUT", query, "--format", "json", "--quiet"))
            self.assertEqual(len(rows), 1)
            return rows[0]

        self.assertEqual(read_row(target), {"id": "0007", "title": title, "status": "open", "date": "2026-11-10"})
        pending = self.root / "ITEMS.pending.csv"
        qsv("edit", str(target), "status", "0", "done", "--output", str(pending))
        qsv("validate", str(pending), "--quiet")
        self.assertEqual(read_row(pending), {"id": "0007", "title": title, "status": "done", "date": "2026-11-10"})
        self.assertEqual(target.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
