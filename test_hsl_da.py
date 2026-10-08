#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HSL kênh da (Loại buổi Kỷ yếu, vòng 5) — kiểm bằng plan() + write_sidecars() THẬT.

CHUYỆN ĐANG SỬA
    Ảnh hoàn thiện buổi raw 19.4 cùng khung với preview Lightroom nên so được từng
    điểm ảnh: ảnh hoàn thiện đổi THEO DẢI MÀU (cam xoay về đỏ, đậm hơn; vàng giữ;
    trung tính gần như đứng yên) — dấu vân tay của HSL. User: "HSL chỉ nên can
    thiệp vào kênh màu sắc tố của da đo được — thường là Orange".

Mục kiểm
    1. Kỷ yếu: kênh da = Orange (da thường), Hue âm (về đỏ), Sat dương; MỘT mức cho
       mọi ảnh màu (cả ảnh không mặt); ảnh B/W không đụng.
    2. Chỉ dải da đổi: Red / Yellow ghi đúng số gốc của preset.
    3. Cộng vào số GỐC: preset Orange Sat +10 -> ghi 10 + mức tool.
    4. Cưới: không ghi HSL. Ảnh tool đã từng ghi HSL (job cũ) -> trả số gốc.
    5. Bản xuất plugin cũ (không có cột HSL): không ghi HSL, cảnh báo Reload plugin.
    6. File job mang đủ sáu cột HSL.
    7. trong_so_hsl(): tâm dải = 1, giữa hai tâm = 0.5 / 0.5.

