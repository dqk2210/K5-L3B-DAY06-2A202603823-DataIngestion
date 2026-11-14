# Báo cáo đánh giá 5 tiêu chí — Day 06 Data Ingestion

- Thời điểm chạy: 2026-11-14T05:26:42+00:00
- Corpus: 167 trang nội dung, 2 tài liệu (Công báo số 713+714 và 715+716, Luật Doanh nghiệp 59/2020/QH14)
- Embedding: google/embeddinggemma-2 (768 dims, local (sentence-transformers), cost 0 USD)
- Benchmark: 22 câu hỏi (17 dev / 5 test), top_k=3
- Lịch sử: bộ số trước đây dùng MiniLM (384d); báo cáo này là kết quả sau khi chuyển sang EmbeddingGemma 2 và nạp lại toàn bộ corpus.

## Tiêu chí 1 — Độ chính xác truy xuất (Hit@1, Evidence Hit@3)

| Chiến lược | Split | Hit@1 | Evidence Hit@3 | Filter compliance |
|---|---|---|---|---|
| A_fixed | dev | 6/17 = 0.3529 | 13/17 = 0.7647 | 0.8889 |
| A_fixed | test | 3/5 = 0.6 | 3/5 = 0.6 | 0.6667 |
| B_para | dev | 8/17 = 0.4706 | 13/17 = 0.7647 | 0.7778 |
| B_para | test | 2/5 = 0.4 | 3/5 = 0.6 | 0.6667 |
| C_para_flt | dev | 9/17 = 0.5294 | 13/17 = 0.7647 | 1.0 |
| C_para_flt | test | 2/5 = 0.4 | 4/5 = 0.8 | 1.0 |

**Định nghĩa** (GUIDE.md): hit = chunk đúng nguồn/trang gold **và** chứa đủ evidence; Hit@1 = câu có rank-1 là hit / tổng câu; EvHit@3 = câu có ≥1 hit trong top-3 / tổng câu. Tử/mẫu ghi đầy đủ trong bảng; nhãn tự động kiểm chứng bằng evidence quote nguyên văn (đã xác minh 22/22 quote tồn tại đúng trang gold bằng `scripts/verify_evidence.py`).

## Tiêu chí 2 — Tính mạch lạc của chunk (chấm thủ công)

### Phương pháp chấm

- Thực hiện theo GUIDE.md §4 (dòng 44-49). (1) Coherence: 10 vị trí nguồn chốt trước khi xem điểm — 10 trang gold đầu tiên của tập dev sắp xếp theo page ID, bỏ vị trí trùng trang (q04 trùng trang 22 với q03): q01, q02, q03, q05, q06, q07, q08, q09, q10, q11; chấm chunk chứa evidence gold theo rubric 0-2, công bố mẫu, nhãn, lý do và điểm trung bình /2. (2) Grounding: chấm top-3 của 5 câu test theo rubric 0-2, báo đủ số lượng từng mức và trung bình /2 kèm lý do. (3) Người chấm là tác giả pipeline — nguy cơ thiên lệch được ghi nhận. (4) Nhãn được soạn nháp với hỗ trợ AI (GLM qua OpenCode) đọc trực tiếp chunk trong results/scoring_material.txt, học viên rà soát và chịu trách nhiệm cuối — GUIDE cho phép dùng LLM hỗ trợ với điều kiện ghi rõ phương pháp (mục này) và có xem xét nhãn; mọi nhãn kèm lý do đọc được. (5) Coherence chấm độc lập với điểm truy xuất (chunk chỉ phụ thuộc tham số chunking); grounding bắt buộc đọc top-3 nên không mù điểm hoàn toàn — chỉ dùng flags từng chunk, không dựa vào số tổng hợp.
- 0 = bị cắt giữa ý/thiếu chủ thể làm không hiểu; 1 = hiểu một phần, thiếu ngữ cảnh; 2 = tự hiểu được và giữ trọn ý
- 0 = không có bằng chứng; 1 = có nhưng thiếu điều kiện/ngữ cảnh cần thiết; 2 = đủ để trả lời và truy nguồn
- Vị trí nguồn chấm: 10 trang gold đầu tiên của tập dev (xác định trước khi xem điểm). Chunk nội dung chỉ phụ thuộc tham số chunking (không đổi khi đổi embedding model), nên nhãn coherence giữ giá trị qua hai lần chạy.
- Chất liệu chấm đầy đủ: `results/scoring_material.txt`; nhãn gốc: `results/manual_labels.json`.

