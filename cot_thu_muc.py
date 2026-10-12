"""Cột THƯ MỤC — ổ đĩa và thư mục ảnh như panel Folders của Lightroom (13/10).

User 13/10: "thiết kế 1 cột liệt kê ra các ổ và các folder đã được thêm vào tool
như Lightroom. Xem có lấy được luôn từ Lightroom ra hiển thị cũng đc. Hiện tại
việc chọn giữa các folder ảnh đang mất trải nghiệm. Đưa cột cảnh này lùi vào
trong." (kèm ảnh panel Folders: ổ "Data Media (G:) 0.1 / 1.8 TB", cây thư mục,
số ảnh bên phải).

NGUỒN
  · Lightroom (chính): plugin ghi cây thư mục của catalog — jobs/
    thu_muc_catalog.tsv (DanhSachCore.runThuMuc): đường dẫn · cha · số ảnh RIÊNG.
    Số hiện ra là số GỘP cả thư mục con, như Lightroom.
  · Tool: các buổi đã mở trong app (thanh_luoi "thu_muc_da_mo") mà Lightroom
    không có (chưa import / dùng nguồn .xmp) — chữ mờ, không số.
Bấm một thư mục = mở buổi đó (như chọn ở nút buổi ▾).
"""
from __future__ import annotations

import os
import shutil
import sys
import tkinter as tk
from tkinter import ttk
from pathlib import Path

import giao_dien as gd
import bieu_tuong as bt

KHOA_DA_MO = "thu_muc_da_mo"
GIU_DA_MO = 40


def khoa(p) -> str:
    return os.path.normcase(os.path.normpath(str(p)))


def nho_da_mo(path) -> None:
    """Ghi buổi vừa mở vào danh sách "đã mở trong tool" (mới nhất đầu)."""
    try:
        import thanh_luoi
        ds = [str(x) for x in (thanh_luoi.doc_kv(KHOA_DA_MO, []) or []) if isinstance(x, str)]
        p = os.path.normpath(str(path))
        ds = [p] + [x for x in ds if khoa(x) != khoa(p)]
        thanh_luoi.ghi_kv(KHOA_DA_MO, ds[:GIU_DA_MO])
    except Exception:                                        # noqa: BLE001
        pass


_CON: dict = {}


def _con_tren_dia(p: str) -> bool:
    """os.path.isdir có đệm 60 giây — ổ mạng rớt thì isdir treo vài giây, mà cột
    Thư mục làm mới mỗi 3 giây."""
    import time
    bay = time.monotonic()
    kq = _CON.get(p)
    if kq is None or bay - kq[0] > 60:
        kq = (bay, os.path.isdir(p))
        _CON[p] = kq
    return kq[1]


def da_mo() -> list:
    """Buổi đã mở trong tool — chỉ những thư mục CÒN trên đĩa (thư mục tạm của bài
    kiểm / buổi đã xoá thì thôi hiện)."""
    try:
        import thanh_luoi
        return [str(x) for x in (thanh_luoi.doc_kv(KHOA_DA_MO, []) or [])
                if isinstance(x, str) and _con_tren_dia(x)]
    except Exception:                                        # noqa: BLE001
        return []


def o_dia(p: str) -> str:
    """Gốc ổ đĩa của đường dẫn: "G:\\" (Windows), "/Volumes/X" hoặc "/" (Mac)."""
    p = str(p)
    if sys.platform == "win32" or (len(p) > 1 and p[1] == ":"):
        d = os.path.splitdrive(p)[0]
        return (d.upper() + "\\") if d else "\\"
    pa = Path(p).parts
    if len(pa) >= 3 and pa[1] == "Volumes":
        return "/" + "/".join(pa[1:3])
    return "/"


def _nhan_o_dia(goc: str) -> str:
    """"Data Media (G:)" như Lightroom; Mac: tên ổ."""
    if goc.startswith("/Volumes/"):
        return goc.split("/")[-1]
    if goc == "/":
        return "Macintosh HD" if sys.platform == "darwin" else "/"
    ten = ""
    if sys.platform == "win32":
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(261)
            if ctypes.windll.kernel32.GetVolumeInformationW(
                    ctypes.c_wchar_p(goc), buf, 261, None, None, None, None, 0):
                ten = buf.value
        except Exception:                                    # noqa: BLE001
            ten = ""
    o = goc.rstrip("\\")
    return f"{ten or 'Ổ đĩa'} ({o})"


