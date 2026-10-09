#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""preset_lr.py — Preset Lightroom: danh sách + xem trước CẢ LƯỚI theo preset (9/10).

User 9/10 (kèm ảnh NEXUS AI Retouch): "Thêm tính năng lấy ra Preset và khi chọn
Preset thì sẽ load lại Preview với preset đã chọn cho toàn bộ ảnh preview".

ĐƯỜNG ĐI
  App ghi jobs/request_xempreset.txt (preset + danh sách ảnh theo thứ tự ưu tiên)
  -> plugin (XemPresetCore.lua) từng lô nhỏ: áp preset TẠM -> Lightroom render
     JPEG 1600 px vào <dữ liệu>/xem_preset/<buổi>/<preset>/ -> trả lại thông số cũ
  -> app đọc bảng jobs/xempreset_anh.tsv, ô lưới / ảnh lớn đổi sang ảnh theo preset
     dần dần (ảnh đang xem đi trước).
  Màu là Lightroom render THẬT (đúng profile, WB Kelvin, đường cong…) — không mô
  phỏng. Đổi lại: cần Lightroom đang mở, mỗi tấm ~0,5–1 giây.

DANH SÁCH PRESET
  Bản chuẩn: plugin ghi jobs/lr_presets.tsv (uuid Lightroom, tên, nhóm, thư mục).
  Dự phòng khi Lightroom chưa từng mở: tự quét file .xmp. CHÚ Ý (đo 9/10): UUID
  trong file .xmp KHÁC UUID Lightroom dùng (NoWBExposure: file EFAD0B…, Lightroom
  A04EDE…) -> bản quét gửi uuid rỗng, plugin tìm theo TÊN + NHÓM.

    danh_sach(hien_adobe)        [{uuid, ten, nhom, thu_muc, adobe}]
    chon_hien() / dat_chon(p)    preset đang xem (None = không áp)
    gui_xem(p, paths, thu_muc_buoi, ap=False) -> id
    tien_do(id) / bang() / dung()
    anh_preset(path)             JPEG theo preset đang chọn của một ảnh (None nếu chưa có)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import duong_dan as dd

TEN_DS = "lr_presets.tsv"
XIN_DS = "request_dspreset.txt"
YEU_CAU = "request_xempreset.txt"
CO_DUNG = "request_xempreset_dung.txt"
TIEN_DO = "xempreset_tiendo.txt"
BANG = "xempreset_anh.tsv"
TEN_CHON = "preset_xem.json"
TEN_KHO = "xem_preset"
CANH = 1600
CHAT = 80
NHOM_USER = "User Presets"


def job_dir() -> Path:
    import autotone as at
    return Path(at.LR_JOB_DIR)


# ------------------------------------------------------------ danh sách preset
def _thu_muc_user() -> list:
    ds = []
    if sys.platform == "darwin":
        ds.append(Path.home() / "Library/Application Support/Adobe/CameraRaw/Settings")
    else:
        ad = os.environ.get("APPDATA")
        if ad:
            ds.append(Path(ad) / "Adobe" / "CameraRaw" / "Settings")
    return ds


def _thu_muc_adobe() -> list:
    if sys.platform == "darwin":
        return [Path("/Library/Application Support/Adobe/CameraRaw/Settings"),
                Path("/Applications/Adobe Lightroom Classic/Adobe Lightroom Classic.app/"
                     "Contents/Resources/Settings")]
    pd = os.environ.get("ProgramData", r"C:\ProgramData")
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    return [Path(pd) / "Adobe" / "CameraRaw" / "Settings",
            Path(pf) / "Adobe" / "Adobe Lightroom Classic" / "Resources" / "Settings"]


def la_adobe(thu_muc: str) -> bool:
    """Preset có sẵn của Adobe (cài cùng Lightroom / Camera Raw), không phải của người dùng."""
    t = str(thu_muc or "").replace("\\", "/").lower()
    if not t:
        return False
    for u in _thu_muc_user():
        if t.startswith(str(u).replace("\\", "/").lower()):
            return False
    return any(k in t for k in ("/programdata/", "/program files", "/resources/settings",
                                "/library/application support/adobe/camerarw",
                                "/applications/"))


_RE_ALT = r"<crs:{0}>\s*<rdf:Alt>\s*<rdf:li[^>]*?(?:/>|>([^<]*)</rdf:li>)"


def doc_xmp(p: Path) -> dict | None:
    """Một file preset .xmp -> {ten, nhom, co_mask} (None nếu không phải preset develop)."""
    try:
        if p.stat().st_size > 4_000_000:
            return None
        s = p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    m = re.search(r'crs:PresetType="(\w+)"', s)
    if not m or m.group(1) != "Normal":
        return None
    ten = re.search(_RE_ALT.format("Name"), s)
    nhom = re.search(_RE_ALT.format("Group"), s)
    ten = (ten.group(1) or "").strip() if ten else ""
    nhom = (nhom.group(1) or "").strip() if nhom else ""
    import html
    return {"ten": html.unescape(ten) or p.stem, "nhom": html.unescape(nhom),
            "co_mask": "MaskGroupBasedCorrections" in s or "CircularGradientBasedCorrections" in s
                       or "GradientBasedCorrections" in s or "PaintBasedCorrections" in s}


