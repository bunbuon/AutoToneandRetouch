#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""retouch_preset.py — Preset mức kéo retouch (9/10).

User: "Cần thêm tính năng tạo preset thông số đã chọn để sử dụng cho các lần
sau nhanh và tiện hơn."

Một preset = MỘT bộ mức phẳng đúng dạng muc_day_du() của màn Retouch
({"vet": 60, "min_da": 40, "nam:vet": 30}) — gồm cả mức riêng theo nhóm mặt
(user 9/10 chốt: "đúng"). Lưu ở <dữ liệu app>/retouch_preset/<tên>.json, mỗi
preset một file: xoá / chép / sao lưu từng cái được, không đụng nhau.

Tên preset là tên file: bỏ ký tự cấm của Windows, bỏ khoảng trắng hai đầu.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import duong_dan as dd

TEN_THU_MUC = "retouch_preset"
_CAM = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def thu_muc() -> Path:
    return dd.du_lieu(TEN_THU_MUC, "x").parent


def ten_hop_le(ten: str) -> str:
    """Tên người dùng gõ -> tên dùng được làm tên file ("" nếu không còn gì)."""
    t = _CAM.sub(" ", str(ten or "")).strip().strip(".")
    t = re.sub(r"\s+", " ", t)
    return t[:60]


def _tep(ten: str) -> Path:
    return thu_muc() / f"{ten}.json"


def danh_sach() -> list[str]:
    """Tên các preset đang có, xếp theo chữ (không phân biệt hoa thường)."""
    try:
        return sorted((p.stem for p in thu_muc().glob("*.json")), key=str.lower)
    except OSError:
        return []


def doc(ten: str) -> dict | None:
    """Bộ mức của preset (None nếu không có / hỏng)."""
    ten = ten_hop_le(ten)
    if not ten:
        return None
    try:
        d = json.loads(_tep(ten).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    m = d.get("muc") if isinstance(d, dict) else None
    if not isinstance(m, dict):
        return None
    ra = {}
    for k, v in m.items():
        try:
            ra[str(k)] = float(v)
        except (TypeError, ValueError):
            continue
    return ra


def ghi(ten: str, muc: dict) -> str:
    """Lưu / ghi đè một preset. -> tên đã chuẩn hoá. ValueError khi tên rỗng."""
    ten = ten_hop_le(ten)
    if not ten:
        raise ValueError("tên preset rỗng")
    m = {}
    for k, v in (muc or {}).items():
        try:
            m[str(k)] = round(float(v), 1)
        except (TypeError, ValueError):
            continue
    f = _tep(ten)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".part")
    tmp.write_text(json.dumps({"ten": ten, "muc": m,
                               "luc": datetime.now().isoformat(timespec="seconds")},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, f)
    return ten


def xoa(ten: str) -> bool:
    ten = ten_hop_le(ten)
    if not ten:
        return False
    try:
        _tep(ten).unlink()
        return True
    except OSError:
        return False


def giong(a: dict, b: dict) -> bool:
    """Hai bộ mức có coi như một không (mức 0 / thiếu như nhau, sai số 0,05)."""
    def chuan(m):
        ra = {}
        for k, v in (m or {}).items():
            try:
                gt = round(float(v), 1)
            except (TypeError, ValueError):
                continue
            if gt > 0:
                ra[str(k)] = gt
        return ra
    return chuan(a) == chuan(b)
