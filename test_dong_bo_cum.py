# -*- coding: utf-8 -*-
"""CỤM CÙNG KHUNG (autotone.nhom_cum / dong_bo_cum / dong_bo_cum_luot2 — 14/10).

User 14/10 gửi 4 cặp ảnh 2709 chụp liên tiếp cùng khung mà sáng / màu khác nhau: "Phải giải
quyết triệt để vấn đề này". chia_loat đòi khẩu / tốc / ISO giống hệt + bố cục ≤ 0.10 + khung
≤ 0.25 EV nên các cặp đó thành nhóm riêng, mỗi nhóm WB / HSL / curve / Exposure riêng.

Mục kiểm
    1. gom: đổi ISO (DSC_9797/9798), thêm người ở mép (Δ bố cục 0.15), khung lệch 0.6 EV vì
       nội dung -> CÙNG cụm; bố cục khác hẳn / cách 45 s / flash khác / khác máy -> TÁCH
    2. dong_bo_cum: Exposure bù đúng phần chênh ISO (log2 1000/640 = 0.644 EV), WB / tông /
       HSL / Luminance / CG / curve = đại diện (kể cả khi mốc HSL hai ảnh lệch nhau)
    3. ảnh đen trắng không bị kéo; tắt dong_bo_cum -> không đổi gì
    4. lượt 2: curve / HSL lượt 2 của một tấm -> cả cụm

Chạy:  python test_dong_bo_cum.py
"""
from __future__ import annotations

import copy
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

for _l in (sys.stdout, sys.stderr):
    try:
        _l.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                        # noqa: BLE001
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at                                        # noqa: E402

LOI: list = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


T0 = datetime(2026, 9, 27, 8, 50, 30)
SIG = np.linspace(0.2, 0.8, 72)


def anh(ten, giay, iso=640, sig_lech=0.0, khung=-2.2, flash=0, model="NIKON Z 8", **kw):
    """Ảnh đã qua decide + compute_values (đủ ô job)."""
    h = math.log2(iso * 0.005 / 16.0)
    r = {"path": f"G:/2709/{ten}.NEF", "dt_obj": T0 + timedelta(seconds=giay), "model": model,
         "fnumber": 4.0, "exposure_time": 0.005, "iso": iso, "flash": flash,
         "scene_sig": list(SIG + sig_lech), "metered_subject_ev": khung + (h - math.log2(640 * 0.005 / 16.0)),
         "meter_boxes": [[10, 10, 50, 60]], "old_exposure": 0.0, "new_exposure": 0.0, "delta_ev": 0.0,
         "old_temp": 5000, "old_tint": 10, "new_temp": 5000, "new_tint": 10,
         "new_highlights": -29, "new_shadows": 16,
         "crs": {"HueAdjustmentOrange": "0", "SaturationAdjustmentOrange": "-13",
                 "LuminanceAdjustmentOrange": "18"},
         "crs_hien": {"HueAdjustmentOrange": "0", "SaturationAdjustmentOrange": "-13",
                      "ColorGradeMidtoneHue": "47", "ColorGradeMidtoneSat": "10",
                      "SplitToningHighlightHue": "234", "SplitToningHighlightSaturation": "13",
                      "ToneCurvePV2012": "0,0,255,255"},
         "notes": ""}
    r.update(kw)
    return r


