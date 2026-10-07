"""Dựng THẬT lưới ảnh (luoi_anh.LuoiAnh) bằng Tk và kiểm trên hình học thật.

VÌ SAO CẦN FILE NÀY BÊN CẠNH kiem_bo_cuc.py
    kiem_bo_cuc.py đọc mã nguồn — biết lưới "có được nối" chứ không biết nó có
    chia cột đúng không, có thật sự chỉ vẽ ô đang nhìn không, bấm vào có chọn
    đúng tấm không. Ba chỗ mà sai thì hoặc app đứng hình (vẽ 3 800 ô), hoặc
    bấm tấm này ra số của tấm kia.

    File này mở một màn hình ảo (Xvfb), dựng lưới bằng widget Tk thật với
    "RAW giả" có JPEG nhúng, rồi hỏi thẳng: mấy cột, vẽ mấy ô, bấm ô thứ i thì
    chọn tấm nào, bảng số và lưới có chọn cùng một tấm không.

    Trước 3/10 tối file này kiểm _xep_cot() (ba cột tuỳ chọn tự co) — hàm đó
    đi cùng bố cục cũ. Bố cục Evoto để tuỳ chọn ở một cột bên phải; thứ cần
    "vẽ thật" bây giờ là lưới ảnh — và dải ảnh một hàng dưới ảnh lớn của mô-đun
    Retouch (kiem_dai_anh).

LƯU Ý VỀ PHÔNG CHỮ
    Máy này không có Segoe UI nên số px khác Windows. File này KHÔNG khẳng
    định "ở 1360 px thì ra 4 cột" — nó kiểm thứ không phụ thuộc phông: rộng
    thì nhiều cột hơn hẹp, ô giãn kín bề ngang, số ô vẽ ra chỉ cỡ một màn.

Chạy:  xvfb-run -a python3.12 kiem_ve_that.py
"""

from __future__ import annotations

import io
import os
import shutil
import struct
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

GOC = Path(__file__).resolve().parent
sys.path.insert(0, str(GOC))
LOI: list[str] = []


def ktra(ten: str, dieu: bool, mo: str = "") -> None:
    if dieu:
        print(f"  {ten:<58} {mo or 'đạt'}")
    else:
        LOI.append(f"{ten}: {mo}")


