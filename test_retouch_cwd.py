#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_retouch_cwd.py — kiem retouch.cwd_retouch() dung mo hinh ban va.

LUAT: goi HAM THAT retouch.cwd_retouch (khong chep logic). Phai THU NGUOC duoc.

Noi dung: cwd_retouch la cach NOI phan "cap nhat mo hinh" voi saytool — saytool
nap mo hinh theo duong tuong doi so voi CWD, nen khi co ban va mang mo_hinh/ moi,
ta tra ve mot thu muc LOP PHU (mo hinh goi + va, va de len) de lam CWD.

Chay:  python test_retouch_cwd.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

GOC = Path(__file__).resolve().parent
sys.path.insert(0, str(GOC))


class Bao:
    def __init__(self):
        self.loi = []
        self.n = 0

    def ok(self, dieu, ten, ghi=""):
        self.n += 1
        print(("  [ok] " if dieu else "  [HONG] ") + ten
              + (f"  — {ghi}" if ghi and not dieu else ""))
        if not dieu:
            self.loi.append(ten)

    def xong(self):
        print("-" * 56)
        if self.loi:
            print(f"{len(self.loi)}/{self.n} HONG: " + ", ".join(self.loi))
            return 1
        print(f"TAT CA {self.n} MUC DAT")
        return 0


def main() -> int:
    import retouch as rt
    b = Bao()

    with tempfile.TemporaryDirectory(prefix="rtcwd_") as tmp:
        tmp = Path(tmp)
        os.environ["AUTOTONE_DATA"] = str(tmp)   # noi goc_du_lieu() -> lop phu
        os.environ.pop("AUTOTONE_MO_HINH_VA", None)

        #[[ Gia lap "goc trong goi": thu muc co saytool/cli.py + mo_hinh/ goc. ]]
        goi = tmp / "goi"
        (goi / "saytool").mkdir(parents=True)
        (goi / "saytool" / "cli.py").write_text("# gia", encoding="utf-8")
        (goi / "mo_hinh").mkdir()
        (goi / "mo_hinh" / "vet.pt").write_text("VET-GOC", encoding="utf-8")
        (goi / "mo_hinh" / "nhan.pt").write_text("NHAN-GOC", encoding="utf-8")

        # ---- 1. KHONG co bien -> cwd_retouch tra ve chinh goc ----
        b.ok(Path(rt.cwd_retouch(goi)) == goi,
             "khong co ban va -> cwd_retouch = goc (duong cu khong doi)")

        # ---- 2. Co ban va mang vet.pt MOI -> lop phu, va de len goc ----
        va = tmp / "ban_va" / "mo_hinh"
        va.mkdir(parents=True)
        va.joinpath("vet.pt").write_text("VET-VA-MOI", encoding="utf-8")  # chi thay vet
        os.environ["AUTOTONE_MO_HINH_VA"] = str(va)

        cwd = Path(rt.cwd_retouch(goi))
        b.ok(cwd != goi, "co ban va -> cwd_retouch tra ve thu muc LOP PHU (khac goc)")
        mh = cwd / "mo_hinh"
        b.ok(mh.is_dir(), "lop phu co thu muc mo_hinh/")
        # vet.pt phai la ban VA
        b.ok((mh / "vet.pt").read_text(encoding="utf-8") == "VET-VA-MOI",
             "vet.pt trong lop phu = ban VA (va de len goc)",
             f"doc duoc: {(mh/'vet.pt').read_text(encoding='utf-8')}")
        # nhan.pt KHONG co trong ban va -> giu ban GOC (khong mat)
        b.ok((mh / "nhan.pt").read_text(encoding="utf-8") == "NHAN-GOC",
             "nhan.pt (ban va khong dung toi) van la ban GOC — khong mat mo hinh")

        # ---- 3. saytool van duoc chon dung lenh: goc GIU nguyen, khong doi ----
        #[[ cwd_retouch KHONG duoc doi `goc` — neu doi, la_goc_trong_goi sai va
        #   lenh_saytool nham sang `python -m` (goi khong co python). Kiem: goc
        #   truyen vao van la goc tra ra o truong hop 1; va cwd (lop phu) KHAC goc. ]]
        b.ok(cwd != goi and (goi / "saytool" / "cli.py").is_file(),
             "goc giu nguyen (de lenh_saytool chon --say-chay), chi CWD doi")

        # ---- 4. Dung lai lop phu: goi lan 2 cung ban va -> cung thu muc ----
        cwd2 = Path(rt.cwd_retouch(goi))
        b.ok(cwd2 == cwd, "goi lai cung ban va -> dung lai lop phu (khong dung lai tu dau)")

        # ---- 5. Doi sang ban va KHAC -> lop phu dung lai theo ban moi ----
        va2 = tmp / "ban_va2" / "mo_hinh"
        va2.mkdir(parents=True)
        va2.joinpath("vet.pt").write_text("VET-VA-2", encoding="utf-8")
        os.environ["AUTOTONE_MO_HINH_VA"] = str(va2)
        cwd3 = Path(rt.cwd_retouch(goi))
        b.ok((cwd3 / "mo_hinh" / "vet.pt").read_text(encoding="utf-8") == "VET-VA-2",
             "doi ban va -> lop phu cap nhat theo ban va moi")

        # ---- 6. Thu muc va KHONG ton tai -> lui ve goc (an toan) ----
        os.environ["AUTOTONE_MO_HINH_VA"] = str(tmp / "khong_co")
        b.ok(Path(rt.cwd_retouch(goi)) == goi,
             "bien tro thu muc khong ton tai -> lui ve goc")

        os.environ.pop("AUTOTONE_MO_HINH_VA", None)

    return b.xong()


if __name__ == "__main__":
    sys.exit(main())
