#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đọc thẳng cache preview + thông số Lightroom (doc_cache_lr.py — 14/10) trên catalog GIẢ.

CHUYỆN ĐANG CANH
    Preview đọc thẳng chỉ dùng được khi nó CÒN MỚI (digest khớp thông số trong catalog) —
    lấy nhầm preview cũ là đo da trên ảnh trước khi sửa mà không ai biết. LrC 15 ghi catalog
    qua WAL: đọc `immutable` là không thấy thay đổi mới. Ảnh dọc lưu chưa xoay.

Mục kiểm
    1. catalog có WAL đang mở (thay đổi chưa gộp): mo_catalog THẤY digest mới; immutable thì không
    2. preview_moi: digest khớp -> có; lệch (preview cũ) -> không; chỉ mức < cạnh -> không;
       chọn mức nhỏ nhất ≥ cạnh; bản sao ảo không tính; ảnh thư mục khác không tính
    3. doc(): Adobe RGB -> sRGB, xoay DA -> ảnh đứng
    4. thong_so(): bảng Lua lồng nhau, mảng, chuỗi có thoát, bool, số âm; dong_xuat: crop
       mặc định khi không có khoá Crop, curve "x,y,…", bool "1"/"0"
    5. không có Previews.lrdata / catalog hỏng -> rỗng / None, không ném lỗi

