#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chất lượng ảnh ra của Retouch (15/10 — user: "ảnh chạy qua retouch dung lượng lại đang tăng.
Cần cơ chế để có thể chọn Quality ảnh xuất ra").

  1. chuan_chat_luong / chat_luong_ra: "auto" mặc định, số kẹp 1–100, giá trị lạ -> "auto";
  2. dòng lệnh saytool: "auto" -> --chat-luong auto, KHÔNG --nen-lai-het (ghép DCT giữ dung lượng);
     một số -> --chat-luong N + --nen-lai-het (ghép DCT bỏ qua chất lượng — phải nén lại cả ảnh);
  3. chay() qua engine thường trú: chất lượng + nguyen_ven lấy từ retouch.json khi không truyền;
     truyền tay (trạm Retouch khi xuất) thì theo số truyền.

    python3 test_chat_luong_ra.py
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ["AUTOTONE_DATA"] = tempfile.mkdtemp(prefix="chat_luong_ra_")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import retouch as rt  # noqa: E402

LOI = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


print("1. chuẩn hoá")
ktra("mặc định (chưa đặt) = auto", rt.chat_luong_ra({}) == "auto")
ktra("số kẹp 1–100, chuỗi số đọc được, lạ -> auto",
     [rt.chuan_chat_luong(v) for v in (90, "85", 150, 0, "abc", None, "AUTO")] == [90, 85, 100, 1, "auto", "auto", "auto"])
ktra("nhãn: auto nói giữ dung lượng; 100 cảnh báo file to",
     "giữ dung lượng" in rt.ten_chat_luong("auto") and "file rất to" in rt.ten_chat_luong(100)
     and rt.ten_chat_luong(90) == "JPEG 90")

print("2. dòng lệnh saytool")
G = Path(tempfile.mkdtemp())
c_auto = rt.lenh(G, G / "vao", G / "ra", {"vet": 50})
c_90 = rt.lenh(G, G / "vao", G / "ra", {"vet": 50}, chat_luong=90)
c_de = rt.lenh(G, G / "vao", G / "ra", {"vet": 50}, chat_luong=85, ghi_de=True)
ktra("mặc định: --chat-luong auto, không --nen-lai-het",
     c_auto[c_auto.index("--chat-luong") + 1] == "auto" and "--nen-lai-het" not in c_auto, str(c_auto[-8:]))
ktra("chọn 90: --chat-luong 90 + --nen-lai-het",
     c_90[c_90.index("--chat-luong") + 1] == "90" and "--nen-lai-het" in c_90)
ktra("ghi đè + 85: vẫn có --chat-luong 85 + --nen-lai-het",
     c_de[c_de.index("--chat-luong") + 1] == "85" and "--nen-lai-het" in c_de and "--ghi-de" in c_de)

print("3. chay() qua engine thường trú")


class GiaEngine:
    def __init__(self):
        self.tham = None

    def chay_duoc(self):
        return True

    def chay_me(self, tham):
        self.tham = tham
        yield ("ma", 0)


def chay(**kw):
    e = GiaEngine()
    for _ in rt.chay(G, G / "vao", G / "ra", {"vet": 50}, engine=e, **kw):
        pass
    return e.tham


t = chay()
ktra("chưa đặt gì: engine nhận chat_luong auto + nguyen_ven True (ghép DCT)",
     t["chat_luong"] == "auto" and t["nguyen_ven"] is True, str({k: t[k] for k in ("chat_luong", "nguyen_ven")}))
rt.ghi_cau_hinh({"chat_luong_ra": 90})
t = chay()
ktra("retouch.json chat_luong_ra 90: engine nhận 90 + nguyen_ven False (nén lại cả ảnh)",
     t["chat_luong"] == 90 and t["nguyen_ven"] is False, str({k: t[k] for k in ("chat_luong", "nguyen_ven")}))
t = chay(chat_luong="auto")
ktra("truyền tay 'auto' thắng cài đặt", t["chat_luong"] == "auto" and t["nguyen_ven"] is True)
ktra("trạm Retouch khi xuất đọc cùng cài đặt (rt.chat_luong_ra)", rt.chat_luong_ra() == 90)
rt.ghi_cau_hinh({"chat_luong_ra": "auto"})

print()
print("TẤT CẢ ĐẠT" if not LOI else f"{len(LOI)} LỖI: " + "; ".join(LOI))
sys.exit(1 if LOI else 0)
