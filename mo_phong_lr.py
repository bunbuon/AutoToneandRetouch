# -*- coding: utf-8 -*-
"""mo_phong_lr.py — "Lightroom GIẢ" có hành vi BIẾT TRƯỚC, để kiểm mo_hinh_lr (14/10).

Không phải Lightroom: một đường dựng ảnh cùng KIỂU (WB nhân kênh trong không gian máy ->
ma trận máy -> Exposure -> Highlights / Shadows theo độ sáng -> đường tông -> curve điểm
-> HSL theo hue OkLab -> Color Grading theo vùng sáng) với hằng số cố định. Mô hình học
trên ảnh dựng của nó phải đoán lại được các biến thể / tổ hợp — đó là bài kiểm cho phần
khớp (mo_hinh_lr.khop / kiem_dinh), không phải bằng chứng mô hình đúng với Lightroom thật
(cái đó là HOC_MAU_LR + KIEM_MOT_LUOT trên máy user).
"""
from __future__ import annotations

import math

import numpy as np

import curve_lr as cl
import mo_hinh_lr as mh

MIEN_THAT, KIEU_THAT = "prophoto22", "kenh"
CAM = np.array([[0.92, 0.10, -0.02], [0.05, 0.90, 0.05], [-0.01, 0.12, 0.89]])
R_CG = np.array([[0.9, -0.3], [0.3, 0.9]])        # bánh xe -> ab OkLab (biết trước)


def _sig(x):
    return 1.0 / (1.0 + np.exp(-x))


def _wb_gain(K, t):
    m = 1e6 / K - 200.0                            # mired so với 5000 K
    return np.array([math.exp(-0.0042 * m), math.exp(-0.0006 * t), math.exp(0.0050 * m)])


def _tong(u):
    v = np.clip(u, 0.0, None)
    return mh.lin_srgb(np.clip(v / (v + 0.25) * 1.25, 0.0, 1.0))


#: đường tông của "Lightroom giả": "rgb_tone" (giữ sắc, như RefBaselineRGBTone của DNG
#: SDK mà Camera Raw dùng cho đường tông của profile) hoặc "kenh"
TONG_THAT = "rgb_tone"


def _T(u):
    """Đường tông (tuyến tính cảnh -> tuyến tính hiển thị 0..1), đơn điệu."""
    v = np.clip(u, 0.0, None)
    return np.clip(v / (v + 0.25) * 1.25, 0.0, 1.0)


def dung(scene, st: dict) -> np.ndarray:
    """Cảnh (RGB tuyến tính của máy, (N, 3)) + thông số -> ảnh dựng sRGB 0..1 (lượng tử 8 bit).

    Như Lightroom: WB + Exposure ở tuyến tính -> không gian làm việc ProPhoto tuyến tính
    -> HL / SH -> đường tông (TONG_THAT) -> mã hoá miền curve (MIEN_THAT) -> curve điểm
    -> sRGB -> HSL -> Color Grading."""
    w = mh.wb_cua(st) or (5000.0, 0.0)
    u = (np.asarray(scene, dtype=np.float64) * _wb_gain(*w)) @ CAM.T
    u = u * 2.0 ** mh._so(st.get("Exposure2012"))                  # noqa: SLF001
    Y = np.clip(u @ mh._Y, 1e-6, None)                             # noqa: SLF001
    lnY = np.log(Y)
    k = (mh._so(st.get("Highlights2012")) * 0.006 * _sig((lnY - math.log(0.3)) * 2.0)  # noqa: SLF001
         + mh._so(st.get("Shadows2012")) * 0.008 * _sig((math.log(0.04) - lnY) * 2.0))  # noqa: SLF001
    u = u * np.exp(k)[:, None]
    t = cl._rgb_tone(u, _T) if TONG_THAT == "rgb_tone" else _T(u)    # noqa: SLF001
    p = cl._trc_ma(np.clip(t, 0.0, 1.0), MIEN_THAT)                  # noqa: SLF001
    c = mh.curve_cua(st)
    bt = cl.bang(c["master"])
    q = cl._rgb_tone(p, lambda v: cl._ap_bang(v, bt)) if KIEU_THAT == "rgb_tone" \
        else cl._ap_bang(p, bt)                                      # noqa: SLF001
    out = np.empty_like(q)
    for i, kk in enumerate(cl.KENH):
        out[:, i] = cl._ap_bang(q[:, i], cl.bang(c[kk]))             # noqa: SLF001
    px = cl.mien_sang_srgb(np.clip(out, 0.0, 1.0), MIEN_THAT)
    lab = mh.lab_cua(px)
    C = np.hypot(lab[:, 1], lab[:, 2])
    h = np.degrees(np.arctan2(lab[:, 2], lab[:, 1]))
    gate = np.clip((C - 0.01) / 0.03, 0.0, 1.0)
    wo = np.exp(-((mh._goc(h - 60.0)) / 28.0) ** 2) * gate          # noqa: SLF001
    wr = np.exp(-((mh._goc(h - 25.0)) / 22.0) ** 2) * gate          # noqa: SLF001
    S = mh._so                                                       # noqa: SLF001
    dh = 0.40 * S(st.get("HueAdjustmentOrange")) * wo + 0.35 * S(st.get("HueAdjustmentRed")) * wr
    dlc = 0.011 * S(st.get("SaturationAdjustmentOrange")) * wo + 0.010 * S(st.get("SaturationAdjustmentRed")) * wr
    dL = 0.0015 * S(st.get("LuminanceAdjustmentOrange")) * wo
    C2 = C * np.exp(dlc)
    h2 = np.radians(h + dh)
    lab = np.stack([lab[:, 0] + dL, C2 * np.cos(h2), C2 * np.sin(h2)], axis=1)
    L = lab[:, 0]

    def v(kh, ks):
        H, s = S(st.get(kh)), S(st.get(ks))
        return np.array([math.cos(math.radians(H)), math.sin(math.radians(H))]) * s / 100.0
    zm = 0.06 * np.exp(-((L - 0.55) / 0.22) ** 2)
    zh = 0.05 * _sig((L - 0.72) / 0.07)
    zs = 0.05 * _sig((0.33 - L) / 0.07)
    dab = (zm[:, None] * (R_CG @ v(*mh.KHOA_CG_MID))[None, :]
           + zh[:, None] * (R_CG @ v(*mh.KHOA_CG_HI))[None, :]
           + zs[:, None] * (R_CG @ v(*mh.KHOA_CG_SH))[None, :])
    lab[:, 1:] += dab
    px = np.clip(mh.srgb_tu_lab(lab), 0.0, 1.0)
    return np.round(px * 255.0) / 255.0


