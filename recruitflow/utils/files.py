from __future__ import annotations

from pathlib import Path

import docx
import fitz


def extract_text(file_name: str, content: bytes) -> str:
    suffix = Path(file_name).suffix.lower()
    if suffix == ".pdf":
        with fitz.open(stream=content, filetype="pdf") as doc:
            return "\n".join(page.get_text() for page in doc)
    if suffix in {".docx", ".doc"}:
        tmp = Path("uploads") / file_name
        tmp.parent.mkdir(exist_ok=True)
        tmp.write_bytes(content)
        document = docx.Document(tmp)
        return "\n".join(p.text for p in document.paragraphs)
    return content.decode("utf-8", errors="ignore")

