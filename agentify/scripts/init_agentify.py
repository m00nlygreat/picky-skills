#!/usr/bin/env python3
"""Create missing agent documents and connect them to the project guidance."""

import argparse
import os
import re
import stat
from pathlib import Path
from tempfile import NamedTemporaryFile


ASSETS = Path(__file__).resolve().parent.parent / "assets"
DOCUMENTS = ("SOUL.md", "MEMORY.md", "HEARTBEAT.md", "memory/INDEX.md")
LEGACY_MARKERS = {"<!-- agentify:start -->", "<!-- agentify:end -->"}
FENCE = re.compile(r"^ {0,3}((?:~{3,})|(?:\x60{3,}))(.*)$")
SECTION_HEADING = re.compile(r"^ {0,3}##[ \t]+에이전트 운영[ \t]*#*[ \t]*$")
TOP_HEADING = re.compile(r"^ {0,3}#{1,2}(?:[ \t]+|$)")


def checked_path(root, name, *, directory=False):
    path = root / name
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"Path points outside the workspace: {path}")
    if path.exists() or path.is_symlink():
        valid = path.is_dir() if directory else path.is_file()
        if not valid:
            raise ValueError(f"Expected a {'directory' if directory else 'file'}: {path}")
    return path


def guidance_path(root):
    canonical = checked_path(root, "AGENTS.md")
    if canonical.exists():
        # Report the actual spelling on case-insensitive file systems.
        return next(
            (path for path in root.iterdir() if path.name.casefold() == "agents.md"
             and path.samefile(canonical)),
            canonical,
        ), False
    legacy = checked_path(root, "AGENTs.md")
    return canonical, legacy.exists()


def visible_lines(lines):
    """Yield offsets and lines that are outside fenced Markdown examples."""
    fence = None
    for index, line in enumerate(lines):
        match = FENCE.match(line.rstrip("\r\n"))
        if fence:
            if match and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not match[2].strip():
                fence = None
        elif match:
            fence = match[1]
        else:
            yield index, line
    if fence:
        raise ValueError("Unclosed fenced code block in project guidance")


def connect_guidance(original, section, use_legacy, *, with_user):
    newline = "\r\n" if b"\r\n" in original else "\n"
    bom = b"\xef\xbb\xbf" if original.startswith(b"\xef\xbb\xbf") else b""
    content = original.decode("utf-8-sig")
    lines = content.splitlines(keepends=True)
    visible = list(visible_lines(lines))
    legacy_offsets = {index for index, line in visible if line.strip() in LEGACY_MARKERS}
    if legacy_offsets:
        lines = [line for index, line in enumerate(lines) if index not in legacy_offsets]
        visible = list(visible_lines(lines))

    start = next((index for index, line in visible if SECTION_HEADING.match(line.rstrip("\r\n"))), None)
    end = len(lines)
    if start is not None:
        end = next(
            (index for index, line in visible if index > start and TOP_HEADING.match(line)),
            len(lines),
        )
    guidance = "".join(line for _, line in visible)

    document_names = DOCUMENTS
    if with_user or "](USER.md)" in guidance:
        document_names += ("USER.md",)
        user_rule = (ASSETS / "AGENTS.user.md").read_text(encoding="utf-8")
        section = section.rstrip() + "\n" + user_rule

    missing = {f"]({path})" for path in document_names if f"]({path})" not in guidance}
    existing_core = any(f"]({path})" in guidance for path in DOCUMENTS)
    if not missing:
        return bom + "".join(lines).encode("utf-8"), document_names

    if start is not None:
        repairs = [
            line for line in section.splitlines()
            if line.startswith("- ") and (not existing_core or any(link in line for link in missing))
        ]
        if repairs:
            while end > start + 1 and not lines[end - 1].strip():
                end -= 1
            if end and not lines[end - 1].endswith(("\n", "\r")):
                lines[end - 1] += newline
            lines[end:end] = [line + newline for line in repairs]
        return bom + "".join(lines).encode("utf-8"), document_names

    content = "".join(lines)
    if existing_core:
        missing_core = any(f"]({path})" in missing for path in DOCUMENTS)
        repairs = [
            line for line in section.splitlines()
            if any(link in line for link in missing)
            or (
                missing_core and line.startswith("- ") and line not in guidance
                and not any(f"]({path})" in line for path in document_names)
            )
        ]
        section = "## 에이전트 운영\n\n" + "\n".join(repairs) + "\n"
    if not content:
        content = "# 에이전트 지침" + newline
        if use_legacy:
            content += newline + "먼저 [기존 프로젝트 지침](AGENTs.md)을 읽고 함께 적용한다." + newline

    if not content.endswith(("\n", "\r")):
        content += newline
    if not content.endswith(newline * 2):
        content += newline
    return bom + (content + section.replace("\n", newline)).encode("utf-8"), document_names


def create_document(path, data):
    try:
        with path.open("xb") as stream:
            stream.write(data)
    except FileExistsError:
        if not path.is_file():
            raise
        print(f"existing {path}")
    else:
        print(f"created {path}")


def update_guidance(path, original, updated):
    if updated == original:
        print(f"unchanged {path}")
        return
    if original is None:
        with path.open("xb") as stream:
            stream.write(updated)
        print(f"created {path}")
        return

    target = path.resolve()
    with NamedTemporaryFile(dir=target.parent, prefix=".agentify-", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        temporary.write_bytes(updated)
        temporary.chmod(stat.S_IMODE(target.stat().st_mode))
        if target.read_bytes() != original:
            raise ValueError(f"Project guidance changed during initialization. Run again: {path}")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"updated {path}")


def initialize(root, *, with_user=False):
    if not root.is_dir():
        raise ValueError(f"Workspace must be an existing directory: {root}")

    checked_path(root, "memory", directory=True)
    guidance, use_legacy = guidance_path(root)
    section = (ASSETS / "AGENTS.section.md").read_text(encoding="utf-8")
    original = guidance.read_bytes() if guidance.exists() else None
    updated, document_names = connect_guidance(original or b"", section, use_legacy, with_user=with_user)
    documents = [(checked_path(root, name), (ASSETS / name).read_bytes()) for name in document_names]

    (root / "memory").mkdir(exist_ok=True)
    for path, data in documents:
        create_document(path, data)
    update_guidance(guidance, original, updated)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path, help="Existing workspace directory")
    parser.add_argument("--with-user", action="store_true", help="Enable the optional USER.md profile")
    args = parser.parse_args()
    try:
        initialize(args.project_root.resolve(), with_user=args.with_user)
    except (OSError, ValueError) as error:
        parser.exit(1, f"agentify: {error}\n")


if __name__ == "__main__":
    main()
