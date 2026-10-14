# -*- coding: utf-8 -*-
"""Kiểm nút "Xử lý ảnh" (13/10) + lưới theo Lightroom + mô phỏng Bù sáng / K / Tint.

User 13/10:
  1. "Ở lưới Preview, chỉ load các ảnh mà trong lightroom đang hiển thị … xoá 10 ảnh
     thì preview cũng chỉ hiện 990 ảnh … và ngược lại".
  2. "Đưa quy trình Phân tích và Áp vào Lightroom thành 1 nút bấm Xử lý ảnh … hiển
     thị tiến trình rõ ràng và thông báo bằng popup khi chạy xong."
  3. "Khi điều chỉnh thông số trên phần Bù sáng, Temp, Tint. Cần load lại preview
     theo các thông số đã chỉnh".
  4. "Thêm option Denoise ảnh … chọn ngưỡng ISO … Mặc định ISO 2000 và Option Off."

Giao diện THẬT (App), engine đo giả (at.analyze vá), "plugin" giả: đổi tên job thành
.done và ghi kết quả Denoise như DenoiseCore.lua.

Chạy:  python test_xu_ly_anh.py
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path

for _l in (sys.stdout, sys.stderr):
    try:
        _l.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                        # noqa: BLE001
        pass

LOI: list = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


def main() -> int:
    tam = Path(tempfile.mkdtemp(prefix="xu_ly_anh_"))
    os.environ["AUTOTONE_DATA"] = str(tam / "du_lieu")
    #  catalog Lightroom GIẢ (SQLite) — không đọc catalog thật của máy
    cat_gia = tam / "Gia.lrcat"
    os.environ["AUTOTONE_CATALOG_LR"] = str(cat_gia)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import autotone as at
    import test_2ban_quay as tq
    import test_giao_dien_gon as tg

    buoi = tam / "SuKien"
    buoi.mkdir()
    ISO = [400, 800, 2000, 3200, 6400, 1600]
    for i in range(len(ISO)):
        tg.raw_gia(buoi / f"SK_{i}.ARW", mau=(90 + 20 * i, 120, 150))
        (buoi / f"SK_{i}.xmp").write_text(tg.XMP_GIA, encoding="utf-8")

    def items_cua(pairs_) -> list:
        out = []
        for p, sc in pairs_:
            i = int(Path(p).stem.split("_")[1])
            r = tq.anh(Path(p).stem, i * 8, -1.6 + 0.12 * i, da=tq.DA_TRONG, iso=ISO[i])
            r["path"] = str(p)
            r["sidecar"] = str(sc) if sc else str(Path(p).with_suffix(".xmp"))
            out.append(r)
        return out

    import tkinter as tk
    import autotone_gui as ag
    import giao_dien as gd
    root = tk.Tk()
    ag.bq.kiem = lambda: {"co_phep": True, "con_lai": timedelta(days=300), "nhac": "",
                          "goi": "1 năm", "may": "TEST01", "het_han": False, "ly_do": ""}
    root.geometry("1600x940+0+0")
    gd.dat_theme(root)
    job_cu, analyze_cu = at.LR_JOB_DIR, at.analyze
    jobs = tam / "jobs"
    jobs.mkdir()
    at.LR_JOB_DIR = jobs
    lan_do: list = []

    def analyze_gia(pairs_, cfg_, jobs_=1, progress=None, cancel=None):
        lan_do.append(len(pairs_))
        for k in range(len(pairs_)):
            if progress:
                progress(k + 1, len(pairs_))
        return items_cua(pairs_), []

    at.analyze = analyze_gia
    try:
        app = ag.App(root)
        app.grid(row=0, column=0, sticky="nsew")

        def vong(n=4):
            for _ in range(n):
                root.update_idletasks()
                root.update()
                time.sleep(0.02)

        def cho(dieu, giay=15.0):
            het = time.time() + giay
            while time.time() < het:
                vong(1)
                if dieu():
                    return True
            return False

        vong(8)
        #  nguồn .xmp + đẩy thẳng Lightroom (job) — không cần bản xuất catalog
        app.v_source.set(ag.SOURCES[0][0])
        app.v_lrpush.set(True)
        app.v_folder.set(str(buoi))
        app.scan_folder()
        vong()
        # ---------------------------------------------------------------- 4. Denoise
        ktra("Denoise mặc định TẮT, ngưỡng 2000", app.v_denoise.get() is False
             and app.read_cfg()["denoise_iso"] == 2000)
        app.v_denoise.set(True)
        vong()
        # ---------------------------------------------------------------- 2. Xử lý ảnh
        ktra("thanh dưới: MỘT nút Xử lý ảnh (vàng), không còn Phân tích / Áp riêng",
             str(app.btn_xu_ly.cget("text")) == "Xử lý ảnh" and app.btn_xu_ly.cget("kieu") == "chinh"
             and not hasattr(app, "btn_analyze") and not hasattr(app, "btn_ghi3"))
        ktra("chưa phân tích: cột Cảnh ẩn", not app.cot_canh.winfo_ismapped())
        app.btn_xu_ly.invoke()
        hop = app._xl_hop()
        ktra("bấm Xử lý ảnh -> mở cửa sổ tiến trình", hop is not None and hop.winfo_exists())
        ktra("…đo xong tự gửi job sang Lightroom",
             cho(lambda: bool(app._xl.get("job"))), str(app._xl.get("job")))
        ktra("…đo đủ 6 ảnh một lần", lan_do == [6], str(lan_do))
        vong()
        ktra("phân tích xong: cột Cảnh hiện ra", app.cot_canh.winfo_ismapped())
        job = Path(app._xl["job"])
        ktra("…bước Phân tích xong, bước Áp đang chạy (chờ Lightroom)",
             app._xl.get("pha") == "ap" and not app._xl.get("xong"))
        ktra("…nút đổi chữ, khoá trong lúc xử lý",
             str(app.btn_xu_ly.cget("text")) in ("Đang xử lý…", "Đang chờ Lightroom…")
             and str(app.btn_xu_ly.cget("state")) == "disabled", str(app.btn_xu_ly.cget("text")))
        #  "plugin" nhận + áp xong
        os.replace(job, job.with_suffix(".done"))
        ktra("Lightroom áp xong -> sang Denoise: gửi yêu cầu riêng",
             cho(lambda: (jobs / at.TEN_YC_DENOISE).is_file()))
        yc = (jobs / at.TEN_YC_DENOISE).read_text(encoding="utf-8").splitlines()
        ma = yc[0].split("=", 1)[1]
        ds_dn = sorted(Path(x).name for x in yc[1:] if x)
        ktra("…chỉ ảnh ISO ≥ 2000", ds_dn == ["SK_2.ARW", "SK_3.ARW", "SK_4.ARW"], str(ds_dn))
        ktra("…đã đánh dấu 'đã áp vào Lightroom'", bool(getattr(app, "_da_ap_lr", False)))
        (jobs / at.TEN_YC_DENOISE).unlink()
        (jobs / at.TEN_KQ_DENOISE).write_text(
            f"ma={ma}\ntong=3\nbat=3\nda_co=0\nkhong_ho_tro=0\nkhong_thay=0\nloi=0\n",
            encoding="utf-8")
        ktra("Denoise xong -> lượt kết thúc, hộp hiện tổng kết 'Xử lý xong'",
             cho(lambda: app._xl.get("xong")) and hop.lbl_tieu_de.cget("text") == "Xử lý xong"
             and hop.winfo_ismapped(), hop.lbl_tieu_de.cget("text"))
        tong = hop.lbl_tong.cget("text")
        ktra("…tổng kết nói số ảnh đã áp + Denoise", "6 file .xmp" in tong or "6 ảnh" in tong
             and "Denoise" in tong, tong.replace("\n", " | ")[:160])
        ktra("…nút Xử lý ảnh mở lại", cho(lambda: str(app.btn_xu_ly.cget("state")) == "normal"))
        hop.destroy()
        #  bấm lại: ảnh đã có kết quả -> KHÔNG đo lại, áp ngay
        app.v_denoise.set(False)
        app.btn_xu_ly.invoke()
        ktra("bấm lại: không đo lại ảnh đã có kết quả", cho(lambda: bool(app._xl.get("job")))
             and lan_do == [6], str(lan_do))
        j2 = Path(app._xl["job"])
        os.replace(j2, j2.with_suffix(".done"))
        ktra("…Denoise tắt -> xong ngay sau khi áp", cho(lambda: app._xl.get("xong"))
             and "denoise" not in app._xl["hop"].hang)
        app._xl["hop"].destroy()
        #  14/10 user: "Khi Denoise ảnh mà bấm dừng thì vẫn đang chạy tiếp"
        app.v_denoise.set(True)
        app.btn_xu_ly.invoke()
        ktra("Dừng Denoise: chạy lại có Denoise -> gửi job", cho(lambda: bool(app._xl.get("job"))))
        j3 = Path(app._xl["job"])
        os.replace(j3, j3.with_suffix(".done"))
        ktra("…sang Denoise: có yêu cầu", cho(lambda: (jobs / at.TEN_YC_DENOISE).is_file()))
        ma3 = (jobs / at.TEN_YC_DENOISE).read_text(encoding="utf-8").splitlines()[0].split("=", 1)[1]
        #  "plugin" NHẬN yêu cầu (đổi tên) và đang làm ảnh 1/3
        os.replace(jobs / at.TEN_YC_DENOISE, jobs / (at.TEN_YC_DENOISE + ".claimed"))
        (jobs / at.TEN_TD_DENOISE).write_text(f"ma={ma3}\nxong=1\ntong=3\n", encoding="utf-8")
        vong()
        hop3 = app._xl["hop"]
        hop3.btn_dung.invoke()
        vong()
        f_dung = jobs / at.TEN_DUNG_DENOISE
        ktra("…bấm Dừng khi Lightroom ĐANG Denoise -> gửi lệnh dừng đúng mã lượt",
             f_dung.is_file() and f_dung.read_text(encoding="utf-8").strip() == f"ma={ma3}",
             f_dung.read_text(encoding="utf-8").strip() if f_dung.is_file() else "không có file")
        ktra("…lượt kết thúc NGAY (không chờ Lightroom chạy hết), hộp nói đã dừng 1/3",
             app._xl.get("xong") and "1/3" in hop3.lbl_tong.cget("text")
             and "dừng" in hop3.lbl_tong.cget("text"),
             hop3.lbl_tong.cget("text").replace("\n", " | ")[:160])
        ktra("…nút Xử lý ảnh mở lại sau khi dừng",
             cho(lambda: str(app.btn_xu_ly.cget("state")) == "normal"))
        hop3.destroy()
        (jobs / (at.TEN_YC_DENOISE + ".claimed")).unlink()
        app.v_denoise.set(False)
        # ---------------------------------------------------------------- 3. mô phỏng
        r0 = next(r for r in app.items if r.get("new_exposure") is not None)
        mp0 = app._mp_cua(r0)
        o0 = next(o for o in app.luoi.ds if o["path"] == r0["path"])
        app.v_bu_sang.set("0.30")
        app.refresh_plan()
        vong()
        r1 = app._r_cua(r0["path"])
        mp1 = app._mp_cua(r1)
        o1 = next(o for o in app.luoi.ds if o["path"] == r0["path"])
        ktra("ô lưới mang thông số mô phỏng (Exposure SẼ ÁP)", o0.get("mp") == mp0 and mp0 is not None,
             str(mp0))
        ktra("kéo Bù sáng +0.30 -> thông số mô phỏng của ô tăng ~0.30 EV",
             mp1 is not None and abs((mp1[0] - (mp0[0] if mp0 else 0)) - 0.30) < 0.06
             and o1.get("mp") == mp1, f"{mp0} -> {mp1}")
        luoi = app.luoi
        k_mp = [k for k in luoi._anh_tk if k[0] == r0["path"]]
        ktra("ảnh nhỏ dựng lại theo thông số mới (khoá ảnh có mp)",
             any(k[-1] == mp1 for k in k_mp) or not k_mp, str(k_mp[-1:] if k_mp else "chưa vẽ"))
        import mo_phong_anh
        from PIL import Image
        im = Image.new("RGB", (40, 30), (100, 100, 100))
        sang = mo_phong_anh.ap(im, (0.5, None)).getpixel((0, 0))[0]
        toi = mo_phong_anh.ap(im, (-0.5, None)).getpixel((0, 0))[0]
        ktra("mo_phong_anh: +EV sáng hơn, −EV tối hơn, 0 giữ nguyên",
             sang > 100 > toi and mo_phong_anh.ap(im, None) is im, f"{toi} < 100 < {sang}")
        # ---------------------------------------------------------------- 1. lưới theo Lightroom
        app.v_source.set(ag.SOURCES[1][0])                  # nguồn catalog
        app.scan_folder()
        vong()
        ktra("nguồn catalog: nhờ plugin theo dõi danh sách ảnh của buổi",
             (jobs / at.TEN_THEO_DOI_DS).is_file()
             and str(buoi.resolve()) in (jobs / at.TEN_THEO_DOI_DS).read_text(encoding="utf-8"))
        ds_all = sorted(str(p) for p in buoi.glob("*.ARW"))

        def ghi_ds(ds):
            (jobs / at.TEN_DS_CATALOG).write_text(
                f"#thu_muc={buoi}\n#trong_catalog=1\n#so={len(ds)}\n#khi=x\n" + "\n".join(ds) + "\n",
                encoding="utf-8")
        ghi_ds(ds_all[2:])                                   # Lightroom đã xoá 2 ảnh
        app._soi_xuat()
        vong()
        ktra("Lightroom xoá 2 ảnh -> lưới chỉ còn 4", len(app.luoi.ds) == 4,
             f"{len(app.luoi.ds)} ô")
        st = (jobs / at.TEN_DS_CATALOG).stat()
        ghi_ds(ds_all)                                       # thêm lại
        os.utime(jobs / at.TEN_DS_CATALOG, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
        app._soi_xuat()
        vong()
        ktra("…thêm lại vào Lightroom -> lưới hiện lại đủ 6", len(app.luoi.ds) == 6,
             f"{len(app.luoi.ds)} ô")
        # ---------------------------------------------------------------- catalog đọc thẳng
        #  13/10 (v83 -> user "chưa thấy phần folder"): plugin không chạy vẫn phải có
        #  cây thư mục + lọc lưới — đọc thẳng .lrcat (catalog_lr), plugin là dự phòng.
        import sqlite3
        import catalog_lr
        (tam / "Khac").mkdir()
        con = sqlite3.connect(cat_gia)
        con.executescript(
            "create table AgLibraryRootFolder(id_local integer, absolutePath text);"
            "create table AgLibraryFolder(id_local integer, rootFolder integer, pathFromRoot text);"
            "create table AgLibraryFile(id_local integer, folder integer, baseName text, extension text);"
            "create table Adobe_images(id_local integer, rootFile integer);")
        goc_lr = str(tam).replace("\\", "/") + "/"
        con.execute("insert into AgLibraryRootFolder values (1, ?)", (goc_lr,))
        con.executemany("insert into AgLibraryFolder values (?, 1, ?)",
                        [(10, ""), (11, buoi.name + "/"), (12, "Khac/")])
        anh_lr = [f"SK_{i}" for i in range(6) if i != 3]          # Lightroom đã xoá SK_3
        con.executemany("insert into AgLibraryFile values (?, 11, ?, 'ARW')",
                        list(enumerate(anh_lr, 100)))
        con.executemany("insert into AgLibraryFile values (?, 12, ?, 'ARW')",
                        [(200 + k, f"K{k}") for k in range(12)])
        con.execute("insert into Adobe_images select id_local, id_local from AgLibraryFile")
        con.commit()
        con.close()
        catalog_lr._DEM.clear()
        ktra("catalog_lr: ảnh của buổi theo catalog (5, thiếu SK_3)",
             len(catalog_lr.anh_trong_thu_muc(buoi) or ()) == 5)
        app._soi_xuat()
        vong()
        ktra("lưới theo catalog đọc thẳng (plugin không chạy cũng lọc): còn 5",
             len(app.luoi.ds) == 5 and not any(Path(o["path"]).name == "SK_3.ARW"
                                                for o in app.luoi.ds), f"{len(app.luoi.ds)} ô")
        # ---------------------------------------------------------------- cột Thư mục
        app._dat_cot_thu_muc()
        vong()
        cay = app.cot_thu_muc.cay
        k_b = os.path.normcase(os.path.normpath(str(buoi)))
        ktra("cột Thư mục: cây từ Lightroom, buổi đang mở được chọn sẵn",
             cay.exists(k_b) and cay.selection() == (k_b,)
             and cay.set(os.path.normcase(os.path.normpath(str(tam))), "so") == "17",
             f"{cay.selection()} · gộp {cay.set(os.path.normcase(os.path.normpath(str(tam))), 'so')}")
        k_k = os.path.normcase(os.path.normpath(str(tam / "Khac")))
        cay.selection_set(k_k)
        vong()
        ktra("bấm một thư mục khác -> mở buổi đó",
             os.path.normcase(os.path.normpath(app.v_folder.get())) == k_k, app.v_folder.get())
        ktra("cột Thư mục LUÔN có ở Cân sáng (cửa sổ 1600 px: đầy đủ, ngoài cùng, cột Cảnh lùi vào)",
             app.cot_thu_muc.winfo_ismapped() and not app.cot_thu_muc.gon
             and app.cot_thu_muc.grid_info().get("column") == 0)
        #  13/10 (user): chưa phân tích = chưa có cảnh -> cột Cảnh ẩn
        ktra("buổi chưa phân tích: cột Cảnh ẨN", not app.items and not app.cot_canh.winfo_ismapped())
        app.cot_thu_muc.btn_gon.invoke()
        vong()
        ktra("bấm ‹ -> thu gọn thành dải hẹp, vẫn còn nút mở lại",
             app.cot_thu_muc.gon and app.cot_thu_muc.winfo_ismapped()
             and app.cot_thu_muc.btn_mo_rong.winfo_ismapped()
             and app.cot_thu_muc.winfo_width() < 80, f"{app.cot_thu_muc.winfo_width()} px")
        app.cot_thu_muc.btn_mo_rong.invoke()
        vong()
        ktra("bấm biểu tượng thư mục -> mở lại đầy đủ", not app.cot_thu_muc.gon
             and app.cot_thu_muc.cay.winfo_ismapped())
    finally:
        at.LR_JOB_DIR, at.analyze = job_cu, analyze_cu
        try:
            root.destroy()
        except Exception:                                    # noqa: BLE001
            pass
        shutil.rmtree(tam, ignore_errors=True)
    print("TAT CA DAT" if not LOI else f"{len(LOI)} LOI")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