def raw_gia(p: Path, mau=(120, 140, 170), w=480, h=320, xoay=1) -> Path:
    """File "RAW" giả: khung TIFF có JPEG nhúng (thẻ 0x0201/0x0202) và thẻ
    hướng xoay 0x0112 — đúng đường at.anh_nho() đi với RAW thật."""
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (w, h), mau)
    ImageDraw.Draw(im).rectangle((0, 0, w // 4, h // 4), fill=(250, 250, 250))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=85)
    j = b.getvalue()
    ent = [(0x0112, 3, 1, xoay), (0x0201, 4, 1, 0), (0x0202, 4, 1, len(j))]
    off = 8 + 2 + len(ent) * 12 + 4 + 16
    ent[1] = (0x0201, 4, 1, off)
    d = bytearray(b"II*\x00" + struct.pack("<I", 8) + struct.pack("<H", len(ent)))
    for tag, typ, cnt, val in ent:
        d += (struct.pack("<HHIHH", tag, typ, cnt, val, 0) if typ == 3
              else struct.pack("<HHII", tag, typ, cnt, val))
    d += struct.pack("<I", 0)
    d += b"\x00" * (off - len(d)) + j + b"\x00" * 4096
    p.write_bytes(bytes(d))
    return p


def kiem_anh_nho(tam: Path) -> None:
    """at.anh_nho + kho ảnh nhỏ trên đĩa — không cần cửa sổ."""
    import autotone as at
    import luoi_anh as la

    ngang = raw_gia(tam / "ngang.ARW", w=600, h=400)
    doc = raw_gia(tam / "doc.ARW", w=600, h=400, xoay=6)
    a = at.anh_nho(str(ngang), 320)
    b = at.anh_nho(str(doc), 320)
    ktra("ảnh nhỏ đọc được từ JPEG nhúng trong RAW",
         a is not None and max(a.size) <= 320 and a.size[0] > a.size[1],
         f"{a.size if a else None}")
    #[[ Anh doc (the 0x0112 = 6) phai xoay dung chieu — luoi anh ma hien anh
    #   nam ngang thi nguoi soat tuong chup sai. ]]
    ktra("ảnh chụp dọc (thẻ xoay 6) hiện đúng chiều dọc",
         b is not None and b.size[1] > b.size[0], f"{b.size if b else None}")

    kho = tam / "kho"
    lan1 = la.doc_anh_nho(str(ngang), kho)
    file_kho = list(kho.glob("*/*.jpg"))
    goc_ham = at.anh_nho
    try:
        at.anh_nho = lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("không được gọi"))
        lan2 = la.doc_anh_nho(str(ngang), kho)
    finally:
        at.anh_nho = goc_ham
    ktra("đọc lần hai lấy từ kho trên đĩa, không mở lại RAW",
         lan1 is not None and len(file_kho) == 1 and lan2 is not None
         and lan2.size == lan1.size, f"{len(file_kho)} file trong kho")
    #[[ Khoa theo duong dan + mtime + co file: file goc bi thay (chep de, sua)
    #   thi KHONG BAO GIO hien anh nho cu cua no. ]]
    k1 = la.khoa_kho(str(ngang))
    st = os.stat(ngang)
    os.utime(ngang, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    k2 = la.khoa_kho(str(ngang))
    ktra("đổi file gốc thì đổi khoá — không hiện ảnh nhỏ cũ", k1 != k2, f"{k1[:8]} → {k2[:8]}")
    for i in range(12):
        f = kho / "zz" / f"{i:020d}.jpg"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x")
        os.utime(f, (1000 + i, 1000 + i))
    xoa = la.don_kho(kho, tran=8)
    con = sorted(p.name for p in (kho / "zz").glob("*.jpg"))
    ktra("kho quá trần thì xoá 1/4 số tấm LÂU KHÔNG DÙNG nhất",
         xoa == 3 and f"{0:020d}.jpg" not in con and f"{11:020d}.jpg" in con,
         f"xoá {xoa} / 13")

    #[[ Ngan xep: tam DAU danh sach dang nhin duoc doc TRUOC (vao sau ra
    #   truoc), tam da cuon qua (khong con muon) thi bo qua. ]]
    bd = la.BoDoc(so_luong=0, kho=kho)
    bd.muon(["a", "b", "c"])
    thu_tu = list(reversed(bd._ngan))
    bd.muon(["x", "y"])
    ktra("đọc ô đang nhìn trước (ngăn xếp)", thu_tu == ["a", "b", "c"]
         and bd._ngan[-1] == "x" and bd._dang_muon == {"x", "y"},
         "cuộn nhanh qua 500 tấm không phải chờ đọc hết")
    bd.dung()


def kiem_luoi(tam: Path) -> None:
    import tkinter as tk
    import giao_dien as gd
    import luoi_anh as la

    root = tk.Tk()
    root.geometry("1000x700+0+0")
    gd.dat_theme(root)
    chon, mo = [], []
    luoi = la.LuoiAnh(root, khi_chon=chon.append, khi_mo=mo.append)
    luoi.pack(fill="both", expand=True)

    def chay(n=6, ngu=0.0):
        for _ in range(n):
            root.update_idletasks()
            root.update()
            if ngu:
                time.sleep(ngu)

    chay()
    ktra("chưa có ảnh thì giữa lưới là lời mời chọn buổi",
         luoi.o_trong.winfo_ismapped() and luoi.nut_trong.winfo_ismapped(),
         luoi.lbl_trong.cget("text").split("\n")[0])

    thu = tam / "buoi"
    thu.mkdir()
    ds = []
    for i in range(300):
        p = thu / f"IMG_{i:04d}.ARW"
        if i < 40:
            raw_gia(p, mau=(40 + i * 5, 90, 150))
        else:
            p.write_bytes(b"khong phai anh")
        ds.append({"path": str(p), "ten": p.name, "dev": (i % 7 - 3) / 10,
                   "canh": 1 + i // 20, "loai": "", "sao1": i == 5,
                   "bo": "thiếu .xmp" if i in (3, 4) else ""})
    luoi.dat_ds(ds)
    chay(10, 0.02)
    c = luoi.canvas

    def so_o():
        return len([t for t in c.find_withtag("o")
                    if c.type(t) == "text" and c.itemcget(t, "text").startswith("IMG_")])

    W = c.winfo_width()
    cot1 = luoi._cot
    ow = luoi._ow
    ktra("có ảnh thì lời mời ẩn đi", not luoi.o_trong.winfo_ismapped()
         or c.itemcget(luoi._cua_trong, "state") == "hidden", "")
    #[[ O GIAN KIN be ngang (nhu Evoto / Lightroom): khong con hai dai trong
    #   hai ben luoi. Sai so cho phep = so cot (chia nguyen). ]]
    du = W - (cot1 * (ow + luoi._khe) + luoi._khe)
    ktra("ô giãn kín bề ngang lưới", 0 <= du <= cot1 + 1 and ow >= luoi.co_o,
         f"{W} px · {cot1} cột × {ow} px · dư {du} px")
    ve = so_o()
    hang_nhin = c.winfo_height() // (luoi._kich_thuoc_o()[1] + luoi._khe) + 2
    ktra("chỉ vẽ ô đang nhìn, không vẽ cả 300 tấm",
         0 < ve <= hang_nhin * cot1, f"{ve} ô vẽ / {len(ds)} tấm")

    root.geometry("1500x700")
    chay(8)
    cot2 = luoi._cot
    root.geometry("520x700")
    chay(8)
    cot3 = luoi._cot
    ktra("rộng thì nhiều cột hơn, hẹp thì ít hơn, không bao giờ 0",
         cot2 > cot1 > cot3 >= 1, f"1500→{cot2} · 1000→{cot1} · 520→{cot3}")
    root.geometry("1000x700")
    chay(8)

    # ---- bấm chọn, phím, bấm đúp
    i = cot1 + 1                    # hàng 2, cột 2
    x, y = luoi._o_xy(i)
    ev = type("E", (), {"x": x + 10, "y": y + 10})()
    luoi._bam(ev)
    ktra("bấm ô nào chọn đúng tấm đó", luoi.dang_chon == ds[i]["path"]
         and chon[-1] == ds[i]["path"], Path(chon[-1]).name if chon else "—")
    luoi._di_phim(0, 1)
    luoi._di_phim(1, 0)
    ktra("phím ↓ xuống một hàng, → sang một tấm",
         luoi.dang_chon == ds[i + cot1 + 1]["path"], Path(luoi.dang_chon or "").name)
    luoi._bam_dup(ev)
    ktra("bấm đúp mở tấm dưới con trỏ", mo == [ds[i]["path"]], Path(mo[-1]).name if mo else "—")

    # ---- cuộn tới cuối: vẽ đúng ô cuối, không vẽ lại cả lưới
    luoi.chon(ds[-1]["path"])
    chay(8)
    ten_ve = {c.itemcget(t, "text") for t in c.find_withtag("o") if c.type(t) == "text"}
    ktra("chọn tấm cuối thì cuộn tới và vẽ được nó",
         any(t.startswith("IMG_0299") for t in ten_ve) and so_o() <= hang_nhin * cot1,
         f"{so_o()} ô đang vẽ")

    # ---- ảnh đọc ở luồng nền, tấm hỏng không làm treo
    luoi.chon(ds[0]["path"])
    t0 = time.time()
    while time.time() - t0 < 8 and len(luoi._anh_pil) < 8:
        chay(1, 0.05)
    ktra("ảnh nhỏ về từ luồng nền", len(luoi._anh_pil) >= 8,
         f"{len(luoi._anh_pil)} ảnh sau {time.time() - t0:.1f} s")
    luoi.chon(ds[60]["path"])
    t0 = time.time()
    while time.time() - t0 < 8 and ds[60]["path"] not in luoi._hong:
        chay(1, 0.05)
    #[[ Tam 60 co the DA doc hong tu luc doc-truoc (hai man duoi) — vong cho
    #   tren thoat ngay ma chua cho luoi ve lai sau khi cuon. Cho ve xong. ]]
    chay(4)
    hong_ve = any(c.type(t) == "text" and "không đọc được" in c.itemcget(t, "text")
                  for t in c.find_withtag("o"))
    ktra("file không đọc được thì ghi rõ, không treo", ds[60]["path"] in luoi._hong
         and hong_ve, "“không đọc được ảnh”")

    # ---- ô SẼ KHÔNG ĐƯỢC GHI: tối đi + nhãn lý do
    luoi.chon(ds[3]["path"])
    t0 = time.time()
    while time.time() - t0 < 8 and ds[3]["path"] not in luoi._anh_pil:
        chay(1, 0.05)
    chay(4)
    nhan = [c.itemcget(t, "text") for t in c.find_withtag("o") if c.type(t) == "text"]
    from PIL import ImageStat, ImageTk
    sang = toi = None
    try:
        w_, h_ = luoi._ow - 4, round(luoi._ow * 2 / 3) - 4
        sang = ImageStat.Stat(ImageTk.getimage(luoi._anh_cho(ds[3]["path"], w_, h_))
                              .convert("L")).mean[0]
        toi = ImageStat.Stat(ImageTk.getimage(luoi._anh_cho(ds[3]["path"], w_, h_, mo=True))
                             .convert("L")).mean[0]
    except Exception as ex:                                  # noqa: BLE001
        print(f"     (không đo được độ sáng ảnh Tk: {ex})")
    ktra("tấm sẽ không được ghi: ảnh tối đi, có nhãn lý do",
         nhan.count("thiếu .xmp") >= 2 and (sang is None or toi < sang * 0.5),
         f"{nhan.count('thiếu .xmp')} nhãn · sáng {sang and round(sang)} → "
         f"{toi and round(toi)}")
    luoi.dat_ds([])
    chay(3)
    ktra("hết ảnh thì lời mời hiện lại",
         c.itemcget(luoi._cua_trong, "state") != "hidden", "")
    root.destroy()


def kiem_dai_anh(tam: Path) -> None:
    """Dải ảnh dưới ảnh lớn (mô-đun Retouch, tối 3/10 — user: "1 ảnh mở to và
    lưới ảnh bên dưới"): khung THẤP thì một hàng cuộn ngang như dải ảnh của
    Evoto / Lightroom; kéo thanh chia cao lên thì thành lưới nhiều hàng. Lưới
    Cân tone (dai=False) thì không bao giờ thành dải."""
    import tkinter as tk
    import giao_dien as gd
    import luoi_anh as la

    root = tk.Tk()
    root.geometry("1000x700+0+0")
    gd.dat_theme(root)
    chon = []
    khung = tk.Frame(root, height=130)
    khung.pack(side="bottom", fill="x")
    khung.pack_propagate(False)
    dai = la.LuoiAnh(khung, khi_chon=chon.append, dai=True)
    dai.pack(fill="both", expand=True)

    def chay(n=6, ngu=0.0):
        for _ in range(n):
            root.update_idletasks()
            root.update()
            if ngu:
                time.sleep(ngu)

    thu = tam / "dai"
    thu.mkdir()
    ds = []
    for i in range(120):
        p = thu / f"D_{i:04d}.ARW"
        if i < 30:
            raw_gia(p, mau=(30 + i * 6, 90, 150))
        else:
            p.write_bytes(b"khong phai anh")
        ds.append({"path": str(p), "ten": p.name, "dev": None, "canh": None, "loai": "",
                   "sao1": False, "bo": "", "dau": "✓ đã làm" if i % 3 == 0 else ""})
    dai.dat_ds(ds)
    chay(10, 0.02)
    c = dai.canvas

    def o_ve():
        return [t for t in c.find_withtag("o")
                if c.type(t) == "rectangle" and c.itemcget(t, "fill") == "#202226"]

    def ten_ve():
        return [c.itemcget(t, "text") for t in c.find_withtag("o")
                if c.type(t) == "text" and c.itemcget(t, "text").startswith("D_")]

    def thay(i):
        x, _y = dai._o_xy(i)
        x0 = c.canvasx(0)
        return x >= x0 - 1 and x + dai._ow <= x0 + c.winfo_width() + 1

    ow, oh = dai._kich_thuoc_o()
    ktra("khung thấp: thành dải MỘT hàng",
         dai.ngang and len({dai._o_xy(i)[1] for i in range(len(ds))}) == 1,
         f"ô {ow}×{oh} · khung cao {c.winfo_height()} px")
    ktra("ô của dải cao gần kín khung", oh >= c.winfo_height() - 2 * dai._khe - 8,
         f"{oh}/{c.winfo_height()} px")
    ktra("dải không có dòng tên dưới ô (tên nằm ở thanh trên ảnh lớn)", not ten_ve())
    vua = c.winfo_width() // (ow + dai._khe) + 2
    ktra("dải chỉ vẽ ô đang nhìn, không vẽ cả 120 tấm",
         0 < len(o_ve()) <= vua, f"{len(o_ve())} ô vẽ")
    nhan = [c.itemcget(t, "text") for t in c.find_withtag("o") if c.type(t) == "text"]
    ktra("nhãn “✓ đã làm” vẫn có trên dải", "✓ đã làm" in nhan)

    i = 3
    x, y = dai._o_xy(i)
    dai._bam(type("E", (), {"x": x - c.canvasx(0) + 8, "y": y + 8})())
    ktra("bấm ô thứ i trên dải chọn đúng tấm đó",
         dai.dang_chon == ds[i]["path"] and chon[-1] == ds[i]["path"],
         Path(chon[-1]).name if chon else "—")
    for _ in range(25):
        dai._di_phim(1, 0)
    chay(3)
    ktra("→ sang từng tấm, dải tự cuộn cho thấy tấm đang chọn",
         dai.dang_chon == ds[28]["path"] and thay(28), Path(dai.dang_chon).name)
    dai._di_phim(0, 1)
    ktra("↓ trên dải là tấm kế (dải không có “hàng dưới”)",
         dai.dang_chon == ds[29]["path"], Path(dai.dang_chon).name)
    x0 = c.canvasx(0)
    c.event_generate("<MouseWheel>", delta=-120, x=40, y=40)
    chay(3)
    ktra("lăn chuột trên dải: cuộn NGANG", c.canvasx(0) > x0 and c.canvasy(0) == 0,
         f"{x0:.0f} → {c.canvasx(0):.0f} px")
    #[[ Luc dang chay, app dem lai 1,5 s mot lan va dat_ds() lai cung danh sach
    #   — khong duoc keo dai ve tam dang chon moi lan nhu the. ]]
    c.xview_moveto(0.6)
    chay(2)
    x_luot = c.canvasx(0)
    dai.dat_ds(list(ds), giu_cuon=True)
    chay(3)
    ktra("đang lướt dải: đếm lại không kéo dải về tấm đang chọn",
         abs(c.canvasx(0) - x_luot) < 1, f"{x_luot:.0f} → {c.canvasx(0):.0f} px")

    khung.configure(height=520)
    chay(10, 0.02)
    ktra("kéo cao: thành lưới nhiều hàng, có tên dưới ô",
         not dai.ngang and 1 < dai._cot < len(ds) and bool(ten_ve()),
         f"{dai._cot} cột")
    khung.configure(height=130)
    chay(10, 0.02)
    ktra("thấp lại: về dải, thấy ngay tấm đang chọn",
         dai.ngang and thay(dai._vi_tri[dai.dang_chon]), Path(dai.dang_chon).name)

    khung2 = tk.Frame(root, height=130)
    khung2.pack(side="top", fill="x")
    khung2.pack_propagate(False)
    luoi2 = la.LuoiAnh(khung2)
    luoi2.pack(fill="both", expand=True)
    luoi2.dat_ds(ds[:10])
    chay(6)
    ktra("lưới Cân tone (dai=False) thấp mấy cũng không thành dải", not luoi2.ngang)
    root.destroy()


def kiem_chon_nhieu(tam: Path) -> None:
    """Dải ảnh Retouch chọn NHIỀU tấm (sáng 4/10 — "Sync All các hiệu ứng đã
    kéo cho các ảnh được chọn"): Ctrl + bấm thêm / bớt, Shift + bấm một dãy,
    Ctrl+A, Esc; tấm ĐANG XEM (tấm nguồn của Sync) không đổi khi Ctrl / Shift.
    Bấm THẬT bằng sự kiện Tk có state (Control = 0x4, Shift = 0x1) — gọi hàm
    thẳng thì không biết rằng buộc phím có ăn hay không."""
    import tkinter as tk
    import giao_dien as gd
    import luoi_anh as la

    root = tk.Tk()
    root.geometry("1000x700+0+0")
    gd.dat_theme(root)
    chon, doi = [], []
    khung = tk.Frame(root, height=130)
    khung.pack(side="bottom", fill="x")
    khung.pack_propagate(False)
    dai = la.LuoiAnh(khung, khi_chon=chon.append, dai=True, chon_nhieu=True,
                     khi_doi_chon=doi.append)
    dai.pack(fill="both", expand=True)

    def chay(n=6):
        for _ in range(n):
            root.update_idletasks()
            root.update()

    thu = tam / "chon_nhieu"
    thu.mkdir()
    ds = []
    for i in range(8):
        p = raw_gia(thu / f"C_{i:02d}.ARW", mau=(40 + 20 * i, 90, 150))
        ds.append({"path": str(p), "ten": p.name, "dev": None, "canh": None, "loai": "",
                   "sao1": False, "bo": "", "dau": "", "rieng": i == 5})
    dai.dat_ds(ds)
    chay(10)
    c = dai.canvas
    gio = [10_000]

    def bam(i, state=0):
        x, y = dai._o_xy(i)
        gio[0] += 1000                  # cách xa nhau: Tk không coi là bấm đúp
        c.event_generate("<Button-1>", x=int(x - c.canvasx(0)) + 10,
                         y=int(y - c.canvasy(0)) + 10, state=state, time=gio[0])
        chay(3)

    def ten():
        return [Path(p).stem for p in dai.ds_chon()]

    P = [o["path"] for o in ds]
    bam(1)
    ktra("bấm thường: chọn đúng một tấm, đó là tấm đang xem",
         dai.ds_chon() == [P[1]] and dai.dang_chon == P[1] and chon[-1:] == [P[1]], str(ten()))
    #[[ 4/10 trua (user: "bam vao 1 anh o duoi luoi anh thi can hien thi ngay
    #   tren khung to"): NumLock bat tren Windows gan bit Mod1 (0x8) vao MOI lan
    #   bam. Tk ngoai Mac doc "<Command-Button-1>" thanh "<Mod1-Button-1>" ->
    #   bam thuong thanh "chon them", tam dang xem dung yen. Mac: 0x8 CHINH LA
    #   Command -> phai la chon them. ]]
    mac = str(root.tk.call("tk", "windowingsystem")) == "aqua"
    bam(3, 0x8)
    if mac:
        ktra("Mac: Cmd + bấm (Mod1) là chọn thêm, tấm đang xem không đổi",
             dai.ds_chon() == [P[1], P[3]] and dai.dang_chon == P[1], str(ten()))
    else:
        ktra("bấm thường khi NumLock bật (bit 0x8): vẫn là bấm thường, sang đúng tấm đó",
             dai.ds_chon() == [P[3]] and dai.dang_chon == P[3] and chon[-1:] == [P[3]],
             str(ten()))
    bam(1)
    n_chon = len(chon)
    bam(3, 0x4)
    bam(6, 0x4)
    ktra("Ctrl + bấm: thêm tấm, tấm đang xem KHÔNG đổi, không báo “chọn tấm khác”",
         dai.ds_chon() == [P[1], P[3], P[6]] and dai.dang_chon == P[1]
         and len(chon) == n_chon, str(ten()))
    ktra("tập chọn đổi thì báo ra (khi_doi_chon)", bool(doi) and doi[-1] == [P[1], P[3], P[6]],
         str([Path(p).stem for p in (doi[-1] if doi else [])]))
    phu = [t for t in c.find_withtag("phu")]
    ktra("tấm đã chọn (không phải tấm đang xem) có viền riêng", len(phu) == 2, f"{len(phu)} viền")
    bam(3, 0x4)
    ktra("Ctrl + bấm tấm đã chọn: bỏ nó ra", dai.ds_chon() == [P[1], P[6]], str(ten()))
    bam(1, 0x4)
    ktra("Ctrl + bấm chính tấm đang xem: bỏ nó, tấm đang xem sang tấm còn lại",
         dai.ds_chon() == [P[6]] and dai.dang_chon == P[6] and chon[-1] == P[6], str(ten()))
    bam(6, 0x4)
    ktra("chỉ còn một tấm: Ctrl + bấm nó không bỏ được (luôn có tấm đang xem)",
         dai.ds_chon() == [P[6]] and dai.dang_chon == P[6], str(ten()))
    bam(2, 0x1)
    ktra("Shift + bấm: chọn cả dãy từ tấm đang xem tới tấm bấm",
         dai.ds_chon() == P[2:7] and dai.dang_chon == P[6], str(ten()))
    c.focus_force()
    chay(2)
    c.event_generate("<Escape>")
    chay(2)
    ktra("Esc: chỉ còn tấm đang xem", dai.ds_chon() == [P[6]], str(ten()))
    c.event_generate("<Control-a>")
    chay(2)
    ktra("Ctrl+A: chọn hết", dai.ds_chon() == P and dai.dang_chon == P[6], f"{len(ten())} tấm")
    dai._di_phim(1, 0)
    chay(2)
    ktra("phím mũi tên: sang tấm kế, thôi chọn nhiều", dai.ds_chon() == [P[7]]
         and dai.dang_chon == P[7], str(ten()))
    bam(4, 0x4)
    dai.chon(P[7], cuon_toi=False)
    ktra("chọn lại tấm đang xem (đếm lại / vẽ lại) không làm mất nhóm đã chọn",
         dai.ds_chon() == [P[4], P[7]], str(ten()))
    dai.dat_ds([o for o in ds if o["path"] != P[4]], giu_cuon=True)
    chay(2)
    ktra("tấm đã chọn biến mất khỏi danh sách: rời khỏi nhóm chọn",
         dai.ds_chon() == [P[7]], str(ten()))
    dai.dat_ds(ds, giu_cuon=True)
    chay(4)
    c.xview_moveto(0)
    chay(4)
    #[[ 7/10 (thiet ke lai): dau "rieng" la CHAM VANG (tag "rieng"), khong con
    #   la nhan chu — dem cham vang, khong dem chu. ]]
    cham = [t for t in c.find_withtag("rieng")
            if c.type(t) == "oval" and c.itemcget(t, "fill") == gd.MAU["nhan"]]
    ktra("ảnh có mức riêng mang chấm vàng trên dải", len(cham) == 1,
         f"{len(cham)} chấm")
    #[[ Luoi Can tone (khong chon_nhieu): Ctrl + bam la bam thuong. ]]
    khung2 = tk.Frame(root, height=300)
    khung2.pack(side="top", fill="x")
    khung2.pack_propagate(False)
    luoi2 = la.LuoiAnh(khung2)
    luoi2.pack(fill="both", expand=True)
    luoi2.dat_ds(ds[:6])
    chay(6)
    c2 = luoi2.canvas
    x, y = luoi2._o_xy(1)
    gio[0] += 1000
    c2.event_generate("<Button-1>", x=int(x) + 10, y=int(y) + 10, time=gio[0])
    x, y = luoi2._o_xy(3)
    gio[0] += 1000
    c2.event_generate("<Button-1>", x=int(x) + 10, y=int(y) + 10, state=0x4, time=gio[0])
    chay(3)
    ktra("lưới không bật chọn nhiều: Ctrl + bấm vẫn chỉ chọn một tấm",
         luoi2.ds_chon() == [ds[3]["path"]] and luoi2.dang_chon == ds[3]["path"],
         str([Path(p).stem for p in luoi2.ds_chon()]))
    root.destroy()


def kiem_dong_bo_app(tam: Path) -> None:
    """Lưới và bảng số trong APP THẬT chọn cùng một tấm, hai chiều."""
    import tkinter as tk
    import autotone_gui as ag
    import giao_dien as gd
    ag.bq.kiem = lambda: {"co_phep": True, "con_lai": timedelta(days=300),
                          "nhac": "", "goi": "1 năm", "may": "TEST01",
                          "het_han": False, "ly_do": ""}
    root = tk.Tk()
    root.geometry("1660x940+0+0")
    gd.dat_theme(root)
    app = ag.App(root)
    app.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    def chay(n=6):
        for _ in range(n):
            root.update_idletasks()
            root.update()

    chay()
    buoi = tam / "dong_bo"
    buoi.mkdir()
    t0 = datetime(2026, 10, 3, 9, 0, 0)
    items = []
    for i in range(14):
        p = raw_gia(buoi / f"A{i:03d}.ARW", mau=(60 + 10 * i, 120, 150))
        dev = [0.0, 0.42, -0.65, 0.9][i % 4]
        items.append(dict(path=str(p), scene=1 + i // 5, dt_obj=t0 + timedelta(seconds=30 * i),
                          delta_ev=dev, new_exposure=dev, new_highlights=-10, new_shadows=5,
                          new_temp=5200, gr_sat=0, clip_after_pct=4.0 if i == 6 else 0.5,
                          shadow_after_pct=0.5, faces_n=1, notes="", scene_size=5,
                          cull="loat" if i == 9 else "", hl_adj=0, sh_adj=0,
                          ngoai_xuat=(i == 11)))
    app.items = items
    app._fill_table()
    app._set_busy(False)
    chay(6)
    ds = app.luoi.ds
    ktra("lưới mang đúng số của bảng (ΔEV, cảnh, 1★, không ghi)",
         len(ds) == 14 and ds[1]["dev"] == 0.42 and ds[6]["loai"] == "clip"
         and ds[9]["sao1"] and ds[11]["bo"] == "không ghi" and ds[0]["canh"] == 1,
         f"{len(ds)} ô")
    i = 7
    x, y = app.luoi._o_xy(i)
    app.luoi._bam(type("E", (), {"x": x + 8, "y": y + 8})())
    chay(2)
    ktra("bấm ô trên lưới → bảng số chọn đúng dòng đó",
         app.tree.selection() == (ds[i]["path"],), Path(ds[i]["path"]).name)
    app.v_xem.set("bang")
    app._doi_xem()
    chay(2)
    app.tree.selection_set(ds[12]["path"])
    chay(3)
    ktra("chọn dòng trong bảng số → lưới chọn đúng tấm đó",
         app.luoi.dang_chon == ds[12]["path"] and app.khung_bang.winfo_ismapped()
         and not app.khung_luoi.winfo_ismapped(), Path(app.luoi.dang_chon or "").name)
    #[[ Sap bang theo cot nao thi luoi theo dung thu tu do — hai cach nhin
    #   cung mot danh sach, khong phai hai danh sach. ]]
    app._sort_by("dev")
    chay(2)
    thu_tu_bang = list(app.tree.get_children())
    ktra("sắp bảng số thì lưới theo đúng thứ tự đó",
         [o["path"] for o in app.luoi.ds] == thu_tu_bang, "ΔEV tăng dần")
    root.destroy()


def main() -> int:
    tam = Path(tempfile.mkdtemp(prefix="ve_that_"))
    os.environ.setdefault("AUTOTONE_DATA", str(tam / "du_lieu"))
    try:
        kiem_anh_nho(tam)
        try:
            import tkinter as tk
            tk.Tk().destroy()
        except Exception as ex:                              # noqa: BLE001
            print(f"  (bỏ qua phần vẽ: không mở được Tk — {ex})")
        else:
            kiem_luoi(tam)
            kiem_dai_anh(tam)
            kiem_chon_nhieu(tam)
            kiem_dong_bo_app(tam)
    finally:
        shutil.rmtree(tam, ignore_errors=True)
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
