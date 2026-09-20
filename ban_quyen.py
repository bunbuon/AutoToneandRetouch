#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ban_quyen.py — Key bản quyền AutoTone: cấp trước, kích hoạt sau.

    python ban_quyen.py               # xem giấy phép của máy này
    python ban_quyen.py --may         # in mã máy

KHÁC GÌ khoa.py
    `khoa.py` là HẠN DÙNG THỬ: một mốc hết hạn ghi cứng trong mã nguồn, chung
    cho mọi máy, gia hạn bằng mã gắn với (mã máy + một mốc trong danh sách app
    dò sẵn). Nó hợp để phát bản thử 72 giờ, KHÔNG hợp để bán.

        - Muốn cấp mã thì phải hỏi mã máy TRƯỚC. Bán hàng không chờ được vậy.
        - Hạn luôn tính từ mốc ghi cứng, nên "1 năm kể từ ngày mua" không diễn
          đạt được. Mốc gốc trôi qua rồi thì mã 30 ngày cũng đã hết hạn sẵn.
          Đã thử thật: sinh mã 365 ngày rồi nhập, app TỪ CHỐI — vì 365 không
          nằm trong danh sách (24, 48, 72, 168, 720) mà nó dò.

    Module này là GIẤY PHÉP BÁN ĐƯỢC:

        - Key mang sẵn SỐ NGÀY trong chính nó, không cần app đoán.
        - Cấp key KHÔNG cần biết máy nào. Máy đầu tiên nhập sẽ "ăn" key và
          khoá vào máy đó vĩnh viễn.
        - Hạn đếm TỪ LÚC KÍCH HOẠT, nên bán trước dùng sau vẫn đủ ngày.

HÌNH DẠNG KEY
    5 nhóm 5 ký tự: AT7K2-9MXQF-3VB8D-WRZ4H-N6PJS

        nhóm 1..4   phần thân: số hiệu key + số ngày, đã mã hoá
        nhóm 5      chữ ký HMAC cắt ngắn, chống bịa key

    Bảng chữ 32 ký tự bỏ I, O, 0, 1 — bốn ký tự hay đọc nhầm nhau qua điện
    thoại. Người dùng gõ 0 hay O, 1 hay I đều quy về một.

GIỚI HẠN — NÓI THẲNG
    Vẫn là khoá MỀM, cùng lý do đã ghi trong khoa.py: khoá bí mật nằm trong
    gói cài, ai dịch ngược được thì tự sinh key được. Không có máy chủ nên
    KHÔNG biết một key đã bị nhập ở máy khác hay chưa — chỉ biết key đó đã
    khoá vào CHÍNH máy này. Người cố tình chia key cho nhiều máy thì mỗi máy
    vẫn chạy. Chặn thật phải kiểm qua máy chủ, và ở đây cố ý không làm: máy
    studio hay mất mạng giữa job, khoá chặn nhầm người dùng hợp lệ thì hại
    hơn lợi.

    Cái nó chặn được, và chặn tốt: quên hạn, vặn đồng hồ lùi, chép thư mục
    giấy phép sang máy khác, sửa file bằng tay, và nhập lại một key đã dùng
    cho máy khác.
