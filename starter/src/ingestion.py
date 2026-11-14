"""Read and normalize source data for the LDN 2020 (Cong Bao) corpus.

Two supported sources:
- data/extracted/pages.jsonl : page-level extraction produced by data/prepare_data.py
                               (pymupdf, per-page text, section tracking). Preferred.
- raw PDF files              : extracted here with pymupdf on the fly.

Every page keeps its document_id, source path and physical page number so
chunks stay traceable to the source (required by the lab manifest).
"""
import json
import re
import unicodedata
from pathlib import Path

import pymupdf

from .models import DocumentPage

# Running header of the printed Cong Bao (repeats on most pages, useless noise).
GAZETTE_HEADER_RE = re.compile(
    r"^\s*\d*\s*CÔNG BÁO/Số\s*7\d\d\s*\+\s*7\d\d/Ngày .*?\d{4}\s*$"
)


def normalize_text(text: str) -> str:
    """Normalize Unicode and whitespace without discarding useful structure."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\u00ad", "")  # soft hyphen
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    # collapse 3+ blank lines to one paragraph break, keep single newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_recurring_headers(pages: list[DocumentPage]) -> list[DocumentPage]:
    """Remove Cong Bao running headers and bare page-number lines.

    Deterministic: only drops lines matching the known gazette header pattern
    or standalone numbers, so no content line is ever lost.
    """
    cleaned: list[DocumentPage] = []
    for page in pages:
        kept_lines = []
        for line in page.text.split("\n"):
            stripped = line.strip()
            if GAZETTE_HEADER_RE.match(stripped):
                continue
            if re.fullmatch(r"\d{1,3}", stripped):  # bare printed page number
                continue
            kept_lines.append(line)
        page.text = normalize_text("\n".join(kept_lines))
        cleaned.append(page)
    return cleaned


def load_pages_jsonl(path: Path) -> list[DocumentPage]:
    """Load the prepared per-page extraction (data/extracted/pages.jsonl)."""
    pages: list[DocumentPage] = []
    with path.open(encoding="utf-8") as fin:
        for line in fin:
            rec = json.loads(line)
            pages.append(
                DocumentPage(
                    document_id=rec["document_id"],
                    source=rec["file"],
                    page=rec["page"],
                    text=normalize_text(rec["text"]),
                    metadata={
                        "section": rec.get("section", ""),
                        "section_title": rec.get("section_title", ""),
                        "page_type": rec.get("page_type", ""),
                        "chars": rec.get("chars", 0),
                    },
                )
            )
    return strip_recurring_headers(pages)


def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    """Extract each physical page with pymupdf; keep page number and source.

    Pages with no extractable text are kept and flagged metadata["empty"]=True
    (scanned pages would need OCR as a separate step).
    """
    pages: list[DocumentPage] = []
    with pymupdf.open(path) as doc:
        for i in range(len(doc)):
            text = normalize_text(doc[i].get_text())
            meta: dict = {"empty": len(text) == 0}
            pages.append(
                DocumentPage(
                    document_id=document_id,
                    source=source,
                    page=i + 1,
                    text=text,
                    metadata=meta,
                )
            )
    return pages
