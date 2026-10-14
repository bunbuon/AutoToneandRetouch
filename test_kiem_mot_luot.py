#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cổng chuỗi một lượt trên buổi thật (kiem_mot_luot.py — 14/10) với plugin GIẢ.

Mục kiểm
    1. chưa có dự đoán của buổi -> mã 2, nói chạy Xử lý ảnh với chuỗi một lượt
    2. dự đoán khớp ảnh Lightroom (giả) -> ĐẠT (mã 0), báo cáo lưu ra ket_qua_kiem
    3. dự đoán lệch 5° -> CHƯA ĐẠT (mã 1); ảnh lượt 2 đã sửa tính riêng

Chạy:  python test_kiem_mot_luot.py
"""
from __future__ import annotations

import os
import pickle
import sys
import tempfile
import threading
import time
import zlib
from datetime import timedelta
from pathlib import Path

GOC = Path(__file__).resolve().parent
sys.path.insert(0, str(GOC))
LOI: list = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


def main() -> int:
    tam = Path(tempfile.mkdtemp(prefix="kiem_mot_luot_"))
    os.environ["AUTOTONE_DATA"] = str(tam / "du_lieu")
    os.environ["AUTOTONE_CATALOG_LR"] = "0"
    os.environ["AUTOTONE_LR_MODULES"] = str(tam / "Modules")
    import autotone as at
    import curve_da as cd
    import kiem_mot_luot as K
    import mau_mot_luot as ml
    import test_curve_da as T
    from PIL import Image

    T.cai_gia()
    jobs = tam / "jobs"
    jobs.mkdir()
    (jobs / at.NHIP_PLUGIN).write_text("vong=1\nkha_nang=curve1,xem1,truoc1\n", encoding="utf-8")
    buoi = tam / "Buoi"
    buoi.mkdir()
    t0 = T.anh("x")["dt_obj"]
    items = [dict(T.anh(f"A{i}", dt=t0 + timedelta(minutes=5 * i)), path=str(buoi / f"A{i}.ARW"))
             for i in range(5)]
    f_kq = Path(at.file_ket_qua_do(buoi))
    f_kq.parent.mkdir(parents=True, exist_ok=True)
    f_kq.write_bytes(zlib.compress(pickle.dumps({"items": items}, protocol=4)))
    anh = T.u8(T.canh())
    cfg = dict(at.DEFAULTS, mau_da_dich={"ten": "m", "trong": [200, 150, 140]})

    def plugin(dung):
        while not dung.is_set():
            rq = jobs / "request_do_truoc.txt"
            if not rq.exists():
                time.sleep(0.05)
                continue
            dong = rq.read_text(encoding="utf-8").splitlines()
            rq.unlink()
            o = dict(x.split("=", 1) for x in dong[1:] if "=" in x and not x.startswith("anh="))
            ds = [x.split("=", 1)[1] for x in dong[1:] if x.startswith("anh=")]
            cap = []
            for p in ds:
                f = Path(o["dest"]) / (Path(p).stem + ".jpg")
                Image.fromarray(anh).save(f, "PNG")
                cap.append(f"{p}\t{f}")
            (jobs / "do_truoc_anh.tsv").write_text("path\tjpg\n" + "\n".join(cap) + "\n", encoding="utf-8")
            (jobs / "do_truoc_tiendo.txt").write_text(f"trang_thai=xong\nxong={len(ds)}\ntong={len(ds)}\n"
                                                      f"ma={o['ma']}\ncach=preview\n", encoding="utf-8")

    def chay():
        dung = threading.Event()
        th = threading.Thread(target=plugin, args=(dung,), daemon=True)
        th.start()
        K.DONG.clear()
        sys.argv = ["kiem_mot_luot.py", str(buoi), "--jobs", str(jobs)]
        try:
            return K.main()
        finally:
            dung.set()
            th.join(2)

    print("1. chưa có dự đoán")
    ktra("mã 2, nói chạy Xử lý ảnh với chuỗi một lượt", chay() == 2 and any("mục 12" in d for d in K.DONG))

    print("2. dự đoán khớp")
    p = tam / "do.png"
    Image.fromarray(anh).save(p)
    do = cd.do_anh(items[0], p, cfg)
    h, q = cd.hue_q(cd.thong_ke(do["da_cu"], do["mien"]))
    for r in items:
        r["du_doan_lr"] = {"h": h, "q": q, "L": 0.7, "kieu": "cu", "trung_ab": None, "khoa": "k",
                           "ngoai_pham_vi": []}
    #  đích = chính da ảnh -> mọi ảnh trong vùng ổn
    import curve_lr as cl
    rgb = (cl.tuyen_tinh_srgb(cl.mien_sang_tuyen_tinh(do["da_cu"], do["mien"]).mean(axis=0)) * 255).round()
    cfg["mau_da_dich"] = {"ten": "m", "trong": [float(x) for x in rgb]}
    ml.luu_du_doan(items, buoi, cfg)
    ma = chay()
    ktra("ĐẠT (mã 0), báo cáo lưu ra ket_qua_kiem", ma == 0 and any("ĐẠT" in d for d in K.DONG)
         and any("Đã lưu" in d for d in K.DONG), "\n".join(K.DONG[-8:]))

    print("3. dự đoán lệch")
    for r in items:
        r["du_doan_lr"] = dict(r["du_doan_lr"], h=h + 5.0)
    cfg["mau_da_dich"] = {"ten": "m", "trong": [200, 140, 160]}       # đích xa -> ngoài vùng ổn
    ml.luu_du_doan(items, buoi, cfg)
    ml.danh_dau_luot2(buoi, items[:1])
    ma = chay()
    ktra("CHƯA ĐẠT (mã 1); ảnh lượt 2 tính riêng", ma == 1 and any("CHƯA ĐẠT" in d for d in K.DONG)
         and any("đã qua lượt 2: 1 ảnh" in d for d in K.DONG), "\n".join(K.DONG[-8:]))
    for f in (GOC / "ket_qua_kiem").glob("mot_luot_*.txt"):
        if f.stat().st_mtime > time.time() - 300:
            f.unlink()
    print(f"\n{len(LOI)} LOI" if LOI else "\nTAT CA DAT")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
