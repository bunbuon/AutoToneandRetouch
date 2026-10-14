#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đo PREVIEW LIGHTROOM trên máy thật — Giai đoạn 0 của chuỗi màu da MỘT LƯỢT (14/10).

User 14/10: "Việc xử lý 1000 ảnh theo cách hiện tại thì thời gian phải tốn 15 phút…
Hãy thử đổi lại Flow". Chuỗi một lượt đo da trên preview Lightroom của trạng thái
HIỆN TẠI (trước khi áp) — chỉ đáng làm nếu Lightroom trả preview đủ nhanh. Lượt 2 hôm
nay: 0.50 s/ảnh, nhưng đó là ảnh VỪA đổi thông số (Lightroom phải dựng lại). Ảnh chưa
đổi có thể đã có preview sẵn trong cache -> nhanh hơn nhiều. Công cụ này đo đúng chuyện đó.

Đo (Lightroom phải đang mở, plugin AutoTone có khả năng xem1):
  A. N/3 ảnh, cạnh 1600, CÙNG LÚC máy đo da song song (như lượt thật)  — lần đầu
  B. N/3 ảnh, cạnh 1600, không đo                                          — lần đầu
  C. N/3 ảnh, cạnh 1024, không đo                                          — lần đầu
  A', C'. lấy lại A (1600) và C (1024)                                    — lần sau
  Soát: 3 ảnh của A được XUẤT THẬT -> preview lệch bản xuất bao nhiêu (độ sáng, màu da).

KHÔNG đổi gì trong catalog: chỉ đọc preview + xuất 3 ảnh soát vào thư mục tạm (xoá khi
xong). Đừng bấm "Xử lý ảnh" trong lúc đo (dùng chung file yêu cầu preview).

Chạy:   python kiem_preview_lr.py <thư mục buổi> [--n 120] [--jobs <thư mục jobs>]
        (hoặc KIEM_PREVIEW_LR.bat)