def canh(seed: int, n_da=1500, n_trung=1500, n_khung=3000):
    """Một "cảnh": da (cam / hồng), xám trung tính, màu khung ngẫu nhiên. -> (scene, loai)."""
    rng = np.random.default_rng(seed)
    goc_da = np.array([0.30, 0.19, 0.14]) * rng.uniform(0.55, 1.1)       # da ~ L 0.65–0.85 sau dựng
    da = goc_da * rng.normal(1.0, 0.06, (n_da, 3))
    da[:, 0] *= rng.uniform(0.95, 1.08)
    xam = rng.uniform(0.02, 0.45, (n_trung, 1)) * np.array([1.0, 1.0, 1.0]) * rng.normal(1, 0.01, (n_trung, 3))
    khung = rng.uniform(0.005, 0.9, (n_khung, 3)) ** 1.6
    scene = np.vstack([da, xam, khung])
    loai = np.concatenate([np.zeros(n_da, np.int8), np.ones(n_trung, np.int8), np.full(n_khung, 2, np.int8)])
    return scene, loai


def bo_anh(n: int = 10, seed: int = 0) -> list:
    """n ảnh học giả: [{"mau": {"px": {biến thể: …}, "loai"}, "st": {biến thể: thông số}}]."""
    rng = np.random.default_rng(seed)
    out, ds = [], []
    curves = [None, "0,0,64,58,128,132,192,200,255,255", "0,0,90,80,170,178,255,250"]
    for i in range(n):
        cur = {"WhiteBalance": "As Shot" if i % 3 == 0 else "Custom",
               "AsShotTemperature": str(round(rng.uniform(3600, 6400))), "AsShotTint": str(round(rng.uniform(-6, 12))),
               "Exposure2012": f"{rng.uniform(-0.5, 0.6):.2f}", "Highlights2012": "0", "Shadows2012": "0",
               "HueAdjustmentOrange": str(int(rng.integers(-8, 4))), "SaturationAdjustmentOrange": "0",
               "ColorGradeMidtoneHue": "40", "ColorGradeMidtoneSat": str(int(rng.integers(0, 8)))}
        if cur["WhiteBalance"] == "Custom":
            cur["Temperature"], cur["Tint"] = str(round(rng.uniform(3600, 6400))), str(round(rng.uniform(-6, 12)))
        if curves[i % 3]:
            cur["ToneCurvePV2012"] = curves[i % 3]
        ds.append({"path": f"G:/Buoi/DSC{i:04d}.ARW", "cur": cur, "seed": seed * 100 + i})
    bien = mh.bien_the(ds)
    cham: set = set()
    for a in ds:
        scene, loai = canh(a["seed"])
        st, px = {}, {}
        for b in bien:
            s = mh.thong_so_bien(a["cur"], b, a["path"], cham)
            st[b["ten"]] = s
            px[b["ten"]] = dung(scene, s).astype(np.float32)
        px["sau"] = px["goc"]
        out.append({"mau": {"px": px, "loai": loai}, "st": st, "path": a["path"]})
    return out
