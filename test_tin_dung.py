#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_tin_dung.py — Credit theo ảnh + một key một máy một lúc (13/10).

    python3 test_tin_dung.py

Ba phần:
  1. ma_anh: đổi tên / chép thư mục / đổi mtime -> CÙNG mã; khác dữ liệu -> khác
     mã; DNG lấy RawDataUniqueID.
  2. Client THẬT (tin_dung + ban_quyen) với Worker THẬT (`wrangler dev --local`,
     D1 cục bộ) — hai "máy" là hai tiến trình con, mỗi cái một AUTOTONE_DATA và
     một mã máy riêng. Không dựng máy chủ giả có logic: chính Worker sẽ chạy
     thật mới là thứ cần kiểm.
     Cần repo KeyActiveAutoTone đã `npm ci`: tìm ở $AUTOTONE_KEYSERVER, hoặc
     thư mục anh em `keyactiveautotone` / `KeyActiveAutoTone`. Không có thì
     phần này in "bỏ qua".
  3. Worker cũ (404) / mất mạng: máy chủ trả lời CỐ ĐỊNH (không logic) và cổng chết.

Key thử ký bằng bí mật THỬ ngay trong bài này (cap_key.py chỉ có trên máy người
bán) — bài này kiểm credit / phiên, không kiểm cách cấp key.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

GOC = Path(__file__).resolve().parent
_TMP = Path(tempfile.mkdtemp(prefix="test_tin_dung_"))
os.environ["AUTOTONE_DATA"] = str(_TMP / "chinh")
sys.path.insert(0, str(GOC))

BANG = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
BI_MAT_THU = "bi-mat-thu-cuc-bo-khong-phai-khoa-that"
TOKEN_THU = "token-quan-tri-thu"

dat = hong = 0


def ket(ten, ok, ghi=""):
    global dat, hong
    if ok:
        dat += 1
        print(f"  [DAT ] {ten}")
    else:
        hong += 1
        print(f"  [HONG] {ten}  {str(ghi).strip()[:400]}")


def tao_key(so_hieu: int, so_ngay: int) -> str:
    n = (1 << 36) | (so_hieu << 16) | so_ngay
    than = "".join(BANG[(n >> (i * 5)) & 31] for i in range(7, -1, -1))
    sig = hmac.new(BI_MAT_THU.encode(), than.encode(), hashlib.sha256).digest()
    s = than + "".join(BANG[sig[i] & 31] for i in range(12))
    return "-".join(s[i:i + 5] for i in range(0, 20, 5))


# ── 1. Mã ảnh ───────────────────────────────────────────────────────────────
def tiff_dng(uid: bytes | None, rac: bytes) -> bytes:
    """TIFF nhỏ nhất có (hoặc không) thẻ RawDataUniqueID, kèm `rac` làm "metadata"."""
    the = []
    if uid is not None:
        the.append((0xC65D, 1, 16, uid))
    n = len(the)
    dau = 8
    vung = dau + 2 + n * 12 + 4
    ifd = struct.pack("<H", n)
    du = b""
    for tag, typ, cnt, val in the:
        ifd += struct.pack("<HHII", tag, typ, cnt, vung + len(du))
        du += val
    ifd += struct.pack("<I", 0)
    return b"II*\x00" + struct.pack("<I", dau) + ifd + du + rac


