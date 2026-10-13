#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Canon CR3: EXIF + ảnh nhúng + hướng ảnh (13/10).

CHUYỆN ĐANG CANH
    User 13/10 (bộ CR3 Canon EOS R, 1/500 f/4 ISO 250): "load ảnh preview không đúng định
    dạng — đo sáng các bức cùng cảnh và thông số bị sáng và tối khác nhau". CR3 là khung
    ISO-BMFF (như MP4), không phải TIFF: read_raw / doc_the / anh_nho chỉ đọc EXIF khi file
    mở đầu bằng II/MM nên CR3 ra tags RỖNG — không hướng ảnh (ảnh dọc nằm ngang, YuNet lúc
    thấy mặt lúc không), không tốc / khẩu / ISO / giờ (chia_loat không gom được loạt ->
    "cùng khung + cùng thông số -> cùng một mức" không chạy).

    File CR3 GIẢ dựng đúng cấu trúc hộp của file thật (đối chiếu file mẫu CanonRaw.cr3 của
    ExifTool: ftyp "crx " · moov{uuid 85c0b687…{CMT1, CMT2, THMB}, trak{…stsz, co64}} ·
    uuid eaf42b5e…{PRVW} · mdat). Hàm THẬT: read_raw, doc_the, anh_nho, measure, chia_loat.

Mục kiểm
    1. read_raw / doc_the: máy, hướng ảnh, giờ chụp, tốc, khẩu, ISO, ống kính từ CMT1 + CMT2
    2. read_raw: ảnh nhúng lấy JPEG CỠ GỐC (mẫu đầu trak 1)
    3. anh_nho: lấy PRVW (không đọc 16 MB / ảnh cỡ gốc), XOAY đúng hướng (ảnh dọc đứng)
    4. measure: ảnh dọc xoay đúng (preview_wh dọc), EV100 có, máy đúng
    5. hai tấm cùng thông số, cách 5 giây -> chia_loat gom MỘT loạt
    6. (tuỳ chọn) file CR3 thật: AUTOTONE_CR3=<file> — có máy, ISO, hướng