Kết quả: ket_qua_kiem/preview_lr_<giờ>.txt — gửi file này cho Claude.
"""
from __future__ import annotations

import argparse
import math
import pickle
import sys
import time
import zlib
from datetime import datetime
from pathlib import Path

GOC = Path(__file__).resolve().parent
sys.path.insert(0, str(GOC))

for _l in (sys.stdout, sys.stderr):
    try:
        _l.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                        # noqa: BLE001
        pass

DONG: list = []


def noi(s: str = "") -> None:
    print(s, flush=True)
    DONG.append(s)


def tim_jobs(tu_dat: str | None) -> Path:
    """Thư mục jobs Lightroom đang dùng: --jobs > jobs_dir.txt của bản trong Modules >
    thư mục jobs của mã nguồn."""
    import autotone as at
    import duong_dan as dd
    if tu_dat:
        return Path(tu_dat)
    m = dd.thu_muc_modules_lr()
    tro = m / "AutoTone.lrplugin" / dd.TEN_TRO_JOBS if m else None
    if tro is not None and tro.is_file():
        p = Path(tro.read_text(encoding="utf-8", errors="replace").strip())
        if p.is_dir():
            return p
    return Path(at.LR_JOB_DIR)


def chon_anh(folder: Path, n: int) -> tuple[list, dict]:
    """(đường dẫn ảnh, {khoá: r}) — ưu tiên ảnh có mặt trong kết quả phân tích đã lưu,
    rải đều cả buổi; chưa phân tích thì lấy file RAW trong thư mục."""
    import autotone as at
    items = []
    try:
        f = at.file_ket_qua_do(folder)
        goi = pickle.loads(zlib.decompress(Path(f).read_bytes()))
        items = [r for r in goi.get("items") or [] if r.get("ok", True)]
    except Exception:                                        # noqa: BLE001
        items = []
    if items:
        co = [r for r in items if r.get("meter_boxes")] or items
        co = sorted(co, key=lambda r: str(r.get("dt") or r["path"]))
        buoc = max(1, len(co) // n)
        ds = co[::buoc][:n]
        return [r["path"] for r in ds], {at.khoa_duong_dan(r["path"]): r for r in ds}
    raw = sorted(p for p in Path(folder).iterdir() if p.suffix.lower() in at.RAW_EXTS)
    buoc = max(1, len(raw) // n)
    return [str(p) for p in raw[::buoc][:n]], {}


def chay_luot(folder, paths, ma, canh, jobs, kiem=None, bo=None, r_cua=None) -> dict:
    """Một yêu cầu preview -> số đo thời gian (+ đo da song song nếu có bo)."""
    import autotone as at
    import xem_lr
    xem_lr.yeu_cau(folder, paths, ma, kiem=kiem, canh=canh, job_dir=jobs)
    t_gui = time.monotonic()
    t_nhan = t_dau = None
    n_dau = 0
    da, do = set(), {}
    td: dict = {}
    while True:
        td = xem_lr.tien_do(jobs)
        bay = time.monotonic()
        if td.get("ma") != ma:
            if bay - t_gui > 180:
                xem_lr.rut_yeu_cau(jobs)
                return {"loi": "Lightroom không nhận yêu cầu sau 3 phút"}
            time.sleep(0.2)
            continue
        if t_nhan is None:
            t_nhan = bay
        x = int(td.get("xong") or 0)
        if x and t_dau is None:
            t_dau, n_dau = bay, x
        if bo is not None:
            for p, j in xem_lr.bang_anh(job_dir=jobs):
                if p not in da:
                    da.add(p)
                    bo.gui(p, (r_cua or {}).get(at.khoa_duong_dan(p)), j)
            do.update(bo.lay())
        if td.get("trang_thai") in ("xong", "dung", "loi"):
            break
        time.sleep(0.2)
    t_xong = time.monotonic()
    bang = xem_lr.bang_anh(job_dir=jobs)
    t_do_xong = t_xong
    if bo is not None:
        for p, j in bang:
            if p not in da:
                da.add(p)
                bo.gui(p, (r_cua or {}).get(at.khoa_duong_dan(p)), j)
        het = time.monotonic() + 300
        while bo.con() and time.monotonic() < het:
            do.update(bo.lay())
            time.sleep(0.1)
        do.update(bo.lay())
        t_do_xong = time.monotonic()
    wh = None
    if bang:
        try:
            from PIL import Image
            with Image.open(bang[0][1]) as im:
                wh = im.size
        except OSError:
            pass
    n = len(bang)
    s_anh = ((t_xong - t_dau) / max(1, n - n_dau)) if (t_dau and n > n_dau) else None
    return {"n": n, "tong": len(paths), "cho_nhan": (t_nhan or t_gui) - t_gui,
            "giay": t_xong - (t_nhan or t_gui), "s_anh": s_anh, "wh": wh,
            "trang_thai": td.get("trang_thai"), "cach": td.get("cach"),
            "thong_bao": td.get("thong_bao") or "", "bang": bang,
            "kiem": xem_lr.bang_anh(xem_lr.TEN_KIEM, job_dir=jobs), "do": do,
            "giay_do": t_do_xong - (t_nhan or t_gui)}


def cau_luot(ten: str, kq: dict) -> str:
    if kq.get("loi"):
        return f"  {ten}: LỖI — {kq['loi']}"
    s = kq.get("s_anh")
    return (f"  {ten}: {kq['n']}/{kq['tong']} ảnh · {kq['giay']:.1f} s"
            + (f" · {s:.2f} s/ảnh" if s is not None else "")
            + (f" · ảnh trả về {kq['wh'][0]}×{kq['wh'][1]}" if kq.get("wh") else "")
            + f" · chờ Lightroom nhận {kq['cho_nhan']:.1f} s"
            + (f" · plugin: {kq['thong_bao']}" if kq.get("thong_bao") else ""))


def so_kiem(kq: dict, r_cua: dict) -> list:
    """Preview vs bản xuất thật của ảnh soát: lệch điểm ảnh + lệch màu da."""
    import autotone as at
    import curve_da as cd
    cfg = dict(at.DEFAULTS)
    pv = {at.khoa_duong_dan(p): j for p, j in kq.get("bang") or []}
    out = []
    for p, xuat in kq.get("kiem") or []:
        j = pv.get(at.khoa_duong_dan(p))
        if not j:
            out.append(f"    {Path(p).name}: không có preview để so")
            continue
        tuoi, so = cd.so_tuoi(j, xuat)
        r = r_cua.get(at.khoa_duong_dan(p))
        a, b = cd.do_anh(r, j, cfg), cd.do_anh(r, xuat, cfg)
        cau = (f"    {Path(p).name}: lệch điểm ảnh {so['lech']} · độ sáng {so['sang']} "
               f"({'khớp' if tuoi else 'LỆCH'})")
        k = "da_mn" if a.get("da_mn") is not None and b.get("da_mn") is not None else "da_cu"
        if a.get(k) is not None and b.get(k) is not None:
            la, lb = cd.thong_ke(a[k], a["mien"]), cd.thong_ke(b[k], b["mien"])
            ha, qa = cd.hue_q(la)
            hb, qb = cd.hue_q(lb)
            dh = (ha - hb + 180.0) % 360.0 - 180.0
            cau += (f" · da: hue {dh:+.2f}° · độ đậm {100 * (qa / max(qb, 1e-9) - 1):+.1f}% "
                    f"· L {la[0] - lb[0]:+.4f}")
        else:
            cau += " · không đo được da"
        out.append(cau)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("thu_muc", help="thư mục buổi chụp (đã có trong catalog Lightroom)")
    ap.add_argument("--n", type=int, default=120, help="số ảnh (chia ba nhóm A / B / C)")
    ap.add_argument("--jobs", default=None, help="thư mục jobs của plugin (mặc định tự tìm)")
    a = ap.parse_args()
    import autotone as at
    import curve_da as cd
    import xem_lr

    folder = Path(a.thu_muc)
    jobs = tim_jobs(a.jobs)
    noi(f"ĐO PREVIEW LIGHTROOM — {datetime.now():%d/%m/%Y %H:%M}")
    noi(f"Thư mục buổi: {folder}")
    noi(f"Thư mục jobs: {jobs}")
    nhip = at.plugin_nhip(jobs)
    kn = at.plugin_kha_nang(jobs)
    noi(f"Nhịp plugin: {'chưa có' if nhip is None else f'{nhip:.0f} giây trước'} · "
        f"khả năng: {','.join(sorted(kn)) or '(không khai)'}")
    if not folder.is_dir():
        noi("[!] Không thấy thư mục buổi.")
        return 2
    if nhip is None or nhip > 90:
        noi("[!] Plugin AutoTone trong Lightroom chưa chạy (không có nhịp mới) — mở Lightroom "
            "rồi chạy lại.")
        return 2
    if xem_lr.KHA_NANG not in kn:
        noi("[!] Plugin trong Lightroom là bản cũ (thiếu xem1) — cài lại AutoTone / chép plugin "
            "mới (KIEM_TOAN_BO.bat mục 3) rồi khởi động lại Lightroom.")
        return 2
    paths, r_cua = chon_anh(folder, max(9, a.n))
    if len(paths) < 9:
        noi("[!] Thư mục có quá ít ảnh.")
        return 2
    k = len(paths) // 3
    A, B, C = paths[:k], paths[k:2 * k], paths[2 * k:3 * k]
    noi(f"Ảnh: {len(paths)} ({'có kết quả phân tích — ảnh có mặt' if r_cua else 'chưa phân tích'})"
        f" · mỗi nhóm {k}")
    noi("Đừng bấm Xử lý ảnh trong lúc đo.\n")

    ma0 = datetime.now().strftime("%Y%m%d_%H%M%S")
    kq = {}
    bo = cd.BoDo(at.DEFAULTS)
    noi(f"Đo da song song: {bo.n} tiến trình")
    try:
        kq["A"] = chay_luot(folder, A, ma0 + "pA", 1600, jobs, kiem=A[:3], bo=bo, r_cua=r_cua)
        noi(cau_luot("A  1600 lần đầu + đo da", kq["A"]))
        if kq["A"].get("do"):
            n_do = len(kq["A"]["do"])
            noi(f"     đo da {n_do} ảnh xong sau {kq['A']['giay_do']:.1f} s tính từ lúc "
                f"Lightroom nhận (Lightroom xong sau {kq['A']['giay']:.1f} s)")
        for ten, nhom, canh in (("B  1600 lần đầu", B, 1600), ("C  1024 lần đầu", C, 1024),
                                ("A' 1600 lần sau", A, 1600), ("C' 1024 lần sau", C, 1024)):
            ma = ma0 + "p" + ten.split()[0].replace("'", "2")
            kq[ten] = chay_luot(folder, nhom, ma, canh, jobs)
            noi(cau_luot(ten, kq[ten]))
            xem_lr.don_tam(ma)
        noi("\nSoát preview với bản xuất thật (3 ảnh của A):")
        for d in so_kiem(kq["A"], r_cua):
            noi(d)
    finally:
        bo.dong()
        for kh in ("A",):
            xem_lr.don_tam(ma0 + "p" + kh)

    #  ước lượng cho 1.000 ảnh
    noi("\nƯớc lượng 1.000 ảnh (chỉ khâu Lightroom trả preview):")
    for ten, khoa in (("A  1600 lần đầu + đo da", "A"), ("B  1600 lần đầu", "B  1600 lần đầu"),
                      ("C  1024 lần đầu", "C  1024 lần đầu"), ("A' 1600 lần sau", "A' 1600 lần sau"),
                      ("C' 1024 lần sau", "C' 1024 lần sau")):
        s = (kq.get(khoa) or {}).get("s_anh")
        if s is not None and math.isfinite(s):
            noi(f"  {ten:28s} ~{s * 1000 / 60:.1f} phút")
    ra = GOC / "ket_qua_kiem"
    ra.mkdir(exist_ok=True)
    f = ra / f"preview_lr_{datetime.now():%Y%m%d_%H%M%S}.txt"
    f.write_text("\n".join(DONG) + "\n", encoding="utf-8")
    noi(f"\nĐã lưu: {f}\nGửi file này cho Claude.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
