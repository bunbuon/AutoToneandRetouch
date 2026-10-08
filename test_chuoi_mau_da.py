#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chuỗi chỉnh MÀU DA (8/10 đêm): đo sau WB + Tone -> HSL kênh da -> đo lại -> Color Grading.

CHUYỆN ĐANG SỬA
    User: "sau khi cân WB và Tone xong phải biết da đang ở màu nào rồi mới can thiệp
    HSL / Color Grading; tránh can thiệp song song thì đè màu lên nhau; da đã ổn thì
    không đổi; Color Grading phải siết chặt hơn vì một thay đổi nhỏ đổi màu cả ảnh".
    Trước đó HSL và Color Grading cùng tính từ trạng thái sau WB + Tone.

Mục kiểm (plan() thật, nguồn catalog, Loại buổi Kỷ yếu)
    1. Da lệch xa đích, bật grade: HSL chạy trước; da_lech1 (sau HSL) nhỏ hơn hẳn
       da_lech0; Color Grading tính trên phần CÒN LẠI -> không grade (còn lệch ≤ ngưỡng),
       trong khi cùng ảnh mà tắt HSL thì có grade.
    2. Da đã đúng đích: HSL không đổi (hue = sat = 0, không ghi ô nào), không grade.
    3. Ngưỡng Color Grading: còn lệch 3° -> không; 12° -> có, Sat tính trên phần vượt
       (0.45 × 8 = 3.6), không vượt trần grade_sat_max (8).
    4. Mô hình HSL trong da_trong_lr: Orange Hue âm xoay da về đỏ, Sat dương đậm hơn.

