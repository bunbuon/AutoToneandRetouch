# -*- coding: utf-8 -*-
"""chon_mau_da.py — bảng chọn màu da đích kiểu Photoshop cho hai chấm cạnh nút "Màu da".

#[[ User 16/10: "Khi di chuột vào cần hiển thị là màu da của phần nào. Ngoài ra khi bấm
#   vào chọn hãy mở bảng màu kiểu như ảnh mẫu mặc định sẽ chọn vào vùng màu da mà đang
#   hiển thị đc chọn và cho người dùng chọn trên bảng màu đó. chọn xong thì sẽ lưu màu da
#   đó làm màu đích." ]]

Hai chấm: trái = đích da TRONG NHÀ (ánh đèn), phải = NGOÀI TRỜI (ánh sáng ngày) — at.dich_da
và curve_da.dich_cua chọn khe theo at._nhan_da_ngoai.

Bảng màu: ô vuông ngang = độ bão hoà HSV (trái trắng -> phải màu thuần), dọc = độ sáng
(trên -> dưới đen); thanh dọc = sắc độ (trên 360° -> dưới 0°, như Photoshop). Ô số R G B %
theo miền Lightroom (Melissa — đúng số Develop hiện khi rê chuột lên ảnh, cùng số
mask_xem.rgb_pt báo).

LƯU (cap_nhat_mau):
  - mẫu có tên: chỉ đổi đúng khe (trong / ngoài), khe kia ghi rõ ra (mẫu cũ thiếu "ngoai"
    thì ngoài trời đi theo trong nhà — sửa trong nhà không được kéo ngoài trời theo). Số
    đo bằng mặt nạ phân vùng (trong_mn / ngoai_mn — curve da dùng khi ảnh cũng đo bằng
    phân vùng) nhân đúng tỉ lệ kênh TUYẾN TÍNH của lần đổi: hai phép đo cùng một màu da
    lệch nhau có hệ thống, giữ nguyên độ lệch đó. "trang" (vùng trắng ảnh mẫu) giữ nguyên.
  - "Mặc định" là số trong gói, không sửa -> lưu thành MẪU MỚI có tên (khe kia lấy đích
    mặc định đang hiện), app chọn luôn mẫu đó cho buổi.

Độ sáng của màu chọn chỉ dùng ở chế độ một lượt (mau_mot_luot / curve_da_sang: L_t, còn
hạ thêm da_dich_L_bu); đường thường chỉ lấy sắc + độ đậm (hue, q = C / L) — kéo dọc ô vuông
giữ nguyên hai số đó.

BÚT LẤY MÀU (16/10, user: "thêm 1 cái bút lấy màu trên ảnh ... mở 1 ảnh trên máy tính, mở bảng
màu, bấm bút và chấm vào bất kỳ đâu trên ảnh sẽ lấy đc ra đúng mã màu của điểm chấm"):
  bấm "Lấy màu" -> hộp ẩn -> chụp màn hình MỘT lần (chỉ trong bộ nhớ, không ghi / gửi đi đâu)
  -> lớp phủ gần như trong suốt trên mọi màn (nhìn vẫn thấy màn thật) bắt chuột + kính lúp
  theo con trỏ -> bấm trái lấy đúng điểm ảnh dưới mũi, Esc / bấm phải huỷ -> hộp hiện lại.
  Toạ độ Tk -> điểm ảnh quy theo TỈ LỆ cỡ ảnh chụp / vùng màn (diem_anh): Windows phóng
  125–150% (tiến trình không khai DPI: Tk đếm điểm logic, ảnh chụp là điểm thật) và Retina
  (ảnh gấp đôi điểm) đều đúng. Windows chụp cả màn ảo (mọi màn, gốc có thể âm); macOS chụp
  màn chính (screencapture), ảnh mang hồ sơ màu màn hình -> đổi về sRGB (macOS quản lý màu
  mọi cửa sổ, đổi ngược ra đúng mã màu trong file); Windows giữ nguyên số khung hình.
"""
from __future__ import annotations

import base64
import colorsys
import io
import sys
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

import numpy as np

import giao_dien as gd
import ngon_ngu

