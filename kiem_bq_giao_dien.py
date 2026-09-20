# -*- coding: utf-8 -*-
"""Kiem giao dien ban quyen: nhap key that vao o that, xem app co mo khong."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import tkinter as tk
from pathlib import Path

AT = r"F:\Claude AI\AutoToneImages"
sys.path.insert(0, AT)

TMP = Path(tempfile.mkdtemp(prefix="kiem_uibq_"))
os.environ["AUTOTONE_DATA"] = str(TMP)

import ban_quyen as bq      # noqa: E402
import khoa                 # noqa: E402
import autotone_gui as ag   # noqa: E402

for _l in (sys.stdout, sys.stderr):
    try:
        _l.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

#[[ Gia lap may chu: bai nay kiem GIAO DIEN, khong kiem duong mang.
#   Duong mang that co bai rieng — kiem_bq_online.py. ]]
from datetime import datetime, timedelta, timezone


def _goi_gia(duong, than):
    bay = datetime.now(timezone.utc)
    d = bq.doc_key(than.get("key", ""))
    ngay = d[1] if d else 365
    return 200, {"ok": True, "so_ngay": ngay,
                 "kich_hoat": bay.isoformat(),
                 "het_han": (bay + timedelta(days=ngay)).isoformat()}


bq._goi = _goi_gia

dat = hong = 0


def ket(t, ok, ghi=""):
    global dat, hong
    if ok:
        dat += 1
        print(f"  [DAT ] {t}")
    else:
        hong += 1
        print(f"  [HONG] {t}  {str(ghi)[:200]}")


def main() -> int:
    #[[ Bat khoa len de gia lap ban giao cho khach. Tren may nay BAT_KHOA=False
    #   (may nguoi lam tool), de nguyen thi app khong bao gio khoa va bai kiem
    #   khong kiem duoc gi. ]]
    khoa.BAT_KHOA = True

    goc = tk.Tk()
    goc.withdraw()
    try:
        app = ag.App(goc)
    except Exception as ex:                                  # noqa: BLE001
        ket("dung duoc cua so chinh", False, repr(ex))
        return 1
    ket("dung duoc cua so chinh", True)

    # 1. May sach: chua co phep -> phai hien lop khoa
    goc.update()
    app._soi_khoa()
    goc.update()
    ket("máy chưa kích hoạt thì hiện lớp khoá",
        getattr(app, "_lop_khoa", None) is not None)

    # 2. Nhan dung: o nhap va nut phai co
    ket("lớp khoá có ô nhập key", hasattr(app, "v_ma"))

    # 3. Nhap KEY BAN QUYEN that vao o that, bam nut that
    key = bq.tao_key(4242, 365)
    app.v_ma.set(key)
    try:
        app.btn_gia_han.invoke()
    except Exception as ex:                                  # noqa: BLE001
        ket("bấm Kích hoạt chạy được", False, repr(ex))
        return 1
    ket("bấm Kích hoạt chạy được", True)
    goc.update()

    g = bq.kiem()
    ket("key bản quyền được nhận", g["co_phep"], g["ly_do"])
    ket("gói đọc đúng là 1 năm", g["goi"] == "1 năm", g["goi"])

    # 4. Lop khoa phai tu go sau khi kich hoat
    for _ in range(12):
        app._soi_khoa()
        goc.update()
        if getattr(app, "_lop_khoa", None) is None:
            break
    ket("lớp khoá tự gỡ sau khi kích hoạt",
        getattr(app, "_lop_khoa", None) is None)

    # 5. Thanh trang thai hien dung ban quyen, khong con "dung thu"
    txt = app.lbl_han.cget("text")
    ket("thanh trạng thái báo bản quyền, không phải dùng thử",
        "Bản quyền" in txt and "dùng thử" not in txt, txt)

    # 6. _khoa_chan phai cho qua khi da co phep
    ket("có phép thì không chặn việc mới", app._khoa_chan() is False)

    # 7. Het han -> chan lai
    from datetime import datetime, timezone, timedelta
    #[[ Lui CA bq_het_han: _het_han() uu tien han may chu da chot. ]]
    cu = datetime.now(timezone.utc) - timedelta(days=400)
    khoa.ghi_trang_thai(bq_kich_hoat=cu.isoformat(), moc_cao=cu.isoformat(),
                        bq_het_han=(cu + timedelta(days=365)).isoformat())
    ket("hết hạn thì chặn việc mới", app._khoa_chan() is True)

    # 8. Nhung do_csv / do_undo KHONG duoc chan
    import inspect
    for ten in ("do_csv", "do_undo"):
        ma = inspect.getsource(getattr(ag.App, ten))
        ket(f"{ten} không gọi _khoa_chan (cho xem/xuất việc cũ)",
            "_khoa_chan" not in ma)

    goc.destroy()
    print(f"\n  {dat} đạt / {hong} hỏng")
    shutil.rmtree(TMP, ignore_errors=True)
    return 1 if hong else 0


if __name__ == "__main__":
    raise SystemExit(main())
