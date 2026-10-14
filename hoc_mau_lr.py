#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HỌC MÀU LIGHTROOM trên ảnh RAW thật của một buổi (14/10) — HOC_MAU_LR.bat.

User 14/10 chọn: hiệu chỉnh trên "Ảnh RAW thật của bạn" (~20 ảnh có mặt, ~5–10 phút, mỗi
máy / profile một lần). Plugin (HocMauCore) áp TẠM 28 biến thể lên từng ảnh, dựng JPEG,
trả lại nguyên thông số; công cụ này học mô hình (mo_hinh_lr), kiểm định để-lại-một-ảnh,
lưu theo máy__profile__process version. Chuỗi màu da một lượt chỉ dùng mô hình ĐẠT.

Cần: Lightroom đang mở, plugin mới (khả năng hocmau1), buổi ĐÃ phân tích trong app (cần
khung mặt). Trong lúc học: đừng sửa ảnh trong Lightroom, đừng bấm Xử lý ảnh. Ctrl+C =
xin plugin dừng — ảnh được trả lại trước khi thoát.

Chạy:   python hoc_mau_lr.py <thư mục buổi> [--n 20] [--canh 1024] [--jobs <thư mục jobs>]
        python hoc_mau_lr.py --phan_tich <khoá>      (học lại từ mẫu đã lưu, không cần Lightroom)
