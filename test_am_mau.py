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

print("7. WB lượt 2 theo da đo thật — HAI CHIỀU, mọi buổi (16/10, DERMAL LOGIA RAW) + Tint (TEST)")
#  da dựng ở WB đã áp 5012 K trong khi WB "đúng" là 3700 K -> da vàng
VANG_THAT = (3700.0, 16.0)
#  ảnh TRONG NHÀ -> đích trong nhà (da trắng hồng), không phải REF (đích ngoài trời của mục 1–6)
REF_T = at.srgb_to_linear(np.asarray(TRONG, float) / 255.0)


def anh_l2(ten, giay, wb_ap=(5012.0, 16.0), **kw):
    r = anh(ten, giay, p_trong=0.98, gio=20, flash=13)
    r.update(new_temp=wb_ap[0], new_tint=wb_ap[1], ngoai_troi=False)
    r.update(kw)
    return r


def do_l2(r, that=VANG_THAT, ref=None):
    ref = REF_T if ref is None else ref
    da = at.doi_wb(ref * 0.6, that, (float(r["new_temp"]), float(r["new_tint"])))
    return {"ok": True, "mien": "melissa",
            "da_cu": cl.srgb_sang_mien(np.tile(at.linear_to_srgb(np.clip(da, 0, 1)), (300, 1)), "melissa")}


CV = dict(CFG, source="catalog", wb="skin", loai_buoi="su_kien")
loat_v = [anh_l2(f"V{i}", i * 2) for i in range(3)]
nv = at.wb_da_luot2([loat_v[0]], {id(loat_v[0]): do_l2(loat_v[0])}, CV, tat_ca=loat_v)
ktra("da thật VÀNG -> cả loạt (kể cả tấm không đo) WB lạnh đi, cùng một K",
     nv == 3 and len({r["wb_l2"] for r in loat_v}) == 1 and loat_v[0]["wb_l2"][0] < 5012 - 300,
     str([r.get("wb_l2") for r in loat_v]))
ktra("…GIỮ Tint, gắn lech_da (+) + ghi chú lạnh", all(r["wb_l2"][1] == 16 and r.get("lech_da", 0) > 0
                                                    and "wb-da-luot2:lanh" in r["notes"] for r in loat_v))
m0, m_that = 1e6 / 5012.0, 1e6 / VANG_THAT[0]
m_moi = 1e6 / loat_v[0]["wb_l2"][0]
ktra("…kéo wb_da_l2_manh (0.6) quãng mired tới WB đưa da về đích (±3 mired)",
     abs((m_moi - m0) - 0.6 * (m_that - m0)) <= 3.0, f"{m_moi - m0:.1f} vs {0.6 * (m_that - m0):.1f}")
r1 = anh_l2("V1x", 0)
at.wb_da_luot2([r1], {id(r1): do_l2(r1)}, dict(CV, wb_da_l2_manh=1.0))
ktra("wb_da_l2_manh 1.0 -> về đúng WB thật (±3 mired)", abs(1e6 / r1["wb_l2"][0] - m_that) <= 3.0,
     str(r1.get("wb_l2")))
xanh = anh_l2("XA", 0, wb_ap=(5012.0, 16.0))
at.wb_da_luot2([xanh], {id(xanh): do_l2(xanh, that=(7000.0, 16.0))}, CV)
ktra("da thật XANH / lạnh quá -> WB ẤM lên (ngược chiều), giữ Tint",
     xanh.get("wb_l2") and xanh["wb_l2"][0] > 5012 + 300 and xanh["wb_l2"][1] == 16
     and xanh.get("lech_da", 0) < 0 and "wb-da-luot2:am" in xanh["notes"], str(xanh.get("wb_l2")))
gan = anh_l2("G", 0)
at.wb_da_luot2([gan], {id(gan): do_l2(gan, that=(4950.0, 16.0))}, CV)
ktra("da gần đích (< wb_da_l2_nguong) -> không đổi", not gan.get("wb_l2") and not gan.get("lech_da"))
REF_N = at.srgb_to_linear(np.asarray(NGOAI, float) / 255.0)
for ten_, kw_, cf_, ref_ in (("Kỷ yếu", {}, dict(CV, loai_buoi="ky_yeu"), None),
                             ("ngoài trời (đích da rám)", {"ngoai_troi": True, "p_trong": 0.01}, CV, REF_N),
                             ("WB theo nhiệt độ máy", {}, dict(CV, wb="asshot"), None)):
    x = anh_l2("X", 0, **kw_)
    at.wb_da_luot2([x], {id(x): do_l2(x, ref=ref_)}, cf_)
    ktra(f"{ten_} -> CŨNG xét (mọi buổi), lạnh đi", x.get("wb_l2") and x["wb_l2"][0] < 5012 - 300,
         str(x.get("wb_l2")))
