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

#[[ TEN HIEN THI cho nguoi dung (tieu de cua so, nhan, hop thoai). Khac TEN KY
#   THUAT "AutoTone" (duong_dan.TEN_UD, bundle id, thu muc du lieu) — doi ten
#   hien thi KHONG dung toi cac thu do. Mot cho sua, moi cho dung lai day. ]]
TEN_HIEN_THI = "Tone&Retouch"


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


class Khung(ttk.Frame):
    """Khung việc nhúng trong cửa sổ chính, thay cho một cửa sổ Toplevel.

    VÌ SAO CÓ LỚP NÀY
        RetouchWindow, BuoiWindow, GuWindow trước đây là tk.Toplevel — mỗi cái
        một cửa sổ rời. Mở ba bốn cái là chúng chồng lên nhau và lạc mất cái
        đang làm. Giờ chúng thành khung nằm trong cột phải.

        Nhưng chúng gọi title(), geometry(), protocol(), destroy() ở hàng chục
        chỗ. Viết lại hết là sửa nhiều thứ đang chạy tốt để đổi một thứ duy nhất
        là CHỖ NGỒI của chúng. Nên lớp này nhận những lời gọi đó và không làm gì
        — ba lớp kia gần như giữ nguyên, chỉ đổi lớp cha.

        destroy() thì KHÔNG nuốt: một khung tự huỷ vẫn phải huỷ thật, và ttk.Frame
        đã có sẵn hành vi đúng.
    """

    def title(self, *_a):
        return ""

    def geometry(self, *_a):
        return ""

    def minsize(self, *_a):
        return None

    def resizable(self, *_a):
        return None

    def protocol(self, *_a):
        return None

    def transient(self, *_a):
        return None

    def grab_set(self, *_a):
        return None

    def lift(self, *_a):                      # noqa: A003
        return None


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


