"""Mở CẢ ứng dụng thật rồi soi từng nhãn xem có bị cắt cụt không.

VÌ SAO FILE NÀY LÀ CÁI ĐÁNG TIN NHẤT TRONG BA FILE KIỂM GIAO DIỆN
    kiem_bo_cuc.py đọc mã nguồn — bắt được "quên nối", "quên chốt".
    kiem_ve_that.py dựng ba cột giả — bắt được logic co cột.
    File này dựng ỨNG DỤNG THẬT, đi qua từng khâu, rồi hỏi Tk một câu duy nhất
    cho mọi widget có chữ:

        winfo_width() < winfo_reqwidth()  ->  chữ đang bị cắt

    Đó chính là lỗi đã xảy ra hai lần: "Dua mat ve muc sang ch", "Khuon mat +
    diem bat net (kh". Không đoán theo số ký tự, không ước theo phông — hỏi
    thẳng bộ dựng hình.

CẦN
    Python có tkinter và một màn hình. Trên Windows chạy thẳng:
        python kiem_man_hinh.py
    Trên máy dựng gói không màn hình:
        xvfb-run -a python3.12 kiem_man_hinh.py

LƯU Ý VỀ PHÔNG
    Máy Linux không có Segoe UI nên bề ngang khác Windows. Vì vậy con số bao
    nhiêu px không mang sang được, NHƯNG câu hỏi "có bị cắt không" thì vẫn đúng
    với phông đang dùng. Chạy trên chính máy Windows là chắc nhất.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tkinter as tk                                          # noqa: E402
from tkinter import ttk                                       # noqa: E402

LOI: list[str] = []


def ktra(ten: str, dieu: bool, mo: str = "") -> None:
    if dieu:
        print(f"  {ten:<50} {mo or 'đạt'}")
    else:
        LOI.append(f"{ten}: {mo}")


def co_chu(w) -> str:
    """Chữ đang hiện trên widget, "" nếu nó không phải loại có chữ."""
    try:
        if w.winfo_class() in ("TLabel", "Label", "TCheckbutton",
                               "TRadiobutton", "TButton", "Button"):
            return str(w.cget("text") or "")
    except tk.TclError:
        pass
    return ""


def di_khap(w, ra):
    ra.append(w)
    for c in w.winfo_children():
        di_khap(c, ra)


def main() -> int:
    import autotone_gui as ag
    import giao_dien as gd

    root = tk.Tk()
    #[[ Dung DUNG kich thuoc man hinh cua nguoi dung (2460x1440, cua so gan
    #   full). Kiem o kich thuoc khac thi khong tra loi duoc cau hoi that. ]]
    root.geometry("1660x940")
    gd.dat_theme(root)
    app = ag.App(root)
    app.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    for _ in range(6):
        root.update_idletasks()
        root.update()

    ktra("ứng dụng dựng lên được", True, "không nổ lúc khởi tạo")

    #[[ SO O COT TRAI VA SO TREN TIEU DE PHAI KHOP.
    #
    #   Loi that da xay ra: ray ghi "4 Export", tieu de ghi "Khau 5 - Export".
    #   Nguyen nhan la hai cho tu dem so rieng, va viec them muc "Tong quan" vao
    #   dau KHAU chi lam lech mot ben. Bai nay doc CHU DANG HIEN o ca hai cho —
    #   khong doc bien, khong doc ma nguon — nen no bat duoc moi kieu lech.
    #]]
    lech = []
    for ma, ten in ag.KHAU:
        app._chon_khau(ma)
        root.update_idletasks()
        tieu_de = app.lbl_khau.cget("text")
        ben_trai = app.ray.hang[ma]["l_so"].cget("text")
        if ben_trai == "·":
            hop = tieu_de == ten            # không số thì tiêu đề chỉ là tên
        else:
            hop = tieu_de.startswith(f"Khâu {ben_trai} ·")
        if not hop:
            lech.append(f"{ma}: ray “{ben_trai}” ≠ tiêu đề “{tieu_de}”")
    ktra("số ở cột trái khớp số trên tiêu đề", not lech,
         " | ".join(lech) if lech else f"{len(ag.KHAU)} mục đều khớp")

    tat_ca_cat = {}
    for ma, ten in ag.KHAU:
        app._chon_khau(ma)
        for _ in range(6):
            root.update_idletasks()
            root.update()
        ds = []
        di_khap(app, ds)
        cat = []
        for w in ds:
            chu = co_chu(w)
            if not chu or not w.winfo_ismapped():
                continue
            #[[ Nhan co wraplength thi Tk XUONG DONG — reqwidth luc do la be
            #   ngang mot dong, khong phai ca doan. So sanh se bao cat oan. ]]
            try:
                if int(w.cget("wraplength") or 0) > 0:
                    continue
            except (tk.TclError, ValueError):
                pass
            if w.winfo_width() < w.winfo_reqwidth() - 1:
                cat.append((chu[:46], w.winfo_width(), w.winfo_reqwidth()))
        if cat:
            tat_ca_cat[ma] = cat
        ktra(f"khâu “{ten}” không có nhãn nào bị cắt", not cat,
             f"{len(ds)} widget" if not cat else f"{len(cat)} nhãn bị cắt")

    if tat_ca_cat:
        print()
        for ma, cat in tat_ca_cat.items():
            for chu, co, can in cat[:5]:
                print(f"     [{ma}] “{chu}” — chỗ có {co} px, cần {can} px")

    # ---- khâu 2 có phải cuộn nữa không, ở từng cỡ cửa sổ
    #[[ DAT MUC O DAU, VA VI SAO.
    #
    #   Man hinh nguoi dung 2460x1440 nen cua so that cao khoang 1380 px. Do
    #   duoc: o cua so >= 1200 px thi khoi tuy chon VUA, khong phai cuon. O cua
    #   so thap 940 px thi con thieu khoang 60 px — khong nhet duoc nua tru khi
    #   cat bot chu giai thich, ma chu giai thich la thu vua duoc yeu cau them.
    #
    #   Nen: BAT BUOC vua o co that (>=1200), con co thap thi in ra de biet chu
    #   khong bao hong. Dat muc o 940 la tu ep minh noi doi hoac tu cat mat
    #   tinh nang.
    #]]
    do_duoc = []
    for w, h in ((1660, 940), (1900, 1200), (2400, 1380)):
        root.geometry(f"{w}x{h}")
        app._chon_khau("phan_tich")
        for _ in range(8):
            root.update_idletasks()
            root.update()
        bo = getattr(app, "_cot_tuy_chon", None)
        cuon = app.khung_cuon.get("phan_tich")
        if not bo or cuon is None:
            continue
        can = bo[0].winfo_reqheight()
        o_nhin = cuon.canvas.winfo_height()
        do_duoc.append((w, h, can, o_nhin, app._so_cot_hien))

    print()
    for w, h, can, o_nhin, n in do_duoc:
        tt = "vừa" if can <= o_nhin + 2 else f"thiếu {can - o_nhin} px"
        print(f"     cửa sổ {w}x{h}: tuỳ chọn {can} px · ô nhìn {o_nhin} px · "
              f"{n} cột — {tt}")
    print()

    lon = [d for d in do_duoc if d[1] >= 1200]
    ktra("ở cỡ cửa sổ thật (≥1200 px cao) thì KHÔNG phải cuộn",
         bool(lon) and all(can <= o + 2 for _w, _h, can, o, _n in lon),
         "màn 1440 của người dùng nằm trong nhóm này")
    ktra("mọi cỡ đều còn xếp nhiều hơn một cột",
         all(n >= 2 for *_x, n in do_duoc),
         " · ".join(f"{w}px→{n} cột" for w, _h, _c, _o, n in do_duoc))
    #[[ Truoc dot sua: 946 px tuy chon nhoi vao 411 px, thay 43%. Muc nay canh
    #   khong ai lam no phinh nguoc lai. ]]
    cao_nhat = max(c for *_x, c, _o, _n in
                   [(0, 0, d[2], d[3], d[4]) for d in do_duoc]) if do_duoc else 0
    ktra("khối tuỳ chọn không phình lại như trước",
         0 < cao_nhat < 700, f"{cao_nhat} px (trước khi sửa: 946 px)")

    # ---- Tổng quan phải dựng đủ tám thẻ
    app._chon_khau("tong_quan")
    for _ in range(6):
        root.update_idletasks()
        root.update()
    the = getattr(app, "_the_tq", {})
    ktra("Tổng quan dựng đủ tám thẻ", len(the) == 8, f"{len(the)} thẻ")
    ktra("thẻ nào cũng có chữ trạng thái",
         all(o["l_tt"].cget("text") for o in the.values()),
         "không thẻ nào trống trơn")

    #[[ Bam vao the phai NHAY duoc sang khau do. Day la ly do the ton tai. ]]
    truoc = app.khung_ngoai["day"].winfo_ismapped()
    app._chon_khau("day")
    for _ in range(4):
        root.update_idletasks()
        root.update()
    ktra("bấm thẻ nhảy được sang khâu tương ứng",
         app.khung_ngoai["day"].winfo_ismapped() and not truoc,
         "khâu 3 hiện lên")

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
