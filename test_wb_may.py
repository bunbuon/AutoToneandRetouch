#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nhớ độ lệch WB As Shot THEO MÁY qua các buổi (wb_may.py + autotone.lech_asshot — 15/10).

  1. chưa có dữ liệu -> y như cũ (bảng wb_asshot_lech_mired, máy lạ = 0)
  2. uoc_asshot: học trong buổi (≥ 3 cặp), bỏ cặp lệch > 60 mired, ASSHOT_BUOI có n / IQR
  3. trộn buổi + đã học (trọng số đã học tối đa 30 cặp), kẹp ±30 mired
  4. ghi_buoi: chỉ khi ổn định (n ≥ 3, IQR ≤ 12), phân tích lại = ghi đè, giữ 20 buổi
  5. bang_cfg: trung vị có trọng số, TRỪ buổi đang mở (không đếm hai lần)
  6. máy không có K trong MakerNote (Canon) -> không cặp, không ghi
  7. wb_may_adobe (ảnh preset có WB) dùng số đã học

    python3 test_wb_may.py
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ["AUTOTONE_DATA"] = tempfile.mkdtemp(prefix="wb_may_")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import autotone as at  # noqa: E402
import wb_may  # noqa: E402

LOI = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


CFG = dict(at.DEFAULTS)


def cap(model, k_may, lech, ten="A"):
    """Ảnh đang As Shot có As Shot thật trong catalog lệch `lech` mired so với K máy."""
    k_adobe = 1e6 / (1e6 / k_may + lech)
    return {"path": f"G:/B/{ten}.ARW", "model": model, "wb_may_K": k_may,
            "crs": {"WhiteBalance": "As Shot", "Temperature": f"{k_adobe:.0f}", "Tint": "5"}}


print("1. chưa có dữ liệu")
at.ASSHOT_BUOI.clear()
ktra("A7 V theo bảng 9.5", abs(at.lech_asshot("ILCE-7M5", CFG) - 9.5) < 1e-9)
ktra("máy lạ = 0", at.lech_asshot("ILCE-9M3", CFG) == 0.0)
ktra("bang_cfg rỗng khi chưa có file", wb_may.bang_cfg() == {})

print("2. uoc_asshot")
items = [cap("ILCE-9M3", 5000 + 100 * i, 6.0 + 0.5 * (i % 3), f"S{i}") for i in range(6)]
items.append(cap("ILCE-9M3", 5600, 150.0, "LECH"))             # As Shot bị sửa tay — bỏ
items += [cap("ILCE-7C", 5200, 3.0, "T1"), cap("ILCE-7C", 5300, 3.0, "T2")]   # < 3 cặp
at.uoc_asshot(items, CFG)
b = at.ASSHOT_BUOI.get("ILCE-9M3")
ktra("≥ 3 cặp -> ASSHOT_BUOI có lệch / n / IQR, bỏ cặp lệch 150 mired",
     b is not None and b["n"] == 6 and 6.0 <= b["lech"] <= 7.0 and b["iqr"] < 2, str(b))
ktra("< 3 cặp -> không học máy đó", "ILCE-7C" not in at.ASSHOT_BUOI)
ktra("lech_asshot dùng số trong buổi", abs(at.lech_asshot("ILCE-9M3", CFG) - b["lech"]) < 1e-9)

print("3. trộn + kẹp")
hoc = dict(CFG, wb_asshot_da_hoc={"ILCE-9M3": {"lech": 12.0, "n": 200}})
x = at.lech_asshot("ILCE-9M3", hoc)
ktra("trộn: trọng số đã học tối đa 30 cặp", abs(x - (6 * b["lech"] + 30 * 12.0) / 36) < 1e-6, f"{x:.3f}")
ktra("chỉ có số đã học (buổi không có cặp)", abs(at.lech_asshot("ILCE-9M3", hoc, buoi={}) - 12.0) < 1e-9)
ktra("kẹp ±30 mired", at.lech_asshot("ILCE-9M3", dict(CFG, wb_asshot_da_hoc={"ILCE-9M3": {"lech": 80.0, "n": 9}}),
                                     buoi={}) == 30.0)