def open_in_explorer(path: Path) -> None:
    try:
        if sys.platform == "win32":
            os.startfile(str(path))                       # noqa: S606
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except OSError as ex:
        messagebox.showwarning("Không mở được", f"{path}\n\n{ex}")


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

        #[[ Mo app len la vao mo-dun Can tone: giua man hinh moi chon buoi chup
        #   (khau "Nap anh" cu nay la nut thu muc tren thanh cong cu). ]]
        self._chon_khau("phan_tich")
        self.after(80, self._pump)
        self.after(400, self._vong_lam_moi)
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
        self.nut_ve = gd.NutTron(self.dau_phu, "←  Kết quả", kieu="chu",
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
        lam = self._khung_lam.pop(ma, None)
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
            (w.grid() if k == ma else w.grid_remove())
        self.khau_dang = ma
        ten = dict(KHAU)[ma]
        md = self.MO_DUN_CUA.get(ma, "tone")
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
            self.nut_ve.configure(text="←  Kết quả" if md == "tone" else "←  Cân tone")
        #[[ MOI MO-DUN MOT BO: bang dieu khien phai, nut tren thanh cong cu,
        #   dong dau trang. Can tone: tuy chon can sang + "1 · Phan tich / 2 ·
        #   Ghi" + [Luoi anh | Bang so]. Retouch: muc ap dung + thu muc + may
        #   + "▶ Chay retouch" — dau trang rieng nam trong khung RetouchWindow.
        #   Ban khong kem retouch (khong co _retouch_win) thi khong co bang. ]]
        rt_win = getattr(self, "_retouch_win", None)
        if md == "tone":
            self.cuon_phai_rt.grid_remove()
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
            (self.ben_phai.grid if rt_win is not None else self.ben_phai.grid_remove)()
            self.cc_phai.grid_remove()
            self.cc_phai_rt.grid()
            self.lbl_job.pack_forget()
            self.dau_trang.grid_remove()
        self.hoi_md.goi_y.dat(MO_KHAU.get("retouch" if md == "retouch"
                                          else "phan_tich", ""))
        #[[ MAY XEM TRUOC CUA RETOUCH (sang 4/10): vao mo-dun thi mo SAN o nen
        #   (keo thanh la thay ngay, khong cho nap mo hinh); roi mo-dun thi tat —
        #   no giu mo hinh tren card do hoa, Lightroom dang can. ]]
        if rt_win is not None:
            try:
                if md == "retouch":
                    rt_win.after(300, rt_win._san_may_xem)
                else:
                    rt_win._nghi_may_xem()
            except Exception:                                # noqa: BLE001
                traceback.print_exc()
        #[[ Dai bao cua buoi (quet thu muc, ban xuat Lightroom) la chuyen cua
        #   Can tone — Retouch lam tren anh da Export, khong can no. ]]
        self.dai_quet.hien(md == "tone")
        self.lbl_md.configure(text="Cân tone" if md == "tone" else "Retouch")
        self.icon_md.delete("all")
        s = gd.don_vi(self) + 2
        gd.ve_bieu_tuong(self.icon_md, md, s / 2, s / 2, s * 0.8, gd.MAU["chu"])

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
        self._retouch_win = RetouchWindow(self, cha, ben=self.cuon_phai_rt.trong,
                                          thanh=self.cc_phai_rt)
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
        try:
            if f:
                cu, t_xuat, t_ghi = at.ban_xuat_cu_hon_lan_ghi(f)
                if cu:
                    canh.append(
                        f"⚠  Bản xuất catalog ({t_xuat:%H:%M %d/%m}) cũ hơn lần "
                        f"tool ghi ({t_ghi:%H:%M %d/%m}). Phân tích lúc này sẽ "
                        "bỏ nhầm ảnh — mở Lightroom rồi phân tích lại.")
        except Exception:                                    # noqa: BLE001
            pass

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

    def _build_folder(self, cha):
        """Buổi chụp trên thanh công cụ — thay cho khâu “Nạp ảnh” cũ.

        Bên trái: chữ AutoTone và NÚT BUỔI (tên thư mục đang mở, bấm là ra menu:
        chọn thư mục, gồm thư mục con, nguồn thông số preset, xoá dữ liệu cũ).
        Giữa thanh: dòng tình trạng quét (lbl_scan) và nút sửa đi kèm khi cần.
        Biến và tên widget giữ nguyên — scan_folder() và _nhan_catalog() viết
        vào lbl_scan / btn_fix y như trước.
        """
        m = gd.MAU
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
           "Color Grading vùng trung tính — da càng ngả vàng thì đẩy càng mạnh "
           "về phía hồng; da đã đúng màu thì gần như không đụng. Ảnh không "
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
        self.btn_cancel = gd.NutTron(cha, "Dừng", kieu="chu", nen=m["toi"],
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
                        bo="không ghi" if r.get("ngoai_xuat") else "")
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
        self.lbl_job.configure(
            text=f"✓ Lần gửi gần nhất {stamp} · {res or last.name}",
            foreground=gd.MAU["xong"])

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
                text=f"{n} ảnh RAW · khớp đủ {hit} ảnh từ catalog Lightroom.{dang_doc}",
                foreground=gd.MAU["xong"])

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

    def _soi_xuat(self):
        """Mỗi 3 giây: có bản xuất mới thì cập nhật lại dòng trạng thái.

        CHỈ đổi cái nhãn, KHÔNG gọi scan_folder(). scan_folder() kết thúc bằng
        _invalidate_measurements(), tức xoá sạch bảng đo — người dùng đo xong
        220 ảnh rồi sang Lightroom xuất lại là mất trắng công đo. Danh sách file
        trong thư mục không đổi khi Lightroom xuất, nên cũng không cần quét lại.
        """
        try:
            if self.source_value() == "catalog" and getattr(self, "pairs", None):
                doi = self._doc_xuat()
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
        d = TaiTaiNguyenDialog(self, tn, ["torch"])
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
        self.refresh_plan()
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
        if self.source_value() == "catalog" and self._doc_xuat():
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
                f"+{r['gr_sat']}" if r.get("gr_sat") else "",
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
        if r.get("gr_sat"):
            lines += [
                "",
                "Color Grading  (đẩy về da trắng hồng, cộng lên preset):",
                f"   Midtone : hue {r['gr_hue']}  sat +{r['gr_sat']}",
                f"   Shadow  : hue {r['gr_shue']}  sat +{r['gr_ssat']}",
            ]
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
        n = sum(1 for r in self.items if r["delta_ev"] or r["hl_adj"] or r["sh_adj"])
        ok = True if not hoi else messagebox.askokcancel(
            "Ghi vào sidecar .xmp",
            f"Sẽ ghi {len(self.items)} file .xmp ({n} ảnh có thay đổi).\n\n"
            "Bản gốc được backup tự động, hoàn tác được bằng nút “Hoàn tác...”.\n\n"
            "LƯU Ý: bước tiếp theo trong Lightroom là\n"
            "Metadata → Read Metadata from File, và thao tác đó GHI ĐÈ\n"
            "mọi chỉnh sửa đang có trong catalog của những ảnh này.\n"
            "Hãy chạy trước khi retouch tay."
            + (f"\n\n{ngoai} ảnh không có trong bản xuất từ Lightroom → KHÔNG ghi."
               if ngoai else "")
            + "\n\nTiếp tục?",
            icon="warning")
        if not ok:
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
        self.status(f"Đang ghi 0/{len(self.items)} file .xmp...", gd.MAU["canh"])
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
        if at.LAST_JOB:
            self._watch_job(at.LAST_JOB)
        else:
            self.lbl_job.configure(
                text="(không gửi job nào sang Lightroom — xem ô “Đẩy thẳng vào Lightroom”)",
                foreground=gd.MAU["mo"])
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
            dong.append(f"\nBackup .xmp: {self.last_backup.name}")
            dong.append(f"\n{nxt}")
            messagebox.showinfo("Chạy hết — xong", "\n".join(dong))
            return
        if messagebox.askyesno(
                "Xong",
                f"Đã ghi {len(self.items)} file .xmp.\n"
                f"Backup: {self.last_backup}\n\n{nxt}\n\nMở thư mục backup?"):
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

    def __init__(self, app: App, cha=None, ben=None, thanh=None):
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
        self._muc_chung_ban = False           # mức chung đổi mà chưa ghi retouch.json
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
                           ("Mở thư mục ra", lambda: self._mo_thu_muc(self.v_ra))):
            if nhan is None:
                self.menu_rt.add_separator()
            else:
                self.menu_rt.add_command(label=nhan, command=lenh)
        self.btn_them_rt = gd.NutTron(
            thanh, "", icon="them", kieu="chu", nen=nen,
            command=lambda: self.app._bat_menu(self.menu_rt, self.btn_them_rt))
        self.btn_them_rt.goi_y = gd.GoiY(
            self.btn_them_rt, "Thêm: kiểm tra tool, đọc lại tính năng, mở thư mục…")
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

        #[[ THANH CONG CU DUOI BANG KEO (nhu Evoto): Reset · Ve muc chung · Sync.
        #   Pack SAU bang keo -> nam duoi cung cua nhom "Muc ap dung". ]]
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
        self.btn_sync_chon.pack(side="left", padx=(6, 0))
        self.btn_sync_chon.goi_y = gd.GoiY(
            self.btn_sync_chon, "Chép mức của ảnh đang xem sang các tấm đang chọn "
                                "ở dải ảnh (Ctrl / Shift + bấm để chọn nhiều tấm; "
                                "Ctrl+A chọn hết).")
        self.btn_ve_chung = gd.NutTron(o_duoi, "Về mức chung", kieu="chu", font=gd.CHU,
                                       command=self._ve_muc_chung)
        self.btn_ve_chung.pack(side="left", padx=(6, 0))
        self.btn_ve_chung.goi_y = gd.GoiY(self.btn_ve_chung,
                                          "Bỏ mức riêng của ảnh đang xem — ảnh này "
                                          "theo lại mức chung.")
        self._dat_cho(self.btn_ve_chung, anchor="w")

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
        if self._xem_bat:
            #[[ So voi tam ANH LON DANG HIEN, khong phai tam tien trinh con
            #   dang mo: luot nhanh qua lai thi hai tam do khac nhau — so nham
            #   la ten tam moi nam duoi anh cua tam cu. ]]
            self._xem_gui_mo(path, hien_dia=path != self._anh_hien)
            return
        self._hien_anh_dia(path)
        #[[ May xem truoc dang chay san thi MO NGAM tam nay luon — lan keo dau
        #   tien tren tam nay khoi cho tool mo anh + tim mat. ]]
        if self._may_xem is not None:
            self._xem_xin_mo(path)

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
        self._danh_dau_the()
        if not self._dang_nap_muc:
            self._nguoi_doi_muc()

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
        cf = self.cf.get("muc") or {}
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
            self.cf["muc"] = dict(d)
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
        if self._muc_anh_vao:
            try:
                self.rt.ghi_muc_anh(self._muc_anh_vao, self._muc_anh)
            except OSError as ex:
                self._append(f"! không ghi được mức riêng từng ảnh: {ex}")
        if self._muc_chung_ban:
            self._muc_chung_ban = False
            try:
                self.rt.ghi_cau_hinh({"muc": dict(self.cf.get("muc") or {})})
            except OSError as ex:
                self._append(f"! không ghi được mức chung: {ex}")

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
        self._hien_an(self.btn_ve_chung, rieng)
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
        self.cf["muc"] = dict(muc)
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
            if self._anh_dang and not self._xem_bat:
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
        self._dat_chip_xem("đang tính…")

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
                    self._dat_chip_xem(self._nguon_muc() + (
                        "" if self._xem_so_mat else
                        " · tool không thấy khuôn mặt nào"))
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
        self.pb.configure(maximum=max(tong, 1), value=xong)
        if not tong:
            self.lbl_tt.configure(text="Thư mục vào chưa có ảnh nào")
        else:
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
    def start(self):
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
        tong, xong = self._dem()
        if not tong:
            messagebox.showinfo("Không có ảnh", f"{vao}\nkhông có ảnh nào.",
                                parent=self)
            return
        con = tong if self.v_lamlai.get() else tong - xong
        if not con:
            messagebox.showinfo("Đã xong từ trước",
                                f"Cả {tong} ảnh đều đã có kết quả.\n\n"
                                "Muốn làm lại thì tick “Làm lại cả ảnh đã có kết quả”.",
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
        lam_lai = bool(self.v_lamlai.get())
        de_quy = bool(self.v_dequy.get())
        xong_cua = {str(p): bool(x) for p, x in self._ds_luoi}
        nhom = self.rt.nhom_theo_muc([str(p) for p, _x in self._ds_luoi],
                                     lambda p: self._loc_muc(self._muc_hieu_luc(p)))
        #[[ any(muc.values()) da dung cho ca muc rieng, vi muc_day_du() gop
        #   ca hai vao mot tu dien phang. Chi doi loi chu: "ba thanh keo" la
        #   con so cua ban cu, gio la sau va con them nam nhom. ]]
        if not nhom or all(self.rt.muc_trong(m) for m, _a in nhom):
            messagebox.showinfo(
                "Chưa bật tính năng nào",
                "Mọi thanh kéo đều ở 0 — kể cả mức riêng theo nhóm"
                + (" và mức riêng từng ảnh" if len(nhom) > 1 else "")
                + ". Không có gì để làm.", parent=self)
            return
        #[[ GHI DE + NHIEU NHOM MUC -> TU CHOI. Chay theo nhom la chay tren
        #   thu muc tam (lien ket cung / ban chep): saytool ghi de len BAN TRONG
        #   THU MUC TAM — tuy cach no ghi (ghi thang hay ghi file moi roi doi
        #   ten) ma anh goc that co doi hay khong. Khong doan chuyen mat anh
        #   goc cua khach. ]]
        if ghi_de and len(nhom) > 1:
            messagebox.showerror(
                "Ghi đè chỉ chạy được MỘT mức",
                f"Các ảnh đang có {len(nhom)} mức khác nhau (mức riêng từng ảnh). "
                "Ghi đè lên ảnh gốc chỉ chạy một mức cho cả thư mục.\n\n"
                "Chọn một trong hai:\n"
                "   • Ctrl+A chọn hết ở dải ảnh rồi bấm “Sync ảnh đã chọn” "
                "để mọi ảnh cùng một mức\n"
                "   • Hoặc tắt “Ghi đè lên ảnh gốc” để ra thư mục khác",
                parent=self)
            return

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
        if len(nhom) > 1:
            try:
                tam_goc = self.rt.tao_thu_muc_tam(vao)
            except OSError as ex:
                messagebox.showerror("Không tạo được thư mục tạm",
                                     f"Chạy theo nhóm mức cần một thư mục tạm:\n{ex}",
                                     parent=self)
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

        #[[ Tat xem truoc TRUOC khi chay: no giu mo hinh tren card do hoa, ca
        #   me nap them mot bo nua la de het bo nho card. ]]
        if self._may_xem is not None:
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
        self._xong_dau = xong
        self._log_cuoi: list[str] = []
        #[[ Gom RIENG cac dong "! BO QUA" thay vi doc lai tu _log_cuoi: chung
        #   duoc in luc NAP BUOC, tuc ngay dau lượt chay, nen mot buoi vai tram
        #   anh la chung da troi khoi 80 dong cuoi tu lau. ]]
        self._bi_bo: list = []
        self._so_dong_log = 0        # đếm để biết tool có nói gì không
        self._append(f"\n=== {datetime.now():%H:%M:%S}  {con} ảnh cần làm, "
                     f"{luong} luồng"
                     + (f", {sum(1 for *_x, la0 in viec if not la0)} lượt theo mức"
                        if len(nhom) > 1 else "") + " ===")

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

        def chay_mot(thu_muc, muc):
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
                for loai, gt in self.rt.chay(
                        goc, thu_muc, ra, muc, may=may,
                        de_quy=de_quy, lam_lai=lam_lai,
                        luong=luong, che_do=che_do,
                        ghi_de=ghi_de):
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
                    ma = chay_mot(vao, nhom[0][0])
                else:
                    n_luot = sum(1 for _m, _a, la0 in viec if not la0)
                    i = 0
                    for m, a, la0 in viec:
                        if self._dung_tay:
                            break
                        if la0:
                            n = self.rt.chep_nguyen_ban(a, vao, ra, de_quy, lam_lai)
                            self.log_q.put(("dong", f"=== {len(a)} ảnh mức 0 hết: "
                                                    f"chép nguyên bản {n} ảnh sang "
                                                    f"thư mục ra ==="))
                            continue
                        i += 1
                        d = tam_goc / f"nhom_{i}"
                        lien, chep = self.rt.dung_thu_muc_nhom(vao, a, d, de_quy)
                        self.log_q.put(("dong", f"=== lượt {i}/{n_luot}: {len(a)} ảnh"
                                                + (f" (chép {chep} ảnh vào thư mục "
                                                   f"tạm)" if chep else "") + " ==="))
                        ma = chay_mot(d, m)
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

    def stop(self):
        #[[ Danh dau TRUOC khi giet: khong danh dau thi vong tu chay lai trong
        #   work() thay ma thoat 0xC0000005 (terminate cung cho ma do tren
        #   Windows) va lai chay tiep - nguoi dung bam Dung ma no khong dung.
        #]]
        self._dung_tay = True
        p = self.proc
        if p and p.poll() is None:
            self._append("… đang dừng")
            try:
                p.terminate()
            except OSError as ex:
                self._append(f"! không dừng được: {ex}")
        self.btn_stop.configure(state="disabled")

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
        #   nhuong card do hoa) — keo thanh tiep la thay ngay. ]]
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

    def on_close(self):
        if self.proc and self.proc.poll() is None:
            if not messagebox.askokcancel(
                    "Đang chạy", "Retouch đang chạy. Đóng cửa sổ sẽ dừng nó.\n\n"
                    "Ảnh đã làm xong vẫn giữ nguyên, chạy lại là tiếp tục.",
                    parent=self):
                return
            self.stop()
        self.destroy()


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

    def __init__(self, cha, tn, can=None):
        super().__init__(cha)
        self.tn = tn
        self.title("Tải tài nguyên retouch")
        self.transient(cha)
        self.resizable(False, False)
        self._dung = False          # nguoi dung bam Dung
        self._dang_tai = False
        self.q = queue.Queue()
        self.xong_het = False

        frm = ttk.Frame(self, padding=14)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, justify="left", wraplength=560, text=(
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
            h = ttk.Frame(frm)
            h.pack(fill="x", pady=2)
            bat = g["ten"] in can
            v = tk.BooleanVar(value=bat or g["da_co"])
            #[[ Goi DA CO thi khoa lai — khong tai lai cai da co. Goi BAT BUOC
            #   cung khoa: bo no thi retouch van khong chay, cho chon chi tao
            #   ra mot lua chon sai. Chi mediapipe la that su tuy chon. ]]
            trang_thai = "disabled" if (g["da_co"] or bat) else "normal"
            ttk.Checkbutton(h, variable=v, state=trang_thai,
                            text=f"{g['ten']}  ({g['mb']} MB)").pack(side="left")
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


def _dat_buffalo(kho) -> None:
    """Đặt buffalo_l từ trong gói vào ~/.insightface nếu chưa có.

    #[[ VI SAO PHAI CHEP CHU KHONG TRO THANG VAO GOI
    #
    #   insightface tim mo hinh o `os.path.expanduser(root)` voi root la THAM SO
    #   cua FaceAnalysis, mac dinh '~/.insightface'. Khong co bien moi truong nao
    #   doi duoc, va saytool goi FaceAnalysis(name="buffalo_l", ...) khong truyen
    #   root — sua cho do la sua vao du an khac.
    #
    #   Nen chep mot lan sang ~/.insightface/models/. Ton ~326 MB o thu muc nguoi
    #   dung, doi lai lan dau bam Retouch khong phai tai gi va khong can mang.
    #]]
    """
    import shutil
    nguon = Path(kho) / "insightface" / "models" / "buffalo_l"
    if not nguon.is_dir():
        return
    dich = Path.home() / ".insightface" / "models" / "buffalo_l"
    if dich.is_dir() and list(dich.glob("*.onnx")):
        return
    try:
        dich.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(nguon, dich, dirs_exist_ok=True)
    except OSError:
        pass                    # khong chep duoc thi de insightface tu tai


def _cua_saytool(co: str, tham: list) -> int:
    """Làm việc của saytool trong chính tiến trình này. -> mã thoát.

    Ba cửa, khớp với ba hằng CO_SAY_* trong retouch.py:
        --say-chay   chạy retouch thật, tham số y hệt saytool.cli
        --say-keo    in JSON danh sách thanh kéo saytool đang có
        --say-kiem   kiểm thư viện, in ra đúng dạng mà retouch.kiem_tra() đọc
    """
    #[[ EP UTF-8 CHO MOI CUA --say-*.
    #
    #   Console Windows mac dinh cp1252, khong ma hoa noi chu Viet. Cac cua nay
    #   in loi bang tieng Viet ("ly do: Máy này chưa kích hoạt..."), nen bat cu
    #   cua nao cham vao mot chuoi co dau la NEM UnicodeEncodeError — va trong
    #   ban .exe no hien ra thanh hop thoai "Failed to execute script", trong
    #   y het mot ban build hong.
    #
    #   Da dinh dung bon lan o bon cho khac nhau (cli.py, dong_goi.py,
    #   kiem_cu_phap.py, va --say-key). Ep mot lan ngay day thi moi cua sau nay
    #   deu khoi dinh lai.
    #]]
    for _luong in (sys.stdout, sys.stderr):
        try:
            _luong.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass

    #[[ mo_hinh/vet.pt, mo_hinh/nong_cam.pt va mo_hinh/liquify/ deu la DUONG DAN
    #   TUONG DOI trong saytool, tinh theo thu muc dang dung. Trong goi thi
    #   chung nam canh saytool o thu muc tai nguyen, nen phai chuyen sang do.
    #   Khong lam thi retouch chet ngay o anh dau: FileNotFoundError 'mo_hinh/vet.pt'.
    #]]
    import os
    try:
        import duong_dan as _dd
        tn = str(_dd.goc_tai_nguyen())
        if os.path.isdir(os.path.join(tn, "mo_hinh")):
            os.chdir(tn)
        if tn not in sys.path:
            sys.path.insert(0, tn)
    except Exception:                                        # noqa: BLE001
        pass

    #[[ Tro cac mo hinh saytool VON TU TAI ve ban da nam san trong goi. Hai bien
    #   moi truong nay la cua chinh saytool (skin_spike4.py dong 98 va 337), nen
    #   khong phai sua mot dong nao ben ToolCloneEvoto.
    #]]
    try:
        import duong_dan as _dd
        kho = _dd.goc_tai_nguyen() / "mo_hinh"
        os.environ.setdefault("SKIN_SPIKE_CACHE", str(kho))
        fp = kho / "resnet34_faceparse.onnx"
        if fp.is_file():
            os.environ.setdefault("FACE_PARSE_ONNX", str(fp))
        _dat_buffalo(kho)
    except Exception:                                        # noqa: BLE001
        pass

    #[[ --say-xem: VONG LAP XEM TRUOC trong goi (keo thanh -> hien ket qua ngay).
    #
    #   Ban mã nguồn chay `python -c MA_CON`; ban DONG GOI khong chay `-c` duoc
    #   (frozen exe != python) nen MayXem.bat_dau() goi `AutoTone.exe --say-xem`.
    #   No chay xem_truoc.vong_xem() — doc JSON o stdin, tra anh nen o stdout —
    #   dung logic y het ban mã nguồn (cung ham). Da chdir sang thu muc tai
    #   nguyen + set model env o tren nen saytool nap duoc mo_hinh/*.pt. ]]
    if co == "--say-xem":
        try:
            import xem_truoc
            return int(xem_truoc.vong_xem() or 0)
        except Exception as ex:                              # noqa: BLE001
            import json as _json
            sys.stdout.write(_json.dumps(
                {"loai": "hong", "loi": f"{type(ex).__name__}: {ex}"}) + "\n")
            sys.stdout.flush()
            return 1

    if co == "--say-keo":
        import json
        try:
            from saytool.buoc import moi_thanh_keo
            ds = [[t.ten, t.nhan, float(t.mac_dinh), t.goi_y,
                   bool(getattr(_b, "can_torch", False))]
                  for _b, t in moi_thanh_keo()]
        except Exception as ex:                              # noqa: BLE001
            print(f"  ! khong doc duoc thanh keo: {type(ex).__name__}: {ex}")
            return 1
        sys.stdout.write("@@KEO@@" + json.dumps(ds, ensure_ascii=False))
        return 0

    #[[ --say-tainguyen: hoi ban DA DONG GOI xem trinh tai co song khong.
    #
    #   Can thiet vi ban nhe song bang tai_nguyen.py, ma duong import cua no
    #   trong diem vao nam trong try/except — thieu han no thi app van chay
    #   binh thuong, chi la khong bao gio tai duoc gi. Chay co nay tren goi
    #   vua build la biet ngay, khong phai doi nguoi dung bam Retouch moi lo.
    #]]
    #[[ --say-key: kiem ban quyen tren goi DA DONG.
    #
    #   Cung ly do voi --say-tainguyen: ban_quyen duoc import o dau file nen
    #   thieu no thi app sap ngay, nhung con CAP_KEY lot vao goi thi khong co
    #   dau hieu gi het — app chay binh thuong, chi la khach tu sinh key duoc.
    #   Co nay kiem ca hai chieu tren chinh goi vua build.
    #]]
    if co == "--say-key":
        try:
            import ban_quyen as _bq
        except Exception as ex:                               # noqa: BLE001
            print(f"THIEU BAN QUYEN: {type(ex).__name__}: {ex}")
            return 1
        #[[ Co the kem mot key de KICH HOAT luon: `AutoTone.exe --say-key <KEY>`.
        #
        #   Can cho hai viec: kiem duoc ca duong kich hoat tren goi da dong
        #   (giao dien thi phai bam tay), va cuu ho tu xa khi khach khong mo
        #   noi giao dien — doc lenh cho ho go vao Command Prompt.
        #]]
        if tham:
            _ok, _nhan = _bq.kich_hoat(tham[0])
            print(("" if _ok else "[!] ") + _nhan)
            if not _ok:
                return 1
        _g = _bq.kiem()
        print(f"may     : {_g['may']}")
        print(f"co phep : {_g['co_phep']}")
        print(f"goi     : {_g['goi'] or '(chua kich hoat)'}")
        if _g["het_han"]:
            print(f"han den : {_g['het_han'].astimezone():%H:%M %d/%m/%Y}")
        if _g["ly_do"]:
            print(f"ly do   : {_g['ly_do']}")
        #[[ Canh chuyen mat tien: cap_key.py lot vao goi. ]]
        try:
            import cap_key                                    # noqa: F401
            print("NGUY HIEM: cap_key.py NAM TRONG GOI — khach tu sinh key duoc!")
            return 1
        except ImportError:
            print("cap_key : khong co trong goi (dung)")
        return 0

    if co == "--say-tainguyen":
        try:
            import tai_nguyen as tn
        except Exception as ex:                               # noqa: BLE001
            print(f"THIEU TRINH TAI: {type(ex).__name__}: {ex}")
            return 1
        print(f"kho   : {tn.goc()}")
        print(f"can   : {', '.join(tn.can_cho_retouch()) or '(du)'}")
        for g in tn.tinh_trang():
            print(f"  {'[x]' if g['da_co'] else '[ ]'} {g['ten']:<10}"
                  f" {g['mb']:>5} MB  {g.get('mo_ta','')}")
        return 0

    if co == "--say-kiem":
        thieu = []
        for m in ("torch", "cv2", "numpy", "saytool"):
            try:
                __import__(m)
            except Exception as ex:                           # noqa: BLE001
                thieu.append(f"{m}: {type(ex).__name__}")
        print("THIEU:" + ";".join(thieu) if thieu else "OK")
        try:
            import saytool
            print("phien ban", getattr(saytool, "__version__", "?"))
        except Exception:                                     # noqa: BLE001
            pass
        return 1 if thieu else 0

    #[[ CHAN DOAN (--say-tim): in ra tim_tool / goc_trong_goi / la_goc_trong_goi
    #   + thu thanh_keo() de xem vi sao self-check bao "CHI CO ban du phong".
    #   Chi de go loi; khong anh huong nguoi dung. ]]
    if co == "--say-tim":
        import retouch as _rt
        _b = _rt.goc_trong_goi()
        _g = _rt.tim_tool()
        print("trong_goi    :", _rt.trong_goi())
        print("goc_trong_goi:", _b)
        print("tim_tool     :", _g)
        print("la_goc_trong_goi(tim_tool):",
              _rt.la_goc_trong_goi(_g) if _g else "n/a")
        try:
            _ds = _rt.thanh_keo(_g, lam_lai=True)
            print("thanh_keo so luong:", len(_ds))
            print("thanh_keo ten:", [t[0] for t in _ds])
        except Exception as _ex:                              # noqa: BLE001
            print("thanh_keo loi:", type(_ex).__name__, _ex)
        try:
            _loi = _rt._LOI_KEO.get(str(_g), "")
            print("_LOI_KEO:", (_loi[:500] if _loi else "(rong)"))
        except Exception:                                     # noqa: BLE001
            pass
        return 0

    from saytool.cli import main as say_main
    return int(say_main(tham) or 0)


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
