"""Nút "Xử lý ảnh" — Phân tích → Áp vào Lightroom → (Denoise) → báo xong (13/10).

User 13/10: "Đưa quy trình Phân tích và Áp vào Lightroom thành 1 nút bấm Xử lý
ảnh. Khi bấm nút này sẽ tự động phân tích, khi phân tích xong tự áp vào
lightroom. Quy trình cần hiển thị tiến trình rõ ràng và thông báo bằng popup
khi chạy xong."

  · PHÂN TÍCH CHỈ ĐO ẢNH CHƯA CÓ KẾT QUẢ: kết quả đo lưu theo buổi
    (at.nap_ket_qua_do) — bấm lại sau khi kéo Bù sáng / K / Tint là áp ngay,
    không đo lại 1000 ảnh. Muốn đo lại cả buổi: ⋯ → "Phân tích lại cả buổi".
  · ÁP: không còn hộp hỏi giữa chừng — phạm vi ảnh Loại 1★ đặt sẵn trong
    Thiết lập › Lọc ảnh ("Áp cả ảnh Loại 1★ vào Lightroom").
  · XONG = LIGHTROOM ĐÃ ÁP (job .done + kiểm chứng), không phải lúc gửi job.
  · CURVE DA + NÉN CHÁY (tuỳ chọn, Thiết lập › Curve — 13/10): LƯỢT 2 sau khi áp —
    Lightroom dựng ảnh đã áp, app đo da từng điểm ảnh + vùng cháy, ghi job curve
    riêng (curve_da.py). Cần plugin mới (OTA không mang Lua).
  · DENOISE (tuỳ chọn, Thiết lập › Giảm nhiễu): yêu cầu RIÊNG sau khi áp xong —
    xem AutoTone.lrplugin/DenoiseCore.lua.

HopXuLy: cửa sổ tiến trình không chặn (đóng = chạy ngầm, thanh dưới vẫn báo);
xong thì chính nó hiện lại thành hộp tổng kết — "popup khi chạy xong".
"""
from __future__ import annotations

import os
import shutil
import threading
import time
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from datetime import datetime

import giao_dien as gd
import autotone as at

#[[ 14/10 (user: "vẫn giữ áp 2 lần để lấy được thông số của lần 1. Nhưng sẽ không hiển
#   thị ra bên ngoài"): lượt 2 (curve da mặt / vùng cháy) chạy NGẦM trong bước "Áp vào
#   Lightroom" — bước đó chỉ xong khi lượt 2 xong; không còn dòng Curve riêng. ]]
BUOC = (("do", "Phân tích ảnh"), ("ap", "Áp vào Lightroom"),
        ("denoise", "Denoise ảnh ISO cao"))
#  chờ yêu cầu Denoise được nhận tối đa bấy nhiêu giây (plugin cũ / Lightroom tắt)
CHO_DENOISE = 90
#  chờ Lightroom nhận yêu cầu dựng ảnh lượt 2 (curve) tối đa bấy nhiêu giây
CHO_CURVE = 90


#  bước của plugin lúc áp (AutoToneCore.applyJob ghi vào nhịp) -> khoảng % của thanh
_KHOANG_AP = (("dò ảnh", 0, 20), ("đọc thông số", 20, 40), ("ghi", 40, 90),
              ("kiểm chứng", 90, 100))


def _phan_tram_ap(buoc: str) -> float:
    """"ghi 200/1813" -> % của cả lượt áp (dò 0–20, đọc 20–40, ghi 40–90, kiểm 90–100)."""
    import re
    mt = re.search(r"(\d+)\s*/\s*(\d+)", buoc or "")
    for dau, lo, hi in _KHOANG_AP:
        if (buoc or "").startswith(dau):
            if mt:
                a, b = int(mt.group(1)), max(1, int(mt.group(2)))
                return lo + (hi - lo) * min(1.0, a / b)
            return lo
    return 0


def _thoi_gian(giay: float) -> str:
    giay = int(max(0, giay))
    if giay < 60:
        return f"{giay} giây"
    if giay < 3600:
        return f"{giay // 60} phút {giay % 60:02d} giây"
    return f"{giay // 3600} giờ {giay % 3600 // 60:02d} phút"


def _moc(xl: dict, ten: str) -> None:
    """Mốc thời gian (lần đầu) của một khâu trong lượt Xử lý ảnh — cả luồng nền ghi."""
    xl.setdefault("moc", {}).setdefault(ten, time.monotonic())


#: khâu -> (mốc đầu, mốc cuối) — 14/10: user "xử lý 1000 ảnh … tốn 15 phút": biết từng
#: khâu bao lâu thì mới biết sửa chỗ nào (ghi trang_thai "xu_ly" + dòng Thời gian)
KHAU_XL = (("do", "t0", "phan_tich"), ("truoc", "phan_tich", "truoc_xong"),
           ("tinh", "phan_tich", "gui"), ("ap", "gui", "ap"),
           ("l2_lr", "l2_gui", "l2_lr_xong"), ("l2_do", "l2_gui", "l2_do_xong"),
           ("l2_giai", "l2_do_xong", "l2_giai_xong"), ("l2_ap", "l2_giai_xong", "l2_ap"),
           ("hoan_thien", "ap", "l2_ap"), ("denoise", "denoise_gui", "denoise_xong"),
           ("tong", "t0", "het"))


def thoi_gian_khau(xl: dict) -> dict:
    """{khâu: giây} cho các khâu có đủ hai mốc."""
    moc = dict(xl.get("moc") or {}, t0=xl.get("t0"))
    if "l2_ap" not in moc and "l2_giai_xong" in moc:
        moc["l2_ap"] = moc.get("het")            # không có job curve: hoàn thiện tới lúc xong
    out = {}
    for ten, a, b in KHAU_XL:
        if moc.get(a) is not None and moc.get(b) is not None:
            out[ten] = round(max(0.0, moc[b] - moc[a]), 1)
    return out


def cau_thoi_gian(kh: dict) -> str:
    """"đo ảnh 1:05 · Lightroom áp 0:19 · hoàn thiện màu da 9:30 · Denoise 0:40"."""
    def mm(g):
        g = int(round(g))
        return f"{g // 60}:{g % 60:02d}"
    cau = [f"{chu} {mm(kh[k])}" for k, chu in (("do", "đo ảnh"), ("truoc", "đo da trên preview"),
                                              ("ap", "Lightroom áp"),
                                              ("hoan_thien", "hoàn thiện màu da"),
                                              ("denoise", "Denoise")) if k in kh]
    return " · ".join(cau)


