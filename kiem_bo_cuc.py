"""Kiểm bố cục kiểu Evoto bằng cách ĐỌC MÃ NGUỒN — không cần mở cửa sổ.

NHỮNG THỨ FILE NÀY CANH

  1. MỌI KHOÁ MÀU CÓ THẬT.
     gd.MAU["tin"] không tồn tại chỉ nổ lúc chạy tới dòng đó — có khi là một
     nhánh hiếm, nổ giữa lúc người dùng đang làm việc.

  2. NHÃN KHÔNG BỊ CẮT CỤT, CHỮ PHỤ VÀO DẤU ?.
     Lỗi cắt chữ đã xảy ra hai lần ("Dua mat ve muc sang ch"). Bảng điều khiển
     phải rộng theo NỘI DUNG (ô chọn dài nhất), không có width= cố định nào
     trên nhãn; chữ giải thích nằm trong dấu ?, chữ còn in ra thì xuống dòng.

  3. NHỮNG THỨ ĐÃ GỠ THÌ PHẢI GỠ HẲN.
     Nút "2 · Ghi vào .xmp" trùng lệnh, "Tự động theo dõi", cột trái bảy khâu,
     "Chạy hết", "Khâu khác"... Còn sót một tham chiếu là app không mở lên được
     — mà lỗi đó chỉ lộ ra khi bấm, không lộ lúc import. Và CÂU CHỈ ĐƯỜNG cũng
     phải gỡ theo: hộp thoại bảo "bấm Enter ở ô thư mục" khi ô đó không còn là
     chỉ người dùng vào ngõ cụt.

  4. KHUNG KIỂU EVOTO (3/10 tối — user: "tham khảo giao diện của Evoto để
     thiết kế lại toàn bộ giao diện").
     Thanh công cụ (buổi ▾ · lần gửi · Phân tích · Ghi · ⋯), lưới ảnh giữa,
     bảng điều khiển phải, cột mô-đun, thanh trạng thái MỘT dòng. Vẫn đúng MỘT
     nút gọi do_apply trong cả app.

  5. HAI LỖI IM LẶNG NGÀY 7/9 vẫn phải hiện ra (plugin chết, bản xuất cũ hơn
     lần ghi) — dải cảnh báo trên cùng, vòng làm mới 4 giây thật sự chạy.

Chạy:  python kiem_bo_cuc.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parent
LOI: list[str] = []


def ktra(ten: str, dieu: bool, mo: str = "") -> None:
    if dieu:
        print(f"  {ten:<58} {mo or 'đạt'}")
    else:
        LOI.append(f"{ten}: {mo}")


def than(ten_ham: str, src: str, cay: ast.AST) -> str:
    for n in ast.walk(cay):
        if isinstance(n, ast.FunctionDef) and n.name == ten_ham:
            return ast.get_source_segment(src, n) or ""
    return ""


def kiem_khoa_mau(ktra) -> None:
    """Mọi khoá dùng trong gd.MAU[...] ở mã nguồn phải là khoá CÓ THẬT.

    #[[ VI SAO CAN BAI NAY.
    #
    #   gd.MAU["tin"] khong ton tai. Python chi no luc CHAY TOI dong do — ma
    #   dong do nam trong mot nhanh hiem (bao trang thai sau khi gui yeu cau
    #   Export), nen no ngoi im trong ma nguon qua ca mot dot sua, roi no giua
    #   luc nguoi dung dang lam viec. Kiem tinh thi bat duoc ngay.
    #]]
    """
    import giao_dien as _gd
    sai = []
    for ten in ("autotone_gui.py", "man_retouch.py", "hop_thoai.py", "cua_saytool.py",
                "duyet_ui.py", "giao_dien.py", "luoi_anh.py"):
        f = GOC / ten
        if not f.is_file():
            continue
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if (isinstance(n, ast.Subscript)
                    and isinstance(n.value, (ast.Attribute, ast.Name))
                    and getattr(n.value, "attr", getattr(n.value, "id", "")) == "MAU"
                    and isinstance(n.slice, ast.Constant)
                    and isinstance(n.slice.value, str)
                    and n.slice.value not in _gd.MAU):
                sai.append(f"{ten}:{n.lineno} MAU[{n.slice.value!r}]")
    ktra("mọi khoá màu dùng trong mã đều có thật", not sai,
         " | ".join(sai) if sai else f"{len(_gd.MAU)} khoá trong bảng màu")


def chuoi_nguoi_doc(cay: ast.AST) -> list[tuple[int, str]]:
    """Mọi hằng chuỗi KHÔNG phải docstring — tức chữ có thể hiện ra cho người
    dùng (nhãn, hộp thoại, dòng trạng thái). Docstring và chú thích # là lịch
    sử cho người đọc mã, được phép nhắc tên cũ."""
    doc = set()
    for n in ast.walk(cay):
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef,
                          ast.AsyncFunctionDef)) and n.body:
            dau = n.body[0]
            if isinstance(dau, ast.Expr) and isinstance(dau.value, ast.Constant) \
                    and isinstance(dau.value.value, str):
                doc.add(id(dau.value))
    ra = []
    for n in ast.walk(cay):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) \
                and id(n) not in doc:
            ra.append((n.lineno, n.value))
    return ra


def main() -> int:
    kiem_khoa_mau(ktra)
    src = (GOC / "autotone_gui.py").read_text(encoding="utf-8")
    cay = ast.parse(src)
    gd_src = (GOC / "giao_dien.py").read_text(encoding="utf-8")
    gd_cay = ast.parse(gd_src)
    lop_app = next((n for n in ast.walk(cay) if isinstance(n, ast.ClassDef)
                    and n.name == "App"), None)
    ktra("tìm được lớp App", lop_app is not None)
    if lop_app is None:
        return 1

    def lop(ten):
        for n in ast.walk(gd_cay):
            if isinstance(n, ast.ClassDef) and n.name == ten:
                return ast.get_source_segment(gd_src, n) or ""
        return ""

    bo = than("_build_options", src, cay)
    sh = than("_build_shell", src, cay)
    gh = than("_build_ghi", src, cay)
    ac = than("_build_actions", src, cay)
    fo = than("_build_folder", src, cay)
    st = than("_build_status", src, cay)
    sb = than("_set_busy", src, cay)
    init = than("__init__", src, lop_app)
    ktra("tìm được các hàm dựng khung", all((bo, sh, gh, ac, fo, st, sb, init)),
         f"_build_options {len(bo.splitlines())} dòng · _build_shell "
         f"{len(sh.splitlines())} dòng")

    # ---------------- 2. không cắt chữ, chữ phụ vào dấu ?
    #[[ Bang dieu khien phai rong theo NOI DUNG: o chon dai nhat (gd.vua_chu)
    #   quyet dinh be ngang, Cuon.theo_noi_dung() cho cot rong theo no. Mot
    #   width= tren nhan la Tk cat cut chu dai hon — da do that: ttk.Label
    #   (width=15) cat "Tach canh khi cach". ]]
    ktra("ô chọn rộng đúng chữ dài nhất (gd.vua_chu)", "gd.vua_chu(cb)" in bo,
         "chữ trong ô chọn không bị cắt")
    ktra("bảng điều khiển phải rộng theo nội dung",
         "self.cuon_phai.theo_noi_dung()" in sh, "không số px cứng nào")
    ktra("không đặt width cố định cho nhãn",
         "ttk.Label(" in bo and "text=nhan, width=" not in bo
         and "text=chu, width=" not in bo,
         "Tk cắt cụt chữ dài hơn width")
    #[[ Mo / dong nhom KHONG duoc doi be ngang cot: cot rong theo noi dung ma
    #   than nhom dong khong tinh vao -> mo "Cach can tone" la cot phinh ~90 px
    #   va ca luoi anh nhay cot. Do than rong nhat (do duoc ca khi dong) roi
    #   chong mot thanh chan dung be ngang ay. ]]
    ktra("bề ngang bảng điều khiển không đổi khi mở / đóng nhóm",
         "n.than.winfo_reqwidth()" in bo and "ttk.Frame(cha, width=rong" in bo,
         "đo thân nhóm rộng nhất, chống một thanh chân")
    #[[ 3/10: chu giai thich KHONG con in san duoi tung tinh nang ma vao dau ?
    #   (gd.NutHoi) — user: "di chuot vao moi hien, cho gon giao dien". Kieu
    #   Mo2.TLabel trong _build_options chinh la chu phu in san cu. Chu nao CON
    #   in ra (canh bao "khong tach canh", dong tom tat nhom) phai co
    #   wraplength — thieu no la cat cut. ]]
    ktra("không còn dòng chữ phụ in sẵn dưới tính năng",
         'style="Mo2.TLabel"' not in bo, "chú thích nằm trong dấu ? cạnh tính năng")
    ktra("chữ còn in ra trong bảng điều khiển đều xuống dòng",
         "wraplength=WRAP" in bo and "WRAP = " in bo
         and "l_tom.configure(wraplength=" in bo,
         "cảnh báo tách cảnh + dòng tóm tắt nhóm")
    ktra("chú thích nổi (GoiY) và dòng tóm tắt nhóm (Nhom) đều xuống dòng",
         "wraplength=self.RONG" in lop("GoiY") and "wraplength=" in lop("Nhom"),
         "chú thích dài bao nhiêu cũng không tràn")
    so_hoi = bo.count("hoi(")
    ktra("dấu ? dựng qua một hàm chung hoi()", so_hoi >= 4,
         f"{so_hoi} chỗ gọi — ct / hop / so / nhóm viên chọn đều đi qua nó")

    # ---------------- 3. những thứ đã gỡ phải gỡ hẳn
    #[[ Soi TEN TRONG MA (bien, thuoc tinh, ham, lop) chu khong grep ca file:
    #   docstring ke lich su "roi ba cot tu co (_xep_cot)" la chuyen cho nguoi
    #   doc ma, khong phai mot tham chieu se no. ]]
    ten_ma = set()
    for n in ast.walk(cay):
        if isinstance(n, ast.Name):
            ten_ma.add(n.id)
        elif isinstance(n, ast.Attribute):
            ten_ma.add(n.attr)
        elif isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            ten_ma.add(n.name)
    for ten in ("btn_apply", "WatchWindow", "open_watcher", "_watch_win",
                "ray", "Ray", "_xep_cot", "KHAU_CHINH", "start_all",
                "menu_khau_khac", "_cot_tuy_chon", "_so_cot_hien"):
        ktra(f"không còn tham chiếu {ten}",
             ten not in ten_ma, "sót một chỗ là app không mở lên được")
    #[[ CAU CHI DUONG phai go theo cai no chi. 3/10 toi: hop thoai van bao
    #   "bam Enter o o thu muc" (o do da thanh nut buoi), "xem dong trang thai o
    #   khau 1", "Doi o Nguon o tren" — nguoi dung lam theo la vao ngo cut. Chi
    #   soi CHU HIEN RA (hang chuoi khong phai docstring); chu thich # va
    #   docstring duoc phep ke lich su. ]]
    cu = ("Khâu khác", "khâu 1", "Enter ở ô thư mục", "dưới nút Ghi",
          "cột trái", "Chạy hết", "ô “Nguồn” ở trên")
    sot = [f"{ln}:{t[:40]}" for ln, t in chuoi_nguoi_doc(cay)
           for c in cu if c in t and not t.startswith("Chạy hết: đo xong")
           and t != "Chạy hết — xong"]
    #[[ Hai chuoi "Chay het…" con lai la cua DUONG GHI TU DONG (self.chuoi),
    #   chi chay khi co ai bat lai co do — giu de khoi dung lai tu dau. ]]
    ktra("không còn câu chỉ đường tới thứ đã gỡ", not sot,
         " | ".join(sot[:4]) if sot else "nút buổi ▾ · dải báo · cạnh nút Ghi")

    # ---------------- 4. khung kiểu Evoto
    ktra("mở app lên là vào trang chính (lưới ảnh)",
         '_chon_khau("phan_tich")' in init and '_chon_khau("nap")' not in init
         and '_chon_khau("tong_quan")' not in init, "không còn khâu Nạp ảnh riêng")
    ktra("thanh công cụ · thân · cột mô-đun · thanh trạng thái",
         all(t in sh for t in ("self.thanh_cc", "self.ben_phai", "gd.ThanhMoDun(",
                               "self.thanh_tt", "self.lbl_han")),
         "hạn dùng LUÔN hiện ở thanh trạng thái")
    ktra("cột mô-đun có Cân tone và Retouch",
         '("tone",' in sh and '("retouch",' in sh, "như Portrait / Background của Evoto")
    #[[ Dem MOI cho truyen command=self.do_apply trong ca lop App (nut ttk, nut
    #   ve tay, muc menu...). Doi nut thi de nham thanh "them nut moi, quen go
    #   nut cu" — dung cai benh hai nut mot viec, _set_busy phai nho khoa ca
    #   hai. Doc cay cu phap, khong grep: chu thich nhac "do_apply" khong tinh. ]]
    goi_ghi = []
    for n in ast.walk(lop_app):
        if isinstance(n, ast.Call):
            for k in n.keywords:
                if k.arg == "command" and isinstance(k.value, ast.Attribute) \
                        and k.value.attr == "do_apply" \
                        and isinstance(k.value.value, ast.Name) \
                        and k.value.value.id == "self":
                    goi_ghi.append(n.lineno)
    ktra("cả app chỉ có MỘT chỗ gọi do_apply", len(goi_ghi) == 1,
         f"{len(goi_ghi)} chỗ (dòng {goi_ghi}) — nút vàng trên thanh công cụ")
    ktra("nút Ghi là nút vẽ tay trên thanh công cụ",
         "self.btn_ghi3 = gd.NutTron(cha" in gh and "self._build_ghi(self.cc_phai)" in src,
         "cạnh “1 · Phân tích”")
    nut_cc = []
    for n in ast.walk(ast.parse(ac)):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr in ("NutTron", "Button"):
            for k in n.keywords:
                if k.arg == "command" and isinstance(k.value, ast.Attribute):
                    nut_cc.append(k.value.attr)
    ktra("_build_actions chỉ dựng hai nút: Phân tích và Dừng",
         sorted(nut_cc) == ["do_cancel", "start_analyze"], f"{sorted(nut_cc)}")
    ktra("Xuất CSV, Duyệt nhanh nằm trong menu ⋯ cạnh nút Ghi",
         "self.do_csv" in gh and "Xuất báo cáo CSV" in gh
         and '_chon_khau("day")' in gh, "việc phụ không chiếm thanh công cụ")
    #[[ Dong lan gui NGAY CANH nut Ghi (giua thanh cong cu), MOT dong — cau dai
    #   cat "…" va hien du khi re chuot. Xuong dong la ca thanh cong cu phinh. ]]
    ktra("dòng trạng thái lần gửi cạnh nút Ghi, một dòng",
         "self.lbl_job = gd.NhanGon(self.cc_giua" in gh, "câu dài cắt “…”, rê chuột hiện đủ")
    ktra("thanh trạng thái một dòng",
         "self.lbl_status = gd.NhanGon(self.ttb_giua" in st,
         "không phình ra khi câu dài")
    #[[ Dai bao cua buoi: dong tinh trang quet KHONG con o thanh cong cu (cau
    #   dai xuong 2-3 dong do, keo cao ca thanh). ]]
    ktra("tình trạng quét nằm ở dải báo trên lưới ảnh",
         "gd.DaiBao(self.giua" in sh and "self.lbl_scan = self.dai_quet.nhan" in fo
         and "self.btn_fix = self.dai_quet.tao_nut(" in fo
         and "self.cc_giua" not in fo, "không còn ở thanh công cụ")
    ktra("Retouch không mang dải báo của Cân tone",
         'self.dai_quet.hien(md == "tone")' in than("_chon_khau", src, cay),
         "dải chỉ nói chuyện buổi đang cân")
    #[[ _set_busy() chay TRONG __init__ truoc khi nut Ghi dung xong, nen phai
    #   dung getattr — khong thi app chet ngay luc mo. ]]
    ktra("_set_busy dùng getattr cho nút Ghi", "getattr(self" in sb,
         "_set_busy chạy trước khi nút Ghi dựng xong")
    ktra("nút vàng là việc kế tiếp (Phân tích ↔ Ghi)",
         'kieu="chinh" if (co_anh and not co_kq) else "phu"' in sb
         and 'kieu="chinh" if co_kq else "phu"' in sb, "như nút Export của Evoto")

    # ---------------- 4b. lưới ảnh
    lu = than("_cap_nhat_luoi", src, cay)
    ktra("lưới ảnh là chế độ xem mặc định",
         "luoi_anh.LuoiAnh(" in than("_build_luoi", src, cay)
         and 'tk.StringVar(value="luoi")' in than("_build_table", src, cay),
         "bảng số thành chế độ xem phụ")
    ktra("lưới hiện cả ảnh SẼ KHÔNG được ghi, kèm lý do",
         '"thiếu .xmp"' in lu and '"không ghi"' in lu and '"missing"' in lu,
         "RAW thiếu .xmp · không có trong bản xuất Lightroom")
    for ham in ("_fill_table", "_invalidate_measurements", "_soi_xuat"):
        ktra(f"{ham} vẽ lại lưới", "_cap_nhat_luoi(" in than(ham, src, cay),
             "lưới và bảng số không được nói khác nhau")

    # ---------------- 5. Tổng quan + lỗi im lặng
    for ten in ("_build_tong_quan", "_lam_moi_tong_quan", "_canh_bao_im_lang",
                "_mot_the_tq"):
        ktra(f"có {ten}", bool(than(ten, src, cay)), "dựng sẵn, chỉ không còn lối vào")
    lm = than("_lam_moi_ray", src, cay)
    ktra("vòng làm mới 4 giây cập nhật nút buổi + thẻ Tổng quan",
         "_lam_moi_tong_quan" in lm and "_dat_nut_buoi" in lm,
         "nút buổi và thẻ không được nói khác nhau")
    #[[ 3/10: vong 4 giay TUNG KHONG CHAY — dong hen lai nam lac trong
    #   _hien_khoa(). Canh ca hai dau: ham vong tu hen lai, va khong con ai
    #   khac hen _lam_moi_ray (moi lan hen la them mot vong song song). ]]
    vl = than("_vong_lam_moi", src, cay)
    ktra("vòng làm mới thật sự tự hẹn lại mỗi 4 giây",
         "self._lam_moi_ray()" in vl and "after(4000, self._vong_lam_moi)" in vl
         and "after(400, self._vong_lam_moi)" in init,
         "chọn buổi xong là mọi chỗ đổi theo")
    ktra("không chỗ nào khác tự hẹn _lam_moi_ray",
         "after(4000, self._lam_moi_ray)" not in src, "hẹn rải rác là thêm vòng song song")
    cb = than("_canh_bao_im_lang", src, cay)
    ktra("cảnh báo bắt cả hai lỗi im lặng của ngày 7/9",
         "plugin_song_khi_nao" in cb and "ban_xuat_cu_hon_lan_ghi" in cb,
         "plugin chết · bản xuất cũ hơn lần ghi")
    ktra("cảnh báo im lặng lên dải trên cùng, trang nào cũng thấy",
         "self.lbl_im_lang" in cb and "_hien_dai_canh" in cb,
         "không chỉ trên màn Tổng quan đã ẩn")

    #[[ Moi command= tro toi mot phuong thuc CO THAT. Sai ten thi khong no luc
    #   import, chi no khi bam — dung kieu loi kho doan nhat. Soi CA lop App. ]]
    co = {c.name for c in lop_app.body if isinstance(c, ast.FunctionDef)}
    thieu = set()
    for n2 in ast.walk(lop_app):
        if isinstance(n2, ast.Call):
            for k in n2.keywords:
                if k.arg in ("command", "khi_chon", "khi_mo", "khi_trong") \
                        and isinstance(k.value, ast.Attribute) \
                        and isinstance(k.value.value, ast.Name) \
                        and k.value.value.id == "self" \
                        and k.value.attr not in co \
                        and not k.value.attr.startswith(("v_", "btn_", "lbl_")):
                    thieu.add(k.value.attr)
    ktra("mọi nút / menu trỏ tới lệnh có thật", not thieu,
         f"thiếu {sorted(thieu)}" if thieu else "không có lệnh ma")

    # ---------------- 5b. mô-đun Retouch cũng theo dáng Evoto (tối 3/10)
    #[[ User: "dua ca phan Retouch thay doi luon". Tuy chon Retouch vao BANG
    #   DIEU KHIEN PHAI, nut Chay len THANH CONG CU, giua la luoi anh cua thu
    #   muc vao. Con sot mot widget kieu cu (o tick, thanh keo ttk, khung co
    #   vien) la mot manh giao dien cu lot giua giao dien moi. ]]
    #[[ 7/10 (giai doan 2): RetouchWindow nam o man_retouch.py, khong con trong
    #   autotone_gui.py — soi dung tep. ]]
    f_rt = GOC / "man_retouch.py"
    src_rt = f_rt.read_text(encoding="utf-8") if f_rt.is_file() else src
    cay_rt = ast.parse(src_rt)
    lop_rt = next((n for n in ast.walk(cay_rt) if isinstance(n, ast.ClassDef)
                   and n.name == "RetouchWindow"), None)
    ktra("tìm được lớp RetouchWindow", lop_rt is not None)
    if lop_rt is not None:
        rt_src = ast.get_source_segment(src_rt, lop_rt) or ""
        cu_rt = [t for t in ("ttk.Checkbutton(", "ttk.Scale(", "LabelFrame(",
                             "ttk.Button(", "ttk.Combobox(") if t in rt_src]
        ktra("Retouch không còn widget kiểu cũ",
             not cu_rt, f"còn {cu_rt}" if cu_rt else
             "công tắc · thanh trượt · viên chọn · nhóm thu gọn")
        init_rt = than("__init__", src_rt, lop_rt)
        ktra("Retouch nhận bảng điều khiển + thanh công cụ từ app",
             "ben=None, thanh=None" in init_rt
             and "RetouchWindow(self, cha, ben=self.cuon_phai_rt.trong" in src
             and "thanh=self.cc_phai_rt" in src, "gọi kiểu cũ RetouchWindow(app) vẫn dựng được")
        trang_rt = than("_dung_trang", src_rt, lop_rt)
        ktra("Retouch có lưới ảnh của thư mục vào",
             "luoi_anh.LuoiAnh(" in trang_rt, "")
        #[[ Toi 3/10: "1 anh mo to va luoi anh ben duoi" — anh lon (khung_anh)
        #   o tren, luoi thanh DAI anh (dai=True) o duoi, thanh chia keo duoc. ]]
        ktra("Retouch: ảnh lớn ở trên, dải ảnh ở dưới, thanh chia kéo được",
             "khung_anh.KhungAnh(" in trang_rt and "dai=True" in trang_rt
             and "tk.PanedWindow(" in trang_rt, "khung_anh · LuoiAnh(dai=True)")
        #[[ Xem truoc tinh NGAY TREN ANH LON, khong mo cua so thu hai co anh
        #   lon va thanh keo rieng. ]]
        xt_py = (GOC / "xem_truoc.py").read_text(encoding="utf-8")
        ktra("không còn cửa sổ Xem trước riêng",
             "Toplevel" not in xt_py and "class MayXem" in xt_py,
             "xem_truoc.py chỉ còn máy tính ảnh")
        #[[ Bam Chay: tat may xem truoc TRUOC khi khoi luong chay — hai bo mo
        #   hinh tren mot card do hoa la duong ngan nhat toi OOM. ]]
        #[[ 7/10: phan CHAY NEN cua start() tach thanh _chay_viec (dung chung voi
        #   luot tu retouch anh moi) — luat ve start van ap cho ca hai. ]]
        bd = than("start", src_rt, lop_rt) + "\n" + than("_chay_viec", src_rt, lop_rt)
        ktra("bấm Chạy tắt xem trước TRƯỚC khi chạy cả mẻ",
             "_tat_xem_truoc(dong_may=True)" in bd and "threading.Thread(" in bd
             and bd.index("_tat_xem_truoc(dong_may=True)") < bd.index("threading.Thread("),
             "nhường card đồ hoạ")
        #[[ Sang 4/10 — user: "bo nut xem truoc. Vi khi keo se load luon vao
        #   anh". Khong con nut tren thanh cong cu; NGUOI keo thanh (khong phai
        #   luc nap muc cua mot tam) la tu bat xem truoc. ]]
        cc_rt = than("_dung_thanh_cong_cu", src_rt, lop_rt)
        ktra("Retouch không còn nút “Xem trước”: kéo thanh là tự xem",
             "btn_xem" not in rt_src and "Xem trước" not in cc_rt.split('"""')[-1]
             and "self._nguoi_doi_muc()" in than("_muc_doi", src_rt, lop_rt)
             and "_dang_nap_muc" in than("_muc_doi", src_rt, lop_rt)
             and "_mo_xem_truoc(tu_dong=True)" in than("_nguoi_doi_muc", src_rt, lop_rt),
             "_muc_doi → _nguoi_doi_muc → _mo_xem_truoc(tu_dong)")
        #[[ "Sync All cac hieu ung da keo cho cac anh duoc chon hoac tat ca":
        #   dai anh chon nhieu duoc, bang co nut Sync. 5/10 user bo nut "Sync tat
        #   ca" ("Nut Sync se mac dinh Sync cho cac anh duoc chon. K can toi nut
        #   Sync Tat ca") — chi con Sync anh da chon (Ctrl+A = tat ca). ]]
        ktra("dải ảnh Retouch chọn nhiều tấm được, bảng có Sync ảnh đã chọn",
             "chon_nhieu=True" in trang_rt and "self._sync_chon" in rt_src,
             "Ctrl / Shift + bấm · Sync")
        #[[ Chay theo nhom muc van di qua CHINH lenh `chay` cua saytool — moi
        #   nhom mot luot rt.chay, KHONG dung lai buoc nao ben nay. 6/10: ghi de
        #   nhieu nhom KHONG con tu choi — tool ghi ra thu muc tam rieng, app
        #   tu thay anh goc (rt.dua_ket_qua_ra). ]]
        ktra("ảnh khác mức chạy theo nhóm, mỗi nhóm một lượt rt.chay",
             "self.rt.nhom_theo_muc(" in bd and bd.count("self.rt.chay(") == 1
             and "self.rt.dua_ket_qua_ra(" in bd and "ghi_de and len(nhom) > 1" not in bd,
             "không dựng lại bước của saytool")
        #[[ Luoi va bo dem PHAI doc cung mot danh sach (rt.ds_anh) — hai cach
        #   loc la hai noi co the lech nhau, va khi lech khong ai biet ben nao
        #   dung (chu thich dau lop RetouchWindow). ]]
        rt_py = (GOC / "retouch.py").read_text(encoding="utf-8")
        dem_py = rt_py[rt_py.index("def dem("):rt_py.index("def lenh(")]
        ktra("lưới và bộ đếm đọc cùng một danh sách (rt.ds_anh)",
             "self.rt.ds_anh(" in than("_dem", src_rt, lop_rt)
             and "ds = ds_anh(vao, ra, de_quy)" in dem_py, "một chỗ quyết định")
        ds_py = rt_py[rt_py.index("def ds_anh("):rt_py.index("def dem(")]
        ktra("nhãn “đã làm” và bản ảnh lớn mở theo một luật (rt.duong_ket_qua)",
             "duong_ket_qua(" in ds_py
             and "self.rt.duong_ket_qua(" in than("_duong_kq", src_rt, lop_rt),
             "một chỗ quyết định")
        co_rt = {c.name for c in lop_rt.body if isinstance(c, ast.FunctionDef)}
        lop_khung = next((n for n in ast.walk(cay) if isinstance(n, ast.ClassDef)
                          and n.name == "Khung"), None)
        if lop_khung is not None:
            co_rt |= {c.name for c in lop_khung.body if isinstance(c, ast.FunctionDef)}
        thieu_rt = set()
        for n2 in ast.walk(lop_rt):
            if isinstance(n2, ast.Call):
                for k in n2.keywords:
                    if k.arg in ("command", "khi_mo", "khi_trong", "khi_chon",
                                 "khi_doi", "khi_phim") \
                            and isinstance(k.value, ast.Attribute) \
                            and isinstance(k.value.value, ast.Name) \
                            and k.value.value.id == "self" \
                            and k.value.attr not in co_rt:
                        thieu_rt.add(k.value.attr)
        ktra("mọi nút / menu của Retouch trỏ tới lệnh có thật", not thieu_rt,
             f"thiếu {sorted(thieu_rt)}" if thieu_rt else "không có lệnh ma")

    # ---------------- 6. đường CLI --watch phải còn nguyên
    at_src = (GOC / "autotone.py").read_text(encoding="utf-8")
    ktra("CLI --watch vẫn còn trong autotone.py",
         "--watch" in at_src and "class Watcher" in at_src,
         "chỉ gỡ giao diện, không gỡ tính năng")

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
