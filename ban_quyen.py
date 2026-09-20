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

#[[ KHONG CO KHOA BI MAT TRONG FILE NAY — CO Y.
#
#   Ban dau khoa ky key nam ngay day. Nhung ma nguon app o tren mot kho
#   GitHub CONG KHAI (de tai nguyen retouch tai duoc), nen bat ky ai mo file
#   nay tren web cung lay duoc khoa, roi tu sinh key vo han — di vong qua ca
#   may chu, vi may chu chi kiem chu ky chu khong biet key nao do minh cap.
#
#   Khong can dich nguoc .exe, chi can bam vao file tren github.com.
#
#   Gio khoa CHI nam o hai noi, ca hai deu kin:
#       - kho bi mat cua Cloudflare (Worker doc de kiem chu ky)
#       - cap_key.py tren may nguoi ban (da chan o .gitignore va LOAI_TRU)
#
#   App khong con kiem chu ky nua: no gui key len may chu va nghe tra loi.
#   Khong mat tinh nang nao, vi kich hoat VON DA bat buoc co mang.
#]]

#[[ MAY CHU KEY — Cloudflare Worker + KV.
#
#   VI SAO CAN: ban offline khong biet mot key da bi nhap o may khac hay chua,
#   nen ai chia key cho 5 may thi ca 5 van chay. May chu ghi nhan key nao
#   thuoc may nao — cach DUY NHAT chan duoc chuyen do ma khong can crack.
#
#   VI SAO KHONG DAT TREN MAY CUA MINH: tunnel qua may ca nhan thi may tat,
#   mat dien hay rot mang la MOI khach bi chan cung luc. Worker chay tren ha
#   tang Cloudflare, khong phu thuoc mot may nao.
#]]
MAY_CHU = "https://autotone-key.keyactive.workers.dev"

#[[ NHIP KIEM LAI VA AN HAN — hai so quyet dinh app tu te hay pha viec.
#
#   Kich hoat lan dau BAT BUOC co mang: do la luc may chu chiem key cho may
#   nay, va la lan duy nhat chan duoc chia se key.
#
#   Sau do cu 7 ngay thu goi lai mot lan. Goi khong duoc thi VAN CHAY tiep
#   toi 30 ngay. Qua 30 ngay khong lien lac duoc moi nhac.
#
#   30 ngay khong phai so tuy tien: studio di chup xa, mang khach san chan
#   cong la, may de trong phong khong noi mang — deu la chuyen that. Mot cai
#   khoa chan nguoi dung hop le vi rot mang thi hai hon la loi, va do la ly do
#   khoa.py co y khong kiem qua may chu. O day kiem, nhung an han phai du dai
#   de khong bao gio chan nham nguoi dang lam viec.
#]]
NHIP_KIEM = timedelta(days=7)
AN_HAN = timedelta(days=30)
CHO_MANG = 8          # giay — het thi coi nhu khong co mang, KHONG phai loi

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


# ── Đọc key (chỉ hình dạng — chữ ký do máy chủ kiểm) ───────────────────────
def sach(key: str) -> str:
    """Bỏ dấu gạch, đưa về hoa, quy các ký tự hay đọc nhầm về một."""
    ra = []
    for c in (key or "").upper():
        if not c.isalnum():
            continue
        ra.append(DOI.get(c, c))
    return "".join(ra)


def dang_key(key: str) -> bool:
    """Chuỗi này CÓ DẠNG một key bản quyền không? KHÔNG kiểm chữ ký.

    App không giữ khoá bí mật nên không xác minh được chữ ký — việc đó máy chủ
    làm. Hàm này chỉ trả lời một câu hẹp hơn nhiều: người dùng vừa gõ key bản
    quyền hay mã gia hạn dùng thử?

    Đủ cho việc đó, vì hai loại khác nhau ở độ dài và bảng chữ:
        key bản quyền    20 ký tự, toàn bộ nằm trong BANG
        mã gia hạn cũ    20 ký tự nhưng sinh từ base32 chuẩn, có thể lọt ký tự
                         ngoài BANG

    Đoán nhầm cũng không mất gì: app thử cả hai đường, cái nào nhận thì lấy.
    """
    t = sach(key)
    return len(t) == NHOM * SO_NHOM and all(c in BANG for c in t)


