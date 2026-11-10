#!/usr/bin/env python3
"""Create or register project documents and merge their maintenance instructions."""
import argparse
import csv
import io
import re
from pathlib import Path
from urllib.parse import quote, unquote


TEMPLATE_ALIASES = {"TERM": "TERMS", "REQ": "REQUIREMENT", "REQUIREMENTS": "REQUIREMENT"}
DOCUMENT_ROLES = {
    "REQUIREMENT": "는 현재 요구사항 요약의 유지본이다. 요구사항을 정리하거나 갱신할 때 이 파일을 함께 관리한다.",
    "MVP": "는 현재 MVP 범위의 유지본이다. MVP 범위를 정리하거나 갱신할 때 이 파일을 함께 관리한다.",
    "TERMS": "는 프로젝트 용어와 GUI 표시명의 유지본이다. 용어, 명명 기준, 화면 표시명을 정리하거나 갱신할 때 이 파일을 함께 관리한다.",
    "LOG": "에는 프로젝트 관련 중대 결정사항, 새로 알아낸 사실, 방향 변경을 시간순으로 남긴다.",
}
ONTOLOGY_PATH = "ONTOLOGY.yaml"
CSV_GUIDE_PATH = "wiki/CSV_GUIDE.md"
ONTOLOGY_BULLET = "- [ONTOLOGY.yaml](ONTOLOGY.yaml)은 프로젝트의 개념·관계·데이터 소스와 찾는 방법의 유지본이다. 관련 정보를 조회하거나 변경할 때 먼저 참조한다."
ONTOLOGY_RULES = [
    "- 온톨로지에는 프로젝트 구조에 필요한 개념·관계·소스를 기록하고, 필요한 속성을 프로젝트에 맞게 확장한다.",
    "- 온톨로지의 추가·수정·삭제·이름·구조·서식 변경은 구체적인 사용자 요청 또는 명시적으로 승인받은 변경안의 범위에서만 수행한다. 오탈자·서식 수정도 예외가 아니다.",
    "- 온톨로지 변경안은 이유·변경 전후·영향을 제시하고, 동의 전에는 원문을 유지한다. 무응답·추정·새 사실의 발견·일반적인 관리 요청·과거의 포괄적 위임을 동의로 간주하지 않는다.",
]
WIKI_SCOPE = "- 위키는 프로젝트와 함께 관리하는 모든 문서를 대상으로 하며, 이름·형식·위치는 프로젝트 구조와 사용자 요청에 맞게 관리한다."
GENERAL_RULES = [
    "- 위키 문서는 한국어로 짧고 명확하게 작성한다.",
    "- 위키의 기본 형식은 Markdown(.md)이며, CSV는 사용자 요청이 있을 때만 사용한다.",
    "- 위키 문서나 프로젝트 문서를 참조할 때는 백틱 경로 대신 마크다운 링크와 프로젝트 기준 상대 경로를 사용한다.",
]
CSV_RULES = [
    "- CSV 조회·검색·검증은 qsv가 있으면 headers·validate·sqlp를 사용한다. sqlp는 read_csv(..., infer_schema => false)로 ID·선행 0·날짜를 문자열로 보존하고, 실패를 빈 결과로 처리하지 않는다.",
    "- CSV 변경은 정본·사본과 기존 도우미를 확인한 뒤 수행한다. 임시 파일에서 수정하고 헤더·고유 키·수정 결과·인코딩을 검증한 뒤 교체한다. 도구의 상세 사용법은 CSV 사용법 문서를 따른다.",
]
SOURCE_RULE = "- 원본 자료 폴더는 사용자가 요청하지 않는 한 수정하지 않는다."
EMPTY_ONTOLOGY = "# 프로젝트별 구성을 사용자와 검토한 뒤 승인된 내용만 반영한다.\n개념: []\n관계: []\n소스: []\n"
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
LEGACY_RULES = {
    "- 이 저장소의 간단한 위키는 [wiki](wiki/)에 둔다.": WIKI_SCOPE,
    "- 이 저장소의 간단한 위키는 " + chr(96) + "wiki/" + chr(96) + "에 둔다.": WIKI_SCOPE,
}
for _name, _role in DOCUMENT_ROLES.items():
    _path = f"wiki/{_name}.md"
    LEGACY_RULES[f"- {chr(96)}{_path}{chr(96)}{_role}"] = f"- [{_path}]({_path}){_role}"
