#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kiem_tien_do_retouch.py — Tiến độ + số đếm của một lượt Retouch THẬT (8/10).

    python kiem_tien_do_retouch.py <thư mục ảnh jpg> [số ảnh, mặc định 24]

User 8/10: "Bên Retouch không hiển thị thanh đã ghi xong — cần chuyển thành thanh
Progress xử lý ảnh Retouch. Retouch xong vẫn báo 0/13 ảnh."

Bài này dựng App thật + màn Retouch, chép N ảnh vào thư mục tạm, bật GHI ĐÈ, chọn
hết, bấm Chạy (engine thường trú + tool thật) rồi kiểm (mặc định 24 ảnh — mẻ
6 ảnh xong trong ~3 s, tool ghi dồn cuối nên không có số giữa chừng để thấy):
    1. ở mô-đun Retouch, thanh "Đã ghi xong …" của Cân tone ẨN
    2. đang chạy: thanh tiến độ ở đáy cửa sổ HIỆN, chữ "Đang retouch x/N ảnh"
    3. xong: "Retouch xong {N}/{N} ảnh" (không phải 0/{N}) ở thanh trạng thái + đáy
    4. sang Cân tone: thanh retouch ẩn, thanh Cân tone về chỗ cũ
ĐẠT / HỎNG ở cuối, mã thoát 0 / 1.
"""
from __future__ import annotations

import os
import shutil
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


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    N = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    anh = sorted(p for p in Path(sys.argv[1]).iterdir()
                 if p.suffix.lower() in (".jpg", ".jpeg"))[:N]
    if len(anh) < N:
        print(f"cần ít nhất {N} ảnh jpg")
        return 2
    td = Path(tempfile.mkdtemp(prefix="kiem_tien_do_"))
    (td / "du_lieu").mkdir()
    os.environ["AUTOTONE_DATA"] = str(td / "du_lieu")
    k = Path(os.environ.get("LOCALAPPDATA", "")) / "AutoTone" / "khoa.json"
    if k.is_file():
        shutil.copy2(k, td / "du_lieu")
    vao = td / "vao"
    vao.mkdir()
    for p in anh:
        shutil.copy2(p, vao / p.name)

    import giao_dien as gd
    import autotone_gui as ag
    import retouch_may as rm
    from tkinter import messagebox
    for ten in ("showinfo", "showwarning", "showerror"):
        setattr(messagebox, ten, lambda *a, **k: "ok")
    for ten in ("askokcancel", "askyesno"):
        setattr(messagebox, ten, lambda *a, **k: True)
    rm.hoi_nut = lambda *_a, **_k: "chung"

    root = tk.Tk()
    root.geometry("1600x900")
    gd.dat_theme(root)
    app = ag.App(root)
    app.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    app._khoa_chan = lambda: False

    def chay(n=3, ngu=0.05):
        for _ in range(n):
            root.update_idletasks()
            root.update()
            time.sleep(ngu)

    # thanh Can tone co chu "Da ghi xong" (nhu lan ghi truoc) — sang Retouch phai an
    app.lbl_tien3.configure(text="Đã ghi xong 738/738")
    app._hien_tien_do()
    chay()
    app._chon_khau("retouch")
    chay(10)
    w = app._retouch_win
    ktra("ở Retouch: thanh “Đã ghi xong” của Cân tone ẩn",
         not app.pb.winfo_ismapped() and not app.lbl_tien3.winfo_ismapped())

    w.v_vao.set(str(vao))
    w.v_ghide.set(True)
    w._doi_ghide()
    for _ in range(40):
        chay(2)
        if w._ds_luoi and w._anh_dang:
            break
    ten0 = next(iter(w.v_muc))
    w.v_muc[ten0].set(60)
    chay(4)
    w.luoi.chon_het()
    chay(4)
    #  kéo thanh = mức của ẢNH ĐANG XEM; Sync cho mọi tấm đã chọn (như người dùng)
    w._sync_chon()
    chay(4)
    # cho may xem truoc (engine) san sang de me chay trong engine nhu that
    het = time.time() + 120
    while time.time() < het and (w._may_xem is None or not w._may_xem.chay_duoc(0.1)):
        chay(2, 0.2)
    w.start()
    thay_chay, chu_chay = False, ""
    da_thay: set = set()
    het = time.time() + 300
    while time.time() < het and w.worker and w.worker.is_alive():
        chay(2, 0.1)
        if w.pb_tt is not None and w.pb_tt.winfo_ismapped():
            thay_chay = True
            _c = w.lbl_tt_chay.cget("text") or ""
            if _c.startswith("Đang retouch"):
                chu_chay = _c
            da_thay.add(int(float(w.pb_tt.cget("value"))))
    chay(20, 0.1)
    ktra("đang chạy: thanh tiến độ retouch hiện ở đáy cửa sổ",
         thay_chay and chu_chay.startswith("Đang retouch"), chu_chay[:70])
    ktra("đang chạy: thanh nhích TỪNG ẢNH (thấy số giữa chừng, không chỉ 0 rồi N)",
         any(0 < v < N for v in da_thay), f"số đã thấy: {sorted(da_thay)}")
    trang_thai = app.lbl_status.cget("text")
    day = w.lbl_tt_chay.cget("text") if w.lbl_tt_chay is not None else ""
    ktra(f"xong: thanh trạng thái báo ĐỦ {N}/{N} (không phải 0/{N})",
         f"{N}/{N}" in trang_thai and "ghi đè" in trang_thai, trang_thai[:80])
    ktra(f"xong: chữ ở đáy “Retouch xong {N}/{N} ảnh”, thanh đầy",
         day.startswith(f"Retouch xong {N}/{N}") and w.pb_tt.winfo_ismapped()
         and float(w.pb_tt.cget("value")) == float(w.pb_tt.cget("maximum")),
         f"{day} · {w.pb_tt.cget('value')}/{w.pb_tt.cget('maximum')}")
    app._chon_khau("phan_tich")
    chay(4)
    ktra("sang Cân tone: thanh retouch ẩn, thanh Cân tone về chỗ cũ",
         not w.pb_tt.winfo_ismapped() and app.lbl_tien3.winfo_ismapped()
         and app.pb.winfo_ismapped())
    try:
        if w._may_xem is not None:
            w._may_xem.dong()
    except Exception:                                        # noqa: BLE001
        pass
    root.destroy()
    shutil.rmtree(td, ignore_errors=True)
    print("TAT CA DAT" if not LOI else f"{len(LOI)} LOI")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
