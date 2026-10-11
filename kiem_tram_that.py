# -*- coding: utf-8 -*-
"""Kiểm trạm retouch với ENGINE THẬT (cần tool retouch + mô hình; chạy được trên mã nguồn
lẫn gói). Hai phần:

  1. Trong tiến trình: Tram + engine thật -> ảnh có mặt người được retouch ĐÈ TẠI CHỖ,
     EXIF còn nguyên, đo thời gian nạp mô hình và thời gian mỗi ảnh khi engine đã nạp.
  2. Mở trạm chạy ngầm bằng ĐÚNG lệnh plugin sẽ chạy (tram_lenh.txt) -> trạm báo nhịp,
     nạp mô hình (san_sang=1), trả lời yêu cầu. Dữ liệu tạm không có bản quyền nên trạm
     phải TỪ CHỐI retouch và nói lý do — đúng đường hết hạn.

    python kiem_tram_that.py [ảnh có mặt người] [AutoTone.exe (gói) — bỏ trống = mã nguồn]
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TAM = Path(tempfile.mkdtemp(prefix="kiem_tram_that_"))
os.environ["AUTOTONE_DATA"] = str(TAM / "data")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image  # noqa: E402
import numpy as np  # noqa: E402

import retouch as rt  # noqa: E402
import tram_retouch as tr  # noqa: E402

LOI = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


def anh_mau() -> Path:
    if len(sys.argv) > 1 and sys.argv[1]:
        return Path(sys.argv[1])
    import insightface
    return Path(insightface.__file__).parent / "data" / "images" / "t1.jpg"


MUC = {"vet": 100, "min_da": 80, "bong_dau": 60, "dodge_burn": 60}
THU = TAM / "jobs" / "tram_retouch"
THU.mkdir(parents=True)
REN = TAM / "render"
REN.mkdir()
RAW = TAM / "G" / "Buoi"
RAW.mkdir(parents=True)
rt.ghi_muc_anh(str(RAW), {}, MUC)


def chuan_bi(ten: str) -> Path:
    """Ảnh Lightroom 'vừa render': JPEG có EXIF (Artist) để kiểm EXIF còn nguyên."""
    with Image.open(anh_mau()) as im:
        im = im.convert("RGB")
        #  ảnh mẫu insightface: mặt ~100 px — tool bỏ qua mặt < 150 px. Phóng lên cỡ
        #  ảnh xuất thật (cạnh dài ~3200) để mặt đủ lớn.
        k = 3200 / max(im.size)
        if k > 1:
            im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
        ex = Image.Exif()
        ex[0x013B] = "SAY Media kiem tram"          # Artist
        p = REN / ten
        im.save(p, "JPEG", quality=90, exif=ex.tobytes())
    (RAW / (Path(ten).stem + ".ARW")).write_bytes(b"raw")
    return p


def cho_kq(id_, giay):
    het = time.time() + giay
    while time.time() < het:
        d = tr.doc_kv(THU / f"kq_{id_}.txt")
        if d:
            return d
        time.sleep(0.1)
    return None


# ================================================================ 1. trong tiến trình
goc = rt.tim_tool()
print(f"tool retouch: {goc}")
if not goc or not rt.hop_le(goc):
    print("BO QUA phần 1: không có tool retouch hợp lệ")
else:
    giu = tr.GiuMay()
    t = tr.Tram(THU, "app", rt=rt, giu=giu, goc_tool=goc, khoa_ok=lambda: True)
    t0 = time.monotonic()
    m = t.lay_may(cho=240)
    t_nap = time.monotonic() - t0
    ktra("engine thật nạp được (mô hình retouch)", m is not None,
         f"{t_nap:.1f} s · {giu.thiet_bi() or '?'}")
    thoi_gian = []
    for i in (1, 2, 3):
        p = chuan_bi(f"DSC000{i}.jpg")
        truoc = np.asarray(Image.open(p).convert("RGB"), dtype=np.int16)
        tr.ghi_kv(THU / f"yc_{i}.txt", {"anh": p, "goc": RAW / f"DSC000{i}.ARW", "che_do": "app"})
        t1 = time.monotonic()
        while not (THU / f"kq_{i}.txt").exists() and time.monotonic() - t1 < 240:
            t.mot_vong()
            time.sleep(0.05)
        thoi_gian.append(time.monotonic() - t1)
        k = tr.doc_kv(THU / f"kq_{i}.txt") or {}
        sau_im = Image.open(p)
        sau = np.asarray(sau_im.convert("RGB"), dtype=np.int16)
        doi = float((np.abs(sau - truoc).max(axis=2) > 6).mean() * 100)
        artist = sau_im.getexif().get(0x013B)
        if i == 1:
            ktra("ảnh có mặt người: retouch ĐÈ TẠI CHỖ file Lightroom render",
                 k.get("ok") == "1" and doi > 0.05 and sau.shape == truoc.shape,
                 f"{k.get('mo_ta')} · đổi {doi:.2f}% điểm ảnh")
            ktra("EXIF của Lightroom còn nguyên sau khi đè", artist == "SAY Media kiem tram", str(artist))
    #  < 30 s: bắt được "nạp lại mô hình mỗi ảnh" (thử thật lạnh 45 s) kể cả khi máy đang
    #  bận (Lightroom + app khác giữ card — đo 11/10: 8–15 s/ảnh; máy rảnh ~2 s)
    ktra("engine đã nạp: mỗi ảnh không phải nạp lại mô hình",
         max(thoi_gian[1:]) < 30, " · ".join(f"{x:.1f} s" for x in thoi_gian))
    ktra("thư mục tạm cạnh ảnh render đã dọn", not list(REN.glob(".autotone_tram_*")))
    t.dung()
    giu.don(ep=True)

# ================================================================ 1b. luồng mới (11/10): hâm nóng +
#   render trước vào thư mục tạm + giao khi Lightroom xong -> ảnh hiện trong thư mục xuất là
#   đã retouch. Engine MỚI (lạnh) để đo đúng thời gian hâm nóng.
if goc and rt.hop_le(goc):
    for f in THU.glob("*"):
        if f.is_file():
            f.unlink()
    giu2 = tr.GiuMay()
    t2 = tr.Tram(THU, "app", rt=rt, giu=giu2, goc_tool=goc, khoa_ok=lambda: True)
    t0 = time.monotonic()
    t2.lay_may(cho=240)
    t_nap = time.monotonic() - t0
    t2._nong_cho = (MUC, "kiểm")
    t0 = time.monotonic()
    t2.ham_nong()
    t_nong = time.monotonic() - t0
    ktra("hâm nóng mô hình các bước đang bật (ảnh mẫu có mặt)", bool(t2._buoc_nong),
         f"nạp engine {t_nap:.1f} s · hâm {t_nong:.1f} s · bước {sorted(t2._buoc_nong)}")
    XUAT = TAM / "Xuat"
    TAMX = XUAT / ".autotone_dang_retouch"
    TAMX.mkdir(parents=True)
    ten = [f"DSC10{i}.jpg" for i in range(1, 7)]
    for i, t in enumerate(ten, 1):           # Lightroom render TRƯỚC cả lượt
        src = chuan_bi(t)
        shutil.move(str(src), str(TAMX / t))
        tr.ghi_kv(THU / f"cho_x{i}.txt", {"anh": TAMX / t, "dich": XUAT / t,
                                          "goc": RAW / (Path(t).stem + ".ARW"), "che_do": "app",
                                          "het": 1})
    lan_dau, thay_bo = [], False
    t0 = time.monotonic()
    for i, t in enumerate(ten, 1):           # vòng của plugin: tới ảnh nào báo san_ ảnh đó
        (THU / f"san_x{i}.txt").write_text("1", encoding="utf-8")
        t1 = time.monotonic()
        while not (THU / f"kq_x{i}.txt").exists() and time.monotonic() - t1 < 240:
            if any((XUAT / x).exists() and not (XUAT / x).read_bytes()[:2] == b"\xff\xd8" for x in ten):
                pass
            t2.mot_vong()
            time.sleep(0.05)
        lan_dau.append(time.monotonic() - t1)
    tong = time.monotonic() - t0
    ok_het = all((XUAT / x).is_file() for x in ten) and not list(TAMX.glob("*.jpg"))
    doi = []
    for x in ten:
        a = np.asarray(Image.open(XUAT / x).convert("RGB"), dtype=np.int16)
        doi.append(a.shape)
    ktra("6 ảnh render trước -> đều ra thư mục xuất (đã retouch), thư mục tạm sạch", ok_het,
         f"tổng {tong:.1f} s · {tong / len(ten):.1f} s/ảnh · chờ từng ảnh "
         + " ".join(f"{x:.1f}" for x in lan_dau))
    ktra("đã hâm nóng: ảnh ĐẦU không còn chờ nạp mô hình (thử thật trước đây 45 s)",
         lan_dau[0] < 15, f"{lan_dau[0]:.1f} s")
    t2.dung()
    giu2.don(ep=True)

# ================================================================ 2. trạm chạy ngầm (lệnh plugin)
for f in THU.glob("*"):
    if f.is_file():
        f.unlink()
exe = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else ""
if exe:
    lenh = f'start "" "{exe}" --say-tram "{THU}"' if os.name == "nt" else f'"{exe}" --say-tram "{THU}" &'
else:
    lenh = tr.lenh_mo_tram(THU)
print(f"lệnh mở trạm: {lenh}")
env = dict(os.environ)
subprocess.run(lenh, shell=True, env=env, cwd=str(TAM))
t0 = time.time()
nhip = None
while time.time() - t0 < 240:
    nhip = tr.doc_nhip(THU, "rieng")
    if nhip and nhip.get("san_sang") == "1":
        break
    time.sleep(0.5)
ktra("trạm chạy ngầm mở được bằng lệnh plugin, nạp xong mô hình (san_sang=1)",
     bool(nhip) and nhip.get("san_sang") == "1", f"{time.time() - t0:.1f} s · {nhip}")
p = chuan_bi("DSC0009.jpg")
noi = p.read_bytes()
tr.ghi_kv(THU / "yc_9.txt", {"anh": p, "goc": RAW / "DSC0009.ARW", "che_do": "app"})
k = cho_kq("9", 60)
ktra("dữ liệu tạm KHÔNG có bản quyền -> trạm từ chối, nói lý do, ảnh giữ nguyên",
     bool(k) and k.get("ok") == "0" and "bản quyền" in k.get("loi", "") and p.read_bytes() == noi,
     str(k))
if nhip and nhip.get("pid"):
    try:
        import psutil
        psutil.Process(int(nhip["pid"])).kill()
    except Exception:                                        # noqa: BLE001
        pass
time.sleep(1)
shutil.rmtree(TAM, ignore_errors=True)
print()
print("KET QUA:", "TAT CA DAT" if not LOI else f"{len(LOI)} LOI: {LOI}")
sys.exit(1 if LOI else 0)
