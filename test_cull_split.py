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


def _loat(n, faces, ears, nghieng=None):
    """Mot loat n anh lien tiep, moi anh `faces` nguoi, EAR do trong luot = ears[i]
    (None = chua do). nghieng[i] = (lech, ti_mat) cua mat do (mac dinh truc dien)."""
    items = [mk(i, secs=i * 0.5, faces=faces) for i in range(n)]
    for i, r in enumerate(items):
        r["path"] = f"X:\\anh\\L{faces}_{i:02d}.ARW"
        e = ears[i]
        if e is not None:
            lech, ti = (nghieng or {}).get(i, (0.1, 0.95))
            r["ear_min"] = e
            r["ear_mat"] = [{"ear": e, "lech": lech, "ti_mat": ti}]
    at.group_bursts(items, 3.0, 0.12, 3)
    return items


def t_burst_luat_moi():
    """8/10: trong loat, CHI anh 1-4 nguoi co nguoi nham mat bi 1 sao; ai mo mat thi giu."""
    bad = 0
    items = _loat(6, 2, [0.30, 0.05, 0.30, 0.30, 0.08, 0.30])
    n = at.pick_burst(items, 2, 1, 0.6, cfg=dict(at.DEFAULTS, burst=True))
    loai = {i for i, r in enumerate(items) if r.get("cull")}
    if loai != {1, 4} or n != 2:
        bad += fails(f"phai loai dung anh 1 va 4 (nham mat), loai {sorted(loai)}")
    for i in (1, 4):
        r = items[i]
        if r.get("cull") != "loat" or r.get("rating") != 1 or r.get("loat_ly_do") != "nham-mat":
            bad += fails(f"anh {i}: nhan sai {r.get('cull')} / {r.get('rating')} / {r.get('loat_ly_do')}")
    for i in (0, 2, 3, 5):
        if items[i].get("rating") or not items[i].get("pick"):
            bad += fails(f"anh {i} mo mat ma van bi gan sao / khong giu")
    return bad


def t_burst_mo_mat_giu_het():
    """Loat dai ma ai cung mo mat -> giu HET (truoc day chi giu 2 tam)."""
    bad = 0
    items = _loat(8, 1, [0.30] * 8)
    if at.pick_burst(items, 2, 1, 0.6, cfg=dict(at.DEFAULTS, burst=True)) != 0 or \
            any(r.get("cull") or r.get("rating") for r in items):
        bad += fails("loat mo mat van bi cat bot")
    return bad


def t_burst_dong_nguoi():
    """Anh tren 4 nguoi: khong loc, giu nguyen du co nguoi nham mat; 4 nguoi van loc."""
    bad = 0
    items = _loat(4, 6, [0.05] * 4)
    at.pick_burst(items, 2, 1, 0.6, cfg=dict(at.DEFAULTS, burst=True))
    if any(r.get("cull") for r in items) or any(r.get("loat_ly_do") != "dong-nguoi" for r in items):
        bad += fails("anh 6 nguoi bi loc")
    items = _loat(4, 4, [0.05] * 4)
    at.pick_burst(items, 2, 1, 0.6, cfg=dict(at.DEFAULTS, burst=True))
    if not all(r.get("cull") == "loat" for r in items):
        bad += fails("anh 4 nguoi nham mat phai bi loc (nguong blink_max_faces = 4)")
    return bad


def t_burst_chua_do_mat():
    """Khong do duoc mat (thieu mediapipe, khong ear.csv) -> khong ket luan, giu het."""
    bad = 0
    items = _loat(5, 1, [None] * 5)
    at.pick_burst(items, 2, 1, 0.6, cfg=dict(at.DEFAULTS, burst=True))
    if any(r.get("cull") for r in items):
        bad += fails("chua do mat ma van loai")
    return bad


def t_mat_nghieng_bo_qua():
    """8/10: loc mat (va loc trung khung) chi xet mat truc dien / 3/4 — mat nghieng bo qua."""
    bad = 0
    cases = [((0.30, 0.95), True, "truc dien"), ((0.80, 0.70), True, "3/4"),
             ((1.20, 0.70), True, "3/4 manh, mat xa con rong"),
             ((1.20, 0.45), False, "gan nghieng, mat xa hep"),
             ((1.80, 0.60), False, "nghieng han")]
    cfg = dict(at.DEFAULTS, blink=True)
    for (lech, ti), loai, ten in cases:
        it = [mk(1, secs=0, faces=1)]
        it[0]["path"] = "X:\\anh\\NG.ARW"
        it[0]["ear_min"] = 0.05
        it[0]["ear_mat"] = [{"ear": 0.05, "lech": lech, "ti_mat": ti}]
        at.pick_blinks(it, cfg, None)
        if (it[0].get("cull") == "nham-mat") != loai:
            bad += fails(f"loc mat, mat {ten} (lech {lech}, ti {ti}): loai={not loai}, mong doi={loai}")
        items = _loat(3, 1, [0.05] * 3, nghieng={i: (lech, ti) for i in range(3)})
        at.pick_burst(items, 2, 1, 0.6, cfg=dict(at.DEFAULTS, burst=True))
        if all(r.get("cull") == "loat" for r in items) != loai:
            bad += fails(f"loc trung khung, mat {ten}: sai")
    # hai nguoi: mot nghieng nham "gia", mot truc dien mo mat -> giu
    it = [mk(1, secs=0, faces=2)]
    it[0]["path"] = "X:\\anh\\HAI.ARW"
    it[0]["ear_min"] = 0.04
    it[0]["ear_mat"] = [{"ear": 0.04, "lech": 2.0, "ti_mat": 0.2},
                        {"ear": 0.30, "lech": 0.1, "ti_mat": 0.95}]
    at.pick_blinks(it, cfg, None)
    if it[0].get("cull"):
        bad += fails("EAR thap cua mat NGHIENG van lam loai anh")
    return bad


def t_one_reason_only():
    """Anh da bi loai vi trung khung thi loc mat khong ghi de ly do."""
    bad = 0
    items = _loat(6, 1, [0.05] * 6)                  # ca loat deu nham mat
    cfg = dict(at.DEFAULTS, burst=True, blink=True)
    at.pick_burst(items, 2, 1, 0.6, cfg=cfg)
    at.pick_blinks(items, cfg, None)
    for r in items:
        if r["notes"].count("loai-") != 1:
            bad += fails(f"{r['path']} phai mang dung 1 ly do loai: {r['notes']}")
    if not all(r.get("cull") == "loat" for r in items):
        bad += fails("anh trong loat nham mat phai mang nhan cua bo loc trung khung")
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
