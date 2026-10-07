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
import sys
import threading
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
from retouch_chung import _RE_TIEN_DO, _cung_thu_muc, _so_muc, hoi_nut   # tên cũ, mã/kiểm cũ còn gọi man_retouch.X
from retouch_may import MayMixin
from retouch_muc import MucMixin

if TYPE_CHECKING:                                            # chỉ cho chú thích kiểu
    from autotone_gui import App


__all__ = ["RetouchWindow", "hoi_nut", "_RE_TIEN_DO", "_so_muc", "_cung_thu_muc"]


class RetouchWindow(MucMixin, MayMixin, Khung):
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
        #[[ MAY / SO LUONG / CHE DO LUON TU DONG (7/10 — user: "bo 2 muc May &
        #   cach chay va Tool retouch vi no tu dong ca roi"). Hai nhom do khong
        #   con tren bang dieu khien, nen KHONG doc lai gia tri cu trong
        #   retouch.json: may nao tung luu "cpu" / "luong": 2 se bi ket vinh vien
        #   o con so do ma khong con cho nao de doi. auto = card do hoa neu co
        #   (CUDA / MPS), 0 luong = saytool tu do theo loi + bo nho. ]]
        self.v_may = tk.StringVar(value="auto")
        self.v_luong = tk.IntVar(value=int(rt.LUONG_MAC_DINH))
        self.v_che_do = tk.StringVar(value=rt.CHE_DO_MAC_DINH)
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
        #[[ 7/10 (thiet ke lai): thanh tien do CHI HIEN KHI DANG CHAY. Truoc day
        #   no nam thuong truc — luc chua chay (0/41) la mot hop toi trong tron
        #   o goc, trong nhu o nhap bi hong. Chu "x/y anh da co ket qua" ben
        #   canh da noi du luc nghi. Xem _hien_pb. ]]
        self.pb = ttk.Progressbar(dau, mode="determinate", length=180)
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
        self.btn_goc = gd.NutTron(t, "Giữ xem gốc", kieu="phu", nen=nen, font=gd.CHU,
                                  icon="so_sanh")
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
                                  icon="mat", command=lambda: self.xem.vao_mat())
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

    def _hien_pb(self, co: bool):
        """Thanh tiến độ chỉ hiện khi đang chạy (xem _dung_trang)."""
        pb = getattr(self, "pb", None)
        if pb is None:
            return
        try:
            if co and not pb.winfo_manager():
                pb.pack(side="right", before=self.lbl_tt)
            elif not co and pb.winfo_manager():
                pb.pack_forget()
        except tk.TclError:
            pass

    def _cap_nhat_nut_chay(self):
        """“Chạy retouch · N ảnh” — N = số tấm ĐANG CHỌN ở dải ảnh (đúng những
        tấm start() sẽ chạy). Chưa có ảnh / chưa chọn thì chỉ “Chạy retouch”."""
        btn = getattr(self, "btn_run", None)
        luoi = getattr(self, "luoi", None)
        if btn is None:
            return
        try:
            n = len(luoi.ds_chon()) if luoi is not None and self._anh_dang else 0
        except Exception:                                    # noqa: BLE001
            n = 0
        chu = f"Chạy retouch  ·  {n} ảnh" if n else "Chạy retouch"
        if btn.cget("text") != chu:
            btn.configure(text=chu)

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
        #[[ 7/10 (thiet ke lai): bieu tuong VE (chay / dung) thay ky tu "▶ ■"
        #   — ky tu do moi phong mot co, lech dong voi chu. Nut Chay mang SO ANH
        #   se chay (_cap_nhat_nut_chay): bam la chay dung nhung tam dang chon,
        #   nhin nut la biet truoc. ]]
        self.btn_stop = gd.NutTron(thanh, "Dừng", kieu="phu", nen=nen, icon="dung",
                                   command=self.stop)
        self.btn_stop.configure(state="disabled")
        self.btn_run = gd.NutTron(thanh, "Chạy retouch", kieu="chinh", nen=nen,
                                  icon="chay", command=self.start)
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
            #[[ 7/10 (thiet ke lai): nut BIEU TUONG thu muc vuong canh o duong dan
            #   thay chu "Chọn…" — o duong dan rong them ~50 px (duong dan dai
            #   doc duoc hon), chu thich noi noi ro viec cua nut. ]]
            nut = gd.NutTron(o, "", kieu="phu", font=gd.CHU, icon="thu_muc",
                             command=lenh)
            nut.goi_y = gd.GoiY(nut, f"Chọn thư mục {nhan.lower()}…")
            nut.pack(side="right", padx=(6, 0))
            e = ttk.Entry(o, textvariable=bien)
            e.pack(side="left", fill="x", expand=True)
            return dong, lbl, e, nut

        g_tm = nhom("thu_muc", "Thư mục", True)
        g_keo = nhom("keo", "Mức áp dụng", True)
        #[[ HAI NHOM "May & cach chay" + "Tool retouch" KHONG HIEN (7/10 — user:
        #   "bo 2 muc nay di vi no tu dong ca roi"). Van DUNG trong mot khung
        #   KHONG pack: lbl_goc la noi _kiem() ghi tinh trang tool (dai bao tren
        #   luoi _dong_bo_dai doc chu cua no, nut Chay bao lai cau do khi tool
        #   chua dung duoc), _nhac_luong / _tom_tat_rt van goi cac widget cu.
        #   Tool chua dung duoc thi dai bao tren luoi co nut "Chọn thư mục
        #   tool…" — duong duy nhat nguoi dung can toi. ]]
        self._khung_an = ttk.Frame(ben)
        nhom_hien = nhom

        def nhom(ma, tieu_de, mo):                           # noqa: F811
            n = gd.Nhom(self._khung_an, tieu_de, mo=mo)
            n.pack(fill="x", anchor="w")
            self._nhom_rt[ma] = n
            return n.than

        g_chay = nhom("chay", "Máy & cách chạy", False)
        g_tool = nhom("tool", "Tool retouch", False)
        nhom = nhom_hien                                     # noqa: F841

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
                                    icon="dat_lai", command=self._reset_anh_0)
        self.btn_reset.pack(side="left")
        self.btn_reset.goi_y = gd.GoiY(
            self.btn_reset, "Đưa mọi thanh của ẢNH ĐANG XEM về 0 (tắt hết tính "
                            "năng). Muốn reset nhiều ảnh thì Reset rồi bấm Sync.")
        self.btn_sync_chon = gd.NutTron(o_duoi, "Sync ảnh đã chọn", kieu="phu", icon="dong_bo",
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

    # ------------------------------------------------------------ tiện ích
    def _pick(self, var: tk.StringVar):
        d = filedialog.askdirectory(title="Chọn thư mục",
                                    initialdir=var.get() or None, parent=self)
        if d:
            var.set(os.path.normpath(d))

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
        self._hien_pb(bool(self.worker and self.worker.is_alive()))
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

    def on_close(self):
        if self.proc and self.proc.poll() is None:
            if not messagebox.askokcancel(
                    "Đang chạy", "Retouch đang chạy. Đóng cửa sổ sẽ dừng nó.\n\n"
                    "Ảnh đã làm xong vẫn giữ nguyên, chạy lại là tiếp tục.",
                    parent=self):
                return
            self.stop()
        self.destroy()