def main() -> int:
    cfg = dict(at.DEFAULTS)
    print("1. gom cụm cùng khung")
    a = anh("DSC_9797", 0, iso=1000)
    b = anh("DSC_9798", 2.3, iso=640, sig_lech=0.086)
    c = anh("DSC_9799", 3.5, sig_lech=0.15)                     # thêm người ở mép khung
    d = anh("DSC_9800", 5.0, sig_lech=0.10, khung=-2.8)         # khung đo lệch 0.6 EV vì nội dung
    e = anh("DSC_9801", 7.0, sig_lech=0.6)                      # bố cục khác hẳn
    f = anh("DSC_9802", 52.0, sig_lech=0.6)                     # cách 45 s
    g_ = anh("DSC_9803", 54.0, sig_lech=0.6, flash=1)           # flash nổ
    s1 = anh("SUB_6700", 1.0, model="NIKON Z5_2")               # máy khác, xen giữa
    cum = at.nhom_cum([a, b, c, d, e, f, g_, s1], cfg)
    ten = sorted([[Path(r["path"]).stem for r in g] for g in cum])
    ktra("đổi ISO 1000 -> 640, thêm người ở mép, khung lệch 0.6 EV -> CÙNG cụm",
         ["DSC_9797", "DSC_9798", "DSC_9799", "DSC_9800"] in ten, str(ten))
    ktra("bố cục khác hẳn / cách 45 s / flash khác -> cụm riêng", ["DSC_9801"] in ten and ["DSC_9802"] in ten
         and ["DSC_9803"] in ten, str(ten))
    ktra("máy khác xen giữa -> riêng (không chen vào cụm Z 8)", ["SUB_6700"] in ten, str(ten))
    ktra("loạt cũ (chia_loat) tách cặp đổi ISO — lý do của lỗi", not any(
        {"DSC_9797", "DSC_9798"} <= {Path(r["path"]).stem for r in g} for g in at.chia_loat([a, b], cfg)))

    print("2. dong_bo_cum")
    a = anh("DSC_9797", 0, iso=1000, new_exposure=-0.26, delta_ev=-0.26, new_temp=4579, new_tint=8,
            hsl_ghi=True, hsl_moi={"HueAdjustmentRed": 0, "SaturationAdjustmentRed": 0, "HueAdjustmentOrange": 20,
                                   "SaturationAdjustmentOrange": -17, "HueAdjustmentYellow": 0,
                                   "SaturationAdjustmentYellow": 0},
            hsl_l_ghi=True, hsl_l_moi={"LuminanceAdjustmentOrange": 53})
    b = anh("DSC_9798", 2.3, iso=640, sig_lech=0.086, new_exposure=0.0, new_temp=5173, new_tint=10,
            new_highlights=-24, gr_ghi=True, gr_mid=(67, 2), gr_hi=(234, 13),
            curve_ghi_mot_luot={k: "0,0,128,140,255,255" for k in at.COT_CURVE},
            crs_hien={"HueAdjustmentOrange": "7", "SaturationAdjustmentOrange": "-45",
                      "ColorGradeMidtoneHue": "47", "ColorGradeMidtoneSat": "10",
                      "SplitToningHighlightHue": "234", "SplitToningHighlightSaturation": "13",
                      "ToneCurvePV2012": "0,0,255,255"})
    c = anh("DSC_9799", 3.5, sig_lech=0.15, new_exposure=0.1)
    ds = [a, b, c]
    n = at.dong_bo_cum(ds, cfg)
    X = [r["new_exposure"] + at.h_may(r) for r in ds]
    ktra("Exposure bù đúng phần chênh ISO: ánh sáng cảnh (new_exposure + h_may) BẰNG nhau",
         max(X) - min(X) < 0.011 and n >= 2, f"{[round(r['new_exposure'], 2) for r in ds]} · {[round(x, 3) for x in X]}")
    ktra("…ảnh ISO 1000 thấp hơn ảnh ISO 640 đúng 0.64 EV",
         abs((a["new_exposure"] - b["new_exposure"]) + math.log2(1000 / 640)) < 0.011,
         f"{a['new_exposure'] - b['new_exposure']:+.3f}")
    hl = [at._hieu_luc_cum(r) for r in ds]                                          # noqa: SLF001
    ktra("HSL / Luminance / CG / curve HIỆU LỰC như nhau cả cụm (mốc lệch nhau vẫn bằng)",
         all(h == hl[0] for h in hl[1:]), str([(h["HueAdjustmentOrange"], h["SaturationAdjustmentOrange"],
                                               h["LuminanceAdjustmentOrange"], h["gr_mid"]) for h in hl]))
    ktra("WB + tông như nhau", len({(r["new_temp"], r["new_tint"], r["new_highlights"], r["new_shadows"]) for r in ds}) == 1,
         str([(r["new_temp"], r["new_tint"], r["new_highlights"]) for r in ds]))
    ktra("ghi chú dong-bo-cum ở ảnh bị kéo", sum("dong-bo-cum" in r["notes"] for r in ds) == 2,
         str([r["notes"] for r in ds]))
    job = at.write_lr_job(ds, "Cum", job_dir=Path(__import__("tempfile").mkdtemp()))
    dong = job.read_text(encoding="utf-8").splitlines()
    cot = dong[0].split("\t")
    o = {Path(d.split("\t")[0]).stem: d.split("\t") for d in dong[1:]}

    def sau_ap(r, k):
        """Số Lightroom mang SAU khi áp job: ô ghi, ô trống = giữ số đang có."""
        o_ = o[Path(r["path"]).stem][cot.index(k)]
        if o_ != "":
            return str(float(o_)) if k != "ToneCurvePV2012" else o_
        v = at._gia_hien(r, k)                                                       # noqa: SLF001
        if k in ("Temperature", "Tint"):
            v = r.get("old_temp" if k == "Temperature" else "old_tint")
        return None if v is None else (str(float(v)) if k != "ToneCurvePV2012" else str(v))
    kh = ("Temperature", "Tint", "SaturationAdjustmentOrange", "HueAdjustmentOrange", "LuminanceAdjustmentOrange",
          "ColorGradeMidtoneHue", "ToneCurvePV2012")
    ktra("job: SAU khi áp cả cụm cùng Temperature / Tint / HSL / Luminance / CG / curve (ô trống = giữ số đang có)",
         all(len({sau_ap(r, k) for r in ds}) == 1 for k in kh), str([[sau_ap(r, k) for k in kh] for r in ds]))

    print("3. đen trắng / tắt")
    bw = anh("DSC_9804", 4.0, bw=True, new_exposure=0.5)
    a2, b2 = copy.deepcopy(a), copy.deepcopy(b)
    at.dong_bo_cum([a2, b2, bw], cfg)
    ktra("ảnh đen trắng không bị kéo", bw["new_exposure"] == 0.5)
    a3 = anh("DSC_9797", 0, iso=1000, new_exposure=-0.26)
    b3 = anh("DSC_9798", 2.3, iso=640, sig_lech=0.086, new_exposure=0.0)
    ktra("tắt dong_bo_cum -> không đổi", at.dong_bo_cum([a3, b3], dict(cfg, dong_bo_cum=False)) == 0
         and a3["new_exposure"] == -0.26)

    print("4. lượt 2")
    a4, b4, c4 = anh("DSC_9797", 0, iso=1000), anh("DSC_9798", 2.3, sig_lech=0.086), anh("DSC_9799", 3.5, sig_lech=0.15)
    b4["curve_ghi"] = {k: "0,0,128,135,255,255" for k in at.COT_CURVE}
    b4["hsl_l2"] = {"SaturationAdjustmentOrange": -25.0}
    n4 = at.dong_bo_cum_luot2([a4, b4, c4], cfg)
    ktra("curve + HSL lượt 2 của một tấm -> cả cụm", n4 == 4 and a4.get("curve_ghi") == b4["curve_ghi"]
         and c4.get("hsl_l2") == b4["hsl_l2"], f"{n4}")
    print(f"\n{len(LOI)} LOI" if LOI else "\nTAT CA DAT")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
