#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bảng chọn màu da đích — hai chấm cạnh nút "Màu da" (16/10, chon_mau_da.py).

User 16/10: "Khi di chuột vào cần hiển thị là màu da của phần nào. Ngoài ra khi bấm vào
chọn hãy mở bảng màu kiểu như ảnh mẫu mặc định sẽ chọn vào vùng màu da mà đang hiển thị
đc chọn và cho người dùng chọn trên bảng màu đó. chọn xong thì sẽ lưu màu da đó làm màu
đích."

  1. Màu: HSV đi về đúng màu; ô vuông (trắng / màu thuần / đen ở đúng góc); thanh sắc độ
     trên 360° -> dưới 0°; R G B % Lightroom khớp mask_xem.rgb_pt và đổi ngược được.
  2. Kéo DỌC ô vuông (độ sáng) giữ hue + độ đậm q mà chuỗi màu da dùng (câu ghi chú trong hộp).
  3. cap_nhat_mau: mẫu có tên chỉ đổi đúng khe; khe kia, vùng trắng giữ; số đo phân vùng
     (_mn) theo đúng tỉ lệ; "Mặc định" -> mẫu MỚI không đè mẫu có sẵn; tên cấm.
  4. Hộp chọn màu (Tk thật): mở ở màu đang hiện; kéo ô vuông / thanh sắc; gõ % Lightroom;
     bấm "Hiện tại" trả màu cũ; Lưu gọi lại đúng màu; đóng thì không gọi.
  5. App thật: hai chấm có chú thích trong nhà / ngoài trời; bấm chấm ngoài trời ở "Mặc
     định" -> mẫu mới chọn luôn, khe trong nhà = đích mặc định; sửa tiếp khe trong nhà của
     mẫu đó -> không thêm mẫu; bấm lần hai khi hộp đang mở không mở hộp thứ hai; bật "da
     trắng hồng" -> chấm Mặc định vẽ đúng đích read_cfg dùng.
  6. Bút lấy màu (user 16/10: "chấm vào bất kỳ đâu trên ảnh sẽ lấy đc ra đúng mã màu"): quy
     toạ độ Tk -> điểm ảnh theo tỉ lệ (Retina / Windows phóng 150%, gốc màn ảo âm); kính lúp
     đúng điểm giữa; hộp ẩn khi chụp, bấm trái lấy đúng điểm ảnh rồi hộp hiện lại; bấm
     ngoài vùng chụp không lấy; bấm phải huỷ; chụp lỗi -> báo + hộp hiện lại. KHÔNG chụp
     màn hình thật — ảnh chụp giả thay cmd.chup_man_hinh.
Chạy:  python test_chon_mau_da.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
TAM = Path(tempfile.mkdtemp(prefix="chon_mau_da_"))
os.environ["AUTOTONE_DATA"] = str(TAM / "du_lieu")

for _l in (sys.stdout, sys.stderr):
    try:
        _l.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                        # noqa: BLE001
        pass

import numpy as np            # noqa: E402

import autotone as at         # noqa: E402
import chon_mau_da as cmd     # noqa: E402
import curve_da as cd         # noqa: E402
import mask_xem               # noqa: E402

LOI: list = []


def ktra(ten, dk, chi_tiet=""):
    print(f"  [{'DAT ' if dk else 'LOI '}] {ten}  {chi_tiet}")
    if not dk:
        LOI.append(ten)


def gan(a, b, tol=1):
    return all(abs(int(x) - int(y)) <= tol for x, y in zip(a, b))


