# -*- coding: utf-8 -*-
"""Bước "Curve da mặt & vùng cháy" trong chuỗi Xử lý ảnh (13/10) — giao diện THẬT.

User 13/10: sau WB + Tone, đo lại da trên ảnh Lightroom dựng rồi chỉnh Curve; vùng
cháy thì nén đỉnh Curve. Chốt: mặc định TẮT, cần nguồn catalog + plugin mới.

App THẬT (autotone_gui) + "plugin" giả: nhận request_do_curve.txt, dựng ảnh (ảnh giả
test_curve_da) vào đúng thư mục + bảng, rồi đổi job @curve thành .done. Bộ dò mặt / phân
vùng mặt giả (test_curve_da.cai_gia) — đo / giải / ghép là hàm thật.

Mục kiểm
    1. hai ô Curve mặc định TẮT, có trong read_cfg; nguồn .xmp hoặc tắt -> không có bước
    2. plugin cũ (nhịp không khai curve1) -> bước "bỏ qua", tổng kết nói cài lại AutoTone
    3. đủ điều kiện: gửi yêu cầu dựng ĐÚNG ảnh đã áp (bỏ 1★), đo, gửi job @curve, Lightroom
       áp xong -> "Xử lý xong", tổng kết có dòng Curve; ảnh dựng lượt 2 đã xoá
    4. Chi tiết ảnh có báo cáo curve (da trước / sau / đích)
    5. Dừng lúc đang chờ dựng -> rút yêu cầu, lượt kết thúc "Đã dừng"

Chạy:  xvfb-run -a python3.12 test_curve_xu_ly.py
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
    tam = Path(tempfile.mkdtemp(prefix="curve_xu_ly_"))
    os.environ["AUTOTONE_DATA"] = str(tam / "du_lieu")
    os.environ["AUTOTONE_CATALOG_LR"] = "0"
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import autotone as at
    import curve_da as cd
    import test_curve_da as T
    import tkinter as tk
    import autotone_gui as ag
    import giao_dien as gd
    import xu_ly_anh_ui as xl_ui

    T.cai_gia()
    jobs = tam / "jobs"
    jobs.mkdir()
    job_cu = at.LR_JOB_DIR
    at.LR_JOB_DIR = jobs
    buoi = tam / "Buoi"
    buoi.mkdir()
    root = tk.Tk()
    ag.bq.kiem = lambda: {"co_phep": True, "con_lai": timedelta(days=300), "nhac": "",
                          "goi": "1 năm", "may": "TEST01", "het_han": False, "ly_do": ""}
    root.geometry("1600x940+0+0")
    gd.dat_theme(root)
    try:
        app = ag.App(root)
        app.grid(row=0, column=0, sticky="nsew")

        def vong(n=4):
            for _ in range(n):
                root.update_idletasks()
                root.update()
                time.sleep(0.02)

        def cho(dieu, giay=60.0):
            het = time.time() + giay
            while time.time() < het:
                vong(1)
                if dieu():
                    return True
            return False

        vong(8)
        # ------------------------------------------------------------ 1
        ktra("hai ô Curve mặc định TẮT", app.v_curve_da.get() is False and app.v_curve_chay.get() is False)
        app.v_curve_da.set(True)
        app.v_curve_chay.set(True)
        cfg = app.read_cfg()
        ktra("read_cfg mang curve_da / curve_chay", cfg.get("curve_da") is True and cfg.get("curve_chay") is True)
        app.folder = lambda: buoi
        app.source_value = lambda: "catalog"
        app.cfg["source"] = "catalog"

        def lam_items():
            ds = []
            for i, ten in enumerate(("A", "B", "C")):
                r = T.anh(ten, scene=i)
                r["path"] = str(buoi / f"{ten}.ARW")
                r.update(new_exposure=0.0, delta_ev=0.0)
                ds.append(r)
            ds[2]["rating"] = 1                                       # ảnh Loại 1★
            return ds

        def mo_luot(items):
            app._xl = {"t0": time.monotonic(), "pha": "ap", "hop": None, "xong": False,
                       "items_ghi": items, "so_gui": len(items), "job": jobs / "apply_x_Buoi.tsv"}
            app._xl_bat_dau(0, len(items), len(items))
            return app._xl["hop"]

        hop = mo_luot(lam_items())
        #  14/10 (user: "vẫn giữ áp 2 lần ... Nhưng sẽ không hiển thị ra bên ngoài")
        ktra("nguồn catalog + bật: lượt 2 BẬT nhưng hộp KHÔNG có dòng Curve riêng",
             app._xl.get("curve") is True and "curve" not in hop.hang
             and list(hop.hang) == ["do", "ap"], str(list(hop.hang)))
        hop.destroy()
        app.v_curve_da.set(False)
        app.v_curve_chay.set(False)
        hop = mo_luot(lam_items())
        ktra("tắt cả hai ô: không có lượt 2", app._xl.get("curve") is False)
        hop.destroy()
        app.v_curve_da.set(True)
        app.v_curve_chay.set(True)
        # ------------------------------------------------------------ 2. plugin cũ
        (jobs / at.NHIP_PLUGIN).write_text("vong=1\nkhi=x\n", encoding="utf-8")
        hop = mo_luot(lam_items())
        app._xl_curve()
        ktra("plugin cũ: bước Curve 'bỏ qua', không gửi yêu cầu",
             app._xl.get("curve_kq", {}).get("bo") == "plugin-cu" and not cd.dang_cho(jobs))
        ktra("…lượt vẫn kết thúc, tổng kết nói cài lại AutoTone",
             cho(lambda: app._xl.get("xong"), 10) and "cài lại AutoTone" in hop.lbl_tong.cget("text"),
             hop.lbl_tong.cget("text").replace("\n", " | ")[:200])
        hop.destroy()
        # ------------------------------------------------------------ 3. đủ điều kiện
        (jobs / at.NHIP_PLUGIN).write_text("vong=1\nkhi=x\nkha_nang=curve1\n", encoding="utf-8")
        items = lam_items()
        hop = mo_luot(items)
        app._xl_job(app._xl["job"], "mat")          # lượt 1 xong (job đã được nhận)
        ktra("lượt 1 xong: bước Áp CHƯA xong, chữ 'đang hoàn thiện' (lượt 2 chạy ngầm)",
             hop.tt.get("ap") == "dang" and "hoàn thiện" in str(tk.Label.cget(hop.hang["ap"][2], "text"))
             and app._xl.get("ap_ket") is not None, f"{hop.tt.get('ap')} · {app._xl.get('ap_ket')}")
        ktra("gửi yêu cầu dựng lượt 2", cd.dang_cho(jobs))
        yc = (jobs / cd.TEN_YEU_CAU).read_text(encoding="utf-8").splitlines()
        anh = sorted(Path(d.split("=", 1)[1]).name for d in yc if d.startswith("anh="))
        ktra("…chỉ ảnh đã áp, bỏ ảnh 1★", anh == ["A.ARW", "B.ARW"], str(anh))
        dest = Path(next(d.split("=", 1)[1] for d in yc if d.startswith("dest=")))
        ma = next(d.split("=", 1)[1] for d in yc if d.startswith("ma="))
        ktra("…ảnh dựng vào thư mục dữ liệu app, không vào _duyet",
             str(tam / "du_lieu") in str(dest) and "_duyet" not in str(dest))
        #  "plugin": nhận, dựng (A lệch màu da, B cháy 10%), ghi bảng + tiến độ
        (jobs / cd.TEN_YEU_CAU).unlink()
        dest.mkdir(parents=True, exist_ok=True)
        T.luu(T.canh(lech=(0.02, 0.0, -0.015)), "x")
        for ten, kw in (("A", {"lech": (0.02, 0.0, -0.015)}), ("B", {"chay_pct": 10.0})):
            from PIL import Image
            Image.fromarray(T.u8(T.canh(**kw))).save(dest / f"{ten}.jpg", quality=97)
        (jobs / cd.TEN_BANG).write_text("path\tjpg\n" + "".join(
            f"{buoi / t}.ARW\t{dest / t}.jpg\n" for t in ("A", "B")), encoding="utf-8")
        (jobs / cd.TEN_TIEN_DO).write_text(f"trang_thai=xong\nxong=2\ntong=2\nloi=0\nma={ma}\n",
                                          encoding="utf-8")
        ktra("đo xong -> gửi job @curve", cho(lambda: app._xl.get("pha") == "curve_ap"),
             str(app._xl.get("pha")))
        job = app._xl.get("curve_job")
        ktra("…tên job @curve", job is not None and Path(job).name.endswith("@curve.tsv"), str(job))
        rows = cd.doc_job(Path(job))
        ktra("…job có A (da) và B (cháy)", len(rows) == 2, str(list(rows)))
        ktra("…ảnh dựng lượt 2 đã xoá", not dest.exists())
        os.replace(job, Path(job).with_suffix(".done"))
        ktra("Lightroom áp curve -> 'Xử lý xong'", cho(lambda: app._xl.get("xong"), 20)
             and hop.lbl_tieu_de.cget("text") == "Xử lý xong", hop.lbl_tieu_de.cget("text"))
        tong = hop.lbl_tong.cget("text")
        ktra("…bước Áp xong với chữ của lượt 1 (Lightroom đã áp … kiểm chứng đủ)",
             hop.tt.get("ap") == "xong"
             and "Lightroom đã áp" in str(tk.Label.cget(hop.hang["ap"][2], "text")),
             str(tk.Label.cget(hop.hang["ap"][2], "text")))
        ktra("…tổng kết KHÔNG có dòng Curve (lượt 2 ngầm), số liệu vẫn tính đủ",
             "Curve" not in tong and "chỉnh da 1 ảnh, nén cháy 1 ảnh"
             in app._xl_tong_ket_curve_chi_tiet(app._xl.get("curve_kq") or {}),
             tong.replace("\n", " | ")[:220])
        hop.destroy()
        # ------------------------------------------------------------ 4. chi tiết
        cb = app._curve_bao.get(at.khoa_duong_dan(items[0]["path"]))
        dong = app._dong_curve(cb) if cb else ""
        ktra("Chi tiết ảnh: báo cáo curve (mặt nạ, da trước → sau, đích)",
             "mặt nạ da" in dong and "→" in dong and "đích" in dong, dong.replace("\n", " | ")[:200])
        # ------------------------------------------------------------ 5. Dừng
        hop = mo_luot(lam_items())
        app._xl_curve()
        ktra("gửi yêu cầu lần nữa", cd.dang_cho(jobs))
        hop.btn_dung.invoke()
        ktra("Dừng lúc chờ dựng: rút yêu cầu, 'Đã dừng'", not cd.dang_cho(jobs)
             and cho(lambda: app._xl.get("xong"), 5) and hop.lbl_tieu_de.cget("text") == "Đã dừng")
        hop.destroy()
        ktra("BUOC không còn bước Curve riêng", "curve" not in dict(xl_ui.BUOC))
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
