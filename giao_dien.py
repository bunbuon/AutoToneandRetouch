#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""giao_dien.py — Bảng màu, kiểu widget và cột trái bảy khâu cho AutoTone.

VÌ SAO NỀN TỐI
    Không phải vì mốt. Người thao tác đang phán đoán màu da và mức sáng ngay
    trong khung xem mặt, mà nền sáng làm cảm nhận độ sáng lệch đi — cùng lý do
    Lightroom và Capture One đều tối. Và cũng vì thế dải xám ở đây là xám TRUNG
    TÍNH thật: không ngả xanh, không ngả ấm. Toàn bộ màu dồn vào đúng một chỗ
    nhấn, dành cho khâu đang làm và nút chính.

VÌ SAO PHẢI theme_use("clam")
    Trên Windows, ttk mặc định dùng theme "vista" và theme đó vẽ nút, ô nhập,
    thanh cuộn bằng chính API của hệ điều hành — `style.configure(background=)`
    bị BỎ QUA hoàn toàn. Đổi sang "clam" (theme tự vẽ) mới đặt được màu. Đây là
    cái bẫy kinh điển: code trông như đã đặt màu, chạy lên vẫn trắng bóc.

NHỮNG CHỖ tkinter KHÔNG LÀM ĐƯỢC
    Bo góc thật, đổ bóng, viền nửa pixel — ttk không có. Bản dựng này thay bằng
    viền 1 px và nền phân tầng, KHÔNG cố mô phỏng. Danh sách xổ của Combobox là
    một widget Tk cổ nằm ngoài ttk nên phải nhuộm riêng bằng option_add().
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# ── Bảng màu ────────────────────────────────────────────────────────────────
MAU = {
    "nen":    "#161616",   # nền ngoài cùng
    "tam":    "#1e1e1e",   # tấm nội dung, cột trái
    "noi":    "#262626",   # ô nhập, hàng nổi
    "noi2":   "#2e2e2e",   # trạng thái rê chuột
    "vien":   "#333333",
    "vien2":  "#3d3d3d",
    "chu":    "#e7e7e7",
    "mo":     "#9a9a9a",   # chữ phụ
    "mo2":    "#6f6f6f",   # nhãn mục, chữ rất phụ
    "nhan":   "#4c9df0",   # màu nhấn duy nhất
    "nhan2":  "#63aaf3",
    "nhan_t": "#1d4e7d",   # nền chọn trong bảng
    "chu_nhan": "#07203a",  # chữ trên nút màu nhấn
    "xong":   "#45b06a",
    "canh":   "#e0a33e",
    "loi":    "#e2564d",
    "bang_canh_nen": "#3a2a10",
    "bang_canh_chu": "#f0c274",
}

# Segoe UI có sẵn trên mọi máy Windows và dựng dấu tiếng Việt đầy đủ.
# Consolas cho số liệu: chữ số đều bề ngang nên cột số thẳng hàng.
CHU = ("Segoe UI", 9)
CHU_DAM = ("Segoe UI", 9, "bold")
CHU_TO = ("Segoe UI", 12, "bold")
CHU_NHO = ("Segoe UI", 8)
CHU_SO = ("Consolas", 9)