Chạy:  python test_cr3.py
"""
from __future__ import annotations

import io
import mmap
import os
import shutil
import struct
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at  # noqa: E402

LOI = []
TAM = Path(tempfile.mkdtemp(prefix="test_cr3_"))


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


# ------------------------------------------------------------------ dựng CR3 giả

def tiff(the: dict) -> bytes:
    """Khối TIFF (II) một IFD. the: {tag: ("A", chữ) | ("H", số) | ("R", (tử, mẫu))}."""
    ds = sorted(the.items())
    n = len(ds)
    dau = 8 + 2 + n * 12 + 4
    ngoai = b""
    muc = b""
    for tag, (kieu, v) in ds:
        if kieu == "A":
            gt = v.encode("ascii") + b"\0"
            typ, cnt = 2, len(gt)
        elif kieu == "H":
            gt, typ, cnt = struct.pack("<H", v) + b"\0\0", 3, 1
        else:
            gt, typ, cnt = struct.pack("<II", *v), 5, 1
        if len(gt) <= 4:
            muc += struct.pack("<HHI", tag, typ, cnt) + gt.ljust(4, b"\0")
        else:
            muc += struct.pack("<HHII", tag, typ, cnt, dau + len(ngoai))
            ngoai += gt + (b"\0" if len(gt) % 2 else b"")
    return b"II*\0" + struct.pack("<I", 8) + struct.pack("<H", n) + muc + b"\0\0\0\0" + ngoai


def hop(kieu: bytes, noi: bytes) -> bytes:
    return struct.pack(">I", 8 + len(noi)) + kieu + noi


def jpeg(w, h, mau_goc=(220, 30, 30)) -> bytes:
    """Ảnh theo chiều CẢM BIẾN (ngang); góc trái-trên tô đỏ để thấy chiều xoay."""
    a = np.full((h, w, 3), 90, np.uint8)
    a[: h // 3, : w // 3] = mau_goc
    b = io.BytesIO()
    Image.fromarray(a).save(b, "JPEG", quality=90)
    return b.getvalue()


def cr3(p: Path, huong=6, gio="2026:10:13 10:00:00", iso=250, toc=(1, 500), khau=(40, 10)):
    cmt1 = tiff({271: ("A", "Canon"), 272: ("A", "Canon EOS R6m2"), 274: ("H", huong),
                 306: ("A", gio)})
    cmt2 = tiff({33434: ("R", toc), 33437: ("R", khau), 34855: ("H", iso),
                 36867: ("A", gio), 42036: ("A", "RF24-105mm F4 L IS USM")})
    thmb = b"\0" * 16 + jpeg(160, 120)
    canon = hop(b"uuid", at._UUID_CANON + hop(b"CNCV", b"CanonCR3_001/00.09.00/00.00.00")    # noqa: SLF001
                + hop(b"CMT1", cmt1) + hop(b"CMT2", cmt2) + hop(b"THMB", thmb))
    goc = jpeg(1800, 1200)                       # "cỡ gốc" (thật 6000 px — nhỏ cho bài kiểm)
    prvw = jpeg(900, 600, (30, 200, 30))          # "PRVW" (thật 1620 px) — góc XANH để biết nguồn

    raw = b"CRX-RAW-" * 512                      # trak 2..4 của CR3 thật: dữ liệu raw / CTMD, KHÔNG phải JPEG

    def trak(stsz, co64):
        return hop(b"trak", hop(b"tkhd", b"\0" * 84) + hop(b"mdia", hop(b"minf", hop(b"stbl", stsz + co64))))

    def moov(vi_tri_goc):
        #  trak 1: bảng cỡ từng mẫu (cỡ chung 0); trak 2: cỡ chung — hai dạng stsz có thật
        t1 = trak(hop(b"stsz", b"\0\0\0\0" + struct.pack(">II", 0, 1) + struct.pack(">I", len(goc))),
                  hop(b"co64", b"\0\0\0\0" + struct.pack(">I", 1) + struct.pack(">Q", vi_tri_goc)))
        t2 = trak(hop(b"stsz", b"\0\0\0\0" + struct.pack(">II", len(raw), 1)),
                  hop(b"co64", b"\0\0\0\0" + struct.pack(">I", 1) + struct.pack(">Q", vi_tri_goc + len(goc))))
        return hop(b"moov", canon + t1 + t2)
    ftyp = hop(b"ftyp", b"crx \0\0\0\x01crx isom")
    uprvw = hop(b"uuid", at._UUID_PRVW + b"\0" * 8                                        # noqa: SLF001
                + hop(b"PRVW", b"\0\0\0\0\0\0\0\x01" + struct.pack(">HH", 900, 600) + b"\0" * 8 + prvw))
    dau = len(ftyp) + len(moov(0)) + len(uprvw) + 8
    p.write_bytes(ftyp + moov(dau) + uprvw + hop(b"mdat", goc + raw + b"\0" * 64))
    return p


# ------------------------------------------------------------------ mục

def muc1(f):
    """1. EXIF từ CMT1 + CMT2"""
    _blob, t = at.read_raw(f)
    ktra("read_raw: máy Canon EOS R6m2", t.get("model") == "Canon EOS R6m2", str(t.get("model")))
    ktra("read_raw: hướng ảnh 6 (dọc)", t.get("orientation") == 6, str(t.get("orientation")))
    ktra("read_raw: tốc 1/500, khẩu f/4, ISO 250", t.get("exposure_time") == (1, 500)
         and t.get("fnumber") == (40, 10) and t.get("iso") == 250, str(t))
    ktra("read_raw: giờ chụp + ống kính", t.get("datetime_original") == "2026:10:13 10:00:00"
         and t.get("lens") == "RF24-105mm F4 L IS USM")
    ktra("read_raw: EV100 tính được", at.ev_anh_sang(t) is not None, str(at.ev_anh_sang(t)))
    d = at.doc_the(f)
    ktra("doc_the (lọc máy / ống kính): cùng máy + ống kính", d.get("model") == "Canon EOS R6m2"
         and d.get("lens") == "RF24-105mm F4 L IS USM")


def muc2(f):
    """2. ảnh nhúng cỡ gốc"""
    blob, _t = at.read_raw(f)
    sz = Image.open(io.BytesIO(blob)).size if blob else None
    ktra("read_raw: lấy JPEG cỡ gốc (trak 1)", sz == (1800, 1200), str(sz))
    #  read_raw còn đường quét JPEG dự phòng ở đầu file nên tự nó không nói được trak có
    #  đọc đúng không — kiểm thẳng danh sách ảnh nhúng _doc_cr3 trả ra
    with open(f, "rb") as fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as mm:
        jp: list = []
        at._doc_cr3(mm, {}, jp)                                                   # noqa: SLF001
        co = []
        for o, ln in jp:
            khoi = bytes(mm[o:o + ln])
            try:
                co.append(Image.open(io.BytesIO(khoi)).size if khoi[:3] == b"\xff\xd8\xff" else "khong-jpeg")
            except OSError:
                co.append("hong")
    ktra("_doc_cr3: JPEG cỡ gốc lấy từ mẫu đầu của trak 1, không lấy trak raw",
         co.count((1800, 1200)) == 1 and "khong-jpeg" not in co and "hong" not in co, str(co))


def muc3(f):
    """3. anh_nho: PRVW, xoay đúng"""
    goc_rr = at.read_raw

    def cam(*_a, **_k):
        raise AssertionError("anh_nho gọi read_raw cho CR3")
    at.read_raw = cam
    try:
        im = at.anh_nho(f, 320)
    except AssertionError as ex:
        im = None
        ktra("anh_nho: không lùi về read_raw (đọc PRVW trực tiếp)", False, str(ex))
    finally:
        at.read_raw = goc_rr
    if im is None:
        return
    ktra("anh_nho: ảnh dọc ĐỨNG (cao > rộng)", im.size[1] > im.size[0], str(im.size))
    #  hướng 6 = xoay 90° chiều kim đồng hồ: góc trái-trên đỏ của cảm biến -> góc PHẢI-trên
    w, h = im.size
    pr, pt = im.getpixel((w - 5, 5)), im.getpixel((5, 5))
    ktra("anh_nho: góc đánh dấu sang PHẢI-trên (xoay đúng chiều)",
         max(pr) > 180 and min(pr) < 80 and max(pt) < 150, f"phải-trên {pr} trái-trên {pt}")
    ktra("anh_nho: lấy PRVW (góc xanh), không giải mã ảnh cỡ gốc (góc đỏ)",
         pr[1] > 150 and pr[0] < 100, str(pr))
    #  Kho ảnh nhỏ trên đĩa đã giữ bản NẰM NGANG của CR3 từ trước 13/10 -> khoá phải đổi,
    #  không thì lưới vẫn hiện ảnh cũ dù đã đọc đúng hướng.
    import hashlib
    import nguon_xem
    st = os.stat(f)
    van = f"{os.path.normcase(os.path.abspath(str(f)))}|{st.st_mtime_ns}|{st.st_size}|1600"
    ktra("ảnh xem RAW: khoá CR3 đổi (bản nằm ngang cũ không dùng lại)",
         nguon_xem._khoa(f, 1600) != hashlib.sha1(van.encode()).hexdigest())
    try:
        import luoi_anh
    except ImportError as ex:            # python không có tkinter: phần này chạy ở bài GUI
        print(f"[BO QUA] kho ảnh nhỏ của lưới: {ex}")
        return
    cu = hashlib.sha1(f"{f}|{st.st_mtime_ns}|{st.st_size}|{luoi_anh.CANH_KHO}".encode()).hexdigest()
    ktra("kho ảnh nhỏ: khoá CR3 đổi (ảnh nằm ngang cũ không dùng lại)",
         luoi_anh.khoa_kho(str(f)) != f"{cu[:2]}/{cu[2:22]}.jpg")


def muc4(f):
    """4. measure"""
    tham = at.cau_hinh_do(dict(at.DEFAULTS, canh_p365=False))
    r = at.measure(f, *tham)
    ktra("measure: ok", r.get("ok"), str(r.get("loi") or r.get("notes", ""))[:120])
    wh = r.get("preview_wh") or (0, 0)
    ktra("measure: preview đã xoay dọc", wh[1] > wh[0], str(wh))
    ktra("measure: máy + EV100", r.get("model") == "Canon EOS R6m2" and at.ev100(r) is not None,
         f"{r.get('model')} {at.ev100(r)}")
    return r


def muc5():
    """5. chia_loat gom loạt"""
    from datetime import datetime
    tham = at.cau_hinh_do(dict(at.DEFAULTS, canh_p365=False))
    ds = []
    for i, gio in enumerate(("2026:10:13 10:00:00", "2026:10:13 10:00:05")):
        r = at.measure(cr3(TAM / f"L{i}.CR3", gio=gio), *tham)
        r["dt_obj"] = datetime.fromisoformat(r["dt"])          # như analyze()
        r["scene"] = 0
        ds.append(r)
    ktra("giờ chụp lấy từ EXIF (không lấy giờ sửa file)",
         [r["dt"] for r in ds] == ["2026-10-13T10:00:00", "2026-10-13T10:00:05"]
         or [r["dt"][:19] for r in ds] == ["2026-10-13T10:00:00", "2026-10-13T10:00:05"],
         str([r["dt"] for r in ds]))
    loat = at.chia_loat(ds, dict(at.DEFAULTS))
    ktra("hai tấm cùng thông số cách 5 giây: MỘT loạt", len(loat) == 1 and len(loat[0]) == 2,
         f"{[len(x) for x in loat]} · thông số {[(r.get('exposure_time'), r.get('iso')) for r in ds]}")


def muc6():
    """6. file CR3 thật (tuỳ chọn)"""
    p = os.environ.get("AUTOTONE_CR3")
    if not p or not Path(p).is_file():
        print("  BỎ QUA: đặt AUTOTONE_CR3=<file .CR3 thật>")
        return
    t = at.doc_the(p)
    ktra("CR3 thật: có máy, ISO, tốc, hướng", bool(t.get("model")) and t.get("iso") is not None
         and t.get("exposure_time") is not None and t.get("orientation") is not None, str(t))


def main():
    f = cr3(TAM / "A.CR3")
    for m in (muc1, muc2, muc3, muc4, muc5, muc6):
        print(m.__doc__.splitlines()[0])
        try:
            m(f) if m in (muc1, muc2, muc3, muc4) else m()
        except Exception as ex:                                  # noqa: BLE001
            import traceback
            traceback.print_exc()
            ktra(f"{m.__name__} không sập", False, repr(ex))
    shutil.rmtree(TAM, ignore_errors=True)
    print(f"\n{len(LOI)} LOI" if LOI else "\nTAT CA DAT")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
