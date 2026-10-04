#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""do_buoi.py — Đo CẢ MỘT BUỔI bằng đúng analyze() của tool rồi lưu số đo ra file.

    python do_buoi.py G:\\TrainTool G:\\2609 G:\\1308

Mỗi thư mục ghi ra  Claude outputs\\do\\<buổi>\\:
    do_<buổi>.json.gz         mọi số analyze() trả về, từng ảnh
    _autotone_baseline.tsv    preset gốc trước khi tool chạm (nếu có)
    _autotone_da_sua_*.tsv    bản chụp "đáp án" mới nhất (nếu có)

VÌ SAO TÁCH BƯỚC ĐO RA (2/10/2026)
    Cổng kiem_gu.py chạy analyze() lại cho MỖI đề xuất. Lần này có năm phần
    sửa, muốn đo từng phần riêng lẫn cả năm cùng lúc — tức chạy lại analyze()
    hàng chục lần. Mà năm phần đó đều nằm ở decide()/plan(), KHÔNG ở measure():
    số đo của một ảnh không đổi dù tham số quyết định đổi thế nào. Đo một lần,
    lưu lại, rồi cho plan() chạy trên bản lưu bao nhiêu lượt cũng được.

    Đây vẫn là hàm THẬT của tool (at.collect_pairs + at.analyze) — không dựng
    lại logic đo nào. Bản lưu là đúng thứ analyze() trả về.

CHỈ ĐỌC ảnh. Không ghi gì vào thư mục buổi, không đụng catalog.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import autotone as at   # noqa: E402

#[[ DAU VET BAN MA DA DO — chot NGAY LUC NAP, khong phai luc ghi file.
#
#   Ban cu doc mtime cua autotone.py luc KET THUC. File bi chep de trong luc
#   dang do thi dau ghi la cua ban moi, ma ma da chay la ban nap tu dau.
#   3/10 phai tra loi "file do Hiu do bang ban nao" — mtime khong tra loi duoc,
#   phai so tung dong moi biet ban tren may THIEU han ban sua khung mat ao (chep
#   nham file cu). Nay ghi ca sha1 luc nap: so voi sha1 cua ban dang xet la xong.
#]]
_AT_FILE = Path(at.__file__).resolve()
AT_MTIME = _AT_FILE.stat().st_mtime
AT_SHA1 = hashlib.sha1(_AT_FILE.read_bytes()).hexdigest()


def _json(o):
    if hasattr(o, "tolist"):
        return o.tolist()
    if isinstance(o, datetime):
        return o.isoformat()
    if isinstance(o, Path):
        return str(o)
    if isinstance(o, (set, tuple)):
        return list(o)
    return str(o)


def do_mot_buoi(folder: Path, out_root: Path, jobs: int) -> int:
    ten = folder.name or str(folder).strip("\\/").replace(":", "")
    dich = out_root / ten
    dich.mkdir(parents=True, exist_ok=True)
    cfg = dict(at.DEFAULTS, source="catalog", bo_qua_nguoi_sua=False)
    pairs, _ = at.collect_pairs(folder, need_sidecar=False)
    print(f"[{ten}] {len(pairs)} anh — dang do ({jobs} tien trinh)...", flush=True)
    t0 = time.time()
    last = [0.0]

    def tien_do(xong, tong):
        if time.time() - last[0] > 10 or xong == tong:
            last[0] = time.time()
            print(f"    {xong}/{tong}", flush=True)

    items, failed = at.analyze(pairs, cfg, jobs, progress=tien_do)
    for r in items:
        r.pop("dt_obj", None)
    goi = {
        "buoi": ten, "thu_muc": str(folder),
        "khi": datetime.now().isoformat(timespec="seconds"),
        "autotone_mtime": AT_MTIME, "autotone_sha1": AT_SHA1,
        "so_anh": len(items), "loi": [dict(path=r.get("path"), error=r.get("error"))
                                       for r in failed],
        "items": items,
    }
    p = dich / f"do_{ten}.json.gz"
    with gzip.open(p.with_suffix(".part"), "wt", encoding="utf-8") as fh:
        json.dump(goi, fh, default=_json, ensure_ascii=True)
    p.with_suffix(".part").replace(p)
    for mau in ("_autotone_baseline.tsv",):
        if (folder / mau).is_file():
            shutil.copy2(folder / mau, dich / mau)
    chup = sorted(folder.glob("_autotone_da_sua_*.tsv"))
    if chup:
        shutil.copy2(chup[-1], dich / chup[-1].name)
    print(f"[{ten}] xong {len(items)} anh, {len(failed)} loi, "
          f"{time.time() - t0:.0f}s -> {p}", flush=True)
    if _AT_FILE.stat().st_mtime != AT_MTIME:
        print(f"[!] [{ten}] autotone.py DA DOI trong luc do — so do la cua ban CU "
              f"(sha1 {AT_SHA1[:10]}). Chay lai DO_BUOI.bat.", flush=True)
    return 0


def main(argv=None) -> int:
    for _l in (sys.stdout, sys.stderr):
        try:
            _l.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass
    a = [Path(x) for x in (argv or sys.argv[1:])]
    if not a:
        print(__doc__)
        return 2
    out_root = HERE / "Claude outputs" / "do"
    jobs = at.safe_jobs(8, dict(at.DEFAULTS))
    for f in a:
        if not f.is_dir():
            print(f"[!] Khong thay thu muc {f} — bo qua", flush=True)
            continue
        do_mot_buoi(f, out_root, jobs)
    (out_root / "xong.txt").write_text(datetime.now().isoformat(timespec="seconds"),
                                       encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
