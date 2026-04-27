import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from book_translate.cli import main


class CliTests(unittest.TestCase):
    def test_cli_init_writes_config(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "project"
            book = Path(td) / "book.azw3"
            book.write_bytes(b"book")

            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["--root", str(root), "init", str(book)])

            self.assertEqual(code, 0)
            self.assertEqual(json.loads((root / "book-translate.json").read_text())["book_path"], str(book.resolve()))

    def test_cli_doctor_returns_nonzero_when_tool_missing(self):
        with mock.patch("book_translate.config.shutil.which", return_value=None):
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["doctor"])

        self.assertEqual(code, 1)


class WholeBookAgentWorkflowTests(unittest.TestCase):
    def test_to_md_hands_whole_book_workspace_to_one_codex_agent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            book = root / "book.azw3"
            book.write_bytes(b"book")
            out_dir = root / "md-book"
            prompts = []

            def fake_extract(book_path, source_dir, force=False):
                source_dir = Path(source_dir)
                source_dir.mkdir(parents=True, exist_ok=True)
                (source_dir / "source.epub").write_bytes(b"epub")
                source = source_dir / "source.md"
                source.write_text("# Raw Book\n\nINTRODUCTION\n\nHello culture map.", encoding="utf-8")
                return source

            class FakeRunner:
                def __init__(self, dry_run=False, model=None):
                    self.dry_run = dry_run
                    self.model = model

                def complete(self, prompt):
                    prompts.append(prompt)
                    (out_dir / "chapters").mkdir(parents=True, exist_ok=True)
                    (out_dir / "chapters" / "001-introduction.md").write_text("# 引言\n\n你好，文化地图。\n", encoding="utf-8")
                    (out_dir / "glossary.yml").write_text("terms:\n  culture map: 文化地图\n", encoding="utf-8")
                    (out_dir / "translation-report.md").write_text("# Report\n", encoding="utf-8")
                    return "done"

            stdout = io.StringIO()
            with mock.patch("book_translate.cli.require_tools", return_value=[]), \
                mock.patch("book_translate.cli.extract_to_markdown", fake_extract), \
                mock.patch("book_translate.cli.CodexRunner", FakeRunner), \
                contextlib.redirect_stdout(stdout):
                code = main(["to-md", str(book), str(out_dir)])

            self.assertEqual(code, 0)
            self.assertEqual(len(prompts), 1)
            self.assertIn("完整阅读", prompts[0])
            self.assertIn("source.md", prompts[0])
            self.assertIn("source.epub", prompts[0])
            self.assertIn(str(out_dir), prompts[0])
            self.assertTrue((out_dir / "chapters" / "001-introduction.md").exists())
            self.assertTrue((out_dir / "glossary.yml").exists())
            self.assertTrue((out_dir / "translation-report.md").exists())
            self.assertFalse((out_dir / "chunks").exists())
            self.assertFalse((out_dir / "segments").exists())
            self.assertIn("[3/4] Running whole-book Codex agent", stdout.getvalue())
            self.assertIn("[4/4] Markdown folder ready", stdout.getvalue())

    def test_to_md_fails_if_agent_does_not_create_chapters(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            book = root / "book.azw3"
            book.write_bytes(b"book")
            out_dir = root / "md-book"

            def fake_extract(book_path, source_dir, force=False):
                source_dir = Path(source_dir)
                source_dir.mkdir(parents=True, exist_ok=True)
                (source_dir / "source.epub").write_bytes(b"epub")
                source = source_dir / "source.md"
                source.write_text("body", encoding="utf-8")
                return source

            class FakeRunner:
                def __init__(self, dry_run=False, model=None):
                    pass

                def complete(self, prompt):
                    return "done without files"

            with mock.patch("book_translate.cli.require_tools", return_value=[]), \
                mock.patch("book_translate.cli.extract_to_markdown", fake_extract), \
                mock.patch("book_translate.cli.CodexRunner", FakeRunner), \
                contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, "chapters"):
                    main(["to-md", str(book), str(out_dir)])


class StandaloneGlossaryOnePassTests(unittest.TestCase):
    def test_glossary_command_scans_source_markdown_once(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            book = root / "book.azw3"
            book.write_bytes(b"book")
            with contextlib.redirect_stdout(io.StringIO()):
                main(["--root", str(root), "init", str(book)])
            source_dir = root / "work" / "source"
            source_dir.mkdir(parents=True, exist_ok=True)
            (source_dir / "source.md").write_text("# One\n\nAlpha.\n\n# Two\n\nBeta.", encoding="utf-8")
            prompts = []

            class FakeRunner:
                def __init__(self, dry_run=False, model=None):
                    pass

                def complete(self, prompt):
                    prompts.append(prompt)
                    return '{"terms": {"Alpha": "阿尔法", "Beta": "贝塔"}}'

            with mock.patch("book_translate.cli.CodexRunner", FakeRunner), contextlib.redirect_stdout(io.StringIO()):
                code = main(["--root", str(root), "glossary", "--all"])

            self.assertEqual(code, 0)
            self.assertEqual(len(prompts), 1)
            self.assertIn("# One", prompts[0])
            self.assertIn("# Two", prompts[0])


if __name__ == "__main__":
    unittest.main()