RULE_PREFIXES = (
    "- 위키는 프로젝트와 함께 관리하는 모든 문서를",
    "- 위키 문서는",
    "- 위키의 기본 형식은",
    "- 위키 문서나 프로젝트 문서를 참조할 때는",
    "- 원본 자료 폴더는",
    "- 온톨로지에는",
    "- 온톨로지의 추가·수정·삭제",
    "- 온톨로지 변경안은",
    "- CSV 조회·검색·검증은",
    "- CSV 변경은",
)


def project_path(project_root, raw):
    raw = raw.replace("\\", "/").strip()
    path = Path(raw)
    if not path.suffix and not path.is_absolute() and len(path.parts) == 1:
        name = TEMPLATE_ALIASES.get(raw.upper(), raw)
        templates = Path(__file__).resolve().parents[1] / "templates"
        if (templates / f"{name.upper()}.md").is_file():
            name = name.upper()
        path = Path("wiki") / (name + ".md")
    elif not path.suffix:
        path = path.with_suffix(".md")
    target = (project_root / path).resolve()
    try:
        target.relative_to(project_root)
    except ValueError:
        raise SystemExit(f"Document must stay within the project: {raw}")
    return target


def selected_documents(project_root, raw_documents):
    documents = []
    ontology = False
    for raw in raw_documents:
        # Retain comma-separated shorthand without splitting literal file paths.
        tokens = raw.split(",") if not Path(raw).suffix and "/" not in raw and "\\" not in raw else [raw]
        for token in tokens:
            token = token.strip()
            if not token:
                continue
            if token.upper() in ("ONTOLOGY", "ONTOLOGY.YAML"):
                ontology = True
                continue
            path = project_path(project_root, token)
            if path not in documents:
                documents.append(path)
    return documents, ontology


def csv_headers(project_root, definitions):
    headers = {}
    for raw_path, raw_header in definitions:
        target = project_path(project_root, raw_path)
        if target.suffix.lower() != ".csv":
            raise SystemExit(f"CSV header requires a .csv document: {raw_path}")
        try:
            rows = list(csv.reader(io.StringIO(raw_header, newline=""), strict=True))
        except csv.Error as error:
            raise SystemExit(f"Invalid CSV header: {error}")
        if len(rows) != 1 or not rows[0] or any(not value.strip() for value in rows[0]):
            raise SystemExit(f"CSV header must be one non-empty row: {raw_path}")
        if len(rows[0]) != len(set(rows[0])) or target in headers:
            raise SystemExit(f"Duplicate CSV header or column: {raw_path}")
        headers[target] = rows[0]
    return headers


def existing_documents(project_root):
    wiki = project_root / "wiki"
    found = []
    if wiki.is_dir():
        for candidate in sorted(wiki.rglob("*")):
            if candidate.is_file() and not any(part.startswith(".") for part in candidate.relative_to(wiki).parts):
                found.append(project_path(project_root, candidate.as_posix()))
    ontology = project_root / ONTOLOGY_PATH
    if ontology.is_file():
        found.append(ontology)
    return found


