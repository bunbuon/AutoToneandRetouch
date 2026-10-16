# -*- coding: utf-8 -*-
"""Dừng giữa lượt đo + plugin bận chứ không phải "không chạy" (16/10).

User 16/10:
  1. "Sau mỗi lần phân tích mà muốn điều chỉnh thông số để phân tích lại thì hay hiển thị thông
     báo plugin Lr đang không nhận. Vào Lr Reload Plugin thì lại được."
     Gốc: vòng lặp plugin TUẦN TỰ, chỉ ghi nhịp đầu mỗi vòng; lượt lấy preview cho lưới (sau
     mỗi lượt Xử lý ảnh, ~500 ảnh = 3–5 phút) giữ nó -> yêu cầu mới nằm chờ, nhịp cũ -> "KHÔNG
     chạy".
  3. "Khi đang phân tích bấm dừng thì không thấy dừng" — do_cancel() tắt self.chuoi nên
     _on_analyzed không gọi _xl_sau_do: hộp tiến trình treo ở "Đang xử lý ảnh…".

  1. plugin_nhip tính cả file tiến độ vừa ghi; plugin_ban nói đang làm gì (x/y).
  2. _xem_lr_nhuong: yêu cầu preview còn chờ -> rút; đang chạy -> xin dừng; rảnh -> không đụng.
     Xin Lightroom xuất thông số (mở buổi / phân tích lại) -> nhường trước.
  3. Dòng trạng thái: plugin bận -> "Lightroom đang lấy preview cho lưới…", KHÔNG "không chạy".
  4. App thật: bấm Xử lý ảnh, bấm Dừng giữa lượt đo -> hộp báo "đang dừng…" ngay, rồi kết thúc
     "Đã dừng" trong vài giây, không gửi job nào; bấm Xử lý ảnh lại chạy được lượt mới.
Chạy:  python test_dung_va_nhuong.py
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


def _song(nhip) -> bool:
    return nhip is not None and nhip < 5


def _cu(p: Path, giay: float):
    t = time.time() - giay
    os.utime(p, (t, t))


def main() -> int:
    tam = Path(tempfile.mkdtemp(prefix="dung_nhuong_"))
    os.environ["AUTOTONE_DATA"] = str(tam / "du_lieu")
    os.environ["AUTOTONE_CATALOG_LR"] = str(tam / "Gia.lrcat")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import autotone as at
    import xem_lr

    jobs = tam / "jobs"
    jobs.mkdir()
    job_cu, analyze_cu = at.LR_JOB_DIR, at.analyze
    at.LR_JOB_DIR = jobs
    try:
        print("1. plugin_nhip / plugin_ban")
        nhip = jobs / at.NHIP_PLUGIN
        nhip.write_text("vong=1\n", encoding="utf-8")
        _cu(nhip, 90)
        ktra("chỉ có nhịp cũ 90 s -> nhịp ~90 s, không bận",
             85 < (at.plugin_nhip() or 0) < 95 and at.plugin_ban() == "", str(at.plugin_nhip()))
        td = jobs / "xem_lr_tiendo.txt"
        td.write_text("trang_thai=dang_chay\nxong=120\ntong=531\n", encoding="utf-8")
        ktra("đang lấy preview cho lưới (tiến độ vừa ghi) -> sống, nói rõ việc",
             _song(at.plugin_nhip()) and at.plugin_ban() == "lấy preview cho lưới 120/531",
             f"{at.plugin_nhip()} · {at.plugin_ban()!r}")
        td.write_text("trang_thai=xong\nxong=531\ntong=531\n", encoding="utf-8")
        ktra("vừa xong (tiến độ mới) -> vẫn tính là sống, nhưng không bận",
             _song(at.plugin_nhip()) and at.plugin_ban() == "")
        td.write_text("trang_thai=dang_chay\nxong=1\ntong=9\n", encoding="utf-8")
        _cu(td, 600)
        ktra("tiến độ 'đang chạy' cũ 10 phút (Lightroom tắt giữa chừng) -> theo nhịp, không bận",
             85 < (at.plugin_nhip() or 0) < 95 and at.plugin_ban() == "")
        nhip.unlink()
        ktra("chưa từng có nhịp -> None (plugin cũ / chưa chạy)", at.plugin_nhip() is None)
        td.unlink()

        import tkinter as tk
        import autotone_gui as ag
        import giao_dien as gd
        import test_2ban_quay as tq
        import test_giao_dien_gon as tg
        root = tk.Tk()
        ag.bq.kiem = lambda: {"co_phep": True, "con_lai": timedelta(days=300), "nhac": "",
                              "goi": "1 năm", "may": "TEST01", "het_han": False, "ly_do": ""}
        root.geometry("1600x940+0+0")
        gd.dat_theme(root)

        buoi = tam / "Buoi"
        buoi.mkdir()
        N = 40
        for i in range(N):
            tg.raw_gia(buoi / f"B_{i}.ARW", mau=(90 + i, 120, 150))
            (buoi / f"B_{i}.xmp").write_text(tg.XMP_GIA, encoding="utf-8")
        lan_do: list = []

        def analyze_gia(pairs_, cfg_, jobs_=1, progress=None, cancel=None):
            """Đo giả CHẬM (0,1 s / ảnh), dừng khi được xin — như at.analyze."""
            lan_do.append(len(pairs_))
            out = []
            for k, (p, sc) in enumerate(pairs_):
                time.sleep(0.1)
                r = tq.anh(Path(p).stem, k * 8, -1.6, da=tq.DA_TRONG, iso=800)
                r.update(path=str(p), sidecar=str(sc))
                out.append(r)
                if progress:
                    progress(k + 1, len(pairs_))
                if cancel and cancel():
                    break
            return out, []

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
            print("2. Nhường Lightroom: thôi lượt preview cho lưới khi có việc mới")
            xem_lr.yeu_cau(buoi, ["a.ARW"], "m1")
            app._xem_lr_luot = {"ma": "m1", "ap": {}, "da": set(), "tuoi": None, "t0": 0, "n": 0}
            app._xem_lr_nhuong()
            ktra("yêu cầu preview còn chờ -> rút, không cắm cờ dừng",
                 not xem_lr.dang_cho() and not (jobs / xem_lr.TEN_CO_DUNG).exists()
                 and app._xem_lr_luot is None)
            app._xem_lr_luot = {"ma": "m2", "ap": {}, "da": set(), "tuoi": None, "t0": 0, "n": 0}
            app._xem_lr_nhuong()
            ktra("plugin đã nhận (đang lấy preview) -> xin dừng", (jobs / xem_lr.TEN_CO_DUNG).exists())
            (jobs / xem_lr.TEN_CO_DUNG).unlink()
            app._xem_lr_nhuong()
            ktra("không có lượt preview nào -> không đụng gì", not (jobs / xem_lr.TEN_CO_DUNG).exists()
                 and not xem_lr.dang_cho())
            #  nguồn catalog: mở buổi / phân tích lại -> xin xuất thông số, nhường trước
            app.v_source.set(next(n for n, k in ag.SOURCES if k == "catalog"))
            app.v_folder.set(str(buoi))
            xem_lr.yeu_cau(buoi, ["a.ARW"], "m3")
            app._xem_lr_luot = {"ma": "m3", "ap": {}, "da": set(), "tuoi": None, "t0": 0, "n": 0}
            app._xin_xuat_nen()
            ktra("xin Lightroom xuất thông số -> rút lượt preview + gửi yêu cầu xuất",
                 not xem_lr.dang_cho() and at.export_request_pending())

            print("3. Dòng trạng thái: plugin bận khác plugin không chạy")
            nhip.write_text("vong=1\n", encoding="utf-8")
            _cu(nhip, 120)
            (jobs / "xem_lr_tiendo.txt").write_text("trang_thai=dang_chay\nxong=200\ntong=531\n",
                                                     encoding="utf-8")
            app.export = {}
            app._dang_cho_xuat = lambda: ("cho_nhan", 12.0)
            app._nhan_catalog()
            chu = str(app.lbl_scan.cget("text"))
            ktra("đang lấy preview -> 'Lightroom đang lấy preview cho lưới 200/531', không 'KHÔNG chạy'",
                 "lấy preview cho lưới 200/531" in chu and "KHÔNG chạy" not in chu, chu)
            (jobs / "xem_lr_tiendo.txt").unlink()
            app._nhan_catalog()
            chu = str(app.lbl_scan.cget("text"))
            ktra("…plugin im thật (nhịp 120 s, không tiến độ) -> vẫn báo KHÔNG chạy",
                 "KHÔNG chạy" in chu, chu)
            del app._dang_cho_xuat
            nhip.unlink()
            for f in jobs.glob("request_*"):
                f.unlink()

            print("4. App thật: bấm Dừng giữa lượt đo của Xử lý ảnh")
            app.v_source.set(ag.SOURCES[0][0])           # .xmp + đẩy thẳng Lightroom
            app.v_lrpush.set(True)
            app.scan_folder()
            vong()
            app.btn_xu_ly.invoke()
            hop = app._xl_hop()
            ktra("bấm Xử lý ảnh -> hộp tiến trình, đang đo",
                 hop is not None and cho(lambda: app._xl.get("pha") == "do", 3))
            cho(lambda: (app.pb.cget("value") or 0) >= 4, 10)
            hop.btn_dung.invoke()
            vong(2)
            ktra("bấm Dừng -> hộp báo 'đang dừng…' ngay, nút Dừng khoá",
                 "đang dừng" in str(hop.hang["do"][2].cget("text"))
                 and str(hop.btn_dung.cget("state")) == "disabled",
                 str(hop.hang["do"][2].cget("text")))
            t0 = time.time()
            ok = cho(lambda: app._xl.get("xong"), 5)
            ktra("…lượt kết thúc 'Đã dừng' trong vài giây (trước: treo mãi)",
                 ok and not app._xl_dang() and "dừng" in str(hop.lbl_tieu_de.cget("text")).lower(),
                 f"{time.time() - t0:.1f} s · {hop.lbl_tieu_de.cget('text')!r}")
            ktra("…không gửi job nào sang Lightroom", not list(jobs.glob("*.tsv")),
                 str([p.name for p in jobs.glob('*.tsv')]))
            ktra("…mới đo một phần (dừng thật, không chạy hết 40 ảnh)",
                 lan_do and len(app.items or []) < N, f"{len(app.items or [])}/{N}")
            vong(10)
            n_truoc = len(lan_do)
            app.btn_xu_ly.invoke()
            ktra("bấm Xử lý ảnh lại -> chạy lượt mới (không kẹt ở hộp cũ)",
                 cho(lambda: len(lan_do) > n_truoc, 5) and app._xl_hop() is not hop)
            hop2 = app._xl_hop()
            cho(lambda: (app.pb.cget("value") or 0) >= 2, 10)
            if hop2 is not None:
                hop2.btn_dung.invoke()
            cho(lambda: app._xl.get("xong"), 8)
        finally:
            at.analyze = analyze_cu
            try:
                root.destroy()
            except Exception:                                # noqa: BLE001
                pass
    finally:
        at.LR_JOB_DIR = job_cu
        shutil.rmtree(tam, ignore_errors=True)
    print()
    print("TAT CA DAT" if not LOI else f"{len(LOI)} LOI: {LOI}")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
