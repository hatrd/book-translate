from __future__ import annotations

import json
import re
from pathlib import Path

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def _flush_chunk(chunks: list[dict], segments_dir: Path, chunk_id: int, heading_prefix: str, body: list[str], heading: str) -> int:
    if not body:
        return chunk_id
    chunk_name = f"{chunk_id:04d}.md"
    text = heading_prefix + "\n\n" + "\n\n".join(part.strip() for part in body if part.strip()) + "\n"
    (segments_dir / chunk_name).write_text(text, encoding="utf-8")
    chunks.append({"id": f"{chunk_id:04d}", "file": chunk_name, "heading": heading, "translation_file": chunk_name})
    return chunk_id + 1


def segment_markdown(source: Path | str, segments_dir: Path | str, max_chars: int = 6000) -> list[dict]:
    source_path = Path(source)
    out_dir = Path(segments_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    chunks: list[dict] = []
    current_heading_line = "# Untitled"
    current_heading = "Untitled"
    current_body: list[str] = []
    current_len = 0
    chunk_id = 1

    paragraphs = [part.strip() for part in source_path.read_text(encoding="utf-8").split("\n\n") if part.strip()]
    for paragraph in paragraphs:
        match = _HEADING.match(paragraph.splitlines()[0]) if paragraph else None
        if match:
            chunk_id = _flush_chunk(chunks, out_dir, chunk_id, current_heading_line, current_body, current_heading)
            current_body = []
            current_len = len(paragraph)
            current_heading_line = paragraph
            current_heading = match.group(2)
            continue

        if current_body and current_len + len(paragraph) > max_chars:
            chunk_id = _flush_chunk(chunks, out_dir, chunk_id, current_heading_line, current_body, current_heading)
            current_body = []
            current_len = len(current_heading_line)
        current_body.append(paragraph)
        current_len += len(paragraph)

    _flush_chunk(chunks, out_dir, chunk_id, current_heading_line, current_body, current_heading)
    (out_dir / "manifest.json").write_text(json.dumps(chunks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return chunks


def load_manifest(segments_dir: Path | str) -> list[dict]:
    return json.loads((Path(segments_dir) / "manifest.json").read_text(encoding="utf-8"))
