#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""preset_ui.py — Chọn preset Lightroom + xem trước CẢ LƯỚI theo preset (9/10).

User 9/10: "Thêm tính năng lấy ra Preset và khi chọn Preset thì sẽ load lại Preview
với preset đã chọn cho toàn bộ ảnh preview" — kèm ảnh mẫu ô "Preset Lightroom" của
NEXUS AI Retouch (tìm preset, nhóm User Presets, công tắc hiện preset Adobe, "Đã
chọn: …").

    NutPresetLR(cha, dp)     nút trên thanh lưới: "Preset LR: <tên> ▾" + tiến độ
    BangPresetLR             bảng nổi dưới nút: tìm, danh sách theo nhóm, công tắc
    DieuPhoiPreset(app)      MỘT cho cả app: preset đang xem, gửi plugin, theo dõi
                             tiến độ, báo các lưới / ảnh lớn đã đăng ký đọc lại ảnh

Màu do Lightroom render thật (xem preset_lr.py / XemPresetCore.lua) — chọn preset
là các ô đổi DẦN theo nhịp Lightroom render (ảnh đang xem + ô đang nhìn đi trước).
"""
from __future__ import annotations

import os
import sys
import time
import traceback
from pathlib import Path

import tkinter as tk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import giao_dien as gd
import preset_lr

NHIP_MS = 900
CHO_LR_GIAY = 12          # quá chừng này giây plugin chưa nhận -> nói ra


def _nc(p) -> str:
    return os.path.normcase(os.path.normpath(str(p)))


# ====================================================================== điều phối
class DieuPhoiPreset:
    """Preset đang xem + lượt render đang chạy. Các lưới / ảnh lớn đăng ký vào."""

    def __init__(self, app):
        self.app = app
        self.luoi: list = []           # LuoiAnh
        self.nghe: list = []           # cb(tập đường dẫn normcase | None = mọi tấm)
        self.nut: list = []            # NutPresetLR
        self.p = preset_lr.chon_hien()
        self.id = None
        self.td = None
        self.da_thay: set = set()
        self.hang_doi: list = []       # [(thư mục, [ảnh…])] chờ gửi (nhiều thư mục con)
        self.t_gui = 0.0
        self.tong = 0
        self.co_san = 0
        self.thu_muc = ""
        self.loi = ""
        self._hen = None
        self._dat_nguon()

    # ------------------------------------------------------------ đăng ký
    def dang_ky_luoi(self, luoi) -> None:
        if luoi is not None and luoi not in self.luoi:
            self.luoi.append(luoi)

    def dang_ky_nghe(self, cb) -> None:
        if cb not in self.nghe:
            self.nghe.append(cb)

    def dang_ky_nut(self, nut) -> None:
        if nut not in self.nut:
            self.nut.append(nut)
        nut.cap_nhat()

    # ------------------------------------------------------------ nguồn ảnh
    def _dat_nguon(self) -> None:
        import luoi_anh
        luoi_anh.dat_nguon(self._nguon if self.p else None)

    def _nguon(self, path):
        p = self.p
        if not p:
            return None
        try:
            return preset_lr.anh_preset(path, p)
        except Exception:                                    # noqa: BLE001
            return None

    def _bao(self, moi) -> None:
        for cb in list(self.nghe):
            try:
                cb(moi)
            except Exception:                                # noqa: BLE001
                traceback.print_exc()

    def _lam_moi_luoi(self, moi=None) -> None:
        for l in list(self.luoi):
            try:
                if moi is None:
                    l.lam_moi_anh()
                else:
                    ds = [k for k in l._vi_tri if _nc(k) in moi]
                    if ds:
                        l.lam_moi_anh(ds)
            except Exception:                                # noqa: BLE001
                pass

    def _cap_nhat_nut(self) -> None:
        for n in list(self.nut):
            try:
                n.cap_nhat()
            except Exception:                                # noqa: BLE001
                pass

    # ------------------------------------------------------------ chọn preset
    def chon(self, p: dict | None) -> None:
        """Người dùng chọn preset (None = không áp): mọi lưới đọc lại ảnh, gửi
        Lightroom render các tấm còn thiếu của buổi đang xem."""
        doi = not preset_lr.cung_preset(p, self.p)
        self.p = p
        preset_lr.dat_chon(p)
        self._dat_nguon()
        self.loi = ""
        if doi:
            self._lam_moi_luoi(None)
            self._bao(None)
        if p is None:
            preset_lr.dung()
            self.id, self.td, self.hang_doi = None, None, []
            self._dung_hen()
            self._cap_nhat_nut()
            return
        self.gui()

    def dung(self) -> None:
        preset_lr.dung()
        self.hang_doi = []
        self.loi = "đã dừng"
        if self.td is not None:
            self.td["trang_thai"] = "dung"
        self._cap_nhat_nut()

    def _ngu_canh(self):
        """(danh sách ảnh của buổi đang xem, ảnh ưu tiên) — lấy từ app."""
        try:
            return self.app.ds_cho_preset()
        except Exception:                                    # noqa: BLE001
            traceback.print_exc()
            return [], []

    def gui(self) -> None:
        """Gửi các tấm CÒN THIẾU của buổi đang xem (ảnh ưu tiên đi trước)."""
        if not self.p:
            return
        ds, uu = self._ngu_canh()
        import nguon_xem
        ds = [str(x) for x in ds if nguon_xem.la_raw(x)]
        self.tong = len(ds)
        thieu = [x for x in ds if preset_lr.anh_preset(x, self.p) is None]
        self.co_san = len(ds) - len(thieu)
        if not thieu:
            self.id, self.td, self.hang_doi = None, None, []
            self._cap_nhat_nut()
            return
        dat = {_nc(x) for x in thieu}
        dau, da = [], set()
        for x in uu:                       # tấm đang mở / chọn / đang nhìn — mỗi tấm một lần
            k = _nc(x)
            if k in dat and k not in da:
                dau.append(str(x))
                da.add(k)
        thu_tu = dau + [x for x in thieu if _nc(x) not in da]
        #  gom theo thư mục (buổi có thư mục con): mỗi lượt plugin một thư mục
        nhom: dict = {}
        for x in thu_tu:
            nhom.setdefault(str(Path(x).parent), []).append(x)
        self.hang_doi = list(nhom.items())
        self._gui_tiep()

    def _gui_tiep(self) -> None:
        if not self.hang_doi or not self.p:
            return
        thu_muc, ds = self.hang_doi.pop(0)
        try:
            self.id = preset_lr.gui_xem(self.p, ds, thu_muc)
        except OSError as ex:
            self.loi = f"không gửi được yêu cầu: {ex}"
            self._cap_nhat_nut()
            return
        self.thu_muc = thu_muc
        self.td = {"trang_thai": "cho", "xong": 0, "tong": len(ds)}
        self.da_thay = set()
        self.t_gui = time.time()
        self._cap_nhat_nut()
        self._hen_soi()

    def doi_buoi(self) -> None:
        """App vừa mở buổi khác / lưới đổi danh sách: còn tấm thiếu thì gửi."""
        if self.p and (self.td is None or self.td.get("trang_thai") in ("xong", "dung", "loi")):
            self.gui()

    # ------------------------------------------------------------ theo dõi
    def _dung_hen(self) -> None:
        if self._hen is not None:
            try:
                self.app.after_cancel(self._hen)
            except Exception:                                # noqa: BLE001
                pass
            self._hen = None

    def _hen_soi(self) -> None:
        self._dung_hen()
        try:
            self._hen = self.app.after(NHIP_MS, self._soi)
        except Exception:                                    # noqa: BLE001
            self._hen = None

    def _soi(self) -> None:
        self._hen = None
        if not self.id:
            return
        td = preset_lr.tien_do(self.id)
        if td is not None:
            self.td = td
            b = preset_lr.bang()
            moi = {k for k in b if k not in self.da_thay}
            if moi:
                self.da_thay |= moi
                self._lam_moi_luoi(moi)
                self._bao(moi)
        tt = (self.td or {}).get("trang_thai")
        if td is None and time.time() - self.t_gui > CHO_LR_GIAY:
            try:
                import autotone as at
                nhip = at.plugin_nhip()
            except Exception:                                # noqa: BLE001
                nhip = None
            self.loi = ("Lightroom chưa mở / plugin AutoTone chưa chạy — mở Lightroom "
                        "là tự làm" if nhip is None or nhip > 60 else
                        "Lightroom đang bận việc khác — làm xong sẽ tới lượt")
        elif td is not None:
            self.loi = ""
        self._cap_nhat_nut()
        if tt in ("xong", "dung", "loi", "thay"):
            if tt == "loi":
                self.loi = str(td.get("thong_bao") or "lỗi không rõ") if td else self.loi
                self.hang_doi = []
                self._cap_nhat_nut()
                return
            if tt == "xong" and self.hang_doi:
                self._gui_tiep()
            return
        self._hen_soi()

    # ------------------------------------------------------------ chữ cho nút
    def mo_ta(self) -> tuple:
        """(chữ trên nút, chữ phụ, loại: ""|"chay"|"loi")."""
        if not self.p:
            return "Preset LR: không áp", "", ""
        ten = self.p.get("ten") or "?"
        if self.loi:
            return f"Preset LR: {ten}", self.loi, "loi"
        td = self.td
        if td and td.get("trang_thai") in ("cho", "dang_chay"):
            xong = self.co_san + int(td.get("xong") or 0)
            phu = f"Lightroom đang dựng {xong}/{self.tong}"
            if td.get("trang_thai") == "cho":
                phu = f"chờ Lightroom nhận… ({self.co_san}/{self.tong} có sẵn)"
            return f"Preset LR: {ten}", phu, "chay"
        if td and int(td.get("lech") or 0):
            return (f"Preset LR: {ten}", f"⚠ {td['lech']} ảnh trả lại thông số chưa khớp — "
                    "xem Nhật ký plugin", "loi")
        thieu = int((td or {}).get("thieu") or 0)
        if not self.tong and td is None:
            return f"Preset LR: {ten}", "buổi đang xem không có ảnh RAW", ""
        return (f"Preset LR: {ten}", (f"{thieu} ảnh không có trong catalog Lightroom"
                                      if thieu else ""), "")


# ====================================================================== nút
class NutPresetLR(tk.Frame):
    """[◐ Preset LR: <tên> ▾]  Lightroom đang dựng 12/560"""

    def __init__(self, cha, dp: DieuPhoiPreset, nen: str | None = None):
        self._nen = nen or gd.MAU["toi"]
        super().__init__(cha, background=self._nen)
        self.dp = dp
        self.btn = gd.NutTron(self, "Preset LR: không áp", kieu="phu", nen=self._nen,
                              font=gd.CHU, mui_ten=True, command=self._mo)
        self.btn.pack(side="left")
        self.btn.goi_y = gd.GoiY(self.btn, "Chọn preset Lightroom để xem trước CẢ LƯỚI theo "
                                 "preset đó — Lightroom render thật (cần Lightroom đang "
                                 "mở). Không đổi ảnh trong catalog.")
        self.lbl = tk.Label(self, text="", background=self._nen, foreground=gd.MAU["mo"],
                            font=gd.CHU_NHO, anchor="w")
        self.lbl.pack(side="left", padx=(8, 0))
        self._bang = None
        dp.dang_ky_nut(self)

    def cap_nhat(self) -> None:
        chu, phu, loai = self.dp.mo_ta()
        if len(chu) > 40:
            chu = chu[:39] + "…"
        try:
            if self.btn.cget("text") != chu:
                self.btn.configure(text=chu)
            self.lbl.configure(text=phu, foreground=(gd.MAU["canh"] if loai == "loi" else
                                                     gd.MAU["nhan"] if loai == "chay" else
                                                     gd.MAU["mo"]))
        except tk.TclError:
            return
        b = self._bang
        if b is not None:
            try:
                b.cap_nhat_trang_thai()
            except tk.TclError:
                self._bang = None

    def _mo(self) -> None:
        if self._bang is not None:
            try:
                self._bang.dong()
            except tk.TclError:
                pass
            self._bang = None
            return
        self._bang = BangPresetLR(self, self.btn, self.dp, khi_dong=self._da_dong)

    def _da_dong(self) -> None:
        self._bang = None


# ====================================================================== bảng nổi
class BangPresetLR(tk.Toplevel):
    """Bảng chọn preset nổi dưới nút (giống ô "Preset Lightroom" của NEXUS)."""

    RONG = 300

    def __init__(self, cha, neo, dp: DieuPhoiPreset, khi_dong=None):
        super().__init__(cha)
        m = gd.MAU
        self.dp = dp
        self._khi_dong = khi_dong
        self.overrideredirect(True)
        self.configure(background=m["vien2"])
        lh = gd.don_vi(cha)
        self._lh = lh
        rong = max(self.RONG, round(lh * 21))
        cao = round(lh * 30)
        trong = tk.Frame(self, background=m["nen"])
        trong.pack(fill="both", expand=True, padx=1, pady=1)

        dau = tk.Frame(trong, background=m["nen"])
        dau.pack(fill="x", padx=12, pady=(10, 6))
        tk.Label(dau, text="Preset Lightroom", background=m["nen"], foreground=m["chu"],
                 font=gd.CHU_TIEU_DE).pack(side="left")
        gd.NutTron(dau, "", kieu="chu", nen=m["nen"], icon="dong",
                   command=self.dong).pack(side="right")
        gd.NutTron(dau, "", kieu="chu", nen=m["nen"], icon="dong_bo",
                   command=self._lam_moi_ds).pack(side="right", padx=(0, 2))

        o_tim = tk.Frame(trong, background=m["tam"], highlightthickness=1,
                         highlightbackground=m["vien2"], highlightcolor=m["vien2"])
        o_tim.pack(fill="x", padx=12, pady=(0, 8))
        self.v_tim = tk.StringVar()
        self.e_tim = tk.Entry(o_tim, textvariable=self.v_tim, background=m["tam"],
                              foreground=m["chu"], insertbackground=m["chu"], relief="flat",
                              font=gd.CHU, borderwidth=0)
        self.e_tim.pack(fill="x", padx=8, pady=5)
        self._goi_y_tim = True
        self._dat_goi_y_tim()
        self.e_tim.bind("<FocusIn>", lambda _e: self._bo_goi_y_tim())
        self.v_tim.trace_add("write", lambda *_a: self._ve_lai())

        o_ds = tk.Frame(trong, background=m["nen"])
        o_ds.pack(fill="both", expand=True, padx=(6, 4))
        self.c = tk.Canvas(o_ds, background=m["nen"], highlightthickness=0, borderwidth=0,
                           width=rong - 24, height=cao)
        self.c.pack(side="left", fill="both", expand=True)
        self.c.tu_cuon = True
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.c.bind(ev, self._lan)
        self.c.bind("<Motion>", self._re)
        self.c.bind("<Leave>", lambda _e: self._dat_re(None))
        self.c.bind("<Button-1>", self._bam)
        self.c.bind("<Double-Button-1>", lambda e: (self._bam(e), self.dong()))

        duoi = tk.Frame(trong, background=m["nen"])
        duoi.pack(fill="x", padx=12, pady=(8, 4))
        self.v_adobe = tk.BooleanVar(value=False)
        gd.CongTac(duoi, self.v_adobe, command=self._doi_adobe, nen=m["nen"]).pack(side="left")
        tk.Label(duoi, text="Hiện preset của Adobe", background=m["nen"], foreground=m["chu"],
                 font=gd.CHU).pack(side="left", padx=(8, 0))
        self.lbl_chon = tk.Label(trong, text="", background=m["nen"], foreground=m["mo"],
                                 font=gd.CHU_NHO, anchor="w", justify="left",
                                 wraplength=rong - 24)
        self.lbl_chon.pack(fill="x", padx=12, pady=(2, 2))
        self.lbl_td = tk.Label(trong, text="", background=m["nen"], foreground=m["mo"],
                               font=gd.CHU_NHO, anchor="w", justify="left",
                               wraplength=rong - 24)
        self.lbl_td.pack(fill="x", padx=12, pady=(0, 4))
        hang = tk.Frame(trong, background=m["nen"])
        hang.pack(fill="x", padx=12, pady=(0, 10))
        self.btn_dung = gd.NutTron(hang, "Dừng dựng", kieu="toi", nen=m["nen"], font=gd.CHU,
                                   command=self._dung)
        self.btn_dung.pack(side="left")
        self.btn_lai = gd.NutTron(hang, "Dựng lại ảnh thiếu", kieu="toi", nen=m["nen"],
                                  font=gd.CHU, command=self._gui_lai)
        self.btn_lai.pack(side="left", padx=(6, 0))

        self._ds_goc: list = []
        self._hang: list = []          # [(loại, dữ liệu, y0, y1)]
        self._re_i = None
        self._nap_ds()
        self.cap_nhat_trang_thai()
        self.update_idletasks()
        x = neo.winfo_rootx()
        y = neo.winfo_rooty() + neo.winfo_height() + 4
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = max(0, min(x, sw - w - 8))
        if y + h > sh - 40:
            y = max(0, neo.winfo_rooty() - h - 4)
        self.geometry(f"+{x}+{y}")
        self.bind("<Escape>", lambda _e: self.dong())
        self.bind("<FocusOut>", self._mat_focus, add="+")
        self.after(30, self._lay_focus)
        #  Lightroom vừa mở thì xin danh sách mới nhất (preset vừa thêm / đổi tên)
        preset_lr.xin_ds()

    # ------------------------------------------------------------ focus / đóng
    def _lay_focus(self):
        try:
            self.focus_force()
            self.c.focus_set()
        except tk.TclError:
            pass

    def _mat_focus(self, _e=None):
        self.after(120, self._kiem_focus)

    def _kiem_focus(self):
        try:
            f = self.focus_get()
        except (tk.TclError, KeyError):
            f = None
        if f is None or not str(f).startswith(str(self)):
            self.dong()

    def dong(self):
        try:
            self.destroy()
        except tk.TclError:
            pass
        if self._khi_dong is not None:
            self._khi_dong()
            self._khi_dong = None

    # ------------------------------------------------------------ ô tìm
    def _dat_goi_y_tim(self):
        self.e_tim.configure(foreground=gd.MAU["mo2"])
        self.v_tim.set("Tìm preset…")
        self._goi_y_tim = True

    def _bo_goi_y_tim(self):
        if self._goi_y_tim:
            self._goi_y_tim = False
            self.v_tim.set("")
            self.e_tim.configure(foreground=gd.MAU["chu"])

    def _tu_tim(self) -> str:
        return "" if self._goi_y_tim else self.v_tim.get()

    # ------------------------------------------------------------ danh sách
    def _nap_ds(self):
        try:
            self._ds_goc = preset_lr.danh_sach(bool(self.v_adobe.get()))
        except Exception:                                    # noqa: BLE001
            traceback.print_exc()
            self._ds_goc = []
        self._ve_lai()
        #  cao vừa danh sách (tối đa ~20 dòng, cuộn khi dài hơn) — gõ tìm thì
        #  giữ nguyên cao, bảng không nhảy dưới tay
        rh = round(self._lh * 1.85)
        cao = self._hang[-1][3] + 6 if self._hang else rh * 3
        try:
            self.c.configure(height=max(rh * 4, min(cao, round(self._lh * 20))))
        except tk.TclError:
            pass

    def _lam_moi_ds(self):
        preset_lr.xin_ds()
        self.after(2500, self._nap_ds)
        self._nap_ds()

    def _doi_adobe(self):
        self._nap_ds()

    def _ve_lai(self):
        m = gd.MAU
        c = self.c
        c.delete("all")
        lh = self._lh
        rh = round(lh * 1.85)
        w = max(100, c.winfo_width() if c.winfo_width() > 10 else int(c.cget("width")))
        ds = preset_lr.loc(self._ds_goc, self._tu_tim())
        self._hang = []
        y = 2
        dang = self.dp.p
        f = gd.CHU
        f_nhom = gd.CHU
        self._hang.append(("khong", None, y, y + rh))
        y += rh
        nhom_cu = None
        for p in ds:
            nh = p.get("nhom") or ""
            if nh != nhom_cu:
                self._hang.append(("nhom", nh, y, y + rh))
                y += rh
                nhom_cu = nh
            self._hang.append(("preset", p, y, y + rh))
            y += rh
        if not ds:
            self._hang.append(("trong", None, y, y + rh * 2))
            y += rh * 2
        for i, (loai, d, y0, y1) in enumerate(self._hang):
            chon = (loai == "khong" and not dang) or (loai == "preset" and dang
                                                     and preset_lr.cung_preset(d, dang))
            nen = m["noi2"] if chon else (m["noi"] if i == self._re_i and loai in
                                          ("khong", "preset") else None)
            if nen:
                c.create_rectangle(4, y0 + 1, w - 4, y1 - 1, fill=nen, outline="",
                                   tags=("o", f"h{i}"))
            if loai == "khong":
                gd.ve_bieu_tuong(c, "dong", 18, (y0 + y1) / 2, lh * 0.7, m["mo"])
                c.create_text(34, (y0 + y1) / 2, text="Không áp preset (ảnh như hiện tại)",
                              anchor="w", fill=m["nhan"] if chon else m["chu"], font=f)
            elif loai == "nhom":
                gd.ve_bieu_tuong(c, "bang", 18, (y0 + y1) / 2, lh * 0.7, m["mo"])
                c.create_text(34, (y0 + y1) / 2, text=d or "(không nhóm)", anchor="w",
                              fill=m["mo"], font=f_nhom)
            elif loai == "preset":
                c.create_text(34, (y0 + y1) / 2, text=d.get("ten") or "?", anchor="w",
                              fill=m["nhan"] if chon else m["chu"], font=f)
            else:
                c.create_text(w / 2, (y0 + y1) / 2, anchor="center", fill=m["mo2"], font=f,
                              text=("Không có preset khớp." if self._tu_tim() else
                                    "Chưa có danh sách preset —\nmở Lightroom (plugin AutoTone) "
                                    "rồi bấm ⟳"), justify="center")
        c.configure(scrollregion=(0, 0, w, y + 4))

    def _hang_tai(self, y):
        y = self.c.canvasy(y)
        for i, (_l, _d, y0, y1) in enumerate(self._hang):
            if y0 <= y < y1:
                return i
        return None

    def _dat_re(self, i):
        if i != self._re_i:
            self._re_i = i
            self._ve_lai()

    def _re(self, e):
        self._dat_re(self._hang_tai(e.y))

    def _lan(self, e):
        if getattr(e, "num", None) == 4:
            d = -1
        elif getattr(e, "num", None) == 5:
            d = 1
        else:
            d = -1 if e.delta > 0 else 1
        self.c.yview_scroll(d * 3, "units")

    def _bam(self, e):
        i = self._hang_tai(e.y)
        if i is None:
            return
        loai, d, _y0, _y1 = self._hang[i]
        if loai == "khong":
            self.dp.chon(None)
        elif loai == "preset":
            self.dp.chon(dict(d))
        else:
            return
        self._ve_lai()
        self.cap_nhat_trang_thai()

    # ------------------------------------------------------------ trạng thái
    def cap_nhat_trang_thai(self):
        p = self.dp.p
        if p:
            self.lbl_chon.configure(text=f"Đã chọn: {p.get('ten')} · {p.get('nhom') or ''}",
                                    foreground=gd.MAU["chu"])
        else:
            self.lbl_chon.configure(text="Đã chọn: không áp preset — lưới hiện ảnh như "
                                         "hiện tại", foreground=gd.MAU["mo"])
        _c, phu, loai = self.dp.mo_ta()
        self.lbl_td.configure(text=phu or ("Mọi ảnh của buổi đã có bản theo preset." if p else
                                           "Chọn một preset: Lightroom render cả lưới theo "
                                           "preset đó (ảnh đang xem làm trước)."),
                              foreground=(gd.MAU["canh"] if loai == "loi" else gd.MAU["mo"]))
        chay = loai == "chay"
        self.btn_dung.configure(state="normal" if chay else "disabled")
        self.btn_lai.configure(state="normal" if (p and not chay) else "disabled")

    def _dung(self):
        self.dp.dung()
        self.cap_nhat_trang_thai()

    def _gui_lai(self):
        self.dp.loi = ""
        self.dp.gui()
        self.cap_nhat_trang_thai()
