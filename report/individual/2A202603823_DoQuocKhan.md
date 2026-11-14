# Báo cáo cá nhân — Day 6

- Họ và tên: Đỗ Quốc Khánh
- MSSV: 2A202603823
- Lớp: L3B
- Ngày làm: 14/11/2026

## Dữ liệu và pipeline

- **Chủ đề, nguồn/quyền, số trang và quy tắc tính trang:** Luật Doanh nghiệp số 59/2020/QH14, bản in Công báo số 713+714 và 715+716 (ngày 24-7-2020), tải từ CDN chính thức `congbaocdn.chinhphu.vn` (trang văn bản: `congbao.chinhphu.vn/van-ban/luat-so-59-2020-qh14-31674.htm`). Quyền xử lý: văn bản quy phạm pháp luật không được bảo hộ quyền tác giả (Luật Sở hữu trí tuệ, Điều 13); chỉ dùng bản gốc Công báo, ghi rõ nguồn khi trích dẫn (chi tiết `data/manifest.json`). Số trang: **168 vật lý / 166 nội dung hợp lệ**. Quy tắc: trang hợp lệ = ≥ 800 ký tự text đã chuẩn hóa; loại trang trống (<200 ký tự) và trang mục lục. Hai file, mỗi file ghi SHA-256 và link nguồn.
- **Chuẩn hóa, lỗi và giới hạn:** extract bằng pymupdf 2.1 theo trang (UTF-8, NFC, gộp khoảng trắng), bỏ header lặp của Công báo và số trang in bằng regex xác định (không đụng dòng nội dung). Lỗi đã xử lý: pypdf sinh ~2.000 lỗi khoảng trắng dấu tiếng Việt trên cùng file ("ng ười", "r ể") trong khi pymupdf chỉ còn 2 vị trí — chọn pymupdf và ghi vào manifest. Giới hạn: 2 vị trí lỗi còn sót; PDF Công báo là bản "signed" scan (không extract được text) nên dùng bản in Công báo thường của CDN; section gán theo trang vật lý nên trang chuyển chương mang section của chương mở đầu trên trang đó.
- **Embedding / vector store / metric / lệnh chạy / chi phí:** `google/embeddinggemma-2` (740M, 768 dims, float32 CPU, local — sentence-transformers 6.3.0, transformers 5.23.0, torch 2.15.0+cpu), query dùng prompt `Retrieval-query`, document dùng `Retrieval-document` theo hướng dẫn Google; vector L2-normalized, metric cosine (`vector_cosine_ops`). Store: PostgreSQL 16.16 + pgvector 0.8.7 (Docker Compose, cổng 127.0.0.1:5433), bảng `chunks` có index HNSW. Lệnh chạy: `cd starter; docker compose -p day6_student_starter up -d --wait; python -m src.run`. Chi phí: **0 USD** (local, không gọi API).
- **Metadata bắt buộc + trường lọc:** bắt buộc `document_id`, `source`, `page`; bổ sung `section` (slug chương, ví dụ `chuong_v`) và `section_title`. Nguồn giá trị: heading "Chương [số La Mã]" trong văn bản — regex yêu cầu heading nằm riêng một dòng và dòng kế là CHỮ IN HOA để loại tham chiếu thân bài (lỗi thật đã bắt: trang 64 có "Mục 1 Chương III" từng làm tracker quay ngược). Lý do chọn: luật phân chia phạm vi theo chương, filter theo chương là truy vấn tự nhiên ("quy định về công ty cổ phần nằm ở đâu?").

## Cấu hình và benchmark

- **A / B / C:**
  - **A_fixed** — cửa sổ ký tự 1000, overlap 150; không filter. 456 chunks.
  - **B_para** — gom đoạn văn (tách theo dòng trống), giới hạn 1200 ký tự; không filter. 341 chunks.
  - **C_para_flt** — chunk giống B hệt; khi câu hỏi có filter thì lọc SQL `metadata @> {"section": ...}`. 341 chunks.
  - Khác biệt duy nhất B–C: áp dụng metadata filter. A–B: cách chia chunk. Corpus, model, store, benchmark giữ nguyên mọi cấu hình.
- **Benchmark:** 22 câu (17 dev / 5 test, chốt trước khi chạy), 4 câu có filter `section` (q10, q14, q17 dev; q20 test — đạt ≥3 câu filter, ≥1 câu test). Loại câu: truc_tiep, dien_dat_lai, dieu_kien. Evidence kiểm chứng nguyên văn bằng `scripts/verify_evidence.py`: 22/22 quote tồn tại đúng trang gold.
- **Tiêu chí chọn chiến lược chốt trước khi xem test:** ưu tiên Evidence Hit@3 (đủ bằng chứng), sau đó Hit@1, rồi filter compliance, cuối cùng tài nguyên (thời gian/chunk) — theo thứ tự ví dụ trong GUIDE.md §4.5.

## Kết quả

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian embed | Chi phí |
|---|---|---|---|---|---|---|
| A_fixed | dev | 6/17 (0.353) | 13/17 (0.765) | 456 | 166.9s | 0 USD |
| A_fixed | test | 3/5 (0.600) | 3/5 (0.600) | 456 | — | 0 USD |
| B_para | dev | 8/17 (0.471) | 13/17 (0.765) | 341 | 149.4s | 0 USD |
| B_para | test | 2/5 (0.400) | 3/5 (0.600) | 341 | — | 0 USD |
| C_para_flt | dev | 9/17 (0.529) | 13/17 (0.765) | 341 | 145.4s | 0 USD |
| C_para_flt | test | 2/5 (0.400) | 4/5 (0.800) | 341 | — | 0 USD |

