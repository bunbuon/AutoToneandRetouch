#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đo da TRƯỚC khi áp trên preview Lightroom (do_truoc.py — 14/10) — catalog / cache / plugin GIẢ.

CHUYỆN ĐANG CANH
    Chuỗi một lượt đo da trên ảnh Lightroom ĐANG dựng. Lấy từ cache khi preview còn mới,
    thiếu thì nhờ plugin. Sai chỗ nào cũng là chỉnh màu theo một ảnh khác: ảnh dọc chưa
    xoay (mặt nạ đặt nhầm chỗ), preview cũ, nhầm thông số "cu" của mô hình.

Mục kiểm
    1. ảnh có preview mới trong cache -> đo từ cache (kể cả ảnh dọc lưu chưa xoay: da đúng màu),
       "st" = thông số catalog lúc dựng; ảnh 1★ / không mặt / đen trắng: không đo
    2. ảnh thiếu / preview cũ -> plugin (request_do_truoc.txt, chỉ preview) -> đo, nguồn "plugin"
    3. mảng giữ ≤ TOI_DA điểm
    4. plugin cũ (không khai truoc1): ảnh cache vẫn đo, ảnh thiếu bỏ + lý do
    5. huy() -> dừng, rút yêu cầu chưa nhận
    6. không có catalog -> mọi ảnh qua plugin

