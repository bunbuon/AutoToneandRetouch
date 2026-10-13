#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Toán curve điểm Lightroom (curve_lr.py — 13/10).

CHUYỆN ĐANG CANH
    Curve da / nén cháy GHÉP vào curve của preset (tổng 138,132 + R/G/B — chất ảnh SAY)
    chứ không ghi đè. Sai ở đây là đổi màu cả ảnh mà không ai thấy ngay: ghép lệch, curve
    gợn sóng (spline C2 vượt quá giữa hai nút), mất curve preset ngoài dải chỉnh.

Mục kiểm
    1. spline đi QUA mọi nút; hai nút -> đường thẳng; ngoài hai đầu giữ y của nút
    2. ghép g đồng nhất -> trả đúng các nút cũ
    3. ghép bump da: lệch so với g∘cũ ≤ 1 mã, đơn điệu, NGOÀI dải lệch curve preset ≤ 1 mã
    4. ghép nén đỉnh: dưới knee như cũ, đỉnh 255 -> 255 − d
    5. bump: chân nằm TRONG [lo, hi] (cắt ngang chân là curve gãy bậc)
    6. ô curve: đọc / ghi qua lại; ô hỏng -> None
    7. đổi màu sRGB <-> miền curve qua lại; trắng -> trắng
    8. ap_mien (ảnh đã dựng với curve cũ -> curve mới) = dựng thẳng bằng curve mới

Chạy:  python test_curve_lr.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import curve_lr as cl  # noqa: E402

LOI = []
PRESET = [(0, 0), (64, 60), (138, 132), (255, 255)]
X = np.linspace(0, 255, 1021)


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


def muc1():
    f = cl.spline(PRESET)
    ktra("spline qua mọi nút", all(abs(float(f(np.array([x]))[0]) - y) < 1e-9 for x, y in PRESET))
    g = cl.spline([(0, 0), (255, 255)])
    ktra("hai nút -> đường thẳng", float(np.max(np.abs(g(X) - X))) < 1e-9)
    h = cl.spline([(20, 30), (200, 220)])
    ktra("ngoài hai đầu giữ y của nút", float(h(np.array([0.0]))[0]) == 30
         and float(h(np.array([255.0]))[0]) == 220)
    #  dng_spline_solver: giá trị tham chiếu tính tay cho (0,0)(64,60)(138,132)(255,255)
    #  ghim bản chép dng_spline_solver: f(100) của curve preset tính bằng thuật toán gốc
    ktra("giữa nút: = bản chép dng_spline_solver (f(100) = 94.480)",
         abs(float(f(np.array([100.0]))[0]) - 94.48007374) < 1e-4, f"{float(f(np.array([100.0]))[0]):.5f}")
    ktra("giữa nút: f(200) = 196.227", abs(float(f(np.array([200.0]))[0]) - 196.22718603) < 1e-4)


def muc2():
    ktra("ghép đồng nhất -> nút cũ y nguyên", cl.ghep(lambda y: y, PRESET) == [(float(x), float(y))
                                                                              for x, y in PRESET])


def muc3():
    f = cl.spline(PRESET)
    for a, b, d in ((0.55, 0.75, 0.03), (0.40, 0.60, -0.03), (0.30, 0.80, 0.01)):
        w = cl.bump(a, b, 0.10, 0.06, 0.92)
        g = cl.g_da(d, w)
        moi = cl.ghep(g, PRESET)
        s = cl.spline(moi)(X)
        dich = g(f(X))
        ktra(f"ghép bump {a}-{b} Δ{d:+}: lệch g∘cũ ≤ 1 mã", float(np.max(np.abs(s - dich))) <= 1.0,
             f"{float(np.max(np.abs(s - dich))):.2f} mã, {len(moi)} điểm")
        ktra(f"ghép bump {a}-{b}: đơn điệu", bool(np.all(np.diff(s) >= -1e-6)))
        fx = f(X)
        ngoai = (fx < (a - 0.10) * 255 - 2) | (fx > (b + 0.10) * 255 + 2)
        ktra(f"ghép bump {a}-{b}: ngoài dải giữ curve preset (≤ 1 mã)",
             float(np.max(np.abs(s[ngoai] - fx[ngoai]))) <= 1.0)
        ktra(f"ghép bump {a}-{b}: không quá {cl.DIEM_TOI_DA} điểm", len(moi) <= cl.DIEM_TOI_DA)


