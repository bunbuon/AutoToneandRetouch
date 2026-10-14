"""Đọc THẲNG catalog Lightroom (.lrcat, SQLite) — CHỈ ĐỌC — 13/10.

User 13/10 (v83, sau khi cài): "Tôi vẫn chưa thấy phần folder như của Lightroom".
Bản v83 lấy cây thư mục + danh sách ảnh của buổi qua PLUGIN (DanhSachCore) — plugin
trong Lightroom không chạy (Lightroom chưa mở lại sau khi cài, vòng lặp chết…) là
không có gì. Catalog thì luôn nằm trên đĩa: đường dẫn ghi trong file cài đặt của
Lightroom (libraryToLoad20), mở SQLite chế độ chỉ đọc (mode=ro&immutable=1 — không
khoá, không ghi gì, Lightroom đang mở vẫn đọc được; catalog dùng journal "delete"
nên thay đổi Lightroom đã ghi là thấy ngay).

Bảng dùng (đối chiếu panel Folders 13/10: BVDay3 1813, 1005 630, G: 10952):
  AgLibraryRootFolder(id_local, absolutePath "G:/")      — thư mục gốc đã thêm
  AgLibraryFolder(id_local, rootFolder, pathFromRoot "BVDay3/")
  AgLibraryFile(id_local, folder, baseName, extension)   — file ảnh
  Adobe_images(rootFile -> AgLibraryFile)                 — ảnh (gồm bản sao ảo)
  Adobe_images.rating (NULL = chưa chấm, 1.0–5.0), masterImage (NOT NULL = bản sao ảo)

Biến môi trường AUTOTONE_CATALOG_LR: đường dẫn .lrcat (ép), hoặc "0" = tắt (bài kiểm).
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys
import time
from pathlib import Path

_DEM: dict = {}


def _tep_cai_dat() -> list:
    """Các file cài đặt Lightroom có thể chứa libraryToLoad20."""
    if sys.platform == "darwin":
        thu = Path.home() / "Library" / "Preferences"
        return sorted(thu.glob("com.adobe.LightroomClassicCC*.plist"), reverse=True)
    app = os.environ.get("APPDATA")
    if not app:
        return []
    thu = Path(app) / "Adobe" / "Lightroom" / "Preferences"
    ds = sorted(thu.glob("Lightroom Classic CC* Preferences.agprefs"), reverse=True)
    #  "…Startup Preferences" ghi catalog mở lúc khởi động — để sau file chính
    return sorted(ds, key=lambda p: "Startup" in p.name)


def duong_catalog() -> Path | None:
    """Catalog Lightroom đang dùng (libraryToLoad20), None nếu không tìm thấy."""
    ep = os.environ.get("AUTOTONE_CATALOG_LR")
    if ep == "0":
        return None
    if ep:
        return Path(ep) if Path(ep).is_file() else None
    kq = _DEM.get("duong")
    if kq is not None and time.monotonic() - kq[0] < 30:
        return kq[1]
    ra = None
    for f in _tep_cai_dat():
        try:
            if f.suffix == ".plist":
                import plistlib
                with open(f, "rb") as fh:
                    v = plistlib.load(fh).get("libraryToLoad20")
            else:
                m = re.search(r'libraryToLoad20\s*=\s*"((?:[^"\\]|\\.)*)"',
                              f.read_text(encoding="utf-8", errors="replace"))
                v = m.group(1).replace("\\\\", "\\") if m else None
        except Exception:                                    # noqa: BLE001
            v = None
        if v and Path(v).is_file():
            ra = Path(v)
            break
    _DEM["duong"] = (time.monotonic(), ra)
    return ra


def _mo(p: Path):
    uri = p.resolve().as_uri() + "?mode=ro&immutable=1"
    return sqlite3.connect(uri, uri=True, timeout=1)


def _dau(p: Path):
    st = p.stat()
    return (str(p), st.st_mtime_ns, st.st_size)


def _doc_cau_truc(p: Path):
    """(gốc {id: absolutePath}, thư mục [(id, gốc, pathFromRoot)], số ảnh {id: n}) — đệm
    theo giờ sửa catalog."""
    dau = _dau(p)
    kq = _DEM.get("cau_truc")
    if kq is not None and kq[0] == dau:
        return kq[1]
    con = _mo(p)
    try:
        goc = dict(con.execute("select id_local, absolutePath from AgLibraryRootFolder"))
        thu = con.execute("select id_local, rootFolder, pathFromRoot "
                          "from AgLibraryFolder").fetchall()
        so = dict(con.execute(
            "select fi.folder, count(*) from Adobe_images i "
            "join AgLibraryFile fi on i.rootFile = fi.id_local group by fi.folder"))
    finally:
        con.close()
    gt = (goc, thu, so)
    _DEM["cau_truc"] = (dau, gt)
    return gt


def _duong(base: str, rel: str) -> str:
    return os.path.normpath((base or "") + (rel or ""))


def cay_thu_muc() -> list | None:
    """[(đường dẫn, thư mục cha, số ảnh riêng)] như DanhSachCore.runThuMuc — None nếu
    không đọc được catalog."""
    p = duong_catalog()
    if p is None:
        return None
    try:
        goc, thu, so = _doc_cau_truc(p)
    except Exception:                                        # noqa: BLE001
        kq = _DEM.get("cau_truc")
        if kq is None:
            return None
        goc, thu, so = kq[1]
    ra = []
    for fid, rid, rel in thu:
        base = goc.get(rid)
        if base is None:
            continue
        rel = rel or ""
        duong = _duong(base, rel)
        if rel.strip("/"):
            cha_rel = rel.rstrip("/").rpartition("/")[0]
            cha = _duong(base, cha_rel + "/" if cha_rel else "")
        else:
            cha = ""
        ra.append((duong, cha, int(so.get(fid, 0))))
    return ra


def anh_trong_thu_muc(folder, gom_con: bool = True) -> set | None:
    """Khoá đường dẫn (autotone.khoa_duong_dan) của mọi ảnh trong `folder` theo catalog.
    None = không biết (không có catalog / thư mục chưa import) -> app KHÔNG lọc."""
    d = sao_trong_thu_muc(folder, gom_con)
    return None if d is None else set(d)


def sao_trong_thu_muc(folder, gom_con: bool = True) -> dict | None:
    """{khoá đường dẫn: số sao 0–5} của mọi ảnh trong `folder` theo catalog — số sao
    ĐANG có trong Lightroom (14/10 user: "nhận diện ảnh rate theo mức trong lightroom").
    Bản sao ảo không đè số sao của ảnh gốc. None = không biết -> app KHÔNG lọc."""
    p = duong_catalog()
    if p is None or not folder:
        return None
    try:
        dau = _dau(p)
    except OSError:
        return None
    k_dem = ("anh_sao", dau, os.path.normcase(os.path.normpath(str(folder))), bool(gom_con))
    kq = _DEM.get("anh")
    if kq is not None and kq[0] == k_dem:
        return kq[1]
    import autotone as at
    try:
        goc, thu, _so = _doc_cau_truc(p)
        f = os.path.normcase(os.path.normpath(str(folder)))
        chon = []
        for rid, base in goc.items():
            b = os.path.normcase(os.path.normpath(base)).rstrip("\\/")
            if f == b or f.startswith(b + os.sep):
                rel = f[len(b):].strip("\\/").replace("\\", "/").lower()
                rel = (rel + "/") if rel else ""
                for fid, r2, pfr in thu:
                    if r2 != rid:
                        continue
                    pl = (pfr or "").lower()
                    if pl == rel or (gom_con and pl.startswith(rel)):
                        chon.append((fid, base, pfr or ""))
        if not chon:
            ra = None
        else:
            thu_cua = {fid: (base, pfr) for fid, base, pfr in chon}
            con = _mo(p)
            dau_hoi = ",".join("?" * len(thu_cua))
            try:
                try:
                    ds = con.execute(
                        "select fi.folder, fi.baseName, fi.extension, i.rating, i.masterImage "
                        "from AgLibraryFile fi left join Adobe_images i "
                        "on i.rootFile = fi.id_local where fi.folder in (%s)" % dau_hoi,
                        list(thu_cua)).fetchall()
                except sqlite3.OperationalError:
                    #  catalog lạ thiếu cột sao: vẫn trả danh sách ảnh (sao = 0) — đừng
                    #  để phần sao làm mất bộ lọc "ảnh còn trong Lightroom"
                    ds = [(f, t, d, None, None) for f, t, d in con.execute(
                        "select folder, baseName, extension from AgLibraryFile "
                        "where folder in (%s)" % dau_hoi, list(thu_cua))]
            finally:
                con.close()
            ra = {}
            for fid, ten, duoi, sao, ban_sao in ds:
                base, pfr = thu_cua[fid]
                k = at.khoa_duong_dan(_duong(base, pfr + f"{ten}.{duoi}" if duoi else
                                             pfr + str(ten)))
                try:
                    n = max(0, min(5, int(round(float(sao or 0)))))
                except (TypeError, ValueError):
                    n = 0
                if ban_sao is None or k not in ra:
                    ra[k] = n
    except Exception:                                        # noqa: BLE001
        return kq[1] if kq is not None and kq[0][2:] == k_dem[2:] else None
    _DEM["anh"] = (k_dem, ra)
    return ra
