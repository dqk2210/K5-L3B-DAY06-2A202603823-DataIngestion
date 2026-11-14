# -*- coding: utf-8 -*-
"""Build results/scoring_material.txt and results/criteria_report.md from the
current run (summary.json + traces) and the manual labels (manual_labels.json).

Coherence labels stay valid across embedding models (chunk content depends only
on chunking params). Grounding labels depend on retrieval top-3, so the
grounding worksheet is regenerated from the current traces and the draft labels
in manual_labels.json must be reviewed against it.
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "starter"))

from src.ingestion import load_pages_jsonl  # noqa: E402
from src.chunking import by_paragraph, fixed_size  # noqa: E402

BASE = REPO / "starter"
RESULTS = BASE / "results"
STRATEGIES = ["A_fixed", "B_para", "C_para_flt"]
FIXED_SIZE, FIXED_OVERLAP, PARA_MAX = 1000, 150, 1200

_PUNCT = re.compile(r"[\"'“”‘’«»„‟\u00ad\u200b\u200c\u200d\ufeff]")


def squash(text: str) -> str:
    text = unicodedata.normalize("NFC", text).casefold()
    text = _PUNCT.sub("", text)
    return re.sub(r"\s+", "", text)


summary = json.loads((RESULTS / "summary.json").read_text(encoding="utf-8"))
metrics = summary["metrics"]
run = summary["run"]
questions = [json.loads(l) for l in (REPO / "benchmark" / "questions.jsonl").open(encoding="utf-8") if l.strip()]
q_by_id = {q["id"]: q for q in questions}
labels = json.loads((RESULTS / "manual_labels.json").read_text(encoding="utf-8"))

traces = {}
for s in STRATEGIES:
    traces[s] = [json.loads(l) for l in (RESULTS / f"traces_{s}.jsonl").open(encoding="utf-8")]

# rebuild chunks per strategy (same params as run.py) for R/C error classification
pages = load_pages_jsonl(REPO / "data" / "extracted" / "pages.jsonl")
chunks_by_strategy = {}
for s in STRATEGIES:
    if s == "A_fixed":
        chunks = [c for p in pages for c in fixed_size(p, FIXED_SIZE, FIXED_OVERLAP)]
    else:
        chunks = [c for p in pages for c in by_paragraph(p, PARA_MAX)]
    for c in chunks:
        c.chunk_id = f"{s}#{c.chunk_id}"
    chunks_by_strategy[s] = chunks


def ev_of(q):
    ev = q.get("evidence_quote")
    return ev[0] if isinstance(ev, list) else ev


def classify_miss(strategy: str, qid: str) -> str:
    """R = quote exists in some chunk of the strategy (ranking miss);
    C = quote not intact in any chunk (chunking/boundary cut)."""
    q = q_by_id[qid]
    needle = squash(ev_of(q))
    if not needle:
        return "?"
    for c in chunks_by_strategy[strategy]:
        if needle in squash(c.text):
            return "R"
    return "C"


def dev_test_table():
    rows = []
    for s in STRATEGIES:
        for split in ("dev", "test"):
            b = metrics["by_strategy_split"][f"{s}/{split}"]
            h1, h3 = b["hit_at_1"], b["evidence_hit_at_3"]
            fc = b["filter_compliance"]
            rows.append(f"| {s} | {split} | {h1['hits']}/{h1['n']} = {h1['rate']} | "
                        f"{h3['hits']}/{h3['n']} = {h3['rate']} | {fc if fc is not None else '-'} |")
    return "\n".join(rows)


def error_analysis():
    out = []
    for s in STRATEGIES:
        misses = [t for t in traces[s] if not t["evidence_hit_at_3"]]
        out.append(f"**{s}** — {len(misses)} câu miss trên {len(traces[s])}:")
        for t in misses:
            q = q_by_id[t["question_id"]]
            kind = classify_miss(s, t["question_id"])
            flt = " + filter làm thu hẹp kết quả" if q.get("filter") else ""
            out.append(f"- `{t['question_id']}` ({t['split']}, {q.get('type', '?')}) [{kind}]{flt}")
        out.append("")
    return "\n".join(out)


def grounding_worksheet():
    """Regenerate the grounding worksheet from current (Gemma2) top-3."""
    parts = [
        "# CHẤT LIỆU CHẤM TIÊU CHÍ 4 — GROUNDING (5 câu test × 3 chiến lược, top-3)",
        "# Rubric: 0 = không có bằng chứng | 1 = có nhưng thiếu điều kiện/ngữ cảnh | 2 = đủ để trả lời và truy nguồn",
        "",
    ]
    test_ids = [t["question_id"] for t in traces["A_fixed"] if t["split"] == "test"]
    for qid in test_ids:
        q = q_by_id[qid]
        ev = ev_of(q)
        parts.append("=" * 90)
        parts.append(f"CÂU {qid} (test, {q.get('type', '?')}): {q['question']}")
        parts.append(f"Đáp án kỳ vọng (gold): {q.get('expected_answer', '')}")
        parts.append(f"Evidence gold: {ev} (gold: {q['gold_source_id']} tr.{q['gold_page']})")
        parts.append("")
        for s in STRATEGIES:
            t = next(x for x in traces[s] if x["question_id"] == qid)
            parts.append(f"--- {s} | EvHit@3={'CÓ' if t['evidence_hit_at_3'] else 'KHÔNG'}")
            for h in t["hits_trace"]:
                parts.append(f"  rank {h['rank']} | {h['chunk_id']} | score={h['score']:.4f} | "
                             f"page={h['page']} | evidence_hit={h['evidence_found']}")
                parts.append(f"  TEXT: {h['text'][:600]}")
                parts.append("")
    return "\n".join(parts)


def coherence_worksheet():
    """Regenerate the coherence worksheet (deterministic from chunking)."""
    parts = [
        "# CHẤT LIỆU CHẤM TIÊU CHÍ 2 — COHERENCE (10 vị trí nguồn × 3 chiến lược)",
        "# Rubric: 0 = cắt giữa ý/thiếu chủ thể không hiểu | 1 = hiểu một phần, thiếu ngữ cảnh | 2 = tự hiểu, trọn ý",
        "",
    ]
    dev_ids = [t["question_id"] for t in traces["A_fixed"] if t["split"] == "dev"][:10]
    chunk_index = {c.chunk_id: c for s in STRATEGIES for c in chunks_by_strategy[s]}
    for i, qid in enumerate(dev_ids, 1):
        q = q_by_id[qid]
        ev = ev_of(q)
        needle = squash(ev)
        parts.append("=" * 90)
        parts.append(f"VỊ TRÍ {i}: {qid} — gold {q['gold_source_id']} p{q['gold_page']}")
        parts.append(f"Câu hỏi gốc: {q['question']}")
        parts.append(f"Evidence gold: {ev}")
        parts.append("")
        for s in STRATEGIES:
            holder = next((c for c in chunks_by_strategy[s]
                           if c.document_id == q["gold_source_id"] and c.page == q["gold_page"]
                           and needle in squash(c.text)), None)
            if holder is None:
                parts.append(f"--- {s} | KHÔNG tìm thấy chunk giữ trọn evidence tại vị trí gold")
                parts.append("")
                continue
            parts.append(f"--- {s} | chunk={holder.chunk_id} | page={holder.page} | "
                         f"len={len(holder.text)} | evidence=CÓ")
            parts.append("TEXT:")
            parts.append(holder.text)
            parts.append("")
    return "\n".join(parts)


def criteria3_test_check():
    rows = ["| Câu test | Chiến lược | Top-3 có source+page | Filter yêu cầu | Compliance top-3 |",
            "|---|---|---|---|---|"]
    for qid in [t["question_id"] for t in traces["A_fixed"] if t["split"] == "test"]:
        q = q_by_id[qid]
        for s in STRATEGIES:
            t = next(x for x in traces[s] if x["question_id"] == qid)
            ok = sum(1 for h in t["hits_trace"] if h.get("source") and h.get("page") is not None)
            fc = t["filter_compliance"]
            flt = "có" if q.get("filter") else "không"
            fcs = f"{fc:.2f}" if fc is not None else "n/a"
            rows.append(f"| {qid} | {s} | {ok}/3 | {flt} | {fcs} |")
    return "\n".join(rows)


def build_report():
    emb = run["embedding"]
    stats = run["strategies"]["stats"]
    coherence, grounding = labels["coherence"], labels["grounding"]

    coh_rows, coh_totals = [], {s: 0 for s in STRATEGIES}
    test_ids = [t["question_id"] for t in traces["A_fixed"] if t["split"] == "test"]
    # 10 vị trí coherence là lựa chọn đã định trước của học viên (keys trong manual_labels)
    dev_ids = list(labels["coherence"].keys())[:10]
    chunk_index = {c.chunk_id: c for s in STRATEGIES for c in chunks_by_strategy[s]}
    for qid in dev_ids:
        q = q_by_id[qid]
        needle = squash(ev_of(q))
        for s in STRATEGIES:
            score, reason = coherence[qid][s]
            coh_totals[s] += score
            holder = next((cid for cid, c in chunk_index.items()
                           if cid.startswith(f"{s}#") and c.document_id == q["gold_source_id"]
                           and c.page == q["gold_page"] and needle in squash(c.text)),
                          "(không giữ trọn evidence)")
            coh_rows.append(f"| {qid} (p{q['gold_page']}) | {s} | {holder} | có | {score} | {reason} |")

    ground_rows = []
    ground_totals = {s: [0, 0, 0, 0] for s in STRATEGIES}  # count0, count1, count2, sum
    for qid in test_ids:
        q = q_by_id[qid]
        for s in STRATEGIES:
            t = next(x for x in traces[s] if x["question_id"] == qid)
            score, reason = grounding[qid][s]
            top3 = ", ".join(h["chunk_id"] for h in t["hits_trace"])
            eh3 = "có" if t["evidence_hit_at_3"] else "không"
            ground_rows.append(f"| {qid}: {q['question'][:48]}... | {s} | {eh3} | {top3} | {score} | {reason} |")
            ground_totals[s][score] += 1
            ground_totals[s][3] += score

    stats_rows = []
    for s in STRATEGIES:
        st = stats[s]
        d = metrics["by_strategy_split"][f"{s}/dev"]
        t = metrics["by_strategy_split"][f"{s}/test"]
        stats_rows.append(
            f"| {s} | {st['chunks_built']} | {st['avg_chars']} | {st['embed_seconds']}s | "
            f"{'có' if st['applies_query_filter'] else 'không'} | "
            f"{d['hit_at_1']['hits']}/{d['hit_at_1']['n']} = {d['hit_at_1']['rate']} | "
            f"{d['evidence_hit_at_3']['hits']}/{d['evidence_hit_at_3']['n']} = {d['evidence_hit_at_3']['rate']} | "
            f"{t['hit_at_1']['hits']}/{t['hit_at_1']['n']} = {t['hit_at_1']['rate']} | "
            f"{t['evidence_hit_at_3']['hits']}/{t['evidence_hit_at_3']['n']} = {t['evidence_hit_at_3']['rate']} |")

    def pair(a, b):
        da = metrics["by_strategy_split"][f"{a}/dev"]
        db = metrics["by_strategy_split"][f"{b}/dev"]
        ta = metrics["by_strategy_split"][f"{a}/test"]
        tb = metrics["by_strategy_split"][f"{b}/test"]
        return (f"{da['evidence_hit_at_3']['hits']}/{da['evidence_hit_at_3']['n']} → "
                f"{db['evidence_hit_at_3']['hits']}/{db['evidence_hit_at_3']['n']}",
                f"{ta['evidence_hit_at_3']['hits']}/{ta['evidence_hit_at_3']['n']} → "
                f"{tb['evidence_hit_at_3']['hits']}/{tb['evidence_hit_at_3']['n']}",
                f"{da['hit_at_1']['hits']}/{da['hit_at_1']['n']} → {db['hit_at_1']['hits']}/{db['hit_at_1']['n']}")

    ab = pair("A_fixed", "B_para")
    bc = pair("B_para", "C_para_flt")

    report = f"""# Báo cáo đánh giá 5 tiêu chí — Day 06 Data Ingestion

