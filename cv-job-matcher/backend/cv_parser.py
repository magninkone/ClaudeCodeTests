"""Extract and normalize text from CV files (PDF, DOCX) or plain text."""

import re
from pathlib import Path
from typing import Optional, Union

import pdfplumber
from docx import Document


def normalize_text(text: str) -> str:
    """Normalize text for matching: lowercase, strip, collapse whitespace."""
    if not text or not text.strip():
        return ""
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def extract_from_pdf(file_path: str) -> str:
    """Extract text from a PDF file."""
    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            content = page.extract_text()
            if content:
                text_parts.append(content)
    return normalize_text("\n".join(text_parts))


def extract_from_docx(file_path: str) -> str:
    """Extract text from a DOCX file."""
    doc = Document(file_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return normalize_text("\n".join(paragraphs))


def extract_from_bytes(data: bytes, filename: str) -> str:
    """Extract text from file bytes based on extension."""
    path = Path(filename)
    suffix = path.suffix.lower()
    # Write to temp file for libraries that need a path
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        if suffix == ".pdf":
            return extract_from_pdf(tmp_path)
        if suffix in (".docx", ".doc"):
            return extract_from_docx(tmp_path)
        # Fallback: treat as plain text
        return normalize_text(data.decode("utf-8", errors="replace"))
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def parse_cv(content: Union[str, bytes], filename: Optional[str] = None) -> str:
    """
    Parse CV from either plain text or file bytes.
    - If content is str, normalize and return.
    - If content is bytes, use filename extension to choose PDF/DOCX parser.
    """
    if isinstance(content, str):
        return normalize_text(content)
    if isinstance(content, bytes):
        name = filename or "document.txt"
        return extract_from_bytes(content, name)
    return ""