Kết quả: <dữ liệu>/mo_hinh_lr/<khoá>.json + ket_qua_kiem/hoc_mau_<giờ>.txt
"""
from __future__ import annotations

import argparse
import json
import pickle
import shutil
import sys
import time
import zlib
from collections import Counter
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


def luu_bao_cao(ten: str) -> Path:
    d = GOC / "ket_qua_kiem"
    d.mkdir(exist_ok=True)
    f = d / f"hoc_mau_{ten}_{datetime.now():%Y%m%d_%H%M%S}.txt"
    f.write_text("\n".join(DONG) + "\n", encoding="utf-8")
    return f


# ------------------------------------------------------------------ chuẩn bị
def nap_phan_tich(folder: Path) -> list:
    import autotone as at
    try:
        goi = pickle.loads(zlib.decompress(Path(at.file_ket_qua_do(folder)).read_bytes()))
        return [r for r in goi.get("items") or [] if r.get("ok", True)]
    except Exception:                                        # noqa: BLE001
        return []


def thong_so_hien_tai(folder: Path, jobs: Path, cho: float = 90.0) -> dict:
    """{khoá: thông số} — catalog (đủ khoá, kể cả CameraProfile / PV / HSL Lum) gộp bản
    xuất của plugin (AsShotTemperature cho ảnh As Shot)."""
    import autotone as at
    import doc_cache_lr as dc
    out: dict = {}
    con = dc.mo_catalog()
    if con is not None:
        try:
            for k, a in dc.anh_buoi(con, folder, gom_con=True).items():
                out[k] = dc.dong_xuat(dc.thong_so(a.get("text")))
        finally:
            con.close()
    truoc = at.ban_xuat_cho_thu_muc(folder, jobs)
    t_truoc = truoc.stat().st_mtime if truoc else 0
    try:
        at.request_export(folder, jobs, skip_rating=0)
        het = time.time() + cho
        while time.time() < het:
            f = at.ban_xuat_cho_thu_muc(folder, jobs)
            if f is not None and f.stat().st_mtime > t_truoc:
                for k, row in at._read_tsv(f).items():                    # noqa: SLF001
                    out[k] = {**out.get(k, {}), **{c: v for c, v in row.items() if v != ""}}
                break
            time.sleep(1.0)
        else:
            noi("  (Lightroom chưa gửi bản xuất thông số — dùng thông số đọc từ catalog)")
    except OSError:
        pass
    return out


def chon_anh_hoc(items: list, cur: dict, n: int = 20) -> tuple[list, str]:
    """Ảnh học: có mặt, không 1★, RAW, CÙNG máy / profile / PV (nhóm đông nhất), không chỉnh
    cục bộ, WB đọc được; rải đều theo thời gian và nhiệt màu. -> ([{"path","cur","r"}], khoá)."""
    import autotone as at
    import mo_hinh_lr as mh
    ung = []
    for r in items:
        k = at.khoa_duong_dan(r.get("lr_path") or r["path"])
        c = cur.get(k)
        if (not c or not r.get("meter_boxes") or int(r.get("rating") or 0) == 1 or r.get("bw")
                or Path(r["path"]).suffix.lower() not in at.RAW_EXTS or mh.wb_cua(c) is None
                or any(x in c for x in ("MaskGroupBasedCorrections", "PaintBasedCorrections"))):
            continue
        ung.append((r, c, mh.khoa_cua(str(r.get("model") or ""), str(c.get("CameraProfile") or ""),
                                      str(c.get("ProcessVersion") or ""))))
    if not ung:
        return [], ""
    khoa = Counter(x[2] for x in ung).most_common(1)[0][0]
    ung = sorted((x for x in ung if x[2] == khoa), key=lambda x: str(x[0].get("dt") or x[0]["path"]))
    #  rải đều: chia thời gian thành n đoạn, mỗi đoạn lấy ảnh có K xa trung vị nhất (đa dạng WB)
    import numpy as np
    K = np.array([mh.wb_cua(x[1])[0] for x in ung])
    Km = float(np.median(K))
    chon = []
    for doan in np.array_split(np.arange(len(ung)), min(n, len(ung))):
        if len(doan):
            i = max(doan, key=lambda j: abs(K[j] - Km) if len(chon) % 2 else -abs(K[j] - Km))
            chon.append(ung[int(i)])
    return [{"path": r.get("lr_path") or r["path"], "cur": c, "r": r} for r, c, _k in chon], khoa


# ------------------------------------------------------------------ học
def hoc(ds: list, bien: list, bang: dict, khoa: str, preview: dict | None = None) -> "object":
    """Mẫu điểm ảnh -> khop + kiem_dinh. preview {path: file preview cùng trạng thái 'goc'}."""
    import autotone as at
    import mo_hinh_lr as mh
    import numpy as np
    anh = []
    cham: set = set()
    for a in ds:
        cap = bang.get(a["path"]) or {}
        if "nen" not in cap or "goc" not in cap:
            continue
        m = mh.mau_anh(a["r"], cap)
        if m is None or (m["loai"] == 0).sum() < 100:
            continue
        st = {b["ten"]: mh.thong_so_bien(a["cur"], b, a["path"], cham) for b in bien}
        st["sau"] = dict(a["cur"])
        anh.append({"mau": m, "st": st, "path": a["path"]})
    if len(anh) < 4:
        return None, anh
    m = mh.khop(anh)
    m.kiem_dinh = mh.kiem_dinh(anh)
    m.kiem_dinh["so_goc"] = mh.so_goc(anh)
    m.dat = bool(m.kiem_dinh.get("dat")) and all(v.get("max", 0) < 3.0 for v in m.kiem_dinh["so_goc"].values())
    m.khoa = khoa
    m.thong_tin.update(n_anh=len(anh), ngay=datetime.now().isoformat(timespec="seconds"))
    #  bảng preview -> bản xuất: preview Lightroom của trạng thái gốc vs ảnh xuất "goc"
    cap = []
    if preview:
        from PIL import Image
        for a in anh:
            pv = preview.get(a["path"])
            if not pv:
                continue
            import doc_cache_lr as dc
            p = dc.doc(pv[0], pv[1])
            W, H = a["mau"]["wh"]
            p = np.asarray(Image.fromarray(p).resize((W, H), Image.BILINEAR), dtype=np.float32) / 255.0
            xuat = mh.doc_anh(bang[a["path"]]["goc"])
            cap.append((p.reshape(-1, 3)[::7], xuat.reshape(-1, 3)[::7]))
        m.preview_sua = mh.khop_preview(cap)
    _ = at
    return m, anh


def bao_cao_mo_hinh(m) -> None:
    import mo_hinh_lr as mh
    kd = m.kiem_dinh or {}
    noi(f"\nMô hình {m.khoa}: {'ĐẠT' if m.dat else 'CHƯA ĐẠT'} "
        f"(ngưỡng tổ hợp: hue ≤ {mh.DAT['hue']}°, độ đậm ≤ {mh.DAT['q'] * 100:.0f}%, "
        f"L ≤ {mh.DAT['L']}, trắng ≤ {mh.DAT['ab']})")
    noi(f"  miền curve: {m.curve['mien']} / {m.curve['kieu']} · đường tông: {m.kieu_g} · "
        f"thứ tự: {m.thu_tu} · {m.thong_tin.get('n_anh')} ảnh")
    noi(f"  nen / sau so với goc (mã): {kd.get('so_goc')}")
    noi("  biến thể        hue°  (p90)   độ đậm%  L       trắng   | không đổi: hue°  độ đậm%")
    for t in mh.BIEN_HOC + mh.TO_HOP:
        d = kd.get(t)
        if not d:
            continue
        noi(f"  {t:12s} {d.get('hue', 0):6.2f} ({d.get('hue_p90', 0):5.2f})  {d.get('q', 0) * 100:6.1f}  "
            f"{d.get('L', 0):.4f}  {d.get('ab', 0):.4f}  | {d.get('hue_khong_doi', 0):6.2f}  "
            f"{d.get('q_khong_doi', 0) * 100:6.1f}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("thu_muc", nargs="?", help="thư mục buổi chụp")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--canh", type=int, default=1024)
    ap.add_argument("--jobs", default=None)
    ap.add_argument("--phan_tich", default=None, help="khoá mô hình: học lại từ mẫu đã lưu")
    ap.add_argument("--cho_toi_da", type=float, default=3600.0, help="giây chờ tối đa")
    a = ap.parse_args()
    import autotone as at
    import mo_hinh_lr as mh
    import kiem_preview_lr as kp

    if a.phan_tich:
        noi(f"HỌC LẠI từ mẫu đã lưu: {a.phan_tich}")
        mau = mh.nap_mau(a.phan_tich)
        if len(mau) < 4:
            noi("[!] Không có mẫu đã lưu cho khoá này.")
            return 2
        m = mh.khop(mau)
        m.kiem_dinh = mh.kiem_dinh(mau)
        m.dat, m.khoa = bool(m.kiem_dinh.get("dat")), a.phan_tich
        m.thong_tin.update(n_anh=len(mau), ngay=datetime.now().isoformat(timespec="seconds"))
        mh.luu(m)
        bao_cao_mo_hinh(m)
        noi(f"\nĐã lưu báo cáo: {luu_bao_cao(a.phan_tich)}")
        return 0 if m.dat else 1

    if not a.thu_muc:
        ap.print_help()
        return 2
    folder = Path(a.thu_muc)
    jobs = kp.tim_jobs(a.jobs)
    noi(f"HỌC MÀU LIGHTROOM — {datetime.now():%d/%m/%Y %H:%M}")
    noi(f"Thư mục buổi: {folder}\nThư mục jobs: {jobs}")
    nhip, kn = at.plugin_nhip(jobs), at.plugin_kha_nang(jobs)
    if nhip is None or nhip > 90:
        noi("[!] Plugin AutoTone trong Lightroom chưa chạy — mở Lightroom rồi chạy lại.")
        return 2
    if mh.KHA_NANG not in kn:
        noi("[!] Plugin trong Lightroom là bản cũ (thiếu hocmau1) — chép plugin mới (KIEM_TOAN_BO.bat "
            "mục 3, chọn C) rồi khởi động lại Lightroom.")
        return 2
    items = nap_phan_tich(folder)
    if not items:
        noi("[!] Buổi này chưa phân tích — mở app, phân tích buổi (Xử lý ảnh) rồi chạy lại.")
        return 2
    noi("Đọc thông số hiện tại (catalog + bản xuất của plugin)…")
    cur = thong_so_hien_tai(folder, jobs)
    ds, khoa = chon_anh_hoc(items, cur, a.n)
    if len(ds) < 6:
        noi(f"[!] Chỉ có {len(ds)} ảnh dùng được (cần ảnh RAW có mặt, không 1★, không chỉnh cục bộ).")
        return 2
    noi(f"Chọn {len(ds)} ảnh · khoá mô hình: {khoa}")
    bien = mh.bien_the([{"path": x["path"], "cur": x["cur"]} for x in ds])
    #  preview của trạng thái gốc (cache Lightroom) — học bảng preview -> bản xuất
    preview = {}
    try:
        import catalog_lr
        import doc_cache_lr as dc
        cat = catalog_lr.duong_catalog()
        con = dc.mo_catalog(cat)
        if con is not None:
            anh_cat = dc.anh_buoi(con, folder, gom_con=True)
            con.close()
            k_cua = {at.khoa_duong_dan(x["path"]): x["path"] for x in ds}
            for k, v in dc.preview_moi(cat, {k: anh_cat[k] for k in k_cua if k in anh_cat}, a.canh).items():
                preview[k_cua[k]] = (v["tep"], v["xoay"])
    except Exception:                                        # noqa: BLE001
        preview = {}
    import duong_dan as dd
    ma = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = dd.goc_du_lieu() / "hoc_mau" / ma
    mh.yeu_cau(dest, [{"path": x["path"], "cur": x["cur"]} for x in ds], bien, canh=a.canh,
               ma=ma, job_dir=jobs)
    tong = len(ds) * (len(bien) + 1)
    noi(f"Đã gửi {len(bien)} biến thể × {len(ds)} ảnh = {tong} lần dựng. Đừng sửa ảnh trong "
        "Lightroom lúc này. (Ctrl+C để dừng — ảnh được trả lại.)")
    t0 = time.monotonic()
    td: dict = {}
    try:
        while True:
            td = mh.tien_do(jobs)
            if td.get("id") == ma:
                x = int(td.get("xong") or 0)
                da = time.monotonic() - t0
                con_lai = f" · còn ~{(da / x * (tong - x)) / 60:.0f} phút" if x > 10 else ""
                print(f"\r  dựng {x}/{tong} · {td.get('bien', '')}{con_lai}      ", end="", flush=True)
                if td.get("trang_thai") in ("xong", "dung", "loi", "thay"):
                    break
            elif time.monotonic() - t0 > 120:
                noi("\n[!] Lightroom không nhận yêu cầu sau 2 phút.")
                return 2
            if time.monotonic() - t0 > a.cho_toi_da:
                mh.xin_dung(jobs)
                noi("\n[!] Quá giờ — đã xin plugin dừng.")
            time.sleep(1.0)
    except KeyboardInterrupt:
        mh.xin_dung(jobs)
        noi("\nĐã xin dừng — chờ plugin trả lại ảnh…")
        het = time.monotonic() + 120
        while time.monotonic() < het and mh.tien_do(jobs).get("trang_thai") == "dang_chay":
            time.sleep(1.0)
        noi("Plugin đã dừng (ảnh đã trả lại)." if mh.tien_do(jobs).get("trang_thai") != "dang_chay"
            else "[!] Plugin chưa báo dừng — mở Lightroom kiểm vài ảnh.")
        return 1
    print()
    noi(f"Plugin: {td.get('trang_thai')} · {td.get('xong')}/{td.get('tong')} lần dựng · "
        f"{td.get('anh_xong')}/{td.get('anh_tong')} ảnh · bỏ {td.get('bo')} · thiếu {td.get('thieu')} · "
        f"trả lại lệch {td.get('lech')} · {(time.monotonic() - t0) / 60:.1f} phút")
    if td.get("lech"):
        noi(f"[!] {td.get('lech')} ảnh trả lại chưa khớp hẳn thông số gốc — xem plugin.log, kiểm ảnh đó.")
    if td.get("trang_thai") != "xong":
        noi("[!] Lượt học không chạy hết — chưa học.")
        luu_bao_cao(khoa or "loi")
        return 1
    noi("Học mô hình + kiểm định để-lại-một-ảnh…")
    m, mau = hoc(ds, bien, mh.bang_anh(jobs), khoa, preview)
    if m is None:
        noi("[!] Quá ít ảnh đo được da (cần ≥ 4).")
        luu_bao_cao(khoa)
        return 1
    mh.luu(m, mau)
    bao_cao_mo_hinh(m)
    shutil.rmtree(dest, ignore_errors=True)                  # mẫu đã lưu (.npz) đủ để học lại
    f = luu_bao_cao(khoa)
    noi(f"\nĐã lưu mô hình: {mh.thu_muc() / (khoa + '.json')}\nĐã lưu báo cáo: {f}\nGửi file báo cáo cho Claude.")
    return 0 if m.dat else 1


if __name__ == "__main__":
    sys.exit(main())
