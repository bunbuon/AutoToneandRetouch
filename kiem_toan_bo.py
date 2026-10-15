# -*- coding: utf-8 -*-
"""Chạy TOÀN BỘ bài kiểm tự động của AutoTone, xếp theo nhóm tính năng (14/10).

User 14/10: "hiện tại cần test trước hết các tính năng. Chưa cần đóng gói vội ...
nên tạo file .bat để test toàn bộ tính năng". KIEM_TOAN_BO.bat gọi file này.

AN TOÀN
    Mỗi bài chạy trong tiến trình riêng với thư mục dữ liệu TẠM (AUTOTONE_DATA):
    không đụng dữ liệu thật trong %LOCALAPPDATA%\\AutoTone, không cài plugin vào
    Lightroom, không ghi job cho Lightroom đang mở, không đọc catalog thật
    (AUTOTONE_CATALOG_LR=0); bài credit dùng máy chủ giả. Bài cần
    Lightroom THẬT / thư mục RAW THẬT / máy chủ key mới nằm ở menu thử tay của
    KIEM_TOAN_BO.bat, không ở đây.

KẾT QUẢ
    ket_qua_kiem/<ngày-giờ>/tong_ket.txt  (bảng ĐẠT / HỎNG / LỖI ĐÃ BIẾT / BỎ QUA)
    ket_qua_kiem/<ngày-giờ>/<bài>.log     (toàn bộ chữ in ra của từng bài)
    ket_qua_kiem/<ngày-giờ>.zip           (cả thư mục — gửi file này cho Claude)

    python kiem_toan_bo.py               # cả bộ
    python kiem_toan_bo.py --nhanh       # bỏ bài dài (Retouch giao diện ~12 phút)
    python kiem_toan_bo.py --nhom curve  # một nhóm (tên hoặc số, xem --ds)
    python kiem_toan_bo.py --ds          # liệt kê nhóm + bài

Thêm bài mới: thêm tên file vào NHOM. Bài hỏng vì lý do đã biết (chưa sửa, không
phải lỗi mới) thì thêm vào DA_BIET kèm mẫu chữ của dòng lỗi — chỉ khi MỌI dòng
lỗi khớp mẫu mới tính là "đã biết".
"""
from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path

GOC = Path(__file__).resolve().parent

