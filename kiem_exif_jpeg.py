#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kiem_exif_jpeg.py — Đọc được ISO từ ảnh ĐÃ XUẤT (JPEG) không.

    python kiem_exif_jpeg.py

VÌ SAO CẦN BÀI KIỂM NÀY
    read_raw() chỉ đọc EXIF khi file mở đầu bằng II/MM — tức định dạng TIFF, mà
    RAW nào cũng vậy. File JPEG mở đầu bằng FFD8, nên cả nhánh đọc EXIF bị bỏ
    qua. Ảnh vẫn đọc được (có đoạn lùi ở cuối read_raw), chỉ là tags rỗng.

    Hậu quả KHÔNG BÁO LỖI MỘT CHỮ NÀO: measure() trả iso=None cho mọi ảnh JPEG.
    Mà ngoai_troi() coi "không đọc được ISO" là trong nhà. Nên hoc_mau_da.py
    chạy trên ảnh đã xuất sẽ thấy 0 ảnh ngoài trời dù thư mục toàn ảnh ngoài
    trời, rồi báo "chưa đủ 10 ảnh để rút màu đích riêng" — một câu khiến người
    dùng đi tìm thêm ảnh, trong khi ảnh không hề thiếu.

    Đây đúng là kiểu lỗi mà bài kiểm phải bắt: mọi thứ vẫn chạy, chỉ là một con
    số lặng lẽ biến mất.
"""
from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at   # noqa: E402


def anh_co_iso(p: Path, iso: int) -> None:
    """Ghi một ảnh JPEG mang đúng ISO cho trước trong EXIF."""
    im = Image.new("RGB", (640, 480), (150, 120, 110))
    ex = Image.Exif()
    ex[0x8769] = {0x8827: iso, 0x829A: (1, 200), 0x829D: (28, 10)}
    im.save(p, "JPEG", quality=90, exif=ex)


def main() -> int:
    loi = []
    cfg = dict(at.DEFAULTS)

    with tempfile.TemporaryDirectory() as t:
        d = Path(t)

        #[[ 1 — DOC DUOC ISO TU JPEG. Day la phep kiem chinh.
        #]]
        for iso, mong_doi_ngoai in ((200, True), (1000, False)):
            p = d / f"iso{iso}.jpg"
            anh_co_iso(p, iso)
            _blob, tags = at.read_raw(p)
            doc = tags.get("iso")
            if doc != iso:
                loi.append(f"JPEG ISO {iso}: read_raw doc ra {doc!r}, "
                           f"dang le {iso}")
                continue
            r = {"iso": doc}
            if at.ngoai_troi(r, cfg) is not mong_doi_ngoai:
                loi.append(f"ISO {iso}: ngoai_troi() tra "
                           f"{at.ngoai_troi(r, cfg)}, dang le {mong_doi_ngoai}")
            else:
                print(f"  ISO {iso:4d} -> doc dung, "
                      f"{'ngoai troi' if mong_doi_ngoai else 'trong nha'}")

        #[[ 2 — ANH KHONG CO EXIF THI KHONG DUOC SAP.
        #
        #   Anh xuat voi tuy chon "khong kem metadata" thi khong co doan APP1 nao.
        #   Luc do phai tra ve None mot cach yen lang, chu khong duoc nem ngoai le
        #   — mot anh thieu ISO khong phai la mot anh hong.
        #]]
        p = d / "khong_exif.jpg"
        Image.new("RGB", (320, 240), (200, 180, 170)).save(p, "JPEG")
        try:
            blob, tags = at.read_raw(p)
        except Exception as ex:                              # noqa: BLE001
            loi.append(f"anh khong co EXIF lam read_raw nem loi: "
                       f"{type(ex).__name__}: {ex}")
        else:
            if tags.get("iso") is not None:
                loi.append("anh khong co EXIF ma van bao co ISO")
            elif blob is None:
                loi.append("anh khong co EXIF thi doc luon ca anh cung hong")
            else:
                print("  khong co EXIF -> iso=None, anh van doc duoc (dung)")

        #[[ 3 — FILE RAC KHONG DUOC LAM DUNG CHUONG TRINH.
        #]]
        p = d / "rac.jpg"
        p.write_bytes(b"\xff\xd8" + b"\xff\xe1\x00\x08Exif\x00\x00" + b"\x00" * 40)
        try:
            at.read_raw(p)
            print("  file JPEG hong -> khong nem loi (dung)")
        except Exception as ex:                              # noqa: BLE001
            loi.append(f"file JPEG hong lam read_raw nem loi: "
                       f"{type(ex).__name__}: {ex}")

    for m in loi:
        print("  [!]", m)
    print("TAT CA DAT" if not loi else f"{len(loi)} LOI")
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
