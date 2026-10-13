"""Toán Curve điểm của Lightroom (ToneCurvePV2012 + Red / Green / Blue) — 13/10.

User 13/10: "sau khi cân WB, Tone xong, đo lại da rồi can thiệp vào các kênh của Curve
cho da mặt đúng màu đích; WB + Tone xong mà vẫn cháy thì can thiệp Curve". Module này
CHỈ là toán thuần (numpy), không đọc ảnh, không biết gì về buổi: đổi màu sang miền
curve, tính spline như Lightroom, ghép một chỉnh sửa vào curve CÓ SẴN của preset, mô
phỏng ảnh sau khi đổi curve. Đo da / giải / gom loạt nằm ở curve_da.py.

#[[ VÌ SAO "GHÉP" chứ không ghi đè (13/10): preset SAY có curve riêng (tổng 138,132 +
#   nghiêng màu R/G/B — xem DEFAULTS "curve" trong autotone.py) tạo nên chất ảnh. Ghi
#   nguyên một curve mới là xoá chất đó. Nên mọi chỉnh sửa là một hàm ở MIỀN RA của
#   curve cũ: curve_mới = g ∘ curve_cũ. Hệ quả hay: ảnh Lightroom vừa dựng (đã qua
#   curve cũ) chỉ cần áp g lên giá trị của chính nó là ra ảnh sau khi đổi curve —
#   không phải đảo ngược curve cũ, không phải đoán điểm ảnh trước curve.
#
#   MIỀN CURVE (chưa đo trên Lightroom thật lúc viết): giả thuyết mặc định "melissa" =
#   gốc màu ProPhoto (D50) + đường TRC của sRGB — không gian Lightroom dùng cho số RGB
#   và histogram. Hai giả thuyết khác để V0 (kiem_curve_lr.py) chọn: ProPhoto γ2.2 và
#   ROMM γ1.8. Spline: bản chép dng_spline_solver của Adobe DNG SDK (C2, đạo hàm bậc
#   hai bằng 0 ở hai đầu) — Lightroom vẽ curve điểm bằng chính bộ giải này trong SDK
#   công khai; V0 xác nhận. Curve tổng: "kenh" (áp riêng từng kênh) hay "rgb_tone"
#   (giữ sắc như RefBaselineRGBTone của DNG SDK) — cũng để V0 chọn. ]]
"""
from __future__ import annotations

import math

import numpy as np

#: Khoá Lightroom của bốn curve điểm, theo thứ tự tool ghi. "ten" (ToneCurveName2012)
#: phải là "Custom" khi curve không còn là curve dựng sẵn của Adobe.
KHOA = {"master": "ToneCurvePV2012", "r": "ToneCurvePV2012Red",
        "g": "ToneCurvePV2012Green", "b": "ToneCurvePV2012Blue"}
KHOA_TEN = "ToneCurveName2012"
KENH = ("r", "g", "b")
DONG_NHAT = ((0.0, 0.0), (255.0, 255.0))

#: Số điểm tối đa của một curve tool ghi — bảo thủ (V0 kiểm Lightroom giữ được bao nhiêu).
DIEM_TOI_DA = 16

MIEN = ("melissa", "prophoto22", "prophoto18")
KIEU_TONG = ("kenh", "rgb_tone")

# ------------------------------------------------------------------- màu

#  sRGB tuyến tính -> XYZ D65 (IEC 61966-2-1)
_SRGB_XYZ = np.array([[0.4124564, 0.3575761, 0.1804375],
                      [0.2126729, 0.7151522, 0.0721750],
                      [0.0193339, 0.1191920, 0.9503041]])
#  Bradford D65 -> D50
_BRAD = np.array([[0.8951, 0.2664, -0.1614], [-0.7502, 1.7135, 0.0367], [0.0389, -0.0685, 1.0296]])
_D65 = np.array([0.95047, 1.0, 1.08883])
_D50 = np.array([0.96422, 1.0, 0.82521])
_PP_XYZ = np.array([[0.7976749, 0.1351917, 0.0313534],     # ProPhoto (ROMM) tuyến tính -> XYZ D50
                    [0.2880402, 0.7118741, 0.0000857],
                    [0.0, 0.0, 0.8252100]])


def _thich_nghi(den, di):
    a, b = _BRAD @ den, _BRAD @ di
    return np.linalg.inv(_BRAD) @ np.diag(b / a) @ _BRAD


