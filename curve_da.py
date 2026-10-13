"""Curve điểm cho DA MẶT và VÙNG CHÁY, đo trên ảnh Lightroom dựng thật — 13/10.

User 13/10: "cân chỉnh màu da so với màu đích trên từng pixel đo được của da… tách
mask da mặt… sau khi cân WB, Tone xong, đo lại da rồi can thiệp các kênh của Curve
cho da mặt đúng màu đích. Nhận biết vùng highlight; WB + Tone xong mà vẫn cháy thì
can thiệp Curve". Chốt với user: đo trên ảnh LIGHTROOM DỰNG (không mô phỏng), vùng
cháy = NÉN ĐỈNH curve tổng (giữ da + trung tông), mặc định TẮT.

Đây là LƯỢT 2 của "Xử lý ảnh": lượt 1 (WB / Tone / HSL / CG) đã vào catalog → plugin
dựng JPEG 1600 px (yeu_cau_dung) → do_anh() mỗi ảnh → ket_thuc(): giải, gom loạt,
ghép vào curve MỐC → ghi_job() job "@curve".

#[[ PHÉP ĐO DA (13/10). Mọi đích da (mẫu màu da của user — mau_da_tu_anh; đích mặc
#   định) đặt trên phép đo "lõi ô mặt + skin_mask + dải sáng p30–p90" (chon_da_hop).
#   Nên sai lệch tới đích đo bằng CHÍNH phép đo đó trên các mặt mask_da tìm được;
#   mặt nạ phân vùng (mat_na_da) quyết DẢI curve cần chỉnh, loại da khỏi vùng trung
#   tính, và là phép đo chính khi mẫu màu da có số đo cùng kiểu (khoá "*_mn").
#
#   GIẢI. Mỗi kênh c: g_c(y) = y + Δ_c·w_c(y), w_c = 1 trên [p10 − 0.02, p90 + 0.02]
#   giá trị da của kênh đó, chân nửa-cosin. Gauss–Newton 3 vòng tìm Δ_R,G,B để
#   (L, a, b) OkLab của TRUNG BÌNH da sau g = (L cũ, đích) — áp g lên TỪNG điểm da
#   rồi mới lấy trung bình, không dời một con số trung bình. Kẹp |Δ| ≤ curve_da_tran
#   (curve vẫn đơn điệu); không tới đích thì áp phần đã kẹp (cùng luật chuỗi màu da
#   13/10: "không tới được thì vẫn áp phần làm da gần đích hơn").
#
#   CHẶN TRẮNG. Curve kênh đổi MỌI điểm ảnh cùng mức sáng với da, kể cả tường trắng /
#   áo xám. Vùng trung tính bị dải chạm tới ≥ 0.5% khung mà dự đoán lệch ab >
#   curve_da_trang_max (0.003 = trang_tran_cg, dưới wb_xet_lai_nguong 0.004) thì thu
#   Δ lại. Không thì curve tạo ám mà bước xét lại WB coi là đáng sửa → hai bước giằng
#   nhau mỗi lần chạy lại.
#
#   NÉN CHÁY. Khung cháy (kênh lớn nhất ≥ 250, mở hình thái 5×5 bỏ đốm bóng) ≥ 2% thì
#   h(x) = x − d·((x − k)/(1 − k))² trên curve tổng: ĐỒNG NHẤT dưới knee k = max(0.80,
#   p95 da + 0.03) nên da / trung tông đứng yên; đỉnh 255 xuống 255 − d (d ≤ 20, đỉnh
#   ≥ 235). Chỗ cháy hẳn trong RAW thành xám phẳng — user đã nghe và chọn cách này.
#   (Lần trước hạ Exposure theo độ cháy — hl_thu_hoi — trượt cổng B 32.65%: user giữ
#   nguyên 234/265 khung cháy ≥ 30%. Cách này không đụng Exposure.)
#
#   GOM LOẠT (chia_loat thật): cả loạt một Δ (trung vị tấm có da), tấm không da theo
#   loạt; nén cháy khi đa số loạt cháy. Ảnh không mặt ngoài loạt: không curve kênh. ]]
"""
from __future__ import annotations

import csv
import io
import math
import os
from datetime import datetime
from pathlib import Path

import numpy as np

import autotone as at
import curve_lr as cl
import mat_na_da as mn

#: tối đa số điểm ảnh giữ lại cho mỗi tập (da, trung tính, mẫu khung)
TOI_DA_DIEM = 20_000
TOI_DA_KHUNG = 60_000
BO_TRUNG_TINH = (0.30, 0.96, 0.025)     # L thấp, L cao, chroma tối đa
CHAM_TRANG = 0.25                       # trọng số dải ≥ này = điểm trung tính "bị chạm"
NGUONG_CHAY = 250

TEN_YEU_CAU = "request_do_curve.txt"
TEN_TIEN_DO = "do_curve_tiendo.txt"
TEN_BANG = "do_curve_anh.tsv"
TEN_CO_DUNG = "request_do_curve_dung.txt"
KHA_NANG = "curve1"


