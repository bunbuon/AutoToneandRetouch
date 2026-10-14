# -*- coding: utf-8 -*-
"""Kiểm CHẤM SAO + LỌC SAO trên lưới Cân sáng (14/10).

User 14/10: "Thêm tính năng nhận diện ảnh rate theo mức trong lightroom. Bên ngoài
preview cũng thêm tính năng rate ảnh 1-5 sao như Lr. Và filter preview theo mức rate".

Giao diện THẬT (App), catalog Lightroom GIẢ (SQLite, có rating + bản sao ảo), "plugin"
giả: nhịp khai kha_nang, Lightroom "nhận" = đổi rating trong catalog giả.
  1. Số sao ĐANG có trong Lightroom (catalog) hiện trên ô; bản sao ảo không đè ảnh gốc.
  2. Lọc ≥ / = / ≤ k sao, "Chưa có sao", bấm lại đúng k = bỏ lọc; số đếm.
  3. Phím 0–5 chấm cho các tấm ĐANG CHỌN (Ctrl + bấm), hiện ngay, gửi request_sao.txt.
  4. Bấm sao thứ k dưới ô = k sao; bấm lại đúng số đó = bỏ sao; không đổi tấm đang chọn.
  5. Lightroom nhận xong -> số sao lấy lại từ catalog, thôi đè.
  6. Plugin cũ (không khai sao1) / nguồn .xmp -> không gửi gì, nói rõ lý do.
  7. Ảnh lớn: phím 0–5 chấm tấm đang xem; nhãn dưới ảnh hiện ★.
Chạy:  python test_cham_sao.py
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

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


#  SK_0 chưa chấm · SK_1 1★ · SK_2 3★ · SK_3 5★ · SK_4 chưa (bản sao ảo 4★) · SK_5 2★
SAO_LR = {0: None, 1: 1.0, 2: 3.0, 3: 5.0, 4: None, 5: 2.0}


def dung_catalog(cat: Path, tam: Path, buoi: Path, sao: dict) -> None:
    if cat.exists():
        cat.unlink()
    con = sqlite3.connect(cat)
    con.executescript(
        "create table AgLibraryRootFolder(id_local integer, absolutePath text);"
        "create table AgLibraryFolder(id_local integer, rootFolder integer, pathFromRoot text);"
        "create table AgLibraryFile(id_local integer, folder integer, baseName text, extension text);"
        "create table Adobe_images(id_local integer, rootFile integer, rating real, "
        "masterImage integer);")
    con.execute("insert into AgLibraryRootFolder values (1, ?)",
                (str(tam).replace("\\", "/") + "/",))
    con.executemany("insert into AgLibraryFolder values (?, 1, ?)", [(10, ""), (11, buoi.name + "/")])
    con.executemany("insert into AgLibraryFile values (?, 11, ?, 'ARW')",
                    [(100 + i, f"SK_{i}") for i in range(6)])
    con.executemany("insert into Adobe_images values (?, ?, ?, NULL)",
                    [(100 + i, 100 + i, sao[i]) for i in range(6)])
    con.execute("insert into Adobe_images values (900, 104, 4.0, 104)")   # bản sao ảo của SK_4
    con.commit()
    con.close()
    st = cat.stat()
    os.utime(cat, ns=(st.st_atime_ns, st.st_mtime_ns + int(time.time() * 1000) % 997 * 1_000_000))


def main() -> int:
    tam = Path(tempfile.mkdtemp(prefix="cham_sao_"))
    os.environ["AUTOTONE_DATA"] = str(tam / "du_lieu")
    cat = tam / "Gia.lrcat"
    os.environ["AUTOTONE_CATALOG_LR"] = str(cat)
    os.environ.pop("AUTOTONE_NGON_NGU", None)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import autotone as at
    import catalog_lr
    import test_giao_dien_gon as tg

    buoi = tam / "SuKien"
    buoi.mkdir()
    for i in range(6):
        tg.raw_gia(buoi / f"SK_{i}.ARW", mau=(90 + 20 * i, 120, 150))
    dung_catalog(cat, tam, buoi, SAO_LR)
    k = {i: at.khoa_duong_dan(str(buoi / f"SK_{i}.ARW")) for i in range(6)}
    # ---------------------------------------------------------------- 1. catalog
    d = catalog_lr.sao_trong_thu_muc(buoi) or {}
    ktra("catalog_lr.sao_trong_thu_muc: số sao Lightroom (NULL = 0), bản sao ảo không đè",
         [d.get(k[i]) for i in range(6)] == [0, 1, 3, 5, 0, 2], str([d.get(k[i]) for i in range(6)]))
    ktra("anh_trong_thu_muc vẫn là tập ảnh của buổi", catalog_lr.anh_trong_thu_muc(buoi) == set(d))

    import tkinter as tk
    import autotone_gui as ag
    import giao_dien as gd
    root = tk.Tk()
    ag.bq.kiem = lambda: {"co_phep": True, "con_lai": timedelta(days=300), "nhac": "",
                          "goi": "1 năm", "may": "TEST01", "het_han": False, "ly_do": ""}
    root.geometry("1600x940+0+0")
    gd.dat_theme(root)
    job_cu = at.LR_JOB_DIR
    jobs = tam / "jobs"
    jobs.mkdir()
    at.LR_JOB_DIR = jobs
    nhip = jobs / at.NHIP_PLUGIN
    nhip.write_text("gen=1\nkha_nang=curve1,sao1\n", encoding="utf-8")
    f_yc = jobs / at.TEN_YC_SAO
    try:
        app = ag.App(root)
        app.grid(row=0, column=0, sticky="nsew")

        def vong(n=4):
            for _ in range(n):
                root.update_idletasks()
                root.update()
                time.sleep(0.02)

        vong(8)
        app.v_source.set(ag.SOURCES[1][0])                       # catalog Lightroom
        app.v_folder.set(str(buoi))
        app.scan_folder()
        app._soi_xuat()
        vong()

        def sao_o():
            return {Path(o["path"]).stem: int(o.get("sao") or 0) for o in app.luoi.ds}

        ktra("lưới: mỗi ô mang số sao ĐANG có trong Lightroom",
             sao_o() == {"SK_0": 0, "SK_1": 1, "SK_2": 3, "SK_3": 5, "SK_4": 0, "SK_5": 2},
             str(sao_o()))
        vong()
        ktra("ô có sao vẽ hàng 5 sao dưới ảnh (ảnh chưa chấm thì chưa vẽ)",
             len(app.luoi.canvas.find_withtag("sao")) == 5 * 4,
             f"{len(app.luoi.canvas.find_withtag('sao'))} ngôi sao")
        # ---------------------------------------------------------------- 2. lọc
        ls = app.loc_sao
        h = ls._hinh()

        def bam_sao(kk):
            ls._bam(SimpleNamespace(x=h["x_sao"] + (kk - 0.5) * h["w_sao"]))
            vong()

        def ten_o():
            return sorted(Path(o["path"]).stem for o in app.luoi.ds)

        ktra("bộ lọc Sao có ở đầu trang, mặc định không lọc",
             ls.winfo_ismapped() and ls.loc() is None and len(app.luoi.ds) == 6)
        bam_sao(3)
        ktra("bấm ★3 -> chỉ ảnh ≥ 3 sao, số đếm 2", ten_o() == ["SK_2", "SK_3"]
             and ls._so == "2", f"{ten_o()} · {ls._so!r}")
        ls._bam(SimpleNamespace(x=h["x_phep"] + 2))
        vong()
        ktra("bấm dấu so sánh -> '=': đúng 3 sao", ls.phep == "eq" and ten_o() == ["SK_2"],
             str(ten_o()))
        ls._bam(SimpleNamespace(x=h["x_phep"] + 2))
        vong()
        ktra("… '≤': từ 3 sao trở xuống (gồm ảnh chưa chấm)", ls.phep == "le"
             and ten_o() == ["SK_0", "SK_1", "SK_2", "SK_4", "SK_5"], str(ten_o()))
        bam_sao(3)
        ktra("bấm lại đúng ★3 -> bỏ lọc, đủ 6 ảnh", ls.loc() is None and len(app.luoi.ds) == 6)
        ls.chip_chua.event_generate("<ButtonRelease-1>")
        ls._chon("chua") if ls.loc() is None else None        # event_generate cần cửa sổ hiện
        vong()
        ktra("'Chưa có sao' -> chỉ ảnh 0 sao", ten_o() == ["SK_0", "SK_4"], str(ten_o()))
        ls._chon("chua")
        vong()
        ls.phep = "ge"
        ktra("bấm lại 'Chưa có sao' -> bỏ lọc", ls.loc() is None and len(app.luoi.ds) == 6)
        # ---------------------------------------------------------------- 3. phím 0–5
        p0, p1 = str(buoi / "SK_0.ARW"), str(buoi / "SK_1.ARW")
        app.luoi.chon(p0)
        app.luoi.da_chon = {p0, p1}                              # Ctrl + bấm SK_1
        ktra("phím 0–5 có gắn trên lưới", bool(app.luoi.canvas.bind("4"))
             and bool(app.luoi.canvas.bind("<KP_4>")))
        app.luoi._sao_phim(4)
        vong()
        ktra("phím 4 khi chọn 2 ảnh -> cả hai hiện 4★ NGAY", sao_o()["SK_0"] == 4
             and sao_o()["SK_1"] == 4, str(sao_o()))
        ktra("…gửi Lightroom request_sao.txt đúng 2 ảnh, 4 sao",
             f_yc.is_file() and at._doc_yc_sao(f_yc) == {p0: 4, p1: 4}, str(at._doc_yc_sao(f_yc)))
        app.luoi.da_chon = {p1}
        app.luoi.dang_chon = p1
        app.luoi._sao_phim(0)
        vong()
        ktra("phím 0 trên SK_1 -> bỏ sao; yêu cầu chưa nhận thì GỘP (SK_0 vẫn 4)",
             at._doc_yc_sao(f_yc) == {p0: 4, p1: 0} and sao_o()["SK_1"] == 0,
             str(at._doc_yc_sao(f_yc)))
        # ---------------------------------------------------------------- 4. bấm sao dưới ô
        p5 = str(buoi / "SK_5.ARW")
        app.luoi.chon(p1, cuon_toi=False)
        vong()
        i5 = app.luoi._vi_tri[p5]
        app.luoi._ve_that()
        hop = app.luoi._hop_sao.get(i5)
        ktra("ô SK_5 có vùng hàng sao để bấm", hop is not None)
        if hop:
            x0, y0, w, hh = hop
            cy = app.luoi.canvas.canvasy(0)
            e = SimpleNamespace(x=x0 + 4.5 * w, y=y0 + hh / 2 - cy)
            app.luoi._bam(e)
            vong()
            ktra("bấm ★5 dưới SK_5 -> 5 sao, tấm đang chọn KHÔNG đổi (vẫn SK_1)",
                 sao_o()["SK_5"] == 5 and at._doc_yc_sao(f_yc).get(p5) == 5
                 and app.luoi.dang_chon == p1, f"{sao_o()['SK_5']} · {app.luoi.dang_chon}")
            app.luoi._ve_that()
            x0, y0, w, hh = app.luoi._hop_sao[i5]
            app.luoi._bam(SimpleNamespace(x=x0 + 4.5 * w, y=y0 + hh / 2 - cy))
            vong()
            ktra("bấm lại đúng ★5 -> bỏ sao", sao_o()["SK_5"] == 0
                 and at._doc_yc_sao(f_yc).get(p5) == 0)
            ktra("bấm đúp lên hàng sao không mở ảnh lớn",
                 app.luoi._bam_dup(SimpleNamespace(x=x0 + 4.5 * w, y=y0 + hh / 2 - cy)) == "break")
        # ---------------------------------------------------------------- 5. Lightroom nhận
        f_yc.unlink()
        moi = dict(SAO_LR)
        moi.update({0: 4.0, 1: None, 5: None})
        dung_catalog(cat, tam, buoi, moi)
        catalog_lr._DEM.clear()
        app._soi_xuat()
        vong()
        ktra("Lightroom đã đặt xong -> sao lấy từ catalog, hết phần 'chờ'",
             sao_o()["SK_0"] == 4 and sao_o()["SK_1"] == 0 and sao_o()["SK_5"] == 0
             and not app._sao_cho, f"{sao_o()} · chờ {len(app._sao_cho)}")
        dung_catalog(cat, tam, buoi, {**moi, 2: 1.0})
        catalog_lr._DEM.clear()
        app._soi_xuat()
        vong()
        ktra("chấm sao NGAY TRONG Lightroom -> lưới đổi theo (3 giây một lần)",
             sao_o()["SK_2"] == 1, str(sao_o()))
        # ---------------------------------------------------------------- 6. không gửi được
        nhip.write_text("gen=1\nkha_nang=curve1\n", encoding="utf-8")
        app._cham_sao([p0], 2)
        vong()
        ktra("plugin cũ (không khai sao1) -> KHÔNG gửi, dòng trạng thái nói cài lại",
             not f_yc.exists() and "bản cũ" in str(app.lbl_status.cget("text")),
             str(app.lbl_status.cget("text"))[:90])
        nhip.write_text("gen=1\nkha_nang=curve1,sao1\n", encoding="utf-8")
        # ---------------------------------------------------------------- 7. ảnh lớn
        p2 = str(buoi / "SK_2.ARW")
        app._mo_mot_ct(p2)
        vong(8)
        ktra("ảnh lớn: nhãn dưới ảnh hiện số sao Lightroom (★)",
             "★" in str(app.lbl_mot_ct.cget("text")), str(app.lbl_mot_ct.cget("text")))
        ktra("ảnh lớn: phím 0–5 có gắn", bool(app.xem_ct.canvas.bind("3")))
        app._cham_sao([app._anh_ct], 3)
        vong()
        ktra("chấm 3★ ở ảnh lớn -> gửi đúng tấm đang xem, nhãn đổi ★★★",
             at._doc_yc_sao(f_yc) == {p2: 3} and "★★★" in str(app.lbl_mot_ct.cget("text")),
             str(app.lbl_mot_ct.cget("text")))
        app._ve_luoi_ct()
        f_yc.unlink()
        app.v_source.set(ag.SOURCES[0][0])
        app._cham_sao([p0], 1)
        ktra("nguồn .xmp -> không gửi, nói cần nguồn catalog",
             not f_yc.exists() and "catalog" in str(app.lbl_status.cget("text")))
    finally:
        at.LR_JOB_DIR = job_cu
        try:
            root.destroy()
        except Exception:                                    # noqa: BLE001
            pass
        shutil.rmtree(tam, ignore_errors=True)
    print("TAT CA DAT" if not LOI else f"{len(LOI)} LOI")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
