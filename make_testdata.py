# -*- coding: utf-8 -*-
"""Sinh bo du lieu gia lap: file .ARW dang TIFF co preview JPEG nhung + sidecar .xmp."""
import io
import struct
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from PIL import Image

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "testshoot")
PRESET = Path.home() / "AppData/Roaming/Adobe/CameraRaw/Settings/saymedia.xmp"

SIDECAR_TMPL = """<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Adobe XMP Core 7.0">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"
   xmp:MetadataDate="2026-08-20T10:00:00+07:00"
   crs:Version="18.5"
   crs:ProcessVersion="15.4"
   crs:WhiteBalance="Custom"
   crs:Temperature="5300"
   crs:Tint="+9"
   crs:Exposure2012="0.00"
   crs:Contrast2012="+5"
   crs:Highlights2012="+16"
   crs:Shadows2012="+16"
   crs:Whites2012="-25"
   crs:Blacks2012="-18"
   crs:Vibrance="+12"
   crs:ToneCurveName2012="Custom"
   crs:HasSettings="True">
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
"""


def make_jpeg(brightness, w=1616, h=1080, cast=(1.0, 1.0, 1.0), seed=0):
    """Anh test: gradient + vung sang manh + nhieu, nhan he so do sang va cast mau."""
    rng = np.random.default_rng(seed)
    yy = np.linspace(0.15, 0.75, h)[:, None]
    xx = np.linspace(0.9, 1.1, w)[None, :]
    base = yy * xx
    # mot vung cua so sang gat de tao clipping
    base[int(h * 0.05):int(h * 0.35), int(w * 0.60):int(w * 0.95)] *= 3.2
    base = base + rng.normal(0, 0.01, (h, w))
    img = np.stack([base * cast[0], base * cast[1], base * cast[2]], axis=2)
    img = np.clip(img * brightness, 0, 1) ** (1 / 2.2)
    im = Image.fromarray((img * 255).astype(np.uint8), "RGB")
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def ascii_pad(s):
    b = s.encode("ascii") + b"\x00"
    return b


def build_arw(jpeg, dt, iso=400):
    """TIFF little-endian toi thieu: IFD0 (+ExifIFD) tro toi JPEG nhung."""
    dt_s = dt.strftime("%Y:%m:%d %H:%M:%S")
    dt_b = ascii_pad(dt_s)          # 20 bytes
    model_b = ascii_pad("ILCE-7M4")
    make_b = ascii_pad("SONY")

    header_len = 8
    ifd0_count = 6
    ifd0_len = 2 + ifd0_count * 12 + 4
    exif_count = 2
    exif_len = 2 + exif_count * 12 + 4

    ifd0_off = header_len
    exif_off = ifd0_off + ifd0_len
    data_off = exif_off + exif_len

    # vung du lieu ngoai entry
    blobs, cursor = [], data_off
    def put(b):
        nonlocal cursor
        off = cursor
        blobs.append(b)
        cursor += len(b) + (len(b) % 2)
        return off

    dt_off = put(dt_b)
    model_off = put(model_b)
    make_off = put(make_b)
    jpeg_off = cursor
    cursor += len(jpeg)

    def entry(tag, typ, cnt, val_bytes):
        assert len(val_bytes) == 4
        return struct.pack("<HHI", tag, typ, cnt) + val_bytes

    L = lambda v: struct.pack("<I", v)
    S = lambda v: struct.pack("<HH", v, 0)

    ifd0 = struct.pack("<H", ifd0_count)
    ifd0 += entry(0x010F, 2, len(make_b), L(make_off))
    ifd0 += entry(0x0110, 2, len(model_b), L(model_off))
    ifd0 += entry(0x0132, 2, len(dt_b), L(dt_off))
    ifd0 += entry(0x0201, 4, 1, L(jpeg_off))
    ifd0 += entry(0x0202, 4, 1, L(len(jpeg)))
    ifd0 += entry(0x8769, 4, 1, L(exif_off))
    ifd0 += L(0)
    assert len(ifd0) == ifd0_len, (len(ifd0), ifd0_len)

    exif = struct.pack("<H", exif_count)
    exif += entry(0x9003, 2, len(dt_b), L(dt_off))
    exif += entry(0x8827, 3, 1, S(iso))
    exif += L(0)
    assert len(exif) == exif_len

    out = bytearray()
    out += b"II" + struct.pack("<HI", 42, ifd0_off)
    out += ifd0 + exif
    for b in blobs:
        out += b
        if len(b) % 2:
            out += b"\x00"
    out += jpeg
    return bytes(out)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = datetime(2026, 8, 20, 14, 0, 0)

    # Canh 1: 5 anh lech sang manh (mo phong AE nhay), chup lien tuc
    # Canh 2: cach 40 phut, toan bo canh toi hon han
    plan = []
    for i, b in enumerate([0.45, 0.62, 1.00, 0.80, 1.55]):
        plan.append((f"DSC0{100+i}.ARW", b, t0 + timedelta(seconds=25 * i), (1.0, 1.0, 1.0)))
    for i, b in enumerate([0.30, 0.34, 0.28]):
        plan.append((f"DSC0{200+i}.ARW", b, t0 + timedelta(minutes=40, seconds=30 * i),
                     (0.85, 1.0, 1.25)))   # cast xanh, de thu --wb

    for name, b, dt, cast in plan:
        jpg = make_jpeg(b, cast=cast, seed=hash(name) % 1000)
        (OUT / name).write_bytes(build_arw(jpg, dt))
        (OUT / name).with_suffix(".xmp").write_text(SIDECAR_TMPL, encoding="utf-8")

    # them 1 anh khong co sidecar de thu nhanh canh bao
    jpg = make_jpeg(0.9, seed=7)
    (OUT / "DSC0999.ARW").write_bytes(build_arw(jpg, t0 + timedelta(minutes=41)))

    print(f"Da tao {len(plan)} cap ARW+XMP (+1 ARW thieu sidecar) trong {OUT.resolve()}")
    for p in sorted(OUT.glob('*.ARW')):
        print(f"  {p.name}  {p.stat().st_size/1024:.0f} KB")


if __name__ == "__main__":
    main()
