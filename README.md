# Day 06 · Data Ingestion Engineering — Pipeline RAG cho Luật Doanh nghiệp 2020

**Lab cá nhân · Lớp L3B · MSSV 2A202603823 — Đỗ Quốc Khánh**

Biến 168 trang Công báo Luật Doanh nghiệp 59/2020/QH14 thành kho tri thức truy xuất được: trích xuất theo trang, chunk theo 3 chiến lược, embedding local (EmbeddingGemma 2), lưu PostgreSQL + pgvector, benchmark 22 câu hỏi và đánh giá theo 5 tiêu chí.

## Tóm tắt kết quả

| Chiến lược | Hit@1 dev | EvHit@3 dev | EvHit@3 test | Filter compliance | Coherence /2 | Grounding /2 |
|---|---|---|---|---|---|---|
| A_fixed (cửa sổ 1000 ký tự) | 6/17 | 13/17 | 3/5 | 2/3 câu (8/9 chunk) dev | 1.80 | 1.60 |
| B_para (theo đoạn) | 8/17 | 13/17 | 3/5 | 2/3 câu (7/9 chunk) dev | 2.00 | 1.20 |
| **C_para_flt (B + filter section)** | **9/17** | **13/17** | **4/5** | **3/3 câu (9/9 chunk)** | **2.00** | **1.60** |

**Chọn C_para_flt** (chốt tiêu chí trước khi xem test: EvHit@3 → Hit@1 → filter compliance → tài nguyên). Chi tiết: [`report/individual/2A202603823_DoQuocKhanh.md`](report/individual/2A202603823_DoQuocKhanh.md) và [`starter/results/criteria_report.md`](starter/results/criteria_report.md).

## Chạy nhanh

```bash
# 1. Cơ sở dữ liệu (cần Docker)
cd starter
python -m venv .venv && .venv\Scripts\Activate.ps1    # Windows; macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
Copy-Item .env.example .env
docker compose -p day6_student_starter up -d --wait
python scripts/check_setup.py                         # Setup OK

# 2. Dữ liệu + model (chạy 1 lần)
cd .. && python data/prepare_data.py                  # → data/extracted/pages.jsonl + manifest
cd starter && python scripts/download_model.py        # → models/embeddinggemma-2 (local)

# 3. Pipeline + benchmark + báo cáo (luôn dùng .venv)
python -m src.run                                     # ~10 phút CPU
python scripts/verify_evidence.py                     # 22/22 evidence OK
python scripts/build_criteria_report.py               # → results/criteria_report.md
```

Lưu ý: chạy pipeline bằng Python của `.venv` — hệ thống thiếu Pillow sẽ lỗi load processor EmbeddingGemma 2. Chi tiết từng bước: [`starter/README.md`](starter/README.md).

## Cấu trúc repo

```text
data/               # PDF gốc Công báo + prepare_data.py + extracted/pages.jsonl + manifest.json
benchmark/          # questions.jsonl — 22 câu (17 dev / 5 test, 4 câu filter)
starter/src/        # pipeline: ingestion → chunking → embeddings → store → evaluation → run
starter/results/    # summary.json, traces, criteria_report.md, manual_labels.json
report/individual/  # báo cáo cá nhân theo mẫu
artifacts/          # experiment_log.csv
```

## Tài liệu đề bài

| Bạn cần tìm | Tài liệu |
|---|---|
| Setup và cách chạy chi tiết | [starter/README.md](starter/README.md) |
| Các bước làm và cách tính chỉ số | [GUIDE.md](GUIDE.md) |
| Năm tiêu chí benchmark và bộ câu hỏi | [BENCHMARK.md](BENCHMARK.md) |
| Tiêu chí chấm điểm | [RUBRIC.md](RUBRIC.md) |
| Quy tắc sử dụng dữ liệu, AI và API | [RULES.md](RULES.md) |
| Cách nộp bài | [SUBMISSION.md](SUBMISSION.md) |