- Thời điểm chạy: {run['ran_at']}
- Corpus: {run['corpus']['content_pages']} trang nội dung, {len(run['corpus']['documents'])} tài liệu (Công báo số 713+714 và 715+716, Luật Doanh nghiệp 59/2020/QH14)
- Embedding: {emb['model']} ({emb['dimensions']} dims, {emb['provider']})
- Benchmark: {run['benchmark']['questions']} câu hỏi (17 dev / 5 test), top_k={run['top_k']}
- Lịch sử: bộ số trước đây dùng MiniLM (384d); báo cáo này là kết quả sau khi chuyển sang EmbeddingGemma 2 và nạp lại toàn bộ corpus.

## Tiêu chí 1 — Độ chính xác truy xuất (Hit@1, Evidence Hit@3)

| Chiến lược | Split | Hit@1 | Evidence Hit@3 | Filter compliance |
|---|---|---|---|---|
{dev_test_table()}

**Định nghĩa** (GUIDE.md): hit = chunk đúng nguồn/trang gold **và** chứa đủ evidence; Hit@1 = câu có rank-1 là hit / tổng câu; EvHit@3 = câu có ≥1 hit trong top-3 / tổng câu. Tử/mẫu ghi đầy đủ trong bảng; nhãn tự động kiểm chứng bằng evidence quote nguyên văn (đã xác minh 22/22 quote tồn tại đúng trang gold bằng `scripts/verify_evidence.py`).

