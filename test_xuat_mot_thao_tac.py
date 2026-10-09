#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Xuất một thao tác (9/10): nút Xuất → hộp thoại → Lightroom xuất → Retouch.

CHUYỆN ĐANG LÀM
    User: "Chuyển xuất ảnh duyệt thành tự động xuất ảnh từ Lightroom, có dialog
    chọn chất lượng / thư mục / trùng tên (retouch thay ảnh gốc?) / cache / xuất
    đâu retouch đó; nút Xuất; lưu thông số retouch, preset, cache preview, worker
    thư mục xuất; kiểm tài nguyên + cảnh báo khi vừa xuất vừa retouch."

Mục kiểm
    1. Chọn ảnh mới (retouch_chung.chon_anh_moi): thường và chế độ xuất (mtime /
       bảng path->jpg / làm lại ảnh đã có kết quả / chờ ổn định).
    2. Cache xem trước: khoá theo ảnh + mức + bản tool; cất/lấy; dọn LRU đúng
       tấm lâu không xem; xoá hết.
    3. Preset: tên hợp lệ, ghi/đọc/xoá/danh sách, so giống; preset của thư mục
       giữ qua ghi_muc_anh.
    4. Cài đặt Xuất: ghi/đọc có kiểm giá trị; đánh giá song song theo ngưỡng.
    5. Thông số Lightroom: ép chất lượng chỉ khi JPEG; gửi yêu cầu xoá vết lượt
       trước; nhận ra yêu cầu đã được plugin nhận; đọc bảng path->jpg.
    6. Giao diện thật: nút “3 · Xuất” trên thanh công cụ; hộp thoại cho kết quả;
       Retouch nhận lượt xuất tuần tự (mức 0 → chép nguyên bản), Lightroom báo
       xong → retouch → kết thúc, thanh tiến độ gộp.

Chạy:  python test_xuat_mot_thao_tac.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
TAM = Path(tempfile.mkdtemp(prefix="xuat1_"))
os.environ["AUTOTONE_DATA"] = str(TAM / "data")

import numpy as np                                            # noqa: E402
from PIL import Image                                         # noqa: E402

LOI: list[str] = []


def ktra(ten: str, dieu: bool, mo: str = "") -> None:
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(f"{ten}: {mo}")


def anh_nhieu(p: Path, w=400, h=300, seed=0):
    rng = np.random.default_rng(seed)
    Image.fromarray(rng.integers(0, 255, (h, w, 3), dtype=np.uint8)).save(p, quality=95)


# ================================================================ 1. chọn ảnh mới
def phan_chon_anh():
    from retouch_chung import chon_anh_moi
    t0 = 1000.0
    # ---- chế độ thường
    td = {"biet": {"a.jpg"}, "cho": {}}
    ds = [("a.jpg", False, 10, 1, t0), ("b.jpg", True, 10, 1, t0), ("c.jpg", False, 10, 1, t0)]
    san, moi = chon_anh_moi(ds, td)
    ktra("thường: đã biết bỏ, đã có kết quả -> biết, tấm mới -> chờ ổn định",
         san == [] and moi and "b.jpg" in td["biet"] and "c.jpg" in td["cho"], f"{san} {td}")
    san, moi = chon_anh_moi([("c.jpg", False, 10, 1, t0)], td)
    ktra("thường: không đổi qua 2 lần quét -> sẵn", san == ["c.jpg"] and not moi)
    san, _ = chon_anh_moi([("c.jpg", False, 12, 2, t0)], {"biet": set(), "cho": {"c.jpg": (10, 1)}})
    ktra("đang ghi dở (cỡ đổi) -> chưa sẵn", san == [])
    # ---- chế độ xuất
    td = {"biet": set(), "cho": {}, "xuat": True, "tu_luc": t0, "ban_do": {os.path.normcase("D:\\x\\IMG_9.jpg")}}
    ds = [("D:\\x\\cu.jpg", False, 10, 1, t0 - 100),        # cũ, Lightroom chưa đụng
          ("D:\\x\\moi.jpg", True, 10, 1, t0 + 5),          # vừa xuất lại, đã có kết quả cũ
          ("D:\\x\\IMG_9.jpg", False, 10, 1, t0 - 100)]     # cũ nhưng nằm trong bảng plugin
    chon_anh_moi(ds, td)
    san, _ = chon_anh_moi(ds, td)
    ktra("xuất: ảnh cũ bỏ qua; ảnh vừa xuất lại (dù có kết quả) + ảnh trong bảng plugin -> chạy",
         sorted(san) == sorted(["D:\\x\\moi.jpg", "D:\\x\\IMG_9.jpg"]) and "D:\\x\\cu.jpg" not in td["biet"],
         str(san))


