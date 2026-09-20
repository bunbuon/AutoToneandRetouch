"""Rà soát TRƯỚC KHI ĐÓNG GÓI — bắt những thứ chỉ lộ ra sau khi đã giao gói.

VÌ SAO CẦN
    Gói build xong thì nhìn không khác gì bản chạy từ mã nguồn. Mọi lỗi đóng
    gói đều thuộc một kiểu: app vẫn mở, vẫn đẹp, chỉ MỘT nút không làm gì —
    và không báo lỗi, vì chỗ gọi thường bọc `except Exception`.

    10/9 đã có thật: thongso_lr và xuat_lr (khâu 5 — đọc thông số Export của
    Lightroom, và nút Export trong app) chỉ được import BÊN TRONG hàm, nên
    PyInstaller không thấy, và cả hai đều thiếu trong bảng NGAM. Bản .exe sẽ
    im lặng không làm gì khi bấm.

    Bài này đọc CÂY CÚ PHÁP để tự tìm ra mọi module của dự án mà app gọi tới,
    thay vì trông vào việc ai đó nhớ cập nhật bảng.

Chạy:  python3 kiem_dong_goi.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parent
LOI: list[str] = []


def ktra(ten: str, dieu: bool, mo: str = "") -> None:
    if dieu:
        print(f"  {ten:<56} {mo or 'đạt'}")
    else:
        LOI.append(f"{ten}: {mo}")


def module_cua_du_an() -> set:
    """Tên mọi file .py ở thư mục gốc — tức module của chính dự án."""
    return {p.stem for p in GOC.glob("*.py")}


def import_trong(f: Path) -> set:
    ra = set()
    try:
        cay = ast.parse(f.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return ra
    for n in ast.walk(cay):
        if isinstance(n, ast.Import):
            ra.update(a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            ra.add(n.module.split(".")[0])
    return ra


def main() -> int:
    sys.path.insert(0, str(GOC))
    import dong_goi as dg

    cua_du_an = module_cua_du_an()
    kiem = {p.stem for p in GOC.glob("kiem_*.py")} | {p.stem for p in GOC.glob("test_*.py")}
    loai = {Path(f).stem for f in dg.LOAI_TRU}

    #[[ Di theo duong import: tu diem vao, lan sang moi module cua du an ma no
    #   goi toi, roi lan tiep. Chi bat mot cap la bo sot cai duoc goi gian tiep. ]]
    can, hang_doi = set(), [Path(dg.DIEM_VAO).stem]
    while hang_doi:
        m = hang_doi.pop()
        if m in can:
            continue
        can.add(m)
        f = GOC / f"{m}.py"
        if not f.is_file():
            continue
        for x in import_trong(f):
            if x in cua_du_an and x not in can:
                hang_doi.append(x)

    #[[ Bo diem vao (PyInstaller tu biet), bo cac file kiem/do (khong vao goi),
    #   va bo nhung file da nam trong danh sach loai tru. ]]
    can -= {Path(dg.DIEM_VAO).stem} | kiem | loai
    thieu = sorted(can - set(dg.NGAM))
    ktra("mọi module dự án app gọi tới đều có trong NGAM", not thieu,
         " ".join(thieu) if thieu else f"{len(can)} module")

    #[[ Nguoc lai: ten trong NGAM ma khong co file thi la rac — thuong la file
    #   da doi ten, va no khong bao loi luc build. ]]
    thua = [m for m in dg.NGAM if not (GOC / f"{m}.py").is_file()]
    ktra("NGAM không kê tên module không tồn tại", not thua, " ".join(thua))

    # ---------- khoá bí mật tuyệt đối không được vào gói
    ktra("tao_ma.py nằm trong danh sách loại trừ", "tao_ma.py" in dg.LOAI_TRU,
         "ai có nó thì tự sinh mã gia hạn được")
    ktra("mọi file kiểm/đo đều bị loại ra khỏi gói",
         not (kiem - loai), " ".join(sorted(kiem - loai)))

    # ---------- dòng lệnh PyInstaller
    c = dg.lenh("mac", retouch=False)
    ktra("bản không retouch: bỏ hẳn retouch.py ra khỏi gói",
         "--exclude-module" in c and "retouch" in c
         and "retouch" not in [c[i + 1] for i, x in enumerate(c)
                               if x == "--hidden-import"],
         "để lại thì thành một nút bấm vào không bao giờ chạy")
    ngam_c = [c[i + 1] for i, x in enumerate(c) if x == "--hidden-import"]
    ktra("bản không retouch vẫn mang đủ mấy module khâu 5",
         {"xuat_lr", "thongso_lr", "duyet", "duyet_ui"} <= set(ngam_c),
         " ".join(sorted(set(ngam_c) & {"xuat_lr", "thongso_lr", "duyet", "duyet_ui"})))
    ktra("bản không retouch không kéo torch / mediapipe vào",
         all(f"--collect-all" != x or c[i + 1] not in ("torch", "mediapipe")
             for i, x in enumerate(c[:-1])))

    c2 = dg.lenh("mac", retouch=True)
    ktra("bản CÓ retouch thì retouch.py vẫn được mang theo",
         "retouch" in [c2[i + 1] for i, x in enumerate(c2)
                       if x == "--hidden-import"])

    #[[ macOS: dau ngan cua --add-data la ":" chu khong phai ";". Sai dau thi
    #   PyInstaller hieu ca chuoi la mot duong dan, va goi ra THIEU HAN thu
    #   muc tai nguyen — app mo len khong thay plugin, khong thay models. ]]
    dd = [c[i + 1] for i, x in enumerate(c) if x == "--add-data"]
    ktra("bản mac dùng dấu ngăn “:” cho --add-data",
         dd and all(":" in x for x in dd), f"{len(dd)} tài nguyên")
    dw = [x for i, x in enumerate(dg.lenh("win", retouch=False))
          if dg.lenh("win", retouch=False)[i - 1] == "--add-data"]
    ktra("bản win dùng dấu ngăn “;”", dw and all(";" in x for x in dw),
         f"{len(dw)} tài nguyên")

    # ---------- giao diện phải chịu được khi không có retouch
    src = (GOC / "autotone_gui.py").read_text(encoding="utf-8")
    cay = ast.parse(src)
    ten_ham = {h.name for h in ast.walk(cay) if isinstance(h, ast.FunctionDef)}
    ktra("giao diện có khung riêng cho bản không kèm retouch",
         "_khung_khong_retouch" in ten_ham)
    lam = [h for h in ast.walk(cay) if isinstance(h, ast.FunctionDef)
           and h.name == "_lam_retouch"]
    ktra("_lam_retouch có bắt lỗi import",
         bool(lam) and any(isinstance(n, ast.Try) for n in ast.walk(lam[0])),
         "không bắt thì bản không retouch nổ ngay khi mở khâu đó")

    print()
    if LOI:
        for m in LOI:
            print("  [!] " + m)
        print(f"{len(LOI)} LỖI")
        return 1
    print("TẤT CẢ ĐẠT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
