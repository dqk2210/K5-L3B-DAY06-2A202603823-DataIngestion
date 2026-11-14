# -*- coding: utf-8 -*-
"""Verify benchmark evidence quotes against the extracted corpus pages."""
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parents[2]
PAGES = REPO / "data" / "extracted" / "pages.jsonl"
QUESTIONS = REPO / "benchmark" / "questions.jsonl"

_PUNCT = re.compile(r"[\"'“”‘’«»„‟\u00ad\u200b\u200c\u200d\ufeff]")


def squash(text: str) -> str:
    text = unicodedata.normalize("NFC", text).casefold()
    text = _PUNCT.sub("", text)
    return re.sub(r"\s+", "", text)


pages = [json.loads(l) for l in PAGES.open(encoding="utf-8")]
page_squash = {p["page"]: squash(p["text"]) for p in pages}
page_raw = {p["page"]: p["text"] for p in pages}
doc_of = {p["page"]: p["document_id"] for p in pages}

KEYWORD_MIN = 5  # độ dài từ tối thiểu để làm từ khóa định vị

questions = [json.loads(l) for l in QUESTIONS.open(encoding="utf-8") if l.strip()]
for q in questions:
    ev = q.get("evidence_quote", "")
    if isinstance(ev, list):
        ev = ev[0] if ev else ""
    needle = squash(ev)
    if not needle:
        continue
    hits = [(doc_of[pg], pg) for pg, sq in page_squash.items() if needle in sq]
    gold = q.get("gold_page")
    status = "OK (dung trang gold)" if any(pg == gold for _, pg in hits) else (
        "SAI TRANG gold" if hits else "KHONG TIM THAY quote nguyen van")
    if status == "OK (dung trang gold)":
        print(f"{q['id']:5s} [{status}]")
        continue

    # gợi ý vị trí thật: trang có nhiều từ khóa của quote nhất (lấy từ quote GỐC,
    # không phải chuỗi đã squash vì squash đã mất khoảng trắng giữa các từ)
    keywords = sorted({w for w in re.findall(r"[a-zà-ỹ0-9]{%d,}" % KEYWORD_MIN, ev.lower())},
                      key=len, reverse=True)[:6]
    best_page, best_score = None, 0
    for pg, sq in page_squash.items():
        score = sum(1 for kw in keywords if kw in sq)
        if score > best_score:
            best_page, best_score = pg, score
    print(f"{q['id']:5s} [{status}] gold_page={gold}")
    print(f"      evidence: {ev[:70]}")
    if best_page and best_score >= 2:
        sq = page_squash[best_page]
        anchor = min(keywords, key=lambda kw: sq.find(kw) if sq.find(kw) >= 0 else 10**9)
        pos = sq.find(anchor)
        lo, hi = max(0, pos - 100), min(len(sq), pos + 140)
        print(f"      doan gan nhat (file {doc_of[best_page]}, trang {best_page}, "
              f"{best_score}/{len(keywords)} tu khoa):")
        print(f"      ...{page_raw[best_page][:0]}{sq[lo:hi]}...")
    else:
        print("      khong dinh vi duoc — xem lai trang gold trong PDF")

