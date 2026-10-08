#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
autotone.py — Cân bằng tone tự động cho ảnh RAW Sony (.ARW) qua sidecar .xmp

Luồng:
  1. Đọc JPEG preview nhúng trong .ARW (tự parse TIFF/IFD — không cần exiftool/rawpy)
  2. Đo log-average luminance (center-weighted), histogram, mức clipping sáng/tối
  3. Gom ảnh thành "scene" theo mốc thời gian chụp (mặc định cách nhau < 5 phút)
  4. Tính delta và ghi ngược vào các trường tone trong .xmp, giữ nguyên phần preset
  5. Trong Lightroom: Metadata > Read Metadata from File

CẢNH BÁO: "Read Metadata from File" GHI ĐÈ chỉnh sửa đang có trong catalog.
Chạy trước khi retouch tay, và backup catalog trước lần chạy đầu tiên.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import mmap
import os
import re
import shutil
import struct
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import duong_dan as dd

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

RAW_EXTS = {".arw", ".sr2", ".srf", ".nef", ".cr2", ".cr3", ".raf",
            ".rw2", ".orf", ".dng", ".pef"}

# --- histogram trên log2 của linear luminance ---
LOG_MIN, LOG_MAX, NBINS = -16.0, 4.0, 400
BW = (LOG_MAX - LOG_MIN) / NBINS

# Ngưỡng clipping quy về linear (sRGB 250/255 và 6/255)
CLIP_HI_LOG = -0.065
CLIP_LO_LOG = -9.10

EPS = 1e-9


# ======================================================================
# 1. Đọc TIFF / EXIF / preview JPEG nhúng trong RAW
# ======================================================================

_TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8, 13: 4}

T_COMPRESSION      = 0x0103
T_STRIP_OFFSETS    = 0x0111
T_STRIP_BYTECOUNTS = 0x0117
T_SUBIFDS          = 0x014A
T_JPEG_OFFSET      = 0x0201
T_JPEG_LENGTH      = 0x0202
T_EXIF_IFD         = 0x8769
T_MAKERNOTE        = 0x927C
#[[ Sony ghi diem lay net that vao MakerNote 0x2027 "FocusLocation":
#   4 so 16-bit = (rong, cao, x, y) theo he toa do anh GOC.
#
#   Day la diem may THUC SU lay net vao, chac chan hon moi cach suy doan tu
#   noi dung anh. Do thuc te: 50/50 anh Sony A7M4 deu co tag nay hop le.
#]]
T_SONY_FOCUS_LOC   = 0x2027
#[[ Nikon ghi vung lay net vao MakerNote 0x00B7 "AFInfo2" (khoi nhi phan).
#
#   MakerNote Nikon co dau "Nikon\0" + 4 byte, roi mot TIFF header RIENG tai
#   +10 (thu tu byte rieng, offset tinh tu header do) — khac Sony la IFD tran.
#
#   Ban 0300 / 0301 (dong Z, vd NIKON Z 6_2): tu byte 0x2a la 6 so 16-bit
#       rong anh AF, cao anh AF, tam X, tam Y, rong vung, cao vung
#   Doi chieu bang ExifTool tren 9 file NEF that cua bo 2609 (Z 6_2, ban 0301):
#   khop tung so. Ban khac (0100 dong D, 0400 Z8/Z9/Z6III) CHUA co file that de
#   doi chieu nen KHONG doc — tra ve khong co, lui ve cach doan cu.
#
#   Nikon Wide-area chon net o DAU DO trong vung, nen giu ca KICH THUOC vung
#   (af_vung), khong chi tam.
#]]
T_NIKON_AFINFO2    = 0x00B7
#[[ WB MAY DA DUNG KHI RENDER PREVIEW — them 2/10/2026 (hoc tu 2 ban quay).
#
#   Toan bo phan can mau doc mau da tren PREVIEW nhung trong RAW. Preview do
#   may render bang WB CUA MAY, khong phai WB cua preset Lightroom. Ma moi may
#   mot kieu: buoi TrainTool, Sony A7IV/A7V dat tay 5200-5600K, Nikon Z6II de
#   Auto (may tu do 4840-6740K). Che do catalog lai KHONG co AsShotTemperature
#   (0/1502 anh), nen tool khong biet preview da duoc can theo nhiet do nao.
#   Doc thang tu MakerNote:
#     Sony  0x0115 WhiteBalance (0 = Auto, 1 = dat nhiet do tay, ...)
#           0xb021 ColorTemperature (K) — co gia tri khi dat tay
#     Nikon 0x004F ColorTemperatureAuto (K may tu do) — IFD Nikon KHONG ma hoa
#           0x000C WB_RBLevels (he so R, B) — 4 so rational
#   Doi chieu ExifTool 12.76 tren 75 file that cua TrainTool: khop tung so.
#]]
T_SONY_WB_MODE     = 0x0115
T_SONY_COLOR_TEMP  = 0xB021
T_NIKON_WB_RB      = 0x000C
T_NIKON_CT_AUTO    = 0x004F
T_ORIENTATION      = 0x0112
T_DATETIME         = 0x0132
T_DATETIME_ORIG    = 0x9003
T_SUBSEC_ORIG      = 0x9291
T_MAKE             = 0x010F
T_MODEL            = 0x0110
T_ISO              = 0x8827
T_EXPTIME          = 0x829A
T_FNUMBER          = 0x829D
T_EXPBIAS          = 0x9204


def _entry_value(data, e, typ, cnt, valoff, size):
    if valoff + size > len(data):
        return None
    if typ == 2:
        return data[valoff:valoff + size].split(b"\x00")[0].decode("ascii", "ignore")
    if typ in (1, 6, 7):
        return list(data[valoff:valoff + size])
    fmt = {3: "H", 8: "h", 4: "I", 9: "i", 11: "f", 12: "d"}.get(typ)
    if fmt:
        return list(struct.unpack_from(e + str(cnt) + fmt, data, valoff))
    if typ in (5, 10):
        f = "II" if typ == 5 else "ii"
        vals = struct.unpack_from(e + f * cnt, data, valoff)
        return [(vals[i * 2], vals[i * 2 + 1]) for i in range(cnt)]
    return None


def _af_nikon(data, mvo: int, tags: dict) -> None:
    """Doc vung lay net tu MakerNote Nikon (xem T_NIKON_AFINFO2). Hong o dau
    thi im lang bo qua — thieu diem AF chi la lui ve cach doan cu."""
    try:
        goc = mvo + 10
        bo = bytes(data[goc:goc + 2])
        if bo not in (b"II", b"MM"):
            return
        e = "<" if bo == b"II" else ">"
        ifd = goc + struct.unpack_from(e + "I", data, goc + 4)[0]
        n = struct.unpack_from(e + "H", data, ifd)[0]
        if not 0 < n <= 512:
            return
        for i in range(n):
            q = ifd + 2 + i * 12
            tag, typ, cnt = struct.unpack_from(e + "HHI", data, q)
            if tag != T_NIKON_AFINFO2:
                continue
            if typ != 7 or cnt < 0x36:
                return
            o = goc + struct.unpack_from(e + "I", data, q + 8)[0]
            ban = bytes(data[o:o + 4])
            if ban not in (b"0300", b"0301"):
                tags["af_nikon_ban"] = ban.decode("ascii", "replace")
                return
            w, h, cx, cy, aw, ah = struct.unpack_from(e + "6H", data, o + 0x2A)
            if w > 0 and h > 0 and 0 < cx <= w and 0 < cy <= h:
                tags["af_point"] = (cx / w, cy / h)
                if aw > 0 and ah > 0:
                    tags["af_vung"] = (aw / w, ah / h)
            return
    except (struct.error, IndexError):
        return


def _wb_nikon(data, mvo: int, tags: dict) -> None:
    """Doc WB may tu MakerNote Nikon (xem T_NIKON_CT_AUTO). Hong thi bo qua —
    thieu so nay chi la quay ve cach can mau cu."""
    try:
        goc = mvo + 10
        bo = bytes(data[goc:goc + 2])
        if bo not in (b"II", b"MM"):
            return
        e = "<" if bo == b"II" else ">"
        ifd = goc + struct.unpack_from(e + "I", data, goc + 4)[0]
        n = struct.unpack_from(e + "H", data, ifd)[0]
        if not 0 < n <= 512:
            return
        for i in range(n):
            q = ifd + 2 + i * 12
            tag, typ, cnt = struct.unpack_from(e + "HHI", data, q)
            if tag == T_NIKON_CT_AUTO and typ == 3 and cnt >= 1:
                k = struct.unpack_from(e + "H", data, q + 8)[0]
                if 1500 <= k <= 15000:
                    tags["wb_may_K"] = int(k)
                    tags["wb_may_che_do"] = "auto"
            elif tag == T_NIKON_WB_RB and typ == 5 and cnt >= 2:
                o = goc + struct.unpack_from(e + "I", data, q + 8)[0]
                rn, rd, bn, bd = struct.unpack_from(e + "4I", data, o)
                if rd and bd and rn and bn:
                    tags["wb_may_rb"] = math.log2((rn / rd) / (bn / bd))
    except (struct.error, IndexError, ValueError):
        return


def _wb_sony(data, mvo: int, e: str, tags: dict) -> None:
    """Doc che do WB va nhiet do dat tay tu MakerNote Sony (IFD tran tai mvo)."""
    try:
        mn = struct.unpack_from(e + "H", data, mvo)[0]
        if not 0 < mn <= 512:
            return
        mode = k = None
        for i in range(mn):
            q = mvo + 2 + i * 12
            if q + 12 > len(data):
                break
            mtag, mtyp, mcnt = struct.unpack_from(e + "HHI", data, q)
            if mtag == T_SONY_WB_MODE and mtyp in (3, 4) and mcnt == 1:
                mode = struct.unpack_from(e + ("H" if mtyp == 3 else "I"), data, q + 8)[0]
            elif mtag == T_SONY_COLOR_TEMP and mtyp in (3, 4) and mcnt == 1:
                k = struct.unpack_from(e + ("H" if mtyp == 3 else "I"), data, q + 8)[0]
        if mode is None:
            return
        #[[ Chi tin nhiet do khi may o che do DAT NHIET DO (1). Che do Auto
        #   (0) thi 0xb021 la so rac/0; cac che do dat san (Daylight, Tungsten...)
        #   co he so rieng ma khong ghi K o day — de None, quay ve cach cu.
        #]]
        tags["wb_may_che_do"] = "auto" if mode == 0 else ("tay" if mode == 1 else f"san{mode}")
        if mode == 1 and k and 1500 <= k <= 15000:
            tags["wb_may_K"] = int(k)
    except (struct.error, IndexError):
        return


def _parse_ifd(data, offset, e, seen, jpegs, tags, depth=0):
    """Duyệt một IFD, thu thập ứng viên JPEG và các tag EXIF cần quan tâm."""
    if depth > 5 or offset <= 0 or offset + 2 > len(data) or offset in seen:
        return
    seen.add(offset)
    try:
        n = struct.unpack_from(e + "H", data, offset)[0]
    except struct.error:
        return
    if n == 0 or n > 1024:
        return

    ent = {}
    base = offset + 2
    for i in range(n):
        p = base + i * 12
        if p + 12 > len(data):
            break
        try:
            tag, typ, cnt = struct.unpack_from(e + "HHI", data, p)
        except struct.error:
            break
        size = _TYPE_SIZE.get(typ, 0) * cnt
        if size == 0 or cnt > 1_000_000:
            continue
        voff = p + 8 if size <= 4 else struct.unpack_from(e + "I", data, p + 8)[0]
        ent[tag] = (typ, cnt, voff, size)

    def get(tag):
        if tag not in ent:
            return None
        return _entry_value(data, e, *ent[tag])

    for tag, key in ((T_DATETIME, "datetime"), (T_DATETIME_ORIG, "datetime_original"),
                     (T_SUBSEC_ORIG, "subsec"), (T_MAKE, "make"), (T_MODEL, "model")):
        if tag in ent and key not in tags:
            v = get(tag)
            if v:
                tags[key] = v
    for tag, key in ((T_ISO, "iso"), (T_EXPTIME, "exposure_time"),
                     (T_FNUMBER, "fnumber"), (T_EXPBIAS, "exposure_bias"),
                     (T_ORIENTATION, "orientation")):
        if tag in ent and key not in tags:
            v = get(tag)
            if v:
                tags[key] = v[0]

    if T_JPEG_OFFSET in ent and T_JPEG_LENGTH in ent:
        o, l = get(T_JPEG_OFFSET), get(T_JPEG_LENGTH)
        if o and l:
            jpegs.append((int(o[0]), int(l[0])))

    comp = get(T_COMPRESSION)
    if comp and comp[0] in (6, 7) and T_STRIP_OFFSETS in ent and T_STRIP_BYTECOUNTS in ent:
        o, l = get(T_STRIP_OFFSETS), get(T_STRIP_BYTECOUNTS)
        if o and l and len(o) == 1:
            jpegs.append((int(o[0]), int(l[0])))

    if T_SUBIFDS in ent:
        for so in (get(T_SUBIFDS) or []):
            _parse_ifd(data, int(so), e, seen, jpegs, tags, depth + 1)
    if T_EXIF_IFD in ent:
        v = get(T_EXIF_IFD)
        if v:
            _parse_ifd(data, int(v[0]), e, seen, jpegs, tags, depth + 1)

    #[[ MakerNote Sony: IFD binh thuong nam ngay tai offset, khong header dem.
    #   Chi lay dung tag diem lay net, khong duyet sau — MakerNote toi 38KB,
    #   duyet het vua cham vua de dinh du lieu rac.
    #]]
    #[[ WB may — doc TRUOC va DOC LAP voi diem AF: khoi AF ben duoi chi chay khi
    #   chua co af_point, ma WB thi can o moi anh. Xem T_SONY_WB_MODE. ]]
    if T_MAKERNOTE in ent and "wb_may_che_do" not in tags:
        _, _, mvw, _ = ent[T_MAKERNOTE]
        if data[mvw:mvw + 6] == b"Nikon\x00":
            _wb_nikon(data, mvw, tags)
        elif "sony" in str(tags.get("make", "")).lower():
            _wb_sony(data, mvw, e, tags)
    if T_MAKERNOTE in ent and "af_point" not in tags:
        _, _, mvo0, _ = ent[T_MAKERNOTE]
        if data[mvo0:mvo0 + 6] == b"Nikon\x00":
            _af_nikon(data, mvo0, tags)
    if T_MAKERNOTE in ent and "af_point" not in tags:
        _, _, mvo, _ = ent[T_MAKERNOTE]
        try:
            mn = struct.unpack_from(e + "H", data, mvo)[0]
        except struct.error:
            mn = 0
        if 0 < mn <= 512:
            for i in range(mn):
                q = mvo + 2 + i * 12
                if q + 12 > len(data):
                    break
                try:
                    mtag, mtyp, mcnt = struct.unpack_from(e + "HHI", data, q)
                except struct.error:
                    break
                if mtag == T_SONY_FOCUS_LOC and mtyp == 3 and mcnt == 4:
                    try:
                        mo = struct.unpack_from(e + "I", data, q + 8)[0]
                        w, h, fx, fy = struct.unpack_from(e + "4H", data, mo)
                    except struct.error:
                        break
                    # (0,0) = may khong khoa net vao dau ca -> bo qua
                    if w > 0 and h > 0 and 0 < fx <= w and 0 < fy <= h:
                        tags["af_point"] = (fx / w, fy / h)
                    break

    nxt_p = base + n * 12
    if nxt_p + 4 <= len(data):
        nxt = struct.unpack_from(e + "I", data, nxt_p)[0]
        if nxt:
            _parse_ifd(data, nxt, e, seen, jpegs, tags, depth)


def _scan_jpegs(data, min_len=64_000):
    """Quét thô toàn file tìm khối JPEG — fallback khi parse IFD không ra gì."""
    out, i, n = [], 0, len(data)
    while i < n:
        i = data.find(b"\xff\xd8\xff", i)
        if i < 0:
            break
        j = data.find(b"\xff\xd9", i + 3)
        if j < 0:
            break
        ln = j + 2 - i
        if ln >= min_len:
            out.append((i, ln))
        i = j + 2
    return out


# Sony để preview full-size trong MakerNote — script không parse MakerNote, nên
# quét thô phần đầu file để tìm nó. Preview luôn nằm trước khối dữ liệu RAW.
SCAN_HEAD_BYTES = 16 * 1024 * 1024
MIN_GOOD_PX = 640


def _pick_preview(mm, cand):
    """Chọn ứng viên lớn nhất mở được. Trả về (bytes, cạnh dài) hoặc (None, 0)."""
    best, best_px = None, 0
    for o, l in sorted(set(cand), key=lambda t: -t[1])[:6]:
        if not (0 < l <= len(mm) - o) or mm[o:o + 3] != b"\xff\xd8\xff":
            continue
        blob = bytes(mm[o:o + l])
        try:
            im = Image.open(io.BytesIO(blob))
            px = max(im.size)
        except Exception:
            continue
        if px > best_px:
            best, best_px = blob, px
        if best_px >= MIN_GOOD_PX:
            break
    return best, best_px


def _tiff_trong_jpeg(mm):
    """Khối TIFF nằm trong đoạn APP1 của một file JPEG. None nếu không có.

    #[[ VI SAO CAN HAM NAY
    #
    #   read_raw() chi doc EXIF khi file mo dau bang II/MM — tuc dinh dang TIFF,
    #   ma RAW nao cung vay. File JPEG mo dau bang FFD8, nen ca nhanh doc EXIF bi
    #   bo qua: anh van doc duoc (co doan lui o cuoi read_raw), nhung tags rong.
    #
    #   Hau qua khong bao loi mot chu nao: measure() tra ve iso=None cho MOI anh
    #   JPEG. Ma ngoai_troi() coi khong doc duoc ISO la trong nha. Nen
    #   hoc_mau_da.py chay tren anh da xuat se thay 0 anh ngoai troi du thu muc
    #   toan anh ngoai troi, va bao "chua du 10 anh de rut mau dich rieng" —
    #   mot cau khien nguoi ta di tim them anh, trong khi anh khong thieu.
    #
    #   Do that tren mot anh da xuat: PIL doc duoc ISOSpeedRatings = 1000, con
    #   measure() tra ve None.
    #
    #   JPEG xep theo doan: FFD8, roi cac marker FFxx kem 2 byte do dai. Doan
    #   APP1 (FFE1) bat dau bang "Exif\0\0" roi den khoi TIFF. Offset ben trong
    #   khoi do tinh TU DAU KHOI, nen phai cat rieng khoi ra roi moi giao cho
    #   _parse_ifd — giao ca file thi moi offset deu lech.
    #]]
    """
    if mm[:2] != b"\xff\xd8":
        return None
    i, n = 2, len(mm)
    while i + 4 <= n:
        if mm[i] != 0xFF:
            break
        m = mm[i + 1]
        if m == 0xD8 or m == 0x01 or 0xD0 <= m <= 0xD7:      # khong co phan do dai
            i += 2
            continue
        if m == 0xDA or m == 0xD9:                           # bat dau anh / het file
            break
        try:
            dai = struct.unpack_from(">H", mm, i + 2)[0]
        except struct.error:
            break
        if dai < 2:
            break
        if m == 0xE1 and mm[i + 4:i + 10] == b"Exif\x00\x00":
            return bytes(mm[i + 10: i + 2 + dai])
        i += 2 + dai
    return None


def read_raw(path: Path):
    """Trả về (bytes preview JPEG lớn nhất, dict tag EXIF). Đọc file 1 lần bằng mmap."""
    tags: dict = {}
    with open(path, "rb") as fh:
        with mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            jpegs: list = []
            if mm[:2] in (b"II", b"MM"):
                e = "<" if mm[:2] == b"II" else ">"
                try:
                    _parse_ifd(mm, struct.unpack_from(e + "I", mm, 4)[0], e, set(), jpegs, tags)
                except Exception:
                    pass
            else:
                #[[ Anh DA XUAT (JPEG): EXIF nam trong doan APP1, khong nam o dau
                #   file. Xem _tiff_trong_jpeg(). Danh sach preview de rong: voi
                #   file JPEG thi CHINH NO la anh, khong lay thumbnail nhung.
                #]]
                kh = _tiff_trong_jpeg(mm)
                if kh and kh[:2] in (b"II", b"MM"):
                    e = "<" if kh[:2] == b"II" else ">"
                    try:
                        _parse_ifd(kh, struct.unpack_from(e + "I", kh, 4)[0],
                                   e, set(), [], tags)
                    except Exception:
                        pass

            cand = [(o, l) for (o, l) in jpegs if l > 2000]
            cand += _scan_jpegs(mm[:SCAN_HEAD_BYTES], min_len=32_000)
            blob, px = _pick_preview(mm, cand)

            # chỉ khi vẫn chưa có preview đủ lớn mới chịu quét hết file
            if px < MIN_GOOD_PX and len(mm) > SCAN_HEAD_BYTES:
                blob2, px2 = _pick_preview(mm, _scan_jpegs(mm, min_len=32_000))
                if px2 > px:
                    blob = blob2

            #[[ CHOT CUOI: FILE TU NO DA LA MOT TAM ANH.
            #
            #   Ham nay sinh ra de moi preview JPEG NHUNG TRONG file RAW. Nhung
            #   no cung duoc goi tren anh DA XUAT — .tif, .png, .jpg — va voi
            #   .tif/.png thi khong co "preview nhung" nao ca: TIFF con bat dau
            #   bang II/MM y het RAW nen nhanh tren tuong la RAW roi khong tim
            #   thay gi, tra ve None, va measure() bao "khong tim thay preview
            #   JPEG trong RAW" — mot cau vo nghia voi mot file PNG.
            #
            #   Hong that 5/9: hoc_mau_da.py chay tren 300 anh da xuat, ra
            #   "thay mat o 0/300 anh". Khong phai khong co mat — la khong doc
            #   duoc anh nao.
            #
            #   Voi file ma chinh no la anh, CHINH NO la preview. Chi thu buoc
            #   nay khi moi cach tren deu truot, nen duong di cua RAW khong doi
            #   mot ly nao.
            #]]
            if blob is None:
                try:
                    thu = bytes(mm)
                    with Image.open(io.BytesIO(thu)) as im:
                        im.verify()
                    blob = thu
                except Exception:                            # noqa: BLE001
                    pass
            return blob, tags


_DUOI_ANH_THUONG = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def anh_nho(path, canh: int = 320):
    """Ảnh nhỏ (PIL RGB, cạnh dài ≤ canh) cho LƯỚI ẢNH của giao diện; None nếu
    không đọc được.

    VÌ SAO KHÔNG GỌI THẲNG read_raw()
        read_raw() là đường của PHÉP ĐO: nó luôn chép 16 MB đầu file để quét
        tìm preview to nhất (Sony giấu preview đủ cỡ trong MakerNote). Lưới ảnh
        chỉ cần một ảnh vài trăm px — đọc 16 MB cho mỗi tấm thì 1 000 tấm là
        16 GB đọc đĩa. Ở đây thử trước các JPEG mà bảng IFD CHỈ TỚI (đọc vài
        KB đầu file + đúng đoạn JPEG đó), lấy cái NHỎ NHẤT mà vẫn đủ cạnh;
        chỉ khi không có cái nào đủ mới lùi về read_raw().

    Không dính gì tới số đo: ảnh này chỉ để NHÌN.

    #[[ ANH THUONG (JPEG/PNG/TIFF da Export — luoi anh cua khau Retouch) mo
    #   THANG bang PIL, xoay theo EXIF. Cho chung di duong read_raw() la quet
    #   16 MB tim "preview nhung" trong mot file von DA la anh; TIFF 16 bit
    #   con roi vao nhanh bang IFD va ra "khong doc duoc". ]]
    """
    p = Path(path)
    if p.suffix.lower() in _DUOI_ANH_THUONG:
        try:
            from PIL import ImageOps
            with Image.open(p) as goc:
                goc.draft("RGB", (canh, canh))
                im = ImageOps.exif_transpose(goc)
                im = im.convert("RGB")
            im.thumbnail((canh, canh), Image.BILINEAR)
            return im
        except Exception:                                    # noqa: BLE001
            return None
    tags: dict = {}
    blob = None
    try:
        with open(p, "rb") as fh:
            with mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                if mm[:2] in (b"II", b"MM"):
                    e = "<" if mm[:2] == b"II" else ">"
                    jpegs: list = []
                    try:
                        _parse_ifd(mm, struct.unpack_from(e + "I", mm, 4)[0], e,
                                   set(), jpegs, tags)
                    except Exception:                        # noqa: BLE001
                        pass
                    du_lon = []
                    for o, ln in sorted(set(jpegs), key=lambda t: t[1]):
                        if ln < 2000 or not (0 < ln <= len(mm) - o) \
                                or mm[o:o + 3] != b"\xff\xd8\xff":
                            continue
                        b = bytes(mm[o:o + ln])
                        try:
                            with Image.open(io.BytesIO(b)) as thu:
                                px = max(thu.size)
                        except Exception:                    # noqa: BLE001
                            continue
                        if px >= canh:
                            du_lon.append(b)
                            break
                    if du_lon:
                        blob = du_lon[0]
    except (OSError, ValueError):
        return None
    for lan in range(2):
        if blob is None:
            try:
                blob, tags2 = read_raw(p)
                tags = tags2 or tags
            except (OSError, ValueError):
                return None
            if blob is None:
                return None
        try:
            im = Image.open(io.BytesIO(blob))
            im.draft("RGB", (canh, canh))
            im = im.convert("RGB")
            im = apply_orientation(im, tags.get("orientation"))
            im.thumbnail((canh, canh), Image.BILINEAR)
            return im
        except Exception:                                    # noqa: BLE001
            #[[ JPEG nhung khong giai ma duoc (vd. JPEG khong mat du lieu
            #   cua DNG): lan sau lui ve read_raw(). ]]
            if lan == 0:
                blob = None
                continue
            return None
    return None


# EXIF Orientation -> phép biến hình của Pillow. Preview nhúng trong RAW được lưu
# nguyên chiều cảm biến, ảnh dọc sẽ nằm ngang nếu không xoay. Bộ nhận diện mặt chỉ
# ăn mặt thẳng đứng nên bỏ qua bước này là hỏng hẳn với ảnh dọc.
_ORIENT_OPS = {
    2: [Image.FLIP_LEFT_RIGHT],
    3: [Image.ROTATE_180],
    4: [Image.FLIP_TOP_BOTTOM],
    5: [Image.FLIP_LEFT_RIGHT, Image.ROTATE_270],
    6: [Image.ROTATE_270],
    7: [Image.FLIP_LEFT_RIGHT, Image.ROTATE_90],
    8: [Image.ROTATE_90],
}


def _rat(v) -> float | None:
    """EXIF RATIONAL (tử, mẫu) -> float. None nếu không đọc được."""
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, (tuple, list)) and len(v) == 2 and v[1]:
        return float(v[0]) / float(v[1])
    return None


def ev_anh_sang(tags: dict) -> float | None:
    """ĐỘ SÁNG CỦA THỨ ÁNH SÁNG ĐANG CÓ, tính từ tam giác phơi sáng.

        EV = log2(N² / t) - log2(ISO / 100)

    Đây KHÔNG phải độ sáng của bức ảnh (cái đó là metered_ev, đo trên pixel).
    Đây là "lúc bấm máy, chỗ đó sáng cỡ nào" — vì máy phải bù trừ để ra một tấm
    ảnh phơi đúng, nên bộ ba khẩu/tốc/ISO chính là số đo của ánh sáng môi trường.

    VÌ SAO SỐ NÀY ĐÁNG GIÁ
        Trong nhà một buổi sự kiện thường rơi vào EV 6-9. Ngoài trời ban ngày là
        EV 13-16. Khoảng cách 5-7 stop, tức GẤP 30 ĐẾN 100 LẦN lượng sáng — rộng
        hơn hẳn mọi dao động trong cùng một loại. Đo thật trên máy ILCE-7M4 buổi
        1308: ISO 800, 1/200, f/2.8 -> EV 7.6, đúng khoảng trong nhà.

        Nó cũng không phụ thuộc pixel: không bị màn LED, áo trắng, hay phông tối
        đánh lừa như cách nhìn vào ảnh.

    CẨN THẬN: số này nói về ÁNH SÁNG, không nói về "ngoài trời". Trong nhà cạnh
    cửa sổ lớn giữa trưa cũng lên EV cao; ngoài trời lúc chạng vạng cũng xuống
    thấp. Nên nó là MỘT dấu hiệu, phải đo xem nó tách được tới đâu trước khi
    đem ra quyết định — xem do_trong_ngoai.py.
    """
    t = _rat(tags.get("exposure_time"))
    n = _rat(tags.get("fnumber"))
    iso = tags.get("iso")
    if not t or not n or not iso or t <= 0 or n <= 0:
        return None
    try:
        iso = float(iso[0] if isinstance(iso, (tuple, list)) else iso)
    except (TypeError, ValueError):
        return None
    if iso <= 0:
        return None
    return float(np.log2(n * n / t) - np.log2(iso / 100.0))


#[[ Mot diem (u, v) tinh theo ti le 0..1 di qua dung phep xoay/lat PIL.
#   Rut ra tu chinh cach PIL.Image.transpose doi toa do pixel, va bai kiem
#   test_af_xoay.py do bang cach cham mot pixel roi xoay anh that.
#]]
_DIEM_OPS = {
    Image.FLIP_LEFT_RIGHT: lambda u, v: (1.0 - u, v),
    Image.FLIP_TOP_BOTTOM: lambda u, v: (u, 1.0 - v),
    Image.ROTATE_90:       lambda u, v: (v, 1.0 - u),     # nguoc chieu kim dong ho
    Image.ROTATE_180:      lambda u, v: (1.0 - u, 1.0 - v),
    Image.ROTATE_270:      lambda u, v: (1.0 - v, u),     # thuan chieu kim dong ho
}


def af_theo_huong(pt, orientation):
    """Diem lay net (ti le 0..1, theo cam bien) -> toa do tren anh DA XOAY.

    VI SAO (29/9, bo 2609): Sony ghi FocusLocation theo he toa do CAM BIEN —
    luc nao cung la khung ngang. Anh chup doc thi preview duoc xoay bang
    apply_orientation(), nhung diem AF truoc day KHONG xoay theo. Diem AF roi
    vao mot cho khac han tren anh, trung mat ai thi nguoi do thanh "chu the
    theo AF" va MOI mat khac bi bo — dung cai nguoi dung thay: tool do mat
    nguoi dung ngoai le trong khi may lay net vao co dau chu re.
    """
    if pt is None:
        return None
    try:
        ops = _ORIENT_OPS.get(int(orientation or 1), [])
    except (TypeError, ValueError):
        return pt
    u, v = float(pt[0]), float(pt[1])
    for op in ops:
        u, v = _DIEM_OPS[op](u, v)
    return (u, v)


def mat_gan_af(boxes, ax: float, ay: float, nguong: float):
    """O mat gan diem AF nhat -> (chi so, khoang cach), hoac (None, None).

    Khoang cach = tu diem AF toi MEP o (0 neu nam trong), chia cho canh dai cua
    chinh o do. Xa hon `nguong` thi coi nhu khong co mat nao gan. Xem chu thich
    o af_gan_mat trong measure().
    """
    if nguong <= 0:
        return None, None
    i_min, d_min = None, None
    for i, b in enumerate(boxes):
        bx, by, bw, bh = (float(v) for v in b[:4])
        dx = max(bx - ax, 0.0, ax - (bx + bw))
        dy = max(by - ay, 0.0, ay - (by + bh))
        d = float(np.hypot(dx, dy)) / max(bw, bh, 1.0)
        if d_min is None or d < d_min:
            i_min, d_min = i, d
    if i_min is None or d_min > nguong:
        return None, None
    return i_min, d_min


def apply_orientation(im: Image.Image, orientation) -> Image.Image:
    try:
        ops = _ORIENT_OPS.get(int(orientation or 1), [])
    except (TypeError, ValueError):
        return im
    for op in ops:
        im = im.transpose(op)
    return im


def parse_dt(tags, fallback: Path) -> datetime:
    s = tags.get("datetime_original") or tags.get("datetime")
    if s:
        s = str(s).strip()
        for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(s[:19], fmt)
                sub = str(tags.get("subsec", "")).strip()
                if sub.isdigit():
                    dt += timedelta(seconds=float("0." + sub))
                return dt
            except ValueError:
                continue
    return datetime.fromtimestamp(fallback.stat().st_mtime)


# ======================================================================
# 2. Đo thống kê ảnh
# ======================================================================

def _lin_to_srgb(v: float) -> float:
    """Linear -> sRGB (0..1). Nghich dao cua srgb_to_linear cho MOT so."""
    v = max(0.0, min(1.0, float(v)))
    return v * 12.92 if v <= 0.0031308 else 1.055 * (v ** (1 / 2.4)) - 0.055


def _srgb_to_lin_1(v: float) -> float:
    """sRGB -> linear cho MOT so. Cung cong thuc srgb_to_linear() dung cho
    mang, tach ra de phanh chong chay da khoi phai dung numpy cho mot gia tri."""
    v = max(0.0, min(1.0, float(v)))
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def srgb_to_linear(a: np.ndarray) -> np.ndarray:
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


# ---------------------------------------------------------------- nhận diện mặt

FACE_MODEL = dd.tai_nguyen("models", "face_detection_yunet_2023mar.onnx")
_DETECTOR = None          # nạp một lần cho mỗi tiến trình


# Dai mau da nguoi (HSV). Rong tay de con nhan duoc da ram, da duoi den vang.
SKIN_HUE_HI = 50.0        # cam-vang
SKIN_HUE_LO = 345.0       # do-hong (vong qua 360)
SKIN_SAT_LO = 0.10
SKIN_SAT_HI = 0.72

#[[ Loai pixel TOI HON HAN phan con lai cua vung da.
#
#   skin_mask lọc theo hue/sat nên TÓC NÂU dưới đèn vàng lọt qua sạch: đúng dải
#   cam-đỏ, độ bão hoà vừa phải. Mặt quay nghiêng thì ô đo (giữa 55% khung mặt)
#   trượt sang tóc, và vì measure() lấy TRUNG BÌNH CỦA LOG — log kéo rất mạnh về
#   phía tối — chỉ cần một mảng tóc là cả phép đo sập.
#
#   Đo thật trên DSC01078: 35% pixel "da" tối bất thường (các tấm cùng loạt chỉ
#   8–10%), phép đo tụt 0.46 EV so với chính ô đo đó. Tool tưởng mặt tối nên
#   chỉnh nhẹ đi, ảnh ra dư sáng.
#
#   Mốc là 0.35 lần phân vị 90 CỦA CHÍNH VÙNG DA, nên nó co giãn theo từng ảnh,
#   không phải ngưỡng tuyệt đối. Đã thử 0.35 / 0.45 / 0.55: cả ba đều sửa được
#   01078, chọn 0.35 vì đụng vào ảnh lành ít nhất.
#
#   Kiểm trên 31 ảnh rải khắp buổi: dịch chuyển trung vị 0.047 EV, 85% dưới
#   0.104, chỉ 2 ảnh vượt 0.20 — và cả hai đều là ảnh ĐANG bị lỗi.
#   Đặt 0 để tắt.
#]]
SKIN_DARK_REL = 0.35

def skin_mask(px_srgb) -> "np.ndarray":
    """Lọc pixel THẬT SỰ là da trong ô mặt.

    Ô mặt là hình chữ nhật nên luôn dính kính, tóc, cổ áo, hậu cảnh. Đo thật
    trên ảnh sự kiện: ô mặt của người mặc vest xanh có tới 25% pixel là màu áo
    (hue ~238°), kéo cả phép đo sáng lẫn màu da đi rất xa.

    Lọc theo hue/sat thay vì theo độ sáng: da người luôn nằm ở dải cam-đỏ
    (hue <= 50° hoặc >= 345°) với độ bão hoà vừa phải, còn vest xanh, tóc đen,
    áo trắng thì rơi ra ngoài.

    px_srgb: mảng (N, 3) sRGB 0..1. Trả về mảng bool (N,).
    """
    mx = px_srgb.max(axis=1)
    mn = px_srgb.min(axis=1)
    d = mx - mn + EPS
    r, g, b = px_srgb[:, 0], px_srgb[:, 1], px_srgb[:, 2]

    hue = np.zeros(len(px_srgb), dtype=np.float32)
    m = mx == r
    hue[m] = ((g[m] - b[m]) / d[m]) % 6
    m = mx == g
    hue[m] = (b[m] - r[m]) / d[m] + 2
    m = mx == b
    hue[m] = (r[m] - g[m]) / d[m] + 4
    hue *= 60.0

    sat = d / (mx + EPS)
    return (((hue <= SKIN_HUE_HI) | (hue >= SKIN_HUE_LO))
            & (sat > SKIN_SAT_LO) & (sat < SKIN_SAT_HI)
            & (mx > 0.08) & (mx < 0.99))


def face_detector():
    """Trả về bộ nhận diện YuNet, hoặc None nếu thiếu OpenCV / thiếu model."""
    global _DETECTOR
    if _DETECTOR is not None:
        return _DETECTOR if _DETECTOR is not False else None
    try:
        import cv2
        if not FACE_MODEL.is_file():
            _DETECTOR = False
            return None
        _DETECTOR = cv2.FaceDetectorYN.create(str(FACE_MODEL), "", (320, 320),
                                              0.5, 0.3, 5000)
    except Exception:
        _DETECTOR = False
        return None
    return _DETECTOR


FOCUS_TILE = 32


def focus_energy(im: Image.Image, tile: int = FOCUS_TILE):
    """Bản đồ 'độ nét cục bộ' theo lưới ô vuông.

    Lấy năng lượng cạnh rồi CHIA CHO ĐỘ SÁNG cục bộ. Bước chia này là mấu chốt:
    không có nó thì màn LED đầy chữ tương phản cao sẽ luôn thắng, và máy sẽ tưởng
    cái màn hình mới là chỗ bắt nét. Chia rồi thì nó thành thước đo tương phản
    tương đối, vùng bokeh mờ tụt hẳn xuống còn chủ thể nổi lên.

    Trả về (mảng năng lượng theo ô, cạnh ô tính bằng pixel).
    """
    g = np.asarray(im.convert("L"), dtype=np.float32) / 255.0
    if min(g.shape) < tile * 2:
        return None, tile
    gx = np.abs(np.diff(g, axis=1))[:-1, :]
    gy = np.abs(np.diff(g, axis=0))[:, :-1]
    e = gx + gy
    lum = g[:-1, :-1]
    h, w = e.shape
    th, tw = h // tile, w // tile
    if th < 2 or tw < 2:
        return None, tile
    e = e[:th * tile, :tw * tile].reshape(th, tile, tw, tile).mean(axis=(1, 3))
    l = lum[:th * tile, :tw * tile].reshape(th, tile, tw, tile).mean(axis=(1, 3))
    return e / (l + 0.08), tile


def detect_faces(im: Image.Image, score: float = 0.5) -> list:
    """Nhận diện mặt trên ảnh ĐÃ XOAY ĐÚNG CHIỀU.

    Ảnh dọc mà chưa xoay theo EXIF thì mặt nằm ngang, YuNet gần như không thấy —
    nên bước apply_orientation() ở trên là bắt buộc, không phải cho đẹp.

    Trả về list (x, y, w, h, score) theo toạ độ của chính `im`.
    """
    det = face_detector()
    if det is None:
        return []
    try:
        import cv2  # noqa: F401  (chỉ để chắc chắn có)
        a = np.asarray(im.convert("RGB"), dtype=np.uint8)[:, :, ::-1].copy()
        h, w = a.shape[:2]
        det.setInputSize((w, h))
        _, faces = det.detect(a)
    except Exception:
        return []
    if faces is None:
        return []
    out = []
    for f in faces:
        x, y, fw, fh = (float(v) for v in f[:4])
        s = float(f[-1])
        if s >= score and fw > 4 and fh > 4:
            #[[ YuNet tra ve 15 so: 4 bbox + 5 landmark (x,y) + score.
            #   Landmark 0,1 la MAT TRAI, MAT PHAI — dung de do nham mat.
            #   Truoc day code chi lay f[:4] va f[-1], bo phi phan landmark.
            #]]
            eyes = None
            if len(f) >= 15:
                eyes = ((float(f[4]), float(f[5])), (float(f[6]), float(f[7])))
            out.append((x, y, fw, fh, s, eyes))
    return out


def _eye_openness(Y, eyes, face_w: float) -> float | None:
    """Độ MỞ của mắt, 0 = nhắm tịt, càng lớn càng mở to.

    Cắt một ô quanh mỗi mắt rồi lấy độ lệch chuẩn theo chiều DỌC chia cho chiều
    NGANG. Mắt mở có lòng đen trên nền lòng trắng nên biến thiên dọc lớn; mắt
    nhắm chỉ còn một vệt mí ngang nên gần như phẳng theo dọc.

    Chia cho biến thiên ngang để khỏi phụ thuộc độ tương phản chung của ảnh —
    ảnh tối và ảnh sáng cho ra thang giống nhau.

    CẢNH BÁO — PHÉP ĐO NÀY CHƯA ĐƯỢC KIỂM CHỨNG, VÀ SỐ LIỆU ĐANG CHỐNG LẠI NÓ.
        Đối chiếu buổi 1308 (1464 ảnh, 1078 giữ / 386 loại): trung vị của nhóm
        BỊ LOẠI lại CAO hơn nhóm được giữ (1.05 so với 0.90) — ngược chiều mong
        đợi. Ở mọi ngưỡng thử, số ảnh tốt bị loại oan nhiều hơn số ảnh nhắm mắt
        bắt được (tỉ lệ tốt nhất 0.37x). Xem thêm ô mắt cắt ra trong eye_sheet:
        có ô mắt nhắm rõ chỉ được 0.82 trong khi mắt mở được 1.6–2.1.

        Vì vậy: KHÔNG dùng hàm này làm ngưỡng tuyệt đối để loại ảnh (cấu hình
        "blink" mặc định tắt và từ chối chạy khi chưa có ngưỡng hiệu chuẩn).
        Nó chỉ còn dùng để XẾP HẠNG TƯƠNG ĐỐI giữa các ảnh trong cùng một loạt
        (pick_burst) — cùng người, cùng ánh sáng, cùng khoảng cách nên sai số
        hệ thống triệt tiêu bớt. Ngay cả chỗ đó cũng chưa có nhãn thật để xác
        nhận, nên trọng số của nó để riêng thành burst_eye_weight, hạ được.
    """
    if not eyes:
        return None
    h, w = Y.shape
    r = max(2, int(face_w * 0.10))
    vals = []
    for ex, ey in eyes:
        x0, x1 = int(max(0, ex - r)), int(min(w, ex + r))
        y0, y1 = int(max(0, ey - r)), int(min(h, ey + r))
        if x1 - x0 < 3 or y1 - y0 < 3:
            continue
        patch = Y[y0:y1, x0:x1]
        v = float(patch.std(axis=0).mean())     # biến thiên dọc
        hh = float(patch.std(axis=1).mean())    # biến thiên ngang
        vals.append(v / (hh + EPS))
    return float(np.mean(vals)) if vals else None


def _eye_worst(face_stats: list) -> tuple:
    """Khuôn mặt NHẮM NHẤT trong khung: trả (độ mở, diện tích %, điểm YuNet).

    Vì sao trả cả ba mà không chỉ trả giá trị nhỏ nhất: luật loại ảnh nhắm mắt
    phải biết cái mặt cho ra con số đó có ĐÁNG TIN không — mặt bé bằng hạt gạo
    ở cuối phòng thì độ mở mắt đo được chỉ là nhiễu. Lấy face_area_min cho việc
    đó là sai, vì đó là mặt bé nhất trong khung, thường không phải mặt này.
    """
    best = None
    for f in face_stats:
        if f.get("eye") is None:
            continue
        if best is None or f["eye"] < best["eye"]:
            best = f
    if best is None:
        return (None, None, None)
    return (float(best["eye"]), best.get("area_pct"), best.get("score"))


def _face_sharpness(Y, x, y, bw, bh) -> float:
    """Độ nét của riêng vùng mặt — bắt ảnh rung, lạc nét.

    Lấy độ lớn gradient trung bình, chuẩn hoá theo độ sáng vùng đó để ảnh tối
    không bị chấm là mờ."""
    h, w = Y.shape
    x0, x1 = int(max(0, x)), int(min(w, x + bw))
    y0, y1 = int(max(0, y)), int(min(h, y + bh))
    if x1 - x0 < 4 or y1 - y0 < 4:
        return 0.0
    f = Y[y0:y1, x0:x1]
    gy = np.abs(np.diff(f, axis=0)).mean()
    gx = np.abs(np.diff(f, axis=1)).mean()
    return float((gy + gx) / (float(f.mean()) + EPS))


def _hist(logv: np.ndarray) -> np.ndarray:
    v = np.clip(logv, LOG_MIN, LOG_MAX - 1e-6)
    return np.histogram(v, bins=NBINS, range=(LOG_MIN, LOG_MAX))[0].astype(np.int32)


def frac_above(hist: np.ndarray, thresh_log: float, shift_ev: float) -> float:
    """Tỉ lệ pixel vượt ngưỡng sau khi dịch exposure `shift_ev` stop."""
    t = thresh_log - shift_ev
    idx = int(np.ceil((t - LOG_MIN) / BW))
    idx = max(0, min(NBINS, idx))
    tot = hist.sum()
    return float(hist[idx:].sum()) / tot if tot else 0.0


def frac_below(hist: np.ndarray, thresh_log: float, shift_ev: float) -> float:
    t = thresh_log - shift_ev
    idx = int(np.floor((t - LOG_MIN) / BW))
    idx = max(0, min(NBINS, idx))
    tot = hist.sum()
    return float(hist[:idx].sum()) / tot if tot else 0.0


#[[ ============ DO DO MO MAT (EAR) NGAY TRONG LUOT PHAN TICH ============
#
#   Truoc day eye_ear.py doc RAW mot luot RIENG chi de do mat: doc file, phan
#   tich ARW, giai nen JPEG hai lan nua. Ca buoi 1464 anh mat them ~12 phut cho
#   dung mot con so.
#
#   Gop vao day thi dung lai duoc blob JPEG da nam san trong bo nho. Van phai
#   giai nen them mot lan o co lon (3000px) — va PHAI GIU DUNG nhu vay, vi
#   nguong 0.12 duoc hieu chuan tren 93 nhan tay do o dung do phan giai do.
#   Do o 1024px thi con so EAR khac di va toan bo hieu chuan mat hieu luc.
#
#   CAN SANG LA UU TIEN SO MOT: moi thu o day deu boc trong try, thieu
#   mediapipe hay loi gi cung chi lam mat con so EAR, khong bao gio lam hong
#   phep do sang.
#]]
EAR_BIG_PX = 3000       # canh dai anh dung de cat mat — GIU NGUYEN, xem tren
EAR_CROP_PX = 320       # canh o mat dua vao FaceMesh
EAR_MARGIN = 0.45       # noi khung mat ra bay nhieu lan truoc khi cat
_L_EYE = dict(top=[159, 158], bot=[145, 153], l=33, r=133)
_R_EYE = dict(top=[386, 385], bot=[374, 380], l=362, r=263)
_MESH = None
_MESH_LOI = ""


def _facemesh():
    """FaceMesh dung chung trong mot tien trinh con. None = khong dung duoc."""
    global _MESH, _MESH_LOI
    if _MESH is None:
        try:
            import mediapipe as mp
            _MESH = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=True, max_num_faces=1, refine_landmarks=True,
                min_detection_confidence=0.2)
        except Exception as ex:                      # noqa: BLE001
            _MESH_LOI = f"{type(ex).__name__}: {ex}"
            _MESH = False
    return _MESH or None


def _ear_mot_mat(lm, w, h, spec):
    def pt(i):
        return np.array([lm[i].x * w, lm[i].y * h])
    ngang = np.linalg.norm(pt(spec["l"]) - pt(spec["r"]))
    if ngang < 1e-6:
        return None
    doc = np.mean([np.linalg.norm(pt(a) - pt(b))
                   for a, b in zip(spec["top"], spec["bot"])])
    return float(doc / ngang)


def do_ear(blob, tags, faces, det_wh, out: dict) -> None:
    """Đo EAR cho mọi mặt YuNet tìm được, ghi vào out. Không bao giờ ném lỗi."""
    mesh = _facemesh()
    if mesh is None:
        out["ear_err"] = _MESH_LOI or "thieu mediapipe"
        return
    try:
        im = Image.open(io.BytesIO(blob))
        im.draft("RGB", (EAR_BIG_PX, EAR_BIG_PX))
        big = apply_orientation(im.convert("RGB"), tags.get("orientation"))
        if max(big.size) > EAR_BIG_PX:
            big.thumbnail((EAR_BIG_PX, EAR_BIG_PX), Image.BILINEAR)
        arr = np.asarray(big)
        sx = big.size[0] / float(max(det_wh[0], 1))
        sy = big.size[1] / float(max(det_wh[1], 1))
        vals, dung = [], 0
        for f in faces:
            x, y, bw, bh = f[0], f[1], f[2], f[3]
            cx, cy = (x + bw / 2) * sx, (y + bh / 2) * sy
            r = max(bw * sx, bh * sy) * (0.5 + EAR_MARGIN)
            x0, y0 = int(max(0, cx - r)), int(max(0, cy - r))
            x1, y1 = int(min(arr.shape[1], cx + r)), int(min(arr.shape[0], cy + r))
            if x1 - x0 < 40 or y1 - y0 < 40:
                continue
            crop = Image.fromarray(arr[y0:y1, x0:x1]).resize(
                (EAR_CROP_PX, EAR_CROP_PX), Image.BILINEAR)
            res = mesh.process(np.asarray(crop))
            if not res.multi_face_landmarks:
                continue
            dung += 1
            lm = res.multi_face_landmarks[0].landmark
            for spec in (_L_EYE, _R_EYE):
                e = _ear_mot_mat(lm, EAR_CROP_PX, EAR_CROP_PX, spec)
                if e is not None:
                    vals.append(e)
        out["ear_faces"] = dung
        out["ear_min"] = min(vals) if vals else None
    except Exception as ex:                          # noqa: BLE001
        out["ear_err"] = f"{type(ex).__name__}: {ex}"


def bo_mat_ao_to(faces: list, kich_thuoc, to_pct: float, diem: float) -> list:
    """Bo khung mat VUA diem duoi `diem` VUA chiem hon `to_pct` % khung hinh.
    Khung la (x, y, w, h, diem, ...) cua YuNet; kich_thuoc = (rong, cao) cua anh
    dua vao nhan dien. to_pct <= 0 -> tra nguyen. Xem chu thich trong measure()."""
    if to_pct <= 0 or not faces:
        return list(faces)
    S_ = float(kich_thuoc[0]) * float(kich_thuoc[1])
    return [f for f in faces
            if not (float(f[4]) < diem and float(f[2]) * float(f[3]) > S_ * to_pct / 100.0)]


def la_den_trang(im) -> bool:
    """Preview này là ảnh ĐEN TRẮNG (máy chụp ở kiểu ảnh B/W — Sony Creative
    Style "B/W", Canon "Monochrome"...)?

    #[[ 8/10 (user: "anh Raw load Preview nhin thay dang de che do BW — can giu
    #   nguyen mau BW nay va van sua cac thong so khac"). JPEG nhung trong RAW la
    #   ban MAY dung theo kieu anh dang chon: B/W thi R = G = B tung diem (lech
    #   1-2 muc vi nen JPEG). Anh mau that luon co da / vai / nen lech hang chuc
    #   muc — ke ca anh "gan nhu xam" (phong trang, ao den) thi da nguoi van lech
    #   >= 15. Nen lay phan vi 99,5 cua do lech kenh: <= 6 la den trang.
    #   Do o ban nho 160 px: nhanh, va JPEG thu nho khong sinh mau gia. ]]
    """
    try:
        nho = im.copy()
        nho.thumbnail((160, 160))
        a = np.asarray(nho, dtype=np.int16)
        if a.ndim != 3 or a.shape[2] < 3:
            return True                   # preview 1 kenh: chac chan xam
        lech = a[..., :3].max(axis=2) - a[..., :3].min(axis=2)
        return bool(np.percentile(lech, 99.5) <= 6)
    except Exception:                     # noqa: BLE001
        return False


def la_bw_catalog(crs: dict) -> bool:
    """Lightroom / sidecar đang để ảnh này ở Black & White (ConvertToGrayscale)."""
    v = str((crs or {}).get("ConvertToGrayscale", "")).strip().lower()
    return v in ("true", "1")


def measure(path: Path, preview_px: int, meter: str, hl_cut: float = 0.85,
            wb_needs_faces: bool = False, face_px: int = 1024,
            face_score: float = 0.5, focus_q: float = 0.92,
            focus_gain: float = 2.0, face_min_ratio: float = 0.25,
            subject_keep: float = 0.60,
            subject_dark_ev: float = 2.0,
            face_min_score_sub: float = 0.0,
            big_low_ratio: float = 0.0,
            big_low_gap: float = 0.15,
            big_low_floor: float = 0.70,
            can_ear: bool = False,
            # Dat SAU can_ear de moi loi goi theo vi tri san co giu nguyen.
            # hl_da_ti_le = 0 -> tat, quay ve chi do dai 30-90%.
            hl_da_ti_le: float = 0.0,
            hl_da_muc: float = 220.0,
            af_gan_mat: float = 0.0,
            af_xoay_theo_anh: bool = True,
            af_nikon: bool = False,
            # Dat CUOI de moi loi goi theo vi tri san co giu nguyen.
            mat_ao_to_pct: float = 0.0,
            mat_ao_diem: float = 0.6) -> dict:
    """Đọc RAW -> preview -> thống kê. Chạy trong worker process."""
    out = {"path": str(path), "ok": False, "error": ""}
    try:
        blob, tags = read_raw(path)
        if blob is None:
            out["error"] = "khong tim thay preview JPEG trong RAW"
            return out

        # Nhận diện mặt cần ảnh to hơn thống kê; decode một lần ở cỡ lớn hơn rồi
        # mới thu nhỏ, tránh giải nén JPEG hai lượt.
        want_faces = meter in ("face", "focus") or wb_needs_faces
        big = max(preview_px, face_px) if want_faces else preview_px

        im = Image.open(io.BytesIO(blob))
        im.draft("RGB", (big, big))   # decode thẳng ở tỉ lệ nhỏ -> rất nhanh
        im = im.convert("RGB")
        im = apply_orientation(im, tags.get("orientation"))
        out["bw"] = la_den_trang(im)

        #[[ Đo mặt ở ĐỘ PHÂN GIẢI NHẬN DIỆN, không phải ở ảnh thống kê 480px.
        #   Mặt trong ảnh sự kiện chỉ ~53px trên khung 1024; thu về 480 thì ô mặt
        #   còn ~14px, đo ra sai lệch thấy rõ. Chỉ cắt đúng mấy ô nhỏ nên không tốn.
        #]]
        faces, face_patches = [], []
        #[[ BON TEN NAY PHAI KHOI TAO O DAY, khong phai trong "if want_faces".
        #
        #   Duoi kia out.update(...) doc face_stats/best_eye/best_sharp/fw_/fh_
        #   VO DIEU KIEN. Khi khong do mat — meter la subject/center/average/
        #   median VA wb khac "skin" — nhanh if khong chay, cac ten do khong ton
        #   tai, UnboundLocalError roi thang vao except boc ca measure(): MOI anh
        #   tra ve ok=False, app bao loi doc anh cho ca thu muc ma khong he lo ra
        #   day la loi lap trinh. Mac dinh wb="skin" nen loi bi che kin.
        #
        #   Bat duoc khi viet tu_kiem.py: bai kiem chay measure() that voi ca 6
        #   cach do nhan hai gia tri wb_needs_faces — to hop ma khong bai kiem
        #   nao truoc do cham toi. Sau do quet AST tim moi ten "chi gan trong
        #   khoi if ma van doc sau khoi" de khong phai vet tung ten mot; xem
        #   phep kiem 12 trong kiem_do_mat.py.
        #]]
        face_stats = []
        best_eye = best_sharp = None
        fw_ = fh_ = 0
        metered_focus = None
        if want_faces:
            imf = im.copy()
            imf.thumbnail((face_px, face_px), Image.BILINEAR)
            faces = detect_faces(imf, face_score)

            #[[ CHỐT CHẶN BÁO MẶT ẢO — bỏ khung có điểm tin cậy thấp.
            #
            #   YuNet báo nhầm mặt trên phông nền, màn LED, tờ sticker, lưng
            #   người quay đi. Những khung ảo đó TO nên thắng trọng số chọn chủ
            #   thể (căn bậc hai diện tích x điểm), rồi kéo cân sáng cả bức theo
            #   độ sáng của một vật thể.
            #
            #   Đối chiếu YuNet với InsightFace trên 400 ảnh buổi 1308: 11 ảnh
            #   (2,8%) có chủ thể mà InsightFace không coi là mặt. Xem tận mắt 5
            #   ảnh thì cả 5 đều là báo ảo — tờ sticker (SAY02075), logo trên
            #   màn LED (SAY03054), phông nền (SAY02506), lưng người tiền cảnh
            #   (SAY02179, DSC01229).
            #
            #   KHÔNG có khung nào đạt ngưỡng -> BỎ HẾT, lùi về đo theo vùng
            #   bắt nét.
            #
            #   ĐÃ BỊ BÁC BỎ — ĐỪNG BẬT, VÀ ĐỪNG THỬ LẠI BẰNG CÁCH CHỈNH NGƯỠNG
            #   ------------------------------------------------------------
            #   Người dùng chấm tay 18 ảnh đổi nhiều nhất khi bật ngưỡng 0,80:
            #   chốt chặn ĐÚNG 11 ảnh, HỎNG 7 ảnh. Đo điểm YuNet của chính
            #   những khung bị loại (80 khung ở ảnh đúng, 24 khung ở ảnh hỏng):
            #       đúng  0,501 - 0,800   (trung vị 0,624)
            #       hỏng  0,506 - 0,793   (trung vị 0,736)
            #   Hai dải TRÙNG NHAU gần như hoàn toàn. Không ngưỡng nào tách
            #   được — hạ xuống thì mất tác dụng, nâng lên thì vứt mặt thật.
            #
            #   Đã thử thêm hình học 5 điểm mốc trên đúng 15 khung có nhãn từng
            #   khung (11 khung xấu / 4 khung tốt): khoảng cách hai mắt trên bề
            #   rộng khung, mũi lệch khỏi trục, độ đối xứng, tỉ lệ cao/rộng, độ
            #   nét. CẢ NĂM đều chồng nhau. Hai khung mặt thật (DSC01546,
            #   SAY03286) còn có hình học méo hơn phần lớn khung xấu.
            #
            #   VÌ SAO KHÔNG TÁCH ĐƯỢC: người dùng mô tả khung xấu là "1 góc mặt
            #   hoặc đứng sau gáy". Đó THẬT SỰ là mặt người — cả YuNet lẫn
            #   InsightFace đều nhận đúng. Câu hỏi thật không phải "có phải mặt
            #   không" mà là "mặt này có dùng để cân sáng được không", và không
            #   bộ dò mặt nào trả lời câu đó. Lấy InsightFace làm ý kiến thứ hai
            #   cũng chỉ đúng 7/10 ca.
            #
            #   Hướng còn lại (chưa làm): thay vì cố nhận ra khung xấu, làm cho
            #   phép đo BỀN với nó — ảnh nhiều mặt thì lấy trung vị độ sáng các
            #   mặt thay vì bám vào một mặt nặng ký nhất. Phải kiểm trên 893 ảnh
            #   đã duyệt trước khi đụng vào.
            #
            #   Giữ tham số này lại để còn đo đạc, nhưng mặc định 0 = TẮT.
            #]]
            if face_min_score_sub > 0 and faces:
                good = [f for f in faces if f[4] >= face_min_score_sub]
                out["faces_lowconf"] = len(faces) - len(good)
                faces = good

            #[[ BỎ KHUNG VỪA ĐIỂM THẤP VỪA TO BẤT THƯỜNG (mat_ao_to_pct). 0 = TẮT.
            #
            #   KHÁC chốt điểm thấp ở trên (đã bác bỏ vì dải điểm khung xấu và
            #   khung tốt trùng nhau): chỉ bỏ khung có CẢ HAI dấu hiệu — điểm dưới
            #   mat_ao_diem VÀ chiếm hơn mat_ao_to_pct % khung hình.
            #
            #   GẶP THẬT 3/10, buổi HPC 25nam\Hiu: HIU02258 là ảnh cận cổ tay
            #   đeo vòng, không có mặt nào. YuNet báo một "mặt" điểm 0,50, rộng
            #   514x551 trên khung 1024x683 — 40% khung, tràn ra ngoài mép trên —
            #   chính là cánh tay. Tool kéo −1,31 trong khi HIU02257 ngay cạnh
            #   (cùng thông số, cùng góc, không thấy mặt) giữ 0,00: hai tấm liền
            #   nhau lệch 1,3 EV.
            #
            #   VÌ SAO HAI DẤU HIỆU THÌ TÁCH ĐƯỢC: mặt thật mà to cỡ đó là chân
            #   dung cận, YuNet nhìn rõ nên cho điểm cao. Đo 40.521 khung mặt của
            #   TrainTool + 2609: 8 khung chiếm > 15% khung hình, điểm 0,65–0,92;
            #   KHÔNG khung nào vừa < 0,6 vừa > 15%. Khung to mà điểm thấp là YuNet
            #   đang đoán mò trên một mảng màu da — tay, cánh tay, vai.
            #]]
            if mat_ao_to_pct > 0 and faces:
                good = bo_mat_ao_to(faces, imf.size, mat_ao_to_pct, mat_ao_diem)
                out["faces_ao_to"] = len(faces) - len(good)
                faces = good

            #[[ Bỏ mặt quá nhỏ so với mặt lớn nhất.
            #   Mặt người trên màn LED, poster, hay khán giả phía sau luôn nhỏ
            #   hơn hẳn chủ thể — mà màn LED thì sáng hơn mặt thật cả 0.8 EV.
            #   Không loại thì phép đo bị kéo lên, script tưởng ảnh đã đủ sáng
            #   và để chủ thể tối đi (đã gặp thật: 2 mặt trên màn LED chỉ chiếm
            #   13% trọng số mà làm lệch 0.4 EV).
            #]]
            if face_min_ratio > 0 and len(faces) > 1:
                amax = max(f[2] * f[3] for f in faces)
                keep = [f for f in faces if f[2] * f[3] >= amax * face_min_ratio]
                out["faces_dropped"] = len(faces) - len(keep)
                faces = keep

            energy, tile = focus_energy(imf)

            af = np.asarray(imf, dtype=np.float32) / 255.0
            linf = srgb_to_linear(af)
            Yf = (0.2126 * linf[..., 0] + 0.7152 * linf[..., 1]
                  + 0.0722 * linf[..., 2])
            fh_, fw_ = Yf.shape

            # --- độ sáng của vùng bắt nét (dùng khi không thấy mặt nào) ---
            if energy is not None:
                thr = float(np.quantile(energy, focus_q))
                sel_t = energy >= thr
                th_, tw_ = energy.shape
                big = np.repeat(np.repeat(sel_t, tile, axis=0), tile, axis=1)
                sub = Yf[:th_ * tile, :tw_ * tile]
                pick = sub[big]
                if pick.size >= 64:
                    metered_focus = float(2.0 ** float(np.log2(pick + EPS).mean()))

            # --- ô mặt, có cộng điểm cho mặt nằm đúng chỗ bắt nét ---
            if energy is not None:
                q50, q95 = float(np.quantile(energy, 0.5)), float(np.quantile(energy, 0.95))
            #[[ Vung AF Nikon (Wide-area): may chon net o DAU DO trong vung, nen
            #   mat nao CHAM vung la mat chu the — khong doi mat trung dung tam.
            #   af_nikon = False -> bo qua diem AF cua Nikon, hanh vi cu.
            #]]
            vung = tags.get("af_vung")
            if vung is not None and not af_nikon:
                afpt, vung = None, None
            else:
                afpt = tags.get("af_point")
            #[[ LENS CO (8/10): EXIF khong co khau (fisheye 10mm khong tiep diem)
            #   = lens lay net TAY. Diem AF may ghi chi la vi tri o AF dang dat,
            #   khong phai cho may khoa net -> bo, khong dung chon chu the. Va
            #   do NET khong noi may net vao ai (fisheye sau truong anh het, nen
            #   ban nhieu canh sac lam mat hau canh ti hon "net" hon mat chinh
            #   to, da min) — xem nhanh chon chu the ben duoi. Buoi raw 19.4:
            #   HUY04802/04830/04789... mat chinh 108x164 diem 0.93 bi bo vi
            #   "kem net" (0.58), do sang lay tu mat hau canh 12x15 (-3.2..-5.3
            #   EV) -> tool keo sang +0.7..+1.75 EV. ]]
            lens_co = not (_rat(tags.get("fnumber")) or 0)
            if lens_co:
                afpt, vung = None, None
            af_hop = None
            if afpt is not None:
                huong = tags.get("orientation") if af_xoay_theo_anh else 1
                if vung is not None:
                    c1 = af_theo_huong((afpt[0] - vung[0] / 2, afpt[1] - vung[1] / 2), huong)
                    c2 = af_theo_huong((afpt[0] + vung[0] / 2, afpt[1] + vung[1] / 2), huong)
                    af_hop = (min(c1[0], c2[0]), min(c1[1], c2[1]),
                              max(c1[0], c2[0]), max(c1[1], c2[1]))
                    out["af_hop"] = tuple(round(v, 4) for v in af_hop)
                afpt = af_theo_huong(afpt, huong)
            if afpt is not None:
                out["af_xy"] = (round(afpt[0], 4), round(afpt[1], 4))
            #[[ Cham diem tung khuon mat de loc anh loat (xem pick_burst).
            #
            #   Hai tieu chi, deu do tren MAT CHU THE:
            #     - eye_open: do MO mat. Cat o mat, tinh do lech chuan doc /
            #       ngang. Mat mo co long den + long trang nen bien thien doc
            #       cao; mat nham chi con mot vet mi nen gan nhu phang.
            #     - face_sharp: do net cua rieng vung mat (khong phai ca khung).
            #       Anh rung, lac net thi mat mo du bo cuc dep.
            #]]
            best_eye, best_sharp, best_w = None, None, -1.0
            #[[ Đo mắt và độ nét cho TỪNG khuôn mặt, không chỉ mặt chủ thể.
            #
            #   Cần cho luật lọc ảnh nhắm mắt: ảnh 1 người hoặc nhóm 2-4 người
            #   mà CÓ AI ĐÓ nhắm mắt thì loại; ảnh tập thể đông người thì không
            #   loại, vì tính chất ảnh tập thể là luôn có người này người kia.
            #   Muốn biết "có ai đó" thì phải đo hết, chứ đo mỗi chủ thể là
            #   không trả lời được câu hỏi.
            #
            #   Kèm cỡ mặt và điểm tin cậy để bên dùng biết phép đo có đáng tin
            #   không: mắt trên một khuôn mặt vài chục pixel thì đo cũng như
            #   đoán.
            #]]
            face_stats = []
            for x, y, bw, bh, s, _eyes in faces:
                cx, cy = x + bw / 2, y + bh / 2

                #[[ Mặt có TRÙM điểm lấy nét thật của máy không.
                #
                #   Đây là tín hiệu chắc chắn nhất: máy đã khoá nét vào ai thì
                #   người đó là chủ thể. Chắc hơn hẳn suy đoán từ nội dung ảnh
                #   — đã thử độ nét (thước đo cạnh nhầm màn LED phẳng là "mờ"),
                #   vị trí Y (chỉ đúng 17%), điểm nhận diện (trung vị chênh
                #   0.04, không phân hoá). Cả ba đều không đủ tin.
                #
                #   Nới rộng ô mặt 30% vì AF thường khoá vào MẮT, mà ô mặt của
                #   YuNet đôi khi lệch chút so với khung mặt thật.
                #]]
                on_af = False
                if af_hop is not None:
                    # vung AF (Nikon): o mat CHAM vung la du
                    on_af = (x <= af_hop[2] * fw_ and x + bw >= af_hop[0] * fw_
                             and y <= af_hop[3] * fh_ and y + bh >= af_hop[1] * fh_)
                elif afpt is not None:
                    ax, ay = afpt[0] * fw_, afpt[1] * fh_
                    # Sàn tuyệt đối 2% cạnh ảnh: mặt nhỏ (chủ thể đứng xa) thì
                    # biên theo tỉ lệ chỉ còn vài pixel, trong khi AF khoá vào
                    # MẮT nên lệch tâm mặt là chuyện thường. Gặp thật: AF cách
                    # tâm mặt 14px mà biên tỉ lệ chỉ cho 7px -> trượt.
                    pad = 0.02 * max(fw_, fh_)
                    mx_ = max(bw * 0.30, pad)
                    my_ = max(bh * 0.30, pad)
                    on_af = (x - mx_ <= ax <= x + bw + mx_
                             and y - my_ <= ay <= y + bh + my_)
                hw, hh = bw * 0.275, bh * 0.275
                x0, x1 = int(max(0, cx - hw)), int(min(fw_, cx + hw))
                y0, y1 = int(max(0, cy - hh)), int(min(fh_, cy + hh))
                if x1 - x0 < 3 or y1 - y0 < 3:
                    continue
                pv = Yf[y0:y1, x0:x1].ravel()

                #[[ Lọc theo MÀU DA trước, rồi mới lọc theo độ sáng.
                #
                #   Ô mặt là hình chữ nhật nên luôn dính kính, tóc, cổ áo, hậu
                #   cảnh. Đo thật: mặt người mặc vest xanh có 25% pixel là màu
                #   áo (hue 238°) — gộp vào thì phép đo lệch gần 1 EV và màu da
                #   đo được cũng sai theo.
                #
                #   Lọc màu không ăn thua (mặt quá nhỏ, ngược sáng, da rất tối)
                #   thì bỏ qua bước này, dùng nguyên ô như trước — thà đo hơi
                #   lệch còn hơn vứt mất khuôn mặt.
                #]]
                pc = af[y0:y1, x0:x1].reshape(-1, 3)
                sk = skin_mask(pc)
                # Vut not pixel toi hon han vung da — xem SKIN_DARK_REL
                if SKIN_DARK_REL > 0 and sk.sum() >= 9:
                    sk_hue = sk
                    sk = sk & (pv >= float(np.quantile(pv[sk], 0.90)) * SKIN_DARK_REL)
                    #[[ Loc quá tay thì lùi về mặt nạ hue/sat, KHÔNG để rơi
                    #   xuống nhánh "dùng cả ô".
                    #
                    #   Nhánh đó gộp cả tóc lẫn hậu cảnh nên tệ hơn chính cái ta
                    #   đang sửa. Đo thật trên buổi 1308: 3/1464 ảnh rơi vào bẫy
                    #   này, phép đo TỐI ĐI tới 0.39 EV — ngược hẳn mục đích.
                    #]]
                    if sk.sum() < max(9, int(0.15 * sk.size)):
                        sk = sk_hue
                if sk.sum() >= max(9, int(0.15 * sk.size)):
                    pv_use, keep_sk = pv[sk], sk
                else:
                    pv_use, keep_sk = pv, None

                #[[ DA DA SANG THI DO THEO CHINH VUNG SANG DO.
                #
                #   Dai 30-90% duoi day la vung TRUNG BINH cua da. Voi mot
                #   khuon mat da bi day sang, trung binh van co ve on trong khi
                #   tran va go ma da cham tran va mat chi tiet — phep do khong
                #   thay, nen con de nghi keo sang them.
                #
                #   Khi phan da sang chiem tu `hl_da_ti_le`% tro len, vung sang
                #   KHONG con la mot vai dom bong ma la trang thai chung cua
                #   khuon mat: do thang vao no.
                #
                #   DO TREN 145 ANH THAT, nguong sang 220/255:
                #     nhom >30% : 33 anh, p95 trung vi 248/255
                #     nhom <=30%: 112 anh, p95 trung vi 178/255
                #   Hai nhom tach han nhau, nen 30% la cho cat tu nhien. Quet
                #   200/210/220/230 thi 220 cho ranh gioi sach nhat.
                #
                #   Dat hl_da_ti_le = 0 de tat, quay ve chi do dai 30-90.
                #]]
                #   Do bang max(R,G,B) tren thang sRGB, KHONG phai luminance:
                #   kenh nao cham tran truoc thi pixel do mat chi tiet truoc, va
                #   voi da nguoi luon la kenh R. Do thu tren mot khuon mat that:
                #   luminance noi 28% vung da vuot nguong, max(RGB) noi 54% —
                #   con so thu hai moi dung voi cai mat nhin thay.
                sel_b = None
                if hl_da_ti_le > 0:
                    mx_use = (pc[keep_sk] if keep_sk is not None else pc).max(axis=1)
                    sang = mx_use >= (hl_da_muc / 255.0)
                    if sang.mean() * 100.0 >= hl_da_ti_le and sang.sum() >= 9:
                        sel_b = sang
                if sel_b is None:
                    lo, hi = np.quantile(pv_use, 0.30), np.quantile(pv_use, 0.90)
                    sel_b = (pv_use >= lo) & (pv_use <= hi)
                if sel_b.sum() < 9:
                    continue
                # đưa mặt nạ độ sáng về lại chỉ số của cả ô
                if keep_sk is None:
                    sel = sel_b
                else:
                    sel = np.zeros_like(sk)
                    sel[np.flatnonzero(sk)[sel_b]] = True

                # Mặt nằm trong vùng nét thì nặng ký hơn mặt nền/khán giả — đó mới
                # là chủ thể máy đã lấy nét vào.
                bonus = 0.0
                if energy is not None and q95 > q50:
                    ty0, ty1 = int(y // tile), int((y + bh) // tile) + 1
                    tx0, tx1 = int(x // tile), int((x + bw) // tile) + 1
                    cell = energy[max(0, ty0):ty1, max(0, tx0):tx1]
                    if cell.size:
                        bonus = float(np.clip((float(cell.mean()) - q50)
                                              / (q95 - q50), 0.0, 1.0))
                px = linf[y0:y1, x0:x1].reshape(-1, 3)[sel]

                #[[ Trọng số: diện tích DỊU đi bằng căn bậc hai, còn độ nét và
                #   độ tin cậy thì tính đủ.
                #
                #   Dùng thẳng bw*bh thì người ngồi sát máy (mặt to nhưng MỜ vì
                #   ngoài vùng nét) luôn thắng người máy thực sự lấy nét vào.
                #   Gặp thật: mặt to 0.71% khung nhưng nét 0.53 / EV -6.06 đè
                #   mất mặt nét 0.91 / score 0.92 ở giữa khung — chọn nhầm chủ
                #   thể, kéo phép đo tối đi 1.8 EV.
                #
                #   Căn bậc hai vẫn giữ ưu thế cho mặt to (chủ thể thường to
                #   hơn) nhưng không còn áp đảo, để độ nét quyết định.
                #]]
                w = float(np.sqrt(bw * bh) * s * (1.0 + focus_gain * bonus))
                #[[ Mang theo ca KHUNG (x, y, rong, cao, diem) tu day tro di.
                #   De cong cu xem_do_sang.py ve dung nhung khung ma chinh ham
                #   nay dung, thay vi dung lai logic loc o file khac roi lech
                #   voi ban that — da mac dung loi do mot lan trong du an nay.
                #]]
                face_patches.append((float(np.log2(pv[sel] + EPS).mean()), w, px,
                                     bonus, on_af, (float(x), float(y), float(bw),
                                                    float(bh), float(s))))

                local_sharp = _face_sharpness(Yf, x, y, bw, bh)
                local_eye = _eye_openness(Yf, _eyes, bw)
                face_stats.append({
                    "eye": local_eye,
                    "sharp": local_sharp,
                    "score": float(s),
                    # Cac so DE TRUY LOI chon nham chu the — xem xem_do_sang.py.
                    # Ghi tu chinh vong lap that, khong dung lai o file khac.
                    "box": (float(x), float(y), float(bw), float(bh)),
                    "w": float(w),
                    "bonus": float(bonus),
                    "on_af": bool(on_af),
                    "ev": float(np.log2(pv[sel] + EPS).mean()),
                    # dien tich mat so voi ca khung, tinh theo %
                    "area_pct": 100.0 * (bw * bh) / float(max(fw_ * fh_, 1)),
                })

                # chỉ chấm điểm cho khuôn mặt NẶNG KÝ NHẤT (chủ thể)
                if w > best_w:
                    best_w = w
                    best_sharp = local_sharp
                    best_eye = local_eye

            nfaces0 = len(face_patches)

            #[[ CHỌN mặt chủ thể theo điểm bắt nét, thay vì gộp trung bình.
            #
            #   Đo thật trên ảnh hội thảo có 3 mặt: chủ thể (nét nhất, to nhất)
            #   chỉ được 53% trọng số, hai mặt khán giả phía sau chiếm 47% —
            #   kéo phép đo lệch 0.91 EV so với mặt chủ thể. Cộng điểm thôi là
            #   không đủ khi mặt nền vừa nhiều vừa to.
            #
            #   Máy đã lấy nét vào ai thì người đó là chủ thể. Nên: giữ những
            #   mặt có trọng số >= subject_keep phần của mặt nặng nhất, bỏ phần
            #   còn lại. Ảnh chỉ có một mặt, hay nhiều mặt cùng hàng (ảnh nhóm,
            #   ảnh tập thể) thì trọng số xấp xỉ nhau nên giữ nguyên tất cả —
            #   đúng ý, vì lúc đó cả nhóm đều là chủ thể.
            #]]
            #[[ AF point THẬT thắng mọi suy đoán khác.
            #
            #   Có mặt nào trùm đúng điểm máy đã khoá nét thì đó là chủ thể,
            #   dùng riêng nó và bỏ qua toàn bộ phần lọc phía dưới. Nhiều mặt
            #   cùng trùm (đám đông sát nhau) thì giữ cả — lúc đó không phân
            #   biệt được, mà cũng không cần.
            #]]
            #[[ BO KHUNG "TO MA DIEM THAP" khi co khung nho ma diem cao han.
            #
            #   Khong phai loc theo diem tuyet doi — cach do da bi nhan tay cua
            #   nguoi dung bac bo (dai diem khung tot va khung xau trung nhau,
            #   xem chu thich CHOT CHAN BAO MAT AO). Day la luat HEP hon nhieu,
            #   chi ban vao dung mot the: mot khung TO nhung diem THAP thang
            #   trong so, trong khi trong cung anh co khung nho hon ma bo do mat
            #   tin chac chan hon han.
            #
            #   Gap that:
            #     SAY02338  khung 174x149 diem 0.59 (hop nhua) thang mat nguoi
            #               47x56 diem 0.73  -> dien tich gap 9.8 lan
            #     DSC01303  khung 41x57 diem 0.56 (mat tren man dien thoai)
            #               thang mat tren san khau 21x26 diem 0.91 -> gap 4.3 lan
            #   Ca hai truong hop do net va diem bat net deu KHONG cuu duoc:
            #   o DSC01303 chinh khung xau lai co diem bat net cao nhat (0.81).
            #
            #   0 = TAT. Bat len phai do lai tren 893 anh da duyet.
            #]]
            #   LAP chu khong xet mot lan: mot anh co the co HAI khung xau
            #   chong len nhau. DSC01303 bo khung 60x96 diem 0.64 xong thi khung
            #   41x57 diem 0.56 lai len lam chu the — cung mot the, phai xet lai.
            #   Chan tren bang chinh so khung, khong the lap vo tan.
            #   SAN BAO VE: khung co diem tu big_low_floor tro len thi KHONG
            #   bao gio bi bo, du to den may. Khong co san nay thi vong lap an
            #   lan sang mat that: SAY03286 bo dung khung sau gay (diem 0.53)
            #   xong lai bo tiep dung mat can chon (0.76) roi nhay ra mat o xa.
            n_bo = 0
            while big_low_ratio > 0 and len(face_patches) > 1:
                main = max(face_patches, key=lambda fp: fp[1])
                s_main = main[5][4]
                if s_main >= big_low_floor:
                    break
                alts = [fp for fp in face_patches
                        if fp is not main and fp[5][4] >= s_main + big_low_gap]
                if not alts:
                    break
                #   So voi khung DANG TIN NHAT, khong phai khung nang ky nhat.
                #   DSC01303: sau khi bo khung 60x96, khung xau 41x57 con lai
                #   duoc so voi 30x52 (diem 0.72, nang ky hon) -> ti le 1.5,
                #   khong an. So voi mat that 21x26 (diem 0.91) thi ti le 4.3.
                #   Cau hoi dung la "co mat nao TIN CHAC HON ma be hon han
                #   khong", nen phai lay khung diem cao nhat.
                alt = max(alts, key=lambda fp: (fp[5][4], fp[1]))
                a_main = main[5][2] * main[5][3]
                a_alt = alt[5][2] * alt[5][3]
                if a_alt <= 0 or a_main < a_alt * big_low_ratio:
                    break
                face_patches = [fp for fp in face_patches if fp is not main]
                n_bo += 1
            if n_bo:
                out["faces_big_lowconf"] = n_bo

            #[[ AF ROI SAT MAT NHUNG KHONG TRUNG O MAT -> lay mat GAN NHAT.
            #
            #   Gap that bo 2609 (29/9), sau khi da xoay diem AF theo anh: may
            #   khoa net vao CO / co ao (SAY06504, SAY06753 — cach mep duoi o mat
            #   0.4 lan co mat), hoac vao toc / khan voan sau gay co dau dang
            #   nghieng mat (SAY06560-06564 — 0.7 lan). Khong trung o nao nen
            #   tool lui ve doan theo noi dung anh, va chon mat nguoi dung sau.
            #   May da khoa vao NGUOI do; mat gan nhat chinh la mat ho.
            #
            #   Chi xet khi KHONG co mat nao trung diem AF. Khoang cach tinh tu
            #   diem AF toi MEP o mat, chia cho canh dai cua o mat do — mat to
            #   thi duoc xa hon mat nho, dung voi co nguoi trong khung.
            #   af_gan_mat = 0 -> TAT (hanh vi cu).
            #]]
            if (afpt is not None and af_gan_mat > 0 and face_patches
                    and not any(len(fp) > 4 and fp[4] for fp in face_patches)):
                i_gan, d_min = mat_gan_af([fp[5][:4] for fp in face_patches],
                                          afpt[0] * fw_, afpt[1] * fh_, af_gan_mat)
                if i_gan is not None:
                    face_patches = [fp if i != i_gan else fp[:4] + (True,) + fp[5:]
                                    for i, fp in enumerate(face_patches)]
                    out["af_gan"] = round(d_min, 3)

            af_hit = [fp for fp in face_patches if len(fp) > 4 and fp[4]]
            if af_hit and len(af_hit) < len(face_patches):
                out["faces_bg_dropped"] = len(face_patches) - len(af_hit)
                out["subject_by"] = "af"
                face_patches = af_hit

            elif len(face_patches) > 1 and subject_keep > 0:
                #[[ Không có AF point (ảnh đời cũ, máy hãng khác) thì mới suy
                #   đoán từ nội dung ảnh — kém tin hơn nhưng còn hơn không.
                #]]
                #[[ Hai bước: lọc theo ĐỘ NÉT trước, rồi mới theo trọng số.
                #
                #   Máy đã lấy nét vào ai thì người đó là chủ thể — đó là tín
                #   hiệu chắc chắn nhất, chắc hơn cả kích thước. Người ngồi sát
                #   máy có mặt to nhưng nằm ngoài vùng nét thì không phải chủ
                #   thể, dù mặt to gấp 7 lần.
                #
                #   Chỉ lọc khi độ nét thật sự phân hoá (nét nhất >= 0.5). Ảnh
                #   chụp nhóm đứng cùng hàng thì ai cũng nét ngang nhau, lọc
                #   bước này không loại ai — đúng ý.
                #]]
                bmax = max(fp[3] for fp in face_patches)
                if bmax >= 0.45 and not lens_co:
                    #[[ Ngưỡng TUYỆT ĐỐI theo khoảng cách tới mặt nét nhất, chứ
                    #   không phải theo tỉ lệ.
                    #
                    #   Ảnh hội thảo: người thuyết trình nét ~0.9, khán giả ngồi
                    #   dưới mờ ~0.5. Lấy tỉ lệ 0.65 thì 0.5 >= 0.9*0.65 = 0.585
                    #   -> hụt sát nút, có ảnh lọt có ảnh không. Lấy hiệu số thì
                    #   dứt khoát: cách mặt nét nhất quá 0.25 là hậu cảnh.
                    #
                    #   Ảnh nhóm cùng hàng thì độ nét chênh nhau rất ít nên
                    #   không ai bị loại.
                    #]]
                    sharp = [fp for fp in face_patches if fp[3] >= bmax - 0.25]
                    if sharp:
                        face_patches = sharp

                    #[[ Độ nét phân hoá MẠNH thì tin hẳn vào nó.
                    #
                    #   Ảnh hội thảo: người thuyết trình nét 0.9, khán giả ngồi
                    #   dưới 0.1-0.5. Chênh nhau quá 0.35 nghĩa là máy đã lấy
                    #   nét rất dứt khoát vào một người — giữ đúng nhóm nét nhất
                    #   (trong 0.15) và bỏ hết phần còn lại, kể cả mặt to hơn.
                    #
                    #   Ảnh nhóm thì chênh lệch nhỏ nên không vào nhánh này.
                    #]]
                    bmin = min(fp[3] for fp in face_patches)
                    if bmax - bmin > 0.35:
                        top = [fp for fp in face_patches if fp[3] >= bmax - 0.15]
                        if top:
                            face_patches = top

                wmax = max(fp[1] for fp in face_patches)
                if wmax > 0:
                    kept = [fp for fp in face_patches if fp[1] >= wmax * subject_keep]
                    if kept:
                        face_patches = kept

                #[[ Bỏ nốt mặt TỐI HƠN HẲN mặt chính.
                #
                #   Qua được vòng lọc nét vẫn còn sót khán giả ngồi rìa vùng nét
                #   (đã gặp: nét 0.83 nhưng tối hơn chủ thể 3.9 EV). Hai người
                #   cùng được chiếu sáng thì không thể chênh nhau tới vài EV —
                #   chênh thế nghĩa là một người đứng dưới đèn, một người ngồi
                #   trong bóng tối, và người dưới đèn mới là chủ thể.
                #
                #   Chỉ bỏ theo MỘT chiều (tối hơn). Mặt sáng hơn thì giữ, vì
                #   đó có thể là chủ thể bị ngược sáng — bỏ đi sẽ hỏng đúng loại
                #   ảnh cần cứu nhất.
                #]]
                if len(face_patches) > 1:
                    main_fp = max(face_patches, key=lambda fp: fp[1])
                    lo_cut = main_fp[0] - subject_dark_ev
                    kept2 = [fp for fp in face_patches if fp[0] >= lo_cut]
                    if kept2:
                        face_patches = kept2

                out["faces_bg_dropped"] = nfaces0 - len(face_patches)

            #[[ Ghi lai DUNG nhung khung da di vao phep do sang.
            #   all_boxes  : moi khung YuNet bao, ke ca khung bi loai
            #   meter_boxes: khung con lai sau tat ca cac vong loc -> chinh la
            #                vung lay do sang
            #   subject_box: khung nang ky nhat trong so do
            #]]
            out["preview_wh"] = (int(fw_), int(fh_))
            out["face_debug"] = face_stats

            #[[ Do mat NGAY TAI DAY, dung lai blob JPEG dang co trong bo nho.
            #   Dat sau khi da co `faces` va sau khi phep do sang da xong phan
            #   cua no — can sang khong phu thuoc mot dong nao ben duoi.
            #]]
            if can_ear and faces:
                do_ear(blob, tags, faces, (fw_, fh_), out)
            out["all_boxes"] = [(float(f[0]), float(f[1]), float(f[2]),
                                 float(f[3]), float(f[4])) for f in faces]
            if face_patches:
                out["meter_boxes"] = [fp[5] for fp in face_patches if len(fp) > 5]
                out["subject_box"] = max(face_patches, key=lambda fp: fp[1])[5]

            del af, linf, Yf

        im.thumbnail((preview_px, preview_px), Image.BILINEAR)

        a8 = np.asarray(im, dtype=np.uint8)
        # Pixel đã bão hoà / bị nghiền đen trong preview: giá trị thật không còn
        # đọc được từ JPEG, phải theo dõi riêng thay vì dựa vào histogram.
        sat_frac = float((a8.max(axis=2) >= 254).mean())
        #[[ Vung GAN chay: sang tren 242/255 nhung chua cham tran.
        #
        #   Ao so mi trang, ao dai, tuong sang... thuong nam o day. Chua "chay"
        #   theo dinh nghia >=254 nen thuat toan cu khong thay gi, trong khi mat
        #   nguoi da thay be	t chi tiet vai va phai keo Highlights bang tay.
        #
        #   Do that tren anh nguoi mac so mi trang: 8.1% pixel >= 242 nhung chi
        #   0.01% >= 254 -> hl_adj = 0, Highlights giu nguyen preset +16.
        #]]
        bright_frac = float((a8.max(axis=2) >= 242).mean())
        crush_frac = float((a8.max(axis=2) <= 1).mean())

        #[[ CHAY SANG RIENG TREN CHU THE (mat + than nguoi ngay duoi).
        #
        #   sat_frac/bright_frac o tren do CA KHUNG. Anh su kien ngoai troi co
        #   nen cay coi toi, nen ti le chay ca khung thap trong khi AO TRANG
        #   cua chu the da chay trang xoa — phanh hl_hard_pct khong bao gio
        #   kich hoat. Do that tren SAYMedia-04770: ca khung 5.4% chay, nhung
        #   rieng vung chu the thi ao gan nhu mat sach chi tiet vai.
        #
        #   Vung chu the uoc luong tu khung mat: rong gap 3 lan mat, cao tu
        #   dinh dau xuong 4 lan chieu cao mat. Khong tach nguoi bang mo hinh —
        #   ton them mot lan suy dien cho moi anh, ma ti le thuan nay da du de
        #   biet "ao chu the co dang chay khong".
        #]]
        subj_sat = subj_bright = None
        sb = out.get("subject_box")
        pw_, ph_ = out.get("preview_wh", (0, 0))
        if sb and pw_ and ph_:
            H8, W8 = a8.shape[:2]
            kx, ky = W8 / float(pw_), H8 / float(ph_)
            fx, fy, fw2, fh2 = (float(sb[0]) * kx, float(sb[1]) * ky,
                                float(sb[2]) * kx, float(sb[3]) * ky)
            cx = fx + fw2 / 2.0
            x0s = int(max(0, cx - fw2 * 1.5))
            x1s = int(min(W8, cx + fw2 * 1.5))
            y0s = int(max(0, fy))
            y1s = int(min(H8, fy + fh2 * 4.0))
            if x1s - x0s >= 4 and y1s - y0s >= 4:
                v8 = a8[y0s:y1s, x0s:x1s].max(axis=2)
                subj_sat = float((v8 >= 254).mean())
                subj_bright = float((v8 >= 242).mean())

        a = a8.astype(np.float32) / 255.0
        lin = srgb_to_linear(a)
        Y = 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]
        Ymax = lin.max(axis=2)

        h, w = Y.shape
        yy = (np.arange(h, dtype=np.float32) - (h - 1) / 2) / max(h / 2, 1)
        xx = (np.arange(w, dtype=np.float32) - (w - 1) / 2) / max(w / 2, 1)
        r2 = yy[:, None] ** 2 + xx[None, :] ** 2
        wmap = np.exp(-r2 / (2 * 0.55 ** 2))

        logY = np.log2(Y + EPS)

        # Ô mặt đã được đo ở trên, tại độ phân giải nhận diện
        metered_face = None
        if face_patches:
            wts = np.array([p[1] for p in face_patches], dtype=np.float64)
            lgs = np.array([p[0] for p in face_patches], dtype=np.float64)
            metered_face = float(2.0 ** float(np.average(lgs, weights=wts)))

        def meter_subject():
            # center-weighted nhưng BỎ vùng sáng nhất (màn LED, cửa sổ, đèn sân
            # khấu). Không loại thì một cái màn hình to sẽ kéo phép đo lên, script
            # tưởng ảnh thừa sáng rồi dìm chủ thể xuống — đúng ngược ý muốn.
            cut = float(np.quantile(Y, hl_cut))
            keep = Y <= cut
            if keep.mean() < 0.05:          # cả khung đều sáng -> không loại gì
                keep = np.ones_like(Y, dtype=bool)
            wk = wmap[keep]
            return float(2.0 ** (float((wk * logY[keep]).sum()) / float(wk.sum())))

        metered_subject = meter_subject()
        used = meter
        if meter == "average":
            metered = float(2.0 ** logY.mean())
        elif meter == "median":
            metered = float(np.median(Y))
        elif meter == "center":
            metered = float(2.0 ** (float((wmap * logY).sum()) / float(wmap.sum())))
        elif meter == "face" and metered_face is not None:
            metered = metered_face
        elif meter in ("face", "focus") and metered_focus is not None:
            metered = metered_focus       # không thấy mặt -> đo ở chỗ bắt nét
            used = "focus"
        else:
            metered = metered_subject
            used = "subject"            # gồm cả trường hợp "face" mà không thấy mặt

        # màu trung bình vùng midtone (bỏ vùng cháy và vùng quá tối)
        m = (Y > 0.0025) & (Y < 0.80)
        if m.sum() < 64:
            m = np.ones_like(Y, dtype=bool)
        rgb_mean = [float(lin[..., c][m].mean()) + EPS for c in range(3)]

        # --- màu da thật: dùng lại chính các patch vừa đo ở trên ---
        face_rgb = None
        face_p95 = None
        da_chay_frac = None
        if face_patches:
            allpx = np.concatenate([p_[2] for p_ in face_patches], axis=0)
            face_rgb = [float(allpx[:, c].mean()) + EPS for c in range(3)]
            #[[ Muc sang cua VUNG SANG tren da (p95 cua kenh lon nhat, thang
            #   sRGB 0-1). Day la cai quyet dinh da con chi tiet hay khong: tran,
            #   go ma, song mui cham tran truoc phan con lai.
            #
            #   metered_face_ev do dai 30-90% nen no la muc sang TRUNG BINH —
            #   mot khuon mat trung binh 150/255 van co the da co 30% pixel
            #   cham 240. Do tren 145 anh that: p95 bam do sang rat sat
            #   (tuong quan +0.958) va tach ro hai nhom — nhom an toan co p95
            #   trung vi 176, nhom nguoi dung che du sang co p95 248.
            #
            #   Chi DO va ghi lai o day. Viec dung no de ghim exposure nam o
            #   decide(), xem skin_hard_p95.
            #]]
            #   `allpx` la LINEAR (srgb_to_linear o tren), nen quy ve sRGB
            #   truoc khi luu: nguong 240/255 la con so nguoi doc hieu duoc,
            #   con 0.87 linear thi khong ai doi chieu duoc voi Photoshop.
            _p95_lin = float(np.quantile(allpx.max(axis=1), 0.95))
            face_p95 = float(_lin_to_srgb(_p95_lin))
            #[[ Ti le da CHAM TRAN tren preview (kenh lon nhat >= 250/255).
            #   p95 bao hoa o ~252-255 khi da da chay tren preview — luc do no
            #   khong con noi duoc chay NANG den dau. Ban quay 2/10: DSC08688
            #   p95 252, tool dim -0.65 ma user phai dim -1.32 ("da kha la chay,
            #   dim chua du"). Chi do va ghi lai; dung hay khong do decide() quyet.
            #]]
            da_chay_frac = float((allpx.max(axis=1) >= _srgb_to_lin_1(250.0 / 255.0)).mean())

        #[[ Độ "thẳng hàng" của khung: backdrop, màn LED, tường ốp gỗ đều có
        #   nhiều đường DỌC và NGANG mạnh, chạy dài suốt khung.
        #
        #   Đo bằng cách cộng gradient theo từng cột / từng hàng: cạnh của một
        #   đường thẳng dài sẽ dồn vào đúng một cột (hoặc hàng), tạo đỉnh nhọn.
        #   Ảnh ngoài trời, ảnh chân dung nền mờ thì gradient tản đều.
        #
        #   Dùng để quyết định có bật Upright hay không — chỉ ảnh có đường thẳng
        #   rõ thì Lightroom mới tính perspective ra kết quả đúng.
        #]]
        gyv = np.abs(np.diff(Y, axis=0)).mean(axis=0)   # theo cột
        gxv = np.abs(np.diff(Y, axis=1)).mean(axis=1)   # theo hàng
        def _peakiness(v):
            if v.size < 8:
                return 0.0
            m = float(v.mean())
            return float(np.percentile(v, 98) / (m + EPS)) if m > EPS else 0.0
        straightness = float(max(_peakiness(gyv), _peakiness(gxv)))

        #[[ Chữ ký bối cảnh: ảnh thu về lưới 4x6 ô, mỗi ô lấy màu trung bình.
        #
        #   Dùng để nhận ra "cùng một khung cảnh": sân khấu, bàn tiệc, sảnh...
        #   Chụp cùng chỗ thì bố cục màu theo không gian gần như không đổi, dù
        #   người trong khung có di chuyển.
        #
        #   Lấy theo Ô chứ không lấy histogram cả ảnh: histogram giống nhau vẫn
        #   có thể là hai chỗ khác hẳn, còn bố cục không gian thì đặc trưng hơn
        #   nhiều. 4x6x3 = 72 số, rẻ cả khi tính lẫn khi truyền giữa tiến trình.
        #]]
        gh, gw = 4, 6
        sig = []
        hstep, wstep = max(1, h // gh), max(1, w // gw)
        for gy in range(gh):
            for gx in range(gw):
                cellv = a[gy * hstep:(gy + 1) * hstep,
                          gx * wstep:(gx + 1) * wstep]
                if cellv.size:
                    sig.extend(float(cellv[..., c].mean()) for c in range(3))
                else:
                    sig.extend((0.0, 0.0, 0.0))

        #[[ CHUẨN HOÁ: chia cho độ sáng trung bình của chính ảnh.
        #
        #   Không chuẩn hoá thì chữ ký lẫn cả độ sáng — mà độ sáng chính là thứ
        #   sắp đem đi cân, nên hai ảnh cùng chỗ chụp lệch phơi sáng sẽ bị coi
        #   là hai bối cảnh, còn hai chỗ khác nhau mà sáng ngang nhau lại bị coi
        #   là một. Gặp thật: hai ảnh khác hẳn bối cảnh chỉ lệch 0.11.
        #
        #   Sau chuẩn hoá, chữ ký mô tả BỐ CỤC và TƯƠNG QUAN MÀU — đúng thứ giữ
        #   nguyên khi chụp cùng một chỗ.
        #]]
        sig_a = np.asarray(sig, dtype=np.float64)
        m_ = float(sig_a.mean())
        if m_ > EPS:
            sig_a /= m_
        sig = [float(v) for v in sig_a]
        eye_worst, eye_worst_area, eye_worst_score = _eye_worst(face_stats)

        out.update(
            ok=True,
            scene_sig=sig,
            straightness=straightness,
            face_rel_area=(100.0 * max((f[2] * f[3] for f in faces), default=0.0)
                           / float(max(fw_ * fh_, 1))) if faces else 0.0,
            eye_open=best_eye,
            face_sharp=best_sharp,
            # Thong ke tren MOI khuon mat — xem face_stats o tren
            eye_open_min=eye_worst,
            # Dien tich / diem tin cay CUA CHINH khuon mat cho ra eye_open_min
            eye_min_area=eye_worst_area,
            eye_min_score=eye_worst_score,
            eyes_measured=sum(1 for f in face_stats if f["eye"] is not None),
            face_sharp_min=min([f["sharp"] for f in face_stats
                                if f["sharp"] is not None], default=None),
            face_area_min=min([f["area_pct"] for f in face_stats], default=None),
            face_score_min=min([f["score"] for f in face_stats], default=None),
            hist_y=_hist(logY).tolist(),
            hist_max=_hist(np.log2(Ymax + EPS)).tolist(),
            metered=metered,
            metered_ev=float(np.log2(metered + EPS)),
            sat_frac=sat_frac,
            bright_frac=bright_frac,
            # Chay sang RIENG tren vung chu the (mat + than) — xem cho tinh.
            subj_sat_frac=subj_sat,
            subj_bright_frac=subj_bright,
            crush_frac=crush_frac,
            p50=float(np.median(Y)),
            rgb_mean=rgb_mean,
            # Dem so mat THAT SU dung de do, khong phai so mat detect duoc:
            # mat nen da bi loai thi khong con anh huong gi toi ket qua.
            faces_n=len(face_patches) if face_patches else len(faces),
            faces_found=len(faces),
            face_rgb=face_rgb,
            # Muc sang vung sang cua da (sRGB 0-1). Phanh chong chay da doc no.
            face_p95=face_p95,
            meter_used=used,
            # Giữ cả hai thang đo: cảnh có ảnh thấy mặt lẫn ảnh không thấy thì
            # phải quy về cùng một thang mới so được với nhau (xem decide()).
            metered_face_ev=(float(np.log2(metered_face + EPS))
                             if metered_face is not None else None),
            metered_focus_ev=(float(np.log2(metered_focus + EPS))
                              if metered_focus is not None else None),
            metered_subject_ev=float(np.log2(metered_subject + EPS)),
            width=w, height=h,
            dt=parse_dt(tags, path).isoformat(),
            iso=tags.get("iso"),
            #[[ Tam giac phoi sang van duoc read_raw() doc san tu truoc, chi la
            #   truoc day bi bo di ngay dong sau. Giu lai: xem ev_anh_sang().
            #]]
            exposure_time=_rat(tags.get("exposure_time")),
            fnumber=_rat(tags.get("fnumber")),
            ev_sang=ev_anh_sang(tags),
            model=tags.get("model", ""),
            # WB may da dung de render preview — xem T_SONY_WB_MODE
            wb_may_che_do=tags.get("wb_may_che_do"),
            wb_may_K=tags.get("wb_may_K"),
            wb_may_rb=tags.get("wb_may_rb"),
            da_chay_frac=da_chay_frac,
        )
    except Exception as ex:  # pragma: no cover - phòng file lỗi
        out["error"] = f"{type(ex).__name__}: {ex}"
    return out


def _measure_star(args):
    return measure(Path(args[0]), *args[1:])


# ======================================================================
# 3. Đọc / ghi sidecar .xmp (giữ nguyên phần preset, chỉ sửa field tone)
# ======================================================================

CRS_NS = "http://ns.adobe.com/camera-raw-settings/1.0/"

# Namespace riêng để lưu giá trị gốc của preset. Nhờ nó, chạy script lần 2, 3...
# vẫn tính từ baseline preset chứ không cộng dồn lên kết quả lần chạy trước.
ATN_NS = "http://saymedia.vn/ns/autotone/1.0/"
ATN_PREFIX = "atn"
ATN_FIELDS = {"Exposure2012": "BaseExposure", "Highlights2012": "BaseHighlights",
              "Shadows2012": "BaseShadows", "Temperature": "BaseTemperature",
              "Tint": "BaseTint",
              # 4 nui parametric curve — cung phai nho moc, khong thi chay lai
              # lan 2 se cong don len ket qua lan 1
              "ParametricHighlights": "BaseHighlights_P",
              "ParametricLights": "BaseLights_P",
              "ParametricDarks": "BaseDarks_P",
              "ParametricShadows": "BaseShadows_P",
              #[[ Color Grading: 8/10 tool CONG VECTO vao banh xe preset (xem
              #   grade_theo_trang_thai) nen can moc ca Hue — truoc chi moc Sat
              #   vi Hue bi ghi de thang 350. Them banh xe highlight. ]]
              "ColorGradeMidtoneSat": "BaseGradeMidSat",
              "ColorGradeMidtoneHue": "BaseGradeMidHue",
              "SplitToningHighlightHue": "BaseGradeHiHue",
              "SplitToningHighlightSaturation": "BaseGradeHiSat"}


def sidecar_for(raw: Path) -> Path | None:
    """Lightroom ghi NAME.xmp; một số công cụ ghi NAME.ARW.xmp."""
    for c in (raw.with_suffix(".xmp"), Path(str(raw) + ".xmp"),
              raw.with_suffix(".XMP"), Path(str(raw) + ".XMP")):
        if c.exists():
            return c
    return None


def read_ns(text: str, prefix: str) -> dict:
    """Đọc mọi field của một namespace — hỗ trợ cả dạng attribute lẫn dạng element."""
    d = {}
    for m in re.finditer(prefix + r':([A-Za-z0-9_]+)\s*=\s*"([^"]*)"', text):
        d[m.group(1)] = m.group(2)
    for m in re.finditer(r"<" + prefix + r":([A-Za-z0-9_]+)>([^<]*)</" + prefix + r":\1>", text):
        d.setdefault(m.group(1), m.group(2))
    return d


def read_crs(text: str) -> dict:
    return read_ns(text, "crs")


def set_ns(text: str, prefix: str, key: str, value: str, ns_uri: str) -> str:
    """Ghi đè một field tại chỗ, giữ nguyên toàn bộ phần còn lại của file."""
    attr = re.compile(r"(" + prefix + r":" + re.escape(key) + r'\s*=\s*")([^"]*)(")')
    if attr.search(text):
        return attr.sub(lambda m: m.group(1) + value + m.group(3), text, count=1)

    elem = re.compile(r"(<" + prefix + r":" + re.escape(key) + r">)([^<]*)(</"
                      + prefix + r":" + re.escape(key) + r">)")
    if elem.search(text):
        return elem.sub(lambda m: m.group(1) + value + m.group(3), text, count=1)

    # chưa có field -> đảm bảo namespace đã khai báo, rồi chèn attribute mới
    ns_pat = r'xmlns:' + prefix + r'\s*=\s*"' + re.escape(ns_uri) + r'"'
    ns = re.search(ns_pat, text)
    if not ns:
        crs_ns = re.search(r'(\s*)xmlns:crs\s*=\s*"' + re.escape(CRS_NS) + r'"', text)
        if not crs_ns:
            raise ValueError("sidecar không có namespace crs — "
                             "có phải file do Lightroom ghi ra không?")
        indent = crs_ns.group(1) if crs_ns.group(1).startswith("\n") else "\n    "
        text = (text[:crs_ns.end()] + indent + f'xmlns:{prefix}="{ns_uri}"'
                + text[crs_ns.end():])
        ns = re.search(ns_pat, text)
    return text[:ns.end()] + f'\n   {prefix}:{key}="{value}"' + text[ns.end():]


def set_crs(text: str, key: str, value: str) -> str:
    return set_ns(text, "crs", key, value, CRS_NS)


def touch_metadata_date(text: str) -> str:
    now = datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
    now = now[:-2] + ":" + now[-2:]
    for key in ("xmp:MetadataDate", "xmp:ModifyDate"):
        pat = re.compile(r"(" + re.escape(key) + r'\s*=\s*")([^"]*)(")')
        if pat.search(text):
            text = pat.sub(lambda m: m.group(1) + now + m.group(3), text, count=1)
        else:
            pat2 = re.compile(r"(<" + re.escape(key) + r">)([^<]*)(</" + re.escape(key) + r">)")
            text = pat2.sub(lambda m: m.group(1) + now + m.group(3), text, count=1)
    return text


def fmt_f(v: float) -> str:
    return "0.00" if abs(v) < 0.005 else f"{v:+.2f}"


def fmt_i(v: int) -> str:
    v = int(round(v))
    return "0" if v == 0 else f"{v:+d}"


def get_f(crs: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(str(crs.get(key, default)).replace("+", ""))
    except (TypeError, ValueError):
        return default


# ======================================================================
# 4. Logic quyết định
# ======================================================================

DEFAULTS = {
    # Do theo mat thi "absolute" vua dua mat ve dung muc sang, vua tu dong dong
    # deu ca buoi (moi mat deu ve cung mot moc) — khong can "scene" nua.
    "mode": "absolute",       # absolute | scene | batch | hybrid
    "meter": "face",          # face | subject | center | average | median
    "face_px": 1024,          # canh dai anh dua vao bo nhan dien mat
    "face_score": 0.5,        # nguong tin cay cua YuNet
    # Vung bat net: lay bao nhieu phan tram o net nhat lam vung do sang
    "focus_quantile": 0.92,
    # Mat nam dung cho bat net thi tinh nang ky hon bao nhieu lan (0 = tat)
    "focus_face_gain": 2.0,
    #[[ Chon mat CHU THE theo diem bat net + kich thuoc.
    #
    #   Giu mat co trong so >= ti le nay so voi mat nang nhat, bo phan con lai.
    #   Trong so = dien tich x do tin cay x (1 + focus_face_gain x do net).
    #
    #   0.60: anh hoi thao 3 mat -> giu 1 mat chu the, bo 2 mat khan gia phia
    #   sau (truoc day chung chiem 47% trong so, keo phep do lech 0.91 EV).
    #   Anh nhom / anh tap the thi cac mat cung hang co trong so xap xi nhau
    #   nen van giu het — dung y, luc do ca nhom deu la chu the.
    #   0 = tat, gop trung binh moi mat nhu truoc.
    #]]
    "subject_keep": 0.60,
    # Bo mat toi hon mat chinh qua bay nhieu EV (chi mot chieu, xem measure()).
    # Hai nguoi cung duoc chieu sang khong the chenh nhau vai EV.
    "subject_dark_ev": 2.0,
    # Chi giu mat co dien tich >= ti le nay so voi mat LON NHAT (0 = tat).
    # MAC DINH TAT: da thu 0.25 tren 120 anh that — khong cuu duoc anh nao ma
    # lam 5 anh nhieu nguoi bi toi di, vi loai nham mat that o hang sau. Chu the
    # bi toi la do phep chong chay sang, khong phai do mat tren man LED; xem
    # hl_subject_floor_ev. Chi bat khi that su chup nhieu poster/man hinh co mat.
    "face_min_ratio": 0.0,
    #[[ Diem tin cay toi thieu de mot khung duoc coi la mat dung duoc.
    #   DA BI BAC BO bang nhan tay cua nguoi dung — xem chu thich day du
    #   "CHOT CHAN BAO MAT AO" trong measure(). Dai diem cua khung xau va khung
    #   tot trung nhau (0.50-0.80 ca hai), khong nguong nao tach duoc.
    #   GIU LAI DE CON DO DAC, KHONG BAT. Dung tu y doi thanh so khac.
    #]]
    "face_min_score_sub": 0.0,
    #[[ Bo khung VUA diem thap VUA to bat thuong — xem chu thich trong measure()
    #   ("BO KHUNG VUA DIEM THAP VUA TO"). mat_ao_to_pct = 0 la TAT.
    #   Gap that 3/10: HIU02258 (anh can co tay, khong co mat) bi YuNet bao mot
    #   "mat" diem 0.50 chiem 40% khung -> -1.31 trong khi tam ben canh 0.00.
    #   15 (% khung) / 0.6 (diem): tren 40.521 khung mat cua TrainTool + 2609
    #   khong khung nao trung ca hai dieu kien -> hai buoi da duyet KHONG doi mot
    #   anh nao (cong B 0%). BAT 3/10.
    #]]
    "mat_ao_to_pct": 15.0,
    "mat_ao_diem": 0.6,
    #[[ Bo khung TO ma DIEM THAP khi trong anh co khung nho hon ma diem cao han
    #   han. Xem chu thich day du trong measure(). 0 = TAT.
    #   DA KIEM TREN 893 ANH DA DUYET — BAT MAC DINH ngay 31.08.2026.
    #   Chay day du hai luot phan tich tren ca 1464 anh buoi 1308 (kiem_luat.py):
    #     Cong 1  anh da duyet bi xe dich qua 0.30 EV:  1/893 = 0.11%
    #             (cong cho phep duoi 2%). O nguong 0.50 EV thi 0/893.
    #             Anh duy nhat bi dong la SAY02338 — chinh la anh dang do sang
    #             tren hop nhua, tuc luat sua dung chu khong pha.
    #     Cong 2  185 anh nguoi dung sua tay: keo LAI GAN 1 anh, day RA XA 0 anh.
    #             DSC01303 tu -0.31 ve -0.57, nguoi dung chon -0.87 -> gan hon
    #             0.26 EV.
    #   Tren toan bo 1464 anh chi 5 anh doi ket qua (0.3%). Luat rat it khi ban,
    #   nen loi ich nho — nhung khi ban thi ban dung, va khong pha gi.
    #]]
    "big_low_ratio": 3.0,
    "big_low_gap": 0.13,
    "big_low_floor": 0.70,   # diem tu day tro len thi khong bao gio bi bo
    #[[ Chay lai mot buoi: anh nguoi dung da chinh tay thi BO QUA, khong ghi de.
    #   Xem chu thich day du o danh_dau_nguoi_sua(). Dat False la quay lai hanh
    #   vi cu (ghi de tat ca) — chi dung khi co y muon lam lai tu dau.
    #]]
    "bo_qua_nguoi_sua": True,
    # Muc sang dich cho khuon mat (log2 linear) khi dung mode absolute/hybrid.
    # Hiệu chỉnh từ ví dụ thật của người dùng: ảnh có da mặt đo được -1.54 EV
    # thì họ muốn Exposure +0.35 -> mốc = -1.54 + 0.35. Xem --calibrate.
    #[[ 4/10: -1.19 -> -1.00 THEO USER: "Do da co tinh nang bu sang ca buoi nen
    #   an di phan Mat sang toi muc di. Co the set phan mat sang toi muc ve
    #   -1.00". O "Mat sang toi muc" da AN khoi giao dien; chinh sang tung buoi
    #   bang "Bu sang ca buoi". Giao dien lay so nay tu DEFAULTS (ca gu.json neu
    #   co) — khong con ghi cung -1.19 o bon cho nhu truoc.
    #   SO DO CU DE DOI CHIEU: buoi CUOI TrainTool / 2609 user sua tay trung vi
    #   -0.09 / -0.13 EV so voi moc -1.19 (tuc TOI hon). Nen voi -1.00 anh cuoi
    #   khong bi phanh se sang hon toi da ~0.19 EV — thay du sang thi dat "Bu
    #   sang ca buoi" am (vd -0.20). ]]
    "face_target_ev": -1.00,
    #[[ BU SANG CA BUOI (EV) — cong vao delta CUOI CUNG cua moi anh co mat, SAU
    #   moi phanh chong chay va san phang canh. 0 = TAT (y het cu).
    #   Giao dien dat qua o "Loai buoi": Cuoi = 0, Su kien = bu_sang_su_kien.
    #
    #   VI SAO (3/10, buoi su kien G:\1005, 630 anh, quy trinh preset moi): user
    #   xem tan mat va noi "anh hoi toi, can sang them mot chut". 38 anh user
    #   sua = 10 quyet dinh doc lap (sync theo nhom): 9 TANG, 1 giam (kem ha
    #   Temp); trung vi theo nhom +0.30 EV. Tool dat mat dung dich -1.19 (delta
    #   trung vi 0.00) — nen khong phai do sai.
    #   VI SAO KHONG DOI face_target_ev: (1) buoi CUOI thi nguoc lai — TrainTool
    #   219 anh sua trung vi -0.09, 2609 688 anh -0.13, anh den cung -0.14 /
    #   -0.10 — doi moc chung la lam hong ca hai buoi da duyet; (2) tren 1005 co
    #   287/630 anh do PHANH CHONG CHAY quyet dinh chu khong phai moc, doi moc
    #   -1.19 -> -0.95 thi nua so anh dung yen, trong khi user tang ca nhung
    #   anh bi phanh (DSC00004-08 +0.2..+0.44, DSC00009-14 +0.25..+0.34).
    #   Bu SAU phanh lam dung viec user tu tay lam.
    #   (4/10: user tu chot moc -1.00 va an o "Mat sang toi muc" — xem
    #   face_target_ev ngay tren. Ly do (1)(2) o day la so do luc moc con -1.19.)
    #   Anh KHONG co mat (giu_nguyen_exposure) khong bu: luat "khong mat thi
    #   khong chinh" giu nguyen. Van ton tran max_ev_up / max_ev.
    #   +0.30 MOI DO TREN MOT BUOI (trong mau) — can them buoi su kien de chot.
    #]]
    "bu_sang_ca_buoi": 0.0,
    "bu_sang_su_kien": 0.30,
    #[[ LOAI BUOI "KY YEU" (8/10) — hoc tu 564 anh nguoi dung tu sua (AnhKyTest)
    #   so voi CHINH anh Lightroom ve ban v41 (1088 preview 2048px, buoi raw 19.4):
    #     mat anh duyet sang hon LR: trong nha +0.24, ngoai troi +0.29 EV
    #     phan vi do sang (log2) anh duyet - LR:
    #        p1 -0.52  p5 -0.11  p10 +0.09  p25 +0.38  p50 +0.48  p75 +0.30
    #        p90 +0.12  p95 +0.06  p99 +0.03
    #   = trung tinh sang hon, vung sang giu, DEN SAU hon. Bu Exposure +0.25 (he
    #   so Exposure do tren chinh 1088 anh: p50 x1.35, p90 x1.0, p99 x0.37) con
    #   thieu: den -0.5..-0.75 (p1), sang -0.1..-0.2 (p90-p95), duoi trung tinh
    #   +0.1..+0.15 (p25) -> nen tone ky yeu: Blacks -30 (SAY -18), Highlights
    #   nen 1 (SAY 16, tuc -15), va KHONG ep Darks (duong S chi con Lights).
    #   Tone nen chi ap khi preset bo trong Basic Tone (nen_cho_anh) — preset
    #   co tone rieng thi ton trong preset. ]]
    #[[ VONG 3 (8/10 chieu, v42 tat Color Grading, 1087 anh LR ve that so 564
    #   anh duyet). Mat khop (trung vi 0.00) TRU 193 anh fisheye duoi den am
    #   (xem phanh_da_san_ky_yeu). Nhom 440 anh Shadows nen 16 (khong bi mo toi):
    #     p1 -0.30  p10 +0.22  p25 +0.30  p50 +0.22  p90 +0.04
    #   -> Shadows nen 16 -> 28, Darks duong S +c (cung Lights), Blacks -30 ->
    #   -40 (v41 -> v42 Blacks -12 ha p1 ~0.3 EV sau khi tru phan +0.25 EV).
    #   Buoc CHUA kiem tren LR ve that — vong 4 kiem. ]]
    "bu_sang_ky_yeu": 0.25,
    "nen_tone_ky_yeu": {"Contrast2012": 5, "Highlights2012": 1, "Shadows2012": 28,
                        "Whites2012": -25, "Blacks2012": -40},
    #[[ Ky yeu: phanh da (skin_hard_p95) khong giu mat TOI DUOI DICH qua muc nay
    #   (EV). Phanh van chan phan VUOT dich. Chi loai_buoi "ky_yeu"; 0 = nhu cu.
    #   Xem cho dung trong decide() (PHANH RIENG CHO DA). ]]
    "phanh_da_san_ky_yeu": 0.6,
    #[[ Ky yeu "den sau": KHONG tu mo vung toi (Shadows sh_adj, Parametric
    #   Shadows cv_sh). 122 anh fisheye canh toi (raw 19.4) tool mo Shadows
    #   +47 / ParametricShadows +35; anh duyet TOI HON LR o p10 0.5-0.8 EV du
    #   mat sang hon +0.56 EV — user giu den sau, dua mat len bang Exposure.
    #   True = mo toi nhu buoi thuong. ]]
    "mo_toi_ky_yeu": False,
    #[[ Ky yeu: lech WB phong cach cong SAU cung (K, Tint). Do tren pixel TRUNG
    #   TINH (OkLab C < 0.025) — khong do tren da, vi da con lech rieng (hue
    #   -6 do, chroma x1.34: HSL/profile cua preset, WB keo theo se am ca khung
    #   — dung loi user vua bo Color Grading vi no). Anh duyet - LR v42:
    #     85mm  da +4.4e-3 db -0.4e-3 | fisheye den thuong da +4.5e-3 db -0.1e-3
    #     fisheye den am (WB dang kep tran 4000K) da +0.1e-3 db -0.6e-3
    #   1 Tint = (+0.51, -0.51)e-3, 100K = (+0.64, +2.56)e-3 -> +130 K, Tint +7.
    #   Bo qua anh WB dang cham tran wb_temp_max (den mau nang: khong can). Tu
    #   8/10 dem ap ca khi bat Color Grading (WB khong doi theo o do nua).
    #
    #   VONG 4 (v43 ve that): Tint +7 -> +3. User nhin: "tint tang hoi qua tay".
    #   So voi anh duyet: trung tinh / da / ca khung van IT hong hon anh duyet,
    #   NHUNG vung xanh duong (dai sash, ao) anh duyet day han sang xanh ngoc
    #   (OkLab a -39e-3) con LR v42 -31, v43 -26 — Tint +7 keo xanh duong ngả
    #   TIM, xa anh duyet them. Xanh la cung xa them 1.6 do. Do la HSL / hieu
    #   chuan cua preset (Blue -> Aqua), WB khong lam duoc ca hai. Chon +3: tim
    #   bot, giu mot phan hong cho da. ]]
    "wb_bu_ky_yeu": {"Temperature": 130, "Tint": 3},
    #[[ Canh WB keo lanh >= ti le nay cua wb_temp_max (trung vi canh) = den vang
    #   nang. Ky yeu: khong cong Tint duong theo da (_tint_tran_am), khong cong WB
    #   ky yeu, bu sang them (_bu_sang_canh_am). 0 = TAT. ]]
    "wb_tran_am_ti_le": 0.85,
    #[[ Ky yeu, canh am nang: bu sang them (EV) vi Lightroom ve mat o do toi hon
    #   preview may ~0.7 EV — xem _bu_sang_canh_am(). 0 = TAT. ]]
    "bu_sang_canh_am_ky_yeu": 0.5,
    "bu_sang_canh_am_tran": 1.0,        # anh da keo >= muc nay thi khong bu them
    #[[ HSL KENH DA (vong 5, user: "chi can thiep vao kenh mau sac to cua da do
    #   duoc — thuong la Orange"). Xem hsl_da_theo_trang_thai().
    #
    #   VI SAO HSL (8/10 toi): anh hoan thien CUNG KHUNG voi preview LR (562/564 cap,
    #   tuong quan do sang 0.991) nen so duoc TUNG DIEM ANH (3.9 trieu diem). Anh
    #   hoan thien doi THEO DAI MAU — cam xoay ve do 5-9 do va dam x1.15-1.25, vang
    #   giu, xanh duong sang xanh ngoc — con trung tinh gan nhu dung yen: dau van tay
    #   cua HSL, khong phai WB. Khop Orange (hue + sat) hang so tren WB v44: lech mau
    #   da trung binh moi anh 15.3 -> 5.3 (OkLab x1000), vat cam / do khac khong xau
    #   di (do 7.7 -> 5.5). WB keo theo da (+437 K / +16) cung dat ~4.6 nhung trang
    #   am hong ~9e-3. Theo TUNG anh (dich hue - hue du doan) KHONG tot hon hang so
    #   (5.6 vs 5.3, mo hinh hue +-2 do) -> MOT muc cho ca buoi, tinh tu trung vi.
    #
    #   Chroma du doan (da_trong_lr, KHONG mo hinh HSL cua preset — anh huong cua
    #   no nam san trong he so nay) DAM hon LR that: ti so LR / du doan 0.56..0.60;
    #   do lai 8/10 dem tren 874 anh LR v43 o WB v46: 0.60 cho ti so 1.00.
    #
    #   v46 "DA DO HAN" (8/10 dem): preset cua user CO HSL (Red -5/-25, Orange
    #   -3/-35, Yellow 0/-45 — truoc v45 plugin khong xuat nen tool khong biet). v46
    #   mo hinh LAI HSL do trong du doan, trong khi he so chroma 0.60 da gom san no
    #   -> tru hai lan -> tool tuong da nhat 35% -> Sat cham tran +50 (ghi Orange
    #   -36/+15), Hue -33. Do v43 -> v46 tung diem anh (tru phan WB doi): DA hue
    #   -13.8 do OkLab, chroma x1.72, L -0.022 cho Hue -33 / Sat +50. Ket qua da
    #   30.3 do / chroma 0.077 vs anh mau 36.7 / 0.058: do han, dam hon 32%.
    #   Nay: KHONG mo hinh HSL preset (nam trong 0.60), quy doi lay THANG tu phan
    #   ung do tren da: 0.418 do OkLab / diem Hue, ln(chroma) 0.01085 / diem Sat.
    #   Dich hue = hue da anh mau DO TUNG DIEM (trong 36.9, ngoai 36.5) — dich
    #   skin_dich_hong (34.4) do hon 2.5 do. Mo hinh doan hue da DO hon LR that
    #   1.3 do (874 anh) -> bu. ]]
    #[[ TAT tu 8/10 dem (v47 -> v48), user: "can thiep HSL khong kha quan, da van
    #   am do; khong dua ve trang duoc thi bo qua". Do 468 anh LR v47 khop tung diem:
    #   da TRUNG BINH da trung anh mau (hue 34.6 vs 36.6, chroma 0.059 vs 0.058, L
    #   0.738 vs 0.748; lech 13.5 -> 5.7) — nhung mat user van thay do. Chua rõ vi
    #   sao: gia thuyet "anh mau da deu mau hon sau retouch" KHONG duoc so do tho ung
    #   ho (IQR hue trong khung mat: mau 6.0 vs LR 5.4 do). Khop mau trung binh khong
    #   bang khop cam nhan — can user cham vai anh cu the truoc khi thu lai.
    #   Tat thi lan ghi sau TRA HSL ve so goc cua preset (anh_da_hsl). Code giu de
    #   bat lai khi co cach do "da deu mau". ]]
    "hsl_da_ky_yeu": False,
    "hsl_da_k_hue": 0.418,        # do hue OkLab cua DA cho moi diem Hue o dai da
    "hsl_da_k_sat": 0.01085,      # ln(chroma) cua DA cho moi diem Saturation o dai da
    "hsl_da_dich_hue": 36.7,      # hue OkLab da anh mau (do), 0 = lay tu skin_dich_hong
    "hsl_da_hue_bu": 1.3,         # cong vao hue da du doan (mo hinh doan do hon LR)
    "hsl_da_chroma_lr": 0.60,     # chroma da LR that / du doan cua da_trong_lr
    "hsl_da_hue_max": 40,
    "hsl_da_sat_max": 30,
    "hsl_da_min_anh": 5,          # it hon so anh co mat nay thi khong chinh
    #[[ PHANH RIENG CHO DA: tran do sang vung sang cua khuon mat (sRGB 0-255).
    #
    #   Phanh hl_hard_pct san co nhin CA KHUNG. No khong cuu duoc truong hop
    #   hay gap nhat o anh su kien ngoai troi: nen cay coi con toi nen tong
    #   muc chay ca khung van thap, trong khi DA MAT da cham tran va mat het
    #   chi tiet o tran, go ma.
    #
    #   Do tren 145 anh that cua nguoi dung:
    #     nhom an toan (da cham 240 duoi 5%) : p95 trung vi 176, cao nhat 230
    #     nhom nguoi dung che du sang        : p95 trung vi 248
    #   Hai nhom tach ro, nen mot tran quanh 235-240 chan dung phan du sang
    #   ma khong dung toi anh dang binh thuong.
    #
    #   CHOT 232 SAU KHI CHAY THAT tren 734 anh co sidecar (buoi 3005):
    #     tran 238 -> 179 anh con p95 > 235
    #     tran 232 ->   2 anh
    #     tran 228 ->   2 anh  (ha tiep khong sua them anh nao, chi lam toi di)
    #   Nguoi dung xem 3 anh o muc 238 va noi "hoi du sang mot chut xiu" —
    #   dung voi cho nhay cua bang tren. So anh bi keo toi qua (<160) khong
    #   doi o moi muc, nen ha tran khong lam anh nao toi oan.
    #
    #   0 = tat phanh nay.
    #]]
    "skin_hard_p95": 232.0,
    #[[ DO SANG THEO VUNG DA SANG khi vung do du lon.
    #
    #   hl_da_muc   : tu muc sRGB nay tro len coi la "da sang" (0-255)
    #   hl_da_ti_le : vung sang chiem tu bao nhieu % vung da thi chuyen sang
    #                 do rieng no. 0 = tat.
    #
    #   Xem chu thich day du trong measure(). Do tren 145 anh: nguong 220 tach
    #   sach hai nhom (p95 trung vi 248 vs 178), va 30% la cho cat tu nhien.
    #]]
    "hl_da_muc": 220.0,
    "hl_da_ti_le": 30.0,
    #[[ Tran chay sang MOI SINH RA tren vung chu the (mat + than), tinh %.
    #
    #   Bo sung cho hl_hard_pct (nhin ca khung) va skin_hard_p95 (nhin rieng
    #   da mat). Ao chu the nam giua hai cai do: sang hon da nhung chi chiem
    #   vai % khung. Xem chu thich day du trong decide().
    #
    #   0 = tat.
    #]]
    "subj_hard_pct": 6.0,
    #[[ Anh khong co khuon mat nao thi GIU NGUYEN Exposure.
    #
    #   Anh khong gian, decor, bang ron... khong co chu the de can, ma moc
    #   face_target_ev lai danh rieng cho da mat. Xem chu thich day du trong
    #   decide(). False = quay lai hanh vi cu (van chinh theo phep do ca khung).
    #]]
    "giu_anh_khong_mat": True,
    # "subject" bo pixel sang tren phan vi nay truoc khi do — chan man LED,
    # cua so, den san khau keo lech phep do
    "meter_highlight_cut": 0.85,
    "target_ev": -2.6,        # ~0.165 linear — chỉ dùng cho absolute/hybrid
    "blend": 0.5,             # hybrid: trọng số kéo về target tuyệt đối
    "gap_minutes": 5.0,
    #[[ Tach canh theo BOI CANH khung hinh, khong chi theo thoi gian.
    #
    #   Anh su kien chup lien tuc nen khoang cach thoi gian khong bao gio vuot
    #   nguong -> ca buoi don vao mot "canh" du da doi phong, doi san khau.
    #
    #   Do that tren 350 anh, bien do sang TRONG cung mot canh:
    #     chi thoi gian : 2.52 EV (canh lon nhat 87 anh)
    #     them boi canh : 0.85 EV (canh lon nhat 28 anh)
    #   Cang nho cang tot — cung mot cho thi phai ra cung mot muc sang.
    #
    #   0 = tat, chi tach theo thoi gian nhu cu.
    #]]
    "scene_sig_thresh": 0.30,
    # Phai lech lien tuc bay nhieu khung moi coi la doi boi canh (mot khung can
    # canh hay nguoi di ngang khong tinh).
    "scene_sig_min_shots": 3,
    #[[ Nhat cat theo thoi gian chi tinh khi chu ky khung hinh cung doi.
    #   Chi co tac dung khi scene_sig_thresh > 0. Xem group_scenes().
    #]]
    "scene_gap_can_sig": True,
    #[[ San phang KET QUA trong cung mot canh (0 = tat, 1 = san hoan toan).
    #
    #   Khac voi viec nham chung mot muc dich: nhieu anh bi chan giua chung
    #   (tran EV, chong chay sang, san chu the) nen dung o cac muc khac nhau.
    #   Buoc nay keo not phan con lai ve trung vi cua canh, ca sang lan mau.
    #
    #   0.7 = keo 70% quang duong con lai; 1.0 = dong bo hoan toan.
    #]]
    #   1.0 = dong bo TUYET DOI. Do that: lech hl_adj 23.6 -> 0, gr_sat 4.3 ->
    #   0, ma do sang trong canh khong xau di (0.34 EV, y het muc 0.7). Anh
    #   cung mot khung phai ra cung mot mau — do moi la muc dich.
    "scene_level": 1.0,
    "scene_level_min": 4,      # canh it hon bay nhieu anh thi khong san
    #[[ CHOT NAY DA BI SO LIEU BAC BO — de 99 tuc la TAT.
    #
    #   Y tuong: san phang khong duoc day anh ra xa dich hon luc chua san.
    #   Chay tren buoi 1308 (1464 anh, kiem_san.py) ngay 2/9:
    #
    #     Cong B  31/1279 anh da duyet xe dich qua 0.30 EV = 2.42%  (cong: <2%)
    #     Cong A  185 anh co dich dung: keo lai gan 3, day ra xa 11
    #             sai trung binh 0.473 -> 0.471 EV, tuc khong doi gi
    #
    #   Ca 149 anh bi dong deu bi keo LEN, khong anh nao keo xuong — dung chu
    #   ky cua chot. Ca biet SAY02955 nhay 1.85 EV (canh chi 4 anh).
    #
    #   Vi sao sai: chot phat bieu "dich luon dung hon su dong deu". Nhung san
    #   phang sinh ra chinh vi trong mot canh, dong deu doi khi dang gia hon
    #   viec tung tam bam sat dich. Tren 185 anh biet dich dung, chot day ra xa
    #   nhieu gap ba lan keo lai gan. Do la loi cua Y TUONG, khong phai cua
    #   tham so — nen khong chinh so cho vua cong.
    #
    #   Giu lai ma nguon va so do de khong ai thu lai lan nua ma khong co bang
    #   chung moi. >= 10 la tat han (khong khoang cach nao vuot noi).
    #]]
    "scene_aim_slack_ev": 99.0,
    #[[ MOC CANH CHI TINH TREN ANH KHONG BI GHIM — thay cho chot tren.
    #
    #   Chan doan that o buoi 0306, canh 3 (11 anh): 9 anh mang co
    #   "ha-vi-chay-sang", dung o -1.83 trong khi dich la -1.19. Muc do KHONG
    #   phai muc dung cua canh, do la muc chung KHONG THE vuot qua. Lay trung
    #   vi ca canh thi moc thanh -1.83, va san phang keo not hai anh khoe manh
    #   xuong theo: SAY09660 tu delta +0.48 (nguoi dung tu chinh +0.44) thanh
    #   -0.16, sai 0.64 EV vi ly do cua anh khac.
    #
    #   Khac cho voi chot da bi bac bo: cho nay sua MOC, khong chan tung anh.
    #   San phang van chay day du, van keo moi anh ve moc — chi la moc gio do
    #   nhung anh THUC SU toi duoc dich dinh ra, khong phai nhung anh bi chan.
    #
    #   Canh khong co anh nao bi ghim thi hai cach ra y het nhau, nen dai da so
    #   anh khong he bi dong toi. Do la khac biet quan trong nhat so voi chot cu
    #   (chot cu dong toi 149 anh o buoi 1308).
    #
    #   Bao nhieu anh "tu do" thi du de dinh moc: anh khong bi ghim thi theo dung
    #   dinh nghia da toi dich, nen trung vi cua chung gan nhu luon bang dich.
    #   Vi vay khong can nhieu. 0 = TAT, tro ve lay trung vi ca canh.
    #
    #   DE 0 (TAT) CHO TOI KHI QUA CONG. Chinh luat cua du an nay: khong bat
    #   thu gi truoc khi no dat cong tren anh nguoi dung da duyet. Chot truoc
    #   do ("khong duoc day ra xa dich") da bi bac bo o buoi 1308 dung vi loai
    #   ly le nay — nghe hop ly nhung so do noi nguoc lai.
    #
    #   Bat len bang cach chay cong, dat thi ghi vao gu.json:
    #     python kiem_gu.py G:\1308 --de-xuat de_xuat_moc_canh.json --ghi-gu
    #]]
    "scene_aim_free_min": 0,
    # Khi san phang trong canh, cho phep vuot tran max_ev them bay nhieu EV.
    # Can thiet vi tran dat cho TUNG anh, con o day muc dich la MOI ANH GIONG
    # NHAU — giu tran cung se chan dung viec dong bo. 0 = khong noi.
    "scene_level_extra_ev": 0.75,
    #[[ MAT DO LECH KHOI KHUNG — 0 = TAT (mac dinh, cho qua cong).
    #
    #   Gap that 29/9, buoi HPC 25nam/TEST (88 anh): NDT09826 bi keo -0.87
    #   trong khi cac tam ke ben dung o -0.19..-0.33. KHONG he bi tach canh
    #   (canh 0, 34 anh), khong doi thong so may (f/2.8, 1/200, ISO 320 ca
    #   loat). Do sang CA KHUNG cung khop hang xom (chu the -1.83, hang xom
    #   -1.71..-1.95). Chi rieng phep do MAT nhay len -0.51 trong khi hang xom
    #   -1.05..-1.19 — mat do nham, anh sang khong he doi.
    #
    #   Cach bat: trong mot loat CUNG canh, CUNG than may, CUNG khau/toc/ISO,
    #   so voi cac tam chup ngay truoc/sau (trung vi hang xom):
    #     - do sang KHUNG gan nhu y nguyen  (lech <= mat_lech_khung_khung_ev)
    #     - ma do sang MAT nhay xa          (lech >  mat_lech_khung_ev)
    #   thi phep do mat bi coi la hong. Mat duoc suy tu do sang khung cua chinh
    #   tam do + khoang cach "mat - khung" cua hang xom — y het cach decide()
    #   von lam voi anh khong thay mat.
    #
    #   PHAI CO DIEU KIEN KHUNG. Ban dau chi so khoang cach "mat - khung": tren
    #   canh 1 cua buoi TEST (san khau, doi co anh lien tuc) no bat nham 17
    #   tam, co tam bi day tu -0.37 xuong -1.16 — NDT09852 mat do DUNG bang
    #   hang xom (-1.07 vs -1.02..-1.07), chi co khung doi vi doi co anh.
    #   Khung doi thi khoang cach doi theo, khong noi gi ve phep do mat.
    #
    #   VA PHAI CUNG BO CUC. Them dieu kien do sang khung roi van con 12 tam bi
    #   bat, trong do NDT09869 bi day +0.45 -> -0.45 trong khi NDT09870 — chup
    #   lien sau, y het khung, mat do y het (-2.55 / -2.56) — dung yen o +0.45.
    #   Tuc ban sua tu tao ra dung benh no dinh chua. Ly do: hang xom theo thoi
    #   gian la mot dan vu khac (bo cuc khac), do sang khung trung nhau chi la
    #   tinh co. Nen hang xom chi tinh nhung tam co chu ky khung (scene_sig)
    #   cach tam dang xet <= mat_lech_khung_bo_cuc. Do tren buoi TEST: cung mot
    #   bo cuc 0.01-0.07, doi goc/doi nguoi 0.13 tro len.
    #
    #   KHONG so rieng thong so may: chup manual thi den san khau doi ma thong
    #   so khong doi. Da thu "cung thong so thi cung Exposure" tren chinh buoi
    #   do: canh 1 (47 anh) bi san ve mot so trong khi do sang khung trai tu
    #   -0.81 toi -2.99 — sai. Nen phai so voi DO SANG KHUNG, khong so voi may.
    #
    #   mat_lech_khung_ke: xet bao nhieu tam moi ben.
    #   Can it nhat mat_lech_khung_min hang xom cung bo cuc moi dam ket luan.
    #
    #   DE 0 CHO TOI KHI QUA CONG tren anh da duyet:
    #     python kiem_gu.py G:\1308 --de-xuat de_xuat_mat_lech_khung.json --nhom do-nham-mat
    #]]
    "mat_lech_khung_ev": 0.0,
    #[[ RIENG ANH LENS CO (khong co khau trong EXIF — fisheye 10mm 8/10) — BAT.
    #
    #   Buoi ky yeu raw 19.4: 748/1089 anh chup fisheye 10mm khong tiep diem,
    #   EXIF khau = 0. Khoa "cung khau/toc/ISO" cua ham nay (va cua chia_loat)
    #   bo qua MOI anh do nen ca hai buoc chua chay. Ma fisheye la cho bo nhan
    #   mat hay bat nham nhat (mat meo, nho o ria khung): HUY04802-04804 do
    #   "mat" -3.25 / -2.70 / -2.82 EV trong khi tam ngay truoc / sau -0.54 /
    #   -0.87, khung y het (-3.27..-3.65), cung 1/200 ISO 500 -> tool day
    #   +0.70..+0.92 EV, hai ben -0.13..-0.46: nguoi dung thay "cung thong so
    #   ma sang toi khac nhau". Anh da duyet cua chinh nguoi dung: "mat" do
    #   duoc o cung cho van -3.55 / -2.77 / -3.13, tuc do nham mot vung toi,
    #   khong phai mat that.
    #
    #   Nguong 1.0 EV (gap 2.5 lan nguong hay gap o cac ca da xet): chi bat do
    #   nham THO. Anh lens thuong giu mat_lech_khung_ev (0 = tat) cho toi khi
    #   qua cong rieng. 0 = tat ca nhanh nay. ]]
    "mat_lech_khung_ev_lens_co": 1.0,
    "mat_lech_khung_khung_ev": 0.25,
    "mat_lech_khung_ke": 3,
    "mat_lech_khung_bo_cuc": 0.10,
    "mat_lech_khung_min": 2,
    #[[ DONG BO LOAT CHUP (3/10) — CUNG KHUNG + CUNG THONG SO -> CUNG MOT KET QUA.
    #   Xem dong_bo_loat(). Ba nguong lay lai dung cac nguong da kiem cua
    #   sua_mat_lech_khung (bo cuc 0.10, khung 0.25 EV), dat TRUOC khi do.
    #
    #   BAT theo yeu cau cua user (3/10: "phai giai quyet dut diem"). Cong:
    #     TrainTool  A gan 158 / xa 108 (sai 0.186 -> 0.177)  B 1.41%  — DAT
    #     2609       A gan 218 / xa 169 (sai 0.193 -> 0.189)  B 7.10%  — B TRUOT
    #   B truot vi anh "da duyet" cua 2609 chua 94 loat ma user CHAP NHAN THU
    #   DONG do lech > 0.3 EV trong cung loat (khong sua tam nao trong loat) —
    #   dung loai lech user nay noi la khong chap nhan. So loat user CO Y de lech
    #   > 0.3 (co sua tay ma van de lech) bi luat ep: 2609 0, TrainTool 1.
    #   Khong noi nguong B; ghi lai de ai doc cung thay. User quyet bat.
    #]]
    "dong_bo_loat": True,
    "loat_bo_cuc": 0.10,       # chu ky khung lech toi da so voi tam DAU loat
    "loat_khung_ev": 0.25,     # do sang khung lech toi da so voi tam dau loat
    "loat_gio_s": 60.0,        # hai tam lien nhau cach toi da bay nhieu giay
    #[[ ===== NAM PHAN SUA TU HAI BAN QUAY 2/10/2026 (buoi TrainTool) =====
    #
    #   Cong 3/10: python kiem_2ban_quay.py (tren so do cua DO_BUOI.bat).
    #   Ket qua tung phan: CLAUDE.md, muc "Nam phan hoc tu 2 ban quay".
    #   Ghi chu day du: Claude outputs\TrainTool\GHI_CHU_HOC_2_BAN_QUAY.md
    #
    #   DANG BAT (3/10, user duyet tan mat Claude outputs\do\so_sanh_ung_vien.pdf,
    #   53 cap anh truoc/sau): khung_sang_pct 12 (muc 3a) va
    #   wb_tint_theo_may {"NIKON": -5} (muc 2b). Moi khoa con lai TAT — da
    #   truot cong, dung bat lai khi chua co bang chung moi.
    #
    #   MUC 1 — MOT ANH SANG MOT KET QUA (do_mat_theo_anh_sang).
    #   canh_ev100: hai tam cung canh + cung may, do sang KHUNG (quy EV100)
    #   lech <= bay nhieu EV thi coi la cung anh sang -> dung chung phep do mat
    #   (trung vi). 0 = TAT. canh_ev100_ke: xet bao nhieu tam moi ben theo gio
    #   chup. canh_ev100_min: can it nhat bay nhieu tam (ke ca chinh no).
    #   canh_ev100_tt: thong so may (EV100) hai tam lech qua bay nhieu EV thi
    #   KHONG gop — nguoi chup doi hon 1 stop la anh sang da doi.
    #]]
    "canh_ev100": 0.0,
    "canh_ev100_ke": 8,
    "canh_ev100_min": 3,
    "canh_ev100_tt": 1.0,
    #[[ MUC 2 — WB THEO DU LIEU MAY + THEO THAN MAY.
    #   wb_theo_may_pull: catalog khong co AsShot -> keo Temp ve nhiet do may
    #     da dung render preview (Sony 0xb021 dat tay, Nikon 0x004F tu do),
    #     he so nhu wb_asshot_pull. 0 = TAT.
    #   wb_tint_theo_may: {"chuoi trong ten may": so Tint cong them}. {} = TAT.
    #   wb_san_theo_may: tinh mau da va san WB RIENG tung than may trong canh.
    #   da_vang_lech_ngoai: da AM HON mau dich ngoai troi qua bay nhieu stop
    #     log2(B/R) thi dung mau dich TRONG NHA cho tam do (den am chieu vao
    #     nguoi du canh sang). 0 = TAT.
    #]]
    "wb_theo_may_pull": 0.0,
    #[[ BAT 3/10. Cong: TrainTool Tint 57 sat / 0 xa (sai tb 5.6 -> 3.9);
    #   2609 user khong sua Tint tam Nikon nao (137 tam) nen cong khong do
    #   duoc — user nhin 10 tam Nikon 2609 truoc/sau va chon ban -5. ]]
    "wb_tint_theo_may": {"NIKON": -5},
    "wb_san_theo_may": False,
    "da_vang_lech_ngoai": 0.0,
    #[[ MUC 3 — KHUNG SANG / CHAY: tran da thap hon + phanh da hai chieu.
    #   khung_sang_pct: khung bao hoa (>=254) tu bay nhieu % thi tran da la
    #     khung_sang_tran_da thay cho skin_hard_p95. 0 = TAT.
    #   phanh_da_hai_chieu: trong khung chay do, da vuot tran thi KEO XUONG ca
    #     khi delta am. Khung khong chay thi khong lam gi (xem decide()).
    #]]
    #[[ BAT 3/10 (chi phan ha tran, KHONG kem phanh hai chieu). Cong: 2609
    #   A 17 sat / 2 xa, B 7/1774 = 0.39%; TrainTool A 43/22 nhung B 12/426 =
    #   2.82% (truot sat nguong 2%). User nhin ca 19 anh da duyet bi doi > 0.30
    #   EV + cac anh da sua, ket luan "deu oke". ]]
    "khung_sang_pct": 12.0,
    "khung_sang_tran_da": 210.0,
    "phanh_da_hai_chieu": False,
    #[[ MUC 4 — BU PHEP DO THEO THAN MAY: {"chuoi trong ten may": ev}. So
    #   duong = tool cho anh may do SANG HON bay nhieu EV. {} = TAT. So bu
    #   KHONG dat tay — hoc tren anh da duyet (kiem_2ban_quay.py in ra).
    #]]
    "bu_exp_theo_may": {},
    #[[ MUC 5 — AO/VAY TRANG: vung chu the >=242 chiem >= hl_ao_trang_pct %
    #   thi tran Highlights noi len hl_ao_trang_max. hl_ao_trang_max 0 = TAT.
    #]]
    "hl_ao_trang_pct": 15.0,
    "hl_ao_trang_max": 0,
    #[[ NHAN NGAY/DEN PHAI LECH DU BAY NHIEU KHUNG LIEN TIEP MOI TINH — 1 = TAT.
    #
    #   Nhan tinh bang EV100 cua tung tam so voi ev_ngoai_troi. Mot tam doi toc
    #   1/160 -> 1/200 giua mot loat la EV100 nhay qua nguong, va truoc day no
    #   (a) mo mot canh 1 anh (khong duoc san phang), (b) lay mau da dich cua
    #   nhom kia. Khung hinh khong doi gi ca.
    #
    #   Luat boi canh von da doi 3 khung lien tiep (scene_sig_min_shots) de mot
    #   nguoi di ngang khong cat vun canh. Day la cung y do cho nhan ngay/den:
    #   mot doan ngan hon N khung, ma HAI BEN cung mot nhan, thi theo hai ben.
    #   Doan o dau/cuoi buoi khong co hai ben de so nen giu nguyen.
    #
    #   DE 1 (TAT) CHO TOI KHI QUA CONG:
    #     python kiem_gu.py <buoi co ca ngay lan den> --de-xuat de_xuat_trong_ngoai.json
    #]]
    "trong_ngoai_min_shots": 1,
    #[[ Diem AF roi sat mat (co, co ao, toc sau gay) ma khong trung o mat nao
    #   -> lay mat gan nhat neu cach mep o mat <= bay nhieu lan canh o mat.
    #   0 = TAT. Xem chu thich trong measure(). DE 0 CHO TOI KHI QUA CONG:
    #     python kiem_gu.py G:\2609 --de-xuat de_xuat_af_gan.json
    #]]
    "af_gan_mat": 0.0,
    #[[ Xoay diem AF theo huong anh (anh chup doc). Sua loi toa do 29/9 — BAT.
    #   Chi de False khi chay CONG doi chung (kiem_gu --goc).
    #]]
    "af_xoay_theo_anh": True,
    #[[ Doc vung AF cua Nikon dong Z (AFInfo2 ban 0300/0301). BAT tu 29/9.
    #
    #   Cong tren G:\2609: A dat (nhung chi 7 anh Nikon co dich dung -> gan
    #   nhu khong do gi), B 1.25% tren ca buoi — con so bi pha loang boi 2800
    #   anh Sony khong doi; tinh rieng Nikon la 39/285 = 13.7% anh da duyet
    #   xe dich qua 0.30 EV. Vi vay KHONG bat theo so, ma dua nguoi dung xem
    #   tan mat ca 39 anh do (gu/2609/so_sanh_nikon_2609.pdf, cu vs moi, co
    #   khung mat va vung AF). Nguoi dung ket luan: diem bat net chuan va anh
    #   sang ban moi oke -> bat. Ban cu thuong do mat nho o hau canh.
    #]]
    "af_nikon": True,
    #[[ TINH NANG 1 — LOC ANH CHUP LIEN TIEP (burst / trung khung). 0 = tat.
    #
    #   Giu lai bao nhieu anh dep nhat moi POSE — khong phai moi loat. Anh
    #   check-in backdrop chup lien tuc nhung nguoi ta doi dang tay lien tuc;
    #   gom ca loat roi giu 2 anh se mat sach cac pose khac.
    #
    #   TINH NANG NAY KHONG PHAI LOC NHAM MAT. No chi so cac anh TRONG CUNG
    #   mot loat voi nhau roi giu 2 tam nhinh hon — khong tra loi cau hoi
    #   "nguoi trong anh co nham mat khong". Anh chup don le ma nham mat van
    #   lot qua; anh loat ma ai cung mo mat van bi cat bot. Ghi chu rieng:
    #   "loai-trong-loat", cot cull = "loat".
    #]]
    "burst": False,
    "burst_gap_sec": 3.0,       # cach nhau duoi bay nhieu giay thi cung mot loat
    "burst_pose_thresh": 0.12,  # doi bo cuc hon nguong nay = pose moi
    "burst_min": 3,             # loat it hon bay nhieu anh thi bo qua
    "burst_keep": 2,            # giu bao nhieu anh dep nhat moi pose
    "burst_reject_rating": 1,   # sao gan cho anh bi loai
    # Trong so cua do mo mat khi xep hang trong loat (con lai danh cho do net).
    # De rieng vi phep do mat chua duoc kiem chung — ha ve 0 la chi con xet net.
    "burst_eye_weight": 0.6,
    #[[ TINH NANG 2 — LOC ANH NHAM MAT. RIENG BIET, mac dinh TAT.
    #
    #   LUAT (nguoi dung dat ra): anh 1 nguoi, hoac nhom 2-4 nguoi, ma co
    #   NGUOI NAO nham mat -> loai. Anh tap the dong nguoi thi du 1-2 nguoi
    #   nham mat cung KHONG loai, vi ban chat anh tap the la nguoi nay nguoi
    #   kia. Nguong so nguoi: blink_max_faces.
    #
    #   VI SAO TACH KHOI LOC LOAT: hai viec khac nhau nen phai co hai cong
    #   tac, hai nhan ghi chu, hai cot rieng. Da tung suyt mac loi vi nhap
    #   lam mot: 377 anh 1 sao cua buoi 1308 la do LOC LOAT gan, khong phai
    #   nguoi dung cham nham mat — lay nhan do di kiem tra phep do nham mat
    #   la lap luan vong, tu kiem tra chinh minh.
    #
    #   DUNG PHEP DO NAO: EAR trong ear.csv do eye_ear.py sinh ra, KHONG dung
    #   eye_open_min cua autotone. Phep do cu da bi nhan that bac bo: 2 anh
    #   nham mat nguoi dung cham nam o hang 15 va 21 tren 34, tuc nua tren.
    #   EAR do vien mi that (MediaPipe FaceMesh, cat mat bang YuNet truoc) thi
    #   xep dung ca hai xuong day. Vi vay bo loc nay doc file rieng — khong co
    #   ear.csv thi no khong chay, chu khong am tham quay ve phep do cu.
    #
    #   NGUONG 0.12 O DAU RA: hieu chuan tren 93 nhan that buoi 1308 (40 anh
    #   EAR thap nhat cham DAY DU + 48 o trai deu trong dai 0.077-0.19 + 5 o
    #   chong lan). Trong 820 anh thuoc pham vi luat:
    #       nguong 0.10 -> loai 75 anh,  ~2 oan  (97% dung), bat ~43%
    #       nguong 0.12 -> loai 114 anh, ~5 oan  (95% dung), bat ~63%
    #       nguong 0.15 -> loai 146 anh, ~19 oan (87% dung), bat ~74%
    #       nguong 0.17 -> loai 173 anh, ~33 oan (81% dung), bat ~82%
    #   Chon 0.12 vi tren muc do ti le loai oan bat dau tang nhanh hon phan
    #   bat them duoc. "Bat duoc" tinh tren so anh hong DUOI 0.19 — anh hong
    #   van con o tren muc do (o 41-48 cua bang dai deu la mat nham), nen con
    #   so do la lac quan; muon nang nguong thi phai cham them dai 0.19-0.25.
    #]]
    "blink": False,
    "blink_thresh": 0.12,       # EAR duoi nguong nay = mat khong dung duoc
    "blink_max_faces": 4,       # dong hon bay nhieu nguoi thi khong loai
    "blink_csv": "ear.csv",     # ten file EAR nam trong chinh thu muc anh
    "blink_reject_rating": 1,   # sao gan cho anh bi loai
    # Xuat thong so tu Lightroom thi BO qua anh co dung so sao nay. Cung quy
    # uoc voi burst_reject_rating. Dat 0 de xuat het.
    "export_skip_rating": 1,
    #[[ Auto Transform: ghi PerspectiveUpright de Lightroom tu nan perspective.
    #
    #   Chi bat cho anh co nen kien truc/backdrop VA mat chu the khong qua to.
    #   Anh chan dung can ma bat Upright thi meo mat, crop mat nguoi.
    #]]
    "upright": False,
    "upright_mode": 1,             # 1 = Auto, 2 = Level, 3 = Vertical, 4 = Full
    "upright_straight_min": 3.6,   # do thang toi thieu (p90 tren anh su kien)
    "upright_face_max_pct": 3.0,   # mat chiem hon bay nhieu % khung = chan dung can
    "max_ev": 1.00,           # trần |delta| exposure
    #[[ Tran rieng cho chieu KEO SANG. 0 = dung chung max_ev (nhu cu).
    #
    #   Tach ra vi hai chieu khong doi xung: dim mot anh thua sang qua tay thi
    #   chi mat cong, con keo sang anh thieu sang thi cuu duoc anh — nhat la anh
    #   nguoc sang hoac chup truoc man LED, thieu toi 2 EV la binh thuong.
    #   Phan chong chay sang (hl_hard_pct) van gac nen khong so bung.
    #]]
    "max_ev_up": 0.0,
    "deadband_ev": 0.05,      # lệch nhỏ hơn mức này thì bỏ qua
    "exposure_gain": 1.0,     # <1 = chỉnh dè dặt hơn
    "highlights": True,
    # Preview JPEG cháy sớm hơn RAW (RAW còn ~1 stop dư sáng), nên tỉ lệ cháy đo
    # được trên preview chỉ là CẬN TRÊN. Nhân với hệ số này để ước lượng mức cháy
    # thật của RAW. Khi preview đã cắt ở 255 thì không còn cách nào biết chính xác.
    "hl_discount": 0.60,
    "hl_trigger_pct": 0.30,
    "hl_gain": 14.0,          # điểm Highlights trên mỗi % pixel cháy
    "hl_max": 45,
    "hl_recover_ev": 1.5,     # kéo xuống bao nhiêu stop thì vùng bão hoà mới hồi lại
    # Ngưỡng cho phần cháy MỚI SINH RA (không phải tổng). Chụp màn LED thì tổng
    # mức cháy vốn đã 30-40%, lấy tổng mà so là chặn sạch mọi mức tăng.
    "hl_hard_pct": 8.0,
    #[[ Vung GAN chay (>= 242/255): ao trang, tuong sang. Chua cham tran nen
    #   phan "chay" o tren khong thay, nhung mat nguoi da thay bet chi tiet.
    #
    #   Hieu chinh tren 250 anh su kien that:
    #     vung sang(>=242): p25=0.6  p50=9.4  p75=35  p90=63
    #     chay that(>=254): p25=0.1  p50=2.2  p75=19  p90=52
    #   Anh su kien chay nhieu la binh thuong (den san khau, man LED) va duong
    #   "chay that" da lo roi. Cai duong nay chi de bat truong hop RIENG: vung
    #   sang LON ma chay that NHO — ao so mi trang, ao dai. Loai do chiem 4%.
    #   Nguong 4% + gain 6 cho ra hl_adj = -28 tren anh so mi trang thuc te
    #   (nguoi dung tu keo ve -35, tuc di dung huong va gan toi noi). Chan them
    #   dieu kien clip_after < nguong nen khong dam vao anh von da chay nhieu.
    #]]
    "hl_bright_trigger_pct": 4.0,
    "hl_bright_gain": 6.0,     # nhe tay hon hl_gain (14) vi con cuu duoc chi tiet
    "hl_bright_max": 40,
    # Do duoc mat thi khong ghim exposure ve 0 du nen chay sang: giu it nhat
    # bay nhieu EV cho chu the. Man LED chay them vai % khong ai de y, mat nguoi
    # toi thi ai cung thay. 0 = tat (quay ve hanh vi cu).
    "hl_subject_floor_ev": 0.45,
    #[[ Thu hoi vung chay — DA BI SO LIEU BAC BO o nguong 0.08, de 0 = TAT.
    #
    #   Chay tren buoi 1308 ngay 2/9 voi hl_thu_hoi_nguong = 0.08:
    #     Cong A (63 anh nhom sang-qua + nen-chay): keo lai gan 35, day ra xa 1
    #            sai trung binh 0.486 -> 0.287 EV. DAT, va manh nhat tu truoc toi nay.
    #     Cong B: 417/1277 anh da duyet xe dich qua 0.30 EV = 32.65%. Cong cho 2%.
    #
    #   Huong thi DUNG — 35 an 1 tren dung nhom no nham toi. Nhung NGUONG sai
    #   han: chot ban trung 36 anh dung va 417 anh sai.
    #
    #   Sai o dau: toi do "nguong 8% bat dung 73/78 anh, 94% chinh xac" TRONG
    #   TAP ANH NGUOI DUNG DA SUA — va khong he doi chieu ti le nen. Hoa ra 44%
    #   anh CUA CA BUOI cung tren nguong do. Mot dac trung co mat o 44% moi anh
    #   thi khong phan biet duoc gi ca; con so 94% kia chi la ti le nen doi lot.
    #
    #   DA DO LAI TREN CA 1464 ANH (3/9) VA HUONG NAY DONG LAI:
    #     bao hoa >= 0.20 -> ban 301 anh da duyet, trung 34/63, chinh xac 10%
    #     bao hoa >= 0.60 -> ban  13 anh da duyet, trung  8/63, chinh xac 38%
    #     bao hoa >= 0.50 VA chot chua chay -> ban 19, trung 12/63, chinh xac 39%
    #   Diem tot nhat lot noi cong B chi bat duoc 12/63 ma van dung 19 anh on.
    #
    #   Ly do that: buoi 1308 co 265 anh bao hoa >=30%, nguoi dung DUYET THANG
    #   234 anh. Vung chay lon la chuyen binh thuong o anh su kien — man LED,
    #   phong trang, cua so. Doc lai loi ho: "giam sang de giu lai noi dung
    #   standee", "de thay duoc ca background phia sau". Ho phan xet CAI GI nam
    #   trong vung chay, khong phai dien tich cua no. Histogram do sang khong
    #   phan biet duoc "standee co chu" voi "mang tuong trang".
    #
    #   Khong thu nguong thu tu tren truc nay. Muon di tiep phai co thu nhin
    #   duoc NOI DUNG vung chay.
    #]]
    "hl_thu_hoi_nguong": 0.0,    # ti le pixel bao hoa tro len thi moi keo xuong
    "hl_thu_hoi_ev": 0.42,       # keo xuong bao nhieu EV
    "hl_thu_hoi_san_ev": 0.60,   # nhung khong de mat thap hon dich qua bay nhieu
    # Cháy sẵn vượt mức này (% ) thì BỎ sàn chủ thể — xem chỗ dùng trong decide().
    # 0 = tắt, luôn giữ sàn như trước.
    "hl_heavy_clip_pct": 20.0,
    "shadows": True,
    "sh_discount": 0.50,      # tương tự cho vùng tối — RAW giữ chi tiết tốt hơn preview
    "sh_recover_ev": 2.0,
    "sh_trigger_pct": 2.0,
    "sh_gain": 3.0,
    "sh_max": 40,
    #[[ Parametric curve — 4 nui truot Shadows/Darks/Lights/Highlights cua
    #   Lightroom, moi cai la so nguyen -100..100.
    #
    #   CHI dung parametric, KHONG dung point curve: preset saymedia da co
    #   duong cong rieng (138,132 + nga mau R/G/B) tao nen chat anh. Trong
    #   Lightroom hai thu nay CONG DON chu khong de nhau, nen chinh parametric
    #   la an toan — curve cua preset con nguyen ven.
    #
    #   Vi sao khong dung han Highlights2012/Shadows2012 cho xong: hai truong do
    #   tac dong dai RONG, keo ca vung ke ben. Parametric cat theo nguong Split
    #   nen nham dung vung can sua — vd ha rieng man LED chay sang ma khong dim
    #   mat nguoi dung truoc no.
    #]]
    "curve": True,            # bat/tat toan bo phan curve
    #[[ Nguong hieu chinh theo do that tren 150 anh su kien:
    #     chay%: p10=0.5  p50=12.5  p75=26  p90=33  p99=40
    #     toi% : p50=0    p90=0.01  p99=8.3
    #   Anh su kien chay 12% la BINH THUONG (den san khau, man LED). Dat nguong
    #   5% thi 1/3 so anh cham tran -40, tay qua. Lay p75=26% lam moc: chi anh
    #   chay hon han moi bi keo.
    #]]
    "curve_hl_trigger_pct": 18.0,   # chay tren nguong nay moi dung toi
    "curve_hl_gain": 1.2,           # moi 1% chay -> bao nhieu diem Highlights am
    "curve_hl_max": 30,             # tran (diem)
    # Chu the: mo chi tiet vung toi (vest den, toc, vung bong)
    "curve_sh_trigger_pct": 0.5,    # % pixel bet toi vuot nguong nay moi dung
    "curve_sh_gain": 3.0,
    "curve_sh_max": 35,
    # Tuong phan tong the: chu S nhe. Preset da co curve rieng nen de tay,
    # chi them mot cham cho anh co chieu sau.
    "curve_contrast": 6,            # Lights +n va Darks -n (0 = tat)
    # Chan tren noi long theo p90: anh su kien chay 25-30% van con dep khi them
    # mot cham tuong phan; chi bo qua nhung anh chay du doi.
    "curve_contrast_max_clip": 30.0,
    #[[ "DAY TONE VE DA TRANG HONG" (grade) — ky yeu, concept. Bat thi:
    #     1. WB dung dich da trang hong (skin_ref_rgb) cho MOI anh, ke ca ngoai
    #        troi (tat: anh ngoai troi keo ve da ram skin_ref_rgb_ngoai).
    #     2. Color Grading tinh theo TRANG THAI — xem grade_theo_trang_thai():
    #        mau da du doan trong Lightroom (WB cuoi, Saturation / Vibrance /
    #        toning cua preset) con lech hue bao nhieu so voi dich thi xoay bay
    #        nhieu; CONG vecto vao banh xe Midtone + Highlight cua preset.
    #
    #   8/10 BO cach cu (hue 350 midtone + hue 220 bong theo do "thieu xanh lam"
    #   cua preview): sai huong (350 la DO, them vao da cam la da do hon — buoi ky
    #   yeu raw 19.4 "mau loan, khong con trang hong"), so tren preview chu khong
    #   tren anh Lightroom, va hai khoa bong ColorGradeShadow* Lightroom khong co.
    #]]
    #[[ QUY TRINH CHUAN CHINH MAU DA (8/10 dem, user) — xem chinh_mau_da():
    #     WB + Tone -> DO da (du doan trong LR, ke ca HSL / toning cua preset)
    #     -> HSL kenh da (chi khi lech vuot da_on_*) -> DO LAI -> Color Grading chi
    #     khi phan con lech > grade_nguong_hue, tinh tren PHAN VUOT, tran chat hon.
    #   Khong bao gio tinh HSL va Color Grading tu cung mot trang thai (de mau len
    #   nhau). Color Grading siet chat nhat: mot banh xe nho doi mau CA KHUNG,
    #   khong rieng vung da. ]]
    "grade": False,           # MAC DINH TAT — bat khi muon day manh ve trang hong
    "grade_sat_max": 8,       # tran Sat tool CONG vao moi banh xe (0-100); 12 -> 8 (8/10 dem)
    "grade_gain_hue": 0.45,   # diem Sat cho moi do hue (OkLab) da con lech dich QUA NGUONG
    "grade_nguong_hue": 4.0,  # da sau HSL con lech it hon (do OkLab) thi KHONG grade
    "da_on_hue": 3.0,         # da sau WB + Tone lech hue <= (do) thi HSL khong doi hue
    "da_on_chroma": 0.10,     # ... chroma lech <= ti le nay thi HSL khong doi Sat
    "da_trang_hong": False,   # dich hong cho ca anh ngoai troi ma khong grade
    #[[ DICH DA "TRANG HONG" (ky yeu / concept) — HOC TU ANH NGUOI DUNG DA DUYET, 8/10.
    #
    #   564 anh nguoi dung tu sua cho buoi ky yeu raw 19.4 (F:\San Pham Final    #   AnhKyTest), do bang chinh measure(), tach trong / ngoai bang chinh
    #   _nhan_da_ngoai (che do Tron), rut nhu hoc_mau_da.py:
    #       trong nha 389 anh -> [246, 194, 181]  log2(B/R) -1.00  G -0.27  hue 34
    #       ngoai troi 175 anh -> [194, 150, 137]  log2(B/R) -1.11  G -0.27  hue 37
    #   Dich hong cu [227, 184, 185] (B/R -0.66, G -0.35, hue 17 — tu anh SU KIEN
    #   PUBGDay1) HONG TIM hon han: bat "Day tone ve da trang hong" la keo ca buoi
    #   lanh + tim. "Trang hong" cua nguoi dung la da DAO: am hon dich cu 0.35-0.45
    #   stop, it tim hon; lanh hon dich da ram ngoai troi [166,123,105] 0.3 stop.
    #   Chi dung khi bat grade / da_trang_hong; quy trinh thuong (su kien, cuoi)
    #   van skin_ref_rgb / skin_ref_rgb_ngoai nhu cu. ]]
    "skin_dich_hong": [246, 194, 181],
    "skin_dich_hong_ngoai": [194, 150, 137],
    #[[ DIEM DIEU KHIEN WB khi bat trang hong — KHAC mau da dich o tren.
    #
    #   Vong WB cua tool chi keo ~30% quang duong toi dich (skin_gain 0.6 giu lai
    #   mau rieng tung anh; 900 K/stop yeu hon vat ly ~2 lan quanh 5000 K). Lay
    #   thang mau da anh duyet lam dich thi da trong LR dung lai giua duong: do
    #   tren raw 19.4 (mo hinh WB Adobe, sat LR that +-2 do hue) hue lech +6 do,
    #   con dich hong cu "vuot" nen lai trung. Nen WB nham mot DIEM DIEU KHIEN
    #   hieu chinh VONG KIN (hieu_chinh_dich.py: chon tren anh chan, cham anh le)
    #   de da SAU WB roi dung mau anh duyet; Color Grading thi nham thang mau da
    #   dich (skin_dich_hong) cho phan con thieu.
    #
    #   So: mau da hoc + 0.2 stop tren log2(B/R) (lanh hon), -0.35 tren log2(G)
    #   (hong hon — vong tint chi keo ~15%, tran wb_tint_max 12). Luoi 7x? thu:
    #   b -0.45 tot hon chut nhung 22 anh cham tran tint -> lay -0.35 (0 anh).
    #   Cham tren 267 anh LE chua dung de chon (che do Tron):
    #                         hue sau WB   hue sau grade (|lech|)   WB tv
    #       v40 dich hong cu     +5.1           -5.9 (6.0)          4792/+14
    #       mau da hoc lam dich  +8.4           +3.9 (4.5)          4981/+13
    #       diem dieu khien nay  +2.5           -0.4 (3.0)          4877/+19
    #   (che do Ngay: +2.9 / +1.4 (3.4)).
    #
    #   8/10 chieu — DO TREN ANH LIGHTROOM VE THAT (1088 preview 2048px, ban v41
    #   tren chinh buoi do): da LR LANH hon anh duyet 0.17 stop log2(B/R) (dG
    #   -0.03, hue +1.4) — LR ve da xanh hon mo hinh WB dung luc hieu chinh.
    #   Diem dieu khien phai dich 0.17 / DO DOC VONG: luoi hieu chinh do duoc dich
    #   diem dieu khien 1 stop thi da ra chi dich ~0.36 stop -> dich 0.47 stop,
    #   tu +0.2 xuong -0.27 stop B/R (G giu -0.35; them -0.18 de bu dG -0.03 thi
    #   ~20 anh cham tran tint). ]]
    "skin_ref_rgb_hong": [218, 147, 147],
    "skin_ref_rgb_hong_ngoai": [218, 145, 142],
    #[[ WB THEO TRANG THAI — xem dau decide(): can tren mau da DU DOAN trong
    #   Lightroom o WB preset, khong tren preview cua may. Chi anh preset DAT WB;
    #   quy trinh preset bo trong WB (nen_wb) khong doi. False = nhu truoc 8/10. ]]
    "wb_theo_trang_thai": True,
    #[[ Tint As Shot THANG ADOBE theo may — MakerNote co K, khong co tint. So
    #   that tu ban xuat catalog 6/10 (Lightroom da render As Shot): A7M4 K may
    #   5000 -> 5100 / +14, 5600 -> 5550 / +10 (123 anh); A7M5 4900 -> 4750 / +16,
    #   5400 -> 5150 / +16 (44 anh). "" = may chua co cap nao. ]]
    "wb_asshot_tint": {"ILCE-7M4": 12.0, "ILCE-7M5": 16.0, "": 12.0},
    "wb": "skin",             # skin | off | asshot | grey | scene
    # "skin": lay nhiet do may do duoc cho canh do (nhu asshot) roi cong them do
    # nga am + nga hong, de da len "trang hong". Hai so duoi la khau vi, chinh duoc.
    "wb_skin_temp_bias": 120.0,   # K, duong = am hon
    "wb_skin_tint_bias": 4.0,     # duong = nga magenta/hong, am = nga xanh la
    #[[ MAU DA DICH — RUT RA TU ANH NGUOI DUNG DA CAN TAY VA DUYET, khong phai
    #   mot tone chon theo cam tinh.
    #
    #   Ban cu la [244, 212, 202]: mot tone sang, nhat va nga hong. Da that duoi
    #   anh sang su kien cach no toi 0.85 stop, nen MOI anh deu bi do la "qua am"
    #   va bi keo lanh — buoi PUBGDay1 (1031 anh): 95% anh bi keo lanh, 34% ghim
    #   dung o tran, KHONG anh nao giu nguyen. Do chinh la vet xanh nguoi dung
    #   nhin thay.
    #
    #   So moi rut tu 269 anh da xuat va duyet cua buoi PUBGDay1, roi cham nguoc
    #   lai tren 175 cap RAW <-> anh duyet ghep theo gio chup (xem kiem_mau_da.py).
    #   Chon tham so tren mot nua du lieu, cham tren nua CHUA nhin toi:
    #
    #                          trung vi lech    trong +-0.25 stop
    #       cau hinh cu            0.212              56%
    #       cau hinh nay           0.152              72%
    #
    #   CHI TI LE MAU CO NGHIA, khong phai do sang: decide() chi lay log2(B/R) va
    #   log2(G/can(R*B)) cua bo ba nay.
    #]]
    "skin_ref_rgb": [227, 184, 185],
    #[[ MAU DA DICH RIENG CHO ANH NGOAI TROI. None = dung chung so tren.
    #
    #   NGUON SO: 16 anh ngoai troi buoi PUBGday2 ma nguoi dung tu can tay va
    #   thay ung (F:\Day2\_ngoaitroi_dachinh). Rut bang chinh cach cua
    #   hoc_mau_da.py: trung vi mau da, roi chon do sang sao cho lam tron ve
    #   0..255 lam lech ti le it nhat.
    #
    #   PHAI LOC TRUOC KHI HOC — mot cai bay that. Trong 20 anh do duoc mau da o
    #   thu muc do, 4 anh ISO 200 DA BI AutoTone lam lanh roi: doi chieu voi
    #   preview trong RAW cua cung khung hinh thi ban JPEG lanh hon ban RAW
    #   (+0.116 va +0.151 stop), va rot dung vao mau dich cu. Hoc ca 20 anh la
    #   day he thong giu nguyen cai mau xanh dang phai sua. Chi hoc 16 anh
    #   ISO 400 — nhung anh doi chieu ra JPEG AM HON RAW, tuc khong bi lam lanh.
    #
    #   KIEM CHONG HOC THUOC: chia doi 200 lan, hoc mot nua thu nua kia.
    #       lech tuyet doi voi mau dich cu  : 0.635 stop (572K)
    #       lech tuyet doi voi mau dich moi : 0.181 stop (163K)
    #
    #   BA NGUONG DAT TRUOC KHI CHAY, do tren 15 anh RAW that cua PUBGday2:
    #       ghim tran        < 10%      -> 0.0%     dat
    #       keo lanh      35% - 65%     -> 60.0%    dat
    #       trung vi |temp_adj| < 150K  -> 68K      dat
    #
    #   CHO CON RUI RO: nhom ngoai troi buoi nay khong dong nhat. 13 anh ISO 400
    #   do ra log2(B/R) quanh -1.3, con 2 anh ISO 200 quanh -0.7 — chenh nhau
    #   0.6 stop du deu la "ngoai troi". So moi hop voi nhom dong (13/15); hai
    #   anh ISO 200 se bi day AM them ~380K. Can nhin lai dung nhom do sau buoi
    #   chay toi.
    #]]
    "skin_ref_rgb_ngoai": [166, 123, 105],
    #[[ ISO tu day tro XUONG coi la ngoai troi (DAU <=, khong phai <).
    #
    #   Nguoi dung chot 400 sau khi do that: 16 trong 23 anh ma CHINH HO danh
    #   dau la ngoai troi nam DUNG o ISO 400. Nguong cu 320 xep 16 anh do vao
    #   nhom trong nha, nen chung bi keo lanh trung vi -484K — chinh la cho
    #   xanh ma ho phai sua tay. Voi nguong 400: -68K.
    #
    #   Dau phai la <= chu khong phai <: de "< 400" thi khong tam nao trong 16
    #   tam do lot vao, va sua nay khong doi duoc gi ca.
    #
    #   0 = tat han viec phan loai. Xem ngoai_troi().
    #]]
    "iso_ngoai_troi": 400,
    #[[ CHE DO ANH SANG CUA BUOI CHUP — do nguoi dung chon, khong doan.
    #
    #   "ngay"  : ca buoi la anh sang ngay (ke ca duoi nha bat / mai che)
    #   "den"   : ca buoi la anh den nhan tao
    #   "tron"  : co ca hai, tu tach theo EV100 (xem ev_ngoai_troi)
    #
    #   VI SAO CO O CHON NAY: khong co cach do nao noi chac duoc, va nguoi chup
    #   thi BIET. Hoi mot cau luc dau buoi re hon moi thuat toan.
    #]]
    "che_do_sang": "tron",
    #[[ NGUONG EV100 TACH ANH SANG NGAY / ANH DEN, dung khi che_do_sang = "tron".
    #
    #   VI SAO BO ISO MA DUNG EV100
    #     ISO chi la MOT trong ba chan cua tam giac phoi sang. Do tren 30 anh
    #     buoi Day2 cua nguoi dung: CUNG mot ISO, muc sang that lech nhau toi
    #     1,7 stop.
    #         ISO 500 -> EV100 tu 7,29 den 9,00
    #         ISO 250 -> EV100 tu 9,36 den 11,00
    #         ISO 400 -> EV100 tu 8,68 den 9,97
    #     Nguoi chup doi khau tu f/2.8 sang f/4 la nguong ISO lech ngay mot
    #     stop. EV100 gop ca ba chan nen khong bi the.
    #
    #   VI SAO CHON 8.5
    #     Giu DUNG nhom anh ma mau dich ngoai troi (skin_ref_rgb_ngoai) da duoc
    #     duyet tren do. Nhom ay chon bang ISO <= 400, va trong mau do thi
    #     ISO <= 400 ung voi EV100 >= 8,68. Dat 8.5 nen nhom gan nhu khong doi,
    #     chi khac o dung may tam ISO cao vi khau mo nho — truoc bi xep nham
    #     trong nha, nay ve dung nhom.
    #
    #     Do thuc te tren 30 anh Day2 (da nhin tan mat 10 tam de dan nhan):
    #         troi mo            EV100 10,3 - 11,6
    #         duoi nha bat/mai   EV100  7,6 - 10,0   <- van la anh sang ngay
    #         sau khi toi den    EV100  6,3
    #     Hoi truong trong nha voi den thuong roi vao EV100 5 - 6,5, nen 8.5
    #     con cach xa hai ben.
    #
    #   DAY LA CON SO NGHIEP VU, khong phai ket qua toi uu hoa. Doi duoc bat ky
    #   luc nao; 0 = tat han viec phan loai.
    #]]
    "ev_ngoai_troi": 8.5,
    #[[ skin_gain KHONG DOI — phep quet tu chon lai dung 0.6.
    #
    #   No khong phai "keo duoc bao nhieu phan quang duong" nhu ten goi gay hieu
    #   nham. Cong thuc that la  c_sau = (1-g)*c_raw + g*mau_dich, tuc g<1 GIU LAI
    #   mot phan mau da goc cua chinh tam anh do — thu mang thong tin rieng ma mot
    #   con so chung khong biet. Nen g cao hon KHONG phai la dung hon.
    #]]
    "skin_gain": 0.6,
    # asshot: kéo nhiệt độ preset về phía nhiệt độ máy đo được của cảnh
    # (crs:AsShotTemperature trong sidecar). 0 = giữ nguyên preset, 1 = theo hẳn máy.
    "wb_asshot_pull": 0.35,
    "wb_temp_gain": 900.0,
    #[[ TRAN NOI TU 400K LEN 1000K — day la phan RUI RO NHAT cua lan doi nay.
    #
    #   Voi mau da dich cu, tran 400K la mot cai phanh: no chan bot mot phep tinh
    #   dang keo sai huong. Sua mau dich xong thi phep tinh khong con sai huong
    #   nua, va luc do cai phanh chi con lam do dang — 19% anh doi muc sua vuot
    #   400K, va tat ca bi cat ngang.
    #
    #   Phep quet chon 1000K, va tren nua du lieu chua nhin toi thi ket qua tot
    #   hon han cau hinh cu. NHUNG: noi tran la cho phep MOI anh di xa hon, ke ca
    #   anh ma phep do mau da tren no vo tinh sai (mat qua nho, anh sang mau, ao
    #   mau da nguoi). Truoc day tran 400K gioi han thiet hai; gio thiet hai toi
    #   da gap hai lam ruoi.
    #
    #   Nen day la cho dau tien phai xem lai neu thay anh nao do bi lech mau la.
    #   Ha ve 600-700K van giu duoc phan lon cai loi, va an toan hon.
    #]]
    "wb_temp_max": 1000.0,
    "wb_tint_gain": 30.0,
    "wb_tint_max": 12.0,
    #[[ QUY TRINH "PRESET KHONG WB, KHONG TONE" (3/10) — xem preset_chua_ap().
    #
    #   User de xuat: import RAW -> ap preset BO TRONG nhom White Balance va nhom
    #   Basic Tone (Exposure, Contrast, Highlights, Shadows, Whites, Blacks). WB
    #   de As Shot thi Lightroom render GIONG preview cua may — dung goc benh "da
    #   vang cuc nang" buoi Hiu: may dat tay 3600-4000K, preset ep 5250K, tool chi
    #   keo duoc toi 4250K (tran wb_temp_max 1000K) nen LR render con am hon ca
    #   preview.
    #
    #   Bo hai nhom do khoi preset thi tool phai TU GHI chung. nen_tone = Basic
    #   Tone cua preset SAY: TrainTool 1502/1502 anh user giu nguyen Contrast 5 /
    #   Whites -25 / Blacks -18; Highlights / Shadows tool van tinh tu moc 16 nhu
    #   cu. nen_wb = WB cua preset (5250 / +16): CHUA doi cach can mau — ra Y HET
    #   quy trinh cu cho toi khi co so As Shot that de hoc lai. Nhan dang TUNG ANH
    #   tu ban xuat catalog; anh da co preset day du thi khong doi gi ca.
    #   Doi preset SAY (WB hay Tone) thi phai doi hai bang nay theo.
    #]]
    "nen_tone": {"Contrast2012": 5, "Highlights2012": 16, "Shadows2012": 16,
                 "Whites2012": -25, "Blacks2012": -18},
    "nen_wb": {"Temperature": 5250, "Tint": 16},
    #[[ WB THEO AS SHOT — quy trinh preset bo trong WB, BUOC 2 (3/10).
    #   Xem uoc_asshot() + _wb_theo_asshot(). CHI anh dang As Shot; quy trinh cu
    #   (preset day du) khong doi mot so nao.
    #
    #   VI SAO: nen 5250 bo qua WB nguoi chup da dat. G:\\2709 (cuoi, Nikon dat
    #   K tay 4760-6670, 1032/1074 anh ngay): Z 8 dat 6670 -> tool ghi 5279,
    #   Z5_2 5880 -> 5409. User: "anh ngoai troi bi keo ve xanh". Dung lai nhanh
    #   "keo ve AsShot" co san tu thoi sidecar, he so CO SAN wb_asshot_pull 0.35:
    #   temp_adj += 0.35 * (As Shot trung vi cua (canh, may) - 5250).
    #   Hai chan, dat TRUOC khi chay cong:
    #   - wb_asshot_theo_chieu: anh NGAY chi duoc keo AM len, anh DEN chi duoc
    #     keo LANH xuong — dung luat user noi "ngoai troi tang K, khong de xanh
    #     lanh; trong nha den vang moi ha K". Z5_2 dat 4760 giua nang (SUB_6733-
    #     54, EV100 11.9) khong bi keo xanh them.
    #   - wb_asshot_min_K: keo duoi 50K thi bo — mat khong thay, chi them nhieu.
    #     Sony dat 5600 (As Shot 5317) chi keo +24K ma cong dem la "xa" (2609
    #     A7M5 ngoai 21/85): may dat sat anh sang ngay thi khong co gi de hoc.
    #
    #   Cong (TrainTool = ban xuat preset moi that, 2609 = gia lap):
    #     TrainTool A 23/4 (Nikon Z6_2 ngoai 25 gan/2 xa), B 0%  — QUA
    #     2609      A 0/0 (khong anh sua nao doi),           B 0%  — QUA
    #     2709: 17/18 anh user sua Temp lai gan (5359 -> 5421, user 5859/5771),
    #       DSC_9614 dung yen; 776/1074 anh doi; Z 8 ngay trung vi 5279 -> 5714.
    #     1005 (Den): SAY00023/24 lai gan, DSC00015-21 lai gan, DSC00004 ra xa.
    #   Phan con lai cua SUB_6698-6713 (user +500K, As Shot chi giai thich +63K)
    #   la gu cua canh do, KHONG suy ra cho ca buoi tu mot canh.
    #
    #   DA THU, BO (dung thu lai khi khong co bang chung moi):
    #   - NEO HAN vao As Shot (Temp = As Shot dich theo mau da): 2709 18/18 gan,
    #     nhung TrainTool B 11.6%, 2609 A 99/160 + B 9.1% — Nikon Auto (TrainTool
    #     Z6_2, As Shot ~6200) user chot 5605; Sony ngay user chot 4800-5300 bat
    #     ke may dat bao nhieu. He so 0.7 / 1.0: TrainTool A truot.
    #   - San "anh ngay khong lanh hon As Shot": DSC_9614 (user 4936 < As Shot
    #     5150), TrainTool A7M5 ngoai 89 anh (user 4609 < 5300) di nguoc.
    #   - Keo truoc san phang mau (nhu Muc 2a): canh tron hai may thi may nay an
    #     As Shot cua may kia — xem _wb_theo_asshot().
    #
    #   VI SAO MUC 2a (wb_theo_may_pull 0.35, 2/10) TRUOT: no dung thang K trong
    #   MakerNote. K may KHONG trung thang Adobe: wb_asshot_lech_mired = 1e6/
    #   K_adobe - 1e6/K_may, do tu cap (K may, As Shot that) trong ban xuat:
    #   A7M4 4800->4800, 5100->5100, 5400->5350, 5600->5550; A7M5 5200->5000,
    #   5600->5300, 5800->5450 (lech ~300K — dung may chiem 2/3 hai buoi); Z 8
    #   5260->5150, 5880->5750, 6250->6050. Nikon khac (Z5_2, Z6_2) CHUA co cap:
    #   he so WB R/B theo K cua Z5_2 / Z6_2 / Z 8 trung nhau (5260K: log2 R/B
    #   0.389 / 0.388 / 0.394) nen tam lay so cua Z 8. Buoi nao tu co >= 3 cap
    #   cua mot may thi hoc lai tu chinh buoi do. Thang tho: TrainTool A 79/122,
    #   2609 107/164 — dung y so cua Muc 2a.
    #]]
    "wb_theo_asshot": True,
    "wb_asshot_theo_chieu": True,
    "wb_asshot_min_K": 50.0,
    "wb_asshot_lech_mired": {"ILCE-7M4": 1.0, "ILCE-7M5": 9.5, "NIKON Z 8": 4.4,
                             "NIKON": 4.4},
    "preview_px": 480,
    "marker": True,
    "lr_push": True,      # ghi job cho plugin Lightroom sau khi apply
    "source": "sidecar",  # sidecar = doc .xmp | catalog = lay tu Lightroom qua plugin
}


# ======================================================================
# GU ĐÃ HỌC — tham số rút ra từ những chỗ người dùng sửa tay
# ======================================================================
#[[ VI SAO NAP THANG VAO DEFAULTS, KHONG DUNG MOT LOP CAU HINH RIENG.
#
#   Tham so hoc duoc phai toi duoc CA BA duong: dong lenh, giao dien, va cac
#   script kiem (kiem_luat, kiem_san, kiem_gu). Them mot lop rieng thi phai
#   noi day vao ba cho, quen cho nao thi cho do chay bang so cu — kieu sai im
#   lang, khong ai phat hien ra.
#
#   Nap thang vao DEFAULTS thi ca ba dung chung mot nguon. Giao dien lay gia
#   tri khoi tao cho o nhap tu DEFAULTS nen o do hien luon so da hoc; nap muon
#   hon mot chut la widget ghi de nguoc lai va cong hoc thanh vo nghia.
#
#   Doi lai: DEFAULTS khong con la hang so. Nen phai on ao ve dieu do. GU_DA_HOC
#   giu nguyen phan da doi de moi cong cu deu noi duoc "dang chay bang gu da
#   hoc, khong phai so mac dinh", va moi lan nap deu in ra stderr.
#]]
GU_FILE = dd.du_lieu("gu.json")
GU_DA_HOC: dict = {}
GU_MAC_DINH: dict = {}


def nap_gu(path: Path | None = None) -> dict:
    """Nạp gu.json vào DEFAULTS. Trả về phần đã đổi. Hỏng thì chạy số gốc."""
    p = Path(path or GU_FILE)
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as ex:
        print(f"[!] Khong doc duoc {p.name}: {ex} — chay bang so mac dinh.",
              file=sys.stderr)
        return {}
    if not isinstance(data, dict):
        print(f"[!] {p.name} phai la mot doi tuong JSON — bo qua.", file=sys.stderr)
        return {}
    #[[ Khoa la hoac sai kieu -> BO, va BAO RA. Mot khoa go sai chinh ta ma van
    #   nap im thi no nam trong cfg khong bao gio co tac dung, con nguoi dung
    #   thi tuong da chinh xong.
    #]]
    la = sorted(set(data) - set(DEFAULTS))
    if la:
        print(f"[!] {p.name} co khoa khong dung den: {', '.join(la)}", file=sys.stderr)
    doi = {}
    for k, v in data.items():
        if k in la:
            continue
        cu = DEFAULTS[k]
        hop = (cu is None or isinstance(v, type(cu))
               or (isinstance(cu, (int, float)) and not isinstance(cu, bool)
                   and isinstance(v, (int, float)) and not isinstance(v, bool)))
        if not hop:
            print(f"[!] {p.name}: {k} sai kieu ({type(v).__name__}, can "
                  f"{type(cu).__name__}) — bo qua khoa nay", file=sys.stderr)
            continue
        if v != cu:
            GU_MAC_DINH[k] = cu
            DEFAULTS[k] = v
            doi[k] = v
    if doi:
        GU_DA_HOC.update(doi)
        print("[i] Gu da hoc: " + ", ".join(f"{k}={v}" for k, v in sorted(doi.items())),
              file=sys.stderr)
    return doi


def mo_ta_gu() -> str:
    """Một dòng cho giao diện / báo cáo: đang chạy bằng gu nào."""
    if not GU_DA_HOC:
        return "Chưa học gu nào — đang chạy tham số mặc định."
    return "Gu đã học: " + ", ".join(
        f"{k} {GU_MAC_DINH.get(k)} → {v}" for k, v in sorted(GU_DA_HOC.items()))


nap_gu()


def group_bursts(items: list, gap_sec: float, pose_thresh: float,
                 min_len: int = 3) -> None:
    """Gán burst id cho ảnh chụp liên tiếp CÙNG MỘT POSE.

    Hai bước, và bước thứ hai mới là điểm mấu chốt:

    1. Gom theo thời gian: cách nhau dưới `gap_sec` giây thì cùng một loạt.

    2. TÁCH THEO POSE trong loạt đó. Ảnh check-in backdrop chụp liên tục nhưng
       người ta đổi dáng tay, quay người, đổi nhóm — nếu chỉ gom theo thời gian
       rồi giữ 2 ảnh thì MẤT SẠCH các pose khác. Nên trong một loạt còn phải
       cắt tiếp mỗi khi bố cục đổi.

    Dùng lại chính scene_sig (lưới 4x6 đã chuẩn hoá) nhưng với ngưỡng NHẠY hơn
    nhiều so với tách cảnh: đổi cảnh là đổi cả phòng, còn đổi pose chỉ là dáng
    tay khác đi trên cùng một nền.

    Ảnh nào không thuộc loạt nào (chụp đơn lẻ) thì burst = -1, không bị lọc.
    """
    items.sort(key=lambda r: r["dt_obj"])
    bid = 0
    cur: list = []

    def close(group):
        nonlocal bid
        if len(group) >= min_len:
            for r in group:
                r["burst"] = bid
            bid += 1
        else:
            for r in group:
                r["burst"] = -1

    prev = None
    prev_sig = None
    for r in items:
        sig = np.asarray(r["scene_sig"], dtype=np.float64) if r.get("scene_sig") else None
        newgrp = False
        if prev is None:
            newgrp = True
        else:
            if (r["dt_obj"] - prev).total_seconds() > gap_sec:
                newgrp = True
            elif pose_thresh > 0 and sig is not None and prev_sig is not None:
                # đổi dáng/bố cục trong cùng loạt -> tách pose mới
                if float(np.abs(sig - prev_sig).mean()) > pose_thresh:
                    newgrp = True
        if newgrp:
            close(cur)
            cur = []
        cur.append(r)
        prev, prev_sig = r["dt_obj"], sig
    close(cur)


def pick_burst(items: list, keep: int, reject_rating: int,
               eye_weight: float = 0.6) -> int:
    """Chấm điểm trong từng loạt, giữ `keep` ảnh đẹp nhất, phần còn lại gắn sao.

    Điểm = mắt mở + nét mặt. Hai thứ này quyết định ảnh dùng được hay không;
    bố cục thì các ảnh trong cùng một loạt vốn đã giống nhau.

    ĐÂY KHÔNG PHẢI LỌC NHẮM MẮT. So sánh ở đây là TƯƠNG ĐỐI, chỉ giữa các ảnh
    trong cùng một loạt: chọn tấm mắt mở HƠN, nét HƠN. Nó không kết luận ảnh
    nào có người nhắm mắt — muốn thế phải dùng pick_blinks, một tính năng riêng.
    Ảnh bị loại ở đây mang ghi chú "loai-trong-loat" và cull="loat", không bao
    giờ mang nhãn nhắm mắt, để về sau không lấy nhãn bên này kiểm bên kia.

    eye_weight: trọng số cho độ mở mắt (phần còn lại dành cho độ nét). Để chỉnh
    được vì phép đo mắt chưa có nhãn thật xác nhận; đặt 0 là chỉ còn xét nét.

    Trả về số ảnh bị đánh dấu loại.
    """
    by: dict[int, list] = {}
    for r in items:
        b = r.get("burst", -1)
        if b >= 0:
            by.setdefault(b, []).append(r)

    dropped = 0
    for group in by.values():
        if len(group) <= keep:
            continue
        # chuẩn hoá từng tiêu chí TRONG loạt: so ảnh với nhau, không so với
        # thang tuyệt đối — loạt chụp tối thì mọi ảnh đều kém nét như nhau.
        eyes = [r.get("eye_open") for r in group]
        shrp = [r.get("face_sharp") for r in group]

        def norm(vals):
            ok = [v for v in vals if v is not None]
            if not ok:
                return [0.5] * len(vals)
            lo, hi = min(ok), max(ok)
            rng = (hi - lo) or 1.0
            return [0.5 if v is None else (v - lo) / rng for v in vals]

        ew = max(0.0, min(1.0, float(eye_weight)))
        ne, ns = norm(eyes), norm(shrp)
        for r, a, b in zip(group, ne, ns):
            r["pick_score"] = ew * a + (1.0 - ew) * b

        ranked = sorted(group, key=lambda r: -r["pick_score"])
        for i, r in enumerate(ranked):
            if i < keep:
                r["pick"] = True
            else:
                r["pick"] = False
                r["rating"] = reject_rating
                r["cull"] = "loat"
                r["notes"] = ";".join(
                    [n for n in [r.get("notes", ""), "loai-trong-loat"] if n])
                dropped += 1
    return dropped


def _stem_any(p) -> str:
    """Tên file không đuôi, cắt được cả dấu / lẫn dấu \\.

    Không dùng Path().stem: trên Linux thì dấu \\ không phải dấu ngăn thư mục
    nên "X:\\anh\\DSC01534.ARW" ra nguyên cả chuỗi. Đường dẫn trong autotone là
    đường dẫn Windows, mà test lại chạy ở nơi khác — phải cắt bằng tay.
    """
    s = str(p or "").replace("\\", "/").rsplit("/", 1)[-1]
    return s.rsplit(".", 1)[0].strip().lower()


def read_ear_csv(path: Path) -> dict:
    """Đọc ear.csv do eye_ear.py sinh ra -> {tên file (không đuôi): (EAR, số người)}.

    Khoá bằng TÊN FILE chứ không bằng đường dẫn đầy đủ: ear.csv có thể được sinh
    ra ở máy khác, ổ khác, hoặc thư mục đã đổi tên. Tên file gốc của máy ảnh thì
    không đổi.
    """
    out = {}
    try:
        with io.open(path, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                try:
                    ear = float(row["ear_min"])
                    faces = int(row["so_nguoi"])
                except (TypeError, ValueError, KeyError):
                    continue
                key = _stem_any(row.get("file"))
                if not key:
                    key = _stem_any(row.get("path"))
                if key:
                    out[key] = (ear, faces)
    except OSError:
        return {}
    return out


def pick_blinks(items: list, cfg: dict, folder: Path | None = None) -> int:
    """Loại ảnh MẮT KHÔNG DÙNG ĐƯỢC — tính năng riêng, không dính tới lọc loạt.

    Luật của người dùng, chép nguyên: ảnh 1 người, hoặc nhóm 2-4 người, mà có
    ai nhắm mắt thì loại. Ảnh tập thể đông người thì dù 1-2 người nhắm mắt cũng
    không loại, vì bản chất ảnh tập thể là người này người kia.

    TÊN GỌI: người dùng chấm nhãn theo tiêu chí "nhắm mắt HOẶC không dùng được",
    và thực tế nhóm EAR thấp có cả ảnh rung/mất nét — mắt nhoè thì viền mí cũng
    nhoè nên EAR tụt theo. Với việc lọc thì cả hai đều là loại, nhưng phải gọi
    đúng tên: đây là bộ lọc "mắt không dùng được", rộng hơn "nhắm mắt".

    NGUỒN SỐ: đọc ear.csv trong chính thư mục ảnh (do eye_ear.py sinh). KHÔNG
    có file đó thì hàm không chạy và nói rõ lý do — tuyệt đối không âm thầm
    quay về eye_open_min, vì phép đo đó đã bị nhãn thật bác bỏ.

    Trả về số ảnh bị đánh dấu loại (0 nếu không chạy được).
    """
    thr = float(cfg.get("blink_thresh") or 0.0)
    if thr <= 0:
        print("[!] Bo qua loc mat: blink_thresh = 0 (chua dat nguong).",
              file=sys.stderr)
        return 0

    #[[ Uu tien so do NGAY TRONG LUOT PHAN TICH, ear.csv chi la duong lui.
    #
    #   Tu khi gop, moi item da mang san ear_min do chinh measure() tinh — cung
    #   mot ham, cung do phan giai, nen cung mot con so. ear.csv van doc duoc de
    #   khong pha thu muc da do bang eye_ear.py truoc day.
    #]]
    trong_luot = sum(1 for r in items if r.get("ear_min") is not None)
    if trong_luot:
        loi = next((r.get("ear_err") for r in items if r.get("ear_err")), "")
        if loi:
            print(f"[!] Mot so anh khong do duoc mat: {loi}", file=sys.stderr)
        return _loc_theo_ear(items, cfg, lambda r: (r.get("ear_min"),
                                                    r.get("faces_n") or 0))

    thieu = next((r.get("ear_err") for r in items if r.get("ear_err")), "")
    if thieu:
        print(f"[!] Bo qua loc mat: khong do duoc do mo mat ({thieu}).\n"
              f"    Cai bang:  pip install mediapipe==0.10.14\n"
              f"    Can sang KHONG bi anh huong.", file=sys.stderr)
        return 0

    name = str(cfg.get("blink_csv") or "ear.csv")
    csv_path = (Path(folder) / name) if folder else None
    ear = read_ear_csv(csv_path) if csv_path else {}
    if not ear:
        print(f"[!] Bo qua loc mat: khong doc duoc {name} trong thu muc anh.\n"
              f"    Chay truoc:  python eye_ear.py \"{folder}\"\n"
              f"    Bo loc nay chi dung EAR trong {name}; no khong dung phep do\n"
              f"    eye_open cua autotone, vi phep do do da bi nhan that bac bo.\n"
              f"    Loc anh trung khung KHONG bi anh huong.", file=sys.stderr)
        return 0

    return _loc_theo_ear(items, cfg, lambda r: ear.get(_stem_any(r.get("path")))
                         or (None, 0))


def _loc_theo_ear(items: list, cfg: dict, lay) -> int:
    """Luật loại ảnh, dùng chung cho cả hai nguồn số — đo trong lượt hay ear.csv.

    Tách ra để hai đường KHÔNG BAO GIỜ lệch luật nhau. `lay(r)` trả (EAR, số người).
    """
    thr = float(cfg.get("blink_thresh") or 0.0)
    max_faces = int(cfg.get("blink_max_faces", 4))
    rating = int(cfg.get("blink_reject_rating", 1))
    dropped = 0
    for r in items:
        # Ảnh đã bị loại vì trùng khung thì thôi — giữ nguyên nhãn cũ để hai
        # tính năng không tranh nhau ghi đè lý do loại.
        if r.get("cull"):
            continue
        val, faces = lay(r)
        if val is None:
            continue                      # ảnh chưa đo EAR -> không kết luận
        if not (1 <= int(faces or 0) <= max_faces):
            continue                      # ảnh tập thể: không đụng tới
        if float(val) >= thr:
            continue
        r["ear_min"] = float(val)
        r["rating"] = rating
        r["cull"] = "nham-mat"
        r["notes"] = ";".join(
            [n for n in [r.get("notes", ""), "loai-nham-mat"] if n])
        dropped += 1
    return dropped


def lam_min_trong_ngoai(items: list, min_shots: int) -> int:
    """Doan nhan ngay/den ngan hon min_shots, kep giua hai doan cung nhan, thi
    theo hai ben. Tra ve so anh bi doi nhan. min_shots <= 1 la TAT.

    Nhan goc giu lai o r["ngoai_troi_tho"] de bao cao con truy duoc.
    Xem chu thich o trong_ngoai_min_shots trong DEFAULTS.
    """
    for r in items:
        r["ngoai_troi_tho"] = bool(r.get("ngoai_troi"))
    n = int(min_shots or 0)
    if n <= 1 or len(items) < 3:
        return 0
    ds = sorted(items, key=lambda r: r["dt_obj"])
    # gom thanh cac doan lien tiep cung nhan: [(nhan, bat_dau, ket_thuc)]
    doan, i = [], 0
    while i < len(ds):
        j = i
        while j + 1 < len(ds) and bool(ds[j + 1]["ngoai_troi"]) == bool(ds[i]["ngoai_troi"]):
            j += 1
        doan.append((bool(ds[i]["ngoai_troi"]), i, j))
        i = j + 1
    doi = 0
    for k in range(1, len(doan) - 1):
        nh, a, b = doan[k]
        truoc, sau = doan[k - 1][0], doan[k + 1][0]
        if b - a + 1 < n and truoc == sau and truoc != nh:
            for x in ds[a:b + 1]:
                x["ngoai_troi"] = truoc
                x["notes"] = ";".join(
                    [v for v in [x.get("notes", ""), "nhan-ngay-den-theo-hai-ben"] if v])
                doi += 1
    return doi


def _nhan_ngoai(r: dict, cfg: dict) -> bool:
    """Nhan ngay/den cua anh: dung nhan plan() da gan (co the da lam min),
    chi tu tinh khi chua co — decide() con duoc goi le trong bai kiem."""
    if "ngoai_troi" in r:
        return bool(r["ngoai_troi"])
    return ngoai_troi(r, cfg)


def tran_da(r: dict, cfg: dict) -> float:
    """Tran p95 cua da (sRGB 0-255) cho phanh da. MUC 3 (2/10/2026).

    Mac dinh skin_hard_p95 (232). Khung cháy nhieu (sat_frac >= khung_sang_pct %)
    thi ha xuong khung_sang_tran_da. khung_sang_pct = 0 la TAT.

    #[[ VI SAO — ban quay 2/10, buoi TrainTool, 108 anh co mat do lai tren RAW:
    #   48 tam user HA sang thi luc tool day ra, da mat dung o DUNG tran 232
    #   (trung vi) trong khung chay ~18%; user keo da ve ~201. Tool keo mat len
    #   toi tran trong khi nen cua so / troi da chay — user noi "giam exposure
    #   de anh hai hoa, thay vi mat nguoi co phai sang" (BNE02316), "giam sang
    #   cho phan da mat khong bi chay highlight" (SAY07160).
    #   Khung it chay (16 tam user TANG sang: trung vi 3.7%) thi khong dung toi.
    #
    #   Khac huong "keo xuong theo muc chay" da DONG ngay 3/9: cai do keo MOI anh
    #   khung chay xuong, ke ca anh da dung. Cai nay chi chan DA MAT bi day len
    #   qua sang trong khung da chay — anh mat dang vua thi khong cham toi.
    #]]
    """
    tran = float(cfg.get("skin_hard_p95") or 0.0)
    nguong = float(cfg.get("khung_sang_pct", 0.0) or 0.0)
    if tran > 0 and nguong > 0 and float(r.get("sat_frac") or 0.0) * 100.0 >= nguong:
        tran = min(tran, float(cfg.get("khung_sang_tran_da") or tran))
    return tran


def _nhan_da_ngoai(r: dict, cfg: dict) -> bool:
    """Nhan ngay/den DUNG DE CHON MAU DA DICH. da_vang_lech_ngoai = 0 -> y het
    _nhan_ngoai().

    #[[ MUC 2 (2/10/2026). Nhan ngay/den tinh bang EV100 >= 8.5 — do DO SANG
    #   cua canh, khong do MAU anh sang. Ban quay 1 buoi TrainTool: le vu quy
    #   trong nha co cua so, EV100 8.6-9.0 nen bi xep "anh sang ngay", lay mau
    #   da dich ngoai troi [166,123,105] — mot mau RAT am — nen da vang duoi den
    #   decor bi coi la binh thuong: tool de SAY 4864-5109K, user keo ve
    #   4305-4609K ("anh chup trong nha, khong gian nhieu mau vang").
    #
    #   Do tren 6 anh do: da preview log2(B/R) -1.71..-2.28, trong khi mau dich
    #   ngoai troi la -1.43 va anh ngoai troi that cua buoi do (SAY06511/23,
    #   Nikon HIU_40xx) chi -0.2..-1.5. Da AM HON CA MAU DICH NGOAI TROI them
    #   mot khoang ro rang thi dang co den am chieu vao nguoi — dung mau dich
    #   trong nha cho tam do. Neu dung mau trong nha: SAY06085 ra ~4390K (user
    #   chot 4364), SAY06092 ~4380K (user 4305).
    #]]
    """
    ngoai = _nhan_ngoai(r, cfg)
    lech = float(cfg.get("da_vang_lech_ngoai", 0.0) or 0.0)
    if not ngoai or lech <= 0 or not r.get("face_rgb"):
        return ngoai
    ref = cfg.get("skin_ref_rgb_ngoai")
    if not ref:
        return ngoai
    mt, _ = wb_cast(np.asarray(r["face_rgb"], dtype=np.float64))
    rt, _ = wb_cast(srgb_to_linear(np.asarray(ref, dtype=np.float64) / 255.0) + EPS)
    return not (mt < rt - lech)


def sua_mat_lech_khung(items: list, cfg: dict) -> int:
    """Phep do mat lech han khoi do sang khung so voi cac tam chup ke ben ->
    thay bang do sang khung + khoang cach mat-khung cua hang xom. Tra ve so anh
    bi thay. Xem mat_lech_khung_ev trong DEFAULTS. 0 = TAT.

    Hang xom = cung canh, cung than may, cung khau/toc/ISO, dung truoc/sau theo
    thoi gian (toi da mat_lech_khung_ke tam moi ben), CUNG BO CUC (chu ky khung
    cach <= mat_lech_khung_bo_cuc). Can >= mat_lech_khung_min hang xom co ca
    phep do mat lan phep do khung.
    """
    nguong = float(cfg.get("mat_lech_khung_ev", 0.0) or 0.0)
    nguong_co = float(cfg.get("mat_lech_khung_ev_lens_co", 0.0) or 0.0)
    if nguong <= 0 and nguong_co <= 0:
        return 0
    ke = max(1, int(cfg.get("mat_lech_khung_ke", 3)))

    def khoa(r):
        f, t, iso = _so(r.get("fnumber")), _so(r.get("exposure_time")), _so(r.get("iso"))
        if not t or not iso:
            return None
        #  Lens co: khong biet khau -> "?" (khau vong co hiem khi doi giua hai
        #  tam chup lien; con dieu kien bo cuc + do sang khung chan phia sau)
        return (r.get("scene"), str(r.get("model") or ""),
                round(f, 1) if f else "?", round(math.log2(t), 2), round(iso))

    loat: dict = {}
    for r in sorted(items, key=lambda r: r["dt_obj"]):
        k = khoa(r)
        if k is not None:
            loat.setdefault(k, []).append(r)

    khung_tol = float(cfg.get("mat_lech_khung_khung_ev", 0.25))
    bo_cuc = float(cfg.get("mat_lech_khung_bo_cuc", 0.10))
    n_min = max(1, int(cfg.get("mat_lech_khung_min", 2)))

    def sig(r):
        v = r.get("scene_sig")
        return np.asarray(v, dtype=np.float64) if v else None

    def hai(r):
        f, c = r.get("metered_face_ev"), r.get("metered_subject_ev")
        return None if f is None or c is None else (float(f), float(c))

    #[[ Tinh het truoc roi moi sua: sua tai cho thi tam sau lay tam vua sua
    #   lam hang xom, va mot tam hong keo lan sang tam ke. ]]
    sua = []
    for k_, ds in loat.items():
        ng = nguong_co if k_[2] == "?" and nguong_co > 0 else nguong
        if ng <= 0:
            continue
        v = [hai(r) for r in ds]
        sg = [sig(r) for r in ds]
        if k_[2] == "?":
            #[[ LENS CO: so KHOANG CACH mat - khung voi trung vi MOI tam cung bo
            #   cuc trong +-ke_rong tam, khong chi +-3 tam ke ben. Do nham o
            #   fisheye hay DON CUM: HUY04802-04804 ba tam lien nham -> trung vi
            #   +-3 tam cua chinh tam DUNG (HUY04805) nghieng ve so nham, lan dau
            #   thu da "sua" nham hai tam dung va keo ca loat len +0.70. Lay ca
            #   cum cung bo cuc rong hon thi so dong tam dung at di. Can >= 3 tam
            #   lanh de so; do nham lan hon nua cum thi khong ket luan. ]]
            ke_rong = max(ke, int(cfg.get("mat_lech_khung_ke_lens_co", 10)))
            #  Bo cuc RONG hon (0.20): fisheye nguoi di trong khung la chu ky doi
            #  nhieu — HUY04801 / 04807-04810 cung canh cach cum 04802-04806
            #  0.11-0.15; bo cuc khac han (04799/04800) cach 0.30-0.38 van bi loai
            bo_cuc_co = max(bo_cuc, float(cfg.get("mat_lech_khung_bo_cuc_lens_co", 0.20)))
            gap = [None if x is None else x[0] - x[1] for x in v]

            def lang_gieng(i, tol):
                return [j for j in range(max(0, i - ke_rong), min(len(ds), i + ke_rong + 1))
                        if j != i and gap[j] is not None and sg[j] is not None
                        and sg[j].shape == sg[i].shape
                        and float(np.abs(sg[j] - sg[i]).mean()) <= tol]
            #  Buoc 1: PHAT HIEN tren nhom rong
            nham = set()
            for i in range(len(ds)):
                if gap[i] is None or sg[i] is None:
                    continue
                rong = lang_gieng(i, bo_cuc_co)
                if len(rong) >= max(3, n_min) and \
                        abs(gap[i] - float(np.median([gap[j] for j in rong]))) > ng:
                    nham.add(i)
            #  Buoc 2: SO SUA lay tu cac tam DUNG gan bo cuc nhat (<= bo_cuc), khong
            #  co moi lay nhom rong — cum 04802-04806 khoang cach that 2.8, vung
            #  rong 2.45: lay rong thi ca loat lech 0.3 EV so voi tam dung
            for i in nham:
                hep = [gap[j] for j in lang_gieng(i, bo_cuc) if j not in nham]
                rong = [gap[j] for j in lang_gieng(i, bo_cuc_co) if j not in nham]
                g_ = hep or rong
                if g_:
                    sua.append((ds[i], v[i][1] + float(np.median(g_))))
            continue
        for i, r in enumerate(ds):
            if v[i] is None or sg[i] is None:
                continue
            hx = [v[j] for j in range(max(0, i - ke), min(len(ds), i + ke + 1))
                  if j != i and v[j] is not None and sg[j] is not None
                  and sg[j].shape == sg[i].shape
                  and float(np.abs(sg[j] - sg[i]).mean()) <= bo_cuc]
            if len(hx) < n_min:
                continue
            mat_hx = float(np.median([x[0] for x in hx]))
            khung_hx = float(np.median([x[1] for x in hx]))
            if (abs(v[i][1] - khung_hx) <= khung_tol
                    and abs(v[i][0] - mat_hx) > ng):
                gap_hx = float(np.median([x[0] - x[1] for x in hx]))
                sua.append((r, v[i][1] + gap_hx))
    for r, moi in sua:
        cu = float(r["metered_face_ev"])
        r["metered_face_ev_tho"] = cu
        r["metered_ev_tho"] = r["metered_ev"]
        r["metered_face_ev"] = round(moi, 4)
        #[[ Doi metered_ev CUNG MOT KHOANG, khong gan thang: metered_ev co the
        #   da tron them phep do khac ngoai mat, gan de se xoa mat phan do. ]]
        r["metered_ev"] = float(r["metered_ev"]) + (moi - cu)
        r["notes"] = ";".join([v for v in [r.get("notes", ""), "do-mat-lech-khung"] if v])
    return len(sua)


def _doi_mat_do(r: dict, moi: float, nhan: str) -> None:
    """Thay phep do mat cua mot anh, GIU so goc de _tra_mat_goc() tra lai.

    Chi luu so goc o lan doi DAU TIEN — anh da bi sua_mat_lech_khung() doi roi
    thi so goc da nam san trong *_tho, luu de la mat so that."""
    cu = float(r["metered_face_ev"])
    if "metered_face_ev_tho" not in r:
        r["metered_face_ev_tho"] = cu
        r["metered_ev_tho"] = r["metered_ev"]
    r["metered_face_ev"] = round(float(moi), 4)
    r["metered_ev"] = float(r["metered_ev"]) + (float(moi) - cu)
    if nhan and nhan not in r.get("notes", ""):
        r["notes"] = ";".join([v for v in [r.get("notes", ""), nhan] if v])


def bu_do_theo_may(items: list, cfg: dict) -> int:
    """MUC 4 (2/10/2026) — bu phep do theo THAN MAY. {} = TAT.

    cfg["bu_exp_theo_may"] = {"chuoi trong ten may": ev, ...}. Mot so DUONG
    nghia la preview cua may do SANG HON cach Lightroom render file RAW cua no,
    nen phep do bi tru di chung do — tool se cho anh sang hon chung do.

    #[[ VI SAO DO THEO MAY: moi hang render preview mot kieu (Nikon dung Picture
    #   Control + Active D-Lighting, Sony dung Creative Style). Tool do mat tren
    #   preview, con Lightroom render tu RAW bang profile Adobe — hai thu lech
    #   nhau mot khoang co dinh theo may. Ban quay 2/10: 40/60 lan user chinh
    #   Exposure anh Nikon la TANG sang (trung vi +0.21 tren anh da sua).
    #   So bu KHONG dat tay: hoc tren anh da duyet cua mot buoi, kiem tren buoi
    #   khac (kiem_2ban_quay.py).
    #]]
    """
    bang = cfg.get("bu_exp_theo_may") or {}
    if not isinstance(bang, dict) or not bang:
        return 0
    n = 0
    for r in items:
        if r.get("metered_face_ev") is None:
            continue
        ten = str(r.get("model") or "").upper()
        for k, v in bang.items():
            if k and str(k).upper() in ten and float(v):
                _doi_mat_do(r, float(r["metered_face_ev"]) - float(v), "bu-theo-may")
                n += 1
                break
    return n


def do_mat_theo_anh_sang(items: list, cfg: dict) -> int:
    """MUC 1 (2/10/2026) — MOT ANH SANG MOT KET QUA. canh_ev100 = 0 la TAT.

    Trong cung canh + cung than may, anh nao co do sang KHUNG (da quy ve EV100)
    gan nhau trong khoang canh_ev100 thi coi la cung mot anh sang. Phep do mat
    cua tam do duoc thay bang TRUNG VI cua nhom do (cung quy ve EV100), roi tra
    lai thang cua tam do bang chinh EV100 cua no. Tra ve so anh bi doi > 0.02.
    Vung sang cua da cung vay: ghi r["face_p95_dong"] cho phanh da doc.

    #[[ VI SAO — ban quay 2/10, buoi TrainTool, do lai tren RAW that:
    #   DSC08668-08672 cung f/2.2 1/100 ISO 500 (EV100 6.60). Mat do duoc
    #   -1.22/-0.79/-0.81/-1.30/-1.22 -> tool ra +0.03/-0.40/-0.38/0/+0.03;
    #   user dong bo het -0.61. BNE02293-305: mat do trai 1.18 EV trong khi
    #   khung chi 0.4 EV. SAY07160-76: thong so may y het, tool 0..+0.68,
    #   user 0. San phang canh ep moi tam ve cung "sang mat DO DUOC", nen do
    #   mat nhieu bao nhieu thi Exposure nhay bay nhieu.
    #
    #   QUY VE EV100 (khau/toc/ISO) vi doi thong so giua chung thi anh tho sang
    #   toi theo, ma anh sang that khong doi: DSC08665 f/2.8 -> 08668 f/2.2 la
    #   +0.69 EV, user bu dung chieu (+0.25 -> -0.61).
    #
    #   CHI GOP ANH CO KHUNG SANG GIONG NHAU: hai phuong an da bi bac ngay 29/9
    #   la "cung thong so may thi cung Exposure" (san khau doi den ma thong so
    #   khong doi). O day dieu kien la DO SANG KHUNG (da quy EV100) — den doi
    #   thi khung doi, anh do tu tach khoi nhom va giu phep do rieng.
    #
    #   CUNG THAN MAY: preview moi may sang mot kieu (xem bu_do_theo_may).
    #]]
    """
    tol = float(cfg.get("canh_ev100", 0.0) or 0.0)
    if tol <= 0:
        return 0
    ke = max(1, int(cfg.get("canh_ev100_ke", 8)))
    n_min = max(2, int(cfg.get("canh_ev100_min", 3)))
    #[[ THONG SO MAY KHONG DUOC NHAY QUA canh_ev100_tt EV giua hai tam.
    #
    #   Do khung (quy EV100) gan nhau chua du noi "cung anh sang tren MAT".
    #   Gap that tren TrainTool: HIU_4113 (EV100 10.32) bi gop voi HIU_4100/
    #   4102 (EV100 11.98) vi khung lech chi 0.48 — nhung mat 4113 nguoc sang,
    #   toi hon khung, con 4100 mat sang hon khung. Trung vi keo mat 4113 len
    #   +1.14 EV -> Exposure -1.55 (user chot -0.50).
    #   Nguoi chup doi thong so hon 1 stop la ho da thay anh sang doi. Doi
    #   duoi 1 stop (DSC08665 -> 08668 f/2.8 -> f/2.2 = 0.69; BNE02302 ISO
    #   1600 -> 1250 = 0.35) la tinh chinh trong cung mot anh sang.
    #]]
    tt = float(cfg.get("canh_ev100_tt", 1.0) or 0.0)

    nhom: dict = {}
    for r in sorted(items, key=lambda r: r["dt_obj"]):
        nhom.setdefault((r.get("scene"), str(r.get("model") or "")), []).append(r)

    sua, p95_dong = [], []
    for ds in nhom.values():
        L, F, E, P = [], [], [], []
        for r in ds:
            ev = ev100(r)
            f, c = r.get("metered_face_ev"), r.get("metered_subject_ev")
            ok = ev is not None and f is not None and c is not None
            L.append(float(f) + ev if ok else None)
            F.append(float(c) + ev if ok else None)
            E.append(ev if ok else None)
            p = r.get("face_p95")
            lp = _srgb_to_lin_1(float(p)) if ok and p else 0.0
            P.append(math.log2(lp) + ev if lp > 1e-6 else None)
        for i, r in enumerate(ds):
            if L[i] is None:
                continue
            gan = [j for j in range(max(0, i - ke), min(len(ds), i + ke + 1))
                   if L[j] is not None and abs(F[j] - F[i]) <= tol
                   and (tt <= 0 or abs(E[j] - E[i]) <= tt)]
            if len(gan) < n_min:
                continue
            moi = float(np.median([L[j] for j in gan])) - E[i]
            if abs(moi - float(r["metered_face_ev"])) > 0.02:
                sua.append((r, moi))
            #[[ Vung sang cua da (face_p95) cung lay DONG THUAN cua chinh nhom
            #   do, cung quy EV100. Khong thi phanh da (tran_da) lai lam dung
            #   cai loi vua sua: cung mot anh sang, tam nao do trung mat co
            #   p95 cao thi bi dim, tam ben canh khong — lai "buc sang buc toi".
            #]]
            pv = [P[j] for j in gan if P[j] is not None]
            if P[i] is not None and len(pv) >= n_min:
                p95_dong.append((r, _lin_to_srgb(2.0 ** (float(np.median(pv)) - E[i]))))
    for r, moi in sua:
        _doi_mat_do(r, moi, "do-theo-anh-sang")
    for r, p in p95_dong:
        r["face_p95_dong"] = round(float(p), 5)
    return len(sua)


def _tra_mat_goc(items: list) -> None:
    """Tra phep do mat goc truoc moi lan decide(). GUI goi plan() lai tren CUNG
    items khi doi tuy chon; khong tra thi tat tuy chon roi van con so da sua."""
    for r in items:
        if "metered_face_ev_tho" in r:
            r["metered_face_ev"] = r.pop("metered_face_ev_tho")
            r["metered_ev"] = r.pop("metered_ev_tho")
        r.pop("face_p95_dong", None)


def group_scenes(items: list, gap_minutes: float, sig_thresh: float = 0.0,
                 sig_min_shots: int = 3, can_sig: bool = True) -> None:
    """Gán scene id theo thời gian, và (tuỳ chọn) theo BỐI CẢNH khung hình.

    HAI LUẬT, MỖI LUẬT TẮT ĐƯỢC RIÊNG
        gap_minutes <= 0  ->  KHÔNG tách theo thời gian
        sig_thresh  <= 0  ->  KHÔNG tách theo bối cảnh

    Tắt cả hai thì cả buổi thành MỘT cảnh. Đó là lựa chọn hợp lệ khi mode là
    "absolute" (mỗi ảnh về mốc riêng, không cần cảnh), nhưng nếu scene_level
    đang bật thì nó biến thành san phẳng CẢ BUỔI về một mốc — đúng bằng mode
    "batch", chỉ là đi cửa sau và không ai nói ra. Nơi gọi phải cảnh báo; hàm
    này chỉ làm đúng thứ được yêu cầu.

    Vì sao cần tách theo bối cảnh: ảnh sự kiện chụp liên tục nên khoảng cách
    thời gian không bao giờ vượt ngưỡng — cả buổi dồn vào một "cảnh" duy nhất
    dù đã đổi phòng, đổi sân khấu. Đo thật: 200 ảnh gom thành 7 cảnh, trong đó
    một cảnh 87 ảnh có biên độ sáng tới 2.2 EV. Cân chung cả nhóm đó là sai.

    Cách so: KHÔNG so hai ảnh liền kề (người đi qua khung cũng làm lệch chữ ký,
    cắt vụn thành 90 cảnh) mà so với chữ ký TRUNG BÌNH của cảnh đang mở. Bối
    cảnh chỉ thực sự đổi khi lệch kéo dài, không phải một khung cá biệt.

    VÌ SAO gap_minutes <= 0 CHỨ KHÔNG PHẢI gap_minutes = 0
        gap = timedelta(0) nghĩa là "cách nhau hơn 0 giây là cảnh mới" — tức
        MỖI ẢNH một cảnh. Đó gần như đúng ngược lại với ý "tắt luật thời gian",
        và nó không sập, không báo gì: chỉ ra 1464 cảnh thay vì 132, rồi mọi
        phép trung vị theo cảnh mất nghĩa. Nên số 0 phải được hiểu là TẮT.
    """
    items.sort(key=lambda r: r["dt_obj"])
    theo_gio = gap_minutes > 0
    gap = timedelta(minutes=gap_minutes) if theo_gio else None
    sid, prev = 0, None
    ref = None          # chữ ký trung bình của cảnh đang mở
    nref = 0
    pending = 0         # số khung liên tiếp đang lệch khỏi cảnh hiện tại
    cho: list = []      # (ảnh, chữ ký) của đúng những khung đang lệch đó

    prev_ngoai = None
    for r in items:
        cut_gio = bool(theo_gio and prev is not None and r["dt_obj"] - prev > gap)

        #[[ TRONG NHA VA NGOAI TROI KHONG BAO GIO CHUNG MOT CANH.
        #
        #   Buoc san phang cuoi decide() keo temp_adj cua moi anh trong cung mot
        #   canh ve trung vi chung — co y, de anh chup canh nhau khong ra hai mau.
        #   Nhung neu canh do vua co anh trong nha vua co anh ngoai troi thi no
        #   xoa sach viec phan hai mau da dich: ca hai nhom ra CUNG MOT so.
        #
        #   Da mac dung the khi kiem: dat mau dich ngoai troi am hon han, ma ca
        #   hai nhom van ra -283K y nhau. Tinh nang chay dung, buoc san phang o
        #   sau xoa mat.
        #
        #   Ma "canh" von co nghia la MOT moi truong anh sang. Trong nha va ngoai
        #   troi la hai moi truong khac nhau nhat co the — nen day khong phai mot
        #   mieng va, ma la dung dinh nghia.
        #]]
        ng = bool(r.get("ngoai_troi"))
        cut_moi_truong = prev_ngoai is not None and ng != prev_ngoai
        prev_ngoai = ng

        sig = r.get("scene_sig")
        #[[ Do do lech TRUOC khi xu ly cat, ke ca khi cat vi thoi gian. Khong do
        #   o day thi ref bi dat lai truoc, va con so do mat luon.
        #]]
        s = np.asarray(sig, dtype=np.float64) if (sig_thresh > 0 and sig) else None
        if s is not None and ref is not None:
            r["scene_sig_lech"] = round(float(np.abs(s - ref).mean()), 4)
            #[[ GIO PHAI DUOC BOI CANH DONG Y.
            #
            #   Nghi lau ma khung hinh y nguyen thi khong phai canh moi. Buoi su
            #   kien co doan check-in chup lien tuc ~30 phut tai MOT phong, nghi
            #   vai phut giua chung la binh thuong (user xac nhan 3/9). Tach doi
            #   doan do ra thi hai nua duoc san sang doc lap, va khach dung cung
            #   mot phong lai ra hai muc sang khac nhau.
            #
            #   Do that buoi 1308, 13 nhat cat theo gio:
            #      7 nhat co chu ky lech 0.36-0.52  -> phong doi that, GIU
            #      6 nhat co chu ky lech 0.05-0.20  -> cung phong, BO
            #   Hai nhom tach hoan toan, khong cai nao roi vao khoang giua. Nen
            #   nguong dung o day la CHINH sig_thresh — cung cai nguong dinh
            #   nghia "boi canh da doi" — chu khong phai mot con so moi.
            #
            #   Nhat nghi 26 phut lech 4.55 EV van duoc giu: chu ky lech 0.44.
            #
            #   Chi phu quyet khi luat boi canh DANG BAT (s is not None). Tat no
            #   di thi khong con y kien nao de hoi, luat thoi gian lam viec mot
            #   minh nhu cu.
            #]]
            if cut_gio and can_sig and r["scene_sig_lech"] <= sig_thresh:
                cut_gio = False
                r["scene_cut"] = "gio-bo-vi-cung-phong"

        #[[ Cat vi DOI MOI TRUONG gop vao SAU khi chot veto, khong di nho duong
        #   cut_gio. Veto "gio phai duoc boi canh dong y" sinh ra de bo nhung
        #   nhat nghi giua mot phong — no khong duoc phep phu quyet viec buoc ra
        #   ngoai troi. Da mac dung the: gop truoc veto thi cut bi nuot, hai
        #   nhom van ve chung mot canh va buoc san phang xoa mat viec phan loai.
        #]]
        cut = cut_gio or cut_moi_truong
        if cut_moi_truong and not cut_gio:
            r["scene_cut"] = "doi-trong-ngoai"

        if s is not None:
            if cut or ref is None:
                ref, nref, pending, cho = s.copy(), 1, 0, []
            elif r["scene_sig_lech"] > sig_thresh:
                pending += 1
                cho.append((r, s))
                # Phải lệch liên tục vài khung mới coi là đổi bối cảnh —
                # một khung cận cảnh hay ai đó đi ngang không tính.
                if pending >= sig_min_shots:
                    cut = True
                    pending = 0
            else:
                pending, cho = 0, []
                nref += 1
                ref += (s - ref) / nref        # trung bình chạy

        if cut:
            sid += 1
            #[[ LUI RANH GIOI VE KHUNG BAT DAU LECH.
            #
            #   Luat boi canh doi lech du sig_min_shots khung lien tiep roi moi
            #   cat — va truoc day no cat NGAY TAI khung xac nhan. Nghia la
            #   sig_min_shots-1 khung dau cua boi canh moi bi bo lai canh cu.
            #
            #   Do that tren buoi 1308: o moi ranh gioi boi canh, lay hai khung
            #   cuoi cua canh cu va xem chung gan trung vi canh nao hon —
            #   40/46 = 87% nam gan canh SAU. Ngau nhien la 50%. Vi du
            #   DSC01107/01108 dang bi can chung voi mot canh sang hon chung
            #   1.2 EV; cap SAY09786/09787 buoi 0306 cung dung kieu do.
            #
            #   Sua bang cach nho khung ma do lech BAT DAU, roi dat ranh gioi o
            #   day — khong ha nguong, khong them con so nao. Ha sig_min_shots
            #   xuong 1 thi lai cat vun vi mot nguoi di ngang khung.
            #
            #   Chi lui cho nhat cat do BOI CANH. Nhat cat theo GIO thi ban than
            #   khoang nghi la bang chung ve vi tri ranh gioi, khong duoc dich.
            #]]
            if not cut_gio and cho:
                for x, _s in cho:
                    x["scene"] = sid
                #[[ CHU KY MO MAN = KHUNG XAC NHAN, khong phai trung binh may
                #   khung vua lui ve.
                #
                #   Ban dau toi lay trung binh, va viet trong ghi chu rang do la
                #   cach dung. Khong co bang chung nao ca — chi la truc giac, va
                #   no la mot thay doi THUA nhet kem vao ban sua.
                #
                #   Do that 3/9 tren buoi 1308 cho thay cai gia: 11 ranh gioi
                #   BIEN MAT (131 -> 124 canh), trong do 5 cho gop hai canh deu
                #   tu 4 anh tro len va lech nhau tu 0.30 EV — nang nhat la mot
                #   canh 4 anh bi nuot vao canh 53 anh cach no 1.69 EV.
                #
                #   TOI KHONG GIAI THICH DUOC CO CHE, va da thu that.
                #   Gia thuyet dau: khung DAU cua doan lech la khung CHUYEN TIEP,
                #   lay trung binh thi duoc mot chu ky lo lung giua hai canh, nen
                #   lan doi boi canh ke tiep khong vuot nguong nua. Nghe xuoi tai,
                #   nhung mot bo so thu nghiem cho ket qua NGUOC LAI — ban trung
                #   binh bat duoc NHIEU ranh gioi hon. Vay huong tac dong tuy hinh
                #   hoc tung truong hop, khong co quy luat mot chieu, va toi da
                #   suyt viet mot loi giai thich tron tru ma sai.
                #
                #   Can cu de doi la BANG CHUNG tren du lieu that, khong phai co
                #   che: ban trung binh mat 11 ranh gioi. Ban nay tra ve dung
                #   hanh vi cu, von da do duoc 131 ranh gioi tren chinh buoi do.
                #
                #   Bai hoc: mot ban sua nen lam DUNG mot viec. Lui ranh gioi va
                #   doi chu ky mo man la hai viec; viec thu hai toi nhet kem vao
                #   ma khong do gi truoc, roi viet ghi chu nhu the no hien nhien
                #   dung.
                #]]
                ref, nref = s.copy(), 1
                cho[0][0]["scene_cut"] = "boi-canh"
            else:
                if sig_thresh > 0 and sig:
                    ref, nref = np.asarray(sig, dtype=np.float64).copy(), 1
                #[[ Giu nhan "doi-trong-ngoai" da gan o tren. Truoc day dong nay
                #   ghi de no thanh "boi-canh", nen bao cao noi "khung hinh doi"
                #   trong khi chu ky lech 0 va nhat cat that ra do EV100 cua MOT
                #   tam vuot nguong ev_ngoai_troi. Doc bao cao la di tim sai cho.
                #]]
                r["scene_cut"] = ("gio" if cut_gio else
                                  "doi-trong-ngoai" if cut_moi_truong else
                                  "boi-canh")
            cho = []
        r["scene"] = sid
        prev = r["dt_obj"]


TONE_NHOM = ("Contrast2012", "Highlights2012", "Shadows2012", "Whites2012", "Blacks2012")
# Cot chi plugin tu 3/10 moi xuat — moc chot tu plugin cu de trong (xem
# attach_catalog_settings).
COT_PLUGIN_MOI = ("WhiteBalance", "Contrast2012", "Whites2012", "Blacks2012")


#[[ Cot plugin xuat tu 8/10: Color Grading / Saturation / Vibrance cua preset —
#   de grade_theo_trang_thai() du doan da trong Lightroom va cong vecto vao so
#   GOC. Luu ca vao moc (save_baseline): lan ghi dau tool doi midtone /
#   highlight, lan sau catalog khong con so goc nua. ]]
COT_MAU = ("ColorGradeMidtoneHue", "ColorGradeMidtoneSat",
           "SplitToningShadowHue", "SplitToningShadowSaturation",
           "SplitToningHighlightHue", "SplitToningHighlightSaturation",
           "SplitToningBalance", "ColorGradeBlending",
           "ColorGradeGlobalHue", "ColorGradeGlobalSat", "Saturation", "Vibrance")


#[[ 8/10 vong 5: HSL KENH DA (Loai buoi Ky yeu) — ba dai HSL co the chua sac to da.
#   Tool chi chinh DAI DA DO DUOC (thuong la Orange), hai dai con lai giu so goc.
#   Cung luu vao moc nhu COT_MAU: lan ghi dau doi Orange, lan sau catalog khong con
#   so goc. Xem hsl_da_theo_trang_thai(). ]]
DAI_HSL_DA = ("Red", "Orange", "Yellow")
COT_HSL = tuple(f"{k}Adjustment{d}" for d in DAI_HSL_DA for k in ("Hue", "Saturation"))


def anh_da_hsl(folder: Path, job_dir: Path | None = None) -> set:
    """Khoá ảnh mà một job bất kỳ của buổi này từng gửi HSL kênh da — catalog của
    chúng đang mang số TOOL ghi, không phải số preset."""
    d = Path(job_dir or LR_JOB_DIR)
    if not d.is_dir():
        return set()
    ten = ten_job(Path(folder).name)
    out = set()
    for jp in sorted(d.glob(f"apply_*_{ten}.done")) + sorted(d.glob(f"apply_*_{ten}.tsv")):
        if "khoiphuc" in jp.name.lower():
            continue
        try:
            with io.open(jp, encoding="utf-8-sig", newline="") as fh:
                for row in csv.DictReader(fh, delimiter="	"):
                    if row.get("path") and any(str(row.get(k) or "").strip() for k in COT_HSL):
                        out.add(khoa_duong_dan(row["path"]))
        except (OSError, csv.Error):
            continue
    return out


def bu_cot_hsl(moc: dict, moi: dict, da_hsl: bool) -> dict:
    """Cột COT_HSL mà mốc để TRỐNG (chốt trước vòng 5) lấy từ bản xuất mới; ảnh tool
    đã từng ghi HSL thì số gốc không còn ở đâu — coi là 0 (preset không chỉnh HSL
    da). -> {cột: giá trị} cần bù."""
    def rong(v) -> bool:
        return str(v if v is not None else "").strip() == ""

    bu = {}
    for k in COT_HSL:
        if not rong(moc.get(k)):
            continue
        if da_hsl:
            bu[k] = "0"
        elif not rong(moi.get(k)):
            bu[k] = moi[k]
    return bu


def anh_da_grade(folder: Path, job_dir: Path | None = None) -> set:
    """Khoá ảnh (khoa_duong_dan) mà một job bất kỳ của buổi này từng gửi Color
    Grading — catalog của chúng đang mang số TOOL ghi ở midtone, không phải số
    preset."""
    d = Path(job_dir or LR_JOB_DIR)
    if not d.is_dir():
        return set()
    ten = ten_job(Path(folder).name)
    out = set()
    for jp in sorted(d.glob(f"apply_*_{ten}.done")) + sorted(d.glob(f"apply_*_{ten}.tsv")):
        if "khoiphuc" in jp.name.lower():
            continue
        try:
            with io.open(jp, encoding="utf-8-sig", newline="") as fh:
                for row in csv.DictReader(fh, delimiter="	"):
                    if str(row.get("ColorGradeMidtoneSat") or "").strip() and row.get("path"):
                        out.add(khoa_duong_dan(row["path"]))
        except (OSError, csv.Error):
            continue
    return out


def bu_cot_mau(moc: dict, moi: dict, da_grade: bool) -> dict:
    """Cột COT_MAU mà mốc để TRỐNG (chốt từ plugin trước 8/10) lấy từ bản xuất
    mới. -> {cột: giá trị} cần bù.

    #[[ Tool CHUA BAO GIO ghi Saturation / Vibrance / banh xe bong, highlight,
    #   global — so trong catalog chinh la so preset. RIENG midtone: anh ma job cu
    #   da gui Color Grading (da_grade) thi catalog dang mang hue 350 / sat cua
    #   tool -> so goc khong con o dau ca; coi la 0 / 0 (preset khong grade
    #   midtone — dung voi Bong22 va preset SAY doi moi). ]]
    """
    def rong(v) -> bool:
        return str(v if v is not None else "").strip() == ""

    bu = {}
    for k in COT_MAU:
        if not rong(moc.get(k)):
            continue
        if k in ("ColorGradeMidtoneHue", "ColorGradeMidtoneSat") and da_grade:
            bu[k] = "0"
        elif not rong(moi.get(k)):
            bu[k] = moi[k]
    return bu


def bu_cot_plugin_moi(moc: dict, moi: dict) -> dict:
    """Cột COT_PLUGIN_MOI mà mốc để TRỐNG (chốt từ plugin cũ) lấy được từ bản
    ghi mới. -> {cột: giá trị} cần bù, {} nếu không bù.

    #[[ 6/10, buoi BVDay3: moc chot tu plugin 4/9 nen bon cot nay rong; catalog
    #   CHUA BAO GIO doi quy trinh (preset luon bo trong WB / Tone, tool chua ghi
    #   chung) -> so trong ban xuat moi CHINH LA so goc, bu vao moc.
    #
    #   CHI BU KHI KHOP VOI CHINH MOC. Moc preset DAY DU (Temperature 5250,
    #   Highlights 16) ma catalog nay As Shot / Tone 0 = anh da import lai theo
    #   quy trinh moi SAU khi chot moc (test_preset_khong_wb_tone muc 4) — bu vao
    #   thi moc thanh lai (WB As Shot + Highlights 16) va che mat nhanh
    #   moc-cu-khac-quy-trinh. Nen:
    #     WhiteBalance: moc khong co Temperature <-> catalog khac Custom
    #     Contrast / Whites / Blacks: moc Highlights = Shadows = 0 <-> catalog
    #       ca ba = 0 ]]
    """
    def rong(v) -> bool:
        return str(v if v is not None else "").strip() == ""

    bu = {}
    wb = str(moi.get("WhiteBalance") or "").strip()
    if rong(moc.get("WhiteBalance")) and wb:
        co_t = get_f(moc, "Temperature", 0.0) > 0
        if (wb.lower() == "custom") == co_t:
            bu["WhiteBalance"] = wb
        elif not co_t:
            #[[ Moc KHONG co Temperature = luc chot anh dang As Shot (preset day
            #   du luon dat Custom 5250). Catalog nay Custom la do sua / sync tay
            #   SAU lan ghi — so goc van la As Shot. BVDay3: 127 anh nhu vay. ]]
            bu["WhiteBalance"] = "As Shot"
        elif abs(get_f(moc, "Temperature", 0.0) - get_f(moi, "Temperature", 0.0)) < 1:
            #[[ As Shot Lightroom DA render (co Temperature, xem _asshot_catalog):
            #   cung nhiet do voi moc = cung trang thai luc chot. ]]
            bu["WhiteBalance"] = wb
    tone = [k for k in ("Contrast2012", "Whites2012", "Blacks2012")
            if rong(moc.get(k)) and not rong(moi.get(k))]
    if tone:
        moc_0 = (get_f(moc, "Highlights2012", 0.0) == 0
                 and get_f(moc, "Shadows2012", 0.0) == 0)
        moi_0 = all(get_f(moi, k, 0.0) == 0 for k in ("Contrast2012", "Whites2012",
                                                      "Blacks2012"))
        if moc_0 == moi_0:
            bu.update({k: moi[k] for k in tone})
    return bu


def preset_chua_ap(crs: dict) -> tuple[bool, bool]:
    """(thieu_tone, thieu_wb): preset da ap cho anh nay BO TRONG nhom Basic Tone /
    nhom White Balance. Doc tu ban xuat catalog (hoac sidecar).

    #[[ THIEU TONE = Contrast, Whites, Blacks CO trong ban xuat va ca ba bang 0,
    #   Highlights / Shadows cung 0. Doi CO MAT ca ba: plugin cu khong xuat chung
    #   -> khong bao gio nhan nham, quy trinh cu giu nguyen tung so. Preset SAY ap
    #   5 / -25 / -18 nen anh co preset day du khong bao gio roi vao day; TrainTool
    #   1502/1502 anh user khong dong vao ba thanh do.
    #
    #   THIEU WB = WhiteBalance co trong ban xuat va KHAC "Custom" (As Shot, Auto,
    #   Daylight...). Preset SAY dat Custom 5250/+16; tool ghi WB cung dat Custom.
    #]]
    """
    def so(k):
        v = crs.get(k)
        if v is None or str(v).strip() == "":
            return None
        try:
            return float(str(v).replace("+", ""))
        except ValueError:
            return None

    ba = [so(k) for k in ("Contrast2012", "Whites2012", "Blacks2012")]
    thieu_tone = (all(v == 0 for v in ba)
                  and (so("Highlights2012") or 0.0) == 0 and (so("Shadows2012") or 0.0) == 0)
    wb = str(crs.get("WhiteBalance") or "").strip()
    return thieu_tone, bool(wb) and wb.lower() != "custom"


def nen_cho_anh(crs: dict, cfg: dict) -> dict:
    """Ban "preset" ma tool tinh tren do: thong so that, phan preset KHONG ap thi
    phu nen SAY (cfg nen_tone / nen_wb). crs goc giu nguyen — moc luu xuong dia la
    so THAT (As Shot) de sau nay con hoc lai WB.

    Danh dau "__nen_tone" / "__nen_wb" de compute_values biet phai TU GHI nhom do
    (Lightroom dang o 0 / As Shot, khong phai o nen). Goi lai tren ket qua cua
    chinh no thi ra y nguyen.
    """
    thieu_tone, thieu_wb = preset_chua_ap(crs)
    out = dict(crs)
    nt = ((cfg.get("nen_tone_ky_yeu") if cfg.get("loai_buoi") == "ky_yeu" else None)
          or cfg.get("nen_tone") or {})
    if thieu_tone and nt:
        out.update({k: nt[k] for k in nt})
        out["__nen_tone"] = True
    nw = cfg.get("nen_wb") or {}
    if thieu_wb and nw.get("Temperature"):
        out["Temperature"], out["Tint"] = nw["Temperature"], nw.get("Tint", 0)
        #[[ Bo AsShot*: o quy trinh cu hai o nay luon trong (ban xuat 3/10 Hiu,
        #   1303/1303 anh). De lot vao decide() thi nhanh "keo ve AsShot" bat len
        #   va ket qua khong con y het quy trinh cu nua. ]]
        out.pop("AsShotTemperature", None)
        out.pop("AsShotTint", None)
        out["__nen_wb"] = True
    return out


def _asshot_catalog(crs: dict) -> float:
    """Temp As Shot THAT trong catalog (thang Adobe), 0 neu khong co.

    Lightroom chi tra so nay cho anh no DA DUNG (1005: 59/630 anh) — anh chua
    dung thi o Temperature de trong. Chi nhan dung "As Shot": "Auto" / "Daylight"
    cung khac Custom nhung so do la Lightroom TU TINH, khong phai WB cua may."""
    if not crs or str(crs.get("WhiteBalance", "")).replace(" ", "").lower() != "asshot":
        return 0.0
    return max(get_f(crs, "Temperature", 0.0), 0.0)


def uoc_asshot(items: list, cfg: dict) -> int:
    """Gan r["asshot_K"] — nhiet do As Shot THANG ADOBE — cho moi anh dang As
    Shot (preset bo trong WB). Tra ve so anh uoc duoc.

    Thu tu: (1) so that trong catalog; (2) K trong MakerNote quy sang thang
    Adobe bang wb_asshot_lech_mired — hoc tu CHINH buoi neu may do co >= 3 cap
    (K may, As Shot that), khong thi lay bang trong DEFAULTS (khop ten may dai
    nhat), khong co thi 0. Khong co ca hai -> khong gan, compute_values tinh nhu
    cu tren nen 5250."""
    if not cfg.get("wb_theo_asshot"):
        return 0
    bang = {str(k).upper(): float(v)
            for k, v in (cfg.get("wb_asshot_lech_mired") or {}).items()}
    cap: dict = {}
    for r in items:
        t, k = _asshot_catalog(r.get("crs") or {}), _so(r.get("wb_may_K"))
        if t > 0 and k and k > 0:
            cap.setdefault(str(r.get("model") or "").upper(), []).append(1e6 / t - 1e6 / k)
    hoc = {m: float(np.median(v)) for m, v in cap.items() if len(v) >= 3}

    def lech(model: str) -> float:
        m = model.upper()
        if m in hoc:
            return hoc[m]
        khop = [k for k in bang if k and k in m]
        return bang[max(khop, key=len)] if khop else 0.0

    n = 0
    for r in items:
        r.pop("asshot_K", None)
        r.pop("asshot_nguon", None)
        crs = r.get("crs") or {}
        if not preset_chua_ap(crs)[1]:
            continue
        t = _asshot_catalog(crs)
        if t > 0:
            r["asshot_K"], r["asshot_nguon"] = round(t, 1), "catalog"
        else:
            k = _so(r.get("wb_may_K"))
            if not k or k <= 0:
                continue
            m = 1e6 / k + lech(str(r.get("model") or ""))
            r["asshot_K"], r["asshot_nguon"] = round(1e6 / max(m, 20.0), 1), "may"
        n += 1
    return n


def preset_val(r: dict, crs_key: str) -> float:
    """Giá trị preset gốc của một field: ưu tiên marker atn: để lần chạy sau
    không tính trên kết quả của lần trước. Có "crs_nen" (decide() dựng, xem
    nen_cho_anh) thì đọc từ đó."""
    mk = ATN_FIELDS[crs_key]
    if mk in r.get("atn", {}):
        return get_f(r["atn"], mk, 0.0)
    return get_f(r.get("crs_nen") or r.get("crs", {}), crs_key, 0.0)


def _so(v):
    """Một giá trị EXIF về số. Tag EXIF hay là (tử, mẫu) hoặc [(tử, mẫu)]."""
    if v is None:
        return None
    if isinstance(v, (list, tuple)):
        if not v:
            return None
        v = v[0]
    if isinstance(v, (list, tuple)):
        if len(v) == 2 and v[1]:
            return float(v[0]) / float(v[1])
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def ev100(r: dict):
    """Mức sáng thật của cảnh, quy về ISO 100. None nếu thiếu tag.

        EV100 = log2(N² / t) − log2(ISO / 100)

    N = khẩu, t = tốc (giây), ISO = độ nhạy. Đây là đại lượng chuẩn của nhiếp
    ảnh cho "cảnh này sáng bao nhiêu" — nó gộp cả ba chân của tam giác phơi
    sáng, nên không đổi khi người chụp bù chân này bằng chân kia.

    VÌ SAO KHÔNG DÙNG ISO KHÔNG
        ISO chỉ là một chân. Đo trên 30 ảnh buổi Day2: cùng ISO 500 có ảnh
        EV100 7,29 và ảnh EV100 9,00 — lệch 1,7 stop ánh sáng thật. Một ngưỡng
        ISO không thể đúng cho cả hai.

    Mốc tham khảo: nắng mở EV100 ≈ 14-15; trời râm/mây ≈ 11-13; dưới nhà bạt
    ban ngày ≈ 8-10; hội trường đèn ≈ 5-6,5; sau khi tối ≈ 6 trở xuống.
    """
    iso = _so(r.get("iso"))
    t = _so(r.get("exposure_time"))
    n = _so(r.get("fnumber"))
    if not iso or not t or not n or iso <= 0 or t <= 0 or n <= 0:
        return None
    try:
        return math.log2(n * n / t) - math.log2(iso / 100.0)
    except (ValueError, ZeroDivisionError):
        return None


def ngoai_troi(r: dict, cfg: dict) -> bool:
    """Ảnh này ăn ánh sáng ngày hay ánh đèn.

    BA CHẾ ĐỘ, DO NGƯỜI DÙNG CHỌN (cfg["che_do_sang"]):
        "ngay" -> cả buổi là ánh sáng ngày, trả về True cho mọi ảnh
        "den"  -> cả buổi là ánh đèn, trả về False cho mọi ảnh
        "tron" -> tự tách theo EV100, ngưỡng cfg["ev_ngoai_troi"]

    VÌ SAO CÓ Ô CHỌN chứ không cố đoán cho bằng được: buổi nào cũng có người
    chụp ở đó và họ BIẾT. Hỏi một câu lúc đầu buổi rẻ hơn mọi thuật toán, và
    không bao giờ sai.

    VÌ SAO TÊN LÀ ÁNH SÁNG NGÀY / ÁNH ĐÈN chứ không phải ngoài trời / trong nhà:
        Buổi Day2 của người dùng chụp HOÀN TOÀN ngoài trời — từ trời mở, xuống
        nhà bạt và mái che, tới sau khi tối đèn. Không hề có ranh giới trong /
        ngoài nhà, chỉ có mức sáng giảm dần. Thứ quyết định màu là NGUỒN SÁNG,
        không phải có tường hay không. Một mô hình phân loại indoor/outdoor
        (Places365 chẳng hạn) sẽ gọi ảnh trong nhà bạt là "indoor" trong khi
        ánh sáng vẫn là ánh sáng ngày — trả lời đúng câu hỏi của nó, sai câu
        hỏi của mình.

    Tên hàm giữ nguyên ngoai_troi() vì nó nằm trong REPORT_COLS, trong file
    trạng thái và trong dữ liệu gu đã học; đổi tên là làm hỏng dữ liệu cũ.

    (Phần chú thích cũ về ngưỡng ISO giữ lại bên dưới — đường ISO vẫn là dự
    phòng khi ảnh không đọc được đủ ba tag để tính EV100.)
    """
    che_do = str(cfg.get("che_do_sang") or "tron").strip().lower()
    if che_do in ("ngay", "day", "ngoai", "ngoai_troi"):
        return True
    if che_do in ("den", "trong", "trong_nha", "indoor"):
        return False

    ng_ev = float(cfg.get("ev_ngoai_troi") or 0)
    if ng_ev > 0:
        ev = ev100(r)
        if ev is not None:
            return ev >= ng_ev
        #[[ Thieu tag de tinh EV100 (anh cu, anh da qua phan mem khac) thi LUI
        #   VE duong ISO chu khong tra ve False luon. Tra ve False la lang le
        #   xep ca nhung anh do vao nhom trong nha. ]]
    return _ngoai_troi_theo_iso(r, cfg)


def _ngoai_troi_theo_iso(r: dict, cfg: dict) -> bool:
    """Đường DỰ PHÒNG: đoán theo ISO khi không tính được EV100.

    NGƯỠNG ĐẶT THEO KINH NGHIỆM CHỤP, KHÔNG PHẢI THEO SỐ LIỆU
        Người dùng chốt: ISO ≤ 320 là ngoài trời, cao hơn là trong nhà. Đó là
        kinh nghiệm chụp sự kiện, và nó là quyết định nghiệp vụ chứ không phải
        một giả thuyết cần chứng minh.

        Cần nói thẳng cái đã đo được: trên buổi PUBGDay1, ISO KHÔNG tách được
        hai cụm (một dốc liền từ 100 tới 2000, 27% ảnh nằm đúng ở ISO 500), và
        ISO cũng không dự đoán được ảnh nào bị lệch màu nhiều. Người dùng biết
        điều đó và vẫn chọn ngưỡng này, chấp nhận rằng ảnh ngoài trời chụp ISO
        cao vì chủ ý kỹ thuật sẽ bị xếp nhầm và họ tự sửa tay.

        Nên đây là một cái van có thể tắt: đặt iso_ngoai_troi = 0 là bỏ hẳn việc
        phân loại, mọi ảnh về chung một nhóm như trước.

    KHÔNG ĐỌC ĐƯỢC ISO THÌ COI LÀ TRONG NHÀ
        Ảnh sự kiện phần lớn là trong nhà, nên đoán về phía đó ít sai hơn. Và sai
        về phía trong nhà thì chỉ là giữ nguyên cách cũ, còn sai về phía ngoài
        trời thì đem một màu đích khác áp lên ảnh không đáng.
    """
    nguong = float(cfg.get("iso_ngoai_troi") or 0)
    if nguong <= 0:
        return False
    iso = r.get("iso")
    if iso is None:
        return False
    try:
        v = float(iso[0] if isinstance(iso, (tuple, list)) else iso)
    except (TypeError, ValueError):
        return False
    return 0 < v <= nguong


def wb_cast(rgb_mean) -> tuple[float, float]:
    """Trả về (lệch nhiệt độ theo stop, lệch tint theo stop) từ giả định grey-world."""
    r, g, b = rgb_mean
    temp_ev = float(np.log2(b / r)) if r > 0 and b > 0 else 0.0
    tint_ev = float(np.log2(g / np.sqrt(r * b))) if r > 0 and b > 0 and g > 0 else 0.0
    return temp_ev, tint_ev


def _skin_wb(cfg: dict, temp_adj: float, tint_adj: float,
             skin_temp_ev, skin_tint_ev, notes: list) -> tuple[float, float]:
    """Cộng phần chỉnh WB theo màu da vào delta đang có, rồi kẹp trong giới hạn.

    Có mẫu da thật thì kéo màu da đo được về phía màu da đích (`skin_ref_rgb`).
    Không thấy mặt nào trong cả cảnh thì lùi về độ ngả hồng cố định.
    """
    if skin_temp_ev is None:
        temp_adj += float(cfg["wb_skin_temp_bias"])
        tint_adj += float(cfg["wb_skin_tint_bias"])
        notes.append("WB-nga-hong-co-dinh-khong-thay-mat")
    else:
        g = float(cfg["skin_gain"])
        temp_adj += g * float(cfg["wb_temp_gain"]) * skin_temp_ev
        tint_adj += g * float(cfg["wb_tint_gain"]) * skin_tint_ev
    return (float(np.clip(temp_adj, -cfg["wb_temp_max"], cfg["wb_temp_max"])),
            float(np.clip(tint_adj, -cfg["wb_tint_max"], cfg["wb_tint_max"])))


# ======================================================================
# MÔ HÌNH MÀU LIGHTROOM — Color Grading tính theo TRẠNG THÁI từng ảnh
# ======================================================================
#[[ 8/10, buoi ky yeu "raw 19.4" (preset Bong22: Custom 5950 / +19, Saturation
#   +19, Vibrance +25, Highlights toning 36/10). Nguoi dung: "bat Color Grading
#   thi mau loan, khong con trang hong" — va: "can thiep Color Grading phai tinh
#   xem anh dang o muc nao, can can thiep ra sao de co ket qua dung yeu cau".
#
#   CACH CU SAI HAI CHO:
#     1. So SAI CHO: mau da do tren preview JPEG cua MAY — render o WB may
#        (K MakerNote 5000-5900). Lightroom render o WB preset (5950 / +19) roi
#        cong Saturation / Vibrance / toning cua preset: da trong LR am hon
#        preview ~0.5 stop va dam hon. Tool khong biet, cu the grade.
#     2. Grade SAI HUONG: hue 350 la DO-hong. Them vao da cam la them R -> da
#        DO va dam hon, khong "trang hong" hon. Da cam -> trang hong la BOT VANG
#        (OkLab b giam), tuc huong tim-hong — ma cung chi khi da con vang.
#
#   CACH MOI, tung anh (grade_theo_trang_thai):
#     1. Da trong LR = da do duoc, doi tu WB may sang WB CUOI (WB preset + phan
#        tool chinh) bang thuat toan nhiet do / tint cua Adobe DNG SDK — dung
#        thang so Lightroom hien — va thich nghi Bradford.
#     2. Cong Saturation / Vibrance va Color Grading SAN CO cua preset (OkLab;
#        banh xe mau Sat 100 = lech 0.09 OkLab, cung mo hinh lightcraft).
#     3. So voi mau dich o CUNG do sang -> chi XOAY hue ve phia mau dich (va bu
#        chroma neu da nhat hon dich), KHONG bot chroma: bot chroma bang grading
#        la nhuom mau doi dien len vung trang.
#     4. Vecto cua tool CONG vao banh xe preset (khong ghi de hue), ca midtone
#        lan highlight: da sang nam giua hai vung, Lightroom chia bao nhieu cho
#        moi vung thi da van nhan du mot vecto.
#]]

#: Bang Robertson (1968) trong Adobe DNG SDK (dng_temperature.cpp, kTempTable):
#: (r = 1e6/K, u, v, do doc t). Thanh Temperature / Tint cua Lightroom la thang nay.
_ROBERTSON = (
    (0, 0.18006, 0.26352, -0.24341), (10, 0.18066, 0.26589, -0.25479),
    (20, 0.18133, 0.26846, -0.26876), (30, 0.18208, 0.27119, -0.28539),
    (40, 0.18293, 0.27407, -0.30470), (50, 0.18388, 0.27709, -0.32675),
    (60, 0.18494, 0.28021, -0.35156), (70, 0.18611, 0.28342, -0.37915),
    (80, 0.18740, 0.28668, -0.40955), (90, 0.18880, 0.28997, -0.44278),
    (100, 0.19032, 0.29326, -0.47888), (125, 0.19462, 0.30141, -0.58204),
    (150, 0.19962, 0.30921, -0.70471), (175, 0.20525, 0.31647, -0.84901),
    (200, 0.21142, 0.32312, -1.0182), (225, 0.21807, 0.32909, -1.2168),
    (250, 0.22511, 0.33439, -1.4512), (275, 0.23247, 0.33904, -1.7298),
    (300, 0.24010, 0.34308, -2.0637), (325, 0.24702, 0.34655, -2.4681),
    (350, 0.25591, 0.34951, -2.9641), (375, 0.26400, 0.35200, -3.5814),
    (400, 0.27218, 0.35407, -4.3633), (425, 0.28039, 0.35577, -5.3762),
    (450, 0.28863, 0.35714, -6.7262), (475, 0.29685, 0.35823, -8.5955),
    (500, 0.30505, 0.35907, -11.324), (525, 0.31320, 0.35968, -15.628),
    (550, 0.32129, 0.36011, -23.325), (575, 0.32931, 0.36038, -40.770),
    (600, 0.33724, 0.36051, -116.45))
_TINT_SCALE = -3000.0                    # dng_temperature: kTintScale

_SRGB_XYZ = np.array([[0.4124564, 0.3575761, 0.1804375],
                      [0.2126729, 0.7151522, 0.0721750],
                      [0.0193339, 0.1191920, 0.9503041]])
_XYZ_SRGB = np.linalg.inv(_SRGB_XYZ)
_BRADFORD = np.array([[0.8951, 0.2664, -0.1614],
                      [-0.7502, 1.7135, 0.0367],
                      [0.0389, -0.0685, 1.0296]])
_BRADFORD_INV = np.linalg.inv(_BRADFORD)
#: Do lech OkLab cua mot banh xe Color Grading o Sat 100 (mo hinh lightcraft —
#: Adobe khong cong bo). Chi quyet dinh ghi bao nhieu diem Sat cho mot do lech
#: can co; tran grade_sat_max chan hai dau.
GRADE_OKLAB_100 = 0.09


def xy_adobe(temp: float, tint: float = 0.0) -> tuple[float, float]:
    """Nhiệt độ / tint THANG LIGHTROOM -> toạ độ xy (dng_temperature::Get_xy_coord).

    Kiểm: 2856 K tint 0 -> (0.4475, 0.4074), đúng nguồn sáng chuẩn A."""
    r = 1e6 / max(float(temp), 1000.0)
    off = float(tint) * (1.0 / _TINT_SCALE)
    B = _ROBERTSON
    for i in range(30):
        if r < B[i + 1][0] or i == 29:
            f = (B[i + 1][0] - r) / (B[i + 1][0] - B[i][0])
            u = B[i][1] * f + B[i + 1][1] * (1.0 - f)
            v = B[i][2] * f + B[i + 1][2] * (1.0 - f)
            n1, n2 = math.hypot(1.0, B[i][3]), math.hypot(1.0, B[i + 1][3])
            uu = (1.0 / n1) * f + (1.0 / n2) * (1.0 - f)
            vv = (B[i][3] / n1) * f + (B[i + 1][3] / n2) * (1.0 - f)
            n3 = math.hypot(uu, vv)
            u += uu / n3 * off
            v += vv / n3 * off
            d = u - 4.0 * v + 2.0
            return 1.5 * u / d, v / d
    return 0.3457, 0.3585                                    # khong toi duoc


def _non_trang(temp: float, tint: float) -> np.ndarray:
    """Đáp ứng nón (Bradford) của điểm trắng (temp, tint), Y = 1."""
    x, y = xy_adobe(temp, tint)
    return _BRADFORD @ np.array([x / y, 1.0, (1.0 - x - y) / y])


def doi_wb(rgb_lin, tu: tuple, sang: tuple) -> np.ndarray:
    """Màu (RGB tuyến tính sRGB) render ở WB `tu` -> cùng vật đó render ở WB `sang`.

    Đổi WB trong Lightroom = đổi điểm trắng được thích nghi về D65; hai lần render
    chênh nhau đúng một phép thích nghi Bradford nón(tu) / nón(sang). Tăng
    Temperature -> ảnh ẤM hơn, đúng chiều thanh trượt."""
    k = _non_trang(*tu) / _non_trang(*sang)
    xyz = _SRGB_XYZ @ np.asarray(rgb_lin, dtype=np.float64)
    return _XYZ_SRGB @ (_BRADFORD_INV @ (k * (_BRADFORD @ xyz)))


def oklab(rgb_lin) -> np.ndarray:
    """RGB tuyến tính sRGB -> OkLab (L, a, b)."""
    r, g, b = (max(float(v), 0.0) for v in rgb_lin)
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1.0 / 3.0)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1.0 / 3.0)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1.0 / 3.0)
    return np.array([0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
                     1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
                     0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_])


_BANG_HUE = None                         # (hue Lightroom, goc OkLab da mo vong)


def _bang_hue():
    """Hue của bánh xe Color Grading (0-359, như HSV) -> góc OkLab của màu gốc
    (H, S=1, V=1). Một bảng tính một lần.

    Vùng xanh lam (hue 231-240) góc OkLab gần như đứng yên và lùi ~0.03° — đặc
    điểm đã biết của OkLab. Ép đơn điệu (cộng một dốc rất nhỏ) để tra ngược
    được; sai khác chỉ trong vùng màu nhìn như nhau."""
    global _BANG_HUE
    if _BANG_HUE is None:
        import colorsys
        hs = np.arange(0.0, 360.0, 0.25)
        goc = [math.atan2(lab[2], lab[1]) for lab in
               (oklab(srgb_to_linear(np.array(colorsys.hsv_to_rgb(h / 360.0, 1.0, 1.0))))
                for h in hs)]
        g = np.maximum.accumulate(np.unwrap(np.asarray(goc)))
        _BANG_HUE = (hs, g + np.arange(len(g)) * 1e-9)
    return _BANG_HUE


def hue_lr_sang_oklab(hue: float) -> float:
    hs, goc = _bang_hue()
    return float(np.interp(float(hue) % 360.0, np.append(hs, 360.0),
                           np.append(goc, goc[0] + 2.0 * math.pi)))


def hue_oklab_sang_lr(goc: float) -> float:
    hs, g = _bang_hue()
    t = g[0] + (float(goc) - g[0]) % (2.0 * math.pi)
    return float(np.interp(t, np.append(g, g[0] + 2.0 * math.pi),
                           np.append(hs, 360.0))) % 360.0


def banh_xe(hue: float, sat: float) -> np.ndarray:
    """Bánh xe Color Grading (hue, sat) -> độ lệch OkLab (a, b) nó cộng vào."""
    s = max(float(sat), 0.0) / 100.0 * GRADE_OKLAB_100
    t = hue_lr_sang_oklab(hue)
    return np.array([s * math.cos(t), s * math.sin(t)])


def banh_xe_nguoc(v) -> tuple[int, int]:
    """Độ lệch OkLab (a, b) -> (hue, sat) nguyên của bánh xe. Quá nhỏ -> (0, 0)."""
    s = float(np.hypot(v[0], v[1])) / GRADE_OKLAB_100 * 100.0
    if s < 0.5:
        return 0, 0
    return int(round(hue_oklab_sang_lr(math.atan2(v[1], v[0])))) % 360, int(round(s))


def _theo_may(bang: dict | None, model: str, mac_dinh: float) -> float:
    """Tra bảng {tên máy: số} theo tên máy khớp DÀI nhất; khoá "" là số chung."""
    #  dict(...) boc ngoai: `(bang or {}).items()` voi bang la THAM SO lam
    #  Cython 3 crash khi annotation_typing=False (xem bao_mat.bien_dich_mot)
    b = {str(k).upper(): float(v) for k, v in dict(bang or {}).items()}
    m = str(model or "").upper()
    khop = [k for k in b if k and k in m]
    if khop:
        return b[max(khop, key=len)]
    return b.get("", mac_dinh)


def wb_may_adobe(r: dict, cfg: dict) -> tuple[float, float] | None:
    """WB MÁY đã dùng để render preview, THANG LIGHTROOM: (temp, tint); None nếu
    không biết.

    temp: As Shot thật trong catalog (ảnh đang As Shot Lightroom đã render), không
    thì K trong MakerNote quy sang thang Adobe (wb_asshot_lech_mired, như
    uoc_asshot). tint: số catalog nếu ảnh đang As Shot, không thì số mặc định theo
    máy (wb_asshot_tint — MakerNote không có tint)."""
    crs = r.get("crs") or {}
    t = float(r.get("asshot_K") or 0.0) or _asshot_catalog(crs)
    if t <= 0:
        k = _so(r.get("wb_may_K"))
        if not k or k <= 0:
            return None
        lech = _theo_may(cfg.get("wb_asshot_lech_mired"), str(r.get("model") or ""), 0.0)
        t = 1e6 / max(1e6 / float(k) + lech, 20.0)
    if _asshot_catalog(crs) > 0 and str(crs.get("Tint", "")).strip() != "":
        ti = get_f(crs, "Tint", 0.0)
    else:
        ti = _theo_may(cfg.get("wb_asshot_tint"), str(r.get("model") or ""), 10.0)
    return float(t), float(ti)


def _wheel_preset(crs: dict) -> dict:
    """Bốn bánh xe Color Grading của preset -> {vùng: vecto OkLab}."""
    def v(kh, ks):
        return banh_xe(get_f(crs, kh, 0.0), get_f(crs, ks, 0.0))
    return {"bong": v("SplitToningShadowHue", "SplitToningShadowSaturation"),
            "giua": v("ColorGradeMidtoneHue", "ColorGradeMidtoneSat"),
            "sang": v("SplitToningHighlightHue", "SplitToningHighlightSaturation"),
            "chung": v("ColorGradeGlobalHue", "ColorGradeGlobalSat")}


#: Phan cua moi vung Color Grading roi len DA khi du doan tac dong cua preset.
#: Da sang (trang hong) nam giua midtone va highlight; Adobe khong cong bo mat na
#: vung — chia doi la gia dinh trung dung, ghi ro o day de con chinh.
_VUNG_DA = {"bong": 0.0, "giua": 0.5, "sang": 0.5, "chung": 1.0}


def mau_dich_lab(ref_rgb) -> np.ndarray:
    """Màu đích (sRGB 0-255) -> OkLab."""
    return oklab(srgb_to_linear(np.asarray(ref_rgb, dtype=np.float64) / 255.0))


def _ap_hsl_lab(c: float, h: float, doi: dict, cfg: dict) -> tuple[float, float]:
    """(chroma, góc OkLab) của DA sau khi HSL ở dải da ĐỔI THÊM `doi` điểm so với
    preset ({HueAdjustmentX: Δ, SaturationAdjustmentX: Δ}). Phản ứng ĐO trên da thật
    (v43 -> v46, 8/10 đêm: Hue -33 / Sat +50 -> da -13.8° / ×1.72): hsl_da_k_hue độ
    OkLab / điểm Hue, ln(chroma) hsl_da_k_sat / điểm Sat. Chỉ dùng cho dải chứa da —
    tool chỉ ghi dải đó."""
    if not doi:
        return c, h
    dh = sum(float(v or 0.0) for k, v in doi.items() if k.startswith("HueAdjustment"))
    ds = sum(float(v or 0.0) for k, v in doi.items() if k.startswith("SaturationAdjustment"))
    if not dh and not ds:
        return c, h
    return (c * math.exp(float(cfg.get("hsl_da_k_sat") or 0.01085) * ds),
            h + math.radians(float(cfg.get("hsl_da_k_hue") or 0.418) * dh))


def da_trong_lr(r: dict, cfg: dict, crs: dict, temp: float, tint: float,
                ref_rgb=None, hsl: dict | None = None) -> np.ndarray | None:
    """Màu da DỰ ĐOÁN trong Lightroom (OkLab) khi ảnh ở WB (temp, tint) và mang
    Saturation / Vibrance / Color Grading của `crs`. Đưa về CÙNG độ sáng với màu
    đích (chỉ so màu, không so sáng tối). None = không có màu da đo được.

    HSL CỦA PRESET không mô hình riêng: ảnh hưởng của nó nằm sẵn trong hệ số
    hsl_da_chroma_lr (đo trên ảnh Lightroom vẽ thật có preset đó). `hsl`: sáu ô HSL
    MỚI (vd r["hsl_moi"]) — mô hình PHẦN ĐỔI so với preset (_ap_hsl_lab). Đây là cách
    "đo lại" da SAU bước HSL trước khi quyết định Color Grading — xem chinh_mau_da().

    Không biết WB máy thì coi preview đã render ở chính (temp, tint) — tức như
    cách cũ, không đổi gì về WB."""
    f = r.get("face_rgb")
    if not f:
        return None
    rgb = np.asarray(f, dtype=np.float64)
    may = wb_may_adobe(r, cfg)
    if may is not None and temp > 0:
        rgb = doi_wb(rgb, may, (float(temp), float(tint)))
    rgb = np.maximum(rgb, 1e-6)
    ref = srgb_to_linear(np.asarray(ref_rgb if ref_rgb is not None else cfg["skin_ref_rgb"],
                                    dtype=np.float64) / 255.0)
    y_ref = float(_SRGB_XYZ[1] @ ref)
    y = float(_SRGB_XYZ[1] @ rgb)
    if y > 0:
        rgb = rgb * (y_ref / y)
    lab = oklab(rgb)
    c, h = float(math.hypot(lab[1], lab[2])), float(math.atan2(lab[2], lab[1]))
    vib = get_f(crs, "Vibrance", 0.0) / 100.0
    sat = get_f(crs, "Saturation", 0.0) / 100.0
    if vib:
        #  Vibrance day mau NHAT manh hon, va CHE da (nhu lightcraft / Lightroom)
        low = 1.0 - min(c / 0.22, 1.0)
        da = hue_lr_sang_oklab(25.0)
        lech = (h - da + math.pi) % (2.0 * math.pi) - math.pi
        che = 1.0 - 0.6 * math.exp(-(lech / 0.35) ** 2) if vib > 0 else 1.0
        c *= max(1.0 + vib * low * low * che * 1.2, 0.0)
    if sat:
        c *= max(1.0 + sat, 0.0)
    #  HSL tool doi them (Lightroom ap sau Saturation / Vibrance, truoc Color Grading)
    if hsl:
        doi = {k: float(dict(hsl).get(k, get_f(crs, k, 0.0))) - get_f(crs, k, 0.0) for k in COT_HSL}
        c, h = _ap_hsl_lab(c, h, doi, cfg)
    ab = np.array([c * math.cos(h), c * math.sin(h)])
    for vung, vec in _wheel_preset(crs).items():
        ab = ab + _VUNG_DA[vung] * vec
    return np.array([lab[0], ab[0], ab[1]])


def dich_da(cfg: dict) -> tuple:
    """(đích da TRONG NHÀ, đích da NGOÀI TRỜI) — sRGB 0-255.

    Bật "Đẩy tone về da trắng hồng" (grade) hoặc da_trang_hong: đích trắng hồng
    học từ ảnh kỷ yếu người dùng đã duyệt (skin_ref_rgb_hong[_ngoai]). Không bật:
    đích thường (skin_ref_rgb / skin_ref_rgb_ngoai) như trước."""
    #[[ 8/10 dem: KY YEU KHONG DOI WB THEO O "grade" nua. WB la buoc 1 cua chuoi
    #   (chinh_mau_da): dich thuong + wb_bu_ky_yeu (do tren pixel trung tinh, v43
    #   -> v44), con phan da lech thi HSL roi Color Grading xu ly noi tiep. Bat
    #   Color Grading ma WB cung doi dich thi hai buoc lai de len nhau. ]]
    if (cfg.get("grade") or cfg.get("da_trang_hong")) and cfg.get("loai_buoi") != "ky_yeu":
        trong = cfg.get("skin_ref_rgb_hong") or cfg["skin_ref_rgb"]
        return trong, cfg.get("skin_ref_rgb_hong_ngoai") or trong
    return cfg["skin_ref_rgb"], cfg.get("skin_ref_rgb_ngoai") or cfg["skin_ref_rgb"]


def dich_da_cuoi(cfg: dict) -> tuple:
    """Màu da CUỐI muốn thấy (trong, ngoài) — HSL kênh da và Color Grading cùng nhắm
    vào đây (một đích cho cả chuỗi, xem chinh_mau_da). Kỷ yếu / bật trắng hồng:
    màu da ảnh duyệt (skin_dich_hong[_ngoai]); không thì như dich_da."""
    if cfg.get("grade") or cfg.get("da_trang_hong") or cfg.get("loai_buoi") == "ky_yeu":
        trong = cfg.get("skin_dich_hong") or dich_da(cfg)[0]
        return trong, cfg.get("skin_dich_hong_ngoai") or trong
    return dich_da(cfg)


#: Bon o Color Grading tool ghi (cong vecto vao so goc cua preset).
COT_GRADE = ("ColorGradeMidtoneHue", "ColorGradeMidtoneSat",
             "SplitToningHighlightHue", "SplitToningHighlightSaturation")


def _grade_goc(r: dict) -> dict:
    """Số GỐC (trước khi tool chạm tới) của bốn ô Color Grading tool ghi."""
    crs, atn = r.get("crs") or {}, r.get("atn") or {}
    out = {}
    for k in COT_GRADE:
        mk = ATN_FIELDS.get(k)
        out[k] = get_f(atn, mk, 0.0) if mk and mk in atn else get_f(crs, k, 0.0)
    return out


def grade_theo_trang_thai(items: list, cfg: dict) -> int:
    """Color Grading theo TRẠNG THÁI từng ảnh — xem chú thích đầu mục. Chạy SAU
    compute_values (cần WB cuối new_temp / new_tint). Gán:

        r["gr_ghi"]           True = ghi Color Grading cho ảnh này
        r["gr_mid"], r["gr_hi"]  (hue, sat) MỚI của bánh xe midtone / highlight
        r["gr_hue"], r["gr_sat"] vecto CỦA TOOL (bảng, CSV, Chi tiết)

    Trả về số ảnh có grade.

    #[[ TRA VE SO GOC: anh lan truoc da bi tool grade (r["da_grade"], xem
    #   attach_catalog_settings) ma lan nay khong grade — tat Color Grading, anh
    #   B/W, da da dung mau — thi GHI LAI so goc. Truoc day tat Color Grading la
    #   khong ghi o nao, nen hue 350 cua lan bat truoc nam lai trong catalog mai.
    #
    #   KHONG BIET SO GOC thi KHONG GHI: ban xuat tu plugin cu khong co cac cot
    #   Color Grading -> coi la 0 thi xoa mat toning cua preset (Bong22:
    #   Highlights 36/10). r["gr_thieu_cot"] de giao dien nhac Reload plugin. ]]
    """
    gain = float(cfg.get("grade_gain_hue", 0.45))
    sat_max = float(cfg.get("grade_sat_max", 12))
    nguong = float(cfg.get("grade_nguong_hue", 0.0) or 0.0)
    tran = sat_max / 100.0 * GRADE_OKLAB_100
    #  Cung DICH voi WB cua tung anh (trong / ngoai) — hai dich keo nguoc nhau
    #  thi grade xoay da di mot huong, WB keo ve huong kia
    ref_trong, ref_ngoai = dich_da_cuoi(cfg)
    #  Cung hue dich voi buoc HSL (hue_da_dich) — hai buoc ma nham hai dich thi
    #  Color Grading keo nguoc cai HSL vua lam
    h_trong = hue_da_dich(cfg, ref_trong)
    h_ngoai = hue_da_dich(cfg, ref_ngoai)
    catalog = cfg.get("source") == "catalog"
    for r in items:
        for key in ("gr_ghi", "gr_mid", "gr_hi", "_gr_v", "gr_thieu_cot", "da_lech1"):
            r.pop(key, None)
        r["gr_hue"] = r["gr_sat"] = 0
        if catalog and r.get("crs") and "SplitToningHighlightSaturation" not in r["crs"]:
            r["gr_thieu_cot"] = True
            if r.get("da_grade"):
                #  Midtone dang mang hue 350 cua tool cu, so goc coi la 0 / 0 (xem
                #  bu_cot_mau) -> tra ve. Highlight: tool cu chua dung, de nguyen.
                r["gr_mid"], r["gr_ghi"] = (0, 0), True
            continue
        if r.get("bw") or not r.get("new_temp"):
            continue
        ngoai = _nhan_da_ngoai(r, cfg)
        #[[ DO LAI trang thai da SAU buoc HSL (r["hsl_moi"] = HSL goc + phan tool
        #   chinh; chua chinh thi HSL cua preset) — Color Grading chi xu ly PHAN
        #   CON LECH, khong tinh lai tu cung trang thai voi HSL. Xem chinh_mau_da(). ]]
        lab = da_trong_lr(r, cfg, r.get("crs") or {}, r["new_temp"], r.get("new_tint", 0),
                          ref_ngoai if ngoai else ref_trong, hsl=r.get("hsl_moi"))
        if lab is None:
            continue
        h_t = h_ngoai if ngoai else h_trong
        ab = lab[1:]
        if float(math.hypot(ab[0], ab[1])) <= 1e-6:
            continue
        h_p = hue_da_du_doan(lab, cfg)
        d = (h_t - h_p + math.pi) % (2.0 * math.pi) - math.pi
        r["da_lech1"] = round(math.degrees(d), 1)        # hue da con lech dich, sau HSL
        if not cfg.get("grade"):
            continue
        #[[ XOAY hue da ve phia hue dich, giu chroma: vecto theo TIEP TUYEN tai
        #   mau da, do manh ti le voi so do hue con lech QUA NGUONG grade_nguong_hue
        #   (grade_gain_hue diem Sat / do, tran grade_sat_max). Do tren raw 19.4:
        #   da du doan trong LR o hue OkLab ~45 do, dich trang hong 17 do — mot
        #   banh xe Sat 12 chi xoay duoc ~5 do, nen lay "dong het khoang cach" thi
        #   anh nao cung cham tran va thanh mot mau co dinh. Ti le theo do lech
        #   thi da lech it grade nhe. KHONG bot chroma: bot chroma bang grading la
        #   nhuom mau doi dien len vung trang.
        #   8/10 dem (user): nguong 4 do + tinh tren PHAN VUOT + tran 8 — Color
        #   Grading doi mau CA KHUNG nen chi dung khi HSL da lam het phan cua no
        #   ma da van con lech ro. ]]
        vuot = abs(math.degrees(d)) - nguong
        if vuot <= 0:
            continue
        sat = min(gain * vuot, sat_max)
        if sat < 1.0:
            continue
        huong = h_p + math.copysign(math.pi / 2.0, d)
        r["_gr_v"] = sat / 100.0 * GRADE_OKLAB_100 * np.array([math.cos(huong),
                                                                math.sin(huong)])

    #  San phang trong canh nhu WB / Exposure: cung cho chup thi cung mot vecto
    lvl = float(cfg.get("scene_level", 0.0))
    if lvl > 0:
        by_scene: dict = {}
        for r in items:
            if "_gr_v" in r:
                by_scene.setdefault(r.get("scene"), []).append(r)
        for g in by_scene.values():
            if len(g) < int(cfg.get("scene_level_min", 4)):
                continue
            med = np.median(np.asarray([r["_gr_v"] for r in g]), axis=0)
            for r in g:
                r["_gr_v"] = r["_gr_v"] + (med - r["_gr_v"]) * lvl
    #  Cung LOAT (chup lien, cung bo cuc / anh sang) -> cung MOT vecto, ke ca tam
    #  khong thay mat — nhu dong_bo_loat lam voi Exposure / WB
    if cfg.get("dong_bo_loat") and cfg.get("grade"):
        for g in chia_loat(items, cfg):
            vs = [r["_gr_v"] for r in g if "_gr_v" in r]
            if not vs:
                continue
            med = np.median(np.asarray(vs), axis=0)
            for r in g:
                if not r.get("bw") and not r.get("gr_thieu_cot") and r.get("new_temp"):
                    r["_gr_v"] = med

    n = 0
    for r in items:
        v = r.pop("_gr_v", None)
        if r.get("gr_thieu_cot"):
            continue
        goc = _grade_goc(r)
        if v is not None:
            dai = float(math.hypot(v[0], v[1]))
            if dai > tran:
                v = v * (tran / dai)
            r["gr_hue"], r["gr_sat"] = banh_xe_nguoc(v)
        if v is not None and r["gr_sat"] >= 1:
            r["gr_mid"] = banh_xe_nguoc(banh_xe(goc["ColorGradeMidtoneHue"],
                                                goc["ColorGradeMidtoneSat"]) + v)
            r["gr_hi"] = banh_xe_nguoc(banh_xe(goc["SplitToningHighlightHue"],
                                               goc["SplitToningHighlightSaturation"]) + v)
            r["gr_ghi"] = True
            n += 1
            if "grade-trang-hong" not in str(r.get("notes", "")):
                r["notes"] = (str(r.get("notes", "")) + f";grade-trang-hong:"
                              f"{r['gr_hue']}/{r['gr_sat']}").strip(";")
        elif r.get("da_grade"):
            r["gr_mid"] = (int(goc["ColorGradeMidtoneHue"]), int(goc["ColorGradeMidtoneSat"]))
            r["gr_hi"] = (int(goc["SplitToningHighlightHue"]),
                          int(goc["SplitToningHighlightSaturation"]))
            r["gr_ghi"] = True
    return n


#: Tam cac dai HSL cua Lightroom (hue kieu HSV, do).
TAM_HSL = (("Red", 0.0), ("Orange", 30.0), ("Yellow", 60.0), ("Green", 120.0),
           ("Aqua", 180.0), ("Blue", 240.0), ("Purple", 270.0), ("Magenta", 300.0))
#: Ket qua HSL kenh da cua lan plan() gan nhat — giao dien doc de noi ra.
HSL_DA: dict = {}


def trong_so_hsl(hue: float) -> dict:
    """Trọng số các dải HSL Lightroom tại một hue (HSV, độ): nội suy tuyến tính
    giữa hai tâm dải kề nhau (vòng tròn)."""
    h = float(hue) % 360.0
    for i in range(len(TAM_HSL)):
        ten0, t0 = TAM_HSL[i]
        ten1, t1 = TAM_HSL[(i + 1) % len(TAM_HSL)]
        t1 = t1 if t1 > t0 else 360.0
        if t0 <= h < t1:
            x = (h - t0) / (t1 - t0)
            return {ten0: 1.0 - x, ten1: x}
    return {TAM_HSL[0][0]: 1.0}


def hue_da_dich(cfg: dict, ref_rgb) -> float:
    """Hue (radian OkLab) của da ĐÍCH cho chuỗi màu da. Kỷ yếu: hue đo từng điểm trên
    da ảnh mẫu (hsl_da_dich_hue); không thì hue của màu đích ref_rgb."""
    h = float(cfg.get("hsl_da_dich_hue") or 0.0)
    if cfg.get("loai_buoi") == "ky_yeu" and h:
        return math.radians(h)
    t = mau_dich_lab(ref_rgb)
    return float(math.atan2(t[2], t[1]))


def hue_da_du_doan(lab, cfg: dict) -> float:
    """Hue (radian) da dự đoán (da_trong_lr), bù độ lệch mô hình đo trên Lightroom
    vẽ thật (hsl_da_hue_bu) — chỉ Kỷ yếu, nơi đã đo."""
    h = float(math.atan2(lab[2], lab[1]))
    if cfg.get("loai_buoi") == "ky_yeu":
        h += math.radians(float(cfg.get("hsl_da_hue_bu") or 0.0))
    return h


def _hsl_goc(r: dict) -> dict:
    """Số GỐC (mốc, trước khi tool chạm tới) của sáu ô HSL kênh da."""
    crs = r.get("crs") or {}
    return {k: get_f(crs, k, 0.0) for k in COT_HSL}


def hsl_da_theo_trang_thai(items: list, cfg: dict) -> dict:
    """HSL KÊNH DA (Loại buổi Kỷ yếu). Chạy SAU compute_values (cần WB cuối).

    1. Màu da DỰ ĐOÁN trong Lightroom ở WB cuối (da_trong_lr) của từng ảnh có mặt,
       so với màu da đích học từ ảnh hoàn thiện (skin_dich_hong[_ngoai]).
    2. KÊNH DA = dải (Red / Orange / Yellow) có trọng số trung vị lớn nhất tại hue
       da đo được — thường là Orange. Chỉ ghi dải đó; hai dải kia giữ số gốc.
    3. Lệch hue / tỉ lệ chroma cần ở TÂM dải = lệch tại hue da / trọng số dải ở đó.
       Trung vị cả buổi -> MỘT mức (xem DEFAULTS: theo từng ảnh không tốt hơn).
    4. Mọi ảnh màu của buổi (kể cả ảnh không mặt) nhận cùng mức, cộng vào số gốc.
       Ảnh tool đã từng ghi HSL (r["da_hsl"]) mà lần này không chỉnh -> trả số gốc.

    Gán r["hsl_ghi"], r["hsl_moi"] {cột: số mới}; r["da_lech0"] = (lệch hue độ OkLab,
    tỉ lệ chroma so đích) của da SAU WB + Tone cho mọi ảnh màu có mặt — kể cả khi
    HSL tắt (trạng thái để giao diện nói ra). Trả về {"dai","hue","sat","n"}."""
    for r in items:
        for key in ("hsl_ghi", "hsl_moi", "hsl_thieu_cot", "da_lech0"):
            r.pop(key, None)
    kq = {"dai": "", "hue": 0, "sat": 0, "n": 0, "bat": False}
    catalog = cfg.get("source") == "catalog"
    bat = bool(catalog and cfg.get("loai_buoi") == "ky_yeu" and cfg.get("hsl_da_ky_yeu"))
    kq["bat"] = bat
    for r in items:
        #  Ban xuat cua plugin CU khong co cot HSL: khong biet so goc -> khong ghi
        if catalog and r.get("crs") and "HueAdjustmentOrange" not in r["crs"]:
            r["hsl_thieu_cot"] = True
    #  1. DO trang thai da sau WB + Tone (cung dich voi Color Grading: dich_da_cuoi,
    #     hue_da_dich). Lech = (dich - du doan) do OkLab, ti le chroma dich / du doan.
    k_c = float(cfg.get("hsl_da_chroma_lr") or 1.0)
    ref_trong, ref_ngoai = dich_da_cuoi(cfg)
    mau = []
    for r in items:
        if r.get("bw") or not r.get("new_temp") or not r.get("face_rgb"):
            continue
        ref = ref_ngoai if _nhan_da_ngoai(r, cfg) else ref_trong
        lab = da_trong_lr(r, cfg, r.get("crs") or {}, r["new_temp"], r.get("new_tint", 0), ref)
        if lab is None:
            continue
        t_lab = mau_dich_lab(ref)
        c_p = float(math.hypot(lab[1], lab[2])) * k_c
        if c_p <= 1e-6:
            continue
        h_p = math.degrees(hue_da_du_doan(lab, cfg))
        h_t = math.degrees(hue_da_dich(cfg, ref))
        c_t = float(math.hypot(t_lab[1], t_lab[2]))
        r["da_lech0"] = (round((h_t - h_p + 180.0) % 360.0 - 180.0, 1), round(c_t / c_p, 3))
        if not r.get("hsl_thieu_cot"):
            mau.append((h_p, h_t, c_p, c_t))
    #[[ 2. HSL kenh da — chi khi bat va trung vi lech VUOT vung "da on" (da_on_*).
    #   Muc tinh THANG bang phan ung do tren da (hsl_da_k_hue / hsl_da_k_sat):
    #   khong chia trong so dai nua — phan ung do da gom ca do phu cua dai Orange
    #   len da (v46: chia trong so ~0.6 la lam muc gap ~1.6 lan, cong voi Sat manh
    #   gap 2.7 lan gia dinh -> da do han). ]]
    dai, hue, sat = "", 0, 0
    if bat and len(mau) >= int(cfg.get("hsl_da_min_anh") or 1):
        ts = [trong_so_hsl(hue_oklab_sang_lr(math.radians(m[0]))) for m in mau]
        w_tv = {d: float(np.median([float(dict(w).get(d, 0.0)) for w in ts])) for d in DAI_HSL_DA}
        dai = max(DAI_HSL_DA, key=lambda d: w_tv[d])
        lech_h = [x[0] for x in (r.get("da_lech0") for r in items) if x]
        lech_c = [x[1] for x in (r.get("da_lech0") for r in items) if x]
        on_h = abs(float(np.median(lech_h))) <= float(cfg.get("da_on_hue") or 0.0)
        on_c = abs(float(np.median(lech_c)) - 1.0) <= float(cfg.get("da_on_chroma") or 0.0)
        k_h = float(cfg.get("hsl_da_k_hue") or 0.418)
        k_s = float(cfg.get("hsl_da_k_sat") or 0.01085)
        us = [((h_t - h_p + 180.0) % 360.0 - 180.0) / k_h for h_p, h_t, _c, _t in mau]
        vs = [math.log(c_t / c_p) / k_s for _h, _t, c_p, c_t in mau]
        hm_ = float(cfg.get("hsl_da_hue_max") or 40)
        sm_ = float(cfg.get("hsl_da_sat_max") or 30)
        hue = 0 if on_h else int(round(float(np.clip(float(np.median(us)), -hm_, hm_))))
        sat = 0 if on_c else int(round(float(np.clip(float(np.median(vs)), -sm_, sm_))))
    n = 0
    for r in items:
        if r.get("hsl_thieu_cot"):
            continue
        goc = _hsl_goc(r)
        if dai and (hue or sat) and not r.get("bw"):
            moi = dict(goc)
            moi[f"HueAdjustment{dai}"] = float(np.clip(goc[f"HueAdjustment{dai}"] + hue, -100, 100))
            moi[f"SaturationAdjustment{dai}"] = float(np.clip(goc[f"SaturationAdjustment{dai}"] + sat,
                                                              -100, 100))
            r["hsl_moi"], r["hsl_ghi"] = moi, True
            n += 1
            nhan = f"hsl-da:{dai}{hue:+d}/{sat:+d}"
            if nhan not in str(r.get("notes", "")):
                r["notes"] = (str(r.get("notes", "")) + ";" + nhan).strip(";")
        elif r.get("da_hsl"):
            r["hsl_moi"], r["hsl_ghi"] = goc, True
    kq.update(dai=dai, hue=hue, sat=sat, n=n)
    return kq


#: Trang thai mau da cua lan plan() gan nhat — giao dien doc. Xem chinh_mau_da().
MAU_DA: dict = {}


def chinh_mau_da(items: list, cfg: dict) -> dict:
    """QUY TRÌNH CHUẨN chỉnh MÀU DA sau WB + Tone (8/10 đêm, user). Chạy SAU
    compute_values (cần WB cuối). Bốn bước, nối tiếp, không bao giờ song song:

        1. ĐO    : da dự đoán trong Lightroom ở WB cuối, mang HSL / Saturation /
                   Vibrance / toning của preset -> r["da_lech0"] (hue, chroma so đích)
        2. HSL   : kênh da (Kỷ yếu), MỘT mức cả buổi, chỉ khi trung vị lệch vượt
                   da_on_hue / da_on_chroma — da đã ổn thì không đụng
        3. ĐO LẠI: da sau HSL (da_trong_lr với r["hsl_moi"]) -> r["da_lech1"]
        4. CG    : Color Grading (ô "Đẩy tone về da trắng hồng") chỉ cho ảnh còn
                   lệch > grade_nguong_hue, tính trên phần vượt, trần grade_sat_max

    #[[ VI SAO: truoc 8/10 dem, HSL va Color Grading cung tinh tu trang thai sau
    #   WB + Tone — cung thay mot do lech va cung sua no -> de mau len nhau. User:
    #   "sau khi can WB va Tone xong phai biet da dang o mau nao roi moi can thiep
    #   HSL / Color Grading; da da on thi khong doi; Color Grading phai siet chat
    #   hon vi mot thay doi nho doi mau ca buc anh". ]]
    Trả về tóm tắt cho giao diện (cũng gán MAU_DA / HSL_DA)."""
    global HSL_DA, MAU_DA
    HSL_DA = hsl_da_theo_trang_thai(items, cfg)
    n_gr = grade_theo_trang_thai(items, cfg)
    l0 = [r["da_lech0"] for r in items if r.get("da_lech0")]
    l1 = [r["da_lech1"] for r in items if r.get("da_lech1") is not None]
    MAU_DA = {
        "n": len(l0),
        "hue0": float(np.median([x[0] for x in l0])) if l0 else 0.0,
        "chroma0": float(np.median([x[1] for x in l0])) if l0 else 1.0,
        "hsl": dict(HSL_DA),
        "hue1": float(np.median(l1)) if l1 else 0.0,
        "grade_bat": bool(cfg.get("grade")),
        "grade_n": int(n_gr),
    }
    return MAU_DA


def decide(items: list, cfg: dict) -> None:
    """Tính delta cho từng ảnh; ghi kết quả vào chính dict của ảnh."""
    mode = cfg["mode"]
    # Preset KHONG ap WB / Tone thi tinh tren nen SAY — xem nen_cho_anh()
    for r in items:
        r["crs_nen"] = nen_cho_anh(r.get("crs") or {}, cfg)

    #[[ WB THEO TRANG THAI (8/10, buoi ky yeu raw 19.4, preset Custom 5950 / +19).
    #
    #   Mau da do tren preview cua MAY — render o WB may (Auto: 5000-5900 K).
    #   Lightroom render o WB PRESET: 5950 / +19 am hon preview ~0.46 stop o anh
    #   may dat 5000 K, gan nhu bang o anh may dat 5900 K. Tool khong biet nen
    #   thay da "con lanh" va CONG them K (trung vi +95 K, nguoi dung: "WB tang K
    #   qua nhieu"), va hai anh cung mot cho chup ma may chon WB khac nhau thi
    #   lech nhau trong Lightroom ma tool khong thay.
    #
    #   Nay: da dung de can = da DU DOAN trong Lightroom o WB preset (doi_wb, mo
    #   hinh Adobe DNG SDK). Chi khi preset DAT WB (Custom / Daylight...): quy
    #   trinh preset bo trong WB (nen_wb, anh dang As Shot) da co _wb_theo_asshot
    #   keo ve As Shot — cong them o day la tinh hai lan. Preset 5250 ma may dat
    #   ~5250 (cac buoi da hieu chinh) thi phep doi ~0: khong doi gi.
    #
    #   Do manh tuong duong nhanh As Shot: skin_gain 0.6 x 900 K/stop tren phan
    #   doi WB may -> preset (~2000 K/stop quanh 5500 K) ~ keo 27% ve WB may, nhanh
    #   As Shot keo 35% (wb_asshot_pull) — cung mot y, hai quy trinh gan nhau.
    #
    #   CHI NGUON CATALOG: moc _autotone_baseline.tsv giu WhiteBalance GOC nen lan
    #   chay lai biet anh von As Shot hay Custom. Duong sidecar ghi xong thi .xmp
    #   mang WB Custom cua tool, moc atn khong giu WhiteBalance -> lan chay lai
    #   tuong preset dat WB, tinh khac lan dau (test_preset_khong_wb_tone). ]]
    for r in items:
        r.pop("_da_lr", None)
        r.pop("wb_trang_thai", None)
        f = r.get("face_rgb")
        if (not f or not cfg.get("wb_theo_trang_thai", True)
                or cfg.get("source") != "catalog"):
            continue
        crs_n = r["crs_nen"]
        if crs_n.get("__nen_wb"):
            continue
        t, ti = preset_val(r, "Temperature"), preset_val(r, "Tint")
        may = wb_may_adobe(r, cfg)
        if t > 0 and may is not None:
            r["_da_lr"] = [float(x) for x in np.maximum(doi_wb(f, may, (t, ti)), 1e-6)]
            r["wb_trang_thai"] = round(float(may[0])), round(float(may[1]))

    #[[ Quy hai thang đo về một.
    #
    #   Ở chế độ "face", ảnh thấy mặt đo theo độ sáng khuôn mặt, ảnh không thấy mặt
    #   phải lùi về đo theo chủ thể — hai con số này KHÔNG so trực tiếp được. Cứ lấy
    #   trung vị chung là hỏng: một cảnh nửa có mặt nửa không sẽ bị lệch cả loạt.
    #
    #   Nên đo độ lệch trung bình giữa hai thang trên chính những ảnh có cả hai, rồi
    #   cộng bù cho ảnh chỉ có thang chủ thể.
    #]]
    _tra_mat_goc(items)
    if cfg["meter"] == "face":
        sua_mat_lech_khung(items, cfg)
        # Muc 4 truoc (hieu chinh tung may), muc 1 sau (dong thuan trong cung
        # may) — dao lai thi muc 1 lay trung vi tren so chua hieu chinh.
        bu_do_theo_may(items, cfg)
        do_mat_theo_anh_sang(items, cfg)

        def _offset(key):
            d = [r["metered_face_ev"] - r[key] for r in items
                 if r.get("metered_face_ev") is not None and r.get(key) is not None]
            return float(np.median(d)) if d else 0.0

        off_focus, off_subject = _offset("metered_focus_ev"), _offset("metered_subject_ev")
        for r in items:
            if r.get("metered_face_ev") is not None:
                continue
            if r.get("metered_focus_ev") is not None:
                r["metered_ev"] = r["metered_focus_ev"] + off_focus
            else:
                r["metered_ev"] = r["metered_subject_ev"] + off_subject
            r["scale_shifted"] = True

    by_scene: dict[int, list] = {}
    for r in items:
        by_scene.setdefault(r["scene"], []).append(r)

    batch_anchor = float(np.median([r["metered_ev"] for r in items]))
    # Đo theo mặt thì mốc tuyệt đối phải là mức sáng của DA MẶT, không phải mức
    # sáng cả khung — hai thang khác nhau, dùng nhầm là lệch cả loạt.
    abs_target = float(cfg["face_target_ev"] if cfg["meter"] == "face"
                       else cfg["target_ev"])

    for sid, group in by_scene.items():
        scene_anchor = float(np.median([r["metered_ev"] for r in group]))

        if mode == "scene":
            target = scene_anchor
        elif mode == "batch":
            target = batch_anchor
        elif mode == "absolute":
            target = abs_target
        else:  # hybrid
            w = float(cfg["blend"])
            target = (1 - w) * scene_anchor + w * abs_target

        scene_cast = np.median([wb_cast(r["rgb_mean"]) for r in group], axis=0)

        # Màu da đo được của cả cảnh (trung vị cho ổn định), so với màu da đích
        skin_temp_ev = skin_tint_ev = None
        theo_may: dict = {}
        #[[ NGOAI TROI VA TRONG NHA CAN HAI MAU DA DICH KHAC NHAU.
        #
        #   Ngoai nang, da AM len la that va la cai dang giu. Trong nha den vang,
        #   da am len la do den va la cai phai khu. Cung mot phep do, hai hanh
        #   dong nguoc nhau — nen mot mau dich chung bao gio cung sai mot ben.
        #
        #   Tach bang ISO (xem ngoai_troi()). Anh nao khong ro thi ve nhom trong
        #   nha, vi do la truong hop pho bien cua anh su kien.
        #
        #   Chua dat mau dich ngoai troi thi ca hai nhom dung chung mot so, tuc
        #   hanh vi y het truoc day — doi nay khong tu no lam thay doi gi.
        #]]
        if cfg["wb"] == "skin":
            def _lech(mau: list, ref_rgb):
                if not mau:
                    return None, None
                meas = np.median(np.asarray(mau, dtype=np.float64), axis=0)
                ref = srgb_to_linear(np.asarray(ref_rgb, dtype=np.float64)
                                     / 255.0) + EPS
                mt, mi = wb_cast(meas)
                rt, ri = wb_cast(ref)
                return mt - rt, mi - ri

            #[[ 8/10 KY YEU / CONCEPT TRANG HONG: dich da ngoai troi la da RAM
            #   ([166,123,105], hoc tu anh PUBGday2 nguoi dung duyet) — dung cho
            #   anh su kien. Buoi ky yeu concept muon da TRANG HONG ca ngoai nang:
            #   che do "Ca buoi anh sang ngay" xep MOI anh vao nhom ngoai troi nen
            #   ca buoi bi keo ve da ram, cong K (raw 19.4: trung vi +95 K, anh
            #   ngoai troi +200..+340 K). Bat "Day tone ve da trang hong" (grade)
            #   hoac da_trang_hong -> mot dich hong cho moi anh. Chi doi DICH o
            #   day; phan loai ngoai troi (_nhan_da_ngoai) giu nguyen. ]]
            ref_trong, ref_ngoai = dich_da(cfg)

            def _hai_nhom(ds):
                #  _da_lr: da du doan trong Lightroom o WB preset (dau decide)
                m_trong = [r.get("_da_lr") or r["face_rgb"] for r in ds
                           if r.get("face_rgb") and not _nhan_da_ngoai(r, cfg)]
                m_ngoai = [r.get("_da_lr") or r["face_rgb"] for r in ds
                           if r.get("face_rgb") and _nhan_da_ngoai(r, cfg)]
                lt = _lech(m_trong, ref_trong)
                ln = _lech(m_ngoai, ref_ngoai)
                #[[ Nhom nao trong thi muon so cua nhom kia — mot canh chi co anh
                #   ngoai troi van phai can duoc. Khong co ca hai thi ve None, va
                #   _skin_wb() se lui ve nhanh "khong thay mat".
                #]]
                if lt[0] is None:
                    lt = ln
                if ln[0] is None:
                    ln = lt
                return lt, ln

            lech_trong, lech_ngoai = _hai_nhom(group)
            #[[ MUC 2 — wb_san_theo_may: tinh mau da RIENG tung than may trong
            #   canh. Preview moi may render mot kieu (Sony dat tay, Nikon Auto),
            #   tron chung thi trung vi la mot mau khong may nao co. Ban quay 2/10:
            #   canh 48 anh DSC + SAY, user chinh DSC tang Tint, SAY giam K —
            #   hai may hai huong. May nao trong canh khong co mat thi lui ve so
            #   cua ca canh.
            #]]
            theo_may = {}
            if cfg.get("wb_san_theo_may"):
                for mdl in {str(r.get("model") or "") for r in group}:
                    ds = [r for r in group if str(r.get("model") or "") == mdl]
                    lt, ln = _hai_nhom(ds)
                    if lt[0] is not None:
                        theo_may[mdl] = (lt, ln)
            skin_temp_ev, skin_tint_ev = lech_trong

        # Nhiệt độ / tint máy đo được, lấy trung vị cả cảnh cho ổn định
        as_t = [get_f(r["crs_nen"], "AsShotTemperature", 0.0) for r in group]
        as_ti = [get_f(r["crs_nen"], "AsShotTint", 0.0) for r in group]
        as_t = [v for v in as_t if v > 0]
        scene_asshot_temp = float(np.median(as_t)) if as_t else 0.0
        scene_asshot_tint = float(np.median(as_ti)) if as_ti else 0.0
        #[[ MUC 2 — wb_theo_may_pull: catalog khong co AsShotTemperature thi lay
        #   nhiet do MAY DA DUNG de render preview (Sony dat tay 0xb021, Nikon
        #   tu do 0x004F) lam AsShot, keo theo dung cong thuc cua nhanh sidecar.
        #   Trung vi theo TUNG MAY trong canh: nhiet do la cua may, khong tron.
        #
        #   VI SAO: mau da do tren preview chi noi da lech bao nhieu SO VOI WB
        #   CUA MAY. Lightroom thi render bang WB preset (5250K). Nikon de Auto
        #   (ngoai troi may tu do 6000-6700K) nen preview da can sach, da trong
        #   "dung" -> tool khong keo gi -> Lightroom van o ~5300K -> anh xanh
        #   lanh. Ban quay 2 buoi TrainTool: HIU_4051 may do 6740K, tool 5355K,
        #   user keo len 5771K; HIU_4098 6460K, tool 5377K, user 6100K.
        #]]
        may_K: dict = {}
        if float(cfg.get("wb_theo_may_pull", 0.0) or 0.0) > 0:
            for mdl in {str(r.get("model") or "") for r in group}:
                ks = [float(r["wb_may_K"]) for r in group
                      if str(r.get("model") or "") == mdl and r.get("wb_may_K")]
                if ks:
                    may_K[mdl] = float(np.median(ks))

        for r in group:
            r["scene_size"] = len(group)
            r["target_ev"] = target
            #[[ Giu lai de CHAN DOAN duoc phan cân WB.
            #
            #   temp_adj cuoi cung la tong cua nhieu thanh phan roi bi kep trong
            #   +-wb_temp_max, nen nhin no khong biet duoc vi sao lech: do mau da
            #   do duoc cach mau dich qua xa (sai o skin_ref_rgb), hay do he so
            #   khuech dai qua manh (sai o wb_temp_gain). skin_temp_ev la so
            #   TRUOC khi nhan he so va truoc khi kep — tach duoc hai nguyen
            #   nhan do ra. Xem do_wb.py.
            #]]
            #[[ Anh nay thuoc nhom nao thi lay so lech cua nhom do. Tinh o muc
            #   CANH (tren kia) chu khong tinh rieng tung anh: mot khuon mat le
            #   do sai thi keo ca tam anh di, con trung vi ca nhom thi khong.
            #]]
            r["ngoai_troi"] = _nhan_ngoai(r, cfg)
            lt_r, ln_r = theo_may.get(str(r.get("model") or ""), (None, None)) \
                if theo_may else (None, None)
            if lt_r is None:
                lt_r, ln_r = (lech_trong, lech_ngoai) if cfg["wb"] == "skin" else (None, None)
            if cfg["wb"] == "skin" and _nhan_da_ngoai(r, cfg):
                skin_temp_ev, skin_tint_ev = ln_r
            elif cfg["wb"] == "skin":
                skin_temp_ev, skin_tint_ev = lt_r
            r["skin_temp_ev"] = skin_temp_ev
            r["skin_tint_ev"] = skin_tint_ev

            delta = (target - r["metered_ev"]) * float(cfg["exposure_gain"])
            up = float(cfg.get("max_ev_up") or cfg["max_ev"])
            delta = float(np.clip(delta, -cfg["max_ev"], up))
            if abs(delta) < cfg["deadband_ev"]:
                delta = 0.0

            #[[ KHONG THAY MAT NAO -> GIU NGUYEN, KHONG CHINH EXPOSURE.
            #
            #   Anh khong gian, decor, bang ron, mam co... khong co chu the de
            #   can. Khi do phep do lui ve "subject" (center-weighted ca khung)
            #   nhung MOC van la face_target_ev — moc danh rieng cho DA MAT.
            #   Do mot thang roi so voi moc cua thang khac, ket qua la con so
            #   vo nghia.
            #
            #   Do tren 734 anh buoi 3005: 66 anh khong co mat, 59 trong so do
            #   dang bi chinh, bien do toi +-1.75 EV. Khong co cach nao biet
            #   con so do dung hay sai vi khong co gi de doi chieu.
            #
            #   Nguoi chup da phoi sang cho nhung khung do theo y minh. Giu
            #   nguyen la lua chon dung: khong biet thi dung doan.
            #
            #   Chi bo qua EXPOSURE. Cac phan khac (WB, curve, highlights) van
            #   chay — chung khong dua vao moc do sang cua da.
            #
            #   Dat False de quay lai hanh vi cu.
            #]]
            if cfg.get("giu_anh_khong_mat", True) and not r.get("faces_n"):
                delta = 0.0
                r["giu_nguyen_exposure"] = True

            hist_max = np.asarray(r["hist_max"], dtype=np.int64)
            hist_y = np.asarray(r["hist_y"], dtype=np.int64)
            hl_d = float(cfg["hl_discount"])
            sh_d = float(cfg["sh_discount"])

            sat = float(r.get("sat_frac", 0.0))
            crush = float(r.get("crush_frac", 0.0))
            hl_rec = float(cfg["hl_recover_ev"])
            sh_rec = float(cfg["sh_recover_ev"])

            def clip_pct(shift):
                # Vùng đã bão hoà trong preview chỉ "hồi" lại được khi kéo exposure
                # xuống đủ nhiều; histogram không nhìn thấy phần này.
                hidden = sat * float(np.clip(1.0 + shift / hl_rec, 0.0, 1.0))
                seen = frac_above(hist_max, CLIP_HI_LOG, shift)
                return 100.0 * hl_d * max(seen, hidden)

            def shadow_pct(shift):
                hidden = crush * float(np.clip(1.0 - shift / sh_rec, 0.0, 1.0))
                seen = frac_below(hist_y, CLIP_LO_LOG, shift)
                return 100.0 * sh_d * max(seen, hidden)

            r["clip_before_pct"] = clip_pct(0.0)

            #[[ Ghìm exposure dương — chỉ tính phần cháy MỚI SINH RA.
            #
            #   Trước đây so tổng mức cháy với ngưỡng, và đó là lỗi: ảnh có màn LED
            #   hay cửa sổ lớn thì tổng mức cháy vốn đã vượt ngưỡng sẵn, nên mọi mức
            #   tăng đều bị chặn về 0 — mặt người cứ tối, đúng thứ cần tránh.
            #
            #   Vùng đã cháy sẵn thì thông tin mất rồi, kéo sáng thêm cũng không mất
            #   gì nữa. Cái đáng bảo vệ là phần còn chi tiết mà sắp bị đẩy quá ngưỡng.
            #]]
            notes = []
            if cfg["highlights"] and delta > 0:
                base_clip = r["clip_before_pct"]

                #[[ Sàn cho chủ thể: đo được mặt thì KHÔNG ghìm hết về 0.
                #
                #   Ảnh chụp trước màn LED lớn thì dù chỉ tính phần cháy mới, mức
                #   cháy vẫn vượt ngưỡng ngay từ nấc đầu -> vòng lặp hạ thẳng về 0
                #   và bỏ mặc chủ thể tối. Đã gặp thật: hai ảnh chụp cách nhau 7
                #   giây, ảnh nền tối được +0.46 còn ảnh trước màn LED bị ghim 0,
                #   nhìn cạnh nhau thấy rõ người bị tối hẳn đi.
                #
                #   Màn LED cháy thêm vài phần trăm không ai để ý — mặt người tối
                #   thì ai cũng thấy. Nên khi có mặt, cho phép giữ tới floor_ev.
                #]]
                #[[ Sàn chủ thể KHÔNG áp dụng khi khung đã cháy quá nặng.
                #
                #   Sàn sinh ra để cứu ảnh chụp trước màn LED bị ghìm 0 làm chủ
                #   thể tối hẳn. Đúng khi vùng cháy còn vừa phải. Nhưng khi màn
                #   chiếu chiếm 2/3 khung (DSC01374: cháy sẵn 38.7%), giữ sàn
                #   +0.45 đẩy cháy lên 51.8% — mất nốt phần chữ còn đọc được.
                #   User chấm tay tấm đó về Exposure 0.00: nền đã cháy nặng thì
                #   thà chủ thể hơi tối còn hơn mất cả khung.
                #]]
                heavy = float(cfg.get("hl_heavy_clip_pct", 0.0))
                floor_ev = 0.0
                if r.get("faces_n", 0) > 0 and not (heavy > 0 and base_clip >= heavy):
                    floor_ev = min(delta, float(cfg.get("hl_subject_floor_ev", 0.0)))

                want = delta
                while delta > floor_ev and (clip_pct(delta) - base_clip) > cfg["hl_hard_pct"]:
                    delta = round(delta - 0.05, 4)
                    if delta < floor_ev + 0.05:
                        delta = floor_ev

                #[[ PHANH RIENG CHO DA — chay SAU phanh ca khung o tren.
                #
                #   Phanh tren nhin tong muc chay ca khung. Anh su kien ngoai
                #   troi co nen cay coi toi, nen tong muc chay thap trong khi
                #   DA MAT da cham tran: no khong phanh, va da mat het chi tiet
                #   o tran voi go ma.
                #
                #   O day chi nhin da. Khong dung floor_ev cua phanh tren: san
                #   do sinh ra de CUU chu the khoi bi toi truoc man LED, con o
                #   day chinh chu the la thu dang bi hong — giu san la giu dung
                #   cai loi can chan.
                #]]
                # face_p95_dong: so dong thuan cung anh sang (muc 1), chi co khi
                # canh_ev100 bat — tat thi y het cu.
                p95 = r.get("face_p95_dong") or r.get("face_p95")
                tran = tran_da(r, cfg)
                if p95 and tran > 0 and r.get("faces_n", 0) > 0:
                    p95_255 = float(p95) * 255.0
                    if p95_255 > 1.0:
                        # Tang EV bao nhieu thi p95 len bay nhieu (thang linear
                        # nhan doi moi EV), roi quy nguoc ve sRGB de so tran.
                        lin = _srgb_to_lin_1(p95_255 / 255.0)
                        con = 0.0
                        if lin > 1e-6:
                            tran_lin = _srgb_to_lin_1(tran / 255.0)
                            con = math.log2(max(tran_lin, 1e-6) / lin)
                        if delta > con:
                            #[[ KY YEU: phanh da KHONG giu mat toi duoi dich qua
                            #   phanh_da_san_ky_yeu EV (8/10, v42 tat CG, raw 19.4).
                            #   193 anh fisheye duoi den am (may dat tay 5400K): da
                            #   preview cam dac (R/G 3.3) nen kenh R cham 251-252
                            #   tren MOI mat du mat chi -1.46 EV (dich -1.00) ->
                            #   phanh ghim delta 0. Lightroom ve cung anh do (WB
                            #   4000K, Adobe Standard nhat hon JPEG Sony) da p95 chi
                            #   218; user dua mat len dung muc dich (anh duyet sang
                            #   hon LR +0.43 EV, da p95 247). Nhom 85mm / fisheye
                            #   den thuong mat da o dich nen khong doi. ]]
                            san_ = 0.0
                            if cfg.get("loai_buoi") == "ky_yeu":
                                san_ = min(delta, float(cfg.get("phanh_da_san_ky_yeu") or 0.0))
                            moi_ = round(max(0.0, con, san_), 4)
                            if moi_ < delta - 1e-9:
                                delta = moi_
                                notes.append("ha-vi-da-sap-chay")
                            if san_ > max(0.0, con) + 1e-9:
                                notes.append("phanh-da-nhuong-ky-yeu")

                #[[ PHANH THEO VUNG CHU THE — mat VA quan ao.
                #
                #   Hai phanh tren nhin hai thu: ca khung (hl_hard_pct) va rieng
                #   da mat (skin_hard_p95). Con thieu dung cai o giua: AO cua
                #   chu the.
                #
                #   Ao trang/sang thuong sang hon da 1-1.5 EV, nen khi da vua du
                #   thi ao da chay. Ma ao chi chiem vai % khung, nen phanh ca
                #   khung khong thay gi. Do that tren SAYMedia-04770:
                #     ca khung >=254 : 4.3%  -> duoi nguong 8%, KHONG phanh
                #     chu the >=254  : 17.3% -> ao da mat chi tiet vai
                #
                #   Chi phanh khi phan chay MOI SINH RA vuot nguong, giong
                #   cach hl_hard_pct lam: vung da chay san thi keo sang them
                #   cung khong mat gi nua.
                #
                #   0 = tat.
                #]]
                subj_tran = float(cfg.get("subj_hard_pct") or 0.0)
                s_sat = r.get("subj_sat_frac")
                if subj_tran > 0 and s_sat is not None and delta > 0:
                    # Uoc luong: moi EV tang lam vung ">=242" tran sang ">=254".
                    # Khong co histogram rieng cho vung chu the nen dung chinh
                    # hai con so da do, noi tuyen tinh theo delta.
                    s_br = float(r.get("subj_bright_frac") or s_sat)
                    base = s_sat * 100.0
                    def _subj_pct(shift):
                        t = float(np.clip(shift / 1.0, 0.0, 1.0))
                        return 100.0 * (s_sat + (s_br - s_sat) * t)
                    while delta > 0 and (_subj_pct(delta) - base) > subj_tran:
                        delta = round(delta - 0.05, 4)
                        if delta < 0.05:
                            delta = 0.0
                    if delta < want - 1e-9 and "ha-vi-chu-the-chay" not in notes:
                        notes.append("ha-vi-chu-the-chay")
                #[[ Cờ CHUNG: vòng lặp trên đã THỰC SỰ hạ delta vì cháy sáng.
                #
                #   Phải có cờ này vì hai cờ cụ thể bên dưới đều có lỗ: ảnh bị
                #   hạ nhưng không rơi đúng 0.0 và cũng không chạm sàn (vì sàn
                #   đã bị hl_heavy_clip_pct tắt) thì không mang cờ nào cả —
                #   bước san phẳng cảnh không nhận ra và kéo ngược nó lên.
                #   Gặp thật ở DSC01374: hạ xong lại bị kéo về +1.12.
                #]]
                if delta < want - 1e-9:
                    notes.append("ha-vi-chay-sang")
                if delta == 0.0:
                    notes.append("ghim-exposure-vi-chay-sang")
                elif floor_ev > 0 and delta < want - 1e-9 and delta <= floor_ev + 1e-9:
                    # chỉ ghi chú khi sàn THẬT SỰ đỡ lại, không phải khi vốn đã thấp
                    notes.append("giu-san-cho-chu-the")

            #[[ MUC 3 — PHANH DA HAI CHIEU (phanh_da_hai_chieu). False = TAT.
            #
            #   Phanh da o tren chi chay khi delta > 0: no CHAN keo da len qua
            #   tran, con da DA vuot tran san (anh chup du sang, hoac tool dang
            #   dim ma dim chua du) thi no dung yen. Ban quay 2/10, buoi
            #   TrainTool: DSC08681-87 tool -0.57, user -0.88 ("tool giam 0.55
            #   chua du, da highlight van chay"); DSC08688-92 tool -0.66, user
            #   -1.32 ("da kha chay, dim chua du"); 48 tam user ha sang co da
            #   p95 dung o tran 232 luc tool day ra, user keo ve ~201.
            #
            #   Hai chieu: da vuot tran thi KEO XUONG toi tran, ke ca khi delta
            #   dang am. Van cham max_ev de mot phep do hong khong dim sap anh.
            #   Gan "ha-vi-chay-sang" de san phang canh khong keo nguoc len.
            #
            #   CHI KHI KHUNG CHAY (tran_da() da ha tran xuong, muc 3a). Ban dau
            #   cho chay ca voi tran thuong 232 — thu tren 75 anh TrainTool thi
            #   10 anh bi keo xuong, 8 anh ra XA dap an: say06085/06092/06104/
            #   06110 da p95 244-249 ma user giu Exposure 0 (chi sua WB). Khung
            #   khong chay thi da sang toi 250 user van nhan. Cai user keo xuong
            #   la da sang TRONG KHUNG CHAY (BNE02293-305 khung 16-20% bao hoa,
            #   da p95 204-239 -> user dong bo -0.35).
            #]]
            if (cfg.get("phanh_da_hai_chieu") and cfg["highlights"]
                    and r.get("faces_n", 0) > 0):
                p95_ = r.get("face_p95_dong") or r.get("face_p95")
                tran_ = tran_da(r, cfg)
                lin_ = _srgb_to_lin_1(float(p95_)) if p95_ else 0.0
                if 0 < tran_ < float(cfg.get("skin_hard_p95") or 0.0) and lin_ > 1e-6:
                    con_ = math.log2(max(_srgb_to_lin_1(tran_ / 255.0), 1e-6) / lin_)
                    if delta > con_ + 1e-9:
                        delta = round(max(con_, -float(cfg["max_ev"])), 4)
                        for nh_ in ("ha-vi-da-sap-chay", "ha-vi-chay-sang"):
                            if nh_ not in notes:
                                notes.append(nh_)

            #[[ THU HOI VUNG CHAY — keo XUONG khi khung von da chay nang.
            #
            #   Chot chong chay o tren chi chay khi delta > 0: no ngan lam TE
            #   HON, khong bao gio SUA cai da sai. Anh nao khung von da chay 30%
            #   ma mat dang o dung dich thi no khong dong gi ca — dung thu nguoi
            #   dung phai ngoi sua tay.
            #
            #   DO TREN 187 ANH NGUOI DUNG SUA TAY o buoi 1308, co ghi ly do:
            #     nhom "sang-qua" + "nen-chay" (63 anh): bao hoa trung vi 22.9%,
            #       trong khi moi nhom con lai deu duoi 8%.
            #     nguong bao hoa 8%: 78 anh vuot, 73 trong so do nguoi dung keo
            #       xuong that -> 94% dung.
            #     muc keo: trung vi -0.42 EV, do lech chuan 0.24, phan vi 25-75%
            #       nam trong khoang -0.58 den -0.36. Rat tap trung.
            #
            #   VI SAO KEO MOT LUONG CO DINH, KHONG TI LE VOI MUC CHAY:
            #     Khop tuyen tinh muc keo theo bao hoa TRONG nhom do cho R^2 =
            #     0.035 — gan nhu khong giai thich duoc gi. He so ra -0.19 EV
            #     tren mot don vi, tuc bao hoa 60% moi keo them 0.11 EV. Bang
            #     buc tranh theo nhom nhin thi co ve tang dan, nhung do la do
            #     THANH PHAN NHOM (anh bao hoa cao phan lon la "sang-qua") chu
            #     khong phai lieu-dap-ung ben trong nhom.
            #     Lam ham ti le o day la khop nhieu. Du lieu chi do noi MOT
            #     nguong va MOT luong.
            #
            #   DIEM MU con nguyen: 187 anh nay deu la anh tool lam SAI. Trong
            #   893 anh nguoi dung duyet thang cung co anh bao hoa cao ma ho thay
            #   on — con so do khong nam trong day. Chi cong B tra loi duoc.
            #   Nen mac dinh 0 = TAT cho toi khi qua cong.
            #]]
            ng_thu = float(cfg.get("hl_thu_hoi_nguong", 0.0))
            if ng_thu > 0 and sat >= ng_thu and cfg["highlights"]:
                keo = float(cfg.get("hl_thu_hoi_ev", 0.0))
                san = float(cfg.get("hl_thu_hoi_san_ev", 0.0))
                moi = delta - keo
                # Khong day mat xuong qua sau so voi dich — chay nen khong dang
                # de doi lay mot chu the toi hom.
                if san > 0:
                    moi = max(moi, (target - r["metered_ev"]) - san)
                if moi < delta - 1e-9:
                    delta = round(moi, 4)
                    notes.append("thu-hoi-vung-chay")

            r["delta_ev"] = delta
            clip_after = clip_pct(delta)
            shadow_after = shadow_pct(delta)
            r["clip_after_pct"] = clip_after
            r["shadow_after_pct"] = shadow_after

            hl_adj = 0
            if cfg["highlights"]:
                #[[ MUC 5 — AO/VAY TRANG CUA CHU THE: noi tran Highlights.
                #   hl_ao_trang_max = 0 la TAT.
                #
                #   Ban quay 2/10, buoi TrainTool: vay cuoi / ao trang chay thi
                #   tool dung o dung tran (hl_bright_max 40, hl_max 45 -> HL
                #   cuoi -24/-29), user keo tiep ve -40..-58 (DSC08593 "vay hoi
                #   chay", DSC08656 HL -58). Tran cu chot cho ca khung — de khong
                #   lam xam ca anh vi mot cai man LED; vung chu the sang (vay,
                #   ao) thi chinh la thu khach nhin, nen cho keo sau hon.
                #   Dieu kien: vung chu the >= 242 chiem >= hl_ao_trang_pct %.
                #]]
                hl_tran = float(cfg["hl_max"])
                hl_tran_b = float(cfg["hl_bright_max"])
                ao_max = float(cfg.get("hl_ao_trang_max", 0) or 0)
                ao_trang = (ao_max > 0 and r.get("subj_bright_frac") is not None
                            and float(r["subj_bright_frac"]) * 100.0
                            >= float(cfg.get("hl_ao_trang_pct", 0.0) or 0.0))
                if ao_trang:
                    hl_tran, hl_tran_b = max(hl_tran, ao_max), max(hl_tran_b, ao_max)
                excess = max(0.0, clip_after - cfg["hl_trigger_pct"])
                hl_adj = -int(round(min(hl_tran, cfg["hl_gain"] * excess)))
                if ao_trang and -hl_adj > float(cfg["hl_max"]):
                    notes.append("keo-HL-ao-trang")

                #[[ Vùng GẦN cháy cũng phải kéo Highlights.
                #
                #   Áo sơ mi trắng, áo dài, tường sáng nằm ở dải 242-253: chưa
                #   "cháy" theo định nghĩa >= 254 nên phần trên tính ra 0, trong
                #   khi mắt đã thấy bệt hết chi tiết vải.
                #
                #   Đo thật trên ảnh người mặc sơ mi trắng: 8.6% pixel >= 242
                #   nhưng chỉ 0.01% >= 254 -> hl_adj = 0, Highlights giữ nguyên
                #   preset +16, người dùng phải tự kéo về -35.
                #
                #   Vùng gần cháy còn CỨU ĐƯỢC chi tiết (chưa mất thông tin) nên
                #   kéo nhẹ tay hơn vùng cháy thật — dùng gain riêng, nhỏ hơn.
                #]]
                bright = float(r.get("bright_frac", 0.0)) * 100.0
                # ước lượng lại theo delta đã chốt: kéo sáng thì vùng này phình ra
                bright *= float(2.0 ** max(0.0, delta))
                b_ex = max(0.0, bright - cfg["hl_bright_trigger_pct"])
                # Chỉ dùng khi cháy THẬT còn ít: ảnh đã cháy nhiều thì đường
                # trên đã lo, chồng thêm chỉ làm xám xịt vô cớ.
                if b_ex > 0 and clip_after < cfg["hl_bright_trigger_pct"]:
                    b_adj = -int(round(min(hl_tran_b,
                                           cfg["hl_bright_gain"] * b_ex)))
                    # lấy cái nào mạnh hơn, KHÔNG cộng dồn hai đường
                    if b_adj < hl_adj:
                        hl_adj = b_adj
                        notes.append("keo-HL-vi-vung-sang-lon")
                        if (ao_trang and -b_adj > float(cfg["hl_bright_max"])
                                and "keo-HL-ao-trang" not in notes):
                            notes.append("keo-HL-ao-trang")
            # Ky yeu "den sau": khong tu mo vung toi — xem mo_toi_ky_yeu
            mo_toi = cfg.get("loai_buoi") != "ky_yeu" or bool(cfg.get("mo_toi_ky_yeu"))
            sh_adj = 0
            if cfg["shadows"] and mo_toi:
                deficit = max(0.0, shadow_after - cfg["sh_trigger_pct"])
                sh_adj = int(round(min(cfg["sh_max"], cfg["sh_gain"] * deficit)))
            r["hl_adj"], r["sh_adj"] = hl_adj, sh_adj

            #[[ Parametric curve — bổ sung cho Highlights2012/Shadows2012.
            #
            #   Hai trường kia tác động dải RỘNG nên phải dè tay, không thì bệt
            #   cả ảnh. Parametric cắt theo ngưỡng Split (25/50/75) nên nhắm
            #   đúng vùng cần sửa: hạ riêng màn LED cháy sáng mà không dìm mặt
            #   người đứng trước nó, mở riêng vest đen mà không làm đục nền.
            #
            #   Cộng DỒN với point curve của preset chứ không đè — nên chất ảnh
            #   SAY Media giữ nguyên.
            #]]
            cv_hl = cv_dk = cv_lt = cv_sh = 0
            if cfg.get("curve", True):
                # 1. nền cháy -> kéo riêng vùng sáng nhất
                ex = max(0.0, clip_after - cfg["curve_hl_trigger_pct"])
                cv_hl = -int(round(min(cfg["curve_hl_max"], cfg["curve_hl_gain"] * ex)))

                # 2. chủ thể bết tối -> mở vùng tối
                df = max(0.0, shadow_after - cfg["curve_sh_trigger_pct"])
                if mo_toi:
                    cv_sh = int(round(min(cfg["curve_sh_max"], cfg["curve_sh_gain"] * df)))

                # 3. tương phản chữ S nhẹ — bỏ qua khi ảnh đang cháy nhiều,
                #    thêm tương phản lúc đó chỉ làm cháy thêm.
                c = int(cfg.get("curve_contrast", 0))
                if c and clip_after <= cfg["curve_contrast_max_clip"]:
                    #  Ky yeu: anh duyet SANG hon o duoi trung tinh (v41 p25
                    #  +0.38; v42 da bo ep Darks van con p25 +0.30, p50 +0.22)
                    #  -> NANG ca Darks cung Lights (xem nen_tone_ky_yeu)
                    cv_lt, cv_dk = c, (c if cfg.get("loai_buoi") == "ky_yeu" else -c)

                # Đã mở vùng tối thì đừng ép Darks xuống nữa — hai cái ngược nhau
                if cv_sh > 0:
                    cv_dk = min(0, cv_dk + cv_sh // 2)

                if cv_hl or cv_dk or cv_lt or cv_sh:
                    notes.append("curve")
            r["cv_hl"], r["cv_lt"] = cv_hl, cv_lt
            r["cv_dk"], r["cv_sh"] = cv_dk, cv_sh

            #[[ Color Grading KHONG tinh o day nua (8/10): can WB CUOI cua anh
            #   (preset + phan tool chinh, chi co sau compute_values) moi biet da
            #   trong Lightroom dang o dau. Xem grade_theo_trang_thai(), plan()
            #   goi sau compute_values. Cach cu (hue 350 theo do thieu xanh lam
            #   cua preview) day da DO hon thay vi trang hong. ]]
            r["gr_hue"], r["gr_sat"] = 0, 0

            #[[ Auto Transform (Upright) — chỉ cho ảnh nền kiến trúc/backdrop.
            #
            #   Ghi PerspectiveUpright = 1 (Auto); Lightroom tự tính perspective
            #   khi mở ảnh. SDK KHÔNG có API tính sẵn nên đây là cách duy nhất.
            #
            #   Ba điều kiện, thiếu một là bỏ qua:
            #     1. Khung có đường thẳng mạnh (backdrop, màn LED, tường ốp).
            #     2. Mặt chủ thể KHÔNG chiếm quá lớn — Upright trên ảnh chân
            #        dung cận sẽ kéo méo mặt và crop mất người. Đã gặp: ảnh
            #        thẳng nhất trong tập lại là chân dung người thuyết trình.
            #     3. Có mặt trong khung (ảnh check-in, ảnh nhóm) — ảnh không
            #        người thì thường là ảnh chi tiết, không cần nắn.
            #]]
            up = 0
            if cfg.get("upright") and r.get("straightness", 0) >= cfg["upright_straight_min"]:
                fw_rel = float(r.get("face_rel_area", 0.0))
                if r.get("faces_n", 0) > 0 and fw_rel <= cfg["upright_face_max_pct"]:
                    up = int(cfg.get("upright_mode", 1))
                    notes.append("upright-auto")
            r["upright"] = up

            temp_adj = tint_adj = 0.0
            if cfg["wb"] in ("asshot", "skin"):
                preset_t = preset_val(r, "Temperature")
                preset_ti = preset_val(r, "Tint")
                pull = float(cfg["wb_asshot_pull"])
                if scene_asshot_temp > 0 and preset_t > 0:
                    temp_adj = float(np.clip(pull * (scene_asshot_temp - preset_t),
                                             -cfg["wb_temp_max"], cfg["wb_temp_max"]))
                    tint_adj = float(np.clip(pull * (scene_asshot_tint - preset_ti),
                                             -cfg["wb_tint_max"], cfg["wb_tint_max"]))
                    if cfg["wb"] == "skin":
                        temp_adj, tint_adj = _skin_wb(cfg, temp_adj, tint_adj,
                                                      skin_temp_ev, skin_tint_ev, notes)
                elif cfg["wb"] == "skin":
                    # thiếu số liệu máy đo -> vẫn cân được theo màu da
                    t0_ = 0.0
                    mk = may_K.get(str(r.get("model") or ""))
                    pull_may = float(cfg.get("wb_theo_may_pull", 0.0) or 0.0)
                    if mk and pull_may > 0 and preset_t > 0:
                        # Muc 2: AsShot thieu -> dung nhiet do may (xem may_K)
                        t0_ = float(np.clip(pull_may * (mk - preset_t),
                                            -cfg["wb_temp_max"], cfg["wb_temp_max"]))
                        notes.append("wb-theo-may")
                    temp_adj, tint_adj = _skin_wb(cfg, t0_, 0.0,
                                                  skin_temp_ev, skin_tint_ev, notes)
                    notes.append("thieu-AsShotTemperature")
                else:
                    notes.append("khong-co-AsShotTemperature")
                # wb_tint_theo_may (muc 2b) cong o CUOI decide(), sau san
                # phang mau — xem _tint_theo_may().
            elif cfg["wb"] in ("grey", "scene"):
                t_ev, ti_ev = wb_cast(r["rgb_mean"])
                if cfg["wb"] == "scene":
                    t_ev -= float(scene_cast[0])
                    ti_ev -= float(scene_cast[1])
                temp_adj = float(np.clip(cfg["wb_temp_gain"] * t_ev,
                                         -cfg["wb_temp_max"], cfg["wb_temp_max"]))
                tint_adj = float(np.clip(cfg["wb_tint_gain"] * ti_ev,
                                         -cfg["wb_tint_max"], cfg["wb_tint_max"]))
            r["temp_adj"], r["tint_adj"] = temp_adj, tint_adj
            # nối thêm, đừng ghi đè: ghi chú đặt trước đó (thiếu sidecar, không có
            # trong bản xuất...) là thông tin người dùng cần thấy nhất
            r["notes"] = ";".join([n for n in [r.get("notes", "")] + notes if n])

    #[[ SAN PHẲNG TRONG CẢNH — bước cuối, chạy sau khi mọi ảnh đã có delta.
    #
    #   Mục tiêu không phải "cùng thông số" mà là KẾT QUẢ NHÌN GIỐNG NHAU: ảnh
    #   chụp cùng một chỗ thì sau khi chỉnh phải cùng độ sáng, cùng màu.
    #
    #   Vì sao vẫn lệch sau khi đã nhắm chung một đích: nhiều ảnh bị chặn giữa
    #   chừng (trần EV, chống cháy sáng, sàn chủ thể) nên mỗi ảnh dừng ở một
    #   mức khác nhau. Đo thật: một cảnh 28 ảnh đều dừng đúng ở sàn 0.45 EV,
    #   độ sáng sau chỉnh vẫn trải 0.91 EV.
    #
    #   Cách làm: lấy TRUNG VỊ độ sáng sau chỉnh của cảnh làm mốc chung, rồi
    #   kéo từng ảnh về phía đó — nhưng chỉ kéo phần còn "room", không phá vỡ
    #   các giới hạn trên. Trung vị chứ không phải trung bình: một hai ảnh cá
    #   biệt không được lôi cả cảnh đi theo.
    #]]
    lvl = float(cfg.get("scene_level", 0.0))
    if lvl > 0:
        for group in by_scene.values():
            if len(group) < int(cfg.get("scene_level_min", 4)):
                continue
            after = np.array([r["metered_ev"] + r["delta_ev"] for r in group])
            #[[ Moc lay tren anh KHONG bi ghim vi chay sang — xem chu thich o
            #   scene_aim_free_min trong DEFAULTS. Khong du anh tu do thi lui
            #   ve trung vi ca canh nhu cu, chu khong tat san phang: canh ma
            #   ca canh deu bi ghim thi muc chung do la that, khong co anh
            #   khoe manh nao de bi keo hong.
            #]]
            #[[ Anh GIU NGUYEN VAN duoc gop vao moc — co chu y.
            #
            #   Da thu loai chung ra (vi chung do bang thang "subject" con anh
            #   co mat do bang thang DA MAT). Ket qua TE HON: canh 30 cua buoi
            #   3005 co 58% anh khong mat, bo chung ra lam moc tut han, 10 anh
            #   co mat bi keo toi theo — p95 vung da trung vi tu 127 xuong 99,
            #   ca biet SAY09208 tu 232 xuong 122.
            #
            #   Ly do: anh khong-mat trong cung mot canh van chup cung mot cho,
            #   cung mot anh sang. Do bang thang khac nhung muc sang thuc te
            #   thi lien quan. Bo chung ra la vut mat phan lon mau cua canh.
            #]]
            n_tu_do = int(cfg.get("scene_aim_free_min", 0))
            tu_do = [a for r, a in zip(group, after)
                     if "ha-vi-chay-sang" not in r.get("notes", "")]
            if n_tu_do > 0 and len(tu_do) >= n_tu_do:
                aim = float(np.median(tu_do))
            else:
                aim = float(np.median(after))
            up_cap = float(cfg.get("max_ev_up") or cfg["max_ev"])
            for r, a in zip(group, after):
                want = (aim - a) * lvl
                if abs(want) < 0.02:
                    continue
                nd = r["delta_ev"] + want
                #[[ San phang duoc NOI TRAN, vi tran phuc vu muc dich khac.
                #
                #   max_ev gioi han muc can thiep tren TUNG anh — de mot anh
                #   don le khong bi keo qua tay. Nhung khi dong bo trong canh
                #   thi muc dich la MOI ANH GIONG NHAU; giu tran cung o day
                #   chinh la thu chan viec do.
                #
                #   Gap that: hai anh cung backdrop, mot anh toi hon 1.0 EV nen
                #   can keo +1.18 nhung bi tran 1.00 chan -> van lech 0.18 EV
                #   du da san phang.
                #
                #   Noi them scene_level_extra_ev, khong tha lỏng hoan toan.
                #]]
                extra = float(cfg.get("scene_level_extra_ev", 0.0))
                nd = float(np.clip(nd, -(cfg["max_ev"] + extra), up_cap + extra))
                # Không kéo sáng thêm ở ảnh đã bị ghìm vì cháy: lý do ghìm vẫn
                # còn nguyên, san phẳng không được phép phá nó.
                #[[ Không kéo sáng thêm ở ảnh ĐÃ bị ghìm vì cháy — dù ghìm
                #   kiểu nào. Trước đây chỉ nhận cờ "ghim-exposure", tức chỉ
                #   ảnh bị ghìm hẳn về 0. Ảnh bị ghìm về SÀN CHỦ THỂ mang cờ
                #   "giu-san-cho-chu-the" nên lọt qua, và bước san phẳng kéo
                #   ngược nó lên lại — vô hiệu hoá đúng cái vừa ghìm.
                #
                #   Đo trên buổi 1308 (1464 ảnh): cờ "ghim-exposure" xuất hiện
                #   0 lần, còn "giu-san-cho-chu-the" 223 lần, trong đó 188 ảnh
                #   bị san phẳng kéo lên lại. Nhóm đó cháy từ trung vị 6.1% lên
                #   24.7% (tăng trung vị 15.8 điểm, cá biệt 31 điểm).
                #   Nói cách khác: chốt bảo vệ đang canh một điều kiện chưa hề
                #   xảy ra, còn điều kiện xảy ra thật thì không ai canh.
                #]]
                if nd > r["delta_ev"] and "ha-vi-chay-sang" in r.get("notes", ""):
                    continue

                #[[ ANH DA CHOT GIU NGUYEN thi san phang cung khong duoc dung.
                #
                #   Anh khong co mat nao da duoc quyet dinh giu nguyen o tren
                #   (xem giu_anh_khong_mat). San phang lam theo trung vi canh —
                #   ma trung vi do tinh tu nhung anh CO mat — nen no keo anh
                #   khong-mat di theo, xoa sach quyet dinh vua roi.
                #
                #   Do that: 46/66 anh khong mat bi keo lai o buoc nay du
                #   delta_ev da la 0.
                #]]
                if r.get("giu_nguyen_exposure"):
                    continue

                #[[ SAN PHANG KHONG DUOC DAY ANH RA XA DICH.
                #
                #   Chot cu chi canh mot chieu: khong cho san phang KEO LEN mot
                #   anh da bi ghim vi chay sang. Chieu nguoc lai bo trong — va
                #   do moi la chieu gay hong.
                #
                #   Gap that o buoi 0306, canh 3 (11 anh): 9 anh bi "ha-vi-chay-
                #   sang" giu o muc -1.83, trong khi dich la -1.19. Trung vi
                #   canh thanh -1.83, tuc muc ma nhung anh KHONG THE sang len
                #   dung lai. San phang lay do lam moc va keo not hai anh khoe
                #   manh xuong theo. SAY09660 dang o dung dich -1.19 (delta
                #   +0.48, nguoi dung tu chinh +0.44 — lech 0.04) bi keo thanh
                #   delta -0.16. Sai 0.64 EV, va sai vi mot ly do khong lien
                #   quan gi den chinh no.
                #
                #   Cung co che nay lam SAY09787 va SAY09788 — cung mot khung
                #   hinh, chup lien nhau — ra hai muc sang khac nhau: 09787 roi
                #   vao canh 4 (105 anh, moc lech -1.59), 09788 vao canh 5 (12
                #   anh, moc dung dich -1.19). Khac 0.32 EV chi vi rot vao hai
                #   ro khac nhau. Toan buoi: 65/166 anh bi san, trung vi lech
                #   0.40 EV, ca biet 0.64.
                #
                #   Luat moi, phat bieu mot cau: san phang duoc phep keo anh
                #   LAI GAN dich bao nhieu cung duoc, nhung khong bao gio duoc
                #   day no ra XA dich hon luc chua san.
                #
                #   Vi sao cach nay dung cho ca hai phia: khi canh lanh manh,
                #   moc trung vi TRUNG voi dich, moi anh deu bi keo lai gan —
                #   chot khong he cham vao, san phang chay nguyen nhu cu. Chot
                #   chi can thiep dung luc moc da troi khoi dich, tuc dung luc
                #   san phang dang lam hong. Khong them nguong nao phai chinh.
                #
                #   scene_aim_slack_ev noi ra mot chut cho anh dang nam SAN
                #   dich van nhuc nhich duoc theo canh (neu khong thi nhung anh
                #   dung y dich bi dong cung hoan toan). De 0 la nghiem ngat.
                #]]
                tgt = r.get("target_ev")
                if tgt is not None:
                    slack = float(cfg.get("scene_aim_slack_ev", 0.0))
                    xa = abs(a - float(tgt)) + slack        # a = muc TRUOC khi san
                    moi = r["metered_ev"] + nd
                    if abs(moi - float(tgt)) > xa:
                        moi = float(tgt) + (xa if moi > float(tgt) else -xa)
                        nd = moi - r["metered_ev"]

                if abs(nd - r["delta_ev"]) >= 0.02:
                    r["delta_ev"] = round(nd, 4)
                    r["notes"] = ";".join(
                        [n for n in [r.get("notes", ""), "san-trong-canh"] if n])

        #[[ Màu cũng san phẳng: đưa WB của cả cảnh về một mốc.
        #
        #   Cùng một chỗ chụp thì nhiệt độ đèn không đổi — chênh lệch giữa các
        #   ảnh là do phép đo, không phải do thực tế. Để nguyên thì xem liền
        #   một dải ảnh sẽ thấy màu nhấp nháy.
        #]]
        for group in by_scene.values():
            if len(group) < int(cfg.get("scene_level_min", 4)):
                continue
            #[[ San phang MOI truong anh huong toi cai nhin thay, khong chi WB.
            #
            #   Truoc day chi san temp/tint nen hai anh cung khung van khac
            #   nhau: gap that mot cap chup cach nhau 1 giay co hl_adj -40 vs
            #   -45 va gr_sat 7 vs 4 — nhin ra hai mau khac han.
            #
            #   Ly do lech: may truong nay tinh RIENG tung anh theo % chay sang
            #   va mau da do duoc, ma AF moi anh lai chon mot nguoi khac (moi
            #   nguoi mac ao mot mau) nen so lieu dau vao da khac nhau.
            #
            #   hl_adj / cv_* / gr_* deu la SO NGUYEN nen lam tron sau khi san.
            #]]
            #[[ MUC 2 — wb_san_theo_may: san WB trong TUNG than may cua canh,
            #   khong tron hai may. Xem cho tinh theo_may o tren. ]]
            nhom_wb = [group]
            if cfg.get("wb_san_theo_may"):
                tm_: dict = {}
                for r in group:
                    tm_.setdefault(str(r.get("model") or ""), []).append(r)
                nhom_wb = list(tm_.values())
            for g_ in nhom_wb:
                for key in ("temp_adj", "tint_adj"):
                    vals = [r.get(key, 0.0) for r in g_]
                    med = float(np.median(vals))
                    for r in g_:
                        r[key] = r.get(key, 0.0) + (med - r.get(key, 0.0)) * lvl

            #  Color Grading san phang rieng, tren VECTO (a, b) chu khong tren
            #  hue / sat — xem grade_theo_trang_thai()
            for key in ("hl_adj", "sh_adj", "cv_hl", "cv_lt", "cv_dk", "cv_sh"):
                vals = [r.get(key, 0) for r in group]
                if not any(vals):
                    continue
                med = float(np.median(vals))
                for r in group:
                    cur = float(r.get(key, 0))
                    r[key] = int(round(cur + (med - cur) * lvl))

    dong_bo_loat(items, cfg)
    if cfg["wb"] in ("asshot", "skin"):
        _wb_theo_asshot(items, cfg)
        _tint_theo_may(items, cfg)
        _tint_tran_am(items, cfg)
        _wb_ky_yeu(items, cfg)
        _bu_sang_canh_am(items, cfg)
    _bu_sang_ca_buoi(items, cfg)


def chia_loat(items: list, cfg: dict) -> list:
    """Chia ảnh thành các LOẠT: cùng máy, cùng cảnh, cùng khẩu/tốc/ISO, chụp
    liền nhau (≤ loat_gio_s giây), CÙNG BỐ CỤC (chữ ký khung lệch ≤ loat_bo_cuc
    so với tấm ĐẦU loạt) và CÙNG ÁNH SÁNG (độ sáng khung lệch ≤ loat_khung_ev
    so với tấm đầu). Trả về danh sách loạt ≥ 2 ảnh.

    So với tấm ĐẦU chứ không so tấm liền trước: so liền trước thì một dãy trôi
    dần (đèn hạ từ từ, người dịch dần) nối thành một chuỗi dài mà hai đầu khác
    hẳn nhau."""
    bo_cuc = float(cfg.get("loat_bo_cuc", 0.10))
    khung_tol = float(cfg.get("loat_khung_ev", 0.25))
    gio = float(cfg.get("loat_gio_s", 60.0))

    def thong_so(r):
        f, t, iso = _so(r.get("fnumber")), _so(r.get("exposure_time")), _so(r.get("iso"))
        if not t or not iso or t <= 0:
            return None
        #  8/10: lens co (fisheye 10mm) EXIF khau = 0 -> "?" thay vi bo ca anh
        #  khoi moi loat (xem mat_lech_khung_ev_lens_co)
        return (round(f, 1) if f else "?", round(math.log2(t), 2), round(iso))

    def sig(r):
        v = r.get("scene_sig")
        return np.asarray(v, dtype=np.float64) if v else None

    theo_may: dict = {}
    for r in sorted(items, key=lambda r: r["dt_obj"]):
        theo_may.setdefault(str(r.get("model") or ""), []).append(r)
    ds_loat = []
    for ds in theo_may.values():
        cur, neo = [], None
        for r in ds:
            ts, s, kh = thong_so(r), sig(r), _so(r.get("metered_subject_ev"))
            if (cur and ts is not None and neo["ts"] is not None and ts == neo["ts"]
                    and r.get("scene") == neo["scene"]
                    and (r["dt_obj"] - cur[-1]["dt_obj"]).total_seconds() <= gio
                    and s is not None and neo["sig"] is not None
                    and s.shape == neo["sig"].shape
                    and float(np.abs(s - neo["sig"]).mean()) <= bo_cuc
                    and kh is not None and neo["khung"] is not None
                    and abs(kh - neo["khung"]) <= khung_tol):
                cur.append(r)
                continue
            if len(cur) >= 2:
                ds_loat.append(cur)
            cur = [r]
            neo = {"ts": ts, "scene": r.get("scene"), "sig": s, "khung": kh}
        if len(cur) >= 2:
            ds_loat.append(cur)
    return ds_loat


def dong_bo_loat(items: list, cfg: dict) -> int:
    """CÙNG KHUNG + CÙNG THÔNG SỐ CHỤP -> CÙNG MỘT KẾT QUẢ. dong_bo_loat False = TẮT.

    Mỗi loạt (xem chia_loat) nhận CÙNG delta Exposure (trung vị các ảnh có
    mặt trong loạt) và cùng Highlights/Shadows/WB/Curve. Ảnh không thấy mặt
    nằm trong loạt cũng theo loạt — cùng khung, cùng đèn, chỉ là người quay đi.
    Trả về số ảnh bị đổi.

    #[[ VI SAO (3/10, user: "phai giai quyet dut diem"). Buoi G:\\2709 (cuoi,
    #   Nikon Z, 1/800 f/2.2 ISO 125): SUB_6485/87/88 -0.40 ma SUB_6486 +0.45;
    #   SUB_6652-6665 (me + co dau, cung khung) nhay -0.47..+0.45 tung tam mot.
    #   San phang canh KHONG chua duoc: no dua moi tam ve cung "mat SAU chinh"
    #   — phep do mat lech bao nhieu (mat me / mat co dau, AF nhay nguoi) thi
    #   Exposure nhay bay nhieu.
    #
    #   VI SAO CHAY O CUOI, TREN KET QUA chu khong tren phep do: muc 1 (do mat
    #   theo anh sang) va sua_mat_lech_khung sua PHEP DO, nhung phanh chong chay
    #   van quyet theo tung tam — tam nay bi phanh tam kia khong. Dong bo ket
    #   qua cuoi moi bao dam "cung mot so".
    #
    #   VI SAO DIEU KIEN CHAT (bo cuc + do sang khung): hai phuong an da BAC —
    #   "cung thong so may thi cung Exposure" (san khau doi den ma thong so
    #   khong doi, 29/9) va muc 1 gop ca anh KHAC NGUOI / khac bo cuc cung anh
    #   sang (cong B 6.34% / 14.77%, 3/10). O day phai cung bo cuc VA cung do
    #   sang khung VA cung thong so VA chup lien nhau.
    #]]
    """
    if not cfg.get("dong_bo_loat"):
        return 0
    KHOA_F = ("delta_ev", "temp_adj", "tint_adj")
    KHOA_I = ("hl_adj", "sh_adj", "cv_hl", "cv_lt", "cv_dk", "cv_sh")
    n = 0
    for i, g in enumerate(chia_loat(items, cfg)):
        co_mat = [r for r in g if not r.get("giu_nguyen_exposure")]
        if not co_mat:
            continue
        gia = {k: float(np.median([float(r.get(k, 0.0) or 0.0) for r in co_mat]))
               for k in KHOA_F}
        gia.update({k: int(round(float(np.median([float(r.get(k, 0) or 0) for r in co_mat]))))
                    for k in KHOA_I})
        for r in g:
            cu = float(r.get("delta_ev", 0.0) or 0.0)
            r["delta_ev"] = round(gia["delta_ev"], 4)
            for k in KHOA_F[1:]:
                r[k] = gia[k]
            for k in KHOA_I:
                r[k] = gia[k]
            #[[ Anh khong mat trong loat da theo loat -> khong con "giu nguyen":
            #   bu sang ca buoi phai ap cho no nhu ca loat, khong thi loat lai
            #   lech nhau dung bang so bu. ]]
            r["giu_nguyen_exposure"] = False
            r["loat"] = i
            if abs(r["delta_ev"] - cu) > 0.005:
                n += 1
            if "dong-bo-loat" not in r.get("notes", ""):
                r["notes"] = ";".join([v for v in [r.get("notes", ""), "dong-bo-loat"] if v])
    return n


def _bu_sang_ca_buoi(items: list, cfg: dict) -> int:
    """Cộng cfg["bu_sang_ca_buoi"] EV vào delta CUỐI của mọi ảnh có mặt.

    Chạy SAU phanh chống cháy và san phẳng cảnh — xem chú thích ở DEFAULTS.
    Ảnh giữ nguyên vì không có mặt thì bỏ qua; vẫn tôn trần max_ev_up/max_ev.
    Trả về số ảnh bị đổi."""
    bu = float(cfg.get("bu_sang_ca_buoi") or 0.0)
    if abs(bu) < 1e-9:
        return 0
    len_ = float(cfg.get("max_ev_up") or cfg["max_ev"])
    xuong = float(cfg["max_ev"])
    n = 0
    for r in items:
        if r.get("giu_nguyen_exposure") or r.get("delta_ev") is None:
            continue
        cu = float(r["delta_ev"])
        moi = float(np.clip(cu + bu, -xuong, len_))
        if abs(moi - cu) < 1e-9:
            continue
        r["delta_ev"] = round(moi, 4)
        r["notes"] = ";".join([v for v in [r.get("notes", ""), f"bu-sang{bu:+.2f}"] if v])
        n += 1
    return n


def _wb_theo_asshot(items: list, cfg: dict) -> int:
    """Quy trinh preset bo trong WB — BUOC 2: keo Temp ve As Shot cua TUNG MAY
    trong canh, he so wb_asshot_pull (nhanh "keo ve AsShot" co san tu thoi
    sidecar). Chi anh co r["asshot_K"] (uoc_asshot) — quy trinh cu khong doi.
    Anh ngay chi keo am, anh den chi keo lanh (wb_asshot_theo_chieu); keo duoi
    wb_asshot_min_K thi bo. Xem chu thich o DEFAULTS. Tra ve so anh bi doi.

    #[[ VI SAO CONG O CUOI, SAU SAN PHANG MAU VA DONG BO LOAT — y nhu
    #   _tint_theo_may: As Shot la cua MAY, khong phai phep do. Cong truoc thi
    #   san phang dua ca canh ve trung vi, canh tron hai may thi may nay an As
    #   Shot cua may kia (2709: A7M5 5317K dung chung canh voi Z5_2 5730K bi keo
    #   +168K thay vi +23K). As Shot lay TRUNG VI theo (canh, may): may doi K
    #   giua canh (SUB_6652-65 5880 -> SUB_6667+ 5560) khong lam anh nhap nhay.
    #
    #   AP CHO MOI anh dang As Shot cua (canh, may) do, KE CA anh khong tu co so:
    #   Sony de Auto khong ghi K, catalog chi tra As Shot cho anh Lightroom da
    #   dung (1005: 59/630) — chi keo nhung tam user da luot qua thi trong mot
    #   canh tam am tam lanh.
    #]]
    """
    if not cfg.get("wb_theo_asshot"):
        return 0
    pull = float(cfg.get("wb_asshot_pull") or 0.0)
    if pull <= 0:
        return 0
    tran = float(cfg["wb_temp_max"])
    nhom: dict = {}
    for r in items:
        if r.get("asshot_K"):
            nhom.setdefault((r.get("scene"), str(r.get("model") or "")), []).append(
                float(r["asshot_K"]))
    n = 0
    for r in items:
        ks = nhom.get((r.get("scene"), str(r.get("model") or "")))
        if not ks or not (r.get("crs_nen") or {}).get("__nen_wb"):
            continue
        a = float(np.median(ks))
        nen = preset_val(r, "Temperature")
        if nen <= 0:
            continue
        keo = float(np.clip(pull * (a - nen), -tran, tran))
        r["asshot_canh"] = round(a)
        if cfg.get("wb_asshot_theo_chieu") and (keo < 0 if r.get("ngoai_troi") else keo > 0):
            continue
        if abs(keo) < float(cfg.get("wb_asshot_min_K") or 0.0):
            continue
        r["temp_adj"] = float(r.get("temp_adj", 0.0)) + keo
        r["notes"] = ";".join([v for v in [r.get("notes", ""), f"wb-asshot{keo:+.0f}"] if v])
        n += 1
    return n


def _tint_theo_may(items: list, cfg: dict) -> int:
    """MUC 2b — lech Tint co dinh theo than may (wb_tint_theo_may). {} = TAT.

    #[[ VI SAO: ban quay 2 (2/10) user noi "anh Nikon qua tool deu bi am tim";
    #   ca 57 anh Nikon user sua Tint deu GIAM, trung vi -5 (16 -> 11). Preset
    #   +16 chinh cho Sony; Nikon render cung Tint do lech sang tim.
    #   Cong: TrainTool 57 sat / 0 xa. User duyet tan mat 3/10 (so_sanh_ung_vien.pdf).
    #
    #   VI SAO CONG O CUOI, SAU SAN PHANG MAU: ban dau cong ngay trong vong tung
    #   anh, roi san phang dua ca canh ve TRUNG VI tint. Canh tron hai may thi
    #   so lech di theo da so: TrainTool 12 anh SONY bi -5 (canh Nikon dong
    #   hon), 7 anh Nikon mat -5 (canh Sony dong hon); 2609: 2 Sony bi, 20 Nikon
    #   mat. San phang dua nen ve mot muc chung, roi moi cong lech cua tung may.
    #]]
    """
    bang = cfg.get("wb_tint_theo_may") or {}
    if not isinstance(bang, dict) or not bang:
        return 0
    n = 0
    for r in items:
        ten_m = str(r.get("model") or "").upper()
        for k_, v_ in bang.items():
            if k_ and str(k_).upper() in ten_m and float(v_):
                r["tint_adj"] = float(r.get("tint_adj", 0.0)) + float(v_)
                r["notes"] = ";".join([v for v in [r.get("notes", ""), "tint-theo-may"] if v])
                n += 1
                break
    return n


def _canh_am_nang(items: list, cfg: dict) -> set:
    """Cac canh ma WB dang keo LANH gan het tran: trung vi temp_adj cua canh <=
    -wb_tran_am_ti_le * wb_temp_max (den vang / den san khau, may dat K cao).
    wb_tran_am_ti_le = 0 -> tap rong (TAT)."""
    ti = float(cfg.get("wb_tran_am_ti_le") or 0.0)
    if ti <= 0:
        return set()
    nguong = -ti * float(cfg["wb_temp_max"])
    nhom: dict = {}
    for r in items:
        if not r.get("bw"):
            nhom.setdefault(r.get("scene"), []).append(float(r.get("temp_adj", 0.0)))
    return {s for s, v in nhom.items() if v and float(np.median(v)) <= nguong}


def _tint_tran_am(items: list, cfg: dict) -> int:
    """Canh am nang (_canh_am_nang): KHONG cong Tint duong (hong) theo mau da.

    #[[ VI SAO (8/10 vong 4, raw 19.4, 69 anh fisheye duoi den vang): phep do
    #   tint cua da = log2(G / sqrt(R*B)). Den vang lam B rat thap nen da "xanh
    #   la" theo phep do do; nhiet do chi keo toi tran -1000 K nen phan am con
    #   du bi doc thanh tint -> tool cong hong (+1.5..+3, Tint 13). Giai WB HAI
    #   CHIEU (doi_wb) dua da ve dich thi tint phai AM (-3..-7), va pixel trung
    #   tinh anh duyet noi Tint ~9.4 (tool 13, LR hong + vang hon ro).
    #   CHI KY YEU: thu cho MOI loai buoi thi buoi cuoi 2609 (kiem_2ban_quay)
    #   them 16 anh user DA DUYET WB bi xe dich > 4 Tint (6.57% -> 7.49%) —
    #   buoi cuoi user giu sac hong am o canh den vang. ]]
    Chi loai_buoi "ky_yeu", che do WB "skin". Tint am (xanh) giu nguyen. Tra ve
    so anh bi doi."""
    if cfg.get("wb") != "skin" or cfg.get("loai_buoi") != "ky_yeu":
        return 0
    am = _canh_am_nang(items, cfg)
    n = 0
    for r in items:
        if r.get("scene") in am and not r.get("bw") and float(r.get("tint_adj", 0.0)) > 0:
            r["tint_adj"] = 0.0
            r["notes"] = ";".join([v for v in [r.get("notes", ""), "tint-tran-am"] if v])
            n += 1
    return n


def _bu_sang_canh_am(items: list, cfg: dict) -> int:
    """Ky yeu: cong bu_sang_canh_am_ky_yeu EV vao delta cua anh trong canh am
    nang (_canh_am_nang) — Lightroom ve mat o do TOI hon preview may nhieu.

    #[[ VI SAO (8/10 vong 4, raw 19.4, hoi truong den vang, 102 anh duyet): mat
    #   Lightroom (do tren anh LR ve that) - mat preview - Exposure tool:
    #     WB keo lanh < 45 mired so voi WB may: ~0 EV (mat anh duyet - LR -0.1..+0.03)
    #     >= 45 mired (WB 4000-4200 K, may dat 5400 K): -0.70 EV; anh duyet sang
    #     hon LR v43: mat +0.55, khung +0.45, p50 +0.65, p90 +0.65 (p10 -0.6).
    #   Buoc nhay, khong tuyen tinh theo mired — nen chi ap cho canh am nang.
    #   BO QUA anh tool da keo >= bu_sang_canh_am_tran EV: 9 anh mat do -3.7..
    #   -8.3 EV (bong toi / mat nho) tool da +2.3..+2.8, anh duyet lai TOI hon
    #   LR 0.5-1.5 EV — keo them la sai chieu. Anh thuong cua canh: delta 0.2-0.6. ]]
    Chay SAU phanh va san phang (nhu _bu_sang_ca_buoi); ton tran max_ev_up.
    Tra ve so anh bi doi."""
    if cfg.get("loai_buoi") != "ky_yeu":
        return 0
    bu = float(cfg.get("bu_sang_canh_am_ky_yeu") or 0.0)
    if bu <= 0:
        return 0
    am = _canh_am_nang(items, cfg)
    if not am:
        return 0
    len_ = float(cfg.get("max_ev_up") or cfg["max_ev"])
    tran_ = float(cfg.get("bu_sang_canh_am_tran") or 0.0)
    n = 0
    for r in items:
        if (r.get("scene") not in am or r.get("bw") or r.get("giu_nguyen_exposure")
                or r.get("delta_ev") is None):
            continue
        cu = float(r["delta_ev"])
        if tran_ > 0 and cu >= tran_:
            continue
        moi = float(min(cu + bu, len_))
        if moi - cu < 0.005:
            continue
        r["delta_ev"] = round(moi, 4)
        r["notes"] = ";".join([v for v in [r.get("notes", ""), f"bu-sang-canh-am{moi - cu:+.2f}"] if v])
        n += 1
    return n


def _wb_ky_yeu(items: list, cfg: dict) -> int:
    """Cong lech WB phong cach ky yeu (wb_bu_ky_yeu: K, Tint) vao temp_adj /
    tint_adj CUOI — sau san phang mau, dong bo loat, As Shot va tint theo may.

    Chi loai_buoi "ky_yeu" — KHONG phu thuoc o "grade" (8/10 dem: WB la buoc co
    dinh cua chuoi chinh_mau_da, HSL / Color Grading xu ly phan con lai). Bo qua
    anh B/W, anh WB dang cham tran wb_temp_max va canh am nang (_canh_am_nang) —
    den mau nang, anh duyet o do LANH hon / it hong hon chu khong am hon. Xem chu
    thich o DEFAULTS. Tra ve so anh bi doi."""
    if cfg.get("loai_buoi") != "ky_yeu":
        return 0
    bu = dict(cfg.get("wb_bu_ky_yeu") or {})
    k_, t_ = float(bu.get("Temperature") or 0.0), float(bu.get("Tint") or 0.0)
    if not (k_ or t_):
        return 0
    tran = float(cfg["wb_temp_max"])
    am = _canh_am_nang(items, cfg)
    n = 0
    for r in items:
        if (r.get("bw") or abs(float(r.get("temp_adj", 0.0))) >= tran - 1.0
                or r.get("scene") in am):
            continue
        r["temp_adj"] = float(r.get("temp_adj", 0.0)) + k_
        r["tint_adj"] = float(r.get("tint_adj", 0.0)) + t_
        r["notes"] = ";".join([v for v in [r.get("notes", ""), f"wb-ky-yeu{k_:+.0f}K{t_:+.0f}"] if v])
        n += 1
    return n


# ======================================================================
# 5. Ghi sidecar
# ======================================================================

def compute_values(r: dict, cfg: dict, crs: dict, atn: dict) -> dict:
    """Tính giá trị mới từ preset gốc + delta. Thuần tính toán, không đụng file.

    Dùng chung cho cả hai nguồn: sidecar .xmp và thông số lấy từ catalog Lightroom.
    Trả về dict {tên field crs: chuỗi giá trị} để bên gọi tự quyết ghi đi đâu.
    """

    #[[ Preset khong ap WB / Tone (quy trinh moi 3/10) -> tinh tren nen SAY, va
    #   phai TU GHI nhom do: Lightroom dang o As Shot / 0 chu khong o nen. Xem
    #   nen_cho_anh(). Anh co preset day du thi crs di qua nguyen ven. ]]
    crs_goc = dict(crs or {})            # TRUOC nen_cho_anh — so goc that (anh B/W)
    crs = nen_cho_anh(crs, cfg)
    nen_tone, nen_wb = bool(crs.get("__nen_tone")), bool(crs.get("__nen_wb"))
    r["nen_tone"], r["nen_wb"] = nen_tone, nen_wb
    #[[ ANH DEN TRANG (8/10): preview cua may la B/W, hoac Lightroom / sidecar
    #   da de Black & White. Giu BW (ghi ConvertToGrayscale — Lightroom mac dinh
    #   dung RAW ra MAU du may chup B/W), van chinh Exposure / Highlights /
    #   Shadows / Contrast / curve. KHONG ghi WB va Color Grading: hai thu do do
    #   tu mau da tren preview — preview xam thi so do la rac (lan ghi 8/10 buoi
    #   Kyyeu dat 5518 K / tint 23 cho ca loat anh B/W), va trong che do B/W cua
    #   Lightroom, doi WB la doi pha tron xam — anh doi sang toi ma khong ai muon. ]]
    bw = bool(r.get("bw")) or la_bw_catalog(crs)
    r["bw"] = bw
    if bw:
        r["gr_sat"] = 0
        r["temp_adj"] = 0.0
        r["tint_adj"] = 0.0
        if "den-trang" not in str(r.get("notes", "")):
            r["notes"] = (str(r.get("notes", "")) + ";den-trang: giu BW, khong doi WB/mau").strip(";")

    def baseline(crs_key: str) -> float:
        """Giá trị preset gốc: ưu tiên marker của lần chạy trước để không cộng dồn."""
        mk = ATN_FIELDS[crs_key]
        if mk in atn:
            r["rerun"] = True
            return get_f(atn, mk, 0.0)
        return get_f(crs, crs_key, 0.0)

    r.setdefault("rerun", False)
    old_exp = baseline("Exposure2012")
    old_hl = baseline("Highlights2012")
    old_sh = baseline("Shadows2012")
    old_temp = baseline("Temperature")
    old_tint = baseline("Tint")

    new_exp = float(np.clip(old_exp + r["delta_ev"], -5.0, 5.0))
    new_hl = int(np.clip(old_hl + r["hl_adj"], -100, 100))
    new_sh = int(np.clip(old_sh + r["sh_adj"], -100, 100))

    # Luôn ghi lại mọi trường mình quản lý (kể cả khi delta = 0). Nếu chỉ ghi khi
    # có thay đổi thì lần chạy lại với tham số khác sẽ để sót giá trị của lần trước.
    changes = {"Exposure2012": fmt_f(new_exp)}
    if cfg["highlights"] or ATN_FIELDS["Highlights2012"] in atn or nen_tone:
        changes["Highlights2012"] = fmt_i(new_hl)
    if cfg["shadows"] or ATN_FIELDS["Shadows2012"] in atn or nen_tone:
        changes["Shadows2012"] = fmt_i(new_sh)
    # Ba thanh tool khong chinh, chi dat dung gia tri preset SAY khi preset bo trong
    for key in ("Contrast2012", "Whites2012", "Blacks2012"):
        r.pop("new_" + key, None)
        if nen_tone and key in crs:
            changes[key] = fmt_i(int(get_f(crs, key, 0.0)))
            r["new_" + key] = int(get_f(crs, key, 0.0))

    #[[ Parametric curve: cộng lên giá trị preset, không ghi đè.
    #
    #   Point curve (ToneCurvePV2012) KHÔNG đụng tới — Lightroom cộng dồn hai
    #   thứ, nên đường cong riêng của preset giữ nguyên vẹn.
    #]]
    if cfg.get("curve", True):
        for key, adj in (("ParametricHighlights", r.get("cv_hl", 0)),
                         ("ParametricLights", r.get("cv_lt", 0)),
                         ("ParametricDarks", r.get("cv_dk", 0)),
                         ("ParametricShadows", r.get("cv_sh", 0))):
            # Lấy từ ATN_FIELDS chứ đừng tự ghép chuỗi: "Base" + "Highlights"
            # trùng đúng marker của Highlights2012, đọc nhầm sang mốc 16 của
            # nó thay vì mốc 0 của ParametricHighlights.
            mk = ATN_FIELDS[key]
            base_v = get_f(atn, mk, 0.0) if mk in atn else get_f(crs, key, 0.0)
            val = int(np.clip(base_v + adj, -100, 100))
            changes[key] = fmt_i(val)
            r["new_" + key] = val
            r["old_" + key] = int(base_v)

    #[[ Color Grading: so MOI cua banh xe midtone / highlight da tinh san o
    #   grade_theo_trang_thai() (plan goi sau compute_values, can WB cuoi).
    #   Duong sidecar: write_sidecars goi lai compute_values SAU plan nen doc
    #   duoc ngay. Ke ca truong hop TRA VE SO GOC (r["da_grade"]). ]]
    if r.get("gr_ghi") and r.get("gr_mid"):
        changes["ColorGradeMidtoneHue"] = str(int(r["gr_mid"][0]))
        changes["ColorGradeMidtoneSat"] = fmt_i(int(np.clip(r["gr_mid"][1], 0, 100)))
    if r.get("gr_ghi") and r.get("gr_hi"):
        changes["SplitToningHighlightHue"] = str(int(r["gr_hi"][0]))
        changes["SplitToningHighlightSaturation"] = fmt_i(int(np.clip(r["gr_hi"][1], 0, 100)))

    new_temp, new_tint = old_temp, old_tint
    if cfg["wb"] != "off" and old_temp <= 0:
        r["notes"] = (r.get("notes", "") + ";bo-qua-WB-preset-dung-As-Shot").strip(";")
    elif cfg["wb"] != "off":
        new_temp = float(np.clip(old_temp + r["temp_adj"], 2000, 50000))
        new_tint = float(np.clip(old_tint + r["tint_adj"], -150, 150))
    if bw:
        new_temp, new_tint = old_temp, old_tint
        changes["ConvertToGrayscale"] = "True"
        #[[ Lan chay TRUOC (khi tool chua biet B/W) co the da ghi WB rac cho anh
        #   nay — buoi Kyyeu 8/10: 5518 K / tint 23. Chay lai (co moc goc) thi TRA
        #   WB ve dung so goc (old_* = moc truoc lan ghi dau). Anh chua tung bi
        #   ghi thi so goc = so dang co -> plugin so thay bang nhau, khong ghi. ]]
        #   So goc lay TRUOC nen_cho_anh: preset de WB trong (As Shot) thi old_*
        #   la nen SAY (5250 K) — dung cho anh mau, khong phai so goc cua anh.
        mk_t, mk_n = ATN_FIELDS["Temperature"], ATN_FIELDS["Tint"]
        goc_t = get_f(atn, mk_t, 0.0) if mk_t in atn else get_f(crs_goc, "Temperature", 0.0)
        goc_n = get_f(atn, mk_n, 0.0) if mk_n in atn else get_f(crs_goc, "Tint", 0.0)
        if goc_t > 0 and (r.get("rerun") or mk_t in atn):
            new_temp, new_tint = goc_t, goc_n
            changes["Temperature"] = str(int(round(goc_t)))
            changes["Tint"] = fmt_i(goc_n)
            r["bw_tra_wb"] = True
    elif old_temp > 0 and (cfg["wb"] != "off" or ATN_FIELDS["Temperature"] in atn or nen_wb):
        changes["Temperature"] = str(int(round(new_temp)))
        changes["Tint"] = fmt_i(new_tint)
        if str(crs.get("WhiteBalance", "")) != "Custom":
            changes["WhiteBalance"] = "Custom"
    #[[ Nen WB khac WB dang co trong Lightroom (As Shot) -> PHAI ghi ca khi tool
    #   khong doi gi (temp_adj = 0): write_lr_job binh thuong bo trong o WB khi
    #   moi == cu, va de trong thi anh o lai As Shot. ]]
    r["wb_ep_ghi"] = nen_wb and old_temp > 0 and not bw

    r.update(old_exposure=old_exp, new_exposure=new_exp,
             old_highlights=int(old_hl), new_highlights=new_hl,
             old_shadows=int(old_sh), new_shadows=new_sh,
             old_temp=int(old_temp), new_temp=int(round(new_temp)),
             old_tint=int(old_tint), new_tint=int(round(new_tint)))
    return changes


def apply_to_sidecar(r: dict, cfg: dict, backup_dir: Path | None, root: Path, dry: bool) -> dict:
    sc = Path(r["sidecar"])
    # Doc/ghi nhi phan: giu nguyen line ending (Adobe dung LF) va BOM neu co.
    # read_text/write_text se doi LF -> CRLF tren Windows va viet lai ca file.
    text = sc.read_bytes().decode("utf-8")
    crs = read_crs(text)
    atn = read_ns(text, ATN_PREFIX) if cfg["marker"] else {}
    changes = compute_values(r, cfg, crs, atn)

    if dry:
        return r

    if backup_dir is not None:
        try:
            rel = sc.relative_to(root)
        except ValueError:
            rel = Path(sc.name)
        dst = backup_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copy2(sc, dst)

    out = text
    if cfg["marker"]:
        # ghi baseline TRƯỚC khi đổi crs, và chỉ ghi lần đầu. Mốc lấy theo NỀN mà
        # compute_values đã tính trên (nen_cho_anh): preset bỏ trống WB/Tone mà
        # ghi mốc As Shot / 0 thì lần chạy sau tính trên một nền khác lần đầu.
        crs_nen = nen_cho_anh(crs, cfg)
        for crs_key, mk in ATN_FIELDS.items():
            if mk not in atn and crs_key in crs_nen:
                out = set_ns(out, ATN_PREFIX, mk, str(crs_nen[crs_key]), ATN_NS)
    for k, v in changes.items():
        out = set_crs(out, k, v)
    out = touch_metadata_date(out)

    tmp = sc.with_suffix(sc.suffix + ".tmp")
    tmp.write_bytes(out.encode("utf-8"))
    os.replace(tmp, sc)
    return r


# ======================================================================
# 5b. Nguồn "catalog": lấy thông số từ Lightroom, khỏi cần .xmp
# ======================================================================

# Plugin xuất ra đây; autotone đọc vào. Nhờ vậy không phải bắt Lightroom ghi
# hàng nghìn sidecar (Ctrl+S trên thư mục lớn rất lâu và trông như bị treo).
EXPORT_FIELDS = ["Exposure2012", "Highlights2012", "Shadows2012",
                 "Temperature", "Tint", "AsShotTemperature", "AsShotTint",
                 # 3/10: de nhan ra preset bo trong WB / Tone (preset_chua_ap).
                 # WhiteBalance la CHU ("As Shot", "Custom"...), khong phai so.
                 "WhiteBalance", "Contrast2012", "Whites2012", "Blacks2012",
                 # 8/10: B/W + Color Grading / Saturation / Vibrance (COT_MAU)
                 "ConvertToGrayscale", *COT_MAU,
                 # 8/10 vong 5: HSL Red / Orange / Yellow (COT_HSL)
                 *COT_HSL]
BASELINE_NAME = "_autotone_baseline.tsv"

# So anh bi bo qua vi nguoi dung da sua tay o lan chay gan nhat — giao dien doc
# de bao cho nguoi dung biet vi sao so anh trong bang it di.
SO_ANH_NGUOI_SUA = 0
#[[ Buoi da duoc LAM LAI sau lan tool ghi gan nhat — xem buoi_dat_lai(). "" = khong;
#   "khong-moc" = file moc da bi xoa; "dat-lai" = ca buoi doi dong loat (ap lai
#   preset / Reset). Giao dien doc de noi ra thay cho "bo qua N anh sua tay". ]]
DAT_LAI_BUOI = ""
#[[ Ly do KHONG loc anh sua tay o lan chay nay, "" neu co loc binh thuong.
#   Giao dien doc de noi ra — mot buoc loc tu tat ma im lang thi khong ai biet. ]]
CANH_BAO_XUAT = ""
#[[ Plugin trong Lightroom con ban cu ma preset da bo trong Tone — xem
#   canh_bao_plugin_cu(). Giao dien doc de noi ra; "" = khong sao. ]]
CANH_BAO_PLUGIN = ""


def canh_bao_plugin_cu(export: dict, cfg: dict | None = None) -> str:
    """"" neu on; khac "" khi ban xuat la cua plugin CU (khong co cot WhiteBalance)
    ma phan lon anh dang Highlights = Shadows = 0 — dau hieu preset bo trong Tone.
    Hoac (8/10) bat "Day tone ve da trang hong" ma ban xuat chua co cot Color
    Grading: tool khong biet toning / Saturation cua preset nen khong grade.

    #[[ VI SAO PHAI NOI: preset_chua_ap() can cot WhiteBalance / Contrast2012 de
    #   nhan ra quy trinh moi. Plugin cu khong xuat chung -> tool tinh nhu preset
    #   day du: Highlights tinh tu 0 thay vi 16, khong ghi Contrast / Whites /
    #   Blacks, WB tinh tu As Shot -> ra mot kieu anh khac, khong bao loi gi. Quen
    #   Reload plugin sau khi cap nhat la chuyen de xay ra nhat.
    #   Quy trinh cu (preset day du) thi Highlights / Shadows = 16 -> khong bao.
    #]]
    """
    #  dict(...) boc ngoai: xem _theo_may (Cython 3 crash voi (tham_so or {}))
    recs = [v for v in dict(export or {}).values() if isinstance(v, dict)]
    if (recs and (cfg or {}).get("grade")
            and not any("SplitToningHighlightSaturation" in v for v in recs)):
        return ("Đang bật “Đẩy tone về da trắng hồng” nhưng plugin trong Lightroom là "
                "bản CŨ, chưa xuất Color Grading / Saturation của preset — tool không "
                "biết số gốc nên KHÔNG grade ảnh nào (WB, Exposure vẫn ghi bình thường). "
                "Vào Lightroom: File > Plug-in Manager > AutoTone > Reload Plug-in, rồi "
                "bấm “Nạp lại catalog”.")
    c_ = dict(cfg or {})
    if (recs and c_.get("loai_buoi") == "ky_yeu" and c_.get("hsl_da_ky_yeu")
            and not any("HueAdjustmentOrange" in v for v in recs)):
        return ("Loại buổi Kỷ yếu có chỉnh HSL kênh da nhưng plugin trong Lightroom là bản "
                "CŨ, chưa xuất HSL của preset — tool KHÔNG chỉnh HSL ảnh nào (WB, Exposure "
                "vẫn ghi bình thường). Vào Lightroom: File > Plug-in Manager > AutoTone > "
                "Reload Plug-in, rồi bấm “Nạp lại catalog”.")
    if not recs or any("WhiteBalance" in v for v in recs):
        return ""
    khong = sum(1 for v in recs if get_f(v, "Highlights2012", 16.0) == 0
                and get_f(v, "Shadows2012", 16.0) == 0)
    if khong * 2 < len(recs):
        return ""
    return (f"{khong}/{len(recs)} ảnh đang Highlights = Shadows = 0 (preset bỏ trống Tone?) "
            "nhưng plugin trong Lightroom là bản CŨ, chưa xuất cột WhiteBalance — tool "
            "không nhận ra để tự ghi WB và Tone. Vào Lightroom: File > Plug-in Manager > "
            "AutoTone > Reload Plug-in, rồi Phân tích lại.")

#[[ Đường dẫn ĐÚNG NHƯ LIGHTROOM LƯU, giữ kèm trong mỗi bản ghi.
#
#   Vì sao cần: plugin tra ảnh bằng catalog:findPhotoByPath(), hàm này so chuỗi
#   khá cứng. Đường dẫn autotone quét từ hệ thống file có thể khác Lightroom ở
#   hoa/thường (F:\BUOI\a.ARW vs F:\Buoi\a.ARW) hay ở dạng gạch chéo — lệch một
#   cái là ảnh đó lặng lẽ không được áp. Trong plugin.log cũ chính là mấy dòng
#   "9 khong co trong catalog", "14 khong co trong catalog".
#
#   Bản xuất từ plugin (export_*.tsv) chứa đường dẫn do chính Lightroom đọc ra.
#   Giữ lại chuỗi đó rồi gửi ngược nguyên văn trong job thì không còn cửa lệch.
#]]
LR_PATH_KEY = "__lrpath"


def khoa_duong_dan(p) -> str:
    """Khoá để so hai đường dẫn có trỏ cùng một file không.

    #[[ VI SAO KHONG DUNG THANG os.path.normcase().
    #
    #   normcase() CHI viet thuong tren Windows. Tren macOS va Linux no tra ve
    #   nguyen van. Nhung o dia mac dinh cua macOS (APFS, HFS+) LA khong phan
    #   biet hoa thuong — y het Windows. Nen tren Mac, Lightroom bao
    #   /Users/x/Anh/DSC01.ARW con Python liet ke ra /Users/x/anh/DSC01.arw thi
    #   ca hai la MOT FILE, ma so chuoi lai khac nhau.
    #
    #   Hau qua: "ban xuat chi khop 0 anh" tren mot buoi ma ban xuat hoan toan
    #   dung. Chu thich cua _read_tsv van viet "khoa la duong dan viet thuong" —
    #   dung tren Windows, sai tren Mac, va khong ai doc lai chu thich khi di
    #   truy loi.
    #
    #   Linux thi de nguyen: o dia o do that su phan biet hoa thuong, viet
    #   thuong di la co the gop nham hai file khac nhau.
    #]]
    """
    d = os.path.abspath(str(p))
    if sys.platform.startswith("win") or sys.platform == "darwin":
        return d.lower()
    return os.path.normcase(d)


def _read_tsv(path: Path) -> dict[str, dict]:
    """Đọc TSV path→giá trị. Khoá chuẩn hoá bằng khoa_duong_dan()."""
    out: dict[str, dict] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    lines = [ln for ln in lines if not ln.startswith("#")]
    if not lines:
        return out
    cols = lines[0].split("\t")
    for line in lines[1:]:
        if not line:
            continue
        v = line.split("\t")
        rec = {cols[i]: v[i] for i in range(1, min(len(cols), len(v))) if v[i] != ""}
        if v[0]:
            rec[LR_PATH_KEY] = v[0]        # giu nguyen van, xem LR_PATH_KEY
            out[khoa_duong_dan(v[0])] = rec
    return out


def _write_tsv(path: Path, cols: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = ["path\t" + "\t".join(cols)] + ["\t".join(r) for r in rows]
    tmp = path.with_suffix(".part")
    # newline="" de KHONG bien \n thanh \r\n tren Windows — Lua doc dong se
    # dinh mot ky tu \r o cuoi, tuy da trim nhung dung de sinh ra van hon.
    with io.open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write("\n".join(body) + "\n")
    os.replace(tmp, path)


def plugin_khac(dang_dung: Path | None = None) -> list:
    """Bản plugin KHÁC mà Lightroom có thể đang ghi vào. [(thư mục, lúc sửa)].

    #[[ VI SAO PHAI DI TIM CHUYEN NAY.
    #
    #   Trong may co the co NHIEU ban AutoTone.lrplugin: ban goc trong thu muc
    #   ma nguon, ban nam trong .app, va ban app chep ra thu muc du lieu nguoi
    #   dung. App CHI doc jobs/ cua ban cuoi. Lightroom thi ghi vao ban ma
    #   NGUOI DUNG da Add trong Plug-in Manager.
    #
    #   Add nham ban thi hai ben lam viec o hai thu muc khac nhau va KHONG BEN
    #   NAO BAO LOI: Lightroom xuat thanh cong, app thi bao "chua co ban xuat"
    #   hoac doc phai ban cu. 11/9 tren may Mac dung la chuyen nay — plugin
    #   duoc Add tu thu muc ChuyenSangMac.
    #
    #   Nen: do xem co ban nao khac co jobs/ MOI HON ban dang dung khong, roi
    #   noi thang ra ca hai duong dan. Chi doc mtime, khong dung vao gi.
    #]]
    """
    dang_dung = Path(dang_dung or LR_PLUGIN_DIR)
    ung_vien = []
    try:
        goc_ma = Path(__file__).resolve().parent
        ung_vien.append(goc_ma / "AutoTone.lrplugin")
        #[[ Ban nam trong goi .app: .../AutoTone.app/Contents/(Resources|MacOS) ]]
        if getattr(sys, "frozen", False):
            meip = getattr(sys, "_MEIPASS", None)
            if meip:
                ung_vien.append(Path(meip) / "AutoTone.lrplugin")
        ung_vien.append(Path(sys.argv[0]).resolve().parent / "AutoTone.lrplugin")
    except (OSError, ValueError):
        pass

    ra, da_thay = [], set()
    try:
        khoa_dang = khoa_duong_dan(dang_dung)
    except (OSError, ValueError):
        khoa_dang = str(dang_dung)
    for c in ung_vien:
        try:
            k = khoa_duong_dan(c)
        except (OSError, ValueError):
            continue
        if k == khoa_dang or k in da_thay or not (c / "jobs").is_dir():
            continue
        da_thay.add(k)
        moi_nhat = 0.0
        for f in (c / "jobs").glob("*"):
            try:
                moi_nhat = max(moi_nhat, f.stat().st_mtime)
            except OSError:
                pass
        if moi_nhat:
            ra.append((c, moi_nhat))
    return sorted(ra, key=lambda x: -x[1])


def latest_catalog_export(job_dir: Path | None = None) -> Path | None:
    """File xuất mới nhất do plugin Lightroom ghi ra.

    #[[ "MOI NHAT" PHAI LA THEO THOI GIAN SUA FILE, KHONG PHAI THEO TEN.
    #
    #   Ban cu lay sorted(glob(...))[-1] — tuc xep theo TEN. Ten co dang
    #   export_20260911_160610.tsv nen xep theo ten thuong trung voi xep theo
    #   thoi gian... nhung chi KHI moi ten deu dung mot khuon. Chi can mot file
    #   le khuon (chep tay, doi ten, hoac sinh ra tu ban plugin khac) la thu tu
    #   dao lon va app om mot ban xuat cu ma van goi no la "moi nhat".
    #
    #   Hong kieu nay khong bao loi: no chi lang le tinh tren so lieu cua buoi
    #   khac. Da mat gan mot tieng hom 4/9 vi dung chuyen do.
    #
    #   Doc mtime co the that bai (file vua bi xoa) nen boc try; luc do lui ve
    #   xep theo ten, van hon la khong tra ve gi.
    #]]
    """
    d = Path(job_dir or LR_JOB_DIR)
    if not d.is_dir():
        return None
    files = [f for f in d.glob("export_*.tsv") if ghi_xong(f)]
    if not files:
        return None
    try:
        return max(files, key=lambda p: (p.stat().st_mtime_ns, p.name))
    except OSError:
        return sorted(files)[-1]


#[[ BAN XUAT PHAI LA CUA DUNG THU MUC — khong phai "file moi nhat" bat ky.
#
#   Gap that 3/10, buoi G:\1009 (437 anh): app bao "ban xuat chi khop 0 anh —
#   437 anh se bi bo qua". File app dang doc la export_20261003_082531.tsv,
#   630 dong, TOAN anh G:\1005 — Lightroom dang mo thu muc 1005 va lenh xuat o
#   menu lay theo vung dang xem. latest_catalog_export() chi biet "moi nhat",
#   khong biet "cua ai".
#
#   Nay chon ban MOI NHAT CO ANH CUA THU MUC NAY. Plugin cung khong con xoa ban
#   xuat cua buoi khac (truoc chi giu dung mot file cho ca catalog — xuat buoi
#   nay la mat ban cua buoi kia).
#
#   Doc tung file de biet no phu thu muc nao thi ton: watcher cua giao dien goi
#   moi 3 giay. Nen nho ket qua theo (mtime, size) — file khong doi thi khong doc
#   lai.
#]]
_PHU_XUAT: dict = {}


def _thu_muc_cua_ban_xuat(p: Path) -> frozenset:
    """Tap thu muc cha (khoa_duong_dan) cua moi anh trong mot ban xuat."""
    try:
        st = p.stat()
    except OSError:
        return frozenset()
    nho = _PHU_XUAT.get(str(p))
    if nho and nho[0] == (st.st_mtime_ns, st.st_size):
        return nho[1]
    cha = set()
    try:
        with io.open(p, encoding="utf-8", errors="replace") as fh:
            dau = True
            for dong in fh:
                if dong.startswith("#"):
                    continue
                if dau:                 # dong tieu de
                    dau = False
                    continue
                duong = dong.split("\t", 1)[0].strip()
                if duong:
                    cha.add(khoa_duong_dan(os.path.dirname(duong)))
    except OSError:
        return frozenset()
    kq = frozenset(cha)
    _PHU_XUAT[str(p)] = ((st.st_mtime_ns, st.st_size), kq)
    return kq


def _phu_thu_muc(cha: frozenset, goc: str, gom_con: bool) -> bool:
    if goc in cha:
        return True
    return gom_con and any(c.startswith(goc.rstrip("\\/") + os.sep) for c in cha)


def ban_xuat_cho_thu_muc(folder, job_dir: Path | None = None,
                         gom_con: bool = False) -> Path | None:
    """Bản xuất MỚI NHẤT có ảnh của thư mục này (None nếu chưa có bản nào).

    gom_con = True: tính cả ảnh ở thư mục con (ô "Gồm cả thư mục con")."""
    if not folder:
        return None
    d = Path(job_dir or LR_JOB_DIR)
    if not d.is_dir():
        return None
    goc = khoa_duong_dan(folder)
    ds = []
    for f in d.glob("export_*.tsv"):
        try:
            ds.append((f.stat().st_mtime_ns, f.name, f))
        except OSError:
            continue
    for _, _, f in sorted(ds, reverse=True):
        if ghi_xong(f) and _phu_thu_muc(_thu_muc_cua_ban_xuat(f), goc, gom_con):
            return f
    return None


#[[ KET QUA CUA MOT LAN APP NHO PLUGIN XUAT — plugin ghi jobs/ketqua_xuat.txt.
#
#   Truoc day plugin khong tim thay anh nao (thu muc chua import, hoac da go
#   khoi catalog) thi chi ghi mot dong vao plugin.log va KHONG ghi gi khac. App
#   doi du 90 giay roi bao "plugin da nhan nhung chua xuat xong" — sai benh. Va
#   so anh 1 sao bi bo (quy uoc "1 sao khong xuat") chi nam trong nhat ky, nen
#   app goi chung ca chung lan anh thieu that la "se bi bo qua".
#]]
KET_QUA_XUAT = "ketqua_xuat.txt"


def xoa_ban_xuat(folder, job_dir: Path | None = None, gom_con: bool = True) -> int:
    """Xoá MỌI bản xuất catalog (export_*.tsv) có ảnh của thư mục này — nút
    “Xoá catalog cũ” (8/10). Trả số file đã xoá. Không đụng job / nhật ký / bản
    xuất của buổi khác."""
    if not folder:
        return 0
    d = Path(job_dir or LR_JOB_DIR)
    if not d.is_dir():
        return 0
    goc = khoa_duong_dan(folder)
    n = 0
    for f in list(d.glob("export_*.tsv")):
        try:
            if _phu_thu_muc(_thu_muc_cua_ban_xuat(f), goc, gom_con):
                f.unlink()
                n += 1
        except OSError:
            continue
    return n


def ket_qua_xuat(job_dir: Path | None = None) -> dict:
    """{} nếu chưa có. Khoá: thu_muc, so_anh, bo_sao, file, loi, cach, khi (mtime)."""
    p = Path(job_dir or LR_JOB_DIR) / KET_QUA_XUAT
    try:
        txt = p.read_text(encoding="utf-8", errors="replace")
        khi = p.stat().st_mtime
    except OSError:
        return {}
    out: dict = {"khi": khi}
    for dong in txt.splitlines():
        k, sep, v = dong.partition("=")
        if sep:
            out[k.strip()] = v.strip()
    for k in ("so_anh", "bo_sao"):
        try:
            out[k] = int(out.get(k) or 0)
        except ValueError:
            out[k] = 0
    return out


def ghi_xong(p: Path) -> bool:
    """File xuất đã ghi xong chưa? True = đọc được.

    #[[ VI SAO CAN, KHI PLUGIN DA GHI .part ROI DOI TEN
    #
    #   Plugin ghi ra export_*.tsv.part roi LrFileUtils.move sang ten that —
    #   dung y de app khong bao gio doc phai file do. Nhung tren Windows,
    #   move sang mot ten DA TON TAI khong nguyen tu: no xoa file cu roi chep
    #   noi dung sang. Trong khoang chep do, app doc duoc mot file cut.
    #
    #   Do that 25/09: plugin bao "xuat 3461 anh" (dem tu chinh bien lines),
    #   ma file tren dia chi 425 dong va KET THUC GIUA MOT DONG:
    #
    #       ...<TAB>16<TAB>5250<TAB>16<TAB><CRLF>G:/PerfectMalai/DSC07725.ARW<TAB>0<TAB>1
    #
    #   20476 byte, trong khi du 3461 dong phai ~166 KB. App doc file do roi
    #   bao "3036 anh se bi bo qua" — mot con so hoan toan bia, va nguoi dung
    #   xuat lai bao nhieu lan cung ra mot so khac nhau.
    #
    #   Dau hieu nhan biet chac chan nhat chinh la cho do: plugin ghi
    #   table.concat(lines, "\n") .. "\n" nen file HOAN CHINH luon ket thuc
    #   bang xuong dong. Cut giua dong thi chac chan dang ghi do.
    #]]
    """
    try:
        if p.stat().st_size < 2:
            return False
        with p.open("rb") as f:
            f.seek(-1, 2)
            return f.read(1) in (b"\n", b"\r")
    except OSError:
        return False


def read_catalog_export(path: Path) -> dict[str, dict]:
    return _read_tsv(Path(path))


def baseline_path(folder: Path) -> Path:
    return Path(folder) / BASELINE_NAME


def xoa_du_lieu_buoi(folder: Path, job_dir: Path | None = None,
                     ca_ban_xuat: bool = False, xoa_moc: bool = False) -> dict:
    """Xoa dau vet tool da luu cho mot buoi chup. Tra ve thong ke da xoa.

    #[[ 3/10: MOC GOC GIU LAI, tru khi xoa_moc=True.
    #
    #   Ban dau nut nay xoa ca _autotone_baseline.tsv ("ba thu phai xoa cung
    #   nhau"). Nhung tu truoc toi 3/10 nut tren giao dien CHUA BAO GIO chay
    #   duoc (goi ham khong ton tai) — nen chua ai thay hau qua cua viec xoa moc.
    #   Sua nut xong thi no lo ra: anh trong Lightroom con mang so tool ghi lan
    #   truoc (nguoi dung chi muon chay lai, khong Reset / import lai), xoa moc
    #   thi lan sau lay chinh so cu lam nen roi CONG THEM lan nua — Exposure
    #   -0.31 thanh -0.62, Highlights -29 thanh -74. Preview trong RAW khong doi
    #   theo Lightroom nen delta tinh ra lan hai y het lan dau.
    #
    #   Giu moc thi ca hai truong hop deu dung: import lai / ap lai cung preset
    #   -> moc = gia tri preset = catalog; chua Reset -> tinh lai tu gia tri
    #   TRUOC khi tool cham. Doi sang preset bo trong WB/Tone thi
    #   attach_catalog_settings tu nhan ra (moc-cu-khac-quy-trinh).
    #   Con lai mot ca moc sai: doi so cua chinh preset (vd Highlights 16 -> 10)
    #   roi chay lai — luc do moi can xoa_moc=True.
    #]]

    VI SAO CAN
        Import lai mot buoi vao Lightroom roi xuat thong so, tool van nho lan
        chay truoc: no thay catalog khac voi cai minh da ghi, ket luan "nguoi
        dung sua tay" va bo qua gan het buoi. Ngay 17.09 gap dung ca do —
        718/734 anh bi bo qua.

        Ba thu phai xoa cung nhau, thieu mot cai la van con vet:

          _autotone_baseline.tsv   moc goc cua tung anh (nam trong thu muc anh)
          apply_*_<ten>.done       tool da ghi gi o lan chay truoc
          apply_*_<ten>.tsv        job chua kip ap, cung mang gia tri cu

        MAC DINH KHONG dung toi export_*.tsv: do la ban xuat MOI tu catalog,
        tuc chinh thu nguoi dung vua tao de chay lai. Xoa no la bat ho xuat lai.

    ca_ban_xuat=True THI XOA CA NO
        Can khi nguoi dung muon "nhan dien lai catalog tu dau" that su. Giu
        ban xuat cu lai thi app van doc no — va neu ban xuat do thieu anh (vi
        luc xuat chi chon mot phan catalog), buoi chup se tiep tuc bi bo qua
        dung nhung anh do, du da bam xoa du lieu.

        Gap that 25/09: thu muc 3461 anh, ban xuat chi co 851 dong. Bam xoa
        du lieu xong van bao "2610 anh se bi bo qua", vi ban xuat cu con
        nguyen.

        3/10: CHI xoa ban xuat CO ANH CUA BUOI NAY (ban_xuat_cho_thu_muc). Ban
        cu xoa HET export_*.tsv vi luc do app chi biet doc "file moi nhat" —
        nay app chon theo thu muc nen ban xuat cua buoi khac giu lai duoc, va
        xoa no la bat buoi kia xuat lai vo co.
        (Cung ngay 3/10 moi biet: nut "Xoa du lieu cu" tren giao dien goi mot
        ham KHONG TON TAI — at.ban_xuat_moi_nhat — nen tu truoc toi nay bam vao
        la vang loi ngam, khong xoa gi ca. Xem kiem_tham_chieu.py.)

    Chi xoa file cua DUNG buoi nay — job cua buoi khac giu nguyen.
    """
    folder = Path(folder)
    ra = {"baseline": 0, "done": 0, "job": 0, "ban_xuat": 0, "loi": []}

    bp = baseline_path(folder)
    if xoa_moc and bp.is_file():
        try:
            bp.unlink()
            ra["baseline"] = 1
        except OSError as e:
            ra["loi"].append(f"{bp.name}: {e}")

    d = Path(job_dir or LR_JOB_DIR)
    if d.is_dir():
        ten = folder.name
        for mau, khoa in (("apply_*_%s.done", "done"), ("apply_*_%s.tsv", "job")):
            for f in d.glob(mau % ten):
                try:
                    f.unlink()
                    ra[khoa] += 1
                except OSError as e:
                    ra["loi"].append(f"{f.name}: {e}")

        if ca_ban_xuat:
            goc = khoa_duong_dan(folder)
            for f in d.glob("export_*.tsv"):
                if not _phu_thu_muc(_thu_muc_cua_ban_xuat(f), goc, True):
                    continue
                try:
                    f.unlink()
                    ra["ban_xuat"] += 1
                except OSError as e:
                    ra["loi"].append(f"{f.name}: {e}")
            # ket qua lan xuat truoc cua CHINH buoi nay cung la vet cu
            kq = ket_qua_xuat(d)
            if kq.get("thu_muc") and khoa_duong_dan(kq["thu_muc"]) == goc:
                try:
                    (d / KET_QUA_XUAT).unlink()
                except OSError:
                    pass
    return ra


def load_baseline(folder: Path) -> dict[str, dict]:
    return _read_tsv(baseline_path(folder))


def save_baseline(folder: Path, base: dict[str, dict], gop: bool = True,
                  thay: set | None = None) -> Path:
    """Ghi mốc preset gốc. Không có sidecar để cắm marker atn: thì phải lưu ra đây,
    nếu không lần chạy thứ hai sẽ cộng dồn lên kết quả lần đầu.

    GỘP, KHÔNG GHI ĐÈ — và đây là chỗ đã gây hỏng thật, buổi 2705 ngày 7/9.

        Bản cũ dựng lại cả file từ ĐÚNG những ảnh của lần chạy này rồi ghi đè.
        Nên một lượt chạy nhỏ là xoá sạch mốc của mọi ảnh không nằm trong lượt
        đó. Đo trên máy người dùng:

            00:15  chạy 2087 ảnh  -> mốc có 2087 ảnh
            00:18  chạy   57 ảnh  -> mốc CÒN 57 ảnh, 2030 ảnh mất mốc
            11:04  chạy 2087 ảnh  -> 2030 ảnh không còn mốc nên lấy giá trị
                                     catalog HIỆN TẠI (đã được sửa lúc 00:15)
                                     làm mốc, rồi cộng thêm một lần nữa

        Kết quả: 1889/1890 ảnh bị ghi ĐÚNG GẤP ĐÔI mức cần (tỷ lệ trung vị
        2.000). Không có một dòng cảnh báo nào — đúng kiểu hỏng tệ nhất.

    Mốc CŨ luôn thắng: theo định nghĩa nó là giá trị TRƯỚC khi tool chạm vào.
    Ảnh mới thì thêm vào. gop=False chỉ để dùng khi thật sự muốn dựng lại mốc
    từ đầu (ví dụ sau khi khôi phục)."""
    if gop:
        cu = load_baseline(folder)
        if cu:
            moi = dict(base)
            for p, rec in cu.items():   # mốc cũ đè lên, không bao giờ ngược lại
                #  ...TRU anh cua buoi da dat lai (thay): moc moi thay moc cu
                if thay and p in thay and p in base:
                    continue
                #[[ Tru bon cot plugin moi (COT_PLUGIN_MOI) ma moc cu de RONG vi
                #   chot tu plugin cu: bu tu ban ghi moi — xem
                #   attach_catalog_settings. Cot da co so thi moc cu van thang. ]]
                #  isinstance chu khong `if m:` tron — xem bao_mat.bien_dich_mot:
                #  Cython tung dich `if m:` thanh doc kich thuoc dict khi m = None
                m = base.get(p)
                if isinstance(m, dict) and m:
                    bu = bu_cot_plugin_moi(rec, m)
                    if bu:
                        rec = dict(rec, **bu)
                    #  Cot mau (8/10) moc cu de trong: attach_catalog_settings da
                    #  quyet so goc (bu_cot_mau) va dat vao ban ghi moi -> lay theo
                    bu = {k: m[k] for k in (*COT_MAU, *COT_HSL)
                          if str(rec.get(k) if rec.get(k) is not None else "").strip() == ""
                          and str(m.get(k) if m.get(k) is not None else "").strip() != ""}
                    if bu:
                        rec = dict(rec, **bu)
                moi[p] = rec
            base = moi
    #[[ Bon cot cuoi cho quy trinh preset bo trong WB / Tone (3/10): thieu chung
    #   thi lan chay lai khong con nhan ra anh dang o As Shot / Tone 0 (xem
    #   preset_chua_ap) va tinh tren mot nen khac lan dau. Moc cu khong co bon
    #   cot nay -> doc ra la quy trinh cu, dung nhu thuc te. ]]
    cols = ["Exposure2012", "Highlights2012", "Shadows2012",
            "Temperature", "Tint", "AsShotTemperature", "AsShotTint",
            "WhiteBalance", "Contrast2012", "Whites2012", "Blacks2012",
            *COT_MAU, *COT_HSL]
    # Cot path ghi ban Lightroom neu co, khong thi ghi khoa normcase. Ghi de
    # bang khoa normcase se lam mat cach viet hoa/thuong that va lan chay sau
    # gui job voi duong dan Lightroom khong nhan ra.
    rows = [[rec.get(LR_PATH_KEY, p)] + [str(rec.get(c, "")) for c in cols]
            for p, rec in sorted(base.items())]
    dest = baseline_path(folder)
    _write_tsv(dest, cols, rows)
    return dest


#[[ ====== NHAN RA ANH NGUOI DUNG DA SUA TAY, DE KHONG GHI DE LEN ======
#
#   VAN DE THAT, do tren buoi 1308:
#     _autotone_baseline.tsv  Exposure  0.00   moc goc
#     apply_...161838.done    Exposure -0.77   tool ghi luc 16:18
#     export_...205725.tsv    Exposure -0.83   nguoi dung sua tay luc 20:57
#   attach_catalog_settings() luon lay MOC GOC khi anh da co moc, nen chay lai
#   lan hai la tinh ra -0.77 va day de len -0.83. 192/1078 anh cua buoi do roi
#   vao dien nay — tat ca ban sua tay bi vut lang le, khong mot dong canh bao.
#
#   Moc goc co ly do ton tai: tinh tu trang thai hien tai thi chay lai nhieu
#   lan se cong don, cang chay cang troi. Khong bo moc.
#
#   Cach ra: tool BIET no da ghi gi (file apply_*.done). Catalog hien tai khac
#   cai no ghi -> chinh la nguoi da sua. Nhung anh do bo qua han.
#]]
def last_applied(folder: Path, job_dir: Path | None = None) -> dict:
    """Đọc file apply_*.done MỚI NHẤT của thư mục này -> {tên ảnh: Exposure}.

    Khớp theo tên thư mục vì job đặt tên là apply_<mốc thời gian>_<tên thư mục>.
    """
    d = Path(job_dir or LR_JOB_DIR)
    if not d.is_dir():
        return {}
    #[[ 8/10: TEN DA CHUAN HOA nhu luc ghi job (ten_job): "raw 19.4" ->
    #   "raw_19.4". Lay ten tho thi buoi co dau cach / dau tieng Viet khong bao
    #   gio thay job nao -> khong nhan ra anh sua tay, ghi de len lang le. ]]
    ten = ten_job(Path(folder).name)
    #[[ Bo qua job KHOI PHUC — day la cai bay lam mat cong sua tay lan thu hai.
    #
    #   khoi_phuc.py tra lai nhung anh nguoi dung sua tay bi ghi de. Job do BUOC
    #   phai mang tien to apply_ (plugin chi nhan apply_*.tsv) nen ap xong no
    #   thanh mot file .done nam chung thu muc nay.
    #
    #   Neu tinh no la "lan tool ghi gan nhat" thi catalog se TRUNG voi no,
    #   danh_dau_nguoi_sua() thay khong lech gi, va lan chay ke tiep de len dung
    #   nhung anh vua cuu ve. Ten file da tranh mau apply_*_<ten>.done san roi;
    #   cau nay la lop chan thu hai, phong khi quy uoc dat ten thay doi.
    #]]
    fs = [p for p in sorted(d.glob(f"apply_*_{ten}.done"))
          if "khoiphuc" not in p.name.lower()]
    if not fs:
        return {}
    out = {}
    try:
        with io.open(fs[-1], encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                try:
                    out[_stem_any(row["path"])] = float(row["Exposure2012"])
                except (TypeError, ValueError, KeyError):
                    continue
    except OSError:
        return {}
    return out


def ban_xuat_cu_hon_lan_ghi(folder: Path, job_dir: Path | None = None,
                            ban_xuat: Path | None = None):
    """Bản xuất catalog có CŨ HƠN lần tool ghi gần nhất không?

    Trả về (có_cũ_hơn, mốc bản xuất, mốc lần ghi) — hai mốc là datetime, hoặc
    None nếu thiếu file.

    ban_xuat: file bản xuất ĐANG DÙNG cho thư mục này (giao diện biết nó). None
    -> tự tìm bản mới nhất có ảnh của thư mục (ban_xuat_cho_thu_muc).

    #[[ 3/10: PHAI LA BAN XUAT CUA DUNG THU MUC. Truoc lay mtime lon nhat cua
    #   MOI export_*.tsv — dung khi app con doc "file moi nhat". Tu khi app doc
    #   ban xuat THEO THU MUC thi hai ben lech nhau: buoi X dung ban xuat cu
    #   (truoc lan ghi), chi can co mot ban xuat cua buoi Y moi hon lan ghi la
    #   chot nay im — va danh_dau_nguoi_sua lai bo ca buoi X trong im lang, dung
    #   benh 2705 ngay 7/9. Khong biet file nao dang dung thi lay ban phu DUNG
    #   thu muc truoc (cu hon hoac bang ban gom thu muc con): nham ve phia bao
    #   oan thi chi tat buoc loc va noi ra; nham ve phia im thi mat ca buoi.
    #]]

    VÌ SAO PHẢI HỎI CÂU NÀY
        danh_dau_nguoi_sua() đứng trên một giả định: bản xuất phản ánh catalog
        HIỆN TẠI. Nếu Lightroom không chạy (hoặc vòng lặp plugin đã chết) thì
        app không xin được bản xuất mới và dùng lại bản cũ trên đĩa. Bản cũ đó
        chụp catalog TRƯỚC lần ghi gần nhất, nên mọi ảnh mà lần ghi đó đổi đều
        "khác cái tool đã ghi" — và bị coi là người dùng sửa tay.

        Đo thật, buổi 2705 ngày 7/9: bản xuất 11:02, job ghi 11:04. Lần phân
        tích sau đó bỏ qua ĐÚNG 2032 ảnh (đúng bằng số ảnh job 11:04 đổi), chỉ
        còn 55 ảnh — và cả 55 đều ra ΔEV +0.00 nên khâu 3 không có gì để ghi.
        Nhìn từ ngoài thì y hệt "tool hỏng", trong khi thật ra nó đang bảo vệ
        những bản sửa tay không hề tồn tại.
    """
    d = Path(job_dir or LR_JOB_DIR)
    if not d.is_dir():
        return False, None, None
    ten = ten_job(Path(folder).name)          # nhu last_applied: ten da chuan hoa
    ghis = [q for q in sorted(d.glob(f"apply_*_{ten}.done"))
            if "khoiphuc" not in q.name.lower()]
    if not ghis:
        return False, None, None
    xuat = (Path(ban_xuat) if ban_xuat else
            ban_xuat_cho_thu_muc(folder, d)
            or ban_xuat_cho_thu_muc(folder, d, gom_con=True))
    if xuat is None:
        return False, None, None
    try:
        t_xuat = xuat.stat().st_mtime
        t_ghi = max(q.stat().st_mtime for q in ghis)
    except OSError:
        return False, None, None
    return (t_xuat < t_ghi,
            datetime.fromtimestamp(t_xuat), datetime.fromtimestamp(t_ghi))


def buoi_dat_lai(items: list, export: dict, folder: Path,
                 dung_sai: float = 0.005) -> str:
    """Buổi đã được LÀM LẠI trong Lightroom sau lần tool ghi gần nhất chưa?
    -> "" (chưa), "khong-moc" hoặc "dat-lai".

    #[[ 8/10, buoi ky yeu raw 19.4: nguoi dung xoa _autotone_baseline.tsv, ap lai
    #   preset cho ca buoi (WB 5000/+10, Tone 0, xoa sao) roi phan tich lai. Job
    #   cu 09:43 van nam trong thu muc jobs -> danh_dau_nguoi_sua thay 856/1089
    #   anh khac so tool da ghi va bao "bo qua 856 anh anh da sua tay" — trong
    #   khi nguoi dung chua sua anh nao.
    #
    #   Hai dau hieu, cai nao cung la CA BUOI lam lai chu khong phai sua tay:
    #     "khong-moc": thu muc buoi KHONG CON file moc ma van co job cua buoi.
    #       Moi lan ghi deu chot moc vao chinh thu muc do (save_baseline truoc
    #       write_lr_job) — job ma khong co moc tuc la moc da bi xoa: lam lai tu
    #       dau. Cung chan luon truong hop hai buoi khac nhau trung TEN thu muc
    #       (job khop theo ten — job_cua_buoi).
    #     "dat-lai": con moc, nhung >= 50% anh lech so tool ghi VA >= 80% so anh
    #       lech mang CUNG MOT bo (Exposure, Highlights, Shadows) — dau van cua ap
    #       preset / Reset dong loat. Sua tay that le te, moi anh mot so (buoi
    #       1308: 192/1078 anh, so khac nhau) -> van bao ve nhu cu.
    #   Dat lai thi moc cu het dung (preset co the da doi): attach_catalog_settings
    #   (bo_moc=True) lay catalog hien tai lam moc moi. ]]
    """
    da_ghi = last_applied(folder)
    if not da_ghi or not export:
        return ""
    if not baseline_path(folder).is_file():
        return "khong-moc"
    so, lech = 0, []
    for r in items:
        cur = export.get(khoa_duong_dan(r["path"]))
        if not isinstance(cur, dict):
            continue
        truoc = da_ghi.get(_stem_any(r["path"]))
        try:
            gio = float(cur.get("Exposure2012"))
        except (TypeError, ValueError):
            continue
        if truoc is None:
            continue
        so += 1
        if abs(gio - truoc) > dung_sai:
            lech.append(cur)
    if so < 10 or len(lech) * 2 < so:
        return ""
    bo = {}
    for c in lech:
        k = (round(get_f(c, "Exposure2012", 0.0), 2), round(get_f(c, "Highlights2012", 0.0)),
             round(get_f(c, "Shadows2012", 0.0)))
        bo[k] = bo.get(k, 0) + 1
    return "dat-lai" if max(bo.values()) * 5 >= len(lech) * 4 else ""


def danh_dau_nguoi_sua(items: list, export: dict, folder: Path,
                       dung_sai: float = 0.005) -> int:
    """Đánh dấu ảnh có giá trị trong catalog khác cái tool đã ghi lần trước.

    Trả về số ảnh bị đánh dấu. Không sửa gì khác — quyết định bỏ qua nằm ở plan().
    """
    da_ghi = last_applied(folder)
    if not da_ghi or not export:
        return 0
    n = 0
    for r in items:
        key = khoa_duong_dan(r["path"])     # cung khoa voi _read_tsv (xem ham do)
        cur = export.get(key)
        if not cur:
            continue
        try:
            gio = float(cur.get("Exposure2012"))
            truoc = da_ghi.get(_stem_any(r["path"]))
        except (TypeError, ValueError):
            continue
        if truoc is None:
            continue
        if abs(gio - truoc) > dung_sai:
            r["nguoi_sua"] = True
            r["nguoi_sua_ev"] = gio
            n += 1
    return n


def attach_catalog_settings(items: list, export: dict[str, dict], folder: Path,
                            persist: bool = True, bo_moc: bool = False) -> tuple[int, int]:
    """Gắn thông số catalog vào items. Trả về (số ảnh khớp, số ảnh không có trong export).

    Ảnh nào đã có mốc thì dùng mốc; chưa có thì lấy giá trị catalog hiện tại làm mốc.
    bo_moc=True (buổi đã đặt lại — buoi_dat_lai): ảnh có trong bản xuất lấy catalog
    hiện tại làm mốc MỚI, thay mốc cũ (r["moc_moi"], save_baseline(thay=...)).
    """
    base = load_baseline(folder)
    da_grade = anh_da_grade(folder) if not bo_moc else set()
    da_hsl = anh_da_hsl(folder) if not bo_moc else set()
    matched = missing = 0
    for r in items:
        #[[ khoa_duong_dan, KHONG phai normcase: ban xuat va moc deu doc qua
        #   _read_tsv -> khoa_duong_dan. Tren Windows hai cach ra cung mot chuoi;
        #   tren macOS normcase khong viet thuong nen ca buoi khop 0 anh. ]]
        key = khoa_duong_dan(r["path"])
        cur = export.get(key)
        old = base.get(key)
        r["ngoai_xuat"] = False
        r.pop("moc_moi", None)
        if bo_moc and cur:
            old = None                      # moc cu het dung: lay catalog hien tai
            r["moc_moi"] = True
        if old is not None and cur:
            #[[ MOC CHOT TU PLUGIN CU (6/10, buoi BVDay3 1813 anh): plugin 4/9 khong
            #   xuat WhiteBalance / Contrast / Whites / Blacks nen moc co cac cot do
            #   RONG. Cap nhat plugin xong, ban xuat moi co chung — nhung cac cot
            #   khac (Exposure, Highlights...) da mang so tool ghi (-45). Lay
            #   nguyen ban xuat moi lam moc (nhanh moc-cu-khac-quy-trinh duoi) la
            #   CONG DON len -45 va khong con nhan ra preset bo trong Tone.
            #   Bu DUNG cac cot moc dang rong tu ban xuat moi: tool khong bao gio
            #   ghi chung khi chua nhan ra quy trinh moi (nen_tone / nen_wb), tuc
            #   so trong catalog van la so goc. Ghi lai vao moc. Chi bu khi khop
            #   voi chinh moc — xem bu_cot_plugin_moi. ]]
            bu = bu_cot_plugin_moi(old, cur)
            if bu:
                old = dict(old, **bu)
                base[key] = old
            bu = bu_cot_mau(old, cur, key in da_grade)
            if bu:
                old = dict(old, **bu)
                base[key] = old
            bu = bu_cot_hsl(old, cur, key in da_hsl)
            if bu:
                old = dict(old, **bu)
                base[key] = old
        r["da_grade"] = key in da_grade
        r["da_hsl"] = key in da_hsl
        if old is not None:
            #[[ Moc cu la preset DAY DU, catalog lai dang o trang thai preset bo
            #   trong WB/Tone (As Shot, Tone 0) -> anh da duoc import / dat lai
            #   theo quy trinh moi SAU khi moc duoc chot. Moc cu da het dung:
            #   tinh tren no thi tool khong biet phai tu ghi WB va ba thanh Tone,
            #   anh o lai As Shot / Tone 0. Trang thai As Shot / Tone 0 khong bao
            #   gio la so tool ghi ra, nen lay no lam moc khong the cong don.
            #   (Khong ghi de file moc: lan sau catalog da mang so tool ghi, moc cu
            #   lai thang — va so nen cua no trung y nen_tone / nen_wb.) ]]
            if cur and any(preset_chua_ap(cur)) and not any(preset_chua_ap(old)):
                r["crs"] = dict(cur)
                r["notes"] = (r.get("notes", "") + ";moc-cu-khac-quy-trinh").strip(";")
            else:
                r["crs"] = dict(old)
            r["atn"] = {}
            r["rerun"] = True
            matched += 1
        elif cur:
            r["crs"] = dict(cur)
            r["atn"] = {}
            base[key] = dict(cur)          # lần đầu thấy -> chốt làm mốc
            matched += 1
        else:
            #[[ KHONG CO trong ban xuat lan moc -> KHONG duoc day vao Lightroom.
            #   Truoc day anh nay van vao job voi nen 0: Highlights tinh tu 0 thay
            #   vi 16, Exposure tinh tu 0 bat ke catalog dang o dau. Ban xuat cua
            #   buoi khac (3/10: G:\1009 doc nham ban xuat G:\1005) thi ca buoi
            #   bi ghi nhu vay, trong khi giao dien bao "se bi bo qua". Nay dung
            #   nhu loi bao: write_lr_job bo qua (ngoai_xuat). Anh 1 sao bi plugin
            #   bo khi xuat cung roi vao day — dung quy uoc "1 sao khong xu ly". ]]
            r["crs"], r["atn"] = {}, {}
            r["ngoai_xuat"] = True
            r["notes"] = (r.get("notes", "") + ";khong-co-trong-export").strip(";")
            missing += 1

        # Đường dẫn đúng như Lightroom lưu — bản xuất mới nhất đáng tin hơn mốc
        # cũ (ảnh có thể đã được đổi tên/chuyển chỗ rồi import lại). Xem
        # LR_PATH_KEY: đây là thứ giữ cho không ảnh nào bị trượt findPhotoByPath.
        lr = (cur or {}).get(LR_PATH_KEY) or (old or {}).get(LR_PATH_KEY)
        if lr:
            r["lr_path"] = lr
    if persist and base:
        save_baseline(folder, base)
    return matched, missing


def undo(backup_dir: Path, root: Path) -> int:
    n = 0
    for src in backup_dir.rglob("*.xmp"):
        rel = src.relative_to(backup_dir)
        dst = root / rel
        if dst.parent.exists():
            shutil.copy2(src, dst)
            n += 1
    return n


def list_backups(root: Path) -> list[Path]:
    """Các thư mục backup của thư mục ảnh này, mới nhất trước."""
    base = root / "_xmp_backup"
    if not base.is_dir():
        return []
    return sorted((d for d in base.iterdir() if d.is_dir()), reverse=True)


# ======================================================================
# 6. API dùng chung cho CLI và GUI
# ======================================================================

def collect_pairs(root: Path, recursive: bool = False, limit: int = 0,
                  need_sidecar: bool = True):
    """Trả về (danh sách (raw, sidecar), danh sách raw thiếu sidecar).

    need_sidecar=False (chế độ catalog): mọi RAW đều xử lý được, khỏi cần .xmp."""
    it = root.rglob("*") if recursive else root.glob("*")
    #[[ BO FILE "._TEN" — rac cua macOS, khong phai anh.
    #
    #   Chep anh qua USB dinh dang exFAT/NTFS thi macOS de lai canh moi file
    #   mot file "._TEN.ARW" giu resource fork. Chung co DUNG duoi .ARW nen lot
    #   qua bo loc duoi, va thu muc 63 anh bong thanh 126 "anh" — mot nua trong
    #   do do kieu gi cung hong, vi ben trong khong phai RAW.
    #
    #   Nhin tu ngoai: "sao no bao 126 anh ma nua so bi loi?" — va khong ai ngo
    #   toi mot loai file minh khong nhin thay trong Finder.
    #
    #   Tren Windows chuyen nay khong xay ra, nen loi nay chi lo ra khi mang
    #   sang Mac. Khong co anh that nao bat dau bang "._".
    #]]
    raws = sorted(p for p in it if p.is_file() and p.suffix.lower() in RAW_EXTS
                  and "_xmp_backup" not in p.parts
                  and not p.name.startswith("._"))
    if limit:
        raws = raws[:limit]
    pairs, missing = [], []
    for p in raws:
        sc = sidecar_for(p)
        if sc or not need_sidecar:
            pairs.append((p, sc))
        else:
            missing.append(p)
    return pairs, missing


def free_ram_mb() -> float:
    """RAM còn trống (MB). Không đo được thì trả về 0 -> bên gọi tự lo liệu."""
    if sys.platform == "win32":
        import ctypes

        class _MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        try:
            m = _MS()
            m.dwLength = ctypes.sizeof(_MS)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                return m.ullAvailPhys / (1024 * 1024)
        except OSError:
            pass
        return 0.0
    try:
        return os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / (1024 * 1024)
    except (ValueError, AttributeError, OSError):
        return 0.0


def safe_jobs(want: int, cfg: dict | None = None) -> int:
    """Số tiến trình chạy được với lượng RAM còn trống.

    Đo thật trên máy: một tiến trình ổn định ở ~100 MB. Nhưng lúc 8 tiến trình
    CÙNG giải nén JPEG preview thì đỉnh nhất thời cao hơn nhiều, và Windows từ
    chối cấp phát ngay cả khi tổng còn dư — nên tính rộng tay 400 MB/tiến trình.

    Lý do phải đo: Lightroom mở sẵn thường chiếm hơn 10 GB. Cắm cứng 8 tiến
    trình như trước thì máy 32 GB vẫn MemoryError hàng loạt (đã gặp thật: 732
    ảnh bị bỏ qua khi máy chỉ còn ~7 GB trống)."""
    want = max(1, int(want))
    free = free_ram_mb()
    if free <= 0:
        return want                      # không đo được thì giữ nguyên ý người dùng

    per = 400.0
    if cfg:
        # preview/face lớn hơn mặc định thì mỗi tiến trình ăn nhiều hơn
        px = max(int(cfg.get("preview_px", 480)), int(cfg.get("face_px", 1024)))
        per *= max(1.0, (px / 1024.0) ** 2)

    # Chừa 3 GB: Lightroom vừa nhả RAM ra là chiếm lại ngay, mà tiến trình cha
    # còn phải giữ toàn bộ kết quả đo của cả buổi chụp.
    fit = int((free - 3072) // per)
    return max(1, min(want, fit))


def analyze(pairs, cfg: dict, jobs: int = 1, progress=None, cancel=None):
    """Đo toàn bộ ảnh. `progress(done, total)` để cập nhật UI, `cancel()` -> True thì dừng.

    Trả về (items đo được, danh sách lỗi)."""
    do = cau_hinh_do(cfg)
    tasks = [(str(p), *do) for p, _ in pairs]
    total = len(tasks)
    results: list = []

    def tick():
        if progress:
            progress(len(results), total)

    tick()
    if jobs > 1 and total > 1:
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            futures = [ex.submit(_measure_star, t) for t in tasks]
            try:
                for fut in futures:
                    results.append(fut.result())
                    tick()
                    if cancel and cancel():
                        break
            finally:
                for fut in futures:
                    fut.cancel()
    else:
        for t in tasks:
            results.append(_measure_star(t))
            tick()
            if cancel and cancel():
                break

    sidecars = {str(p): sc for p, sc in pairs}
    items, failed = [], []
    for r in results:
        if r.get("ok"):
            r["sidecar"] = str(sidecars[r["path"]])
            r["dt_obj"] = datetime.fromisoformat(r["dt"])
            items.append(r)
        else:
            failed.append(r)

    # Hết RAM là lỗi NHẤT THỜI: chạy lại tuần tự thì hầu như đều qua, vì lúc đó
    # chỉ còn một tiến trình. Không thử lại thì cả buổi chụp mất trắng chỉ vì
    # Lightroom tình cờ đang giữ nhiều RAM (đã gặp: 732/734 ảnh bị bỏ qua).
    oom = [r for r in failed if "MemoryError" in str(r.get("error", ""))]
    if oom and jobs > 1 and not (cancel and cancel()):
        retry = [(Path(r["path"]), sidecars.get(r["path"])) for r in oom]
        again, _ = analyze(retry, cfg, 1, progress=progress, cancel=cancel)
        if again:
            done = {r["path"] for r in again}
            items.extend(again)
            failed = [r for r in failed if r["path"] not in done]

    return items, failed


def cau_hinh_do(cfg: dict) -> tuple:
    """MỌI tham số đi vào measure() (trừ đường dẫn ảnh), đúng thứ tự của nó.

    Một chỗ duy nhất: analyze() dựng việc đo từ đây, và kết quả đo lưu theo
    buổi (luu_ket_qua_do) dùng chính bộ này làm khoá — thêm tham số đo mà quên
    khoá thì nạp nhầm kết quả đo bằng cách cũ."""
    return (cfg["preview_px"], cfg["meter"], cfg["meter_highlight_cut"],
            cfg["wb"] == "skin", cfg["face_px"], cfg["face_score"],
            cfg["focus_quantile"], cfg["focus_face_gain"],
            cfg.get("face_min_ratio", 0.25),
            cfg.get("subject_keep", 0.60),
            cfg.get("subject_dark_ev", 2.0),
            cfg.get("face_min_score_sub", 0.0),
            cfg.get("big_low_ratio", 0.0),
            cfg.get("big_low_gap", 0.13),
            cfg.get("big_low_floor", 0.70),
            # Chi do mat khi nguoi dung tick loc mat — do khong khi thi phi
            # mot lan giai nen 3000px cho moi anh.
            bool(cfg.get("blink")),
            # Do theo vung da sang khi vung do du lon — xem hl_da_ti_le.
            float(cfg.get("hl_da_ti_le", 0.0)),
            float(cfg.get("hl_da_muc", 220.0)),
            float(cfg.get("af_gan_mat", 0.0)),
            bool(cfg.get("af_xoay_theo_anh", True)),
            bool(cfg.get("af_nikon", False)),
            float(cfg.get("mat_ao_to_pct", 0.0)),
            float(cfg.get("mat_ao_diem", 0.6)))


#[[ KET QUA PHAN TICH LUU THEO BUOI (8/10).
#
#   User: "khi 1 buoi da duoc phan tich can luu lai thong so da phan tich va
#   hien thi neu mo lai dung folder do". Truoc day ket qua do chi nam trong RAM
#   — dong app / mo buoi khac roi quay lai la "chua phan tich", phai do lai
#   1813 anh.
#
#   Chi luu ket qua DO (measure), khong luu ke hoach: ke hoach phu thuoc ban
#   xuat catalog, baseline, gu.json... nen nap xong van tinh lai nhu vua phan
#   tich. Nap CHI KHI chac chan giong het lan do:
#     - cung ban engine (dau file autotone — doi ban app la doi cach do, nap
#       ket qua do bang code cu se lam lech am tham, loai loi kho tim nhat);
#     - cung tham so do (cau_hinh_do);
#     - MOI anh RAW hien co trong thu muc deu co trong lan do, cung kich thuoc
#       va gio sua. Anh bi xoa bot thi van nap (do tung anh doc lap); them anh
#       moi thi khong. ]]
THU_MUC_KET_QUA_DO = "phan_tich"
GIU_KET_QUA_DO = 40                  # so buoi giu lai, buoi cu nhat bi xoa truoc
_DAU_ENGINE: list = []


def dau_engine() -> str:
    """Dấu của chính file engine đang chạy (.py hay .pyd đã mã hoá). Đổi bản = đổi dấu."""
    if not _DAU_ENGINE:
        import hashlib
        try:
            h = hashlib.sha1(Path(__file__).read_bytes()).hexdigest()[:16]
        except OSError:
            h = f"khong-doc-duoc-{os.getpid()}-{time.time()}"     # khong bao gio khop
        _DAU_ENGINE.append(h)
    return _DAU_ENGINE[0]


def file_ket_qua_do(thu_muc) -> Path:
    import hashlib
    goc = os.path.normcase(os.path.normpath(str(thu_muc)))
    h = hashlib.sha1(goc.encode("utf-8", "surrogatepass")).hexdigest()[:10]
    return dd.goc_du_lieu() / THU_MUC_KET_QUA_DO / f"{ten_job(Path(thu_muc).name)}_{h}.pkl"


def _chu_ky_anh(path) -> tuple:
    try:
        st = os.stat(path)
        return (int(st.st_size), int(st.st_mtime_ns))
    except OSError:
        return (-1, -1)


def luu_ket_qua_do(thu_muc, cfg: dict, pairs, items: list, failed: list) -> Path | None:
    """Ghi kết quả đo của buổi (gọi NGAY sau analyze(), trước khi plan() đụng vào
    items). Hỏng thì trả None — không lưu được không phải lý do làm hỏng lượt đo."""
    import pickle
    import zlib
    f = file_ket_qua_do(thu_muc)
    goi = {"dang": 1, "engine": dau_engine(), "thu_muc": str(thu_muc),
           "cau_hinh": cau_hinh_do(cfg),
           "anh": {str(p): _chu_ky_anh(p) for p, _ in pairs},
           "items": items, "failed": list(failed or []), "luc": time.time()}
    try:
        du_lieu = zlib.compress(pickle.dumps(goi, protocol=4), 3)
        f.parent.mkdir(parents=True, exist_ok=True)
        tam = f.with_name(f.name + ".tmp")
        tam.write_bytes(du_lieu)
        os.replace(tam, f)
    except Exception:                                        # noqa: BLE001
        return None
    try:
        #  file vua ghi luon giu (dong ho may lech thi mtime khong dang tin)
        cu = sorted((x for x in f.parent.glob("*.pkl") if x != f),
                    key=lambda x: x.stat().st_mtime, reverse=True)
        for x in cu[max(0, GIU_KET_QUA_DO - 1):]:
            x.unlink()
    except OSError:
        pass
    return f


def nap_ket_qua_do(thu_muc, cfg: dict, pairs) -> tuple:
    """-> (kết quả, lý do). Kết quả là dict {items, failed, luc, n_bo} khi KHỚP
    hoàn toàn với lần đo đã lưu, None nếu không — lúc đó `lý do` nói vì sao
    (chuỗi rỗng = buổi này chưa từng phân tích)."""
    import pickle
    import zlib
    f = file_ket_qua_do(thu_muc)
    if not f.is_file():
        return None, ""
    try:
        goi = pickle.loads(zlib.decompress(f.read_bytes()))
    except Exception:                                        # noqa: BLE001
        return None, "file kết quả cũ hỏng"
    if not isinstance(goi, dict) or goi.get("dang") != 1:
        return None, "kết quả cũ là định dạng khác"
    if goi.get("engine") != dau_engine():
        return None, "kết quả cũ đo bằng bản app khác"
    if tuple(goi.get("cau_hinh") or ()) != cau_hinh_do(cfg):
        return None, "cách đo đã đổi so với lần trước"
    anh = goi.get("anh") or {}
    moi = doi = 0
    for p, _ in pairs:
        ck = anh.get(str(p))
        if ck is None:
            moi += 1
        elif tuple(ck) != _chu_ky_anh(p):
            doi += 1
    if moi or doi:
        return None, ", ".join(x for x in (f"{moi} ảnh mới" if moi else "",
                                           f"{doi} ảnh đã đổi" if doi else "") if x)
    co = {str(p): str(sc) for p, sc in pairs}
    items = []
    for it in goi.get("items") or []:
        sc = co.get(str(it.get("path")))
        if sc is not None:
            it["sidecar"] = sc               # che do nguon doi thi duong .xmp theo lan nay
            items.append(it)
    failed = [r for r in goi.get("failed") or [] if str(r.get("path")) in co]
    return {"items": items, "failed": failed, "luc": float(goi.get("luc") or 0),
            "n_bo": len(goi.get("items") or []) - len(items)}, ""


def plan(items: list, cfg: dict, folder: Path | None = None,
         export: dict | None = None, ban_xuat: Path | None = None) -> None:
    """Gom cảnh, nạp thông số nguồn, tính delta và điền giá trị dự kiến (không ghi file).

    ban_xuat: file mà `export` đọc ra (nguồn catalog) — để chốt "bản xuất cũ
    hơn lần ghi" so đúng file đó. None -> tự tìm theo thư mục."""
    # Hai bộ lọc ĐỘC LẬP, chạy nối tiếp: trùng khung trước, nhắm mắt sau.
    # Bật/tắt riêng, ngưỡng riêng, nhãn riêng. Ảnh đã bị loại ở bước trước thì
    # bước sau bỏ qua, nên mỗi ảnh chỉ mang đúng MỘT lý do loại.
    if cfg.get("burst"):
        group_bursts(items, float(cfg["burst_gap_sec"]),
                     float(cfg["burst_pose_thresh"]), int(cfg["burst_min"]))
        pick_burst(items, int(cfg["burst_keep"]), int(cfg["burst_reject_rating"]),
                   float(cfg.get("burst_eye_weight", 0.6)))
    if cfg.get("blink"):
        pick_blinks(items, cfg, folder)
    #[[ Gan nhan trong/ngoai TRUOC khi tach canh — group_scenes() doc no de
    #   khong bao gio de hai moi truong anh sang vao chung mot canh.
    #]]
    for r in items:
        r["ngoai_troi"] = ngoai_troi(r, cfg)
    lam_min_trong_ngoai(items, int(cfg.get("trong_ngoai_min_shots", 1)))
    group_scenes(items, cfg["gap_minutes"],
                 float(cfg.get("scene_sig_thresh", 0.0)),
                 int(cfg.get("scene_sig_min_shots", 3)),
                 bool(cfg.get("scene_gap_can_sig", True)))

    # decide() cần AsShotTemperature ở mức cả cảnh nên phải nạp thông số trước
    if cfg.get("source") == "catalog":
        global SO_ANH_NGUOI_SUA, CANH_BAO_XUAT, CANH_BAO_PLUGIN, DAT_LAI_BUOI
        #  Hai phep kiem nay doc ban xuat + job, KHONG doc moc — phai chay TRUOC
        #  attach_catalog_settings: buoi da dat lai thi mot thu moc moi.
        cu, t_xuat, t_ghi = ban_xuat_cu_hon_lan_ghi(Path(folder or "."),
                                                    ban_xuat=ban_xuat)
        DAT_LAI_BUOI = "" if cu else buoi_dat_lai(items, export or {}, Path(folder or "."))
        attach_catalog_settings(items, export or {}, Path(folder or "."), persist=False,
                                bo_moc=DAT_LAI_BUOI == "dat-lai")
        #[[ As Shot cua tung anh — TRUOC khi bo anh nguoi sua: anh user da mo
        #   trong Develop chinh la anh Lightroom da dung, tuc anh co As Shot
        #   THAT de hoc do lech thang K. Bo chung truoc thi mat gan het cap. ]]
        uoc_asshot(items, cfg)
        #[[ BO QUA anh nguoi dung da sua tay — xem chu thich o danh_dau_nguoi_sua().
        #   Dat NGAY SAU khi nap thong so va TRUOC decide(), de nhung anh do
        #   khong di qua bat ky buoc tinh nao: khong can sang, khong san phang
        #   canh, khong loc. Chung phai ra khoi duong ong hoan toan.
        #]]
        CANH_BAO_XUAT = ""
        CANH_BAO_PLUGIN = canh_bao_plugin_cu(export or {}, cfg)
        if CANH_BAO_PLUGIN:
            print("[!] " + CANH_BAO_PLUGIN, file=sys.stderr)
        if cu:
            #[[ BAN XUAT CU HON LAN GHI -> KHONG duoc chay danh_dau_nguoi_sua.
            #   Gia dinh cua no da hong (xem ban_xuat_cu_hon_lan_ghi). Chay tiep
            #   thi no bo qua gan het buoi chup mot cach lang le. Tha khong loc
            #   gi con hon loc sai — va phai NOI RA.
            #]]
            SO_ANH_NGUOI_SUA = 0
            CANH_BAO_XUAT = (
                f"Ban xuat catalog ({t_xuat:%H:%M %d/%m}) CU HON lan tool ghi "
                f"({t_ghi:%H:%M %d/%m}) — Lightroom chua tra ve ban moi. "
                "Da bo qua buoc loc anh sua tay de khong bo nham ca buoi. "
                "Mo Lightroom, nap lai plugin roi phan tich lai.")
            print("[!] " + CANH_BAO_XUAT, file=sys.stderr)
        elif DAT_LAI_BUOI:
            #  Buoi da lam lai sau lan ghi truoc -> job cu khong con noi duoc anh
            #  nao "nguoi dung sua tay". Xem buoi_dat_lai().
            SO_ANH_NGUOI_SUA = 0
            print(f"[i] Buoi da dat lai sau lan ghi truoc ({DAT_LAI_BUOI}) — tinh lai tu "
                  "trang thai catalog hien tai, khong loc anh sua tay.", file=sys.stderr)
        elif cfg.get("bo_qua_nguoi_sua", True):
            n = danh_dau_nguoi_sua(items, export or {}, Path(folder or "."))
            SO_ANH_NGUOI_SUA = n
            if n:
                items[:] = [r for r in items if not r.get("nguoi_sua")]
                print(f"[i] Bo qua {n} anh anh da sua tay — khong ghi de len chung.",
                      file=sys.stderr)
    else:
        for r in items:
            try:
                txt = Path(r["sidecar"]).read_bytes().decode("utf-8")
                r["crs"], r["atn"] = read_crs(txt), read_ns(txt, ATN_PREFIX)
            except (OSError, TypeError, UnicodeDecodeError) as ex:
                r["crs"], r["atn"] = {}, {}
                r["notes"] = f"khong-doc-duoc-sidecar:{ex}"
            #  Tool da tung ghi Color Grading: so trong .xmp khac moc goc atn:
            r["da_grade"] = any(
                ATN_FIELDS[k] in r["atn"]
                and get_f(r["atn"], ATN_FIELDS[k], 0.0) != get_f(r["crs"], k, 0.0)
                for k in COT_GRADE)
        #[[ KHONG uoc_asshot o duong sidecar: ghi xong thi .xmp mang WB Custom
        #   cua tool, moc atn chi giu nen 5250 — lan chay lai mat As Shot, ra so
        #   khac lan dau (4716 -> 5250). Duong catalog giu As Shot trong moc. ]]

    decide(items, cfg)
    for r in items:
        try:
            if cfg.get("source") == "catalog":
                compute_values(r, cfg, r["crs"], r["atn"])
            else:
                apply_to_sidecar(r, cfg, None, Path("."), dry=True)
        except Exception as ex:
            r["notes"] = (r.get("notes", "") + f";LOI:{ex}").strip(";")
    #[[ MAU DA can WB CUOI (new_temp / new_tint) -> SAU compute_values. Chuoi: do
    #   -> HSL kenh da -> do lai -> Color Grading (chinh_mau_da). Hong thi khong
    #   ghi HSL / grade anh nao (va noi ra), khong duoc lam do ca buoi. ]]
    global HSL_DA, MAU_DA
    try:
        chinh_mau_da(items, cfg)
    except Exception as ex:                                  # noqa: BLE001
        HSL_DA, MAU_DA = {}, {}
        for r in items:
            r.pop("gr_ghi", None)
            r.pop("hsl_ghi", None)
        print(f"[!] Chinh mau da (HSL / Color Grading) loi, bo qua: {ex}", file=sys.stderr)


def write_sidecars(items: list, cfg: dict, root: Path, backup_dir: Path | None = None,
                   progress=None) -> Path:
    """Ghi thật vào .xmp sau khi đã backup. Trả về thư mục backup.

    progress(da_xong, tong): gọi sau mỗi ảnh, để bên gọi vẽ thanh tiến độ.
    Ghi 1000 file .xmp mất hàng chục giây; không có nó thì giao diện đứng im
    và người dùng không biết là đang chạy hay đã treo.
    """
    if cfg.get("source") == "catalog":
        # Không có sidecar để ghi: chốt mốc rồi đẩy thẳng job sang Lightroom.
        base = {khoa_duong_dan(r["path"]): r["crs"]
                for r in items if r.get("crs")}
        if base:
            save_baseline(root, base, thay={khoa_duong_dan(r["path"]) for r in items
                                            if r.get("moc_moi") and r.get("crs")})
        write_lr_job(items, root.name)
        return baseline_path(root)

    backup_dir = Path(backup_dir or (root / "_xmp_backup" /
                                     datetime.now().strftime("%Y%m%d_%H%M%S"))).resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)
    tong = len(items)
    for i, r in enumerate(items, 1):
        try:
            apply_to_sidecar(r, cfg, backup_dir, root, dry=False)
        except Exception as ex:
            r["notes"] = (r.get("notes", "") + f";LOI:{ex}").strip(";")
        if progress is not None:
            progress(i, tong)
    if cfg.get("lr_push"):
        try:
            write_lr_job(items, root.name)
        except OSError as ex:
            print(f"[!] khong ghi duoc job cho Lightroom: {ex}", file=sys.stderr)
    return backup_dir


#[[ Cot phuc vu luat loc anh nham mat / mo:
#   faces_n        so nguoi do duoc  -> quyet dinh anh ca nhan hay anh tap the
#   eye_open_min   nguoi nham mat nhat trong khung
#   eyes_measured  do duoc mat cua bao nhieu nguoi (thap = khong dang tin)
#   face_area_min  mat nho nhat, tinh theo % khung -> mat qua nho thi do nhu doan
#   face_score_min diem tin cay thap nhat cua YuNet
#]]
#   cull           LY DO loai, do dau ra: "loat" = trung khung, "nham-mat" =
#                  nham mat, rong = khong bi loai. Co cot nay de sau nay khong
#                  con nhap nhan cua hai bo loc lam mot (da tung: 377 anh 1 sao
#                  buoi 1308 la do loc trung khung, khong phai nham mat).
REPORT_EXTRA = ["faces_n", "faces_found", "eye_open", "eye_open_min",
                "eye_min_area", "eye_min_score", "ear_min", "ear_faces",
                "eyes_measured", "face_sharp", "face_sharp_min",
                "face_area_min", "face_score_min", "cull"]

REPORT_COLS = ["path", "sidecar", "dt", "scene", "scene_size", "iso", "ngoai_troi",
               "model", "metered_ev",
               "target_ev", "delta_ev", "old_exposure", "new_exposure",
               "clip_before_pct", "clip_after_pct", "shadow_after_pct",
               "hl_adj", "old_highlights", "new_highlights",
               "sh_adj", "old_shadows", "new_shadows",
               "temp_adj", "old_temp", "new_temp", "tint_adj", "old_tint", "new_tint",
               #[[ Hai cot moi, de TRUY duoc viec gom canh tu chinh bao cao:
               #   scene_cut       vi sao anh nay mo mot canh moi: "gio" hay
               #                   "boi-canh" (rong = khong phai anh dau canh)
               #   scene_sig_lech  do lech chu ky so voi canh dang mo, do TRUOC
               #                   khi cat. Co no thi tra loi duoc "nhat cat
               #                   theo gio nay co duoc boi canh dong y khong"
               #                   ma khong phai chay lai gi.
               #]]
               "scene_cut", "scene_sig_lech",
               *REPORT_EXTRA, "notes"]


def unprocessed_count(pairs) -> int:
    """Số sidecar chưa từng chạy autotone (chưa có marker atn:)."""
    n = 0
    for _raw, sc in pairs:
        try:
            if f"{ATN_PREFIX}:{ATN_FIELDS['Exposure2012']}" not in \
                    sc.read_bytes()[:16384].decode("utf-8", "ignore"):
                n += 1
        except OSError:
            n += 1
    return n


def process_folder(folder: Path, cfg: dict, jobs: int = 1, recursive: bool = False,
                   log=print, write: bool = True) -> dict:
    """Chạy trọn một thư mục. Trả về tóm tắt để ghi log / hiện lên UI."""
    pairs, missing = collect_pairs(folder, recursive)
    out = {"folder": str(folder), "pairs": len(pairs), "missing": len(missing),
           "written": 0, "failed": 0, "scenes": 0, "backup": None, "changed": 0}
    if not pairs:
        return out

    items, failed = analyze(pairs, cfg, jobs)
    out["failed"] = len(failed)
    for f in failed:
        log(f"    lỗi: {Path(f['path']).name}: {f['error']}")
    if not items:
        return out

    plan(items, cfg)
    out["scenes"] = len({r["scene"] for r in items})
    out["changed"] = sum(1 for r in items if r["delta_ev"] or r["hl_adj"] or r["sh_adj"])
    if write:
        out["backup"] = str(write_sidecars(items, cfg, folder))
        out["written"] = len(items)
    return out


# ---------------------------------------------------------------- worker theo dõi

class Watcher:
    """Theo dõi thư mục, tự xử lý khi buổi chụp đã import xong.

    Không xử lý ngay lúc ảnh vừa xuất hiện: cân theo cảnh cần thấy đủ ảnh của cảnh
    đó, mà Lightroom thì ghi sidecar dần dần. Nên chỉ chạy khi thư mục đã "yên"
    (không file nào thêm/đổi) suốt `settle` giây.

    Trạng thái đã-xử-lý-hay-chưa đọc thẳng từ marker atn: trong sidecar, nên tắt
    máy bật lại vẫn đúng, không cần file trạng thái riêng.
    """

    def __init__(self, root: Path, cfg: dict, *, recursive: bool = False,
                 subfolders: bool = False, interval: float = 20.0,
                 settle: float = 120.0, jobs: int = 1, log=print, write: bool = True):
        self.root = Path(root)
        self.cfg = cfg
        self.recursive = recursive
        self.subfolders = subfolders
        self.interval = max(2.0, float(interval))
        self.settle = max(0.0, float(settle))
        self.jobs = jobs
        self.log = log
        self.write = write
        self.state: dict[str, dict] = {}   # folder -> {sig, since, done}

    def jobs_list(self) -> list[Path]:
        if not self.subfolders:
            return [self.root] if self.root.is_dir() else []
        if not self.root.is_dir():
            return []
        return sorted(d for d in self.root.iterdir()
                      if d.is_dir() and d.name != "_xmp_backup")

    @staticmethod
    def signature(folder: Path, recursive: bool):
        """Dấu vân tay của thư mục — đổi nghĩa là còn đang import/ghi."""
        it = folder.rglob("*") if recursive else folder.glob("*")
        sig = []
        for p in it:
            if "_xmp_backup" in p.parts:
                continue
            sfx = p.suffix.lower()
            if sfx in RAW_EXTS or sfx == ".xmp":
                try:
                    st = p.stat()
                    sig.append((str(p), int(st.st_mtime), st.st_size))
                except OSError:
                    pass
        return tuple(sorted(sig))

    def tick(self, now: float) -> list[dict]:
        """Một nhịp kiểm tra. Trả về danh sách tóm tắt của thư mục vừa xử lý."""
        done = []
        for folder in self.jobs_list():
            key = str(folder)
            sig = self.signature(folder, self.recursive)
            st = self.state.setdefault(key, {"sig": None, "since": now, "done": None})

            if sig != st["sig"]:
                st["sig"], st["since"] = sig, now
                continue                      # còn đang thay đổi, chờ tiếp
            if not sig or sig == st["done"]:
                continue                      # rỗng, hoặc đã xử lý đúng bộ này rồi
            if now - st["since"] < self.settle:
                continue                      # chưa đủ yên

            pairs, missing = collect_pairs(folder, self.recursive)
            todo = unprocessed_count(pairs)
            if not todo:
                st["done"] = sig
                if missing:
                    self.log(f"[{folder.name}] {missing and len(missing)} ảnh chưa có "
                             f".xmp — bỏ qua (Lightroom: Ctrl+A rồi Ctrl+S)")
                continue

            self.log(f"[{folder.name}] bắt đầu — {len(pairs)} ảnh, {todo} ảnh chưa xử lý"
                     + (f", {len(missing)} ảnh thiếu .xmp sẽ bỏ qua" if missing else ""))
            try:
                res = process_folder(folder, self.cfg, self.jobs, self.recursive,
                                     log=self.log, write=self.write)
            except Exception as ex:
                self.log(f"[{folder.name}] LỖI: {type(ex).__name__}: {ex}")
                st["since"] = now             # thử lại sau
                continue

            st["done"] = self.signature(folder, self.recursive)
            st["sig"] = st["done"]
            self.log(f"[{folder.name}] xong — {res['written']} sidecar, "
                     f"{res['scenes']} cảnh, {res['changed']} ảnh có thay đổi"
                     + (f", backup: {Path(res['backup']).name}" if res["backup"] else ""))
            res["name"] = folder.name
            done.append(res)
        return done

    def loop(self, should_stop=None):
        import time as _time
        self.log(f"Đang theo dõi: {self.root}"
                 + ("  (mỗi thư mục con là một buổi chụp)" if self.subfolders else "")
                 + f"\nKiểm tra mỗi {self.interval:.0f}s, chờ yên {self.settle:.0f}s "
                 f"rồi mới xử lý." + ("" if self.write else "  [CHẠY THỬ — không ghi]"))
        while not (should_stop and should_stop()):
            try:
                self.tick(_time.monotonic())
            except Exception as ex:
                self.log(f"LỖI vòng lặp: {type(ex).__name__}: {ex}")
            slept = 0.0
            while slept < self.interval and not (should_stop and should_stop()):
                _time.sleep(0.25)
                slept += 0.25
        self.log("Đã dừng theo dõi.")


# ---------------------------------------------------- cầu nối sang Lightroom

# Plugin Lightroom đọc job từ đây rồi áp thẳng vào catalog, khỏi phải bấm
# Metadata > Read Metadata from File. Định dạng TSV cho đơn giản — Lua không có
# sẵn bộ đọc JSON, mà TSV thì parse bằng string.gmatch là xong.
# Đặt ngay trong bundle plugin: phía Lua lấy _PLUGIN.path nên hai bên luôn chỉ về
# cùng một chỗ, không phụ thuộc cách Lightroom hiểu các thư mục hệ thống.
LR_PLUGIN_DIR = dd.plugin()
LR_JOB_DIR = LR_PLUGIN_DIR / "jobs"
LR_JOB_FIELDS = ["Exposure2012", "Highlights2012", "Shadows2012", "Temperature", "Tint",
                 # Parametric curve: plugin ghi bang s[key] = val nen chi can la
                 # SO — khong phai sua mot dong Lua nao.
                 "ParametricHighlights", "ParametricLights",
                 "ParametricDarks", "ParametricShadows",
                 #[[ Color Grading — so nguyen, plugin ghi bang s[key] = val.
                 #   8/10: BO "ColorGradeShadowHue/Sat" — Lightroom KHONG CO hai
                 #   khoa do (bong la SplitToningShadowHue / Saturation): ghi vao
                 #   khong an, va buoc kiem chung bao 1083/1089 anh "CHUA nhan"
                 #   (buoi raw 19.4). Bo ca ColorGradeMidtoneLum (tool khong chinh).
                 #   Banh xe highlight nam CUOI danh sach. ]]
                 "ColorGradeMidtoneHue", "ColorGradeMidtoneSat",
                 # Rating di duong rieng trong plugin (setRawMetadata), khong
                 # phai develop setting — xem AutoToneCore.lua
                 "Rating",
                 # Upright: 1 = Auto. Lightroom tu tinh perspective khi mo anh,
                 # SDK khong co API tinh san.
                 "PerspectiveUpright",
                 # 3/10: chi co so khi preset bo trong nhom Basic Tone (xem
                 # nen_cho_anh); o trong = plugin khong dung toi. Dat CUOI de
                 # moi cho doc job theo vi tri cot (neu con) khong lech.
                 "Contrast2012", "Whites2012", "Blacks2012",
                 #[[ 8/10: anh den trang — "1" = giu Black & White (plugin doc
                 #   thanh true), o trong = khong dung toi. Dat CUOI: plugin cu
                 #   doc theo ten cot. ]]
                 "ConvertToGrayscale",
                 # 8/10: banh xe highlight (grade_theo_trang_thai cong vecto vao)
                 "SplitToningHighlightHue", "SplitToningHighlightSaturation",
                 # 8/10 vong 5: HSL kenh da (hsl_da_theo_trang_thai) — o trong =
                 # khong dung toi; plugin doc theo TEN cot nen khong sua Lua
                 *COT_HSL]

# File job vừa ghi gần nhất — giao diện theo dõi nó tới khi plugin đổi đuôi .done
LAST_JOB: Path | None = None


def job_state(job: Path | None) -> str:
    """Job đang ở đâu: "cho", "dang" (plugin đang áp), "xong", hay "mat".

    Plugin đổi tên file theo từng chặng, nên chỉ cần nhìn tên là biết:
        apply_x.tsv          -> đang xếp hàng
        apply_x.tsv.running  -> plugin đã giành được và đang áp
        apply_x.done         -> áp xong
    """
    if job is None:
        return "mat"
    p = Path(job)
    if p.with_suffix(".done").exists():
        return "xong"
    #[[ 8/10: plugin gianh job bang ten DUY NHAT `<job>.<id>-<gio>-<so>.running`
    #   (AutoToneCore M.claim) — ban truoc chi do `<job>.running` nen khong bao
    #   gio thay "dang", job dang ap bi bao la "mat". ]]
    if p.with_suffix(p.suffix + ".running").exists() or any(p.parent.glob(p.name + ".*.running")):
        return "dang"
    if p.exists():
        return "cho"
    if p.with_suffix(".huy").exists():
        return "huy"
    return "mat"


def huy_job(job: Path | None) -> str:
    """Huỷ một job Lightroom CHƯA nhận: đổi `apply_x.tsv` -> `apply_x.huy` (plugin chỉ
    quét `apply_*.tsv`). Trả về "da-huy", "da-nhan" (plugin đã giành / đang áp / đã áp
    — không ngắt giữa chừng được), hoặc "khong-co".

    #[[ An toan voi plugin: plugin gianh job bang LrFileUtils.move(.tsv -> .running)
    #   roi kiem file CUA NO. Ta doi ten truoc thi lenh move cua plugin truot, no bo
    #   qua; plugin doi truoc thi os.replace cua ta bao FileNotFoundError -> "da-nhan".
    #   Khong bao gio ca hai cung "thang". ]]"""
    if job is None:
        return "khong-co"
    p = Path(job)
    st = job_state(p)
    if st in ("dang", "xong"):
        return "da-nhan"
    if st != "cho":
        return "da-huy" if st == "huy" else "khong-co"
    try:
        os.replace(p, p.with_suffix(".huy"))
        return "da-huy"
    except FileNotFoundError:
        return "da-nhan" if job_state(p) in ("dang", "xong") else "khong-co"
    except OSError:
        return "da-nhan"


def job_dang_cho(thu_muc=None, job_dir: Path | None = None) -> list:
    """Các job `apply_*.tsv` CHƯA được Lightroom nhận (của buổi `thu_muc`, None = mọi buổi)."""
    d = Path(job_dir or LR_JOB_DIR)
    if not d.is_dir():
        return []
    return [p for p in sorted(d.glob("apply_*.tsv")) if job_cua_buoi(p, thu_muc)]


def job_unverified(job: Path | None) -> list[tuple[str, str]]:
    """Ảnh plugin đọc lại mà thấy CHƯA nhận đúng thông số, cho đúng job này.

    Plugin chỉ ghi file verify_*.tsv khi có vấn đề, nên không có file nghĩa là
    mọi ảnh tìm thấy trong catalog đều đã đúng."""
    if job is None:
        return []
    name = Path(job).name
    for pre in ("apply_", ""):
        if name.startswith(pre) and pre:
            name = name[len(pre):]
            break
    stem = name[:-4] if name.endswith(".tsv") else name
    vf = LR_JOB_DIR / f"verify_{stem}.tsv"
    try:
        lines = vf.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    out = []
    for ln in lines[1:]:
        if not ln:
            continue
        v = ln.split("\t")
        out.append((v[0], v[1] if len(v) > 1 else ""))
    return out


def request_export(folder: Path, job_dir: Path | None = None,
                   skip_rating: int | None = None) -> Path:
    """Nhờ plugin xuất thông số của một thư mục, khỏi phải vào Lightroom bấm menu.

    Ghi ra jobs/request_export.txt; vòng lặp nền của plugin dò mỗi 5 giây, thấy
    thì tự chạy rồi xoá file này. Cùng cơ chế với job áp, chỉ ngược chiều.

    Plugin lấy ảnh theo THƯ MỤC chứ không theo vùng chọn trong Lightroom —
    chạy từ nền thì không có vùng chọn nào đáng tin.
    """
    d = Path(job_dir or LR_JOB_DIR)
    d.mkdir(parents=True, exist_ok=True)
    dest = d / "request_export.txt"
    tmp = d / "request_export.part"
    body = [str(Path(folder).resolve())]
    #[[ Bỏ ảnh đã bị loại. Người dùng gán 1 sao cho ảnh không xử lý, và chính
    #   pick_burst của autotone cũng gán 1 sao cho ảnh trùng khung
    #   (burst_reject_rating). Xuất cả chúng thì vừa chậm vừa làm loãng dữ
    #   liệu học gu — ảnh đã loại thì không ai sửa, nên bộ thu thập sẽ đếm
    #   chúng là "tool làm đúng" dù chưa ai nhìn tới.
    #]]
    if skip_rating is None:
        skip_rating = DEFAULTS.get("export_skip_rating")
    if skip_rating:
        body.append(f"skip_rating={int(skip_rating)}")
    tmp.write_text("\n".join(body) + "\n", encoding="utf-8")
    os.replace(tmp, dest)          # doi ten: plugin khong doc phai file dang ghi
    return dest


def export_request_pending(job_dir: Path | None = None) -> bool:
    """File yêu cầu còn nằm đó = plugin CHƯA nhận.

    Phân biệt được hai kiểu hỏng khác hẳn nhau:
      còn file  -> plugin không chạy, hoặc đang chạy bản cũ chưa có hàm này
      mất file  -> plugin đã nhận nhưng phần xuất hỏng, phải xem plugin.log
    """
    d = Path(job_dir or LR_JOB_DIR)
    return (d / "request_export.txt").exists()


def export_stamp(job_dir: Path | None = None, thu_muc=None) -> float:
    """Thời điểm của bản xuất mới nhất. Dùng để biết plugin đã trả lời chưa.

    thu_muc: chỉ tính bản xuất CÓ ẢNH của thư mục đó — một bản xuất của buổi
    khác (người dùng bấm menu xuất bên Lightroom) không được tính là "đã trả lời"."""
    p = (ban_xuat_cho_thu_muc(thu_muc, job_dir) if thu_muc
         else latest_catalog_export(job_dir))
    try:
        return p.stat().st_mtime if p else 0.0
    except OSError:
        return 0.0


#[[ NHIP CUA VONG LAP PLUGIN (3/10) — jobs/plugin_song.txt, plugin ghi ~10 giay
#   mot lan khi vong lap con song (Core.ghiNhip, goi tu Init.lua).
#
#   Gap that 3/10 08:25 -> 09:04: vong lap trong Lightroom KHONG chay (khong
#   mot dong nhat ky nao suot 39 phut), app ghi yeu cau xuat luc 09:02:51 roi
#   cho mai "dang nho Lightroom doc thu muc". User Reload plugin luc 09:04:49 ->
#   09:04:50 da xuat xong 326 anh: duong nho xuat chi mat 1 giay KHI vong lap
#   song. plugin.log khong noi duoc vong lap con song khong (no chi ghi khi co
#   viec). Co nhip thi app noi ngay "plugin khong chay — Reload", khong de user
#   ngoi cho roi tu vao menu xuat tay.
#]]
NHIP_PLUGIN = "plugin_song.txt"


def plugin_nhip(job_dir: Path | None = None) -> float | None:
    """Giây kể từ nhịp cuối của vòng lặp plugin. None = chưa từng có nhịp (plugin
    bản cũ chưa ghi nhịp, hoặc chưa bao giờ chạy)."""
    f = Path(job_dir or LR_JOB_DIR) / NHIP_PLUGIN
    try:
        return max(0.0, time.time() - f.stat().st_mtime)
    except OSError:
        return None


def plugin_buoc(job_dir: Path | None = None) -> str:
    """Bước plugin đang làm khi áp job ("dò ảnh 400/1813", "ghi 200/1813"...); ""
    khi vòng lặp rảnh hoặc plugin bản cũ (8/10 — xem M.ghiNhip trong AutoToneCore)."""
    try:
        txt = (Path(job_dir or LR_JOB_DIR) / NHIP_PLUGIN).read_text(encoding="utf-8",
                                                                    errors="replace")
    except OSError:
        return ""
    for dong in txt.splitlines():
        if dong.startswith("buoc="):
            return dong[5:].strip()
    return ""


def plugin_song_khi_nao(job_dir: Path | None = None) -> float | None:
    """Lần cuối plugin ghi vào nhật ký, tính bằng giây trước hiện tại.

    None = chưa có nhật ký nào.

    VÌ SAO CẦN: khi file yêu cầu nằm im, có HAI bệnh khác hẳn nhau mà cách chữa
    ngược nhau, và trước đây chỉ báo một bệnh.

      Nhật ký vừa ghi cách đây vài phút  -> plugin ĐANG chạy, nhưng bản trong
        bộ nhớ là bản cũ / vòng lặp đã chết. Chữa: thoát hẳn Lightroom, mở lại.
      Nhật ký cũ hàng giờ                -> Lightroom không mở, hoặc plugin
        chưa hề nạp. Bảo người dùng thoát-mở-lại là vô nghĩa: chưa có gì để
        thoát. Chữa: mở Lightroom lên đã.

    Gặp thật ngày 2/9: nhật ký dừng ở 16:18 hôm trước, mà hộp thoại vẫn khuyên
    "thoát hẳn Lightroom rồi mở lại".
    """
    f = Path(job_dir or LR_JOB_DIR) / "plugin.log"
    try:
        return max(0.0, time.time() - f.stat().st_mtime)
    except OSError:
        return None


def mo_ta_khoang(giay: float | None) -> str:
    if giay is None:
        return "chưa có nhật ký nào"
    if giay < 90:
        return f"{int(giay)} giây trước"
    if giay < 5400:
        return f"{int(giay / 60)} phút trước"
    if giay < 172800:
        return f"{giay / 3600:.1f} giờ trước"
    return f"{giay / 86400:.1f} ngày trước"


def read_plugin_log(lines: int = 400) -> list[str]:
    """Mấy dòng cuối của plugin.log. Plugin ghi mỗi job một dòng kết quả."""
    try:
        return LR_JOB_DIR.joinpath("plugin.log").read_text(
            encoding="utf-8", errors="replace").splitlines()[-lines:]
    except OSError:
        return []


def sent_values(path: str) -> tuple[str, dict] | None:
    """Tra xem ảnh này đã được gửi sang Lightroom chưa, và gửi số gì.

    Tìm ngược từ job mới nhất. Dùng để trả lời đúng câu hỏi hay gặp nhất:
    "ảnh này đã nhận thông số chưa?" — thay vì ngồi nhìn Before/After mà đoán."""
    if not LR_JOB_DIR.is_dir():
        return None
    key = khoa_duong_dan(path)
    jobs = sorted(LR_JOB_DIR.glob("apply_*.done")) + sorted(LR_JOB_DIR.glob("apply_*.tsv"))
    for jp in sorted(jobs, key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            lines = jp.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        if not lines:
            continue
        cols = lines[0].split("	")
        for ln in lines[1:]:
            v = ln.split("	")
            if v and khoa_duong_dan(v[0]) == key:
                rec = {cols[i]: v[i] for i in range(1, min(len(cols), len(v)))
                       if v[i] != ""}
                return jp.name, rec
    return None


def job_result(job: Path | None) -> str:
    """Dòng log plugin ghi cho đúng job này (có số ảnh đã áp), "" nếu chưa có."""
    if job is None:
        return ""
    name = Path(job).with_suffix(".tsv").name
    for ln in reversed(read_plugin_log()):
        if name in ln:
            return ln.split("  ", 1)[-1] if "  " in ln else ln
    return ""


def ten_job(name: str) -> str:
    """Phần tên buổi trong tên file job: apply_<YYYYmmdd_HHMMSS>_<ten_job>.tsv.

    Một chỗ duy nhất — giao diện cũng dùng nó để lọc job của ĐÚNG buổi đang
    mở (job_cua_buoi). Hai nơi tự viết hai biểu thức thì sớm muộn lệch nhau."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", name or "autotone")[:60]


def job_cua_buoi(job: Path, thu_muc) -> bool:
    """Job này có phải của buổi `thu_muc` không (None = mọi buổi)."""
    if thu_muc is None:
        return True
    return Path(job).stem[22:] == ten_job(Path(thu_muc).name)


def write_lr_job(items: list, name: str = "", job_dir: Path | None = None) -> Path | None:
    """Ghi file job cho plugin Lightroom. Trả về đường dẫn, hoặc None nếu không có gì."""
    rows = []
    for r in items:
        if "new_exposure" not in r:
            continue
        if r.get("ngoai_xuat"):
            # khong co trong ban xuat catalog -> khong biet nen, khong ghi
            # (xem attach_catalog_settings)
            continue
        # Ghi cả ảnh không đổi: plugin áp giá trị TUYỆT ĐỐI, nên phải liệt kê đủ thì
        # catalog mới khớp hệt sidecar — kể cả ảnh vừa được trả về đúng mức preset.
        # wb_ep_ghi: nen WB khac WB dang co trong Lightroom (As Shot) — phai ghi
        # ca khi tool khong doi gi, xem compute_values
        wb_changed = (not r.get("bw") and (r.get("new_temp") != r.get("old_temp")
                                           or r.get("new_tint") != r.get("old_tint")
                                           or bool(r.get("wb_ep_ghi")))
                      ) or bool(r.get("bw_tra_wb"))
        # Color Grading: grade_theo_trang_thai() da tinh so MOI cua hai banh xe
        # (moi banh xe ghi rieng — anh thieu cot mau chi tra midtone ve 0)
        gr = bool(r.get("gr_ghi") and r.get("gr_mid"))
        gr_hi = bool(r.get("gr_ghi") and r.get("gr_hi"))
        rows.append([
            # Ưu tiên đường dẫn Lightroom tự đọc ra (xem LR_PATH_KEY). Gửi đường
            # dẫn quét từ đĩa thì lệch hoa/thường là plugin không tìm thấy ảnh.
            r.get("lr_path") or r["path"],
            fmt_f(r["new_exposure"]),
            str(int(r["new_highlights"])),
            str(int(r["new_shadows"])),
            # để trống = plugin không đụng tới trường đó
            str(int(r["new_temp"])) if wb_changed and r.get("new_temp") else "",
            str(int(r["new_tint"])) if wb_changed and r.get("new_temp") else "",
            # 4 núi parametric curve — ô trống nếu lần chạy này không động tới
            *[str(int(r[k])) if k in r else ""
              for k in ("new_ParametricHighlights", "new_ParametricLights",
                        "new_ParametricDarks", "new_ParametricShadows")],
            # Color Grading midtone — ô trống nếu lần chạy này không ghi grade
            *([str(int(r["gr_mid"][0])), str(int(r["gr_mid"][1]))]
              if gr else ["", ""]),
            # ô trống = không đụng tới
            str(int(r["rating"])) if r.get("rating") else "",
            str(int(r["upright"])) if r.get("upright") else "",
            # preset bỏ trống Basic Tone -> đặt đúng số preset SAY (nen_tone)
            *[str(int(r["new_" + k])) if r.get("new_" + k) is not None else ""
              for k in ("Contrast2012", "Whites2012", "Blacks2012")],
            "1" if r.get("bw") else "",
            *([str(int(r["gr_hi"][0])), str(int(r["gr_hi"][1]))]
              if gr_hi else ["", ""]),
            # HSL kenh da: ca sau o (so goc + phan tool chinh o dai da) hoac trong het
            *([str(int(dict(r["hsl_moi"]).get(k, 0))) for k in COT_HSL]
              if r.get("hsl_ghi") and r.get("hsl_moi") else [""] * len(COT_HSL)),
        ])
    if not rows:
        return None

    job_dir = Path(job_dir or LR_JOB_DIR)
    job_dir.mkdir(parents=True, exist_ok=True)
    safe = ten_job(name)
    # Tiền tố apply_ để phân biệt với export_*.tsv (chiều catalog -> autotone)
    dest = job_dir / f"apply_{datetime.now():%Y%m%d_%H%M%S}_{safe}.tsv"

    lines = ["path\t" + "\t".join(LR_JOB_FIELDS)]
    lines += ["\t".join(c) for c in rows]
    # .part rồi đổi tên: plugin không bao giờ đọc phải file đang ghi dở
    tmp = dest.with_suffix(".part")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, dest)
    #[[ 8/10: TRUOC DAY KHONG AI GAN LAST_JOB — giao dien (_ghi_xong) hoi no de
    #   theo doi job vua gui, luon thay None nen bao "(khong gui job nao sang
    #   Lightroom...)" ngay sau khi VUA gui. Buoi ky yeu raw 19.4: ghi lan 1 gui
    #   1089 anh that ma dong trang thai noi khong gui gi -> nguoi dung tuong nut
    #   Ghi hong. ]]
    global LAST_JOB
    LAST_JOB = dest
    return dest


def write_report(items: list, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=REPORT_COLS, extrasaction="ignore")
        w.writeheader()
        for r in items:
            w.writerow(r)


# ======================================================================
# 6. CLI
# ======================================================================

def build_parser() -> argparse.ArgumentParser:
    """Các tham số cũng có trong DEFAULTS đều để default=None, nhờ vậy --config
    không bị default của argparse ghi đè; chỉ cờ gõ thật mới thắng."""
    d = DEFAULTS
    p = argparse.ArgumentParser(
        description="Cân bằng tone tự động cho RAW Sony qua sidecar .xmp",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("folder", type=Path, help="Thư mục chứa .ARW + .xmp")
    p.add_argument("--apply", action="store_true",
                   help="Thực sự ghi vào .xmp (mặc định chỉ chạy thử, không ghi)")
    p.add_argument("--recursive", "-r", action="store_true", help="Quét cả thư mục con")
    #[[ Anh sang cua buoi. Mac dinh None de --config khong bi de len — xem chu
    #   thich dau build_parser(). ]]
    p.add_argument("--anh-sang", dest="che_do_sang",
                   choices=["ngay", "den", "tron"], default=None,
                   help=f"ngay=ca buoi anh sang ngay (ke ca trong nha bat); "
                        f"den=ca buoi anh den; tron=tu tach theo EV100 "
                        f"(md: {d['che_do_sang']})")
    p.add_argument("--ev-ngoai-troi", dest="ev_ngoai_troi", type=float,
                   default=None,
                   help=f"Nguong EV100 tach anh sang ngay / anh den khi "
                        f"--anh-sang tron. 0 = tat, lui ve nguong ISO "
                        f"(md: {d['ev_ngoai_troi']})")
    p.add_argument("--mode", choices=["scene", "batch", "absolute", "hybrid"], default=None,
                   help=f"scene=cân trong từng cảnh; batch=cân cả buổi; absolute=kéo về "
                        f"mức sáng cố định; hybrid=trộn scene+absolute (mđ: {d['mode']})")
    p.add_argument("--meter",
                   choices=["face", "focus", "subject", "center", "average", "median"],
                   default=None,
                   help=f"Cách đo độ sáng (mđ: {d['meter']})")
    p.add_argument("--gap", type=float, default=None,
                   help=f"Phút giữa 2 shot để tách cảnh mới (mđ: {d['gap_minutes']})")
    p.add_argument("--max-ev", type=float, default=None,
                   help=f"Trần |delta| exposure (mđ: {d['max_ev']})")
    p.add_argument("--gain", type=float, default=None,
                   help=f"Hệ số dè dặt cho exposure, 0.7 = chỉnh nhẹ hơn (mđ: {d['exposure_gain']})")
    p.add_argument("--target-ev", type=float, default=None,
                   help=f"Mức sáng đích (log2 linear) cho mode absolute/hybrid "
                        f"(mđ: {d['target_ev']})")
    p.add_argument("--blend", type=float, default=None,
                   help=f"Trọng số hybrid (mđ: {d['blend']})")
    p.add_argument("--no-highlights", action="store_true", help="Không đụng Highlights2012")
    p.add_argument("--no-shadows", action="store_true", help="Không đụng Shadows2012")
    p.add_argument("--wb", choices=["skin", "off", "asshot", "grey", "scene"], default=None,
                   help=f"off=không đụng WB; asshot=kéo nhiệt độ preset về phía nhiệt độ "
                        f"máy đo được của cảnh (khuyến nghị nếu muốn động WB); "
                        f"grey=grey-world trên preview; scene=grey-world nhưng chỉ san "
                        f"phẳng chênh lệch trong cùng một cảnh (mđ: {d['wb']})")
    p.add_argument("--preview-px", type=int, default=None,
                   help=f"Cạnh dài preview khi đo (mđ: {d['preview_px']})")
    p.add_argument("--max-ev-up", type=float, default=None,
                   help="Trần riêng cho chiều kéo sáng (mđ: dùng chung --max-ev)")
    p.add_argument("--burst", action="store_true",
                   help="Lọc ảnh TRÙNG KHUNG (chụp liên tiếp): giữ 2 đẹp nhất mỗi "
                        "pose, ảnh loại 1 sao. Không phải lọc nhắm mắt")
    p.add_argument("--burst-keep", type=int, default=None,
                   help="Giữ bao nhiêu ảnh mỗi pose (mđ: 2)")
    p.add_argument("--loc-mat-to", type=float, default=None, metavar="TI_LE",
                   help="Bỏ khung to mà điểm thấp khi có khung nhỏ hơn nhưng tin cậy "
                        "hơn hẳn. 3.0 là giá trị đã thử; 0 = tắt (mđ: tắt)")
    p.add_argument("--blink", action="store_true",
                   help="Lọc ảnh MẮT KHÔNG DÙNG ĐƯỢC (tính năng riêng): ảnh 1 người "
                        "hoặc nhóm 2-4 người mà có ai nhắm mắt thì loại; ảnh tập thể "
                        "đông người thì bỏ qua. Cần chạy eye_ear.py trước để có ear.csv")
    p.add_argument("--blink-thresh", type=float, default=None,
                   help=f"EAR dưới ngưỡng này coi là mắt không dùng được "
                        f"(mđ: {d['blink_thresh']} — hiệu chuẩn trên 93 nhãn thật)")
    p.add_argument("--blink-max-faces", type=int, default=None,
                   help="Đông hơn bấy nhiêu người thì không loại (mđ: 4)")
    p.add_argument("--upright", action="store_true",
                   help="Auto Transform cho ảnh backdrop / màn LED")
    p.add_argument("--no-scene-sig", action="store_true",
                   help="Không tách cảnh theo bối cảnh khung hình")
    p.add_argument("--gap-khong-can-sig", action="store_true",
                   help="Nhat cat theo thoi gian tinh ngay, khong doi boi canh "
                        "dong y (tro ve hanh vi truoc 3/9)")
    p.add_argument("--no-scene-gap", action="store_true",
                   help="Không tách cảnh theo thời gian (đối xứng với "
                        "--no-scene-sig; tắt cả hai thì cả buổi là một cảnh)")
    p.add_argument("--no-scene-level", action="store_true",
                   help="Không đồng bộ sáng+màu trong cùng bối cảnh")
    p.add_argument("--no-curve", action="store_true",
                   help="Không tự chỉnh parametric curve")
    p.add_argument("--grade", action="store_true",
                   help="Bật Color Grading đẩy tone về da trắng hồng")
    p.add_argument("--no-lr-push", action="store_true",
                   help="Không ghi job cho plugin Lightroom (chỉ ghi .xmp)")
    p.add_argument("--no-marker", action="store_true",
                   help="Không ghi marker baseline atn: (chạy lại lần 2 sẽ cộng dồn!)")
    p.add_argument("--jobs", type=int, default=min(8, (os.cpu_count() or 4)))
    p.add_argument("--report", type=Path, default=None, help="Đường dẫn CSV báo cáo")
    p.add_argument("--backup-dir", type=Path, default=None)
    p.add_argument("--config", type=Path, default=None, help="File JSON ghi đè tham số")
    p.add_argument("--undo", type=Path, default=None,
                   help="Khôi phục .xmp từ thư mục backup rồi thoát")
    p.add_argument("--nguon", choices=["sidecar", "catalog"], default=None,
                   help="sidecar = doc .xmp (md) | catalog = lay tu Lightroom "
                        "qua ban xuat cua plugin, khong can .xmp")
    p.add_argument("--calibrate", default=None, metavar="FILE=EV",
                   help="Hiệu chỉnh mốc sáng theo gu của bạn: chỉ ra một ảnh và "
                        "mức Exposure bạn thấy đúng, ví dụ "
                        '--calibrate "SAY07021.ARW=+0.35"')
    p.add_argument("--watch", action="store_true",
                   help="Chế độ worker: theo dõi thư mục, tự xử lý khi buổi chụp "
                        "import xong (Ctrl+C để dừng)")
    p.add_argument("--subfolders", action="store_true",
                   help="--watch: coi mỗi thư mục con là một buổi chụp riêng")
    p.add_argument("--interval", type=float, default=20.0,
                   help="--watch: bao nhiêu giây kiểm tra một lần")
    p.add_argument("--settle", type=float, default=120.0,
                   help="--watch: thư mục phải yên bao nhiêu giây mới xử lý")
    p.add_argument("--limit", type=int, default=0, help="Chỉ xử lý N ảnh đầu (để thử)")
    return p


def main(argv=None) -> int:
    # Console Windows mac dinh la cp1252 -> ep UTF-8 de in duoc tieng Viet
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    args = build_parser().parse_args(argv)
    root: Path = args.folder.resolve()

    if args.undo:
        n = undo(args.undo.resolve(), root)
        print(f"Đã khôi phục {n} sidecar từ {args.undo}")
        return 0

    if not root.is_dir():
        print(f"Không phải thư mục: {root}", file=sys.stderr)
        return 2

    cfg = dict(DEFAULTS)
    if args.nguon:
        cfg["source"] = args.nguon
    if args.config:
        unknown = set(json.loads(args.config.read_text(encoding="utf-8"))) - set(DEFAULTS)
        if unknown:
            print(f"[!] --config có khoá không dùng đến: {', '.join(sorted(unknown))}",
                  file=sys.stderr)
        cfg.update(json.loads(args.config.read_text(encoding="utf-8")))

    # Thứ tự ưu tiên: cờ dòng lệnh > --config > DEFAULTS
    for cfg_key, val in (("mode", args.mode), ("meter", args.meter),
                         ("gap_minutes", args.gap), ("max_ev", args.max_ev),
                         ("exposure_gain", args.gain), ("target_ev", args.target_ev),
                         ("blend", args.blend), ("wb", args.wb),
                         ("preview_px", args.preview_px),
                         ("max_ev_up", args.max_ev_up)):
        if val is not None:
            cfg[cfg_key] = val

    if args.no_highlights:
        cfg["highlights"] = False
    if args.no_shadows:
        cfg["shadows"] = False
    if args.no_marker:
        cfg["marker"] = False
    if args.no_lr_push:
        cfg["lr_push"] = False
    if args.burst:
        cfg["burst"] = True
    if args.burst_keep is not None:
        cfg["burst_keep"] = args.burst_keep
    if args.loc_mat_to is not None:
        cfg["big_low_ratio"] = args.loc_mat_to
    if args.blink:
        cfg["blink"] = True
    if args.blink_thresh is not None:
        cfg["blink_thresh"] = args.blink_thresh
    if args.blink_max_faces is not None:
        cfg["blink_max_faces"] = args.blink_max_faces
    if args.upright:
        cfg["upright"] = True
    if args.no_scene_sig:
        cfg["scene_sig_thresh"] = 0.0
    if args.no_scene_gap:
        cfg["gap_minutes"] = 0.0
    if args.gap_khong_can_sig:
        cfg["scene_gap_can_sig"] = False
    if args.no_scene_level:
        cfg["scene_level"] = 0.0
    if args.no_curve:
        cfg["curve"] = False
    if args.grade:
        cfg["grade"] = True

    if args.calibrate:
        spec = args.calibrate
        if "=" not in spec:
            print('Cú pháp: --calibrate "duong/dan/anh.ARW=+0.35"', file=sys.stderr)
            return 2
        fpath, want = spec.rsplit("=", 1)
        fp = Path(fpath.strip().strip('"'))
        if not fp.is_absolute():
            fp = root / fp
        if not fp.is_file():
            print(f"Không thấy file: {fp}", file=sys.stderr)
            return 2
        try:
            want_ev = float(want.replace("+", ""))
        except ValueError:
            print(f"Không đọc được mức EV: {want!r}", file=sys.stderr)
            return 2

        r = measure(fp, cfg["preview_px"], cfg["meter"], cfg["meter_highlight_cut"],
                    True, cfg["face_px"], cfg["face_score"],
                    cfg["focus_quantile"], cfg["focus_face_gain"],
                    cfg.get("face_min_ratio", 0.25),
                    cfg.get("subject_keep", 0.60),
                    cfg.get("subject_dark_ev", 2.0),
                    cfg.get("face_min_score_sub", 0.0),
                    cfg.get("big_low_ratio", 0.0),
                    cfg.get("big_low_gap", 0.13),
                    cfg.get("big_low_floor", 0.70),
                    bool(cfg.get("blink")))
        if not r.get("ok"):
            print(f"Không đo được: {r['error']}", file=sys.stderr)
            return 1
        src = ("khuôn mặt" if r.get("metered_face_ev") is not None else
               "vùng bắt nét" if r.get("metered_focus_ev") is not None else "chủ thể")
        base = (r.get("metered_face_ev") if r.get("metered_face_ev") is not None
                else r.get("metered_focus_ev") if r.get("metered_focus_ev") is not None
                else r["metered_subject_ev"])
        key = "face_target_ev" if cfg["meter"] == "face" else "target_ev"
        print(f"{fp.name}: đo được {base:+.2f} EV trên {src} "
              f"({r['faces_n']} mặt)")
        print(f"Bạn muốn Exposure {want_ev:+.2f}  ->  mốc phù hợp: "
              f"{base + want_ev:+.3f}")
        print(f"\nHiện tại {key} = {cfg[key]:+.2f}. Đổi bằng file --config:")
        print(f'    {{"{key}": {base + want_ev:.3f}}}')
        return 0


    if args.watch:
        w = Watcher(root, cfg, recursive=args.recursive, subfolders=args.subfolders,
                    interval=args.interval, settle=args.settle, jobs=args.jobs,
                    log=lambda m: print(f"{datetime.now():%H:%M:%S}  {m}", flush=True),
                    write=args.apply)
        try:
            w.loop()
        except KeyboardInterrupt:
            print("\nĐã dừng.")
        return 0

    #[[ Che do catalog KHONG can sidecar.
    #
    #   Thong so den tu ban xuat cua plugin (export_*.tsv), khong phai tu .xmp.
    #   Bat sidecar o day thi chinh che do sinh ra de khoi phai Ctrl+S lai bi
    #   chan boi dieu kien Ctrl+S — vong tron.
    #]]
    can_sc = cfg.get("source") != "catalog"
    pairs, missing = collect_pairs(root, args.recursive, args.limit,
                                   need_sidecar=can_sc)
    if not pairs and not missing:
        print(f"Không tìm thấy file RAW nào trong {root}", file=sys.stderr)
        return 1
    if missing:
        print(f"[!] {len(missing)} RAW chưa có sidecar .xmp — bỏ qua. "
              f"Trong Lightroom chọn ảnh rồi Ctrl+S để tạo, "
              f"hoặc chạy kèm --nguon catalog.")
        for p in missing[:5]:
            print(f"    - {p.name}")
    if not pairs:
        return 1

    jobs = safe_jobs(args.jobs, cfg)
    if jobs < args.jobs:
        print(f"[!] chỉ còn {free_ram_mb() / 1024:.1f} GB RAM trống — giảm còn "
              f"{jobs} tiến trình (yêu cầu {args.jobs}) để khỏi MemoryError.",
              file=sys.stderr)
    print(f"Đang đo {len(pairs)} ảnh (preview {cfg['preview_px']}px, {jobs} tiến trình)...")
    items, failed = analyze(pairs, cfg, jobs)

    for f in failed:
        print(f"[lỗi] {Path(f['path']).name}: {f['error']}", file=sys.stderr)
    if not items:
        return 1

    plan(items, cfg)

    backup_dir = None
    if args.apply:
        backup_dir = write_sidecars(items, cfg, root, args.backup_dir)

    # ---- in kết quả ----
    nsc = len({r["scene"] for r in items})
    print(f"\n{len(items)} ảnh / {nsc} cảnh  (mode={cfg['mode']}, meter={cfg['meter']}, "
          f"gap={cfg['gap_minutes']}p, max={cfg['max_ev']:+.2f}EV, wb={cfg['wb']})")
    print(f"{'file':<26}{'cảnh':>5}{'ΔEV':>8}{'Exp':>8}{'HL':>6}{'SH':>6}"
          f"{'cháy%':>8}{'tối%':>7}  ghi chú")
    print("-" * 92)
    for r in items:
        print(f"{Path(r['path']).name[:25]:<26}{r['scene']:>5}{r['delta_ev']:>+8.2f}"
              f"{r['new_exposure']:>+8.2f}{r['new_highlights']:>6d}{r['new_shadows']:>6d}"
              f"{r['clip_after_pct']:>8.2f}{r['shadow_after_pct']:>7.2f}  {r.get('notes','')}")

    d = np.array([r["delta_ev"] for r in items])
    print("-" * 92)
    print(f"ΔEV: trung bình {d.mean():+.2f}, min {d.min():+.2f}, max {d.max():+.2f}, "
          f"số ảnh đổi {int((d != 0).sum())}/{len(d)}")

    if args.report:
        write_report(items, args.report)
        print(f"Báo cáo: {args.report}")

    if args.apply:
        print(f"\nĐã ghi {len(items)} sidecar. Backup: {backup_dir}")
        print(f"Hoàn tác:  python autotone.py \"{root}\" --undo \"{backup_dir}\"")
        print("Bước cuối trong Lightroom: chọn ảnh > Metadata > Read Metadata from File")
    else:
        print("\n(chạy thử — chưa ghi gì). Thêm --apply để ghi vào .xmp")
    return 0


if __name__ == "__main__":
    sys.exit(main())
