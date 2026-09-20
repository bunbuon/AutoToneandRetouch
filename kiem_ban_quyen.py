#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kiem_ban_quyen.py — Kiểm cơ chế key bản quyền.

Mỗi phép kiểm ở đây tương ứng một cách mất tiền hoặc một cách chặn nhầm khách
hàng thật. Chạy trên thư mục tạm nên không đụng giấy phép của máy đang dùng.

    python kiem_ban_quyen.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

GOC = Path(__file__).resolve().parent

#[[ Chay moi phep trong TIEN TRINH CON, moi tien trinh mot thu muc du lieu.
#
#   khoa.py cache ma may trong bien module, va doc_trang_thai() doc mot file
#   duy nhat. Chay het trong mot tien trinh thi cac phep an nhau: phep truoc
#   ghi giay phep, phep sau tuong minh dang o may sach.
#]]
MA = r'''
import os, sys
sys.path.insert(0, r"{goc}")
os.environ["AUTOTONE_DATA"] = r"{du_lieu}"
import ban_quyen as bq

#[[ TAT DUONG MANG cho cac phep OFFLINE.
#
#   Tu khi kich_hoat() bat buoc qua may chu, cac phep o day khong kich hoat
#   duoc nua — chung kiem phan LOGIC CUC BO (ma hoa key, chong van dong ho,
#   chong sua file), khong kiem duong mang.
#
#   Nen thay _goi() bang mot ban gia lap luon dong y. Phan mang that duoc
#   kiem rieng trong kiem_bq_online.py bang may chu HTTP that — de hai bai
#   khong dam chan nhau.
#]]
from datetime import datetime, timedelta, timezone


def _goi_gia(duong, than):
    bay = datetime.now(timezone.utc)
    d = bq.doc_key(than.get("key", ""))
    ngay = d[1] if d else 365
    return 200, {{"ok": True, "so_ngay": ngay,
                  "kich_hoat": bay.isoformat(),
                  "het_han": (bay + timedelta(days=ngay)).isoformat()}}


bq._goi = _goi_gia
{than}
'''


