#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kiem_nut_catalog.py — Bản xuất catalog sau khi phân tích (8/10).

    python kiem_nut_catalog.py

User 8/10: "Phần thông báo này cần ẩn đi [Bản xuất catalog … cũ hơn lần tool
ghi …]. Hiện tại đang load lại catalog sau một khoảng thời gian. Khi đã bấm phân
tích thì chỉ cần thêm nút load lại Catalog mới hoặc xoá Catalog cũ."

Kiểm, với thư mục job giả (không cần Lightroom):
    1. bản xuất cũ hơn lần ghi -> dải cảnh báo trên cùng KHÔNG nói chuyện đó
    2. chưa phân tích: không có nút catalog; đã phân tích: có hai nút
    3. đã phân tích: bản xuất mới trên đĩa KHÔNG tự thay bản đang dùng
       (refresh_plan / nhịp 3 giây không đọc lại)
    4. “Nạp lại catalog” gửi yêu cầu xuất cho Lightroom (request_export.txt)
    5. “Xoá catalog cũ” xoá bản xuất của buổi này (không đụng buổi khác) và gửi
       yêu cầu xuất bản mới
ĐẠT / HỎNG ở cuối, mã thoát 0 / 1.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
LOI: list = []


def ktra(ten, ok, chi_tiet=""):
    print(f"  [{'DAT ' if ok else 'HONG'}] {ten}  {chi_tiet}")
    if not ok:
        LOI.append(ten)


def ban_xuat(d: Path, ten: str, thu_muc: Path, anh: list, mtime: float) -> Path:
    """export_*.tsv tối thiểu: dòng đầu là tiêu đề, cột đầu là đường dẫn ảnh."""
    p = d / ten
    dong = ["path\texposure"] + [f"{thu_muc / a}\t0" for a in anh]
    p.write_text("\n".join(dong) + "\n", encoding="utf-8")
    os.utime(p, (mtime, mtime))
    return p


def main() -> int:
    td = Path(tempfile.mkdtemp(prefix="kiem_nut_catalog_"))
    os.environ["AUTOTONE_DATA"] = str(td / "du_lieu")
    (td / "du_lieu").mkdir()
    import autotone as at
    import giao_dien as gd
    import autotone_gui as ag
    from tkinter import messagebox
    messagebox.askokcancel = lambda *a, **k: True
    for t in ("showinfo", "showwarning", "showerror"):
        setattr(messagebox, t, lambda *a, **k: "ok")

    jobs = td / "jobs"
    jobs.mkdir()
    at.LR_JOB_DIR = jobs
    buoi = td / "Kyyeu"
    buoi.mkdir()
    khac = td / "BuoiKhac"
    khac.mkdir()
    bay_gio = time.time()
    bx_cu = ban_xuat(jobs, "export_20261008_001500.tsv", buoi, ["a.NEF", "b.NEF"],
                     bay_gio - 600)
    bx_khac = ban_xuat(jobs, "export_20261008_001000.tsv", khac, ["x.NEF"],
                       bay_gio - 900)
    # lan ghi SAU ban xuat -> ban xuat "cu hon lan ghi"
    done = jobs / f"apply_20261008_001540_{at.ten_job(buoi.name)}.done"
    done.write_text("x\n", encoding="utf-8")
    os.utime(done, (bay_gio - 300, bay_gio - 300))
    cu, _t1, _t2 = at.ban_xuat_cu_hon_lan_ghi(buoi)

    root = tk.Tk()
    root.geometry("1500x900")
    gd.dat_theme(root)
    app = ag.App(root)
    app.grid(row=0, column=0, sticky="nsew")
    app._khoa_chan = lambda: False
    app.folder = lambda: buoi
    app.source_value = lambda: "catalog"

    def chay(n=3):
        for _ in range(n):
            root.update_idletasks()
            root.update()

    chay()
    app._canh_bao_im_lang(buoi)
    chay()
    ktra("bản xuất cũ hơn lần ghi: dải cảnh báo trên cùng không nhắc tới",
         cu and "cũ hơn lần" not in app.lbl_im_lang.cget("text")
         and not app.dai_canh.winfo_ismapped(),
         f"cũ={cu} · dải: “{app.lbl_im_lang.cget('text')[:50]}”")

    # chua phan tich
    app.items = []
    app._nut_catalog()
    chay()
    ktra("chưa phân tích: không có nút catalog",
         not app.btn_nap_catalog.winfo_manager() and not app.btn_xoa_catalog.winfo_manager())

    # "da phan tich": doc ban xuat lan dau, roi khoa
    app._doc_xuat()
    dau_truoc = app._dau_xuat
    app.items = [{"path": str(buoi / "a.NEF")}]
    app._xuat_khoa = True
    app._nut_catalog()
    chay()
    ktra("đã phân tích: có nút “Nạp lại catalog” + “Xoá catalog cũ”",
         bool(app.btn_nap_catalog.winfo_manager()) and bool(app.btn_xoa_catalog.winfo_manager()))

    # ban xuat MOI xuat hien tren dia -> khong tu thay
    ban_xuat(jobs, "export_20261008_002000.tsv", buoi, ["a.NEF", "b.NEF", "c.NEF"],
             bay_gio - 60)
    app.pairs = [(str(buoi / "a.NEF"), None)]
    app._soi_xuat()
    ktra("đã phân tích: bản xuất mới trên đĩa KHÔNG tự thay bản đang dùng",
         app._dau_xuat == dau_truoc, str(app._dau_xuat[0] if app._dau_xuat else None))

    # Nap lai -> gui yeu cau xuat
    req = jobs / "request_export.txt"
    if req.exists():
        req.unlink()
    app.do_nap_lai_catalog()
    chay()
    ktra("“Nạp lại catalog” nhờ Lightroom xuất lại (request_export.txt)",
         req.is_file() and str(buoi.resolve()) in req.read_text(encoding="utf-8"),
         req.read_text(encoding="utf-8").strip()[:60] if req.is_file() else "không có")

    # Xoa catalog cu (bang tinh lai: ghi nhan thay vi at.plan tren muc gia)
    req.unlink(missing_ok=True)
    tinh_lai = []
    app.refresh_plan = lambda: tinh_lai.append(dict(app.export))
    app.do_xoa_catalog_cu()
    chay()
    con_buoi = [p.name for p in jobs.glob("export_*.tsv")
                if p.name in (bx_cu.name, "export_20261008_002000.tsv")]
    ktra("“Xoá catalog cũ” xoá MỌI bản xuất của buổi này",
         not con_buoi and not app.export, f"còn {con_buoi}")
    ktra("…không đụng bản xuất của buổi khác", bx_khac.is_file())
    ktra("…bảng tính lại ngay với bản xuất rỗng (ảnh chưa ghi được cho tới bản mới)",
         tinh_lai and tinh_lai[0] == {}, f"{len(tinh_lai)} lần tính lại")
    ktra("…và nhờ Lightroom xuất bản mới ngay", req.is_file())
    root.destroy()
    print("TAT CA DAT" if not LOI else f"{len(LOI)} LOI")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
