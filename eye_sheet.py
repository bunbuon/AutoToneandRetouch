#!/usr/bin/env python3
"""Cắt vùng mắt của một mẫu ảnh ra thành bảng để người dùng chấm bằng mắt.

VÌ SAO CẦN
    Luật lọc ảnh nhắm mắt cần một phép đo tin được. Phép đo hiện tại
    (_eye_openness) đã bị bác bỏ bằng số liệu buổi 1308: ở mọi ngưỡng nó loại
    oan nhiều hơn bắt đúng, tỉ lệ tốt nhất chỉ 0.37 — tệ hơn tung đồng xu.

    Muốn thay phép đo thì phải có NHÃN THẬT: ảnh nào mắt thực sự nhắm. Mà nhãn
    1 sao sẵn có KHÔNG dùng được — 377 ảnh 1 sao của buổi 1308 là do chính tool
    gán khi lọc trùng khung (nhật ký ghi "377 gan sao"), không phải người dùng
    tự chấm. Lấy nó ra kiểm chính tool là lập luận vòng.

    File này cắt sẵn vùng mắt ra một tấm ảnh lớn, đánh số từng ô. Người dùng chỉ
    cần đọc số của những ô mắt NHẮM — vài phút, thay vì lục 1464 ảnh.

LẤY MẪU THẾ NÀO
    Trải đều theo giá trị đo hiện tại, KHÔNG chỉ lấy phần nghi ngờ nhất. Lấy
    lệch về một phía thì không biết phép đo mới đúng hay chỉ đang khớp với phép
    đo cũ. Cần cả ô mắt mở lẫn ô mắt nhắm để so.

CÁCH DÙNG
    python eye_sheet.py "G:\\1308" --csv autotone20260831_2102.csv
    -> sinh ra eye_sheet_01.png, eye_sheet_02.png ... và eye_sheet_index.csv
"""

from __future__ import annotations

import argparse
import csv
import io
import ntpath
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at   # noqa: E402

CELL = 190          # cạnh mỗi ô trong bảng, tính bằng pixel
COLS = 8            # số ô mỗi hàng
PER_SHEET = 48      # số ô mỗi tấm — vừa một màn hình, không phải cuộn
PAD = 26            # chỗ chừa để ghi số thứ tự và giá trị đo


def _key(p: str) -> str:
    return ntpath.splitext(ntpath.basename(p.strip()))[0].lower()


def num(v):
    try:
        return float(str(v).replace("+", "").strip())
    except (TypeError, ValueError):
        return None


