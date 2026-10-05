"""Dựng THẬT mô-đun Retouch bằng Tk rồi kiểm những chỗ từng hỏng ngoài đời.

NHỮNG CHỖ ĐÓ
    1. Bảng thanh kéo. Máy có saytool 0.9.5 (sáu thanh kéo) mà app hiện đúng ba
       — ba cái trong bảng dự phòng viết cứng. Không một dòng nào nói vì sao.
       Bài này canh: CÓ tool mà dùng bảng dự phòng thì PHẢI có dòng nói ra;
       CHƯA có tool thì dải báo trên lưới nói nguyên nhân, kèm nút chọn tool.
    2. Ô "Vào" không đi theo thư mục Export. Đổi thư mục Export xong vẫn phải
       vào sửa tay lần nữa; quên thì retouch chạy trên thư mục của BUỔI TRƯỚC
       mà không báo gì.
    3. Mức riêng theo nhóm khuôn mặt — đặt riêng cho Nam phải đi tới saytool.
    4. Ép số luồng thì nói ra (kể cả khi nhóm đang đóng).
    5. Nhịp chạy (s/ảnh, còn bao lâu) tính bằng số file ra.
    6. Dáng Evoto (tối 3/10 — "đưa cả phần Retouch thay đổi luôn", rồi "1 ảnh
       mở to và lưới ảnh bên dưới"): ảnh lớn ở trên, dải ảnh một hàng ở dưới;
       tấm đã làm mang nhãn và ảnh lớn mở BẢN KẾT QUẢ (giữ = bản gốc) — cả hai
       theo một luật (rt.ds_anh / rt.duong_ket_qua); ô "Ra" trống không bị hiểu
       là thư mục hiện hành; tuỳ chọn ở bảng điều khiển phải, nút Chạy trên
       thanh công cụ.
    7. Xem trước tính NGAY TRÊN ẢNH LỚN theo mức ở bảng phải (tool giả chạy
       qua đúng tiến trình con): đổi mức / đổi tấm thì tính lại, bấm Chạy thì
       tắt máy xem trước. Từ sáng 4/10 KHÔNG còn nút "Xem trước": kéo thanh là
       tự xem, vào mô-đun là máy xem trước mở sẵn, bấm ✕ trên chip để tắt.
    8. Mức riêng từng ảnh + Sync (sáng 4/10 — "Sync All các hiệu ứng đã kéo
       cho các ảnh được chọn hoặc tất cả"): kéo là chỉnh ảnh đang xem; Ctrl /
       Shift + bấm thật trên dải để chọn nhiều; Sync đã chọn / tất cả; ghi
       xuống đĩa theo thư mục vào; chạy theo nhóm mức (mỗi nhóm một lượt tool,
       thư mục tạm liên kết cứng, nhóm mức 0 chép nguyên bản, ghi đè thì từ
       chối).

VÌ SAO DỰNG TK THẬT CHỨ KHÔNG ĐỌC MÃ
    Đều là chuyện "cái gì HIỆN RA trên màn hình". Đọc mã chỉ chứng minh được
    có viết hàm, không chứng minh được nó có chạy và có hiện.

Chạy:  xvfb-run -a python3.12 kiem_retouch_gui.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
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

    #[[ HOP THOAI THAT cua tkinter la cua so MODAL — bai kiem khong co ai bam:
    #   gap mot cai ngoai du tinh la TREO toi het gio (da gap luc thu nguoc 4/10:
    #   mot dot bien lam start() hien "Chưa bật tính năng nào"). Thay ca bo bang
    #   ban GHI LAI; cho nao can tra loi khac thi tu thay rieng. ]]
    hop_thoai: list = []

    def _hop_gia(ten, tra_loi):
        def f(*a, **_k):
            hop_thoai.append((ten, " ".join(map(str, a))))
            return tra_loi
        return f

    for _ten, _tl in (("showinfo", "ok"), ("showwarning", "ok"), ("showerror", "ok"),
                      ("askokcancel", True), ("askyesno", True),
                      ("askyesnocancel", True), ("askquestion", "yes")):
        setattr(ag.messagebox, _ten, _hop_gia(_ten, _tl))

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
    #[[ Khong co tool that o may nay -> chac chan dang dung bang du phong. ]]
    ktra("chưa có tool thì KHÔNG nhận vơ là đã hỏi thật",
         not rt.da_hoi_that(""), "bảng đang hiện là bản dự phòng")

    def chay(n=4):
        for _ in range(n):
            root.update_idletasks()
            root.update()

    w._dong_bo_dai()
    chay()
    ktra("chưa có tool: dải báo trên lưới nói nguyên nhân",
         w.dai_rt.dang_hien() and "Chưa dùng được tool retouch"
         in w.dai_rt.nhan.cget("text"), w.dai_rt.nhan.cget("text")[:60])
    ktra("và có nút chọn thư mục tool ngay đó", w.btn_chon_tool.winfo_ismapped())
    w._canh_bao_keo("")
    chay()
    ktra("chưa có tool thì không nói thêm “bảng dự phòng” lần hai",
         not w.o_canh_keo.winfo_ismapped(), "một nguyên nhân, một cảnh báo")
    #[[ Dung truong hop 9/9: CO tool (saytool\cli.py co that) ma hoi khong
    #   duoc -> app hien bang du phong. Phai noi ra, kem nut thu lai. ]]
    gia = Path(tmp) / "ToolCloneEvoto"
    (gia / "saytool").mkdir(parents=True)
    (gia / "saytool" / "cli.py").write_text("# gia\n", encoding="utf-8")
    w._canh_bao_keo(str(gia))
    chay()
    ktra("có tool mà dùng bảng dự phòng thì có dòng nói ra",
         w.o_canh_keo.winfo_ismapped(), w.lbl_keo.cget("text")[:60])
    ktra("dòng đó nói rõ đây là bảng dự phòng", "DỰ PHÒNG" in w.lbl_keo.cget("text"))
    ktra("và có nút để thử lại", w.btn_keo_lai.winfo_ismapped())

    #[[ Nhan thanh keo KHONG duoc cat. Ten cua 0.9.5 dai hon han ba ten cu
    #   ("Xoá khuyết điểm cơ thể" 22 ky tu) — dung bang voi CHINH ten dai do,
    #   o the Chung lan the mot nhom (cong tac "rieng" an bot cho). ]]
    dai = [("vet", "Xoá khuyết điểm", 100.0, "Mụn, vết thâm"),
           ("vet_body", "Xoá khuyết điểm cơ thể", 0.0, "Trên tay, chân"),
           ("nhan_tran", "Làm mờ nếp nhăn trán", 0.0, "Nhẹ tay"),
           ("da_body", "Làm mịn da cơ thể", 0.0, "Da tay, chân"),
           ("lq_thon_mat", "Làm thon mặt", 0.0, "Liquify"),
           ("chan", "Kéo dài chân", 0.0, "Mức 100 = giãn thêm 14.5%")]
    keo_that = rt.thanh_keo
    rt.thanh_keo = lambda goc=None, lam_lai=False: list(dai)
    from tkinter import font as tkfont

    def chu_bi_cat(o) -> bool:
        """Chữ cần nhiều chỗ hơn chỗ nhãn ĐANG có.

        #[[ KHONG so winfo_width voi winfo_reqwidth: nhan dat width=12 thi
        #   reqwidth CUNG la 12 ky tu — chu bi cat ma hai so van bang nhau, bai
        #   kiem "dat" (thu nguoc 3/10 bat duoc dung cho nay). Do thang CHU
        #   bang phong cua chinh nhan. ]]
        """
        ten_phong = str(o.cget("font") or "") or ttk.Style(o).lookup(
            str(o.cget("style") or o.winfo_class()), "font") or "TkDefaultFont"
        try:
            f = tkfont.Font(root=o, font=ten_phong)
        except tk.TclError:
            f = tkfont.nametofont("TkDefaultFont")
        return f.measure(str(o.cget("text"))) > o.winfo_width() + 1

    cat = []
    try:
        for nh in ("", "nam"):
            w.doi_nhom(nh)
            chay(6)
            for o in w._o_keo:
                try:
                    if o.winfo_class() == "TLabel" and o.winfo_ismapped() \
                            and chu_bi_cat(o):
                        cat.append(f"{nh or 'chung'}:{str(o.cget('text'))[:30]}")
                except tk.TclError:
                    pass
        ten_hien = [str(o.cget("text")) for o in w._o_keo if o.winfo_class() == "TLabel"]
    finally:
        rt.thanh_keo = keo_that
        w.doi_nhom("")
        chay(4)
    ktra("bảng dựng đúng sáu tính năng tool báo, nhãn dài không bị cắt",
         not cat and "Xoá khuyết điểm cơ thể" in ten_hien,
         " | ".join(cat) if cat else f"{len(dai)} tính năng · cả thẻ Chung lẫn thẻ Nam")

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
         [ma for ma, _n in w._ds_the] == ["", *[n[0] for n in nhom]]
         and all(w.nhan_the(ma) for ma, _n in w._ds_the),
         " · ".join(w.nhan_the(ma) for ma, _n in w._ds_the))
    ktra("mở lên là ở thẻ Chung", w.nhom_dang == "" and w.v_nhom.get() == "")

    #[[ Bien cua MOI nhom phai ton tai ngay ca khi the do khong dang hien —
    #   chi tao cho the dang xem thi chuyen the la mat muc vua dat. ]]
    ten0 = w._ds_keo[0][0]
    ktra("biến của mọi nhóm đều có sẵn, không đợi mở thẻ",
         all(("nam", ten0) in w.v_rieng and (n[0], ten0) in w.v_bat_rieng
             for n in nhom), f"{len(w.v_rieng)} ô mức riêng")

    #[[ BAM THAT vao vien "Nam" (su kien chuot tren vien chon), khong goi
    #   ham — noi sai su kien la bam mai khong an ma goi ham van "dat". ]]
    pd = next(p for p in w._pd_the if p.nhan_cua("nam"))
    i_nam = [g for g, _n in pd._ds].index("nam")
    x0, x1 = pd._o[i_nam]
    pd.event_generate("<ButtonRelease-1>", x=(x0 + x1) // 2, y=pd.winfo_height() // 2)
    for _ in range(4):
        root.update_idletasks()
        root.update()
    ktra("bấm thẻ Nam thì chuyển sang thẻ đó", w.nhom_dang == "nam"
         and w.v_nhom.get() == "nam", w.nhom_dang)
    if w.nhom_dang != "nam":
        w.doi_nhom("nam")               # đã báo lỗi ở trên — đi tiếp để kiểm phần sau
        for _ in range(4):
            root.update_idletasks()
            root.update()
    ktra("thẻ một nhóm có công tắc “riêng” ở đầu mỗi hàng",
         sum(isinstance(o, gd.CongTac) for o in w._o_keo) == len(
             [t for t, *_x in w._ds_keo if rt.theo_nhom(t, "")]),
         f"{sum(isinstance(o, gd.CongTac) for o in w._o_keo)} công tắc")

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
         w.nhan_the("nam").endswith("·"), w.nhan_the("nam"))
    ktra("thẻ không đặt gì thì không có dấu",
         not w.nhan_the("nu").endswith("·"), w.nhan_the("nu"))

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
    ktra("về thẻ Chung thì không còn công tắc “riêng” nào",
         not any(isinstance(o, gd.CongTac) for o in w._o_keo))

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
    for _ in range(3):
        root.update_idletasks()
        root.update()
    #[[ Nhom "May & cach chay" DONG san — canh bao nam trong nhom dong thi
    #   dong tom tat phai noi ra, khong thi la giau. ]]
    ktra("nhóm đang đóng thì dòng tóm tắt vẫn nói đang ép",
         not w._nhom_rt["chay"].dang_mo
         and "ép 2" in w._nhom_rt["chay"].l_tom.cget("text"),
         w._nhom_rt["chay"].l_tom.cget("text"))
    w._nhom_rt["chay"].mo()
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

    # ---------------------------------------- 6. dáng Evoto: ảnh lớn + dải ảnh
    #[[ Toi 3/10, user: "Phan luoi anh cua Retouch hay lam giong Evoto. 1 anh
    #   mo to va luoi anh ben duoi". Ket qua (A1, A3) MAU KHAC han anh vao —
    #   do mau tren anh lon la biet dang hien ban nao. ]]
    from PIL import Image
    vao = Path(tmp) / "xuat"
    ra = Path(tmp) / "xuat_retouch"
    vao.mkdir()
    ra.mkdir()
    for i in range(5):
        Image.new("RGB", (300, 200), (40 * i, 120, 160)).save(vao / f"A{i}.png")
    for i in (1, 3):
        Image.new("RGB", (300, 200), (250, 250, 0)).save(ra / f"A{i}.png")
    w.v_ghide.set(False)
    w._doi_ghide()

    def mang_chung_sang(thu_muc, muc=None):
        """Từ 5/10 mức chung theo TỪNG thư mục vào (project mới = 0). Các phần
        test dưới kiểm logic mức riêng / mức chung trên một project ĐÃ CÓ mức
        chung — giả lập bằng cách ghi sẵn mức chung đang dùng cho thư mục đó
        (đúng như bản cũ, khi mức chung còn dùng chung mọi thư mục)."""
        rt.ghi_muc_anh(str(thu_muc), {}, muc if muc is not None else w._muc_chung_day_du())

    #[[ 5/10: thu muc nay KHONG ghi san muc chung — anh muc 0 thi anh lon la
    #   ban tren dia (cac test ket qua / giu xem goc ben duoi). Anh CO thong so
    #   thi tu xem truoc — xem test rieng sau. Muc chung cu (nam:vet=40...) giu
    #   lai cho vao2. ]]
    chung_dau = w._muc_chung_day_du()
    w.v_ra.set(str(ra))
    w.v_vao.set(str(vao))
    w._dem()
    chay(6)
    da = sorted(Path(o["path"]).name for o in w.luoi.ds if o.get("dau"))
    ktra("dải ảnh hiện ảnh của thư mục vào, tấm đã làm mang nhãn",
         len(w.luoi.ds) == 5 and da == ["A1.png", "A3.png"]
         and "2/5" in w.lbl_tt.cget("text"),
         f"{len(w.luoi.ds)} ô · đã làm {da} · “{w.lbl_tt.cget('text')[:40]}”")

    def cho_anh(giay=10):
        het = time.time() + giay
        while time.time() < het:
            chay(1)
            if not w.xem.dang_nap and w.xem.kich_thuoc() is not None:
                break
        chay(3)

    def mau_giua():
        w.xem._nhanh_toi = 0
        w.xem.ve_ngay()
        x0, y0, ww, hh = w.xem.vung_ve
        return tuple(w.xem._photo._PhotoImage__photo.get(ww // 2, hh // 2))

    cho_anh()
    ktra("mở mô-đun là có ẢNH LỚN ngay (tấm đầu), không phải khung trống",
         w._anh_dang == str(vao / "A0.png") and w.xem.kich_thuoc() == (300, 200)
         and w.luoi.dang_chon == str(vao / "A0.png"), Path(w._anh_dang or "—").name)
    ktra("ảnh lớn ở trên, dải ảnh MỘT hàng ở dưới",
         w.xem.winfo_rooty() < w.luoi.winfo_rooty() and w.luoi.ngang
         and w.xem.winfo_height() > 2 * w.luoi.winfo_height(),
         f"ảnh lớn {w.xem.winfo_height()} px · dải {w.luoi.winfo_height()} px")
    ktra("tấm chưa làm: “Chưa retouch”, không có gì để so",
         "Chưa retouch" in w.chip_anh.cget("text") and not w.xem.co_truoc()
         and str(w.btn_goc.cget("state")) == "disabled", w.chip_anh.cget("text"))
    #[[ Cho dai anh doc xong anh nho cua A1: anh lon hien anh nho do NGAY
    #   (ban goc, cung co 300 px voi anh that) roi moi thay bang ban ket qua —
    #   duong de anh tam lam ket anh lon (gap 3/10). ]]
    het = time.time() + 8
    while str(vao / "A1.png") not in w.luoi._anh_pil and time.time() < het:
        chay(1)
        time.sleep(0.02)
    x, y = w.luoi._o_xy(1)
    c = w.luoi.canvas
    w.luoi._bam(type("E", (), {"x": x - c.canvasx(0) + 8, "y": y + 8})())
    cho_anh()
    het = time.time() + 5
    while not w.xem.co_truoc() and time.time() < het:
        chay(1)
    ktra("bấm tấm đã làm trên dải: ảnh lớn là BẢN KẾT QUẢ",
         w._anh_dang == str(vao / "A1.png") and "Đã retouch" in w.chip_anh.cget("text")
         and mau_giua() == (250, 250, 0), f"{w.chip_anh.cget('text')} · {mau_giua()}")
    b = w.btn_goc
    ktra("nút “Giữ xem gốc” bật khi có bản gốc", str(b.cget("state")) == "normal")
    b.event_generate("<ButtonPress-1>", x=5, y=5)
    chay(2)
    goc = mau_giua()
    b.event_generate("<ButtonRelease-1>", x=5, y=5)
    chay(2)
    ktra("giữ “Giữ xem gốc”: thấy ẢNH GỐC, nhả ra: lại bản kết quả",
         goc == (40, 120, 160) and mau_giua() == (250, 250, 0), f"{goc} → {mau_giua()}")
    ktra("thanh dưới ảnh: tên, cỡ, tỉ lệ",
         "A1.png" in w.lbl_ten_anh.cget("text") and "300×200" in w.lbl_ten_anh.cget("text")
         and w.lbl_zoom.cget("text").endswith("%"),
         f"{w.lbl_ten_anh.cget('text')} · {w.lbl_zoom.cget('text')}")
    w.xem.canvas.focus_force()
    chay(2)
    w.xem.canvas.event_generate("<Right>")
    cho_anh()
    ktra("→ trên ảnh lớn: sang tấm kế (dải chọn theo)",
         w._anh_dang == str(vao / "A2.png") and w.luoi.dang_chon == w._anh_dang,
         Path(w._anh_dang or "—").name)
    #[[ Luot chay vua ghi ket qua cho DUNG tam dang soi: anh lon tu doi sang
    #   ban ket qua, va giu nguyen cho dang phong — nguoi dung dang soi mat
    #   thi van o mat. ]]
    w.xem.dat_ty_le(2.0, (100, 100))
    chay(2)
    s_dang, tam_dang = w.xem.ty_le(), w.xem.tam()
    Image.new("RGB", (300, 200), (0, 200, 90)).save(ra / "A2.png")
    w._dem()
    het = time.time() + 6
    while time.time() < het and "Đã retouch" not in w.chip_anh.cget("text"):
        chay(1)
    cho_anh()
    ktra("tấm đang xem vừa có kết quả: ảnh lớn tự đổi sang bản kết quả",
         mau_giua() == (0, 200, 90) and "Đã retouch" in w.chip_anh.cget("text"),
         str(mau_giua()))
    ktra("…và giữ nguyên chỗ đang soi",
         w.xem.ty_le() == s_dang and w.xem.tam() == tam_dang,
         f"{w.xem.ty_le() * 100:.0f}%")
    #[[ Ghi de: anh ra de len anh vao, khong biet tam nao da lam bang file —
    #   khong duoc gan nhan "da lam" theo thu muc ra cu. ]]
    w.v_ghide.set(True)
    w._doi_ghide()
    chay(4)
    ktra("ghi đè thì không gắn nhãn “đã làm” theo thư mục ra",
         len(w.luoi.ds) == 5 and not any(o.get("dau") for o in w.luoi.ds))
    w.v_ghide.set(False)
    w._doi_ghide()
    chay(4)
    #[[ O "Ra" TRONG khong phai thu muc hien hanh: Path("") == Path(".") —
    #   dung trong thu muc vao thi moi anh "da co ket qua" gia. ]]
    cu_cwd = os.getcwd()
    try:
        os.chdir(vao)
        try:
            tong, xong = rt.dem(vao, Path(""))
            ds0 = rt.ds_anh(vao, "")
            kq0 = rt.duong_ket_qua(vao / "A0.png", vao, "")
        except Exception as ex:                              # noqa: BLE001
            #[[ Sap o day cung la hong DUNG muc nay — noi ra o dong [!] chu
            #   khong de ca bai kiem chet ma khong ai biet chet vi dau. ]]
            tong, xong, ds0, kq0 = -1, -1, [], f"{type(ex).__name__}: {ex}"
    finally:
        os.chdir(cu_cwd)
    ktra("ô “Ra” trống không bị hiểu là thư mục hiện hành",
         tong == 5 and xong == 0 and not any(x for _p, x in ds0) and kq0 is None,
         f"{xong}/{tong}" + (f" · {kq0}" if kq0 else ""))
    #[[ Mot luat cho ca hai cho: nhan "da lam" tren dai va file ma anh lon mo.
    #   Lech nhau la bam tam "da lam" ma anh lon hien ban goc. ]]
    lech = [p.name for p, x in rt.ds_anh(vao, ra)
            if x != rt.duong_ket_qua(p, vao, ra).is_file()]
    ktra("nhãn “đã làm” và bản ảnh lớn mở dùng CHUNG một luật",
         not lech, "lệch: " + ", ".join(lech) if lech else "rt.duong_ket_qua")
    #[[ Bam dup mot tam tren dai = bat xem truoc DUNG tam do. Thay ham bat
    #   (khong co tool that o day — muc 7 chay tool gia). ]]
    goi = []
    w._mo_xem_truoc = lambda anh=None: goi.append(anh)
    x, y = w.luoi._o_xy(2)
    w.luoi._bam_dup(type("E", (), {"x": x - c.canvasx(0) + 6, "y": y + 6})())
    ktra("bấm đúp một tấm trên dải là bật xem trước đúng tấm đó",
         goi == [w.luoi.ds[2]["path"]], Path(goi[0]).name if goi else "—")
    del w._mo_xem_truoc

    #[[ Sang 4/10 — user: "bo nut xem truoc. Vi khi keo se load luon vao anh":
    #   tren thanh cong cu chi con nut Chay (vang), khong con "Xem trước". ]]
    chu_cc = [str(x.cget("text")) for x in app.cc_phai_rt.winfo_children()
              if isinstance(x, gd.NutTron) and x.winfo_ismapped()]
    ktra("nút Chạy (vàng) trên thanh công cụ của app, KHÔNG còn nút Xem trước",
         w.btn_run.winfo_ismapped() and str(w.btn_run.cget("kieu")) == "chinh"
         and str(w.btn_run.winfo_toplevel()) == str(root)
         and w.btn_run.master is app.cc_phai_rt
         and not any("Xem trước" in t for t in chu_cc) and not hasattr(w, "btn_xem"),
         " · ".join(t for t in chu_cc if t) or "—")
    ktra("đang ở Retouch thì nút của Cân tone ẩn đi",
         not app.btn_analyze.winfo_ismapped() and not app.btn_ghi3.winfo_ismapped()
         and not app.lbl_job.winfo_ismapped())
    rong_rt = app.ben_phai.winfo_width()
    ktra("tuỳ chọn Retouch nằm ở bảng điều khiển phải",
         app.cuon_phai_rt.winfo_ismapped() and not app.cuon_phai.winfo_ismapped()
         and w.khung_keo.winfo_ismapped(), f"rộng {rong_rt} px")
    #[[ Chay -> nut Dung hien ra; xong -> an di, nut Chay mo lai. ]]
    w._dat_dang_chay(True)
    root.update_idletasks()
    dang = w.btn_stop.winfo_ismapped() and str(w.btn_run.cget("state")) == "disabled"
    w._dat_dang_chay(False)
    root.update_idletasks()
    ktra("đang chạy thì có nút Dừng, xong thì ẩn",
         dang and not w.btn_stop.winfo_ismapped()
         and str(w.btn_run.cget("state")) == "normal")

    # ---------------------------------------- 7. xem trước NGAY TRÊN ẢNH LỚN
    #[[ Tool GIA dung dang saytool: NguCanh thu ve 1400 px, mot "mat"; Bo.chay
    #   dao mau anh (khac han ban goc) va ghi lai muc nhan duoc. Chay that qua
    #   xem_truoc.MayXem — tien trinh con, giao thuc JSON nhu tool that.
    #   Sang 4/10: KHONG con nut "Xem trước" — keo thanh la anh lon tinh lai;
    #   vao mo-dun la may xem truoc mo SAN o nen. ]]
    (gia / "saytool" / "__init__.py").write_text("", encoding="utf-8")
    (gia / "saytool" / "buoc.py").write_text(
        "class B:\n    def __init__(s, ten, nhan):\n        s.ten, s.nhan = ten, nhan\n"
        "def tat_ca():\n    return [B('vet', 'Xoa khuyet diem'), B('chan', 'Keo dai chan')]\n",
        encoding="utf-8")
    (gia / "saytool" / "ngu_canh.py").write_text(
        "import cv2, numpy as np\n"
        "class _M:\n    def __init__(s, b):\n        s.bbox = b\n        s.width = b[2] - b[0]\n"
        "class NguCanh:\n    def __init__(s, p, canh_toi_da=1400):\n"
        "        a = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)\n"
        "        h, w = a.shape[:2]\n        k = min(1.0, canh_toi_da / max(h, w))\n"
        "        if k < 1:\n            a = cv2.resize(a, (int(w * k), int(h * k)))\n"
        "        s.anh = a\n        H, W = a.shape[:2]\n"
        "        s.mat = [] if 'khong_mat' in str(p) else [_M([W*0.4, H*0.3, W*0.5, H*0.45])]\n",
        encoding="utf-8")
    (gia / "saytool" / "mot_anh.py").write_text(
        "import json, os, time\nfrom pathlib import Path\n"
        "class Bo:\n    def __init__(s, may='auto'):\n        time.sleep(0.1)\n"
        "    def chay(s, nc, muc):\n        time.sleep(0.25)\n"
        "        if Path(os.environ['GIA_TU_CHOI']).exists() and any(':' in k for k in muc):\n"
        "            raise ValueError('khong biet khoa ' + [k for k in muc if ':' in k][0])\n"
        "        with open(os.environ['GIA_GHI_MUC'], 'a', encoding='utf-8') as f:\n"
        "            f.write(json.dumps(muc) + '\\n')\n"
        "        return 255 - nc.anh\n", encoding="utf-8")
    ghi = Path(tmp) / "muc_nhan.jsonl"
    tu_choi = Path(tmp) / "tu_choi_nhom"
    os.environ["GIA_GHI_MUC"] = str(ghi)
    os.environ["GIA_TU_CHOI"] = str(tu_choi)

    def muc_nhan():
        if not ghi.is_file():
            return []
        return [json.loads(d) for d in ghi.read_text(encoding="utf-8").splitlines() if d]

    def cho(dk, giay=20):
        het = time.time() + giay
        while time.time() < het:
            chay(1)
            time.sleep(0.02)
            if dk():
                return True
        return False

    def chip():
        return str(w.chip_anh.cget("text"))

    def xong_xem():
        """Chip của bản xem trước ĐÃ TÍNH XONG (không phải đang mở / đang tính)."""
        t = chip()
        return w._xem_dang_hien and t.startswith("Xem trước · ") and "✕" in t \
            and ("mức riêng" in t or "mức chung" in t)

    vao2 = Path(tmp) / "xuat2"
    vao2.mkdir()
    Image.new("RGB", (2000, 1500), (200, 120, 60)).save(vao2 / "P0.png")
    Image.new("RGB", (2000, 1500), (60, 160, 90)).save(vao2 / "P1.png")
    Image.new("RGB", (2000, 1500), (90, 90, 200)).save(vao2 / "P2_khong_mat.png")
    w.v_goc.set(str(gia))
    mang_chung_sang(vao2, chung_dau)
    w.v_ra.set(str(Path(tmp) / "xuat2_ra"))
    w.v_vao.set(str(vao2))
    w._dem()
    cho_anh()
    #[[ Vao mo-dun: may xem truoc mo SAN o nen va mo ngam tam dang xem — anh
    #   lon VAN la ban tren dia (chua ai keo gi). Roi mo-dun thi tat may (giu
    #   mo hinh tren card do hoa, Lightroom dang can). ]]
    app._chon_khau("phan_tich")
    chay(3)
    app._chon_khau("retouch")
    ok = cho(lambda: w._xem_fp == str(vao2 / "P0.png"))
    #[[ 5/10 — user: "anh da duoc keo thong so thi phai tai vao preview luon".
    #   P0 co san muc chung > 0, chua co ket qua -> vao mo-dun la TU xem truoc. ]]
    ktra("vào mô-đun Retouch: tấm ĐÃ CÓ thông số → xem trước TỰ BẬT, không cần kéo",
         ok and w._may_xem is not None and w._xem_bat
         and getattr(w, "_xem_tu_dong", False), chip())
    #[[ Xem truoc TU BAT thi moi tam tu quyet: tam muc 0 -> anh goc; quay lai
    #   tam co thong so -> tu xem truoc lai. ]]
    k_p1 = w._khoa(str(vao2 / "P1.png"))
    w._muc_anh[k_p1] = {t: 0.0 for t, *_x in w._ds_keo}
    w.luoi.chon(str(vao2 / "P1.png"))
    w._chon_anh(str(vao2 / "P1.png"))
    chay(3)
    ktra("xem trước tự bật → sang tấm MỨC 0: ảnh gốc trên đĩa, tắt xem trước",
         not w._xem_bat and "Chưa retouch" in chip(), chip())
    w.luoi.chon(str(vao2 / "P0.png"))
    w._chon_anh(str(vao2 / "P0.png"))
    ok = cho(xong_xem)
    ktra("…quay lại tấm CÓ thông số: tự xem trước lại",
         ok and w._xem_bat and w._anh_dang == str(vao2 / "P0.png"), chip())
    w._muc_anh.pop(k_p1, None)
    p_cu = w._may_xem.proc if w._may_xem is not None else None
    app._chon_khau("phan_tich")
    chay(3)
    ktra("rời mô-đun Retouch: tắt máy xem trước (trả card đồ hoạ)",
         w._may_xem is None and p_cu is not None and cho(lambda: p_cu.poll() is not None, 5))
    app._chon_khau("retouch")
    cho(lambda: w._xem_fp == str(vao2 / "P0.png"))
    chay(3)
    so_cua_so = len([x for x in root.winfo_children() if isinstance(x, tk.Toplevel)])
    #[[ KEO THANH (khong bam nut nao): tam dang xem da mo san o tien trinh con
    #   nen tinh NGAY, khong cho mo anh / tim mat. ]]
    w.v_muc[ten0].set(60)
    chay(1)
    ktra("kéo thanh: xem trước TỰ BẬT, tấm đã mở sẵn nên tính ngay",
         w._xem_bat and w._xem_dang_tinh is not None, chip())
    ok = cho(xong_xem)
    ktra("ảnh lớn thành bản TÍNH BẰNG TOOL, không mở cửa sổ thứ hai",
         ok and w.xem.kich_thuoc() == (1400, 1050)
         and len([x for x in root.winfo_children() if isinstance(x, tk.Toplevel)])
         == so_cua_so, f"{chip()} · {w.xem.kich_thuoc()}")
    ktra("bản xem trước khác ảnh gốc, giữ xem gốc thì thấy gốc",
         mau_giua() == (55, 135, 195) and w.xem.co_truoc(), str(mau_giua()))
    nhan = muc_nhan()
    ktra("tool nhận ĐÚNG mức đang đặt ở bảng phải (cả mức riêng theo nhóm)",
         bool(nhan) and nhan[-1] == w._muc_xem() and nhan[-1].get(ten0) == 60
         and f"nam:{ten0}" in nhan[-1], str(nhan[-1] if nhan else "—")[:70])
    ktra("mặt tool tìm được → Vào mặt bật", w.xem.so_mat() == 1
         and str(w.btn_mat.cget("state")) == "normal")
    n0 = len(muc_nhan())
    w.v_muc[ten0].set(20)
    ok = cho(lambda: len(muc_nhan()) > n0 and muc_nhan()[-1].get(ten0) == 20
             and xong_xem())
    ktra("kéo thanh ở bảng phải: ảnh lớn tính lại theo mức mới", ok,
         f"{len(muc_nhan()) - n0} lần tính")
    #[[ Tat bang dau ✕ tren chip: anh lon ve ban tren dia, may van chay san —
    #   va GIU vung dang soi (ban xem truoc 1400 px -> ban tren dia 2000 px).
    #   Keo tiep la tu bat lai. ]]
    w.xem.dat_ty_le(1.0)
    w.xem._cx, w.xem._cy = 760.0, 560.0
    w.xem._kep()
    chay(2)
    c_xt = w.xem.tam()
    w.chip_anh.event_generate("<Button-1>", x=4, y=4)
    chay(3)
    ktra("bấm ✕ trên chip: tắt xem trước, ảnh lớn về bản trên đĩa (máy vẫn chạy sẵn)",
         not w._xem_bat and not w._xem_dang_hien and "Chưa retouch" in chip()
         and w._may_xem is not None, chip())
    cho_anh()
    he = 2000 / 1400
    ktra("…và giữ chỗ đang soi (không nhảy về vừa khung)",
         not w.xem.la_vua() and abs(w.xem.ty_le() - 1.0 / he) < 1e-6
         and abs(w.xem.tam()[0] - c_xt[0] * he) < 2 and abs(w.xem.tam()[1] - c_xt[1] * he) < 2,
         f"{w.xem.ty_le() * 100:.0f}% · tâm ({w.xem.tam()[0]:.0f},{w.xem.tam()[1]:.0f})")
    w.xem.vua_khung()
    n0 = len(muc_nhan())
    w.v_muc[ten0].set(25)
    ok = cho(lambda: len(muc_nhan()) > n0 and muc_nhan()[-1].get(ten0) == 25
             and xong_xem())
    ktra("tắt rồi kéo tiếp: xem trước tự bật lại, tính theo mức mới", ok and w._xem_bat,
         f"{len(muc_nhan()) - n0} lần tính")
    #[[ Doi the nhom (dung lai bang thanh keo) ma muc khong doi -> KHONG tinh
    #   lai: 3 giay mot lan tinh cho mot cu bam the la phi. ]]
    n0, ma0 = len(muc_nhan()), w._xem_ma
    w.doi_nhom("nu")
    w.doi_nhom("")
    het = time.time() + 1.2           # quá 0,2 s chờ ngừng tay + một lần tính
    while time.time() < het:
        chay(1)
        time.sleep(0.02)
    ktra("đổi thẻ nhóm mà mức không đổi: không tính lại",
         w._xem_ma == ma0 and len(muc_nhan()) == n0, f"{w._xem_ma - ma0} lần xin tính")
    #[[ Keo roi tra ve DUNG muc cu truoc khi kip tinh -> muc gui di y het lan
    #   vua tinh: khong tinh lai. ]]
    cu = float(w.v_muc[ten0].get())
    w.v_muc[ten0].set(cu + 7)
    w.v_muc[ten0].set(cu)
    het = time.time() + 1.2
    while time.time() < het:
        chay(1)
        time.sleep(0.02)
    ktra("kéo rồi trả về đúng mức cũ (chưa kịp tính): không tính lại",
         w._xem_ma == ma0 and len(muc_nhan()) == n0, f"{w._xem_ma - ma0} lần xin tính")
    #[[ Dang TINH tam P0 thi bam sang P1: ket qua cua P0 ve sau KHONG duoc ve
    #   len anh lon (nguoi dung dang nhin P1). Ghi lai moi anh da dat len. ]]
    da_dat = []
    dat_that = w.xem.dat_anh

    def dat_ghi(sau, *a, **kw):
        da_dat.append(sau.getpixel((sau.width // 2, sau.height // 2)))
        return dat_that(sau, *a, **kw)

    w.xem.dat_anh = dat_ghi
    w.v_muc[ten0].set(30)
    w._xem_tinh()
    ktra("đang tính thì có một yêu cầu đang chạy", w._xem_dang_tinh is not None)
    w._buoc_anh(1)
    chay(2)
    ktra("đang xem trước mà bấm sang tấm khác: ảnh lớn đổi NGAY (bản trên đĩa)",
         w._anh_dang == str(vao2 / "P1.png") and not w._xem_dang_hien
         and w.xem.kich_thuoc() == (2000, 1500), str(w.xem.kich_thuoc()))
    ok = cho(lambda: w._xem_fp == str(vao2 / "P1.png") and xong_xem())
    ktra("đang xem trước mà sang tấm khác: tính luôn tấm đó",
         ok and mau_giua() == (195, 95, 165), f"{Path(w._xem_fp or '—').name} · {mau_giua()}")
    w.xem.dat_anh = dat_that
    ktra("kết quả muộn của tấm cũ không đè lên tấm đang xem",
         (55, 135, 195) not in da_dat, f"{len(da_dat)} lần đặt ảnh: {da_dat}")
    #[[ Luot nhanh qua lai khi dang xem truoc: MOT lan mo anh moi luc (tien
    #   trinh con lam tuan tu tung viec) — luot bon tam khong xep hang bon lan
    #   mo, va cuoi cung la DUNG tam dang xem. ]]
    P1 = str(vao2 / "P1.png")
    mo = []
    gui_that = w._may_xem.gui

    def gui_ghi(**kw):
        if kw.get("viec") == "mo_anh":
            mo.append(kw.get("fp"))
        return gui_that(**kw)

    w._may_xem.gui = gui_ghi
    for d in (1, -1, -1, 1):
        w._buoc_anh(d)
    ok = cho(lambda: w._anh_dang == P1 and w._xem_fp == P1 and xong_xem())
    w._may_xem.gui = gui_that
    ktra("lướt nhanh lúc xem trước: một lần mở ảnh mỗi lúc, cuối cùng đúng tấm đang xem",
         ok and len(mo) <= 2 and mau_giua() == (195, 95, 165),
         f"{len(mo)} lần mở: {[Path(x).stem for x in mo]} · {mau_giua()}")
    #[[ Anh khong co mat VAN tinh: tu 0.9.5 co buoc chay tren co the (khuyet
    #   diem co the, keo dai chan). Chi noi ra la tool khong thay mat nao. ]]
    n0 = len(muc_nhan())
    w._buoc_anh(1)
    ok = cho(lambda: "không thấy khuôn mặt" in chip())
    ktra("ảnh tool không thấy mặt: vẫn tính (bước cơ thể), và nói ra",
         ok and len(muc_nhan()) == n0 + 1, chip()[:60])
    w._buoc_anh(-1)
    cho(xong_xem)
    #[[ Ban saytool khong nhan khoa "nam:vet" -> tinh lai voi muc chung va noi
    #   ra, khong dung o loi. Tu 5/10 moi thanh mac dinh 0, nen dat muc CHUNG
    #   > 0 truoc: khong thi luc lui ve muc chung se la "moi muc o 0" -> preview
    #   khong tinh, test cho xong_xem mai khong xong. ]]
    tu_choi.write_text("1", encoding="utf-8")
    w.v_muc[ten0].set(50)               # muc chung > 0 de con viec sau khi lui nhom
    chay(2)
    w.v_rieng[("nam", ten0)].set(55)
    w._doi_bat_rieng(("nam", ten0))
    ok = cho(lambda: w._xem_bo_nhom and xong_xem())
    ktra("tool không nhận mức riêng theo nhóm: lùi về mức chung, nói ra",
         ok and not any(":" in k for k in muc_nhan()[-1])
         and "mức Chung" in w.txt.get("1.0", "end"), chip()[:50])
    tu_choi.unlink()
    #[[ Bam Chay: tat may xem truoc TRUOC (giu mo hinh tren card do hoa). Chay
    #   that start() voi tool gia — chi thay buoc goi saytool. ]]
    may = w._may_xem
    p_con = may.proc if may is not None else None
    w._kiem = lambda chay_thu=False: True
    w._hoi_chep = lambda *a: True
    goi_chay = []

    def chay_ghi(*a, **_k):
        goi_chay.append(str(a[1]))
        return iter([("ma", 0)])

    chay_that, w.rt.chay = w.rt.chay, chay_ghi
    hoi_that = ag.messagebox.askokcancel
    ag.messagebox.askokcancel = lambda *a, **k: True
    #[[ Luong chay ca me doc bien Tk (v_dequy...) — chi duoc khi co mainloop.
    #   Bai kiem khong co mainloop nen cho no chay LIEN o luong chinh. ]]
    import threading

    class _ChayLien:
        def __init__(self, target=None, daemon=None, **_k):
            self._t = target

        def start(self):
            self._t()

        def is_alive(self):
            return False

    luong_that = threading.Thread
    threading.Thread = _ChayLien
    try:
        w.start()
        tat_ngay = w._may_xem is None and not w._xem_bat
    finally:
        threading.Thread = luong_that
        w.rt.chay = chay_that
        ag.messagebox.askokcancel = hoi_that
    chay(6)
    ktra("bấm Chạy: tắt xem trước, đóng tiến trình con (nhường card đồ hoạ)",
         tat_ngay and bool(goi_chay) and p_con is not None
         and cho(lambda: p_con.poll() is not None, 5), f"{len(goi_chay)} lượt chạy")
    ktra("…và ảnh lớn về bản trên đĩa", not w._xem_dang_hien
         and w.xem.kich_thuoc() in (None, (2000, 1500)), str(w.xem.kich_thuoc()))
    w._mo_xem_truoc()
    cho(lambda: w._xem_san_sang and w._may_xem is not None)
    w._may_xem.proc.kill()
    ok = cho(lambda: not w._xem_bat)
    ktra("tiến trình xem trước chết: tắt xem trước, nói ra",
         ok and "đã dừng" in chip(), chip()[:50])

    # ---------------------------------------- 8. mức riêng từng ảnh + Sync
    #[[ Sang 4/10 — user: "can them nut Sync All cac hieu ung da keo cho cac
    #   anh duoc chon hoac tat ca". Nhu Evoto: keo thanh la chinh ANH DANG XEM;
    #   Sync chep muc cua anh do sang cac tam da chon / tat ca. Chay: anh khac
    #   muc thi moi nhom mot luot cua tool. ]]
    vao3 = Path(tmp) / "xuat3"
    ra3 = Path(tmp) / "xuat3_ra"
    vao3.mkdir()
    for i in range(6):
        Image.new("RGB", (600, 400), (20 + 30 * i, 100, 150)).save(vao3 / f"Q{i}.png")
    q = [str(vao3 / f"Q{i}.png") for i in range(6)]
    #[[ 5/10 — user: "them 1 project voi cac tinh nang chua duoc dua ve 0".
    #   Gia lap retouch.json CU con muc chung 100 (ban cu ghi muc chung o day,
    #   dung chung moi thu muc): thu muc MOI van phai hien moi thanh = 0. ]]
    chung_truoc = w._muc_chung_day_du()     # muc chung project truoc (vao2)
    rt.ghi_cau_hinh({"muc": {t: 100.0 for t, *_x in w._ds_keo}})
    w.cf["muc"] = {t: 100.0 for t, *_x in w._ds_keo}
    w.v_ra.set(str(ra3))
    w.v_vao.set(str(vao3))
    w._dem()
    cho_anh()
    chay(4)
    chung0 = w._muc_chung_day_du()
    ktra("thư mục mới: chưa ảnh nào có mức riêng, bảng là mức chung",
         w._anh_dang == q[0] and not w._muc_anh
         and rt.giong_muc(w.muc_day_du(), chung0)
         and "theo mức chung" in w.lbl_pham_vi.cget("text"),
         w.lbl_pham_vi.cget("text"))
    ktra("project mới: MỌI thanh = 0 (dù retouch.json cũ còn mức chung 100)",
         all(float(v.get()) == 0.0 for v in w.v_muc.values())
         and all(float(v) == 0.0 for v in chung0.values()),
         str({k: v.get() for k, v in w.v_muc.items()}))
    #[[ 5/10 — user: "chon anh o luoi anh khi chua Sync ... chua ve muc 0".
    #   Keo Q0 roi sang Q1 (chua Sync): Q1 phai = 0 het. ]]
    w.v_muc[ten0].set(35)
    chay(2)
    w._buoc_anh(1)
    chay(2)
    ktra("chọn ảnh CHƯA Sync: mọi thanh = 0",
         w._anh_dang == q[1]
         and all(float(v.get()) == 0.0 for v in w.v_muc.values()),
         str({k: v.get() for k, v in w.v_muc.items()}))
    w._buoc_anh(-1)
    chay(2)
    w._ve_muc_chung()                         # Q0 bo muc rieng vua keo
    chay(2)
    #[[ Phan duoi kiem logic muc rieng / muc chung tren project DA CO muc chung
    #   (project cu) — dat muc chung cua vao3 = muc chung project truoc. ]]
    w._muc_chung_tm = dict(chung_truoc)
    w._muc_chung_ban = True
    w._luu_muc()
    w._nap_muc_vao_bang(w._muc_hieu_luc(q[0]))
    chay(2)
    chung0 = w._muc_chung_day_du()
    a0 = float(w.v_muc[ten0].get())
    moi = 15.0 if a0 != 15.0 else 25.0
    w.v_muc[ten0].set(moi)
    chay(2)
    ktra("kéo thanh: CHỈ ảnh đang xem có mức riêng",
         list(w._muc_anh) == ["Q0.png"] and w._muc_anh["Q0.png"].get(ten0) == moi,
         str(list(w._muc_anh)))
    ktra("…ảnh đó mang nhãn “riêng” trên dải, dòng phạm vi nói “mức riêng”",
         bool(w.luoi.ds[0].get("rieng")) and not w.luoi.ds[1].get("rieng")
         and "mức riêng" in w.lbl_pham_vi.cget("text"), w.lbl_pham_vi.cget("text"))
    ktra("máy xem trước vừa hỏng: kéo thanh KHÔNG tự mở lại, nói ra ở chip",
         w._may_xem is None and "lỗi" in chip(), chip()[:60])
    w._buoc_anh(1)
    chay(2)
    ktra("sang tấm khác: bảng hiện mức CỦA TẤM ĐÓ (mức chung)",
         w._anh_dang == q[1] and float(w.v_muc[ten0].get()) == chung0[ten0]
         and "theo mức chung" in w.lbl_pham_vi.cget("text"),
         f"{w.v_muc[ten0].get()} · {w.lbl_pham_vi.cget('text')}")
    w._buoc_anh(-1)
    chay(2)
    ktra("quay lại: bảng hiện lại đúng mức riêng vừa kéo",
         w._anh_dang == q[0] and float(w.v_muc[ten0].get()) == moi,
         str(w.v_muc[ten0].get()))
    #[[ Keo ve DUNG muc chung: anh het muc rieng (khong de nhan "riêng" ao —
    #   nhin dai anh tuong tam do khac ma that ra y het). ]]
    w.v_muc[ten0].set(chung0[ten0])
    chay(2)
    ktra("kéo về đúng mức chung: ảnh hết mức riêng, mất nhãn “riêng”",
         "Q0.png" not in w._muc_anh and not w.luoi.ds[0].get("rieng"),
         str(sorted(w._muc_anh)))
    w.v_muc[ten0].set(moi)
    chay(2)

    def sang(i):
        w.luoi.chon(q[i])
        w._chon_anh(q[i])
        chay(2)

    #[[ NAP muc cua tam vua chon KHONG phai la keo: Q5 tat rieng nhom Nam, Q0
    #   giu Nam 40 — chuyen qua lai, muc rieng cua ca hai phai nguyen ven (nap
    #   tung bien mot ma tinh la keo thi tam nay an mot nua muc cua tam kia). ]]
    k_nam = ("nam", ten0)
    sang(5)
    if w.v_bat_rieng[k_nam].get():
        w.v_bat_rieng[k_nam].set(False)
        w._doi_bat_rieng(k_nam)
    w.v_muc[ten0].set(moi + 3)
    chay(2)
    sang(0)
    sang(5)
    m5, m0 = dict(w._muc_anh.get("Q5.png", {})), dict(w._muc_anh.get("Q0.png", {}))
    ktra("chuyển tấm qua lại: nạp mức KHÔNG ghi đè mức riêng của tấm nào",
         f"nam:{ten0}" not in m5 and m5.get(ten0) == moi + 3
         and m0.get(f"nam:{ten0}") == 40 and m0.get(ten0) == moi
         and f"nam:{ten0}" not in w._muc_hieu_luc(q[5])
         and not w.v_bat_rieng[k_nam].get(),
         f"Q5 {ten0}={m5.get(ten0)} nam={m5.get(f'nam:{ten0}')} · Q0 nam={m0.get(f'nam:{ten0}')}")
    w._ve_muc_chung()          # nut "Về mức chung" da bo khoi UI (5/10)
    sang(0)
    #[[ BAM THAT tren dai anh: Ctrl / Shift + bam (su kien Tk co state). Thoi
    #   diem cach nhau 1 giay — khong thi Tk coi hai lan bam la bam dup. ]]
    c3 = w.luoi.canvas
    t_ev = [50_000]

    def bam(i, state=0):
        x, y = w.luoi._o_xy(i)
        t_ev[0] += 1000
        c3.event_generate("<Button-1>", x=int(x - c3.canvasx(0)) + 10,
                          y=int(y - c3.canvasy(0)) + 10, state=state, time=t_ev[0])
        chay(2)

    def ten_chon():
        return [Path(p).stem for p in w.luoi.ds_chon()]

    bam(2, 0x4)
    bam(4, 0x4)
    ktra("Ctrl + bấm: chọn thêm, tấm đang xem (tấm nguồn) không đổi",
         w.luoi.ds_chon() == [q[0], q[2], q[4]] and w._anh_dang == q[0],
         f"{ten_chon()} · đang xem {Path(w._anh_dang or '—').stem}")
    ktra("nút “Sync ảnh đã chọn” đếm đúng số tấm và bật",
         "(3)" in w.btn_sync_chon.cget("text")
         and w.btn_sync_chon.cget("state") == "normal", w.btn_sync_chon.cget("text"))
    w.btn_sync_chon.invoke()
    chay(2)
    ktra("Sync ảnh đã chọn: các tấm chọn nhận ĐÚNG mức tấm đang xem, tấm khác không đổi",
         sorted(w._muc_anh) == ["Q0.png", "Q2.png", "Q4.png"]
         and all(rt.giong_muc(w._muc_anh[k], w._muc_anh["Q0.png"]) for k in w._muc_anh)
         and [bool(o.get("rieng")) for o in w.luoi.ds]
         == [True, False, True, False, True, False], str(sorted(w._muc_anh)))
    bam(1)
    ktra("bấm thường: hết chọn nhiều, sang đúng tấm đó, nút Sync đã chọn tắt",
         w.luoi.ds_chon() == [q[1]] and w._anh_dang == q[1]
         and w.btn_sync_chon.cget("state") == "disabled", str(ten_chon()))
    bam(3, 0x1)
    ktra("Shift + bấm: chọn cả dãy, tấm đang xem không đổi",
         w.luoi.ds_chon() == q[1:4] and w._anh_dang == q[1], str(ten_chon()))
    #[[ 4/10 trua — user: "khi bam vao 1 anh o duoi luoi anh thi can hien thi
    #   ngay tren khung to". May user bat NumLock: Windows gan bit 0x8 (Mod1)
    #   vao MOI lan bam, va "<Command-Button-1>" ngoai Mac la "<Mod1-Button-1>"
    #   -> bam thuong thanh "chon them", anh lon dung yen (anh chup man hinh:
    #   "Sync anh da chon (2)", khung to van tam cu). Mac: 0x8 la Command that. ]]
    if str(root.tk.call("tk", "windowingsystem")) != "aqua":
        bam(4, 0x8)
        ktra("bấm thường khi NumLock bật: sang đúng tấm đó, ảnh lớn hiện NGAY tấm đó",
             w.luoi.ds_chon() == [q[4]] and w._anh_dang == q[4] and w._anh_hien == q[4]
             and Path(q[4]).name in w.lbl_ten_anh.cget("text"),
             f"{ten_chon()} · ảnh lớn {Path(w._anh_hien or '—').name} · "
             f"“{w.lbl_ten_anh.cget('text')[:30]}”")
    bam(2)
    w._ve_muc_chung()          # nut "Về mức chung" da bo khoi UI (5/10)
    chay(2)
    ktra("“Về mức chung”: tấm đang xem bỏ mức riêng, bảng về mức chung",
         "Q2.png" not in w._muc_anh and float(w.v_muc[ten0].get()) == chung0[ten0]
         and not w.luoi.ds[2].get("rieng"),
         str(sorted(w._muc_anh)))
    #[[ Ghi xuong dia THEO THU MUC VAO; doi thu muc qua lai van con, va thu muc
    #   kia khong lan sang. Vua keo (chua toi hen ghi 0,6 s) ma doi thu muc
    #   ngay thi van phai ghi NOT muc cua thu muc cu. ]]
    bam(4)
    w.v_muc[ten0].set(moi + 1)
    w.v_vao.set(str(vao2))
    tren_dia = rt.doc_muc_anh(str(vao3))
    w._dem()
    chay(4)
    o_kia = sorted(w._muc_anh)
    w.v_vao.set(str(vao3))
    w._dem()
    chay(4)
    ktra("mức riêng ghi xuống đĩa theo thư mục vào (vừa kéo xong đổi thư mục vẫn ghi)",
         sorted(tren_dia) == ["Q0.png", "Q4.png"]
         and (tren_dia.get("Q4.png") or {}).get(ten0) == moi + 1
         and sorted(w._muc_anh) == ["Q0.png", "Q4.png"] and "Q0.png" not in o_kia,
         f"{sorted(tren_dia)} · Q4 {ten0}={(tren_dia.get('Q4.png') or {}).get(ten0)}"
         f" · thư mục kia {o_kia}")
    bam(4)
    w.v_muc[ten0].set(moi)
    chay(2)
    #[[ Sync tat ca HOI LAI khi sap xoa muc rieng cua tam KHAC muc; huy la khong
    #   doi gi. Dong y: moi anh theo dung muc tam dang xem, thanh muc chung. ]]
    bam(1)
    w.v_muc[ten0].set(moi + 10)
    chay(2)
    bam(0)
    hoi = []
    ag.messagebox.askokcancel = lambda *a, **k: (hoi.append(" ".join(map(str, a))), False)[1]
    try:
        w._sync_het()  # nut da go khoi UI; goi thang ham
    finally:
        ag.messagebox.askokcancel = hoi_that
    chay(2)
    ktra("Sync tất cả: hỏi lại khi sắp xoá mức riêng của tấm KHÁC; huỷ thì không đổi gì",
         len(hoi) == 1 and "1 ảnh khác" in hoi[0]
         and sorted(w._muc_anh) == ["Q0.png", "Q1.png", "Q4.png"], str(sorted(w._muc_anh)))
    ag.messagebox.askokcancel = lambda *a, **k: True
    try:
        w._sync_het()  # nut da go khoi UI; goi thang ham
    finally:
        ag.messagebox.askokcancel = hoi_that
    chay(2)
    w._luu_muc()
    #[[ 5/10: muc chung nam o file CUA THU MUC VAO, khong o retouch.json. ]]
    mc = rt.doc_muc_chung(str(vao3))
    ktra("Sync tất cả: mọi ảnh theo mức tấm đang xem, thành MỨC CHUNG của thư mục",
         not w._muc_anh and not any(o.get("rieng") for o in w.luoi.ds)
         and float(mc.get(ten0, -1)) == moi
         and rt.giong_muc(w._muc_chung_day_du(), w.muc_day_du())
         and not rt.doc_muc_anh(str(vao3)), f"mức chung {ten0}={mc.get(ten0)}")
    # ------------- chạy theo nhóm mức
    bam(1)
    w.v_muc[ten0].set(moi + 10)                 # Q1: mức riêng
    bam(3)
    for t in list(w.v_muc):                     # Q3: tắt hết (không retouch)
        w.v_muc[t].set(0)
    for k, b in list(w.v_bat_rieng.items()):
        if b.get():
            b.set(False)
            w._doi_bat_rieng(k)
    chay(2)
    goi = []

    def chay_gia(goc, thu_muc, ra, muc, **kw):
        anh = sorted(p.name for p in Path(thu_muc).iterdir() if p.suffix == ".png")
        cung = all(os.stat(Path(thu_muc) / a).st_ino == os.stat(vao3 / a).st_ino
                   for a in anh)
        goi.append((str(thu_muc), anh, dict(muc), cung, dict(kw)))
        Path(ra).mkdir(parents=True, exist_ok=True)
        for a in anh:
            Image.open(Path(thu_muc) / a).point(lambda v: 255 - v).save(Path(ra) / a)
        yield ("ma", 0)

    def chay_start():
        w.rt.chay = chay_gia
        threading.Thread = _ChayLien
        try:
            w.start()
        finally:
            threading.Thread = luong_that
            w.rt.chay = chay_that
        chay(4)

    hoi = []
    ag.messagebox.askokcancel = lambda *a, **k: (hoi.append(" ".join(map(str, a))), True)[1]
    try:
        chay_start()
    finally:
        ag.messagebox.askokcancel = hoi_that
    tam = Path(tmp) / ".autotone_retouch_tam"
    q1 = w._loc_muc(w._muc_hieu_luc(q[1]))
    ktra("ảnh khác mức: mỗi nhóm MỘT lượt chạy của tool, đúng ảnh, đúng mức",
         len(goi) == 2 and goi[0][1] == ["Q0.png", "Q2.png", "Q4.png", "Q5.png"]
         and goi[1][1] == ["Q1.png"] and goi[0][2].get(ten0) == moi
         and rt.giong_muc(goi[1][2], q1),
         " | ".join(f"{g[1]} {g[2].get(ten0)}" for g in goi))
    ktra("…mỗi lượt trên thư mục tạm cạnh thư mục vào, ảnh là liên kết cứng",
         bool(goi) and all(g[0].startswith(str(tam)) and g[3] for g in goi),
         goi[0][0] if goi else "—")
    ktra("nhóm mức 0 hết: KHÔNG gọi tool, chép nguyên bản sang thư mục ra",
         (ra3 / "Q3.png").is_file()
         and (ra3 / "Q3.png").read_bytes() == (vao3 / "Q3.png").read_bytes()
         and not any("Q3.png" in g[1] for g in goi))
    ktra("chạy xong: thư mục tạm đã xoá, thư mục ra đủ ảnh",
         not tam.exists() and rt.dem(vao3, ra3) == (6, 6), str(rt.dem(vao3, ra3)))
    ktra("hỏi lại trước khi chạy theo nhóm, kể từng nhóm",
         bool(hoi) and "2 lượt" in hoi[-1] and "mức 0 hết" in hoi[-1], (hoi or ["—"])[-1][:90])
    #[[ Thu muc TRUNG TEN thu muc tam ma KHONG co file moc la cua nguoi dung:
    #   khong bao gio xoa, lay ten khac. ]]
    rieng = Path(tmp) / "goc_rieng"
    (rieng / "xuat").mkdir(parents=True)
    cua_ho = rieng / ".autotone_retouch_tam"
    cua_ho.mkdir()
    (cua_ho / "anh_cua_ho.jpg").write_bytes(b"anh that")
    d_tam = rt.tao_thu_muc_tam(rieng / "xuat")
    con_nguyen = (cua_ho / "anh_cua_ho.jpg").is_file()
    xoa_ho = rt.don_thu_muc_tam(cua_ho)
    ktra("thư mục trùng tên thư mục tạm mà KHÔNG phải của app: không đụng tới",
         con_nguyen and d_tam != cua_ho and not xoa_ho
         and (cua_ho / "anh_cua_ho.jpg").is_file()
         and rt.don_thu_muc_tam(d_tam) and not d_tam.exists(),
         f"thư mục tạm lấy tên {d_tam.name}")
    #[[ Ghi de ma anh khac muc: tu choi — chay theo nhom la chay tren thu muc
    #   tam, ghi de o do khong biet anh goc that co doi khong. ]]
    loi = []
    loi_that = ag.messagebox.showerror
    ag.messagebox.showerror = lambda *a, **k: loi.append(" ".join(map(str, a)))
    ag.messagebox.askokcancel = lambda *a, **k: True
    w.v_ghide.set(True)
    w._doi_ghide()
    goi.clear()
    try:
        chay_start()
    finally:
        ag.messagebox.showerror = loi_that
        ag.messagebox.askokcancel = hoi_that
        w.v_ghide.set(False)
        w._doi_ghide()
    ktra("ghi đè mà ảnh khác mức: từ chối, không chạy gì",
         not goi and bool(loi) and "MỘT mức" in loi[-1], (loi or ["—"])[-1][:60])
    #[[ Moi anh cung muc (truong hop thuong): MOT luot thang tren thu muc vao
    #   — y het truoc khi co muc rieng tung anh. ]]
    bam(0)
    ag.messagebox.askokcancel = lambda *a, **k: True
    try:
        w._sync_het()  # nut da go khoi UI; goi thang ham
        w.v_lamlai.set(True)
        goi.clear()
        chay_start()
    finally:
        ag.messagebox.askokcancel = hoi_that
        w.v_lamlai.set(False)
    ktra("mọi ảnh cùng mức: MỘT lượt thẳng trên thư mục vào (như trước)",
         len(goi) == 1 and goi[0][0] == str(vao3) and goi[0][4].get("lam_lai") is True
         and len(goi[0][1]) == 6, " | ".join(f"{g[0]} {len(g[1])} ảnh" for g in goi))
    #[[ Ten tep DAI + muc rieng (dong pham vi dai nhat, co nut "Về mức chung"):
    #   bang dieu khien KHONG duoc phinh ra — phinh la anh lon / dai anh nhay
    #   cot. Anh chup 4/10 bat duoc: ban dau nut nam cung dong voi ten tep. ]]
    vao4 = Path(tmp) / "xuat4"
    vao4.mkdir()
    Image.new("RGB", (600, 400), (90, 100, 150)).save(
        vao4 / "SAY-Media-Wedding-Le-Thanh-Hon-Nha-Hang-08865.png")
    w.v_ra.set(str(Path(tmp) / "xuat4_ra"))
    w.v_vao.set(str(vao4))
    w._dem()
    cho_anh()
    chay(4)
    w.v_muc[ten0].set(moi + 5)
    chay(8)
    ktra("tên tệp dài + mức riêng: bảng điều khiển không phình ra",
         app.ben_phai.winfo_width() == rong_rt
         and "mức riêng" in w.lbl_pham_vi.cget("text"),
         f"{app.ben_phai.winfo_width()} px (chuẩn {rong_rt})")

    app._chon_khau("phan_tich")
    for _ in range(4):
        root.update_idletasks()
        root.update()
    rong_tone = app.ben_phai.winfo_width()
    ktra("đổi mô-đun thì bảng điều khiển không đổi bề ngang",
         rong_tone == rong_rt and app.btn_analyze.winfo_ismapped()
         and not w.btn_run.winfo_ismapped(), f"Cân tone {rong_tone} px · Retouch {rong_rt} px")

    #[[ NUT RESET VE 0 (5/10) — dat o CUOI de khong lam lech trinh tu test tren.
    #   Keo mot thanh > 0 roi bam Reset: moi thanh ve 0, moi muc rieng theo nhom
    #   tat het. Nut nam o thanh cong cu DUOI bang keo (cung hang Sync). ]]
    app._chon_khau("retouch")
    for _ in range(4):
        root.update_idletasks()
        root.update()
    if hasattr(w, "btn_reset"):
        w.v_muc[ten0].set(80)
        for _ in range(3):
            root.update_idletasks(); root.update()
        w.btn_reset.invoke()
        for _ in range(3):
            root.update_idletasks(); root.update()
        het0 = all(float(v.get()) == 0.0 for v in w.v_muc.values())
        khong_rieng = not any(b.get() for b in w.v_bat_rieng.values())
        #[[ Nut nam trong o_duoi (pack sau bang keo). Khong kiem winfo_ismapped:
        #   nhom "Muc ap dung" co the thu gon tuy trang thai test. Kiem nut CO
        #   TON TAI va chuc nang Reset chay dung (het0 + khong_rieng). ]]
        co_nut = w.btn_reset.winfo_exists()
        ktra("Reset về 0: mọi thanh của ảnh đang xem về 0",
             het0 and khong_rieng and co_nut,
             f"het0={het0} khong_rieng={khong_rieng} co_nut={bool(co_nut)}")
        #[[ 5/10: Reset + Sync DOCK o thanh day co dinh cot phai (ngoai vung
        #   cuon), bo nut "Về mức chung". ]]
        day = str(app.chan_phai_rt_trong)
        ktra("Reset + Sync dock ở đáy cột phải (ngoài vùng cuộn), hiện ở Retouch",
             str(w.btn_reset.master) == day and str(w.btn_sync_chon.master) == day
             and bool(app.chan_phai_rt.winfo_ismapped())
             and bool(w.btn_reset.winfo_ismapped()),
             f"master={w.btn_reset.master} · day_hien={app.chan_phai_rt.winfo_ismapped()}")
        ktra("bỏ nút “Về mức chung”", not hasattr(w, "btn_ve_chung"))
        app._chon_khau("phan_tich")
        for _ in range(3):
            root.update_idletasks(); root.update()
        ktra("sang Cân tone: thanh đáy Retouch ẩn",
             not app.chan_phai_rt.winfo_ismapped())

    else:
        LOI.append("Reset về 0: KHÔNG thấy nút btn_reset")

    #[[ 5/10 — KHOA RETOUCH KHI DANG TAI BAN GPU NGAM (user: "tai va cai day du
    #   moi cho dung Retouch"). Ban ma nguon khong tu tai (khong frozen) nen
    #   gia lap trang thai cua _bat_tai_gpu_ngam roi bom tin nhu luong tai. ]]
    import queue as _queue

    def bom(n=4):
        for _ in range(n):
            root.update_idletasks()
            root.update()

    app._chon_khau("phan_tich")
    bom()
    app._gpu_q = _queue.Queue()
    app._gpu_tt, app._gpu_loi = "dang_tai", ""
    app._gpu_tien = ("tai", 500_000_000, 2_300_000_000)
    app._chon_khau("retouch")
    bom()
    ktra("đang tải GPU: vào Retouch thấy trang chờ, KHÔNG thấy bảng điều khiển / nút Chạy",
         app.khoa_rt.winfo_ismapped() and not app.khung_ngoai["retouch"].winfo_ismapped()
         and not app.ben_phai.winfo_ismapped() and not app.cc_phai_rt.winfo_ismapped()
         and "22%" in app._krt["tt"].cget("text"), app._krt["tt"].cget("text"))
    app._gpu_q.put(("loi", "URLError: khong co mang"))
    app._bom_gpu()
    bom()
    ktra("tải lỗi: nói lỗi + có nút Thử lại / Dùng tạm bằng CPU",
         app.khoa_rt.winfo_ismapped() and app._krt["nut"].winfo_ismapped()
         and "khong co mang" in app._krt["tt"].cget("text"), app._krt["tt"].cget("text"))
    app._gpu_tt = "dang_tai"
    app._gpu_q.put(("xong",))
    app._bom_gpu()
    bom()
    ktra("tải xong: Retouch TỰ MỞ (trang thật + bảng điều khiển), trang chờ ẩn",
         not app.khoa_rt.winfo_ismapped() and app.khung_ngoai["retouch"].winfo_ismapped()
         and app.ben_phai.winfo_ismapped() and app.cc_phai_rt.winfo_ismapped())
    app._gpu_tt, app._gpu_bo_qua = "loi", True
    app._chon_khau("phan_tich")
    bom()
    app._chon_khau("retouch")
    bom()
    ktra("tải lỗi + chọn “Dùng tạm bằng CPU”: Retouch mở bình thường",
         not app.khoa_rt.winfo_ismapped() and app.khung_ngoai["retouch"].winfo_ismapped())
    app._gpu_tt, app._gpu_bo_qua = "", False

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
