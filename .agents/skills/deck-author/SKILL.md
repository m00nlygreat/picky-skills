---
name: deck-author
description: Create, refactor, validate, and compile Markdown slide decks for md2ppt. Use when Codex needs to produce a root deck Markdown file, embedded child Markdown modules, slide-ready assets, layout or note directives, tables, code blocks, image references, or a .pptx output through md2ppt.
---

# Md2ppt Deck Author

## Overview

Use this skill to author Markdown that converts cleanly through [md2ppt](https://github.com/m00nlygreat/md2ppt) into PowerPoint. The converter flattens embedded Markdown, parses slides/placeholders, and renders them into a reference `.pptx` template.
## Workflow

1. Identify the deck root, target audience, duration, and source material.
2. Create a root Markdown file with deck-level YAML frontmatter that includes `title`. If compiling a lesson `text.md` directly, add YAML frontmatter with `title` there too.
3. Put lesson content in child Markdown modules under a stable folder such as `modules/`; put generated or collected visual assets under `attachments/`.
4. Use md2ppt grammar deliberately: `#` or `##` starts a slide, `---` or `___` forces a new slide, and `***` splits placeholders inside the current slide.
5. Keep child modules free of YAML frontmatter unless there is a specific reason; `flatten.py` ignores child frontmatter.
6. Save slide image assets as transparent PNG project files and reference them with relative Markdown image paths. If a new raster visual is needed for a slide, use `$imagegen` and move the final project-bound `.png` into `attachments/` before referencing it.
7. Validate the deck structure before final delivery. Compile only if the user wants a `.pptx`; assume `md2ppt` is installed as a CLI command on `PATH`. Use built-in templates by name with `--template`; use `--ref` only for an explicit external `.pptx` template path.

## File Structure

Prefer this shape:

```text
deck-title.md
modules/
  01-intro.md
  02-practice.md
attachments/
  concept-map.png
  workflow-step.png
debug/
```

Root file pattern:

```markdown
---
title: Deck Title
author: Instructor Name
---

# Chapter Title

![](modules/01-intro.md)

# Practice

![](modules/02-practice.md)
```

Child module pattern:

```markdown
## Slide Title

- One clear idea
- Keep bullets short

***

![](../attachments/example.png)

---

### Supporting Heading

Use `###` to add an in-slide heading instead of starting a new slide.
```

## Slide Image Types

When planning or creating visuals, explicitly classify requested slide images using these six default types. These are defaults, not hard boundaries: if the user asks for an image that crosses categories, create the hybrid image that best serves the slide instead of forcing it into only one type.

1. Concept diagram: a simple relationship map of the core idea, usually 3-5 named elements connected by lines. Keep in-image text to element names, not explanatory sentences.
2. Process image: a workflow, flowchart, sequence, or timeline that shows the slide's steps. Prefer four or fewer steps with short labels and clear directional flow.
3. System/technical structure image: an architecture, data-flow, or component diagram. Show the main actors, interface, processing layer, storage, model, or external services as named blocks.
4. Case/example image: a representative example, before/after comparison, result mockup, or 2-3 comparison cards. Use real provided material when available; otherwise create a clearly illustrative example.
5. Metaphor image: a visual analogy for the deck's message, such as scattered inputs becoming an organized structure or multiple streams converging into one output. Prefer little or no text.
6. Markup image: annotations on a provided screenshot or image, using boxes, arrows, numbers, highlights, and short labels to point out key UI areas, issues, or comparison points. If no source screenshot or image is available, ask the user to provide one before making the markup image.

All final deck-referenced images must be transparent PNG files. Source screenshots or references may arrive in other formats, but the asset saved under `attachments/` should be a `.png` with an alpha channel; preserve opaque screenshot/photo content when needed and keep any canvas, padding, or non-image background transparent.

## Authoring Rules

- Any Markdown file passed directly to `md2ppt` must start with YAML frontmatter containing `title`; otherwise the generated PPTX may have an empty or broken title slide.
- Use standalone `![](child.md)` lines for embeds. `flatten.py` only expands Markdown embeds that occupy the full line.
- Use standalone image lines. Local image files are inserted into picture placeholders; inline images are not a reliable slide content pattern.
- Do not put a table and an image on the same slide. Treat tables and images as conceptually equivalent explanatory formats; choose one, or split them into separate slides when both are needed.
- Do not add `[layout]: # (...)` by default. md2ppt infers the layout from headings, slide breaks, and placeholder count.
- Use `[layout]: # (layout_name)` only when intentionally forcing a layout that exists in the target template and cannot be inferred automatically. Do not add internal/default layout names such as `section_header`, `title_and_content`, or `two_content` unless the target template actually contains that layout name.
- Use `[note]: # (speaker note text)` on its own line for slide notes.
- Prefer `##` for normal content slides inside modules. Use `#` when a section divider or table-of-contents chapter is intentional.
- Keep each slide to one main message. If a slide needs both text and media, separate areas with `***`.
- Use pipe tables only for small tables that can fit in one slide placeholder.
- Use fenced code blocks for code; include the language tag for syntax highlighting.

Read `references/md2ppt-format.md` when you need the full syntax, conversion pipeline, layouts, or examples.

## Validation And Compile

Run the bundled checker from the project root:

```powershell
python .\.agents\skills\deck-author\scripts\check_md2ppt_deck.py ".\deck-title.md"
```

Compile through the `md2ppt` CLI when a `.pptx` is requested:

```powershell
python .\.agents\skills\deck-author\scripts\check_md2ppt_deck.py ".\deck-title.md" --compile --out ".\deck-title.pptx" --template default
```

List built-in templates with `md2ppt --list-templates`. Do not ask for or assume a local md2ppt repository path. If the checker reports missing assets or malformed embeds, fix the Markdown files before compiling again. If compilation fails because `md2ppt` is unavailable, report that the CLI is not installed or not on `PATH`.
