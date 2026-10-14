# -*- coding: utf-8 -*-
"""doc_cache_lr.py — ĐỌC THẲNG cache preview + thông số develop của Lightroom (CHỈ ĐỌC) — 14/10.

User 14/10: "thử tìm hiểu hướng nếu đưa tất cả vào plugin cắm vào trong Lightroom thì có
thể xử lý các bước thông số, preview và phân tích nhanh hơn không". Đo trên máy user
(LrC 15.5): cổ chai là Lightroom DỰNG preview (~0.5 s/ảnh) — trong hay ngoài plugin như
nhau. Nhưng preview Lightroom ĐÃ dựng nằm sẵn trên đĩa: đọc thẳng 13 ms/ảnh, khớp ảnh
lấy qua plugin (lệch TB 0.93 mã / 79 ảnh).

  <tên catalog> Previews.lrdata/previews.db   (SQLite)
      ImageCacheEntry(imageId = Adobe_images.id_local, uuid, digest, orientation)
      PyramidLevel(uuid, digest, longDimension, …)
  <tên catalog> Previews.lrdata/<uuid[0]>/<uuid[:4]>/<uuid>-<digest>_<cạnh>
      mỗi mức một file JPEG thô (Adobe RGB, CHƯA xoay: orientation AB/BC/CD/DA)
  catalog .lrcat: Adobe_imageDevelopSettings(image, digest, text) — text = toàn bộ
      thông số develop dạng bảng Lua; digest đổi mỗi khi thông số đổi.

PREVIEW CÒN MỚI = digest của preview == digest thông số trong catalog (buổi 2709 sau khi
áp + dựng: 1068/1074). Ảnh chưa từng xem trong Lightroom thường chỉ có mức nhỏ (<1024).

LrC 15 ghi catalog qua WAL (.lrcat-wal): mở `immutable` (như catalog_lr) là BỎ QUA thay
đổi chưa gộp vào file chính -> có WAL thì CHÉP .lrcat + .lrcat-wal ra thư mục tạm rồi mở
bản chép (~1.3 s / 788 MB; dùng lại khi hai file chưa đổi).

Định dạng KHÔNG công khai (Adobe đổi được): mọi hàm trả None / rỗng khi không đọc được —
nơi gọi LÙI VỀ plugin (requestJpegThumbnail). Không bao giờ ghi vào file của Lightroom.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import time
from pathlib import Path

import numpy as np

_BAN: dict = {}                    # đường catalog -> (dấu, đường bản chép)
#: mã xoay của Lightroom -> phép xoay PIL (đo 14/10: DA = 90° ngược chiều kim)
XOAY = {"AB": None, "BC": "ROTATE_270", "CD": "ROTATE_180", "DA": "ROTATE_90"}


def thu_muc_preview(catalog) -> Path:
    p = Path(catalog)
    return p.with_name(p.stem + " Previews.lrdata")


def _dau(p: Path):
    try:
        st = p.stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def _thu_muc_tam() -> Path:
    import duong_dan as dd
    return dd.goc_du_lieu() / "tam_lrcat"


def mo_catalog(catalog=None) -> sqlite3.Connection | None:
    """Kết nối CHỈ ĐỌC tới catalog, THẤY cả thay đổi còn trong WAL. None nếu không mở được."""
    if catalog is None:
        import catalog_lr
        catalog = catalog_lr.duong_catalog()
    if catalog is None:
        return None
    p = Path(catalog)
    wal = p.with_name(p.name + "-wal")
    dw = _dau(wal)
    try:
        if not dw or dw[1] == 0:
            return sqlite3.connect(p.resolve().as_uri() + "?mode=ro&immutable=1", uri=True, timeout=1)
        dau = (_dau(p), dw)
        cu = _BAN.get(str(p))
        if cu and cu[0] == dau and Path(cu[1]).is_file():
            return sqlite3.connect(Path(cu[1]).as_uri() + "?mode=ro", uri=True, timeout=1)
        tam = _thu_muc_tam()
        shutil.rmtree(tam, ignore_errors=True)
        tam.mkdir(parents=True, exist_ok=True)
        dich = tam / "c.lrcat"
        for _lan in range(2):
            shutil.copyfile(p, dich)
            shutil.copyfile(wal, tam / "c.lrcat-wal")
            #  chép trúng lúc Lightroom gộp WAL -> bản chép lệch trang: chép lại một lần
            con = sqlite3.connect(str(dich), timeout=1)
            try:
                if con.execute("pragma quick_check(1)").fetchone()[0] == "ok":
                    con.execute("pragma wal_checkpoint(TRUNCATE)")
                    con.close()
                    _BAN[str(p)] = (dau, str(dich))
                    return sqlite3.connect(dich.as_uri() + "?mode=ro", uri=True, timeout=1)
            except sqlite3.DatabaseError:
                pass
            con.close()
            time.sleep(0.3)
    except (OSError, sqlite3.Error):
        return None
    return None


def mo_preview_db(catalog) -> sqlite3.Connection | None:
    f = thu_muc_preview(catalog) / "previews.db"
    if not f.is_file():
        return None
    try:
        return sqlite3.connect(f.resolve().as_uri() + "?mode=ro&immutable=1", uri=True, timeout=1)
    except sqlite3.Error:
        return None


def anh_buoi(con: sqlite3.Connection, folder, gom_con: bool = False) -> dict:
    """{khoá đường dẫn: {"id", "digest", "text", "xoay"}} của ảnh (không tính bản sao
    ảo) trong `folder`."""
    import autotone as at
    f = os.path.normcase(os.path.normpath(str(folder))).rstrip("\\/")
    out = {}
    try:
        rows = con.execute(
            "select ro.absolutePath, fo.pathFromRoot, fi.baseName, fi.extension, i.id_local, "
            "i.orientation, ds.digest, ds.text from Adobe_images i "
            "join AgLibraryFile fi on fi.id_local = i.rootFile "
            "join AgLibraryFolder fo on fo.id_local = fi.folder "
            "join AgLibraryRootFolder ro on ro.id_local = fo.rootFolder "
            "left join Adobe_imageDevelopSettings ds on ds.image = i.id_local "
            "where i.masterImage is null").fetchall()
    except sqlite3.Error:
        return out
    for base, pfr, ten, duoi, iid, xoay, dg, txt in rows:
        d = os.path.normpath((base or "") + (pfr or ""))
        dn = os.path.normcase(d).rstrip("\\/")
        if dn != f and not (gom_con and dn.startswith(f + os.sep)):
            continue
        p = os.path.join(d, f"{ten}.{duoi}" if duoi else str(ten))
        out[at.khoa_duong_dan(p)] = {"id": int(iid), "digest": dg, "text": txt, "xoay": xoay}
    return out


def preview_moi(catalog, anh: dict, canh: int = 1024) -> dict:
    """{khoá: {"tep", "canh", "xoay"}} cho ảnh có preview CÒN MỚI (digest khớp) ở mức ≥
    `canh` (mức nhỏ nhất đạt). Ảnh không có -> không có trong kết quả."""
    con = mo_preview_db(catalog)
    if con is None:
        return {}
    goc = thu_muc_preview(catalog)
    try:
        ce = {int(i): (u, d, x) for i, u, d, x in
              con.execute("select imageId, uuid, digest, orientation from ImageCacheEntry")}
    except sqlite3.Error:
        return {}
    finally:
        con.close()
    out = {}
    for k, a in anh.items():
        e = ce.get(a["id"])
        if not e or not a.get("digest") or e[1] != a["digest"]:
            continue
        u, d, x = e
        thu = goc / u[0] / u[:4]
        try:
            muc = sorted(int(p.name.rsplit("_", 1)[1]) for p in thu.glob(f"{u}-{d}_*")
                         if p.name.rsplit("_", 1)[1].isdigit())
        except OSError:
            continue
        lon = [m for m in muc if m >= canh]
        if lon:
            out[k] = {"tep": str(thu / f"{u}-{d}_{lon[0]}"), "canh": lon[0], "xoay": x or a.get("xoay")}
    return out


def doc(tep, xoay=None, draft=None) -> np.ndarray:
    """File preview -> sRGB uint8, ĐÃ xoay đứng như Lightroom hiện."""
    from PIL import Image
    import curve_da
    a = curve_da.doc_srgb(tep, draft)
    t = XOAY.get(xoay or "AB")
    if t:
        a = np.asarray(Image.fromarray(a).transpose(getattr(Image.Transpose, t)))
    return a


# ------------------------------------------------------------------ thông số (bảng Lua)
class _Doc:
    def __init__(self, s: str):
        self.s, self.i = s, 0

    def _trang(self):
        s = self.s
        while self.i < len(s):
            if s[self.i] in " \t\r\n,;":
                self.i += 1
            elif s.startswith("--", self.i):
                j = s.find("\n", self.i)
                self.i = len(s) if j < 0 else j
            else:
                break

    def gia_tri(self):
        self._trang()
        s, i = self.s, self.i
        c = s[i] if i < len(s) else ""
        if c == "{":
            return self.bang()
        if c == '"' or c == "'":
            return self.chuoi(c)
        for tu, v in (("true", True), ("false", False), ("nil", None)):
            if s.startswith(tu, i) and not (s[i + len(tu):i + len(tu) + 1].isalnum()):
                self.i += len(tu)
                return v
        j = i
        while j < len(s) and (s[j].isalnum() or s[j] in "+-.eExX_"):
            j += 1
        self.i = j
        tok = s[i:j]
        try:
            return int(tok, 0) if tok.lstrip("+-").isdigit() or tok.lower().startswith(("0x", "-0x")) \
                else float(tok)
        except ValueError:
            return tok

    def chuoi(self, q):
        s, i = self.s, self.i + 1
        out = []
        while i < len(s) and s[i] != q:
            if s[i] == "\\" and i + 1 < len(s):
                out.append({"n": "\n", "t": "\t", "r": "\r"}.get(s[i + 1], s[i + 1]))
                i += 2
            else:
                out.append(s[i])
                i += 1
        self.i = i + 1
        return "".join(out)

    def bang(self):
        self.i += 1
        mang, tu = [], {}
        while True:
            self._trang()
            if self.i >= len(self.s):
                break
            if self.s[self.i] == "}":
                self.i += 1
                break
            j = self.i
            #  khoá = giá trị (khoá là tên, hoặc ["chuỗi"])
            k = None
            if self.s[j] == "[":
                self.i += 1
                k = self.gia_tri()
                self._trang()
                self.i += 1                  # ]
                self._trang()
                self.i += 1                  # =
            else:
                e = j
                while e < len(self.s) and (self.s[e].isalnum() or self.s[e] == "_"):
                    e += 1
                sau = self.s[e:e + 3].lstrip()
                if e > j and sau.startswith("=") and not sau.startswith("=="):
                    k = self.s[j:e]
                    self.i = self.s.index("=", e) + 1
            v = self.gia_tri()
            if k is None:
                mang.append(v)
            else:
                tu[k] = v
        return tu if tu or not mang else mang


def thong_so(text: str | None) -> dict:
    """Bảng Lua `s = { Exposure2012 = 0, … }` -> dict Python. Hỏng -> {}."""
    if not text:
        return {}
    try:
        i = text.index("{")
        v = _Doc(text[i:]).gia_tri()
        return v if isinstance(v, dict) else {}
    except (ValueError, IndexError, RecursionError):
        return {}


def dong_xuat(st: dict) -> dict:
    """Thông số (thong_so) -> dòng giống bản xuất của plugin (chuỗi; curve "x,y,…";
    bool "1"/"0"; không crop -> crop đồng nhất) — cho app dùng chung một kiểu."""
    out = {}
    for k, v in st.items():
        if isinstance(v, bool):
            out[k] = "1" if v else "0"
        elif isinstance(v, (int, float)):
            out[k] = f"{v:.14g}"
        elif isinstance(v, str):
            out[k] = v
        elif isinstance(v, list) and v and all(isinstance(x, (int, float)) for x in v):
            out[k] = ",".join(f"{x:.14g}" for x in v)
    for k, mac in (("CropLeft", "0"), ("CropTop", "0"), ("CropRight", "1"), ("CropBottom", "1"),
                   ("CropAngle", "0")):
        out.setdefault(k, mac)
    return out