class HopXuLy(tk.Toplevel):
    """Cửa sổ tiến trình của MỘT lượt Xử lý ảnh."""

    def __init__(self, app, co_denoise: bool, khi_dung, co_curve: bool = False,
                 buoc: tuple | None = None, tieu_de: str = "Xử lý ảnh",
                 dang: str = "Đang xử lý ảnh…"):
        #  15/10: buoc / tieu_de / dang — cửa sổ Học màu Lightroom (hoc_mau_ui) dùng chung
        super().__init__(app.winfo_toplevel())
        m = gd.MAU
        self.app = app
        self._khi_dung = khi_dung
        self.title(tieu_de)
        self.transient(app.winfo_toplevel())
        self.resizable(False, False)
        self.configure(background=m["nen"])
        self.protocol("WM_DELETE_WINDOW", self.an)
        self._t0 = time.monotonic()
        self._xong = False
        o = tk.Frame(self, background=m["nen"], padx=22, pady=18)
        o.pack(fill="both", expand=True)
        dau = tk.Frame(o, background=m["nen"])
        dau.pack(fill="x")
        self.lbl_tieu_de = tk.Label(dau, text=dang, background=m["nen"],
                                    foreground=m["chu"], font=gd.phong(13, "dam2"))
        self.lbl_tieu_de.pack(side="left")
        self.lbl_gio = tk.Label(dau, text="", background=m["nen"], foreground=m["mo"],
                                font=gd.phong(9, "so"))
        self.lbl_gio.pack(side="right")
        self.lbl_buoi = tk.Label(o, text="", background=m["nen"], foreground=m["mo"],
                                 font=gd.CHU_NHO, anchor="w")
        self.lbl_buoi.pack(fill="x", pady=(2, 12))
        #  các bước
        self.hang: dict = {}
        self.tt: dict = {}
        s = gd.don_vi(self) + 6
        for ma, ten in (buoc or BUOC):
            if ma == "denoise" and not co_denoise:
                continue
            h = tk.Frame(o, background=m["nen"])
            h.pack(fill="x", pady=4)
            cv = tk.Canvas(h, width=s, height=s, background=m["nen"], highlightthickness=0)
            cv.tu_cuon = False
            cv.pack(side="left", padx=(0, 10))
            l = tk.Label(h, text=ten, background=m["nen"], foreground=m["mo"],
                         font=gd.CHU_DAM, anchor="w")
            l.pack(side="left")
            ct = gd.NhanGon(h, text="", anchor="e", background=m["nen"],
                            foreground=m["mo"], font=gd.CHU_NHO)
            ct.pack(side="right", fill="x", expand=True, padx=(16, 0))
            self.hang[ma] = (cv, l, ct, s)
            self._ve_trang_thai(ma, "cho")
        #  thanh tiến độ của bước đang chạy
        self.thanh = gd.ThanhTienDo(o, cao=8, nen=m["nen"])
        self.thanh.pack(fill="x", pady=(14, 4))
        self.lbl_td = tk.Label(o, text="", background=m["nen"], foreground=m["mo"],
                               font=gd.phong(9, "so"), anchor="w")
        self.lbl_td.pack(fill="x")
        #  tổng kết (chỉ hiện khi xong)
        self.lbl_tong = tk.Label(o, text="", background=m["nen"], foreground=m["chu"],
                                 font=gd.CHU, justify="left", anchor="w", wraplength=460)
        #  nút
        self.day = tk.Frame(o, background=m["nen"])
        self.day.pack(fill="x", pady=(16, 0))
        self.btn_dung = gd.NutTron(self.day, "Dừng", kieu="phu", icon="dung",
                                   nen=m["nen"], command=self._dung)
        self.btn_dung.pack(side="right")
        self.btn_an = gd.NutTron(self.day, "Chạy ngầm", kieu="toi", nen=m["nen"],
                                 command=self.an)
        self.btn_an.pack(side="right", padx=(0, 8))
        self.btn_dong = gd.NutTron(self.day, "Đóng", kieu="chinh", nen=m["nen"],
                                   command=self.destroy)
        self.bind("<Escape>", lambda _e: self.an())
        self.minsize(520, 1)
        self._dat_cho()
        self._dong_ho()

    # ------------------------------------------------------------ hiển thị
    def _dat_cho(self):
        try:
            self.update_idletasks()
            cha = self.app.winfo_toplevel()
            x = cha.winfo_rootx() + (cha.winfo_width() - self.winfo_width()) // 2
            y = cha.winfo_rooty() + (cha.winfo_height() - self.winfo_height()) // 3
            self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        except tk.TclError:
            pass

    def _dong_ho(self):
        if self._xong:
            return
        try:
            self.lbl_gio.configure(text=_thoi_gian(time.monotonic() - self._t0))
            self.after(1000, self._dong_ho)
        except tk.TclError:
            pass

    def _ve_trang_thai(self, ma, tt):
        cv, l, _ct, s = self.hang[ma]
        m = gd.MAU
        cv.delete("all")
        r = s / 2 - 2
        cx = cy = s / 2
        if tt == "xong":
            cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=m["xong"], outline="")
            gd.ve_bieu_tuong(cv, "xong", cx, cy, s * 0.62, "#111214")
            l.configure(foreground=m["chu"])
        elif tt == "dang":
            cv.create_oval(cx - r, cy - r, cx + r, cy + r, outline=m["nhan"], width=2)
            cv.create_oval(cx - r * 0.42, cy - r * 0.42, cx + r * 0.42, cy + r * 0.42,
                           fill=m["nhan"], outline="")
            l.configure(foreground=m["nhan"])
        elif tt == "loi":
            cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=m["do"], outline="")
            gd.ve_bieu_tuong(cv, "dong", cx, cy, s * 0.56, "#111214")
            l.configure(foreground=m["do"])
        elif tt == "bo":
            cv.create_oval(cx - r, cy - r, cx + r, cy + r, outline=m["mo3"], width=1.5)
            cv.create_line(cx - r * 0.45, cy, cx + r * 0.45, cy, fill=m["mo2"], width=2)
            l.configure(foreground=m["mo2"])
        else:                                                   # chờ
            cv.create_oval(cx - r, cy - r, cx + r, cy + r, outline=m["mo3"], width=1.5)
            l.configure(foreground=m["mo"])

    def buoc(self, ma: str, tt: str, chi_tiet: str = ""):
        """Đặt trạng thái một bước: cho / dang / xong / loi / bo (bỏ qua)."""
        if ma not in self.hang:
            return
        self.tt[ma] = tt                    # trạng thái hiện tại của bước (bài kiểm đọc)
        try:
            self._ve_trang_thai(ma, tt)
            ct = self.hang[ma][2]
            ct.configure(text=chi_tiet, foreground={"loi": gd.MAU["do"], "xong": gd.MAU["mo"],
                                                   "dang": gd.MAU["chu"]}.get(tt, gd.MAU["mo"]))
            if tt == "dang":
                self.thanh.dat(0, 1)
                self.lbl_td.configure(text="")
        except tk.TclError:
            pass

    def tien_do(self, xong, tong, chu: str = ""):
        try:
            self.thanh.dat(xong, tong)
            self.lbl_td.configure(text=chu or (f"{gd.so_vn(xong)} / {gd.so_vn(tong)} ảnh"
                                               if tong else ""))
        except tk.TclError:
            pass

    def dat_buoi(self, chu: str):
        try:
            self.lbl_buoi.configure(text=chu)
        except tk.TclError:
            pass

    def an(self):
        """Đóng = chạy ngầm (đang chạy) / đóng hẳn (đã xong)."""
        if self._xong:
            self.destroy()
            return
        try:
            self.withdraw()
        except tk.TclError:
            pass

    def hien(self):
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except tk.TclError:
            pass

    def _dung(self):
        if self._khi_dung is not None:
            self._khi_dung()

    def ket_thuc(self, tieu_de: str, dong: list, loi: bool = False, nut: tuple | None = None):
        """Lượt xong (hoặc dừng / lỗi): hộp hiện lại thành bảng tổng kết + chuông.
        nut = (nhãn, lệnh): thêm một nút cạnh Đóng (bấm = đóng hộp rồi chạy lệnh)."""
        self._xong = True
        m = gd.MAU
        try:
            self.lbl_tieu_de.configure(text=tieu_de,
                                       foreground=m["do"] if loi else m["chu"])
            self.lbl_gio.configure(text=_thoi_gian(time.monotonic() - self._t0))
            self.thanh.pack_forget()
            self.lbl_td.pack_forget()
            self.lbl_tong.configure(text="\n".join(dong))
            self.lbl_tong.pack(fill="x", pady=(14, 0), before=self.day)
            self.btn_dung.pack_forget()
            self.btn_an.pack_forget()
            self.btn_dong.pack(side="right")
            if nut:
                def _lam(lenh=nut[1]):
                    self.destroy()
                    lenh()
                self.btn_them = gd.NutTron(self.day, nut[0], kieu="phu", nen=m["nen"],
                                           command=_lam)
                self.btn_them.pack(side="right", padx=(0, 8))
            self.bind("<Return>", lambda _e: self.destroy())
            self.hien()
            self.bell()
            self._dat_cho()
        except tk.TclError:
            pass


