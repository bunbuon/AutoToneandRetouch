#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""man_retouch.py — Màn Retouch: lớp RetouchWindow (tách từ autotone_gui.py, 7/10).

Giai đoạn 2 tái cấu trúc: autotone_gui.py 9.500 dòng gồm vỏ cửa sổ + màn
Cân tone (App) VÀ cả màn Retouch (RetouchWindow, ~3.400 dòng). Màn Retouch chỉ
chạm vào App qua ba chỗ — app.status(), app.folder(), app._bat_menu() — và
ba khung chứa App đưa vào lúc dựng (ben / thanh / chan), nên tách ra là sạch.

autotone_gui nạp module này LƯỜI trong App._lam_retouch (bản --khong-retouch
không mang retouch / xem_truoc); hoi_nut, _RE_TIEN_DO, _so_muc, _cung_thu_muc
đi cùng vì chỉ màn này dùng. Bài kiểm vá hoi_nut thì vá man_retouch.hoi_nut.
"""

from __future__ import annotations

import os
import queue
import re
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import giao_dien as gd

from typing import TYPE_CHECKING

from giao_dien import Khung, open_in_explorer
from hop_thoai import TaiTaiNguyenDialog

if TYPE_CHECKING:                                            # chỉ cho chú thích kiểu
    from autotone_gui import App


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
    -> mã của nút được bấm; None khi đóng cửa sổ / Esc."""
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

    for ma, nhan in reversed(nut):
        ttk.Button(hang, text=nhan, command=lambda m=ma: chon(m)).pack(
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


class RetouchWindow(Khung):
    """Chặng cuối: đưa thư mục Lightroom vừa Export sang tool retouch.

    KHÔNG TỰ ĐẾM ẢNH ĐÃ LÀM
        duong_ong.chay() bên tool retouch đã tự bỏ qua ảnh đã có kết quả trong
        thư mục ra. Cửa sổ này chỉ ĐỌC lại con số đó để báo trước còn bao nhiêu
        tấm — tự lọc một lần nữa ở đây là hai nơi cùng quyết định một việc, và
        khi hai nơi lệch nhau thì không ai biết bên nào đúng.

    TIẾN ĐỘ ĐO BẰNG SỐ FILE, KHÔNG PHẢI BẰNG CÁCH ĐỌC LOG
        Log của tool chỉ in dòng khi có ghi chú, ảnh chạy trơn thì im lặng —
        bám vào log là thanh tiến độ đứng yên hàng phút dù máy vẫn chạy. Đếm
        file trong thư mục ra thì luôn đúng, kể cả khi tool đổi cách in log.
    """

    def __init__(self, app: App, cha=None, ben=None, thanh=None, chan=None):
        #[[ cha = trang Retouch trong cua so chinh. Truyen None thi van la con
        #   truc tiep cua App — de doan ma cu con goi RetouchWindow(app) khong
        #   sap (kiem_ghi_de.py).
        #
        #   ben / thanh (toi 3/10, bo cuc Evoto — user: "dua ca phan Retouch
        #   thay doi luon"): noi dat BANG DIEU KHIEN (cot phai cua app) va NUT
        #   CHAY (thanh cong cu). Khong truyen thi dung ngay trong khung nay.
        #]]
        super().__init__(cha if cha is not None else app)
        self.app = app
        #[[ chan = thanh day co dinh o cot phai (Reset / Sync, 5/10). Khong
        #   truyen thi cac nut nam cuoi nhom "Muc ap dung". ]]
        self._chan = chan
        self.title("Retouch — chặng cuối đường ống")
        self.geometry("880x640")
        self.minsize(760, 520)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        import retouch as rt
        self.rt = rt
        self.proc = None
        self.worker: threading.Thread | None = None
        self.log_q: queue.Queue = queue.Queue()
        self.cf = rt.doc_cau_hinh()
        self._keo_dang_hoi = False
        self.nhom_dang = ""                 # "" = thẻ Chung
        self.v_rieng: dict = {}             # (nhóm, kéo) -> mức riêng
        self.v_bat_rieng: dict = {}         # (nhóm, kéo) -> có đặt riêng không
        self._o_the_nhom: list = []
        self._sc_theo: dict = {}
        self._ds_keo: list = []
        self._ds_the: list = []
        self._ds_luoi: list = []
        self._hen_luoi = self._hen_d = self._hen_tt = None
        self._dai_cu = None
        # ảnh lớn
        self._anh_dang: str | None = None     # tấm đang xem (đường dẫn ảnh vào)
        self._anh_kq_duong = None             # bản kết quả đang mở (None: đang xem gốc)
        self._anh_hien = None                 # tấm mà ẢNH LỚN đang thật sự hiện (đĩa / xem trước)
        self._ten_hien = ""
        self._thanh_cu = None
        # xem trước trên ảnh lớn (xem _mo_xem_truoc)
        self._may_xem = None
        self._xem_bat = False
        self._xem_san_sang = False
        self._xem_goc_tool = ""
        self._xem_cho_fp = None               # đã xin mở, chờ "da_mo"
        self._xem_fp = None                   # ảnh tiến trình con đang mở
        self._xem_goc_im = None
        self._xem_ma = 0
        self._xem_dang_tinh = None            # mã yêu cầu đang tính
        self._xem_can_tinh = False            # mức đổi trong lúc đang tính
        self._xem_cuoi = None                 # (fp, mức) đã gửi lần cuối
        self._xem_bo_nhom = False             # tool không nhận mức riêng theo nhóm
        self._hen_xem = self._hen_tinh = None
        self._xem_dang_hien = False           # ảnh lớn đang là bản xem trước
        self._xem_so_mat = 1                  # số mặt tool thấy ở tấm đang xem trước
        self._xem_mat: list = []              # mặt (toạ độ bản 1400 px) của tấm đã mở
        self._xem_mo_dang = None              # đã gửi "mo_anh", chưa có "da_mo"
        self._xem_hong = ""                   # máy xem trước hỏng -> kéo thanh KHÔNG tự thử lại
        self._xem_loi_cuoi = ""               # lỗi lúc khởi động tiến trình con (để nói ra)
        # mức riêng từng ảnh (sáng 4/10 — xem _muc_hieu_luc)
        self._muc_anh: dict = {}              # khoá ảnh -> bộ mức phẳng (dạng muc_day_du)
        self._muc_anh_vao = None              # thư mục vào mà _muc_anh thuộc về
        self._muc_anh_khoa = None
        self._muc_chung_ban = False           # mức chung đổi mà chưa ghi xuống đĩa
        #[[ MUC CHUNG THEO THU MUC VAO (5/10) — khong con o retouch.json dung
        #   chung moi thu muc. Thu muc moi = {} = moi thanh 0. Xem
        #   retouch.doc_muc_chung. ]]
        self._muc_chung_tm: dict = {}
        self._hen_luu_ma = None
        self._dang_nap_muc = False            # đang NẠP mức một tấm vào bảng (không phải người kéo)
        self._nhom_ds: list = []              # [(mã, nhãn)] nhóm mặt, hỏi lúc dựng bảng

        # ---------------------------------------------------------- biến
        #[[ Dung MOI bien TRUOC mot o nao: _dung_thanh_keo doc v_goc,
        #   _dem doc v_ghide / v_dequy, tom tat doc tat ca. ]]
        #[[ THU MUC EXPORT CUA CHINH BUOI NAY THANG cau hinh chung.
        #
        #   retouch.json giu mot khoa "vao" duy nhat cho moi buoi — mo buoi moi
        #   thi no van la thu muc cua buoi truoc. Con trang_thai cua tung buoi
        #   giu thu_muc_export RIENG cua buoi do, tuc dung hon han. Truoc day
        #   khong doc toi no, nen doi buoi ma quen sua o "Vao" la retouch chay
        #   tren anh buoi cu — anh van ra du, khong bao gi.
        #]]
        vao_buoi = ""
        try:
            import trang_thai as tt
            if app.folder():
                vao_buoi = tt.doc(tt.ten_buoi(app.folder())).get("thu_muc_export") or ""
        except Exception:                                    # noqa: BLE001
            vao_buoi = ""
        vao_md = (vao_buoi or self.cf.get("vao")
                  or (str(app.folder()) if app.folder() else ""))
        self.v_vao = tk.StringVar(value=vao_md)
        self.v_ra = tk.StringVar(value=self.cf.get("ra", ""))
        #[[ GHI DE LEN ANH GOC — chi can MOT duong dan. saytool tu choi neu nhan
        #   ca --ghi-de lan thu muc ra, nen o "Ra" phai KHOA LAI (xem
        #   _doi_ghide). Khong lui lai duoc: canh bao rieng + hoi xac nhan luc
        #   bam Chay (start()). ]]
        self.v_ghide = tk.BooleanVar(value=bool(self.cf.get("ghi_de", False)))
        goc = rt.tim_tool()
        self.v_goc = tk.StringVar(value=str(goc) if goc else "")
        self.v_may = tk.StringVar(value=self.cf.get("may", "auto"))
        #[[ SO LUONG: 0 = de saytool tu do may — xem retouch.LUONG_MAC_DINH. ]]
        self.v_luong = tk.IntVar(value=int(self.cf.get("luong", rt.LUONG_MAC_DINH)))
        self.v_che_do = tk.StringVar(
            value=self.cf.get("che_do", rt.CHE_DO_MAC_DINH))
        self.v_lamlai = tk.BooleanVar(value=False)
        self.v_dequy = tk.BooleanVar(value=False)
        #[[ TU RETOUCH ANH MOI (7/10) — xem _bat_theo_doi. Nho qua cac lan mo. ]]
        self.v_tu_moi = tk.BooleanVar(value=bool(self.cf.get("tu_moi", False)))
        self._theo_doi = None
        self._hen_quet_ma = None
        self.v_nhom = tk.StringVar(value="")
        self._export_cu = self.cf.get("theo_export", "")

        # ---------------------------------------------------------- khung
        m = gd.MAU
        try:
            self.configure(style="Toi.TFrame")
        except tk.TclError:
            pass
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        if ben is None:
            ben = ttk.Frame(self, padding=(14, 0, 0, 0))
            ben.grid(row=0, column=1, rowspan=4, sticky="ns")
        if thanh is None:
            thanh = tk.Frame(self, background=m["toi"])
            thanh.grid(row=3, column=0, sticky="e", pady=(8, 0))
        self.ben, self.thanh = ben, thanh
        self._dung_trang()
        self._dung_thanh_cong_cu(thanh)
        self._dung_bang(ben, goc)

        self.v_vao.trace_add("write", lambda *_: self._doi_vao())
        self.v_ra.trace_add("write", lambda *_: (self._nho_thu_muc(), self._hen_dem()))
        self.v_dequy.trace_add("write", lambda *_: self._hen_dem())
        self.v_luong.trace_add("write", lambda *_: self._nhac_luong())
        for b in (self.v_vao, self.v_ra, self.v_ghide, self.v_may, self.v_luong,
                  self.v_che_do, self.v_lamlai, self.v_dequy):
            b.trace_add("write", lambda *_: self._hen_tom_tat())
        self._nhac_luong()
        self._doi_ghide()
        self._doi_vao()
        self._kiem()
        self._canh_bao_keo(self.v_goc.get().strip().strip('"'))
        self.after(150, self._pump)
        self.bind("<Destroy>", self._khi_huy, add="+")
        #[[ Hoi tool NGAY khi mo, o luong nen. Truoc day chi hoi dong bo luc
        #   dung bang: hoi that bai la lang le roi ve ba thanh keo du phong va
        #   khong bao gio thu lai. ]]
        self.after(200, lambda: self._hoi_keo_nen(self.v_goc.get().strip().strip('"'))
                   if self.rt.hop_le(self.v_goc.get().strip().strip('"')) else None)

    # ------------------------------------------------------------ dựng khung
    def _dung_trang(self):
        """Vùng giữa (dáng Evoto): [Ảnh | Nhật ký] · tiến độ ở đầu trang, dải
        báo khi tool chưa dùng được, rồi MỘT ẢNH LỚN với dải ảnh bên dưới.

        #[[ ANH LON + DAI ANH (toi 3/10 — user: "Phan luoi anh cua Retouch hay
        #   lam giong Evoto. 1 anh mo to va luoi anh ben duoi").
        #
        #   Truoc do giua man la luoi anh kin man: nhin duoc ca buoi nhung
        #   khong soi duoc mot tam nao — ma o khau retouch, viec chinh la SOI
        #   (da da sach chua, mat co meo khong). Gio: anh lon o tren (ban ket
        #   qua neu da lam, giu chuot = ban goc), dai anh mot hang o duoi de
        #   chuyen tam. Keo thanh chia len la dai thanh luoi nhieu hang.
        #
        #   Dai anh van la LuoiAnh doc tu rt.ds_anh — cung danh sach voi bo
        #   dem, khong dem lan hai. Bam dup mot tam = bat xem truoc tam do. ]]
        """
        m = gd.MAU
        dau = tk.Frame(self, background=m["toi"])
        dau.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.v_xem = tk.StringVar(value="luoi")
        self.chon_xem = gd.PhanDoan(dau, self.v_xem, [("luoi", "Ảnh"),
                                                      ("nhat_ky", "Nhật ký")],
                                    command=self._doi_xem, nen=m["toi"], deu=False)
        self.chon_xem.pack(side="left")
        self.pb = ttk.Progressbar(dau, mode="determinate", length=180)
        self.pb.pack(side="right")
        self.lbl_tt = gd.NhanGon(dau, text="", anchor="w", background=m["toi"],
                                 foreground=m["mo"], font=gd.CHU)
        self.lbl_tt.pack(side="left", fill="x", expand=True, padx=(14, 14))

        #[[ Tool chua dung duoc thi noi NGAY TREN ANH, khong chi trong nhom
        #   "Tool retouch" (co the dang dong). Chu lay tu lbl_goc — _dong_bo_dai
        #   chep sang, khong viet cau thu hai. ]]
        self.dai_rt = gd.DaiBao(self, nen=m["toi"])
        self.dai_rt.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.btn_chon_tool = self.dai_rt.tao_nut("Chọn thư mục tool…",
                                                 command=self._pick_goc)

        giua = tk.Frame(self, background=m["toi"])
        giua.grid(row=2, column=0, sticky="nsew")
        giua.rowconfigure(0, weight=1)
        giua.columnconfigure(0, weight=1)
        import khung_anh
        import luoi_anh
        self.khung_anh = tk.Frame(giua, background=m["toi"])
        self.khung_anh.grid(row=0, column=0, sticky="nsew")
        #[[ Thanh chia KEO DUOC: dai anh mac dinh mot hang (~120 px); ai can
        #   nhin nhieu tam thi keo len — qua hai hang o la thanh luoi. Nho cao
        #   da keo vao retouch.json (_nho_cao_dai). ]]
        self.chia = tk.PanedWindow(self.khung_anh, orient="vertical", sashwidth=7,
                                   sashrelief="flat", borderwidth=0,
                                   background=m["toi"], opaqueresize=True,
                                   showhandle=False, sashcursor="sb_v_double_arrow")
        self.chia.pack(fill="both", expand=True)
        tren = tk.Frame(self.chia, background=m["toi"])
        self._dung_thanh_xem(tren)
        self.xem = khung_anh.KhungAnh(tren, khi_doi=self._cap_nhat_thanh_xem,
                                      khi_phim=self._buoc_anh)
        self.xem.pack(fill="both", expand=True)
        duoi = tk.Frame(self.chia, background=m["toi"])
        tk.Frame(duoi, background=m["vien"], height=1).pack(fill="x")
        #[[ chon_nhieu: Ctrl / Shift + bam chon NHIEU tam — de "Sync anh da
        #   chon" (sang 4/10). Tam dang xem van la tam nguon. ]]
        self.luoi = luoi_anh.LuoiAnh(duoi, khi_chon=self._chon_anh,
                                     khi_mo=self._xem_mot_anh,
                                     khi_trong=lambda: self._pick(self.v_vao), dai=True,
                                     chon_nhieu=True,
                                     khi_doi_chon=lambda _ds: self._cap_nhat_pham_vi())
        self.luoi.nut_trong.configure(text="Chọn thư mục ảnh đã Export")
        self.luoi.pack(fill="both", expand=True)
        self.chia.add(tren, minsize=220, stretch="always")
        self.chia.add(duoi, minsize=80, height=self._cao_dai_md(), stretch="never")
        self.chia.bind("<ButtonRelease-1>", self._nho_cao_dai, add="+")

        self.khung_log = tk.Frame(giua, background=m["toi"])
        self.khung_log.grid(row=0, column=0, sticky="nsew")
        self.khung_log.rowconfigure(0, weight=1)
        self.khung_log.columnconfigure(0, weight=1)
        self.txt = tk.Text(self.khung_log, wrap="word", height=10, state="disabled",
                           font=("Consolas", 9), background=m["toi2"],
                           foreground=m["chu"], insertbackground=m["chu"],
                           selectbackground=m["nhan_t"], relief="flat",
                           borderwidth=0, highlightthickness=0, padx=12, pady=10)
        self.txt.grid(row=0, column=0, sticky="nsew")
        sc = ttk.Scrollbar(self.khung_log, orient="vertical", command=self.txt.yview,
                           style="Toi.Vertical.TScrollbar")
        sc.grid(row=0, column=1, sticky="ns")
        self.txt.configure(yscrollcommand=sc.set)
        self._doi_xem()

    def _dung_thanh_xem(self, cha):
        """Thanh mỏng dưới ảnh lớn: [trạng thái] tên · cỡ ......... Vào mặt ·
        Vừa khung · 100% · tỉ lệ · Giữ xem gốc · ?"""
        m = gd.MAU
        nen = m["toi"]
        t = tk.Frame(cha, background=nen)
        t.pack(side="bottom", fill="x", pady=(6, 6))
        self.thanh_xem = t
        hoi = gd.NutHoi(t, "Kéo thanh ở bảng phải: ảnh lớn tính lại NGAY theo mức "
                           "đó (bản xem trước). Bấm ✕ trên nhãn “Xem trước” để "
                           "về bản trên đĩa.\n"
                           "Lăn chuột: phóng to / thu nhỏ quanh con trỏ.\n"
                           "Kéo: di chuyển ảnh đang phóng.\n"
                           "Nháy đúp: 100% đúng chỗ bấm ↔ vừa khung.\n"
                           "Giữ chuột trên ảnh (hoặc giữ phím \\): xem ảnh GỐC.\n"
                           "← →: tấm trước / sau · 0: vừa khung · 1: 100% · "
                           "M: vào mặt kế tiếp.\n"
                           "Dải ảnh: Ctrl + bấm chọn thêm, Shift + bấm chọn một "
                           "dãy — để Sync mức.", nen=nen)
        hoi.pack(side="right", padx=(8, 0))
        self.btn_goc = gd.NutTron(t, "Giữ xem gốc", kieu="phu", nen=nen, font=gd.CHU)
        self.btn_goc.pack(side="right", padx=(10, 0))
        #[[ Nut GIU chu khong phai nut bam: an xuong la anh goc, tha ra la
        #   ket qua — so sanh nhanh nhat, khong phai bam hai lan. ]]
        self.btn_goc.bind("<ButtonPress-1>", lambda _e: self.xem.giu_goc(
            self.btn_goc.cget("state") != "disabled"), add="+")
        self.btn_goc.bind("<ButtonRelease-1>", lambda _e: self.xem.giu_goc(False),
                          add="+")
        self.lbl_zoom = tk.Label(t, text="", background=nen, foreground=m["chu"],
                                 font=gd.CHU_SO, width=5, anchor="e")
        self.lbl_zoom.pack(side="right", padx=(8, 0))
        self.btn_100 = gd.NutTron(t, "100%", kieu="chu", nen=nen, font=gd.CHU,
                                  command=lambda: self.xem.phong_100())
        self.btn_100.pack(side="right", padx=(4, 0))
        self.btn_vua = gd.NutTron(t, "Vừa khung", kieu="chu", nen=nen, font=gd.CHU,
                                  command=lambda: self.xem.vua_khung())
        self.btn_vua.pack(side="right", padx=(4, 0))
        self.btn_mat = gd.NutTron(t, "Vào mặt", kieu="phu", nen=nen, font=gd.CHU,
                                  command=lambda: self.xem.vao_mat())
        self.btn_mat.pack(side="right")
        self.btn_mat.goi_y = gd.GoiY(self.btn_mat, "Nhảy tới khuôn mặt kế tiếp (mặt "
                                                   "to trước), phóng đủ để soi da.")
        self.chip_anh = tk.Label(t, text="", font=gd.CHU_NHO, padx=8, pady=2,
                                 background=nen, foreground=m["mo"])
        self.chip_anh.pack(side="left")
        #[[ Dang xem truoc thi chip mang dau ✕: bam la tat xem truoc, anh lon ve
        #   ban tren dia. Thay cho nut "Xem trước" da bo (sang 4/10). ]]
        self.chip_anh.bind("<Button-1>", lambda _e: self._tat_xem_truoc()
                           if self._xem_bat else None)
        self.lbl_ten_anh = gd.NhanGon(t, text="", anchor="w", background=nen,
                                      foreground=m["chu"], font=gd.CHU)
        self.lbl_ten_anh.pack(side="left", fill="x", expand=True, padx=(8, 8))
        for b in (self.btn_goc, self.btn_100, self.btn_vua, self.btn_mat):
            b.configure(state="disabled")

    MAU_CHIP = {"xong": ("#1d3a28", "#9be3b5"), "chua": ("#2c2f34", "#a3a6ab"),
                "xem": ("#3a3214", "#ffde17"), "loi": ("#3a1d1b", "#f3b7b2"),
                "": (None, None)}

    def _dat_chip(self, loai: str, chu: str = ""):
        nen, mau = self.MAU_CHIP.get(loai, (None, None))
        if not chu or nen is None:
            self.chip_anh.configure(text="", background=gd.MAU["toi"], cursor="")
            self.chip_anh.pack_forget()
            return
        self.chip_anh.configure(text=chu, background=nen, foreground=mau,
                                cursor="hand2" if self._xem_bat else "")
        if not self.chip_anh.winfo_manager():
            self.chip_anh.pack(side="left", before=self.lbl_ten_anh)

    def _dat_chip_xem(self, chu: str, loai: str = "xem"):
        """Chip lúc đang xem trước — luôn kèm ✕ (bấm để tắt)."""
        self._dat_chip(loai, (f"Xem trước · {chu}" if loai == "xem" else chu) + "   ✕")

    def _cap_nhat_thanh_xem(self):
        """Khung ảnh vừa đổi (tỉ lệ / nạp xong / mặt) -> thanh dưới ảnh."""
        x = getattr(self, "xem", None)
        if x is None:
            return
        kt = x.kich_thuoc()
        co = kt is not None and not x.dang_trong()
        s = x.ty_le() if co else 0.0
        zoom = ""
        if co:
            zoom = f"{s * 100:.0f}%" if s >= 0.095 else f"{s * 100:.1f}%"
        ten = self._ten_hien
        if co and ten:
            ten += f"  ·  {kt[0]}×{kt[1]}"
            if self._xem_dang_hien:
                ten += " (bản xem trước)"
            if x.i_mat >= 0 and x.so_mat():
                ten += f"  ·  mặt {x.i_mat + 1}/{x.so_mat()}"
        tt = (zoom, ten, co and not x.la_vua(), co and abs(s - 1.0) > 1e-3,
              co and x.so_mat() > 0, co and x.co_truoc())
        if tt == self._thanh_cu:
            return
        self._thanh_cu = tt
        self.lbl_zoom.configure(text=zoom)
        self.lbl_ten_anh.configure(text=ten)
        for b, bat in ((self.btn_vua, tt[2]), (self.btn_100, tt[3]),
                       (self.btn_mat, tt[4]), (self.btn_goc, tt[5])):
            moi = "normal" if bat else "disabled"
            if b.cget("state") != moi:
                b.configure(state=moi)

    def _cao_dai_md(self) -> int:
        try:
            h = int(self.cf.get("cao_dai_anh") or 0)
        except (TypeError, ValueError):
            h = 0
        return h if 80 <= h <= 2000 else round(gd.don_vi(self) * 7.6)

    def _nho_cao_dai(self, _e=None):
        """Thả thanh chia: nhớ cao dải ảnh cho lần mở sau."""
        try:
            y = self.chia.sash_coord(0)[1]
            h = self.chia.winfo_height() - y - int(self.chia.cget("sashwidth"))
        except (tk.TclError, IndexError, ValueError):
            return
        if h >= 80 and h != self.cf.get("cao_dai_anh"):
            self.cf["cao_dai_anh"] = h
            try:
                self.rt.ghi_cau_hinh({"cao_dai_anh": h})
            except Exception:                                # noqa: BLE001
                pass

    def _doi_xem(self):
        """[Ảnh | Nhật ký] — cùng một lượt chạy, hai cách nhìn."""
        if self.v_xem.get() == "nhat_ky":
            self.khung_anh.grid_remove()
            self.khung_log.grid()
        else:
            self.khung_log.grid_remove()
            self.khung_anh.grid()

    def _dung_thanh_cong_cu(self, thanh):
        """▶ Chạy retouch (nút vàng) · ⋯ — trên thanh công cụ của app.

        #[[ KHONG CON NUT "XEM TRUOC" (sang 4/10 — user: "bo nut xem truoc. Vi
        #   khi keo se load luon vao anh de thay dc luon"). Keo mot thanh o bang
        #   phai la anh lon tinh lai NGAY (_nguoi_doi_muc -> _mo_xem_truoc tu
        #   dong), nhu Evoto. Tat: bam chip "Xem trước · …  ✕" duoi anh lon.
        #   Van tinh bang CHINH saytool (xem_truoc.MayXem) — khong dung lai buoc
        #   nao ben nay. ]]
        """
        nen = gd.nen_cua(thanh)
        self.btn_stop = gd.NutTron(thanh, "■  Dừng", kieu="chu", nen=nen,
                                   command=self.stop)
        self.btn_stop.configure(state="disabled")
        self.btn_run = gd.NutTron(thanh, "▶  Chạy retouch", kieu="chinh", nen=nen,
                                  command=self.start)
        self.btn_run.pack(side="left", padx=(0, 6))
        self.menu_rt = tk.Menu(self, tearoff=0)
        for nhan, lenh in (("Kiểm tra tool", lambda: self._kiem(chay_thu=True)),
                           ("Đọc lại tính năng", self.do_doc_lai_keo),
                           (None, None),
                           ("Mở thư mục vào", lambda: self._mo_thu_muc(self.v_vao)),
                           ("Mở thư mục ra", lambda: self._mo_thu_muc(self.v_ra)),
                           #[[ 5/10 — user: "o dau 3 cham chua thay phan Tai ban
                           #   tang toc GPU". Muc nay truoc chi o menu ··· cua Can
                           #   tone; Retouch moi la cho can no (keo thanh / Chay
                           #   retouch tren CPU cham). ]]
                           (None, None),
                           ("Tải bản tăng tốc GPU…",
                            lambda: getattr(self.app, "tai_gpu", lambda: None)())):
            if nhan is None:
                self.menu_rt.add_separator()
            else:
                self.menu_rt.add_command(label=nhan, command=lenh)
        self.btn_them_rt = gd.NutTron(
            thanh, "", icon="them", kieu="chu", nen=nen,
            command=lambda: self.app._bat_menu(self.menu_rt, self.btn_them_rt))
        self.btn_them_rt.goi_y = gd.GoiY(
            self.btn_them_rt, "Thêm: kiểm tra tool, đọc lại tính năng, mở thư mục, "
                              "tải bản tăng tốc GPU…")
        self.btn_them_rt.pack(side="left")

    def _dat_dang_chay(self, co: bool):
        """Đang chạy: nút Chạy khoá, nút Dừng hiện ra; xong thì ngược lại."""
        self.btn_run.configure(state="disabled" if co else "normal")
        self.btn_stop.configure(state="normal" if co else "disabled")
        try:
            if co:
                self.btn_stop.pack(side="left", padx=(0, 6), before=self.btn_run)
            else:
                self.btn_stop.pack_forget()
        except tk.TclError:
            pass

    @staticmethod
    def _dat_cho(w, truoc=None, **kw):
        """Nhớ chỗ pack của một ô hiện / ẩn được — pack_forget quên mất chỗ,
        pack lại không có before= là ô chạy xuống cuối nhóm."""
        w._cho = (truoc, kw)

    @staticmethod
    def _hien_an(w, co: bool):
        truoc, kw = getattr(w, "_cho", (None, {}))
        try:
            if co and not w.winfo_manager():
                them = {}
                if truoc is not None and truoc.winfo_manager():
                    them["before"] = truoc
                w.pack(**kw, **them)
            elif not co and w.winfo_manager():
                w.pack_forget()
        except tk.TclError:
            pass

    def _dung_bang(self, ben, goc):
        """Bảng điều khiển của mô-đun Retouch — MỘT CỘT, nhóm thu gọn, như
        bảng Cân tone: Thư mục · Mức áp dụng · Máy & cách chạy · Tool retouch.

        #[[ Tu "Muc ap dung" tro xuong la chuyen it doi giua cac buoi — dong
        #   san, moi nhom mot dong tom tat. Hai nhom dau mo san: thu muc phai
        #   dung buoi, muc ap dung la thu dang chinh. Canh bao nam o nhom dong
        #   (ep so luong, tool chua dung duoc) thi dong tom tat noi ra. ]]
        """
        m = gd.MAU
        rt = self.rt
        WRAP = 300
        self._nhom_rt: dict = {}

        def nhom(ma, tieu_de, mo):
            n = gd.Nhom(ben, tieu_de, mo=mo)
            n.pack(fill="x", anchor="w")
            self._nhom_rt[ma] = n
            return n.than

        def hoi(cha_, chu):
            gd.NutHoi(cha_, chu).pack(side="left", padx=(6, 0))

        def ct(cha_, bien, chu, mo="", lenh=None):
            o = ttk.Frame(cha_)
            o.pack(fill="x", anchor="w", pady=2)
            cong = gd.CongTac(o, bien, command=lenh)
            cong.pack(side="right", padx=(12, 0))
            lbl = ttk.Label(o, text=chu)
            lbl.pack(side="left")
            lbl.bind("<Button-1>", lambda _e: cong.bat_tat())
            if mo:
                hoi(o, mo)
            return o

        def o_duong(cha_, nhan, bien, mo, lenh):
            dong = ttk.Frame(cha_)
            dong.pack(fill="x", pady=(6, 0))
            lbl = ttk.Label(dong, text=nhan)
            lbl.pack(side="left")
            hoi(dong, mo)
            o = ttk.Frame(cha_)
            o.pack(fill="x", pady=(3, 0))
            nut = gd.NutTron(o, "Chọn…", kieu="phu", font=gd.CHU, command=lenh)
            nut.pack(side="right", padx=(6, 0))
            e = ttk.Entry(o, textvariable=bien)
            e.pack(side="left", fill="x", expand=True)
            return dong, lbl, e, nut

        g_tm = nhom("thu_muc", "Thư mục", True)
        g_keo = nhom("keo", "Mức áp dụng", True)
        g_chay = nhom("chay", "Máy & cách chạy", False)
        g_tool = nhom("tool", "Tool retouch", False)

        # ------------------------------------------------ thư mục
        _d, _l, self.e_vao, self.btn_vao = o_duong(
            g_tm, "Vào", self.v_vao,
            "Thư mục Lightroom vừa Export ra — retouch lấy ảnh từ đây. Mở buổi "
            "nào thì tự theo thư mục Export của buổi đó.",
            lambda: self._pick(self.v_vao))
        #[[ MOT DONG NOI KHI O "VAO" LECH VOI THU MUC EXPORT CUA BUOI. KHONG tu
        #   ghi de len cai nguoi dung da go — chi noi va de mot nut. ]]
        self.o_theo_export = gd.TheBao(g_tm, muc="canh")
        self.lbl_theo_export = self.o_theo_export.nhan
        self.btn_theo_export = self.o_theo_export.tao_nut(
            "Dùng thư mục Export", self._nhan_theo_export)
        hang_ra, self.lbl_ra, self.e_ra, self.btn_ra = o_duong(
            g_tm, "Ra", self.v_ra,
            "Nơi lưu ảnh đã retouch. Bật “Ghi đè lên ảnh gốc” thì không cần ô "
            "này.", lambda: self._pick(self.v_ra))
        self._dat_cho(self.o_theo_export, truoc=hang_ra, fill="x", pady=(6, 0))
        o = ct(g_tm, self.v_ghide, "Ghi đè lên ảnh gốc",
               "Không cần thư mục ra: ảnh retouch THAY THẾ ảnh gốc. Không lùi lại "
               "được — lúc bấm Chạy sẽ hỏi lại kèm số ảnh và đường dẫn.",
               lenh=self._doi_ghide)
        o.pack_configure(pady=(10, 2))
        self.lbl_ghide = ttk.Label(g_tm, style="Canh.TLabel", text="",
                                   wraplength=WRAP, justify="left")
        self._dat_cho(self.lbl_ghide, fill="x", pady=(2, 2))
        self.o_tu_moi = ct(
            g_tm, self.v_tu_moi, "Tự retouch ảnh mới thêm vào",
            "Bật rồi bấm Chạy retouch: chạy xong app vẫn THEO DÕI thư mục Vào. "
            "Ảnh nào mới chép vào — kể cả trong lúc đang chạy — được tự retouch "
            "bằng MỨC CHUNG (các thanh ở thẻ Chung lúc bấm Chạy, không dùng mức "
            "riêng giới tính) rồi xuất ra, hoặc ghi đè nếu đang bật ghi đè. Ảnh "
            "có sẵn lúc bấm Chạy không bị tính là ảnh mới. Bấm Dừng để thôi theo "
            "dõi.",
            lenh=self._doi_tu_moi)

        # ------------------------------------------------ mức áp dụng
        #[[ THANH KEO DUNG DONG, theo danh sach saytool DANG co (rt.thanh_keo).
        #   Hoi lan dau ton vai giay (saytool import torch) nen hoi o luong nen
        #   luc mo the Retouch — xem _hoi_keo_nen. ]]
        self.khung_keo = g_keo
        #[[ PHAM VI + SYNC (sang 4/10 — user: "can them nut Sync All cac hieu
        #   ung da keo cho cac anh duoc chon hoac tat ca"). NHU EVOTO: keo thanh
        #   la chinh ANH DANG XEM (anh khac khong doi); "Sync anh da chon" chep
        #   muc cua anh dang xem sang cac tam Ctrl / Shift + bam o dai anh;
        #   "Sync tat ca" chep cho ca thu muc va lay lam MUC CHUNG. Anh chua
        #   chinh rieng thi theo muc chung (retouch.json "muc" — nhu truoc, nen
        #   ai khong dung toi Sync thi ket qua y het truoc day). ]]
        o_pv = ttk.Frame(g_keo)
        o_pv.pack(fill="x", pady=(4, 0))
        #[[ Ten tep dai thi XUONG DONG, khong day bang dieu khien phinh ra (anh
        #   lon / dai anh nhay cot). Nut "Về mức chung" o DONG RIENG ben duoi —
        #   cung dong voi ten tep la vuot be ngang cot (do 4/10: 433 px thay vi
        #   394). ]]
        self.lbl_pham_vi = ttk.Label(o_pv, text="", wraplength=WRAP - 20,
                                     justify="left", anchor="w")
        self.lbl_pham_vi.pack(side="left")
        hoi(o_pv, "Kéo thanh là chỉnh ẢNH ĐANG XEM (như Evoto) — ảnh lớn tính "
                  "lại ngay. Mở thư mục mới thì mọi thanh ở 0; tự kéo tính năng "
                  "muốn dùng.\n\n"
                  "Reset về 0: đưa mọi thanh của ảnh đang xem về 0.\n\n"
                  "Sync ảnh đã chọn: chép mức của ảnh đang xem sang các tấm đang "
                  "chọn ở dải ảnh — Ctrl + bấm để chọn thêm, Shift + bấm để chọn "
                  "một dãy, Ctrl+A chọn hết.\n\n"
                  "Lúc chạy, ảnh khác mức nhau thì tool chạy theo từng nhóm mức "
                  "(mỗi nhóm một lượt).")
        #[[ SYNC + RESET CHUYEN XUONG DUOI (user 5/10, nhu Evoto): hang the nhom
        #   + bang thanh keo o tren, thanh cong cu (Reset / Ve muc chung / Sync)
        #   nam DUOI bang keo. Nen cac nut nay dung o cuoi g_keo — xem o_duoi_keo
        #   phia sau _dung_thanh_keo. BO "Sync tat ca": Sync mac dinh cho ANH DANG
        #   CHON (user: "khong can toi nut Sync Tat ca"). ]]
        self.o_the = ttk.Frame(g_keo)
        self.o_the.pack(fill="x", pady=(4, 0))
        #[[ BANG THANH KEO KHONG PHAI CUA saytool THI PHAI NOI (9/9: may co
        #   0.9.5 sau thanh keo ma app hien dung ba, khong mot dong nao noi vi
        #   sao) — kem nut thu lai. ]]
        self.o_canh_keo = gd.TheBao(g_keo, muc="canh")
        self.lbl_keo = self.o_canh_keo.nhan
        self.btn_keo_lai = self.o_canh_keo.tao_nut("Đọc lại tính năng",
                                                   self.do_doc_lai_keo)
        self._dat_cho(self.btn_keo_lai, anchor="w", pady=(6, 0))
        self.o_hang_keo = ttk.Frame(g_keo)
        self.o_hang_keo.pack(fill="x")
        self._dat_cho(self.o_canh_keo, truoc=self.o_hang_keo, fill="x", pady=(6, 2))
        self.v_muc = {}
        self._o_keo = []            # các ô đã dựng, để dựng lại khi đổi thư mục
        self._hang_keo = self._dung_thanh_keo(goc)

        #[[ RESET + SYNC DOCK O DAY COT PHAI (5/10, nhu Evoto — user: "nut Reset
        #   va Sync anh de dock o cuoi luon. Bo ve muc chung di"). Nam o thanh day
        #   CO DINH (App.chan_phai_rt, ngoai vung cuon) — luon thay, khong phai
        #   cuon. Khong co thanh day (RetouchWindow dung rieng) thi dat cuoi nhom
        #   "Muc ap dung". Nut "Ve muc chung" BO: muc chung moi thu muc = 0 nen no
        #   trung voi Reset; ham _ve_muc_chung van giu cho ma cu / test. ]]
        if self._chan is not None:
            o_duoi = self._chan
        else:
            o_duoi = ttk.Frame(g_keo)
            o_duoi.pack(fill="x", pady=(8, 2))
        self.btn_reset = gd.NutTron(o_duoi, "Reset về 0", kieu="phu", font=gd.CHU,
                                    command=self._reset_anh_0)
        self.btn_reset.pack(side="left")
        self.btn_reset.goi_y = gd.GoiY(
            self.btn_reset, "Đưa mọi thanh của ẢNH ĐANG XEM về 0 (tắt hết tính "
                            "năng). Muốn reset nhiều ảnh thì Reset rồi bấm Sync.")
        self.btn_sync_chon = gd.NutTron(o_duoi, "Sync ảnh đã chọn", kieu="phu",
                                        font=gd.CHU, command=self._sync_chon)
        self.btn_sync_chon.pack(side="left", padx=(8, 0))
        self.btn_sync_chon.goi_y = gd.GoiY(
            self.btn_sync_chon, "Chép mức của ảnh đang xem sang các tấm đang chọn "
                                "ở dải ảnh (Ctrl / Shift + bấm để chọn nhiều tấm; "
                                "Ctrl+A chọn hết).")

        # ------------------------------------------------ máy & cách chạy
        dong = ttk.Frame(g_chay)
        dong.pack(fill="x", pady=(4, 0))
        ttk.Label(dong, text="Máy").pack(side="left")
        hoi(dong, "auto: tự dùng card đồ hoạ nếu có. cuda: card NVIDIA. mps: Mac "
                  "chip Apple. cpu: chỉ dùng CPU — chậm, nhưng máy nào cũng chạy.")
        self.chon_may = gd.PhanDoan(g_chay, self.v_may,
                                    [(x, x) for x in ("auto", "cuda", "mps", "cpu")])
        self.chon_may.pack(fill="x", pady=(3, 0))
        #[[ SO LUONG: 0 = de saytool tu do may (0.9.5 chan boi ca so loi LAN bo
        #   nho con trong that). Ep mot con so la VO HIEU HOA phan tu do do —
        #   nen noi ra khi dang ep, va de mot nut ve 0 (_nhac_luong). ]]
        dong = ttk.Frame(g_chay)
        dong.pack(fill="x", pady=(10, 0))
        ttk.Label(dong, text="Số luồng").pack(side="left")
        hoi(dong, "0 = để tool tự dò theo số lõi và bộ nhớ còn trống — khuyên "
                  "dùng. Ép một con số là tắt phần tự dò đó.")
        o = ttk.Frame(g_chay)
        o.pack(fill="x", pady=(3, 0))
        ttk.Spinbox(o, from_=0, to=16, width=4, textvariable=self.v_luong,
                    state="readonly").pack(side="left")
        self.btn_luong0 = gd.NutTron(o, "về 0", kieu="phu", font=gd.CHU,
                                     command=lambda: self.v_luong.set(0))
        self._dat_cho(self.btn_luong0, side="left", padx=(8, 0))
        self.lbl_luong = ttk.Label(g_chay, foreground="#8a8a8a", wraplength=WRAP,
                                   justify="left")
        self.lbl_luong.pack(fill="x", pady=(3, 0))
        #[[ CHE DO — tham so cua 0.9.5. "tiet_kiem" la duong thoat that su khi
        #   may dang ban: mot luong, o nho nhat. ]]
        dong = ttk.Frame(g_chay)
        dong.pack(fill="x", pady=(10, 0))
        ttk.Label(dong, text="Chế độ").pack(side="left")
        hoi(dong, "Tự động: tool tự đo máy rồi chọn — nên dùng. Tiết kiệm: một "
                  "luồng, ô nhớ nhỏ nhất — cho máy yếu hoặc khi đang chạy việc "
                  "khác. Nhanh: dám dùng nhiều bộ nhớ hơn.")
        self.chon_che_do = gd.PhanDoan(
            g_chay, self.v_che_do,
            [(c, self.TEN_CHE_DO.get(c, c)) for c in rt.CHE_DO])
        self.chon_che_do.pack(fill="x", pady=(3, 0))
        o = ct(g_chay, self.v_lamlai, "Làm lại cả ảnh đã có kết quả",
               "Mặc định tool bỏ qua ảnh đã có trong thư mục ra — chạy lại là đi "
               "tiếp từ chỗ dừng. Bật để làm lại từ đầu.")
        o.pack_configure(pady=(10, 2))
        ct(g_chay, self.v_dequy, "Cả thư mục con")

        # ------------------------------------------------ tool retouch
        o = ttk.Frame(g_tool)
        o.pack(fill="x", pady=(4, 0))
        gd.NutTron(o, "Chọn…", kieu="phu", font=gd.CHU,
                   command=self._pick_goc).pack(side="right", padx=(6, 0))
        ttk.Entry(o, textvariable=self.v_goc).pack(side="left", fill="x", expand=True)
        self.lbl_goc = ttk.Label(g_tool, foreground=m["mo"], justify="left",
                                 wraplength=WRAP)
        self.lbl_goc.pack(fill="x", pady=(6, 2))
        #[[ NOI RA KHI TOOL DA CHUYEN CHO (8/9: F:\ToolCloneEvoto ->
        #   F:\Claude AI\ToolCloneEvoto). rt.tim_tool() tu do lai va ghi de —
        #   nhung lang le doi duong dan duoi tay nguoi dung cung la mot kieu
        #   hong. Bao dung mot lan roi quen (rt.quen_da_chuyen()). ]]
        chuyen = rt.da_chuyen_cho()
        if chuyen:
            cu_, moi_ = chuyen
            gd.TheBao(g_tool, muc="canh",
                      chu=f"Tool đã chuyển chỗ: {cu_}  →  {moi_}. App tự dò ra và "
                          f"ghi lại. Nếu đây không phải bản anh muốn dùng, bấm "
                          f"“Chọn…”.").pack(fill="x", pady=(6, 2))
            rt.quen_da_chuyen()

        #[[ Cot rong BANG cot Can tone — doi mo-dun ma cot doi be ngang la luoi
        #   anh nhay cot. Thanh chan dung be ngang cua bang Can tone. ]]
        rong = int(getattr(self.app, "_rong_bang", 0) or 0)
        if rong and ben is not self:
            ttk.Frame(ben, width=rong, height=1).pack(anchor="w")
            for n in self._nhom_rt.values():
                n.l_tom.configure(wraplength=max(200, rong - 20))
        self._tom_tat_rt()
        self._cap_nhat_pham_vi()

    TEN_CHE_DO = {"auto": "Tự động", "tiet_kiem": "Tiết kiệm", "nhanh": "Nhanh"}
    #[[ Ba the nhom mot hang: bang dieu khien rong bang bang Can tone (~360 px
    #   ruot) — sau vien mot hang ("Nữ lớn tuổi", "Nam lớn tuổi"…) la vuot cot,
    #   cot phinh ra va luoi anh nhay cot khi doi mo-dun. ]]
    MOI_HANG_THE = 3

    def _hen_tom_tat(self):
        if self._hen_tt is None:
            try:
                self._hen_tt = self.after_idle(self._tom_tat_rt)
            except tk.TclError:
                pass

    def _tom_tat_rt(self):
        """Dòng tóm tắt của từng nhóm khi đóng — thu gọn mà không giấu."""
        self._hen_tt = None
        ds = getattr(self, "_nhom_rt", None)
        if not ds:
            return

        def ten(s):
            s = str(s or "").strip().strip('"')
            return Path(s).name if s else "—"

        if self.v_ghide.get():
            tm = f"Ghi đè lên ảnh gốc · {ten(self.v_vao.get())}"
        else:
            tm = f"{ten(self.v_vao.get())} → {ten(self.v_ra.get())}"
        bat = []
        for t, nhan, _md, _g in self._ds_keo:
            v = self.v_muc.get(t)
            try:
                gt = float(v.get()) if v is not None else 0.0
            except (tk.TclError, ValueError):
                gt = 0.0
            if gt > 0:
                bat.append(f"{nhan} {gt:.0f}")
        rieng = sorted({self.nhan_nhom(nh) for (nh, _t), b in self.v_bat_rieng.items()
                        if b.get()})
        keo = (" · ".join(bat) if bat else "Mọi tính năng đang ở 0") + (
            f" · riêng: {', '.join(rieng)}" if rieng else "")
        n_rieng = len(getattr(self, "_muc_anh", {}) or {})
        if n_rieng:
            keo += f" · {n_rieng} ảnh có mức riêng"
        try:
            n = int(self.v_luong.get())
        except (tk.TclError, ValueError):
            n = 0
        chay = [f"Máy {self.v_may.get()}",
                "tự dò luồng" if n <= 0 else f"⚠ ép {n} luồng",
                self.TEN_CHE_DO.get(self.v_che_do.get(), self.v_che_do.get())]
        if self.v_lamlai.get():
            chay.append("làm lại ảnh đã có")
        if self.v_dequy.get():
            chay.append("cả thư mục con")
        try:
            tool = (str(self.lbl_goc.cget("text")).strip().splitlines() or ["—"])[0]
        except (tk.TclError, AttributeError):
            tool = "—"
        for ma, chu in (("thu_muc", tm), ("keo", keo), ("chay", " · ".join(chay)),
                        ("tool", tool)):
            if ma in ds:
                ds[ma].dat_tom_tat(chu)

    def _dong_bo_dai(self):
        """Tool chưa dùng được -> dải báo trên lưới nói ra (chữ của lbl_goc)."""
        try:
            chu = str(self.lbl_goc.cget("text") or "")
            mau = str(self.lbl_goc.cget("foreground") or "")
        except tk.TclError:
            return
        if (chu, mau) == self._dai_cu:
            return
        self._dai_cu = (chu, mau)
        muc = gd.DaiBao._muc_cua(mau)
        dong = next((d.strip() for d in chu.splitlines() if d.strip()), "")
        if muc == "loi" and dong:
            moi = "Chưa dùng được tool retouch — " + dong
        elif muc == "canh" and dong:
            moi = dong
        else:
            moi = ""
        self.dai_rt.nhan.configure(text=moi, foreground=mau or gd.MAU["mo"])
        #[[ Nut "Chon thu muc tool…" chi khi tool CHUA dung duoc — dang chay
        #   thu ("Dang chay thu...") thi khong co gi de chon. ]]
        (self.btn_chon_tool.pack if muc == "loi" and moi
         else self.btn_chon_tool.pack_forget)()
        self._tom_tat_rt()

    def _hen_dem(self):
        """Đếm lại + vẽ lại lưới SAU khi người dùng ngừng gõ (0,3 s)."""
        if self._hen_d is not None:
            try:
                self.after_cancel(self._hen_d)
            except tk.TclError:
                pass
        try:
            self._hen_d = self.after(300, self._dem_hen)
        except tk.TclError:
            self._hen_d = None

    def _dem_hen(self):
        self._hen_d = None
        try:
            self._dem()
        except Exception:                                    # noqa: BLE001
            traceback.print_exc()

    def _ve_luoi(self):
        """Đổ danh sách ảnh vào dải ảnh (rt.ds_anh — cùng cách lọc với tool),
        giữ tấm đang xem; chưa xem tấm nào thì mở tấm đầu lên ảnh lớn."""
        self._hen_luoi = None
        ghi_de = bool(self.v_ghide.get())
        o = [{"path": str(p), "ten": p.name, "dev": None, "canh": None, "loai": "",
              "sao1": False, "bo": "",
              "dau": "✓ đã làm" if (xong and not ghi_de) else "",
              "rieng": self._khoa(p) in self._muc_anh}
             for p, xong in self._ds_luoi]
        self.luoi.dat_ds(o, giu_cuon=True)
        if not o:
            vao = self.v_vao.get().strip().strip('"')
            if not vao:
                chu = "Chưa chọn thư mục ảnh đã Export."
            elif Path(vao).is_dir():
                chu = f"Thư mục vào chưa có ảnh nào:\n{vao}"
            else:
                chu = f"Không có thư mục:\n{vao}"
            self.luoi.dat_trong("Chưa có ảnh.", co_nut=False)
            self.xem.dat_trong(chu, nut="Chọn thư mục ảnh đã Export",
                               lenh=lambda: self._pick(self.v_vao))
            co_anh = self._anh_dang is not None
            self._anh_dang = None
            self._anh_hien = None
            self._ten_hien = ""
            if self._xem_bat:
                self._xem_bat = False
            self._dat_chip("")
            self._cap_nhat_thanh_xem()
            if co_anh:
                #[[ Het anh: bang thanh keo ve MUC CHUNG (keo luc nay la dat muc
                #   chung), khong de nguyen muc rieng cua tam vua mat. ]]
                self._nap_muc_vao_bang(self._muc_chung_day_du())
            self._cap_nhat_pham_vi()
            return
        co = {x["path"] for x in o}
        dang = self._anh_dang if self._anh_dang in co else None
        if dang is None:
            #[[ Mo len la co ANH ngay, nhu Evoto — khong de khung lon trong
            #   bat nguoi dung di bam mot tam truoc. ]]
            dang = o[0]["path"]
            self.luoi.chon(dang)
            self._chon_anh(dang)
            return
        if self.luoi.dang_chon != dang:
            self.luoi.chon(dang, cuon_toi=False)
        if not self._xem_bat:
            #[[ Tam DANG XEM vua co ket qua (luot chay vua ghi ra), hay doi
            #   thu muc ra -> mo lai ban ket qua, giu nguyen cho dang soi. Doc
            #   ket qua hong (dang ghi do) thi thu lai o lan dem sau. ]]
            kq = self._duong_kq(dang)
            if (str(kq) if kq else None) != (str(self._anh_kq_duong)
                                             if self._anh_kq_duong else None) \
                    or (kq is not None and self.xem.loi):
                self._hien_anh_dia(dang, giu_khung=True)

    def _duong_kq(self, path):
        """Bản kết quả CÓ THẬT của một ảnh vào (None: chưa làm / ghi đè)."""
        if self.v_ghide.get():
            return None
        vao = self.v_vao.get().strip().strip('"')
        ra = self.v_ra.get().strip().strip('"')
        if not vao or not ra:
            return None
        try:
            q = self.rt.duong_ket_qua(path, vao, ra, self.v_dequy.get())
        except (ValueError, OSError):
            return None
        return q if (q is not None and q.is_file()) else None

    def _chon_anh(self, path: str):
        """Bấm một tấm trong dải ảnh (hoặc ← →) -> lên ảnh lớn, và bảng thanh
        kéo hiện MỨC CỦA TẤM ĐÓ (như Evoto: kéo là chỉnh tấm đang xem)."""
        self._anh_dang = path
        self._ten_hien = Path(path).name
        self._nap_muc_vao_bang(self._muc_hieu_luc(path))
        self._cap_nhat_pham_vi()
        if self._xem_bat and getattr(self, "_xem_tu_dong", False):
            #[[ Xem truoc dang bat TU DONG (tam truoc co san thong so, nguoi
            #   dung chua keo gi): sang tam moi thi TAM DO tu quyet — co ket qua
            #   thi hien ket qua, co thong so thi xem truoc, muc 0 thi anh goc.
            #   Tat mem (giu may xem truoc); tin ket qua cu ve muon se bi bo vi
            #   _xem_bat da tat. ]]
            self._xem_bat = False
            if self._hen_tinh is not None:
                try:
                    self.after_cancel(self._hen_tinh)
                except tk.TclError:
                    pass
                self._hen_tinh = None
        if self._xem_bat:
            #[[ So voi tam ANH LON DANG HIEN, khong phai tam tien trinh con
            #   dang mo: luot nhanh qua lai thi hai tam do khac nhau — so nham
            #   la ten tam moi nam duoi anh cua tam cu. ]]
            self._xem_gui_mo(path, hien_dia=path != self._anh_hien)
            return
        self._hien_anh_dia(path)
        if self._tu_xem_neu_co_muc(path):
            return
        #[[ May xem truoc dang chay san thi MO NGAM tam nay luon — lan keo dau
        #   tien tren tam nay khoi cho tool mo anh + tim mat. ]]
        if self._may_xem is not None:
            self._xem_xin_mo(path)

    def _tu_xem_neu_co_muc(self, path) -> bool:
        """Ảnh ĐÃ CÓ thông số (mức riêng / mức chung > 0) -> bật xem trước luôn.

        #[[ 5/10 — user: "khi mo 1 folder, neu cac anh da duoc keo thong so thi
        #   phai duoc tai vao preview luon, nhu hien tai phai keo thanh keo moi
        #   thay doi lai". Truoc day xem truoc CHI bat khi nguoi dung keo thanh;
        #   chon mot tam da co muc (nhan "riêng") van hien anh goc tren dia.
        #   Chi tu bat khi dang o mo-dun Retouch va khong co luot Chay dang
        #   chay (xem truoc khi do bi tat de nhuong card). Anh muc 0 het: giu
        #   anh goc nhu cu — khong co gi de tinh. ]]
        """
        if self._xem_bat or not path:
            return False
        if getattr(self.app, "khau_dang", "") != "retouch":
            return False
        if self.worker is not None and self.worker.is_alive():
            return False
        #[[ Tam DA CO KET QUA tren dia ("✓ Đã retouch"): hien chinh file ket qua
        #   (anh that da xuat, khong ton cong tinh) — keo thanh thi van xem truoc. ]]
        if self._duong_kq(path) is not None:
            return False
        try:
            co = any(_so_muc(v, 0) > 0 for v in self._muc_hieu_luc(path).values())
        except Exception:                                    # noqa: BLE001
            co = False
        if not co:
            return False
        self._mo_xem_truoc(path, tu_dong=True)
        if self._xem_bat:
            self._xem_tu_dong = True     # bat vi anh co san thong so, khong phai keo
        return self._xem_bat

    def _hien_anh_dia(self, path: str, giu_khung: bool = False):
        """Ảnh lớn từ đĩa: bản KẾT QUẢ nếu đã làm (giữ chuột = bản gốc), không
        thì chính ảnh vào. Ảnh nhỏ của dải hiện ngay trong lúc chờ nạp."""
        kq = self._duong_kq(path)
        self._anh_kq_duong = kq
        self._xem_dang_hien = False
        self._anh_hien = path
        tam = self.luoi._anh_pil.get(path)
        if kq is not None:
            self.xem.mo(kq, truoc=path, tam=tam, giu_khung=giu_khung)
        else:
            self.xem.mo(path, tam=tam, giu_khung=giu_khung)
        self._chip_dia(kq)
        self._thanh_cu = None
        self._cap_nhat_thanh_xem()

    def _chip_dia(self, kq):
        """Chip của bản trên đĩa: ✓ Đã retouch / Chưa retouch (ghi đè: không)."""
        if kq is not None:
            self._dat_chip("xong", "✓ Đã retouch")
        else:
            self._dat_chip("" if self.v_ghide.get() else "chua",
                           "" if self.v_ghide.get() else "Chưa retouch")

    def _buoc_anh(self, d: int):
        """← → trên ảnh lớn: tấm trước / sau trong dải ảnh."""
        if self.luoi.ds:
            self.luoi._di_phim(d, 0)

    def _xem_mot_anh(self, path: str):
        """Bấm đúp một tấm trong dải ảnh -> bật xem trước ĐÚNG tấm đó."""
        self._mo_xem_truoc(anh=path)

    def _mo_thu_muc(self, var: tk.StringVar):
        d = Path(var.get().strip().strip('"') or ".")
        if var.get().strip() and d.is_dir():
            open_in_explorer(d)
        else:
            messagebox.showinfo("Chưa có thư mục",
                                f"Không có thư mục:\n{var.get() or '(trống)'}",
                                parent=self)

    def nhan_nhom(self, ma: str) -> str:
        return dict(self._ds_the or [("", "Chung")]).get(ma, ma) or "Chung"

    def nhan_the(self, ma: str) -> str:
        """Nhãn đang hiện của thẻ nhóm `ma` (có dấu · khi nhóm có mức riêng)."""
        for pd in getattr(self, "_pd_the", []):
            t = pd.nhan_cua(ma)
            if t:
                return t
        return ""

    # ------------------------------------------------------------ tiện ích
    def _pick(self, var: tk.StringVar):
        d = filedialog.askdirectory(title="Chọn thư mục",
                                    initialdir=var.get() or None, parent=self)
        if d:
            var.set(os.path.normpath(d))

    def _dung_thanh_keo(self, goc) -> int:
        """Dựng lại bảng thanh kéo theo saytool ở thư mục goc. -> số hàng đã dùng.

        Dựng LẠI chứ không chỉ dựng một lần: người dùng đổi thư mục tool sang
        một bản khác thì danh sách thanh kéo cũng khác, mà giao diện vẫn hiện
        bảng cũ thì họ kéo một thứ không còn tồn tại.

        BỐ CỤC MỚI — MỘT HÀNG THẺ NHÓM Ở TRÊN, BẢNG THANH KÉO Ở DƯỚI

        #[[ VI SAO KHONG DUNG 5 NHOM x N THANH KEO CUNG MOT LUC.
        #
        #   saytool chia nam nhom khuon mat (Nu / Nam / Tre con / Nu lon tuoi /
        #   Nam lon tuoi). Sau thanh keo nhan nam nhom la ba muoi thanh keo tren
        #   mot man hinh — khong ai doc noi, va 95% thoi gian moi nhom deu dung
        #   chung mot muc.
        #
        #   Nen: mot hang the o tren, moi luc chi hien MOT bang. The "Chung" la
        #   muc mac dinh cho moi nhom; the mot nhom chi hien nhung thanh keo
        #   nhom do KHAI RIENG. The nao dang co muc rieng thi mang mot dau cham.
        #
        #   Day cung la cach giao dien rieng cua saytool lam (tabs trong
        #   giao_dien.py), nen nguoi dung khong phai hoc lai lan hai.
        #]]
        """
        #[[ Go vet cu TRUOC khi huy hang: v_rieng song qua moi lan dung lai,
        #   trace de lai se ghi vao nhan da huy ("invalid command name"). ]]
        for b, t in getattr(self, "_vet_keo", []):
            try:
                b.trace_remove("write", t)
            except (tk.TclError, ValueError):
                pass
        self._vet_keo = []
        for w in self._o_keo:
            try:
                w.destroy()
            except Exception:                                # noqa: BLE001
                pass
        self._o_keo = []
        self._sc_theo = {}
        self.v_muc = {}
        ds0 = self.rt.thanh_keo(goc)
        #[[ saytool nay tra moi thanh keo dang [ten, nhan, mac_dinh, goi_y,
        #   can_torch?] (5 phan tu — them can_torch 5/10). Cac vong lap ben duoi
        #   unpack 4 phan tu, nen TACH can_torch ra dict _can_torch_keo va giu
        #   _ds_keo dung 4 phan tu (tuong thich saytool cu tra 4 phan tu). ]]
        self._can_torch_keo = {}
        ds = []
        for row in ds0:
            if len(row) >= 5:
                self._can_torch_keo[row[0]] = bool(row[4])
            ds.append(list(row[:4]))
        self._ds_keo = ds
        nhom = self.rt.nhom_mat(goc)
        self._nhom_ds = [tuple(x) for x in nhom]
        sb = self.o_hang_keo
        #[[ Gia tri ban dau = MUC CUA ANH DANG XEM (rieng neu co, khong thi muc
        #   chung) — khong phai gia tri cua bien cu: moi lan keo da ghi ngay vao
        #   _muc_anh / muc chung, nen doc lai tu do la dung ca khi tool vua tra
        #   loi bang thanh keo that (thanh moi lay muc chung / mac dinh). ]]
        muc_ht = self._muc_hien_tai()

        #[[ Biến của MỌI nhóm phải tồn tại kể cả khi thẻ đó không đang hiện —
        #   nếu chỉ tạo cho thẻ đang xem thì chuyển thẻ là mất mức vừa đặt. ]]
        if not hasattr(self, "v_rieng"):
            self.v_rieng, self.v_bat_rieng = {}, {}
        for ten, _nhan, md, _goi in ds:
            for nh, _l in nhom:
                k = (nh, ten)
                if k in self.v_rieng:
                    continue
                gt = muc_ht.get(f"{nh}:{ten}")
                #[[ Mac dinh 0 (khong lay md cua buoc): moi project = 0 het. ]]
                self.v_rieng[k] = tk.DoubleVar(
                    value=_so_muc(gt, _so_muc(muc_ht.get(ten), 0)))
                self.v_bat_rieng[k] = tk.BooleanVar(value=gt not in (None, ""))

        self._dung_the_nhom(goc)
        hang = 1
        for ten, nhan, md, goi in ds:
            v = tk.DoubleVar(value=_so_muc(muc_ht.get(ten), 0))  # mac dinh 0
            self.v_muc[ten] = v
            if self.nhom_dang and not self.rt.theo_nhom(ten, goc):
                #[[ Buoc tu khai theo_nhom = False thi khong chia duoc — khong
                #   hien o the nhom, thay vi hien mot thanh keo khong co tac
                #   dung gi. ]]
                continue
            hang = self._mot_hang_keo(sb, hang, goc, ten, nhan, md, goi, v)
        return hang

    def _mot_hang_keo(self, sb, i, goc, ten, nhan, md, goi, v) -> int:
        """Một tính năng = nhãn · dấu ? · số ở trên, thanh trượt ở dưới (dáng
        Evoto). Ở thẻ một nhóm thì công tắc “riêng” đứng đầu hàng.

        #[[ KHONG dat width= o nhan. ttk.Label(width=N) CAT chu dai hon N, va
        #   ten cua 0.9.5 dai hon han ba ten cu: "Xoá khuyết điểm cơ thể" la 22
        #   ky tu, "Làm mờ nếp nhăn trán" 20. kiem_retouch_gui.py do bang Tk
        #   that, voi ca nhan dai. ]]
        """
        nh = self.nhom_dang
        o = ttk.Frame(sb)
        o.pack(fill="x", pady=(6, 1))
        dong = ttk.Frame(o)
        dong.pack(fill="x")
        self._o_keo += [o, dong]
        if not nh:
            bien = v
        else:
            k = (nh, ten)
            bien = self.v_rieng[k]
            bat = self.v_bat_rieng[k]
            ct = gd.CongTac(dong, bat, command=lambda _k=k: self._doi_bat_rieng(_k))
            ct.pack(side="left", padx=(0, 8))
            ct.goi_y = gd.GoiY(ct, "Riêng cho nhóm này — tắt thì nhóm này theo "
                                   "mức chung.")
            self._o_keo.append(ct)
        l1 = ttk.Label(dong, text=nhan)
        l1.pack(side="left")
        self._o_keo.append(l1)
        #[[ CAN TAI TORCH: tinh nang nay can torch ma ban --nhe chua tai. Van
        #   hien thanh keo (de nguoi dung biet co + dat muc truoc), nhung ghi chu
        #   "cần tải torch" cho ro — khong phai thieu tinh nang. Tai torch (lan
        #   dau bam Chay retouch) xong, doc lai la het dau nay. ]]
        if getattr(self, "_can_torch_keo", {}).get(ten):
            lct = ttk.Label(dong, text="· cần tải torch", style="Mo2.TLabel")
            lct.pack(side="left", padx=(6, 0))
            self._o_keo.append(lct)
            lct.goi_y = gd.GoiY(lct, "Tính năng này cần thư viện AI (torch) — "
                                     "bản cài tải về lần đầu bấm “Chạy retouch”. "
                                     "Đặt mức trước cũng được; tải xong là chạy.")
        chu = goi
        if nh:
            t = self.rt.tin_keo(goc).get(ten) or {}
            if nh in (t.get("bo_qua") or ()):
                chu = ("Bước này mặc định KHÔNG chạy cho nhóm này — bật “riêng” "
                       "là ép nó chạy. " + goi)
            elif t.get("ghi_chu"):
                chu = t["ghi_chu"]
        if chu:
            h = gd.NutHoi(dong, chu)
            h.pack(side="left", padx=(6, 0))
            self._o_keo.append(h)
        lb = ttk.Label(dong, width=4, anchor="e")
        lb.pack(side="right")
        sc = gd.Truot(o, from_=0, to=100, variable=bien,
                      command=lambda gt, _b=bien: self._lam_tron(_b, gt))
        sc.pack(fill="x", pady=(3, 0))
        #[[ Ban phim: mui ten +-1, Shift +-10. Bam dup thanh = ve muc mac dinh
        #   cua tool (nhu Lightroom / Evoto). ]]
        for phim, buoc in (("<Left>", -1), ("<Down>", -1), ("<Right>", 1),
                           ("<Up>", 1), ("<Shift-Left>", -10), ("<Shift-Right>", 10)):
            sc.bind(phim, lambda _e, _s=sc, _b=buoc: (_s.set(_s.get() + _b), "break")[1])
        sc.bind("<Double-Button-1>", lambda _e, _s=sc, _m=md: _s.set(float(_m)))
        self._o_keo += [sc, lb]

        # đọc lại chính biến đó, không giữ giá trị chụp lúc dựng
        tid = bien.trace_add("write", lambda *_a, _v=bien, _l=lb: self._muc_doi(_l, _v))
        self._vet_keo.append((bien, tid))
        self._ghi_so(lb, bien)
        if nh:
            self._mo_hang(sc, lb, self.v_bat_rieng[(nh, ten)].get())
            self._sc_theo[(nh, ten)] = (sc, lb)
        return i + 1

    def _lam_tron(self, bien, gt):
        """Mức là số nguyên 0–100 — kéo chuột không đẻ ra 63,2847."""
        try:
            v = round(float(gt))
            if float(bien.get()) != v:
                bien.set(v)
        except (tk.TclError, ValueError):
            pass

    def _ghi_so(self, lb, bien):
        try:
            lb.configure(text=f"{float(bien.get()):.0f}")
        except (tk.TclError, ValueError):
            pass
        self._hen_tom_tat()

    def _muc_doi(self, lb, bien):
        """Một thanh vừa đổi số. NGƯỜI kéo (không phải lúc nạp mức của tấm vừa
        chọn) -> thành mức của ảnh đang xem, và ảnh lớn tính lại."""
        self._ghi_so(lb, bien)
        if not self._dang_nap_muc:
            self._nguoi_doi_muc()

    def _nguoi_doi_muc(self):
        """Người dùng vừa đổi mức trên bảng: (1) ghi thành mức của ẢNH ĐANG
        XEM — chưa có ảnh nào thì là mức chung; (2) ảnh lớn tính lại theo mức
        đó, chưa bật xem trước thì TỰ BẬT (không còn nút "Xem trước")."""
        self._ghi_muc_dang()
        #[[ Nguoi dung da KEO: xem truoc tu day la cua nguoi dung (giu bat khi
        #   sang tam khac), khong con la "tu bat theo tam" nua. ]]
        self._xem_tu_dong = False
        if self._xem_bat:
            self._hen_tinh_xem()
        elif self._anh_dang:
            self._mo_xem_truoc(tu_dong=True)

    def _mo_hang(self, sc, lb, bat: bool):
        """Chưa tick “riêng” thì thanh kéo mờ đi và không kéo được.

        #[[ De keo duoc ma khong co tac dung la kieu giao dien noi doi: nguoi
        #   dung keo, thay so doi, tuong da dat xong — roi chay ra ket qua y
        #   nhu cu. ]]
        """
        st = "normal" if bat else "disabled"
        try:
            sc.configure(state=st)
            lb.configure(foreground=gd.MAU["chu"] if bat else gd.MAU["mo2"])
        except tk.TclError:
            pass

    def _doi_bat_rieng(self, k):
        o = self._sc_theo.get(k)
        if o:
            self._mo_hang(o[0], o[1], self.v_bat_rieng[k].get())
        if not self._dang_nap_muc and self.v_bat_rieng[k].get():
            self._chung_ve_0_khi_rieng(k)
        self._danh_dau_the()
        if not self._dang_nap_muc:
            self._nguoi_doi_muc()

    def _ten_theo_nhom(self) -> set:
        """Tính năng chia được theo nhóm mặt (có thanh ở thẻ giới tính)."""
        goc = self._goc_hien()
        return {t for t, *_x in self._ds_keo if self.rt.theo_nhom(t, goc)}

    def _chung_ve_0_khi_rieng(self, k):
        """Bật “riêng” ĐẦU TIÊN cho một nhóm mặt -> mức CHUNG của ảnh về 0.

        #[[ 6/10 — user: "Buc nao chon gioi tinh rieng de chinh sua rieng thi
        #   mac dinh su dung thong so cua cac gioi tinh. Muc Chung se dua thong
        #   so ve 0." Truoc day muc chung VAN AP cho moi khuon mat khong dat
        #   rieng (ca tinh nang nhom do chua bat rieng) — dat rieng cho Nu ma Nam
        #   van bi lam min theo muc chung. Chi lam O LAN BAT DAU (chua nhom nao
        #   bat rieng): sau do nguoi dung tu keo lai muc chung thi la y ho — luc
        #   Chay retouch se hoi dung Chung hay Rieng (xem start). Tinh nang
        #   khong chia nhom (keo dai chan...) khong co the gioi tinh nen GIU muc
        #   chung. Thanh rieng vua bat lay so cua muc chung truoc khi ve 0. ]]
        """
        if any(v.get() for kk, v in self.v_bat_rieng.items() if kk != k):
            return
        nhom_duoc = self._ten_theo_nhom()
        doi = []
        self._dang_nap_muc = True
        try:
            rv = self.v_rieng.get(k)
            cv = self.v_muc.get(k[1])
            if rv is not None and cv is not None and float(rv.get()) == 0.0:
                rv.set(float(cv.get()))
            for ten, v in self.v_muc.items():
                if ten in nhom_duoc and float(v.get()) != 0.0:
                    v.set(0.0)
                    doi.append(ten)
        except (tk.TclError, ValueError):
            pass
        finally:
            self._dang_nap_muc = False
        if doi:
            p = self._anh_dang
            self._append(f"… {Path(p).name if p else 'Cả thư mục'}: đặt riêng theo "
                         "nhóm mặt — các thanh ở thẻ Chung về 0 (chỉ nhóm đặt "
                         "riêng được retouch)")
            self.app.status("Đã đưa mức Chung về 0 — ảnh này dùng mức riêng theo "
                            "giới tính", gd.MAU["xong"])

    def _dung_the_nhom(self, goc):
        """Thẻ nhóm: Chung + từng nhóm khuôn mặt, thành hàng viên chọn — ba
        viên một hàng (bảng điều khiển hẹp, sáu viên một hàng là cắt chữ).

        #[[ Chi dung lai khi DANH SACH NHOM doi. Doi the ma huy luon hang vien
        #   chon la huy chinh widget dang chay do su kien bam cua no. ]]
        """
        ds = [("", "Chung")] + [tuple(x) for x in self.rt.nhom_mat(goc)]
        if ds != self._ds_the or not getattr(self, "_pd_the", None):
            for w in self._o_the_nhom:
                try:
                    w.destroy()
                except Exception:                            # noqa: BLE001
                    pass
            self._o_the_nhom = []
            self._ds_the = ds
            self._pd_the = []
            n = self.MOI_HANG_THE
            for i in range(0, len(ds), n):
                pd = gd.PhanDoan(self.o_the, self.v_nhom, ds[i:i + n],
                                 command=lambda: self.doi_nhom(self.v_nhom.get()))
                pd.pack(fill="x", pady=(0, 4))
                self._pd_the.append(pd)
                self._o_the_nhom.append(pd)
            self.lbl_the = ttk.Label(self.o_the, style="Mo2.TLabel", text="",
                                     wraplength=300, justify="left")
            self.lbl_the.pack(anchor="w", fill="x", pady=(0, 2))
            self._o_the_nhom.append(self.lbl_the)
        if self.v_nhom.get() != self.nhom_dang:
            self.v_nhom.set(self.nhom_dang)
        self._danh_dau_the()

    def _danh_dau_the(self):
        """Thẻ đang chọn nổi lên (viên chọn tự lo); thẻ có mức riêng mang dấu ·."""
        if not getattr(self, "_pd_the", None):
            return
        co = {nh for (nh, _t), v in self.v_bat_rieng.items() if v.get()}
        n = self.MOI_HANG_THE
        for j, pd in enumerate(self._pd_the):
            phan = self._ds_the[n * j:n * j + n]
            pd.dat_lua_chon([(ma, (nhan + " ·") if ma and ma in co else nhan)
                             for ma, nhan in phan])
        if hasattr(self, "lbl_the"):
            self.lbl_the.configure(
                text="Mức dùng cho mọi nhóm không đặt riêng · 0 = tắt hẳn tính năng"
                     if not self.nhom_dang
                else "Chỉ áp cho nhóm này; tính năng chưa bật “riêng” thì theo "
                     "mức chung")
        self._hen_tom_tat()

    def doi_nhom(self, ma: str):
        self.nhom_dang = ma
        if self.v_nhom.get() != ma:
            self.v_nhom.set(ma)
        self._dung_lai_thanh_keo(self.v_goc.get().strip().strip('"'))

    def muc_day_du(self) -> dict:
        """Bảng mức phẳng: mức chung + mọi mức riêng theo nhóm.

        Đúng định dạng saytool dùng ({"vet": 100, "nam:vet": 40}), nên retouch.json
        cũ vẫn đọc được và chỗ nào không quan tâm đến nhóm cứ đọc khoá chung.
        """
        d = {k: v.get() for k, v in self.v_muc.items()}
        for (nh, ten), bat in self.v_bat_rieng.items():
            if bat.get() and ten in self.v_muc:
                d[f"{nh}:{ten}"] = self.v_rieng[(nh, ten)].get()
        return d

    # ------------------------------------------------------------ mức riêng từng ảnh
    #[[ MUC RIENG TUNG ANH + SYNC (sang 4/10 — user: "can them nut Sync All cac
    #   hieu ung da keo cho cac anh duoc chon hoac tat ca").
    #
    #   Bang thanh keo hien MUC CUA ANH DANG XEM. Keo = chinh anh do (luu vao
    #   _muc_anh, theo khoa rt.khoa_anh, ghi ra file rieng cua thu muc vao —
    #   rt.ghi_muc_anh). Anh khong co muc rieng thi theo MUC CHUNG (cf "muc").
    #   Muc rieng ma trung muc chung thi KHONG giu (bo khoi _muc_anh) — dau
    #   "riêng" tren dai anh chi hien khi that su khac. ]]
    def _goc_hien(self) -> str:
        return self.v_goc.get().strip().strip('"')

    def _vao_hien(self) -> str:
        return self.v_vao.get().strip().strip('"')

    def _khoa(self, p) -> str:
        return self.rt.khoa_anh(p, self._vao_hien(), bool(self.v_dequy.get()))

    def _muc_chung_day_du(self) -> dict:
        """Mức CHUNG (retouch.json "muc") đủ mọi tính năng tool đang có, dạng
        muc_day_du(): tính năng chưa có mức thì lấy mặc định của tool; mức
        riêng theo nhóm chỉ giữ cái tool còn có."""
        cf = self._muc_chung_tm or {}          # muc chung CUA THU MUC VAO dang mo
        ten_co = {t for t, *_x in self._ds_keo}
        #[[ MOI PROJECT = 0 HET (user 5/10, nhu Evoto): thu muc chua luu muc
        #   bao gio thi MOI thanh = 0, nguoi dung tu keo tinh nang muon dung.
        #   KHONG lay mac_dinh cua buoc (vet/min_da... mac_dinh 100) lam gia tri
        #   ban dau nua — gio 0 = tat, nguoi dung chu dong bat. Anh / thu muc DA
        #   luu muc cu van giu nguyen (cf.get(ten) co gia tri thi dung gia tri do). ]]
        d = {ten: _so_muc(cf.get(ten), 0) for ten, _n, _md, _g in self._ds_keo}
        #[[ Nhom mat lay tu ban da hoi luc dung bang (_nhom_ds), KHONG goi
        #   rt.nhom_mat(None) o day: ham nay chay moi nhip keo, ma nhom_mat(None)
        #   di do tim tool tren dia. ]]
        ma_nhom = {n for n, _l in self._nhom_ds}
        for k, v in cf.items():
            nh, co, ten = str(k).partition(":")
            if co and ten in ten_co and nh in ma_nhom and v not in (None, ""):
                d[str(k)] = _so_muc(v, 0)
        return d

    def _muc_hieu_luc(self, p) -> dict:
        """Bộ mức THẬT SỰ áp cho một ảnh: mức riêng của nó, không thì mức chung.
        Tính năng mức riêng chưa có (tool vừa thêm) thì theo mức chung — nhưng
        mức riêng theo NHÓM MẶT thì không: bộ riêng đã nói đủ nhóm nào riêng."""
        chung = self._muc_chung_day_du()
        rieng = self._muc_anh.get(self._khoa(p)) if p else None
        if rieng is None:
            return chung
        d = {k: v for k, v in chung.items() if ":" not in str(k)}
        d.update(rieng)
        return d

    def _muc_hien_tai(self) -> dict:
        return self._muc_hieu_luc(self._anh_dang) if self._anh_dang \
            else self._muc_chung_day_du()

    def _loc_muc(self, d: dict) -> dict:
        """Bỏ khoá của tính năng tool KHÔNG còn có (để gom nhóm lúc chạy không
        tách hai nhóm chỉ vì một khoá cũ). Bảng thanh kéo chưa phải của tool
        thật (bản dự phòng) thì không lọc — không đoán."""
        if not self._goc_hien() or not self.rt.da_hoi_that(self._goc_hien()):
            return dict(d)
        ten_co = {t for t, *_x in self._ds_keo}
        ma_nhom = {n for n, _l in self._nhom_ds}
        ra = {}
        for k, v in d.items():
            nh, co, ten = str(k).partition(":")
            if (not co and k in ten_co) or (co and ten in ten_co and nh in ma_nhom):
                ra[k] = v
        return ra

    def _nap_muc_vao_bang(self, muc: dict):
        """Đặt bảng thanh kéo theo một bộ mức (mức của tấm vừa chọn) — KHÔNG
        tính là người kéo: không ghi đè mức của ai, không tính lại ảnh lớn."""
        md_cua = {t: md for t, _n, md, _g in self._ds_keo}
        self._dang_nap_muc = True
        try:
            for ten, v in self.v_muc.items():
                gt = _so_muc(muc.get(ten), md_cua.get(ten, 0))
                try:
                    if float(v.get()) != gt:
                        v.set(gt)
                except (tk.TclError, ValueError):
                    v.set(gt)
            for (nh, ten), bat in self.v_bat_rieng.items():
                k = f"{nh}:{ten}"
                co = ten in md_cua and muc.get(k) not in (None, "")
                gt = _so_muc(muc.get(k), _so_muc(muc.get(ten), md_cua.get(ten, 0)))
                if bool(bat.get()) != co:
                    bat.set(co)
                rv = self.v_rieng.get((nh, ten))
                if rv is not None and float(rv.get()) != gt:
                    rv.set(gt)
                o = self._sc_theo.get((nh, ten))
                if o:
                    self._mo_hang(o[0], o[1], co)
        finally:
            self._dang_nap_muc = False
        self._danh_dau_the()
        self._hen_tom_tat()

    def _ghi_muc_dang(self):
        """Mức trên bảng -> mức của ảnh đang xem (hoặc mức chung khi chưa có
        ảnh). Trùng mức chung thì ảnh đó KHÔNG giữ mức riêng."""
        d = self.muc_day_du()
        p = self._anh_dang
        if not p:
            self._muc_chung_tm = dict(d)
            self._muc_chung_ban = True
        else:
            k = self._khoa(p)
            if self.rt.giong_muc(d, self._muc_chung_day_du()):
                self._muc_anh.pop(k, None)
            else:
                self._muc_anh[k] = dict(d)
            self._cap_nhat_dau_rieng(p)
        self._hen_luu_muc()
        self._cap_nhat_pham_vi()

    def _hen_luu_muc(self):
        """Ghi xuống đĩa SAU khi ngừng tay 0,6 s (kéo thanh là hàng chục lần
        đổi số một giây)."""
        if self._hen_luu_ma is not None:
            try:
                self.after_cancel(self._hen_luu_ma)
            except tk.TclError:
                pass
        try:
            self._hen_luu_ma = self.after(600, self._luu_muc)
        except tk.TclError:
            self._hen_luu_ma = None

    def _luu_muc(self):
        if self._hen_luu_ma is not None:
            try:
                self.after_cancel(self._hen_luu_ma)
            except tk.TclError:
                pass
        self._hen_luu_ma = None
        #[[ Muc rieng tung anh + MUC CHUNG cung nam o file cua thu muc vao
        #   (khong ghi muc chung vao retouch.json nua — xem _muc_chung_tm). ]]
        self._muc_chung_ban = False
        if self._muc_anh_vao:
            try:
                self.rt.ghi_muc_anh(self._muc_anh_vao, self._muc_anh,
                                    dict(self._muc_chung_tm))
            except OSError as ex:
                self._append(f"! không ghi được mức của thư mục này: {ex}")

    def _doi_bang_muc_anh(self, vao: str):
        """Đổi thư mục vào: ghi nốt mức riêng của thư mục cũ, đọc của thư mục
        mới (mỗi thư mục vào một bảng — tên ảnh hai buổi có thể trùng nhau)."""
        k = os.path.normcase(os.path.abspath(vao)) if vao else None
        if k == self._muc_anh_khoa:
            return
        if self._hen_luu_ma is not None:
            self._luu_muc()
        self._muc_anh_khoa = k
        self._muc_anh_vao = vao or None
        try:
            self._muc_anh = self.rt.doc_muc_anh(vao) if vao else {}
        except Exception:                                    # noqa: BLE001
            self._muc_anh = {}
        #[[ Muc chung CUA THU MUC NAY — thu muc moi chua co -> {} -> moi thanh 0. ]]
        try:
            self._muc_chung_tm = self.rt.doc_muc_chung(vao) if vao else {}
        except Exception:                                    # noqa: BLE001
            self._muc_chung_tm = {}

    def _cap_nhat_dau_rieng(self, p=None):
        """Nhãn "riêng" trên dải ảnh theo _muc_anh (p: chỉ một tấm)."""
        luoi = getattr(self, "luoi", None)
        if luoi is None:
            return
        doi = False
        for o in luoi.ds:
            if p is not None and o["path"] != p:
                continue
            r = self._khoa(o["path"]) in self._muc_anh
            if bool(o.get("rieng")) != r:
                o["rieng"] = r
                doi = True
        if doi:
            luoi._ve()
        self._hen_tom_tat()

    def _cap_nhat_pham_vi(self):
        """Dòng “đang chỉnh ảnh nào” + hai nút Sync, theo tấm đang xem và số
        tấm đang chọn ở dải ảnh."""
        if not hasattr(self, "lbl_pham_vi"):
            return
        p = self._anh_dang
        rieng = bool(p) and self._khoa(p) in self._muc_anh
        if not p:
            chu = "Chưa có ảnh — đang đặt MỨC CHUNG cho mọi ảnh."
        else:
            chu = f"{Path(p).name} · " + ("mức riêng của ảnh này" if rieng
                                          else "theo mức chung")
        n = len(self.luoi.ds_chon()) if p else 0
        #[[ Ham nay chay MOI nhip keo thanh — chi ve lai khi co gi doi (nut bo
        #   tron ve lai la dung lai anh nen). ]]
        moi = (chu, rieng, n, bool(p and self._muc_anh))
        if moi == getattr(self, "_pham_vi_cu", None):
            return
        self._pham_vi_cu = moi
        try:
            self.lbl_pham_vi.configure(text=chu, foreground=gd.MAU["nhan"] if rieng
                                       else gd.MAU["mo"])
        except tk.TclError:
            return
        self.btn_sync_chon.configure(
            text=f"Sync ảnh đã chọn ({n})" if n > 1 else "Sync ảnh đã chọn",
            state="normal" if n > 1 else "disabled")
        #[[ Reset ve 0: bat khi co anh dang xem (reset chinh anh do). ]]
        if hasattr(self, "btn_reset"):
            self.btn_reset.configure(state="normal" if p else "disabled")

    def _mo_ta_muc(self, muc: dict, toi_da: int = 4) -> str:
        """“Xoá khuyết điểm 60 · Làm mịn da 40 · riêng Nam: Làm thon mặt 30”."""
        nhan = {t: n for t, n, *_x in self._ds_keo}
        ten_nhom = dict(self._nhom_ds)
        chung, rieng = [], []
        for k, v in muc.items():
            gt = _so_muc(v, 0)
            nh, co, ten = str(k).partition(":")
            if not co and gt > 0:
                chung.append(f"{nhan.get(k, k)} {gt:.0f}")
            elif co:
                rieng.append(f"{ten_nhom.get(nh, nh)}: {nhan.get(ten, ten)} {gt:.0f}")
        ra = " · ".join(chung[:toi_da]) + (" …" if len(chung) > toi_da else "")
        if not chung:
            ra = "mọi tính năng ở 0"
        if rieng:
            ra += " · riêng " + ", ".join(rieng[:2]) + (" …" if len(rieng) > 2 else "")
        return ra

    def _reset_anh_0(self):
        """Đưa MỌI thanh của ảnh đang xem về 0 (tắt hết tính năng), rồi tính
        lại ảnh lớn — như kéo tay nhưng một phát về 0. Muốn reset nhiều ảnh:
        Reset tấm này rồi bấm Sync ảnh đã chọn.

        #[[ Dat var duoi co _dang_nap_muc = True de moi var ve 0 KHONG tung lan
        #   goi _nguoi_doi_muc (hang chuc lan ghi + tinh lai). Xong het thi goi
        #   MOT lan _nguoi_doi_muc -> ghi muc + tinh lai preview mot luot. ]]
        """
        self._dang_nap_muc = True
        try:
            for v in self.v_muc.values():
                try:
                    if float(v.get()) != 0.0:
                        v.set(0.0)
                except (tk.TclError, ValueError):
                    v.set(0.0)
            #[[ Tat luon moi muc RIENG theo nhom (bo tick "rieng") — reset la
            #   sach, khong de sot mot nhom nao con muc. ]]
            for (nh, ten), bat in self.v_bat_rieng.items():
                if bool(bat.get()):
                    bat.set(False)
                rv = self.v_rieng.get((nh, ten))
                if rv is not None and float(rv.get()) != 0.0:
                    rv.set(0.0)
                o = self._sc_theo.get((nh, ten))
                if o:
                    self._mo_hang(o[0], o[1], False)
        finally:
            self._dang_nap_muc = False
        self._danh_dau_the()
        self._nguoi_doi_muc()
        p = self._anh_dang
        if p:
            self._append(f"… Reset {Path(p).name} về 0 (tắt hết tính năng)")

    def _sync_chon(self):
        """Chép mức của ảnh đang xem sang mọi tấm đang chọn ở dải ảnh."""
        p = self._anh_dang
        ds = [q for q in self.luoi.ds_chon() if q != p]
        if not p or not ds:
            return
        muc = self.muc_day_du()
        giong = self.rt.giong_muc(muc, self._muc_chung_day_du())
        for q in ds:
            k = self._khoa(q)
            if giong:
                self._muc_anh.pop(k, None)
            else:
                self._muc_anh[k] = dict(muc)
        self._luu_muc()
        self._cap_nhat_dau_rieng()
        self._cap_nhat_pham_vi()
        self._append(f"… Sync mức của {Path(p).name} sang {len(ds)} ảnh đã chọn: "
                     + self._mo_ta_muc(muc))
        self.app.status(f"Đã Sync mức của {Path(p).name} sang {len(ds)} ảnh đã chọn",
                        gd.MAU["xong"])

    def _sync_het(self):
        """Chép mức của ảnh đang xem cho MỌI ảnh và lấy làm mức chung."""
        p = self._anh_dang
        if not p:
            return
        muc = self.muc_day_du()
        k_dang = self._khoa(p)
        khac = [k for k, m in self._muc_anh.items()
                if k != k_dang and not self.rt.giong_muc(m, muc)]
        if khac and not messagebox.askokcancel(
                "Sync tất cả?",
                f"{len(khac)} ảnh khác đang có mức riêng của nó. “Sync tất cả” sẽ "
                f"đưa MỌI ảnh về đúng mức của {Path(p).name}:\n\n"
                f"   {self._mo_ta_muc(muc, 8)}\n\n"
                "Mức riêng của những ảnh đó mất đi. Tiếp tục?", parent=self):
            return
        self._muc_chung_tm = dict(muc)
        self._muc_chung_ban = True
        self._muc_anh.clear()
        self._luu_muc()
        self._cap_nhat_dau_rieng()
        self._cap_nhat_pham_vi()
        n = len(self.luoi.ds)
        self._append(f"… Sync tất cả ({n} ảnh) theo mức của {Path(p).name}: "
                     + self._mo_ta_muc(muc))
        self.app.status(f"Đã Sync mức của {Path(p).name} cho cả {n} ảnh",
                        gd.MAU["xong"])

    def _ve_muc_chung(self):
        """Ảnh đang xem bỏ mức riêng, theo lại mức chung."""
        p = self._anh_dang
        if not p:
            return
        self._muc_anh.pop(self._khoa(p), None)
        self._luu_muc()
        self._nap_muc_vao_bang(self._muc_hieu_luc(p))
        self._cap_nhat_dau_rieng(p)
        self._cap_nhat_pham_vi()
        if self._xem_bat:
            self._hen_tinh_xem()

    def _dung_lai_thanh_keo(self, goc):
        """Dựng lại bảng thanh kéo (đổi thẻ nhóm, đổi tool, tool vừa trả lời)."""
        self._hang_keo = self._dung_thanh_keo(goc)
        self._canh_bao_keo(goc)

    def _canh_bao_keo(self, goc):
        """Nói ra khi bảng thanh kéo chỉ là bản dự phòng, và nói rõ vì sao."""
        if not hasattr(self, "lbl_keo"):
            return
        if not self._keo_dang_hoi and not self.rt.hop_le(goc):
            #[[ Chua co tool dung duoc thi dai bao tren luoi ("Chua dung duoc
            #   tool retouch — …") da noi NGUYEN NHAN; bang du phong chi la he
            #   qua. Noi them o day la hai canh bao cho mot chuyen. Canh bao
            #   nay danh cho truong hop co tool ma HOI KHONG DUOC (9/9). ]]
            self._hien_an(self.o_canh_keo, False)
            return
        if self._keo_dang_hoi:
            self.lbl_keo.configure(
                text="Đang hỏi tool xem nó có những tính năng nào… "
                     "(lần đầu phải nạp torch nên có thể mất một phút)")
            self._hien_an(self.btn_keo_lai, False)
            self._hien_an(self.o_canh_keo, True)
            return
        if self.rt.da_hoi_that(goc):
            self._hien_an(self.o_canh_keo, False)
            return
        vi_sao = self.rt.loi_hoi_keo(goc)
        self.lbl_keo.configure(
            text="Đang hiện bảng DỰ PHÒNG, không phải tính năng thật của tool. "
                 + (f"Vì: {vi_sao.splitlines()[0]}" if vi_sao
                    else "Chưa hỏi được tool.")
                 + "  Bấm “Đọc lại tính năng” để thử lại; chi tiết in ở Nhật ký.")
        self._hien_an(self.btn_keo_lai, True)
        self._hien_an(self.o_canh_keo, True)
        if vi_sao:
            for d in vi_sao.splitlines():
                self._append("   " + d)

    def do_doc_lai_keo(self):
        """Hỏi lại tool — chạy ở luồng nền, vì lần hỏi có thể tới 180 giây."""
        goc = self.v_goc.get().strip().strip('"')
        if not self.rt.hop_le(goc):
            self._append("! chưa chọn đúng thư mục tool, không hỏi được")
            return
        self._hoi_keo_nen(goc, ep=True)

    def _hoi_keo_nen(self, goc, ep: bool = False):
        #[[ PHAI CHAY O LUONG NEN.
        #
        #   rt.thanh_keo() mo mot tien trinh con nap torch — do duoc la hang
        #   chuc giay, toi da 180. Goi thang tren luong giao dien la Tk dung
        #   hinh dung nhu treo, va nguoi dung se tat app giua chung.
        #]]
        if self._keo_dang_hoi:
            return
        if not ep and self.rt.da_hoi_that(goc):
            return
        self._keo_dang_hoi = True
        self._canh_bao_keo(goc)
        if ep:
            self.rt.quen_thanh_keo(goc)
            self._append("… đang hỏi lại tool xem có những tính năng nào")

        def work():
            try:
                self.rt.thanh_keo(goc, lam_lai=True)
            except Exception:                                # noqa: BLE001
                pass
            self.log_q.put(("keo", goc))

        threading.Thread(target=work, daemon=True).start()

    def _pick_goc(self):
        d = filedialog.askdirectory(title="Thư mục ToolCloneEvoto",
                                    initialdir=self.v_goc.get() or None, parent=self)
        if d:
            self.v_goc.set(os.path.normpath(d))
            self._xem_hong = ""                 # tool mới: xem trước được thử lại
            if self._kiem():
                self._dung_lai_thanh_keo(self.v_goc.get().strip())

    def _nho_thu_muc(self):
        #[[ Ghi vao TRANG THAI ngay khi nguoi dung go duong dan, khong doi toi
        #   luc bam Chay.
        #
        #   Ban truoc chi ghi trong start(). Ket qua la mot vong luan quan: cua
        #   so "Buoi chup" khong biet thu muc Export nen khong the hoi "Export
        #   xong roi, chay retouch chua?"; con muon no biet thi phai chay
        #   retouch thanh cong truoc. Chay that bai (nhu lan 3/9) thi khong bao
        #   gio thoat ra duoc.
        #]]
        try:
            import trang_thai as tt
            goc = self.app.folder()
            if not goc:
                return
            vao = self.v_vao.get().strip().strip('"')
            ra = self.v_ra.get().strip().strip('"')
            d = {}
            if vao and Path(vao).is_dir():
                d["thu_muc_export"] = os.path.normpath(vao)
            if ra:
                d["thu_muc_retouch"] = os.path.normpath(ra)
            if d:
                tt.ghi(tt.ten_buoi(goc), **d)
        except Exception:                                    # noqa: BLE001
            pass

    def theo_thu_muc_export(self, d: str, tu_dong: bool = True):
        """Khâu Export vừa biết thư mục — kéo nó sang ô “Vào” của Retouch.

        tu_dong=False là người dùng tự bấm nút, lúc đó ghi đè không cần hỏi.
        """
        d = os.path.normpath(str(d or "").strip().strip('"'))
        if not d or d == ".":
            return
        self._export_moi = d
        vao = self.v_vao.get().strip().strip('"')
        if not tu_dong or not vao or _cung_thu_muc(vao, self._export_cu) \
                or _cung_thu_muc(vao, d):
            #[[ O dang trong, hoac dang bam theo thu muc Export cu -> cu di
            #   theo, khong hoi. Nguoi dung chua he go gi rieng o day. ]]
            if not _cung_thu_muc(vao, d):
                self.v_vao.set(d)
                self.app.status(f"Khâu Retouch đã theo thư mục Export: {d}",
                                gd.MAU["nhan"])
            self._export_cu = d
            self.rt.ghi_cau_hinh({"theo_export": d})
            self._hien_an(self.o_theo_export, False)
        else:
            #[[ Ho da go mot duong dan KHAC. Noi ra, dung tu doi. ]]
            self.lbl_theo_export.configure(
                text=f"Khâu Export đang trỏ {d} — khác ô “Vào” ở trên.")
            self._hien_an(self.o_theo_export, True)
        self._dem()

    def _nhan_theo_export(self):
        d = getattr(self, "_export_moi", "")
        if d:
            self.theo_thu_muc_export(d, tu_dong=False)

    def _doi_vao(self):
        #[[ Goi y thu muc RA chi khi nguoi dung CHUA tu dat.
        #   Ghi de len duong dan ho vua go la kieu "tu dong" gay uc che nhat.
        #]]
        vao = self.v_vao.get().strip().strip('"')
        if vao and not self.v_ra.get().strip():
            self.v_ra.set(os.path.normpath(vao.rstrip("\\/") + "_retouch"))
        #[[ Moi thu muc vao mot bang muc rieng tung anh (rt.doc_muc_anh). ]]
        self._doi_bang_muc_anh(vao)
        self._nho_thu_muc()
        self._hen_dem()

    def _append(self, msg: str):
        self.txt.configure(state="normal")
        self.txt.insert("end", msg + "\n")
        self.txt.see("end")
        self.txt.configure(state="disabled")
        self._ghi_log_tep(msg)

    def _ghi_log_tep(self, msg: str):
        """Nhật ký Retouch ra file <dữ liệu>/retouch.log (xoay ở 2 MB).

        #[[ 7/10: Nhat ky tren giao dien mat khi dong app; loi bao SAU (anh
        #   thieu buoc, me dung giua chung, engine sap) can dong that cua lan
        #   chay do. Mot file cho ca xem truoc + me; xem_truoc.log / _loi.log
        #   la cua tien trinh con. ]]
        """
        try:
            import duong_dan as _dd
            p = _dd.du_lieu("retouch.log")
            if p.is_file() and p.stat().st_size > 2 * 1024 * 1024:
                os.replace(p, p.with_name("retouch.log.cu"))
            with open(p, "a", encoding="utf-8") as fh:
                fh.write(f"{datetime.now():%m-%d %H:%M:%S} {msg}\n")
        except Exception:                                    # noqa: BLE001
            pass

    def _kiem(self, chay_thu: bool = False):
        """chay_thu=True: chạy hẳn một tiến trình con để BIẾT thiếu gói nào.

        Kiểm nhanh (chỉ nhìn file) chạy mỗi lần mở cửa sổ. Kiểm sâu chỉ chạy
        khi bấm nút, vì `import torch` mất vài giây và không nên chặn giao diện.
        """
        goc = self.v_goc.get().strip().strip('"')
        ly_do = self.rt.vi_sao_khong_dung(goc)
        if ly_do:
            self.lbl_goc.configure(text=ly_do, foreground=gd.MAU["loi"])
            self._dem()
            return False
        self.rt.ghi_cau_hinh({"goc": goc})
        py = Path(self.rt.python_cho(goc)).name
        self.lbl_goc.configure(text=f"Sẵn sàng — chạy bằng {py}", foreground=gd.MAU["xong"])
        self._dem()
        if chay_thu:
            self.lbl_goc.configure(text="Đang chạy thử...", foreground=gd.MAU["canh"])
            self.update_idletasks()

            def work():
                ok, mo = self.rt.kiem_tra(goc)
                self.log_q.put(("kiem", (ok, mo)))

            threading.Thread(target=work, daemon=True).start()
        return True

    def _nhac_luong(self):
        try:
            n = int(self.v_luong.get())
        except Exception:                                    # noqa: BLE001
            n = 0
        if n > 0:
            self.lbl_luong.configure(
                text=f"(đang ép {n} — tắt phần tự dò máy của tool)",
                foreground=gd.MAU["canh"])
        else:
            self.lbl_luong.configure(text="(0 = tự dò theo máy)",
                                     foreground="#8a8a8a")
        self._hien_an(self.btn_luong0, n > 0)
        self._hen_tom_tat()

    # ------------------------------------------------------------ xem trước
    #[[ XEM TRUOC NGAY TREN ANH LON — TU BAT KHI KEO (sang 4/10 — user: "bo nut
    #   xem truoc. Vi khi keo se load luon vao anh de thay dc luon").
    #
    #   Keo mot thanh la anh lon tinh lai theo muc cua ANH DANG XEM, nhu Evoto.
    #   May xem truoc (tien trinh con, nap mo hinh ~10 giay) duoc MO SAN khi vao
    #   mo-dun Retouch (_san_may_xem) — lan keo dau khoi cho nap. Tat: bam chip
    #   "Xem trước · …  ✕" duoi anh lon. Bam dup mot tam o dai anh van bat duoc.
    #
    #   Dang chay ca me thi KHONG bat: hai tien trinh cung nap mo hinh len mot
    #   card do hoa la duong ngan nhat toi "OOM on device 0". ]]
    def _mo_xem_truoc(self, anh: str | None = None, tu_dong: bool = False):
        """Bật xem trước: ẢNH LỚN tính lại theo mức của ảnh đang xem.

        tu_dong=True: bật vì người dùng KÉO THANH — không hộp thoại nào, chỉ
        nói ở chip dưới ảnh lớn; máy xem trước đã hỏng thì không tự thử lại
        (kéo thanh là hàng chục lần một giây). Bấm đúp một tấm ở dải ảnh là
        bật hẳn — thử lại cả khi đã hỏng."""
        goc = self._goc_hien()
        if not self.rt.hop_le(goc):
            self._dat_chip("loi", "Chưa xem trước được — chưa chọn đúng thư mục "
                                  "tool retouch")
            return
        if self.worker is not None and self.worker.is_alive():
            self._dat_chip("chua", "Đang chạy retouch — xem trước tạm tắt tới khi "
                                   "chạy xong")
            return
        if not tu_dong:
            self._xem_hong = ""
        elif self._xem_hong:
            self._dat_chip("loi", f"Xem trước đang lỗi: {self._xem_hong[:60]} — bấm "
                                  "đúp một tấm ở dải ảnh để thử lại")
            return
        if anh and anh != self._anh_dang:
            self._anh_dang = anh
            self._ten_hien = Path(anh).name
            self._nap_muc_vao_bang(self._muc_hieu_luc(anh))
        if anh and self.luoi.dang_chon != anh:
            self.luoi.chon(anh)
        self._cap_nhat_pham_vi()
        if not self._anh_dang:
            return
        if not self._dam_bao_may_xem():
            self._dat_chip("loi", "Không mở được xem trước: "
                                  + (self._xem_hong or "không rõ vì sao")[:70])
            return
        self._xem_bat = True
        self._xem_gui_mo(self._anh_dang)
        self._hen_bom_xem()

    def _tat_xem_truoc(self, dong_may: bool = False):
        """Tắt xem trước: ảnh lớn về bản trên đĩa, GIỮ chỗ đang soi. dong_may:
        tắt hẳn tiến trình con (nhường card đồ hoạ cho lượt chạy)."""
        self._xem_bat = False
        if self._hen_tinh is not None:
            try:
                self.after_cancel(self._hen_tinh)
            except tk.TclError:
                pass
            self._hen_tinh = None
        if dong_may:
            self._dong_may_xem()
        if self._anh_dang:
            if self._xem_dang_hien:
                self._hien_anh_dia(self._anh_dang, giu_khung=True)
            else:
                #[[ Anh lon van la ban tren dia (chua kip co ket qua xem
                #   truoc) — khoi nap lai, chi tra chip ve. ]]
                self._chip_dia(self._anh_kq_duong)

    def _dong_may_xem(self):
        m = self._may_xem
        self._may_xem = None
        self._xem_san_sang = False
        self._xem_fp = self._xem_cho_fp = self._xem_mo_dang = None
        self._xem_goc_im = None
        self._xem_dang_tinh = None
        self._xem_can_tinh = False
        self._xem_cuoi = None
        if m is not None:
            m.dong()

    def _nghi_may_xem(self):
        """Rời mô-đun Retouch: tắt máy xem trước — trả card đồ hoạ / bộ nhớ cho
        Lightroom. Quay lại thì _san_may_xem mở lại (ở nền)."""
        if self._xem_bat:
            self._tat_xem_truoc(dong_may=True)
        else:
            self._dong_may_xem()

    def _khi_huy(self, e=None):
        if e is not None and e.widget is not self:
            return
        for ten in ("_hen_xem", "_hen_tinh"):
            h = getattr(self, ten, None)
            if h is not None:
                try:
                    self.after_cancel(h)
                except tk.TclError:
                    pass
                setattr(self, ten, None)
        if self._hen_luu_ma is not None:
            try:
                self._luu_muc()
            except Exception:                                # noqa: BLE001
                pass
        self._dong_may_xem()

    def _dam_bao_may_xem(self) -> bool:
        """Có máy xem trước đang chạy (đúng tool đang chọn) chưa — chưa thì mở.
        False: không mở được (lý do ở _xem_hong) hoặc không được mở lúc này
        (chưa có tool, đang chạy cả mẻ)."""
        goc = self._goc_hien()
        if self._may_xem is not None and (not self._may_xem.song()
                                          or self._xem_goc_tool != goc):
            self._dong_may_xem()
        if self._may_xem is not None:
            return True
        if not self.rt.hop_le(goc) or (self.worker is not None and self.worker.is_alive()):
            return False
        try:
            import xem_truoc
        except Exception as ex:                              # noqa: BLE001
            self._xem_hong = f"{type(ex).__name__}: {ex}"
            return False
        may = xem_truoc.MayXem(self.rt, goc)
        loi = may.bat_dau(self.v_may.get() or "auto")
        if loi:
            self._xem_hong = loi
            self._append(f"! xem trước: {loi}")
            return False
        self._may_xem = may
        self._xem_goc_tool = goc
        self._xem_san_sang = False
        self._xem_fp = self._xem_cho_fp = self._xem_mo_dang = None
        self._xem_goc_im = None
        self._xem_dang_tinh = None
        self._xem_can_tinh = False
        self._xem_cuoi = None
        self._xem_loi_cuoi = ""
        self._append("… máy xem trước: đang nạp mô hình (lần đầu ~10 giây)")
        self._hen_bom_xem()
        return True

    def _san_may_xem(self):
        """Vào mô-đun Retouch / chạy xong: mở SẴN máy xem trước (ảnh lớn vẫn là
        bản trên đĩa) và mở ngầm tấm đang xem — lần kéo đầu khỏi chờ nạp."""
        try:
            if getattr(self.app, "khau_dang", "") != "retouch" or self._xem_hong:
                return
            #[[ Da co may (ke ca may vua chet ma _bom_xem chua kip doc tin
            #   "chet") thi KHONG mo may moi o day: mo de len la nuot mat tin
            #   chet, va vong "chet -> tu mo lai" khong ai chan. ]]
            if self._may_xem is None and not self._dam_bao_may_xem():
                return
            #[[ Tam dang xem DA CO thong so -> tinh xem truoc luon (5/10); chua
            #   co thi chi mo ngam nhu cu. ]]
            if self._anh_dang and not self._xem_bat \
                    and not self._tu_xem_neu_co_muc(self._anh_dang):
                self._xem_xin_mo(self._anh_dang)
        except Exception:                                    # noqa: BLE001
            traceback.print_exc()

    def _xem_xin_mo(self, path: str):
        """Xin tiến trình con mở `path`. MỘT lần mở mỗi lúc: đang mở dở tấm khác
        thì chỉ nhớ tấm mới, tấm kia xong mới gửi — lướt nhanh mười tấm không
        xếp hàng mười lần mở (tiến trình con làm tuần tự từng việc)."""
        self._xem_cho_fp = path
        m = self._may_xem
        if m is None or not self._xem_san_sang or self._xem_mo_dang is not None:
            return
        if path == self._xem_fp and self._xem_goc_im is not None:
            return
        if m.gui(viec="mo_anh", fp=path):
            self._xem_mo_dang = path

    def _xem_gui_mo(self, path: str, hien_dia: bool = False):
        """Đang xem trước mà tấm đổi (hoặc vừa bật): mở tấm đó ở tiến trình
        con rồi tính. Đã mở sẵn (mở ngầm lúc lướt) thì tính luôn.

        hien_dia: vừa bấm sang tấm KHÁC — hiện ngay bản trên đĩa trong lúc chờ,
        không để tên tấm mới nằm dưới ảnh của tấm cũ một hai giây."""
        if hien_dia:
            self._hien_anh_dia(path)
        self._xem_xin_mo(path)
        if self._xem_fp == path and self._xem_goc_im is not None \
                and self._xem_mo_dang is None:
            self._xem_tinh(ep=not self._xem_dang_hien)
        elif self._xem_san_sang and self._may_xem is not None:
            self._dat_chip_xem("đang mở ảnh…")
        else:
            self._dat_chip_xem("đang nạp mô hình…")

    def _nguon_muc(self) -> str:
        p = self._anh_dang
        return ("mức riêng của ảnh này" if p and self._khoa(p) in self._muc_anh
                else "theo mức chung")

    def _muc_xem(self) -> dict:
        """Mức gửi đi: mức chung + mức riêng theo nhóm (như lúc Chạy) — tool
        không nhận mức riêng thì chỉ mức chung (_xem_bo_nhom)."""
        d = self.muc_day_du()
        if self._xem_bo_nhom:
            d = {k: v for k, v in d.items() if ":" not in str(k)}
        return {k: round(float(v), 1) for k, v in d.items()}

    def _hen_tinh_xem(self):
        """Mức vừa đổi: tính lại SAU khi ngừng tay 0,2 s (đang tính thì chỉ
        tính thêm MỘT lần khi lần đó xong — xem _xem_tinh)."""
        if not self._xem_bat:
            return
        if self._hen_tinh is not None:
            try:
                self.after_cancel(self._hen_tinh)
            except tk.TclError:
                pass
        try:
            self._hen_tinh = self.after(200, self._xem_tinh)
        except tk.TclError:
            self._hen_tinh = None

    def _xem_tinh(self, ep: bool = False):
        self._hen_tinh = None
        m = self._may_xem
        if not self._xem_bat or m is None or not self._xem_fp \
                or self._xem_fp != self._anh_dang:
            return
        if self._xem_mo_dang is not None:
            #[[ Dang mo DO mot tam khac o tien trinh con: tinh bay gio la tinh
            #   tren tam do ("chua mo anh nay"). "da_mo" ve se tinh (ep=True). ]]
            return
        muc = self._muc_xem()
        if not ep and self._xem_cuoi == (self._xem_fp, muc):
            return
        if self._xem_dang_tinh is not None:
            #[[ Dang tinh -> chi danh dau, tinh MOT lan nua khi lan nay xong. ]]
            self._xem_can_tinh = True
            return
        if not any(float(v) > 0 for v in muc.values()):
            self._xem_cuoi = (self._xem_fp, muc)
            if self._xem_goc_im is not None:
                self.xem.dat_anh(self._xem_goc_im, truoc=None, mat=self._xem_mat,
                                 giu_khung=True)
                self._xem_dang_hien = True
                self._anh_hien = self._xem_fp
                self._thanh_cu = None
                self._cap_nhat_thanh_xem()
            self._dat_chip_xem("mọi mức đang ở 0")
            return
        self._xem_ma += 1
        self._xem_dang_tinh = self._xem_ma
        self._xem_cuoi = (self._xem_fp, muc)
        self._xem_muc_gui = muc
        m.gui(viec="tinh", ma=self._xem_ma, fp=self._xem_fp, muc=muc)
        self._xem_t0 = time.monotonic()
        self._dat_chip_xem("đang tính…")
        if getattr(self, "_hen_giay_xem", None) is not None:
            try:
                self.after_cancel(self._hen_giay_xem)   # mot bo dem moi luc
            except tk.TclError:
                pass
        self._dem_giay_xem()

    def _dem_giay_xem(self):
        """Đếm giây trên chip lúc đang tính xem trước.

        #[[ 5/10 — user: "keo thanh tren ban .exe khong thay thay doi". Ban cai
        #   chay torch CPU: moi lan keo 5-13 giay moi co anh (do that tren
        #   SAY00551: .exe 6-13 s, .bat / CUDA 0.3-2 s, KET QUA GIONG HET). Trong
        #   luc do anh lon dung yen voi dong "dang tinh…" nho -> tuong keo khong
        #   an. Dem giay de thay may DANG lam; may chay CPU ma CO card NVIDIA thi
        #   chi cho tai ban tang toc GPU. ]]
        """
        self._hen_giay_xem = None
        if self._xem_dang_tinh is None or not self._xem_bat:
            return
        n = int(time.monotonic() - getattr(self, "_xem_t0", time.monotonic()))
        chu = f"đang tính… {n} giây" if n >= 1 else "đang tính…"
        if n >= 3 and getattr(self, "_xem_may", "") == "cpu":
            if getattr(self, "_co_nvidia", None) is None:
                try:
                    import shutil as _sh
                    self._co_nvidia = bool(_sh.which("nvidia-smi"))
                except Exception:                            # noqa: BLE001
                    self._co_nvidia = False
            chu += (" (máy đang tính bằng CPU — menu ··· › Tải bản tăng tốc GPU "
                    "để nhanh hơn)" if self._co_nvidia else " (tính bằng CPU)")
        self._dat_chip_xem(chu)
        try:
            self._hen_giay_xem = self.after(1000, self._dem_giay_xem)
        except tk.TclError:
            self._hen_giay_xem = None

    def _hen_bom_xem(self):
        if self._hen_xem is None and self._may_xem is not None:
            try:
                self._hen_xem = self.after(80, self._bom_xem)
            except tk.TclError:
                self._hen_xem = None

    def _bom_xem(self):
        """Tin từ tiến trình con xem trước (luồng chính)."""
        self._hen_xem = None
        m = self._may_xem
        if m is None:
            return
        import xem_truoc
        for d in m.lay():
            t = d.get("loai")
            if t == "san_sang":
                self._xem_san_sang = True
                self._xem_may = str(d.get("may") or "")      # "cuda" / "cpu" / ...
                #[[ Suc khoe engine (7/10 — giai doan 1): MOT dong trong nhat ky
                #   retouch (va retouch.log) moi lan engine mo, noi ro dang tinh
                #   bang gi — may (cuda/cpu/mps), bo do mat ORT (CUDA / DirectML /
                #   CoreML / CPU), ban saytool. Truoc day chay CPU hay do mat bang
                #   CPU deu im lang, chi thay "cham" / "khong thay mat". ]]
                self._append(f"[engine] máy={self._xem_may or '?'} · bộ dò mặt="
                             f"{d.get('ort') or '?'} · saytool {d.get('ban') or '?'}"
                             + ("" if d.get("ban") else
                                " (bản cũ: mẻ sẽ chạy bằng tiến trình riêng)"))
                if self._xem_cho_fp:
                    self._xem_xin_mo(self._xem_cho_fp)
                    if self._xem_bat:
                        self._dat_chip_xem("đang mở ảnh…")
            elif t == "da_mo":
                self._xem_mo_dang = None
                if d.get("fp") != self._xem_cho_fp:
                    #[[ Anh cu — da bam sang tam khac trong luc mo. Bo, mo tam
                    #   moi nhat (dung mot lan mo, xem _xem_xin_mo). ]]
                    self._xem_fp, self._xem_goc_im = None, None
                    if self._xem_cho_fp:
                        self._xem_xin_mo(self._xem_cho_fp)
                    continue
                self._xem_fp = d.get("fp")
                self._xem_goc_im = xem_truoc.giai_anh(d.get("goc", ""))
                self._xem_mat = d.get("mat") or []
                self._xem_so_mat = int(d.get("so_mat") or 0)
                self._xem_cuoi = None
                if self._xem_bat and self._xem_fp == self._anh_dang \
                        and self._xem_goc_im is not None:
                    #[[ Khong co mat van TINH: tu 0.9.5 co buoc chay tren co the
                    #   (khuyet diem co the, keo dai chan) — noi "keo thanh khong
                    #   doi gi" la sai. Chi noi ra la tool khong thay mat nao.
                    #   Trong luc tinh, anh lon GIU ban dang hien (ban tren dia) —
                    #   khong chop sang ban goc 1400 px roi moi ra ket qua. ]]
                    self._xem_tinh(ep=True)
            elif t == "ket_qua":
                if d.get("ma") == self._xem_dang_tinh:
                    self._xem_dang_tinh = None
                im = xem_truoc.giai_anh(d.get("anh", "")) if d.get("anh") else None
                if self._xem_bat and im is not None and d.get("fp") == self._xem_fp \
                        and self._xem_fp == self._anh_dang:
                    self.xem.dat_anh(im, truoc=self._xem_goc_im, mat=self._xem_mat,
                                     giu_khung=True)
                    self._xem_dang_hien = True
                    self._anh_hien = self._xem_fp
                    self._thanh_cu = None
                    self._cap_nhat_thanh_xem()
                    #[[ BUOC BAT MA KHONG CHAY DUOC (5/10): truoc day tien trinh
                    #   xem truoc lang le bo qua — anh lon y nhu chua retouch ma
                    #   chip van bao "Xem truoc", user tuong keo thanh khong an.
                    #   Nay noi thang tren chip + ly do o Nhat ky (moi bo mot lan). ]]
                    bq = [x for x in (d.get("bo_qua") or []) if x]
                    canh = ""
                    if bq:
                        canh = " · KHÔNG chạy được: " + ", ".join(str(x[0]) for x in bq[:3]) \
                            + (" …" if len(bq) > 3 else "") + " (xem Nhật ký)"
                        khoa_bq = tuple(str(x[0]) for x in bq)
                        if khoa_bq != getattr(self, "_xem_bq_cuoi", None):
                            self._xem_bq_cuoi = khoa_bq
                            for x in bq:
                                self._append(f"! xem trước: bỏ qua “{x[0]}” — "
                                             f"{x[1] if len(x) > 1 else ''}")
                    else:
                        self._xem_bq_cuoi = None
                    self._dat_chip_xem(self._nguon_muc() + (
                        "" if self._xem_so_mat else
                        " · tool không thấy khuôn mặt nào") + canh)
                if self._xem_can_tinh:
                    self._xem_can_tinh = False
                    self._xem_tinh()
            elif t == "hong":
                if d.get("ma") is not None and d.get("ma") == self._xem_dang_tinh:
                    self._xem_dang_tinh = None
                    #[[ Ban saytool khong nhan muc rieng theo nhom (khoa
                    #   "nam:vet") -> tinh lai voi muc chung, va noi ra. ]]
                    gui = getattr(self, "_xem_muc_gui", {}) or {}
                    if "chua mo anh" in str(d.get("loi") or ""):
                        gui = {}      # ảnh ở tiến trình con đã đổi — không phải tool chê khoá nhóm
                    if not self._xem_bo_nhom and any(":" in str(k) for k in gui):
                        self._xem_bo_nhom = True
                        self._append("… xem trước: tool không nhận mức riêng theo "
                                     "nhóm — xem trước chỉ áp mức Chung")
                        self._xem_cuoi = None
                        self._xem_tinh(ep=True)
                        continue
                elif d.get("ma") is None:
                    if d.get("fp") is None:
                        #[[ Hong luc KHOI DONG (import saytool…): tien trinh con
                        #   thoat ngay sau dong nay — giu ly do de noi o "chet". ]]
                        self._xem_loi_cuoi = str(d.get("loi") or "")[:300]
                    else:
                        self._xem_mo_dang = None
                        if d.get("fp") != self._xem_cho_fp:
                            if self._xem_cho_fp:
                                self._xem_xin_mo(self._xem_cho_fp)
                            continue
                loi = str(d.get("loi") or "lỗi không rõ").splitlines()[0][:120]
                self._append(f"! xem trước: {loi}")
                if self._xem_bat:
                    self._dat_chip_xem(f"Xem trước lỗi: {loi[:60]}", loai="loi")
                if self._xem_can_tinh:
                    self._xem_can_tinh = False
                    self._xem_tinh()
            elif t == "chet":
                ly_do = (self._xem_loi_cuoi.splitlines() or [""])[0][:120]
                self._append("! tiến trình xem trước đã dừng"
                             + (f" — {ly_do}" if ly_do else ""))
                #[[ Danh dau HONG: keo thanh khong tu mo lai (tranh vong mo ->
                #   chet -> mo). Bam dup mot tam o dai anh la thu lai. ]]
                self._xem_hong = ly_do or "tiến trình xem trước đã dừng"
                bat = self._xem_bat
                self._may_xem = None
                self._xem_san_sang = False
                self._xem_dang_tinh = None
                self._xem_mo_dang = None
                self._xem_fp, self._xem_goc_im = None, None
                if bat:
                    self._tat_xem_truoc()
                    self._dat_chip("loi", "Xem trước đã dừng — bấm đúp một tấm ở dải "
                                          "ảnh để bật lại")
                return
        self._hen_bom_xem()

    def _doi_ghide(self):
        """Bật/tắt ô “Ra” theo tuỳ chọn ghi đè, và nhắc hậu quả."""
        gd_on = self.v_ghide.get()
        tt = "disabled" if gd_on else "normal"
        for w in (self.e_ra, self.btn_ra):
            w.configure(state=tt)
        self.lbl_ra.configure(
            foreground=gd.MAU["mo2"] if gd_on else gd.MAU["chu"])
        self.lbl_ghide.configure(
            text="Ảnh gốc bị thay thế — không lùi lại được." if gd_on else "")
        self._hien_an(self.lbl_ghide, gd_on)
        self._nho_thu_muc()
        try:
            self._dem()
        except Exception:                                    # noqa: BLE001
            pass

    def _dem(self):
        """(tổng ảnh vào, số đã có kết quả) — và vẽ lại lưới ảnh từ CHÍNH danh
        sách đó (rt.ds_anh: cùng cách lọc với tool, không đếm lần hai).

        #[[ GHI DE: KHONG DEM DUOC BANG FILE, phai nghe tool bao.
        #
        #   Anh ra de len chinh anh vao, nen nhin thu muc khong biet tam nao
        #   da lam. Dem bang file luon ra 0 da xong -> thanh tien do dung im o
        #   0/2021 suot ca me, trong khi nhat ky chay am am. Nguoi dung khong
        #   biet no con song hay da treo.
        #
        #   saytool CO in tien do: "  10/2021  0.74s/anh  con lai ~24.8 phut",
        #   moi 10 anh mot dong. _pump bat dong do vao _tien_do_tool.
        #   Thua mot chut do tre (10 anh) nhung dung han so 0 chet cung.
        #]]
        #[[ O "Vao" / "Ra" TRONG la CHUA CO, khong phai thu muc hien hanh:
        #   Path("") == Path(".") — ban cu dem anh trong thu muc app dang dung. ]]
        """
        s_vao = self.v_vao.get().strip().strip('"')
        s_ra = self.v_ra.get().strip().strip('"')
        ghi_de = bool(self.v_ghide.get())
        ds = self.rt.ds_anh(Path(s_vao) if s_vao else None,
                            None if (ghi_de or not s_ra) else Path(s_ra),
                            self.v_dequy.get())
        tong = len(ds)
        if ghi_de:
            xong = min(int(getattr(self, "_tien_do_tool", 0) or 0), tong)
        else:
            xong = sum(1 for _p, da in ds if da)
        lc = getattr(self, "_luot_chay", None)
        if lc and self.worker and self.worker.is_alive():
            #[[ Dang chay anh DA CHON / theo nhom muc tren thu muc tam: dem theo
            #   LUOT CHAY (xem start), khong theo file thu muc ra. ]]
            da = min(lc["xong"] + int(getattr(self, "_tien_do_tool", 0) or 0), lc["tong"])
            self.pb.configure(maximum=max(lc["tong"], 1), value=da)
            self.lbl_tt.configure(text=f"Đang chạy {da}/{lc['tong']} ảnh"
                                       + self._nhip())
        elif not tong:
            self.pb.configure(maximum=1, value=0)
            self.lbl_tt.configure(text="Thư mục vào chưa có ảnh nào")
        else:
            self.pb.configure(maximum=max(tong, 1), value=xong)
            self.lbl_tt.configure(
                text=f"{xong}/{tong} ảnh đã có kết quả — còn {tong - xong}"
                     + self._nhip())
        self._ds_luoi = ds
        if self._hen_luoi is None:
            try:
                self._hen_luoi = self.after_idle(self._ve_luoi)
            except tk.TclError:
                pass
        return tong, xong

    def _nhip(self) -> str:
        """“· 4,9 s/ảnh · còn ~57 phút” — đo bằng SỐ FILE ĐÃ RA, không tin log.

        #[[ VI SAO TU DO CHU KHONG DOC DONG TIEN DO CUA TOOL.
        #
        #   saytool chi in tien do MOI 10 ANH. Voi 5 giay mot anh la gan mot
        #   phut moi co mot dong — nguoi dung nhin man hinh dung im, khong biet
        #   nhanh hay cham, va cau hoi dau tien luon la "bao lau nua thi xong".
        #
        #   Dem file trong thu muc ra thi biet lien tuc, va dung ke ca khi tool
        #   khong noi gi. Moc t0 lay tu luc bam Chay, va tru di so anh DA CO
        #   san tu luoc truoc — khong tru thi lan chay tiep tuc se ra toc do
        #   nhanh gia.
        #]]
        """
        t0 = getattr(self, "_t0", None)
        if not t0 or not (self.worker and self.worker.is_alive()):
            return ""
        giay = time.monotonic() - t0
        lam = self.pb.cget("value") - getattr(self, "_xong_dau", 0)
        try:
            lam = float(lam)
        except (TypeError, ValueError):
            return ""
        if lam < 1 or giay < 5:
            return "  ·  đang khởi động…"
        moi_anh = giay / lam
        con = max(0.0, float(self.pb.cget("maximum")) - self.pb.cget("value"))
        phut = con * moi_anh / 60.0
        return (f"  ·  {moi_anh:.1f} s/ảnh  ·  còn ~"
                + (f"{phut:.0f} phút" if phut < 90
                   else f"{phut / 60:.1f} giờ"))

    def _mo_cua_so_tai(self, can=None) -> bool:
        """Mo cua so tai tai nguyen. True = da tai duoc it nhat mot goi.

        Tra True thi ben goi se kiem lai — de nguoi dung thay ket qua moi
        ngay, khong phai tu bam lai nut Kiem tra.
        """
        try:
            import tai_nguyen as tn
        except Exception as ex:                              # noqa: BLE001
            messagebox.showerror(
                "Không có trình tải",
                "Bản cài này thiếu phần tải tài nguyên "
                f"({type(ex).__name__}).\n\n"
                "Đây là lỗi đóng gói — báo lại để dựng bản mới.",
                parent=self)
            return False
        d = TaiTaiNguyenDialog(self, tn, can)
        self.wait_window(d)
        return bool(d.xong_het)

    def _hoi_chep(self, muc: dict | None = None) -> bool:
        """Thiếu mô hình thì hỏi chép ngay tại đây. True = xong, chạy tiếp được.

        VÌ SAO CẢ NÚT "KIỂM TRA" CŨNG GỌI HÀM NÀY
            Bản trước chỉ chặn ở nút Chạy. Nút Kiểm tra thì chẩn đoán đúng, in
            ra đủ cả tên file lẫn tên ứng viên, rồi kết luận "chưa sẵn sàng" —
            và hết. Người dùng đọc xong dừng lại, hoàn toàn hợp lý: một cái nút
            nói cho anh biết hỏng gì mà không sửa được thì nó vừa tạo ra một
            việc phải làm, vừa không nói rõ làm ở đâu.

            Đã xảy ra thật 3/9. Nút nào phát hiện được thì nút đó phải sửa được.
        """
        goc = Path(self.v_goc.get().strip().strip('"'))
        if not self.rt.hop_le(goc):
            return False
        thieu = self.rt.mo_hinh_can(goc, muc)
        if not thieu:
            return True
        co = [t for t in thieu if t["ung_vien"]]
        khong = [t for t in thieu if not t["ung_vien"]]
        if khong:
            messagebox.showerror(
                "Thiếu file mô hình",
                "Tool retouch cần những file này, và không tìm thấy file nào "
                "thay được:\n\n"
                + "\n".join(f"   {t['dich']}   (cho “{t['buoc']}”)" for t in khong)
                + f"\n\nChúng phải nằm trong {goc}.\n\n"
                "Tạm thời: kéo thanh của tính năng đó về 0 để bỏ qua nó.",
                parent=self)
            return False
        if not messagebox.askokcancel(
                "Thiếu file mô hình — chép giúp?",
                "saytool tìm mô hình ở một đường dẫn cố định mà máy này chưa có. "
                "File thì có sẵn, chỉ nằm chỗ khác.\n\n"
                "Sẽ CHÉP (không xoá, không di chuyển):\n\n"
                + "\n".join(f"   {t['ung_vien'][0]}\n      →  {t['dich']}"
                             for t in co)
                + "\n\nCăn cứ: chay_giao_dien.bat của anh gọi đúng những file "
                  "này làm --model và --model-nong-cam.\n\nChép?",
                parent=self):
            return False
        try:
            dong = self.rt.chep_mo_hinh(goc, co)
        except OSError as ex:
            messagebox.showerror("Chép không được", str(ex), parent=self)
            return False
        for d in dong:
            self._append("  chép mô hình: " + d)
        self.lbl_goc.configure(text="Đã chép mô hình xong — bấm Kiểm tra lại.",
                               foreground=gd.MAU["xong"])
        return not self.rt.mo_hinh_can(goc, muc)

    # ------------------------------------------------------------ chạy
    def _bi_khoa(self) -> bool:
        """Chốt bản quyền ngay đầu việc nặng (7/10).

        App._khoa_chan nói "mọi đường vào việc thật đều đi qua đây" — nhưng chỉ
        App.open_retouch gọi nó, còn hai đường khác vào màn này (thanh mô-đun,
        _chon_khau) và chính nút Chạy retouch / vòng tự retouch ảnh mới thì
        không: hết hạn mà lớp phủ chưa kịp hiện (soi mỗi phút) là vẫn chạy
        được mẻ mới. Bản không có App thật (bài kiểm dựng tay) thì không chặn."""
        chan = getattr(self.app, "_khoa_chan", None)
        return bool(chan is not None and chan())

    def start(self):
        if self._bi_khoa():
            return
        if not self._kiem():
            messagebox.showinfo("Chưa dùng được tool retouch",
                                self.lbl_goc.cget("text"), parent=self)
            return
        vao = Path(self.v_vao.get().strip().strip('"'))
        ra = Path(self.v_ra.get().strip().strip('"'))
        if not vao.is_dir():
            messagebox.showinfo("Thiếu thư mục vào", f"Không có:\n{vao}", parent=self)
            return
        ghi_de = bool(self.v_ghide.get())
        if not ghi_de:
            if not str(ra).strip():
                messagebox.showinfo("Thiếu thư mục ra",
                                    "Chọn nơi lưu ảnh đã retouch, hoặc tick "
                                    "“Ghi đè lên ảnh gốc”.", parent=self)
                return
            #[[ Ra TRUNG Vao la mat anh goc mot cach AM THAM. Nguoi dung muon
            #   ghi de thi co o tick rieng — o do co canh bao va hoi xac nhan.
            #]]
            try:
                if ra.resolve() == vao.resolve():
                    messagebox.showerror(
                        "Hai thư mục trùng nhau",
                        "Thư mục ra phải KHÁC thư mục vào.\n\n"
                        "Muốn retouch đè lên ảnh gốc thì tick "
                        "“Ghi đè lên ảnh gốc” — ở đó có cảnh báo rõ ràng.",
                        parent=self)
                    return
            except OSError:
                pass
        #[[ TU RETOUCH ANH MOI: chup danh sach anh CO SAN + muc cho anh moi NGAY
        #   LUC BAM — anh xuat hien sau moc nay (ke ca trong luot nay) moi la moi.
        #   Chi giao cho self._theo_doi luc THAT SU chay / vao theo doi (huy o
        #   hop hoi nao thi khong theo doi gi). ]]
        theo_doi = (self._chuan_bi_theo_doi(vao, ra, ghi_de)
                    if self.v_tu_moi.get() else None)
        tong_tm, _xong_tm = self._dem()
        if not tong_tm:
            if theo_doi:
                self._vao_theo_doi(theo_doi, "thư mục chưa có ảnh")
                return
            messagebox.showinfo("Không có ảnh", f"{vao}\nkhông có ảnh nào.",
                                parent=self)
            return
        #[[ CHI CHAY ANH DANG CHON (6/10 — user: "Khi bam Chay Retouch thi anh
        #   nao duoc Select thi se chay va xuat anh do"). Chon o dai anh (Ctrl+A
        #   = ca thu muc). Chon RIENG MOT PHAN la y muon xuat lai CHINH nhung tam
        #   do -> lam lai ca tam da co ket qua. Chon het thi giu nhu cu: bo qua tam
        #   da xong tru khi tick "Lam lai" — me hang nghin anh sap giua chung bam
        #   chay lai van di tiep tu cho dung. ]]
        tat_ca = [str(p) for p, _x in self._ds_luoi]
        luoi = getattr(self, "luoi", None)
        da_chon = {str(p) for p in (luoi.ds_chon() if luoi is not None else [])}
        ds_chay = [p for p in tat_ca if p in da_chon]
        if not ds_chay and theo_doi:
            self._vao_theo_doi(theo_doi, "chưa chọn ảnh nào để chạy trước")
            return
        if not ds_chay:
            messagebox.showinfo("Chưa chọn ảnh nào",
                                "Bấm chọn ảnh cần retouch ở dải ảnh (Ctrl+A để chọn "
                                "hết) rồi bấm Chạy retouch.", parent=self)
            return
        mot_phan = len(ds_chay) < len(tat_ca)
        xong_cua = {str(p): bool(x) for p, x in self._ds_luoi}
        tong = len(ds_chay)
        xong = sum(1 for p in ds_chay if xong_cua.get(p))
        lam_lai = bool(self.v_lamlai.get()) or mot_phan
        con = tong if (lam_lai or ghi_de) else tong - xong
        if not con and theo_doi:
            self._vao_theo_doi(theo_doi, "ảnh đã chọn đều có kết quả")
            return
        if not con:
            messagebox.showinfo("Đã xong từ trước",
                                f"Cả {tong} ảnh đều đã có kết quả.\n\n"
                                "Muốn làm lại: chọn riêng những tấm cần làm ở dải "
                                "ảnh, hoặc tick “Làm lại cả ảnh đã có kết quả”.",
                                parent=self)
            return

        #[[ NHOM THEO MUC (sang 4/10 — muc rieng tung anh + Sync).
        #
        #   Moi anh mot bo muc HIEU LUC (muc rieng cua no, khong thi muc chung).
        #   saytool chi nhan MOT bo muc cho ca thu muc, nen anh cung muc gom mot
        #   luot: MOT nhom (khong ai dat rieng — truong hop thuong) thi chay y
        #   het truoc day, thang tren thu muc vao. Nhieu nhom thi moi nhom mot
        #   thu muc tam (lien ket cung) + mot luot `chay` cua CHINH saytool.
        #   Nhom muc 0 het (khong retouch) thi chep nguyen ban sang thu muc ra
        #   — thu muc giao khach du anh, va bo dem "da lam" dung. ]]
        de_quy = bool(self.v_dequy.get())
        muc_cua = {p: self._loc_muc(self._muc_hieu_luc(p)) for p in ds_chay}
        #[[ VUA MUC CHUNG VUA MUC RIENG GIOI TINH -> HOI (6/10). Xem
        #   rt.co_ca_chung_rieng. "Rieng": muc chung cua tinh nang chia nhom ve
        #   0 — chi nhom da dat rieng duoc retouch; "Chung": bo muc rieng, moi
        #   khuon mat theo muc chung. Chi doi muc CUA LUOT CHAY NAY, khong sua
        #   muc da luu. ]]
        nhom_duoc = self._ten_theo_nhom()
        ca_hai = [p for p in ds_chay if self.rt.co_ca_chung_rieng(muc_cua[p], nhom_duoc)]
        if ca_hai:
            ten = ", ".join(Path(p).name for p in ca_hai[:3]) + (" …" if len(ca_hai) > 3 else "")
            dung = hoi_nut(
                self, "Dùng mức Chung hay mức riêng giới tính?",
                f"{len(ca_hai)} ảnh ({ten}) đang bật CẢ mức Chung LẪN mức riêng "
                "theo giới tính / nhóm mặt.\n\n"
                "• Mức Chung: mọi khuôn mặt theo mức Chung, bỏ mức riêng.\n"
                "• Riêng giới tính: chỉ nhóm đã đặt riêng được retouch theo mức "
                "của nhóm đó — mức Chung về 0.\n\n"
                "Chỉ áp cho lượt chạy này, không đổi mức đã lưu.",
                [("chung", "Dùng mức Chung"), ("rieng", "Dùng riêng giới tính"),
                 (None, "Huỷ")])
            if dung is None:
                return
            for p in ca_hai:
                muc_cua[p] = self.rt.chon_chung_rieng(muc_cua[p], nhom_duoc, dung)
            self._append(f"… {len(ca_hai)} ảnh có cả mức Chung lẫn riêng giới tính: "
                         + ("dùng mức Chung" if dung == "chung"
                            else "dùng mức riêng giới tính (Chung về 0)"))
        nhom = self.rt.nhom_theo_muc(ds_chay, lambda p: muc_cua[p])
        #[[ any(muc.values()) da dung cho ca muc rieng, vi muc_day_du() gop
        #   ca hai vao mot tu dien phang. Chi doi loi chu: "ba thanh keo" la
        #   con so cua ban cu, gio la sau va con them nam nhom. ]]
        if (not nhom or all(self.rt.muc_trong(m) for m, _a in nhom)) and theo_doi:
            self._vao_theo_doi(theo_doi, "ảnh đã chọn đều ở mức 0")
            return
        if not nhom or all(self.rt.muc_trong(m) for m, _a in nhom):
            messagebox.showinfo(
                "Chưa bật tính năng nào",
                "Mọi thanh kéo đều ở 0 — kể cả mức riêng theo nhóm"
                + (" và mức riêng từng ảnh" if len(nhom) > 1 else "")
                + ". Không có gì để làm.", parent=self)
            return
        #[[ CHAY TREN THU MUC TAM khi: nhieu muc (moi muc mot luot), hoac chi
        #   chay MOT PHAN thu muc (anh dang chon). Ghi de + thu muc tam KHONG con
        #   bi chan (6/10 — user bi chan "Ghi de chi chay duoc MOT muc"): saytool
        #   ghi ra thu muc tam rieng, app tu thay anh goc — rt.dua_ket_qua_ra. ]]
        theo_tam = len(nhom) > 1 or mot_phan

        #[[ HOI XAC NHAN GHI DE — sau khi da dem duoc so anh.
        #
        #   saytool cung hoi, nhung bang input() tren dong lenh: tien trinh con
        #   cua app khong co ban phim nen cau hoi do se treo mai mai. Nen app
        #   phai hoi thay, va bao saytool khoi hoi (--dong-y-ghi-de).
        #
        #   Hoi SAU khi dem de noi duoc SO ANH va DUONG DAN that — saytool ghi
        #   chu ro ly do: "phai nhin thay so anh va duong dan TRUOC khi go dong
        #   y", vi hai lan retouch chong len nhau thi khong the biet tu noi
        #   dung anh la da lam roi hay chua.
        #]]
        if ghi_de and not messagebox.askokcancel(
                "Ghi đè lên ảnh gốc?",
                f"{tong} ảnh trong:\n    {vao}\n\n"
                "sẽ bị THAY THẾ bằng bản đã retouch. Ảnh gốc không còn bản "
                "sao, và KHÔNG lùi lại được.\n\n"
                "Chạy lại lần nữa sẽ retouch chồng lên kết quả lần này.\n\n"
                "Đồng ý ghi đè?", icon="warning", parent=self):
            return

        #[[ Viec tung nhom: chi nhung tam CON PHAI LAM (tool tu bo qua tam da
        #   co ket qua, nhung dung thu muc tam cho nhom da xong het la ton mot
        #   lan nap mo hinh vo ich). ]]
        viec = []
        for m, a in nhom:
            con_g = [p for p in a if lam_lai or ghi_de or not xong_cua.get(p)]
            if con_g:
                viec.append((m, con_g, self.rt.muc_trong(m)))
        if len(nhom) > 1:
            dong = []
            for m, a, la0 in viec:
                ten = ", ".join(Path(p).name for p in a[:3]) + (" …" if len(a) > 3 else "")
                dong.append(f"   • {len(a)} ảnh ({ten}): "
                            + ("mức 0 hết — chép nguyên bản sang thư mục ra, "
                               "không retouch" if la0 else self._mo_ta_muc(m)))
            n_chay = sum(1 for _m, _a, la0 in viec if not la0)
            if not messagebox.askokcancel(
                    "Chạy theo từng nhóm mức?",
                    "Các ảnh đang có mức KHÁC NHAU (mức riêng từng ảnh) — tool "
                    f"chạy {n_chay} lượt, mỗi lượt một mức:\n\n" + "\n".join(dong)
                    + "\n\nMỗi lượt nạp mô hình một lần (thêm ~10 giây). Chạy?",
                    parent=self):
                return

        #[[ Chan TRUOC khi chay, dung de no chet o anh dau — xem _hoi_chep().
        #   Hoi du mo hinh cho MOI nhom: muc lon nhat cua tung tinh nang. ]]
        if not self._hoi_chep(self.rt.gop_muc([m for m, _a, la0 in viec if not la0])):
            return

        tam_goc = None
        if theo_tam:
            try:
                tam_goc = self.rt.tao_thu_muc_tam(vao)
            except OSError as ex:
                messagebox.showerror("Không tạo được thư mục tạm",
                                     "Chạy ảnh đã chọn / theo nhóm mức cần một thư "
                                     f"mục tạm:\n{ex}", parent=self)
                return

        #[[ CHAN DUONG DAN CO DAU TIENG VIET — xem khong_ascii() ben retouch.py.
        #   TU 14/9: chi con chan khi ban saytool dang tro toi la ban CU (chua
        #   co saytool/duong_dan.py). Ban moi da doc/ghi duoc duong dan co dau,
        #   chan nua la chan oan — nguoi dung phai di doi ten thu muc vo co.
        #   Truyen goc vao de no nhin ban DANG DUNG ma quyet dinh, khong doan.
        #   Chay theo nhom thi xet ca thu muc tam (no co the nam o thu muc tam
        #   cua he thong — duong dan co ten nguoi dung co dau).
        #]]
        xau = self.rt.khong_ascii(vao, ra, *([tam_goc] if tam_goc else []),
                                  goc=self.v_goc.get().strip().strip('"'))
        if xau:
            self.rt.don_thu_muc_tam(tam_goc)
            messagebox.showerror(
                "Đường dẫn có dấu tiếng Việt",
                "Bản tool retouch đang chọn là bản CŨ — nó dùng OpenCV thẳng, "
                "mà OpenCV trên Windows không mở được file có dấu trong đường "
                "dẫn:\n\n"
                + "\n".join(f"   {x}" for x in xau)
                + "\n\nChạy tiếp thì cả mẻ trượt hết, và nó báo “check file "
                  "path/integrity” nghe như ảnh hỏng — dễ đi tìm sai chỗ.\n\n"
                  "Cách xử lý, chọn một trong hai:\n"
                  "   • Cập nhật tool retouch lên bản có saytool/duong_dan.py "
                  "(bản này đọc/ghi được đường dẫn có dấu)\n"
                  "   • Hoặc Export ra một thư mục tên không dấu, ví dụ "
                  "G:\\2905_export",
                parent=self)
            return
        #[[ "muc" trong retouch.json la MUC CHUNG (anh khong co muc rieng) —
        #   khong phai muc cua anh dang xem tren bang. Muc rieng tung anh ghi o
        #   file rieng cua thu muc vao (_luu_muc). ]]
        self._luu_muc()
        self.rt.ghi_cau_hinh({"vao": str(vao), "ra": str(ra),
                              "muc": self._muc_chung_day_du(),
                              "may": self.v_may.get(),
                              "luong": int(self.v_luong.get()),
                              "che_do": self.v_che_do.get(),
                              "ghi_de": bool(self.v_ghide.get())})
        #[[ Ghi hai thu muc vao TRANG THAI CUA BUOI, khong chi vao retouch.json.
        #   retouch.json giu lua chon GAN NHAT (dung chung moi buoi); bang trang
        #   thai can biet buoi 1308 export ra dau, buoi 0306 ra dau. Hai muc
        #   dich khac nhau nen giu ca hai cho.
        #]]
        self._t0 = time.monotonic()
        try:
            import trang_thai as tt
            goc = self.app.folder()
            if goc:
                tt.ghi(tt.ten_buoi(goc), thu_muc_export=str(vao),
                       thu_muc_retouch=str(ra))
        except Exception:                                    # noqa: BLE001
            pass

        self._dung_hen_quet()
        self._theo_doi = theo_doi
        if theo_doi:
            self._append("… bật “Tự retouch ảnh mới”: chạy xong sẽ theo dõi thư mục "
                         "Vào, ảnh mới dùng mức chung: " + self._mo_ta_muc(theo_doi["muc"]))
        self._chay_viec(
            vao=vao, ra=ra, ghi_de=ghi_de, lam_lai=lam_lai, de_quy=de_quy,
            viec=viec, tam_goc=tam_goc, muc_thang=nhom[0][0], xong_dau=xong,
            tieu_de=f"{con} ảnh cần làm"
                    + (f" (ảnh đã chọn, trên {len(tat_ca)} ảnh của thư mục)"
                       if mot_phan else "")
                    + (f", {sum(1 for *_x, la0 in viec if not la0)} lượt theo mức"
                       if len(nhom) > 1 else ""))

    def _chay_viec(self, *, vao, ra, ghi_de, lam_lai, de_quy, viec, tam_goc,
                   muc_thang, xong_dau, tieu_de):
        """Chạy retouch ở luồng nền — chung cho nút Chạy retouch (start) và lượt
        tự retouch ảnh mới (_chay_anh_moi). Mọi câu hỏi / kiểm tra đã xong ở bên
        gọi. viec = [(mức, [ảnh], mức 0 hết?)]; tam_goc None = MỘT lượt thẳng
        trên thư mục vào với muc_thang."""
        #[[ ENGINE THUONG TRU (7/10, giai doan 1 tai cau truc): me chay NGAY
        #   TRONG may xem truoc — mo hinh da nap, mot bo tren card (xem
        #   retouch.chay(engine=)). Chua co may thi mo luon (nap ~4 s — truoc
        #   day moi lan bam deu phai nap). Khong mo duoc (tool hong...) thi lui
        #   ve tien trinh con cu; luc do moi phai tat may xem truoc de nhuong
        #   card: no giu mo hinh tren card, ca me nap them mot bo nua la het. ]]
        if self._may_xem is None and not self._xem_hong:
            self._dam_bao_may_xem()
        self._engine_dung = self._may_xem is not None and self._may_xem.song()
        if self._engine_dung:
            self._tat_xem_truoc(dong_may=False)
            self._append("… chạy mẻ trong máy xem trước (mô hình đã nạp sẵn) — "
                         "xem trước tạm dừng tới khi xong")
        elif self._may_xem is not None:
            self._tat_xem_truoc(dong_may=True)
            self._append("… đã tắt xem trước để nhường card đồ hoạ cho lượt chạy")
        goc = Path(self.v_goc.get().strip().strip('"'))
        luong = int(self.v_luong.get())
        #[[ Doc bien Tk O DAY (luong chinh): luong nen chi cam gia tri. ]]
        may = self.v_may.get()
        che_do = self.v_che_do.get()
        self._dat_dang_chay(True)
        #[[ Giu 80 dong log cuoi de con GIAI THICH duoc ma thoat.
        #   Ma 3221225477 mot minh khong noi gi; ma do CONG voi dong "OOM on
        #   device 0" thi noi duoc chinh xac phai lam gi.
        #]]
        self._luong_dang_chay = luong
        #[[ So anh DA CO truoc khi bam Chay. Khong tru no thi lan chay tiep tuc
        #   (600 anh da xong tu luot truoc) se ra toc do nhanh gia. ]]
        self._xong_dau = xong_dau
        self._log_cuoi: list[str] = []
        #[[ Gom RIENG cac dong "! BO QUA" thay vi doc lai tu _log_cuoi: chung
        #   duoc in luc NAP BUOC, tuc ngay dau lượt chay, nen mot buoi vai tram
        #   anh la chung da troi khoi 80 dong cuoi tu lau. ]]
        self._bi_bo: list = []
        self._so_dong_log = 0        # đếm để biết tool có nói gì không
        self._append(f"\n=== {datetime.now():%H:%M:%S}  {tieu_de}, {luong} luồng ===")

        #[[ MA SAP: tien trinh bi giet GIUA CHUNG, khong phai chay xong hay
        #   nguoi dung bam Dung. Gap mot trong so nay thi tu chay lai.
        #]]
        MA_SAP = (3221225477,   # 0xC0000005 ACCESS_VIOLATION
                  3221226356,   # 0xC0000374 HEAP_CORRUPTION
                  3221226505)   # 0xC0000409 FAIL_FAST
        self._dung_tay = False
        #[[ Dat lai tien do moi lan chay. Khong dat lai thi lan chay thu hai
        #   bat dau tu con so cua lan truoc — thanh tien do nhay vot roi dung
        #   im, te hon la dung im tu dau. ]]
        self._tien_do_tool = 0

        #[[ Tien do LUOT CHAY tren thu muc tam: ket qua chi ra thu muc that khi
        #   xong tung luot, dem file thu muc ra thi thanh tien do dung im. Dem bang
        #   so anh da dua ra + tien do tool cua luot dang chay (xem _dem). ]]
        self._luot_chay = ({"tong": sum(len(a) for _m, a, _l in viec), "xong": 0}
                           if tam_goc is not None else None)
        if tam_goc is not None:
            self._xong_dau = 0

        def chay_mot(thu_muc, muc, ra=ra, ghi_de=ghi_de, lam_lai=lam_lai):
            #[[ TU CHAY LAI khi sap giua me anh.
            #
            #   0xC0000374 lam sap tien trinh o anh 556/3465. Tien trinh da
            #   hong vung nho thi khong cuu duoc, nhung CA ME thi cuu duoc:
            #   tool tu bo qua anh da co ket qua, nen chay lai la di tiep tu
            #   dung cho dung. Truoc day nguoi dung phai ngoi canh bam Chay
            #   lai hang chuc lan cho het 3465 anh.
            #
            #   DIEU KIEN DUNG LAI: lan vua roi phai lam duoc THEM it nhat mot
            #   tam. Khong tien bo ma van chay lai la lap vo han o dung tam
            #   anh gay sap - te hon la dung han, vi nguoi dung tuong no dang
            #   chay.
            #]]
            lan = 0
            while True:
                lan += 1
                #[[ rt.dem() chu KHONG phai self._dem(): _dem() dong vao
                #   widget Tk (thanh tien do, nhan trang thai), ma day la
                #   LUONG NEN - dong vao Tk tu luong khac la mot nguon treo
                #   giao dien kinh dien. rt.dem() chi dem file, khong ve gi.
                #]]
                _, truoc = self.rt.dem(thu_muc, ra, de_quy)
                ma_cuoi = 0
                #[[ engine = may xem truoc DANG SONG luc goi (doc moi lan: no
                #   chet giua me thi lan tu-chay-lai di duong tien trinh con). ]]
                for loai, gt in self.rt.chay(
                        goc, thu_muc, ra, muc, may=may,
                        de_quy=de_quy, lam_lai=lam_lai,
                        luong=luong, che_do=che_do,
                        ghi_de=ghi_de,
                        engine=(self._may_xem if getattr(self, "_engine_dung", False)
                                else None)):
                    if loai == "pid":
                        self.proc = gt
                        continue
                    if loai == "ma":
                        ma_cuoi = int(gt or 0)
                        continue      # giu lai: con co the chay tiep
                    self.log_q.put((loai, gt))

                if ma_cuoi not in MA_SAP or self._dung_tay:
                    return ma_cuoi
                tong, sau = self.rt.dem(thu_muc, ra, de_quy)
                con = tong - sau
                if sau <= truoc or con <= 0:
                    return ma_cuoi
                self.log_q.put((
                    "dong",
                    f"=== sap (ma {ma_cuoi}) sau khi lam them {sau - truoc} anh"
                    f" - tu chay lai, con {con} anh (lan {lan + 1}) ==="))

        def work():
            ma = 0
            try:
                if tam_goc is None:
                    ma = chay_mot(vao, muc_thang)
                else:
                    n_luot = sum(1 for _m, _a, la0 in viec if not la0)
                    i = 0
                    lc = self._luot_chay
                    for m, a, la0 in viec:
                        if self._dung_tay:
                            break
                        if la0:
                            #[[ Muc 0 het = khong retouch. Ghi de thi anh goc giu
                            #   nguyen la dung; ra thu muc khac thi chep nguyen ban
                            #   sang de thu muc giao khach du anh. ]]
                            n = 0 if ghi_de else self.rt.chep_nguyen_ban(
                                a, vao, ra, de_quy, lam_lai)
                            if lc is not None:
                                lc["xong"] += len(a)
                            self.log_q.put(("dong", f"=== {len(a)} ảnh mức 0 hết: "
                                                    + ("giữ nguyên ảnh gốc" if ghi_de
                                                       else f"chép nguyên bản {n} ảnh "
                                                            "sang thư mục ra") + " ==="))
                            continue
                        i += 1
                        d = tam_goc / f"nhom_{i}"
                        d_ra = tam_goc / f"ra_{i}"
                        lien, chep = self.rt.dung_thu_muc_nhom(vao, a, d, de_quy)
                        self.log_q.put(("dong", f"=== lượt {i}/{n_luot}: {len(a)} ảnh"
                                                + (f" (chép {chep} ảnh vào thư mục "
                                                   f"tạm)" if chep else "") + " ==="))
                        #[[ saytool LUON ghi ra thu muc tam rieng (d_ra, moi tinh,
                        #   khong --ghi-de, khong --lam-lai — sap giua chung thi
                        #   chay lai di tiep dung cho), roi app dua tung tam ra
                        #   thu muc ra / de len anh goc. Dua ra CA KHI hong /
                        #   dung giua chung: tam nao da xong thi khong mat. ]]
                        self._tien_do_tool = 0
                        ma = chay_mot(d, m, ra=d_ra, ghi_de=False, lam_lai=False)
                        n_ra = self.rt.dua_ket_qua_ra(a, vao, d_ra, ra, de_quy, ghi_de)
                        if lc is not None:
                            lc["xong"] += n_ra
                        self._tien_do_tool = 0
                        self.log_q.put(("dong", f"=== đã {'ghi đè lên ảnh gốc' if ghi_de else 'đưa ra thư mục ra'}"
                                                f" {n_ra}/{len(a)} ảnh ==="))
                        if ma != 0 or self._dung_tay:
                            break
            except Exception:                                # noqa: BLE001
                self.log_q.put(("loi", traceback.format_exc()))
                ma = ma or 1
            finally:
                if tam_goc is not None:
                    self.rt.don_thu_muc_tam(tam_goc)
            self.log_q.put(("ma", ma))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    # ------------------------------------------------------------ tự retouch ảnh mới
    #[[ TU RETOUCH ANH MOI (7/10 — user: "Tu dong Retouch cac anh moi khi duoc
    #   them vao trong Folder dang duoc Retouch. Co the quet Folder de them cac anh
    #   duoc them moi vao trong qua trinh chay Retouch. Can Option chon bat len.
    #   Khi duoc bat thi chi dung thong so cua muc chung de ap vao cac anh moi roi
    #   export").
    #
    #   Bat cong tac roi bam Chay retouch: chup lai danh sach anh CO SAN (anh moi
    #   = xuat hien SAU moc nay, ke ca trong luc luot dau dang chay) va bo muc ap
    #   cho anh moi = cac thanh THE CHUNG dang dat (khong muc rieng gioi tinh —
    #   anh moi chua ai xem, chua biet mat ai). Luot dau xong, cu 5 giay quet thu
    #   muc Vao (o luong chinh, chi liet ke file): anh moi chua co ket qua, kich
    #   thuoc + gio sua KHONG DOI qua hai lan quet (Lightroom / the nho da chep
    #   xong) -> mot luot chay rieng cho nhung anh do (thu muc tam, _chay_viec).
    #   Dung = thoi theo doi. Anh hong khi chay khong thu lai (tranh lap vo han). ]]
    QUET_GIAY = 5

    def _doi_tu_moi(self):
        try:
            self.rt.ghi_cau_hinh({"tu_moi": bool(self.v_tu_moi.get())})
        except OSError:
            pass
        if not self.v_tu_moi.get() and self._theo_doi is not None \
                and not (self.worker and self.worker.is_alive()):
            self._dung_theo_doi("đã tắt “Tự retouch ảnh mới”")

    def _chuan_bi_theo_doi(self, vao, ra, ghi_de):
        """Lúc bấm Chạy (công tắc đang bật): ảnh có sẵn + mức cho ảnh mới.
        None khi mức Chung đang 0 hết (đã nói ra) — lượt này vẫn chạy bình thường."""
        muc = self._loc_muc({k: v for k, v in self.muc_day_du().items()
                             if ":" not in str(k)})
        if self.rt.muc_trong(muc):
            messagebox.showinfo(
                "Tự retouch ảnh mới",
                "Các thanh ở thẻ Chung đang 0 hết — ảnh mới thêm vào sẽ không có "
                "gì để retouch, nên lần này KHÔNG theo dõi thư mục.\n\n"
                "Kéo các thanh ở thẻ Chung tới mức muốn dùng cho ảnh mới rồi bấm "
                "Chạy retouch lại.", parent=self)
            return None
        de_quy = bool(self.v_dequy.get())
        return {"vao": str(vao), "ra": str(ra), "ghi_de": bool(ghi_de),
                "de_quy": de_quy, "muc": muc, "so": 0, "cho": {},
                "biet": {str(p) for p, _x in self.rt.ds_anh(vao, None, de_quy)}}

    def _vao_theo_doi(self, td, ly_do: str = ""):
        """Bắt đầu / tiếp tục theo dõi (không có lượt nào đang chạy)."""
        self._theo_doi = td
        self._dung_tay = False
        self._dat_dang_chay(True)                # nút Dừng = thôi theo dõi
        self._append(f"=== THEO DÕI {td['vao']} — ảnh mới thêm vào sẽ tự retouch "
                     f"bằng mức chung: {self._mo_ta_muc(td['muc'])}"
                     + (f" ({ly_do})" if ly_do else "") + " ===")
        self._bao_theo_doi()
        self._hen_quet()

    def _bao_theo_doi(self):
        td = self._theo_doi
        if td is None:
            return
        self.app.status(f"Đang theo dõi “{Path(td['vao']).name}” — ảnh mới tự retouch "
                        f"bằng mức chung (đã làm {td['so']} ảnh mới). Bấm Dừng để "
                        "thôi.", gd.MAU["xong"])

    def _hen_quet(self):
        self._dung_hen_quet()
        try:
            self._hen_quet_ma = self.after(int(self.QUET_GIAY * 1000), self._quet_moi)
        except tk.TclError:
            self._hen_quet_ma = None

    def _dung_hen_quet(self):
        if self._hen_quet_ma is not None:
            try:
                self.after_cancel(self._hen_quet_ma)
            except tk.TclError:
                pass
        self._hen_quet_ma = None

    def _dung_theo_doi(self, ly_do: str = ""):
        td = self._theo_doi
        self._dung_hen_quet()
        self._theo_doi = None
        if td is not None:
            self._append("=== thôi theo dõi thư mục" + (f" ({ly_do})" if ly_do else "")
                         + f" — đã tự retouch {td['so']} ảnh mới ===")
            self.app.status(f"Đã thôi theo dõi — tự retouch {td['so']} ảnh mới",
                            gd.MAU["mo"])
        if not (self.worker and self.worker.is_alive()):
            self._dat_dang_chay(False)

    def _quet_moi(self):
        """Một lần quét thư mục Vào tìm ảnh mới (luồng chính, chỉ liệt kê file)."""
        self._hen_quet_ma = None
        td = self._theo_doi
        if td is None or self._dung_tay:
            return
        if not self.v_tu_moi.get():
            self._dung_theo_doi("đã tắt “Tự retouch ảnh mới”")
            return
        if self.worker and self.worker.is_alive():
            self._hen_quet()
            return
        try:
            ds = self.rt.ds_anh(Path(td["vao"]),
                                None if td["ghi_de"] else Path(td["ra"]), td["de_quy"])
        except OSError:
            ds = []
        san, co_moi = [], False
        for p, xong in ds:
            k = str(p)
            if k in td["biet"]:
                continue
            if xong:                       # đã có kết quả (người dùng tự chạy)
                td["biet"].add(k)
                continue
            try:
                st = os.stat(p)
            except OSError:
                continue
            dau = (st.st_size, st.st_mtime_ns)
            if st.st_size > 0 and td["cho"].get(k) == dau:
                san.append(k)
            else:
                co_moi = co_moi or k not in td["cho"]
                td["cho"][k] = dau
        if co_moi or san:
            self._dem()                    # dải ảnh hiện ngay tấm mới
        if not san:
            self._hen_quet()
            return
        for k in san:
            td["biet"].add(k)
            td["cho"].pop(k, None)
        self._chay_anh_moi(san)

    def _chay_anh_moi(self, ds: list):
        if self._bi_khoa():
            self._dung_theo_doi("hết hạn bản quyền")
            return
        td = self._theo_doi
        vao, ra = Path(td["vao"]), Path(td["ra"])
        try:
            tam_goc = self.rt.tao_thu_muc_tam(vao)
        except OSError as ex:
            self._append(f"! không tạo được thư mục tạm cho ảnh mới: {ex}")
            self._dung_theo_doi("lỗi thư mục tạm")
            return
        td["so"] += len(ds)
        ten = ", ".join(Path(p).name for p in ds[:3]) + (" …" if len(ds) > 3 else "")
        self._chay_viec(vao=vao, ra=ra, ghi_de=td["ghi_de"], lam_lai=True,
                        de_quy=td["de_quy"], viec=[(dict(td["muc"]), list(ds), False)],
                        tam_goc=tam_goc, muc_thang=dict(td["muc"]), xong_dau=0,
                        tieu_de=f"tự retouch {len(ds)} ảnh mới ({ten}) bằng mức chung")
        self._bao_theo_doi()

    def stop(self):
        #[[ Danh dau TRUOC khi giet: khong danh dau thi vong tu chay lai trong
        #   work() thay ma thoat 0xC0000005 (terminate cung cho ma do tren
        #   Windows) va lai chay tiep - nguoi dung bam Dung ma no khong dung.
        #]]
        self._dung_tay = True
        #[[ Dang theo doi ma khong co luot nao chay -> Dung = thoi theo doi ngay. ]]
        if self._theo_doi is not None and not (self.worker and self.worker.is_alive()):
            self._dung_theo_doi("đã bấm Dừng")
            return
        #[[ Me dang chay trong ENGINE THUONG TRU: xin dung (anh dang lam xong roi
        #   thoi), khong giet — giet la mat luon may xem truoc. 20 s khong dung
        #   duoc (ket trong mot buoc) thi tat han engine. ]]
        m = self._may_xem
        if m is not None and getattr(m, "dang_chay", False):
            self._append("… đang dừng — ảnh đang làm sẽ xong rồi mới dừng")
            m.dung_chay()
            self.btn_stop.configure(state="disabled")
            try:
                self.after(20000, self._ep_dung_engine)
            except tk.TclError:
                pass
            return
        p = self.proc
        if p and p.poll() is None:
            self._append("… đang dừng")
            try:
                p.terminate()
            except OSError as ex:
                self._append(f"! không dừng được: {ex}")
        self.btn_stop.configure(state="disabled")

    def _ep_dung_engine(self):
        """Bấm Dừng đã 20 s mà mẻ trong engine chưa dừng -> tắt hẳn tiến trình."""
        m = self._may_xem
        if self.worker is not None and self.worker.is_alive() and m is not None \
                and getattr(m, "dang_chay", False):
            self._append("! engine không dừng được trong 20 s — tắt hẳn tiến trình")
            m.dong()

    def _pump(self):
        try:
            while True:
                loai, gt = self.log_q.get_nowait()
                if loai == "keo":
                    self._keo_dang_hoi = False
                    self._dung_lai_thanh_keo(gt)
                    n = len(self.v_muc)
                    #[[ Noi "tool bao N tinh nang" khi tool CHUA he noi gi la
                    #   mot cau sai — no khang dinh dung cai bang du phong la
                    #   cua tool. Da suyt lam nguoi dung tin nham mot lan. ]]
                    if self.rt.da_hoi_that(gt):
                        self._append(f"… tool báo {n} tính năng: "
                                     + ", ".join(self.v_muc.keys()))
                    else:
                        self._append(f"… vẫn chưa hỏi được tool — đang dùng "
                                     f"bảng dự phòng {n} tính năng")
                elif loai == "kiem":
                    ok, mo = gt
                    #[[ THIEU GOI TAI DUOC -> MO CUA SO TAI, khong chi bao loi.
                    #
                    #   retouch.kiem_tra() gan nhan "TAI_DUOC:<ten goi>" khi
                    #   ban .exe thieu dung nhung thu tai ve duoc. Do la tinh
                    #   huong BINH THUONG cua ban nhe o lan chay dau, khong
                    #   phai hong — nen phai mo duong sua ngay tai day.
                    #]]
                    if not ok and str(mo).startswith("TAI_DUOC:"):
                        dong1 = str(mo).splitlines()[0]
                        can = [x for x in dong1[len("TAI_DUOC:"):].split(",") if x]
                        self.lbl_goc.configure(
                            text="Chưa có tài nguyên retouch — đang mở cửa sổ tải.",
                            foreground=gd.MAU["canh"])
                        if self._mo_cua_so_tai(can):
                            self.after(60, lambda: self._kiem(chay_thu=True))
                        continue
                    self.lbl_goc.configure(text=mo,
                                           foreground=gd.MAU["xong"] if ok else gd.MAU["loi"])
                    #[[ Sua duoc thi sua luon, dung bat nguoi dung di tim nut khac.
                    #]]
                    if not ok and self._hoi_chep():
                        self.after(60, lambda: self._kiem(chay_thu=True))
                elif loai == "lenh":
                    self._append(f"$ {gt}")
                elif loai == "ma":
                    self._xong(gt)
                else:
                    #[[ BAT DONG TIEN DO CUA TOOL — can cho che do ghi de.
                    #
                    #   saytool in "  10/2021  0.74s/anh  con lai ~24.8 phut"
                    #   moi 10 anh. Ghi de thi khong dem duoc bang file (anh ra
                    #   de len anh vao), nen day la nguon duy nhat biet no lam
                    #   toi dau. Xem _dem().
                    #]]
                    m = _RE_TIEN_DO.match(str(gt))
                    if m:
                        self._tien_do_tool = int(m.group(1))
                    bo = self.rt.buoc_bi_bo([gt])
                    if bo:
                        self._bi_bo.extend(bo)
                    self._append(gt)
                    self._so_dong_log = getattr(self, "_so_dong_log", 0) + 1
                    ds = getattr(self, "_log_cuoi", None)
                    if ds is not None:
                        ds.append(str(gt))
                        del ds[:-80]
        except queue.Empty:
            pass
        #[[ Dem file THUA hon moi 1.5 giay, khong phai moi vong bom log.
        #   _dem() goi iterdir() tren thu muc co the hang nghin anh; goi 3
        #   lan/giay tren o mang la tu lam cham chinh tien trinh dang do.
        #]]
        song = bool(self.worker and self.worker.is_alive())
        if song:
            now = time.monotonic()
            if now - getattr(self, "_lan_dem", 0.0) >= 1.5:
                self._lan_dem = now
                self._dem()
        self._dong_bo_dai()
        self.after(250 if song else 800, self._pump)

    def _xong(self, ma: int):
        self.proc = None
        try:
            import trang_thai as tt
            goc = self.app.folder()
            if goc and getattr(self, "_t0", None):
                tt.ghi_khau(tt.ten_buoi(goc), "retouch",
                            time.monotonic() - self._t0, ma_thoat=ma)
        except Exception:                                    # noqa: BLE001
            pass
        self._dat_dang_chay(False)
        #[[ Chay xong: mo lai may xem truoc o nen (da tat luc bam Chay de
        #   nhuong card do hoa) — keo thanh tiep la thay ngay. Engine thuong
        #   tru chet GIUA ME (sap 0xC0000005...) thi xoa dau "hong" de mo lai:
        #   dau do la cua lan chet nay, khong phai xem truoc hong that. ]]
        if getattr(self, "_engine_dung", False) and (
                self._may_xem is None or not self._may_xem.song()):
            self._xem_hong = ""
        try:
            self.after(800, self._san_may_xem)
        except tk.TclError:
            pass
        tong, xong = self._dem()
        #[[ TINH NANG BI BO GIUA CHUNG PHAI DUOC NOI LAI O CUOI.
        #
        #   Tu ban 0.9.5, buoc nao nap khong duoc (thieu file mo hinh chang han)
        #   thi saytool in mot dong "! BO QUA <ten>" roi CHAY TIEP. Anh van ra
        #   du, nhin qua van dep — chi la thieu han mot tinh nang. Dong do in ra
        #   ngay dau luot chay, tram dong log truoc khi xong, nen khong ai thay.
        #
        #   Bao o cuoi, va bao mau CANH chu khong phai mau XONG: mot buoi giao
        #   khach thieu buoc xoa khuyet diem thi khong the goi la "xong tot".
        #]]
        bo = getattr(self, "_bi_bo", [])
        if bo:
            self._append("")
            self._append("!!! Mấy tính năng sau KHÔNG chạy trong lượt này:")
            for ten, vi_sao in bo:
                self._append(f"    · {ten} — {vi_sao}")
            self._append("    Ảnh vẫn ra đủ nhưng THIẾU mấy tính năng đó. "
                         "Kiểm lại file mô hình rồi chạy lại với “Làm lại cả "
                         "ảnh đã có kết quả”.")
        if ma == 0 and bo:
            ten_bo = ", ".join(t for t, _ in bo)
            self._append(f"=== xong, {xong}/{tong} ảnh — NHƯNG thiếu: {ten_bo} ===")
            self.app.status(
                f"Retouch xong {xong}/{tong} ảnh nhưng THIẾU: {ten_bo} — "
                f"xem nhật ký", gd.MAU["canh"])
        elif ma == 0:
            self._append(f"=== xong, {xong}/{tong} ảnh có kết quả ===")
            self.app.status(f"Retouch xong: {xong}/{tong} ảnh → {self.v_ra.get()}",
                            gd.MAU["xong"])
        else:
            #[[ Dung tay cung ve day. Phan biet bang con lai, khong bang ma
            #   thoat: terminate() tren Windows tra ma khac tren Linux, con
            #   "con bao nhieu anh" thi luon dung.
            #]]
            self._append(f"=== dừng ở {xong}/{tong} ảnh (mã {ma}) ===")
            #[[ KHONG IN RA DONG NAO LA MOT MANH BANG CHUNG, KHONG PHAI "im lang".
            #
            #   duong_ong.chay() in ba dong ngay truoc khi bat dau (cau hinh
            #   may, so anh, danh sach buoc). Khong thay dong nao nghia la no
            #   chet TRUOC ca ba dong do — tuc chet luc NAP MO HINH, khong phai
            #   luc xu ly anh. Hai cho do bao hoan toan khac nhau, nen phai noi
            #   ro thay vi de nguoi dung doan. ]]
            if not getattr(self, "_so_dong_log", 0):
                self._append(
                    "   Tool KHÔNG in ra dòng nào — nó chết trước cả dòng "
                    "“cấu hình máy”, tức là chết lúc NẠP MÔ HÌNH chứ không "
                    "phải lúc xử lý ảnh. Thường là hết bộ nhớ card, hoặc một "
                    "file mô hình hỏng.")
            #[[ Dich ma thoat ra tieng nguoi NGAY TRONG NHAT KY.
            #   Ban truoc chi in "ma 3221225477" roi bao "chay lai la tiep tuc"
            #   — loi khuyen do sai han: chay lai voi 12 luong thi lai OOM o
            #   dung cho cu, va nguoi dung se lap lai mai.
            #]]
            vi = self.rt.giai_thich_ma(ma, "\n".join(getattr(self, "_log_cuoi", [])),
                                       getattr(self, "_luong_dang_chay", 0))
            for d in (vi.splitlines() if vi else []):
                self._append("   " + d)
            self._append("Chạy lại là tiếp tục từ chỗ dừng — tool tự bỏ qua "
                         "ảnh đã có kết quả.")
            self.app.status(f"Retouch dừng ở {xong}/{tong} ảnh", gd.MAU["canh"])
            #[[ Dung giua chung thi LY DO nam trong nhat ky — dua nguoi dung
            #   toi do, dung de ho nhin luoi anh ma doan. ]]
            self.v_xem.set("nhat_ky")
            self._doi_xem()
        #[[ TU RETOUCH ANH MOI: luot vua xong (luot dau hay luot anh moi, ke ca
        #   hong — anh hong da nam trong "biet", khong thu lai) -> quay lai theo
        #   doi, tru khi nguoi dung bam Dung / tat cong tac. ]]
        if self._theo_doi is not None:
            if self._dung_tay or not self.v_tu_moi.get():
                self._dung_theo_doi("đã bấm Dừng" if self._dung_tay
                                    else "đã tắt “Tự retouch ảnh mới”")
            else:
                self._dat_dang_chay(True)
                self._bao_theo_doi()
                self._hen_quet()

    def on_close(self):
        if self.proc and self.proc.poll() is None:
            if not messagebox.askokcancel(
                    "Đang chạy", "Retouch đang chạy. Đóng cửa sổ sẽ dừng nó.\n\n"
                    "Ảnh đã làm xong vẫn giữ nguyên, chạy lại là tiếp tục.",
                    parent=self):
                return
            self.stop()
        self.destroy()