def _f(cfg: dict, k: str) -> float:
    v = cfg.get(k)
    return float(at.DEFAULTS[k] if v is None else v)


def _mau(a: np.ndarray, n: int, seed: int = 0) -> np.ndarray:
    if a.shape[0] <= n:
        return a
    idx = np.random.default_rng(seed).choice(a.shape[0], n, replace=False)
    return a[np.sort(idx)]


def _lab_px(lin: np.ndarray) -> np.ndarray:
    lms = np.cbrt(np.maximum(np.asarray(lin, dtype=np.float64) @ at._OK_M1.T, 0.0))  # noqa: SLF001
    return lms @ at._OK_M2.T                                                          # noqa: SLF001


def thong_ke(px_mien: np.ndarray, mien: str) -> np.ndarray:
    """(L, a, b) OkLab của trung bình TUYẾN TÍNH các điểm da (giá trị miền curve)."""
    lin = cl.mien_sang_tuyen_tinh(px_mien, mien).mean(axis=0)
    return np.asarray(at.oklab(lin), dtype=np.float64)


def hue_q(lab) -> tuple[float, float]:
    return (float(math.degrees(math.atan2(lab[2], lab[1]))),
            float(math.hypot(lab[1], lab[2]) / max(float(lab[0]), 1e-6)))


def _goc(d: float) -> float:
    return (d + 180.0) % 360.0 - 180.0


# ------------------------------------------------------------------- đo