Cùng **10 vị trí nguồn** cho cả 3 chiến lược. Thang 0–2.

| Vị trí nguồn | Chiến lược | Chunk chứa vị trí | Có đủ evidence? | Điểm | Lý do |
|---|---|---|---|---|---|
| q01 (p20) | A_fixed | A_fixed#ldn-2020-congbao-p1#p020#f00 | có | 1 | Điều 26 k1+a,b,c trọn nhưng k2 bị cắt giữa câu ('Cổng thông tin quốc gia v') — mất ý nơi nộp hồ sơ qua mạng |
| q01 (p20) | B_para | B_para#ldn-2020-congbao-p1#p020#g00 | có | 2 | Điều 26 k1 trọn, k2 đủ ý; chỉ câu kế tiếp lửng ở đuôi chunk |
| q01 (p20) | C_para_flt | C_para_flt#ldn-2020-congbao-p1#p020#g00 | có | 2 | Như B_para (cùng chunk g00) |
| q02 (p21) | A_fixed | A_fixed#ldn-2020-congbao-p1#p021#f00 | có | 2 | Điều 27 k1 (a-d) + k2 trọn vẹn; đầu chunk lửng giữa câu Điều 26 nhưng không ảnh hưởng hiểu Điều 27 |
| q02 (p21) | B_para | B_para#ldn-2020-congbao-p1#p021#g00 | có | 2 | Điều 27 trọn + mở đầu Điều 28; kết thúc lửng ở mục '3.' |
| q02 (p21) | C_para_flt | C_para_flt#ldn-2020-congbao-p1#p021#g00 | có | 2 | Như B_para (chunk g00 chứa evidence được chọn) |
| q03 (p22) | A_fixed | A_fixed#ldn-2020-congbao-p1#p022#f00 | có | 2 | Mở đầu đúng 'Điều 29' — Điều 29 trọn vẹn, đọc độc lập hiểu ngay |
| q03 (p22) | B_para | B_para#ldn-2020-congbao-p1#p022#g00 | có | 2 | Điều 29 trọn + Điều 30 k1-k3 đầy đủ hơn |
| q03 (p22) | C_para_flt | C_para_flt#ldn-2020-congbao-p1#p022#g00 | có | 2 | Như B_para |
| q05 (p27) | A_fixed | A_fixed#ldn-2020-congbao-p1#p027#f00 | có | 1 | Điều 37 k1 trọn nhưng k2 bị cắt giữa câu — mất cách viết loại hình doanh nghiệp |
| q05 (p27) | B_para | B_para#ldn-2020-congbao-p1#p027#g00 | có | 2 | Điều 37 k1 trọn + k2 đầy đủ (chỉ cụm cuối 'DNTN' lửng) |
| q05 (p27) | C_para_flt | C_para_flt#ldn-2020-congbao-p1#p027#g00 | có | 2 | Như B_para |
| q06 (p30) | A_fixed | A_fixed#ldn-2020-congbao-p1#p030#f00 | có | 2 | Mở đầu đúng 'Điều 42' — Điều 42 trọn vẹn là đoạn ngắn tự hoàn chỉnh |
| q06 (p30) | B_para | B_para#ldn-2020-congbao-p1#p030#g00 | có | 2 | Điều 42 trọn + Điều 43 trọn |
| q06 (p30) | C_para_flt | C_para_flt#ldn-2020-congbao-p1#p030#g00 | có | 2 | Như B_para |
| q07 (p31) | A_fixed | A_fixed#ldn-2020-congbao-p1#p031#f01 | có | 2 | Có tiêu đề Chương III + Mục 1 + Điều 46 k1 trọn (evidence giữa chunk) |
| q07 (p31) | B_para | B_para#ldn-2020-congbao-p1#p031#g01 | có | 2 | Điều 46 k1 trọn với ngữ cảnh Chương III/Mục 1 |
| q07 (p31) | C_para_flt | C_para_flt#ldn-2020-congbao-p1#p031#g01 | có | 2 | Như B_para |
| q08 (p36) | A_fixed | A_fixed#ldn-2020-congbao-p1#p036#f00 | có | 2 | Điều 51 k1 (a-c) + k2 trọn; k3 cắt đuôi nhưng ý chính mua lại theo giá thị trường còn đủ |
| q08 (p36) | B_para | B_para#ldn-2020-congbao-p1#p036#g00 | có | 2 | Điều 51 k1-k3 trọn vẹn |
| q08 (p36) | C_para_flt | C_para_flt#ldn-2020-congbao-p1#p036#g00 | có | 2 | Như B_para |
| q09 (p48) | A_fixed | A_fixed#ldn-2020-congbao-p1#p048#f00 | có | 2 | Mở đầu đúng 'Điều 64' — k1,k2,k3 trọn, evidence trọn câu |
| q09 (p48) | B_para | B_para#ldn-2020-congbao-p1#p048#g00 | có | 2 | Điều 64 trọn + Điều 65 k1-k2 |
| q09 (p48) | C_para_flt | C_para_flt#ldn-2020-congbao-p1#p048#g00 | có | 2 | Như B_para |
| q10 (p51) | A_fixed | A_fixed#ldn-2020-congbao-p1#p051#f00 | có | 2 | Mở đầu đúng 'Điều 69' — Điều 69 + Điều 70 trọn |
| q10 (p51) | B_para | B_para#ldn-2020-congbao-p1#p051#g00 | có | 2 | Điều 69 + 70 trọn + Điều 71 mở đầu |
| q10 (p51) | C_para_flt | C_para_flt#ldn-2020-congbao-p1#p051#g00 | có | 2 | Như B_para |
| q11 (p53) | A_fixed | A_fixed#ldn-2020-congbao-p1#p053#f00 | có | 2 | Tiêu đề Mục 2 + Điều 74 k1-k3 trọn (evidence ở k3); k4 cắt đuôi nhưng không chứa gold |
| q11 (p53) | B_para | B_para#ldn-2020-congbao-p1#p053#g01 | có | 2 | Mở đầu đúng 'Điều 74' — cả bốn khoản trọn |
| q11 (p53) | C_para_flt | C_para_flt#ldn-2020-congbao-p1#p053#g01 | có | 2 | Như B_para |

