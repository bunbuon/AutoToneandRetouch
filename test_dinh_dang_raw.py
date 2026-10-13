#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tám đuôi RAW của ba hãng: Canon CR2 / CR3 / CRW · Nikon NEF / NRW · Sony ARW / SRF / SR2 (13/10).

CHUYỆN ĐANG CANH
    User 13/10: "phân tích luôn các định dạng file" (sau khi CR3 ra tags RỖNG — xem
    test_cr3.py). Rà bằng file THẬT (27 RAW của bộ ảnh mẫu metadata-extractor + mẫu
    ExifTool / Exiv2, đối chiếu ExifTool từng số) thì thấy:
      · .CRW và .NRW KHÔNG có trong RAW_EXTS -> app không nhận file, buổi chụp "trống";
      · CRW (CIFF) mở đầu "II" như TIFF nhưng KHÔNG phải TIFF -> lọt nhánh TIFF, đọc
        offset rác -> tags rỗng hẳn (không máy, hướng, ISO, tốc, khẩu, giờ) — y bệnh CR3;
      · Nikon D70 / D70s không ghi ISO vào EXIF chuẩn (chỉ trong MakerNote) -> EV100 rỗng.
    Các khung còn lại (ARW, SR2, SRF, NEF, NRW, CR2) là TIFF, đi chung một đường đọc.

    File GIẢ dựng đúng cấu trúc file thật (CIFF: đống lồng nhau, bảng bản ghi 10 byte ở
    cuối đống, vị trí tính từ đầu đống — như "Canon EOS 10D.crw"; TIFF: IFD0 + EXIF IFD +
    MakerNote "Nikon\\0" + JPEG nhúng). Số đích lấy từ ExifTool trên file thật (ghi rõ).
    Hàm THẬT: collect_pairs, doc_the, read_raw, anh_nho, measure.

Mục kiểm
    1. RAW_EXTS + collect_pairs nhận đủ 8 đuôi (cả chữ hoa)
    2. CRW: máy, hướng (Rotation 270 -> 8, 90 -> 6), giờ, ISO / khẩu / tốc / bù sáng (số ExifTool)
    3. CRW: ảnh nhúng JpgFromRaw — read_raw lấy nó, anh_nho xoay đúng, measure chạy
    4. CRW / CR3 hỏng (đống tự trỏ, lồng sâu, cắt cụt, số rác) không treo, không sập
    5. Khung TIFF dưới mọi đuôi (.NRW .SRF .SR2 .NEF .ARW .CR2): EXIF + hướng + ảnh nhúng
    6. Nikon: ISO từ MakerNote khi EXIF thiếu; EXIF có thì giữ số EXIF
    7. (tuỳ chọn) thư mục RAW thật: AUTOTONE_RAW_MAU=<thư mục> — mỗi file có máy / ISO /
       tốc / khẩu, ảnh nhỏ đọc được

