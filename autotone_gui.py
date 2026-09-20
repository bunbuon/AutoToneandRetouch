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
import khoa


#[[ BAY KHAU — xuong song cua ung dung.
#
#   Ma khau o day PHAI trung voi khoa "ten" ma trang_thai.tinh() tra ve, vi cot
#   trai doc thang tu do. Lech mot chu la khau do khong bao gio hien trang thai,
#   ma khong bao loi gi ca — nen doi ten khau thi phai doi ca hai noi.
#]]
KHAU = [("tong_quan", "Tổng quan"),
        ("nap", "Nạp ảnh"),
        ("phan_tich", "Phân tích"),
        ("day", "Đẩy vào Lightroom"),
        ("export", "Export"),
        ("retouch", "Retouch"),
        ("gu", "Vì sao tôi sửa"),
        ("hoc", "Gu đã học")]

MO_KHAU = {
    "tong_quan": "Cả buổi đang ở đâu — bảy khâu, mỗi khâu một thẻ. Bấm vào thẻ "
                 "là nhảy thẳng vào khâu đó.",
    "nap": "Chọn thư mục buổi chụp và cho biết lấy thông số preset từ đâu.",
    "phan_tich": "Đo sáng từng ảnh rồi tính thông số. Chưa đụng tới file nào — "
                 "mọi thứ ở đây đều xem lại được trước khi ghi.",
    "day": "Ghi thông số vào .xmp hoặc đẩy thẳng qua plugin, rồi kiểm chứng "
           "Lightroom đã nhận đúng.",
    "export": "Chỉ chỗ Lightroom vừa xuất ảnh ra, để các khâu sau biết đường tìm.",
    "retouch": "Đưa thư mục vừa Export sang tool chỉnh chân dung. Chạy sau "
               "Export, không chạy song song.",
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
WBS = [("Da trắng hồng — máy đo + ngả hồng  (khuyên dùng)", "skin"),
       ("Theo nhiệt độ máy đo được", "asshot"),
       ("Không đụng tới", "off"),
       ("Grey-world trên preview", "grey"),
       ("Grey-world, chỉ san trong cảnh", "scene")]

SOURCES = [("Sidecar .xmp  (phải bấm Ctrl+S trong Lightroom)", "sidecar"),
           ("Lightroom catalog qua plugin  (không cần Ctrl+S)", "catalog")]

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
    """Cửa sổ chính: cột trái bảy khâu, cột phải khung việc của khâu đang chọn.

    BỐ CỤC
        ┌───────────────────────────────────────────┐
        │ băng cảnh báo mã nguồn cũ  (chỉ khi cần)  │
        ├──────────────┬────────────────────────────┤
        │ cột trái     │ tiêu đề khâu               │
        │ 7 khâu       ├────────────────────────────┤
        │              │ khung việc (đổi theo khâu) │
        │ ▶ Chạy hết   │                            │
        ├──────────────┴────────────────────────────┤
        │ thanh trạng thái + tiến độ                │
        └───────────────────────────────────────────┘

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
        self.rowconfigure(1, weight=1)

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

        self.khau_dang = "nap"
        self.khung: dict = {}          # mã khâu -> Frame nội dung
        self._khung_lam: dict = {}     # mã khâu -> hàm dựng chậm

        self._canh_ma_cu()
        self._build_shell()

        # Các khâu dựng ngay (giữ biến mà nơi khác đọc bất cứ lúc nào)
        self._build_tong_quan(self.khung["tong_quan"])
        self._build_folder(self.khung["nap"])
        self._build_options(self.khung["phan_tich"])
        #[[ NUT VA BANG KHONG NAM TRONG VUNG CUON — chung duoc GHIM o duoi.
        #
        #   Cho tat ca vao vung cuon thi ky thuat la xong: bam duoc, cuon toi la
        #   thay. Nhung "1 · Phan tich" la nut chinh cua ca man hinh, va bang
        #   ket qua la thu nguoi dung nhin nhieu nhat — bat cuon xuong moi thay
        #   chung la doi mot loi nay lay mot phien khac.
        #
        #   Nen chi phan TUY CHON cuon; nut va bang luon o day man hinh.
        #   minsize giu cho hai vung khong bao gio bi bop het khi cua so thap.
        #]]
        ngoai = self.khung_ngoai["phan_tich"]
        #[[ TUY CHON DUOC 2 PHAN, BANG + NUT DUOC 1.
        #
        #   Truoc day chia doi 1:1. Do bang Tk that o cua so 1660x940: khoi tuy
        #   chon can 695 px ma chi duoc cap 389 px — VAN PHAI CUON, dung cai
        #   dang di chua. Bang ket qua thi tu no da cuon duoc roi nen nhuong
        #   bot cho khong mat gi; con tuy chon ma phai cuon la giau tinh nang.
        #
        #   minsize 260 giu cho bang khong bi bop den muc khong con doc noi.
        #]]
        ngoai.rowconfigure(0, weight=2, minsize=120)
        ngoai.rowconfigure(1, weight=1, minsize=260)
        duoi = ttk.Frame(ngoai)
        duoi.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        duoi.columnconfigure(0, weight=1)
        self._build_actions(duoi)
        self._build_table(duoi)
        self._build_lrbox(self.khung["day"])
        self._build_export(self.khung["export"])
        self._build_hoc(self.khung["hoc"])
        self._build_status()

        self._khung_lam["retouch"] = self._lam_retouch
        self._khung_lam["gu"] = self._lam_gu

        self._chon_khau("tong_quan")
        self.after(80, self._pump)
        self.after(400, self._lam_moi_ray)
        self._soi_khoa()
        self.after(3000, self._soi_xuat)
        self._set_busy(False)

    # ------------------------------------------------------------ khung vỏ
    def _build_shell(self):
        m = gd.MAU
        than = tk.Frame(self, background=m["nen"])
        than.grid(row=1, column=0, sticky="nsew")
        than.columnconfigure(1, weight=1)
        than.rowconfigure(0, weight=1)

        # cột trái
        self.ray = gd.Ray(than, KHAU, self._chon_khau,
                          khong_so=("tong_quan",))
        self.ray.configure(width=252)
        self.ray.grid(row=0, column=0, sticky="ns")
        #[[ pack_propagate, KHONG phai grid_propagate.
        #   Con cua Ray dat bang pack(), nen chinh pack moi la thu dang tinh lai
        #   be ngang cua no theo con. Goi nham grid_propagate thi lenh chay tron
        #   tru, khong bao gi, va cot trai co lai con ~185 px thay vi 252 —
        #   dai nhan dang chon cung cut theo. Da dinh dung o ban dung thu.
        #]]
        self.ray.pack_propagate(False)
        self.ray.grid_propagate(False)
        vien = tk.Frame(than, width=1, background=m["vien"])
        vien.grid(row=0, column=0, sticky="nse")

        self.btn_all = ttk.Button(self.ray.chan, text="▶  Chạy hết",
                                  style="Chinh.TButton", command=self.start_all)
        self.btn_all.pack(fill="x")
        ttk.Button(self.ray.chan, text="Bảng tóm tắt buổi…", style="Pha.TButton",
                   command=self.open_buoi).pack(fill="x", pady=(6, 0))
        #[[ Han dung LUON hien, khong giau trong menu. Nguoi dung phai biet con
        #   bao lau TRUOC khi bat dau mot buoi 1400 anh, chu khong phai phat hien
        #   ra luc dang chay do.
        #]]
        self.lbl_han = tk.Label(self.ray.chan, text="", anchor="w", justify="left",
                                background=gd.MAU["tam"], foreground=gd.MAU["mo2"],
                                font=gd.CHU_NHO, wraplength=224)
        self.lbl_han.pack(fill="x", pady=(8, 0))

        # cột phải
        phai = tk.Frame(than, background=m["nen"])
        phai.grid(row=0, column=1, sticky="nsew", padx=(1, 0))
        phai.columnconfigure(0, weight=1)
        phai.rowconfigure(1, weight=1)

        dau = tk.Frame(phai, background=m["nen"], padx=20, pady=14)
        dau.grid(row=0, column=0, sticky="ew")
        self.lbl_khau = ttk.Label(dau, text="", style="To.TLabel")
        self.lbl_khau.pack(anchor="w")
        self.lbl_khau_mo = ttk.Label(dau, text="", style="Mo.TLabel",
                                     wraplength=820, justify="left")
        self.lbl_khau_mo.pack(anchor="w", pady=(3, 0))
        tk.Frame(phai, height=1, background=m["vien"]).grid(row=0, column=0,
                                                            sticky="ews")

        self.hop = tk.Frame(phai, background=m["nen"])
        self.hop.grid(row=1, column=0, sticky="nsew", padx=20, pady=(14, 14))
        self.hop.columnconfigure(0, weight=1)
        self.hop.rowconfigure(0, weight=1)
        #[[ MOI KHAU NAM TRONG MOT VUNG CUON DUOC.
        #
        #   Khung viec cua khau Phan tich cao hon cua so tren man 1080: ba hop
        #   chon, sau o so, chin cong tac. grid khong tu cho cuon, no chi cat
        #   bot — nen nut "1 · Phan tich" bi day khoi mep duoi va khong cach nao
        #   voi toi. Da xay ra that 3/9 tren may nguoi dung.
        #
        #   Cac khau khac hien chua du dai de tran, nhung cho chung vao cung mot
        #   khuon thi khong con phai nho khau nao dai khau nao ngan — them mot
        #   cong tac vao khau bat ky cung khong lam vo bo cuc.
        #]]
        self.khung_ngoai: dict = {}
        #[[ Giu ca doi tuong Cuon chu khong chi cai khung ben trong no.
        #   self.khung[ma] tro toi khung BEN TRONG canvas — no luon cao dung
        #   bang noi dung, nen nhin vao do khong bao gio biet duoc "co phai
        #   cuon khong". Cau tra loi nam o chieu cao CANVAS. Bai kiem
        #   kiem_man_hinh.py hoi dung cho nay. ]]
        self.khung_cuon: dict = {}
        for ma, _ten in KHAU:
            k = ttk.Frame(self.hop)
            k.grid(row=0, column=0, sticky="nsew")
            k.columnconfigure(0, weight=1)
            k.rowconfigure(0, weight=1)
            k.grid_remove()
            cu = gd.Cuon(k)
            cu.grid(row=0, column=0, sticky="nsew")
            self.khung_ngoai[ma] = k
            self.khung_cuon[ma] = cu
            self.khung[ma] = cu.trong

    def _chon_khau(self, ma: str):
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
        #[[ Hien/an KHUNG NGOAI, khong phai self.khung[ma].
        #
        #   Tu khi moi khau nam trong mot vung cuon, self.khung[ma] tro toi khung
        #   BEN TRONG canvas — no duoc dat bang create_window chu khong phai
        #   grid, nen goi .grid()/.grid_remove() len no khong lam gi ca. Ket qua:
        #   khong khau nao duoc hien, ca cot phai trong tron.
        #
        #   Khong nem loi, khong bao gi het. Bai kiem chieu cao cua so bat duoc
        #   vi no hoi "nut co NHIN THAY khong", chu khong hoi "co sap khong".
        #]]
        for k, w in self.khung_ngoai.items():
            (w.grid() if k == ma else w.grid_remove())
        self.khau_dang = ma
        ten = dict(KHAU)[ma]
        #[[ HOI RAY, KHONG TU DEM.
        #
        #   enumerate(KHAU, 1) o day tung dung, cho den luc them "Tong quan" vao
        #   dau KHAU: ray bo qua muc do khi danh so, tieu de thi khong, nen mot
        #   man hinh hien "4 Export" ben trai va "Khau 5 - Export" ben phai.
        #   Gio chi con mot cho dem so — Ray.so_cua().
        #]]
        so = self.ray.so_cua(ma)
        self.lbl_khau.configure(
            text=ten if so == "·" else f"Khâu {so} · {ten}")
        self.lbl_khau_mo.configure(text=MO_KHAU.get(ma, ""))
        self.ray.chon(ma)

    def _lam_moi_ray(self):
        """Đọc lại trạng thái bảy khâu từ đĩa. Rẻ — chỉ đếm file và đọc mtime."""
        try:
            import trang_thai as tt
            f = self.folder()
            if f:
                ds = tt.tinh(f)
                self.ray.cap_nhat(ds, tt.ten_buoi(f))
                self._lam_moi_tong_quan(ds)
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
            cu = getattr(self, "_lop_khoa", None)
            if cu is not None:
                try:
                    cu.destroy()
                except tk.TclError:
                    pass
                self._lop_khoa = None
        else:
            self._hien_khoa(k)
        self.after(60_000, self._soi_khoa)

    def _khoa_chan(self) -> bool:
        """True = đang khoá, đã báo rồi. Gọi ở ĐẦU mọi việc nặng.

        Chặn hai lớp: lớp phủ che giao diện, và chốt này ngay đầu từng việc.
        Lớp phủ có thể bị né (một phím tắt, một nút tôi quên tắt); chốt này thì
        không — mọi đường vào việc thật đều đi qua đây.
        """
        if khoa.kiem()["chay_duoc"]:
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
        lop = tk.Frame(self, background=m["nen"])
        lop.grid(row=1, column=0, sticky="nsew")
        lop.lift()
        self._lop_khoa = lop
        hop = tk.Frame(lop, background=m["tam"], padx=34, pady=28,
                       highlightthickness=1, highlightbackground=m["loi"])
        hop.place(relx=0.5, rely=0.42, anchor="center")

        tk.Label(hop, text="Hết hạn dùng thử", background=m["tam"],
                 foreground=m["loi"], font=("Segoe UI", 15, "bold")).pack(anchor="w")
        tk.Label(hop, text=k["ly_do"], background=m["tam"], foreground=m["chu"],
                 font=gd.CHU, justify="left", wraplength=520
                 ).pack(anchor="w", pady=(8, 16))

        tk.Label(hop, text="Đọc mã máy này cho người cấp mã:", background=m["tam"],
                 foreground=m["mo"], font=gd.CHU).pack(anchor="w")
        e_may = tk.Entry(hop, font=("Consolas", 14), width=16, justify="center",
                         relief="flat", background=m["noi"], foreground=m["chu"])
        e_may.insert(0, k["may"])
        e_may.configure(state="readonly")
        e_may.pack(anchor="w", pady=(4, 16))

        tk.Label(hop, text="Mã gia hạn:", background=m["tam"], foreground=m["mo"],
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
            ok, _moi, nhan = khoa.nhap_ma(self.v_ma.get())
            lbl.configure(text=nhan, foreground=m["xong"] if ok else m["loi"])
            lbl.pack(anchor="w", pady=(10, 0))
            if ok:
                #[[ KHONG tu go lop phu o day. De _soi_khoa() lam — no la cho
                #   DUY NHAT quyet dinh khoa hay mo. Hai cho cung quyet mot viec
                #   thi khi chung lech nhau se khong ai biet ben nao dung.
                #]]
                self.after(300, self._soi_khoa)

        self.btn_gia_han = ttk.Button(hang, text="Gia hạn", style="Chinh.TButton",
                                      command=gui)
        self.btn_gia_han.pack(side="left", padx=(8, 0))
        e.bind("<Return>", lambda _e: gui())
        e.focus_set()
        tk.Label(hop, text="Mọi tính năng đã khoá cho tới khi nhập mã hợp lệ.",
                 background=m["tam"], foreground=m["mo2"], font=gd.CHU_NHO
                 ).pack(anchor="w", pady=(18, 0))
        self.after(4000, self._lam_moi_ray)

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
        self._retouch_win = RetouchWindow(self, cha)
        self._retouch_win.grid(row=0, column=0, sticky="nsew")

    def _khung_khong_retouch(self, cha):
        """Bản không kèm retouch — nói rõ, và chỉ đúng chỗ tiếp theo."""
        the = gd.The(cha, "Phần Retouch tách khỏi bản này",
                     "Bản này chỉ có sáu khâu: nạp ảnh → phân tích → đẩy vào "
                     "Lightroom → Export → gói duyệt → học gu.", "cho")
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
        self.lbl_moi = tk.Label(self, anchor="w", padx=14, pady=7, justify="left",
                                background=gd.MAU["bang_canh_nen"],
                                foreground=gd.MAU["bang_canh_chu"], font=gd.CHU)
        self.lbl_moi.grid(row=0, column=0, sticky="ew")
        self.lbl_moi.grid_remove()
        self.after(15000, self._soi_ma)

    def _soi_ma(self):
        moi = [n for n, t in self._moc_ma().items()
               if t > self._moc_luc_mo.get(n, 0) + 1]
        if moi:
            self.lbl_moi.configure(
                text="⚠  Mã nguồn trên đĩa đã đổi (" + ", ".join(moi) +
                     ") — cửa sổ này vẫn chạy bản cũ trong bộ nhớ. "
                     "Đóng và mở lại AutoTone để dùng bản mới.")
            self.lbl_moi.grid()
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
                                    "Vào khâu 1 · Nạp ảnh để chọn thư mục")

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
                o["l_mo"].configure(text="→ Khâu 3 · Dựng ảnh duyệt")
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

    def _build_folder(self, cha):
        #[[ Nhan nhom nam o CHA, khung noi dung nam duoi no. Lam vay thi ba hang
        #   ben trong f giu nguyen so hang cu (0,1,2) — khong phai danh so lai
        #   thu gi dang chay tot chi de chen mot cai nhan.
        #]]
        gd.tieu_muc(cha, "Thư mục ảnh").grid(row=0, column=0, sticky="w",
                                             pady=(0, 8))
        f = ttk.Frame(cha)
        f.grid(row=1, column=0, sticky="ew")
        f.columnconfigure(0, weight=1)

        self.v_folder = tk.StringVar()
        e = ttk.Entry(f, textvariable=self.v_folder)
        e.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        e.bind("<Return>", lambda _e: self.scan_folder())
        ttk.Button(f, text="Chọn thư mục...", command=self.pick_folder).grid(row=0, column=1)

        row = ttk.Frame(f)
        row.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.v_recursive = tk.BooleanVar(value=False)
        ttk.Checkbutton(row, text="Gồm cả thư mục con", variable=self.v_recursive,
                        command=self.scan_folder).pack(side="left", padx=(0, 24))
        ttk.Label(row, text="Lấy thông số preset từ:").pack(side="left", padx=(0, 6))
        self.v_source = tk.StringVar(value=SOURCES[0][0])
        cbs = ttk.Combobox(row, textvariable=self.v_source, state="readonly",
                           values=[s[0] for s in SOURCES], width=42)
        cbs.pack(side="left")
        cbs.bind("<<ComboboxSelected>>", lambda _e: self.scan_folder())
        line = ttk.Frame(f)
        line.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        self.lbl_scan = ttk.Label(line, text="Chưa chọn thư mục", foreground=gd.MAU["mo"])
        self.lbl_scan.pack(side="left")
        self.btn_fix = ttk.Button(line, text="Cách tạo .xmp cho số còn lại",
                                  command=self.show_sidecar_help)
        # chỉ hiện khi thực sự thiếu — xem scan_folder()
        #[[ Nut xoa du lieu cu cua buoi nay.
        #
        #   Import lai mot buoi roi xuat thong so, tool van nho lan chay truoc:
        #   no thay catalog khac cai minh da ghi, ket luan "nguoi dung sua tay"
        #   va bo qua gan het buoi. Nut nay xoa moc goc + so ghi cu de lan chay
        #   sau coi buoi do la moi hoan toan.
        #
        #   Dat canh dong trang thai vi day dung la cho nguoi dung nhin thay so
        #   anh khong khop roi thac mac.
        #]]
        self.btn_xoa_cu = ttk.Button(line, text="Xoá dữ liệu cũ của buổi này",
                                     style="Pha.TButton",
                                     command=self.xoa_du_lieu_buoi)
        self.btn_xoa_cu.pack(side="right")

    def _build_options(self, cha):
        """Tuỳ chọn khâu 2, xếp BA CỘT để không phải cuộn.

        VÌ SAO BA CỘT
            Bản trước xếp bốn nhóm thành MỘT cột dọc rộng chừng 500 px, trong
            khi cửa sổ rộng ~1360 px. Hơn 60% chiều ngang bỏ trống, và cái giá
            đó trả bằng chiều dọc: đếm ra 946 px tuỳ chọn nhét vào 411 px chỗ
            thật sự có — nhìn thấy 43%, phải cuộn để thấy 57% còn lại.

            Chia ba cột thì 946 / 3 ≈ 315 px, lọt trong 411 px. Hết cuộn, và
            hết chỗ giấu tính năng.

        VÌ SAO KHÔNG CHIA ĐỀU 1:1:1
            Nhãn tiếng Việt của cột "Cách cân tone" dài nhất — riêng một dòng
            combobox "Da trắng hồng — máy đo + ngả hồng (khuyến dùng)" đã ~300
            px. Đây đúng là cái bẫy đã cắt cụt nhãn ở bản trước đó nữa (xem lịch
            sử: "Dua mat ve muc sang ch", "Khuon mat + diem bat net (kh"). Nên
            cột 1 rộng hơn: 5 / 4 / 4.

            Mọi dòng chữ phụ đều đặt wraplength — chữ dài thì XUỐNG DÒNG chứ
            không bị cắt. Đó là khác biệt giữa lần này và lần trước.

        Tên biến và lệnh giữ nguyên hết — chỉ đổi chỗ ngồi.
        """
        # ---------------------------------------------------------- biến
        self.v_mode = tk.StringVar(value=MODES[0][0])
        self.v_meter = tk.StringVar(value=METERS[0][0])
        self.v_wb = tk.StringVar(value=WBS[0][0])
        self.v_target = tk.StringVar(value="-1.19")
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
        self.v_burst = tk.BooleanVar(value=False)
        self.v_blink = tk.BooleanVar(value=False)
        self.v_upright = tk.BooleanVar(value=False)
        self.v_lrpush = tk.BooleanVar(value=True)
        self.v_gap_on = tk.BooleanVar(value=True)
        self.v_gap_can_sig = tk.BooleanVar(value=True)
        self.v_che_do_sang = tk.StringVar(
            value=at.DEFAULTS.get("che_do_sang", "tron"))

        # ------------------------------------------------------- ba cột
        #[[ BA COT, NHUNG TU CO LAI KHI CUA SO HEP.
        #
        #   Cua so nho nhat cho phep la 1180 px (root.minsize). Tru cot trai 252
        #   px va le, con ~840 px cho ba cot — cot hep nhat khi ay khoang 258 px,
        #   trong khi nhan dai nhat ("Auto Transform cho anh backdrop / man LED")
        #   can ~293 px. Xep cung ba cot la CAT CUT NHAN, dung cai bay da lam
        #   hong bo cuc hai lan truoc.
        #
        #   Nen: hoi Tk xem moi cot THUC SU can bao nhieu (winfo_reqwidth) roi
        #   chon so cot vua duoc. Do thay vi doan theo so ky tu — dung cho moi
        #   phong chu, moi muc DPI, moi ngon ngu.
        #]]
        khung = ttk.Frame(cha)
        khung.grid(row=0, column=0, sticky="new")
        c1 = ttk.Frame(khung)
        c2 = ttk.Frame(khung)
        c3 = ttk.Frame(khung)
        self._cot_tuy_chon = (khung, c1, c2, c3)
        self._so_cot_hien = 0
        khung.bind("<Configure>", self._xep_cot)

        WRAP = 300      # chữ phụ dài thì xuống dòng, không bị cắt

        def muc(cha_, chu, dau=False):
            gd.tieu_muc(cha_, chu).pack(anchor="w", pady=(0 if dau else 18, 8))

        def phu(cha_, chu, lui=20):
            ttk.Label(cha_, text=chu, style="Mo2.TLabel",
                      wraplength=WRAP, justify="left").pack(anchor="w",
                                                            padx=(lui, 0))

        def ct(cha_, bien, chu, mo=""):
            o = ttk.Frame(cha_)
            o.pack(fill="x", anchor="w")
            ttk.Checkbutton(o, text=chu, variable=bien,
                            command=self.refresh_plan).pack(anchor="w")
            if mo:
                phu(o, mo)
            return o

        #[[ CA COT 1 DUNG CHUNG MOT LUOI GRID, khong phai moi hang mot Frame.
        #
        #   VI SAO: de canh thang cot thi phai co be ngang chung cho moi nhan.
        #   Cach de nhat la dat width=15 cho tung nhan — VA DO LA CAI BAY. Tk
        #   CAT CUT chu dai hon width. Do bang Tk that: width=15 cat nhan "Tach
        #   canh khi cach"; con dat width=19 thi lai thua cho o nhan ngan, va
        #   con so 19 do phu thuoc phong chu — doi phong hoac doi muc phong to
        #   cua Windows la sai lai.
        #
        #   Grid thi Tk TU tinh be ngang cot 0 bang nhan rong nhat. Khong con
        #   con so ma thuat nao, va khong bao gio cat chu.
        #]]
        luoi: dict = {}          # cột -> (frame lưới, số hàng đang dùng)

        def _luoi(cot):
            """Lưới grid của một cột, dựng khi lần đầu cần tới.

            VÌ SAO GRID CHỨ KHÔNG width= TRÊN TỪNG NHÃN
                Muốn ô số thẳng cột thì mọi nhãn phải cùng bề ngang. Đặt
                width=15 là cách dễ nhất — VÀ LÀ CÁI BẪY: Tk CẮT CỤT chữ dài
                hơn width. Đo bằng Tk thật: width=15 cắt nhãn "Tách cảnh khi
                cách"; mà con số an toàn lại đổi theo phông và theo mức phóng
                to của Windows. Grid thì Tk tự tính bề ngang cột 0 theo nhãn
                rộng nhất — không còn con số ma thuật, không bao giờ cắt chữ.
            """
            if cot not in luoi:
                k = ttk.Frame(cot)
                k.pack(fill="x")
                k.columnconfigure(1, weight=1)
                luoi[cot] = [k, 0]
            return luoi[cot]

        def hop(cot, nhan, var, gia_tri, khi_doi):
            """Một hàng combobox: nhãn cột 0, hộp chọn chiếm hết phần còn lại."""
            k, r = _luoi(cot)
            ttk.Label(k, text=nhan).grid(row=r, column=0, sticky="w",
                                         padx=(0, 10), pady=3)
            cb = ttk.Combobox(k, textvariable=var, state="readonly",
                              values=gia_tri)
            cb.grid(row=r, column=1, sticky="ew", pady=3)
            cb.bind("<<ComboboxSelected>>", lambda _e: khi_doi())
            luoi[cot][1] = r + 1
            return cb

        def so(cot, nhan, var, lo, hi, buoc, mo=""):
            """Một hàng số: nhãn + ô số, chữ giải thích xuống dòng dưới."""
            k, r = _luoi(cot)
            lbl = ttk.Label(k, text=nhan)
            lbl.grid(row=r, column=0, sticky="w", padx=(0, 10), pady=3)
            sp = ttk.Spinbox(k, textvariable=var, from_=lo, to=hi,
                             increment=buoc, width=7, command=self.refresh_plan)
            sp.grid(row=r, column=1, sticky="w", pady=3)
            sp.bind("<FocusOut>", lambda _e: self.refresh_plan())
            sp.bind("<Return>", lambda _e: self.refresh_plan())
            r += 1
            if mo:
                #[[ Chu giai thich trai het hai cot va CO wraplength — dai bao
                #   nhieu cung xuong dong, khong bao gio bi cat. ]]
                ttk.Label(k, text=mo, style="Mo2.TLabel", wraplength=WRAP,
                          justify="left").grid(row=r, column=0, columnspan=2,
                                               sticky="w", pady=(0, 6))
                r += 1
            luoi[cot][1] = r
            return lbl, sp

        #[[ BA COT DUOC CAN THEO CHIEU CAO THAT, khong theo "nhom nao ve nhom
        #   nay cho gon". Do bang Tk that lan dau: c1 695 px, c2 363, c3 328 —
        #   nhoi vao o nhin 389 px, tuc VAN PHAI CUON, dung cai dang di chua.
        #   Nguyen nhan la may dong giai thich moi them lam c1 phinh len.
        #
        #   Nay chia lai cho ba cot xap xi nhau. Doi noi dung thi PHAI do lai —
        #   kiem_man_hinh.py hoi thang Tk "co phai cuon khong". ]]

        # ------------------------------------------- cột 1 · cách cân tone
        muc(c1, "Cách cân tone", dau=True)
        hop(c1, "Chế độ", self.v_mode, [m[0] for m in MODES],
            self._on_mode_change)
        # đổi cách đo sáng thì phải quét lại ảnh
        hop(c1, "Đo sáng", self.v_meter, [m[0] for m in METERS],
            self._on_meter_change)
        hop(c1, "Cân bằng trắng", self.v_wb, [w[0] for w in WBS],
            self.refresh_plan)

        #[[ Hai o nay chi co nghia voi mode absolute/hybrid — _on_mode_change()
        #   bat/tat chung, nen phai giu dung ten bien lbl_target/sp_target/
        #   lbl_blend/sp_blend. De ngay duoi o "Che do" vi chung phu thuoc no. ]]
        self.lbl_target, self.sp_target = so(
            c1, "Mặt sáng tới mức", self.v_target, -6.0, 0.0, 0.1,
            "Mức sáng ĐÍCH của da mặt (EV log2, càng âm càng tối). −1.19 lấy "
            "từ ảnh anh chấm tay: da đo −1.54 EV thì anh muốn +0.35. Chỉ dùng "
            "ở chế độ “Đưa mặt về mức sáng chuẩn” và “Trộn”.")
        self.lbl_blend, self.sp_blend = so(
            c1, "Độ trộn", self.v_blend, 0.0, 1.0, 0.05,
            "Chỉ ở chế độ “Trộn”. 0 = theo trung vị cảnh, 1 = theo mức đích "
            "ở trên.")

        #[[ ANH SANG CUA BUOI — nguoi dung chon, khong doan.
        #
        #   Khong co cach do nao noi chac duoc anh nay an anh sang ngay hay anh
        #   den, ma nguoi chup thi BIET. Hoi mot cau luc dau buoi re hon moi
        #   thuat toan va khong bao gio sai.
        #
        #   Ten la "anh sang ngay / anh den" CHU KHONG PHAI "ngoai troi / trong
        #   nha": buoi Day2 chup hoan toan ngoai troi — tu troi mo, xuong nha
        #   bat va mai che, toi sau khi toi den. Thu quyet dinh MAU la nguon
        #   sang chu khong phai co tuong hay khong. ]]
        muc(c1, "Ánh sáng của buổi")

        def rd(ma, chu, mo):
            o = ttk.Frame(c1)
            o.pack(fill="x", anchor="w")
            ttk.Radiobutton(o, text=chu, value=ma, variable=self.v_che_do_sang,
                            command=self._doi_che_do_sang).pack(anchor="w")
            phu(o, mo)

        rd("tron", "Trộn — tự tách theo mức sáng",
           f"Ngưỡng EV100 {at.DEFAULTS.get('ev_ngoai_troi')} · tính từ "
           "ISO + tốc + khẩu, không phải ISO không")
        rd("ngay", "Cả buổi ánh sáng ngày",
           "Kể cả ảnh chụp trong nhà bạt hay dưới mái che ban ngày")
        rd("den", "Cả buổi ánh đèn",
           "Hội trường, sân khấu, hoặc chụp sau khi trời tối")

        # ------------------------- cột 2 · giới hạn chỉnh + ghìm & bảo vệ
        muc(c2, "Giới hạn chỉnh", dau=True)
        so(c2, "Dìm tối đa −", self.v_maxev, 0.1, 5.0, 0.05,
           "Trần cho chiều DÌM TỐI. Đo ra phải dìm 1.8 EV mà đặt 1.00 thì chỉ "
           "dìm 1.00. Chiều kéo sáng do ô dưới quyết định.")
        so(c2, "Kéo sáng tối đa +", self.v_maxup, 0.1, 5.0, 0.05,
           "Trần cho chiều KÉO SÁNG, để riêng vì hai chiều không đối xứng: dìm "
           "quá tay chỉ mất công, kéo sáng thì cứu được ảnh ngược sáng hay "
           "chụp trước màn LED. Phần chống cháy sáng vẫn gác.")
        so(c2, "Mức độ can thiệp", self.v_gain, 0.1, 1.5, 0.05,
           "Nhân vào mức chỉnh trước khi kẹp trần. 1.0 = đủ như đo được, "
           "0.7 = dè dặt, 1.2 = mạnh tay.")

        #[[ GHIM & BAO VE doi THONG SO cua tung anh (highlights, shadows, mau,
        #   curve) — chung deu tra loi cau "anh nay sang toi dau".
        #   LOC & GOM CANH (cot 3) doi xem CO NHUNG ANH NAO va chung di voi
        #   nhau ra sao. Hai viec khac han, khi truy loi bao gio cung chi nghi
        #   toi mot trong hai. ]]
        muc(c2, "Ghìm & bảo vệ")
        ct(c2, self.v_hl, "Tự kéo Highlights khi cháy sáng",
           "Ngăn làm cháy thêm — không gỡ được chỗ đã cháy sẵn")
        ct(c2, self.v_sh, "Tự kéo Shadows khi bết tối")
        ct(c2, self.v_grade, "Đẩy tone về da trắng hồng", "Color Grading")
        ct(c2, self.v_curve, "Tự chỉnh Curve (parametric)")

        # ---------------------------------------- cột 3 · lọc & gom cảnh
        muc(c3, "Lọc & gom cảnh", dau=True)
        #[[ HAI LUAT TACH CANH, MOI LUAT MOT O TICH.
        #   Do that tren hai buoi: luat thoi gian chi tao 13/131 ranh gioi o
        #   buoi 1308 va 2/5 o buoi 0306 — phan con lai la boi canh. Nhung
        #   8/13 cap se bi gop lai neu tat no lech nhau tu 0.5 EV tro len,
        #   trong do mot cap lech 4.55 EV. Nen MAC DINH VAN BAT. ]]
        ct(c3, self.v_gap_on, "Tách cảnh theo thời gian")
        #[[ O so phut de NGAY duoi o tich cua chinh no. Truoc no nam o cot khac
        #   va chu phai viet "so phut o cot trai" — bat nguoi doc phai lia mat
        #   di cho khac de hieu mot cau. ]]
        self.lbl_gap, self.sp_gap = so(
            c3, "     nghỉ quá", self.v_gap, 0.5, 240, 0.5,
            "phút thì coi là cảnh mới")
        #[[ Do that buoi 1308: trong 13 nhat cat theo gio, 6 nhat co khung hinh
        #   y nguyen — chinh la nhung doan check-in chup ~30 phut mot phong. ]]
        o_cs = ct(c3, self.v_gap_can_sig, "…nhưng chỉ khi bối cảnh cũng đổi",
                  "Nghỉ lâu mà vẫn đứng nguyên một phông thì không tính là "
                  "cảnh mới")
        self.cb_gap_can_sig = o_cs.winfo_children()[0]
        ct(c3, self.v_scenesig, "Tách cảnh theo bối cảnh khung hình")
        ct(c3, self.v_level, "Đồng bộ sáng + màu trong cùng bối cảnh")

        #[[ CANH BAO KHI TAT CA HAI LUAT -> ca buoi la MOT canh. "Dong bo sang
        #   + mau" mac dinh BAT va no san phang moi anh ve trung vi cua canh —
        #   mot canh duy nhat nghia la san phang ca buoi ve mot moc. Do that
        #   buoi 1308: mot canh don le da co bien do 5.14 EV. ]]
        self.lbl_canh_canh = ttk.Label(c3, style="Canh.TLabel", wraplength=WRAP,
                                       justify="left")
        self.lbl_canh_canh.pack(anchor="w", pady=(8, 0))
        for b in (self.v_gap_on, self.v_scenesig, self.v_level):
            b.trace_add("write", lambda *_a: self._soi_tach_canh())
        self._soi_tach_canh()

        #[[ HAI BO LOC RIENG BIET — dung gop lam mot. Loc trung khung chi so
        #   cac anh trong CUNG mot loat; no khong tra loi "co ai nham mat
        #   khong". Loc mat doc EAR trong ear.csv, nguong 0.12 hieu chuan tren
        #   93 nhan that cua buoi 1308. ]]
        ct(c3, self.v_burst, "Lọc ảnh trùng khung",
           "Chụp liên tiếp — giữ 2 tấm đẹp nhất mỗi pose, ảnh loại gắn 1 sao")
        o = ct(c3, self.v_blink, "Lọc ảnh mắt không dùng được",
               "1 người hoặc nhóm 2–4; ảnh tập thể đông người bỏ qua. "
               "Đo luôn khi phân tích, chậm thêm ~0.8s/ảnh")
        self.cb_blink = o.winfo_children()[0]
        ct(c3, self.v_upright, "Auto Transform cho ảnh backdrop / màn LED")

        self._on_mode_change()

    def _xep_cot(self, _e=None):
        """Xếp ba cột tuỳ chọn thành 3 / 2 / 1 cột tuỳ bề ngang đang có.

        ĐO CHỨ KHÔNG ĐOÁN
            winfo_reqwidth() là bề ngang Tk THẬT SỰ cần để không cắt chữ, tính
            từ phông và DPI đang dùng. Đoán theo số ký tự thì sai ngay khi đổi
            phông hoặc đổi mức phóng của Windows — và cái giá của việc sai là
            nhãn bị cắt cụt, đúng lỗi đã gặp hai lần trước.

        CHỐNG VÒNG LẶP
            Xếp lại cột làm Tk bắn <Configure> lần nữa. Nên chỉ đụng vào khi SỐ
            CỘT thật sự đổi; số cột không đổi thì thoát ngay, không grid lại gì.
        """
        bo = getattr(self, "_cot_tuy_chon", None)
        if not bo:
            return
        khung, c1, c2, c3 = bo
        rong = khung.winfo_width()
        if rong <= 1:
            return                      # chưa vẽ lần nào, kích thước chưa có thật
        KHE = 24
        can = [c.winfo_reqwidth() for c in (c1, c2, c3)]
        if min(can) <= 1:
            return                      # nội dung chưa dựng xong

        if sum(can) + 2 * KHE <= rong:
            n = 3
        elif max(can[0] + can[1], can[2]) + KHE <= rong:
            n = 2
        else:
            n = 1
        if n == self._so_cot_hien:
            return
        self._so_cot_hien = n

        for c in (c1, c2, c3):
            c.grid_forget()
        for i in range(3):
            khung.columnconfigure(i, weight=0, uniform="")

        if n == 3:
            c1.grid(row=0, column=0, sticky="new", padx=(0, KHE))
            c2.grid(row=0, column=1, sticky="new", padx=(0, KHE))
            c3.grid(row=0, column=2, sticky="new")
            for i, w in ((0, 5), (1, 4), (2, 4)):
                khung.columnconfigure(i, weight=w)
        elif n == 2:
            c1.grid(row=0, column=0, sticky="new", padx=(0, KHE))
            c2.grid(row=0, column=1, sticky="new")
            c3.grid(row=1, column=0, columnspan=2, sticky="new", pady=(18, 0))
            khung.columnconfigure(0, weight=5)
            khung.columnconfigure(1, weight=4)
        else:
            for i, c in enumerate((c1, c2, c3)):
                c.grid(row=i, column=0, sticky="new", pady=(0 if i == 0 else 18, 0))
            khung.columnconfigure(0, weight=1)

    def _build_actions(self, cha):
        """Nút của khâu 2. CHỈ hai nút: chạy và dừng.

        VÌ SAO CHỈ CÒN HAI
            "2 · Ghi vào .xmp" và nút "Ghi và đẩy sang Lightroom" ở khâu 3 gọi
            CÙNG MỘT lệnh do_apply(). Hai nút cho một việc, ở hai màn hình, và
            _set_busy() phải nhớ khoá/mở cả hai cho khớp nhau. Giờ chỉ còn nút
            ở khâu 3 — đúng chỗ của nó, vì đó là khâu "đẩy vào Lightroom".

            "Xuất CSV" cũng chuyển sang khâu 3: nó xuất KẾT QUẢ, tức việc làm
            sau khi đã có kết quả, không phải việc của lúc đang phân tích.

            "Tự động theo dõi…" gỡ bỏ theo yêu cầu. Đường CLI `--watch` vẫn còn
            nguyên trong autotone.py, không đụng tới.
        """
        f = ttk.Frame(cha)
        f.grid(row=6, column=0, sticky="ew", pady=(14, 10))
        f.columnconfigure(2, weight=1)

        self.btn_analyze = ttk.Button(f, text="1 · Phân tích",
                                      style="Chinh.TButton",
                                      command=self.start_analyze)
        self.btn_analyze.grid(row=0, column=0, padx=(0, 6))
        self.btn_cancel = ttk.Button(f, text="Dừng", command=self.do_cancel,
                                     width=7)
        self.btn_cancel.grid(row=0, column=1)

        self.pb = ttk.Progressbar(f, mode="determinate")
        self.pb.grid(row=0, column=2, sticky="ew", padx=(12, 0))

    def _build_table(self, cha):
        gd.tieu_muc(cha, "Kết quả phân tích").grid(row=7, column=0, sticky="w",
                                                   pady=(0, 6))
        f = ttk.Frame(cha)
        f.grid(row=8, column=0, sticky="nsew")
        cha.rowconfigure(8, weight=1)
        f.columnconfigure(0, weight=1)
        f.rowconfigure(0, weight=1)

        #[[ height=8, khong de mac dinh 10. Mac dinh la ~210px chi rieng cho
        #   bang; cong nut va nhan thi vung ghim duoi doi hon 300px, va tren cua
        #   so thap thi tk BO HIEN nhung widget khong vua — nut "2 · Ghi vao
        #   .xmp" bien mat khong dau vet. Bang van cuon duoc, 8 dong la du de
        #   nhin, con 2 dong kia doi lay viec nut luon nhin thay.
        #]]
        self.tree = ttk.Treeview(f, columns=[c[0] for c in COLS], show="headings",
                                 selectmode="browse", height=8)
        for key, title, width, anchor in COLS:
            self.tree.heading(key, text=title, command=lambda k=key: self._sort_by(k))
            self.tree.column(key, width=width, anchor=anchor,
                             stretch=(key in ("file", "note")))
        self.tree.grid(row=0, column=0, sticky="nsew")

        sb = ttk.Scrollbar(f, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)

        #[[ MAU HANG TREN NEN TOI.
        #   Ba mau cu (#fff3e0, #ffebee, #ffcdd2) la pastel sang, ve tren nen
        #   #1e1e1e thi chu den bien mat. Doi sang nen dam cung sac: van doc duoc
        #   chu trang, va van phan biet duoc ba muc voi nhau.
        #]]
        self.tree.tag_configure("big", background="#3a2c12")      # chỉnh mạnh
        self.tree.tag_configure("clip", background="#3a1f1d")     # cháy nhiều
        self.tree.tag_configure("err", background="#4a201d")
        self.tree.tag_configure("zero", foreground=gd.MAU["mo2"])  # không đổi gì
        self.tree.bind("<Double-1>", self._show_detail)
        self._sort_state = (None, False)

    def _build_status(self):
        """Một thanh trạng thái duy nhất, chạy suốt đáy cửa sổ.

        Trước đây trạng thái nằm rải ba chỗ: một nhãn dưới bảng, một dòng gợi ý
        dưới nữa, và một ô riêng cho Lightroom. Ba chỗ thì lúc cần không biết
        nhìn đâu. Giờ: chuyện ĐANG XẢY RA ở thanh này; chuyện của riêng một khâu
        nằm trong khâu đó.
        """
        m = gd.MAU
        f = tk.Frame(self, background="#101010", padx=16, pady=7,
                     highlightthickness=1, highlightbackground=m["vien"])
        f.grid(row=2, column=0, sticky="ew")
        self.lbl_status = tk.Label(f, text="", anchor="w", background="#101010",
                                   foreground=m["chu"], font=gd.CHU)
        self.lbl_status.pack(side="left")
        self.lbl_hint = tk.Label(
            f, anchor="e", background="#101010", foreground=m["mo2"], font=gd.CHU,
            text="Sau khi ghi: trong Lightroom chọn ảnh → Metadata → Read Metadata from File")
        self.lbl_hint.pack(side="right")

    def _build_lrbox(self, cha):
        """Khâu 3 — đẩy thông số sang Lightroom và kiểm chứng nó đã nhận."""
        self.the_job = gd.The(cha, "", "", "")
        self.the_job.grid(row=0, column=0, sticky="ew")
        #[[ Giu lbl_job tro toi dong mo ta cua the: refresh_job_state() va
        #   _watch_job() dang goi self.lbl_job.configure(text=..., foreground=...)
        #   o sau chin cho khac nhau. Tro thang vao nhan ben trong the thi ca chin
        #   cho do van chay dung, khong phai sua cho nao.
        #]]
        self.lbl_job = self.the_job.l_mo

        cong = ttk.Frame(cha)
        cong.grid(row=1, column=0, sticky="w", pady=(16, 0))
        gd.tieu_muc(cong, "Cách đẩy").pack(anchor="w", pady=(0, 6))
        ttk.Checkbutton(cong, text="Đẩy thẳng vào Lightroom",
                        variable=self.v_lrpush).pack(anchor="w")
        ttk.Label(cong, style="Mo2.TLabel",
                  text="Khỏi phải chọn ảnh rồi Metadata → Read Metadata from File"
                  ).pack(anchor="w", padx=(20, 0))

        #[[ THANH TIEN DO RIENG CHO KHAU 3.
        #
        #   Truoc day chi co MOT thanh tien do, va no nam trong _build_actions()
        #   — tuc o khau 2. Nut "2 · Ghi vao .xmp" cung nam o do.
        #
        #   Nhung man hinh nay ten la "Khau 3 · Day vao Lightroom" va dong mo ta
        #   cua chinh no viet "Ghi thong so vao .xmp hoac day thang qua plugin".
        #   Nguoi dung dung o day, bam Ghi o khau 2 roi chuyen sang day xem ket
        #   qua — va KHONG THAY GI DONG DAY ca, vi thanh tien do o lai khau 2.
        #   Ho bao "thanh progress o phan 3 khong chay". Dung: no khong co that.
        #
        #   Nen: dat mot thanh tien do ngay tai day, va mot nut Ghi ngay tai day.
        #   Ca hai thanh cung an mot nguon tin (hang doi self.q), khong co ban
        #   sao trang thai thu hai de lech nhau.
        #]]
        tien = ttk.Frame(cha)
        tien.grid(row=2, column=0, sticky="ew", pady=(18, 0))
        tien.columnconfigure(3, weight=1)
        self.btn_ghi3 = ttk.Button(tien, text="Ghi và đẩy sang Lightroom",
                                   style="Chinh.TButton", command=self.do_apply)
        self.btn_ghi3.grid(row=0, column=0, padx=(0, 10))
        #[[ Xuat CSV chuyen tu khau 2 sang day: no xuat KET QUA, tuc viec lam
        #   sau khi da co ket qua — khong phai viec cua luc dang phan tich.
        #   Ten bien giu nguyen btn_csv vi _set_busy() dang goi toi no. ]]
        self.btn_csv = ttk.Button(tien, text="Xuất CSV", style="Pha.TButton",
                                  command=self.do_csv)
        self.btn_csv.grid(row=0, column=1, padx=(0, 10))
        self.pb3 = ttk.Progressbar(tien, mode="determinate", length=220)
        self.pb3.grid(row=0, column=2, padx=(0, 10))
        self.lbl_tien3 = ttk.Label(tien, style="Mo2.TLabel", text="")
        self.lbl_tien3.grid(row=0, column=3, sticky="w")

        bar = ttk.Frame(cha)
        bar.grid(row=3, column=0, sticky="w", pady=(14, 0))
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
                                "Chọn thư mục buổi chụp ở khâu 1 trước đã.")
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
                        "Gắn lý do ở khâu 6 rồi bấm “Học từ buổi này”.",
                        "tin" if n else "")
        self.txt_gu.configure(state="normal")
        self.txt_gu.delete("1.0", "end")
        self.txt_gu.insert("1.0", mo or "(chưa có)")
        self.txt_gu.configure(state="disabled")

    def refresh_job_state(self):
        """Đọc lại trạng thái job mới nhất trong thư mục jobs.

        Chạy cả lúc khởi động: job của lần chạy trước vẫn còn đó, nên mở app lên
        là biết ngay lần gửi gần nhất đã tới Lightroom chưa."""
        jobs = sorted(at.LR_JOB_DIR.glob("apply_*.tsv")) if at.LR_JOB_DIR.is_dir() else []
        if jobs:                                   # còn .tsv = plugin chưa áp
            self._watch_job(jobs[-1])
            return

        done = sorted(at.LR_JOB_DIR.glob("apply_*.done")) if at.LR_JOB_DIR.is_dir() else []
        if not done:
            self.lbl_job.configure(
                text="Chưa gửi lần nào. Bấm “2 · Ghi vào .xmp” để đẩy sang Lightroom.",
                foreground=gd.MAU["mo"])
            return

        last = done[-1]
        res = at.job_result(last)
        stamp = datetime.fromtimestamp(last.stat().st_mtime).strftime("%H:%M:%S")
        self.lbl_job.configure(
            text=f"✓ Lần gửi gần nhất {stamp} · {res or last.name}",
            foreground=gd.MAU["xong"])

    # -------------------------------------------------------------- trạng thái
    def _tien_do_3(self, done: int, total: int, viec: str) -> None:
        """Cập nhật thanh tiến độ của khâu 3. Im lặng nếu khâu 3 chưa dựng xong.

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

    def _set_busy(self, busy: bool):
        self.busy = busy
        state = "disabled" if busy else "normal"
        for b in (self.btn_all, self.btn_analyze, self.btn_undo):
            b.configure(state=state)
        self.btn_cancel.configure(state="normal" if busy else "disabled")
        has = bool(self.items) and not busy
        #[[ Nut Ghi va nut Xuat CSV deu nam o khau 3 (khong con ban sao o khau
        #   2 nua). Dung getattr vi _set_busy() duoc goi trong __init__ TRUOC
        #   khi _build_lrbox() chay xong — thieu no la app khong mo len duoc. ]]
        for ten in ("btn_ghi3", "btn_csv"):
            w = getattr(self, ten, None)
            if w is not None:
                w.configure(state="normal" if has else "disabled")

    def status(self, text: str, color: str = gd.MAU["chu"]):
        self.lbl_status.configure(text=text, foreground=color)

    def _invalidate_measurements(self):
        """Tuỳ chọn vừa đổi ảnh hưởng tới phép đo -> phải quét lại."""
        if self.items:
            self.items = []
            self.measure_key = None
            self.tree.delete(*self.tree.get_children())
            self.status("Cách đo sáng đã đổi — bấm “1 · Phân tích” để quét lại.", gd.MAU["canh"])
        self._set_busy(False)

    def _on_meter_change(self):
        # Mốc sáng của "khuôn mặt" và của "cả khung" là hai thang khác nhau —
        # giữ nguyên số cũ khi đổi cách đo là sai hẳn một quãng dài.
        face = dict(METERS).get(self.v_meter.get()) == "face"
        self.v_target.set("-1.19" if face else "-2.60")
        self.lbl_target.configure(text="Mặt sáng tới mức:" if face
                                  else "Mức sáng đích:")
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
                   **({"face_target_ev": self._num(self.v_target, -1.19)}
                      if dict(METERS).get(self.v_meter.get()) == "face"
                      else {"target_ev": self._num(self.v_target, -2.6)}),
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
                   max_ev_up=self._num(self.v_maxup, 1.0),
                   #[[ Anh sang cua buoi — nguoi dung chon o khau 2.
                   #   Thieu dong nay thi o chon la mot cai nut khong noi vao
                   #   dau ca: bam thay doi nhung phan tich khong he doi. ]]
                   che_do_sang=self.v_che_do_sang.get(),
                   source=self.source_value())
        return cfg

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
            "Xong rồi thì mỗi lần bấm “2 · Ghi vào .xmp”, Lightroom tự cập nhật "
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
            loi_ra = ("  →  Đổi ô “Nguồn” ở trên sang “Lightroom catalog qua "
                      "plugin” là không cần .xmp nữa."
                      if m > n else
                      "  →  Sang Lightroom chọn mấy ảnh đó rồi bấm Ctrl+S.")
            self.lbl_scan.configure(
                text=f"⚠ Chỉ {n}/{n + m} ảnh có sidecar .xmp — {m} ảnh còn lại "
                     f"sẽ bị bỏ qua.{loi_ra}  ",
                foreground=gd.MAU["loi"])
            self.btn_fix.pack(side="left")
        else:
            self.lbl_scan.configure(text=f"{n} ảnh RAW, đủ sidecar .xmp.",
                                    foreground=gd.MAU["xong"])
        self._invalidate_measurements()

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
        """Đọc lại bản xuất mới nhất. -> True nếu đổi so với lần đọc trước."""
        p = at.latest_catalog_export()
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

    def _dem_khop(self) -> int:
        #[[ Phai dung CHUNG mot ham chuan hoa voi ben ghi khoa (at._read_tsv),
        #   khong thi mot ben viet thuong mot ben khong va khop ra 0. ]]
        return sum(1 for p, _ in getattr(self, "pairs", [])
                   if at.khoa_duong_dan(p) in self.export)

    def _nhan_catalog(self):
        """Dòng trạng thái cho nguồn 'catalog'. Tách riêng để đồng hồ gọi được."""
        n = len(getattr(self, "pairs", []))
        hit = self._dem_khop()
        self.btn_fix.pack_forget()
        if not self.export:
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
                text=f"{n} ảnh RAW · CHƯA có bản xuất từ Lightroom.{them}  ",
                foreground=gd.MAU["loi"])
            self.btn_fix.pack(side="left")
        elif hit < n:
            #[[ NOI RO DANG DOC FILE NAO, NO BAO NHIEU TUOI, VA O THU MUC NAO.
            #
            #   Ban cu chi noi "chi khop 0 anh". Cau do dung ma vo dung: no khong
            #   phan biet duoc "Lightroom xuat thieu anh" voi "app dang doc nham
            #   ban xuat cua buoi khac". Ngay 4/9 la truong hop thu hai va mat
            #   gan mot tieng moi tim ra — trong khi chi can in ten file cung
            #   thu muc la thay ngay: export_20260903_... trong khi hom nay la
            #   4/9, va thu muc lai la %LOCALAPPDATA% chu khong phai o F noi
            #   Lightroom dang ghi.
            #]]
            them = ""
            dau = getattr(self, "_dau_xuat", None)
            if dau:
                p = Path(dau[0])
                tuoi = at.mo_ta_khoang(max(0.0, time.time() - dau[1] / 1e9))
                them = f"   ← đang đọc {p.name} ({tuoi}) trong {p.parent}"
            self.lbl_scan.configure(
                text=f"{n} ảnh RAW · bản xuất chỉ khớp {hit} ảnh — "
                     f"{n - hit} ảnh sẽ bị bỏ qua.{them}  ",
                foreground=gd.MAU["loi"])
            self.btn_fix.pack(side="left")
        else:
            self.lbl_scan.configure(
                text=f"{n} ảnh RAW · khớp đủ {hit} ảnh từ catalog Lightroom.",
                foreground=gd.MAU["xong"])

    def _soi_xuat(self):
        """Mỗi 3 giây: có bản xuất mới thì cập nhật lại dòng trạng thái.

        CHỈ đổi cái nhãn, KHÔNG gọi scan_folder(). scan_folder() kết thúc bằng
        _invalidate_measurements(), tức xoá sạch bảng đo — người dùng đo xong
        220 ảnh rồi sang Lightroom xuất lại là mất trắng công đo. Danh sách file
        trong thư mục không đổi khi Lightroom xuất, nên cũng không cần quét lại.
        """
        try:
            if (self.source_value() == "catalog" and getattr(self, "pairs", None)
                    and self._doc_xuat()):
                self._nhan_catalog()
        except Exception:                                    # noqa: BLE001
            pass
        self.after(3000, self._soi_xuat)

    def source_value(self) -> str:
        return dict(SOURCES).get(self.v_source.get(), "sidecar")

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
        hoi = (
            "Xoa moi thu tool da ghi nho cho buoi \u201c" + ten + "\u201d?\n\n"
            "  . moc goc (_autotone_baseline.tsv)\n"
            "  . so ghi cac lan chay truoc\n\n"
            "KHONG dung toi anh, .xmp, hay ban xuat tu Lightroom.\n\n"
            "Sau khi xoa, lan chay toi coi buoi nay la moi hoan toan \u2014 "
            "khong con anh nao bi bo qua vi \u201cda sua tay\u201d."
        )
        if not messagebox.askyesno("Xoa du lieu cu", hoi):
            return

        try:
            r = at.xoa_du_lieu_buoi(Path(d))
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
        msg = ("Da xoa: " + ", ".join(phan)) if phan else "Khong co gi de xoa."
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

    def start_all(self):
        """Phân tích -> lọc -> ghi và đẩy vào Lightroom, hỏi đúng một lần."""
        if self._khoa_chan():
            return
        root = self.folder()
        if not root:
            messagebox.showinfo("Thiếu thư mục", "Chọn thư mục chứa ảnh RAW trước đã.")
            return
        self.scan_folder()
        if not self.pairs:
            return
        cfg = self.read_cfg()
        viec = ["cân sáng toàn bộ ảnh"]
        if cfg.get("burst"):
            viec.append("lọc ảnh trùng khung (gắn 1 sao)")
        if cfg.get("blink"):
            viec.append("lọc ảnh mắt không dùng được (gắn 1 sao, chậm thêm ~0.8s/ảnh)")
        viec.append("ghi .xmp" + (" và đẩy thẳng vào Lightroom"
                                  if cfg.get("lr_push") else ""))
        if not messagebox.askokcancel(
                "Chạy hết",
                f"{len(self.pairs)} ảnh trong:\n{root}\n\n"
                + "\n".join(f"  • {v}" for v in viec)
                + "\n\nBản .xmp gốc được backup, hoàn tác được.\n"
                  "Bấm “Dừng” bất cứ lúc nào để ngắt giữa chừng.\n\nChạy?"):
            return
        #[[ Co noi chuoi truyen THANG vao start_analyze, khong dat san o day.
        #
        #   Ban truoc dat self.chuoi = True roi moi goi start_analyze(). Nhung
        #   start_analyze co bon duong ra som (chua chon thu muc, khong tim thay
        #   cap anh nao, thieu mediapipe...) va khong duong nao xoa co. Ra som
        #   mot lan la co ket lai True vinh vien; lan sau nguoi dung bam
        #   "1 · Phan tich" mot minh thi no TU GHI .xmp ma khong hoi ai.
        #
        #   Truyen tham so thi co chi duoc dat dung luc luong nen thuc su khoi
        #   dong, khong con duong nao de no ket lai.
        #]]
        self.start_analyze(chuoi=True)

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
        #   duong ra som — xem chu thich o start_all().
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
                + "\n\nSố này cũng hiện ở dòng trạng thái dưới bảng.")
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
        at.plan(self.items, self.cfg, self.folder(), getattr(self, "export", {}))
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
            self.lbl_hint.configure(
                text="Sau khi ghi: trong Lightroom chọn ảnh → Metadata → "
                     "Read Metadata from File", foreground=gd.MAU["mo"])
        self._set_busy(False)

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
        n = sum(1 for r in self.items if r["delta_ev"] or r["hl_adj"] or r["sh_adj"])
        ok = True if not hoi else messagebox.askokcancel(
            "Ghi vào sidecar .xmp",
            f"Sẽ ghi {len(self.items)} file .xmp ({n} ảnh có thay đổi).\n\n"
            "Bản gốc được backup tự động, hoàn tác được bằng nút “Hoàn tác...”.\n\n"
            "LƯU Ý: bước tiếp theo trong Lightroom là\n"
            "Metadata → Read Metadata from File, và thao tác đó GHI ĐÈ\n"
            "mọi chỉnh sửa đang có trong catalog của những ảnh này.\n"
            "Hãy chạy trước khi retouch tay.\n\nTiếp tục?",
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
                   "Plugin áp thẳng vào catalog; dòng trạng thái ở khâu 3 sẽ báo\n"
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
            before = at.export_stamp()
            try:
                at.request_export(root)
            except OSError as ex:
                messagebox.showerror("Không gửi được yêu cầu", str(ex))
                return
            self.lbl_job.unbind("<Button-1>")
            #[[ Tat CA BA nut cung goi _ask_lr_export.
            #   Bo sot btn_gu thi moi lan bam lai sinh them mot vong cho rieng
            #   (self.after lap lai moi giay) va them mot lan ghi request_export.
            #   Nguoi dung bam hai lan -> hai vong, hai lan thu goi duyet.
            #]]
            self.btn_read.configure(state="disabled")
            self.btn_learn.configure(state="disabled")
            self._nut_gu("disabled")

        if at.export_stamp() > before:
            self.btn_read.configure(state="normal")
            self.btn_learn.configure(state="normal")
            self._nut_gu("normal")
            done(at.latest_catalog_export())
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
            self.refresh_scan()
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
            cu = at.latest_catalog_export()
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
        if self._khoa_chan():
            return
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
        if self._khoa_chan():
            return
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

    def __init__(self, app: App, cha=None):
        #[[ cha = o luoi trong cua so chinh. Truyen None thi van la con truc tiep
        #   cua App — de doan ma cu con goi RetouchWindow(app) khong sap.
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

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(4, weight=1)

        # ---- thư mục
        box = ttk.LabelFrame(frm, text=" Thư mục ", padding=8)
        box.grid(row=0, column=0, sticky="ew")
        box.columnconfigure(1, weight=1)
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
        ttk.Label(box, text="Vào  (Lightroom vừa Export ra)").grid(row=0, column=0, sticky="w")
        ttk.Entry(box, textvariable=self.v_vao).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(box, text="Chọn...", command=lambda: self._pick(self.v_vao)
                   ).grid(row=0, column=2)
        ttk.Label(box, text="Ra   (ảnh đã retouch)").grid(row=1, column=0, sticky="w",
                                                          pady=(6, 0))
        ttk.Entry(box, textvariable=self.v_ra).grid(row=1, column=1, sticky="ew",
                                                    padx=6, pady=(6, 0))
        ttk.Button(box, text="Chọn...", command=lambda: self._pick(self.v_ra)
                   ).grid(row=1, column=2, pady=(6, 0))
        #[[ MOT DONG NOI KHI O "VAO" LECH VOI THU MUC EXPORT O KHAU 5.
        #
        #   Khau Export moi biet Lightroom xuat ra dau (nguoi dung go tay, hoac
        #   Export Filter bat duoc). Truoc day khau Retouch khong he biet, nen
        #   doi thu muc Export xong van phai vao day sua tay lan nua — va quen
        #   thi retouch chay tren dung thu muc cua BUOI TRUOC ma khong bao gi.
        #
        #   KHONG tu ghi de len cai nguoi dung da go: ho co the co tinh tro vao
        #   mot thu muc khac. Chi ghi de khi o dang trong hoac dang bam theo thu
        #   muc Export cu — con lai thi noi mot dong va de ho bam. ]]
        self.o_theo_export = ttk.Frame(box)
        self.o_theo_export.grid(row=2, column=0, columnspan=3, sticky="w",
                                pady=(8, 0))
        self.lbl_theo_export = ttk.Label(self.o_theo_export, style="Canh.TLabel",
                                         justify="left", wraplength=680)
        self.lbl_theo_export.pack(side="left")
        self.btn_theo_export = ttk.Button(
            self.o_theo_export, text="Dùng thư mục Export", style="Pha.TButton",
            command=self._nhan_theo_export)
        self.btn_theo_export.pack(side="left", padx=(10, 0))
        self.o_theo_export.grid_remove()
        self._export_cu = self.cf.get("theo_export", "")

        self.v_vao.trace_add("write", lambda *_: self._doi_vao())
        self.v_ra.trace_add("write", lambda *_: self._nho_thu_muc())

        # ---- tool
        tb = ttk.LabelFrame(frm, text=" Tool retouch ", padding=8)
        tb.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        tb.columnconfigure(0, weight=1)
        goc = rt.tim_tool()
        self.v_goc = tk.StringVar(value=str(goc) if goc else "")
        ttk.Entry(tb, textvariable=self.v_goc).grid(row=0, column=0, sticky="ew",
                                                    padx=(0, 6))
        ttk.Button(tb, text="Chọn...", command=self._pick_goc).grid(row=0, column=1)
        self.lbl_goc = ttk.Label(tb, foreground=gd.MAU["mo"], justify="left")
        self.lbl_goc.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        #[[ NOI RA KHI TOOL DA CHUYEN CHO.
        #
        #   8/9: nguoi dung chuyen tool tu F:\ToolCloneEvoto sang
        #   F:\Claude AI\ToolCloneEvoto. rt.tim_tool() nay tu do lai va ghi de
        #   duong dan moi — nhung LANG LE doi duong dan duoi tay nguoi dung
        #   cung la mot kieu hong. Neu ho chuyen nham, hoac con hai ban, ho
        #   phai duoc biet app dang tro vao ban nao.
        #
        #   Bao dung mot lan roi quen (rt.quen_da_chuyen()), khong nhac mai.
        #]]
        chuyen = rt.da_chuyen_cho()
        if chuyen:
            cu_, moi_ = chuyen
            l = ttk.Label(tb, style="Canh.TLabel", justify="left", wraplength=720,
                          text=f"Tool đã chuyển chỗ: {cu_}  →  {moi_}. "
                               f"App tự dò ra và ghi lại. Nếu đây không phải bản "
                               f"anh muốn dùng, bấm “Chọn…”.")
            l.grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))
            rt.quen_da_chuyen()

        #[[ THANH KEO DUNG DONG, theo danh sach saytool DANG co.
        #
        #   Truoc day dung tu rt.THANH_KEO ghi cung, nen khi ToolCloneEvoto them
        #   buoc liquify (thanh keo "Lam thon mat") thi giao dien khong hien ra
        #   va tinh nang do coi nhu khong ton tai. Gio hoi chinh saytool.
        #
        #   Hoi lan dau ton vai giay (saytool import torch ngay o dau file), nen
        #   dung o day — luc nguoi dung mo the Retouch — chu khong luc khoi dong.
        #]]
        sb = ttk.LabelFrame(
            frm, text=" Mức áp dụng  (0 = tắt hẳn tính năng đó) ", padding=8)
        sb.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        sb.columnconfigure(1, weight=1)
        self.khung_keo = sb
        self.v_muc = {}
        self._o_keo = []            # các ô đã dựng, để dựng lại khi đổi thư mục
        self._hang_keo = n = self._dung_thanh_keo(goc)

        #[[ MOT DONG NOI THAT KHI BANG THANH KEO KHONG PHAI CUA saytool.
        #
        #   9/9: may co saytool 0.9.5 (sau thanh keo) ma app hien dung ba —
        #   dung ba cai trong bang du phong viet cung. Khong mot dong nao noi vi
        #   sao, nen nhin tu phia nguoi dung thi app "binh thuong", chi la thieu
        #   ba tinh nang moi. Kieu hong te nhat: khong co dau vet de lan ra.
        #
        #   Nen tu day: dung bang du phong thi PHAI noi, va phai kem nut de thu
        #   lai — chu khong bat nguoi dung tat mo lai app de doan.
        #]]
        self.o_canh_keo = ttk.Frame(sb)
        self.lbl_keo = ttk.Label(self.o_canh_keo, style="Canh.TLabel",
                                 justify="left", wraplength=680)
        self.lbl_keo.pack(side="left")
        self.btn_keo_lai = ttk.Button(self.o_canh_keo, text="Đọc lại tính năng",
                                      style="Pha.TButton",
                                      command=self.do_doc_lai_keo)
        self.btn_keo_lai.pack(side="left", padx=(10, 0))

        opt = ttk.Frame(sb)
        self.o_tuy_chon = opt
        opt.grid(row=n, column=0, columnspan=4, sticky="w", pady=(8, 0))
        ttk.Label(opt, text="Máy:").pack(side="left")
        self.v_may = tk.StringVar(value=self.cf.get("may", "auto"))
        ttk.Combobox(opt, textvariable=self.v_may, width=7, state="readonly",
                     values=["auto", "cuda", "mps", "cpu"]).pack(side="left", padx=(4, 14))
        #[[ SO LUONG: 0 = de saytool tu do may.
        #
        #   Truoc day o nay bat dau tu 1 va mac dinh 1, vi ban saytool cu chon
        #   min(12, ncpu-2) roi 12 luong cung nap InsightFace len card 8 GB ->
        #   OOM -> sap ngay o anh dau (do that 3/9).
        #
        #   Ban 0.9.5 sua tan goc: co khoa quanh cho khoi tao mo hinh, va
        #   phan_cung.so_luong() chan boi CA so loi LAN bo nho con trong that.
        #   Ep mot con so tu day gio la VO HIEU HOA phan tu do do — xem ghi chu
        #   o retouch.LUONG_MAC_DINH. Nen mac dinh ve 0, va van cho ep tay.
        #]]
        ttk.Label(opt, text="Số luồng:").pack(side="left")
        self.v_luong = tk.IntVar(value=int(self.cf.get("luong", rt.LUONG_MAC_DINH)))
        ttk.Spinbox(opt, from_=0, to=16, width=4, textvariable=self.v_luong,
                    state="readonly").pack(side="left", padx=(4, 4))
        #[[ NOI RA KHI DANG EP MOT CON SO.
        #
        #   retouch.json cua may nay con "luong": 2 tu dot chua OOM hoi 3/9.
        #   Con so do TU NO khong sai, nhung phan_cung.so_luong() cua 0.9.5 co
        #   nhanh `if xin > 0: return min(xin, ...)` — nen ep mot con so la vo
        #   hieu hoa toan bo phan tu do theo so loi va bo nho con trong. Tren
        #   may 32 loi, ep 2 la tu bop toc do xuong con mot phan may.
        #
        #   Khong tu doi gia tri cua ho: chi noi ra va de mot nut. ]]
        self.lbl_luong = ttk.Label(opt, foreground="#8a8a8a")
        self.lbl_luong.pack(side="left")
        self.btn_luong0 = ttk.Button(opt, text="về 0", style="Pha.TButton",
                                     width=6,
                                     command=lambda: self.v_luong.set(0))
        self.v_luong.trace_add("write", lambda *_: self._nhac_luong())
        self._nhac_luong()
        #[[ CHE DO — tham so moi cua 0.9.5. "tiet_kiem" la duong thoat that su
        #   khi may dang ban: mot luong, o nho nhat. Truoc day khong co gi giua
        #   "chay binh thuong" va "khong chay". ]]
        ttk.Label(opt, text="Chế độ:").pack(side="left")
        self.v_che_do = tk.StringVar(
            value=self.cf.get("che_do", rt.CHE_DO_MAC_DINH))
        ttk.Combobox(opt, textvariable=self.v_che_do, width=10, state="readonly",
                     values=list(rt.CHE_DO)).pack(side="left", padx=(4, 14))
        self.v_lamlai = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt, text="Làm lại cả ảnh đã có kết quả",
                        variable=self.v_lamlai).pack(side="left")
        self.v_dequy = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt, text="Cả thư mục con",
                        variable=self.v_dequy).pack(side="left", padx=(14, 0))

        # ---- chạy
        bar = ttk.Frame(frm)
        bar.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.btn_run = ttk.Button(bar, text="▶  Chạy retouch", command=self.start)
        self.btn_run.pack(side="left")
        self.btn_stop = ttk.Button(bar, text="■  Dừng", command=self.stop,
                                   state="disabled")
        self.btn_stop.pack(side="left", padx=6)
        ttk.Button(bar, text="Kiểm tra",
                   command=lambda: self._kiem(chay_thu=True)).pack(side="left", padx=6)
        self.pb = ttk.Progressbar(bar, mode="determinate", length=180)
        self.pb.pack(side="left", padx=(14, 8))
        self.lbl_tt = ttk.Label(bar, foreground=gd.MAU["mo"])
        self.lbl_tt.pack(side="left")

        logf = ttk.LabelFrame(frm, text=" Nhật ký ", padding=4)
        logf.grid(row=4, column=0, sticky="nsew", pady=(8, 0))
        logf.columnconfigure(0, weight=1)
        logf.rowconfigure(0, weight=1)
        self.txt = tk.Text(logf, wrap="word", height=10, state="disabled",
                           font=("Consolas", 9))
        self.txt.grid(row=0, column=0, sticky="nsew")
        sc = ttk.Scrollbar(logf, orient="vertical", command=self.txt.yview)
        sc.grid(row=0, column=1, sticky="ns")
        self.txt.configure(yscrollcommand=sc.set)

        self._doi_vao()
        self._kiem()
        self.after(150, self._pump)
        #[[ Hoi tool NGAY khi mo, o luong nen. Truoc day chi hoi dong bo luc
        #   dung bang: hoi that bai la lang le roi ve ba thanh keo du phong va
        #   khong bao gio thu lai. ]]
        self.after(200, lambda: self._hoi_keo_nen(self.v_goc.get().strip().strip('"'))
                   if self.rt.hop_le(self.v_goc.get().strip().strip('"')) else None)

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
        for w in self._o_keo:
            try:
                w.destroy()
            except Exception:                                # noqa: BLE001
                pass
        self._o_keo = []
        cu = dict(self.v_muc)
        cu_rieng = {k: v.get() for k, v in getattr(self, "v_rieng", {}).items()
                    if self.v_bat_rieng.get(k) and self.v_bat_rieng[k].get()}
        self.v_muc = {}
        ds = self.rt.thanh_keo(goc)
        self._ds_keo = ds
        sb = self.khung_keo
        muc_cf = self.cf.get("muc", {}) or {}

        #[[ Biến của MỌI nhóm phải tồn tại kể cả khi thẻ đó không đang hiện —
        #   nếu chỉ tạo cho thẻ đang xem thì chuyển thẻ là mất mức vừa đặt. ]]
        if not hasattr(self, "v_rieng"):
            self.v_rieng, self.v_bat_rieng = {}, {}
        nhom = self.rt.nhom_mat(goc)
        for ten, _nhan, md, _goi in ds:
            for nh, _l in nhom:
                k = (nh, ten)
                if k in self.v_rieng:
                    continue
                gt = cu_rieng.get(k, muc_cf.get(f"{nh}:{ten}"))
                self.v_rieng[k] = tk.DoubleVar(
                    value=float(gt) if gt not in (None, "") else float(md))
                self.v_bat_rieng[k] = tk.BooleanVar(value=gt not in (None, ""))

        self._dung_the_nhom(goc)
        hang = 1
        for ten, nhan, md, goi in ds:
            try:
                bd = float(cu[ten].get()) if ten in cu else \
                    float(muc_cf.get(ten, md))
            except Exception:                                # noqa: BLE001
                bd = float(md)
            v = tk.DoubleVar(value=bd)
            self.v_muc[ten] = v
            if self.nhom_dang and not self.rt.theo_nhom(ten, goc):
                #[[ Buoc tu khai theo_nhom = False thi khong chia duoc — khong
                #   hien o the nhom, thay vi hien mot thanh keo khong co tac
                #   dung gi. ]]
                continue
            hang = self._mot_hang_keo(sb, hang, goc, ten, nhan, md, goi, v)
        return hang

    def _mot_hang_keo(self, sb, i, goc, ten, nhan, md, goi, v) -> int:
        """Một hàng thanh kéo — ở thẻ Chung hoặc ở thẻ một nhóm."""
        nh = self.nhom_dang
        #[[ KHONG dat width= o nhan. ttk.Label(width=N) CAT chu dai hon N, va
        #   ten cua 0.9.5 dai hon han ba ten cu: "Xoá khuyết điểm cơ thể" la 22
        #   ky tu, "Làm mờ nếp nhăn trán" 20 — width=16 cat ca hai. Cung loi da
        #   bat duoc bang Tk that o kiem_retouch_gui.py. ]]
        l1 = ttk.Label(sb, text=nhan)
        l1.grid(row=i, column=0, sticky="w", padx=(0, 6))
        self._o_keo.append(l1)

        if not nh:
            bien = v
        else:
            k = (nh, ten)
            bien = self.v_rieng[k]
            bat = self.v_bat_rieng[k]
            ck = ttk.Checkbutton(sb, text="riêng", variable=bat,
                                 command=lambda _k=k: self._doi_bat_rieng(_k))
            ck.grid(row=i, column=4, sticky="w", padx=(10, 0))
            self._o_keo.append(ck)

        sc = ttk.Scale(sb, from_=0, to=100, variable=bien, orient="horizontal")
        sc.grid(row=i, column=1, sticky="ew", padx=6)
        lb = ttk.Label(sb, width=4)
        lb.grid(row=i, column=2)
        chu = goi
        if nh:
            t = self.rt.tin_keo(goc).get(ten) or {}
            if nh in (t.get("bo_qua") or ()):
                chu = ("Bước này mặc định KHÔNG chạy cho nhóm này — tick "
                       "“riêng” là ép nó chạy. " + goi)
            elif t.get("ghi_chu"):
                chu = t["ghi_chu"]
        l2 = ttk.Label(sb, text=chu, foreground="#8a8a8a", wraplength=380,
                       justify="left")
        l2.grid(row=i, column=3, sticky="w", padx=(10, 0))
        self._o_keo += [sc, lb, l2]

        # đọc lại chính biến đó, không giữ giá trị chụp lúc dựng
        bien.trace_add("write",
                       lambda *_a, _v=bien, _l=lb: _l.configure(text=f"{_v.get():.0f}"))
        lb.configure(text=f"{bien.get():.0f}")
        if nh:
            self._mo_hang(sc, lb, self.v_bat_rieng[(nh, ten)].get())
            self._sc_theo[(nh, ten)] = (sc, lb)
        return i + 1

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

    def _dung_the_nhom(self, goc):
        """Hàng thẻ: Chung + từng nhóm khuôn mặt."""
        for w in getattr(self, "_o_the_nhom", []):
            try:
                w.destroy()
            except Exception:                                # noqa: BLE001
                pass
        self._o_the_nhom = []
        self._sc_theo = {}
        h = ttk.Frame(self.khung_keo)
        h.grid(row=0, column=0, columnspan=5, sticky="w", pady=(0, 8))
        self._o_the_nhom.append(h)
        self._nut_the = {}
        for ma, nhan in [("", "Chung")] + [tuple(x) for x in self.rt.nhom_mat(goc)]:
            b = ttk.Button(h, text=nhan, width=13,
                           command=lambda _m=ma: self.doi_nhom(_m))
            b.pack(side="left", padx=(0, 4))
            self._nut_the[ma] = b
        self.lbl_the = ttk.Label(h, style="Mo2.TLabel", text="")
        self.lbl_the.pack(side="left", padx=(12, 0))
        self._danh_dau_the()

    def _danh_dau_the(self):
        """Thẻ đang chọn nổi lên; thẻ có mức riêng mang một dấu chấm."""
        if not hasattr(self, "_nut_the"):
            return
        for ma, b in self._nut_the.items():
            co = any(v.get() for (nh, _t), v in self.v_bat_rieng.items()
                     if nh == ma) if ma else False
            nhan = dict([("", "Chung")] + [tuple(x) for x in self.rt.nhom_mat(
                self.v_goc.get().strip().strip('"'))]).get(ma, ma)
            b.configure(text=(nhan + " ·") if co else nhan,
                        style="Chinh.TButton" if ma == self.nhom_dang
                        else "Pha.TButton")
        if hasattr(self, "lbl_the"):
            self.lbl_the.configure(
                text="Mức dùng cho mọi nhóm không đặt riêng" if not self.nhom_dang
                else "Chỉ áp cho nhóm này; ô không tick “riêng” thì theo mức chung")

    def doi_nhom(self, ma: str):
        self.nhom_dang = ma
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

    def _dung_lai_thanh_keo(self, goc):
        """Dựng lại bảng thanh kéo và đẩy hàng tuỳ chọn xuống dưới."""
        self._hang_keo = n = self._dung_thanh_keo(goc)
        try:
            self.o_canh_keo.grid_configure(row=n)
            self.o_tuy_chon.grid_configure(row=n + 1)
        except Exception:                                    # noqa: BLE001
            pass
        self._canh_bao_keo(goc)

    def _canh_bao_keo(self, goc):
        """Nói ra khi bảng thanh kéo chỉ là bản dự phòng, và nói rõ vì sao."""
        if not hasattr(self, "lbl_keo"):
            return
        if self._keo_dang_hoi:
            self.lbl_keo.configure(
                text="Đang hỏi tool xem nó có những tính năng nào… "
                     "(lần đầu phải nạp torch nên có thể mất một phút)")
            self.o_canh_keo.grid(row=getattr(self, "_hang_keo", 1), column=0,
                                 columnspan=5, sticky="w", pady=(8, 0))
            self.btn_keo_lai.pack_forget()
            return
        if self.rt.da_hoi_that(goc):
            self.o_canh_keo.grid_remove()
            return
        vi_sao = self.rt.loi_hoi_keo(goc)
        self.lbl_keo.configure(
            text="Đang hiện bảng DỰ PHÒNG, không phải tính năng thật của tool. "
                 + (f"Vì: {vi_sao.splitlines()[0]}" if vi_sao
                    else "Chưa hỏi được tool.")
                 + "  Bấm “Đọc lại tính năng” để thử lại; chi tiết in ở Nhật ký.")
        self.btn_keo_lai.pack(side="left", padx=(10, 0))
        self.o_canh_keo.grid(row=getattr(self, "_hang_keo", 1), column=0,
                             columnspan=5, sticky="w", pady=(8, 0))
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
            self.o_theo_export.grid_remove()
        else:
            #[[ Ho da go mot duong dan KHAC. Noi ra, dung tu doi. ]]
            self.lbl_theo_export.configure(
                text=f"Khâu Export đang trỏ {d} — khác ô “Vào” ở trên.")
            self.o_theo_export.grid()
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
        self._nho_thu_muc()

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
            self.btn_luong0.pack(side="left", padx=(6, 14))
        else:
            self.lbl_luong.configure(text="(0 = tự dò theo máy)",
                                     foreground="#8a8a8a")
            self.btn_luong0.pack_forget()

    def _dem(self):
        vao = Path(self.v_vao.get().strip().strip('"') or ".")
        ra = Path(self.v_ra.get().strip().strip('"') or ".")
        tong, xong = self.rt.dem(vao, ra, self.v_dequy.get())
        self.pb.configure(maximum=max(tong, 1), value=xong)
        if not tong:
            self.lbl_tt.configure(text="Thư mục vào chưa có ảnh nào")
        else:
            self.lbl_tt.configure(
                text=f"{xong}/{tong} ảnh đã có kết quả — còn {tong - xong}"
                     + self._nhip())
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
        if not str(ra).strip():
            messagebox.showinfo("Thiếu thư mục ra", "Chọn nơi lưu ảnh đã retouch.",
                                parent=self)
            return
        #[[ Ra TRUNG Vao la mat anh goc: tool ghi de len chinh file dau vao,
        #   va lan chay sau se retouch chong len anh da retouch.
        #]]
        try:
            if ra.resolve() == vao.resolve():
                messagebox.showerror(
                    "Hai thư mục trùng nhau",
                    "Thư mục ra phải KHÁC thư mục vào.\n\n"
                    "Trùng nhau thì ảnh gốc bị ghi đè, và lần chạy sau sẽ "
                    "retouch chồng lên ảnh đã retouch.", parent=self)
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

        #[[ muc_day_du() chu khong phai v_muc: v_muc chi la MUC CHUNG. Bo mat
        #   muc rieng theo nhom o day thi nguoi dung dat rieng cho Nam xong bam
        #   Chay, va no chay y nhu khong dat gi — khong bao mot dong nao. ]]
        muc = self.muc_day_du()
        #[[ any(muc.values()) da dung cho ca muc rieng, vi muc_day_du() gop
        #   ca hai vao mot tu dien phang. Chi doi loi chu: "ba thanh keo" la
        #   con so cua ban cu, gio la sau va con them nam nhom. ]]
        if not any(float(v or 0) > 0 for v in muc.values()):
            messagebox.showinfo(
                "Chưa bật tính năng nào",
                "Mọi thanh kéo đều ở 0 — kể cả mức riêng theo nhóm. "
                "Không có gì để làm.", parent=self)
            return

        #[[ Chan TRUOC khi chay, dung de no chet o anh dau — xem _hoi_chep().
        #]]
        if not self._hoi_chep(self.muc_day_du()):
            return

        #[[ CHAN DUONG DAN CO DAU TIENG VIET — xem khong_ascii() ben retouch.py.
        #   TU 14/9: chi con chan khi ban saytool dang tro toi la ban CU (chua
        #   co saytool/duong_dan.py). Ban moi da doc/ghi duoc duong dan co dau,
        #   chan nua la chan oan — nguoi dung phai di doi ten thu muc vo co.
        #   Truyen goc vao de no nhin ban DANG DUNG ma quyet dinh, khong doan.
        #]]
        xau = self.rt.khong_ascii(vao, ra, goc=self.v_goc.get().strip().strip('"'))
        if xau:
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
        self.rt.ghi_cau_hinh({"vao": str(vao), "ra": str(ra), "muc": muc,
                              "may": self.v_may.get(),
                              "luong": int(self.v_luong.get()),
                              "che_do": self.v_che_do.get()})
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

        goc = Path(self.v_goc.get().strip().strip('"'))
        luong = int(self.v_luong.get())
        self.btn_run.configure(state="disabled")
        self.btn_stop.configure(state="normal")
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
                     f"{luong} luồng ===")

        #[[ MA SAP: tien trinh bi giet GIUA CHUNG, khong phai chay xong hay
        #   nguoi dung bam Dung. Gap mot trong so nay thi tu chay lai.
        #]]
        MA_SAP = (3221225477,   # 0xC0000005 ACCESS_VIOLATION
                  3221226356,   # 0xC0000374 HEAP_CORRUPTION
                  3221226505)   # 0xC0000409 FAIL_FAST
        self._dung_tay = False

        def work():
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
                _, truoc = self.rt.dem(vao, ra, self.v_dequy.get())
                ma_cuoi = 0
                try:
                    for loai, gt in self.rt.chay(
                            goc, vao, ra, muc, may=self.v_may.get(),
                            de_quy=self.v_dequy.get(), lam_lai=self.v_lamlai.get(),
                            luong=luong, che_do=self.v_che_do.get()):
                        if loai == "pid":
                            self.proc = gt
                            continue
                        if loai == "ma":
                            ma_cuoi = int(gt or 0)
                            continue      # giu lai: con co the chay tiep
                        self.log_q.put((loai, gt))
                except Exception:                                # noqa: BLE001
                    self.log_q.put(("loi", traceback.format_exc()))
                    self.log_q.put(("ma", 1))
                    return

                if ma_cuoi not in MA_SAP or self._dung_tay:
                    self.log_q.put(("ma", ma_cuoi))
                    return
                tong, sau = self.rt.dem(vao, ra, self.v_dequy.get())
                con = tong - sau
                if sau <= truoc or con <= 0:
                    self.log_q.put(("ma", ma_cuoi))
                    return
                self.log_q.put((
                    "dong",
                    f"=== sap (ma {ma_cuoi}) sau khi lam them {sau - truoc} anh"
                    f" - tu chay lai, con {con} anh (lan {lan + 1}) ==="))

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
        self.btn_run.configure(state="normal")
        self.btn_stop.configure(state="disabled")
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

    def on_close(self):
        if self.proc and self.proc.poll() is None:
            if not messagebox.askokcancel(
                    "Đang chạy", "Retouch đang chạy. Đóng cửa sổ sẽ dừng nó.\n\n"
                    "Ảnh đã làm xong vẫn giữ nguyên, chạy lại là tiếp tục.",
                    parent=self):
                return
            self.stop()
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

    if co == "--say-keo":
        import json
        try:
            from saytool.buoc import moi_thanh_keo
            ds = [[t.ten, t.nhan, float(t.mac_dinh), t.goi_y]
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
                              "--say-tainguyen"):
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

    root = tk.Tk()
    root.title("AutoTone — cân sáng tự động")
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