def muc4():
    h = cl.h_chay(0.82, 15)
    moi = cl.ghep(h, PRESET)
    s, f = cl.spline(moi), cl.spline(PRESET)
    duoi = f(X) < 0.82 * 255 - 3
    ktra("nén đỉnh: dưới knee như curve preset (≤ 1 mã)",
         float(np.max(np.abs(s(X)[duoi] - f(X)[duoi]))) <= 1.0)
    ktra("nén đỉnh: 255 -> 240", abs(float(s(np.array([255.0]))[0]) - 240) <= 0.5,
         str(moi[-1]))


def muc5():
    w = cl.bump(0.55, 0.75, 0.10, 0.06, 0.76)
    y = np.linspace(0, 1, 2001)
    v = w(y)
    ktra("bump: không nhảy bậc (chân nằm trong [lo, hi])", float(np.max(np.abs(np.diff(v)))) < 0.02,
         f"bước lớn nhất {float(np.max(np.abs(np.diff(v)))):.3f}")
    ktra("bump: = 0 ngoài [lo, hi]", float(v[y > 0.76].max(initial=0)) == 0 and float(v[y < 0.06].max()) == 0)


def muc6():
    o = cl.ghi_o(PRESET)
    ktra("ô curve: ghi -> '0,0,64,60,138,132,255,255'", o == "0,0,64,60,138,132,255,255", o)
    ktra("ô curve: đọc lại", cl.doc_o(o) == [(0.0, 0.0), (64.0, 60.0), (138.0, 132.0), (255.0, 255.0)])
    for hong in ("0,0,64", "", "0,0,300,255", "0,0,70,1,60,2,255,255", None):
        ktra(f"ô hỏng {hong!r} -> None", cl.doc_o(hong) is None)


def muc7():
    px = np.random.default_rng(0).random((5000, 3))
    for m in cl.MIEN:
        lai = cl.mien_sang_srgb(cl.srgb_sang_mien(px, m), m)
        ktra(f"sRGB <-> miền {m}: qua lại", float(np.max(np.abs(lai - px))) < 1e-6)
    tr = cl.srgb_sang_mien(np.array([[1.0, 1.0, 1.0]]))
    ktra("trắng sRGB -> trắng miền curve", float(np.max(np.abs(tr - 1.0))) < 1e-5, str(tr))


def muc8():
    h = cl.h_chay(0.84, 12)
    w = cl.bump(0.45, 0.65, 0.10, 0.06, 0.80)
    g = cl.g_da(0.02, w)
    cu = {"master": PRESET, "r": [(0, 0), (128, 135), (255, 255)], "b": [(0, 0), (120, 115), (255, 255)]}
    moi = {"master": cl.ghep(h, cu["master"]), "r": cl.ghep(g, cu["r"]), "b": cu["b"]}
    u = np.random.default_rng(1).random((20000, 3))

    def dung(v, cv, kieu):
        bt = cl.bang(cv.get("master") or cl.DONG_NHAT)
        p = cl._rgb_tone(v, lambda t: cl._ap_bang(t, bt)) if kieu == "rgb_tone" else cl._ap_bang(v, bt)
        out = np.empty_like(p)
        for i, c in enumerate(cl.KENH):
            out[..., i] = cl._ap_bang(p[..., i], cl.bang(cv.get(c) or cl.DONG_NHAT))
        return out
    for kieu in cl.KIEU_TONG:
        a, b = dung(u, cu, kieu), dung(u, moi, kieu)
        c = cl.ap_mien(a, cu, moi, kieu)
        ktra(f"ap_mien ({kieu}) = dựng thẳng bằng curve mới", float(np.max(np.abs(b - c))) * 255 < 0.05,
             f"{float(np.max(np.abs(b - c))) * 255:.4f} mã")


def main():
    for m in (muc1, muc2, muc3, muc4, muc5, muc6, muc7, muc8):
        print(m.__doc__ or m.__name__)
        try:
            m()
        except Exception as ex:                                  # noqa: BLE001
            ktra(f"{m.__name__} không sập", False, repr(ex))
    print(f"\n{len(LOI)} LOI" if LOI else "\nTAT CA DAT")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
