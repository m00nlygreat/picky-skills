---
name: gd-sync
description: Push or pull a local directory against a configured Google Drive folder with gog CLI. Use when the user asks to initialize, inspect, dry-run, upload, download, or synchronize a folder governed by gd-sync.yml, including ignore rules and last-sync tracking.
---

# Google Drive Sync

Reconcile a local folder with Google Drive in an explicitly selected direction. Push uses `gog drive sync push`; pull recursively lists and downloads Drive items. Never claim either operation is bidirectional. Push never deletes remote-only files, and pull never deletes local-only files.

## Push workflow

1. Identify the local root from the user's request. Use the current working directory only when the intended root is unambiguous.
2. Run the bundled script in inspection mode first:

   ```powershell
   python <skill-dir>/scripts/gd_sync.py --root <local-root> --dry-run
   ```

3. If `gog` is missing or authentication is not configured, relay the script's setup guidance and stop.
4. If `gd-sync.yml` is missing, the script creates it and stops. Ask the user to fill `drive_folder_id`, or fill it from a Drive folder URL/ID explicitly supplied by the user.
5. Inspect `gd-sync.yml`. Require a non-placeholder `drive_folder_id`. Preserve `gd-sync.yml` in the ignore list.
6. Show the dry-run result. Do not perform a real push unless the user requested synchronization or confirms after inspection.
7. Execute the push:

   ```powershell
   python <skill-dir>/scripts/gd_sync.py --root <local-root>
   ```

8. Report whether the push completed and the new `last_sync_at` value.

## Pull workflow

1. Inspect `gd-sync.yml` and require a non-placeholder `drive_folder_id`.
2. Run pull in inspection mode first:

   ```powershell
   python <skill-dir>/scripts/gd_sync.py --root <local-root> --direction pull --dry-run
   ```

3. Show files that would be created or overwritten. Pull never deletes local-only files.
4. Do not overwrite local files unless the user explicitly requested pull or confirms after inspecting the dry-run.
5. Execute pull:

   ```powershell
   python <skill-dir>/scripts/gd_sync.py --root <local-root> --direction pull
   ```

6. Report created, updated, skipped, and ignored counts plus the new `last_sync_at` value.
7. Treat same-name remote paths, unsafe names, and file/folder type conflicts as errors instead of guessing.
8. Export Google Docs, Sheets, Slides, and Drawings as DOCX, XLSX, PPTX, and PNG respectively; reject unsupported Google-native types.

## Configuration

Use this schema in `<local-root>/gd-sync.yml`:

```yaml
drive_folder_id: "Google Drive folder ID"
last_sync_at: null
ignore:
  - "gd-sync.yml"
  - ".agents/"
  - ".codex/"
  - ".claude/"
  - ".git/"
  - "*.tmp"
```

- Interpret ignore entries as path globs relative to the local root.
- Apply ignore entries in both push and pull directions.
- Treat a trailing `/` as a directory and all of its descendants.
- Always ignore `gd-sync.yml` and the agent configuration directories `.agents/`, `.codex/`, and `.claude/`, even if a user removes them from the list.
- Update `last_sync_at` only after a successful non-dry-run push.
- Update `last_sync_at` only after a successful non-dry-run push or pull.
- Refuse local symbolic links instead of silently following them.

## Authentication

The script detects a missing CLI or base configuration. If `gog` reports missing credentials or tokens during push, guide the user through:

```powershell
gog auth credentials set <oauth-client.json>
gog auth add <email>
gog auth list --check
```

Allow the user's configured keyring to prompt interactively. Never request, print, or persist the keyring password in project files or command history.