#  (mã, tên nhóm, [bài]) — thứ tự = thứ tự chạy (bài nhanh, nền tảng trước)
NHOM = [
    ("ma", "Mã nguồn & danh sách đóng gói", [
        "kiem_cu_phap.py", "kiem_dong_goi.py", "kiem_bo_cuc.py", "kiem_tham_chieu.py",
    ]),
    ("raw", "Đọc RAW: CR2 CR3 CRW · NEF NRW · ARW SRF SR2 · EXIF", [
        "test_cr3.py", "test_dinh_dang_raw.py", "kiem_exif_jpeg.py",
    ]),
    ("sang", "Đo sáng · cân tone · chủ thể · gom loạt", [
        "test_bu_sang.py", "test_dong_bo_loat.py", "test_mat_sang_nhat.py",
        "test_da_sang_tron.py", "test_san_phang.py", "test_chu_the_af.py", "test_af_xoay.py",
        "test_mat_ao_to.py", "test_mat_lech_khung.py", "test_canh_ngoai_toi.py",
        "test_tach_canh.py", "test_2ban_quay.py", "test_ky_yeu_vong3.py", "test_cull_split.py",
        "kiem_che_do_sang.py", "kiem_do_mat.py", "kiem_lens_co.py",
    ]),
    ("mau", "Màu da · WB · HSL · Color Grade", [
        "test_wb_asshot.py", "test_phanh_da_wb.py", "test_hsl_da.py", "test_hsl_da_cuoi.py",
        "test_chuoi_mau_da.py", "test_mau_da_mot_dich.py", "test_loc_may_mau_da.py",
        "kiem_grade_trang_thai.py", "kiem_den_trang.py",
    ]),
    ("curve", "Curve da + nén vùng cháy (mới 13/10, mặc định TẮT)", [
        "test_curve_lr.py", "test_mat_na_da.py", "test_curve_da.py", "test_curve_job.py",
        "test_curve_xu_ly.py", "kiem_curve_lua.py", "test_do_song_song.py",
    ]),
    ("hoc_mau", "Học màu Lightroom + chuỗi một lượt (mới 14/10, chưa bật)", [
        "test_mo_hinh_lr.py", "test_doc_cache_lr.py", "test_do_truoc.py",
        "test_mau_mot_luot.py", "test_mot_luot_ui.py", "test_hoc_mau_lr.py",
        "test_kiem_mot_luot.py", "test_mask_xem.py", "test_dong_bo_cum.py", "test_nguoi_sua_lich_su.py", "test_chu_the.py",
    ]),
    ("lr", "Lightroom: plugin · job · catalog · preset · bản xuất", [
        "kiem_plugin_lua51.py", "kiem_xem_preset_lua.py", "kiem_retouch_khi_xuat_lua.py",
        "test_cho_lightroom.py", "test_plugin_modules.py", "test_preset_lr.py",
        "test_preset_khong_wb_tone.py", "kiem_nut_catalog.py", "kiem_ban_xuat.py",
        "kiem_moc_va_xuat.py", "kiem_dat_lai_buoi.py", "test_dung_lai_buoi.py",
        "kiem_xuat_lr.py", "kiem_ghi_de.py", "kiem_duyet_py.py", "test_kiem_preview_lr.py",
        "kiem_hoc_mau_lua.py",
    ]),
    ("gd", "Giao diện: Xử lý ảnh · chấm / lọc sao · Thư mục · lưới · tiếng Anh", [
        "test_xu_ly_anh.py", "test_cham_sao.py", "test_xem_lr.py", "test_ngon_ngu.py", "test_giao_dien_gon.py",
        "kiem_man_hinh.py",
        "kiem_ve_that.py", "kiem_khung_anh.py", "kiem_gui_duyet.py", "kiem_nhan_keo.py",
        "test_luu_phan_tich.py", "test_trang_thai.py", "kiem_da_tien_trinh.py",
    ]),
    ("key", "Bản quyền · credit · một máy một lúc · cập nhật · góp ý", [
        "kiem_khoa.py", "kiem_ban_quyen.py", "kiem_bq_online.py", "kiem_bq_giao_dien.py",
        "kiem_quan_ly_key.py", "test_tin_dung.py", "test_tin_dung_gui.py",
        "test_cap_nhat.py", "test_gop_y.py",
    ]),
    ("retouch", "Retouch & Xuất", [
        "test_tram_retouch.py", "test_retouch_cwd.py", "test_retouch_luong.py", "test_dua_ra_som.py", "test_chat_luong_ra.py",
        "test_xuat_mot_thao_tac.py", "kiem_tim_tool.py", "kiem_retouch_095.py",
        "kiem_xem_truoc.py", "kiem_retouch_gui.py",
    ]),
]

DAI = {"kiem_retouch_gui.py": 1800}        # giây chờ tối đa (mặc định CHO_MAC_DINH)
CHO_MAC_DINH = 900
BO_KHI_NHANH = {"kiem_retouch_gui.py", "test_hoc_mau_lr.py"}    # 14/10: học màu giả ~2 phút

#  Bài hỏng vì lý do ĐÃ BIẾT — mẫu chữ của dòng lỗi + giải thích. Hết lý do thì xoá.
DA_BIET = {
    "test_xuat_mot_thao_tac.py": (
        r"3 · Xuất",
        "nút “3 · Xuất” đã chuyển thành Export… ở cột Thư mục từ v86; bài kiểm chưa theo"),
    "test_dinh_dang_raw.py": (
        r"SIGALRM",
        "bài kiểm dùng hẹn giờ SIGALRM — chỉ có trên Linux / Mac, không phải lỗi đọc RAW"),
    "test_retouch_luong.py": (
        r"LUONG|luong|luồng",
        "lệch từ 59f1e78 (LUONG_MAC_DINH = 0), có từ trước"),
    "kiem_retouch_gui.py": (
        r"khong co mang|không có mạng",
        "mục cần mạng, có từ trước"),
    "kiem_nhan_keo.py": (
        r"too many values to unpack",
        "bài kiểm cũ: bảng thanh kéo nay nhiều cột hơn, bài chưa theo (hỏng cả trên main 13/10)"),
    "kiem_retouch_095.py": (
        r"giao diện có (truyền|bắt)|vet_body.pt",
        "bài kiểm cũ dò chữ trong file giao diện trước khi tách mô-đun (hỏng cả trên main 13/10)"),
}

