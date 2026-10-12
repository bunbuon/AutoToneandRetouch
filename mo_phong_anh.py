"""Mô phỏng thông số SẼ ÁP (Exposure + WB) lên ảnh xem trước — 13/10.

User 13/10: "Khi điều chỉnh thông số trên phần Bù sáng, Temp, Tint. Cần load lại
preview theo các thông số đã chỉnh". Trước đó lưới / bảng chi tiết / ảnh lớn
chỉ hiện ẢNH NHÚNG trong RAW (màu máy ảnh) — kéo Bù sáng chỉ đổi con số ΔEV
trên ô, ảnh đứng im.

CÁCH MÔ PHỎNG (gần đúng — không phải Lightroom render):
  · ảnh nhúng ≈ Lightroom ở Exposure 0 + WB As Shot của máy. Nên với ảnh nhúng
    đem áp CẢ thông số cuối: Exposure = new_exposure, WB từ WB máy
    (at.wb_may_adobe) sang (new_temp, new_tint) — "tuyet_doi".
  · ảnh preset Lightroom / ảnh duyệt đã mang thông số catalog lúc đó: chỉ áp
    PHẦN ĐỔI — ΔExposure = new − old, WB (old_temp, old_tint) → (new_temp,
    new_tint) — "tuong_doi".
  · WB: thích nghi Bradford giữa hai điểm trắng thang Lightroom (at.doi_wb, mô
    hình Adobe DNG SDK) dồn thành MỘT ma trận 3×3 trên RGB tuyến tính.
  · Exposure: nhân 2^EV trong miền "cảnh" — ảnh hiển thị đã có vai sáng (đỉnh
    không vượt 1), nên trước khi nhân phải gỡ vai (_vai_nguoc), nhân xong
    đặt vai lại (_vai). EV = 0 và không đổi WB → ảnh y nguyên từng điểm ảnh.
"""
from __future__ import annotations

import numpy as np

try:
    from PIL import Image
except Exception:                                            # noqa: BLE001
    Image = None

import autotone as at

#  sRGB 8 bit -> tuyến tính: bảng 256 ô (nhanh hơn tính lũy thừa từng điểm)
_LUT_LIN = at.srgb_to_linear(np.arange(256, dtype=np.float64) / 255.0).astype(np.float32)
#  tuyến tính -> sRGB 8 bit: bảng 4096 nấc
_N = 4096
_x = np.linspace(0.0, 1.0, _N)
_LUT_SRGB = (np.clip(np.where(_x <= 0.0031308, _x * 12.92,
                              1.055 * np.power(_x, 1 / 2.4) - 0.055), 0, 1) * 255 + 0.5
             ).astype(np.uint8)
del _x

#  vai sáng: tuyến tính dưới K, trên K tiệm cận 1 (cùng dạng so_sanh_ung_vien._vai)
_K = 0.75
_TRAN = 0.9995                       # điểm ảnh đã cháy hẳn: không gỡ vai tới vô cực


def _vai(x: np.ndarray) -> np.ndarray:
    m = x > _K
    if m.any():
        x = x.copy()
        x[m] = _K + (1 - _K) * (1 - np.exp(-(x[m] - _K) / (1 - _K)))
    return x


def _vai_nguoc(y: np.ndarray) -> np.ndarray:
    m = y > _K
    if m.any():
        y = y.copy()
        t = np.minimum(y[m], _TRAN)
        y[m] = _K - (1 - _K) * np.log(1 - (t - _K) / (1 - _K))
    return y


def ma_tran_wb(tu, sang) -> np.ndarray | None:
    """Ma trận 3×3 (RGB tuyến tính sRGB): ảnh render ở WB `tu` -> ở WB `sang`
    (thang Lightroom (K, tint)). None nếu thiếu số / không đổi."""
    try:
        t0, n0 = float(tu[0]), float(tu[1])
        t1, n1 = float(sang[0]), float(sang[1])
    except (TypeError, ValueError, IndexError):
        return None
    if t0 <= 0 or t1 <= 0 or (abs(t0 - t1) < 1 and abs(n0 - n1) < 0.1):
        return None
    k = at._non_trang(t0, n0) / at._non_trang(t1, n1)
    m = at._XYZ_SRGB @ at._BRADFORD_INV @ np.diag(k) @ at._BRADFORD @ at._SRGB_XYZ
    return m.astype(np.float32)


def ap(im, tham_so):
    """Ảnh PIL -> ảnh PIL đã mô phỏng. tham_so = (ev, wb) từ tham_so_anh();
    None -> trả nguyên ảnh."""
    if tham_so is None or Image is None or im is None:
        return im
    ev, wb = tham_so
    m = ma_tran_wb(*wb) if wb else None
    if abs(float(ev or 0.0)) < 0.005 and m is None:
        return im
    a = np.asarray(im.convert("RGB"))
    lin = _vai_nguoc(_LUT_LIN[a])
    if m is not None:
        lin = lin @ m.T
    if ev:
        lin = lin * np.float32(2.0 ** float(ev))
    lin = _vai(np.clip(lin, 0.0, None))
    idx = (np.clip(lin, 0.0, 1.0) * (_N - 1) + 0.5).astype(np.int32)
    return Image.fromarray(_LUT_SRGB[idx], "RGB")


def _so(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def tham_so_anh(r: dict, cfg: dict | None, kieu: str = "tuyet_doi"):
    """Thông số mô phỏng của MỘT ảnh sau plan: (ev, wb) — wb = ((K, tint) gốc,
    (K, tint) mới) hoặc None. None nếu ảnh không có gì để mô phỏng.

    kieu "tuyet_doi": nguồn là ảnh nhúng (màu máy) — áp Exposure cuối + WB máy
    -> WB cuối. "tuong_doi": nguồn đã mang thông số catalog (preset / duyệt) —
    chỉ áp phần đổi."""
    if not r or r.get("error") or r.get("loi"):
        return None
    moi_ev, cu_ev = _so(r.get("new_exposure")), _so(r.get("old_exposure"))
    if kieu == "tuyet_doi":
        ev = moi_ev if moi_ev is not None else (_so(r.get("delta_ev")) or 0.0)
    else:
        ev = (moi_ev - cu_ev) if (moi_ev is not None and cu_ev is not None) \
            else (_so(r.get("delta_ev")) or 0.0)
    wb = None
    t1, n1 = _so(r.get("new_temp")), _so(r.get("new_tint"))
    if not r.get("bw") and t1 and t1 > 0 and n1 is not None:
        tu = None
        if kieu == "tuyet_doi":
            try:
                tu = at.wb_may_adobe(r, cfg or at.DEFAULTS)
            except Exception:                                # noqa: BLE001
                tu = None
        if tu is None:
            t0, n0 = _so(r.get("old_temp")), _so(r.get("old_tint"))
            tu = (t0, n0 or 0.0) if t0 and t0 > 0 else None
        if tu is not None and (abs(tu[0] - t1) >= 1 or abs(tu[1] - n1) >= 0.1):
            wb = ((round(float(tu[0])), round(float(tu[1]), 1)),
                  (round(t1), round(n1, 1)))
    ev = round(float(ev), 2)
    if abs(ev) < 0.005 and wb is None:
        return None
    return (ev, wb)
