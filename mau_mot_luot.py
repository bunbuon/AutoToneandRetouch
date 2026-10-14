# -*- coding: utf-8 -*-
"""mau_mot_luot.py — CHUỖI MÀU DA MỘT LƯỢT: Tone -> HSL -> Curve -> WB -> CG (14/10).

User 14/10: "Việc xử lý 1000 ảnh theo cách hiện tại thì thời gian phải tốn 15 phút. Như
này đang quá lâu. Hãy thử đổi lại Flow 1 chút. Với mỗi 1 ảnh cần lấy ra được vùng da mặt
và pixel vùng da đó để can thiệp xử lý ánh sáng và màu sắc cho giống với màu da đích …
Quy trình chỉnh Tone -> Color Mixer HSL -> Tone Curve -> WB -> CG". Chốt: "Một lượt, dự
đoán đã học".

Mỗi ảnh có mặt mang r["lr_truoc"] (do_truoc: da / vùng trắng / khung đo trên preview
Lightroom của trạng thái HIỆN TẠI, "cu") và một mô hình Lightroom ĐÃ ĐẠT kiểm định cho
máy / profile / process version của nó (mo_hinh_lr, học trên RAW thật). Mỗi bước dự đoán
điểm ảnh Lightroom sẽ dựng (MoHinh.ap(px, cu, mới)) rồi quyết theo đúng luật cũ:

  1. TONE  — decide() / compute_values như cũ (Exposure, HL/SH, WB cân theo da). HSL / CG /
             curve về số PRESET: da đo ở trạng thái đó.
  2. HSL   — một mức Cam mỗi cảnh, vùng ổn / trần / chặn vượt đích như chuoi_mau_da_mau;
             hệ số đổi hue / độ đậm lấy từ mô hình TẠI hue da của ảnh (không hằng số).
  3. CURVE — curve_da.giai_da + ket_thuc trên da dự đoán sau HSL, miền curve đã hiệu chỉnh;
             một curve mỗi loạt; ghi CÙNG job chính (r["curve_ghi_mot_luot"]).
  4. WB    — CHỈ vùng trắng (dự đoán sau Tone + HSL + Curve) so với vùng trắng của mẫu,
             trung vị cảnh, ngưỡng / phần / trần như wb_xet_lai; Jacobi từ mô hình.
             Không bao giờ giải WB theo da.
  5. CG    — phần da CÒN lệch sau WB, luật grade như cũ, kẹp trang_tran_cg.
  Cuối: r["du_doan_lr"] = da / vùng trắng dự đoán sau cả chuỗi — soát sau khi áp so với
  preview Lightroom thật (lệch nhiều -> lượt 2 chỉ cho ảnh đó).

Chọn đường THEO CẢNH (chon_duong): cảnh nào đa số ảnh có mặt có số đo trước + mô hình thì
cả cảnh đi chuỗi này (ảnh không đo nhận mức HSL / WB của cảnh, curve của loạt); cảnh khác
đi chuoi_mau_da_mau như cũ. Không có mô hình đạt = không dùng (KIEM_MOT_LUOT / HOC_MAU_LR).
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

import autotone as at
import curve_lr as cl

_MH: dict = {}


def bat(cfg: dict) -> bool:
    import os
    return bool(cfg.get("mau_mot_luot")) or os.environ.get("AUTOTONE_MOT_LUOT") == "1"


def cu_cua(r: dict) -> dict:
    """Thông số Lightroom lúc preview được dựng: bản xuất (crs_hien) + catalog (st, cùng
    lúc với preview — ưu tiên)."""
    return {**(r.get("crs_hien") or {}), **((r.get("lr_truoc") or {}).get("st") or {})}


def khoa_cua(r: dict) -> str:
    import mo_hinh_lr as mh
    cu = cu_cua(r)
    return mh.khoa_cua(str(r.get("model") or ""), str(cu.get("CameraProfile") or ""),
                       str(cu.get("ProcessVersion") or ""))


def mo_hinh_cho(r: dict):
    """Mô hình ĐẠT kiểm định cho ảnh này, None nếu chưa học / chưa đạt."""
    import mo_hinh_lr as mh
    k = khoa_cua(r)
    if k not in _MH:
        m = mh.nap(k)
        _MH[k] = m if (m is not None and m.dat) else None
    return _MH[k]


def quen_mo_hinh() -> None:
    _MH.clear()


def _co_mat(r: dict) -> bool:
    return bool(r.get("meter_boxes")) and not r.get("bw") and int(r.get("rating") or 0) != 1


def chon_duong(items: list, cfg: dict, ti_le: float = 0.5) -> tuple[list, list]:
    """(ảnh chuỗi một lượt, ảnh đường cũ) — theo CẢNH: cảnh đi một lượt khi ≥ ti_le số LOẠT
    có mặt của nó có ảnh đo được trên preview + mô hình đạt (14/10: đo trước chỉ lấy tối đa
    hai ảnh mỗi loạt — do_truoc.mau_loat — nên đếm theo loạt, không theo tấm)."""
    if not bat(cfg):
        return [], list(items)
    theo: dict = {}
    for r in items:
        theo.setdefault(r.get("scene"), []).append(r)
    moi, cu = [], []
    for ds in theo.values():
        mat = [r for r in ds if _co_mat(r)]
        loats = at.nhom_loat(mat, cfg) if mat else []
        ok = [g for g in loats if any(r.get("lr_truoc") and mo_hinh_cho(r) is not None for r in g)]
        if loats and len(ok) >= max(1, math.ceil(ti_le * len(loats))):
            moi += ds
        else:
            cu += ds
    return moi, cu


# ------------------------------------------------------------------ thông số
def _f(v, mac=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(mac)


def _wb_doi(r: dict) -> bool:
    """Job có ghi WB không — đúng điều kiện của write_lr_job."""
    return bool((not r.get("bw") and (r.get("new_temp") != r.get("old_temp")
                                      or r.get("new_tint") != r.get("old_tint")
                                      or bool(r.get("wb_ep_ghi")))) or r.get("bw_tra_wb"))


def _tone(r: dict, cu: dict) -> dict:
    s = dict(cu)
    s["Exposure2012"] = _f(r.get("new_exposure"), _f(cu.get("Exposure2012")))
    for k, rk in (("Highlights2012", "new_highlights"), ("Shadows2012", "new_shadows")):
        if r.get(rk) is not None:
            s[k] = _f(r[rk])
    for k in ("Contrast2012", "Whites2012", "Blacks2012"):
        if r.get("new_" + k) is not None:
            s[k] = _f(r["new_" + k])
    if r.get("new_temp") and _wb_doi(r):
        s.update(WhiteBalance="Custom", Temperature=_f(r["new_temp"]), Tint=_f(r.get("new_tint")))
    return s


def _lum_goc(r: dict, cu: dict) -> float | None:
    """Luminance Cam GỐC (preset) của ảnh: mốc nếu đã có; chưa có = tool chưa từng ghi ô này
    (COT_HSL_L, 14/10) -> số Lightroom đang có chính là số preset. None = không biết."""
    moc = (r.get("crs") or {}).get(at.COT_HSL_L[0])
    if str(moc if moc is not None else "").strip() != "":
        return _f(moc)
    v = (cu or {}).get(at.COT_HSL_L[0])
    if str(v if v is not None else "").strip() != "":
        return _f(v)
    #  thông số đọc thẳng catalog (lr_truoc["st"]) không có ô này = Lightroom để mặc định 0;
    #  chỉ có bản xuất plugin (không xuất ô này) thì không biết
    return 0.0 if (r.get("lr_truoc") or {}).get("st") else None


def thong_so_tone(r: dict, cu: dict) -> dict:
    """Thông số sau bước Tone (+ WB đã quyết). HSL về PRESET (chuỗi luôn ghi HSL kênh da);
    Color Grading về preset khi tool từng ghi (job trả lại), không thì giữ số đang có;
    curve về mốc khi Lightroom đang mang curve mốc / curve tool (curve_reset), curve người
    dùng tự sửa thì giữ."""
    s = _tone(r, cu)
    s.update(at._hsl_goc(r))                                     # noqa: SLF001
    lg = _lum_goc(r, cu)
    if lg is not None:
        s[at.COT_HSL_L[0]] = lg
    if r.get("da_grade"):
        s.update(at._grade_goc(r))                               # noqa: SLF001
    if r.get("curve_tt") in ("moc", "tool") or r.get("curve_reset"):
        for k in at.COT_CURVE:
            v = (r.get("curve_moc") or {}).get(k)
            if v not in (None, ""):
                s[k] = v
    return s


def thong_so_job(r: dict, cu: dict) -> dict:
    """Thông số Lightroom SAU KHI áp job chính — đúng như write_lr_job ghi: ô trống =
    Lightroom giữ số đang có (cu)."""
    s = _tone(r, cu)
    if r.get("hsl_ghi") and r.get("hsl_moi"):
        s.update({k: _f(v) for k, v in dict(r["hsl_moi"]).items()})
    if r.get("hsl_l_ghi") and r.get("hsl_l_moi"):
        s.update({k: _f(v) for k, v in dict(r["hsl_l_moi"]).items()})
    if r.get("gr_ghi") and r.get("gr_mid"):
        s["ColorGradeMidtoneHue"], s["ColorGradeMidtoneSat"] = r["gr_mid"]
    if r.get("gr_ghi") and r.get("gr_hi"):
        s["SplitToningHighlightHue"], s["SplitToningHighlightSaturation"] = r["gr_hi"]
    cv = r.get("curve_ghi_mot_luot") or (r.get("curve_reset") if at.co_cot_curve(r.get("curve_reset") or {})
                                         else None)
    if cv:
        s.update({k: v for k, v in cv.items() if v not in (None, "")})
    return s


def _ap_curve(s: dict, ghi: dict | None) -> dict:
    return dict(s, **ghi) if ghi else s


# ------------------------------------------------------------------ đo
def _srgb(P, mien):
    return cl.mien_sang_srgb(np.asarray(P, dtype=np.float64), mien) if P is not None and len(P) else None


#: điểm ảnh tối đa mỗi loại khi DỰ ĐOÁN (14/10: chuỗi 1.054 ảnh mất ~5 phút tính với đủ
#: 4.000 / 4.000 / 8.000 điểm; thống kê da / vùng trắng / % cháy không đổi đáng kể khi bớt)
SO_DIEM = {"da": 900, "trung": 1500, "khung": 3000}


def _bot(P, n: int):
    if P is None or len(P) <= n:
        return P
    return np.asarray(P)[np.linspace(0, len(P) - 1, n).round().astype(int)]


def mau_cua(r: dict, cfg: dict) -> dict | None:
    """Điểm ảnh sRGB của ảnh đo trước: da (đúng kiểu đo với đích), trung tính, khung."""
    import curve_da
    d = r.get("lr_truoc") or {}
    if not d.get("ok"):
        return None
    mien = d.get("mien") or "melissa"
    kieu = "mn" if (((cfg.get("mau_da_dich") or {}).get("trong_mn"))
                    and d.get("da_mn") is not None and d.get("mat_na") == "parse") else "cu"
    P = d.get("da_mn") if kieu == "mn" else d.get("da_cu")
    if P is None or len(P) < 50:
        return None
    rgb, ngoai = curve_da.dich_cua(r, cfg, kieu)
    lt = at.mau_dich_lab(rgb)
    return {"da": _srgb(_bot(P, SO_DIEM["da"]), mien), "trung": _srgb(_bot(d.get("trung"), SO_DIEM["trung"]), mien),
            "khung": _srgb(_bot(d.get("khung"), SO_DIEM["khung"]), mien),
            "kieu": kieu, "mien": mien, "ngoai": ngoai,
            "h_t": math.degrees(math.atan2(lt[2], lt[1])),
            "q_t": float(math.hypot(lt[1], lt[2])) / max(float(lt[0]), 1e-6),
            "L_t": float(lt[0]), "rgb_t": [int(v) for v in rgb]}


def rgb_pt(px_srgb, mien: str = "melissa") -> list | None:
    """R G B % (miền Lightroom hiện ở Develop — Melissa) của trung bình điểm da."""
    if px_srgb is None or not len(px_srgb):
        return None
    w = cl.srgb_sang_mien(np.asarray(px_srgb, dtype=np.float64), mien).mean(axis=0) * 100.0
    return [round(float(v), 1) for v in w]


def _da(px) -> tuple[float, float, float]:
    import mo_hinh_lr as mh
    return mh.thong_ke_da(px)


def _trang(px) -> tuple[float, float] | None:
    """(a, b) trung vị VÙNG TRẮNG (L 0.62–0.96, chroma < 0.025) — như do_anh_duyet."""
    import mo_hinh_lr as mh
    if px is None or not len(px):
        return None
    lab = mh.lab_cua(px)
    #  điểm sau dự đoán chạm trần (≥ 250) lệch màu — không xét WB (14/10)
    m = ((lab[:, 0] >= 0.62) & (lab[:, 0] <= 0.96) & (np.hypot(lab[:, 1], lab[:, 2]) < 0.025)
         & (np.asarray(px).max(axis=1) * 255 < 250))
    if m.sum() < 50:
        return None
    return float(np.median(lab[m, 1])), float(np.median(lab[m, 2]))


# ------------------------------------------------------------------ chặn cháy (Lightroom)
def _phan_chay(px) -> float:
    """% điểm khung dự đoán chạm ≥ 250 (kênh lớn nhất) — cùng ngưỡng vùng cháy của curve_da."""
    if px is None or not len(px):
        return 0.0
    return float((np.asarray(px).max(axis=1) * 255 >= 250).mean() * 100.0)


def chay_lr(items: list, mm: dict, cfg: dict, du) -> dict:
    """Exposure / Highlights theo độ CHÁY dự đoán trên ẢNH LIGHTROOM (14/10).

    #[[ User 14/10 (DSC09395, ngoài trời sáng): "Như ảnh này vẫn đang cháy sáng". Các phanh
    #   cháy của decide() đo trên JPEG NHÚNG của máy — Lightroom dựng khác: tấm đó JPEG nhúng
    #   mặt p95 248 nhưng Lightroom 233, khung cháy 37% mà Highlights vẫn ở số preset −29,
    #   tool còn +0.21 EV. Ở đây cùng các luật / ngưỡng của decide(), nhưng số đo là khung
    #   Lightroom dự đoán (mô hình học trên RAW thật):
    #     - khung đã cháy nặng ở Exposure preset (≥ hl_heavy_clip_pct) -> không tăng sáng;
    #     - phần cháy MỚI do tool tăng sáng không vượt hl_hard_pct (hạ từng 0.05 EV);
    #     - Highlights: hl_gain điểm / % cháy vượt hl_trigger_pct, trần hl_max (lấy mức
    #       mạnh hơn giữa decide() và đây);
    #     - cùng loạt chụp một mức (trung vị) — như dong_bo_loat. ]]"""
    hard = float(cfg.get("hl_hard_pct") or 8.0)
    nang = float(cfg.get("hl_heavy_clip_pct") or 20.0)
    trig, gain = float(cfg.get("hl_trigger_pct") or 0.3), float(cfg.get("hl_gain") or 14.0)
    hl_tran = float(cfg.get("hl_max") or 45)
    tk = {"ha_ev": 0, "keo_hl": 0}
    moi: dict = {}
    for r in items:
        if id(r) not in mm or r.get("bw"):
            continue
        m = mm[id(r)]
        if m["mau"].get("khung") is None:
            continue
        s = thong_so_tone(r, m["cu"])
        s0 = dict(s, Exposure2012=_f(r.get("old_exposure"), _f(s.get("Exposure2012"))),
                  Highlights2012=_f(r.get("old_highlights"), _f(s.get("Highlights2012"))))
        c0 = _phan_chay(du(r, s0, "khung"))
        delta = _f(r.get("delta_ev"))
        if delta > 0:
            if c0 >= nang:
                delta = 0.0
            else:
                def chay_them(d_, r=r, s=s, c0=c0):
                    return _phan_chay(du(r, dict(s, Exposure2012=_f(r.get("old_exposure")) + d_), "khung")) - c0
                if chay_them(delta) > hard:
                    #  chia đôi [0, delta] tìm mức tăng lớn nhất còn trong hl_hard_pct (6 lần dự đoán
                    #  thay vì tới 20 lần bước 0.05 — chuỗi 1.054 ảnh tính chậm 14/10)
                    lo, hi = 0.0, delta
                    for _ in range(6):
                        mid = (lo + hi) / 2.0
                        if chay_them(mid) > hard:
                            hi = mid
                        else:
                            lo = mid
                    delta = round(lo, 2)
        c1 = _phan_chay(du(r, dict(s, Exposure2012=_f(r.get("old_exposure")) + delta), "khung"))
        hl = -int(round(min(hl_tran, gain * max(0.0, c1 - trig))))
        moi[id(r)] = (delta, min(int(r.get("hl_adj") or 0), hl), c0, c1)
    #  cùng loạt -> một mức (trung vị các tấm đo được), tấm không đo theo loạt
    for loat in at.chia_loat([r for r in items if not r.get("bw")], cfg):
        co = [moi[id(r)] for r in loat if id(r) in moi]
        if not co:
            continue
        d_l = float(np.median([x[0] for x in co]))
        h_l = int(round(float(np.median([x[1] for x in co]))))
        for r in loat:
            c = moi.get(id(r), (None, None, None, None))
            moi[id(r)] = (d_l, h_l, c[2], c[3])
    for r in items:
        x = moi.get(id(r))
        if x is None or r.get("new_exposure") is None:
            continue
        delta, hl = x[0], x[1]
        doi = False
        if delta < _f(r.get("delta_ev")) - 1e-6:
            r["delta_ev"] = delta
            tk["ha_ev"] += 1
            doi = True
            if "ha-vi-chay-lr" not in str(r.get("notes", "")):
                r["notes"] = (str(r.get("notes", "")) + ";ha-vi-chay-lr").strip(";")
        if hl < int(r.get("hl_adj") or 0):
            r["hl_adj"] = hl
            tk["keo_hl"] += 1
            doi = True
        if doi:
            at.compute_values(r, cfg, r["crs"], r["atn"])
        if id(r) in mm:
            mm[id(r)]["chay"] = {"truoc": round(x[2], 1) if x[2] is not None else None,
                                 "tone": round(x[3], 1) if x[3] is not None else None,
                                 "hl": int(r.get("new_highlights") or 0),
                                 "ev": round(_f(r.get("new_exposure")), 2)}
    return tk