def phan_mau():
    print("1. Màu: HSV, ô vuông, thanh sắc độ, % Lightroom")
    da = [237, 206, 200]
    ktra("sRGB -> HSV -> sRGB về đúng màu", cmd.rgb_cua(*cmd.hsv_cua(da)) == da)
    o = cmd.anh_sv(30.0, 64)
    thuan = cmd.rgb_cua(30.0, 1.0, 1.0)
    ktra("ô vuông: trên-trái trắng, trên-phải màu thuần, đáy đen",
         gan(o[0, 0], (255, 255, 255)) and gan(o[0, -1], thuan) and gan(o[-1, 0], (0, 0, 0))
         and gan(o[-1, -1], (0, 0, 0)), f"{o[0, -1].tolist()} vs {thuan}")
    ktra("ô vuông: giữa = HSV(30°, 0.5, 0.5)", gan(o[32, 32], cmd.rgb_cua(30, 32 / 63, 1 - 32 / 63), 2))
    s = cmd.anh_sac(4, 61)
    ktra("thanh sắc độ: trên đỏ (360°), giữa xanh lơ (180°), dưới đỏ (0°)",
         gan(s[0, 0], (255, 0, 0)) and gan(s[30, 0], (0, 255, 255)) and gan(s[-1, 0], (255, 0, 0)))
    pt = cmd.pt_lr(da)
    ktra("R G B % Lightroom = mask_xem.rgb_pt (cùng số chip Mask da)", pt == mask_xem.rgb_pt([da]),
         f"{pt}")
    ktra("% Lightroom -> sRGB về đúng màu (±1)", gan(cmd.rgb_tu_pt(pt), da), str(cmd.rgb_tu_pt(pt)))
    ktra("chú thích chấm nói rõ khe + số Lightroom",
         "trong nhà" in cmd.chu_cham("trong", da, "Gu A") and "Gu A" in cmd.chu_cham("trong", da, "Gu A")
         and "ngoài trời" in cmd.chu_cham("ngoai", da, None) and "R 8" in cmd.chu_cham("ngoai", da, None))

    print("2. Kéo dọc ô vuông (độ sáng) giữ hue + độ đậm q của chuỗi màu da")
    h, s_, _v = cmd.hsv_cua(da)
    h0, q0 = cd.hue_q(at.mau_dich_lab(cmd.rgb_cua(h, s_, 0.93)))
    h1, q1 = cd.hue_q(at.mau_dich_lab(cmd.rgb_cua(h, s_, 0.62)))
    ktra("hue lệch < 1.5°, q lệch < 4% giữa sáng 0.93 và 0.62", abs(h0 - h1) < 1.5 and abs(q1 / q0 - 1) < 0.04,
         f"hue {h0:.1f}/{h1:.1f} · q {q0:.3f}/{q1:.3f}")
    h2, q2 = cd.hue_q(at.mau_dich_lab(cmd.rgb_cua(h, min(1.0, s_ * 1.6), 0.93)))
    ktra("…còn kéo NGANG (bão hoà) thì đổi độ đậm", q2 > q0 * 1.2, f"q {q0:.3f} -> {q2:.3f}")


def phan_luu():
    print("3. cap_nhat_mau")
    goc = ([227, 184, 185], [166, 123, 105])
    d = {"_cuoi": "Gu A", "Gu A": {"trong": [230, 200, 190], "n_anh": 3,
                                   "trang": {"trong": [0.001, 0.002]},
                                   "trong_mn": [220, 190, 182]}}
    ten = cmd.cap_nhat_mau(d, "Gu A", "trong", [240, 196, 190], goc, luc="L")
    m = d["Gu A"]
    ktra("mẫu có tên: sửa tại chỗ, không thêm mẫu", ten == "Gu A" and set(d) == {"_cuoi", "Gu A"})
    ktra("khe trong nhà = màu mới", m["trong"] == [240, 196, 190])
    ktra("mẫu cũ thiếu 'ngoai' -> ghi rõ ngoài trời = trong nhà CŨ (không đi theo màu mới)",
         m["ngoai"] == [230, 200, 190], str(m.get("ngoai")))
    ti = cmd._lin([240, 196, 190]) / cmd._lin([230, 200, 190])
    ktra("số đo phân vùng (trong_mn) nhân đúng tỉ lệ tuyến tính, ngoai_mn giữ số cũ",
         gan(m["trong_mn"], cmd._tu_lin(cmd._lin([220, 190, 182]) * ti)) and m["ngoai_mn"] == [220, 190, 182],
         f"{m['trong_mn']}")
    ktra("vùng trắng + số ảnh giữ nguyên, ghi dấu sửa tay",
         m["trang"] == {"trong": [0.001, 0.002]} and m["n_anh"] == 3 and m["sua_tay"] == "L")
    cmd.cap_nhat_mau(d, "Gu A", "ngoai", [170, 120, 100], goc)
    ktra("sửa khe ngoài trời không đụng khe trong nhà",
         d["Gu A"]["ngoai"] == [170, 120, 100] and d["Gu A"]["trong"] == [240, 196, 190])
    t2 = cmd.cap_nhat_mau(d, None, "ngoai", [180, 130, 110], goc, ten_moi="Gu A", cam=("Mặc định",))
    ktra("'Mặc định' -> mẫu MỚI, không đè mẫu trùng tên", t2 == "Gu A 2" and d["Gu A"]["ngoai"] == [170, 120, 100],
         t2)
    ktra("…khe kia = đích mặc định đang hiện, đánh dấu tu_mac_dinh",
         d[t2]["trong"] == goc[0] and d[t2]["ngoai"] == [180, 130, 110] and d[t2]["tu_mac_dinh"])
    ktra("tên cấm (trùng 'Mặc định' / bắt đầu _) -> đổi tên",
         cmd.ten_trong({}, "Mặc định", cam=("Mặc định",)) == "Mặc định (riêng)"
         and cmd.ten_trong({}, "_cuoi") == "cuoi (riêng)" and cmd.ten_trong({}, "  ") == cmd.TEN_MOI)
    try:
        cmd.cap_nhat_mau(d, "Gu A", "giua", [1, 2, 3], goc)
        ok = False
    except ValueError:
        ok = True
    ktra("khe lạ -> ValueError", ok)


