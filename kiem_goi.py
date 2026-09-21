#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kiem_goi.py — Kiểm CÁI GÓI ĐÃ BUILD, không phải mã nguồn.

    python kiem_goi.py                              # tự tìm trong dist/
    python kiem_goi.py "" "G:\\0608"               # kèm ảnh RAW thật
    python kiem_goi.py "D:\\AutoTone" "G:\\0608"  # chỉ rõ cả hai

CHẠY TRÊN MÁY NÀO
    Trên chính máy vừa build, và — quan trọng hơn — trên MÁY SẠCH chưa từng cài
    Python. Máy build luôn có sẵn thư viện ở ngoài, nên một gói thiếu file vẫn
    có thể chạy được ở đó mà chết trên máy khách. Chép cả thư mục gói sang máy
    sạch, chép kèm mỗi file kiem_goi.py này, rồi chạy nó bằng... không cần
    Python: xem phần cuối — nó gọi chính AutoTone.exe để tự kiểm.
    (Nếu máy sạch không có Python thì chạy tay: mở PowerShell trong thư mục gói,
     $env:AUTOTONE_TU_KIEM="$HOME\\bao.txt"; .\\AutoTone.exe   rồi mở bao.txt.)

BA LỚP KIỂM, VÌ MỖI LỚP TRẢ LỜI MỘT CÂU KHÁC NHAU
    1. Nhìn từ ngoài  — gói có đủ file không, có lọt file cấm không.
    2. Chạy bên trong — app tự kiểm bằng tu_kiem.py: đường dẫn tài nguyên sau
       khi đóng gói, import ngầm, chỗ ghi, khoá, chạy thật đường đo–tính.
    3. So trước/sau  — app có ÂM THẦM GHI vào thư mục gói không. Trên Windows
       ghi vào Program Files bị chuyển hướng sang VirtualStore mà không báo lỗi,
       nên chỉ nhìn mã nguồn thì không bao giờ thấy.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

GOC = Path(__file__).resolve().parent
TEN = "AutoTone"
CHO = 600.0        # giây; lần chạy đầu phải nạp torch nên rất lâu


def tim_goi(chi_ro: str | None) -> Path | None:
    if chi_ro:
        p = Path(chi_ro).expanduser().resolve()
        return p if p.exists() else None
    for ung in (GOC / "dist" / f"{TEN}.app", GOC / "dist" / TEN):
        if ung.exists():
            return ung
    return None


def file_chay(goi: Path) -> Path | None:
    """Đường dẫn tới file thực thi bên trong gói."""
    if goi.suffix == ".app":
        p = goi / "Contents" / "MacOS" / TEN
        return p if p.is_file() else None
    for ten in (f"{TEN}.exe", TEN):
        p = goi / ten
        if p.is_file():
            return p
    return None


def anh_chup(goi: Path) -> dict:
    """Bản chụp nội dung gói: đường dẫn -> (cỡ, thời điểm sửa)."""
    d = {}
    for p in goi.rglob("*"):
        if p.is_file():
            try:
                s = p.stat()
                d[str(p.relative_to(goi))] = (s.st_size, int(s.st_mtime))
            except OSError:
                pass
    return d