# ------------------------------------------------------------------ sáng da theo đích (Tone)
def sang_dich(items: list, mm: dict, cfg: dict, du) -> dict:
    """Bước TONE kéo ĐỘ SÁNG da dự đoán về L của màu đích — Exposure MỘT mức mỗi cảnh (14/10).

    #[[ User 14/10: "Với mỗi 1 màu đích đều chia theo R G B. Vậy nên cần phải đưa màu của da
    #   mặt ảnh về đúng với màu đó dù can thiệp qua bước nào. Nếu các bước trước đó đã cho ra
    #   ánh sáng và màu sắc da đúng như da đích thì các bước sau sẽ không chỉnh gì thêm."
    #   Đo buổi 2709 trên preview Lightroom: da L 0.746 trung vị, đích "Lễ Vu Quy" 0.864
    #   (R G B % 70/64/59 vs 86/80/76). Luật:
    #     - mỗi ảnh: Exposure thêm e để L da dự đoán = L đích (± mot_luot_ev_sang_tran);
    #     - CẢNH dùng trung vị e (giữ đều trong cảnh — "bức tăng bức giảm" 11/10); |L lệch|
    #       ≤ da_on_L ở trung vị -> không đổi;
    #     - kẹp trần max_ev / max_ev_up; chặn cháy để chay_lr chạy SAU (hạ EV khi cháy mới
    #       vượt hl_hard_pct, kéo Highlights) -> phần sáng còn thiếu để HSL Luminance + Curve. ]]"""
    tol = float(cfg.get("da_on_L") or 0.02)
    tran = float(cfg.get("mot_luot_ev_sang_tran") or 0.6)
    #  14/10 tối: không tăng sáng cả ảnh (user: "dư sáng ít nhất 0.5ev") — chỉ hạ khi da sáng
    #  hơn đích; phần sáng còn thiếu để Luminance Cam / Curve vùng da
    len_e = float(cfg.get("mot_luot_ev_sang_len", 0.0) or 0.0)
    xuong = float(cfg["max_ev"])
    len_ = float(cfg.get("max_ev_up") or cfg["max_ev"])
    tk = {"canh": 0, "tang": 0, "giam": 0, "e": []}
    e_cua: dict = {}
    theo: dict = {}
    for r in items:
        if id(r) in mm and not r.get("bw") and r.get("new_exposure") is not None:
            theo.setdefault(r.get("scene"), []).append(r)
    for _canh, ds in theo.items():
        es, lech = [], []
        #  mức của CẢNH là trung vị: 12 ảnh rải đều đủ (cảnh 300 ảnh tính 300 lần thì chậm)
        mau = [ds[int(i)] for i in np.linspace(0, len(ds) - 1, min(len(ds), 12)).round()]
        for r in mau:
            m = mm[id(r)]
            s = thong_so_tone(r, m["cu"])
            Lt = float(m["mau"]["L_t"])
            ev0 = _f(s.get("Exposure2012"))

            def f(e, r=r, s=s, ev0=ev0, Lt=Lt):
                return _da(du(r, dict(s, Exposure2012=ev0 + e)))[0] - Lt
            d0 = f(0.0)
            lech.append(d0)
            if abs(d0) <= tol:
                es.append(0.0)
                continue
            if d0 < 0 and len_e <= 0:
                es.append(0.0)               # da tối hơn đích: không tăng sáng cả ảnh
                continue
            lo, hi = -tran, max(0.0, len_e)
            f_lo, f_hi = f(lo), f(hi)
            if f_hi <= 0:
                es.append(hi)
                continue
            if f_lo >= 0:
                es.append(lo)
                continue
            for _ in range(7):
                mid = (lo + hi) / 2.0
                if f(mid) < 0:
                    lo = mid
                else:
                    hi = mid
            es.append((lo + hi) / 2.0)
        if not es or abs(float(np.median(lech))) <= tol:
            continue
        E = round(float(np.median(es)), 2)
        if abs(E) < 0.03:
            continue
        tk["canh"] += 1
        tk["e"].append(E)
        for r in ds:
            e_cua[id(r)] = E
    #  ảnh không đo được (không mặt…) cùng LOẠT với ảnh đã có mức -> theo loạt (như
    #  dong_bo_loat); ảnh không mặt đứng riêng giữ nguyên (giu_anh_khong_mat); ảnh LẺ đã đo
    #  là nhóm của chính nó (nhom_loat)
    for loat in at.nhom_cum([r for r in items if not r.get("bw")], cfg):
        co = [e_cua[id(r)] for r in loat if id(r) in e_cua]
        if not co:
            continue
        E_l = round(float(np.median(co)), 2)
        for r in loat:
            if r.get("new_exposure") is None:
                continue
            E = e_cua.get(id(r), E_l)
            moi = float(np.clip(_f(r.get("delta_ev")) + E, -xuong, len_))
            if abs(moi - _f(r.get("delta_ev"))) < 1e-6:
                continue
            tk["tang" if moi > _f(r.get("delta_ev")) else "giam"] += 1
            r["delta_ev"] = round(moi, 4)
            nhan = f"sang-dich:{E:+.2f}"
            if nhan not in str(r.get("notes", "")):
                r["notes"] = (str(r.get("notes", "")) + ";" + nhan).strip(";")
            at.compute_values(r, cfg, r["crs"], r["atn"])
    tk["e"] = round(float(np.median(tk["e"])), 2) if tk["e"] else 0.0
    return tk


