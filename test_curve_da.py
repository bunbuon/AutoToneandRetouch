#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Curve da mặt + nén vùng cháy đo trên ảnh Lightroom dựng (curve_da.py — 13/10).

CHUYỆN ĐANG CANH
    User 13/10: "đo lại da trên từng pixel sau WB + Tone rồi can thiệp các kênh Curve cho
    da đúng màu đích; WB + Tone xong mà vẫn cháy thì can thiệp Curve". Chốt: đo trên ảnh
    Lightroom dựng, nén ĐỈNH curve tổng, vùng trắng không được ám.

    Ảnh "Lightroom dựng" ở đây là ảnh GIẢ dựng trong miền curve (mặt da lệch đích một
    lượng đã biết, mảng xám cùng độ sáng da, mảng trắng, khối cháy, đốm bóng); bộ dò mặt
    và mô hình phân vùng được thay bằng bản giả cho ảnh giả. Mọi phần còn lại là hàm THẬT:
    mat_na_da.mat_na, curve_da.do_anh / giai_da / giai_chay / ket_thuc, at.chia_loat,
    curve_lr (ghép + mô phỏng). Ảnh sau khi đổi curve = curve_lr.ap_anh của ảnh dựng — rồi
    ĐO LẠI bằng do_anh như một ảnh Lightroom mới.

Mục kiểm
    1. da lệch đích -> curve kênh đưa về (hue ≤ 1°, chroma ≤ 5%) — đo LẠI trên ảnh sau
    2. da đúng đích -> không đổi curve
    3. vùng xám cùng độ sáng da chiếm nhiều -> thu Δ, xám lệch ≤ 0.003 (đo lại)
    4. mảng trắng L 0.9 không đổi (≤ 0.5 mã); ngoài dải da ảnh y nguyên
    5. trần |Δ| ≤ curve_da_tran; da rất đỏ: hue KHÔNG xa đích hơn, chroma gần hơn
    6. trong / ngoài trời -> đích tương ứng
    7. cháy 10% -> sau < 2%; điểm < 200 lệch ≤ 0.5 mã; 1.5% không kích; đốm bóng 3% không
       kích; da p95 > 0.90 bỏ; cháy 40% đỉnh ≥ 235
    8. loạt: hai tấm cùng loạt một curve (trung vị); tấm không mặt trong loạt theo loạt;
       tấm không mặt ngoài loạt không curve kênh
    9. job @curve: chỉ ảnh có đổi, tên "Custom", ghép vào curve MỐC