def do_anh(r: dict | None, anh, cfg: dict) -> dict:
    """Đo một ảnh Lightroom dựng (JPEG sRGB). -> dict (xem cuối hàm); "ok": False khi
    không đọc được."""
    import cv2
    from PIL import Image
    mien = str(cfg.get("curve_mien") or at.DEFAULTS["curve_mien"])
    try:
        with Image.open(anh) as im:
            img = np.asarray(im.convert("RGB"))
    except (OSError, ValueError) as e:
        return {"ok": False, "ly_do": f"không đọc được ảnh dựng ({e})"}
    H, W = img.shape[:2]
    arr = img.astype(np.float32) / 255.0
    #  mặt nạ da cần cho CẢ hai việc: curve da (đo da) và nén cháy (knee trên mức da)
    m = mn.mat_na(img, r)
    out = {"ok": True, "wh": (W, H), "mien": mien, "mat_na": m["kieu"], "n_da": m["n"],
           "mat": m["mat"], "crop": m["crop"], "ly_do": m["ly_do"]}
    if m["n"]:
        out["da_mn"] = cl.srgb_sang_mien(_mau(arr[m["da"]], TOI_DA_DIEM), mien)
    cu = [at.chon_da_hop(arr, b) for b in m["mat"]]
    cu = [c for c in cu if c is not None and len(c)]
    if cu:
        out["da_cu"] = cl.tuyen_tinh_sang_mien(_mau(np.vstack(cu), TOI_DA_DIEM), mien)
    #  vùng trung tính: lưới thưa (~240k điểm), bỏ da và ô mặt nới rộng
    buoc = max(1, int(math.sqrt(H * W / 240_000)))
    sub = arr[::buoc, ::buoc]
    trong_mat = np.zeros(sub.shape[:2], bool)
    for x, y, w, h in m["mat"]:
        x0, y0 = int(max(0, (x - 0.3 * w) / buoc)), int(max(0, (y - 0.3 * h) / buoc))
        x1, y1 = int((x + 1.3 * w) / buoc) + 1, int((y + 1.3 * h) / buoc) + 1
        trong_mat[y0:y1, x0:x1] = True
    px = sub.reshape(-1, 3)
    lab = _lab_px(at.srgb_to_linear(px))
    lo, hi, cmax = BO_TRUNG_TINH
    tt = ((lab[:, 0] >= lo) & (lab[:, 0] <= hi) & (np.hypot(lab[:, 1], lab[:, 2]) < cmax)
          & ~at.skin_mask(px) & ~trong_mat.reshape(-1))
    out["trung_ti_le"] = float(tt.mean())
    if tt.any():
        out["trung"] = cl.srgb_sang_mien(_mau(px[tt], TOI_DA_DIEM, 1), mien)
    #  vùng cháy: kênh lớn nhất ≥ 250, mở 5×5 bỏ đốm bóng / phản quang
    chay = (img.max(axis=2) >= NGUONG_CHAY).astype(np.uint8)
    mo = cv2.morphologyEx(chay, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    out["chay_pct"] = round(100.0 * float(mo.mean()), 3)
    out["chay_tho_pct"] = round(100.0 * float(chay.mean()), 3)
    out["khung"] = cl.srgb_sang_mien(_mau(px, TOI_DA_KHUNG, 2), mien)
    #  da sáng tới đâu (cho knee nén cháy): đo trên mặt nạ CHƯA bỏ điểm bóng — da cháy
    #  hẳn thì mặt nạ đã lọc rỗng mà vẫn phải biết là da đang ở đỉnh
    tho = m.get("da_tho")
    if tho is not None and int(tho.sum()) >= 50:
        ref = cl.srgb_sang_mien(_mau(arr[tho], TOI_DA_DIEM, 3), mien)
    else:
        ref = out.get("da_mn") if out.get("da_mn") is not None else out.get("da_cu")
    out["p95_da"] = float(np.percentile(ref.max(axis=1), 95)) if ref is not None else None
    return out


def da_mau_mn(anh, r: dict | None) -> np.ndarray | None:
    """RGB TUYẾN TÍNH trung bình da (mặt nạ PHÂN VÙNG) của một ảnh đã hoàn thiện — để
    mau_da_tu_anh lưu đích cùng phép đo với ảnh Lightroom dựng ("*_mn"). None khi không
    có mô hình phân vùng / không thấy da."""
    from PIL import Image
    if not mn.trang_thai()["co"]:
        return None
    try:
        with Image.open(anh) as im:
            im.draft("RGB", (2048, 2048))
            img = np.asarray(im.convert("RGB"))
    except (OSError, ValueError):
        return None
    m = mn.mat_na(img, r)
    if m["kieu"] != "parse" or not m["n"]:
        return None
    px = img[m["da"]].astype(np.float32) / 255.0
    return at.srgb_to_linear(_mau(px, TOI_DA_DIEM)).mean(axis=0)


# ------------------------------------------------------------------- giải

def dich_cua(r: dict, cfg: dict, kieu: str) -> tuple:
    """(rgb đích sRGB 0–255, trong / ngoài) — đích CUỐI của chuỗi màu da
    (dich_da_cuoi), chọn trong / ngoài như chuoi_mau_da_mau. kieu "mn": mẫu màu da
    có số đo bằng mặt nạ phân vùng thì dùng số đó."""
    ngoai = bool(at._nhan_da_ngoai(r, cfg))                    # noqa: SLF001
    trong_t, ngoai_t = at.dich_da_cuoi(cfg)
    rgb = ngoai_t if ngoai else trong_t
    md = cfg.get("mau_da_dich") or {}
    if kieu == "mn":
        k = "ngoai_mn" if ngoai else "trong_mn"
        rgb = md.get(k) or md.get("trong_mn") or rgb
    return list(rgb), ngoai


def _ap_g(P, delta, ws):
    out = np.array(P, dtype=np.float64, copy=True)
    for i in range(3):
        if delta[i]:
            out[:, i] = out[:, i] + delta[i] * ws[i](P[:, i])
    return np.clip(out, 0.0, 1.0)


def _bpt_hop(J, c, tran: float) -> np.ndarray:
    """min ‖J·D + c‖ với |D_i| ≤ tran — ba ẩn nên duyệt đủ 27 cách (mỗi ẩn: tự do /
    kẹp dưới / kẹp trên), lấy nghiệm hợp lệ dư nhỏ nhất.

    #[[ 13/10: kẹp SAU khi giải (np.clip bước Gauss–Newton) đã thử trên ảnh mẫu da rất
    #   đỏ: cả ba kênh chạm trần, chroma về gần đích nhưng hue trôi XA đích 5° (23.7° →
    #   28.9°, đích 16.6°). Giải đúng bài toán có ràng buộc thì phần được phép chỉnh
    #   dồn vào đúng hướng. ]]"""
    import itertools
    tot, du_tot = np.zeros(3), float("inf")
    for trang_thai in itertools.product((0, -1, 1), repeat=3):
        D = np.array([tran * t for t in trang_thai], dtype=np.float64)
        tu_do = [i for i, t in enumerate(trang_thai) if t == 0]
        if tu_do:
            A = J[:, tu_do]
            b = -(c + J @ D)
            try:
                D[tu_do] = np.linalg.lstsq(A, b, rcond=None)[0]
            except np.linalg.LinAlgError:
                continue
            if np.any(np.abs(D[tu_do]) > tran + 1e-12):
                continue
        du = float(np.linalg.norm(J @ D + c))
        if du < du_tot - 1e-15:
            tot, du_tot = D, du
    return tot


def he_so_trang(do: dict, D, ws, cfg: dict) -> tuple[float, float]:
    """(hệ số thu Δ ≤ 1, lệch ab dự đoán SAU khi thu) để vùng trung tính dải da chạm
    tới không ám quá curve_da_trang_max. Vùng chạm tới < curve_da_trang_dien_tich
    khung thì không xét (1.0, 0.0)."""
    N = do.get("trung")
    D = np.asarray(D, dtype=np.float64)
    if N is None or not len(N) or not np.any(D):
        return 1.0, 0.0
    mien = do.get("mien") or "melissa"
    wN = np.max(np.stack([ws[i](N[:, i]) for i in range(3)], axis=1), axis=1)
    cham = wN > CHAM_TRANG
    if float(do.get("trung_ti_le", 0.0)) * float(cham.mean()) < _f(cfg, "curve_da_trang_dien_tich"):
        return 1.0, 0.0
    Nc = N[cham]
    lab_n = _lab_px(cl.mien_sang_tuyen_tinh(Nc, mien))
    tmax = _f(cfg, "curve_da_trang_max")
    thu, lech = 1.0, 0.0
    for _ in range(3):                                   # lệch ~ tuyến tính theo Δ
        lab_m = _lab_px(cl.mien_sang_tuyen_tinh(_ap_g(Nc, D * thu, ws), mien))
        lech = float(math.hypot(np.median(lab_m[:, 1] - lab_n[:, 1]),
                                np.median(lab_m[:, 2] - lab_n[:, 2])))
        if lech <= tmax * 1.001:
            break
        thu *= tmax / lech
    return thu, lech


def giai_da(do: dict, r: dict, cfg: dict, tran_tren: float = 0.96) -> dict:
    """Δ_R,G,B (thang 0..1) đưa da tới đích. tran_tren: mép trên dải (dưới knee nén
    cháy − 0.04 khi có nén). -> {"delta", "dai", "h0", "q0", "h_t", "q_t", "h1", "q1",
    "kieu", "trang_lech", "thu", "ly_do"}."""
    mien = do.get("mien") or "melissa"
    #  mẫu màu da có số đo bằng mặt nạ PHÂN VÙNG và ảnh này cũng đo bằng phân vùng
    #  -> cùng một phép đo; còn lại dùng phép đo cũ (chon_da_hop) như mọi đích da
    kieu = "mn" if (((cfg.get("mau_da_dich") or {}).get("trong_mn"))
                    and do.get("da_mn") is not None and do.get("mat_na") == "parse") else "cu"
    P = do.get("da_mn") if kieu == "mn" else do.get("da_cu")
    if P is None or len(P) < 50:
        return {"delta": [0.0, 0.0, 0.0], "ly_do": "khong-thay-da"}
    rgb, ngoai = dich_cua(r, cfg, kieu)
    lt = at.mau_dich_lab(rgb)
    h_t, q_t = hue_q(lt)
    lab0 = thong_ke(P, mien)
    h0, q0 = hue_q(lab0)
    out = {"delta": [0.0, 0.0, 0.0], "h0": h0, "q0": q0, "h_t": h_t, "q_t": q_t,
           "h1": h0, "q1": q0, "kieu": kieu, "ngoai": ngoai, "trang_lech": 0.0, "thu": 1.0,
           "ly_do": ""}
    on_h, on_c = _f(cfg, "da_on_hue"), _f(cfg, "da_on_chroma")
    if abs(_goc(h_t - h0)) <= on_h and abs(q0 / max(q_t, 1e-9) - 1.0) <= on_c:
        out["ly_do"] = "da-on"
        return out
    B = do.get("da_mn") if do.get("da_mn") is not None else P
    chan, tran = _f(cfg, "curve_da_chan"), _f(cfg, "curve_da_tran")
    dai, ws = [], []
    for i in range(3):
        a, b = float(np.percentile(B[:, i], 10)) - 0.02, float(np.percentile(B[:, i], 90)) + 0.02
        dai.append((a, b))
        ws.append(cl.bump(a, b, chan, 0.06, tran_tren))
    out["dai"] = dai
    L0 = float(lab0[0])
    lq_on = math.log(1.0 + on_c)

    def sai(D, wh, wq):
        """Sai lệch theo ĐƠN VỊ vùng ổn: L giữ (0.01 = 1 đơn vị), hue theo da_on_hue,
        ln(chroma) theo ln(1 + da_on_chroma)."""
        lab = thong_ke(_ap_g(P, D, ws), mien)
        h, q = hue_q(lab)
        return np.array([(float(lab[0]) - L0) / 0.01, wh * _goc(h - h_t) / on_h,
                         wq * math.log(max(q, 1e-9) / q_t) / lq_on])

    #[[ KHÔNG ĐỔI XẤU MỘT CHIỀU ĐỂ ĐỔI TỐT CHIỀU KIA (13/10). Ảnh mẫu da rất đỏ (q gấp
    #   2.5 đích, cả ba kênh chạm trần): nghiệm "gần nhất" kéo chroma về mà đẩy hue xa
    #   đích thêm 5°. Luật chuỗi màu da 13/10 là "vẫn áp phần làm da GẦN đích hơn" —
    #   nên hue (hoặc chroma) xấu đi quá vùng ổn thì giải lại, nặng gấp 10 chiều đó. ]]
    dh0, lq0 = abs(_goc(h0 - h_t)), abs(math.log(max(q0, 1e-9) / q_t))
    wh = wq = 1.0
    D = np.zeros(3)
    for _vong in range(4):
        D = np.zeros(3)
        for _ in range(3):
            e = sai(D, wh, wq)
            J = np.zeros((3, 3))
            for j in range(3):
                Dj = D.copy()
                Dj[j] += 0.002
                J[:, j] = (sai(Dj, wh, wq) - e) / 0.002
            D = _bpt_hop(J, e - J @ D, tran)
        h1, q1 = hue_q(thong_ke(_ap_g(P, D, ws), mien))
        xau_h = abs(_goc(h1 - h_t)) > max(dh0, on_h) + 1e-6
        xau_q = abs(math.log(max(q1, 1e-9) / q_t)) > max(lq0, lq_on) + 1e-6
        if not xau_h and not xau_q:
            break
        wh *= 10.0 if xau_h else 1.0
        wq *= 10.0 if xau_q else 1.0
    else:
        D = np.zeros(3)
        out["ly_do"] = "khong-giai-duoc"
    #  chặn trắng: vùng trung tính dải chạm tới không được ám quá curve_da_trang_max
    thu, lech = he_so_trang(do, D, ws, cfg)
    D = D * thu
    out["thu"], out["trang_lech"] = thu, lech
    out["delta"] = [float(v) for v in D]
    out["h1"], out["q1"] = hue_q(thong_ke(_ap_g(P, D, ws), mien))
    return out


def tinh_chinh_nut(P, moc: dict, moi: dict, lab_y, mien: str, kieu_tong: str,
                   vung: dict, vong: int = 3) -> dict:
    """Curve kênh đã ghép (nút y số NGUYÊN — Lightroom lưu 0..255) lệch g ý định ~0.5–1
    mã cùng một chiều cả dải -> da lệch dự đoán ~0.8° (đo 13/10 trên ảnh giả). Dò từng
    nút TRONG dải da ± 1 mã, giữ thay đổi nào đưa THỐNG KÊ DA của curve thật (ap_mien)
    gần thống kê ý định `lab_y` hơn. vung: {kênh: (lo, hi) miền ra 0..1}."""
    P = _mau(np.asarray(P, dtype=np.float64), 4000, 5)

    def sai(m):
        lab = thong_ke(cl.ap_mien(P, moc, m, kieu_tong), mien)
        return (((lab[0] - lab_y[0]) / 0.01) ** 2 + ((lab[1] - lab_y[1]) / 0.002) ** 2
                + ((lab[2] - lab_y[2]) / 0.002) ** 2)
    moi = {k: list(v) for k, v in moi.items()}
    tot = sai(moi)
    luoi = np.linspace(0.0, 255.0, 511)
    for _ in range(vong):
        doi = False
        for c, (lo, hi) in vung.items():
            d = moi[c]
            for i in range(1, len(d) - 1):
                if not lo * 255 - 2 <= d[i][1] <= hi * 255 + 2:
                    continue
                for buoc in (-1.0, 1.0):
                    y = d[i][1] + buoc
                    if not d[i - 1][1] <= y <= d[i + 1][1]:
                        continue
                    thu = dict(moi)
                    thu[c] = d[:i] + [(d[i][0], y)] + d[i + 1:]
                    s = sai(thu)
                    if s < tot - 1e-9 and np.all(np.diff(cl.spline(thu[c])(luoi)) >= -1e-6):
                        moi, tot, doi, d = thu, s, True, thu[c]
        if not doi:
            break
    return moi


def giai_chay(do: dict, cfg: dict) -> dict:
    """Nén đỉnh curve tổng. -> {"k", "d", "chay_pct", "ly_do"} (d = 0: không nén)."""
    pct = float(do.get("chay_pct") or 0.0)
    out = {"k": None, "d": 0.0, "chay_pct": pct, "ly_do": ""}
    if pct < _f(cfg, "curve_chay_nguong"):
        out["ly_do"] = "khong-chay"
        return out
    p95 = do.get("p95_da")
    k = max(_f(cfg, "curve_chay_knee"), (p95 + 0.03) if p95 is not None else 0.0)
    if k > _f(cfg, "curve_chay_knee_max"):
        out["ly_do"] = "da-sang"
        return out
    d = min(_f(cfg, "curve_chay_d_max"), 8.0 + 0.4 * (pct - 2.0), 0.45 * (1.0 - k) * 255.0,
            255.0 - _f(cfg, "curve_chay_san"))
    out.update(k=float(k), d=float(max(0.0, d)))
    return out


# ------------------------------------------------------------------- gom + curve

def _curve_moc(r: dict) -> dict:
    moc = r.get("curve_moc") or {}
    return {c: (cl.doc_o(moc.get(k)) or list(cl.DONG_NHAT)) for c, k in cl.KHOA.items()}


def du_dieu_kien(r: dict) -> str:
    """"" = ảnh được làm curve; ngược lại là lý do bỏ."""
    if r.get("bw"):
        return "den-trang"
    if r.get("ngoai_xuat") or not r.get("ok", True):
        return "khong-co-trong-catalog"
    if int(r.get("rating") or 0) == 1:
        return "1-sao"
    tt = r.get("curve_tt")
    if tt == "nguoi_sua":
        return "nguoi-sua-curve"
    if tt == "mat_goc":
        return "mat-curve-goc"
    if tt in (None, "khong_ro") or not at.co_cot_curve(r.get("curve_moc") or {}):
        return "plugin-cu"
    return ""


def chon_anh(items: list, cfg: dict) -> list:
    """Ảnh cần dựng ở lượt 2. Chỉ bật curve da: ảnh có mặt (hoặc cùng loạt với ảnh có
    mặt — tấm không mặt trong loạt theo loạt)."""
    ds = [r for r in items if not du_dieu_kien(r)]
    if cfg.get("curve_chay"):
        return ds
    co_mat = {id(r) for r in ds if r.get("meter_boxes")}
    for loat in at.chia_loat(ds, cfg) if ds else []:
        if any(id(r) in co_mat for r in loat):
            co_mat |= {id(r) for r in loat}
    return [r for r in ds if id(r) in co_mat]


def ket_thuc(items: list, do_map: dict, cfg: dict) -> dict:
    """Giải + gom loạt + ghép curve cho các ảnh đã đo (do_map: id(r) -> do_anh()).
    Ghi r["curve_ghi"] = {khoá Lightroom: ô} (chỉ khi có đổi) và r["curve_bao"].
    -> tóm tắt."""
    bat_da, bat_chay = bool(cfg.get("curve_da")), bool(cfg.get("curve_chay"))
    mien = str(cfg.get("curve_mien") or at.DEFAULTS["curve_mien"])
    kieu_tong = str(cfg.get("curve_kieu_tong") or at.DEFAULTS["curve_kieu_tong"])
    ds = [r for r in items if id(r) in do_map and do_map[id(r)].get("ok")]
    for r in items:
        r.pop("curve_ghi", None)
        r.pop("curve_bao", None)
    chay = {id(r): giai_chay(do_map[id(r)], cfg) if bat_chay else {"d": 0.0, "ly_do": "tat"}
            for r in ds}
    #  nén cháy theo loạt: đa số loạt cháy -> cả loạt, knee lớn nhất, d trung vị
    loats = at.chia_loat(ds, cfg) if ds else []
    for loat in loats:
        kq = [chay[id(r)] for r in loat]
        co = [c for c in kq if c.get("d", 0) > 0]
        if bat_chay and len(co) * 2 > len(kq):
            k, d = max(c["k"] for c in co), float(np.median([c["d"] for c in co]))
            d = min(d, 0.45 * (1.0 - k) * 255.0)
            for r in loat:
                chay[id(r)] = dict(chay[id(r)], k=k, d=d, ly_do="theo-loat")
        elif bat_chay:
            for r in loat:
                chay[id(r)] = dict(chay[id(r)], d=0.0, ly_do="loat-khong-chay")
    da = {}
    for r in ds:
        c = chay[id(r)]
        tran_tren = (c["k"] - 0.04) if c.get("d", 0) > 0 else 0.96
        da[id(r)] = (giai_da(do_map[id(r)], r, cfg, tran_tren) if bat_da
                     else {"delta": [0.0, 0.0, 0.0], "ly_do": "tat"})
    #  curve kênh theo loạt: trung vị Δ của tấm có da, tấm không da theo loạt; chặn
    #  trắng lấy hệ số NHỎ NHẤT qua cả loạt (một loạt một curve)
    for loat in loats:
        co = [r for r in loat if "dai" in da[id(r)] or da[id(r)].get("ly_do") == "da-on"]
        if not bat_da or not co:
            continue
        D = np.median(np.array([da[id(r)]["delta"] for r in co]), axis=0)
        co_dai = [da[id(r)] for r in co if "dai" in da[id(r)]]
        dai = ([(float(np.median([g["dai"][i][0] for g in co_dai])),
                 float(np.median([g["dai"][i][1] for g in co_dai]))) for i in range(3)]
               if co_dai else None)
        thu = 1.0
        if dai is not None and np.any(D):
            for r in loat:
                c = chay[id(r)]
                tt = (c["k"] - 0.04) if c.get("d", 0) > 0 else 0.96
                ws = [cl.bump(a, b, _f(cfg, "curve_da_chan"), 0.06, tt) for a, b in dai]
                thu = min(thu, he_so_trang(do_map[id(r)], D * thu, ws, cfg)[0] * thu)
        for r in loat:
            g = dict(da[id(r)])
            g["delta"] = [float(v) * thu for v in D]
            if dai is not None:
                g["dai"] = dai
            g["thu"] = min(float(g.get("thu", 1.0)), thu)
            g["loat"] = len(loat)
            da[id(r)] = g
    #  loạt: tinh chỉnh nút MỘT lần trên da gộp của cả loạt -> cả loạt cùng một curve
    loat_cua = {id(r): i for i, loat in enumerate(loats) for r in loat}
    da_loat: dict = {}
    for r in ds:
        i = loat_cua.get(id(r))
        g, do = da[id(r)], do_map[id(r)]
        P = do.get("da_mn") if g.get("kieu") == "mn" else do.get("da_cu")
        if i is not None and P is not None and len(P) >= 50 and "h0" in g:
            da_loat.setdefault(i, []).append(_mau(P, 3000, 7))
    tinh_san: dict = {}
    n_da = n_chay = 0
    for r in ds:
        g, c, do = da[id(r)], chay[id(r)], do_map[id(r)]
        moc = _curve_moc(r)
        moi = dict(moc)
        tran_tren = (c["k"] - 0.04) if c.get("d", 0) > 0 else 0.96
        doi = False
        if c.get("d", 0) > 0:
            moi["master"] = cl.ghep(cl.h_chay(c["k"], c["d"]), moc["master"])
            doi = True
        if any(abs(v) * 255 >= 0.5 for v in g["delta"]) and g.get("dai"):
            ws, vung = [], {}
            for i, ch in enumerate(cl.KENH):
                a, b = g["dai"][i]
                ws.append(cl.bump(a, b, _f(cfg, "curve_da_chan"), 0.06, tran_tren))
                if abs(g["delta"][i]) * 255 >= 0.5:
                    moi[ch] = cl.ghep(cl.g_da(g["delta"][i], ws[i]), moc[ch])
                    vung[ch] = (a - _f(cfg, "curve_da_chan"), b + _f(cfg, "curve_da_chan"))
                    doi = True
            #  nút số nguyên -> tinh chỉnh theo thống kê da (ảnh lẻ: da của ảnh; loạt:
            #  da gộp cả loạt, làm một lần cho mỗi curve mốc — cả loạt cùng một curve)
            i = loat_cua.get(id(r))
            P = (np.vstack(da_loat[i]) if i in da_loat else
                 (do.get("da_mn") if g.get("kieu") == "mn" else do.get("da_cu")))
            khoa = (i, tuple(sorted((r.get("curve_moc") or {}).items()))) if i is not None else None
            if khoa is not None and khoa in tinh_san:
                moi = dict(moi, **tinh_san[khoa])
            elif vung and P is not None and len(P) >= 50:
                lab_y = thong_ke(_ap_g(P, np.asarray(g["delta"]), ws), mien)
                moi = tinh_chinh_nut(P, moc, moi, lab_y, mien, kieu_tong, vung)
                if khoa is not None:
                    tinh_san[khoa] = {c: moi[c] for c in vung}
        bao = {"mat_na": do.get("mat_na"), "n_da": do.get("n_da", 0), "crop": do.get("crop"),
               "delta_ma": [round(v * 255, 1) for v in g.get("delta", [0, 0, 0])],
               "da": {k: (round(v, 3) if isinstance(v, float) else v)
                      for k, v in g.items() if k in ("h0", "q0", "h_t", "q_t", "h1", "q1",
                                                     "trang_lech", "thu", "kieu", "ly_do",
                                                     "loat")},
               "chay": {"truoc": c.get("chay_pct", do.get("chay_pct")), "k": c.get("k"),
                        "d": round(float(c.get("d") or 0.0), 1), "ly_do": c.get("ly_do", "")}}
        if doi:
            #  dự đoán bằng curve THẬT vừa ghép (không bằng g / h ý định)
            P = do.get("da_mn") if g.get("kieu") == "mn" else do.get("da_cu")
            if P is not None and len(P) and "h0" in g:
                h1, q1 = hue_q(thong_ke(cl.ap_mien(P, moc, moi, kieu_tong), mien))
                bao["da"]["h1"], bao["da"]["q1"] = round(h1, 2), round(q1, 4)
            K = do.get("khung")
            if K is not None and c.get("d", 0) > 0:
                sau = cl.mien_sang_srgb(cl.ap_mien(K, moc, moi, kieu_tong), mien)
                bao["chay"]["sau"] = round(100.0 * float((sau.max(axis=1) * 255 >= NGUONG_CHAY
                                                          ).mean()), 3)
            r["curve_ghi"] = {cl.KHOA_TEN: "Custom",
                              **{k: cl.ghi_o(moi[c_]) for c_, k in cl.KHOA.items()}}
            n_da += int(any(abs(v) * 255 >= 0.5 for v in g.get("delta", [0, 0, 0])))
            n_chay += int(c.get("d", 0) > 0)
        r["curve_bao"] = bao
    return {"do": len(ds), "doi": sum(1 for r in ds if r.get("curve_ghi")),
            "da": n_da, "chay": n_chay,
            "mat_na": {k: sum(1 for r in ds if do_map[id(r)].get("mat_na") == k)
                       for k in ("parse", "du_phong", "tron")},
            "khong_da": sum(1 for r in ds if da[id(r)].get("ly_do") == "khong-thay-da"),
            "da_on": sum(1 for r in ds if da[id(r)].get("ly_do") == "da-on"),
            "chan_trang": sum(1 for r in ds if da[id(r)].get("thu", 1.0) < 1.0)}


# ------------------------------------------------------------------- job + cầu nối

def ghi_job(items: list, name: str, job_dir: Path | None = None) -> Path | None:
    """Job lượt 2: chỉ cột curve, chỉ ảnh có đổi. Tên apply_<giờ>_<buổi>@curve.tsv."""
    rows = [[r.get("lr_path") or r["path"], *[str(r["curve_ghi"].get(k) or "")
                                             for k in at.COT_CURVE]]
            for r in items if r.get("curve_ghi")]
    if not rows:
        return None
    d = Path(job_dir or at.LR_JOB_DIR)
    d.mkdir(parents=True, exist_ok=True)
    dest = d / f"apply_{datetime.now():%Y%m%d_%H%M%S}_{at.ten_job(name)}{at.HAU_TO_CURVE}.tsv"
    lines = ["path\t" + "\t".join(at.COT_CURVE)] + ["\t".join(c) for c in rows]
    tmp = dest.with_suffix(".part")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, dest)
    return dest


