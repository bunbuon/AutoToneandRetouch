#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dong_bo_mac.py — Chép mã nguồn sang ChuyenSangMac/AutoTone-mac.

    python dong_bo_mac.py --thu     # chỉ liệt kê, không chép
    python dong_bo_mac.py           # chép thật

VÌ SAO CẦN SCRIPT, KHI CHỈ LÀ CHÉP FILE
    Trước đây chép tay. Ngày 21/09 kiểm lại thì bản Mac thiếu HẲN hai module
    mới (`ban_quyen.py`, `tai_nguyen.py`) và lệch 5 file khác — tức bản Mac
    đang ở trạng thái trước cả phần bản quyền lẫn phần tải tài nguyên.

    Lệch kiểu này không báo lỗi gì cả. Nó chỉ lộ ra khi ai đó build bản Mac và
    thấy thiếu tính năng, hoặc tệ hơn là không thấy — rồi sửa nhầm vào bản chép
    trong khi bản chạy là bản gốc.

HAI FILE KHÔNG BAO GIỜ ĐƯỢC CHÉP
    `cap_key.py` và `quan_ly_key.py` giữ khoá ký key. Chúng chỉ sống trên máy
    người bán, không đi theo bất cứ bản phát hành nào — kể cả bản Mac.
    Danh sách CAM ở dưới canh đúng chuyện đó.
"""
from __future__ import annotations

import filecmp
import shutil
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parent
MAC = GOC / "ChuyenSangMac" / "AutoTone-mac"

#[[ TUYET DOI KHONG CHEP — giu khoa ky key hoac chi co nghia tren Windows. ]]
CAM = {
    "cap_key.py",          # giu khoa ky key
    "quan_ly_key.py",      # giao dien cap key, goi cap_key
    "so_key.csv",          # so ban hang
    "tao_ma.py",           # khoa cua he dung thu cu
    "khoa.json",           # giay phep cua rieng mot may
    "dong_bo_mac.py",      # chinh no
}

#[[ Duoi file duoc phep chep. Bo .pyc, .zip, anh mau... ]]
DUOI = {".py", ".md", ".lua", ".txt"}


def nen_chep(p: Path) -> bool:
    if p.name in CAM:
        return False
    if p.suffix not in DUOI:
        return False
    #[[ LOC THEO CHINH LOAI_TRU CUA dong_goi.py, khong doan theo ten file.
    #
    #   Nhung file do la cong cu phat trien — da duoc quyet dinh mot lan la
    #   khong vao goi. Chep chung sang Mac roi build lai o do thi ban Mac se
    #   mang theo dung nhung thu ban Windows da co y loai ra, va hai ban lech
    #   nhau ngay tu dinh nghia san pham.
    #
    #   Doc tu dong_goi thay vi chep lai danh sach: mot nguon su that.
    #]]
    if p.name in CAN_DE_BUILD:
        return True
    try:
        import dong_goi
        from pathlib import Path as _P
        if p.name in {_P(f).name for f in dong_goi.LOAI_TRU}:
            return False
    except Exception:                                        # noqa: BLE001
        pass
    #[[ tu_kiem.py PHAI chep du ten no giong bai kiem: goi da build goi toi no
    #   qua lenh --tu-kiem. Thieu no thi mat cach kiem thu goi tren may Mac. ]]
    if p.name.startswith(("kiem_", "test_")) and p.name != "tu_kiem.py":
        return False
    return True


#[[ CO TRONG LOAI_TRU NHUNG VAN PHAI CHEP SANG MAC.
#
#   LOAI_TRU tra loi cau "file nao khong vao GOI". Day la cau khac: "file nao
#   can de BUILD duoc goi tren may khac". dong_goi.py tu loai minh khoi goi —
#   dung — nhung thieu no thi may Mac khong build duoc gi ca.
#
#   Hong that 21/09: dong bo xong van thay ban Mac dung dong_goi.py cu, khong
#   biet che do --nhe lan hai module moi. Goi build ra se thieu ca phan ban
#   quyen lan phan tai tai nguyen, ma khong bao loi gi.
#
#   kiem_goi.py di kem vi no la cach duy nhat biet goi vua build co dat khong.
#]]
CAN_DE_BUILD = {"dong_goi.py", "kiem_goi.py"}


def main(argv=None) -> int:
    for _l in (sys.stdout, sys.stderr):
        try:
            _l.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass

    tham = list(argv if argv is not None else sys.argv[1:])
    chi_thu = "--thu" in tham

    if not MAC.is_dir():
        print(f"  [!] Chưa có {MAC}")
        return 1

    them, doi, giong = [], [], 0
    for p in sorted(GOC.glob("*")):
        if not p.is_file() or not nen_chep(p):
            continue
        dich = MAC / p.name
        if not dich.exists():
            them.append(p)
        elif not filecmp.cmp(p, dich, shallow=False):
            doi.append(p)
        else:
            giong += 1

    print(f"\n  Nguồn: {GOC}")
    print(f"  Đích : {MAC}\n")
    if them:
        print(f"  THÊM ({len(them)}):")
        for p in them:
            print(f"      + {p.name}")
    if doi:
        print(f"  CẬP NHẬT ({len(doi)}):")
        for p in doi:
            print(f"      ~ {p.name}")
    print(f"  Giống sẵn: {giong} file")

    #[[ Canh file chi co ben Mac — co the la ban cu bo quen, ma cung co the la
    #   file rieng cua macOS (.command). Khong tu xoa, chi bao. ]]
    chi_mac = [q.name for q in sorted(MAC.glob("*.py"))
               if not (GOC / q.name).is_file()]
    if chi_mac:
        print(f"\n  [!] Chỉ có bên Mac, không có bên Windows ({len(chi_mac)}):")
        for n in chi_mac:
            print(f"      ? {n}")
        print("      Kiểm xem là file cũ bỏ quên hay cố ý riêng cho macOS.")

    if chi_thu:
        print("\n  (--thu: chưa chép gì cả)")
        return 0
    if not them and not doi:
        print("\n  Không có gì để chép.")
        return 0

    for p in them + doi:
        shutil.copy2(p, MAC / p.name)
    print(f"\n  Đã chép {len(them) + len(doi)} file.")
    #[[ Nhac lai dieu de quen nhat, vi no khong the tu dong hoa duoc. ]]
    print("  Bản .app PHẢI build trên máy Mac — PyInstaller không build chéo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