def kiem_ma_anh():
    import tin_dung as td
    d = _TMP / "ma_anh"
    (d / "a").mkdir(parents=True)
    (d / "b").mkdir(parents=True)
    rng = os.urandom
    goc = d / "a" / "DSC00001.ARW"
    du = rng(400_000)
    goc.write_bytes(du)
    m0 = td.ma_anh(goc)
    ket("ma_anh: 32 ký tự hex", len(m0) == 32 and all(c in "0123456789abcdef" for c in m0), m0)
    chep = d / "b" / "doi_ten.arw"
    shutil.copy2(goc, chep)
    ket("chép sang thư mục khác + đổi tên: cùng mã", td.ma_anh(chep) == m0)
    os.utime(chep, (1, 1))
    ket("đổi mtime: cùng mã", td.ma_anh(chep) == m0)
    # Hai ảnh burst: đầu file y hệt (cùng EXIF), chỉ khác dữ liệu cảm biến ở giữa
    b = bytearray(du)
    b[200_000] ^= 0xFF
    (d / "b" / "burst.arw").write_bytes(bytes(b))
    ket("hai ảnh chỉ khác dữ liệu cảm biến ở giữa: khác mã",
        td.ma_anh(d / "b" / "burst.arw") != m0)
    b = bytearray(du)
    b[10] ^= 0xFF
    (d / "b" / "exif.arw").write_bytes(bytes(b))
    ket("khác EXIF ở đầu file: khác mã", td.ma_anh(d / "b" / "exif.arw") != m0)
    (d / "b" / "nho.arw").write_bytes(b"x" * 1000)
    ket("file nhỏ hơn 128 KiB vẫn có mã", len(td.ma_anh(d / "b" / "nho.arw")) == 32)
    uid = bytes(range(1, 17))
    p1 = d / "a" / "IMG.dng"
    p1.write_bytes(tiff_dng(uid, b"metadata-cu" * 50))
    p2 = d / "b" / "IMG_sau_khi_LR_ghi.dng"
    p2.write_bytes(tiff_dng(uid, b"metadata-MOI-dai-hon" * 80))
    m1 = td.ma_anh(p1)
    ket("DNG có RawDataUniqueID: mã = u + uid", m1 == "u" + uid.hex(), m1)
    ket("DNG bị Lightroom ghi lại metadata (byte đổi, cỡ đổi): vẫn cùng mã",
        td.ma_anh(p2) == m1)
    p3 = d / "b" / "khong_uid.dng"
    p3.write_bytes(tiff_dng(None, b"x" * 300))
    ket("DNG không có RawDataUniqueID: lùi về mã nội dung", len(td.ma_anh(p3)) == 32)
    ket("ma_nhieu: song song, đúng thứ tự, file hỏng -> None",
        td.ma_nhieu([goc, d / "khong_co.arw", chep]) == [m0, None, m0])


# ── 2. Worker thật ──────────────────────────────────────────────────────────
def tim_worker() -> Path | None:
    ung_vien = [os.environ.get("AUTOTONE_KEYSERVER") or "",
                str(GOC.parent / "keyactiveautotone"), str(GOC.parent / "KeyActiveAutoTone")]
    for u in ung_vien:
        if u and (Path(u) / "src" / "credit.js").exists() and (Path(u) / "node_modules").exists():
            return Path(u)
    return None