Chạy:  python test_hsl_da.py
"""
from __future__ import annotations

import contextlib
import copy
import csv
import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at          # noqa: E402
import test_2ban_quay as tq    # noqa: E402

PRESET = {"Exposure2012": "0", "Highlights2012": "0", "Shadows2012": "0",
          "Contrast2012": "0", "Whites2012": "0", "Blacks2012": "0",
          "Temperature": "5000", "Tint": "10", "WhiteBalance": "Custom",
          "Saturation": "19", "Vibrance": "25"}
HSL0 = {k: "0" for k in at.COT_HSL}
DA_KY_YEU = [0.61, 0.42, 0.355]          # da preview that (HUY04176), tuyen tinh


def bo_anh(d: Path) -> list:
    items = [tq.anh(f"M{i}", i * 5, -1.0 + 0.05 * i, da=DA_KY_YEU) for i in range(6)]
    k = tq.anh("KMAT", 40, -1.2)
    k.update(faces_n=0, faces_found=0, metered_face_ev=None, meter_used="subject", face_rgb=None)
    bw = tq.anh("BW", 45, -1.0, da=DA_KY_YEU)
    bw["bw"] = True
    items += [k, bw]
    for r in items:
        r["path"] = str(d / Path(r["path"].replace("\\", "/")).name)
        r["crs"] = dict(PRESET)
    return items


def chay(items, d: Path, jobs: Path, cot_hsl=True, them: dict | None = None, **kw):
    its = copy.deepcopy(items)
    exp = {}
    for r in its:
        e = dict(PRESET, **(HSL0 if cot_hsl else {}))
        if cot_hsl and Path(r["path"]).stem == "M0":
            e["SaturationAdjustmentOrange"] = "10"
        e.update((them or {}).get(Path(r["path"]).stem, {}))
        exp[at.khoa_duong_dan(r["path"])] = e
    cfg = dict(at.DEFAULTS, source="catalog", bo_qua_nguoi_sua=False, burst=False, blink=False,
               wb="skin", bu_sang_ca_buoi=0.0, max_ev_up=1.0)
    cfg.update(kw)
    cu = at.LR_JOB_DIR
    at.LR_JOB_DIR = jobs
    try:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            at.plan(its, cfg, d, exp)
            at.write_sidecars(its, cfg, d)
        job = at.LAST_JOB
    finally:
        at.LR_JOB_DIR = cu
    return {Path(r["path"]).stem: r for r in its}, dict(at.HSL_DA), at.CANH_BAO_PLUGIN, job


def main() -> int:
    loi: list = []
    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "raw 19.4"
        d.mkdir()
        jobs = Path(td) / "jobs"
        jobs.mkdir()
        items = bo_anh(d)

        ky, hsl, cb, job = chay(items, d, jobs, loai_buoi="ky_yeu")
        # 1.
        if hsl.get("dai") != "Orange":
            loi.append(f"Kenh da phai la Orange, dang {hsl}")
        if not (hsl.get("hue", 0) < 0 < hsl.get("sat", 0)):
            loi.append(f"Da thuong phai Hue am (ve do), Sat duong: {hsl}")
        mau = [k for k in ky if k != "BW"]
        if any(not ky[k].get("hsl_ghi") for k in mau):
            loi.append("Moi anh mau (ca anh khong mat) phai nhan HSL da")
        if ky["BW"].get("hsl_ghi"):
            loi.append("Anh B/W khong duoc ghi HSL")
        h, s = int(hsl.get("hue", 0)), int(hsl.get("sat", 0))
        for k in mau:
            m = ky[k].get("hsl_moi") or {}
            goc_s = 10.0 if k == "M0" else 0.0
            if m.get("HueAdjustmentOrange") != float(h) or m.get("SaturationAdjustmentOrange") != goc_s + s:
                loi.append(f"{k}: Orange {m.get('HueAdjustmentOrange')}/{m.get('SaturationAdjustmentOrange')}"
                           f" phai {h}/{goc_s + s} (3. cong vao so goc)")
            # 2.
            if any(m.get(c) != 0.0 for c in at.COT_HSL if "Orange" not in c):
                loi.append(f"{k}: dai Red / Yellow phai giu so goc 0: {m}")
        # 6.
        with open(job, encoding="utf-8-sig") as fh:
            rows = {Path(r["path"]).stem: r for r in csv.DictReader(fh, delimiter="\t")}
        if any(c not in next(iter(rows.values())) for c in at.COT_HSL):
            loi.append("File job thieu cot HSL")
        if rows["M1"].get("HueAdjustmentOrange") != str(h) or rows["BW"].get("HueAdjustmentOrange"):
            loi.append(f"Job: M1 Orange {rows['M1'].get('HueAdjustmentOrange')} phai {h}; BW phai trong")

        # 4. Cuoi: khong HSL; anh tool da ghi HSL (job cu o jobs/) -> tra so goc
        cu_, hsl_c, _, _ = chay(items, d, jobs, loai_buoi="cuoi")
        if hsl_c.get("dai") or any(r.get("hsl_ghi") and r.get("hsl_moi", {}).get("HueAdjustmentOrange") != 0.0
                                   for r in cu_.values()):
            loi.append(f"Cuoi khong duoc chinh HSL: {hsl_c}")
        if not cu_["M1"].get("hsl_ghi"):
            loi.append("Anh da tung ghi HSL (job truoc) phai duoc TRA so goc khi Cuoi")
        sach = Path(td) / "jobs_sach"
        sach.mkdir()
        cu2, _, _, _ = chay(items, d, sach, loai_buoi="cuoi")
        if any(r.get("hsl_ghi") for r in cu2.values()):
            loi.append("Cuoi, chua tung ghi HSL: khong duoc ghi o HSL nao")

        # 5. plugin cu — thu muc MOI (chua co moc: moc co cot HSL thi van biet so goc)
        d2 = Path(td) / "raw 19.4 b"
        d2.mkdir()
        items2 = bo_anh(d2)
        cu3, hsl3, cb3, _ = chay(items2, d2, sach, cot_hsl=False, loai_buoi="ky_yeu")
        if any(r.get("hsl_ghi") for r in cu3.values()) or hsl3.get("dai"):
            loi.append("Ban xuat khong co cot HSL: khong duoc ghi HSL")
        if "HSL" not in cb3:
            loi.append(f"Thieu canh bao Reload plugin cho HSL: {cb3!r}")
        if cb:
            loi.append(f"Ban xuat day du ma van canh bao plugin: {cb!r}")

    # 7.
    w = at.trong_so_hsl(30.0)
    if abs(w.get("Orange", 0) - 1.0) > 1e-9:
        loi.append(f"trong_so_hsl(30) phai Orange 1.0: {w}")
    w = at.trong_so_hsl(15.0)
    if abs(w.get("Red", 0) - 0.5) > 1e-9 or abs(w.get("Orange", 0) - 0.5) > 1e-9:
        loi.append(f"trong_so_hsl(15) phai Red/Orange 0.5: {w}")
    w = at.trong_so_hsl(330.0)
    if abs(w.get("Magenta", 0) - 0.5) > 1e-9 or abs(w.get("Red", 0) - 0.5) > 1e-9:
        loi.append(f"trong_so_hsl(330) phai Magenta/Red 0.5: {w}")

    for m in loi:
        print("  [!]", m)
    print("TAT CA DAT" if not loi else f"{len(loi)} LOI")
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
