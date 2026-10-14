#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CỔNG chuỗi màu da MỘT LƯỢT trên một buổi THẬT (14/10) — KIEM_MOT_LUOT.bat.

Chạy SAU khi đã Xử lý ảnh một buổi với chuỗi một lượt bật (KIEM_TOAN_BO mục 12): app lưu
dự đoán màu da / vùng trắng của từng ảnh (mo_hinh_lr/du_doan_<buổi>.json). Công cụ này
lấy preview Lightroom THẬT của mọi ảnh đó (cache Lightroom nếu còn mới, thiếu thì nhờ
plugin dựng), đo da, so với dự đoán.

ĐẠT (mới bật mặc định): lệch dự đoán trung vị ≤ 1.5° hue và ≤ 5% độ đậm, VÀ ≥ 85% ảnh
nằm trong vùng ổn của đích da sau một lượt (ảnh lượt 2 đã sửa thêm tính riêng).

Chạy:  python kiem_mot_luot.py <thư mục buổi> [--jobs <thư mục jobs>]
Kết quả: ket_qua_kiem/mot_luot_<buổi>_<giờ>.txt — gửi cho Claude.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

GOC = Path(__file__).resolve().parent
sys.path.insert(0, str(GOC))

for _l in (sys.stdout, sys.stderr):
    try:
        _l.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                        # noqa: BLE001
        pass

DONG: list = []
NGUONG_H, NGUONG_Q, NGUONG_ON = 1.5, 0.05, 0.85


def noi(s: str = "") -> None:
    print(s, flush=True)
    DONG.append(s)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("thu_muc")
    ap.add_argument("--jobs", default=None)
    a = ap.parse_args()
    import numpy as np
    import autotone as at
    import do_truoc
    import hoc_mau_lr as hm
    import kiem_preview_lr as kp
    import mau_mot_luot as ml

    folder = Path(a.thu_muc)
    jobs = kp.tim_jobs(a.jobs)
    noi(f"CỔNG CHUỖI MỘT LƯỢT — {datetime.now():%d/%m/%Y %H:%M}\nThư mục buổi: {folder}")
    f = ml.file_du_doan(folder)
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        noi(f"[!] Chưa có dự đoán của buổi này ({f.name}) — Xử lý ảnh buổi này với chuỗi một lượt "
            "bật (KIEM_TOAN_BO mục 12) trước.")
        return 2
    du = {at.khoa_duong_dan(p): v for p, v in (d.get("anh") or {}).items()}
    luot2 = {at.khoa_duong_dan(p) for p in d.get("luot2") or []}
    cfg = dict(at.DEFAULTS, **{k: v for k, v in (d.get("cfg") or {}).items() if v is not None})
    items = [r for r in hm.nap_phan_tich(folder)
             if at.khoa_duong_dan(r.get("lr_path") or r["path"]) in du]
    noi(f"Dự đoán lúc {d.get('luc')}: {len(du)} ảnh · có kết quả phân tích {len(items)} · lượt 2 "
        f"đã sửa thêm {len(luot2)}")
    if not items:
        noi("[!] Không ghép được ảnh nào với kết quả phân tích của buổi.")
        return 2
    for r in items:
        r["du_doan_lr"] = du[at.khoa_duong_dan(r.get("lr_path") or r["path"])]
    t0 = time.monotonic()
    noi("Lấy preview Lightroom hiện tại + đo da…")
    kq = do_truoc.chay(folder, items, cfg, job_dir=jobs,
                       bao=lambda x, t, c: print(f"\r  {c}      ", end="", flush=True))
    print()
    noi(f"  đo {kq.get('do')}/{kq.get('tong')} ảnh · cache {kq.get('cache')} · plugin {kq.get('plugin')} · "
        f"{time.monotonic() - t0:.0f} giây" + (f" · {kq['ly_do']}" if kq.get("ly_do") else ""))
    mot, hai = [], []
    for r in items:
        l = ml.lech_soat(r, r.get("lr_truoc"), cfg)
        if l is None:
            continue
        (hai if at.khoa_duong_dan(r.get("lr_path") or r["path"]) in luot2 else mot).append((r, l))
    if not mot:
        noi("[!] Không đo được ảnh nào.")
        return 2

    def tom(ds, ten):
        dh = np.array([l["dh"] for _r, l in ds])
        dq = np.array([l["dq"] for _r, l in ds])
        on = np.mean([not l["ngoai_on"] for _r, l in ds])
        noi(f"  {ten}: {len(ds)} ảnh · lệch dự đoán hue trung vị {np.median(dh):.2f}° (p90 {np.percentile(dh, 90):.2f}°)"
            f" · độ đậm {np.median(dq) * 100:.1f}% (p90 {np.percentile(dq, 90) * 100:.1f}%) · "
            f"trong vùng ổn của đích {on * 100:.0f}%")
        return float(np.median(dh)), float(np.median(dq)), float(on)
    noi("\nKết quả:")
    h, q, on = tom(mot, "chỉ một lượt")
    if hai:
        tom(hai, "đã qua lượt 2")
    theo_canh: dict = {}
    for r, l in mot:
        theo_canh.setdefault(r.get("scene"), []).append(l)
    noi("  theo cảnh (cảnh: n · hue trung vị · % trong vùng ổn):")
    for c, ls in sorted(theo_canh.items(), key=lambda x: str(x[0])):
        noi(f"    {c}: {len(ls)} · {np.median([x['dh'] for x in ls]):.2f}° · "
            f"{np.mean([not x['ngoai_on'] for x in ls]) * 100:.0f}%")
    dat = h <= NGUONG_H and q <= NGUONG_Q and on >= NGUONG_ON
    noi(f"\n{'ĐẠT' if dat else 'CHƯA ĐẠT'}: cần hue ≤ {NGUONG_H}°, độ đậm ≤ {NGUONG_Q * 100:.0f}%, "
        f"≥ {NGUONG_ON * 100:.0f}% ảnh trong vùng ổn.")
    ra = GOC / "ket_qua_kiem"
    ra.mkdir(exist_ok=True)
    fo = ra / f"mot_luot_{at.ten_job(folder.name)}_{datetime.now():%Y%m%d_%H%M%S}.txt"
    fo.write_text("\n".join(DONG) + "\n", encoding="utf-8")
    noi(f"\nĐã lưu: {fo}\nGửi file này cho Claude.")
    return 0 if dat else 1


if __name__ == "__main__":
    sys.exit(main())
