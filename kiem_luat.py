#!/usr/bin/env python3
"""Kiểm luật chọn chủ thể trên 893 ảnh người dùng đã duyệt — CỔNG của giai đoạn 1.

CÂU HỎI
    Luật "bỏ khung to mà điểm thấp" sửa đúng 4 ảnh đã xem tận mắt. Nhưng nó có
    làm xê dịch những ảnh vốn đã đúng không? Đó mới là câu quyết định có bật
    được hay không, và nó không trả lời được bằng cách nhìn thêm ảnh.

HAI TẬP ẢNH, HAI TIÊU CHÍ KHÁC NHAU
    893 ảnh ĐÃ DUYỆT  người dùng xuất ra và không sửa gì -> tool đã đúng.
                      Luật càng ít đụng vào càng tốt. Đây là tập quan trọng nhất.
    185 ảnh ĐÃ SỬA    người dùng chỉnh tay, nên biết đích đúng là bao nhiêu.
                      Luật phải kéo LẠI GẦN con số đó, hoặc ít nhất không đẩy xa.

CỔNG (đặt trước khi chạy, không nới sau)
    - Dưới 2% trong 893 ảnh đã duyệt bị xê dịch quá 0.30 EV
    - Trong 185 ảnh đã sửa, số ảnh được kéo lại gần phải NHIỀU HƠN số bị đẩy xa
    Không đạt thì để luật tắt vĩnh viễn và ghi lý do — không chỉnh tham số cho vừa.

CHẠY ĐÚNG ĐƯỜNG SẢN PHẨM
    File này gọi analyze() rồi plan() của autotone, hai lượt, chỉ khác nhau đúng
    một tham số. Không dựng lại logic nào — bài học đã trả giá bốn lần trong dự
    án này.

CÁCH DÙNG
    Đứng trong thư mục AutoToneImages, chạy một dòng:

        python kiem_luat.py "G:\\1308"

    Không cần chỉ --export: mặc định lấy file export_*.tsv MỚI NHẤT trong
    AutoTone.lrplugin\\jobs, và corrections.csv nằm cạnh file này.

    LƯU Ý VỀ DẤU XUỐNG DÒNG: PowerShell dùng dấu ` (backtick), Command Prompt
    dùng dấu ^. Viết nhầm loại nào thì shell sẽ coi dấu đó là một tham số và
    báo "unrecognized arguments". Cách chắc ăn nhất là viết trên MỘT dòng như
    trên.
"""
from __future__ import annotations

import argparse
import csv
import io
import ntpath
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at   # noqa: E402


def stem(p) -> str:
    return ntpath.splitext(ntpath.basename(str(p)))[0].strip().lower()


