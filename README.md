# book-translate

[中文说明](README.zh-CN.md)

`book-translate` turns a local `.azw3` book into a publishable Chinese Markdown folder, then lets you export that folder to EPUB with Pandoc.

The core design choice of this project is to **trust the agent**. The outer Python program does not mechanically split the book into fixed-size chunks or pretend those chunks are chapters. Instead, it prepares the complete source workspace and hands the whole book to one Codex agent. The agent reads the full book context, recovers the real structure, builds the glossary, decides whether it needs internal sub-agents, and writes the final chapter Markdown files.

## Recommended Flow

Run from this repository root:

```bash
cd /path/to/book-translate

PYTHONPATH=src python3 -m book_translate to-md \
  "input-book.azw3" \
  book-zh
```

The output folder should contain:

- `chapters/`: the main output, split into ordered chapter Markdown files such as `001-introduction.md`.
- `images/`: image resources extracted from the source EPUB when present.
- `glossary.yml`: global terminology table created by the agent.
- `translation-report.md`: notes about structure detection, cleanup, and review risks.
- `.book-translate-work/`: hidden workspace containing `source.epub`, `source.md`, and `agent-instructions.md`.

If the run fails halfway, rerun the same command after fixing the reported issue.

## Dry Run First

Use dry run when you want to inspect exactly what will be handed to the agent before spending time on translation:

```bash
PYTHONPATH=src python3 -m book_translate to-md \
  "input-book.azw3" \
  book-zh \
  --dry-run
```

Then read:

```bash
less book-zh/.book-translate-work/agent-instructions.md
```

When the instructions look right, run the same command again without `--dry-run`.

## Export EPUB

After `book-zh/chapters/` exists, export it with Pandoc:

```bash
pandoc book-zh/chapters/*.md \
  --resource-path=book-zh/chapters \
  --toc \
  --toc-depth=2 \
  --split-level=2 \
  --metadata title="Translated Book Title" \
  --metadata author="Author Name" \
  --metadata lang=zh \
  -o book-zh.epub
```

Important EPUB export notes:

- Use `--resource-path=book-zh/chapters` when chapter Markdown files reference images as `../images/00001.jpeg`. This lets Pandoc resolve the path from the chapter directory and actually package the images into the EPUB.
- Keep `--toc-depth=2` for a chapter/subsection table of contents. If your generated Markdown uses `###` headings that should appear in the EPUB TOC, change it to `--toc-depth=3`.
- Use `--split-level=2` so each `##` subsection becomes its own XHTML file in the EPUB. This avoids reader-specific bugs where TOC links to nested heading anchors jump back to the chapter's top-level heading.
- If you use `--toc-depth=3`, consider `--split-level=3` for the same reason.
- If the source contains a cover image, pass it explicitly with `--epub-cover-image=book-zh/images/<cover-file>`; otherwise unreferenced images are not included automatically.

## Requirements

- Python 3.11+
- Calibre, for `ebook-convert`
- Pandoc, for source EPUB-to-Markdown conversion and final EPUB export
- Codex CLI, for `codex exec`

Check the machine once:

```bash
PYTHONPATH=src python3 -m book_translate doctor
```

On Fedora, install the external tools with:

```bash
sudo dnf install calibre pandoc
```

## What Happens Internally

```text
AZW3 -> source.epub/source.md/images -> whole-book Codex agent -> chapters/*.md -> pandoc EPUB
```

The outer program only prepares source files and instructions. The Codex agent is responsible for:

- Reading the whole `source.md`, and consulting `source.epub` if needed.
- Recovering real book structure from headings, TOC, spine, layout cues, and context.
- Building one global glossary.
- Translating into natural Simplified Chinese publishing style.
- Cleaning Calibre/Pandoc HTML noise.
- Writing `chapters/*.md`, `glossary.yml`, and `translation-report.md`.

This is intentionally different from a fixed chunk pipeline. Chunking is allowed only as the agent's internal execution strategy; it should not leak into the final book structure.

## Reasoning Effort

The current implementation does **not** explicitly set Codex reasoning effort. It calls:

```text
codex exec --output-last-message <file> -
```

So reasoning effort comes from your Codex CLI default/profile. In this environment, Codex has been running with `reasoning effort: medium` unless overridden by your config.

If we want this project to force a higher effort for book translation, the next change should add a CLI option such as `--reasoning-effort high` and pass it through to `codex exec` using a Codex config override.

## Advanced Stage Commands

The older staged commands remain available for debugging, but they are not the default publishing workflow:

```bash
PYTHONPATH=src python3 -m book_translate init book.azw3
PYTHONPATH=src python3 -m book_translate extract
PYTHONPATH=src python3 -m book_translate glossary
PYTHONPATH=src python3 -m book_translate export output.epub
```
