#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tin_dung.py — Credit theo ảnh + một key dùng MỘT máy tại một thời điểm (13/10).

User 13/10: "cấp 1 key cho 1 máy đang gặp vấn đề với người dùng 2 thiết bị muốn
linh động... làm cơ chế tính credit của ảnh. Key 1 năm là 500.000 credit. 1
credit = 1 ảnh đã bấm phân tích. Ảnh đã phân tích và trừ credit rồi thì lần
bấm phân tích sau không trừ nữa. Như xuất ảnh của Evoto." Rồi: "1 key chỉ dùng
được 1 máy 1 thời điểm... máy khác cũng vào tool thì hiện cảnh báo, chọn tiếp
tục sẽ đẩy thiết bị đang dùng kia ra." Mất mạng: cho ứng trước 2.000 ảnh.

MÁY CHỦ là nơi giữ số thật (Worker `autotone-key`, D1 — repo KeyActiveAutoTone,
src/credit.js): số dư, ảnh nào đã trừ, máy nào đang giữ phiên. Module này chỉ:
    ma_anh()      mã nội dung một ảnh (không phụ thuộc tên / thư mục / máy)
    vao_phien()   xin dùng key trên máy này (hoặc chiếm từ máy khác)
    nhip()        báo còn sống 5 phút/lần, biết mình bị đẩy ra
    roi()         nhả phiên lúc đóng app
    tru(ids)      trừ credit cho một mẻ ảnh sắp phân tích
    dong_bo_ung() trừ bù ảnh đã phân tích lúc mất mạng

Mọi hàm gọi mạng đều CHẶN tới 8 giây (ban_quyen.CHO_MANG) — chỉ gọi ở luồng nền.

TẮT (chạy như trước khi có credit) khi: chưa có key trên máy, AUTOTONE_CREDIT=0,
hoặc máy chủ chưa có cửa credit (Worker cũ trả 404 / chưa tạo D1 trả 503). Vì
vậy app mới ra trước khi Worker được cập nhật vẫn chạy bình thường.

GIỚI HẠN — như ban_quyen.py đã nói: chặn ở app là MỀM (mã nguồn công khai).
Số credit và phiên trên máy chủ mới là thật; ai sửa app để khỏi gọi tru() thì
phân tích được mà không bị trừ, nhưng không lấy được credit của người khác.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import ban_quyen as bq
import duong_dan as dd
import khoa

#[[ Ung truoc toi da 2.000 anh MOI khi mat mang (user chot 13/10). Anh da tru
#   tu truoc (so cai cuc bo biet) thi phan tich lai khong tinh vao han nay. ]]
UNG_TRUOC_TOI_DA = 2000
NHIP_GIAY = 300           # 5 phút một nhịp; máy chủ coi im > 15 phút là đã rời
ME_TOI_DA = 2000          # mỗi lần gọi /credit/tru (máy chủ nhận tới 5.000)
KHOI = 64 * 1024          # ma_anh đọc 64 KiB đầu + 64 KiB giữa
#[[ May chu chua co cua credit (Worker cu / chua tao D1): thu lai sau 6 gio,
#   khong goi moi lan bam Phan tich cho moi. ]]
THU_LAI_MAY_CHU_CU = 6 * 3600

_KHOA = threading.RLock()