def doc_export(p: Path) -> dict:
    """Ảnh đã xuất -> số sao. Ảnh 1 sao là ảnh bị lọc, không tính vào cổng."""
    out = {}
    with io.open(p, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            try:
                out[stem(r["path"])] = int(float(r.get("Rating") or 0))
            except (TypeError, ValueError):
                out[stem(r["path"])] = 0
    return out


def doc_sua(p: Path) -> dict:
    """Ảnh người dùng sửa tay -> giá trị Exposure họ chọn."""
    out = {}
    with io.open(p, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            try:
                out[stem(r["file"])] = float(r["user_exposure"])
            except (TypeError, ValueError, KeyError):
                continue
    return out


def chay_mot_luot(folder: Path, cfg: dict, jobs: int, export: dict) -> dict:
    """Một lượt phân tích + lập kế hoạch ĐẦY ĐỦ, y hệt lúc chạy thật.

    Truyền cả `export` — thông số catalog — vì thiếu nó thì mốc so sánh khác đi
    và hai lượt không còn so được với nhau.
    """
    catalog = cfg.get("source") == "catalog"
    pairs, thieu = at.collect_pairs(folder, need_sidecar=not catalog)
    if thieu:
        print(f"    ({len(thieu)} anh thieu sidecar, bo qua)")
    t0 = time.time()
    items, failed = at.analyze(pairs, cfg, jobs)
    at.plan(items, cfg, folder, export)
    print(f"    {len(items)} anh do duoc, {len(failed)} loi, {time.time() - t0:.0f}s")
    return {stem(r["path"]): r for r in items}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Kiểm luật chọn chủ thể trên ảnh đã duyệt.")
    ap.add_argument("folder", type=Path)
    #[[ Ca hai duong dan deu co mac dinh, de bot mot nguon go sai.
    #   --export: lay file export_*.tsv moi nhat trong thu muc jobs cua plugin
    #   --sua   : corrections.csv nam canh chinh file nay
    #]]
    ap.add_argument("--export", type=Path, default=None,
                    help="File export_*.tsv do plugin xuất (mđ: file mới nhất "
                         "trong AutoTone.lrplugin/jobs)")
    ap.add_argument("--sua", type=Path, default=None,
                    help="corrections.csv (mđ: nằm cạnh kiem_luat.py)")
    ap.add_argument("--ti-le", type=float, default=3.0, help="big_low_ratio đem thử")
    ap.add_argument("--nguong-lech", type=float, default=0.30,
                    help="Xê dịch quá bấy nhiêu EV thì tính là bị đụng (mđ: 0.30)")
    ap.add_argument("--cong", type=float, default=2.0,
                    help="Cổng: tối đa bao nhiêu %% ảnh đã duyệt được phép bị đụng")
    ap.add_argument("--jobs", type=int, default=0)
    ap.add_argument("--nguon", default="catalog", choices=["catalog", "sidecar"],
                    help="Nguồn thông số gốc — phải TRÙNG với chế độ anh chạy "
                         "thật, nếu không thì hai lượt so với mốc khác nhau "
                         "(mđ: catalog)")
    a = ap.parse_args(argv)

    here = Path(__file__).resolve().parent
    if a.export is None:
        a.export = at.latest_catalog_export(here / "AutoTone.lrplugin" / "jobs")
        if a.export is None:
            print("Khong tim thay file export_*.tsv nao. Chi ro bang --export.")
            return 1
        print(f"Dung file export moi nhat: {a.export.name}")
    if a.sua is None:
        a.sua = here / "corrections.csv"
    for f, ten in ((a.export, "--export"), (a.sua, "--sua")):
        if not Path(f).is_file():
            print(f"Khong thay file {ten}: {f}")
            return 1

    rating = doc_export(a.export)
    sua = doc_sua(a.sua)
    duyet = {k for k, v in rating.items() if v != 1 and k not in sua}
    print(f"Tap kiem: {len(duyet)} anh da duyet | {len(sua)} anh da sua tay\n")

    # So tien trinh: dung dung ham cua autotone de khong an het RAM khi
    # Lightroom dang mo — no tru san 3 GB cho Lightroom.
    jobs = at.safe_jobs(a.jobs or 8, dict(at.DEFAULTS))
    print(f"So tien trinh: {jobs}")
    cfg_tat = dict(at.DEFAULTS, big_low_ratio=0.0, source=a.nguon)
    cfg_bat = dict(at.DEFAULTS, big_low_ratio=a.ti_le, source=a.nguon)
    exp = at.read_catalog_export(a.export) if a.nguon == "catalog" else {}
    print(f"Nguon thong so: {a.nguon} ({len(exp)} anh co trong export)")

    print("Luot 1/2 — luat TAT")
    tat = chay_mot_luot(a.folder, cfg_tat, jobs, exp)
    print("Luot 2/2 — luat BAT")
    bat = chay_mot_luot(a.folder, cfg_bat, jobs, exp)

    rows = []
    for k, r0 in tat.items():
        r1 = bat.get(k)
        if r1 is None:
            continue
        e0, e1 = r0.get("new_exposure"), r1.get("new_exposure")
        if e0 is None or e1 is None:
            continue
        rows.append({
            "file": k, "nhom": "duyet" if k in duyet else ("sua" if k in sua else "khac"),
            "ev_tat": round(float(e0), 4), "ev_bat": round(float(e1), 4),
            "lech": round(float(e1) - float(e0), 4),
            "nguoi_dung": sua.get(k, ""),
        })

    if not rows:
        print("\nKhong ghep duoc anh nao giua hai luot. Kiem tra:")
        print("  - dung thu muc RAW chua")
        print("  - --nguon co dung che do anh van chay khong")
        return 1

    dest = a.folder / "kiem_luat.csv"
    with io.open(dest, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ---------- CỔNG 1: ảnh đã duyệt ----------
    d = [r for r in rows if r["nhom"] == "duyet"]
    dung = [r for r in d if abs(r["lech"]) > a.nguong_lech]
    pct = 100.0 * len(dung) / max(len(d), 1)
    print(f"\n{'=' * 62}\nCONG 1 — 893 anh da duyet")
    print(f"  bi xe dich qua {a.nguong_lech} EV: {len(dung)}/{len(d)}  ({pct:.2f}%)")
    print(f"  cong cho phep: duoi {a.cong}%   -> {'DAT' if pct < a.cong else 'KHONG DAT'}")
    if dung:
        v = sorted(abs(r["lech"]) for r in dung)
        print(f"  bien do trong nhom bi dung: trung vi {v[len(v) // 2]:.2f}, lon nhat {v[-1]:.2f} EV")
        print("  10 anh bi dung manh nhat:")
        for r in sorted(dung, key=lambda r: -abs(r["lech"]))[:10]:
            print(f"     {r['file']:<12} {r['ev_tat']:+.2f} -> {r['ev_bat']:+.2f}  ({r['lech']:+.2f})")

    # ---------- CỔNG 2: ảnh đã sửa tay ----------
    s = [r for r in rows if r["nhom"] == "sua" and r["nguoi_dung"] != ""]
    gan = xa = 0
    for r in s:
        u = float(r["nguoi_dung"])
        if abs(r["ev_bat"] - u) < abs(r["ev_tat"] - u) - 1e-6:
            gan += 1
        elif abs(r["ev_bat"] - u) > abs(r["ev_tat"] - u) + 1e-6:
            xa += 1
    print(f"\nCONG 2 — {len(s)} anh nguoi dung da sua tay")
    print(f"  luat keo LAI GAN gia tri nguoi dung chon: {gan} anh")
    print(f"  luat day RA XA                          : {xa} anh")
    print(f"  -> {'DAT' if gan >= xa else 'KHONG DAT'}")

    ok = pct < a.cong and gan >= xa
    print(f"\n{'=' * 62}")
    print("KET LUAN: " + ("CA HAI CONG DAT — luat bat duoc" if ok else
                          "KHONG DAT — de luat TAT, ghi lai ly do"))
    print(f"-> {dest.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
