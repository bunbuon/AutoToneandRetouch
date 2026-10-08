#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
autotone_gui.py — Giao diện cho autotone.py

Chạy:  python autotone_gui.py       (hoặc bấm đúp AUTOTONE.bat)

Điểm đáng chú ý: bước ĐO ảnh chỉ phụ thuộc thư mục + cách đo sáng + kích thước
preview. Mọi tuỳ chọn còn lại (chế độ, tách cảnh, trần EV, WB, highlights...) chỉ
tác động ở bước TÍNH, nên đổi chúng thì bảng cập nhật ngay mà không phải quét lại
ảnh — chỉnh tới lui thoải mái rồi mới bấm ghi.
"""

from __future__ import annotations

import contextlib
import csv
import io
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import duong_dan as dd
import autotone as at
import duong_dan as dd
import duyet
import duyet_ui
import giao_dien as gd
import ban_quyen as bq
import khoa

#[[ 7/10 (giai doan 2 tai cau truc): tach autotone_gui.py (9.500 dong).
#   TEN_HIEN_THI / Khung / open_in_explorer sang giao_dien.py; hop thoai
#   sang hop_thoai.py; cua saytool (--say-*) sang cua_saytool.py; man
#   Retouch sang man_retouch.py (nap LUOI trong _lam_retouch — ban
#   --khong-retouch khong mang retouch / xem_truoc). Ten cu van import
#   duoc tu day cho ma / bai kiem cu. ]]
from giao_dien import Khung, open_in_explorer, TEN_HIEN_THI   # noqa: F401
from hop_thoai import (BuoiWindow, GuWindow, LogWindow,     # noqa: F401
                       TaiCapNhat, TaiTaiNguyenDialog, UndoDialog)
from cua_saytool import _cua_saytool, _tro_insightface   # noqa: F401


#[[ BAY KHAU — xuong song cua ung dung.
#
#   Ma khau o day PHAI trung voi khoa "ten" ma trang_thai.tinh() tra ve, vi cot
#   trai doc thang tu do. Lech mot chu la khau do khong bao gio hien trang thai,
#   ma khong bao loi gi ca — nen doi ten khau thi phai doi ca hai noi.
#]]
KHAU = [("tong_quan", "Tổng quan"),
        ("nap", "Nạp ảnh"),
        ("phan_tich", "Phân tích"),
        ("day", "Duyệt nhanh & Lightroom"),
        ("export", "Export"),
        ("retouch", "Retouch"),
        ("gu", "Vì sao tôi sửa"),
        ("hoc", "Gu đã học")]

#[[ KHONG CON COT TRAI (3/10 toi). Chieu 3/10 user bo Tong quan va khau
#   3/4/6/7 khoi cot trai ("gan nhu khong can toi"), toi 3/10 bo luon phan
#   con lai ("bo luon phan giao dien nay") roi dung lai theo Evoto: thanh cong
#   cu + luoi anh + bang dieu khien phai + cot mo-dun (xem _build_shell).
#   Cac trang van DUNG SAN (giu bien, giu trang_thai — ma khau giu nguyen,
#   trang_thai.tinh() van tra ve dung cac ma do): "day" mo tu nut ⋯ canh nut
#   Ghi, "retouch" la mo-dun o cot bieu tuong ben phai, "gu" do trang "day"
#   goi. Tong quan / Export / Gu da hoc khong con loi vao — dung san, khong
#   xoa, de mot ngay can lai thi chi viec them mot muc menu. ]]

MO_KHAU = {
    "tong_quan": "Cả buổi đang ở đâu — mỗi khâu một thẻ. Bấm vào thẻ là nhảy "
                 "thẳng vào khâu đó.",
    "nap": "Chọn thư mục buổi chụp và cho biết lấy thông số preset từ đâu.",
    "phan_tich": "Đo sáng từng ảnh, tính thông số, xem lại trong bảng — rồi bấm "
                 "“2 · Ghi và đẩy vào Lightroom”. Chưa bấm Ghi thì chưa đụng "
                 "tới file nào.",
    "day": "Dựng ảnh duyệt nhanh, hoàn tác, đọc lại thông số từ Lightroom, nhật "
           "ký plugin. Nút Ghi và đẩy nằm ở khâu Phân tích.",
    "export": "Chỉ chỗ Lightroom vừa xuất ảnh ra, để các khâu sau biết đường tìm.",
    "retouch": "Đưa thư mục vừa Export sang tool chỉnh chân dung. Chạy sau "
               "Export, không chạy song song. Kéo thanh là chỉnh ảnh đang xem "
               "(thấy ngay trên ảnh lớn); Sync để áp cho các ảnh đã chọn hoặc "
               "tất cả.",
    "gu": "Gắn lý do cho từng tấm anh đã sửa tay. Một phím một lý do — đây là "
          "dữ liệu để tool học gu của anh.",
    "hoc": "Những tham số tool đã học được từ các buổi trước, và đang dùng thay "
           "cho mặc định.",
}


# --- nhãn tiếng Việt <-> giá trị nội bộ ---
MODES = [("Đưa mặt về mức sáng chuẩn  (khuyên dùng)", "absolute"),
         ("Cân trong từng cảnh", "scene"),
         ("Cân cả buổi về một mức", "batch"),
         ("Trộn: cảnh + mức chuẩn", "hybrid")]
METERS = [("Khuôn mặt + điểm bắt nét  (khuyên dùng)", "face"),
          ("Chỉ điểm bắt nét", "focus"),
          ("Ưu tiên chủ thể — bỏ vùng cháy sáng", "subject"),
          ("Ưu tiên giữa khung", "center"),
          ("Trung bình toàn khung", "average"),
          ("Trung vị toàn khung", "median")]
#[[ Nhan ngan: o chon dai nhat quyet dinh be ngang ca bang dieu khien phai
#   (gd.vua_chu — khong cat chu). "— may do + nga hong" da noi trong dau ?
#   canh o "Can bang trang". ]]
WBS = [("Da trắng hồng  (khuyên dùng)", "skin"),
       ("Theo nhiệt độ máy đo được", "asshot"),
       ("Không đụng tới", "off"),
       ("Grey-world trên preview", "grey"),
       ("Grey-world, chỉ san trong cảnh", "scene")]
#[[ LOAI BUOI (3/10) — cuoi va su kien can muc sang mat KHAC nhau. Chon o day
#   chi dien so vao o "Bu sang ca buoi"; so do moi la thu duoc tinh. Xem chu
#   thich bu_sang_ca_buoi trong autotone.DEFAULTS. ]]
LOAI_BUOI = [("Cưới", "cuoi"),
             ("Sự kiện — sáng hơn", "su_kien")]

SOURCES = [("Sidecar .xmp  (phải bấm Ctrl+S trong Lightroom)", "sidecar"),
           ("Lightroom catalog qua plugin  (không cần Ctrl+S)", "catalog")]
#[[ NGUON MAC DINH = catalog (4/10 — user: "Mặc định sẽ chỉ dùng Lightroom
#   Catalog"). Truoc day mo app len la Sidecar .xmp: buoi nao cung bao do "chi
#   0/N anh co sidecar" cho toi khi vao menu doi tay. Sidecar VAN con trong
#   menu (may chua cai plugin), chi khong con la mac dinh. CLI (autotone.py
#   --nguon) giu nguyen mac dinh cu. ]]
NGUON_MAC_DINH = "catalog"

COLS = [("file", "File", 210, "w"),
        ("scene", "Cảnh", 50, "center"),
        ("time", "Giờ chụp", 76, "center"),
        ("dev", "ΔEV", 62, "e"),
        ("exp", "Exposure", 78, "e"),
        ("hl", "Highl.", 60, "e"),
        ("sh", "Shad.", 60, "e"),
        ("temp", "Temp", 62, "e"),
        ("curve", "Curve", 96, "center"),
        ("grade", "Grade", 60, "center"),
        ("clip", "Cháy %", 66, "e"),
        ("dark", "Tối %", 60, "e"),
        ("faces", "Mặt", 46, "center"),
        ("pick", "Loạt", 52, "center"),
        ("note", "Ghi chú", 210, "w")]


# Plugin dò thư mục 5 giây/lần, nên 90 giây là đã lỡ 18 nhịp — chắc chắn có gì
# đó không ổn chứ không phải chậm. Thư mục vài trăm ảnh áp mất vài chục giây.
LR_JOB_TIMEOUT = 90


def _curve_txt(r: dict) -> str:
    """Tóm tắt 4 núi parametric curve cho vừa một ô bảng.

    Hiện dạng "H-29 S+12": chỉ liệt kê núi nào thực sự đổi, ô trống nghĩa là
    lần chạy này không đụng tới curve."""
    parts = []
    for tag, key in (("H", "cv_hl"), ("L", "cv_lt"), ("D", "cv_dk"), ("S", "cv_sh")):
        v = r.get(key, 0)
        if v:
            parts.append(f"{tag}{v:+d}")
    return " ".join(parts)


def _pick_txt(r: dict) -> str:
    """Kết quả lọc cho một ô bảng, KÈM LÝ DO loại.

    Ghi rõ lý do vì hai bộ lọc khác nhau: "trùng khung" là bị loại do có ảnh
    khác cùng loạt đẹp hơn, "nhắm mắt" là bị loại do chính nó. Gộp chung thành
    "loại 1★" thì về sau không còn phân biệt được nhãn nào của bộ lọc nào.
    """
    cull = r.get("cull") or ""
    if cull == "nham-mat":
        return f"loại {r.get('rating', 1)}★ nhắm mắt"
    if cull == "loat":
        return f"loại {r.get('rating', 1)}★ trùng khung"
    if r.get("burst", -1) < 0:
        return ""
    if r.get("pick"):
        return "giữ"
    return ""


class App(ttk.Frame):
    """Cửa sổ chính, dáng Evoto (3/10 tối) — xem _build_shell().

    BỐ CỤC
        ┌──────────────────────────────────────────────────────────┐
        │ dải cảnh báo (mã nguồn cũ, lỗi im lặng)    (chỉ khi cần) │
        ├──────────────────────────────────────────────────────────┤
        │ AutoTone │ buổi ▾ ……… lần gửi │ 1 · Phân tích │ 2 · Ghi ⋯ │
        ├─────────────────────────────────────┬──────────────┬───┤
        │ [Lưới ảnh | Bảng số]  tổng kết       │ bảng điều    │ ≡ │
        │ dải báo của buổi        (khi cần)    │ khiển của    │ ☺ │
        │ lưới ảnh / bảng số / trang phụ       │ mô-đun       │   │
        ├─────────────────────────────────────┴──────────────┴───┤
        │ tiến độ · đang làm gì ……………………………………… hạn dùng          │
        └──────────────────────────────────────────────────────────┘

    MỘT KHUNG VIỆC MỘT LẦN
        Bảy khung đều được dựng sẵn lúc khởi động rồi giấu đi bằng grid_remove().
        Dựng sẵn vì mấy khung này giữ biến (v_target, tree, v_muc...) mà các
        phần khác của app đọc bất cứ lúc nào — dựng chậm thì phải đi rào từng
        chỗ đọc, nhiều cơ hội sót hơn nhiều so với việc dựng hết ngay.
        Ngoại lệ: khung Retouch và Vì sao tôi sửa dựng khi bấm tới, vì chúng
        cần đọc đĩa và không phải buổi nào cũng đụng tới.
    """

    def __init__(self, master: tk.Tk):
        super().__init__(master, padding=0)
        self.master = master
        self.grid(sticky="nsew")
        master.columnconfigure(0, weight=1)
        master.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        #[[ 0 dai canh bao · 1 thanh cong cu · 2 than · 3 thanh trang thai ]]
        self.rowconfigure(2, weight=1)

        self.items: list = []          # kết quả đo, dùng lại khi đổi tuỳ chọn
        self.measure_key = None        # (thư mục, đệ quy, meter, preview_px) của lần đo
        self.cfg: dict = dict(at.DEFAULTS)
        self.pairs: list = []
        self.missing: list = []
        self.export: dict = {}
        self.busy = False
        self.cancel_flag = False
        self.q: queue.Queue = queue.Queue()
        self.last_backup: Path | None = None

        self.khau_dang = "phan_tich"
        self.khung: dict = {}          # mã khâu -> Frame nội dung
        self._khung_lam: dict = {}     # mã khâu -> hàm dựng chậm

        self._canh_ma_cu()
        self._build_shell()

        #[[ Cac khau dung ngay (giu bien ma noi khac doc bat cu luc nao).
        #   3/10 toi — dung theo khung Evoto: thu muc buoi len THANH CONG CU,
        #   tuy chon vao BANG DIEU KHIEN PHAI, hai nut chinh len thanh cong cu,
        #   tien do + lan gui xuong THANH TRANG THAI, giua la luoi anh / bang. ]]
        self._build_tong_quan(self.khung["tong_quan"])
        self._build_folder(self.cc_trai)
        self._build_options(self.cuon_phai.trong)
        self._build_actions(self.cc_phai)
        self._build_ghi(self.cc_phai)
        self._build_table(self.khung["phan_tich"])
        self._build_lrbox(self.khung["day"])
        self._build_export(self.khung["export"])
        self._build_hoc(self.khung["hoc"])
        self._build_status()

        self._khung_lam["retouch"] = self._lam_retouch
        self._khung_lam["gu"] = self._lam_gu
        #[[ Bat dau tai ban tang toc GPU o nen (neu may co card NVIDIA va chua
        #   co) TRUOC khi vao trang nao — tu day Retouch khoa toi khi tai xong. ]]
        self._bat_tai_gpu_ngam()

        #[[ Mo app len la vao mo-dun Can tone: giua man hinh moi chon buoi chup
        #   (khau "Nap anh" cu nay la nut thu muc tren thanh cong cu). ]]
        self._chon_khau("phan_tich")
        self.after(80, self._pump)
        self.after(400, self._vong_lam_moi)
        self.after(1200, self._bao_plugin_cap_nhat)
        self._soi_khoa()
        self.after(3000, self._soi_xuat)
        self._set_busy(False)

    # ------------------------------------------------------------ khung vỏ
    def _build_shell(self):
        """Khung kiểu Evoto (3/10 tối — user: "tham khảo giao diện của Evoto
        để thiết kế lại toàn bộ giao diện").

            ┌ AutoTone │ [▭ buổi ▾] │ số ảnh …… [1 · Phân tích] [2 · Ghi & đẩy] ⋯ ┐
            ├──────────────────────────────────────┬──────────────┬───┤
            │ vùng giữa: lưới ảnh / bảng kết quả   │ bảng điều    │ ≡ │
            │ (hoặc khung Retouch, Duyệt nhanh…)   │ khiển phải   │ ☺ │
            ├──────────────────────────────────────┴──────────────┴───┤
            │ tiến độ · đang làm gì ……… lần gửi gần nhất · hạn dùng   │
            └──────────────────────────────────────────────────────────┘

        Cột trái bảy khâu bỏ hẳn: hai việc chính (Phân tích, Ghi & đẩy) lên
        thanh công cụ như nút Export của Evoto; Retouch là một mô-đun ở cột
        biểu tượng sát mép phải, như Portrait / Background của Evoto.
        """
        m = gd.MAU
        # ---- hàng 1: thanh công cụ
        cc = tk.Frame(self, background=m["toi"], padx=14, pady=8)
        cc.grid(row=1, column=0, sticky="ew")
        cc.columnconfigure(1, weight=1)
        self.thanh_cc = cc
        self.cc_trai = tk.Frame(cc, background=m["toi"])
        self.cc_trai.grid(row=0, column=0, sticky="w")
        self.cc_giua = tk.Frame(cc, background=m["toi"])
        self.cc_giua.grid(row=0, column=1, sticky="ew", padx=(16, 16))
        self.cc_phai = tk.Frame(cc, background=m["toi"])
        self.cc_phai.grid(row=0, column=2, sticky="e")
        #[[ Nut cua mo-dun Retouch (▶ Chay retouch, Xem truoc, ⋯) — cung o voi
        #   nut cua Can tone, doi cho theo mo-dun dang mo (_chon_khau). Thanh
        #   cong cu luon chi mang viec cua man hinh dang nhin, nhu Evoto. ]]
        self.cc_phai_rt = tk.Frame(cc, background=m["toi"])
        self.cc_phai_rt.grid(row=0, column=2, sticky="e")
        self.cc_phai_rt.grid_remove()
        tk.Frame(self, height=1, background=m["vien"]).grid(row=1, column=0,
                                                            sticky="sew")

        # ---- hàng 2: thân
        than = tk.Frame(self, background=m["toi"])
        than.grid(row=2, column=0, sticky="nsew")
        than.columnconfigure(0, weight=1)
        than.rowconfigure(0, weight=1)
        self.than = than

        # vùng giữa: dòng đầu trang + các trang
        self.giua = tk.Frame(than, background=m["toi"])
        self.giua.grid(row=0, column=0, sticky="nsew")
        self.giua.columnconfigure(0, weight=1)
        self.giua.rowconfigure(1, weight=1)
        self.dau_trang = tk.Frame(self.giua, background=m["toi"], padx=16, pady=10)
        self.dau_trang.grid(row=0, column=0, sticky="ew")
        #[[ Dong dau cua trang PHU (Duyet nhanh, Tong quan…): nut quay ve +
        #   ten trang + dau ? mo ta. Trang chinh (Can tone) dung dong dau rieng
        #   — xem _build_table(). ]]
        self.dau_phu = tk.Frame(self.dau_trang, background=m["toi"])
        self.nut_ve = gd.NutTron(self.dau_phu, "Kết quả", kieu="chu", icon="chevron_trai",
                                 command=lambda: self._chon_khau("phan_tich"),
                                 nen=m["toi"])
        self.nut_ve.pack(side="left", padx=(0, 10))
        self.lbl_khau = tk.Label(self.dau_phu, text="", background=m["toi"],
                                 foreground=m["chu"], font=gd.CHU_TIEU_DE)
        self.lbl_khau.pack(side="left")
        #[[ Dong mo ta khau (MO_KHAU) vao dau ? canh tieu de: doc mot lan la
        #   thuoc, sau do chi con chiem mot dong cua moi man hinh. ]]
        self.hoi_khau = gd.NutHoi(self.dau_phu, "", nen=m["toi"])
        self.hoi_khau.pack(side="left", padx=(8, 0))
        self.dau_chinh = tk.Frame(self.dau_trang, background=m["toi"])
        #[[ DAI BAO CUA BUOI — tinh trang quet (lbl_scan) + nut sua (btn_fix).
        #   Tung nam giua thanh cong cu: cau dai xuong 2-3 dong chu do, keo cao
        #   ca thanh. No la chuyen cua BUOI dang mo nen nam ngay tren luoi anh,
        #   nen theo muc (loi do / canh cam / on chi mot dong mo). Xem
        #   gd.DaiBao. Hang 1 cua vung giua; cac trang day xuong hang 2. ]]
        self.dai_quet = gd.DaiBao(self.giua, nen=m["toi"])
        self.dai_quet.grid(row=1, column=0, sticky="ew", padx=(16, 10), pady=(0, 10))
        self.giua.rowconfigure(1, weight=0)
        self.giua.rowconfigure(2, weight=1)

        self.hop = tk.Frame(self.giua, background=m["toi"])
        self.hop.grid(row=2, column=0, sticky="nsew", padx=(16, 10), pady=(0, 10))
        self.hop.columnconfigure(0, weight=1)
        self.hop.rowconfigure(0, weight=1)
        #[[ MOI TRANG NAM TRONG MOT VUNG CUON DUOC — grid khong tu cho cuon, no
        #   chi cat bot: nut bi day khoi mep duoi la khong cach nao voi toi (da
        #   xay ra that 3/9). Giu ca doi tuong Cuon: self.khung[ma] la khung
        #   BEN TRONG canvas, cau tra loi "co phai cuon khong" nam o canvas. ]]
        self.khung_ngoai: dict = {}
        self.khung_cuon: dict = {}
        for ma, _ten in KHAU:
            #[[ Trang cua MO-DUN (Can tone, Retouch) nen TOI nhu vung giua —
            #   chung tu lo phan cuon (luoi anh, bang, nhat ky). Trang phu nen
            #   bang dieu khien — thanh mot "the" sang hon tren nen toi, widget
            #   ttk ben trong (nen mac dinh) hoa vao the. ]]
            mo_dun = ma in ("phan_tich", "retouch")
            nen_tr = m["toi"] if mo_dun else m["nen"]
            k = ttk.Frame(self.hop, style=("Toi.TFrame" if mo_dun else "TFrame"))
            k.grid(row=0, column=0, sticky="nsew")
            k.columnconfigure(0, weight=1)
            k.rowconfigure(0, weight=1)
            k.grid_remove()
            cu = gd.Cuon(k, nen=nen_tr)
            cu.grid(row=0, column=0, sticky="nsew")
            self.khung_ngoai[ma] = k
            self.khung_cuon[ma] = cu
            self.khung[ma] = cu.trong
            if not mo_dun:
                cu.trong.configure(padding=(20, 16))
        #[[ Trang mo-dun tu lo phan cuon cua no (luoi anh / bang / nhat ky tu
        #   cuon), nen khung gian het chieu cao thay vi cao bang noi dung. ]]
        self.khung_cuon["phan_tich"].lap_day()
        self.khung_cuon["retouch"].lap_day()
        #[[ TRANG CHO RETOUCH (5/10 — user: "sau khi cai xong tu dong tai tai
        #   nguyen ngam. Tai va cai day du moi cho dung Retouch, tranh mat trai
        #   nghiem"). Nam CUNG O voi trang Retouch; hien thay no khi dang tai
        #   ban tang toc GPU — xem _bat_tai_gpu_ngam / _ve_khoa_rt. ]]
        self.khoa_rt = tk.Frame(self.hop, background=m["toi"])
        self.khoa_rt.grid(row=0, column=0, sticky="nsew")
        self.khoa_rt.grid_remove()

        # bảng điều khiển phải
        self.ben_phai = tk.Frame(than, background=m["nen"])
        self.ben_phai.grid(row=0, column=1, sticky="ns")
        self.ben_phai.rowconfigure(1, weight=1)
        self.ben_phai.columnconfigure(0, weight=1)
        dau_p = tk.Frame(self.ben_phai, background=m["nen"], padx=16, pady=12)
        dau_p.grid(row=0, column=0, sticky="ew")
        self.icon_md = tk.Canvas(dau_p, width=gd.don_vi(self) + 2,
                                 height=gd.don_vi(self) + 2,
                                 background=m["nen"], highlightthickness=0)
        self.icon_md.tu_cuon = False
        self.icon_md.pack(side="left", padx=(0, 8))
        self.lbl_md = tk.Label(dau_p, text="Cân tone", background=m["nen"],
                               foreground=m["chu"], font=gd.CHU_TIEU_DE)
        self.lbl_md.pack(side="left")
        self.hoi_md = gd.NutHoi(dau_p, MO_KHAU["phan_tich"])
        self.hoi_md.pack(side="left", padx=(8, 0))
        tk.Frame(self.ben_phai, height=1, background=m["vien"]).grid(
            row=0, column=0, sticky="sew")
        self.cuon_phai = gd.Cuon(self.ben_phai, nen=m["nen"])
        self.cuon_phai.theo_noi_dung()
        #[[ Le phai cho noi dung: khong co, dong tom tat cua nhom cham sat mep
        #   cot (anh chup 3/10: "…WB da trang hong" dinh vao vach). ]]
        self.cuon_phai.trong.configure(padding=(0, 0, 12, 0))
        self.cuon_phai.grid(row=1, column=0, sticky="nsew", padx=(16, 4), pady=(4, 8))
        #[[ Bang dieu khien cua mo-dun Retouch — cung cho, doi theo mo-dun.
        #   RetouchWindow dung ruot cua no (luc mo Retouch lan dau). ]]
        self.cuon_phai_rt = gd.Cuon(self.ben_phai, nen=m["nen"])
        self.cuon_phai_rt.theo_noi_dung()
        self.cuon_phai_rt.trong.configure(padding=(0, 0, 12, 0))
        self.cuon_phai_rt.grid(row=1, column=0, sticky="nsew", padx=(16, 4),
                               pady=(4, 8))
        self.cuon_phai_rt.grid_remove()
        #[[ THANH DAY CO DINH CUA RETOUCH (5/10, nhu Evoto — user: "nut Reset va
        #   Sync anh de dock o cuoi luon"): Reset / Sync nam NGOAI vung cuon, luon
        #   thay o day cot phai, khong phai cuon xuong duoi bang keo moi bam duoc.
        #   Chi hien o mo-dun Retouch (xem _chon_mo_dun). ]]
        self.chan_phai_rt = tk.Frame(self.ben_phai, background=m["nen"])
        tk.Frame(self.chan_phai_rt, height=1, background=m["vien"]).pack(fill="x")
        self.chan_phai_rt_trong = tk.Frame(self.chan_phai_rt, background=m["nen"],
                                           padx=16, pady=10)
        self.chan_phai_rt_trong.pack(fill="x")
        self.chan_phai_rt.grid(row=2, column=0, sticky="ew")
        self.chan_phai_rt.grid_remove()
        tk.Frame(than, width=1, background=m["vien"]).grid(row=0, column=1,
                                                           sticky="nsw")

        # cột mô-đun
        tk.Frame(than, width=1, background=m["vien"]).grid(row=0, column=2,
                                                           sticky="nsw")
        self.thanh_md = gd.ThanhMoDun(
            than, [("tone", "Cân tone · phân tích rồi đẩy vào Lightroom", "tone"),
                   ("retouch", "Retouch · chỉnh chân dung ảnh đã Export",
                    "retouch")],
            self._chon_mo_dun)
        self.thanh_md.grid(row=0, column=3, sticky="ns")

        # ---- hàng 3: thanh trạng thái
        ttb = tk.Frame(self, background=m["toi2"], padx=14, pady=6)
        ttb.grid(row=3, column=0, sticky="ew")
        ttb.columnconfigure(1, weight=1)
        self.thanh_tt = ttb
        self.ttb_trai = tk.Frame(ttb, background=m["toi2"])
        self.ttb_trai.grid(row=0, column=0, sticky="w")
        self.ttb_giua = tk.Frame(ttb, background=m["toi2"])
        self.ttb_giua.grid(row=0, column=1, sticky="ew", padx=(12, 12))
        self.ttb_phai = tk.Frame(ttb, background=m["toi2"])
        self.ttb_phai.grid(row=0, column=2, sticky="e")
        tk.Frame(self, height=1, background=m["vien"]).grid(row=3, column=0,
                                                            sticky="new")
        #[[ Han dung LUON hien, khong giau trong menu. Nguoi dung phai biet con
        #   bao lau TRUOC khi bat dau mot buoi 1400 anh, chu khong phai phat hien
        #   ra luc dang chay do. Nay o goc phai thanh trang thai (cot trai da bo).
        #]]
        self.lbl_han = tk.Label(self.ttb_phai, text="", anchor="e", justify="right",
                                background=m["toi2"], foreground=m["mo2"],
                                font=gd.CHU_NHO)
        self.lbl_han.pack(side="right", padx=(14, 0))

    #[[ Khau nao thuoc mo-dun nao. Moi khau khong ghi o day deu la trang PHU cua
    #   mo-dun Can tone (mo tu menu "⋯", co nut quay ve). ]]
    MO_DUN_CUA = {"phan_tich": "tone", "retouch": "retouch"}

    def _chon_mo_dun(self, md: str):
        """Bấm một biểu tượng ở cột mô-đun."""
        self._chon_khau("retouch" if md == "retouch" else "phan_tich")

    def _chon_khau(self, ma: str):
        #[[ "Nap anh" khong con la mot trang: chon thu muc la nut tren thanh
        #   cong cu, giua man hinh moi chon khi chua co buoi. Cho goi cu (va
        #   bai kiem cu) goi "nap" thi dua ve trang chinh. ]]
        if ma == "nap":
            ma = "phan_tich"
        if ma not in self.khung:
            return
        #[[ Retouch DANG KHOA (dang tai ban tang toc GPU): KHONG dung trang that
        #   — dung no la hoi saytool (--say-keo) va mo may xem truoc, ca hai nap
        #   torch: nap luc nay la nap ban CPU, tai xong lai phai mo lai. Hien
        #   trang cho thay vao, xong thi _bom_gpu goi lai _chon_khau("retouch"). ]]
        khoa_rt = ma == "retouch" and self._gpu_khoa()
        lam = None if khoa_rt else self._khung_lam.pop(ma, None)
        if lam:
            try:
                lam(self.khung[ma])
            except Exception:                                # noqa: BLE001
                traceback.print_exc()
                ttk.Label(self.khung[ma], style="Loi.TLabel", justify="left",
                          text="Không dựng được khung này:\n"
                               + traceback.format_exc()[-400:]).grid(sticky="w")
        #[[ Hien/an KHUNG NGOAI, khong phai self.khung[ma]: self.khung[ma] la khung
        #   BEN TRONG canvas, dat bang create_window nen .grid()/.grid_remove()
        #   len no khong lam gi — da tung lam ca vung giua trong tron. ]]
        for k, w in self.khung_ngoai.items():
            (w.grid() if k == ma and not khoa_rt else w.grid_remove())
        if khoa_rt:
            self.khoa_rt.grid()
            self._ve_khoa_rt()
        else:
            self.khoa_rt.grid_remove()
        self.khau_dang = ma
        ten = dict(KHAU)[ma]
        md = self.MO_DUN_CUA.get(ma, "tone")
        self._md_dang = md
        self.thanh_md.chon(md)
        self.lbl_khau.configure(text=ten)
        self.hoi_khau.goi_y.dat(MO_KHAU.get(ma, ""))
        #[[ Trang chinh hien dong dau rieng (Luoi | Bang, tong so anh); trang
        #   phu hien nut quay ve + ten trang. ]]
        if ma == "phan_tich":
            self.dau_phu.pack_forget()
            self.dau_chinh.pack(fill="x")
        else:
            self.dau_chinh.pack_forget()
            self.dau_phu.pack(fill="x")
            self.nut_ve.configure(text="Kết quả" if md == "tone" else "Cân tone")
        #[[ MOI MO-DUN MOT BO: bang dieu khien phai, nut tren thanh cong cu,
        #   dong dau trang. Can tone: tuy chon can sang + "1 · Phan tich / 2 ·
        #   Ghi" + [Luoi anh | Bang so]. Retouch: muc ap dung + thu muc + may
        #   + "▶ Chay retouch" — dau trang rieng nam trong khung RetouchWindow.
        #   Ban khong kem retouch (khong co _retouch_win) thi khong co bang. ]]
        rt_win = getattr(self, "_retouch_win", None)
        if md == "tone":
            self.cuon_phai_rt.grid_remove()
            self.chan_phai_rt.grid_remove()
            self.cuon_phai.grid()
            self.ben_phai.grid()
            self.cc_phai_rt.grid_remove()
            self.cc_phai.grid()
            if not self.lbl_job.winfo_manager():
                self.lbl_job.pack(side="right", fill="x", expand=True)
            self.dau_trang.grid()
        else:
            self.cuon_phai.grid_remove()
            self.cuon_phai_rt.grid()
            self.chan_phai_rt.grid()
            (self.ben_phai.grid if rt_win is not None and not khoa_rt
             else self.ben_phai.grid_remove)()
            self.cc_phai.grid_remove()
            (self.cc_phai_rt.grid_remove if khoa_rt else self.cc_phai_rt.grid)()
            self.lbl_job.pack_forget()
            self.dau_trang.grid_remove()
        self.hoi_md.goi_y.dat(MO_KHAU.get("retouch" if md == "retouch"
                                          else "phan_tich", ""))
        #[[ MAY XEM TRUOC CUA RETOUCH (sang 4/10): vao mo-dun thi mo SAN o nen
        #   (keo thanh la thay ngay, khong cho nap mo hinh); roi mo-dun thi tat —
        #   no giu mo hinh tren card do hoa, Lightroom dang can. ]]
        if rt_win is not None:
            try:
                if md == "retouch" and not khoa_rt:
                    rt_win.after(300, rt_win._san_may_xem)
                else:
                    rt_win._nghi_may_xem()
            except Exception:                                # noqa: BLE001
                traceback.print_exc()
        #[[ Dai bao cua buoi (quet thu muc, ban xuat Lightroom) la chuyen cua
        #   Can tone — Retouch lam tren anh da Export, khong can no. ]]
        self.dai_quet.hien(md == "tone")
        self._hien_tien_do()
        if rt_win is not None:
            try:
                rt_win._hien_tien_do_tt()
            except Exception:                                # noqa: BLE001
                pass
        self.lbl_md.configure(text="Cân tone" if md == "tone" else "Retouch")
        self.icon_md.delete("all")
        s = gd.don_vi(self) + 2
        gd.ve_bieu_tuong(self.icon_md, md, s / 2, s / 2, s * 0.8, gd.MAU["chu"])

    # ------------------------------------------------------------ tải GPU ngầm
    #[[ TU TAI BAN TANG TOC GPU O NEN (5/10 — user: "viec thieu tai nguyen lam
    #   anh huong toi trai nghiem. Flow sau khi cai dat xong se tu dong tai tai
    #   nguyen ngam. Sau khi tai va cai dat day du moi cho dung Retouch").
    #
    #   Ban cai DAY DU da mang torch CPU + mo hinh + mediapipe — thu duy nhat
    #   con thieu la torch CUDA (2,3 GB), va no CHI co ich tren may co card
    #   NVIDIA. Nen: may co card (nvidia-smi) ma chua co -> tai ngam ngay luc
    #   mo app, KHOA Retouch (trang cho co tien do) toi khi tai + giai nen xong
    #   roi tu mo — khong can khoi dong lai, vi tien trinh xem truoc / chay
    #   retouch la tien trinh MOI, nap_het("torch") luc khoi dong se lay ban
    #   CUDA. May khong card: khong tai gi, Retouch dung ngay bang CPU.
    #   Tai loi (mat mang...): noi ro, co "Thu lai" va "Dung tam bang CPU" —
    #   khong de nguoi dung ket han. ]]
    def _bao_plugin_cap_nhat(self):
        """Bản cài vừa chép plugin Lightroom mới đè lên bản cũ -> nhắc Reload.

        #[[ 6/10: plugin cu (4/9) nam o thu muc du lieu suot nhieu ban cai vi
        #   duong_dan.plugin() chi chep khi chua co. Nay no tu cap nhat file ma
        #   (duong_dan._cap_nhat_plugin) — nhung Lightroom chi doc file moi khi
        #   Reload / mo lai. Chua Reload thi ban xuat van thieu cot WhiteBalance /
        #   Contrast -> tool bo qua WB va ba thanh Tone, y het loi user bao. ]]
        """
        doi = list(getattr(dd, "PLUGIN_CAP_NHAT", []) or [])
        if not doi:
            return
        messagebox.showinfo(
            "Đã cập nhật plugin Lightroom",
            f"Bản cài này mang plugin AutoTone mới ({len(doi)} file đã cập nhật).\n\n"
            "Để Lightroom dùng bản mới: trong Lightroom vào File › Plug-in "
            "Manager… › chọn AutoTone › bấm Reload Plug-in (hoặc tắt hẳn rồi mở "
            "lại Lightroom).\n\n"
            "Chưa Reload thì Lightroom vẫn chạy plugin cũ: tool không nhận ra "
            "preset bỏ trống WB / Tone nên sẽ bỏ qua cân WB và Contrast / Whites / "
            "Blacks.", parent=self)

    def _gpu_khoa(self) -> bool:
        return (getattr(self, "_gpu_tt", "") in ("dang_tai", "loi")
                and not getattr(self, "_gpu_bo_qua", False))

    def _bat_tai_gpu_ngam(self):
        self._gpu_tt = ""
        if not getattr(sys, "frozen", False) or not sys.platform.startswith("win") \
                or os.environ.get("AUTOTONE_KHONG_TAI_GPU"):
            return
        try:
            import shutil as _sh
            import tai_nguyen as tn
            g = tn.GOI.get("torch")
            if g is None:
                return
            #[[ 6/10: ban cai KEM SAN torch CUDA (goi_kem) -> khong tai gi ca.
            #   Don goi torch tai ve cu o thu muc du lieu (thua — va co the dang
            #   HONG do lan "tai lai" xoa do dang luc DLL bi khoa). Luc nay chua
            #   tien trinh nao nap no (nap uu tien goi kem) nen xoa duoc. ]]
            if getattr(tn, "co_kem", None) and tn.co_kem(g):
                don = [tn.thu_muc_goi(g)] + list(tn.goc().glob(f"{g.ten}_*"))
                #[[ Mo hinh / mediapipe TAI VE tu ban cai cu: ban nay mang san
                #   trong goi (tai_nguyen.trong_goi) va nap() khong con dung
                #   chung — xoa cho khoi lan, khoi ton ~250 MB. ]]
                for t, gk in tn.GOI.items():
                    if getattr(tn, "trong_goi", None) and tn.trong_goi(t):
                        don += list(tn.goc().glob(f"{gk.ten}-*"))
                        don += list(tn.goc().glob(f"{gk.ten}_*"))
                for p in don:
                    if p.exists():
                        _sh.rmtree(p, ignore_errors=True)
                return
            if tn.da_co(g) or not _sh.which("nvidia-smi"):
                return
            #[[ Don thu muc giai nen TAM con sot (lan truoc dong app giua chung
            #   — luong tai la daemon, chet ngang khong kip don). ]]
            for p in tn.goc().glob(f"{g.ten}_*"):
                if p.is_dir() and p != tn.thu_muc_goi(g):
                    _sh.rmtree(p, ignore_errors=True)
        except Exception:                                    # noqa: BLE001
            return
        self._gpu_tn, self._gpu_g = tn, g
        self._gpu_q = queue.Queue()
        self._gpu_dung = False
        self._gpu_tien = ("tai", 0, 0)
        self._gpu_loi = ""
        self._gpu_tt = "dang_tai"
        threading.Thread(target=self._luong_tai_gpu, daemon=True).start()
        self.after(400, self._bom_gpu)

    def _luong_tai_gpu(self):
        tn, g, q = self._gpu_tn, self._gpu_g, self._gpu_q
        try:
            tn.tai(g, tien_do=lambda pha, da, tong: q.put(("tien", pha, da, tong)),
                   dung=lambda: self._gpu_dung)
            q.put(("xong",))
        except BaseException as ex:                          # noqa: BLE001
            q.put(("loi", f"{type(ex).__name__}: {str(ex)[:300]}"))

    def _bom_gpu(self):
        """Tiến độ tải GPU ngầm (luồng chính)."""
        q = getattr(self, "_gpu_q", None)
        if q is None:
            return
        try:
            while True:
                x = q.get_nowait()
                if x[0] == "tien":
                    self._gpu_tien = x[1:]
                elif x[0] == "xong":
                    self._gpu_tt = "xong"
                elif x[0] == "loi":
                    self._gpu_tt = "loi"
                    self._gpu_loi = x[1]
        except queue.Empty:
            pass
        if getattr(self, "khau_dang", "") == "retouch":
            if self._gpu_khoa():
                self._ve_khoa_rt()
            elif self.khoa_rt.winfo_manager():
                self._chon_khau("retouch")                   # tai xong: dung trang that
        if self._gpu_tt == "dang_tai":
            self.after(400, self._bom_gpu)
        elif self._gpu_tt == "xong":
            self.status("Đã tải xong bản tăng tốc GPU — Retouch chạy bằng card NVIDIA",
                        gd.MAU["xong"])

    def _ve_khoa_rt(self):
        """Trang chờ của Retouch: tiến độ tải bản GPU, hoặc lỗi + lối thoát."""
        m = gd.MAU
        if not hasattr(self, "_krt"):
            k = {}
            o = tk.Frame(self.khoa_rt, background=m["toi"])
            o.place(relx=0.5, rely=0.42, anchor="center")
            k["tieu_de"] = tk.Label(o, text="Đang chuẩn bị Retouch", font=gd.CHU_TIEU_DE,
                                    background=m["toi"], foreground=m["chu"])
            k["tieu_de"].pack(anchor="w")
            k["mo_ta"] = tk.Label(
                o, justify="left", wraplength=560, background=m["toi"],
                foreground=m["mo"], font=gd.CHU,
                text="Máy có card NVIDIA — app đang tải bản tăng tốc GPU (khoảng "
                     "2,3 GB, chỉ tải một lần) để kéo thanh và Chạy retouch nhanh "
                     "trên card. Retouch tự mở khi tải xong, không cần khởi động "
                     "lại. Trong lúc chờ vẫn dùng Cân tone bình thường.")
            k["mo_ta"].pack(anchor="w", pady=(8, 14))
            k["pb"] = ttk.Progressbar(o, length=560, mode="determinate", maximum=100)
            k["pb"].pack(anchor="w")
            k["tt"] = tk.Label(o, text="", background=m["toi"], foreground=m["chu"],
                               font=gd.CHU)
            k["tt"].pack(anchor="w", pady=(8, 0))
            k["nut"] = tk.Frame(o, background=m["toi"])
            k["thu_lai"] = gd.NutTron(k["nut"], "Thử lại", kieu="chinh", font=gd.CHU,
                                      command=self._khoa_rt_thu_lai)
            k["thu_lai"].pack(side="left")
            k["cpu"] = gd.NutTron(k["nut"], "Dùng tạm bằng CPU (chậm hơn)", kieu="phu",
                                  font=gd.CHU, command=self._khoa_rt_dung_cpu)
            k["cpu"].pack(side="left", padx=(8, 0))
            self._krt = k
        k = self._krt
        tt = getattr(self, "_gpu_tt", "")
        if tt == "loi":
            k["tieu_de"].configure(text="Chưa tải được bản tăng tốc GPU")
            k["tt"].configure(text=f"Lỗi: {self._gpu_loi}", foreground=m["loi"])
            if not k["nut"].winfo_manager():
                k["nut"].pack(anchor="w", pady=(14, 0))
            return
        k["tieu_de"].configure(text="Đang chuẩn bị Retouch")
        if k["nut"].winfo_manager():
            k["nut"].pack_forget()
        pha, da, tong = getattr(self, "_gpu_tien", ("tai", 0, 0))
        pt = (100.0 * da / tong) if tong else 0.0
        k["pb"].configure(value=pt)
        if pha == "giai-nen":
            chu = f"Đang giải nén… {pt:.0f}%"
        elif tong:
            chu = f"Đang tải {pt:.0f}%  ·  {da / 1e9:.2f} / {tong / 1e9:.2f} GB"
        else:
            chu = "Đang kết nối máy chủ tải…"
        k["tt"].configure(text=chu, foreground=m["chu"])

    def _khoa_rt_thu_lai(self):
        self._bat_tai_gpu_ngam()
        if self._gpu_tt == "dang_tai":
            self._ve_khoa_rt()
        else:                                                # đã có / không cần nữa
            self._chon_khau("retouch")

    def _khoa_rt_dung_cpu(self):
        """Tải lỗi mà người dùng vẫn muốn làm ngay: mở Retouch bằng torch CPU
        trong gói (chỉ phiên này — lần mở app sau tự thử tải lại)."""
        self._gpu_bo_qua = True
        self._chon_khau("retouch")

    def _bat_menu(self, menu: tk.Menu, nut) -> None:
        """Mở một menu ngay dưới nút đã bấm (nút ttk thường, khỏi Menubutton:
        theme clam không nhuộm TMenubutton nên nó trắng bóc giữa nền tối).

        Dưới nút không đủ chỗ trong cửa sổ app thì mở LÊN TRÊN — từng có nút
        nằm sát đáy cửa sổ, mở xuống là menu lòi ra ngoài."""
        x = nut.winfo_rootx()
        y = nut.winfo_rooty() + nut.winfo_height()
        try:
            menu.update_idletasks()
            cao = menu.winfo_reqheight()
            top = nut.winfo_toplevel()
            day = top.winfo_rooty() + top.winfo_height()
            if y + cao > day and nut.winfo_rooty() - cao >= top.winfo_rooty():
                y = nut.winfo_rooty() - cao
        except tk.TclError:
            pass
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _vong_lam_moi(self):
        """Mỗi 4 giây đọc lại trạng thái: cột trái, thẻ Tổng quan, dải cảnh báo.

        #[[ 3/10: VONG NAY TUNG KHONG CHAY. Dong hen lai `after(4000, ...)` nam
        #   lac o cuoi _hien_khoa() (lop phu ban quyen) chu khong o day — nen
        #   cot trai chi doc trang thai DUNG MOT LAN luc mo app. Chon buoi xong
        #   cot trai van ghi "CHUA CHON BUOI"; plugin chet giua chung thi khong
        #   noi gi. Tach rieng ham vong: _lam_moi_ray() con duoc goi thang (xuat
        #   xong, chon buoi) — de no tu hen lai thi moi lan goi thang lai de
        #   them mot vong song song. ]]
        """
        try:
            self._lam_moi_ray()
        finally:
            self.after(4000, self._vong_lam_moi)

    def _lam_moi_ray(self):
        """Đọc lại trạng thái buổi từ đĩa. Rẻ — chỉ đếm file và đọc mtime.

        Tên giữ như cũ (vòng 4 giây, xem _vong_lam_moi): cột trái bảy khâu đã
        bỏ, nay nó làm mới nút buổi trên thanh công cụ, thẻ Tổng quan và dải
        cảnh báo."""
        try:
            import trang_thai as tt
            f = self.folder()
            self._dat_nut_buoi()
            if f:
                self._lam_moi_tong_quan(tt.tinh(f))
            else:
                self._lam_moi_tong_quan([])
        except Exception:                                    # noqa: BLE001
            pass

    # ------------------------------------------------------------ hạn dùng
    def _soi_khoa(self):
        """Kiểm hạn mỗi phút, và khoá NGAY khi tới hạn giữa lúc đang chạy.

        VÌ SAO KHÔNG CHỈ KIỂM LÚC KHỞI ĐỘNG
            Máy trong studio mở app cả ngày. Chỉ kiểm lúc mở thì hết hạn từ sáng
            mà tới tối vẫn dùng bình thường, miễn đừng đóng cửa sổ — tức cái hạn
            gần như không có tác dụng.
        """
        #[[ BAN QUYEN DUNG TRUOC HAN DUNG THU.
        #
        #   Hai he thong cung ton tai: ban_quyen (key ban cho khach) va khoa
        #   (han dung thu 72 gio ghi cung trong ma nguon). May da kich hoat key
        #   thi khong con lien quan gi toi han dung thu nua — kiem ca hai roi
        #   lay cai nghiem hon la sai, vi key 1 nam se bi han 72 gio chan.
        #]]
        g = bq.kiem()
        if g["co_phep"]:
            con = bq.mo_ta_con_lai(g["con_lai"])
            gap = bool(g["con_lai"] and g["con_lai"].days < 7)
            #[[ NHAC TRUOC KHI HET AN HAN, khong doi den luc bi chan.
            #
            #   May offline lau qua 30 ngay se mat quyen chay. Bao truoc thi
            #   ho noi mang mot lan la xong; bao sau thi ho dang giua job va
            #   khong hieu vi sao app dung. ]]
            if g.get("nhac"):
                self.lbl_han.configure(text=f"{g['nhac']}   ·   máy {g['may']}",
                                       foreground=gd.MAU["canh"])
            else:
                self.lbl_han.configure(
                    text=f"Bản quyền {g['goi']} · còn {con}   ·   máy {g['may']}",
                    foreground=gd.MAU["canh"] if gap else gd.MAU["mo2"])
            self._go_lop_khoa()
            self.after(60_000, self._soi_khoa)
            return

        #[[ CHUA KICH HOAT KEY thi roi ve han dung thu cu — de nguoi ta thu
        #   truoc khi mua. Het ca hai thi moi chan. ]]
        k = khoa.kiem()
        if k["chay_duoc"]:
            if k.get("tat"):
                #[[ Khoa tat (khoa.BAT_KHOA = False) thi KHONG duoc hien dem
                #   nguoc. Han goc van nam trong ma nguon va da qua tu lau, nen
                #   ve nguyen cong thuc cu se in ra "Ban dung thu · con da het
                #   han" mau cam — bao dong ve mot thu khong con hieu luc.
                #   Chi con ma may, de con doc duoc khi can cap ma cho may khac.
                #]]
                self.lbl_han.configure(text=f"máy {k['may']}",
                                       foreground=gd.MAU["mo2"])
            else:
                con = khoa.mo_ta_con_lai(k["con_lai"])
                gap = bool(k["con_lai"] and k["con_lai"].total_seconds() < 12 * 3600)
                self.lbl_han.configure(
                    text=f"Bản dùng thử · còn {con}   ·   máy {k['may']}",
                    foreground=gd.MAU["canh"] if gap else gd.MAU["mo2"])
            self._go_lop_khoa()
        else:
            self._hien_khoa(k)
        self.after(60_000, self._soi_khoa)

    def _go_lop_khoa(self):
        cu = getattr(self, "_lop_khoa", None)
        if cu is not None:
            try:
                cu.destroy()
            except tk.TclError:
                pass
            self._lop_khoa = None

    def _khoa_chan(self) -> bool:
        """True = đang khoá, đã báo rồi. Gọi ở ĐẦU mọi việc nặng.

        Chặn hai lớp: lớp phủ che giao diện, và chốt này ngay đầu từng việc.
        Lớp phủ có thể bị né (một phím tắt, một nút tôi quên tắt); chốt này thì
        không — mọi đường vào việc thật đều đi qua đây.
        """
        if bq.kiem()["co_phep"] or khoa.kiem()["chay_duoc"]:
            return False
        self._hien_khoa(khoa.kiem())
        return True

    def _hien_khoa(self, k: dict):
        """Lớp phủ che toàn bộ khung việc, kèm ô nhập mã gia hạn."""
        cu = getattr(self, "_lop_khoa", None)
        if cu is not None and cu.winfo_exists():
            cu.lift()
            return
        m = gd.MAU
        #[[ LOP PHU CHE KHUNG VIEC, KHONG CHE CA CUA SO.
        #
        #   Chinh sach: het han thi khoa viec MOI, van cho xem va xuat viec cu.
        #   Lop phu cu che row=1 (khung viec) — dung y do. Nhung cac nut "Xuat
        #   CSV" va "Khoi phuc" nam TRONG khung do, nen che het la mau thuan
        #   voi chinh sach vua neu.
        #
        #   Nen lop phu them mot hang nut o duoi, de nguoi dung van lam duoc
        #   hai viec khong bi khoa ma khong phai tat app di mo lai.
        #]]
        lop = tk.Frame(self, background=m["toi"])
        lop.grid(row=1, column=0, rowspan=2, sticky="nsew")
        lop.lift()
        self._lop_khoa = lop
        hop = tk.Frame(lop, background=m["tam"], padx=34, pady=28,
                       highlightthickness=1, highlightbackground=m["loi"])
        hop.place(relx=0.5, rely=0.42, anchor="center")

        #[[ TIEU DE THEO DUNG TINH HUONG.
        #
        #   "Het han dung thu" la sai khi khach da mua key va key het han —
        #   ho khong dung thu, ho la khach hang. Bao sai tinh huong thi ho
        #   tuong app hong, hoac tuong minh bi tinh phi nham.
        #]]
        #[[ BA TINH HUONG KHAC NHAU, BA TIEU DE KHAC NHAU.
        #
        #       da mua, het han    -> "Ban quyen da het han"
        #       chua mua bao gio   -> "Chua kich hoat ban quyen"
        #       het han dung thu   -> "Het han dung thu"
        #
        #   Truoc day chi co hai nhanh, va `da_mua` do bang `het_han` co hay
        #   khong. May chua kich hoat bao gio thi khong co het_han, nen roi vao
        #   nhanh "Het han dung thu" — bao mot thu ho chua tung dung.
        #]]
        gp = bq.kiem()
        if gp["het_han"]:
            #[[ DA TUNG MUA: noi dung chuyen ho gap — giay phep het han. ]]
            tieu_de, ly_do = "Bản quyền đã hết hạn", gp["ly_do"]
        else:
            #[[ CHUA MUA BAO GIO. Ho vua het han dung thu, vua chua co ban
            #   quyen — ca hai deu dung, nhung cau huu ich la cai NOI HO PHAI
            #   LAM GI, chu khong phai cai da mat.
            #
            #   "Het han dung thu" la mot ngo cut: doc xong khong biet di dau.
            #   "Can kich hoat ban quyen" chi thang xuong o nhap ngay duoi.
            #]]
            tieu_de = "Cần kích hoạt bản quyền"
            ly_do = (k["ly_do"] + "\n\nNhập key bản quyền để dùng tiếp."
                     if k.get("ly_do") else gp["ly_do"])

        self.lbl_tieu_de = tk.Label(
            hop, text=tieu_de, background=m["tam"],
            foreground=m["loi"], font=("Segoe UI", 15, "bold"))
        self.lbl_tieu_de.pack(anchor="w")
        self.lbl_ly_do = tk.Label(
            hop, text=ly_do, background=m["tam"], foreground=m["chu"],
            font=gd.CHU, justify="left", wraplength=520)
        self.lbl_ly_do.pack(anchor="w", pady=(8, 16))

        #[[ NOI RO ANH CU VAN CON. Day la cau hoi dau tien cua bat ky ai gap
        #   man hinh khoa giua mot job: "the anh toi lam ca sang thi sao?"
        #   Khong tra loi truoc thi ho hoang, va cai hoang do dat hon tien key.
        #]]
        tk.Label(hop, background=m["tam"], foreground=m["xong"], font=gd.CHU,
                 justify="left", wraplength=520,
                 text="Ảnh đã xử lý vẫn còn nguyên trên đĩa. Chỉ việc MỚI bị "
                      "khoá — mở xem và xuất lại kết quả cũ vẫn bình thường."
                 ).pack(anchor="w", pady=(0, 16))

        tk.Label(hop, text="Mã máy của máy này:", background=m["tam"],
                 foreground=m["mo"], font=gd.CHU).pack(anchor="w")
        e_may = tk.Entry(hop, font=("Consolas", 14), width=16, justify="center",
                         relief="flat", background=m["noi"], foreground=m["chu"])
        e_may.insert(0, k["may"])
        e_may.configure(state="readonly")
        e_may.pack(anchor="w", pady=(4, 16))

        tk.Label(hop, text="Key bản quyền (hoặc mã gia hạn dùng thử):",
                 background=m["tam"], foreground=m["mo"],
                 font=gd.CHU).pack(anchor="w")
        hang = tk.Frame(hop, background=m["tam"])
        hang.pack(anchor="w", pady=(4, 0))
        self.v_ma = tk.StringVar()
        e = tk.Entry(hang, textvariable=self.v_ma, font=("Consolas", 13), width=26,
                     relief="flat", background=m["noi"], foreground=m["chu"],
                     insertbackground=m["chu"])
        e.pack(side="left", ipady=4)
        lbl = tk.Label(hop, background=m["tam"], font=gd.CHU, justify="left",
                       wraplength=520)

        def gui():
            #[[ THU KEY BAN QUYEN TRUOC, ma gia han dung thu sau.
            #
            #   Hai loai ma khac hinh dang (key 20 ky tu chia 4 nhom 5; ma gia
            #   han 20 ky tu chia 5 nhom 4) nhung deu la chu so viet hoa, nen
            #   khong the nhin ma doan. Thu ca hai va lay cai nao nhan — de
            #   nguoi dung khoi phai biet minh dang cam loai giay to nao.
            #]]
            go = self.v_ma.get()
            ok, nhan = bq.kich_hoat(go)
            if not ok and not bq.dang_key(go):
                #[[ Chi lui ve ma gia han khi chuoi do KHONG PHAI mot key hop
                #   le. Key dung ma kich hoat that bai (vi du giay phep hong)
                #   thi phai bao dung loi do, dung de khoa.nhap_ma() ghi de
                #   bang "Ma khong dung cho may nay" — sai huong hoan toan.
                #]]
                ok2, _moi, nhan2 = khoa.nhap_ma(go)
                if ok2 or not nhan:
                    ok, nhan = ok2, nhan2
            #[[ Doi CA TIEU DE theo ket qua vua roi.
            #
            #   Truoc day chi dong duoi doi, nen man hinh hien "Ban quyen da
            #   het han" o tren va "Key khong hop le" o duoi — hai cau noi hai
            #   chuyen khac nhau, nguoi doc khong biet tin cau nao.
            #]]
            if ok:
                self.lbl_tieu_de.configure(text="Đã kích hoạt",
                                           foreground=m["xong"])
                self.lbl_ly_do.configure(text="")
            else:
                self.lbl_tieu_de.configure(text="Chưa kích hoạt được",
                                           foreground=m["loi"])
                self.lbl_ly_do.configure(text="")
            lbl.configure(text=nhan, foreground=m["xong"] if ok else m["loi"])
            lbl.pack(anchor="w", pady=(10, 0))
            if ok:
                #[[ KHONG tu go lop phu o day. De _soi_khoa() lam — no la cho
                #   DUY NHAT quyet dinh khoa hay mo. Hai cho cung quyet mot viec
                #   thi khi chung lech nhau se khong ai biet ben nao dung.
                #]]
                self.after(300, self._soi_khoa)

        self.btn_gia_han = ttk.Button(hang, text="Kích hoạt", style="Chinh.TButton",
                                      command=gui)
        self.btn_gia_han.pack(side="left", padx=(8, 0))
        e.bind("<Return>", lambda _e: gui())
        e.focus_set()
        tk.Label(hop, background=m["tam"], foreground=m["mo2"],
                 font=gd.CHU_NHO, justify="left", wraplength=520,
                 text="Gửi mã máy ở trên cho SAY Media để lấy key. "
                      "Key gắn với đúng máy này và đếm hạn từ lúc kích hoạt."
                 ).pack(anchor="w", pady=(18, 0))

        #[[ Hai viec KHONG bi khoa — dat ngay tren lop phu de khoi phai tat app.
        #   Xem ghi chu o do_csv() va do_undo(). ]]
        hang_cu = tk.Frame(hop, background=m["tam"])
        hang_cu.pack(anchor="w", pady=(14, 0))
        ttk.Button(hang_cu, text="Xuất báo cáo CSV",
                   command=self.do_csv).pack(side="left")
        ttk.Button(hang_cu, text="Khôi phục ảnh gốc",
                   command=self.do_undo).pack(side="left", padx=(8, 0))

    def _nut_gu(self, trang_thai: str):
        """Bật/tắt nút thu gói duyệt, chịu được cả khi khung chưa dựng.

        Khung "Vì sao tôi sửa" dựng chậm — tới lúc bấm mới có. Nhưng _gu_chay()
        gọi tới nút này ở bốn chỗ, và một trong bốn chỗ là nhánh xử lý LỖI. Để
        nó ném AttributeError ngay giữa lúc đang báo lỗi là biến một lỗi đọc
        được thành một vệt stack không ai hiểu.
        """
        b = getattr(self, "btn_gu", None)
        if b is not None:
            try:
                b.configure(state=trang_thai)
            except tk.TclError:                  # khung đã bị huỷ
                pass

    def _lam_retouch(self, cha):
        cha.rowconfigure(0, weight=1)
        #[[ BAN --khong-retouch KHONG MANG retouch.py THEO.
        #
        #   De khung Retouch dung len roi bao "chua san sang" thi no trong y
        #   het mot tinh nang co that ma bam vao khong bao gio chay — nguoi
        #   dung se di tim ToolCloneEvoto, di doi duong dan, mat ca buoi.
        #
        #   Bat ImportError o day va noi thang: phan nay da TACH KHOI BAN NAY.
        #   Khac han "chua cai duoc". ]]
        try:
            import retouch                                   # noqa: F401
        except Exception:                                    # noqa: BLE001
            self._retouch_win = None
            self._khung_khong_retouch(cha)
            return
        #[[ Bo cuc Evoto (toi 3/10): tuy chon vao BANG DIEU KHIEN PHAI, nut
        #   Chay len THANH CONG CU — RetouchWindow chi giu vung giua (luoi anh
        #   da Export / nhat ky). ]]
        from man_retouch import RetouchWindow
        self._retouch_win = RetouchWindow(self, cha, ben=self.cuon_phai_rt.trong,
                                          thanh=self.cc_phai_rt,
                                          chan=self.chan_phai_rt_trong)
        self._retouch_win.grid(row=0, column=0, sticky="nsew")

    def _khung_khong_retouch(self, cha):
        """Bản không kèm retouch — nói rõ, và chỉ đúng chỗ tiếp theo."""
        the = gd.The(cha, "Phần Retouch tách khỏi bản này",
                     "Bản này dừng ở: nạp ảnh → phân tích → ghi và đẩy vào "
                     "Lightroom. Duyệt nhanh nằm trong nút “⋯” cạnh nút Ghi.", "cho")
        the.grid(row=0, column=0, sticky="ew")
        ttk.Label(cha, style="Mo2.TLabel", wraplength=760, justify="left",
                  text="Tool retouch (ToolCloneEvoto) đang được tối ưu tốc độ "
                       "nên tạm để ngoài. Ảnh sau khi Export cứ chạy tay bằng "
                       "tool đó như thường; các khâu còn lại không phụ thuộc "
                       "vào nó.\n\nMuốn có lại: đóng gói lại trên máy có "
                       "ToolCloneEvoto, bỏ tham số --khong-retouch."
                  ).grid(row=1, column=0, sticky="w", pady=(14, 0))

    def _lam_gu(self, cha):
        cha.rowconfigure(2, weight=1)
        self.the_goi = gd.The(cha, "Chưa thu gói duyệt", "", "")
        self.the_goi.grid(row=0, column=0, sticky="ew")

        bar = ttk.Frame(cha)
        bar.grid(row=1, column=0, sticky="w", pady=(14, 14))
        self.btn_gu = ttk.Button(bar, text="Thu gói duyệt", style="Chinh.TButton",
                                 command=self.do_gu)
        self.btn_gu.pack(side="left", padx=(0, 6))
        ttk.Button(bar, text="Mở thư mục gói duyệt", style="Pha.TButton",
                   command=lambda: open_in_explorer(
                       dd.goc_du_lieu() / "gu")).pack(side="left")

        self.hop_gu = ttk.Frame(cha)
        self.hop_gu.grid(row=2, column=0, sticky="nsew")
        self.hop_gu.columnconfigure(0, weight=1)
        self.hop_gu.rowconfigure(0, weight=1)
        self._lam_moi_goi()

    def _lam_moi_goi(self):
        f = self.folder()
        if not f or not hasattr(self, "the_goi"):
            return
        gu = dd.goc_du_lieu() / "gu" / f.name / "gu.csv"
        if not gu.is_file():
            self.the_goi.dat("Chưa thu gói duyệt",
                             "Bấm “Thu gói duyệt” — tool sẽ so thông số hiện tại "
                             "trong Lightroom với những gì nó đã ghi.", "")
            return
        tong = gan = 0
        try:
            with io.open(gu, encoding="utf-8-sig", newline="") as fh:
                for r in csv.DictReader(fh):
                    tong += 1
                    if (r.get("ly_do") or "").strip():
                        gan += 1
        except OSError:
            return
        self.the_goi.dat(f"{gan}/{tong} ảnh đã gắn lý do", str(gu),
                         "xong" if tong and gan >= tong else "cho")

    #[[ BAO KHI MA NGUON TREN DIA DA MOI HON TIEN TRINH DANG CHAY.
    #
    #   Python nap file luc khoi dong. Ghi de file tren dia KHONG doi duoc tien
    #   trinh dang chay — giao dien van chay bang ban cu cho toi khi dong va mo
    #   lai. Y het benh cua plugin Lightroom, chi la o phia tool.
    #
    #   Trieu chung rat de hieu nham: bam nut, thay dung hop thoai cu, ket luan
    #   "ban vua sua khong an". Da xay ra that ngay 2/9 — nguoi dung bam "Vi sao
    #   toi sua" va nhan lai cua so cu, trong khi file tren dia da dung.
    #
    #   Trong du an nay ma nguon duoc thay lien tuc trong luc app dang mo, nen
    #   cai bay nay se con lap lai. Mot dai bang do noi thang la du.
    #]]
    MA_THEO_DOI = ("autotone_gui.py", "autotone.py", "thu_gu.py", "retouch.py",
                   "kiem_gu.py", "learn_corrections.py", "trang_thai.py")

    def _moc_ma(self) -> dict:
        d = Path(__file__).resolve().parent
        out = {}
        for n in self.MA_THEO_DOI:
            try:
                out[n] = (d / n).stat().st_mtime
            except OSError:
                pass
        return out

    def _canh_ma_cu(self):
        self._moc_luc_mo = self._moc_ma()
        #[[ Bang canh bao o HANG 0, tren cung.
        #
        #   Ban truoc dat no o hang 99 (duoi cung) vi luc do hang 0..5 da co chu
        #   va chen vao dau thi phai danh so lai het. Bo cuc moi chi con ba hang
        #   (bang canh / than / trang thai) nen dua duoc len dung cho no phai o:
        #   mot lòi canh bao "app dang chay ban cu" ma nam duoi cung, sau ca bang
        #   anh, thi doc duoc no la da muon roi.
        #]]
        #[[ 3/10: HANG 0 la mot DAI chua HAI bang canh bao, chu khong chi bang
        #   "ma nguon da doi". Bang thu hai la hai loi IM LANG ngay 7/9 (plugin
        #   chet, ban xuat cu hon lan ghi) — truoc chi hien tren man Tong quan,
        #   ma Tong quan da roi khoi cot trai (user: "gan nhu khong can toi").
        #   Bo no o do la giau dung thu man hinh do sinh ra de noi. Dat len dai
        #   tren cung thi khau nao cung thay. ]]
        self.dai_canh = tk.Frame(self, background=gd.MAU["bang_canh_nen"])
        self.dai_canh.grid(row=0, column=0, sticky="ew")
        self.dai_canh.grid_remove()
        kieu = dict(anchor="w", padx=14, pady=7, justify="left", wraplength=1000,
                    background=gd.MAU["bang_canh_nen"],
                    foreground=gd.MAU["bang_canh_chu"], font=gd.CHU)
        self.lbl_moi = tk.Label(self.dai_canh, **kieu)
        self.lbl_im_lang = tk.Label(self.dai_canh, **kieu)
        self.after(15000, self._soi_ma)

    def _hien_dai_canh(self):
        """Dải cảnh báo trên cùng: hiện những bảng đang có chữ, theo thứ tự cố
        định; không bảng nào có chữ thì giấu cả dải."""
        co = False
        for lbl in (self.lbl_moi, self.lbl_im_lang):
            lbl.pack_forget()
        for lbl in (self.lbl_moi, self.lbl_im_lang):
            if lbl.cget("text"):
                lbl.pack(fill="x")
                co = True
        (self.dai_canh.grid if co else self.dai_canh.grid_remove)()

    def _soi_ma(self):
        moi = [n for n, t in self._moc_ma().items()
               if t > self._moc_luc_mo.get(n, 0) + 1]
        if moi:
            self.lbl_moi.configure(
                text="⚠  Mã nguồn trên đĩa đã đổi (" + ", ".join(moi) +
                     ") — cửa sổ này vẫn chạy bản cũ trong bộ nhớ. "
                     "Đóng và mở lại AutoTone để dùng bản mới.")
            self._hien_dai_canh()
        self.after(15000, self._soi_ma)

    # ------------------------------------------------------------------ UI
    # ============================================================ TỔNG QUAN
    def _build_tong_quan(self, cha):
        """Khâu 0 — cả buổi đang ở đâu, tám thẻ trên một màn hình.

        VÌ SAO CÓ MÀN HÌNH NÀY
            Ngày 7/9 hai lỗi lớn đều IM LẶNG: bản xuất catalog cũ hơn lần ghi
            (nên bước lọc bỏ nhầm 2 032/2 087 ảnh), và vòng lặp plugin chết từ
            11:04 (nên job 18:54 nằm im không ai nhận). Cả hai chỉ lộ ra khi đi
            đọc file trong thư mục jobs. Không có chỗ nào trong app nói ra.

            Đây là chỗ đó.

        KHÔNG TỰ TÍNH LẠI GÌ
            Trạng thái bảy khâu lấy nguyên từ trang_thai.tinh() — nó đã suy
            trạng thái từ file trên đĩa. Thêm một đường tính thứ hai là sớm
            muộn hai đường lệch nhau, và lúc lệch thì không biết tin cái nào.
        """
        m = gd.MAU
        dau = ttk.Frame(cha)
        dau.grid(row=0, column=0, sticky="ew")
        self.lbl_tq_buoi = ttk.Label(dau, text="Chưa chọn buổi chụp",
                                     font=gd.CHU_TO)
        self.lbl_tq_buoi.pack(anchor="w")
        self.lbl_tq_duong = ttk.Label(dau, style="Mo2.TLabel", text="")
        self.lbl_tq_duong.pack(anchor="w", pady=(2, 0))

        #[[ Bang canh bao dat NGAY DUOI tieu de, tren ca luoi the. Nhung loi im
        #   lang phai la thu dap vao mat dau tien, khong phai thu tim thay sau
        #   khi da doc het tam cai the. ]]
        self.khung_tq_canh = tk.Frame(cha, background="#241d10", padx=14,
                                      pady=10, highlightthickness=1,
                                      highlightbackground=m["canh"])
        self.lbl_tq_canh = tk.Label(self.khung_tq_canh, text="", anchor="w",
                                    justify="left", background="#241d10",
                                    foreground="#f0c274", font=gd.CHU,
                                    wraplength=980)
        self.lbl_tq_canh.pack(anchor="w")

        luoi = ttk.Frame(cha)
        luoi.grid(row=2, column=0, sticky="ew", pady=(16, 0))
        for c in range(4):
            luoi.columnconfigure(c, weight=1, uniform="the")
        self._the_tq = {}
        for i, (ma, ten) in enumerate(KHAU):
            if ma == "tong_quan":
                continue
            self._the_tq[ma] = self._mot_the_tq(luoi, (i - 1) // 4, (i - 1) % 4,
                                                ma, ten)
        #[[ The thu tam: Duyet nhanh. No khong phai mot khau trong trang_thai
        #   nen phai tu lay so; de chung o day vi nguoi dung nhin no nhu mot
        #   viec ngang hang voi bay khau kia. ]]
        self._the_tq["duyet"] = self._mot_the_tq(luoi, 1, 3, "day",
                                                 "Duyệt nhanh")

        cuoi = ttk.Frame(cha)
        cuoi.grid(row=3, column=0, sticky="w", pady=(20, 0))
        ttk.Button(cuoi, text="Bảng tóm tắt buổi…", style="Pha.TButton",
                   command=self.open_buoi).pack(side="left", padx=(0, 6))
        ttk.Button(cuoi, text="Nhật ký plugin", style="Pha.TButton",
                   command=self.show_plugin_log).pack(side="left")

    def _mot_the_tq(self, cha, r, c, ma_nhay, ten):
        """Một thẻ. Bấm bất kỳ đâu trên thẻ là nhảy vào khâu tương ứng."""
        m = gd.MAU
        h = tk.Frame(cha, background=m["tam"], padx=13, pady=11,
                     highlightthickness=1, highlightbackground=m["vien"])
        h.grid(row=r, column=c, sticky="nsew", padx=(0, 10), pady=(0, 10))
        l_ten = tk.Label(h, text=ten.upper(), anchor="w", background=m["tam"],
                         foreground=m["mo2"], font=("Segoe UI", 8, "bold"))
        l_ten.pack(fill="x")
        l_tt = tk.Label(h, text="—", anchor="w", background=m["tam"],
                        foreground=m["chu"], font=gd.CHU, wraplength=230,
                        justify="left")
        l_tt.pack(fill="x", pady=(4, 3))
        l_mo = tk.Label(h, text="", anchor="w", background=m["tam"],
                        foreground=m["mo"], font=gd.CHU_NHO, wraplength=230,
                        justify="left")
        l_mo.pack(fill="x")

        o = dict(khung=h, l_ten=l_ten, l_tt=l_tt, l_mo=l_mo)
        #[[ Bat chuot tren MOI widget con — cung bai hoc voi cot trai: click roi
        #   vao cai nam duoi con tro chu khong noi len Frame cha. Bo sot mot cai
        #   la co mot vung chet ma nguoi dung bam mai khong an. ]]
        for w in (h, l_ten, l_tt, l_mo):
            w.bind("<Button-1>", lambda _e, k=ma_nhay: self._chon_khau(k))
            w.bind("<Enter>", lambda _e, d=o: d["khung"].configure(
                background=m["noi"], highlightbackground=m["vien2"]) or
                [x.configure(background=m["noi"])
                 for x in (d["l_ten"], d["l_tt"], d["l_mo"])])
            w.bind("<Leave>", lambda _e, d=o: d["khung"].configure(
                background=m["tam"], highlightbackground=m["vien"]) or
                [x.configure(background=m["tam"])
                 for x in (d["l_ten"], d["l_tt"], d["l_mo"])])
        return o

    def _lam_moi_tong_quan(self, ds):
        """Vẽ lại tám thẻ. ds = trang_thai.tinh(), hoặc [] khi chưa chọn buổi."""
        if not hasattr(self, "_the_tq"):
            return
        m = gd.MAU
        f = self.folder()
        self.lbl_tq_buoi.configure(
            text=(f"Buổi {f.name}" if f else "Chưa chọn buổi chụp"))
        self.lbl_tq_duong.configure(text=str(f) if f else
                                    "Bấm nút buổi chụp trên thanh công cụ để chọn thư mục")

        for k in ds:
            o = self._the_tq.get(k["ten"])
            if not o:
                continue
            o["l_tt"].configure(
                text=k["mo_ta"].split(" — ")[0] or "—",
                foreground=m["xong"] if k["xong"]
                else (m["canh"] if k.get("viec") else m["chu"]))
            chi = []
            if k.get("khi"):
                chi.append(k["khi"])
            if k.get("giay"):
                chi.append(f"{k['giay'] / 60:.1f} phút")
            if not k["xong"] and k.get("viec"):
                chi.append("→ " + k["viec"])
            o["l_mo"].configure(text=" · ".join(chi))

        # ---- thẻ Duyệt nhanh: lấy thẳng từ tiến trình plugin ghi ra
        try:
            td = duyet.tien_do()
            o = self._the_tq["duyet"]
            if td:
                o["l_tt"].configure(text=duyet.mo_ta(td),
                                    foreground=m["xong"]
                                    if td.get("trang_thai") == "xong"
                                    else m["canh"])
                o["l_mo"].configure(text=str(td.get("thu_muc") or ""))
            else:
                o["l_tt"].configure(text="Chưa dựng ảnh duyệt",
                                    foreground=m["chu"])
                o["l_mo"].configure(text="→ ⋯ · Duyệt nhanh trước khi Export")
        except Exception:                                    # noqa: BLE001
            pass

        self._canh_bao_im_lang(f)

    def _canh_bao_im_lang(self, f):
        """Hai lỗi từng xảy ra mà KHÔNG báo gì — bắt chúng phải hiện ra ở đây.

        1. Vòng lặp plugin chết. Job nằm im ở đuôi .tsv, không ai nhận, app vẫn
           báo "đã ghi". Ngày 7/9: nhật ký dừng ở 11:04, job 18:54 còn nguyên.
        2. Bản xuất catalog cũ hơn lần tool ghi. Bước lọc "ảnh sửa tay" so nhầm
           và bỏ 2 032/2 087 ảnh trong im lặng.
        """
        canh = []
        try:
            cho = len(list(at.LR_JOB_DIR.glob("apply_*.tsv"))) \
                if at.LR_JOB_DIR.is_dir() else 0
            lau = at.plugin_song_khi_nao()
            if cho and (lau is None or lau > 300):
                khi = ("chưa có nhật ký nào" if lau is None
                       else f"nhật ký im {lau / 60:.0f} phút")
                canh.append(f"⚠  {cho} job đang chờ mà plugin không nhận "
                            f"({khi}). Mở Lightroom, Plug-in Manager → Reload.")
        except Exception:                                    # noqa: BLE001
            pass
        #[[ 8/10 (user: "phan thong bao nay can an di"): canh bao "ban xuat catalog
        #   cu hon lan tool ghi" KHONG len dai tren cung nua. Ngay sau moi lan ghi,
        #   ban xuat nao cung "cu hon lan ghi" — dai cam hien thuong truc, nguoi
        #   dung quen mat no. An toan van giu: at.plan() tu TAT buoc loc "anh sua
        #   tay" khi ban xuat cu (ban_xuat_cu_hon_lan_ghi), nen khong con cai benh
        #   bo nham 2032 anh cua 7/9. Ban xuat dang dung + nut "Nạp lại catalog" /
        #   "Xoá catalog cũ" nam o dai buoi chup tren luoi (_nut_catalog). ]]

        if canh:
            self.lbl_tq_canh.configure(text="\n".join(canh))
            self.khung_tq_canh.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        else:
            self.khung_tq_canh.grid_remove()
        #[[ Cung chu do len dai canh bao tren cung — Tong quan da roi khoi cot
        #   trai nen o tren chi con la cho phu. Xem _canh_ma_cu(). ]]
        chu = "\n".join(canh)
        if self.lbl_im_lang.cget("text") != chu:
            self.lbl_im_lang.configure(text=chu)
            self._hien_dai_canh()

    def _anh_logo(self, co: int):
        """Logo app (icon.ico) cỡ `co` px làm PhotoImage — None nếu không đọc được."""
        try:
            from PIL import Image, ImageTk
            p = dd.tai_nguyen("icon.ico")
            if not p.is_file():
                p = Path(__file__).resolve().parent / "icon.ico"
            if not p.is_file():
                return None
            im = Image.open(p)
            #  (KHONG viet sorted(a or [b]) — Cython 3 crash o EarlyReplaceBuiltinCalls)
            co_san = list(im.info.get("sizes") or [im.size])
            co_san.sort()
            im.size = next((k for k in co_san if k[0] >= co * 2), co_san[-1])
            im = im.convert("RGBA").resize((co, co), Image.LANCZOS)
            return ImageTk.PhotoImage(im, master=self)
        except Exception:                                    # noqa: BLE001
            return None

    def _build_folder(self, cha):
        """Buổi chụp trên thanh công cụ — thay cho khâu “Nạp ảnh” cũ.

        Bên trái: chữ AutoTone và NÚT BUỔI (tên thư mục đang mở, bấm là ra menu:
        chọn thư mục, gồm thư mục con, nguồn thông số preset, xoá dữ liệu cũ).
        Giữa thanh: dòng tình trạng quét (lbl_scan) và nút sửa đi kèm khi cần.
        Biến và tên widget giữ nguyên — scan_folder() và _nhan_catalog() viết
        vào lbl_scan / btn_fix y như trước.
        """
        m = gd.MAU
        #[[ 7/10 (thiet ke lai): LOGO cua app (icon.ico — chu S vang) dung truoc
        #   ten, nhu Evoto / Lightroom dat logo goc trai. Khong doc duoc anh (goi
        #   cu, may la) thi chi con chu — khong duoc lam hong thanh cong cu. ]]
        logo = self._anh_logo(round(gd.don_vi(self) * 1.45))
        if logo is not None:
            self._logo = logo
            tk.Label(cha, image=logo, background=m["toi"], borderwidth=0).pack(
                side="left", padx=(0, 8))
        tk.Label(cha, text=TEN_HIEN_THI, background=m["toi"], foreground=m["chu"],
                 font=gd.CHU_TIEU_DE).pack(side="left", padx=(0, 14))
        tk.Frame(cha, width=1, height=gd.don_vi(self) + 6,
                 background=m["vien2"]).pack(side="left", padx=(0, 12))

        self.v_folder = tk.StringVar()
        self.v_recursive = tk.BooleanVar(value=False)
        self.v_source = tk.StringVar(
            value=next(nhan for nhan, ma in SOURCES if ma == NGUON_MAC_DINH))

        self.menu_buoi = tk.Menu(self, tearoff=0)
        self.menu_buoi.add_command(label="Chọn thư mục buổi chụp…",
                                   command=self.pick_folder)
        self.menu_buoi.add_command(label="Quét lại thư mục", command=self.scan_folder)
        self.menu_buoi.add_separator()
        self.menu_buoi.add_checkbutton(label="Gồm cả thư mục con",
                                       variable=self.v_recursive,
                                       command=self.scan_folder)
        self.menu_buoi.add_separator()
        self.menu_buoi.add_command(label="Lấy thông số preset từ:", state="disabled")
        for nhan, _ma in SOURCES:
            self.menu_buoi.add_radiobutton(label="   " + nhan, value=nhan,
                                           variable=self.v_source,
                                           command=self.scan_folder)
        self.menu_buoi.add_separator()
        #[[ Xoa du lieu cu cua buoi nay. Import lai mot buoi roi xuat thong so,
        #   tool van nho lan chay truoc: thay catalog khac cai minh da ghi, ket
        #   luan "nguoi dung sua tay" va bo qua gan het buoi. Muc nay xoa moc
        #   goc + so ghi cu de lan chay sau coi buoi do la moi hoan toan. ]]
        self.menu_buoi.add_command(label="Xoá dữ liệu cũ của buổi này…",
                                   command=self.xoa_du_lieu_buoi)

        self.nut_buoi = gd.NutTron(cha, "Chọn buổi chụp", kieu="toi",
                                   icon="thu_muc", mui_ten=True, nen=m["toi"],
                                   command=lambda: self._bat_menu(self.menu_buoi,
                                                                  self.nut_buoi))
        self.nut_buoi.pack(side="left")
        self.v_folder.trace_add("write", lambda *_a: self._dat_nut_buoi())

        #[[ Dong tinh trang quet nam trong DAI BAO ngay tren luoi anh (xem
        #   _build_shell) chu khong con giua thanh cong cu. Moi cho goi cu van
        #   lbl_scan.configure(text=, foreground=) va btn_fix.pack(side="left")
        #   / pack_forget() — gd.DaiBao doi mau chu thanh muc cua ca dai. Chua
        #   chon buoi thi dai trong (an): giua luoi da noi "Chua chon buoi". ]]
        self.lbl_scan = self.dai_quet.nhan
        self.btn_fix = self.dai_quet.tao_nut("Cách tạo .xmp cho số còn lại",
                                             command=self.show_sidecar_help)
        #[[ 8/10: SAU KHI PHAN TICH, ban xuat catalog dung yen — hai nut nay la
        #   cach doi no (xem refresh_plan / _nut_catalog). ]]
        self.btn_nap_catalog = self.dai_quet.tao_nut_them(
            "Nạp lại catalog", command=self.do_nap_lai_catalog, icon="dong_bo")
        self.btn_xoa_catalog = self.dai_quet.tao_nut_them(
            "Xoá catalog cũ", command=self.do_xoa_catalog_cu)

    def _dat_nut_buoi(self):
        """Nút buổi trên thanh công cụ hiện TÊN buổi đang mở (thư mục), rê
        chuột thì hiện đủ đường dẫn."""
        nut = getattr(self, "nut_buoi", None)
        if nut is None:
            return
        f = self.folder()
        ten = f.name if f else ""
        if not ten:
            s = self.v_folder.get().strip().strip('"')
            ten = Path(s).name if s else ""
        nut.configure(text=ten or "Chọn buổi chụp")
        if not hasattr(nut, "goi_y"):
            nut.goi_y = gd.GoiY(nut, "")
        nut.goi_y.dat(str(f) if f else "Chọn thư mục ảnh RAW của buổi chụp")
        # chỉ hiện khi thực sự thiếu — xem scan_folder()

    def _build_options(self, cha):
        """Bảng điều khiển của mô-đun Cân tone — MỘT CỘT bên phải, dáng Evoto.

        LỊCH SỬ NGẮN
            Từng là một cột dọc dưới đầu trang (phải cuộn, 946 px nhét vào
            411 px), rồi ba cột tự co (_xep_cot), rồi ba cột nhóm thu gọn.
            3/10 tối — user: "tham khảo giao diện của Evoto". Evoto để tuỳ chọn
            ở MỘT cột bên phải, nhóm thu gọn, thanh trượt nhãn trên / thanh
            dưới, công tắc thay ô tick, viên chọn thay nút tròn. Làm đúng vậy:
            vùng giữa dành hết cho lưới ảnh, tuỳ chọn không còn tranh chiều dọc
            với kết quả.

        KHÔNG CẮT CHỮ
            Cột rộng theo NỘI DUNG (Cuon.theo_noi_dung): ô chọn dài nhất
            (gd.vua_chu) quyết định bề ngang, không đặt số px cứng nào —
            kiem_man_hinh.py đo cả chữ trong ô chọn lẫn nhãn.

        Tên biến và lệnh giữ nguyên hết — chỉ đổi chỗ ngồi và dáng.
        """
        # ---------------------------------------------------------- biến
        self.v_mode = tk.StringVar(value=MODES[0][0])
        self.v_meter = tk.StringVar(value=METERS[0][0])
        self.v_wb = tk.StringVar(value=WBS[0][0])
        #[[ Moc sang mat lay tu at.DEFAULTS (da gom gu.json neu co) — truoc
        #   4/10 ghi cung "-1.19" o day nen gu da hoc khong bao gio toi duoc
        #   giao dien. O nay da AN (xem duoi), bien van giu de tinh. ]]
        self.v_target = tk.StringVar(value=self._moc_dich(True))
        self.v_blend = tk.StringVar(value="0.50")
        self.v_gap = tk.StringVar(value="5")
        self.v_maxev = tk.StringVar(value="1.00")
        self.v_maxup = tk.StringVar(value="1.00")
        self.v_gain = tk.StringVar(value="1.00")
        self.v_hl = tk.BooleanVar(value=True)
        self.v_sh = tk.BooleanVar(value=True)
        self.v_grade = tk.BooleanVar(value=False)
        self.v_curve = tk.BooleanVar(value=True)
        self.v_scenesig = tk.BooleanVar(value=True)
        self.v_level = tk.BooleanVar(value=True)
        self.v_dong_bo_loat = tk.BooleanVar(
            value=bool(at.DEFAULTS.get("dong_bo_loat", True)))
        self.v_burst = tk.BooleanVar(value=False)
        self.v_blink = tk.BooleanVar(value=False)
        self.v_upright = tk.BooleanVar(value=False)
        self.v_lrpush = tk.BooleanVar(value=True)
        self.v_gap_on = tk.BooleanVar(value=True)
        self.v_gap_can_sig = tk.BooleanVar(value=True)
        self.v_che_do_sang = tk.StringVar(
            value=at.DEFAULTS.get("che_do_sang", "tron"))
        self.v_loai_buoi = tk.StringVar(value=LOAI_BUOI[0][0])
        self.v_bu_sang = tk.StringVar(
            value=f"{float(at.DEFAULTS.get('bu_sang_ca_buoi', 0.0)):.2f}")

        WRAP = 300      # chữ còn in ra (cảnh báo) thì xuống dòng, không bị cắt

        #[[ NHOM THU GON + DAU ? + THANH TRUOT — user 3/10: "chuyen phan chon
        #   option cua phan tich thu gon theo cac nhom; tinh nang co thong so
        #   thanh thanh truot; chu thich vao dau ? canh moi tinh nang, di chuot
        #   vao moi hien, cho gon giao dien". Nhom dong thi hien MOT dong tom
        #   tat gia tri dang chon — thu gon ma khong giau. Phan than chi bi
        #   pack_forget, bien van song.
        #
        #   Chu thich KHONG bi bo dong nao: moi dong chu phu cu chuyen nguyen
        #   van vao dau ? ngay canh tinh nang cua no (test_giao_dien_gon.py
        #   canh dieu nay). ]]
        self._nhom_tuy_chon: dict = {}

        def nhom(ma, tieu_de):
            n = gd.Nhom(cha, tieu_de, mo=False)
            n.pack(fill="x", anchor="w")
            self._nhom_tuy_chon[ma] = n
            return n.than

        def hoi(cha_, chu):
            return gd.NutHoi(cha_, chu)

        def ct(cha_, bien, chu, mo="", lui=0):
            """Một hàng công tắc: chữ (+ dấu ?) bên trái, công tắc bên phải —
            như "Face Mole ⚪" của Evoto. Bấm vào chữ cũng bật/tắt."""
            o = ttk.Frame(cha_)
            o.pack(fill="x", anchor="w", pady=2, padx=(lui, 0))
            cong = gd.CongTac(o, bien, command=self.refresh_plan)
            cong.pack(side="right", padx=(12, 0))
            lbl = ttk.Label(o, text=chu)
            lbl.pack(side="left", anchor="w")
            lbl.bind("<Button-1>", lambda _e: cong.bat_tat())
            if mo:
                hoi(o, mo).pack(side="left", padx=(6, 0))
            return o

        def hop(cha_, nhan, var, gia_tri, khi_doi, mo=""):
            """Một ô chọn: nhãn (+ dấu ?) ở trên, ô chọn rộng hết cột ở dưới."""
            k = ttk.Frame(cha_)
            k.pack(fill="x", pady=(4, 1))
            dong = ttk.Frame(k)
            dong.pack(fill="x")
            ttk.Label(dong, text=nhan).pack(side="left")
            if mo:
                hoi(dong, mo).pack(side="left", padx=(6, 0))
            cb = ttk.Combobox(k, textvariable=var, state="readonly",
                              values=gia_tri)
            gd.vua_chu(cb)      # rộng đúng chữ dài nhất -> cột rộng theo nó
            cb.pack(fill="x", pady=(4, 0))
            cb.bind("<<ComboboxSelected>>", lambda _e: khi_doi())
            return cb

        def so(cha_, nhan, var, lo, hi, buoc, mo="", phim=None, lui=0):
            """Một thông số: nhãn · ? · số ở trên, thanh trượt ở dưới (Evoto).

            lo..hi là khoảng của THANH; ô số vẫn gõ được số ngoài khoảng đó.
            Tính lại kế hoạch khi THẢ chuột / Enter / rời ô — không theo từng
            nhịp kéo (xem gd.ThanhTruot)."""
            tt = gd.ThanhTruot(cha_, var, lo, hi, buoc, khi_xong=self.refresh_plan,
                               phim=phim, nhan=nhan, mo=mo)
            tt.pack(fill="x", pady=(4, 1), padx=(lui, 0))
            return tt.lbl, tt

        #[[ THU TU NHOM = thu tu nguoi dung nghi khi mo mot buoi moi: buoi gi,
        #   anh sang the nao, can ra sao, roi moi toi gioi han, bao ve, canh,
        #   loc. ]]
        g_loai = nhom("loai_buoi", "Loại buổi")
        g_sang = nhom("sang", "Ánh sáng của buổi")
        g_tone = nhom("tone", "Cách cân tone")
        g_tran = nhom("tran", "Giới hạn chỉnh")
        g_ghim = nhom("ghim", "Ghìm & bảo vệ")
        g_canh = nhom("canh", "Gom cảnh & đồng bộ")
        g_loc = nhom("loc", "Lọc ảnh")

        # ------------------------------------------------ loại buổi
        #[[ LOAI BUOI + BU SANG (3/10) — cuoi va su kien can muc sang mat KHAC
        #   nhau. Chon loai chi dien so vao thanh "Bu sang ca buoi"; so do moi
        #   la thu duoc tinh. Bu sang cong SAU phanh chong chay — doi "Mat sang
        #   toi muc" khong thay duoc: tren G:\1005 doi moc thi 287/630 anh dung
        #   yen. Vien chon nhu "Male | Female" cua Evoto. ]]
        #[[ Vien chon dung MOT MINH mot hang, dau ? o mep phai — ten nhom
        #   ("Loai buoi") da noi no la gi, mot dong nhan "Buoi nay la" phia tren
        #   chi ton them mot hang. ]]
        dong_lb = ttk.Frame(g_loai)
        dong_lb.pack(fill="x", pady=(4, 2))
        hoi(dong_lb, "Cưới: không bù. Sự kiện: bù sáng "
                     f"{float(at.DEFAULTS.get('bu_sang_su_kien', 0.3)):+.2f} EV "
                     "cho cả buổi — chọn xong vẫn sửa được số ở thanh dưới."
            ).pack(side="right", padx=(8, 0))
        NGAN_LB = {"cuoi": "Cưới", "su_kien": "Sự kiện"}
        self.cb_loai_buoi = gd.PhanDoan(
            dong_lb, self.v_loai_buoi,
            [(nhan, NGAN_LB.get(ma, nhan)) for nhan, ma in LOAI_BUOI],
            command=self._doi_loai_buoi)
        self.cb_loai_buoi.pack(side="left", fill="x", expand=True)
        self.lbl_bu_sang, self.sp_bu_sang = so(
           g_loai, "Bù sáng cả buổi +", self.v_bu_sang, -1.0, 1.0, 0.05,
           "EV, cộng sau chống cháy. Cưới 0 · Sự kiện "
           f"{float(at.DEFAULTS.get('bu_sang_su_kien', 0.3)):+.2f}. "
           "Ảnh không có mặt giữ nguyên. "
           #[[ 4/10: o "Mat sang toi muc" da an — moc nam o day cho nguoi
           #   dung biet so 0 cua thanh nay nghia la mat sang toi dau. ]]
           f"Mốc sáng mặt: {float(at.DEFAULTS['face_target_ev']):+.2f} EV.")

        # ------------------------------------------------ ánh sáng của buổi
        #[[ ANH SANG CUA BUOI — nguoi dung chon, khong doan.
        #
        #   Khong co cach do nao noi chac duoc anh nay an anh sang ngay hay anh
        #   den, ma nguoi chup thi BIET. Hoi mot cau luc dau buoi re hon moi
        #   thuat toan va khong bao gio sai.
        #
        #   Ten la "anh sang ngay / anh den" CHU KHONG PHAI "ngoai troi / trong
        #   nha": buoi Day2 chup hoan toan ngoai troi — tu troi mo, xuong nha
        #   bat va mai che, toi sau khi toi den. Thu quyet dinh MAU la nguon
        #   sang chu khong phai co tuong hay khong.
        #
        #   Ba lua chon thanh MOT hang vien chon; ten day du + chu thich tung
        #   lua chon gom vao dau ? canh hang. ]]
        lua_sang: list = []

        def rd(ma, chu, mo):
            lua_sang.append((ma, chu, mo))

        rd("tron", "Trộn — tự tách theo mức sáng",
           f"Ngưỡng EV100 {at.DEFAULTS.get('ev_ngoai_troi')} · tính từ "
           "ISO + tốc + khẩu, không phải ISO không")
        rd("ngay", "Cả buổi ánh sáng ngày",
           "Kể cả ảnh chụp trong nhà bạt hay dưới mái che ban ngày")
        rd("den", "Cả buổi ánh đèn",
           "Hội trường, sân khấu, hoặc chụp sau khi trời tối")
        dong_s = ttk.Frame(g_sang)
        dong_s.pack(fill="x", pady=(4, 2))
        hoi(dong_s, "\n".join(f"{chu}: {mo}" for _m, chu, mo in lua_sang)
            ).pack(side="right", padx=(8, 0))
        NGAN_S = {"tron": "Trộn", "ngay": "Ánh sáng ngày", "den": "Ánh đèn"}
        self.chon_sang = gd.PhanDoan(dong_s, self.v_che_do_sang,
                                     [(ma, NGAN_S[ma]) for ma, _c, _m in lua_sang],
                                     command=self._doi_che_do_sang)
        self.chon_sang.pack(side="left", fill="x", expand=True)

        # ------------------------------------------------ cách cân tone
        hop(g_tone, "Chế độ", self.v_mode, [m[0] for m in MODES],
            self._on_mode_change,
            "Đưa mặt về mức sáng chuẩn: mọi ảnh có mặt đưa về cùng một mức sáng "
            f"da ({float(at.DEFAULTS['face_target_ev']):+.2f} EV) — khuyên dùng.\n"
            "Cân trong từng cảnh: theo trung vị độ "
            "sáng của chính cảnh đó.\nCân cả buổi về một mức: trung vị của cả "
            "buổi.\nTrộn: pha giữa trung vị cảnh và mức chuẩn (ô “Độ trộn”).")
        # đổi cách đo sáng thì phải quét lại ảnh
        hop(g_tone, "Đo sáng", self.v_meter, [m[0] for m in METERS],
            self._on_meter_change,
            "Đo độ sáng ở đâu trên ảnh. “Khuôn mặt + điểm bắt nét” đo da mặt "
            "của người được lấy nét — khuyên dùng. Đổi cách đo thì phải bấm "
            "“1 · Phân tích” để quét lại ảnh.")
        hop(g_tone, "Cân bằng trắng", self.v_wb, [w[0] for w in WBS],
            self.refresh_plan,
            "Da trắng hồng: kéo màu da về đích da trắng hồng (đích riêng cho ánh "
            "sáng ngày và ánh đèn), kèm WB người chụp đặt trên máy khi preset để "
            "trống WB.\nTheo nhiệt độ máy đo được: chỉ kéo về WB của máy.\n"
            "Grey-world: cân theo màu trung bình của preview.")
        #[[ Hai o nay chi co nghia voi mode absolute/hybrid — _on_mode_change()
        #   bat/tat chung, nen phai giu dung ten bien lbl_target/sp_target/
        #   lbl_blend/sp_blend. De ngay duoi o "Che do" vi chung phu thuoc no. ]]
        self.lbl_target, self.sp_target = so(
            g_tone, "Mặt sáng tới mức", self.v_target, -3.0, 0.0, 0.01,
            "Mức sáng ĐÍCH của da mặt (EV log2, càng âm càng tối). Mặc định "
            f"{float(at.DEFAULTS['face_target_ev']):+.2f}. Chỉ dùng ở chế độ "
            "“Đưa mặt về mức sáng chuẩn” và “Trộn”.", phim=0.05)
        #[[ AN O "MAT SANG TOI MUC" (4/10 — user: "Do da co tinh nang bu sang ca
        #   buoi nen an di phan Mat sang toi muc di. Co the set ... ve -1.00").
        #   Sang toi theo buoi chinh o "Bu sang ca buoi" (nhom Loai buoi) — hai
        #   thanh cung lam mot viec tren man hinh la thua mot. Moc nam o
        #   at.DEFAULTS["face_target_ev"] (-1.00). Chi pack_forget: bien, trang
        #   thai bat/tat theo che do (_on_mode_change) van song — muon hien lai
        #   chi can bo dong nay. ]]
        self.sp_target.pack_forget()
        self.lbl_blend, self.sp_blend = so(
            g_tone, "Độ trộn", self.v_blend, 0.0, 1.0, 0.05,
            "Chỉ ở chế độ “Trộn”. 0 = theo trung vị cảnh, 1 = theo mức sáng "
            "chuẩn.")

        # ------------------------------------------------ giới hạn chỉnh
        so(g_tran, "Dìm tối đa −", self.v_maxev, 0.1, 5.0, 0.05,
           "Trần cho chiều DÌM TỐI. Đo ra phải dìm 1.8 EV mà đặt 1.00 thì chỉ "
           "dìm 1.00. Chiều kéo sáng do ô dưới quyết định.")
        so(g_tran, "Kéo sáng tối đa +", self.v_maxup, 0.1, 5.0, 0.05,
           "Trần cho chiều KÉO SÁNG, để riêng vì hai chiều không đối xứng: dìm "
           "quá tay chỉ mất công, kéo sáng thì cứu được ảnh ngược sáng hay "
           "chụp trước màn LED. Phần chống cháy sáng vẫn gác.")
        so(g_tran, "Mức độ can thiệp", self.v_gain, 0.1, 1.5, 0.05,
           "Nhân vào mức chỉnh trước khi kẹp trần. 1.0 = đủ như đo được, "
           "0.7 = dè dặt, 1.2 = mạnh tay.")

        #[[ GHIM & BAO VE doi THONG SO cua tung anh (highlights, shadows, mau,
        #   curve) — chung deu tra loi cau "anh nay sang toi dau".
        #   GOM CANH / LOC ANH doi xem CO NHUNG ANH NAO va chung di voi nhau ra
        #   sao. Hai viec khac han, khi truy loi bao gio cung chi nghi toi mot
        #   trong hai. ]]
        ct(g_ghim, self.v_hl, "Tự kéo Highlights khi cháy sáng",
           "Ngăn làm cháy thêm — không gỡ được chỗ đã cháy sẵn")
        ct(g_ghim, self.v_sh, "Tự kéo Shadows khi bết tối",
           "Nâng Shadows khi vùng tối bết lại; chỉ cộng lên số của preset.")
        ct(g_ghim, self.v_grade, "Đẩy tone về da trắng hồng",
           "Kỷ yếu, concept: da trắng hồng cả ảnh ngoài trời.\n"
           "· Cân trắng dùng đích da trắng hồng cho MỌI ảnh (tắt thì ảnh ngoài "
           "trời kéo về da rám nắng).\n"
           "· Color Grading tính trên màu da DỰ ĐOÁN trong Lightroom (WB preset, "
           "Saturation / Vibrance / toning của preset): da còn vàng thì xoay về "
           "hồng, đã đúng thì không đụng; cộng vào bánh xe Midtone + Highlight "
           "của preset, không ghi đè.\n"
           "Tắt lại thì ảnh tool đã grade được trả về số của preset. Ảnh không "
           "thấy mặt thì không grade.")
        ct(g_ghim, self.v_curve, "Tự chỉnh Curve (parametric)",
           "Cộng bốn núi parametric curve (Highlights / Lights / Darks / "
           "Shadows) lên preset; point curve của preset giữ nguyên.")

        # ------------------------------------------- gom cảnh & đồng bộ
        #[[ HAI LUAT TACH CANH, MOI LUAT MOT CONG TAC.
        #   Do that tren hai buoi: luat thoi gian chi tao 13/131 ranh gioi o
        #   buoi 1308 va 2/5 o buoi 0306 — phan con lai la boi canh. Nhung
        #   8/13 cap se bi gop lai neu tat no lech nhau tu 0.5 EV tro len,
        #   trong do mot cap lech 4.55 EV. Nen MAC DINH VAN BAT. ]]
        ct(g_canh, self.v_gap_on, "Tách cảnh theo thời gian",
           "Hai tấm cách nhau lâu hơn số phút ở thanh dưới thì sang cảnh mới.")
        #[[ Thanh so phut de NGAY duoi cong tac cua chinh no, lui vao mot nac
        #   cho thay no thuoc cong tac tren. Thanh 1–60 phut; o so van go duoc
        #   toi 240. ]]
        lui = gd.don_vi(self)
        self.lbl_gap, self.sp_gap = so(
            g_canh, "Nghỉ quá (phút)", self.v_gap, 1.0, 60.0, 0.5,
            "Nghỉ giữa hai tấm quá số phút này thì coi là cảnh mới. Thanh "
            "kéo 1–60; cần hơn thì gõ thẳng vào ô số (tới 240).", lui=lui)
        #[[ Do that buoi 1308: trong 13 nhat cat theo gio, 6 nhat co khung hinh
        #   y nguyen — chinh la nhung doan check-in chup ~30 phut mot phong. ]]
        o_cs = ct(g_canh, self.v_gap_can_sig, "…nhưng chỉ khi bối cảnh cũng đổi",
                  "Nghỉ lâu mà vẫn đứng nguyên một phông thì không tính là "
                  "cảnh mới", lui=lui)
        self.cb_gap_can_sig = o_cs.winfo_children()[0]
        ct(g_canh, self.v_scenesig, "Tách cảnh theo bối cảnh khung hình",
           "So chữ ký bố cục của từng khung; đổi phông / đổi chỗ đứng thì "
           "sang cảnh mới dù chụp liền tay.")
        ct(g_canh, self.v_level, "Đồng bộ sáng + màu trong cùng bối cảnh",
           "Trong một cảnh, đưa mọi tấm về cùng độ sáng và màu SAU chỉnh — "
           "xem liền một dải ảnh không bị nhấp nháy.")
        #[[ 3/10 — user: "cung khung + cung thong so ma hai muc sang khac nhau
        #   phai giai quyet dut diem". Xem at.dong_bo_loat(). ]]
        ct(g_canh, self.v_dong_bo_loat, "Cùng khung + cùng thông số → cùng một mức",
           "Loạt chụp liền tay (cùng máy, cùng khẩu/tốc/ISO, cùng bố cục, "
           "trong 60 giây) nhận đúng MỘT mức sáng và màu.")

        #[[ CANH BAO KHI TAT CA HAI LUAT -> ca buoi la MOT canh. "Dong bo sang
        #   + mau" mac dinh BAT va no san phang moi anh ve trung vi cua canh —
        #   mot canh duy nhat nghia la san phang ca buoi ve mot moc. Do that
        #   buoi 1308: mot canh don le da co bien do 5.14 EV.
        #   Canh bao la chu PHAI THAY, khong vao dau ?. Nhom dong thi dong tom
        #   tat cung noi ra (xem _tom_tat_nhom). ]]
        self.lbl_canh_canh = ttk.Label(g_canh, style="Canh.TLabel", wraplength=WRAP,
                                       justify="left")
        self.lbl_canh_canh.pack(anchor="w", pady=(4, 0))
        for b in (self.v_gap_on, self.v_scenesig, self.v_level):
            b.trace_add("write", lambda *_a: self._soi_tach_canh())
        self._soi_tach_canh()

        # ---------------------------------------------------------- lọc ảnh
        #[[ HAI BO LOC RIENG BIET — dung gop lam mot. Loc trung khung chi so
        #   cac anh trong CUNG mot loat; no khong tra loi "co ai nham mat
        #   khong". Loc mat doc EAR trong ear.csv, nguong 0.12 hieu chuan tren
        #   93 nhan that cua buoi 1308. ]]
        ct(g_loc, self.v_burst, "Lọc ảnh trùng khung",
           "Chụp liên tiếp — giữ 2 tấm đẹp nhất mỗi pose, ảnh loại gắn 1 sao")
        o = ct(g_loc, self.v_blink, "Lọc ảnh mắt không dùng được",
               "1 người hoặc nhóm 2–4; ảnh tập thể đông người bỏ qua. "
               "Đo luôn khi phân tích, chậm thêm ~0.8s/ảnh")
        self.cb_blink = o.winfo_children()[0]
        ct(g_loc, self.v_upright, "Auto Transform cho ảnh backdrop / màn LED",
           "Ghi Upright = Auto cho ảnh nhiều đường thẳng (backdrop, màn LED) "
           "có người mà mặt không chiếm quá lớn.")

        #[[ Dong tom tat cua nhom dong — doi theo moi bien. Gom mot nhip
        #   after_idle: keo mot thanh truot ban hang chuc lan write, tinh lai
        #   bay dong tom tat moi lan la phi. ]]
        self._hen_tom_tat = None
        for b in (self.v_mode, self.v_meter, self.v_wb, self.v_target,
                  self.v_blend, self.v_che_do_sang, self.v_maxev, self.v_maxup,
                  self.v_gain, self.v_hl, self.v_sh, self.v_grade, self.v_curve,
                  self.v_loai_buoi, self.v_bu_sang, self.v_gap_on, self.v_gap,
                  self.v_gap_can_sig, self.v_scenesig, self.v_level,
                  self.v_dong_bo_loat, self.v_burst, self.v_blink,
                  self.v_upright):
            b.trace_add("write", lambda *_a: self._hen_lai_tom_tat())
        self._tom_tat_nhom()

        #[[ BE NGANG CO DINH — mo / dong nhom KHONG lam cot doi be ngang.
        #   Cot rong theo noi dung (Cuon.theo_noi_dung) ma than nhom dong thi
        #   khong tinh vao: mo "Cach can tone" (o chon dai nhat) la cot phinh ra
        #   ~90 px va ca luoi anh nhay cot theo. Nen: do than RONG NHAT cua moi
        #   nhom (do duoc ca khi dang dong) va chong mot thanh chan bang dung be
        #   ngang do. Dong tom tat xuong dong theo dung be ngang ay. ]]
        self.update_idletasks()
        rong = max([n.than.winfo_reqwidth() for n in self._nhom_tuy_chon.values()]
                   + [n.dau.winfo_reqwidth() for n in self._nhom_tuy_chon.values()])
        self._rong_bang = rong
        ttk.Frame(cha, width=rong, height=1).pack(anchor="w")
        for n in self._nhom_tuy_chon.values():
            n.l_tom.configure(wraplength=max(200, rong - 20))
        self.lbl_canh_canh.configure(wraplength=rong)

        self._on_mode_change()

    # ------------------------------------------------- nhóm thu gọn: tóm tắt
    #[[ Ten ngan cho dong tom tat — nhan day du cua hop chon dai toi 50 ky tu
    #   ("Da trang hong — may do + nga hong  (khuyen dung)"), ba cai noi nhau
    #   la tran mot cot. ]]
    NGAN_MODE = {"absolute": "Mặt về mức chuẩn", "scene": "Cân từng cảnh",
                 "batch": "Cả buổi một mức", "hybrid": "Trộn cảnh + mức chuẩn"}
    NGAN_METER = {"face": "đo mặt + bắt nét", "focus": "đo điểm bắt nét",
                  "subject": "đo chủ thể", "center": "đo giữa khung",
                  "average": "đo trung bình khung", "median": "đo trung vị khung"}
    NGAN_WB = {"skin": "WB da trắng hồng", "asshot": "WB theo máy",
               "off": "không đổi WB", "grey": "WB grey-world",
               "scene": "WB grey-world trong cảnh"}
    NGAN_SANG = {"tron": "Trộn — tự tách theo mức sáng",
                 "ngay": "Cả buổi ánh sáng ngày", "den": "Cả buổi ánh đèn"}

    def _hen_lai_tom_tat(self):
        if getattr(self, "_hen_tom_tat", None) is None:
            self._hen_tom_tat = self.after_idle(self._tom_tat_nhom)

    def _tom_tat_nhom(self):
        """Viết lại dòng tóm tắt của từng nhóm theo giá trị đang chọn."""
        self._hen_tom_tat = None
        ds = getattr(self, "_nhom_tuy_chon", None)
        if not ds:
            return
        so = lambda v, d: self._num_im(v, d)      # noqa: E731
        mode = self.mode_value()
        meter = dict(METERS).get(self.v_meter.get(), "face")
        tone = [self.NGAN_MODE.get(mode, mode), self.NGAN_METER.get(meter, meter),
                self.NGAN_WB.get(dict(WBS).get(self.v_wb.get(), "skin"), "")]
        ghim = [t for t, b in (("Highlights", self.v_hl), ("Shadows", self.v_sh),
                               ("da trắng hồng", self.v_grade),
                               ("Curve", self.v_curve)) if b.get()]
        canh = []
        if self.v_gap_on.get():
            canh.append(f"nghỉ > {so(self.v_gap, 5.0):g} phút")
        if self.v_scenesig.get():
            canh.append("đổi bối cảnh")
        tach = ("Tách cảnh khi " + " hoặc ".join(canh)) if canh else \
            "⚠ Không tách cảnh — cả buổi là một cảnh"
        dong = [t for t, b in (("cảnh", self.v_level),
                               ("loạt", self.v_dong_bo_loat)) if b.get()]
        loc = [t for t, b in (("trùng khung", self.v_burst), ("mắt", self.v_blink),
                              ("Auto Transform", self.v_upright)) if b.get()]
        loai = dict(LOAI_BUOI).get(self.v_loai_buoi.get(), "cuoi")
        chu = {
            "tone": " · ".join(t for t in tone if t),
            "sang": self.NGAN_SANG.get(self.v_che_do_sang.get(),
                                       self.v_che_do_sang.get()),
            "tran": (f"Dìm −{so(self.v_maxev, 1.0):.2f} · Kéo +"
                     f"{so(self.v_maxup, 1.0):.2f} · Can thiệp "
                     f"×{so(self.v_gain, 1.0):.2f}"),
            "ghim": ("Tự kéo " + ", ".join(ghim)) if ghim else "Tắt hết",
            "loai_buoi": (f"{'Sự kiện' if loai == 'su_kien' else 'Cưới'} · bù sáng "
                          f"{so(self.v_bu_sang, 0.0):+.2f} EV"),
            "canh": tach + (" · đồng bộ " + " + ".join(dong) if dong else ""),
            "loc": ("Lọc " + ", ".join(loc)) if loc else "Không lọc ảnh",
        }
        for ma, n in ds.items():
            n.dat_tom_tat(chu.get(ma, ""))

    def _num_im(self, var, default: float) -> float:
        """Như _num() nhưng KHÔNG ghi đè ô đang gõ dở — dòng tóm tắt chạy theo
        từng phím bấm, ghi default vào ô lúc người dùng mới gõ “-” là cướp
        phím của họ."""
        try:
            return float(str(var.get()).replace(",", "."))
        except (ValueError, tk.TclError):
            return default

    def _build_actions(self, cha):
        """Nút chạy trên thanh công cụ (như nút Export của Evoto). CHỈ hai việc
        chạy: Phân tích và Dừng — Dừng chỉ hiện khi đang chạy.

        VÌ SAO KHÔNG CÒN NÚT GHI THỨ HAI
            Hồi trước "2 · Ghi vào .xmp" ở đây và "Ghi và đẩy sang Lightroom" ở
            khâu 3 gọi CÙNG MỘT lệnh do_apply() — hai nút một việc, _set_busy()
            phải nhớ khoá cả hai. Nút Ghi dựng riêng ở _build_ghi(), và vẫn là
            đúng một nút trong cả app.

            "Tự động theo dõi…" gỡ bỏ theo yêu cầu. Đường CLI `--watch` vẫn còn
            nguyên trong autotone.py, không đụng tới.
        """
        m = gd.MAU
        self.btn_cancel = gd.NutTron(cha, "Dừng", kieu="chu", nen=m["toi"], icon="dung",
                                     command=self.do_cancel)
        self.btn_analyze = gd.NutTron(cha, "1 · Phân tích", kieu="phu",
                                      nen=m["toi"], command=self.start_analyze)
        self.btn_analyze.pack(side="left", padx=(0, 8))
        #[[ MOT thanh tien do cho ca do lan ghi, nam o thanh trang thai. pb3 tro
        #   vao chinh thanh nay de _tien_do_3() va moi cho goi cu khong phai
        #   sua. ]]
        self.pb = ttk.Progressbar(self.ttb_trai, mode="determinate", length=160)
        self.pb.pack(side="left", padx=(0, 10))
        self.pb3 = self.pb
        self.lbl_tien3 = tk.Label(self.ttb_trai, text="", background=m["toi2"],
                                  foreground=m["mo"], font=gd.CHU_NHO)
        self.lbl_tien3.pack(side="left")

    def _build_ghi(self, cha):
        """Nút “2 · Ghi và đẩy vào Lightroom” — nút VÀNG duy nhất trên thanh công
        cụ, như Export của Evoto — kèm nút “⋯” cho việc phụ.

        VẪN CHỈ MỘT NÚT GHI TRONG CẢ APP
            Lý do gỡ nút "2 · Ghi vào .xmp" khỏi khâu 2 hồi trước là HAI nút cho
            một lệnh, _set_busy() phải nhớ khoá cả hai. btn_ghi3 vẫn là nút
            duy nhất gọi do_apply — kiem_bo_cuc.py và test_giao_dien_gon.py đếm.

        Việc phụ (Xuất CSV, Hoàn tác, Đọc từ Lightroom, Duyệt nhanh, nhật ký,
        cài plugin, và công tắc “Đẩy thẳng vào Lightroom”) gom vào “⋯”.
        Dòng trạng thái lần gửi (lbl_job) nằm ngay bên trái nút Ghi.
        """
        m = gd.MAU
        self.btn_ghi3 = gd.NutTron(cha, "2 · Ghi và đẩy vào Lightroom",
                                   kieu="chinh", nen=m["toi"],
                                   command=self.do_apply)
        self.btn_ghi3.pack(side="left", padx=(0, 6))
        self.btn_ghi3.goi_y = gd.GoiY(
            self.btn_ghi3,
            "Ghi .xmp cho các ảnh trong bảng rồi gửi sang Lightroom.\n"
            "“Đẩy thẳng vào Lightroom” (bật/tắt trong ⋯): plugin áp thẳng vào "
            "catalog — khỏi phải chọn ảnh rồi Metadata → Read Metadata from "
            "File. Bỏ tick thì chỉ ghi .xmp (phải đọc lại bằng tay).")
        self.menu_them = tk.Menu(self, tearoff=0)
        self.menu_them.add_checkbutton(label="Đẩy thẳng vào Lightroom",
                                       variable=self.v_lrpush)
        self.menu_them.add_separator()
        for nhan, lenh in (("Xuất báo cáo CSV", self.do_csv),
                           ("Hoàn tác…", self.do_undo),
                           ("Đọc từ Lightroom", self.do_read_from_lr),
                           (None, None),
                           ("Duyệt nhanh trước khi Export…",
                            lambda: self._chon_khau("day")),
                           ("Nhật ký plugin", self.show_plugin_log),
                           ("Làm mới trạng thái", self.refresh_job_state),
                           ("Cài plugin…", self.show_plugin_help),
                           (None, None),
                           ("Tải bản tăng tốc GPU…", self.tai_gpu),
                           ("Kiểm tra cập nhật…", self.kiem_cap_nhat)):
            if nhan is None:
                self.menu_them.add_separator()
            else:
                self.menu_them.add_command(label=nhan, command=lenh)
        self.btn_them = gd.NutTron(cha, "", icon="them", kieu="chu",
                                   nen=m["toi"], command=self._mo_menu_them)
        self.btn_them.goi_y = gd.GoiY(
            self.btn_them, "Thêm: đẩy thẳng vào Lightroom, xuất CSV, hoàn tác, "
                           "đọc từ Lightroom, duyệt nhanh, nhật ký plugin…")
        self.btn_them.pack(side="left")
        #[[ Trang thai lan gui gan nhat — TRUOC day nam trong the cua khau 3 va
        #   KHONG BAO GIO HIEN (nhan bi pack_forget). Nay nam NGAY CANH nut Ghi
        #   tren thanh cong cu (giua thanh, can phai): bam gui xong la thay
        #   "dang cho / da ap xong" ngay canh cho vua bam. MOT dong — cau dai
        #   cat "…", re chuot hien du (gd.NhanGon): xuong dong la ca thanh cong
        #   cu phinh ra moi lan cau doi. ]]
        self.lbl_job = gd.NhanGon(self.cc_giua, text="", anchor="e",
                                  background=m["toi"], foreground=m["mo"],
                                  font=gd.CHU_NHO)
        self.lbl_job.pack(side="right", fill="x", expand=True)

    def _mo_menu_them(self):
        """Menu “Thêm”: khoá đúng những mục mà nút cũ của nó cũng bị khoá."""
        co_anh = bool(self.items) and not self.busy
        try:
            self.menu_them.entryconfigure("Xuất báo cáo CSV",
                                          state="normal" if co_anh else "disabled")
            self.menu_them.entryconfigure("Hoàn tác…",
                                          state="disabled" if self.busy else "normal")
        except tk.TclError:
            pass
        self._bat_menu(self.menu_them, self.btn_them)

    def kiem_cap_nhat(self):
        """Hoi Releases xem co ban moi khong. Co thi hoi nguoi dung roi tai.

        Buoc KIEM chay o luong nen (mang co the cho 8 giay), roi ve luong giao
        dien bang self.after de hoi + mo hop tai. Khong co mang / da moi nhat
        thi bao mot cau, khong lam gi them — dung nguyen tac "thieu cap nhat
        khong lam hong gi" cua cap_nhat.py.
        """
        try:
            import cap_nhat as cn
        except Exception as ex:                              # noqa: BLE001
            messagebox.showinfo("Cập nhật",
                                f"Bản này chưa có mô-đun cập nhật.\n({ex})",
                                parent=self)
            return

        q: queue.Queue = queue.Queue()

        def _chay():
            try:
                q.put(("ok", cn.kiem_tra()))
            except Exception as ex:                          # noqa: BLE001
                q.put(("loi", f"{type(ex).__name__}: {ex}"))

        threading.Thread(target=_chay, daemon=True).start()

        def _doi():
            try:
                loai, gt = q.get_nowait()
            except queue.Empty:
                self.after(150, _doi)
                return
            if loai == "loi" or gt is None:
                messagebox.showinfo(
                    "Cập nhật",
                    f"Đang dùng bản mới nhất ({cn.phien_ban_dang_chay()}).\n\n"
                    "Không có bản nào mới hơn trên máy chủ."
                    if loai == "ok" else
                    f"Không kiểm được cập nhật (mạng?).\n{gt}",
                    parent=self)
                return
            #[[ Co ban moi — hoi truoc khi tai (nguyen tac da chot voi nguoi dung). ]]
            mb = f" (~{gt['mb']} MB)" if gt.get("mb") else ""
            ghi = ("\n\n" + gt["ghi_chu"]) if gt.get("ghi_chu") else ""
            if messagebox.askyesno(
                    "Có bản cập nhật",
                    f"Bản mới: {gt['ver']}{mb}\n"
                    f"Đang chạy: {cn.phien_ban_dang_chay()}{ghi}\n\n"
                    "Tải và cập nhật ngay? Không cần cài lại — lần mở app sau "
                    "sẽ tự dùng bản mới.",
                    parent=self):
                TaiCapNhat(self, cn, gt)

        self.after(150, _doi)

    def _build_table(self, cha):
        """Trang chính của mô-đun Cân tone: LƯỚI ẢNH (mặc định, như Evoto) hoặc
        BẢNG SỐ. Dòng đầu trang: [Lưới ảnh | Bảng số] · tổng kết · gợi ý."""
        m = gd.MAU
        cha.rowconfigure(0, weight=1)
        cha.columnconfigure(0, weight=1)

        dc = self.dau_chinh
        self.v_xem = tk.StringVar(value="luoi")
        self.chon_xem = gd.PhanDoan(dc, self.v_xem, [("luoi", "Lưới ảnh"),
                                                      ("bang", "Bảng số")],
                                    command=self._doi_xem, nen=m["toi"], deu=False)
        self.chon_xem.pack(side="left")
        self.lbl_tong = tk.Label(dc, text="", background=m["toi"],
                                 foreground=m["mo"], font=gd.CHU, anchor="w")
        self.lbl_tong.pack(side="left", padx=(14, 0))
        #[[ O CANH BAO cua dau trang (catalog cu, plugin cu, canh le loi...).
        #   Khong co canh bao thi la cau nhac sau khi ghi — CHI khi da tat "Day
        #   thang vao Lightroom": dang day thang ma nhac "Metadata → Read
        #   Metadata from File" la chi sai duong (plugin ap thang, doc lai bang
        #   tay con co the ghi de). ]]
        self.lbl_hint = tk.Label(
            dc, anchor="e", justify="right", background=m["toi"],
            foreground=m["mo"], font=gd.CHU_NHO, wraplength=560,
            text=self._goi_y_sau_ghi())
        self.lbl_hint.pack(side="right")

        def _doi_day_thang(*_a):
            if not str(self.lbl_hint.cget("text")).startswith("⚠"):
                self.lbl_hint.configure(text=self._goi_y_sau_ghi(),
                                        foreground=m["mo"])
        self.v_lrpush.trace_add("write", _doi_day_thang)

        # ---- khung lưới ảnh
        self.khung_luoi = tk.Frame(cha, background=m["toi"])
        self.khung_luoi.grid(row=0, column=0, sticky="nsew")
        self.khung_luoi.rowconfigure(0, weight=1)
        self.khung_luoi.columnconfigure(0, weight=1)
        self._build_luoi(self.khung_luoi)

        # ---- khung bảng số
        self.khung_bang = tk.Frame(cha, background=m["toi"])
        self.khung_bang.grid(row=0, column=0, sticky="nsew")
        self.khung_bang.rowconfigure(0, weight=1)
        self.khung_bang.columnconfigure(0, weight=1)
        f = self.khung_bang
        #[[ height=8: bang van cuon duoc; tren cua so thap tk BO HIEN widget
        #   khong vua — nut tung bien mat khong dau vet vi bang an het cho. ]]
        self.tree = ttk.Treeview(f, columns=[c[0] for c in COLS], show="headings",
                                 selectmode="browse", height=8)
        for key, title, width, anchor in COLS:
            self.tree.heading(key, text=title, command=lambda k=key: self._sort_by(k))
            self.tree.column(key, width=width, anchor=anchor,
                             stretch=(key in ("file", "note")))
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(f, orient="vertical", command=self.tree.yview,
                           style="Toi.Vertical.TScrollbar")
        sb.grid(row=0, column=1, sticky="ns")
        #[[ 15 cot ~1250 px ma vung giua (con bang dieu khien ben phai) chi
        #   ~900: thieu thanh cuon ngang la cot "Toi %", "Mat", "Loat", "Ghi
        #   chu" nam ngoai mep, khong cach nao xem. Thanh ngang TU AN khi vua. ]]
        sbx = ttk.Scrollbar(f, orient="horizontal", command=self.tree.xview,
                            style="Toi.Horizontal.TScrollbar")
        sbx.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=sb.set,
                            xscrollcommand=gd.thanh_tu_an(sbx))

        #[[ MAU HANG TREN NEN TOI — nen dam cung sac: van doc duoc chu trang,
        #   va van phan biet duoc ba muc voi nhau. ]]
        self.tree.tag_configure("big", background="#3a2c12")      # chỉnh mạnh
        self.tree.tag_configure("clip", background="#3a1f1d")     # cháy nhiều
        self.tree.tag_configure("err", background="#4a201d")
        self.tree.tag_configure("zero", foreground=gd.MAU["mo2"])  # không đổi gì
        self.tree.bind("<Double-1>", self._show_detail)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._chon_tu_bang(), add="+")
        self._sort_state = (None, False)
        self._doi_xem()

    # ------------------------------------------------------------ lưới ảnh
    def _build_luoi(self, cha):
        """Lưới ảnh của cả buổi (luoi_anh.LuoiAnh) — chế độ xem MẶC ĐỊNH."""
        import luoi_anh
        self.luoi = luoi_anh.LuoiAnh(cha, khi_chon=self._chon_tu_luoi,
                                     khi_mo=self._mo_tu_luoi,
                                     khi_trong=self.pick_folder)
        self.luoi.grid(row=0, column=0, sticky="nsew")
        self._dang_dong_bo_chon = False

    def _doi_xem(self):
        """[Lưới ảnh | Bảng số] — cùng một danh sách, hai cách nhìn."""
        if self.v_xem.get() == "bang":
            self.khung_luoi.grid_remove()
            self.khung_bang.grid()
        else:
            self.khung_bang.grid_remove()
            self.khung_luoi.grid()

    def _cap_nhat_luoi(self, giu_cuon: bool = False):
        """Đổ danh sách ảnh vào lưới: trước khi phân tích là các file RAW của
        buổi (chưa có số), sau khi phân tích là kết quả kèm ΔEV, đúng thứ tự
        bảng số đang sắp.

        Ảnh SẼ KHÔNG được ghi vẫn hiện — mờ đi, kèm nhãn lý do. Lưới là "cả
        buổi": nhìn vào phải thấy ngay tấm nào nằm ngoài, chứ không phải đếm
        lệch rồi đi đoán. (Ngày 3/10 thử buổi 60 RAW chưa có .xmp: lưới trống
        trơn kèm câu "Không tìm thấy file RAW nào" — sai, RAW có đủ 60 tấm.)
          · nguồn .xmp: RAW thiếu sidecar        → "thiếu .xmp"
          · nguồn catalog: không có trong bản xuất Lightroom (gồm cả ảnh 1 sao
            plugin bỏ khi xuất)                    → "không ghi"
        """
        luoi = getattr(self, "luoi", None)
        if luoi is None:
            return
        catalog = self.source_value() == "catalog"
        xuat = getattr(self, "export", None) or {}

        def o_cua(path, **kw):
            return {"path": str(path), "ten": Path(path).name, "dev": None,
                    "canh": None, "loai": "", "sao1": False, "bo": "", **kw}

        if self.items:
            ds = [o_cua(r["path"], dev=r.get("delta_ev"), canh=r.get("scene"),
                        loai=(self._tags(r) or ("",))[0],
                        sao1=(r.get("cull") or "") in ("nham-mat", "loat"),
                        bo="không ghi" if r.get("ngoai_xuat") else "",
                        bw=bool(r.get("bw")))
                  for r in self.items]
        else:
            #[[ Chua phan tich: anh khong co trong ban xuat Lightroom chi danh dau
            #   khi DA CO ban xuat — chua co thi chua biet, dung to mo ca buoi. ]]
            ds = [o_cua(p, bo=("không ghi" if catalog and xuat
                               and at.khoa_duong_dan(p) not in xuat else ""))
                  for p, _sc in (self.pairs or [])]
        thieu = [o_cua(p, bo="thiếu .xmp") for p in (getattr(self, "missing", None) or [])]
        if self.items:
            ds += thieu                 # bảng đang sắp thế nào thì giữ thế ấy
        else:
            ds = sorted(ds + thieu, key=lambda o: o["path"])
        luoi.dat_ds(ds, giu_cuon=giu_cuon)
        if not ds:
            if self.folder() is None:
                luoi.dat_trong("Chưa chọn buổi chụp.\n"
                               "Chọn thư mục ảnh RAW để bắt đầu.")
            else:
                luoi.dat_trong(f"Không tìm thấy file RAW nào trong\n"
                               f"{self.folder()}")
        if not self.items:
            n = len(ds)
            self.lbl_tong.configure(
                text=(f"{n} ảnh RAW · chưa phân tích" if n else ""))

    def _chon_tu_luoi(self, path: str):
        """Bấm một ô lưới -> chọn đúng dòng đó trong bảng số."""
        if self._dang_dong_bo_chon:
            return
        self._dang_dong_bo_chon = True
        try:
            if self.tree.exists(path):
                self.tree.selection_set(path)
                self.tree.focus(path)
                self.tree.see(path)
        finally:
            self._dang_dong_bo_chon = False

    def _chon_tu_bang(self):
        """Chọn một dòng bảng -> lưới chọn đúng tấm đó."""
        if self._dang_dong_bo_chon:
            return
        sel = self.tree.selection()
        if sel and getattr(self, "luoi", None) is not None:
            self._dang_dong_bo_chon = True
            try:
                self.luoi.chon(sel[0])
            finally:
                self._dang_dong_bo_chon = False

    def _mo_tu_luoi(self, path: str):
        """Bấm đúp một ô lưới -> mở bảng chi tiết của tấm đó (như bấm đúp bảng)."""
        if self.tree.exists(path):
            self.tree.focus(path)
            self.tree.selection_set(path)
            self._show_detail(None)

    def _build_status(self):
        """Một thanh trạng thái duy nhất, chạy suốt đáy cửa sổ.

        Trái: thanh tiến độ + đang làm tới đâu. Giữa: chuyện ĐANG XẢY RA.
        Phải: hạn dùng (lbl_han). Lần gửi gần nhất (lbl_job) nằm cạnh nút Ghi
        trên thanh công cụ. Chuyện của riêng một trang nằm trong trang đó.
        """
        m = gd.MAU
        #[[ Mot dong, theo be ngang that cua cot giua (toi_da=None): cau dai
        #   cat "…", re chuot hien du. ]]
        self.lbl_status = gd.NhanGon(self.ttb_giua, text="", anchor="w",
                                     background=m["toi2"], foreground=m["chu"],
                                     font=gd.CHU)
        self.lbl_status.pack(side="left", fill="x", expand=True)

    def _build_lrbox(self, cha):
        """Khâu “Duyệt nhanh & Lightroom” — việc PHỤ quanh lần đẩy.

        3/10 chiều: nút “2 · Ghi và đẩy vào Lightroom”, ô “Đẩy thẳng” và dòng
        trạng thái lần gửi đã dời sang khâu Phân tích (_build_ghi). Ở đây còn
        những việc ít dùng: hoàn tác, đọc lại thông số, nhật ký plugin, cài
        plugin, và Duyệt nhanh. Mở từ menu “⋯” cạnh nút Ghi (cột trái đã bỏ).
        """
        gd.tieu_muc(cha, "Lightroom").grid(row=0, column=0, sticky="w",
                                           pady=(0, 6))
        bar = ttk.Frame(cha)
        bar.grid(row=3, column=0, sticky="w", pady=(0, 0))
        self.btn_undo = ttk.Button(bar, text="Hoàn tác…", command=self.do_undo)
        self.btn_undo.pack(side="left", padx=(0, 6))
        self.btn_read = ttk.Button(bar, text="Đọc từ Lightroom",
                                   command=self.do_read_from_lr)
        self.btn_read.pack(side="left", padx=(0, 6))
        self.btn_joblog = ttk.Button(bar, text="Nhật ký plugin", style="Pha.TButton",
                                     command=self.show_plugin_log)
        self.btn_joblog.pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Làm mới", style="Pha.TButton",
                   command=self.refresh_job_state).pack(side="left")
        ttk.Button(bar, text="Cài plugin", style="Pha.TButton",
                   command=self.show_plugin_help).pack(side="left")

        self._build_duyet(cha)
        self.refresh_job_state()

    def _build_duyet(self, cha):
        """Duyệt nhanh — soát màu sau khi ghi, TRƯỚC khi Export.

        VÌ SAO NẰM Ở KHÂU 3 CHỨ KHÔNG PHẢI MỘT KHÂU RIÊNG
            Đúng thứ tự làm việc: ghi màu -> soát hết một lượt -> sửa mấy tấm
            chưa ổn -> mới Export. Soát là phần đuôi của việc ghi, không phải
            một việc rời; tách thành khâu riêng thì phải sửa cả bảng KHAU và
            trang_thai.tinh() để đổi đúng một thứ đang chạy tốt.

        VÌ SAO KHÔNG DÙNG PREVIEW CỦA LIGHTROOM
            SDK Lua không có API nào cho preview — xem DuyetCore.lua. Ở đây
            Lightroom render ra JPEG nhỏ bằng LrExportSession (có GPU), app mở
            mấy ảnh đó lên soát. Nhờ vậy Import không cần bật Smart Preview và
            không phải chờ dựng preview lần nào.
        """
        gd.tieu_muc(cha, "Duyệt nhanh trước khi Export").grid(
            row=4, column=0, sticky="w", pady=(24, 6))
        ttk.Label(cha, style="Mo2.TLabel", wraplength=760, justify="left",
                  text="Lightroom render ảnh JPEG nhỏ để soát màu — không cần "
                       "Smart Preview, không phải chờ dựng preview. Soát xong, "
                       "đánh dấu đỏ mấy tấm cần sửa rồi mở Develop sửa đúng "
                       "mấy tấm đó."
                  ).grid(row=5, column=0, sticky="w")

        d = ttk.Frame(cha)
        d.grid(row=6, column=0, sticky="ew", pady=(12, 0))
        d.columnconfigure(4, weight=1)
        self.btn_duyet = ttk.Button(d, text="Dựng ảnh duyệt",
                                    style="Chinh.TButton",
                                    command=lambda: self.do_duyet(None))
        self.btn_duyet.grid(row=0, column=0, padx=(0, 6))
        #[[ Nut chay thu de RIENG va de canh nut chinh. Lan dau tren mot may
        #   moi thi phai co so do that truoc khi tin — 50 anh mat vai chuc giay,
        #   ca buoi thi khong ai muon phat hien sai sau 20 phut. ]]
        self.btn_duyet20 = ttk.Button(
            d, text=f"Thử {duyet.GIOI_HAN_THU} ảnh", style="Pha.TButton",
            command=lambda: self.do_duyet(duyet.GIOI_HAN_THU))
        self.btn_duyet20.grid(row=0, column=1, padx=(0, 6))
        #[[ NUT DUNG.
        #   Thu muc 2000 anh ma lo bam chay ca buoi thi truoc day khong co
        #   duong nao thoat: vong lap nen cua plugin khong co nut bam, con tat
        #   Lightroom giua chung la cach te nhat. Nut nay dat mot file co;
        #   plugin kiem giua hai lo roi dung. ]]
        self.btn_dung_duyet = ttk.Button(d, text="Dừng", style="Pha.TButton",
                                         command=self.do_dung_duyet)
        self.btn_dung_duyet.grid(row=0, column=2, padx=(0, 10))
        self.pb_duyet = ttk.Progressbar(d, mode="determinate", length=200)
        self.pb_duyet.grid(row=0, column=3, padx=(0, 10))
        self.lbl_duyet = ttk.Label(d, style="Mo2.TLabel", text="")
        self.lbl_duyet.grid(row=0, column=4, sticky="w")

        d2 = ttk.Frame(cha)
        d2.grid(row=7, column=0, sticky="w", pady=(8, 0))
        self.btn_mo_duyet = ttk.Button(d2, text="Mở lưới soát",
                                       command=self.do_mo_duyet)
        self.btn_mo_duyet.pack(side="left", padx=(0, 6))
        ttk.Button(d2, text="Xoá ảnh duyệt", style="Pha.TButton",
                   command=self.do_xoa_duyet).pack(side="left")

        self._duyet_dang_soi = False
        self._cap_nhat_duyet()

    # ------------------------------------------------------------- duyệt nhanh
    def _cap_nhat_duyet(self):
        """Vẽ lại thanh tiến trình và nhãn của khối Duyệt nhanh."""
        td = duyet.tien_do()
        tong = int(td.get("tong") or 0)
        xong = int(td.get("xong") or 0)
        self.pb_duyet.configure(maximum=max(tong, 1), value=min(xong, max(tong, 1)))
        self.lbl_duyet.configure(text=duyet.mo_ta(td))
        f = self.folder()
        co_anh = bool(duyet.bang_anh())
        self.btn_mo_duyet.configure(state="normal" if (f and co_anh) else "disabled")
        dang = td.get("trang_thai") == "dang_chay" or duyet.dang_cho()
        self.btn_dung_duyet.configure(state="normal" if dang else "disabled")
        return td

    def do_duyet(self, gioi_han=None):
        f = self.folder()
        if not f:
            messagebox.showinfo("Chưa chọn thư mục",
                                "Chọn thư mục buổi chụp trước đã (nút buổi chụp ở góc trên bên trái).")
            return
        dest = duyet.thu_muc_duyet(f)
        try:
            duyet.yeu_cau(f, dest=dest, gioi_han=gioi_han)
        except OSError as ex:
            messagebox.showerror("Không gửi được yêu cầu", str(ex))
            return
        n = f"{gioi_han} ảnh đầu" if gioi_han else "cả buổi"
        self.status(f"Đã nhờ Lightroom dựng ảnh duyệt ({n}). "
                    "Lightroom phải đang mở; plugin dò 5 giây một lần.",
                    gd.MAU["nhan"])
        self.lbl_duyet.configure(text="Đang chờ plugin nhận yêu cầu…")
        if not self._duyet_dang_soi:
            self._duyet_dang_soi = True
            self.after(1500, self._soi_duyet)

    def _soi_duyet(self, im_lang: int = 0):
        """Theo dõi tiến trình dựng ảnh duyệt.

        Dừng dò khi plugin báo xong/lỗi. Nếu mãi không thấy gì (Lightroom không
        mở, hoặc plugin là bản cũ chưa có DuyetCore) thì sau 60 giây phải NÓI
        RA — im lặng chờ mãi là kiểu hỏng khó chẩn đoán nhất."""
        td = self._cap_nhat_duyet()
        tt = td.get("trang_thai")
        if tt in ("xong", "dung", "loi"):
            self._duyet_dang_soi = False
            if tt == "xong":
                self.status(duyet.mo_ta(td) + " — bấm “Mở lưới soát”.",
                            gd.MAU["xong"])
            elif tt == "dung":
                self.status(duyet.mo_ta(td) + " — số ảnh đã dựng vẫn soát được.",
                            gd.MAU["canh"])
            else:
                self.status(duyet.mo_ta(td), gd.MAU["loi"])
            return
        if not tt and duyet.dang_cho():
            im_lang += 1
            if im_lang == 40:            # 40 x 1,5s = 60 giây
                self.status(
                    "Đã 60 giây mà plugin chưa nhận yêu cầu dựng ảnh duyệt. "
                    "Kiểm: Lightroom có đang mở không, và plugin đã nạp lại "
                    "bản mới chưa (Plug-in Manager → Reload).", gd.MAU["canh"])
        else:
            im_lang = 0
        self.after(1500, lambda: self._soi_duyet(im_lang))

    def do_dung_duyet(self):
        """Xin plugin dừng dựng ảnh duyệt sau khi xong lô đang chạy."""
        try:
            duyet.dung()
        except OSError as ex:
            messagebox.showerror("Không gửi được lệnh dừng", str(ex))
            return
        #[[ Noi ro "sau khi xong lo dang chay" chu khong noi "da dung".
        #   Plugin kiem co GIUA HAI LO — cat ngang mot lo dang render se de lai
        #   file do tren dia. Nen co the con doi toi 25 anh nua; noi truoc thi
        #   khong ai tuong nut hong. ]]
        self.lbl_duyet.configure(text="Đã xin dừng — plugin dừng sau khi xong "
                                      "lô đang chạy…")
        self.status("Đã xin dừng dựng ảnh duyệt. Ảnh đã dựng vẫn soát được "
                    "bình thường.", gd.MAU["canh"])

    def do_mo_duyet(self):
        f = self.folder()
        if not f:
            return
        if not duyet.bang_anh():
            messagebox.showinfo(
                "Chưa có ảnh duyệt",
                "Bấm “Dựng ảnh duyệt” trước — Lightroom cần render ảnh ra đã.")
            return
        duyet_ui.CuaSoDuyet(self, f, duyet.thu_muc_duyet(f))

    def do_xoa_duyet(self):
        f = self.folder()
        if not f:
            return
        dest = duyet.thu_muc_duyet(f)
        if not dest.is_dir():
            self.status("Không có thư mục ảnh duyệt nào để xoá.", gd.MAU["mo"])
            return
        if not messagebox.askokcancel(
                "Xoá ảnh duyệt",
                f"Xoá cả thư mục:\n{dest}\n\n"
                "Chỉ xoá ảnh JPEG dựng để soát. Ảnh gốc và thông số trong "
                "Lightroom không bị đụng tới."):
            return
        byte = duyet.don_dep(dest)
        self._cap_nhat_duyet()
        self.status(f"Đã xoá ảnh duyệt, giải phóng {byte / 1e6:.0f} MB",
                    gd.MAU["xong"])

    # ------------------------------------------------------- khâu 4 và khâu 7
    def _build_export(self, cha):
        """Khâu 4 — chỉ chỗ Lightroom đã Export ra.

        Đây là một trong ba thứ KHÔNG suy được từ đĩa (xem trang_thai.py), nên
        ứng dụng buộc phải hỏi. Hỏi một lần cho mỗi buổi, rồi nhớ."""
        self.the_export = gd.The(cha, "Chưa biết anh Export ra đâu",
                                 "Lightroom không để lại dấu vết nào đọc được.",
                                 "cho")
        self.the_export.grid(row=0, column=0, sticky="ew")

        h = ttk.Frame(cha)
        h.grid(row=1, column=0, sticky="ew", pady=(16, 0))
        h.columnconfigure(1, weight=1)
        ttk.Label(h, text="Thư mục Export").grid(row=0, column=0, padx=(0, 10))
        self.v_export_dir = tk.StringVar()
        ttk.Entry(h, textvariable=self.v_export_dir).grid(row=0, column=1,
                                                          sticky="ew", padx=(0, 6))
        ttk.Button(h, text="Chọn…", command=self._chon_export).grid(row=0, column=2)
        ttk.Label(cha, style="Mo2.TLabel",
                  text="Chọn tên không dấu — OpenCV trên Windows không mở được "
                       "đường dẫn có dấu tiếng Việt."
                  ).grid(row=2, column=0, sticky="w", pady=(6, 0))

        #[[ CHO PLUGIN NOI, KHONG PHAI DOAN.
        #
        #   Plugin cam mot Export Filter vao chinh luong Export cua nguoi dung
        #   nen doc duoc thu muc dich tu bang thong so ho vua chon. Nhung filter
        #   chi chay khi ho da tich no mot lan trong hop thoai Export, nen o day
        #   phai chiu duoc ca hai truong hop: co ban bat duoc, va khong co.
        #
        #   VA KHONG BAO GIO TU DIEN DE LEN CAI HO DA GO. Lang le doi duong dan
        #   duoi tay nguoi dung la kieu loi khong ai lan ra duoc.
        #]]
        self.khung_batduoc = ttk.Frame(cha)
        self.khung_batduoc.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        self.khung_batduoc.columnconfigure(0, weight=1)
        self.lbl_batduoc = ttk.Label(self.khung_batduoc, style="Mo.TLabel",
                                     text="", wraplength=700, justify="left")
        self.lbl_batduoc.grid(row=0, column=0, sticky="w")
        self.btn_batduoc = ttk.Button(self.khung_batduoc, text="Dùng đường dẫn này",
                                      style="Pha.TButton", command=self._dung_batduoc)
        self.btn_batduoc.grid(row=0, column=1, padx=(10, 0))
        self._build_xuat(cha)
        self._lam_moi_export()

    # --------------------------------------------------- Export ngay trong app

    def _build_xuat(self, cha):
        """Bấm một nút, Lightroom xuất — không mở hộp thoại Export nào.

        VÌ SAO THÊM ĐƯỜNG NÀY BÊN CẠNH Ô NHẬP TAY Ở TRÊN
            Ô ở trên giải bài "anh Export xong rồi, app phải biết ra đâu".
            Đường này giải bài đó theo chiều ngược lại: app tự chạy lượt
            Export, nên thư mục đích là thứ app ĐẶT RA, không phải thứ phải
            đoán, phải nghe, phải hỏi. Chắc chắn tuyệt đối.

            Hai đường độc lập. Hỏng đường này thì đường kia vẫn chạy.

        THÔNG SỐ KHÔNG BỊA
            App KHÔNG dựng lại hộp thoại Export của Lightroom (gần bốn chục ô,
            quên một ô là ảnh giao khách khác với ảnh vẫn giao). Nó đọc đúng
            thông số Lightroom đang dùng và gửi nguyên sang — xem thongso_lr.py.
            Không đọc được thì KHÔNG có nút bấm, thà thế còn hơn xuất bằng
            thông số bịa.
        """
        gd.tieu_muc(cha, "Hoặc để app Export luôn").grid(
            row=4, column=0, sticky="w", pady=(26, 6))
        self.lbl_xuat_ts = ttk.Label(cha, style="Mo2.TLabel", wraplength=760,
                                     justify="left", text="")
        self.lbl_xuat_ts.grid(row=5, column=0, sticky="w")

        h = ttk.Frame(cha)
        h.grid(row=6, column=0, sticky="ew", pady=(12, 0))
        h.columnconfigure(5, weight=1)
        self.btn_xuat = ttk.Button(h, text="Export bằng thông số này",
                                   style="Chinh.TButton", command=self.do_xuat)
        self.btn_xuat.grid(row=0, column=0, padx=(0, 6))
        self.btn_dung_xuat = ttk.Button(h, text="Dừng", style="Pha.TButton",
                                        command=self.do_dung_xuat)
        self.btn_dung_xuat.grid(row=0, column=1, padx=(0, 10))
        self.v_xuat_bo1 = tk.BooleanVar(value=True)
        ttk.Checkbutton(h, text="Bỏ ảnh 1 sao",
                        variable=self.v_xuat_bo1).grid(row=0, column=2, padx=(0, 12))
        #[[ VA CHAM TEN FILE: bat buoc chon truoc, khong de "ask".
        #   Thong so that cua may nay dang la "ask" — Lightroom se dung mot hop
        #   thoai giua chung, ma vong lap nen thi khong co ai bam. Nhin tu ngoai
        #   giong het "app treo". ]]
        ttk.Label(h, text="Trùng tên").grid(row=0, column=3, padx=(0, 6))
        self.v_xuat_vc = tk.StringVar(value="overwrite")
        ttk.Combobox(h, textvariable=self.v_xuat_vc, width=12, state="readonly",
                     values=("overwrite", "skip", "rename")
                     ).grid(row=0, column=4, padx=(0, 12))
        self.pb_xuat = ttk.Progressbar(h, mode="determinate", length=180)
        self.pb_xuat.grid(row=0, column=5, sticky="w")
        self.lbl_xuat = ttk.Label(cha, style="Mo2.TLabel", text="",
                                  wraplength=760, justify="left")
        self.lbl_xuat.grid(row=7, column=0, sticky="w", pady=(8, 0))

        self._xuat_dang_soi = False
        self._lam_moi_xuat_ts()

    def _thong_so_xuat(self) -> dict:
        """Thông số Export lấy từ Lightroom. {} nếu không đọc được."""
        try:
            import thongso_lr as tl
            st, _luc = tl.doc_prefs()
            return st
        except Exception:                                    # noqa: BLE001
            return {}

    def _lam_moi_xuat_ts(self):
        try:
            import thongso_lr as tl
            st, luc = tl.doc_prefs()
        except Exception:                                    # noqa: BLE001
            st, luc = {}, None
        if not st:
            self.lbl_xuat_ts.configure(
                text="Chưa đọc được thông số Export của Lightroom, nên app "
                     "không dám tự xuất — bịa thông số cho ảnh giao khách là "
                     "kiểu sai tệ nhất. Anh cứ Export bằng Lightroom như "
                     "thường, ô ở trên vẫn nhận đường dẫn.")
            self.btn_xuat.configure(state="disabled")
            return
        #[[ Noi thang moc thoi gian. Lightroom ghi file cau hinh theo nhip cua
        #   no, khong ghi ngay luc bam OK — nen bang nay CO THE cu hon lan
        #   Export gan nhat. Giau con so do di la de nguoi dung tin nham. ]]
        khi = luc.strftime("%d/%m %H:%M") if luc else "không rõ lúc nào"
        self.lbl_xuat_ts.configure(
            text=f"Dùng đúng thông số lần Export gần nhất của anh trong "
                 f"Lightroom (đọc lúc {khi}): {tl.mo_ta(st)}")
        self.btn_xuat.configure(state="normal")

    def do_xuat(self):
        f = self.folder()
        if not f:
            messagebox.showinfo("Chưa chọn buổi", "Chọn thư mục buổi chụp trước.")
            return
        dest = self.v_export_dir.get().strip()
        if not dest:
            messagebox.showinfo(
                "Chưa có thư mục đích",
                "Chọn “Thư mục Export” ở trên — đó là chỗ ảnh sẽ ra.")
            return
        st = self._thong_so_xuat()
        if not st:
            return
        try:
            import thongso_lr as tl
            import xuat_lr
            st = tl.ep(st, dest, self.v_xuat_vc.get())
            xuat_lr.yeu_cau_xuat(f, dest, st,
                                 bo_sao=1 if self.v_xuat_bo1.get() else 0)
        except (OSError, ValueError) as ex:
            messagebox.showerror("Không gửi được yêu cầu", str(ex))
            return
        self.pb_xuat.configure(value=0)
        self.lbl_xuat.configure(text="Đã gửi yêu cầu — chờ Lightroom nhận…")
        self.status("Đã gửi yêu cầu Export sang Lightroom.", gd.MAU["nhan"])
        if not self._xuat_dang_soi:
            self._xuat_dang_soi = True
            self.after(1200, self._soi_xuat_anh)

    def do_dung_xuat(self):
        try:
            import xuat_lr
            xuat_lr.dung_xuat()
        except OSError as ex:
            messagebox.showerror("Không gửi được lệnh dừng", str(ex))
            return
        #[[ Noi ro "sau khi xong lo dang chay", giong nut Dung cua Duyet nhanh:
        #   plugin kiem co GIUA HAI LO, cat ngang mot lo dang render se de lai
        #   file do tren dia. ]]
        self.lbl_xuat.configure(text="Đã xin dừng — plugin dừng sau khi xong "
                                     "lô đang chạy…")

    def _soi_xuat_anh(self, im_lang: int = 0):
        """Theo dõi lượt Export do app gửi.

        Im lặng chờ mãi là kiểu hỏng khó chẩn đoán nhất — đã mất một vòng chẩn
        đoán vì plugin chết mà không ai biết. Nên quá 60 giây không thấy gì thì
        phải nói ra."""
        try:
            import xuat_lr
            td = xuat_lr.tien_do_xuat()
            cho = xuat_lr.dang_cho_xuat()
        except Exception:                                    # noqa: BLE001
            self._xuat_dang_soi = False
            return
        tong = td.get("tong") or 0
        xong = td.get("xong") or 0
        if tong:
            self.pb_xuat.configure(maximum=tong, value=xong)
        tt = td.get("trang_thai")
        if tt == "dang_chay":
            bo = td.get("bo_sao") or 0
            self.lbl_xuat.configure(
                text=f"Đang xuất {xong}/{tong} ảnh vào {td.get('thu_muc', '')}"
                     + (f" · đã bỏ {bo} ảnh 1 sao" if bo else ""))
        elif tt in ("xong", "dung", "loi"):
            self._xuat_dang_soi = False
            loi = td.get("loi") or 0
            if tt == "loi":
                self.lbl_xuat.configure(text="Lỗi: " + str(td.get("thong_bao", "")))
                self.status("Export không chạy được: "
                            + str(td.get("thong_bao", "")), gd.MAU["loi"])
            else:
                cau = (f"Xong {xong}/{td.get('tong', xong)} ảnh"
                       + (f", {loi} ảnh không ra file" if loi else "")
                       + " · " + str(td.get("thong_bao", "")))
                self.lbl_xuat.configure(text=cau)
                self.status(cau, gd.MAU["canh"] if (loi or tt == "dung")
                            else gd.MAU["xong"])
            #[[ Xuat xong thi khau 5 phai dem lai ngay: the o tren van dang
            #   hien so anh cua lan truoc. ]]
            self._lam_moi_export()
            self._lam_moi_ray()
            self.day_export_sang_retouch(td.get("thu_muc", ""))
            return
        elif not tt and cho:
            im_lang += 1
            if im_lang == 50:            # 50 x 1,2s = 60 giây
                self.status(
                    "Đã 60 giây mà plugin chưa nhận yêu cầu Export. Kiểm: "
                    "Lightroom có đang mở không, và plugin đã nạp lại bản mới "
                    "chưa (Plug-in Manager → Reload).", gd.MAU["canh"])
        else:
            im_lang = 0
        self.after(1200, lambda: self._soi_xuat_anh(im_lang))

    def _dung_batduoc(self):
        """Chép đường dẫn plugin bắt được vào ô — chỉ khi người dùng tự bấm."""
        try:
            import xuat_lr
            d = xuat_lr.doc().get("thu_muc") or ""
        except Exception:                                    # noqa: BLE001
            return
        if not d:
            return
        self.v_export_dir.set(os.path.normpath(d))
        f = self.folder()
        if f:
            import trang_thai as tt
            tt.ghi(tt.ten_buoi(f), thu_muc_export=self.v_export_dir.get())
        self._lam_moi_export()
        self.day_export_sang_retouch(self.v_export_dir.get())

    def _chon_export(self):
        d = filedialog.askdirectory(title="Thư mục Lightroom đã Export ra",
                                    initialdir=self.v_export_dir.get() or None)
        if not d:
            return
        self.v_export_dir.set(os.path.normpath(d))
        f = self.folder()
        if f:
            import trang_thai as tt
            tt.ghi(tt.ten_buoi(f), thu_muc_export=self.v_export_dir.get())
        self._lam_moi_export()
        self.day_export_sang_retouch(self.v_export_dir.get())

    def _lam_moi_export(self):
        try:
            import trang_thai as tt
            f = self.folder()
            if not f:
                return
            st = tt.doc(tt.ten_buoi(f))
            d = st.get("thu_muc_export") or ""
            if d and not self.v_export_dir.get():
                self.v_export_dir.set(d)
            n = tt.dem_anh(d) if d else 0
            if d and n:
                self.the_export.dat(f"{n} ảnh trong {Path(d).name}", d, "xong")
            elif d:
                self.the_export.dat("Thư mục chưa có ảnh nào", d, "cho")
            else:
                self.the_export.dat("Chưa biết anh Export ra đâu",
                                    "Bật “AutoTone: ghi lại thư mục Export” trong "
                                    "hộp thoại Export của Lightroom thì app tự biết.",
                                    "cho")
            self._lam_moi_batduoc(d)
        except Exception:                                    # noqa: BLE001
            pass

    def day_export_sang_retouch(self, d: str):
        """Khâu 5 vừa biết thư mục Export -> báo cho khâu Retouch.

        #[[ Khau Retouch dung trong mot cua so con dung lazy: chua mo lan nao
        #   thi khong co gi de bao, va cung khong can — luc mo no tu doc lai
        #   thu_muc_export tu trang_thai. ]]
        """
        w = getattr(self, "_retouch_win", None)
        if w is None or not d:
            return
        try:
            w.theo_thu_muc_export(d)
        except Exception:                                    # noqa: BLE001
            pass

    def _lam_moi_batduoc(self, dang_dung: str):
        """Ba trạng thái, ba câu khác nhau — và chỉ một cái đáng gọi là cảnh báo."""
        if not hasattr(self, "lbl_batduoc"):
            return
        try:
            import xuat_lr
            b = xuat_lr.doc()
        except Exception:                                    # noqa: BLE001
            b = {}
        if not b:
            self.lbl_batduoc.configure(
                text="Plugin chưa bắt được lần Export nào. Trong hộp thoại Export "
                     "của Lightroom, mục Post-Process Actions, chọn “AutoTone: ghi "
                     "lại thư mục Export” rồi lưu vào preset — chỉ phải làm một lần.")
            self.btn_batduoc.grid_remove()
            return
        bat = b.get("thu_muc", "")
        tem = b.get("tem", "")
        if xuat_lr.cung_mot_cho(bat, dang_dung):
            #[[ Khop roi thi KHONG con gi de bam. De nut o day chi lam nguoi
            #   dung phan van "minh co phai bam khong". ]]
            self.lbl_batduoc.configure(
                text=f"Khớp với lần Export gần nhất của Lightroom ({tem}).")
            self.btn_batduoc.grid_remove()
        elif dang_dung:
            self.lbl_batduoc.configure(
                text=f"Lightroom Export gần nhất ra một chỗ KHÁC: {bat} ({tem}). "
                     f"Ô trên đang là {dang_dung}.")
            self.btn_batduoc.grid()
        else:
            self.lbl_batduoc.configure(
                text=f"Lightroom vừa Export ra {bat} ({tem}).")
            self.btn_batduoc.grid()

    def _build_hoc(self, cha):
        """Khâu 7 — tham số tool đã học được và đang dùng thay cho mặc định."""
        self.the_gu = gd.The(cha, "", "", "tin")
        self.the_gu.grid(row=0, column=0, sticky="ew")

        gd.tieu_muc(cha, "Tham số đã học").grid(row=1, column=0, sticky="w",
                                                pady=(16, 6))
        self.txt_gu = tk.Text(cha, height=8, wrap="none", relief="flat",
                              background=gd.MAU["tam"], foreground=gd.MAU["chu"],
                              font=gd.CHU_SO, padx=12, pady=10,
                              highlightthickness=1,
                              highlightbackground=gd.MAU["vien"])
        self.txt_gu.grid(row=2, column=0, sticky="ew")
        self.txt_gu.configure(state="disabled")

        bar = ttk.Frame(cha)
        bar.grid(row=3, column=0, sticky="w", pady=(18, 0))
        self.btn_learn = ttk.Button(bar, text="Học từ buổi này",
                                    style="Chinh.TButton", command=self.do_learn)
        self.btn_learn.pack(side="left", padx=(0, 6))
        ttk.Button(bar, text="Làm mới", style="Pha.TButton",
                   command=self._lam_moi_hoc).pack(side="left")
        self._lam_moi_hoc()

    def _lam_moi_hoc(self):
        mo = at.mo_ta_gu()
        n = len(getattr(at, "GU_DA_HOC", {}) or {})
        self.the_gu.dat(f"Đã học {n} tham số" if n else "Chưa học được gì",
                        "Mọi lần phân tích đều dùng những con số này thay cho "
                        "mặc định của tool." if n else
                        "Gắn lý do ở “Vì sao tôi sửa” rồi bấm “Học từ buổi này”.",
                        "tin" if n else "")
        self.txt_gu.configure(state="normal")
        self.txt_gu.delete("1.0", "end")
        self.txt_gu.insert("1.0", mo or "(chưa có)")
        self.txt_gu.configure(state="disabled")

    def refresh_job_state(self):
        """Đọc lại trạng thái job mới nhất trong thư mục jobs.

        Chạy cả lúc khởi động: job của lần chạy trước vẫn còn đó, nên mở app lên
        là biết ngay lần gửi gần nhất đã tới Lightroom chưa.

        #[[ CHI JOB CUA BUOI DANG MO (3/10 chieu). Dong nay gio nam ngay duoi
        #   nut Ghi o khau Phan tich (truoc day an trong khau 3, xem _build_ghi)
        #   — lay "job moi nhat bat ke buoi nao" thi dang mo G:\\2709 ma dong
        #   nay khoe lan gui cua Hiu. Chua chon buoi thi moi lay moi buoi. ]]
        """
        f = self.folder()
        self._goi_y_job("")
        jobs = ([p for p in sorted(at.LR_JOB_DIR.glob("apply_*.tsv"))
                 if at.job_cua_buoi(p, f)] if at.LR_JOB_DIR.is_dir() else [])
        if jobs:                                   # còn .tsv = plugin chưa áp
            #[[ Dang theo doi job nay roi thi thoi — goi lai moi lan chon thu
            #   muc ma khong chot thi moi lan them mot vong after() do cung mot
            #   job. ]]
            if getattr(self, "_job_dang_theo", None) != jobs[-1]:
                self._watch_job(jobs[-1])
            return

        done = ([p for p in sorted(at.LR_JOB_DIR.glob("apply_*.done"))
                 if at.job_cua_buoi(p, f)] if at.LR_JOB_DIR.is_dir() else [])
        if not done:
            self.lbl_job.unbind("<Button-1>")
            self.lbl_job.configure(
                text=(f"Buổi {f.name} chưa gửi lần nào. " if f else
                      "Chưa gửi lần nào. ")
                + "Bấm “2 · Ghi và đẩy vào Lightroom” khi đã soát bảng.",
                foreground=gd.MAU["mo"])
            return

        last = done[-1]
        res = at.job_result(last)
        stamp = datetime.fromtimestamp(last.stat().st_mtime).strftime("%H:%M %d/%m")
        self.lbl_job.unbind("<Button-1>")
        #[[ 7/10 (thiet ke lai): dong nay nam giua thanh cong cu — truoc day in
        #   nguyen dong nhat ky plugin ("apply_2026..tsv: ap 922, bo qua 136 (da
        #   dung san), tong 1058 dong; 0 khong co trong catalog, 0 loi..." —
        #   khong dau, dai het thanh). Nay: MOT cau ngan co dau; dong day du nam
        #   trong chu thich noi khi re chuot. ]]
        self.lbl_job.configure(text=self._tom_job(stamp, res, f.name if f else ""),
                               foreground=gd.MAU["xong"])
        self._goi_y_job(f"Lần gửi gần nhất {stamp}\n{res or last.name}")

    @staticmethod
    def _tom_job(stamp: str, res: str, ten: str) -> str:
        """Dòng nhật ký plugin -> một câu ngắn có dấu cho thanh công cụ.

        "…: ap 922, bo qua 136 (…), tong 1058 dong; 0 khong co trong catalog,
        2 loi…" -> "✓ Buổi G0310 đã đẩy vào Lightroom 16:23 03/10 · 922 ảnh ·
        2 lỗi" (ten = tên buổi — đổi buổi là biết ngay dòng này nói về buổi nào).
        Không đọc ra số nào (plugin đổi cách ghi) thì vẫn nói được đã gửi lúc nào."""
        import re as _re
        r = str(res or "")
        phan = [f"✓ Buổi {ten} đã đẩy vào Lightroom {stamp}" if ten
                else f"✓ Đã đẩy vào Lightroom {stamp}"]
        m = _re.search(r"\bap (\d+)", r)
        if m:
            phan.append(f"{int(m.group(1))} ảnh")
        m = _re.search(r"\b(\d+) loi\b", r)
        if m and int(m.group(1)):
            phan.append(f"{int(m.group(1))} lỗi")
        m = _re.search(r"\b(\d+) khong co trong catalog", r)
        if m and int(m.group(1)):
            phan.append(f"{int(m.group(1))} ảnh không có trong catalog")
        return "  ·  ".join(phan)

    def _goi_y_job(self, chu: str) -> None:
        """Chú thích nổi của dòng trạng thái gửi Lightroom (dòng đầy đủ)."""
        dat = getattr(self.lbl_job, "dat_goi_y", None)
        if dat is not None:
            dat(chu)

    # -------------------------------------------------------------- trạng thái
    def _tien_do_3(self, done: int, total: int, viec: str) -> None:
        """Cập nhật thanh tiến độ của lần đo / lần ghi (pb3 giờ là chính thanh
        của khâu Phân tích) kèm dòng chữ cạnh nó. Im lặng nếu chưa dựng xong.

        Dựng giao diện theo thứ tự nào thì cũng có lúc một khâu chưa tồn tại mà
        hàng đợi đã có tin — nên phải chịu được việc widget chưa có, thay vì để
        một AttributeError làm chết cả vòng bơm tin.
        """
        pb = getattr(self, "pb3", None)
        if pb is None:
            return
        try:
            pb.configure(value=done, maximum=max(total, 1))
            self.lbl_tien3.configure(
                text=f"{viec} {done}/{total}" if done < total
                else f"{viec} xong {total}/{total}")
        except Exception:                                    # noqa: BLE001
            pass
        self._hien_tien_do()

    def _hien_tien_do(self):
        """Thanh tiến độ chỉ hiện khi ĐANG chạy, hoặc khi còn chữ của lần chạy
        vừa rồi ("Đã ghi xong 34/34" — bằng chứng đã chạy xong, xem _ghi_xong).
        Lúc rảnh nó là một rãnh trống 160 px đẩy dòng trạng thái ra giữa thanh."""
        pb = getattr(self, "pb", None)
        nhan = getattr(self, "lbl_tien3", None)
        if pb is None or nhan is None:
            return
        #[[ 8/10 (user: "ben Retouch khong hien thanh da ghi xong, chuyen thanh
        #   thanh Progress xu ly anh Retouch"): o mo-dun Retouch, thanh + chu
        #   "Đã ghi xong 738/738" cua Can tone AN — cho do la thanh tien do
        #   retouch (RetouchWindow._hien_tien_do_tt). ]]
        if getattr(self, "_md_dang", "tone") == "retouch":
            for w in (pb, nhan):
                try:
                    w.pack_forget()
                except tk.TclError:
                    pass
            return
        try:
            if not nhan.winfo_manager():
                nhan.pack(side="left")
        except tk.TclError:
            pass
        co = bool(getattr(self, "busy", False)) or bool(nhan.cget("text"))
        try:
            if co and not pb.winfo_manager():
                pb.pack(side="left", padx=(0, 10), before=nhan)
            elif not co and pb.winfo_manager():
                pb.pack_forget()
        except tk.TclError:
            pass

    def _set_busy(self, busy: bool):
        self.busy = busy
        state = "disabled" if busy else "normal"
        for b in (self.btn_analyze, self.btn_undo):
            b.configure(state=state)
        self.btn_cancel.configure(state="normal" if busy else "disabled")
        #[[ "Dung" chi hien khi dang chay — luc ranh no chi la mot nut chet
        #   tren thanh cong cu. ]]
        try:
            if busy:
                self.btn_cancel.pack(side="left", padx=(0, 6),
                                     before=self.btn_analyze)
            else:
                self.btn_cancel.pack_forget()
        except tk.TclError:
            pass
        has = bool(self.items) and not busy
        #[[ Nut Ghi o thanh cong cu (_build_ghi); Xuat CSV la muc trong menu
        #   "⋯" (tu khoa luc mo menu). Dung getattr vi _set_busy() co the chay
        #   TRUOC khi cac nut do dung xong — thieu no la app khong mo len duoc. ]]
        w = getattr(self, "btn_ghi3", None)
        if w is not None:
            w.configure(state="normal" if has else "disabled")
        #[[ NUT VANG = VIEC KE TIEP — nhu Evoto, moi luc dung mot nut chinh.
        #   Chua chon buoi: khong nut nao tren thanh vang (nut vang la "Chon thu
        #   muc buoi chup" giua luoi). Co anh, chua co ket qua: "1 · Phan tich"
        #   vang. Co ket qua: "2 · Ghi va day" vang, "Phan tich" lui ve phu. ]]
        co_kq = bool(self.items)
        co_anh = bool(getattr(self, "pairs", None))
        self.btn_analyze.configure(kieu="chinh" if (co_anh and not co_kq) else "phu")
        if w is not None:
            w.configure(kieu="chinh" if co_kq else "phu")
        self._hien_tien_do()

    def status(self, text: str, color: str = gd.MAU["chu"]):
        self.lbl_status.configure(text=text, foreground=color)

    def _invalidate_measurements(self):
        """Tuỳ chọn vừa đổi ảnh hưởng tới phép đo -> phải quét lại."""
        self._xuat_khoa = False
        try:
            self._nut_catalog()
        except Exception:                                    # noqa: BLE001
            pass
        if self.items:
            self.items = []
            self.measure_key = None
            self.tree.delete(*self.tree.get_children())
            self.status("Cách đo sáng đã đổi — bấm “1 · Phân tích” để quét lại.", gd.MAU["canh"])
        self._cap_nhat_luoi()
        self._set_busy(False)

    @staticmethod
    def _moc_dich(face: bool) -> str:
        """Mốc sáng đích theo cách đo: da mặt (face_target_ev) hay cả khung
        (target_ev) — hai thang khác nhau. Lấy từ at.DEFAULTS (gồm gu.json)."""
        return f"{float(at.DEFAULTS['face_target_ev' if face else 'target_ev']):.2f}"

    def _on_meter_change(self):
        # Mốc sáng của "khuôn mặt" và của "cả khung" là hai thang khác nhau —
        # giữ nguyên số cũ khi đổi cách đo là sai hẳn một quãng dài.
        face = dict(METERS).get(self.v_meter.get()) == "face"
        self.v_target.set(self._moc_dich(face))
        self.lbl_target.configure(text="Mặt sáng tới mức" if face
                                  else "Mức sáng đích")
        self._invalidate_measurements()

    def _on_mode_change(self):
        adv = self.mode_value() in ("absolute", "hybrid")
        for w in (self.lbl_target, self.sp_target):
            w.configure(state="normal" if adv else "disabled")
        blend = self.mode_value() == "hybrid"
        for w in (self.lbl_blend, self.sp_blend):
            w.configure(state="normal" if blend else "disabled")
        self.refresh_plan()

    # ------------------------------------------------------------- đọc tuỳ chọn
    def mode_value(self) -> str:
        return dict(MODES).get(self.v_mode.get(), "scene")

    def _num(self, var: tk.StringVar, default: float) -> float:
        try:
            return float(str(var.get()).replace(",", "."))
        except ValueError:
            var.set(f"{default:g}")
            return default

    def _soi_tach_canh(self):
        """Nói ngay hậu quả khi tắt cả hai luật tách cảnh. Xem chú thích ở trên."""
        if not hasattr(self, "lbl_canh_canh"):
            return
        if hasattr(self, "cb_gap_can_sig"):
            #[[ "Chi khi boi canh cung doi" chi co nghia khi CA HAI luat cung
            #   bat. Tat mot trong hai ma o tich nay van sang thi no hua mot
            #   viec khong xay ra.
            #]]
            self.cb_gap_can_sig.configure(
                state="normal" if (self.v_gap_on.get() and self.v_scenesig.get())
                else "disabled")
        if hasattr(self, "sp_gap"):
            #[[ O so phut vo nghia khi luat da tat. De no sang va bam duoc thi
            #   nguoi dung se chinh no roi cho ket qua doi — khong doi gi ca.
            #]]
            self.sp_gap.configure(state="normal" if self.v_gap_on.get()
                                  else "disabled")
        if self.v_gap_on.get() or self.v_scenesig.get():
            self.lbl_canh_canh.configure(text="")
            return
        if self.v_level.get():
            self.lbl_canh_canh.configure(
                text="⚠  Tắt cả hai luật tách cảnh → cả buổi là MỘT cảnh, mà "
                     "“Đồng bộ sáng + màu” đang bật sẽ san phẳng toàn bộ buổi về "
                     "một mốc — đúng bằng chế độ “Cân cả buổi về một mức”. "
                     "Tắt “Đồng bộ sáng + màu” nếu không định vậy.")
        else:
            self.lbl_canh_canh.configure(
                text="Tắt cả hai luật tách cảnh → cả buổi là một cảnh. "
                     "Không sao với chế độ “Đưa mặt về mức sáng chuẩn”, nhưng "
                     "“Cân trong từng cảnh” sẽ không còn cảnh nào để cân.")

    def read_cfg(self) -> dict:
        cfg = dict(at.DEFAULTS)
        cfg.update(mode=self.mode_value(),
                   meter=dict(METERS).get(self.v_meter.get(), "face"),
                   wb=dict(WBS).get(self.v_wb.get(), "skin"),
                   # 0 = tắt hẳn luật thời gian — xem group_scenes()
                   gap_minutes=(self._num(self.v_gap, 5.0)
                                if self.v_gap_on.get() else 0.0),
                   max_ev=self._num(self.v_maxev, 1.0),
                   exposure_gain=self._num(self.v_gain, 1.0),
                   **({"face_target_ev": self._num(
                       self.v_target, float(at.DEFAULTS["face_target_ev"]))}
                      if dict(METERS).get(self.v_meter.get()) == "face"
                      else {"target_ev": self._num(
                          self.v_target, float(at.DEFAULTS["target_ev"]))}),
                   blend=self._num(self.v_blend, 0.5),
                   highlights=self.v_hl.get(),
                   shadows=self.v_sh.get(),
                   lr_push=self.v_lrpush.get(),
                   curve=self.v_curve.get(),
                   grade=self.v_grade.get(),
                   burst=self.v_burst.get(),
                   # Hai cờ RIÊNG cho hai bộ lọc khác nhau — xem chú thích ở
                   # chỗ dựng hai ô tick.
                   blink=self.v_blink.get(),
                   upright=self.v_upright.get(),
                   scene_level=(at.DEFAULTS["scene_level"]
                                if self.v_level.get() else 0.0),
                   scene_sig_thresh=(at.DEFAULTS["scene_sig_thresh"]
                                     if self.v_scenesig.get() else 0.0),
                   scene_gap_can_sig=self.v_gap_can_sig.get(),
                   dong_bo_loat=self.v_dong_bo_loat.get(),
                   max_ev_up=self._num(self.v_maxup, 1.0),
                   #[[ Anh sang cua buoi — nguoi dung chon o khau 2.
                   #   Thieu dong nay thi o chon la mot cai nut khong noi vao
                   #   dau ca: bam thay doi nhung phan tich khong he doi. ]]
                   che_do_sang=self.v_che_do_sang.get(),
                   #[[ Bu sang ca buoi — o so la thu duoc tinh; hop "Loai buoi"
                   #   chi dien so vao do (xem _doi_loai_buoi). ]]
                   bu_sang_ca_buoi=self._num(self.v_bu_sang, 0.0),
                   loai_buoi=dict(LOAI_BUOI).get(self.v_loai_buoi.get(), "cuoi"),
                   source=self.source_value())
        return cfg

    def _doi_loai_buoi(self):
        """Chọn loại buổi -> điền số bù sáng tương ứng, tính lại kế hoạch.

        Không quét lại ảnh: bù sáng cộng vào delta cuối trong decide(), số đo
        giữ nguyên."""
        ma = dict(LOAI_BUOI).get(self.v_loai_buoi.get(), "cuoi")
        bu = (float(at.DEFAULTS.get("bu_sang_su_kien", 0.30)) if ma == "su_kien"
              else 0.0)
        self.v_bu_sang.set(f"{bu:.2f}")
        self.refresh_plan()

    def _doi_che_do_sang(self):
        """Đổi ánh sáng của buổi -> tính lại kế hoạch, KHÔNG quét lại ảnh.

        ngoai_troi() được gọi trong at.plan(), tức trên số đo đã có sẵn — nên
        chỉ cần refresh_plan(). Gọi _invalidate_measurements() ở đây là vứt cả
        lượt phân tích vừa mất hàng chục phút chỉ để đổi một ô chọn."""
        self.refresh_plan()

    def show_plugin_help(self):
        installed = at.LR_PLUGIN_DIR.is_dir()
        pending = len(list(at.LR_JOB_DIR.glob("*.tsv"))) if at.LR_JOB_DIR.is_dir() else 0
        done = len(list(at.LR_JOB_DIR.glob("*.done"))) if at.LR_JOB_DIR.is_dir() else 0
        state = (f"Plugin đã có sẵn tại:\n{at.LR_PLUGIN_DIR}\n\n"
                 f"Job đang chờ Lightroom xử lý: {pending}\n"
                 f"Job đã xử lý xong: {done}\n\n"
                 if installed else "KHÔNG tìm thấy thư mục plugin!\n\n")
        if done == 0 and pending > 0:
            state += ("Chưa job nào được xử lý — nhiều khả năng plugin chưa được thêm "
                      "vào Lightroom, hoặc Lightroom chưa mở.\n\n")
        messagebox.showinfo(
            "Plugin Lightroom — cài một lần",
            state +
            "Cách thêm vào Lightroom (chỉ làm 1 lần):\n"
            "   1. Mở Lightroom Classic\n"
            "   2. File → Plug-in Manager...\n"
            "   3. Bấm Add ở góc dưới bên trái\n"
            f"   4. Trỏ tới thư mục:\n      {at.LR_PLUGIN_DIR}\n"
            "   5. Bấm Done\n\n"
            "Xong rồi thì mỗi lần bấm “2 · Ghi và đẩy vào Lightroom”, Lightroom tự cập nhật "
            "thông số trong vài giây, không phải bấm gì thêm.\n\n"
            "Plugin chỉ sửa đúng 5 trường tone (Exposure, Highlights, Shadows, "
            "Temperature, Tint) và giữ nguyên mọi thứ khác của ảnh — an toàn hơn "
            "Read Metadata from File, vốn ghi đè toàn bộ chỉnh sửa trong catalog.\n\n"
            "Muốn tắt tự động: Library → Plug-in Extras → “AutoTone: bật/tắt tự động áp”.")
        if installed and messagebox.askyesno("Mở thư mục plugin?",
                                             "Mở thư mục plugin trong Explorer để tiện "
                                             "copy đường dẫn?"):
            open_in_explorer(at.LR_PLUGIN_DIR)

    def folder(self) -> Path | None:
        s = self.v_folder.get().strip().strip('"')
        if not s:
            return None
        p = Path(s)
        return p if p.is_dir() else None

    # ------------------------------------------------------------------ hành vi
    def pick_folder(self):
        d = filedialog.askdirectory(title="Chọn thư mục chứa ảnh RAW",
                                    initialdir=self.v_folder.get() or None)
        if d:
            self.v_folder.set(os.path.normpath(d))
            self.scan_folder()

    def scan_folder(self):
        root = self.folder()
        #[[ Doi buoi thi chu "Da ghi xong 34/34" cua buoi truoc khong con la
        #   chuyen cua buoi nay — xoa, thanh tien do an theo. ]]
        if not getattr(self, "busy", False) and getattr(self, "lbl_tien3", None) is not None:
            self.lbl_tien3.configure(text="")
            self.pb.configure(value=0)
            self._hien_tien_do()
        if not root:
            self.lbl_scan.configure(text="Chưa chọn thư mục hợp lệ", foreground=gd.MAU["mo"])
            return
        catalog = self.source_value() == "catalog"
        self.pairs, self.missing = at.collect_pairs(
            root, self.v_recursive.get(), need_sidecar=not catalog)
        n, m = len(self.pairs), len(self.missing)
        self.btn_fix.pack_forget()

        if not n and not m:
            self.lbl_scan.configure(text="Không tìm thấy file RAW nào ở đây.",
                                    foreground=gd.MAU["loi"])
        elif catalog:
            self._doc_xuat()
            #[[ 3/10: TU nho Lightroom xuat DUNG thu muc nay, khong cho nguoi
            #   dung vao menu. Lenh menu lay theo vung dang xem ben Lightroom —
            #   G:\1009 tren app, Lightroom dang mo G:\1005 -> ban xuat 1005 ->
            #   "khop 0 anh". Yeu cau theo THU MUC thi khong co cua lech do. ]]
            self._xin_xuat_nen()
            self._nhan_catalog()
        elif m:
            #[[ NOI LUON DUONG THOAT, DUNG CHI NOI LA HONG.
            #
            #   Ban cu chi bao "chi n/N anh co sidecar". Dung, nhung no de nguoi
            #   dung o ngo cut: ho khong biet rang co san mot che do KHONG CAN
            #   .xmp ngay trong o "Nguon" ngay tren dau. 11/9 tren may Mac da
            #   mat mot vong hoi dap chi vi cau nay khong noi ra.
            #
            #   Va cau thoat chi dung khi HAU HET anh thieu — thieu vai tam thi
            #   bam Ctrl+S ben Lightroom la xong, doi ca che do lam gi. ]]
            loi_ra = ("  →  Bấm nút buổi chụp ▾ (góc trên bên trái), chọn “Lightroom "
                      "catalog qua plugin” là không cần .xmp nữa."
                      if m > n else
                      "  →  Sang Lightroom chọn mấy ảnh đó rồi bấm Ctrl+S.")
            self.lbl_scan.configure(
                text=f"⚠ Chỉ {n}/{n + m} ảnh có sidecar .xmp — {m} ảnh còn lại "
                     f"sẽ bị bỏ qua.{loi_ra}  ",
                foreground=gd.MAU["loi"])
            self.btn_fix.configure(text="Cách tạo .xmp cho số còn lại",
                                   command=self.show_sidecar_help)
            self.btn_fix.pack(side="left")
        else:
            self.lbl_scan.configure(text=f"{n} ảnh RAW, đủ sidecar .xmp.",
                                    foreground=gd.MAU["xong"])
        self._invalidate_measurements()
        #[[ Dong trang thai lan gui (duoi nut Ghi) la cua BUOI — doi buoi thi
        #   doi theo, khong de no noi chuyen buoi truoc. Cot trai cung vay: doc
        #   lai ngay, khong doi toi nhip 4 giay. ]]
        self.refresh_job_state()
        self._lam_moi_ray()

    #[[ BAN XUAT TU LIGHTROOM PHAI DUOC DOC LAI, KHONG DOC MOT LAN ROI THOI.
    #
    #   Thu tu thao tac tu nhien cua nguoi dung la: mo app -> chon thu muc ->
    #   sang Lightroom xuat -> quay lai bam Phan tich. Ban cu doc ban xuat DUY
    #   NHAT mot lan, ngay luc chon thu muc — tuc luc chua he co ban xuat cho
    #   buoi nay. Va plugin thi "chi giu lai ban moi nhat cho do rac" (xem
    #   cleanupExports trong ExportForAutoTone.lua), nen cai app doc duoc la ban
    #   xuat cua BUOI TRUOC.
    #
    #   Hong that ngay 4/9: buoi G:\0608 co 96 anh, plugin xuat dung 96 dong
    #   dung duong dan G:\0608\... , the ma app bao "khop 0 anh". Ban xuat app
    #   dang cam trong tay la cua buoi 2905 hom truoc — khop 0 la dung, chi la
    #   no dang so voi nham file.
    #
    #   Nang hon ca cai nhan sai: at.plan() nhan chinh self.export nay, nen bam
    #   Phan tich la tinh tren ban xuat cu that su, chu khong phai chi hien sai.
    #
    #   Nen: doc lai o BA cho — luc quet thu muc, luc bam Phan tich (chac chan
    #   dung ban moi nhat), va mot dong ho nhe go cua moi 3 giay de cai nhan tu
    #   xanh len khi nguoi dung vua xuat xong ben Lightroom.
    #]]
    def _doc_xuat(self) -> bool:
        """Đọc lại bản xuất mới nhất CÓ ẢNH CỦA THƯ MỤC ĐANG CHỌN.
        -> True nếu đổi so với lần đọc trước.

        3/10: trước lấy "file mới nhất" bất kể của buổi nào — xem
        at.ban_xuat_cho_thu_muc()."""
        p = at.ban_xuat_cho_thu_muc(self.folder(), gom_con=bool(self.v_recursive.get()))
        dau = None
        if p is not None:
            try:
                dau = (str(p), p.stat().st_mtime_ns)
            except OSError:
                dau = (str(p), 0)
        if dau == getattr(self, "_dau_xuat", "chua-doc"):
            return False
        self._dau_xuat = dau
        self.export = at.read_catalog_export(p) if p is not None else {}
        return True

    def _file_xuat(self):
        """File mà self.export đọc ra (None nếu chưa có). at.plan() cần nó để
        chốt "bản xuất cũ hơn lần ghi" so đúng file — xem
        at.ban_xuat_cu_hon_lan_ghi()."""
        dau = getattr(self, "_dau_xuat", None)
        return Path(dau[0]) if isinstance(dau, tuple) and dau[0] else None

    def _dem_khop(self) -> int:
        #[[ Phai dung CHUNG mot ham chuan hoa voi ben ghi khoa (at._read_tsv),
        #   khong thi mot ben viet thuong mot ben khong va khop ra 0. ]]
        return sum(1 for p, _ in getattr(self, "pairs", [])
                   if at.khoa_duong_dan(p) in self.export)

    def _nhan_catalog(self):
        """Dòng trạng thái cho nguồn 'catalog'. Tách riêng để đồng hồ gọi được.

        #[[ NOI DUNG BENH CUA TUNG ANH THIEU (3/10). Truoc day moi anh khong co
        #   trong ban xuat deu la "se bi bo qua" — gop chung ba chuyen khac han:
        #     · anh 1 sao: plugin CO Y bo (quy uoc "1 sao khong xu ly") -> binh
        #       thuong, khong phai loi;
        #     · thu muc chua co trong catalog (chua import / da go) -> phai
        #       Import ben Lightroom;
        #     · dang doc nham ban xuat cua buoi khac -> nay khong con xay ra
        #       (ban_xuat_cho_thu_muc), nhung ban xuat lay tu MENU thi chi co
        #       anh dang chon / dang loc ben Lightroom.
        #   So anh 1 sao lay tu ketqua_xuat.txt cua plugin (at.ket_qua_xuat).
        #]]
        """
        n = len(getattr(self, "pairs", []))
        hit = self._dem_khop()
        self.btn_fix.pack_forget()
        # nut canh dong trang thai: o nguon catalog la "Anh nao thieu?"
        self.btn_fix.configure(text="Ảnh nào thiếu?", command=self._xem_anh_thieu)
        kq = self._kq_cua_thu_muc()
        cho, giay = self._dang_cho_xuat()
        #[[ 3/10: TACH "plugin khong chay" ra khoi "dang cho". Yeu cau con nam
        #   nguyen (plugin chua nhan) qua 6 giay ma nhip cua vong lap cu hon 30
        #   giay (hoac plugin ban cu chua co nhip) -> vong lap KHONG chay; cho
        #   tiep la vo ich, phai Reload. Plugin song thi nhan trong <= 2 giay. ]]
        nhip = at.plugin_nhip()
        chet = cho == "cho_nhan" and giay > 6 and (nhip is None or nhip > 30)
        if chet:
            dang_doc = ("   ⚠ Plugin trong Lightroom KHÔNG chạy"
                        + (f" (nhịp cuối {at.mo_ta_khoang(nhip)})" if nhip is not None else "")
                        + " — mở Lightroom, hoặc File › Plug-in Manager › AutoTone › "
                          "Reload Plug-in. Yêu cầu vẫn giữ: plugin chạy lại là xuất ngay.")
        elif cho == "dang_xuat":
            dang_doc = f"   ⏳ Lightroom đang đọc thư mục ({int(giay)}s)"
        elif cho:
            dang_doc = f"   ⏳ đang nhờ Lightroom đọc thư mục ({int(giay)}s)"
        else:
            dang_doc = ""
        if not self.export:
            if cho:
                self.lbl_scan.configure(text=f"{n} ảnh RAW ·{dang_doc}  ",
                                        foreground=gd.MAU["loi"] if chet else gd.MAU["canh"])
                return
            if kq.get("loi") == "khong-co-trong-catalog":
                self.lbl_scan.configure(
                    text=f"{n} ảnh RAW · Lightroom KHÔNG có ảnh nào của thư mục này — "
                         "chưa Import, hoặc đã gỡ khỏi catalog. Import thư mục vào "
                         "Lightroom rồi bấm “Đọc từ Lightroom”.  ",
                    foreground=gd.MAU["loi"])
                return
            if kq.get("loi") and kq.get("bo_sao"):
                self.lbl_scan.configure(
                    text=f"{n} ảnh RAW · cả {kq['bo_sao']} ảnh của thư mục trong Lightroom "
                         "đều 1 sao — theo quy ước không xử lý ảnh 1 sao.  ",
                    foreground=gd.MAU["canh"])
                return
            #[[ "CHUA co ban xuat" co hai nguyen nhan hoan toan khac nhau, va
            #   loi khuyen cho moi cai cung khac han:
            #     1. Nguoi dung chua chay lenh xuat cua plugin bao gio.
            #     2. Da chay roi, nhung Lightroom Add NHAM mot ban plugin khac,
            #        nen no ghi mot noi con app doc mot noi.
            #   Cai (2) khong bao loi o ben nao ca — Lightroom bao xuat thanh
            #   cong, app bao chua co. 11/9 tren may Mac dung la truong hop nay.
            #   Do duoc thi phai noi ra, dung de nguoi dung tu doan. ]]
            them = ""
            try:
                khac = at.plugin_khac()
                if khac:
                    them = (f"  ← nhưng có bản plugin KHÁC đã chạy: "
                            f"{khac[0][0]} — Lightroom có thể đang Add nhầm bản đó.")
            except Exception:                                # noqa: BLE001
                pass
            self.lbl_scan.configure(
                text=f"{n} ảnh RAW · CHƯA có bản xuất từ Lightroom cho thư mục này.{them}  ",
                foreground=gd.MAU["loi"])
            self.btn_fix.pack(side="left")
        elif hit < n:
            #[[ NOI RO DANG DOC FILE NAO, NO BAO NHIEU TUOI, VA O THU MUC NAO.
            #   Ngay 4/9 mat gan mot tieng chi vi khong in ten file ban xuat. ]]
            dau = getattr(self, "_dau_xuat", None)
            ten_bx = Path(dau[0]).name if dau else ""
            thieu = n - hit
            # so 1 sao chi tin khi ket qua plugin noi ve DUNG file dang doc
            bo_sao = min(thieu, int(kq.get("bo_sao") or 0)) if kq.get("file") == ten_bx else 0
            con = thieu - bo_sao
            phan = [f"{n} ảnh RAW · khớp {hit} ảnh từ catalog"]
            if bo_sao:
                phan.append(f"{bo_sao} ảnh 1 sao — không xử lý theo quy ước")
            if con:
                if kq.get("file") == ten_bx:
                    #[[ 3/10, G:\1009: 111/437 anh thieu chinh la 111 ban sao da co
                    #   trong catalog o G:\Test1009 — Lightroom bo qua luc Import vi
                    #   "Suspected Duplicates". Noi luon nguyen nhan hay gap nhat. ]]
                    phan.append(f"{con} ảnh CHƯA có trong thư mục này bên Lightroom "
                                "(chưa import, hoặc bị bỏ vì trùng ảnh ở thư mục khác) — "
                                "sẽ không được ghi; bấm “Ảnh nào thiếu?”")
                else:
                    phan.append(f"{con} ảnh không có trong bản xuất (bản xuất từ menu chỉ "
                                "lấy ảnh đang chọn / đang lọc bên Lightroom) — sẽ không "
                                "được ghi")
            them = ""
            if dau and con:
                tuoi = at.mo_ta_khoang(max(0.0, time.time() - dau[1] / 1e9))
                them = f"   ← đang đọc {ten_bx} ({tuoi}) trong {Path(dau[0]).parent}"
            self.lbl_scan.configure(text=" · ".join(phan) + "." + them + dang_doc + "  ",
                                    foreground=gd.MAU["loi"] if con else gd.MAU["xong"])
            if con:
                self.btn_fix.pack(side="left")
        else:
            self.lbl_scan.configure(
                text=f"{n} ảnh RAW · khớp đủ {hit} ảnh từ catalog Lightroom"
                     f"{self._moc_ban_xuat()}.{dang_doc}",
                foreground=gd.MAU["xong"])

    def _moc_ban_xuat(self) -> str:
        """“ · bản xuất 00:15 08/10” — bản catalog ĐANG DÙNG (8/10: sau khi phân
        tích nó đứng yên, nên phải nói rõ là bản lúc nào)."""
        p = self._file_xuat()
        try:
            return (" · bản xuất " + datetime.fromtimestamp(p.stat().st_mtime)
                    .strftime("%H:%M %d/%m")) if p is not None else ""
        except OSError:
            return ""

    def _xem_anh_thieu(self):
        """Nguồn catalog: ảnh nào có trên đĩa mà thư mục bên Lightroom không có,
        vì sao hay gặp, sửa thế nào."""
        root = self.folder()
        thieu = [Path(p).name for p, _ in getattr(self, "pairs", [])
                 if at.khoa_duong_dan(p) not in self.export]
        kq = self._kq_cua_thu_muc()
        if not self.export:
            dong = ["Chưa có bản xuất nào từ Lightroom cho thư mục này.", "",
                    "· Lightroom phải đang mở và plugin AutoTone đang chạy. Vừa cập nhật "
                    "plugin thì: File → Plug-in Manager → AutoTone → Reload Plug-in.",
                    "· App tự nhờ Lightroom đọc thư mục mỗi khi bạn chọn thư mục — bấm "
                    "nút buổi chụp ▾ → “Quét lại thư mục” để nhờ lại.",
                    "· Thư mục chưa từng Import vào Lightroom thì phải Import trước."]
        else:
            ten = Path(root).name if root else "thư mục này"
            dong = [f"{len(thieu)} ảnh có trên đĩa nhưng thư mục {ten} bên Lightroom KHÔNG có.", ""]
            if kq.get("bo_sao"):
                dong += [f"Trong đó có {kq['bo_sao']} ảnh 1 sao — plugin bỏ theo quy ước "
                         "(không xử lý ảnh 1 sao), không phải lỗi.", ""]
            dong += ["Hay gặp nhất khi dùng lại một buổi: chính các ảnh này ĐÃ có trong "
                     "catalog ở một thư mục khác (bản sao, thư mục thử...). Lúc Import, "
                     "Lightroom coi chúng là “Suspected Duplicates” và bỏ qua.", "",
                     "Cách sửa, trong Lightroom:",
                     f"   1. Chuột phải thư mục {ten} → Synchronize Folder…",
                     "   2. Tick “Show import dialog before importing” → Synchronize",
                     "   3. Trong hộp Import, cột phải mục File Handling: BỎ tick "
                     "“Don't Import Suspected Duplicates” → Import",
                     "      (hoặc gỡ thư mục bản sao khỏi catalog trước: chuột phải thư mục "
                     "đó → Remove)",
                     "   4. Quay lại đây, bấm nút buổi chụp ▾ → “Quét lại thư mục” — app tự đọc lại.", "",
                     "Ảnh thiếu:"]
            dong += ["   " + t for t in thieu[:300]]
            if len(thieu) > 300:
                dong.append(f"   ... và {len(thieu) - 300} ảnh nữa")
        LogWindow(self, dong, title="Ảnh không có trong Lightroom",
                  subtitle=str(root or ""))

    def _xin_xuat_nen(self):
        """Nhờ plugin xuất thông số của ĐÚNG thư mục đang chọn — không chờ, không
        khoá nút nào. Đồng hồ _soi_xuat cập nhật dòng trạng thái khi có kết quả."""
        root = self.folder()
        if not root or self.source_value() != "catalog":
            return
        try:
            at.request_export(root)
        except OSError:
            return
        self._yeu_cau_xuat = (at.khoa_duong_dan(root), time.time())

    def _kq_cua_thu_muc(self) -> dict:
        """Kết quả lần nhờ xuất GẦN NHẤT nếu nó là của thư mục đang chọn và không
        cũ hơn lần nhờ gần nhất của phiên này; {} nếu không."""
        root = self.folder()
        kq = at.ket_qua_xuat()
        if not root or not kq.get("thu_muc"):
            return {}
        if at.khoa_duong_dan(kq["thu_muc"]) != at.khoa_duong_dan(root):
            return {}
        yc = getattr(self, "_yeu_cau_xuat", None)
        if yc and yc[0] == at.khoa_duong_dan(root) and kq.get("khi", 0) < yc[1] - 1:
            return {}                     # cua lan nho TRUOC — lan nay chua tra loi
        return kq

    def _dang_cho_xuat(self) -> tuple:
        """(trạng thái, đã chờ bao nhiêu giây). Trạng thái: "" = không chờ gì,
        "cho_nhan" = file yêu cầu còn nằm đó (plugin chưa nhận),
        "dang_xuat" = plugin đã nhận, chưa có kết quả."""
        root = self.folder()
        yc = getattr(self, "_yeu_cau_xuat", None)
        if not root or not yc or yc[0] != at.khoa_duong_dan(root):
            return "", 0.0
        giay = max(0.0, time.time() - yc[1])
        if at.export_request_pending():
            return "cho_nhan", giay        # con nam do thi con cho, bao lau cung vay
        if giay > 120:
            return "", giay
        if (at.export_stamp(thu_muc=root) >= yc[1] - 1
                or at.ket_qua_xuat().get("khi", 0) >= yc[1] - 1):
            return "", giay
        return "dang_xuat", giay

    def _nut_catalog(self):
        """Hai nút catalog chỉ hiện khi ĐÃ PHÂN TÍCH với nguồn catalog."""
        co = bool(self.items) and self.source_value() == "catalog" and bool(self.folder())
        for b in (getattr(self, "btn_nap_catalog", None),
                  getattr(self, "btn_xoa_catalog", None)):
            if b is None:
                continue
            try:
                (b.pack if co else b.pack_forget)()
            except tk.TclError:
                pass

    def _tinh_lai_theo_ban_xuat(self, path=None):
        """Bản xuất vừa đổi (nạp lại / xoá) -> đọc lại, tính lại bảng, khoá lại."""
        self._xuat_khoa = False
        try:
            if self.items:
                self.refresh_plan()
            else:
                self._doc_xuat()
            self._nhan_catalog()
        finally:
            self._xuat_khoa = bool(self.items)
            self._nut_catalog()
            try:
                self.btn_nap_catalog.configure(state="normal")
            except Exception:                                # noqa: BLE001
                pass

    def do_nap_lai_catalog(self):
        """Nhờ Lightroom xuất lại thông số của buổi này, có rồi thì tính lại bảng."""
        if self._khoa_chan() or not self.folder():
            return
        self.btn_nap_catalog.configure(state="disabled")

        def xong(path):
            self._tinh_lai_theo_ban_xuat(path)
            khi = ""
            try:
                if path:
                    khi = datetime.fromtimestamp(Path(path).stat().st_mtime).strftime(
                        " (%H:%M %d/%m)")
            except OSError:
                pass
            self.status(f"Đã nạp lại catalog{khi} — bảng đã tính lại theo bản mới.",
                        gd.MAU["xong"])

        def that_bai(_ly_do=None):
            try:
                self.btn_nap_catalog.configure(state="normal")
            except Exception:                                # noqa: BLE001
                pass

        self.status("Đang nhờ Lightroom xuất lại catalog của buổi này…", gd.MAU["canh"])
        self._ask_lr_export(xong, that_bai=that_bai)

    def do_xoa_catalog_cu(self):
        """Xoá bản xuất catalog cũ của buổi này rồi nhờ Lightroom xuất bản mới."""
        f = self.folder()
        if not f:
            return
        p = self._file_xuat()
        khi = ""
        try:
            if p is not None:
                khi = datetime.fromtimestamp(p.stat().st_mtime).strftime(" lúc %H:%M %d/%m")
        except OSError:
            pass
        if not messagebox.askokcancel(
                "Xoá catalog cũ?",
                f"Xoá bản xuất catalog của buổi {f.name}{khi}.\n\n"
                "App sẽ nhờ Lightroom xuất bản mới ngay sau đó (Lightroom cần đang "
                "mở). Chưa có bản mới thì ảnh chưa ghi được.", parent=self):
            return
        n = at.xoa_ban_xuat(f)
        self.export = {}
        self._dau_xuat = None
        self._tinh_lai_theo_ban_xuat()
        self.status(f"Đã xoá {n} bản xuất cũ của buổi {f.name} — đang nhờ "
                    "Lightroom xuất bản mới…", gd.MAU["canh"])
        self.do_nap_lai_catalog()

    def _soi_xuat(self):
        """Mỗi 3 giây: có bản xuất mới thì cập nhật lại dòng trạng thái.

        CHỈ đổi cái nhãn, KHÔNG gọi scan_folder(). scan_folder() kết thúc bằng
        _invalidate_measurements(), tức xoá sạch bảng đo — người dùng đo xong
        220 ảnh rồi sang Lightroom xuất lại là mất trắng công đo. Danh sách file
        trong thư mục không đổi khi Lightroom xuất, nên cũng không cần quét lại.
        """
        try:
            if self.source_value() == "catalog" and getattr(self, "pairs", None):
                doi = (False if getattr(self, "_xuat_khoa", False)
                       else self._doc_xuat())
                cho, giay = self._dang_cho_xuat()
                tt = (at.ket_qua_xuat().get("khi"), cho, int(giay // 3) if cho else 0)
                if doi or tt != getattr(self, "_tt_xuat", None):
                    self._tt_xuat = tt
                    self._nhan_catalog()
                #[[ Ban xuat moi -> anh nao "khong ghi" doi theo; luoi chua phan
                #   tich phai ve lai (da phan tich thi bang so la cua lan do). ]]
                if doi and not self.items:
                    self._cap_nhat_luoi(giu_cuon=True)
        except Exception:                                    # noqa: BLE001
            pass
        self.after(3000, self._soi_xuat)

    def source_value(self) -> str:
        return dict(SOURCES).get(self.v_source.get(), NGUON_MAC_DINH)

    def _tai_mediapipe(self) -> bool:
        """Hoi tai mediapipe ngay tai cho. True = tai xong, dung duoc luon.

        Goi tu luong phan tich khi nguoi dung tick loc anh nham mat ma may
        chua co mediapipe. Khong tu tai: 53 MB la tien mang cua ho, phai hoi.
        """
        try:
            import tai_nguyen as tn
        except Exception:                                    # noqa: BLE001
            return False
        if tn.da_co(tn.GOI["mediapipe"]):
            return tn.nap("mediapipe")
        g = tn.GOI["mediapipe"]
        if not messagebox.askokcancel(
                "Tải mediapipe?",
                "Đã tick lọc ảnh mắt không dùng được, nhưng bản cài chưa "
                f"mang sẵn mediapipe ({g.mb} MB).\n\n"
                "Tải một lần, dùng mãi.\n\nTải bây giờ?",
                parent=self):
            return False
        d = TaiTaiNguyenDialog(self, tn, ["mediapipe"])
        self.wait_window(d)
        return tn.da_co(g) and tn.nap("mediapipe")

    def tai_gpu(self):
        """Tải bản torch CUDA (tăng tốc trên card NVIDIA) — TUỲ CHỌN.

        #[[ Ban cai da nhoi torch CPU: chay duoc moi may, du 8 tinh nang ngay.
        #   Day la ban NANG CAP cho may co card NVIDIA: tai torch CUDA ve, lan
        #   sau mo app tai_nguyen.nap("torch") chen no len dau sys.path -> torch
        #   CUDA thang torch CPU trong goi -> retouch chay tren card (nhanh hon
        #   nhieu). May khong co card thi khong can bam — torch CPU van chay.
        #
        #   Chi co nghia khi DA DONG GOI (co torch CPU san). Chay tu ma nguon
        #   thi torch la cua moi truong, khong lien quan. ]]
        """
        #[[ Dang tai NGAM (_bat_tai_gpu_ngam) thi khong mo them mot luot tai
        #   thu hai ghi vao CUNG thu muc — chi noi tien do o dau. ]]
        if getattr(self, "_gpu_tt", "") == "dang_tai":
            messagebox.showinfo(
                "Đang tải bản GPU",
                "App đang tự tải bản tăng tốc GPU ở nền. Xem tiến độ ở mô-đun "
                "Retouch — tải xong Retouch tự mở, không cần làm gì thêm.",
                parent=self)
            return
        try:
            import tai_nguyen as tn
        except Exception as ex:                              # noqa: BLE001
            messagebox.showerror(
                "Không có trình tải",
                f"Bản cài này thiếu phần tải tài nguyên ({type(ex).__name__}).",
                parent=self)
            return
        g = tn.GOI.get("torch")
        if g is None:
            messagebox.showinfo(
                "Không có bản GPU",
                "Bản cài này chưa khai gói tăng tốc GPU.", parent=self)
            return
        #[[ 6/10: ban cai da KEM SAN torch CUDA -> khong tai / khong "tai lai"
        #   (xoa thu muc torch dang nap la nguyen nhan loi PermissionError). ]]
        if getattr(tn, "co_kem", None) and tn.co_kem(g):
            messagebox.showinfo(
                "Đã có sẵn bản GPU",
                "Bản cài này đã KÈM SẴN bản tăng tốc GPU — không cần tải. "
                + ("App đang tự dùng card NVIDIA cho retouch."
                   if tn.co_card_nvidia() else
                   "Máy này không thấy card NVIDIA nên retouch chạy bằng CPU."),
                parent=self)
            return
        #[[ Da tai roi: bao da co, hoi co muon tai lai khong (vd ban loi). ]]
        if tn.da_co(g):
            if not messagebox.askyesno(
                    "Đã có bản GPU",
                    "Máy đã tải bản tăng tốc GPU rồi. App sẽ tự dùng nó khi có "
                    "card NVIDIA.\n\nTải lại (nếu bản cũ lỗi)?", parent=self):
                return
            #[[ Tai lai: xoa thu muc cu de tai_nguyen.tai() tai moi. ]]
            try:
                import shutil
                shutil.rmtree(tn.thu_muc_goi(g), ignore_errors=True)
            except Exception:                                # noqa: BLE001
                pass
        #[[ Kiem may CO card NVIDIA khong — chi de NHAC, khong chan: nguoi dung
        #   co the tai truoc roi cam card sau, hoac tai cho may khac. ]]
        nhac_cpu = ""
        try:
            import saytool.thiet_bi as _tb          # noqa: F401
            import torch as _t
            if not _t.cuda.is_available():
                #[[ torch CPU trong goi luon bao cuda khong co — nen doan them
                #   bang nvidia-smi de biet may co card that khong. ]]
                import shutil as _sh
                if not _sh.which("nvidia-smi"):
                    nhac_cpu = ("\n\nLƯU Ý: không thấy card NVIDIA trên máy này. "
                                "Bản GPU vẫn tải được nhưng retouch sẽ chạy bằng "
                                "CPU như hiện tại — chỉ tải nếu máy có card rời.")
        except Exception:                                    # noqa: BLE001
            pass
        if not messagebox.askokcancel(
                "Tải bản tăng tốc GPU?",
                f"Bản cài đã chạy đủ 8 tính năng bằng CPU. Bản tăng tốc GPU "
                f"({g.mb} MB) giúp máy có card NVIDIA chạy retouch nhanh hơn "
                f"nhiều.\n\nTải một lần, dùng mãi. Tải xong, lần mở app sau sẽ "
                f"tự dùng card.{nhac_cpu}\n\nTải bây giờ?", parent=self):
            return
        d = TaiTaiNguyenDialog(self, tn, ["torch"], gpu=True)
        self.wait_window(d)
        if tn.da_co(g):
            messagebox.showinfo(
                "Đã tải xong bản GPU",
                "Tải xong. Hãy ĐÓNG và MỞ LẠI app để dùng card NVIDIA cho "
                "retouch.", parent=self)

    def xoa_du_lieu_buoi(self):
        """Xoa moc goc + so ghi cu cua buoi dang chon, roi quet lai.

        Import lai mot buoi vao Lightroom roi xuat thong so, tool van nho lan
        chay truoc: no thay catalog khac cai minh da ghi, ket luan "nguoi dung
        sua tay" va bo qua gan het buoi. Nut nay xoa sach de lan chay sau coi
        buoi do la moi hoan toan.
        """
        d = (self.v_folder.get() or "").strip()
        if not d or not Path(d).is_dir():
            messagebox.showinfo("AutoTone", "Chua chon thu muc buoi chup.")
            return

        ten = Path(d).name

        #[[ HOI RIENG VE BAN XUAT, vi xoa no la bat nguoi dung xuat lai tu LR.
        #
        #   Nhung PHAI cho xoa duoc: neu ban xuat cu thieu anh (luc xuat chi
        #   chon mot phan catalog), thi giu no lai nghia la buoi chup tiep tuc
        #   bi bo qua dung nhung anh do — du da bam xoa du lieu.
        #
        #   Gap that 25/09: thu muc 3461 anh, ban xuat 851 dong. Bam xoa xong
        #   van bao "2610 anh se bi bo qua".
        #]]
        #[[ 3/10: dong nay tung goi at.ban_xuat_moi_nhat() — ham KHONG TON TAI.
        #   Bam nut la vang AttributeError ngay dong dau, Tkinter nuot loi: khong
        #   hoi, khong xoa gi. Nguoi dung bao "xoa du lieu chua giai quyet triet
        #   de" la dung theo nghia den. kiem_tham_chieu.py gio canh loai loi nay
        #   (goi ham / thuoc tinh khong ton tai) tren moi file. ]]
        bx = at.ban_xuat_cho_thu_muc(Path(d), gom_con=True)
        co_bx = bx is not None
        dong_bx = ""
        if co_bx:
            try:
                n = max(0, sum(1 for _ in bx.open(encoding="utf-8")) - 1)
                dong_bx = f"  . ban xuat tu Lightroom ({bx.name}, {n} anh)\n"
            except OSError:
                dong_bx = f"  . ban xuat tu Lightroom ({bx.name})\n"

        #[[ 3/10: GIU moc goc — xem at.xoa_du_lieu_buoi (xoa moc + anh chua Reset
        #   ben Lightroom = lan sau cong chong len so cu). ]]
        hoi = (
            "Xoa so ghi cua tool cho buoi \u201c" + ten + "\u201d?\n\n"
            "  . so ghi cac lan chay truoc\n"
            + dong_bx +
            "\nGIU moc goc (_autotone_baseline.tsv): lan chay toi tinh lai MOI anh tu "
            "gia tri TRUOC khi tool cham, nen khong bi cong chong du anh trong "
            "Lightroom con mang so cu.\n\n"
            "KHONG dung toi anh hay file .xmp.\n\n"
            "Sau khi xoa, khong con anh nao bi bo qua vi \u201cda sua tay\u201d \u2014 "
            "nghia la anh sua tay trong Lightroom cung se bi tinh lai va ghi de."
        )
        if not messagebox.askyesno("Xoa du lieu cu", hoi):
            return

        try:
            r = at.xoa_du_lieu_buoi(Path(d), ca_ban_xuat=True, xoa_moc=False)
        except Exception as ex:
            messagebox.showerror("AutoTone", "Khong xoa duoc:\n" + str(ex))
            return

        phan = []
        if r["baseline"]:
            phan.append("moc goc")
        if r["done"]:
            phan.append(str(r["done"]) + " so ghi")
        if r["job"]:
            phan.append(str(r["job"]) + " job cho")
        if r.get("ban_xuat"):
            phan.append(str(r["ban_xuat"]) + " ban xuat")
        msg = ("Da xoa: " + ", ".join(phan)) if phan else "Khong co gi de xoa."
        #[[ KHONG con bao nguoi dung vao Lightroom chon thu muc, Ctrl+A, chay menu:
        #   lenh menu lay theo vung dang xem / dang loc ben Lightroom, sai mot
        #   buoc la ban xuat thieu anh hoac cua buoi khac. App tu nho plugin xuat
        #   dung thu muc (scan_folder -> _xin_xuat_nen) ngay sau hop thoai nay. ]]
        if self.source_value() == "catalog":
            msg += ("\n\nApp dang tu nho Lightroom doc lai thu muc nay (Lightroom "
                    "phai dang mo).\nCho dong trang thai o khau 1 bao \u201ckhop\u201d.")
        if r["loi"]:
            msg += "\n\nKhong xoa duoc:\n" + "\n".join(r["loi"][:5])
        messagebox.showinfo("AutoTone", msg)
        self.scan_folder()

    def show_sidecar_help(self):
        if self.source_value() == "catalog":
            messagebox.showinfo(
                "Lấy thông số từ Lightroom",
                "Chưa có (hoặc chưa đủ) bản xuất từ catalog.\n\n"
                "Trong Lightroom Classic:\n"
                "   1. Vào Library, mở đúng thư mục buổi chụp\n"
                "   2. Ctrl+A chọn hết  (hoặc chỉ chọn số ảnh muốn xử lý)\n"
                "   3. Library → Plug-in Extras →\n"
                "      “AutoTone: xuất thông số cho autotone”\n"
                "   4. Chờ vài giây, thấy báo “Đã xuất...” thì quay lại đây\n"
                "   5. Bấm “1 · Phân tích”\n\n"
                "Cách này KHÔNG cần Ctrl+S. Ctrl+S phải ghi từng ấy file .xmp ra đĩa "
                "nên với thư mục vài nghìn ảnh sẽ rất lâu và trông như Lightroom bị "
                "treo — thật ra nó vẫn đang chạy.\n\n"
                "Chưa cài plugin? Bấm nút “Cài plugin...” bên dưới.")
            return
        n = len(self.missing)
        messagebox.showinfo(
            "Tạo sidecar .xmp cho ảnh còn thiếu",
            f"{n} ảnh chưa có file .xmp bên cạnh, nên autotone không đụng tới được.\n\n"
            "Sidecar phải do Lightroom ghi ra thì mới chứa đúng preset của bạn.\n\n"
            "Cách làm, trong Lightroom:\n"
            "   1. Vào Library, mở đúng thư mục này\n"
            "   2. Ctrl+A để chọn toàn bộ ảnh\n"
            "   3. Ctrl+S  (hoặc Metadata → Save Metadata to File)\n"
            "   4. Chờ thanh tiến trình chạy xong\n"
            "   5. Quay lại đây bấm “1 · Phân tích”\n\n"
            "Để lần sau không phải làm thủ công:\n"
            "   Edit → Catalog Settings → thẻ Metadata →\n"
            "   bật “Automatically write changes into XMP”.\n"
            "Từ đó Lightroom tự ghi .xmp mỗi khi bạn sửa ảnh.\n\n"
            "LƯU Ý VỀ TỐC ĐỘ: Adobe khuyến cáo bật tuỳ chọn này làm Lightroom\n"
            "chậm đi rõ rệt — mỗi lần sửa là một lần ghi file ra đĩa. Với thư\n"
            "mục vài nghìn ảnh thì nên TẮT nó và dùng nguồn “Lightroom catalog\n"
            "qua plugin” ở trên: không cần .xmp, không cần Ctrl+S, không cần\n"
            "Read Metadata from File.")

    def start_analyze(self, chuoi: bool = False):
        if self._khoa_chan():
            return
        #[[ Xoa co NGAY DAU. Bam "1 · Phan tich" mot minh la huy moi chuoi con
        #   treo tu lan truoc — khong bao gio ghi .xmp ma nguoi dung khong bao.
        #]]
        self.chuoi = False
        root = self.folder()
        if not root:
            messagebox.showinfo("Thiếu thư mục", "Chọn thư mục chứa ảnh RAW trước đã.")
            return
        self.scan_folder()
        if not self.pairs:
            return

        cfg = self.read_cfg()
        #[[ Tick loc mat ma chua co ear.csv thi NOI NGAY, dung im lang.
        #
        #   Bo loc mat doc EAR tu ear.csv do eye_ear.py sinh ra. Khong co file
        #   do thi pick_blinks() bo qua va chi in ra stderr — ma cua so nay
        #   khong hien stderr, nen nguoi dung tick xong thay khong loc duoc anh
        #   nao va tuong tinh nang hong.
        #
        #   Da mac dung loi nay mot lan trong du an: luat chon chu the mac dinh
        #   tat, nguoi dung chay lai roi tuong luat khong an. Im lang la loai
        #   loi tot nhieu cong nhat de tim.
        #]]
        if cfg.get("blink"):
            co_mp = True
            try:
                import mediapipe as _mp   # noqa: F401
            except Exception:             # noqa: BLE001
                co_mp = False
            #[[ BAN .EXE THI MOI TAI, KHONG BAO "pip install".
            #
            #   Trong ban dong goi khong co pip, khong co Python nao de cai
            #   vao — cau "pip install mediapipe" la mot ngo cut. Mediapipe
            #   lai la goi tai ve duoc (53 MB), nen mo dung cua so tai.
            #
            #   Chay tu ma nguon thi giu nguyen cau cu: luc do pip co that.
            #]]
            if not co_mp and getattr(sys, "frozen", False):
                co_mp = self._tai_mediapipe()
            if not co_mp and not (root / str(cfg.get("blink_csv", "ear.csv"))).is_file():
                messagebox.showwarning(
                    "Chưa cài mediapipe",
                    "Đã tick lọc ảnh mắt không dùng được, nhưng máy chưa có "
                    "mediapipe nên không đo được độ mở mắt.\n\n"
                    + ("Bấm Retouch → cửa sổ tải, tick “mediapipe”.\n\n"
                       if getattr(sys, "frozen", False) else
                       "Cài một lần:\n\n    pip install mediapipe==0.10.14\n\n")
                    + "Bây giờ tôi vẫn phân tích và CÂN SÁNG bình thường, chỉ "
                      "không lọc mắt.")
                cfg["blink"] = False
                self.v_blink.set(False)
        self.cancel_flag = False

        pairs = list(self.pairs)
        # Bớt tiến trình khi máy sắp hết RAM. Lightroom mở sẵn dễ chiếm hơn
        # 10 GB, chạy đủ 8 tiến trình lúc đó là MemoryError hàng loạt.
        jobs = 1 if len(pairs) < 12 else at.safe_jobs(min(8, (os.cpu_count() or 4)), cfg)

        self._set_busy(True)
        self.pb.configure(value=0, maximum=len(self.pairs))
        free = at.free_ram_mb() / 1024
        self.status(f"Đang đo {len(self.pairs)} ảnh · {jobs} tiến trình · "
                    f"RAM trống {free:.1f} GB")

        t_bat_dau = time.monotonic()

        def work():
            try:
                items, failed = at.analyze(
                    pairs, cfg, jobs,
                    progress=lambda d, t: self.q.put(("progress", (d, t))),
                    cancel=lambda: self.cancel_flag)
                #[[ Ghi thoi gian NGAY TAI DAY, o luong nen, truoc khi bao ve
                #   luong chinh. Ghi o cho khac thi phai nho truyen moc bat dau
                #   di qua hai lop, va mot ngay nao do se quen.
                #]]
                try:
                    import trang_thai as tt
                    tt.ghi_khau(tt.ten_buoi(root), "phan_tich",
                                time.monotonic() - t_bat_dau, so_anh=len(items))
                except Exception:                            # noqa: BLE001
                    pass                                     # do gio khong dang de hong ca luot chay
                self.q.put(("done", (items, failed, cfg, root)))
            except Exception:
                self.q.put(("error", traceback.format_exc()))

        #[[ Chi bat co khi luong nen DA khoi dong that. Truoc dong nay con bon
        #   duong ra som; dat co som hon thi ra som mot lan la co ket lai True,
        #   lan sau bam "1 · Phan tich" mot minh la TU GHI .xmp ma khong hoi ai.
        #   (Nut "Chay het" — noi duy nhat goi chuoi=True — da go 3/10; co van
        #   giu de duong ghi tu dong, neu co lai, khong phai dung lai tu dau.)
        #]]
        self.chuoi = chuoi
        threading.Thread(target=work, daemon=True).start()

    def _pump(self):
        """Nhận tin từ luồng nền — tkinter chỉ được đụng từ luồng chính."""
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "progress":
                    done, total = payload
                    self.pb.configure(value=done, maximum=max(total, 1))
                    self._tien_do_3(done, total, "Đang đo")
                    self.status(f"Đang đo {done}/{total} ảnh...")
                elif kind == "ghi_progress":
                    done, total = payload
                    self.pb.configure(value=done, maximum=max(total, 1))
                    self._tien_do_3(done, total, "Đang ghi")
                    self.status(f"Đang ghi {done}/{total} file .xmp...", gd.MAU["canh"])
                elif kind == "ghi_done":
                    self._ghi_xong(*payload)
                elif kind == "ghi_error":
                    self.chuoi = False
                    self._set_busy(False)
                    self.status("Lỗi khi ghi .xmp.", gd.MAU["loi"])
                    messagebox.showerror("Lỗi khi ghi", payload)
                elif kind == "done":
                    self._on_analyzed(*payload)
                elif kind == "error":
                    self.chuoi = False      # loi thi ngat chuoi, khong ghi tiep
                    self._set_busy(False)
                    self.status("Lỗi khi phân tích.", gd.MAU["loi"])
                    messagebox.showerror("Lỗi", payload)
        except queue.Empty:
            pass
        self.after(80, self._pump)

    def _on_analyzed(self, items, failed, cfg, root):
        self.items = items
        self.measure_key = (str(root), self.v_recursive.get(), cfg["meter"], cfg["preview_px"])
        self._set_busy(False)
        self.pb.configure(value=0)

        #[[ SO ANH DO HONG PHAI O LAI TREN MAN HINH, KHONG CHI TRONG HOP THOAI.
        #
        #   11/9 tren may Mac: tien do chay het 64/64 ma bang chi ra 1 anh. App
        #   CO hien hop thoai liet ke, nhung bam OK la mat, va sau do man hinh
        #   chi con dong "1 anh · 1 canh ..." — trong y het mot thu muc mot anh.
        #   Cau hoi "63 anh kia dau" khong con dau vet nao tra loi.
        #
        #   Nen: gom loi theo NOI DUNG (63 anh cung mot loi khac han 63 anh moi
        #   anh mot kieu), giu lai de _fill_table() in kem, va in nguyen van ra
        #   o Nhat ky de con chep di hoi.
        #]]
        self._do_hong = list(failed or [])
        if failed:
            nhom: dict = {}
            for f in failed:
                nhom.setdefault(str(f.get("error")), []).append(
                    Path(f["path"]).name)
            dong = []
            for k, ds in sorted(nhom.items(), key=lambda x: -len(x[1])):
                dong.append(f"· {len(ds)} ảnh: {k}")
                dong.append(f"      ví dụ: {', '.join(ds[:3])}")
            messagebox.showwarning(
                "Không đo được",
                f"{len(failed)}/{len(failed) + len(items)} ảnh bị bỏ qua:\n\n"
                + "\n".join(dong[:14])
                + "\n\nSố này cũng hiện ở thanh trạng thái dưới đáy cửa sổ.")
        if not items:
            self.chuoi = False
            self.status("Không đo được ảnh nào.", gd.MAU["loi"])
            return
        self._xuat_khoa = False             # lần tính đầu: đọc bản xuất mới nhất
        self.refresh_plan()
        self._xuat_khoa = True              # rồi đứng yên tới khi bấm “Nạp lại catalog”
        self._nut_catalog()
        if getattr(self, "chuoi", False):
            self.chuoi = False
            if self.cancel_flag:
                self.status("Đã dừng giữa chừng — chưa ghi gì cả.", gd.MAU["canh"])
            else:
                # after() de bang ve xong roi moi mo hop thoai ke tiep
                self.status("Chạy hết: đo xong, đang ghi .xmp...", gd.MAU["canh"])
                self.after(60, lambda: self.do_apply(hoi=False))
        if self.cancel_flag:   # sau refresh_plan, nếu không sẽ bị ghi đè
            self.status(f"Đã dừng — mới đo {len(items)}/{len(self.pairs)} ảnh, "
                        f"bảng dưới chỉ tính trên phần này.", gd.MAU["canh"])

    def refresh_plan(self):
        """Tính lại delta từ số đo có sẵn (không quét lại ảnh) và vẽ bảng."""
        if not self.items or self.busy:
            return
        self.cfg = self.read_cfg()
        #[[ Doc lai ban xuat NGAY TRUOC KHI TINH.
        #   Day moi la cho quan trong: at.plan() dung self.export de gan thong so
        #   preset goc. Doc lai o day thi du nguoi dung vua xuat ben Lightroom
        #   xong, phep tinh van an dung ban moi nhat — chu khong phai chi cai
        #   nhan tren man hinh moi dung.
        #]]
        #[[ 8/10: DA PHAN TICH thi ban xuat DUNG YEN (_xuat_khoa) — user: "khi da
        #   bam phan tich thi chi can them nut load lai Catalog moi hoac xoa
        #   Catalog cu". Truoc day moi lan doi tuy chon / moi 3 giay app lang le
        #   doc lai ban xuat moi nhat, bang so doi duoi tay nguoi dung. Lan tinh
        #   DAU sau khi do xong van doc ban moi nhat (_on_analyzed mo khoa). ]]
        if self.source_value() == "catalog" and not getattr(self, "_xuat_khoa", False) \
                and self._doc_xuat():
            self._nhan_catalog()
        at.plan(self.items, self.cfg, self.folder(), getattr(self, "export", {}),
                ban_xuat=self._file_xuat() if self.source_value() == "catalog" else None)
        self._fill_table()

    def _fill_table(self):
        self.tree.delete(*self.tree.get_children())
        for r in self.items:
            self.tree.insert("", "end", iid=r["path"], values=self._row(r),
                             tags=self._tags(r))
        n = len(self.items)
        nsc = len({r["scene"] for r in self.items})
        deltas = [r["delta_ev"] for r in self.items]
        changed = sum(1 for d in deltas if d)
        self._cap_nhat_luoi(giu_cuon=True)
        self.lbl_tong.configure(text=f"{n} ảnh · {nsc} cảnh · {changed} ảnh sẽ đổi")
        msg = (f"{n} ảnh · {nsc} cảnh · {changed} ảnh sẽ đổi · "
               f"ΔEV từ {min(deltas):+.2f} đến {max(deltas):+.2f} "
               f"(trung bình {sum(deltas)/n:+.2f})")
        #[[ Bang it anh hon thu muc thi PHAI noi ngay o day. Do la cau hoi dau
        #   tien nguoi dung dat ra, va cho nay la cho ho dang nhin. ]]
        hong = getattr(self, "_do_hong", [])
        if hong:
            msg += f" · {len(hong)} ảnh ĐO HỎNG, đã bỏ qua"
        # Bao ro vi sao bang it anh hon thu muc — xem danh_dau_nguoi_sua()
        if getattr(at, "SO_ANH_NGUOI_SUA", 0):
            msg += f" · bỏ qua {at.SO_ANH_NGUOI_SUA} ảnh anh đã sửa tay"
        ngoai = sum(1 for r in self.items if r.get("ngoai_xuat"))
        if ngoai:
            msg += f" · {ngoai} ảnh không có trong bản xuất Lightroom → không ghi"

        #[[ BAN XUAT CU HON LAN GHI — phai bao ngay, mau canh bao.
        #
        #   Ngay 7/9 buoi 2705: Lightroom khong chay nen app dung lai ban xuat
        #   cu (11:02), cu hon job da ghi luc 11:04. Buoc loc "anh sua tay" so
        #   nham va bo qua 2032/2087 anh, chi con 55 anh va ca 55 deu ra
        #   dEV +0.00 — nen khau 3 khong co gi de ghi. Nhin tu ngoai giong het
        #   "tool hong". Nay autotone tu tat buoc loc do va tra ve mot cau giai
        #   thich; cho nay la cho duy nhat nguoi dung nhin thay no.
        #]]
        canh_bao = getattr(at, "CANH_BAO_XUAT", "")
        if canh_bao:
            self.status(msg + " · " + canh_bao, gd.MAU["canh"])
            self.lbl_hint.configure(text="⚠ Số liệu catalog đang cũ — "
                                         "mở Lightroom rồi phân tích lại",
                                    foreground=gd.MAU["canh"])
            #[[ PHAI mo khoa giao dien truoc khi thoat som.
            #   Bo dong nay thi bam "Phan tich" xong ung dung ket o trang thai
            #   dang chay, moi nut deu mo — dung hong nang hon cai canh bao. ]]
            self._set_busy(False)
            return

        #[[ 3/10: preset bo trong Tone ma plugin trong Lightroom con ban cu (chua
        #   xuat cot WhiteBalance) -> autotone khong nhan ra quy trinh moi de tu
        #   ghi WB va Tone. Xem canh_bao_plugin_cu() trong autotone.py. Khong
        #   chan gi, chi noi — nhung noi bang mau canh bao, ngay cho dang nhin.
        #]]
        cb_plugin = getattr(at, "CANH_BAO_PLUGIN", "")
        if cb_plugin:
            self.status(msg + " · " + cb_plugin, gd.MAU["canh"])
            self.lbl_hint.configure(text="⚠ Plugin Lightroom là bản cũ — Reload plugin "
                                         "rồi phân tích lại",
                                    foreground=gd.MAU["canh"])
            self._set_busy(False)
            return

        # Cảnh chỉ có 1 ảnh thì chế độ "trong từng cảnh" không có gì để so
        alone = sum(1 for r in self.items if r["scene_size"] == 1)
        if self.cfg["mode"] == "scene" and alone >= max(2, n // 2):
            self.status(msg, gd.MAU["chu"])
            self.lbl_hint.configure(
                text=f"⚠ {alone}/{n} ảnh nằm một mình trong cảnh của nó nên không có gì "
                     f"để cân (ΔEV = 0). Tăng ô “Tách cảnh” lên, hoặc đổi Chế độ sang "
                     f"“Cân cả buổi về một mức”.", foreground=gd.MAU["canh"])
        else:
            self.status(msg)
            self.lbl_hint.configure(text=self._goi_y_sau_ghi(),
                                    foreground=gd.MAU["mo"])
        self._set_busy(False)

    def _goi_y_sau_ghi(self) -> str:
        """Câu nhắc ở đầu trang khi không có cảnh báo nào.

        Đẩy thẳng vào Lightroom (plugin) thì KHÔNG cần Read Metadata from File
        — nhắc câu đó lúc ấy là chỉ sai đường. Chỉ nhắc khi đã tắt đẩy thẳng."""
        v = getattr(self, "v_lrpush", None)
        if v is not None and v.get():
            return ""
        return ("Đẩy thẳng đang tắt — ghi xong sang Lightroom: Ctrl+A chọn hết → "
                "Metadata → Read Metadata from File")

    @staticmethod
    def _row(r):
        return (Path(r["path"]).name, r["scene"],
                r["dt_obj"].strftime("%H:%M:%S"),
                f"{r['delta_ev']:+.2f}",
                f"{r['new_exposure']:+.2f}",
                f"{r['new_highlights']:+d}",
                f"{r['new_shadows']:+d}",
                r["new_temp"] or "—",
                _curve_txt(r),
                #  8/10: hue/sat tool cong vao banh xe preset; "gốc" = tra ve so preset
                (f"{r['gr_hue']}/{r['gr_sat']}" if r.get("gr_ghi") and r.get("gr_sat")
                 else "gốc" if r.get("gr_ghi") else ""),
                f"{r['clip_after_pct']:.2f}",
                f"{r['shadow_after_pct']:.2f}",
                (f"{r.get('faces_n',0)}*" if r.get('subject_by')=='af'
                 else r.get('faces_n', 0)),
                _pick_txt(r),
                r.get("notes", ""))

    @staticmethod
    def _tags(r):
        if "LOI" in r.get("notes", ""):
            return ("err",)
        if r["clip_after_pct"] >= 3.0:
            return ("clip",)
        if abs(r["delta_ev"]) >= 0.5:
            return ("big",)
        if r["delta_ev"] == 0:
            return ("zero",)
        return ()

    def _sort_by(self, key):
        if not self.items:
            return
        col, rev = self._sort_state
        rev = not rev if col == key else False
        idx = [c[0] for c in COLS].index(key)

        def sort_key(r):
            v = self._row(r)[idx]
            try:
                return (0, float(str(v).replace("+", "")))
            except ValueError:
                return (1, str(v))

        self.items.sort(key=sort_key, reverse=rev)
        self._sort_state = (key, rev)
        self._fill_table()

    def _show_detail(self, _event):
        sel = self.tree.focus()
        r = next((x for x in self.items if x["path"] == sel), None)
        if not r:
            return
        lines = [
            f"{Path(r['path']).name}",
            f"Chụp lúc     : {r['dt_obj']:%Y-%m-%d %H:%M:%S}   ISO {r.get('iso', '?')}",
            f"Cảnh         : #{r['scene']}  ({r['scene_size']} ảnh)",
            "",
            f"Độ sáng đo   : {r['metered_ev']:+.2f} EV",
            f"Mức đích     : {r['target_ev']:+.2f} EV",
            f"→ ΔEV        : {r['delta_ev']:+.2f}",
            "",
            f"Exposure     : {r['old_exposure']:+.2f}  →  {r['new_exposure']:+.2f}",
            f"Highlights   : {r['old_highlights']:+d}  →  {r['new_highlights']:+d}",
            f"Shadows      : {r['old_shadows']:+d}  →  {r['new_shadows']:+d}",
            f"Temperature  : {r['old_temp']}  →  {r['new_temp']}",
            f"Tint         : {r['old_tint']:+d}  →  {r['new_tint']:+d}",
        ]
        if any(r.get(k) for k in ("cv_hl", "cv_lt", "cv_dk", "cv_sh")):
            lines += [
                "",
                "Parametric curve  (cộng thêm, KHÔNG đè curve của preset):",
                f"   Highlights : {r.get('cv_hl', 0):+d}",
                f"   Lights     : {r.get('cv_lt', 0):+d}",
                f"   Darks      : {r.get('cv_dk', 0):+d}",
                f"   Shadows    : {r.get('cv_sh', 0):+d}",
            ]
        if r.get("wb_trang_thai"):
            t_may, n_may = r["wb_trang_thai"]
            lines += ["", f"WB máy (preview): {t_may} / {n_may:+d} → tool cân trên màu da "
                          f"DỰ ĐOÁN trong Lightroom ở WB preset, không phải màu preview"]
        if r.get("gr_ghi"):
            m_, h_ = r.get("gr_mid"), r.get("gr_hi")
            lines += ["", "Color Grading  (tính theo màu da dự đoán trong Lightroom):"]
            if r.get("gr_sat"):
                lines.append(f"   Tool cộng thêm : hue {r['gr_hue']}  sat {r['gr_sat']}"
                             "  (vào cả Midtone lẫn Highlight của preset)")
            else:
                lines.append("   Trả về số gốc của preset (lần trước tool đã grade ảnh này)")
            if m_:
                lines.append(f"   Midtone        : hue {m_[0]}  sat {m_[1]}")
            if h_:
                lines.append(f"   Highlight      : hue {h_[0]}  sat {h_[1]}")
        lines += [
            "",
            f"Cháy sáng    : {r['clip_before_pct']:.2f}%  →  {r['clip_after_pct']:.2f}% (ước lượng)",
            f"Vùng sáng lớn: {r.get('bright_frac', 0) * 100:.1f}% (≥242/255 — áo trắng, tường sáng)",
            f"Bết tối      : {r['shadow_after_pct']:.2f}% (ước lượng)",
        ]

        # Ảnh đã đúng sáng thì autotone để nguyên. Không nói rõ thì nhìn
        # Before/After trong Lightroom sẽ tưởng là chưa nhận được thông số.
        d_exp = abs(r["new_exposure"] - r["old_exposure"])
        d_hl = abs(r["new_highlights"] - r["old_highlights"])
        d_sh = abs(r["new_shadows"] - r["old_shadows"])
        d_temp = abs((r.get("new_temp") or 0) - (r.get("old_temp") or 0))
        if d_exp < 0.05 and d_hl <= 3 and d_sh <= 3 and d_temp <= 100:
            lines += ["",
                      "Ảnh này gần như KHÔNG ĐỔI — autotone chấm là đã đúng sáng.",
                      "Nhìn Before/After trong Lightroom sẽ thấy y hệt nhau; đó là",
                      "đúng, không phải chưa nhận được thông số."]
        # Đã thực sự gửi sang Lightroom chưa — đọc từ file job, không phải đoán
        sent = at.sent_values(r["path"])
        if sent:
            jn, sv = sent
            lines += ["", f"Đã gửi sang Lightroom: {jn}",
                      "   " + "  ".join(f"{k.replace('2012', '')}={v}"
                                        for k, v in sv.items())]
        else:
            lines += ["", "CHƯA gửi sang Lightroom — bấm “2 · Ghi” để đẩy đi."]

        if r.get("subject_by") == "af":
            lines += ["", f"Chủ thể chọn theo ĐIỂM LẤY NÉT THẬT của máy",
                      f"   (bỏ {r.get('faces_bg_dropped',0)} mặt hậu cảnh trong "
                      f"{r.get('faces_found',0)} mặt tìm được)"]
        elif r.get("faces_bg_dropped"):
            lines += ["", f"Bỏ {r['faces_bg_dropped']} mặt hậu cảnh "
                      f"(suy đoán từ độ nét — ảnh không có điểm lấy nét)"]

        if r.get("notes"):
            lines += ["", f"Ghi chú      : {r['notes']}"]
        if r.get("rerun"):
            lines += ["", "Ảnh này đã chạy autotone trước đó — giá trị trên tính lại",
                      "từ preset gốc, không cộng dồn."]
        messagebox.showinfo("Chi tiết", "\n".join(lines))

    def do_cancel(self):
        self.cancel_flag = True
        # Ngat luon chuoi "Chay het" — dung roi thi khong duoc tu ghi tiep
        self.chuoi = False
        self.status("Đang dừng...", gd.MAU["canh"])

    def do_apply(self, hoi: bool = True):
        """hoi=False: đang chạy trong chuỗi “Chạy hết”, đã hỏi ở đầu rồi."""
        if self._khoa_chan():
            return
        if not self.items:
            return
        root = self.folder()
        if not root:
            return
        #[[ 3/10: anh KHONG co trong ban xuat Lightroom thi tool khong biet thong
        #   so hien tai cua no -> write_lr_job bo qua (xem at.attach_catalog_settings).
        #   Ca buoi deu ngoai ban xuat thi dung han o day, noi ro — dung de nguoi
        #   dung tuong da ghi xong. ]]
        ngoai = sum(1 for r in self.items if r.get("ngoai_xuat"))
        if self.cfg.get("source") == "catalog" and ngoai and ngoai == len(self.items):
            messagebox.showwarning(
                "Chưa có thông số từ Lightroom",
                f"Không ảnh nào trong {len(self.items)} ảnh có trong bản xuất từ "
                "Lightroom, nên tool KHÔNG ghi gì cả — nó không biết thông số hiện "
                "tại của chúng.\n\nXem dải báo phía trên lưới ảnh để biết vì sao "
                "(thư mục chưa import vào Lightroom, Lightroom chưa mở...), sửa xong "
                "thì bấm “Đọc từ Lightroom” rồi phân tích lại.")
            return
        n = sum(1 for r in self.items
                if r.get("delta_ev") or r.get("hl_adj") or r.get("sh_adj"))
        #[[ 8/10 (buoi ky yeu raw 19.4, "ghi vao Lightroom lan 2 khong hoat dong"):
        #   nguon catalog van hien hop thoai CUA SIDECAR — "Se ghi 1089 file .xmp
        #   ... Read Metadata from File ... GHI DE moi chinh sua ... Tiep tuc?" —
        #   sai viec (khong ghi .xmp nao, khong can Read Metadata) va de doa dung
        #   cho nguoi dung bam Huy o lan hai. Lai khong co parent: hop co the nam
        #   sau cua so chinh, bam nut Ghi nhu khong co gi xay ra. ]]
        if self.cfg.get("source") == "catalog":
            gui = sum(1 for r in self.items
                      if "new_exposure" in r and not r.get("ngoai_xuat"))
            n_gr = sum(1 for r in self.items if r.get("gr_ghi") and r.get("gr_sat"))
            ok = True if not hoi else messagebox.askokcancel(
                "Gửi vào Lightroom",
                f"Gửi {gui} ảnh vào Lightroom ({n} ảnh đổi sáng"
                + (f", {n_gr} ảnh Color Grading trắng hồng" if n_gr else "") + ").\n\n"
                "Plugin áp thẳng vào catalog — KHÔNG cần Read Metadata from File. "
                "Mốc gốc giữ trong _autotone_baseline.tsv: gửi lại bao nhiêu lần "
                "cũng tính từ preset gốc, không cộng dồn."
                + (f"\n\n{ngoai} ảnh không có trong bản xuất từ Lightroom → KHÔNG gửi."
                   if ngoai else "")
                + "\n\nGửi?",
                icon="question", parent=self)
        else:
            ok = True if not hoi else messagebox.askokcancel(
                "Ghi vào sidecar .xmp",
                f"Sẽ ghi {len(self.items)} file .xmp ({n} ảnh có thay đổi).\n\n"
                "Bản gốc được backup tự động, hoàn tác được bằng nút “Hoàn tác...”.\n\n"
                "LƯU Ý: bước tiếp theo trong Lightroom là\n"
                "Metadata → Read Metadata from File, và thao tác đó GHI ĐÈ\n"
                "mọi chỉnh sửa đang có trong catalog của những ảnh này.\n"
                "Hãy chạy trước khi retouch tay."
                + "\n\nTiếp tục?",
                icon="warning", parent=self)
        if not ok:
            self.status("Đã huỷ — chưa gửi gì.", gd.MAU["mo"])
            return
        #[[ GHI O LUONG NEN.
        #
        #   write_sidecars() ghi mot file .xmp cho MOI anh. Voi buoi 1000 anh la
        #   hang chuc giay, va truoc day no chay thang tren luong giao dien: ca
        #   cua so dung im, khong thanh tien do, khong biet la dang chay hay da
        #   treo. Nguoi dung bao dung cau do — "bam Ghi xong khong thay loading".
        #
        #   Chuyen sang luong nen + hang doi self.q, dung y het buoc Phan tich.
        #]]
        at.LAST_JOB = None
        self._set_busy(True)
        self.pb.configure(value=0, maximum=max(len(self.items), 1))
        self.status("Đang gửi vào Lightroom..." if self.cfg.get("source") == "catalog"
                    else f"Đang ghi 0/{len(self.items)} file .xmp...", gd.MAU["canh"])
        self.lbl_job.configure(text="", foreground=gd.MAU["mo"])

        items, cfg = self.items, self.cfg

        def work():
            t0 = time.monotonic()
            try:
                bk = at.write_sidecars(
                    items, cfg, root,
                    progress=lambda d, t: self.q.put(("ghi_progress", (d, t))))
                self.q.put(("ghi_done", (bk, time.monotonic() - t0, root, hoi)))
            except Exception:                                # noqa: BLE001
                self.q.put(("ghi_error", traceback.format_exc()))

        threading.Thread(target=work, daemon=True).start()

    def _ghi_xong(self, backup, giay: float, root, hoi: bool):
        """Chạy trên luồng chính sau khi ghi .xmp xong."""
        self.last_backup = backup
        self._set_busy(False)
        self.pb.configure(value=0)
        #[[ Khong dua thanh khau 3 ve 0: de nguyen "xong N/N" lam bang chung da
        #   chay xong. Dua ve 0 thi man hinh lai trong tron y het luc chua bam —
        #   dung cai da lam nguoi dung tuong khong co gi chay. ]]
        self._tien_do_3(len(self.items), max(len(self.items), 1), "Đã ghi")
        #[[ Do CA khau ghi. Cong kiem giai doan 4 doi tong thoi gian tung khau;
        #   thieu mot khau thi con so tong khong so duoc voi cach lam cu.
        #   Ghi ngay sau write_sidecars, TRUOC phan cho plugin — cho plugin la
        #   thoi gian cua Lightroom, khong phai cua tool.
        #]]
        try:
            import trang_thai as tt
            tt.ghi_khau(tt.ten_buoi(root), "day", giay, so_anh=len(self.items))
        except Exception:                                    # noqa: BLE001
            pass
        self._fill_table()
        catalog = self.cfg.get("source") == "catalog"
        job = at.LAST_JOB
        if job:
            self._watch_job(job)
        else:
            self.lbl_job.configure(
                text=("⚠ Không có ảnh nào để gửi — xem cột ghi chú trong bảng." if catalog
                      else "(không gửi job nào sang Lightroom — xem ô “Đẩy thẳng vào Lightroom”)"),
                foreground=gd.MAU["loi"] if catalog else gd.MAU["mo"])
        if catalog:
            #[[ 8/10: nguon catalog khong ghi .xmp nao — "Da ghi 1089 sidecar ·
            #   backup: _autotone_baseline.tsv" la noi sai viec vua lam. ]]
            self.status(f"Đã gửi {Path(job).name} vào Lightroom — chờ plugin áp."
                        if job else "Không gửi gì — không ảnh nào có thông số để ghi.",
                        gd.MAU["xong"] if job else gd.MAU["loi"])
        else:
            self.status(f"Đã ghi {len(self.items)} sidecar · backup: {self.last_backup.name}",
                        gd.MAU["xong"])
        #[[ NOI RO PHAI LAM GI, VA NHAT LA CAI BAY "DOC CHUA XONG".
        #
        #   Nguoi dung bao: sang Develop scroll thi co anh khong nhan thong so
        #   moi. Hai nguyen nhan, deu im lang:
        #     1. Read Metadata from File chi ap len anh DANG CHON. Chon vai tam
        #        roi bam thi may tam kia khong duoc doc, va Lightroom khong noi.
        #     2. Read Metadata chay NGAM. Scroll sang Develop truoc khi no xong
        #        thi anh chua toi luot van hien thong so cu.
        #
        #   Va quan trong nhat: dung plugin thi KHONG CAN Read Metadata. Cau cu
        #   noi "khong dung plugin thi lam tay" de nguoi doc tuong lam ca hai
        #   cung duoc — ma lam ca hai la thua, va lan hai co the ghi de lan mot.
        #]]
        if self.cfg.get("lr_push"):
            nxt = ("KHÔNG cần Metadata → Read Metadata from File.\n"
                   "Plugin áp thẳng vào catalog; dòng trạng thái cạnh nút Ghi sẽ báo\n"
                   "“đã áp xong, kiểm chứng đủ” khi Lightroom nhận đủ.\n\n"
                   "Chờ dòng đó xanh rồi hãy sang Develop.")
        else:
            nxt = ("Sang Lightroom: Ctrl+A chọn HẾT ảnh trong thư mục →\n"
                   "Metadata → Read Metadata from File.\n\n"
                   "Hai chỗ hay sót:\n"
                   "· Chỉ chọn vài tấm thì những tấm còn lại KHÔNG được đọc.\n"
                   "· Lightroom đọc ngầm — chờ thanh tiến độ góc trái chạy xong\n"
                   "  rồi mới sang Develop, không thì ảnh chưa tới lượt vẫn\n"
                   "  hiện thông số cũ.")
        if not hoi:
            loat = sum(1 for r in self.items if r.get("cull") == "loat")
            mat = sum(1 for r in self.items if r.get("cull") == "nham-mat")
            n_doi = sum(1 for r in self.items
                        if r.get("delta_ev") or r.get("hl_adj") or r.get("sh_adj"))
            dong = [f"{len(self.items)} ảnh đã cân sáng ({n_doi} ảnh có thay đổi)."]
            ngoai = sum(1 for r in self.items if r.get("ngoai_xuat"))
            if ngoai:
                dong.append(f"{ngoai} ảnh không có trong bản xuất từ Lightroom → "
                            f"KHÔNG ghi (xem dải báo phía trên lưới ảnh)")
            if getattr(at, "SO_ANH_NGUOI_SUA", 0):
                dong.append(f"{at.SO_ANH_NGUOI_SUA} ảnh anh đã sửa tay → giữ nguyên, "
                            f"không ghi đè")
            if loat:
                dong.append(f"{loat} ảnh trùng khung → 1 sao")
            if mat:
                dong.append(f"{mat} ảnh mắt không dùng được → 1 sao")
            if not catalog:
                dong.append(f"\nBackup .xmp: {self.last_backup.name}")
            dong.append(f"\n{nxt}")
            messagebox.showinfo("Chạy hết — xong", "\n".join(dong), parent=self)
            return
        if catalog:
            #[[ Nguon catalog: khong co backup .xmp de mo. Dong trang thai canh nut
            #   Ghi tu bao "da ap xong, kiem chung du" — khong can them hop nao. ]]
            return
        if messagebox.askyesno(
                "Xong",
                f"Đã ghi {len(self.items)} file .xmp.\n"
                f"Backup: {self.last_backup}\n\n{nxt}\n\nMở thư mục backup?",
                parent=self):
            open_in_explorer(self.last_backup)

    # ------------------------------------------------- theo dõi job Lightroom
    def _watch_job(self, job, tries: int = 0):
        """Theo dõi job tới khi plugin đổi đuôi thành .done.

        Không chặn giao diện: mỗi giây kiểm tra một lần bằng self.after()."""
        if tries == 0:
            self._job_dang_theo = job          # refresh_job_state() hỏi cái này
        st = at.job_state(job)

        if st == "xong":
            #[[ Không tin bộ đếm của plugin, đọc kết quả KIỂM CHỨNG.
            #   Plugin áp xong thì đọc lại từng ảnh TỪ CATALOG và đối chiếu; ảnh
            #   nào chưa nhận đúng thì tên nằm trong verify_*.tsv. Nhờ vậy câu
            #   "toàn bộ ảnh đã có setting mới chưa" trả lời được bằng dữ liệu,
            #   không phải bằng niềm tin.
            #]]
            bad = at.job_unverified(job)
            res = at.job_result(job)
            if bad:
                self.lbl_job.configure(
                    text=f"⚠ Áp xong nhưng {len(bad)} ảnh CHƯA nhận đúng — "
                         f"bấm để xem danh sách.",
                    foreground=gd.MAU["loi"])
                self.lbl_job.bind("<Button-1>", lambda _e: self._show_unverified(bad))
            else:
                self.lbl_job.unbind("<Button-1>")
                self.lbl_job.configure(
                    text=f"✓ Lightroom đã áp xong, kiểm chứng đủ · "
                         f"{res or Path(job).name}",
                    foreground=gd.MAU["xong"])
            return

        if st == "mat":
            self.lbl_job.configure(text="✓ Lightroom đã nhận job.", foreground=gd.MAU["xong"])
            return

        if st == "dang":
            # Plugin da gianh duoc job (doi ten thanh .running) va dang ap
            self.lbl_job.configure(
                text=f"⚙ Lightroom đang áp {Path(job).name}... ({tries}s)",
                foreground=gd.MAU["canh"])
            self.after(1000, lambda: self._watch_job(job, tries + 1))
            return

        if tries >= LR_JOB_TIMEOUT:
            self.lbl_job.configure(
                text=f"⚠ Plugin chưa xử lý sau {LR_JOB_TIMEOUT}s — job vẫn nằm chờ, "
                     f"không mất đi đâu.", foreground=gd.MAU["loi"])
            return

        self.lbl_job.configure(
            text=f"⏳ Đã gửi {Path(job).name} — đang chờ Lightroom áp... ({tries}s)",
            foreground=gd.MAU["canh"])
        self.after(1000, lambda: self._watch_job(job, tries + 1))

    def _show_unverified(self, bad):
        """Danh sách ảnh plugin đọc lại mà thấy chưa nhận đúng thông số."""
        khong_co = [p for p, why in bad if why.startswith("khong-co")]
        chua_nhan = [(p, why) for p, why in bad if not why.startswith("khong-co")]
        lines = []
        if khong_co:
            lines += [f"{len(khong_co)} ảnh KHÔNG CÓ trong catalog Lightroom",
                      "(chưa import, hoặc đã đổi tên/chuyển chỗ sau khi import):", ""]
            lines += ["   " + Path(p).name for p in khong_co[:40]]
            if len(khong_co) > 40:
                lines.append(f"   ... và {len(khong_co) - 40} ảnh nữa")
            lines += ["", "Cách sửa: trong Lightroom bấm chuột phải lên thư mục →",
                      "Synchronize Folder... để import số ảnh còn thiếu, rồi chạy lại.", ""]
        if chua_nhan:
            lines += [f"{len(chua_nhan)} ảnh CÓ trong catalog nhưng đọc lại vẫn chưa "
                      "đúng thông số:", ""]
            lines += [f"   {Path(p).name}  ({why})" for p, why in chua_nhan[:40]]
            if len(chua_nhan) > 40:
                lines.append(f"   ... và {len(chua_nhan) - 40} ảnh nữa")
            lines += ["", "Thường là ảnh đang mở trong Develop hoặc bị khoá.",
                      "Bấm “2 · Ghi” lần nữa là plugin áp lại đúng mấy ảnh này —",
                      "ảnh đã đúng sẽ được bỏ qua nên rất nhanh."]
        LogWindow(self, lines, title="Ảnh chưa nhận thông số",
                  subtitle="Kết quả plugin đọc lại TỪ CATALOG sau khi áp")

    # ------------------------------------------- điều khiển Lightroom từ app
    def _ask_lr_export(self, done, tries: int = 0, before: float | None = None,
                       that_bai=None):
        """Nhờ plugin xuất thông số rồi chờ. Không chặn giao diện.

        Chờ bằng cách nhìn MỐC THỜI GIAN của bản xuất mới nhất, chứ không nhìn
        file yêu cầu biến mất — plugin xoá file yêu cầu NGAY khi nhận, còn phần
        xuất thì mất thêm vài chục giây với thư mục lớn."""
        root = self.folder()
        if before is None:
            if not root:
                return
            before = at.export_stamp(thu_muc=root)
            try:
                at.request_export(root)
            except OSError as ex:
                messagebox.showerror("Không gửi được yêu cầu", str(ex))
                return
            self._yeu_cau_xuat = (at.khoa_duong_dan(root), time.time())
            self.lbl_job.unbind("<Button-1>")
            #[[ Tat CA BA nut cung goi _ask_lr_export.
            #   Bo sot btn_gu thi moi lan bam lai sinh them mot vong cho rieng
            #   (self.after lap lai moi giay) va them mot lan ghi request_export.
            #   Nguoi dung bam hai lan -> hai vong, hai lan thu goi duyet.
            #]]
            self.btn_read.configure(state="disabled")
            self.btn_learn.configure(state="disabled")
            self._nut_gu("disabled")

        #[[ Chi tinh la "da tra loi" khi co ban xuat MOI CUA THU MUC NAY — ban
        #   xuat cua buoi khac (bam menu ben Lightroom) khong phai cau tra loi. ]]
        if at.export_stamp(thu_muc=root) > before:
            self.btn_read.configure(state="normal")
            self.btn_learn.configure(state="normal")
            self._nut_gu("normal")
            done(at.ban_xuat_cho_thu_muc(root))
            return

        #[[ Plugin da tra loi la KHONG xuat duoc (thu muc khong co trong catalog,
        #   moi anh deu 1 sao...) -> dung ngay, noi dung benh. Truoc day doi du
        #   LR_JOB_TIMEOUT giay roi bao "plugin chua xuat xong" — sai benh. ]]
        kq = self._kq_cua_thu_muc()
        if kq.get("loi") and not at.export_request_pending():
            self.btn_read.configure(state="normal")
            self.btn_learn.configure(state="normal")
            self._nut_gu("normal")
            if kq["loi"] == "khong-co-trong-catalog":
                ly_do = ("Lightroom KHÔNG có ảnh nào của thư mục này — chưa Import, hoặc "
                         "đã gỡ khỏi catalog. Import thư mục vào Lightroom rồi bấm lại.")
            else:
                ly_do = "Lightroom không xuất được: " + str(kq["loi"])
            self.lbl_job.configure(text="⚠ " + ly_do, foreground=gd.MAU["loi"])
            self._nhan_catalog()
            if that_bai:
                that_bai(ly_do)
            return

        if tries >= LR_JOB_TIMEOUT:
            self.btn_read.configure(state="normal")
            self.btn_learn.configure(state="normal")
            self._nut_gu("normal")
            #[[ Nói đúng bệnh thay vì "kiểm tra plugin đã cài chưa".
            #   File yêu cầu còn nằm đó nghĩa là plugin KHÔNG nhận được — gần
            #   như luôn là do Lightroom đang giữ bản plugin cũ trong bộ nhớ.
            #   Sửa file trên đĩa không đủ, phải thoát hẳn Lightroom. ]]
            lau = at.plugin_song_khi_nao()
            khi = at.mo_ta_khoang(lau)
            #[[ HAI BENH KHAC NHAU, hai cach chua nguoc nhau — xem chu thich o
            #   at.plugin_song_khi_nao(). Ban truoc luon khuyen "thoat han
            #   Lightroom roi mo lai", ke ca khi Lightroom khong he mo: nhat ky
            #   dung tu hom truoc thi khong co gi de thoat.
            #]]
            chet_han = lau is None or lau > 900
            if at.export_request_pending():
                if chet_han:
                    tom = ("⚠ Plugin không chạy — nhật ký ghi lần cuối "
                           f"{khi}. Lightroom có đang mở không?")
                    chi_tiet = (
                        "File yêu cầu vẫn nằm nguyên trong thư mục job, và nhật ký "
                        f"plugin ghi lần cuối {khi}.\n\n"
                        "Nhật ký cũ như vậy nghĩa là vòng lặp nền của plugin KHÔNG "
                        "chạy — gần như luôn là do Lightroom không mở, hoặc mở rồi "
                        "nhưng plugin chưa nạp.\n\n"
                        "Cách xử lý:\n"
                        "   1. Mở Lightroom Classic lên\n"
                        "   2. Chờ khoảng 10 giây cho plugin nạp\n"
                        "   3. Bấm lại nút này\n\n"
                        "Nếu Lightroom ĐANG mở sẵn mà nhật ký vẫn cũ: vào File → "
                        "Plug-in Manager, chọn AutoTone, bấm Reload. Không thấy "
                        "plugin trong danh sách thì nó chưa được thêm vào.\n\n"
                        f"Thư mục job:\n{at.LR_JOB_DIR}")
                else:
                    tom = ("⚠ Plugin đang chạy bản cũ — hãy THOÁT HẲN Lightroom "
                           "rồi mở lại (bấm để xem chi tiết).")
                    chi_tiet = (
                        "File yêu cầu vẫn nằm nguyên trong thư mục job, nhưng nhật "
                        f"ký plugin có ghi {khi} — tức plugin CÓ chạy, chỉ là không "
                        "thấy file yêu cầu.\n\n"
                        "Nguyên nhân hay gặp nhất: Lightroom đang giữ BẢN PLUGIN CŨ "
                        "trong bộ nhớ. Ghi đè file trên đĩa không đủ — Lightroom chỉ "
                        "nạp lại code khi khởi động.\n\n"
                        "Cách xử lý:\n"
                        "   1. Thoát hẳn Lightroom (không phải chỉ đóng cửa sổ)\n"
                        "   2. Mở lại, chờ khoảng 10 giây\n"
                        "   3. Bấm lại nút này\n\n"
                        f"Thư mục job:\n{at.LR_JOB_DIR}")
                self.lbl_job.configure(text=tom, foreground=gd.MAU["loi"])
                self.lbl_job.bind("<Button-1>", lambda _e: messagebox.showinfo(
                    "Plugin chưa nhận yêu cầu", chi_tiet))
                if that_bai:
                    that_bai(chi_tiet)
                    return
            else:
                self.lbl_job.configure(
                    text=f"⚠ Plugin đã nhận nhưng chưa xuất xong sau "
                         f"{LR_JOB_TIMEOUT}s — xem “Nhật ký plugin”.",
                    foreground=gd.MAU["loi"])
                if that_bai:
                    that_bai(f"Plugin đã nhận yêu cầu nhưng chưa xuất xong sau "
                             f"{LR_JOB_TIMEOUT} giây.")
            return

        self.lbl_job.configure(
            text=f"⏳ Đang nhờ Lightroom đọc thư mục... ({tries}s)",
            foreground=gd.MAU["canh"])
        self.after(1000, lambda: self._ask_lr_export(done, tries + 1, before,
                                                     that_bai))

    def do_read_from_lr(self):
        """Thay cho: vào Lightroom -> Plug-in Extras -> xuất thông số."""
        if self._khoa_chan():
            return
        if not self.folder():
            messagebox.showinfo("Chưa chọn thư mục", "Chọn thư mục buổi chụp trước.")
            return
        def done(path):
            n = max(0, len(at.read_catalog_export(path)) if path else 0)
            self.lbl_job.configure(
                text=f"✓ Đã đọc {n} ảnh từ catalog Lightroom · {Path(path).name}",
                foreground=gd.MAU["xong"])
            self._invalidate_measurements()
            # 3/10: truoc goi self.refresh_scan() — ham khong ton tai, loi ngam
            self.scan_folder()
        self._ask_lr_export(done)

    def do_learn(self):
        """Đọc lại catalog rồi đối chiếu với job đã áp, xem bạn đã sửa gì.

        Gộp ba bước thành một: xuất thông số, chạy learn_corrections, hiện bảng.
        Chạy SAU khi bạn đã sửa tay xong thì kết quả mới có nghĩa."""
        if self._khoa_chan():
            return
        root = self.folder()
        if not root:
            messagebox.showinfo("Chưa chọn thư mục", "Chọn thư mục buổi chụp trước.")
            return
        if not messagebox.askokcancel(
                "Học từ buổi này",
                "Sẽ đọc lại thông số hiện tại trong Lightroom và so với những gì "
                "tool đã ghi, để biết bạn đã sửa tay chỗ nào.\n\n"
                "Chỉ có nghĩa nếu bạn ĐÃ sửa xong buổi này."):
            return

        def done(_path):
            try:
                import learn_corrections as lc
            except ImportError:
                messagebox.showerror(
                    "Thiếu learn_corrections.py",
                    "File learn_corrections.py phải nằm cùng thư mục với autotone.py.")
                return
            #[[ TIM BAO CAO O DUNG CHO — day la cho lam ca co che hoc chet lang.
            #
            #   Ban cu chi glob trong THU MUC SCRIPT. Nhung write_report() ghi
            #   bao cao vao THU MUC BUOI CHUP (hop thoai Luu CSV mo san o do).
            #   Nen csvs luon rong -> csv_path=None -> ctx={} -> moi dong thu ve
            #   deu thieu metered_ev lan clip_before.
            #
            #   Hau qua do tren chinh corrections.csv: 185/185 dong co
            #   metered_ev RONG, ca 185 roi vao nhom "khong-ro", implied_target
            #   rong not. Bao cao khong bao gio du MIN_SAMPLES nen in mai mot
            #   cau "can 8 ca nua". Nhin nhu dang thu thap, thuc te chi luu
            #   duoc hai cot so — tool ghi bao nhieu, nguoi dung chon bao nhieu
            #   — khong kem mot manh boi canh nao. Khong co boi canh thi khong
            #   phan nhom duoc, khong phan nhom duoc thi khong de xuat noi moc.
            #
            #   Tim ca hai cho, moi nhat thang. Khong co thi tu ghi mot ban tam
            #   tu so lieu dang co san trong bo nho, de nguoi dung khong phai
            #   nho bam "Luu CSV" truoc moi lan hoc.
            #]]
            here = Path(__file__).resolve().parent
            csvs = sorted([p for d in (root, here) for p in d.glob("autotone*.csv")],
                          key=lambda p: p.stat().st_mtime)
            if not csvs and self.items:
                tam = Path(tempfile.gettempdir()) / f"autotone-hoc-{os.getpid()}.csv"
                at.write_report(self.items, tam)
                csvs = [tam]
            try:
                rows = lc.collect(root.name, at.LR_JOB_DIR, csvs[-1] if csvs else None)
            except SystemExit as ex:
                messagebox.showerror("Không thu được", str(ex))
                return
            if not rows:
                messagebox.showinfo(
                    "Không ghép được ảnh nào",
                    "Bản xuất và job đã áp không có ảnh chung.\n"
                    "Có thể bạn chưa bấm “2 · Ghi” cho thư mục này.")
                return
            lc.save(rows, lc.STORE)
            nf = sum(1 for r in rows if r["da_sua"] == "1")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                lc.report(lc.STORE)
            self.lbl_job.configure(
                text=f"✓ Đã học từ {len(rows)} ảnh, trong đó {nf} ảnh bạn sửa tay.",
                foreground=gd.MAU["xong"])
            LogWindow(self, buf.getvalue().splitlines(),
                      title="Gu của bạn — tổng hợp mọi buổi đã thu",
                      subtitle=str(lc.STORE))
        self._ask_lr_export(done)

    def do_gu(self):
        """Thu gói duyệt rồi mở cửa sổ gắn lý do cho từng ảnh đã sửa.

        Khác nút "Học từ buổi này" ở chỗ: nút kia chỉ đếm anh đã sửa bao nhiêu,
        nút này hỏi VÌ SAO — thứ duy nhất tách được "tool sai" khỏi "gu của
        tôi khác". Trộn hai loại đó vào một phép trung vị là cách chắc chắn
        nhất để chỉnh nhầm tham số.
        """
        if self._khoa_chan():
            return
        #[[ CHONG BAM HAI LAN.
        #
        #   Buoc thu goi duyet do lai TUNG anh bang measure() roi ve khung —
        #   mot buoi 185 anh mat vai phut. Truoc day no chay THANG tren luong
        #   giao dien, nen ca cua so dong bang suot thoi gian do: khong thanh
        #   tien do, khong chu chay, bam vao dau cung khong nhuc nhich.
        #
        #   Nguoi dung tuong nut hong nen bam lai — va bam lai THAT SU chay
        #   them mot lan nua. Hai lan do cung ghi vao mot file gu.csv, cung
        #   tranh nhau thu muc anh, va may thi cham gap doi. Da xay ra that.
        #
        #   Nen: co khoa o day, va viec nang chay o luong nen (xem _gu_chay).
        #]]
        if getattr(self, "_gu_dang_chay", False):
            messagebox.showinfo(
                "Đang thu gói duyệt",
                "Đang chạy rồi — mỗi ảnh phải đo lại và vẽ khung nên mất vài "
                "phút.\n\nXem dòng trạng thái phía dưới để biết tới đâu.")
            return
        self._chon_khau("gu")
        root = self.folder()
        if not root:
            messagebox.showinfo("Chưa chọn thư mục", "Chọn thư mục buổi chụp trước.")
            return
        try:
            import thu_gu
        except ImportError:
            messagebox.showerror(
                "Thiếu thu_gu.py",
                "File thu_gu.py phải nằm cùng thư mục với autotone.py.")
            return
        ra = dd.goc_du_lieu() / "gu" / root.name
        if (ra / "gu.csv").is_file():
            #[[ GOI DUYET CU CO THE THIEU SO LIEU — moi mo len la khong biet.
            #
            #   Ban dau file nay lay boi canh tu bao cao autotone*.csv, ma bao
            #   cao do la tuy chon. Ai khong bam "Luu CSV" thi ca goi duyet ra
            #   doi voi metered_ev/so mat rong tron — do that tren buoi 1308:
            #   0/187 dong co so lieu. Nguoi dung khong thay gi bat thuong, va
            #   Agent thi khong con gi de tim quy luat.
            #
            #   Gio thu_gu tu do lay so lieu, nhung goi duyet CU van rong. Nen
            #   phai kiem va moi thu lai — kem loi hua giu nguyen ly do, vi neu
            #   khong nguoi dung se khong dam bam.
            #]]
            thieu = tong = 0
            try:
                with io.open(ra / "gu.csv", encoding="utf-8-sig", newline="") as fh:
                    for r in csv.DictReader(fh):
                        tong += 1
                        if not (r.get("metered_ev") or "").strip():
                            thieu += 1
            except OSError:
                pass
            if tong and thieu > tong // 2:
                if messagebox.askyesno(
                        "Gói duyệt thiếu số liệu",
                        f"Gói duyệt của buổi này có {thieu}/{tong} dòng KHÔNG có "
                        "số liệu đo sáng (metered_ev, số mặt, độ sáng khung).\n\n"
                        "Không có những số đó thì không tìm được quy luật — chỉ "
                        "biết anh sửa bao nhiêu, không biết vì sao.\n\n"
                        "Thu lại bây giờ? Lý do và giải thích anh đã gắn sẽ được "
                        "GIỮ NGUYÊN.\n\n"
                        "Chọn Không để mở cửa sổ gắn lý do như cũ."):
                    self._gu_chay(root, ra)
                    return
            self._mo_gu(ra)
            return

        if not messagebox.askokcancel(
                "Thu gói duyệt",
                "Chưa có gói duyệt cho buổi này. Sẽ đọc lại thông số hiện tại "
                "trong Lightroom, so với những gì tool đã ghi, rồi vẽ khung mặt "
                "cho từng ảnh anh đã sửa.\n\n"
                "Mất vài phút nếu buổi có nhiều ảnh sửa. Cửa sổ vẫn dùng được "
                "trong lúc chạy."):
            return

        def that_bai(_ly_do):
            #[[ KHONG DE NUT NAY DI VAO NGO CUT.
            #   Truoc: doc lai catalog that bai -> hien mot hop thoai roi thoi.
            #   Trong khi ban xuat cu VAN nam do va van dung duoc cho phan lon
            #   anh. Gio hoi thang, kem tuoi cua no, de nguoi dung tu quyet.
            #]]
            cu = at.ban_xuat_cho_thu_muc(root)     # cua DUNG buoi nay (3/10)
            if not cu:
                messagebox.showinfo(
                    "Chưa có bản xuất nào",
                    "Không đọc lại được catalog, và cũng chưa có bản xuất cũ nào "
                    "để dùng tạm.\n\nBấm dòng cảnh báo màu đỏ ở trên để xem "
                    "cách xử lý.")
                return
            khi = at.mo_ta_khoang(max(0.0, time.time() - cu.stat().st_mtime))
            if not messagebox.askokcancel(
                    "Dùng bản xuất cũ?",
                    f"Không đọc lại được catalog từ Lightroom.\n\n"
                    f"Có một bản xuất cũ: {cu.name}\ntạo {khi}.\n\n"
                    "Dùng nó thì vẫn gắn lý do được, nhưng danh sách sẽ THIẾU "
                    "những chỗ anh sửa sau thời điểm đó, và có thể thừa vài tấm "
                    "tool đã đổi từ lúc ấy.\n\n"
                    "Dùng bản cũ này?"):
                return
            self._gu_chay(root, ra)

        self._ask_lr_export(lambda _p: self._gu_chay(root, ra), that_bai=that_bai)

    def _gu_chay(self, root: Path, ra: Path):
        """Chạy thu_gu ở luồng nền, đẩy từng dòng tiến độ về dòng trạng thái."""
        import thu_gu
        self._gu_dang_chay = True
        self._nut_gu("disabled")
        self.status("Đang thu gói duyệt — đo lại và vẽ khung từng ảnh...", gd.MAU["canh"])
        q: queue.Queue = queue.Queue()

        class _Ra(io.TextIOBase):
            """Bắt từng dòng print của thu_gu, không gom tới cuối mới hiện."""

            def __init__(self):
                self.dem = ""

            def write(self, t):
                self.dem += t
                while "\n" in self.dem:
                    dong, self.dem = self.dem.split("\n", 1)
                    q.put(("dong", dong))
                return len(t)

        def work():
            ra_gia = _Ra()
            try:
                with contextlib.redirect_stdout(ra_gia):
                    rc = thu_gu.main([str(root)])
                q.put(("xong", rc))
            except Exception:                                # noqa: BLE001
                q.put(("dong", traceback.format_exc()))
                q.put(("xong", 1))

        log = []

        def bom():
            try:
                while True:
                    loai, gt = q.get_nowait()
                    if loai == "dong":
                        if gt.strip():
                            log.append(gt)
                            self.status(f"Gói duyệt: {gt.strip()}", gd.MAU["canh"])
                    else:
                        self._gu_dang_chay = False
                        self._nut_gu("normal")
                        if gt != 0 or not (ra / "gu.csv").is_file():
                            self.status("Không thu được gói duyệt", gd.MAU["loi"])
                            LogWindow(self, log, title="Không thu được gói duyệt",
                                      subtitle=str(ra))
                        else:
                            self.status(f"Đã thu gói duyệt → {ra}", gd.MAU["xong"])
                            self._mo_gu(ra)
                        return
            except queue.Empty:
                pass
            self.after(200, bom)

        threading.Thread(target=work, daemon=True).start()
        self.after(200, bom)

    def _mo_gu(self, ra: Path):
        """Nhúng khung gắn lý do vào khâu 6, thay cho một cửa sổ riêng."""
        self._chon_khau("gu")
        self._lam_moi_goi()
        cu = getattr(self, "_gu_win", None)
        if cu is not None:
            #[[ Huy khung cu TRUOC khi dung khung moi. Khong huy thi hai khung
            #   chong len nhau o cung o luoi, va cai nam duoi van con bat phim —
            #   go mot phim la hai khung cung ghi ly do vao mot file.
            #]]
            try:
                cu.destroy()
            except tk.TclError:
                pass
        self._gu_win = GuWindow(self, ra, self.hop_gu)
        self._gu_win.grid(row=0, column=0, sticky="nsew")

    def show_plugin_log(self):
        """Xem plugin đã làm gì — mỗi job một dòng, có số ảnh đã áp."""
        lines = at.read_plugin_log(200)
        if not lines:
            messagebox.showinfo(
                "Nhật ký plugin",
                f"Chưa có nhật ký nào ở:\n{at.LR_JOB_DIR / 'plugin.log'}\n\n"
                "Nghĩa là plugin chưa từng chạy — kiểm tra đã thêm vào Lightroom chưa "
                "(File → Plug-in Manager → Add).")
            return
        LogWindow(self, lines)

    def do_undo(self):
        #[[ KHONG khoa: khoi phuc anh tu backup la LAY LAI cai von cua ho.
        #
        #   Neu chan o day thi nguoi het han dang ket voi mot thu muc anh da
        #   bi sua ma khong hoan tac duoc — app giu con tin chinh anh goc cua
        #   khach. Do la muc do gay hai vuot xa moi khoan tien key.
        #]]
        root = self.folder()
        if not root:
            messagebox.showinfo("Thiếu thư mục", "Chọn thư mục ảnh trước đã.")
            return
        backups = at.list_backups(root)
        if not backups:
            messagebox.showinfo("Không có backup",
                                f"Chưa có bản backup nào trong\n{root / '_xmp_backup'}")
            return
        UndoDialog(self, root, backups)

    def open_buoi(self):
        """Một màn hình biết buổi chụp đang dở ở đâu."""
        if not self.folder():
            messagebox.showinfo("Chưa chọn thư mục", "Chọn thư mục buổi chụp trước.")
            return
        if getattr(self, "_buoi_win", None) and self._buoi_win.winfo_exists():
            self._buoi_win.lift()
            self._buoi_win.lam_moi()
            return
        self._buoi_win = BuoiWindow(self)

    def open_retouch(self):
        """Chặng cuối đường ống: Export xong rồi mới retouch, không song song.

        Chạy chồng lên lúc Lightroom đang export thì hai bên tranh nhau card đồ
        hoạ và ổ đĩa — tổng thời gian không giảm, còn log thì rối. Người dùng
        đã chốt chạy nối tiếp."""
        if self._khoa_chan():
            return
        self._chon_khau("retouch")

    def do_csv(self):
        #[[ KHONG khoa: day la XUAT lai ket qua da co trong self.items, khong
        #   chay them viec nao. Chan o day la giu con tin mot bang bao cao ma
        #   may da tinh xong tu truoc luc het han. ]]
        if not self.items:
            return
        root = self.folder()
        dest = filedialog.asksaveasfilename(
            title="Lưu báo cáo CSV", defaultextension=".csv",
            initialdir=str(root) if root else None,
            initialfile=f"autotone-{datetime.now():%Y%m%d_%H%M}.csv",
            filetypes=[("CSV", "*.csv")])
        if not dest:
            return
        at.write_report(self.items, Path(dest))
        self.status(f"Đã lưu báo cáo: {dest}", gd.MAU["xong"])


def main():
    #[[ PHAI LA DONG DAU TIEN CUA CA CHUONG TRINH. Khong duoc de gi len tren.
    #
    #   Buoc do anh chay 8 tien trinh song song (ProcessPoolExecutor). Tren
    #   macOS va Windows, multiprocessing khoi dong tien trinh con bang SPAWN:
    #   no CHAY LAI CHINH FILE THUC THI. Voi ban chay tu ma nguon thi Python tu
    #   biet duong xu ly, nhung voi ban da dong goi thi moi tien trinh con se
    #   chay lai main() — tuc MO THEM MOT CUA SO APP, va moi cua so do lai mo
    #   tiep 8 cua so nua.
    #
    #   freeze_support() chan dung cho do: trong tien trinh con no lam phan viec
    #   cua worker roi thoat, khong bao gio di tiep xuong duoi.
    #
    #   Tren Linux khong lo ra vi mac dinh la fork, khong chay lai file thuc thi.
    #   Nen loi nay chi hien khi dong goi cho Windows/macOS — dung hai he ma app
    #   nay nham toi. Xem kiem_da_tien_trinh.py.
    #]]
    import multiprocessing
    multiprocessing.freeze_support()

    #[[ CAP NHAT: nap ban CODE/MODEL moi (neu da tai) TRUOC moi import module app.
    #
    #   Vi sao o DAY, truoc ca `import tai_nguyen`: loi app trong goi la .pyd/.so;
    #   chi khi thu muc cap nhat dung TRUOC trong sys.path thi Python moi nap ban
    #   moi thay vi ban trong goi. Dat sau mot `import autotone` nao do thi ban cu
    #   da bi nap mat roi, chen sau cung vo ich.
    #
    #   kich_hoat() KHONG BAO GIO nem loi (boc try/except rong): mot ban cap nhat
    #   hong khong duoc phep chan app mo len. Boc them o day cho chac — thieu han
    #   module cap_nhat (ban cu) cung chay binh thuong.
    #
    #   Day chi KICH HOAT ban da tai. Viec KIEM mang + hoi nguoi dung + tai nam
    #   trong giao dien (sau khi cua so da mo), de khong lam cham luc khoi dong.
    #]]
    try:
        import cap_nhat as _cn
        _ver_va = _cn.kich_hoat()
        if _ver_va:
            print(f"[cap nhat] dang chay ban {_ver_va} (da ap ban va)")
    except Exception:                                    # noqa: BLE001
        pass

    #[[ CUA CHAY saytool TU TRONG GOI — phai o ngay sau freeze_support().
    #
    #   VI SAO CAN
    #     Ban chay tu ma nguon goi tool retouch bang:
    #         <goc>/.venv/bin/python -m saytool.cli chay ...
    #     Ban all-in-one thi KHONG co .venv, va sys.executable la chinh file app
    #     da dong goi chu khong phai mot trinh thong dich — dua "-m saytool.cli"
    #     cho no thi no coi do la tham so cua app, khong phai lenh Python.
    #
    #     Nen o day mo mot cua rieng: chay lai chinh app voi mot co dac biet thi
    #     no lam viec cua saytool roi thoat, khong dung toi giao dien. Thu vien
    #     da nam san trong goi nen khong phai nap them gi.
    #
    #   PHAI DAT TRUOC tk.Tk(): tien trinh con khong duoc mo cua so nao.
    #]]
    #[[ NAP TAI NGUYEN TAI ROI — phai dat TRUOC moi nhanh khac.
    #
    #   Ban nhe khong mang torch / mo hinh / mediapipe trong goi; chung nam o
    #   thu muc du lieu, tai ve khi nguoi dung can. Them chung vao duong tim
    #   module NGAY DAY de moi duong di ben duoi deu thay:
    #
    #       - giao dien (nut retouch hoi saytool co nhung buoc nao)
    #       - cua --say-chay (tien trinh con thuc su chay retouch)
    #       - bai tu kiem
    #
    #   Dat sau ba cai do thi tien trinh con khong thay torch, va loi hien ra
    #   la "No module named torch" — khong he nhac gi den tai nguyen.
    #
    #   Thieu goi thi nap() tra False va di tiep: khau can sang khong dung
    #   toi thu nao trong so nay. Chi khau retouch moi doi, va no tu bao.
    #]]
    try:
        import tai_nguyen as _tn
        _tn.nap_het(("torch", "mo-hinh", "mediapipe"))
    except Exception:                                    # noqa: BLE001
        pass

    _tham = sys.argv[1:]
    if _tham and _tham[0] in ("--say-chay", "--say-keo", "--say-kiem",
                              "--say-tainguyen", "--say-key", "--say-tim",
                              "--say-xem"):
        sys.exit(_cua_saytool(_tham[0], _tham[1:]))

    #[[ CUA TU KIEM — phai o TRUOC tk.Tk().
    #
    #   Sau khi dong goi, khong con cach nao chay python trong goi de kiem thu:
    #   goi chi co MOT diem vao la app nay. Nen app tu nhan lenh tu kiem, chay
    #   tu_kiem.py ngay ben trong goi roi thoat voi ma 0/1. kiem_goi.py o ngoai
    #   chi viec goi app voi bien AUTOTONE_TU_KIEM roi doc file bao cao.
    #
    #   Truoc tk.Tk() vi may build (hoac may khong co man hinh) van phai kiem
    #   duoc; tao cua so o do la gay ngay truoc khi kiem duoc gi.
    #]]
    if os.environ.get("AUTOTONE_TU_KIEM") or "--tu-kiem" in sys.argv[1:]:
        import tu_kiem
        sys.exit(tu_kiem.main(sys.argv[1:]))

    #[[ TASKBAR ICON tren Windows: phai dat AppUserModelID TRUOC tk.Tk().
    #
    #   Windows nhom cua so tren taskbar theo AppUserModelID. Mot tien trinh
    #   Python khong dat ID se duoc gan ID cua chinh python.exe/exe bootloader,
    #   va taskbar lay icon mac dinh — nen du cua so da co icon qua iconbitmap,
    #   nut tren taskbar van co the hien icon khac. Dat mot ID rieng cho app thi
    #   Windows coi no la ung dung doc lap va dung icon cua so. Chi Windows. ]]
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "vn.saymedia.autotone")
        except Exception:                                # noqa: BLE001
            pass

    root = tk.Tk()

    #[[ LOI TRONG CALLBACK KHONG DUOC IM LANG (8/10). Ban .exe khong co console:
    #   Tk in traceback ra stderr = khong ai thay, nguoi dung chi thay "bam nut
    #   khong an" (bao cao "ghi vao Lightroom lan 2 khong hoat dong"). Ghi ra
    #   <du lieu>/loi_giao_dien.log va hien mot hop ngan — MOI LOI MOT LAN: vong
    #   after() moi giay ma loi thi khong duoc dap hop thoai lien tuc. ]]
    _da_bao: set = set()

    def _bao_loi_callback(exc, val, tb):
        chu = "".join(traceback.format_exception(exc, val, tb))
        try:
            import duong_dan as _dd2
            with open(_dd2.goc_du_lieu() / "loi_giao_dien.log", "a", encoding="utf-8") as fh:
                fh.write(f"\n=== {datetime.now():%Y-%m-%d %H:%M:%S}\n{chu}")
        except Exception:                                # noqa: BLE001
            pass
        khoa_loi = f"{exc.__name__}: {val}"
        if khoa_loi in _da_bao or len(_da_bao) >= 3:
            return
        _da_bao.add(khoa_loi)
        try:
            messagebox.showerror("Lỗi", f"{khoa_loi}\n\nĐã ghi chi tiết vào "
                                 "loi_giao_dien.log trong thư mục dữ liệu của app.",
                                 parent=root)
        except Exception:                                # noqa: BLE001
            pass
    root.report_callback_exception = _bao_loi_callback
    #[[ Hien phien ban dang chay ngay tren tieu de: voi OTA, nguoi dung can biet
    #   minh dang o ban nao (goi hay ban va). Boc try/except — thieu cap_nhat
    #   (ban cu) thi chi la khong co so, khong phai loi. ]]
    try:
        import cap_nhat as _cnv
        root.title(f"{TEN_HIEN_THI} — cân sáng & retouch  (v{_cnv.phien_ban_dang_chay()})")
    except Exception:                                    # noqa: BLE001
        root.title(f"{TEN_HIEN_THI} — cân sáng & retouch")

    #[[ ICON CUA SO + TASKBAR. --icon cua PyInstaller chi nhung vao .exe (Explorer
    #   / shortcut thay icon gold); CUA SO Tkinter van dung icon mac dinh (long
    #   vu xanh) tru khi goi iconbitmap/iconphoto. File icon duoc mang vao GOC
    #   tai nguyen goi, GIU TEN GOC "icon.ico" (xem dong_goi.lenh --add-data
    #   ...;"." ). Chay tu ma nguon thi lay icon.ico canh file .py. Boc
    #   try/except: thieu icon chi la khong doi icon, KHONG chan app mo len. ]]
    try:
        import duong_dan as _dd
        #[[ Tim theo TEN GOC. Truoc day tim "app.ico" — SAI, vi --add-data tao
        #   THU MUC app.ico/ chua icon.ico (DEST la thu muc dich). Nay icon nam
        #   thang o goc ten icon.ico; van du phong app.ico cho goi cu. ]]
        _ico = None
        for _ten in ("icon.ico", "app.ico"):
            _p = _dd.tai_nguyen(_ten)
            if _p.is_file():
                _ico = _p
                break
        if _ico is None:
            _p = Path(__file__).resolve().parent / "icon.ico"
            _ico = _p if _p.is_file() else None
        if _ico and _ico.is_file():
            try:
                #[[ PHAI goi iconbitmap(ico) KHONG 'default' de DOI icon CUA SO
                #   CHINH (root). iconbitmap(default=ico) CHI dat mac dinh cho
                #   cua so con tao SAU — root van giu icon mac dinh (long vu).
                #   Da kiem qua Win32 WM_GETICON: default -> icon_handle=0 (khong
                #   doi); khong default -> icon_handle!=0 (doi that). Goi CA HAI:
                #   iconbitmap(ico) cho root, default cho cac hop thoai sau. ]]
                root.iconbitmap(str(_ico))              # doi icon ROOT (titlebar+taskbar)
                root.iconbitmap(default=str(_ico))      # + mac dinh cho cua so con
            except Exception:                            # noqa: BLE001
                #[[ Mac/Linux khong nhan .ico qua iconbitmap -> thu iconphoto PNG. ]]
                _png = _ico.with_name("app.png")
                if _png.is_file():
                    root.iconphoto(True, tk.PhotoImage(file=str(_png)))
    except Exception:                                    # noqa: BLE001
        pass

    #[[ Rong hon truoc: cot trai an 252 px, va bang anh co 15 cot. 1180 la be
    #   ngang toi thieu de bang khong phai cuon ngang ngay tu luc mo len.
    #]]
    root.minsize(1180, 680)
    root.geometry("1360x820")
    #[[ theme_use("clam") NAM TRONG dat_theme(). Ban cu dat "vista" ngay o day,
    #   ma vista ve nut va o nhap bang API cua Windows nen moi lenh doi mau deu
    #   bi bo qua — giao dien se van trang boc du da dat mau khap noi.
    #]]
    gd.dat_theme(root)
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
