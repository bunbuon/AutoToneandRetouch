#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tao_ban_cap_nhat.py — dong goi MOT ban cap nhat code (+model) de len Releases.

VIEC NAY LAM GI
    Tao file app-<ver>-<nen>.zip chua CODE MOI (loi da ma hoa .pyd/.so + plumbing
    .py) va, neu muon, ca mo_hinh/ retouch moi. Roi in ra khoi JSON de dan vao
    latest.json tren GitHub Releases (tag app-latest). App dang chay se thay,
    hoi nguoi dung, tai ve va LAN MO SAU tu dung ban moi — khong cai lai.

    Chi dong CODE, khong dong torch/python runtime: nguyen muc dich cua OTA la
    tranh tai lai vai GB. torch van di qua tai_nguyen.py nhu cu.

CHAY TREN MAY DICH — GIONG dong_goi.py
    .pyd phai dich TREN Windows, .so TREN Mac. Script lay dung nen tang may
    dang chay (cap_nhat.nen_may) va chi tao ban cho nen do. Muon ca Win lan Mac
    thi chay tren tung may roi gop hai khoi 'nen' vao cung mot latest.json.

VI DU
    # Tren Windows, ban chi sua logic (khong doi model):
    python tao_ban_cap_nhat.py --ver 2026.10.11 --ghi-chu "Sua cv"

    # Kem model retouch moi:
    python tao_ban_cap_nhat.py --ver 2026.10.11 --mo-hinh ../ToolCloneEvoto/mo_hinh

    # Ban .py THUAN (khong ma hoa — chay moi he, tien cho sua vat plumbing):
    python tao_ban_cap_nhat.py --ver 2026.10.11 --khong-ma-hoa
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

GOC = Path(__file__).resolve().parent
sys.path.insert(0, str(GOC))

import cap_nhat as cn


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def dung_noi_dung(ver: str, ma_hoa: bool, mo_hinh: Path | None,
                  them_py=None) -> Path:
    """Dung thu muc tam chua noi dung ban cap nhat. -> thu muc do.

    ma_hoa=True : loi (bao_mat.MA_HOA) -> .pyd/.so, phan con lai .py.
    ma_hoa=False: tat ca .py (ban chay moi he).
    """
    import bao_mat
    ra = GOC / "build" / f"ban_cap_nhat_{ver}"
    if ra.exists():
        shutil.rmtree(ra)
    ra.mkdir(parents=True)

    #[[ Cac module ship — giong dong_goi: bo file kiem/do/khoa-ky. Lay tu
    #   dong_goi.LOAI_TRU de khong lech. ]]
    import dong_goi
    bo = {Path(f).stem for f in dong_goi.LOAI_TRU}

    #[[ DANH SACH MODULE DUA VAO BAN CAP NHAT.
    #
    #   Mac dinh: mang HET module app ship (nhu goc), tru bo{}. The thi mot ban
    #   cap nhat co the sua BAT KY module nao — khong phai doan truoc file nao se
    #   doi. Ban nho hon thi them --chi de chi dua vai file.
    #]]
    ship = [p for p in sorted(GOC.glob("*.py"))
            if p.stem not in bo and p.stem != "chay"]
    if them_py:
        chon = set(them_py)
        ship = [p for p in ship if p.stem in chon]

    ma_hoa_set = set(bao_mat.MA_HOA) if ma_hoa else set()

    n_pyd = n_py = 0
    if ma_hoa:
        ok, nhac = bao_mat.co_trinh_bien_dich()
        if not ok:
            raise SystemExit(f"  [!] {nhac}")
        if nhac:
            print("  " + nhac)

    for p in ship:
        if p.stem in ma_hoa_set:
            bao_mat.bien_dich_mot(p, ra, lang=True)
            n_pyd += 1
        else:
            #[[ Plumbing .py: gan banner ban quyen giong cay dong goi. ]]
            (ra / p.name).write_text(bao_mat.BANNER + p.read_text(encoding="utf-8"),
                                     encoding="utf-8")
            n_py += 1

    #[[ MO HINH RETOUCH (tuy chon). Chep vao mo_hinh/; app ap qua bien moi
    #   truong (cap_nhat.ap_model). Chi chep .pt/.onnx/.npz + thu muc con. ]]
    n_mh = 0
    if mo_hinh:
        mh = Path(mo_hinh)
        if not mh.is_dir():
            raise SystemExit(f"  [!] Khong thay thu muc mo hinh: {mh}")
        dich = ra / "mo_hinh"
        dich.mkdir()
        for f in sorted(mh.iterdir()):
            if f.is_dir():
                shutil.copytree(f, dich / f.name)
                n_mh += 1
            elif f.suffix in (".pt", ".onnx", ".npz"):
                shutil.copy2(f, dich / f.name)
                n_mh += 1

    print(f"  noi dung: {n_pyd} module ma hoa + {n_py} .py"
          + (f" + {n_mh} muc mo hinh" if mo_hinh else ""))
    return ra