Chạy:  python test_chuoi_mau_da.py
"""
from __future__ import annotations

import contextlib
import copy
import io
import math
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at          # noqa: E402
import test_2ban_quay as tq    # noqa: E402

#  preset WB = WB may (5000 / +12) -> doi_wb ~ khong doi; khong Sat / Vib / toning
PRESET = {"Exposure2012": "0", "Highlights2012": "0", "Shadows2012": "0",
          "Contrast2012": "0", "Whites2012": "0", "Blacks2012": "0",
          "Temperature": "5000", "Tint": "12", "WhiteBalance": "Custom",
          "Saturation": "0", "Vibrance": "0", **{k: "0" for k in at.COT_HSL},
          #  co du cot Color Grading cua plugin moi — thieu thi tool khong biet so goc, khong grade
          **{k: "0" for k in at.COT_MAU if k not in ("Saturation", "Vibrance")}}
M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
               [0.0883024619, 0.2817188376, 0.6299787005]])
M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
               [0.0259040371, 0.7827717662, -0.8086757660]])


def da_lech(cfg, xoay_do: float, chroma_x: float = 1.0) -> list:
    """Màu da (RGB tuyến tính) mà tool sẽ DỰ ĐOÁN lệch đích đúng `xoay_do` độ OkLab
    và chroma × chroma_x (đã bù hệ số hsl_da_chroma_lr)."""
    lab = at.mau_dich_lab(at.dich_da_cuoi(cfg)[0])
    c, h = math.hypot(lab[1], lab[2]), math.atan2(lab[2], lab[1]) - math.radians(xoay_do)
    c = c / float(cfg["hsl_da_chroma_lr"]) * chroma_x
    lab2 = np.array([lab[0], c * math.cos(h), c * math.sin(h)])
    return [float(v) for v in np.linalg.inv(M1) @ ((np.linalg.inv(M2) @ lab2) ** 3)]


def bo_anh(d: Path, face) -> list:
    items = [tq.anh(f"M{i}", i * 5, -1.0, da=face, may_K=5000) for i in range(6)]
    for r in items:
        r["path"] = str(d / Path(r["path"].replace("\\", "/")).name)
        r["crs"] = dict(PRESET)
    return items


def chay(items, d: Path, jobs: Path, **kw):
    its = copy.deepcopy(items)
    exp = {at.khoa_duong_dan(r["path"]): dict(PRESET) for r in its}
    cfg = dict(at.DEFAULTS, source="catalog", bo_qua_nguoi_sua=False, burst=False, blink=False,
               wb="off", bu_sang_ca_buoi=0.0, max_ev_up=1.0, loai_buoi="ky_yeu", dong_bo_loat=False)
    cfg.update(kw)
    cu = at.LR_JOB_DIR
    at.LR_JOB_DIR = jobs
    try:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            at.plan(its, cfg, d, exp)
    finally:
        at.LR_JOB_DIR = cu
    return {Path(r["path"]).stem: r for r in its}, dict(at.MAU_DA)


def main() -> int:
    loi: list = []
    D = at.DEFAULTS
    cfg0 = dict(D, loai_buoi="ky_yeu")
    with tempfile.TemporaryDirectory() as td:
        jobs = Path(td) / "jobs"
        jobs.mkdir()

        # 1. da lech xa (-12 do, nhat x0.75), bat grade: HSL truoc, CG tren phan con lai
        d1 = Path(td) / "xa"
        d1.mkdir()
        xa = bo_anh(d1, da_lech(cfg0, -12.0, 0.75))
        co_hsl, md = chay(xa, d1, jobs, grade=True)
        r = co_hsl["M0"]
        if not (md.get("hsl", {}).get("dai") == "Orange" and md["hsl"]["hue"] < 0 < md["hsl"]["sat"]):
            loi.append(f"Da lech xa: HSL Orange phai hue am / sat duong: {md.get('hsl')}")
        if not r.get("da_lech0") or abs(r["da_lech0"][0]) < 8:
            loi.append(f"da_lech0 phai ghi lech ~-12: {r.get('da_lech0')}")
        if r.get("da_lech1") is None or abs(r["da_lech1"]) > abs(r["da_lech0"][0]) * 0.4:
            loi.append(f"Sau HSL phai con lech it hon han: {r.get('da_lech0')} -> {r.get('da_lech1')}")
        if any(x.get("gr_ghi") and x.get("gr_sat") for x in co_hsl.values()):
            loi.append(f"HSL da sua xong thi Color Grading KHONG duoc grade them (de mau): "
                       f"{[(x.get('da_lech1'), x.get('gr_sat')) for x in co_hsl.values()]}")
        khong_hsl, md2 = chay(xa, d1, jobs, grade=True, hsl_da_ky_yeu=False)
        if not all(x.get("gr_ghi") and x.get("gr_sat") >= 1 for x in khong_hsl.values()):
            loi.append(f"Dung bai: tat HSL thi da lech 12 do phai duoc grade: "
                       f"{[(x.get('da_lech1'), x.get('gr_sat')) for x in khong_hsl.values()]}")
        if md2.get("hsl", {}).get("hue") or md2.get("hsl", {}).get("sat"):
            loi.append("hsl_da_ky_yeu=False ma van ra muc HSL")

        # 2. da dung dich: khong HSL, khong grade
        d2 = Path(td) / "dung"
        d2.mkdir()
        dung = bo_anh(d2, da_lech(cfg0, 0.0, 1.0))
        on, md3 = chay(dung, d2, jobs, grade=True)
        if md3.get("hsl", {}).get("hue") or md3.get("hsl", {}).get("sat") or any(x.get("hsl_ghi") for x in on.values()):
            loi.append(f"Da dung dich: HSL phai khong doi: {md3.get('hsl')}")
        if any(x.get("gr_ghi") for x in on.values()):
            loi.append("Da dung dich: khong duoc Color Grading")
        if abs(md3.get("hue0", 99)) > 1.0 or abs(md3.get("chroma0", 9) - 1.0) > 0.08:
            loi.append(f"Dung bai: trang thai phai ~0 / x1.00: {md3}")

        # 3. nguong Color Grading (HSL tat de thay rieng CG)
        for do_, mong in ((-3.0, False), (-12.0, True)):
            d3 = Path(td) / f"cg{abs(do_):.0f}"
            d3.mkdir()
            kq, _ = chay(bo_anh(d3, da_lech(cfg0, do_, 1.0)), d3, jobs, grade=True, hsl_da_ky_yeu=False)
            co = all(x.get("gr_ghi") and x.get("gr_sat") >= 1 for x in kq.values())
            if co != mong:
                loi.append(f"Lech {do_:+.0f} do: grade {'co' if co else 'khong'}, phai {'co' if mong else 'khong'}: "
                           f"{[(x.get('da_lech1'), x.get('gr_sat')) for x in kq.values()]}")
            if mong:
                s = kq["M0"]["gr_sat"]
                mong_s = round(float(D["grade_gain_hue"]) * (12.0 - float(D["grade_nguong_hue"])))
                if abs(s - mong_s) > 1 or s > D["grade_sat_max"]:
                    loi.append(f"Sat grade {s} phai ~{mong_s} (tinh tren phan vuot nguong), <= {D['grade_sat_max']}")

    # 4. mo hinh HSL
    r = {"face_rgb": da_lech(cfg0, 0.0, 1.0), "wb_may_K": 5000, "model": "ILCE-7M4", "crs": dict(PRESET)}
    ref = at.dich_da_cuoi(cfg0)[0]
    l0 = at.da_trong_lr(r, cfg0, dict(PRESET), 5000, 12, ref)
    l1 = at.da_trong_lr(r, cfg0, dict(PRESET), 5000, 12, ref,
                        hsl={"HueAdjustmentOrange": -30, "SaturationAdjustmentOrange": 30})
    h0, h1 = math.degrees(math.atan2(l0[2], l0[1])), math.degrees(math.atan2(l1[2], l1[1]))
    c0, c1 = math.hypot(l0[1], l0[2]), math.hypot(l1[1], l1[2])
    #  da dich o LR hue ~15 = giua Red / Orange -> Orange chi an mot nua: -4.5 do HSV, x1.15
    if not (h1 < h0 - 2 and c1 > c0 * 1.10):
        loi.append(f"Mo hinh HSL: Orange -30/+30 phai xoay ve do va dam hon: hue {h0:.1f}->{h1:.1f}, chroma x{c1/c0:.2f}")

    for m in loi:
        print("  [!]", m)
    print("TAT CA DAT" if not loi else f"{len(loi)} LOI")
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