# ================================================================ 2. cache
def phan_cache():
    import cache_xem
    d = TAM / "anh"
    d.mkdir(exist_ok=True)
    a = d / "a.jpg"
    anh_nhieu(a)
    k1 = cache_xem.khoa(a, {"vet": 50}, "0.9.5")
    k2 = cache_xem.khoa(a, {"vet": 60}, "0.9.5")
    k3 = cache_xem.khoa(a, {"vet": 50}, "0.9.6")
    ktra("khoá đổi theo mức và bản tool", len({k1, k2, k3}) == 3)
    k_tron = cache_xem.khoa(a, {"vet": 50.04, "min_da": 0}, "0.9.5")
    ktra("khoá bỏ qua mức 0 và làm tròn 0,1", k_tron == cache_xem.khoa(a, {"vet": 50}, "0.9.5"))
    anh_nhieu(a, seed=1)
    os.utime(a, (time.time() + 5, time.time() + 5))
    ktra("ảnh vào đổi (mtime) -> khoá khác", cache_xem.khoa(a, {"vet": 50}, "0.9.5") != k1)
    c = cache_xem.CacheXem(TAM / "cache", gioi_han_mb=1)
    im = Image.fromarray(np.random.default_rng(3).integers(0, 255, (900, 1400, 3), dtype=np.uint8))
    ks = []
    for i in range(8):                       # mỗi tấm nhiễu ~0,4 MB -> vượt 1 MB
        k = cache_xem.khoa(f"D:/x{i}.jpg", {"vet": 50}, "b")
        ks.append(k)
        c.cat(k, im)
        if i == 0:
            time.sleep(0.05)
    ktra("cất rồi lấy lại được (ảnh 1400 px)", (c.lay(ks[-1]) or Image.new("RGB", (1, 1))).size == (1400, 900))
    ktra("dọn LRU: tổng dưới giới hạn, tấm mới nhất còn, tấm cũ nhất đã xoá",
         c.dung_luong() <= 1024 * 1024 and c.co(ks[-1]) and not c.co(ks[0]),
         f"{c.dung_luong() / 1e6:.2f} MB, {c.so_tam()} tấm")
    c2 = cache_xem.CacheXem(TAM / "cache", gioi_han_mb=1)
    ktra("mở lại thư mục cache vẫn thấy chỉ mục", c2.so_tam() == c.so_tam() and c2.co(ks[-1]))
    n = c2.xoa_het()
    ktra("xoá hết", n > 0 and c2.so_tam() == 0 and not list((TAM / "cache").glob("*.jpg")))


# ================================================================ 3. preset
def phan_preset():
    import retouch_preset as rp
    import retouch as rt
    ktra("tên preset bỏ ký tự cấm", rp.ten_hop_le('  Cưới: "nhẹ"/x?  ') == "Cưới nhẹ x")
    ten = rp.ghi("Cưới nhẹ", {"vet": 60, "min_da": "40", "nam:vet": 30, "hong": "x"})
    ktra("ghi + danh sách + đọc", ten == "Cưới nhẹ" and rp.danh_sach() == ["Cưới nhẹ"]
         and rp.doc("Cưới nhẹ") == {"vet": 60.0, "min_da": 40.0, "nam:vet": 30.0})
    ktra("so giống: 0 và thiếu như nhau", rp.giong({"vet": 60, "x": 0}, {"vet": 60.04})
         and not rp.giong({"vet": 60}, {"vet": 61}))
    try:
        rp.ghi("", {"vet": 1})
        ok = False
    except ValueError:
        ok = True
    ktra("tên rỗng -> ValueError", ok)
    vao = TAM / "thumuc_vao"
    vao.mkdir(exist_ok=True)
    rt.ghi_muc_anh(vao, {"a.jpg": {"vet": 10}}, {"vet": 60})
    rt.ghi_preset_thu_muc(vao, "Cưới nhẹ")
    rt.ghi_muc_anh(vao, {"a.jpg": {"vet": 10}, "b.jpg": {"vet": 20}}, None)
    ktra("preset của thư mục giữ qua ghi_muc_anh; mức riêng/chung không mất",
         rt.doc_preset_thu_muc(vao) == "Cưới nhẹ" and rt.doc_muc_chung(vao) == {"vet": 60}
         and set(rt.doc_muc_anh(vao)) == {"a.jpg", "b.jpg"})
    rt.ghi_preset_thu_muc(vao, "")
    ktra("bỏ preset thư mục", rt.doc_preset_thu_muc(vao) == "")
    ktra("xoá preset", rp.xoa("Cưới nhẹ") and rp.danh_sach() == [])


