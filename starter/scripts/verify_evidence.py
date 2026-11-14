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
# key theo (document_id, page): hai file Cong Bao co so trang trung nhau
page_squash = {(p["document_id"], p["page"]): squash(p["text"]) for p in pages}

questions = [json.loads(l) for l in QUESTIONS.open(encoding="utf-8") if l.strip()]
for q in questions:
    ev = q.get("evidence_quote", "")
    if isinstance(ev, list):
        ev = ev[0] if ev else ""
    needle = squash(ev)
    if not needle:
        continue
    gold_doc = q.get("gold_source_id")
    same_doc = [(doc, pg) for (doc, pg), sq in page_squash.items() if needle and needle in sq and doc == gold_doc]
    other_doc = [(doc, pg) for (doc, pg), sq in page_squash.items() if needle and needle in sq and doc != gold_doc]
    gold = q.get("gold_page")
    on_gold = any(pg == gold for _, pg in same_doc)
    status = "OK" if on_gold else ("SAI TRANG gold (quote dung, trang khac)" if same_doc else (
        "quote chi co o file khac" if other_doc else "KHONG TIM THAY quote nguyen van"))
    if status == "OK":
        print(f"{q['id']:5s} [OK] {gold_doc} trang {gold}")
        continue
    print(f"{q['id']:5s} [{status}] gold={gold_doc} trang {gold} | tim thay: {same_doc or other_doc}")
    print(f"      evidence: {ev[:80]}")