for ten_, kw_, cf_ in (("WB Không đụng tới", {}, dict(CV, wb="off")), ("nguồn .xmp", {}, dict(CV, source="sidecar")),
                       ("ảnh đen trắng", {"bw": True}, CV)):
    x = anh_l2("Y", 0, **kw_)
    at.wb_da_luot2([x], {id(x): do_l2(x)}, cf_)
    ktra(f"{ten_} -> không đổi", not x.get("wb_l2"), str(x.get("wb_l2")))
nt = anh_l2("NT", 0, ngoai_toi=True)
at.wb_da_luot2([nt], {id(nt): do_l2(nt)}, CV)
ktra("ngoài trời buổi tối + ô 'giữ ấm' BẬT -> không kéo lạnh", not nt.get("wb_l2"))
nt2 = anh_l2("NT2", 0, ngoai_toi=True)
at.wb_da_luot2([nt2], {id(nt2): do_l2(nt2)}, dict(CV, wb_ngoai_toi=False))
ktra("…tắt ô 'giữ ấm' -> kéo lạnh như mọi ảnh", nt2.get("wb_l2") and nt2["wb_l2"][0] < 5012)
nt3 = anh_l2("NT3", 0, ngoai_toi=True)
at.wb_da_luot2([nt3], {id(nt3): do_l2(nt3, that=(7000.0, 16.0))}, CV)
ktra("…da xanh ở ảnh ngoài trời tối vẫn được ẤM lên", nt3.get("wb_l2") and nt3["wb_l2"][0] > 5012)
tr = anh_l2("T", 0)
at.wb_da_luot2([tr], {id(tr): do_l2(tr, that=(2600.0, 16.0))}, dict(CV, wb_da_l2_tran_K=800.0))
ktra("kẹp trần wb_da_l2_tran_K quanh WB đã áp", tr.get("wb_l2") and tr["wb_l2"][0] >= 5012 - 800,
     str(tr.get("wb_l2")))
#  16/10 (buổi TEST — da tím: G thiếu so với cả R lẫn B, B/R gần đích): lượt kiểm chỉnh cả TINT
#  — kéo wb_da_l2_manh_tint (0.3) quãng tới Tint đưa da về đích, lệch ≥ 4 mới chỉnh, trần ±10
tim = anh_l2("TIM", 0)
at.wb_da_luot2([tim], {id(tim): do_l2(tim, that=(5012.0, 40.0))}, CV)
ktra("da tím (Tint thật 40 vs áp 16, Temp đúng) -> Tint kéo về phía 40 đúng 0.3 quãng, GIỮ Temp",
     tim.get("wb_l2") and abs(tim["wb_l2"][0] - 5012) <= 60 and 16 + 4 <= tim["wb_l2"][1] <= 16 + 10
     and tim.get("wb_l2_da") and "wb-da-luot2:tint" in tim["notes"], str(tim.get("wb_l2")))
gan_t = anh_l2("GT", 0)
at.wb_da_luot2([gan_t], {id(gan_t): do_l2(gan_t, that=(5012.0, 19.0))}, CV)
ktra("Tint lệch < 4 -> không đổi", not gan_t.get("wb_l2"), str(gan_t.get("wb_l2")))
xa_t = anh_l2("XT", 0)
at.wb_da_luot2([xa_t], {id(xa_t): do_l2(xa_t, that=(5012.0, 120.0))}, CV)
ktra("Tint lệch rất xa -> chạm trần ±10 quanh Tint đã áp", xa_t.get("wb_l2") and xa_t["wb_l2"][1] == 26,
     str(xa_t.get("wb_l2")))
