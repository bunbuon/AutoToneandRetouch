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
    """(ảnh chuỗi một lượt, ảnh đường cũ) — theo CẢNH."""
    if not bat(cfg):
        return [], list(items)
    theo: dict = {}
    for r in items:
        theo.setdefault(r.get("scene"), []).append(r)
    moi, cu = [], []
    for ds in theo.values():
        mat = [r for r in ds if _co_mat(r)]
        ok = [r for r in mat if r.get("lr_truoc") and mo_hinh_cho(r) is not None]
        if mat and len(ok) >= max(1, math.ceil(ti_le * len(mat))):
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


def thong_so_tone(r: dict, cu: dict) -> dict:
    """Thông số sau bước Tone (+ WB đã quyết). HSL về PRESET (chuỗi luôn ghi HSL kênh da);
    Color Grading về preset khi tool từng ghi (job trả lại), không thì giữ số đang có;
    curve về mốc khi Lightroom đang mang curve mốc / curve tool (curve_reset), curve người
    dùng tự sửa thì giữ."""
    s = _tone(r, cu)
    s.update(at._hsl_goc(r))                                     # noqa: SLF001
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
    return {"da": _srgb(P, mien), "trung": _srgb(d.get("trung"), mien), "khung": _srgb(d.get("khung"), mien),
            "kieu": kieu, "mien": mien, "ngoai": ngoai,
            "h_t": math.degrees(math.atan2(lt[2], lt[1])),
            "q_t": float(math.hypot(lt[1], lt[2])) / max(float(lt[0]), 1e-6)}


def _da(px) -> tuple[float, float, float]:
    import mo_hinh_lr as mh
    return mh.thong_ke_da(px)


def _trang(px) -> tuple[float, float] | None:
    """(a, b) trung vị VÙNG TRẮNG (L 0.62–0.96, chroma < 0.025) — như do_anh_duyet."""
    import mo_hinh_lr as mh
    if px is None or not len(px):
        return None
    lab = mh.lab_cua(px)
    m = (lab[:, 0] >= 0.62) & (lab[:, 0] <= 0.96) & (np.hypot(lab[:, 1], lab[:, 2]) < 0.025)
    if m.sum() < 50:
        return None
    return float(np.median(lab[m, 1])), float(np.median(lab[m, 2]))


# ------------------------------------------------------------------ chuỗi
_XOA = ("hsl_ghi", "hsl_moi", "hsl_thieu_cot", "da_lech0", "da_lech1", "da_duyet", "da_goc",
        "mau_da_bao", "_md", "curve_ghi_mot_luot", "curve_bao_mot_luot", "du_doan_lr", "gr_ghi",
        "gr_mid", "gr_hi", "_gr_v", "gr_thieu_cot")