#: sRGB tuyến tính -> ProPhoto tuyến tính (và ngược lại)
SRGB_SANG_PP = np.linalg.inv(_PP_XYZ) @ _thich_nghi(_D65, _D50) @ _SRGB_XYZ
PP_SANG_SRGB = np.linalg.inv(SRGB_SANG_PP)


def srgb_tuyen_tinh(v):
    v = np.asarray(v, dtype=np.float64)
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def tuyen_tinh_srgb(v):
    v = np.clip(np.asarray(v, dtype=np.float64), 0.0, None)
    return np.where(v <= 0.0031308, v * 12.92, 1.055 * np.power(v, 1 / 2.4) - 0.055)


def _trc_ma(lin, mien):
    """Tuyến tính -> giá trị đã mã hoá của miền curve (0..1)."""
    lin = np.clip(lin, 0.0, None)
    if mien == "melissa":
        return tuyen_tinh_srgb(lin)
    if mien == "prophoto22":
        return np.power(lin, 1 / 2.2)
    if mien == "prophoto18":                                  # ROMM: đoạn thẳng 1/512
        return np.where(lin < 1 / 512, lin * 16.0, np.power(lin, 1 / 1.8))
    raise ValueError(f"miền curve lạ: {mien}")


def _trc_giai(v, mien):
    v = np.clip(np.asarray(v, dtype=np.float64), 0.0, None)
    if mien == "melissa":
        return srgb_tuyen_tinh(v)
    if mien == "prophoto22":
        return np.power(v, 2.2)
    if mien == "prophoto18":
        return np.where(v < 16 / 512, v / 16.0, np.power(v, 1.8))
    raise ValueError(f"miền curve lạ: {mien}")


def srgb_sang_mien(px, mien="melissa"):
    """sRGB 0..1 (..., 3) -> giá trị kênh trong miền curve 0..1."""
    px = np.asarray(px, dtype=np.float64)
    lin = srgb_tuyen_tinh(px) @ SRGB_SANG_PP.T
    return np.clip(_trc_ma(lin, mien), 0.0, 1.0)


def tuyen_tinh_sang_mien(lin_srgb, mien="melissa"):
    """sRGB TUYẾN TÍNH (..., 3) -> miền curve 0..1."""
    lin = np.asarray(lin_srgb, dtype=np.float64) @ SRGB_SANG_PP.T
    return np.clip(_trc_ma(lin, mien), 0.0, 1.0)


def mien_sang_tuyen_tinh(v, mien="melissa"):
    """Miền curve 0..1 -> sRGB TUYẾN TÍNH (không cắt gam — để lấy trung bình màu)."""
    return np.clip(_trc_giai(v, mien) @ PP_SANG_SRGB.T, 0.0, None)


def mien_sang_srgb(v, mien="melissa"):
    """Miền curve 0..1 -> sRGB 0..1 (cắt gam ở 0..1 như ảnh JPEG Lightroom xuất)."""
    lin = _trc_giai(v, mien) @ PP_SANG_SRGB.T
    return np.clip(tuyen_tinh_srgb(np.clip(lin, 0.0, 1.0)), 0.0, 1.0)


# ------------------------------------------------------------------- spline

def _he_so_doc(X, Y):
    """Độ dốc tại các nút — chép dng_spline_solver::Solve (Adobe DNG SDK)."""
    n = len(X)
    S = np.zeros(n)
    A = X[1] - X[0]
    B = (Y[1] - Y[0]) / A
    S[0] = B
    for j in range(2, n):
        C = X[j] - X[j - 1]
        D = (Y[j] - Y[j - 1]) / C
        S[j - 1] = (B * C + D * A) / (A + C)
        A, B = C, D
    S[n - 1] = 2.0 * B - S[n - 2]
    S[0] = 2.0 * S[0] - S[1]
    if n > 2:
        E, F, G = np.zeros(n), np.zeros(n), np.zeros(n)
        F[0] = 0.5
        E[n - 1] = 0.5
        G[0] = 0.75 * (S[0] + S[1])
        G[n - 1] = 0.75 * (S[n - 2] + S[n - 1])
        for j in range(1, n - 1):
            A = (X[j + 1] - X[j - 1]) * 2.0
            E[j] = (X[j + 1] - X[j]) / A
            F[j] = (X[j] - X[j - 1]) / A
            G[j] = 1.5 * S[j]
        for j in range(1, n):
            A = 1.0 - F[j - 1] * E[j]
            if j != n - 1:
                F[j] /= A
            G[j] = (G[j] - G[j - 1] * E[j]) / A
        for j in range(n - 2, -1, -1):
            G[j] = G[j] - F[j] * G[j + 1]
        S = G
    return S


