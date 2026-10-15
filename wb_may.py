"""Nhớ độ lệch WB As Shot THEO MÁY qua các buổi — wb_may.json (15/10).

User 15/10 chọn "Nhớ lệch WB theo máy" (bản cài cho thợ dùng máy ảnh khác nhau). K trong
MakerNote của máy KHÔNG trùng thang Adobe: lệch = 1e6/K_adobe − 1e6/K_máy (mired). Trước
chỉ có bảng 4 máy của dev (autotone DEFAULTS wb_asshot_lech_mired) + số học trong chính
buổi (≥ 3 cặp K máy / As Shot thật). Nay số học được của mỗi buổi được GHI LẠI:

  · ghi_buoi(buổi, autotone.ASSHOT_BUOI) — sau khi phân tích (app, nguồn catalog); chỉ máy
    có ≥ 3 cặp và IQR ≤ 12 mired (ổn định); một buổi một dòng (phân tích lại = ghi đè);
    giữ 20 buổi gần nhất mỗi máy.
  · bang_cfg(trừ_buổi) -> cfg["wb_asshot_da_hoc"] = {MODEL: {"lech", "n"}}: trung vị có
    trọng số (số cặp) của các buổi, TRỪ buổi đang mở (số trong buổi đã có ở ASSHOT_BUOI —
    không đếm hai lần). autotone.lech_asshot trộn hai nguồn.

Chỉ Sony / Nikon ghi K trong MakerNote; máy khác không có cặp -> không ghi gì, y như cũ.
"""
from __future__ import annotations

import json
from datetime import datetime

import duong_dan as dd

TEN_TEP = "wb_may.json"
TOI_THIEU_CAP = 3
IQR_TOI_DA = 12.0               # mired
GIU_BUOI = 20


def _tep():
    return dd.du_lieu(TEN_TEP)


def doc() -> dict:
    """{"may": {MODEL: [{"buoi", "lech", "n", "iqr", "luc"}]}} — hỏng / thiếu thì rỗng."""
    try:
        d = json.loads(_tep().read_text(encoding="utf-8"))
        if isinstance(d, dict) and isinstance(d.get("may"), dict):
            return d
    except (OSError, ValueError):
        pass
    return {"may": {}}


def khoa_buoi(folder) -> str:
    import autotone as at
    return at.khoa_duong_dan(str(folder))


def ghi_buoi(folder, bang: dict) -> int:
    """Ghi số học trong buổi (autotone.ASSHOT_BUOI). -> số máy đã ghi."""
    if not bang:
        return 0
    kb = khoa_buoi(folder)
    d = doc()
    n = 0
    for model, v in dict(bang).items():
        try:
            so, iqr, lech = int(v["n"]), float(v.get("iqr") or 0.0), float(v["lech"])
        except (KeyError, TypeError, ValueError):
            continue
        if so < TOI_THIEU_CAP or iqr > IQR_TOI_DA or abs(lech) > 60.0:
            continue
        ds = [x for x in d["may"].get(str(model).upper(), []) if x.get("buoi") != kb]
        ds.append({"buoi": kb, "lech": round(lech, 2), "n": so, "iqr": round(iqr, 2),
                   "luc": datetime.now().isoformat(timespec="seconds")})
        d["may"][str(model).upper()] = sorted(ds, key=lambda x: str(x.get("luc", "")))[-GIU_BUOI:]
        n += 1
    if n:
        try:
            dd.ghi_ben(_tep(), json.dumps(d, ensure_ascii=False, indent=1))
        except OSError:
            return 0
    return n


def _trung_vi_trong_so(ds: list) -> float:
    ds = sorted(ds, key=lambda x: x[0])
    tong = sum(w for _v, w in ds)
    tich = 0.0
    for v, w in ds:
        tich += w
        if tich >= tong / 2:
            return float(v)
    return float(ds[-1][0])


def bang_cfg(tru_buoi=None) -> dict:
    """{MODEL: {"lech": trung vị có trọng số, "n": tổng số cặp, "buoi": số buổi}}."""
    kb = khoa_buoi(tru_buoi) if tru_buoi else None
    out = {}
    for model, ds in doc()["may"].items():
        dung = []
        for x in ds or []:
            if kb is not None and x.get("buoi") == kb:
                continue
            try:
                dung.append((float(x["lech"]), max(1, int(x["n"]))))
            except (KeyError, TypeError, ValueError):
                continue
        if dung:
            out[model] = {"lech": round(_trung_vi_trong_so(dung), 2),
                          "n": sum(w for _v, w in dung), "buoi": len(dung)}
    return out
