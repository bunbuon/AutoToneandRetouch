#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bieu_tuong.py — Bộ biểu tượng của Tone&Retouch (7/10, thiết kế lại).

VÌ SAO CÓ MODULE NÀY
    Trước đây biểu tượng vẽ thẳng bằng nét canvas của Tk (create_line /
    create_oval). Tk trên Windows KHÔNG khử răng cưa nét canvas: đường chéo,
    vòng tròn, góc bo đều lởm chởm, nét mảnh 1 px lúc có lúc không — nhìn gần
    thấy ngay "đồ vẽ tay", lệch hẳn với nút bo tròn (đã dựng bằng PIL) ngay
    bên cạnh.

    Nay mọi biểu tượng là ĐƯỜNG VECTOR trên lưới 24 × 24 (cú pháp path của
    SVG), dựng bằng PIL ở cỡ GẤP 4 rồi thu nhỏ (LANCZOS) — mịn như icon của
    Evoto / Lightroom ở mọi cỡ và mọi mức phóng DPI, vẽ một lần rồi giữ trong
    bộ nhớ đệm theo (tên, cỡ, màu).

PHONG CÁCH (một bộ, không lẫn)
    Nét đều 1,8 / 24 (to nhỏ theo cỡ), đầu nét và góc nối BO TRÒN, hình đặc
    chỉ dùng cho thứ cần nặng mắt (▶ chạy, ■ dừng, chấm "thêm"). Góc hình bo
    1,5–2 đơn vị. Khung an toàn 3–21: biểu tượng nào cũng chiếm cùng một cỡ
    thị giác, đặt cạnh nhau không cái to cái nhỏ.

    Tất cả do app tự vẽ (không lấy của bộ icon nào) — khỏi lo giấy phép.

DÙNG
    anh_bieu_tuong(w, "thu_muc", 18, "#e8e9eb") -> PhotoImage (đã đệm)
    co("thu_muc") -> True nếu có trong bộ
    gd.ve_bieu_tuong(canvas, ten, cx, cy, s, mau) gọi qua đây.
