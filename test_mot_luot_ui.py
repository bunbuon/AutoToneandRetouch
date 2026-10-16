# -*- coding: utf-8 -*-
"""Chuỗi màu da MỘT LƯỢT trong nút Xử lý ảnh (xu_ly_anh_ui — 14/10) — giao diện THẬT.

App THẬT + "plugin" giả. Đo trước (do_truoc.chay) / tính kế hoạch được thay bằng hàm giả
(phần đó có bài riêng: test_do_truoc, test_mau_mot_luot); bài này canh LUỒNG của hộp
Xử lý ảnh.

Mục kiểm
    1. tắt / chưa học màu Lightroom -> đi thẳng sang Áp; tổng kết chỉ tới menu học màu (15/10:
       nút trong app thay HOC_MAU_LR.bat), máy đủ ảnh chưa học -> nút "Học màu máy này…";
       công tắc "Chế độ nhanh một lượt" nhớ qua lần mở sau
    2. bật + có mô hình -> pha "đo da trên preview Lightroom" -> tính lại kế hoạch -> Áp
    3. Dừng lúc đang đo trước -> "Đã dừng", chưa áp gì
    4. áp xong: ảnh một lượt CHỈ SOÁT (một ảnh mỗi loạt + ảnh lẻ), ảnh đường cũ đo đủ
    5. ảnh soát lệch dự đoán + ngoài vùng ổn -> cả loạt vào job curve (kể cả tấm không đo);
       loạt khớp dự đoán không đụng; tổng kết "Màu da một lượt … soát … hoàn thiện thêm"

Chạy:  python test_mot_luot_ui.py
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
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
    tam = Path(tempfile.mkdtemp(prefix="mot_luot_ui_"))
    os.environ["AUTOTONE_DATA"] = str(tam / "du_lieu")
    os.environ["AUTOTONE_CATALOG_LR"] = "0"
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import autotone as at
    import curve_da as cd
    import do_truoc
    import mau_mot_luot as ml
    import test_curve_da as T
    import tkinter as tk
    import autotone_gui as ag
    import giao_dien as gd
    from PIL import Image

    T.cai_gia()
    jobs = tam / "jobs"
    jobs.mkdir()
    at.LR_JOB_DIR = jobs
    buoi = tam / "Buoi"
    buoi.mkdir()
    (jobs / at.NHIP_PLUGIN).write_text("vong=1\nkha_nang=curve1,xem1,truoc1\n", encoding="utf-8")
    root = tk.Tk()
    ag.bq.kiem = lambda: {"co_phep": True, "con_lai": timedelta(days=300), "nhac": "",
                          "goi": "1 năm", "may": "TEST01", "het_han": False, "ly_do": ""}
    root.geometry("1600x940+0+0")
    gd.dat_theme(root)
    try:
        app = ag.App(root)
        #  17/10: Quy trình Auto mặc định BẬT, mẫu da tự chọn gợi ý theo loại buổi — bài này kiểm
        #  luồng thường với mẫu "Mặc định"
        app.v_auto_lr.set(False)
        app.v_mau_da.set(ag.MAU_DA_MAC_DINH)
        app.grid(row=0, column=0, sticky="nsew")

        def vong(n=4):
            for _ in range(n):
                root.update_idletasks()
                root.update()
                time.sleep(0.02)

        def cho(dieu, giay=40.0):
            het = time.time() + giay
            while time.time() < het:
                vong(1)
                if dieu():
                    return True
            return False

        vong(8)
        app.folder = lambda: buoi
        app.source_value = lambda: "catalog"
        app.cfg["source"] = "catalog"
        DICH = [227, 184, 185]                       # da của ảnh giả T.canh() = đích
        doc_cfg = app.read_cfg

        def cfg_(**kw):
            #  bài này canh LUỒNG; kéo sáng về L đích (14/10) có bài riêng (test_mau_mot_luot) —
            #  ảnh giả không cùng độ sáng với màu đích nên tắt ở đây
            return dict(doc_cfg(), mau_da_dich={"ten": "m", "trong": DICH}, curve_da=True,
                        curve_chay=False, mot_luot_sang_dich=False, **kw)
        app.read_cfg = lambda: cfg_(mau_mot_luot=True)

        def mo_luot(items, pha="do"):
            t = time.monotonic()
            app._xl = {"t0": t - 2.0, "pha": pha, "hop": None, "xong": False,
                       "items_ghi": items, "so_gui": len(items), "job": jobs / "apply_x_Buoi.tsv",
                       "moc": {"phan_tich": t - 1.0, "gui": t - 0.5}}
            app._xl_bat_dau(0, len(items), len(items))
            return app._xl["hop"]

        ap_goi = []
        app.do_apply = lambda **kw: ap_goi.append(kw)
        ke_hoach = []

        # ------------------------------------------------------------ 1
        print("1. tắt / chưa học")
        items = [dict(T.anh("A"), path=str(buoi / "A.ARW"), model="ILCE-7M4")]
        hop = mo_luot(items)
        ktra("tắt mau_mot_luot -> không đo trước", app._xl_bat_truoc(items, cfg_(mau_mot_luot=False)) is False)
        ktra("bật mà chưa học màu cho máy -> không đo trước, nhớ lý do",
             app._xl_bat_truoc(items, cfg_(mau_mot_luot=True)) is False
             and app._xl.get("truoc_kq", {}).get("bo") == "chua-hoc")
        ktra("…tổng kết chỉ tới menu học màu (tên máy), không còn HOC_MAU_LR.bat",
             "Học màu Lightroom cho máy ảnh này" in app._xl_cau_mot_luot(app._xl)
             and "HOC_MAU_LR" not in app._xl_cau_mot_luot(app._xl)
             and "ILCE-7M4" in app._xl_cau_mot_luot(app._xl), app._xl_cau_mot_luot(app._xl))
        ktra("…1 ảnh (< 6) -> không gợi ý học máy đó", app._xl.get("ml_thieu") == [])
        hop.destroy()
        sau = [dict(T.anh(f"S{i}"), path=str(buoi / f"S{i}.ARW"), model="ILCE-7M4") for i in range(6)]
        hop = mo_luot(sau)
        app._xl_bat_truoc(sau, cfg_(mau_mot_luot=True))
        ktra("máy đủ 6 ảnh chưa có mô hình -> ml_thieu có khoá máy đó",
             app._xl.get("ml_thieu") == [ml.khoa_cua(sau[0])], str(app._xl.get("ml_thieu")))
        hoc_goi = []
        app.hoc_mau_lr = lambda khoa_ds=None: hoc_goi.append(khoa_ds)
        app._xl["items_ghi"] = []
        app._xl_ket_thuc("xong")
        ktra("tổng kết có nút 'Học màu máy này…' -> mở học màu với đúng máy",
             getattr(hop, "btn_them", None) is not None and (hop.btn_them.invoke() or True)
             and hoc_goi == [[ml.khoa_cua(sau[0])]], str(hoc_goi))
        del app.hoc_mau_lr
        import thanh_luoi
        app.v_mot_luot.set(True)
        ktra("công tắc một lượt: bật -> read_cfg có mau_mot_luot, nhớ vào luoi_xem.json",
             doc_cfg()["mau_mot_luot"] is True and thanh_luoi.doc_kv("mau_mot_luot") is True)
        app.v_mot_luot.set(False)
        ktra("…tắt -> nhớ False", doc_cfg()["mau_mot_luot"] is False and thanh_luoi.doc_kv("mau_mot_luot") is False)
        #  16/10 (user chọn "Mặc định cũng là đích"): mẫu Mặc định = đích -> chuỗi màu da + một lượt chạy
        md0 = doc_cfg().get("mau_da_dich") or {}
        ktra("mẫu da 'Mặc định': read_cfg có đích mặc định (chuỗi màu da + một lượt chạy được)",
             md0.get("mac_dinh") and md0.get("trong") and md0.get("ngoai"), str(md0))
        hop.destroy()
        #  15/10 (v91, lọc 1037): plan() bỏ HẾT ảnh (cả buổi bị coi là sửa tay) -> bảng không
        #  sập (min() của rỗng), hộp Xử lý ảnh báo rõ, không gửi Áp
        hop = mo_luot([])
        app.items = []
        at.SO_ANH_NGUOI_SUA, at.CANH_BAO_XUAT, at.CANH_BAO_PLUGIN = 361, "", ""
        try:
            app._fill_table()
            loi_bang = ""
        except Exception as ex:                              # noqa: BLE001
            loi_bang = repr(ex)
        ktra("bảng tổng kết với 0 ảnh không sập", not loi_bang, loi_bang)
        n_ap = len(ap_goi)
        app.cancel_flag = False
        app._xl_sau_do([], cfg_(mau_mot_luot=False))
        ktra("0 ảnh còn để áp -> hộp kết thúc, nói rõ 'sửa tay', không gửi Áp",
             app._xl.get("xong") and "sửa tay" in hop.lbl_tong.cget("text") and len(ap_goi) == n_ap,
             hop.lbl_tong.cget("text")[:120])
        at.SO_ANH_NGUOI_SUA = 0

        # ------------------------------------------------------------ 2
        print("2. đo trước -> tính lại -> áp")
        ml.mo_hinh_cho = lambda r: object()
        do_goi = []

        def chay_gia(root_, items_, cfg, huy=None, bao=None, **k):
            do_goi.append(len(items_))
            for x in items_:
                x["lr_truoc"] = {"ok": True}
            bao(1, 1, "đo da trên preview Lightroom 1/1")
            return {"tong": 1, "cache": 1, "plugin": 0, "do": 1, "loi": 0, "khong_co": 0}
        do_truoc.chay = chay_gia

        def tinh_lai():
            ke_hoach.append(threading.current_thread().name)
            for x in app.items or []:
                if x.get("lr_truoc"):
                    x["mot_luot"] = True
        app.refresh_plan = tinh_lai
        app._plan_tinh = tinh_lai          # 16/10: tính lại sau đo trước chạy ở luồng nền
        app._plan_ve = lambda: None        # (refresh_plan giả trước đây không vẽ bảng)
        app.items = items
        hop = mo_luot(items)
        ap_goi.clear()
        ok = app._xl_sau_do(items, cfg_(mau_mot_luot=True))
        ktra("bắt đầu pha 'đo da trên preview Lightroom'", ok and app._xl["pha"] == "truoc"
             and "preview" in str(tk.Label.cget(hop.hang["do"][2], "text")), str(app._xl["pha"]))
        ktra("…xong: tính lại kế hoạch rồi gửi Áp", cho(lambda: bool(ap_goi)) and ke_hoach
             and app._xl["pha"] == "ap" and app._xl.get("n_mot_luot") == 1, f"{app._xl['pha']} {ke_hoach}")
        ktra("…tính lại kế hoạch ở LUỒNG NỀN (16/10: trên luồng giao diện Windows báo treo)",
             ke_hoach and ke_hoach[-1] == "tinh_ke_hoach", str(ke_hoach))
        #  hai yêu cầu chồng nhau: lần hai chờ lần đầu xong rồi tính MỘT lần nữa, cả hai được báo
        cham = []

        def tinh_cham():
            cham.append(threading.current_thread().name)
            time.sleep(0.4)
        app._plan_tinh = tinh_cham
        bao = []
        app.refresh_plan_nen(lambda loi: bao.append(("a", loi)))
        app.refresh_plan_nen(lambda loi: bao.append(("b", loi)))
        ktra("hai lần tính nền chồng nhau -> tính 2 lần nối tiếp, mỗi xong() gọi đúng một lần",
             cho(lambda: len(bao) == 2, 10) and len(cham) == 2 and sorted(x[0] for x in bao) == ["a", "b"]
             and not getattr(app, "_plan_dang", False), f"{cham} {bao}")
        app._plan_tinh = tinh_lai
        ktra("…bước Đo ghi số ảnh đo trên preview (từ cache)",
             "cache" in str(tk.Label.cget(hop.hang["do"][2], "text")), str(tk.Label.cget(hop.hang["do"][2], "text")))
        hop.destroy()

        # ------------------------------------------------------------ 3
        print("3. Dừng lúc đo trước")
        cho_huy = threading.Event()

        def chay_cham(root_, items_, cfg, huy=None, bao=None, **k):
            while not huy():
                time.sleep(0.05)
            cho_huy.set()
            return {"tong": 1, "do": 0}
        do_truoc.chay = chay_cham
        hop = mo_luot(items)
        ap_goi.clear()
        app._xl_sau_do(items, cfg_(mau_mot_luot=True))
        vong(5)
        app._xl_dung()
        ktra("Dừng -> 'Đã dừng', không áp", cho(lambda: app._xl.get("xong")) and not ap_goi
             and hop.lbl_tieu_de.cget("text") == "Đã dừng" and cho_huy.is_set(), hop.lbl_tieu_de.cget("text"))
        hop.destroy()

        # ------------------------------------------------------------ 4-5
        print("4-5. soát sau khi áp")
        t0 = T.anh("x")["dt_obj"]
        anh_cua = {}

        def r_(ten, giay, canh, lech=(0.0, 0.0, 0.0), mot_luot=True):
            r = dict(T.anh(ten, dt=t0 + timedelta(seconds=giay), scene=canh), path=str(buoi / f"{ten}.ARW"))
            r.update(new_exposure=0.0, delta_ev=0.0, mot_luot=mot_luot)
            anh_cua[ten] = T.u8(T.canh(lech=lech))
            return r
        L1 = [r_(f"L1{i}", i * 2, 0, lech=(0.03, 0.0, -0.02)) for i in range(3)]       # da đỏ: lệch
        L2 = [r_(f"L2{i}", 300 + i * 2, 0) for i in range(3)]                          # khớp
        LE = r_("LE", 7200, 3)                                                          # ảnh lẻ
        CU = r_("CU", 9000, 4, mot_luot=False)                                         # đường cũ
        ml_ds = L1 + L2 + [LE]
        #  dự đoán: L1 dự đoán da ĐÚNG đích (sai thật), L2 / LE dự đoán khớp ảnh thật
        cfg4 = cfg_(mau_mot_luot=True)
        for r in ml_ds:
            p = tam / f"{Path(r['path']).stem}_do.png"
            Image.fromarray(anh_cua[Path(r["path"]).stem]).save(p)
            do = cd.do_anh(r, p, cfg4)
            lab_ = cd.thong_ke(do["da_cu"], do["mien"])
            h, q = cd.hue_q(lab_)
            if r in L1:
                h, q = cd.hue_q(at.mau_dich_lab(DICH))
            #  14/10: soát xét cả L — dự đoán L đúng bằng số đo (ảnh giả không lệch sáng)
            r["du_doan_lr"] = {"h": h, "q": q, "L": float(lab_[0]), "kieu": "cu", "trung_ab": None,
                               "khoa": "k", "ngoai_pham_vi": []}
        items = ml_ds + [CU]
        hop = mo_luot(items, pha="ap")
        app._xl["n_mot_luot"] = len(ml_ds)
        app._xl_job(app._xl["job"], "mat")
        ktra("gửi yêu cầu dựng lượt 2", cho(lambda: cd.dang_cho(jobs), 5))
        yc = (jobs / cd.TEN_YEU_CAU).read_text(encoding="utf-8").splitlines()
        anh = sorted(Path(d.split("=", 1)[1]).stem for d in yc if d.startswith("anh="))
        ktra("chỉ SOÁT: một ảnh mỗi loạt + ảnh lẻ + ảnh đường cũ (4 / 8 ảnh)",
             len(anh) == 4 and "CU" in anh and "LE" in anh and sum(a.startswith("L1") for a in anh) == 1
             and sum(a.startswith("L2") for a in anh) == 1, str(anh))
        dest = Path(next(d.split("=", 1)[1] for d in yc if d.startswith("dest=")))
        ma = next(d.split("=", 1)[1] for d in yc if d.startswith("ma="))
        (jobs / cd.TEN_YEU_CAU).unlink()
        dest.mkdir(parents=True, exist_ok=True)
        for t in anh:
            Image.fromarray(anh_cua[t]).save(dest / f"{t}.jpg", quality=97)
        (jobs / cd.TEN_BANG).write_text("path\tjpg\n" + "".join(
            f"{buoi / t}.ARW\t{dest / t}.jpg\n" for t in anh), encoding="utf-8")
        (jobs / cd.TEN_TIEN_DO).write_text(f"trang_thai=xong\nxong={len(anh)}\ntong={len(anh)}\nloi=0\nma={ma}\n",
                                          encoding="utf-8")
        ktra("đo xong -> job @curve", cho(lambda: app._xl.get("pha") == "curve_ap"), str(app._xl.get("pha")))
        sa = app._xl.get("ml_soat") or {}
        ktra("soát 3 ảnh, 1 lệch (loạt L1)", sa.get("n") == 3 and sa.get("lech") == 1, str({k: sa.get(k) for k in ("n", "lech", "hue", "q", "sua")}))
        rows = cd.doc_job(Path(app._xl["curve_job"]))
        ten = sorted(Path(k).stem.upper() for k in rows)
        ktra("job curve: cả loạt L1 (kể cả 2 tấm không đo) + ảnh đường cũ; L2 / LE không đụng",
             all(f"L1{i}" in ten for i in range(3)) and not any(t.startswith("L2") or t == "LE" for t in ten),
             str(ten))
        os.replace(app._xl["curve_job"], Path(app._xl["curve_job"]).with_suffix(".done"))
        ktra("Lightroom áp -> 'Xử lý xong'", cho(lambda: app._xl.get("xong"), 20)
             and hop.lbl_tieu_de.cget("text") == "Xử lý xong", hop.lbl_tieu_de.cget("text"))
        tong = hop.lbl_tong.cget("text")
        ktra("tổng kết: 'Màu da một lượt … soát 3 ảnh … hoàn thiện thêm'",
             "Màu da một lượt" in tong and "soát 3 ảnh" in tong and "hoàn thiện thêm" in tong,
             tong.replace("\n", " | ")[:300])
        import mo_hinh_lr as mh
        ktra("lịch sử lệch dự đoán ghi vào mo_hinh_lr/lich_su.jsonl", (mh.thu_muc() / "lich_su.jsonl").is_file())
        hop.destroy()
    finally:
        try:
            root.destroy()
        except Exception:                                    # noqa: BLE001
            pass
        shutil.rmtree(tam, ignore_errors=True)
    print(f"\n{len(LOI)} LOI" if LOI else "\nTAT CA DAT")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