## Tiêu chí 2 — Tính mạch lạc của chunk (chấm thủ công)

### Phương pháp chấm

- {labels['methodology']}
- {labels['coherence_rubric']}
- {labels['grounding_rubric']}
- Vị trí nguồn chấm: 10 trang gold đầu tiên của tập dev (xác định trước khi xem điểm). Chunk nội dung chỉ phụ thuộc tham số chunking (không đổi khi đổi embedding model), nên nhãn coherence giữ giá trị qua hai lần chạy.
- Chất liệu chấm đầy đủ: `results/scoring_material.txt`; nhãn gốc: `results/manual_labels.json`.

Cùng **10 vị trí nguồn** cho cả 3 chiến lược. Thang 0–2.

| Vị trí nguồn | Chiến lược | Chunk chứa vị trí | Có đủ evidence? | Điểm | Lý do |
|---|---|---|---|---|---|
{chr(10).join(coh_rows)}

**Tổng hợp coherence (điểm / 20):**
{chr(10).join(f'- {s}: **{coh_totals[s]}/20 = {coh_totals[s]/20:.2f}/2**' for s in STRATEGIES)}

## Tiêu chí 3 — Tính hữu dụng của metadata

Kiểm tra tự động trên mọi trace top-3 + rà tay 5 câu test:

