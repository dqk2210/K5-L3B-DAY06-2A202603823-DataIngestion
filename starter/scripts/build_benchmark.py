"""Build benchmark/questions.jsonl grounded in the extracted corpus.

Each question spec carries an evidence anchor (exact corpus substring). The
script locates the anchor in pages.jsonl to derive gold_source_id, gold_page
and section, so every gold label is verifiable — no invented quotes.
Run from starter/: python scripts/build_benchmark.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parents[2]
PAGES_PATH = REPO / "data" / "extracted" / "pages.jsonl"
OUT_PATH = REPO / "benchmark" / "questions.jsonl"


def squash(text: str) -> str:
    """Whitespace-insensitive form (matches evaluation's evidence matcher)."""
    return re.sub(r"\s+", "", text)


# (id, split, type, question, evidence anchor, filter or None)
SPECS = [
    # ---------- dev: trực tiếp ----------
    ("q01", "dev", "truc_tiep",
     "Đăng ký doanh nghiệp được thực hiện theo những phương thức nào?",
     "Đăng ký doanh nghiệp trực tiếp tại Cơ quan đăng ký kinh doanh", None),
    ("q02", "dev", "truc_tiep",
     "Doanh nghiệp được cấp Giấy chứng nhận đăng ký doanh nghiệp khi thỏa mãn những điều kiện gì?",
     "Ngành, nghề đăng ký kinh doanh không bị cấm đầu tư kinh doanh", None),
    ("q03", "dev", "dien_dat_lai",
     "Một mã số doanh nghiệp đã cấp có thể được cấp lại cho doanh nghiệp khác không?",
     "Mỗi doanh nghiệp có một mã số duy nhất và không được sử dụng lại để cấp cho doanh nghiệp khác", None),
    ("q04", "dev", "truc_tiep",
     "Doanh nghiệp phải đăng ký thay đổi nội dung Giấy chứng nhận đăng ký doanh nghiệp trong thời hạn bao lâu kể từ ngày có thay đổi?",
     "trong thời hạn 10 ngày kể từ ngày có thay đổi", None),
    ("q05", "dev", "truc_tiep",
     "Tên tiếng Việt của doanh nghiệp bao gồm những thành tố nào?",
     "Tên tiếng Việt của doanh nghiệp bao gồm hai thành tố theo thứ tự sau đây", None),
    ("q06", "dev", "truc_tiep",
     "Trụ sở chính của doanh nghiệp được đặt ở đâu?",
     "Trụ sở chính của doanh nghiệp đặt trên lãnh thổ Việt Nam, là địa chỉ liên lạc của doanh nghiệp", None),
    # ---------- dev: diễn đạt lại ----------
    ("q07", "dev", "dien_dat_lai",
     "Công ty TNHH hai thành viên trở lên có tối đa bao nhiêu thành viên?",
     "doanh nghiệp có từ 02 đến 50 thành viên là tổ chức, cá nhân", None),
    ("q08", "dev", "dieu_kien",
     "Trường hợp nào thành viên công ty TNHH có quyền yêu cầu công ty mua lại phần vốn góp của mình?",
     "nếu thành viên đó đã bỏ phiếu không tán thành đối với nghị quyết, quyết định của Hội đồng thành viên", None),
    ("q09", "dev", "dieu_kien",
     "Đối với doanh nghiệp nhà nước, Giám đốc hoặc Tổng giám đốc có bị giới hạn quan hệ gia đình với người quản lý công ty không?",
     "không được là người có quan hệ gia đình của người quản lý công ty", None),
    ("q10", "dev", "dieu_kien",
     "Công ty trách nhiệm hữu hạn khi nào được chia lợi nhuận cho các thành viên?",
     "sau khi đã hoàn thành nghĩa vụ thuế và các nghĩa vụ tài chính khác", {"section": None}),  # section filled at build
    # ---------- dev: diễn đạt lại (tiếp) ----------
    ("q11", "dev", "dien_dat_lai",
     "Công ty TNHH một thành viên có được phát hành cổ phần không?",
     "Công ty trách nhiệm hữu hạn một thành viên không được phát hành cổ phần", None),
    ("q12", "dev", "dien_dat_lai",
     "Doanh nghiệp nhà nước được tổ chức và quản lý dưới những hình thức nào?",
     "Doanh nghiệp nhà nước được tổ chức quản lý dưới hình thức công ty trách nhiệm hữu hạn, công ty cổ phần", None),
    ("q13", "dev", "truc_tiep",
     "Luật Doanh nghiệp 2020 quy định công ty cổ phần có những loại cổ phần ưu đãi nào?",
     "Cổ phần ưu đãi gồm các loại sau đây", None),
    ("q14", "dev", "truc_tiep",
     "Khi nào công ty cổ phần được trả cổ tức cho cổ phần phổ thông?",
     "Công ty cổ phần chỉ được trả cổ tức của cổ phần phổ thông khi có đủ các điều kiện sau đây", {"section": None}),
    ("q15", "dev", "truc_tiep",
     "Cuộc họp Đại hội đồng cổ đông được tiến hành khi có tỷ lệ cổ đông dự họp như thế nào?",
     "được tiến hành khi có số cổ đông dự họp đại diện trên 50% tổng số phiếu biểu quyết", None),
    ("q16", "dev", "dien_dat_lai",
     "Nghị quyết Đại hội đồng cổ đông về thay đổi ngành, nghề kinh doanh cần được tán thành với tỷ lệ bao nhiêu?",
     "được thông qua nếu được số cổ đông đại diện từ 65% tổng số phiếu biểu quyết trở lên", None),
    # ---------- dev: filter ----------
    ("q17", "dev", "dieu_kien",
     "Trách nhiệm của thành viên hợp danh đối với các nghĩa vụ của công ty hợp danh được quy định như thế nào?",
     "Thành viên hợp danh phải là cá nhân, chịu trách nhiệm bằng toàn bộ tài sản của mình về các nghĩa vụ của công ty", {"section": None}),
    # ---------- test ----------
    ("q18", "test", "dien_dat_lai",
     "Doanh nghiệp tư nhân có được phát hành chứng khoán không?",
     "Doanh nghiệp tư nhân không được phát hành bất kỳ loại chứng khoán nào", None),
    ("q19", "test", "dieu_kien",
     "Công ty không còn đủ số thành viên tối thiểu trong bao lâu thì bị giải thể?",
     "không còn đủ số lượng thành viên tối thiểu theo quy định của Luật này trong thời hạn 06 tháng liên tục", None),
    ("q20", "test", "truc_tiep",
     "Trường hợp nào một công ty được coi là công ty mẹ của công ty khác?",
     "Sở hữu trên 50% vốn điều lệ hoặc tổng số cổ phần phổ thông của công ty đó", {"section": None}),
    ("q21", "test", "truc_tiep",
     "Công ty cổ phần cần ít nhất bao nhiêu cổ đông khi thành lập?",
     "số lượng cổ đông tối thiểu là 03 và không hạn chế số lượng tối đa", None),
    ("q22", "test", "dieu_kien",
     "Giấy chứng nhận đăng ký doanh nghiệp bị mất hoặc hư hỏng thì được xử lý như thế nào?",
     "Trường hợp Giấy chứng nhận đăng ký doanh nghiệp bị mất, bị hư hỏng hoặc bị hủy hoại dưới hình thức khác, doanh nghiệp được cấp lại Giấy chứng nhận đăng ký doanh nghiệp", None),
]


# Đáp án ngắn gọn, trọn nghĩa cho từng câu (trích nguồn điều luật trong ngoặc).
ANSWERS = {
    "q01": "Ba phương thức: trực tiếp tại Cơ quan đăng ký kinh doanh, qua dịch vụ bưu chính, hoặc qua mạng thông tin điện tử (Điều 26 k1).",
    "q02": "Bốn điều kiện: ngành nghề không bị cấm đầu tư kinh doanh; tên đặt đúng quy định các Điều 37, 38, 39, 41; có hồ sơ đăng ký hợp lệ; nộp đủ lệ phí (Điều 27 k1).",
    "q03": "Không. Mỗi doanh nghiệp có một mã số duy nhất và không được sử dụng lại để cấp cho doanh nghiệp khác (Điều 29 k1).",
    "q04": "Trong thời hạn 10 ngày kể từ ngày có thay đổi (Điều 30 k2).",
    "q05": "Hai thành tố theo thứ tự: loại hình doanh nghiệp và tên riêng (Điều 37 k1).",
    "q06": "Đặt trên lãnh thổ Việt Nam; là địa chỉ liên lạc của doanh nghiệp, xác định theo địa giới đơn vị hành chính, có số điện thoại, số fax và thư điện tử nếu có (Điều 42).",
    "q07": "Tối đa 50 thành viên là tổ chức, cá nhân (tối thiểu 02) (Điều 46 k1).",
    "q08": "Khi đã bỏ phiếu không tán thành nghị quyết, quyết định của Hội đồng thành viên về: sửa đổi Điều lệ liên quan quyền/nghĩa vụ thành viên, HĐTV; tổ chức lại công ty; hoặc trường hợp khác theo Điều lệ (Điều 51 k1).",
    "q09": "Có. Giám đốc/Tổng giám đốc của DNNN và công ty con của DNNN không được là người có quan hệ gia đình của người quản lý công ty, Kiểm soát viên của công ty và của công ty mẹ (Điều 64 k3).",
    "q10": "Chỉ được chia lợi nhuận sau khi đã hoàn thành nghĩa vụ thuế và các nghĩa vụ tài chính khác theo pháp luật, bảo đảm thanh toán đủ các khoản nợ và nghĩa vụ tài sản khác đến hạn sau khi chia (Điều 69).",
    "q11": "Không, trừ trường hợp để chuyển đổi thành công ty cổ phần (Điều 74 k3).",
    "q12": "Được tổ chức quản lý dưới hình thức công ty trách nhiệm hữu hạn hoặc công ty cổ phần, gồm doanh nghiệp Nhà nước nắm giữ 100% vốn điều lệ hoặc nắm trên 50% vốn điều lệ/tổng số cổ phần có quyền biểu quyết (Điều 88 k1).",
    "q13": "Bốn loại: cổ phần ưu đãi cổ tức, ưu đãi hoàn lại, ưu đãi biểu quyết, và ưu đãi khác theo Điều lệ công ty và pháp luật chứng khoán (Điều 114 k2).",
    "q14": "Khi đã hoàn thành nghĩa vụ thuế và các nghĩa vụ tài chính khác; đã trích lập các quỹ công ty và bù đắp lỗ trước đó; và bảo đảm thanh toán đủ các khoản nợ đến hạn ngay sau khi trả cổ tức (Điều 135 k2).",
    "q15": "Khi có số cổ đông dự họp đại diện trên 50% tổng số phiếu biểu quyết; tỷ lệ cụ thể do Điều lệ công ty quy định (Điều 145 k1).",
    "q16": "Từ 65% tổng số phiếu biểu quyết trở lên của tất cả cổ đông dự họp tán thành; tỷ lệ cụ thể do Điều lệ quy định (Điều 148 k1).",
    "q17": "Thành viên hợp danh phải là cá nhân và chịu trách nhiệm bằng toàn bộ tài sản của mình về các nghĩa vụ của công ty (Điều 177 k1).",
    "q18": "Không. Doanh nghiệp tư nhân không được phát hành bất kỳ loại chứng khoán nào (Điều 188 k2).",
    "q19": "06 tháng liên tục không còn đủ số lượng thành viên tối thiểu mà không làm thủ tục chuyển đổi loại hình doanh nghiệp (Điều 207 k1c).",
    "q20": "Một trong ba trường hợp: sở hữu trên 50% vốn điều lệ hoặc tổng số cổ phần phổ thông; có quyền trực tiếp/gián tiếp quyết định bổ nhiệm đa số hoặc tất cả thành viên HĐQT, Giám đốc/Tổng giám đốc; có quyền quyết định sửa đổi, bổ sung Điều lệ (Điều 195 k1).",
    "q21": "Tối thiểu 03 cổ đông và không hạn chế số lượng tối đa (Điều 111 k1b).",
    "q22": "Doanh nghiệp được cấp lại Giấy chứng nhận đăng ký doanh nghiệp và phải nộp lệ phí theo quy định của pháp luật (Điều 27 k2).",
}


def main() -> None:
    pages = [json.loads(line) for line in PAGES_PATH.open(encoding="utf-8") if line.strip()]    # squashed page text for whitespace-insensitive anchor lookup
    index: list[tuple[dict, str]] = [(p, squash(p["text"])) for p in pages]

    questions: list[dict] = []
    problems: list[str] = []
    for qid, split, qtype, question, anchor, filt in SPECS:
        anchor_sq = squash(anchor)
        found = [(p, pos) for p, sq in index if (pos := sq.find(anchor_sq)) != -1]
        if not found:
            problems.append(f"{qid}: evidence NOT FOUND in corpus: {anchor[:60]}...")
            continue
        page, pos = found[0]  # first occurrence (gazette reprints would come later)
        section = page.get("section", "")
        if filt is not None and filt.get("section") is None:
            filt = {"section": section}  # pin filter to the gold page's section
        q = {
            "id": qid,
            "split": split,
            "type": qtype,
            "question": question,
            "expected_answer": "",  # filled from evidence below
            "gold_source_id": page["document_id"],
            "gold_page": page["page"],
            "evidence_quote": anchor,
        }
        if filt:
            q["filter"] = filt
        q["expected_answer"] = ANSWERS[qid]
        questions.append(q)

    if problems:
        raise SystemExit("BUILD FAILED:\n  - " + "\n  - ".join(problems))

    # lab requirements (BENCHMARK.md)
    dev = sum(1 for q in questions if q["split"] == "dev")
    test = sum(1 for q in questions if q["split"] == "test")
    filtered = [q for q in questions if q.get("filter")]
    filtered_test = [q for q in filtered if q["split"] == "test"]
    assert dev >= 15 and test >= 5 and len(filtered) >= 3 and len(filtered_test) >= 1, \
        f"splits wrong: dev={dev} test={test} filter={len(filtered)} filter_test={len(filtered_test)}"
    assert len({q['id'] for q in questions}) == len(questions)

    OUT_PATH.parent.mkdir(exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8", newline="\n") as fout:
        for q in questions:
            fout.write(json.dumps(q, ensure_ascii=False) + "\n")

    print(f"Wrote {len(questions)} questions -> {OUT_PATH}")
    print(f"dev={dev} test={test} filter={len(filtered)} (test filter={len(filtered_test)})")
    for q in questions:
        mark = " [filter]" if q.get("filter") else ""
        print(f"  {q['id']} {q['split']:4s} {q['type']:12s} {q['gold_source_id']} p{q['gold_page']}{mark}")


if __name__ == "__main__":
    main()