#  dòng báo lỗi của các bài (mỗi bài một kiểu in, gom lại)
DONG_LOI = re.compile(r"\[\s*(LOI|LỖI|!|HONG|HỎNG|FAIL)\s*\]|^\s*(LOI|LỖI)\b|Traceback|Error:", re.I)
DEM_LOI = re.compile(r"\b([1-9]\d*)\s+(LOI|LỖI|lỗi|hỏng)\b")
DAT_CUOI = re.compile(r"TAT CA DAT|TẤT CẢ ĐẠT|\b0 (hỏng|LOI|LỖI)\b", re.I)
BO_QUA = re.compile(r"\bBO QUA\b|\[bỏ qua\]|bỏ qua:|SKIP", re.I)


def _co_lupa() -> bool:
    try:
        r = subprocess.run([sys.executable, "-c", "from lupa import lua51"],
                           capture_output=True, timeout=60)
        return r.returncode == 0
    except Exception:                                        # noqa: BLE001
        return False


def chuan_bi_lupa(env: dict) -> str:
    """Bài plugin cần lupa (Lua 5.1 thật). Thiếu thì cài RIÊNG vào .lupa_kiem (một lần,
    cần mạng) — không đụng Python của máy."""
    if _co_lupa():
        return "có sẵn"
    thu = GOC / ".lupa_kiem"
    if not (thu / "lupa").is_dir():
        print("  · cài lupa (Lua 5.1 để kiểm plugin Lightroom) vào .lupa_kiem — một lần...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--disable-pip-version-check",
                        "--target", str(thu), "lupa"], timeout=600)
    if (thu / "lupa").is_dir():
        env["LUPA_DIR"] = str(thu)
        return f"cài riêng ở {thu.name}"
    return "KHÔNG cài được (bài plugin sẽ BỎ QUA)"


def chay_mot(bai: str, env_goc: dict, thu_ra: Path) -> dict:
    tam = Path(tempfile.mkdtemp(prefix="kiem_tb_"))
    env = dict(env_goc, AUTOTONE_DATA=str(tam))
    cho = DAI.get(bai, CHO_MAC_DINH)
    t0 = time.time()
    try:
        #  stderr gộp vào stdout ĐÚNG thứ tự in (-u) — dòng cuối là dòng tổng kết của bài
        r = subprocess.run([sys.executable, "-u", bai], cwd=str(GOC), env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=cho)
        chu = (r.stdout or b"").decode("utf-8", "replace")
        rc = r.returncode
    except subprocess.TimeoutExpired as e:
        chu = (e.stdout or b"").decode("utf-8", "replace")
        chu += f"\n[!] QUÁ GIỜ: chạy hơn {cho} giây, đã dừng"
        rc = -9
    finally:
        shutil.rmtree(tam, ignore_errors=True)
    giay = time.time() - t0
    (thu_ra / (Path(bai).stem + ".log")).write_text(chu, encoding="utf-8")

    dong = chu.splitlines()
    loi = [x.strip() for x in dong if DONG_LOI.search(x)]
    cuoi = [x for x in dong[-6:] if x.strip()]
    dem_loi = any(DEM_LOI.search(x) for x in cuoi)
    if rc == 0 and not dem_loi:
        trang = "BỎ QUA" if (any(BO_QUA.search(x) for x in cuoi)
                             and not any(DAT_CUOI.search(x) for x in cuoi)) else "ĐẠT"
        ghi = cuoi[-1].strip()[:110] if trang == "BỎ QUA" and cuoi else ""
    else:
        #  dòng đáng đọc nhất: "[!] ..." / "[LOI] ..." trước, rồi dòng lỗi Python cuối
        uu = [x for x in loi if x.startswith("[")] or [x for x in loi if "Error" in x][-1:] or loi
        trang, ghi = "HỎNG", (uu[0] if uu else (cuoi[-1] if cuoi else f"mã thoát {rc}"))[:110]
        biet = DA_BIET.get(bai)
        if biet:
            mau = re.compile(biet[0])
            #  mọi dòng lỗi thật (bỏ dòng Traceback / tổng đếm) đều khớp mẫu đã biết
            that = [x for x in loi if not re.match(r"Traceback|File ", x) and not DEM_LOI.search(x)]
            if (that and all(mau.search(x) for x in that)) or (not that and mau.search(chu)):
                trang, ghi = "LỖI ĐÃ BIẾT", biet[1]
    return {"bai": bai, "trang": trang, "giay": giay, "ghi": ghi, "rc": rc}


