"""Mở CẢ ứng dụng thật rồi soi từng chữ xem có bị cắt cụt không.

VÌ SAO FILE NÀY LÀ CÁI ĐÁNG TIN NHẤT TRONG BA FILE KIỂM GIAO DIỆN
    kiem_bo_cuc.py đọc mã nguồn — bắt được "quên nối", "quên chốt".
    kiem_ve_that.py dựng lưới ảnh thật — bắt được logic chia cột, chỉ vẽ ô
    đang nhìn, chọn ô.
    File này dựng ỨNG DỤNG THẬT, đi qua từng trang, rồi hỏi Tk một câu duy
    nhất cho mọi widget có chữ:

        chỗ được cấp < chỗ chữ cần  ->  chữ đang bị cắt

    Đó chính là lỗi đã xảy ra hai lần: "Dua mat ve muc sang ch", "Khuon mat +
    diem bat net (kh". Không đoán theo số ký tự, không ước theo phông — hỏi
    thẳng bộ dựng hình. Nút vẽ tay (gd.NutTron), viên chọn (gd.PhanDoan) và ô
    chọn cũng bị hỏi, vì chữ của chúng không nằm trong một Label.

KHUNG KIỂU EVOTO (tối 3/10)
    Thanh công cụ · lưới ảnh giữa · bảng điều khiển phải · cột mô-đun. Bảng
    điều khiển là MỘT cột cuộn được như Evoto — tuỳ chọn không còn nằm trên
    bảng kết quả, nên "khối tuỳ chọn ăn mất chỗ của bảng" (mục đích của các
    mức cũ) không còn xảy ra được; các mức ở đây đo lại đúng câu hỏi đó trên
    bố cục mới — xem phần "bảng điều khiển phải".

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
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tkinter as tk                                          # noqa: E402
from tkinter import font as tkfont                            # noqa: E402

LOI: list[str] = []


def ktra(ten: str, dieu: bool, mo: str = "") -> None:
    if dieu:
        print(f"  {ten:<56} {mo or 'đạt'}")
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


def o_chon_bi_cat(w):
    """(chữ dài nhất, chỗ có, cần) nếu ô chọn không đủ chỗ cho giá trị DÀI NHẤT
    của nó, None nếu đủ.

    #[[ "Dua mat ve muc sang ch" la chu bi cat TRONG O CHON, khong phai
    #   nhan — ma phep so winfo_width < winfo_reqwidth o duoi khong bat duoc
    #   no: reqwidth cua o chon chi la width ky tu dat san, khong lien quan gi
    #   toi chu ben trong. Nen do thang chu: be ngang chu dai nhat (phong cua
    #   chinh o) so voi phan ruot o = be ngang that tru le/vien/mui ten. Phan
    #   le do lay tu Tk: reqwidth - width * be ngang ky tu "0". ]]
    """
    try:
        if w.winfo_class() != "TCombobox" or not w.winfo_ismapped():
            return None
        f = tkfont.Font(root=w, font=w.cget("font") or "TkTextFont")
        gia_tri = [str(v) for v in w.tk.splitlist(w.cget("values"))]
        if not gia_tri:
            return None
        tran = w.winfo_reqwidth() - int(w.cget("width")) * f.measure("0")
        co = w.winfo_width() - tran
        dai = max(gia_tri, key=f.measure)
        can = f.measure(dai)
        return (dai, co, can) if co < can - 1 else None
    except (tk.TclError, ValueError):
        return None


def ve_tay_bi_cat(w, gd):
    """(chữ, chỗ có, cần) nếu một nút vẽ tay / viên chọn hẹp hơn chữ của nó.

    #[[ NutTron va PhanDoan la Canvas: winfo_reqwidth la be ngang DAT, khong
    #   phai be ngang chu — nen phai hoi chinh no "chu cua mi can bao nhieu"
    #   (rong_chu / rong_can), roi so voi be ngang THAT dang duoc cap. ]]
    """
    try:
        if not w.winfo_ismapped():
            return None
        if isinstance(w, gd.NutTron):
            can = w.rong_chu()
            if w.winfo_width() < can - 1:
                return (str(w.cget("text")) or "(nút biểu tượng)", w.winfo_width(), can)
        elif isinstance(w, gd.PhanDoan):
            can = w.rong_can()
            if w.winfo_width() < can - 1:
                return ("viên chọn " + " | ".join(t for _g, t in w._ds),
                        w.winfo_width(), can)
    except (tk.TclError, AttributeError):
        return None
    return None


def main() -> int:
    import autotone_gui as ag
    import giao_dien as gd

    #[[ Lop phu ban quyen che mat giao dien — bai nay kiem giao dien, khong
    #   kiem ban quyen (da co kiem_ban_quyen rieng). ]]
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
    ktra("ứng dụng dựng lên được", True, "không nổ lúc khởi tạo")

    # ---- tiêu đề trang: không số giả
    #[[ Loi that da xay ra: ray ghi "4 Export", tieu de ghi "Khau 5 - Export".
    #   Cot trai da bo; trang PHU chi con nut ← + TEN trang. Mot "Khau 4 ·" tren
    #   tieu de bay gio la so ma: khong con cho nao danh so cho no khop. Trang
    #   chinh khong co tieu de chu — no co dong [Luoi anh | Bang so]. ]]
    lech = []
    for ma, ten in ag.KHAU:
        app._chon_khau(ma)
        root.update_idletasks()
        if ma in ("nap", "phan_tich"):
            if app.khau_dang != "phan_tich" or not app.dau_chinh.winfo_ismapped():
                lech.append(f"{ma}: không về trang chính")
            continue
        if ma == "retouch":
            #[[ Retouch la MO-DUN (toi 3/10): dau trang rieng [Luoi anh | Nhat
            #   ky] nam trong khung cua no; dong dau trang phu cua app phai an,
            #   khong thi hai dong dau chong nhau. ]]
            w = getattr(app, "_retouch_win", None)
            if app.dau_trang.winfo_ismapped() or (
                    w is not None and not w.chon_xem.winfo_ismapped()):
                lech.append("retouch: đầu trang mô-đun lẫn với đầu trang phụ")
            continue
        tieu_de = app.lbl_khau.cget("text")
        if tieu_de != ten or not app.dau_phu.winfo_ismapped():
            lech.append(f"{ma}: tiêu đề “{tieu_de}”")
    ktra("tiêu đề trang phụ là đúng tên trang, không số", not lech,
         " | ".join(lech) if lech else f"{len(ag.KHAU)} trang")

    # ---- không chữ nào bị cắt, trang nào cũng vậy
    #[[ Trang chinh soi HAI LAN: dong het nhom (dong tom tat — thu nguoi dung
    #   thay dau tien) va mo het nhom (o chon / thanh truot / vien chon ben
    #   trong — chu bi cat trong nhom dong la chu bi cat ngay khi mo ra). ]]
    tat_ca_cat = {}
    luot = []
    for ma, ten in ag.KHAU:
        if ma == "nap":
            continue
        if ma == "phan_tich":
            luot += [(ma, "Trang chính (đóng nhóm)", False),
                     (ma, "Trang chính (mở nhóm)", True)]
        else:
            luot.append((ma, ten, True))
    nhan_gon = []
    #[[ Cau that dai cho thanh trang thai va dong lan gui — de phep kiem "cat
    #   thi phai co cau du" o duoi co cai de kiem, khong dat suong. ]]
    app.status("Đang đo 1400 ảnh · " + "câu rất dài " * 60 + "· HẾT")
    app.lbl_job.configure(text="✓ Lần gửi gần nhất · " + "job rất dài " * 60)
    for ma, ten, mo_nhom in luot:
        for n in app._nhom_tuy_chon.values():
            (n.mo if mo_nhom else n.dong)()
        app._chon_khau(ma)
        chay()
        ds = []
        di_khap(app, ds)
        cat = []
        for w in ds:
            if isinstance(w, gd.NhanGon):
                nhan_gon.append(w)
                continue                # cắt "…" là CHỦ Ý — xem phần dưới
            oc = o_chon_bi_cat(w) or ve_tay_bi_cat(w, gd)
            if oc:
                cat.append(((str(oc[0]))[:46], oc[1], oc[2]))
                continue
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
            tat_ca_cat[ten] = cat
        ktra(f"“{ten}” không có chữ nào bị cắt", not cat,
             f"{len(ds)} widget" if not cat else f"{len(cat)} chỗ bị cắt")
    if tat_ca_cat:
        print()
        for ma, cat in tat_ca_cat.items():
            for chu, co, can in cat[:5]:
                print(f"     [{ma}] “{chu}” — chỗ có {co} px, cần {can} px")
        print()
    #[[ NhanGon (thanh trang thai, dong lan gui) CO Y cat "…" de giu MOT dong.
    #   Dieu kien de cat duoc: cau du phai nam trong cho re chuot. Cat ma khong
    #   co cau du thi la mat chu that. ]]
    gon = set(nhan_gon)
    bi_cat = [w for w in gon if w.dang_cat()]
    #  7/10: nhãn có chú thích RIÊNG (dat_goi_y — vd. dòng gửi Lightroom kèm
    #  chi tiết) thì chú thích phải CHỨA câu đủ, không cần bằng hẳn
    mat = [w for w in bi_cat if " ".join(w.cget("text").split())
           not in " ".join(w.goi_y.chu.split())]
    ktra("nhãn một dòng bị cắt thì rê chuột hiện câu đủ",
         len(bi_cat) >= 2 and not mat,
         f"{len(gon)} nhãn một dòng · {len(bi_cat)} đang cắt “…”")
    app.status("")
    app.refresh_job_state()

    # ---- bảng điều khiển phải
    #[[ CAU HOI CU, BO CUC MOI.
    #
    #   Truoc toi 3/10 tuy chon nam TREN bang ket qua; muc cu ("o cua so >=1200
    #   px cao, mo het nhom, khong phai cuon") canh hai chuyen: khoi tuy chon
    #   khong an mat cho cua bang anh, va khong phai cuon ca trang moi toi nut
    #   chinh (3/9 nut "1 · Phan tich" tung bi day khoi mep duoi).
    #
    #   Bo cuc Evoto tach tuy chon ra MOT COT RIENG ben phai, nut chinh len
    #   thanh cong cu: hai chuyen do khong con xay ra duoc nua (kiem ngay duoi:
    #   luoi anh cao het vung giua). Cot rieng thi cuon rieng nhu Evoto. Nen do
    #   lai dung cau hoi tren bo cuc moi:
    #     · DONG HET (mac dinh luc mo app): vua, khong cuon — o MOI co tu nho
    #       nhat cho phep (1180x680) tro len.
    #     · MOT nhom mo (cach dung thuong ngay), ke ca nhom cao nhat: vua o moi
    #       cua so >= 1200 px cao — dung muc 1200 cu.
    #     · MO HET: vua o co that cua nguoi dung (man 2460x1440 -> cua so
    #       ~2400x1380, dung con so cua muc cu). Cua so 1900x1200 mo het thi in
    #       ra so px phai cuon, de biet chu khong bao hong.
    #   Va bang KHONG DOI be ngang khi mo / dong nhom — doi la luoi anh nhay cot.
    #]]
    nhom = app._nhom_tuy_chon
    cu = app.cuon_phai

    def do_tai(w, h, mo):
        root.geometry(f"{w}x{h}")
        app._chon_khau("phan_tich")
        for k, n in nhom.items():
            (n.mo if (mo is True or k == mo) else n.dong)()
        chay(8)
        return (cu.trong.winfo_reqheight(), cu.canvas.winfo_height(),
                app.ben_phai.winfo_width(), app.giua.winfo_width(), app.luoi._cot,
                app.luoi.winfo_height())

    print()
    co = ((1180, 680), (1660, 940), (1900, 1200), (2400, 1380))
    dong = {kt: do_tai(*kt, False) for kt in co}
    mo_het = {kt: do_tai(*kt, True) for kt in co}
    cao_nhat = max(nhom, key=lambda k: (do_tai(1900, 1200, k)[0]))
    mot = {kt: do_tai(*kt, cao_nhat) for kt in co if kt[1] >= 1200}
    for nhan, bo in (("đóng hết", dong), ("mở hết", mo_het),
                     (f"chỉ mở “{nhom[cao_nhat].tieu_de}”", mot)):
        for (w, h), (can, o, rb, rg, cot, _hl) in bo.items():
            tt = "vừa" if can <= o + 2 else f"phải cuộn {can - o} px"
            print(f"     [{nhan}] {w}x{h}: bảng {can} px · ô nhìn {o} px · rộng "
                  f"{rb} px · lưới {rg} px / {cot} cột — {tt}")
    print()
    ktra("đóng hết nhóm: bảng điều khiển vừa, không cuộn, ở mọi cỡ",
         all(can <= o + 2 for can, o, *_x in dong.values()), "kể cả 1180x680")
    ktra("một nhóm mở (nhóm cao nhất): vừa ở mọi cửa sổ ≥1200 px cao",
         bool(mot) and all(can <= o + 2 for can, o, *_x in mot.values()),
         f"nhóm “{nhom[cao_nhat].tieu_de}”")
    that = mo_het[(2400, 1380)]
    ktra("mở hết nhóm: vừa ở cỡ thật của người dùng (2400x1380)",
         that[0] <= that[1] + 2, f"{that[0]} px nội dung / {that[1]} px ô nhìn")
    rong = {rb for bo in (dong, mo_het, mot) for _c, _o, rb, *_x in bo.values()}
    ktra("bề ngang bảng điều khiển không đổi khi mở / đóng nhóm, đổi cỡ cửa sổ",
         len(rong) == 1, f"{sorted(rong)} px")
    #[[ Luoi anh la thu chinh cua man hinh: cao het vung giua (khong con khoi
    #   tuy chon nao chen tren no), va rong it nhat 55% cua so o 1660. ]]
    w1660 = dong[(1660, 940)]
    ktra("lưới ảnh chiếm phần lớn màn hình",
         w1660[3] >= 0.55 * 1660 and all(b[4] >= 3 for b in dong.values())
         and all(b[5] >= h - 250 for (_w, h), b in dong.items()),
         f"1660 px → lưới {w1660[3]} px · 1180 px → {dong[(1180, 680)][4]} cột")
    root.geometry("1660x940")
    for n in nhom.values():
        n.dong()
    chay(4)

    # ---- Tổng quan vẫn dựng đủ tám thẻ (chỉ không còn lối vào)
    app._chon_khau("tong_quan")
    chay()
    the = getattr(app, "_the_tq", {})
    ktra("Tổng quan dựng đủ tám thẻ", len(the) == 8, f"{len(the)} thẻ")
    ktra("thẻ nào cũng có chữ trạng thái",
         all(o["l_tt"].cget("text") for o in the.values()), "không thẻ nào trống trơn")
    #[[ Bam vao the phai NHAY duoc sang khau do. Day la ly do the ton tai. ]]
    truoc = app.khung_ngoai["day"].winfo_ismapped()
    the["day"]["l_ten"].event_generate("<Button-1>")
    chay(4)
    ktra("bấm thẻ nhảy được sang trang tương ứng",
         app.khung_ngoai["day"].winfo_ismapped() and not truoc,
         "trang Duyệt nhanh & Lightroom hiện lên")

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
