#!/usr/bin/env python3
"""Đo độ mở mắt bằng EAR (viền mí thật) và dựng bảng chấm để lấy nhãn.

VÌ SAO CÓ FILE NÀY
    Phép đo cũ (_eye_openness trong autotone) đã bị chính nhãn của người dùng
    bác bỏ: 34 ô mắt được chấm, hai ô nhắm mắt thật (DSC01469, DSC01374) lại
    nằm hạng 15 và 21 trên 34 — tức là nửa TRÊN, phép đo coi chúng mở mắt hơn
    phần lớn ảnh khác. Không cứu được bằng cách chỉnh ngưỡng.

    EAR đo bằng viền mí thật thì xếp đúng hai ảnh đó xuống hạng 1 và 2 trong
    số 20 ảnh thuộc phạm vi luật (1-4 người), cách ảnh kế tiếp một khoảng rõ
    (0.105 so với 0.181). Nhưng MỚI CÓ 2 NHÃN — đủ để tin hướng đi, chưa đủ để
    chốt ngưỡng. File này sinh thêm nhãn để chốt.

HAI TẦNG, VÌ SAO
    FaceMesh tự dò mặt rất kém trên ảnh sự kiện: chạy thẳng chỉ thấy mặt ở 8/35
    ảnh. Nên YuNet (đang dùng sẵn để cân sáng) dò khung mặt trước, cắt khung đó
    từ ảnh xem trước độ phân giải cao rồi mới đưa vào FaceMesh — lúc đó thấy đủ
    35/35.

CÁCH DÙNG
    pip install mediapipe==0.10.14
    python eye_ear.py "G:\\1308"
    -> ear.csv, ear_sheet_01.png ..., ear_sheet_index.csv

    Mở ear_sheet_*.png, đọc số của những ô MẮT NHẮM, điền 1 vào cột nham_mat
    trong ear_sheet_index.csv rồi gửi lại.

LẤY MẪU THẾ NÀO
    Một nửa lấy ở nhóm EAR THẤP NHẤT (nơi mắt nhắm thật sự nằm — chấm ở đây mới
    biết đo có bắt oan không), một nửa TRẢI ĐỀU phần còn lại (để biết có bỏ sót
    không). Chỉ lấy một phía là tự lừa mình.
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at   # noqa: E402

# Chỉ số điểm viền mí trên/dưới và hai khoé mắt trong lưới 468 điểm FaceMesh.
L_EYE = dict(top=[159, 158], bot=[145, 153], l=33, r=133)
R_EYE = dict(top=[386, 385], bot=[374, 380], l=362, r=263)

CROP_PX = 320       # cạnh ô mặt đưa vào FaceMesh
MARGIN = 0.45       # nới khung mặt ra bấy nhiêu lần trước khi cắt
BIG_PX = 3000       # cạnh dài ảnh xem trước dùng để cắt mặt
CELL, COLS, PER_SHEET, PAD = 190, 8, 48, 26

_MESH = None        # mỗi tiến trình con giữ một bản riêng, nạp lúc dùng đầu tiên


def _mesh():
    global _MESH
    if _MESH is None:
        import mediapipe as mp
        _MESH = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=True, max_num_faces=1, refine_landmarks=True,
            min_detection_confidence=0.2)
    return _MESH


def _previews(p: Path, det_px: int):
    blob, tags = at.read_raw(p)
    if blob is None:
        return None, None
    o = tags.get("orientation")
    im = Image.open(io.BytesIO(blob))
    im.draft("RGB", (det_px, det_px))
    det = at.apply_orientation(im.convert("RGB"), o)
    det.thumbnail((det_px, det_px), Image.BILINEAR)

    im2 = Image.open(io.BytesIO(blob))
    im2.draft("RGB", (BIG_PX, BIG_PX))
    big = at.apply_orientation(im2.convert("RGB"), o)
    if max(big.size) > BIG_PX:
        big.thumbnail((BIG_PX, BIG_PX), Image.BILINEAR)
    return det, big


def _ear(lm, w, h, spec):
    def pt(i):
        return np.array([lm[i].x * w, lm[i].y * h])
    horiz = np.linalg.norm(pt(spec["l"]) - pt(spec["r"]))
    if horiz < 1e-6:
        return None, None
    vert = np.mean([np.linalg.norm(pt(a) - pt(b))
                    for a, b in zip(spec["top"], spec["bot"])])
    mid = (pt(spec["l"]) + pt(spec["r"])) / 2.0
    return float(vert / horiz), mid


def measure_one(path_str: str) -> dict:
    """Trả về EAR nhỏ nhất của ảnh, kèm ô mắt đã cắt sẵn để đưa vào bảng chấm."""
    p = Path(path_str)
    out = {"path": path_str, "name": p.stem, "faces": 0, "meshes": 0,
           "ear_min": None, "crop": None}
    try:
        det, big = _previews(p, at.DEFAULTS["face_px"])
        if det is None:
            return out
        faces = at.detect_faces(det, at.DEFAULTS["face_score"])
        out["faces"] = len(faces)
        if not faces:
            return out
        sx = big.size[0] / float(det.size[0])
        sy = big.size[1] / float(det.size[1])
        barr = np.asarray(big)
        best = None
        for x, y, bw, bh, _s, _e in faces:
            cx, cy = (x + bw / 2) * sx, (y + bh / 2) * sy
            r = max(bw * sx, bh * sy) * (0.5 + MARGIN)
            x0, y0 = int(max(0, cx - r)), int(max(0, cy - r))
            x1, y1 = int(min(barr.shape[1], cx + r)), int(min(barr.shape[0], cy + r))
            if x1 - x0 < 40 or y1 - y0 < 40:
                continue
            face = Image.fromarray(barr[y0:y1, x0:x1]).resize(
                (CROP_PX, CROP_PX), Image.BILINEAR)
            res = _mesh().process(np.asarray(face))
            if not res.multi_face_landmarks:
                continue
            out["meshes"] += 1
            lm = res.multi_face_landmarks[0].landmark
            for spec in (L_EYE, R_EYE):
                e, mid = _ear(lm, CROP_PX, CROP_PX, spec)
                if e is None:
                    continue
                if best is None or e < best[0]:
                    best = (e, np.asarray(face), mid)
        if best is not None:
            e, farr, mid = best
            out["ear_min"] = e
            # Ô mắt CĂN THEO ĐIỂM MÍ THẬT — bảng cũ cắt theo 5 điểm của YuNet
            # nên nhiều ô lệch ra cả khuôn mặt, người chấm không nhìn được mắt.
            rr = int(CROP_PX * 0.12)
            ex, ey = int(mid[0]), int(mid[1])
            x0, y0 = max(0, ex - rr), max(0, ey - rr)
            x1, y1 = min(CROP_PX, ex + rr), min(CROP_PX, ey + rr)
            if x1 - x0 >= 8 and y1 - y0 >= 8:
                out["crop"] = farr[y0:y1, x0:x1]
    except Exception as ex:                     # noqa: BLE001
        out["loi"] = f"{type(ex).__name__}: {ex}"
    return out


def sample(rows: list, n_low: int, n_spread: int, max_faces: int) -> list:
    """Nửa lấy ở nhóm EAR thấp nhất, nửa trải đều phần còn lại."""
    ok = [r for r in rows
          if r["ear_min"] is not None and 1 <= r["faces"] <= max_faces]
    ok.sort(key=lambda r: r["ear_min"])
    low = ok[:n_low]
    rest = ok[n_low:]
    step = max(1, len(rest) // n_spread) if rest else 1
    return low + rest[::step][:n_spread]


def band_from_csv(csv_path: Path, lo: float, hi: float, n: int,
                  max_faces: int) -> list:
    """Lấy danh sách ảnh trong một DẢI EAR, đọc từ ear.csv đã đo lần trước.

    Vì sao cần: sau khi chấm xong lượt đầu, chỗ chưa chắc chắn thu về đúng một
    dải hẹp — dưới dải thì gần như ảnh nào cũng hỏng, trên dải thì gần như ảnh
    nào cũng dùng được. Ngưỡng nằm đâu đó trong dải đó. Chấm thêm ở NGOÀI dải
    chỉ tốn công mà không đổi được quyết định.

    Đọc lại từ CSV nên không phải đo lại cả buổi; chỉ đo lại vài chục ảnh trong
    dải để lấy ô mắt dựng bảng.
    """
    with io.open(csv_path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    cand = []
    for r in rows:
        try:
            ear = float(r["ear_min"])
            faces = int(r["so_nguoi"])
        except (TypeError, ValueError, KeyError):
            continue
        if lo <= ear < hi and 1 <= faces <= max_faces:
            cand.append((ear, r["path"]))
    cand.sort()
    if len(cand) > n:
        step = len(cand) / float(n)     # trải đều trong dải, không dồn một đầu
        cand = [cand[int(i * step)] for i in range(n)]
    return [p for _e, p in cand]


def build_sheets(sel: list, out_dir: Path, prefix: str = "ear_sheet") -> list:
    cells = [r for r in sel if r.get("crop") is not None]
    made = []
    for s in range(0, len(cells), PER_SHEET):
        chunk = cells[s:s + PER_SHEET]
        rows_n = (len(chunk) + COLS - 1) // COLS
        sheet = Image.new("RGB", (COLS * CELL, rows_n * (CELL + PAD)), (24, 24, 26))
        d = ImageDraw.Draw(sheet)
        for i, c in enumerate(chunk):
            cx, cy = (i % COLS) * CELL, (i // COLS) * (CELL + PAD)
            img = Image.fromarray(c["crop"]).resize((CELL - 8, CELL - 8), Image.LANCZOS)
            sheet.paste(img, (cx + 4, cy + 4))
            d.text((cx + 6, cy + CELL),
                   f"{s + i + 1}  {c['name'][-8:]}  ear={c['ear_min']:.3f}",
                   fill=(210, 210, 215))
        dest = out_dir / f"{prefix}_{s // PER_SHEET + 1:02d}.png"
        sheet.save(dest)
        made.append(dest)

    idx = out_dir / f"{prefix}_index.csv"
    with io.open(idx, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["so_thu_tu", "file", "ear_min", "so_nguoi", "nham_mat"])
        for i, c in enumerate(cells, 1):
            w.writerow([i, c["name"], f"{c['ear_min']:.4f}", c["faces"], ""])
    made.append(idx)
    return made


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Đo EAR và dựng bảng chấm mắt.")
    ap.add_argument("folder", type=Path)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--n-low", type=int, default=40,
                    help="Số ảnh lấy ở nhóm EAR thấp nhất (mđ: 40)")
    ap.add_argument("--n-spread", type=int, default=40,
                    help="Số ảnh trải đều phần còn lại (mđ: 40)")
    ap.add_argument("--max-faces", type=int, default=4,
                    help="Chỉ xét ảnh tối đa bấy nhiêu người (phạm vi luật)")
    ap.add_argument("--band", default=None, metavar="LO,HI",
                    help="Chỉ dựng bảng chấm cho ảnh có EAR trong dải này, đọc "
                         "lại từ ear.csv (vd: --band 0.077,0.19). Không đo lại "
                         "cả buổi")
    ap.add_argument("--n", type=int, default=48,
                    help="Số ô trong bảng khi dùng --band (mđ: 48)")
    ap.add_argument("--prefix", default=None,
                    help="Tên đầu file bảng chấm (mđ: ear_sheet, hoặc ear_band "
                         "khi dùng --band)")
    a = ap.parse_args(argv)

    #[[ Che do DAI: chi do lai vai chuc anh trong dai can quyet dinh.
    #   Nhanh hon do lai ca buoi hang chuc lan, va nhan thu ve dung cho dang
    #   thieu — chinh la cho ranh gioi giua "gan nhu anh nao cung hong" va
    #   "gan nhu anh nao cung dung duoc".
    #]]
    if a.band:
        lo, hi = (float(v) for v in a.band.split(","))
        csv_path = a.folder / "ear.csv"
        if not csv_path.exists():
            print(f"Chua co {csv_path.name}. Chay lenh khong co --band truoc.")
            return 1
        picked = band_from_csv(csv_path, lo, hi, a.n, a.max_faces)
        if not picked:
            print(f"Khong co anh nao trong dai {lo}-{hi}.")
            return 1
        print(f"Do lai {len(picked)} anh trong dai EAR {lo}-{hi}...")
        rows = [measure_one(p) for p in picked]
        rows.sort(key=lambda r: (r["ear_min"] is None, r["ear_min"] or 0))
        prefix = a.prefix or "ear_band"
        made = build_sheets(rows, a.folder, prefix)
        for f in made:
            print("  ->", f.name)
        print(f"\nMo {prefix}_*.png, doc so cua nhung o MAT NHAM,")
        print(f"dien 1 vao cot 'nham_mat' trong {prefix}_index.csv roi gui lai.")
        return 0

    files = sorted(str(p) for p in a.folder.iterdir()
                   if p.suffix.lower() in at.RAW_EXTS)
    if not files:
        print("Khong thay file RAW nao trong thu muc.")
        return 1
    print(f"Do EAR tren {len(files)} anh, {a.jobs} tien trinh...")

    rows = []
    if a.jobs > 1:
        with ProcessPoolExecutor(max_workers=a.jobs) as ex:
            for i, r in enumerate(ex.map(measure_one, files, chunksize=4), 1):
                rows.append(r)
                if i % 100 == 0:
                    print(f"  {i}/{len(files)}")
    else:
        for i, f in enumerate(files, 1):
            rows.append(measure_one(f))
            if i % 100 == 0:
                print(f"  {i}/{len(files)}")

    csv_path = a.folder / "ear.csv"
    with io.open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["path", "file", "so_nguoi", "so_mat_do_duoc", "ear_min", "loi"])
        for r in rows:
            w.writerow([r["path"], r["name"], r["faces"], r["meshes"],
                        "" if r["ear_min"] is None else f"{r['ear_min']:.4f}",
                        r.get("loi", "")])

    sel = sample(rows, a.n_low, a.n_spread, a.max_faces)
    made = build_sheets(sel, a.folder, a.prefix or "ear_sheet")
    done = sum(1 for r in rows if r["ear_min"] is not None)
    print(f"\nDo duoc {done}/{len(rows)} anh -> {csv_path.name}")
    for f in made:
        print("  ->", f.name)
    print("\nMo ear_sheet_*.png, doc so cua nhung o MAT NHAM,")
    print("dien 1 vao cot 'nham_mat' trong ear_sheet_index.csv roi gui lai.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
