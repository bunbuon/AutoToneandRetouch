#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""khung_anh.py — Khung xem MỘT ảnh lớn kiểu Evoto: vừa khung, lăn chuột phóng
to quanh con trỏ, kéo để đi, nháy đúp 100% ↔ vừa khung, giữ chuột (hoặc phím \\)
xem bản gốc, "Vào mặt" nhảy tới từng khuôn mặt.

VÌ SAO VIẾT LẠI (tối 3/10 — user: "1 ảnh mở to và lưới ảnh bên dưới. Sửa lại
cả tính năng zoom ảnh")
    Zoom cũ (cửa sổ Xem trước) hỏng ba chỗ:
      1. Phóng to mà ảnh trên màn hình KHÔNG to ra. tk.PhotoImage chỉ thu nhỏ
         được theo bội số nguyên (subsample), không phóng được: cắt 1/5 khung
         của ảnh 1400 px là còn 280 px, hiện đúng 280 px giữa khung đen — càng
         phóng ảnh càng BÉ.
      2. Mỗi nấc lăn chuột là một vòng qua tiến trình con (cắt, nén PNG, gửi
         về): lăn thì ảnh đứng im, nửa giây sau mới nhảy.
      3. Kéo để đi thì ảnh không chạy theo tay (chỉ đổi khung số, thả tay mới
         xin cắt lại), và kéo xong thì kẹt ở "ẢNH GỐC".
    Ở đây vẽ bằng PIL ngay trong app: cắt ĐÚNG vùng đang nhìn, đổi cỡ đúng
    bằng khung — mỗi nhịp lăn / kéo là một lần vẽ vài chục ms.

NẠP DẦN, KHÔNG NHẢY
    Ảnh xuất 7008×4672 giải mã đủ mất ~0,3 s. Nên: hiện ngay ảnh nhỏ của dải
    ảnh (có sẵn), rồi bản nháp (JPEG draft, giải mã thẳng ở 1/2–1/8), rồi bản
    đủ nét — cả hai nạp ở luồng nền. Khung nhìn tính theo toạ độ ẢNH ĐỦ NÉT,
    nên ba bản thay nhau mà ảnh không xê dịch.

THÁP ẢNH
    Mỗi bản kèm các tầng 1/2, 1/4, 1/8 (Image.reduce). Vẽ ở tỉ lệ 20% thì lấy
    tầng 1/4 rồi đổi cỡ phần còn lại — không bao giờ phải thu 33 MP xuống vừa
    màn hình trong một lần vẽ.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

import tkinter as tk

import giao_dien as gd

try:
    from PIL import Image, ImageTk
except Exception:                                            # noqa: BLE001
    Image = ImageTk = None

CANH_NHAP = 1400        # cạnh dài TỐI THIỂU của bản nháp (JPEG draft lấy bậc ≥ cỡ này)
TANG_NHO = 900          # tầng nhỏ nhất của tháp không xuống dưới cỡ này
GIU_MS = 150            # giữ chuột bao lâu (không kéo) thì hiện ảnh gốc
NET_MS = 170            # ngừng lăn / kéo bao lâu thì vẽ lại bằng bộ lọc nét
DIEM_MAT = 0.6          # ngưỡng điểm YuNet cho "Vào mặt"


# ── tháp ảnh ─────────────────────────────────────────────────────────────────
class Thap:
    """Một ảnh + các tầng thu nhỏ. rong/cao là cỡ ẢNH ĐỦ NÉT (toạ độ logic);
    mỗi tầng là (hệ số x, hệ số y, ảnh PIL) với hệ số = logic / tầng."""

    def __init__(self, rong: int, cao: int, tang: list, tam: bool = False):
        self.rong, self.cao = int(rong), int(cao)
        self.tang = sorted(tang, key=lambda t: t[0])
        #[[ tam=True: anh nho MUON TAM cua dai anh (co the la ban goc trong khi
        #   anh chinh la ban ket qua). Khong bao gio tinh la "du net" — ke ca
        #   khi anh nho trung co anh that (anh 300 px), khong thi ban that ve
        #   sau bi bo qua va anh lon ket o anh tam. Da gap 3/10. ]]
        self.tam = tam
        self.day_du = (not tam) and bool(self.tang) and self.tang[0][0] <= 1.0001

    def chon(self, s: float):
        """Tầng thưa nhất mà vẫn còn ≥ 1 điểm ảnh cho mỗi điểm màn hình ở tỉ
        lệ s; không tầng nào đủ (đang phóng quá 100%) thì tầng dày nhất."""
        hop = [t for t in self.tang if t[0] * s <= 1.0001]
        return hop[-1] if hop else self.tang[0]


def thap_tu_anh(im, rong: int | None = None, cao: int | None = None) -> Thap:
    """Tháp từ một ảnh PIL RGB. rong/cao = cỡ logic (None: chính cỡ của im)."""
    rong = int(rong or im.width)
    cao = int(cao or im.height)
    tang = [(rong / im.width, cao / im.height, im)]
    cur = im
    while min(cur.size) >= 2 and max(cur.size) // 2 >= TANG_NHO:
        cur = cur.reduce(2)
        tang.append((rong / cur.width, cao / cur.height, cur))
    return Thap(rong, cao, tang)


# ── đọc file ─────────────────────────────────────────────────────────────────
_XOAY = None


def _cach_xoay():
    global _XOAY
    if _XOAY is None:
        T = Image.Transpose
        _XOAY = {2: [T.FLIP_LEFT_RIGHT], 3: [T.ROTATE_180], 4: [T.FLIP_TOP_BOTTOM],
                 5: [T.TRANSPOSE], 6: [T.ROTATE_270], 7: [T.TRANSVERSE],
                 8: [T.ROTATE_90]}
    return _XOAY


def _huong(im) -> int:
    try:
        return int(im.getexif().get(0x0112, 1) or 1)
    except Exception:                                        # noqa: BLE001
        return 1


def _xoay(im, huong: int):
    for t in _cach_xoay().get(huong, []):
        im = im.transpose(t)
    return im


def _rgb(im):
    if im.mode == "RGB":
        return im
    try:
        return im.convert("RGB")
    except Exception:                                        # noqa: BLE001
        #[[ TIFF 16 bit xam ("I;16") khong doi thang sang RGB duoc. ]]
        return im.convert("I").point(lambda v: v / 256).convert("L").convert("RGB")


def kich_thuoc(p) -> tuple[int, int]:
    """Cỡ logic (đã xoay theo EXIF) — chỉ đọc đầu file, không giải mã."""
    with Image.open(p) as im:
        w, h = im.size
        o = _huong(im)
    return (h, w) if o in (5, 6, 7, 8) else (w, h)


def nap_nhap(p, canh: int = CANH_NHAP) -> Thap:
    """Bản nháp ~canh px. JPEG thì draft: giải mã thẳng ở 1/2, 1/4, 1/8 — nhanh
    hơn giải mã đủ rồi thu nhỏ cả chục lần."""
    im = Image.open(p)
    w0, h0 = im.size
    o = _huong(im)
    if max(w0, h0) > canh * 1.5:
        k = max(w0, h0) / float(canh)
        try:
            im.draft("RGB", (max(1, int(w0 / k)), max(1, int(h0 / k))))
        except Exception:                                    # noqa: BLE001
            pass
    im.load()
    a = _xoay(_rgb(im), o)
    W, H = (h0, w0) if o in (5, 6, 7, 8) else (w0, h0)
    k = int(max(a.size) // canh)
    if k >= 2:                         # không phải JPEG (draft không có tác dụng)
        a = a.reduce(k)
    return thap_tu_anh(a, W, H)


def nap_day_du(p) -> Thap:
    im = Image.open(p)
    o = _huong(im)
    im.load()
    return thap_tu_anh(_xoay(_rgb(im), o))


_DET = threading.local()


def tim_mat(im) -> list:
    """[(x, y, w, h)] các mặt YuNet thấy trên im (toạ độ của im), mặt TO trước.
    Không có OpenCV / mô hình thì [] — nút "Vào mặt" tự tắt."""
    try:
        import cv2
        import numpy as np

        import autotone as at
        mo_hinh = Path(at.FACE_MODEL)
        if not mo_hinh.is_file():
            return []
        k = 1.0
        a = im
        if max(a.size) > 1600:
            k = 1600.0 / max(a.size)
            a = a.resize((max(1, round(a.width * k)), max(1, round(a.height * k))),
                         Image.BILINEAR)
        #[[ Bo nhan dien RIENG cho luong nay: at.face_detector() dung chung
        #   mot doi tuong cho ca app, ma setInputSize + detect tren cung mot
        #   doi tuong tu hai luong la dua nhau. ]]
        det = getattr(_DET, "det", None)
        if det is None:
            det = cv2.FaceDetectorYN.create(str(mo_hinh), "", (320, 320),
                                            DIEM_MAT, 0.3, 5000)
            _DET.det = det
        det.setInputSize((a.width, a.height))
        _, faces = det.detect(np.asarray(a)[:, :, ::-1].copy())
    except Exception:                                        # noqa: BLE001
        return []
    if faces is None:
        return []
    ra = []
    for f in faces:
        x, y, w, h = (float(v) / k for v in f[:4])
        if float(f[-1]) >= DIEM_MAT and w > 8 and h > 8:
            ra.append((x, y, w, h))
    ra.sort(key=lambda b: -b[2] * b[3])
    return ra[:40]


# ── luồng nạp ────────────────────────────────────────────────────────────────
class _BoNap:
    """MỘT luồng nền nạp ảnh cho khung. Việc mới thay hẳn việc cũ — chỉ ảnh
    đang xem là đáng nạp; bấm qua 10 tấm thì không phải chờ nạp đủ 10 tấm."""

    def __init__(self):
        self._cv = threading.Condition()
        self._viec = None
        self._ma = 0
        self._xong: list = []
        self._dang = False
        self._dung = False
        self._luong = threading.Thread(target=self._chay, daemon=True)
        self._luong.start()

    def nap(self, ma: int, viec: list, tim_mat_tren: str | None) -> None:
        """viec = [(vai, đường dẫn)] — vai "sau" (ảnh chính) / "truoc" (gốc)."""
        with self._cv:
            self._ma = ma
            self._viec = (ma, viec, tim_mat_tren)
            self._cv.notify_all()

    def huy(self) -> None:
        with self._cv:
            self._ma += 1
            self._viec = None

    def dung(self, cho: float = 0.0) -> None:
        """Dừng luồng nạp. cho > 0: đợi việc đang dở (giải mã / tìm mặt) xong.

        #[[ PHAI DOI khi dong app: luong dang o giua cv2 (YuNet) ma tien trinh
        #   thoat thi C++ bao "terminate called without an active exception" va
        #   abort — tren Windows la mot hop thoai loi luc tat app. Gap that o bai
        #   kiem 3/10 (dong ngay sau khi doi anh). Viec dai nhat ~0,3 s. ]]
        """
        with self._cv:
            self._dung = True
            self._viec = None
            self._cv.notify_all()
        if cho > 0 and self._luong is not threading.current_thread():
            self._luong.join(cho)

    def lay(self) -> list:
        with self._cv:
            xong, self._xong = self._xong, []
        return xong

    def con_viec(self) -> bool:
        with self._cv:
            return self._viec is not None or self._dang or bool(self._xong)

    def _moi(self, ma) -> bool:
        return self._ma == ma and not self._dung

    def _dua(self, *gt):
        with self._cv:
            self._xong.append(gt)

    def _chay(self):
        while True:
            with self._cv:
                while self._viec is None and not self._dung:
                    self._cv.wait(0.5)
                if self._dung:
                    return
                ma, viec, tim = self._viec
                self._viec = None
                self._dang = True
            try:
                self._lam(ma, viec, tim)
            finally:
                with self._cv:
                    self._dang = False
                self._dua(ma, "het", "", None)

    def _lam(self, ma, viec, tim):
        nhap = {}
        for vai, p in viec:
            if not self._moi(ma):
                return
            try:
                th = nap_nhap(p)
            except Exception as ex:                          # noqa: BLE001
                self._dua(ma, "loi", vai, f"{type(ex).__name__}: {ex}")
                continue
            nhap[vai] = th
            self._dua(ma, "nhap", vai, th)
        if tim and tim in nhap and self._moi(ma):
            th = nhap[tim]
            fx, fy, im = th.tang[0]
            self._dua(ma, "mat", tim, [(x * fx, y * fy, w * fx, h * fy)
                                        for x, y, w, h in tim_mat(im)])
        for vai, p in viec:
            if vai not in nhap or not self._moi(ma):
                continue
            if nhap[vai].day_du:
                continue                     # ảnh nhỏ: bản nháp đã là bản đủ
            try:
                self._dua(ma, "du", vai, nap_day_du(p))
            except Exception as ex:                          # noqa: BLE001
                self._dua(ma, "loi_du", vai, f"{type(ex).__name__}: {ex}")


# ── khung xem ────────────────────────────────────────────────────────────────
class KhungAnh(tk.Frame):
    """Một ảnh lớn. Hai bản: "sau" (ảnh chính — kết quả retouch, bản xem
    trước) và "truoc" (bản gốc để so). Khung nhìn là (tỉ lệ, tâm) theo toạ độ
    ẢNH SAU; bản trước khác cỡ thì quy đổi theo tỉ lệ khung.

    khi_doi()      — gọi sau mỗi lần đổi tỉ lệ / nạp xong / đổi bản đang hiện.
    khi_phim(d)    — ← → : d = -1 / +1 (ảnh trước / sau trong dải ảnh).
    """

    PHONG_MAX = 8.0         # 800%
    BUOC_LAN = 1.2          # mỗi nấc lăn chuột
    LE = 12                 # lề quanh ảnh khi vừa khung
    MAT_MAX = 2.0           # "Vào mặt" phóng tối đa 200%

    #[[ SO SANH TRUOC / SAU (9/10 — user: "co cac tinh nang zoom, man hinh so sanh
    #   truoc sau nhu trong Lightroom"). Ba kieu, cung khung nhin (ti le + tam)
    #   cho ca hai ban — phong / keo mot ben la ben kia theo:
    #     "sau"   mot anh; giu chuot / phim \\ xem goc (nhu truoc nay)
    #     "canh"  TRUOC | SAU canh nhau, moi ben nua khung
    #     "chia"  mot anh, ben trai vach la TRUOC, ben phai la SAU; keo vach
    #   Khong co ban truoc thi moi kieu deu ve nhu "sau". ]]
    KHE_CANH = 8

    def __init__(self, cha, nen: str | None = None, khi_doi=None, khi_phim=None,
                 khi_dup=None):
        self._nen = nen or "#101114"
        super().__init__(cha, background=self._nen)
        self._khi_doi = khi_doi
        self._khi_phim = khi_phim
        #  9/10: bấm đúp ảnh -> gọi khi_dup (vd. về lưới ảnh) thay vì phóng 100%
        self._khi_dup = khi_dup
        self.che_do_so = "sau"
        self._chia = 0.5
        self._keo_chia = False
        self.canvas = tk.Canvas(self, background=self._nen, highlightthickness=0,
                                borderwidth=0, takefocus=1, cursor="arrow")
        self.canvas.pack(fill="both", expand=True)
        c = self.canvas
        self._i_anh = c.create_image(0, 0, anchor="nw", state="hidden")
        self._i_anh2 = c.create_image(0, 0, anchor="nw", state="hidden")      # bản TRƯỚC khi so
        self._i_vach = c.create_line(0, 0, 0, 0, fill="#ffffff", width=2, state="hidden")
        self._i_nut_vach = c.create_oval(0, 0, 0, 0, fill="#ffffff", outline="#111214",
                                         width=2, state="hidden")
        f_nhan = gd._phong(self, ("Segoe UI", 10, "bold"))
        #[[ Nhan "ANH GOC" nam tren nen toi rieng: chu cam tren anh cuoi (phong
        #   nen kem, vay trang) la khong doc duoc — da thay tren anh that. ]]
        self._i_nhan_nen = c.create_rectangle(0, 0, 0, 0, fill="#111214", outline="",
                                              state="hidden")
        self._i_nhan = c.create_text(22, 18, anchor="nw", text="", fill=gd.MAU["canh"],
                                     font=f_nhan)
        self._i_chu = c.create_text(0, 0, anchor="center", text="", fill=gd.MAU["mo"],
                                    font=gd._phong(self, gd.CHU), justify="center")
        #  nhãn TRƯỚC / SAU khi so sánh (viên bo tròn như Lightroom / mẫu user gửi)
        f_so = gd._phong(self, ("Segoe UI", 9, "bold"))
        self._nhan_so = {}
        for ten, nen_v in (("truoc", "#3b3f47"), ("sau", "#6d4ad8")):
            nen_id = c.create_rectangle(0, 0, 0, 0, fill=nen_v, outline="", state="hidden")
            chu_id = c.create_text(0, 0, anchor="nw", text="TRƯỚC" if ten == "truoc" else "SAU",
                                   fill="#ffffff", font=f_so, state="hidden")
            self._nhan_so[ten] = (nen_id, chu_id)
        self._o_trong = tk.Frame(c, background=self._nen)
        #[[ 7/10 (thiet ke lai): bieu tuong khung anh lon + tieu de dam + dong
        #   giai thich mo — giong man trong cua luoi anh (luoi_anh.dat_trong). ]]
        lh = gd.don_vi(self)
        self._s_trong = round(lh * 3.8)
        self.icon_trong = tk.Canvas(self._o_trong, width=self._s_trong,
                                    height=self._s_trong, background=self._nen,
                                    highlightthickness=0, borderwidth=0)
        self.icon_trong.tu_cuon = False
        gd.ve_bieu_tuong(self.icon_trong, "anh", self._s_trong / 2,
                         self._s_trong / 2, self._s_trong * 0.8, gd.MAU["mo2"], net=1.3)
        self.icon_trong.pack(pady=(0, 10))
        self.lbl_trong_dau = tk.Label(self._o_trong, text="", background=self._nen,
                                      foreground=gd.MAU["chu"], font=gd.CHU_TIEU_DE,
                                      justify="center", wraplength=460)
        self.lbl_trong_dau.pack(pady=(0, 4))
        self.lbl_trong = tk.Label(self._o_trong, text="", background=self._nen,
                                  foreground=gd.MAU["mo"], font=gd.CHU,
                                  justify="center", wraplength=460)
        self.lbl_trong.pack(pady=(0, 0))
        self.nut_trong = gd.NutTron(self._o_trong, "", kieu="chinh", icon="thu_muc",
                                    nen=self._nen)
        self._i_trong = c.create_window(0, 0, window=self._o_trong, anchor="center",
                                        state="hidden")

        self._sau: Thap | None = None
        self._truoc: Thap | None = None
        self._s: float | None = None         # None = vừa khung
        self._cx = self._cy = 0.0
        self.hien_truoc = False
        self._goc_do_chuot = False
        self.mat: list = []
        self.i_mat = -1
        self._ma = 0
        self._bo_nap: _BoNap | None = None
        self._photo = None
        self._photo2 = None
        self._nhanh_toi = 0.0
        self._hen_ve = self._hen_net = self._hen_bom = self._hen_giu = None
        self._hen_tha_phim = None
        self._bat_dau = None
        self._keo = None
        self._da_keo = False
        self.dang_nap = False
        self.loi = ""
        self.lan_ve = 0
        self.vung_ve = None          # (x, y, rộng, cao) của ảnh vừa vẽ — cho bài kiểm
        self.loc_ve = ""             # bộ lọc vừa dùng — cho bài kiểm
        self.tang_ve = 1.0           # hệ số tầng tháp vừa vẽ — cho bài kiểm

        c.bind("<Configure>", lambda _e: self._khi_doi_co(), add="+")
        c.bind("<ButtonPress-1>", self._nhan)
        c.bind("<B1-Motion>", self._di)
        c.bind("<ButtonRelease-1>", self._tha)
        c.bind("<Double-Button-1>", self._dup)
        c.bind("<Motion>", self._re_chuot, add="+")
        c.bind("<MouseWheel>", self._lan)
        c.bind("<Button-4>", lambda e: self._lan(e, 1))
        c.bind("<Button-5>", lambda e: self._lan(e, -1))
        c.bind("<Left>", lambda _e: self._phim_buoc(-1))
        c.bind("<Right>", lambda _e: self._phim_buoc(1))
        for phim in ("<KeyPress-0>", "<Escape>"):
            c.bind(phim, lambda _e: (self.vua_khung(), "break")[1])
        c.bind("<KeyPress-1>", lambda _e: (self.phong_100(), "break")[1])
        for phim in ("<plus>", "<equal>", "<KP_Add>"):
            c.bind(phim, lambda _e: (self.phong(1.25), "break")[1])
        for phim in ("<minus>", "<KP_Subtract>"):
            c.bind(phim, lambda _e: (self.phong(0.8), "break")[1])
        for phim in ("<KeyPress-m>", "<KeyPress-M>"):
            c.bind(phim, lambda _e: (self.vao_mat(), "break")[1])
        c.bind("<KeyPress-backslash>", self._phim_goc)
        c.bind("<KeyRelease-backslash>", self._tha_phim_goc)
        self.bind("<Destroy>", self._huy, add="+")

    # ================================================================ trạng thái
    def _kt_canvas(self):
        c = self.canvas
        return max(1, c.winfo_width()), max(1, c.winfo_height())

    def _so_canh(self) -> bool:
        return self.che_do_so == "canh" and self._truoc is not None and self._sau is not None

    def _so_chia(self) -> bool:
        return self.che_do_so == "chia" and self._truoc is not None and self._sau is not None

    def _kt(self):
        """Cỡ MỘT ô nhìn: cả khung, hoặc nửa khung khi so TRƯỚC | SAU cạnh nhau —
        mọi phép vừa khung / kẹp / phóng tính trên ô này."""
        W, H = self._kt_canvas()
        if self._so_canh():
            return max(1, (W - self.KHE_CANH) // 2), H
        return W, H

    def _diem_o(self, x, y):
        """Toạ độ chuột -> toạ độ trong ô nhìn (ô phải khi so cạnh nhau)."""
        if self._so_canh():
            Wo, _H = self._kt()
            if x >= Wo + self.KHE_CANH:
                return x - (Wo + self.KHE_CANH), y
            return min(x, Wo), y
        return x, y

    def dat_che_do_so(self, che_do: str) -> None:
        """"sau" | "canh" | "chia" — đổi kiểu so sánh, giữ chỗ đang soi."""
        che_do = che_do if che_do in ("sau", "canh", "chia") else "sau"
        if che_do == self.che_do_so:
            return
        self.che_do_so = che_do
        self.hien_truoc = self._goc_do_chuot = False
        self._kep()
        self._ve()
        self._bao()

    def kich_thuoc(self):
        """(rộng, cao) logic của ảnh đang xem, None nếu chưa có ảnh."""
        return None if self._sau is None else (self._sau.rong, self._sau.cao)

    def co_truoc(self) -> bool:
        return self._truoc is not None

    def so_mat(self) -> int:
        return len(self.mat)

    def s_vua(self) -> float:
        """Tỉ lệ vừa khung — không phóng ảnh nhỏ quá 100%."""
        if self._sau is None:
            return 1.0
        return self._s_vua_cho(self._sau.rong, self._sau.cao)

    def _s_vua_cho(self, rong, cao) -> float:
        W, H = self._kt()
        return max(1e-4, min((W - 2 * self.LE) / max(1, rong),
                             (H - 2 * self.LE) / max(1, cao), 1.0))

    #[[ CUNG MOT ANH, DO PHAN GIAI KHAC (sang 4/10). Keo thanh o bang phai la
    #   anh lon doi tu ban tren dia (6000 px) sang ban xem truoc (1400 px) va
    #   nguoc lai khi tat xem truoc. Truoc day khac co la nhay ve vua khung —
    #   dang soi da o mat, keo "Lam min da" mot cai la mat cho dang soi. Gio
    #   giu dung VUNG dang soi; ban xem truoc chi 1400 px nen khong phong qua
    #   ZOOM_GIU (qua do chi la nhoe ra, khong soi them duoc gi). ]]
    ZOOM_GIU = 2.0

    def _anh_xa(self, cu, moi, s, cx, cy) -> bool:
        """Đặt khung nhìn cho ảnh cỡ `moi` sao cho vẫn thấy đúng vùng đang soi
        trên ảnh cỡ `cu` (s, cx, cy là khung nhìn cũ). False: không phải cùng
        một ảnh (chưa có ảnh, hoặc khác tỉ lệ khung) — bên gọi về vừa khung."""
        if cu is None or moi is None:
            return False
        (w1, h1), (w2, h2) = cu, moi
        if (w1, h1) == (w2, h2):
            self._s, self._cx, self._cy = s, cx, cy
            return True
        if min(w1, h1, w2, h2) <= 0 or abs(w1 * h2 - w2 * h1) > 0.02 * w1 * h2:
            return False
        k = w2 / w1
        vua = self._s_vua_cho(w2, h2)
        s2 = None
        if s is not None:
            s2 = s / k
            if k < 1:
                s2 = min(s2, max(self.ZOOM_GIU, vua))
            if s2 <= vua + 1e-9:
                s2 = None
        self._s = s2
        W, H = self._kt()
        ss = vua if s2 is None else s2
        nw, nh = W / (2 * ss), H / (2 * ss)
        x, y = cx * k, cy * k
        self._cx = w2 / 2.0 if w2 <= 2 * nw else min(max(x, nw), w2 - nw)
        self._cy = h2 / 2.0 if h2 <= 2 * nh else min(max(y, nh), h2 - nh)
        return True

    def ty_le(self) -> float:
        """Điểm màn hình trên một điểm ảnh (1.0 = 100%)."""
        return self.s_vua() if self._s is None else self._s

    def la_vua(self) -> bool:
        return self._s is None

    def tam(self):
        return self._cx, self._cy

    def _ve_tam_giua(self):
        if self._sau is not None:
            self._cx, self._cy = self._sau.rong / 2.0, self._sau.cao / 2.0

    def _kep(self):
        """Kẹp tâm: ảnh to hơn khung thì không trôi ra ngoài mép; nhỏ hơn khung
        (chiều nào) thì nằm giữa (chiều đó)."""
        th = self._sau
        if th is None:
            return
        W, H = self._kt()
        s = self.ty_le()
        nw, nh = W / (2 * s), H / (2 * s)
        self._cx = th.rong / 2.0 if th.rong <= 2 * nw else min(max(self._cx, nw), th.rong - nw)
        self._cy = th.cao / 2.0 if th.cao <= 2 * nh else min(max(self._cy, nh), th.cao - nh)

    def keo_duoc(self) -> bool:
        """Ảnh đang to hơn khung (ít nhất một chiều) — kéo để đi được."""
        if self._sau is None:
            return False
        W, H = self._kt()
        s = self.ty_le()
        return self._sau.rong * s > W + 0.5 or self._sau.cao * s > H + 0.5

    def _bao(self):
        self.canvas.configure(cursor="fleur" if self.keo_duoc() else "arrow")
        if self._khi_doi is not None:
            try:
                self._khi_doi()
            except Exception:                                # noqa: BLE001
                import traceback
                traceback.print_exc()

    def _khi_doi_co(self):
        self._kep()
        c = self.canvas
        W, H = self._kt_canvas()
        c.coords(self._i_trong, W / 2, H / 2)
        c.coords(self._i_chu, W / 2, H / 2)
        self._ve()
        self._bao()

    # ================================================================ nạp ảnh
    def mo(self, sau, truoc=None, tam=None, giu_khung: bool = False,
           tim_mat_anh: bool = True) -> None:
        """Mở ảnh từ đĩa. sau = ảnh chính; truoc = bản gốc để so (None: không
        so); tam = ảnh PIL nhỏ có sẵn (ảnh của dải) để hiện NGAY trong lúc chờ."""
        self._ma += 1
        ma = self._ma
        self._an_trong()
        self.loi = ""
        cu = self.kich_thuoc()
        s_cu, cx_cu, cy_cu = self._s, self._cx, self._cy
        try:
            W, H = kich_thuoc(sau)
        except Exception as ex:                              # noqa: BLE001
            self._sau = self._truoc = None
            self.mat, self.i_mat = [], -1
            self.loi = f"Không mở được ảnh: {type(ex).__name__}: {ex}"
            self.dang_nap = False
            self._ve()
            self._bao()
            return
        if tam is not None:
            try:
                t = _rgb(tam)
                self._sau = Thap(W, H, [(W / t.width, H / t.height, t)], tam=True)
            except Exception:                                # noqa: BLE001
                self._sau = None
        else:
            self._sau = None
        self._truoc = None
        self.mat, self.i_mat = [], -1
        self.hien_truoc = self._goc_do_chuot = False
        if not (giu_khung and self._anh_xa(cu, (W, H), s_cu, cx_cu, cy_cu)):
            self._s = None
            self._cx, self._cy = W / 2.0, H / 2.0
        self.dang_nap = True
        if self._bo_nap is None:
            self._bo_nap = _BoNap()
        viec = [("sau", str(sau))] + ([("truoc", str(truoc))] if truoc else [])
        self._bo_nap.nap(ma, viec, "sau" if tim_mat_anh else None)
        self._hen_bom_nap()
        self._ve()
        self._bao()

    def dat_anh(self, sau, truoc=None, mat=None, giu_khung: bool = True) -> None:
        """Đặt thẳng ảnh PIL (bản xem trước tính ở tiến trình con). Cùng cỡ với
        ảnh đang xem và giu_khung → giữ nguyên chỗ đang soi."""
        self._ma += 1
        if self._bo_nap is not None:
            self._bo_nap.huy()
        self._an_trong()
        self.loi = ""
        cu = self.kich_thuoc()
        s_cu, cx_cu, cy_cu = self._s, self._cx, self._cy
        self._sau = thap_tu_anh(_rgb(sau))
        self._truoc = thap_tu_anh(_rgb(truoc)) if truoc is not None else None
        if mat is not None:
            self.mat, self.i_mat = list(mat), -1
        self.dang_nap = False
        if not (giu_khung and self._anh_xa(cu, self.kich_thuoc(), s_cu, cx_cu, cy_cu)):
            self._s = None
            self._ve_tam_giua()
        if self._truoc is None:
            self.hien_truoc = self._goc_do_chuot = False
        self._ve()
        self._bao()

    def dat_sau(self, sau) -> None:
        """Thay riêng ảnh chính, giữ bản gốc và chỗ đang soi."""
        cu = self.kich_thuoc()
        self._sau = thap_tu_anh(_rgb(sau))
        if cu != self.kich_thuoc():
            self._s = None
            self._ve_tam_giua()
        self._kep()
        self._ve()
        self._bao()

    def dat_trong(self, chu: str, nut: str | None = None, lenh=None) -> None:
        """Không có ảnh: chữ giữa khung, kèm một nút (tuỳ)."""
        self._ma += 1
        if self._bo_nap is not None:
            self._bo_nap.huy()
        self._sau = self._truoc = None
        self.mat, self.i_mat = [], -1
        self.hien_truoc = self._goc_do_chuot = False
        self.dang_nap = False
        self.loi = ""
        dau, _, sau = str(chu or "").partition("\n")
        self.lbl_trong_dau.configure(text=dau)
        self.lbl_trong.configure(text=sau.strip())
        (self.lbl_trong.pack(pady=(0, 0), after=self.lbl_trong_dau) if sau.strip()
         else self.lbl_trong.pack_forget())
        if nut:
            self.nut_trong.configure(text=nut, command=lenh)
            if not self.nut_trong.winfo_manager():
                self.nut_trong.pack(pady=(16, 0))
        else:
            self.nut_trong.pack_forget()
        W, H = self._kt_canvas()
        self.canvas.coords(self._i_trong, W / 2, H / 2)
        self.canvas.itemconfigure(self._i_trong, state="normal")
        self._ve()
        self._bao()

    def _an_trong(self):
        self.canvas.itemconfigure(self._i_trong, state="hidden")

    def dang_trong(self) -> bool:
        return self.canvas.itemcget(self._i_trong, "state") != "hidden"

    def _hen_bom_nap(self):
        if self._hen_bom is None:
            try:
                self._hen_bom = self.after(25, self._bom_nap)
            except tk.TclError:
                self._hen_bom = None

    def _bom_nap(self):
        self._hen_bom = None
        bn = self._bo_nap
        if bn is None:
            return
        doi = False
        for ma, loai, vai, gt in bn.lay():
            if ma != self._ma:
                continue
            if loai in ("nhap", "du"):
                cu = self._sau if vai == "sau" else self._truoc
                #[[ Khong lui: ban du net da ve thi ban nhap (toi muon) khong
                #   duoc de len. ]]
                if cu is not None and cu.day_du and loai == "nhap":
                    continue
                if vai == "sau":
                    self._sau = gt
                else:
                    self._truoc = gt
                doi = True
            elif loai == "mat":
                self.mat, self.i_mat = list(gt or []), -1
                doi = True
            elif loai == "loi" and vai == "sau":
                self.loi = f"Không đọc được ảnh: {gt}"
                self._sau = None
                doi = True
            elif loai == "het":
                self.dang_nap = False
                doi = True
        if doi:
            self._kep()
            self._ve()
            self._bao()
        if bn.con_viec():
            self._hen_bom_nap()

    # ================================================================ vẽ
    def _ve(self):
        if self._hen_ve is None:
            try:
                self._hen_ve = self.after_idle(self._ve_that)
            except tk.TclError:
                self._hen_ve = None

    def ve_ngay(self):
        """Vẽ ngay (bài kiểm / chụp màn hình), không chờ lúc rảnh."""
        if self._hen_ve is not None:
            try:
                self.after_cancel(self._hen_ve)
            except tk.TclError:
                pass
            self._hen_ve = None
        self._ve_that()

    def _nhanh(self):
        """Đang lăn / kéo: vẽ bằng bộ lọc nhanh, ngừng tay mới vẽ nét."""
        self._nhanh_toi = time.monotonic() + NET_MS / 1000.0
        if self._hen_net is not None:
            try:
                self.after_cancel(self._hen_net)
            except tk.TclError:
                pass
        try:
            self._hen_net = self.after(NET_MS + 10, self._lam_net)
        except tk.TclError:
            self._hen_net = None

    def _lam_net(self):
        self._hen_net = None
        self._nhanh_toi = 0.0
        self._ve()

    def _cat_ve(self, hien, th, W, H, ox: float = 0.0):
        """Vẽ bản `hien` (khung nhìn theo toạ độ ảnh chính `th`) vào ô rộng W, cao
        H đặt ở ox. -> (ảnh PIL đã cắt, px, py, tên bộ lọc, tầng) hoặc None."""
        s = self.ty_le()
        kx, ky = hien.rong / th.rong, hien.cao / th.cao
        sx, sy = s / kx, s / ky
        cx, cy = self._cx * kx, self._cy * ky
        x0 = max(0.0, cx - W / (2 * sx))
        x1 = min(float(hien.rong), cx + W / (2 * sx))
        y0 = max(0.0, cy - H / (2 * sy))
        y1 = min(float(hien.cao), cy + H / (2 * sy))
        if x1 - x0 < 1e-3 or y1 - y0 < 1e-3:
            return None
        fx, fy, im = hien.chon(min(sx, sy))
        box = (max(0.0, x0 / fx), max(0.0, y0 / fy),
               min(float(im.width), x1 / fx), min(float(im.height), y1 / fy))
        tw = max(1, int(round((x1 - x0) * sx)))
        tch = max(1, int(round((y1 - y0) * sy)))
        nhanh = time.monotonic() < self._nhanh_toi
        if sx >= 3.0:
            loc, ten = Image.NEAREST, "nearest"        # soi điểm ảnh: không làm nhoè
        elif nhanh:
            loc, ten = Image.BILINEAR, "bilinear"
        elif sx * fx < 1.0:
            loc, ten = Image.LANCZOS, "lanczos"
        else:
            loc, ten = Image.BICUBIC, "bicubic"
        out = im.resize((tw, tch), loc, box=box)
        px = int(round(ox + W / 2 + (x0 - cx) * sx))
        py = int(round(H / 2 + (y0 - cy) * sy))
        return out, px, py, ten, fx

    def _ve_that(self):
        self._hen_ve = None
        c = self.canvas
        try:
            Wc, Hc = self._kt_canvas()
        except tk.TclError:
            return
        th = self._sau
        if th is None:
            self._an_anh()
            self._an_so()
            self.vung_ve = None
            self._dat_nhan("")
            if self.dang_trong():
                c.itemconfigure(self._i_chu, text="")
            else:
                c.coords(self._i_chu, Wc / 2, Hc / 2)
                c.itemconfigure(self._i_chu, text=self.loi or (
                    "đang mở ảnh…" if self.dang_nap else ""),
                    fill=gd.MAU["loi"] if self.loi else gd.MAU["mo"])
            return
        c.itemconfigure(self._i_chu, text="")
        W, H = self._kt()
        try:
            if self._so_canh():
                #  TRƯỚC | SAU cạnh nhau: ô trái bản trước, ô phải bản sau
                tr = self._cat_ve(self._truoc, th, W, H, 0.0)
                sa = self._cat_ve(th, th, W, H, float(W + self.KHE_CANH))
                if sa is None:
                    self._an_anh()
                    return
                out, px, py, ten, fx = sa
                self._photo = ImageTk.PhotoImage(out, master=c)
                c.coords(self._i_anh, px, py)
                c.itemconfigure(self._i_anh, image=self._photo, state="normal")
                if tr is not None:
                    #  ô trái không được tràn sang ô phải
                    o2, px2, py2 = tr[0], tr[1], tr[2]
                    tran = px2 + o2.width - W
                    if tran > 0:
                        o2 = o2.crop((0, 0, max(1, o2.width - tran), o2.height))
                    self._photo2 = ImageTk.PhotoImage(o2, master=c)
                    c.coords(self._i_anh2, px2, py2)
                    c.itemconfigure(self._i_anh2, image=self._photo2, state="normal")
                else:
                    c.itemconfigure(self._i_anh2, image="", state="hidden")
                c.itemconfigure(self._i_vach, state="hidden")
                c.itemconfigure(self._i_nut_vach, state="hidden")
                self._dat_nhan("")
                self._dat_nhan_so(12, W + self.KHE_CANH + 12)
                self.vung_ve = (px, py, out.width, out.height)
            else:
                hien = self._truoc if (self.hien_truoc and self._truoc is not None
                                       and not self._so_chia()) else th
                ve = self._cat_ve(hien, th, W, H, 0.0)
                if ve is None:
                    self._an_anh()
                    return
                out, px, py, ten, fx = ve
                self._photo = ImageTk.PhotoImage(out, master=c)
                c.coords(self._i_anh, px, py)
                c.itemconfigure(self._i_anh, image=self._photo, state="normal")
                if self._so_chia():
                    #  CHIA ĐÔI: bản trước phủ phần bên trái vạch
                    xv = int(round(W * self._chia))
                    tr = self._cat_ve(self._truoc, th, W, H, 0.0)
                    if tr is not None and xv > tr[1]:
                        o2, px2, py2 = tr[0], tr[1], tr[2]
                        o2 = o2.crop((0, 0, max(1, min(o2.width, xv - px2)), o2.height))
                        self._photo2 = ImageTk.PhotoImage(o2, master=c)
                        c.coords(self._i_anh2, px2, py2)
                        c.itemconfigure(self._i_anh2, image=self._photo2, state="normal")
                    else:
                        c.itemconfigure(self._i_anh2, image="", state="hidden")
                    c.coords(self._i_vach, xv, 0, xv, H)
                    r = 9
                    c.coords(self._i_nut_vach, xv - r, H / 2 - r, xv + r, H / 2 + r)
                    c.itemconfigure(self._i_vach, state="normal")
                    c.itemconfigure(self._i_nut_vach, state="normal")
                    c.tag_raise(self._i_vach)
                    c.tag_raise(self._i_nut_vach)
                    self._dat_nhan("")
                    self._dat_nhan_so(12, max(xv + 12, 12))
                else:
                    c.itemconfigure(self._i_anh2, image="", state="hidden")
                    c.itemconfigure(self._i_vach, state="hidden")
                    c.itemconfigure(self._i_nut_vach, state="hidden")
                    self._an_so()
                    self._dat_nhan("ẢNH GỐC" if hien is not th else "")
                self.vung_ve = (px, py, out.width, out.height)
        except Exception as ex:                              # noqa: BLE001
            self.loi = f"Không vẽ được ảnh: {ex}"
            self._an_anh()
            return
        self.loc_ve = ten
        self.tang_ve = fx
        self.lan_ve += 1

    def _dat_nhan_so(self, x_truoc, x_sau):
        c = self.canvas
        for ten, x in (("truoc", x_truoc), ("sau", x_sau)):
            nen_id, chu_id = self._nhan_so[ten]
            c.coords(chu_id, x + 10, 14)
            c.itemconfigure(chu_id, state="normal")
            bb = c.bbox(chu_id)
            if bb:
                c.coords(nen_id, bb[0] - 10, bb[1] - 4, bb[2] + 10, bb[3] + 4)
            c.itemconfigure(nen_id, state="normal")
            c.tag_raise(nen_id)
            c.tag_raise(chu_id)

    def _an_so(self):
        c = self.canvas
        for nen_id, chu_id in self._nhan_so.values():
            c.itemconfigure(nen_id, state="hidden")
            c.itemconfigure(chu_id, state="hidden")
        c.itemconfigure(self._i_vach, state="hidden")
        c.itemconfigure(self._i_nut_vach, state="hidden")
        try:
            c.itemconfigure(self._i_anh2, image="", state="hidden")
        except tk.TclError:
            pass
        self._photo2 = None

    def _an_anh(self):
        #[[ Go ANH khoi muc canvas TRUOC khi bo PhotoImage: muc con tro ten mot
        #   anh da xoa thi lan itemconfigure sau (ke ca chi doi state) Tk bao
        #   "image pyimageN doesn't exist". ]]
        try:
            self.canvas.itemconfigure(self._i_anh, image="", state="hidden")
            self.canvas.itemconfigure(self._i_anh2, image="", state="hidden")
        except tk.TclError:
            pass
        self._photo = None
        self._photo2 = None

    def _dat_nhan(self, chu: str):
        c = self.canvas
        c.itemconfigure(self._i_nhan, text=chu)
        if not chu:
            c.itemconfigure(self._i_nhan_nen, state="hidden")
            return
        x0, y0, x1, y1 = c.bbox(self._i_nhan)
        c.coords(self._i_nhan_nen, x0 - 8, y0 - 4, x1 + 8, y1 + 4)
        c.itemconfigure(self._i_nhan_nen, state="normal")
        c.tag_raise(self._i_nhan_nen)
        c.tag_raise(self._i_nhan)

    # ================================================================ zoom
    def vua_khung(self) -> None:
        if self._sau is None:
            return
        self._s = None
        self._ve_tam_giua()
        self._ve()
        self._bao()

    def phong(self, k: float, diem=None) -> None:
        """Đổi tỉ lệ ×k, giữ nguyên điểm ảnh nằm dưới `diem` (toạ độ khung;
        None = giữa khung) — phóng quanh con trỏ, không quanh tâm ảnh."""
        if self._sau is None:
            return
        W, H = self._kt()
        s = self.ty_le()
        s_vua = self.s_vua()
        s2 = min(self.PHONG_MAX, max(s_vua, s * k))
        self.dat_ty_le(s2, diem)

    def dat_ty_le(self, s2: float, diem=None) -> None:
        if self._sau is None:
            return
        W, H = self._kt()
        s = self.ty_le()
        px, py = diem if diem is not None else (W / 2.0, H / 2.0)
        ix = self._cx + (px - W / 2.0) / s
        iy = self._cy + (py - H / 2.0) / s
        s_vua = self.s_vua()
        s2 = min(self.PHONG_MAX, max(s_vua, float(s2)))
        self._s = None if s2 <= s_vua * 1.0005 else s2
        s2 = self.ty_le()
        self._cx = ix - (px - W / 2.0) / s2
        self._cy = iy - (py - H / 2.0) / s2
        self._kep()
        self._nhanh()
        self._ve()
        self._bao()

    def phong_100(self, diem=None) -> None:
        """100% (ảnh nhỏ hơn khung thì 200%) quanh `diem`."""
        if self._sau is None:
            return
        self.dat_ty_le(1.0 if self.s_vua() < 0.999 else 2.0, diem)

    def vao_mat(self) -> bool:
        """Nhảy tới khuôn mặt kế tiếp (to trước), chừa lề thấy cả đầu tóc."""
        if self._sau is None or not self.mat:
            return False
        self.i_mat = (self.i_mat + 1) % len(self.mat)
        x, y, w, h = self.mat[self.i_mat]
        W, H = self._kt()
        canh = max(w, h) * 2.6
        s2 = min(W / canh, H / canh, self.MAT_MAX)
        s_vua = self.s_vua()
        self._s = None if s2 <= s_vua * 1.0005 else s2
        self._cx, self._cy = x + w / 2.0, y + h / 2.0
        self._kep()
        self._nhanh()
        self._ve()
        self._bao()
        return True

    # ================================================================ so gốc
    def giu_goc(self, co: bool, tu_chuot: bool = False) -> None:
        """Hiện bản GỐC trong lúc giữ — cùng khung nhìn, so điểm với điểm."""
        co = bool(co) and self._truoc is not None
        if co == self.hien_truoc:
            return
        self.hien_truoc = co
        self._goc_do_chuot = co and tu_chuot
        self._ve()
        self._bao()

    def _huy_giu(self):
        if self._hen_giu is not None:
            try:
                self.after_cancel(self._hen_giu)
            except tk.TclError:
                pass
            self._hen_giu = None

    def _phim_goc(self, _e=None):
        if self._hen_tha_phim is not None:
            try:
                self.after_cancel(self._hen_tha_phim)
            except tk.TclError:
                pass
            self._hen_tha_phim = None
        self.giu_goc(True)
        return "break"

    def _tha_phim_goc(self, _e=None):
        #[[ X11 tu lap phim bang cap Release/Press lien tiep — tha ngay la anh
        #   nhap nhay giua goc va sau. Doi 60 ms, co Press moi thi huy. ]]
        try:
            self._hen_tha_phim = self.after(60, self._tha_phim_that)
        except tk.TclError:
            self._hen_tha_phim = None
        return "break"

    def _tha_phim_that(self):
        self._hen_tha_phim = None
        self.giu_goc(False)

    # ================================================================ chuột
    def _gan_vach(self, x) -> bool:
        if not self._so_chia():
            return False
        W, _H = self._kt()
        return abs(x - W * self._chia) <= 10

    def _re_chuot(self, e):
        if self._so_chia():
            if self._gan_vach(e.x):
                self.canvas.configure(cursor="sb_h_double_arrow")
                return
        self.canvas.configure(cursor="fleur" if self.keo_duoc() else "arrow")

    def _nhan(self, e):
        self.canvas.focus_set()
        self._bat_dau = (e.x, e.y)
        self._keo = (e.x, e.y)
        self._da_keo = False
        self._huy_giu()
        self._keo_chia = self._gan_vach(e.x)
        if self._keo_chia:
            return
        if self._truoc is not None and self.che_do_so == "sau":
            #[[ Giu (khong keo) moi la xem goc — cham mot cai de lay tieu diem
            #   thi khong nhay sang anh goc. ]]
            try:
                self._hen_giu = self.after(GIU_MS, lambda: self.giu_goc(True, True))
            except tk.TclError:
                self._hen_giu = None

    def _di(self, e):
        if self._bat_dau is None:
            return
        if self._keo_chia:
            W, _H = self._kt()
            self._chia = min(0.98, max(0.02, e.x / max(1, W)))
            self._ve()
            return
        if not self._da_keo:
            if abs(e.x - self._bat_dau[0]) < 4 and abs(e.y - self._bat_dau[1]) < 4:
                return
            self._da_keo = True
            self._huy_giu()
            #[[ Keo la DI CHUYEN, khong phai so goc — dang hien goc (giu lau
            #   roi moi keo) thi tra ve anh chinh ngay. Ban cu ket o "ANH GOC"
            #   sau moi lan keo. ]]
            if self._goc_do_chuot:
                self.giu_goc(False)
        if self.keo_duoc():
            s = self.ty_le()
            self._cx -= (e.x - self._keo[0]) / s
            self._cy -= (e.y - self._keo[1]) / s
            self._kep()
            self._nhanh()
            self._ve()
            self._bao()
        self._keo = (e.x, e.y)

    def _tha(self, _e=None):
        self._keo_chia = False
        self._huy_giu()
        if self._goc_do_chuot:
            self.giu_goc(False)
        self._bat_dau = None
        if self._da_keo:
            self._da_keo = False
            self._lam_net()

    def _dup(self, e):
        """Nháy đúp: vừa khung → 100% đúng chỗ bấm; đang phóng → vừa khung."""
        self._huy_giu()
        if self._goc_do_chuot:
            self.giu_goc(False)
        if self._sau is None:
            return
        if self._khi_dup is not None:
            try:
                self._khi_dup()
            except Exception:                                # noqa: BLE001
                import traceback
                traceback.print_exc()
            return
        if self.la_vua():
            self.phong_100(self._diem_o(e.x, e.y))
        else:
            self.vua_khung()

    @staticmethod
    def _nac(e) -> float:
        """Số nấc của một sự kiện lăn: Windows ±120/nấc, macOS ±1..±n."""
        d = float(getattr(e, "delta", 0) or 0)
        if not d:
            return 0.0
        n = d / 120.0 if abs(d) >= 30 else d
        return max(-3.0, min(3.0, n))

    def _lan(self, e, n=None):
        if self._sau is None:
            return "break"
        n = self._nac(e) if n is None else n
        if n:
            self.phong(self.BUOC_LAN ** n, self._diem_o(e.x, e.y))
        return "break"

    def _phim_buoc(self, d):
        if self._khi_phim is not None:
            self._khi_phim(d)
        return "break"

    # ================================================================ dọn
    def _huy(self, e=None):
        if e is not None and e.widget is not self:
            return
        for ten in ("_hen_ve", "_hen_net", "_hen_bom", "_hen_giu", "_hen_tha_phim"):
            h = getattr(self, ten, None)
            if h is not None:
                try:
                    self.after_cancel(h)
                except tk.TclError:
                    pass
                setattr(self, ten, None)
        if self._bo_nap is not None:
            self._bo_nap.dung(cho=3.0)
            self._bo_nap = None
