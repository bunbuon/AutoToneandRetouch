#!/usr/bin/env python3
"""Vẽ ra đúng những khuôn mặt AutoTone dùng để đo sáng, cho người chấm bằng mắt.

VÌ SAO PHẢI LÀ HÀM THẬT, KHÔNG PHẢI BẢN DỰNG LẠI
    Trong dự án này tôi đã hai lần dựng lại logic chọn chủ thể ở file phân tích
    rồi rút ra kết luận sai, vì bản dựng lại thiếu các vòng lọc mà measure()
    thật sự chạy (điểm bắt nét AF, lọc theo độ nét, lọc mặt tối hơn hẳn). Có
    ảnh tôi kết luận "đang đo sáng trên phông nền" trong khi bản thật đã bỏ
    khung phông từ lâu và đang đo đúng mặt người.

    Nên file này KHÔNG tự chọn gì cả. Nó gọi thẳng autotone.measure() rồi vẽ
    lại đúng ba thứ hàm đó trả về: mọi khung YuNet báo, khung nào đi vào phép
    đo, và khung nặng ký nhất.

BA MÀU
    XANH LÁ dày   khung NẶNG KÝ NHẤT — chủ thể chính của phép đo sáng
    XANH DƯƠNG    khung cũng được tính vào phép đo (ảnh nhóm thì cả nhóm)
    XÁM gạch chéo khung YuNet báo nhưng đã bị loại, không ảnh hưởng độ sáng

CÁCH DÙNG
    python xem_do_sang.py "G:\\1308" --n 50
    -> do_sang_01.png, do_sang_02.png ...  +  do_sang_index.csv
"""
from __future__ import annotations

import argparse
import csv
import io
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at   # noqa: E402

CELL = 430          # cạnh ô ảnh
PAD = 30            # chỗ chừa ghi chú dưới mỗi ô
COLS = 4
PER_SHEET = 12      # 12 ô mỗi tấm — đủ lớn để nhìn rõ mặt nhỏ


def do_mot_anh(p: Path, cfg: dict) -> dict:
    """Gọi ĐÚNG hàm sản phẩm. Không thêm, không bớt, không đoán."""
    return at.measure(
        p, cfg["preview_px"], cfg["meter"], cfg["meter_highlight_cut"],
        cfg["wb"] == "skin", cfg["face_px"], cfg["face_score"],
        cfg["focus_quantile"], cfg["focus_face_gain"],
        cfg.get("face_min_ratio", 0.0), cfg.get("subject_keep", 0.60),
        cfg.get("subject_dark_ev", 2.0), cfg.get("face_min_score_sub", 0.0),
        cfg.get("big_low_ratio", 0.0), cfg.get("big_low_gap", 0.13),
        cfg.get("big_low_floor", 0.70))


def preview(p: Path, px: int):
    blob, tags = at.read_raw(p)
    if blob is None:
        return None
    im = Image.open(io.BytesIO(blob))
    im.draft("RGB", (px, px))
    im = at.apply_orientation(im.convert("RGB"), tags.get("orientation"))
    im.thumbnail((px, px), Image.BILINEAR)
    return im.convert("RGB")


def ve(im: Image.Image, r: dict):
    """Vẽ ba loại khung. Toạ độ lấy nguyên từ measure() nên khớp tuyệt đối."""
    d = ImageDraw.Draw(im)
    meter = [tuple(b[:4]) for b in (r.get("meter_boxes") or [])]
    sub = r.get("subject_box")
    sub4 = tuple(sub[:4]) if sub else None
    for b in (r.get("all_boxes") or []):
        x, y, w, h, s = b
        key = (x, y, w, h)
        if sub4 is not None and _gan(key, sub4):
            col, wd = (60, 220, 120), 5
        elif any(_gan(key, m) for m in meter):
            col, wd = (80, 170, 255), 4
        else:
            col, wd = (155, 155, 160), 2
            d.line([x, y, x + w, y + h], fill=col, width=1)
        d.rectangle([x, y, x + w, y + h], outline=col, width=wd)
        d.text((x + 3, y + 3), f"{s:.2f}", fill=(245, 245, 250))
    return im


