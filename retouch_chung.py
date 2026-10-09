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


#[[ CHON ANH MOI DE TU RETOUCH (9/10, tach thanh ham thuan de kiem duoc).
#
#   ds_stat = [(duong dan, da co ket qua?, co file, mtime_ns, mtime)]; td = ban ghi
#   theo doi cua retouch_may (biet / cho / tu_luc / ban_do / xuat). Luat:
#     * da nam trong "biet" -> bo (da chay hoac da loai).
#     * CHE DO XUAT (td["xuat"]): chi nhan anh THUOC LUOT NAY — mtime >= tu_luc
#       (Lightroom vua ghi) hoac nam trong bang path->jpg plugin ghi (ban_do).
#       Anh cu trong thu muc (lan xuat truoc, Lightroom chua dong toi) KHONG lay:
#       lay roi Lightroom ghi de len sau thi ket qua retouch la cua ban cu.
#       Da co ket qua ma Lightroom vua ghi lai -> VAN chay lai (lam_lai).
#     * Che do thuong: anh da co ket qua -> biet, bo qua.
#     * On dinh: (co, mtime_ns) KHONG DOI qua hai lan quet moi "san" — dang chep
#       / dang ghi thi cho. Tra (san, co_moi): co_moi = vua thay tam moi (de ve
#       lai dai anh). ]]
def chon_anh_moi(ds_stat, td: dict):
    san, co_moi = [], False
    biet, cho = td.setdefault("biet", set()), td.setdefault("cho", {})
    xuat = bool(td.get("xuat"))
    tu_luc = float(td.get("tu_luc") or 0.0)
    ban_do = td.get("ban_do") or set()
    import os as _os
    for k, xong, co, mtns, mt in ds_stat:
        if k in biet:
            continue
        if xuat:
            if not (mt >= tu_luc or _os.path.normcase(k) in ban_do):
                continue
        elif xong:
            biet.add(k)
            continue
        dau = (int(co), int(mtns))
        if co > 0 and cho.get(k) == dau:
            san.append(k)
        else:
            co_moi = co_moi or k not in cho
            cho[k] = dau
    return san, co_moi


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
