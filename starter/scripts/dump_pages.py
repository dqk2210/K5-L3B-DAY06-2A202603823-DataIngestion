# -*- coding: utf-8 -*-
"""Dump normalized text of specific file-1 pages for evidence selection."""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
REPO = Path(__file__).resolve().parents[2]
PAGES = REPO / "data" / "extracted" / "pages.jsonl"

want = {int(x) for x in sys.argv[1:]}
pages = [json.loads(l) for l in PAGES.open(encoding="utf-8")]
for p in pages:
    if p["document_id"].endswith("p1") and p["page"] in want:
        print(f"================ TRANG {p['page']} ================")
        print(p["text"])
        print()