class XuLyAnhMixin:
    """Luồng nút Xử lý ảnh — gắn vào App (autotone_gui)."""

    # ------------------------------------------------------------ trạng thái
    def _xl_dang(self) -> bool:
        xl = getattr(self, "_xl", None)
        return bool(xl) and not xl.get("xong") and xl.get("hop") is not None

    def _xl_hop(self):
        xl = getattr(self, "_xl", None)
        return (xl or {}).get("hop")

    def xu_ly_anh(self):
        """Bấm “Xử lý ảnh”."""
        if self._khoa_chan() or self.busy or self._xl_dang():
            if self._xl_dang() and self._xl_hop() is not None:
                self._xl_hop().hien()
            return
        if self._hm_chan():                 # 15/10: đang học màu Lightroom (hoc_mau_ui)
            return
        if getattr(self, "_dang_cho_lr", False):
            self.status("Lần gửi trước Lightroom chưa áp xong — chờ nó, hoặc bấm “Huỷ gửi” "
                        "rồi bấm Xử lý ảnh lại.", gd.MAU["canh"])
            return
        self._xl = {"t0": time.monotonic(), "pha": "", "hop": None, "xong": False}
        self.start_analyze(chuoi=True, dung_kho=True)

    def _xl_bat_dau(self, so_do: int, so_kho: int, tong: int):
        """start_analyze đã chốt danh sách ảnh: mở hộp tiến trình."""
        xl = getattr(self, "_xl", None)
        if xl is None:
            return
        cfg = self.read_cfg()
        xl.update(pha="do", so_do=so_do, so_kho=so_kho, tong=tong,
                  denoise=bool(cfg.get("denoise")), denoise_iso=int(cfg.get("denoise_iso") or 2000),
                  curve=bool((cfg.get("curve_da") or cfg.get("curve_chay"))
                             and self.source_value() == "catalog"))
        hop = xl.get("hop")
        if hop is None:
            hop = xl["hop"] = HopXuLy(self, xl["denoise"], self._xl_dung, co_curve=xl["curve"])
        root = self.folder()
        hop.dat_buoi(f"Buổi {Path(str(root)).name if root else ''} · {gd.so_vn(tong)} ảnh")
        if so_do:
            hop.buoc("do", "dang", (f"đo {gd.so_vn(so_do)} ảnh mới · {gd.so_vn(so_kho)} ảnh "
                                    f"có kết quả" if so_kho else f"đo {gd.so_vn(so_do)} ảnh"))
            hop.tien_do(0, so_do)
        else:
            hop.buoc("do", "dang", f"{gd.so_vn(so_kho)} ảnh đã có kết quả — không đo lại")
        self._set_busy(self.busy)

    def _xl_cho_xuat_roi(self, ham, t0: float | None = None):
        """Mọi ảnh đã có kết quả đo: đợi bản xuất thông số Lightroom vừa xin (scan_folder
        -> _xin_xuat_nen) về — tối đa 20 giây — rồi mới tính kế hoạch (ham)."""
        t0 = t0 or time.monotonic()
        try:
            cho = self._dang_cho_xuat()[0] if self.source_value() == "catalog" else ""
        except Exception:                                    # noqa: BLE001
            cho = ""
        if cho and time.monotonic() - t0 < 20:
            if not self.busy:
                self._set_busy(True)
            hop = self._xl_hop()
            if hop is not None:
                hop.buoc("do", "dang", "chờ Lightroom gửi thông số hiện tại của ảnh…")
            self.after(500, lambda: self._xl_cho_xuat_roi(ham, t0))
            return
        if self.busy:
            self._set_busy(False)
        if self.cancel_flag and self._xl_dang():
            self._xl_hop().buoc("do", "loi", "đã dừng")
            self._xl_ket_thuc("dung", "Đã dừng — chưa áp gì vào Lightroom.")
            return
        ham()

    def _xl_tien_do(self, xong, tong):
        hop = self._xl_hop()
        if hop is not None and self._xl_dang():
            xl = self._xl
            con = ""
            if xong and tong and xong < tong:
                da = time.monotonic() - xl.setdefault("t_do", time.monotonic())
                if da > 3:
                    con = f" · còn ~{_thoi_gian(da / xong * (tong - xong))}"
            else:
                xl.setdefault("t_do", time.monotonic())
            hop.tien_do(xong, tong, f"{gd.so_vn(xong)} / {gd.so_vn(tong)} ảnh{con}")

    def _xl_dung(self):
        """Nút Dừng của hộp."""
        xl = getattr(self, "_xl", None)
        if not xl or xl.get("xong"):
            return
        pha = xl.get("pha")
        if pha == "do":
            self.do_cancel()
        elif pha == "truoc":
            xl["truoc_huy"] = True
        elif pha == "ap":
            if getattr(self, "_job_dang_theo", None) is not None and \
                    at.job_state(self._job_dang_theo) == "cho":
                self.huy_gui()
            else:
                self.status("Lightroom đang áp — không ngắt giữa chừng được.", gd.MAU["canh"])
        elif pha == "curve":
            #  đang dựng / đo: plugin chưa nhận thì rút yêu cầu, nhận rồi thì xin dừng sau lô
            xl["curve_huy"] = True
            import curve_da
            if curve_da.dang_cho():
                curve_da.rut_yeu_cau()
            else:
                curve_da.xin_dung()
            self._xl_ket_thuc("dung", "Đã dừng — WB / Tone đã áp vào Lightroom, phần hoàn thiện "
                                      "màu da chưa ghi.")
        elif pha == "curve_ap":
            job = xl.get("curve_job")
            if job is not None and at.job_state(job) == "cho":
                try:
                    Path(job).unlink()
                except OSError:
                    pass
                self._xl_ket_thuc("dung", "Đã dừng — WB / Tone đã áp vào Lightroom, phần hoàn "
                                          "thiện màu da chưa ghi.")
            else:
                self.status("Lightroom đang hoàn thiện — không ngắt giữa chừng được.",
                            gd.MAU["canh"])
        elif pha == "denoise":
            try:
                (Path(at.LR_JOB_DIR) / at.TEN_YC_DENOISE).unlink()
                self._xl_ket_thuc("dung", "Đã huỷ Denoise — Lightroom chưa nhận yêu cầu.")
                return
            except OSError:
                pass
            #  14/10: Lightroom nhận rồi -> xin plugin dừng ngay sau ảnh đang làm (trước
            #  đây chỉ báo "không ngắt được" và Lightroom chạy hết danh sách)
            ma = xl.get("denoise_ma") or ""
            try:
                at.dung_denoise(ma)
            except OSError as ex:
                self.status(f"Không gửi được lệnh dừng Denoise: {ex}", gd.MAU["do"])
                return
            td = at.tien_do_denoise(ma)
            xong, tong = td.get("xong") or 0, td.get("tong") or xl.get("denoise_tong") or 0
            hop = xl.get("hop")
            if hop is not None:
                hop.buoc("denoise", "bo", f"đã dừng — {gd.so_vn(xong)}/{gd.so_vn(tong)} ảnh")
            self._xl_ket_thuc("dung", f"Đã dừng Denoise — Lightroom không bật thêm ảnh nào "
                                      f"({gd.so_vn(xong)}/{gd.so_vn(tong)} ảnh đã bật trước khi "
                                      "dừng; Lightroom vẫn xử lý nốt các ảnh đó ở nền).")

    # ------------------------------------------------------------ các pha
    def _xl_sau_do(self, items, cfg) -> bool:
        """_on_analyzed xong lượt đo của Xử lý ảnh -> sang Áp. False = dừng chuỗi."""
        xl = getattr(self, "_xl", None)
        hop = self._xl_hop()
        if not xl or hop is None:
            return False
        if self.cancel_flag:
            hop.buoc("do", "loi", "đã dừng")
            self._xl_ket_thuc("dung", "Đã dừng giữa chừng — chưa áp gì vào Lightroom.")
            return False
        canh_bao = getattr(at, "CANH_BAO_XUAT", "") or getattr(at, "CANH_BAO_PLUGIN", "")
        if canh_bao and self.source_value() == "catalog":
            hop.buoc("do", "xong", f"{gd.so_vn(len(items))} ảnh")
            hop.buoc("ap", "loi", "dừng: số liệu Lightroom chưa dùng được")
            self._xl_ket_thuc("loi", canh_bao)
            return False
        if not self.items:
            #  15/10: plan() bỏ hết ảnh (vd. cả buổi khác số tool ghi -> "sửa tay") — nói rõ,
            #  không gửi job rỗng
            n_sua = int(getattr(at, "SO_ANH_NGUOI_SUA", 0) or 0)
            hop.buoc("do", "xong", "không còn ảnh nào để áp")
            hop.buoc("ap", "bo", "không có ảnh nào để áp")
            self._xl_ket_thuc("loi", (
                f"Cả {gd.so_vn(n_sua)} ảnh đều khác số tool ghi lần trước nên được coi là ảnh "
                "bạn đã sửa tay trong Lightroom — không áp gì. Nếu bạn vừa đặt lại cả buổi: "
                "đóng hộp thoại đang mở trong Lightroom (hoặc mở lại Lightroom) để plugin "
                "chạy lại, rồi bấm Xử lý ảnh." if n_sua else "Không còn ảnh nào để áp."))
            return False
        hop.buoc("do", "xong", f"{gd.so_vn(len(items))} ảnh"
                 + (f" · {gd.so_vn(len(self._do_hong))} ảnh không đo được"
                    if getattr(self, "_do_hong", None) else ""))
        _moc(xl, "phan_tich")
        if self._xl_bat_truoc(items, cfg):
            return True
        xl["pha"] = "ap"
        hop.buoc("ap", "dang", "đang gửi…")
        self.after(60, lambda: self.do_apply(hoi=False, tu_dong=True))
        return True

    # ------------------------------------------------------------ chuỗi một lượt (14/10)
    def _xl_bat_truoc(self, items, cfg) -> bool:
        """Chuỗi màu da MỘT LƯỢT (mau_mot_luot): bật + nguồn catalog + mẫu màu da + có mô
        hình Lightroom ĐẠT cho máy của buổi -> đo da trên preview Lightroom (cache / plugin)
        TRƯỚC khi áp, rồi tính lại kế hoạch. False = đi thẳng sang Áp như cũ."""
        xl = self._xl
        try:
            import mau_mot_luot as ml
        except ImportError:
            return False
        if not ml.bat(cfg) or self.source_value() != "catalog" \
                or not (cfg.get("mau_da_dich") or {}).get("trong"):
            return False
        ml.quen_mo_hinh()
        mat = [r for r in items if r.get("meter_boxes") and not r.get("bw")]
        may = {}
        for r in mat:
            may.setdefault(ml.khoa_cua(r), r)
        co = [k for k, r in may.items() if ml.mo_hinh_cho(r) is not None]
        #  15/10: máy đủ ảnh mà chưa có mô hình -> tổng kết có nút "Học màu máy này…"
        dem: dict = {}
        for r in mat:
            dem[ml.khoa_cua(r)] = dem.get(ml.khoa_cua(r), 0) + 1
        xl["ml_thieu"] = sorted(k for k in may if k not in co and dem.get(k, 0) >= 6)
        if not co:
            xl["truoc_kq"] = {"bo": "chua-hoc", "may": sorted({str(r.get("model") or "?")
                                                              for r in mat})}
            return False
        xl.update(pha="truoc", truoc_xong=False, truoc_huy=False, truoc_td=(0, len(mat), ""))
        hop = xl["hop"]
        hop.buoc("do", "dang", "đo da trên preview Lightroom…")
        hop.tien_do(0, max(1, len(mat)), "Đo da trên preview Lightroom…")
        root = self.folder()

        def chay():
            import do_truoc
            try:
                xl["truoc_kq"] = do_truoc.chay(
                    root, items, cfg, huy=lambda: bool(xl.get("truoc_huy") or self.cancel_flag),
                    bao=lambda x, t, c: xl.__setitem__("truoc_td", (x, t, c)))
            except Exception as ex:                          # noqa: BLE001
                xl["truoc_kq"] = {"bo": "loi", "ly_do": str(ex)}
            xl["truoc_xong"] = True
        threading.Thread(target=chay, daemon=True).start()
        self.after(400, self._xl_soi_truoc)
        return True

    def _xl_soi_truoc(self):
        xl = getattr(self, "_xl", None)
        if not xl or xl.get("xong") or xl.get("pha") != "truoc":
            return
        hop = xl["hop"]
        if not xl.get("truoc_xong"):
            x, t, c = xl.get("truoc_td") or (0, 1, "")
            hop.tien_do(x, max(1, t), (c or "Đo da trên preview Lightroom…")[:1].upper()
                        + (c or "Đo da trên preview Lightroom…")[1:])
            self.after(400, self._xl_soi_truoc)
            return
        _moc(xl, "truoc_xong")
        if xl.get("truoc_huy") or self.cancel_flag:
            hop.buoc("do", "loi", "đã dừng")
            self._xl_ket_thuc("dung", "Đã dừng — chưa áp gì vào Lightroom.")
            return
        kq = xl.get("truoc_kq") or {}
        #  kế hoạch tính lại với số đo trước -> cảnh đủ số đo đi chuỗi một lượt. 16/10: ở LUỒNG
        #  NỀN (refresh_plan_nen) — trên luồng giao diện từng đứng hình ~50 giây ("bị treo")
        hop.buoc("do", "dang", "tính màu da theo số đo trên preview…")
        hop.tien_do(0, 0, "Tính màu da theo số đo trên preview Lightroom…")
        self.refresh_plan_nen(lambda loi: self._xl_sau_tinh_lai(xl, kq, loi))

    def _xl_sau_tinh_lai(self, xl, kq, loi):
        if xl is not getattr(self, "_xl", None) or xl.get("xong"):
            return
        hop = xl["hop"]
        if loi:
            hop.buoc("do", "loi", "lỗi khi tính màu da")
            self._xl_ket_thuc("loi", "Lỗi khi tính màu da theo số đo trên preview:\n"
                              + str(loi).strip().splitlines()[-1])
            return
        if xl.get("truoc_huy") or self.cancel_flag:
            hop.buoc("do", "loi", "đã dừng")
            self._xl_ket_thuc("dung", "Đã dừng — chưa áp gì vào Lightroom.")
            return
        n_ml = sum(1 for r in self.items or [] if r.get("mot_luot"))
        xl["n_mot_luot"] = n_ml
        chu = f"{gd.so_vn(len(self.items or []))} ảnh"
        if kq.get("do"):
            chu += (f" · đo da trên preview {gd.so_vn(kq['do'])} ảnh"
                    + (f" ({gd.so_vn(kq.get('cache', 0))} từ cache Lightroom)" if kq.get("cache") else ""))
        hop.buoc("do", "xong", chu)
        xl["pha"] = "ap"
        hop.buoc("ap", "dang", "đang gửi…")
        self.after(60, lambda: self.do_apply(hoi=False, tu_dong=True))

    def _xl_ap_loi(self, ly_do: str):
        """do_apply(tu_dong) dừng trước khi gửi."""
        hop = self._xl_hop()
        if hop is not None and self._xl_dang():
            hop.buoc("ap", "loi", "không gửi")
            self._xl_ket_thuc("loi", ly_do)

    def _xl_da_gui(self, job, so_gui: int, items_ghi: list):
        """Đã ghi job (hoặc .xmp). job None = không có gì gửi Lightroom."""
        xl = getattr(self, "_xl", None)
        hop = self._xl_hop()
        if not xl or hop is None or xl.get("xong"):
            return
        xl["items_ghi"] = list(items_ghi)
        #  15/10: ảnh ám xanh nặng (WB cứu theo da) -> lượt 2 đo da thật hoàn thiện WB, kể cả
        #  khi curve da tắt (chỉ dựng / đo đúng các ảnh đó)
        xl["n_am_mau"] = (sum(1 for r in items_ghi if r.get("am_mau"))
                          if self.source_value() == "catalog" else 0)
        #  16/10: ảnh có mặt -> lượt 2 đo da thật, WB theo da HAI CHIỀU (at.wb_da_luot2), kể cả
        #  khi curve da tắt (chỉ dựng một ảnh mỗi loạt) — mọi buổi
        try:
            cfg_v = self.read_cfg()
            xl["wb_da_can"] = bool(at.wb_da_can(cfg_v)
                                   and any(at.wb_da_hop_le(r, cfg_v) for r in items_ghi))
        except Exception:                                    # noqa: BLE001
            xl["wb_da_can"] = False
        xl["so_gui"] = so_gui
        if job:
            xl["job"] = job
            _moc(xl, "gui")
            hop.buoc("ap", "dang", f"đã gửi {gd.so_vn(so_gui)} ảnh — chờ Lightroom nhận…")
            hop.tien_do(0, max(1, so_gui), "Chờ Lightroom nhận…")
            return
        if self.cfg.get("source") == "catalog":
            hop.buoc("ap", "loi", "không có ảnh nào để gửi")
            self._xl_ket_thuc("loi", "Không ảnh nào có thông số để gửi — xem dải báo phía "
                                     "trên lưới ảnh.")
            return
        hop.buoc("ap", "xong", f"đã ghi {gd.so_vn(so_gui)} file .xmp")
        if "denoise" in hop.hang:
            hop.buoc("denoise", "bo", "cần Lightroom (nguồn catalog)")
        self._xl_ket_thuc("xong")

    def _xl_job(self, job, st: str, chu: str = ""):
        """_watch_job báo trạng thái job của lượt Xử lý ảnh."""
        xl = getattr(self, "_xl", None)
        hop = self._xl_hop()
        if not xl or hop is None or xl.get("xong") or xl.get("job") != job:
            return
        if st == "cho":
            hop.buoc("ap", "dang", chu or "chờ Lightroom nhận…")
        elif st == "dang":
            hop.buoc("ap", "dang", "Lightroom đang áp")
            buoc = at.plugin_buoc() or ""
            hop.tien_do(_phan_tram_ap(buoc), 100,
                        f"Lightroom: {buoc}" if buoc else "Lightroom đang áp…")
        elif st == "huy":
            hop.buoc("ap", "loi", "đã huỷ gửi")
            self._xl_ket_thuc("dung", "Đã huỷ gửi — Lightroom chưa nhận gì.")
        elif st in ("xong", "mat"):
            _moc(xl, "ap")
            bad = at.job_unverified(job) if st == "xong" else []
            xl["chua_nhan"] = len(bad or [])
            ket = ("xong" if not bad else "loi",
                   f"Lightroom đã áp {gd.so_vn(xl.get('so_gui', 0))} ảnh"
                   + (f" · {len(bad)} ảnh chưa nhận đúng" if bad else " · kiểm chứng đủ"))
            if xl.get("curve") or xl.get("n_mot_luot") or xl.get("n_am_mau") or xl.get("wb_da_can"):
                xl["ap_ket"] = ket                 # chốt khi lượt 2 (ngầm) xong — _xl_chot_ap
                hop.buoc("ap", "dang", "Lightroom đã áp — đang hoàn thiện…")
            else:
                hop.buoc("ap", *ket)
                hop.tien_do(1, 1, "")
            self._da_ap_lr = True
            xl["chua_nhan_ds"] = {at.khoa_duong_dan(p) for p, _w in (bad or [])}
            if xl.get("n_mot_luot"):
                try:
                    import mau_mot_luot as ml
                    ml.luu_du_doan(xl.get("items_ghi") or [], self.folder(),   # cho KIEM_MOT_LUOT
                                   self.read_cfg())
                except Exception:                            # noqa: BLE001
                    pass
            self._xl_curve()

    # ------------------------------------------------------------ lượt 2: curve
    def _xl_curve(self):
        """Áp xong: Lightroom dựng ảnh đã áp -> đo da / vùng cháy -> job curve."""
        import curve_da
        xl = self._xl
        hop = xl.get("hop")
        if (not xl.get("curve") and not xl.get("n_mot_luot") and not xl.get("n_am_mau")
                and not xl.get("wb_da_can")):
            self._xl_denoise()
            return
        if curve_da.KHA_NANG not in at.plugin_kha_nang():
            xl["curve_kq"] = {"bo": "plugin-cu"}
            self._xl_denoise()
            return
        cfg = self.read_cfg()
        bo = xl.get("chua_nhan_ds") or set()
        ghi = [r for r in xl.get("items_ghi") or []
               if at.khoa_duong_dan(r.get("lr_path") or r["path"]) not in bo]
        #[[ 14/10 chuỗi MỘT LƯỢT: curve đã đi cùng job chính -> không dựng lại cả buổi;
        #   chỉ SOÁT (mau_mot_luot.chon_soat: một ảnh mỗi loạt + ảnh lẻ + ảnh ngoại suy),
        #   lệch dự đoán thì lượt 2 cho đúng loạt / cảnh đó (mau_mot_luot.soat). ]]
        ml_ds = [r for r in ghi if r.get("mot_luot") and r.get("du_doan_lr")]
        mau = []
        if ml_ds:
            import mau_mot_luot as ml
            mau = ml.chon_soat(ml_ds, cfg)
        ds = [r for r in curve_da.chon_anh([r for r in ghi if not r.get("mot_luot")], cfg)] \
            if xl.get("curve") else []
        ds += [r for r in mau if r not in ds]
        co_ds = {id(r) for r in ds}
        ds += [r for r in ghi if r.get("am_mau") and id(r) not in co_ds]   # 15/10: WB lượt 2
        #  16/10: WB theo da hai chiều — xét mọi ảnh có mặt; curve tắt thì dựng một ảnh / loạt
        xl["da_tat"] = [r for r in ghi if at.wb_da_hop_le(r, cfg)] if at.wb_da_can(cfg) else []
        co_ds = {id(r) for r in ds}
        ds += [r for r in at.chon_dai_dien_da(xl["da_tat"], cfg) if id(r) not in co_ds]
        xl["ml_ds"], xl["ml_mau"] = ml_ds, {id(r) for r in mau}
        #  14/10: lượt 2 theo cụm cùng khung tới cả ảnh một lượt KHÔNG đo (đo trước 2 ảnh / loạt)
        #  16/10: ảnh không có người không vào lượt 2 (user) — kể cả theo loạt của chuỗi một lượt
        xl["ml_tat"] = [r for r in ghi if r.get("mot_luot") and r.get("meter_boxes")]
        if not ds:
            xl["curve_kq"] = {"bo": "khong-anh"}
            self._xl_denoise()
            return
        root = self.folder()
        #  14/10: có mili-giây — lượt vừa Dừng và lượt mới trong CÙNG một giây từng dùng chung
        #  thư mục ảnh dựng, luồng của lượt cũ dọn mất ảnh của lượt mới
        ma = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        dest = curve_da.thu_muc_dung(root, ma)
        try:
            #  14/10 (user: "Tại sao k chỉ load lại Preview của Lightroom rồi can thiệp"):
            #  preview thay Export; vài ảnh xuất thật để soát preview còn tươi
            curve_da.yeu_cau_dung(root, ds, dest, ma, nguon="preview",
                                  kiem=curve_da.chon_kiem(ds))
            xl["curve_nguon"] = "preview"
        except OSError as ex:
            xl["curve_kq"] = {"bo": "loi", "ly_do": str(ex)}
            self._xl_denoise()
            return
        _moc(xl, "l2_gui")
        xl.update(pha="curve", curve_ma=ma, curve_ds=ds, curve_dest=dest, curve_do={},
                  curve_goc=root,
                  curve_cfg=cfg, curve_ten=Path(str(root)).name, t_curve=time.monotonic(),
                  curve_luong_xong=False, curve_huy=False)
        hop.buoc("ap", "dang", "Lightroom đã áp — đang hoàn thiện…")
        hop.tien_do(0, len(ds), "Hoàn thiện…")
        threading.Thread(target=self._xl_curve_luong, args=(xl,), daemon=True).start()
        self.after(1000, self._xl_soi_curve)

    @staticmethod
    def _xl_soat_tuoi(bang, kiem=None, xong=None):
        """Preview của các ảnh soát có khớp bản XUẤT THẬT không (curve_da.so_tuoi). Mặc
        định đọc bảng của lượt 2 (curve); preview lưới (xem_lr) truyền kiem / xong.
        None = chưa đủ ảnh để soát (đợi tiếp); True / False."""
        import curve_da
        if xong is None:
            xong = curve_da.tien_do().get("trang_thai") in ("xong", "dung", "loi")
        if kiem is None:
            kiem = curve_da.bang_anh(ten=curve_da.TEN_KIEM)
        if not kiem:
            #  plugin xuất ảnh soát TRƯỚC preview: nhóm preview đầu đã ra mà chưa có bảng
            #  soát = không xuất được ảnh nào để soát -> không có gì để so, tin preview
            return True if (xong or bang) else None
        pv = {at.khoa_duong_dan(p): j for p, j in bang}
        cap = [(pv.get(at.khoa_duong_dan(p)), j) for p, j in kiem]
        if any(a is None for a, _ in cap):
            if not xong:
                return None              # preview của ảnh soát chưa tới — đợi
            cap = [(a, b) for a, b in cap if a]
        kq = []
        for a, b in cap:
            try:
                kq.append(curve_da.so_tuoi(a, b)[0])
            except (OSError, ValueError):
                pass
        return all(kq) if kq else True

    @staticmethod
    def _xl_curve_luong(xl):
        """LUỒNG NỀN — không gọi Tk: đo từng ảnh Lightroom vừa dựng (lô nào xong đo lô
        đó), rồi giải + gom loạt + ghi job curve.

        #[[ 14/10: đo SONG SONG (curve_da.BoDo, nhiều tiến trình) — một luồng thì lượt 2
        #   buổi 2709 mất 18 phút trong khi Lightroom trả preview xong sau 9 phút. ]]"""
        import curve_da
        ds, cfg, ma = xl["curve_ds"], xl["curve_cfg"], xl["curve_ma"]
        tuoi = None                          # None: chưa soát / không cần; True / False
        theo = {}
        for r in ds:
            theo[at.khoa_duong_dan(r.get("lr_path") or r["path"])] = r
            theo.setdefault(at.khoa_duong_dan(r["path"]), r)
        da = set()
        td: dict = {}
        bo = None
        try:
            bo = curve_da.BoDo(cfg)
            xl["curve_tho"] = bo.n
            while not xl.get("curve_huy"):
                td = curve_da.tien_do()
                bang = curve_da.bang_anh() if td.get("ma") == ma else []
                #[[ 14/10 (user: "tool đứng im ở ảnh số 8"): đã XIN preview mà plugin chưa
                #   nói đang dựng bằng gì -> chưa đo (8 ảnh đầu từng bị đo trước khi soát). ]]
                if (xl.get("curve_nguon") == "preview" and not td.get("cach")
                        and td.get("trang_thai") not in ("xong", "dung", "loi")):
                    time.sleep(0.5)
                    continue
                #[[ 14/10: ảnh là PREVIEW -> soát vài tấm với bản xuất thật TRƯỚC khi đo.
                #   Preview cũ (chưa theo thông số vừa áp) -> xin dừng, gửi lại Export. ]]
                if td.get("cach") == "preview" and tuoi is None:
                    tuoi = XuLyAnhMixin._xl_soat_tuoi(bang)
                    if tuoi is None:
                        time.sleep(0.5)
                        continue
                    xl["curve_cach"] = "preview" if tuoi else "export (preview lệch)"
                    if not tuoi:
                        curve_da.xin_dung()
                        het = time.monotonic() + 120
                        while time.monotonic() < het and not xl.get("curve_huy"):
                            if curve_da.tien_do().get("trang_thai") in ("dung", "xong", "loi"):
                                break
                            time.sleep(0.5)
                        ma = datetime.now().strftime("%Y%m%d_%H%M%S") + "x"
                        xl["curve_ma"], xl["t_curve"] = ma, time.monotonic()
                        xl["curve_nguon"] = "export"
                        curve_da.yeu_cau_dung(xl["curve_goc"], ds, xl["curve_dest"], ma,
                                              nguon="export")
                        da.clear()
                        bo.bo()
                        xl["curve_do"].clear()
                        continue
                if td.get("cach") == "preview" and not tuoi:
                    time.sleep(0.5)
                    continue
                if bang:
                    _moc(xl, "l2_lr_dau")
                moi = [(p, j) for p, j in bang if p not in da]
                for p, j in moi:
                    if xl.get("curve_huy"):
                        break
                    da.add(p)
                    r = theo.get(at.khoa_duong_dan(p))
                    if r is None:
                        continue
                    bo.gui(id(r), r, j)
                for k, kq in bo.lay():
                    xl["curve_do"][k] = kq
                if td.get("ma") == ma and td.get("trang_thai") in ("xong", "dung", "loi"):
                    _moc(xl, "l2_lr_xong")
                    if bo.con() == 0 and all(p in da for p, _j in curve_da.bang_anh()):
                        break
                time.sleep(0.2 if bo.con() else 0.5)
            _moc(xl, "l2_do_xong")
            if not xl.get("curve_huy"):
                do_map = {k: v for k, v in xl["curve_do"].items()}
                mau_ids = xl.get("ml_mau") or set()
                #  15/10: ảnh ám xanh nặng -> WB bổ sung theo da đo THẬT trên ảnh Lightroom
                xl["am_mau_l2"] = at.wb_cuu_am_luot2(ds, do_map, cfg)
                #  16/10: da đo thật vàng / xanh quá -> WB lạnh / ấm theo da, cả loạt (mọi buổi)
                xl["wb_da_l2"] = at.wb_da_luot2(ds, do_map, cfg, tat_ca=xl.get("da_tat"))
                #  ảnh có WB lượt 2 (ám xanh / lệch da) KHÔNG giải curve — da đo dưới WB chưa hoàn
                #  thiện, WB lượt 2 sửa; curve nữa là sửa hai lần
                ds_cu = ([r for r in ds if id(r) not in mau_ids and not r.get("am_mau")
                          and not r.get("lech_da")] if xl.get("curve") else [])
                xl["curve_tt"] = curve_da.ket_thuc(ds_cu, {id(r): do_map[id(r)] for r in ds_cu
                                                           if id(r) in do_map}, cfg)
                #  14/10: ảnh liên tiếp cùng khung -> cùng curve lượt 2
                at.dong_bo_cum_luot2(ds_cu, cfg, khoa=("curve_ghi",))
                ghi_ds = list(ds_cu)
                co_ghi = {id(r) for r in ghi_ds}
                ghi_ds += [r for r in ds if r.get("wb_l2") and id(r) not in co_ghi]
                co_ghi = {id(r) for r in ghi_ds}
                ghi_ds += [r for r in xl.get("da_tat") or [] if r.get("wb_l2") and id(r) not in co_ghi]
                if xl.get("ml_ds"):
                    import mau_mot_luot as ml
                    xl["ml_soat"] = ml.soat(xl["ml_ds"], {k: do_map[k] for k in mau_ids
                                                         if k in do_map}, cfg,
                                            tat_ca=xl.get("ml_tat"))
                    ghi_ds += [r for r in xl["ml_soat"]["anh_sua"] if r not in ghi_ds]
                    ml.danh_dau_luot2(xl.get("curve_goc"), xl["ml_soat"]["anh_sua"])
                xl["curve_job"] = curve_da.ghi_job(ghi_ds, xl["curve_ten"])
                _moc(xl, "l2_giai_xong")
                if curve_da.giu_anh(cfg):                       # chạy cổng: giữ để so
                    curve_da.luu_ket_qua(xl["curve_dest"], ds, do_map, curve_da.bang_anh(),
                                         xl["curve_job"])
        except Exception as ex:                                   # noqa: BLE001
            xl["curve_loi"] = str(ex)
        finally:
            if bo is not None:
                bo.dong(huy=bool(xl.get("curve_huy")))
            xl["curve_td"] = td
            if not curve_da.giu_anh(cfg):
                shutil.rmtree(xl["curve_dest"], ignore_errors=True)
            xl["curve_luong_xong"] = True

    def _xl_soi_curve(self):
        import curve_da
        xl = getattr(self, "_xl", None)
        if not xl or xl.get("xong") or xl.get("pha") not in ("curve", "curve_ap"):
            return
        hop = xl["hop"]
        ds = xl["curve_ds"]
        if xl["pha"] == "curve_ap":
            st = at.job_state(xl["curve_job"])
            if st in ("xong", "mat"):
                _moc(xl, "l2_ap")
                bad = at.job_unverified(xl["curve_job"]) if st == "xong" else []
                tt = xl.get("curve_tt") or {}
                xl["curve_kq"] = dict(tt, chua_nhan=len(bad or []))
                self._xl_luu_bao_curve(ds)
                self._xl_denoise()
                return
            if st == "huy":
                self._xl_ket_thuc("dung", "Đã dừng — WB / Tone đã áp vào Lightroom, phần hoàn "
                                          "thiện màu da chưa ghi.")
                return
            hop.buoc("ap", "dang", "Lightroom đã áp — đang hoàn thiện…")
            self.after(1000, self._xl_soi_curve)
            return
        if xl.get("curve_luong_xong"):
            if xl.get("curve_loi"):
                xl["curve_kq"] = {"bo": "loi", "ly_do": xl["curve_loi"]}
                self._xl_denoise()
                return
            tt = xl.get("curve_tt") or {}
            td = xl.get("curve_td") or {}
            if td.get("trang_thai") == "loi" and not tt.get("do"):
                xl["curve_kq"] = {"bo": "loi", "ly_do": td.get("thong_bao") or ""}
                self._xl_denoise()
                return
            if xl.get("curve_job") is None:
                xl["curve_kq"] = dict(tt)
                self._xl_luu_bao_curve(ds)
                self._xl_denoise()
                return
            xl["pha"] = "curve_ap"
            hop.buoc("ap", "dang", "Lightroom đã áp — đang hoàn thiện…")
            self.after(1000, self._xl_soi_curve)
            return
        td = curve_da.tien_do()
        n_do = len(xl["curve_do"])
        if td.get("ma") == xl["curve_ma"]:
            lr = int(td.get("xong") or 0)
            if lr > n_do + 8:
                #  đo còn chờ (soát preview / máy bận): nói Lightroom đã trả tới đâu
                hop.tien_do(n_do + lr, 2 * len(ds),
                            f"Hoàn thiện {gd.so_vn(n_do)} / {gd.so_vn(len(ds))} ảnh · "
                            f"Lightroom đã dựng {gd.so_vn(lr)}")
            else:
                hop.tien_do(n_do, len(ds),
                            f"Hoàn thiện {gd.so_vn(n_do)} / {gd.so_vn(len(ds))} ảnh")
        elif curve_da.dang_cho() and time.monotonic() - xl["t_curve"] > CHO_CURVE:
            curve_da.rut_yeu_cau()
            xl["curve_huy"] = True
            xl["curve_kq"] = {"bo": "khong-nhan"}
            self._xl_denoise()
            return
        self.after(1000, self._xl_soi_curve)

    @staticmethod
    def _xl_cau_curve(tt: dict) -> str:
        if not tt.get("do"):
            return "không đo được ảnh nào"
        cau = [f"đo {gd.so_vn(tt['do'])} ảnh"]
        if tt.get("da"):
            cau.append(f"chỉnh da {gd.so_vn(tt['da'])}")
        if tt.get("chay"):
            cau.append(f"nén cháy {gd.so_vn(tt['chay'])}")
        if not tt.get("doi"):
            cau.append("không ảnh nào cần đổi curve")
        return " · ".join(cau)

    def _xl_luu_bao_curve(self, ds):
        """Báo cáo curve từng ảnh -> bảng Chi tiết ảnh (giữ qua các lần tính lại kế hoạch)."""
        bao = getattr(self, "_curve_bao", None)
        if bao is None:
            bao = self._curve_bao = {}
        for r in ds:
            if r.get("curve_bao"):
                bao[at.khoa_duong_dan(r["path"])] = r["curve_bao"]

    def _xl_chot_ap(self):
        """Lượt 2 (ngầm) xong / dừng: bước "Áp vào Lightroom" mới xong — chữ của lượt 1,
        cộng ảnh Lightroom chưa nhận curve (nếu có)."""
        xl = getattr(self, "_xl", None)
        ket = xl.pop("ap_ket", None) if xl else None
        hop = xl.get("hop") if xl else None
        if not ket or hop is None:
            return
        tt, chu = ket
        n = int((xl.get("curve_kq") or {}).get("chua_nhan") or 0)
        if n:
            tt, chu = "loi", chu + f" · {n} ảnh chưa nhận đủ"
        hop.buoc("ap", tt, chu)
        hop.tien_do(1, 1, "")

    def _xl_denoise(self):
        xl = self._xl
        hop = xl.get("hop")
        self._xl_chot_ap()
        if "denoise" not in hop.hang:
            self._xl_ket_thuc("xong")
            return
        cfg = self.read_cfg()
        ds = at.anh_can_denoise(xl.get("items_ghi") or [], cfg)
        xl["denoise_tong"] = len(ds)
        if not ds:
            hop.buoc("denoise", "bo", f"không ảnh nào ISO ≥ {int(cfg.get('denoise_iso') or 2000)}")
            self._xl_ket_thuc("xong")
            return
        ma = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            at.yeu_cau_denoise(ds, ma)
        except OSError as ex:
            hop.buoc("denoise", "loi", "không gửi được yêu cầu")
            self._xl_ket_thuc("loi", f"Không gửi được yêu cầu Denoise: {ex}")
            return
        xl.update(pha="denoise", denoise_ma=ma, t_denoise=time.monotonic())
        _moc(xl, "denoise_gui")
        hop.buoc("denoise", "dang", f"{gd.so_vn(len(ds))} ảnh ISO ≥ "
                                    f"{int(cfg.get('denoise_iso') or 2000)} — chờ Lightroom nhận…")
        hop.tien_do(0, len(ds), "Chờ Lightroom nhận…")
        self.after(1000, self._xl_soi_denoise)

    def _xl_soi_denoise(self):
        xl = getattr(self, "_xl", None)
        if not xl or xl.get("xong") or xl.get("pha") != "denoise":
            return
        hop = xl["hop"]
        td = at.tien_do_denoise(xl["denoise_ma"])
        kq = td.get("ket_qua")
        if kq is not None:
            def so(k):
                try:
                    return int(float(kq.get(k) or 0))
                except ValueError:
                    return 0
            xl["denoise_kq"] = kq
            _moc(xl, "denoise_xong")
            if kq.get("ly_do") == "lightroom-chua-ho-tro":
                hop.buoc("denoise", "loi", "Lightroom này chưa hỗ trợ (cần 14.4+)")
            else:
                bat, co, kht, loi = so("bat"), so("da_co"), so("khong_ho_tro"), so("loi")
                hop.buoc("denoise", "xong" if not loi else "loi",
                         (f"gom 1 lệnh: {gd.so_vn(bat)} ảnh" if so("lo") else
                          f"bật {gd.so_vn(bat)} ảnh")
                         + (f" · {co} ảnh đã có" if co else "")
                         + (f" · {kht} ảnh không hỗ trợ" if kht else "")
                         + (f" · {loi} lỗi" if loi else ""))
                hop.tien_do(1, 1, "")
            self._xl_ket_thuc("xong")
            return
        if td.get("tong"):
            hop.buoc("denoise", "dang", "Lightroom đang bật Denoise (module Develop)")
            hop.tien_do(td["xong"], td["tong"],
                        f"Denoise {gd.so_vn(td['xong'])} / {gd.so_vn(td['tong'])} ảnh")
        elif td.get("cho") and time.monotonic() - xl["t_denoise"] > CHO_DENOISE:
            #  plugin cũ (chưa có DenoiseCore) / Lightroom tắt: rút yêu cầu, đừng để nó
            #  chạy bất ngờ lúc Lightroom mở lại
            try:
                (Path(at.LR_JOB_DIR) / at.TEN_YC_DENOISE).unlink()
            except OSError:
                pass
            hop.buoc("denoise", "loi", "Lightroom chưa nhận yêu cầu")
            self._xl_ket_thuc("loi", "Lightroom không nhận yêu cầu Denoise sau "
                                     f"{CHO_DENOISE} giây — plugin trong Lightroom là bản cũ? "
                                     "Tắt / mở lại Lightroom rồi bấm Xử lý ảnh lần nữa "
                                     "(ảnh đã áp không áp lại, chỉ Denoise).")
            return
        self.after(1000, self._xl_soi_denoise)

    @staticmethod
    def _xl_tong_ket_curve(cv: dict) -> str:
        """14/10: lượt 2 chạy ngầm — tổng kết CHỈ nói khi nó hỏng (cần người dùng làm gì).
        Số liệu từng ảnh vẫn ở bảng Chi tiết ảnh (_dong_curve)."""
        bo = cv.get("bo")
        if bo == "plugin-cu":
            return ("⚠ Màu da chưa hoàn thiện: plugin trong Lightroom là bản cũ — cài lại "
                    "AutoTone (bản đầy đủ, cập nhật OTA không mang plugin) rồi khởi động lại "
                    "Lightroom.")
        if bo == "khong-nhan":
            return (f"⚠ Màu da chưa hoàn thiện: Lightroom không dựng ảnh sau {CHO_CURVE} giây.")
        if bo == "loi":
            return f"⚠ Màu da chưa hoàn thiện: lỗi — {cv.get('ly_do') or 'xem nhật ký'}."
        if cv.get("chua_nhan"):
            return f"⚠ {cv['chua_nhan']} ảnh Lightroom chưa nhận phần hoàn thiện màu da."
        return ""

    @staticmethod
    def _xl_tong_ket_curve_chi_tiet(cv: dict) -> str:
        """Câu đầy đủ (bài kiểm / nhật ký) — không hiện trong hộp từ 14/10."""
        bo = cv.get("bo")
        if bo == "khong-anh":
            return "· Curve: không ảnh nào cần đo."
        mn = cv.get("mat_na") or {}
        cau = (f"· Curve: chỉnh da {gd.so_vn(cv.get('da', 0))} ảnh, nén cháy "
               f"{gd.so_vn(cv.get('chay', 0))} ảnh / {gd.so_vn(cv.get('do', 0))} ảnh đo")
        if cv.get("da_on"):
            cau += f" · {gd.so_vn(cv['da_on'])} ảnh da đã đúng đích"
        if cv.get("chan_trang"):
            cau += f" · {gd.so_vn(cv['chan_trang'])} ảnh thu bớt để vùng trắng không ám"
        if mn.get("du_phong") and not mn.get("parse"):
            cau += " · mặt nạ da DỰ PHÒNG (máy chưa có mô hình phân vùng mặt)"
        if cv.get("chua_nhan"):
            cau += f" · ⚠ {cv['chua_nhan']} ảnh Lightroom chưa nhận curve"
        return cau + "."

    # ------------------------------------------------------------ preview Lightroom (14/10)
    def _xem_lr_bat_dau(self, xl) -> bool:
        """User 14/10: "oke làm luôn hiện preview" — áp xong thì lưới / ảnh lớn của tool hiện
        PREVIEW LIGHTROOM (xem_lr). Nhờ plugin lấy preview các ảnh vừa áp (CHỈ preview, có
        ảnh soát tươi); False khi plugin cũ / không có gì để lấy."""
        import curve_da
        import xem_lr
        if xem_lr.KHA_NANG not in at.plugin_kha_nang():
            return False
        bo = xl.get("chua_nhan_ds") or set()
        items = [r for r in (xl.get("items_ghi") or [])
                 if at.khoa_duong_dan(r.get("lr_path") or r["path"]) not in bo]
        if not items:
            return False
        ap = {}
        for r in items:
            ve = (r.get("new_exposure"), r.get("new_temp"), r.get("new_tint"))
            for p in {r.get("lr_path") or r["path"], r["path"]}:
                ap[at.khoa_duong_dan(p)] = ve
        ma = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            xem_lr.yeu_cau(self.folder(), [r.get("lr_path") or r["path"] for r in items], ma,
                           kiem=curve_da.chon_kiem(items))
        except OSError:
            return False
        self._xem_lr_luot = {"ma": ma, "ap": ap, "da": set(), "tuoi": None,
                             "t0": time.monotonic(), "n": 0}
        self.after(1500, self._xem_lr_soi)
        return True

    def _xem_lr_soi(self):
        import curve_da
        import xem_lr
        lt = getattr(self, "_xem_lr_luot", None)
        if not lt:
            return
        td = xem_lr.tien_do()
        if td.get("ma") != lt["ma"]:
            if xem_lr.dang_cho() and time.monotonic() - lt["t0"] > CHO_CURVE * 2:
                xem_lr.rut_yeu_cau()             # Lightroom tắt / plugin cũ: thôi
                self._xem_lr_luot = None
                return
            self.after(1500, self._xem_lr_soi)
            return
        xong = td.get("trang_thai") in ("xong", "dung", "loi")
        bang = xem_lr.bang_anh()
        if lt["tuoi"] is None and td.get("cach") == "preview":
            lt["tuoi"] = XuLyAnhMixin._xl_soat_tuoi(
                bang, kiem=xem_lr.bang_anh(xem_lr.TEN_KIEM), xong=xong)
            if lt["tuoi"] is False:
                xem_lr.xin_dung()
                self.status("Lightroom chưa cập nhật preview sau khi áp — lưới giữ ảnh của tool.",
                            gd.MAU["mo"])
                self._xem_lr_luot = None
                self.after(5000, lambda: xem_lr.don_tam(lt["ma"]))
                return
        if lt["tuoi"]:
            moi = [(p, j) for p, j in bang if p not in lt["da"]]
            if moi:
                da = xem_lr.nhan(moi, lt["ap"])
                lt["da"].update(p for p, _j in moi)
                lt["n"] += len(da)
                if da:
                    theo = {at.khoa_duong_dan(o["path"]): o["path"] for o in self.luoi.ds}
                    self.luoi.lam_moi_anh([theo[at.khoa_duong_dan(p)] for p in da
                                           if at.khoa_duong_dan(p) in theo])
                    self._cap_nhat_luoi(giu_cuon=True)      # mô phỏng: chỉ phần đổi sau khi áp
                    if getattr(self, "_che_do_ct", "luoi") == "mot" and self._anh_ct:
                        self._nap_mot_ct(self._anh_ct, giu_khung=True)
        if xong and (lt["tuoi"] is not None or td.get("cach") != "preview"):
            if lt["n"]:
                self.status(f"Lưới đã hiện preview Lightroom ({gd.so_vn(lt['n'])} ảnh).",
                            gd.MAU["xong"])
            self._xem_lr_luot = None
            xem_lr.don_tam(lt["ma"])
            return
        self.after(1500, self._xem_lr_soi)

    def _xl_cau_mot_luot(self, xl) -> str:
        """Dòng tổng kết chuỗi một lượt (+ ghi lịch sử lệch dự đoán)."""
        tk = xl.get("truoc_kq") or {}
        if tk.get("bo") == "chua-hoc":
            return ("· Màu da một lượt: chưa học màu Lightroom cho máy "
                    f"{', '.join(tk.get('may') or [])} — lần này dùng đường thường. Học: "
                    "⋯ › Học màu Lightroom cho máy ảnh này…")
        n = int(xl.get("n_mot_luot") or 0)
        if not n:
            return ""
        sa = xl.get("ml_soat") or {}
        cau = f"· Màu da một lượt: {gd.so_vn(n)} ảnh"
        if sa.get("n"):
            cau += (f" · soát {gd.so_vn(sa['n'])} ảnh, lệch dự đoán trung vị {sa['hue']:.1f}° / "
                    f"{sa['q'] * 100:.0f}%")
            if sa.get("sua"):
                cau += f" · {gd.so_vn(sa['sua'])} ảnh hoàn thiện thêm (lượt 2)"
            elif sa.get("lech"):
                cau += (f" · {gd.so_vn(sa['lech'])} ảnh lệch (bật Curve da để tự hoàn thiện)"
                        if sa.get("can") else f" · {gd.so_vn(sa['lech'])} ảnh lệch (Curve không chỉnh thêm được)")
            if sa.get("ca_buoi"):
                cau += (" · ⚠ lệch nhiều cả buổi — nên học màu Lightroom lại (⋯ › Học màu "
                        "Lightroom cho máy ảnh này…)")
            if not xl.get("ml_lich_su"):
                xl["ml_lich_su"] = True
                try:
                    import mau_mot_luot as ml
                    import trang_thai as tt
                    ml.ghi_lich_su(sa, tt.ten_buoi(self.folder()))
                except Exception:                            # noqa: BLE001
                    pass
        return cau + "."

    # ------------------------------------------------------------ kết thúc
    def _xl_ghi_thoi_gian(self, xl, kieu: str, kh: dict) -> None:
        """Thời gian từng khâu -> trang_thai (khâu "xu_ly") — so buổi này với buổi trước."""
        try:
            import trang_thai as tt
            root = self.folder()
            if not root or not kh.get("tong"):
                return
            tt.ghi_khau(tt.ten_buoi(root), "xu_ly", kh["tong"], ket=kieu,
                        so_anh=len(xl.get("items_ghi") or []),
                        so_hoan_thien=len(xl.get("curve_ds") or []),
                        tho=xl.get("curve_tho"), cach=xl.get("curve_cach") or xl.get("curve_nguon"),
                        chi_tiet=kh)
        except Exception:                                    # noqa: BLE001
            pass                                             # đo giờ không đáng để hỏng lượt

    def _xl_ket_thuc(self, kieu: str, ly_do: str = ""):
        """kieu: xong / dung / loi -> hộp tổng kết."""
        xl = getattr(self, "_xl", None)
        if not xl or xl.get("xong"):
            return
        self._xl_chot_ap()                  # dừng giữa lượt 2: bước Áp (lượt 1) vẫn đã xong
        xl["xong"] = True
        hop = xl.get("hop")
        _moc(xl, "het")
        giay = time.monotonic() - xl["t0"]
        kh = thoi_gian_khau(xl)
        self._xl_ghi_thoi_gian(xl, kieu, kh)
        dong = []
        if kieu == "xong":
            items = xl.get("items_ghi") or []
            n_loai = sum(1 for r in items if self._nhan_cua(r) == "loai")
            n_doi = sum(1 for r in items if r.get("delta_ev") or r.get("hl_adj") or r.get("sh_adj"))
            dong.append(f"✓ {gd.so_vn(xl.get('so_gui', len(items)))} ảnh đã áp vào Lightroom "
                        f"({gd.so_vn(n_doi)} ảnh đổi sáng)."
                        if self.cfg.get("source") == "catalog" else
                        f"✓ Đã ghi {gd.so_vn(xl.get('so_gui', len(items)))} file .xmp.")
            if xl.get("credit_cau"):
                dong.append(f"· {xl['credit_cau']}.")          # 13/10: credit của lượt
            if n_loai:
                dong.append(f"· {gd.so_vn(n_loai)} ảnh Loại đã gắn 1★ trong Lightroom.")
            elif not self.read_cfg().get("ap_anh_loai", True):
                n_bo = sum(1 for r in self.items or [] if self._nhan_cua(r) == "loai")
                if n_bo:
                    dong.append(f"· {gd.so_vn(n_bo)} ảnh Loại KHÔNG áp (chỉ áp ảnh Giữ).")
            if xl.get("chua_nhan"):
                dong.append(f"⚠ {xl['chua_nhan']} ảnh Lightroom chưa nhận đúng — bấm dòng trạng "
                            "thái trên thanh trên để xem.")
            #  15/10 (user: "Các thông báo hiển thị ngắn gọn. Các thay đổi chi tiết bỏ đi"):
            #  curve / một lượt / chủ thể / cụm / ám xanh chỉ hiện ở bản dev (mã nguồn)
            import duong_dan as dd
            chi_tiet = not dd.dong_goi()
            cv = xl.get("curve_kq") if chi_tiet else None
            if cv is not None and self._xl_tong_ket_curve(cv):
                dong.append(self._xl_tong_ket_curve(cv))
            cau_ml = self._xl_cau_mot_luot(xl)
            if cau_ml and chi_tiet:
                dong.append(cau_ml)
            #  15/10: ảnh liền nhau cùng khung mà ánh sáng THẬT lệch (flash không kịp hồi…) —
            #  autotone.dong_bo_cum / mau_mot_luot.can_sang_cum bù Exposure riêng
            #  15/10: chủ thể chính (autotone.gan_chu_the)
            ct = dict(getattr(at, "CHU_THE", {}) or {}) if chi_tiet else {}
            if ct.get("nguoi"):
                dong.append(f"· Chủ thể chính: {len(ct['nguoi'])} người xuất hiện nhiều nhất ("
                            + " · ".join(gd.so_vn(p["n_anh"]) for p in ct["nguoi"])
                            + f" ảnh) — đo sáng + màu da theo mặt họ ở {gd.so_vn(ct.get('anh', 0))} ảnh.")
            bu = [r for r in xl.get("items_ghi") or [] if r.get("bu_cum_ev")]
            if bu and chi_tiet:
                dong.append(f"· Ảnh liền nhau cùng khung: {gd.so_vn(len(bu))} ảnh ánh sáng thật lệch "
                            "(flash không kịp hồi…) được bù sáng riêng cho đều với cả loạt.")
            #  15/10: ảnh ám xanh nặng — WB chỉnh theo da (autotone.cuu_am_mau / wb_cuu_am_luot2)
            av = [r for r in xl.get("items_ghi") or [] if r.get("lech_da") and r.get("wb_l2")]
            if av and chi_tiet:
                n_l = sum(1 for r in av if r["lech_da"] > 0)
                dong.append(f"· WB theo da đo trên ảnh Lightroom: {gd.so_vn(n_l)} ảnh da vàng -> lạnh đi, "
                            f"{gd.so_vn(len(av) - n_l)} ảnh da xanh -> ấm lên.")
            am = [r for r in xl.get("items_ghi") or [] if r.get("am_mau")]
            if am and chi_tiet:
                wbs = sorted({int(r["am_mau_wb"][0]) for r in am if r.get("am_mau_wb")})
                l2 = sum(1 for r in am if r.get("wb_l2"))
                dong.append(f"· Ảnh ám xanh nặng (ngoài trời, da xanh hơn đích): {gd.so_vn(len(am))} ảnh — "
                            "WB chỉnh theo da"
                            + (f" ({wbs[0]}–{wbs[-1]} K)" if len(wbs) > 1 else (f" ({wbs[0]} K)" if wbs else ""))
                            + (f", {gd.so_vn(l2)} ảnh hoàn thiện theo da đo trên ảnh Lightroom." if l2 else "."))
            kq = xl.get("denoise_kq")
            if kq is not None and kq.get("ly_do") != "lightroom-chua-ho-tro":
                dong.append(f"· Denoise: bật {kq.get('bat', 0)} ảnh ISO ≥ "
                            f"{int(xl.get('denoise_iso') or 2000)} — Lightroom xử lý nền, xem "
                            "tiến độ ở góc trên bên trái Lightroom.")
                #  14/10: gom 1 lệnh chỉ được khi Develop bật Auto Sync — chưa thì nhắc
                if kq.get("lo") != "1" and int(float(kq.get("bat") or 0)) >= 2:
                    dong.append("  Mẹo: bật Auto Sync trong Develop (công tắc cạnh nút Sync) để "
                                "Lightroom Denoise cả danh sách trong một tác vụ, không phải "
                                "chọn từng ảnh.")
            elif kq is not None:
                dong.append("⚠ Denoise: Lightroom này chưa cho bật Denoise qua plugin "
                            "(cần Lightroom Classic 14.4 trở lên).")
            if self.source_value() == "catalog":
                dong.append("Không cần Read Metadata from File — sang Develop là thấy.")
                if self._xem_lr_bat_dau(xl) and chi_tiet:
                    dong.append("· Lưới đang đổi sang preview Lightroom (giống hệt Lightroom).")
            tieu_de = "Xử lý xong"
            self.status(f"✓ Xử lý xong · {_thoi_gian(giay)}", gd.MAU["xong"])
        elif kieu == "dung":
            tieu_de = "Đã dừng"
            dong.append(ly_do or "Đã dừng.")
        else:
            tieu_de = "Chưa xử lý xong"
            dong.append(ly_do or "Có lỗi — xem dòng trạng thái.")
        dong.append(f"\nThời gian: {_thoi_gian(giay)}"
                    + (f" ({cau_thoi_gian(kh)})" if kieu == "xong" and cau_thoi_gian(kh) else ""))
        nut = None
        if kieu == "xong" and xl.get("ml_thieu"):
            thieu = list(xl["ml_thieu"])
            nut = ("Học màu máy này…", lambda: self.hoc_mau_lr(khoa_ds=thieu))
        if hop is not None:
            hop.ket_thuc(tieu_de, dong, loi=(kieu == "loi"), nut=nut)
        try:
            self._set_busy(self.busy)
            self._lam_moi_buoc()
        except Exception:                                    # noqa: BLE001
            pass
