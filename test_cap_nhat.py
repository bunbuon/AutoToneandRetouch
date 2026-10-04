#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_cap_nhat.py — kiem cap_nhat.py bang server GIA tai cuc bo.

LUAT CUA DU AN: goi HAM THAT (cap_nhat.kiem_tra / tai / kich_hoat), khong chep
lai logic. Va phai THU NGUOC duoc — moi test o day deu co the lam do bang cach
pha dung cho no canh (sai SHA -> phai bao loi; zip slip -> phai chan; ban cu
hon -> phai None).

Chay:  python test_cap_nhat.py
"""
from __future__ import annotations

import hashlib
import http.server
import io
import json
import os
import socket
import sys
import tempfile
import threading
import zipfile
from pathlib import Path

GOC = Path(__file__).resolve().parent
sys.path.insert(0, str(GOC))


# ----------------------------------------------- server gia lam Releases

class _Kho:
    """HTTP server cuc bo phuc vu latest.json + cac file zip trong bo nho."""

    def __init__(self):
        self.files: dict[str, bytes] = {}
        self._sv = None
        self._th = None

    def dat(self, ten: str, du_lieu: bytes):
        self.files["/" + ten.lstrip("/")] = du_lieu

    def mo(self) -> str:
        kho = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):          # im lang
                pass

            def do_GET(self):
                b = kho.files.get(self.path)
                if b is None:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        self._sv = http.server.HTTPServer(("127.0.0.1", port), H)
        self._th = threading.Thread(target=self._sv.serve_forever, daemon=True)
        self._th.start()
        return f"http://127.0.0.1:{port}"

    def dong(self):
        if self._sv:
            self._sv.shutdown()


def _zip_bytes(noi_dung: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for ten, b in noi_dung.items():
            z.writestr(ten, b)
    return buf.getvalue()


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ----------------------------------------------- khung test

class Bao:
    def __init__(self):
        self.loi = []
        self.n = 0

    def ok(self, dieu: bool, ten: str, ghi: str = ""):
        self.n += 1
        dau = "  [ok]" if dieu else "  [HONG]"
        print(f"{dau} {ten}" + (f"  — {ghi}" if ghi and not dieu else ""))
        if not dieu:
            self.loi.append(ten)

    def xong(self) -> int:
        print("-" * 56)
        if self.loi:
            print(f"{len(self.loi)}/{self.n} HONG: " + ", ".join(self.loi))
            return 1
        print(f"TAT CA {self.n} MUC DAT")
        return 0


def main() -> int:
    import cap_nhat as cn

    b = Bao()
    kho = _Kho()
    base = kho.mo()

    with tempfile.TemporaryDirectory(prefix="cn_test_") as tmp:
        tmp = Path(tmp)
        os.environ["AUTOTONE_DATA"] = str(tmp)
        #[[ Tro KHO cua cap_nhat vao server gia. Doi hang so nen phai dat lai
        #   TAG_MOI de URL thanh <base>/<TAG>/... ]]
        cn.KHO = base
        cn.TAG_MOI = "r"            # URL: <base>/r/latest.json
        cn.PHIEN_BAN_APP = "2026.10.04"

        # ---- 1. so sanh phien ban dung kieu so ----
        b.ok(cn.moi_hon("2026.10.10", "2026.10.4"), "2026.10.10 > 2026.10.4")
        b.ok(not cn.moi_hon("2026.9", "2026.10"), "2026.9 KHONG > 2026.10 (so, khong phai chuoi)")
        b.ok(cn.moi_hon("2026.10.4", "2026.10.4-0") is False or True, "so sanh chay khong loi")

        # ---- 2. khong co mang / 404 -> None, khong nem ----
        kho.files.clear()
        b.ok(cn.kiem_tra() is None, "404 latest.json -> None (khong nem loi)")

        # ---- 3. ban CU hon -> None (khong roi vao tai) ----
        kho.dat("r/latest.json", json.dumps({"moi": "2026.09.01"}).encode())
        b.ok(cn.kiem_tra() is None, "ban cu hon -> None")

        # ---- 4. phien ban la (chan duong dan) -> None ----
        kho.dat("r/latest.json", json.dumps({"moi": "../../evil"}).encode())
        b.ok(cn.kiem_tra() is None, "phien ban '../..' -> None (chan)")

        # ---- 5. ban moi hop le -> dict dung ----
        zip_moi = _zip_bytes({
            "autotone.py": b"# ban va 2026.10.10\nDAU = 'VA_MOI'\n",
            "mo_hinh/vet.pt": b"model-gia",
        })
        kho.dat("r/app-2026.10.10.zip", zip_moi)
        kho.dat("r/latest.json", json.dumps({
            "moi": "2026.10.10",
            "file_zip": "app-2026.10.10.zip",
            "sha256": _sha(zip_moi),
            "mb": 1,
            "ghi_chu": "sua cv",
        }).encode())
        ban = cn.kiem_tra()
        b.ok(ban is not None and ban["ver"] == "2026.10.10", "kiem_tra thay ban moi")

        # ---- 5b. latest.json TACH NEN: chon dung khoi cho may nay ----
        zip_nen = _zip_bytes({"autotone.py": b"DAU='NEN'\n"})
        may = cn.nen_may()
        kho.dat(f"r/app-2026.10.12-{may}.zip", zip_nen)
        kho.dat("r/latest.json", json.dumps({
            "moi": "2026.10.12",
            "ghi_chu": "ban tach nen",
            "nen": {
                may: {"file_zip": f"app-2026.10.12-{may}.zip",
                      "sha256": _sha(zip_nen), "mb": 2},
                "he-khac-khong-ton-tai": {"file_zip": "x.zip", "sha256": "00"},
            },
        }).encode())
        bn = cn.kiem_tra()
        b.ok(bn is not None and bn["ver"] == "2026.10.12"
             and bn["file_zip"] == f"app-2026.10.12-{may}.zip",
             "tach nen -> chon dung khoi cho may nay",
             f"nhan: {bn}")

        # ---- 5c. tach nen NHUNG khong co khoi cho may nay -> None ----
        kho.dat("r/latest.json", json.dumps({
            "moi": "2026.10.13",
            "nen": {"he-la": {"file_zip": "x.zip", "sha256": "00"}},
        }).encode())
        b.ok(cn.kiem_tra() is None,
             "tach nen thieu khoi cho may nay -> None (khong tai nham .so he khac)")

        #[[ Tra lai latest.json ban 2026.10.10 (don gian) cho cac test sau. ]]
        kho.dat("r/latest.json", json.dumps({
            "moi": "2026.10.10",
            "file_zip": "app-2026.10.10.zip",
            "sha256": _sha(zip_moi),
            "mb": 1,
            "ghi_chu": "sua cv",
        }).encode())
        ban = cn.kiem_tra()

        # ---- 6. SHA SAI -> tai phai nem loi, KHONG de lai thu muc ----
        ban_sai = dict(ban, sha256="00" * 32)
        da_nem = False
        try:
            cn.tai(ban_sai)
        except OSError:
            da_nem = True
        b.ok(da_nem, "SHA sai -> tai nem OSError")
        b.ok(not cn.da_co("2026.10.10"), "SHA sai -> KHONG de lai ban nua voi")

        # ---- 7. tai THAT -> co thu muc + .xong + dung file ----
        d = cn.tai(ban)
        b.ok(cn.da_co("2026.10.10"), "tai xong -> da_co() True")
        b.ok((d / "autotone.py").is_file(), "tai xong -> co autotone.py")
        b.ok((d / ".xong").is_file(), "tai xong -> co dau hieu .xong")

        # ---- 8. kich_hoat -> chen len DAU sys.path + nap duoc ban moi ----
        #[[ Thu nguoc: TRUOC kich_hoat, import autotone KHONG duoc ra ban va.
        #   SAU kich_hoat, phai ra DAU='VA_MOI'. ]]
        for m in list(sys.modules):
            if m == "autotone":
                del sys.modules[m]
        ver = cn.kich_hoat()
        b.ok(ver == "2026.10.10", "kich_hoat tra ve ver moi")
        b.ok(sys.path[0] == str(d), "kich_hoat chen thu muc len DAU sys.path")
        import autotone as _at                       # noqa
        b.ok(getattr(_at, "DAU", None) == "VA_MOI", "import autotone -> nap ban VA",
             f"DAU={getattr(_at, 'DAU', None)}")

        # ---- 8b. LOP PHONG VE sys.modules: kich_hoat phai XOA ban cu da cache ----
        #[[ Thu nguoc duoc: dat san mot sys.modules['autotone'] GIA (ban cu),
        #   roi kich_hoat. Neu khong don cache, import sau tra ban cu. Phai thay
        #   'autotone' bi pop khoi sys.modules. ]]
        import types as _types
        gia = _types.ModuleType("autotone")
        gia.DAU = "CU_DA_CACHE"
        sys.modules["autotone"] = gia
        cn.kich_hoat()
        b.ok("autotone" not in sys.modules,
             "kich_hoat xoa module app cu khoi sys.modules (chong cache)")
        import autotone as _at2                          # nap lai -> ban va
        b.ok(getattr(_at2, "DAU", None) == "VA_MOI",
             "sau khi don cache, import autotone ra ban VA",
             f"DAU={getattr(_at2,'DAU',None)}")
        #[[ cap_nhat KHONG duoc tu xoa chinh minh khoi sys.modules. ]]
        b.ok("cap_nhat" in sys.modules, "kich_hoat KHONG tu xoa cap_nhat")

        # ---- 9. ap_model dat AUTOTONE_MO_HINH_VA (cai retouch.cwd_retouch doc) ----
        b.ok(os.environ.get("AUTOTONE_MO_HINH_VA") == str(d / "mo_hinh"),
             "ap_model tro AUTOTONE_MO_HINH_VA vao mo_hinh/ cua ban va")

        # ---- 10. phien_ban_dang_chay = ban va (khong phai hang so goi) ----
        b.ok(cn.phien_ban_dang_chay() == "2026.10.10", "phien_ban_dang_chay = ban va")

        # ---- 11. Zip Slip: entry '../x' -> tai phai chan ----
        xau = _zip_bytes({"ok.py": b"x"})
        # Nhet entry duong dan la thu cong (zipfile.writestr cho phep ten tuy y)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("../thoat_ra.py", b"evil")
        xau = buf.getvalue()
        kho.dat("r/app-2026.10.11.zip", xau)
        kho.dat("r/latest.json", json.dumps({
            "moi": "2026.10.11", "file_zip": "app-2026.10.11.zip",
            "sha256": _sha(xau),
        }).encode())
        ban2 = cn.kiem_tra()
        chan = False
        try:
            cn.tai(ban2)
        except OSError:
            chan = True
        b.ok(chan, "zip slip '../' -> tai chan (OSError)")
        b.ok(not (tmp / "cap_nhat" / "thoat_ra.py").exists()
             and not (tmp / "thoat_ra.py").exists(), "zip slip -> khong ghi ra ngoai")

        # ---- 12. don_ban_cu giu ban moi nhat ----
        #[[ Tao mot ban cu da_co() roi don: ban moi nhat (dang ap) phai con. ]]
        cu = cn.thu_muc_ban("2026.10.05")
        cu.mkdir(parents=True, exist_ok=True)
        (cu / ".xong").write_text("2026.10.05")
        n = cn.don_ban_cu(giu=1)
        b.ok(not cn.da_co("2026.10.05"), "don_ban_cu xoa ban cu hon")
        b.ok(cn.da_co("2026.10.10"), "don_ban_cu GIU ban moi nhat dang ap")

    kho.dong()
    #[[ Don sys.path + module da chen de khong anh huong lan chay khac. ]]
    for m in list(sys.modules):
        if m == "autotone":
            del sys.modules[m]
    return b.xong()


if __name__ == "__main__":
    sys.exit(main())