# ── Gọi máy chủ ─────────────────────────────────────────────────────────────
def _goi(duong: str, than: dict) -> tuple[int, dict] | None:
    """Gọi một cửa của máy chủ. -> (mã HTTP, dữ liệu), hoặc None nếu không nối được.

    Phân biệt rõ HAI chuyện, vì chúng dẫn tới hai xử lý trái ngược:

        None        = không nối được (mất mạng, máy chủ sập, tường lửa chặn)
                      -> KHÔNG được coi là vi phạm. Chạy tiếp trong ân hạn.
        (mã, dữ liệu) = máy chủ trả lời -> nghe theo nó, kể cả khi nó từ chối.
    """
    import json as _json
    import urllib.error
    import urllib.request
    try:
        req = urllib.request.Request(
            MAY_CHU.rstrip("/") + duong,
            data=_json.dumps(than).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "User-Agent": "AutoTone"},
            method="POST")
        with urllib.request.urlopen(req, timeout=CHO_MANG) as r:
            return r.status, _json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        #[[ 4xx/5xx VAN la may chu tra loi — doc lay ly do. Coi no la "mat
        #   mang" thi key da thu hoi se chay tiep het 30 ngay an han. ]]
        try:
            return e.code, _json.loads(e.read().decode("utf-8"))
        except Exception:                                    # noqa: BLE001
            return e.code, {}
    except Exception:                                        # noqa: BLE001
        return None


