#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""retouch_chung.py — Bốn hàm nhỏ màn Retouch dùng chung (tách từ man_retouch, 7/10).

    _cung_thu_muc  hai đường dẫn có cùng một thư mục không
    _RE_TIEN_DO    dòng tiến độ của saytool "N/M x.xs/anh"
    _so_muc        giá trị thanh kéo -> float, có mặc định
    hoi_nut        hộp hỏi với nút mang tên riêng (Chung / Riêng…)

Là module LÁ (không import module app nào) để retouch_muc / retouch_may /
man_retouch cùng dùng mà không vòng. Bài kiểm vá hoi_nut thì vá ở module gọi
nó (retouch_may.hoi_nut — nơi start() tra tên).
"""

from __future__ import annotations
import re
import tkinter as tk
from tkinter import ttk

import giao_dien as gd


def _cung_thu_muc(a, b) -> bool:
    """Hai đường dẫn có trỏ cùng một thư mục không (Windows: không phân biệt
    hoa thường, \\ và / như nhau). So chuỗi thẳng thì "F:/Out" khác "F:\\out\\"
    và app sẽ dựng một cảnh báo lệch thư mục hoàn toàn vô nghĩa."""
    def chuan(x):
        return str(x or "").replace("/", "\\").rstrip("\\").lower()
    return bool(a) and bool(b) and chuan(a) == chuan(b)


#[[ "  10/2021  0.74s/anh  con lai ~24.8 phut" — dong tien do cua saytool.
#   Khop tu dau dong de khong an nham cac dong khac co dang so/so. ]]
_RE_TIEN_DO = re.compile(r"\s*(\d+)\s*/\s*(\d+)\s+[\d.]+s/anh")


def _so_muc(v, md) -> float:
    """Một mức đọc từ bảng mức (có thể thiếu / rỗng / hỏng) -> số; hỏng thì md."""
    if v is not None and v != "":
        try:
            return float(v)
        except (TypeError, ValueError):
            pass
    try:
        return float(md)
    except (TypeError, ValueError):
        return 0.0


def hoi_nut(cha, tieu_de: str, noi_dung: str, nut: list):
    """Hộp hỏi có nút MANG TÊN RIÊNG (messagebox chỉ có Yes / No / Cancel —
    "Yes = mức chung" là bắt người dùng nhớ quy ước). nut = [(mã, nhãn), ...]
    -> mã của nút được bấm; None khi đóng cửa sổ / Esc.

    7/10 (thiết kế lại): nút bo tròn như phần còn lại của app (gd.NutTron);
    phần tử thứ ba (tuỳ) là kiểu nút — "chinh" (vàng, việc khuyên làm) hay
    "phu". Không ghi thì mọi nút là "phu": hai lựa chọn ngang hàng (vd. Chung /
    Riêng) không được tô một bên như thể app đã chọn hộ."""
    w = tk.Toplevel(cha)
    w.title(tieu_de)
    w.transient(cha)
    w.resizable(False, False)
    kq = [None]
    o = ttk.Frame(w, padding=16)
    o.pack(fill="both", expand=True)
    ttk.Label(o, text=noi_dung, wraplength=480, justify="left").pack(anchor="w")
    hang = ttk.Frame(o)
    hang.pack(fill="x", pady=(14, 0))

    def chon(ma):
        kq[0] = ma
        w.destroy()

    for muc in reversed(nut):
        ma, nhan = muc[0], muc[1]
        kieu = muc[2] if len(muc) > 2 else "phu"
        gd.NutTron(hang, nhan, kieu=kieu, command=lambda m=ma: chon(m)).pack(
            side="right", padx=(8, 0))
    w.bind("<Escape>", lambda _e: chon(None))
    w.protocol("WM_DELETE_WINDOW", lambda: chon(None))
    try:
        w.update_idletasks()
        x = cha.winfo_rootx() + (cha.winfo_width() - w.winfo_width()) // 2
        y = cha.winfo_rooty() + (cha.winfo_height() - w.winfo_height()) // 3
        w.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        w.grab_set()
    except tk.TclError:
        pass
    w.wait_window()
    return kq[0]
