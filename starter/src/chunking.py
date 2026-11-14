"""Chunking strategies: fixed-size, paragraph and structure-aware (by article).

Strategies used by the benchmark (see src/run.py):
- A: fixed_size    — character windows per page
- B: by_paragraph  — paragraph groups per page
- C: by_article    — one chunk per "Dieu" (article) of the law, spanning pages;
                     metadata carries dieu/chuong so queries can filter by section.
"""
import re

from .models import Chunk, DocumentPage

# "Dieu 10. Tieu chi, quyen va nghia vu ..." — article heading on its own line.
ARTICLE_RE = re.compile(r"^Điều\s*(\d+)\.[ \t]*(.*)$", re.M)
# Chuong heading is alone on its own line; the ALL-CAPS title follows on the
# next line. Body-text references ("Muc 1 Chuong III") must never match.
CHUONG_RE = re.compile(r"^Chương\s+([IVX]+)[ \t]*$", re.M)

STRATEGY_FIXED = "fixed"
STRATEGY_PARAGRAPH = "paragraph"
STRATEGY_ARTICLE = "article"


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


def by_article(pages: list[DocumentPage]) -> list[Chunk]:
    """One chunk per law article ("Dieu"), joining text that spans pages.

    Only pages classified as real content are used, so table-of-contents or
    near-empty gazette pages cannot create phantom articles. Metadata carries
    dieu number/title and the current chuong (chapter) for metadata filtering.
    """
    content_pages = [p for p in pages if p.metadata.get("page_type", "noi_dung") == "noi_dung"]
    full_text = "\n".join(p.text for p in content_pages)

    # Track which physical page each character position came from.
    offsets: list[tuple[int, int]] = []  # (start_offset, page_number)
    cursor = 0
    for p in content_pages:
        offsets.append((cursor, p.page))
        cursor += len(p.text) + 1  # +1 for the join newline

    def page_at(pos: int) -> int:
        result = offsets[0][1]
        for start, number in offsets:
            if start <= pos:
                result = number
            else:
                break
        return result

    chuong, chuong_title = "", ""
    article_starts: list[dict] = []
    # Walk the document in position order: chapter headings update the current
    # chapter, article headings open a new chunk.
    events = [
        *(("chapter", m.start(), m) for m in CHUONG_RE.finditer(full_text)),
        *(("article", m.start(), m) for m in ARTICLE_RE.finditer(full_text)),
    ]
    events.sort(key=lambda item: item[1])
    for kind, pos, match in events:
        if kind == "chapter":
            title_line = next(
                (l.strip() for l in full_text[match.end() :].split("\n") if l.strip()), ""
            )
            if not title_line or title_line != title_line.upper():
                continue  # body-text cross-reference, not a real heading
            chuong = match.group(1)
            chuong_title = title_line
        else:
            article_starts.append(
                {
                    "dieu": int(match.group(1)),
                    "title": match.group(2).strip(),
                    "start": pos,
                    "chuong": chuong,
                    "chuong_title": chuong_title,
                }
            )

    chunks: list[Chunk] = []
    for i, article in enumerate(article_starts):
        end = article_starts[i + 1]["start"] if i + 1 < len(article_starts) else len(full_text)
        text = full_text[article["start"] : end].strip()
        if not text:
            continue
        page_start = page_at(article["start"])
        page_end = page_at(min(end, len(full_text) - 1))
        chunks.append(
            Chunk(
                chunk_id=f"{content_pages[0].document_id}#d{article['dieu']:03d}",
                document_id=content_pages[0].document_id,
                source=content_pages[0].source,
                page=page_start,
                text=text,
                metadata={
                    "strategy": STRATEGY_ARTICLE,
                    "dieu": article["dieu"],
                    "dieu_title": article["title"],
                    "chuong": article["chuong"],
                    "chuong_title": article["chuong_title"],
                    "page_start": page_start,
                    "page_end": page_end,
                },
            )
        )
    return chunks