"""
from __future__ import annotations

import hashlib
import hmac
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

#[[ KHONG `sys.path.insert` o day.
#
#   Ban dau file nay co dong `sys.path.insert(0, thu muc cua no)` truoc khi
#   import khoa, cho chac an khi chay thang `python ban_quyen.py`. Dong do lam
#   PyInstaller SAP luc phan tich:
#
#       TypeError: attribute name must be string, not 'list'
#         ... modulegraph.py, visit_FunctionDef
#
#   Trinh phan tich cua PyInstaller doc tinh, no thay mot lenh sua sys.path o
#   muc module roi co dien giai — va vo cay AST cua chinh no. Build hong hoan
#   toan, ma thong bao khong nhac gi toi file nay.
#
#   Bo di thi khong mat gi: app import `ban_quyen` khi thu muc do da nam trong
#   duong tim module san roi. Chay thang file nay tu thu muc khac thi dung
#   `python -m ban_quyen`.
#]]
import khoa  # dùng lại mã máy, chữ ký, chống vặn đồng hồ

#[[ Khoa bi mat RIENG, khong dung chung voi khoa.py.
#
#   Hai he thong doc lap nhau: doi khoa nay thi cac ma gia han dung thu cu van
#   con hieu luc, va nguoc lai. Dung chung mot khoa thi mot lan doi la hong ca
#   hai, ma ta lai hay phai doi khoa nay hon (moi dot ban).
#]]
BI_MAT = b"AutoTone-SAY-Media-ban-quyen-v1"

#[[ Bo I, O, 0, 1 — xem ghi chu dau file. 32 ky tu de vua 5 bit/ky tu. ]]
BANG = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
DOI = {"0": "9", "O": "9", "1": "8", "I": "8"}

NHOM = 5
SO_NHOM = 4          # 8 ky tu than + 12 ky tu chu ky = 20 ky tu
PHIEN_BAN = 1        # 4 bit dau than — doi khi doi cach ma hoa

# Các gói bán — chỉ để tiện cấp key, app không phụ thuộc danh sách này.
GOI_BAN = {
    "thu": 7,
    "thang": 30,
    "quy": 90,
    "nam": 365,
    "vinh-vien": 36500,
}


# ── Mã hoá / giải mã key ────────────────────────────────────────────────────
def _b32(so: int, do_dai: int) -> str:
    ra = []
    for _ in range(do_dai):
        ra.append(BANG[so & 31])
        so >>= 5
    return "".join(reversed(ra))


def _so(s: str) -> int:
    n = 0
    for c in s:
        n = (n << 5) | BANG.index(c)
    return n


def sach(key: str) -> str:
    """Bỏ dấu gạch, đưa về hoa, quy các ký tự hay đọc nhầm về một."""
    ra = []
    for c in (key or "").upper():
        if not c.isalnum():
            continue
        ra.append(DOI.get(c, c))
    return "".join(ra)


def tao_key(so_hieu: int, so_ngay: int) -> str:
    """Sinh một key. CHỈ chạy ở máy người bán — xem cap_key.py.

    so_hieu: số thứ tự key, để phân biệt các key cùng số ngày (1..1_048_575).
    so_ngay: số ngày hiệu lực kể từ lúc kích hoạt (1..65535).
    """
    if not 1 <= so_hieu <= 0xFFFFF:
        raise ValueError("so_hieu phải trong 1..1048575")
    if not 1 <= so_ngay <= 0xFFFF:
        raise ValueError("so_ngay phải trong 1..65535")

    #[[ THAN 40 BIT = 4 bit phien ban + 20 bit so hieu + 16 bit so ngay.
    #
    #   Vua dung 8 ky tu (8 x 5 bit = 40 bit), khong du mot bit nao. Ban dau
    #   toi de than 20 ky tu cho "du cho", va moi key deu bat dau bang
    #   AAAAA-AAAAA — nhin nhu key hong, ma khach thi khong biet do la binh
    #   thuong. Chat vua khit thi moi ky tu deu mang tin, key nao cung khac
    #   nhau ngay tu dau.
    #
    #   4 bit phien ban de sau doi cach ma hoa ma van tu choi duoc key cu mot
    #   cach ro rang, thay vi giai ra so ngay bay ba.
    #]]
    than = (PHIEN_BAN << 36) | (so_hieu << 16) | so_ngay
    s_than = _b32(than, 8)
    ky = hmac.new(BI_MAT, s_than.encode("ascii"), hashlib.sha256).digest()
    #[[ Chu ky 12 ky tu = 60 bit. Doan mo 1 key can trung binh 2^59 lan thu,
    #   ma moi lan thu la mot lan go tay vao o nhap. ]]
    s_ky = "".join(BANG[b & 31] for b in ky[:12])
    s = s_than + s_ky
    return "-".join(s[i:i + NHOM] for i in range(0, len(s), NHOM))


def doc_key(key: str) -> tuple[int, int] | None:
    """Đọc key. -> (số hiệu, số ngày), hoặc None nếu key sai.

    Chỉ kiểm CHỮ KÝ, không đụng tới máy — vì lúc cấp key chưa biết máy nào.
    """
    s = sach(key)
    if len(s) != NHOM * SO_NHOM:
        return None
    if any(c not in BANG for c in s):
        return None
    s_than, s_ky = s[:8], s[8:]
    ky = hmac.new(BI_MAT, s_than.encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(s_ky, "".join(BANG[b & 31] for b in ky[:12])):
        return None
    than = _so(s_than)
    if (than >> 36) & 0xF != PHIEN_BAN:
        return None
    return (than >> 16) & 0xFFFFF, than & 0xFFFF


# ── Giấy phép trên máy này ──────────────────────────────────────────────────
def _doc() -> dict:
    d = khoa.doc_trang_thai()
    return {} if d.get("hong") else d


def kich_hoat(key: str) -> tuple[bool, str]:
    """Kích hoạt key trên MÁY NÀY. -> (được không, lời nhắn).

    Ghi lại mốc kích hoạt để đếm hạn từ đó. Khoá luôn vào mã máy: chép file
    giấy phép sang máy khác thì chữ ký sai, và khoa.doc_trang_thai() trả cờ
    hỏng.
    """
    if not sach(key):
        return False, "Chưa nhập key."
    doc = doc_key(key)
    if doc is None:
        return False, ("Key không hợp lệ. Kiểm tra lại từng ký tự — dễ nhầm "
                       "nhất là B với 8, S với 5.")
    so_hieu, so_ngay = doc

    d = _doc()
    cu = d.get("bq_key")
    bay_gio = datetime.now(timezone.utc)
    if cu and sach(cu) == sach(key):
        #[[ NHAP LAI DUNG KEY DA KICH HOAT: khong dat lai moc.
        #
        #   Neu dat lai thi nguoi dung cu nhap lai key moi lan gan het han la
        #   gia han vo han — key 30 ngay thanh key vinh vien. Da nghi toi
        #   chuyen "nhap lai de sua giay phep hong", nhung file hong thi
        #   doc_trang_thai() tra {} nen `cu` cung mat, khong roi vao nhanh nay.
        #]]
        het = _het_han(d)
        return True, (f"Key này đã kích hoạt trên máy này rồi — hạn đến "
                      f"{het.astimezone():%H:%M %d/%m/%Y}." if het else
                      "Key này đã kích hoạt trên máy này rồi.")

    khoa.ghi_trang_thai(
        bq_key=sach(key),
        bq_so_hieu=so_hieu,
        bq_ngay=so_ngay,
        bq_kich_hoat=bay_gio.isoformat(),
        moc_cao=bay_gio.isoformat(),
    )
    het = bay_gio + timedelta(days=so_ngay)
    return True, (f"Đã kích hoạt. Giấy phép {_ten_goi(so_ngay)} — hạn đến "
                  f"{het.astimezone():%H:%M %d/%m/%Y}.")


def _ten_goi(so_ngay: int) -> str:
    for ten, n in GOI_BAN.items():
        if n == so_ngay:
            return {"thu": "dùng thử 7 ngày", "thang": "1 tháng",
                    "quy": "3 tháng", "nam": "1 năm",
                    "vinh-vien": "vĩnh viễn"}.get(ten, f"{so_ngay} ngày")
    return f"{so_ngay} ngày"


def _het_han(d: dict) -> datetime | None:
    try:
        bd = datetime.fromisoformat(d["bq_kich_hoat"])
    except (KeyError, ValueError, TypeError):
        return None
    try:
        n = int(d.get("bq_ngay") or 0)
    except (TypeError, ValueError):
        return None
    return bd + timedelta(days=n) if n else None


def kiem() -> dict:
    """Trạng thái giấy phép lúc này.

    -> {"co_phep": bool, "ly_do": str, "con_lai": timedelta|None,
        "het_han": datetime|None, "may": str, "goi": str}

    `co_phep=False` nghĩa là KHÔNG được chạy việc mới. Xem việc cũ thì vẫn cho
    — quyết định đó nằm ở giao diện, không nằm ở đây.
    """
    may = khoa.ma_may()
    ra = {"co_phep": False, "ly_do": "", "con_lai": None,
          "het_han": None, "may": may, "goi": ""}

    d = khoa.doc_trang_thai()
    if d.get("hong"):
        ra["ly_do"] = ("Giấy phép không khớp với máy này — file có thể đã bị "
                       "sửa, hoặc được chép từ máy khác sang. "
                       "Nhập lại key trên chính máy này.")
        return ra

    if not d.get("bq_key"):
        ra["ly_do"] = "Máy này chưa kích hoạt bản quyền."
        return ra

    het = _het_han(d)
    if het is None:
        ra["ly_do"] = "Giấy phép thiếu thông tin hạn. Nhập lại key."
        return ra

    ra["het_han"] = het
    ra["goi"] = _ten_goi(int(d.get("bq_ngay") or 0))
    bay_gio = datetime.now(timezone.utc)

    #[[ CHONG VAN DONG HO LUI — dung lai moc_cao cua khoa.py.
    #
    #   Khong co cai nay thi ke het han chi can chinh lich may lui lai la dung
    #   tiep vo han, khong can biet gi ve ma nguon.
    #]]
    try:
        cao = datetime.fromisoformat(d["moc_cao"]) if d.get("moc_cao") else None
    except (ValueError, TypeError):
        cao = None
    if cao and bay_gio < cao - khoa.DUNG_SAI_DONG_HO:
        ra["ly_do"] = (f"Đồng hồ máy đang chạy lùi so với lần dùng gần nhất "
                       f"({cao.astimezone():%d/%m %H:%M}). "
                       f"Chỉnh lại đồng hồ cho đúng rồi mở lại.")
        return ra
    if cao is None or bay_gio > cao:
        khoa.ghi_trang_thai(moc_cao=bay_gio.isoformat())

    if bay_gio >= het:
        ra["ly_do"] = (f"Giấy phép đã hết hạn lúc "
                       f"{het.astimezone():%H:%M %d/%m/%Y}.")
        return ra

    ra.update(co_phep=True, con_lai=het - bay_gio)
    return ra


def mo_ta_con_lai(td) -> str:
    """Đổi khoảng thời gian còn lại thành chữ đọc được."""
    if td is None:
        return "—"
    g = int(td.total_seconds())
    if g <= 0:
        return "đã hết hạn"
    ngay, g = divmod(g, 86400)
    gio = g // 3600
    if ngay >= 365:
        return f"{ngay // 365} năm {(ngay % 365) // 30} tháng"
    if ngay >= 60:
        return f"{ngay // 30} tháng {ngay % 30} ngày"
    if ngay:
        return f"{ngay} ngày {gio} giờ"
    if gio:
        return f"{gio} giờ {(g % 3600) // 60} phút"
    return f"{g // 60} phút"


def main(argv=None) -> int:
    import argparse
    for _l in (sys.stdout, sys.stderr):
        try:
            _l.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description="Giay phep AutoTone.")
    ap.add_argument("--may", action="store_true", help="Chi in ma may")
    ap.add_argument("--kich-hoat", metavar="KEY", help="Kich hoat key tren may nay")
    a = ap.parse_args(argv)

    if a.may:
        print(khoa.ma_may())
        return 0
    if a.kich_hoat:
        ok, nhan = kich_hoat(a.kich_hoat)
        print(("  " if ok else "  [!] ") + nhan)
        return 0 if ok else 1

    k = kiem()
    print()
    print(f"  Máy      : {k['may']}")
    if k["co_phep"]:
        print(f"  Giấy phép: {k['goi']}")
        print(f"  Hạn đến  : {k['het_han'].astimezone():%H:%M %d/%m/%Y}")
        print(f"  Còn lại  : {mo_ta_con_lai(k['con_lai'])}")
    else:
        print(f"  Giấy phép: CHƯA CÓ / KHÔNG HỢP LỆ")
        print(f"  Lý do    : {k['ly_do']}")
    print()
    return 0 if k["co_phep"] else 1


if __name__ == "__main__":
    sys.exit(main())
