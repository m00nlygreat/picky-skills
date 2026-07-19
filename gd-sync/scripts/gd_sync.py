#!/usr/bin/env python3
"""Safely push or pull a directory with Google Drive via gog CLI."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

CONFIG_NAME = "gd-sync.yml"
DEFAULT_IGNORES = [CONFIG_NAME]
FOLDER_MIME = "application/vnd.google-apps.folder"
GOOGLE_EXPORTS = {
    "application/vnd.google-apps.document": ("docx", ".docx"),
    "application/vnd.google-apps.spreadsheet": ("xlsx", ".xlsx"),
    "application/vnd.google-apps.presentation": ("pptx", ".pptx"),
    "application/vnd.google-apps.drawing": ("png", ".png"),
}


def find_gog() -> str | None:
    found = shutil.which("gog")
    if found:
        return found
    if os.name == "nt":
        fallback = Path.home() / ".local" / "bin" / "gog.exe"
        if fallback.is_file():
            return str(fallback)
    return None


def unquote(value: str) -> str:
    value = value.strip()
    if value in {"", "null", "~"}:
        return ""
    if value.startswith('"') and value.endswith('"'):
        return str(json.loads(value))
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    return value


def load_config(path: Path) -> dict[str, object]:
    result: dict[str, object] = {"drive_folder_id": "", "last_sync_at": "", "ignore": []}
    section = ""
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-"):
            if section != "ignore":
                raise ValueError(f"line {number}: list item is only valid under ignore")
            items = result["ignore"]
            assert isinstance(items, list)
            items.append(unquote(line[1:].strip()))
            continue
        if ":" not in line:
            raise ValueError(f"line {number}: expected key: value")
        key, value = line.split(":", 1)
        key = key.strip()
        if key not in result:
            raise ValueError(f"line {number}: unknown key {key!r}")
        if key == "ignore":
            if value.strip() not in {"", "[]"}:
                raise ValueError(f"line {number}: ignore must be a YAML list")
            section = "ignore"
        else:
            result[key] = unquote(value)
            section = ""
    ignores = [str(item) for item in result["ignore"] if str(item).strip()]
    result["ignore"] = list(dict.fromkeys(DEFAULT_IGNORES + ignores))
    return result


def write_config(path: Path, config: dict[str, object]) -> None:
    folder_id = str(config.get("drive_folder_id") or "")
    last_sync = str(config.get("last_sync_at") or "")
    ignores = [str(item) for item in config.get("ignore", DEFAULT_IGNORES)]
    ignores = list(dict.fromkeys(DEFAULT_IGNORES + ignores))
    lines = [
        f"drive_folder_id: {json.dumps(folder_id, ensure_ascii=False)}",
        f"last_sync_at: {json.dumps(last_sync) if last_sync else 'null'}",
        "ignore:",
    ]
    lines.extend(f"  - {json.dumps(item, ensure_ascii=False)}" for item in ignores)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ignored(relative: Path, patterns: list[str], is_dir: bool) -> bool:
    rel = relative.as_posix().lstrip("./")
    for raw_pattern in patterns:
        pattern = raw_pattern.strip().replace("\\", "/")
        if not pattern:
            continue
        directory_rule = pattern.endswith("/")
        pattern = pattern.strip("/")
        if directory_rule:
            if rel == pattern or rel.startswith(pattern + "/"):
                return True
            if "/" not in pattern and pattern in relative.parts:
                return True
            continue
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(relative.name, pattern):
            return True
        if is_dir and fnmatch.fnmatch(rel + "/", pattern):
            return True
    return False


def stage_tree(root: Path, destination: Path, patterns: list[str]) -> tuple[int, int]:
    copied_files = 0
    ignored_entries = 0
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        kept_dirs: list[str] = []
        for name in dirs:
            source = current_path / name
            relative = source.relative_to(root)
            if ignored(relative, patterns, True):
                ignored_entries += 1
            elif source.is_symlink():
                raise ValueError(f"symbolic link is not supported: {relative}")
            else:
                kept_dirs.append(name)
                (destination / relative).mkdir(parents=True, exist_ok=True)
        dirs[:] = kept_dirs
        for name in files:
            source = current_path / name
            relative = source.relative_to(root)
            if ignored(relative, patterns, False):
                ignored_entries += 1
                continue
            if source.is_symlink():
                raise ValueError(f"symbolic link is not supported: {relative}")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied_files += 1
    return copied_files, ignored_entries


def file_md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_child(parent: Path, name: str) -> Path:
    if not name or name in {".", ".."} or Path(name).name != name or "/" in name or "\\" in name:
        raise ValueError(f"unsafe Drive item name: {name!r}")
    return parent / name


def list_drive_folder(gog: str, folder_id: str) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    page = ""
    while True:
        command = [
            gog, "drive", "ls", "--parent", folder_id, "--max", "1000", "--json",
            "--fields", "files(id,name,mimeType,md5Checksum),nextPageToken",
        ]
        if page:
            command.extend(["--page", page])
        completed = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8")
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "gog drive ls failed")
        payload = json.loads(completed.stdout)
        files = payload.get("files", [])
        if not isinstance(files, list):
            raise ValueError("unexpected gog drive ls response")
        items.extend(item for item in files if isinstance(item, dict))
        page = str(payload.get("nextPageToken") or "")
        if not page:
            return items


def pull_tree(gog: str, folder_id: str, root: Path, patterns: list[str], dry_run: bool) -> tuple[int, int, int, int]:
    creates = updates = skips = ignored_entries = 0
    seen: set[str] = set()

    def visit(remote_id: str, relative: Path) -> None:
        nonlocal creates, updates, skips, ignored_entries
        for item in list_drive_folder(gog, remote_id):
            name = str(item.get("name") or "")
            item_id = str(item.get("id") or "")
            mime = str(item.get("mimeType") or "")
            child = safe_child(relative, name)
            is_dir = mime == FOLDER_MIME
            if ignored(child, patterns, is_dir):
                ignored_entries += 1
                continue
            export = GOOGLE_EXPORTS.get(mime)
            if mime.startswith("application/vnd.google-apps.") and not is_dir and not export:
                raise ValueError(f"unsupported Google-native file: {child.as_posix()} ({mime})")
            if export and not child.name.lower().endswith(export[1]):
                child = child.with_name(child.name + export[1])
            key = child.as_posix().casefold()
            if key in seen:
                raise ValueError(f"duplicate Drive path after export: {child.as_posix()}")
            seen.add(key)
            target = root / child
            if is_dir:
                if target.exists() and not target.is_dir():
                    raise ValueError(f"remote folder conflicts with local file: {child.as_posix()}")
                if not target.exists():
                    print(f"create_folder\t{child.as_posix()}")
                    if not dry_run:
                        target.mkdir(parents=True, exist_ok=True)
                visit(item_id, child)
                continue
            if target.exists() and not target.is_file():
                raise ValueError(f"remote file conflicts with local directory: {child.as_posix()}")
            remote_md5 = str(item.get("md5Checksum") or "")
            if target.is_file() and remote_md5 and file_md5(target) == remote_md5:
                skips += 1
                print(f"skip_file\t{child.as_posix()}\tmd5 match")
                continue
            action = "update_file" if target.exists() else "create_file"
            if action == "update_file":
                updates += 1
            else:
                creates += 1
            print(f"{action}\t{child.as_posix()}\tremote source")
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                command = [gog, "drive", "download", item_id, "--out", str(target), "--overwrite"]
                if export:
                    command.extend(["--format", export[0]])
                completed = subprocess.run(command, check=False)
                if completed.returncode != 0:
                    raise RuntimeError(f"gog download failed: {child.as_posix()}")

    visit(folder_id, Path())
    return creates, updates, skips, ignored_entries


def setup_guidance(message: str) -> None:
    print(message, file=sys.stderr)
    print("Install: https://gogcli.sh/install.html", file=sys.stderr)
    print("Configure:", file=sys.stderr)
    print("  gog auth credentials set <oauth-client.json>", file=sys.stderr)
    print("  gog auth add <email>", file=sys.stderr)
    print("  gog auth list --check", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="local directory containing gd-sync.yml")
    parser.add_argument("--direction", choices=("push", "pull"), default="push")
    parser.add_argument("--dry-run", action="store_true", help="show gog's reconciliation plan")
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"Local root is not a directory: {root}", file=sys.stderr)
        return 2

    gog = find_gog()
    if not gog:
        setup_guidance("gog CLI was not found on PATH or in ~/.local/bin.")
        return 3
    if subprocess.run([gog, "--version"], check=False).returncode != 0:
        setup_guidance("gog CLI exists but could not run.")
        return 3
    if subprocess.run([gog, "auth", "status"], check=False).returncode != 0:
        setup_guidance("gog authentication configuration is unavailable.")
        return 4

    config_path = root / CONFIG_NAME
    if not config_path.exists():
        write_config(config_path, {
            "drive_folder_id": "REPLACE_WITH_DRIVE_FOLDER_ID",
            "last_sync_at": "",
            "ignore": DEFAULT_IGNORES,
        })
        print(f"Created configuration: {config_path}")
        print("Set drive_folder_id, then run the command again.")
        return 2
    try:
        config = load_config(config_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Invalid {CONFIG_NAME}: {exc}", file=sys.stderr)
        return 2

    folder_id = str(config["drive_folder_id"]).strip()
    if not folder_id or folder_id == "REPLACE_WITH_DRIVE_FOLDER_ID":
        print(f"Set drive_folder_id in {config_path}", file=sys.stderr)
        return 2

    patterns = [str(item) for item in config["ignore"]]
    if args.direction == "pull":
        try:
            creates, updates, skips, ignored_count = pull_tree(
                gog, folder_id, root, patterns, args.dry_run
            )
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
            print(f"Pull failed: {exc}", file=sys.stderr)
            return 2
        print(
            f"Pull summary: create_files={creates} update_files={updates} "
            f"skip_files={skips} ignored={ignored_count}"
        )
        if args.dry_run:
            print("Pull dry run completed; local files and last_sync_at were not changed.")
        else:
            config["last_sync_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            write_config(config_path, config)
            print(f"Pull completed; last_sync_at={config['last_sync_at']}")
        return 0

    with tempfile.TemporaryDirectory(prefix="gd-sync-") as temp_name:
        staging = Path(temp_name)
        try:
            files, skipped = stage_tree(root, staging, patterns)
        except (OSError, ValueError) as exc:
            print(f"Could not prepare synchronization: {exc}", file=sys.stderr)
            return 2
        print(f"Prepared {files} file(s); ignored {skipped} entry/entries.")
        command = [gog, "drive", "sync", "push", str(staging), "--parent", folder_id]
        if args.dry_run:
            command.append("--dry-run")
        completed = subprocess.run(command, check=False)

    if completed.returncode != 0:
        print("gog push failed. If the error mentions credentials, tokens, or keyring, run:", file=sys.stderr)
        print("  gog auth credentials set <oauth-client.json>", file=sys.stderr)
        print("  gog auth add <email>", file=sys.stderr)
        print("  gog auth list --check", file=sys.stderr)
        return completed.returncode
    if args.dry_run:
        print("Dry run completed; last_sync_at was not changed.")
    else:
        config["last_sync_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        write_config(config_path, config)
        print(f"Push completed; last_sync_at={config['last_sync_at']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
