#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lọc máy / ống kính trước Phân tích · màu da đích từ ảnh đã sửa · bù K / Tint cả buổi (12/10).

CHUYỆN ĐANG SỬA (user 12/10)
    "Mỗi thiết bị / mỗi người có màu da mong muốn theo gu — cho họ chọn màu da qua ảnh họ đã
    sửa sẵn." · "Thêm option phân loại files theo Model máy, hoặc Lens như filter Metadata của
    Lightroom; bấm Phân tích thì hỏi phân tích loại nào hay hết." · "Thêm option bù / giảm K và
    Tint như bù sáng cả buổi."

Mục kiểm — engine
    1. doc_the đọc Model + LensModel (TIFF tự dựng); ten_lens bỏ "----"; may_lens cả buổi.
    2. Lưu kết quả đo GỘP: đo máy A rồi máy B -> nạp cả buổi đủ A + B. Chỉ có A: nạp thường
       từ chối, nạp mot_phan trả A + số ảnh thiếu.
    3. Bù K / Tint cả buổi: cộng mọi ảnh, bỏ ảnh đen trắng, WB "Tắt" không cộng; chạy SAU
       chặn "ngoài trời tối" (người dùng chọn thì người dùng thắng).
    4. Màu da đích: dich_da / dich_da_cuoi trả đích riêng (thắng cả trắng hồng / kỷ yếu);
       decide thật: đích ấm hơn -> K cao hơn.
    5. mau_da_tu_anh (measure giả): nhóm theo EV100, chuẩn hoá màu, nhóm thiếu lấy nhóm kia,
       bỏ ảnh đen trắng / không mặt; không ảnh nào có da -> ValueError.
Mục kiểm — giao diện thật
    6. Buổi 2 máy: bấm Phân tích hiện hộp chọn; bỏ một máy -> analyze nhận đúng phần chọn;
       lần sau hộp nhớ lựa chọn; đo nốt phần kia -> kết quả gộp, mở lại nạp đủ 6.
    7. Buổi 1 máy 1 ống kính: không hỏi, đo hết.
    8. Ô Bù K / Tint + Màu da đích vào read_cfg; mẫu lưu / nhớ theo buổi / xoá.

Chạy:  python test_loc_may_mau_da.py
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import struct
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
TAM = Path(tempfile.mkdtemp(prefix="loc_may_"))
os.environ["AUTOTONE_DATA"] = str(TAM / "du_lieu")

import numpy as np            # noqa: E402
import autotone as at         # noqa: E402
import test_san_phang as ts   # noqa: E402

LOI: list = []


def ktra(ten, dk, chi_tiet=""):
    print(f"  [{'DAT' if dk else 'LOI'}] {ten}  {chi_tiet}")
    if not dk:
        LOI.append(ten)


def tiff_may(model: str, lens: str, them: bytes = b"") -> bytes:
    """TIFF tối thiểu: IFD0 có Model + con trỏ Exif IFD, Exif IFD có LensModel."""
    mb, lb = model.encode() + b"\0", lens.encode() + b"\0"
    o_m, o_l = 56, 56 + len(mb)
    b = bytearray(b"II*\x00" + struct.pack("<I", 8))
    b += struct.pack("<H", 2) + struct.pack("<HHII", 0x0110, 2, len(mb), o_m)
    b += struct.pack("<HHII", 0x8769, 4, 1, 38) + struct.pack("<I", 0)
    b += struct.pack("<H", 1) + struct.pack("<HHII", 0xA434, 2, len(lb), o_l) + struct.pack("<I", 0)
    return bytes(b + mb + lb + them)


def lam_buoi(ten: str, ds: list) -> Path:
    d = TAM / ten
    d.mkdir(parents=True)
    for i, (m, ln) in enumerate(ds):
        (d / f"{ten}_{i}.ARW").write_bytes(tiff_may(m, ln, bytes([i]) * 32))
    return d


SONY, NIKON = ("ILCE-7M5", "FE 24-70mm F2.8 GM II"), ("NIKON Z 6_2", "NIKKOR Z 24-120mm f/4 S")


