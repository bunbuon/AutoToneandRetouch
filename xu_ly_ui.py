#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xu_ly_ui.py — Trang 5 · “Xử lý & xuất” (giao diện mới 12/10).

VÌ SAO CÓ TRANG NÀY
    Bản thiết kế "SAY Auto Tone & Retouch — UI mới" (trang 3): một chỗ nhìn
    lượt đang chạy — số ảnh lớn, thanh tiến độ, giây mỗi ảnh, còn bao lâu, thư
    mục ra; các bước của cả buổi (đo → áp Lightroom → Lightroom xuất →
    retouch); phần cứng + chế độ chạy; nhật ký; "Báo khi xong".

    Trước đây tiến độ Xuất + Retouch chỉ là một dòng chữ ở thanh trạng thái.

NGUỒN SỐ LIỆU (chỉ ĐỌC, không tự chạy việc gì)
    · Phân tích / ghi: App.busy + App.pb (value / maximum) + App.lbl_tien3.
    · Lightroom xuất: xuat_lr.tien_do_xuat() (file nhịp plugin ghi).
    · Retouch: RetouchWindow — worker, pb_tt, _chu_tt_chay, txt (nhật ký),
      v_che_do (Tự động / Tiết kiệm / Nhanh — đúng ba chế độ của saytool).
    Mỗi giây đọc lại một lần khi trang đang hiện (và theo vòng 4 giây của App
    để thanh 5 bước biết đang chạy gì).
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
import threading
import time
import tkinter as tk
import traceback
from pathlib import Path

import giao_dien as gd

_PHAN_CUNG: dict = {}


def _doc_phan_cung() -> dict:
    """GPU / CPU / RAM — đọc MỘT lần (nvidia-smi có thể mất cả giây)."""
    if _PHAN_CUNG:
        return _PHAN_CUNG
    tt = {"gpu": "", "cpu": "", "ram": ""}
    try:
        kw = {}
        if sys.platform == "win32":
            kw["creationflags"] = 0x08000000                 # CREATE_NO_WINDOW
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total",
                            "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=6, **kw)
        dong = (r.stdout or "").strip().splitlines()
        if r.returncode == 0 and dong:
            ten, _sep, mb = dong[0].partition(",")
            ten = ten.replace("NVIDIA GeForce ", "").replace("NVIDIA ", "").strip()
            try:
                tt["gpu"] = f"{ten} · {float(mb) / 1024:.1f} GB".replace(".", ",")
            except ValueError:
                tt["gpu"] = ten
    except Exception:                                        # noqa: BLE001
        pass
    if not tt["gpu"] and sys.platform == "darwin":
        try:
            r = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                               capture_output=True, text=True, timeout=4)
            tt["gpu"] = (r.stdout or "").strip() or "GPU tích hợp"
        except Exception:                                    # noqa: BLE001
            tt["gpu"] = "GPU tích hợp"
    tt["gpu"] = tt["gpu"] or "Không thấy card NVIDIA"
    tt["cpu"] = f"{os.cpu_count() or '?'} luồng"
    try:
        import psutil
        tt["ram"] = f"{psutil.virtual_memory().total / 2 ** 30:.0f} GB"
    except Exception:                                        # noqa: BLE001
        tt["ram"] = platform.machine() or "?"
    _PHAN_CUNG.update(tt)
    return _PHAN_CUNG


def _gio(giay: float) -> str:
    giay = max(0, int(giay))
    if giay < 60:
        return f"~{giay} giây"
    if giay < 3600:
        return f"~{round(giay / 60)} phút"
    return f"~{giay // 3600} giờ {round(giay % 3600 / 60)} phút"


def _rut_gon(p: str, toi_da: int = 26) -> str:
    p = str(p or "")
    if len(p) <= toi_da:
        return p
    phan = Path(p).parts
    ra = phan[-1]
    for x in reversed(phan[:-1]):
        if len(ra) + len(x) + 2 > toi_da - 2:
            break
        ra = str(Path(x) / ra)
    return "…" + os.sep + ra


