#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mat do lech khoi khung — kiem bang plan()/decide() THAT, khong dung lai logic.

CHUYEN DANG CANH (buoi HPC 25nam/TEST, 29/9)
    NDT09826 bi keo -0.87 trong khi hang xom cung khung, cung thong so may dung
    o -0.19..-0.33. Do sang khung y nguyen, chi phep do MAT nhay len -0.51.

BON TINH HUONG
    1. Tat (mac dinh) -> y het truoc: tam lech van lech.
    2. Bat -> tam lech ve sat hang xom.
    3. Bat, nhung hai tam lien nhau CUNG bo cuc khac (cap 09869/09870) -> khong
       dung toi. Ban dau khong co dieu kien bo cuc, no day 09869 xuong -0.45
       trong khi 09870 y het khung dung o +0.45: tu tao ra dung benh can chua.
    4. Bat, cung bo cuc nhung KHUNG sang han len -> anh sang doi that, khong
       dung toi.
    5. Chay bat roi chay tat tren CUNG items (GUI lam vay khi doi tuy chon) ->
       phai tra ve so goc.
"""
from __future__ import annotations

import io
import contextlib
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at          # noqa: E402
import test_san_phang as ts    # noqa: E402

T0 = datetime(2026, 9, 29, 20, 0, 0)
SIG_A = [0.40, 0.35, 0.30, 0.25] * 3
SIG_B = [0.10, 0.60, 0.20, 0.70] * 3      # bo cuc khac han


def loat(mat, khung=None, sig=None):
    ds = []
    for i, m in enumerate(mat):
        r = ts._anh(f"NDT{i:05d}", m, T0 + timedelta(seconds=4 * i))
        r["metered_subject_ev"] = (khung[i] if khung else -1.70)
        r["scene_sig"] = list(sig[i] if sig else SIG_A)
        r["iso"], r["fnumber"], r["exposure_time"] = 320, 2.8, 1 / 200
        ds.append(r)
    return ds


def chay(ds, **kw):
    #[[ 3/10: dong_bo_loat (BAT mac dinh) ep ca loat cung khung + cung thong so
    #   ve MOT muc — dung loat bai nay dung. Bai nay kiem RIENG
    #   sua_mat_lech_khung nen tat no; luat loat co bai rieng
    #   (test_dong_bo_loat.py). ]]
    kw.setdefault("dong_bo_loat", False)
    cfg = ts._cfg(**kw)
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        at.plan(ds, cfg, None, None)
    return {Path(r["path"].replace("\\\\", "/")).stem[-5:]: r for r in ds}


def d(kq, k):
    return float(kq[k]["delta_ev"])


def main() -> int:
    loi = []
    MAT = [-1.10, -1.15, -1.05, -0.40, -1.12, -1.08, -1.11]

    # 1 — tat
    kq = chay(loat(MAT))
    if abs(d(kq, "00003") - d(kq, "00002")) < 0.4:
        loi.append(f"Tat: tam lech phai con lech (dung hanh vi cu), "
                   f"{d(kq, '00003'):+.2f} vs {d(kq, '00002'):+.2f}")

    # 2 — bat
    kq = chay(loat(MAT), mat_lech_khung_ev=0.5)
    ke = [d(kq, k) for k in ("00002", "00004")]
    if abs(d(kq, "00003") - sum(ke) / 2) > 0.10:
        loi.append(f"Bat: tam lech phai ve sat hang xom, {d(kq, '00003'):+.2f} "
                   f"vs {ke}")
    if "do-mat-lech-khung" not in kq["00003"]["notes"]:
        loi.append("Bat: khong de lai dau vet do-mat-lech-khung")
    if any("do-mat-lech-khung" in kq[k]["notes"] for k in kq if k != "00003"):
        loi.append("Bat: dung nham tam khong lech")

    # 3 — cap cung bo cuc khac, mat toi hon ca loat
    mat3 = [-1.10, -1.15, -1.05, -2.55, -2.56, -1.08, -1.11]
    sig3 = [SIG_A, SIG_A, SIG_A, SIG_B, SIG_B, SIG_A, SIG_A]
    kq = chay(loat(mat3, sig=sig3), mat_lech_khung_ev=0.5)
    if abs(d(kq, "00003") - d(kq, "00004")) > 0.05:
        loi.append(f"Cap cung khung ra hai muc: {d(kq, '00003'):+.2f} vs "
                   f"{d(kq, '00004'):+.2f} — dieu kien bo cuc khong chay")
    if any("do-mat-lech-khung" in kq[k]["notes"] for k in ("00003", "00004")):
        loi.append("Cap bo cuc khac bi coi la do mat hong")

    # 4 — khung sang han len cung mat: anh sang doi that
    khung4 = [-1.70, -1.70, -1.70, -1.00, -1.70, -1.70, -1.70]
    kq = chay(loat(MAT, khung=khung4), mat_lech_khung_ev=0.5)
    if "do-mat-lech-khung" in kq["00003"]["notes"]:
        loi.append("Khung sang len 0.7 EV ma van coi la do mat hong")

    # 5 — bat roi tat tren cung items
    ds = loat(MAT)
    chay(ds, mat_lech_khung_ev=0.5)
    kq = chay(ds)
    if abs(float(kq["00003"]["metered_face_ev"]) - (-0.40)) > 1e-6:
        loi.append(f"Tat lai khong tra so goc: mat = "
                   f"{kq['00003']['metered_face_ev']}")

    for m in loi:
        print("  [!]", m)
    print("TAT CA DAT" if not loi else f"{len(loi)} LOI")
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
