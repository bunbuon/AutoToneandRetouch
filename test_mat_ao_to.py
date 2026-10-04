#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bo khung mat VUA diem thap VUA to bat thuong — kiem bang ham THAT bo_mat_ao_to().

CHUYEN DANG CANH (3/10, buoi HPC 25nam\\Hiu)
    HIU02258: anh can co tay deo vong, khong co mat. YuNet bao mot "mat" diem
    0,50 rong 514x551 tren khung 1024x683 (40% khung) — la canh tay. Tool keo
    -1,31 trong khi HIU02257 ngay canh (khong thay mat) giu 0,00.

BON TINH HUONG
    1. Khung cua HIU02258 (diem 0,50, 40% khung) -> BO.
    2. Mat that chup can (diem 0,65 — thap nhat trong 8 khung > 15% cua
       TrainTool + 2609 — rong 40% khung) -> GIU.
    3. Mat nho diem thap (khan gia phia sau, 0,52, 0,3% khung) -> GIU: diem
       thap mot minh khong du (nguong diem da bi bac bo, xem measure()).
    4. mat_ao_to_pct = 0 -> khong bo gi.
    5. Mac dinh dang BAT 15% / 0,6.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at   # noqa: E402

KHUNG = (1024, 683)
TAY_HIU02258 = (567.9, -42.5, 513.5, 551.1, 0.5006)
CAN_THAT = (300.0, 100.0, 520.0, 540.0, 0.65)
KHAN_GIA = (900.0, 200.0, 40.0, 50.0, 0.52)


def main() -> int:
    loi = []
    ds = [TAY_HIU02258, CAN_THAT, KHAN_GIA]
    giu = at.bo_mat_ao_to(ds, KHUNG, 15.0, 0.6)
    if TAY_HIU02258 in giu:
        loi.append("Khung canh tay cua HIU02258 (0.50, 40% khung) phai bi bo")
    if CAN_THAT not in giu:
        loi.append("Mat that chup can diem 0.65 bi bo nham")
    if KHAN_GIA not in giu:
        loi.append("Mat nho diem thap bi bo — diem thap MOT MINH khong duoc bo")
    if at.bo_mat_ao_to(ds, KHUNG, 0.0, 0.6) != ds:
        loi.append("mat_ao_to_pct = 0 phai giu nguyen moi khung")
    d = at.DEFAULTS
    if float(d.get("mat_ao_to_pct", 0)) != 15.0 or float(d.get("mat_ao_diem", 0)) != 0.6:
        loi.append(f"Mac dinh phai la 15% / 0.6, dang la {d.get('mat_ao_to_pct')} / {d.get('mat_ao_diem')}")
    for m in loi:
        print("  [!]", m)
    print("TAT CA DAT" if not loi else f"{len(loi)} LOI")
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