def chay(than: str, du_lieu: Path) -> tuple[int, str]:
    ma = MA.format(goc=GOC, du_lieu=du_lieu, than=than)
    r = subprocess.run([sys.executable, "-c", ma], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    for _l in (sys.stdout, sys.stderr):
        try:
            _l.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass

    tmp = Path(tempfile.mkdtemp(prefix="kiem_bq_"))
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
            print(f"  [HONG] {ten}  {ghi.strip()[:300]}")

    # 1. Sinh rồi đọc lại — mọi gói bán
    ma, ra = chay('''
import ban_quyen as bq
for ten, ngay in bq.GOI_BAN.items():
    k = bq.tao_key(7, ngay)
    d = bq.doc_key(k)
    assert d == (7, ngay), (ten, k, d)
print("OK")
''', moi())
    ket("sinh rồi đọc lại đúng, mọi gói bán", "OK" in ra, ra)

    # 2. Key bịa / sai một ký tự phải bị từ chối
    ma, ra = chay('''
k = bq.tao_key(5, 30)
assert bq.doc_key(k) is not None
s = list(bq.sach(k))
s[0] = "B" if s[0] != "B" else "C"
assert bq.doc_key("".join(s)) is None, "sua 1 ky tu ma van qua"
assert bq.doc_key("AAAAA-AAAAA-AAAAA-AAAAA") is None, "key bia van qua"
assert bq.doc_key("") is None and bq.doc_key("xxx") is None
print("OK")
''', moi())
    ket("key bịa / sai 1 ký tự bị từ chối", "OK" in ra, ra)

    # 3. Ký tự dễ đọc nhầm: gõ 0 thay O, 1 thay I vẫn phải nhận
    ma, ra = chay('''
k = bq.tao_key(11, 365)
s = bq.sach(k)
assert bq.doc_key(s.replace("9", "O").replace("8", "1")) == (11, 365)
assert bq.doc_key(k.lower()) == (11, 365), "chu thuong phai nhan"
assert bq.doc_key(" " + k + " ") == (11, 365), "khoang trang phai bo qua"
print("OK")
''', moi())
    ket("gõ nhầm 0/O, 1/I, chữ thường vẫn nhận", "OK" in ra, ra)

    # 4. Kích hoạt: máy sạch -> có phép, hạn đếm từ LÚC KÍCH HOẠT
    ma, ra = chay('''
from datetime import datetime, timezone, timedelta
assert bq.kiem()["co_phep"] is False, "may sach ma da co phep"
k = bq.tao_key(21, 30)
ok, nhan = bq.kich_hoat(k)
assert ok, nhan
s = bq.kiem()
assert s["co_phep"], s["ly_do"]
con = (s["het_han"] - datetime.now(timezone.utc)).total_seconds()
assert 29.9 * 86400 < con < 30.1 * 86400, f"han lech: {con/86400:.2f} ngay"
print("OK")
''', moi())
    ket("kích hoạt xong có phép, hạn đúng 30 ngày từ lúc kích hoạt",
        "OK" in ra, ra)

    # 5. Nhập lại chính key đó KHÔNG được đặt lại mốc (nếu không = gia hạn vô hạn)
    ma, ra = chay('''
import json, khoa
k = bq.tao_key(22, 30)
bq.kich_hoat(k)
d1 = khoa.doc_trang_thai()["bq_kich_hoat"]
ok, nhan = bq.kich_hoat(k)
d2 = khoa.doc_trang_thai()["bq_kich_hoat"]
assert ok, nhan
assert d1 == d2, f"moc bi dat lai: {d1} -> {d2}"
print("OK")
''', moi())
    ket("nhập lại cùng key không đặt lại mốc (chặn gia hạn vô hạn)",
        "OK" in ra, ra)

    # 6. Hết hạn -> mất phép, lý do nói rõ
    ma, ra = chay('''
from datetime import datetime, timezone, timedelta
import khoa
k = bq.tao_key(23, 30)
bq.kich_hoat(k)
#[[ Lui CA HAI moc: bq_kich_hoat va bq_het_han.
#
#   Tu khi co may chu, _het_han() uu tien `bq_het_han` (han may chu da chot)
#   chu khong tinh lai tu ngay kich hoat. Chi lui mot cai thi han cu van con,
#   va bai kiem bao "het han ma van co phep" — loi cua BAI KIEM, khong phai
#   cua san pham.
#]]
cu = datetime.now(timezone.utc) - timedelta(days=40)
het_cu = cu + timedelta(days=30)
khoa.ghi_trang_thai(bq_kich_hoat=cu.isoformat(), moc_cao=cu.isoformat(),
                    bq_het_han=het_cu.isoformat())
s = bq.kiem()
assert s["co_phep"] is False, "het han ma van co phep"
assert "hết hạn" in s["ly_do"], s["ly_do"]
print("OK")
''', moi())
    ket("hết hạn thì mất phép, báo đúng lý do", "OK" in ra, ra)

    # 7. Vặn đồng hồ lùi -> chặn
    ma, ra = chay('''
from datetime import datetime, timezone, timedelta
import khoa
k = bq.tao_key(24, 365)
bq.kich_hoat(k)
assert bq.kiem()["co_phep"]
# Gia lap: lan truoc dung o tuong lai (tuc bay gio dong ho dang lui)
tuong_lai = datetime.now(timezone.utc) + timedelta(days=3)
khoa.ghi_trang_thai(moc_cao=tuong_lai.isoformat())
s = bq.kiem()
assert s["co_phep"] is False, "van dong ho lui ma van chay"
assert "lùi" in s["ly_do"], s["ly_do"]
print("OK")
''', moi())
    ket("vặn đồng hồ lùi bị chặn", "OK" in ra, ra)

    # 8. Sửa file giấy phép bằng tay -> chữ ký sai -> mất phép
    ma, ra = chay('''
import json, khoa
k = bq.tao_key(25, 30)
bq.kich_hoat(k)
p = khoa._file()
d = json.loads(p.read_text(encoding="utf-8"))
d["bq_ngay"] = 36500          # tu nang thanh vinh vien
p.write_text(json.dumps(d), encoding="utf-8")
s = bq.kiem()
assert s["co_phep"] is False, "sua tay ma van chay"
assert "sửa" in s["ly_do"] or "khớp" in s["ly_do"], s["ly_do"]
print("OK")
''', moi())
    ket("sửa file giấy phép bằng tay bị bắt", "OK" in ra, ra)

    # 9. Chép giấy phép sang MÁY KHÁC -> không dùng được
    #[[ Gia lap may khac bang cach ep khoa.ma_may() tra ma khac, roi doc lai
    #   dung file giay phep do — dung y het viec bung o C sang may moi. ]]
    d9 = moi()
    ma, ra = chay('''
k = bq.tao_key(26, 365)
bq.kich_hoat(k)
assert bq.kiem()["co_phep"]
print("OK-tao")
''', d9)
    if "OK-tao" not in ra:
        ket("chép giấy phép sang máy khác bị chặn", False, ra)
    else:
        ma, ra = chay('''
import khoa
khoa.ma_may = lambda: "MAYKHAC00001"
khoa._ma_may_cache = None
s = bq.kiem()
assert s["co_phep"] is False, "chep sang may khac ma van chay"
print("OK")
''', d9)
        ket("chép giấy phép sang máy khác bị chặn", "OK" in ra, ra)

    # 10. Key vĩnh viễn phải sống rất lâu, không tràn số
    ma, ra = chay('''
from datetime import datetime, timezone
k = bq.tao_key(27, bq.GOI_BAN["vinh-vien"])
ok, nhan = bq.kich_hoat(k)
assert ok, nhan
s = bq.kiem()
assert s["co_phep"], s["ly_do"]
nam = (s["het_han"] - datetime.now(timezone.utc)).days / 365
assert nam > 99, f"chi con {nam:.0f} nam"
print("OK")
''', moi())
    ket("key vĩnh viễn sống > 99 năm, không tràn số", "OK" in ra, ra)

    # 11. Giới hạn đầu vào khi sinh key
    ma, ra = chay('''
for hieu, ngay in ((0, 30), (2**20, 30), (5, 0), (5, 2**16)):
    try:
        bq.tao_key(hieu, ngay)
    except ValueError:
        continue
    raise AssertionError(f"nhan tham so sai: {hieu}, {ngay}")
print("OK")
''', moi())
    ket("từ chối tham số ngoài khoảng khi sinh key", "OK" in ra, ra)

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n  {dat} đạt / {hong} hỏng")
    return 1 if hong else 0


if __name__ == "__main__":
    sys.exit(main())
