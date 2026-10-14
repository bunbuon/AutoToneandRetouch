# -*- coding: utf-8 -*-
"""CHỦ THỂ CHÍNH (autotone.nhom_nguoi / gan_chu_the / do_mat_chu_the — 15/10).

User 15/10: "Cần thêm cơ chế Detect chủ thể trong bức ảnh để nhận diện trong các bộ ảnh lấy
ra được 5-6 người xuất hiện nhiều nhất và đặt trọng số cho nó. Khi 1 bức ảnh xuất hiện 1-6
người đó thì sẽ phải ưu tiên đo sáng và cân bằng trên mặt của chủ thể đó. Nếu xuất hiện cùng
lúc 5-6 người thì ưu tiên đo sáng vào người có trọng số xuất hiện nhiều nhất."

Mục kiểm (đặc trưng mặt GIẢ — vectơ 128 chiều mỗi người + nhiễu)
    1. nhom_nguoi gom đúng người, đếm số ảnh
    2. gan_chu_the: ảnh có A + B -> đo mặt A (trọng số cao hơn); chỉ B -> B; mặt A quá nhỏ so
       với B -> B; mặt trong ảnh in trên phông (nhỏ, điểm thấp) không bao giờ là chủ thể;
       meter_boxes / face_rgb / face_p95 đổi theo mặt chủ thể, gọi lại thì trả số gốc
    3. do_mat_chu_the: phép đo mặt = mặt chủ thể; tắt chu_the_chinh -> không đổi gì
    4. buổi quá ít ảnh có mặt -> tắt

Chạy:  python test_chu_the.py
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import numpy as np

for _l in (sys.stdout, sys.stderr):
    try:
        _l.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                        # noqa: BLE001
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at                                        # noqa: E402

LOI: list = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


RNG = np.random.default_rng(7)
NGUOI = {k: RNG.normal(size=128) for k in "ABCP"}


def dt(k):
    v = NGUOI[k] / np.linalg.norm(NGUOI[k]) + RNG.normal(scale=0.045, size=128)
    v = v / np.linalg.norm(v)
    return np.clip(np.round(v * 127), -127, 127).astype(np.int8).tobytes().hex()


def anh(i, mat):
    """mat: [(người, x, rộng, ev, điểm)]"""
    fd, md = [], []
    for k, x, w, ev, s in mat:
        b = (float(x), 50.0, float(w), float(w) * 1.2)
        fd.append({"box": b, "score": s, "ev": ev, "sharp": 0.3, "rgb": [0.4 + ev / 10, 0.3, 0.25], "p95": 0.8})
        md.append({"box": b, "dt": dt(k)})
    return {"path": f"G:/B/IMG{i:04d}.ARW", "face_debug": fd, "mat_dt": md,
            "meter_boxes": [f["box"] + (f["score"],) for f in fd], "face_rgb": [0.5, 0.4, 0.3],
            "face_p95": 0.9, "metered_face_ev": float(np.mean([f["ev"] for f in fd])),
            "metered_ev": float(np.mean([f["ev"] for f in fd])), "notes": ""}


def buoi():
    ds = []
    for i in range(30):                                  # A một mình
        ds.append(anh(i, [("A", 100, 80, -1.0, 0.93)]))
    for i in range(30, 45):                              # A + B, B to hơn chút
        ds.append(anh(i, [("A", 100, 80, -1.2, 0.93), ("B", 300, 90, -0.6, 0.94)]))
    for i in range(45, 55):                              # chỉ B
        ds.append(anh(i, [("B", 300, 90, -0.5, 0.94)]))
    for i in range(55, 60):                              # A đứng xa (nhỏ) + B to
        ds.append(anh(i, [("A", 100, 30, -2.0, 0.92), ("B", 300, 90, -0.7, 0.94)]))
    for i in range(60, 100):                             # ảnh in trên phông P (nhỏ, điểm thấp) + C to
        ds.append(anh(i, [("P", 500, 40, -3.0, 0.84), ("C", 200, 85, -0.9, 0.93)]))
    return ds


def main() -> int:
    cfg = dict(at.DEFAULTS)
    print("1. nhom_nguoi")
    ds = buoi()
    ng = at.nhom_nguoi(ds, cfg)
    so = sorted(p["n_anh"] for p in ng)
    ktra("4 người, đếm đúng số ảnh (A 50, B 30, C 40, P 40)", so == [30, 40, 40, 50], str([(p["n_anh"], round(p["co"], 2), round(p["diem"], 2)) for p in ng]))

    print("2. gan_chu_the")
    ds = buoi()
    goc = copy.deepcopy(ds)
    kq = at.gan_chu_the(ds, cfg)
    ktra("chủ thể: A (50), C (40), B (30) — P (ảnh in: mặt nhỏ, điểm 0.84) bị loại",
         [p["n_anh"] for p in kq["nguoi"]] == [50, 40, 30], str(kq))
    ktra("ảnh A + B -> đo mặt A (trọng số cao hơn)", all(ds[i]["chu_the"]["box"][0] == 100 for i in range(30, 45)),
         str(ds[30].get("chu_the")))
    ktra("chỉ B -> B", all(ds[i]["chu_the"]["box"][0] == 300 for i in range(45, 55)))
    ktra("A đứng xa (30 px < 0.5 × 90) -> B", all(ds[i]["chu_the"]["box"][0] == 300 for i in range(55, 60)))
    ktra("ảnh in trên phông + C -> C", all(ds[i]["chu_the"]["box"][0] == 200 for i in range(60, 100)))
    ktra("meter_boxes / face_rgb / face_p95 theo mặt chủ thể",
         ds[30]["meter_boxes"] == [(100.0, 50.0, 80.0, 96.0, 0.93)] and abs(ds[30]["face_rgb"][0] - 0.28) < 1e-3
         and ds[30]["face_p95"] == 0.8, f"{ds[30]['meter_boxes']} {ds[30]['face_rgb']}")
    at.gan_chu_the(ds, dict(cfg, chu_the_chinh=False))
    ktra("gọi lại (tắt) -> trả nguyên số gốc",
         all(r["meter_boxes"] == g["meter_boxes"] and r["face_rgb"] == g["face_rgb"] and not r.get("chu_the")
             for r, g in zip(ds, goc)))

    print("3. do_mat_chu_the")
    ds = buoi()
    at.gan_chu_the(ds, cfg)
    n = at.do_mat_chu_the(ds, cfg)
    ktra("phép đo mặt = mặt chủ thể (ảnh A + B: −1.2, không phải trung bình −0.9)",
         n == 100 and abs(ds[30]["metered_face_ev"] + 1.2) < 1e-6 and "chu-the-chinh" in ds[30]["notes"]
         and abs(ds[30]["metered_face_ev_tho"] + 0.9) < 1e-6, f"{n} · {ds[30]['metered_face_ev']}")
    at._tra_mat_goc(ds)                                                      # noqa: SLF001
    ktra("_tra_mat_goc trả phép đo cũ", abs(ds[30]["metered_face_ev"] + 0.9) < 1e-6)
    ktra("_mat_tho (bù cụm) dùng mặt chủ thể", abs(at._mat_tho(ds[30]) + 1.2) < 1e-6)  # noqa: SLF001

    print("4. buổi ít ảnh có mặt")
    it = buoi()[:12]
    ktra("< chu_the_min_buoi ảnh có mặt -> tắt", at.gan_chu_the(it, cfg) == {} and not any(r.get("chu_the") for r in it))
    print(f"\n{len(LOI)} LOI" if LOI else "\nTAT CA DAT")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