# ------------------------------------------------------------------ chuỗi
_XOA = ("hsl_ghi", "hsl_moi", "hsl_thieu_cot", "da_lech0", "da_lech1", "da_duyet", "da_goc",
        "mau_da_bao", "_md", "curve_ghi_mot_luot", "curve_bao_mot_luot", "du_doan_lr", "gr_ghi",
        "gr_mid", "gr_hi", "_gr_v", "gr_thieu_cot", "hsl_l_ghi", "hsl_l_moi", "_moc_lum")


def chuoi(items: list, cfg: dict, folder=None) -> dict:
    """Chuỗi một lượt cho các ảnh `items` (cả cảnh — xem chon_duong). Trả tóm tắt kiểu
    MAU_DA (+ "mot_luot")."""
    import curve_da
    on_h = float(cfg.get("da_on_hue") or 3.0)
    on_c = float(cfg.get("da_on_chroma") or 0.10)
    #  14/10: chuỗi một lượt nâng sáng da (Exposure / Luminance) làm da NHẠT đi -> Sat phải bù
    #  nhiều hơn đường cũ; chạy thật 2709: 331 ảnh chạm trần +15 / +20 -> trần riêng (20, 35)
    phan = float(cfg.get("mot_luot_phan") or cfg.get("hsl_da_cuoi_phan") or 0.8)
    tran_h, tran_s = (float(v) for v in (cfg.get("mot_luot_hsl_tran") or cfg.get("hsl_da_cuoi_tran")
                                         or (15, 20)))
    #[[ 14/10: chuỗi một lượt chạy ĐỦ năm bước (user: "đưa màu của da mặt ảnh về đúng với màu
    #   đó dù can thiệp qua bước nào") — ô HSL da / Color Grading của giao diện cũ chỉ bật /
    #   tắt đường cũ. Buổi 2709 chạy với hai ô đó tắt: da dự đoán cuối lệch hue −3.4°. ]]
    hsl_bat = bool(cfg.get("hsl_da_cuoi") or cfg.get("hsl_da_ky_yeu") or cfg.get("mot_luot_hsl", True))
    grade_bat = bool(cfg.get("grade") or cfg.get("mot_luot_cg", True))
    md = dict(cfg.get("mau_da_dich") or {})
    co_trang = bool((md.get("trang") or {}).get("trong"))
    wb_bat = bool(cfg.get("source") == "catalog" and cfg.get("wb") != "off"
                  and cfg.get("wb_xet_lai", True) and co_trang)
    nguong_t = float(cfg.get("wb_xet_lai_nguong") or 0.004)
    phan_t = float(cfg.get("wb_xet_lai_phan") or 0.8)
    tran_k, tran_ti = (float(v) for v in (cfg.get("wb_xet_lai_tran") or (300.0, 6.0)))
    min_t = max(1, int(cfg.get("wb_xet_lai_min_anh") or 3))
    kq = {"mau": True, "ten": str(md.get("ten") or ""), "n": 0, "n_lr": 0,
          "hue_dich": 0.0, "q_dich": 0.0, "hue0": 0.0, "q0": 0.0, "hue1": 0.0, "q1": 0.0,
          "hue2": 0.0, "q2": 0.0, "wb_bat": wb_bat, "wb_co_trang": co_trang, "wb_canh_chinh": 0,
          "wb_canh_giu": 0, "wb_canh_chua_do": 0, "wb_k": 0.0, "wb_tint": 0.0, "trang_lech": None,
          "hsl": {"bat": hsl_bat, "mau": True, "dai": "Orange", "hue": 0, "sat": 0, "n": 0,
                  "canh_chinh": 0, "canh_on": 0, "canh_chan": 0},
          "grade_bat": grade_bat, "grade_n": 0,
          "mot_luot": {"anh": 0, "canh": 0, "curve": 0, "ngoai_pham_vi": 0, "chay": {},
                       "sang": {}, "lum": {"canh": 0, "muc": 0}, "L_dich": 0.0, "L0": 0.0,
                       "L1": 0.0, "L2": 0.0}}
    sang_bat = bool(cfg.get("mot_luot_sang_dich", True))
    tol_L = float(cfg.get("da_on_L") or 0.02)
    tran_L = float(cfg.get("hsl_da_lum_tran") or 25)
    for r in items:
        for k in _XOA:
            r.pop(k, None)
        r["mot_luot"] = True                  # lượt 2 sau khi áp: chỉ soát (xu_ly_anh_ui)
    #  ---- chuẩn bị: mô hình, thông số "cu", điểm ảnh, đích
    mm: dict = {}
    for r in items:
        if not _co_mat(r) or not r.get("lr_truoc") or not r.get("new_temp"):
            continue
        mh = mo_hinh_cho(r)
        mau = mau_cua(r, cfg) if mh is not None else None
        if mau is None:
            continue
        cu = cu_cua(r)
        mm[id(r)] = {"mh": mh, "cu": cu, "mau": mau}
    kq["mot_luot"]["anh"] = len(mm)
    theo_canh: dict = {}
    for r in items:
        theo_canh.setdefault(r.get("scene"), []).append(r)
    kq["mot_luot"]["canh"] = len(theo_canh)

    def du(r, s, tap="da"):
        m = mm[id(r)]
        px = m["mau"].get(tap)
        return None if px is None else m["mh"].ap(px, m["cu"], s)

    #  ---- 1. TONE — sáng da về L đích (theo cảnh), rồi chặn cháy TRÊN ẢNH LIGHTROOM
    #  (chay_lr chạy SAU: hạ phần tăng sáng làm cháy mới, kéo Highlights)
    if sang_bat:
        kq["mot_luot"]["sang"] = sang_dich(items, mm, cfg, du)
    if cfg.get("highlights", True) and cfg.get("mot_luot_chay", True):
        kq["mot_luot"]["chay"] = chay_lr(items, mm, cfg, du)

    def do_lai(r, m):
        L, h, q = _da(du(r, m["s"]))
        m.update(L=L, h0=h, q0=q, dh0=at._goc_lech(m["mau"]["h_t"] - h),     # noqa: SLF001
                 lr0=math.log(m["mau"]["q_t"] / max(q, 1e-9)))
    for r in items:
        if id(r) not in mm:
            continue
        m = mm[id(r)]
        m["s"] = thong_so_tone(r, m["cu"])
        do_lai(r, m)
        m["L_tone"] = m["L"]
        r["da_lech0"] = (round(m["dh0"], 1), round(math.exp(m["lr0"]), 3))

    #  ---- 2a. HSL Luminance Cam — độ sáng da còn thiếu sau Tone, một mức mỗi LOẠT chụp
    #[[ 14/10: theo LOẠT, không theo cảnh — DSC09395 (da đã sáng hơn đích sau Tone) nằm trong
    #   cảnh mà các loạt khác tối hơn: mức cảnh +25 làm nó sáng quá. Loạt = cùng khoảnh khắc,
    #   cùng ánh sáng; loạt không đo được da theo trung vị các loạt của cảnh. ]]
    lum_cua: dict = {}                       # id(r) -> mức
    if sang_bat:
        k_canh: dict = {}
        theo_loat = at.nhom_cum([r for r in items if not r.get("bw")], cfg)
        for loat in theo_loat:
            dung = [r for r in loat if id(r) in mm and mm[id(r)]["s"].get("LuminanceAdjustmentOrange") is not None]
            if not dung:
                continue
            res = float(np.median([mm[id(r)]["mau"]["L_t"] - mm[id(r)]["L"] for r in dung]))
            if abs(res) <= tol_L:
                for r in loat:
                    lum_cua[id(r)] = 0
                continue
            canh = dung[0].get("scene")
            if canh not in k_canh:
                kl = []
                for r in [x for x in theo_canh.get(canh, []) if id(x) in mm][:8]:
                    m = mm[id(r)]
                    s = m["s"]
                    L_ = _da(du(r, dict(s, LuminanceAdjustmentOrange=_f(s.get("LuminanceAdjustmentOrange")) + 10)))[0]
                    kl.append((L_ - m["L"]) / 10.0)
                k_canh[canh] = float(np.median(kl)) if kl else 0.0
            k_l = k_canh[canh]
            if not k_l > 0.0003:
                continue
            li = int(round(float(np.clip(res / k_l, -tran_L, tran_L))))
            for r in loat:
                lum_cua[id(r)] = li
        #  loạt không đo được: trung vị các loạt đã có mức trong cùng cảnh
        for canh, ds in theo_canh.items():
            co = [lum_cua[id(r)] for r in ds if id(r) in lum_cua]
            if not co:
                continue
            tv = int(round(float(np.median(co))))
            for r in ds:
                lum_cua.setdefault(id(r), tv)
        muc = [v for v in lum_cua.values() if v]
        kq["mot_luot"]["lum"] = {"anh": len(muc), "canh": len({r.get("scene") for r in items
                                                               if lum_cua.get(id(r))}),
                                 "muc": int(np.median(muc)) if muc else 0}
        for r in items:
            if r.get("bw") or id(r) not in lum_cua:
                continue
            cu_r = mm[id(r)]["cu"] if id(r) in mm else cu_cua(r)
            goc = _lum_goc(r, cu_r)
            if goc is None:
                continue
            li = lum_cua.get(id(r), 0)
            moi_l = float(np.clip(goc + li, -100, 100))
            dang = _f(cu_r.get(at.COT_HSL_L[0]), goc)
            if abs(moi_l - dang) >= 0.5:
                r["hsl_l_moi"], r["hsl_l_ghi"] = {at.COT_HSL_L[0]: moi_l}, True
                if li:
                    nhan = f"lum-da:Orange{li:+d}"
                    if nhan not in str(r.get("notes", "")):
                        r["notes"] = (str(r.get("notes", "")) + ";" + nhan).strip(";")
            #  mốc chưa có ô này (tool chưa từng ghi) -> lưu số gốc trước lần ghi đầu
            moc = (r.get("crs") or {}).get(at.COT_HSL_L[0])
            if r.get("hsl_l_ghi") and str(moc if moc is not None else "").strip() == "":
                r["_moc_lum"] = goc
            if id(r) in mm:
                m = mm[id(r)]
                m["s"] = dict(m["s"], LuminanceAdjustmentOrange=moi_l)
                m["lum"] = li
                do_lai(r, m)

    #  ---- 2. HSL Cam — một mức mỗi LOẠT chụp, hệ số theo mô hình tại hue da
    #[[ 14/10: theo LOẠT, không theo cảnh. Chạy thật 2709 với một mức mỗi cảnh: dự đoán khớp
    #   Lightroom (lệch 1.1°) mà chỉ 19% da vào vùng ổn — trong một cảnh mỗi loạt (người,
    #   chỗ đứng) da khác nhau, một mức cả cảnh chỉ kéo được trung vị. Loạt = cùng khoảnh
    #   khắc: vẫn đều trong loạt; loạt không đo được theo trung vị các loạt của cảnh. ]]
    def he_so(r):
        m = mm[id(r)]
        s = m["s"]
        h_ = _da(du(r, dict(s, HueAdjustmentOrange=_f(s.get("HueAdjustmentOrange")) + 10)))[1]
        q_ = _da(du(r, dict(s, SaturationAdjustmentOrange=_f(s.get("SaturationAdjustmentOrange")) + 10)))[2]
        return (at._goc_lech(h_ - m["h0"]) / 10.0, math.log(max(q_, 1e-9) / max(m["q0"], 1e-9)) / 10.0)  # noqa: SLF001
    k_canh: dict = {}

    def k_cua(canh):
        if canh not in k_canh:
            dung_c = [r for r in theo_canh.get(canh, []) if id(r) in mm]
            mau = [dung_c[int(i)] for i in np.linspace(0, len(dung_c) - 1, min(len(dung_c), 8)).round()]
            ks = np.array([he_so(r) for r in mau]) if mau else np.zeros((1, 2))
            k_h, k_s = float(np.median(ks[:, 0])), float(np.median(ks[:, 1]))
            #  mô hình không thấy phản ứng (da ngoài dải Cam…) -> hằng số đo tay cũ
            if not k_h > 0.05:
                k_h = float(cfg.get("hsl_da_k_hue") or 0.418)
            if not k_s > 0.002:
                k_s = float(cfg.get("hsl_da_k_sat") or 0.01085)
            k_canh[canh] = (k_h, k_s)
        return k_canh[canh]
    muc_loat: dict = {}                       # id(r) -> (ui, vi)
    us, vs = [], []
    for ds in (at.nhom_cum([r for r in items if not r.get("bw")], cfg) if hsl_bat else []):
        dung = [r for r in ds if id(r) in mm]
        if not dung:
            continue
        canh = dung[0].get("scene")
        k_h, k_s = k_cua(canh)
        dh = np.array([mm[id(r)]["dh0"] for r in dung])
        lr = np.array([mm[id(r)]["lr0"] for r in dung])
        u = v = 0.0
        if abs(float(np.median(dh))) > on_h:
            u = float(np.clip(phan * float(np.median(dh)) / k_h, -tran_h, tran_h))
        if abs(math.exp(float(np.median(lr))) - 1.0) > on_c:
            v = float(np.clip(phan * float(np.median(lr)) / k_s, -tran_s, tran_s))
        #  chặn vượt đích trên CẢ cảnh — đúng luật chuoi_mau_da_mau (9/10)
        res_h, res_c = -dh, -lr
        chan = False
        if u < 0:
            gh = min(0.0, (-on_h - float(np.percentile(res_h, 25))) / k_h)
            if u < gh:
                u, chan = gh, True
        elif u > 0:
            gh = max(0.0, (on_h - float(np.percentile(res_h, 75))) / k_h)
            if u > gh:
                u, chan = gh, True
        if v > 0:
            gh = max(0.0, (math.log(1.0 + on_c) - float(np.percentile(res_c, 75))) / k_s)
            if v > gh:
                v, chan = gh, True
        elif v < 0:
            gh = min(0.0, (math.log(1.0 - on_c) - float(np.percentile(res_c, 25))) / k_s)
            if v < gh:
                v, chan = gh, True
        ui, vi = int(round(u)), int(round(v))
        kq["hsl"]["canh_chan"] += int(chan)
        for r in ds:
            muc_loat[id(r)] = (ui, vi)
        if ui or vi:
            kq["hsl"]["canh_chinh"] += 1
            us.append(ui)
            vs.append(vi)
        else:
            kq["hsl"]["canh_on"] += 1
    #  loạt không đo được da: trung vị các loạt đã có mức của cùng cảnh
    for canh, ds in theo_canh.items():
        co = [muc_loat[id(r)] for r in ds if id(r) in muc_loat]
        if co:
            tv = (int(round(float(np.median([c[0] for c in co])))), int(round(float(np.median([c[1] for c in co])))))
            for r in ds:
                muc_loat.setdefault(id(r), tv)
    if us:
        kq["hsl"]["hue"], kq["hsl"]["sat"] = int(np.median(us)), int(np.median(vs))
    for r in items:
        #  tắt ô HSL -> mức 0 (trả số preset cho ảnh tool từng ghi), như chuoi_mau_da_mau;
        #  bật mà cảnh chưa đo được da -> không đụng
        if r.get("bw") or (hsl_bat and id(r) not in muc_loat):
            continue
        ui, vi = muc_loat[id(r)] if hsl_bat else (0, 0)
        goc = at._hsl_goc(r)                                         # noqa: SLF001
        moi = dict(goc)
        moi["HueAdjustmentOrange"] = float(np.clip(goc["HueAdjustmentOrange"] + ui, -100, 100))
        moi["SaturationAdjustmentOrange"] = float(np.clip(goc["SaturationAdjustmentOrange"] + vi, -100, 100))
        dang = {k: _f((r.get("crs_hien") or {}).get(k), goc[k]) for k in at.COT_HSL}
        if any(abs(float(moi[k]) - float(dang[k])) >= 0.5 for k in at.COT_HSL):
            r["hsl_moi"], r["hsl_ghi"] = moi, True
            kq["hsl"]["n"] += 1
            if ui or vi:
                nhan = f"hsl-da-mot-luot:Orange{ui:+d}/{vi:+d}"
                if nhan not in str(r.get("notes", "")):
                    r["notes"] = (str(r.get("notes", "")) + ";" + nhan).strip(";")
        if id(r) in mm:
            mm[id(r)]["s"] = dict(mm[id(r)]["s"], **moi)
            mm[id(r)]["hsl"] = (ui, vi)
    for r in items:
        if id(r) in mm:
            m = mm[id(r)]
            m.setdefault("hsl", (0, 0))
            L, h, q = _da(du(r, m["s"]))
            m.update(h1=h, q1=q)
            r["da_lech1"] = round(at._goc_lech(m["mau"]["h_t"] - h), 1)     # noqa: SLF001

    #  ---- 3. CURVE — da dự đoán sau HSL, miền curve đã hiệu chỉnh của mô hình
    nen_chay = bool(cfg.get("curve_chay") or cfg.get("mot_luot_nen_chay", True))
    #  14/10: chuỗi một lượt luôn có bước Curve da (Tone -> HSL -> CURVE -> WB -> CG — đích R G B,
    #  bước trước chưa đưa da tới thì Curve chỉnh tiếp) — ô "Curve da" của giao diện cũ chỉ bật /
    #  tắt lượt 2 của đường cũ
    curve_bat = bool(cfg.get("curve_da") or cfg.get("mot_luot_curve_da", True))
    if curve_bat or nen_chay:
        do_map, ds_cv = {}, []
        for r in curve_da.chon_anh(items, cfg):
            if id(r) not in mm:
                continue
            m = mm[id(r)]
            mien_mh, kieu_mh = m["mh"].curve["mien"], m["mh"].curve["kieu"]
            da = du(r, m["s"])
            tr = du(r, m["s"], "trung")
            kh = du(r, m["s"], "khung")
            d0 = r["lr_truoc"]
            do = {"ok": True, "mien": mien_mh, "mat_na": d0.get("mat_na"), "n_da": d0.get("n_da"),
                  "crop": d0.get("crop"), "trung_ti_le": d0.get("trung_ti_le", 0.0)}
            P = cl.srgb_sang_mien(da, mien_mh)
            do["da_mn" if m["mau"]["kieu"] == "mn" else "da_cu"] = P
            if m["mau"]["kieu"] == "mn":
                do["da_cu"] = P
            if tr is not None:
                do["trung"] = cl.srgb_sang_mien(tr, mien_mh)
            if kh is not None:
                do["khung"] = cl.srgb_sang_mien(kh, mien_mh)
                do["chay_pct"] = round(100.0 * float((kh.max(axis=1) * 255 >= curve_da.NGUONG_CHAY).mean()), 3)
            do["p95_da"] = float(np.percentile(P.max(axis=1), 95))
            do_map[id(r)] = do
            ds_cv.append(r)
        if ds_cv:
            m0 = mm[id(ds_cv[0])]["mh"]
            cfg_cv = dict(cfg, curve_mien=m0.curve["mien"], curve_kieu_tong=m0.curve["kieu"],
                          curve_chay=nen_chay, curve_da_sang=sang_bat, curve_da=curve_bat)
            tt = curve_da.ket_thuc(ds_cv, do_map, cfg_cv)
            kq["mot_luot"]["curve"] = int(tt.get("doi", 0))
            for r in ds_cv:
                g = r.pop("curve_ghi", None)
                b = r.pop("curve_bao", None)
                if g:
                    r["curve_ghi_mot_luot"] = g
                    mm[id(r)]["s"] = _ap_curve(mm[id(r)]["s"], g)
                if b:
                    r["curve_bao_mot_luot"] = b
            #  ảnh trong loạt không đo được: theo curve của loạt (cùng curve mốc)
            for loat in at.chia_loat(curve_da.chon_anh(items, cfg), cfg):
                co = [r for r in loat if r.get("curve_ghi_mot_luot")]
                for r in loat:
                    if r.get("curve_ghi_mot_luot") or not co:
                        continue
                    mau = next((x for x in co if x.get("curve_moc") == r.get("curve_moc")), None)
                    if mau is not None:
                        r["curve_ghi_mot_luot"] = dict(mau["curve_ghi_mot_luot"])
    for r in items:
        if id(r) in mm:
            m = mm[id(r)]
            m["L_cv"], m["h_cv"], m["q_cv"] = _da(du(r, m["s"]))

    #  ---- 4. WB — chỉ vùng trắng, dự đoán sau Tone + HSL + Curve
    if wb_bat:
        lech_tat_ca = []
        for canh, ds in theo_canh.items():
            lech = []
            for r in ds:
                if id(r) not in mm:
                    continue
                m = mm[id(r)]
                t = _trang(du(r, m["s"], "trung"))
                tr_dich = (md.get("trang") or {}).get("ngoai" if m["mau"]["ngoai"] else "trong")
                if t is None or not tr_dich:
                    continue
                m["trang_lech"] = (t[0] - float(tr_dich[0]), t[1] - float(tr_dich[1]))
                lech.append(m["trang_lech"])
            if len(lech) < min_t:
                kq["wb_canh_chua_do"] += 1
                continue
            med = np.median(np.asarray(lech), axis=0)
            lech_tat_ca.append(float(np.hypot(*med)))
            if float(np.hypot(*med)) <= nguong_t:
                kq["wb_canh_giu"] += 1
                for r in ds:
                    if id(r) in mm:
                        mm[id(r)]["wb"] = "giu"
                continue
            #  Jacobi của vùng trắng theo (K, Tint) — từ mô hình, trung vị cảnh
            J = []
            for r in ds:
                if id(r) not in mm or "trang_lech" not in mm[id(r)]:
                    continue
                m = mm[id(r)]
                s = m["s"]
                t0 = _trang(du(r, s, "trung"))
                tk = _trang(du(r, dict(s, Temperature=_f(s.get("Temperature")) + 100.0), "trung"))
                tt_ = _trang(du(r, dict(s, Tint=_f(s.get("Tint")) + 4.0), "trung"))
                if t0 and tk and tt_:
                    J.append(np.column_stack([(np.array(tk) - t0) / 100.0, (np.array(tt_) - t0) / 4.0]))
            if not J:
                kq["wb_canh_chua_do"] += 1
                continue
            try:
                dwb = -phan_t * np.linalg.solve(np.median(np.asarray(J), axis=0), med)
            except np.linalg.LinAlgError:
                kq["wb_canh_chua_do"] += 1
                continue
            kq["wb_canh_chinh"] += 1
            bu = (float(round(np.clip(dwb[0], -tran_k, tran_k))), float(round(np.clip(dwb[1], -tran_ti, tran_ti))))
            for r in ds:
                if r.get("bw") or not r.get("new_temp"):
                    continue
                cu_bu = r.get("wb_bu") or (0.0, 0.0)
                bu_r = (float(np.clip(cu_bu[0] + bu[0], -tran_k, tran_k)),
                        float(np.clip(cu_bu[1] + bu[1], -tran_ti, tran_ti)))
                at._dat_wb_bu(r, cfg, bu_r)                           # noqa: SLF001
                if id(r) in mm:
                    m = mm[id(r)]
                    m["wb"], m["bu"] = "chinh", bu_r
                    m["s"] = dict(m["s"], WhiteBalance="Custom", Temperature=_f(r["new_temp"]),
                                  Tint=_f(r.get("new_tint")),
                                  Exposure2012=_f(r.get("new_exposure"), _f(m["s"].get("Exposure2012"))))
        if lech_tat_ca:
            kq["trang_lech"] = float(np.median(lech_tat_ca))
        bus = [mm[id(r)]["bu"] for r in items if id(r) in mm and mm[id(r)].get("wb") == "chinh"]
        if bus:
            kq["wb_k"] = float(np.median([b[0] for b in bus]))
            kq["wb_tint"] = float(np.median([b[1] for b in bus]))
    for r in items:
        if id(r) in mm:
            m = mm[id(r)]
            m["h_wb"], m["q_wb"] = _da(du(r, m["s"]))[1:]

    #  ---- 5. COLOR GRADING — phần da còn lệch SAU WB
    gain = float(cfg.get("grade_gain_hue", 0.45))
    sat_max = float(cfg.get("grade_sat_max", 12))
    nguong = float(cfg.get("grade_nguong_hue", 0.0) or 0.0)
    tran_cg = min(sat_max / 100.0 * at.GRADE_OKLAB_100, float(cfg.get("trang_tran_cg") or 0.003))
    for r in items:
        r["gr_hue"] = r["gr_sat"] = 0
        if not grade_bat or id(r) not in mm:
            continue
        m = mm[id(r)]
        d = at._goc_lech(m["mau"]["h_t"] - m["h_wb"])                     # noqa: SLF001
        vuot = abs(d) - nguong
        if vuot <= 0:
            continue
        sat = min(gain * vuot, sat_max)
        if sat < 1.0:
            continue
        huong = math.radians(m["h_wb"]) + math.copysign(math.pi / 2.0, d)
        r["_gr_v"] = sat / 100.0 * at.GRADE_OKLAB_100 * np.array([math.cos(huong), math.sin(huong)])
    kq["grade_n"] = at._grade_hoan_tat(items, dict(cfg, grade=True) if grade_bat else cfg,  # noqa: SLF001
                                       tran_cg)

    #  ---- cụm cùng khung: cùng ánh sáng / màu (14/10) — TRƯỚC dự đoán cuối
    kq["mot_luot"]["cum"] = at.dong_bo_cum(items, cfg)

    #  ---- dự đoán cuối + báo cáo
    bao = []
    for r in items:
        if id(r) not in mm:
            continue
        m = mm[id(r)]
        s = thong_so_job(r, m["cu"])
        L, h, q = _da(du(r, s))
        t = _trang(du(r, s, "trung"))
        ngoai = m["mh"].ngoai_pham_vi(m["cu"], s)
        kq["mot_luot"]["ngoai_pham_vi"] += int(bool(ngoai))
        px_cuoi = du(r, s)
        r["du_doan_lr"] = {"L": round(L, 4), "h": round(h, 2), "q": round(q, 4),
                           "L_t": round(m["mau"]["L_t"], 4), "rgb_pt": rgb_pt(px_cuoi),
                           "rgb_t": m["mau"].get("rgb_t"),
                           "trung_ab": (round(t[0], 4), round(t[1], 4)) if t else None,
                           "khoa": m["mh"].khoa, "ngoai_pham_vi": ngoai, "kieu": m["mau"]["kieu"],
                           "thong_so": {k: s[k] for k in ("Exposure2012", "Temperature", "Tint",
                                                          "HueAdjustmentOrange",
                                                          "SaturationAdjustmentOrange") if k in s}}
        r["mau_da_bao"] = {
            "nguon": "mo_hinh_lr", "dich": (round(m["mau"]["h_t"], 1), round(m["mau"]["q_t"], 4)),
            "sau_wb": (round(m["h0"], 1), round(m["q0"], 4)),
            "wb": m.get("wb", "chua_do"), "wb_bu": m.get("bu", (0.0, 0.0)),
            "trang_lech": m.get("trang_lech"), "hsl": m["hsl"],
            "sau_hsl": (round(m["h1"], 1), round(m["q1"], 4)),
            "sau_curve": (round(m["h_cv"], 1), round(m["q_cv"], 4)),
            "chay": m.get("chay"),
            "L": {"dich": round(m["mau"]["L_t"], 3), "truoc": round(_da(m["mau"]["da"])[0], 3),
                  "tone": round(m.get("L_tone", m["L"]), 3), "hsl": round(m["L"], 3),
                  "curve": round(m.get("L_cv", m["L"]), 3), "cuoi": round(L, 3),
                  "lum": int(m.get("lum") or 0)},
            "rgb": {"truoc": rgb_pt(m["mau"]["da"]), "cuoi": rgb_pt(px_cuoi),
                    "dich": rgb_pt(np.asarray([m["mau"]["rgb_t"]], dtype=np.float64) / 255.0)},
            "cg": (int(r.get("gr_hue") or 0), int(r.get("gr_sat") or 0)) if r.get("gr_ghi") else None,
            "sau_cg": (round(h, 1), round(q, 4))}
        bao.append(r["mau_da_bao"])
    #  mốc: số Luminance Cam gốc cho ảnh vừa ghi ô này lần đầu (lần sau tính từ preset)
    them = {}
    for r in items:
        if r.get("_moc_lum") is not None:
            r.setdefault("crs", {})[at.COT_HSL_L[0]] = str(int(round(float(r["_moc_lum"]))))
            them[at.khoa_duong_dan(r.get("lr_path") or r["path"])] = {
                at.COT_HSL_L[0]: int(round(float(r["_moc_lum"])))}
    if them and folder is not None:
        try:
            at.moc_them_cot(Path(str(folder)), them)
        except OSError:
            pass
    if bao:
        kq["n"] = kq["n_lr"] = len(bao)
        for ten, k_ in (("L_dich", "dich"), ("L0", "truoc"), ("L1", "tone"), ("L2", "cuoi")):
            kq["mot_luot"][ten] = round(float(np.median([b["L"][k_] for b in bao])), 3)
        for ten, i, k_ in (("hue_dich", 0, "dich"), ("q_dich", 1, "dich"), ("hue0", 0, "sau_wb"),
                           ("q0", 1, "sau_wb"), ("hue1", 0, "sau_hsl"), ("q1", 1, "sau_hsl"),
                           ("hue2", 0, "sau_cg"), ("q2", 1, "sau_cg")):
            kq[ten] = float(np.median([b[k_][i] for b in bao]))
    return kq


