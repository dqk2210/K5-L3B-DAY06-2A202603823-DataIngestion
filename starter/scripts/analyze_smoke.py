# -*- coding: utf-8 -*-
"""Phân tích trace smoke: tại sao hit/miss."""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
results = Path(__file__).resolve().parents[1] / "results"

for name in ["traces_A_fixed.jsonl", "traces_B_para.jsonl", "traces_C_para_flt.jsonl"]:
    print(f"===== {name} =====")
    for line in (results / name).open(encoding="utf-8"):
        t = json.loads(line)
        status = "HIT@1" if t["hit_at_1"] else ("evHIT@3" if t["evidence_hit_at_3"] else "MISS")
        print(f"  {t['question_id']} [{t['strategy']}/{t['split']}] {status}")
        for h in t["hits_trace"]:
            cid = h["chunk_id"][:34]
            print(f"    rank{h['rank']} {cid:36s} score={h['score']:.3f} page={h['page']} "
                  f"hit={h['hit']} ev={h['evidence_found']}")
    print()