#: Khe -> tên hiện cho người dùng (chú thích chấm + tiêu đề bảng màu).
TEN_KHE = {"trong": "Màu da trong nhà", "ngoai": "Màu da ngoài trời"}
#: Tên gợi ý cho mẫu mới — dịch ở NGUỒN (ô nhập tên + khoá trong mau_da.json, như
#: MAU_DA_MAC_DINH của autotone_gui), móc Tk không dịch chữ trong ô nhập.
TEN_MOI = ngon_ngu.t("Màu da tự chọn")


# ------------------------------------------------------------------- màu

def _kep(rgb) -> list:
    return [int(max(0, min(255, round(float(v))))) for v in rgb]


def hsv_cua(rgb) -> tuple:
    """sRGB 0–255 -> (sắc 0–360°, bão hoà 0–1, sáng 0–1)."""
    r, g, b = (max(0.0, min(255.0, float(v))) / 255.0 for v in rgb)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return h * 360.0, s, v


def rgb_cua(h: float, s: float, v: float) -> list:
    """(sắc °, bão hoà, sáng) -> sRGB 0–255."""
    r, g, b = colorsys.hsv_to_rgb((float(h) % 360.0) / 360.0, max(0.0, min(1.0, float(s))),
                                  max(0.0, min(1.0, float(v))))
    return _kep((r * 255.0, g * 255.0, b * 255.0))


def pt_lr(rgb) -> list:
    """sRGB 0–255 -> R G B % như Lightroom hiện (miền Melissa), một chữ số lẻ."""
    import curve_lr as cl
    v = cl.srgb_sang_mien(np.asarray(rgb, dtype=np.float64).reshape(1, 3) / 255.0,
                          "melissa")[0] * 100.0
    return [round(float(x), 1) for x in v]


def rgb_tu_pt(pt) -> list:
    """R G B % Lightroom (Melissa) -> sRGB 0–255 (cắt gam như ảnh xuất)."""
    import curve_lr as cl
    v = np.clip(np.asarray(pt, dtype=np.float64).reshape(1, 3) / 100.0, 0.0, 1.0)
    return _kep(cl.mien_sang_srgb(v, "melissa")[0] * 255.0)


def anh_sv(h: float, n: int) -> np.ndarray:
    """Ô vuông n×n của sắc h: cột = bão hoà 0 -> 1, hàng = sáng 1 -> 0. uint8 (n, n, 3)."""
    c = np.asarray(colorsys.hsv_to_rgb((float(h) % 360.0) / 360.0, 1.0, 1.0))
    s = np.linspace(0.0, 1.0, n)[None, :, None]
    v = np.linspace(1.0, 0.0, n)[:, None, None]
    return (v * (1.0 - s + s * c[None, None, :]) * 255.0 + 0.5).astype(np.uint8)


def anh_sac(rong: int, cao: int) -> np.ndarray:
    """Thanh sắc độ dọc: trên 360° -> dưới 0° (như Photoshop). uint8 (cao, rong, 3)."""
    hang = np.array([colorsys.hsv_to_rgb(x % 1.0, 1.0, 1.0) for x in np.linspace(1.0, 0.0, cao)])
    return np.repeat((hang * 255.0 + 0.5).astype(np.uint8)[:, None, :], rong, axis=1)


def _lin(rgb) -> np.ndarray:
    x = np.clip(np.asarray(rgb, dtype=np.float64) / 255.0, 0.0, 1.0)
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def _tu_lin(lin) -> list:
    x = np.clip(np.asarray(lin, dtype=np.float64), 0.0, 1.0)
    return _kep(np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055) * 255.0)


# ------------------------------------------------------------------- lưu

def ten_trong(d: dict, ten: str, cam=()) -> str:
    """Tên mẫu mới hợp lệ, chưa có trong d (thêm " 2", " 3"… nếu trùng)."""
    ten = (ten or "").strip()[:60] or TEN_MOI
    if ten in cam or ten.startswith("_"):
        ten = ten.lstrip("_") + " (riêng)"
    goc, i = ten, 2
    while ten in d:
        ten = f"{goc} {i}"
        i += 1
    return ten


