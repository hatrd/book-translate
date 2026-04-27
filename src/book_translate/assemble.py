from __future__ import annotations

from pathlib import Path


def assemble_translations(manifest: list[dict], translations_dir: Path | str, output: Path | str) -> Path:
    translations = Path(translations_dir)
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    parts = []
    for item in sorted(manifest, key=lambda value: value["id"]):
        file_name = item.get("translation_file") or item["file"]
        parts.append((translations / file_name).read_text(encoding="utf-8").strip())
    out.write_text("\n\n".join(part for part in parts if part) + "\n", encoding="utf-8")
    return out


def _slugify_heading(value: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "chapter"


def _without_repeated_heading(text: str, previous_heading: str | None) -> str:
    if not previous_heading:
        return text.strip()
    lines = text.strip().splitlines()
    if lines and lines[0].lstrip("# ").strip() == previous_heading:
        return "\n".join(lines[1:]).strip()
    return text.strip()


def write_chapter_markdown_files(manifest: list[dict], translations_dir: Path | str, chapters_dir: Path | str) -> list[Path]:
    translations = Path(translations_dir)
    out_dir = Path(chapters_dir)
    if out_dir.exists():
        for child in out_dir.glob("*.md"):
            child.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)

    grouped: list[tuple[str, list[str]]] = []
    for item in sorted(manifest, key=lambda value: value["id"]):
        heading = item.get("heading") or "Untitled"
        file_name = item.get("translation_file") or item["file"]
        text = (translations / file_name).read_text(encoding="utf-8")
        if not grouped or grouped[-1][0] != heading:
            grouped.append((heading, [text]))
        else:
            grouped[-1][1].append(_without_repeated_heading(text, heading))

    written: list[Path] = []
    for index, (heading, parts) in enumerate(grouped, start=1):
        path = out_dir / f"{index:03d}-{_slugify_heading(heading)}.md"
        path.write_text("\n\n".join(part.strip() for part in parts if part.strip()) + "\n", encoding="utf-8")
        written.append(path)
    return written
