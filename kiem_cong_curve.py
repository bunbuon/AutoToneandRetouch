# -*- coding: utf-8 -*-
"""CỔNG curve da + nén cháy trên ảnh LIGHTROOM THẬT (13/10) — máy Windows.

Luật dự án: ngưỡng đặt TRƯỚC khi chạy, không nới. Ngưỡng ở NGUONG dưới đây (và trong
CLAUDE.md mục "Curve da + nén cháy"). Trượt -> giữ TẮT, ghi lý do.

QUY TRÌNH (hai buổi CHƯA dùng khi làm tính năng: một cưới có mẫu da, một sự kiện LED)
  1. Mở app bằng KIEM_CONG_CURVE.bat mo  (đặt AUTOTONE_CURVE_GIU_ANH=1: lượt 2 giữ ảnh
     dựng R1 + ket_qua.json), bật hai ô Curve, bấm Xử lý ảnh cho buổi cổng, chờ xong.
  2. KIEM_CONG_CURVE.bat "<thư mục buổi>"  -> script nhờ Lightroom dựng LẠI đúng các ảnh
     đó SAU job curve (R2), đo R1 / R2 bằng CHÍNH curve_da.do_anh, tính cổng, ghi
     cong_curve.txt + so_sanh_curve.pdf cạnh ket_qua.json.

CỔNG
  Da A  (ảnh có chỉnh curve kênh): trung vị |lệch hue| R2 ≤ 0.7 × R1; tỉ lệ ảnh trong
        vùng ổn (3°, 10%) tăng ≥ 10 điểm %; dự đoán (curve_bao) vs đo R2: trung vị ≤ 1.0°.
  Da B  ≤ 2% ảnh có da XẤU ĐI (hue thêm > 1.0° hoặc |ln q| thêm > 0.05);
        vùng trung tính lệch ab > 0.004 ở ≤ 2% ảnh có ≥ 0.5% khung trung tính;
        ảnh KHÔNG đổi curve: trung bình |R2 − R1| ≤ 0.5 mã.
  Cháy A ≥ 95% ảnh nén có cháy < 2% trên R2.
  Cháy B ≥ 99% ảnh nén: trung vị |ΔY| ≤ 1 mã ở điểm < 200, da lệch ≤ 1 mã.
  Chỉ báo: tỉ lệ ảnh kích nén cháy.
"""
from __future__ import annotations

import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at  # noqa: E402
import curve_da as cd  # noqa: E402
import mat_na_da as mn  # noqa: E402

NGUONG = {"da_a_hue_ti_le": 0.7, "da_a_on_tang_diem": 10.0, "da_a_du_doan_do": 1.0,
          "da_b_xau_di_pct": 2.0, "da_b_xau_hue": 1.0, "da_b_xau_lnq": 0.05,
          "da_b_trang_ab": 0.004, "da_b_trang_pct": 2.0, "da_b_trang_dien_tich": 0.005,
          "da_b_khong_doi_ma": 0.5,
          "chay_a_pct": 95.0, "chay_a_sau": 2.0, "chay_b_pct": 99.0, "chay_b_y_ma": 1.0,
          "chay_b_da_ma": 1.0}
ON_HUE, ON_Q = 3.0, 0.10


def tim_ket_qua(buoi: Path, ma: str | None) -> Path:
    import duong_dan as dd
    goc = dd.goc_du_lieu() / "do_curve" / at.ten_job(buoi.name)
    ds = sorted(goc.glob("*/ket_qua.json")) if goc.is_dir() else []
    if ma:
        ds = [p for p in ds if p.parent.name == ma]
    if not ds:
        raise SystemExit(f"Không thấy ket_qua.json trong {goc} — chạy Xử lý ảnh với "
                         "AUTOTONE_CURVE_GIU_ANH=1 (KIEM_CONG_CURVE.bat mo) trước.")
    return ds[-1]


def dung_r2(buoi: Path, anh: list, dest: Path) -> dict:
    ma = f"cong_{int(time.time())}"
    items = [{"path": a["path"], "lr_path": a.get("lr_path")} for a in anh]
    cd.yeu_cau_dung(buoi, items, dest, ma)
    het = time.time() + 60 + 2.0 * len(items)
    while time.time() < het:
        td = cd.tien_do()
        if td.get("ma") == ma and td.get("trang_thai") in ("xong", "loi", "dung"):
            break
        time.sleep(2.0)
    else:
        raise SystemExit("Hết giờ chờ Lightroom dựng R2 — Lightroom mở chưa?")
    return {at.khoa_duong_dan(p): j for p, j in cd.bang_anh()}