def spline(diem):
    """Hàm f(x) (x, f trên thang 0..255, nhận mảng) vẽ đúng như curve điểm Lightroom.
    Ngoài hai nút đầu / cuối: giữ y của nút đó (dng_spline_solver::Evaluate)."""
    d = chuan(diem)
    X = np.array([p[0] for p in d], dtype=np.float64)
    Y = np.array([p[1] for p in d], dtype=np.float64)
    S = _he_so_doc(X, Y)

    def f(x):
        x = np.asarray(x, dtype=np.float64)
        j = np.clip(np.searchsorted(X, x, side="left"), 1, len(X) - 1)
        x0, x1, y0, y1, s0, s1 = X[j - 1], X[j], Y[j - 1], Y[j], S[j - 1], S[j]
        A = x1 - x0
        Bb = (x - x0) / A
        Cc = (x1 - x) / A
        D = ((y0 * (2.0 - Cc + Bb) + (s0 * A * Bb)) * (Cc * Cc)
             + (y1 * (2.0 - Bb + Cc) - (s1 * A * Cc)) * (Bb * Bb))
        return np.where(x <= X[0], Y[0], np.where(x >= X[-1], Y[-1], D))
    return f


def chuan(diem) -> list:
    """Danh sách điểm (x, y) hợp lệ, x tăng ngặt; rỗng / hỏng -> curve đồng nhất."""
    try:
        d = [(float(x), float(y)) for x, y in diem]
    except (TypeError, ValueError):
        return list(DONG_NHAT)
    d = sorted(d)
    ok = (len(d) >= 2 and all(0 <= x <= 255 and 0 <= y <= 255 for x, y in d)
          and all(d[i + 1][0] > d[i][0] for i in range(len(d) - 1)))
    return d if ok else list(DONG_NHAT)


def doc_o(o) -> list | None:
    """Ô "x1,y1,x2,y2,…" (job / bản xuất / mốc) -> [(x, y), …]. Trống / hỏng -> None."""
    if o is None:
        return None
    if isinstance(o, (list, tuple)):
        so = [float(v) for v in o]
    else:
        s = str(o).strip().strip("{}[]")
        if not s:
            return None
        try:
            so = [float(v) for v in s.replace(";", ",").split(",") if v.strip()]
        except ValueError:
            return None
    if len(so) < 4 or len(so) % 2:
        return None
    d = list(zip(so[0::2], so[1::2]))
    #  x phải TĂNG NGẶT theo đúng thứ tự trong ô (Lightroom lưu đã sắp) — ô lộn thứ tự là
    #  ô hỏng, đừng tự sắp lại rồi ghi một curve khác hẳn
    if (any(d[i + 1][0] <= d[i][0] for i in range(len(d) - 1))
            or not all(0 <= x <= 255 and 0 <= y <= 255 for x, y in d)):
        return None
    return d


def ghi_o(diem) -> str:
    """[(x, y), …] -> "x1,y1,…" — số nguyên khi tròn (Lightroom lưu 0..255)."""
    out = []
    for x, y in diem:
        for v in (x, y):
            out.append(str(int(round(v))) if abs(v - round(v)) < 1e-6 else f"{v:.2f}")
    return ",".join(out)


def la_dong_nhat(diem) -> bool:
    f = spline(diem)
    x = np.arange(256.0)
    return bool(np.max(np.abs(f(x) - x)) < 0.5)


def bang(diem, n: int = 4096) -> np.ndarray:
    """Bảng tra miền 0..1 -> 0..1 (n nấc) của một curve điểm."""
    x = np.linspace(0.0, 255.0, n)
    return np.clip(spline(diem)(x) / 255.0, 0.0, 1.0)


# ------------------------------------------------------------------- ghép

