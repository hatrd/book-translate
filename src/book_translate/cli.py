from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from .agent import build_whole_book_agent_prompt, extract_epub_images, validate_agent_output
from .assemble import assemble_translations, write_chapter_markdown_files
from .codex import CodexRunner, build_glossary_prompt, build_translation_prompt
from .config import init_project, load_config, require_tools
from .extract import extract_to_markdown
from .export import export_document
from .glossary import load_glossary, merge_glossary_terms, parse_glossary_response, save_glossary
from .segment import load_manifest, segment_markdown



def _copy_output_folder(config, output_dir: Path, final_markdown: Path, include_whole_book: bool = False) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    if include_whole_book:
        shutil.copy2(final_markdown, output_dir / "book.zh.md")
    else:
        stale_whole_book = output_dir / "book.zh.md"
        if stale_whole_book.exists():
            stale_whole_book.unlink()
    if config.glossary_path.exists():
        shutil.copy2(config.glossary_path, output_dir / "glossary.yml")
    chapters_target = output_dir / "chapters"
    if chapters_target.exists():
        shutil.rmtree(chapters_target)
    shutil.copytree(config.dist_dir / "chapters", chapters_target)
    segments_target = output_dir / "segments"
    if segments_target.exists():
        shutil.rmtree(segments_target)
    shutil.copytree(config.segments_dir, segments_target)
    chunks_target = output_dir / "chunks"
    if chunks_target.exists():
        shutil.rmtree(chunks_target)
    shutil.copytree(config.translations_dir, chunks_target, ignore=shutil.ignore_patterns("*.prompt.txt"))