def _gan(a, b, eps: float = 1.5) -> bool:
    return all(abs(u - v) <= eps for u, v in zip(a, b))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Xem AutoTone đo sáng ở khuôn mặt nào.")
    ap.add_argument("folder", type=Path)
    ap.add_argument("--n", type=int, default=50, help="Số ảnh lấy ngẫu nhiên (mđ: 50)")
    ap.add_argument("--seed", type=int, default=1308,
                    help="Hạt ngẫu nhiên — giữ nguyên thì lần sau ra đúng bộ ảnh cũ")
    ap.add_argument("--chi-nhieu-mat", action="store_true",
                    help="Chỉ lấy ảnh có từ 2 khuôn mặt trở lên (nơi dễ chọn nhầm)")
    #[[ Bat luat NGAY TREN DONG LENH, khong phai sua ma nguon.
    #   Truoc do muon thu luat phai vao sua DEFAULTS trong autotone.py — de
    #   quen, va da xay ra that: nguoi dung chay lai roi tuong luat khong an,
    #   trong khi thuc te luat chua he chay.
    #]]
    ap.add_argument("--luat", action="store_true",
                    help="BẬT luật bỏ khung to mà điểm thấp (mặc định tắt)")
    ap.add_argument("--ti-le", type=float, default=3.0,
                    help="Khung to gấp bấy nhiêu lần thì mới xét bỏ (mđ: 3.0)")
    a = ap.parse_args(argv)

    files = sorted(p for p in a.folder.iterdir() if p.suffix.lower() in at.RAW_EXTS)
    if not files:
        print("Khong thay file RAW nao.")
        return 1
    random.Random(a.seed).shuffle(files)

    cfg = dict(at.DEFAULTS)
    if a.luat:
        cfg["big_low_ratio"] = a.ti_le
    print(f"Luat bo khung to ma diem thap: "
          f"{'BAT (ti le ' + str(cfg['big_low_ratio']) + ')' if cfg['big_low_ratio'] > 0 else 'TAT'}")
    cells, i = [], 0
    print(f"Do va ve toi da {a.n} anh (hat ngau nhien {a.seed})...")
    while len(cells) < a.n and i < len(files):
        p = files[i]
        i += 1
        try:
            r = do_mot_anh(p, cfg)
        except Exception as ex:                      # noqa: BLE001
            print(f"  [!] {p.name}: {type(ex).__name__}: {ex}")
            continue
        if not r.get("ok"):
            continue
        boxes = r.get("all_boxes") or []
        if a.chi_nhieu_mat and len(boxes) < 2:
            continue
        im = preview(p, cfg["face_px"])
        if im is None:
            continue
        cells.append((p.stem, r, ve(im, r)))
        if len(cells) % 10 == 0:
            print(f"  {len(cells)}/{a.n}")

    if not cells:
        print("Khong ve duoc anh nao.")
        return 1

    made = []
    for s in range(0, len(cells), PER_SHEET):
        chunk = cells[s:s + PER_SHEET]
        for _n, _r, im in chunk:
            im.thumbnail((CELL - 10, CELL - 10))
        cols = min(COLS, len(chunk))
        rows_n = (len(chunk) + cols - 1) // cols
        #[[ Chieu cao TUNG HANG tinh rieng, khong lay chung mot chieu cao lon
        #   nhat ca tam. Anh doc cao gan gap doi anh ngang, lay chung thi hang
        #   toan anh ngang bi chua mot khoang den to bang nua o.
        #]]
        hrow = [max(im.size[1] for _n, _r, im in chunk[ri * cols:(ri + 1) * cols])
                for ri in range(rows_n)]
        ytop = [10 + sum(h + PAD + 14 for h in hrow[:ri]) for ri in range(rows_n)]
        H = ytop[-1] + hrow[-1] + PAD + 14
        sheet = Image.new("RGB", (cols * CELL, H), (22, 22, 24))
        d = ImageDraw.Draw(sheet)
        for k, (nm, r, im) in enumerate(chunk):
            cx = (k % cols) * CELL
            cy = ytop[k // cols] - 5
            sheet.paste(im, (cx + 5, cy + 5))
            nguon = ("khuon mat" if r.get("metered_face_ev") is not None else
                     "vung bat net" if r.get("metered_focus_ev") is not None
                     else "ca khung hinh")
            ty = cy + im.size[1] + 10
            d.text((cx + 6, ty), f"{s + k + 1}. {nm}   {len(r.get('all_boxes') or [])} khung"
                                 f" -> {len(r.get('meter_boxes') or [])} do sang",
                   fill=(238, 238, 242))
            d.text((cx + 6, ty + 14), f"    do theo {nguon}   EV "
                                      f"{r.get('metered_ev', 0):+.2f}",
                   fill=(172, 172, 180))
        nhan = "LUAT BAT" if cfg["big_low_ratio"] > 0 else "luat tat"
        d.text((8, H - 16), f"[{nhan}]  seed {a.seed}", fill=(150, 150, 158))
        hau = "_luat" if cfg["big_low_ratio"] > 0 else ""
        dest = a.folder / f"do_sang{hau}_{s // PER_SHEET + 1:02d}.png"
        sheet.save(dest)
        made.append(dest)

    idx = a.folder / ("do_sang_luat_index.csv" if cfg["big_low_ratio"] > 0
                      else "do_sang_index.csv")
    with io.open(idx, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["so_thu_tu", "file", "so_khung", "so_khung_do_sang",
                    "nguon_do", "metered_ev", "chon_dung", "ghi_chu"])
        for k, (nm, r, _im) in enumerate(cells, 1):
            nguon = ("mat" if r.get("metered_face_ev") is not None else
                     "net" if r.get("metered_focus_ev") is not None else "khung")
            w.writerow([k, nm, len(r.get("all_boxes") or []),
                        len(r.get("meter_boxes") or []), nguon,
                        f"{r.get('metered_ev', 0):.3f}", "", ""])

    for f in made:
        print("  ->", f.name)
    print(f"  -> {idx.name}")
    print("\nXANH LA day = mat nang ky nhat, chu the chinh cua phep do sang")
    print("XANH DUONG  = khung cung duoc tinh vao phep do")
    print("XAM gach    = khung bi loai, khong anh huong do sang")
    print("\nO nao chon SAI chu the thi ghi so cua no vao cot 'chon_dung' = 0.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
