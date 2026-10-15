#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Xem trước Retouch trên ảnh RAW: ngưỡng "mặt quá nhỏ" quy theo ẢNH GỐC (15/10).

User 15/10: "Tính năng làm thon mặt không thấy thay đổi trong ảnh này" (NVQ_6851, 4 người đội
mũ, mặt ~90 px trên bản xem 1400 px). Xem trước RAW mở ảnh TRUNG GIAN (Lightroom dựng 1600 px /
preview nhúng) -> engine quy ngưỡng thon mặt 150 px theo ảnh đó = 131 px -> bỏ cả 4 mặt im lặng.

  1. autotone.canh_goc_raw: cạnh dài ảnh gốc từ header TIFF (ImageWidth / Length); file hỏng -> 0
  2. xem_truoc._quy_goc: có canh_goc lớn hơn ảnh đang mở -> ty_le = cạnh ảnh / cạnh gốc;
     không có / nhỏ hơn -> giữ nguyên
  3. retouch_may: ảnh RAW (nguồn trung gian) gửi canh_goc kèm lệnh mo_anh; ảnh thường thì không

    python3 test_xem_goc_raw.py
"""
import os
import sys
import tempfile
import types
from pathlib import Path

os.environ["AUTOTONE_DATA"] = tempfile.mkdtemp(prefix="xem_goc_")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

import autotone as at  # noqa: E402
import xem_truoc  # noqa: E402

LOI = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


tam = Path(os.environ["AUTOTONE_DATA"])
print("1. canh_goc_raw")
f = tam / "goc.tif"
Image.new("RGB", (640, 480), (90, 90, 90)).save(f)
ktra("TIFF 640x480 -> 640", at.canh_goc_raw(f) == 640, str(at.canh_goc_raw(f)))
(tam / "hong.NEF").write_bytes(b"khong phai raw")
ktra("file hỏng -> 0", at.canh_goc_raw(tam / "hong.NEF") == 0)
ktra("không có file -> 0", at.canh_goc_raw(tam / "khong_co.ARW") == 0)

print("2. _quy_goc")


def nc(rong=1400, cao=932, ty_le=0.875):
    return types.SimpleNamespace(anh=np.zeros((cao, rong, 3), np.uint8), ty_le=ty_le)


n = nc()
xem_truoc._quy_goc(n, {"canh_goc": 6064})
ktra("ảnh trung gian 1400 px, gốc 6064 -> ty_le 1400/6064 (ngưỡng 150 px -> 35, sàn 40)",
     abs(n.ty_le - 1400 / 6064) < 1e-9, f"{n.ty_le:.4f}")
n = nc()
xem_truoc._quy_goc(n, {})
ktra("không có canh_goc -> giữ ty_le của engine", n.ty_le == 0.875)
n = nc()
xem_truoc._quy_goc(n, {"canh_goc": 1000})
ktra("canh_goc nhỏ hơn ảnh đang mở (vô lý) -> giữ nguyên", n.ty_le == 0.875)

print("3. retouch_may gửi canh_goc")
import retouch_may  # noqa: E402

gui = []


class MayGia:
    def gui(self, **kw):
        gui.append(kw)
        return True


w = types.SimpleNamespace(_xem_cho_fp=None, _may_xem=MayGia(), _xem_san_sang=True, _xem_mo_dang=None,
                          _xem_fp=None, _xem_goc_im=None)
raw = str(tam / "NVQ_6851.NEF")
w._fp_that = lambda p: str(tam / "lr_render.jpg") if p == raw else p
w._canh_goc = lambda p: 6064
ham = None
for ten in dir(retouch_may.MayMixin):
    fn = getattr(retouch_may.MayMixin, ten)
    if callable(fn) and getattr(fn, "__code__", None) and "mo_anh" in fn.__code__.co_consts:
        ham = fn
        break
if ham is None:                                              # tên hàm gửi lệnh mở ảnh
    for ten, fn in vars(retouch_may.MayMixin).items():
        if callable(fn) and "canh_goc" in getattr(fn, "__code__", types.SimpleNamespace(co_names=())).co_names:
            ham = fn
ktra("tìm được hàm gửi lệnh mo_anh", ham is not None)
if ham is not None:
    ham(w, raw)
    ktra("ảnh RAW: gửi ảnh trung gian + canh_goc 6064", gui and gui[-1].get("fp", "").endswith("lr_render.jpg")
         and gui[-1].get("canh_goc") == 6064, str(gui[-1:]))
    w._xem_mo_dang = None
    w._canh_goc = lambda p: (_ for _ in ()).throw(AssertionError("không được hỏi cạnh gốc"))
    ham(w, str(tam / "da_xuat.jpg"))
    ktra("ảnh đã xuất (không trung gian): canh_goc = 0, không đọc header", gui[-1].get("canh_goc") == 0,
         str(gui[-1:]))

print()
print("TẤT CẢ ĐẠT" if not LOI else f"{len(LOI)} LỖI: " + "; ".join(LOI))
sys.exit(1 if LOI else 0)
