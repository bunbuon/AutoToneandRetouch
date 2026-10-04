#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dong_installer.py — bọc dist\\AutoTone (onedir) thành Setup.exe bằng Inno Setup.

VÌ SAO: người dùng muốn MỘT file cài đặt cho Windows, không phải thư mục/zip.
File này dò ISCC.exe (trình biên dịch Inno Setup) rồi chạy installer_win.iss với
tham số tên/phiên bản/icon — để đổi tên hay icon KHÔNG phải sửa .iss.

    python dong_installer.py                         # ten=AutoTone, ban tu cap_nhat
    python dong_installer.py --ten "AutoTone Pro"    # doi ten hien thi
    python dong_installer.py --icon icon.ico         # gan icon
    python dong_installer.py --nguon dist\\AutoTone    # goi khac mac dinh

Chạy SAU khi đã có dist\\AutoTone (dong_goi.py --bao-mat --nhe). Ra:
dist\\<ten>-Setup.exe
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parent


def tim_iscc() -> Path | None:
    """Dò ISCC.exe ở các chỗ Inno Setup hay cài."""
    import shutil
    tren_path = shutil.which("ISCC") or shutil.which("iscc")
    if tren_path:
        return Path(tren_path)
    ung_vien = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    ]
    for p in ung_vien:
        if p.is_file():
            return p
    return None


def main(argv=None) -> int:
    for _l in (sys.stdout, sys.stderr):
        try:
            _l.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass

    ap = argparse.ArgumentParser(description="Dong Setup.exe cho Windows bang Inno Setup.")
    ap.add_argument("--ten", default="AutoTone", help="Ten hien thi cua app")
    ap.add_argument("--nguon", type=Path, default=GOC / "dist" / "AutoTone",
                    help="Thu muc goi onedir (mac dinh dist/AutoTone)")
    ap.add_argument("--exe", default="AutoTone.exe", help="Ten file chay trong goi")
    ap.add_argument("--icon", type=Path, default=None, help="File .ico cho shortcut/Setup")
    ap.add_argument("--ban", default=None, help="Phien ban (mac dinh lay cap_nhat.PHIEN_BAN_APP)")
    ap.add_argument("--publisher", default="SAY MEDIA")
    ap.add_argument("--ra", type=Path, default=GOC / "dist", help="Thu muc xuat Setup.exe")
    a = ap.parse_args(argv)

    iscc = tim_iscc()
    if iscc is None:
        print("  [!] Khong tim thay ISCC.exe (Inno Setup chua cai).")
        print("      Cai: winget install --id JRSoftware.InnoSetup -e")
        print("      Hoac tai: https://jrsoftware.org/isdl.php")
        return 1

    nguon = a.nguon.resolve()
    if not (nguon / a.exe).is_file():
        print(f"  [!] Khong thay {nguon / a.exe}.")
        print("      Dong goi truoc: python dong_goi.py --bao-mat --nhe ...")
        return 1

    if a.ban:
        ban = a.ban
    else:
        try:
            sys.path.insert(0, str(GOC))
            import cap_nhat
            ban = cap_nhat.PHIEN_BAN_APP
        except Exception:                                    # noqa: BLE001
            ban = "1.0"

    iss = GOC / "installer_win.iss"
    if not iss.is_file():
        print(f"  [!] Khong thay {iss}.")
        return 1

    #[[ TEN FILE AN TOAN: bo & va ky tu la khoi ten thu muc / Setup.exe. Ten
    #   HIEN THI (--ten) giu nguyen "Tone&Retouch"; ten file thanh "Tone-Retouch".
    #   Windows cho & trong ten file nhung no gay roi shell/URL — tranh han. ]]
    import re
    ten_file = re.sub(r"[^\w.-]+", "-", a.ten).strip("-") or "App"

    cmd = [str(iscc),
           f"/DTenApp={a.ten}",
           f"/DTenFile={ten_file}",
           f"/DPhienBan={ban}",
           f"/DNguon={nguon}",
           f"/DExe={a.exe}",
           f"/DPublisher={a.publisher}",
           f"/DRaDir={a.ra.resolve()}"]
    if a.icon:
        ic = a.icon.resolve()
        if not ic.is_file():
            print(f"  [!] Khong thay icon {ic}.")
            return 1
        cmd.append(f"/DIcon={ic}")
    cmd.append(str(iss))

    print(f"  Ten: {a.ten}   Ban: {ban}   Icon: {a.icon or '(mac dinh)'}")
    print(f"  Nguon: {nguon}")
    print("  " + " ".join(f'"{c}"' if " " in c else c for c in cmd) + "\n")

    a.ra.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(cmd, cwd=str(GOC))
    if r.returncode:
        print(f"  [!] Inno Setup loi, ma {r.returncode}")
        return r.returncode

    ra_file = a.ra / f"{ten_file}-Setup.exe"
    if ra_file.is_file():
        print(f"\n  Setup: {ra_file}  ({ra_file.stat().st_size / 1e6:.0f} MB)")
    else:
        print(f"\n  Xong, nhung khong thay {ra_file} — xem log tren.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