def dong_zip(noi_dung: Path, ra_zip: Path) -> None:
    if ra_zip.exists():
        ra_zip.unlink()
    with zipfile.ZipFile(ra_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(noi_dung.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(noi_dung).as_posix())


def main(argv=None) -> int:
    for _l in (sys.stdout, sys.stderr):
        try:
            _l.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass

    ap = argparse.ArgumentParser(description="Tao mot ban cap nhat OTA.")
    ap.add_argument("--ver", required=True, help="Phien ban moi, vd 2026.10.11")
    ap.add_argument("--ghi-chu", default="", dest="ghi_chu",
                    help="Mo ta ngan hien cho nguoi dung")
    ap.add_argument("--mo-hinh", type=Path, default=None, dest="mo_hinh",
                    help="Thu muc mo_hinh retouch dua kem (tuy chon)")
    ap.add_argument("--khong-ma-hoa", action="store_true", dest="khong_ma_hoa",
                    help="Dong ban .py thuan (chay moi he, khong can trinh dich C)")
    ap.add_argument("--chi", nargs="*", default=None,
                    help="Chi dua vai module (ten khong .py). Mac dinh: tat ca.")
    a = ap.parse_args(argv)

    if not cn._hop_le(a.ver):
        print(f"  [!] Phien ban khong hop le (chi so/./-): {a.ver!r}")
        return 1
    if not cn.moi_hon(a.ver, cn.PHIEN_BAN_APP):
        print(f"  [!] {a.ver} KHONG moi hon ban hien tai (cap_nhat.PHIEN_BAN_APP "
              f"= {cn.PHIEN_BAN_APP}).")
        print("      Sua PHIEN_BAN_APP cho dung, hoac dat --ver cao hon.")
        return 1

    ma_hoa = not a.khong_ma_hoa
    nen = cn.nen_may()
    #[[ Ban ma hoa chua .pyd/.so -> gan NEN TANG vao ten file. Ban .py thuan
    #   chay moi he -> ten khong gan nen. ]]
    ten_zip = f"app-{a.ver}-{nen}.zip" if ma_hoa else f"app-{a.ver}.zip"

    print(f"  Tao ban cap nhat {a.ver} ({'ma hoa .pyd/.so' if ma_hoa else '.py thuan'}, "
          f"nen: {nen})...")
    noi_dung = dung_noi_dung(a.ver, ma_hoa, a.mo_hinh, them_py=a.chi)

    ra_dir = GOC / "dist"
    ra_dir.mkdir(exist_ok=True)
    ra_zip = ra_dir / ten_zip
    dong_zip(noi_dung, ra_zip)
    sha = _sha(ra_zip)
    mb = round(ra_zip.stat().st_size / 1048576, 1)
    print(f"\n  Da tao: {ra_zip}  ({mb} MB)")
    print(f"  SHA-256: {sha}")

    #[[ In khoi latest.json san de dan len Releases. ]]
    if ma_hoa:
        meta = {
            "moi": a.ver,
            "ghi_chu": a.ghi_chu,
            "nen": {nen: {"file_zip": ten_zip, "sha256": sha, "mb": mb}},
        }
        nhac = ("  (Ban MA HOA theo nen. Co ca Windows lan Mac thi chay script "
                "tren tung may\n   roi GOP cac khoi 'nen' lai vao mot latest.json.)")
    else:
        meta = {"moi": a.ver, "ghi_chu": a.ghi_chu,
                "file_zip": ten_zip, "sha256": sha, "mb": mb}
        nhac = "  (Ban .py thuan — chay moi he, dung chung mot file.)"

    (ra_dir / "latest.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n  ==== latest.json (da ghi ra dist/latest.json) ====")
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print(nhac)
    print("\n  CACH PHAT HANH:")
    print(f"   1. Tao/cap nhat Release tag 'app-latest' tren GitHub.")
    print(f"   2. Up file:  {ra_zip.name}")
    print(f"   3. Up (hoac thay) file: latest.json")
    print(f"   4. Doi cap_nhat.PHIEN_BAN_APP cho lan build GOI KE TIEP (de goi "
          f"moi khong tu coi minh la cu).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
