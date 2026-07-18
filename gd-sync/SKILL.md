---
name: gd-sync
description: Push a local directory to a configured Google Drive folder with gog CLI. Use when the user asks to initialize, inspect, dry-run, or execute local-to-Google-Drive folder synchronization governed by gd-sync.yml, including ignore rules and last-sync tracking.
---

# Google Drive Sync

Push a local folder to Google Drive with `gog drive sync push`. Treat the operation as one-way local-to-remote reconciliation; never claim it is bidirectional, and never delete remote-only files.

## Workflow

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

## Configuration

Use this schema in `<local-root>/gd-sync.yml`:

```yaml
drive_folder_id: "Google Drive folder ID"
last_sync_at: null
ignore:
  - "gd-sync.yml"
  - ".git/"
  - "*.tmp"
```

- Interpret ignore entries as path globs relative to the local root.
- Treat a trailing `/` as a directory and all of its descendants.
- Always ignore `gd-sync.yml`, even if a user removes it from the list.
- Update `last_sync_at` only after a successful non-dry-run push.
- Refuse local symbolic links instead of silently following them.

## Authentication

The script detects a missing CLI or base configuration. If `gog` reports missing credentials or tokens during push, guide the user through:

```powershell
gog auth credentials set <oauth-client.json>
gog auth add <email>
gog auth list --check
```

Allow the user's configured keyring to prompt interactively. Never request, print, or persist the keyring password in project files or command history.