**Tổng hợp coherence (điểm / 20):**
- A_fixed: **18/20 = 0.90/2**
- B_para: **20/20 = 1.00/2**
- C_para_flt: **20/20 = 1.00/2**

## Tiêu chí 3 — Tính hữu dụng của metadata

Kiểm tra tự động trên mọi trace top-3 + rà tay 5 câu test:

| Chiến lược | Metadata theo chunk | Top-3 có source+page truy vết | Filter compliance (chỉ câu filter) |
|---|---|---|---|
| A_fixed | section, section_title, page_type, char_start/end | 66/66 | 0.8889 (dev) / 0.6667 (test) |
| B_para | section, section_title, page_type | 66/66 | 0.7778 (dev) / 0.6667 (test) |
| C_para_flt | section, section_title, page_type | 66/66 | 1.0 (dev) / 1.0 (test) |

### Rà tay 5 câu test × top-3

| Câu test | Chiến lược | Top-3 có source+page | Filter yêu cầu | Compliance top-3 |
|---|---|---|---|---|
| q18 | A_fixed | 3/3 | không | n/a |
| q18 | B_para | 3/3 | không | n/a |
| q18 | C_para_flt | 3/3 | không | n/a |
| q19 | A_fixed | 3/3 | không | n/a |
| q19 | B_para | 3/3 | không | n/a |
| q19 | C_para_flt | 3/3 | không | n/a |
| q20 | A_fixed | 3/3 | có | 0.67 |
| q20 | B_para | 3/3 | có | 0.67 |
| q20 | C_para_flt | 3/3 | có | 1.00 |
| q21 | A_fixed | 3/3 | không | n/a |
| q21 | B_para | 3/3 | không | n/a |
| q21 | C_para_flt | 3/3 | không | n/a |
| q22 | A_fixed | 3/3 | không | n/a |
| q22 | B_para | 3/3 | không | n/a |
| q22 | C_para_flt | 3/3 | không | n/a |

- 100% top-3 giữ được `source` + `page` ở mọi chiến lược → truy vết về Công Báo luôn được.
- A/B không áp filter nên compliance < 1.0 là đúng thiết kế (đo mức tuân thủ của kết quả khi người dùng có yêu cầu phạm vi); C = 1.0 nhờ filter SQL theo `section`, và mọi câu test có filter đều trả kết quả thuộc đúng phạm vi yêu cầu.
- Trường hữu ích: `section` — giúp lọc phạm vi theo chương (cấu hình C) và cho biết ngữ cảnh chương của chunk ngay trong metadata.
- Không phát hiện lỗi metadata trong 45 bản ghi kiểm tra (5 câu test × top-3 × 3 chiến lược). Hạn chế: `section` gán theo trang vật lý nên một trang chứa cả cuối chương trước và đầu chương sau sẽ mang section của chương mở đầu trên trang — metadata lệch biên ở các trang chuyển chương.