Chạy:  python test_dinh_dang_raw.py
"""
from __future__ import annotations

import io
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
TAM = Path(tempfile.mkdtemp(prefix="test_dinh_dang_"))
TAM_DUOI = (".CR2", ".CR3", ".CRW", ".NEF", ".NRW", ".ARW", ".SRF", ".SR2")


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


def jpeg(w, h, mau_goc=(220, 30, 30)) -> bytes:
    """Ảnh theo chiều CẢM BIẾN (ngang); góc trái-trên tô màu để thấy chiều xoay."""
    a = np.full((h, w, 3), 90, np.uint8)
    a[: h // 3, : w // 3] = mau_goc
    b = io.BytesIO()
    Image.fromarray(a).save(b, "JPEG", quality=90)
    return b.getvalue()


def goc_mau(im) -> str:
    """Góc nào đang mang màu đánh dấu: tt / tp / dt / dp (trên-trái / trên-phải / dưới-...)."""
    w, h = im.size
    o = {"tt": (5, 5), "tp": (w - 6, 5), "dt": (5, h - 6), "dp": (w - 6, h - 6)}
    return ",".join(k for k, xy in o.items() if max(im.getpixel(xy)) > 180)


# ------------------------------------------------------------------ CRW (CIFF) giả

def dong(ghi: list) -> bytes:
    """Một đống CIFF: dữ liệu, rồi bảng bản ghi, rồi 4 byte vị trí bảng (tính từ đầu đống).
    ghi: [(thẻ, bytes)] — thẻ kiểu 0x2800 / 0x3000 thì bytes là một đống con đã dựng."""
    du, bang = b"", []
    for the, noi in ghi:
        bang.append(struct.pack("<HII", the, len(noi), len(du)))
        du += noi + (b"\0" if len(noi) % 2 else b"")
    return du + struct.pack("<H", len(bang)) + b"".join(bang) + struct.pack("<I", len(du))


#  ShotInfo (0x102a) THẬT của hai file mẫu, số đích là ExifTool trên chính file đó
SHOT_10D = [66, 0, 160, 300, 221, 255, -20, 0, 3, 0, 8, 8, 0, 0, 0, 0, 0, 0, 1, 0, 0,
            228, 252, 164, 0, 0, 252, 3, -1, 0, 0, 0, 0]       # ISO 100, f/11.8146, 0.0042598 s, −0.667
SHOT_REBEL = [66, 0, 160, -160, 116, 189, 0, 0, 3, 0, 8, 8, 0, -1, 0, 20, 0, 0, 1, 142, 119,
              116, 192, 47, 0, 0, 252, 0, -1, 0, 0, 0, 0]       # ISO 100, f/3.5636, 1/64 s


def crw(p: Path, xoay=270, gio=1058190376, shot=SHOT_10D, may=b"Canon\0Canon EOS 10D\0",
        anh: bytes | None = None, them_goc: bytes = b"", exif_truoc=False) -> Path:
    """Bố cục như "Canon EOS 10D.crw": gốc{JpgFromRaw, ImageProps{ImageInfo, TimeStamp,
    0x2807{MakeModel}}, ExifInformation{ShotInfo}}."""
    anh = jpeg(1536, 1024) if anh is None else anh
    info = struct.pack("<IIIiIII", 3072, 2048, 0x3F800000, xoay, 8, 24, 257)
    props = dong([(0x1810, info),                               # ImageInfo: kiểu u32
                  (0x180E, struct.pack("<III", gio, 0, 0)),
                  (0x2807, dong([(0x080A, may.ljust(32, b"\0"))]))])
    exif = dong([(0x102A, struct.pack(f"<{len(shot)}h", *shot))])
    goc = dong([(0x2007, anh), (0x300B, exif), (0x300A, props)] if exif_truoc
               else [(0x2007, anh), (0x300A, props), (0x300B, exif)])
    p.write_bytes(b"II" + struct.pack("<I", 26) + b"HEAPCCDR" + b"\x02\0\x01\0" + b"\0" * 8
                  + goc + them_goc)
    return p


# ------------------------------------------------------------------ TIFF giả

def ifd(the: dict, dau: int) -> bytes:
    """Một IFD (II) đặt ở vị trí tuyệt đối `dau`. the: {tag: (kiểu, giá trị)}."""
    ds = sorted(the.items())
    ngoai_dau = dau + 2 + 12 * len(ds) + 4
    muc, ngoai = b"", b""
    for tag, (k, v) in ds:
        if k == "A":
            gt, typ, cnt = v.encode("ascii") + b"\0", 2, len(v) + 1
        elif k == "H":
            gt, typ, cnt = struct.pack("<H", v), 3, 1
        elif k == "H2":
            gt, typ, cnt = struct.pack("<HH", *v), 3, 2
        elif k == "L":
            gt, typ, cnt = struct.pack("<I", v), 4, 1
        elif k == "R":
            gt, typ, cnt = struct.pack("<II", *v), 5, 1
        else:                                                  # "U": bytes
            gt, typ, cnt = v, 7, len(v)
        if len(gt) <= 4:
            muc += struct.pack("<HHI", tag, typ, cnt) + gt.ljust(4, b"\0")
        else:
            muc += struct.pack("<HHII", tag, typ, cnt, ngoai_dau + len(ngoai))
            ngoai += gt + (b"\0" if len(gt) % 2 else b"")
    return struct.pack("<H", len(ds)) + muc + b"\0\0\0\0" + ngoai


def tiff_raw(p: Path, may="NIKON D70", hang="NIKON CORPORATION", huong=6, iso=200,
             makernote: bytes | None = None) -> Path:
    """IFD0 (máy, hướng, JPEG nhúng) -> EXIF IFD (tốc, khẩu, ISO, giờ, MakerNote)."""
    anh = jpeg(1200, 800)
    exif = {0x829A: ("R", (1, 250)), 0x829D: ("R", (56, 10)), 0x9003: ("A", "2026:10:13 09:00:00")}
    if iso:
        exif[0x8827] = ("H", iso)
    if makernote:
        exif[0x927C] = ("U", makernote)

    def ifd0(vi_exif, vi_anh):
        return ifd({0x010F: ("A", hang), 0x0110: ("A", may), 0x0112: ("H", huong),
                    0x0201: ("L", vi_anh), 0x0202: ("L", len(anh)), 0x8769: ("L", vi_exif)}, 8)
    n0 = len(ifd0(0, 0))
    b_exif = ifd(exif, 8 + n0)
    p.write_bytes(b"II*\0" + struct.pack("<I", 8) + ifd0(8 + n0, 8 + n0 + len(b_exif)) + b_exif + anh)
    return p


def nikon_mn(iso: int) -> bytes:
    """MakerNote Nikon kiểu 2: "Nikon\\0" + phiên bản + TIFF riêng (vị trí tính từ +10)."""
    return b"Nikon\0\x02\x10\0\0" + b"II*\0" + struct.pack("<I", 8) + ifd({0x0002: ("H2", (0, iso))}, 8)


# ------------------------------------------------------------------ mục

def muc1():
    """1. RAW_EXTS + collect_pairs: đủ 8 đuôi"""
    thieu = [d for d in TAM_DUOI if d.lower() not in at.RAW_EXTS]
    ktra("RAW_EXTS có đủ CR2 CR3 CRW NEF NRW ARW SRF SR2", not thieu, f"thiếu {thieu}")
    d = TAM / "buoi"
    d.mkdir()
    for i, duoi in enumerate(TAM_DUOI):
        (d / f"A{i}{duoi if i % 2 else duoi.lower()}").write_bytes(b"x")
    pairs, _ = at.collect_pairs(d, need_sidecar=False)
    ktra("collect_pairs nhận cả 8 file (hoa / thường)", len(pairs) == 8,
         str(sorted(p.suffix for p, _ in pairs)))


def muc2():
    """2. CRW: EXIF từ CIFF"""
    t = at.doc_the(crw(TAM / "B.CRW"))
    ktra("CRW: máy Canon EOS 10D", (t.get("make"), t.get("model")) == ("Canon", "Canon EOS 10D"), str(t))
    ktra("CRW: Rotation 270 -> Orientation 8", t.get("orientation") == 8, str(t.get("orientation")))
    ktra("CRW: giờ chụp 2003:07:14 13:46:16 (ExifTool)", t.get("datetime_original") == "2003:07:14 13:46:16",
         str(t.get("datetime_original")))
    tt, kk = at._rat(t.get("exposure_time")), at._rat(t.get("fnumber"))          # noqa: SLF001
    ktra("CRW 10D: ISO 100, f/11.8146, 0.0042598 s (ExifTool)",
         t.get("iso") == 100 and kk and abs(kk - 11.8146) < 0.01 and tt and abs(tt / 0.00425980 - 1) < 0.002,
         f"iso {t.get('iso')} f {kk} t {tt}")
    ktra("CRW 10D: bù sáng −2/3 (mã 0x14 = 2/3 stop)",
         abs((at._rat(t.get("exposure_bias")) or 9) + 0.6667) < 0.01, str(t.get("exposure_bias")))  # noqa: SLF001
    t = at.doc_the(crw(TAM / "C.CRW", xoay=90, shot=SHOT_REBEL, may=b"Canon\0Canon EOS DIGITAL REBEL\0"))
    tt, kk = at._rat(t.get("exposure_time")), at._rat(t.get("fnumber"))          # noqa: SLF001
    ktra("CRW Rebel: ISO 100, f/3.5636, 1/64 s (ExifTool)",
         t.get("iso") == 100 and kk and abs(kk - 3.5636) < 0.01 and tt and abs(tt - 1 / 64) < 1e-6,
         f"iso {t.get('iso')} f {kk} t {tt}")
    ktra("CRW: Rotation 90 -> Orientation 6", t.get("orientation") == 6, str(t.get("orientation")))
    #  mã 1/3 stop (0x0c): f/2.8 + 1/3 stop = f/3.2 trên máy
    shot = list(SHOT_REBEL)
    shot[21] = 96 + 0x0C
    k = at._rat(at.doc_the(crw(TAM / "D.CRW", shot=shot)).get("fnumber"))         # noqa: SLF001
    ktra("CRW: mã khẩu 1/3 stop (96+0x0c) = f/3.2", k is not None and abs(k - 3.17) < 0.03, str(k))
    #  ISO tự động: ISO = BaseISO × AutoISO / 100 (ExifTool); AutoISO mã 32 = ×2 -> 200
    shot = list(SHOT_10D)
    shot[1] = 32
    iso = at.doc_the(crw(TAM / "D2.CRW", shot=shot)).get("iso")
    ktra("CRW: ISO tự động (AutoISO mã 32) = 200", iso == 200, str(iso))
    ktra("ev_anh_sang tính được từ CRW", at.ev_anh_sang(t) is not None, str(at.ev_anh_sang(t)))


def muc3():
    """3. CRW: ảnh nhúng + xoay + đo"""
    f = crw(TAM / "E.CRW", xoay=270)
    blob, _t = at.read_raw(f)
    sz = Image.open(io.BytesIO(blob)).size if blob else None
    ktra("read_raw: JpgFromRaw 1536×1024", sz == (1536, 1024), str(sz))
    goc_rr = at.read_raw

    def cam(*_a, **_k):
        raise AssertionError("anh_nho gọi read_raw cho CRW")
    at.read_raw = cam
    try:
        im = at.anh_nho(f, 320)
    except AssertionError as ex:
        im = None
        ktra("anh_nho: đọc JpgFromRaw thẳng (không lùi về read_raw)", False, str(ex))
    finally:
        at.read_raw = goc_rr
    if im is not None:
        ktra("anh_nho: ảnh dọc ĐỨNG", im.size[1] > im.size[0], str(im.size))
        #  Orientation 8: hàng 0 thành mép TRÁI -> góc trái-trên của cảm biến xuống trái-DƯỚI
        ktra("anh_nho: Orientation 8 -> góc đánh dấu ở trái-dưới", goc_mau(im) == "dt", goc_mau(im))
    tham = at.cau_hinh_do(dict(at.DEFAULTS, canh_p365=False))
    r = at.measure(f, *tham)
    ktra("measure: chạy, preview dọc, có EV100",
         r.get("ok") and r.get("preview_wh") and r["preview_wh"][1] > r["preview_wh"][0]
         and at.ev100(r) is not None, f"{r.get('preview_wh')} {at.ev100(r)} {r.get('loi') or ''}")


def muc4():
    """4. CRW / CR3 hỏng không treo / không sập"""
    import signal

    class Treo(Exception):
        pass

    def bao(*_):
        raise Treo()
    ca = {}
    f = crw(TAM / "F.CRW")
    d = f.read_bytes()
    ca["cắt cụt nửa file"] = d[: len(d) // 2]
    ca["cắt cụt 30 byte"] = d[:30]
    #  đống con trỏ lại ĐÚNG vùng của chính nó (bản ghi 0x300a cỡ / vị trí = cả đống gốc)
    tu_tro = struct.pack("<H", 1) + struct.pack("<HII", 0x300A, 16, 0) + struct.pack("<I", 0)
    ca["đống tự trỏ"] = b"II" + struct.pack("<I", 26) + b"HEAPCCDR" + b"\0" * 12 + tu_tro
    sau = dong([(0x080A, b"Canon\0X\0")])
    for _ in range(2000):
        sau = dong([(0x300A, sau)])
    ca["lồng 2000 tầng"] = b"II" + struct.pack("<I", 26) + b"HEAPCCDR" + b"\0" * 12 + sau
    rac = list(SHOT_10D)
    rac[1] = rac[2] = 32767
    rac[21] = rac[22] = -32768
    #  ShotInfo nằm TRƯỚC thông tin máy: số rác mà làm hỏng cả lượt đọc là mất luôn máy + hướng
    ca["ShotInfo số rác (tràn 2**x)"] = crw(TAM / "G.CRW", shot=rac, exif_truoc=True).read_bytes()
    ca["bảng trỏ ra ngoài"] = d[:-4] + struct.pack("<I", 0xFFFFFFF0)
    #  CR3 hỏng: mdia lồng mdia 3000 tầng trong trak (đệ quy không chặn = RecursionError)
    mdia = b""
    for _ in range(3000):
        mdia = struct.pack(">I", 8 + len(mdia)) + b"mdia" + mdia
    trak = struct.pack(">I", 8 + len(mdia)) + b"trak" + mdia
    ca["CR3 lồng mdia 3000 tầng"] = (struct.pack(">I", 24) + b"ftypcrx \0\0\0\x01crx isom"
                                     + struct.pack(">I", 8 + len(trak)) + b"moov" + trak)
    signal.signal(signal.SIGALRM, bao)
    for ten, b in ca.items():
        p = TAM / "hong.crw"
        p.write_bytes(b)
        ok, mo = True, ""
        for ham in (at.doc_the, at.read_raw, at.anh_nho):
            signal.alarm(10)
            try:
                ham(p)
            except (OSError, ValueError):
                pass
            except Treo:
                ok, mo = False, f"{ham.__name__} TREO"
            except Exception as ex:                          # noqa: BLE001
                ok, mo = False, f"{ham.__name__}: {type(ex).__name__} {ex}"
            finally:
                signal.alarm(0)
        ktra(f"File hỏng — {ten}", ok, mo)
    t = at.doc_the(TAM / "G.CRW")
    ktra("ShotInfo rác: bỏ ISO / tốc / khẩu rác, vẫn giữ máy + hướng",
         t.get("model") == "Canon EOS 10D" and t.get("orientation") == 8
         and t.get("iso") is None and t.get("exposure_time") is None, str(t))


def muc5():
    """5. Khung TIFF dưới mọi đuôi"""
    for duoi in (".NRW", ".SRF", ".SR2", ".NEF", ".ARW", ".CR2"):
        f = tiff_raw(TAM / f"H{duoi}", may=f"MAY{duoi}", huong=6)
        t = at.doc_the(f)
        im = at.anh_nho(f, 320)
        blob, _ = at.read_raw(f)
        sz = Image.open(io.BytesIO(blob)).size if blob else None
        ktra(f"{duoi}: máy, hướng 6, ISO, tốc, khẩu, ảnh nhúng, ảnh nhỏ đứng + đúng góc",
             t.get("model") == f"MAY{duoi}" and t.get("orientation") == 6 and t.get("iso") == 200
             and at._rat(t.get("exposure_time")) == 1 / 250 and sz == (1200, 800)          # noqa: SLF001
             and im is not None and im.size[1] > im.size[0] and goc_mau(im) == "tp",
             f"{t.get('model')} h={t.get('orientation')} iso={t.get('iso')} {sz} "
             f"{im.size if im else None} {goc_mau(im) if im else ''}")


def muc6():
    """6. Nikon: ISO trong MakerNote"""
    t = at.doc_the(tiff_raw(TAM / "I.NEF", iso=0, makernote=nikon_mn(400)))
    ktra("D70: EXIF không ISO -> lấy ISO 400 từ MakerNote", t.get("iso") == 400, str(t.get("iso")))
    ktra("D70: EV100 tính được", at.ev_anh_sang(t) is not None, str(at.ev_anh_sang(t)))
    t = at.doc_the(tiff_raw(TAM / "J.NEF", iso=200, makernote=nikon_mn(400)))
    ktra("Máy đời mới: EXIF ISO 200 giữ nguyên (MakerNote 400 không đè)", t.get("iso") == 200,
         str(t.get("iso")))
    t = at.doc_the(tiff_raw(TAM / "K.NEF", iso=0, makernote=nikon_mn(0)))
    ktra("MakerNote ISO 0 -> không đặt ISO", t.get("iso") is None, str(t.get("iso")))


def muc7():
    """7. thư mục RAW thật (tuỳ chọn)"""
    d = os.environ.get("AUTOTONE_RAW_MAU")
    if not d or not Path(d).is_dir():
        print("  BỎ QUA: đặt AUTOTONE_RAW_MAU=<thư mục RAW thật>")
        return
    pairs, _ = at.collect_pairs(Path(d), need_sidecar=False)
    for p, _ in pairs:
        t = at.doc_the(p)
        im = at.anh_nho(p, 320)
        ktra(f"{p.name}: máy / ISO / tốc / khẩu / ảnh nhỏ",
             bool(t.get("model")) and t.get("iso") is not None and t.get("exposure_time") is not None
             and t.get("fnumber") is not None and im is not None,
             f"{t.get('model')} iso={t.get('iso')} h={t.get('orientation')} {im.size if im else None}")


def main():
    #  giờ CRW là giờ MÁY (giây Unix không múi giờ) — chạy ở múi +7 để đọc nhầm giờ máy
    #  theo giờ địa phương thì lệch 7 tiếng
    os.environ["TZ"] = "Asia/Ho_Chi_Minh"
    if hasattr(__import__("time"), "tzset"):
        __import__("time").tzset()
    for m in (muc1, muc2, muc3, muc4, muc5, muc6, muc7):
        print(m.__doc__.splitlines()[0])
        try:
            m()
        except Exception as ex:                                  # noqa: BLE001
            import traceback
            traceback.print_exc()
            ktra(f"{m.__name__} không sập", False, repr(ex))
    shutil.rmtree(TAM, ignore_errors=True)
    print(f"\n{len(LOI)} LOI" if LOI else "\nTAT CA DAT")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
