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
                [--may "Z 8"]      chỉ máy có tên chứa chữ này (mặc định: máy đông ảnh nhất)
                [--tat_ca [--lai]] lần lượt MỌI máy / profile của buổi (≥ 6 ảnh); máy đã có
                                   mẫu học thì bỏ qua (học lại từ mẫu: --phan_tich), --lai
                                   để dựng lại
                [--tiep <mã>]      học tiếp từ lượt dựng <mã> (hoc_mau/<mã>) đã gửi trước —
                                   công cụ thoát giữa chừng nhưng plugin vẫn dựng xong
        python hoc_mau_lr.py --phan_tich <khoá>      (học lại từ mẫu đã lưu, không cần Lightroom)
Kết quả: <dữ liệu>/mo_hinh_lr/<khoá>.json + ket_qua_kiem/hoc_mau_<giờ>.txt
"""
from __future__ import annotations

import argparse
import json
import os
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
#  15/10 (học màu TỪ APP — hoc_mau_ui): mỗi dòng nói / mỗi nhịp tiến độ còn gửi tới các hàm này
_BAO: list = []                  # f(dong: str)
_TIEN: list = []                 # f(xong: int, tong: int, bien: str, con_lai: str)


def noi(s: str = "") -> None:
    print(s, flush=True)
    DONG.append(s)
    for f in list(_BAO):
        try:
            f(s)
        except Exception:                                    # noqa: BLE001
            pass


def _tien(x: int, tong: int, bien: str, con_lai: str) -> None:
    print(f"\r  dựng {x}/{tong} · {bien}{con_lai}      ", end="", flush=True)
    for f in list(_TIEN):
        try:
            f(x, tong, bien, con_lai)
        except Exception:                                    # noqa: BLE001
            pass


def luu_bao_cao(ten: str) -> Path:
    #  15/10: thư mục DỮ LIỆU app (bản cài: thư mục gói là chỉ đọc) — chạy mã nguồn thì
    #  goc_du_lieu() vẫn là thư mục mã nguồn như trước
    import duong_dan as dd
    d = dd.goc_du_lieu() / "ket_qua_kiem"
    d.mkdir(parents=True, exist_ok=True)
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


def thong_so_hien_tai(folder: Path, jobs: Path, cho: float = 90.0, xin_xuat: bool = True) -> dict:
    """{khoá: thông số} — catalog (đủ khoá, kể cả CameraProfile / PV / HSL Lum) gộp bản
    xuất của plugin (AsShotTemperature cho ảnh As Shot). xin_xuat=False: chỉ catalog (nhanh —
    hộp chọn máy của app)."""
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
    if not xin_xuat:
        return out
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


TOI_THIEU = 6                    # ảnh dùng được tối thiểu của một máy / profile


def _ung_vien(items: list, cur: dict, may: str | None = None) -> list:
    """[(r, thông số, khoá máy__profile__PV)] — ảnh RAW có mặt, không 1★, không chỉnh cục bộ,
    WB đọc được; may: chỉ máy có tên chứa chữ này (không phân biệt hoa thường)."""
    import autotone as at
    import mo_hinh_lr as mh
    ung = []
    for r in items:
        if may and may.strip().lower() not in str(r.get("model") or "").lower():
            continue
        k = at.khoa_duong_dan(r.get("lr_path") or r["path"])
        c = cur.get(k)
        if (not c or not r.get("meter_boxes") or int(r.get("rating") or 0) == 1 or r.get("bw")
                or Path(r["path"]).suffix.lower() not in at.RAW_EXTS or mh.wb_cua(c) is None
                or any(x in c for x in ("MaskGroupBasedCorrections", "PaintBasedCorrections"))):
            continue
        ung.append((r, c, mh.khoa_cua(str(r.get("model") or ""), str(c.get("CameraProfile") or ""),
                                      str(c.get("ProcessVersion") or ""))))
    return ung


def cac_khoa(items: list, cur: dict) -> list:
    """[(khoá máy__profile__PV, số ảnh dùng được)] — đông nhất trước."""
    return Counter(x[2] for x in _ung_vien(items, cur)).most_common()


def chon_anh_hoc(items: list, cur: dict, n: int = 20, khoa: str | None = None,
                 may: str | None = None) -> tuple[list, str]:
    """Ảnh học: có mặt, không 1★, RAW, CÙNG máy / profile / PV (khoa, mặc định nhóm đông
    nhất), không chỉnh cục bộ, WB đọc được; rải đều theo thời gian và nhiệt màu.
    -> ([{"path","cur","r"}], khoá)."""
    import mo_hinh_lr as mh
    ung = _ung_vien(items, cur, may)
    if not ung:
        return [], ""
    khoa = khoa or Counter(x[2] for x in ung).most_common(1)[0][0]
    ung = sorted((x for x in ung if x[2] == khoa), key=lambda x: str(x[0].get("dt") or x[0]["path"]))
    if not ung:
        return [], khoa
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
    ap.add_argument("--may", default=None, help="chỉ máy có tên chứa chữ này (vd \"Z 8\", 7M4)")
    ap.add_argument("--tat_ca", action="store_true", help="lần lượt mọi máy / profile của buổi")
    ap.add_argument("--lai", action="store_true", help="--tat_ca: dựng lại cả máy đã có mẫu học")
    ap.add_argument("--tiep", default=None, help="mã lượt dựng (hoc_mau/<mã>) để học tiếp")
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
    if a.tiep:
        ds, khoa = ds_luot_cu(items, cur, a.tiep, jobs)
        ma_ra = hoc_mot(folder, jobs, ds, khoa, a, ma=a.tiep)
        f = luu_bao_cao(khoa or "loi")
        print(f"Đã lưu báo cáo: {f}\nGửi file báo cáo cho Claude.")
        return ma_ra
    if not a.tat_ca:
        ds, khoa = chon_anh_hoc(items, cur, a.n, may=a.may)
        ma_ra = hoc_mot(folder, jobs, ds, khoa, a)
        f = luu_bao_cao(khoa or "loi")
        print(f"Đã lưu báo cáo: {f}\nGửi file báo cáo cho Claude.")
        return ma_ra
    #  --tat_ca: từng máy / profile (đông ảnh trước); máy đã có mô hình ĐẠT thì bỏ qua
    ds_khoa = [(k, n) for k, n in cac_khoa(items, cur) if n >= TOI_THIEU]
    noi("Máy / profile của buổi: " + (", ".join(f"{k} ({n} ảnh)" for k, n in ds_khoa) or "không có"))
    ma_ra, ket = 0, []
    for k, n in ds_khoa:
        cu = mh.nap(k, kem_goc=False)       # 15/10: máy chỉ có bản kèm gói vẫn học được
        if cu is not None and not a.lai and (cu.dat or (mh.thu_muc() / f"{k}_mau.npz").is_file()):
            noi(f"\n— {k}: đã có {'mô hình ĐẠT' if cu.dat else 'mẫu học (mô hình chưa đạt)'} "
                f"({cu.thong_tin.get('ngay')}) — bỏ qua (học lại từ mẫu: --phan_tich {k}; "
                "dựng lại: --lai)")
            ket.append((k, "đã có" if cu.dat else "đã có mẫu, chưa đạt"))
            continue
        noi(f"\n=== {k} ({n} ảnh dùng được) ===")
        ds, _k = chon_anh_hoc(items, cur, a.n, khoa=k)
        m_ra = hoc_mot(folder, jobs, ds, k, a)
        ket.append((k, {0: "ĐẠT", 1: "CHƯA ĐẠT / không chạy hết"}.get(m_ra, "lỗi")))
        ma_ra = max(ma_ra, m_ra)
        if m_ra >= 2:
            noi("[!] Dừng — Lightroom / plugin không trả lời.")
            break
    noi("\nTỔNG KẾT: " + "; ".join(f"{k}: {v}" for k, v in ket))
    f = luu_bao_cao("tat_ca_" + folder.name)
    print(f"Đã lưu báo cáo: {f}\nGửi file báo cáo cho Claude.")
    return ma_ra


def ds_luot_cu(items: list, cur: dict, ma: str, jobs: Path) -> tuple[list, str]:
    """Ảnh của lượt dựng `ma` đã gửi: hoc_mau/<ma>/yeu_cau_hoc.json (lượt mới), không có thì
    theo bảng ảnh dựng của plugin. -> (ds như chon_anh_hoc, khoá)."""
    import autotone as at
    import duong_dan as dd
    import mo_hinh_lr as mh
    try:
        yc = json.loads((dd.goc_du_lieu() / "hoc_mau" / ma / "yeu_cau_hoc.json").read_text(encoding="utf-8"))
        paths, khoa = list(yc.get("paths") or []), str(yc.get("khoa") or "")
    except (OSError, ValueError):
        paths, khoa = list(mh.bang_anh(jobs)), ""
    muon = {at.khoa_duong_dan(p) for p in paths}
    ds = []
    for r, c, k in _ung_vien(items, cur):
        if at.khoa_duong_dan(r.get("lr_path") or r["path"]) in muon and (not khoa or k == khoa):
            khoa = khoa or k
            ds.append({"path": r.get("lr_path") or r["path"], "cur": c, "r": r})
    #  đúng thứ tự đã gửi (biến thể tính theo ds)
    thu = {at.khoa_duong_dan(p): i for i, p in enumerate(paths)}
    ds.sort(key=lambda x: thu.get(at.khoa_duong_dan(x["path"]), 0))
    return ds, khoa


def _xin_dung_cho_tra(jobs: Path) -> None:
    """Xin plugin dừng rồi chờ nó TRẢ LẠI ảnh (tối đa 2 phút) — Ctrl+C / nút Dừng của app."""
    import mo_hinh_lr as mh
    mh.xin_dung(jobs)
    noi("\nĐã xin dừng — chờ plugin trả lại ảnh…")
    het = time.monotonic() + 120
    while time.monotonic() < het and mh.tien_do(jobs).get("trang_thai") == "dang_chay":
        time.sleep(1.0)
    noi("Plugin đã dừng (ảnh đã trả lại)." if mh.tien_do(jobs).get("trang_thai") != "dang_chay"
        else "[!] Plugin chưa báo dừng — mở Lightroom kiểm vài ảnh.")


def hoc_mot(folder: Path, jobs: Path, ds: list, khoa: str, a, ma: str | None = None,
            dung=None) -> int:
    """Một máy / profile: gửi biến thể cho plugin, chờ dựng xong, học + kiểm định, lưu.
    ma: lượt dựng đã gửi trước (--tiep) — không gửi lại, chờ / dùng ảnh dựng của nó.
    dung: hàm -> True khi người dùng bấm Dừng (app) — như Ctrl+C.
    -> 0 ĐẠT · 1 chưa đạt / không chạy hết · 2 Lightroom không nhận."""
    import autotone as at
    import mo_hinh_lr as mh
    if len(ds) < TOI_THIEU:
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
    tong = len(ds) * (len(bien) + 1)
    if ma is None:
        ma = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = dd.goc_du_lieu() / "hoc_mau" / ma
        dest.mkdir(parents=True, exist_ok=True)
        #  để học tiếp được nếu công cụ thoát giữa chừng (plugin vẫn dựng xong): --tiep <mã>
        (dest / "yeu_cau_hoc.json").write_text(json.dumps(
            {"khoa": khoa, "paths": [x["path"] for x in ds], "canh": a.canh}, ensure_ascii=False),
            encoding="utf-8")
        mh.yeu_cau(dest, [{"path": x["path"], "cur": x["cur"]} for x in ds], bien, canh=a.canh,
                   ma=ma, job_dir=jobs)
        noi(f"Đã gửi {len(bien)} biến thể × {len(ds)} ảnh = {tong} lần dựng. Đừng sửa ảnh trong "
            "Lightroom lúc này. (Ctrl+C để dừng — ảnh được trả lại.)")
    else:
        dest = dd.goc_du_lieu() / "hoc_mau" / ma
        noi(f"Học tiếp lượt dựng {ma} ({len(ds)} ảnh) — không gửi lại.")
    t0 = time.monotonic()
    td: dict = {}
    #  đã thấy tiến độ của lượt này chưa: đọc trúng lúc plugin đang ghi file tiến độ (rỗng /
    #  khoá) KHÔNG phải "Lightroom không nhận" — 14/10 công cụ thoát khi plugin đang dựng 312/580
    da_thay = False
    try:
        while True:
            td = mh.tien_do(jobs)
            if td.get("id") == ma:
                da_thay = True
                x = int(td.get("xong") or 0)
                da = time.monotonic() - t0
                con_lai = f" · còn ~{(da / x * (tong - x)) / 60:.0f} phút" if x > 10 else ""
                _tien(x, tong, str(td.get("bien", "")), con_lai)
                if td.get("trang_thai") in ("xong", "dung", "loi", "thay"):
                    break
            elif not da_thay and time.monotonic() - t0 > 120:
                noi("\n[!] Lightroom không nhận yêu cầu sau 2 phút.")
                return 2
            if time.monotonic() - t0 > a.cho_toi_da:
                mh.xin_dung(jobs)
                noi("\n[!] Quá giờ — đã xin plugin dừng.")
            if dung is not None and dung():
                raise KeyboardInterrupt
            time.sleep(1.0)
    except KeyboardInterrupt:
        _xin_dung_cho_tra(jobs)
        return 1
    print()
    noi(f"Plugin: {td.get('trang_thai')} · {td.get('xong')}/{td.get('tong')} lần dựng · "
        f"{td.get('anh_xong')}/{td.get('anh_tong')} ảnh · bỏ {td.get('bo')} · thiếu {td.get('thieu')} · "
        f"trả lại lệch {td.get('lech')} · {(time.monotonic() - t0) / 60:.1f} phút")
    if td.get("lech"):
        noi(f"[!] {td.get('lech')} ảnh trả lại chưa khớp hẳn thông số gốc — xem plugin.log, kiểm ảnh đó.")
    if td.get("trang_thai") != "xong":
        noi("[!] Lượt học không chạy hết — chưa học.")
        return 1
    noi("Học mô hình + kiểm định để-lại-một-ảnh…")
    m, mau = hoc(ds, bien, mh.bang_anh(jobs), khoa, preview)
    if m is None:
        noi("[!] Quá ít ảnh đo được da (cần ≥ 4).")
        return 1
    mh.luu(m, mau)
    bao_cao_mo_hinh(m)
    if not os.environ.get("AUTOTONE_GIU_HOC_MAU"):
        shutil.rmtree(dest, ignore_errors=True)              # mẫu đã lưu (.npz) đủ để học lại
    noi(f"\nĐã lưu mô hình: {mh.thu_muc() / (khoa + '.json')}")
    return 0 if m.dat else 1


# ------------------------------------------------------------------ gọi từ app (15/10)
#[[ User 15/10 ("đóng gói để cài trên các máy khác, thợ dùng thiết bị khác nhau"): học màu
#   Lightroom phải chạy được TỪ APP đã cài — trước chỉ có HOC_MAU_LR.bat (dòng lệnh, cần Python
#   hệ thống, không có trong gói). Ba hàm dưới không đọc sys.argv, không import
#   kiem_preview_lr (không có trong gói); dòng lệnh main() giữ nguyên. Xem hoc_mau_ui. ]]
def kiem_san_sang(folder: Path, jobs: Path | None = None) -> tuple[str, list]:
    """-> ("", items) khi học được; ("lý do", []) khi chưa (plugin tắt / bản cũ / chưa phân tích)."""
    import autotone as at
    import mo_hinh_lr as mh
    jobs = Path(jobs or at.LR_JOB_DIR)
    nhip, kn = at.plugin_nhip(jobs), at.plugin_kha_nang(jobs)
    if nhip is None or nhip > 90:
        return "Plugin AutoTone trong Lightroom chưa chạy — mở Lightroom rồi thử lại.", []
    if mh.KHA_NANG not in kn:
        return ("Plugin trong Lightroom là bản cũ (thiếu khả năng học màu) — cài lại Tone&Retouch "
                "bằng bộ cài đầy đủ rồi khởi động lại Lightroom (bản cập nhật tự động không mang "
                "plugin)."), []
    items = nap_phan_tich(Path(folder))
    if not items:
        return "Buổi này chưa phân tích — bấm Xử lý ảnh trước rồi thử lại.", []
    return "", items


def cac_khoa_cho(folder: Path, items: list) -> list:
    """[(khoá, số ảnh dùng được, trạng thái "dat" | "goi" | "chua_dat" | "chua_hoc")] của buổi —
    đọc thẳng catalog (nhanh, không nhờ plugin). Đông ảnh trước."""
    import mo_hinh_lr as mh
    cur = thong_so_hien_tai(Path(folder), Path("."), xin_xuat=False)
    out = []
    for k, n in cac_khoa(items, cur):
        m = mh.nap(k)
        tt = "chua_hoc" if m is None else ("chua_dat" if not m.dat else
                                           ("goi" if getattr(m, "nguon", "") == "goi" else "dat"))
        out.append((k, int(n), tt))
    return out


def chay(folder: Path, jobs: Path | None = None, *, khoa_ds: list | None = None, n: int = 20,
         canh: int = 1024, cho_toi_da: float = 3600.0, bao=None, tien=None, dung=None,
         buoc=None) -> dict:
    """Học các máy / profile `khoa_ds` của buổi (None = mọi khoá ≥ TOI_THIEU ảnh chưa có mô hình
    ĐẠT trong thư mục dữ liệu). bao(dòng) / tien(xong, tong, biến, còn lại) / dung() -> True /
    buoc(mã, trạng thái, chi tiết) — mã "chuan_bi" hoặc chính khoá; trạng thái dang / xong /
    loi / bo (cửa sổ tiến trình của app).
    -> {"ma": 0 | 1 | 2, "ket": [(khoá, "ĐẠT" | …)], "bao_cao": đường file, "loi": lý do}."""
    import types
    import autotone as at
    import mo_hinh_lr as mh
    folder = Path(folder)
    jobs = Path(jobs or at.LR_JOB_DIR)
    DONG.clear()
    if bao is not None:
        _BAO.append(bao)
    if tien is not None:
        _TIEN.append(tien)

    def _b(ma, tt, ct=""):
        if buoc is not None:
            try:
                buoc(ma, tt, ct)
            except Exception:                                # noqa: BLE001
                pass

    try:
        noi(f"HỌC MÀU LIGHTROOM — {datetime.now():%d/%m/%Y %H:%M}")
        noi(f"Thư mục buổi: {folder}")
        loi, items = kiem_san_sang(folder, jobs)
        if loi:
            noi("[!] " + loi)
            _b("chuan_bi", "loi", loi)
            return {"ma": 2, "ket": [], "bao_cao": str(luu_bao_cao("loi")), "loi": loi}
        _b("chuan_bi", "dang", "plugin xuất thông số hiện tại…")
        noi("Đọc thông số hiện tại (catalog + bản xuất của plugin)…")
        cur = thong_so_hien_tai(folder, jobs)
        _b("chuan_bi", "xong", f"{len(cur)} ảnh")
        if khoa_ds is None:
            khoa_ds = [k for k, so in cac_khoa(items, cur) if so >= TOI_THIEU
                       and not ((mh.nap(k, kem_goc=False) or types.SimpleNamespace(dat=False)).dat)]
        a = types.SimpleNamespace(canh=int(canh), cho_toi_da=float(cho_toi_da))
        ma_ra, ket = 0, []
        for k in khoa_ds:
            if dung is not None and dung():
                ket.append((k, "đã dừng"))
                _b(k, "bo", "đã dừng")
                ma_ra = max(ma_ra, 1)
                continue
            noi(f"\n=== {k} ===")
            _b(k, "dang", "chọn ảnh học…")
            ds, _k = chon_anh_hoc(items, cur, n, khoa=k)
            m_ra = hoc_mot(folder, jobs, ds, k, a, dung=dung)
            if m_ra == 1 and dung is not None and dung():
                ket.append((k, "đã dừng"))
                _b(k, "bo", "đã dừng — ảnh đã trả lại")
            else:
                ket.append((k, {0: "ĐẠT", 1: "CHƯA ĐẠT / không chạy hết"}.get(m_ra, "lỗi")))
                _b(k, "xong" if m_ra == 0 else "loi", ket[-1][1])
            ma_ra = max(ma_ra, m_ra)
            if m_ra >= 2:
                noi("[!] Dừng — Lightroom / plugin không trả lời.")
                break
        noi("\nTỔNG KẾT: " + ("; ".join(f"{k}: {v}" for k, v in ket) or "không có máy nào cần học"))
        return {"ma": ma_ra, "ket": ket, "bao_cao": str(luu_bao_cao("app_" + folder.name)), "loi": ""}
    finally:
        if bao is not None and bao in _BAO:
            _BAO.remove(bao)
        if tien is not None and tien in _TIEN:
            _TIEN.remove(tien)


if __name__ == "__main__":
    sys.exit(main())