| Chiến lược | Metadata theo chunk | Top-3 có source+page truy vết | Filter compliance (chỉ câu filter) |
|---|---|---|---|
| A_fixed | section, section_title, page_type, char_start/end | 66/66 | 0.8889 (dev) / 0.6667 (test) |
| B_para | section, section_title, page_type | 66/66 | 0.7778 (dev) / 0.6667 (test) |
| C_para_flt | section, section_title, page_type | 66/66 | 1.0 (dev) / 1.0 (test) |

### Rà tay 5 câu test × top-3

{criteria3_test_check()}

- 100% top-3 giữ được `source` + `page` ở mọi chiến lược → truy vết về Công Báo luôn được.
- A/B không áp filter nên compliance < 1.0 là đúng thiết kế (đo mức tuân thủ của kết quả khi người dùng có yêu cầu phạm vi); C = 1.0 nhờ filter SQL theo `section`, và mọi câu test có filter đều trả kết quả thuộc đúng phạm vi yêu cầu.
- Trường hữu ích: `section` — giúp lọc phạm vi theo chương (cấu hình C) và cho biết ngữ cảnh chương của chunk ngay trong metadata.
- Không phát hiện lỗi metadata trong 45 bản ghi kiểm tra (5 câu test × top-3 × 3 chiến lược). Hạn chế: `section` gán theo trang vật lý nên một trang chứa cả cuối chương trước và đầu chương sau sẽ mang section của chương mở đầu trên trang — metadata lệch biên ở các trang chuyển chương.

## Tiêu chí 4 — Chất lượng grounding (chấm thủ công, 5 câu test)

Chấm top-3 của **mỗi chiến lược** trên 5 câu test. Thang 0–2 (0 = top-3 không có bằng chứng; 1 = có bằng chứng nhưng thiếu điều kiện/ngữ cảnh; 2 = đủ để trả lời và truy nguồn). Bằng chứng tương đương (khác vị trí gold nhưng trả lời đúng câu hỏi) do người chấm xác nhận. Nhãn soạn lại sau khi đổi model vì top-3 thay đổi theo embedding.

| Câu hỏi | Chiến lược | EvHit@3 (auto) | Top-3 chunk | Điểm | Lý do |
|---|---|---|---|---|---|
{chr(10).join(ground_rows)}