tat_t = anh_l2("TT", 0)
at.wb_da_luot2([tat_t], {id(tat_t): do_l2(tat_t, that=(5012.0, 40.0))}, dict(CV, wb_da_l2_tint=False))
ktra("tắt wb_da_l2_tint -> giữ Tint (như trước 16/10)", not tat_t.get("wb_l2"), str(tat_t.get("wb_l2")))
ca_hai = anh_l2("CH", 0)
at.wb_da_luot2([ca_hai], {id(ca_hai): do_l2(ca_hai, that=(3700.0, 40.0))}, CV)
ktra("vàng + tím -> Temp lạnh đi VÀ Tint chỉnh trong cùng một lần",
     ca_hai.get("wb_l2") and ca_hai["wb_l2"][0] < 5012 - 300 and ca_hai["wb_l2"][1] > 16 + 3
     and "wb-da-luot2:lanh" in ca_hai["notes"] and "wb-da-luot2:tint" in ca_hai["notes"], str(ca_hai.get("wb_l2")))
am_x = anh_l2("A", 0, am_mau=1.6, wb_l2=(9000, 30))
at.wb_da_luot2([am_x], {id(am_x): do_l2(am_x)}, CV, tat_ca=[am_x])
ktra("ảnh ám xanh nặng giữ WB lượt 2 của nó (không bị xoá / đè)", am_x.get("wb_l2") == (9000, 30))
dd_ = [anh_l2(f"D{i}", i * 2) for i in range(3)] + [anh_l2("E", 900)]
dd_[1]["meter_boxes"] = [[0, 0, 200, 200]]
dai = at.chon_dai_dien_da(dd_, CV)
ktra("chon_dai_dien_da: một tấm mỗi loạt, mặt lớn nhất", len(dai) == 2 and dd_[1] in dai and dd_[3] in dai,
     str([r["path"][-8:] for r in dai]))
ktra("wb_da_can: WB Không đụng tới / grey-world / nguồn xmp -> không; Kỷ yếu -> có",
     at.wb_da_can(CV) and at.wb_da_can(dict(CV, loai_buoi="ky_yeu"))
     and not at.wb_da_can(dict(CV, wb="off")) and not at.wb_da_can(dict(CV, wb="grey"))
     and not at.wb_da_can(dict(CV, source="sidecar")))

print("8. Chốt VÙNG TRẮNG ở lượt kiểm (16/10 TestAnhCuoi — ảnh ngoài trời XANH vì WB theo da)")
XAM = np.full(3, 0.75)                     # vật trung tính sáng (áo trắng) — L OkLab ~0.91


def do_l2w(r, that=VANG_THAT, trang_that=None):
    """như do_l2 + VÙNG TRẮNG: vật trung tính ĐÚNG ở WB `trang_that` (mặc định WB đã áp), dựng ở
    WB đã áp của ảnh."""
    do = do_l2(r, that)
    wb_ap = (float(r["new_temp"]), float(r["new_tint"]))
    w = at.doi_wb(XAM, trang_that or wb_ap, wb_ap)
    do["trung"] = cl.srgb_sang_mien(np.tile(at.linear_to_srgb(np.clip(w, 0, 1)), (300, 1)), "melissa")
    return do


WB_AP = (5012.0, 16.0)
k_bien = at._K_bien_trang(XAM + at.EPS, WB_AP, 0.0 - CV["wb_da_l2_trang_xanh"])
neo = anh_l2("NEO", 0, wb_neo_trang=True)
at.wb_da_luot2([neo], {id(neo): do_l2w(neo)}, CV)
ktra("ảnh NEO WB theo vùng trắng, da VÀNG, trắng đúng -> kéo lạnh DỪNG ở biên vùng trắng",
     neo.get("wb_l2_chan") == "chan-lanh" and 5012 - 300 < k_bien < 5012
     and (not neo.get("wb_l2") or neo["wb_l2"][0] >= k_bien - 5), f"{neo.get('wb_l2')} · biên {k_bien:.0f}")
ktra("…lưu vùng trắng MỐC (đo một lần, kèm WB lúc đo)",
     neo.get("trang_l2_ref") is not None and tuple(neo["trang_l2_ref"][1]) == WB_AP, str(neo.get("trang_l2_ref")))