"""
from __future__ import annotations

import math
import re

# ── Bộ biểu tượng ────────────────────────────────────────────────────────
#  Mỗi biểu tượng = danh sách nét:
#    ("p", "<path SVG>")            nét viền (stroke)
#    ("pf", "<path SVG>")           hình đặc (fill) — kèm viền cùng màu cho mép bo
#    ("o", cx, cy, r)               vòng tròn viền
#    ("of", cx, cy, r)              chấm tròn đặc
#    ("r", x, y, w, h, bo)          hình chữ nhật bo góc, viền
#    ("rf", x, y, w, h, bo)         hình chữ nhật bo góc, đặc
BO: dict[str, list] = {
    # Cân tone — ba thanh trượt, núm rỗng (đường đứt quanh núm)
    "tone": [
        ("p", "M4 6.5H7.4"), ("p", "M12.6 6.5H20"), ("o", 10, 6.5, 2.4),
        ("p", "M4 12H13.4"), ("p", "M18.6 12H20"), ("o", 16, 12, 2.4),
        ("p", "M4 17.5H5.4"), ("p", "M10.6 17.5H20"), ("o", 8, 17.5, 2.4),
    ],
    # Retouch — chân dung + ngôi sao lấp lánh (làm đẹp)
    "retouch": [
        ("o", 10.5, 8.6, 3.6),
        ("p", "M3.8 20.2C4.6 16.4 7.2 14.4 10.5 14.4C13.8 14.4 16.4 16.4 17.2 20.2"),
        ("pf", "M18.6 3.2L19.35 5.15L21.3 5.9L19.35 6.65L18.6 8.6L17.85 6.65L15.9 5.9"
               "L17.85 5.15Z"),
    ],
    "thu_muc": [
        ("p", "M3.6 7.4C3.6 6.5 4.3 5.8 5.2 5.8H9.2L11.2 7.9H18.8C19.7 7.9 20.4 8.6 "
              "20.4 9.5V17C20.4 17.9 19.7 18.6 18.8 18.6H5.2C4.3 18.6 3.6 17.9 3.6 17Z"),
    ],
    "them": [("of", 5.8, 12, 1.55), ("of", 12, 12, 1.55), ("of", 18.2, 12, 1.55)],
    "luoi": [("r", 4, 4, 6.8, 6.8, 1.6), ("r", 13.2, 4, 6.8, 6.8, 1.6),
             ("r", 4, 13.2, 6.8, 6.8, 1.6), ("r", 13.2, 13.2, 6.8, 6.8, 1.6)],
    "bang": [("of", 5.2, 7, 1.15), ("of", 5.2, 12, 1.15), ("of", 5.2, 17, 1.15),
             ("p", "M9 7H20"), ("p", "M9 12H20"), ("p", "M9 17H20")],
    # ↺ đặt lại — cung 315° ngược chiều kim đồng hồ, đầu mũi tên góc trên trái
    "dat_lai": [
        ("p", "M5 12A7 7 0 1 0 7.05 7.05"),
        ("p", "M7.05 3.2V7.05H3.2"),
    ],
    "mui_xuong": [("p", "M8 10.2L12 14.2L16 10.2")],
    "chevron_phai": [("p", "M9.5 6L15.5 12L9.5 18")],
    "chevron_xuong": [("p", "M6 9.5L12 15.5L18 9.5")],
    "chevron_trai": [("p", "M14.5 6L8.5 12L14.5 18")],
    # Vào mặt — bốn góc khung lấy nét + khuôn mặt cười
    "mat": [
        ("p", "M3.8 8.2V6.2C3.8 4.9 4.9 3.8 6.2 3.8H8.2"),
        ("p", "M15.8 3.8H17.8C19.1 3.8 20.2 4.9 20.2 6.2V8.2"),
        ("p", "M20.2 15.8V17.8C20.2 19.1 19.1 20.2 17.8 20.2H15.8"),
        ("p", "M8.2 20.2H6.2C4.9 20.2 3.8 19.1 3.8 17.8V15.8"),
        ("of", 9.4, 10.2, 1.05), ("of", 14.6, 10.2, 1.05),
        ("p", "M9 14.4C9.7 15.4 10.8 15.9 12 15.9C13.2 15.9 14.3 15.4 15 14.4"),
    ],
    "anh": [
        ("r", 3.4, 4.6, 17.2, 14.8, 2.2),
        ("p", "M3.6 16.6L8.6 11.8L12.6 15.6L15 13.3L20.4 18"),
        ("o", 15.4, 9.4, 1.7),
    ],
    "chay": [("pf", "M8.2 5.6C8.2 4.9 9 4.5 9.6 4.9L18.6 11.2C19.1 11.6 19.1 12.4 18.6 "
                    "12.8L9.6 19.1C9 19.5 8.2 19.1 8.2 18.4Z")],
    "dung": [("rf", 6.2, 6.2, 11.6, 11.6, 2.2)],
    # Giữ xem gốc — khung chia đôi, nửa trái đặc (trước | sau)
    "so_sanh": [
        ("r", 3.4, 5, 17.2, 14, 2.2),
        ("pf", "M5.6 5H12V19H5.6C4.4 19 3.4 18 3.4 16.8V7.2C3.4 6 4.4 5 5.6 5Z"),
        ("p", "M12 3V21"),
    ],
    # ? trong vòng tròn
    "hoi": [
        ("o", 12, 12, 8.6),
        ("p", "M9.5 9.6C9.5 8.2 10.6 7.2 12 7.2C13.4 7.2 14.5 8.2 14.5 9.5C14.5 11.4 "
              "12 11.6 12 13.6"),
        ("of", 12, 16.6, 1.15),
    ],
    "dong": [("p", "M7 7L17 17"), ("p", "M17 7L7 17")],
    "xong": [("p", "M5 12.5L9.8 17.2L19 7.2")],
    "canh": [  # tam giác cảnh báo
        ("p", "M10.4 4.6C11.1 3.4 12.9 3.4 13.6 4.6L20.6 17C21.3 18.2 20.4 19.6 19 "
              "19.6H5C3.6 19.6 2.7 18.2 3.4 17Z"),
        ("p", "M12 9.4V13.4"), ("of", 12, 16.4, 1.1),
    ],
    "cong": [("p", "M12 5V19"), ("p", "M5 12H19")],
    "tai": [  # tải về
        ("p", "M12 4V14.6"), ("p", "M7.4 10.2L12 14.8L16.6 10.2"),
        ("p", "M4.6 16.4V18C4.6 19.1 5.5 20 6.6 20H17.4C18.5 20 19.4 19.1 19.4 18V16.4"),
    ],
    "dong_bo": [  # Sync — hai mũi tên vòng
        ("p", "M19.4 10.4A7.6 7.6 0 0 0 5.8 7.4"), ("p", "M5.2 3.6V7.8H9.4"),
        ("p", "M4.6 13.6A7.6 7.6 0 0 0 18.2 16.6"), ("p", "M18.8 20.4V16.2H14.6"),
    ],
}

NET = 1.8          # bề dày nét trên lưới 24
SS = 4             # dựng gấp 4 rồi thu nhỏ


def co(ten: str) -> bool:
    return ten in BO


# ── Đọc path SVG → các đoạn điểm (đã dàn phẳng đường cong) ──────────────
_SO = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]|-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def _cung(x1, y1, rx, ry, phi, lon, chieu, x2, y2, n=24):
    """Cung elip SVG (dạng điểm đầu-cuối) -> các điểm. Theo phụ lục F.6 của SVG."""
    if rx == 0 or ry == 0:
        return [(x2, y2)]
    cp, sp = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    x1p, y1p = cp * dx + sp * dy, -sp * dx + cp * dy
    rx, ry = abs(rx), abs(ry)
    lam = (x1p ** 2) / rx ** 2 + (y1p ** 2) / ry ** 2
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    tu = rx ** 2 * ry ** 2 - rx ** 2 * y1p ** 2 - ry ** 2 * x1p ** 2
    mau = rx ** 2 * y1p ** 2 + ry ** 2 * x1p ** 2
    k = math.sqrt(max(0.0, tu / mau)) if mau else 0.0
    if lon == chieu:
        k = -k
    cxp, cyp = k * rx * y1p / ry, -k * ry * x1p / rx
    cx = cp * cxp - sp * cyp + (x1 + x2) / 2
    cy = sp * cxp + cp * cyp + (y1 + y2) / 2

    def goc(ux, uy, vx, vy):
        g = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return g

    t1 = goc(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dt = goc((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not chieu and dt > 0:
        dt -= 2 * math.pi
    elif chieu and dt < 0:
        dt += 2 * math.pi
    n = max(6, int(abs(dt) / (2 * math.pi) * 64))
    ra = []
    for i in range(1, n + 1):
        t = t1 + dt * i / n
        x = cx + rx * math.cos(t) * cp - ry * math.sin(t) * sp
        y = cy + rx * math.cos(t) * sp + ry * math.sin(t) * cp
        ra.append((x, y))
    return ra


def _bezier(p0, p1, p2, p3, n=20):
    ra = []
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        ra.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                   u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
    return ra


def doc_path(d: str) -> list:
    """Path SVG -> [(điểm..., kín?)]. Đủ cho bộ này: M L H V C S Q T A Z, hoa / thường."""
    tk = _SO.findall(d)
    i = 0
    doan, dang = [], []
    x = y = x0 = y0 = 0.0
    lenh = None
    c_cuoi = None                     # điểm điều khiển cuối (cho S / T)

    def so():
        nonlocal i
        v = float(tk[i])
        i += 1
        return v

    def ket(kin=False):
        nonlocal dang
        if len(dang) > 1:
            doan.append((dang, kin))
        dang = []

    while i < len(tk):
        if re.match(r"[A-Za-z]", tk[i]):
            lenh = tk[i]
            i += 1
            if lenh in "Zz":
                if dang:
                    dang.append((x0, y0))
                x, y = x0, y0
                ket(True)
                continue
        tuong = lenh.islower()
        L = lenh.upper()
        bx, by = (x, y) if tuong else (0.0, 0.0)
        if L == "M":
            ket()
            x, y = so() + bx, so() + by
            x0, y0 = x, y
            dang = [(x, y)]
            lenh = "l" if tuong else "L"          # cặp số tiếp theo là L
            c_cuoi = None
        elif L == "L":
            x, y = so() + bx, so() + by
            dang.append((x, y))
            c_cuoi = None
        elif L == "H":
            x = so() + bx
            dang.append((x, y))
            c_cuoi = None
        elif L == "V":
            y = so() + by
            dang.append((x, y))
            c_cuoi = None
        elif L in "CS":
            if L == "C":
                c1 = (so() + bx, so() + by)
            else:
                c1 = ((2 * x - c_cuoi[0], 2 * y - c_cuoi[1]) if c_cuoi else (x, y))
            c2 = (so() + bx, so() + by)
            p = (so() + bx, so() + by)
            dang.extend(_bezier((x, y), c1, c2, p))
            c_cuoi = c2
            x, y = p
        elif L in "QT":
            if L == "Q":
                q = (so() + bx, so() + by)
            else:
                q = ((2 * x - c_cuoi[0], 2 * y - c_cuoi[1]) if c_cuoi else (x, y))
            p = (so() + bx, so() + by)
            c1 = (x + 2 / 3 * (q[0] - x), y + 2 / 3 * (q[1] - y))
            c2 = (p[0] + 2 / 3 * (q[0] - p[0]), p[1] + 2 / 3 * (q[1] - p[1]))
            dang.extend(_bezier((x, y), c1, c2, p))
            c_cuoi = q
            x, y = p
        elif L == "A":
            rx, ry, phi = so(), so(), so()
            lon, chieu = int(so()), int(so())
            px, py = so() + bx, so() + by
            dang.extend(_cung(x, y, rx, ry, phi, lon, chieu, px, py))
            x, y = px, py
            c_cuoi = None
        else:                                           # lệnh lạ: bỏ qua số
            i += 1
    ket()
    return doan


def _hcn_path(x, y, w, h, r) -> str:
    r = max(0.0, min(r, w / 2, h / 2))
    return (f"M{x + r} {y}H{x + w - r}A{r} {r} 0 0 1 {x + w} {y + r}V{y + h - r}"
            f"A{r} {r} 0 0 1 {x + w - r} {y + h}H{x + r}A{r} {r} 0 0 1 {x} {y + h - r}"
            f"V{y + r}A{r} {r} 0 0 1 {x + r} {y}Z")


# ── Dựng ────────────────────────────────────────────────────────────────
def mat_na(ten: str, co_px: int, net: float | None = None):
    """Mặt nạ "L" (trắng = có nét) cỡ co_px × co_px, đã khử răng cưa."""
    from PIL import Image, ImageDraw
    n = max(4, int(co_px))
    W = n * SS
    k = W / 24.0
    im = Image.new("L", (W, W), 0)
    d = ImageDraw.Draw(im)
    #  nét: tối thiểu ~1,15 px thật — nhỏ hơn thì mờ nhoè ở icon 12–14 px
    bd = max((net or NET) * k, 1.15 * SS)

    def chuyen(pts):
        return [(px * k, py * k) for px, py in pts]

    def net_doan(pts, kin):
        pts = chuyen(pts)
        if len(pts) < 2:
            return
        d.line(pts, fill=255, width=max(1, round(bd)), joint="curve")
        if not kin:                                   # đầu nét tròn
            r = bd / 2
            for (px, py) in (pts[0], pts[-1]):
                d.ellipse((px - r, py - r, px + r, py + r), fill=255)

    for net_ve in BO[ten]:
        loai = net_ve[0]
        if loai in ("p", "pf"):
            for pts, kin in doc_path(net_ve[1]):
                if loai == "pf":
                    d.polygon(chuyen(pts), fill=255)
                net_doan(pts, kin)
        elif loai in ("o", "of"):
            _, cx, cy, r = net_ve
            cx, cy, r = cx * k, cy * k, r * k
            if loai == "of":
                d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
            else:
                d.ellipse((cx - r - bd / 2, cy - r - bd / 2, cx + r + bd / 2, cy + r + bd / 2),
                          outline=255, width=max(1, round(bd)))
        elif loai in ("r", "rf"):
            _, x, y, w, h, bo = net_ve
            for pts, kin in doc_path(_hcn_path(x, y, w, h, bo)):
                if loai == "rf":
                    d.polygon(chuyen(pts), fill=255)
                net_doan(pts, True)
    return im.resize((n, n), Image.LANCZOS)


def _rgb(mau: str, w=None) -> tuple:
    mau = str(mau)
    if mau.startswith("#") and len(mau) == 7:
        return tuple(int(mau[i:i + 2], 16) for i in (1, 3, 5))
    if w is not None:
        r, g, b = w.winfo_rgb(mau)
        return r // 257, g // 257, b // 257
    return (232, 233, 235)


def anh_pil(ten: str, co_px: int, mau: str, net: float | None = None, w=None):
    """Ảnh RGBA của biểu tượng (màu `mau`, nền trong suốt)."""
    from PIL import Image
    m = mat_na(ten, co_px, net)
    im = Image.new("RGBA", m.size, _rgb(mau, w) + (0,))
    im.putalpha(m)
    return im


def anh_bieu_tuong(w, ten: str, co_px: int, mau: str, net: float | None = None):
    """PhotoImage của biểu tượng — ĐỆM theo (tên, cỡ, màu, nét) trên cửa sổ gốc
    (Tk xoá ảnh khi mất tham chiếu Python; đệm giữ nó sống và khỏi dựng lại mỗi
    lần nút vẽ lại khi rê chuột)."""
    goc = w._root()
    kho = getattr(goc, "_bt_kho", None)
    if kho is None:
        kho = {}
        goc._bt_kho = kho
    khoa = (ten, int(co_px), str(mau), net)
    a = kho.get(khoa)
    if a is None:
        from PIL import ImageTk
        a = ImageTk.PhotoImage(anh_pil(ten, int(co_px), mau, net, w), master=goc)
        kho[khoa] = a
    return a


def bang_mau(duong_ra, co_ds=(14, 16, 20, 24, 48), nen="#22252a", mau="#e8e9eb"):
    """Ảnh xem trước cả bộ (để soát bằng mắt): mỗi hàng một biểu tượng, mỗi cột một cỡ."""
    from PIL import Image, ImageDraw
    ds = list(BO)
    o = max(co_ds) + 24
    W = 150 + o * len(co_ds)
    H = o * len(ds) + 20
    im = Image.new("RGB", (W, H), nen)
    d = ImageDraw.Draw(im)
    for r, ten in enumerate(ds):
        y = 10 + r * o
        d.text((10, y + o / 2 - 6), ten, fill="#a3a6ab")
        for c, n in enumerate(co_ds):
            a = anh_pil(ten, n, mau)
            x = 150 + c * o + (o - n) // 2
            im.paste(a, (x, y + (o - n) // 2), a)
    im.save(duong_ra)
    return duong_ra


if __name__ == "__main__":
    import sys
    print(bang_mau(sys.argv[1] if len(sys.argv) > 1 else "bieu_tuong_xem.png"))
