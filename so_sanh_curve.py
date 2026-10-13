# -*- coding: utf-8 -*-
"""PDF trước / sau cho curve da + nén cháy (13/10) — user XEM TẬN MẮT rồi mới bật mặc định.

Mỗi trang hai cặp: ảnh Lightroom dựng TRƯỚC curve | SAU curve (ảnh thật của buổi cổng,
kiem_cong_curve.py dựng), kèm ô phóng mặt ×2 (khung mặt tool đo) và dòng số: hue / độ
đậm da trước → sau → đích, Δ R/G/B, cháy % trước → sau. Giống bản so_sanh_nikon_2609
user đã duyệt AF Nikon.

Dùng:  from so_sanh_curve import lap_pdf; lap_pdf(cap, "x.pdf")
       cap = [{"ten", "r1", "r2", "mat": (x, y, w, h) theo ảnh dựng | None, "chu": [dòng]}]
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

GOC = Path(__file__).resolve().parent
TRANG = (1754, 1240)                       # A4 ngang, 150 dpi
NEN = (24, 24, 26)
CHU = (237, 235, 231)
MO = (166, 163, 157)


def _phong(co: int):
    for ten in ("BeVietnamPro-Regular.ttf", "BeVietnamPro-Medium.ttf"):
        p = GOC / "fonts" / ten
        if p.is_file():
            try:
                return ImageFont.truetype(str(p), co)
            except OSError:
                pass
    return ImageFont.load_default()


def _vua(im: Image.Image, rong: int, cao: int) -> Image.Image:
    im = im.copy()
    im.thumbnail((rong, cao))
    return im


def _o_mat(im: Image.Image, mat, canh: int) -> Image.Image | None:
    if not mat:
        return None
    x, y, w, h = (float(v) for v in mat)
    cx, cy, s = x + w / 2, y + h / 2, max(w, h) * 0.75
    o = im.crop((int(cx - s), int(cy - s), int(cx + s), int(cy + s)))
    return o.resize((canh, canh), Image.LANCZOS)


def _cap(trang: Image.Image, d: ImageDraw.ImageDraw, c: dict, y0: int, cao: int):
    """Một cặp: TRƯỚC | SAU (ảnh dựng), cột phải hai ô mặt ×2, dòng số ở dưới."""
    f_ten, f_so = _phong(20), _phong(16)
    rong_anh, o_mat = 690, 220
    cao_anh = cao - 40 - 26 * max(1, len(c.get("chu") or [])) - 10
    try:
        r1, r2 = Image.open(c["r1"]).convert("RGB"), Image.open(c["r2"]).convert("RGB")
    except OSError as ex:
        d.text((40, y0 + 10), f"{c.get('ten', '?')}: không mở được ảnh ({ex})", fill=MO, font=f_so)
        return
    x = 40
    for nhan, im in (("TRƯỚC", r1), ("SAU", r2)):
        trang.paste(_vua(im, rong_anh, cao_anh), (x, y0 + 30))
        d.text((x, y0 + 6), nhan, fill=MO, font=f_so)
        x += rong_anh + 16
    for k, im in enumerate((r1, r2)):
        o = _o_mat(im, c.get("mat"), min(o_mat, (cao_anh - 12) // 2))
        if o is not None:
            trang.paste(o, (x, y0 + 30 + k * (o.size[1] + 12)))
    y = y0 + 30 + cao_anh + 8
    for i, dong in enumerate(c.get("chu") or [c.get("ten", "")]):
        d.text((40, y + i * 26), str(dong), fill=CHU if i == 0 else MO, font=f_ten if i == 0 else f_so)


def lap_pdf(cap: list, dest, tieu_de: str = "") -> Path | None:
    """cap: danh sách cặp (xem đầu file). Hai cặp một trang. -> đường dẫn PDF."""
    if not cap:
        return None
    trangs = []
    cao_cap = (TRANG[1] - 90) // 2
    for i in range(0, len(cap), 2):
        t = Image.new("RGB", TRANG, NEN)
        d = ImageDraw.Draw(t)
        d.text((40, 24), f"{tieu_de}   ·   trang {i // 2 + 1}/{(len(cap) + 1) // 2}", fill=MO, font=_phong(18))
        for k, c in enumerate(cap[i:i + 2]):
            _cap(t, d, c, 70 + k * cao_cap, cao_cap)
        trangs.append(t)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    trangs[0].save(dest, "PDF", resolution=150, save_all=True, append_images=trangs[1:])
    return dest