# ================================================================ 4. cài đặt + tài nguyên
def phan_cai_dat():
    import xuat_ui
    cd = xuat_ui.doc_cai_dat()
    ktra("mặc định: 80 / overwrite / thư mục riêng / 2 GB / retouch ngay",
         cd["chat"] == 80 and cd["va_cham"] == "overwrite" and cd["retouch_ra"] == "rieng"
         and cd["cache_mb"] == 2048 and cd["tu_retouch"] is True)
    xuat_ui.ghi_cai_dat({"chat": 95, "va_cham": "skip", "retouch_ra": "ghi_de", "cache_mb": 512,
                         "tu_retouch": False, "preset": "P", "rac": 1})
    cd = xuat_ui.doc_cai_dat()
    ktra("ghi / đọc lại đúng, bỏ khoá lạ", cd["chat"] == 95 and cd["va_cham"] == "skip"
         and cd["retouch_ra"] == "ghi_de" and cd["cache_mb"] == 512 and cd["tu_retouch"] is False
         and cd["preset"] == "P" and "rac" not in cd)
    xuat_ui.ghi_cai_dat({"chat": 500, "va_cham": "ask", "cache_mb": 1})
    cd = xuat_ui.doc_cai_dat()
    ktra("giá trị hỏng được kẹp: chất lượng ≤ 100, trùng tên không 'ask', cache ≥ 64 MB",
         cd["chat"] == 100 and cd["va_cham"] == "overwrite" and cd["cache_mb"] == 64)
    ktra("thư mục retouch mặc định cạnh thư mục xuất",
         xuat_ui.thu_muc_retouch_cua("F:\\Giao\\Cuoi\\") == os.path.normpath("F:\\Giao\\Cuoi_retouch"))
    tot = {"ram_trong_gb": 12, "vram_trong_gb": 5, "card": "RTX", "dia_trong_gb": 100}
    ok, ly = xuat_ui.danh_gia_song_song(tot)
    ktra("máy đủ sức -> song song", ok and not ly)
    ok, ly = xuat_ui.danh_gia_song_song(dict(tot, ram_trong_gb=4))
    ktra("RAM trống < 6 GB -> không", not ok and any("RAM" in x for x in ly), str(ly))
    ok, ly = xuat_ui.danh_gia_song_song(dict(tot, vram_trong_gb=1.2, vram_tong_gb=8))
    ktra("VRAM trống ít (Windows dồn được) nhưng card 8 GB -> vẫn song song", ok, str(ly))
    ok, ly = xuat_ui.danh_gia_song_song(dict(tot, vram_tong_gb=2))
    ktra("card < 4 GB VRAM -> không", not ok and any("VRAM" in x for x in ly), str(ly))
    ok, ly = xuat_ui.danh_gia_song_song(dict(tot, card=""))
    ktra("không card NVIDIA -> không (retouch CPU giành CPU với Lightroom)",
         not ok and any("CPU" in x for x in ly))
    tn = xuat_ui.tai_nguyen_may(str(TAM))
    ktra("đo máy thật trả về số", tn["ram_trong_gb"] > 0 and tn["cpu"] > 0 and tn["dia_trong_gb"] > 0,
         xuat_ui.mo_ta_tai_nguyen(tn))