def document_rule(project_root, path):
    relative = path.relative_to(project_root).as_posix()
    if relative == ONTOLOGY_PATH:
        return ONTOLOGY_BULLET
    if relative == CSV_GUIDE_PATH:
        return "- [CSV 사용법](wiki/CSV_GUIDE.md)에 CSV 구조 확인·qsv 조회·문자열 보존·변경·검증 절차를 정리한다. CSV 작업 전에 참조하고 프로젝트에 맞게 유지한다."
    label = relative.replace("[", "\\[").replace("]", "\\]")
    link = f"[{label}]({quote(relative, safe='/')})"
    role = DOCUMENT_ROLES.get(path.stem.upper())
    if role is None:
        role = "은 프로젝트의 CSV 문서다. 열·고유 키·변경 경로를 확인하고 관련 정보와 함께 관리한다." if path.suffix.lower() == ".csv" else "은 프로젝트와 함께 관리하는 문서다. 관련 내용이 바뀌면 함께 갱신한다."
    return f"- {link}{role}"


def render_agents_section(project_root, documents):
    lines = ["## 위키 관리", "", WIKI_SCOPE, *GENERAL_RULES]
    for path in documents:
        lines.append(document_rule(project_root, path))
    if any(path.name == ONTOLOGY_PATH for path in documents):
        lines.extend(ONTOLOGY_RULES)
    if any(path.suffix.lower() == ".csv" for path in documents):
        lines.extend(CSV_RULES)
    lines.append(SOURCE_RULE)
    return "\n".join(lines) + "\n"


def wiki_section_bounds(content):
    """Find the section while ignoring headings inside fenced examples."""
    start = None
    offset = 0
    fence = None
    for line in content.splitlines(keepends=True):
        stripped = line.lstrip(" \t")
        marker = stripped[:1]
        if marker in (chr(96), "~") and marker:
            length = len(stripped) - len(stripped.lstrip(marker))
            if length >= 3:
                if fence is None:
                    fence = (marker, length)
                elif marker == fence[0] and length >= fence[1] and not stripped[length:].strip():
                    fence = None
                offset += len(line)
                continue
        if fence is None:
            heading = re.match(r"^(#{1,2})[ \t]+([^\r\n]+)", line)
            if heading:
                title = heading[2].rstrip(" \t#")
                if start is not None:
                    return start, offset
                if heading[1] == "##" and title == "위키 관리":
                    start = offset
        offset += len(line)
    return (start, len(content)) if start is not None else None

def instruction_key(line):
    stripped = line.strip()
    for prefix in RULE_PREFIXES:
        if stripped.startswith(prefix):
            return prefix
    links = LINK_PATTERN.findall(stripped)
    if links:
        return "document:" + unquote(links[0])
    return stripped


def inject_agents_section(agents_path, section):
    if agents_path.exists():
        with agents_path.open(encoding="utf-8", newline="") as stream:
            content = stream.read()
    else:
        content = "# 에이전트 메모\n"
    newline = "\r\n" if "\r\n" in content else "\n"
    bounds = wiki_section_bounds(content)
    if bounds is None:
        separator = "" if content.endswith(newline * 2) else newline if content.endswith(newline) else newline * 2
        updated = content + separator + section.replace("\n", newline)
    else:
        start, end = bounds
        original = content[start:end]
        migrated = "".join(
            LEGACY_RULES.get(line.rstrip("\r\n"), line.rstrip("\r\n"))
            + line[len(line.rstrip("\r\n")):]
            for line in original.splitlines(keepends=True)
        )
        present = {instruction_key(line) for line in migrated.splitlines() if line.startswith("- ")}
        missing = [
            line for line in section.splitlines()
            if line.startswith("- ") and instruction_key(line) not in present
        ]
        if missing:
            ending = newline * 2 if end < len(content) else newline
            migrated = migrated.rstrip("\r\n") + newline + newline.join(missing) + ending
        updated = content[:start] + migrated + content[end:]
    if updated == content:
        return False
    with agents_path.open("w", encoding="utf-8", newline="") as stream:
        stream.write(updated)
    return True


def agents_file(project_root):
    for name in ("AGENTS.md", "AGENTs.md"):
        candidate = project_root / name
        if candidate.exists():
            return candidate
    return project_root / "AGENTS.md"

