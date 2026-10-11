# -*- coding: utf-8 -*-
"""may_nhan_gop_y.py — MÁY NHẬN góp dữ liệu từ app Tone&Retouch của người test (12/10/2026).

Chạy trên máy ở nhà, sau đường hầm Cloudflare (tao_duong_ham_gop_y.bat):
    python may_nhan_gop_y.py                 (nghe 127.0.0.1:8100)

    POST /gop-y      thân = gói zip (gop_y.py phía app), đầu:
                       X-Gop-Y-Khoa  khoá chung (khớp gop_y.BI_MAT)  — sai -> 403
                       X-Nguoi       mã người gửi (băm key bản quyền)
                       X-Goi         tên gói
                     -> lưu <kho>/<người>/<ngày>/<gói>.zip + một dòng vào <kho>/so_nhan.jsonl
    GET  /suc-khoe   {"ok": true} — để kiểm đường hầm

Chỉ cho GHI một gói (có giới hạn dung lượng + số gói / người / ngày). Không có đường đọc
nào: lộ khoá trong app cũng không ai tải được dữ liệu của người khác.
Cấu hình: may_nhan_gop_y.json cạnh file này (tự tạo lần đầu):
    {"cong": 8100, "kho": "<thư mục lưu>", "bi_mat": "...", "toi_da_mb": 600, "goi_moi_ngay": 60}
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
import zipfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAU_HINH = HERE / "may_nhan_gop_y.json"
MAC_DINH = {"cong": 8100, "kho": str(Path.home() / "AutoTone_GopY"),
            "bi_mat": "jA4PRIql5Wzx9IgAtAQcawqSKjfXBG3C", "toi_da_mb": 600, "goi_moi_ngay": 60}
_SACH = re.compile(r"[^A-Za-z0-9._-]+")
_KHOA = threading.Lock()


def cau_hinh() -> dict:
    if not CAU_HINH.is_file():
        CAU_HINH.write_text(json.dumps(MAC_DINH, ensure_ascii=False, indent=2), encoding="utf-8")
    d = dict(MAC_DINH)
    try:
        d.update(json.loads(CAU_HINH.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return d


def log(*a):
    print(datetime.now().strftime("%m-%d %H:%M:%S"), *a, flush=True)


class XuLy(BaseHTTPRequestHandler):
    server_version = "AutoToneGopY/1"
    CF: dict = {}

    def _tra(self, ma: int, d: dict):
        b = json.dumps(d, ensure_ascii=False).encode("utf-8")
        self.send_response(ma)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *_a):              # gọn log: chỉ dòng của mình
        return

    def do_GET(self):
        if self.path.rstrip("/") == "/suc-khoe":
            return self._tra(200, {"ok": True})
        return self._tra(404, {"loi": "khong co"})

    def do_POST(self):
        cf = self.CF
        if self.path.rstrip("/") != "/gop-y":
            return self._tra(404, {"loi": "khong co"})
        if self.headers.get("X-Gop-Y-Khoa", "") != cf["bi_mat"]:
            return self._tra(403, {"loi": "sai khoa"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0 or n > cf["toi_da_mb"] * 1e6:
            return self._tra(413, {"loi": "dung luong"})
        nguoi = _SACH.sub("_", self.headers.get("X-Nguoi", "khong_ro"))[:40] or "khong_ro"
        goi = _SACH.sub("_", self.headers.get("X-Goi", "goi.zip"))[:120] or "goi.zip"
        if not goi.endswith(".zip"):
            goi += ".zip"
        ngay = datetime.now().strftime("%Y-%m-%d")
        kho = Path(cf["kho"])
        thu = kho / nguoi / ngay
        with _KHOA:
            thu.mkdir(parents=True, exist_ok=True)
            if len(list(thu.glob("*.zip"))) >= cf["goi_moi_ngay"]:
                return self._tra(429, {"loi": "qua so goi trong ngay"})
        tam = thu / (goi + f".{os.getpid()}.{threading.get_ident()}.part")
        con = n
        with open(tam, "wb") as fh:
            while con > 0:
                b = self.rfile.read(min(1 << 20, con))
                if not b:
                    break
                fh.write(b)
                con -= len(b)
        if con:
            tam.unlink(missing_ok=True)
            return self._tra(400, {"loi": "thieu du lieu"})
        try:
            with zipfile.ZipFile(tam) as zf:
                if "meta.json" not in zf.namelist():
                    raise ValueError("thieu meta.json")
                meta = json.loads(zf.read("meta.json").decode("utf-8"))
        except Exception as ex:                              # noqa: BLE001
            tam.unlink(missing_ok=True)
            return self._tra(400, {"loi": f"goi hong: {ex}"})
        dich = thu / goi
        if dich.exists():
            dich = thu / f"{dich.stem}_{int(time.time())}.zip"
        os.replace(tam, dich)
        dong = {"luc": datetime.now().isoformat(timespec="seconds"), "nguoi": nguoi, "goi": dich.name,
                "duong": str(dich.relative_to(kho)), "mb": round(n / 1e6, 2),
                "phien_ban": meta.get("phien_ban"), "than_may": meta.get("than_may"),
                "so_anh": meta.get("so_anh"), "anh_sua": meta.get("anh_sua"),
                "ip": self.headers.get("CF-Connecting-IP") or self.client_address[0]}
        with _KHOA:
            with open(kho / "so_nhan.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps(dong, ensure_ascii=False) + "\n")
        log(f"nhan {dich.name} · {nguoi} · {n / 1e6:.1f} MB · {meta.get('so_anh')} anh "
            f"({meta.get('anh_sua')} sua) · {', '.join(meta.get('than_may') or [])}")
        return self._tra(200, {"ok": True, "goi": dich.name})


def tao_may(cf: dict, cong: int | None = None) -> ThreadingHTTPServer:
    XuLy.CF = cf
    return ThreadingHTTPServer(("127.0.0.1", int(cong if cong is not None else cf["cong"])), XuLy)


def main() -> int:
    cf = cau_hinh()
    Path(cf["kho"]).mkdir(parents=True, exist_ok=True)
    may = tao_may(cf)
    log(f"may nhan gop y: http://127.0.0.1:{cf['cong']} -> {cf['kho']}")
    try:
        may.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
