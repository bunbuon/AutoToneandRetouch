# -*- coding: utf-8 -*-
"""Ảnh LENS CƠ (fisheye 10mm, EXIF khẩu = 0) — đo sáng đồng đều trong loạt (8/10).

CHUYỆN ĐANG SỬA (buổi kỷ yếu "raw 19.4", 748/1089 ảnh fisheye 10mm không tiếp điểm)
    Cùng 1/200 ISO 500, cùng cảnh, khung sáng y hệt mà HUY04802-04804 bị kéo
    +0.70..+0.92 EV còn tấm trước / sau −0.13..−0.46 — người dùng: "cùng thông
    số chụp mà đo sáng khác nhau". Hai lỗi chồng nhau:
      1. measure() chọn CHỦ THỂ theo điểm AF (vô nghĩa với lens lấy nét tay) và
         theo ĐỘ NÉT (fisheye nét hết; nền nhiều cạnh làm mặt hậu cảnh tí hon
         "nét" hơn mặt chính to) -> đo sáng trên mặt hậu cảnh 12x15 px tối −3 EV.
      2. Hai lưới an toàn sua_mat_lech_khung + chia_loat (đồng bộ loạt) gom ảnh
         theo "cùng khẩu/tốc/ISO" — khẩu = 0 nên bỏ qua MỌI ảnh fisheye.

Mục kiểm (plan() THẬT, ảnh giả)
    1. Loạt lens cơ 10 tấm, 3 tấm LIỀN NHAU đo nhầm mặt (−3 EV, khung y hệt) ->
       cả 3 bị bắt ("do-mat-lech-khung"), cả loạt ra CÙNG một mức, bằng mức
       các tấm đo đúng; tấm đo đúng KHÔNG bị đụng.
    2. Cùng tình huống nhưng lens thường (khẩu 2.8): như cũ — sua_mat_lech_khung
       vẫn tắt (mat_lech_khung_ev = 0) nên 3 tấm kia giữ phép đo của chúng.
    3. chia_loat nhận ảnh lens cơ (khẩu "?") — trước đây trả về 0 loạt.

Chạy:  python kiem_lens_co.py
"""
from __future__ import annotations

import contextlib
import copy
import io
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at          # noqa: E402
import test_san_phang as ts    # noqa: E402

LOI: list = []
T0 = datetime(2026, 4, 19, 9, 53, 40)
SIG = [0.9, 0.8, 1.0, 1.1] * 18
NHAM = (3, 4, 5)


def ktra(ten, ok, ct=""):
    print(f"  [{'DAT ' if ok else 'HONG'}] {ten}  {ct}")
    if not ok:
        LOI.append(ten)


def loat(khau: float) -> list:
    ds = []
    for i in range(10):
        mat = -3.0 if i in NHAM else -0.75 + 0.03 * (i % 3)
        r = ts._anh(f"HUY0{4800 + i}", mat, T0 + timedelta(seconds=3 * i))
        r["metered_subject_ev"] = -3.5 + 0.02 * (i % 2)
        r["scene_sig"] = [v + 0.01 * (i % 3) for v in SIG]
        r["fnumber"], r["exposure_time"], r["iso"] = khau, 1 / 200, 500
        r["model"] = "ILCE-7M4"
        ds.append(r)
    return ds


def chay(ds, **kw):
    cfg = ts._cfg(**kw)
    ds = copy.deepcopy(ds)
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        at.plan(ds, cfg, None, None)
    return ds


def main() -> int:
    # ---- 1. lens co
    ds = chay(loat(0.0))
    nham = [r for i, r in enumerate(ds) if i in NHAM]
    dung = [r for i, r in enumerate(ds) if i not in NHAM]
    ktra("lens cơ: 3 tấm đo nhầm liền nhau đều bị bắt",
         all("do-mat-lech-khung" in r.get("notes", "") for r in nham),
         str([round(r["metered_face_ev"], 2) for r in nham]))
    ktra("… tấm đo đúng không bị đụng", not any("do-mat-lech-khung" in r.get("notes", "") for r in dung))
    ev = [r["delta_ev"] for r in ds]
    ktra("… cả loạt cùng một mức sáng (lệch ≤ 0.05 EV)", max(ev) - min(ev) <= 0.05,
         f"{min(ev):+.2f}..{max(ev):+.2f}")
    # ---- 2. lens thuong: nhu cu
    ds2 = chay(loat(2.8))
    ktra("lens thường: bước sửa mặt lệch khung vẫn TẮT như cũ",
         not any("do-mat-lech-khung" in r.get("notes", "") for r in ds2))
    # ---- 3. chia_loat
    cfg = ts._cfg()
    ds3 = copy.deepcopy(loat(0.0))
    with contextlib.redirect_stderr(io.StringIO()):
        at.group_scenes(ds3, cfg["gap_minutes"])
    ktra("chia_loat nhận ảnh lens cơ (khẩu \"?\")", len(at.chia_loat(ds3, cfg)) >= 1,
         f"{len(at.chia_loat(ds3, cfg))} loạt")
    print("TAT CA DAT" if not LOI else f"{len(LOI)} LOI: {LOI}")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