def gop(cu: dict | None, moi: dict) -> dict:
    """Tóm tắt hai đường (cũ / một lượt) -> một MAU_DA cho giao diện."""
    if not cu or not cu.get("n"):
        return dict(moi)
    out = dict(cu)
    tong = cu.get("n", 0) + moi.get("n", 0)
    for k in ("hue_dich", "q_dich", "hue0", "q0", "hue1", "q1", "hue2", "q2"):
        out[k] = (cu.get(k, 0.0) * cu.get("n", 0) + moi.get(k, 0.0) * moi.get("n", 0)) / max(1, tong)
    for k in ("n", "n_lr", "wb_canh_chinh", "wb_canh_giu", "wb_canh_chua_do", "grade_n"):
        out[k] = cu.get(k, 0) + moi.get(k, 0)
    out["hsl"] = dict(cu.get("hsl") or {})
    for k in ("n", "canh_chinh", "canh_on", "canh_chan"):
        out["hsl"][k] = (cu.get("hsl") or {}).get(k, 0) + (moi.get("hsl") or {}).get(k, 0)
    out["mot_luot"] = moi.get("mot_luot")
    return out


# ------------------------------------------------------------------ soát sau khi áp
#[[ 14/10 (user chọn "Báo + tự chạy lượt 2 cho ảnh lệch"): áp xong, lấy preview Lightroom
#   THẬT của một ảnh mỗi loạt (+ ảnh lẻ, ảnh ngoại suy), đo da, so với r["du_doan_lr"].
#   Lệch dự đoán > LECH_H / LECH_Q VÀ da còn ngoài vùng ổn của đích -> cả loạt (cảnh lệch
#   ≥ TI_LE_CANH: cả cảnh; trung vị buổi > LECH_BUOI: mọi ảnh) chạy curve lượt 2 — ghép
#   lên curve VỪA ÁP (không phải curve mốc: mốc không còn là thứ Lightroom đang dựng). ]]
LECH_H, LECH_Q, TI_LE_CANH, LECH_BUOI = 1.5, 0.05, 0.30, 2.0
#: 14/10 — L: lệch dự đoán quá LECH_L (OkLab) là "lệch"; ngoài LECH_L_ON × da_on_L so với L
#: đích là ngoài vùng ổn độ sáng
LECH_L, LECH_L_ON = 0.02, 1.5


