#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""luoi_anh.py — Lưới ảnh nhỏ của cả buổi, kiểu thư viện ảnh của Evoto.

VÌ SAO CÓ (3/10 tối)
    User chọn bố cục "Lưới ảnh như Evoto": giữa màn hình là ảnh của cả buổi,
    mỗi tấm gắn ΔEV tool sẽ chỉnh; bảng số thành chế độ xem phụ. Nhìn ảnh thì
    nhận ra ngay tấm nào lệch, tấm nào đo nhầm — điều bảng số không nói được.

BA CHỖ PHẢI ĐÚNG, KHÔNG THÌ APP ĐỨNG HÌNH
    1. Chỉ VẼ ô đang nhìn thấy. Buổi 3 800 tấm mà tạo 3 800 ảnh Tk là vài trăm
       MB và vài giây đứng hình mỗi lần cuộn. Ở đây mỗi lần cuộn chỉ vẽ lại vài
       chục ô trong khung nhìn.
    2. Đọc ảnh ở LUỒNG NỀN, giao diện chỉ nhận kết quả. Đọc preview trong RAW
       mất vài chục ms một tấm; làm trên luồng giao diện là cuộn giật.
       Ảnh Tk (PhotoImage) thì CHỈ tạo ở luồng chính — luồng nền trả ảnh PIL.
    3. Đọc ô ĐANG NHÌN trước: hàng chờ là ngăn xếp (vào sau ra trước) — cuộn
       nhanh qua 500 tấm thì không phải chờ đọc hết 500 tấm vừa lướt qua.

ẢNH NHỎ CÓ LƯU ĐĨA
    Mỗi tấm đọc một lần rồi lưu JPEG nhỏ vào thư mục dữ liệu (anh_nho/), khoá
    theo đường dẫn + mtime + cỡ file — mở lại buổi là hiện ngay. Đầy quá
    TRAN_KHO tấm thì xoá bớt những tấm lâu không dùng.
"""
from __future__ import annotations

import hashlib
import os
import threading
import time
from collections import OrderedDict
from pathlib import Path

import tkinter as tk
from tkinter import ttk

import giao_dien as gd

try:
    from PIL import Image, ImageTk
except Exception:                                            # noqa: BLE001
    Image = ImageTk = None

CANH_KHO = 360          # cạnh dài ảnh nhỏ lưu đĩa — đủ cho ô to nhất
TRAN_KHO = 30000        # quá số tấm này thì dọn bớt kho ảnh nhỏ
SO_LUONG = 4            # luồng đọc ảnh


# ── kho ảnh nhỏ trên đĩa ─────────────────────────────────────────────────────
def thu_muc_kho() -> Path:
    try:
        import duong_dan as dd
        goc = dd.goc_du_lieu()
    except Exception:                                        # noqa: BLE001
        goc = Path(__file__).resolve().parent
    return goc / "anh_nho"


def khoa_kho(path: str) -> str | None:
    """Tên file trong kho: đổi file gốc (mtime/cỡ) là đổi khoá, ảnh cũ tự hết
    hiệu lực — không bao giờ hiện ảnh nhỏ của một file đã bị thay."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    h = hashlib.sha1(f"{path}|{st.st_mtime_ns}|{st.st_size}|{CANH_KHO}"
                     .encode("utf-8", "surrogatepass")).hexdigest()
    return f"{h[:2]}/{h[2:22]}.jpg"


def doc_anh_nho(path: str, kho: Path | None = None):
    """PIL Image (cạnh dài ≤ CANH_KHO) của một tấm — lấy từ kho nếu có, không
    thì đọc từ RAW rồi cất vào kho. None nếu không đọc được."""
    kho = kho or thu_muc_kho()
    k = khoa_kho(path)
    if k is not None:
        f = kho / k
        if f.is_file():
            try:
                with Image.open(f) as im:
                    im.load()
                    anh = im.convert("RGB")
                try:
                    os.utime(f, None)          # đánh dấu "mới dùng" cho lúc dọn kho
                except OSError:
                    pass
                return anh
            except Exception:                                # noqa: BLE001
                pass
    try:
        import autotone as at
        im = at.anh_nho(path, CANH_KHO)
    except Exception:                                        # noqa: BLE001
        im = None
    if im is None:
        return None
    if k is not None:
        try:
            f = kho / k
            f.parent.mkdir(parents=True, exist_ok=True)
            tam = f.with_suffix(".part")
            im.save(tam, "JPEG", quality=84)
            os.replace(tam, f)
        except OSError:
            pass
    return im


