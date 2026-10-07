#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kiem_ghi_de.py — Kiem tuy chon GHI DE len anh goc.

Moi phep o day tuong ung mot cach LAM MAT ANH GOC cua khach. Ghi de khong lui
lai duoc, nen cho nay phai chac.

    python kiem_ghi_de.py
"""
from __future__ import annotations

import sys
import tempfile
import tkinter as tk
from pathlib import Path

GOC = Path(__file__).resolve().parent
sys.path.insert(0, str(GOC))

dat = hong = 0


def ket(t, ok, ghi=""):
    global dat, hong
    if ok:
        dat += 1
        print(f"  [DAT ] {t}")
    else:
        hong += 1
        print(f"  [HONG] {t}  {str(ghi)[:180]}")


def main() -> int:
    for _l in (sys.stdout, sys.stderr):
        try:
            _l.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass

    import retouch as rt

    g = Path(r"F:\Claude AI\ToolCloneEvoto")
    vao, ra = Path("A"), Path("B")

    # --- Lop lenh ---------------------------------------------------------
    c_thuong = rt.lenh(g, vao, ra, {})
    c_ghide = rt.lenh(g, vao, ra, {}, ghi_de=True)

    ket("lệnh thường vẫn có thư mục ra", "B" in c_thuong)
    ket("lệnh ghi đè KHÔNG có thư mục ra", "B" not in c_ghide, c_ghide)
    ket("lệnh ghi đè có --ghi-de", "--ghi-de" in c_ghide)
    #[[ Thieu --dong-y-ghi-de thi saytool goi input() trong mot tien trinh
    #   khong co ban phim -> treo mai mai, khong bao gi. ]]
    ket("lệnh ghi đè có --dong-y-ghi-de (nếu không sẽ treo)",
        "--dong-y-ghi-de" in c_ghide)
    ket("lệnh thường KHÔNG có --ghi-de", "--ghi-de" not in c_thuong)

    # Cac tham so khac phai giu nguyen o ca hai che do
    for co in ("--may", "--chat-luong"):
        ket(f"ghi đè vẫn giữ {co}", co in c_ghide)

    # --- Lop giao dien ----------------------------------------------------
    import autotone_gui as ag

    import man_retouch as mr          # 7/10: RetouchWindow / _RE_TIEN_DO o day
    tmp = Path(tempfile.mkdtemp(prefix="kiem_gd_"))
    (tmp / "vao").mkdir()

    goc_tk = tk.Tk()
    goc_tk.withdraw()
    try:
        app = ag.App(goc_tk)
        goc_tk.update()
        w = mr.RetouchWindow(app)
        goc_tk.update()
    except Exception as ex:                                  # noqa: BLE001
        ket("dựng được cửa sổ Retouch", False, repr(ex))
        return 1
    ket("dựng được cửa sổ Retouch", True)

    ket("có ô tick ghi đè", hasattr(w, "v_ghide"))

    # Mac dinh: o "Ra" dung duoc
    w.v_ghide.set(False)
    w._doi_ghide()
    goc_tk.update()
    ket("mặc định: ô “Ra” dùng được",
        str(w.e_ra.cget("state")) == "normal", w.e_ra.cget("state"))

    # Bat ghi de: o "Ra" phai mo di
    w.v_ghide.set(True)
    w._doi_ghide()
    goc_tk.update()
    ket("bật ghi đè: ô “Ra” bị khoá",
        str(w.e_ra.cget("state")) == "disabled", w.e_ra.cget("state"))
    ket("bật ghi đè: nút Chọn cũng khoá",
        str(w.btn_ra.cget("state")) == "disabled")
    ket("bật ghi đè: có nhắc không lùi lại được",
        "lùi" in w.lbl_ghide.cget("text"), w.lbl_ghide.cget("text"))

    # Tat lai: phai tro ve binh thuong
    w.v_ghide.set(False)
    w._doi_ghide()
    goc_tk.update()
    ket("tắt ghi đè: ô “Ra” dùng lại được",
        str(w.e_ra.cget("state")) == "normal")
    ket("tắt ghi đè: hết dòng nhắc", not w.lbl_ghide.cget("text"))

    # --- Thanh tien do o che do ghi de ------------------------------------
    #[[ Ghi de thi khong dem duoc bang file. Phai doc dong tien do cua tool,
    #   khong thi thanh dung im o 0/N suot ca me — nguoi dung khong biet no
    #   con song hay da treo. Do that 27/09. ]]
    import shutil as _sh
    src = Path(r"G:\TestRetouchFinal")
    if src.is_dir():
        for a in sorted(src.glob("*.jpg"))[:5]:
            _sh.copy2(a, tmp / "vao" / a.name)
    else:
        for i in range(5):
            (tmp / "vao" / f"a{i}.jpg").write_bytes(b"x" * 10)

    w.v_vao.set(str(tmp / "vao"))
    w.v_ghide.set(True)
    w._doi_ghide()
    goc_tk.update()

    w._tien_do_tool = 0
    tong, xong = w._dem()
    ket("ghi đè: đếm đúng tổng số ảnh", tong == 5, f"tong={tong}")
    ket("ghi đè: chưa chạy thì 0 xong", xong == 0, f"xong={xong}")

    # Gia lap tool in dong tien do
    w._tien_do_tool = 3
    tong, xong = w._dem()
    ket("ghi đè: đọc được tiến độ từ tool", xong == 3, f"xong={xong}")

    # Tool bao qua tong (khong nen xay ra) -> phai chan lai
    w._tien_do_tool = 99
    _, xong = w._dem()
    ket("ghi đè: không vượt quá tổng", xong == 5, f"xong={xong}")

    ket("mẫu bắt đúng dòng tiến độ",
        mr._RE_TIEN_DO.match("  10/2021  0.74s/anh  con lai ~24.8 phut") is not None)
    ket("mẫu KHÔNG ăn nhầm dòng log thường",
        mr._RE_TIEN_DO.match("  . SAY-Media-07354.jpg: vet co the") is None)

    w.destroy()
    goc_tk.destroy()

    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n  {dat} đạt / {hong} hỏng")
    return 1 if hong else 0


if __name__ == "__main__":
    sys.exit(main())