def dat_theme(root: tk.Misc) -> ttk.Style:
    """Nhuộm toàn bộ widget ttk. Gọi MỘT lần, ngay sau khi tạo cửa sổ gốc."""
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except tk.TclError:      # máy lạ không có clam thì thôi, đừng làm sập app
        pass

    m = MAU
    root.configure(background=m["nen"])

    #[[ Danh sach xo cua Combobox va Listbox KHONG phai widget ttk — chung la
    #   widget Tk co, nen style khong voi toi. Chi option_add moi doi duoc, va
    #   phai goi TRUOC khi tao combobox dau tien.
    #]]
    root.option_add("*TCombobox*Listbox.background", m["noi"])
    root.option_add("*TCombobox*Listbox.foreground", m["chu"])
    root.option_add("*TCombobox*Listbox.selectBackground", m["nhan_t"])
    root.option_add("*TCombobox*Listbox.selectForeground", m["chu"])
    root.option_add("*TCombobox*Listbox.font", CHU)

    #[[ WIDGET TK CO — style cua ttk khong voi toi chung.
    #
    #   tk.Text, tk.Listbox, tk.Toplevel deu mac dinh NEN TRANG. Trong ban dung
    #   thu dau tien, o Nhat ky cua khung Retouch hien ra mot manh trang toat
    #   giua nen toi — dung kieu loi ma doc code khong thay, phai chay len moi
    #   biet.
    #
    #   option_add chi an voi widget tao SAU no, va chi khi noi tao khong tu dat
    #   mau. Nen goi o day, truoc khi App() dung bat cu thu gi.
    #]]
    for w in ("Text", "Listbox"):
        root.option_add(f"*{w}.background", m["tam"])
        root.option_add(f"*{w}.foreground", m["chu"])
        root.option_add(f"*{w}.selectBackground", m["nhan_t"])
        root.option_add(f"*{w}.selectForeground", m["chu"])
        root.option_add(f"*{w}.highlightThickness", 1)
        root.option_add(f"*{w}.highlightBackground", m["vien"])
        root.option_add(f"*{w}.highlightColor", m["vien"])
        root.option_add(f"*{w}.relief", "flat")
        root.option_add(f"*{w}.borderWidth", 0)
    root.option_add("*Text.insertBackground", m["chu"])
    root.option_add("*Toplevel.background", m["nen"])
    root.option_add("*Menu.background", m["noi"])
    root.option_add("*Menu.foreground", m["chu"])
    root.option_add("*Menu.activeBackground", m["nhan_t"])
    root.option_add("*Menu.activeForeground", m["chu"])

    st.configure(".", background=m["nen"], foreground=m["chu"],
                 fieldbackground=m["noi"], font=CHU,
                 bordercolor=m["vien"], darkcolor=m["nen"], lightcolor=m["nen"],
                 troughcolor=m["noi"], focuscolor=m["nhan"])

    st.configure("TFrame", background=m["nen"])
    st.configure("Tam.TFrame", background=m["tam"])
    st.configure("Noi.TFrame", background=m["noi"])

    st.configure("TLabel", background=m["nen"], foreground=m["chu"])
    #[[ Nhan bi tat (state="disabled") — vi du "Do tron:" khi che do la absolute.
    #   Khong khai bao map thi clam ve no bang mau disabled cua rieng no: mot o
    #   xam sang giua nen toi, trong nhu mot cai o nhap dang hong.
    #]]
    st.map("TLabel", background=[("disabled", m["nen"])],
           foreground=[("disabled", m["mo2"])])
    st.configure("Mo.TLabel", foreground=m["mo"])
    st.configure("Mo2.TLabel", foreground=m["mo2"], font=CHU_NHO)
    st.configure("So.TLabel", font=CHU_SO, foreground=m["mo"])
    st.configure("To.TLabel", font=CHU_TO)
    st.configure("Muc.TLabel", foreground=m["mo2"], font=("Segoe UI", 8, "bold"))
    st.configure("Xong.TLabel", foreground=m["xong"])
    st.configure("Canh.TLabel", foreground=m["canh"])
    st.configure("Loi.TLabel", foreground=m["loi"])

    # ── nút ──
    st.configure("TButton", background=m["noi"], foreground=m["chu"],
                 bordercolor=m["vien2"], relief="flat", padding=(11, 5))
    st.map("TButton",
           background=[("pressed", m["vien"]), ("active", m["noi2"]),
                       ("disabled", m["tam"])],
           foreground=[("disabled", m["mo2"])],
           bordercolor=[("active", "#4a4a4a")])

    st.configure("Chinh.TButton", background=m["nhan"], foreground=m["chu_nhan"],
                 bordercolor=m["nhan"], font=CHU_DAM, padding=(13, 6))
    st.map("Chinh.TButton",
           background=[("pressed", m["nhan_t"]), ("active", m["nhan2"]),
                       ("disabled", m["vien"])],
           foreground=[("disabled", m["mo2"])])

    #[[ Nut "pha": viec phu, khong duoc tranh mat voi nut chinh. Khong vien,
    #   khong nen — chi la chu. Dung cho Xuat CSV, Nhat ky, Cach tao .xmp...
    #]]
    st.configure("Pha.TButton", background=m["nen"], foreground=m["mo"],
                 bordercolor=m["nen"], relief="flat", padding=(6, 4))
    st.map("Pha.TButton",
           background=[("active", m["nen"]), ("pressed", m["nen"])],
           foreground=[("active", m["chu"]), ("disabled", m["mo2"])])

    # ── ô nhập ──
    for ten in ("TEntry", "TSpinbox", "TCombobox"):
        st.configure(ten, fieldbackground=m["noi"], background=m["noi"],
                     foreground=m["chu"], bordercolor=m["vien2"],
                     arrowcolor=m["mo"], insertcolor=m["chu"],
                     selectbackground=m["nhan_t"], selectforeground=m["chu"],
                     padding=(6, 4))
        st.map(ten,
               fieldbackground=[("readonly", m["noi"]), ("disabled", m["tam"])],
               foreground=[("disabled", m["mo2"])],
               bordercolor=[("focus", m["nhan"])],
               arrowcolor=[("disabled", m["mo2"])])

    #[[ O TICK — PHAI GHI DE CA BANG MAP, KHONG CHI configure().
    #
    #   clam co san map rieng cho o tick, trong do co dong:
    #       ('!disabled', '!selected', '#ffffff')
    #   Dong do EP o tick chua tick thanh mau trang, va no thang moi thu dat
    #   bang configure(). Ban dung thu dau tien dinh dung bay nay: o chua tick
    #   trang boc giua nen toi.
    #
    #   Lan sua thu hai lai hong theo huong nguoc lai: doi sang `indicatorcolor`
    #   — mot tuy chon cua theme 'alt' chu clam khong doc — nen ca o tick DA
    #   TICK cung khong hien mau, nhin nhu chua tick het. Doc sai trang thai mac
    #   dinh cua nam cong tac la dieu te hon ca hai.
    #
    #   Dung ten clam that (`indicatorbackground`) va ghi de dung nhung trang
    #   thai clam da khai bao.
    #]]
    st.configure("TCheckbutton", background=m["nen"], foreground=m["chu"],
                 indicatorbackground=m["noi"], indicatorforeground=m["chu_nhan"],
                 bordercolor=m["vien2"], focuscolor=m["nhan"], padding=(0, 3))
    st.map("TCheckbutton",
           background=[("active", m["nen"])],
           indicatorbackground=[("disabled", m["tam"]),
                                ("pressed", m["noi2"]),
                                ("selected", m["nhan"]),
                                ("!disabled", "!selected", m["noi"])],
           indicatorforeground=[("selected", m["chu_nhan"])],
           foreground=[("disabled", m["mo2"])])
    st.configure("TRadiobutton", background=m["nen"], foreground=m["chu"],
                 indicatorbackground=m["noi"], indicatorforeground=m["chu_nhan"],
                 bordercolor=m["vien2"], padding=(0, 3))
    st.map("TRadiobutton",
           background=[("active", m["nen"])],
           indicatorbackground=[("disabled", m["tam"]),
                                ("selected", m["nhan"]),
                                ("!disabled", "!selected", m["noi"])])

    st.configure("TLabelframe", background=m["nen"], bordercolor=m["vien"],
                 relief="solid", borderwidth=1)
    st.configure("TLabelframe.Label", background=m["nen"], foreground=m["mo2"],
                 font=("Segoe UI", 8, "bold"))

    st.configure("TScrollbar", background=m["noi"], troughcolor=m["nen"],
                 bordercolor=m["nen"], arrowcolor=m["mo"], relief="flat")
    st.map("TScrollbar", background=[("active", m["noi2"])])

    st.configure("TProgressbar", background=m["nhan"], troughcolor=m["noi"],
                 bordercolor=m["nen"], lightcolor=m["nhan"], darkcolor=m["nhan"])

    st.configure("TScale", background=m["nen"], troughcolor=m["noi"])

    st.configure("TSeparator", background=m["vien"])

    # ── bảng ảnh ──
    st.configure("Treeview", background=m["tam"], fieldbackground=m["tam"],
                 foreground=m["chu"], bordercolor=m["vien"], rowheight=21,
                 font=CHU)
    st.map("Treeview",
           background=[("selected", m["nhan_t"])],
           foreground=[("selected", m["chu"])])
    st.configure("Treeview.Heading", background=m["noi"], foreground=m["mo"],
                 relief="flat", font=("Segoe UI", 8, "bold"), padding=(6, 4))
    st.map("Treeview.Heading", background=[("active", m["noi2"])])
    return st


