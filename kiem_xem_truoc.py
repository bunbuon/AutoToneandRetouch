#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kiem_xem_truoc.py — Kiểm xem trước retouch với ToolCloneEvoto THẬT.

Từ tối 3/10 xem trước không còn là cửa sổ riêng: nó tính ngay trên ẢNH LỚN của
mô-đun Retouch (xem_truoc.MayXem + khung_anh.KhungAnh). Bài này chạy cả hai
với tool thật: tiến trình con nạp được mô hình, mở ảnh có mặt, tính ra ảnh khác
ảnh gốc, mặt tìm được thì "Vào mặt" nhảy tới, phóng to là ảnh TO RA, và KÉO
THANH trong app (sáng 4/10 đã bỏ nút "Xem trước") thì ảnh lớn thành bản tính
bằng tool.

Cần ToolCloneEvoto và một ảnh CÓ KHUÔN MẶT. Không có thì bỏ qua, không báo
hỏng: bài kiểm bị bỏ qua rõ ràng vẫn hơn một bài kiểm luôn "đạt" giả.

    python kiem_xem_truoc.py
    AUTOTONE_TOOL_THU=<thư mục tool> AUTOTONE_ANH_THU=<ảnh> python kiem_xem_truoc.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import tkinter as tk
from pathlib import Path

GOC = Path(__file__).resolve().parent
sys.path.insert(0, str(GOC))

#[[ Anh thu PHAI co mat to (>= ~150 px o ban 1400 px): saytool bo qua mat nho hon
#   nguong (buoc_min_da.MIN_MAT = 100 px, theo Evoto) — SAY-Media-08865 (3 mat
#   100-120 px) tu 7/10 chi doi 0,3 % diem anh, bai "anh KHAC anh goc" hong oan.
#   Duoc dua duong dan anh khac o tham so dong lenh. ]]
import sys as _sys
_UNG = [r"F:\Sản Phẩm Final\Tháng 9 2026\Look\Chon anh\SAY00551.jpeg",
        r"G:\TestRetouchFinal\SAY-Media-08865.jpg"]
ANH_THU = (_sys.argv[1] if len(_sys.argv) > 1 else
           next((a for a in _UNG if __import__("os").path.isfile(a)), _UNG[-1]))
dat = hong = 0


def ket(t, ok, ghi=""):
    global dat, hong
    if ok:
        dat += 1
        print(f"  [DAT ] {t}  {str(ghi)[:90]}")
    else:
        hong += 1
        print(f"  [!] [HONG] {t}  {str(ghi)[:150]}")


