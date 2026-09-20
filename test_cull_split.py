#!/usr/bin/env python3
"""Kiểm tra hai bộ lọc TRÙNG KHUNG và NHẮM MẮT là độc lập với nhau.

Vì sao phải có test này: đã từng suýt lấy nhãn của bộ lọc này đi kiểm chứng bộ
lọc kia (377 ảnh 1 sao buổi 1308 là do lọc trùng khung gán, không phải người
dùng chấm nhắm mắt). Test khoá lại điều kiện để chuyện đó không tái diễn:
mỗi ảnh bị loại phải mang đúng MỘT lý do, ghi rõ trong cột cull.
"""
import csv
import io
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at

T0 = datetime(2026, 8, 31, 10, 0, 0)


def mk(i, *, secs, faces=1, eye=2.0, sharp=0.8, area=5.0, score=0.95, sig=None):
    return {
        "path": f"IMG_{i:04d}.ARW",
        "dt_obj": T0 + timedelta(seconds=secs),
        "scene_sig": sig or [1.0] * 72,
        "faces_n": faces, "eyes_measured": faces,
        "eye_open": eye, "eye_open_min": eye,
        "eye_min_area": area, "eye_min_score": score,
        "face_sharp": sharp, "notes": "",
    }


def fails(msg):
    print("  KHONG DAT:", msg)
    return 1


def write_ear(tmp: Path, rows) -> Path:
    """Dựng một ear.csv giả lập đúng định dạng eye_ear.py sinh ra."""
    p = tmp / "ear.csv"
    with io.open(p, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["path", "file", "so_nguoi", "so_mat_do_duoc", "ear_min", "loi"])
        for name, faces, ear in rows:
            w.writerow([f"X:\\anh\\{name}.ARW", name, faces, faces,
                        "" if ear is None else f"{ear:.4f}", ""])
    return p


def t_blink_off_by_default():
    """Mặc định phải TẮT, và không có ear.csv thì từ chối chạy."""
    bad = 0
    if at.DEFAULTS["blink"] is not False:
        bad += fails("blink phai mac dinh False")
    with tempfile.TemporaryDirectory() as td:
        items = [mk(1, secs=0)]
        items[0]["path"] = "IMG_0001.ARW"
        cfg = dict(at.DEFAULTS, blink=True)
        n = at.pick_blinks(items, cfg, Path(td))     # thư mục trống, không có ear.csv
        if n != 0 or items[0].get("cull"):
            bad += fails("khong co ear.csv ma van loai anh — phai tu choi chay")
    # và không được âm thầm quay về phép đo cũ
    with tempfile.TemporaryDirectory() as td:
        items = [mk(1, secs=0, eye=0.001)]          # eye_open_min cực thấp
        items[0]["path"] = "IMG_0001.ARW"
        at.pick_blinks(items, dict(at.DEFAULTS, blink=True), Path(td))
        if items[0].get("cull"):
            bad += fails("khong co ear.csv ma van dung eye_open_min de loai")
    return bad


def t_group_rule():
    """Ảnh 1 người và nhóm 2-4 thì loại; tập thể đông người thì không."""
    bad = 0
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        cases = [(1, True), (2, True), (4, True), (5, False), (12, False)]
        write_ear(tmp, [(f"IMG_{f}", f, 0.05) for f, _ in cases])
        cfg = dict(at.DEFAULTS, blink=True, blink_thresh=0.12)
        for faces, want in cases:
            it = [mk(1, secs=0, faces=faces)]
            it[0]["path"] = f"X:\\anh\\IMG_{faces}.ARW"
            at.pick_blinks(it, cfg, tmp)
            got = it[0].get("cull") == "nham-mat"
            if got != want:
                bad += fails(f"{faces} nguoi: loai={got}, mong doi={want}")
    return bad


def t_threshold():
    """Đúng ngưỡng 0.12: dưới thì loại, bằng hoặc trên thì giữ."""
    bad = 0
    if abs(at.DEFAULTS["blink_thresh"] - 0.12) > 1e-9:
        bad += fails("nguong mac dinh phai la 0.12 (hieu chuan tren 93 nhan that)")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        cases = [("A", 0.1199, True), ("B", 0.1200, False), ("C", 0.30, False)]
        write_ear(tmp, [(n, 1, e) for n, e, _ in cases])
        cfg = dict(at.DEFAULTS, blink=True)
        for name, _e, want in cases:
            it = [mk(1, secs=0)]
            it[0]["path"] = f"X:\\anh\\{name}.ARW"
            at.pick_blinks(it, cfg, tmp)
            got = it[0].get("cull") == "nham-mat"
            if got != want:
                bad += fails(f"{name}: loai={got}, mong doi={want}")
    return bad