# ================================================================ 5. thông số + yêu cầu
def phan_lr():
    import thongso_lr as tl
    import xuat_lr
    st = {"LR_format": "JPEG", "LR_jpeg_quality": 0.8, "LR_useWatermark": False}
    e = tl.ep(st, "F:\\Giao", "overwrite", chat=0.92)
    ktra("ép chất lượng JPEG theo người dùng", e["LR_jpeg_quality"] == 0.92 and e["LR_collisionHandling"] == "overwrite")
    e2 = tl.ep(dict(st, LR_format="TIFF"), "F:\\Giao", "skip", chat=0.5)
    ktra("định dạng khác JPEG -> không đụng chất lượng / định dạng",
         e2["LR_jpeg_quality"] == 0.8 and e2["LR_format"] == "TIFF")
    e3 = tl.ep(st, "F:\\Giao", "rename")
    ktra("không truyền chat -> giữ số Lightroom", e3["LR_jpeg_quality"] == 0.8)
    job = TAM / "jobs"
    job.mkdir(exist_ok=True)
    (job / xuat_lr.TEN_TIEN_DO_XUAT).write_text("trang_thai=xong\nxong=5\ntong=5\n", encoding="utf-8")
    (job / xuat_lr.TEN_BANG_XUAT).write_text("path\tjpg\nG:\\a.ARW\tF:\\Giao\\a.jpg\n", encoding="utf-8")
    (job / xuat_lr.TEN_CO_DUNG_XUAT).write_text("dung", encoding="utf-8")
    p = xuat_lr.yeu_cau_xuat("G:\\Buoi", "F:\\Giao", e, bo_sao=1, lo=10, job_dir=job)
    dong = p.read_text(encoding="utf-8").splitlines()
    ktra("gửi yêu cầu xoá vết lượt trước (tiến độ, bảng, cờ dừng)",
         not (job / xuat_lr.TEN_TIEN_DO_XUAT).exists() and not (job / xuat_lr.TEN_BANG_XUAT).exists()
         and not (job / xuat_lr.TEN_CO_DUNG_XUAT).exists() and "lo=10" in dong
         and "ts\tn\tLR_jpeg_quality\t0.92" in dong, str(dong[:4]))
    ktra("yêu cầu đang chờ", xuat_lr.dang_cho_xuat(job))
    p_cs = xuat_lr.yeu_cau_xuat("G:\\Buoi", "F:\\Giao", e, bo_sao=-1, job_dir=job)
    ktra("chỉ xuất ảnh chưa gắn sao -> dòng bo_sao=-1 gửi plugin",
         "bo_sao=-1" in p_cs.read_text(encoding="utf-8").splitlines())
    p_cs.unlink()
    p = xuat_lr.yeu_cau_xuat("G:\\Buoi", "F:\\Giao", e, bo_sao=1, lo=10, job_dir=job)
    p.rename(job / (xuat_lr.TEN_YEU_CAU_XUAT + ".tableABC-1791000000-3.running"))
    ktra("plugin đã nhận (.<id>.running) vẫn tính là đang chờ", xuat_lr.dang_cho_xuat(job))
    for f in job.glob("*.running"):
        f.unlink()
    ktra("hết file -> không chờ", not xuat_lr.dang_cho_xuat(job))
    (job / xuat_lr.TEN_BANG_XUAT).write_text(
        "path\tjpg\nG:\\Buoi\\DSC01.ARW\tF:\\Giao\\SAY-01.jpg\nG:\\Buoi\\DSC02.ARW\tF:\\Giao\\SAY-02.jpg\n",
        encoding="utf-8")
    b = xuat_lr.bang_anh(job)
    ktra("đọc bảng ảnh gốc -> file ra (tên ra khác tên gốc)",
         b == {"G:\\Buoi\\DSC01.ARW": "F:\\Giao\\SAY-01.jpg", "G:\\Buoi\\DSC02.ARW": "F:\\Giao\\SAY-02.jpg"}, str(b))


