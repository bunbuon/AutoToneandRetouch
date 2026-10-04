#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diem lay net (AF) phai xoay CUNG anh — kiem bang cach cham pixel that.

LOI DA GAP (29/9, bo 2609): Sony ghi diem AF theo toa do cam bien (khung
ngang). Anh chup doc duoc xoay de do, diem AF thi khong — roi sang cho khac,
trung mat nguoi ngoai le, va tool bo luon mat co dau chu re.

Cach kiem: voi MOI huong EXIF 1..8, dung anh khung ngang, cham mot pixel o
(u, v), cho qua apply_orientation() THAT, tim lai pixel do, so voi
af_theo_huong(). Khong tinh tay mot toa do nao.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at   # noqa: E402


def main() -> int:
    loi = []
    W, H = 600, 400
    for u, v in ((0.64, 0.51), (0.10, 0.90), (0.83, 0.12)):
        for huong in range(1, 9):
            a = np.zeros((H, W), dtype=np.uint8)
            x, y = int(u * W), int(v * H)
            a[y, x] = 255
            im = at.apply_orientation(Image.fromarray(a), huong)
            b = np.asarray(im)
            yy, xx = np.argwhere(b == 255)[0]
            that = ((xx + 0.5) / b.shape[1], (yy + 0.5) / b.shape[0])
            tinh = at.af_theo_huong((u, v), huong)
            if abs(that[0] - tinh[0]) > 0.01 or abs(that[1] - tinh[1]) > 0.01:
                loi.append(f"huong {huong}, diem {u, v}: anh that {that}, ham tra {tinh}")
    if at.af_theo_huong(None, 8) is not None:
        loi.append("Khong co diem AF thi phai tra None")

    #[[ mat_gan_af: AF roi vao CO (duoi mep o mat 0.4 lan co mat — dung nhu
    #   SAY06753) phai chon mat do, khong chon mat nguoi dung xa phia sau.
    #]]
    o = [(335, 277, 77, 100), (511, 386, 36, 48)]     # mat chu the / nguoi sau
    i, d = at.mat_gan_af(o, 369, 416, 1.0)
    if i != 0:
        loi.append(f"AF o co chu the phai chon mat 0, duoc {i} (d={d})")
    i, d = at.mat_gan_af(o, 369, 416, 0.0)
    if i is not None:
        loi.append("nguong 0 phai la TAT")
    i, d = at.mat_gan_af(o, 369, 700, 1.0)
    if i is not None:
        loi.append(f"AF xa moi mat (o chan) thi khong duoc gan cho ai, duoc {i} d={d}")
    i, d = at.mat_gan_af(o, 520, 400, 1.0)
    if i != 1 or d != 0.0:
        loi.append(f"AF nam TRONG o mat nho phai chon dung o do, d=0, duoc {i} {d}")
    #[[ Nikon AFInfo2: dung mot NEF gia toi thieu — TIFF chinh (II) chua
    #   MakerNote "Nikon\0" + TIFF rieng (MM, nguoc thu tu byte, de bat loi doc
    #   nham thu tu byte cua file chinh) + khoi 0x00B7. So lay tu HIU_4230.NEF
    #   that (ExifTool: 6048x4024, tam 3273,2588, vung 769x887).
    #]]
    import struct

    def nef_gia(ban: bytes, e_mn: str = ">"):
        khoi = bytearray(60)
        khoi[0:4] = ban
        struct.pack_into(e_mn + "6H", khoi, 0x2A, 6048, 4024, 3273, 2588, 769, 887)
        bo = b"MM" if e_mn == ">" else b"II"
        mn_tiff = bytearray(bo + struct.pack(e_mn + "HI", 42, 8))
        mn_tiff += struct.pack(e_mn + "H", 1)
        mn_tiff += struct.pack(e_mn + "HHII", 0x00B7, 7, len(khoi), 8 + 2 + 12 + 4)
        mn_tiff += struct.pack(e_mn + "I", 0)
        mn_tiff += khoi
        mn = b"Nikon\x00\x02\x11\x00\x00" + bytes(mn_tiff)
        dau = bytearray(b"II" + struct.pack("<HI", 42, 8))
        ifd = struct.pack("<H", 1) + struct.pack("<HHII", 0x927C, 7, len(mn), 8 + 2 + 12 + 4)
        ifd += struct.pack("<I", 0)
        return bytes(dau + ifd + mn)

    for e_mn in (">", "<"):
        tags = {}
        at._parse_ifd(nef_gia(b"0301", e_mn), 8, "<", set(), [], tags)
        pt, vg = tags.get("af_point"), tags.get("af_vung")
        if not pt or abs(pt[0] - 3273 / 6048) > 1e-9 or abs(pt[1] - 2588 / 4024) > 1e-9:
            loi.append(f"Nikon 0301 ({e_mn}): diem AF sai {pt}")
        if not vg or abs(vg[0] - 769 / 6048) > 1e-9 or abs(vg[1] - 887 / 4024) > 1e-9:
            loi.append(f"Nikon 0301 ({e_mn}): vung AF sai {vg}")
    tags = {}
    at._parse_ifd(nef_gia(b"0400"), 8, "<", set(), [], tags)
    if "af_point" in tags or tags.get("af_nikon_ban") != "0400":
        loi.append(f"Nikon ban 0400 CHUA doi chieu duoc thi KHONG duoc doc: {tags}")

    for m in loi:
        print("  [!]", m)
    print("TAT CA DAT" if not loi else f"{len(loi)} LOI")
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