def ghep(g, cu, them_x=(), toi_da: int = DIEM_TOI_DA, sai: float = 1.0) -> list:
    """Curve mới = g ∘ curve cũ, vẽ lại thành danh sách điểm.

    g: hàm trên MIỀN RA của curve cũ (0..255 -> 0..255, nhận mảng), đơn điệu.
    them_x: nút nên có (mép dải đổi) — x trên miền VÀO.
    Nút = nút cũ ∪ them_x ∪ {0, 255}; y làm tròn số nguyên như Lightroom lưu; thêm nút
    ở chỗ lệch nhiều nhất tới khi lệch ≤ `sai` mã (hoặc đủ `toi_da` điểm).
    ValueError khi kết quả không đơn điệu."""
    cu = chuan(cu)
    f_cu = spline(cu)
    luoi = np.linspace(0.0, 255.0, 1021)
    dich = np.clip(g(f_cu(luoi)), 0.0, 255.0)
    nut = {0.0, 255.0} | {float(round(x)) for x, _ in cu}
    nut |= {float(round(x)) for x in them_x if 0 < x < 255}

    def dung(ns):
        xs = sorted(ns)
        return [(x, float(round(float(np.clip(g(f_cu(np.array([x])))[0], 0, 255))))) for x in xs]

    diem = dung(nut)
    while True:
        lech = np.abs(spline(diem)(luoi) - dich)
        if float(lech.max()) <= sai or len(diem) >= toi_da:
            break
        #  nút mới ở chỗ lệch nhất, không trùng nút cũ
        for i in np.argsort(-lech):
            x = float(round(luoi[i]))
            if x not in nut:
                nut.add(x)
                break
        else:
            break
        diem = dung(nut)
    diem = _tinh_chinh(diem, luoi, dich)
    dau = spline(diem)(luoi)
    if np.any(np.diff(dau) < -1e-6):
        raise ValueError("curve ghép không đơn điệu")
    return diem


def _tinh_chinh(diem, luoi, dich, vong: int = 3):
    """Nút y làm tròn số nguyên thì curve lệch g∘cũ CÙNG MỘT CHIỀU cả dải (đo 13/10: kênh
    G +0.64 mã trung bình -> da trôi ~0.9° hue so với dự đoán). Thử y ± 1 từng nút (trừ hai
    đầu), giữ thay đổi nào làm tổng bình phương lệch nhỏ đi."""
    d = [list(p) for p in diem]

    def sai(dd):
        return float(np.sum((spline(dd)(luoi) - dich) ** 2))
    tot = sai(d)
    for _ in range(vong):
        doi = False
        for i in range(1, len(d) - 1):
            for buoc in (-1.0, 1.0):
                y = d[i][1] + buoc
                if not 0 <= y <= 255:
                    continue
                thu = [p[:] for p in d]
                thu[i][1] = y
                s = sai(thu)
                if s < tot - 1e-9:
                    d, tot, doi = thu, s, True
        if not doi:
            break
    return [(float(x), float(y)) for x, y in d]


def lech_toi_da(a, b) -> float:
    """Chênh lớn nhất (mã 0..255) giữa hai curve điểm."""
    x = np.linspace(0.0, 255.0, 1021)
    return float(np.max(np.abs(spline(a)(x) - spline(b)(x))))


# ------------------------------------------------------------------- hàm chỉnh

def bump(a: float, b: float, chan: float, lo: float, hi: float):
    """Trọng số w(y) trên miền 0..1: = 1 trên [a, b], chân nửa-cosin rộng `chan` hai
    bên, = 0 ngoài [lo, hi] — dải co lại để cả chân nằm TRONG [lo, hi] (cắt ngang chân
    là curve gãy bậc). Trả hàm nhận mảng."""
    a, b = max(a, lo + chan), min(b, hi - chan)
    if a > b:
        a = b = min(max((a + b) / 2, lo + chan), hi - chan)

    def w(y):
        y = np.asarray(y, dtype=np.float64)
        out = np.zeros_like(y)
        trong = (y >= a) & (y <= b)
        out[trong] = 1.0
        if chan > 0:
            t = (y >= a - chan) & (y < a)
            out[t] = 0.5 * (1 - np.cos(math.pi * (y[t] - (a - chan)) / chan))
            t = (y > b) & (y <= b + chan)
            out[t] = 0.5 * (1 + np.cos(math.pi * (y[t] - b) / chan))
        out[(y < lo) | (y > hi)] = 0.0
        return out
    return w


def g_da(delta: float, w):
    """Chỉnh da ở miền ra 0..255: g(y) = y + Δ·w(y) (Δ trên thang 0..1)."""
    def g(y):
        y = np.asarray(y, dtype=np.float64)
        return y + 255.0 * delta * w(y / 255.0)
    return g


