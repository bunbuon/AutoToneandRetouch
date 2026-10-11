#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chủ thể theo AF trên THÂN người + đồng bộ da trong chuỗi cùng chủ thể (11/10 chiều).

CHUYỆN ĐANG SỬA
    User (buổi 1010, SAY08328-08387): "có ảnh +2.23 EV mà ảnh trước +0.83"; "cùng
    là 2 người đó nhưng ánh sáng đang lệch nhau"; "cùng cảnh và cùng chủ thể thì
    phải đo các bức ảnh cùng chủ thể đó để chỉnh cho ra đều sáng". Đôi đi giữa
    thảm đỏ, máy khoá nét vào NGỰC họ (AF 0.5, 0.54) — không trúng ô mặt nào ->
    tool đo mặt khách hai bên (người sát máy, mặt tí hon ở xa).

Mục kiểm
    1. DEFAULTS bật cả hai.
    2. Số đo THẬT SAY08361: AF trên thân -> đúng hai mặt đôi chính (444,293) và
       (540,303), không khách; phép đo = trung bình hai mặt (lệch 0.42 <= 1 EV).
    3. AF đã trúng một ô mặt -> luật cũ lo, không đụng.
    4. Hơn af_than_toi_da mặt dưới AF -> không biết ai, bỏ qua.
    5. Hai mặt chủ thể lệch > 1 EV -> lấy mặt SÁNG nhất.
    6. Chuỗi cùng chủ thể: đo da từng tấm có nhiễu + xu hướng sáng dần -> Exposure
       giảm dần đều (không nhảy), có cờ dong-bo-chu-the.
    7. Nghỉ quá chu_the_giay / đổi thông số máy -> tách chuỗi.
    8. Loạt cùng bố cục trong chuỗi vẫn MỘT số.
    9. Tắt -> không đổi. 10. Giao diện: ô mặc định BẬT, bỏ tích -> False.

Chạy:  python test_chu_the_af.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at          # noqa: E402
import test_san_phang as ts    # noqa: E402

T0 = datetime(2026, 10, 10, 14, 24, 29)
#  SAY08361 (phan_tich/1010_*.pkl): (x, y, w, h), ev, nét, điểm — preview 1024x683
SAY08361 = [((444.4, 293.7, 23.3, 31.0), -4.21, 0.43, 0.92), ((10.3, 169.3, 39.0, 54.8), -1.75, 0.23, 0.90),
            ((594.1, 313.4, 16.4, 20.5), -5.11, 0.47, 0.89), ((540.2, 303.5, 20.5, 29.8), -3.79, 0.34, 0.88),
            ((37.9, 254.2, 39.8, 66.7), -0.75, 0.14, 0.84), ((187.0, 286.2, 23.7, 40.0), -2.09, 0.28, 0.82),
            ((623.4, 314.2, 14.3, 19.8), -5.23, 0.55, 0.82), ((356.3, 297.7, 16.0, 22.5), -4.34, 0.55, 0.79),
            ((107.4, 311.0, 33.0, 55.6), -2.40, 0.34, 0.78), ((646.8, 316.3, 18.1, 25.1), -3.97, 0.38, 0.78),
            ((855.9, 296.6, 28.6, 44.4), -3.11, 0.29, 0.66), ((692.7, 321.3, 18.8, 27.0), -3.48, 0.38, 0.63),
            ((390.8, 314.4, 16.1, 22.6), -3.71, 0.49, 0.57), ((283.4, 314.4, 18.6, 25.9), -3.97, 0.51, 0.54),
            ((753.1, 315.5, 17.6, 26.2), -4.30, 0.60, 0.53)]


def anh(ten, cu, mats, af=(0.5, 0.5415), on_af=None, khi=T0):
    r = ts._anh(ten, cu, khi)
    r["face_debug"] = [{"box": b, "ev": e, "sharp": s, "score": d, "on_af": bool(on_af and i in on_af)}
                       for i, (b, e, s, d) in enumerate(mats)]
    r["faces_n"] = len(mats)
    r["af_xy"] = af
    r["preview_wh"] = (1024, 683)
    r["fnumber"], r["exposure_time"], r["iso"] = 3.5, 1 / 250, 1250
    return r


def do(r, **kw):
    cfg = dict(at.DEFAULTS, **kw)
    at._tra_mat_goc([r])
    at.do_mat_sang_nhat([r], cfg)
    return r


def chuoi(evs, giay=1.5, iso=None, loat=None, **kw):
    """Chuỗi cùng chủ thể (AF trúng mặt): da đo được evs, delta trước = -1 - ev (đo riêng)."""
    ds = []
    for i, e in enumerate(evs):
        r = anh(f"C{i}", e, [((500.0, 300.0, 30.0 + i, 40.0), e, 0.4, 0.9)], on_af={0},
                khi=T0 + timedelta(seconds=(giay[i] if isinstance(giay, list) else giay * i)))
        if iso:
            r["iso"] = iso[i]
        r["delta_ev"] = round(-1.0 - e, 4)
        r["loat"] = loat[i] if loat else None
        ds.append(r)
    cfg = dict(at.DEFAULTS, **kw)
    at.dong_bo_chu_the(ds, cfg)
    return ds


