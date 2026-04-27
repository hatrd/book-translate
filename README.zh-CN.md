# book-translate

`book-translate` 用于把本地 `.azw3` 书籍转换成可发布的中文 Markdown 文件夹，然后可以用 Pandoc 导出 EPUB。

本项目的核心设计选择是：**充分信任 agent 能力**。外层 Python 程序不把书机械切成固定长度 chunk，也不假装这些 chunk 就是章节。它只负责准备完整的源书工作区，然后把整本书交给一个 Codex agent。agent 会阅读完整上下文，恢复真实书籍结构，建立全局术语表，决定是否需要内部子 agent，并写出最终章节 Markdown 文件。

## 推荐流程

在仓库根目录运行：

```bash
cd /path/to/book-translate

PYTHONPATH=src python3 -m book_translate to-md \
  "input-book.azw3" \
  book-zh
```

输出目录应包含：

- `chapters/`：主输出，按阅读顺序拆分的章节 Markdown，例如 `001-introduction.md`。
- `images/`：从源 EPUB 中提取出的图片资源，如果源书包含图片。
- `glossary.yml`：agent 创建的全局术语表。
- `translation-report.md`：结构识别、清理策略和需要人工复核的问题说明。
- `.book-translate-work/`：隐藏工作区，包含 `source.epub`、`source.md` 和 `agent-instructions.md`。

如果运行中途失败，修复报错后重新运行同一个命令即可。

## 先 Dry Run

如果想先检查交给 agent 的完整任务说明，而不是立刻开始翻译，可以运行：

```bash
PYTHONPATH=src python3 -m book_translate to-md \
  "input-book.azw3" \
  book-zh \
  --dry-run
```

然后查看：

```bash
less book-zh/.book-translate-work/agent-instructions.md
```

确认说明符合预期后，去掉 `--dry-run` 再运行正式翻译。

## 导出 EPUB

当 `book-zh/chapters/` 生成后，用 Pandoc 导出 EPUB：

```bash
pandoc book-zh/chapters/*.md \
  --resource-path=book-zh/chapters \
  --toc \
  --toc-depth=2 \
  --split-level=2 \
  --metadata title="译本书名" \
  --metadata author="Author Name" \
  --metadata lang=zh \
  -o book-zh.epub
```

EPUB 导出注意事项：

- 当章节 Markdown 中的图片路径是 `../images/00001.jpeg` 这类形式时，应使用 `--resource-path=book-zh/chapters`。这样 Pandoc 会从章节目录出发解析相对路径，并把图片真正打包进 EPUB。
- `--toc-depth=2` 会把章和二级小节写入目录。如果生成的 Markdown 使用了需要进入目录的 `###` 标题，可以改成 `--toc-depth=3`。
- `--split-level=2` 会把每个 `##` 小节拆成独立 XHTML 文件，避免部分阅读器点击目录中的小节锚点时跳回本章一级标题。
- 如果使用 `--toc-depth=3`，也可以考虑搭配 `--split-level=3`，原因同上。
- 如果源书包含封面图，需要显式添加 `--epub-cover-image=book-zh/images/<cover-file>`；未被正文引用的图片不会自动进入最终 EPUB。

## 依赖

- Python 3.11+
- Calibre：提供 `ebook-convert`
- Pandoc：用于源 EPUB 到 Markdown 的转换，以及最终 EPUB 导出
- Codex CLI：提供 `codex exec`

检查本机环境：

```bash
PYTHONPATH=src python3 -m book_translate doctor
```

Fedora 上可以安装外部工具：

```bash
sudo dnf install calibre pandoc
```

## 内部流程

```text
AZW3 -> source.epub/source.md/images -> whole-book Codex agent -> chapters/*.md -> pandoc EPUB
```

外层程序只准备源文件和任务说明。Codex agent 负责：

- 阅读完整 `source.md`，必要时参考 `source.epub`。
- 从标题、目录、spine、版式线索和上下文中恢复真实书籍结构。
- 建立一个全局术语表。
- 翻译成自然、准确、适合出版的简体中文。
- 清理 Calibre/Pandoc 残留的 HTML 噪声。
- 写出 `chapters/*.md`、`glossary.yml` 和 `translation-report.md`。

这与固定 chunk 流水线刻意不同。chunk 只允许作为 agent 的内部执行策略，不应该泄露到最终书籍结构中。

## 推理强度

当前实现没有显式设置 Codex reasoning effort。实际调用方式是：

```text
codex exec --output-last-message <file> -
```

因此推理强度由你的 Codex CLI 默认配置或 profile 决定。如果希望翻译整本书时强制使用更高推理强度，可以后续增加类似 `--reasoning-effort high` 的 CLI 参数，并把它透传给 `codex exec`。

## 高级分步命令

旧的分步命令仍保留用于调试，但它们不是默认发布流程：

```bash
PYTHONPATH=src python3 -m book_translate init book.azw3
PYTHONPATH=src python3 -m book_translate extract
PYTHONPATH=src python3 -m book_translate glossary
PYTHONPATH=src python3 -m book_translate export output.epub
```
