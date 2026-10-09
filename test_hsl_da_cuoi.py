#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HSL màu da ẢNH CƯỚI — quyết định trên da ĐO THẬT ở ảnh duyệt (9/10).

CHUYỆN ĐANG LÀM
    User: "Thêm option bật HSL để tự chỉnh. Cân WB và Tone xong thì phải biết được
    tình trạng da chủ thể đang ở mức nào với các thông số đã chỉnh rồi mới quyết
    định chỉnh HSL để ra màu đích. Không được kéo da quá đỏ hay ám màu khác như
    kỷ yếu." Xem at.hsl_da_cuoi.

Ảnh duyệt tổng hợp: mỗi ảnh một mảng "da" màu biết trước (OkLab hue / chroma) đúng
chỗ khung mặt tool chọn, đặt trong <buổi>/_duyet — như ảnh Lightroom vẽ khi Duyệt
nhanh. Job .done giả mang đúng WB / Tone đã đẩy vào Lightroom.

Mục kiểm (vòng 2, 9/10 — đo thật Ănhoi2009: KHÔNG BAO GIỜ xoay da về đỏ)
    1. Da vàng + nhạt -> Hue GIỮ (không xoay về đỏ), Sat dương tới mép khoảng (80%).
    2. Da trong khoảng ổn -> cảnh giữ nguyên (không ghi HSL).
    3. Da QUÁ ĐỎ -> lùi về vàng (Hue dương), quá đậm -> Sat giảm.
    4. Trần đậm (1/4 mặt đậm nhất) cắt đúng.
    5. Thiếu ảnh duyệt / ảnh duyệt cũ hơn job / WB-Tone đổi so với job -> không đụng.
    6. Preset không phải SAY -> không đụng. Cảnh chỉ 1 ảnh đo -> không quyết.
    7. Vòng kín: HSL cộng vào số JOB đã ghi; ảnh duyệt mới cho thấy đỏ quá -> lùi.
    8. Tắt ô -> ảnh tool từng ghi HSL trả về số preset (đường cũ).
    9. Ô Temp / Tint của job để TRỐNG (WB không đổi) vẫn nhận là trùng.