def cong_trong() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Worker:
    def __init__(self, thu_muc: Path):
        self.thu_muc = thu_muc
        self.du = Path(tempfile.mkdtemp(prefix="worker_", dir=_TMP))
        self.wr = str(thu_muc / "node_modules" / ".bin" /
                      ("wrangler.cmd" if os.name == "nt" else "wrangler"))
        self.p = None
        self.url = ""

    def bat(self):
        env = {**os.environ, "CI": "1"}
        r = subprocess.run([self.wr, "d1", "migrations", "apply", "autotone-credit", "--local",
                            "--persist-to", str(self.du)], cwd=self.thu_muc, env=env,
                           capture_output=True, text=True, shell=(os.name == "nt"))
        if r.returncode:
            raise RuntimeError("migrations: " + r.stdout[-800:] + r.stderr[-800:])
        cong = cong_trong()
        ts = [self.wr, "dev", "--local", "--port", str(cong), "--ip", "127.0.0.1",
              "--persist-to", str(self.du)]
        for b in (f"BI_MAT:{BI_MAT_THU}", f"ADMIN_TOKEN:{TOKEN_THU}",
                  "GIAY_HOAT_DONG:900", "GIAY_GHI_NHIP:0"):
            ts += ["--var", b]
        self.p = subprocess.Popen(ts, cwd=self.thu_muc, env=env, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, shell=(os.name == "nt"))
        self.url = f"http://127.0.0.1:{cong}"
        for _ in range(120):
            try:
                with urllib.request.urlopen(self.url + "/khoe", timeout=2) as r:
                    if r.status == 200:
                        return self
            except OSError:
                time.sleep(0.5)
        raise RuntimeError("wrangler dev không lên")

    def tat(self):
        if self.p:
            self.p.terminate()
            try:
                self.p.wait(10)
            except subprocess.TimeoutExpired:
                self.p.kill()

    def quan_tri(self, duong, than=None):
        req = urllib.request.Request(
            self.url + duong, data=None if than is None else json.dumps(than).encode(),
            headers={"Content-Type": "application/json", "X-Admin-Token": TOKEN_THU},
            method="GET" if than is None else "POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            return json.loads(e.read() or b"{}")


MA_CON = r'''
import os, sys, json
sys.path.insert(0, AT)
os.environ["AUTOTONE_DATA"] = DU_LIEU
import khoa, ban_quyen as bq, tin_dung as td
khoa.ma_may = lambda: MA_MAY
td.ten_may = lambda: TEN_MAY
bq.MAY_CHU = MAY_CHU
bq.CHO_MANG = 3
def ra(x):
    print("@@" + json.dumps(x, ensure_ascii=False, default=str))
THAN
'''


def may(du_lieu: Path, ma_may: str, ten: str, url: str, than: str) -> dict:
    ma = (f"AT = r{str(GOC)!r}\nDU_LIEU = r{str(du_lieu)!r}\n"
          f"MA_MAY = {ma_may!r}\nTEN_MAY = {ten!r}\nMAY_CHU = {url!r}\n"
          + MA_CON.replace("THAN", than))
    r = subprocess.run([sys.executable, "-c", ma], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    for dong in (r.stdout or "").splitlines():
        if dong.startswith("@@"):
            return json.loads(dong[2:])
    return {"loi_chay": (r.stdout or "")[-600:] + (r.stderr or "")[-1200:]}


def kiem_worker_that():
    tm = tim_worker()
    if not tm:
        print("  [bỏ qua] không thấy repo KeyActiveAutoTone đã npm ci "
              "(đặt AUTOTONE_KEYSERVER) — phần Worker thật không chạy")
        return
    w = Worker(tm).bat()
    try:
        _kiem_worker_that(w)
    finally:
        w.tat()


def _kiem_worker_that(w: Worker):
    A = (_TMP / "may_A", "AAAAAAAA0001", "MAY-A")
    B = (_TMP / "may_B", "BBBBBBBB0002", "MAY-B")
    for d, *_ in (A, B):
        d.mkdir(parents=True, exist_ok=True)
    K = tao_key(201, 365)

    def tren(m, than, url=None):
        return may(m[0], m[1], m[2], url or w.url, than)

    ids3 = ["%032x" % i for i in (1, 2, 3)]

    r = tren(A, f'''
ok, nhan = bq.kich_hoat({K!r})
v = td.vao_phien()
t1 = td.tru({ids3!r})
t2 = td.tru({ids3!r})
ra(dict(ok=ok, v=v, t1=t1, t2=t2, tom=td.tom_tat()))''')
    ket("máy A: kích hoạt + vào phiên", r.get("ok") and r["v"]["tt"] == "dung", r)
    ket("máy A: trừ 3 ảnh mới, 500.000 -> 499.997",
        r.get("t1", {}).get("moi") == 3 and r["t1"]["credit"]["con_lai"] == 499997, r)
    ket("máy A: phân tích lại 3 ảnh đó: không trừ nữa",
        r.get("t2", {}).get("moi") == 0 and r["t2"]["cu"] == 3, r)
    ket("tom_tat hiện số credit", r.get("tom") == "499.997 credit", r.get("tom"))

    r = tren(B, f'''
ok, nhan = bq.kich_hoat({K!r})
v1 = td.vao_phien()
v2 = td.vao_phien(chiem=True)
ra(dict(ok=ok, nhan=nhan, v1=v1, v2=v2))''')
    ket("máy B: cùng key kích hoạt ĐƯỢC (không còn khoá một máy)", r.get("ok"), r)
    ket("máy B vào khi A đang dùng: xung_dot, nói tên máy A",
        r.get("v1", {}).get("tt") == "xung_dot" and r["v1"].get("ten_may") == "MAY-A", r)
    ket("máy B bấm tiếp tục: dùng được", r.get("v2", {}).get("tt") == "dung", r)

    r = tren(A, f'''
# Trạm retouch: lần xác nhận cuối CÒN MỚI (< 5 phút) -> tin trạng thái đã lưu, không gọi mạng
ok_moi, _ = td.phien_ok()
# Lần xác nhận cuối đã CŨ -> phải tự hỏi máy chủ và biết mình bị đẩy ra
td._ghi_phien(luc_phien="2000-01-01T00:00:00+00:00")
ok, ly = td.phien_ok()
n = td.nhip()
t = td.tru(["%032x" % 99])
ra(dict(n=n, t=t, ok=ok, ly=ly, ok_moi=ok_moi))''')
    ket("máy A: nhịp kế tiếp biết mình bị đẩy ra, tên máy B",
        r.get("n", {}).get("tt") == "bi_day_ra" and r["n"].get("ten_may") == "MAY-B", r)
    ket("máy A bị đẩy ra: không trừ / không phân tích được", r.get("t", {}).get("tt") == "bi_day_ra", r)
    ket("trạm retouch: xác nhận còn mới thì không gọi mạng (vẫn tin trạng thái lưu)",
        r.get("ok_moi") is True, r)
    ket("trạm retouch: xác nhận đã cũ -> tự hỏi máy chủ, biết bị đẩy ra, nói tên máy B",
        r.get("ok") is False and "MAY-B" in r.get("ly", ""), r)

    r = tren(B, f'''
t = td.tru({ids3 + ["%032x" % 4]!r})
ra(dict(t=t))''')
    ket("máy B phân tích lại 3 ảnh A đã trừ + 1 ảnh mới: chỉ trừ 1",
        r.get("t", {}).get("moi") == 1 and r["t"]["cu"] == 3, r)

    # ── Mất mạng: ứng trước tối đa, có mạng lại thì trừ bù ──
    chet = f"http://127.0.0.1:{cong_trong()}"
    r = tren(B, f'''
td.UNG_TRUOC_TOI_DA = 3
t1 = td.tru(["%032x" % 1, "%032x" % 50, "%032x" % 51])
t2 = td.tru(["%032x" % 52, "%032x" % 53])
ra(dict(t1=t1, t2=t2, tom=td.tom_tat()))''', url=chet)
    ket("mất mạng: ảnh đã trừ miễn phí, 2 ảnh mới vào ứng trước",
        r.get("t1", {}).get("tt") == "ung_truoc" and r["t1"]["ung"] == 2, r)
    ket("mất mạng: vượt hạn ứng trước thì chặn (het_ung_truoc)",
        r.get("t2", {}).get("tt") == "het_ung_truoc", r)
    ket("dòng tóm tắt nói đang ứng trước", "ứng trước 2/3" in (r.get("tom") or ""), r.get("tom"))
    r = tren(B, '''
n = td.nhip()
ra(dict(n=n, ung=td.SoCai().so_ung(), tom=td.tom_tat()))''')
    ket("có mạng lại: nhịp tự trừ bù 2 ảnh ứng trước",
        r.get("ung") == 0 and r.get("n", {}).get("credit", {}).get("con_lai") == 499994, r)

    # ── Hết credit ──
    # Đã dùng 6 (A 3 + B 1 + ứng trước 2) -> đặt tổng 7 để còn đúng 1
    w.quan_tri("/credit/dat", {"key": K, "tong": 7})
    r = tren(B, f'''
t = td.tru(["%032x" % 2, "%032x" % 60, "%032x" % 61])
ra(dict(t=t))''')
    ket("hết credit: báo cần 2, còn 1, chỉ ảnh đã trừ nằm trong cu_idx",
        r.get("t", {}).get("tt") == "het_credit" and r["t"]["can"] == 2
        and r["t"]["con_lai"] == 1 and r["t"]["cu_idx"] == [0], r)

    # ── Đã đăng nhập là giữ: đóng app / tắt máy không nhả (user 13/10) ──
    #  B "đóng app" = tiến trình con của B đã kết thúc ở trên, không gọi gì thêm.
    r = tren(A, "ra(dict(v=td.vao_phien(), tt=td.trang_thai().get('tt')))")
    ket("B đã đóng app: A (máy đã bị đẩy ra) mở lại VẪN thấy hộp — key ở MAY-B",
        r.get("v", {}).get("tt") == "xung_dot" and r["v"].get("ten_may") == "MAY-B"
        and r.get("tt") == "xung_dot", r)
    r = tren(A, "ra(dict(n=td.nhip(), n2=td.nhip()))")
    ket("…chưa bấm gì thì các nhịp sau vẫn là 'key ở máy khác' (không đổi sang 'bị đẩy ra')",
        r.get("n", {}).get("tt") == "xung_dot" and r.get("n2", {}).get("tt") == "xung_dot", r)
    r = tren(B, "ra(dict(v=td.vao_phien()))")
    ket("chính B mở lại app: vào luôn", r.get("v", {}).get("tt") == "dung", r)
    r = tren(A, "ra(dict(v=td.vao_phien(chiem=True)))")
    ket("A bấm Vẫn truy cập: dùng được", r.get("v", {}).get("tt") == "dung", r)
    r = tren(B, "ra(dict(n=td.nhip()))")
    ket("…B bị đẩy ra ở nhịp kế tiếp, nghe tên MAY-A",
        r.get("n", {}).get("tt") == "bi_day_ra" and r["n"].get("ten_may") == "MAY-A", r)
    #  A đang GIỮ key (có mã phiên) rồi tắt máy; B chiếm trong lúc A tắt; A mở lại
    r = tren(B, "ra(dict(v=td.vao_phien(chiem=True)))")
    ket("A đang tắt, B bấm Vẫn truy cập: B dùng được", r.get("v", {}).get("tt") == "dung", r)
    r = tren(A, "ra(dict(v=td.vao_phien(), n=td.nhip(), n2=td.nhip()))")
    ket("A mở lại: hộp 'key đang ở MAY-B' đứng yên qua các nhịp (không đổi sang 'bị đẩy ra')",
        r.get("v", {}).get("tt") == "xung_dot" and r.get("n", {}).get("tt") == "xung_dot"
        and r.get("n2", {}).get("tt") == "xung_dot" and r["n2"].get("ten_may") == "MAY-B", r)
    r = tren(A, "ra(dict(v=td.vao_phien(chiem=True)))")
    ket("A lấy lại key (cho các mục sau)", r.get("v", {}).get("tt") == "dung", r)
    import tin_dung as _td
    ket("hàm nhả phiên khi đóng app không còn", not hasattr(_td, "roi")
        and not hasattr(_td, "roi_nhanh"))
    ket("nhịp: đang chạy việc 5 giây, rảnh 30 giây",
        _td.khoang_nhip(True) == 5 and _td.khoang_nhip(False) == 30)
    ket("trạm retouch hỏi lại máy chủ khi xác nhận cũ hơn 15 giây", _td.XAC_NHAN_TRAM == 15)

    # ── Bảng Credit & thiết bị ──
    r = tren(A, "ra(td.lay_tom_tat())")
    dm = {x["may"]: x for x in r.get("dem_may") or []}
    ket("Credit & thiết bị: đếm theo máy (A trừ 3 / B trừ 3)",
        dm.get("AAAAAAAA0001", {}).get("so_tru") == 3
        and dm.get("BBBBBBBB0002", {}).get("so_tru") == 3, r)

    # ── Gia hạn bằng key mới trên máy A: ảnh đã trừ không trừ lại ──
    K2 = tao_key(202, 365)
    r = tren(A, f'''
ok, nhan = bq.kich_hoat({K2!r})
t = td.tru(["%032x" % 1, "%032x" % 70])
ra(dict(ok=ok, t=t, cu=khoa.doc_trang_thai().get("bq_key_cu")))''')
    ket("gia hạn bằng key mới: ảnh đã trừ ở key cũ không trừ lại",
        r.get("ok") and r.get("t", {}).get("moi") == 1 and r["t"]["cu"] == 1, r)


# ── 2b. Nhịp thích ứng (luồng NhipPhien thật, hàm mạng thay bằng bộ đếm) ────
def kiem_nhip_thich_ung():
    import tin_dung as td
    goc = (td.vao_phien, td.nhip)
    dem = {"n": 0}

    def gia(*_a, **_k):
        dem["n"] += 1
        return {"tt": "dung"}
    td.vao_phien = td.nhip = gia
    try:
        ban = {"v": False}
        n = td.NhipPhien(lambda kq: None, dang_ban=lambda: ban["v"]).bat_dau()
        time.sleep(7)
        ranh = dem["n"]
        ban["v"] = True                 # vừa bấm Phân tích giữa lúc đang chờ 30 giây
        time.sleep(11.5)
        ban_n = dem["n"] - ranh
        n.dung()
    finally:
        td.vao_phien, td.nhip = goc
    ket("rảnh: 7 giây chỉ hỏi máy chủ 1 lần (lúc mở app)", ranh == 1, ranh)
    ket("đang chạy việc: hỏi 5 giây một lần, kể cả khi đang giữa lượt chờ 30 giây",
        2 <= ban_n <= 3, ban_n)


# ── 3. Worker cũ / mất mạng hẳn ─────────────────────────────────────────────
class Cu(BaseHTTPRequestHandler):
    """Worker CŨ: không có cửa credit -> 404 khong_co_cua_nay. Trả lời cố định."""
    def log_message(self, *a):
        pass

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        b = json.dumps({"ok": False, "ly_do": "khong_co_cua_nay"}).encode()
        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


def kiem_worker_cu():
    sv = HTTPServer(("127.0.0.1", 0), Cu)
    threading.Thread(target=sv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{sv.server_address[1]}"
    d = _TMP / "may_cu"
    d.mkdir(parents=True, exist_ok=True)
    r = may(d, "CCCCCCCC0003", "MAY-C", url, '''
khoa.ghi_trang_thai(bq_key="ABCDEABCDEABCDEABCDE")
t = td.tru(["%032x" % 1])
ra(dict(t=t, bat=td.bat(), v=td.vao_phien()))''')
    ket("Worker cũ (404): tru -> tat, rồi thôi gọi (chạy như trước khi có credit)",
        r.get("t", {}).get("tt") == "tat" and r.get("bat") is False
        and r.get("v", {}).get("tt") == "tat", r)
    sv.shutdown()
    r = may(d, "DDDDDDDD0004", "MAY-D", url, '''
ra(dict(bat=td.bat(), t=td.tru(["%032x" % 1])))''')
    ket("chưa có key trên máy: credit tắt", r.get("bat") is False and r["t"]["tt"] == "tat", r)
    r = may(_TMP / "may_tat", "EEEEEEEE0005", "MAY-E", url, '''
os.environ["AUTOTONE_CREDIT"] = "0"
khoa.ghi_trang_thai(bq_key="ABCDEABCDEABCDEABCDE")
ra(dict(bat=td.bat()))''')
    ket("AUTOTONE_CREDIT=0: tắt", r.get("bat") is False, r)


def main() -> int:
    for _l in (sys.stdout, sys.stderr):
        try:
            _l.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass
    try:
        for f in (kiem_ma_anh, kiem_nhip_thich_ung, kiem_worker_cu, kiem_worker_that):
            try:
                f()
            except Exception as e:                           # noqa: BLE001
                import traceback
                ket(f"{f.__name__} sập", False, traceback.format_exc()[-1500:])
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)
    print(f"\n  {dat} đạt / {hong} hỏng")
    return 1 if hong else 0


if __name__ == "__main__":
    sys.exit(main())