LY_DO_VIET = {
    "key_sai": "Key không hợp lệ. Kiểm tra lại từng ký tự.",
    "ma_may_sai": "Máy này không đọc được mã máy hợp lệ.",
    "da_thu_hoi": "Key này đã bị thu hồi. Liên hệ SAY Media.",
    "da_dung_may_khac": "Key này đã kích hoạt trên MỘT MÁY KHÁC rồi. "
                        "Mỗi key chỉ dùng cho một máy. Nếu anh vừa đổi máy, "
                        "báo SAY Media để mở khoá.",
    "sai_may": "Key này thuộc về một máy khác.",
    "chua_kich_hoat": "Key chưa được kích hoạt.",
    "het_han": "Giấy phép đã hết hạn.",
    "loi_may_chu": "Máy chủ đang trục trặc. Thử lại sau ít phút.",
}


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
    #[[ KHONG giai key o day nua — app khong giu khoa bi mat.
    #
    #   Chi chan truoc nhung chuoi RO RANG khong phai key (sai do dai, lot ky
    #   tu la) de khoi goi may chu mot cach vo ich. Con key dung dang ma chu
    #   ky sai thi may chu bat, va no tra ve "key_sai" — cung mot cau bao loi.
    #]]
    if not dang_key(key):
        return False, ("Key không hợp lệ. Kiểm tra lại từng ký tự — dễ nhầm "
                       "nhất là B với 8, S với 5.")

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

    #[[ KICH HOAT PHAI QUA MAY CHU — day la lan DUY NHAT chan duoc chia se key.
    #
    #   Cho kich hoat offline roi "dong bo sau" thi mot key van chay duoc tren
    #   bao nhieu may tuy y cho toi khi chung noi mang — tuc la mat han tac
    #   dung cua may chu. Nen o day mat mang la KHONG kich hoat duoc, va noi
    #   thang ly do thay vi bao mot loi chung chung.
    #]]
    tl = _goi("/kich-hoat", {"key": sach(key), "may": khoa.ma_may()})
    if tl is None:
        return False, ("Không nối được máy chủ để kích hoạt.\n\n"
                       "Lần kích hoạt đầu tiên cần mạng. Sau khi kích hoạt "
                       "xong thì dùng offline thoải mái.\n\n"
                       "Kiểm tra mạng rồi bấm Kích hoạt lại.")
    ma, d = tl
    if not d.get("ok"):
        ly = d.get("ly_do", "")
        nhan = LY_DO_VIET.get(ly, f"Máy chủ từ chối ({ly or ma}).")
        if ly == "da_dung_may_khac" and d.get("may_cu"):
            nhan += f"\n\nMáy đang giữ key: {d['may_cu']}"
        return False, nhan

    #[[ Lay han TU MAY CHU, khong tu tinh o may khach.
    #
    #   May chu la noi duy nhat biet key duoc kich hoat luc nao. Tinh o may
    #   khach thi van dong ho la doi duoc han — chinh thu ta dang chan. ]]
    #[[ so_ngay do MAY CHU noi — app khong tu giai duoc nua, va cung khong
    #   nen tu giai: may chu la noi duy nhat biet key do dang con hieu luc. ]]
    so_ngay = int(d.get("so_ngay") or 0)
    try:
        het = datetime.fromisoformat(d["het_han"].replace("Z", "+00:00"))
        bd = datetime.fromisoformat(d["kich_hoat"].replace("Z", "+00:00"))
    except (KeyError, ValueError, AttributeError):
        if not so_ngay:
            return False, ("Máy chủ trả lời thiếu thông tin hạn. "
                           "Thử lại sau ít phút.")
        het = bay_gio + timedelta(days=so_ngay)
        bd = bay_gio

    khoa.ghi_trang_thai(
        bq_key=sach(key),
        bq_ngay=so_ngay,
        bq_kich_hoat=bd.isoformat(),
        bq_het_han=het.isoformat(),
        bq_kiem_cuoi=bay_gio.isoformat(),
        moc_cao=bay_gio.isoformat(),
    )
    if d.get("lap_lai"):
        return True, (f"Key này đã kích hoạt trên máy này rồi — hạn đến "
                      f"{het.astimezone():%H:%M %d/%m/%Y}.")
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
    #[[ Han MAY CHU da chot thi uu tien — xem ghi chu trong kich_hoat(). ]]
    if d.get("bq_het_han"):
        try:
            return datetime.fromisoformat(d["bq_het_han"])
        except (ValueError, TypeError):
            pass
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
          "het_han": None, "may": may, "goi": "", "nhac": ""}

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

    #[[ KIEM DINH KY VOI MAY CHU — 7 ngay mot lan, an han 30 ngay.
    #
    #   Ba ket cuc, va chung PHAI khac nhau:
    #
    #     may chu noi OK        -> ghi moc, chay tiep
    #     may chu noi KHONG     -> dung ngay (key bi thu hoi / dung sai may)
    #     khong noi duoc may chu-> CHAY TIEP trong an han, chi nhac neu qua han
    #
    #   Gop hai truong hop cuoi lam mot la hong ca he thong: hoac key thu hoi
    #   van chay 30 ngay, hoac nguoi mat mang bi chan ngay. Nen _goi() tra
    #   None rieng cho "khong noi duoc".
    #]]
    try:
        kc = datetime.fromisoformat(d["bq_kiem_cuoi"]) if d.get("bq_kiem_cuoi") else None
    except (ValueError, TypeError):
        kc = None

    if kc is None or bay_gio - kc >= NHIP_KIEM:
        tl = _goi("/kiem", {"key": d.get("bq_key", ""), "may": may})
        if tl is not None:
            _ma, kq = tl
            if kq.get("ok"):
                khoa.ghi_trang_thai(bq_kiem_cuoi=bay_gio.isoformat())
                kc = bay_gio
            else:
                ly = kq.get("ly_do", "")
                ra["ly_do"] = LY_DO_VIET.get(
                    ly, f"Máy chủ không xác nhận giấy phép ({ly}).")
                return ra
        #[[ tl is None: khong noi duoc. Khong ghi moc, khong chan. De vong
        #   duoi xet xem da qua an han chua. ]]

    if kc is not None and bay_gio - kc > AN_HAN:
        ngay = (bay_gio - kc).days
        ra["ly_do"] = (
            f"Đã {ngay} ngày không kết nối được máy chủ để xác nhận giấy "
            f"phép.\n\nNối mạng rồi mở lại app — chỉ cần một lần là chạy "
            f"tiếp bình thường.")
        return ra

    ra.update(co_phep=True, con_lai=het - bay_gio)
    #[[ Bao cho giao dien biet dang trong an han, de no nhac nhe truoc khi
    #   het — nhac sau khi da bi chan thi qua muon. ]]
    if kc is not None:
        thieu = AN_HAN - (bay_gio - kc)
        if thieu.days <= 7:
            ra["nhac"] = (f"Chưa xác nhận được giấy phép với máy chủ. "
                          f"Còn {thieu.days} ngày nữa cần nối mạng một lần.")
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