def cai_plugin_lr() -> int:
    """Mục 3 của KIEM_TOAN_BO.bat: chép plugin MỚI (mã nguồn) vào thư mục Modules của
    Lightroom, trỏ jobs_dir.txt về AutoTone.lrplugin/jobs của mã nguồn — app chạy từ
    mã nguồn ghi job ở đó. Bản cài (Tone&Retouch) mở lên sẽ chép lại plugin của nó."""
    sys.path.insert(0, str(GOC))
    import duong_dan as dd
    nguon = GOC / "AutoTone.lrplugin"
    kq = dd.cai_vao_modules(nguon, nguon / "jobs")
    if kq.get("loi"):
        print(f"  [!] Không chép được plugin vào Lightroom: {kq['loi']}")
        return 1
    doi = kq.get("doi") or []
    print(f"  Plugin mới -> {kq['duong']}")
    print(f"  {'lần đầu cài' if kq.get('moi') else f'{len(doi)} file đổi'}"
          f"{': ' + ', '.join(doi[:8]) if doi else ''}")
    print("  KHỞI ĐỘNG LẠI Lightroom để nạp plugin mới (Denoise, curve, danh sách ảnh).")
    return 0


def main(argv=None) -> int:
    for _l in (sys.stdout, sys.stderr):
        try:
            _l.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--nhanh", action="store_true", help="bỏ bài dài")
    ap.add_argument("--nhom", action="append", default=[], help="chỉ chạy nhóm này (lặp lại được)")
    ap.add_argument("--bai", action="append", default=[], help="chỉ chạy bài này")
    ap.add_argument("--ds", action="store_true", help="liệt kê nhóm + bài rồi thoát")
    ap.add_argument("--cai-plugin-lr", action="store_true",
                    help="chép plugin mã nguồn vào Lightroom (thử tay từ mã nguồn)")
    a = ap.parse_args(argv)
    if a.cai_plugin_lr:
        return cai_plugin_lr()

    if a.ds:
        for i, (ma, ten, ds) in enumerate(NHOM, 1):
            print(f"{i}. [{ma}] {ten}")
            for b in ds:
                print(f"      {b}{'   (dài)' if b in DAI else ''}")
        return 0

    chon = []
    for i, (ma, ten, ds) in enumerate(NHOM, 1):
        if a.nhom and ma not in a.nhom and str(i) not in a.nhom:
            continue
        for b in ds:
            if a.bai and b not in a.bai:
                continue
            if a.nhanh and b in BO_KHI_NHANH:
                continue
            chon.append((ten, b))
    thieu = [b for _t, b in chon if not (GOC / b).is_file()]

    luc = datetime.now().strftime("%Y%m%d_%H%M%S")
    thu_ra = GOC / "ket_qua_kiem" / luc
    thu_ra.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONWARNINGS="ignore",
               OPENCV_LOG_LEVEL="ERROR", AUTOTONE_CATALOG_LR="0")
    env.pop("AUTOTONE_NGON_NGU", None)
    #  bài credit chạy app với Worker THẬT cục bộ (wrangler dev) — repo máy chủ key trên
    #  máy này tên KeyServer (bài tự tìm KeyActiveAutoTone); không có thì bài tự bỏ qua
    if not env.get("AUTOTONE_KEYSERVER"):
        for ten in ("KeyServer", "KeyActiveAutoTone", "keyactiveautotone"):
            ks = GOC.parent / ten
            if (ks / "node_modules").is_dir() and (ks / "src" / "credit.js").is_file():
                env["AUTOTONE_KEYSERVER"] = str(ks)
                break
    lupa = chuan_bi_lupa(env)

    try:
        nhanh = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(GOC),
                               capture_output=True, text=True).stdout.strip()
        commit = subprocess.run(["git", "log", "-1", "--format=%h %ci %s"], cwd=str(GOC),
                                capture_output=True, text=True).stdout.strip()
    except Exception:                                        # noqa: BLE001
        nhanh = commit = "?"
    try:
        import cap_nhat
        ban = cap_nhat.PHIEN_BAN_APP
    except Exception:                                        # noqa: BLE001
        ban = "?"
    dau = [f"KIỂM TOÀN BỘ AutoTone — {datetime.now():%d/%m/%Y %H:%M}",
           f"Mã nguồn: nhánh {nhanh} · {commit} · phiên bản {ban}",
           f"Python {platform.python_version()} ({sys.executable}) · {platform.platform()}",
           f"lupa: {lupa} · máy chủ key cục bộ: {env.get('AUTOTONE_KEYSERVER') or 'không có'}"
           f" · {len(chon)} bài" + (" · chế độ nhanh" if a.nhanh else ""), ""]
    print("\n".join(dau))

    kq = []
    nhom_cu = None
    t0 = time.time()
    for i, (ten, b) in enumerate(chon, 1):
        if ten != nhom_cu:
            print(f"\n== {ten}")
            nhom_cu = ten
        if b in thieu:
            kq.append({"bai": b, "trang": "BỎ QUA", "giay": 0, "ghi": "không có file", "rc": 0,
                       "nhom": ten})
            print(f"  [{i:>2}/{len(chon)}] {b:<32} BỎ QUA  (không có file)")
            continue
        print(f"  [{i:>2}/{len(chon)}] {b:<32} ...", end="", flush=True)
        r = chay_mot(b, env, thu_ra)
        r["nhom"] = ten
        kq.append(r)
        print(f"\r  [{i:>2}/{len(chon)}] {b:<32} {r['trang']:<12} {r['giay']:>5.0f}s"
              f"{'  ' + r['ghi'] if r['ghi'] else ''}", flush=True)

    dem = {k: sum(1 for r in kq if r["trang"] == k) for k in ("ĐẠT", "HỎNG", "LỖI ĐÃ BIẾT", "BỎ QUA")}
    phut = (time.time() - t0) / 60
    tom = (f"TỔNG: {len(kq)} bài · ĐẠT {dem['ĐẠT']} · HỎNG {dem['HỎNG']} · "
           f"LỖI ĐÃ BIẾT {dem['LỖI ĐÃ BIẾT']} · BỎ QUA {dem['BỎ QUA']} · {phut:.1f} phút")
    bang = list(dau)
    nhom_cu = None
    for r in kq:
        if r["nhom"] != nhom_cu:
            bang.append(f"\n== {r['nhom']}")
            nhom_cu = r["nhom"]
        bang.append(f"  {r['trang']:<12} {r['bai']:<32} {r['giay']:>5.0f}s"
                    f"{'  ' + r['ghi'] if r['ghi'] else ''}")
    bang += ["", tom]
    hong = [r for r in kq if r["trang"] == "HỎNG"]
    if hong:
        bang += ["", "BÀI HỎNG (xem <tên bài>.log cùng thư mục):"]
        bang += [f"  - {r['bai']}: {r['ghi']}" for r in hong]
    (thu_ra / "tong_ket.txt").write_text("\n".join(bang) + "\n", encoding="utf-8")

    goi = thu_ra.parent / f"{luc}.zip"
    with zipfile.ZipFile(goi, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(thu_ra.iterdir()):
            zf.write(f, f"{luc}/{f.name}")
    print(f"\n{tom}")
    print(f"Bảng kết quả: {thu_ra / 'tong_ket.txt'}")
    print(f"Gửi cho Claude: {goi}")
    return 1 if hong else 0


if __name__ == "__main__":
    sys.exit(main())