def _dung_luong(goc: str) -> str:
    """"0.1 / 1.8 TB" = còn trống / tổng (như Lightroom)."""
    try:
        du = shutil.disk_usage(goc)
    except OSError:
        return ""
    tb = du.total >= 1024 ** 4
    k = 1024 ** 4 if tb else 1024 ** 3
    return f"{du.free / k:.1f} / {du.total / k:.1f} {'TB' if tb else 'GB'}"


def _ten(p: str) -> str:
    n = Path(p).name
    return n or p.rstrip("\\/") or p


def _tu_nhien(s: str):
    import re
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


class CotThuMuc(tk.Frame):
    """Cột trái của Cân sáng: ổ đĩa → thư mục (Lightroom + các buổi đã mở)."""

    def __init__(self, cha, khi_chon, khi_lam_moi=None, rong: int = 220):
        m = gd.MAU
        super().__init__(cha, background=m["nen"])
        self._khi_chon = khi_chon
        self._khi_lam_moi = khi_lam_moi
        self._dang_dat = False
        self._dl = ([], [], None)          # (dòng Lightroom, đã mở, đang mở)
        self._ky = None
        self._mo_san: set = set()
        tk.Frame(self, width=rong, height=1, background=m["nen"]).pack(anchor="w")
        dau = tk.Frame(self, background=m["nen"], padx=16)
        dau.pack(fill="x", pady=(14, 6))
        tk.Label(dau, text="THƯ MỤC", background=m["nen"], foreground=m["mo"],
                 font=gd.CHU_MUC).pack(side="left")
        self.btn_lam_moi = gd.NutTron(dau, "", icon="dat_lai", kieu="chu", nen=m["nen"],
                                      command=self._lam_moi)
        self.btn_lam_moi.goi_y = gd.GoiY(self.btn_lam_moi,
                                         "Đọc lại thư mục từ Lightroom ngay (plugin tự cập nhật ~2 phút "
                                         "một lần)")
        self.btn_lam_moi.pack(side="right")
        #  ô lọc thư mục
        o = tk.Frame(self, background=m["tam"], highlightthickness=1,
                     highlightbackground=m["vien2"], highlightcolor=m["nhan"])
        o.pack(fill="x", padx=(12, 8), pady=(0, 8))
        lh = gd.don_vi(self)
        ic = tk.Canvas(o, width=lh + 6, height=lh + 4, background=m["tam"], highlightthickness=0)
        ic.tu_cuon = False
        gd.ve_bieu_tuong(ic, "loc_anh", (lh + 6) / 2, (lh + 4) / 2, lh * 0.8, m["mo2"])
        ic.pack(side="left", padx=(6, 0))
        self.v_loc = tk.StringVar()
        self.o_loc = tk.Entry(o, textvariable=self.v_loc, background=m["tam"],
                              foreground=m["chu"], insertbackground=m["chu"],
                              relief="flat", borderwidth=0, font=gd.CHU_NHO)
        self.o_loc.pack(side="left", fill="x", expand=True, padx=(4, 6), pady=4)
        self._goi_y_loc = "Lọc thư mục"
        self._dat_goi_y_loc(True)
        self.o_loc.bind("<FocusIn>", lambda _e: self._dat_goi_y_loc(False), add="+")
        self.o_loc.bind("<FocusOut>", lambda _e: self._dat_goi_y_loc(not self.v_loc.get()),
                        add="+")
        self.v_loc.trace_add("write", lambda *_a: self._ve_lai())
        #  cây
        st = ttk.Style(self)
        st.configure("ThuMuc.Treeview", background=m["nen"], fieldbackground=m["nen"],
                     foreground=m["chu"], bordercolor=m["nen"], lightcolor=m["nen"],
                     darkcolor=m["nen"], rowheight=max(22, round(lh * 1.55)), font=gd.CHU_NHO,
                     indent=max(12, round(lh * 0.9)))
        st.map("ThuMuc.Treeview", background=[("selected", m["noi2"])],
               foreground=[("selected", m["chu"])])
        st.layout("ThuMuc.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        khung = tk.Frame(self, background=m["nen"])
        khung.pack(fill="both", expand=True, padx=(6, 2), pady=(0, 10))
        khung.columnconfigure(0, weight=1)
        khung.rowconfigure(0, weight=1)
        self.cay = ttk.Treeview(khung, style="ThuMuc.Treeview", show="tree",
                                columns=("so",), selectmode="browse")
        self.cay.column("#0", width=max(120, rong - 70), stretch=True)
        self.cay.column("so", width=56, anchor="e", stretch=False)
        self.cay.grid(row=0, column=0, sticky="nsew")
        self.thanh = ttk.Scrollbar(khung, orient="vertical", command=self.cay.yview)
        self.cay.configure(yscrollcommand=self._dat_thanh)
        self.cay.tag_configure("dia", foreground=m["chu"], font=gd.phong(9, "dam"))
        self.cay.tag_configure("tool", foreground=m["mo2"])
        self.cay.tag_configure("buoi", foreground=m["nhan"])
        self.cay.bind("<<TreeviewSelect>>", self._chon, add="+")
        self.cay.bind("<<TreeviewOpen>>", lambda _e: self._nho_mo(), add="+")
        self.cay.bind("<<TreeviewClose>>", lambda _e: self._nho_mo(), add="+")
        s = max(14, round(lh * 1.0))
        self._ic_tm = bt.anh_bieu_tuong(self, "thu_muc", s, m["mo"])
        self._ic_tm_buoi = bt.anh_bieu_tuong(self, "thu_muc", s, m["nhan"])
        self._ic_dia = bt.anh_bieu_tuong(self, "phan_cung", s, m["xong"])
        self.lbl_trong = tk.Label(self, text="", background=m["nen"], foreground=m["mo2"],
                                  font=gd.CHU_NHO, justify="left", anchor="w",
                                  wraplength=rong - 32)

    # ------------------------------------------------------------ phụ
    def _dat_goi_y_loc(self, hien: bool):
        m = gd.MAU
        if hien and not self.v_loc.get():
            self.o_loc.configure(foreground=m["mo2"])
            self._dang_dat = True
            self.o_loc.insert(0, self._goi_y_loc)
            self._dang_dat = False
        elif not hien and self.o_loc.get() == self._goi_y_loc and \
                self.o_loc.cget("foreground") == m["mo2"]:
            self._dang_dat = True
            self.o_loc.delete(0, "end")
            self._dang_dat = False
            self.o_loc.configure(foreground=m["chu"])

    def _chu_loc(self) -> str:
        t = self.v_loc.get()
        if t == self._goi_y_loc and self.o_loc.cget("foreground") == gd.MAU["mo2"]:
            return ""
        return t.strip().lower()

    def _dat_thanh(self, lo, hi):
        if float(lo) <= 0.0 and float(hi) >= 1.0:
            self.thanh.grid_remove()
        else:
            self.thanh.grid(row=0, column=1, sticky="ns")
        self.thanh.set(lo, hi)

    def _lam_moi(self):
        if self._khi_lam_moi is not None:
            self._khi_lam_moi()

    def _nho_mo(self):
        self.after_idle(lambda: setattr(self, "_mo_san", {
            i for i in self._tat_ca() if self.cay.item(i, "open")}))

    def _tat_ca(self):
        ra, ds = [], list(self.cay.get_children(""))
        while ds:
            i = ds.pop()
            ra.append(i)
            ds.extend(self.cay.get_children(i))
        return ra

    def _chon(self, _e=None):
        if self._dang_dat:
            return
        sel = self.cay.selection()
        if not sel or sel[0].startswith("dia:"):
            return
        duong = self._duong.get(sel[0])
        if duong and self._khi_chon is not None:
            self._khi_chon(duong)

    # ------------------------------------------------------------ dữ liệu
    def dat(self, dong_lr, da_mo_tool, dang_mo) -> None:
        """dong_lr: [(đường dẫn, cha, số ảnh riêng)] từ Lightroom (None = chưa có);
        da_mo_tool: các buổi đã mở trong app; dang_mo: buổi đang mở."""
        ky = (tuple(dong_lr or ()), tuple(da_mo_tool or ()), khoa(dang_mo) if dang_mo else None,
              dong_lr is None)
        if ky == self._ky:
            return
        self._ky = ky
        self._dl = (list(dong_lr or []), list(da_mo_tool or []), dang_mo, dong_lr is None)
        self._ve_lai()

    def _ve_lai(self):
        if self._dang_dat:
            return
        dong_lr, tool, dang_mo, chua_co_lr = self._dl
        loc = self._chu_loc()
        cay = self.cay
        self._dang_dat = True
        try:
            cay.delete(*cay.get_children(""))
            self._duong = {}
            #  nút Lightroom: con, số riêng, tổng gộp
            rieng, con, goc_lr = {}, {}, []
            ten_that = {}
            for p, cha, n in dong_lr:
                k = khoa(p)
                rieng[k] = int(n)
                ten_that[k] = p
                if cha:
                    con.setdefault(khoa(cha), []).append(k)
                else:
                    goc_lr.append(k)
            #  thư mục Lightroom có cha nhưng cha không có trong danh sách -> coi là gốc
            for p, cha, _n in dong_lr:
                if cha and khoa(cha) not in rieng and khoa(p) not in goc_lr:
                    goc_lr.append(khoa(p))
            tong: dict = {}

            def gop(k):
                if k in tong:
                    return tong[k]
                t = rieng.get(k, 0) + sum(gop(c) for c in con.get(k, []))
                tong[k] = t
                return t
            for k in goc_lr:
                gop(k)
            #  thư mục tool không nằm dưới thư mục Lightroom nào
            tool_rieng = []
            for p in tool:
                k = khoa(p)
                if k in rieng:
                    continue
                tool_rieng.append(p)
            #  lọc: giữ thư mục khớp + tổ tiên của nó
            khop = None
            if loc:
                khop = set()
                cha_cua = {c: k for k, ds in con.items() for c in ds}
                for k, p in ten_that.items():
                    if loc in _ten(p).lower():
                        x = k
                        while x is not None and x not in khop:
                            khop.add(x)
                            x = cha_cua.get(x)
                tool_rieng = [p for p in tool_rieng if loc in _ten(p).lower()]
            #  nhóm theo ổ
            o_cua: dict = {}
            for k in goc_lr:
                if khop is not None and k not in khop:
                    continue
                o_cua.setdefault(o_dia(ten_that[k]), []).append(("lr", k))
            for p in tool_rieng:
                o_cua.setdefault(o_dia(p), []).append(("tool", p))
            k_dang = khoa(dang_mo) if dang_mo else None
            for goc in sorted(o_cua, key=_tu_nhien):
                iid_dia = "dia:" + goc
                cay.insert("", "end", iid=iid_dia, text=" " + _nhan_o_dia(goc),
                           values=(_dung_luong(goc),), image=self._ic_dia,
                           open=(iid_dia in self._mo_san or not self._mo_san), tags=("dia",))
                muc = sorted(o_cua[goc], key=lambda x: _tu_nhien(_ten(
                    ten_that[x[1]] if x[0] == "lr" else x[1])))

                def them(cha_iid, k):
                    p = ten_that[k]
                    la_buoi = k == k_dang
                    cay.insert(cha_iid, "end", iid=k, text=" " + _ten(p),
                               values=(gd.so_vn(tong.get(k, rieng.get(k, 0))),),
                               image=self._ic_tm_buoi if la_buoi else self._ic_tm,
                               open=k in self._mo_san or bool(loc), tags=("buoi",) if la_buoi else ())
                    self._duong[k] = p
                    for c in sorted(con.get(k, []), key=lambda x: _tu_nhien(_ten(ten_that[x]))):
                        if khop is None or c in khop:
                            them(k, c)
                for loai, x in muc:
                    if loai == "lr":
                        them(iid_dia, x)
                    else:
                        k = khoa(x)
                        if cay.exists(k):
                            continue
                        la_buoi = k == k_dang
                        cay.insert(iid_dia, "end", iid=k, text=" " + _ten(x), values=("",),
                                   image=self._ic_tm_buoi if la_buoi else self._ic_tm,
                                   tags=("buoi",) if la_buoi else ("tool",))
                        self._duong[k] = x
            #  buổi đang mở: hiện + chọn (mở tổ tiên)
            if k_dang and cay.exists(k_dang):
                x = cay.parent(k_dang)
                while x:
                    cay.item(x, open=True)
                    x = cay.parent(x)
                cay.selection_set(k_dang)
                cay.see(k_dang)
            else:
                cay.selection_set(())
            if not cay.get_children(""):
                self.lbl_trong.configure(
                    text=("Không thư mục nào khớp." if loc else
                          "Đang đọc thư mục từ Lightroom…\nMở Lightroom (plugin AutoTone) để "
                          "thấy các thư mục của catalog." if chua_co_lr else
                          "Catalog Lightroom chưa có thư mục nào."))
                if not self.lbl_trong.winfo_manager():
                    self.lbl_trong.pack(fill="x", padx=16, before=self.cay.master)
            elif self.lbl_trong.winfo_manager():
                self.lbl_trong.pack_forget()
        finally:
            self._dang_dat = False