#: khoá của r cần để đo LẠI một ảnh ở cổng (kiem_cong_curve) bằng chính do_anh / giai_da
KHOA_R_CONG = ("path", "lr_path", "meter_boxes", "preview_wh", "ngoai_troi", "ev100", "model",
               "scene", "curve_moc", "curve_tt", "rating", "bw", "dt_obj")


def luu_ket_qua(dest, ds: list, do_map: dict, bang: list, job) -> Path:
    """Giữ ảnh dựng lượt 2 + ket_qua.json (khi chạy CỔNG — AUTOTONE_CURVE_GIU_ANH=1 hoặc
    curve_giu_anh): kiem_cong_curve.py dựng lại sau job curve và so trước / sau."""
    import json
    jpg = {at.khoa_duong_dan(p): j for p, j in bang}
    out = []
    for r in ds:
        do = do_map.get(id(r)) or {}
        rec = {k: (str(r[k]) if k == "dt_obj" else r[k]) for k in KHOA_R_CONG if k in r}
        rec["jpg"] = jpg.get(at.khoa_duong_dan(r.get("lr_path") or r["path"]))
        rec["do"] = {k: do.get(k) for k in ("mat_na", "n_da", "chay_pct", "p95_da", "trung_ti_le")}
        rec["curve_bao"] = r.get("curve_bao")
        rec["curve_ghi"] = r.get("curve_ghi")
        out.append(rec)
    f = Path(dest) / "ket_qua.json"
    Path(dest).mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"job": str(job) if job else None, "anh": out}, ensure_ascii=False,
                            default=str, indent=1), encoding="utf-8")
    return f