Chạy:  python test_doc_cache_lr.py
"""
from __future__ import annotations

import io
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
LOI: list = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


TEXT = '''s = { Exposure2012 = -0.35,
WhiteBalance = "Custom",
Temperature = 5214,
Tint = -3,
CameraProfile = "Adobe Standard",
ConvertToGrayscale = false,
ToneCurvePV2012Red = { 0, 0, 136, 133, 255, 255 },
Look = { Name = "Adobe Color", Parameters = { Version = 3 }, },
Ten = "a\\"b\\\\c",
}
'''


def tao_catalog(p: Path):
    con = sqlite3.connect(p)
    con.executescript("""
    create table AgLibraryRootFolder (id_local integer primary key, absolutePath);
    create table AgLibraryFolder (id_local integer primary key, rootFolder, pathFromRoot);
    create table AgLibraryFile (id_local integer primary key, folder, baseName, extension);
    create table Adobe_images (id_local integer primary key, rootFile, orientation, masterImage);
    create table Adobe_imageDevelopSettings (id_local integer primary key, image, digest, text);
    insert into AgLibraryRootFolder values (1, 'G:/');
    insert into AgLibraryFolder values (10, 1, 'Buoi/'), (11, 1, 'Khac/');
    """)
    for i in range(1, 7):
        con.execute("insert into AgLibraryFile values (?, ?, ?, 'ARW')", (100 + i, 10 if i < 6 else 11, f"DSC{i:04d}"))
        con.execute("insert into Adobe_images values (?, ?, ?, NULL)", (1000 + i, 100 + i, "DA" if i == 2 else "AB"))
        con.execute("insert into Adobe_imageDevelopSettings values (?, ?, ?, ?)", (i, 1000 + i, f"dg{i}", TEXT))
    #  bản sao ảo của ảnh 1 (cùng file)
    con.execute("insert into Adobe_images values (2001, 101, 'AB', 1001)")
    con.execute("insert into Adobe_imageDevelopSettings values (99, 2001, 'dgao', 's = {}')")
    con.commit()
    con.close()


def jpeg(w, h, mau, adobe=True) -> bytes:
    from PIL import Image, ImageCms
    im = Image.new("RGB", (w, h), mau)
    im.paste((255, 0, 0), (0, 0, 8, 8))                 # góc trên-trái đỏ -> soát xoay
    b = io.BytesIO()
    kw = {}
    if adobe:
        try:
            kw["icc_profile"] = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        except Exception:                                    # noqa: BLE001
            pass
    im.save(b, "JPEG", quality=95, **kw)
    return b.getvalue()


def main() -> int:
    tam = Path(tempfile.mkdtemp(prefix="doc_cache_lr_"))
    os.environ["AUTOTONE_DATA"] = str(tam / "du_lieu")
    import autotone as at
    import doc_cache_lr as dc

    cat = tam / "LR" / "Cat.lrcat"
    cat.parent.mkdir()
    tao_catalog(cat)

    print("1. WAL")
    giu = sqlite3.connect(cat)
    giu.execute("pragma journal_mode=wal")
    giu.execute("pragma wal_autocheckpoint=0")
    giu.execute("update Adobe_imageDevelopSettings set digest='dg3moi' where image=1003")
    giu.commit()                                         # còn trong WAL, chưa gộp
    wal = cat.with_name(cat.name + "-wal")
    ktra("có file WAL chưa gộp", wal.is_file() and wal.stat().st_size > 0)
    imm = sqlite3.connect(cat.as_uri() + "?mode=ro&immutable=1", uri=True)
    ktra("immutable KHÔNG thấy thay đổi trong WAL (vì sao phải chép)",
         imm.execute("select digest from Adobe_imageDevelopSettings where image=1003").fetchone()[0] == "dg3")
    imm.close()
    con = dc.mo_catalog(cat)
    anh = dc.anh_buoi(con, "G:/Buoi")
    k3 = at.khoa_duong_dan("G:/Buoi/DSC0003.ARW")
    ktra("mo_catalog THẤY digest mới trong WAL", anh.get(k3, {}).get("digest") == "dg3moi", str(anh.get(k3)))
    ktra("5 ảnh của thư mục, không tính bản sao ảo / thư mục khác",
         len(anh) == 5 and at.khoa_duong_dan("G:/Khac/DSC0006.ARW") not in anh, str(sorted(anh)))
    ktra("catalog gốc không bị đụng (vẫn WAL của Lightroom)", wal.is_file())

    print("2. preview_moi")
    pv = cat.with_name("Cat Previews.lrdata")
    (pv).mkdir()
    db = sqlite3.connect(pv / "previews.db")
    db.execute("create table ImageCacheEntry (imageId, uuid, digest, orientation)")
    muc = {1: (320, 1024, 2048), 2: (1024,), 3: (1024,), 4: (320, 640), 5: (2048,)}
    for i, ms in muc.items():
        u = f"{'ABCDE'[i - 1]}1234567-0000-0000-0000-00000000000{i}"
        dgv = "dg3" if i == 3 else f"dg{i}"              # ảnh 3: preview CŨ (trước thay đổi WAL)
        db.execute("insert into ImageCacheEntry values (?, ?, ?, ?)", (1000 + i, u, dgv, "DA" if i == 2 else "AB"))
        d = pv / u[0] / u[:4]
        d.mkdir(parents=True, exist_ok=True)
        for m in ms:
            w, h = (m, m * 2 // 3)
            (d / f"{u}-{dgv}_{m}").write_bytes(jpeg(w, h, (120, 100, 90)))
    db.commit()
    db.close()
    moi = dc.preview_moi(cat, anh, 1024)
    k = {i: at.khoa_duong_dan(f"G:/Buoi/DSC{i:04d}.ARW") for i in range(1, 6)}
    ktra("digest khớp + đủ mức -> có (1, 2, 5)", set(moi) == {k[1], k[2], k[5]}, str(sorted(moi)))
    ktra("chọn mức NHỎ NHẤT ≥ 1024 (ảnh 1 có 320/1024/2048 -> 1024)", moi[k[1]]["canh"] == 1024)
    ktra("ảnh 3 preview cũ (digest lệch) -> không dùng; ảnh 4 chỉ mức nhỏ -> không",
         k[3] not in moi and k[4] not in moi)
    ktra("cạnh 2048 -> chỉ ảnh có mức 2048", set(dc.preview_moi(cat, anh, 2048)) == {k[1], k[5]})

    print("3. doc()")
    a = dc.doc(moi[k[2]]["tep"], moi[k[2]]["xoay"])
    ktra("xoay DA -> ảnh ĐỨNG (1024×682 -> 682 rộng × 1024 cao)", a.shape[:2] == (1024, 682), str(a.shape))
    ktra("điểm đỏ góc trên-trái sau xoay nằm góc DƯỚI-trái",
         int(a[-1, 0, 0]) > 150 and int(a[-1, 0, 1]) < 120, str(a[-1, 0]))
    ktra("uint8 sRGB", a.dtype == np.uint8 and a.ndim == 3)

    print("4. thong_so / dong_xuat")
    st = dc.thong_so(TEXT)
    ktra("số / chuỗi / bool / mảng / bảng lồng", st.get("Exposure2012") == -0.35 and st.get("Temperature") == 5214
         and st.get("Tint") == -3 and st.get("ConvertToGrayscale") is False
         and st.get("ToneCurvePV2012Red") == [0, 0, 136, 133, 255, 255]
         and st.get("Look", {}).get("Parameters", {}).get("Version") == 3, str(st)[:200])
    ktra("chuỗi có thoát", st.get("Ten") == 'a"b\\c', repr(st.get("Ten")))
    d = dc.dong_xuat(st)
    ktra("dong_xuat: curve 'x,y,…', bool '0', crop mặc định đồng nhất",
         d["ToneCurvePV2012Red"] == "0,0,136,133,255,255" and d["ConvertToGrayscale"] == "0"
         and (d["CropLeft"], d["CropTop"], d["CropRight"], d["CropBottom"], d["CropAngle"]) == ("0", "0", "1", "1", "0")
         and at.cat_lr_cua(d) == (0.0, 0.0, 1.0, 1.0, 0.0), str({x: d.get(x) for x in ("CropLeft", "ToneCurvePV2012Red")}))
    ktra("text hỏng / rỗng -> {}", dc.thong_so("không phải lua") == {} and dc.thong_so(None) == {})

    print("5. thiếu / hỏng")
    ktra("không có Previews.lrdata -> rỗng", dc.preview_moi(tam / "khong" / "X.lrcat", anh) == {})
    hong = tam / "hong.lrcat"
    hong.write_bytes(b"khong phai sqlite")
    c2 = dc.mo_catalog(hong)
    ktra("catalog hỏng -> anh_buoi rỗng, không ném lỗi", c2 is None or dc.anh_buoi(c2, "G:/Buoi") == {})
    con.close()
    giu.close()
    print(f"\n{len(LOI)} LOI" if LOI else "\nTAT CA DAT")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
