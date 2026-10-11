# -*- coding: utf-8 -*-
"""nhan_goi_gop_y.py — Gom gói góp ý đã nhận về đúng định dạng cổng kiem_2ban_quay.

    python nhan_goi_gop_y.py [<kho>]

Mỗi gói <kho>/<người>/<ngày>/*.zip (chưa gom) giải ra:
    Claude outputs/gop_y/<buổi>/    do_<buổi>.json.gz, _autotone_da_sua_*.tsv,
                                    _autotone_baseline.tsv, anh_nho/, meta.json, toc_do.csv
    Claude outputs/gop_y_jobs/      apply_*_<buổi>.done
Rồi chấm cả kho bằng chính cổng đáp án tay:
    python kiem_2ban_quay.py --do "Claude outputs/gop_y" --jobs "Claude outputs/gop_y_jobs"
In bảng tổng hợp: số buổi / ảnh / ảnh sửa theo THÂN MÁY và theo phiên bản app.
"""
from __future__ import annotations

import json
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOC = HERE.parent
DO = GOC / "Claude outputs" / "gop_y"
JOBS = GOC / "Claude outputs" / "gop_y_jobs"


def gom(kho: Path) -> int:
    DO.mkdir(parents=True, exist_ok=True)
    JOBS.mkdir(parents=True, exist_ok=True)
    da = DO / "_da_gom.txt"
    xong = set(da.read_text(encoding="utf-8").splitlines()) if da.is_file() else set()
    n = 0
    for z in sorted(kho.rglob("*.zip")):
        khoa = str(z.relative_to(kho))
        if khoa in xong:
            continue
        try:
            with zipfile.ZipFile(z) as zf:
                meta = json.loads(zf.read("meta.json").decode("utf-8"))
                buoi = meta["buoi"]
                d = DO / buoi
                d.mkdir(parents=True, exist_ok=True)
                for ten in zf.namelist():
                    if ten.endswith("/"):
                        continue
                    if ten.startswith("apply_") and ten.endswith(".done"):
                        (JOBS / ten).write_bytes(zf.read(ten))
                    else:
                        p = d / ten
                        p.parent.mkdir(parents=True, exist_ok=True)
                        p.write_bytes(zf.read(ten))
        except Exception as ex:                              # noqa: BLE001
            print(f"[!] {khoa}: {ex}")
            continue
        with open(da, "a", encoding="utf-8") as fh:
            fh.write(khoa + "\n")
        n += 1
    return n


def tong_hop() -> None:
    theo_may = defaultdict(lambda: [0, 0, 0])
    theo_ban = defaultdict(lambda: [0, 0, 0])
    for m in sorted(DO.glob("*/meta.json")):
        try:
            meta = json.loads(m.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for may in meta.get("than_may") or ["?"]:
            t = theo_may[may]
            t[0] += 1; t[1] += int(meta.get("so_anh") or 0); t[2] += int(meta.get("anh_sua") or 0)
        b = theo_ban[str(meta.get("phien_ban") or "?")]
        b[0] += 1; b[1] += int(meta.get("so_anh") or 0); b[2] += int(meta.get("anh_sua") or 0)
    print("\nTHEO THÂN MÁY        buổi    ảnh   ảnh sửa")
    for k, (a, b, c) in sorted(theo_may.items(), key=lambda x: -x[1][1]):
        print(f"  {k[:20]:20} {a:5} {b:6} {c:8}")
    print("\nTHEO PHIÊN BẢN       buổi    ảnh   ảnh sửa")
    for k, (a, b, c) in sorted(theo_ban.items()):
        print(f"  {k[:20]:20} {a:5} {b:6} {c:8}")


def main(argv=None) -> int:
    a = list(argv if argv is not None else sys.argv[1:])
    kho = Path(a[0]) if a else Path(json.loads((HERE / "may_nhan_gop_y.json").read_text(encoding="utf-8"))["kho"])
    n = gom(kho)
    print(f"gom {n} gói mới -> {DO}")
    tong_hop()
    print(f'\nChấm: python kiem_2ban_quay.py --do "{DO}" --jobs "{JOBS}"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
