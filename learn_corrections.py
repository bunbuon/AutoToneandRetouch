#!/usr/bin/env python3
"""Thu thập những chỗ người dùng sửa tay sau khi autotone đã áp.

VÌ SAO CẦN
    face_target_ev là MỘT hằng số áp cho mọi ảnh. Hiệu chỉnh nó bằng tay thì
    mỗi lần chỉ dựa được vào một hai tấm, mà một tấm không đại diện cho cả
    buổi chụp — đã có ca đổi mốc theo một ảnh làm lệch cả loạt.

    File này nhặt TẤT CẢ những chỗ người dùng sửa khác tool, kèm bối cảnh của
    từng ảnh, rồi gộp lại thành mốc riêng cho từng LOẠI CẢNH. Không đoán, không
    mô hình hộp đen — chỉ là trung vị của những gì người dùng đã thực sự làm.

TÍN HIỆU LẤY TỪ ĐÂU
    Không cần thêm gì vào plugin. Ba file đã có sẵn trong pipeline:

      jobs/apply_*.done   tool ĐÃ ghi gì vào catalog
      jobs/export_*.tsv   catalog HIỆN ĐANG có gì  (chạy "AutoTone: xuất thông
                          số" SAU khi sửa tay xong)
      autotone*.csv       bối cảnh: metered_ev, cháy trước, ISO, cảnh, ghi chú

    Ảnh nào export khác apply -> đó là chỗ người dùng đã sửa.

CÔNG THỨC
    Giống hệt --calibrate, chỉ khác là gộp theo nhóm thay vì từng ảnh:
        mốc phù hợp = metered_ev + Exposure người dùng chốt
    Lấy TRUNG VỊ trong nhóm để một hai ảnh cá biệt không lôi cả nhóm đi.

CÁCH DÙNG
    python learn_corrections.py "G:\\1308" --csv autotone20260831_1514.csv
    python learn_corrections.py --report          # xem tổng hợp mọi buổi đã thu
"""

from __future__ import annotations

import argparse
import csv
import io
import ntpath
import os
import statistics
import sys
from datetime import datetime
from pathlib import Path

import duong_dan as dd

LR_PLUGIN_DIR = dd.plugin()
LR_JOB_DIR = LR_PLUGIN_DIR / "jobs"
STORE = dd.du_lieu("corrections.csv")

# Dưới mức này coi như làm tròn, không phải người dùng sửa thật.
MIN_DELTA_EV = 0.05
# Nhóm ít hơn ngần này ca thì KHÔNG đề xuất mốc — thà không nói còn hơn nói bừa.
MIN_SAMPLES = 8

STORE_COLS = ["shot", "file", "when", "scene", "iso", "faces",
              "metered_ev", "target_ev", "clip_before", "clip_after",
              "tool_exposure", "user_exposure", "sua_bao_nhieu",
              "implied_target", "bucket", "da_sua", "notes"]


# ---------------------------------------------------------------- đọc file

def _key(p: str) -> str:
    """Khoá so khớp. Đường dẫn trong file là của Windows nên phải dùng ntpath;
    Path().stem trên Linux không tách được dấu gạch ngược."""
    return ntpath.splitext(ntpath.basename(p.strip()))[0].lower()