def phan_hop(root):
    import giao_dien as gd
    print("4. Hộp chọn màu (Tk thật)")
    kq: list = []
    goc = [237, 206, 200]
    hop = cmd.HopChonMauDa(root, goc, "trong", ten_mau="Gu A", xong=lambda r, t: kq.append((r, t)))
    root.update()
    ktra("mở ở đúng màu đang hiện + số % Lightroom điền sẵn",
         hop.rgb() == goc and [b.get() for b in hop.bien_pt] == ["%.1f" % x for x in cmd.pt_lr(goc)])
    ktra("mẫu có tên -> không có ô tên mẫu mới", hop.bien_ten is None)

    class E:
        def __init__(self, x, y):
            self.x, self.y = x, y
    n, p = hop.n, hop.p
    hop._keo_sv(E(p + n - 1, p))
    ktra("bấm góc trên-phải ô vuông -> màu thuần của sắc đang chọn",
         hop.rgb() == cmd.rgb_cua(hop.h, 1.0, 1.0) and hop.s == 1.0 and hop.v == 1.0)
    hop._keo_sac(E(5, p + (n - 1) // 2))
    ktra("kéo thanh sắc độ giữa -> ~180° (xanh lơ)", abs(hop.h - 180.0) < 1.0, f"{hop.h:.1f}")
    hop._keo_sv(E(-50, 10 ** 4))
    ktra("kéo ra ngoài ô vuông -> kẹp trong (đen)", hop.rgb() == [0, 0, 0])
    hop.cv_cu.event_generate("<Button-1>", x=3, y=3)
    root.update()
    ktra("bấm ô 'Hiện tại' -> về màu cũ", hop.rgb() == goc, str(hop.rgb()))
    for b, x in zip(hop.bien_pt, ("88.0", "80,5", "77.0")):
        b.set(x)
    hop._go_so()
    ktra("gõ % Lightroom (dấu phẩy được) + Enter -> màu theo số", gan(hop.rgb(), cmd.rgb_tu_pt([88, 80.5, 77])),
         str(hop.rgb()))
    ktra("…ô số giữ đúng số vừa gõ", [b.get() for b in hop.bien_pt] == ["88.0", "80,5", "77.0"])
    hop.bien_pt[0].set("abc")
    truoc = hop.rgb()
    ktra("số sai -> không đổi màu, điền lại số đúng", not hop._doc_so() and hop.rgb() == truoc
         and hop.bien_pt[0].get() != "abc")
    for b, x in zip(hop.bien_pt, ("86.0", "79.0", "75.0")):
        b.set(x)
    hop._luu()                                          # gõ rồi bấm Lưu luôn (không Enter)
    root.update()
    ktra("Lưu (số gõ chưa Enter vẫn được áp) -> gọi lại đúng màu, đóng hộp",
         len(kq) == 1 and gan(kq[0][0], cmd.rgb_tu_pt([86, 79, 75])) and kq[0][1] is None
         and not hop.winfo_exists(), str(kq))
    hop2 = cmd.HopChonMauDa(root, goc, "ngoai", ten_mau=None, ten_moi="Gu mới",
                            xong=lambda r, t: kq.append((r, t)))
    root.update()
    ktra("'Mặc định' -> có ô tên mẫu mới điền sẵn", hop2.bien_ten is not None and hop2.bien_ten.get() == "Gu mới")
    hop2.focus_force()
    root.update()
    hop2.event_generate("<Escape>")
    root.update()
    ktra("Esc -> đóng, không lưu", len(kq) == 1 and not hop2.winfo_exists())
    del gd


def phan_but(root):
    print("6. Bút lấy màu (ảnh chụp giả — không chụp màn hình thật)")
    #  ảnh "Retina": 2 điểm ảnh mỗi điểm Tk, màn ảo bắt đầu ở x = -100 (màn phụ bên trái)
    yy, xx = np.mgrid[0:200, 0:400]
    anh = np.stack([xx % 256, yy, np.full_like(xx, 77)], axis=-1).astype(np.uint8)
    vung = (-100, 0, 200, 100)
    ktra("quy toạ độ theo tỉ lệ + gốc âm: (-100, 0) -> điểm (0, 0); (0, 50) -> (200, 100)",
         cmd.diem_anh(anh, vung, -100, 0) == (0, 0) and cmd.diem_anh(anh, vung, 0, 50) == (200, 100)
         and cmd.diem_anh(anh, vung, 99.9, 99.9) == (399, 199))
    ktra("ngoài vùng chụp -> None", cmd.diem_anh(anh, vung, 100, 50) is None
         and cmd.mau_tai(anh, vung, -101, 5) is None)
    ktra("mau_tai = đúng điểm ảnh dưới mũi chuột", cmd.mau_tai(anh, vung, 0, 50) == [200, 100, 77])
    lup = cmd.anh_kinh_lup(anh, vung, 0, 50, r=6, phong=9)
    ktra("kính lúp 13×13 điểm × 9: ô giữa = màu điểm chấm",
         lup.shape == (117, 117, 3) and lup[58, 58].tolist() == [200, 100, 77])
    lup2 = cmd.anh_kinh_lup(anh, vung, -100, 0, r=6, phong=9)
    ktra("…sát mép: phần ngoài ảnh tô xám, ô giữa vẫn đúng",
         lup2[0, 0].tolist() == [64, 64, 64] and lup2[58, 58].tolist() == [0, 0, 77])

    goi: list = []
    goc_chup = cmd.chup_man_hinh
    cmd.chup_man_hinh = lambda w: (goi.append(1), (anh, (0, 0, 200, 100)))[1]
    loi_hop: list = []
    goc_loi = cmd.messagebox.showerror
    cmd.messagebox.showerror = lambda *a, **k: loi_hop.append(a)

    class E:
        def __init__(self, x, y):
            self.x_root, self.y_root = x, y

    def cho(dk, giay=3.0):
        het = time.time() + giay
        while time.time() < het:
            root.update()
            if dk():
                return True
            time.sleep(0.02)
        return False

    try:
        goc = [237, 206, 200]
        hop = cmd.HopChonMauDa(root, goc, "trong", ten_mau="Gu A")
        root.update()
        ktra("hộp có nút 'Lấy màu' (biểu tượng bút)",
             "Lấy màu" in str(hop.btn_hut.cget("text")) and hop.btn_hut._icon == "hut_mau")
        import bieu_tuong
        ktra("biểu tượng hut_mau có trong bộ", bieu_tuong.co("hut_mau"))
        hop.btn_hut.invoke()
        root.update()
        ktra("bấm 'Lấy màu' -> hộp ẩn trước khi chụp (khỏi che ảnh)", hop.state() == "withdrawn" and not goi)
        ktra("…rồi chụp đúng một lần, lớp phủ + kính lúp hiện",
             cho(lambda: isinstance(hop._but, cmd.ButLayMau)) and len(goi) == 1
             and hop._but.phu.winfo_exists() and hop._but.lup.winfo_exists())
        but = hop._but
        but._di(E(75, 30))
        root.update()
        ktra("rê chuột: kính lúp ghi số Lightroom + sRGB của điểm dưới mũi",
             "sRGB 150 · 60 · 77" in but.lbl.cget("text") and but.o_mau.cget("background") == "#963c4d",
             but.lbl.cget("text").replace("\n", " | "))
        but._bam(E(500, 30))
        root.update()
        ktra("bấm ngoài vùng chụp -> chưa lấy, bút vẫn mở", hop._but is but and but.phu is not None)
        but._bam(E(75, 30))
        root.update()
        ktra("bấm trái -> lấy đúng màu điểm chấm, hộp hiện lại, lớp phủ đóng",
             gan(hop.rgb(), [150, 60, 77]) and hop.state() == "normal" and hop._but is None
             and but.phu is None and but.anh is None, str(hop.rgb()))
        ktra("…ô số Lightroom theo màu vừa lấy",
             [b.get() for b in hop.bien_pt] == ["%.1f" % x for x in cmd.pt_lr(hop.rgb())])
        truoc = hop.rgb()
        hop.lay_mau()
        cho(lambda: isinstance(hop._but, cmd.ButLayMau))
        but = hop._but
        but.phu.event_generate("<Button-3>", x=5, y=5)
        root.update()
        ktra("bấm phải -> huỷ, giữ màu cũ, hộp hiện lại",
             hop._but is None and hop.rgb() == truoc and hop.state() == "normal")

        def hong(_w):
            raise OSError("không có quyền")
        cmd.chup_man_hinh = hong
        hop.lay_mau()
        cho(lambda: hop._but is None and hop.state() == "normal")
        ktra("chụp lỗi -> báo lỗi, hộp hiện lại, màu giữ nguyên",
             len(loi_hop) == 1 and "không có quyền" in str(loi_hop[0]) and hop.state() == "normal"
             and hop.rgb() == truoc)
        hop.destroy()
    finally:
        cmd.chup_man_hinh = goc_chup
        cmd.messagebox.showerror = goc_loi


def phan_app(root):
    import autotone_gui as ag
    import giao_dien as gd
    print("5. App thật: hai chấm, chú thích, lưu mẫu")
    ag.bq.kiem = lambda: {"co_phep": True, "con_lai": timedelta(days=300), "nhac": "",
                          "goi": "1 năm", "may": "TEST01", "het_han": False, "ly_do": ""}
    root.geometry("1500x900+0+0")
    gd.dat_theme(root)
    app = ag.App(root)
    #  17/10: Quy trình Auto mặc định BẬT, mẫu da tự chọn gợi ý theo loại buổi — bài này kiểm
    #  luồng thường với mẫu "Mặc định"
    app.v_auto_lr.set(False)
    app.v_mau_da.set(ag.MAU_DA_MAC_DINH)
    app.grid(row=0, column=0, sticky="nsew")

    def vong(k=4):
        for _ in range(k):
            root.update_idletasks()
            root.update()
            time.sleep(0.02)
    vong(8)
    app.v_mau_da.set(ag.MAU_DA_MAC_DINH)
    app._doi_mau_da(nho=False)
    vong()
    goc = app._dich_hien()
    ktra("hai chấm = đích Mặc định (trong · ngoài)",
         set(app.cv_mau_da) == {"trong", "ngoai"} and goc == tuple(map(list, at.dich_da_cuoi(app.read_cfg()))))
    gy = app._gy_mau_da
    ktra("rê chuột: chấm trái nói 'trong nhà', chấm phải 'ngoài trời' + số Lightroom",
         "trong nhà" in gy["trong"].chu and "ngoài trời" in gy["ngoai"].chu
         and "Lightroom" in gy["trong"].chu and "mặc định" in gy["ngoai"].chu.lower(), gy["trong"].chu)
    cv = app.cv_mau_da["ngoai"]
    ktra("chấm có bấm được (Button-1 gọi _chon_mau_da, con trỏ bàn tay)",
         bool(cv.bind("<Button-1>")) and cv.cget("cursor") == "hand2")
    if cv.winfo_viewable():
        cv.event_generate("<Button-1>", x=8, y=8)
    else:                                               # nhóm Tone đang đóng: gọi thẳng
        app._chon_mau_da("ngoai")
    vong()
    hop = getattr(app, "_hop_mau_da", None)
    ktra("bấm chấm ngoài trời -> mở bảng màu ở đúng màu chấm đó",
         hop is not None and hop.winfo_exists() and hop.khe == "ngoai" and gan(hop.rgb(), goc[1]),
         str(hop and hop.rgb()))
    app._chon_mau_da("ngoai")
    vong()
    so_hop = sum(1 for w in root.winfo_children() if isinstance(w, cmd.HopChonMauDa))
    ktra("bấm lần hai khi hộp đang mở -> không mở hộp thứ hai", so_hop == 1, str(so_hop))
    hop.dat_rgb([190, 140, 120])
    hop._luu()
    vong()
    d = json.loads((Path(os.environ["AUTOTONE_DATA"]) / ag.FILE_MAU_DA).read_text(encoding="utf-8"))
    m = d.get(cmd.TEN_MOI) or {}
    ktra("Lưu ở 'Mặc định' -> mẫu mới 'Màu da tự chọn': ngoài trời = màu chọn, trong nhà = đích mặc định",
         gan(m.get("ngoai") or [], [190, 140, 120]) and m.get("trong") == [int(round(x)) for x in goc[0]],
         str(m))
    c = app.read_cfg()
    ktra("…app chọn luôn mẫu đó, read_cfg nhắm đúng màu mới",
         app.v_mau_da.get() == cmd.TEN_MOI and gan(c["mau_da_dich"]["ngoai"], [190, 140, 120])
         and d.get("_cuoi") == cmd.TEN_MOI)
    cv = app.cv_mau_da["ngoai"]
    fill = cv.itemcget(cv.find_all()[0], "fill")
    ktra("…chấm ngoài trời vẽ lại màu mới, chú thích ghi tên mẫu",
         fill == "#%02x%02x%02x" % tuple(m["ngoai"]) and cmd.TEN_MOI in app._gy_mau_da["ngoai"].chu, fill)
    app._chon_mau_da("trong")
    vong()
    hop = app._hop_mau_da
    ktra("sửa tiếp khe trong nhà của mẫu có tên -> hộp không hỏi tên", hop.bien_ten is None and hop.ten_mau == cmd.TEN_MOI)
    hop.dat_rgb([235, 195, 188])
    hop._luu()
    vong()
    d = json.loads((Path(os.environ["AUTOTONE_DATA"]) / ag.FILE_MAU_DA).read_text(encoding="utf-8"))
    mau = [k for k in d if not k.startswith("_")]
    ktra("…chỉ đổi khe trong nhà, không thêm mẫu",
         mau == [cmd.TEN_MOI] and gan(d[cmd.TEN_MOI]["trong"], [235, 195, 188])
         and gan(d[cmd.TEN_MOI]["ngoai"], [190, 140, 120]), str(d))
    app.v_mau_da.set(ag.MAU_DA_MAC_DINH)
    app._doi_mau_da(nho=False)
    app.v_grade.set(True)
    vong()
    md = at.dich_mac_dinh(app.read_cfg())
    cv = app.cv_mau_da["trong"]
    ktra("bật 'da trắng hồng' ở Mặc định -> chấm vẽ đúng đích read_cfg dùng",
         md and app._dich_hien()[0] == md["trong"]
         and cv.itemcget(cv.find_all()[0], "fill") == "#%02x%02x%02x" % tuple(md["trong"]),
         str(md and md["trong"]))
    app.v_grade.set(False)
    vong()
    app.destroy()


def main() -> int:
    phan_mau()
    phan_luu()
    try:
        import tkinter as tk
        root = tk.Tk()
    except Exception as ex:                                  # noqa: BLE001
        print(f"  (bỏ phần giao diện: {type(ex).__name__}: {ex})")
        root = None
    if root is not None:
        try:
            import giao_dien as gd
            gd.dat_theme(root)
            phan_hop(root)
            phan_but(root)
            phan_app(root)
        finally:
            try:
                root.destroy()
            except Exception:                                # noqa: BLE001
                pass
    print()
    print("TAT CA DAT" if not LOI else f"{len(LOI)} LOI: {LOI}")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