def t_unmeasured_photo():
    """Ảnh không có trong ear.csv thì KHÔNG kết luận, không loại bừa."""
    bad = 0
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        write_ear(tmp, [("KHAC", 1, 0.02)])
        it = [mk(1, secs=0)]
        it[0]["path"] = "X:\\anh\\CHUA_DO.ARW"
        at.pick_blinks(it, dict(at.DEFAULTS, blink=True), tmp)
        if it[0].get("cull"):
            bad += fails("anh chua do EAR ma van bi loai")
    return bad


def t_match_by_name():
    """Khớp theo TÊN FILE, không theo đường dẫn — ear.csv có thể sinh ở máy khác."""
    bad = 0
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        write_ear(tmp, [("DSC01534", 1, 0.03)])
        it = [mk(1, secs=0)]
        it[0]["path"] = "G:\\buoi-khac\\DSC01534.ARW"   # ổ khác, thư mục khác
        at.pick_blinks(it, dict(at.DEFAULTS, blink=True), tmp)
        if it[0].get("cull") != "nham-mat":
            bad += fails("khong khop duoc khi duong dan khac")
    return bad


def t_burst_never_labels_blink():
    """Lọc trùng khung chỉ được gắn nhãn 'loat', không bao giờ gắn nhãn nhắm mắt."""
    bad = 0
    items = [mk(i, secs=i * 0.5, eye=2.0 - i * 0.1) for i in range(6)]
    at.group_bursts(items, 3.0, 0.12, 3)
    at.pick_burst(items, 2, 1, 0.6)
    culled = [r for r in items if r.get("cull")]
    if not culled:
        bad += fails("loc loat khong loai duoc anh nao — kich ban test sai")
    for r in culled:
        if r["cull"] != "loat" or "nham-mat" in r["notes"]:
            bad += fails(f"{r['path']}: loc loat gan nhan sai -> {r['cull']} / {r['notes']}")
    return bad


def t_one_reason_only():
    """Ảnh đã bị loại vì trùng khung thì lọc mắt không ghi đè lý do."""
    bad = 0
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        items = [mk(i, secs=i * 0.5) for i in range(6)]
        for i, r in enumerate(items):
            r["path"] = f"X:\\anh\\IMG_{i:04d}.ARW"
        write_ear(tmp, [(f"IMG_{i:04d}", 1, 0.05) for i in range(6)])  # cả loạt đều hỏng
        cfg = dict(at.DEFAULTS, burst=True, blink=True)
        at.group_bursts(items, 3.0, 0.12, 3)
        at.pick_burst(items, 2, 1, 0.6)
        at.pick_blinks(items, cfg, tmp)
        for r in items:
            if r["notes"].count("loai-") > 1:
                bad += fails(f"{r['path']} mang 2 ly do loai: {r['notes']}")
        kept = [r for r in items if r.get("pick")]
        if not any(r.get("cull") == "nham-mat" for r in kept):
            bad += fails("anh giu lai trong loat ma mat hong van phai bi loc rieng")
    return bad


def t_eye_weight():
    """Hạ burst_eye_weight về 0 thì xếp hạng chỉ còn dựa vào độ nét."""
    bad = 0
    items = [mk(i, secs=i * 0.5) for i in range(4)]
    # mắt và nét ngược chiều nhau để thấy rõ trọng số quyết định ai bị loại
    for i, r in enumerate(items):
        r["eye_open"] = float(i)          # ảnh cuối mắt mở nhất
        r["face_sharp"] = float(3 - i)    # ảnh đầu nét nhất
    at.group_bursts(items, 3.0, 0.12, 3)
    at.pick_burst(items, 2, 1, 0.0)       # chỉ xét nét
    if items[0].get("cull") or not items[0].get("pick"):
        bad += fails("eye_weight=0 ma anh net nhat van bi loai")
    return bad


def t_report_has_cull():
    """CSV phải có cột cull và cột tin cậy của chính mắt nhắm nhất."""
    bad = 0
    if "cull" not in at.REPORT_COLS:
        bad += fails("CSV thieu cot cull — khong phan biet duoc ly do loai")
    for c in ("eye_min_area", "eye_min_score"):
        if c not in at.REPORT_COLS:
            bad += fails(f"CSV thieu cot {c}")
    return bad


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    bad = 0
    for fn in tests:
        print(f"- {fn.__name__}: {fn.__doc__.splitlines()[0]}")
        bad += fn()
    print("\n" + ("TAT CA DAT" if bad == 0 else f"{bad} loi"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