def giu_anh(cfg: dict) -> bool:
    return bool(cfg.get("curve_giu_anh")) or os.environ.get("AUTOTONE_CURVE_GIU_ANH") == "1"


def thu_muc_dung(folder, ma: str) -> Path:
    """Nơi plugin đổ ảnh dựng lượt 2: <dữ liệu>/do_curve/<buổi>/<mã> — KHÔNG phải _duyet
    (chuỗi màu da đọc _duyet; ảnh lượt 2 không được lẫn vào đó)."""
    import duong_dan as dd
    return dd.goc_du_lieu() / "do_curve" / at.ten_job(Path(str(folder)).name) / ma


def yeu_cau_dung(folder, items: list, dest, ma: str, canh: int = 1600, chat: int = 80,
                 lo: int = 25, job_dir: Path | None = None) -> Path:
    """Nhờ plugin dựng ảnh lượt 2 cho ĐÚNG các ảnh `items` (dòng anh=)."""
    d = Path(job_dir or at.LR_JOB_DIR)
    d.mkdir(parents=True, exist_ok=True)
    for ten in (TEN_TIEN_DO, TEN_BANG, TEN_CO_DUNG):
        try:
            (d / ten).unlink()
        except OSError:
            pass
    Path(dest).mkdir(parents=True, exist_ok=True)
    body = [str(Path(str(folder))), f"dest={Path(dest)}", f"canh={int(canh)}",
            f"chat={int(chat)}", f"lo={int(lo)}", "bo_sao=1", f"ma={ma}"]
    body += [f"anh={r.get('lr_path') or r['path']}" for r in items]
    f = d / TEN_YEU_CAU
    tmp = d / (TEN_YEU_CAU + ".part")
    tmp.write_text("\n".join(body) + "\n", encoding="utf-8")
    os.replace(tmp, f)
    return f


