#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kiem_ota.py — thử MỘT bản cập nhật OTA trên một gói THẬT trước khi phát hành.

    python kiem_ota.py <thư mục gói, vd dist/AutoTone> <app-...zip>

Giải nén bản OTA vào thư mục dữ liệu TẠM dưới số phiên bản giả 2099.1.1 (luôn mới hơn
gói) như cap_nhat.tai() để lại, rồi chạy chính file chạy của gói ở chế độ tự kiểm
(AUTOTONE_TU_KIEM, như kiem_goi). ĐẠT khi: tự kiểm TẤT CẢ ĐẠT VÀ dòng "Bản đang chạy"
nói lõi nạp TỪ BẢN CẬP NHẬT — tức trên đúng hệ điều hành / kiến trúc này, gói nạp được
.pyd / .so của bản vá và chạy đúng (13/10: lần đầu phát hành OTA cho cả Mac).

Không đụng dữ liệu thật trên máy, không tải gì qua mạng."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kiem_goi  # noqa: E402

VER_GIA = "2099.1.1"


def main(argv=None) -> int:
    for _l in (sys.stdout, sys.stderr):
        try:
            _l.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        print(__doc__)
        return 2
    goi, zp = Path(argv[0]).resolve(), Path(argv[1]).resolve()
    exe = kiem_goi.file_chay(goi)
    if exe is None or not zp.is_file():
        print(f"  [!] Không thấy file chạy trong {goi} hoặc không có {zp}")
        return 2
    tam = Path(tempfile.mkdtemp(prefix="kiem_ota_"))
    va = tam / "du_lieu" / "cap_nhat" / VER_GIA
    va.mkdir(parents=True)
    with zipfile.ZipFile(zp) as z:
        z.extractall(va)
    (va / ".xong").write_text(VER_GIA, encoding="utf-8")
    bao = tam / "bao_cao.txt"
    env = {**os.environ, "AUTOTONE_DATA": str(tam / "du_lieu"), "AUTOTONE_TU_KIEM": str(bao)}
    print(f"  Gói {goi.name} + bản vá {zp.name} (giả {VER_GIA}) — đang tự kiểm...")
    try:
        r = subprocess.run([str(exe)], env=env, capture_output=True, timeout=kiem_goi.CHO,
                           text=True, errors="replace")
    except subprocess.TimeoutExpired:
        print("  [!] App không thoát — treo khi nạp bản vá?")
        return 1
    van = bao.read_text(encoding="utf-8", errors="replace") if bao.is_file() else ""
    dong = next((d for d in van.splitlines() if "Bản đang chạy" in d), "")
    print("  " + (dong or "(không có dòng 'Bản đang chạy')"))
    tu_va = "TỪ BẢN CẬP NHẬT" in dong and VER_GIA in dong
    dat = "TAT CA DAT" in van
    if not dat:
        print("\n".join("  " + d for d in van.splitlines() if "HONG" in d) or
              f"  (không có báo cáo; mã thoát {r.returncode})\n{r.stderr[-1500:]}")
    print(f"  [{'DAT ' if tu_va else 'HONG'}] lõi nạp từ bản cập nhật")
    print(f"  [{'DAT ' if dat else 'HONG'}] tự kiểm với bản vá")
    print("OTA ĐẠT" if (tu_va and dat) else "OTA HỎNG")
    return 0 if (tu_va and dat) else 1


if __name__ == "__main__":
    sys.exit(main())
