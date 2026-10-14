# -*- coding: utf-8 -*-
"""mo_hinh_lr.py — MÔ HÌNH MÀU LIGHTROOM học trên ảnh RAW thật của người dùng (14/10).

User 14/10: "Với mỗi 1 ảnh cần lấy ra được vùng da mặt và pixel vùng da đó để can thiệp
xử lý ánh sáng và màu sắc cho giống với màu da đích. Cần học về hệ màu và cách bù trừ
màu sắc trong Curve, CG… Quy trình chỉnh Tone -> Color Mixer HSL -> Tone Curve -> WB -> CG".
Chốt: chuỗi màu da MỘT LƯỢT — đo da trên preview Lightroom của trạng thái hiện tại, dự
đoán ảnh Lightroom dựng sau khi đổi thông số bằng mô hình này, áp MỘT lần.

HỌC (HOC_MAU_LR.bat -> hoc_mau_lr.py): ~20 ảnh có mặt, plugin (HocMauCore.lua) áp TẠM
từng biến thể (bien_the) rồi dựng; ảnh dựng thẳng hàng từng điểm nên mỗi cặp (nen ->
biến thể) cho đúng Lightroom đổi MỖI điểm ảnh thế nào. Mô hình (MoHinh) — trên ảnh đã
dựng, sRGB:

  1. Đường đáp ứng hiệu dụng g (mỗi kênh, ln u = g(z)) — Debevec–Malik trên cặp
     Exposure ±0.7: g(z+) − g(z0) = 0.7·ln2. Exposure / WB / HL-SH tác động ở "u".
  2. WB: u' = M(Δmired, Δtint)·u, M ≈ I + A1·Δm + A2·Δm² (cùng kiểu cho tint), khớp
     3×3 trên mọi điểm không cháy.
  3. Highlights / Shadows: ln gain theo ln Y (16 ngăn) × thanh trượt — gần đúng (Lightroom
     làm cục bộ).
  4. Curve điểm: chọn giả thuyết miền × kiểu curve tổng của curve_lr có sai số ap_mien
     nhỏ nhất trên các biến thể curve — lần đầu curve_lr được hiệu chỉnh trên ảnh thật.
  5. HSL (Cam / Đỏ): Δhue, Δln chroma, ΔL trong OkLab theo hue (24 ngăn) × chroma (3
     ngăn), a·s + b·s² — thay hằng số hsl_da_k_hue / k_sat.
  6. Color Grading: Δab OkLab = M_vùng(L)·Δv (v = sat/100·(cos H, sin H) của bánh xe);
     midtone khớp 2×2 mỗi ngăn L từ ba hue; highlight / shadow = trọng số vùng × hướng
     midtone.
  7. Thứ tự curve / HSL trong Lightroom: chọn bằng hai tổ hợp trộn dấu (không dùng khi học).

KIỂM ĐỊNH: để lại một ảnh, học trên phần còn lại, đoán ảnh đó (mọi biến thể + tổ hợp) —
màu da trung bình (hue, độ đậm, L) và vùng trung tính (ab). Đạt khi tổ hợp lệch trung vị
≤ 2.0° / 8% / 0.02 L và trung tính ≤ 0.003 — kém hơn thì app KHÔNG dùng mô hình (đường
cũ chạy như trước).

#[[ 14/10 — NGƯỠNG THEO VÙNG ỔN CỦA APP, không theo phòng thí nghiệm. Ba máy thật của buổi
#   2709 (Z 8, Z5_2, A7M4) đều lệch tổ hợp 1.5–2.0° trung vị với ngưỡng cũ 1.0°: phần lớn do
#   HSL Cam của ảnh khác nhau (Sat −13 … −45 — Lightroom áp WB / Exposure TRƯỚC HSL nên ảnh
#   HSL mạnh phản ứng khác). Vùng ổn của da là ±3° / ±10% (da_on_hue / da_on_chroma): dự
#   đoán lệch ≤ 2° vẫn đặt da trong vùng ổn; tấm lệch hơn thì soát sau khi áp bắt và chạy
#   lượt 2 riêng tấm đó. ]]
"""
from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime
from pathlib import Path

import numpy as np

import autotone as at
import curve_lr as cl

PHIEN_BAN = 1
TEN_YEU_CAU = "request_hocmau.txt"
TEN_TIEN_DO = "hocmau_tiendo.txt"
TEN_BANG = "hocmau_anh.tsv"
TEN_CO_DUNG = "request_hocmau_dung.txt"
KHA_NANG = "hocmau1"

#: biên độ biến thể khi học
EV, HL, SH, MIRED, TINT, HSL_S, CV_MA, CG_SAT = 0.7, -40.0, 40.0, 25.0, 15.0, 30.0, 12.0, 25.0
#: ngưỡng ĐẠT của kiểm định (tổ hợp, ảnh để lại) — xem chú thích đầu file (14/10)
DAT = {"hue": 2.0, "q": 0.08, "L": 0.02, "ab": 0.003}
#: hue OkLab của điểm DA hợp lệ (độ, vòng qua 0): mặt nạ trên ảnh dựng cạnh 1024 có lúc lấy
#: nhầm lá cây / nền (hue 107°, 127° ở mẫu Z 8 thật) — kéo lệch cả học lẫn kiểm định
DA_HUE = (-15.0, 85.0)

LUOI = 128                               # nút của đường đáp ứng g
NGAN_HUE, NGAN_C = 24, (0.01, 0.04, 0.08)
NGAN_L = 8
SO_DA, SO_TRUNG, SO_KHUNG = 3000, 3000, 6000

KHOA_HSL = ("HueAdjustmentOrange", "SaturationAdjustmentOrange", "LuminanceAdjustmentOrange",
            "HueAdjustmentRed", "SaturationAdjustmentRed")
KHOA_CG_MID = ("ColorGradeMidtoneHue", "ColorGradeMidtoneSat")
KHOA_CG_HI = ("SplitToningHighlightHue", "SplitToningHighlightSaturation")
KHOA_CG_SH = ("SplitToningShadowHue", "SplitToningShadowSaturation")

_M1 = np.asarray(at._OK_M1, dtype=np.float64)                  # noqa: SLF001
_M2 = np.asarray(at._OK_M2, dtype=np.float64)                  # noqa: SLF001
_M1I, _M2I = np.linalg.inv(_M1), np.linalg.inv(_M2)
_Y = np.array([0.2126, 0.7152, 0.0722])


# ===================================================================== màu
def srgb_lin(px):
    return at.srgb_to_linear(np.clip(np.asarray(px, dtype=np.float64), 0.0, 1.0))


def lin_srgb(v):
    v = np.clip(np.asarray(v, dtype=np.float64), 0.0, 1.0)
    return np.where(v <= 0.0031308, v * 12.92, 1.055 * np.power(v, 1.0 / 2.4) - 0.055)


def lab_cua(px_srgb):
    """sRGB 0..1 (N, 3) -> OkLab (N, 3)."""
    return np.cbrt(np.maximum(srgb_lin(px_srgb) @ _M1.T, 0.0)) @ _M2.T


def srgb_tu_lab(lab):
    lms = np.asarray(lab, dtype=np.float64) @ _M2I.T
    return lin_srgb(np.maximum(lms, 0.0) ** 3 @ _M1I.T)


def thong_ke_da(px_srgb) -> tuple[float, float, float]:
    """(L, hue °, q = chroma / L) OkLab của TRUNG BÌNH TUYẾN TÍNH các điểm (như curve_da)."""
    lin = srgb_lin(px_srgb).mean(axis=0)
    L, a, b = at.oklab(lin)
    return float(L), float(math.degrees(math.atan2(b, a))), float(math.hypot(a, b) / max(L, 1e-6))


