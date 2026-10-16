#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chuỗi màu da MỘT LƯỢT (mau_mot_luot.py — 14/10) đầu-cuối trên "Lightroom giả".

CHUYỆN ĐANG CANH
    User 14/10: "Quy trình chỉnh Tone -> Color Mixer HSL -> Tone Curve -> WB -> CG", áp MỘT
    lần. Chuỗi quyết trên ảnh DỰ ĐOÁN; nếu dự đoán sai thì áp xong da lệch mà không còn
    lượt 2 cứu. Bài này dựng ảnh "sau khi áp job" bằng mo_phong_lr (hành vi biết trước) và
    so với cái chuỗi đã dự đoán.

Mục kiểm
    1. chọn đường theo cảnh: có số đo + mô hình đạt -> một lượt; máy khác (không mô hình) -> cũ
    2. chuỗi đủ năm bước theo thứ tự (báo cáo sau_wb -> sau_hsl -> sau_curve -> sau_cg)
    3. dự đoán cuối == Lightroom giả dựng với ĐÚNG thông số job (da ≤ 1° / 4%, trắng ≤ 0.002)
    4. da về gần đích hơn chỉ Tone; vùng trắng gần đích trắng hơn trước WB
    5. HSL một mức mỗi cảnh, trong trần; curve một curve mỗi loạt, cả ảnh không đo trong loạt
    6. WB không theo da: vùng trắng đã đúng đích -> giữ WB dù da lệch
    7. job chính mang curve của chuỗi
    8. chạy lại trên kết quả (Lightroom đã mang thông số job) -> gần như không đổi
    13. thứ tự 16/10: Tone Curve (nén cháy) đầu, WB theo da (mẫu không vùng trắng), curve cuối
        giữ phần nén + ghép màu da; vùng ổn / ảnh ám màu giữ WB

Chạy:  python test_mau_mot_luot.py
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
LOI: list = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