# ================================================================ 5b. sập máy: ghi bền + an toàn CPU
def phan_sap_may():
    """9/10: lần Xuất đầu tiên máy user sập màn hình xanh (0x101, i9-13900KS chưa vá
    microcode) — xuat.json + khoa.json thành toàn byte 0."""
    import subprocess
    import duong_dan as dd
    import khoa
    import xuat_ui
    f = TAM / "ben" / "a.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    dd.ghi_ben(f, '{"x": 1}')
    ktra("ghi_ben: ghi đủ, không để lại .part", f.read_text(encoding="utf-8") == '{"x": 1}'
         and not list(f.parent.glob("*.part")))
    khoa.ghi_trang_thai(thu=1)
    kf = khoa.thu_muc_trang_thai() / "khoa.json"
    ktra("khoa: ghi kèm bản sao lưu", kf.is_file() and kf.with_name("khoa.json.bak").is_file())
    kf.write_bytes(b"\x00" * 357)                      # đúng cảnh sau lần sập
    d = khoa.doc_trang_thai()
    ktra("khoa.json toàn byte 0 -> đọc bản sao lưu, giữ dữ liệu, không coi là hỏng",
         d.get("thu") == 1 and not d.get("hong"), str(d)[:80])
    bak = kf.with_name("khoa.json.bak")
    sua = bak.read_text(encoding="utf-8").replace('"thu": 1', '"thu": 2')
    bak.write_text(sua, encoding="utf-8")
    ktra("bản sao lưu bị sửa tay -> vẫn bắt chữ ký sai (hong)", khoa.doc_trang_thai().get("hong") is True)
    kf.unlink()
    bak.unlink()
    xuat_ui.ghi_cai_dat({"thu_muc": "F:/Giao"})
    (dd.goc_du_lieu() / "xuat.json").write_bytes(b"\x00" * 189)
    ktra("xuat.json toàn byte 0 -> về mặc định, không ném", xuat_ui.doc_cai_dat()["chat"] == 80)
    # ---- an toàn CPU
    ktra("đề xuất an toàn: Intel 13/14 + có nhân E -> bật; 12th / AMD / không nhân E -> tắt",
         xuat_ui.de_xuat_an_toan("13th Gen Intel(R) Core(TM) i9-13900KS", list(range(16, 32)))
         and xuat_ui.de_xuat_an_toan("14th Gen Intel(R) Core(TM) i7-14700K", [20, 21])
         and not xuat_ui.de_xuat_an_toan("12th Gen Intel(R) Core(TM) i9-12900K", [16, 17])
         and not xuat_ui.de_xuat_an_toan("AMD Ryzen 9 7950X", [])
         and not xuat_ui.de_xuat_an_toan("13th Gen Intel(R) Core(TM) i9-13900KS", []))
    e = xuat_ui.nhan_e()
    n = os.cpu_count() or 1
    ktra("nhân E đọc từ Windows là tập con hợp lệ các luồng", all(0 <= x < n for x in e),
         f"{len(e)} luồng nhân E / {n} · {xuat_ui.ten_cpu()}")
    try:
        import psutil
    except ImportError:
        print("  (bỏ qua ghim CPU: thiếu psutil)")
        return
    cpus = e or list(range(max(0, n - 2), n))
    gia = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                           creationflags=0x08000000 if sys.platform.startswith("win") else 0)
    try:
        cu = psutil.Process(gia.pid).cpu_affinity()
        da = xuat_ui.ghim_cpu([gia.pid, 999999999], cpus)
        ghim = psutil.Process(gia.pid).cpu_affinity()
        n_tra = xuat_ui.tra_cpu(da)
        sau = psutil.Process(gia.pid).cpu_affinity()
        ktra("ghim tiến trình vào nhân E rồi trả lại đúng như cũ (pid không có thì bỏ qua)",
             sorted(ghim) == sorted(cpus) and sorted(sau) == sorted(cu) and n_tra >= 1,
             f"ghim {len(ghim)} luồng, trả {len(sau)}")
    finally:
        gia.kill()