def cap_nhat_mau(d: dict, ten: str | None, khe: str, rgb_moi, goc, ten_moi: str = TEN_MOI,
                 cam=(), luc: str | None = None) -> str:
    """Ghi màu khe ("trong" / "ngoai") vào d (nội dung mau_da.json, sửa tại chỗ).

    ten: mẫu có tên đang chọn -> sửa mẫu đó; None / không có trong d ("Mặc định") -> mẫu
    MỚI tên ten_moi (không đè mẫu sẵn có) với khe kia = goc (đích đang hiện).
    -> tên mẫu đã ghi."""
    if khe not in TEN_KHE:
        raise ValueError(khe)
    rgb_moi = _kep(rgb_moi)
    luc = luc or datetime.now().isoformat(timespec="seconds")
    m = d.get(ten) if ten else None
    if isinstance(m, dict) and m.get("trong"):
        m = dict(m)
        cu = list(m.get(khe) or m["trong"])
        m["ngoai"] = list(m.get("ngoai") or m["trong"])
        if m.get("trong_mn"):
            m["ngoai_mn"] = list(m.get("ngoai_mn") or m["trong_mn"])
            ti = np.clip(_lin(rgb_moi) / np.maximum(_lin(cu), 1e-4), 0.2, 5.0)
            m[khe + "_mn"] = _tu_lin(_lin(m[khe + "_mn"]) * ti)
        m[khe] = rgb_moi
        m["sua_tay"] = luc
        d[ten] = m
        return ten
    ten = ten_trong(d, ten_moi, cam)
    m = {"trong": _kep(goc[0]), "ngoai": _kep(goc[1]), "luc": luc, "sua_tay": luc,
         "tu_mac_dinh": True}
    m[khe] = rgb_moi
    d[ten] = m
    return ten


# ------------------------------------------------------------------- bút lấy màu

def _vung_ao_win() -> tuple | None:
    """(x, y, rộng, cao) màn hình ẢO (mọi màn) theo toạ độ của tiến trình — cùng hệ với Tk."""
    try:
        import ctypes
        u = ctypes.windll.user32
        x, y, w, h = (int(u.GetSystemMetrics(i)) for i in (76, 77, 78, 79))
        return (x, y, w, h) if w > 0 and h > 0 else None
    except Exception:                                        # noqa: BLE001
        return None


def quyen_chup_mac() -> bool | None:
    """macOS 10.15+: app đã được phép Ghi màn hình chưa (chưa thì xin — hệ thống tự hỏi /
    mở Cài đặt). Thiếu quyền thì screencapture chỉ ra hình nền, KHÔNG báo lỗi -> phải hỏi
    trước. None: không phải macOS / không hỏi được."""
    if sys.platform != "darwin":
        return None
    try:
        import ctypes
        cg = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
        cg.CGPreflightScreenCaptureAccess.restype = ctypes.c_bool
        if cg.CGPreflightScreenCaptureAccess():
            return True
        cg.CGRequestScreenCaptureAccess.restype = ctypes.c_bool
        return bool(cg.CGRequestScreenCaptureAccess())
    except Exception:                                        # noqa: BLE001
        return None


def _ve_srgb(im):
    """Ảnh chụp mang hồ sơ màu màn hình (macOS) -> sRGB; không có hồ sơ -> giữ nguyên."""
    icc = im.info.get("icc_profile")
    if not icc:
        return im
    try:
        from PIL import ImageCms
        return ImageCms.profileToProfile(im.convert("RGB"), ImageCms.ImageCmsProfile(io.BytesIO(icc)),
                                         ImageCms.createProfile("sRGB"), outputMode="RGB")
    except Exception:                                        # noqa: BLE001
        return im


def chup_man_hinh(w) -> tuple:
    """Chụp màn hình -> (uint8 (H, W, 3), (x0, y0, rộng, cao) vùng Tk mà ảnh phủ). Chỉ giữ
    trong bộ nhớ cho MỘT lần lấy màu."""
    from PIL import ImageGrab
    vung = _vung_ao_win() if sys.platform == "win32" else None
    if vung is not None:
        im = ImageGrab.grab(all_screens=True)
    else:
        im = ImageGrab.grab()
        vung = (0, 0, int(w.winfo_screenwidth()), int(w.winfo_screenheight()))
    return np.asarray(_ve_srgb(im).convert("RGB")), vung