def don_kho(kho: Path | None = None, tran: int = TRAN_KHO) -> int:
    """Kho quá `tran` tấm thì xoá 1/4 số tấm lâu không dùng nhất. Trả về số
    tấm đã xoá. Chạy ở luồng nền, lỗi gì cũng bỏ qua — chỉ là bộ nhớ đệm."""
    kho = kho or thu_muc_kho()
    try:
        ds = [(f.stat().st_mtime, f) for f in kho.glob("*/*.jpg")]
    except OSError:
        return 0
    if len(ds) <= tran:
        return 0
    ds.sort()
    xoa = 0
    for _t, f in ds[: len(ds) // 4]:
        try:
            f.unlink()
            xoa += 1
        except OSError:
            pass
    return xoa


# ── luồng đọc ảnh: ngăn xếp, ô đang nhìn đi trước ────────────────────────────
class BoDoc:
    """N luồng nền đọc ảnh nhỏ. Yêu cầu mới nhất được làm trước (LIFO); một
    đường dẫn không còn được muốn nữa (đã cuộn qua) thì bỏ qua."""

    def __init__(self, so_luong: int = SO_LUONG, kho: Path | None = None):
        self._kho = kho
        self._ngan: list = []
        self._dang_muon: set = set()
        self._xong: list = []
        self.dang_doc = 0               # số tấm đang đọc dở ở các luồng
        self._khoa = threading.Lock()
        self._co = threading.Condition(self._khoa)
        self._dung = False
        self.luong = [threading.Thread(target=self._chay, daemon=True)
                      for _ in range(so_luong)]
        for t in self.luong:
            t.start()

    def muon(self, ds_path) -> None:
        """Thay danh sách đang muốn: ô đang nhìn + vài hàng kế tiếp."""
        with self._co:
            self._dang_muon = set(ds_path)
            co = set(self._ngan)
            for p in reversed(list(ds_path)):
                if p not in co:
                    self._ngan.append(p)
            self._co.notify_all()

    def lay_xong(self) -> list:
        with self._khoa:
            xong, self._xong = self._xong, []
        return xong

    def dung(self) -> None:
        with self._co:
            self._dung = True
            self._ngan.clear()
            self._co.notify_all()

    def _chay(self):
        while True:
            with self._co:
                while not self._dung and not self._ngan:
                    self._co.wait(0.5)
                if self._dung:
                    return
                p = self._ngan.pop()
                if p not in self._dang_muon:
                    continue
                self.dang_doc += 1
            try:
                im = doc_anh_nho(p, self._kho)
            except Exception:                                # noqa: BLE001
                im = None
            with self._khoa:
                self._xong.append((p, im))
                self.dang_doc -= 1

    def con_viec(self) -> bool:
        """Còn tấm chờ đọc hoặc đang đọc dở không."""
        with self._khoa:
            return bool(self._ngan) or self.dang_doc > 0


# ── lưới ảnh ─────────────────────────────────────────────────────────────────
class LuoiAnh(tk.Frame):
    """Lưới ảnh nhỏ, cuộn được, chỉ vẽ ô đang nhìn.

    ds = [{"path", "ten", "dev" (float|None), "canh" (int|None), "loai"
           ("err"|"clip"|"big"|"zero"|""), "sao1" (bool),
           "bo" (str: lý do ảnh SẼ KHÔNG được ghi, "" nếu được ghi),
           "dau" (str, tuỳ chọn: nhãn trạng thái thường, vd. "✓ đã làm")}, ...]

    Ô có "bo" vẽ ảnh tối hẳn đi kèm nhãn lý do góc phải trên — vẫn là ảnh của
    buổi, chỉ là nằm ngoài lần ghi.

    khi_chon(path)  — bấm một ô.   khi_mo(path) — bấm đúp một ô.

    dai=True: KHUNG THẤP (không đủ hai hàng ô) thì thành DẢI ẢNH một hàng cuộn
    ngang, kiểu dải ảnh dưới ảnh lớn của Evoto / Lightroom — kéo cao khung lên
    là lại thành lưới nhiều hàng. Lưới Cân tone không bật (dai=False).

    chon_nhieu=True: CHỌN NHIỀU TẤM như Lightroom — Ctrl + bấm thêm / bớt một
    tấm, Shift + bấm chọn một dãy, Ctrl+A chọn hết, Esc bỏ chọn nhiều. Tấm
    ĐANG XEM (dang_chon) không đổi khi Ctrl / Shift + bấm: đó là tấm nguồn khi
    Sync mức sang các tấm đã chọn. khi_doi_chon(ds_chon) — tập đã chọn vừa đổi.
    Ô có "rieng" mang nhãn "riêng" góc trái trên (ảnh có mức riêng).
    """

    tu_cuon = True          # Cuon nhường lăn chuột cho lưới

    def __init__(self, cha, khi_chon=None, khi_mo=None, nen: str | None = None,
                 khi_trong=None, dai: bool = False, chon_nhieu: bool = False,
                 khi_doi_chon=None):
        self._nen = nen or gd.MAU["toi"]
        super().__init__(cha, background=self._nen)
        self._khi_chon = khi_chon
        self._khi_mo = khi_mo
        self._chon_nhieu = bool(chon_nhieu)
        self._khi_doi_chon = khi_doi_chon
        self.ds: list = []
        self._vi_tri: dict = {}            # path -> chỉ số
        self.dang_chon: str | None = None
        #[[ Tap DA CHON luon gom tam dang xem (dang_chon) — chon mot tam thi tap
        #   chi co tam do. Chon nhieu chi khi chon_nhieu=True. ]]
        self.da_chon: set = set()
        lh = gd.don_vi(self)
        #[[ co_o la be ngang TOI THIEU cua o. That ra o gian cho vua kin be
        #   ngang luoi (_sap_xep -> self._ow) nhu luoi Evoto / Lightroom: chia
        #   deu thi khong con hai dai trong hai ben. Gian toi da < 2*co_o + khe
        #   (rong hon thi da du cho them mot cot) = ~330 px, van duoi CANH_KHO
        #   nen anh nho khong phai phong to. ]]
        self.co_o = round(lh * 10.5)
        self._ow = self.co_o
        self._khe = max(8, round(lh * 0.6))
        self._cao_chu = lh + 4
        self._cot = 1
        self._cho_dai = bool(dai)
        self.ngang = False                 # đang là dải một hàng
        self._cao_dai = 0                  # cao ô ảnh ở chế độ dải (đã lượng tử)
        self._anh_tk: OrderedDict = OrderedDict()   # (path, cỡ) -> PhotoImage
        self._anh_pil: OrderedDict = OrderedDict()  # path -> PIL (đã đọc)
        self._hong: set = set()
        self._bo_doc: BoDoc | None = None
        self._hen_bom = None
        self._hen_ve = None

        self.canvas = tk.Canvas(self, background=self._nen, highlightthickness=0,
                                borderwidth=0, takefocus=1)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.thanh = ttk.Scrollbar(self, orient="vertical", command=self._cuon_y,
                                   style="Toi.Vertical.TScrollbar")
        self.thanh.grid(row=0, column=1, sticky="ns")
        self.thanh_x = ttk.Scrollbar(self, orient="horizontal", command=self._cuon_x,
                                     style="Toi.Horizontal.TScrollbar")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.canvas.configure(yscrollcommand=self._dat_thanh)

        # ô trống: chưa có ảnh nào
        self.o_trong = tk.Frame(self.canvas, background=self._nen)
        self.lbl_trong = tk.Label(self.o_trong, text="", background=self._nen,
                                  foreground=gd.MAU["mo"], font=gd.CHU,
                                  justify="center", wraplength=420)
        self.lbl_trong.pack(pady=(0, 14))
        self.nut_trong = gd.NutTron(self.o_trong, "Chọn thư mục buổi chụp",
                                    kieu="chinh", icon="thu_muc", nen=self._nen,
                                    command=khi_trong)
        self.nut_trong.pack()
        self._cua_trong = self.canvas.create_window(0, 0, window=self.o_trong,
                                                    anchor="center")

        c = self.canvas
        c.bind("<Configure>", lambda _e: self._sap_xep(), add="+")
        c.bind("<MouseWheel>", self._lan)
        c.bind("<Button-4>", lambda _e: self._lan_linux(-1))
        c.bind("<Button-5>", lambda _e: self._lan_linux(1))
        c.bind("<Button-1>", self._bam)
        c.bind("<Double-Button-1>", self._bam_dup)
        if self._chon_nhieu:
            #[[ Rang buoc RIENG cho Ctrl / Shift + bam: Tk chon rang buoc khop
            #   NHAT, nen bam tron van vao _bam thuong. KHONG doc bit 0x8 cua
            #   e.state — tren Windows do la NumLock.
            #
            #   "<Command-Button-1>" CHI rang buoc tren Mac (aqua). Ngoai Mac Tk
            #   KHONG bao loi ten "Command" — no la ten khac cua Mod1, tuc
            #   "<Mod1-Button-1>", ma Mod1 tren Windows CHINH LA NumLock. Ban 4/10
            #   sang tuong "Tk bao loi ten la" nen rang buoc o moi may: NumLock bat
            #   thi MOI lan bam thuong khop rang buoc Command (khop nhieu hon
            #   "<Button-1>") va thanh "chon them" — tam dang xem dung yen, anh
            #   lon khong doi (may user, 4/10 trua: "bam vao 1 anh o duoi luoi anh
            #   thi can hien thi ngay tren khung to"). ]]
            c.bind("<Control-Button-1>", lambda e: self._bam(e, kieu="them"))
            c.bind("<Shift-Button-1>", lambda e: self._bam(e, kieu="day"))
            if str(c.tk.call("tk", "windowingsystem")) == "aqua":
                c.bind("<Command-Button-1>", lambda e: self._bam(e, kieu="them"))
            for phim in ("<Control-a>", "<Control-A>"):
                c.bind(phim, lambda _e: (self.chon_het(), "break")[1])
            c.bind("<Escape>", lambda _e: self._thu_chon())
        for phim, (dx, dy) in (("<Left>", (-1, 0)), ("<Right>", (1, 0)),
                               ("<Up>", (0, -1)), ("<Down>", (0, 1))):
            c.bind(phim, lambda _e, d=(dx, dy): self._di_phim(*d))
        c.bind("<Return>", lambda _e: self._mo_dang_chon())
        self.bind("<Destroy>", self._huy, add="+")
        self.dat_trong("Chưa chọn buổi chụp.\nChọn thư mục ảnh RAW để bắt đầu.")

    def _dat_thanh(self, lo, hi):
        """Thanh cuộn tự ẩn khi lưới vừa một màn — như Cuon."""
        (self.thanh.grid_remove() if float(lo) <= 0.0 and float(hi) >= 1.0
         else self.thanh.grid())
        self.thanh.set(lo, hi)

    def _dat_thanh_x(self, lo, hi):
        if float(lo) <= 0.0 and float(hi) >= 1.0:
            self.thanh_x.grid_remove()
        else:
            self.thanh_x.grid(row=1, column=0, sticky="ew")
        self.thanh_x.set(lo, hi)

    # ---------------------------------------------------------------- dữ liệu
    def dat_ds(self, ds: list, giu_cuon: bool = False) -> None:
        """Đổi danh sách ô. giu_cuon=True khi chỉ đổi số (ΔEV) chứ không đổi
        tập ảnh — khỏi nhảy về đầu lưới mỗi lần kéo một thanh trượt."""
        cu = [o["path"] for o in self.ds]
        self.ds = list(ds)
        self._vi_tri = {o["path"]: i for i, o in enumerate(self.ds)}
        moi = [o["path"] for o in self.ds]
        if not giu_cuon or cu != moi:
            if set(cu) != set(moi):
                self.canvas.yview_moveto(0)
                self.canvas.xview_moveto(0)
        if self.dang_chon not in self._vi_tri:
            self.dang_chon = None
        cu_chon = set(self.da_chon)
        self.da_chon = {p for p in self.da_chon if p in self._vi_tri}
        if self.dang_chon is not None:
            self.da_chon.add(self.dang_chon)
        self.canvas.itemconfigure(self._cua_trong,
                                  state="normal" if not self.ds else "hidden")
        self._sap_xep()
        if self.da_chon != cu_chon:
            self._bao_doi_chon()

    def dat_trong(self, chu: str, co_nut: bool = True) -> None:
        """Chữ hiện giữa lưới khi chưa có ảnh nào."""
        self.lbl_trong.configure(text=chu)
        (self.nut_trong.pack() if co_nut else self.nut_trong.pack_forget())

    def chon(self, path: str | None, cuon_toi: bool = True) -> None:
        """Đặt tấm đang xem. Tấm đó đã nằm trong nhóm đang chọn thì GIỮ nhóm
        (đếm lại / vẽ lại lưới không làm mất các tấm đã Ctrl + bấm); không thì
        chỉ còn chọn mỗi tấm đó."""
        cu_chon = set(self.da_chon)
        self.dang_chon = path if path in self._vi_tri else None
        if self.dang_chon is None:
            self.da_chon = set()
        elif self.dang_chon not in self.da_chon:
            self.da_chon = {self.dang_chon}
        if cuon_toi and self.dang_chon is not None:
            self._cuon_toi(self._vi_tri[self.dang_chon])
        self._ve()
        if self.da_chon != cu_chon:
            self._bao_doi_chon()

    def ds_chon(self) -> list:
        """Các tấm đang chọn, theo thứ tự trong lưới (luôn gồm tấm đang xem)."""
        return [o["path"] for o in self.ds if o["path"] in self.da_chon]

    def chon_het(self) -> None:
        """Ctrl+A: chọn mọi tấm (tấm đang xem giữ nguyên)."""
        if not self._chon_nhieu or not self.ds:
            return
        if self.dang_chon is None:
            self.chon(self.ds[0]["path"], cuon_toi=False)
            if self._khi_chon is not None:
                self._khi_chon(self.dang_chon)
        self.da_chon = {o["path"] for o in self.ds}
        self._ve()
        self._bao_doi_chon()

    def _thu_chon(self):
        """Esc: chỉ còn chọn tấm đang xem."""
        if len(self.da_chon) > 1:
            self.da_chon = {self.dang_chon} if self.dang_chon else set()
            self._ve()
            self._bao_doi_chon()

    def _bao_doi_chon(self):
        if self._khi_doi_chon is not None:
            try:
                self._khi_doi_chon(self.ds_chon())
            except Exception:                                # noqa: BLE001
                import traceback
                traceback.print_exc()

    # ---------------------------------------------------------------- hình học
    def _kich_thuoc_o(self):
        w = self._ow
        if self.ngang:
            return w, self._cao_dai          # dải ảnh: không có dòng tên dưới ô
        return w, round(w * 2 / 3) + self._cao_chu + 6

    def _nguong_dai(self) -> int:
        """Khung thấp hơn mức này (không đủ hai hàng ô lưới) thì thành dải."""
        oh = round(self.co_o * 2 / 3) + self._cao_chu + 6
        return 2 * oh + 3 * self._khe

    def _doi_che_do(self, ngang: bool):
        c = self.canvas
        self.ngang = ngang
        if ngang:
            self.thanh.grid_remove()
            c.configure(yscrollcommand="", xscrollcommand=self._dat_thanh_x)
            c.yview_moveto(0)
        else:
            self.thanh_x.grid_remove()
            c.configure(xscrollcommand="", yscrollcommand=self._dat_thanh)
            c.xview_moveto(0)

    def _sap_xep(self):
        c = self.canvas
        rong = max(1, c.winfo_width())
        cao = max(1, c.winfo_height())
        ngang = self._cho_dai and cao < self._nguong_dai()
        doi = ngang != self.ngang
        if doi:
            self._doi_che_do(ngang)
        if ngang:
            #[[ DAI ANH: o cao theo khung, rong = 3/2 cao. Cao luong tu 8 px:
            #   keo thanh chia tung diem anh la moi diem anh mot co o moi, moi
            #   co o mot loat PhotoImage moi — keo thanh chia se giat. ]]
            ah = max(24, (cao - 2 * self._khe) // 8 * 8)
            doi = doi or ah != self._cao_dai
            self._cao_dai = ah
            self._ow = round(ah * 3 / 2)
            self._cot = max(1, len(self.ds))
            tong = self._khe + len(self.ds) * (self._ow + self._khe)
            c.configure(scrollregion=(0, 0, max(tong, rong), cao),
                        xscrollincrement=self._ow + self._khe)
            c.coords(self._cua_trong, rong / 2, cao / 2)
            #[[ Chi keo toi tam dang chon khi VUA doi che do / co o — khong
            #   phai moi lan dat_ds: dem lai moi 1,5 giay luc dang chay ma keo
            #   dai ve tam dang chon thi nguoi dung khong luot dai di dau duoc. ]]
            if doi and self.dang_chon in self._vi_tri:
                self._cuon_toi(self._vi_tri[self.dang_chon])
            self._ve()
            return
        self._cot = max(1, (rong - self._khe) // (self.co_o + self._khe))
        self._ow = max(self.co_o // 2, (rong - self._khe) // self._cot - self._khe)
        ow, oh = self._kich_thuoc_o()
        hang = (len(self.ds) + self._cot - 1) // self._cot
        cao = self._khe + hang * (oh + self._khe)
        c.configure(scrollregion=(0, 0, rong, max(cao, c.winfo_height())))
        c.coords(self._cua_trong, rong / 2, max(c.winfo_height(), 200) / 2)
        self._ve()

    def _o_xy(self, i):
        ow, oh = self._kich_thuoc_o()
        if self.ngang:
            return self._khe + i * (ow + self._khe), self._khe
        rong = max(1, self.canvas.winfo_width())
        du = rong - self._khe - self._cot * (ow + self._khe)
        x0 = self._khe + max(0, du) // 2
        hng, cot = divmod(i, self._cot)
        return (x0 + cot * (ow + self._khe), self._khe + hng * (oh + self._khe))

    def _o_nhin_ngang(self):
        """(ô đầu, ô cuối + 1) đang lọt trong khung — chế độ dải."""
        c = self.canvas
        ow, _oh = self._kich_thuoc_o()
        x0 = c.canvasx(0)
        x1 = x0 + c.winfo_width()
        i0 = max(0, int((x0 - self._khe) // (ow + self._khe)))
        i1 = min(len(self.ds), int((x1 - self._khe) // (ow + self._khe)) + 1)
        return i0, i1

    def _hang_nhin(self):
        c = self.canvas
        ow, oh = self._kich_thuoc_o()
        y0 = c.canvasy(0)
        y1 = y0 + c.winfo_height()
        h0 = max(0, int((y0 - self._khe) // (oh + self._khe)))
        h1 = int((y1 - self._khe) // (oh + self._khe)) + 1
        return h0, h1

    # ---------------------------------------------------------------- vẽ
    def _ve(self):
        if self._hen_ve is None:
            self._hen_ve = self.after_idle(self._ve_that)

    def _ve_that(self):
        self._hen_ve = None
        c = self.canvas
        try:
            c.delete("o")
        except tk.TclError:
            return
        if not self.ds:
            return
        ow, oh = self._kich_thuoc_o()
        if self.ngang:
            ah = oh
            i0, i1 = self._o_nhin_ngang()
            man = max(1, i1 - i0)
        else:
            ah = round(ow * 2 / 3)
            h0, h1 = self._hang_nhin()
            i0, i1 = h0 * self._cot, min(len(self.ds), (h1 + 1) * self._cot)
            man = max(1, (h1 - h0)) * self._cot
        can_doc = []
        m = gd.MAU
        f_nho = gd._phong(self, gd.CHU_NHO)
        f_so = gd._phong(self, ("Segoe UI", 8, "bold"))
        nhieu = len(self.da_chon) > 1
        for i in range(i0, i1):
            o = self.ds[i]
            x, y = self._o_xy(i)
            chon = o["path"] == self.dang_chon
            #[[ Tam DA CHON (Ctrl / Shift + bam) ma khong phai tam dang xem: nen
            #   sang hon + vien trang — phan biet duoc voi tam dang xem (vien
            #   vang), nhu Lightroom. ]]
            phu = nhieu and not chon and o["path"] in self.da_chon
            bo = o.get("bo") or ""
            # nền khung ảnh
            c.create_rectangle(x, y, x + ow, y + ah, fill="#33363c" if phu else "#202226",
                               outline=m["nhan"] if chon else "#202226",
                               width=2 if chon else 1, tags=("o",))
            a = self._anh_cho(o["path"], ow - 4, ah - 4, mo=bool(bo))
            if a is not None:
                c.create_image(x + ow / 2, y + ah / 2, image=a, tags=("o",))
            elif o["path"] in self._hong:
                c.create_text(x + ow / 2, y + ah / 2, text="không đọc được ảnh",
                              fill=m["mo2"], font=f_nho, tags=("o",))
            else:
                can_doc.append(o["path"])
            if chon:
                c.create_rectangle(x - 1, y - 1, x + ow + 1, y + ah + 1,
                                   outline=m["nhan"], width=2, tags=("o",))
            elif phu:
                c.create_rectangle(x - 1, y - 1, x + ow + 1, y + ah + 1,
                                   outline="#e8e9eb", width=2, tags=("o", "phu"))
            # nhãn góc: cảnh (trái trên), ΔEV (phải dưới), 1 sao (trái dưới)
            y_nw = y + 4
            if o.get("canh") is not None:
                self._nhan(c, x + 4, y_nw, f"C{o['canh']}", "nw", "#111214",
                           "#d9dadc", f_nho)
                y_nw += f_nho.metrics("linespace") + 6
            if o.get("rieng"):
                #[[ Anh co MUC RIENG (Retouch: da keo / Sync rieng cho tam nay).
                #   Chu chu khong dung ky hieu but chi: nhin la hieu, va khong
                #   tuy vao phong co ky hieu do hay khong. ]]
                self._nhan(c, x + 4, y_nw, "riêng", "nw", "#3a3214", "#ffde17", f_nho)
            dev = o.get("dev")
            if dev is not None:
                loai = o.get("loai", "")
                nen = {"err": "#7a2a24", "clip": "#6a3320", "big": "#6b5410",
                       "zero": "#2b2d31"}.get(loai, "#1d2b22" if dev > 0 else "#2a2230")
                chu = m["mo"] if loai == "zero" else "#f2f2f2"
                txt = "lỗi" if loai == "err" else f"{dev:+.2f}"
                self._nhan(c, x + ow - 4, y + ah - 4, txt, "se", nen, chu, f_so)
            if o.get("sao1"):
                self._nhan(c, x + 4, y + ah - 4, "1★", "sw", "#5a1f1b", "#f3b7b2",
                           f_so)
            if bo:
                self._nhan(c, x + ow - 4, y + 4, bo, "ne", "#111214", m["mo"],
                           f_nho)
            elif o.get("dau"):
                #[[ "dau": nhan trang thai THUONG (vd. "✓ da lam" o Retouch) —
                #   anh giu nguyen do sang, khac "bo" la anh nam NGOAI. ]]
                self._nhan(c, x + ow - 4, y + 4, o["dau"], "ne", "#1d3a28",
                           "#9be3b5", f_nho)
            # tên file (dải ảnh thì không — tên nằm ở thanh trên ảnh lớn)
            if self.ngang:
                continue
            ten = o.get("ten", "")
            c.create_text(x + 2, y + ah + 5, text=self._cat(ten, f_nho, ow - 4),
                          anchor="nw",
                          fill=(m["chu"] if chon else (m["mo2"] if bo else m["mo"])),
                          font=f_nho, tags=("o",))
        # đọc trước thêm hai màn
        sau = min(len(self.ds), i1 + 2 * man)
        for i in range(i1, sau):
            p = self.ds[i]["path"]
            if p not in self._anh_pil and p not in self._hong:
                can_doc.append(p)
        if can_doc:
            self._doc(can_doc)

    @staticmethod
    def _cat(chu, f, rong):
        if f.measure(chu) <= rong:
            return chu
        while chu and f.measure(chu + "…") > rong:
            chu = chu[:-1]
        return chu + "…"

    def _nhan(self, c, x, y, chu, goc, nen, mau_chu, f):
        tw = f.measure(chu)
        h = f.metrics("linespace") + 2
        w = tw + 8
        x0 = x - (w if "e" in goc else 0)
        y0 = y - (h if "s" in goc else 0)
        c.create_rectangle(x0, y0, x0 + w, y0 + h, fill=nen, outline="",
                           tags=("o",))
        c.create_text(x0 + w / 2, y0 + h / 2, text=chu, fill=mau_chu, font=f,
                      tags=("o",))

    # ---------------------------------------------------------------- ảnh
    def _anh_cho(self, path, w, h, mo: bool = False):
        """PhotoImage vừa khung (w×h) nếu đã đọc xong, không thì None.
        mo=True: tối hẳn đi (ảnh sẽ không được ghi)."""
        key = (path, w, h, mo)
        a = self._anh_tk.get(key)
        if a is not None:
            self._anh_tk.move_to_end(key)
            return a
        im = self._anh_pil.get(path)
        if im is None:
            return None
        anh = im.copy()
        anh.thumbnail((w, h), Image.BILINEAR)
        if mo:
            anh = anh.point(lambda v: int(v * 0.32))
        a = ImageTk.PhotoImage(anh, master=self)
        self._anh_tk[key] = a
        while len(self._anh_tk) > 400:
            self._anh_tk.popitem(last=False)
        return a

    def _doc(self, ds_path):
        if Image is None:
            return
        if self._bo_doc is None:
            self._bo_doc = BoDoc()
            threading.Thread(target=don_kho, daemon=True).start()
        self._bo_doc.muon(ds_path)
        if self._hen_bom is None:
            self._hen_bom = self.after(40, self._bom)

    def _bom(self):
        """Nhận ảnh luồng nền đọc xong (ở luồng chính), vẽ lại nếu có mới."""
        self._hen_bom = None
        if self._bo_doc is None:
            return
        co = False
        for p, im in self._bo_doc.lay_xong():
            if im is None:
                self._hong.add(p)
            else:
                self._anh_pil[p] = im
                while len(self._anh_pil) > 1500:
                    self._anh_pil.popitem(last=False)
            co = True
        if co:
            self._ve()
        #[[ Het viec thi THOI hen — khong de mot nhip 200 ms chay mai suot
        #   phien lam viec. _doc() hen lai khi co tam moi can doc. ]]
        if co or self._bo_doc.con_viec():
            try:
                self._hen_bom = self.after(40, self._bom)
            except tk.TclError:
                pass

    def _huy(self, _e=None):
        #[[ Huy nhip hen TRUOC khi widget mat: de lai la Tcl bao "invalid
        #   command name …_bom" luc dong app. ]]
        for ten in ("_hen_bom", "_hen_ve"):
            h = getattr(self, ten, None)
            if h is not None:
                try:
                    self.after_cancel(h)
                except tk.TclError:
                    pass
                setattr(self, ten, None)
        if self._bo_doc is not None:
            self._bo_doc.dung()
            self._bo_doc = None

    # ---------------------------------------------------------------- tương tác
    def _cuon_y(self, *a):
        self.canvas.yview(*a)
        self._ve()

    def _cuon_x(self, *a):
        self.canvas.xview(*a)
        self._ve()

    def _lan(self, e):
        huong = -1 if e.delta > 0 else 1
        if self.ngang:
            #[[ Dai anh: lan chuot di NGANG, hai o mot nac — nhu dai anh
            #   Lightroom. Lan doc tren dai mot hang thi khong co gi de cuon. ]]
            self.canvas.xview_scroll(2 * huong, "units")
        else:
            self.canvas.yview_scroll(huong, "units")
        self._ve()
        return "break"

    def _lan_linux(self, huong):
        if self.ngang:
            self.canvas.xview_scroll(2 * huong, "units")
        else:
            self.canvas.yview_scroll(huong, "units")
        self._ve()
        return "break"

    def _o_tai(self, x, y):
        c = self.canvas
        x, y = c.canvasx(x), c.canvasy(y)
        ow, oh = self._kich_thuoc_o()
        if self.ngang:
            i = int((x - self._khe) // (ow + self._khe))
            if i < 0 or i >= len(self.ds):
                return None
            ox, oy = self._o_xy(i)
            return i if (ox <= x <= ox + ow and oy <= y <= oy + oh) else None
        x0, _y0 = self._o_xy(0)
        cot = int((x - x0) // (ow + self._khe))
        hang = int((y - self._khe) // (oh + self._khe))
        if cot < 0 or cot >= self._cot or hang < 0:
            return None
        ox, oy = self._o_xy(hang * self._cot + cot)
        if not (ox <= x <= ox + ow and oy <= y <= oy + oh):
            return None
        i = hang * self._cot + cot
        return i if i < len(self.ds) else None

    def _bam(self, e, kieu: str = ""):
        """Bấm một ô. kieu "them" (Ctrl + bấm): thêm / bớt tấm đó khỏi nhóm
        đang chọn; "day" (Shift + bấm): chọn dãy từ tấm đang xem tới tấm bấm.
        Hai kiểu đó KHÔNG đổi tấm đang xem — chỉ bấm thường mới đổi."""
        self.canvas.focus_set()
        i = self._o_tai(e.x, e.y)
        if i is None:
            return
        p = self.ds[i]["path"]
        if self._chon_nhieu and kieu and self.dang_chon in self._vi_tri:
            if kieu == "day":
                a = self._vi_tri[self.dang_chon]
                lo, hi = sorted((a, i))
                self.da_chon = {self.ds[j]["path"] for j in range(lo, hi + 1)}
            elif p != self.dang_chon:
                (self.da_chon.discard if p in self.da_chon else self.da_chon.add)(p)
            else:
                #[[ Ctrl + bam CHINH tam dang xem: bo no khoi nhom, tam dang xem
                #   chuyen sang tam gan nhat con trong nhom. Nhom chi con moi no
                #   thi thoi — luc nao cung co mot tam dang xem. ]]
                con = [q for q in self.da_chon if q != p and q in self._vi_tri]
                if not con:
                    return
                self.da_chon.discard(p)
                self.dang_chon = min(con, key=lambda q: abs(self._vi_tri[q] - i))
                self._ve()
                self._bao_doi_chon()
                if self._khi_chon is not None:
                    self._khi_chon(self.dang_chon)
                return
            self.da_chon.add(self.dang_chon)
            self._ve()
            self._bao_doi_chon()
            return
        cu_chon = set(self.da_chon)
        self.dang_chon = p
        self.da_chon = {p}
        self._ve()
        if self.da_chon != cu_chon:
            self._bao_doi_chon()
        if self._khi_chon is not None:
            self._khi_chon(self.dang_chon)

    def _bam_dup(self, e):
        i = self._o_tai(e.x, e.y)
        if i is not None and self._khi_mo is not None:
            self._khi_mo(self.ds[i]["path"])

    def _mo_dang_chon(self):
        if self.dang_chon and self._khi_mo is not None:
            self._khi_mo(self.dang_chon)

    def _di_phim(self, dx, dy):
        if not self.ds:
            return "break"
        i = self._vi_tri.get(self.dang_chon, -1)
        buoc = (dx or dy) if self.ngang else dx + dy * self._cot
        j = 0 if i < 0 else min(max(i + buoc, 0), len(self.ds) - 1)
        self.dang_chon = self.ds[j]["path"]
        cu_chon = set(self.da_chon)
        self.da_chon = {self.dang_chon}         # phím mũi tên = chọn một tấm
        self._cuon_toi(j)
        self._ve()
        if self.da_chon != cu_chon:
            self._bao_doi_chon()
        if self._khi_chon is not None:
            self._khi_chon(self.dang_chon)
        return "break"

    def _cuon_toi(self, i):
        c = self.canvas
        if self.ngang:
            ow, _oh = self._kich_thuoc_o()
            x, _y = self._o_xy(i)
            x0 = c.canvasx(0)
            x1 = x0 + c.winfo_width()
            sr = c.cget("scrollregion").split()
            tong = float(sr[2]) if len(sr) == 4 else 1.0
            if x < x0:
                c.xview_moveto(max(0.0, (x - self._khe) / max(1.0, tong)))
            elif x + ow > x1:
                c.xview_moveto(max(0.0, (x + ow + self._khe - c.winfo_width())
                                   / max(1.0, tong)))
            return
        _ow, oh = self._kich_thuoc_o()
        _x, y = self._o_xy(i)
        y0 = c.canvasy(0)
        y1 = y0 + c.winfo_height()
        sr = c.cget("scrollregion").split()
        tong = float(sr[3]) if len(sr) == 4 else 1.0
        if y < y0:
            c.yview_moveto(max(0.0, (y - self._khe) / max(1.0, tong)))
        elif y + oh > y1:
            c.yview_moveto(max(0.0, (y + oh + self._khe - c.winfo_height())
                               / max(1.0, tong)))