def main() -> int:
    # 1
    d1 = lam_buoi("MayLens", [SONY] * 4 + [NIKON] * 2)
    t = at.doc_the(next(d1.glob("*_0.ARW")))
    ktra("doc_the đọc Model + LensModel", t.get("model") == SONY[0] and t.get("lens") == SONY[1], str(t))
    ktra("ten_lens: '----' / rỗng -> ''; gộp khoảng trắng",
         at.ten_lens("----") == "" and at.ten_lens(None) == "" and at.ten_lens(" FE  85mm ") == "FE 85mm")
    pairs, _ = at.collect_pairs(d1, need_sidecar=False)      # nguồn catalog: không cần .xmp
    m = at.may_lens(pairs)
    ktra("may_lens cả buổi: 4 Sony + 2 Nikon", sorted(v[0] for v in m.values()).count(SONY[0]) == 4
         and sorted(v[1] for v in m.values()).count(NIKON[1]) == 2, str(sorted(set(m.values()))))

    # 2
    cfg = dict(at.DEFAULTS)
    pa = [pr for pr in pairs if m[str(pr[0])][0] == SONY[0]]
    pb = [pr for pr in pairs if m[str(pr[0])][0] == NIKON[0]]

    def items(prs):
        return [{"path": str(p), "sidecar": str(sc), "metered_ev": -1.5, "ok": True} for p, sc in prs]

    at.luu_ket_qua_do(d1, cfg, pa, items(pa), [])
    kq, ly = at.nap_ket_qua_do(d1, cfg, pairs)
    ktra("chỉ đo máy A: nạp thường từ chối, nói 2 ảnh mới", kq is None and "2 ảnh mới" in ly, ly)
    kq, ly = at.nap_ket_qua_do(d1, cfg, pairs, mot_phan=True)
    ktra("nạp mot_phan: 4 ảnh máy A + thiếu 2", kq is not None and len(kq["items"]) == 4
         and kq["thieu"] == 2, str(kq and (len(kq["items"]), kq["thieu"])))
    at.luu_ket_qua_do(d1, cfg, pb, items(pb), [])
    kq, ly = at.nap_ket_qua_do(d1, cfg, pairs)
    ktra("đo nốt máy B -> GỘP: nạp thường đủ 6, thiếu 0",
         kq is not None and len(kq["items"]) == 6 and kq["thieu"] == 0, ly)

    # 3
    T18 = datetime(2026, 10, 11, 18, 30)

    def chuoi(n, da=(0.45, 0.17, 0.06), p=0.5):
        out = []
        for i in range(n):
            r = ts._anh(f"x{i}", -1.6, T18 + timedelta(seconds=40 * i))
            r.update(iso=800, exposure_time=1 / 125, fnumber=2.8, p_trong=p, face_rgb=list(da))
            r["crs"] = {"Temperature": "5250", "Tint": "10", "WhiteBalance": "Custom", "Exposure2012": "0"}
            out.append(r)
        return out

    def chay(ds, **kw):
        c = ts._cfg(source="catalog", wb="skin", **kw)
        with contextlib.redirect_stderr(io.StringIO()):
            at.gan_canh(ds, c)
            for r in ds:
                r["ngoai_troi"] = at.ngoai_troi(r, c) or bool(r.get("ngoai_toi"))
            at.group_scenes(ds, 5.0)
            at.decide(ds, c)
            for r in ds:
                at.compute_values(r, c, r["crs"], {})
        return ds

    goc = chay(chuoi(6, p=0.95))
    bu = chay(chuoi(6, p=0.95), bu_k_ca_buoi=200, bu_tint_ca_buoi=-4)
    ktra("bù +200 K / Tint −4: mọi ảnh cộng đúng", all(abs((b["new_temp"] - a["new_temp"]) - 200) <= 1
                                                    and abs((b["new_tint"] - a["new_tint"]) + 4) <= 1
                                                    for a, b in zip(goc, bu)),
         f"{goc[0]['new_temp']} -> {bu[0]['new_temp']}")
    toi = chay(chuoi(6, p=0.5), bu_k_ca_buoi=-300)
    ktra("ngoài trời tối + bù −300 K: người dùng thắng chặn (K = preset − 300)",
         all(abs(r["new_temp"] - 4950) <= 1 for r in toi), str([r["new_temp"] for r in toi][:3]))
    a = [{"temp_adj": 10.0, "tint_adj": 0.0, "notes": ""}, {"temp_adj": 0.0, "tint_adj": 0.0, "bw": True}]
    ktra("ảnh đen trắng không cộng; WB Tắt không cộng",
         at._wb_bu_ca_buoi(a, dict(cfg, bu_k_ca_buoi=100)) == 1 and a[0]["temp_adj"] == 110
         and a[1]["temp_adj"] == 0
         and at._wb_bu_ca_buoi([{"temp_adj": 0.0}], dict(cfg, wb="off", bu_k_ca_buoi=100)) == 0)

    # 4
    md = {"ten": "Gu A", "trong": [240, 170, 140], "ngoai": [235, 165, 130]}
    ktra("dich_da / dich_da_cuoi trả đích riêng (thắng trắng hồng + kỷ yếu)",
         at.dich_da(dict(cfg, mau_da_dich=md, grade=True)) == (md["trong"], md["ngoai"])
         and at.dich_da_cuoi(dict(cfg, mau_da_dich=md, loai_buoi="ky_yeu")) == (md["trong"], md["ngoai"]))
    da_thuong = (0.40, 0.25, 0.20)
    k0 = chay(chuoi(6, da=da_thuong, p=0.95))[0]["new_temp"]
    k1 = chay(chuoi(6, da=da_thuong, p=0.95), mau_da_dich=md)[0]["new_temp"]
    ktra("decide thật: đích ấm hơn -> K cao hơn", k1 > k0 + 50, f"{k0} -> {k1}")

    # 5
    gia = {"a.jpg": dict(ok=True, face_rgb=[0.50, 0.30, 0.25], iso=100, exposure_time=1 / 200, fnumber=8.0),
           "b.jpg": dict(ok=True, face_rgb=[0.52, 0.31, 0.25], iso=100, exposure_time=1 / 200, fnumber=8.0),
           "c.jpg": dict(ok=True, face_rgb=[0.60, 0.35, 0.33], iso=3200, exposure_time=1 / 60, fnumber=2.8),
           "d.jpg": dict(ok=True, face_rgb=None),
           "e.jpg": dict(ok=True, face_rgb=[0.5, 0.5, 0.5], bw=True)}
    cu = at.measure
    at.measure = lambda p, *a_, **k_: dict(gia[Path(p).name])
    try:
        kq = at.mau_da_tu_anh(list(gia), cfg)
        kq2 = at.mau_da_tu_anh(["a.jpg", "b.jpg"], cfg)
        try:
            at.mau_da_tu_anh(["d.jpg", "e.jpg"], cfg)
            loi_rong = False
        except ValueError:
            loi_rong = True
    finally:
        at.measure = cu
    ktra("mau_da_tu_anh: 2 ảnh ngày + 1 ảnh đèn, bỏ ảnh không mặt + đen trắng",
         kq["n_ngoai"] == 2 and kq["n_trong"] == 1 and kq["n_anh"] == 3 and sorted(kq["bo"]) == ["d.jpg", "e.jpg"], str(kq))
    ktra("màu chuẩn hoá: kênh lớn nhất ~ 0.85 tuyến tính (237/255), chỉ giữ màu",
         max(kq["ngoai"]) == 237 and kq["ngoai"][0] > kq["ngoai"][1] > kq["ngoai"][2], str(kq["ngoai"]))
    ktra("chỉ có ảnh ngày -> đích ánh đèn lấy theo ánh sáng ngày", kq2["trong"] == kq2["ngoai"], str(kq2))
    ktra("không ảnh nào thấy da -> ValueError", loi_rong)

    # 6-8 giao diện thật
    try:
        import tkinter as tk
        import autotone_gui as ag
        import giao_dien as gd
        import hop_thoai as ht
        root = tk.Tk()
    except Exception as ex:                                  # noqa: BLE001
        print(f"  (bỏ phần giao diện: {type(ex).__name__}: {ex})")
        print("TAT CA DAT" if not LOI else f"{len(LOI)} LOI: {LOI}")
        return 1 if LOI else 0
    ag.bq.kiem = lambda: {"co_phep": True, "con_lai": timedelta(days=300), "nhac": "",
                          "goi": "1 năm", "may": "TEST01", "het_han": False, "ly_do": ""}
    root.geometry("1500x900+0+0")
    gd.dat_theme(root)
    job_cu, analyze_cu = at.LR_JOB_DIR, at.analyze
    at.LR_JOB_DIR = TAM / "jobs"
    at.LR_JOB_DIR.mkdir()
    lan_do: list = []

    def analyze_gia(pairs_, cfg_, jobs=1, progress=None, cancel=None):
        lan_do.append(sorted(Path(p).name for p, _ in pairs_))
        out = []
        for i, (p, sc) in enumerate(pairs_):
            r = ts._anh(Path(p).stem, -1.6, datetime(2026, 10, 1, 10, 0) + timedelta(seconds=30 * i))
            r.update(path=str(p), sidecar=str(sc))
            out.append(r)
        return out, []

    at.analyze = analyze_gia
    try:
        app = ag.App(root)
        app.grid(row=0, column=0, sticky="nsew")

        def vong(n=4):
            for _ in range(n):
                root.update_idletasks()
                root.update()
                time.sleep(0.02)

        def cho_do_xong(giay=15.0):
            het = time.time() + giay
            while time.time() < het:
                vong(1)
                if not app.busy and lan_do:
                    vong(3)
                    return True
            return False

        def hop():
            return [w for w in root.winfo_children() + app.winfo_children()
                    if isinstance(w, ht.LocMayLensDialog)]

        vong(8)
        d2 = lam_buoi("HaiMay", [SONY] * 4 + [NIKON] * 2)
        app.v_folder.set(str(d2))
        app.scan_folder()
        vong()
        app.start_analyze()
        vong()
        h = hop()
        ktra("buổi 2 máy: bấm Phân tích hiện hộp chọn máy / ống kính, chưa đo gì",
             len(h) == 1 and not lan_do, f"{len(h)} hộp, đo {lan_do}")
        if h:
            h[0].v_may[NIKON[0]].set(False)
            h[0]._dem()
            ktra("bỏ máy Nikon: hộp đếm 4/6", "4/6" in h[0].lbl.cget("text"), h[0].lbl.cget("text"))
            h[0]._chon()
            ktra("analyze nhận đúng 4 ảnh Sony", cho_do_xong() and len(lan_do[-1]) == 4
                 and len(app.items) == 4, str(lan_do))
            ktra("dòng trạng thái nói phân tích một phần", "Phân tích một phần" in app.lbl_status.cget("text"),
                 app.lbl_status.cget("text")[:100])
        app.start_analyze()
        vong()
        h = hop()
        ktra("lần sau hộp nhớ lựa chọn (Nikon vẫn bỏ tick)",
             len(h) == 1 and not h[0].v_may[NIKON[0]].get() and h[0].v_may[SONY[0]].get())
        if h:
            h[0].v_may[NIKON[0]].set(True)
            h[0].v_may[SONY[0]].set(False)
            h[0]._chon()
            ktra("đo nốt 2 ảnh Nikon", cho_do_xong() and len(lan_do[-1]) == 2, str(lan_do[-1:]))
        app.v_folder.set(str(TAM))
        app.scan_folder()
        app.v_folder.set(str(d2))
        app.scan_folder()
        vong()
        ktra("mở lại buổi: nạp GỘP đủ 6 ảnh, không đo lại", len(app.items) == 6 and len(lan_do) == 2,
             f"{len(app.items)} ảnh, {len(lan_do)} lần đo")
        d3 = lam_buoi("MotMay", [SONY] * 3)
        app.v_folder.set(str(d3))
        app.scan_folder()
        vong()
        app.start_analyze()
        vong()
        ktra("buổi 1 máy 1 ống kính: không hỏi, đo hết 3", not hop() and cho_do_xong()
             and len(lan_do[-1]) == 3, str(lan_do[-1:]))

        # 8
        app.v_bu_k.set("150")
        app.v_bu_tint.set("-3")
        c = app.read_cfg()
        ktra("ô Bù K / Tint vào read_cfg", c["bu_k_ca_buoi"] == 150 and c["bu_tint_ca_buoi"] == -3)
        ktra("màu da mặc định -> mau_da_dich None", c["mau_da_dich"] is None)
        app._ghi_mau_da({"Gu A": {"trong": md["trong"], "ngoai": md["ngoai"], "n_anh": 3}})
        app._dung_menu_mau_da()
        app.v_mau_da.set("Gu A")
        app._doi_mau_da()
        c = app.read_cfg()
        ktra("chọn mẫu 'Gu A' -> read_cfg mang đích riêng",
             (c["mau_da_dich"] or {}).get("trong") == md["trong"], str(c["mau_da_dich"]))
        luu = json.loads((Path(os.environ["AUTOTONE_DATA"]) / ag.FILE_MAU_DA).read_text(encoding="utf-8"))
        ktra("nhớ mẫu dùng gần nhất + mẫu của buổi này",
             luu.get("_cuoi") == "Gu A" and luu.get("_theo_buoi", {}).get(str(d3)) == "Gu A")
        app.v_mau_da.set(ag.MAU_DA_MAC_DINH)
        app.v_folder.set(str(d3))
        app.scan_folder()
        ktra("mở lại buổi -> ô Màu da đích về đúng mẫu của buổi", app.v_mau_da.get() == "Gu A")
        ktra("tên mẫu không lẫn khoá ghi nhớ '_'; menu có mẫu + Tạo + Xoá",
             all(not x.startswith("_") for x in app._ten_mau_da())
             and app.menu_mau_da.index("end") == len(app._ten_mau_da()) + 2)
        ag.messagebox.askyesno = lambda *a_, **k_: True
        app._xoa_mau_da()
        luu = json.loads((Path(os.environ["AUTOTONE_DATA"]) / ag.FILE_MAU_DA).read_text(encoding="utf-8"))
        ktra("xoá mẫu: về mặc định, gỡ khỏi ghi nhớ",
             app.v_mau_da.get() == ag.MAU_DA_MAC_DINH and "Gu A" not in luu and luu.get("_cuoi") != "Gu A")
    finally:
        at.LR_JOB_DIR, at.analyze = job_cu, analyze_cu
        try:
            root.destroy()
        except Exception:                                    # noqa: BLE001
            pass
    print("TAT CA DAT" if not LOI else f"{len(LOI)} LOI: {LOI}")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