def main(argv=None) -> int:
    #[[ Console cp1252 khong in noi chu Viet — bai kiem DAT van chet o dong
    #   in dau tien. Xem ghi chu trong _cua_saytool(). ]]
    for _l in (sys.stdout, sys.stderr):
        try:
            _l.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass
    argv = sys.argv[1:] if argv is None else argv
    #[[ Doi so thu hai (tuy chon): thu muc anh RAW THAT.
    #
    #   Co no thi bai tu kiem ben trong goi doc RAW that, do that, ghi .xmp that
    #   roi hoan tac. Day la phan duy nhat cham toi file dinh dang RIENG CUA MAY
    #   ANH nguoi dung — anh JPEG bai kiem tu sinh khong bao gio lo ra duoc
    #   chuyen preview nhung trong .ARW nam o dau va to bao nhieu.
    #]]
    anh = None
    if len(argv) > 1:
        anh = str(Path(argv[1]).expanduser())
        if not Path(anh).is_dir():
            print(f"  [!] Không thấy thư mục ảnh: {anh}")
            return 2
    goi = tim_goi(argv[0] if argv else None)
    if goi is None:
        print("  [!] Không tìm thấy gói. Chạy dong_goi.py trước, hoặc chỉ rõ "
              "thư mục:  python kiem_goi.py <thư mục gói>")
        return 2

    loi: list[str] = []
    print(f"  Gói: {goi}\n")

    # ── Lớp 1: nhìn từ ngoài ────────────────────────────────────────────────
    exe = file_chay(goi)
    if exe is None:
        print(f"  [!] Không thấy file chạy trong {goi}")
        return 2
    print(f"  [DAT ] File chạy: {exe.name}")

    import dong_goi
    lot = []
    for f in dong_goi.LOAI_TRU:
        lot += [str(p.relative_to(goi)) for p in goi.rglob(f)]
    #[[ tao_ma tach ra bao rieng: cac file kia lot vao chi la rac, con tao_ma
    #   lot vao la co che han dung thanh vo nghia.
    #]]
    nguy = [f for f in lot if "tao_ma" in f]
    if nguy:
        loi.append("tao_ma LỌT VÀO GÓI: " + ", ".join(nguy)
                   + " — ai có gói đều tự sinh được mã gia hạn")
    elif lot:
        print(f"  [    ] {len(lot)} file kiểm lọt vào gói (vô hại, chỉ là rác): "
              + ", ".join(lot[:4]) + ("..." if len(lot) > 4 else ""))
    else:
        print("  [DAT ] Không file nào trong danh sách loại trừ lọt vào gói")

    co = sum(v[0] for v in anh_chup(goi).values())
    print(f"  [    ] Cỡ gói: {co / 1e9:.2f} GB")

    # ── Lớp 3a: chụp trước khi chạy ─────────────────────────────────────────
    truoc = anh_chup(goi)

    # ── Lớp 2: bảo app tự kiểm ──────────────────────────────────────────────
    tam = Path(tempfile.mkdtemp(prefix="kiem_goi_"))
    bao = tam / "bao_cao.txt"
    #[[ AUTOTONE_DATA tro vao thu muc tam: bai kiem khong duoc dung vao gu.json
    #   hay giay phep that dang co tren may.
    #]]
    env = {**os.environ, "AUTOTONE_DATA": str(tam / "du_lieu"),
           "AUTOTONE_TU_KIEM": str(bao)}
    if anh:
        env["AUTOTONE_TU_KIEM_ANH"] = anh
        print(f"\n  Ảnh thật để kiểm: {anh}")
        print("  (chỉ ĐỌC ảnh gốc; .xmp được chép ra thư mục tạm rồi mới ghi thử)")
    print(f"\n  Đang chạy app để nó tự kiểm (tối đa {CHO / 60:.0f} phút)...")
    try:
        r = subprocess.run([str(exe)], env=env, capture_output=True,
                           timeout=CHO, text=True, errors="replace")
        ma = r.returncode
    except subprocess.TimeoutExpired:
        loi.append(f"App không thoát sau {CHO / 60:.0f} phút — nhiều khả năng "
                   "nó mở cửa sổ thay vì chạy tự kiểm, hoặc treo lúc nạp torch")
        ma = None
        r = None

    if bao.is_file():
        van = bao.read_text(encoding="utf-8")
        print("\n" + "\n".join("  " + d for d in van.splitlines()))
        if "TAT CA DAT" not in van:
            loi.append("Bài tự kiểm bên trong gói KHÔNG đạt — xem các dòng "
                       "[HONG] ở trên")
    else:
        loi.append(f"App không ghi được báo cáo tự kiểm ra {bao}")
        if r is not None:
            #[[ App --windowed khong co console nen stdout thuong rong. Loi that
            #   thi nam o stderr, va do la manh moi duy nhat con lai.
            #]]
            for ten, d in (("stdout", r.stdout), ("stderr", r.stderr)):
                if (d or "").strip():
                    print(f"\n  --- {ten} của app ---\n" +
                          "\n".join("  " + x for x in d.strip().splitlines()[-25:]))
    if ma not in (0, None):
        loi.append(f"App thoát với mã {ma} (đáng lẽ 0)")

    # ── Lớp 3b: gói có bị ghi vào không ─────────────────────────────────────
    sau = anh_chup(goi)
    them = sorted(set(sau) - set(truoc))
    doi = sorted(k for k in set(sau) & set(truoc) if sau[k] != truoc[k])
    if them or doi:
        loi.append("App GHI VÀO THƯ MỤC GÓI khi chạy: "
                   + ", ".join((them + doi)[:6])
                   + " — trên Windows nếu gói nằm trong Program Files thì các "
                     "file này bị chuyển hướng sang VirtualStore và người dùng "
                     "sẽ mất dữ liệu mà không hề có thông báo lỗi")
    else:
        print("\n  [DAT ] App không ghi gì vào thư mục gói")

    dl = tam / "du_lieu"
    if dl.is_dir() and any(dl.iterdir()):
        print(f"  [DAT ] App ghi dữ liệu ra đúng thư mục dữ liệu "
              f"({len(list(dl.rglob('*')))} mục)")
    else:
        loi.append(f"App không ghi gì vào thư mục dữ liệu {dl} — nhiều khả năng "
                   "nó vẫn đang ghi vào chỗ khác")

    print()
    for m in loi:
        print("  [!]", m)
    print("GÓI ĐẠT" if not loi else f"{len(loi)} VẤN ĐỀ")
    print(f"\n  (thư mục tạm của bài kiểm: {tam} — xoá được)")
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
