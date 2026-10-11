# -*- coding: utf-8 -*-
"""Kiểm trạm retouch cho "Retouch khi xuất" của Lightroom (tram_retouch.py, 10/10).

Engine giả (không cần tool / card): rt.chay giả ghi ảnh ra thư mục ra kèm dấu bộ mức.
    python test_tram_retouch.py
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

TAM = Path(tempfile.mkdtemp(prefix="kiem_tram_"))
os.environ["AUTOTONE_DATA"] = str(TAM / "data")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import retouch as rt  # noqa: E402
import retouch_preset as rp  # noqa: E402
import tram_retouch as tr  # noqa: E402

LOI = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


# ---------------------------------------------------------------- engine giả
class MayGia:
    def __init__(self, *_a):
        self.con = True
        self.co_chay = True
        self.tin_san_sang = {"loai": "san_sang", "may": "cuda", "ban": "x"}
        self.dang_chay = False
        self.proc = None
        self.dong_lan = 0

    def song(self):
        return self.con

    def chay_duoc(self, cho=60.0):
        return self.con

    def dong(self):
        self.con = False
        self.dong_lan += 1


class GiuGia(tr.GiuMay):
    def __init__(self):
        super().__init__()
        self.lan_mo = 0

    def lay(self, rt_, goc, may="auto", dung=True):
        with self._khoa:
            if self.may is None or not self.may.song():
                self.may, self.goc = MayGia(), str(goc)
                self.lan_mo += 1
                moi = True
            else:
                moi = False
            if dung:
                self.so_dung += 1
            return self.may, "", moi


GOI = []
GOI_SO = []
HANH_DONG_GIUA = []


def chay_gia(goc, vao, ra, muc, engine=None, **kw):
    GOI.append({"vao": str(vao), "muc": dict(muc), "anh": sorted(p.name for p in Path(vao).iterdir()),
                "kw": dict(kw), "engine": engine is not None})
    GOI_SO.append(len(list(Path(vao).iterdir())))
    yield ("lenh", "gia")
    for h in list(HANH_DONG_GIUA):
        h()
    for p in Path(vao).iterdir():
        if p.name.startswith("KHONG_RA"):
            continue
        (Path(ra) / p.name).write_bytes(b"RT:" + json.dumps(muc, sort_keys=True).encode() + b"|" + p.read_bytes())
    yield ("dong", "  xong")
    yield ("ma", 0)


rt.chay = chay_gia
rt.hop_le = lambda goc: True


def tram_moi(loai="app", **kw):
    kw.setdefault("khoa_ok", lambda: True)          # dữ liệu tạm không có bản quyền thật
    return tr.Tram(THU, loai, rt=rt, giu=kw.pop("giu", None) or GiuGia(), goc_tool="C:/tool", **kw)


THU = TAM / "jobs" / "tram_retouch"
THU.mkdir(parents=True)
RAW = TAM / "G" / "Buoi"
RAW.mkdir(parents=True)
RENDER = TAM / "LR_render"
RENDER.mkdir()


def anh(ten, noi=b"JPEG"):
    p = RENDER / ten
    p.write_bytes(noi)
    (RAW / (Path(ten).stem + ".ARW")).write_bytes(b"raw")
    return p


def yc(id_, anh_p, goc="", che_do="app"):
    tr.ghi_kv(THU / f"yc_{id_}.txt", {"anh": anh_p, "goc": goc, "che_do": che_do, "t": int(time.time())})


def kq(id_):
    return tr.doc_kv(THU / f"kq_{id_}.txt") or {}


# ---------------------------------------------------------------- 1. tra mức
vao = str(RAW)
rt.ghi_muc_anh(vao, {"DSC0002.ARW": {"vet": 80, "min_da": 10}}, {"vet": 40, "nam:vet": 20})
m, mt = tr.muc_cho(rt, "app", str(RAW / "DSC0001.ARW"))
ktra("mức buổi (mức chung của thư mục RAW, kể cả mức theo nhóm)", m == {"vet": 40, "nam:vet": 20}
     and "buổi" in mt, f"{m} · {mt}")
m, mt = tr.muc_cho(rt, "app", str(RAW / "DSC0002.ARW"))
ktra("mức riêng của ảnh đè mức chung (bỏ mức nhóm của chung)", m == {"vet": 80, "min_da": 10}
     and "riêng" in mt, f"{m} · {mt}")
rp.ghi("Cưới mịn", {"vet": 100, "min_da": 60})
m, mt = tr.muc_cho(rt, "preset:Cưới mịn", str(RAW / "DSC0002.ARW"))
ktra("chế độ preset: đúng preset cho mọi ảnh (bỏ mức riêng)", m == {"vet": 100, "min_da": 60}
     and "Cưới mịn" in mt, f"{m} · {mt}")
m, mt = tr.muc_cho(rt, "app", str(TAM / "Khac" / "X.ARW"))
ktra("buổi chưa đặt mức + chưa có mức gần nhất -> None", m is None, mt)
tr.ghi_gan_nhat({"vet": 55}, "Cưới mịn", "D:/x")
m, mt = tr.muc_cho(rt, "app", str(TAM / "Khac" / "X.ARW"))
ktra("buổi chưa đặt mức -> mức gần nhất người dùng đặt trong app", m == {"vet": 55}
     and "gần nhất" in mt, f"{m} · {mt}")

# ---------------------------------------------------------------- 2. làm + ghi đè tại chỗ
a1, a2, a3 = anh("DSC0001.jpg", b"A1"), anh("DSC0002.jpg", b"A2"), anh("DSC0003.jpg", b"A3")
yc("1", a1, str(RAW / "DSC0001.ARW"))
yc("2", a2, str(RAW / "DSC0002.ARW"))
yc("3", a3, str(RAW / "DSC0003.ARW"))
t = tram_moi()
GOI.clear()
n = t.mot_vong()
ktra("trạm nhận đủ 3 yêu cầu, gom theo mức -> 2 mẻ engine (mức buổi / mức riêng)",
     n == 3 and len(GOI) == 2 and sorted(len(g["anh"]) for g in GOI) == [1, 2], str([g["anh"] for g in GOI]))
ktra("ảnh ĐÈ TẠI CHỖ đúng file Lightroom render, đúng bộ mức",
     a1.read_bytes().startswith(b'RT:{"nam:vet": 20, "vet": 40}|A1')
     and a2.read_bytes().startswith(b'RT:{"min_da": 10, "vet": 80}|A2'), a1.read_bytes()[:40])
ktra("kết quả ok + mô tả mức, file dang_ / thư mục tạm đã dọn",
     kq("1").get("ok") == "1" and "buổi" in kq("1").get("mo_ta", "")
     and not list(THU.glob("dang_*")) and not list(RENDER.glob(".autotone_tram_*")), str(kq("1")))
ktra("mẻ chạy bằng engine thường trú, chất lượng JPEG 'auto' (theo ảnh Lightroom)",
     all(g["engine"] and g["kw"].get("chat_luong") == "auto" and g["kw"].get("lam_lai") for g in GOI))
ktra("nhịp trạm app: san_sang=1, máy cuda; presets.txt có preset",
     tr.doc_nhip(THU, "app").get("san_sang") == "1" and tr.doc_nhip(THU, "app").get("may") == "cuda"
     and "Cưới mịn" in (THU / "presets.txt").read_text(encoding="utf-8"))

# ---------------------------------------------------------------- 3. các đường không retouch
rt.ghi_muc_anh(str(RAW), {}, {})                     # buổi: mọi mức 0
(TAM / "data" / tr.GAN_NHAT).unlink()
a4 = anh("DSC0004.jpg", b"A4")
yc("4", a4, str(RAW / "DSC0004.ARW"))
d5 = RENDER / "DSC0005.dng"
d5.write_bytes(b"D5")
yc("5", d5, str(RAW / "DSC0005.ARW"))
yc("6", RENDER / "khong_co.jpg", "")
GOI.clear()
t.mot_vong()
ktra("buổi chưa có mức (0 hết / chưa đặt) -> bỏ qua, ảnh giữ nguyên, không gọi engine",
     kq("4").get("ok") == "1" and kq("4").get("bo_qua") == "1" and a4.read_bytes() == b"A4"
     and not GOI, str(kq("4")))
ktra("định dạng không retouch (DNG) -> bỏ qua", kq("5").get("bo_qua") == "1" and d5.read_bytes() == b"D5")
ktra("file render không còn -> báo lỗi (plugin cho ảnh ra chưa retouch)", kq("6").get("ok") == "0"
     and "không thấy" in kq("6").get("loi", ""))

# ---------------------------------------------------------------- 4. huỷ / quá giờ
rt.ghi_muc_anh(str(RAW), {}, {"vet": 30})
a7 = anh("DSC0007.jpg", b"A7")
yc("7", a7, str(RAW / "DSC0007.ARW"))
(THU / "huy_7.txt").write_text("1", encoding="utf-8")
t.mot_vong()
ktra("plugin đã huỷ trước khi trạm làm -> không đè", a7.read_bytes() == b"A7" and kq("7").get("ok") == "0")
a8 = anh("DSC0008.jpg", b"A8")
yc("8", a8, str(RAW / "DSC0008.ARW"))
HANH_DONG_GIUA.append(lambda: (THU / "huy_8.txt").write_text("1", encoding="utf-8"))
t.mot_vong()
HANH_DONG_GIUA.clear()
ktra("plugin huỷ GIỮA lúc engine đang làm -> không đè file (Lightroom có thể đã chuyển đi)",
     a8.read_bytes() == b"A8" and kq("8").get("ok") == "0" and "huỷ" in kq("8").get("loi", ""))
a9 = anh("KHONG_RA9.jpg", b"A9")
yc("9", a9, str(RAW / "KHONG_RA9.ARW"))
t.mot_vong()
ktra("tool không ra ảnh -> lỗi, ảnh giữ nguyên", a9.read_bytes() == b"A9" and kq("9").get("ok") == "0"
     and "không ra ảnh" in kq("9").get("loi", ""), kq("9").get("loi", ""))
cu = THU / "yc_cu.txt"
tr.ghi_kv(cu, {"anh": str(a9)})
os.utime(cu, (time.time() - 3600, time.time() - 3600))
t.mot_vong()
ktra("yêu cầu nằm quá 15 phút (plugin đã bỏ) -> dọn, không làm", not cu.exists() and not kq("cu"))

# ---------------------------------------------------------------- 5. hai trạm không giành nhau
for i in range(10, 16):
    yc(str(i), anh(f"DSC00{i}.jpg", b"X"), str(RAW / f"DSC00{i}.ARW"))
t2 = tram_moi("rieng")
n1, n2 = t.nhan(), t2.nhan()
id1, id2 = {y["id"] for y in n1}, {y["id"] for y in n2}
ktra("hai trạm cùng giành: mỗi ảnh đúng MỘT trạm nhận", len(id1 | id2) == 6 and not (id1 & id2),
     f"{len(id1)} + {len(id2)}")
for y in n1 + n2:
    t.tra_loi(y, ok=False, loi="dọn")

# ---------------------------------------------------------------- 6. ai phục vụ
for f in THU.glob("tram_*.txt"):
    f.unlink()
giu_app = GiuGia()
ta = tram_moi("app", giu=giu_app)
tr.ghi_kv(THU / "tram_rieng.txt", {"pid": 1, "san_sang": 1, "t": int(time.time())})
ktra("app CHƯA nạp engine mà trạm ngầm đang chạy -> app nhường", not ta.duoc_nhan())
giu_app.lay(rt, "C:/tool", dung=False)
ktra("app đã có engine -> app nhận việc", ta.duoc_nhan())
tr.ghi_kv(THU / "tram_app.txt", {"pid": 2, "san_sang": 1, "t": int(time.time())})
ktra("trạm ngầm thấy engine app sẵn sàng -> nhường (không nạp mô hình thứ hai)",
     not tram_moi("rieng").duoc_nhan())
tr.ghi_kv(THU / "tram_app.txt", {"pid": 2, "san_sang": 1, "t": int(time.time()) - 60})
ktra("nhịp app cũ (app tắt) -> trạm ngầm nhận việc", tram_moi("rieng").duoc_nhan())

# ---------------------------------------------------------------- 7. xin nạp (hộp Export mở)
for f in THU.glob("tram_*.txt"):
    f.unlink()
giu2 = GiuGia()
t3 = tram_moi("app", giu=giu2)
(THU / tr.XIN_NAP).write_text("1", encoding="utf-8")
t3.mot_vong()
het = time.time() + 3
while time.time() < het and giu2.lan_mo == 0:
    time.sleep(0.05)
ktra("hộp Export mở (xin_nap) -> app nạp engine ngay + giữ 30 phút",
     giu2.lan_mo == 1 and giu2.giu_toi > time.time() + 25 * 60 and not (THU / tr.XIN_NAP).exists())

# ---------------------------------------------------------------- 8. chặn
a20 = anh("DSC0020.jpg", b"B")
yc("20", a20, str(RAW / "DSC0020.ARW"))
tram_moi(khoa_ok=lambda: False).mot_vong()
ktra("hết hạn bản quyền -> không retouch, nói lý do", a20.read_bytes() == b"B"
     and "bản quyền" in kq("20").get("loi", ""))
yc("21", a20, str(RAW / "DSC0020.ARW"))
tram_moi(chan=lambda: "đang tải bản tăng tốc GPU").mot_vong()
ktra("app đang tải GPU -> không retouch, nói lý do", "tải bản tăng tốc" in kq("21").get("loi", ""))

# ---------------------------------------------------------------- 9. giữ engine chung
g = tr.GiuMay()
m1 = MayGia()
g.may, g.goc, g.so_dung = m1, "C:/tool", 1
ktra("tha: còn người dùng khác? không — chưa giữ -> đóng thật", g.tha(m1) and m1.dong_lan == 1)
m2 = MayGia()
g.may, g.goc, g.so_dung = m2, "C:/tool", 1
g.giu(60)
ktra("đang được giữ (vừa đổi mức / vừa xuất) -> rời màn Retouch KHÔNG đóng engine",
     not g.tha(m2) and m2.song())
ktra("app đóng (ép) -> đóng dù đang giữ", g.don(ep=True) and not m2.song())
m3 = MayGia()
g.may, g.goc, g.so_dung, g.giu_toi = m3, "C:/tool", 0, 0
m3.dang_chay = True
ktra("đang chạy mẻ -> không đóng", not g.don())

# ---------------------------------------------------------------- 11. (11/10) render vào thư mục tạm
#  user thử thật: ảnh chưa retouch hiện trong thư mục xuất rồi mới bị đè -> nay Lightroom
#  render vào <đích>/.autotone_dang_retouch, trạm GIỮ bản retouch, giao khi có san_.
for f in THU.glob("*.txt"):
    f.unlink()
rt.ghi_muc_anh(str(RAW), {}, {"vet": 30})
XUAT = TAM / "Xuat"
TAMX = XUAT / ".autotone_dang_retouch"
TAMX.mkdir(parents=True)


def cho(id_, ten, noi=b"R\xff\xd9", goc=None):
    tam = TAMX / ten
    tam.write_bytes(noi)
    tr.ghi_kv(THU / f"cho_{id_}.txt", {"anh": tam, "dich": XUAT / ten,
                                       "goc": goc or RAW / (Path(ten).stem + ".ARW"), "che_do": "app",
                                       "het": 1})
    return tam, XUAT / ten


tc = tram_moi()
tam1, dich1 = cho("c1", "DSC0101.jpg")
GOI.clear()
tc.mot_vong()                                    # vừa thấy file: chưa đứng yên đủ
ktra("file render vừa xuất hiện (chưa đứng yên ON_DINH_GIAY) -> chưa nhận", not GOI)
time.sleep(tr.ON_DINH_GIAY + 0.1)
tc.mot_vong()
ktra("file ghi trọn (JPEG có FFD9, đứng yên) -> retouch SỚM, GIỮ bản retouch, đích CHƯA có file",
     len(GOI) == 1 and not dich1.exists() and "c1" in tc._cho_giao and not kq("c1"))
(THU / "san_c1.txt").write_text("1", encoding="utf-8")
tc.mot_vong()
ktra("plugin báo san_ (Lightroom xong với file) -> giao: đích là bản retouch, file tạm đã xoá",
     dich1.read_bytes().startswith(b"RT:") and not tam1.exists() and kq("c1").get("ok") == "1"
     and not (THU / "san_c1.txt").exists() and not list(TAMX.glob(".kq_*")), str(kq("c1")))
tam2, dich2 = cho("c2", "DSC0102.jpg", noi=b"R2 dang ghi")   # JPEG chưa có FFD9
time.sleep(tr.ON_DINH_GIAY + 0.1)
GOI.clear()
tc.mot_vong()
tc.mot_vong()
ktra("JPEG chưa có FFD9 (Lightroom đang ghi) -> không nhận dù đứng yên", not GOI)
(THU / "san_c2.txt").write_text("1", encoding="utf-8")
tc.mot_vong()
ktra("có san_ (Lightroom đã xong) -> nhận ngay và giao", dich2.read_bytes().startswith(b"RT:"))
tam3, dich3 = cho("c3", "DSC0103.jpg")
time.sleep(tr.ON_DINH_GIAY + 0.1)
tc.mot_vong()
tc.mot_vong()
(THU / "huy_c3.txt").write_text("1", encoding="utf-8")
tc.mot_vong()
ktra("plugin huỷ (quá giờ / bấm ✕) -> không giao, bỏ bản giữ (plugin tự chuyển bản gốc)",
     not dich3.exists() and "c3" not in tc._cho_giao and not list(TAMX.glob(".kq_*")))
rt.ghi_muc_anh(str(RAW), {}, {})
tam4, dich4 = cho("c4", "DSC0104.jpg", noi=b"R4\xff\xd9")
(THU / "san_c4.txt").write_text("1", encoding="utf-8")
tc.mot_vong()
ktra("mức 0 -> giao NGUYÊN bản Lightroom sang đích (bỏ qua)", dich4.read_bytes() == b"R4\xff\xd9"
     and kq("c4").get("bo_qua") == "1" and not tam4.exists())
rt.ghi_muc_anh(str(RAW), {}, {"vet": 30})
tam5, dich5 = cho("c5", "KHONG_RA105.jpg", noi=b"R5\xff\xd9")
(THU / "san_c5.txt").write_text("1", encoding="utf-8")
tc.mot_vong()
ktra("tool không ra ảnh -> vẫn giao bản Lightroom sang đích, báo lỗi",
     dich5.read_bytes() == b"R5\xff\xd9" and kq("c5").get("ok") == "0")
GOI.clear()
GOI_SO.clear()
for i in range(10):
    t_, _d = cho(f"l{i}", f"DSC02{i:02d}.jpg")
tc.mot_vong()                                    # lần đầu thấy file
time.sleep(tr.ON_DINH_GIAY + 0.1)
tc.mot_vong()                                    # đứng yên đủ -> nhận tối đa 2 lô
time.sleep(tr.ON_DINH_GIAY + 0.1)
tc.mot_vong()
ktra("nhiều ảnh render trước -> mẻ engine tối đa LO_TOI_DA ảnh, làm hết",
     GOI_SO and max(GOI_SO) == tr.LO_TOI_DA and sum(GOI_SO) == 10, str(GOI_SO))
for i in range(10):
    (THU / f"huy_l{i}.txt").write_text("1", encoding="utf-8")
tc.mot_vong()
for f in list(THU.glob("*.txt")) + list(TAMX.glob("*")):
    f.unlink()

# ---------------------------------------------------------------- 12. nhịp ở luồng riêng
th = tram_moi("app")
th.giu.lay(rt, "C:/tool", dung=False)
th.bat_nen()
cham = []


def chay_cham(goc, vao, ra, muc, engine=None, **kw):
    cham.append(1)
    yield ("lenh", "cham")
    time.sleep(3.0)
    yield ("ma", 0)


rt.chay = chay_cham
a30 = anh("DSC0030.jpg", b"C")
yc("30", a30, str(RAW / "DSC0030.ARW"))
time.sleep(2.5)
n = tr.doc_nhip(THU, "app", cu=1.5)
ktra("trạm đang làm mẻ dài vẫn báo nhịp mới (plugin không tưởng chết, không mở engine thứ hai)",
     cham and n is not None and n.get("dang") == "1", str(n))
th.dung()
time.sleep(1.5)
rt.chay = chay_gia
for f in THU.glob("*.txt"):
    f.unlink()

# ---------------------------------------------------------------- 13. hâm nóng
tn = tram_moi()
nong = []
tn.ham_nong_goc = tn.ham_nong


def chay_nong(goc, vao, ra, muc, engine=None, **kw):
    nong.append((sorted(p.name for p in Path(vao).iterdir()), dict(muc)))
    yield ("ma", 0)


rt.chay = chay_nong
tr.ghi_kv(THU / tr.XIN_NAP, {"che_do": "preset:Cưới mịn"})
tn.mot_vong()
ktra("hộp Export mở (xin_nap che_do=preset) -> hâm nóng bằng ảnh mẫu với đúng mức preset",
     len(nong) == 1 and nong[0][0] == ["nong.jpg"] and nong[0][1] == {"vet": 100.0, "min_da": 60.0},
     str(nong))
tr.ghi_kv(THU / tr.XIN_NAP, {"che_do": "preset:Cưới mịn"})
tn.mot_vong()
ktra("các bước đã hâm trên engine này -> không hâm lại", len(nong) == 1)
tr.ghi_gan_nhat({"vet": 50, "chan": 40}, "", "")
tn.mot_vong()                     # thấy đổi
time.sleep(tr.NONG_SAU_GIAY + 0.2)
tn.mot_vong()                     # ngừng tay đủ lâu -> đặt chờ
tn.mot_vong()                     # hâm
ktra("đổi mức trong app (thêm bước mới) -> ngừng tay 2 s thì hâm bước mới",
     len(nong) == 2 and nong[1][1] == {"vet": 50, "chan": 40}, str(nong[1:]))
ktra("nhịp báo nong=1 khi đã hâm xong", tr.doc_nhip(THU, "app").get("nong") == "1")
rt.chay = chay_gia

# ---------------------------------------------------------------- 14. trạm ngầm thoát (11/10)
#  user: Setup báo "unable to automatically close all applications" dù đã đóng app — còn
#  AutoTone --say-tram (không cửa sổ). Nay: trình cài ghi dung_tram.txt; Lightroom tắt -> thoát.
import threading as _th
THU2 = TAM / "jobs2" / "tram_retouch"
THU2.mkdir(parents=True)
tr.GIU = GiuGia()


def chay_ngam():
    kq_ = {}
    t = _th.Thread(target=lambda: kq_.setdefault("ma", tr.main_rieng([str(THU2)])), daemon=True)
    t.start()
    return t, kq_


cu = THU2 / tr.DUNG_TRAM
cu.write_text("1", encoding="utf-8")
os.utime(cu, (time.time() - 600, time.time() - 600))
tr.lightroom_dang_chay = lambda: True
t, _k = chay_ngam()
time.sleep(1.5)
ktra("cờ dừng CŨ (lần cài trước) -> trạm ngầm mới vẫn chạy, xoá cờ", t.is_alive() and not cu.exists())
(THU2 / tr.DUNG_TRAM).write_text("1", encoding="utf-8")
t.join(5)
ktra("trình cài đặt ghi dung_tram.txt -> trạm ngầm thoát ngay, xoá nhịp",
     not t.is_alive() and tr.doc_nhip(THU2, "rieng") is None
     and "lệnh dừng" in (THU2 / "tram.log").read_text(encoding="utf-8"))
tr.lightroom_dang_chay = lambda: False
tr.KHONG_LR_THOAT = 1
(THU2 / tr.DUNG_TRAM).unlink(missing_ok=True)
t, _k = chay_ngam()
t.join(10)
ktra("Lightroom đã tắt -> trạm ngầm tự thoát (không giữ card / chặn cài đặt)",
     not t.is_alive() and "Lightroom đã tắt" in (THU2 / "tram.log").read_text(encoding="utf-8"))
iss = (Path(__file__).resolve().parent / "installer_win.iss").read_text(encoding="utf-8")
ktra("installer: PrepareToInstall + InitializeUninstall dừng tiến trình nền --say- (không đụng cửa sổ app)",
     "function PrepareToInstall" in iss and "function InitializeUninstall" in iss
     and "dung_tram.txt" in iss and "--say-" in iss and "Stop-Process" in iss)

# ---------------------------------------------------------------- 15. (11/10) lời báo trước ghi THẲNG
#  Lua của Lightroom KHÔNG có os.rename / os.remove: v67 ghi cho_ bằng .part + os.rename -> hỏng
#  ở mọi lượt thật (user: "vẫn chờ xuất xong mới retouch", 22 file cho_*.txt.part). Nay plugin ghi
#  thẳng, dòng cuối het=1 = ghi trọn.
import re as _re
for f in THU.glob("*.txt"):
    f.unlink()
rt.ghi_muc_anh(str(RAW), {}, {"vet": 30})
tq = tram_moi()
tam_h = TAMX / "DSC0901.jpg"
tam_h.write_bytes(b"R\xff\xd9")
(THU / "cho_h1.txt").write_text(f"anh={tam_h}\ndich={XUAT / 'DSC0901.jpg'}\ngoc={RAW / 'DSC0901.ARW'}\n"
                                "che_do=app\n", encoding="utf-8")
time.sleep(tr.ON_DINH_GIAY + 0.1)
GOI.clear()
tq.mot_vong()
ktra("lời báo trước CHƯA có dòng het=1 (plugin đang ghi dở) -> chưa nhận",
     not GOI and (THU / "cho_h1.txt").exists())
with open(THU / "cho_h1.txt", "a", encoding="utf-8") as fh:
    fh.write("het=1\n")
tq.mot_vong()                       # thấy file render lần đầu
time.sleep(tr.ON_DINH_GIAY + 0.1)
tq.mot_vong()                       # đứng yên đủ lâu -> nhận
ktra("có dòng het=1 -> nhận, retouch sớm", len(GOI) == 1, str(GOI_SO))
cu_part = THU / "cho_v67.txt.part"
cu_part.write_text("x", encoding="utf-8")
os.utime(cu_part, (time.time() - 7200, time.time() - 7200))
tq._t_don = 0.0
tq.nhan()
ktra("file .part bỏ dở quá 1 giờ (v67 để lại) -> trạm dọn", not cu_part.exists())
lua_loi = []
for p_ in sorted((Path(__file__).resolve().parent / "AutoTone.lrplugin").glob("*.lua")):
    for i_, dong in enumerate(p_.read_text(encoding="utf-8").splitlines(), 1):
        if _re.search(r"os\.(rename|remove|execute|exit)\s*\(", dong.split("--", 1)[0]):
            lua_loi.append(f"{p_.name}:{i_}")
ktra("plugin Lua KHÔNG gọi os.rename/os.remove/os.execute (Lightroom không có các hàm đó)",
     not lua_loi, str(lua_loi))
rt.chay = chay_gia

# ---------------------------------------------------------------- 10. lệnh mở trạm / điều kiện mở
l = tr.lenh_mo_tram(THU)
ktra("lệnh mở trạm chạy ngầm: --say-tram + thư mục trạm" + (" + start (Windows)" if os.name == "nt" else ""),
     "--say-tram" in l and str(THU) in l and (l.startswith('start "" ') if os.name == "nt" else l.endswith("&")), l)
ktra("dữ liệu ở thư mục tạm (bài kiểm) -> app không mở trạm", tr.ly_do_khong_mo() != "", tr.ly_do_khong_mo())

print()
print("KET QUA:", "TAT CA DAT" if not LOI else f"{len(LOI)} LOI: {LOI}")
sys.exit(1 if LOI else 0)
