"""Dựng THẬT khung ảnh lớn (khung_anh.KhungAnh) bằng Tk, bơm sự kiện chuột /
phím thật, rồi đo ảnh vừa vẽ.

NHỮNG CHỖ ZOOM CŨ (cửa sổ Xem trước) TỪNG HỎNG — tối 3/10, user: "Sửa lại cả
tính năng zoom ảnh"
    1. Phóng to mà ảnh trên màn hình BÉ đi (tk.PhotoImage không phóng được, chỉ
       cắt vùng nhỏ rồi hiện đúng cỡ điểm ảnh). Bài này đo bằng ô cờ 10 px:
       ở 400% mỗi ô phải dài ~40 px trên màn hình.
    2. Lăn chuột phóng quanh TÂM thay vì quanh con trỏ / ảnh đứng im cho tới
       khi tiến trình con trả lời. Bài này: điểm ảnh dưới con trỏ đứng yên.
    3. Kéo để đi: ảnh không chạy theo tay, và kéo xong kẹt ở "ẢNH GỐC".
       Bài này: ảnh vẽ lại TRONG lúc kéo, kéo xong vẫn là ảnh chính.
    Thêm: nạp dần không làm nhảy khung nhìn, đổi ảnh nhanh không hiện nhầm ảnh
    cũ, chỉ vẽ vùng đang nhìn (800% của ảnh 4000 px không tạo ảnh 32000 px).

Chạy:  xvfb-run -a python3.12 kiem_khung_anh.py
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

GOC = Path(__file__).resolve().parent
sys.path.insert(0, str(GOC))

import tkinter as tk                                          # noqa: E402

LOI: list[str] = []


def ktra(ten: str, dieu: bool, mo: str = "") -> None:
    if dieu:
        print(f"  {ten:<62} {mo or 'đạt'}")
    else:
        LOI.append(f"{ten}: {mo}")


def main() -> int:
    from PIL import Image

    import giao_dien as gd
    import khung_anh as ka

    tmp = Path(tempfile.mkdtemp())
    # Ô cờ 10 px, hai màu — đo cỡ ô trên màn hình là biết tỉ lệ THẬT đang vẽ.
    co = Image.new("RGB", (4000, 3000), (30, 30, 30))
    o = Image.new("RGB", (10, 10), (230, 230, 230))
    for y in range(0, 3000, 20):
        for x in range(0, 4000, 20):
            co.paste(o, (x, y))
            co.paste(o, (x + 10, y + 10))
    co.save(tmp / "co.png")
    Image.new("RGB", (4000, 3000), (20, 60, 200)).save(tmp / "xanh.png")
    Image.new("RGB", (4000, 3000), (200, 40, 30)).save(tmp / "do.png")
    # JPEG to, xoay EXIF 6 (chụp dọc): cỡ logic phải là 3000×4000.
    ex = Image.Exif()
    ex[0x0112] = 6
    Image.new("RGB", (4000, 3000), (90, 140, 60)).save(tmp / "doc.jpg", quality=90,
                                                      exif=ex)
    Image.new("RGB", (6000, 4000), (120, 90, 200)).save(tmp / "to.jpg", quality=90)

    root = tk.Tk()
    root.geometry("1000x700+0+0")
    gd.dat_theme(root)
    k = ka.KhungAnh(root)
    k.pack(fill="both", expand=True)
    c = k.canvas

    def chay(n=4, t=0.01):
        for _ in range(n):
            root.update_idletasks()
            root.update()
            time.sleep(t)

    def cho_nap(giay=15):
        het = time.time() + giay
        while time.time() < het:
            chay(1)
            if not k.dang_nap and k.kich_thuoc() is not None:
                return True
        return False

    def mau_tai(sx, sy):
        """Màu điểm (sx, sy) trên khung — đọc từ ảnh vừa vẽ."""
        k.ve_ngay()
        x0, y0, w, h = k.vung_ve
        return tuple(k._photo._PhotoImage__photo.get(int(sx - x0), int(sy - y0)))

    def anh_duoi(sx, sy):
        """Điểm ảnh (toạ độ ảnh) đang nằm dưới điểm (sx, sy) của khung."""
        W, H = k._kt()
        s = k.ty_le()
        cx, cy = k.tam()
        return cx + (sx - W / 2) / s, cy + (sy - H / 2) / s

    #[[ MOI su kien chuot mang "time" cach nhau 1 giay: event_generate khong
    #   ghi time thi moi lan bam deu la 0 — Tk tuong lan bam thu hai (cung cho)
    #   la NHAY DUP va goi _dup thay cho _nhan. Thu nguoc 3/10 da bat duoc mot
    #   muc "dat" vi the ma khong kiem gi ca. ]]
    gio = [100_000]

    def chuot(su_kien, x, y, cach=1000):
        gio[0] += cach
        c.event_generate(su_kien, x=x, y=y, time=gio[0])

    chay(6)

    # ------------------------------------------------ 1. vừa khung, nạp xong
    k.mo(tmp / "co.png")
    ktra("mở ảnh: nạp xong ở luồng nền", cho_nap(), str(k.kich_thuoc()))
    W, H = k._kt()
    s_vua = k.ty_le()
    k.ve_ngay()
    x0, y0, w, h = k.vung_ve
    ktra("vừa khung: cả ảnh nằm giữa khung, đúng tỉ lệ",
         k.la_vua() and abs(w - 4000 * s_vua) <= 2 and abs(h - 3000 * s_vua) <= 2
         and abs(x0 - (W - w) / 2) <= 1 and abs(y0 - (H - h) / 2) <= 1,
         f"{w}×{h} ở ({x0},{y0}) · {s_vua * 100:.1f}%")

    # ------------------------------------------------ 2. phóng to là ảnh TO RA
    def chu_ky_o():
        """Bề ngang một ô cờ trên màn hình: đếm đổi màu dọc một hàng."""
        k.ve_ngay()
        x0, y0, w, h = k.vung_ve
        anh = k._photo._PhotoImage__photo
        y = h // 2
        mau = [anh.get(x, y)[0] > 128 for x in range(0, w)]
        doi = [i for i in range(1, len(mau)) if mau[i] != mau[i - 1]]
        if len(doi) < 3:
            return 0.0
        return (doi[-1] - doi[0]) / (len(doi) - 1)

    k.dat_ty_le(4.0)
    k._nhanh_toi = 0
    p4 = chu_ky_o()
    k.dat_ty_le(1.0)
    k._nhanh_toi = 0
    p1 = chu_ky_o()
    ktra("100%: ô cờ 10 px dài 10 px trên màn hình", abs(p1 - 10) <= 0.6, f"{p1:.2f} px")
    ktra("400%: ô cờ 10 px dài ~40 px — phóng to là ảnh TO RA",
         abs(p4 - 40) <= 1.5, f"{p4:.2f} px")
    k.dat_ty_le(8.0)
    k._nhanh_toi = 0
    k.ve_ngay()
    x0, y0, w, h = k.vung_ve
    ktra("800%: chỉ vẽ vùng đang nhìn (không tạo ảnh 32 000 px)",
         w <= W + 2 and h <= H + 2, f"ảnh vẽ {w}×{h}, khung {W}×{H}")
    ktra("800% thì soi điểm ảnh (không làm nhoè)", k.loc_ve == "nearest", k.loc_ve)

    # ------------------------------------------------ 3. lăn chuột quanh con trỏ
    #[[ Tu 100% chu khong tu vua khung: tu vua khung, nac dau anh moi lon hon
    #   khung mot chut va bi kep mep (dung y) — diem duoi con tro xe dich vi
    #   kep, khong phai vi phong quanh tam. ]]
    k.dat_ty_le(1.0)
    chay(2)
    diem = (260, 210)
    truoc = anh_duoi(*diem)
    s0 = k.ty_le()
    lv = k.lan_ve
    c.event_generate("<MouseWheel>", delta=120, x=diem[0], y=diem[1])
    chay(2)
    sau = anh_duoi(*diem)
    ktra("lăn chuột: phóng to một nấc", abs(k.ty_le() / s0 - k.BUOC_LAN) < 1e-6,
         f"{s0 * 100:.0f}% → {k.ty_le() * 100:.0f}%")
    ktra("lăn chuột: điểm ảnh dưới con trỏ đứng yên",
         abs(sau[0] - truoc[0]) < 0.6 and abs(sau[1] - truoc[1]) < 0.6,
         f"({truoc[0]:.1f},{truoc[1]:.1f}) → ({sau[0]:.1f},{sau[1]:.1f})")
    ktra("lăn chuột: ảnh vẽ lại NGAY, không chờ ai trả lời", k.lan_ve > lv,
         f"{k.lan_ve - lv} lần vẽ")
    for _ in range(30):
        c.event_generate("<MouseWheel>", delta=-120, x=diem[0], y=diem[1])
    chay(2)
    ktra("lăn ngược hết cỡ: về vừa khung, không nhỏ hơn", k.la_vua()
         and abs(k.ty_le() - s_vua) < 1e-9, f"{k.ty_le() * 100:.1f}%")
    for _ in range(40):
        c.event_generate("<MouseWheel>", delta=120, x=diem[0], y=diem[1])
    chay(2)
    ktra("lăn xuôi hết cỡ: dừng ở 800%", abs(k.ty_le() - k.PHONG_MAX) < 1e-9,
         f"{k.ty_le() * 100:.0f}%")

    # ------------------------------------------------ 4. kéo để đi
    k.dat_ty_le(2.0)
    chay(2)
    cx0, cy0 = k.tam()
    lv = k.lan_ve
    chuot("<ButtonPress-1>", 500, 300)
    chuot("<B1-Motion>", 470, 300)
    chuot("<B1-Motion>", 400, 280)
    chay(2)
    cx1, cy1 = k.tam()
    ktra("kéo: ảnh đi theo tay ngay trong lúc kéo (chưa thả)",
         abs((cx1 - cx0) - 50) < 0.6 and abs((cy1 - cy0) - 10) < 0.6 and k.lan_ve > lv,
         f"tâm +{cx1 - cx0:.1f},+{cy1 - cy0:.1f} điểm ảnh · {k.lan_ve - lv} lần vẽ")
    chuot("<ButtonRelease-1>", 400, 280)
    chay(2)
    #[[ Keo vuot qua mep (50% -> 940 px man hinh = 1880 diem anh, xa hon
    #   khoang tu tam toi mep): tam bi kep, mep anh trung mep khung. ]]
    k.vua_khung()
    k.dat_ty_le(0.5)
    chay(2)
    chuot("<ButtonPress-1>", 50, 50)
    chuot("<B1-Motion>", 990, 690)
    chuot("<ButtonRelease-1>", 990, 690)
    chay(2)
    cx, cy = k.tam()
    s = k.ty_le()
    ktra("kéo quá mép: ảnh dừng ở mép, không trôi ra ngoài",
         abs(cx - W / (2 * s)) < 0.6 and abs(cy - H / (2 * s)) < 0.6,
         f"tâm ({cx:.0f},{cy:.0f})")
    k.vua_khung()
    chay(2)
    cx0 = k.tam()
    chuot("<ButtonPress-1>", 500, 300)
    chuot("<B1-Motion>", 300, 300)
    chuot("<ButtonRelease-1>", 300, 300)
    chay(2)
    ktra("vừa khung thì kéo không làm ảnh trôi", k.tam() == cx0 and k.la_vua())

    # ------------------------------------------------ 5. nháy đúp
    def nhay_dup(x, y):
        chuot("<ButtonPress-1>", x, y)
        chuot("<ButtonRelease-1>", x, y, cach=20)
        chuot("<ButtonPress-1>", x, y, cach=40)
        chuot("<ButtonRelease-1>", x, y, cach=20)
        chay(3)

    truoc = anh_duoi(300, 250)
    nhay_dup(300, 250)
    sau = anh_duoi(300, 250)
    ktra("nháy đúp khi vừa khung: 100% đúng chỗ bấm",
         abs(k.ty_le() - 1.0) < 1e-9 and abs(sau[0] - truoc[0]) < 0.6
         and abs(sau[1] - truoc[1]) < 0.6, f"{k.ty_le() * 100:.0f}%")
    nhay_dup(300, 250)
    ktra("nháy đúp khi đang phóng: về vừa khung", k.la_vua())

    # ------------------------------------------------ 6. phím
    c.focus_force()
    chay(2)
    c.event_generate("<KeyPress-1>")
    chay(2)
    ktra("phím 1: 100%", abs(k.ty_le() - 1.0) < 1e-9)
    c.event_generate("<KeyPress-0>")
    chay(2)
    ktra("phím 0: vừa khung", k.la_vua())
    buoc = []
    k._khi_phim = buoc.append
    c.event_generate("<Right>")
    c.event_generate("<Left>")
    chay(2)
    ktra("← →: báo ra ngoài để sang tấm trước / sau", buoc == [1, -1], str(buoc))
    k._khi_phim = None

    # ------------------------------------------------ 7. giữ xem gốc
    k.mo(tmp / "xanh.png", truoc=tmp / "do.png")
    cho_nap()
    het = time.time() + 10
    while not k.co_truoc() and time.time() < het:
        chay(1)
    chay(2)
    ktra("có bản gốc để so", k.co_truoc())
    ktra("bình thường hiện ảnh chính", mau_tai(500, 350) == (20, 60, 200),
         str(mau_tai(500, 350)))
    chuot("<ButtonPress-1>", 500, 350)
    chay(1)
    time.sleep(ka.GIU_MS / 1000 + 0.12)
    chay(3)
    ktra("giữ chuột (không kéo): hiện ảnh GỐC", k.hien_truoc
         and mau_tai(500, 350) == (200, 40, 30), str(mau_tai(500, 350)))
    ktra("và có nhãn “ẢNH GỐC” trên ảnh", c.itemcget(k._i_nhan, "text") == "ẢNH GỐC")
    chuot("<B1-Motion>", 560, 350)
    chay(2)
    ktra("kéo sau khi giữ: về ngay ảnh chính, không kẹt ở ảnh gốc",
         not k.hien_truoc and mau_tai(500, 350) == (20, 60, 200))
    chuot("<ButtonRelease-1>", 560, 350)
    chay(2)
    chuot("<ButtonPress-1>", 500, 350)
    chuot("<ButtonRelease-1>", 500, 350)
    chay(1)
    time.sleep(ka.GIU_MS / 1000 + 0.12)
    chay(3)
    ktra("bấm nhả nhanh (lấy tiêu điểm) thì KHÔNG nhảy sang ảnh gốc",
         not k.hien_truoc)
    c.focus_force()
    c.event_generate("<KeyPress-backslash>")
    chay(2)
    goc_phim = k.hien_truoc
    c.event_generate("<KeyRelease-backslash>")
    chay(2)
    time.sleep(0.1)
    chay(2)
    ktra("giữ phím \\ : ảnh gốc, nhả ra: ảnh chính", goc_phim and not k.hien_truoc)
    k.dat_ty_le(2.5, (200, 200))
    k.giu_goc(True)
    s_goc, tam_goc = k.ty_le(), k.tam()
    k.giu_goc(False)
    ktra("so gốc giữ nguyên chỗ đang soi", s_goc == k.ty_le() and tam_goc == k.tam())

    # ------------------------------------------------ 8. nạp dần không nhảy
    #[[ Anh nho cua dai anh hien ngay, roi ban nhap, roi ban du net — khung
    #   nhin tinh theo toa do ANH DU NET nen phong / keo trong luc nap khong
    #   bi mat khi ban moi ve. ]]
    tam = Image.new("RGB", (300, 200), (120, 90, 200))
    k.mo(tmp / "to.jpg", tam=tam)
    k.ve_ngay()
    ktra("ảnh nhỏ có sẵn hiện NGAY, trước khi nạp xong",
         k.vung_ve is not None and k.kich_thuoc() == (6000, 4000) and k.dang_nap,
         str(k.kich_thuoc()))
    k.dat_ty_le(1.5, (420, 300))
    s_dat, tam_dat = k.ty_le(), k.tam()
    cho_nap()
    ktra("nạp xong bản đủ nét: tỉ lệ và chỗ đang soi giữ nguyên",
         k._sau.day_du and k.ty_le() == s_dat and k.tam() == tam_dat,
         f"{k.ty_le() * 100:.0f}%")
    ktra("ảnh đủ nét có tầng thu nhỏ (vẽ 20% không thu 24 MP mỗi lần)",
         len(k._sau.tang) >= 3, f"{len(k._sau.tang)} tầng")
    k.vua_khung()
    k._nhanh_toi = 0
    k.ve_ngay()
    t_vua = k.tang_ve
    k.dat_ty_le(2.0)
    k._nhanh_toi = 0
    k.ve_ngay()
    ktra("vừa khung vẽ từ tầng thu nhỏ, 200% vẽ từ ảnh đủ nét",
         t_vua >= 2 and k.tang_ve == 1.0, f"tầng 1/{t_vua:.0f} → 1/{k.tang_ve:.0f}")

    # ------------------------------------------------ 9. xoay EXIF, đổi ảnh nhanh
    k.mo(tmp / "doc.jpg")
    cho_nap()
    ktra("ảnh chụp dọc (EXIF 6) hiện đứng", k.kich_thuoc() == (3000, 4000),
         str(k.kich_thuoc()))
    #[[ Tam "to.jpg" dang nap do o luong nen thi bam sang tam khac: tin cua
    #   tam cu ve SAU khong duoc ve len — ghi lai moi co anh da hien. ]]
    k.mo(tmp / "to.jpg")
    time.sleep(0.04)
    chay(1)
    k.mo(tmp / "co.png")
    k.mo(tmp / "doc.jpg")
    da_hien = set()
    het = time.time() + 15
    while time.time() < het:
        chay(1)
        da_hien.add(k.kich_thuoc())
        if not k.dang_nap and not k._bo_nap.con_viec():
            break
    chay(10)
    da_hien.add(k.kich_thuoc())
    da_hien.discard(None)                # lúc đang mở chưa có ảnh nào — đúng
    ktra("bấm qua nhanh ba tấm: chỉ tấm cuối hiện ra, không lóe ảnh cũ",
         k.kich_thuoc() == (3000, 4000) and da_hien == {(3000, 4000)},
         str(sorted(da_hien)))
    k.mo(tmp / "khong_co.jpg")
    chay(2)
    ktra("file không mở được: nói ra, không sập", bool(k.loi) and k.kich_thuoc() is None,
         k.loi[:50])

    # ------------------------------------------------ 10. vào mặt
    k.mo(tmp / "co.png")
    cho_nap()
    k.mat = [(1000.0, 800.0, 100.0, 120.0), (3000.0, 2000.0, 400.0, 400.0)]
    k.i_mat = -1
    ok1 = k.vao_mat()
    c1, s1 = k.tam(), k.ty_le()
    k.vao_mat()
    c2 = k.tam()
    k.vao_mat()
    ktra("vào mặt: nhảy tới giữa mặt, phóng đủ soi (không quá 200%)",
         ok1 and abs(c1[0] - 1050) < 0.6 and abs(c1[1] - 860) < 0.6
         and abs(s1 - min(W / 312, H / 312, k.MAT_MAX)) < 1e-6,
         f"tâm ({c1[0]:.0f},{c1[1]:.0f}) · {s1 * 100:.0f}%")
    ktra("bấm tiếp: sang mặt kế, hết vòng thì quay lại mặt đầu",
         abs(c2[0] - 3200) < 0.6 and k.i_mat == 0, f"mặt {k.i_mat + 1}/2")
    k.mat = []
    ktra("ảnh không có mặt: Vào mặt không làm gì", not k.vao_mat())

    # ------------------------------------------------ 10b. cùng ảnh, độ phân giải khác
    #[[ Sang 4/10: keo thanh o Retouch la anh lon doi tu ban tren dia (6000 px)
    #   sang ban xem truoc 1400 px — va nguoc lai khi tat (bam ✕). Truoc day
    #   khac co la nhay ve vua khung: dang soi da o mat, keo mot cai la mat cho
    #   dang soi. Phai giu DUNG vung dang soi; ban 1400 px khong phong qua
    #   ZOOM_GIU (qua do chi la nhoe). ]]
    k.mo(tmp / "to.jpg")
    cho_nap()
    k._s, k._cx, k._cy = 1.0, 2500.0, 1800.0
    k._kep()
    he = 1400 / 6000
    k.dat_anh(Image.new("RGB", (1400, 933), (10, 20, 30)), giu_khung=True)
    ktra("sang bản xem trước 1400 px: giữ đúng chỗ đang soi, không phóng quá 200%",
         abs(k.tam()[0] - 2500 * he) < 1.0 and abs(k.tam()[1] - 1800 * he) < 1.0
         and abs(k.ty_le() - k.ZOOM_GIU) < 1e-9,
         f"tâm ({k.tam()[0]:.0f},{k.tam()[1]:.0f}) · {k.ty_le() * 100:.0f}%")
    k.mo(tmp / "to.jpg", giu_khung=True)
    cho_nap()
    ktra("về bản trên đĩa: lại đúng chỗ đó",
         abs(k.tam()[0] - 2500) < 1.5 and abs(k.tam()[1] - 1800) < 1.5
         and abs(k.ty_le() - k.ZOOM_GIU * 1400 / 6000) < 1e-6,
         f"tâm ({k.tam()[0]:.0f},{k.tam()[1]:.0f}) · {k.ty_le() * 100:.1f}%")
    k.vua_khung()
    k.dat_anh(Image.new("RGB", (1400, 933), (10, 20, 30)), giu_khung=True)
    ktra("đang vừa khung thì bản xem trước cũng vừa khung", k.la_vua())
    k.dat_ty_le(1.0)
    k.dat_anh(Image.new("RGB", (1000, 1000), (10, 20, 30)), giu_khung=True)
    ktra("khác tỉ lệ khung (không phải cùng một ảnh): về vừa khung", k.la_vua())

    # ------------------------------------------------ 11. trống
    k.dat_trong("Chưa chọn thư mục.", nut="Chọn thư mục", lenh=lambda: None)
    chay(2)
    ktra("không có ảnh: chữ + nút giữa khung", k.dang_trong()
         and k.nut_trong.winfo_ismapped() and k.kich_thuoc() is None)

    root.destroy()
    print()
    if LOI:
        for m in LOI:
            print("  [!] " + m)
        print(f"{len(LOI)} LỖI")
        return 1
    print("TẤT CẢ ĐẠT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