def chon_soat(ds: list, cfg: dict, toi_da_le: int = 40) -> list:
    """Ảnh soát: một ảnh mỗi loạt (ưu tiên ngoại suy, rồi đổi nhiều nhất) + ảnh lẻ
    (≤ toi_da_le, rải đều) + mọi ảnh ngoại suy."""
    co = [r for r in ds if r.get("du_doan_lr")]
    if not co:
        return []
    loats = at.chia_loat(co, cfg)
    trong_loat = {id(r) for g in loats for r in g}

    def doi(r):
        d = (r.get("du_doan_lr") or {})
        return (bool(d.get("ngoai_pham_vi")), abs(_f(r.get("delta_ev"))) +
                abs(_f(r.get("new_temp")) - _f(r.get("old_temp"))) / 400.0)
    out = [max(g, key=doi) for g in loats]
    le = [r for r in co if id(r) not in trong_loat]
    buoc = max(1, math.ceil(len(le) / max(1, toi_da_le)))
    out += le[::buoc]
    da = {id(r) for r in out}
    out += [r for r in co if (r.get("du_doan_lr") or {}).get("ngoai_pham_vi") and id(r) not in da]
    return out


def lech_soat(r: dict, do: dict, cfg: dict) -> dict | None:
    """Số đo thật (curve_da.do_anh trên preview sau khi áp) so với dự đoán."""
    import curve_da
    d = r.get("du_doan_lr") or {}
    if not do or not do.get("ok") or not d:
        return None
    P = do.get("da_mn") if d.get("kieu") == "mn" and do.get("da_mn") is not None else do.get("da_cu")
    if P is None or len(P) < 50:
        return None
    lab = curve_da.thong_ke(P, do.get("mien") or "melissa")
    h, q = curve_da.hue_q(lab)
    kieu = "mn" if d.get("kieu") == "mn" else "cu"
    rgb, _ng = curve_da.dich_cua(r, cfg, kieu)
    lt = at.mau_dich_lab(rgb)
    h_t, q_t = curve_da.hue_q(lt)
    on_h = float(cfg.get("da_on_hue") or 3.0)
    on_c = float(cfg.get("da_on_chroma") or 0.10)
    dh = abs(at._goc_lech(h - float(d["h"])))                         # noqa: SLF001
    dq = abs(q / max(float(d["q"]), 1e-9) - 1.0)
    ngoai_on = abs(at._goc_lech(h_t - h)) > on_h or abs(q / max(q_t, 1e-9) - 1.0) > on_c  # noqa: SLF001
    #  14/10: đích R G B — độ sáng da cũng phải trong vùng ổn (dự đoán có L đích)
    dL = abs(float(lab[0]) - float(d["L"])) if d.get("L") is not None else 0.0
    if cfg.get("mot_luot_sang_dich", True) and d.get("L_t") is not None:
        ngoai_on = ngoai_on or abs(float(lab[0]) - float(d["L_t"])) > LECH_L_ON * float(cfg.get("da_on_L") or 0.02)
    return {"h": round(h, 2), "q": round(q, 4), "L": round(float(lab[0]), 4), "dh": round(dh, 2),
            "dq": round(dq, 4), "dL": round(dL, 4), "ngoai_on": bool(ngoai_on),
            "lech": bool((dh > LECH_H or dq > LECH_Q or dL > LECH_L) and ngoai_on)}