# ================================================================ 6. giao diện thật
def phan_giao_dien():
    try:
        import tkinter as tk
        from datetime import timedelta
        import autotone as at
        import autotone_gui as ag
        import giao_dien as gd
        import xuat_ui
        root = tk.Tk()
    except Exception as ex:                                  # noqa: BLE001
        print(f"  (bo qua phan giao dien: {ex.__class__.__name__}: {ex})")
        return
    root.withdraw()
    try:
        ag.bq.kiem = lambda: {"co_phep": True, "con_lai": timedelta(days=300), "nhac": "",
                              "goi": "1 năm", "may": "TEST01", "het_han": False, "ly_do": ""}
        gd.dat_theme(root)
        app = ag.App(root)
        cc = app.thanh_cc
        lenh = app.btn_xuat_anh.cget("command") if hasattr(app, "btn_xuat_anh") else None
        ktra("nút “3 · Xuất” trên thanh công cụ Cân tone, gọi do_xuat_hop",
             hasattr(app, "btn_xuat_anh") and "Xuất" in str(app.btn_xuat_anh.cget("text"))
             and (lenh == app.do_xuat_hop or str(lenh).endswith("do_xuat_hop"))
             and app.btn_xuat_anh.winfo_toplevel() is cc.winfo_toplevel(), str(lenh)[:60])
        # ---- hộp thoại (hộp xác nhận modal thì trả lời "có" — bài kiểm không có người bấm)
        xuat_ui.messagebox.askyesno = lambda *a, **k: True
        xuat_ui.messagebox.showinfo = lambda *a, **k: None
        st = {"LR_format": "JPEG", "LR_jpeg_quality": 0.8}
        d = xuat_ui.XuatDialog(root, buoi="Test", thu_muc_goi_y=str(TAM / "giao"), thong_so_lr=st,
                               ds_preset=[], muc_dang={"vet": 50})
        d.update()
        d._nhan_tn({"ram_trong_gb": 20, "vram_trong_gb": 6, "card": "RTX", "cpu": 8, "dia_trong_gb": 50})
        d.v_chat.set("88")
        d.v_retouch_ra.set("rieng")
        d.v_tu_retouch.set(True)
        d._bat_dau()
        kq = d.ket_qua
        ktra("hộp thoại: chất lượng 88, thư mục, retouch song song khi máy đủ sức",
             kq and kq["chat"] == 88 and kq["thu_muc"] == os.path.normpath(str(TAM / "giao"))
             and kq["song_song"] is True and kq["thu_muc_retouch"].endswith("_retouch"), str(kq)[:160])
        d = xuat_ui.XuatDialog(root, buoi="Test", thu_muc_goi_y=str(TAM / "giao"), thong_so_lr=st)
        d.update()
        d._nhan_tn({"ram_trong_gb": 3, "vram_trong_gb": 6, "card": "RTX", "cpu": 8, "dia_trong_gb": 50})
        d.v_retouch_ra.set("rieng")
        d.v_tu_retouch.set(True)
        d.v_ep.set(False)
        d._bat_dau()
        kq = d.ket_qua
        ktra("máy yếu: tự đổi sang retouch sau khi xuất xong, có lý do",
             kq and kq["song_song"] is False and kq["tu_retouch"] is True and kq["ly_do_tuan_tu"],
             str(kq and kq["ly_do_tuan_tu"]))
        ktra("cài đặt được nhớ (chat 88 -> ghi ở lần đầu, lần hai giữ)", xuat_ui.doc_cai_dat()["chat"] == 88)
        # ---- 9/10: chỉ xuất ảnh chưa gắn sao (ảnh có sao = đã lọc)
        xuat_ui.ghi_cai_dat({"chi_chua_sao": None})
        d = xuat_ui.XuatDialog(root, buoi="Test", thu_muc_goi_y=str(TAM / "giao"), thong_so_lr=st,
                               so_da_loc=41)
        d.update()
        d._nhan_tn({"ram_trong_gb": 20, "vram_trong_gb": 6, "card": "RTX", "cpu": 8, "dia_trong_gb": 50})
        mac_dinh_bat = bool(d.v_chi_chua_sao.get())
        khoa_1sao = str(d.ct_bo_sao1.cget("state")) == "disabled"
        noi = d.lbl_da_loc.cget("text")
        d._bat_dau()
        kq = d.ket_qua
        ktra("buổi đã lọc 41 ảnh -> mặc định BẬT “chỉ ảnh chưa gắn sao”, khoá ô “bỏ 1 sao”, gửi bo_sao=-1",
             mac_dinh_bat and khoa_1sao and "41" in noi and kq and kq["bo_sao"] == -1
             and kq["chi_chua_sao"] is True, f"{noi} · {kq and kq.get('bo_sao')}")
        d = xuat_ui.XuatDialog(root, buoi="Test", thu_muc_goi_y=str(TAM / "giao"), thong_so_lr=st,
                               so_da_loc=0)
        d.update()
        nho = bool(d.v_chi_chua_sao.get())
        d.v_chi_chua_sao.set(False)
        d._doi_chi_chua_sao()
        d.v_bo_sao1.set(True)
        d._nhan_tn({"ram_trong_gb": 20, "vram_trong_gb": 6, "card": "RTX", "cpu": 8, "dia_trong_gb": 50})
        d._bat_dau()
        kq = d.ket_qua
        ktra("lựa chọn được nhớ; tắt đi thì về “bỏ 1 sao” (bo_sao=1)",
             nho and kq and kq["bo_sao"] == 1 and xuat_ui.doc_cai_dat()["chi_chua_sao"] is False)
        # ---- 9/10: chọn thư mục xuất ở hộp thoại -> Retouch mặc định mở nó
        md = TAM / "xuat_md"
        md.mkdir(exist_ok=True)
        anh_nhieu(md / "A_1.jpg", seed=9)
        app._chot_thu_muc_retouch(str(md))
        import retouch as _rt
        ktra("chốt thư mục xuất -> retouch.json “vao” = thư mục đó",
             _rt.doc_cau_hinh().get("vao") == str(md))
        # ---- Retouch nhận lượt xuất (tuần tự, mức 0 -> chép nguyên bản)
        app._chon_khau("retouch")
        app.update()
        rt_win = getattr(app, "_retouch_win", None)
        if rt_win is not None:
            for _ in range(10):
                app.update()
                time.sleep(0.05)
            ktra("mở Retouch lần đầu: Vào = thư mục xuất, dải ảnh có ảnh ngay (không phải chọn)",
                 os.path.normcase(rt_win.v_vao.get()) == os.path.normcase(str(md))
                 and len(rt_win._ds_luoi) == 1, f"{rt_win.v_vao.get()} · {len(rt_win._ds_luoi)} ảnh")
        if rt_win is None:
            ktra("có màn Retouch để nhận lượt xuất", False, "bản không kèm retouch")
            return
        ktra("Retouch có nút preset + Lưu + xoá; menu ⋯ có “Xuất ảnh từ Lightroom…”",
             hasattr(rt_win, "btn_preset") and hasattr(rt_win, "btn_ps_luu")
             and any("Xuất ảnh" in rt_win.menu_rt.entrycget(i, "label")
                     for i in range(rt_win.menu_rt.index("end") + 1)
                     if rt_win.menu_rt.type(i) == "command"))
        vao = TAM / "giao"
        vao.mkdir(exist_ok=True)
        ra = TAM / "giao_retouch"
        #  không mở engine thật (mức 0 -> chỉ chép, không cần tool): bài kiểm chạy
        #  được trên máy không có saytool và không chiếm card của người dùng
        rt_win.v_goc.set("")
        rt_win._xem_hong = "bài kiểm: không mở engine"
        ok = rt_win.bat_dau_theo_xuat(vao=str(vao), ra=str(ra), ghi_de=False, muc={}, song_song=False)
        ktra("bắt đầu theo lượt xuất: trạng thái + theo dõi chế độ xuất, nút Dừng hiện",
             ok and rt_win._xuat and rt_win._theo_doi and rt_win._theo_doi.get("xuat")
             and rt_win._xuat["song_song"] is False and str(rt_win.btn_stop.cget("state")) == "normal")
        rt_win.QUET_GIAY = 0.2
        # Lightroom "đang xuất": chưa được retouch gì (tuần tự)
        anh_nhieu(vao / "IMG_1.jpg", seed=1)
        rt_win.cap_nhat_xuat({"trang_thai": "dang_chay", "xong": 1, "tong": 2, "thu_muc": str(vao)})
        for _ in range(6):
            rt_win._quet_moi()
            app.update()
            time.sleep(0.05)
        ktra("tuần tự: Lightroom chưa xong thì chưa retouch; thanh đáy nói “Lightroom xuất 1/2”",
             not (rt_win.worker and rt_win.worker.is_alive())
             and not (ra / "IMG_1.jpg").exists()
             and "Lightroom xuất 1/2" in rt_win._chu_tt_chay, rt_win._chu_tt_chay)
        #[[ 9/10 WORKER (user: "co anh thi load vao preview va add luon preset len
        #   Review"): anh vua xuat ra hien NGAY tren dai anh + anh lon, ke ca khi
        #   chua retouch (tuan tu). ]]
        ktra("worker: ảnh vừa xuất lên dải ảnh + ảnh lớn ngay trong lúc Lightroom đang xuất",
             any(str(p).endswith("IMG_1.jpg") for p, _x in rt_win._ds_luoi)
             and str(rt_win._anh_dang or "").endswith("IMG_1.jpg")
             and rt_win._xuat.get("xem_dau", "").endswith("IMG_1.jpg"),
             f"{rt_win._anh_dang} · {len(rt_win._ds_luoi)} ảnh")
        anh_nhieu(vao / "IMG_2.jpg", seed=2)
        rt_win.cap_nhat_xuat({"trang_thai": "xong", "xong": 2, "tong": 2, "thu_muc": str(vao),
                              "thong_bao": "3 giay"})
        het = time.monotonic() + 20
        while time.monotonic() < het and rt_win._xuat is not None:
            rt_win._quet_moi() if rt_win._hen_quet_ma is None and not (rt_win.worker and rt_win.worker.is_alive()) else None
            app.update()
            time.sleep(0.1)
        ktra("Lightroom xong -> retouch (mức 0: chép nguyên bản) -> kết thúc lượt",
             rt_win._xuat is None and rt_win._theo_doi is None and (ra / "IMG_1.jpg").is_file()
             and (ra / "IMG_2.jpg").is_file(), rt_win._chu_tt_chay)
        ktra("câu tổng kết ở thanh đáy, đếm đủ 2 ảnh đã xử lý",
             "Xuất + retouch xong" in rt_win._chu_tt_chay and "retouch 2 ảnh" in rt_win._chu_tt_chay,
             rt_win._chu_tt_chay)

        #[[ 10/10 KE THUA NEXUS: VUA XUAT VUA RETOUCH qua HANG DOI plugin — anh vao
        #   hang doi (Lightroom da ghi xong) duoc retouch NGAY lan quet dau, khong
        #   cho dung yen qua hai lan quet; file dang ghi do chua vao hang doi thi
        #   khong dung; het hang doi + Lightroom xong -> ket thuc. ]]
        import xuat_lr
        jd_cu = at.LR_JOB_DIR
        at.LR_JOB_DIR = TAM / "jobs_hang_doi"
        at.LR_JOB_DIR.mkdir(exist_ok=True)
        try:
            vao2, ra2 = TAM / "giao2", TAM / "giao2_retouch"
            vao2.mkdir(exist_ok=True)
            rt_win.bat_dau_theo_xuat(vao=str(vao2), ra=str(ra2), ghi_de=False, muc={},
                                     song_song=True)
            rt_win._du_tai_nguyen = lambda: (True, "")      # không phụ thuộc RAM máy kiểm
            hd = at.LR_JOB_DIR / xuat_lr.TEN_HANG_DOI_XUAT
            hd.write_text("", encoding="utf-8")              # plugin mở hàng đợi đầu lượt
            anh_nhieu(vao2 / "A_1.jpg", seed=3)
            (vao2 / "A_2.jpg").write_bytes(b"\xff\xd8 Lightroom dang ghi do")
            with open(hd, "a", encoding="utf-8") as fh:
                fh.write(f"G:\\Buoi\\A_1.ARW\t{vao2 / 'A_1.jpg'}\n")
            rt_win.cap_nhat_xuat({"trang_thai": "dang_chay", "xong": 1, "tong": 2,
                                  "thu_muc": str(vao2)})
            rt_win._quet_moi()                               # MỘT lần quét
            td2 = rt_win._theo_doi or {}
            biet = {Path(k).name for k in td2.get("biet", set())}
            ktra("song song + hàng đợi: ảnh Lightroom vừa xuất được retouch NGAY lần quét đầu",
                 "A_1.jpg" in biet and td2.get("co_hd"), str(sorted(biet)))
            ktra("file đang ghi dở chưa vào hàng đợi: không đụng", "A_2.jpg" not in biet)
            ktra("có hàng đợi -> nhịp quét 0,7 s",
                 rt_win.QUET_GIAY_HANG_DOI == 0.7 and td2.get("co_hd"))
            het = time.monotonic() + 15
            while time.monotonic() < het and (rt_win.worker and rt_win.worker.is_alive()
                                               or getattr(rt_win, "_cho_xong", False)):
                app.update()
                time.sleep(0.05)
            anh_nhieu(vao2 / "A_2.jpg", seed=4)
            with open(hd, "a", encoding="utf-8") as fh:
                fh.write(f"G:\\Buoi\\A_2.ARW\t{vao2 / 'A_2.jpg'}\n#het\t2\n")
            rt_win.cap_nhat_xuat({"trang_thai": "xong", "xong": 2, "tong": 2,
                                  "thu_muc": str(vao2), "thong_bao": "2 giay"})
            het = time.monotonic() + 20
            while time.monotonic() < het and rt_win._xuat is not None:
                if rt_win._hen_quet_ma is None and not (rt_win.worker and rt_win.worker.is_alive()):
                    rt_win._quet_moi()
                app.update()
                time.sleep(0.05)
            ktra("hết hàng đợi + Lightroom xong -> kết thúc lượt, đủ 2 ảnh",
                 rt_win._xuat is None and (ra2 / "A_1.jpg").is_file() and (ra2 / "A_2.jpg").is_file()
                 and "retouch 2 ảnh" in rt_win._chu_tt_chay, rt_win._chu_tt_chay)
        finally:
            at.LR_JOB_DIR = jd_cu
    finally:
        try:
            root.destroy()
        except Exception:                                    # noqa: BLE001
            pass


def main() -> int:
    #  treo quá 180 s (Tk / engine) thì in vết các luồng rồi thoát — không treo bộ kiểm
    import faulthandler
    faulthandler.dump_traceback_later(180, exit=True)
    phan_chon_anh()
    phan_cache()
    phan_preset()
    phan_cai_dat()
    phan_lr()
    phan_sap_may()
    phan_giao_dien()
    print("TAT CA DAT" if not LOI else f"{len(LOI)} LOI")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
