#!/usr/bin/env python3
"""Create the project ontology starter and connect its guidance in AGENTS.md."""
import argparse
import re
from pathlib import Path
from urllib.parse import quote, unquote


ONTOLOGY_PATH = "ONTOLOGY.yaml"
ENTITY_DOCS_PATH = "docs/ontology"
ENTITY_DOC_PATTERN = f"{ENTITY_DOCS_PATH}/<이름>.md"
ONTOLOGY_STARTER = (
    "# 모든 프로젝트 작업을 시작할 때 이 파일 전체를 읽는다.\n"
    "# 엔티티를 다루기 전에 작업에 필요한 명세만 먼저 읽는다.\n"
    f"# 명세문서 경로는 프로젝트 루트 기준이다. 경로가 없으면 {ENTITY_DOC_PATTERN}가 있는 경우 읽는다.\n\n"
    "# 프로젝트별 구성을 사용자와 검토한 뒤 승인된 내용만 반영한다.\n"
    "개념: []\n"
    "관계: []\n"
    "소스: []\n"
)
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
BASE_RULES = [
    "- 프로젝트 온톨로지의 정본은 [ONTOLOGY.yaml](ONTOLOGY.yaml)이다.",
    "- 모든 프로젝트 작업을 시작할 때 정본 전체를 읽고 작업 맥락에 포함한다.",
    "- 엔티티를 다루기 전에 현재 작업에 필요한 엔티티의 명세만 읽는다.",
    "- 개념·관계·소스와 속성의 변경은 사용자가 지정하거나 명시적으로 승인한 범위에서만 반영한다. 다른 변경은 이유·변경 전후·예상 영향을 제안하고 승인 전에는 정본을 유지한다.",
]


def markdown_path(project_root, path):
    relative = path.relative_to(project_root).as_posix()
    label = relative.replace("[", "\\[").replace("]", "\\]")
    return f"[{label}]({quote(relative, safe='/')})"


def entity_documents(project_root):
    directory = project_root / ENTITY_DOCS_PATH
    if not directory.exists():
        return []
    if not directory.is_dir():
        raise SystemExit(f"Entity specification path is not a directory: {directory}")
    return sorted(
        (
            path for path in directory.rglob("*.md")
            if path.is_file() and not any(part.startswith(".") for part in path.relative_to(directory).parts)
        ),
        key=lambda path: path.relative_to(project_root).as_posix(),
    )


def section_bounds(content):
    """Find the target section while ignoring headings inside fenced examples."""
    heading_title = "온톨로지 관리"
    start = None
    offset = 0
    fence = None
    for line in content.splitlines(keepends=True):
        stripped = line.lstrip(" \t")
        marker = stripped[:1]
        if marker in (chr(96), "~"):
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
                if heading[1] == "##" and title == heading_title:
                    start = offset
        offset += len(line)
    return (start, len(content)) if start is not None else None


def instruction_key(line):
    stripped = line.strip()
    links = LINK_PATTERN.findall(stripped)
    if links:
        return "document:" + unquote(links[0])
    return stripped


def render_agents_section(project_root, entities):
    lines = ["## 온톨로지 관리", "", *BASE_RULES]
    for path in entities:
        link = markdown_path(project_root, path)
        lines.append(f"- 해당 엔티티를 다룰 때 {link}의 명세를 참조한다.")
    return "\n".join(lines) + "\n"


def inject_agents_section(agents_path, section):
    if agents_path.exists():
        with agents_path.open(encoding="utf-8", newline="") as stream:
            content = stream.read()
    else:
        content = "# 에이전트 메모\n"
    newline = "\r\n" if "\r\n" in content else "\n"
    bounds = section_bounds(content)
    if bounds is None:
        separator = "" if content.endswith(newline * 2) else newline if content.endswith(newline) else newline * 2
        updated = content + separator + section.replace("\n", newline)
    else:
        start, end = bounds
        original = content[start:end]
        present = {instruction_key(line) for line in original.splitlines() if line.startswith("- ")}
        missing = [
            line for line in section.splitlines()
            if line.startswith("- ") and instruction_key(line) not in present
        ]
        if missing:
            ending = newline * 2 if end < len(content) else newline
            updated_section = original.rstrip("\r\n") + newline + newline.join(missing) + ending
            updated = content[:start] + updated_section + content[end:]
        else:
            updated = content
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
    parser = argparse.ArgumentParser(description="Initialize or connect a project ontology without replacing existing data.")
    parser.add_argument("--project-root", default=".", help="Project root. Default: current directory.")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    ontology_path = project_root / ONTOLOGY_PATH
    agent_path = agents_file(project_root)
    if ontology_path.exists() or ontology_path.is_symlink():
        if not ontology_path.is_file():
            raise SystemExit(f"Ontology path is not a readable file: {ontology_path}")
    if agent_path.exists() and not agent_path.is_file():
        raise SystemExit(f"Agent guidance path is not a file: {agent_path}")
    entities = entity_documents(project_root)

    project_root.mkdir(parents=True, exist_ok=True)
    if ontology_path.exists():
        ontology_action = "skipped existing"
    else:
        try:
            with ontology_path.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(ONTOLOGY_STARTER)
            ontology_action = "created"
        except FileExistsError:
            ontology_action = "skipped existing"

    changed = inject_agents_section(agent_path, render_agents_section(project_root, entities))
    print(f"{ontology_action} {ontology_path}")
    print(f"{'updated' if changed else 'unchanged'} {agent_path}")


if __name__ == "__main__":
    main()
