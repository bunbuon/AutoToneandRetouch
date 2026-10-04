#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đồng bộ loạt chụp (3/10) — CÙNG KHUNG + CÙNG THÔNG SỐ -> CÙNG MỘT MỨC.

CHUYỆN ĐANG SỬA
    Buổi G:\\2709 (cưới, Nikon Z, 1/800 f/2.2 ISO 125): SUB_6485/87/88 ra −0.40
    mà SUB_6486 ra +0.45 (mặt đo nhầm −4.25 EV); SUB_6652–6665 (mẹ + cô dâu,
    cùng khung) nhảy −0.47..+0.45 từng tấm vì phép đo mặt nhảy giữa hai người.
    User: "phải giải quyết dứt điểm". San phẳng cảnh không chữa được: nó đưa mọi
    tấm về cùng "mặt SAU chỉnh", nên phép đo mặt lệch bao nhiêu thì Exposure
    nhảy bấy nhiêu. Luật mới chạy trên KẾT QUẢ cuối: cả loạt nhận cùng một số.

Mục kiểm (plan() THẬT)
    1. Bật (mặc định): mọi tấm trong loạt cùng delta = trung vị delta lúc tắt;
       có cờ dong-bo-loat; cùng mã loạt.
    2. Tắt: trở lại từng tấm một (loạt mẫu lệch > 0.3 EV).
    3. Khác bố cục (chữ ký khung lệch > loat_bo_cuc) -> tách loạt.
    4. Khác thông số (ISO đổi) -> tách.
    5. Khác độ sáng khung (> loat_khung_ev — đèn đổi) -> tách.
    6. Nghỉ quá loat_gio_s giây -> tách.
    7. Khác thân máy, kể cả chụp xen kẽ -> không gộp.
    8. Tấm không thấy mặt trong loạt -> theo loạt, không còn "giữ nguyên".
    9. Giao diện (khi có tkinter + màn hình): ô tích mặc định BẬT, read_cfg
       mang đúng giá trị, bỏ tích -> False.