def _stat(do: dict, kieu: str):
    P = do.get("da_mn") if kieu == "mn" else do.get("da_cu")
    if P is None or len(P) < 50:
        return None
    return cd.hue_q(cd.thong_ke(P, do.get("mien") or "melissa"))


def _trung_tinh(a1: np.ndarray, a2: np.ndarray, mat: list) -> tuple:
    """(lệch ab trung vị R1 -> R2 trên vùng trung tính của R1, tỉ lệ khung)."""
    buoc = max(1, int(math.sqrt(a1.shape[0] * a1.shape[1] / 240_000)))
    s1, s2 = a1[::buoc, ::buoc].reshape(-1, 3), a2[::buoc, ::buoc].reshape(-1, 3)
    lab1 = cd._lab_px(at.srgb_to_linear(s1))                           # noqa: SLF001
    lab2 = cd._lab_px(at.srgb_to_linear(s2))                           # noqa: SLF001
    tt = ((lab1[:, 0] >= 0.30) & (lab1[:, 0] <= 0.96) & (np.hypot(lab1[:, 1], lab1[:, 2]) < 0.025)
          & ~at.skin_mask(s1))
    if not tt.any():
        return 0.0, 0.0
    return (float(math.hypot(np.median(lab2[tt, 1] - lab1[tt, 1]), np.median(lab2[tt, 2] - lab1[tt, 2]))),
            float(tt.mean()))