## Tiêu chí 4 — Chất lượng grounding (chấm thủ công, 5 câu test)

Chấm top-3 của **mỗi chiến lược** trên 5 câu test. Thang 0–2 (0 = top-3 không có bằng chứng; 1 = có bằng chứng nhưng thiếu điều kiện/ngữ cảnh; 2 = đủ để trả lời và truy nguồn). Bằng chứng tương đương (khác vị trí gold nhưng trả lời đúng câu hỏi) do người chấm xác nhận. Nhãn soạn lại sau khi đổi model vì top-3 thay đổi theo embedding.

| Câu hỏi | Chiến lược | EvHit@3 (auto) | Top-3 chunk | Điểm | Lý do |
|---|---|---|---|---|---|
| q18: Doanh nghiệp tư nhân có được phát hành chứng kho... | A_fixed | có | A_fixed#ldn-2020-congbao-p2#p052#f01, A_fixed#ldn-2020-congbao-p2#p002#f01, A_fixed#ldn-2020-congbao-p1#p092#f00 | 2 | Rank-1 chứa Điều 188 với k2 'không được phát hành bất kỳ loại chứng khoán nào' — đủ trả lời và truy nguồn |
| q18: Doanh nghiệp tư nhân có được phát hành chứng kho... | B_para | có | B_para#ldn-2020-congbao-p2#p052#g01, B_para#ldn-2020-congbao-p1#p088#g01, B_para#ldn-2020-congbao-p2#p065#g00 | 2 | Rank-1 là Điều 188 trọn k1-k3 (k2 nêu rõ cấm phát hành chứng khoán) + ngữ cảnh Chương VII |
| q18: Doanh nghiệp tư nhân có được phát hành chứng kho... | C_para_flt | có | C_para_flt#ldn-2020-congbao-p2#p052#g01, C_para_flt#ldn-2020-congbao-p1#p088#g01, C_para_flt#ldn-2020-congbao-p2#p065#g00 | 2 | Như B_para (rank-1 cùng chunk) |
| q19: Công ty không còn đủ số thành viên tối thiểu tro... | A_fixed | có | A_fixed#ldn-2020-congbao-p2#p066#f01, A_fixed#ldn-2020-congbao-p1#p037#f02, A_fixed#ldn-2020-congbao-p1#p069#f01 | 2 | Rank-1 chứa Điều 207 k1c (06 tháng liên tục) + k2 điều kiện giải thể — đủ trả lời và truy nguồn |
| q19: Công ty không còn đủ số thành viên tối thiểu tro... | B_para | không | B_para#ldn-2020-congbao-p1#p043#g01, B_para#ldn-2020-congbao-p1#p038#g01, B_para#ldn-2020-congbao-p2#p023#g01 | 0 | Top-3 là Điều 59, Điều 54, Điều 154 — không có Điều 207 |
| q19: Công ty không còn đủ số thành viên tối thiểu tro... | C_para_flt | không | C_para_flt#ldn-2020-congbao-p1#p043#g01, C_para_flt#ldn-2020-congbao-p1#p038#g01, C_para_flt#ldn-2020-congbao-p2#p023#g01 | 0 | Như B_para |
| q20: Trường hợp nào một công ty được coi là công ty m... | A_fixed | không | A_fixed#ldn-2020-congbao-p2#p056#f01, A_fixed#ldn-2020-congbao-p2#p056#f02, A_fixed#ldn-2020-congbao-p2#p024#f02 | 0 | Top-3 chỉ có Điều 195 k3-k6 (can thiệp/trách nhiệm công ty mẹ) — thiếu k1 định nghĩa ba trường hợp sở hữu trên 50% |
| q20: Trường hợp nào một công ty được coi là công ty m... | B_para | không | B_para#ldn-2020-congbao-p1#p063#g02, B_para#ldn-2020-congbao-p2#p056#g01, B_para#ldn-2020-congbao-p2#p056#g00 | 0 | Rank-1 là mảnh chunk 63 ký tự; rank-2/3 là Điều 195 k3-k6 — vẫn thiếu k1 định nghĩa |
| q20: Trường hợp nào một công ty được coi là công ty m... | C_para_flt | có | C_para_flt#ldn-2020-congbao-p2#p056#g01, C_para_flt#ldn-2020-congbao-p2#p056#g00, C_para_flt#ldn-2020-congbao-p2#p055#g01 | 2 | Rank-3 chứa Điều 194 k2 và Điều 195 k1 (evidence 'Sở hữu trên 50%...') — đủ định nghĩa công ty mẹ |
| q21: Công ty cổ phần cần ít nhất bao nhiêu cổ đông kh... | A_fixed | không | A_fixed#ldn-2020-congbao-p1#p088#f01, A_fixed#ldn-2020-congbao-p1#p088#f00, A_fixed#ldn-2020-congbao-p1#p083#f00 | 2 | Rank-1 chứa Điều 112 k1 'ít nhất 03 cổ đông sáng lập' khi thành lập — bằng chứng tương đương gold (Điều 111), người chấm xác nhận hợp lệ |
| q21: Công ty cổ phần cần ít nhất bao nhiêu cổ đông kh... | B_para | có | B_para#ldn-2020-congbao-p1#p088#g00, B_para#ldn-2020-congbao-p1#p080#g01, B_para#ldn-2020-congbao-p1#p088#g01 | 2 | Rank-2 chứa Điều 111 k1a-b (gold trang 80): 'số lượng cổ đông tối thiểu là 03 và không hạn chế số lượng tối đa' |
| q21: Công ty cổ phần cần ít nhất bao nhiêu cổ đông kh... | C_para_flt | có | C_para_flt#ldn-2020-congbao-p1#p088#g00, C_para_flt#ldn-2020-congbao-p1#p080#g01, C_para_flt#ldn-2020-congbao-p1#p088#g01 | 2 | Như B_para (rank-2 cùng chunk) |
| q22: Giấy chứng nhận đăng ký doanh nghiệp bị mất hoặc... | A_fixed | có | A_fixed#ldn-2020-congbao-p1#p021#f00, A_fixed#ldn-2020-congbao-p1#p022#f01, A_fixed#ldn-2020-congbao-p1#p022#f02 | 2 | Rank-1 chứa Điều 27 k2 (trang 21): mất/hư hỏng được cấp lại GCN và nộp lệ phí — đủ trả lời |
| q22: Giấy chứng nhận đăng ký doanh nghiệp bị mất hoặc... | B_para | có | B_para#ldn-2020-congbao-p1#p021#g00, B_para#ldn-2020-congbao-p2#p068#g01, B_para#ldn-2020-congbao-p1#p022#g01 | 2 | Rank-1 cùng chunk Điều 27 g00 — như A_fixed |
| q22: Giấy chứng nhận đăng ký doanh nghiệp bị mất hoặc... | C_para_flt | có | C_para_flt#ldn-2020-congbao-p1#p021#g00, C_para_flt#ldn-2020-congbao-p2#p068#g01, C_para_flt#ldn-2020-congbao-p1#p022#g01 | 2 | Như B_para |

