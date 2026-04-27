from __future__ import annotations

import subprocess
from pathlib import Path


def export_document(markdown: Path | str, output: Path | str) -> Path:
    source = Path(markdown)
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["pandoc", str(source), "-o", str(target)], check=True)
    return target
