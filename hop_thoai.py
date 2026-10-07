#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hop_thoai.py — Các cửa sổ phụ của Tone&Retouch (tách từ autotone_gui.py, 7/10).

    BuoiWindow          buổi chụp đang ở khâu nào (nối sang cả hai màn)
    TaiCapNhat          tải MỘT bản cập nhật code/model, có thanh tiến độ
    TaiTaiNguyenDialog  tải torch / mô hình / mediapipe
    GuWindow            "Vì sao tôi sửa" — gắn lý do cho từng ảnh
    LogWindow           xem nhật ký / danh sách
    UndoDialog          chọn bản backup để khôi phục

Chỉ phụ thuộc giao_dien (Khung, open_in_explorer, TEN_HIEN_THI) và autotone;
KHÔNG import autotone_gui (tránh vòng) — nhận `app` qua tham số.
"""

from __future__ import annotations

import csv
import io
import os
import queue
import sys
import threading
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at
import giao_dien as gd

from typing import TYPE_CHECKING

from giao_dien import Khung, open_in_explorer, TEN_HIEN_THI

if TYPE_CHECKING:                                            # chỉ cho chú thích kiểu
    from autotone_gui import App


class BuoiWindow(tk.Toplevel):
    """Buổi chụp đang ở khâu nào — bảy khâu, mỗi khâu một dòng.

    MỌI TRẠNG THÁI SUY TỪ FILE TRÊN ĐĨA, không từ những gì app tự nhớ. Xem
    chú thích đầu trang_thai.py: file trạng thái chỉ giữ ba thứ không suy nổi
    (thư mục Export, thư mục retouch, thời gian từng khâu). Xoá nó đi thì mất
    mấy con số thời gian chứ không mất trạng thái — có bài kiểm cho đúng điều
    đó trong test_trang_thai.py.
    """

    def __init__(self, app: App):
        super().__init__(app)
        self.app = app
        import trang_thai as tt
        self.tt = tt
        self.title(f"Buổi chụp — {app.folder().name}")
        self.geometry("780x520")
        self.minsize(680, 440)

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(1, weight=1)

        self.lbl_top = ttk.Label(frm, font=("Segoe UI", 11, "bold"))
        self.lbl_top.grid(row=0, column=0, sticky="w", pady=(0, 8))

        self.hop = ttk.Frame(frm)
        self.hop.grid(row=1, column=0, sticky="nsew")
        self.hop.columnconfigure(1, weight=1)

        bar = ttk.Frame(frm)
        bar.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        ttk.Button(bar, text="Làm mới", command=self.lam_moi).pack(side="left")
        ttk.Button(bar, text="Chỉ chỗ đã Export...",
                   command=self.chon_export).pack(side="left", padx=6)
        ttk.Button(bar, text="Chép tóm tắt",
                   command=self.chep).pack(side="left", padx=6)
        ttk.Button(bar, text="Đóng", command=self.destroy).pack(side="right")

        self.lam_moi()
        #[[ Tu lam moi moi 5 giay. Day la cach "app tu nhan ra thu muc Export"
        #   ma khong can mot tien trinh nen theo doi o dia: cua so nay mo thi
        #   no dem lai, dong thi thoi. Nguoi dung Export xong, nhin sang day la
        #   thay so anh nhay len.
        #]]
        self._dem_lan_truoc = None
        self.after(5000, self._tu_lam_moi)

    def _tu_lam_moi(self):
        if not self.winfo_exists():
            return
        self.lam_moi(im_lang=True)
        self.after(5000, self._tu_lam_moi)

    def lam_moi(self, im_lang: bool = False):
        root = self.app.folder()
        if not root:
            return
        for w in self.hop.winfo_children():
            w.destroy()
        ks = self.tt.tinh(root)
        xong = sum(1 for k in ks if k["xong"])
        self.lbl_top.configure(text=f"{root}      {xong}/{len(ks)} khâu xong")

        for i, k in enumerate(ks):
            dau = "✓" if k["xong"] else "○"
            mau = gd.MAU["xong"] if k["xong"] else gd.MAU["mo"]
            ttk.Label(self.hop, text=dau, foreground=mau,
                      font=("Segoe UI", 12)).grid(row=i, column=0, sticky="w",
                                                  padx=(0, 8), pady=3)
            o = ttk.Frame(self.hop)
            o.grid(row=i, column=1, sticky="ew", pady=3)
            o.columnconfigure(0, weight=1)
            ttk.Label(o, text=k["nhan"], font=("Segoe UI", 10, "bold")
                      ).grid(row=0, column=0, sticky="w")
            phu = k["mo_ta"]
            if k["khi"]:
                phu += f"      {k['khi']}"
            if k["giay"]:
                phu += f"      {k['giay'] / 60:.1f} phút"
            ttk.Label(o, text=phu, foreground=gd.MAU["mo"]).grid(row=1, column=0, sticky="w")
            if k["viec"]:
                ttk.Button(self.hop, text=k["viec"], width=20,
                           command=lambda v=k["viec"]: self.lam(v)
                           ).grid(row=i, column=2, padx=(10, 0))

        # Số ảnh trong thư mục Export vừa tăng -> hỏi, KHÔNG tự chạy.
        ex = self.tt.doc(self.tt.ten_buoi(root)).get("thu_muc_export")
        n = self.tt.dem_anh(ex) if ex else 0
        if (not im_lang) or self._dem_lan_truoc is None:
            self._dem_lan_truoc = n
            return
        if n > self._dem_lan_truoc:
            truoc, self._dem_lan_truoc = self._dem_lan_truoc, n
            #[[ HOI, khong tu chay. Nguoi dung da chot dieu nay tu dau: retouch
            #   chi chay khi ho chu dong, khong co tien trinh nao am tham.
            #]]
            if messagebox.askyesno(
                    "Export xong rồi?",
                    f"Thư mục Export vừa tăng từ {truoc} lên {n} ảnh.\n\n"
                    "Mở cửa sổ Retouch bây giờ?", parent=self):
                self.app.open_retouch()

    def lam(self, viec: str):
        """Bấm nút việc tiếp theo — gọi đúng nút tương ứng ở cửa sổ chính."""
        if viec.startswith("1"):
            self.app.start_analyze()
        elif viec.startswith("2"):
            self.app.do_apply()
        elif viec.startswith("3"):
            self.app.open_retouch()
        elif viec.startswith("Vì sao"):
            self.app.do_gu()
        elif viec.startswith("Chỉ chỗ"):
            self.chon_export()
        else:
            messagebox.showinfo("Việc này làm ở cửa sổ chính", viec, parent=self)

    def chon_export(self):
        root = self.app.folder()
        cu = self.tt.doc(self.tt.ten_buoi(root)).get("thu_muc_export")
        d = filedialog.askdirectory(title="Thư mục Lightroom đã Export ra",
                                    initialdir=cu or str(root), parent=self)
        if d:
            self.tt.ghi(self.tt.ten_buoi(root), thu_muc_export=os.path.normpath(d))
            self._dem_lan_truoc = None
            self.lam_moi()

    def chep(self):
        t = self.tt.tom_tat(self.app.folder())
        self.clipboard_clear()
        self.clipboard_append(t)
        LogWindow(self, t.splitlines(), title="Tóm tắt buổi chụp",
                  subtitle="Đã chép vào clipboard")


class TaiCapNhat(tk.Toplevel):
    """Tai MOT ban cap nhat code/model ve, co thanh tien do.

    Giong TaiTaiNguyenDialog ve cach lam (luong nen + queue + _bom), nhung cho
    DUNG MOT ban (dict tu cap_nhat.kiem_tra). Tai xong ghi vao thu muc du lieu;
    LAN MO SAU app tu kich_hoat() ban moi. KHONG ap giua chung — doi mot module
    .pyd dang chay bang ban khac luc dang chay la tro mao hiem khong can.
    """

    def __init__(self, cha, cn, ban: dict):
        super().__init__(cha)
        self.cn = cn
        self.ban = ban
        self.title(f"Cập nhật {TEN_HIEN_THI}")
        self.transient(cha)
        self.resizable(False, False)
        self._dung = False
        self._dang = False
        self.q: queue.Queue = queue.Queue()

        frm = ttk.Frame(self, padding=14)
        frm.pack(fill="both", expand=True)
        mb = f"  (~{ban['mb']} MB)" if ban.get("mb") else ""
        ttk.Label(frm, justify="left", wraplength=560, text=(
            f"Bản mới: {ban['ver']}{mb}\n"
            f"Đang chạy: {cn.phien_ban_dang_chay()}"
        )).pack(anchor="w")
        if ban.get("ghi_chu"):
            ttk.Label(frm, style="Mo.TLabel", justify="left", wraplength=560,
                      text=ban["ghi_chu"]).pack(anchor="w", pady=(4, 0))
        ttk.Label(frm, style="Mo.TLabel", justify="left", wraplength=560,
                  text=f"Lưu tại: {cn.goc()}").pack(anchor="w", pady=(6, 10))

        self.lbl = ttk.Label(frm, justify="left", wraplength=560,
                             text="Bấm Tải để bắt đầu.")
        self.lbl.pack(anchor="w", pady=(6, 4))
        self.pb = ttk.Progressbar(frm, length=560, mode="determinate")
        self.pb.pack(fill="x")

        nut = ttk.Frame(frm)
        nut.pack(fill="x", pady=(12, 0))
        self.btn = ttk.Button(nut, text="Tải", command=self._bat_dau)
        self.btn.pack(side="right")
        ttk.Button(nut, text="Đóng", command=self._dong).pack(
            side="right", padx=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self._dong)
        self.after(100, self._bom)

    def _bat_dau(self):
        if self._dang:
            return
        self._dung = False
        self._dang = True
        self.btn.configure(text="Dừng", command=self._xin_dung)
        threading.Thread(target=self._chay, daemon=True).start()

    def _xin_dung(self):
        self._dung = True
        self.lbl.configure(text="Đang dừng...", foreground=gd.MAU["canh"])

    def _chay(self):
        def td(pha, da, tong):
            self.q.put(("td", (pha, da, tong)))
        try:
            self.cn.tai(self.ban, tien_do=td, dung=lambda: self._dung)
            self.q.put(("xong", None))
        except InterruptedError:
            self.q.put(("dung", None))
        except Exception as ex:                              # noqa: BLE001
            self.q.put(("loi", f"{type(ex).__name__}: {ex}"))

    def _bom(self):
        try:
            while True:
                loai, gt = self.q.get_nowait()
                if loai == "td":
                    pha, da, tong = gt
                    if pha == "tai" and tong:
                        self.pb.configure(maximum=tong, value=da)
                        self.lbl.configure(
                            text=f"Đang tải: {da / 1048576:.0f}/"
                                 f"{tong / 1048576:.0f} MB",
                            foreground=gd.MAU["mo"])
                    elif pha == "giai-nen":
                        self.lbl.configure(text="Đang giải nén...",
                                           foreground=gd.MAU["canh"])
                elif loai == "dung":
                    self._dang = False
                    self.btn.configure(text="Tải", command=self._bat_dau)
                    self.pb.configure(value=0)
                    self.lbl.configure(
                        text="Đã dừng. Bấm Tải để chạy lại từ đầu.",
                        foreground=gd.MAU["canh"])
                elif loai == "loi":
                    self._dang = False
                    self.btn.configure(text="Tải", command=self._bat_dau)
                    self.pb.configure(value=0)
                    self.lbl.configure(text=f"Lỗi: {gt}",
                                       foreground=gd.MAU["loi"])
                elif loai == "xong":
                    self._dang = False
                    self.btn.configure(text="Tải", state="disabled")
                    self.pb.configure(value=self.pb["maximum"])
                    self.lbl.configure(
                        text=f"Xong. Đã tải bản {self.ban['ver']}.\n"
                             "Khởi động lại AutoTone để dùng bản mới.",
                        foreground=gd.MAU["xong"])
                    #[[ Don ban cu de khoi phinh — giu ban vua tai. ]]
                    try:
                        self.cn.don_ban_cu(giu=1)
                    except Exception:                        # noqa: BLE001
                        pass
        except queue.Empty:
            pass
        self.after(120, self._bom)

    def _dong(self):
        if self._dang and not messagebox.askokcancel(
                "Đang tải",
                "Đang tải dở. Đóng lại sẽ dừng.\n\nĐóng?", parent=self):
            return
        self._dung = True
        self.destroy()


class TaiTaiNguyenDialog(tk.Toplevel):
    """Tai cac goi nang ve may — torch, mo hinh, mediapipe.

    VI SAO CAN CUA SO NAY
        Ban nhe khong mang torch lan mo hinh trong goi (82 MB thay vi 4.1 GB).
        Thieu chung thi retouch khong chay, va thong bao cu bao nguoi dung
        "pip install torch" — mot cau vo nghia trong ban .exe, vi o do khong
        co pip, khong co Python nao de cai vao.

        Theo dung le cua _hoi_chep(): nut nao phat hien duoc thi nut do phai
        sua duoc. Day la cho sua.

    Tai xong KHONG can khoi dong lai: nap() them duong dan vao sys.path ngay,
    va cac module nang deu duoc import BEN TRONG ham luc chay, khong phai o
    dau file. Nen lan bam Retouch ke tiep la thay.
    """

    def __init__(self, cha, tn, can=None, gpu=False):
        #[[ gpu=True (5/10): mo tu "Tai ban tang toc GPU…" tren ban cai DAY DU
        #   (torch CPU + mo hinh da trong goi). User hoi "phan torch dang khong
        #   chon duoc la da duoc tai hay chua": hop thoai cu ghi torch "can cho
        #   retouch", khoa o tick (ttk disabled ve ra o TRONG — tuong chua
        #   chon), hien ca mo-hinh / mediapipe ma goi da co, va noi "ban cai
        #   khong mang san" — sai voi ban nay. Che do nay chi hien torch CUDA,
        #   o tick ro, cau chu noi dung la goi TANG TOC. ]]
        super().__init__(cha)
        self.tn = tn
        self.title("Tải bản tăng tốc GPU" if gpu else "Tải tài nguyên retouch")
        self.transient(cha)
        self.resizable(False, False)
        self._dung = False          # nguoi dung bam Dung
        self._dang_tai = False
        self.q = queue.Queue()
        self.xong_het = False

        frm = ttk.Frame(self, padding=14)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, justify="left", wraplength=560, text=(
            "Bản tăng tốc GPU: torch CUDA cho card NVIDIA. Bản cài đã chạy đủ "
            "8 tính năng bằng CPU — gói này chỉ để kéo thanh / Chạy retouch "
            "nhanh hơn nhiều. Tải một lần, dùng mãi; tải xong hãy ĐÓNG và MỞ "
            "LẠI app." if gpu else
            "Phần retouch cần thư viện và mô hình nặng, nên bản cài không "
            "mang sẵn. Tải một lần, dùng mãi — lần sau mở app không hỏi lại."
        )).pack(anchor="w")

        #[[ Noi ro no nam o DAU. Nguoi dung co quyen biet vai GB sap di vao o
        #   nao, va sau nay muon xoa thi tim o dau. ]]
        ttk.Label(frm, style="Mo.TLabel", justify="left", wraplength=560,
                  text=f"Lưu tại: {tn.goc()}").pack(anchor="w", pady=(6, 10))

        self.hang = {}
        can = set(can or tn.can_cho_retouch())
        for g in tn.tinh_trang():
            if gpu and g["ten"] != "torch":
                continue                 # ban day du da co mo hinh / mediapipe
            h = ttk.Frame(frm)
            h.pack(fill="x", pady=2)
            bat = g["ten"] in can
            v = tk.BooleanVar(value=bat or g["da_co"])
            #[[ Goi DA CO thi khoa lai — khong tai lai cai da co. Goi BAT BUOC
            #   cung khoa: bo no thi retouch van khong chay, cho chon chi tao
            #   ra mot lua chon sai. Chi mediapipe la that su tuy chon.
            #   Che do gpu: o torch de "normal" (tick hien RO) — ttk disabled
            #   ve o trong tren nen toi, nhin nhu chua chon. ]]
            if gpu and not g["da_co"]:
                trang_thai = "normal"
            else:
                trang_thai = "disabled" if (g["da_co"] or bat) else "normal"
            ttk.Checkbutton(h, variable=v, state=trang_thai,
                            text=f"{g['ten']}  ({g['mb']} MB)").pack(side="left")
            if gpu:
                ghi = "đã tải" if g["da_co"] else "bản tăng tốc — tuỳ chọn"
            else:
                ghi = "đã có" if g["da_co"] else ("cần cho retouch" if bat
                                                  else "tuỳ chọn")
            ttk.Label(h, style="Mo.TLabel",
                      text=f"— {g['mo_ta']}  [{ghi}]").pack(side="left",
                                                            padx=(8, 0))
            self.hang[g["ten"]] = (v, g)

        self.lbl = ttk.Label(frm, justify="left", wraplength=560, text="")
        self.lbl.pack(anchor="w", pady=(12, 4))
        self.pb = ttk.Progressbar(frm, length=560, mode="determinate")
        self.pb.pack(fill="x")

        nut = ttk.Frame(frm)
        nut.pack(fill="x", pady=(12, 0))
        self.btn_tai = ttk.Button(nut, text="Tải", command=self._bat_dau)
        self.btn_tai.pack(side="right")
        ttk.Button(nut, text="Đóng", command=self._dong).pack(side="right",
                                                              padx=(0, 8))

        self._cap_nhat_tong()
        self.protocol("WM_DELETE_WINDOW", self._dong)
        self.after(100, self._bom)

    def _chon(self):
        return [g for ten, (v, g) in self.hang.items()
                if v.get() and not g["da_co"]]

    def _cap_nhat_tong(self):
        ds = self._chon()
        if not ds:
            self.lbl.configure(text="Đã có đủ tài nguyên.",
                               foreground=gd.MAU["xong"])
            self.btn_tai.configure(state="disabled")
            self.xong_het = True
        else:
            tong = sum(g["mb"] for g in ds)
            self.lbl.configure(text=f"Sẽ tải {len(ds)} gói, khoảng {tong} MB.",
                               foreground=gd.MAU["mo"])

    def _bat_dau(self):
        ds = self._chon()
        if not ds:
            return
        self._dung = False
        self._dang_tai = True
        self.btn_tai.configure(text="Dừng", command=self._xin_dung)
        threading.Thread(target=self._chay, args=(ds,), daemon=True).start()

    def _xin_dung(self):
        self._dung = True
        self.lbl.configure(text="Đang dừng...", foreground=gd.MAU["canh"])

    def _chay(self, ds):
        """Chay trong luong rieng — moi cap nhat giao dien di qua self.q."""
        for i, g in enumerate(ds, 1):
            ten = g["ten"]
            try:
                goi = self.tn.GOI[ten]

                def td(pha, da, tong, _t=ten, _i=i):
                    self.q.put(("td", (_t, _i, len(ds), pha, da, tong)))

                self.tn.tai(goi, tien_do=td, dung=lambda: self._dung)
                self.q.put(("xong1", ten))
            except InterruptedError:
                self.q.put(("dung", ten))
                return
            except Exception as ex:                          # noqa: BLE001
                self.q.put(("loi", (ten, f"{type(ex).__name__}: {ex}")))
                return
        self.q.put(("xong", None))

    def _bom(self):
        """Doc hang doi, ve lai giao dien. Chay tren luong giao dien."""
        try:
            while True:
                loai, gt = self.q.get_nowait()
                if loai == "td":
                    ten, i, n, pha, da, tong = gt
                    if pha == "tai" and tong:
                        self.pb.configure(maximum=tong, value=da)
                        self.lbl.configure(
                            text=f"[{i}/{n}] {ten}: "
                                 f"{da / 1048576:.0f}/{tong / 1048576:.0f} MB",
                            foreground=gd.MAU["mo"])
                    elif pha == "giai-nen":
                        self.lbl.configure(
                            text=f"[{i}/{n}] {ten}: đang giải nén...",
                            foreground=gd.MAU["canh"])
                elif loai == "xong1":
                    #[[ Nap NGAY sau moi goi, khong doi tai het. Tai torch xong
                    #   la dung duoc torch, du mo hinh con dang tai. ]]
                    self.tn.nap(gt)
                    self.hang[gt][1]["da_co"] = True
                elif loai == "dung":
                    self._dang_tai = False
                    self.btn_tai.configure(text="Tải", command=self._bat_dau)
                    self.pb.configure(value=0)
                    self.lbl.configure(
                        text="Đã dừng. Bấm Tải để chạy tiếp — phần đã tải "
                             "xong vẫn giữ nguyên.",
                        foreground=gd.MAU["canh"])
                elif loai == "loi":
                    ten, mo = gt
                    self._dang_tai = False
                    self.btn_tai.configure(text="Tải", command=self._bat_dau)
                    self.pb.configure(value=0)
                    self.lbl.configure(text=f"Lỗi khi tải {ten}:\n{mo}",
                                       foreground=gd.MAU["loi"])
                elif loai == "xong":
                    self._dang_tai = False
                    self.xong_het = True
                    self.btn_tai.configure(text="Tải", state="disabled",
                                           command=self._bat_dau)
                    self.pb.configure(value=self.pb["maximum"])
                    self.lbl.configure(
                        text="Xong. Bấm Đóng rồi bấm Retouch — không cần "
                             "khởi động lại app.",
                        foreground=gd.MAU["xong"])
        except queue.Empty:
            pass
        self.after(120, self._bom)

    def _dong(self):
        if self._dang_tai and not messagebox.askokcancel(
                "Đang tải",
                "Đang tải dở. Đóng lại sẽ dừng việc tải.\n\n"
                "Phần đã tải xong vẫn giữ, lần sau tải tiếp.\n\nĐóng?",
                parent=self):
            return
        self._dung = True
        self.destroy()


class GuWindow(Khung):
    """Gắn lý do cho từng ảnh đã sửa tay — một ảnh một lần, bấm là xong.

    VÌ SAO KHÔNG PHẢI MỘT BẢNG ĐỂ GÕ
        Gõ vào bảng thì mỗi ảnh mất mươi giây và anh sẽ bỏ dở giữa chừng — mà
        dữ liệu bỏ dở còn tệ hơn không có, vì nó lệch: anh chỉ gõ cho những
        tấm dễ nói. Ở đây một phím là một lý do, nên gắn xong cả buổi trong
        vài phút và không bỏ sót tấm khó.

    VÌ SAO PHẢI THẤY KHUNG MẶT
        Xanh lá là khuôn mặt tool dùng để đo sáng. Nhìn khung là biết ngay tool
        đo nhầm chỗ hay đo đúng mà anh chỉ muốn sáng khác — hai nhóm đó dẫn tới
        hai tham số hoàn toàn khác nhau, và gộp chúng lại chính là cái đã làm
        mốc tính ra -1.42 thay vì -1.19.
    """

    def __init__(self, app, thu_muc: Path, cha=None):
        super().__init__(cha if cha is not None else app)
        self.app = app
        self.dir = Path(thu_muc)
        self.csv = self.dir / "gu.csv"
        self.title(f"Vì sao tôi sửa — {self.dir.name}")
        self.geometry("1020x760")
        self.rows, self.cols = self._doc()
        if not self.rows:
            messagebox.showinfo("Không có ảnh nào", f"{self.csv} rỗng.")
            self.destroy()
            return
        self.i = self._dau_tien_chua_gan()
        self._ly_do = self._nap_ly_do()
        self._anh = None                  # giữ tham chiếu, nếu không Tk xoá mất
        self._dung()
        self._hien()

    # ---------------------------------------------------------------- dữ liệu
    def _doc(self):
        with io.open(self.csv, encoding="utf-8-sig", newline="") as fh:
            r = csv.DictReader(fh)
            return list(r), list(r.fieldnames or [])

    def _nap_ly_do(self):
        try:
            import thu_gu
            return thu_gu.LY_DO
        except Exception:                                    # noqa: BLE001
            return [("khac", "Lý do khác", "")]

    def _dau_tien_chua_gan(self) -> int:
        for k, r in enumerate(self.rows):
            if not (r.get("ly_do") or "").strip():
                return k
        return 0

    def _ghi(self):
        #[[ Ghi ra .part roi doi ten. Cua so nay ghi sau MOI lan bam, nen neu
        #   ghi thang va may treo dung luc do thi mat sach cong gan ca buoi.
        #]]
        tmp = self.csv.with_suffix(".part")
        with io.open(tmp, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=self.cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(self.rows)
        os.replace(tmp, self.csv)

    # ---------------------------------------------------------------- giao diện
    def _dung(self):
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(1, weight=1)

        self.lbl_top = ttk.Label(frm, font=("Segoe UI", 11, "bold"))
        self.lbl_top.grid(row=0, column=0, sticky="w")

        self.canvas = tk.Label(frm, background="#161618")
        self.canvas.grid(row=1, column=0, sticky="nsew", pady=(6, 6))

        self.lbl_so = ttk.Label(frm, foreground=gd.MAU["mo"], font=("Consolas", 9),
                                justify="left")
        self.lbl_so.grid(row=2, column=0, sticky="w")

        box = ttk.LabelFrame(frm, text="Vì sao anh sửa tấm này?", padding=8)
        box.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        box.columnconfigure(0, weight=1)
        self.v_ly_do = tk.StringVar(value="")
        for n, (ma, nghia, thamso) in enumerate(self._ly_do):
            t = f"{n + 1}.  {nghia}"
            if thamso:
                t += f"     [{thamso}]"
            ttk.Radiobutton(box, text=t, value=ma, variable=self.v_ly_do,
                            command=self._chon).grid(row=n, column=0, sticky="w")
            self.bind(str(n + 1), lambda _e, m=ma: self._phim(m))
        #[[ Phim so KHONG duoc an khi con tro dang o o ghi chu.
        #   Go "2 nguoi dung khung" vao o giai thich thi so 2 se bi hieu la
        #   phim tat, gan ly do #2 roi nhay sang anh khac — mat luon cau vua go.
        #]]

        ttk.Label(box, text="Giải thích thêm (không bắt buộc):").grid(
            row=len(self._ly_do), column=0, sticky="w", pady=(6, 0))
        self.v_note = tk.StringVar()
        ttk.Entry(box, textvariable=self.v_note).grid(
            row=len(self._ly_do) + 1, column=0, sticky="ew")

        bar = ttk.Frame(frm)
        bar.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(bar, text="◀  Trước", command=lambda: self._di(-1)).pack(side="left")
        ttk.Button(bar, text="Sau  ▶", command=lambda: self._di(1)).pack(
            side="left", padx=(6, 0))
        self.lbl_tien = ttk.Label(bar, foreground=gd.MAU["mo"])
        self.lbl_tien.pack(side="left", padx=(14, 0))
        ttk.Button(bar, text="Xong", command=self._xong).pack(side="right")
        ttk.Button(bar, text="Mở thư mục gói duyệt",
                   command=lambda: open_in_explorer(self.dir)).pack(
            side="right", padx=(0, 6))

        # Phim 1..7 chon ly do, mui ten di lai — gan ca buoi khong roi ban phim
        self.bind("<Left>", lambda _e: self._di(-1))
        self.bind("<Right>", lambda _e: self._di(1))
        self.bind("<Escape>", lambda _e: self._xong())
        self.focus_set()

    def _phim(self, ma: str):
        if isinstance(self.focus_get(), (ttk.Entry, tk.Entry)):
            return                       # dang go chu, khong phai bam phim tat
        self.v_ly_do.set(ma)
        self._chon()

    def _chon(self):
        """Chọn xong là ghi luôn và nhảy sang tấm sau — không cần bấm Lưu."""
        r = self.rows[self.i]
        r["ly_do"] = self.v_ly_do.get()
        r["giai_thich"] = self.v_note.get().strip()
        self._ghi()
        if self.i < len(self.rows) - 1:
            self._di(1)
        else:
            self._hien()

    def _di(self, buoc: int):
        r = self.rows[self.i]
        note = self.v_note.get().strip()
        if note != (r.get("giai_thich") or ""):
            r["giai_thich"] = note
            self._ghi()
        self.i = max(0, min(len(self.rows) - 1, self.i + buoc))
        self._hien()

    def _hien(self):
        r = self.rows[self.i]
        n_gan = sum(1 for x in self.rows if (x.get("ly_do") or "").strip())
        self.lbl_top.configure(
            text=f"{self.i + 1}/{len(self.rows)}   {r['file'].upper()}"
                 f"      tool {r['tool_exposure']}  →  anh chọn {r['user_exposure']}"
                 f"   ({r['sua_bao_nhieu']})")
        self.lbl_tien.configure(text=f"đã gắn {n_gan}/{len(self.rows)}")
        self.v_ly_do.set(r.get("ly_do") or "")
        self.v_note.set(r.get("giai_thich") or "")

        chi = [f"đo theo {r.get('nguon_do') or '?'}",
               f"{r.get('khung_tong') or '?'} khung → {r.get('khung_do_sang') or '?'} đo sáng",
               f"metered {r.get('metered_ev') or '?'}",
               f"cháy trước {r.get('clip_before') or '?'}%",
               f"cảnh {r.get('scene') or '?'} (n={r.get('scene_size') or '?'})"]
        if r.get("notes"):
            chi.append(r["notes"])
        self.lbl_so.configure(text="   |   ".join(chi))

        #[[ Anh khong co thi noi ro LY DO, dung de mot o den.
        #   Thieu anh nghia la thu_gu chay voi --khong-ve, hoac file RAW da bi
        #   di chuyen. Ca hai deu sua duoc, nhung chi khi biet.
        #]]
        p = self.dir / (r.get("anh_le") or "")
        if r.get("anh_le") and p.is_file():
            try:
                from PIL import Image, ImageTk
                im = Image.open(p)
                #[[ winfo_width() tra ve 1 khi cua so chua duoc ve lan nao —
                #   khong phai 0, nen "or 960" khong do duoc. Anh dau tien se
                #   bi thu nho con 1 pixel. Lay max() moi chac.
                #]]
                im.thumbnail((max(self.canvas.winfo_width(), 960),
                              max(self.canvas.winfo_height(), 520)))
                self._anh = ImageTk.PhotoImage(im)
                self.canvas.configure(image=self._anh, text="")
                return
            except Exception as ex:                          # noqa: BLE001
                loi = f"Không mở được ảnh:\n{type(ex).__name__}: {ex}"
        else:
            loi = ("Không có ảnh cho tấm này.\n\n"
                   "Có thể thu_gu.py chạy với --khong-ve, hoặc file RAW\n"
                   "đã bị chuyển đi khỏi thư mục buổi chụp.")
        self._anh = None
        self.canvas.configure(image="", text=loi, foreground=gd.MAU["mo"])

    def _xong(self):
        self._di(0)
        chua = [r["file"] for r in self.rows if not (r.get("ly_do") or "").strip()]
        if chua and not messagebox.askokcancel(
                "Còn ảnh chưa gắn lý do",
                f"Còn {len(chua)} ảnh chưa gắn.\n\n"
                "Ảnh chưa gắn sẽ không được dùng để học — đóng lại bây giờ?"):
            return
        self.app.status(
            f"Đã gắn lý do {len(self.rows) - len(chua)}/{len(self.rows)} ảnh "
            f"— gói duyệt ở {self.dir}", gd.MAU["xong"])
        self.destroy()


class LogWindow(tk.Toplevel):
    """Nhật ký plugin Lightroom — mỗi job một dòng, kèm số ảnh đã áp."""

    def __init__(self, app, lines: list, title: str = "", subtitle: str = ""):
        super().__init__(app)
        self.app = app
        self.title(title or "Nhật ký plugin Lightroom")
        self.geometry("900x460")
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(1, weight=1)

        ttk.Label(frm, foreground=gd.MAU["mo"],
                  text=subtitle or f"{at.LR_JOB_DIR / 'plugin.log'}"
                  ).grid(row=0, column=0, sticky="w", pady=(0, 6))

        txt = tk.Text(frm, wrap="none", font=("Consolas", 9))
        txt.grid(row=1, column=0, sticky="nsew")
        sb = ttk.Scrollbar(frm, orient="vertical", command=txt.yview)
        sb.grid(row=1, column=1, sticky="ns")
        txt.configure(yscrollcommand=sb.set)
        txt.insert("1.0", "\n".join(lines))
        txt.see("end")                     # dòng mới nhất nằm cuối
        txt.configure(state="disabled")

        bar = ttk.Frame(frm)
        bar.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(bar, text="Mở thư mục job",
                   command=lambda: open_in_explorer(at.LR_JOB_DIR)
                   ).pack(side="left")
        ttk.Button(bar, text="Đóng", command=self.destroy).pack(side="right")


class UndoDialog(tk.Toplevel):
    """Chọn một bản backup để khôi phục."""

    def __init__(self, app: App, root: Path, backups: list[Path]):
        super().__init__(app)
        self.app, self.root_dir, self.backups = app, root, backups
        self.title("Hoàn tác — chọn bản backup")
        self.transient(app.master)
        self.resizable(False, False)

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Khôi phục sidecar .xmp về bản đã lưu lúc:").pack(anchor="w")

        self.lb = tk.Listbox(frm, height=min(10, len(backups)), width=54,
                             exportselection=False)
        for d in backups:
            n = len(list(d.rglob("*.xmp")))
            try:
                when = datetime.strptime(d.name, "%Y%m%d_%H%M%S").strftime("%d/%m/%Y  %H:%M:%S")
            except ValueError:
                when = d.name
            self.lb.insert("end", f"{when}   —   {n} file")
        self.lb.selection_set(0)
        self.lb.pack(pady=(6, 10), fill="x")

        bar = ttk.Frame(frm)
        bar.pack(fill="x")
        ttk.Button(bar, text="Khôi phục", command=self._do).pack(side="right")
        ttk.Button(bar, text="Huỷ", command=self.destroy).pack(side="right", padx=(0, 6))

        self.grab_set()
        self.lb.focus_set()

    def _do(self):
        sel = self.lb.curselection()
        if not sel:
            return
        d = self.backups[sel[0]]
        if not messagebox.askokcancel("Xác nhận",
                                      f"Ghi đè sidecar hiện tại bằng bản\n{d.name}?",
                                      parent=self):
            return
        n = at.undo(d, self.root_dir)
        self.destroy()
        self.app.status(f"Đã khôi phục {n} sidecar từ {d.name}", gd.MAU["xong"])
        messagebox.showinfo("Đã hoàn tác",
                            f"Khôi phục {n} file .xmp.\n\n"
                            "Nhớ chạy lại Read Metadata from File trong Lightroom "
                            "để catalog khớp với file.")
