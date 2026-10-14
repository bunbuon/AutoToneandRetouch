#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Công cụ đo preview Lightroom (kiem_preview_lr.py — 14/10) với "plugin" giả.

Công cụ chạy trên Lightroom THẬT ở máy user; bài này chỉ canh phần logic: tìm thư mục
jobs, từ chối khi plugin không chạy / bản cũ, gửi đủ năm lượt (A / B / C / A' / C'), đo
da song song ở lượt A, soát preview với ảnh xuất, ghi báo cáo, dọn thư mục tạm.

Chạy:  python test_kiem_preview_lr.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path

GOC = Path(__file__).resolve().parent
sys.path.insert(0, str(GOC))
LOI: list = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


def plugin_gia(jobs: Path, anh_mau: Path, dung: threading.Event, nhat_ky: list):
    """Nhận request_xem_lr.txt -> trả preview (ảnh mẫu) từng nhóm 4 + bảng soát."""
    import shutil
    while not dung.is_set():
        req = jobs / "request_xem_lr.txt"
        if not req.exists():
            time.sleep(0.05)
            continue
        dong = req.read_text(encoding="utf-8").splitlines()
        req.unlink()
        opts, anh, kiem = {}, [], []
        for d in dong[1:]:
            k, _, v = d.partition("=")
            if k == "anh":
                anh.append(v)
            elif k == "kiem_anh":
                kiem.append(v)
            elif k:
                opts[k] = v
        nhat_ky.append({"canh": opts.get("canh"), "n": len(anh), "kiem": len(kiem),
                        "chi_preview": opts.get("chi_preview")})
        dest = Path(opts["dest"])
        dest.mkdir(parents=True, exist_ok=True)
        if kiem:
            (dest / "_kiem").mkdir(exist_ok=True)
            rows = []
            for p in kiem:
                f = dest / "_kiem" / (Path(p).stem + ".jpg")
                shutil.copyfile(anh_mau, f)
                rows.append(f"{p}\t{f}")
            (jobs / "xem_lr_kiem.tsv").write_text("path\tjpg\n" + "\n".join(rows) + "\n",
                                                  encoding="utf-8")
        cap = []
        for i, p in enumerate(anh):
            f = dest / (Path(p).stem + ".jpg")
            shutil.copyfile(anh_mau, f)
            cap.append(f"{p}\t{f}")
            if True:                                  # từng ảnh một, có nhịp
                (jobs / "xem_lr_anh.tsv").write_text("path\tjpg\n" + "\n".join(cap) + "\n",
                                                     encoding="utf-8")
                xong = i + 1 == len(anh)
                (jobs / "xem_lr_tiendo.txt").write_text(
                    f"trang_thai={'xong' if xong else 'dang_chay'}\nxong={i + 1}\ntong={len(anh)}\n"
                    f"ma={opts['ma']}\ncach=preview\n"
                    + ("thong_bao=1 giay, 0.05 giay/anh\n" if xong else ""), encoding="utf-8")
                time.sleep(0.3)