# ── mảnh dựng sẵn ───────────────────────────────────────────────────────────

def tieu_muc(cha, chu: str, **kw):
    """Nhãn nhóm chữ nhỏ in hoa — thay cho viền LabelFrame ở khắp nơi.

    Mười công tắc nằm trong một cái LabelFrame duy nhất thì viền đó không nói
    lên điều gì. Vài nhãn nhóm không viền phân tầng tốt hơn nhiều viền lồng nhau.
    """
    return ttk.Label(cha, text=chu.upper(), style="Muc.TLabel", **kw)


class The(tk.Frame):
    """Thẻ trạng thái: một dòng tiêu đề, một dòng mô tả, một vạch màu bên trái.

    Vạch màu mang NGHĨA (xong / đang chờ / có tin / hỏng) chứ không phải trang
    trí — nhìn màu vạch là biết cần để mắt tới hay không, khỏi phải đọc chữ.
    """
    MAU_LOAI = {"xong": "xong", "cho": "canh", "tin": "nhan",
                "loi": "loi", "": "vien2"}

    def __init__(self, cha, tieu_de="", mo_ta="", loai=""):
        super().__init__(cha, background=MAU["tam"],
                         highlightthickness=1, highlightbackground=MAU["vien"])
        self.vach = tk.Frame(self, width=3,
                             background=MAU[self.MAU_LOAI.get(loai, "vien2")])
        self.vach.pack(side="left", fill="y")
        trong = tk.Frame(self, background=MAU["tam"], padx=13, pady=10)
        trong.pack(side="left", fill="both", expand=True)
        self.l_ten = tk.Label(trong, text=tieu_de, anchor="w", justify="left",
                              background=MAU["tam"], foreground=MAU["chu"],
                              font=CHU_DAM)
        self.l_ten.pack(fill="x")
        self.l_mo = tk.Label(trong, text=mo_ta, anchor="w", justify="left",
                             background=MAU["tam"], foreground=MAU["mo"], font=CHU)
        self.l_mo.pack(fill="x")
        if not mo_ta:
            self.l_mo.pack_forget()

    def dat(self, tieu_de=None, mo_ta=None, loai=None):
        if tieu_de is not None:
            self.l_ten.configure(text=tieu_de)
        if mo_ta is not None:
            self.l_mo.configure(text=mo_ta)
            (self.l_mo.pack(fill="x") if mo_ta else self.l_mo.pack_forget())
        if loai is not None:
            self.vach.configure(background=MAU[self.MAU_LOAI.get(loai, "vien2")])


