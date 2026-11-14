# Starter · Pipeline Day 06 — PostgreSQL + pgvector

Pipeline **đã hiện thực hoàn chỉnh** cho lab Data Ingestion Engineering: nạp Luật Doanh nghiệp 59/2020/QH14 (bản in Công báo), chunk theo 3 chiến lược, embedding local, lưu pgvector, chạy benchmark 22 câu và xuất báo cáo 5 tiêu chí.

## Cấu trúc

```text
starter/
├── docker-compose.yml     # PostgreSQL 16 + pgvector 0.8.7, cổng local 127.0.0.1:5433
├── init.sql               # bật extension vector khi tạo database mới
├── requirements.txt       # psycopg, pymupdf, sentence-transformers, pillow...
├── .env.example           # cấu hình mẫu; copy thành .env (không commit .env)
├── models/                # model local (git-ignored) — tải bằng scripts/download_model.py
│   ├── embeddinggemma-2/  #   google/embeddinggemma-2 (740M, 768 dims) — model chính
│   └── paraphrase-multilingual-MiniLM-L12-v2/  # preset dự phòng
├── scripts/
│   ├── check_setup.py         # kiểm tra kết nối DB + extension
│   ├── download_model.py      # tải embedding model về models/ (chạy 1 lần)
│   ├── check_embeddings.py    # smoke-test model local
│   ├── build_benchmark.py     # sinh benchmark/questions.jsonl từ corpus (evidence tự kiểm chứng)
│   ├── verify_evidence.py     # xác minh 22/22 evidence tồn tại đúng trang gold
│   ├── diagnose_misses.py     # phân tích câu miss (R = ranking, C = chunking)
│   └── build_criteria_report.py  # dựng results/criteria_report.md + scoring_material.txt
├── src/
│   ├── models.py          # DocumentPage / Chunk (giữ traceability nguồn/trang)
│   ├── ingestion.py       # đọc pages.jsonl, chuẩn hóa, bỏ header lặp Công báo
│   ├── chunking.py        # fixed_size / by_paragraph (+ by_article không dùng)
│   ├── embeddings.py      # MyEmbedder — embeddinggemma-2 local, L2-normalize
│   ├── store.py           # PgVectorStore — upsert không nhân đôi, cosine + filter jsonb
│   ├── evaluation.py      # Hit@1 / Evidence Hit@3, trace top-3 đầy đủ metadata
│   └── run.py             # pipeline entry point: corpus → chunk → embed → store → benchmark
└── results/               # summary.json, traces_*.jsonl, criteria_report.md, manual_labels.json
```

## 1. Cài đặt

Cần Docker Desktop, Python 3.11–3.14. Chạy từ thư mục `starter/`:

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1   (macOS/Linux: source .venv/bin/activate)
python -m pip install -r requirements.txt
# Windows PowerShell: Copy-Item .env.example .env   (macOS/Linux: cp .env.example .env)
docker compose -p day6_student_starter up -d --wait
python scripts/check_setup.py      # kỳ vọng: Setup OK
```

Docker dùng cổng `127.0.0.1:5433`, mật khẩu cố định **chỉ dùng local cho lab**; nếu cổng bận, sửa đồng thời port trong `docker-compose.yml` và `DATABASE_URL` trong `.env`. `init.sql` chỉ chạy khi volume mới được tạo.

## 2. Chuẩn bị dữ liệu và model

```bash
# từ gốc repo: trích xuất PDF Công báo → data/extracted/pages.jsonl + manifest.json
python data/prepare_data.py

# từ starter/: tải model embedding local (chạy 1 lần, cần mạng)
python scripts/download_model.py
```

**Quan trọng**: luôn chạy pipeline bằng Python của `.venv` (`python` sau khi activate, hoặc `.venv\Scripts\python.exe`). Python hệ thống thiếu Pillow sẽ lỗi khi load processor của EmbeddingGemma 2 (multimodal processor cần Pillow/torchvision kể cả khi chỉ dùng text).

## 3. Chạy pipeline và benchmark

```bash
# từ starter/, với .venv đã activate:
python -m src.run                 # nạp 3 chiến lược + chạy 22 câu, ~10 phút (CPU)
python scripts/verify_evidence.py # xác minh evidence 22/22
python scripts/build_criteria_report.py  # dựng báo cáo 5 tiêu chí
```

- Ba chiến lược: **A_fixed** (cửa sổ 1000 ký tự, overlap 150), **B_para** (gom đoạn ≤1200 ký tự), **C_para_flt** (chunk như B + filter SQL `section` khi câu hỏi có filter). Cùng corpus 166 trang nội dung, cùng model, cùng benchmark.
- Nạp lại an toàn: upsert theo `chunk_id`, chunk cũ của tài liệu đổi bị xóa — không nhân đôi.
- Chỉ chunk trang `page_type='noi_dung'` (≥800 ký tự); trang mục lục/trống/trang ngắn bị loại.

## 4. Kết quả

| File | Nội dung |
|---|---|
| `results/summary.json` | metrics Hit@1/EvHit@3 theo chiến lược × split + manifest chạy lại được |
| `results/traces_*.jsonl` | trace top-3 mỗi câu: chunk_id, document_id, text, score, metadata, flags |
| `results/criteria_report.md` | báo cáo 5 tiêu chí (tự động + nhãn chấm tay) |
| `results/manual_labels.json` | nhãn coherence/grounding kèm lý do từng ô |
| `results/scoring_material.txt` | chất liệu để chấm/kiểm tra chéo |

## Phiên bản đã dùng

Python 3.12 · sentence-transformers 6.3.0 · transformers 5.23.0 · torch 2.15.0+cpu · psycopg 3.3.8 · pymupdf 2.1 · PostgreSQL 16 + pgvector 0.8.7 (Docker) · model `google/embeddinggemma-2` (768 dims, local, 0 USD). Chi tiết trong `data/manifest.json` và báo cáo cá nhân.