def main() -> int:
    tam = Path(tempfile.mkdtemp(prefix="kiem_pv_lr_"))
    os.environ["AUTOTONE_DATA"] = str(tam / "du_lieu")
    os.environ["AUTOTONE_LR_MODULES"] = str(tam / "Modules")      # không có bản trong Modules
    import autotone as at
    import kiem_preview_lr as K
    import test_curve_da as T

    jobs = tam / "jobs"
    jobs.mkdir()
    buoi = tam / "Buoi"
    buoi.mkdir()
    for i in range(12):
        (buoi / f"DSC{i:04d}.ARW").write_bytes(b"")
    anh_mau = T.luu(T.canh(), "pv_mau")
    T.cai_gia()                          # bộ dò / phân vùng mặt giả -> đo tại chỗ (BoDo n=1)
    #  kết quả phân tích đã lưu của buổi: ảnh có mặt (khung đo trên ảnh mẫu)
    import pickle
    import zlib
    items = [dict(T.anh(f"DSC{i:04d}"), path=str(buoi / f"DSC{i:04d}.ARW"), dt=f"2026-10-14T10:00:{i:02d}")
             for i in range(12)]
    f_kq = Path(at.file_ket_qua_do(buoi))
    f_kq.parent.mkdir(parents=True, exist_ok=True)
    f_kq.write_bytes(zlib.compress(pickle.dumps({"items": items}, protocol=4)))

    print("1. tìm thư mục jobs / từ chối khi plugin không chạy")
    ktra("--jobs thắng", K.tim_jobs(str(jobs)) == jobs)
    ktra("không có bản trong Modules -> jobs của mã nguồn", K.tim_jobs(None) == Path(at.LR_JOB_DIR))
    K.DONG.clear()
    sys.argv = ["kiem_preview_lr.py", str(buoi), "--jobs", str(jobs), "--n", "12"]
    ktra("chưa có nhịp plugin -> mã 2, nói mở Lightroom", K.main() == 2
         and any("chưa chạy" in d for d in K.DONG), K.DONG[-1] if K.DONG else "")
    (jobs / at.NHIP_PLUGIN).write_text("vong=1\nkha_nang=curve1\n", encoding="utf-8")
    K.DONG.clear()
    ktra("plugin thiếu xem1 -> mã 2, nói cài lại", K.main() == 2
         and any("bản cũ" in d for d in K.DONG), K.DONG[-1] if K.DONG else "")

    print("2. đủ năm lượt với plugin giả")
    (jobs / at.NHIP_PLUGIN).write_text("vong=1\nkha_nang=curve1,sao1,xem1\n", encoding="utf-8")
    dung, nk = threading.Event(), []
    th = threading.Thread(target=plugin_gia, args=(jobs, anh_mau, dung, nk), daemon=True)
    th.start()
    K.DONG.clear()
    try:
        ma = K.main()
    finally:
        dung.set()
        th.join(2)
    ktra("chạy xong, mã 0", ma == 0, str(K.DONG[-3:]))
    ktra("năm yêu cầu: 1600 · 1600 · 1024 · 1600 · 1024, chỉ preview",
         [x["canh"] for x in nk] == ["1600", "1600", "1024", "1600", "1024"]
         and all(x["chi_preview"] == "1" for x in nk), str(nk))
    ktra("chỉ lượt A xin 3 ảnh soát", [x["kiem"] for x in nk] == [3, 0, 0, 0, 0], str(nk))
    bc = "\n".join(K.DONG)
    ktra("báo cáo có từng lượt + s/ảnh", all(t in bc for t in ("A  1600 lần đầu + đo da",
                                                              "B  1600 lần đầu", "C' 1024 lần sau"))
         and "s/ảnh" in bc, bc[:300])
    ktra("lượt A đo da song song đủ ảnh", "đo da 4 ảnh xong" in bc, bc[:600])
    ktra("soát 3 ảnh: preview == ảnh xuất -> 'khớp', hue +0.00°",
         bc.count("(khớp)") == 3 and "hue +0.00°" in bc, bc[bc.find("Soát"):][:400])
    ktra("báo cáo lưu ra ket_qua_kiem", any("Đã lưu:" in d for d in K.DONG))
    ktra("chọn ảnh từ kết quả phân tích (ảnh có mặt)", "có kết quả phân tích" in bc)
    ktra("thư mục tạm xem_lr_tam đã dọn",
         not any((Path(os.environ["AUTOTONE_DATA"]) / "xem_lr_tam").glob("*")))
    ktra("không cất gì vào kho preview của lưới (xem_lr)",
         not (Path(os.environ["AUTOTONE_DATA"]) / "xem_lr" / "chi_muc.json").exists())
    for f in (GOC / "ket_qua_kiem").glob("preview_lr_*.txt"):
        if f.stat().st_mtime > time.time() - 60:
            f.unlink()
    print(f"\n{len(LOI)} LOI" if LOI else "\nTAT CA DAT")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