ktra("đã học thắng bảng cũ (A7 V)", abs(at.lech_asshot("ILCE-7M5", dict(
    CFG, wb_asshot_da_hoc={"ILCE-7M5": {"lech": 14.0, "n": 40}}), buoi={}) - 14.0) < 1e-9)

print("4. ghi_buoi")
n = wb_may.ghi_buoi("G:/Buoi1", {"ILCE-9M3": {"lech": 6.5, "n": 6, "iqr": 1.0},
                                 "NIKON Z 6_2": {"lech": 3.0, "n": 8, "iqr": 25.0},     # không ổn định
                                 "ILCE-7C": {"lech": 2.0, "n": 2, "iqr": 0.0}})          # quá ít
d = wb_may.doc()["may"]
ktra("chỉ máy ổn định được ghi", n == 1 and list(d) == ["ILCE-9M3"], str(list(d)))
wb_may.ghi_buoi("G:/Buoi1", {"ILCE-9M3": {"lech": 7.5, "n": 7, "iqr": 1.0}})
d = wb_may.doc()["may"]["ILCE-9M3"]
ktra("phân tích lại cùng buổi = ghi đè (một dòng)", len(d) == 1 and d[0]["lech"] == 7.5 and d[0]["n"] == 7)
for i in range(25):
    wb_may.ghi_buoi(f"G:/B{i:02d}", {"ILCE-9M3": {"lech": 10.0, "n": 3, "iqr": 0.0}})
ktra("giữ 20 buổi gần nhất", len(wb_may.doc()["may"]["ILCE-9M3"]) == 20)

print("5. bang_cfg")
import json  # noqa: E402
import duong_dan as dd  # noqa: E402
dd.du_lieu(wb_may.TEN_TEP).write_text(json.dumps({"may": {"ILCE-9M3": [
    {"buoi": wb_may.khoa_buoi("G:/X"), "lech": 4.0, "n": 3},
    {"buoi": wb_may.khoa_buoi("G:/Y"), "lech": 9.0, "n": 20},
    {"buoi": wb_may.khoa_buoi("G:/Z"), "lech": 30.0, "n": 3}]}}), encoding="utf-8")
bc = wb_may.bang_cfg()
ktra("trung vị có trọng số theo số cặp", bc["ILCE-9M3"]["lech"] == 9.0 and bc["ILCE-9M3"]["n"] == 26, str(bc))
bc = wb_may.bang_cfg(tru_buoi="G:/Y")
ktra("trừ buổi đang mở (không đếm hai lần)", bc["ILCE-9M3"]["n"] == 6 and bc["ILCE-9M3"]["buoi"] == 2, str(bc))
dd.du_lieu(wb_may.TEN_TEP).write_text("{hỏng", encoding="utf-8")
ktra("file hỏng -> rỗng, không lỗi", wb_may.bang_cfg() == {})

print("6. Canon / máy không có K")
canon = [{"path": f"G:/C/{i}.CR3", "model": "Canon EOS R6", "wb_may_K": None,
          "crs": {"WhiteBalance": "As Shot", "Temperature": "5200"}} for i in range(5)]
at.uoc_asshot(canon, CFG)
ktra("không cặp nào -> ASSHOT_BUOI rỗng, ghi_buoi 0", not at.ASSHOT_BUOI and wb_may.ghi_buoi("G:/C", at.ASSHOT_BUOI) == 0)

print("7. wb_may_adobe")
r = {"model": "ILCE-9M3", "wb_may_K": 5000.0, "crs": {"WhiteBalance": "Custom", "Temperature": "5600"}}
at.ASSHOT_BUOI.clear()
t0 = at.wb_may_adobe(r, CFG)[0]
t1 = at.wb_may_adobe(r, dict(CFG, wb_asshot_da_hoc={"ILCE-9M3": {"lech": 10.0, "n": 30}}))[0]
ktra("chưa học: K máy giữ nguyên (máy lạ, lệch 0)", abs(t0 - 5000.0) < 0.5, f"{t0:.0f}")
ktra("đã học +10 mired -> K Adobe thấp hơn", abs(t1 - 1e6 / (200.0 + 10.0)) < 0.5, f"{t1:.0f}")

print()
print("TẤT CẢ ĐẠT" if not LOI else f"{len(LOI)} LỖI: " + "; ".join(LOI))
sys.exit(1 if LOI else 0)
