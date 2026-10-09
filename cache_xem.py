#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cache_xem.py — Bộ nhớ đệm ẢNH XEM TRƯỚC retouch trên đĩa (9/10).

VÌ SAO CÓ FILE NÀY
    Xem trước của màn Retouch do engine thường trú tính (xem_truoc.MayXem) —
    mỗi lần ~1–3 giây trên card, và KHÔNG tính được trong lúc engine đang chạy
    cả mẻ (lệnh xếp hàng tới khi mẻ xong). User 9/10: "trong quá trình xuất
    không load được preview; tạo bộ nhớ Cache để lưu các Preview, khi xuất
    cũng có thể xem các ảnh khác; cho sửa dung lượng; quá thì tự xoá cũ nhất".

    Nên: ảnh xem trước nào đã tính xong thì ghi xuống đây (JPEG 1400 px cạnh
    dài, ~0,3–0,5 MB/tấm). Mở lại thư mục, hay đang chạy mẻ, bấm vào tấm đã
    từng xem là hiện NGAY, không qua engine.

KHOÁ = những gì làm ảnh xem trước KHÁC đi
    đường dẫn + mtime + cỡ file ảnh vào · bộ mức kéo (phẳng, sắp theo tên) ·
    bản saytool. Đổi bất kỳ thứ nào là một tấm khác — không bao giờ hiện bản
    xem trước của mức cũ cho mức mới.

DỌN THEO LRU
    Chỉ mục giữ lần xem cuối (`luc`) của từng tấm; vượt giới hạn thì xoá tấm
    LÂU KHÔNG XEM nhất trước, cho tới khi đủ chỗ. Giới hạn đặt ở hộp thoại
    Xuất (xuat_ui, mặc định 2 GB) — xem gioi_han_mb().

AN TOÀN
    Mọi lỗi đĩa chỉ làm MẤT cache, không bao giờ làm hỏng xem trước: lay()
    trả None, cat() lặng lẽ bỏ. Ghi .part rồi đổi tên. Có khoá luồng vì kết
    quả xem trước về ở luồng chính còn mẻ chạy có thể gọi từ luồng nền.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import duong_dan as dd

TEN_THU_MUC = "xem_truoc_cache"
TEN_CHI_MUC = "chi_muc.json"
MB_MAC_DINH = 2048            # 2 GB — ~4.000–6.000 tấm xem trước
CHAT_LUONG = 90
CANH_TOI_DA = 1400            # cùng cỡ engine trả về (xem_truoc: 1400 px)


def khoa(path, muc: dict, ban: str = "") -> str:
    """Khoá cache của một (ảnh, bộ mức, bản tool). Ảnh đổi (mtime / cỡ) là
    khoá khác. Mức làm tròn 1 chữ số thập phân như _muc_xem gửi engine."""
    p = str(path or "")
    try:
        st = os.stat(p)
        dau = f"{st.st_mtime_ns}|{st.st_size}"
    except OSError:
        dau = "?"
    #  mức 0 = tắt tính năng = như không có khoá đó (engine cũng hiểu vậy)
    m = {}
    for k, v in (muc or {}).items():
        try:
            gt = round(float(v), 1)
        except (TypeError, ValueError):
            continue
        if gt > 0:
            m[str(k)] = gt
    van = "|".join([os.path.normcase(os.path.abspath(p)), dau,
                    json.dumps(m, sort_keys=True), str(ban or "")])
    return hashlib.sha1(van.encode("utf-8", "surrogatepass")).hexdigest()