# ── Mã ảnh ──────────────────────────────────────────────────────────────────
def ma_anh(path) -> str:
    """Mã nội dung của một ảnh — để biết "ảnh này đã trừ credit chưa".

    #[[ VI SAO MA NOI DUNG, KHONG PHAI DUONG DAN
    #
    #   Cung mot anh hay doi cho: doi ten thu muc, chep sang thu muc moi de
    #   chay lai (G:\\1009 -> G:\\Test1009, 3/10), mang sang may thu hai. Khoa
    #   theo duong dan / mtime (nhu kho ket qua do) thi moi lan nhu vay la tru
    #   lai. RAW doc quyen (ARW, NEF, CR3...) Lightroom KHONG BAO GIO ghi vao —
    #   no ghi .xmp hoac catalog — nen byte cua file la bat bien.
    #
    #   64 KiB dau chua TIFF header + EXIF + MakerNote (gio chup, so may...),
    #   64 KiB giua nam trong du lieu cam bien. Hai anh chup lien nhau (burst,
    #   cung giay, ARW khong nen cung co file) van khac nhau o du lieu cam bien.
    #   Doc 128 KiB/anh — khong dang ke canh read_raw (quet toi 16 MB/anh).
    #
    #   DNG thi KHAC: Lightroom co the ghi metadata vao chinh file DNG (bat
    #   "Automatically write changes into XMP"), lam doi byte. DNG co san the
    #   RawDataUniqueID (0xC65D) — ma cua du lieu raw, khong doi khi metadata
    #   doi — nen dung no; thieu thi lui ve ma noi dung.
    #]]
    """
    p = Path(path)
    if p.suffix.lower() == ".dng":
        try:
            import autotone as at
            uid = at.doc_the(str(p)).get("raw_uid")
            if uid:
                return "u" + str(uid).lower()
        except Exception:                                    # noqa: BLE001
            pass
    co = p.stat().st_size
    with open(p, "rb") as fh:
        dau = fh.read(KHOI)
        giua = b""
        if co > 2 * KHOI:
            fh.seek(co // 2 - KHOI // 2)
            giua = fh.read(KHOI)
    h = hashlib.sha256(b"AutoTone-anh-v1\0" + str(co).encode() + b"\0" + dau + giua)
    return h.hexdigest()[:32]


def ma_nhieu(paths, luong: int = 8) -> list:
    """ma_anh cho cả mẻ, song song (đọc đĩa là chính). Ảnh đọc hỏng -> None."""
    def mot(p):
        try:
            return ma_anh(p)
        except OSError:
            return None
    ds = list(paths)
    if len(ds) <= 2:
        return [mot(p) for p in ds]
    with ThreadPoolExecutor(max_workers=max(1, min(luong, len(ds)))) as ex:
        return list(ex.map(mot, ds))


# ── Trạng thái trên máy này ─────────────────────────────────────────────────
def _thu_muc() -> Path:
    return dd.goc_du_lieu() / "credit"


def _file_phien() -> Path:
    return _thu_muc() / "phien.json"


def _doc_phien() -> dict:
    try:
        d = json.loads(_file_phien().read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _ghi_phien(**kw) -> dict:
    with _KHOA:
        d = _doc_phien()
        d.update(kw)
        try:
            _thu_muc().mkdir(parents=True, exist_ok=True)
            dd.ghi_ben(_file_phien(), json.dumps(d, ensure_ascii=False, indent=1))
        except OSError:
            pass
        return d


def _bay_gio() -> str:
    return datetime.now(timezone.utc).isoformat()


def key_hien() -> str | None:
    d = khoa.doc_trang_thai()
    if d.get("hong"):
        return None
    k = d.get("bq_key")
    return bq.sach(k) if k else None


def ten_may() -> str:
    try:
        return (platform.node() or "").strip()[:64] or khoa.ma_may()
    except Exception:                                        # noqa: BLE001
        return "?"


def bat() -> bool:
    """Credit có đang áp cho máy này không."""
    if (os.environ.get("AUTOTONE_CREDIT") or "").strip() == "0":
        return False
    k = key_hien()
    if not k:
        return False
    d = _doc_phien()
    if d.get("key") and d.get("key") != k:
        #[[ Doi key (gia han, nhap key khac): phien cu khong con gia tri. ]]
        _ghi_phien(key=k, phien=None, tt="", khac=None, credit=None,
                   may_chu_cu=None)
        return True
    cu = d.get("may_chu_cu")
    if cu and time.time() - float(cu) < THU_LAI_MAY_CHU_CU:
        return False
    return True


def trang_thai() -> dict:
    """Trạng thái đã lưu (KHÔNG gọi mạng) — cho giao diện vẽ nhãn."""
    d = _doc_phien()
    d["ung"] = SoCai().so_ung() if bat() else 0
    d["bat"] = bat()
    return d


# ── Sổ cái cục bộ ───────────────────────────────────────────────────────────
class SoCai:
    """Ảnh đã trừ (máy chủ xác nhận) + hàng ứng trước lúc mất mạng.

    #[[ Chi de LAM VIEC KHI MAT MANG: biet anh nao phan tich lai la mien phi,
    #   va con ung truoc duoc bao nhieu. Khi co mang thi may chu quyet — so cai
    #   nay khong bao gio thay may chu tra loi "da tru chua". SQLite vi toi
    #   500.000 ma/nam; tep JSON se phai doc-ghi lai ca khoi moi me. ]]
    """

    def __init__(self, duong: Path | None = None):
        self.duong = Path(duong) if duong else _thu_muc() / "so_cai.sqlite"

    def _ket_noi(self):
        self.duong.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(str(self.duong), timeout=10)
        c.execute("CREATE TABLE IF NOT EXISTS da_tru (key TEXT, id TEXT, "
                  "PRIMARY KEY (key, id)) WITHOUT ROWID")
        c.execute("CREATE TABLE IF NOT EXISTS ung (key TEXT, id TEXT, luc REAL, "
                  "PRIMARY KEY (key, id)) WITHOUT ROWID")
        return c

    def da_co(self, key: str, ids) -> set:
        ids = list(ids)
        if not ids:
            return set()
        with _KHOA:
            c = self._ket_noi()
            try:
                ra = set()
                for i in range(0, len(ids), 500):
                    phan = ids[i:i + 500]
                    q = ",".join("?" * len(phan))
                    for bang in ("da_tru", "ung"):
                        ra.update(r[0] for r in c.execute(
                            f"SELECT id FROM {bang} WHERE key = ? AND id IN ({q})",
                            [key, *phan]))
                return ra
            finally:
                c.close()

    def them(self, key: str, ids) -> None:
        with _KHOA:
            c = self._ket_noi()
            try:
                c.executemany("INSERT OR IGNORE INTO da_tru (key, id) VALUES (?, ?)",
                              [(key, i) for i in ids])
                c.commit()
            finally:
                c.close()

    def them_ung(self, key: str, ids) -> None:
        with _KHOA:
            c = self._ket_noi()
            try:
                t = time.time()
                c.executemany("INSERT OR IGNORE INTO ung (key, id, luc) VALUES (?, ?, ?)",
                              [(key, i, t) for i in ids])
                c.commit()
            finally:
                c.close()

    def ds_ung(self, key: str | None = None) -> list:
        with _KHOA:
            c = self._ket_noi()
            try:
                if key:
                    return [tuple(r) for r in c.execute(
                        "SELECT key, id FROM ung WHERE key = ? ORDER BY luc", (key,))]
                return [tuple(r) for r in c.execute("SELECT key, id FROM ung ORDER BY luc")]
            finally:
                c.close()

    def so_ung(self) -> int:
        with _KHOA:
            c = self._ket_noi()
            try:
                return int(c.execute("SELECT COUNT(*) FROM ung").fetchone()[0])
            finally:
                c.close()

    def xong_ung(self, key: str, ids) -> None:
        """Ảnh ứng trước đã trừ bù xong: chuyển sang da_tru."""
        with _KHOA:
            c = self._ket_noi()
            try:
                c.executemany("DELETE FROM ung WHERE key = ? AND id = ?",
                              [(key, i) for i in ids])
                c.executemany("INSERT OR IGNORE INTO da_tru (key, id) VALUES (?, ?)",
                              [(key, i) for i in ids])
                c.commit()
            finally:
                c.close()


# ── Gọi máy chủ ─────────────────────────────────────────────────────────────
def _goi(duong: str, than: dict):
    """bq._goi kèm api 2 + key + mã máy. -> (mã, dữ liệu) | None (mất mạng)."""
    d = dict(than)
    d.setdefault("api", 2)
    d.setdefault("may", khoa.ma_may())
    return bq._goi(duong, d)


def _may_chu_cu(ma: int, kq: dict) -> bool:
    """Worker chưa có cửa credit: 404 khong_co_cua_nay (Worker cũ) hoặc 503 chưa tạo D1."""
    ly = (kq or {}).get("ly_do", "")
    return (ma == 404 and ly == "khong_co_cua_nay") or (ma == 503 and ly == "chua_co_credit")


def _danh_dau_may_chu_cu() -> dict:
    _ghi_phien(may_chu_cu=time.time())
    return {"tt": "tat"}


def _luu_credit(cr) -> None:
    if isinstance(cr, dict) and "con_lai" in cr:
        _ghi_phien(credit={k: int(cr.get(k) or 0) for k in ("tong", "da_dung", "con_lai")},
                   luc_credit=_bay_gio())


def luu_tom_tat(kq: dict) -> None:
    """Lưu phần credit / máy đang dùng / đếm theo máy mà /kiem (api 2) trả kèm."""
    if not isinstance(kq, dict) or "credit" not in kq:
        return
    _luu_credit(kq.get("credit"))
    _ghi_phien(dem_may=kq.get("dem_may") or [], dang_dung=kq.get("dang_dung"),
               luc_tom_tat=_bay_gio())


def lay_tom_tat() -> dict:
    """Gọi /kiem (api 2) lấy số mới nhất cho bảng "Credit & thiết bị". Luồng nền.

    -> {"ok": True, "credit", "dang_dung", "dem_may"} hoặc {"ok": False, "nhan"}.
    """
    key = key_hien()
    if not key:
        return {"ok": False, "nhan": "Máy này chưa kích hoạt bản quyền."}
    tl = _goi("/kiem", {"key": key})
    if tl is None:
        d = _doc_phien()
        return {"ok": False, "mat_mang": True, "nhan": "Không nối được máy chủ.",
                "credit": d.get("credit"), "dem_may": d.get("dem_may") or [],
                "dang_dung": d.get("dang_dung")}
    ma, kq = tl
    if not kq.get("ok"):
        return {"ok": False, **_loi(kq, ma)}
    luu_tom_tat(kq)
    return {"ok": True, "credit": kq.get("credit"), "dang_dung": kq.get("dang_dung"),
            "dem_may": kq.get("dem_may") or [], "het_han": kq.get("het_han")}


def _loi(kq: dict, ma) -> dict:
    ly = (kq or {}).get("ly_do", "")
    return {"tt": "loi", "ly_do": ly,
            "nhan": bq.LY_DO_VIET.get(ly, f"Máy chủ từ chối ({ly or ma}).")}


# ── Phiên ───────────────────────────────────────────────────────────────────
def vao_phien(chiem: bool = False) -> dict:
    """Xin dùng key trên máy này.

    -> {"tt": "dung"}                       đã giữ phiên
       {"tt": "xung_dot", "ten_may", "cach_giay"}   máy khác đang dùng
       {"tt": "mat_mang"} / {"tt": "tat"} / {"tt": "loi", "nhan"}
    """
    if not bat():
        return {"tt": "tat"}
    key = key_hien()
    d = khoa.doc_trang_thai()
    than = {"key": key, "ten_may": ten_may(), "chiem": bool(chiem)}
    if d.get("bq_key_cu"):
        than["key_cu"] = d["bq_key_cu"]
    tl = _goi("/phien/vao", than)
    if tl is None:
        return {"tt": "mat_mang"}
    ma, kq = tl
    if kq.get("ok"):
        _ghi_phien(key=key, phien=kq.get("phien"), tt="dung", khac=None,
                   luc_phien=_bay_gio(), may_chu_cu=None)
        _luu_credit(kq.get("credit"))
        dong_bo_ung()
        return {"tt": "dung", "credit": _doc_phien().get("credit")}
    if _may_chu_cu(ma, kq):
        return _danh_dau_may_chu_cu()
    if kq.get("ly_do") == "dang_dung_may_khac":
        khac = {"ten_may": kq.get("ten_may") or "", "cach_giay": kq.get("cach_giay")}
        _ghi_phien(key=key, tt="xung_dot", khac=khac)
        return {"tt": "xung_dot", **khac}
    return _loi(kq, ma)


def nhip() -> dict:
    """Báo máy chủ "máy này còn dùng". Bị đẩy ra thì biết ngay ở đây."""
    if not bat():
        return {"tt": "tat"}
    d = _doc_phien()
    if d.get("tt") == "bi_day_ra":
        return {"tt": "bi_day_ra", **(d.get("khac") or {})}
    if not d.get("phien"):
        return vao_phien(chiem=False)
    tl = _goi("/phien/nhip", {"key": key_hien(), "phien": d["phien"]})
    if tl is None:
        return {"tt": "mat_mang"}
    ma, kq = tl
    if kq.get("ok"):
        _ghi_phien(tt="dung", luc_phien=_bay_gio())
        _luu_credit(kq.get("credit"))
        #[[ Tra so du SAU khi tru bu anh ung truoc — giao dien hien dung so. ]]
        dong_bo_ung()
        return {"tt": "dung", "credit": _doc_phien().get("credit")}
    if _may_chu_cu(ma, kq):
        return _danh_dau_may_chu_cu()
    ly = kq.get("ly_do")
    if ly == "het_phien":
        #[[ Phien da het ma khong ai chiem (vd. may chu duoc don): vao lai lang
        #   le — khong co may nao de "day ra" ca. ]]
        return vao_phien(chiem=False)
    if ly == "bi_day_ra":
        khac = {"ten_may": kq.get("ten_may") or "", "luc": kq.get("luc")}
        _ghi_phien(tt="bi_day_ra", phien=None, khac=khac)
        return {"tt": "bi_day_ra", **khac}
    return _loi(kq, ma)


def roi() -> None:
    """Nhả phiên (đóng app) để máy khác mở không bị hỏi. Lỗi gì cũng bỏ qua."""
    try:
        if not bat():
            return
        d = _doc_phien()
        if d.get("phien") and d.get("tt") == "dung":
            _goi("/phien/roi", {"key": key_hien(), "phien": d["phien"]})
            _ghi_phien(phien=None, tt="")
    except Exception:                                        # noqa: BLE001
        pass


def roi_nhanh(cho: float = 2.0) -> None:
    """roi() ở luồng riêng, chờ tối đa `cho` giây — đóng app không bị treo vì mạng."""
    t = threading.Thread(target=roi, daemon=True, name="credit_roi")
    t.start()
    t.join(cho)


def phien_ok(tu_kiem: bool = True) -> tuple[bool, str]:
    """Cho tiến trình KHÔNG có giao diện (trạm retouch): máy này còn giữ phiên không.

    Lần xác nhận cuối quá một nhịp thì gọi nhip(). Mất mạng -> cho chạy (ân hạn
    bản quyền vẫn do ban_quyen.kiem lo).
    """
    if not bat():
        return True, ""
    d = _doc_phien()
    if d.get("tt") == "bi_day_ra":
        return False, _cau_bi_day(d.get("khac") or {})
    try:
        luc = datetime.fromisoformat(d.get("luc_phien") or "")
        moi = (datetime.now(timezone.utc) - luc).total_seconds() < NHIP_GIAY
    except (TypeError, ValueError):
        moi = False
    if moi and d.get("tt") == "dung":
        return True, ""
    if not tu_kiem:
        return True, ""
    kq = nhip()
    if kq["tt"] == "bi_day_ra":
        return False, _cau_bi_day(kq)
    if kq["tt"] == "xung_dot":
        return False, (f"Key đang được dùng trên máy «{kq.get('ten_may') or '?'}». "
                       f"Mở AutoTone trên máy này để chuyển key về đây.")
    return True, ""


def _cau_bi_day(khac: dict) -> str:
    return (f"Key này vừa được đăng nhập trên máy «{khac.get('ten_may') or '?'}», "
            f"máy này đã bị đẩy ra.")


# ── Trừ credit ──────────────────────────────────────────────────────────────
def tru(ids) -> dict:
    """Trừ credit cho một mẻ ảnh SẮP phân tích (ids = ma_anh từng ảnh).

    -> {"tt": "ok", "moi", "cu", "credit"}
       {"tt": "het_credit", "can", "con_lai", "cu_idx", "credit"}   không trừ ảnh nào
           của phần chưa trừ — cu_idx = vị trí các ảnh ĐÃ trừ (phân tích lại miễn phí)
       {"tt": "ung_truoc", "moi", "ung"}     mất mạng, đã ghi vào hàng ứng trước
       {"tt": "het_ung_truoc", "ung", "can"} mất mạng và vượt 2.000 ảnh ứng trước
       {"tt": "bi_day_ra" | "xung_dot", "ten_may", ...}
       {"tt": "tat"} / {"tt": "loi", "nhan"}
    """
    ids = [str(i) for i in ids]
    if not bat() or not ids:
        return {"tt": "tat"} if not bat() else {"tt": "ok", "moi": 0, "cu": 0}
    key = key_hien()
    d = _doc_phien()
    if d.get("tt") == "bi_day_ra":
        return {"tt": "bi_day_ra", **(d.get("khac") or {})}
    if not d.get("phien"):
        v = vao_phien(chiem=False)
        if v["tt"] in ("xung_dot", "tat", "loi"):
            return v
        if v["tt"] == "mat_mang":
            return _tru_mat_mang(key, ids, list(range(len(ids))))
        d = _doc_phien()

    so = SoCai()
    moi = cu = 0
    cu_idx: list = []
    credit = None
    for dau in range(0, len(ids), ME_TOI_DA):
        me = ids[dau:dau + ME_TOI_DA]
        than = {"key": key, "phien": d.get("phien"), "ids": me, "ten_may": ten_may()}
        tl = _goi("/credit/tru", than)
        if tl is not None and tl[1].get("ly_do") == "het_phien":
            v = vao_phien(chiem=False)
            if v["tt"] != "dung":
                return v if v["tt"] != "mat_mang" else _tru_mat_mang(
                    key, ids[dau:], list(range(dau, len(ids))), cu_idx, moi)
            d = _doc_phien()
            than["phien"] = d.get("phien")
            tl = _goi("/credit/tru", than)
        if tl is None:
            #[[ Mat mang giua chung: phan da tru van tinh, phan con lai vao
            #   hang ung truoc. ]]
            return _tru_mat_mang(key, ids[dau:], list(range(dau, len(ids))), cu_idx, moi)
        ma, kq = tl
        if kq.get("ok"):
            so.them(key, me)
            moi += int(kq.get("moi") or 0)
            cu += int(kq.get("cu") or 0)
            cu_idx += [dau + int(i) for i in kq.get("cu_idx") or []]
            credit = kq.get("credit")
            _luu_credit(credit)
            continue
        if _may_chu_cu(ma, kq):
            return _danh_dau_may_chu_cu()
        ly = kq.get("ly_do")
        if ly == "het_credit":
            _luu_credit(kq.get("credit"))
            #[[ Cac me truoc DA tru xong — tinh chung la "da tru" cho giao dien
            #   de nghi: phan tich lai phan do mien phi, chi can credit cho
            #   phan moi cua me nay va cac me sau. ]]
            con = [i for i in range(dau + len(me), len(ids))]
            return {"tt": "het_credit",
                    "can": int(kq.get("can") or 0) + len(con),
                    "con_lai": int(kq.get("con_lai") or 0),
                    "cu_idx": list(range(dau)) + [dau + int(i) for i in kq.get("cu_idx") or []],
                    "credit": kq.get("credit")}
        if ly == "bi_day_ra":
            khac = {"ten_may": kq.get("ten_may") or "", "luc": kq.get("luc")}
            _ghi_phien(tt="bi_day_ra", phien=None, khac=khac)
            return {"tt": "bi_day_ra", **khac}
        return _loi(kq, ma)
    return {"tt": "ok", "moi": moi, "cu": cu, "cu_idx": cu_idx, "credit": credit}


def _tru_mat_mang(key, ids, vi_tri, cu_idx=None, moi_da=0) -> dict:
    """Mất mạng: ảnh đã trừ (sổ cái biết) thì miễn phí, ảnh mới vào hàng ứng trước."""
    so = SoCai()
    da = so.da_co(key, ids)
    moi_ids = []
    thay = set()
    for i in ids:
        if i in da or i in thay:
            continue
        thay.add(i)
        moi_ids.append(i)
    ung = so.so_ung()
    if ung + len(moi_ids) > UNG_TRUOC_TOI_DA:
        return {"tt": "het_ung_truoc", "ung": ung, "can": len(moi_ids),
                "con_ung": max(0, UNG_TRUOC_TOI_DA - ung)}
    #[[ Biet so du lan cuoi thi khong ung qua so du do — ung truoc la "tru
    #   sau", khong phai "phan tich khong tinh". ]]
    cr = (_doc_phien().get("credit") or {})
    if "con_lai" in cr and ung + len(moi_ids) > int(cr["con_lai"]) and moi_ids:
        return {"tt": "het_credit", "can": len(moi_ids),
                "con_lai": max(0, int(cr["con_lai"]) - ung),
                "cu_idx": [vi_tri[k] for k, i in enumerate(ids) if i in da] + list(cu_idx or []),
                "credit": cr, "mat_mang": True}
    so.them_ung(key, moi_ids)
    return {"tt": "ung_truoc", "moi": len(moi_ids) + moi_da, "ung": ung + len(moi_ids)}


def dong_bo_ung() -> int:
    """Trừ bù các ảnh đã phân tích lúc mất mạng. -> số ảnh đã đồng bộ."""
    if not bat():
        return 0
    so = SoCai()
    ds = so.ds_ung()
    if not ds:
        return 0
    xong = 0
    theo_key: dict = {}
    for k, i in ds:
        theo_key.setdefault(k, []).append(i)
    for k, ids in theo_key.items():
        for dau in range(0, len(ids), ME_TOI_DA):
            me = ids[dau:dau + ME_TOI_DA]
            tl = _goi("/credit/tru", {"key": k, "ids": me, "ung_truoc": True,
                                      "ten_may": ten_may()})
            if tl is None:
                return xong
            ma, kq = tl
            if kq.get("ok"):
                so.xong_ung(k, me)
                xong += len(me)
                if k == key_hien():
                    _luu_credit(kq.get("credit"))
            elif kq.get("ly_do") in ("key_sai", "da_thu_hoi", "het_han", "chua_kich_hoat"):
                #[[ Key cu da thu hoi / het han: khong con ai de tru — bo, khong
                #   thi hang ung truoc ket mai va chan may nay. ]]
                so.xong_ung(k, me)
            else:
                return xong
    return xong


# ── Chữ cho giao diện ───────────────────────────────────────────────────────
def so_chu(n) -> str:
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "?"


def tom_tat() -> str:
    """"487.230 credit" / "487.230 credit · ứng trước 340/2.000" / "" khi tắt."""
    t = trang_thai()
    if not t.get("bat"):
        return ""
    cr = t.get("credit") or {}
    phan = []
    if "con_lai" in cr:
        phan.append(f"{so_chu(cr['con_lai'])} credit")
    if t.get("ung"):
        phan.append(f"ứng trước {so_chu(t['ung'])}/{so_chu(UNG_TRUOC_TOI_DA)}")
    return " · ".join(phan)


def cau_ket_qua(kq: dict, so_anh: int) -> str:
    """Một câu cho dòng trạng thái sau khi trừ."""
    tt = kq.get("tt")
    if tt == "ok":
        con = (kq.get("credit") or {}).get("con_lai")
        cu = int(kq.get("cu") or 0)
        cau = f"Trừ {so_chu(kq.get('moi', 0))} credit"
        if cu:
            cau += f" ({so_chu(cu)} ảnh đã trừ trước)"
        if con is not None:
            cau += f" · còn {so_chu(con)}"
        return cau
    if tt == "ung_truoc":
        return (f"Mất mạng — đã ứng trước {so_chu(kq.get('ung'))}/"
                f"{so_chu(UNG_TRUOC_TOI_DA)} ảnh, sẽ trừ khi có mạng")
    return ""


# ── Nhịp nền cho giao diện ──────────────────────────────────────────────────
class NhipPhien:
    """Luồng nền: vào phiên lúc mở app rồi 5 phút một nhịp.

    Báo cho giao diện qua `bao(kq)` (gọi từ luồng nền — giao diện tự chuyển về
    luồng chính, vd. đặt vào hàng đợi). Chỉ báo khi trạng thái ĐỔI, để nhịp
    đều đặn không vẽ lại gì.
    """

    def __init__(self, bao, nhip_giay: float = NHIP_GIAY):
        self.bao = bao
        self.nhip_giay = nhip_giay
        self._dung = threading.Event()
        self._danh_thuc = threading.Event()
        self._cu = None
        self.t = threading.Thread(target=self._chay, daemon=True, name="credit_nhip")

    def bat_dau(self):
        self.t.start()
        return self

    def dung(self):
        self._dung.set()
        self._danh_thuc.set()

    def ngay(self):
        """Nhịp ngay (sau khi người dùng bấm "Tiếp tục dùng ở máy này"...)."""
        self._danh_thuc.set()

    def _chay(self):
        lan_dau = True
        while not self._dung.is_set():
            try:
                kq = vao_phien(chiem=False) if lan_dau else nhip()
            except Exception as e:                           # noqa: BLE001
                kq = {"tt": "loi", "nhan": str(e)}
            lan_dau = False
            khoa_tt = (kq.get("tt"), (kq.get("credit") or {}).get("con_lai"))
            if khoa_tt != self._cu:
                self._cu = khoa_tt
                try:
                    self.bao(kq)
                except Exception:                            # noqa: BLE001
                    pass
            self._danh_thuc.wait(self.nhip_giay)
            self._danh_thuc.clear()