| Strategy | Coherence TB /2 (n=10) | Metadata đủ và đúng (n/N) | Filter tuân thủ | Grounding 0/1/2 và TB /2 (n=5) |
|---|---|---|---|---|
| A_fixed | 0.90 (18/20) | 45/45 | 0.89 dev / 0.67 test | 0:1, 1:0, 2:4 → **0.80** |
| B_para | 1.00 (20/20) | 45/45 | 0.78 dev / 0.67 test | 0:2, 1:0, 2:3 → **0.60** |
| C_para_flt | 1.00 (20/20) | 45/45 | 1.00 dev / 1.00 test | 0:1, 1:0, 2:4 → **0.80** |

- Đường dẫn trace: `starter/results/traces_{A_fixed,B_para,C_para_flt}.jsonl` (đủ chunk ID, text, score, metadata, gold, flags dev+test). Nhãn thủ công: `starter/results/manual_labels.json`; chất liệu chấm: `starter/results/scoring_material.txt`. Cách chọn mẫu coherence: 10 trang gold đầu của dev sắp xếp theo page ID, bỏ trùng trang (q04 trùng trang 22 với q03) — chốt trước khi xem điểm. Grounding: toàn bộ 5 câu test.

## Phân tích và kết luận

- **A–B:** cùng metadata, khác chunking. Đoạn văn giữ trọn điều luật → Hit@1 dev 6/17 → 8/17; coherence 18/20 → 20/20 (cửa sổ cắt giữa câu Điều 26 k2 và Điều 37 k2 làm mất ý); grounding 8/10 → 6/10 (overlap của A bắt được hai đoạn bằng chứng ngoài dự đoán nhưng thiếu ngữ cảnh ở 2 câu khác — mẫu nhỏ, xem phần hạn chế).
- **B–C:** cùng chunk, khác filter. C tăng EvHit@3 test 3/5 → 4/5, Hit@1 dev 8/17 → 9/17, filter compliance 1.0 tuyệt đối (vs 0.78/0.67 tự nhiên của B). Ví dụ: **q20** (test, "Trường hợp nào một công ty được coi là công ty mẹ?") — B không lọc nên top-3 toàn Điều 195 k3-k6 về trách nhiệm; C lọc `chuong_viii` đưa Điều 195 k1 (định nghĩa "Sở hữu trên 50%...") vào rank-3.
- **2 ví dụ sai có ID câu và nguồn:**
  1. **q04** (dev, gold `ldn-2020-congbao-p1` tr.22): evidence "trong thời hạn 10 ngày kể từ ngày có thay đổi" nằm trong chunk `p1#p022#g00` nhưng không vào top-3 ở cả ba chiến lược — cụm boilerplate này lặp ở Điều 33 (trang 23); rank-2 là chunk trang 23 chứa đúng cụm từ nhưng khác trang gold → miss theo định nghĩa hit.
  2. **q20** (test, gold `ldn-2020-congbao-p2` tr.55): A và B không truy xuất được Điều 195 k1 (định nghĩa công ty mẹ) — top-3 chỉ có k3-k6; câu hỏi dùng từ "công ty mẹ" khớp phần trách nhiệm (k3-k6) mạnh hơn phần định nghĩa (k1).
- **Chiến lược chọn: C_para_flt.** EvHit@3 test cao nhất (4/5), Hit@1 dev cao nhất (9/17), filter compliance 1.0, coherence trọn điểm, tài nguyên bằng B. Đổi lại: filter chỉ có giá trị khi câu hỏi cung cấp phạm vi (input giả định cung cấp trước); với câu không filter, C tương đương B. Điều kiện áp dụng: corpus có metadata phân vùng đáng tin (chương của văn bản pháp luật).
- **Hạn chế:** (1) tập test 5 câu — chênh 1 câu là ±0.2, kết luận dựa chủ yếu vào dev; (2) người chấm thủ công trùng tác giả pipeline và nhãn soạn nháp với hỗ trợ AI rồi học viên rà soát — thiên lệch đã ghi trong `manual_labels.json`, khuyến nghị người độc lập kiểm tra chéo; (3) EvHit@3 dev ba chiến lược bằng nhau (13/17) do 4 câu miss chung là miss ranking (boilerplate pháp luật lặp giữa các điều), không phải lỗi chunking; (4) thời gian đo trên CPU cá nhân, chỉ so sánh tương đối; (5) corpus là bản Công báo 2020 chưa hợp nhất (Luật đã sửa đổi 2025) — câu hỏi và đáp án theo văn bản gốc này.
- **Nếu làm lại / mở rộng:** (1) hybrid BM25 + dense theo mục "Mở rộng tùy chọn" để xử lý boilerplate lặp; (2) thử chunk theo cấu trúc Điều (mỗi điều 1 chunk, metadata `dieu`) — corpus pháp luật có cấu trúc sẵn; (3) mời một người chấm độc lập kiểm tra chéo nhãn; (4) đo thêm trên thiết bị khác để con số thời gian ổn định.
