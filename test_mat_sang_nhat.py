#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đo theo MẶT NÉT SÁNG NHẤT (11/10) — at.do_mat_sang_nhat.

CHUYỆN ĐANG SỬA
    User 11/10: ảnh cùng cảnh "bức tăng EV bức giảm EV"; "chỉ đo sáng trên các
    khuôn mặt sắc nét, out nét bỏ qua; ảnh tập thể thì xử lý cho khuôn mặt ánh
    sáng đang sáng nhất". Buổi 1010: SAY08563 / SAY08566 cùng nhóm người, cùng
    thông số máy, mặt sáng nhất đều ~-0.4 — phép đo cũ (trung bình có trọng số)
    ra -0.53 và -1.24, Exposure -0.47 và +0.36.

Mục kiểm
    1. DEFAULTS bật; ảnh MỘT mặt giữ nguyên.
    2. Ảnh nhóm: lấy mặt sáng nhất; có cờ mat-sang-nhat; metered_ev dời cùng.
    3. Mặt OUT NÉT (nét < 0.4 × mặt nét nhất) sáng hơn -> bỏ qua.
    4. Mặt điểm YuNet thấp sáng hơn -> bỏ qua.
    5. Đám đông: không sáng hơn phép đo cũ quá mat_sang_nhat_tran.
    6. Lọc xong còn < 2 mặt -> giữ nguyên.
    7. Tắt -> giữ nguyên; _tra_mat_goc trả số cũ (GUI tính lại nhiều lần).
    8. Số đo THẬT SAY08563/08566: khoảng cách hai phép đo hẹp lại.
    9. plan() thật hai lần liền trên cùng items -> cùng kết quả (không cộng dồn).
   10. Giao diện: ô mặc định BẬT, bỏ tích -> read_cfg mang False.