**Tổng hợp grounding trên 5 câu test:**
| Chiến lược | Điểm 0 | Điểm 1 | Điểm 2 | Tổng điểm /10 | Trung bình /2 |
|---|---|---|---|---|---|
| A_fixed | 1 | 0 | 4 | 8/10 | **0.80/2** |
| B_para | 2 | 0 | 3 | 6/10 | **0.60/2** |
| C_para_flt | 1 | 0 | 4 | 8/10 | **0.80/2** |

Lưu ý: 5 câu test là mẫu rất nhỏ — chênh 1–2 câu là sai số lớn; kết luận chiến lược dựa chủ yếu vào dev (17 câu) và chỉ số tự động.

## Tiêu chí 5 — Tác động của chiến lược dữ liệu

| Chiến lược | Số chunk | TB ký tự/chunk | Thời gian embed (s) | Áp filter | Hit@1 dev | EvHit@3 dev | Hit@1 test | EvHit@3 test |
|---|---|---|---|---|---|---|---|---|
| A_fixed | 456 | 809 | 166.9s | không | 6/17 = 0.3529 | 13/17 = 0.7647 | 3/5 = 0.6 | 3/5 = 0.6 |
| B_para | 341 | 954 | 149.4s | không | 8/17 = 0.4706 | 13/17 = 0.7647 | 2/5 = 0.4 | 3/5 = 0.6 |
| C_para_flt | 341 | 954 | 145.4s | có | 9/17 = 0.5294 | 13/17 = 0.7647 | 2/5 = 0.4 | 4/5 = 0.8 |

