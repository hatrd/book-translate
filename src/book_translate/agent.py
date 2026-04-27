from __future__ import annotations

import shutil
import zipfile
from pathlib import Path


def build_whole_book_agent_prompt(source_md: Path, source_epub: Path, output_dir: Path) -> str:
    return f"""你是一位 INTJ 型图书翻译与电子书制作 agent。请完整阅读输入书籍材料，自己判断目录、章节边界、术语表和翻译执行策略，然后输出一个可发布的中文 Markdown 书籍文件夹。\n\n输入材料：\n- 完整源 Markdown：{source_md}\n- 完整源 EPUB：{source_epub}\n- 输出目录：{output_dir}\n\n核心原则：\n- 你必须完整理解整本书结构后再组织输出。\n- 不要按固定字符数机械切分最终章节；技术分块只允许作为你内部翻译策略。\n- 如果运行环境支持子 agent，你可以按真实章节或部件开子 agent 并行翻译，但必须统一术语表和最终风格。\n- 最终 Markdown 文件必须按真实书籍结构组织，而不是按临时 chunk 组织。\n\n必须产出：\n- {output_dir}/chapters/：按阅读顺序排列的章节 Markdown，例如 001-preface.md、002-introduction.md。\n- {output_dir}/glossary.yml：全书统一术语表。\n- {output_dir}/translation-report.md：说明你如何识别章节、如何处理图片/脚注/HTML 残留、是否有需要人工复核的问题。\n- 如源书含图片，保留或引用 {output_dir}/images/ 下的资源。\n\n翻译要求：\n- 英文翻译为简体中文。\n- 风格为自然、准确、适合商业/管理类图书的中文出版风。\n- 清理 Calibre/Pandoc 残留的无意义 span/div/class/amznremoved/page id。\n- 保留必要图片、图题、脚注、强调、列表和链接。\n- 术语必须全书一致；重要概念首次出现可附英文括注。\n- 不要输出整本合并 Markdown，除非它只是你内部临时文件；最终主产物是 chapters/。\n\n执行方式：\n1. 读取 source.md；必要时检查 source.epub 的目录、spine 或内部 HTML 来恢复真实章节。\n2. 建立全局术语表。\n3. 翻译并整理每个真实章节。\n4. 写入 chapters/*.md、glossary.yml、translation-report.md。\n5. 完成前自检：chapters/ 不得只有 untitled；不得把整本书塞进一个章节；不得留下大量无意义 HTML 噪声。\n\n只在完成文件写入后，用简短中文总结输出了哪些文件。\n"""


def extract_epub_images(source_epub: Path, images_dir: Path) -> list[Path]:
    if not source_epub.exists():
        return []
    images_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    try:
        with zipfile.ZipFile(source_epub) as archive:
            for name in sorted(archive.namelist()):
                lower = name.lower()
                if not lower.startswith("images/") or not lower.endswith((".jpeg", ".jpg", ".png", ".gif", ".webp", ".svg")):
                    continue
                target = images_dir / Path(name).name
                with archive.open(name) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                copied.append(target)
    except zipfile.BadZipFile:
        return []
    return copied


def validate_agent_output(output_dir: Path) -> None:
    chapters = output_dir / "chapters"
    files = sorted(chapters.glob("*.md")) if chapters.exists() else []
    if not files:
        raise RuntimeError(f"Whole-book agent did not create chapter Markdown files under {chapters}")
