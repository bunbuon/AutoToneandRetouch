#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Công cụ học màu Lightroom (hoc_mau_lr.py — 14/10) với "plugin" + "Lightroom" GIẢ.

Plugin giả trả bản xuất thông số và DỰNG mọi biến thể bằng mo_phong_lr (hành vi biết
trước); mặt nạ da giả theo hình (test_curve_da). Canh LUỒNG của công cụ: từ chối khi
plugin cũ / buổi chưa phân tích, chọn ảnh cùng máy, gửi đủ biến thể, học + kiểm định,
lưu mô hình ĐẠT theo khoá máy__profile__PV, dọn ảnh dựng, học lại từ mẫu đã lưu.

Chạy:  python test_hoc_mau_lr.py
"""
from __future__ import annotations

import json
import os
import pickle
import sys
import tempfile
import threading
import time
import zlib
from datetime import timedelta
from pathlib import Path

import numpy as np

GOC = Path(__file__).resolve().parent
sys.path.insert(0, str(GOC))
LOI: list = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


def main() -> int:
    tam = Path(tempfile.mkdtemp(prefix="hoc_mau_lr_"))
    os.environ["AUTOTONE_DATA"] = str(tam / "du_lieu")
    os.environ["AUTOTONE_CATALOG_LR"] = "0"
    os.environ["AUTOTONE_LR_MODULES"] = str(tam / "Modules")
    import autotone as at
    import hoc_mau_lr as H
    import mo_hinh_lr as mh
    import mo_phong_lr as sim
    import test_curve_da as T
    from PIL import Image

    T.cai_gia()
    jobs = tam / "jobs"
    jobs.mkdir()
    buoi = tam / "Buoi"
    buoi.mkdir()
    N = 6
    t0 = T.anh("x")["dt_obj"]
    goc_anh = mh.srgb_lin(T.canh())                       # cảnh tuyến tính (H, W, 3)
    items, cat, canh = [], {}, {}
    rng = np.random.default_rng(3)
    for i in range(N + 2):
        p = buoi / f"DSC{i:04d}.ARW"
        p.write_bytes(b"")
        r = dict(T.anh(f"DSC{i:04d}", dt=t0 + timedelta(minutes=5 * i)), path=str(p),
                 model="SIM" if i < N + 1 else "MAY_KHAC", dt=str(t0 + timedelta(minutes=5 * i)))
        items.append(r)
        K = round(float(rng.uniform(3800, 6200)))
        cat[at.khoa_duong_dan(str(p))] = {
            "WhiteBalance": "Custom", "Temperature": str(K), "Tint": str(int(rng.integers(-5, 10))),
            "AsShotTemperature": str(K), "AsShotTint": "3", "Exposure2012": f"{rng.uniform(-0.4, 0.4):.2f}",
            "Highlights2012": "0", "Shadows2012": "0", "ToneCurvePV2012": "0,0,64,60,128,130,192,196,255,255",
            "CameraProfile": "Adobe Standard", "ProcessVersion": "15.4"}
        canh[str(p).replace("\\", "/").lower()] = goc_anh * float(rng.uniform(0.6, 1.1))
    f_kq = Path(at.file_ket_qua_do(buoi))
    f_kq.parent.mkdir(parents=True, exist_ok=True)
    f_kq.write_bytes(zlib.compress(pickle.dumps({"items": items}, protocol=4)))

    def plugin(dung: threading.Event, nk: list):
        while not dung.is_set():
            rx = jobs / "request_export.txt"
            if rx.exists():
                rx.unlink()
                cot = ["WhiteBalance", "Temperature", "Tint", "AsShotTemperature", "AsShotTint",
                       "Exposure2012", "Highlights2012", "Shadows2012", "ToneCurvePV2012",
                       "CameraProfile", "ProcessVersion"]
                dong = ["path\t" + "\t".join(cot)]
                for r in items:
                    c = cat[at.khoa_duong_dan(r["path"])]
                    dong.append(r["path"] + "\t" + "\t".join(c.get(k, "") for k in cot))
                time.sleep(1.1)
                (jobs / f"export_{time.strftime('%Y%m%d_%H%M%S')}.tsv").write_text(
                    "\n".join(dong) + "\n", encoding="utf-8")
            rq = jobs / "request_hocmau.txt"
            if not rq.exists():
                time.sleep(0.05)
                continue
            req = json.loads(rq.read_text(encoding="utf-8"))
            rq.unlink()
            nk.append(req)
            dest = Path(req["dest"])
            bang = ["bien\tpath\tjpg"]
            for a in req["anh"]:
                c = cat[at.khoa_duong_dan(a["path"])]
                sc = canh[a["path"].replace("\\", "/").lower()]
                Hh, Ww = sc.shape[:2]
                for b in req["bien"] + [{"ten": "sau", "goc": True}]:
                    st = mh.thong_so_bien(c, b, a["path"], set())
                    px = sim.dung(sc.reshape(-1, 3), st).reshape(Hh, Ww, 3)
                    d = dest / b["ten"]
                    d.mkdir(parents=True, exist_ok=True)
                    f = d / (Path(a["path"]).stem.lower() + ".jpg")
                    Image.fromarray((px * 255).round().astype(np.uint8)).save(f, "PNG")
                    bang.append(f"{b['ten']}\t{a['path']}\t{f}")
            n = len(req["anh"]) * (len(req["bien"]) + 1)
            (jobs / "hocmau_anh.tsv").write_text("\n".join(bang) + "\n", encoding="utf-8")
            (jobs / "hocmau_tiendo.txt").write_text(
                f"id={req['id']}\ntrang_thai=xong\nxong={n}\ntong={n}\nanh_xong={len(req['anh'])}\n"
                f"anh_tong={len(req['anh'])}\nthieu=0\nbo=0\nlech=0\n", encoding="utf-8")

    print("1. từ chối")
    sys.argv = ["hoc_mau_lr.py", str(buoi), "--jobs", str(jobs)]
    H.DONG.clear()
    ktra("chưa có nhịp plugin -> mã 2", H.main() == 2 and any("chưa chạy" in d for d in H.DONG))
    (jobs / at.NHIP_PLUGIN).write_text("vong=1\nkha_nang=curve1,xem1\n", encoding="utf-8")
    H.DONG.clear()
    ktra("plugin thiếu hocmau1 -> mã 2, nói chép plugin mới", H.main() == 2
         and any("hocmau1" in d for d in H.DONG))
    (jobs / at.NHIP_PLUGIN).write_text("vong=1\nkha_nang=curve1,xem1,hocmau1,truoc1\n", encoding="utf-8")
    sys.argv = ["hoc_mau_lr.py", str(tam / "ChuaPhanTich"), "--jobs", str(jobs)]
    (tam / "ChuaPhanTich").mkdir()
    H.DONG.clear()
    ktra("buổi chưa phân tích -> mã 2", H.main() == 2 and any("chưa phân tích" in d for d in H.DONG))

    print("2. học trên Lightroom giả")
    dung, nk = threading.Event(), []
    th = threading.Thread(target=plugin, args=(dung, nk), daemon=True)
    th.start()
    sys.argv = ["hoc_mau_lr.py", str(buoi), "--jobs", str(jobs), "--n", str(N)]
    H.DONG.clear()
    try:
        ma = H.main()
    finally:
        dung.set()
        th.join(5)
    bc = "\n".join(H.DONG)
    ktra("chạy xong, mô hình ĐẠT (mã 0)", ma == 0, bc[-600:])
    ktra("chỉ ảnh cùng máy SIM (bỏ máy khác + ảnh 1★ không có)", nk and all(
        "DSC0007" not in a["path"] for a in nk[0]["anh"]) and len(nk[0]["anh"]) == N, str(len(nk[0]["anh"]) if nk else 0))
    ktra("đủ 28 biến thể, nen = WB Custom mỗi ảnh", nk and len(nk[0]["bien"]) == 28
         and all(a["nen"]["WhiteBalance"] == "Custom" for a in nk[0]["anh"]))
    khoa = mh.khoa_cua("SIM", "Adobe Standard", "15.4")
    m = mh.nap(khoa)
    ktra("mô hình lưu theo khoá SIM__Adobe_Standard__15.4, ĐẠT", m is not None and m.dat, khoa)
    ktra("ảnh dựng đã dọn, mẫu .npz giữ lại", not any((Path(os.environ["AUTOTONE_DATA"]) / "hoc_mau").glob("*"))
         and (mh.thu_muc() / f"{khoa}_mau.npz").is_file())
    ktra("báo cáo có bảng biến thể + tổ hợp", "tohop1" in bc and "miền curve" in bc and "ĐẠT" in bc)

    print("3. học lại từ mẫu đã lưu")
    sys.argv = ["hoc_mau_lr.py", "--phan_tich", khoa]
    H.DONG.clear()
    ktra("--phan_tich: học lại không cần Lightroom, vẫn ĐẠT", H.main() == 0 and mh.nap(khoa).dat)

    print("4. chọn máy: --may / --tat_ca")
    k_khac = mh.khoa_cua("MAY_KHAC", "Adobe Standard", "15.4")
    ktra("cac_khoa: đủ máy của buổi, đông ảnh trước",
         [k for k, _n in H.cac_khoa(items, cat)] == [khoa, k_khac], str(H.cac_khoa(items, cat)))
    ds_k, k2 = H.chon_anh_hoc(items, cat, 20, may="khac")
    ktra("--may khac: chỉ ảnh máy MAY_KHAC", k2 == k_khac and len(ds_k) == 1, f"{k2} {len(ds_k)}")
    ds_k, k2 = H.chon_anh_hoc(items, cat, 20, khoa=khoa)
    ktra("khoa= cho trước: đúng nhóm đó", k2 == khoa and len(ds_k) == N + 1, f"{k2} {len(ds_k)}")
    dung, nk = threading.Event(), []
    th = threading.Thread(target=plugin, args=(dung, nk), daemon=True)
    th.start()
    nhip = "vong=1\nkha_nang=curve1,xem1,hocmau1,truoc1\n"
    (jobs / at.NHIP_PLUGIN).write_text(nhip, encoding="utf-8")          # nhịp mới (lượt học trên lâu)
    sys.argv = ["hoc_mau_lr.py", str(buoi), "--jobs", str(jobs), "--tat_ca"]
    H.DONG.clear()
    try:
        ma = H.main()
    finally:
        dung.set()
        th.join(5)
    bc = "\n".join(H.DONG)
    ktra("--tat_ca: máy đã có mô hình ĐẠT -> bỏ qua, không gửi Lightroom; máy < 6 ảnh không học",
         ma == 0 and not nk and "bỏ qua" in bc and k_khac not in bc.split("TỔNG KẾT")[-1], bc[-300:])
    dung, nk = threading.Event(), []
    th = threading.Thread(target=plugin, args=(dung, nk), daemon=True)
    th.start()
    (jobs / at.NHIP_PLUGIN).write_text(nhip, encoding="utf-8")
    sys.argv = ["hoc_mau_lr.py", str(buoi), "--jobs", str(jobs), "--tat_ca", "--lai", "--n", str(N)]
    H.DONG.clear()
    try:
        ma = H.main()
    finally:
        dung.set()
        th.join(5)
    bc = "\n".join(H.DONG)
    ktra("--tat_ca --lai: học lại máy đó, ĐẠT, có tổng kết", ma == 0 and len(nk) == 1
         and "TỔNG KẾT" in bc and f"{khoa}: ĐẠT" in bc, bc[-300:])
    for f in (GOC / "ket_qua_kiem").glob("hoc_mau_*.txt"):
        if f.stat().st_mtime > time.time() - 600:
            f.unlink()
    print(f"\n{len(LOI)} LOI" if LOI else "\nTAT CA DAT")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