def soat(ds: list, do_mau: dict, cfg: dict, tat_ca: list | None = None) -> dict:
    """ds: ảnh chuỗi một lượt vừa áp (có dự đoán); do_mau {id(r): do_anh} của ảnh soát; tat_ca:
    MỌI ảnh một lượt (kể cả không đo — lượt 2 theo cụm cùng khung phải tới cả chúng). Gắn
    r["soat_lr"]; ảnh cần lượt 2 có r["curve_ghi"] / r["hsl_l2"]. -> tóm tắt."""
    tat_ca = list(tat_ca) if tat_ca is not None else list(ds)
    for r in tat_ca:
        r.pop("hsl_l2", None)
    import curve_da
    kq = {"n": 0, "lech": 0, "hue": None, "q": None, "sua": 0, "anh_sua": [], "ca_buoi": False}
    for r in ds:
        r.pop("soat_lr", None)
    theo = {id(r): r for r in ds}
    ket = {}
    for k, do in do_mau.items():
        r = theo.get(k)
        if r is None:
            continue
        l = lech_soat(r, do, cfg)
        if l is not None:
            r["soat_lr"] = l
            ket[k] = l
    if not ket:
        return kq
    kq["n"] = len(ket)
    kq["lech"] = sum(1 for v in ket.values() if v["lech"])
    kq["hue"] = round(float(np.median([v["dh"] for v in ket.values()])), 2)
    kq["q"] = round(float(np.median([v["dq"] for v in ket.values()])), 4)
    #  ảnh cần lượt 2
    can: set = set()
    if kq["hue"] > LECH_BUOI:
        kq["ca_buoi"] = True
        can = {id(r) for r in ds}
    else:
        loats = at.chia_loat(ds, cfg)
        loat_cua = {id(r): i for i, g in enumerate(loats) for r in g}
        for k, v in ket.items():
            if not v["lech"]:
                continue
            i = loat_cua.get(k)
            can |= {id(r) for r in loats[i]} if i is not None else {k}
        theo_canh: dict = {}
        for k, v in ket.items():
            theo_canh.setdefault(theo[k].get("scene"), []).append(v["lech"])
        for canh, ls in theo_canh.items():
            if len(ls) >= 2 and sum(ls) / len(ls) >= TI_LE_CANH:
                can |= {id(r) for r in ds if r.get("scene") == canh}
    #  14/10: chuỗi một lượt luôn có bước Curve (kéo cả L — đích R G B): lượt 2 cho ảnh lệch
    #  chạy cả khi ô "Curve da" tắt; tắt hẳn (mot_luot_curve_da False) thì chỉ BÁO, không đánh
    #  dấu ảnh nào là "đã qua lượt 2" (14/10: 888 ảnh bị đánh dấu dù không ghi gì)
    if not (cfg.get("curve_da") or cfg.get("curve_chay") or cfg.get("mot_luot_curve_da", True)):
        kq["anh_sua"] = []
        kq["can"] = len(can)
        return kq
    cfg = dict(cfg, curve_da=True, curve_da_sang=bool(cfg.get("mot_luot_sang_dich", True)))
    #  14/10 tối: HSL Cam theo số đo THẬT cho mọi loạt còn ngoài vùng ổn (phan_hoi_hsl); loạt
    #  đã sửa HSL thì lượt 2 không chồng thêm curve (curve tính trên số đo TRƯỚC khi đổi HSL)
    hsl2 = phan_hoi_hsl(ds, do_mau, ket, cfg, tat_ca) if cfg.get("mot_luot_l2_hsl", True) else {}
    for r in tat_ca:
        if id(r) in hsl2:
            r["hsl_l2"] = hsl2[id(r)]
    kq["hsl"] = len(hsl2)
    can = {k for k in can if k not in hsl2}
    #  curve lượt 2: ghép lên curve VỪA ÁP; ảnh đo được trong nhóm cần sửa giải trên số đo
    #  của nó, cùng loạt thì ket_thuc gom một curve; tấm không đo trong loạt theo loạt
    ds_sua = [theo[k] for k in can if k in theo]
    hop_le = {id(r) for r in curve_da.chon_anh(ds_sua, cfg)}
    da_do = [r for r in ds_sua if id(r) in do_mau and id(r) in hop_le]
    cu_moc = {}
    for r in ds_sua:
        cu_moc[id(r)] = r.get("curve_moc")
        cv = r.get("curve_ghi_mot_luot")
        if cv:
            r["curve_moc"] = {k: cv.get(k, "") for k in at.COT_CURVE}
    try:
        if da_do:
            curve_da.ket_thuc(da_do, {id(r): do_mau[id(r)] for r in da_do}, cfg)
        for loat in at.chia_loat(ds_sua, cfg):
            mau = next((r for r in loat if r.get("curve_ghi")), None)
            for r in loat:
                if (mau is not None and not r.get("curve_ghi") and id(r) in hop_le
                        and r.get("curve_moc") == mau.get("curve_moc")):
                    r["curve_ghi"] = dict(mau["curve_ghi"])
    finally:
        for r in ds_sua:
            r["curve_moc"] = cu_moc[id(r)]
    at.dong_bo_cum_luot2(tat_ca, cfg)
    kq["anh_sua"] = [r for r in tat_ca if r.get("curve_ghi") or r.get("hsl_l2")]
    kq["sua"] = len(kq["anh_sua"])
    return kq


