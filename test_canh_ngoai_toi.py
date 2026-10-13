#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nhận cảnh trong / ngoài (Places365) + "ngoài trời buổi tối" không hạ K (12/10).

CHUYỆN ĐANG SỬA
    User 12/10: "sự kiện ngoài trời lúc chiều tối, máy nâng ISO cao, không flash — nhận
    là ảnh sự kiện thì WB đang dìm K xuống, thực tế cần tăng K lên". PUBGM 18-19h: đèn
    LED cam + flash gel, da đo ra cam -> cân theo da kéo 5250 -> 4250-4700 K.

Mục kiểm
    1. DEFAULTS bật; canh_p365 đúng vị trí trong measure() và cau_hinh_do() (thẳng hàng).
    2. read_raw đọc EXIF Flash (0x9209) trong Exif IFD.
    3. do_canh: mô hình + 365 nhãn (161 trong); thiếu mô hình -> (None, "") không vỡ.
    4. gan_canh: ngoài trời tối (gộp cửa sổ) -> cờ; trong nhà tối / ban ngày / sáng /
       "Cả buổi ánh đèn" / tắt khoá / không có p_trong -> không cờ; vài ảnh lẻ "ngoài"
       giữa buổi trong nhà không lật cả cửa sổ.
    5. _wb_ngoai_toi: temp_adj âm -> 0 (+ghi chú), dương giữ, ảnh không cờ giữ.
    6. _nhan_da_ngoai: ảnh ngoai_toi luôn dùng đích da ngoài trời.
    7. Đường thật gan_canh -> nhãn -> group_scenes -> decide (WB da): da cam ngoài trời
       tối — tắt khoá ra 4250 K, bật ra >= preset.

