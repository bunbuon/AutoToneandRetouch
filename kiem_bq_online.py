#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kiem_bq_online.py — Kiểm bản quyền có máy chủ, bằng máy chủ THẬT.

Dựng một máy chủ HTTP giả lập đúng giao thức của Worker, rồi cho ban_quyen
gọi vào đó. Không giả lập hàm _goi() — vì chính đường mạng và cách đọc lỗi
mới là chỗ dễ sai nhất.

Phép quan trọng nhất ở đây KHÔNG phải "chặn được kẻ gian", mà là "KHÔNG chặn
nhầm khách hàng thật khi họ mất mạng".

    python kiem_bq_online.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

GOC = Path(__file__).resolve().parent

# Trạng thái máy chủ giả lập — bài kiểm chỉnh để dựng từng tình huống
COI = {"ok": True, "ly_do": "", "ma": 200, "kich_hoat": None, "het_han": None,
       "so_ngay": 365, "sap": False}


class May(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        if COI["sap"]:
            #[[ Dong phut khong tra loi — giong tuong lua nuot goi tin hon la
            #   tra ve 500. Do la dang "mat mang" hay gap nhat. ]]
            self.close_connection = True
            return
        n = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(n)
        d = {"ok": COI["ok"]}
        if COI["ok"]:
            d.update(so_ngay=COI["so_ngay"], kich_hoat=COI["kich_hoat"],
                     het_han=COI["het_han"])
        else:
            d.update(ly_do=COI["ly_do"])
        b = json.dumps(d).encode()
        self.send_response(COI["ma"])
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


MA_CON = r'''
import os, sys, json
from datetime import datetime, timedelta, timezone
sys.path.insert(0, AT)
os.environ["AUTOTONE_DATA"] = DU_LIEU
import ban_quyen as bq, khoa
bq.MAY_CHU = MAY_CHU
THAN
'''


def chay(than: str, du_lieu: Path, cong: int) -> tuple[int, str]:
    ma = (f"AT = r{str(GOC)!r}\n"
          f"DU_LIEU = r{str(du_lieu)!r}\n"
          f"MAY_CHU = 'http://127.0.0.1:{cong}'\n"
          + MA_CON.replace("THAN", than))
    r = subprocess.run([sys.executable, "-c", ma], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    for _l in (sys.stdout, sys.stderr):
        try:
            _l.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass

    sv = HTTPServer(("127.0.0.1", 0), May)
    threading.Thread(target=sv.serve_forever, daemon=True).start()
    cong = sv.server_address[1]

    tmp = Path(tempfile.mkdtemp(prefix="kiem_bqon_"))
    dat = hong = 0
    n = [0]

    def moi() -> Path:
        n[0] += 1
        d = tmp / f"may{n[0]}"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def ket(ten, ok, ghi=""):
        nonlocal dat, hong
        if ok:
            dat += 1
            print(f"  [DAT ] {ten}")
        else:
            hong += 1
            print(f"  [HONG] {ten}  {str(ghi).strip()[:280]}")

    from datetime import datetime, timedelta, timezone
    bay = datetime.now(timezone.utc)
    COI.update(ok=True, ma=200, sap=False, so_ngay=365,
               kich_hoat=bay.isoformat(),
               het_han=(bay + timedelta(days=365)).isoformat())

    # 1. Kích hoạt qua máy chủ
    _, ra = chay('''
k = bq.tao_key(1, 365)
ok, nhan = bq.kich_hoat(k)
assert ok, nhan
s = bq.kiem()
assert s["co_phep"], s["ly_do"]
print("OK")
''', moi(), cong)
    ket("kích hoạt qua máy chủ được", "OK" in ra, ra)

    # 2. Máy chủ từ chối (key đã dùng máy khác) -> KHÔNG kích hoạt
    COI.update(ok=False, ma=409, ly_do="da_dung_may_khac")
    _, ra = chay('''
k = bq.tao_key(2, 365)
ok, nhan = bq.kich_hoat(k)
assert not ok, "may chu tu choi ma van kich hoat"
assert "MÁY KHÁC" in nhan or "máy khác" in nhan, nhan
assert not bq.kiem()["co_phep"]
print("OK")
''', moi(), cong)
    ket("máy chủ báo key đã dùng máy khác -> chặn", "OK" in ra, ra)

    # 3. MẤT MẠNG lúc kích hoạt -> không kích hoạt, nhưng nói rõ lý do
    COI.update(sap=True)
    _, ra = chay('''
k = bq.tao_key(3, 365)
ok, nhan = bq.kich_hoat(k)
assert not ok, "mat mang ma van kich hoat"
assert "mạng" in nhan, nhan
print("OK")
''', moi(), cong)
    ket("mất mạng lúc kích hoạt: chặn, báo rõ cần mạng", "OK" in ra, ra)

    # 4. QUAN TRỌNG NHẤT: đã kích hoạt rồi, mất mạng -> VẪN CHẠY
    COI.update(ok=True, ma=200, sap=False)
    d4 = moi()
    _, ra = chay('''
k = bq.tao_key(4, 365)
ok, nhan = bq.kich_hoat(k)
assert ok, nhan
print("OK-tao")
''', d4, cong)
    if "OK-tao" not in ra:
        ket("mất mạng sau khi kích hoạt: VẪN CHẠY", False, ra)
    else:
        COI.update(sap=True)
        _, ra = chay('''
import khoa
from datetime import datetime, timezone, timedelta
# Gia lap: lan kiem cuoi cach day 20 ngay -> toi nhip kiem, nhung chua qua an han
cu = datetime.now(timezone.utc) - timedelta(days=20)
khoa.ghi_trang_thai(bq_kiem_cuoi=cu.isoformat())
s = bq.kiem()
assert s["co_phep"], f"mat mang 20 ngay ma da bi chan: {s['ly_do']}"
print("OK")
''', d4, cong)
        ket("mất mạng 20 ngày sau kích hoạt: VẪN CHẠY (ân hạn)",
            "OK" in ra, ra)

    # 5. Quá ân hạn 30 ngày -> mới chặn
    COI.update(sap=True)
    d5 = moi()
    COI.update(sap=False)
    _, ra = chay('''
k = bq.tao_key(5, 365)
assert bq.kich_hoat(k)[0]
print("OK-tao")
''', d5, cong)
    COI.update(sap=True)
    _, ra = chay('''
import khoa
from datetime import datetime, timezone, timedelta
cu = datetime.now(timezone.utc) - timedelta(days=40)
khoa.ghi_trang_thai(bq_kiem_cuoi=cu.isoformat())
s = bq.kiem()
assert not s["co_phep"], "qua an han 40 ngay ma van chay"
assert "máy chủ" in s["ly_do"], s["ly_do"]
print("OK")
''', d5, cong)
    ket("quá ân hạn 30 ngày mới chặn", "OK" in ra, ra)

    # 6. Sắp hết ân hạn -> nhắc trước, chưa chặn
    COI.update(sap=False)
    d6 = moi()
    _, ra = chay('''
k = bq.tao_key(6, 365)
assert bq.kich_hoat(k)[0]
print("OK-tao")
''', d6, cong)
    COI.update(sap=True)
    _, ra = chay('''
import khoa
from datetime import datetime, timezone, timedelta
cu = datetime.now(timezone.utc) - timedelta(days=25)
khoa.ghi_trang_thai(bq_kiem_cuoi=cu.isoformat())
s = bq.kiem()
assert s["co_phep"], "chua qua an han ma da chan"
assert s["nhac"], "khong nhac truoc khi het an han"
print("OK:", s["nhac"][:60])
''', d6, cong)
    ket("sắp hết ân hạn: nhắc trước, chưa chặn", "OK:" in ra, ra)

    # 7. Máy chủ THU HỒI key -> dừng NGAY, không đợi ân hạn
    COI.update(sap=False)
    d7 = moi()
    _, ra = chay('''
k = bq.tao_key(7, 365)
assert bq.kich_hoat(k)[0]
print("OK-tao")
''', d7, cong)
    COI.update(ok=False, ma=403, ly_do="da_thu_hoi")
    _, ra = chay('''
import khoa
from datetime import datetime, timezone, timedelta
cu = datetime.now(timezone.utc) - timedelta(days=8)
khoa.ghi_trang_thai(bq_kiem_cuoi=cu.isoformat())
s = bq.kiem()
assert not s["co_phep"], "key da thu hoi ma van chay"
assert "thu hồi" in s["ly_do"], s["ly_do"]
print("OK")
''', d7, cong)
    ket("key bị thu hồi: dừng ngay, không đợi ân hạn", "OK" in ra, ra)

    # 8. Chưa tới nhịp kiểm thì KHÔNG gọi máy chủ (đỡ tốn, đỡ phụ thuộc)
    COI.update(ok=True, ma=200, sap=False)
    d8 = moi()
    _, ra = chay('''
k = bq.tao_key(8, 365)
assert bq.kich_hoat(k)[0]
print("OK-tao")
''', d8, cong)
    COI.update(sap=True)     # máy chủ chết, nhưng chưa tới nhịp nên không sao
    _, ra = chay('''
s = bq.kiem()
assert s["co_phep"], f"chua toi nhip kiem ma da chan: {s['ly_do']}"
print("OK")
''', d8, cong)
    ket("chưa tới nhịp 7 ngày: không gọi máy chủ, chạy bình thường",
        "OK" in ra, ra)

    sv.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n  {dat} đạt / {hong} hỏng")
    return 1 if hong else 0


if __name__ == "__main__":
    sys.exit(main())
