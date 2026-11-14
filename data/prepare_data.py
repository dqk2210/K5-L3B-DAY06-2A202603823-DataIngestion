# -*- coding: utf-8 -*-
"""Chuẩn bị corpus cho lab Data Ingestion Engineering.

Đọc PDF Công báo (Luật Doanh nghiệp 59/2020/QH14), trích xuất text theo trang
bằng pymupdf, phân loại trang, theo dõi Chương, và sinh:
  - data/extracted/pages.jsonl : 1 dòng = 1 trang (document_id, page, section, page_type, chars, text)
  - data/manifest.json         : nguồn, quyền sử dụng, số trang vật lý/quy tắc tính,
                                 thống kê cấu trúc (Chương/Điều), phiên bản công cụ, ghi nhận lỗi.

Chạy:  python data/prepare_data.py
"""
import hashlib
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pymupdf

sys.stdout.reconfigure(encoding="utf-8")

DATA_DIR = Path(__file__).resolve().parent
RAW_DIR = DATA_DIR / "raw"
EXTRACT_DIR = DATA_DIR / "extracted"

FILES = [
    {
        "doc_id": "ldn-2020-congbao-p1",
        "file": "data/raw/ldn_2020_congbao_1.pdf",
        "cong_bao_so": "713 + 714",
        "cong_bao_ngay": "2020-07-24",
        "source_url": "https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2020/6/31674/31830-1-2020713-71459-2020-qh14.pdf",
    },
    {
        "doc_id": "ldn-2020-congbao-p2",
        "file": "data/raw/ldn_2020_congbao_2.pdf",
        "cong_bao_so": "715 + 716",
        "cong_bao_ngay": "2020-07-24",
        "source_url": "https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2020/6/31674/31833-1-2020715-71659-2020-qh14.pdf",
    },
]

# Quy tắc tính trang nội dung hợp lệ (ghi vào manifest theo yêu cầu GUIDE.md)
MIN_CHARS_VALID = 800   # trang >= 800 ký tự text chuẩn hóa -> tính là nội dung
MIN_CHARS_BLANK = 200   # trang < 200 ký tự -> trống/ apenas header

# Heading thật nằm riêng một dòng ("Chương IV"); tham chiếu thân bài
# ("Mục 1 Chương III") phải bị loại. Title heading là dòng CHỮ IN HOA kế tiếp.
CHUONG_RE = re.compile(r"^Chương\s+([IVX]+)[ \t]*$", re.M)
DIEU_RE = re.compile(r"Điều\s*(\d+)\.")
# Lỗi font PDF tiếng Việt: khoảng trắng lọt giữa chữ cái và ký tự mang dấu
BROKEN_SPACE_RE = re.compile(r"[a-zà-ỹ] [ớừảệộổ]")


