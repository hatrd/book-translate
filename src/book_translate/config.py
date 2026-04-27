from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CONFIG = {
    "source_language": "en",
    "target_language": "zh-Hans",
    "style": "简体中文出版风",
    "chunk_max_chars": 6000,
}


@dataclass(frozen=True)
class ProjectConfig:
    root: Path
    book_path: Path
    source_language: str = "en"
    target_language: str = "zh-Hans"
    style: str = "简体中文出版风"
    chunk_max_chars: int = 6000

    @property
    def work(self) -> Path:
        return self.root / "work"

    @property
    def source_dir(self) -> Path:
        return self.work / "source"

    @property
    def segments_dir(self) -> Path:
        return self.work / "segments"

    @property
    def translations_dir(self) -> Path:
        return self.work / "translations"

    @property
    def dist_dir(self) -> Path:
        return self.root / "dist"

    @property
    def glossary_path(self) -> Path:
        return self.work / "glossary.yml"

    @property
    def config_path(self) -> Path:
        return self.root / "book-translate.json"


def init_project(book_path: Path | str, root: Path | str = ".") -> ProjectConfig:
    book = Path(book_path).expanduser().resolve()
    project_root = Path(root).expanduser().resolve()
    config = ProjectConfig(root=project_root, book_path=book)

    for directory in [config.source_dir, config.segments_dir, config.translations_dir, config.dist_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    data = dict(DEFAULT_CONFIG)
    data["book_path"] = str(book)
    config.config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not config.glossary_path.exists():
        config.glossary_path.write_text("terms: {}\nconflicts: []\n", encoding="utf-8")
    return config


def load_config(root: Path | str = ".") -> ProjectConfig:
    project_root = Path(root).expanduser().resolve()
    data = json.loads((project_root / "book-translate.json").read_text(encoding="utf-8"))
    return ProjectConfig(
        root=project_root,
        book_path=Path(data["book_path"]).expanduser().resolve(),
        source_language=data.get("source_language", DEFAULT_CONFIG["source_language"]),
        target_language=data.get("target_language", DEFAULT_CONFIG["target_language"]),
        style=data.get("style", DEFAULT_CONFIG["style"]),
        chunk_max_chars=int(data.get("chunk_max_chars", DEFAULT_CONFIG["chunk_max_chars"])),
    )


def require_tools(tools: list[str]) -> list[str]:
    return [tool for tool in tools if shutil.which(tool) is None]