def main() -> int:
    for _l in (sys.stdout, sys.stderr):
        try:
            _l.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass

    import retouch as rt
    tool = os.environ.get("AUTOTONE_TOOL_THU") or rt.tim_tool()
    if not tool or not rt.hop_le(tool):
        print("  (bỏ qua: chưa có ToolCloneEvoto)")
        return 0
    anh = os.environ.get("AUTOTONE_ANH_THU") or ANH_THU
    if not Path(anh).is_file():
        print(f"  (bỏ qua: chưa có ảnh thử {anh})")
        return 0
    tool = str(tool)

    import xem_truoc

    # ------------------------------------------------ 1. tiến trình con, tool thật
    may = xem_truoc.MayXem(rt, tool)
    loi = may.bat_dau("auto")
    ket("khởi động được tiến trình xem trước", not loi, loi)
    if loi:
        print(f"\n  {dat} đạt / {hong} hỏng")
        return 1

    hang: list = []                      # tin đã nhận mà chưa ai lấy

    def cho(loai, giay, dk=lambda d: True):
        het = time.time() + giay
        while time.time() < het:
            hang.extend(may.lay())
            for i, d in enumerate(hang):
                if (d.get("loai") == loai and dk(d)) or d.get("loai") in ("hong", "chet"):
                    del hang[i]
                    return d
            time.sleep(0.1)
        return None

    d = cho("san_sang", 180)
    keo = (d or {}).get("keo") or []
    ket("nạp xong mô hình, có thanh kéo của saytool (≥ 5 bước)",
        d is not None and d.get("loai") == "san_sang" and len(keo) >= 5,
        (d or {}).get("loi") or [k["ten"] for k in keo])
    may.gui(viec="mo_anh", fp=anh)
    d = cho("da_mo", 120, lambda x: x.get("fp") == anh)
    ok_mo = d is not None and d.get("loai") == "da_mo"
    goc = xem_truoc.giai_anh(d.get("goc", "")) if ok_mo else None
    ket("mở được ảnh, trả về ảnh gốc 1400 px và đúng tên ảnh",
        goc is not None and max(goc.size) <= 1400 and d.get("fp") == anh,
        goc.size if goc is not None else (d or {}).get("loi"))
    mat = (d or {}).get("mat") or []
    ket("tìm được khuôn mặt (mặt TO trước)",
        len(mat) >= 1 and all(mat[i][2] >= mat[i + 1][2] for i in range(len(mat) - 1)),
        f"{len(mat)} mặt")
    ten = [k["ten"] for k in keo if k["ten"] in ("vet", "min_da")] or \
          [k["ten"] for k in keo if k["ten"] != "chan"][:1]
    muc = {t: 100.0 for t in ten}
    may.gui(viec="tinh", ma=1, fp=anh, muc=muc)
    d = cho("ket_qua", 120, lambda x: x.get("ma") == 1)
    sau = xem_truoc.giai_anh(d.get("anh", "")) if d and d.get("loai") == "ket_qua" else None
    khac = None
    if sau is not None and goc is not None and sau.size == goc.size:
        from PIL import ImageChops, ImageStat
        #[[ Do TRONG O MAT TO NHAT: lam min da / xoa khuyet diem chi cham vao mat
        #   (mat 164 px tren anh 1400 px: trong mat lech ~0,5, ca anh chi 0,016 —
        #   do ca anh thi bai nay hong du tool lam dung). Khong co mat: do ca anh. ]]
        hop = None
        if mat:
            x, y, w, h = [int(v) for v in mat[0][:4]]
            hop = (max(0, x), max(0, y), min(goc.size[0], x + w), min(goc.size[1], y + h))
        lech = ImageChops.difference(sau, goc)
        if hop and hop[2] > hop[0] and hop[3] > hop[1]:
            lech = lech.crop(hop)
        khac = sum(ImageStat.Stat(lech).mean) / 3
    ket("tính ra ảnh KHÁC ảnh gốc (đo trong ô mặt), đúng số thứ tự và tên ảnh",
        khac is not None and khac > 0.2 and d.get("fp") == anh,
        f"lệch trung bình {khac:.2f}" if khac is not None else (d or {}).get("loi"))
    may.gui(viec="tinh", ma=2, fp=anh, muc=muc)
    may.gui(viec="tinh", ma=3, fp="khac.jpg", muc=muc)
    d2 = cho("ket_qua", 120, lambda x: x.get("ma") == 2)
    d3 = cho("hong", 60, lambda x: x.get("ma") == 3)
    ket("tin về mang số thứ tự để bỏ kết quả cũ; xin tính ảnh chưa mở thì báo",
        d2 is not None and d2.get("ma") == 2 and d3 is not None
        and d3.get("loai") == "hong" and d3.get("ma") == 3,
        (d3 or {}).get("loi"))

    # ------------------------------------------------ 2. khung ảnh với ảnh thật
    import giao_dien as gd
    import khung_anh as ka

    goc_tk = tk.Tk()
    goc_tk.geometry("1100x760+0+0")
    gd.dat_theme(goc_tk)
    k = ka.KhungAnh(goc_tk)
    k.pack(fill="both", expand=True)

    def chay(n=4):
        for _ in range(n):
            goc_tk.update_idletasks()
            goc_tk.update()

    chay(6)
    if sau is not None:
        k.dat_anh(sau, truoc=goc, mat=mat)
        chay(3)
        s_vua = k.ty_le()
        ket("Vào mặt: nhảy tới mặt to nhất, phóng to hơn vừa khung",
            k.vao_mat() and k.ty_le() > s_vua, f"{s_vua * 100:.0f}% → {k.ty_le() * 100:.0f}%")
        k.dat_ty_le(2.0)
        k._nhanh_toi = 0
        k.ve_ngay()
        x0, y0, w, h = k.vung_ve
        W, H = k._kt()
        ket("200%: ảnh phủ kín khung (to ra, không bé đi như zoom cũ)",
            w >= W - 2 and h >= H - 2, f"{w}×{h} trong khung {W}×{H}")
        k.giu_goc(True)
        ket("giữ xem gốc: cùng chỗ đang soi", k.hien_truoc and k.ty_le() == 2.0)
        k.giu_goc(False)
    may.dong()
    time.sleep(0.5)
    ket("đóng được tiến trình con", not may.song())
    goc_tk.destroy()

    # ------------------------------------------------ 3. trong app: ảnh lớn
    os.environ["AUTOTONE_DATA"] = tempfile.mkdtemp()
    import autotone_gui as ag
    root = tk.Tk()
    root.geometry("1500x900+0+0")
    gd.dat_theme(root)
    app = ag.App(root)
    app.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    app._chon_khau("retouch")
    for _ in range(8):
        root.update_idletasks()
        root.update()
    rw = app._retouch_win
    rw.v_goc.set(tool)
    rw.v_ra.set(str(Path(tempfile.mkdtemp()) / "ra"))
    rw.v_vao.set(str(Path(anh).parent))
    rw._dem()
    het = time.time() + 10
    while time.time() < het and not rw.luoi.ds:
        root.update()
        time.sleep(0.05)
    if rw.luoi.dang_chon != anh:
        rw.luoi.chon(anh)
        rw._chon_anh(anh)
    #[[ Sang 4/10: KHONG con nut "Xem trước" — keo thanh la anh lon tinh lai
    #   (user: "khi keo se load luon vao anh de thay dc luon"). ]]
    for t in ten:
        if t in rw.v_muc:
            rw.v_muc[t].set(100)
    het = time.time() + 240
    while time.time() < het:
        root.update()
        time.sleep(0.05)
        chu = rw.chip_anh.cget("text")
        if ("Xem trước · " in chu and ("mức riêng" in chu or "mức chung" in chu)) \
                or "lỗi" in chu or "dừng" in chu:
            break
    chu = rw.chip_anh.cget("text")
    ket("kéo thanh trong app (không còn nút Xem trước): ảnh lớn thành bản tính bằng tool",
        rw._xem_dang_hien and ("mức riêng" in chu or "mức chung" in chu)
        and max(rw.xem.kich_thuoc() or (0, 0)) <= 1400, chu)
    p = rw._may_xem.proc if rw._may_xem is not None else None
    rw._tat_xem_truoc(dong_may=True)
    time.sleep(0.5)
    ket("tắt xem trước: đóng tiến trình con, ảnh lớn về bản trên đĩa",
        (p is None or p.poll() is not None) and not rw._xem_dang_hien)
    root.destroy()

    print(f"\n  {dat} đạt / {hong} hỏng")
    return 1 if hong else 0


if __name__ == "__main__":
    sys.exit(main())