def pick_sample(csv_path: Path, n: int, max_faces: int) -> list[dict]:
    """Chọn mẫu TRẢI ĐỀU theo giá trị đo hiện tại, trong phạm vi luật áp dụng."""
    with io.open(csv_path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    cand = []
    for r in rows:
        faces = num(r.get("faces_n")) or 0
        eye = num(r.get("eye_open_min"))
        if eye is None or not (1 <= faces <= max_faces):
            continue
        cand.append({"path": r["path"], "eye": eye, "faces": int(faces),
                     "area": num(r.get("face_area_min"))})
    if not cand:
        return []
    cand.sort(key=lambda r: r["eye"])
    # Trải đều trên dải đã sắp xếp: lấy cách quãng, không lấy cụm đầu
    step = max(1, len(cand) // n)
    return cand[::step][:n]


def eye_crops(path: Path, cfg: dict) -> list[np.ndarray]:
    """Cắt ô quanh từng mắt, đi ĐÚNG đường mà measure() đi.

    Ba bước bắt buộc, bỏ bước nào cũng ra kết quả khác measure():
      1. read_raw()          lấy JPEG nhúng trong ARW
      2. apply_orientation() xoay theo EXIF — ảnh dọc chưa xoay thì YuNet
                             gần như không thấy mặt nào
      3. thumbnail(face_px)  nhận diện ở độ phân giải 1024, không phải 480
    """
    blob, tags = at.read_raw(path)
    if blob is None:
        return []
    im = Image.open(io.BytesIO(blob))
    im.draft("RGB", (cfg["face_px"], cfg["face_px"]))
    im = at.apply_orientation(im.convert("RGB"), tags.get("orientation"))
    im.thumbnail((cfg["face_px"], cfg["face_px"]), Image.BILINEAR)
    arr = np.asarray(im)
    faces = at.detect_faces(im, cfg["face_score"])
    out = []
    for x, y, bw, bh, _s, eyes in faces:
        for ex, ey in (eyes or []):
            r = max(10, int(bw * 0.22))
            x0, y0 = int(max(0, ex - r)), int(max(0, ey - r))
            x1, y1 = int(min(arr.shape[1], ex + r)), int(min(arr.shape[0], ey + r))
            if x1 - x0 < 8 or y1 - y0 < 8:
                continue
            out.append(arr[y0:y1, x0:x1])
    return out


def build(sample: list[dict], cfg: dict, out_dir: Path) -> list[Path]:
    cells = []
    for r in sample:
        p = Path(r["path"])
        try:
            crops = eye_crops(p, cfg)
        except Exception:
            crops = []
        if not crops:
            continue
        # Lấy MỘT mắt cho mỗi ảnh — mắt của khuôn mặt đầu tiên là đủ để chấm,
        # và giữ bảng gọn để người dùng đọc nhanh.
        cells.append({"img": crops[0], "name": p.stem, "eye": r["eye"]})

    sheets = []
    for s in range(0, len(cells), PER_SHEET):
        chunk = cells[s:s + PER_SHEET]
        rows = (len(chunk) + COLS - 1) // COLS
        W = COLS * CELL
        H = rows * (CELL + PAD)
        sheet = Image.new("RGB", (W, H), (24, 24, 26))
        d = ImageDraw.Draw(sheet)
        for i, c in enumerate(chunk):
            cx, cy = (i % COLS) * CELL, (i // COLS) * (CELL + PAD)
            img = Image.fromarray(c["img"]).resize((CELL - 8, CELL - 8), Image.LANCZOS)
            sheet.paste(img, (cx + 4, cy + 4))
            idx = s + i + 1
            d.text((cx + 6, cy + CELL), f"{idx}  {c['name'][-8:]}  do={c['eye']:.2f}",
                   fill=(210, 210, 215))
        dest = out_dir / f"eye_sheet_{s // PER_SHEET + 1:02d}.png"
        sheet.save(dest)
        sheets.append(dest)

    idx_path = out_dir / "eye_sheet_index.csv"
    with io.open(idx_path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["so_thu_tu", "file", "eye_open_min", "nham_mat"])
        for i, c in enumerate(cells, 1):
            w.writerow([i, c["name"], f"{c['eye']:.4f}", ""])
    sheets.append(idx_path)
    return sheets


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Cắt vùng mắt ra bảng để chấm bằng mắt.")
    p.add_argument("folder", type=Path)
    p.add_argument("--csv", type=Path, required=True,
                   help="File CSV do nút 'Xuất CSV' tạo ra")
    p.add_argument("--n", type=int, default=96, help="Số ảnh lấy mẫu")
    p.add_argument("--max-faces", type=int, default=4,
                   help="Chỉ lấy ảnh có tối đa bấy nhiêu mặt (phạm vi luật áp dụng)")
    a = p.parse_args(argv)

    cfg = dict(at.DEFAULTS)
    sample = pick_sample(a.csv, a.n, a.max_faces)
    if not sample:
        print("Không chọn được ảnh nào. Kiểm tra CSV có cột eye_open_min chưa.")
        return 1
    print(f"Chọn {len(sample)} ảnh, trải từ đo={sample[0]['eye']:.2f} "
          f"tới {sample[-1]['eye']:.2f}")
    files = build(sample, cfg, a.folder)
    for f in files:
        print("  ->", f)
    print("\nMở ảnh eye_sheet_*.png, đọc số của những ô MẮT NHẮM,")
    print("rồi điền 1 vào cột 'nham_mat' trong eye_sheet_index.csv.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