def chuoi(items: list, cfg: dict, folder=None) -> dict:
    """Chuỗi một lượt cho các ảnh `items` (cả cảnh — xem chon_duong). Trả tóm tắt kiểu
    MAU_DA (+ "mot_luot")."""
    import curve_da
    on_h = float(cfg.get("da_on_hue") or 3.0)
    on_c = float(cfg.get("da_on_chroma") or 0.10)
    phan = float(cfg.get("hsl_da_cuoi_phan") or 0.8)
    tran_h, tran_s = (float(v) for v in (cfg.get("hsl_da_cuoi_tran") or (15, 20)))
    hsl_bat = bool(cfg.get("hsl_da_cuoi") or cfg.get("hsl_da_ky_yeu"))
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
          "grade_bat": bool(cfg.get("grade")), "grade_n": 0,
          "mot_luot": {"anh": 0, "canh": 0, "curve": 0, "ngoai_pham_vi": 0}}
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

    #  ---- 1. TONE
    for r in items:
        if id(r) not in mm:
            continue
        m = mm[id(r)]
        m["s"] = thong_so_tone(r, m["cu"])
        L, h, q = _da(du(r, m["s"]))
        m.update(L=L, h0=h, q0=q, dh0=at._goc_lech(m["mau"]["h_t"] - h),     # noqa: SLF001
                 lr0=math.log(m["mau"]["q_t"] / max(q, 1e-9)))
        r["da_lech0"] = (round(m["dh0"], 1), round(math.exp(m["lr0"]), 3))

    #  ---- 2. HSL Cam — một mức mỗi cảnh, hệ số theo mô hình tại hue da
    def he_so(r):
        m = mm[id(r)]
        s = m["s"]
        h_ = _da(du(r, dict(s, HueAdjustmentOrange=_f(s.get("HueAdjustmentOrange")) + 10)))[1]
        q_ = _da(du(r, dict(s, SaturationAdjustmentOrange=_f(s.get("SaturationAdjustmentOrange")) + 10)))[2]
        return (at._goc_lech(h_ - m["h0"]) / 10.0, math.log(max(q_, 1e-9) / max(m["q0"], 1e-9)) / 10.0)  # noqa: SLF001
    muc_canh: dict = {}
    us, vs = [], []
    for canh, ds in theo_canh.items():
        dung = [r for r in ds if id(r) in mm]
        if not dung or not hsl_bat:
            continue
        #  hệ số của mô hình tại hue da (trung vị cảnh); mô hình không thấy phản ứng
        #  (da ngoài dải Cam…) -> hằng số đo tay cũ
        ks = np.array([he_so(r) for r in dung])
        k_h, k_s = float(np.median(ks[:, 0])), float(np.median(ks[:, 1]))
        if not k_h > 0.05:
            k_h = float(cfg.get("hsl_da_k_hue") or 0.418)
        if not k_s > 0.002:
            k_s = float(cfg.get("hsl_da_k_sat") or 0.01085)
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
        muc_canh[canh] = (ui, vi, k_h, k_s)
        if ui or vi:
            kq["hsl"]["canh_chinh"] += 1
            us.append(ui)
            vs.append(vi)
        else:
            kq["hsl"]["canh_on"] += 1
    if us:
        kq["hsl"]["hue"], kq["hsl"]["sat"] = int(np.median(us)), int(np.median(vs))
    for r in items:
        #  tắt ô HSL -> mức 0 (trả số preset cho ảnh tool từng ghi), như chuoi_mau_da_mau;
        #  bật mà cảnh chưa đo được da -> không đụng
        if r.get("bw") or (hsl_bat and r.get("scene") not in muc_canh):
            continue
        ui, vi = muc_canh[r.get("scene")][:2] if hsl_bat else (0, 0)
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
    if cfg.get("curve_da") or cfg.get("curve_chay"):
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
            cfg_cv = dict(cfg, curve_mien=m0.curve["mien"], curve_kieu_tong=m0.curve["kieu"])
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
            m["h_cv"], m["q_cv"] = _da(du(r, m["s"]))[1:]

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
        if not cfg.get("grade") or id(r) not in mm:
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
    kq["grade_n"] = at._grade_hoan_tat(items, cfg, tran_cg)                # noqa: SLF001

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
        r["du_doan_lr"] = {"L": round(L, 4), "h": round(h, 2), "q": round(q, 4),
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
            "cg": (int(r.get("gr_hue") or 0), int(r.get("gr_sat") or 0)) if r.get("gr_ghi") else None,
            "sau_cg": (round(h, 1), round(q, 4))}
        bao.append(r["mau_da_bao"])
    if bao:
        kq["n"] = kq["n_lr"] = len(bao)
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
    return {"h": round(h, 2), "q": round(q, 4), "dh": round(dh, 2), "dq": round(dq, 4),
            "ngoai_on": bool(ngoai_on), "lech": bool((dh > LECH_H or dq > LECH_Q) and ngoai_on)}


def soat(ds: list, do_mau: dict, cfg: dict) -> dict:
    """ds: ảnh chuỗi một lượt vừa áp; do_mau {id(r): do_anh} của ảnh soát. Gắn r["soat_lr"];
    ảnh cần lượt 2 có r["curve_ghi"] (curve ghép lên curve vừa áp). -> tóm tắt."""
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
    if not (cfg.get("curve_da") or cfg.get("curve_chay")):
        kq["anh_sua"] = [theo[k] for k in can]
        return kq
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
    kq["anh_sua"] = [r for r in ds_sua if r.get("curve_ghi")]
    kq["sua"] = len(kq["anh_sua"])
    return kq


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
