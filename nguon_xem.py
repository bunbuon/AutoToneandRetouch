#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nguon_xem.py — Ảnh để NHÌN cho một file RAW (9/10).

User 9/10: "Khi load ảnh preview ảnh RAW thì cho phép kéo các thanh Retouch luôn và
xem được luôn trên preview" — chốt nguồn: ẢNH DUYỆT Lightroom vẽ (Duyệt nhanh,
<buổi>/_duyet/<tên>.jpg — đúng WB / tone / preset, nhìn như ảnh xuất cuối); chưa
có thì ảnh JPEG NHÚNG trong RAW (màu máy ảnh, chưa qua preset).

Khung ảnh lớn (PIL) và engine retouch (cv2) đều không đọc RAW — nên RAW được đổi
thành MỘT FILE JPEG thật: ảnh duyệt dùng thẳng; ảnh nhúng rút ra một lần, cất ở
<dữ liệu app>/xem_raw/ (khoá theo đường dẫn + mtime + cỡ file), dọn khi quá TRAN tấm.

    la_raw(p)            đuôi RAW?
    anh_duyet(p)         ảnh duyệt Lightroom của RAW này (None nếu chưa dựng)
    anh_nhung(p, canh)   JPEG nhúng đã rút (None nếu không đọc được)
    anh_xem(p)           (đường dẫn JPEG để nhìn, "preset" | "duyet" | "nhung" | "anh")
                         "preset": Lightroom render theo preset đang chọn (preset_lr)
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import duong_dan as dd

TEN_KHO = "xem_raw"
CANH = 2400             # ảnh nhúng rút ra: đủ cho ảnh lớn + engine (1400 px)
TRAN = 3000             # quá chừng này tấm trong kho thì xoá 1/4 tấm cũ nhất


def la_raw(p) -> bool:
    try:
        import autotone as at
        return Path(str(p)).suffix.lower() in at.RAW_EXTS
    except Exception:                                        # noqa: BLE001
        return Path(str(p)).suffix.lower() in {".arw", ".nef", ".cr2", ".cr3", ".raf",
                                                ".dng", ".orf", ".rw2", ".srw", ".pef"}


def anh_duyet(p) -> Path | None:
    """<thư mục ảnh>/_duyet/<tên không đuôi>.jpg nếu đã có (Duyệt nhanh)."""
    p = Path(str(p))
    q = p.parent / "_duyet" / (p.stem + ".jpg")
    return q if q.is_file() else None


def _kho() -> Path:
    return dd.du_lieu(TEN_KHO, "x").parent


def _khoa(p, canh) -> str | None:
    try:
        st = os.stat(p)
    except OSError:
        return None
    van = f"{os.path.normcase(os.path.abspath(str(p)))}|{st.st_mtime_ns}|{st.st_size}|{canh}"
    return hashlib.sha1(van.encode("utf-8", "surrogatepass")).hexdigest()


def _don(kho: Path):
    try:
        ds = sorted(kho.glob("*.jpg"), key=lambda f: f.stat().st_mtime)
    except OSError:
        return
    if len(ds) > TRAN:
        for f in ds[:len(ds) // 4]:
            try:
                f.unlink()
            except OSError:
                pass


def anh_nhung(p, canh: int = CANH) -> Path | None:
    """JPEG nhúng trong RAW (cạnh dài ≤ canh) rút ra kho; None nếu không đọc được."""
    k = _khoa(p, canh)
    if k is None:
        return None
    kho = _kho()
    f = kho / f"{k}.jpg"
    if f.is_file():
        try:
            os.utime(f, None)
        except OSError:
            pass
        return f
    try:
        import autotone as at
        im = at.anh_nho(str(p), canh)
    except Exception:                                        # noqa: BLE001
        im = None
    if im is None:
        return None
    try:
        kho.mkdir(parents=True, exist_ok=True)
        tam = f.with_suffix(".part")
        im.convert("RGB").save(tam, "JPEG", quality=92)
        os.replace(tam, f)
    except OSError:
        return None
    _don(kho)
    return f


def anh_xem(p) -> tuple:
    """(file JPEG để nhìn, nguồn): RAW -> ảnh duyệt Lightroom ("duyet"), thiếu thì
    ảnh nhúng ("nhung"); ảnh thường -> chính nó ("anh"). (None, "") nếu không có."""
    if not la_raw(p):
        return Path(str(p)), "anh"
    #  9/10: đang chọn xem theo preset Lightroom và tấm này đã render -> dùng nó
    try:
        import preset_lr
        f = preset_lr.anh_preset(p)
    except Exception:                                        # noqa: BLE001
        f = None
    if f is not None:
        return f, "preset"
    d = anh_duyet(p)
    if d is not None:
        return d, "duyet"
    n = anh_nhung(p)
    return (n, "nhung") if n is not None else (None, "")