Chạy:  python test_canh_ngoai_toi.py
"""
from __future__ import annotations

import contextlib
import inspect
import io
import struct
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at          # noqa: E402
import test_san_phang as ts    # noqa: E402

LOI: list = []


def ktra(ten, dk, chi_tiet=""):
    print(f"  [{'DAT' if dk else 'LOI'}] {ten}  {chi_tiet}")
    if not dk:
        LOI.append(ten)


def anh(ten, khi, p_trong, iso=800, t=1 / 125, khau=2.8, da=(0.45, 0.17, 0.06)):
    r = ts._anh(ten, -1.6, khi)
    r.update(iso=iso, exposure_time=t, fnumber=khau, p_trong=p_trong,
             face_rgb=list(da))
    r["crs"] = {"Temperature": "5250", "Tint": "10", "WhiteBalance": "Custom",
                "Exposure2012": "0"}
    return r


def chuoi(t0, n, p, buoc_s=60, **kw):
    ds = []
    for i in range(n):
        pi = p[i % len(p)] if isinstance(p, (list, tuple)) else p
        ds.append(anh(f"{t0:%H%M}_{i}", t0 + timedelta(seconds=buoc_s * i), pi, **kw))
    return ds


def co(ds):
    return sum(1 for r in ds if r.get("ngoai_toi"))


def tiff_flash(v):
    """TIFF tối thiểu: IFD0 trỏ Exif IFD, Exif IFD có Flash = v."""
    b = bytearray(b"II*\x00" + struct.pack("<I", 8))
    b += struct.pack("<H", 1) + struct.pack("<HHII", 0x8769, 4, 1, 26) + struct.pack("<I", 0)
    b += struct.pack("<H", 1) + struct.pack("<HHI", 0x9209, 3, 1) + struct.pack("<HH", v, 0)
    b += struct.pack("<I", 0)
    return bytes(b)


def main() -> int:
    # 1
    d = at.DEFAULTS
    ktra("DEFAULTS bật nhận cảnh + ngoài trời buổi tối",
         d.get("canh_p365") and d.get("wb_ngoai_toi") and d.get("canh_cua_so_phut") == 30.0)
    ts_ = list(inspect.signature(at.measure).parameters)
    #  14/10: hl_da_tron (theo máy) thêm SAU canh_p365 — điều canh vẫn là cau_hinh_do()
    #  THẲNG HÀNG với measure() (đo truyền theo vị trí): canh_p365 đúng chỗ ở cả hai bên
    ch_ = at.cau_hinh_do(dict(d))
    i_ = ts_.index("canh_p365")
    ktra("canh_p365 đúng vị trí trong measure() và cau_hinh_do() (thẳng hàng, đủ tham số)",
         ch_[i_ - 1] is True and len(ch_) == len(ts_) - 1
         and at.cau_hinh_do(dict(d, canh_p365=False))[i_ - 1] is False, f"{ts_[i_:]}")
    # 2
    for v, no in ((13, True), (16, False), (0, False)):
        tags, jp = {}, []
        data = tiff_flash(v)
        at._parse_ifd(data, 8, "<", set(), jp, tags)
        ktra(f"EXIF Flash {v} đọc ra (đã nổ = {no})", tags.get("flash") == v
             and bool((tags.get("flash") or 0) & 1) == no, str(tags))
    # 3
    nhan = Path(at.CANH_NHAN).read_text(encoding="utf-8").split("\n")
    nhan = [x for x in nhan if x.strip()]
    ktra("365 nhãn Places365, 161 loại trong nhà",
         len(nhan) == 365 and sum(x.split()[1] == "1" for x in nhan) == 161)
    from PIL import Image
    p, ten = at.do_canh(Image.new("RGB", (640, 480), (90, 120, 160)))
    ktra("do_canh chạy ra P(trong) 0-1 + tên cảnh", p is not None and 0 <= p <= 1 and ten.startswith("/"),
         f"{p} {ten}")
    cu = (at._CANH, at.CANH_MODEL)
    at._CANH, at.CANH_MODEL = None, Path("khong_co.onnx")
    p2 = at.do_canh(Image.new("RGB", (64, 64)))
    at._CANH, at.CANH_MODEL = cu
    ktra("thiếu mô hình -> (None, \"\"), không vỡ", p2 == (None, ""), str(p2))
    # 4
    cfg = ts._cfg(source="catalog", wb="skin")
    T18 = datetime(2026, 10, 11, 18, 20)
    ngoai = chuoi(T18, 30, [0.9, 0.3, 0.8, 0.5])           # TB 0.625: PUBGM tối
    at.gan_canh(ngoai, cfg)
    ktra("ngoài trời tối (P lẻ 0.3-0.9, TB < 0.8) -> cả chuỗi mang cờ", co(ngoai) == 30,
         f"{co(ngoai)}/30 cs {ngoai[0].get('p_trong_cs')}")
    trong = chuoi(T18, 40, 0.96)
    for i in (5, 17, 29):
        trong[i]["p_trong"] = 0.1                           # vài ảnh lẻ bị gọi "ngoài"
    at.gan_canh(trong, cfg)
    ktra("trong nhà tối có vài ảnh lẻ 'ngoài' -> không cờ ảnh nào", co(trong) == 0,
         f"cs {trong[5].get('p_trong_cs')}")
    kinh = chuoi(datetime(2026, 10, 11, 18, 46), 12, [0.74, 0.78])
    at.gan_canh(kinh, cfg)
    ktra("nhà hàng vách kính buổi tối (KN2009 18:46, TB 0.76) -> không cờ", co(kinh) == 0,
         f"cs {kinh[0].get('p_trong_cs')}")
    ngay = chuoi(datetime(2026, 10, 11, 14, 0), 20, 0.3)
    at.gan_canh(ngay, cfg)
    ktra("ngoài trời BAN NGÀY (14h) -> không cờ", co(ngay) == 0 and ngay[0]["canh_ngoai"])
    sang = chuoi(T18, 10, 0.3, iso=100, t=1 / 250, khau=8.0)   # EV100 14
    at.gan_canh(sang, cfg)
    ktra("sau 17h nhưng còn nắng (EV100 >= 11) -> không cờ", co(sang) == 0,
         f"EV100 {at.ev100(sang[0]):.1f}")
    for k, v in (("che_do_sang", "den"), ("wb_ngoai_toi", False)):
        x = chuoi(T18, 10, 0.3)
        at.gan_canh(x, dict(cfg, **{k: v}))
        ktra(f"{k}={v!r} -> không cờ", co(x) == 0)
    x = chuoi(T18, 10, None)
    at.gan_canh(x, cfg)
    ktra("không có p_trong (kết quả đo cũ / thiếu mô hình) -> không cờ, không vỡ", co(x) == 0)
    dem = chuoi(datetime(2026, 10, 11, 0, 30), 5, 0.2)
    at.gan_canh(dem, cfg)
    ktra("ngoài trời sau nửa đêm -> có cờ", co(dem) == 5)
    # 5
    a = [{"ngoai_toi": True, "temp_adj": -600.0, "notes": ""},
         {"ngoai_toi": True, "temp_adj": 200.0, "notes": ""},
         {"temp_adj": -600.0, "notes": ""}]
    n = at._wb_ngoai_toi(a, cfg)
    ktra("_wb_ngoai_toi: âm -> 0 + ghi chú, dương giữ, ảnh không cờ giữ",
         n == 1 and a[0]["temp_adj"] == 0 and "ngoai-toi-giu-am+600" in a[0]["notes"]
         and a[1]["temp_adj"] == 200 and a[2]["temp_adj"] == -600, str([r["temp_adj"] for r in a]))
    ktra("_wb_ngoai_toi tắt khoá -> không đổi",
         at._wb_ngoai_toi([{"ngoai_toi": True, "temp_adj": -5.0}], dict(cfg, wb_ngoai_toi=False)) == 0)
    # 6
    r = anh("x", T18, 0.3, da=(0.6, 0.2, 0.05))
    r.update(ngoai_toi=True, ngoai_troi=False)
    ktra("_nhan_da_ngoai: ảnh ngoai_toi -> đích da ngoài trời (kể cả bật da_vang_lech_ngoai)",
         at._nhan_da_ngoai(r, dict(cfg, da_vang_lech_ngoai=0.3)) is True)
    # 7
    ra = {}
    for bat in (False, True):
        ds = chuoi(datetime(2026, 10, 11, 18, 30), 8, [0.5, 0.75], buoc_s=40)
        c = ts._cfg(source="catalog", wb="skin", wb_ngoai_toi=bat)
        with contextlib.redirect_stderr(io.StringIO()):
            at.gan_canh(ds, c)
            for r in ds:
                r["ngoai_troi"] = at.ngoai_troi(r, c) or bool(r.get("ngoai_toi"))
            at.group_scenes(ds, 5.0)
            at.decide(ds, c)
            for r in ds:
                at.compute_values(r, c, r["crs"], {})
        ra[bat] = ds
    k0 = [r["new_temp"] for r in ra[False]]
    k1 = [r["new_temp"] for r in ra[True]]
    ktra("đường thật: da cam ngoài trời tối — tắt khoá hạ K, bật giữ >= preset 5250",
         max(k0) < 5000 and min(k1) >= 5250 and all("ngoai-toi" in r["notes"] for r in ra[True]),
         f"tắt {k0[0]} · bật {k1[0]}")
    print("TAT CA DAT" if not LOI else f"{len(LOI)} LOI: {LOI}")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