class Cuon(ttk.Frame):
    """Vùng cuộn được. Đặt nội dung vào `.trong`.

    VÌ SAO CẦN
        Khung việc của khâu Phân tích cao hơn cửa sổ: ba hộp chọn, sáu ô số,
        chín công tắc. Trên màn 1080 thì nút "1 · Phân tích" bị đẩy khỏi mép
        dưới, và grid không tự cho cuộn — nên nút chính biến mất, không cách nào
        với tới. Đã xảy ra thật 3/9.

    HAI CHỖ DỄ SAI
        1. Thanh cuộn phải TỰ ẨN khi không có gì để cuộn. Một thanh cuộn luôn
           hiện mà kéo không nhúc nhích khiến người dùng tưởng giao diện treo.
        2. Lăn chuột trên bảng ảnh hoặc ô nhật ký phải cuộn CHÍNH NÓ, không phải
           cuộn cả trang. Widget nào tự cuộn được thì nhường cho nó — xem `_lan`.
    """

    TU_CUON = (ttk.Treeview, tk.Text, tk.Listbox, tk.Canvas)

    def __init__(self, cha, **kw):
        super().__init__(cha, **kw)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, background=MAU["nen"], highlightthickness=0,
                                borderwidth=0, takefocus=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.thanh = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.thanh.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self._dat_thanh)

        self.trong = ttk.Frame(self.canvas)
        self.trong.columnconfigure(0, weight=1)
        self._cua = self.canvas.create_window((0, 0), window=self.trong, anchor="nw")
        self.trong.bind("<Configure>", self._noi_dung_doi)
        self.canvas.bind("<Configure>", self._be_ngang_doi)
        self.canvas.bind("<Enter>", lambda _e: self._nghe_lan(True))
        self.canvas.bind("<Leave>", lambda _e: self._nghe_lan(False))
        self.bind("<Destroy>", lambda _e: self._nghe_lan(False))

    def _noi_dung_doi(self, _e):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _be_ngang_doi(self, e):
        self.canvas.itemconfigure(self._cua, width=e.width)

    def _dat_thanh(self, lo, hi):
        (self.thanh.grid_remove() if float(lo) <= 0.0 and float(hi) >= 1.0
         else self.thanh.grid())
        self.thanh.set(lo, hi)

    def _nghe_lan(self, vao):
        #[[ bind_all vi con tro co the dang nam tren mot widget con, va su kien
        #   lan chuot khong noi len cha. Go ra khi chuot roi khoi vung — neu
        #   khong thi lan chuot o bat ky dau trong app cung cuon khung nay.
        #]]
        try:
            (self.canvas.bind_all("<MouseWheel>", self._lan) if vao
             else self.canvas.unbind_all("<MouseWheel>"))
        except tk.TclError:
            pass

    def _lan(self, e):
        w = self.winfo_containing(e.x_root, e.y_root)
        while w is not None and w is not self.canvas:
            if isinstance(w, self.TU_CUON):
                return                      # bảng/ô nhật ký tự lo phần của nó
            w = getattr(w, "master", None)
        lo, hi = self.canvas.yview()
        if lo <= 0.0 and hi >= 1.0:
            return                          # không có gì để cuộn
        self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")