Chạy:  python test_curve_da.py
"""
from __future__ import annotations

import math
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at  # noqa: E402
import curve_da as cd  # noqa: E402
import curve_lr as cl  # noqa: E402
import mat_na_da as mn  # noqa: E402

LOI = []
TAM = Path(tempfile.mkdtemp(prefix="test_curve_da_"))
MIEN = "melissa"
W, H = 900, 600
MAT = (360, 160, 180, 240)                     # khung mặt (x, y, w, h)
MOC = {"ToneCurveName2012": "Custom", "ToneCurvePV2012": "0,0,64,60,138,132,255,255",
       "ToneCurvePV2012Red": "0,0,255,255", "ToneCurvePV2012Green": "0,0,255,255",
       "ToneCurvePV2012Blue": "0,0,255,255"}


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


# ------------------------------------------------------------------ ảnh giả

def _lin_mien(lin):
    return cl.tuyen_tinh_sang_mien(np.asarray(lin, dtype=np.float64), MIEN)


def canh(da_rgb=(227, 184, 185), lech=(0.0, 0.0, 0.0), xam_pct=0.0, chay_pct=0.0,
         dom_pct=0.0, da_sang=1.0, seed=0, mat_mau_da=False) -> np.ndarray:
    """Ảnh "Lightroom dựng" ĐỘ CHÍNH XÁC CAO (sRGB float 0..1, (H, W, 3)) — Lightroom tính
    ảnh ở độ chính xác cao rồi làm tròn 8 bit MỘT lần khi xuất (u8()). Làm tròn ảnh đã
    làm tròn (đổi curve trên ảnh 8 bit) lệch hue ~0.7° ở da mịn — lỗi của bài kiểm, không
    phải của Lightroom. Nội dung: nền xám tối, mặt da màu `da_rgb` (độ sáng đổ bóng) LỆCH
    `lech` trong miền curve, mắt tối, môi đỏ, mảng trắng L 0.9, mảng xám CÙNG độ sáng da
    chiếm xam_pct % khung, khối cháy chay_pct %, đốm bóng (1 điểm) dom_pct %."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:H, 0:W]
    lin_nen = np.full((H, W, 3), 0.035)
    lin_nen *= (0.8 + 0.4 * xx / W)[..., None]
    img = _lin_mien(lin_nen)
    #  mặt: elip, đổ bóng theo x, nhiễu nhẹ
    cx, cy = MAT[0] + MAT[2] / 2, MAT[1] + MAT[3] / 2
    el = ((xx - cx) / (MAT[2] * 0.48)) ** 2 + ((yy - cy) / (MAT[3] * 0.50)) ** 2 <= 1
    goc = at.srgb_to_linear(np.asarray(da_rgb, dtype=np.float64) / 255.0)
    k = (0.30 + 0.25 * (xx - MAT[0]) / MAT[2]) * da_sang
    lin_da = goc[None, None, :] * k[..., None] * (1 + rng.normal(0, 0.015, (H, W, 1)))
    da = np.clip(_lin_mien(lin_da) + np.asarray(lech)[None, None, :], 0, 1)
    img[el] = da[el]
    #  mat_mau_da: mắt / môi CÙNG MÀU + độ sáng da (chỉ nhãn / hình loại được chúng —
    #  không để lọc tối / skin_mask làm thay mà bài kiểm vẫn tưởng mặt nạ đúng)
    for ex in (cx - 35, cx + 35):                                  # mắt
        o = ((xx - ex) ** 2 + (yy - (cy - 30)) ** 2) <= 12 ** 2
        img[o] = (np.clip(_lin_mien(goc * 0.45) + np.asarray(lech), 0, 1) if mat_mau_da
                  else _lin_mien([0.01, 0.008, 0.007]))
    moi = ((xx - cx) / 26) ** 2 + ((yy - (cy + 65)) / 9) ** 2 <= 1   # môi
    img[moi] = (np.clip(_lin_mien(goc * np.array([0.47, 0.40, 0.42])), 0, 1) if mat_mau_da
                else _lin_mien([0.25, 0.04, 0.05]))
    img[440:520, 40:200] = _lin_mien([0.75, 0.75, 0.75])            # trắng L ~0.9
    if xam_pct:
        Lda = float(np.median(at.srgb_to_linear(cl.mien_sang_srgb(img[el], MIEN)) @ at._SRGB_XYZ[1]))
        n = int(xam_pct / 100 * W * H)
        cao = max(1, n // 300)
        img[H - cao:H, 560:860] = _lin_mien([Lda, Lda, Lda])          # đáy phải
    if chay_pct:                       # khối cháy: dải phải rồi dải trái, KHÔNG đè lên mặt
        n = int(chay_pct / 100 * W * H)
        for x0, x1 in ((600, W), (0, 300)):
            cao = min(H, n // (x1 - x0))
            img[0:cao, x0:x1] = 1.0
            n -= cao * (x1 - x0)
            if n <= 0:
                break
    out = cl.mien_sang_srgb(img, MIEN)
    if dom_pct:
        n = int(dom_pct / 100 * W * H)
        ys = rng.integers(0, H // 2, n) * 2
        xs = rng.integers(0, W // 2, n) * 2
        out[ys, xs] = 1.0
    return out


def u8(f):
    return (np.clip(f, 0, 1) * 255 + 0.5).astype(np.uint8)


def gia_mat(img):
    x, y, w, h = MAT
    cx, cy = x + w / 2, y + h / 2
    return [(float(x), float(y), float(w), float(h), 0.95,
             [(cx - 35, cy - 30), (cx + 35, cy - 30), (cx, cy + 10), (cx - 25, cy + 65), (cx + 25, cy + 65)])]


def gia_phan_vung(crop):
    """Nhãn theo HÌNH cho ảnh giả (như mô hình thật: da cháy vẫn là da): elip mặt = 1,
    mắt = 4, môi = 12. Gốc ô cắt tính lại bằng chính mn._vung_cat."""
    x0, y0, _x1, _y1 = mn._vung_cat(gia_mat(None)[0], W, H)             # noqa: SLF001
    h, w = crop.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    xx, yy = xx + x0, yy + y0
    cx, cy = MAT[0] + MAT[2] / 2, MAT[1] + MAT[3] / 2
    L = np.zeros((h, w), np.uint8)
    L[((xx - cx) / (MAT[2] * 0.48)) ** 2 + ((yy - cy) / (MAT[3] * 0.50)) ** 2 <= 1] = 1
    for ex in (cx - 35, cx + 35):
        L[((xx - ex) ** 2 + (yy - (cy - 30)) ** 2) <= 12 ** 2] = 4
    L[((xx - cx) / 26) ** 2 + ((yy - (cy + 65)) / 9) ** 2 <= 1] = 12
    return L


def cai_gia():
    mn.tim_mat = gia_mat
    mn.nhan_vung = gia_phan_vung
    mn.trang_thai = lambda: {"co": True, "kieu": "gia", "duong": "", "ly_do": ""}
    #  14/10: hàm giả chỉ có trong tiến trình này — đo song song (curve_da.BoDo, tiến
    #  trình con) sẽ chạy mô hình THẬT. Bài kiểm dùng hàm giả thì đo tại chỗ.
    os.environ["AUTOTONE_CURVE_THO"] = "1"


def luu(arr, ten):
    p = TAM / f"{ten}.png"
    Image.fromarray(u8(arr) if arr.dtype != np.uint8 else arr).save(p)
    return p


def anh(ten="A", dt=None, ev=7.0, **kw):
    """Một ảnh của kế hoạch (r) — đủ khoá cho chia_loat / dich_cua / chon_anh."""
    return {"path": f"G:/Buoi/{ten}.ARW", "ok": True, "ev100": ev, "model": "ILCE-7M4",
            "scene": 0, "fnumber": 2.8, "exposure_time": 1 / 200, "iso": 800,
            "dt_obj": dt or datetime(2026, 10, 13, 10, 0, 0), "scene_sig": [0.5] * 16,
            "metered_subject_ev": -2.0, "meter_boxes": [list(MAT)], "preview_wh": (W, H),
            "ngoai_troi": ev >= 8.5, "curve_tt": "moc", "curve_moc": dict(MOC), **kw}


def cfg_(**kw):
    c = dict(at.DEFAULTS, curve_da=True, curve_chay=False)
    c.update(kw)
    return c


def dich_hq(r, cfg):
    rgb, _ng = cd.dich_cua(r, cfg, "cu")
    return cd.hue_q(at.mau_dich_lab(rgb))


def sau(arr, r):
    """Ảnh dựng lại (độ chính xác cao) với curve tool vừa ghép (r["curve_ghi"])."""
    moc = {c: cl.doc_o(r["curve_moc"][k]) for c, k in cl.KHOA.items()}
    moi = {c: cl.doc_o(r["curve_ghi"][k]) for c, k in cl.KHOA.items()}
    return cl.ap_anh(arr, moc, moi, MIEN)


def do_lai(arr, r, cfg, ten):
    return cd.do_anh(r, luu(arr, ten), cfg)


# ------------------------------------------------------------------ mục

def muc1():
    """1. da lệch đích -> curve kênh đưa về; đo LẠI trên ảnh sau"""
    cfg = cfg_()
    r = anh()
    a1 = canh(lech=(0.02, 0.0, -0.015))                  # trong trần curve_da_tran
    d1 = do_lai(a1, r, cfg, "m1a")
    cd.ket_thuc([r], {id(r): d1}, cfg)
    ktra("có curve ghi (Custom + 4 curve)", bool(r.get("curve_ghi"))
         and r["curve_ghi"].get("ToneCurveName2012") == "Custom")
    a2 = sau(a1, r)
    g2 = cd.giai_da(do_lai(a2, r, cfg, "m1b"), r, cfg)
    h_t, q_t = dich_hq(r, cfg)
    g1 = cd.giai_da(d1, r, cfg)
    ktra("trước: da lệch đích rõ", abs(g1["h0"] - h_t) > 3 or abs(g1["q0"] / q_t - 1) > 0.1,
         f"{g1['h0']:.1f}°/{g1['q0']:.3f} vs {h_t:.1f}°/{q_t:.3f}")
    ktra("sau: hue ≤ 1° so với đích", abs(cd._goc(g2["h0"] - h_t)) <= 1.0, f"{g2['h0']:.2f} vs {h_t:.2f}")
    ktra("sau: chroma/L ≤ 5% so với đích", abs(g2["q0"] / q_t - 1) <= 0.05, f"{g2['q0']:.4f} vs {q_t:.4f}")
    bao = r["curve_bao"]["da"]
    ktra("dự đoán (curve thật) khớp đo lại ≤ 0.5°", abs(bao["h1"] - g2["h0"]) <= 0.5,
         f"dự đoán {bao['h1']} đo {g2['h0']:.2f}")
    return a1, r


def muc2():
    """2. da đúng đích -> không đổi curve"""
    cfg = cfg_()
    r = anh()
    a1 = canh()
    d = do_lai(a1, r, cfg, "m2")
    g = cd.giai_da(d, r, cfg)
    cd.ket_thuc([r], {id(r): d}, cfg)
    ktra("da đúng đích: ly_do da-on, Δ = 0", g["ly_do"] == "da-on" and not any(g["delta"]),
         f"{g.get('h0', 0):.1f}° {g.get('q0', 0):.3f}")
    ktra("da đúng đích: không ghi curve", not r.get("curve_ghi"))


def muc3():
    """3. vùng xám cùng độ sáng da nhiều -> thu Δ; xám lệch ≤ 0.003 (đo lại)"""
    cfg = cfg_()
    r = anh()
    a1 = canh(lech=(0.035, 0.0, -0.025), xam_pct=6.0)
    d1 = do_lai(a1, r, cfg, "m3a")
    cd.ket_thuc([r], {id(r): d1}, cfg)
    da = r["curve_bao"]["da"]
    ktra("xám nhiều: Δ bị thu (thu < 1)", da.get("thu", 1.0) < 1.0, str(da.get("thu")))
    a1, a2 = u8(a1), u8(sau(a1, r))
    vung = (slice(H - 60, H), slice(560, 860))

    def ab(arr):
        lab = cd._lab_px(at.srgb_to_linear(arr[vung].reshape(-1, 3).astype(np.float32) / 255.0))
        return np.median(lab[:, 1]), np.median(lab[:, 2])
    (a0, b0), (a1_, b1_) = ab(a1), ab(a2)
    lech = math.hypot(a1_ - a0, b1_ - b0)
    ktra("xám cùng độ sáng da: lệch ab ≤ 0.003 (+ làm tròn 8 bit)", lech <= 0.0035, f"{lech:.4f}")


def muc4(a1, r):
    """4. trắng L 0.9 không đổi; ngoài dải da ảnh y nguyên"""
    a1, a2 = u8(a1), u8(sau(a1, r))
    tr = np.abs(a2[440:520, 40:200].astype(int) - a1[440:520, 40:200].astype(int)).max()
    ktra("mảng trắng L 0.9: lệch ≤ 1 mã (làm tròn)", tr <= 1, f"{tr}")
    nen = np.abs(a2[300:600, 0:300].astype(int) - a1[300:600, 0:300].astype(int)).max()
    ktra("nền tối ngoài dải da: lệch ≤ 1 mã", nen <= 1, f"{nen}")


def muc5():
    """5. trần |Δ|; da rất đỏ: hue không xa đích hơn, chroma gần hơn"""
    cfg = cfg_()
    r = anh()
    d = do_lai(canh(lech=(0.12, -0.03, -0.10)), r, cfg, "m5")
    g = cd.giai_da(d, r, cfg)
    tran = float(at.DEFAULTS["curve_da_tran"])
    ktra("trần: |Δ| ≤ curve_da_tran", max(abs(v) for v in g["delta"]) <= tran + 1e-9,
         str([round(v, 4) for v in g["delta"]]))
    h_t, q_t = g["h_t"], g["q_t"]
    ktra("da rất lệch: hue KHÔNG xa đích hơn", abs(cd._goc(g["h1"] - h_t)) <= max(abs(cd._goc(g["h0"] - h_t)), 3.0) + 1e-6,
         f"{g['h0']:.1f} -> {g['h1']:.1f} (đích {h_t:.1f})")
    ktra("da rất lệch: chroma gần đích hơn", abs(math.log(g["q1"] / q_t)) < abs(math.log(g["q0"] / q_t)),
         f"{g['q0']:.3f} -> {g['q1']:.3f} (đích {q_t:.3f})")


def muc6():
    """6. trong / ngoài trời -> đích tương ứng"""
    cfg = cfg_()
    t, n = at.dich_da_cuoi(cfg)
    rgb_t, ng_t = cd.dich_cua(anh(ev=6.0), cfg, "cu")
    rgb_n, ng_n = cd.dich_cua(anh(ev=12.0), cfg, "cu")
    ktra("EV100 thấp -> đích trong nhà", rgb_t == list(t) and not ng_t)
    ktra("EV100 cao -> đích ngoài trời", rgb_n == list(n) and ng_n, f"{rgb_n} vs {n}")
    md = {"trong": [230, 190, 180], "ngoai": [200, 160, 140], "trong_mn": [231, 188, 182],
          "ngoai_mn": [201, 158, 141]}
    c2 = cfg_(mau_da_dich=md)
    ktra("mẫu có số đo phân vùng: kieu mn -> đích *_mn", cd.dich_cua(anh(ev=12.0), c2, "mn")[0] == md["ngoai_mn"])


def muc7():
    """7. nén vùng cháy"""
    cfg = cfg_(curve_da=False, curve_chay=True)
    r = anh()
    a1 = canh(chay_pct=10.0)
    d1 = do_lai(a1, r, cfg, "m7a")
    cd.ket_thuc([r], {id(r): d1}, cfg)
    ktra("cháy 10%: có nén", r.get("curve_bao", {}).get("chay", {}).get("d", 0) > 0,
         str(r.get("curve_bao", {}).get("chay")))
    a2 = sau(a1, r)
    d2 = do_lai(a2, r, cfg, "m7b")
    ktra("cháy 10% -> sau < 2%", d2["chay_pct"] < 2.0, f"{d1['chay_pct']:.2f} -> {d2['chay_pct']:.2f}")
    a1, a2 = u8(a1), u8(a2)
    duoi = a1.max(axis=2) < 200
    lech = np.abs(a2.astype(int) - a1.astype(int)).max(axis=2)[duoi].max()
    ktra("điểm < 200: lệch ≤ 1 mã (làm tròn)", lech <= 1, str(lech))
    for pct, ten in ((1.5, "cháy 1.5%"),):
        g = cd.giai_chay(do_lai(canh(chay_pct=pct), r, cfg, "m7c"), cfg)
        ktra(f"{ten}: không kích", g["d"] == 0, g["ly_do"])
    g = cd.giai_chay(do_lai(canh(dom_pct=3.0), r, cfg, "m7d"), cfg)
    ktra("đốm bóng 3% (điểm lẻ): không kích", g["d"] == 0, f"{g['chay_pct']:.2f}% {g['ly_do']}")
    #  da cháy HẲN (mọi điểm da ≥ 250): mặt nạ đã lọc rỗng, vẫn phải biết da ở đỉnh
    d = do_lai(canh(chay_pct=10.0, da_sang=6.0), r, cfg, "m7e")
    g = cd.giai_chay(d, cfg)
    ktra("da p95 > 0.90: bỏ (da-sang)", g["ly_do"] == "da-sang", f"p95 {d['p95_da']:.3f}")
    #  trần nén nới ra 40 mã: chỉ còn SÀN đỉnh 235 giữ lại
    g = cd.giai_chay(do_lai(canh(chay_pct=40.0), r, cfg, "m7f"), dict(cfg, curve_chay_d_max=40))
    ktra("cháy 40%: đỉnh ≥ 235", g["d"] > 0 and 255 - g["d"] >= at.DEFAULTS["curve_chay_san"] - 1e-9,
         f"d {g['d']:.1f}")


def muc8():
    """8. gom loạt"""
    cfg = cfg_()
    t0 = datetime(2026, 10, 13, 10, 0, 0)
    r1, r2 = anh("L1", t0), anh("L2", t0 + timedelta(seconds=5))
    r3 = anh("L3", t0 + timedelta(seconds=9), meter_boxes=[])            # loạt, không mặt
    r4 = anh("X4", t0 + timedelta(hours=2), meter_boxes=[], scene=5)     # lẻ, không mặt
    d1 = do_lai(canh(lech=(0.03, 0, -0.02)), r1, cfg, "m8a")
    d2 = do_lai(canh(lech=(0.05, 0, -0.03), seed=1), r2, cfg, "m8b")
    trang = canh()
    trang[MAT[1]:MAT[1] + MAT[3], MAT[0]:MAT[0] + MAT[2]] = 0.12        # xoá mặt
    cd.mn.tim_mat = lambda img: []
    d3 = do_lai(trang, r3, cfg, "m8c")
    d4 = do_lai(trang, r4, cfg, "m8d")
    cai_gia()
    ds = [r1, r2, r3, r4]
    ktra("chia_loat thật: L1, L2, L3 một loạt", any({id(x) for x in l} == {id(r1), id(r2), id(r3)}
                                                    for l in at.chia_loat(ds, cfg)))
    cd.ket_thuc(ds, {id(r1): d1, id(r2): d2, id(r3): d3, id(r4): d4}, cfg)
    k = "ToneCurvePV2012Red"
    ktra("cùng loạt: một curve", r1.get("curve_ghi", {}).get(k) == r2.get("curve_ghi", {}).get(k)
         and r1.get("curve_ghi"), str(r1.get("curve_ghi", {}).get(k)))
    ktra("tấm không mặt trong loạt: theo loạt", r3.get("curve_ghi", {}).get(k) == r1.get("curve_ghi", {}).get(k))
    ktra("tấm không mặt ngoài loạt: không curve kênh", not r4.get("curve_ghi"))
    ktra("chon_anh: chỉ bật da -> bỏ tấm lẻ không mặt", [x["path"] for x in cd.chon_anh(ds, cfg)]
         == [r1["path"], r2["path"], r3["path"]])


def muc9():
    """9. job @curve"""
    cfg = cfg_()
    r1, r2 = anh("J1"), anh("J2", datetime(2026, 10, 13, 12, 0, 0), scene=3)
    d1 = do_lai(canh(lech=(0.03, 0, -0.02)), r1, cfg, "m9a")
    d2 = do_lai(canh(), r2, cfg, "m9b")
    cd.ket_thuc([r1, r2], {id(r1): d1, id(r2): d2}, cfg)
    job = cd.ghi_job([r1, r2], "Buoi X", TAM / "jobs")
    ktra("tên job apply_<giờ>_<buổi>@curve.tsv", job is not None and job.name.endswith(f"{at.ten_job('Buoi X')}@curve.tsv"),
         job.name if job else "")
    rows = cd.doc_job(job)
    ktra("chỉ ảnh có đổi", list(rows) == [at.khoa_duong_dan(r1["path"])], str(list(rows)))
    row = rows[at.khoa_duong_dan(r1["path"])]
    ktra("cột = path + COT_CURVE", list(row) == ["path", *at.COT_CURVE])
    tong = cl.doc_o(row["ToneCurvePV2012"])
    ktra("curve tổng = curve mốc (không nén cháy)", tong == cl.doc_o(MOC["ToneCurvePV2012"]))


def muc10():
    """10. curve_da_sang (14/10): da TỐI hơn đích -> kéo cả L; tắt -> giữ L"""
    r = anh("S1")
    a = canh(da_rgb=(209, 169, 170))                    # cùng màu đích, tối hơn
    cfg0 = cfg_()
    d = do_lai(a, r, cfg0, "m10")
    g0 = cd.giai_da(d, r, cfg0)
    ktra("tắt: màu trong vùng ổn -> không đổi (giữ L như 13/10)", not any(g0["delta"]),
         f"{g0.get('ly_do')} L {g0.get('L0', 0):.3f} -> đích {g0.get('L_t', 0):.3f}")
    cfg1 = cfg_(curve_da_sang=True)
    g1 = cd.giai_da(d, r, cfg1)
    ktra("bật: Δ dương cả ba kênh, L da lên gần đích hơn", all(v > 0 for v in g1["delta"])
         and abs(g1["L1"] - g1["L_t"]) < abs(g1["L0"] - g1["L_t"]) - 0.005,
         f"Δ {[round(v, 3) for v in g1['delta']]} · L {g1['L0']:.3f} -> {g1['L1']:.3f} (đích {g1['L_t']:.3f})")
    ktra("bật: màu vẫn trong vùng ổn", abs(cd._goc(g1["h1"] - g1["h_t"])) <= 3.0
         and abs(g1["q1"] / g1["q_t"] - 1) <= 0.10, f"{g1['h1']:.1f}° {g1['q1']:.4f}")
    #  ảnh giả có đổ bóng nên L da đo < L màu đích; nới vùng ổn L để "đúng đích cả sáng"
    cfg2 = cfg_(curve_da_sang=True, da_on_L=0.30)
    g2 = cd.giai_da(do_lai(canh(), r, cfg2, "m10b"), r, cfg2)
    ktra("bật + màu đúng đích + L trong vùng ổn -> không đổi", not any(g2["delta"]) and g2["ly_do"] == "da-on",
         f"{g2.get('ly_do')} L {g2.get('L0', 0):.3f}/{g2.get('L_t', 0):.3f}")


def main():
    cai_gia()
    a1 = r = None
    for m in (muc1, muc2, muc3, muc4, muc5, muc6, muc7, muc8, muc9, muc10):
        print(m.__doc__.splitlines()[0])
        try:
            if m is muc4:
                if a1 is not None:
                    m(a1, r)
            elif m is muc1:
                a1, r = m()
            else:
                m()
        except Exception as ex:                                  # noqa: BLE001
            import traceback
            traceback.print_exc()
            ktra(f"{m.__name__} không sập", False, repr(ex))
    shutil.rmtree(TAM, ignore_errors=True)
    print(f"\n{len(LOI)} LOI" if LOI else "\nTAT CA DAT")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
