# -*- coding: utf-8 -*-
"""Kiểm giao diện TIẾNG ANH (13/10).

User 13/10: "chắc sẽ cần làm thêm 1 bản ngôn ngữ tiếng anh. Mặc định sẽ là tiếng anh
khi cài app lần đầu. Trong setting sẽ cho chọn ngôn ngữ".

  1. ngon_ngu.t: nguyên câu, mẫu f-string, câu ghép, giữ đường dẫn, dịch hai lần vô hại.
  2. Chọn ngôn ngữ: mã nguồn -> vi; bản cài lần đầu -> en; máy đã dùng -> vi; kv thắng.
  3. App dựng bằng tiếng Anh (móc Tk): tiêu đề, nút Xử lý ảnh, nhãn, menu, ô chọn
     (nhãn MODES dịch ở nguồn nên mode_value() vẫn đúng), nút không bị cắt chữ.
Chạy:  python test_ngon_ngu.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path

GOC = Path(__file__).resolve().parent
LOI: list = []

for _l in (sys.stdout, sys.stderr):
    try:
        _l.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                        # noqa: BLE001
        pass


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


def phan_chon_ngon_ngu():
    """Chạy trong tiến trình con (ngon_ngu quyết MỘT lần mỗi tiến trình)."""
    ma = r'''
import os, sys, json
sys.path.insert(0, %r)
os.environ.pop("AUTOTONE_NGON_NGU", None)
import ngon_ngu, thanh_luoi, duong_dan as dd
kq = {}
kq["nguon"] = ngon_ngu._quyet()
sys.frozen = True
kq["cai_dau"] = ngon_ngu._quyet()
kq["luu"] = thanh_luoi.doc_kv("ngon_ngu")
thanh_luoi.ghi_kv("ngon_ngu", None)
(dd.goc_du_lieu() / "phan_tich").mkdir(parents=True, exist_ok=True)
kq["da_dung"] = ngon_ngu._quyet()
thanh_luoi.ghi_kv("ngon_ngu", "en")
kq["kv"] = ngon_ngu._quyet()
print(json.dumps(kq))
''' % str(GOC)
    import json
    for ten in ("a", "b"):
        tam = Path(tempfile.mkdtemp(prefix="nn_" + ten))
        env = dict(os.environ, AUTOTONE_DATA=str(tam), PYTHONUTF8="1")
        env.pop("AUTOTONE_NGON_NGU", None)
        r = subprocess.run([sys.executable, "-c", ma], capture_output=True, text=True,
                           env=env, cwd=str(GOC), timeout=120)
        shutil.rmtree(tam, ignore_errors=True)
        dong = [x for x in r.stdout.splitlines() if x.startswith("{")]
        if dong:
            kq = json.loads(dong[-1])
            break
    else:
        kq = {}
    ktra("chạy từ mã nguồn, chưa chọn -> Tiếng Việt", kq.get("nguon") == "vi", str(kq))
    ktra("bản cài LẦN ĐẦU (thư mục dữ liệu trống) -> English, và ghi lại lựa chọn",
         kq.get("cai_dau") == "en" and kq.get("luu") == "en")
    ktra("bản cài trên máy ĐÃ dùng app (có phan_tich/) -> giữ Tiếng Việt", kq.get("da_dung") == "vi")
    ktra("đã chọn trong Thiết lập (kv) -> theo lựa chọn", kq.get("kv") == "en")


def main() -> int:
    phan_chon_ngon_ngu()
    tam = Path(tempfile.mkdtemp(prefix="nn_app_"))
    os.environ["AUTOTONE_DATA"] = str(tam)
    os.environ["AUTOTONE_NGON_NGU"] = "en"
    os.environ["AUTOTONE_CATALOG_LR"] = "0"
    sys.path.insert(0, str(GOC))
    import ngon_ngu as ng
    t = ng.t
    # ---------------------------------------------------------------- 1. hàm dịch
    ktra("nguyên câu", t("Xử lý ảnh") == "Process photos", t("Xử lý ảnh"))
    ktra("mẫu f-string giữ số", t("Đang đo 12/34 ảnh...") == "Measuring 12/34 photos...",
         t("Đang đo 12/34 ảnh..."))
    ktra("dịch hai lần vô hại", t(t("Thiết lập cân sáng")) == t("Thiết lập cân sáng"))
    s = r"Không mở được G:\Sản Phẩm Final\BVDay3 — ổ đĩa chưa cắm / thư mục đã chuyển chỗ."
    ktra("đường dẫn có dấu giữ nguyên", "G:\\Sản Phẩm Final\\BVDay3" in t(s) and "Could not open" in t(s),
         t(s))
    ktra("câu ghép (f-string có trong từ điển + đoạn nối thêm)",
         t("221 ảnh · 43 cảnh · 182 ảnh sẽ đổi · ΔEV từ -1.40 đến +1.75 (trung bình +0.19) · x")
         .startswith("221 photos · 43 scenes · 182 photos will change"))
    ktra("chữ không dấu trên giao diện", t("Chung") == "All" and t("Nhanh") == "Fast")
    ktra("tiêu đề in hoa", t("CƠ THỂ") == "BODY", t("CƠ THỂ"))
    ktra("câu không phải tiếng Việt để nguyên", t("DSC09670.ARW") == "DSC09670.ARW")
    # ---------------------------------------------------------------- 3. app tiếng Anh
    ng.cai_moc()
    import tkinter as tk
    import tkinter.font as tkfont
    import autotone_gui as ag
    import giao_dien as gd
    ag.bq.kiem = lambda: {"co_phep": True, "con_lai": timedelta(days=300), "nhac": "",
                          "goi": "1 năm", "may": "TEST01", "het_han": False, "ly_do": ""}
    root = tk.Tk()
    root.geometry("1600x940+0+0")
    gd.dat_theme(root)
    try:
        app = ag.App(root)
        app.grid(row=0, column=0, sticky="nsew")
        root.title("SAY Auto Tone — cân sáng & retouch")
        for _ in range(10):
            root.update_idletasks()
            root.update()
            time.sleep(0.02)
        ktra("tiêu đề cửa sổ tiếng Anh", "cân sáng" not in root.title(), root.title())
        b = app.btn_xu_ly
        chu = b.itemcget(b._i_chu, "text")
        ktra("nút Xử lý ảnh vẽ chữ tiếng Anh", chu == "Process photos", chu)
        f = tkfont.Font(font=b._f)
        ktra("nút đủ rộng cho chữ tiếng Anh (đo theo chữ đã dịch)",
             b.winfo_reqwidth() >= f.measure("Process photos"), f"{b.winfo_reqwidth()} px")
        ktra("nhãn đầu bảng Thiết lập tiếng Anh", app.lbl_md.cget("text") == "Auto Tone settings",
             app.lbl_md.cget("text"))
        m = app.menu_them
        nhan = [m.entrycget(i, "label") for i in range(m.index("end") + 1)
                if m.type(i) in ("command", "checkbutton")]
        ktra("menu ⋯ tiếng Anh", "Re-analyze the whole session" in nhan
             and not any(ng.VN.search(x) for x in nhan), " | ".join(nhan[:5]))
        ktra("ô chọn Chế độ: nhãn tiếng Anh, mode_value() vẫn đúng",
             not ng.VN.search(app.v_mode.get()) and app.mode_value() == "absolute",
             f"{app.v_mode.get()} -> {app.mode_value()}")
        ktra("ô chọn ngôn ngữ EN | VI ở đầu bảng Thiết lập",
             app.chon_ngon_ngu.winfo_ismapped() and app.v_ngon_ngu.get() == "en")
        #  không còn nhãn ttk / tk tiếng Việt đang HIỆN ở trang Cân sáng
        con = []

        def di(w):
            for c in w.winfo_children():
                try:
                    if c.winfo_ismapped() and isinstance(c, (tk.Label, tk.Button)) \
                            or c.winfo_class() in ("TLabel", "TButton", "TCheckbutton"):
                        #  chữ THẬT đang vẽ (NhanGon.cget trả câu gốc đủ — chủ ý)
                        x = str(tk.Label.cget(c, "text") if isinstance(c, tk.Label)
                                else c.cget("text"))
                        if c.winfo_ismapped() and ng.VN.search(x):
                            con.append(x[:50])
                except tk.TclError:
                    pass
                di(c)
        di(app)
        ktra("không còn nhãn tiếng Việt đang hiện (trừ tên riêng)", len(con) <= 2, " | ".join(con[:6]))
    finally:
        try:
            root.destroy()
        except Exception:                                    # noqa: BLE001
            pass
        shutil.rmtree(tam, ignore_errors=True)
    print("TAT CA DAT" if not LOI else f"{len(LOI)} LOI")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
