from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def _format_terms(glossary: dict) -> str:
    terms = glossary.get("terms", {})
    if not terms:
        return "（暂无）"
    return "\n".join(f"- {term}: {translation}" for term, translation in sorted(terms.items()))


def build_translation_prompt(chunk_markdown: str, glossary: dict, heading: str = "") -> str:
    return f"""你是一位严谨的图书翻译编辑。请把下面英文 Markdown 翻译为中文。\n\n要求：\n- 译文风格：简体中文出版风，适合商业/管理类图书阅读。\n- 只输出翻译后的 Markdown，不要解释，不要包裹代码块。\n- 保留 Markdown 标题层级、段落、强调、列表和链接结构。\n- 正文以中文为主；重要概念首次出现可保留英文括注。\n- 严格遵守术语表；如果原文出现术语表中的英文术语，使用对应中文译名。\n\n当前章节：{heading or '未知'}\n\n术语表：\n{_format_terms(glossary)}\n\n待翻译 Markdown：\n{chunk_markdown}\n"""


def build_glossary_prompt(markdown: str, existing: dict) -> str:
    return f"""请从下面英文图书内容中提取需要保持全书一致的关键术语、人名、概念名，并给出简体中文译名。\n\n要求：\n- 输出 JSON，格式为 {{"terms": {{"english term": "中文译名"}}}}。\n- 不要输出解释。\n- 已有术语优先，不要随意改译。\n\n已有术语：\n{_format_terms(existing)}\n\n内容：\n{markdown}\n"""


class CodexRunner:
    def __init__(self, dry_run: bool = False, model: str | None = None):
        self.dry_run = dry_run
        self.model = model

    def _command(self, output_file: Path) -> list[str]:
        command = ["codex", "exec", "--output-last-message", str(output_file)]
        if self.model:
            command.extend(["--model", self.model])
        command.append("-")
        return command

    def _run_prompt(self, prompt: str, output_file: Path) -> str:
        command = self._command(output_file)
        try:
            completed = subprocess.run(command, check=True, text=True, capture_output=True, input=prompt)
        except subprocess.CalledProcessError as error:
            details = (error.stderr or error.output or "Codex failed without stderr").strip()
            raise RuntimeError(f"codex exec failed with exit code {error.returncode}: {details}") from error
        if output_file.exists():
            return output_file.read_text(encoding="utf-8")
        return completed.stdout

    def translate(self, prompt: str, output: Path | str, prompt_path: Path | str) -> Path:
        out = Path(output)
        prompt_file = Path(prompt_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        prompt_file.parent.mkdir(parents=True, exist_ok=True)
        prompt_file.write_text(prompt, encoding="utf-8")
        if self.dry_run:
            out.write_text(f"<!-- DRY RUN: prompt written to {prompt_file} -->\n\n", encoding="utf-8")
            return out
        self._run_prompt(prompt, out)
        return out

    def complete(self, prompt: str) -> str:
        if self.dry_run:
            return '{"terms": {}}'
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "codex-last-message.txt"
            return self._run_prompt(prompt, output_file)