def diem_anh(anh: np.ndarray, vung, x: float, y: float) -> tuple | None:
    """Toạ độ Tk (x, y) -> (cột, hàng) trên ảnh chụp; None khi ngoài ảnh."""
    x0, y0, rw, rh = vung
    cao, rong = anh.shape[:2]
    px = int((float(x) - x0) * rong / max(rw, 1))
    py = int((float(y) - y0) * cao / max(rh, 1))
    return (px, py) if 0 <= px < rong and 0 <= py < cao else None


def mau_tai(anh: np.ndarray, vung, x: float, y: float) -> list | None:
    """Màu sRGB 0–255 của ĐÚNG điểm ảnh dưới mũi chuột (x, y toạ độ Tk); None ngoài ảnh."""
    d = diem_anh(anh, vung, x, y)
    return None if d is None else [int(v) for v in anh[d[1], d[0], :3]]


def anh_kinh_lup(anh: np.ndarray, vung, x: float, y: float, r: int = 6, phong: int = 9) -> np.ndarray:
    """Ô phóng to (2r+1)² điểm ảnh quanh mũi chuột, mỗi điểm phong × phong; ngoài ảnh tô xám."""
    k = 2 * r + 1
    o = np.full((k, k, 3), 64, dtype=np.uint8)
    d = diem_anh(anh, vung, x, y)
    if d is not None:
        cao, rong = anh.shape[:2]
        px, py = d
        x1, x2, y1, y2 = max(px - r, 0), min(px + r + 1, rong), max(py - r, 0), min(py + r + 1, cao)
        o[y1 - (py - r):y2 - (py - r), x1 - (px - r):x2 - (px - r)] = anh[y1:y2, x1:x2, :3]
    return np.repeat(np.repeat(o, phong, axis=0), phong, axis=1)