Chi phí: 0 USD cho cả ba chiến lược (embedding local; thời gian là chi phí duy nhất và tỉ lệ thuận với số chunk — đổi sang EmbeddingGemma 2 (740M) làm thời gian embed tăng ~15 lần so với MiniLM trên cùng phần cứng CPU).

### So sánh từng cặp yếu tố

| Thay đổi | EvHit@3 dev | EvHit@3 test | Hit@1 dev | Nhận xét |
|---|---|---|---|---|
| A → B (đổi cách chia chunk: cửa sổ cố định → theo đoạn) | 13/17 → 13/17 | 3/5 → 3/5 | 6/17 → 8/17 | Chunk theo đoạn giữ trọn ý hơn cửa sổ ký tự → tăng chất lượng truy xuất cùng tài nguyên. |
| B → C (giữ nguyên chunk, thêm metadata filter) | 13/17 → 13/17 | 3/5 → 4/5 | 8/17 → 9/17 | Chỉ thêm filter (cùng chunk, cùng embed) — chênh lệch thuần túy do metadata filter. |

### Phân tích lỗi theo chiến lược

Với mỗi câu miss, phân biệt: **(R)** evidence có trong một chunk nào đó của chiến lược nhưng không lọt top-3 (lỗi truy xuất/ranking) hay **(C)** evidence không tồn tại trọn vẹn trong chunk nào (lỗi chia chunk — thường do cắt qua biên).

**A_fixed** — 6 câu miss trên 22:
- `q04` (dev, truc_tiep) [R]
- `q05` (dev, truc_tiep) [R]
- `q11` (dev, dien_dat_lai) [R]
- `q17` (dev, dieu_kien) [R] + filter làm thu hẹp kết quả
- `q20` (test, truc_tiep) [R] + filter làm thu hẹp kết quả
- `q21` (test, truc_tiep) [R]

**B_para** — 6 câu miss trên 22:
- `q04` (dev, truc_tiep) [R]
- `q05` (dev, truc_tiep) [R]
- `q11` (dev, dien_dat_lai) [R]
- `q17` (dev, dieu_kien) [R] + filter làm thu hẹp kết quả
- `q19` (test, dieu_kien) [R]
- `q20` (test, truc_tiep) [R] + filter làm thu hẹp kết quả

**C_para_flt** — 5 câu miss trên 22:
- `q04` (dev, truc_tiep) [R]
- `q05` (dev, truc_tiep) [R]
- `q11` (dev, dien_dat_lai) [R]
- `q17` (dev, dieu_kien) [R] + filter làm thu hẹp kết quả
- `q19` (test, dieu_kien) [R]


## Kết luận (dữ liệu tự động + nhãn chấm tay)

1. **C_para_flt tốt nhất** trong bộ ba theo chỉ số tự động: cùng chunk với B nhưng filter `section` cải thiện EvHit@3 test (4/5 vs 3/5) và đạt compliance 1.0 tuyệt đối.
2. **B > A** trên dev Hit@1 (8/17 vs 6/17): chunk theo đoạn giữ trọn ý hơn cửa sổ ký tự — coherence chấm tay xác nhận cùng hướng.
3. EvHit@3 dev ba chiến lược bằng nhau (13/17): bốn câu miss chung (q04, q05, q11, q17) là miss truy xuất thuần túy — gold chunk tồn tại nhưng không vào top-3 do boilerplate pháp luật lặp giữa các điều (vd. quy định "10 ngày" của Điều 30 và Điều 33) — xem `scripts/diagnose_misses.py`.
4. Chi phí mọi chiến lược bằng nhau (embed local, 0 USD); thời gian embed ~15× khi đổi sang EmbeddingGemma 2 — đánh đổi chất lượng/nguồn lực cần ghi khi chọn model.
5. **Nguy cơ thiên lệch**: người chấm thủ công trùng tác giả pipeline, và nhãn được soạn nháp với hỗ trợ AI rồi học viên rà soát — đã ghi phương pháp ở tiêu chí 2; khuyến khích một người chấm độc lập kiểm tra chéo 10 ô ngẫu nhiên.