Chạy:  python test_hsl_da_cuoi.py
"""
from __future__ import annotations

import csv
import math
import os
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at  # noqa: E402

LOI: list[str] = []
W, H = 1024, 683
HOP = (450.0, 250.0, 120.0, 150.0, 0.95)          # khung mat (x, y, rong, cao, diem)


def ktra(ten: str, dieu: bool, mo: str = "") -> None:
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(f"{ten}: {mo}")


def srgb_tu_oklab(L, h, c):
    a, b = c * math.cos(math.radians(h)), c * math.sin(math.radians(h))
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    lin = np.array([4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
                    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
                    -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s])
    lin = np.clip(lin, 0, 1)
    return np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * lin ** (1 / 2.4) - 0.055)


def anh_duyet(p: Path, h, c, L=0.76):
    """Ảnh 'Lightroom vẽ': nền xám, mảng da màu (hue h, chroma c) có nhiễu sáng nhẹ."""
    arr = np.full((H, W, 3), 0.35, dtype=np.float64)
    rng = np.random.default_rng(int(h * 10 + c * 1000))
    x, y, bw, bh = (int(v) for v in HOP[:4])
    for i in range(bh):
        for k in (0,):
            pass
    da = np.stack([srgb_tu_oklab(L + rng.normal(0, 0.02), h, c) for _ in range(64)])
    vung = da[rng.integers(0, 64, size=(bh, bw))]
    arr[y:y + bh, x:x + bw] = vung
    Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8)).save(p, quality=95)


SAY = {"HueAdjustmentRed": "0", "SaturationAdjustmentRed": "4", "HueAdjustmentOrange": "7",
       "SaturationAdjustmentOrange": "-25", "HueAdjustmentYellow": "0", "SaturationAdjustmentYellow": "-4"}


def mk(buoi: Path, ten: str, canh: int, **kw):
    r = {"path": str(buoi / f"{ten}.ARW"), "scene": canh, "bw": False, "notes": "",
         "meter_boxes": [HOP], "preview_wh": (W, H), "new_temp": 5100, "new_tint": 14,
         "old_temp": 5100, "old_tint": 14, "new_exposure": 0.25, "new_highlights": -20,
         "new_shadows": 16, "crs": dict(SAY)}
    r.update(kw)
    return r


def ghi_job(jobs: Path, buoi: Path, items, ten="apply_20261009_100000", tuoi=120, hsl=None, wb_trong=False):
    cot = ["path", "Exposure2012", "Highlights2012", "Shadows2012", "Temperature", "Tint"] + list(at.COT_HSL)
    p = jobs / f"{ten}_{at.ten_job(buoi.name)}.done"
    with open(p, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(cot)
        for r in items:
            h = (hsl or {}).get(r["path"], {})
            w.writerow([r["path"], f"{r['new_exposure']:+.2f}", int(r["new_highlights"]), int(r["new_shadows"]),
                        "" if wb_trong else int(r["new_temp"]), "" if wb_trong else int(r["new_tint"])]
                       + [h.get(k, "") for k in at.COT_HSL])
    t = time.time() - tuoi
    os.utime(p, (t, t))
    return p


def chay(items, buoi, jobs, **them):
    cfg = dict(at.DEFAULTS, source="catalog", loai_buoi="cuoi", hsl_da_cuoi=True, **them)
    return at.hsl_da_cuoi(items, cfg, buoi, jobs)


def main() -> int:
    tam = Path(tempfile.mkdtemp(prefix="hsl_cuoi_"))
    buoi = tam / "Cuoi_Test"
    (buoi / "_duyet").mkdir(parents=True)
    jobs = tam / "jobs"
    jobs.mkdir()
    k_h, k_s = float(at.DEFAULTS["hsl_da_k_hue"]), float(at.DEFAULTS["hsl_da_k_sat"])
    hue_min = float(at.DEFAULTS["hsl_da_cuoi_hue_min"])
    c_lo, c_hi = (float(v) for v in at.DEFAULTS["hsl_da_cuoi_dam"])
    dh, dc = 38.0, 0.050                     # mau da TRONG khoang on

    # canh 1: da vang + nhat | canh 2: da o dich | canh 3: da qua do | canh 4: khong anh duyet
    # canh 5: chi 1 anh | canh 6: anh duyet CU hon job | canh 7: WB doi so voi job
    mau = {1: (45.0, 0.040), 2: (dh, dc), 3: (28.0, 0.060), 5: (45.0, 0.040), 6: (45.0, 0.040), 7: (45.0, 0.040)}
    items = []
    for canh, n in ((1, 3), (2, 3), (3, 3), (4, 3), (5, 1), (6, 3), (7, 3)):
        for i in range(n):
            items.append(mk(buoi, f"C{canh}_{i}", canh))
    items.append(mk(buoi, "C1_khongmat", 1, meter_boxes=[]))          # anh khong mat cua canh 1
    ghi_job(jobs, buoi, items)
    for r in items:
        canh = r["scene"]
        if canh in mau and r["meter_boxes"]:
            p = buoi / "_duyet" / (Path(r["path"]).stem + ".jpg")
            anh_duyet(p, *mau[canh])
            if canh == 6:
                t = time.time() - 600                                   # ve TRUOC job
                os.utime(p, (t, t))
    for r in items:
        if r["scene"] == 7:
            r["new_temp"] = 5300                                        # lan tinh nay khac job

    kq = chay(items, buoi, jobs)
    theo = {}
    for r in items:
        theo.setdefault(r["scene"], []).append(r)

    # ---- 1
    d = [r["da_duyet"] for r in theo[1] if r.get("da_duyet")]
    ktra("do duoc da tren anh duyet canh 1 (3 anh)", len(d) == 3,
         f"hue {np.median([x[0] for x in d]):.1f} chroma {np.median([x[1] for x in d]):.4f}" if d else "")
    h1 = float(np.median([x[0] for x in d])); c1 = float(np.median([x[1] for x in d]))
    h1q = float(np.percentile([x[0] for x in d], 25)); c1q = float(np.percentile([x[1] for x in d], 75))
    u_mong = 0                                        # da vang: KHONG xoay ve do
    v_mong = int(round(np.clip(0.8 * math.log(c_lo / c1) / k_s, -20, 20)))
    r1 = theo[1][0]
    ok1 = r1.get("hsl_ghi") and r1["hsl_moi"]["HueAdjustmentOrange"] == 7 + u_mong \
        and r1["hsl_moi"]["SaturationAdjustmentOrange"] == -25 + v_mong
    ktra("canh vang + nhat -> Hue GIU (khong xoay ve do), Sat duong toi mep khoang (80%)",
         bool(ok1) and v_mong > 0,
         f"Hue {r1.get('hsl_moi', {}).get('HueAdjustmentOrange')} (mong {7 + u_mong}) Sat "
         f"{r1.get('hsl_moi', {}).get('SaturationAdjustmentOrange')} (mong {-25 + v_mong})")
    ktra("anh khong mat cung canh nhan cung muc HSL",
         all(r.get("hsl_moi") == r1.get("hsl_moi") for r in theo[1]))
    ktra("Red / Yellow giu nguyen so preset",
         r1["hsl_moi"]["SaturationAdjustmentRed"] == 4 and r1["hsl_moi"]["SaturationAdjustmentYellow"] == -4)
    # ---- 2
    ktra("canh da trong khoang on -> giu nguyen (khong ghi HSL)", not any(r.get("hsl_ghi") for r in theo[2]))
    # ---- 3
    r3 = theo[3][0]
    ktra("canh da QUA DO -> lui ve vang (Hue duong), Sat giam",
         r3.get("hsl_ghi") and r3["hsl_moi"]["HueAdjustmentOrange"] > 7
         and r3["hsl_moi"]["SaturationAdjustmentOrange"] < -25,
         str({k: r3.get("hsl_moi", {}).get(k) for k in ("HueAdjustmentOrange", "SaturationAdjustmentOrange")}))
    # ---- 5 / 6 / 7 / 4
    ktra("canh khong co anh duyet -> khong dung HSL", not any(r.get("hsl_ghi") for r in theo[4]))
    ktra("canh chi 1 anh do duoc -> khong quyet", not any(r.get("hsl_ghi") for r in theo[5]))
    ktra("anh duyet CU hon job -> khong dung", not any(r.get("hsl_ghi") or r.get("da_duyet") for r in theo[6]))
    ktra("WB lan tinh nay khac job -> khong dung", not any(r.get("hsl_ghi") or r.get("da_duyet") for r in theo[7])
         and kq["doi_so"] == 3, f"doi_so {kq['doi_so']}")
    ktra("tom tat: dem dung so canh chinh / on", kq["canh_chinh"] == 2 and kq["canh_on"] == 1,
         f"chinh {kq['canh_chinh']} on {kq['canh_on']} canh {kq['canh']} thieu_duyet {kq['thieu_duyet']}")

    # ---- 4. tran dam: khoang [0.060, 0.045] -> keo len du nhung 1/4 mat dam nhat cham 0.045
    kq4 = chay(items, buoi, jobs, hsl_da_cuoi_dam=[0.060, 0.045])
    r1 = theo[1][0]
    v_tran = int(round(max(0.0, math.log(0.045 / c1q) / k_s)))
    ktra("tran dam: 1/4 mat dam nhat sau HSL khong vuot mep tren",
         r1["hsl_moi"]["SaturationAdjustmentOrange"] == -25 + v_tran,
         f"Sat {r1['hsl_moi']['SaturationAdjustmentOrange']} (mong {-25 + v_tran})")
    ktra("tom tat ghi canh cham chot chan", kq4["canh_chan"] >= 1)
    # ---- 4b. KHONG BAO GIO xoay ve do: ca khi da vang dam (50 do) trong moi cau hinh
    kq4b = chay(items, buoi, jobs, hsl_da_cuoi_phan=1.0, hsl_da_cuoi_hue_min=60.0)
    ktra("da vang van KHONG bi xoay ve do (Hue chi tang hoac giu)",
         all((r.get("hsl_moi") or {}).get("HueAdjustmentOrange", 7) >= 7 for r in items),
         str(sorted({(r.get('hsl_moi') or {}).get('HueAdjustmentOrange') for r in items if r.get('hsl_moi')})))

    # ---- 6. preset khong phai SAY
    khac = [dict(r, crs=dict(r["crs"], SaturationAdjustmentOrange="-35")) for r in items]
    kq6 = chay(khac, buoi, jobs)
    ktra("preset khong phai SAY -> khong dung HSL", kq6["khac_preset"] and not any(r.get("hsl_ghi") for r in khac))

    # ---- 7. vong kin: job moi da ghi HSL; anh duyet moi cho thay da DO qua -> lui
    hsl_job = {r["path"]: {"HueAdjustmentOrange": "-7", "SaturationAdjustmentOrange": "-7",
                           "HueAdjustmentRed": "0", "SaturationAdjustmentRed": "4",
                           "HueAdjustmentYellow": "0", "SaturationAdjustmentYellow": "-4"} for r in items}
    for r in items:
        if r["scene"] == 7:
            r["new_temp"] = 5100
    #  job HSL ghi SAU lan duyet truoc (thu tu that): anh duyet cu (canh 3) gio cu hon job
    for r in theo[3]:
        pa = buoi / "_duyet" / (Path(r["path"]).stem + ".jpg")
        t = time.time() - 90
        os.utime(pa, (t, t))
    ghi_job(jobs, buoi, items, ten="apply_20261009_110000", tuoi=30, hsl=hsl_job)
    for r in theo[1]:
        if r["meter_boxes"]:
            anh_duyet(buoi / "_duyet" / (Path(r["path"]).stem + ".jpg"), 31.0, 0.058)   # sau HSL: do qua
    for r in theo[2]:
        anh_duyet(buoi / "_duyet" / (Path(r["path"]).stem + ".jpg"), dh, dc)            # van o dich
    kq7 = chay(items, buoi, jobs)
    r1, r2 = theo[1][0], theo[2][0]
    ktra("vong kin: da qua do sau HSL -> Hue LUI (duong) tinh tu so job -7",
         r1.get("hsl_ghi") and r1["hsl_moi"]["HueAdjustmentOrange"] > -7,
         f"Hue {r1.get('hsl_moi', {}).get('HueAdjustmentOrange')}")
    ktra("vong kin: canh da trong khoang on -> khong ghi (Lightroom giu HSL dang co)", not r2.get("hsl_ghi"))
    ktra("anh duyet cu hon job MOI -> khong dung (canh 3 chua duyet lai)", not any(r.get("hsl_ghi") for r in theo[3]))

    # ---- 8. tat o -> duong cu tra so preset cho anh tool tung ghi HSL
    for r in items:
        r["da_hsl"] = True
    cfg = dict(at.DEFAULTS, source="catalog", loai_buoi="cuoi", hsl_da_cuoi=False)
    at.chinh_mau_da(items, cfg, buoi)
    r1 = theo[1][0]
    ktra("tat o -> anh tool tung ghi HSL tra ve so preset",
         r1.get("hsl_ghi") and r1["hsl_moi"]["HueAdjustmentOrange"] == 7
         and r1["hsl_moi"]["SaturationAdjustmentOrange"] == -25)
    for r in items:
        r.pop("da_hsl", None)

    # ---- 9. o Temp / Tint job de trong (WB khong doi) van trung
    for p in jobs.glob("*.done"):
        p.unlink()
    ghi_job(jobs, buoi, items, ten="apply_20261009_120000", tuoi=60, wb_trong=True)
    for r in theo[1]:
        if r["meter_boxes"]:
            anh_duyet(buoi / "_duyet" / (Path(r["path"]).stem + ".jpg"), 45.0, 0.040)
    kq9 = chay(items, buoi, jobs)
    ktra("o WB job trong (WB khong doi) -> van nhan anh duyet", theo[1][0].get("hsl_ghi") and kq9["doi_so"] == 0,
         f"doi_so {kq9['doi_so']}")

    # ---- 10. giao dien that: o tick co mat va doc vao cfg
    try:
        import tkinter as tk
        from datetime import timedelta
        import autotone_gui as ag
        import giao_dien as gd
        root = tk.Tk()
    except Exception as ex:                                  # noqa: BLE001
        print(f"  (bo qua phan giao dien: {ex.__class__.__name__}: {ex})")
    else:
        try:
            ag.bq.kiem = lambda: {"co_phep": True, "con_lai": timedelta(days=300), "nhac": "",
                                  "goi": "1 năm", "may": "TEST01", "het_han": False, "ly_do": ""}
            gd.dat_theme(root)
            app = ag.App(root)
            ktra("giao dien: o 'Tu chinh HSL mau da' mac dinh TAT",
                 app.v_hsl_da.get() is False and app.read_cfg().get("hsl_da_cuoi") is False)
            app.v_hsl_da.set(True)
            ktra("giao dien: tick o -> cfg hsl_da_cuoi = True", app.read_cfg().get("hsl_da_cuoi") is True)
        finally:
            root.destroy()

    print("TAT CA DAT" if not LOI else f"{len(LOI)} LOI")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
