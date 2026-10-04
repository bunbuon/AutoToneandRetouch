#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kiem_tham_chieu.py — mọi `at.TÊN` mà các file gọi tới phải CÓ THẬT trong
autotone.py, và mọi `self.tên(...)` trong giao diện phải có hàm tương ứng.

    python kiem_tham_chieu.py

VÌ SAO (3/10)
    Nút "Xoá dữ liệu cũ của buổi này" gọi at.ban_xuat_moi_nhat() — hàm KHÔNG
    TỒN TẠI (đổi tên lúc nào không ai biết). Bấm nút là văng AttributeError ở
    dòng đầu; Tkinter nuốt lỗi vào stderr, cửa sổ không hiện gì, không xoá gì.
    Người dùng bấm nhiều lần trong nhiều ngày và kết luận "xoá dữ liệu chưa
    giải quyết triệt để". Nút "Đọc từ Lightroom" cũng gọi self.refresh_scan()
    không tồn tại — văng ở dòng cuối sau khi đã đọc xong.

    kiem_cu_phap.py chỉ NẠP file — tên sai trong thân hàm không bao giờ bị nạp
    tới cho tới lúc chạy đúng dòng đó. Bài này đọc cây cú pháp (ast) và đối
    chiếu từng tên, không cần chạy giao diện.

GIỚI HẠN — nói rõ để khỏi tin quá:
    · chỉ bắt `at.X` (tên module autotone nhập vào là `at`) và `self.x(...)`
      trong autotone_gui.py; gọi qua biến khác thì không bắt.
    · `self.x(...)` tính là có nếu x là hàm của BẤT KỲ lớp nào trong file, là
      thuộc tính được gán `self.x = ...`, hoặc là hàm của Tk/ttk.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import autotone as at   # noqa: E402

#[[ Ham Tk hay goi tren self khi KHONG nap duoc tkinter (may chay kiem khong cai
#   python3-tk). Co tkinter thi lay day du bang dir(). ]]
TK_HAY_DUNG = {
    "after", "after_cancel", "after_idle", "bind", "bind_all", "unbind", "configure",
    "config", "destroy", "geometry", "title", "update", "update_idletasks",
    "wait_window", "wait_visibility", "protocol", "resizable", "minsize", "maxsize",
    "grid", "pack", "place", "grid_forget", "pack_forget", "columnconfigure",
    "rowconfigure", "grid_columnconfigure", "grid_rowconfigure", "focus_set",
    "focus_force", "attributes", "iconbitmap", "iconphoto", "quit", "mainloop",
    "withdraw", "deiconify", "lift", "lower", "transient", "grab_set", "grab_release",
    "clipboard_clear", "clipboard_append", "clipboard_get", "event_generate",
    "nametowidget", "option_add", "winfo_exists", "winfo_width", "winfo_height",
    "winfo_reqwidth", "winfo_reqheight", "winfo_x", "winfo_y", "winfo_rootx",
    "winfo_rooty", "winfo_screenwidth", "winfo_screenheight", "winfo_children",
    "winfo_toplevel", "winfo_ismapped", "winfo_viewable", "state", "cget", "keys",
    "tk_setPalette", "report_callback_exception", "overrideredirect", "call",
    "focus_get", "focus_displayof", "selection_get", "winfo_pointerxy",
}


def ham_tk() -> set:
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception:                                        # noqa: BLE001
        return set(TK_HAY_DUNG)
    out = set(TK_HAY_DUNG)
    for c in (tk.Tk, tk.Toplevel, tk.Frame, tk.Canvas, ttk.Frame, ttk.Label,
              ttk.Button, ttk.Treeview):
        out |= set(dir(c))
    return out


def thieu_at(cay) -> list:
    return sorted({n.attr for n in ast.walk(cay)
                   if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                   and n.value.id == "at" and not hasattr(at, n.attr)})


def thieu_self(cay) -> list:
    ham = set()
    gan = set()
    for n in ast.walk(cay):
        if isinstance(n, ast.ClassDef):
            ham |= {f.name for f in n.body if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))}
        if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            dich = n.targets if isinstance(n, ast.Assign) else [n.target]
            for t in dich:
                for x in ast.walk(t):
                    if (isinstance(x, ast.Attribute) and isinstance(x.value, ast.Name)
                            and x.value.id == "self"):
                        gan.add(x.attr)
    tk_ = ham_tk()
    goi = {n.func.attr for n in ast.walk(cay)
           if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
           and isinstance(n.func.value, ast.Name) and n.func.value.id == "self"}
    return sorted(g for g in goi if g not in ham and g not in gan and g not in tk_)


def main() -> int:
    loi = []
    so_file = 0
    for f in sorted(HERE.glob("*.py")):
        try:
            src = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "import autotone as at" not in src and f.name != "autotone_gui.py":
            continue
        try:
            cay = ast.parse(src)
        except SyntaxError as ex:
            loi.append(f"{f.name}: SyntaxError {ex}")
            continue
        so_file += 1
        for ten in thieu_at(cay):
            loi.append(f"{f.name}: at.{ten} KHONG TON TAI trong autotone.py")
        if f.name == "autotone_gui.py":
            for ten in thieu_self(cay):
                loi.append(f"{f.name}: self.{ten}(...) KHONG co ham nao ten do")
    print(f"  rà {so_file} file")
    for m in loi:
        print("  [!]", m)
    print("TAT CA DAT" if not loi else f"{len(loi)} LOI")
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