def h_chay(k: float, d: float):
    """Nén đỉnh (miền 0..255): đồng nhất dưới knee k (0..1), trên đó
    h(x) = x − d·((x − k)/(1 − k))², d tính bằng mã — đỉnh 255 xuống 255 − d."""
    def h(x):
        x = np.asarray(x, dtype=np.float64)
        t = np.clip((x / 255.0 - k) / (1.0 - k), 0.0, None)
        return x - d * t * t
    return h


# ------------------------------------------------------------------- mô phỏng

def _ap_bang(v, b):
    return np.interp(v, np.linspace(0.0, 1.0, len(b)), b)


def _nguoc_bang(v, b):
    """Đảo một bảng tra đơn điệu không giảm."""
    x = np.linspace(0.0, 1.0, len(b))
    bb = np.maximum.accumulate(b)
    return np.interp(v, bb, x)


def _rgb_tone(p, f):
    """Áp hàm f lên ba kênh mà giữ sắc (RefBaselineRGBTone của DNG SDK): kênh lớn /
    nhỏ nhất qua f, kênh giữa nội suy theo tỉ lệ cũ."""
    mx, mn = p.max(axis=-1, keepdims=True), p.min(axis=-1, keepdims=True)
    fmx, fmn = f(mx), f(mn)
    ti = np.where(mx > mn, (p - mn) / np.where(mx > mn, mx - mn, 1.0), 0.0)
    return fmn + (fmx - fmn) * ti


def ap_mien(w, cu: dict, moi: dict, kieu_tong: str = "kenh"):
    """Giá trị miền curve của ảnh ĐÃ dựng với curve `cu` (sau cả bốn curve, 0..1, (..., 3))
    -> giá trị khi dựng lại với curve `moi`. `cu` / `moi`: {"master"|"r"|"g"|"b": điểm}
    (thiếu = đồng nhất). Giả định `moi["master"]` = h ∘ `cu["master"]` và
    `moi[c]` = g_c ∘ `cu[c]` (đúng cách tool ghép) — khi đó chỉ cần h và g_c:
        p = cu_c⁻¹(w)  (ra của curve tổng cũ),  w' = g_c(cu_c(h(p)))."""
    w = np.asarray(w, dtype=np.float64)
    out = np.empty_like(w)
    p = np.empty_like(w)
    b_cu = {c: bang(cu.get(c) or DONG_NHAT) for c in KENH}
    for i, c in enumerate(KENH):
        p[..., i] = _nguoc_bang(w[..., i], b_cu[c])
    #  h = curve tổng mới ∘ (curve tổng cũ)⁻¹ trên miền ra của curve tổng cũ
    bt_cu, bt_moi = bang(cu.get("master") or DONG_NHAT), bang(moi.get("master") or DONG_NHAT)
    if np.max(np.abs(bt_cu - bt_moi)) > 1e-9:
        def h(v):
            return _ap_bang(_nguoc_bang(v, bt_cu), bt_moi)
        q = _rgb_tone(p, h) if kieu_tong == "rgb_tone" else h(p)
    else:
        q = p
    for i, c in enumerate(KENH):
        out[..., i] = _ap_bang(q[..., i], bang(moi.get(c) or DONG_NHAT))
    return np.clip(out, 0.0, 1.0)


def ap_anh(px_srgb, cu: dict, moi: dict, mien: str = "melissa", kieu_tong: str = "kenh"):
    """Ảnh sRGB 0..1 Lightroom đã dựng với curve `cu` -> ảnh dự đoán với curve `moi`."""
    w = srgb_sang_mien(px_srgb, mien)
    return mien_sang_srgb(ap_mien(w, cu, moi, kieu_tong), mien)


def ap_curve_tu_dau(px_srgb, curves: dict, mien: str = "melissa", kieu_tong: str = "kenh"):
    """Áp nguyên bộ curve lên ảnh CHƯA qua curve (cho bài kiểm / ảnh thử V0)."""
    w = srgb_sang_mien(px_srgb, mien)
    bt = bang(curves.get("master") or DONG_NHAT)
    p = _rgb_tone(w, lambda v: _ap_bang(v, bt)) if kieu_tong == "rgb_tone" else _ap_bang(w, bt)
    out = np.empty_like(p)
    for i, c in enumerate(KENH):
        out[..., i] = _ap_bang(p[..., i], bang(curves.get(c) or DONG_NHAT))
    return mien_sang_srgb(out, mien)
