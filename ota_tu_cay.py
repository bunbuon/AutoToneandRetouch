#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ota_tu_cay.py — đóng bản cập nhật OTA từ CHÍNH cây đã biên dịch của lần build gói.

VÌ SAO KHÔNG DÙNG tao_ban_cap_nhat.py
    tao_ban_cap_nhat biên dịch lại lõi lần nữa (MSVC / clang) và đòi --ver MỚI HƠN
    PHIEN_BAN_APP. Phát hành cùng lúc với gói (13/10, v84) thì bản OTA phải là ĐÚNG số
    phiên bản của gói (máy cũ nâng lên bản đó; gói mới cùng số thì không nạp lại) và
    đúng các .pyd / .so đã nằm trong gói vừa qua kiem_goi — biên dịch lần hai là thêm
    một lần MSVC chập chờn và một bộ nhị phân chưa ai kiểm.

LÀM GÌ
    build/nguon_bao_mat (dong_goi --bao-mat / bao_mat.dung_cay_nguon dựng ra): mọi module
    ship (như tao_ban_cap_nhat.dung_noi_dung: trừ LOAI_TRU và chay.py) — lõi lấy .pyd /
    .so, phần còn lại lấy .py có banner. Ghi dist/app-<ver>-<nen>.zip và
    dist/ota-<nen>.json = khối "nen" cho latest.json. --gop latest.json: gộp các khối
    ota-*.json (Windows + Mac) vào một latest.json.

    python ota_tu_cay.py [--ghi-chu "..."]
    python ota_tu_cay.py --gop dist/latest.json ota-win.json ota-mac-arm64.json ...
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

GOC = Path(__file__).resolve().parent
sys.path.insert(0, str(GOC))


def file_cay(cay: Path, ma_hoa: set, bo: set) -> list:
    """Danh sách file đưa vào bản OTA, lấy từ cây đã biên dịch. SystemExit khi thiếu."""
    ship = sorted(p.stem for p in GOC.glob("*.py") if p.stem not in bo)
    lay, thieu = [], []
    for ten in ship:
        if ten in ma_hoa:
            nhi_phan = [p for p in cay.glob(f"{ten}.*") if p.suffix in (".pyd", ".so")]
            (lay.append(nhi_phan[0]) if nhi_phan else thieu.append(f"{ten} (.pyd/.so)"))
        else:
            p = cay / f"{ten}.py"
            (lay.append(p) if p.is_file() else thieu.append(f"{ten}.py"))
    if thieu:
        raise SystemExit(f"  [!] Thiếu trong {cay}: {', '.join(thieu)}")
    return lay


def dong(cay: Path, ver: str, ghi_chu: str, ra: Path) -> dict:
    import bao_mat
    import cap_nhat as cn
    import dong_goi
    bo = {Path(f).stem for f in dong_goi.LOAI_TRU} | {"chay"}
    lay = file_cay(cay, set(bao_mat.MA_HOA), bo)
    nen = cn.nen_may()
    ra.mkdir(parents=True, exist_ok=True)
    z = ra / f"app-{ver}-{nen}.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in lay:
            zf.write(f, f.name)
    khoi = {"file_zip": z.name, "sha256": hashlib.sha256(z.read_bytes()).hexdigest(),
            "mb": round(z.stat().st_size / 1048576, 1)}
    meta = {"moi": ver, "ghi_chu": ghi_chu, "nen": {nen: khoi}}
    (ra / f"ota-{nen}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    nb = sum(1 for f in lay if f.suffix in (".pyd", ".so"))
    print(f"  {len(lay)} file ({nb} lõi biên dịch) -> {z} ({khoi['mb']} MB)")
    return meta


def gop(dich: Path, nguon: list) -> dict:
    """Gộp các ota-*.json (cùng phiên bản) vào một latest.json."""
    meta: dict = {}
    for p in nguon:
        m = json.loads(Path(p).read_text(encoding="utf-8"))
        if meta and m["moi"] != meta["moi"]:
            raise SystemExit(f"  [!] Khác phiên bản: {p} = {m['moi']}, đang gộp {meta['moi']}")
        if not meta:
            meta = {"moi": m["moi"], "ghi_chu": m.get("ghi_chu", ""), "nen": {}}
        meta["ghi_chu"] = meta["ghi_chu"] or m.get("ghi_chu", "")
        meta["nen"].update(m["nen"])
    dich.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return meta


def main(argv=None) -> int:
    for _l in (sys.stdout, sys.stderr):
        try:
            _l.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass
    import cap_nhat as cn
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ver", default=cn.PHIEN_BAN_APP)
    ap.add_argument("--ghi-chu", default="", dest="ghi_chu")
    ap.add_argument("--cay", type=Path, default=GOC / "build" / "nguon_bao_mat")
    ap.add_argument("--ra", type=Path, default=GOC / "dist")
    ap.add_argument("--gop", type=Path, default=None, help="latest.json cần ghi")
    ap.add_argument("nguon", nargs="*", help="(với --gop) các ota-*.json")
    a = ap.parse_args(argv)
    if a.gop:
        gop(a.gop, a.nguon)
        return 0
    if not cn._hop_le(a.ver):
        print(f"  [!] Phiên bản không hợp lệ: {a.ver!r}")
        return 1
    dong(a.cay, a.ver, a.ghi_chu, a.ra)
    return 0


if __name__ == "__main__":
    sys.exit(main())