def quet_xmp(hien_adobe: bool = False) -> list:
    ds = []
    goc = [(d, False) for d in _thu_muc_user()]
    if hien_adobe:
        goc += [(d, True) for d in _thu_muc_adobe()]
    for d, adobe in goc:
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*.xmp")):
            x = doc_xmp(p)
            if x is None:
                continue
            ds.append({"uuid": "", "ten": x["ten"],
                       "nhom": x["nhom"] or (NHOM_USER if not adobe else p.parent.name),
                       "thu_muc": str(p.parent), "adobe": adobe, "co_mask": x["co_mask"],
                       "nguon": "xmp"})
    return ds


def doc_ds_plugin(jd: Path | None = None) -> list:
    """Danh sách plugin gửi (uuid Lightroom THẬT). [] nếu chưa có."""
    p = Path(jd or job_dir()) / TEN_DS
    try:
        txt = p.read_text(encoding="utf-8-sig")
    except OSError:
        return []
    ds = []
    for dong in txt.splitlines():
        c = dong.split("\t")
        if len(c) < 3 or not c[1].strip():
            continue
        tm = c[3] if len(c) > 3 else ""
        ds.append({"uuid": c[0].strip(), "ten": c[1].strip(), "nhom": c[2].strip(),
                   "thu_muc": tm.strip(), "adobe": la_adobe(tm), "co_mask": False,
                   "nguon": "lr"})
    return ds


def xin_ds(jd: Path | None = None) -> None:
    """Nhờ plugin gửi lại danh sách ngay (không chờ chu kỳ 20 giây)."""
    try:
        (Path(jd or job_dir()) / XIN_DS).write_text("1", encoding="utf-8")
    except OSError:
        pass


def _thu_tu(p: dict):
    return (bool(p.get("adobe")), p.get("nhom") != NHOM_USER, _bo_dau(p.get("nhom") or ""),
            _bo_dau(p.get("ten") or ""))


def danh_sach(hien_adobe: bool = False, jd: Path | None = None) -> list:
    ds = doc_ds_plugin(jd)
    if not ds:
        ds = quet_xmp(hien_adobe)
    if not hien_adobe:
        ds = [p for p in ds if not p.get("adobe")]
    return sorted(ds, key=_thu_tu)


def loc(ds: list, tu: str) -> list:
    """Lọc theo chữ gõ (không dấu, không hoa thường) trên tên + nhóm."""
    tu = _bo_dau(tu).strip()
    if not tu:
        return list(ds)
    return [p for p in ds if tu in _bo_dau(f"{p.get('ten', '')} {p.get('nhom', '')}")]


def _bo_dau(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", str(s or "").replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").casefold()


# ------------------------------------------------------------ preset đang xem
def khoa_preset(p: dict | None) -> str:
    if not p:
        return ""
    if p.get("uuid"):
        return re.sub(r"[^0-9A-Za-z]", "", p["uuid"])[:40]
    return "n" + hashlib.sha1(f"{p.get('nhom', '')}|{p.get('ten', '')}".encode("utf-8")
                              ).hexdigest()[:16]


_chon_nho = [None, None]          # (mtime_ns, preset) — hàm này gọi mỗi ô lưới


def chon_hien() -> dict | None:
    f = dd.du_lieu(TEN_CHON)
    try:
        mt = f.stat().st_mtime_ns
    except OSError:
        _chon_nho[:] = [None, None]
        return None
    if _chon_nho[0] == mt:
        return _chon_nho[1]
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    d = d if isinstance(d, dict) and d.get("ten") else None
    _chon_nho[:] = [mt, d]
    return d


def dat_chon(p: dict | None) -> None:
    try:
        f = dd.du_lieu(TEN_CHON)
        if p:
            dd.ghi_ben(f, json.dumps({k: p.get(k) for k in ("uuid", "ten", "nhom", "thu_muc")},
                                     ensure_ascii=False))
        elif f.exists():
            f.unlink()
    except OSError:
        pass


def cung_preset(a: dict | None, b: dict | None) -> bool:
    if not a or not b:
        return not a and not b
    if a.get("uuid") and b.get("uuid"):
        return a["uuid"] == b["uuid"]
    return a.get("ten") == b.get("ten") and (a.get("nhom") or "") == (b.get("nhom") or "")


# ------------------------------------------------------------ kho ảnh theo preset
def thu_muc_kho(thu_muc_buoi, p: dict | None) -> Path:
    h = hashlib.sha1(os.path.normcase(os.path.abspath(str(thu_muc_buoi))).encode(
        "utf-8", "surrogatepass")).hexdigest()[:12]
    return dd.goc_du_lieu() / TEN_KHO / h / (khoa_preset(p) or "_")


