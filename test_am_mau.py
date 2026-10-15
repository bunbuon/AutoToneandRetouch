#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ảnh ÁM XANH NẶNG -> WB theo da (15/10 — buổi lọc 1037: "nhận diện được khuôn mặt và không
thấy vùng da hoặc thấy 1 ít nhưng lại đang không đưa được màu da về màu đích").

  1. cổng da: da ám xanh bị skin_mask tuyệt đối loại; bu_am_mau + skin_mask(bu) nhận lại;
     da thường / ám vàng / ám tím -> bu None (không đoán)
  2. am_mau_cua: chỉ ngoài trời chắc, ban ngày, khung ám VỪA, không flash, da xanh hơn ngưỡng
  3. wb_cuu_am: giải ra đúng WB "thật" đã làm da xanh (dựng bằng doi_wb), kéo am_mau_manh
  4. cuu_am_mau: theo loạt cùng WB, kẹp trần, ảnh thường KHÔNG đổi, ghi chú
  5. wb_cuu_am_luot2 + curve_da.ghi_job: đo da thật -> WB bổ sung vào job lượt 2
  6. mat_na_da._du_phong: mặt nạ dự phòng có điểm da trên ảnh ám, báo đã bù

    python3 test_am_mau.py
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

os.environ["AUTOTONE_DATA"] = tempfile.mkdtemp(prefix="am_mau_")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402

import autotone as at  # noqa: E402

LOI = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


CFG = dict(at.DEFAULTS, wb="skin", source="catalog")
TRONG, NGOAI = at.dich_da(CFG)
REF = at.srgb_to_linear(np.asarray(NGOAI, float) / 255.0)
MAY = (5600.0, 2.0)
THAT = (15000.0, 45.0)                # WB "đúng" theo Bradford để da ám như lọc 1037 (+1.5 stop)
DA_AM = at.doi_wb(REF * 0.6, THAT, MAY)          # da dựng ở WB máy 5600 -> xanh


def anh(ten, giay, f=None, khung=None, p_trong=0.01, gio=7, flash=0, **kw):
    r = {"path": f"G:/am/{ten}.NEF", "model": "NIKON Z 6_2", "face_rgb": list(f if f is not None else DA_AM),
         #  khung ám VỪA như ảnh thật lọc 1037 (+0.67…+0.97 stop) — da thì ám hơn nhiều
         "rgb_mean": list(khung if khung is not None else [0.25, 0.27, 0.25 * 2 ** 0.8]),
         "p_trong": p_trong, "flash": flash, "dt_obj": datetime(2026, 10, 10, gio, 38) + timedelta(seconds=giay),
         "crs_nen": {"Temperature": "5250", "Tint": "16"}, "crs": {}, "notes": "", "iso": 250,
         "exposure_time": 0.004, "fnumber": 5.6, "scene_sig": list(np.linspace(0.2, 0.8, 72)),
         "metered_subject_ev": -2.0, "meter_boxes": [[10, 10, 50, 60]]}
    r.update(kw)
    return r


print("1. cổng da")
px_am = np.clip(at.linear_to_srgb(np.tile(DA_AM, (200, 1)) * np.random.default_rng(1).uniform(0.85, 1.15, (200, 1))), 0, 1)
bu = at.bu_am_mau(px_am)
ktra("da ám xanh: cổng tuyệt đối loại gần hết", at.skin_mask(px_am).mean() < 0.05, f"{at.skin_mask(px_am).mean():.2f}")
ktra("…bu_am_mau có hệ số, skin_mask(bu) nhận lại da", bu is not None and at.skin_mask(px_am, bu).mean() > 0.8,
     f"{at.skin_mask(px_am, bu).mean() if bu is not None else None}")
px_thuong = np.clip(at.linear_to_srgb(np.tile(REF * 0.6, (200, 1))), 0, 1)
ktra("da thường: bu None (cổng tuyệt đối đã nhận)", at.bu_am_mau(px_thuong) is None and at.skin_mask(px_thuong).mean() > 0.8)
vang = np.clip(at.linear_to_srgb(np.tile([0.5, 0.35, 0.05], (200, 1))), 0, 1)
tim = np.clip(at.linear_to_srgb(np.tile([0.40, 0.10, 0.45], (200, 1))), 0, 1)
ktra("ám vàng / ám tím (B < 0.95 R): không đoán da", at.bu_am_mau(vang) is None and at.bu_am_mau(tim) is None)

print("2. am_mau_cua")
ktra("ngoài trời, 7 giờ, khung ám vừa, da xanh -> ÁM NẶNG", (at.am_mau_cua(anh("A", 0), CFG) or 0) >= 1.3,
     str(at.am_mau_cua(anh("A", 0), CFG)))
for ten, r in (("trong nhà (sân khấu)", anh("B", 0, p_trong=0.9)), ("ban đêm 20 h", anh("C", 0, gio=20)),
               ("flash nổ", anh("D", 0, flash=9)), ("thiếu p_trong (bản phân tích cũ)", anh("E", 0, p_trong=None)),
               ("khung ám CỰC mạnh (đèn màu)", anh("F", 0, khung=[0.05, 0.1, 0.5])),
               ("da thường", anh("G", 0, f=REF * 0.6))):
    ktra(f"…{ten} -> không", at.am_mau_cua(r, CFG) is None)