def read_tsv(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out
    lines = [ln for ln in lines if ln and not ln.startswith("#")]
    if not lines:
        return out
    cols = lines[0].split("\t")
    for ln in lines[1:]:
        v = ln.split("\t")
        if not v or not v[0]:
            continue
        out[_key(v[0])] = {cols[i]: v[i] for i in range(1, min(len(cols), len(v)))}
    return out


def read_csv_ctx(path: Path) -> dict[str, dict]:
    try:
        with io.open(path, encoding="utf-8-sig", newline="") as fh:
            return {_key(r["path"]): r for r in csv.DictReader(fh) if r.get("path")}
    except OSError:
        return {}


def num(v, default=None):
    try:
        return float(str(v).replace("+", "").strip())
    except (TypeError, ValueError):
        return default


def newest(pattern: str, job_dir: Path) -> Path | None:
    files = sorted(job_dir.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


# ---------------------------------------------------------------- phân nhóm

def bucket_of(clip_before: float | None, metered: float | None) -> str:
    """Chia theo ĐIỀU KIỆN CHỤP, không theo nội dung ảnh.

    Hai trục này chọn vì chúng đúng là hai trục mà lỗi đã xuất hiện thật:
    DSC01374 hỏng vì nền cháy nặng, DSC01078 hỏng vì mặt đo sai. Thêm trục
    nữa thì mỗi nhóm còn quá ít ca để nói được gì.
    """
    if clip_before is None or metered is None:
        return "khong-ro"
    if clip_before >= 20.0:
        return "nen-chay-nang"
    if metered <= -2.0:
        return "nguoc-sang"
    if clip_before >= 5.0:
        return "nen-sang"
    return "thuong"


# ---------------------------------------------------------------- thu thập

def collect(shot: str, job_dir: Path, csv_path: Path | None,
            export_path: Path | None = None) -> list[dict]:
    export = read_tsv(export_path or newest("export_*.tsv", job_dir) or Path("x"))
    if not export:
        raise SystemExit(
            "Không thấy bản xuất từ catalog.\n"
            "Trong Lightroom: chọn ảnh -> Library -> Plug-in Extras ->\n"
            "  \"AutoTone: xuất thông số cho autotone\"\n"
            "Phải chạy SAU khi đã sửa tay xong.")

    # Gộp mọi job đã áp, mới đè cũ — ảnh có thể nằm trong nhiều job
    applied: dict[str, dict] = {}
    jobs = sorted(job_dir.glob("apply_*.done"), key=lambda p: p.stat().st_mtime)
    for jp in jobs:
        applied.update(read_tsv(jp))
    if not applied:
        raise SystemExit(f"Không có job nào đã áp trong {job_dir}")

    ctx = read_csv_ctx(csv_path) if csv_path else {}

    rows = []
    for k, cur in export.items():
        job = applied.get(k)
        if not job:
            continue                      # ảnh không nằm trong job nào
        tool_exp = num(job.get("Exposure2012"))
        user_exp = num(cur.get("Exposure2012"))
        if tool_exp is None or user_exp is None:
            continue
        diff = user_exp - tool_exp
        #[[ GIỮ CẢ ẢNH KHÔNG SỬA. Đây là chỗ dễ sai nhất của cả file.
        #
        #   Ảnh người dùng KHÔNG động vào cũng là một phán quyết: "tool đúng
        #   rồi". Tính mốc chỉ từ ảnh bị sửa thì đương nhiên ra mốc lệch, vì
        #   toàn bộ mẫu là những ca tool làm sai.
        #
        #   Đo thật trên buổi 1308: chỉ tính 185 ảnh bị sửa thì ra mốc −1.42
        #   cho nhóm "thuong"; tính cả 532 ảnh của nhóm đó thì ra đúng −1.19,
        #   tức mốc đang dùng KHÔNG sai. Nghe theo con số đầu là phá 893 ảnh
        #   đã được duyệt để chiều 185 ảnh bị sửa.
        #]]
        sua = abs(diff) >= MIN_DELTA_EV

        c = ctx.get(k, {})
        metered = num(c.get("metered_ev"))
        clip_b = num(c.get("clip_before_pct"))
        rows.append({
            "shot": shot,
            "file": k,
            "when": datetime.now().strftime("%Y-%m-%d"),
            "scene": c.get("scene", ""),
            "iso": c.get("iso", ""),
            "faces": c.get("faces_n", ""),
            "metered_ev": f"{metered:.4f}" if metered is not None else "",
            "target_ev": c.get("target_ev", ""),
            "clip_before": f"{clip_b:.2f}" if clip_b is not None else "",
            "clip_after": c.get("clip_after_pct", ""),
            "tool_exposure": f"{tool_exp:.4f}",
            "user_exposure": f"{user_exp:.4f}",
            "sua_bao_nhieu": f"{diff:+.4f}",
            # Mốc mà chính ảnh này ngụ ý — công thức của --calibrate
            "implied_target": f"{metered + user_exp:.4f}" if metered is not None else "",
            "bucket": bucket_of(clip_b, metered),
            "da_sua": "1" if sua else "0",
            "notes": c.get("notes", ""),
        })
    return rows


def save(rows: list[dict], store: Path) -> int:
    """Ghi nối vào kho. Trùng (buổi, file) thì bản mới thắng."""
    old: dict[tuple, dict] = {}
    if store.is_file():
        with io.open(store, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                old[(r.get("shot", ""), r.get("file", ""))] = r
    before = len(old)
    for r in rows:
        old[(r["shot"], r["file"])] = r
    with io.open(store, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=STORE_COLS, extrasaction="ignore")
        w.writeheader()
        for _, r in sorted(old.items()):
            w.writerow(r)
    return len(old) - before


# ---------------------------------------------------------------- báo cáo

def report(store: Path) -> None:
    if not store.is_file():
        print("Chưa thu được ca nào. Chạy lệnh thu thập trước.")
        return
    with io.open(store, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        print("Kho rỗng.")
        return

    shots = sorted({r["shot"] for r in rows})
    nf = sum(1 for r in rows if r.get("da_sua") == "1")
    print(f"\n{len(rows)} ảnh đã thu, {nf} ảnh bạn sửa tay, "
          f"từ {len(shots)} buổi: {', '.join(shots)}")

    by: dict[str, list[dict]] = {}
    for r in rows:
        by.setdefault(r["bucket"], []).append(r)

    print(f"\n{'nhom':16}{'tong':>7}{'da sua':>8}{'sua trung vi':>14}"
          f"{'moc hien tai':>14}{'moc de xuat':>13}")
    print("-" * 72)
    order = ["thuong", "nen-sang", "nguoc-sang", "nen-chay-nang", "khong-ro"]
    for b in order + [k for k in by if k not in order]:
        g = by.get(b)
        if not g:
            continue
        fixed = [r for r in g if r.get("da_sua") == "1"]
        n_fix = len(fixed)
        diffs = [num(r["sua_bao_nhieu"]) for r in fixed] or [0.0]
        diffs = [d for d in diffs if d is not None] or [0.0]
        # Moc tinh tren MOI anh trong nhom, khong chi anh bi sua — xem ghi chu
        # o cho gan bien "sua" trong collect().
        imp = [num(r["implied_target"]) for r in g]
        imp = [d for d in imp if d is not None]
        cur = [num(r["target_ev"]) for r in g]
        cur = [d for d in cur if d is not None]
        cur_s = f"{statistics.median(cur):+.2f}" if cur else "?"
        if len(imp) >= MIN_SAMPLES:
            sug = f"{statistics.median(imp):+.2f}"
        else:
            sug = f"can {MIN_SAMPLES - len(imp)} ca nua"
        print(f"{b:16}{len(g):>7}{n_fix:>8}{statistics.median(diffs):>+14.2f}"
              f"{cur_s:>14}{sug:>13}")

    print(f"\nChi de xuat moc khi nhom co tu {MIN_SAMPLES} ca tro len.")
    print("Cot 'sua trung vi' AM nghia la ban thuong keo TOI hon tool.")
    print("Cot 'moc de xuat' tinh tren TOAN BO anh trong nhom, ke ca anh ban")
    print("khong sua — vi anh khong sua cung la mot phan quyet: tool dung roi.")

    strong = sorted([r for r in rows if r.get("da_sua") == "1"],
                    key=lambda r: -abs(num(r["sua_bao_nhieu"]) or 0))[:10]
    print(f"\n10 ca sua manh tay nhat:")
    print(f"  {'file':14}{'nhom':16}{'tool':>8}{'ban chot':>10}{'lech':>8}")
    for r in strong:
        print(f"  {r['file']:14}{r['bucket']:16}{num(r['tool_exposure']):>+8.2f}"
              f"{num(r['user_exposure']):>+10.2f}{num(r['sua_bao_nhieu']):>+8.2f}")


# ---------------------------------------------------------------- CLI

def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Thu thập chỗ người dùng sửa tay sau khi autotone áp xong.")
    p.add_argument("folder", nargs="?", type=Path,
                   help="Thư mục buổi chụp (chỉ dùng để đặt tên buổi)")
    p.add_argument("--csv", type=Path, default=None,
                   help="File CSV do nút 'Xuất CSV' tạo ra — lấy bối cảnh từ đây")
    p.add_argument("--export", type=Path, default=None,
                   help="Chỉ định file export_*.tsv (mặc định lấy bản mới nhất)")
    p.add_argument("--jobs", type=Path, default=LR_JOB_DIR, help="Thư mục jobs")
    p.add_argument("--store", type=Path, default=STORE, help="Kho tích luỹ")
    p.add_argument("--report", action="store_true", help="Chỉ xem tổng hợp")
    a = p.parse_args(argv)

    if a.report:
        report(a.store)
        return 0
    if not a.folder:
        p.error("thiếu thư mục buổi chụp (hoặc dùng --report)")

    shot = a.folder.name or str(a.folder)
    rows = collect(shot, a.jobs, a.csv, a.export)
    if not rows:
        print("Không ghép được ảnh nào giữa bản xuất và job đã áp.\n"
              "Kiểm tra đã chạy 'AutoTone: xuất thông số' SAU khi sửa chưa.")
        return 0
    added = save(rows, a.store)
    nf = sum(1 for r in rows if r["da_sua"] == "1")
    print(f"Thu được {len(rows)} ảnh ở buổi {shot}, trong đó {nf} ảnh bạn sửa tay "
          f"({added} dòng mới).")
    print(f"Kho: {a.store}")
    report(a.store)
    return 0


if __name__ == "__main__":
    sys.exit(main())