def dang_cho(job_dir: Path | None = None) -> bool:
    return (Path(job_dir or at.LR_JOB_DIR) / TEN_YEU_CAU).exists()


def xin_dung(job_dir: Path | None = None) -> None:
    d = Path(job_dir or at.LR_JOB_DIR)
    d.mkdir(parents=True, exist_ok=True)
    (d / TEN_CO_DUNG).write_text("dung\n", encoding="utf-8")


def rut_yeu_cau(job_dir: Path | None = None) -> None:
    """Rút yêu cầu chưa ai nhận (plugin cũ / Lightroom tắt)."""
    try:
        (Path(job_dir or at.LR_JOB_DIR) / TEN_YEU_CAU).unlink()
    except OSError:
        pass


def tien_do(job_dir: Path | None = None) -> dict:
    """trang_thai (dang_chay/xong/loi/dung), xong, tong, loi, ma, thong_bao."""
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
    for k in ("xong", "tong", "loi"):
        try:
            out[k] = int(out[k])
        except (KeyError, ValueError):
            pass
    return out


def bang_anh(job_dir: Path | None = None) -> list[tuple[str, str]]:
    """(đường dẫn Lightroom, ảnh dựng) — plugin ghi lại sau MỖI lô."""
    try:
        lines = (Path(job_dir or at.LR_JOB_DIR) / TEN_BANG).read_text(
            encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    out = []
    for line in lines[1:]:
        v = line.split("\t")
        if len(v) >= 2 and v[0] and v[1]:
            out.append((v[0], v[1]))
    return out


def doc_job(p: Path) -> dict:
    """{khoá ảnh: dòng} của một job curve (để kiểm / cổng)."""
    out = {}
    with io.open(p, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if row.get("path"):
                out[at.khoa_duong_dan(row["path"])] = row
    return out