class TrangXuLy(tk.Frame):
    """Trang Xử lý & xuất — hai cột: tiến độ + các bước | phần cứng + nhật ký."""

    BUOC = (("do", "Đo sáng và lọc ảnh"), ("ap", "Áp cân sáng vào Lightroom"),
            ("xuat", "Lightroom xuất ảnh"), ("rt", "Retouch"))

    def __init__(self, cha, app):
        m = gd.MAU
        super().__init__(cha, background=m["toi"])
        self.app = app
        self._mau_toc: list = []          # [(giờ, số đã xong)] của việc đang chạy
        self._viec_cu = None
        self._chay_cu = False
        self._hen = None
        lh = gd.don_vi(self)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        trai = tk.Frame(self, background=m["toi"])
        trai.grid(row=0, column=0, sticky="new", padx=(0, 20))
        trai.columnconfigure(0, weight=1)
        phai = tk.Frame(self, background=m["toi"], width=round(lh * 24))
        phai.grid(row=0, column=1, sticky="new")
        tk.Frame(phai, width=round(lh * 24), height=1, background=m["toi"]).pack()

        # ---- thẻ tiến độ
        the = gd.TheBo(trai, nen=m["toi"], pad=24)
        the.grid(row=0, column=0, sticky="ew")
        t = the.trong
        t.columnconfigure(0, weight=1)
        self.lbl_viec = tk.Label(t, text="", background=m["tam"], foreground=m["mo"],
                                 font=gd.CHU, anchor="w")
        self.lbl_viec.grid(row=0, column=0, sticky="w")
        hang = tk.Frame(t, background=m["tam"])
        hang.grid(row=1, column=0, sticky="ew", pady=(2, 14))
        self.lbl_so = tk.Label(hang, text="0", background=m["tam"], foreground=m["chu"],
                               font=gd.phong(30, "dam"))
        self.lbl_so.pack(side="left")
        self.lbl_tong = tk.Label(hang, text="", background=m["tam"], foreground=m["mo"],
                                 font=gd.phong(13, "so"))
        self.lbl_tong.pack(side="left", padx=(8, 0), pady=(14, 0))
        nut = tk.Frame(hang, background=m["tam"])
        nut.pack(side="right")
        self.btn_dung = gd.NutTron(nut, "Dừng", kieu="do", icon="dong", nen=m["tam"],
                                   command=self._dung)
        self.btn_bat_dau = gd.NutTron(nut, "Xuất & retouch…", kieu="chinh", icon="xuat_anh",
                                      nen=m["tam"], command=self._bat_dau)
        self.thanh = gd.ThanhTienDo(t, cao=max(6, round(lh * 0.55)), nen=m["tam"])
        self.thanh.grid(row=2, column=0, sticky="ew")
        o = tk.Frame(t, background=m["tam"])
        o.grid(row=3, column=0, sticky="ew", pady=(16, 0))
        self.o_so = {}
        for i, (ma, icon, phu) in enumerate((("toc", "toc_do", "mỗi ảnh"),
                                             ("con", "dong_ho", "còn lại"),
                                             ("ra", "thu_muc", "thư mục ra"))):
            o.columnconfigure(i, weight=1, uniform="o")
            th = gd.TheBo(o, nen_the=m["noi"], vien="", pad=12, pady=10, r=10, nen=m["tam"])
            th.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 10, 0))
            tr = th.trong
            gd.HopIcon(tr, icon, kieu="trung_tinh", co=round(lh * 2.0),
                       nen=m["noi"], mau_hop="#26282d", mau_net=m["nhan"]).pack(
                side="left", padx=(0, 10))
            cot = tk.Frame(tr, background=m["noi"])
            cot.pack(side="left", fill="x", expand=True)
            gt = gd.NhanGon(cot, text="—", background=m["noi"], foreground=m["chu"],
                            font=gd.phong(11, "so_vua"), anchor="w")
            gt.pack(fill="x")
            tk.Label(cot, text=phu, background=m["noi"], foreground=m["mo"],
                     font=gd.CHU_NHO, anchor="w").pack(fill="x")
            self.o_so[ma] = gt
        self.o_so["ra"].bind("<Button-1>", lambda _e: self._mo_ra())
        self.o_so["ra"].configure(cursor="hand2")

        # ---- các bước
        the2 = gd.TheBo(trai, nen=m["toi"], pad=0, pady=12)
        the2.grid(row=1, column=0, sticky="ew", pady=(20, 0))
        t2 = the2.trong
        t2.columnconfigure(0, weight=1)
        tk.Label(t2, text="CÁC BƯỚC", background=m["tam"], foreground=m["mo"],
                 font=gd.CHU_MUC, anchor="w").grid(row=0, column=0, sticky="w",
                                                   padx=24, pady=(8, 10))
        self.hang_buoc = {}
        for i, (ma, ten) in enumerate(self.BUOC):
            tk.Frame(t2, height=1, background=m["vien"]).grid(row=1 + 2 * i, column=0,
                                                              sticky="ew")
            h = tk.Frame(t2, background=m["tam"], padx=24, pady=12)
            h.grid(row=2 + 2 * i, column=0, sticky="ew")
            ic = tk.Canvas(h, width=round(lh * 1.7), height=round(lh * 1.7),
                           background=m["tam"], highlightthickness=0)
            ic.tu_cuon = False
            ic.pack(side="left", padx=(0, 12))
            lb = tk.Label(h, text=ten, background=m["tam"], foreground=m["chu"],
                          font=gd.phong(10, "vua"), anchor="w")
            lb.pack(side="left")
            ph = tk.Label(h, text="", background=m["tam"], foreground=m["mo"],
                          font=gd.phong(9, "so"), anchor="e")
            ph.pack(side="right")
            self.hang_buoc[ma] = (h, ic, lb, ph)

        # ---- phần cứng
        the3 = gd.TheBo(phai, nen=m["toi"], pad=20)
        the3.pack(fill="x")
        t3 = the3.trong
        dau = tk.Frame(t3, background=m["tam"])
        dau.pack(fill="x", pady=(0, 12))
        gd.HopIcon(dau, "phan_cung", co=round(lh * 2.1), nen=m["tam"],
                   mau_hop="#26282d", mau_net=m["nhan"]).pack(side="left", padx=(0, 10))
        tk.Label(dau, text="Phần cứng", background=m["tam"], foreground=m["chu"],
                 font=gd.phong(11, "dam")).pack(side="left")
        self.lbl_hw = {}
        for ma, ten in (("gpu", "GPU"), ("cpu", "CPU"), ("ram", "RAM")):
            d = tk.Frame(t3, background=m["tam"])
            d.pack(fill="x", pady=2)
            tk.Label(d, text=ten, background=m["tam"], foreground=m["mo"],
                     font=gd.CHU).pack(side="left")
            v = gd.NhanGon(d, text="…", background=m["tam"], foreground=m["chu"],
                           font=gd.phong(9, "so"), anchor="e")
            v.pack(side="right", fill="x", expand=True, padx=(12, 0))
            self.lbl_hw[ma] = v
        self.v_che_do_tam = tk.StringVar(value="auto")
        self.chon_che_do = gd.PhanDoan(t3, self.v_che_do_tam,
                                       [("auto", "Tự động"), ("nhanh", "Nhanh"),
                                        ("tiet_kiem", "Tiết kiệm")],
                                       command=self._doi_che_do, nen=m["tam"])
        self.chon_che_do.pack(fill="x", pady=(12, 0))
        self.chon_che_do.goi_y = gd.GoiY(
            self.chon_che_do, "Chế độ chạy của Retouch. Tự động: tool tự đo máy rồi "
                              "chọn — nên dùng. Nhanh: dám dùng nhiều bộ nhớ hơn. "
                              "Tiết kiệm: một luồng, ô nhớ nhỏ nhất — cho máy yếu "
                              "hoặc khi đang chạy việc khác.")
        self.the_canh = gd.TheBao(t3, muc="canh", chu="")
        self.btn_gpu = self.the_canh.tao_nut("Tải bản tăng tốc GPU…", self._tai_gpu)

        # ---- nhật ký
        the4 = gd.TheBo(phai, nen=m["toi"], pad=20)
        the4.pack(fill="x", pady=(20, 0))
        t4 = the4.trong
        dau = tk.Frame(t4, background=m["tam"])
        dau.pack(fill="x", pady=(0, 10))
        gd.HopIcon(dau, "nhat_ky", co=round(lh * 2.1), nen=m["tam"],
                   mau_hop="#26282d", mau_net=m["chu"]).pack(side="left", padx=(0, 10))
        tk.Label(dau, text="Nhật ký", background=m["tam"], foreground=m["chu"],
                 font=gd.phong(11, "dam")).pack(side="left")
        gd.NutTron(dau, "Mở thư mục log", kieu="chu", font=gd.CHU_NHO, nen=m["tam"],
                   command=self._mo_log).pack(side="right")
        self.txt = tk.Text(t4, height=7, width=10, wrap="word", borderwidth=0,
                           highlightthickness=0, background=m["tam"], foreground=m["mo"],
                           font=gd.phong(8, "so"), state="disabled", cursor="arrow")
        self.txt.tag_configure("cuoi", foreground=m["nhan"])
        self.txt.pack(fill="x")

        # ---- báo khi xong
        hang = tk.Frame(phai, background=m["toi"])
        hang.pack(fill="x", pady=(18, 0), padx=4)
        tk.Label(hang, text="Báo khi xong", background=m["toi"], foreground=m["chu"],
                 font=gd.CHU).pack(side="left")
        import thanh_luoi
        self.v_bao = tk.BooleanVar(value=bool(thanh_luoi.doc_kv("bao_khi_xong", True)))
        self.v_bao.trace_add("write", lambda *_a: thanh_luoi.ghi_kv("bao_khi_xong",
                                                                    bool(self.v_bao.get())))
        gd.CongTac(hang, self.v_bao, nen=m["toi"]).pack(side="right")

        threading.Thread(target=self._nap_hw, daemon=True).start()
        self.lam_moi()

    # ------------------------------------------------------------ số liệu
    def _nap_hw(self):
        """Luồng nền: chỉ đọc vào _PHAN_CUNG — nhãn đổi ở luồng giao diện (_ve)."""
        _doc_phan_cung()

    def _rt(self):
        return getattr(self.app, "_retouch_win", None)

    def _trang_thai(self) -> dict:
        """Việc đang chạy (ưu tiên retouch > Lightroom xuất > phân tích / ghi)."""
        app, rt = self.app, self._rt()
        st = {"viec": "", "da": 0, "tong": 0, "chay": False, "ra": "", "chu": ""}
        try:
            import xuat_lr
            td = xuat_lr.tien_do_xuat()
        except Exception:                                    # noqa: BLE001
            td = {}
        st["td"] = td
        rt_chay = bool(rt is not None and getattr(rt, "worker", None)
                       and rt.worker.is_alive())
        st["rt_chay"] = rt_chay
        if rt is not None and getattr(rt, "pb_tt", None) is not None:
            try:
                st["rt_da"] = int(float(rt.pb_tt.cget("value")))
                st["rt_tong"] = int(float(rt.pb_tt.cget("maximum")))
            except (tk.TclError, ValueError):
                st["rt_da"] = st["rt_tong"] = 0
        st["rt_chu"] = str(getattr(rt, "_chu_tt_chay", "") or "") if rt is not None else ""
        buoi = app.folder().name if app.folder() else ""
        if rt_chay:
            st.update(viec="rt", da=st.get("rt_da", 0), tong=st.get("rt_tong", 0),
                      chay=True, chu=f"Đang retouch · buổi {buoi}")
            st["ra"] = str(getattr(rt, "_ra_luot", None) or rt.v_ra.get() or "")
        elif td.get("trang_thai") == "dang_chay":
            st.update(viec="xuat", da=int(td.get("xong") or 0), tong=int(td.get("tong") or 0),
                      chay=True, chu=f"Lightroom đang xuất · buổi {buoi}",
                      ra=str(td.get("thu_muc", "")))
        elif app.busy:
            try:
                da = int(float(app.pb.cget("value")))
                tong = int(float(app.pb.cget("maximum")))
            except (tk.TclError, ValueError):
                da = tong = 0
            chu = str(app.lbl_tien3.cget("text") or "Đang phân tích")
            st.update(viec="do", da=da, tong=tong, chay=True,
                      chu=f"{chu.split(' ')[0] if chu else 'Đang'} · buổi {buoi}")
            st["chu"] = (f"Đang ghi · buổi {buoi}" if "ghi" in chu.lower()
                         else f"Đang phân tích · buổi {buoi}")
        else:
            if st["rt_chu"]:
                st.update(viec="rt", da=st.get("rt_da", 0), tong=st.get("rt_tong", 0),
                          chu=st["rt_chu"])
                if rt is not None:
                    st["ra"] = str(getattr(rt, "_ra_luot", None) or rt.v_ra.get() or "")
            elif td.get("trang_thai") in ("xong", "dung", "loi"):
                st.update(viec="xuat", da=int(td.get("xong") or 0),
                          tong=int(td.get("tong") or 0), ra=str(td.get("thu_muc", "")),
                          chu=("Lightroom đã xuất xong" if td.get("trang_thai") == "xong"
                               else "Lightroom dừng xuất"))
            else:
                st["chu"] = (f"Chưa chạy lượt nào · buổi {buoi}" if buoi
                             else "Chưa chọn buổi")
        return st

    def lam_moi(self):
        """Đọc lại số liệu; tự hẹn lại mỗi giây khi trang đang hiện."""
        if self._hen is not None:
            try:
                self.after_cancel(self._hen)
            except tk.TclError:
                pass
            self._hen = None
        try:
            self._ve(self._trang_thai())
        except Exception:                                    # noqa: BLE001
            traceback.print_exc()
        try:
            if self.winfo_ismapped():
                self._hen = self.after(1000, self.lam_moi)
        except tk.TclError:
            pass

    def _ve(self, st: dict):
        m = gd.MAU
        app = self.app
        da, tong, chay = st["da"], st["tong"], st["chay"]
        #  tốc độ: mẫu (giờ, số xong) của đúng việc đang chạy, cửa sổ ~90 giây
        bay_gio = time.time()
        if st["viec"] != self._viec_cu or not chay:
            self._mau_toc = []
        self._viec_cu = st["viec"] if chay else None
        if chay and (not self._mau_toc or self._mau_toc[-1][1] != da):
            self._mau_toc.append((bay_gio, da))
            self._mau_toc = [x for x in self._mau_toc if bay_gio - x[0] < 90] or \
                [(bay_gio, da)]
        s_anh = None
        if len(self._mau_toc) >= 2:
            (t0, d0), (t1, d1) = self._mau_toc[0], self._mau_toc[-1]
            if d1 > d0:
                s_anh = (t1 - t0) / (d1 - d0)
        self.lbl_viec.configure(text=st["chu"])
        self.lbl_so.configure(text=gd.so_vn(da))
        self.lbl_tong.configure(text=f"/ {gd.so_vn(tong)} ảnh" if tong else "ảnh")
        self.thanh.dat(da, tong)
        self.o_so["toc"].configure(text=(gd.thap_phan_vn(s_anh, 2, False) + " s")
                                   if s_anh else "—")
        self.o_so["con"].configure(text=_gio(s_anh * max(0, tong - da))
                                   if (s_anh and chay and tong) else
                                   ("xong" if (tong and da >= tong) else "—"))
        self.o_so["ra"].configure(text=_rut_gon(st.get("ra", "")) or "—")
        self.o_so["ra"].dat_goi_y(st.get("ra", ""))
        #  nút: đang chạy -> Dừng; rảnh -> Xuất & retouch…
        if chay:
            self.btn_bat_dau.pack_forget()
            if not self.btn_dung.winfo_manager():
                self.btn_dung.pack(side="left")
        else:
            self.btn_dung.pack_forget()
            if not self.btn_bat_dau.winfo_manager():
                self.btn_bat_dau.pack(side="left")
            self.btn_bat_dau.configure(state="normal" if app.items else "disabled")
        #  các bước
        td = st.get("td") or {}
        n_do = len(app.items or [])
        do_luc = getattr(app, "_do_luc", None)
        buoc = {
            "do": (("chay", f"{gd.so_vn(da)} / {gd.so_vn(tong)}")
                   if (st["viec"] == "do" and chay) else
                   ("xong", f"{gd.so_vn(n_do)} ảnh"
                    + (f" · {time.strftime('%H:%M', time.localtime(do_luc))}"
                       if do_luc else "")) if n_do else ("cho", "Chờ")),
            "ap": (("chay", "đang chờ Lightroom") if getattr(app, "_dang_cho_lr", False)
                   else ("xong", "đã áp") if getattr(app, "_da_ap_lr", False)
                   else ("cho", "Chưa áp")),
            "xuat": (("chay", f"{gd.so_vn(td.get('xong') or 0)} / "
                              f"{gd.so_vn(td.get('tong') or 0)}")
                     if td.get("trang_thai") == "dang_chay" else
                     ("xong", f"{gd.so_vn(td.get('xong') or 0)} ảnh")
                     if td.get("trang_thai") == "xong" else
                     ("loi", "dừng / lỗi") if td.get("trang_thai") in ("dung", "loi")
                     else ("cho", "Chờ")),
            "rt": (("chay", f"{gd.so_vn(st.get('rt_da', 0))} / "
                            f"{gd.so_vn(st.get('rt_tong', 0))}")
                   if st.get("rt_chay") else
                   ("xong", f"{gd.so_vn(st.get('rt_da', 0))} ảnh")
                   if str(st.get("rt_chu", "")).startswith("Retouch xong") else
                   ("cho", "Chờ")),
        }
        lh = gd.don_vi(self)
        for ma, (h, ic, lb, ph) in self.hang_buoc.items():
            tt, chu = buoc[ma]
            nen = m["nhan_nen"] if tt == "chay" else m["tam"]
            for w in (h, lb, ph):
                w.configure(background=nen)
            ic.configure(background=nen)
            lb.configure(foreground=m["mo"] if tt == "cho" else m["chu"],
                         font=gd.phong(10, "dam" if tt == "chay" else "vua"))
            ph.configure(text=chu, foreground=m["nhan"] if tt == "chay" else
                         m["loi"] if tt == "loi" else m["mo"])
            ic.delete("all")
            s = round(lh * 1.7)
            if tt == "xong":
                ic.create_oval(1, 1, s - 1, s - 1, fill=m["xong_nen"], outline="")
                gd.ve_bieu_tuong(ic, "giu_anh", s / 2, s / 2, s * 0.55, m["xong"])
            elif tt == "chay":
                ic.create_arc(2, 2, s - 2, s - 2, start=90, extent=-280, style="arc",
                              outline=m["nhan"], width=2)
            elif tt == "loi":
                ic.create_oval(1, 1, s - 1, s - 1, fill=m["do_nen"], outline="")
                gd.ve_bieu_tuong(ic, "dong", s / 2, s / 2, s * 0.5, m["do"])
            else:
                ic.create_oval(2, 2, s - 2, s - 2, outline=m["mo3"], width=2)
        #  chế độ retouch: gắn vào RetouchWindow.v_che_do khi đã mở Retouch
        rt = self._rt()
        if rt is not None and getattr(rt, "v_che_do", None) is not None:
            try:
                if self.v_che_do_tam.get() != rt.v_che_do.get():
                    self.v_che_do_tam.set(rt.v_che_do.get())
            except tk.TclError:
                pass
        #  cảnh báo GPU
        gpu_tt = getattr(app, "_gpu_tt", "")
        if gpu_tt == "loi":
            self.the_canh.nhan.configure(text="Tải bản tăng tốc GPU bị lỗi — Retouch "
                                              "đang chạy bằng CPU (chậm hơn nhiều).")
            if not self.the_canh.winfo_manager():
                self.the_canh.pack(fill="x", pady=(14, 0))
        elif gpu_tt == "dang_tai":
            self.the_canh.nhan.configure(text="Đang tải bản tăng tốc GPU — Retouch mở "
                                              "khi tải xong.")
            if not self.the_canh.winfo_manager():
                self.the_canh.pack(fill="x", pady=(14, 0))
        elif self.the_canh.winfo_manager():
            self.the_canh.pack_forget()
        self._ve_nhat_ky(st)
        if _PHAN_CUNG and self.lbl_hw["gpu"].cget("text") == "…":
            for k, w in self.lbl_hw.items():
                w.configure(text=_PHAN_CUNG.get(k, ""))
        #  thanh 5 bước + báo khi xong
        phu = ""
        if chay:
            ten = {"rt": "Retouch", "xuat": "Đang xuất", "do": "Đang chạy"}.get(st["viec"], "")
            phu = f"{ten} {gd.so_vn(da)}/{gd.so_vn(tong)}" if tong else ten
        elif str(st.get("rt_chu", "")).startswith("Retouch xong"):
            phu = st["rt_chu"]
        app._xu_ly_tt = {"dang": chay, "xong": bool(phu) and not chay, "phu": phu}
        if self._chay_cu and not chay:
            self._bao_xong(st)
        self._chay_cu = chay

    def _ve_nhat_ky(self, st):
        rt = self._rt()
        dong = []
        if rt is not None and getattr(rt, "txt", None) is not None:
            try:
                dong = [d for d in rt.txt.get("end-9l", "end").splitlines() if d.strip()]
            except tk.TclError:
                dong = []
        if not dong:
            td = st.get("td") or {}
            if td.get("thong_bao"):
                dong = [str(td.get("thong_bao"))]
        chu = "\n".join(dong[-7:])
        if getattr(self, "_chu_log", None) == chu:
            return
        self._chu_log = chu
        t = self.txt
        t.configure(state="normal")
        t.delete("1.0", "end")
        if chu:
            ds = chu.splitlines()
            for i, d in enumerate(ds):
                t.insert("end", d + ("\n" if i < len(ds) - 1 else ""),
                         ("cuoi",) if (i == len(ds) - 1 and st.get("chay")) else ())
        else:
            t.insert("end", "Chưa có nhật ký — chạy Xuất hoặc Retouch để xem tiến trình.")
        t.configure(state="disabled")

    # ------------------------------------------------------------ hành động
    def _bao_xong(self, st):
        if not self.v_bao.get():
            return
        try:
            self.bell()
            top = self.winfo_toplevel()
            top.deiconify()
            top.lift()
            top.attributes("-topmost", True)
            top.after(400, lambda: top.attributes("-topmost", False))
        except tk.TclError:
            pass
        self.app.status("✓ Xong: " + (st.get("chu") or "lượt chạy"), gd.MAU["xong"])

    def _dung(self):
        st = self._trang_thai()
        rt = self._rt()
        if st.get("rt_chay") and rt is not None:
            rt.stop()
        elif (st.get("td") or {}).get("trang_thai") == "dang_chay":
            self.app.do_dung_xuat()
        elif self.app.busy:
            self.app.do_cancel()
        self.after(300, self.lam_moi)

    def _bat_dau(self):
        self.app.do_xuat_hop()

    def _doi_che_do(self):
        rt = self._rt()
        if rt is not None and getattr(rt, "v_che_do", None) is not None:
            rt.v_che_do.set(self.v_che_do_tam.get())

    def _tai_gpu(self):
        self.app.tai_gpu()

    def _mo_ra(self):
        p = self._trang_thai().get("ra")
        if p and Path(p).exists():
            gd.open_in_explorer(Path(p))

    def _mo_log(self):
        try:
            import duong_dan as dd
            gd.open_in_explorer(dd.du_lieu("retouch.log").parent)
        except Exception:                                    # noqa: BLE001
            traceback.print_exc()
