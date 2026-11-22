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
START = "<!-- agentify:start -->"
END = "<!-- agentify:end -->"
FENCE = re.compile(r"^ {0,3}((?:~{3,})|(?:\x60{3,}))(.*)$")


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


def connect_guidance(original, section, use_legacy):
    newline = "\r\n" if b"\r\n" in original else "\n"
    bom = b"\xef\xbb\xbf" if original.startswith(b"\xef\xbb\xbf") else b""
    content = original.decode("utf-8-sig")
    lines = content.splitlines(keepends=True)
    visible = list(visible_lines(lines))
    markers = [(index, line.strip()) for index, line in visible if line.strip() in (START, END)]
    if markers:
        if [marker for _, marker in markers] != [START, END]:
            raise ValueError("Expected one complete agentify section in project guidance")
        start, end = [index for index, _ in markers]
        block = "".join(line for index, line in visible if start < index < end)
        missing = {f"]({path})" for path in DOCUMENTS if f"]({path})" not in block}
        repairs = [line for line in section.splitlines() if any(link in line for link in missing)]
        if repairs:
            lines[end:end] = [line + newline for line in repairs]
        return bom + "".join(lines).encode("utf-8")

    if not content:
        content = "# 에이전트 지침" + newline
        if use_legacy:
            content += newline + "먼저 [기존 프로젝트 지침](AGENTs.md)을 읽고 함께 적용한다." + newline

    if not content.endswith(("\n", "\r")):
        content += newline
    if not content.endswith(newline * 2):
        content += newline
    return bom + (content + section.replace("\n", newline)).encode("utf-8")


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


def initialize(root):
    if not root.is_dir():
        raise ValueError(f"Workspace must be an existing directory: {root}")

    checked_path(root, "memory", directory=True)
    documents = [(checked_path(root, name), (ASSETS / name).read_bytes()) for name in DOCUMENTS]
    guidance, use_legacy = guidance_path(root)
    section = (ASSETS / "AGENTS.section.md").read_text(encoding="utf-8")
    original = guidance.read_bytes() if guidance.exists() else None
    updated = connect_guidance(original or b"", section, use_legacy)

    (root / "memory").mkdir(exist_ok=True)
    for path, data in documents:
        create_document(path, data)
    update_guidance(guidance, original, updated)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path, help="Existing workspace directory")
    args = parser.parse_args()
    try:
        initialize(args.project_root.resolve())
    except (OSError, ValueError) as error:
        parser.exit(1, f"agentify: {error}\n")


if __name__ == "__main__":
    main()
