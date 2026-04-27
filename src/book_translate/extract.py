from __future__ import annotations

import subprocess
from pathlib import Path


def extract_to_markdown(book_path: Path | str, source_dir: Path | str, force: bool = False) -> Path:
    book = Path(book_path)
    out_dir = Path(source_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    epub = out_dir / "source.epub"
    markdown = out_dir / "source.md"
    if markdown.exists() and not force:
        return markdown
    subprocess.run(["ebook-convert", str(book), str(epub)], check=True)
    subprocess.run(["pandoc", str(epub), "-t", "gfm", "-o", str(markdown)], check=True)
    return markdown