ktra("…tắt am_mau_bat -> không", at.am_mau_cua(anh("H", 0), dict(CFG, am_mau_bat=False)) is None)

print("3. wb_cuu_am")
w = at.wb_cuu_am(anh("A", 0), dict(CFG, am_mau_manh=1.0), MAY)
ktra("giải ra đúng WB thật đã làm da xanh (±2 mired, ±3 tint)", w is not None and abs(1e6 / w[0] - 1e6 / THAT[0]) <= 2.0
     and abs(w[1] - THAT[1]) < 3, str(w))
w9 = at.wb_cuu_am(anh("A", 0), CFG, MAY)
ktra("am_mau_manh 0.9: ấm hơn preset nhưng chưa tới hết", w9 is not None and 5250 < w9[0] < w[0], str(w9))

print("4. cuu_am_mau")
loat = [anh(f"L{i}", i * 2) for i in range(3)]
thuong = anh("T", 600, f=REF * 0.6, khung=[0.3, 0.3, 0.3])
for r in loat + [thuong]:
    r["temp_adj"], r["tint_adj"] = 141.0, -6.0
n = at.cuu_am_mau(loat + [thuong], CFG)
ktra("3 ảnh ám được cứu, ảnh thường không", n == 3 and all(r.get("am_mau") for r in loat) and not thuong.get("am_mau"))
ktra("…cả loạt cùng WB, ấm hơn preset nhiều", len({r["am_mau_wb"] for r in loat}) == 1 and loat[0]["am_mau_wb"][0] > 7000,
     str(loat[0].get("am_mau_wb")))
ktra("…ảnh thường giữ nguyên temp_adj / tint_adj", thuong["temp_adj"] == 141.0 and thuong["tint_adj"] == -6.0)
ktra("…ghi chú am-mau:wb-theo-da", all("am-mau:wb-theo-da" in r["notes"] for r in loat))
nho = [anh("K", 0)]
at.cuu_am_mau(nho, dict(CFG, am_mau_tran_K=1000.0, am_mau_tran_tint=5.0))
ktra("kẹp trần quanh preset", nho[0]["temp_adj"] <= 1000.0 and nho[0]["tint_adj"] <= 5.0, str(nho[0].get("am_mau_wb")))
ktra("WB 'off' -> không cứu, xoá cờ cũ", at.cuu_am_mau(nho, dict(CFG, wb="off")) == 0 and not nho[0].get("am_mau"))

print("5. lượt 2")
import curve_da  # noqa: E402
import curve_lr as cl  # noqa: E402
r2 = anh("M", 0)
at.cuu_am_mau([r2], dict(CFG, am_mau_tran_K=2000.0))        # lượt 1 kẹp thấp: còn xanh
r2["new_temp"], r2["new_tint"] = r2["am_mau_wb"]
#  da THẬT trên ảnh Lightroom dựng ở WB vừa áp: vẫn còn xanh một chút
da_lr = at.doi_wb(REF * 0.6, THAT, r2["am_mau_wb"])
P = cl.srgb_sang_mien(np.tile(at.linear_to_srgb(da_lr), (300, 1)), "melissa")
n2 = at.wb_cuu_am_luot2([r2], {id(r2): {"ok": True, "da_cu": P, "mien": "melissa"}}, dict(CFG, am_mau_tran_K=12000.0))
ktra("đo da thật còn xanh -> WB bổ sung ấm hơn WB đã áp", n2 == 1 and r2["wb_l2"][0] > r2["am_mau_wb"][0], str(r2.get("wb_l2")))
r3 = anh("N", 0, f=REF * 0.6)
n3 = at.wb_cuu_am_luot2([r3], {id(r3): {"ok": True, "da_cu": P, "mien": "melissa"}}, CFG)
ktra("ảnh không ám -> lượt 2 không đụng WB", n3 == 0 and not r3.get("wb_l2"))
jd = Path(tempfile.mkdtemp())
job = curve_da.ghi_job([r2], "AmMau", job_dir=jd)
dong = job.read_text(encoding="utf-8").splitlines() if job else []
cot = dong[0].split("\t") if dong else []
ktra("job lượt 2 có cột Temperature / Tint đúng số", "Temperature" in cot and dong[1].split("\t")[cot.index("Temperature")]
     == str(r2["wb_l2"][0]), str(cot[-3:]))

print("6. mặt nạ dự phòng")
import mat_na_da  # noqa: E402
img = np.full((200, 200, 3), 40, np.uint8)
mat = (np.clip(at.linear_to_srgb(DA_AM), 0, 1) * 255).astype(np.uint8)
img[40:160, 50:150] = mat
mk, bu_dung = mat_na_da._du_phong(img, (50, 40, 100, 120, 0.9, None))
ktra("mặt nạ dự phòng: có điểm da trên mặt ám xanh, báo đã bù", int(mk.sum()) >= mat_na_da.DIEM_DA_TOI_THIEU and bu_dung,
     f"{int(mk.sum())} điểm")

print()
print("TẤT CẢ ĐẠT" if not LOI else f"{len(LOI)} LỖI: " + "; ".join(LOI))
sys.exit(1 if LOI else 0)