def phan_hoi_hsl(ds: list, do_mau: dict, ket: dict, cfg: dict, tat_ca: list | None = None) -> dict:
    """Lượt 2: HSL Cam (Hue / Sat / Luminance) theo số đo THẬT sau khi áp (14/10 tối).

    #[[ User 14/10 ("oke hãy thử xem sao"): lượt 2 sửa HSL từ số đo thật chứ không chỉ curve
    #   (curve trần 0.03 không kéo nổi độ đậm). Chạy thật 2709: dự đoán một lượt lệch thật
    #   ~1° / 5% trung vị nhưng p90 3.5° / 20% — da chỉ ~25% vào vùng ổn cả màu lẫn sáng.
    #   Ở đây số đo là da THẬT của ảnh soát (một ảnh mỗi loạt) ở đúng trạng thái vừa áp; mô hình
    #   chỉ cho độ nhạy CỤC BỘ (bước ±10 quanh trạng thái đó — không ngoại suy xa):
    #     - chỉ thành phần NGOÀI vùng ổn (hue ±da_on_hue, độ đậm ±da_on_chroma, L ±da_on_L);
    #     - giải 3×3 (Hue, Sat, Lum Cam -> hue, ln độ đậm, L) có trọng số theo vùng ổn, kéo
    #       mot_luot_phan phần lệch; loạt một mức (trung vị các tấm soát của loạt);
    #     - tổng so với số preset vẫn trong trần chuỗi (mot_luot_hsl_tran, hsl_da_lum_tran). ]]
    #[[ Cụm cùng khung (14/10): MỘT số TUYỆT ĐỐI cho mọi ảnh của cụm — kể cả ảnh không đo
    #   (tat_ca: mọi ảnh một lượt) — tính từ ảnh soát (trước: mỗi ảnh "số hiện tại + Δ" kẹp
    #   theo mốc RIÊNG từng ảnh và chỉ ảnh có đo -> 85 cụm 2709 lệch Hue / Sat sau lượt 2). ]]
    -> {id(r): {khoá HSL: số mới}} cho mọi ảnh của cụm cần sửa."""
    import curve_da
    on_h = float(cfg.get("da_on_hue") or 3.0)
    on_c = float(cfg.get("da_on_chroma") or 0.10)
    tol_L = float(cfg.get("da_on_L") or 0.02)
    tran_h, tran_s = (float(v) for v in (cfg.get("mot_luot_hsl_tran") or (15, 20)))
    tran_L = float(cfg.get("hsl_da_lum_tran") or 35)
    phan = float(cfg.get("mot_luot_phan") or 0.8)
    sang = bool(cfg.get("mot_luot_sang_dich", True))
    KH, KS, KL = "HueAdjustmentOrange", "SaturationAdjustmentOrange", at.COT_HSL_L[0]
    W = np.diag([1.0 / on_h, 1.0 / math.log(1.0 + on_c), 1.0 / tol_L])
    out: dict = {}
    co_do = {id(r) for r in ds}
    for g in at.nhom_cum(list(tat_ca if tat_ca is not None else ds), cfg):
        ds_d = []
        mau_r = None
        for r in g:
            l = ket.get(id(r))
            do = do_mau.get(id(r))
            m = mo_hinh_cho(r) if id(r) in co_do else None
            if not l or not l.get("ngoai_on") or not do or not hasattr(m, "ap"):
                continue
            kieu = "mn" if ((r.get("du_doan_lr") or {}).get("kieu") == "mn" and do.get("da_mn") is not None) else "cu"
            P = do.get("da_mn") if kieu == "mn" else do.get("da_cu")
            if P is None or len(P) < 50:
                continue
            px = _srgb(_bot(P, SO_DIEM["da"]), do.get("mien") or "melissa")
            cu_r = cu_cua(r)
            s1 = thong_so_job(r, cu_r)
            if s1.get(KL) in (None, ""):
                lg = _lum_goc(r, cu_r)
                if lg is None:
                    continue
                s1[KL] = lg
            L0, h0, q0 = _da(px)
            rgb, _ng = curve_da.dich_cua(r, cfg, kieu)
            lt = at.mau_dich_lab(rgb)
            L_t = float(lt[0])
            h_t = math.degrees(math.atan2(lt[2], lt[1]))
            q_t = float(math.hypot(lt[1], lt[2])) / max(L_t, 1e-6)
            dh = at._goc_lech(h_t - h0)                                  # noqa: SLF001
            rh = dh if abs(dh) > on_h else 0.0
            rq = math.log(q_t / max(q0, 1e-9)) if abs(q0 / max(q_t, 1e-9) - 1.0) > on_c else 0.0
            rL = (L_t - L0) if (sang and abs(L_t - L0) > tol_L) else 0.0
            if not (rh or rq or rL):
                continue
            J = np.zeros((3, 3))
            for j, k in enumerate((KH, KS, KL)):
                L2, h2, q2 = _da(m.ap(px, s1, dict(s1, **{k: _f(s1.get(k)) + 10.0})))
                J[:, j] = (at._goc_lech(h2 - h0) / 10.0, math.log(max(q2, 1e-9) / max(q0, 1e-9)) / 10.0,  # noqa: SLF001
                           (L2 - L0) / 10.0)
            if not sang:
                J[:, 2] = 0.0
            try:
                D = np.linalg.lstsq(W @ J, W @ np.array([rh, rq, rL]), rcond=None)[0] * phan
            except np.linalg.LinAlgError:
                continue
            ds_d.append(D)
            mau_r = mau_r or r
        if not ds_d:
            continue
        D = np.median(np.asarray(ds_d), axis=0)
        #  số tuyệt đối tính MỘT lần từ ảnh soát (cụm đã cùng số hiệu lực sau lượt 1 — dong_bo_cum)
        cu_m = cu_cua(mau_r)
        s1 = thong_so_job(mau_r, cu_m)
        goc = at._hsl_goc(mau_r)                                             # noqa: SLF001
        lg = _lum_goc(mau_r, cu_m)
        moi = {}
        for k, d_, tran, g0 in ((KH, D[0], tran_h, goc.get(KH)), (KS, D[1], tran_s, goc.get(KS)),
                                (KL, D[2], tran_L, lg)):
            if g0 is None or abs(d_) < 0.5:
                continue
            cur = _f(s1.get(k), g0)
            v = float(np.clip(round(cur + d_), max(-100.0, g0 - tran), min(100.0, g0 + tran)))
            if abs(v - cur) >= 1.0:
                moi[k] = v
        if moi:
            for r in g:
                if not r.get("bw"):
                    out[id(r)] = dict(moi)
    return out


