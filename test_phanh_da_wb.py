#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phanh da theo WB Lightroom (11/10) — at.he_so_da_wb + at.phanh_da_sau_wb.

CHUYỆN ĐANG SỬA
    User 11/10: "WB -> Tone -> HSL -> CG, mỗi bước check lại tình trạng da rồi mới
    quyết bước sau". Phanh da đo vùng sáng của da (face_p95) trên PREVIEW máy —
    render ở WB MÁY. Lightroom render ở WB preset + phần tool kéo: WB ấm hơn thì
    kênh R của da cao hơn (dễ cháy hơn tool tưởng), lạnh hơn thì thấp hơn (ca kỷ
    yếu raw 19.4: preview R 251-252, Lightroom 4000 K chỉ 218 — phanh ghìm 0 oan).

Mục kiểm
    1. DEFAULTS bật.
    2. Chặng 1 (trong phanh): preset LẠNH hơn WB máy -> nới phanh (sáng hơn lúc
       tắt), có cờ da-theo-wb-; preset ẤM hơn -> siết (tối hơn), cờ da-theo-wb+.
    3. Preview đã bão hoà (p95 >= 250) -> KHÔNG nới.
    4. Chặng 2: WB cuối ấm lên (temp_adj) -> hạ Exposure, cờ ha-vi-da-sau-wb;
       mức hạ không quá log2 hệ số WB; không xuống dưới 0.
    5. WB cuối lạnh đi / delta <= 0 / wb off / tắt khoá -> không đổi.
    6. Cả LOẠT hạ cùng mức thấp nhất.

Chạy:  python test_phanh_da_wb.py
"""
from __future__ import annotations

import contextlib
import io
import math
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at          # noqa: E402
import test_san_phang as ts    # noqa: E402

T0 = datetime(2026, 10, 11, 10, 0, 0)


def anh(ten, p95, temp_preset, k_may, mat=-1.6):
    r = ts._anh(ten, mat, T0)
    r["face_p95"] = p95
    r["face_rgb"] = [0.50, 0.30, 0.18]
    r["wb_may_K"] = k_may
    r["crs"] = {"Temperature": str(temp_preset), "Tint": "10", "WhiteBalance": "Custom",
                "Exposure2012": "0"}
    return r


def decide(r, **kw):
    cfg = ts._cfg(source="catalog", wb="off", max_ev_up=1.0, **kw)
    ds = [r]
    with contextlib.redirect_stderr(io.StringIO()):
        at.group_scenes(ds, 5.0)
        at.decide(ds, cfg)
    return ds[0]


def anh2(ten, delta, temp_adj, p95=0.85, loat=None):
    """Ảnh đã qua decide: preset 5250 = WB máy, tool kéo temp_adj."""
    r = ts._anh(ten, -1.2, T0)
    r.update(face_p95=p95, face_rgb=[0.50, 0.30, 0.18], wb_may_K=5250, delta_ev=delta,
             temp_adj=temp_adj, tint_adj=0.0, crs_nen={"Temperature": "5250", "Tint": "10"},
             atn={}, asshot_K=5250.0, loat=loat)
    return r


def main() -> int:
    loi: list = []
    if not (at.DEFAULTS.get("phanh_da_theo_wb") and at.DEFAULTS.get("phanh_da_wb_nha")):
        loi.append("DEFAULTS: phanh_da_theo_wb + phanh_da_wb_nha phai BAT (11/10)")

    # 2 — chặng 1
    tat = decide(anh("lanh", 0.92, 4000, 5400), phanh_da_theo_wb=False)
    bat = decide(anh("lanh", 0.92, 4000, 5400))
    if not (bat["delta_ev"] > tat["delta_ev"] + 0.1 and "da-theo-wb-" in bat["notes"]):
        loi.append(f"Preset LANH hon may: phai noi phanh ({tat['delta_ev']} -> {bat['delta_ev']}, {bat['notes']})")
    tat = decide(anh("am", 0.86, 6500, 5000), phanh_da_theo_wb=False)
    bat = decide(anh("am", 0.86, 6500, 5000))
    if not (bat["delta_ev"] < tat["delta_ev"] - 0.1 and "da-theo-wb+" in bat["notes"]):
        loi.append(f"Preset AM hon may: phai siet phanh ({tat['delta_ev']} -> {bat['delta_ev']}, {bat['notes']})")
    print(f"  chang 1 (preset am hon may): delta {tat['delta_ev']:+.2f} -> {bat['delta_ev']:+.2f}")

    # 3 — bão hoà: không nới
    tat = decide(anh("bh", 0.985, 4000, 5400), phanh_da_theo_wb=False)
    bat = decide(anh("bh", 0.985, 4000, 5400))
    if abs(bat["delta_ev"] - tat["delta_ev"]) > 1e-6:
        loi.append(f"Preview bao hoa (p95 251): khong duoc noi phanh ({tat['delta_ev']} -> {bat['delta_ev']})")

    # 4 — chặng 2: WB cuối ấm lên
    cfg = dict(at.DEFAULTS, wb="skin")
    r = anh2("w", 0.60, 900.0, p95=0.86)
    k = at.he_so_da_wb(r, cfg, 0.86 * 255.0,
                       (5250.0 + 900.0, at.preset_val(r, "Tint")))
    at.phanh_da_sau_wb([r], cfg)
    if not (k > 1.0 and r["delta_ev"] < 0.60 and "ha-vi-da-sau-wb" in r["notes"]):
        loi.append(f"WB cuoi am len: phai ha Exposure (k {k:.3f}, delta {r['delta_ev']}, {r['notes']})")
    if 0.60 - r["delta_ev"] > math.log2(k) + 1e-6:
        loi.append(f"Muc ha {0.60 - r['delta_ev']:.3f} vuot log2 he so WB {math.log2(k):.3f}")
    print(f"  chang 2: WB +900 K -> he so {math.log2(k):+.3f} EV, delta 0.60 -> {r['delta_ev']:+.3f}")
    r = anh2("w0", 0.05, 2000.0, p95=0.95)
    at.phanh_da_sau_wb([r], cfg)
    if r["delta_ev"] < 0:
        loi.append("Chang 2 khong duoc ha xuong duoi 0")

    # 5 — không đổi
    for ten_, r_, c_ in (("WB lanh di", anh2("c", 0.6, -900.0, p95=0.86), cfg),
                         ("delta <= 0", anh2("d", -0.2, 900.0, p95=0.86), cfg),
                         ("wb off", anh2("o", 0.6, 900.0, p95=0.86), dict(cfg, wb="off")),
                         ("tat khoa", anh2("t", 0.6, 900.0, p95=0.86), dict(cfg, phanh_da_theo_wb=False))):
        d0 = r_["delta_ev"]
        at.phanh_da_sau_wb([r_], c_)
        if r_["delta_ev"] != d0:
            loi.append(f"{ten_}: chang 2 khong duoc doi delta ({d0} -> {r_['delta_ev']})")

    # 6 — loạt
    a, b = anh2("l1", 0.6, 900.0, p95=0.86, loat=7), anh2("l2", 0.6, 900.0, p95=0.70, loat=7)
    at.phanh_da_sau_wb([a, b], cfg)
    if abs(a["delta_ev"] - b["delta_ev"]) > 1e-9 or a["delta_ev"] >= 0.6:
        loi.append(f"Loat: phai ha CUNG muc thap nhat ({a['delta_ev']} / {b['delta_ev']})")

    for m in loi:
        print("  [!]", m)
    print("TAT CA DAT" if not loi else f"{len(loi)} LOI")
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