class ButLayMau:
    """Bút lấy màu toàn màn hình. xong(rgb) khi bấm trái, xong(None) khi Esc / bấm phải."""

    R, PHONG = 6, 9

    def __init__(self, cha, xong):
        self.xong = xong
        self.anh, self.vung = chup_man_hinh(cha)
        m = gd.MAU
        x0, y0, rw, rh = self.vung
        #  lớp phủ gần trong suốt: nhìn xuyên thấy màn thật mà vẫn nhận chuột (alpha 0 thì
        #  chuột lọt xuống cửa sổ bên dưới). macOS 0.05 — cửa sổ quá trong có thể bị Cocoa
        #  cho chuột lọt qua; màu lấy từ ẢNH CHỤP nên lớp phủ tối 5% không đổi số.
        self.phu = tk.Toplevel(cha)
        self.phu.overrideredirect(True)
        self.phu.configure(background="#000000", cursor="crosshair")
        self.phu.geometry(f"{rw}x{rh}{x0:+d}{y0:+d}")
        for k, v in (("-alpha", 0.05 if sys.platform == "darwin" else 0.01), ("-topmost", True)):
            try:
                self.phu.attributes(k, v)
            except tk.TclError:
                pass
        #  kính lúp: cửa sổ riêng chạy theo con trỏ (lệch 24 px — chuột không bao giờ đè lên)
        self.lup = tk.Toplevel(cha)
        self.lup.overrideredirect(True)
        try:
            self.lup.attributes("-topmost", True)
        except tk.TclError:
            pass
        vien = tk.Frame(self.lup, background=m["vien2"], padx=1, pady=1)
        vien.pack()
        trong = tk.Frame(vien, background=m["noi"], padx=6, pady=6)
        trong.pack()
        c = (2 * self.R + 1) * self.PHONG
        self.cv = tk.Canvas(trong, width=c, height=c, highlightthickness=0, background="#404040")
        self.cv.pack()
        h = tk.Frame(trong, background=m["noi"])
        h.pack(fill="x", pady=(6, 0))
        self.o_mau = tk.Frame(h, width=18, height=18, background="#404040",
                              highlightthickness=1, highlightbackground=m["vien2"])
        self.o_mau.pack(side="left")
        self.lbl = tk.Label(h, text="", background=m["noi"], foreground=m["chu"],
                            font=gd.phong(9, "so"), justify="left", anchor="w")
        self.lbl.pack(side="left", padx=(6, 0))
        tk.Label(trong, text="Bấm để lấy màu · Esc để huỷ", background=m["noi"],
                 foreground=m["mo"], font=gd.CHU_NHO).pack(anchor="w", pady=(4, 0))
        self._anh_lup = None
        for w in (self.phu, self.lup):
            w.bind("<Escape>", lambda _e: self.ket_thuc(None))
            w.bind("<Button-3>", lambda _e: self.ket_thuc(None))
        self.phu.bind("<Motion>", self._di)
        self.phu.bind("<Button-1>", self._bam)
        try:
            px, py = cha.winfo_pointerxy()
            self.cap_nhat(px, py)
            self.phu.update_idletasks()
            self.phu.focus_force()
            self.phu.grab_set()
        except tk.TclError:
            pass

    def cap_nhat(self, x: float, y: float):
        """Kính lúp + màu dưới mũi chuột (x, y toạ độ Tk)."""
        self._anh_lup = anh_tk(self.cv, anh_kinh_lup(self.anh, self.vung, x, y, self.R, self.PHONG))
        self.cv.delete("all")
        self.cv.create_image(0, 0, image=self._anh_lup, anchor="nw")
        a, k = self.R * self.PHONG, self.PHONG
        self.cv.create_rectangle(a - 1, a - 1, a + k, a + k, outline="#000000")
        self.cv.create_rectangle(a, a, a + k - 1, a + k - 1, outline="#ffffff")
        rgb = mau_tai(self.anh, self.vung, x, y)
        if rgb is None:
            self.o_mau.configure(background="#404040")
            self.lbl.configure(text="Ngoài vùng chụp")
        else:
            self.o_mau.configure(background="#%02x%02x%02x" % tuple(rgb))
            r, g, b = pt_lr(rgb)
            self.lbl.configure(text=f"R {r:.1f} · G {g:.1f} · B {b:.1f} %\n"
                                    f"sRGB {rgb[0]} · {rgb[1]} · {rgb[2]}")
        #  kính lúp lệch dưới-phải con trỏ; sát mép thì lật sang trái / lên trên
        self.lup.update_idletasks()
        lw, lh = self.lup.winfo_reqwidth(), self.lup.winfo_reqheight()
        x0, y0, rw, rh = self.vung
        xi, yi = int(x), int(y)
        lx = xi + 24 if xi + 24 + lw <= x0 + rw else xi - 24 - lw
        ly = yi + 24 if yi + 24 + lh <= y0 + rh else yi - 24 - lh
        self.lup.geometry(f"{lx:+d}{ly:+d}")

    def _di(self, e):
        self.cap_nhat(e.x_root, e.y_root)

    def _bam(self, e):
        rgb = mau_tai(self.anh, self.vung, e.x_root, e.y_root)
        if rgb is not None:
            self.ket_thuc(rgb)

    def ket_thuc(self, rgb):
        if self.phu is None:
            return
        for w in (self.phu, self.lup):
            try:
                w.grab_release()
            except tk.TclError:
                pass
            try:
                w.destroy()
            except tk.TclError:
                pass
        self.phu = self.lup = None
        self.anh = None                                  # bỏ ảnh chụp ngay
        if self.xong is not None:
            self.xong(rgb)


# ------------------------------------------------------------------- giao diện

def chu_cham(khe: str, rgb, ten_mau: str | None) -> str:
    """Chú thích khi rê chuột lên một chấm."""
    r, g, b = pt_lr(rgb)
    mau = f"Mẫu “{ten_mau}”" if ten_mau else "Mẫu mặc định"
    return (f"{TEN_KHE[khe]} · {mau}\n"
            f"Lightroom: R {r:.1f} · G {g:.1f} · B {b:.1f} %\n"
            "Bấm để chọn màu.")


def anh_tk(w, arr: np.ndarray) -> tk.PhotoImage:
    """Mảng uint8 -> PhotoImage qua PNG (Tk 8.6 tự đọc) — không cần ImageTk (bản Mac
    không gắn được ImageTk vào Tk, xem gd.va_imagetk)."""
    from PIL import Image
    b = io.BytesIO()
    Image.fromarray(np.ascontiguousarray(arr), "RGB").save(b, "PNG", compress_level=1)
    return tk.PhotoImage(master=w, data=base64.b64encode(b.getvalue()).decode("ascii"),
                         format="png")