def _moc_ghi_buoi(thu_muc_buoi) -> float:
    """Lần cuối Lightroom ÁP job của buổi này (apply_*_<buổi>.done) — ảnh render
    trước mốc này mang thông số cũ (tool vừa ghi lại WB / tone)."""
    try:
        import autotone as at
        ten = at.ten_job(Path(str(thu_muc_buoi)).name)
        jd = job_dir()
        moc = 0.0
        for f in jd.glob(f"apply_*_{ten}.done"):
            moc = max(moc, f.stat().st_mtime)
        return moc
    except Exception:                                        # noqa: BLE001
        return 0.0


_hop_le: dict = {}


def kho_hop_le(thu_muc_buoi, p: dict | None) -> bool:
    """Kho của (buổi, preset) còn dùng được: dựng SAU lần ghi Lightroom cuối."""
    k = (os.path.normcase(str(thu_muc_buoi)), khoa_preset(p))
    t = time.monotonic()
    c = _hop_le.get(k)
    if c is not None and t - c[0] < 5:
        return c[1]
    kho = thu_muc_kho(thu_muc_buoi, p)
    try:
        moc_kho = float(json.loads((kho / "meta.json").read_text(encoding="utf-8"))["t"])
    except (OSError, ValueError, KeyError, TypeError):
        moc_kho = 0.0
    ok = moc_kho > 0 and moc_kho >= _moc_ghi_buoi(thu_muc_buoi)
    _hop_le[k] = (t, ok)
    return ok


def anh_preset(path, p: dict | None = None) -> Path | None:
    """JPEG Lightroom đã render theo preset (đang chọn) của một ảnh, nếu có và còn
    hợp lệ."""
    p = p if p is not None else chon_hien()
    if not p:
        return None
    path = Path(str(path))
    kho = thu_muc_kho(path.parent, p)
    f = kho / (path.stem + ".jpg")
    if not f.is_file():
        return None
    return f if kho_hop_le(path.parent, p) else None


# ------------------------------------------------------------ yêu cầu plugin
def gui_xem(p: dict, paths: list, thu_muc_buoi, ap: bool = False,
            jd: Path | None = None) -> str:
    """Gửi yêu cầu render `paths` (đã xếp ưu tiên) theo preset `p`. -> id lượt."""
    jd = Path(jd or job_dir())
    kho = thu_muc_kho(thu_muc_buoi, p)
    kho.mkdir(parents=True, exist_ok=True)
    meta = kho / "meta.json"
    if not ap:
        try:
            cu = float(json.loads(meta.read_text(encoding="utf-8"))["t"])
        except (OSError, ValueError, KeyError, TypeError):
            cu = 0.0
        if cu < _moc_ghi_buoi(thu_muc_buoi):
            #  ảnh cũ mang thông số trước lần ghi Lightroom cuối -> bỏ hết, dựng lại
            for f in kho.glob("*.jpg"):
                try:
                    f.unlink()
                except OSError:
                    pass
    dd.ghi_ben(meta, json.dumps({"t": time.time(), "ten": p.get("ten"), "nhom": p.get("nhom"),
                                 "buoi": str(thu_muc_buoi)}, ensure_ascii=False))
    _hop_le.clear()
    id_ = str(int(time.time() * 1000))
    dong = [f"id={id_}", f"uuid={p.get('uuid') or ''}", f"ten={p.get('ten') or ''}",
            f"nhom={p.get('nhom') or ''}", f"dest={kho}", f"canh={CANH}", f"chat={CHAT}",
            f"ap={1 if ap else 0}", "---"] + [str(x) for x in paths]
    for ten in (CO_DUNG,):
        try:
            (jd / ten).unlink()
        except OSError:
            pass
    tam = jd / (YEU_CAU + ".part")
    tam.write_text("\n".join(dong) + "\n", encoding="utf-8")
    os.replace(tam, jd / YEU_CAU)
    return id_


def dung(jd: Path | None = None) -> None:
    jd = Path(jd or job_dir())
    try:
        (jd / YEU_CAU).unlink()
    except OSError:
        pass
    try:
        (jd / CO_DUNG).write_text("1", encoding="utf-8")
    except OSError:
        pass


def tien_do(id_: str, jd: Path | None = None) -> dict | None:
    """Tiến độ lượt `id_` (None: plugin chưa nhận lượt này)."""
    p = Path(jd or job_dir()) / TIEN_DO
    try:
        txt = p.read_text(encoding="utf-8-sig")
    except OSError:
        return None
    d = {}
    for dong in txt.splitlines():
        if "=" in dong:
            k, v = dong.split("=", 1)
            d[k.strip()] = v.strip()
    if d.get("id") != str(id_):
        return None
    for k in ("xong", "tong", "thieu", "lech", "ap"):
        try:
            d[k] = int(d.get(k) or 0)
        except ValueError:
            d[k] = 0
    return d


def bang(jd: Path | None = None) -> dict:
    """{đường dẫn ảnh gốc (normcase): jpg} của lượt plugin đang / vừa làm."""
    p = Path(jd or job_dir()) / BANG
    try:
        txt = p.read_text(encoding="utf-8-sig")
    except OSError:
        return {}
    out = {}
    for dong in txt.splitlines():
        c = dong.split("\t")
        if len(c) >= 2 and c[0] and c[1]:
            out[os.path.normcase(os.path.normpath(c[0]))] = os.path.normpath(c[1])
    return out
