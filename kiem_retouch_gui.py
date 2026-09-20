"""Dựng THẬT cửa sổ Retouch bằng Tk rồi kiểm hai chỗ vừa hỏng ngoài đời.

HAI CHỖ ĐÓ
    1. Bảng thanh kéo. Máy có saytool 0.9.5 (sáu thanh kéo) mà app hiện đúng ba
       — ba cái trong bảng dự phòng viết cứng. Không một dòng nào nói vì sao,
       nên nhìn từ phía người dùng thì app "bình thường", chỉ là thiếu ba tính
       năng mới. Bài này canh: dùng bảng dự phòng thì PHẢI có dòng nói ra.
    2. Ô "Vào" không đi theo thư mục Export ở khâu 5. Đổi thư mục Export xong
       vẫn phải vào sửa tay lần nữa; quên thì retouch chạy trên thư mục của
       BUỔI TRƯỚC mà không báo gì.

VÌ SAO DỰNG TK THẬT CHỨ KHÔNG ĐỌC MÃ
    Cả hai đều là chuyện "cái gì HIỆN RA trên màn hình". Đọc mã chỉ chứng minh
    được có viết hàm, không chứng minh được nó có chạy và có hiện.

Chạy:  xvfb-run -a python3.12 kiem_retouch_gui.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

GOC = Path(__file__).resolve().parent
sys.path.insert(0, str(GOC))

import tkinter as tk                                          # noqa: E402
from tkinter import ttk                                       # noqa: E402

LOI: list[str] = []


def ktra(ten: str, dieu: bool, mo: str = "") -> None:
    if dieu:
        print(f"  {ten:<56} {mo or 'đạt'}")
    else:
        LOI.append(f"{ten}: {mo}")


def main() -> int:
    tmp = tempfile.mkdtemp()
    os.environ["AUTOTONE_DATA"] = tmp
    import autotone_gui as ag
    import giao_dien as gd
    import retouch as rt

    root = tk.Tk()
    root.geometry("1660x940")
    gd.dat_theme(root)
    app = ag.App(root)
    app.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    app._chon_khau("retouch")
    for _ in range(8):
        root.update_idletasks()
        root.update()

    w = getattr(app, "_retouch_win", None)
    ktra("cửa sổ Retouch dựng lên được", w is not None)
    if w is None:
        root.destroy()
        return 1

    # ---------------------------------------------- 1. bảng thanh kéo dự phòng
    #[[ Khong co tool that o may nay -> chac chan dang dung bang du phong.
    #   Dung la truong hop can canh. ]]
    ktra("chưa có tool thì KHÔNG nhận vơ là đã hỏi thật",
         not rt.da_hoi_that(""), "bảng đang hiện là bản dự phòng")
    w._canh_bao_keo("")
    root.update_idletasks()
    ktra("dùng bảng dự phòng thì có dòng nói ra",
         w.o_canh_keo.winfo_ismapped(), w.lbl_keo.cget("text")[:60])
    ktra("dòng đó nói rõ đây là bảng dự phòng",
         "DỰ PHÒNG" in w.lbl_keo.cget("text"))
    ktra("và có nút để thử lại", w.btn_keo_lai.winfo_ismapped())

    #[[ Nhan thanh keo KHONG duoc cat. Ten cua 0.9.5 dai hon han ba ten cu:
    #   "Xoá khuyết điểm cơ thể" 22 ky tu; width=16 cu cat mat. ]]
    cat = []
    for o in w._o_keo:
        try:
            if o.winfo_class() == "TLabel" and o.winfo_ismapped() \
                    and o.winfo_width() < o.winfo_reqwidth() - 1:
                cat.append(str(o.cget("text"))[:30])
        except tk.TclError:
            pass
    ktra("không nhãn thanh kéo nào bị cắt", not cat, " | ".join(cat))

    #[[ Va kiem thang: dat mot nhan DAI vao roi do lai. Neu con width=16 thi
    #   cho co se nho hon cho can. ]]
    l = ttk.Label(w.khung_keo, text="Xoá khuyết điểm cơ thể")
    l.grid(row=99, column=0, sticky="w")
    root.update_idletasks()
    ktra("nhãn dài của 0.9.5 vẫn đủ chỗ",
         l.winfo_reqwidth() > 0 and l.winfo_width() >= l.winfo_reqwidth() - 1,
         f"cần {l.winfo_reqwidth()} px, có {l.winfo_width()} px")
    l.destroy()

    # ------------------------------------------- 2. ô "Vào" theo thư mục Export
    w.v_vao.set("")
    w.theo_thu_muc_export("F:\\Giao\\2705")
    root.update_idletasks()
    ktra("ô Vào đang trống thì đi theo thư mục Export luôn",
         w.v_vao.get().replace("/", "\\") == "F:\\Giao\\2705", w.v_vao.get())
    ktra("và không hiện cảnh báo lệch", not w.o_theo_export.winfo_ismapped())

    #[[ Doi thu muc Export lan hai: o Vao dang bam theo cai cu nen cu di theo,
    #   khong hoi. Nguoi dung chua he go gi rieng o day. ]]
    w.theo_thu_muc_export("F:\\Giao\\2806")
    root.update_idletasks()
    ktra("đang bám theo thì đổi Export lần hai vẫn đi theo",
         w.v_vao.get().replace("/", "\\") == "F:\\Giao\\2806", w.v_vao.get())

    #[[ Nhung neu ho DA GO mot duong dan khac thi tuyet doi khong duoc ghi de.
    #   "Tu dong" ghi de len cai vua go la kieu gay uc che nhat. ]]
    w.v_vao.set("F:\\Toi\\Tu\\Chon")
    w.theo_thu_muc_export("F:\\Giao\\9999")
    root.update_idletasks()
    ktra("người dùng đã gõ đường dẫn khác -> KHÔNG tự ghi đè",
         w.v_vao.get() == "F:\\Toi\\Tu\\Chon", w.v_vao.get())
    ktra("mà nói ra một dòng để họ tự quyết",
         w.o_theo_export.winfo_ismapped(),
         w.lbl_theo_export.cget("text")[:60])
    ktra("dòng đó nêu đúng thư mục Export",
         "9999" in w.lbl_theo_export.cget("text"))

    w._nhan_theo_export()
    root.update_idletasks()
    ktra("bấm nút thì mới ghi đè",
         w.v_vao.get().replace("/", "\\") == "F:\\Giao\\9999", w.v_vao.get())
    ktra("bấm xong thì dòng cảnh báo tắt đi",
         not w.o_theo_export.winfo_ismapped())

    #[[ "F:/Giao" va "F:\\giao\\" la CUNG mot cho. So chuoi thang thi app dung
    #   ra mot canh bao lech thu muc hoan toan vo nghia, va nguoi dung se hoc
    #   cach phot lo canh bao — hong luon ca nhung canh bao that. ]]
    w.v_vao.set("F:/Giao/9999/")
    w.theo_thu_muc_export("F:\\GIAO\\9999")
    root.update_idletasks()
    ktra("khác hoa thường / dấu gạch vẫn là cùng một chỗ",
         not w.o_theo_export.winfo_ismapped(), "không cảnh báo bừa")

    #[[ App phai co duong day sang: khau 5 doi thu muc thi khau Retouch biet. ]]
    app.v_export_dir.set("F:\\Giao\\tu_khau5")
    app.day_export_sang_retouch(app.v_export_dir.get())
    root.update_idletasks()
    ktra("khâu 5 đổi thư mục thì khâu Retouch nhận được",
         "tu_khau5" in w.v_vao.get() or w.o_theo_export.winfo_ismapped(),
         w.v_vao.get())

    # ------------------------------------- 3. mức riêng theo nhóm khuôn mặt
    #[[ VI SAO PHAN NAY QUAN TRONG.
    #
    #   Evoto khong de mot bo thanh keo cho ca buc anh. Anh ky yeu co ca thay
    #   giao lan hoc sinh: keo "lam thon mat" 60 cho ca hai la sai ca hai.
    #   saytool da chia nhom tu ban 0.5.0; rieng AutoTone thi chua, nen chay qua
    #   day la moi anh an cung mot muc.
    #]]
    nhom = rt.nhom_mat("")
    ktra("biết đủ năm nhóm khuôn mặt", len(nhom) == 5,
         " · ".join(n[1] for n in nhom))
    ktra("có hàng thẻ Chung + từng nhóm",
         set(w._nut_the) == {"", *[n[0] for n in nhom]},
         " ".join(sorted(w._nut_the)))
    ktra("mở lên là ở thẻ Chung", w.nhom_dang == "")

    #[[ Bien cua MOI nhom phai ton tai ngay ca khi the do khong dang hien —
    #   chi tao cho the dang xem thi chuyen the la mat muc vua dat. ]]
    ten0 = w._ds_keo[0][0]
    ktra("biến của mọi nhóm đều có sẵn, không đợi mở thẻ",
         all(("nam", ten0) in w.v_rieng and (n[0], ten0) in w.v_bat_rieng
             for n in nhom), f"{len(w.v_rieng)} ô mức riêng")

    w.doi_nhom("nam")
    for _ in range(4):
        root.update_idletasks()
        root.update()
    ktra("bấm thẻ Nam thì chuyển sang thẻ đó", w.nhom_dang == "nam")

    #[[ Chua tick "rieng" thi thanh keo phai MO va khong keo duoc. De keo duoc
    #   ma khong co tac dung la kieu giao dien noi doi. ]]
    sc, _lb = w._sc_theo[("nam", ten0)]
    ktra("chưa tick “riêng” thì thanh kéo khoá lại",
         str(sc.cget("state")) == "disabled", str(sc.cget("state")))
    ktra("và mức riêng chưa được tính vào bảng gửi đi",
         f"nam:{ten0}" not in w.muc_day_du())

    w.v_bat_rieng[("nam", ten0)].set(True)
    w.v_rieng[("nam", ten0)].set(40)
    w._doi_bat_rieng(("nam", ten0))
    root.update_idletasks()
    ktra("tick “riêng” thì mở thanh kéo ra",
         str(sc.cget("state")) == "normal", str(sc.cget("state")))
    d = w.muc_day_du()
    ktra("bảng gửi đi có mức riêng, đúng dạng saytool",
         d.get(f"nam:{ten0}") == 40 and ten0 in d,
         f"nam:{ten0}=40 · chung={d.get(ten0)}")
    ktra("thẻ có mức riêng thì mang dấu chấm",
         w._nut_the["nam"].cget("text").endswith("·"),
         w._nut_the["nam"].cget("text"))
    ktra("thẻ không đặt gì thì không có dấu",
         not w._nut_the["nu"].cget("text").endswith("·"),
         w._nut_the["nu"].cget("text"))

    #[[ Chuyen the roi quay lai: muc vua dat phai con nguyen. Dung bang lai lam
    #   mat no la kieu loi nguoi dung chi phat hien sau khi chay xong ca me. ]]
    w.doi_nhom("nu")
    root.update_idletasks()
    w.doi_nhom("nam")
    root.update_idletasks()
    ktra("chuyển thẻ qua lại không mất mức vừa đặt",
         w.muc_day_du().get(f"nam:{ten0}") == 40,
         str(w.muc_day_du().get(f"nam:{ten0}")))

    w.doi_nhom("")
    root.update_idletasks()
    ktra("về thẻ Chung thì không còn ô “riêng” nào",
         not any(str(o.cget("text")) == "riêng" for o in w._o_keo
                 if o.winfo_class() == "TCheckbutton"))

    #[[ Va dong lenh phai mang muc rieng sang: --nhom nam:<keo>=40. Thieu no
    #   thi nguoi dung dat rieng xong bam Chay va no chay y nhu khong dat gi. ]]
    c = rt.lenh(GOC, "/vao", "/ra", w.muc_day_du())
    ktra("dòng lệnh mang mức riêng sang saytool",
         "--nhom" in c and any(x.startswith(f"nam:{ten0.replace('_','-')}=")
                               for x in c),
         " ".join(c[-4:]))

    # ---------------------------------------- 4. nhắc khi đang ép số luồng
    #[[ retouch.json cua may that con "luong": 2 tu dot chua OOM 3/9. Con so do
    #   gio VO HIEU HOA phan tu do cua saytool 0.9.5 — 32 loi ma chi chay 2. ]]
    w.v_luong.set(2)
    root.update_idletasks()
    ktra("ép số luồng thì nói ra là đang ép",
         "ép 2" in w.lbl_luong.cget("text"), w.lbl_luong.cget("text"))
    ktra("và hiện nút để về 0", w.btn_luong0.winfo_ismapped())
    w.btn_luong0.invoke()
    root.update_idletasks()
    ktra("bấm nút thì về 0", int(w.v_luong.get()) == 0)
    ktra("về 0 rồi thì hết nhắc và ẩn nút",
         "tự dò" in w.lbl_luong.cget("text")
         and not w.btn_luong0.winfo_ismapped(), w.lbl_luong.cget("text"))

    # ---------------------------------------- 5. nhịp chạy: s/ảnh và còn bao lâu
    #[[ saytool chi in tien do MOI 10 ANH — voi 5 giay mot anh la gan mot phut
    #   moi co mot dong. Nguoi dung nhin man hinh dung im. Nen tu do bang so
    #   file da ra. ]]
    ktra("chưa chạy thì không bịa ra nhịp", w._nhip() == "")

    class _W:
        def is_alive(self):
            return True
    w.worker = _W()
    w._t0 = __import__("time").monotonic() - 180.0     # đã chạy 3 phút
    w._xong_dau = 0
    w.pb.configure(maximum=734, value=37)
    nh = w._nhip()
    #[[ 37 anh trong 180 giay = 4,9 s/anh; con 697 anh -> ~57 phut. Dung dung
    #   con so nguoi dung bao 9/9, de con so trong bai kiem co nghia. ]]
    ktra("tính đúng s/ảnh", "4.9 s/ảnh" in nh, nh)
    ktra("và ước được còn bao lâu", "57 phút" in nh, nh)

    #[[ Chay TIEP TUC (da co 600 anh tu luot truoc) ma khong tru di thi ra toc
    #   do nhanh gia — va nguoi dung tuong da sua duoc gi do. ]]
    w._xong_dau = 30
    w.pb.configure(value=37)
    nh = w._nhip()
    ktra("chạy tiếp tục thì trừ đi số ảnh đã có sẵn",
         "25.7 s/ảnh" in nh, nh)
    w.worker = None

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