def main():
    parser = argparse.ArgumentParser(description="Create or register project documents and their wiki guidance.")
    parser.add_argument("documents", nargs="*", help="Arbitrary document names or project-relative paths. Bare names use wiki/NAME.md.")
    parser.add_argument("--project-root", default=".", help="Project root. Default: current directory.")
    parser.add_argument("--ontology", action="store_true", help="Initialize or connect the special ONTOLOGY.yaml document.")
    parser.add_argument("--csv-header", nargs=2, action="append", default=[], metavar=("PATH", "HEADER"), help="Create a new CSV with an explicitly chosen header row.")
    parser.add_argument("--force", action="store_true", help="Overwrite selected Markdown starter files only; preserve existing CSV and ontology data.")
    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()
    skill_root = Path(__file__).resolve().parents[1]
    documents, legacy_ontology = selected_documents(project_root, args.documents)
    headers = csv_headers(project_root, args.csv_header)
    for path in headers:
        if path not in documents:
            documents.append(path)
    if args.ontology or legacy_ontology:
        documents.append(project_root / ONTOLOGY_PATH)
    documents = list(dict.fromkeys(documents))

    # Validate all creation requests before changing project files.
    for target in documents:
        existed = target.exists() or target.is_symlink()
        if existed and not target.is_file():
            raise SystemExit(f"Document path is not a readable file: {target}")
        if existed:
            continue
        if target.name == ONTOLOGY_PATH:
            continue
        if target.suffix.lower() == ".csv" and target not in headers:
            raise SystemExit(f"Choose a header for the new CSV with --csv-header: {target}")
        if target.suffix.lower() not in (".md", ".csv"):
            raise SystemExit(f"Create this document with its format-specific tool first, then register its path: {target}")

    project_root.mkdir(parents=True, exist_ok=True)
    outcomes = []
    for target in documents:
        existed = target.exists()
        if existed and (target.suffix.lower() != ".md" or not args.force):
            outcomes.append(("skipped existing", target))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.name == ONTOLOGY_PATH:
            content = EMPTY_ONTOLOGY
        elif target.suffix.lower() == ".csv":
            with target.open("x", encoding="utf-8-sig", newline="") as stream:
                csv.writer(stream).writerow(headers[target])
            outcomes.append(("created", target))
            continue
        else:
            template = skill_root / "templates" / f"{target.stem.upper()}.md"
            if target.relative_to(project_root).as_posix() == CSV_GUIDE_PATH:
                template = skill_root / "references" / "csv.md"
            content = template.read_bytes().decode("utf-8") if template.is_file() else f"# {target.stem.replace('_', ' ')}\n"
        try:
            with target.open("w" if existed else "x", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
        except FileExistsError:
            outcomes.append(("skipped existing", target))
            continue
        outcomes.append(("overwritten" if existed else "created", target))

    managed = list(dict.fromkeys(existing_documents(project_root) + documents))
    if any(path.suffix.lower() == ".csv" for path in managed):
        guide = project_path(project_root, CSV_GUIDE_PATH)
        if not guide.exists():
            guide.parent.mkdir(parents=True, exist_ok=True)
            with guide.open("xb") as stream:
                stream.write((skill_root / "references" / "csv.md").read_bytes())
            outcomes.append(("created", guide))
        elif not guide.is_file():
            raise SystemExit(f"CSV guide path is not a file: {guide}")
        if guide not in managed:
            managed.append(guide)
    managed = sorted(managed, key=lambda path: path.relative_to(project_root).as_posix())
    agent_path = agents_file(project_root)
    changed = inject_agents_section(agent_path, render_agents_section(project_root, managed))
    for action, path in outcomes:
        print(f"{action} {path}")
    print(f"{'updated' if changed else 'unchanged'} {agent_path}")


if __name__ == "__main__":
    main()
