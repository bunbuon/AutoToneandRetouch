#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""duong_dan.py — Chỗ nào chỉ ĐỌC, chỗ nào GHI ĐƯỢC.

VÌ SAO PHẢI TÁCH RA
    Chạy từ mã nguồn thì mọi thứ nằm chung một thư mục và ghi đâu cũng được.
    Đóng gói rồi thì không:

      * Windows: gói cài nằm trong C:\\Program Files — user thường KHÔNG ghi
        được vào đó. Ghi hỏng thì Windows còn âm thầm chuyển hướng sang
        VirtualStore, nên chương trình tưởng đã ghi xong mà file thật nằm chỗ
        khác — loại lỗi mất dữ liệu khó truy nhất.
      * macOS: nội dung trong .app được ký; ghi vào đó là phá chữ ký, lần mở
        sau Gatekeeper chặn luôn ứng dụng.
      * PyInstaller onefile: giải nén ra thư mục tạm rồi XOÁ khi thoát — ghi
        vào đó là mất sạch sau mỗi lần đóng app.

    Nên: tài nguyên (mô hình, bản gốc plugin) chỉ đọc, nằm trong gói.
    Dữ liệu (gu đã học, job gửi Lightroom, trạng thái buổi, cấu hình) ghi vào
    thư mục dữ liệu của người dùng.

PLUGIN LIGHTROOM LÀ TRƯỜNG HỢP ĐẶC BIỆT
    Nó vừa là tài nguyên (đi kèm gói) vừa phải GHI được (thư mục jobs nằm bên
    trong nó), và Lightroom phải nạp được nó. Nên lần chạy đầu, bản gốc trong
    gói được chép sang thư mục dữ liệu, và từ đó trở đi dùng bản chép.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

TEN_UD = "AutoTone"


def dong_goi() -> bool:
    """Đang chạy từ gói đã đóng (PyInstaller) hay từ mã nguồn?"""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def goc_tai_nguyen() -> Path:
    """Thư mục CHỈ ĐỌC: mô hình, bản gốc plugin, tài liệu."""
    if dong_goi():
        return Path(sys._MEIPASS)                    # noqa: SLF001
    return Path(__file__).resolve().parent


def goc_du_lieu() -> Path:
    """Thư mục GHI ĐƯỢC của người dùng.

    Đặt được bằng biến môi trường AUTOTONE_DATA — cần cho bài kiểm (chạy trên
    thư mục tạm) và cho máy muốn để dữ liệu sang ổ khác.
    """
    tu_dat = os.environ.get("AUTOTONE_DATA")
    if tu_dat:
        return Path(tu_dat)
    if not dong_goi():
        #[[ Chay tu ma nguon thi giu nguyen thoi quen cu: moi thu nam canh file
        #   .py. Doi cho luc nay se lam lac het gu.json va trang_thai/ dang co.
        #]]
        return Path(__file__).resolve().parent
    if sys.platform.startswith("win"):
        goc = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        goc = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        goc = os.environ.get("XDG_DATA_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "share")
    return Path(goc) / TEN_UD


def tao(p: Path) -> Path:
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return p


def du_lieu(*ten) -> Path:
    """Đường dẫn trong thư mục dữ liệu, tự tạo thư mục cha."""
    p = goc_du_lieu().joinpath(*ten)
    tao(p.parent)
    return p


def tai_nguyen(*ten) -> Path:
    return goc_tai_nguyen().joinpath(*ten)


def plugin() -> Path:
    """Thư mục plugin Lightroom dùng thật — chép từ gói ra lần đầu.

    Chỉ chép khi CHƯA có. Chép đè mỗi lần chạy sẽ xoá mất thư mục jobs đang
    chờ Lightroom xử lý, và ăn mất kết quả của lần chạy trước.
    """
    dich = goc_du_lieu() / "AutoTone.lrplugin"
    if not dong_goi():
        return Path(__file__).resolve().parent / "AutoTone.lrplugin"
    nguon = goc_tai_nguyen() / "AutoTone.lrplugin"
    if not dich.exists() and nguon.is_dir():
        try:
            tao(dich.parent)
            #[[ KHONG CHEP THU MUC jobs THEO.
            #
            #   jobs/ la TRANG THAI LUC CHAY, khong phai tai nguyen: nhat ky
            #   plugin, job da xong, va ban xuat tu catalog Lightroom. Chep no
            #   sang may moi la moi ban cai deu khoi dong voi lich su cua studio
            #   khac — va te nhat, voi mot ban xuat CU.
            #
            #   Hong that 4/9: goi build ra mang theo export_20260903_105234.tsv
            #   (buoi 2905, 220 anh). Ban .exe chep no ra roi doc phai, nen buoi
            #   G:\\0608 96 anh bi bao "ban xuat chi khop 0 anh" — trong khi
            #   Lightroom van xuat dung, chi la xuat vao MOT THU MUC KHAC.
            #
            #   dong_goi.py cung da loc jobs/ ra khong cho vao goi. Chan o ca
            #   hai dau: goi cu (da lo build roi) van duoc cuu o day.
            #]]
            shutil.copytree(nguon, dich,
                            ignore=shutil.ignore_patterns("jobs"))
        except OSError:
            pass
    tao(dich / "jobs")
    return dich


def mo_ta() -> str:
    return (f"tài nguyên: {goc_tai_nguyen()}\n"
            f"dữ liệu   : {goc_du_lieu()}\n"
            f"plugin    : {plugin()}\n"
            f"đóng gói  : {'có' if dong_goi() else 'không (chạy từ mã nguồn)'}")


if __name__ == "__main__":
    print(mo_ta())
