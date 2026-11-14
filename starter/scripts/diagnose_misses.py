# -*- coding: utf-8 -*-
"""Chan doan 4 cau EvHit@3 fail: quote bi cat qua ranh gioi chunk hay khong rank top-3?"""
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "starter"))

from src.ingestion import load_pages_jsonl  # noqa: E402
from src.chunking import by_paragraph  # noqa: E402

_PUNCT = re.compile(r"[\"'“”‘’«»„‟\u00ad\u200b\u200c\u200d\ufeff]")


def squash(text: str) -> str:
    text = unicodedata.normalize("NFC", text).casefold()
    text = _PUNCT.sub("", text)
    return re.sub(r"\s+", "", text)


with (REPO / "benchmark" / "questions.jsonl").open(encoding="utf-8") as _f:
    questions = {q["id"]: q for q in (json.loads(line) for line in _f if line.strip())}
pages = load_pages_jsonl(REPO / "data" / "extracted" / "pages.jsonl")
chunks = [c for p in pages for c in by_paragraph(p, 1200)]

for qid in ["q04", "q05", "q11", "q17"]:
    q = questions[qid]
    ev = q["evidence_quote"]
    ev = ev[0] if isinstance(ev, list) else ev
    needle = squash(ev)
    # chunk nào chứa quote nguyên vẹn?
    holders = [c.chunk_id for c in chunks if needle in squash(c.text)]
    gold_doc, gold_page = q["gold_source_id"], q["gold_page"]
    on_gold_page = [h for h in holders if f"{gold_doc}#p{gold_page:03d}" in h]
    # rank trong trace C?
    trace = next(json.loads(l) for l in (REPO / "starter" / "results" / "traces_C_para_flt.jsonl").open(encoding="utf-8")
                 if json.loads(l)["question_id"] == qid)
    ranked_ids = [h["chunk_id"].split("#", 1)[1] for h in trace["hits_trace"]]
    holder_rank = next((i + 1 for i, rid in enumerate(ranked_ids) if rid in holders), None)
    print(f"{qid}: quote trong chunk: {holders or 'KHONG chunk nao giu tron quote (bi cat ranh gioi)'}")
    print(f"   chunk nam tren trang gold: {on_gold_page or '-'} | rank trong top-3 (C): {holder_rank or 'ngoai top-3'}")
    print(f"   question: {q['question'][:60]}")
    print()
