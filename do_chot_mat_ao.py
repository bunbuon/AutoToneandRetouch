#!/usr/bin/env python3
"""Đo tác động thật của chốt chặn báo-mặt-ảo trước khi bật nó.

BỐI CẢNH
    Đối chiếu YuNet với InsightFace trên 400 ảnh buổi 1308: 11 ảnh (2,8%) có
    chủ thể mà InsightFace không coi là khuôn mặt. Xem tận mắt 5 ảnh thì cả 5
    đều là báo ảo — tờ sticker, logo trên màn LED, phông nền, lưng người tiền
    cảnh. Chúng thắng vì TO, dù điểm tin cậy thấp (0,58–0,77) so với mặt thật
    của chủ thể (0,86–0,95).

    Chốt chặn rất đơn giản: bỏ khung có điểm dưới ngưỡng. Nhưng KHÔNG được bật
    bừa — mặt nhỏ ở xa trong ảnh tập thể cũng có điểm thấp, và nếu chốt này ăn
    vào chúng thì cân sáng ảnh tập thể đổi theo, đúng loại thiệt hại âm thầm mà
    dự án này đã mất công tránh.

FILE NÀY ĐO GÌ
    Chạy đúng hàm measure() của autotone HAI LẦN trên cùng một ảnh — một lần
    tắt chốt, một lần bật — rồi báo:
      - bao nhiêu ảnh đổi kết quả, và lệch bao nhiêu EV
      - bao nhiêu ảnh MẤT HẲN khuôn mặt (lùi về đo theo vùng bắt nét)
      - ảnh nào lệch nhiều nhất, để mở ra xem tận mắt
    Không kết luận hộ. Chỉ đưa số và danh sách ảnh cần nhìn.

CÁCH DÙNG
    python do_chot_mat_ao.py "G:\\1308" --nguong 0.80 --n 400
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at   # noqa: E402


def _do(args) -> dict:
    """Đo một ảnh hai lần. Tách ra hàm cấp module để chạy được đa tiến trình."""
    path, cfg, thr = args
    p = Path(path)
    common = (cfg["preview_px"], cfg["meter"], cfg["meter_highlight_cut"],
              cfg["wb"] == "skin", cfg["face_px"], cfg["face_score"],
              cfg["focus_quantile"], cfg["focus_face_gain"],
              cfg.get("face_min_ratio", 0.0), cfg.get("subject_keep", 0.60),
              cfg.get("subject_dark_ev", 2.0))
    off = at.measure(p, *common, 0.0)
    on = at.measure(p, *common, thr)
    if not (off.get("ok") and on.get("ok")):
        return {"file": p.stem, "loi": off.get("error") or on.get("error")}

    def ev(r):
        return r.get("metered_ev")

    def nguon(r):
        if r.get("metered_face_ev") is not None:
            return "mat"
        if r.get("metered_focus_ev") is not None:
            return "net"
        return "khung"

    e0, e1 = ev(off), ev(on)
    return {
        "file": p.stem,
        "mat_truoc": off.get("faces_n") or 0,
        "mat_sau": on.get("faces_n") or 0,
        "bi_loai": on.get("faces_lowconf") or 0,
        "nguon_truoc": nguon(off),
        "nguon_sau": nguon(on),
        "ev_truoc": None if e0 is None else round(e0, 4),
        "ev_sau": None if e1 is None else round(e1, 4),
        "lech_ev": None if (e0 is None or e1 is None) else round(e1 - e0, 4),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Đo tác động của chốt chặn báo mặt ảo.")
    ap.add_argument("folder", type=Path)
    ap.add_argument("--nguong", type=float, default=0.80,
                    help="Điểm tin cậy tối thiểu để coi là mặt thật (mđ: 0.80)")
    ap.add_argument("--n", type=int, default=400, help="Số ảnh lấy mẫu (mđ: 400)")
    ap.add_argument("--jobs", type=int, default=6)
    a = ap.parse_args(argv)

    files = sorted(p for p in a.folder.iterdir() if p.suffix.lower() in at.RAW_EXTS)
    if not files:
        print("Khong thay file RAW nao.")
        return 1
    if len(files) > a.n:                    # trải đều cả buổi, không lấy cụm đầu
        step = len(files) / float(a.n)
        files = [files[int(i * step)] for i in range(a.n)]

    cfg = dict(at.DEFAULTS)
    print(f"Do {len(files)} anh, nguong {a.nguong}, {a.jobs} tien trinh...")
    tasks = [(str(p), cfg, a.nguong) for p in files]
    rows = []
    with ProcessPoolExecutor(max_workers=a.jobs) as ex:
        for i, r in enumerate(ex.map(_do, tasks, chunksize=4), 1):
            rows.append(r)
            if i % 50 == 0:
                print(f"  {i}/{len(files)}")

    ok = [r for r in rows if "loi" not in r]
    dest = a.folder / "chot_mat_ao.csv"
    with io.open(dest, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(ok[0].keys()))
        w.writeheader()
        w.writerows(ok)

    n = len(ok)
    doi = [r for r in ok if r["lech_ev"] not in (None, 0.0)]
    mat_het = [r for r in ok if r["nguon_truoc"] == "mat" and r["nguon_sau"] != "mat"]
    bi = [r for r in ok if r["bi_loai"] > 0]
    lon = sorted((r for r in doi), key=lambda r: -abs(r["lech_ev"]))

    print(f"\n{n} anh do duoc")
    print(f"Anh co khung bi chot chan loai : {len(bi)}  ({100 * len(bi) / n:.1f}%)")
    print(f"Anh DOI ket qua do sang        : {len(doi)}  ({100 * len(doi) / n:.1f}%)")
    print(f"Anh MAT HAN khuon mat          : {len(mat_het)}  "
          f"({100 * len(mat_het) / n:.1f}%)  <- lui ve do theo vung bat net")
    if doi:
        v = sorted(abs(r["lech_ev"]) for r in doi)
        print(f"Lech EV trong so anh doi: trung vi {v[len(v) // 2]:.2f} | "
              f"lon nhat {v[-1]:.2f}")
    print(f"\n-> {dest.name}")
    if lon:
        print("\nMO TAN MAT NHUNG ANH LECH NHIEU NHAT — moi anh tu hoi mot cau:")
        print("khung bi loai co phai mat that khong?\n")
        print(f"{'anh':<12}{'mat':>8}{'nguon':>14}{'lech EV':>10}")
        for r in lon[:20]:
            print(f"{r['file']:<12}{r['mat_truoc']:>4}->{r['mat_sau']:<3}"
                  f"{r['nguon_truoc']:>7}->{r['nguon_sau']:<6}{r['lech_ev']:>10.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