Chạy:  python test_do_truoc.py
"""
from __future__ import annotations

import io
import os
import sqlite3
import sys
import tempfile
import threading
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
LOI: list = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


def png(arr) -> bytes:
    from PIL import Image
    b = io.BytesIO()
    Image.fromarray(arr).save(b, "PNG")
    return b.getvalue()


def dung_lr(tam: Path, anh: list, cu: set):
    """Catalog + cache giả. anh: [(tên, mảng uint8 ĐỨNG, xoay)]; cu: tên có preview CŨ."""
    from PIL import Image
    cat = tam / "LR" / "C.lrcat"
    cat.parent.mkdir(parents=True)
    con = sqlite3.connect(cat)
    con.executescript("""
    create table AgLibraryRootFolder (id_local integer primary key, absolutePath);
    create table AgLibraryFolder (id_local integer primary key, rootFolder, pathFromRoot);
    create table AgLibraryFile (id_local integer primary key, folder, baseName, extension);
    create table Adobe_images (id_local integer primary key, rootFile, orientation, masterImage);
    create table Adobe_imageDevelopSettings (id_local integer primary key, image, digest, text);
    """)
    goc = str(tam / "Buoi").replace("\\", "/").rstrip("/")
    con.execute("insert into AgLibraryRootFolder values (1, ?)", (goc.rsplit("/", 1)[0] + "/",))
    con.execute("insert into AgLibraryFolder values (10, 1, ?)", (goc.rsplit("/", 1)[1] + "/",))
    pvd = cat.with_name("C Previews.lrdata")
    pvd.mkdir()
    db = sqlite3.connect(pvd / "previews.db")
    db.execute("create table ImageCacheEntry (imageId, uuid, digest, orientation)")
    for i, (ten, arr, xoay) in enumerate(anh, 1):
        con.execute("insert into AgLibraryFile values (?, 10, ?, 'ARW')", (100 + i, ten))
        con.execute("insert into Adobe_images values (?, ?, ?, NULL)", (1000 + i, 100 + i, xoay))
        con.execute("insert into Adobe_imageDevelopSettings values (?, ?, ?, ?)",
                    (i, 1000 + i, f"dg{i}", f's = {{ Exposure2012 = 0.{i}, WhiteBalance = "Custom", '
                                             f'Temperature = {5000 + i}, Tint = 3 }}'))
        u = f"{i:08X}-0000-0000-0000-000000000000"
        d = pvd / u[0] / u[:4]
        d.mkdir(parents=True, exist_ok=True)
        luu = arr if xoay == "AB" else np.asarray(Image.fromarray(arr).transpose(Image.Transpose.ROTATE_270))
        dg = "dgcu" if ten in cu else f"dg{i}"
        db.execute("insert into ImageCacheEntry values (?, ?, ?, ?)", (1000 + i, u, dg, xoay))
        (d / f"{u}-{dg}_1024").write_bytes(png(luu))
    con.commit()
    db.commit()
    con.close()
    db.close()
    return cat


def plugin_gia(jobs: Path, anh: dict, dung: threading.Event, nk: list):
    while not dung.is_set():
        req = jobs / "request_do_truoc.txt"
        if not req.exists():
            time.sleep(0.05)
            continue
        dong = req.read_text(encoding="utf-8").splitlines()
        req.unlink()
        opts, ds = {}, []
        for x in dong[1:]:
            k, _, v = x.partition("=")
            if k == "anh":
                ds.append(v)
            elif k:
                opts[k] = v
        nk.append(dict(opts, n=len(ds)))
        dest = Path(opts["dest"])
        cap = []
        for p in ds:
            f = dest / (Path(p).stem + ".jpg")
            f.write_bytes(png(anh[Path(p).stem]))
            cap.append(f"{p}\t{f}")
        (jobs / "do_truoc_anh.tsv").write_text("path\tjpg\n" + "\n".join(cap) + "\n", encoding="utf-8")
        (jobs / "do_truoc_tiendo.txt").write_text(f"trang_thai=xong\nxong={len(ds)}\ntong={len(ds)}\n"
                                                  f"ma={opts['ma']}\ncach=preview\n", encoding="utf-8")


def main() -> int:
    tam = Path(tempfile.mkdtemp(prefix="do_truoc_"))
    os.environ["AUTOTONE_DATA"] = str(tam / "du_lieu")
    import autotone as at
    import curve_da as cd
    import do_truoc as dt
    import test_curve_da as T

    T.cai_gia()                                  # mặt nạ giả, đo tại chỗ
    jobs = tam / "jobs"
    jobs.mkdir()
    (tam / "Buoi").mkdir()
    goc_arr = T.u8(T.canh())
    ten = ["A1", "A2", "A3", "A4", "A5", "A6"]
    anh = {t: goc_arr for t in ten}
    #  A2 dọc (lưu chưa xoay trong cache) — ảnh "đứng" của nó = ảnh xoay
    from PIL import Image
    doc_arr = np.asarray(Image.fromarray(goc_arr).transpose(Image.Transpose.ROTATE_90))
    anh["A2"] = doc_arr
    cat = dung_lr(tam, [(t, anh[t], "DA" if t == "A2" else "AB") for t in ten], cu={"A3"})
    H, W = goc_arr.shape[:2]

    def item(t, **kw):
        r = dict(T.anh(t), path=str(tam / "Buoi" / f"{t}.ARW"), cat_lr=(0, 0, 1, 1, 0), **kw)
        if t == "A2":                       # khung mặt trên ảnh ĐỨNG (dọc)
            x, y, w, h = T.MAT
            r["meter_boxes"] = [[y, W - x - w, h, w]]
            r["preview_wh"] = (H, W)
        return r
    items = [item("A1"), item("A2"), item("A3"), item("A4", rating=1), item("A5", meter_boxes=[]),
             item("A6", bw=True)]
    (jobs / at.NHIP_PLUGIN).write_text("vong=1\nkha_nang=curve1,xem1,truoc1\n", encoding="utf-8")

    print("1-3. cache + plugin")
    dung, nk = threading.Event(), []
    th = threading.Thread(target=plugin_gia, args=(jobs, anh, dung, nk), daemon=True)
    th.start()
    try:
        kq = dt.chay(tam / "Buoi", items, dict(at.DEFAULTS, mot_luot_do_moi_loat=0), job_dir=jobs, catalog=cat)
    finally:
        dung.set()
        th.join(2)
    r = {x["path"].rsplit("\\", 1)[-1].rsplit("/", 1)[-1][:2]: x for x in items}
    ktra("cần đo 3 ảnh (bỏ 1★, không mặt, đen trắng)", kq["tong"] == 3 and all(
        "lr_truoc" not in r[t] for t in ("A4", "A5", "A6")), str(kq))
    ktra("A1, A2 từ cache; A3 (preview cũ) qua plugin", r["A1"].get("lr_truoc", {}).get("nguon") == "cache"
         and r["A2"].get("lr_truoc", {}).get("nguon") == "cache"
         and r["A3"].get("lr_truoc", {}).get("nguon") == "plugin" and kq["do"] == 3 and kq["plugin"] == 1, str(kq))
    ktra("plugin chỉ được xin ảnh thiếu (1 ảnh), chỉ preview, cạnh 1600 (mặt đủ lớn cho phân vùng)",
         len(nk) == 1 and nk[0]["n"] == 1 and nk[0]["chi_preview"] == "1" and nk[0]["canh"] == "1600", str(nk))
    st = r["A1"]["lr_truoc"].get("st") or {}
    ktra("'st' = thông số catalog lúc dựng (Exposure 0.1, K 5001, crop đồng nhất)",
         st.get("Exposure2012") == "0.1" and st.get("Temperature") == "5001" and st.get("CropRight") == "1", str(st))
    h1 = cd.hue_q(cd.thong_ke(r["A1"]["lr_truoc"]["da_mn"], r["A1"]["lr_truoc"]["mien"]))[0]
    h2 = cd.hue_q(cd.thong_ke(r["A2"]["lr_truoc"]["da_mn"], r["A2"]["lr_truoc"]["mien"]))[0]
    ktra("ảnh dọc lưu chưa xoay: xoay đứng -> da đúng chỗ, cùng màu ảnh ngang", abs(h1 - h2) < 0.5,
         f"{h1:.2f}° / {h2:.2f}°")
    ktra("mảng ≤ TOI_DA điểm", all(len(r[t]["lr_truoc"][k]) <= dt.TOI_DA for t in ("A1", "A2", "A3")
                                   for k in ("da_mn", "trung", "khung") if r[t]["lr_truoc"].get(k) is not None))
    ktra("thư mục tạm của plugin đã dọn", not any((Path(os.environ["AUTOTONE_DATA"]) / "do_truoc_tam").glob("*")))

    print("4. plugin cũ")
    (jobs / at.NHIP_PLUGIN).write_text("vong=1\nkha_nang=curve1,xem1\n", encoding="utf-8")
    kq = dt.chay(tam / "Buoi", items, dict(at.DEFAULTS, mot_luot_do_moi_loat=0), job_dir=jobs, catalog=cat)
    ktra("ảnh cache vẫn đo; ảnh thiếu bỏ + lý do 'truoc1'",
         kq["do"] == 2 and "lr_truoc" not in r["A3"] and "truoc1" in kq["ly_do"], str(kq))

    print("5. huỷ")
    (jobs / at.NHIP_PLUGIN).write_text("vong=1\nkha_nang=curve1,xem1,truoc1\n", encoding="utf-8")
    kq = dt.chay(tam / "Buoi", items, dict(at.DEFAULTS, mot_luot_do_moi_loat=0), job_dir=jobs, catalog=cat, huy=lambda: True)
    ktra("huy() -> không chờ Lightroom, không để lại yêu cầu, lý do 'đã dừng'",
         not (jobs / dt.TEN_YEU_CAU).exists() and kq["plugin"] == 0 and kq["ly_do"] == "đã dừng", str(kq))

    print("6. không có catalog")
    dung, nk = threading.Event(), []
    th = threading.Thread(target=plugin_gia, args=(jobs, anh, dung, nk), daemon=True)
    th.start()
    try:
        kq = dt.chay(tam / "Buoi", items, dict(at.DEFAULTS, mot_luot_do_moi_loat=0), job_dir=jobs, catalog=tam / "khong.lrcat")
    finally:
        dung.set()
        th.join(2)
    ktra("mọi ảnh qua plugin, vẫn đo đủ 3", kq["do"] == 3 and kq["plugin"] == 3 and kq["cache"] == 0, str(kq))

    print("7. lấy mẫu theo loạt (14/10: trong loạt da lệch ~3% — đo tối đa 2 ảnh mỗi loạt)")
    from datetime import timedelta
    t0_ = T.anh("x")["dt_obj"]
    loat = [dict(T.anh(f"L{i}", dt=t0_ + timedelta(seconds=2 * i))) for i in range(5)]
    le = dict(T.anh("LE", dt=t0_ + timedelta(hours=1)))
    chon = [Path(r["path"]).stem for r in dt.mau_loat(loat + [le], dict(at.DEFAULTS), 2)]
    ktra("loạt 5 ảnh -> 2 ảnh rải đều (đầu, cuối); ảnh lẻ giữ", chon == ["L0", "L4", "LE"], str(chon))
    ktra("n = 0 -> mọi ảnh", len(dt.mau_loat(loat + [le], dict(at.DEFAULTS), 0)) == 6)
    print(f"\n{len(LOI)} LOI" if LOI else "\nTAT CA DAT")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