def ghi_lich_su(kq: dict, buoi: str) -> None:
    """mo_hinh_lr/lich_su.jsonl — lệch dự đoán qua các buổi (mô hình trôi thì thấy)."""
    import json
    from datetime import datetime
    import mo_hinh_lr as mh
    try:
        d = mh.thu_muc()
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "lich_su.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"luc": datetime.now().isoformat(timespec="seconds"), "buoi": buoi,
                                 **{k: kq.get(k) for k in ("n", "lech", "hue", "q", "sua", "ca_buoi")}},
                                ensure_ascii=False) + "\n")
    except OSError:
        pass


def file_du_doan(folder):
    from pathlib import Path
    import mo_hinh_lr as mh
    return mh.thu_muc() / f"du_doan_{at.ten_job(Path(str(folder)).name)}.json"


def luu_du_doan(items: list, folder, cfg: dict | None = None) -> None:
    """Dự đoán của lần áp vừa rồi + đích da / vùng ổn lúc đó (KIEM_MOT_LUOT so với preview
    Lightroom thật)."""
    import json
    from datetime import datetime
    import duong_dan as dd
    ds = {r.get("lr_path") or r["path"]: r["du_doan_lr"] for r in items if r.get("du_doan_lr")}
    if not ds:
        return
    try:
        f = file_du_doan(folder)
        f.parent.mkdir(parents=True, exist_ok=True)
        cfg = cfg or {}
        dd.ghi_ben(f, json.dumps({"luc": datetime.now().isoformat(timespec="seconds"),
                                  "thu_muc": str(folder), "anh": ds, "luot2": [],
                                  "cfg": {k: cfg.get(k) for k in ("mau_da_dich", "da_on_hue",
                                                                  "da_on_chroma", "curve_mien")}},
                                 ensure_ascii=False, default=str))
    except OSError:
        pass


def danh_dau_luot2(folder, ds: list) -> None:
    """Ảnh lượt 2 đã sửa thêm sau dự đoán — KIEM_MOT_LUOT tính riêng."""
    import json
    import duong_dan as dd
    if not ds:
        return
    try:
        f = file_du_doan(folder)
        d = json.loads(f.read_text(encoding="utf-8"))
        d["luot2"] = sorted(set(d.get("luot2") or []) | {r.get("lr_path") or r["path"] for r in ds})
        dd.ghi_ben(f, json.dumps(d, ensure_ascii=False, default=str))
    except (OSError, ValueError):
        pass
