#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kiem_khoa.py — Kiểm cơ chế hạn dùng thử và mã gia hạn.

    python kiem_khoa.py

Chạy trên thư mục trạng thái TẠM nên không đụng gì tới giấy phép thật đang có
trên máy. Mọi phép kiểm đều gọi hàm thật trong khoa.py.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import khoa   # noqa: E402


class GioGia:
    """Giả lập đồng hồ máy. khoa.py chỉ lấy giờ qua datetime.now(timezone.utc)."""

    def __init__(self, moc):
        self.moc = moc

    def __call__(self, tz=None):
        return self.moc.astimezone(tz) if tz else self.moc


def chay(moc):
    with mock.patch.object(khoa, "datetime", wraps=datetime) as m:
        m.now = GioGia(moc)
        m.fromisoformat = datetime.fromisoformat
        return khoa.kiem()


def main() -> int:
    #[[ Console cp1252 khong in noi chu Viet — bai kiem DAT van chet o dong
    #   tong ket, trong y het bai kiem hong. Xem ghi chu trong _cua_saytool(). ]]
    for _l in (sys.stdout, sys.stderr):
        try:
            _l.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass

    loi = []
    #[[ Dat AUTOTONE_DATA thay vi va de len ham: nhu vay bai kiem di qua DUNG
    #   con duong ma app that su dung, ke ca khi da dong goi.
    #]]
    tam = Path(tempfile.mkdtemp())
    cu_env = os.environ.get("AUTOTONE_DATA")
    os.environ["AUTOTONE_DATA"] = str(tam)

    #[[ TU BAT LAI KHOA TRONG TIEN TRINH NAY.
    #
    #   khoa.BAT_KHOA co the dang la False tren may dang phat trien (co y —
    #   xem ghi chu trong khoa.py). Neu de nguyen thi moi phep kiem ben duoi
    #   deu thay "chay duoc" va bai kiem BAO DAT MA KHONG KIEM GI CA — kieu
    #   hong te nhat: mot bai kiem mu van in ra "TAT CA DAT".
    #
    #   Bat lai o day chi anh huong tien trinh nay, khong sua file.
    #]]
    khoa_cu = khoa.BAT_KHOA
    khoa.BAT_KHOA = True

    han = khoa._moc_han()
    truoc = han - timedelta(hours=10)
    sau = han + timedelta(hours=1)

    # 1 — trước hạn thì chạy được
    k = chay(truoc)
    if not k["chay_duoc"]:
        loi.append(f"Truoc han ma da khoa: {k['ly_do']}")
    if k["con_lai"] is None or abs(k["con_lai"] - timedelta(hours=10)) > timedelta(minutes=1):
        loi.append(f"Con lai tinh sai: {k['con_lai']}")

    # 2 — sau hạn thì khoá
    k = chay(sau)
    if k["chay_duoc"]:
        loi.append("Qua han ma van chay duoc")
    if "Hết hạn" not in k["ly_do"]:
        loi.append(f"Ly do khoa khong ro: {k['ly_do']!r}")

    #[[ 3 — VAN DONG HO LUI. Chay o han-1h (ghi moc cao), roi van ve han-30h.
    #]]
    (tam / "khoa.json").unlink(missing_ok=True)
    chay(han - timedelta(hours=1))
    k = chay(han - timedelta(hours=30))
    if k["chay_duoc"]:
        loi.append("Van dong ho lui 29 tieng ma van chay duoc")
    if "lùi" not in k["ly_do"]:
        loi.append(f"Khong nhan ra la van dong ho: {k['ly_do']!r}")

    # 4 — lệch nhỏ trong dung sai thì KHÔNG được coi là gian lận
    (tam / "khoa.json").unlink(missing_ok=True)
    chay(truoc)
    k = chay(truoc - timedelta(minutes=2))
    if not k["chay_duoc"]:
        loi.append(f"Lech 2 phut ma da bao gian lan: {k['ly_do']!r}")

    #[[ 5 — SUA FILE TRANG THAI BANG TAY. Doi mot ky tu trong moc_cao.
    #]]
    (tam / "khoa.json").unlink(missing_ok=True)
    chay(truoc)
    p = tam / "khoa.json"
    p.write_text(p.read_text(encoding="utf-8").replace('"moc_cao": "2', '"moc_cao": "1'),
                 encoding="utf-8")
    k = chay(truoc)
    if k["chay_duoc"]:
        loi.append("Sua file trang thai bang tay ma van chay duoc")

    # 6 — mã gia hạn đúng thì mở lại được
    (tam / "khoa.json").unlink(missing_ok=True)
    chay(truoc)
    ma = khoa.tao_ma(khoa.ma_may(), han + timedelta(hours=72))
    with mock.patch.object(khoa, "datetime", wraps=datetime) as m:
        m.now = GioGia(sau)
        m.fromisoformat = datetime.fromisoformat
        ok, moi, nhan = khoa.nhap_ma(ma)
    if not ok:
        loi.append(f"Ma dung ma bi tu choi: {nhan}")
    k = chay(sau)
    if not k["chay_duoc"]:
        loi.append(f"Gia han xong ma van khoa: {k['ly_do']}")
    k = chay(han + timedelta(hours=80))
    if k["chay_duoc"]:
        loi.append("Qua ca han da gia han ma van chay duoc")

    # 7 — mã sai / mã của máy khác thì từ chối
    for xau, ten in (("ABCD-EFGH-IJKL-MNOP-QRST", "ma bia"),
                     (khoa.tao_ma("KHACMAYKHAC", han + timedelta(hours=72)),
                      "ma cua may khac"),
                     ("", "ma rong")):
        ok, _moi, _n = khoa.nhap_ma(xau)
        if ok:
            loi.append(f"Chap nhan {ten}: {xau!r}")

    #[[ 8 — SO GIO SINH MA phai nam trong danh sach app do. Day la cho de lech
    #   nhat giua tao_ma.py va khoa.py, va lech thi ma dung van bi tu choi.
    #]]
    import tao_ma
    ds = tao_ma.moc_app_do()
    for gio in ds:
        ok, _m, _n = khoa.nhap_ma(khoa.tao_ma(khoa.ma_may(),
                                              han + timedelta(hours=gio)))
        if not ok:
            loi.append(f"App khong nhan ma {gio} gio du no nam trong danh sach do")

    #[[ 9 — MA MAY PHAI ON DINH QUA TIEN TRINH, khong phai trong mot tien trinh.
    #
    #   Ban cu kiem "ma_may() != ma_may()" trong cung mot tien trinh va luon dat,
    #   ke ca khi ma may that su doi moi lan mo app: uuid.getnode() nho ket qua
    #   trong bien module nen goi lan hai chi doc lai cai da nho.
    #
    #   Loi that da xay ra: getnode() BIA RA so ngau nhien khi khong doc duoc
    #   card mang, va bia moi lan chay. Ma may doi -> chu ky file trang thai
    #   khong khop -> app khoa dung nguoi dung hop le. Chi goi qua TIEN TRINH CON
    #   moi thay.
    #]]
    if len(khoa.ma_may()) != 12:
        loi.append(f"Ma may dai {len(khoa.ma_may())}, dang le 12")
    lay = [subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, sys.argv[1]); import khoa; print(khoa.ma_may())",
         str(Path(khoa.__file__).parent)],
        capture_output=True, text=True, env={**os.environ, "AUTOTONE_DATA": str(tam)},
    ).stdout.strip() for _ in range(3)]
    if len(set(lay)) != 1:
        loi.append(f"Ma may DOI giua cac lan chay: {lay} — nguoi dung hop le se "
                   "bi khoa ngay lan mo app sau khi nhap ma gia han")
    elif lay[0] != khoa.ma_may():
        loi.append(f"Ma may trong tien trinh con ({lay[0]}) khac trong tien "
                   f"trinh nay ({khoa.ma_may()})")

    #[[ 9b — nguon dinh danh khong duoc la so getnode() bia ra. Kiem thang vao
    #   nguon chu khong qua ma bam, vi bam roi thi khong con phan biet duoc.
    #]]
    ng = khoa.nguon_ma_may()
    if not ng.split("|")[0].split(":")[0] in ("win", "mac", "nix", "luu"):
        loi.append(f"Nguon ma may la {ng!r} — khong ro tu dau ra")
    if khoa._mac_that() is None and ng.startswith("mac:"):
        loi.append("Dung MAC du getnode() dang bia so ngau nhien")

    #[[ 10 — tao_ma.py KHONG DUOC nam trong goi cai. Kiem o day vi day la cho
    #   duy nhat chay moi lan; de trong tai lieu thi khong ai doc.
    #]]
    import dong_goi
    if "tao_ma" not in " ".join(dong_goi.LOAI_TRU):
        loi.append("dong_goi.py khong loai tao_ma.py ra khoi goi — bat ky ai co "
                   "goi cai deu tu sinh duoc ma gia han")

    #[[ 10b — tu_kiem PHAI nam trong NGAM. autotone_gui chi import no ben trong
    #   main() nen PyInstaller khong tu do ra. Thieu no thi goi build xong van
    #   chay, chi la lenh tu kiem im lang — tuc mat cach duy nhat kiem thu goi
    #   ma khong nhan ra la da mat.
    #]]
    if "tu_kiem" not in dong_goi.NGAM:
        loi.append("dong_goi.NGAM thieu tu_kiem — goi build ra se khong tu kiem "
                   "duoc, va kiem_goi.py se bao 'app khong ghi bao cao'")
    for f in ("kiem_goi.py", "kiem_do_mat.py"):
        if f not in dong_goi.LOAI_TRU:
            loi.append(f"dong_goi.LOAI_TRU thieu {f}")

    # 11 — hạn phải đúng 72 giờ kể từ 01:00 04/09/2026 giờ VN
    mong = datetime(2026, 9, 4, 1, 0, tzinfo=timezone(timedelta(hours=7))) \
        + timedelta(hours=72)
    if khoa._moc_han() != mong:
        loi.append(f"Han sai: {khoa._moc_han()} != {mong}")
    if khoa.HAN_ISO[-6:] not in ("+07:00",):
        loi.append("HAN_ISO khong ghi kem mui gio — may dat mui gio khac se "
                   "hieu ra mot moc khac")

    # 12 — tat khoa thi phai tat HAN, va phai noi ra la dang tat
    khoa.BAT_KHOA = False
    k = chay(sau)                      # moc SAU han goc
    if not k["chay_duoc"]:
        loi.append("BAT_KHOA=False ma van khoa")
    if not k.get("tat"):
        loi.append("BAT_KHOA=False nhung kiem() khong bao co 'tat' — giao dien "
                   "khong biet duong an phan dem nguoc")
    if k["con_lai"] is not None:
        #[[ De nguyen hieu so thi giao dien in ra "con da het han" mau cam,
        #   bao dong ve mot thu da tat. Phai la None. ]]
        loi.append(f"BAT_KHOA=False ma con_lai van co gia tri: {k['con_lai']}")
    if khoa.mo_ta_con_lai(k["con_lai"]) != "—":
        loi.append("mo_ta_con_lai(None) phai ra dau gach")

    # 13 — dong goi phai BI CHAN khi khoa dang tat
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import dong_goi
        if dong_goi.chot_khoa(False):
            loi.append("dong_goi van cho dong goi khi BAT_KHOA=False — ban giao "
                       "cho nguoi khac se khong co khoa ma khong ai biet")
        if not dong_goi.chot_khoa(True):
            loi.append("dong_goi chan ca khi da go --khong-khoa")
        khoa.BAT_KHOA = True
        if not dong_goi.chot_khoa(False):
            loi.append("dong_goi chan nham khi BAT_KHOA=True")
    except ImportError as ex:
        loi.append(f"khong nap duoc dong_goi: {ex}")
    khoa.BAT_KHOA = khoa_cu

    if cu_env is None:
        os.environ.pop("AUTOTONE_DATA", None)
    else:
        os.environ["AUTOTONE_DATA"] = cu_env
    shutil.rmtree(tam, ignore_errors=True)
    for m in loi:
        print("  [!]", m)
    print("TAT CA DAT" if not loi else f"{len(loi)} LOI")
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
