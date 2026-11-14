"""Implement fixed-size and structure-aware chunking."""
import re

from .models import Chunk, DocumentPage

STRATEGY_FIXED = "fixed"
STRATEGY_PARAGRAPH = "paragraph"


def _base(page: DocumentPage, suffix: str) -> dict:
    """Common metadata every chunk inherits from its page."""
    return {
        "strategy": suffix,
        "section": page.metadata.get("section", ""),
        "section_title": page.metadata.get("section_title", ""),
        "page_type": page.metadata.get("page_type", ""),
    }


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    """Split page text into overlapping character windows, keeping page metadata."""
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")
    text = page.text
    if not text:
        return []
    step = size - overlap
    chunks: list[Chunk] = []
    start = 0
    index = 0
    while start < len(text):
        end = min(start + size, len(text))
        window = text[start:end].strip()
        if window:
            chunks.append(
                Chunk(
                    chunk_id=f"{page.document_id}#p{page.page:03d}#f{index:02d}",
                    document_id=page.document_id,
                    source=page.source,
                    page=page.page,
                    text=window,
                    metadata={**_base(page, STRATEGY_FIXED), "char_start": start, "char_end": end},
                )
            )
            index += 1
        if end == len(text):
            break
        start += step
    return chunks


def _split_long_paragraph(text: str, max_size: int) -> list[str]:
    """Hard-split an oversized paragraph into <=max_size pieces."""
    return [text[i : i + max_size].strip() for i in range(0, len(text), max_size)]


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """Group paragraphs (blank-line separated) up to max_size chars.

    Oversized paragraphs are hard-split; each chunk stays on one page.
    """
    if not page.text:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", page.text) if p.strip()]
    groups: list[str] = []
    current = ""
    for para in paragraphs:
        pieces = [para] if len(para) <= max_size else _split_long_paragraph(para, max_size)
        for piece in pieces:
            if current and len(current) + 1 + len(piece) <= max_size:
                current = f"{current}\n{piece}"
            else:
                if current:
                    groups.append(current)
                current = piece
    if current:
        groups.append(current)

    return [
        Chunk(
            chunk_id=f"{page.document_id}#p{page.page:03d}#g{i:02d}",
            document_id=page.document_id,
            source=page.source,
            page=page.page,
            text=group,
            metadata=_base(page, STRATEGY_PARAGRAPH),
        )
        for i, group in enumerate(groups)
    ]