class CacheXem:
    """Một thư mục cache + chỉ mục LRU. Dùng chung một thể hiện (lay_chung())."""

    def __init__(self, thu_muc: Path | None = None, gioi_han_mb: int | None = None):
        self.thu_muc = Path(thu_muc) if thu_muc else dd.du_lieu(TEN_THU_MUC, "x").parent
        self._khoa_luong = threading.Lock()
        self._chi_muc: dict = {}              # khoa -> {"co": bytes, "luc": epoch}
        self._gioi_han_mb = int(gioi_han_mb) if gioi_han_mb else None
        self._nap()

    # ------------------------------------------------------------ chỉ mục
    def _tep_chi_muc(self) -> Path:
        return self.thu_muc / TEN_CHI_MUC

    def _nap(self):
        try:
            d = json.loads(self._tep_chi_muc().read_text(encoding="utf-8"))
            if isinstance(d, dict):
                self._chi_muc = {str(k): {"co": int(v.get("co", 0)), "luc": float(v.get("luc", 0))}
                                 for k, v in d.items() if isinstance(v, dict)}
        except (OSError, ValueError):
            self._chi_muc = {}
        #[[ File trên đĩa mà chỉ mục không biết (chỉ mục mất / ghi dở) thì đưa
        #   vào chỉ mục với mtime của nó — không để file mồ côi chiếm chỗ mãi. ]]
        try:
            for f in self.thu_muc.glob("*.jpg"):
                k = f.stem
                if k not in self._chi_muc:
                    st = f.stat()
                    self._chi_muc[k] = {"co": st.st_size, "luc": st.st_mtime}
        except OSError:
            pass

    def _ghi_chi_muc(self):
        try:
            self.thu_muc.mkdir(parents=True, exist_ok=True)
            tmp = self._tep_chi_muc().with_suffix(".part")
            tmp.write_text(json.dumps(self._chi_muc, separators=(",", ":")), encoding="utf-8")
            os.replace(tmp, self._tep_chi_muc())
        except OSError:
            pass

    # ------------------------------------------------------------ giới hạn
    def gioi_han_mb(self) -> int:
        if self._gioi_han_mb:
            return self._gioi_han_mb
        try:
            import xuat_ui
            return int(xuat_ui.doc_cai_dat().get("cache_mb") or MB_MAC_DINH)
        except Exception:                                    # noqa: BLE001
            return MB_MAC_DINH

    def dat_gioi_han_mb(self, mb: int):
        self._gioi_han_mb = max(64, int(mb))
        self.don()

    def dung_luong(self) -> int:
        """Tổng byte đang chiếm (theo chỉ mục)."""
        with self._khoa_luong:
            return sum(int(v.get("co", 0)) for v in self._chi_muc.values())

    def so_tam(self) -> int:
        return len(self._chi_muc)

    def _duong(self, k: str) -> Path:
        return self.thu_muc / f"{k}.jpg"

    def don(self) -> int:
        """Xoá tấm lâu không xem nhất cho tới khi dưới giới hạn. -> số tấm đã xoá."""
        gh = self.gioi_han_mb() * 1024 * 1024
        xoa = 0
        with self._khoa_luong:
            tong = sum(int(v.get("co", 0)) for v in self._chi_muc.values())
            if tong <= gh:
                return 0
            for k, v in sorted(self._chi_muc.items(), key=lambda kv: kv[1].get("luc", 0)):
                if tong <= gh:
                    break
                try:
                    self._duong(k).unlink()
                except OSError:
                    pass
                tong -= int(v.get("co", 0))
                self._chi_muc.pop(k, None)
                xoa += 1
            self._ghi_chi_muc()
        return xoa

    def xoa_het(self) -> int:
        with self._khoa_luong:
            n = 0
            for k in list(self._chi_muc):
                try:
                    self._duong(k).unlink()
                except OSError:
                    pass
                n += 1
            self._chi_muc = {}
            self._ghi_chi_muc()
        return n

    # ------------------------------------------------------------ đọc / ghi
    def co(self, k: str) -> bool:
        with self._khoa_luong:
            return k in self._chi_muc and self._duong(k).is_file()

    def lay(self, k: str):
        """Ảnh PIL RGB của khoá, None nếu không có. Chạm `luc` (LRU)."""
        with self._khoa_luong:
            if k not in self._chi_muc:
                return None
            f = self._duong(k)
            try:
                from PIL import Image
                with Image.open(f) as im:
                    im.load()
                    ra = im.convert("RGB")
            except (OSError, ValueError):
                self._chi_muc.pop(k, None)
                return None
            self._chi_muc[k]["luc"] = time.time()
            #[[ Khong ghi chi muc moi lan DOC (luot anh la hang chuc lan doc):
            #   `luc` ghi xuong o lan cat() / don() ke tiep, hoac luc dong. ]]
            return ra

    def cat(self, k: str, im) -> bool:
        """Ghi một ảnh PIL vào cache (thu về CANH_TOI_DA nếu lớn hơn)."""
        try:
            from PIL import Image
            im = im.convert("RGB") if im.mode != "RGB" else im
            w, h = im.size
            if max(w, h) > CANH_TOI_DA:
                im = im.copy()
                im.thumbnail((CANH_TOI_DA, CANH_TOI_DA), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=CHAT_LUONG, optimize=True)
            du_lieu = buf.getvalue()
        except Exception:                                    # noqa: BLE001
            return False
        with self._khoa_luong:
            try:
                self.thu_muc.mkdir(parents=True, exist_ok=True)
                f = self._duong(k)
                tmp = f.with_suffix(".part")
                tmp.write_bytes(du_lieu)
                os.replace(tmp, f)
            except OSError:
                return False
            self._chi_muc[k] = {"co": len(du_lieu), "luc": time.time()}
            self._ghi_chi_muc()
        self.don()
        return True

    def luu(self):
        with self._khoa_luong:
            self._ghi_chi_muc()


_CHUNG: CacheXem | None = None


def lay_chung() -> CacheXem:
    """Thể hiện dùng chung của app (thư mục dữ liệu)."""
    global _CHUNG
    if _CHUNG is None:
        _CHUNG = CacheXem()
    return _CHUNG


def mo_ta_dung_luong(c: CacheXem | None = None) -> str:
    c = c or lay_chung()
    mb = c.dung_luong() / (1024 * 1024)
    return f"{mb:,.0f} MB / {c.gioi_han_mb():,} MB · {c.so_tam()} tấm"