def cong(buoi: Path, ma: str | None = None) -> dict:
    f = tim_ket_qua(buoi, ma)
    kq = json.loads(f.read_text(encoding="utf-8"))
    job = kq.get("job")
    if job and at.job_state(Path(job)) not in ("xong",):
        raise SystemExit(f"Job curve {job} chưa áp xong ({at.job_state(Path(job))}).")
    anh = [a for a in kq["anh"] if a.get("jpg") and Path(a["jpg"]).exists()]
    r2 = dung_r2(buoi, anh, f.parent / "R2")
    cfg = dict(at.DEFAULTS, curve_da=True, curve_chay=True)
    da_rows, chay_rows, khong_doi, cap = [], [], [], []
    for a in anh:
        j2 = r2.get(at.khoa_duong_dan(a.get("lr_path") or a["path"]))
        if not j2:
            continue
        r = {k: a.get(k) for k in cd.KHOA_R_CONG if k in a}
        d1, d2 = cd.do_anh(r, a["jpg"], cfg), cd.do_anh(r, j2, cfg)
        i1 = np.asarray(Image.open(a["jpg"]).convert("RGB"), dtype=np.float32) / 255.0
        i2 = np.asarray(Image.open(j2).convert("RGB"), dtype=np.float32) / 255.0
        if i1.shape != i2.shape:
            continue
        bao = a.get("curve_bao") or {}
        da_b, ch_b = bao.get("da") or {}, bao.get("chay") or {}
        if not a.get("curve_ghi"):
            khong_doi.append(float(np.abs(i2 - i1).mean() * 255))
            continue
        dong = [Path(a["path"]).name]
        if any(abs(v) >= 0.5 for v in bao.get("delta_ma") or [0]) and "h_t" in da_b:
            s1, s2 = _stat(d1, da_b.get("kieu", "cu")), _stat(d2, da_b.get("kieu", "cu"))
            if s1 and s2:
                ht, qt = da_b["h_t"], da_b["q_t"]
                lab, tl = _trung_tinh(i1, i2, d1.get("mat") or [])
                da_rows.append({"h1": abs(cd._goc(s1[0] - ht)), "h2": abs(cd._goc(s2[0] - ht)),  # noqa: SLF001
                                "q1": abs(math.log(s1[1] / qt)), "q2": abs(math.log(s2[1] / qt)),
                                "on1": abs(cd._goc(s1[0] - ht)) <= ON_HUE and abs(s1[1] / qt - 1) <= ON_Q,  # noqa: SLF001
                                "on2": abs(cd._goc(s2[0] - ht)) <= ON_HUE and abs(s2[1] / qt - 1) <= ON_Q,  # noqa: SLF001
                                "du_doan": abs(cd._goc(float(da_b.get("h1", s1[0])) - s2[0])),  # noqa: SLF001
                                "trang": lab, "trang_dt": tl})
                dong.append(f"da {s1[0]:.1f}°/{s1[1]:.3f} → {s2[0]:.1f}°/{s2[1]:.3f}  (đích {ht:.1f}°/{qt:.3f})"
                            f" · Δ R/G/B {bao.get('delta_ma')} mã")
        if ch_b.get("d"):
            y1 = at.srgb_to_linear(i1) @ at._SRGB_XYZ[1]                    # noqa: SLF001
            duoi = i1.max(axis=2) < 200 / 255
            dy = np.abs(i2 - i1).max(axis=2)[duoi] * 255 if duoi.any() else np.zeros(1)
            m = mn.mat_na((i1 * 255).astype(np.uint8), r)
            da_dich = float(np.abs(i2 - i1)[m["da"]].mean() * 255) if m["n"] else 0.0
            chay_rows.append({"sau": d2["chay_pct"], "dy": float(np.median(dy)), "da": da_dich})
            dong.append(f"cháy {d1['chay_pct']:.2f}% → {d2['chay_pct']:.2f}% · đỉnh −{ch_b['d']} mã")
            del y1
        cap.append({"ten": Path(a["path"]).name, "r1": a["jpg"], "r2": j2,
                    "mat": (d1.get("mat") or [None])[0], "chu": dong})
    N = NGUONG
    ket = {"anh": len(anh), "da": len(da_rows), "chay": len(chay_rows), "khong_doi": len(khong_doi)}
    if da_rows:
        h1 = float(np.median([x["h1"] for x in da_rows]))
        h2 = float(np.median([x["h2"] for x in da_rows]))
        on1 = 100.0 * np.mean([x["on1"] for x in da_rows])
        on2 = 100.0 * np.mean([x["on2"] for x in da_rows])
        dd = float(np.median([x["du_doan"] for x in da_rows]))
        xau = 100.0 * np.mean([(x["h2"] > x["h1"] + N["da_b_xau_hue"]) or (x["q2"] > x["q1"] + N["da_b_xau_lnq"])
                               for x in da_rows])
        tt = [x for x in da_rows if x["trang_dt"] >= N["da_b_trang_dien_tich"]]
        trang = 100.0 * np.mean([x["trang"] > N["da_b_trang_ab"] for x in tt]) if tt else 0.0
        ket.update(da_a=(h2 <= N["da_a_hue_ti_le"] * h1 and on2 - on1 >= N["da_a_on_tang_diem"]
                         and dd <= N["da_a_du_doan_do"]),
                   da_b=(xau <= N["da_b_xau_di_pct"] and trang <= N["da_b_trang_pct"]),
                   da_so=dict(hue_r1=h1, hue_r2=h2, on_r1=on1, on_r2=on2, du_doan=dd, xau_di_pct=xau,
                              trang_lech_pct=trang, trang_n=len(tt)))
    if khong_doi:
        ket["khong_doi_ma"] = float(np.mean(khong_doi))
        ket["da_b"] = bool(ket.get("da_b", True) and ket["khong_doi_ma"] <= N["da_b_khong_doi_ma"])
    if chay_rows:
        a_ = 100.0 * np.mean([x["sau"] < N["chay_a_sau"] for x in chay_rows])
        b_ = 100.0 * np.mean([x["dy"] <= N["chay_b_y_ma"] and x["da"] <= N["chay_b_da_ma"] for x in chay_rows])
        ket.update(chay_a=a_ >= N["chay_a_pct"], chay_b=b_ >= N["chay_b_pct"],
                   chay_so=dict(sau_duoi_2=a_, giu_trung_tong=b_, ti_le_kich=100.0 * len(chay_rows) / max(1, len(anh))))
    dong = [f"CỔNG CURVE · {buoi} · {datetime.now():%Y-%m-%d %H:%M}", f"ket_qua: {f}",
            f"ngưỡng: {json.dumps(NGUONG, ensure_ascii=False)}",
            json.dumps(ket, ensure_ascii=False, indent=1, default=lambda v: v.item() if hasattr(v, "item") else str(v))]
    for k in ("da_a", "da_b", "chay_a", "chay_b"):
        if k in ket:
            dong.append(f"{k}: {'ĐẠT' if ket[k] else 'TRƯỢT'}")
    (f.parent / "cong_curve.txt").write_text("\n".join(dong) + "\n", encoding="utf-8")
    print("\n".join(dong))
    try:
        import so_sanh_curve
        cap.sort(key=lambda c: -len(c["chu"]))
        p = so_sanh_curve.lap_pdf(cap[:60], f.parent / "so_sanh_curve.pdf", f"Curve da + nén cháy · {buoi.name}")
        print(f"PDF: {p}")
    except Exception as ex:                                       # noqa: BLE001
        print(f"(không lập được PDF: {ex})")
    return ket


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    cong(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else None)
