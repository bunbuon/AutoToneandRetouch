#!/usr/bin/env python3
"""So sánh HAI bộ dò mặt trên cùng một tập ảnh: YuNet (AutoTone) vs InsightFace
(ToolCloneEvoto).

VÌ SAO CẦN CHẠY THAY VÌ ĐỌC THÔNG SỐ
    Hai bên đã có số đo, nhưng đo trên hai thứ khác nhau: TOC_DO.md đo tốc độ
    InsightFace trên 14 ảnh JPEG đã xuất, còn AutoTone đo YuNet trên preview
    nhúng trong ARW. Không so trực tiếp được. File này bắt cả hai đọc CÙNG một
    ảnh, CÙNG một độ phân giải, rồi mới đếm.

    Ba câu hỏi cần trả lời, không phải một:
      1. InsightFace có tìm được mặt mà YuNet bỏ sót không, và ngược lại?
      2. Hai bên có chọn CÙNG một chủ thể không? Đây mới là câu quan trọng với
         AutoTone: cân sáng bám vào khuôn mặt nặng ký nhất, chọn nhầm là lệch
         cả ảnh (đã gặp: DSC01306, 7 mặt, chọn nhầm -> lệch 5.91 EV).
      3. Đếm số người có đổi không? Luật lọc mắt chỉ áp dụng cho ảnh 1-4 người
         — đổi bộ dò mặt là đổi luôn phạm vi áp dụng của luật.

    KHÔNG trả lời được câu "bên nào đúng hơn", vì không có nhãn thật số người
    trong mỗi ảnh. File này chỉ đo ĐỘ LỆCH giữa hai bên và chỉ ra đúng những
    ảnh đáng mở ra xem bằng mắt.

CÁCH DÙNG
    python so_sanh_do_mat.py "G:\\1308" --n 200
    -> so_sanh_do_mat.csv  +  danh sách ảnh lệch nhiều nhất để xem tận mắt
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at   # noqa: E402


def load_preview(p: Path, px: int):
    """Đi ĐÚNG đường AutoTone đi: JPEG nhúng -> xoay theo EXIF -> thu nhỏ."""
    blob, tags = at.read_raw(p)
    if blob is None:
        return None
    im = Image.open(io.BytesIO(blob))
    im.draft("RGB", (px, px))
    im = at.apply_orientation(im.convert("RGB"), tags.get("orientation"))
    im.thumbnail((px, px), Image.BILINEAR)
    return im


def yunet_faces(im: Image.Image, score: float):
    """(x, y, w, h, score) — gọi thẳng hàm AutoTone đang dùng, không viết lại."""
    return [(f[0], f[1], f[2], f[3], f[4]) for f in at.detect_faces(im, score)]


_APP = None


def insight_faces(im: Image.Image, det_side: int, thresh: float):
    """(x, y, w, h) — dựng InsightFace y hệt skin_spike4.py của ToolCloneEvoto."""
    global _APP
    if _APP is None:
        from insightface.app import FaceAnalysis
        _APP = FaceAnalysis(name="buffalo_l",
                            allowed_modules=["detection", "landmark_2d_106"])
        _APP.prepare(ctx_id=0, det_size=(det_side, det_side), det_thresh=thresh)
    bgr = np.asarray(im.convert("RGB"))[:, :, ::-1].copy()
    out = []
    for f in _APP.get(bgr):
        x0, y0, x1, y1 = (float(v) for v in f.bbox)
        out.append((x0, y0, x1 - x0, y1 - y0, float(getattr(f, "det_score", 1.0))))
    return out


def iou(a, b) -> float:
    # Chi lay 4 so dau: khung mat con mang them diem tin cay o cuoi
    ax, ay, aw, ah = a[:4]
    bx, by, bw, bh = b[:4]
    x0, y0 = max(ax, bx), max(ay, by)
    x1, y1 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    inter = (x1 - x0) * (y1 - y0)
    return inter / (aw * ah + bw * bh - inter)


def weight(f) -> float:
    """Trọng số chọn chủ thể — ĐÚNG công thức AutoTone dùng: sqrt(diện tích) x điểm.

    Bản đầu của file này so hai khuôn mặt TO NHẤT. Sai, và tôi phải sửa: AutoTone
    không chọn mặt to nhất, nó chọn mặt nặng ký nhất, trong đó điểm tin cậy của
    bộ dò mặt cũng có tiếng nói. So sai thứ thì kết luận cũng sai thứ.
    """
    return float((f[2] * f[3]) ** 0.5 * (f[4] if len(f) > 4 else 1.0))


def subject(faces):
    return max(faces, key=weight) if faces else None


def tie_ratio(faces) -> float:
    """Tỉ lệ trọng số mặt nhì / mặt nhất. Gần 1 = hoà, đổi bên nào cũng như nhau."""
    if len(faces) < 2:
        return 0.0
    w = sorted((weight(f) for f in faces), reverse=True)
    return w[1] / w[0] if w[0] > 0 else 0.0


def best_iou(box, faces) -> float:
    """IoU cao nhất giữa `box` và BẤT KỲ mặt nào bên kia.

    Đây mới là câu hỏi đúng: chủ thể AutoTone đang bám vào có được bên kia công
    nhận là một khuôn mặt KHÔNG — chứ không phải hai bên có cùng gọi tên một
    người là "to nhất" hay không. Bằng 0 nghĩa là AutoTone đang đo sáng trên một
    thứ mà bộ dò mặt kia không coi là mặt.
    """
    return max((iou(box, f) for f in faces), default=0.0)


def scope(n: int, lo=1, hi=4) -> bool:
    """Ảnh có thuộc phạm vi luật lọc mắt không (1-4 người)."""
    return lo <= n <= hi


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="So sánh YuNet vs InsightFace.")
    ap.add_argument("folder", type=Path)
    ap.add_argument("--n", type=int, default=200, help="Số ảnh lấy mẫu (mđ: 200)")
    ap.add_argument("--px", type=int, default=None,
                    help=f"Cạnh dài ảnh đưa vào cả hai (mđ: {at.DEFAULTS['face_px']})")
    ap.add_argument("--det-side", type=int, default=1024,
                    help="det_size của InsightFace (mđ: 1024, như ToolCloneEvoto)")
    ap.add_argument("--det-thresh", type=float, default=0.30,
                    help="Ngưỡng InsightFace (mđ: 0.30, như skin_spike4)")
    a = ap.parse_args(argv)
    px = a.px or at.DEFAULTS["face_px"]

    files = sorted(p for p in a.folder.iterdir() if p.suffix.lower() in at.RAW_EXTS)
    if not files:
        print("Khong thay file RAW nao.")
        return 1
    if len(files) > a.n:                       # trải đều cả buổi, không lấy cụm đầu
        step = len(files) / float(a.n)
        files = [files[int(i * step)] for i in range(a.n)]
    print(f"So sanh tren {len(files)} anh, ca hai cung doc preview {px}px\n")

    rows, t_y, t_i = [], 0.0, 0.0
    for i, p in enumerate(files, 1):
        im = load_preview(p, px)
        if im is None:
            continue
        t0 = time.time()
        fy = yunet_faces(im, at.DEFAULTS["face_score"])
        t_y += time.time() - t0
        t0 = time.time()
        try:
            fi = insight_faces(im, a.det_side, a.det_thresh)
        except Exception as ex:               # noqa: BLE001
            print(f"[!] InsightFace loi: {ex}")
            return 1
        t_i += time.time() - t0

        sy, si = subject(fy), subject(fi)
        #[[ BA CON SO, KHONG PHAI MOT — vi co ba kieu "lech" khac han nhau.
        #
        #   cong_nhan : chu the AutoTone dang bam vao co duoc InsightFace coi la
        #               mot khuon mat khong. Bang 0 = AutoTone dang do sang tren
        #               mot thu KHONG PHAI MAT (gap that: SAY02506 do sang tren
        #               phong nen). Day la loi nang nhat.
        #   hoa       : mat nhi / mat nhat theo trong so. Gan 1 nghia la hai mat
        #               nang ky ngang nhau, ai "thang" cung khong quan trong —
        #               phan lon truong hop hai ben "chon khac chu the" chi la
        #               the, khong phai loi.
        #   cung_nguoi: hai ben co cung goi ten mot nguoi la chu the khong.
        #]]
        rows.append({
            "file": p.stem,
            "yunet": len(fy),
            "insight": len(fi),
            "cong_nhan": f"{best_iou(sy, fi):.3f}" if (sy and fi) else "",
            "hoa": f"{tie_ratio(fy):.3f}",
            "cung_nguoi": f"{iou(sy, si):.3f}" if (sy and si) else "",
            "doi_pham_vi": int(scope(len(fy)) != scope(len(fi))),
        })
        if i % 25 == 0:
            print(f"  {i}/{len(files)}")

    dest = a.folder / "so_sanh_do_mat.csv"
    with io.open(dest, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    n = len(rows)
    ty = sum(r["yunet"] for r in rows)
    ti = sum(r["insight"] for r in rows)
    only_i = sum(1 for r in rows if r["yunet"] == 0 and r["insight"] > 0)
    only_y = sum(1 for r in rows if r["insight"] == 0 and r["yunet"] > 0)
    doi = [r for r in rows if r["doi_pham_vi"]]

    def f(r, k):
        return float(r[k]) if r[k] else 0.0

    # Chu the AutoTone chon KHONG duoc InsightFace coi la mat -> nghi bao mat ao
    ao = [r for r in rows if r["cong_nhan"] and f(r, "cong_nhan") < 0.2]
    # Hai ben goi ten hai nguoi khac nhau NHUNG hai nguoi do nang ky ngang nhau
    hoa = [r for r in rows if r["cung_nguoi"] and f(r, "cung_nguoi") < 0.3
           and f(r, "hoa") >= 0.85]
    # Khac chu the THAT SU: khong phai hoa, va chu the van duoc cong nhan la mat
    that = [r for r in rows if r["cung_nguoi"] and f(r, "cung_nguoi") < 0.3
            and f(r, "hoa") < 0.85 and f(r, "cong_nhan") >= 0.2]

    print(f"\n{'':<28}{'YuNet':>10}{'InsightFace':>14}")
    print(f"{'Tong khuon mat':<28}{ty:>10}{ti:>14}")
    print(f"{'Giay/anh':<28}{t_y / n:>10.3f}{t_i / n:>14.3f}")
    print(f"\nAnh chi InsightFace thay mat  : {only_i}")
    print(f"Anh chi YuNet thay mat        : {only_y}")
    print(f"Doi pham vi luat 1-4 nguoi    : {len(doi)}/{n} "
          f"({100 * len(doi) / n:.1f}%)")
    print(f"\nCHU THE AutoTone dang bam vao:")
    print(f"  InsightFace KHONG coi la mat: {len(ao)}/{n} "
          f"({100 * len(ao) / n:.1f}%)   <- NANG NHAT, nghi do sang tren vat the")
    print(f"  Khac nguoi nhung HOA (>=0.85): {len(hoa)}/{n} "
          f"({100 * len(hoa) / n:.1f}%)   <- vo hai, hai mat nang ky ngang nhau")
    print(f"  Khac nguoi THAT SU           : {len(that)}/{n} "
          f"({100 * len(that) / n:.1f}%)")
    print(f"\n-> {dest.name}")
    if ao:
        print("\nMO TAN MAT NHUNG ANH NAY TRUOC — day la cho AutoTone co the dang")
        print("do sang tren mot thu khong phai khuon mat:")
        for r in ao[:15]:
            print(f"   {r['file']}  YuNet {r['yunet']} mat / "
                  f"InsightFace {r['insight']} mat  cong_nhan={r['cong_nhan']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