def cmd_to_md(args: argparse.Namespace) -> int:
    book = Path(args.book).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else book.with_suffix("")
    work_root = output_dir / ".book-translate-work"

    missing = require_tools(["ebook-convert", "pandoc", "codex"])
    if missing and not args.dry_run:
        print("Missing tools: " + ", ".join(missing))
        print("Install Calibre for ebook-convert, Pandoc for conversion, and Codex CLI for translation.")
        return 1

    print(f"[1/4] Preparing source workspace: {book}", flush=True)
    config = init_project(book, work_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    source = extract_to_markdown(config.book_path, config.source_dir, force=args.force)
    source_epub = config.source_dir / "source.epub"
    copied_images = extract_epub_images(source_epub, output_dir / "images")
    if copied_images:
        print(f"      Copied {len(copied_images)} image resources", flush=True)

    print("[2/4] Writing whole-book agent instructions", flush=True)
    prompt = build_whole_book_agent_prompt(source_md=source, source_epub=source_epub, output_dir=output_dir)
    instructions = work_root / "agent-instructions.md"
    instructions.parent.mkdir(parents=True, exist_ok=True)
    instructions.write_text(prompt, encoding="utf-8")
    if args.dry_run:
        print(f"Dry run: wrote agent instructions to {instructions}", flush=True)
        return 0

    print("[3/4] Running whole-book Codex agent", flush=True)
    runner = CodexRunner(dry_run=False, model=args.model)
    runner.complete(prompt)

    validate_agent_output(output_dir)
    print(f"[4/4] Markdown folder ready: {output_dir}", flush=True)
    return 0

def cmd_init(args: argparse.Namespace) -> int:
    config = init_project(args.book, args.root)
    print(f"Initialized workspace at {config.root}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    missing = require_tools(["ebook-convert", "pandoc", "codex"])
    if missing:
        print("Missing tools: " + ", ".join(missing))
        print("Install Calibre for ebook-convert, Pandoc for export/conversion, and Codex CLI for translation.")
        return 1
    print("All required tools found.")
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    config = load_config(args.root)
    missing = require_tools(["ebook-convert", "pandoc"])
    if missing:
        print("Missing tools: " + ", ".join(missing))
        return 1
    path = extract_to_markdown(config.book_path, config.source_dir, force=args.force)
    print(path)
    return 0


def cmd_segment(args: argparse.Namespace) -> int:
    config = load_config(args.root)
    source = Path(args.source) if args.source else config.source_dir / "source.md"
    manifest = segment_markdown(source, config.segments_dir, max_chars=args.max_chars or config.chunk_max_chars)
    print(f"Wrote {len(manifest)} segments to {config.segments_dir}")
    return 0


def cmd_glossary(args: argparse.Namespace) -> int:
    config = load_config(args.root)
    source = config.source_dir / "source.md"
    if not source.exists():
        print(f"Missing source Markdown: {source}")
        print("Run extract first, or use to-md to run the full pipeline.")
        return 1
    glossary = load_glossary(config.glossary_path)
    runner = CodexRunner(dry_run=args.dry_run, model=args.model)
    print(f"Building glossary from whole source Markdown: {source}", flush=True)
    response = runner.complete(build_glossary_prompt(source.read_text(encoding="utf-8"), glossary))
    glossary = merge_glossary_terms(glossary, parse_glossary_response(response))
    save_glossary(config.glossary_path, glossary)
    print(f"Glossary now has {len(glossary.get('terms', {}))} terms: {config.glossary_path}")
    return 0


def cmd_translate(args: argparse.Namespace) -> int:
    config = load_config(args.root)
    glossary = load_glossary(config.glossary_path)
    manifest = load_manifest(config.segments_dir)
    runner = CodexRunner(dry_run=args.dry_run, model=args.model)
    count = 0
    print(f"[4/6] Translating {len(manifest)} chunks", flush=True)
    translated_count = 0
    skipped_count = 0
    for index, item in enumerate(manifest, start=1):
        out = config.translations_dir / item.get("translation_file", item["file"])
        prompt_path = config.translations_dir / f"{item['id']}.prompt.txt"
        if out.exists() and not args.force:
            skipped_count += 1
            print(f"      Translation chunk {index}/{len(manifest)}: {item['id']} skipped", flush=True)
            continue
        chunk = (config.segments_dir / item["file"]).read_text(encoding="utf-8")
        prompt = build_translation_prompt(chunk, glossary, heading=item.get("heading", ""))
        runner.translate(prompt, out, prompt_path)
        count += 1
    print(f"Translated {count} chunks into {config.translations_dir}")
    return 0


def cmd_assemble(args: argparse.Namespace) -> int:
    config = load_config(args.root)
    manifest = load_manifest(config.segments_dir)
    output = Path(args.output) if args.output else config.dist_dir / "book.zh.md"
    assemble_translations(manifest, config.translations_dir, output)
    write_chapter_markdown_files(manifest, config.translations_dir, config.dist_dir / "chapters")
    print(output)
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    missing = require_tools(["pandoc"])
    if missing:
        print("Missing tools: " + ", ".join(missing))
        return 1
    config = load_config(args.root)
    source = Path(args.source) if args.source else config.dist_dir / "book.zh.md"
    target = Path(args.output)
    export_document(source, target)
    print(target)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="book-translate", description="Resumable book translation pipeline using Codex CLI.")
    parser.add_argument("--root", default=".", help="Workspace root containing book-translate.json")
    sub = parser.add_subparsers(dest="command", required=True)


    p = sub.add_parser("to-md", help="Translate an AZW3 book into an organized Markdown folder")
    p.add_argument("book")
    p.add_argument("output_dir", nargs="?", help="Output folder; defaults to the book filename without extension")
    p.add_argument("--dry-run", action="store_true", help="Write prompts/placeholders without calling Codex")
    p.add_argument("--force", action="store_true", help="Rebuild existing stage outputs")
    p.add_argument("--model")
    p.add_argument("--max-chars", type=int, help=argparse.SUPPRESS)
    p.add_argument("--glossary-limit", type=int, default=3, help=argparse.SUPPRESS)
    p.add_argument("--glossary-all", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--whole-book", action="store_true", help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_to_md)

    p = sub.add_parser("init", help="Create a resumable workspace")
    p.add_argument("book")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("doctor", help="Check external tools")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("extract", help="Convert AZW3 to source Markdown")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("segment", help="Split source Markdown into resumable chunks")
    p.add_argument("--source")
    p.add_argument("--max-chars", type=int)
    p.set_defaults(func=cmd_segment)

    p = sub.add_parser("glossary", help="Extract/evolve global glossary with Codex")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--model")
    p.add_argument("--limit", type=int, default=3, help=argparse.SUPPRESS)
    p.add_argument("--all", action="store_true", help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_glossary)

    p = sub.add_parser("translate", help="Translate chunks with Codex")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--model")
    p.set_defaults(func=cmd_translate)

    p = sub.add_parser("assemble", help="Assemble translated chunks into Markdown")
    p.add_argument("--output")
    p.set_defaults(func=cmd_assemble)

    p = sub.add_parser("export", help="Export translated Markdown with Pandoc")
    p.add_argument("output")
    p.add_argument("--source")
    p.set_defaults(func=cmd_export)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
