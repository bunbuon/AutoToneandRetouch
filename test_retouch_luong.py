#!/usr/bin/env python3
"""Kiểm dòng lệnh retouch — nhất là --luong.

VÌ SAO ĐÁNG MỘT FILE TEST RIÊNG
    Bỏ sót --luong không báo lỗi gì cả: dòng lệnh vẫn hợp lệ, tool vẫn chạy,
    chỉ có điều nó tự lấy min(12, ncpu-2) rồi sập ở ảnh đầu vì hết VRAM. Một
    lỗi im lặng thì chỉ có test mới giữ được.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import retouch as rt   # noqa: E402


def dung(cmd, co):
    """Giá trị đi liền sau một cờ trong dòng lệnh, None nếu không có cờ đó."""
    if co not in cmd:
        return None
    i = cmd.index(co)
    return cmd[i + 1] if i + 1 < len(cmd) else ""


def main() -> int:
    loi = []
    vao, ra = Path("C:/vao"), Path("C:/ra")
    muc = {"vet": 100.0, "nong_cam": 80.0, "chan": 0.0}

    # --- mac dinh PHAI co --luong, va phai la 1
    cmd = rt.lenh(Path("C:/tool"), vao, ra, muc)
    if "--luong" not in cmd:
        loi.append("Mac dinh khong truyen --luong -> saytool tu lay 12 -> OOM")
    elif dung(cmd, "--luong") != "1":
        loi.append(f"Mac dinh --luong = {dung(cmd, '--luong')}, dang le 1")
    if rt.LUONG_MAC_DINH != 1:
        loi.append(f"LUONG_MAC_DINH = {rt.LUONG_MAC_DINH}, dang le 1")

    # --- nguoi dung tang len thi phai di qua nguyen ven
    if dung(rt.lenh(Path("C:/tool"), vao, ra, muc, luong=4), "--luong") != "4":
        loi.append("Chon 4 luong ma dong lenh khong mang so 4")

    # --- 0 = de saytool tu quyet (co duong thoat, nhung khong phai mac dinh)
    if "--luong" in rt.lenh(Path("C:/tool"), vao, ra, muc, luong=0):
        loi.append("luong=0 dang le KHONG truyen co, de saytool tu quyet")

    # --- ba thanh keo van con nguyen sau khi them co moi
    for ten, gt in (("--vet", "100"), ("--nong-cam", "80"), ("--chan", "0")):
        if dung(cmd, ten) != gt:
            loi.append(f"{ten} = {dung(cmd, ten)}, dang le {gt}")

    # --- giai_thich_ma: ma tran + log OOM -> phai chi ra dung viec can lam
    v = rt.giai_thich_ma(3221225477, "  memory allocation failed with OOM on "
                                     "device 0 while trying to allocate ...", 12)
    if "VRAM" not in v or "Số luồng" not in v:
        loi.append(f"Log co OOM ma khong bao ha so luong:\n{v}")
    # da o 1 luong thi bao ha nua la vo nghia
    v1 = rt.giai_thich_ma(3221225477, "OOM on device 0", 1)
    if "Số luồng" in v1:
        loi.append(f"Dang chay 1 luong ma van bao ha luong:\n{v1}")
    if rt.giai_thich_ma(0, "", 1):
        loi.append("Ma 0 (thanh cong) ma van giai thich gi do")
    if "0xC0000005" not in rt.giai_thich_ma(3221225477, "", 1):
        loi.append("Ma 3221225477 khong duoc dich ra ten loi")

    # --- 12/10: bo anh khong co nguoi (retouch.json "bo_khong_nguoi", mac dinh BAT)
    if "--ca-anh-khong-nguoi" in rt.lenh(Path("C:/tool"), vao, ra, muc):
        loi.append("Mac dinh (bo anh khong nguoi) ma dong lenh lai gui --ca-anh-khong-nguoi")
    if "--ca-anh-khong-nguoi" not in rt.lenh(Path("C:/tool"), vao, ra, muc, bo_khong_nguoi=False):
        loi.append("Tat 'Bo qua anh khong co nguoi' ma dong lenh thieu --ca-anh-khong-nguoi")

    class EngineGia:
        def __init__(self):
            self.tham = None

        def chay_duoc(self):
            return True

        def chay_me(self, tham):
            self.tham = tham
            yield ("ma", 0)

    cu_doc = rt.doc_cau_hinh
    try:
        for cf, mong in (({}, True), ({"bo_khong_nguoi": False}, False), ({"bo_khong_nguoi": True}, True)):
            rt.doc_cau_hinh = lambda cf=cf: dict(cf)
            e = EngineGia()
            list(rt.chay(Path("C:/tool"), vao, ra, muc, engine=e))
            if not e.tham or e.tham.get("bo_khong_nguoi") is not mong:
                loi.append(f"retouch.json {cf} -> engine phai nhan bo_khong_nguoi={mong}, "
                           f"dang {None if not e.tham else e.tham.get('bo_khong_nguoi')}")
        rt.doc_cau_hinh = lambda: {"bo_khong_nguoi": False}
        e = EngineGia()
        list(rt.chay(Path("C:/tool"), vao, ra, muc, engine=e, bo_khong_nguoi=True))
        if e.tham.get("bo_khong_nguoi") is not True:
            loi.append("Ben goi truyen bo_khong_nguoi=True thi phai thang retouch.json")
    finally:
        rt.doc_cau_hinh = cu_doc

    for m in loi:
        print("  [!]", m)
    print("TAT CA DAT" if not loi else f"{len(loi)} LOI")
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