#  vòng 2: ảnh dựng đã ám (điểm "trắng" đo lại sẽ sai) — dùng MỐC, không đo lại
neo["new_temp"] = float((neo.get("wb_l2") or WB_AP)[0])
do2 = do_l2w(neo)
do2["trung"] = do2["trung"][:10]                          # đo lại không được (ít điểm)
at.wb_da_luot2([neo], {id(neo): do2}, CV)
ktra("…vòng 2 dùng lại MỐC: vẫn không lạnh quá biên",
     not neo.get("wb_l2") or neo["wb_l2"][0] >= k_bien - 5, str(neo.get("wb_l2")))
khong_neo = anh_l2("KN", 0)
at.wb_da_luot2([khong_neo], {id(khong_neo): do_l2w(khong_neo)}, CV)
ktra("ảnh KHÔNG neo, trong nhà / flash nổ -> như cũ: kéo lạnh theo da (> 300 K)",
     khong_neo.get("wb_l2") and khong_neo["wb_l2"][0] < 5012 - 300 and not khong_neo.get("wb_l2_chan"),
     str(khong_neo.get("wb_l2")))
ngay = anh_l2("NG", 0, flash=16, fnumber=3.5, exposure_time=1 / 400, iso=100)
at.wb_da_luot2([ngay], {id(ngay): do_l2w(ngay)}, CV)
ktra("ảnh ÁNH SÁNG NGÀY mạnh (EV100 ≥ 11, flash không nổ), không neo -> kéo lạnh ≤ 150 K",
     ngay.get("wb_l2") and ngay["wb_l2"][0] >= 5012 - 150 and ngay.get("wb_l2_chan") == "chan-lanh-ngay"
     and at._ngay_manh(ngay, CV) and not at._ngay_manh(khong_neo, CV), str(ngay.get("wb_l2")))
xanh_tr = anh_l2("XT2", 0, wb_neo_trang=True)
at.wb_da_luot2([xanh_tr], {id(xanh_tr): do_l2w(xanh_tr, that=WB_AP, trang_that=(5800.0, 16.0))}, CV)
ktra("ảnh neo, da ĐÚNG mà vùng trắng đã XANH (trắng thật ở 5800 K) -> ấm lên về biên, ≤ 500 K",
     xanh_tr.get("wb_l2") and 5012 < xanh_tr["wb_l2"][0] <= 5012 + 500
     and "wb-trang-luot2:am" in xanh_tr["notes"], str(xanh_tr.get("wb_l2")))
tim_n = anh_l2("TIMN", 0, wb_neo_trang=True)
tim_k = anh_l2("TIMK", 0)
at.wb_da_luot2([tim_n], {id(tim_n): do_l2w(tim_n, that=(5012.0, 120.0))}, CV)
at.wb_da_luot2([tim_k], {id(tim_k): do_l2w(tim_k, that=(5012.0, 120.0))}, CV)
ti_n = (tim_n.get("wb_l2") or WB_AP)[1]
ti_k = (tim_k.get("wb_l2") or WB_AP)[1]
#  da lệch Tint xa thì phép giải dời cả Temperature (bị chặn ở biên b) -> biên Tint tính ở K đã chốt
ti_bien = at._ti_bien_trang(XAM + at.EPS, WB_AP, float((tim_n.get("wb_l2") or WB_AP)[0]),
                            CV["wb_da_l2_trang_tint"])
ktra("ảnh neo: Tint theo da dừng ở biên vùng trắng (OkLab a ≤ +0.006 ở K đã chốt), không neo chạm trần +10",
     ti_k == 26 and 16 < ti_n <= round(ti_bien) and ti_n < ti_k
     and tim_n.get("wb_l2_chan") in ("chan-lanh", "chan-tint"), f"neo {ti_n} · không neo {ti_k} · biên {ti_bien:.1f}")
tat_c = anh_l2("TC", 0, wb_neo_trang=True)
at.wb_da_luot2([tat_c], {id(tat_c): do_l2w(tat_c)}, dict(CV, wb_da_l2_trang=False))
ktra("tắt wb_da_l2_trang -> như trước 16/10 (kéo lạnh theo da)",
     tat_c.get("wb_l2") and tat_c["wb_l2"][0] < 5012 - 300, str(tat_c.get("wb_l2")))

print()
print("TẤT CẢ ĐẠT" if not LOI else f"{len(LOI)} LỖI: " + "; ".join(LOI))
sys.exit(1 if LOI else 0)