def main() -> int:
    loi: list = []
    if not (at.DEFAULTS.get("chu_the_af_than") and at.DEFAULTS.get("dong_bo_chu_the")):
        loi.append("DEFAULTS: chu_the_af_than + dong_bo_chu_the phai BAT (user 11/10)")

    # 2 — số đo thật SAY08361
    r = anh("SAY08361", -2.675, SAY08361)
    uv = at.mat_af_than(r, at.DEFAULTS)
    if sorted(f["box"][0] for f in uv) != [444.4, 540.2]:
        loi.append(f"SAY08361: AF tren than phai chon dung doi chinh, dang {[f['box'] for f in uv]}")
    do(r)
    if abs(r["metered_face_ev"] - (-4.21 - 3.79) / 2) > 1e-6 or "chu-the-af-than" not in r["notes"]:
        loi.append(f"SAY08361: phep do phai = trung binh hai mat doi chinh -4.00, dang {r['metered_face_ev']}")
    print(f"  SAY08361: do cu -2.68 (khach) -> {r['metered_face_ev']:+.2f} (doi di giua tham)")

    # 3 — AF trúng mặt
    r = anh("T", -2.675, SAY08361, on_af={1})
    if at.mat_af_than(r, at.DEFAULTS):
        loi.append("AF da trung o mat -> mat_af_than phai tra rong (luat cu lo)")

    # 4 — quá nhiều mặt dưới AF
    dong = [((480.0 + 6 * i, 300.0, 20.0, 26.0), -2.0, 0.4, 0.9) for i in range(5)]
    r = do(anh("D", -3.0, dong))
    if "chu-the-af-than" in r["notes"]:
        loi.append("Hon af_than_toi_da mat duoi AF -> khong duoc chon")

    # 5 — lệch > 1 EV -> sáng nhất
    hai = [((470.0, 300.0, 22.0, 30.0), -4.6, 0.4, 0.9), ((530.0, 300.0, 22.0, 30.0), -0.6, 0.4, 0.9)]
    r = do(anh("H", -3.0, hai))
    if abs(r["metered_face_ev"] + 0.6) > 1e-6:
        loi.append(f"Hai mat lech 4 EV -> phai lay mat sang nhat -0.6, dang {r['metered_face_ev']}")

    # 6 — chuỗi: xu hướng sáng dần + một tấm nhiễu
    evs = [-4.0, -3.3, -3.6, -2.6, -2.3]          # tấm 3 nhiễu tối (-3.6)
    ds = chuoi(evs, max_ev=3.0, max_ev_up=3.0)
    d = [r["delta_ev"] for r in ds]
    print("  chuoi: delta do rieng", [round(-1 - e, 2) for e in evs], "->", [round(x, 2) for x in d])
    if not all(d[i] >= d[i + 1] - 1e-6 for i in range(len(d) - 1)) or d[0] - d[-1] < 1.0:
        loi.append(f"Chuoi sang dan: Exposure phai giam dan (theo xu huong ~1.7 EV) khong nhay, dang {d}")
    if not all("dong-bo-chu-the" in r["notes"] for r in ds if abs(r["delta_ev"] - (-1 - float(r['metered_face_ev']))) > 0.005):
        loi.append("Chuoi: thieu co dong-bo-chu-the")

    # 7 — tách chuỗi
    ds = chuoi([-3.0, -2.0, -3.0, -2.0, -3.0], giay=[0, 1, 2, 30, 31])
    if any("dong-bo-chu-the" in r["notes"] for r in ds[3:]):
        loi.append("Nghi > chu_the_giay -> phai tach chuoi (2 tam cuoi khong du chuoi)")
    ds = chuoi([-3.0, -2.0, -3.0, -2.0, -3.0], iso=[1250, 1250, 1250, 400, 400])
    if any("dong-bo-chu-the" in r["notes"] for r in ds[3:]):
        loi.append("Doi thong so may -> phai tach chuoi")

    # 8 — loạt là một đơn vị
    ds = chuoi([-3.0, -2.6, -2.2, -1.8, -1.4], loat=[None, 7, 7, None, None])
    if abs(ds[1]["delta_ev"] - ds[2]["delta_ev"]) > 1e-9:
        loi.append("Loat trong chuoi phai van MOT so")

    # 9 — tắt
    ds = chuoi([-4.0, -3.3, -3.6, -2.6, -2.3], dong_bo_chu_the=False)
    if any("dong-bo-chu-the" in r["notes"] for r in ds):
        loi.append("Tat dong_bo_chu_the -> khong doi")

    loi += kiem_giao_dien()
    for m in loi:
        print("  [!]", m)
    print("TAT CA DAT" if not loi else f"{len(loi)} LOI")
    return 1 if loi else 0


def kiem_giao_dien() -> list:
    try:
        import tkinter as tk
        import autotone_gui as ag
        root = tk.Tk()
    except Exception as ex:                          # noqa: BLE001
        print(f"  (bo qua phan giao dien: {ex.__class__.__name__}: {ex})")
        return []
    loi = []
    try:
        root.withdraw()
        app = ag.App(root)
        if app.read_cfg().get("dong_bo_chu_the") is not True:
            loi.append("Giao dien mo len: dong_bo_chu_the phai BAT")
        app.v_dong_bo_chu_the.set(False)
        if app.read_cfg().get("dong_bo_chu_the") is not False:
            loi.append("Bo tich 'Cung chu the trong chuoi anh lien' thi read_cfg phai mang False")
    finally:
        root.destroy()
    return loi


if __name__ == "__main__":
    sys.exit(main())