def main() -> int:
    tam = Path(tempfile.mkdtemp(prefix="mot_luot_"))
    os.environ["AUTOTONE_DATA"] = str(tam / "du_lieu")
    os.environ.pop("AUTOTONE_MOT_LUOT", None)
    import autotone as at
    import curve_lr as cl
    import mau_mot_luot as ml
    import mo_hinh_lr as m
    import mo_phong_lr as sim

    #  mô hình học trên Lightroom giả, lưu theo khoá máy / profile / PV
    mh = m.khop(sim.bo_anh(8))
    mh.khoa, mh.dat = m.khoa_cua("SIM", "Adobe Standard", "15.4"), True
    m.luu(mh)
    ml.quen_mo_hinh()

    CV = "0,0,64,60,128,130,192,196,255,255"

    def cu_cua(i):
        return {"WhiteBalance": "Custom", "Temperature": "5200", "Tint": "5", "Exposure2012": "0",
                "Highlights2012": "0", "Shadows2012": "0", "HueAdjustmentOrange": "0",
                "SaturationAdjustmentOrange": "0", "ColorGradeMidtoneHue": "0", "ColorGradeMidtoneSat": "0",
                "SplitToningHighlightHue": "0", "SplitToningHighlightSaturation": "0",
                "ToneCurveName2012": "Custom", "ToneCurvePV2012": CV, "ToneCurvePV2012Red": "0,0,255,255",
                "ToneCurvePV2012Green": "0,0,255,255", "ToneCurvePV2012Blue": "0,0,255,255",
                "CameraProfile": "Adobe Standard", "ProcessVersion": "15.4"}

    canh_cua: dict = {}

    def do_truoc(r, cu):
        """r["lr_truoc"] như do_truoc.chay: số đo trên ảnh Lightroom (giả) dựng với cu."""
        scene, loai = canh_cua[r["path"]]
        px = sim.dung(scene, cu)
        mien = "melissa"
        r["lr_truoc"] = {"ok": True, "mien": mien, "mat_na": "parse", "n_da": int((loai == 0).sum()),
                         "da_mn": cl.srgb_sang_mien(px[loai == 0], mien),
                         "da_cu": cl.srgb_sang_mien(px[loai == 0], mien),
                         "trung": cl.srgb_sang_mien(px[loai == 1], mien),
                         "khung": cl.srgb_sang_mien(px, mien), "trung_ti_le": 0.2,
                         "nguon": "cache", "st": dict(cu)}

    def anh(i, canh, t0, may="SIM", lum=None, sang=1.0, goc=None, cv_rgb=None, **kw):
        """goc: cảnh gốc dùng chung (ảnh liên tiếp cùng khung) — mặc định mỗi ảnh một cảnh."""
        p = f"G:/Buoi/DSC{i:04d}.ARW"
        scene, loai = sim.canh(100 + (i if goc is None else goc))
        scene = scene * sang
        #  vùng "trắng" của cảnh: xám sáng (L ~0.7–0.9 sau dựng)
        scene[loai == 1] = np.random.default_rng(i).uniform(0.30, 0.55, (int((loai == 1).sum()), 1)) * [1, 1, 1]
        canh_cua[p] = (scene, loai)
        cu = cu_cua(i)
        if lum is not None:
            cu["LuminanceAdjustmentOrange"] = str(lum)
        if cv_rgb:                                  # curve R/G/B của preset (16/10)
            cu.update(cv_rgb)
        r = {"path": p, "lr_path": p, "ok": True, "scene": canh, "dt_obj": t0, "model": may,
             "scene_sig": [0.5] * 16, "meter_boxes": [[10, 10, 50, 60]], "preview_wh": (600, 400),
             "rating": 0, "ngoai_troi": False, "ev100": 7.0, "crs": dict(cu), "atn": {},
             "fnumber": 2.8, "exposure_time": 1 / 200, "iso": 800, "metered_subject_ev": -2.0,
             "crs_hien": dict(cu), "curve_moc": {k: cu.get(k, "") for k in at.COT_CURVE},
             "curve_tt": "moc", "delta_ev": 0.15, "hl_adj": 0, "sh_adj": 0,
             "temp_adj": -250.0, "tint_adj": 0.0, "face_rgb": [0.5, 0.4, 0.35], **kw}
        at.compute_values(r, CFG, r["crs"], r["atn"])
        do_truoc(r, cu)
        return r

    #  đích: da hồng hơn / ít vàng hơn da dựng; vùng trắng trung tính
    #  da_dich_L_bu 0: các kịch bản dưới dựng quanh đúng số mẫu (mức hạ theo gu: test_curve_da)
    CFG = dict(at.DEFAULTS, source="catalog", hsl_da_cuoi=True, grade=True, curve_da=True, da_dich_L_bu=0.0,
               curve_chay=False, mau_mot_luot=True, wb="skin",
               mau_da_dich={"ten": "mau", "trong": [226, 182, 170], "trong_mn": [226, 182, 170],
                            "trang": {"trong": [0.006, 0.008]}})
    T_DICH = (0.006, 0.008)
    t0 = datetime(2026, 10, 14, 10, 0, 0)
    items = []
    for i in range(6):                              # cảnh 0: hai loạt × 3
        items.append(anh(i, 0, t0 + timedelta(seconds=2 * i + (120 if i >= 3 else 0))))
    for i in range(6, 9):                           # cảnh 1: một loạt
        items.append(anh(i, 1, t0 + timedelta(hours=2, seconds=2 * i)))
    items[4].pop("lr_truoc")                        # một tấm trong loạt 2 không đo được
    items.append(anh(20, 2, t0 + timedelta(hours=4), may="MAY_KHAC"))  # máy chưa học màu

    print("1. chọn đường")
    moi, cu_ds = ml.chon_duong(items, CFG)
    ktra("cảnh có số đo + mô hình -> một lượt; máy chưa học -> đường cũ",
         len(moi) == 9 and [r["model"] for r in cu_ds] == ["MAY_KHAC"], f"{len(moi)} / {len(cu_ds)}")
    ktra("tắt mau_mot_luot -> mọi ảnh đường cũ", ml.chon_duong(items, dict(CFG, mau_mot_luot=False))[0] == [])

    print("2-5. chuỗi")
    #  da / vùng trắng chỉ sau Tone (để so)
    truoc = {}
    for r in moi:
        if r.get("lr_truoc"):
            s0 = ml.thong_so_tone(r, ml.cu_cua(r))
            sc, lo = canh_cua[r["path"]]
            px0 = sim.dung(sc, s0)
            truoc[r["path"]] = (m.thong_ke_da(px0[lo == 0]), ml._trang(px0[lo == 1]))
    kq = ml.chuoi(moi, CFG)
    do_dc = [r for r in moi if r.get("du_doan_lr")]
    ktra("8 ảnh có dự đoán (ảnh không đo không có)", len(do_dc) == 8 and kq["mot_luot"]["anh"] == 8, str(kq["mot_luot"]))
    b = do_dc[0]["mau_da_bao"]
    ktra("báo cáo đủ năm bước theo thứ tự, nguồn mo_hinh_lr",
         b["nguon"] == "mo_hinh_lr" and all(k in b for k in ("sau_wb", "sau_hsl", "sau_curve", "sau_cg")), str(b))
    lech_h, lech_q, lech_t = [], [], []
    gan_hon, trang_hon = 0, 0
    lt = at.mau_dich_lab(CFG["mau_da_dich"]["trong"])
    h_t = math.degrees(math.atan2(lt[2], lt[1]))
    for r in do_dc:
        s = ml.thong_so_job(r, ml.cu_cua(r))
        sc, lo = canh_cua[r["path"]]
        px = sim.dung(sc, s)
        L, h, q = m.thong_ke_da(px[lo == 0])
        t = ml._trang(px[lo == 1])
        d = r["du_doan_lr"]
        lech_h.append(abs(at._goc_lech(h - d["h"])))
        lech_q.append(abs(q / d["q"] - 1))
        if t and d["trung_ab"]:
            lech_t.append(math.hypot(t[0] - d["trung_ab"][0], t[1] - d["trung_ab"][1]))
        (L0, h0, q0), t0_ = truoc[r["path"]]
        gan_hon += int(abs(at._goc_lech(h_t - h)) <= abs(at._goc_lech(h_t - h0)) + 0.2)
        if t and t0_:
            trang_hon += int(math.hypot(t[0] - T_DICH[0], t[1] - T_DICH[1])
                             <= math.hypot(t0_[0] - T_DICH[0], t0_[1] - T_DICH[1]) + 1e-4)
    #  14/10: ngưỡng q 4% -> 6%: Tone giờ còn kéo sáng da về đích (Exposure đổi nhiều hơn)
    ktra("dự đoán == Lightroom giả dựng với thông số job: da ≤ 1° / 6%",
         max(lech_h) <= 1.0 and max(lech_q) <= 0.06, f"hue max {max(lech_h):.2f}° · q max {max(lech_q) * 100:.1f}%")
    #  một mức MỖI CẢNH (giữ đều trong cảnh): xét trung vị cảnh, không từng tấm
    theo_c: dict = {}
    for r in do_dc:
        theo_c.setdefault(r["scene"], []).append(r["mau_da_bao"]["L"])
    tv = {c: (float(np.median([x["truoc"] for x in v])), float(np.median([x["tone"] for x in v])),
              v[0]["dich"]) for c, v in theo_c.items()}
    ktra("Tone kéo sáng da về L đích theo CẢNH (cảnh sáng hơn đích -> hạ EV)",
         kq["mot_luot"]["sang"].get("canh", 0) >= 1
         and all(abs(t - d) <= abs(a - d) + 1e-3 and abs(t - d) <= 0.02 for a, t, d in tv.values()),
         f"{kq['mot_luot']['sang']} · (trước, sau Tone, đích) {tv}")
    #  Luminance theo LOẠT (14/10): loạt đã trong vùng ổn sau Tone -> không kéo; loạt còn tối /
    #  sáng -> kéo đúng chiều (bước sau chỉ chỉnh phần còn thiếu)
    sai_l = []
    for loat in at.chia_loat([r for r in do_dc], CFG):
        tv = float(np.median([r["mau_da_bao"]["L"]["tone"] - r["mau_da_bao"]["L"]["dich"] for r in loat]))
        lum = {int(r["mau_da_bao"]["L"]["lum"]) for r in loat}
        if len(lum) != 1 or (abs(tv) <= 0.02 and lum != {0}) or (tv < -0.02 and not min(lum) > 0)                 or (tv > 0.02 and not max(lum) < 0):
            sai_l.append((round(tv, 3), sorted(lum)))
    ktra("Luminance Cam theo loạt: trong vùng ổn -> 0, tối hơn -> dương, sáng hơn -> âm (một mức mỗi loạt)",
         not sai_l, f"{sai_l} · {kq['mot_luot']['lum']}")
    ktra("báo cáo có R G B % (trước / cuối / đích)", all(len(do_dc[0]["mau_da_bao"]["rgb"][k] or []) == 3
                                                          for k in ("truoc", "cuoi", "dich")),
         str(do_dc[0]["mau_da_bao"]["rgb"]))
    ktra("…vùng trắng ≤ 0.002", lech_t and max(lech_t) <= 0.002, f"{max(lech_t) if lech_t else None}")
    ktra("da về gần đích hơn chỉ Tone (mọi ảnh)", gan_hon == len(do_dc), f"{gan_hon}/{len(do_dc)}")
    ktra("vùng trắng gần đích trắng hơn trước WB", trang_hon == len(do_dc), f"{trang_hon}/{len(do_dc)}")
    #  14/10: một mức mỗi LOẠT (trước: mỗi cảnh)
    hsl = [[(r.get("hsl_moi") or {}).get("HueAdjustmentOrange") for r in g]
           for g in at.chia_loat([r for r in moi if r.get("hsl_ghi")], CFG)]
    th, ts = CFG.get("mot_luot_hsl_tran") or (15, 20)
    ktra(f"HSL: một mức mỗi loạt, trong trần ±{th} / ±{ts}",
         hsl and all(len(set(g)) == 1 for g in hsl)
         and all(abs(v) <= th for g in hsl for v in g if v is not None), str(hsl))
    loat2 = [r for r in moi if r["scene"] == 0 and r["path"] >= "G:/Buoi/DSC0003"]
    cv = [r.get("curve_ghi_mot_luot") for r in loat2]
    ktra("curve: cả loạt một curve, kể cả tấm không đo được", all(c for c in cv)
         and all(c == cv[0] for c in cv), str([bool(c) for c in cv]))
    ktra("WB đã chỉnh theo vùng trắng ở ít nhất một cảnh", kq["wb_canh_chinh"] >= 1, str(kq))
    #  16/10 TestAnhCuoi: ảnh có WB theo vùng trắng mang cờ NEO -> lượt kiểm (at.wb_da_luot2) giữ vùng trắng
    neo_c = [r for r in moi if (r.get("wb_bu") or (0, 0))[0]]
    ktra("…ảnh chỉnh WB theo vùng trắng mang cờ wb_neo_trang (lượt kiểm không kéo trắng sang xanh)",
         neo_c and all(r.get("wb_neo_trang") for r in neo_c), f"{sum(1 for r in neo_c if r.get('wb_neo_trang'))}/{len(neo_c)}")

    def tinh_lai(r, cfg):
        """Như plan(): decide() tính temp_adj MỚI (bỏ phần bù WB lần trước) -> compute_values."""
        r["temp_adj"], r["tint_adj"] = -250.0, 0.0
        r.pop("wb_bu", None)
        at.compute_values(r, cfg, r["crs"], r["atn"])

    print("6. WB không theo da")
    #  cảnh vùng trắng ĐÃ trung tính sau Tone: đặt đích trắng = vùng trắng dự đoán
    r6 = [r for r in moi if r["scene"] == 1 and r.get("lr_truoc")]
    ab = np.median([truoc[r["path"]][1] for r in r6], axis=0)
    cfg6 = dict(CFG, mau_da_dich=dict(CFG["mau_da_dich"], trang={"trong": [float(ab[0]), float(ab[1])]}))
    for r in [r for r in moi if r["scene"] == 1]:
        tinh_lai(r, cfg6)
    nhiet = {r["path"]: r["new_temp"] for r in r6}
    ml.chuoi([r for r in moi if r["scene"] == 1], cfg6)
    ktra("vùng trắng đúng đích -> giữ WB (da lệch thì HSL / Curve / CG lo)",
         all(r["new_temp"] == nhiet[r["path"]] for r in r6)
         and all(r["mau_da_bao"]["wb"] == "giu" for r in r6), str([r["mau_da_bao"]["wb"] for r in r6]))
    #  15/10: ảnh ÁM XANH NẶNG đã cứu WB theo da (autotone.cuu_am_mau) — vùng trắng lệch đích
    #  kéo WB cả cảnh, nhưng KHÔNG được kéo ảnh am_mau về lại
    cfg6b = dict(CFG, mau_da_dich=dict(CFG["mau_da_dich"], trang={"trong": [float(ab[0]) + 0.03,
                                                                           float(ab[1]) - 0.03]}),
                 wb_xet_lai_min_anh=2)                 # cảnh 3 ảnh, bỏ ảnh am_mau còn 2
    for r in [r for r in moi if r["scene"] == 1]:
        tinh_lai(r, cfg6b)
    r6[0]["am_mau"] = True
    nhiet = {r["path"]: r["new_temp"] for r in r6}
    ml.chuoi([r for r in moi if r["scene"] == 1], cfg6b)
    doi = [r for r in r6[1:] if r["new_temp"] != nhiet[r["path"]]]
    ktra("vùng trắng lệch đích -> WB cảnh đổi, ảnh am_mau giữ WB đã cứu",
         doi and r6[0]["new_temp"] == nhiet[r6[0]["path"]], f"đổi {len(doi)}/{len(r6) - 1}")
    r6[0].pop("am_mau", None)

    print("7. job")
    for r in moi:
        tinh_lai(r, CFG)
    ml.chuoi(moi, CFG)
    job = at.write_lr_job(moi, "Buoi", job_dir=tam / "jobs")
    dong = job.read_text(encoding="utf-8").splitlines()
    cot = dong[0].split("\t")
    ic = cot.index("ToneCurvePV2012Red")
    co_cv = [d.split("\t") for d in dong[1:] if d.split("\t")[ic]]
    ktra("job chính mang curve của chuỗi (ToneCurvePV2012Red có giá trị)", len(co_cv) >= 3, f"{len(co_cv)} dòng")

    print("8. chạy lại trên kết quả")
    def hsl_hl(r):
        return float((r.get("hsl_moi") or {}).get("HueAdjustmentOrange",
                                                   ml._f((r.get("crs_hien") or {}).get("HueAdjustmentOrange"))))
    lan1 = {r["path"]: (hsl_hl(r), r.get("curve_ghi_mot_luot"), r.get("gr_mid"), r["new_temp"])
            for r in moi}
    for r in moi:
        s = ml.thong_so_job(r, ml.cu_cua(r))
        cu2 = {k: (f"{v:.14g}" if isinstance(v, float) else str(v)) for k, v in s.items()}
        r["crs_hien"] = cu2
        if r.get("lr_truoc") or r["path"] != items[4]["path"]:
            do_truoc(r, cu2)
        tinh_lai(r, CFG)
    ml.chuoi(moi, CFG)
    doi_hsl = sum(1 for r in moi if abs(hsl_hl(r) - lan1[r["path"]][0]) >= 1)
    doi_k = max(abs(r["new_temp"] - lan1[r["path"]][3]) for r in moi)
    ktra("lần hai: HSL như lần một", doi_hsl == 0, f"{doi_hsl} ảnh đổi")
    ktra("lần hai: WB lệch ≤ 30 K", doi_k <= 30, f"{doi_k} K")
    gr = [abs(((r.get("gr_mid") or (0, 0))[1]) - ((lan1[r["path"]][2] or (0, 0))[1])) for r in moi]
    ktra("lần hai: Color Grading lệch ≤ 2 sat", max(gr) <= 2, str(gr))

    print("9. sáng da theo đích: Tone bị chặn -> Luminance Cam; mốc; chạy lại không cộng dồn")
    buoi9 = tam / "Buoi9"
    buoi9.mkdir()
    #  cảnh TỐI (da L thấp hơn đích sáng), Tone chỉ được +0.1 EV
    ds9 = [anh(40 + i, 5, t0 + timedelta(hours=6, seconds=2 * i), lum=10, sang=0.55) for i in range(3)]
    #  ảnh LẺ (không thuộc loạt nào) cùng cảnh — chia_loat không trả nó (14/10: ~200 ảnh lẻ
    #  của 2709 không được nâng sáng)
    le9 = anh(45, 5, t0 + timedelta(hours=7), lum=10, sang=0.55)
    for r in ds9 + [le9]:
        r["crs"].pop("LuminanceAdjustmentOrange", None)          # mốc chốt trước 14/10: chưa có ô này
    at.save_baseline(buoi9, {at.khoa_duong_dan(r["path"]): dict(r["crs"], __lrpath=r["path"]) for r in ds9 + [le9]})
    #  14/10 tối: mặc định Tone KHÔNG tăng sáng cả ảnh (user: "dư sáng ít nhất 0.5ev") —
    #  mục này bật lại tăng tối đa +0.1 để canh đường kẹp; mặc định có bài riêng ở mục 10
    cfg9 = dict(CFG, mot_luot_ev_sang_tran=0.1, mot_luot_ev_sang_len=0.1, grade=False)
    kq9 = ml.chuoi(ds9 + [le9], cfg9, folder=buoi9)
    ktra("ảnh LẺ cũng được nâng sáng (Tone) + Luminance của riêng nó",
         "sang-dich" in str(le9.get("notes")) and le9.get("hsl_l_ghi"), str(le9.get("notes")))
    lum = [(r.get("hsl_l_moi") or {}).get("LuminanceAdjustmentOrange") for r in ds9]
    ktra("Tone kẹp +0.1 EV", abs(kq9["mot_luot"]["sang"].get("e", 0) - 0.1) < 1e-6, str(kq9["mot_luot"]["sang"]))
    tran_l = float(cfg9.get("hsl_da_lum_tran") or 35)
    ktra(f"…phần sáng còn thiếu -> Luminance Cam (một mức cả loạt, trong trần ±{tran_l:.0f}, cộng vào số preset 10)",
         all(r.get("hsl_l_ghi") for r in ds9) and len(set(lum)) == 1 and 10 < lum[0] <= 10 + tran_l,
         f"{lum} · {kq9['mot_luot']['lum']}")
    Ls = [r["mau_da_bao"]["L"] for r in ds9]
    ktra("L dự đoán cuối gần đích hơn L sau Tone", all(abs(x["cuoi"] - x["dich"]) < abs(x["tone"] - x["dich"]) for x in Ls),
         str([(x["tone"], x["cuoi"], x["dich"]) for x in Ls]))
    lech_L = []
    for r in ds9:
        s = ml.thong_so_job(r, ml.cu_cua(r))
        sc, lo = canh_cua[r["path"]]
        lech_L.append(abs(m.thong_ke_da(sim.dung(sc, s)[lo == 0])[0] - r["du_doan_lr"]["L"]))
    ktra("L dự đoán == Lightroom giả dựng với thông số job (≤ 0.02)", max(lech_L) <= 0.02, f"{max(lech_L):.4f}")
    moc = at.load_baseline(buoi9)
    ktra("mốc: lưu số Luminance gốc (10) cho ảnh vừa ghi lần đầu",
         all(moc[at.khoa_duong_dan(r["path"])].get("LuminanceAdjustmentOrange") == "10" for r in ds9)
         and all(r["crs"].get("LuminanceAdjustmentOrange") == "10" for r in ds9))
    job9 = at.write_lr_job(ds9, "Buoi9", job_dir=tam / "jobs9")
    dong = job9.read_text(encoding="utf-8").splitlines()
    ic = dong[0].split("\t").index("LuminanceAdjustmentOrange")
    ktra("job mang cột LuminanceAdjustmentOrange", all(d.split("\t")[ic] == str(int(lum[0])) for d in dong[1:]),
         str([d.split("\t")[ic] for d in dong[1:]]))
    #  lần hai: Lightroom đang mang số tool vừa ghi -> tính lại từ preset, không cộng dồn
    for r in ds9:
        s = ml.thong_so_job(r, ml.cu_cua(r))
        cu2 = {k: (f"{v:.14g}" if isinstance(v, float) else str(v)) for k, v in s.items()}
        r["crs_hien"] = cu2
        do_truoc(r, cu2)
        tinh_lai(r, cfg9)
    ml.chuoi(ds9, cfg9, folder=buoi9)
    lum2 = [(r.get("hsl_l_moi") or {}).get("LuminanceAdjustmentOrange",
                                             ml._f(r["crs_hien"].get("LuminanceAdjustmentOrange"))) for r in ds9]
    ktra("lần hai: Luminance như lần một (tính từ mốc 10, không cộng dồn)",
         all(abs(a - b) <= 2 for a, b in zip(lum2, lum)), f"{lum} -> {lum2}")
    #  moc_them_cot: không đè số mốc có sẵn, không tạo mốc mới
    n = at.moc_them_cot(buoi9, {ds9[0]["path"]: {"LuminanceAdjustmentOrange": 99},
                                "G:/Buoi/KHONG_CO.ARW": {"LuminanceAdjustmentOrange": 5}})
    moc = at.load_baseline(buoi9)
    ktra("moc_them_cot: không đè số có sẵn, không tạo mốc cho ảnh chưa có", n == 0
         and moc[at.khoa_duong_dan(ds9[0]["path"])].get("LuminanceAdjustmentOrange") == "10"
         and at.khoa_duong_dan("G:/Buoi/KHONG_CO.ARW") not in moc)

    print("10. mặc định: Tone không tăng sáng cả ảnh; lượt 2 sửa HSL theo số đo THẬT")
    ds10 = [anh(60 + i, 7, t0 + timedelta(hours=9, seconds=2 * i), lum=10, sang=0.55) for i in range(3)]
    cfg10 = dict(CFG, grade=False)
    ev0 = [r["new_exposure"] for r in ds10]
    kq10 = ml.chuoi(ds10, cfg10)
    ktra("da tối hơn đích: Exposure KHÔNG tăng (mặc định mot_luot_ev_sang_len = 0)",
         all(r["new_exposure"] <= e + 1e-6 for r, e in zip(ds10, ev0)) and not kq10["mot_luot"]["sang"].get("tang"),
         f"{ev0} -> {[r['new_exposure'] for r in ds10]} · {kq10['mot_luot']['sang']}")
    ktra("…phần sáng da để Luminance Cam", all(r.get("hsl_l_ghi") for r in ds10),
         str([(r.get('hsl_l_moi') or {}).get('LuminanceAdjustmentOrange') for r in ds10]))
    #  "Lightroom thật" khác dự đoán: da cảnh thật ĐỎ + đậm hơn cảnh mô hình đã thấy — cảnh sáng
    #  thường (lượt 1 chưa chạm trần HSL, còn chỗ cho lượt 2). 16/10: WB nay chạy TRƯỚC HSL —
    #  cảnh giả này WB vùng trắng ấm +300 K làm da dự đoán đậm tới mức HSL lượt 1 chạm trần, lượt
    #  2 hết chỗ. Mục này kiểm CƠ CHẾ soát HSL, không kiểm WB -> tắt WB của chuỗi cho cảnh này
    cfg10b = dict(cfg10, wb_xet_lai=False, mot_luot_wb_da=False)
    ds10 = [anh(70 + i, 8, t0 + timedelta(hours=10, seconds=2 * i), lum=10) for i in range(3)]
    ml.chuoi(ds10, cfg10b)
    lt10 = at.mau_dich_lab(CFG["mau_da_dich"]["trong"])
    h_t10, q_t10 = math.degrees(math.atan2(lt10[2], lt10[1])), math.hypot(lt10[1], lt10[2]) / lt10[0]

    def do_that(r, lech):
        sc, lo = canh_cua[r["path"]]
        sc = sc.copy()
        sc[lo == 0] = sc[lo == 0] * np.asarray(lech)
        s_ = ml.thong_so_job(r, ml.cu_cua(r))
        if r.get("hsl_l2"):
            s_ = dict(s_, **r["hsl_l2"])
        px = sim.dung(sc, s_)
        return {"ok": True, "mien": "melissa", "mat_na": "parse",
                "da_mn": cl.srgb_sang_mien(px[lo == 0], "melissa"),
                "da_cu": cl.srgb_sang_mien(px[lo == 0], "melissa")}, m.thong_ke_da(px[lo == 0])
    LECH = (1.06, 0.98, 0.93)
    do_mau = {id(ds10[1]): do_that(ds10[1], LECH)[0]}
    _L1, h1, q1 = do_that(ds10[1], LECH)[1]
    kqs = ml.soat(ds10, do_mau, cfg10b)
    co = [r for r in ds10 if r.get("hsl_l2")]
    ktra("lượt 2: cả loạt (3 ảnh, 1 tấm soát) nhận HSL mới theo số đo thật, một mức",
         len(co) == 3 and len({tuple(sorted(r["hsl_l2"].items())) for r in co}) == 1, str([r.get("hsl_l2") for r in ds10]))
    _L2, h2, q2 = do_that(ds10[1], LECH)[1]
    xa1 = abs(at._goc_lech(h1 - h_t10)) / 3.0 + abs(math.log(q1 / q_t10)) / math.log(1.1)
    xa2 = abs(at._goc_lech(h2 - h_t10)) / 3.0 + abs(math.log(q2 / q_t10)) / math.log(1.1)
    #  cảnh giả rất đậm: Sat chạm trần −20 của chuỗi -> chỉ đòi GẦN hơn, đúng chiều, trong trần
    th10, ts10 = cfg10b.get("mot_luot_hsl_tran") or (15, 20)
    ktra("lượt 2: da thật sau HSL mới GẦN đích hơn (hue / độ đậm), Sat giảm, trong trần",
         xa2 < xa1 - 0.3 and all(-ts10 <= (r["hsl_l2"].get("SaturationAdjustmentOrange", -1)) < 0 for r in co),
         f"trước {h1:.1f}°/{q1 / q_t10:.2f}× · sau {h2:.1f}°/{q2 / q_t10:.2f}× · đích {h_t10:.1f}°")
    job10 = __import__("curve_da").ghi_job(ds10, "Buoi10", tam / "jobs10")
    cot10 = job10.read_text(encoding="utf-8").splitlines()[0].split("\t") if job10 else []
    dong10 = job10.read_text(encoding="utf-8").splitlines()[1:] if job10 else []
    ktra("job lượt 2 mang cột HSL Cam (curve để trống)", job10 is not None and cot10[:6] == ["path", *at.COT_CURVE]
         and any(k in cot10 for k in ("HueAdjustmentOrange", "SaturationAdjustmentOrange", "LuminanceAdjustmentOrange"))
         and all(not any(d.split("\t")[1:6]) for d in dong10), str(cot10))
    ktra("tóm tắt soát: số ảnh sửa HSL", kqs.get("hsl") == 3 and kqs.get("sua") == 3, str({k: kqs.get(k) for k in ("hsl", "sua", "n")}))
    #  14/10: cụm cùng khung — chỉ MỘT tấm có dự đoán + số đo (đo trước 2 ảnh / loạt), lượt 2 phải
    #  tới cả tấm không đo, cùng số TUYỆT ĐỐI (2709 bản 7: 85 cụm lệch Hue / Sat sau lượt 2)
    for r in ds10:
        r.pop("hsl_l2", None)
    kq_t = ml.soat([ds10[1]], do_mau, cfg10, tat_ca=ds10)
    ktra("lượt 2 tới cả ảnh KHÔNG đo trong cụm, cùng số tuyệt đối",
         all(r.get("hsl_l2") for r in ds10) and len({tuple(sorted(r["hsl_l2"].items())) for r in ds10}) == 1
         and kq_t.get("sua") == 3, str([r.get("hsl_l2") for r in ds10]))

    print("11. cụm cùng khung: tấm flash không kịp hồi -> cân sáng trên da dự đoán Lightroom (15/10)")
    #  6 tấm cùng thông số, 2 giây / tấm; tấm 1 và 4 RAW tối 0.86 EV (scene × 0.55): mặt preview
    #  máy tối 0.86 EV, khung tối 0.5 EV
    t11 = t0 + timedelta(hours=11)
    ds11 = []
    for i in range(6):
        toi = i in (1, 4)
        ds11.append(anh(80 + i, 9, t11 + timedelta(seconds=2 * i), sang=0.55 if toi else 1.0, goc=80,
                        metered_face_ev=-1.86 if toi else -1.0, metered_subject_ev=-2.5 if toi else -2.0))
    kq11 = ml.chuoi(ds11, cfg10)
    L11 = [r["du_doan_lr"]["L"] for r in ds11]
    ev11 = [r["new_exposure"] for r in ds11]
    thuong = [L11[i] for i in (0, 2, 3, 5)]
    ktra("da dự đoán tấm tối = tấm thường (±0.015 L)",
         all(abs(L11[i] - float(np.median(thuong))) <= 0.015 for i in (1, 4)), f"L {L11}")
    ktra("…bù trên Lightroom (bu_cum_lr) mạnh hơn phần bù preview máy (0.5 × 0.86 = 0.43)",
         all(ds11[i].get("bu_cum_lr") and ds11[i]["bu_cum_lr"] > 0.5 for i in (1, 4))
         and all(ds11[i].get("bu_cum_lr") is None for i in (0, 2, 3, 5)),
         f"{[r.get('bu_cum_lr') for r in ds11]} · EV {ev11}")
    ktra("…tấm thường cùng một Exposure; tóm tắt can_sang", len({ev11[i] for i in (0, 2, 3, 5)}) == 1
         and kq11["mot_luot"]["can_sang"]["anh"] == 2
         and kq11["mot_luot"]["can_sang"]["chenh_sau"] < kq11["mot_luot"]["can_sang"]["chenh_truoc"],
         str(kq11["mot_luot"]["can_sang"]))
    at.dong_bo_cum(ds11, cfg10)
    ktra("dong_bo_cum cuối plan() giữ nguyên số đã cân", [r["new_exposure"] for r in ds11] == ev11,
         str([r["new_exposure"] for r in ds11]))
    #  preview máy nói tấm tối hơn nhưng da Lightroom bằng (số đo preview máy lệch) -> bỏ phần bù
    ds12 = []
    for i in range(6):
        ds12.append(anh(90 + i, 10, t11 + timedelta(hours=1, seconds=2 * i), goc=90,
                        metered_face_ev=-1.86 if i == 1 else -1.0, metered_subject_ev=-2.5 if i == 1 else -2.0))
    ml.chuoi(ds12, cfg10)
    ktra("preview máy đòi bù mà Lightroom thấy da đã bằng -> không bù (về Exposure chung)",
         len({r["new_exposure"] for r in ds12}) == 1, str([(r["new_exposure"], r.get("bu_cum_lr")) for r in ds12]))

    print("12. Tone theo CỤM, không theo cảnh (15/10)")
    #  cùng cảnh 11: cụm 1 da rất sáng (ngoài trời, như DSC09393–95), cụm 2 cách 3 phút da bình
    #  tối hơn đích -> cụm 1 hạ Exposure CẢ ẢNH đủ mức, cụm 2 không bị kéo theo (trước: trung vị cảnh)
    t13 = t0 + timedelta(hours=13)
    ds13 = [anh(110 + i, 11, t13 + timedelta(seconds=2 * i), sang=1.8, goc=110) for i in range(3)]
    ds13 += [anh(120 + i, 11, t13 + timedelta(minutes=3, seconds=2 * i), sang=0.55, goc=120) for i in range(3)]
    ev13 = [r["new_exposure"] for r in ds13]
    kq13 = ml.chuoi(ds13, dict(cfg10, da_dich_L_bu=0.0))
    e1 = [round(r["new_exposure"] - e, 2) for r, e in zip(ds13[:3], ev13[:3])]
    e2 = [round(r["new_exposure"] - e, 2) for r, e in zip(ds13[3:], ev13[3:])]
    ktra("cụm da sáng: hạ Exposure cả cụm, một mức; cụm da thường cùng cảnh: không hạ",
         len(set(e1)) == 1 and e1[0] <= -0.2 and all(x > -0.05 for x in e2), f"{e1} / {e2} · {kq13['mot_luot']['sang']}")

    print("13. Thứ tự mới (16/10): Curve R/G/B (ô bật) -> Tone Curve (tông) -> WB theo da -> Tone -> HSL -> CG")
    #  mẫu KHÔNG có vùng trắng (như "Mặc định") -> bước WB theo DA; cảnh sáng có vùng cháy -> nén.
    #  16/10 tối: ô Curve R/G/B bật thì curve chạy ĐẦU và đưa da về đích -> WB không còn gì để làm;
    #  các mục WB dưới đây chạy với ô TẮT
    md13 = {"ten": "mau13", "trong": [226, 182, 170], "ngoai": [226, 182, 170]}
    cfg13 = dict(CFG, mau_da_dich=md13, curve_chay=True, grade=False, curve_da=False)
    cfg13r = dict(cfg13, curve_da=True)
    t13b = t0 + timedelta(hours=15)

    def bo13(goc, cfg_, sang=1.0, base=None, **kw):
        base = goc if base is None else base
        ds = [anh(base + i, 12 + goc % 7, t13b + timedelta(minutes=base, seconds=2 * i), goc=goc, sang=sang, **kw)
              for i in range(3)]
        kq_ = ml.chuoi(ds, cfg_)
        return ds, kq_

    lt13 = at.mau_dich_lab(md13["trong"])
    h13 = math.degrees(math.atan2(lt13[2], lt13[1]))

    def lech_cuoi(r):
        return abs(at._goc_lech((r.get("du_doan_lr") or {}).get("h", 0.0) - h13))

    def lech_sau_wb(r):
        #  da dự đoán SAU WB + Tone, TRƯỚC HSL / curve / CG (mau_da_bao["sau_wb"])
        return abs(at._goc_lech(r["mau_da_bao"]["sau_wb"][0] - h13))

    ds_a, kq_a = bo13(140, cfg13)
    ds_b, kq_b = bo13(140, dict(cfg13, mot_luot_wb_da=False))
    ktra("mẫu không vùng trắng -> bước WB THEO DA chạy, ghi chú wb-da-mot-luot",
         (kq_a.get("wb_da") or {}).get("chinh", 0) >= 1
         and all("wb-da-mot-luot" in str(r.get("notes", "")) for r in ds_a), str(kq_a.get("wb_da")))
    ktra("…một WB cho cả cụm cùng khung", len({(r["new_temp"], r["new_tint"]) for r in ds_a}) == 1,
         str([(r["new_temp"], r["new_tint"]) for r in ds_a]))
    dk = [r["new_temp"] - r2["new_temp"] for r, r2 in zip(ds_a, ds_b)]
    dt = [r["new_tint"] - r2["new_tint"] for r, r2 in zip(ds_a, ds_b)]
    ktra("…trong trần (≤ 1000 K, ≤ 10 Tint) và có đổi thật",
         all(abs(x) <= 1000 + 1 for x in dk) and all(abs(x) <= 10 + 0.5 for x in dt)
         and any(abs(x) >= 50 or abs(y) >= 1 for x, y in zip(dk, dt)), f"ΔK {dk} · ΔTint {dt}")
    ktra("…ngay sau WB + Tone (trước HSL) da GẦN đích hơn chuỗi không có bước WB theo da",
         all(lech_sau_wb(r) < lech_sau_wb(r2) for r, r2 in zip(ds_a, ds_b)),
         f"{[round(lech_sau_wb(r), 1) for r in ds_a]} vs {[round(lech_sau_wb(r), 1) for r in ds_b]}")
    ktra("…da dự đoán cuối trong vùng ổn hue (≤ da_on_hue)",
         all(lech_cuoi(r) <= float(cfg13.get("da_on_hue") or 3.0) for r in ds_a),
         str([round(lech_cuoi(r), 1) for r in ds_a]))
    ds_c, kq_c = bo13(150, dict(cfg13, da_on_hue=90.0, da_on_chroma=10.0))
    ktra("da trong vùng ổn -> bước WB theo da GIỮ WB", (kq_c.get("wb_da") or {}).get("chinh", 1) == 0
         and not any("wb-da-mot-luot" in str(r.get("notes", "")) for r in ds_c), str(kq_c.get("wb_da")))
    ds_d, _kq = bo13(160, cfg13, am_mau=1.4)
    ktra("ảnh ám xanh nặng (am_mau — WB đã cứu theo da) giữ WB",
         not any("wb-da-mot-luot" in str(r.get("notes", "")) for r in ds_d))
    #  ô Curve R/G/B BẬT: curve chạy đầu đưa da về đích -> bước WB theo da giữ WB
    ds_r, kq_r = bo13(140, cfg13r, base=540)
    ktra("ô Curve R/G/B bật: curve R/G/B chạy ĐẦU (có curve), bước WB thấy da đã ổn -> giữ WB",
         kq_r["mot_luot"].get("curve", 0) >= 1 and (kq_r.get("wb_da") or {}).get("chinh", 1) == 0
         and all("wb-da-mot-luot" not in str(r.get("notes", "")) for r in ds_r),
         f"curve {kq_r['mot_luot'].get('curve')} · wb {kq_r.get('wb_da')}")
    ktra("…da ngay sau curve R/G/B (trước WB / Tone) đã gần đích hơn trước chuỗi",
         all(abs(at._goc_lech(r["mau_da_bao"]["sau_curve"][0] - h13))
             < abs(at._goc_lech(m.thong_ke_da(sim.dung(canh_cua[r["path"]][0], ml.cu_cua(r))
                                              [canh_cua[r["path"]][1] == 0])[1] - h13)) for r in ds_r),
         str([r["mau_da_bao"]["sau_curve"] for r in ds_r]))
    #  XOÁ R/G/B của preset (at.dat_lai_rgb, plan() gọi): mốc về thẳng, curve da tính từ đó
    RGB_PRESET = {"ToneCurvePV2012Red": "0,0,136,128,255,255", "ToneCurvePV2012Green": "0,0,125,122,255,255",
                  "ToneCurvePV2012Blue": "0,0,127,138,255,255"}
    ds_f = [anh(600 + i, 19, t13b + timedelta(hours=1, seconds=2 * i), goc=140, cv_rgb=RGB_PRESET)
            for i in range(3)]
    ds_f.append(anh(610, 19, t13b + timedelta(hours=2), goc=140, cv_rgb=RGB_PRESET, meter_boxes=[]))
    ds_f.append(anh(611, 19, t13b + timedelta(hours=3), goc=140, cv_rgb=RGB_PRESET, curve_tt="nguoi_sua"))
    ktra("ô Curve R/G/B TẮT -> không xoá gì", at.dat_lai_rgb(ds_f, cfg13) == 0
         and all(r["curve_moc"]["ToneCurvePV2012Red"] == RGB_PRESET["ToneCurvePV2012Red"] for r in ds_f))
    n_f = at.dat_lai_rgb(ds_f, cfg13r)
    ktra("ô bật: ảnh có mặt -> mốc R/G/B THẲNG + job lượt 1 ghi nó (curve_reset), curve tổng giữ preset",
         n_f == 3 and all(r["curve_moc"][k] == at.RGB_THANG and r["curve_reset"][k] == at.RGB_THANG
                          for r in ds_f[:3] for k in RGB_PRESET)
         and all(r["curve_moc"]["ToneCurvePV2012"] == CV for r in ds_f[:3]), f"{n_f} ảnh")
    ktra("…ảnh không mặt / curve người dùng tự sửa: không đụng",
         all(r["curve_moc"]["ToneCurvePV2012Red"] == RGB_PRESET["ToneCurvePV2012Red"] and not r.get("curve_reset")
             for r in ds_f[3:]))
    ktra("…dat_lai_rgb chỉ với nguồn catalog", at.dat_lai_rgb([anh(620, 19, t13b, cv_rgb=RGB_PRESET)],
                                                                dict(cfg13r, source="sidecar")) == 0)
    kq_f = ml.chuoi(ds_f[:3], cfg13r)
    cv_f = [r.get("curve_ghi_mot_luot") or {} for r in ds_f[:3]]
    ktra("chuỗi: curve R/G/B ghi ra dựng từ R/G/B THẲNG (không còn điểm 136/128 của preset)",
         kq_f["mot_luot"].get("curve", 0) >= 1
         and all("136,128" not in str(c.get("ToneCurvePV2012Red", "")) for c in cv_f if c), str(cv_f[0]))
    lech_f = []
    for r in ds_f[:3]:
        if r.get("du_doan_lr"):
            sc_, lo_ = canh_cua[r["path"]]
            px_ = sim.dung(sc_, ml.thong_so_job(r, ml.cu_cua(r)))
            lech_f.append(abs(at._goc_lech(m.thong_ke_da(px_[lo_ == 0])[1] - r["du_doan_lr"]["h"])))
    ktra("…dự đoán cuối == Lightroom giả dựng với thông số job (da ≤ 1°)", lech_f and max(lech_f) <= 1.0,
         str([round(x, 2) for x in lech_f]))
    moc_p = {k: CV if k == "ToneCurvePV2012" else RGB_PRESET.get(k, "Custom") for k in at.COT_CURVE}
    ktra("trang_thai_curve: catalog đang ở preset với R/G/B thẳng (tool xoá) -> 'tool' (tắt ô thì trả preset)",
         at.trang_thai_curve(moc_p, at.moc_rgb_thang(moc_p), None) == "tool"
         and at.trang_thai_curve(moc_p, moc_p, None) == "moc")
    #  Tone Curve chạy đầu: cảnh sáng (khung cháy) -> curve cuối mang CẢ nén cháy (curve tổng khác
    #  mốc) lẫn chỉnh màu da (kênh R/G/B) — bước 5 ghép lên curve bước 1, không về mốc
    #  cảnh gốc 140: khung cháy ~10%, da chưa cháy (p95 0,77) -> nén (cảnh da cũng gần cháy
    #  thì luật "da sáng -> không nén" chặn — bước Tone lo phần sáng)
    ds_e, kq_e = bo13(40, cfg13r, base=440)
    cv_e = [r.get("curve_ghi_mot_luot") or {} for r in ds_e]
    nen = [c.get("ToneCurvePV2012") not in (None, "", CV) for c in cv_e]
    kenh = [any(c.get(k) not in (None, "", "0,0,255,255") for k in ("ToneCurvePV2012Red", "ToneCurvePV2012Green",
                                                                      "ToneCurvePV2012Blue")) for c in cv_e]
    ktra("cảnh cháy: bước 1 nén cháy (curve tổng) và curve cuối GIỮ phần nén",
         kq_e["mot_luot"].get("curve_tong", 0) >= 1 and all(nen), f"{kq_e['mot_luot']} · {nen}")
    ktra("…curve R/G/B màu da ghép thêm lên (kênh khác đồng nhất) khi da còn lệch",
         any(kenh) and all(c.get("ToneCurvePV2012") == cv_e[0].get("ToneCurvePV2012") for c in cv_e if c), str(kenh))
    lech_e = []
    for r in ds_e:
        if r.get("du_doan_lr"):
            sc_, lo_ = canh_cua[r["path"]]
            px_ = sim.dung(sc_, ml.thong_so_job(r, ml.cu_cua(r)))
            lech_e.append(abs(at._goc_lech(m.thong_ke_da(px_[lo_ == 0])[1] - r["du_doan_lr"]["h"])))
    ktra("…dự đoán cuối == Lightroom giả dựng với thông số job (da ≤ 1°)",
         lech_e and max(lech_e) <= 1.0, str([round(x, 2) for x in lech_e]))

    print("14. Quy trình Auto (16/10): WB -> Tone -> Curve R/G/B; HSL / CG / Luminance / nén cháy tắt")
    cfg14 = dict(CFG, mau_da_dich=md13, quy_trinh_auto=True, curve_da=True, curve_chay=True,
                 grade=True, hsl_da_cuoi=True)
    ds14 = [anh(700 + i, 26, t13b + timedelta(hours=6, seconds=2 * i), goc=40, sang=0.6) for i in range(3)]
    ev14 = [r["new_exposure"] for r in ds14]
    kq14 = ml.chuoi(ds14, cfg14)
    ktra("không Luminance Cam, không HSL Cam, không Color Grading (giữ tông Auto)",
         not any(r.get("hsl_l_ghi") or r.get("hsl_ghi") or r.get("gr_ghi") for r in ds14),
         str([(r.get("hsl_l_ghi"), r.get("hsl_ghi"), r.get("gr_ghi")) for r in ds14]))
    ktra("…không nén vùng cháy, không chặn cháy kéo Highlights (Auto đã lo vùng sáng)",
         not kq14["mot_luot"].get("curve_tong") and not kq14["mot_luot"].get("chay"), str(kq14["mot_luot"]))
    ktra("WB theo da chạy (mẫu không vùng trắng) rồi Curve R/G/B CUỐI (có curve kênh)",
         kq14.get("wb_da") is not None and kq14["mot_luot"].get("curve", 0) >= 1, str(kq14.get("wb_da")))
    d14 = [round(r["new_exposure"] - e, 3) for r, e in zip(ds14, ev14)]
    ktra("Tone: da tối hơn đích -> Exposure được TĂNG nhưng ≤ +0.3 (auto_ev_sang_len)",
         all(0 < x <= 0.3 + 1e-6 for x in d14), str(d14))

    print("15. Quy trình Auto — DUYỆT LẠI một lần bằng dự đoán trước khi áp (16/10 tối)")
    import curve_da as cdm

    def loi_sim(ds, cfg_):
        """tổng lệch da (chuẩn hoá theo vùng ổn) trên Lightroom GIẢ dựng với đúng thông số job."""
        tong = 0.0
        for r in ds:
            sc, lo = canh_cua[r["path"]]
            L, h, q = m.thong_ke_da(sim.dung(sc, ml.thong_so_job(r, ml.cu_cua(r)))[lo == 0])
            lt = at.mau_dich_lab(cdm.dich_cua(r, cfg_, "mn")[0])
            h_t = math.degrees(math.atan2(lt[2], lt[1]))
            q_t = math.hypot(lt[1], lt[2]) / lt[0]
            tong += (((L - lt[0]) / 0.02) ** 2 + (at._goc_lech(h - h_t) / 3.0) ** 2  # noqa: SLF001
                     + (math.log(q / q_t) / math.log(1.1)) ** 2)
        return tong
    cfg15 = dict(cfg14, curve_da=False)                       # chỉ WB + Exposure
    t15 = t13b + timedelta(hours=8)
    a15 = [anh(800 + i, 27, t15 + timedelta(seconds=2 * i), goc=50, sang=0.3) for i in range(3)]
    b15 = [anh(810 + i, 28, t15 + timedelta(minutes=30, seconds=2 * i), goc=50, sang=0.3) for i in range(3)]
    kq_a15 = ml.chuoi(a15, dict(cfg15, auto_duyet_lai=False))
    kq_b15 = ml.chuoi(b15, cfg15)
    dv15 = kq_b15["mot_luot"].get("duyet") or {}
    e_a, e_b = loi_sim(a15, cfg15), loi_sim(b15, cfg15)
    ktra("duyệt lại: cụm da còn lệch đích sau chuỗi được chỉnh thêm — lệch trên Lightroom giả GIẢM",
         dv15.get("lech", 0) >= 1 and dv15.get("sua", 0) >= 1 and e_b < 0.8 * e_a,
         f"{dv15} · lệch {e_a:.1f} -> {e_b:.1f}")
    ktra("…tắt auto_duyet_lai -> không duyệt", not (kq_a15["mot_luot"].get("duyet") or {}).get("xet"),
         str(kq_a15["mot_luot"].get("duyet")))
    ktra("…cả cụm cùng khung MỘT mức chỉnh, ghi chú duyet-lai, Exposure thêm ≤ +0.3",
         len({(r["new_exposure"], r["new_temp"], r["new_tint"]) for r in b15}) == 1
         and all("duyet-lai" in r["notes"] for r in b15)
         and all(rb["new_exposure"] - ra["new_exposure"] <= 0.3 + 1e-6 for ra, rb in zip(a15, b15)),
         str([(r["new_exposure"], r["new_temp"], r["new_tint"]) for r in b15]))
    c15 = [anh(820 + i, 29, t15 + timedelta(hours=1, seconds=2 * i), goc=50, sang=0.3) for i in range(3)]
    ml.chuoi(c15, cfg15)
    dv_c = ml.duyet_lai(c15, {}, cfg15)
    ktra("ảnh không có số đo / mô hình (không trong mm) -> duyệt không đụng", dv_c == {"xet": 0, "lech": 0,
                                                                                     "sua": 0, "dat_sau": 0},
         str(dv_c))

    print("16. Phạm vi chỉnh: chỉ WB / chỉ Exposure (17/10)")
    t16 = t15 + timedelta(hours=4)
    for pv, so in (("wb", 840), ("ev", 850), ("wb_ev", 860)):
        ds16 = [anh(so + i, 30 + so, t16 + timedelta(minutes=so, seconds=2 * i), goc=50, sang=0.3)
                for i in range(3)]
        truoc = [(r["new_exposure"], r["new_temp"], r["new_tint"]) for r in ds16]
        kq16 = ml.chuoi(ds16, dict(cfg15, pham_vi=pv))
        sau = [(r["new_exposure"], r["new_temp"], r["new_tint"]) for r in ds16]
        doi_ev = any(abs(a[0] - b[0]) > 1e-6 for a, b in zip(truoc, sau))
        doi_wb = any(a[1:] != b[1:] for a, b in zip(truoc, sau))
        ktra(f"phạm vi '{pv}': chỉ đổi " + {"wb": "WB", "ev": "Exposure", "wb_ev": "WB + Exposure"}[pv]
             + ", không curve",
             (doi_ev == (pv != "wb")) and (pv != "ev" or not doi_wb) and (pv == "ev" or doi_wb or doi_ev)
             and not any(r.get("curve_ghi_mot_luot") for r in ds16),
             f"{truoc} -> {sau} · duyệt {kq16['mot_luot'].get('duyet')}")
    print(f"\n{len(LOI)} LOI" if LOI else "\nTAT CA DAT")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