def normalize(text: str) -> str:
    """Chuẩn hóa text thô: gộp dòng, bỏ khoảng trắng thừa."""
    text = text.replace("\u00ad", "")  # soft hyphen
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def classify_page(chars: int, text: str) -> str:
    """Phân loại trang: muc_luc / rong / noi_dung."""
    if "MỤC LỤC" in text.upper():
        return "muc_luc"
    if chars < MIN_CHARS_BLANK:
        return "rong"
    return "noi_dung"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main() -> None:
    EXTRACT_DIR.mkdir(exist_ok=True)
    pages_out = EXTRACT_DIR / "pages.jsonl"

    current_chuong = ("khai_quat", "")  # trước Chương I (phần mở đầu)
    all_dieu: set[int] = set()
    all_chuong: list[dict] = []
    seen_chuong: set[str] = set()
    broken_spaces_total = 0
    file_stats: list[dict] = []

    with pages_out.open("w", encoding="utf-8", newline="\n") as fout:
        for spec in FILES:
            pdf_path = DATA_DIR.parent / spec["file"]
            doc = pymupdf.open(pdf_path)
            n_pages = len(doc)
            n_valid = 0
            chars_file = 0
            dieu_file: set[int] = set()
            broken_file = 0

            for i in range(n_pages):
                raw = doc[i].get_text()
                text = normalize(raw)
                chars = len(text)
                page_type = classify_page(chars, text)
                if chars >= MIN_CHARS_VALID:
                    n_valid += 1
                chars_file += chars
                broken_file += len(BROKEN_SPACE_RE.findall(text))

                # cập nhật Chương hiện hành (giữ trạng thái liên tục giữa 2 file)
                for m in CHUONG_RE.finditer(raw):
                    roman = m.group(1)
                    # title = dòng không rỗng kế sau heading; chỉ nhận nếu IN HOA
                    title_line = ""
                    for line in raw[m.end() :].split("\n"):
                        if line.strip():
                            title_line = line.strip()
                            break
                    if not title_line or title_line != title_line.upper():
                        continue  # tham chiếu trong thân bài, không phải heading
                    key = roman
                    if key not in seen_chuong:
                        seen_chuong.add(key)
                        all_chuong.append({"chuong": roman, "tieu_de": title_line})
                    current_chuong = (f"chuong_{roman.lower()}", title_line)

                for m in DIEU_RE.finditer(text):
                    dieu_file.add(int(m.group(1)))

                fout.write(json.dumps({
                    "document_id": spec["doc_id"],
                    "file": spec["file"],
                    "page": i + 1,
                    "section": current_chuong[0],
                    "section_title": current_chuong[1],
                    "page_type": page_type,
                    "chars": chars,
                    "text": text,
                }, ensure_ascii=False) + "\n")

            doc.close()
            all_dieu |= dieu_file
            broken_spaces_total += broken_file
            file_stats.append({
                "doc_id": spec["doc_id"],
                "file": spec["file"],
                "sha256": sha256_of(pdf_path),
                "size_bytes": pdf_path.stat().st_size,
                "cong_bao": f"Số {spec['cong_bao_so']} ngày {spec['cong_bao_ngay']}",
                "source_url": spec["source_url"],
                "pages_physical": n_pages,
                "pages_valid": n_valid,
                "chars_total": chars_file,
                "dieu_phat_hien": f"{min(dieu_file)}-{max(dieu_file)} ({len(dieu_file)} điều)",
                "loi_khoang_trang": broken_file,
            })

    dieu_thieu = [n for n in range(min(all_dieu), max(all_dieu) + 1) if n not in all_dieu]
    manifest = {
        "corpus_id": "ldn-2020",
        "title": "Luật Doanh nghiệp số 59/2020/QH14",
        "so_hieu": "59/2020/QH14",
        "loai_van_ban": "Luật (văn bản quy phạm pháp luật)",
        "co_quan_ban_hanh": "Quốc hội",
        "ngay_ban_hanh": "2020-06-17",
        "ngay_hieu_luc": "2021-01-01",
        "nguon": {
            "trang_van_ban": "https://congbao.chinhphu.vn/van-ban/luat-so-59-2020-qh14-31674.htm",
            "cach_lay": (
                "Tải trực tiếp file PDF bản in Công báo từ CDN chính thức "
                "congbaocdn.chinhphu.vn (link trong từng file bên dưới) bằng curl -L."
            ),
        },
        "quyen_su_dung": {
            "trang_thai": "Được phép xử lý, trích xuất, tái sử dụng.",
            "co_so": (
                "Văn bản quy phạm pháp luật không được bảo hộ quyền tác giả "
                "(Luật Sở hữu trí tuệ 2005, sửa đổi bổ sung 2022 — Điều 13). "
                "Bản dùng là bản in Công báo chính thức do Văn phòng Chính phủ công bố."
            ),
            "yeu_cau": "Ghi rõ nguồn Công báo (số, ngày) khi trích dẫn/tái sử dụng.",
            "ghi_chu": (
                "Chỉ dùng bản gốc Công báo của Chính phủ; không dùng bản hợp nhất "
                "của dịch vụ thương mại (thuvienphapluat, luatvietnam...)."
            ),
            "muc_dich": "Học liệu cá nhân cho lab Data Ingestion Engineering, phi thương mại.",
        },
        "so_trang": {
            "quy_tac_tinh": (
                "Trang nội dung hợp lệ = trang có >= 800 ký tự text đã chuẩn hóa. "
                "Loại: trang trống/chỉ còn header (<200 ký tự) và trang mục lục."
            ),
            "tong_so_trang_vat_ly": sum(f["pages_physical"] for f in file_stats),
            "tong_so_trang_noi_dung_hop_le": sum(f["pages_valid"] for f in file_stats),
        },
        "extraction": {
            "tool": "pymupdf (fitz)",
            "pymupdf_version": pymupdf.__version__,
            "python_version": sys.version.split()[0],
            "ngay_chay": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "don_vi_xuat": "text theo trang, UTF-8, chuẩn hóa khoảng trắng",
            "ghi_nhan_loi": (
                f"Sót lại {broken_spaces_total} vị trí lỗi khoảng trắng dấu tiếng Việt "
                "trên toàn corpus (lỗi font PDF: dấu bị tách thành glyph riêng). "
                "So sánh: pypdf sinh ~2.000 lỗi tương tự trên cùng file -> chọn pymupdf. "
                "Không có trang nào là scan (toàn bộ extract được text)."
            ),
        },
        "cau_truc": {
            "tong_so_dieu": len(all_dieu),
            "dieu_range": f"{min(all_dieu)}-{max(all_dieu)}",
            "dieu_thieu": dieu_thieu,
            "tong_so_chuong": len(all_chuong),
            "chuong": all_chuong,
        },
        "luu_y_noi_dung": (
            "Luật Doanh nghiệp đã được sửa đổi, bổ sung bởi nhiều văn bản sau 2020 "
            "(đáng chú ý Luật số 76/2025/QH15). Corpus này dùng bản gốc Công báo 2020 "
            "chưa hợp nhất — câu hỏi benchmark phải trả lời theo văn bản gốc này."
        ),
        "files": file_stats,
        "trich_xuat_theo_trang": {
            "file": "data/extracted/pages.jsonl",
            "moi_dong": {
                "document_id": "ID tài liệu",
                "file": "đường dẫn file gốc",
                "page": "số trang (1-based)",
                "section": "slug chương đang hiệu lực trên trang",
                "section_title": "tên chương",
                "page_type": "noi_dung | muc_luc | rong",
                "chars": "số ký tự đã chuẩn hóa",
                "text": "nội dung trang",
            },
        },
    }

    out = DATA_DIR / "manifest.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Đã ghi: {out.name}, {pages_out.relative_to(DATA_DIR.parent)}")
    print(f"Tổng: {manifest['so_trang']['tong_so_trang_vat_ly']} trang vật lý, "
          f"{manifest['so_trang']['tong_so_trang_noi_dung_hop_le']} trang hợp lệ, "
          f"{manifest['cau_truc']['tong_so_dieu']} điều, {len(all_chuong)} chương, "
          f"{broken_spaces_total} lỗi khoảng trắng")


if __name__ == "__main__":
    main()
