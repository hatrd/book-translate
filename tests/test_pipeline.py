import json
import unittest
from pathlib import Path
from unittest import mock

from book_translate.config import init_project, require_tools
from book_translate.segment import segment_markdown
from book_translate.glossary import merge_glossary_terms
from book_translate.codex import build_translation_prompt, CodexRunner
from book_translate.assemble import assemble_translations


class PipelineTests(unittest.TestCase):
    def test_init_project_creates_resumable_workspace(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            book = tmp_path / "book.azw3"
            book.write_bytes(b"book")

            config = init_project(book, tmp_path / "workspace")

            self.assertEqual(config.book_path, book)
            self.assertTrue((config.root / "work/source").is_dir())
            self.assertTrue((config.root / "work/segments").is_dir())
            self.assertTrue((config.root / "work/translations").is_dir())
            self.assertTrue((config.root / "dist").is_dir())
            self.assertTrue((config.root / "book-translate.json").exists())
            data = json.loads((config.root / "book-translate.json").read_text())
            self.assertEqual(data["source_language"], "en")

    def test_require_tools_reports_missing_tools(self):
        with mock.patch("book_translate.config.shutil.which", lambda name: None if name == "pandoc" else f"/usr/bin/{name}"):
            missing = require_tools(["ebook-convert", "pandoc", "codex"])

        self.assertEqual(missing, ["pandoc"])

    def test_segment_markdown_preserves_headings_and_chunks_paragraphs(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            markdown = "# Chapter One\n\nFirst paragraph.\n\nSecond paragraph.\n\n## Section\n\nThird paragraph."
            source = tmp_path / "source.md"
            source.write_text(markdown)
            segments_dir = tmp_path / "segments"

            manifest = segment_markdown(source, segments_dir, max_chars=40)

            self.assertEqual([item["heading"] for item in manifest], ["Chapter One", "Chapter One", "Section"])
            self.assertTrue((segments_dir / manifest[0]["file"]).read_text().startswith("# Chapter One"))
            self.assertIn("Second paragraph.", (segments_dir / manifest[1]["file"]).read_text())
            self.assertTrue((segments_dir / "manifest.json").exists())

    def test_merge_glossary_terms_keeps_existing_translation_and_records_conflict(self):
        existing = {"terms": {"culture map": "文化地图"}, "conflicts": []}
        incoming = {"terms": {"culture map": "文化图谱", "lead": "领导"}}

        merged = merge_glossary_terms(existing, incoming)

        self.assertEqual(merged["terms"]["culture map"], "文化地图")
        self.assertEqual(merged["terms"]["lead"], "领导")
        self.assertEqual(merged["conflicts"], [{"term": "culture map", "existing": "文化地图", "incoming": "文化图谱"}])

    def test_build_translation_prompt_injects_glossary_style_and_markdown(self):
        prompt = build_translation_prompt(
            chunk_markdown="# Title\n\nCulture map text.",
            glossary={"terms": {"culture map": "文化地图"}},
            heading="Title",
        )

        self.assertIn("简体中文出版风", prompt)
        self.assertIn("culture map: 文化地图", prompt)
        self.assertIn("# Title", prompt)
        self.assertIn("只输出翻译后的 Markdown", prompt)

    def test_codex_runner_dry_run_writes_prompt_without_executing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            runner = CodexRunner(dry_run=True)
            output = tmp_path / "out.md"
            prompt_path = tmp_path / "prompt.txt"

            result = runner.translate("Translate me", output, prompt_path)

            self.assertEqual(result, output)
            self.assertTrue(output.read_text().startswith("<!-- DRY RUN"))
            self.assertIn("Translate me", prompt_path.read_text())

    def test_assemble_translations_orders_chunks(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            manifest = [
                {"id": "0002", "translation_file": "0002.md"},
                {"id": "0001", "translation_file": "0001.md"},
            ]
            translations = tmp_path / "translations"
            translations.mkdir()
            (translations / "0001.md").write_text("第一段")
            (translations / "0002.md").write_text("第二段")
            output = tmp_path / "book.zh.md"

            assemble_translations(manifest, translations, output)

            self.assertEqual(output.read_text(), "第一段\n\n第二段\n")


if __name__ == "__main__":
    unittest.main()

class ChapterOutputTests(unittest.TestCase):
    def test_write_chapter_markdown_files_groups_chunks_by_heading(self):
        import tempfile
        from book_translate.assemble import write_chapter_markdown_files

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            translations = root / "translations"
            translations.mkdir()
            (translations / "0001.md").write_text("# Intro\n\n第一段", encoding="utf-8")
            (translations / "0002.md").write_text("# Intro\n\n第二段", encoding="utf-8")
            (translations / "0003.md").write_text("# Next Step\n\n第三段", encoding="utf-8")
            manifest = [
                {"id": "0001", "heading": "Intro", "translation_file": "0001.md"},
                {"id": "0002", "heading": "Intro", "translation_file": "0002.md"},
                {"id": "0003", "heading": "Next Step", "translation_file": "0003.md"},
            ]

            written = write_chapter_markdown_files(manifest, translations, root / "chapters")

            self.assertEqual([path.name for path in written], ["001-intro.md", "002-next-step.md"])
            self.assertIn("第一段\n\n第二段", written[0].read_text(encoding="utf-8"))
            self.assertIn("第三段", written[1].read_text(encoding="utf-8"))

class CodexRunnerInvocationTests(unittest.TestCase):
    def test_codex_complete_sends_prompt_on_stdin_and_reads_last_message_file(self):
        import subprocess
        from unittest import mock

        def fake_run(command, check, text, capture_output, input):
            self.assertIn("--output-last-message", command)
            self.assertEqual(command[-1], "-")
            self.assertEqual(input, "prompt text")
            output_file = Path(command[command.index("--output-last-message") + 1])
            output_file.write_text('{"terms": {"Culture Map": "文化地图"}}', encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="transcript", stderr="")

        with mock.patch("book_translate.codex.subprocess.run", fake_run):
            result = CodexRunner().complete("prompt text")

        self.assertEqual(result, '{"terms": {"Culture Map": "文化地图"}}')

    def test_codex_translate_raises_error_with_stderr_when_codex_fails(self):
        import subprocess
        import tempfile
        from unittest import mock

        def fake_run(command, check, text, capture_output, input):
            raise subprocess.CalledProcessError(1, command, output="stdout text", stderr="auth failed")

        with tempfile.TemporaryDirectory() as td, mock.patch("book_translate.codex.subprocess.run", fake_run):
            runner = CodexRunner()
            with self.assertRaisesRegex(RuntimeError, "auth failed"):
                runner.translate("prompt", Path(td) / "out.md", Path(td) / "prompt.txt")

class WholeBookAgentHelpersTests(unittest.TestCase):
    def test_build_whole_book_agent_prompt_contains_workspace_contract(self):
        from book_translate.agent import build_whole_book_agent_prompt

        prompt = build_whole_book_agent_prompt(
            source_md=Path("/tmp/work/source/source.md"),
            source_epub=Path("/tmp/work/source/source.epub"),
            output_dir=Path("/tmp/out"),
        )

        self.assertIn("完整阅读", prompt)
        self.assertIn("/tmp/work/source/source.md", prompt)
        self.assertIn("/tmp/work/source/source.epub", prompt)
        self.assertIn("/tmp/out/chapters", prompt)
        self.assertIn("不要按固定字符数机械切分", prompt)

    def test_extract_epub_images_copies_images_from_epub(self):
        import tempfile
        import zipfile
        from book_translate.agent import extract_epub_images

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            epub = root / "source.epub"
            with zipfile.ZipFile(epub, "w") as archive:
                archive.writestr("images/00001.jpeg", b"image")
                archive.writestr("text/chapter.html", "<p>x</p>")

            copied = extract_epub_images(epub, root / "out" / "images")

            self.assertEqual([path.name for path in copied], ["00001.jpeg"])
            self.assertEqual((root / "out" / "images" / "00001.jpeg").read_bytes(), b"image")
