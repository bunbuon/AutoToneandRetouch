# -*- coding: utf-8 -*-
"""Kiểm lưới / ảnh lớn hiện PREVIEW LIGHTROOM sau khi áp (14/10).

User 14/10: "oke làm luôn hiện preview" — áp xong thì ảnh thấy trên tool phải giống
Lightroom (preview của tool là ảnh nhúng trong RAW: màu máy ảnh).
  1. xem_lr: cất / đọc / quên preview, ghi thông số lúc áp.
  2. Xử lý xong -> xin plugin preview ĐÚNG các ảnh vừa áp (nguon=preview, chi_preview=1,
     ảnh soát kiem_anh=).
  3. Preview tươi -> lưới (luoi_anh.NGUON) + ảnh lớn (nguon_xem "lr") dùng preview; mô
     phỏng chỉ phần ĐỔI sau khi áp (vừa áp: không mô phỏng gì; kéo Bù sáng +0.30: +0.30).
  4. Preview lệch bản xuất thật (cũ) -> không cất, xin plugin dừng, lưới giữ ảnh tool.
Chạy:  python test_xem_lr.py
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
    tam = Path(tempfile.mkdtemp(prefix="xem_lr_"))
    os.environ["AUTOTONE_DATA"] = str(tam / "du_lieu")
    os.environ["AUTOTONE_CATALOG_LR"] = "0"
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import numpy as np
    from PIL import Image
    import autotone as at
    import test_2ban_quay as tq
    import test_giao_dien_gon as tg
    import xem_lr
    import luoi_anh
    import nguon_xem

    # ------------------------------------------------------------ 1. kho
    j = tam / "p.jpg"
    Image.new("RGB", (64, 48), (200, 120, 90)).save(j)
    da = xem_lr.nhan([("G:/B/X1.ARW", str(j))], {at.khoa_duong_dan("G:/B/X1.ARW"): (0.3, 5200, 4)})
    ktra("xem_lr.nhan: cất preview + thông số lúc áp", da == ["G:/B/X1.ARW"]
         and xem_lr.anh("G:/B/X1.ARW") is not None and xem_lr.ap_cua("G:/B/X1.ARW") == (0.3, 5200, 4))
    xem_lr.quen(["G:/B/X1.ARW"])
    ktra("xem_lr.quen: bỏ preview", xem_lr.anh("G:/B/X1.ARW") is None)

    buoi = tam / "SuKien"
    buoi.mkdir()
    for i in range(5):
        tg.raw_gia(buoi / f"SK_{i}.ARW", mau=(90 + 20 * i, 120, 150))
        (buoi / f"SK_{i}.xmp").write_text(tg.XMP_GIA, encoding="utf-8")

    def items_cua(pairs_) -> list:
        out = []
        for p, sc in pairs_:
            i = int(Path(p).stem.split("_")[1])
            r = tq.anh(Path(p).stem, i * 8, -1.6 + 0.12 * i, da=tq.DA_TRONG)
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
    root.geometry("1500x900+0+0")
    gd.dat_theme(root)
    job_cu, analyze_cu = at.LR_JOB_DIR, at.analyze
    jobs = tam / "jobs"
    jobs.mkdir()
    at.LR_JOB_DIR = jobs
    at.analyze = lambda pairs_, cfg_, jobs_=1, progress=None, cancel=None: (items_cua(pairs_), [])
    (jobs / at.NHIP_PLUGIN).write_text("gen=1\nkha_nang=curve1,sao1,xem1\n", encoding="utf-8")
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
        app.v_source.set(ag.SOURCES[0][0])
        app.v_folder.set(str(buoi))
        app.scan_folder()
        app.start_analyze()
        ktra("phân tích (giả) xong", cho(lambda: bool(app.items)), str(len(app.items or [])))
        vong()
        r0 = next(r for r in app.items if app._mp_cua(r) is not None)
        o0 = lambda: next(o for o in app.luoi.ds if o["path"] == r0["path"])  # noqa: E731
        ktra("trước khi có preview Lightroom: ô mô phỏng TUYỆT ĐỐI trên ảnh nhúng",
             o0()["mp"] is not None and luoi_anh.NGUON(r0["path"]) is None, str(o0()["mp"]))
        # ------------------------------------------------------------ 2. xin preview
        xl = {"items_ghi": list(app.items)}
        ktra("Xử lý xong -> xin preview Lightroom", app._xem_lr_bat_dau(xl) is True)
        yc = (jobs / xem_lr.TEN_YEU_CAU).read_text(encoding="utf-8").splitlines()
        anh = [d.split("=", 1)[1] for d in yc if d.startswith("anh=")]
        kiem = [d.split("=", 1)[1] for d in yc if d.startswith("kiem_anh=")]
        ktra("…đúng các ảnh vừa áp, CHỈ preview (không Export bù), có ảnh soát",
             len(anh) == len(app.items) and "nguon=preview" in yc and "chi_preview=1" in yc
             and len(kiem) == 3, f"{len(anh)} ảnh · soát {len(kiem)}")
        ma = next(d.split("=", 1)[1] for d in yc if d.startswith("ma="))
        dest = Path(next(d.split("=", 1)[1] for d in yc if d.startswith("dest=")))

        def plugin_tra(toi: float, ma_: str, dest_: Path):
            (jobs / xem_lr.TEN_YEU_CAU).unlink(missing_ok=True)
            (dest_ / "_kiem").mkdir(parents=True, exist_ok=True)
            bang, kb = [], []
            for p in anh:
                ten = Path(p).stem
                goc = np.full((240, 360, 3), (180, 130, 100), np.uint8)
                Image.fromarray(np.clip(goc * toi, 0, 255).astype(np.uint8)).save(
                    dest_ / f"{ten}.jpg", quality=90)
                bang.append(f"{p}\t{dest_ / ten}.jpg")
                if p in kiem:
                    Image.fromarray(goc).save(dest_ / "_kiem" / f"{ten}.jpg", quality=95)
                    kb.append(f"{p}\t{dest_ / '_kiem' / ten}.jpg")
            (jobs / xem_lr.TEN_KIEM).write_text("path\tjpg\n" + "\n".join(kb) + "\n", encoding="utf-8")
            (jobs / xem_lr.TEN_BANG).write_text("path\tjpg\n" + "\n".join(bang) + "\n", encoding="utf-8")
            (jobs / xem_lr.TEN_TIEN_DO).write_text(
                f"trang_thai=xong\nxong={len(anh)}\ntong={len(anh)}\nma={ma_}\ncach=preview\n",
                encoding="utf-8")

        plugin_tra(1.0, ma, dest)
        app._xem_lr_soi()
        vong()
        f0 = xem_lr.anh(r0["path"])
        ktra("preview tươi -> cất vào kho, lưới đọc preview Lightroom (luoi_anh.NGUON)",
             f0 is not None and luoi_anh.NGUON(r0["path"]) == f0, str(f0))
        ktra("ảnh lớn: nguồn 'lr' (Preview Lightroom sau khi áp)",
             nguon_xem.anh_xem(r0["path"])[1] == "lr")
        ktra("vừa áp xong: ô KHÔNG mô phỏng gì thêm (preview đã mang thông số)",
             o0()["mp"] is None, str(o0()["mp"]))
        ktra("thư mục tạm của lượt đã dọn", not dest.exists())
        app.v_bu_sang.set("0.30")
        app.refresh_plan()
        vong()
        mp = o0()["mp"]
        ktra("kéo Bù sáng +0.30 sau khi áp -> mô phỏng CHỈ +0.30 trên preview Lightroom",
             mp is not None and abs(mp[0] - 0.30) < 0.02, str(mp))
        app._mo_mot_ct(r0["path"])
        vong(6)
        ktra("ảnh lớn ghi rõ 'Preview Lightroom (sau khi áp)'",
             "Preview Lightroom" in str(app.lbl_mot_ct.cget("text")), str(app.lbl_mot_ct.cget("text")))
        app._ve_luoi_ct()
        # ------------------------------------------------------------ 4. preview cũ
        ktra("xin lần nữa", app._xem_lr_bat_dau(xl) is True)
        yc2 = (jobs / xem_lr.TEN_YEU_CAU).read_text(encoding="utf-8").splitlines()
        ma2 = next(d.split("=", 1)[1] for d in yc2 if d.startswith("ma="))
        dest2 = Path(next(d.split("=", 1)[1] for d in yc2 if d.startswith("dest=")))
        plugin_tra(0.7, ma2, dest2)                    # preview TỐI hơn bản xuất thật
        app._xem_lr_soi()
        vong()
        ktra("preview lệch bản xuất (cũ) -> KHÔNG cất, xin plugin dừng, giữ preview trước",
             xem_lr.anh(r0["path"]) == f0 and (jobs / xem_lr.TEN_CO_DUNG).exists()
             and "chưa cập nhật preview" in str(app.lbl_status.cget("text")),
             str(app.lbl_status.cget("text"))[:80])
        (jobs / at.NHIP_PLUGIN).write_text("gen=1\nkha_nang=curve1,sao1\n", encoding="utf-8")
        ktra("plugin cũ (không khai xem1) -> không xin", app._xem_lr_bat_dau(xl) is False)
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
