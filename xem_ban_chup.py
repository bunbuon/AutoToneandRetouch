#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xem_ban_chup.py — Đọc bản chụp nguyên trạng (_autotone_da_sua_*.tsv) và
đối chiếu với lần tool đẩy thông số gần nhất của buổi đó.

    python xem_ban_chup.py "G:\\2609"
    python xem_ban_chup.py "G:\\2609\\_autotone_da_sua_20260929_150000.tsv"

CHỈ ĐỌC. Trả lời ba câu:
    1. Bản chụp có đủ ảnh không, đọc được hết không.
    2. Anh đã đổi WB (Temperature / Tint) ở bao nhiêu ảnh so với cái tool ghi.
    3. Đổi về phía nào, bao nhiêu — con số thô để bước học WB bắt đầu.

doc_ban_chup() để các công cụ học sau này dùng chung, không ai tự viết lại
cách đọc file này.
"""
from __future__ import annotations

import csv
import io
import json
import ntpath
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TIEN_TO = "_autotone_da_sua_"


def ten(p: str) -> str:
    return ntpath.splitext(ntpath.basename(str(p)))[0].strip().lower()


def ban_moi_nhat(thu_muc: Path) -> Path | None:
    ds = sorted(thu_muc.glob(TIEN_TO + "*.tsv"))
    return ds[-1] if ds else None


def doc_ban_chup(p: Path) -> dict:
    """{ten_anh: {"path", "rating", "s": dict thong so day du}}. Dong hong thi bo
    qua va dem, khong lam sap ca file."""
    out, hong = {}, 0
    with io.open(p, encoding="utf-8", newline="") as fh:
        next(fh, None)
        for dong in fh:
            dong = dong.rstrip("\r\n")
            if not dong:
                continue
            try:
                path, sao, js = dong.split("\t", 2)
                out[ten(path)] = {"path": path, "rating": int(float(sao or 0)),
                                  "s": json.loads(js)}
            except (ValueError, json.JSONDecodeError):
                hong += 1
    if hong:
        print(f"[!] {hong} dong doc hong trong {p.name}", file=sys.stderr)
    return out


def lan_ghi_cuoi(buoi: str) -> dict:
    """Thong so tool da day o job apply_*_<buoi>.done gan nhat."""
    jobs = HERE / "AutoTone.lrplugin" / "jobs"
    ds = sorted(jobs.glob(f"apply_*_{buoi}.done"))
    if not ds:
        return {}
    out = {}
    with io.open(ds[-1], encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            out[ten(r["path"])] = r
    return out


def _so(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main(argv=None) -> int:
    a = (argv or sys.argv[1:])
    if not a:
        print(__doc__)
        return 2
    p = Path(a[0])
    if p.is_dir():
        f = ban_moi_nhat(p)
        if f is None:
            print(f"Khong thay {TIEN_TO}*.tsv nao trong {p}")
            return 1
        buoi = p.name
    else:
        f, buoi = p, p.parent.name
    d = doc_ban_chup(f)
    sao = {}
    for v in d.values():
        sao[v["rating"]] = sao.get(v["rating"], 0) + 1
    so_truong = sorted(len(v["s"]) for v in d.values())
    print(f"Ban chup: {f}")
    print(f"  {len(d)} anh | theo sao: {dict(sorted(sao.items()))}")
    if so_truong:
        print(f"  moi anh {so_truong[0]}-{so_truong[-1]} truong thong so")

    tool = lan_ghi_cuoi(buoi)
    if not tool:
        print(f"\n(Khong thay apply_*_{buoi}.done — khong doi chieu duoc voi tool)")
        return 0
    dt, di, n, doi = [], [], 0, 0
    for k, v in d.items():
        if v["rating"] == 1 or k not in tool:
            continue
        t0, i0 = _so(tool[k].get("Temperature")), _so(tool[k].get("Tint"))
        t1, i1 = _so(v["s"].get("Temperature")), _so(v["s"].get("Tint"))
        if None in (t0, i0, t1, i1):
            continue
        n += 1
        if abs(t1 - t0) >= 1 or abs(i1 - i0) >= 1:
            doi += 1
            dt.append(t1 - t0)
            di.append(i1 - i0)
    print(f"\nDoi chieu voi lan tool ghi gan nhat ({n} anh khong 1 sao co ca hai ben):")
    print(f"  so anh ban da doi WB: {doi} ({100.0 * doi / max(n, 1):.0f}%)")
    if dt:
        dt.sort(); di.sort()
        m = len(dt) // 2
        print(f"  Temperature anh sua - tool: trung vi {dt[m]:+.0f}K, "
              f"khoang {dt[len(dt) // 10]:+.0f}..{dt[len(dt) * 9 // 10]:+.0f}K (10-90%)")
        print(f"  Tint        anh sua - tool: trung vi {di[m]:+.0f}, "
              f"khoang {di[len(di) // 10]:+.0f}..{di[len(di) * 9 // 10]:+.0f} (10-90%)")
        am = sum(1 for x in dt if x > 0)
        print(f"  anh keo AM hon tool: {am}, LANH hon tool: {len(dt) - am}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