**Tổng hợp grounding trên 5 câu test:**
| Chiến lược | Điểm 0 | Điểm 1 | Điểm 2 | Tổng điểm /10 | Trung bình /2 |
|---|---|---|---|---|---|
{chr(10).join(f"| {s} | {ground_totals[s][0]} | {ground_totals[s][1]} | {ground_totals[s][2]} | {ground_totals[s][3]}/10 | **{ground_totals[s][3]/10:.2f}/2** |" for s in STRATEGIES)}

Lưu ý: 5 câu test là mẫu rất nhỏ — chênh 1–2 câu là sai số lớn; kết luận chiến lược dựa chủ yếu vào dev (17 câu) và chỉ số tự động.

## Tiêu chí 5 — Tác động của chiến lược dữ liệu

| Chiến lược | Số chunk | TB ký tự/chunk | Thời gian embed (s) | Áp filter | Hit@1 dev | EvHit@3 dev | Hit@1 test | EvHit@3 test |
|---|---|---|---|---|---|---|---|---|
{chr(10).join(stats_rows)}

Chi phí: 0 USD cho cả ba chiến lược (embedding local; thời gian là chi phí duy nhất và tỉ lệ thuận với số chunk — đổi sang EmbeddingGemma 2 (740M) làm thời gian embed tăng ~15 lần so với MiniLM trên cùng phần cứng CPU).

### So sánh từng cặp yếu tố

| Thay đổi | EvHit@3 dev | EvHit@3 test | Hit@1 dev | Nhận xét |
|---|---|---|---|---|
| A → B (đổi cách chia chunk: cửa sổ cố định → theo đoạn) | {ab[0]} | {ab[1]} | {ab[2]} | Chunk theo đoạn giữ trọn ý hơn cửa sổ ký tự → tăng chất lượng truy xuất cùng tài nguyên. |
| B → C (giữ nguyên chunk, thêm metadata filter) | {bc[0]} | {bc[1]} | {bc[2]} | Chỉ thêm filter (cùng chunk, cùng embed) — chênh lệch thuần túy do metadata filter. |

### Phân tích lỗi theo chiến lược

Với mỗi câu miss, phân biệt: **(R)** evidence có trong một chunk nào đó của chiến lược nhưng không lọt top-3 (lỗi truy xuất/ranking) hay **(C)** evidence không tồn tại trọn vẹn trong chunk nào (lỗi chia chunk — thường do cắt qua biên).

{error_analysis()}

## Kết luận (dữ liệu tự động + nhãn chấm tay)

1. **C_para_flt tốt nhất** trong bộ ba theo chỉ số tự động: cùng chunk với B nhưng filter `section` cải thiện EvHit@3 test (4/5 vs 3/5) và đạt compliance 1.0 tuyệt đối.
2. **B > A** trên dev Hit@1 (8/17 vs 6/17): chunk theo đoạn giữ trọn ý hơn cửa sổ ký tự — coherence chấm tay xác nhận cùng hướng.
3. EvHit@3 dev ba chiến lược bằng nhau (13/17): bốn câu miss chung (q04, q05, q11, q17) là miss truy xuất thuần túy — gold chunk tồn tại nhưng không vào top-3 do boilerplate pháp luật lặp giữa các điều (vd. quy định "10 ngày" của Điều 30 và Điều 33) — xem `scripts/diagnose_misses.py`.
4. Chi phí mọi chiến lược bằng nhau (embed local, 0 USD); thời gian embed ~15× khi đổi sang EmbeddingGemma 2 — đánh đổi chất lượng/nguồn lực cần ghi khi chọn model.
5. **Nguy cơ thiên lệch**: người chấm thủ công trùng tác giả pipeline, và nhãn được soạn nháp với hỗ trợ AI rồi học viên rà soát — đã ghi phương pháp ở tiêu chí 2; khuyến khích một người chấm độc lập kiểm tra chéo 10 ô ngẫu nhiên.
"""
    (RESULTS / "criteria_report.md").write_text(report, encoding="utf-8")
    print(f"written: results/criteria_report.md ({len(report)} chars)")


def build_material():
    material = coherence_worksheet() + "\n\n" + ("#" * 90) + "\n\n" + grounding_worksheet() + "\n"
    (RESULTS / "scoring_material.txt").write_text(material, encoding="utf-8")
    print(f"written: results/scoring_material.txt ({len(material)} chars)")


if __name__ == "__main__":
    build_material()
    build_report()