Chạy:  python test_mat_sang_nhat.py
"""
from __future__ import annotations

import contextlib
import copy
import io
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at          # noqa: E402
import test_san_phang as ts    # noqa: E402

T0 = datetime(2026, 10, 10, 15, 26, 0)


def mat(ev, sharp=0.4, score=0.9):
    return {"ev": ev, "sharp": sharp, "score": score, "box": (0.0, 0.0, 30.0, 40.0)}


def anh(cu, faces, ten="A"):
    r = ts._anh(ten, cu, T0)
    r["face_debug"] = faces
    r["faces_n"] = len(faces)
    return r


def chay(r, **kw):
    cfg = dict(at.DEFAULTS, **kw)
    at._tra_mat_goc([r])
    at.do_mat_sang_nhat([r], cfg)
    return r


#  Số đo THẬT buổi 1010 (phan_tich/1010_*.pkl): (ev, nét, điểm) từng mặt
SAY08563 = (-0.534, [(-0.71, 0.38, 0.89), (-0.54, 0.30, 0.88), (-1.01, 0.36, 0.87),
                     (-0.46, 0.38, 0.86), (-0.49, 0.28, 0.86), (-0.38, 0.36, 0.85),
                     (-0.54, 0.42, 0.83), (-0.43, 0.39, 0.83)])
SAY08566 = (-1.244, [(-1.24, 0.34, 0.89), (-0.52, 0.32, 0.89), (-1.29, 0.36, 0.88),
                     (-0.69, 0.45, 0.87), (-0.67, 0.33, 0.87), (-0.52, 0.42, 0.86),
                     (-0.50, 0.35, 0.84), (-0.44, 0.31, 0.75), (-3.74, 0.17, 0.53)])


def main() -> int:
    loi: list = []
    if not at.DEFAULTS.get("mat_sang_nhat"):
        loi.append("DEFAULTS: mat_sang_nhat phai BAT (user yeu cau 11/10)")

    # 1 — mot mat
    r = chay(anh(-1.3, [mat(-1.3)]))
    if abs(r["metered_face_ev"] + 1.3) > 1e-9 or "mat-sang-nhat" in r["notes"]:
        loi.append("Anh MOT mat phai giu nguyen phep do")

    # 2 — nhom
    r = chay(anh(-1.4, [mat(-1.6), mat(-0.95), mat(-1.3)]))
    if abs(r["metered_face_ev"] + 0.95) > 1e-6:
        loi.append(f"Anh nhom: phai lay mat sang nhat -0.95, dang {r['metered_face_ev']}")
    if "mat-sang-nhat" not in r["notes"]:
        loi.append("Anh nhom: thieu co mat-sang-nhat")
    if abs(r["metered_ev"] - (-1.4 + 0.45)) > 1e-6:
        loi.append(f"Anh nhom: metered_ev phai doi cung (+0.45), dang {r['metered_ev']}")

    # 3 — mat out net sang hon
    r = chay(anh(-1.4, [mat(-1.5, sharp=0.5), mat(-1.2, sharp=0.45), mat(-0.3, sharp=0.1)]))
    if abs(r["metered_face_ev"] + 1.2) > 1e-6:
        loi.append(f"Mat OUT NET (0.1 < 0.4 x 0.5) phai bi bo: mong -1.2, dang {r['metered_face_ev']}")

    # 4 — diem thap
    r = chay(anh(-1.4, [mat(-1.5), mat(-1.2), mat(-0.3, score=0.5)]))
    if abs(r["metered_face_ev"] + 1.2) > 1e-6:
        loi.append(f"Mat diem YuNet 0.5 < 0.6 phai bi bo: mong -1.2, dang {r['metered_face_ev']}")

    # 5 — dam dong: chan
    r = chay(anh(-1.5, [mat(-0.2)] + [mat(-1.5)] * 20))
    tran = float(at.DEFAULTS["mat_sang_nhat_tran"])
    if abs(r["metered_face_ev"] - (-1.5 + tran)) > 1e-6:
        loi.append(f"Dam dong: khong duoc sang hon phep do cu qua {tran} EV, dang {r['metered_face_ev']}")

    # 6 — loc xong con 1 mat
    r = chay(anh(-1.4, [mat(-1.4, sharp=0.5), mat(-0.3, sharp=0.05)]))
    if abs(r["metered_face_ev"] + 1.4) > 1e-9:
        loi.append("Loc xong con 1 mat thi giu nguyen")

    # 7 — tat + tra so goc
    r = chay(anh(-1.4, [mat(-1.6), mat(-0.95)]), mat_sang_nhat=False)
    if abs(r["metered_face_ev"] + 1.4) > 1e-9:
        loi.append("Tat: phai giu nguyen phep do")
    r = chay(anh(-1.4, [mat(-1.6), mat(-0.95)]))
    at._tra_mat_goc([r])
    if abs(r["metered_face_ev"] + 1.4) > 1e-9 or abs(r["metered_ev"] + 1.4) > 1e-9:
        loi.append("_tra_mat_goc phai tra lai phep do cu (GUI tinh lai nhieu lan)")

    # 8 — so do that 1010
    a = chay(anh(SAY08563[0], [mat(e, s, d) for e, s, d in SAY08563[1]], "SAY08563"))
    b = chay(anh(SAY08566[0], [mat(e, s, d) for e, s, d in SAY08566[1]], "SAY08566"))
    cu = abs(SAY08563[0] - SAY08566[0])
    moi = abs(a["metered_face_ev"] - b["metered_face_ev"])
    print(f"  SAY08563/08566: phep do cu cach nhau {cu:.2f} EV -> moi {moi:.2f} EV "
          f"({a['metered_face_ev']:+.2f} / {b['metered_face_ev']:+.2f})")
    if not moi < cu / 2 + 0.01:
        loi.append(f"So do that 1010: hai anh cung nhom phai gan nhau hon (cu {cu:.2f}, moi {moi:.2f})")
    if b["metered_face_ev"] > -0.40:
        loi.append("SAY08566: mat 3.74 (net 0.17, diem 0.53) khong duoc la mat do")

    # 9 — plan() hai lan
    ds = [anh(-1.4, [mat(-1.6), mat(-0.95), mat(-1.3)], "B1"),
          anh(-1.2, [mat(-1.2)], "B2")]
    cfg = ts._cfg()
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        at.plan(ds, cfg, None, None)
        d1 = [(r["metered_face_ev"], r["delta_ev"]) for r in ds]
        at.plan(ds, cfg, None, None)
        d2 = [(r["metered_face_ev"], r["delta_ev"]) for r in ds]
    if d1 != d2:
        loi.append(f"plan() hai lan phai ra cung ket qua: {d1} vs {d2}")
    if abs(ds[0]["metered_face_ev"] + 0.95) > 1e-6:
        loi.append("plan(): anh nhom phai do theo mat sang nhat")

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
        if app.read_cfg().get("mat_sang_nhat") is not True:
            loi.append("Giao dien mo len: mat_sang_nhat phai BAT")
        app.v_mat_sang_nhat.set(False)
        if app.read_cfg().get("mat_sang_nhat") is not False:
            loi.append("Bo tich 'Anh nhieu nguoi: do mat net sang nhat' thi read_cfg phai mang False")
    finally:
        root.destroy()
    return loi


if __name__ == "__main__":
    sys.exit(main())
