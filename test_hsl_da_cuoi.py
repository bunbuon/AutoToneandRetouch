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

Mục kiểm (vòng 3, 9/10 — user: "da đạt màu TRẮNG, chỉ 1 chút hồng"; v52 đỏ hơn
preset 1.9°). Đích: hue 36–41°, độ đậm 0.036–0.042, tính từ TRẠNG THÁI PRESET.
    1. Da vàng + đậm -> Hue âm (bớt vàng tới mép 41°), Sat âm (trắng đi), đúng 80%.
       Da vàng + nhạt -> Hue âm, Sat dương tới mép dưới.
    2. Da trong khoảng -> cảnh giữ nguyên (không ghi HSL).
    3. Da QUÁ ĐỎ -> lùi về vàng (Hue dương), quá đậm -> Sat giảm.
    4. Sàn đỏ (1/4 mặt đỏ nhất) và trần đậm (1/4 mặt đậm nhất) cắt đúng; phan 1.0
       -> mọi cảnh về đúng khoảng, không cảnh nào đỏ hơn mép dưới.
    5. Thiếu ảnh duyệt / ảnh duyệt cũ hơn job / WB-Tone đổi so với job -> không đụng.
    6. Preset không phải SAY -> không đụng. Cảnh chỉ 1 ảnh đo -> không quyết.
    7. Vòng kín: tool từng kéo ĐỎ (job Orange -7) mà da ở preset đã trong khoảng
       -> TRẢ VỀ số preset; Lightroom đang mang đúng mức -> Ghi lại không trôi.
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
    h_lo, h_hi = (float(v) for v in at.DEFAULTS["hsl_da_cuoi_hue"])
    c_lo, c_hi = (float(v) for v in at.DEFAULTS["hsl_da_cuoi_dam"])
    dh, dc = 38.5, 0.039                     # mau da TRONG khoang (trang, hoi hong)

    def mong(hs, cs, phan=0.8, khoang_c=(c_lo, c_hi), san=h_lo):
        """Muc Orange (Hue, Sat) cua canh — tinh doc lap tu so da O PRESET."""
        h, c = float(np.median(hs)), float(np.median(cs))
        hq, cq = float(np.percentile(hs, 25)), float(np.percentile(cs, 75))
        lo, hi = khoang_c
        u = phan * (h_hi - h) / k_h if h > h_hi else (phan * (h_lo - h) / k_h if h < h_lo else 0.0)
        u = float(np.clip(u, -15, 15))
        dcc = math.log(hi / c) if c > hi else (math.log(lo / c) if c < lo else 0.0)
        v = float(np.clip(phan * dcc / k_s, -20, 20))
        if u < 0 and hq + k_h * u < san:
            u = min(0.0, (san - hq) / k_h)
        if v > 0 and cq * math.exp(k_s * v) > hi:
            v = max(0.0, math.log(hi / cq) / k_s)
        return int(round(u)), int(round(v))

    # canh 1: da vang + dam | canh 2: da trong khoang | canh 3: da qua do | canh 4: khong anh duyet
    # canh 5: chi 1 anh | canh 6: anh duyet CU hon job | canh 7: WB doi so voi job | canh 8: vang + nhat
    mau = {1: (47.0, 0.050), 2: (dh, dc), 3: (31.0, 0.050), 5: (47.0, 0.050), 6: (47.0, 0.050),
           7: (47.0, 0.050), 8: (46.0, 0.030)}
    items = []
    for canh, n in ((1, 3), (2, 3), (3, 3), (4, 3), (5, 1), (6, 3), (7, 3), (8, 3)):
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
    hs1, cs1 = [x[0] for x in d], [x[1] for x in d]
    u_mong, v_mong = mong(hs1, cs1)
    r1 = theo[1][0]
    ok1 = r1.get("hsl_ghi") and r1["hsl_moi"]["HueAdjustmentOrange"] == 7 + u_mong \
        and r1["hsl_moi"]["SaturationAdjustmentOrange"] == -25 + v_mong
    ktra("canh vang + dam -> Hue AM (bot vang toi mep), Sat AM (trang di), dung 80%",
         bool(ok1) and u_mong < 0 and v_mong < 0,
         f"Hue {r1.get('hsl_moi', {}).get('HueAdjustmentOrange')} (mong {7 + u_mong}) Sat "
         f"{r1.get('hsl_moi', {}).get('SaturationAdjustmentOrange')} (mong {-25 + v_mong})")
    ktra("hue du doan sau HSL van VANG hon mep duoi (khong do hon dich)",
         all(r.get("da_lech1", 1) <= 0 for r in theo[1] if r.get("da_goc")),
         str([r.get("da_lech1") for r in theo[1]]))
    d8 = [r["da_duyet"] for r in theo[8] if r.get("da_duyet")]
    u8, v8 = mong([x[0] for x in d8], [x[1] for x in d8])
    r8 = theo[8][0]
    ktra("canh vang + nhat -> Hue am, Sat duong toi mep duoi",
         r8.get("hsl_ghi") and u8 < 0 < v8 and r8["hsl_moi"]["HueAdjustmentOrange"] == 7 + u8
         and r8["hsl_moi"]["SaturationAdjustmentOrange"] == -25 + v8,
         f"{ {k: r8.get('hsl_moi', {}).get(k) for k in ('HueAdjustmentOrange', 'SaturationAdjustmentOrange')} } "
         f"mong {7 + u8}/{-25 + v8}")
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
    ktra("tom tat: dem dung so canh chinh / on", kq["canh_chinh"] == 3 and kq["canh_on"] == 1,
         f"chinh {kq['canh_chinh']} on {kq['canh_on']} canh {kq['canh']} thieu_duyet {kq['thieu_duyet']}")

    # ---- 4. san do: 1/4 mat do nhat canh 1 khong duoi 45 -> Hue chi keo toi 45
    kq4 = chay(items, buoi, jobs, hsl_da_cuoi_san_do=45.0)
    r1 = theo[1][0]
    u_san, _ = mong(hs1, cs1, san=45.0)
    ktra("san do: canh vang keo bot vang nhung 1/4 mat do nhat khong duoi 45",
         r1["hsl_moi"]["HueAdjustmentOrange"] == 7 + u_san and u_mong < u_san <= 0,
         f"Hue {r1['hsl_moi']['HueAdjustmentOrange']} (mong {7 + u_san}, khong san {7 + u_mong})")
    ktra("tom tat ghi canh cham chot chan", kq4["canh_chan"] >= 1)
    # ---- 4a. tran dam: khoang [0.080, 0.032] -> canh 8 (nhat) keo len nhung 1/4 mat dam nhat cham 0.032
    chay(items, buoi, jobs, hsl_da_cuoi_dam=[0.080, 0.032])
    _, v_tran = mong([x[0] for x in d8], [x[1] for x in d8], khoang_c=(0.080, 0.032))
    ktra("tran dam: 1/4 mat dam nhat sau HSL khong vuot mep tren",
         r8["hsl_moi"]["SaturationAdjustmentOrange"] == -25 + v_tran and 0 < v_tran < 20,
         f"Sat {r8['hsl_moi']['SaturationAdjustmentOrange']} (mong {-25 + v_tran})")
    # ---- 4b. phan 1.0: moi canh ve DUNG khoang hue, khong canh nao do hon mep duoi
    chay(items, buoi, jobs, hsl_da_cuoi_phan=1.0)
    #  canh cham tran 15 diem (anh duyet gia do ra 48 do) thi chi can khong do hon mep
    lech = [(r["da_lech1"], abs(r["hsl_moi"]["HueAdjustmentOrange"] - 7) >= 15) for r in items
            if r.get("hsl_ghi") and r.get("da_lech1") is not None]
    ktra("phan 1.0: hue du doan sau HSL ve dung khoang (|lech| <= 0.5 do), khong do hon 36",
         bool(lech) and all(x <= 0.5 and (tran or abs(x) <= 0.5) for x, tran in lech),
         str(sorted(set(lech))))

    # ---- 6. preset khong phai SAY
    khac = [dict(r, crs=dict(r["crs"], SaturationAdjustmentOrange="-35")) for r in items]
    kq6 = chay(khac, buoi, jobs)
    ktra("preset khong phai SAY -> khong dung HSL", kq6["khac_preset"] and not any(r.get("hsl_ghi") for r in khac))

    # ---- 7. vong kin, tinh tu PRESET (vong 3)
    #  canh 1: Lightroom DANG mang dung muc lan 1 -> Ghi lai khong troi
    #  canh 2: tool tung keo DO (Orange -7/-7, kieu v52): anh duyet do (33 do) nhung
    #          tru phan HSL ra thi da o preset da trong khoang -> TRA VE preset 7/-25
    muc1 = {r["path"]: dict(r["hsl_moi"]) for r in theo[1] if r.get("hsl_moi")}
    chay(items, buoi, jobs)                       # lai muc mac dinh cho canh 1
    muc1 = {r["path"]: dict(r["hsl_moi"]) for r in theo[1] if r.get("hsl_moi")} or muc1
    hsl_job = {}
    for r in items:
        if r["scene"] == 1:
            hsl_job[r["path"]] = {k: f"{v:+.0f}" for k, v in muc1[r["path"]].items()}
        elif r["scene"] == 2:
            hsl_job[r["path"]] = {"HueAdjustmentOrange": "-7", "SaturationAdjustmentOrange": "-7",
                                  "HueAdjustmentRed": "0", "SaturationAdjustmentRed": "4",
                                  "HueAdjustmentYellow": "0", "SaturationAdjustmentYellow": "-4"}
    for r in items:
        if r["scene"] == 7:
            r["new_temp"] = 5100
    #  job HSL ghi SAU lan duyet truoc (thu tu that): anh duyet cu (canh 3) gio cu hon job
    for r in theo[3]:
        pa = buoi / "_duyet" / (Path(r["path"]).stem + ".jpg")
        t = time.time() - 90
        os.utime(pa, (t, t))
    ghi_job(jobs, buoi, items, ten="apply_20261009_110000", tuoi=30, hsl=hsl_job)
    #  Lightroom ve DUNG phan ung thanh truot: canh 1 = da lan 1 + muc lan 1; canh 2 =
    #  33 do / 0.046 (do vi HSL tool). Thay ham do bang so chinh xac — anh duyet gia
    #  (JPEG 8 bit, da nhat) lech hue toi +-2 do, khong kiem duoc vong kin.
    du1, dv1 = u_mong, v_mong
    that = {}
    for r in theo[1]:
        if r["meter_boxes"]:
            g = r["da_duyet"]
            that[r["path"]] = (g[0] + k_h * du1, g[1] * math.exp(k_s * dv1), g[2], g[3])
            anh_duyet(buoi / "_duyet" / (Path(r["path"]).stem + ".jpg"), *that[r["path"]][:2])
    for r in theo[2]:
        that[r["path"]] = (33.0, 0.046, 0.76, 3000)
        anh_duyet(buoi / "_duyet" / (Path(r["path"]).stem + ".jpg"), 33.0, 0.046)
    do_cu = at.da_tren_anh_duyet
    at.da_tren_anh_duyet = lambda r, anh: that.get(r["path"]) or do_cu(r, anh)
    try:
        kq7 = chay(items, buoi, jobs)
    finally:
        at.da_tren_anh_duyet = do_cu
    r1, r2 = theo[1][0], theo[2][0]
    lai = r1.get("hsl_moi") or {}
    ktra("vong kin: Lightroom da mang dung muc -> Ghi lai khong troi (khong ghi / lech <= 1 diem)",
         not r1.get("hsl_ghi") or all(abs(float(lai[k]) - float(muc1[r1["path"]][k])) <= 1 for k in lai),
         f"job {muc1[r1['path']].get('HueAdjustmentOrange')}/{muc1[r1['path']].get('SaturationAdjustmentOrange')}"
         f" -> {lai.get('HueAdjustmentOrange')}/{lai.get('SaturationAdjustmentOrange')}")
    ktra("vong kin: tool tung keo do (Orange -7), da preset trong khoang -> TRA VE preset 7/-25",
         r2.get("hsl_ghi") and r2["hsl_moi"]["HueAdjustmentOrange"] == 7
         and r2["hsl_moi"]["SaturationAdjustmentOrange"] == -25 and kq7["tra_preset"] >= 3,
         f"{ {k: r2.get('hsl_moi', {}).get(k) for k in ('HueAdjustmentOrange', 'SaturationAdjustmentOrange')} }"
         f" tra_preset {kq7['tra_preset']} da_goc {r2.get('da_goc')}")
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
            anh_duyet(buoi / "_duyet" / (Path(r["path"]).stem + ".jpg"), 47.0, 0.050)
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
