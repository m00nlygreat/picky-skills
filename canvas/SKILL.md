---
name: canvas
description: Open local Markdown and other project files in a reusable, live-reloading browser canvas. Use when Codex needs to preview, present, or visually inspect a file while editing it, especially Markdown with relative images and links. The bundled loopback-only server chooses an available port, renders CommonMark and GitHub Flavored Markdown with remark, blocks paths outside the project root, and reloads the page when the source file changes.
---

# Canvas

Open a project file in a local browser preview that stays current while the file is edited.

## Start a preview

Run the bundled script from the project root:

```powershell
node <skill-dir>/scripts/canvas-server.js start --path "relative/path/to/file.md"
```

Read the returned JSON and open `url`, preferably in the in-app browser. Present `markdownLink` to the user when they need to open it themselves.

The server binds only to `127.0.0.1`, selects an available port automatically, and is reused for later files in the same project. Change the `path` query parameter to preview another project-relative file.

Install bundled dependencies once if Node reports that `remark` is missing:

```powershell
npm install --prefix <skill-dir> --omit=dev
```

## Manage the server

Run commands from the same project root:

```powershell
node <skill-dir>/scripts/canvas-server.js status
node <skill-dir>/scripts/canvas-server.js stop
```

Pass `--root <project-directory>` only when the current directory is not the intended project root.

## Rendering behavior

- Render `.md` and `.markdown` with `remark`, including GitHub Flavored Markdown tables, task lists, strikethrough, and autolinks.
- Resolve Markdown images through the project-scoped asset endpoint and open relative links inside Canvas.
- Show common text and browser-supported media safely; offer a download link for unsupported binary files.
- Reload the open page through server-sent events when the selected file changes.
- Reject absolute paths, traversal outside the project root, directories, and symlink escapes.

To support another format, add a renderer object with `supports(file)` and `render(file, context)` to the registry in `scripts/canvas-server.js`. Use the context helpers `assetUrl`, `documentUrl`, and `escapeHtml`, and keep unsupported files on the fallback path.