class HopChonMauDa(tk.Toplevel):
    """Bảng chọn màu cho một khe. xong(rgb, ten_moi) khi bấm Lưu — ten_moi: tên mẫu mới
    người dùng gõ (chỉ khi đang ở "Mặc định"), None khi sửa mẫu có tên."""

    def __init__(self, cha, rgb, khe: str, ten_mau: str | None = None,
                 ten_moi: str | None = None, gan=None, xong=None):
        super().__init__(cha.winfo_toplevel())
        m = gd.MAU
        self.xong, self.khe, self.ten_mau = xong, khe, ten_mau
        self.goc = _kep(rgb)
        self.h, self.s, self.v = hsv_cua(self.goc)
        self._pt_hien: list = []
        self._anh_sv = self._anh_sac = None
        self.title(TEN_KHE[khe])
        self.transient(cha.winfo_toplevel())
        self.resizable(False, False)
        self.configure(background=m["nen"])
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        u = gd.don_vi(self)
        self.n = max(200, min(360, 13 * u))           # cạnh ô vuông theo DPI
        self.p = 8                                     # lề cho vòng chọn ở mép
        o = tk.Frame(self, background=m["nen"], padx=18, pady=14)
        o.pack(fill="both", expand=True)
        tk.Label(o, text=TEN_KHE[khe], background=m["nen"], foreground=m["chu"],
                 font=gd.phong(13, "dam2")).pack(anchor="w")
        tk.Label(o, text=(f"Mẫu “{ten_mau}”" if ten_mau else
                          "Mẫu mặc định — lưu thành mẫu mới"),
                 background=m["nen"], foreground=m["mo"], font=gd.CHU_NHO).pack(
            anchor="w", pady=(2, 10))

        hang = tk.Frame(o, background=m["nen"])
        hang.pack(anchor="w")
        #  ô mới (trên) / hiện tại (dưới) — bấm ô dưới là trả về màu cũ
        o_mau = tk.Frame(hang, background=m["nen"])
        o_mau.pack(side="left", anchor="n", padx=(0, 12))
        k = 3 * u
        tk.Label(o_mau, text="Mới", background=m["nen"], foreground=m["mo"],
                 font=gd.CHU_NHO).pack()
        self.cv_moi = tk.Canvas(o_mau, width=k, height=k, highlightthickness=1,
                                highlightbackground=m["vien"], background=m["nen"])
        self.cv_moi.pack()
        self.cv_cu = tk.Canvas(o_mau, width=k, height=k, highlightthickness=1,
                               highlightbackground=m["vien"], cursor="hand2",
                               background="#%02x%02x%02x" % tuple(self.goc))
        self.cv_cu.pack()
        tk.Label(o_mau, text="Hiện tại", background=m["nen"], foreground=m["mo"],
                 font=gd.CHU_NHO).pack()
        self.cv_cu.bind("<Button-1>", lambda _e: self.dat_rgb(self.goc))
        gd.GoiY(self.cv_cu, "Bấm để trả về màu hiện tại.")

        n, p = self.n, self.p
        self.cv_sv = tk.Canvas(hang, width=n + 2 * p, height=n + 2 * p, highlightthickness=0,
                               background=m["nen"], cursor="crosshair")
        self.cv_sv.pack(side="left")
        self.rong_sac = max(16, u)
        self.lech_sac = 12                              # chỗ cho tam giác bên trái thanh
        self.cv_sac = tk.Canvas(hang, width=self.lech_sac + self.rong_sac + 2,
                                height=n + 2 * p, highlightthickness=0, background=m["nen"],
                                cursor="sb_v_double_arrow")
        self.cv_sac.pack(side="left", padx=(6, 0))
        self._anh_sac = anh_tk(self, anh_sac(self.rong_sac, n))
        self.cv_sac.create_image(self.lech_sac, p, image=self._anh_sac, anchor="nw")
        self.cv_sac.create_rectangle(self.lech_sac, p, self.lech_sac + self.rong_sac, p + n - 1,
                                     outline=m["vien"])
        for su_kien in ("<Button-1>", "<B1-Motion>"):
            self.cv_sv.bind(su_kien, self._keo_sv)
            self.cv_sac.bind(su_kien, self._keo_sac)

        #  R G B % như Lightroom — gõ số rồi Enter
        so = tk.Frame(o, background=m["nen"])
        so.pack(fill="x", pady=(12, 0))
        tk.Label(so, text="Lightroom %", background=m["nen"], foreground=m["mo"],
                 font=gd.CHU_NHO).pack(side="left", padx=(0, 8))
        self.bien_pt = []
        for ten in ("R", "G", "B"):
            tk.Label(so, text=ten, background=m["nen"], foreground=m["chu"],
                     font=gd.CHU_DAM).pack(side="left", padx=(6, 3))
            b = tk.StringVar()
            e = ttk.Entry(so, textvariable=b, width=6, justify="right")
            e.pack(side="left")
            e.bind("<Return>", self._go_so)
            e.bind("<FocusOut>", lambda _e: self._doc_so())
            self.bien_pt.append(b)
        self.lbl_srgb = tk.Label(so, text="", background=m["nen"], foreground=m["mo"],
                                 font=gd.phong(9, "so"))
        self.lbl_srgb.pack(side="right")
        tk.Label(o, text="Màu này quyết sắc và độ đậm của da; độ sáng da mặt vẫn theo "
                         "Bù sáng.", background=m["nen"], foreground=m["mo"],
                 font=gd.CHU_NHO, justify="left", wraplength=n + 6 * u).pack(
            anchor="w", pady=(8, 0))

        self.bien_ten = None
        if not ten_mau:
            h_ten = tk.Frame(o, background=m["nen"])
            h_ten.pack(fill="x", pady=(10, 0))
            tk.Label(h_ten, text="Tên mẫu mới", background=m["nen"], foreground=m["chu"],
                     font=gd.CHU).pack(side="left", padx=(0, 8))
            self.bien_ten = tk.StringVar(value=ten_moi or TEN_MOI)
            ttk.Entry(h_ten, textvariable=self.bien_ten, width=28).pack(
                side="left", fill="x", expand=True)

        day = tk.Frame(o, background=m["nen"])
        day.pack(fill="x", pady=(14, 0))
        self.btn_luu = gd.NutTron(day, "Lưu làm màu đích", kieu="chinh", nen=m["nen"],
                                  command=self._luu)
        self.btn_luu.pack(side="right")
        gd.NutTron(day, "Huỷ", kieu="phu", nen=m["nen"], command=self.destroy).pack(
            side="right", padx=(0, 8))
        self._but = None
        self.btn_hut = gd.NutTron(day, "Lấy màu", icon="hut_mau", kieu="phu", nen=m["nen"],
                                  command=self.lay_mau)
        self.btn_hut.pack(side="left")
        gd.GoiY(self.btn_hut, "Bút lấy màu: chấm vào bất kỳ đâu trên màn hình (ảnh đang mở, "
                              "Lightroom…) để lấy đúng màu điểm đó. Esc để huỷ.")
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Return>", lambda _e: self._luu())

        self._ve_sv()
        self._cap_nhat()
        self._dat_cho(cha, gan)

    # ------------------------------------------------------------ vẽ
    def _dat_cho(self, cha, gan):
        try:
            self.update_idletasks()
            top = cha.winfo_toplevel()
            tx, ty, tw, th = (top.winfo_rootx(), top.winfo_rooty(), top.winfo_width(),
                              top.winfo_height())
            w, h = self.winfo_reqwidth(), self.winfo_reqheight()
            if gan is not None and gan.winfo_ismapped():
                x = gan.winfo_rootx() + gan.winfo_width() - w
                y = gan.winfo_rooty() + gan.winfo_height() + 6
            else:
                x, y = tx + (tw - w) // 2, ty + (th - h) // 3
            x = max(tx, min(x, tx + tw - w)) if tw > w else x
            y = max(ty, min(y, ty + th - h)) if th > h else y
            self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
            self.grab_set()
            self.focus_set()
        except tk.TclError:
            pass

    def _ve_sv(self):
        self._anh_sv = anh_tk(self, anh_sv(self.h, self.n))
        self.cv_sv.delete("anh")
        self.cv_sv.create_image(self.p, self.p, image=self._anh_sv, anchor="nw", tags="anh")
        self.cv_sv.tag_lower("anh")

    def _cap_nhat(self, ghi_so: bool = True):
        n, p = self.n, self.p
        rgb = self.rgb()
        hx = "#%02x%02x%02x" % tuple(rgb)
        self.cv_moi.configure(background=hx)
        #  vòng chọn: viền đen trên nền sáng, trắng trên nền tối (như Photoshop)
        x, y = p + self.s * (n - 1), p + (1.0 - self.v) * (n - 1)
        sang = (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) > 140
        self.cv_sv.delete("vong")
        self.cv_sv.create_oval(x - 6, y - 6, x + 6, y + 6, width=2, tags="vong",
                               outline="#000000" if sang else "#ffffff")
        y = p + (1.0 - min(max(self.h, 0.0), 360.0) / 360.0) * (n - 1)
        self.cv_sac.delete("tam_giac")
        self.cv_sac.create_polygon(1, y - 6, self.lech_sac - 2, y, 1, y + 6, fill="#ffffff",
                                   outline=gd.MAU["vien"], tags="tam_giac")
        self.lbl_srgb.configure(text="sRGB %d · %d · %d" % tuple(rgb))
        if ghi_so:
            self._pt_hien = ["%.1f" % x for x in pt_lr(rgb)]
            for b, x in zip(self.bien_pt, self._pt_hien):
                b.set(x)

    # ------------------------------------------------------------ điều khiển
    def rgb(self) -> list:
        return rgb_cua(self.h, self.s, self.v)

    def dat_rgb(self, rgb, ghi_so: bool = True):
        h, s, v = hsv_cua(rgb)
        #  xám không có sắc / đen không có bão hoà -> giữ số đang có
        if s > 1e-6 and v > 1e-6:
            self.h = h
        if v > 1e-6:
            self.s = s
        self.v = v
        self._ve_sv()
        self._cap_nhat(ghi_so)

    def _keo_sv(self, e):
        n, p = self.n, self.p
        self.s = max(0.0, min(1.0, (e.x - p) / (n - 1)))
        self.v = max(0.0, min(1.0, 1.0 - (e.y - p) / (n - 1)))
        self._cap_nhat()

    def _keo_sac(self, e):
        n, p = self.n, self.p
        self.h = 360.0 * max(0.0, min(1.0, 1.0 - (e.y - p) / (n - 1)))
        self._ve_sv()
        self._cap_nhat()

    def _doc_so(self) -> bool:
        """Áp số R G B % đang gõ (nếu khác số đang hiện). False khi số không hợp lệ."""
        chu = [b.get().strip().replace(",", ".") for b in self.bien_pt]
        if chu == self._pt_hien:
            return True
        try:
            pt = [float(x) for x in chu]
        except ValueError:
            self._cap_nhat()
            return False
        if not all(0.0 <= x <= 100.0 for x in pt):
            self._cap_nhat()
            return False
        self.dat_rgb(rgb_tu_pt(pt), ghi_so=False)
        self._pt_hien = chu
        return True

    def lay_mau(self):
        """Nút "Lấy màu": ẩn hộp (khỏi che ảnh) rồi mới chụp màn hình."""
        if self._but is not None:
            return
        if quyen_chup_mac() is False:
            messagebox.showinfo(
                "Bút lấy màu",
                "Cần cho phép ghi màn hình: System Settings › Privacy & Security › Screen "
                "Recording → bật Tone&Retouch, rồi mở lại app.", parent=self)
            return
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.withdraw()
        self._but = True                                  # đang chờ chụp
        self.after(250, self._bat_dau_but)                # chờ hộp ẩn hẳn

    def _bat_dau_but(self):
        try:
            self._but = ButLayMau(self.master, self._xong_but)
        except Exception as ex:                          # noqa: BLE001
            self._but = None
            self._hien_lai()
            messagebox.showerror("Bút lấy màu", f"Không chụp được màn hình: {ex}", parent=self)

    def _xong_but(self, rgb):
        self._but = None
        self._hien_lai()
        if rgb:
            self.dat_rgb(rgb)

    def _hien_lai(self):
        try:
            self.deiconify()
            self.lift()
            self.grab_set()
            self.focus_set()
        except tk.TclError:
            pass

    def _go_so(self, _e=None):
        self._doc_so()
        return "break"                                  # Enter trong ô số không bấm Lưu

    def _luu(self):
        self._doc_so()
        ten = self.bien_ten.get().strip() if self.bien_ten is not None else None
        rgb = self.rgb()
        self.destroy()
        if self.xong is not None:
            self.xong(rgb, ten)
