# -*- coding: utf-8 -*-
"""Lớp MASK DA trên preview của app (mask_xem.py + nút "Mask da" — 14/10).

User 14/10: "show cái lớp mask của da đang dùng để tool xử lý để tôi xem có mask đúng
không? show trên preview của app luôn cho từng ảnh". Mask phải là ĐÚNG phép tách da tool
dùng, đúng chỗ trên ảnh đang hiện, và không làm treo giao diện.

Mục kiểm
    1. mã điểm ảnh: da đo (1), da bị bỏ vì bóng (2), cháy (3), trắng xét WB (4) đúng chỗ;
       mặt KHÔNG phải chủ thể (all_boxes) không bị tính là trắng
    2. phu(): tô màu, giữ cỡ ảnh, vẽ khung mặt
    3. BoMask: lần đầu None (đang tính nền), xong thì có; kho đĩa dùng lại ở phiên sau
    4. app thật: nút "Mask da" bật -> lưới phủ mask (ô đổi màu), tắt -> như cũ; ảnh lớn
       ghi "Mask: …"

Chạy:  python test_mask_xem.py
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path

import numpy as np

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
    tam = Path(tempfile.mkdtemp(prefix="mask_xem_"))
    os.environ["AUTOTONE_DATA"] = str(tam / "du_lieu")
    os.environ["AUTOTONE_CATALOG_LR"] = "0"
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import mask_xem as mx
    import test_curve_da as T
    from PIL import Image

    T.cai_gia()
    W, H = T.W, T.H
    #  ảnh giả: mặt (da) + vùng xám trung tính + vùng cháy + một điểm bóng trên má +
    #  một "mặt khách" xám sáng (không phải chủ thể)
    a = T.u8(T.canh(xam_pct=20.0, chay_pct=8.0))
    cx, cy = T.MAT[0] + T.MAT[2] / 2, T.MAT[1] + T.MAT[3] / 2
    a[int(cy + 15):int(cy + 25), int(cx + 45):int(cx + 55)] = 255          # bóng trên má
    khach = (700, 40, 80, 100)
    a[khach[1]:khach[1] + khach[3], khach[0]:khach[0] + khach[2]] = (205, 203, 200)
    src = tam / "anh.png"
    Image.fromarray(a).save(src)
    r = dict(T.anh("A"), all_boxes=[tuple(T.MAT) + (0.95,), khach + (0.9,)])

    print("1. mã điểm ảnh")
    kq = mx.tinh(src, r)
    ma = kq["ma"]
    ktra("má trong mặt nạ = da đo (1)", ma[int(cy + 20), int(cx - 50)] == 1, str(ma[int(cy + 20), int(cx - 50)]))
    ktra("điểm bóng trên má = da bị bỏ (2) hoặc cháy, không phải da đo",
         ma[int(cy + 20), int(cx + 50)] in (2, 3), str(ma[int(cy + 20), int(cx + 50)]))
    ktra("có vùng cháy (3) và vùng trắng (4)", (ma == 3).any() and (ma == 4).any(),
         str({k: int((ma == k).sum()) for k in range(5)}))
    ktra("mặt khách xám sáng KHÔNG bị tính là trắng xét WB",
         not (ma[khach[1] + 10:khach[1] + khach[3] - 10, khach[0] + 10:khach[0] + khach[2] - 10] == 4).any())
    ktra("tóm tắt nói kiểu mặt nạ + số mặt", "1 mặt" in mx.tom_tat(kq) and "điểm da" in mx.tom_tat(kq),
         mx.tom_tat(kq))

    print("2. phu()")
    im = Image.fromarray(a).resize((450, 300))
    ph = mx.phu(im, kq)
    ktra("cỡ ảnh giữ nguyên, ảnh đổi màu", ph.size == im.size
         and float(np.abs(np.asarray(ph, float) - np.asarray(im, float)).mean()) > 3)
    p0 = np.asarray(ph)[int((cy + 20) / 2), int((cx - 50) / 2)]
    ktra("điểm da tô xanh lá (G trội)", int(p0[1]) > int(p0[0]) and int(p0[1]) > int(p0[2]), str(p0))
    ktra("không có mask -> trả lại ảnh nguyên", mx.phu(im, None) is im)

    print("3. BoMask")
    xong = []
    bo = mx.BoMask(khi_xong=xong.append)
    ktra("lần đầu: None (đang tính ở nền)", bo.lay(src, r) is None)
    het = time.time() + 30
    while not xong and time.time() < het:
        time.sleep(0.05)
    ktra("tính xong -> báo về + lay() có", bool(xong) and bo.lay(src, r) is not None)
    bo2 = mx.BoMask()
    ktra("phiên sau: lấy từ kho đĩa ngay (không tính lại)", bo2.lay(src, r) is not None)
    r2 = dict(r, meter_boxes=[[10, 10, 50, 50]])
    ktra("đổi khung mặt -> khoá khác (tính lại)", bo2.lay(src, r2) is None)

    print("4. app thật")
    import tkinter as tk
    import autotone_gui as ag
    import giao_dien as gd
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

        vong(8)
        anh_jpg = tam / "Buoi" / "A.jpg"
        anh_jpg.parent.mkdir()
        Image.fromarray(a).save(anh_jpg, quality=95)
        r3 = dict(r, path=str(anh_jpg))
        app.items = [r3]
        app.luoi.dat_ds([{"path": str(anh_jpg), "ten": "A.jpg"}])
        vong(20)
        ktra("có nút 'Mask da', mặc định TẮT", hasattr(app, "chip_mask") and app.v_mask.get() is False)
        k0 = [k for k in app.luoi._anh_tk if k[0] == str(anh_jpg)]
        app.chip_mask._chon("bat")
        het = time.time() + 30
        while time.time() < het:
            vong(2)
            if not getattr(app, "_mask_moi", None) and app._bo_mask().lay(app._nguon_luoi(str(anh_jpg)), r3):
                vong(10)
                break
        k1 = [k for k in app.luoi._anh_tk if k[0] == str(anh_jpg) and k[5] is not None]
        ktra("bật: lưới vẽ lại ô với lớp phủ mask", app.luoi.lop_phu is not None and bool(k1),
             f"{len(k0)} -> {len(k1)}")
        app.chip_mask._chon("bat")
        vong(5)
        ktra("tắt: lưới bỏ lớp phủ", app.luoi.lop_phu is None and app.v_mask.get() is False)
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
