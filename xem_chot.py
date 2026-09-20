#!/usr/bin/env python3
"""Dựng bảng ảnh để chấm bằng mắt: chốt chặn báo-mặt-ảo làm ĐÚNG hay làm HỎNG.

VÌ SAO CẦN
    Đo trên 400 ảnh buổi 1308 với ngưỡng 0.80: 14% ảnh đổi kết quả cân sáng,
    4,5% đổi từ 1 EV trở lên. Con số đó nói MỨC THAY ĐỔI, không nói thay đổi
    theo hướng tốt hay xấu. Chỉ có mắt người trả lời được câu đó.

    Mỗi ảnh chỉ cần một câu hỏi: KHUNG BỊ LOẠI (viền xám gạch) có phải khuôn
    mặt thật không?
        - không phải mặt  -> chốt chặn làm đúng
        - là mặt thật     -> chốt chặn làm hỏng, ngưỡng đang quá cao

CÁCH ĐỌC BẢNG
    viền XANH LÁ  khuôn mặt chốt chặn giữ lại — nơi lấy độ sáng SAU khi bật
    viền ĐỎ       chủ thể TRƯỚC khi bật, nếu nó khác
    viền XÁM      khung bị chốt chặn loại, kèm điểm tin cậy của YuNet
    Không còn khung xanh nào = ảnh mất hẳn mặt, lùi về đo theo vùng bắt nét.

CÁCH DÙNG
    python xem_chot.py "G:\\1308" --nguong 0.80 --n 24 --toi-thieu 1.0
    -> xem_chot_01.png  +  xem_chot_index.csv (cột 'chot_dung' để anh điền)
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at   # noqa: E402
import so_sanh_do_mat as ss   # noqa: E402

CELL = 460          # cạnh ô ảnh trong bảng
PAD = 34            # chỗ chừa ghi tên ảnh và EV
COLS = 3


def doc_csv(p: Path, toi_thieu: float, n: int) -> list:
    """Lấy những ảnh đổi nhiều nhất — chỗ chốt chặn có sức tàn phá lớn nhất."""
    with io.open(p, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    out = []
    for r in rows:
        try:
            d = float(r["lech_ev"])
        except (TypeError, ValueError):
            continue
        if abs(d) >= toi_thieu:
            r["d"] = d
            out.append(r)
    out.sort(key=lambda r: -abs(r["d"]))
    return out[:n]


def ve(p: Path, thr: float, px: int):
    """Vẽ khung lên preview: giữ lại / bị loại / chủ thể cũ."""
    im = ss.load_preview(p, px)
    if im is None:
        return None
    im = im.convert("RGB")
    faces = ss.yunet_faces(im, at.DEFAULTS["face_score"])
    giu = [f for f in faces if f[4] >= thr]
    loai = [f for f in faces if f[4] < thr]
    cu = ss.subject(faces)
    moi = ss.subject(giu)

    d = ImageDraw.Draw(im)
    for f in loai:
        x, y, w, h = f[:4]
        # gạch chéo cho dễ phân biệt khi in đen trắng hoặc nhìn nhanh
        d.rectangle([x, y, x + w, y + h], outline=(150, 150, 155), width=3)
        d.line([x, y, x + w, y + h], fill=(150, 150, 155), width=2)
        d.text((x + 4, y + 4), f"{f[4]:.2f}", fill=(230, 230, 235))
    if cu is not None and (moi is None or cu is not moi):
        x, y, w, h = cu[:4]
        d.rectangle([x, y, x + w, y + h], outline=(240, 70, 70), width=5)
    if moi is not None:
        x, y, w, h = moi[:4]
        d.rectangle([x, y, x + w, y + h], outline=(70, 220, 120), width=5)
    im.thumbnail((CELL - 10, CELL - 10))
    return im


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Xem chốt chặn làm đúng hay hỏng.")
    ap.add_argument("folder", type=Path)
    ap.add_argument("--nguong", type=float, default=0.80)
    ap.add_argument("--n", type=int, default=24, help="Số ảnh đưa vào bảng")
    ap.add_argument("--toi-thieu", type=float, default=1.0,
                    help="Chỉ lấy ảnh lệch từ bấy nhiêu EV trở lên (mđ: 1.0)")
    ap.add_argument("--csv", type=Path, default=None,
                    help="File chot_mat_ao.csv (mđ: nằm trong chính thư mục ảnh)")
    a = ap.parse_args(argv)

    src = a.csv or (a.folder / "chot_mat_ao.csv")
    if not src.exists():
        print(f"Chua co {src.name}. Chay do_chot_mat_ao.py truoc.")
        return 1
    sel = doc_csv(src, a.toi_thieu, a.n)
    if not sel:
        print(f"Khong co anh nao lech tu {a.toi_thieu} EV tro len.")
        return 1
    print(f"Dung bang cho {len(sel)} anh lech nhieu nhat...")

    cells = []
    for r in sel:
        p = a.folder / f"{r['file']}.ARW"
        if not p.exists():
            cand = list(a.folder.glob(r["file"] + ".*"))
            p = cand[0] if cand else None
        if p is None:
            continue
        im = ve(p, a.nguong, at.DEFAULTS["face_px"])
        if im is not None:
            cells.append((r, im))

    # Ít ảnh hơn một hàng thì thu số cột lại, khỏi chừa khoảng đen vô ích
    cols = min(COLS, len(cells))
    rows_n = (len(cells) + cols - 1) // cols
    # Chú thích đặt DƯỚI ảnh theo chiều cao thật của nó, không đặt theo ô —
    # ảnh dọc cao gần bằng ô nên đặt cứng sẽ đè lên mặt người.
    hmax = max(im.size[1] for _r, im in cells)
    sheet = Image.new("RGB", (cols * CELL, rows_n * (hmax + PAD + 10)), (22, 22, 24))
    d = ImageDraw.Draw(sheet)
    for i, (r, im) in enumerate(cells):
        cx, cy = (i % cols) * CELL, (i // cols) * (hmax + PAD + 10)
        sheet.paste(im, (cx + 5, cy + 5))
        mat = "MAT HAN MAT -> do vung net" if r["nguon_sau"] == "net" else "doi chu the"
        ty = cy + im.size[1] + 10
        d.text((cx + 6, ty),
               f"{i + 1}. {r['file']}   EV {float(r['ev_truoc']):+.2f} -> "
               f"{float(r['ev_sau']):+.2f}  ({r['d']:+.2f})", fill=(235, 235, 240))
        d.text((cx + 6, ty + 14), f"    {mat}", fill=(175, 175, 182))

    dest = a.folder / "xem_chot_01.png"
    sheet.save(dest)

    idx = a.folder / "xem_chot_index.csv"
    with io.open(idx, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["so_thu_tu", "file", "lech_ev", "nguon_sau", "chot_dung"])
        for i, (r, _im) in enumerate(cells, 1):
            w.writerow([i, r["file"], f"{r['d']:.2f}", r["nguon_sau"], ""])

    print(f"  -> {dest.name}\n  -> {idx.name}")
    print("\nVoi moi o, chi hoi mot cau: KHUNG XAM GACH CHEO co phai mat that khong?")
    print("  khong phai mat -> chot dung  -> dien 1 vao cot 'chot_dung'")
    print("  la mat that    -> chot hong  -> dien 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
