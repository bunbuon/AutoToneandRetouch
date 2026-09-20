#!/usr/bin/env python3
"""Kiểm bảng trạng thái buổi chụp — dựng thư mục giả, gọi hàm thật.

Điều quan trọng nhất được kiểm ở đây: trạng thái phải suy ra từ FILE, không
phải từ những gì file trạng thái tự khai. Nên mỗi bài đều dựng file thật rồi
xem tinh() có nhìn thấy không, và bài cuối xoá file trạng thái đi để chắc rằng
mất nó thì chỉ mất số đo thời gian, không mất trạng thái.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trang_thai as ts   # noqa: E402


def dung_moi_truong():
    d = Path(tempfile.mkdtemp())
    (d / "buoi").mkdir()
    (d / "jobs").mkdir()
    (d / "export").mkdir()
    (d / "retouch").mkdir()
    ts.THU_MUC = d / "trang_thai"
    return d


def lay(ks, ten):
    return next(k for k in ks if k["ten"] == ten)


def main() -> int:
    loi = []
    d = dung_moi_truong()
    buoi, jobs = d / "buoi", d / "jobs"

    # --- thu muc rong
    ks = ts.tinh(buoi, jobs)
    if lay(ks, "nap")["xong"] or lay(ks, "day")["xong"]:
        loi.append("Thu muc rong ma bao da xong khau nao do")
    if lay(ks, "nap")["viec"] != "Chọn đúng thư mục buổi chụp":
        loi.append("Thu muc rong ma khong chi duoc viec tiep theo")

    # --- co anh RAW
    for i in range(7):
        (buoi / f"DSC0{i:03d}.ARW").write_bytes(b"x")
    ks = ts.tinh(buoi, jobs)
    if not lay(ks, "nap")["xong"] or "7" not in lay(ks, "nap")["mo_ta"]:
        loi.append(f"Dem sai so anh RAW: {lay(ks, 'nap')['mo_ta']}")

    # --- da day vao catalog, 2 anh gan 1 sao
    (jobs / "apply_20260903_101500_buoi.done").write_text(
        "path\tExposure2012\tRating\n"
        "G:\\buoi\\a.ARW\t-0.50\t\n"
        "G:\\buoi\\b.ARW\t-0.40\t1\n"
        "G:\\buoi\\c.ARW\t-0.30\t1\n", encoding="utf-8")
    ks = ts.tinh(buoi, jobs)
    k = lay(ks, "day")
    if not k["xong"] or "3 ảnh" not in k["mo_ta"] or "2 ảnh gắn 1 sao" not in k["mo_ta"]:
        loi.append(f"Doc sai file job: {k['mo_ta']}")

    # --- job KHOI PHUC khong duoc tinh la lan tool day
    #[[ Cung ly le nhu trong last_applied(): job khoi phuc mang tien to apply_
    #   nhung no la de tra lai gia tri NGUOI DUNG chon, khong phai tool ghi.
    #]]
    d2 = dung_moi_truong()
    for i in range(3):
        (d2 / "buoi" / f"X{i}.ARW").write_bytes(b"x")
    (d2 / "jobs" / "apply_20260903_1_buoi-khoiphuc.done").write_text(
        "path\tExposure2012\nG:\\buoi\\a.ARW\t-0.5\n", encoding="utf-8")
    if lay(ts.tinh(d2 / "buoi", d2 / "jobs"), "day")["xong"]:
        loi.append("Job khoi phuc bi tinh nham la lan tool day thong so")

    # --- Export + retouch dang do
    ts.ghi("buoi", thu_muc_export=str(d / "export"),
           thu_muc_retouch=str(d / "retouch"))
    for i in range(10):
        (d / "export" / f"{i}.jpg").write_bytes(b"x")
    for i in range(4):
        (d / "retouch" / f"{i}.jpg").write_bytes(b"x")
    ks = ts.tinh(buoi, jobs)
    if not lay(ks, "export")["xong"]:
        loi.append("Co 10 anh trong thu muc export ma bao chua xong")
    k = lay(ks, "retouch")
    if k["xong"]:
        loi.append("Retouch moi 4/10 ma da bao xong")
    if "4/10" not in k["mo_ta"] or "còn 6" not in k["mo_ta"]:
        loi.append(f"Khong bao dung con bao nhieu anh: {k['mo_ta']}")

    # --- retouch xong
    for i in range(4, 10):
        (d / "retouch" / f"{i}.jpg").write_bytes(b"x")
    if not lay(ts.tinh(buoi, jobs), "retouch")["xong"]:
        loi.append("Retouch du 10/10 ma van bao chua xong")

    # --- XOA file trang thai: trang thai phai con, chi mat thoi gian
    ts.ghi_khau("buoi", "day", 123.0)
    truoc = ts.tinh(buoi, jobs)
    ts.duong_dan("buoi").unlink()
    sau = ts.tinh(buoi, jobs)
    if not lay(sau, "day")["xong"]:
        loi.append("Xoa file trang thai la mat luon trang thai 'da day' — "
                   "dang le phai suy duoc tu file job tren dia")
    if lay(truoc, "day")["giay"] != 123.0 or lay(sau, "day")["giay"] is not None:
        loi.append("Thoi gian tung khau khong nam dung cho (phai o file trang thai)")
    if lay(sau, "export")["xong"]:
        loi.append("Mat file trang thai ma van biet thu muc Export — khong the")

    print(ts.tom_tat(buoi, jobs))
    print()
    for m in loi:
        print("  [!]", m)
    print("TAT CA DAT" if not loi else f"{len(loi)} LOI")
    shutil.rmtree(d, ignore_errors=True)
    shutil.rmtree(d2, ignore_errors=True)
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