class Ray(tk.Frame):
    """Cột trái bảy khâu — xương sống của ứng dụng.

    VÌ SAO NÓ Ở ĐÂY CHỨ KHÔNG NẰM SAU MỘT CÁI NÚT
        trang_thai.py đã dựng sẵn mô hình bảy khâu và tự suy trạng thái từ file
        trên đĩa. Trước đây nó nằm sau nút "Buổi chụp..." nên phải nhớ mà bấm mới
        thấy. Đưa ra cột trái thì mở app lên là biết ngay đang đứng ở đâu, khâu
        nào xong, khâu nào còn dở, và mỗi khâu mất bao lâu.

    KHÔNG DÙNG ttk.Button CHO TỪNG KHÂU
        Mỗi khâu là hai dòng chữ khác cỡ khác màu, cộng một chấm trạng thái, cộng
        một vạch nhấn bên trái. ttk.Button chỉ nhận MỘT nhãn. Nên mỗi khâu ở đây
        là một tk.Frame tự dựng, bắt <Button-1> trên cả cụm.
    """

    def __init__(self, cha, khau, khi_chon, khong_so=()):
        """khong_so: mã của những mục KHÔNG mang số thứ tự.

        Màn hình Tổng quan nằm chung cột trái nhưng không phải một khâu trong
        quy trình — nó không có "trước" và "sau". Đánh số nó thành 1 thì bảy
        khâu tụt xuống 2..8, lệch với mọi chỗ khác đang gọi tên "khâu 3",
        "khâu 4" (kể cả trong tài liệu và trong chính chú thích mã nguồn).
        Nên nó nhận dấu · thay cho số, và không tiêu tốn một số thứ tự nào.
        """
        super().__init__(cha, background=MAU["tam"])
        self.khi_chon = khi_chon
        self.hang: dict = {}
        self.dang = None
        self.khong_so = set(khong_so)

        self.l_buoi = tk.Label(self, text="CHƯA CHỌN BUỔI", anchor="w",
                               background=MAU["tam"], foreground=MAU["mo2"],
                               font=("Segoe UI", 8, "bold"), padx=14, pady=10)
        self.l_buoi.pack(fill="x")

        boc = tk.Frame(self, background=MAU["tam"], padx=6)
        boc.pack(fill="both", expand=True)
        #[[ NGUON SO DUY NHAT.
        #
        #   Truoc day tieu de o cot phai tu dem lay bang enumerate(KHAU, 1). Them
        #   muc "Tong quan" vao dau KHAU la hai cho lech nhau ngay: ray ghi
        #   "4 Export" con tieu de ghi "Khau 5 - Export". Nguoi dung nhin thay
        #   ngay trong mot man hinh.
        #
        #   Nen so thu tu chi duoc dem MOT LAN, o day, va ai can thi hoi
        #   so_cua(). Khong con cho nao tu dem nua.
        #]]
        self.so_thu_tu: dict = {}
        so = 0
        for ma, ten in khau:
            if ma in self.khong_so:
                self.so_thu_tu[ma] = "·"
            else:
                so += 1
                self.so_thu_tu[ma] = str(so)
            self.hang[ma] = self._mot_khau(boc, self.so_thu_tu[ma], ma, ten)

        self.chan = tk.Frame(self, background=MAU["tam"], padx=10, pady=10,
                             highlightthickness=1, highlightbackground=MAU["vien"])
        self.chan.pack(fill="x", side="bottom")

    def so_cua(self, ma) -> str:
        """Số thứ tự đang hiện ở cột trái — "·" nếu mục đó không mang số."""
        return self.so_thu_tu.get(ma, "·")

    def _mot_khau(self, cha, so, ma, ten):
        h = tk.Frame(cha, background=MAU["tam"], padx=0, pady=0)
        h.pack(fill="x", pady=1)
        vach = tk.Frame(h, width=3, background=MAU["tam"])
        vach.pack(side="left", fill="y")
        trong = tk.Frame(h, background=MAU["tam"], padx=8, pady=7)
        trong.pack(side="left", fill="both", expand=True)

        l_so = tk.Label(trong, text=str(so), background=MAU["tam"],
                        foreground=MAU["mo2"], font=("Consolas", 9, "bold"))
        l_so.pack(side="left", anchor="n", padx=(0, 9))
        cham = tk.Canvas(trong, width=9, height=9, highlightthickness=0,
                         background=MAU["tam"])
        cham.pack(side="right", anchor="n", pady=3)
        cham.create_oval(1, 1, 8, 8, fill="#3f3f3f", outline="", tags="c")

        cot = tk.Frame(trong, background=MAU["tam"])
        cot.pack(side="left", fill="x", expand=True)
        l_ten = tk.Label(cot, text=ten, anchor="w", background=MAU["tam"],
                         foreground=MAU["chu"], font=CHU)
        l_ten.pack(fill="x")
        l_phu = tk.Label(cot, text="", anchor="w", background=MAU["tam"],
                         foreground=MAU["mo"], font=("Consolas", 8))
        l_phu.pack(fill="x")

        o = dict(khung=h, vach=vach, trong=trong, cot=cot, cham=cham,
                 l_so=l_so, l_ten=l_ten, l_phu=l_phu, ma=ma)
        #[[ Bat chuot tren MOI widget con: click roi vao cai nam duoi con tro,
        #   khong noi len Frame cha. Bo sot mot cai la co mot vung chet ma nguoi
        #   dung bam mai khong an — kieu loi rat kho doan tu phia ho.
        #]]
        for w in (h, trong, cot, l_so, l_ten, l_phu, cham):
            w.bind("<Button-1>", lambda _e, k=ma: self.khi_chon(k))
            w.bind("<Enter>", lambda _e, d=o: self._ro(d, True))
            w.bind("<Leave>", lambda _e, d=o: self._ro(d, False))
        return o

    def _nen(self, o, mau):
        for w in (o["khung"], o["trong"], o["cot"], o["l_so"], o["l_ten"],
                  o["l_phu"], o["cham"]):
            w.configure(background=mau)

    def _ro(self, o, vao):
        if o["ma"] == self.dang:
            return
        self._nen(o, MAU["noi"] if vao else MAU["tam"])

    def chon(self, ma):
        self.dang = ma
        for k, o in self.hang.items():
            dang = (k == ma)
            self._nen(o, MAU["noi"] if dang else MAU["tam"])
            o["vach"].configure(background=MAU["nhan"] if dang else MAU["tam"])
            o["l_so"].configure(foreground=MAU["nhan"] if dang else MAU["mo2"])

    def cap_nhat(self, ds, buoi=""):
        """ds = danh sách khâu từ trang_thai.tinh(). Chỉ đọc, không tính lại."""
        self.l_buoi.configure(text=("BUỔI " + buoi).upper() if buoi
                              else "CHƯA CHỌN BUỔI")
        for k in ds:
            o = self.hang.get(k["ten"])
            if not o:
                continue
            #[[ Chi lay MENH DE DAU cua mo ta. trang_thai viet cho ban tom tat
            #   nen cau dai: "Chua co bao cao — bam 1 · Phan tich roi Xuat CSV".
            #   Cot trai rong 252 px, cat cung o 34 ky tu thi ra "Chua co bao
            #   cao — bam 1 · P" — nua cau, doc kho chiu hon la khong co.
            #   Cat o dau gach ngang thi con "Chua co bao cao", tron ven.
            #]]
            phu = k["mo_ta"].split(" — ")[0]
            if k.get("giay"):
                phu += f" · {k['giay'] / 60:.1f} phút"
            #[[ 26 ky tu, do bang thuoc chu khong uoc luong: Consolas 8 trong
            #   cot 252 px (tru le va cham trang thai) vua dung 26 ky tu. De 32
            #   thi Tk tu cat not, va no cat KHONG co dau ba cham — nguoi doc
            #   khong biet la con chu bi khuat hay cau no von cut nhu vay.
            #]]
            if len(phu) > 26:
                phu = phu[:25] + "…"
            o["l_phu"].configure(text=phu)
            mau = MAU["xong"] if k["xong"] else "#3f3f3f"
            if not k["xong"] and k.get("viec"):
                mau = MAU["canh"]
            o["cham"].itemconfigure("c", fill=mau)

    def dang_chay(self, ma, chay=True):
        o = self.hang.get(ma)
        if o:
            o["cham"].itemconfigure("c", fill=MAU["nhan"] if chay else "#3f3f3f")