Chạy:  python test_dong_bo_loat.py      (phần giao diện: xvfb-run -a trên Linux)
"""
from __future__ import annotations

import contextlib
import copy
import io
import statistics as st
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at          # noqa: E402
import test_san_phang as ts    # noqa: E402

T0 = datetime(2026, 9, 27, 10, 0, 0)
SIG_A = [0.9, 0.8, 1.0, 1.1] * 18          # 72 số, như chữ ký thật
SIG_B = [x + 0.30 for x in SIG_A]          # lệch 0.30 > loat_bo_cuc
#[[ Phép đo mặt nhảy như SUB_6652-6665: -1.73/-1.06/-1.37/-1.73/-1.05/-2.35 ]]
MAT = [-1.73, -1.06, -1.37, -1.73, -1.05, -2.35]


def loat(mat=MAT, giay=4, sig=None, iso=None, khung=None, model=None, ten="SUB"):
    ds = []
    for i, m in enumerate(mat):
        r = ts._anh(f"{ten}_{6652 + i}", m, T0 + timedelta(seconds=(giay[i] if isinstance(giay, list) else giay * i)))
        r["metered_subject_ev"] = khung[i] if khung else -1.70
        r["scene_sig"] = list((sig[i] if sig else SIG_A))
        r["iso"] = iso[i] if iso else 125
        r["fnumber"], r["exposure_time"] = 2.2, 1 / 800
        r["model"] = model[i] if model else "NIKON Z 6_2"
        ds.append(r)
    return ds


def chay(ds, **kw):
    cfg = ts._cfg(**kw)
    ds = copy.deepcopy(ds)
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        at.plan(ds, cfg, None, None)
    return {r["path"].split("\\")[-1].split(".")[0]: r for r in ds}


def rong(kq, ks=None):
    v = [float(r["delta_ev"]) for k, r in kq.items() if ks is None or k in ks]
    return max(v) - min(v)


def main() -> int:
    loi: list = []
    if not at.DEFAULTS.get("dong_bo_loat"):
        loi.append("DEFAULTS: dong_bo_loat phai BAT (user yeu cau 3/10)")

    # 1 + 2 — bat / tat
    tat = chay(loat(), dong_bo_loat=False)
    if rong(tat) <= 0.3:
        loi.append(f"Dung bai: luc tat loat mau phai lech > 0.3 EV, dang {rong(tat):.2f}")
    bat = chay(loat())
    if rong(bat) > 1e-6:
        loi.append(f"Bat: ca loat phai CUNG delta, dang lech {rong(bat):.3f}")
    mong = st.median(float(r["delta_ev"]) for r in tat.values())
    if any(abs(float(r["delta_ev"]) - mong) > 1e-3 for r in bat.values()):
        loi.append(f"Bat: delta chung phai la trung vi luc tat ({mong:+.3f})")
    if len({r.get("loat") for r in bat.values()}) != 1 or any(r.get("loat") is None for r in bat.values()):
        loi.append("Bat: ca loat phai cung mot ma loat")
    if not all("dong-bo-loat" in r.get("notes", "") for r in bat.values()):
        loi.append("Bat: thieu co dong-bo-loat trong notes")

    # 3 — khac bo cuc
    kq = chay(loat(sig=[SIG_A] * 3 + [SIG_B] * 3))
    if len({kq[k].get("loat") for k in kq}) != 2:
        loi.append("Khac bo cuc (chu ky lech 0.30) phai tach thanh 2 loat")

    # 4 — khac thong so
    kq = chay(loat(iso=[125, 125, 125, 200, 200, 200]))
    if len({kq[k].get("loat") for k in kq}) != 2:
        loi.append("Doi ISO giua loat phai tach")

    # 5 — den doi (khung lech 0.40)
    kq = chay(loat(khung=[-1.70] * 3 + [-2.10] * 3))
    if len({kq[k].get("loat") for k in kq}) != 2:
        loi.append("Do sang khung lech 0.40 EV (den doi) phai tach")

    # 5b — den ha DAN (moi buoc 0.15 < 0.25, cong don 0.75): so voi tam DAU nen
    #      phai tach; so voi tam lien truoc thi noi thanh mot chuoi — sai.
    kq = chay(loat(khung=[-1.70, -1.85, -2.00, -2.15, -2.30, -2.45]))
    if len({kq[k].get("loat") for k in kq if kq[k].get("loat") is not None}) < 2:
        loi.append("Den ha dan (cong don 0.75 EV) khong duoc noi thanh mot loat")

    # 6 — nghi lau
    kq = chay(loat(giay=[0, 4, 8, 200, 204, 208]))
    if len({kq[k].get("loat") for k in kq}) != 2:
        loi.append("Nghi 192 giay giua loat phai tach")

    # 7 — hai than may chup xen ke
    kq = chay(loat(model=["NIKON Z 6_2", "ILCE-7M4"] * 3))
    nhom = {}
    for r in kq.values():
        nhom.setdefault(r.get("model"), set()).add(r.get("loat"))
    if any(None in v or len(v) != 1 for v in nhom.values()) or len(set.union(*nhom.values())) != 2:
        loi.append("Hai than may xen ke: moi may mot loat rieng, khong gop")

    # 8 — tam khong mat trong loat
    ds = loat()
    ds[2].update(faces_n=0, faces_found=0, metered_face_ev=None, meter_used="subject")
    kq = chay(ds)
    k2 = Path(ds[2]["path"].replace("\\", "/")).stem
    if rong(kq) > 1e-6:
        loi.append(f"Tam khong mat phai theo loat, loat dang lech {rong(kq):.3f}")
    if kq[k2].get("giu_nguyen_exposure"):
        loi.append("Tam khong mat da theo loat thi khong con 'giu nguyen'")

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
        if app.read_cfg().get("dong_bo_loat") is not True:
            loi.append("Giao dien mo len: dong_bo_loat phai BAT")
        app.v_dong_bo_loat.set(False)
        if app.read_cfg().get("dong_bo_loat") is not False:
            loi.append("Bo tich o 'Cung khung + cung thong so' thi read_cfg phai mang False")
    finally:
        root.destroy()
    return loi


if __name__ == "__main__":
    sys.exit(main())
