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

    def anh(i, canh, t0, may="SIM", **kw):
        p = f"G:/Buoi/DSC{i:04d}.ARW"
        scene, loai = sim.canh(100 + i)
        #  vùng "trắng" của cảnh: xám sáng (L ~0.7–0.9 sau dựng)
        scene[loai == 1] = np.random.default_rng(i).uniform(0.30, 0.55, (int((loai == 1).sum()), 1)) * [1, 1, 1]
        canh_cua[p] = (scene, loai)
        cu = cu_cua(i)
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
    CFG = dict(at.DEFAULTS, source="catalog", hsl_da_cuoi=True, grade=True, curve_da=True,
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
    ktra("dự đoán == Lightroom giả dựng với thông số job: da ≤ 1° / 4%",
         max(lech_h) <= 1.0 and max(lech_q) <= 0.04, f"hue max {max(lech_h):.2f}° · q max {max(lech_q) * 100:.1f}%")
    ktra("…vùng trắng ≤ 0.002", lech_t and max(lech_t) <= 0.002, f"{max(lech_t) if lech_t else None}")
    ktra("da về gần đích hơn chỉ Tone (mọi ảnh)", gan_hon == len(do_dc), f"{gan_hon}/{len(do_dc)}")
    ktra("vùng trắng gần đích trắng hơn trước WB", trang_hon == len(do_dc), f"{trang_hon}/{len(do_dc)}")
    hsl = {r["scene"]: (r.get("hsl_moi") or {}).get("HueAdjustmentOrange") for r in moi if r.get("hsl_ghi")}
    ktra("HSL: một mức mỗi cảnh, trong trần ±15 / ±20",
         all(len({(r.get("hsl_moi") or {}).get("HueAdjustmentOrange") for r in moi if r["scene"] == c}) == 1 for c in hsl)
         and all(abs(v) <= 15 for v in hsl.values() if v is not None), str(hsl))
    loat2 = [r for r in moi if r["scene"] == 0 and r["path"] >= "G:/Buoi/DSC0003"]
    cv = [r.get("curve_ghi_mot_luot") for r in loat2]
    ktra("curve: cả loạt một curve, kể cả tấm không đo được", all(c for c in cv)
         and all(c == cv[0] for c in cv), str([bool(c) for c in cv]))
    ktra("WB đã chỉnh theo vùng trắng ở ít nhất một cảnh", kq["wb_canh_chinh"] >= 1, str(kq))

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
    print(f"\n{len(LOI)} LOI" if LOI else "\nTAT CA DAT")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