def _goc(d):
    return (np.asarray(d) + 180.0) % 360.0 - 180.0


def _so(v, mac=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(mac)


# ===================================================================== thông số
def wb_cua(st: dict) -> tuple[float, float] | None:
    """(Kelvin, tint) Lightroom đang dựng: WB Custom -> Temperature / Tint; nhãn khác
    (As Shot…) -> AsShotTemperature / AsShotTint của bản xuất."""
    st = st or {}
    nhan = str(st.get("WhiteBalance") or "")
    if nhan == "Custom" or (not nhan and st.get("Temperature") not in (None, "")):
        k, t = st.get("Temperature"), st.get("Tint")
    else:
        k, t = st.get("AsShotTemperature"), st.get("AsShotTint")
    try:
        return float(k), float(t)
    except (TypeError, ValueError):
        return None


def mired_doi(K: float, dm: float) -> float:
    """Kelvin sau khi đổi dm mired (dm < 0 -> Kelvin cao hơn -> ảnh ấm hơn)."""
    return 1e6 / (1e6 / float(K) + float(dm))


def curve_cua(st: dict) -> dict:
    """{"master"|"r"|"g"|"b": điểm} từ thông số (ô "x,y,…" của bản xuất hoặc mảng)."""
    return {c: (cl.doc_o((st or {}).get(k)) or list(cl.DONG_NHAT)) for c, k in cl.KHOA.items()}


def _phang(diem) -> list:
    return [float(v) for p in diem for v in p]


def _bump_kenh(cu, ma: float):
    w = cl.bump(0.50, 0.80, 0.10, 0.06, 0.96)
    return cl.ghep(cl.g_da(ma / 255.0, w), cu)


def _s_tong(cu, bien_do: float = 8.0):
    return cl.ghep(lambda y: np.asarray(y, dtype=np.float64)
                   + bien_do * np.sin(2.0 * np.pi * np.asarray(y, dtype=np.float64) / 255.0), cu)


def bien_the(ds: list) -> list:
    """Danh sách biến thể gửi HocMauCore. ds: [{"path", "cur": dòng bản xuất}] — chỉ ảnh có
    WB đọc được (wb_cua). Mỗi biến thể: {"ten", "goc"?, "doi"?, "dat"?, "dat_anh"?}."""
    def theo_anh(fn):
        out = {}
        for a in ds:
            v = fn(a)
            if v:
                out[a["path"]] = v
        return out

    def wb(a, dm=0.0, dt=0.0):
        K, t = wb_cua(a["cur"])
        return {"Temperature": round(mired_doi(K, dm)), "Tint": round(t + dt)}

    def cv(a, kenh, ma):
        cu = curve_cua(a["cur"])
        moi = _bump_kenh(cu[kenh], ma) if kenh != "master" else _s_tong(cu["master"])
        return {cl.KHOA[kenh]: _phang(moi)}

    b = [{"ten": "goc", "goc": True}, {"ten": "nen"},
         {"ten": "ev+", "doi": {"Exposure2012": EV}}, {"ten": "ev-", "doi": {"Exposure2012": -EV}},
         {"ten": "hl-", "doi": {"Highlights2012": HL}}, {"ten": "sh+", "doi": {"Shadows2012": SH}},
         {"ten": "k+", "dat_anh": theo_anh(lambda a: wb(a, dm=-MIRED))},
         {"ten": "k-", "dat_anh": theo_anh(lambda a: wb(a, dm=MIRED))},
         {"ten": "t+", "dat_anh": theo_anh(lambda a: wb(a, dt=TINT))},
         {"ten": "t-", "dat_anh": theo_anh(lambda a: wb(a, dt=-TINT))}]
    for ten, k in (("o_hue", "HueAdjustmentOrange"), ("o_sat", "SaturationAdjustmentOrange")):
        b += [{"ten": ten + "+", "doi": {k: HSL_S}}, {"ten": ten + "-", "doi": {k: -HSL_S}}]
    b += [{"ten": "o_lum+", "doi": {"LuminanceAdjustmentOrange": HSL_S}},
          {"ten": "r_hue+", "doi": {"HueAdjustmentRed": HSL_S}},
          {"ten": "r_sat+", "doi": {"SaturationAdjustmentRed": HSL_S}}]
    for kenh in ("r", "g", "b"):
        b.append({"ten": "cv_" + kenh, "dat": {cl.KHOA_TEN: "Custom"},
                  "dat_anh": theo_anh(lambda a, k=kenh: cv(a, k, CV_MA))})
    b.append({"ten": "cv_s", "dat": {cl.KHOA_TEN: "Custom"},
              "dat_anh": theo_anh(lambda a: cv(a, "master", 0))})
    for H in (30, 150, 270):
        b.append({"ten": f"cg_m{H}", "dat": {"ColorGradeMidtoneHue": H, "ColorGradeMidtoneSat": CG_SAT}})
    b.append({"ten": "cg_h", "dat": {"SplitToningHighlightHue": 60,
                                     "SplitToningHighlightSaturation": CG_SAT}})
    b.append({"ten": "cg_s", "dat": {"SplitToningShadowHue": 240,
                                     "SplitToningShadowSaturation": CG_SAT}})
    #  hai tổ hợp trộn dấu — KHÔNG dùng khi học, chỉ để kiểm định + chọn thứ tự
    b.append({"ten": "tohop1", "doi": {"Exposure2012": 0.3, "HueAdjustmentOrange": 15.0,
                                       "SaturationAdjustmentOrange": -15.0},
              "dat": {cl.KHOA_TEN: "Custom", "ColorGradeMidtoneHue": 40, "ColorGradeMidtoneSat": 12},
              "dat_anh": theo_anh(lambda a: dict(wb(a, dm=-12.0, dt=6.0), **cv(a, "r", 6.0)))})
    b.append({"ten": "tohop2", "doi": {"Exposure2012": -0.3, "HueAdjustmentOrange": -15.0,
                                       "SaturationAdjustmentOrange": 15.0, "Shadows2012": 20.0},
              "dat": {cl.KHOA_TEN: "Custom", "SplitToningHighlightHue": 200,
                      "SplitToningHighlightSaturation": 10},
              "dat_anh": theo_anh(lambda a: dict(wb(a, dm=12.0, dt=-6.0), **cv(a, "b", 6.0)))})
    return b


def nen_cua(cur: dict) -> dict | None:
    """WB Custom ở đúng Kelvin / tint Lightroom đang dựng (biến thể "nen")."""
    w = wb_cua(cur)
    if w is None:
        return None
    return {"WhiteBalance": "Custom", "Temperature": round(w[0]), "Tint": round(w[1])}


def thong_so_bien(cur: dict, b: dict, path: str, cham: set) -> dict:
    """Thông số TUYỆT ĐỐI của một biến thể cho một ảnh — đúng như HocMauCore.thongSoBien,
    để mô hình tính thay đổi (cu -> moi) cùng một kiểu cho mọi biến thể."""
    st = dict(cur)
    if b.get("goc"):
        return st
    for k, v in (nen_cua(cur) or {}).items():
        st[k] = v
    for k, v in (b.get("doi") or {}).items():
        st[k] = _so(cur.get(k)) + float(v)
    for k, v in (b.get("dat") or {}).items():
        st[k] = v
    for k, v in ((b.get("dat_anh") or {}).get(path) or {}).items():
        st[k] = v
    return st


# ===================================================================== cầu nối plugin
def yeu_cau(dest, ds: list, bien: list, canh: int = 1024, chat: int = 90,
            ma: str | None = None, job_dir: Path | None = None) -> Path:
    """Ghi jobs/request_hocmau.txt (JSON) cho HocMauCore. ds: [{"path", "cur"}]."""
    d = Path(job_dir or at.LR_JOB_DIR)
    d.mkdir(parents=True, exist_ok=True)
    for ten in (TEN_TIEN_DO, TEN_BANG, TEN_CO_DUNG):
        try:
            (d / ten).unlink()
        except OSError:
            pass
    req = {"id": ma or datetime.now().strftime("%Y%m%d_%H%M%S"), "dest": str(Path(dest)),
           "canh": int(canh), "chat": int(chat),
           "anh": [{"path": a["path"], "nen": nen_cua(a["cur"])} for a in ds], "bien": bien}
    f = d / TEN_YEU_CAU
    tmp = d / (TEN_YEU_CAU + ".part")
    tmp.write_text(json.dumps(req, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, f)
    return f


def tien_do(job_dir: Path | None = None) -> dict:
    out: dict = {}
    try:
        txt = (Path(job_dir or at.LR_JOB_DIR) / TEN_TIEN_DO).read_text(encoding="utf-8",
                                                                      errors="replace")
    except OSError:
        return {}
    for dong in txt.splitlines():
        k, _, v = dong.partition("=")
        if k:
            out[k.strip()] = v.strip()
    for k in ("xong", "tong", "anh_xong", "anh_tong", "thieu", "bo", "lech"):
        try:
            out[k] = int(out[k])
        except (KeyError, ValueError):
            pass
    return out


def bang_anh(job_dir: Path | None = None) -> dict:
    """{đường dẫn: {biến thể: jpg}} từ hocmau_anh.tsv."""
    out: dict = {}
    try:
        lines = (Path(job_dir or at.LR_JOB_DIR) / TEN_BANG).read_text(
            encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out
    for line in lines[1:]:
        v = line.split("\t")
        if len(v) >= 3 and all(v[:3]):
            out.setdefault(v[1], {})[v[0]] = v[2]
    return out


def xin_dung(job_dir: Path | None = None) -> None:
    d = Path(job_dir or at.LR_JOB_DIR)
    d.mkdir(parents=True, exist_ok=True)
    (d / TEN_CO_DUNG).write_text("dung\n", encoding="utf-8")


# ===================================================================== mẫu điểm ảnh
def doc_anh(p) -> np.ndarray:
    from PIL import Image
    with Image.open(p) as im:
        return np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0


def mau_anh(r: dict | None, cap: dict, seed: int = 0) -> dict | None:
    """Mẫu điểm ảnh của MỘT ảnh học: cùng toạ độ trên mọi ảnh dựng của nó (cap: {biến thể:
    jpg}). Loại: 0 da (mặt nạ phân vùng trên ảnh "nen"), 1 trung tính, 2 khung.
    -> {"px": {biến thể: (N, 3) float32}, "loai": (N,), "wh"} hoặc None."""
    import mat_na_da as mn
    if "nen" not in cap:
        return None
    nen = doc_anh(cap["nen"])
    H, W = nen.shape[:2]
    m = mn.mat_na(np.ascontiguousarray((nen * 255).astype(np.uint8)), r)
    rng = np.random.default_rng(seed)
    da = np.flatnonzero(m["da"].reshape(-1)) if m.get("n") else np.array([], int)
    px = nen.reshape(-1, 3)
    lab = lab_cua(px)
    trong_mat = np.zeros((H, W), bool)
    for x, y, w, h in m.get("mat") or []:
        trong_mat[int(max(0, y - 0.3 * h)):int(y + 1.3 * h), int(max(0, x - 0.3 * w)):int(x + 1.3 * w)] = True
    tt = np.flatnonzero((lab[:, 0] >= 0.30) & (lab[:, 0] <= 0.96)
                        & (np.hypot(lab[:, 1], lab[:, 2]) < 0.025) & ~trong_mat.reshape(-1))

    def chon(idx, n):
        return np.sort(rng.choice(idx, n, replace=False)) if len(idx) > n else idx
    idx = [chon(da, SO_DA), chon(tt, SO_TRUNG), chon(np.arange(H * W), SO_KHUNG)]
    loai = np.concatenate([np.full(len(i), k, np.int8) for k, i in enumerate(idx)])
    idx = np.concatenate(idx)
    out = {"loai": loai, "wh": (W, H), "px": {}}
    for ten, jpg in cap.items():
        a = nen if ten == "nen" else doc_anh(jpg)
        if a.shape[:2] != (H, W):
            continue
        out["px"][ten] = a.reshape(-1, 3)[idx].astype(np.float32)
    return loc_da(out)


def loc_da(mau: dict) -> dict:
    """Điểm "da" (loai 0) mà màu ở ảnh nen KHÔNG phải màu da (hue OkLab ngoài DA_HUE) ->
    loai 2 (khung): vẫn dùng học đường đáp ứng, không tính vào màu da."""
    px = (mau.get("px") or {}).get("nen")
    if px is None or not len(px):
        return mau
    lab = lab_cua(px)
    h = np.degrees(np.arctan2(lab[:, 2], lab[:, 1]))
    sai = (np.asarray(mau["loai"]) == 0) & ~((h >= DA_HUE[0]) & (h <= DA_HUE[1]))
    if sai.any():
        loai = np.array(mau["loai"], copy=True)
        loai[sai] = 2
        mau["loai"] = loai
    return mau


# ===================================================================== mô hình
class MoHinh:
    """Lightroom đổi điểm ảnh ĐÃ DỰNG thế nào khi thông số đổi cu -> moi (xem đầu file)."""

    def __init__(self):
        self.g = np.tile(np.log(np.clip(lin_srgb_inv_grid(), 1e-4, None)), (3, 1))
        self.kieu_g = "kenh"
        self.wb = {k: np.zeros((3, 3)) for k in ("A1", "A2", "B1", "B2")}
        self.hlsh = {"x": np.linspace(-8, 0, 16), "hl": np.zeros(16), "sh": np.zeros(16)}
        self.curve = {"mien": at.DEFAULTS.get("curve_mien", "melissa"),
                      "kieu": at.DEFAULTS.get("curve_kieu_tong", "kenh")}
        self.hsl = {}                     # khoá -> {"a": (3, 24, 3), "b": (3, 24, 3)}
        self.cg = {"mid": np.zeros((NGAN_L, 2, 2)), "hi": np.zeros(NGAN_L), "sh": np.zeros(NGAN_L),
                   "R": np.eye(2)}
        self.thu_tu = "curve_truoc"
        self.pham_vi = {}
        self.preview_sua = None           # (3, 256) bảng preview -> bản xuất, None = đồng nhất
        self.kiem_dinh = {}
        self.dat = False
        self.khoa = ""
        self.thong_tin = {}

    # ---------------------------------------------------------- áp
    #[[ HAI KIỂU ĐƯỜNG ĐÁP ỨNG (kieu_g). "kenh": mỗi kênh một hàm trên giá trị miền curve
    #   p. "rgb_tone": MỘT hàm trên tuyến tính ProPhoto t (= giải TRC của p), áp giữ sắc
    #   (kênh lớn / nhỏ nhất qua hàm, kênh giữa theo tỉ lệ cũ) — RefBaselineRGBTone của DNG
    #   SDK mà Camera Raw dùng cho đường tông của profile. Học cả hai, giữ kiểu sai ít hơn. ]]
    def _g(self, p):
        """ln u (tuyến tính hoá) của giá trị miền curve TRƯỚC curve."""
        x = np.linspace(0.0, 1.0, LUOI)
        p = np.asarray(p, dtype=np.float64)
        if self.kieu_g == "rgb_tone":
            t = cl._trc_giai(p, self.curve["mien"])                    # noqa: SLF001
            G = self.g[0]

            def f(v):                     # lưới theo t^(1/2.2): đủ nút cho vùng tối
                return np.exp(np.interp(np.power(np.clip(v, 0.0, 1.0), 1 / 2.2), x, G))
            return np.log(np.clip(cl._rgb_tone(t, f), 1e-6, None))      # noqa: SLF001
        return np.stack([np.interp(p[:, c], x, self.g[c]) for c in range(3)], axis=1)

    def _g_nguoc(self, lnu):
        x = np.linspace(0.0, 1.0, LUOI)
        lnu = np.asarray(lnu, dtype=np.float64)
        if self.kieu_g == "rgb_tone":
            G = self.g[0]

            def f(v):
                return np.power(np.interp(np.log(np.clip(v, 1e-6, None)), G, x), 2.2)
            t = cl._rgb_tone(np.exp(lnu), f)                             # noqa: SLF001
            return cl._trc_ma(np.clip(t, 0.0, 1.0), self.curve["mien"])  # noqa: SLF001
        return np.stack([np.interp(lnu[:, c], self.g[c], x) for c in range(3)], axis=1)

    def _M_wb(self, dm: float, dt: float) -> np.ndarray:
        I = np.eye(3)
        Mm = I + self.wb["A1"] * dm + self.wb["A2"] * dm * dm
        Mt = I + self.wb["B1"] * dt + self.wb["B2"] * dt * dt
        return Mt @ Mm

    def _hsl_doi(self, lab, cu: dict, moi: dict):
        """(Δhue °, Δln C, ΔL) của mọi điểm khi HSL đổi."""
        n = lab.shape[0]
        dh, dlc, dL = np.zeros(n), np.zeros(n), np.zeros(n)
        C = np.hypot(lab[:, 1], lab[:, 2])
        h = np.degrees(np.arctan2(lab[:, 2], lab[:, 1])) % 360.0
        hb = h / (360.0 / NGAN_HUE) - 0.5
        i0 = np.floor(hb).astype(int) % NGAN_HUE
        f = hb - np.floor(hb)
        cb = np.clip(np.searchsorted(NGAN_C, C, side="right") - 1, 0, len(NGAN_C) - 1)
        song = C >= NGAN_C[0]
        for k, bang in self.hsl.items():
            s = _so(moi.get(k)) - _so(cu.get(k))
            if abs(s) < 1e-9:
                continue
            for j, arr in enumerate((dh, dlc, dL)):
                a = np.asarray(bang["a"])[j]
                b = np.asarray(bang["b"])[j]
                va = (1 - f) * a[i0, cb] + f * a[(i0 + 1) % NGAN_HUE, cb]
                vb = (1 - f) * b[i0, cb] + f * b[(i0 + 1) % NGAN_HUE, cb]
                arr += np.where(song, va * s + vb * s * s, 0.0)
        return dh, dlc, dL

    def _ap_hsl(self, px, cu, moi):
        if not any(abs(_so(moi.get(k)) - _so(cu.get(k))) > 1e-9 for k in self.hsl):
            return px
        lab = lab_cua(px)
        dh, dlc, dL = self._hsl_doi(lab, cu, moi)
        C = np.hypot(lab[:, 1], lab[:, 2]) * np.exp(dlc)
        h = np.arctan2(lab[:, 2], lab[:, 1]) + np.radians(dh)
        lab2 = np.stack([lab[:, 0] + dL, C * np.cos(h), C * np.sin(h)], axis=1)
        return srgb_tu_lab(lab2)

    def truoc_curve(self, px_srgb, st: dict) -> np.ndarray:
        """Điểm ảnh đã dựng -> giá trị miền curve TRƯỚC bộ curve điểm của ảnh (đảo curve
        tổng + curve kênh). Đường đáp ứng g học ở đây: preset mỗi buổi một curve, học trên
        ảnh đã qua curve là trộn curve của preset vào đáp ứng của Lightroom."""
        w = cl.srgb_sang_mien(np.clip(np.asarray(px_srgb, dtype=np.float64), 0.0, 1.0),
                              self.curve["mien"])
        c = curve_cua(st)
        bt = cl.bang(c["master"])
        out = np.empty_like(w)
        for i, k in enumerate(cl.KENH):
            out[:, i] = cl._nguoc_bang(cl._nguoc_bang(w[:, i], cl.bang(c[k])), bt)  # noqa: SLF001
        return out

    def qua_curve(self, p, st: dict) -> np.ndarray:
        """Giá trị miền curve trước curve -> sRGB 0..1 sau bộ curve điểm của `st`."""
        c = curve_cua(st)
        bt = cl.bang(c["master"])

        def f(v):
            return cl._ap_bang(v, bt)                                  # noqa: SLF001
        q = cl._rgb_tone(p, f) if self.curve["kieu"] == "rgb_tone" else f(p)  # noqa: SLF001
        out = np.empty_like(q)
        for i, k in enumerate(cl.KENH):
            out[:, i] = cl._ap_bang(q[:, i], cl.bang(c[k]))            # noqa: SLF001
        return cl.mien_sang_srgb(np.clip(out, 0.0, 1.0), self.curve["mien"])

    @staticmethod
    def _v(st, kh, ks):
        H, S = _so(st.get(kh)), _so(st.get(ks))
        return np.array([math.cos(math.radians(H)), math.sin(math.radians(H))]) * S / 100.0

    def _ap_cg(self, px, cu, moi):
        dmid = self._v(moi, *KHOA_CG_MID) - self._v(cu, *KHOA_CG_MID)
        dhi = self._v(moi, *KHOA_CG_HI) - self._v(cu, *KHOA_CG_HI)
        dsh = self._v(moi, *KHOA_CG_SH) - self._v(cu, *KHOA_CG_SH)
        if not (np.any(np.abs(dmid) > 1e-9) or np.any(np.abs(dhi) > 1e-9)
                or np.any(np.abs(dsh) > 1e-9)):
            return px
        lab = lab_cua(px)
        Lb = np.clip(lab[:, 0] * NGAN_L - 0.5, 0, NGAN_L - 1)
        i0 = np.floor(Lb).astype(int)
        i1 = np.minimum(i0 + 1, NGAN_L - 1)
        f = (Lb - i0)[:, None]
        mid = np.asarray(self.cg["mid"])
        Mb = (1 - f[:, :, None]) * mid[i0] + f[:, :, None] * mid[i1]
        dab = np.einsum("nij,j->ni", Mb, dmid)
        R = np.asarray(self.cg["R"])
        for ten, dv in (("hi", dhi), ("sh", dsh)):
            if np.any(np.abs(dv) > 1e-9):
                w = np.asarray(self.cg[ten])
                wl = (1 - f[:, 0]) * w[i0] + f[:, 0] * w[i1]
                dab = dab + wl[:, None] * (R @ dv)[None, :]
        lab[:, 1:] += dab
        return srgb_tu_lab(lab)

    def ap(self, px_srgb, cu: dict, moi: dict) -> np.ndarray:
        """Điểm ảnh Lightroom dựng (sRGB 0..1, (N, 3)) với thông số `cu` -> dự đoán với `moi`.

        Thứ tự: gỡ curve của `cu` -> g (tuyến tính hoá) -> WB -> Exposure -> HL/SH -> g⁻¹
        -> [HSL nếu hsl_truoc] -> curve của `moi` -> [HSL nếu curve_truoc] -> Color Grading."""
        px = np.clip(np.asarray(px_srgb, dtype=np.float64), 0.0, 1.0)
        p = self.truoc_curve(px, cu)
        lnu = self._g(p)
        wc, wm = wb_cua(cu), wb_cua(moi)
        if wc and wm and (abs(wc[0] - wm[0]) > 1 or abs(wc[1] - wm[1]) > 0.05):
            dm = 1e6 / wm[0] - 1e6 / wc[0]
            M = self._M_wb(dm, wm[1] - wc[1])
            lnu = np.log(np.clip(np.exp(lnu) @ M.T, 1e-6, None))
        dev = _so(moi.get("Exposure2012")) - _so(cu.get("Exposure2012"))
        lnu = lnu + dev * math.log(2.0)
        dhl = _so(moi.get("Highlights2012")) - _so(cu.get("Highlights2012"))
        dsh = _so(moi.get("Shadows2012")) - _so(cu.get("Shadows2012"))
        if abs(dhl) > 1e-9 or abs(dsh) > 1e-9:
            lnY = np.log(np.clip(np.exp(lnu) @ _Y, 1e-6, None))
            k = (np.interp(lnY, self.hlsh["x"], self.hlsh["hl"]) * dhl
                 + np.interp(lnY, self.hlsh["x"], self.hlsh["sh"]) * dsh)
            lnu = lnu + k[:, None]
        p = np.clip(self._g_nguoc(lnu), 0.0, 1.0)
        if self.thu_tu == "hsl_truoc" and self._co_hsl(cu, moi):
            #  HSL trước curve: làm trên ảnh "chưa curve" (curve đồng nhất) rồi mới qua curve
            mien = self.curve["mien"]
            px0 = self._ap_hsl(cl.mien_sang_srgb(p, mien), cu, moi)
            p = cl.srgb_sang_mien(px0, mien)
            px = self.qua_curve(p, moi)
        else:
            px = self._ap_hsl(self.qua_curve(p, moi), cu, moi)
        return np.clip(self._ap_cg(px, cu, moi), 0.0, 1.0)

    def _co_hsl(self, cu, moi) -> bool:
        return any(abs(_so(moi.get(k)) - _so(cu.get(k))) > 1e-9 for k in self.hsl)

    def sua_preview(self, px):
        """Điểm ảnh PREVIEW Lightroom -> như bản xuất (bảng học lúc hiệu chỉnh)."""
        if self.preview_sua is None:
            return px
        x = np.linspace(0.0, 1.0, 256)
        b = np.asarray(self.preview_sua)
        return np.stack([np.interp(px[:, c], x, b[c]) for c in range(3)], axis=1)

    def ngoai_pham_vi(self, cu: dict, moi: dict) -> list:
        """Khoá đổi vượt khoảng đã học (dự đoán là ngoại suy)."""
        out = []
        for k, (lo, hi) in (self.pham_vi or {}).items():
            if k == "mired":
                wc, wm = wb_cua(cu), wb_cua(moi)
                d = (1e6 / wm[0] - 1e6 / wc[0]) if (wc and wm) else 0.0
            elif k == "tint":
                wc, wm = wb_cua(cu), wb_cua(moi)
                d = (wm[1] - wc[1]) if (wc and wm) else 0.0
            else:
                d = _so(moi.get(k)) - _so(cu.get(k))
            if d < lo - 1e-9 or d > hi + 1e-9:
                out.append(k)
        return out

    # ---------------------------------------------------------- lưu / nạp
    def thanh_dict(self) -> dict:
        def L(v):
            return np.asarray(v).tolist() if isinstance(v, np.ndarray) else v
        return {"phien_ban": PHIEN_BAN, "khoa": self.khoa, "g": L(self.g), "kieu_g": self.kieu_g,
                "wb": {k: L(v) for k, v in self.wb.items()},
                "hlsh": {k: L(v) for k, v in self.hlsh.items()}, "curve": dict(self.curve),
                "hsl": {k: {"a": L(v["a"]), "b": L(v["b"])} for k, v in self.hsl.items()},
                "cg": {k: L(v) for k, v in self.cg.items()}, "thu_tu": self.thu_tu,
                "pham_vi": self.pham_vi, "preview_sua": L(self.preview_sua),
                "kiem_dinh": self.kiem_dinh, "dat": bool(self.dat), "thong_tin": self.thong_tin}

    @classmethod
    def tu_dict(cls, d: dict) -> "MoHinh":
        m = cls()
        A = np.asarray
        m.khoa = d.get("khoa", "")
        m.g = A(d["g"], dtype=np.float64)
        m.kieu_g = d.get("kieu_g", "kenh")
        m.wb = {k: A(v, dtype=np.float64) for k, v in d["wb"].items()}
        m.hlsh = {k: A(v, dtype=np.float64) for k, v in d["hlsh"].items()}
        m.curve = dict(d.get("curve") or m.curve)
        m.hsl = {k: {"a": A(v["a"]), "b": A(v["b"])} for k, v in (d.get("hsl") or {}).items()}
        m.cg = {k: A(v, dtype=np.float64) for k, v in d["cg"].items()}
        m.thu_tu = d.get("thu_tu", m.thu_tu)
        m.pham_vi = {k: tuple(v) for k, v in (d.get("pham_vi") or {}).items()}
        m.preview_sua = A(d["preview_sua"]) if d.get("preview_sua") is not None else None
        m.kiem_dinh = d.get("kiem_dinh") or {}
        m.dat = bool(d.get("dat"))
        m.thong_tin = d.get("thong_tin") or {}
        return m


def lin_srgb_inv_grid():
    """Đường g khởi đầu: giải mã sRGB (ln của tuyến tính) trên lưới LUOI."""
    return at.srgb_to_linear(np.linspace(0.0, 1.0, LUOI))


# ===================================================================== khớp
def _he_so_g(z):
    p = np.clip(z, 0.0, 1.0) * (LUOI - 1)
    i0 = np.minimum(np.floor(p).astype(int), LUOI - 2)
    return i0, p - i0


def khop_g(cap: list, lam: float = 0.3) -> np.ndarray:
    """Đường đáp ứng g mỗi kênh (LUOI nút) từ các cặp (z0, z1, d): g(z1) − g(z0) = d.
    Phương trình chuẩn cộng dồn (mỗi phương trình 4 hệ số), phạt đạo hàm hai, neo g ở
    giữa = ln(sRGB⁻¹(0.5)); ép đơn điệu."""
    out = np.zeros((3, LUOI))
    neo = int(LUOI // 2)
    g0 = np.log(np.clip(lin_srgb_inv_grid(), 1e-4, None))
    D2 = np.zeros((LUOI - 2, LUOI))
    for i in range(LUOI - 2):
        D2[i, i:i + 3] = (1.0, -2.0, 1.0)
    for c in range(3):
        AtA = np.zeros((LUOI, LUOI))
        Atb = np.zeros(LUOI)
        for z0, z1, d in cap:
            a, b = np.asarray(z0)[:, c], np.asarray(z1)[:, c]
            ok = (a > 0.02) & (a < 0.98) & (b > 0.02) & (b < 0.98)
            if not ok.any():
                continue
            a, b = a[ok], b[ok]
            i0, f0 = _he_so_g(a)
            i1, f1 = _he_so_g(b)
            I = np.stack([i1, i1 + 1, i0, i0 + 1], axis=1)
            C = np.stack([1 - f1, f1, -(1 - f0), -f0], axis=1)
            for p in range(4):
                for q in range(4):
                    np.add.at(AtA, (I[:, p], I[:, q]), C[:, p] * C[:, q])
                np.add.at(Atb, I[:, p], C[:, p] * d)
        n = max(1.0, float(np.trace(AtA)) / LUOI)
        AtA = AtA + lam * n * (D2.T @ D2)
        AtA[neo, neo] += 1e6 * n
        Atb[neo] += 1e6 * n * g0[neo]
        #  hai đầu thiếu dữ liệu: kéo nhẹ về g khởi đầu
        AtA += 1e-6 * n * np.eye(LUOI)
        Atb += 1e-6 * n * g0
        g = np.linalg.solve(AtA, Atb)
        g = np.maximum.accumulate(g) + np.linspace(0.0, 1e-4, LUOI)
        out[c] = g
    return out


def khop_wb(cap: dict, mh: MoHinh) -> dict:
    """{"A1","A2","B1","B2"} từ M của k± (Δmired) và t± (Δtint). cap: {ten: [(px_nen,
    px_bien, Δ)]}."""
    def M_cua(ds):
        U, V = [], []
        for p0, p1, _d in ds:
            ok = (p0.max(axis=1) < 0.98) & (p1.max(axis=1) < 0.98) & (p0.min(axis=1) > 0.02)
            U.append(np.exp(mh._g(p0[ok].astype(np.float64))))
            V.append(np.exp(mh._g(p1[ok].astype(np.float64))))
        if not U:
            return None
        U, V = np.vstack(U), np.vstack(V)
        w = 1.0 / np.clip(U.sum(axis=1, keepdims=True), 1e-3, None)
        return np.linalg.lstsq(U * w, V * w, rcond=None)[0].T
    out = {k: np.zeros((3, 3)) for k in ("A1", "A2", "B1", "B2")}
    for ten_c, ten_t, dk, (k1, k2) in (("k+", "k-", MIRED, ("A1", "A2")),
                                       ("t+", "t-", TINT, ("B1", "B2"))):
        Mp, Mn = M_cua(cap.get(ten_c) or []), M_cua(cap.get(ten_t) or [])
        if Mp is None or Mn is None:
            continue
        #  k+ = Δmired −MIRED (ấm hơn); t+ = Δtint +TINT
        dp = -dk if ten_c == "k+" else dk
        I = np.eye(3)
        out[k1] = (Mp - Mn) / (2.0 * dp)
        out[k2] = (Mp + Mn - 2.0 * I) / (2.0 * dp * dp)
    return out


def khop_hlsh(cap: dict, mh: MoHinh) -> dict:
    x = np.linspace(-8.0, 0.0, 16)
    out = {"x": x, "hl": np.zeros(16), "sh": np.zeros(16)}
    for ten, khoa, s in (("hl-", "hl", HL), ("sh+", "sh", SH)):
        Y0, Y1 = [], []
        for p0, p1, _d in cap.get(ten) or []:
            ok = (p0.max(axis=1) < 0.98) & (p1.max(axis=1) < 0.98)
            Y0.append(np.exp(mh._g(p0[ok].astype(np.float64))) @ _Y)
            Y1.append(np.exp(mh._g(p1[ok].astype(np.float64))) @ _Y)
        if not Y0:
            continue
        l0 = np.log(np.clip(np.concatenate(Y0), 1e-6, None))
        r = np.log(np.clip(np.concatenate(Y1), 1e-6, None)) - l0
        k = np.zeros(16)
        bien = np.concatenate([[-np.inf], (x[1:] + x[:-1]) / 2, [np.inf]])
        for i in range(16):
            m = (l0 >= bien[i]) & (l0 < bien[i + 1])
            k[i] = float(np.median(r[m])) / s if m.sum() >= 20 else np.nan
        if np.all(np.isnan(k)):
            continue
        ok = ~np.isnan(k)
        out[khoa] = np.interp(x, x[ok], k[ok])
    return out


def chon_curve(cap: list) -> tuple[dict, dict]:
    """(giả thuyết tốt nhất {"mien","kieu"}, {giả thuyết: sai số}). cap: [(px_nen, px_bien,
    curve_cu, curve_moi)]."""
    sai = {}
    for mien in cl.MIEN:
        for kieu in cl.KIEU_TONG:
            e, n = 0.0, 0
            for p0, p1, cu, moi in cap:
                ok = (p0.max(axis=1) < 0.98) & (p1.max(axis=1) < 0.98)
                du = cl.ap_anh(p0[ok].astype(np.float64), cu, moi, mien, kieu)
                e += float(np.abs(du - p1[ok]).sum())
                n += int(ok.sum()) * 3
            sai[f"{mien}/{kieu}"] = e / max(1, n) * 255.0
    tot = min(sai, key=sai.get)
    mien, kieu = tot.split("/")
    return {"mien": mien, "kieu": kieu}, sai


def _bang_hsl(lab0, lab1, s_cap):
    """Trung vị (Δh, Δln C, ΔL) mỗi ngăn hue × chroma — cho MỘT biến thể."""
    C0 = np.hypot(lab0[:, 1], lab0[:, 2])
    C1 = np.hypot(lab1[:, 1], lab1[:, 2])
    h0 = np.degrees(np.arctan2(lab0[:, 2], lab0[:, 1])) % 360.0
    h1 = np.degrees(np.arctan2(lab1[:, 2], lab1[:, 1]))
    dh = _goc(h1 - h0)
    dlc = np.log(np.clip(C1, 1e-4, None) / np.clip(C0, 1e-4, None))
    dL = lab1[:, 0] - lab0[:, 0]
    ib = np.floor(h0 / (360.0 / NGAN_HUE)).astype(int) % NGAN_HUE
    cb = np.searchsorted(NGAN_C, C0, side="right") - 1
    out = np.full((3, NGAN_HUE, len(NGAN_C)), np.nan)
    for i in range(NGAN_HUE):
        for j in range(len(NGAN_C)):
            m = (ib == i) & (cb == j)
            if m.sum() >= 20:
                out[0, i, j] = np.median(dh[m])
                out[1, i, j] = np.median(dlc[m])
                out[2, i, j] = np.median(dL[m])
    return out


def _lap_hue(t):
    """Ngăn hue thiếu dữ liệu: nội suy vòng theo hue; cả hàng trống -> 0."""
    t = np.array(t, dtype=np.float64)
    x = np.arange(NGAN_HUE)
    for j in range(t.shape[0]):
        for k in range(t.shape[2]):
            v = t[j, :, k]
            ok = ~np.isnan(v)
            if not ok.any():
                t[j, :, k] = 0.0
            elif not ok.all():
                xs = np.concatenate([x[ok] - NGAN_HUE, x[ok], x[ok] + NGAN_HUE])
                vs = np.concatenate([v[ok]] * 3)
                t[j, :, k] = np.interp(x, xs, vs)
    return t


def khop_hsl(cap: dict) -> dict:
    """{khoá HSL: {"a", "b"}} — cap: {ten biến thể: [(px_nen, px_bien)]}."""
    def bang(ten, s):
        ds = cap.get(ten) or []
        if not ds:
            return None
        l0 = np.vstack([lab_cua(p0) for p0, _p in ds])
        l1 = np.vstack([lab_cua(p1) for _q, p1 in ds])
        return _lap_hue(_bang_hsl(l0, l1, s))
    out = {}
    for khoa, ten in (("HueAdjustmentOrange", "o_hue"), ("SaturationAdjustmentOrange", "o_sat")):
        tp, tn = bang(ten + "+", HSL_S), bang(ten + "-", -HSL_S)
        if tp is None or tn is None:
            continue
        out[khoa] = {"a": (tp - tn) / (2 * HSL_S), "b": (tp + tn) / (2 * HSL_S * HSL_S)}
    for khoa, ten in (("LuminanceAdjustmentOrange", "o_lum+"), ("HueAdjustmentRed", "r_hue+"),
                      ("SaturationAdjustmentRed", "r_sat+")):
        tp = bang(ten, HSL_S)
        if tp is not None:
            out[khoa] = {"a": tp / HSL_S, "b": np.zeros_like(tp)}
    return out


def khop_cg(cap: dict) -> dict:
    """Color Grading: cap {ten: [(px_nen, px_bien, st_cu, st_moi)]}."""
    out = {"mid": np.zeros((NGAN_L, 2, 2)), "hi": np.zeros(NGAN_L), "sh": np.zeros(NGAN_L),
           "R": np.eye(2)}
    V, D, Lb = [], [], []
    for ten in ("cg_m30", "cg_m150", "cg_m270"):
        for p0, p1, cu, moi in cap.get(ten) or []:
            l0, l1 = lab_cua(p0), lab_cua(p1)
            dv = MoHinh._v(moi, *KHOA_CG_MID) - MoHinh._v(cu, *KHOA_CG_MID)
            V.append(np.tile(dv, (len(l0), 1)))
            D.append(l1[:, 1:] - l0[:, 1:])
            Lb.append(l0[:, 0])
    if V:
        V, D, Lb = np.vstack(V), np.vstack(D), np.concatenate(Lb)
        ib = np.clip((Lb * NGAN_L).astype(int), 0, NGAN_L - 1)
        for b in range(NGAN_L):
            m = ib == b
            if m.sum() >= 30:
                out["mid"][b] = np.linalg.lstsq(V[m], D[m], rcond=None)[0].T
        w = np.bincount(ib, minlength=NGAN_L).astype(float)
        R = np.tensordot(w / max(1.0, w.sum()), out["mid"], axes=1)
        g = math.sqrt(abs(np.linalg.det(R))) or 1.0
        out["R"] = R / g
        #  ngăn thiếu dữ liệu: theo ngăn gần nhất có
        co = [b for b in range(NGAN_L) if np.any(out["mid"][b])]
        for b in range(NGAN_L):
            if co and not np.any(out["mid"][b]):
                out["mid"][b] = out["mid"][min(co, key=lambda x: abs(x - b))]
    for ten, khoa, kv in (("cg_h", "hi", KHOA_CG_HI), ("cg_s", "sh", KHOA_CG_SH)):
        num, den = np.zeros(NGAN_L), np.zeros(NGAN_L)
        for p0, p1, cu, moi in cap.get(ten) or []:
            l0, l1 = lab_cua(p0), lab_cua(p1)
            dv = MoHinh._v(moi, *kv) - MoHinh._v(cu, *kv)
            u = out["R"] @ dv
            if not np.any(u):
                continue
            ib = np.clip((l0[:, 0] * NGAN_L).astype(int), 0, NGAN_L - 1)
            proj = (l1[:, 1:] - l0[:, 1:]) @ u
            np.add.at(num, ib, proj)
            np.add.at(den, ib, float(u @ u))
        out[khoa] = np.where(den > 0, num / np.maximum(den, 1e-12), 0.0)
    return out


def khop_preview(cap: list) -> np.ndarray | None:
    """Bảng preview -> bản xuất (3, 256) từ cặp (px_preview, px_xuat) cùng toạ độ."""
    if not cap:
        return None
    P = np.vstack([a for a, _b in cap])
    X = np.vstack([b for _a, b in cap])
    x = np.linspace(0.0, 1.0, 256)
    out = np.zeros((3, 256))
    for c in range(3):
        bien = np.linspace(0.0, 1.0, 65)
        tam, gt = [], []
        for i in range(64):
            m = (P[:, c] >= bien[i]) & (P[:, c] < bien[i + 1])
            if m.sum() >= 20:
                tam.append(float(np.median(P[m, c])))
                gt.append(float(np.median(X[m, c])))
        if len(tam) < 4:
            return None
        out[c] = np.maximum.accumulate(np.interp(x, [0.0] + tam + [1.0], [0.0] + gt + [1.0]))
    return out


# ===================================================================== học + kiểm định
#: biến thể dùng để học (tổ hợp chỉ để kiểm định)
BIEN_HOC = ("ev+", "ev-", "hl-", "sh+", "k+", "k-", "t+", "t-", "o_hue+", "o_hue-", "o_sat+",
            "o_sat-", "o_lum+", "r_hue+", "r_sat+", "cv_r", "cv_g", "cv_b", "cv_s", "cg_m30",
            "cg_m150", "cg_m270", "cg_h", "cg_s")
TO_HOP = ("tohop1", "tohop2")


def _cap_rgb(ev: list, mien: str) -> list:
    """Cặp Exposure cho kiểu "rgb_tone": kênh LỚN và NHỎ nhất (cùng kênh trước / sau) của
    tuyến tính ProPhoto, mã hoá t^(1/2.2) — một hàm chung, nhân ba cột cho khop_g."""
    out = []
    for p0, p1, d in ev:
        t0 = cl._trc_giai(np.asarray(p0, dtype=np.float64), mien)     # noqa: SLF001
        t1 = cl._trc_giai(np.asarray(p1, dtype=np.float64), mien)     # noqa: SLF001
        n = np.arange(len(t0))
        i, j = t0.argmax(axis=1), t0.argmin(axis=1)
        a = np.power(np.clip(np.concatenate([t0[n, i], t0[n, j]]), 0.0, 1.0), 1 / 2.2)
        b = np.power(np.clip(np.concatenate([t1[n, i], t1[n, j]]), 0.0, 1.0), 1 / 2.2)
        out.append((np.repeat(a[:, None], 3, 1), np.repeat(b[:, None], 3, 1), d))
    return out


#: biến thể chỉ đổi WB / Exposure / HL-SH — để chọn kiểu đường đáp ứng
BIEN_TONG = ("ev+", "ev-", "hl-", "sh+", "k+", "k-", "t+", "t-")


def _sai_tong(mh: "MoHinh", anh: list) -> float:
    e = []
    for a in anh:
        px = a["mau"]["px"]
        for t in BIEN_TONG:
            if t in px and "nen" in px:
                e.append(float(np.abs(mh.ap(px["nen"], a["st"]["nen"], a["st"][t]) - px[t]).mean()))
    return float(np.mean(e)) if e else 0.0


def khop(anh: list) -> MoHinh:
    """Học mô hình. anh: [{"mau": mau_anh(), "st": {biến thể: thông số tuyệt đối}}]."""
    mh = MoHinh()

    def cap(ten, them=None):
        out = []
        for a in anh:
            px = a["mau"]["px"]
            if ten in px and "nen" in px:
                out.append((px["nen"], px[ten]) + (them(a) if them else ()))
        return out
    #  1. curve TRƯỚC: miền curve quyết "trước curve" — nơi học đường đáp ứng
    cv = []
    for t in ("cv_r", "cv_g", "cv_b", "cv_s"):
        cv += cap(t, lambda a, t=t: (curve_cua(a["st"]["nen"]), curve_cua(a["st"][t])))
    if cv:
        mh.curve, sai = chon_curve(cv)
        mh.thong_tin["curve_sai"] = {k: round(v, 3) for k, v in sai.items()}

    def truoc(ten):
        """Cặp giá trị TRƯỚC curve — bỏ điểm chạm biên gam sRGB ở một trong hai ảnh (ảnh
        xuất cắt ở biên sRGB: đảo về ProPhoto ra số sai, kéo lệch cả đường đáp ứng)."""
        out = []
        for a in anh:
            px = a["mau"]["px"]
            if ten in px and "nen" in px:
                p0, p1 = px["nen"], px[ten]
                ok = ((p0.min(axis=1) > 0.01) & (p0.max(axis=1) < 0.99)
                      & (p1.min(axis=1) > 0.01) & (p1.max(axis=1) < 0.99))
                if ok.sum() >= 50:
                    out.append((mh.truoc_curve(p0[ok], a["st"]["nen"]),
                                mh.truoc_curve(p1[ok], a["st"][ten])))
        return out
    #  2. đường đáp ứng từ Exposure ± (cả hai kiểu), 3. WB, HL / SH theo từng kiểu
    ev = [(p0, p1, EV * math.log(2.0)) for p0, p1 in truoc("ev+")]
    ev += [(p0, p1, -EV * math.log(2.0)) for p0, p1 in truoc("ev-")]
    wb_cap = {t: [(p0, p1, 0.0) for p0, p1 in truoc(t)] for t in ("k+", "k-", "t+", "t-")}
    hs_cap = {t: [(p0, p1, 0.0) for p0, p1 in truoc(t)] for t in ("hl-", "sh+")}
    thu = {}
    for kieu in ("kenh", "rgb_tone"):
        mh.kieu_g = kieu
        if ev:
            mh.g = khop_g(ev) if kieu == "kenh" else khop_g(_cap_rgb(ev, mh.curve["mien"]))
        mh.wb = khop_wb(wb_cap, mh)
        mh.hlsh = khop_hlsh(hs_cap, mh)
        thu[kieu] = (_sai_tong(mh, anh), mh.g.copy(), mh.wb, mh.hlsh)
    mh.kieu_g = min(thu, key=lambda k: thu[k][0])
    mh.g, mh.wb, mh.hlsh = thu[mh.kieu_g][1:]
    mh.thong_tin["g_sai"] = {k: round(v[0] * 255, 3) for k, v in thu.items()}
    #  5. HSL, 6. CG
    mh.hsl = khop_hsl({t: cap(t) for t in ("o_hue+", "o_hue-", "o_sat+", "o_sat-", "o_lum+",
                                           "r_hue+", "r_sat+")})
    mh.cg = khop_cg({t: cap(t, lambda a, t=t: (a["st"]["nen"], a["st"][t]))
                     for t in ("cg_m30", "cg_m150", "cg_m270", "cg_h", "cg_s")})
    #  7. thứ tự curve / HSL: tổ hợp
    th = {}
    for thu in ("curve_truoc", "hsl_truoc"):
        mh.thu_tu = thu
        e = []
        for a in anh:
            for t in TO_HOP:
                if t in a["mau"]["px"]:
                    du = mh.ap(a["mau"]["px"]["nen"], a["st"]["nen"], a["st"][t])
                    e.append(float(np.abs(du - a["mau"]["px"][t]).mean()))
        th[thu] = float(np.mean(e)) if e else 0.0
    mh.thu_tu = min(th, key=th.get) if th else "curve_truoc"
    mh.thong_tin["thu_tu_sai"] = {k: round(v * 255, 3) for k, v in th.items()}
    mh.pham_vi = {"Exposure2012": (-EV, EV), "Highlights2012": (HL, 0.0), "Shadows2012": (0.0, SH),
                  "mired": (-MIRED, MIRED), "tint": (-TINT, TINT),
                  **{k: (-HSL_S, HSL_S) for k in KHOA_HSL}}
    return mh


def lech(px_du, px_that, loai) -> dict:
    """Lệch dự đoán / thật: da (hue °, q tỉ lệ, L) + trung tính (ab)."""
    out = {}
    da = loai == 0
    if da.sum() >= 50:
        L0, h0, q0 = thong_ke_da(px_du[da])
        L1, h1, q1 = thong_ke_da(px_that[da])
        out.update(hue=float(abs(_goc(h0 - h1))), q=float(abs(q0 / max(q1, 1e-9) - 1.0)),
                   L=float(abs(L0 - L1)))
    tt = loai == 1
    if tt.sum() >= 50:
        a, b = lab_cua(px_du[tt]), lab_cua(px_that[tt])
        out["ab"] = float(math.hypot(np.median(a[:, 1]) - np.median(b[:, 1]),
                                     np.median(a[:, 2]) - np.median(b[:, 2])))
    return out


def kiem_dinh(anh: list) -> dict:
    """Để lại từng ảnh: học trên phần còn lại, đoán ảnh đó. -> {biến thể: {chỉ số: trung vị,
    chỉ số_p90}, "dat": bool, ...}."""
    theo: dict = {}
    for i, a in enumerate(anh):
        con = anh[:i] + anh[i + 1:]
        if len(con) < 2:
            break
        mh = khop(con)
        px = a["mau"]["px"]
        for t in BIEN_HOC + TO_HOP:
            if t not in px:
                continue
            du = mh.ap(px["nen"], a["st"]["nen"], a["st"][t])
            l = lech(du, px[t], a["mau"]["loai"])
            khong = lech(px["nen"], px[t], a["mau"]["loai"])          # đoán "không đổi gì"
            theo.setdefault(t, []).append((l, khong))
    out = {}
    for t, ds in theo.items():
        d = {}
        for k in ("hue", "q", "L", "ab"):
            v = [x[0][k] for x in ds if k in x[0]]
            v0 = [x[1][k] for x in ds if k in x[1]]
            if v:
                d[k] = round(float(np.median(v)), 4)
                d[k + "_p90"] = round(float(np.percentile(v, 90)), 4)
                d[k + "_khong_doi"] = round(float(np.median(v0)), 4)
        d["n"] = len(ds)
        out[t] = d
    th = [out[t] for t in TO_HOP if t in out]
    out["dat"] = bool(th) and all(all(x.get(k, 0.0) <= DAT[k] for k in DAT) for x in th)
    return out


def so_goc(anh: list) -> dict:
    """"nen" (WB Custom ở Kelvin đang thấy) có như "goc" không; "sau" (sau khi trả lại) có
    như "goc" không — lệch trung bình mã 0..255."""
    out = {}
    for ten in ("nen", "sau"):
        v = [float(np.abs(a["mau"]["px"][ten] - a["mau"]["px"]["goc"]).mean() * 255)
             for a in anh if ten in a["mau"]["px"] and "goc" in a["mau"]["px"]]
        if v:
            out[ten] = {"tb": round(float(np.mean(v)), 3), "max": round(float(np.max(v)), 3)}
    return out


# ===================================================================== kho mô hình
def khoa_cua(model: str, profile: str, pv: str) -> str:
    s = f"{model or 'may'}__{profile or 'profile'}__{pv or 'pv'}"
    return re.sub(r"[^\w.\-]+", "_", s, flags=re.UNICODE)[:120]


def thu_muc() -> Path:
    import duong_dan as dd
    return dd.goc_du_lieu() / "mo_hinh_lr"


def luu(mh: MoHinh, mau: list | None = None) -> Path:
    d = thu_muc()
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{mh.khoa}.json"
    import duong_dan as dd
    dd.ghi_ben(f, json.dumps(mh.thanh_dict(), ensure_ascii=False))
    if mau:
        np.savez_compressed(d / f"{mh.khoa}_mau.npz", **{
            f"{i}__{t}": a["mau"]["px"][t] for i, a in enumerate(mau) for t in a["mau"]["px"]},
            **{f"{i}__loai": a["mau"]["loai"] for i, a in enumerate(mau)})
        (d / f"{mh.khoa}_st.json").write_text(json.dumps([a["st"] for a in mau], ensure_ascii=False,
                                                         default=str), encoding="utf-8")
    return f


def nap(khoa: str) -> MoHinh | None:
    try:
        return MoHinh.tu_dict(json.loads((thu_muc() / f"{khoa}.json").read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def nap_mau(khoa: str) -> list:
    """Mẫu đã lưu -> danh sách anh cho khop() (học lại không cần Lightroom)."""
    d = thu_muc()
    try:
        z = np.load(d / f"{khoa}_mau.npz")
        st = json.loads((d / f"{khoa}_st.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for i, s in enumerate(st):
        px = {k.split("__", 1)[1]: z[k] for k in z.files if k.startswith(f"{i}__") and not k.endswith("__loai")}
        if f"{i}__loai" in z.files:
            out.append({"mau": loc_da({"px": px, "loai": z[f"{i}__loai"]}), "st": s})
    #  ảnh không còn đủ điểm da hợp lệ: bỏ (như hoc() khi học từ ảnh dựng)
    return [a for a in out if int((np.asarray(a["mau"]["loai"]) == 0).sum()) >= 100]
