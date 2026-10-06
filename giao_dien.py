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

import math
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk


def va_imagetk() -> None:
    """ImageTk không gắn được vào Tk -> đưa ảnh vào Tk bằng PNG (Tk 8.6 tự đọc).

    #[[ 6/10 — ban macOS mo len chet NGAY o nut dau tien (anh_bo_goc ->
    #   ImageTk.PhotoImage): "TypeError: bad argument type for built-in
    #   operation" tai _imagingtk.tkinit. Python build cua ban Mac (python-build-
    #   standalone) NHUNG SAN _tkinter vao thu vien Python — khong co __file__ ->
    #   PIL._tkinter_finder.TKINTER_LIB = None -> ma C cua Pillow khong tim duoc
    #   Tcl/Tk de gan "PyImagingPhoto". Khong sua duoc ben trong Pillow, nen bo
    #   qua han duong do: lan dau hong thi tu do moi lan paste() deu dua anh qua
    #   PNG (giu ca kenh trong suot — nut bo goc can no). Windows / may chay duoc
    #   duong C thi khong doi gi: van thu duong C truoc. ]]
    """
    if _IMAGETK_VA:
        return
    try:
        from PIL import ImageTk
    except Exception:                                        # noqa: BLE001
        return
    goc = ImageTk.PhotoImage.paste
    hong = [False]

    def paste(self, im, *a, **k):
        if not hong[0]:
            try:
                return goc(self, im, *a, **k)
            except Exception:                                # noqa: BLE001
                hong[0] = True
        import base64
        import io
        m = im if im.mode in ("RGB", "RGBA", "L", "LA") else im.convert("RGBA")
        b = io.BytesIO()
        m.save(b, format="PNG", compress_level=1)
        self._PhotoImage__photo.configure(data=base64.b64encode(b.getvalue()),
                                          format="png")

    ImageTk.PhotoImage.paste = paste
    _IMAGETK_VA.append(True)


_IMAGETK_VA: list = []
va_imagetk()

# ── Bảng màu ────────────────────────────────────────────────────────────────
#[[ BANG MAU KIEU EVOTO (3/10 toi — user: "tham khao giao dien cua Evoto de
#   thiet ke lai toan bo giao dien"). Do tu anh chup giao dien Evoto that
#   (support.evoto.ai): vung giua / thanh cong cu #17181A, bang dieu khien
#   #22252A, o lom #181C1F, vien chon #3A3B3F, nut "Export" vang #FFDE17 chu
#   den. Xam hoi lanh — dung nhu Evoto, khong phai xam trung tinh cu.
#
#   "nen" van la nen MAC DINH cua moi khung ttk — nay la mau BANG DIEU KHIEN.
#   Vung giua va thanh cong cu toi hon ("toi") va dat mau TUONG MINH. Giu ten
#   khoa cu de hang tram cho goi gd.MAU["nen"] khong phai sua.
#
#   CANH BAO DOI SANG CAM: vang da la mau cua nut chinh; canh bao cung vang
#   thi nguoi dung khong phan biet "bam vao day" voi "coi chung". ]]
MAU = {
    "toi":    "#17181a",   # vùng giữa, thanh công cụ (như canvas Evoto)
    "toi2":   "#121315",   # thanh trạng thái
    "nen":    "#22252a",   # bảng điều khiển + nền mặc định của khung ttk
    "tam":    "#1b1d21",   # ô lõm: ô nhập, nhật ký, thẻ
    "noi":    "#2c2f34",   # nền nổi nhẹ: nút phụ, hàng rê chuột
    "noi2":   "#3a3d42",   # rê chuột / viên đang chọn
    "noi3":   "#46494f",   # đang bấm
    "vien":   "#2f3237",   # vạch chia
    "vien2":  "#474a50",   # viền ô, rãnh thanh trượt
    "chu":    "#e8e9eb",
    "mo":     "#a3a6ab",   # chữ phụ
    "mo2":    "#6f7378",   # chữ rất phụ
    "nhan":   "#ffde17",   # vàng Evoto — nút chính, ô đang chọn
    "nhan2":  "#ffe650",   # rê chuột
    "nhan3":  "#e5c200",   # đang bấm
    #  nền dòng chọn trong bảng — XÁM TRUNG TÍNH, không ngả vàng: dòng "chỉnh
    #  mạnh" (big) đã nhuộm nâu vàng, chọn mà cũng vàng thì không phân biệt nổi.
    "nhan_t": "#4a4e57",
    "chu_nhan": "#17181a",  # chữ trên nền vàng
    "xong":   "#4cc27a",
    "canh":   "#f0913c",
    "loi":    "#ec5a50",
    "bang_canh_nen": "#3a2614",
    "bang_canh_chu": "#f6c08a",
}

# Segoe UI có sẵn trên mọi máy Windows và dựng dấu tiếng Việt đầy đủ.
# Consolas cho số liệu: chữ số đều bề ngang nên cột số thẳng hàng.
# CHU_DAM / CHU_TIEU_DE đổi sang Semibold trong dat_theme() nếu máy có — Bold
# của Segoe UI nặng hơn hẳn chữ đậm của Evoto.
CHU = ("Segoe UI", 9)
CHU_DAM = ("Segoe UI", 9, "bold")
CHU_TO = ("Segoe UI", 12, "bold")
CHU_NHO = ("Segoe UI", 8)
CHU_SO = ("Consolas", 9)
CHU_TIEU_DE = ("Segoe UI", 10, "bold")


def dat_theme(root: tk.Misc) -> ttk.Style:
    """Nhuộm toàn bộ widget ttk. Gọi MỘT lần, ngay sau khi tạo cửa sổ gốc."""
    global CHU_DAM, CHU_TIEU_DE
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except tk.TclError:      # máy lạ không có clam thì thôi, đừng làm sập app
        pass

    #[[ Semibold neu may co (Windows 7+ deu co "Segoe UI Semibold"). Doi
    #   o day vi phai co root moi hoi duoc danh sach phong; noi khac goi
    #   gd.CHU_DAM luc dung widget nen lay duoc gia tri moi. ]]
    try:
        if "Segoe UI Semibold" in tkfont.families(root):
            CHU_DAM = ("Segoe UI Semibold", 9)
            CHU_TIEU_DE = ("Segoe UI Semibold", 10)
    except tk.TclError:
        pass

    m = MAU
    root.configure(background=m["toi"])

    #[[ Danh sach xo cua Combobox va Listbox KHONG phai widget ttk — chung la
    #   widget Tk co, nen style khong voi toi. Chi option_add moi doi duoc, va
    #   phai goi TRUOC khi tao combobox dau tien.
    #]]
    root.option_add("*TCombobox*Listbox.background", m["tam"])
    root.option_add("*TCombobox*Listbox.foreground", m["chu"])
    root.option_add("*TCombobox*Listbox.selectBackground", m["noi2"])
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
    #[[ Menu xo: nen tam lom, dong re chuot xam sang — nhu menu Evoto, khong
    #   to vang ca dong (vang chi danh cho nut chinh). ]]
    root.option_add("*Menu.background", m["tam"])
    root.option_add("*Menu.foreground", m["chu"])
    root.option_add("*Menu.activeBackground", m["noi2"])
    root.option_add("*Menu.activeForeground", m["chu"])
    root.option_add("*Menu.selectColor", m["nhan"])
    root.option_add("*Menu.disabledForeground", m["mo2"])
    root.option_add("*Menu.relief", "flat")
    root.option_add("*Menu.borderWidth", 1)
    root.option_add("*Menu.activeBorderWidth", 0)
    root.option_add("*Menu.font", CHU)

    st.configure(".", background=m["nen"], foreground=m["chu"],
                 fieldbackground=m["tam"], font=CHU,
                 bordercolor=m["vien"], darkcolor=m["nen"], lightcolor=m["nen"],
                 troughcolor=m["tam"], focuscolor=m["nhan"],
                 selectbackground=m["noi2"], selectforeground=m["chu"])

    st.configure("TFrame", background=m["nen"])
    st.configure("Tam.TFrame", background=m["tam"])
    st.configure("Noi.TFrame", background=m["noi"])
    st.configure("Toi.TFrame", background=m["toi"])

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
    for ten in ("Toi.TLabel", "ToiMo.TLabel", "ToiMo2.TLabel"):
        st.configure(ten, background=m["toi"])
    st.configure("ToiMo.TLabel", foreground=m["mo"])
    st.configure("ToiMo2.TLabel", foreground=m["mo2"], font=CHU_NHO)

    # ── nút ttk (những nút chưa đổi sang NutTron) — phẳng, không viền nổi ──
    st.configure("TButton", background=m["noi"], foreground=m["chu"],
                 bordercolor=m["noi"], lightcolor=m["noi"], darkcolor=m["noi"],
                 relief="flat", padding=(12, 5), focuscolor=m["noi"])
    st.map("TButton",
           background=[("pressed", m["noi3"]), ("active", m["noi2"]),
                       ("disabled", m["tam"])],
           bordercolor=[("pressed", m["noi3"]), ("active", m["noi2"]),
                        ("disabled", m["tam"]), ("focus", m["vien2"])],
           lightcolor=[("pressed", m["noi3"]), ("active", m["noi2"]),
                       ("disabled", m["tam"])],
           darkcolor=[("pressed", m["noi3"]), ("active", m["noi2"]),
                      ("disabled", m["tam"])],
           foreground=[("disabled", m["mo2"])])

    st.configure("Chinh.TButton", background=m["nhan"], foreground=m["chu_nhan"],
                 bordercolor=m["nhan"], lightcolor=m["nhan"], darkcolor=m["nhan"],
                 font=CHU_DAM, padding=(14, 6))
    st.map("Chinh.TButton",
           background=[("pressed", m["nhan3"]), ("active", m["nhan2"]),
                       ("disabled", m["noi"])],
           bordercolor=[("pressed", m["nhan3"]), ("active", m["nhan2"]),
                        ("disabled", m["noi"])],
           lightcolor=[("pressed", m["nhan3"]), ("active", m["nhan2"]),
                       ("disabled", m["noi"])],
           darkcolor=[("pressed", m["nhan3"]), ("active", m["nhan2"]),
                      ("disabled", m["noi"])],
           foreground=[("disabled", m["mo2"])])

    #[[ Nut "pha": viec phu, khong duoc tranh mat voi nut chinh. Khong vien,
    #   khong nen — chi la chu. Dung cho Xuat CSV, Nhat ky, Cach tao .xmp...
    #]]
    st.configure("Pha.TButton", background=m["nen"], foreground=m["mo"],
                 bordercolor=m["nen"], lightcolor=m["nen"], darkcolor=m["nen"],
                 relief="flat", padding=(6, 4))
    st.map("Pha.TButton",
           background=[("active", m["nen"]), ("pressed", m["nen"])],
           bordercolor=[("active", m["nen"]), ("pressed", m["nen"])],
           lightcolor=[("active", m["nen"]), ("pressed", m["nen"])],
           darkcolor=[("active", m["nen"]), ("pressed", m["nen"])],
           foreground=[("active", m["chu"]), ("disabled", m["mo2"])])

    # ── ô nhập: lõm tối, viền mảnh, sáng viền vàng khi đang gõ ──
    for ten in ("TEntry", "TSpinbox", "TCombobox"):
        st.configure(ten, fieldbackground=m["tam"], background=m["noi"],
                     foreground=m["chu"], bordercolor=m["vien2"],
                     lightcolor=m["tam"], darkcolor=m["tam"],
                     arrowcolor=m["mo"], insertcolor=m["chu"],
                     selectbackground=m["noi2"], selectforeground=m["chu"],
                     padding=(6, 4))
        st.map(ten,
               fieldbackground=[("readonly", m["tam"]), ("disabled", m["nen"])],
               background=[("active", m["noi2"]), ("disabled", m["nen"])],
               foreground=[("disabled", m["mo2"])],
               bordercolor=[("focus", m["nhan"]), ("active", m["mo2"])],
               lightcolor=[("focus", m["tam"])],
               darkcolor=[("focus", m["tam"])],
               arrowcolor=[("disabled", m["mo2"]), ("active", m["chu"])])

    #[[ O so canh thanh truot: khong vien, nen trung bang dieu khien — doc nhu
    #   mot con so; dang go thi hien vien vang (nhu o "0" cua Evoto). ]]
    st.configure("So.TEntry", fieldbackground=m["nen"], bordercolor=m["nen"],
                 lightcolor=m["nen"], darkcolor=m["nen"], padding=(3, 1),
                 foreground=m["chu"])
    st.map("So.TEntry",
           fieldbackground=[("focus", m["tam"]), ("disabled", m["nen"])],
           bordercolor=[("focus", m["nhan"])],
           lightcolor=[("focus", m["tam"])], darkcolor=[("focus", m["tam"])],
           foreground=[("disabled", m["mo2"])])

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
                 indicatorbackground=m["tam"], indicatorforeground=m["chu_nhan"],
                 bordercolor=m["vien2"], focuscolor=m["nhan"], padding=(0, 3))
    st.map("TCheckbutton",
           background=[("active", m["nen"])],
           indicatorbackground=[("disabled", m["nen"]),
                                ("pressed", m["noi2"]),
                                ("selected", m["nhan"]),
                                ("!disabled", "!selected", m["tam"])],
           indicatorforeground=[("selected", m["chu_nhan"])],
           foreground=[("disabled", m["mo2"])])
    st.configure("TRadiobutton", background=m["nen"], foreground=m["chu"],
                 indicatorbackground=m["tam"], indicatorforeground=m["chu_nhan"],
                 bordercolor=m["vien2"], padding=(0, 3))
    st.map("TRadiobutton",
           background=[("active", m["nen"])],
           indicatorbackground=[("disabled", m["nen"]),
                                ("selected", m["nhan"]),
                                ("!disabled", "!selected", m["tam"])])

    st.configure("TLabelframe", background=m["nen"], bordercolor=m["vien"],
                 relief="solid", borderwidth=1)
    st.configure("TLabelframe.Label", background=m["nen"], foreground=m["mo2"],
                 font=("Segoe UI", 8, "bold"))

    #[[ THANH CUON MANH, KHONG MUI TEN — nhu Evoto. Bo hai mui ten khoi
    #   layout cua clam: thanh cuon chi con ranh + con chay, ranh trung mau
    #   nen nen gan nhu vo hinh cho toi khi re chuot vao con chay. ]]
    for huong in ("Vertical", "Horizontal"):
        st.layout(f"{huong}.TScrollbar", [
            (f"{huong}.Scrollbar.trough", {"sticky": "nswe", "children": [
                (f"{huong}.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
    st.configure("TScrollbar", background=m["noi2"], troughcolor=m["nen"],
                 bordercolor=m["nen"], lightcolor=m["noi2"], darkcolor=m["noi2"],
                 arrowcolor=m["mo"], relief="flat", gripcount=0, arrowsize=9)
    st.map("TScrollbar", background=[("active", m["noi3"])],
           lightcolor=[("active", m["noi3"])], darkcolor=[("active", m["noi3"])])
    for ten, nen in (("Toi", m["toi"]), ("Tam", m["tam"])):
        for huong in ("Vertical", "Horizontal"):
            st.layout(f"{ten}.{huong}.TScrollbar",
                      st.layout(f"{huong}.TScrollbar"))
            st.configure(f"{ten}.{huong}.TScrollbar", troughcolor=nen,
                         bordercolor=nen)

    #[[ Thanh tien do: ranh TRUNG mau thanh trang thai — luc ranh no vo hinh,
    #   chi hien dai vang khi dang chay (Evoto khong co thanh tien do thuong
    #   truc nao). ]]
    #  Ranh "noi" (xam rat toi) chu khong phai mau nen: nam tren the sang (trang
    #  Duyet nhanh) ma ranh mau toi2 thi thanh mot hop den dac giua the. Thanh
    #  o thanh trang thai thi chi hien khi dang chay (App._hien_tien_do).
    st.configure("TProgressbar", background=m["nhan"], troughcolor=m["noi"],
                 bordercolor=m["noi"], lightcolor=m["nhan"], darkcolor=m["nhan"],
                 thickness=4)

    #[[ THANH TRUOT ttk (con dung o khung Retouch) — PHAI GHI DE CA MAP.
    #
    #   clam map chung cho "." : background disabled -> #dcdad5, active ->
    #   #eeebe7. Con truot cua thanh BI TAT hien thanh hai o TRANG choi giua
    #   nen toi — trong nhu dang duoc chon. Re chuot vao cung trang bung.
    #   Thanh truot cua bang tuy chon gio la gd.Truot (ve tay, kieu Evoto). ]]
    st.configure("TScale", background=m["mo"], troughcolor=m["tam"],
                 bordercolor=m["vien2"], lightcolor=m["mo"], darkcolor=m["mo"],
                 gripcount=0, sliderlength=12)
    for _k in ("background", "lightcolor", "darkcolor"):
        st.map("TScale", **{_k: [("disabled", m["vien2"]), ("pressed", m["nhan"]),
                                 ("active", m["chu"])]})
    st.map("TScale", bordercolor=[("disabled", m["vien"])])

    st.configure("TSeparator", background=m["vien"])

    # ── bảng ảnh: nằm trên vùng giữa tối, như lưới ảnh ──
    st.configure("Treeview", background=m["toi"], fieldbackground=m["toi"],
                 foreground=m["chu"], bordercolor=m["toi"], lightcolor=m["toi"],
                 darkcolor=m["toi"], rowheight=24, font=CHU)
    st.map("Treeview",
           background=[("selected", m["nhan_t"])],
           foreground=[("selected", m["chu"])])
    st.configure("Treeview.Heading", background=m["toi"], foreground=m["mo"],
                 bordercolor=m["vien"], lightcolor=m["toi"], darkcolor=m["toi"],
                 relief="flat", font=("Segoe UI", 8, "bold"), padding=(6, 5))
    st.map("Treeview.Heading", background=[("active", m["noi"])],
           foreground=[("active", m["chu"])])
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

    def __init__(self, cha, nen: str | None = None, **kw):
        super().__init__(cha, **kw)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, background=nen or MAU["nen"],
                                highlightthickness=0, borderwidth=0, takefocus=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.thanh = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.thanh.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self._dat_thanh)

        self.trong = ttk.Frame(self.canvas, style=(
            "Toi.TFrame" if (nen or MAU["nen"]) == MAU["toi"] else "TFrame"))
        self.trong.columnconfigure(0, weight=1)
        self._cua = self.canvas.create_window((0, 0), window=self.trong, anchor="nw")
        self._lap_day = False
        self._theo_ngang = False
        self.trong.bind("<Configure>", self._noi_dung_doi)
        self.canvas.bind("<Configure>", self._be_ngang_doi)
        self.canvas.bind("<Enter>", lambda _e: self._nghe_lan(True))
        self.canvas.bind("<Leave>", lambda _e: self._nghe_lan(False))
        self.bind("<Destroy>", lambda _e: self._nghe_lan(False))

    def lap_day(self):
        """Khung bên trong cao ĐÚNG bằng ô nhìn, không cuộn — cho trang tự lo
        phần cuộn của nó (lưới ảnh, bảng kết quả)."""
        self._lap_day = True
        self.thanh.grid_remove()

    def theo_noi_dung(self):
        """Bề ngang ô nhìn = bề ngang nội dung (bảng điều khiển phải): cột
        rộng đúng bằng tuỳ chọn rộng nhất, không cắt chữ, không thừa.

        Chỗ của thanh cuộn được CHỪA SẴN kể cả lúc nó ẩn: không chừa thì mở
        một nhóm làm nội dung tràn -> thanh cuộn hiện -> cột rộng thêm ~10 px
        -> lưới ảnh bên cạnh nhảy cột."""
        self._theo_ngang = True
        self.columnconfigure(1, minsize=self.thanh.winfo_reqwidth())

    def _noi_dung_doi(self, _e):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        if self._theo_ngang:
            w = self.trong.winfo_reqwidth()
            try:
                if int(float(self.canvas.cget("width"))) != w:
                    self.canvas.configure(width=w)
            except (tk.TclError, ValueError):
                pass

    def _be_ngang_doi(self, e):
        if self._lap_day:
            self.canvas.itemconfigure(self._cua, width=e.width, height=e.height)
            self.canvas.configure(scrollregion=(0, 0, e.width, e.height))
        else:
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
            #[[ Canvas tu ve (nut, cong tac, thanh truot, dau ?) KHONG tu cuon
            #   — chung dat tu_cuon = False. Thieu dong nay thi re chuot len mot
            #   thanh truot roi lan chuot la ca bang dieu khien dung im. ]]
            if isinstance(w, self.TU_CUON) and getattr(w, "tu_cuon", True):
                return                      # bảng/ô nhật ký tự lo phần của nó
            w = getattr(w, "master", None)
        lo, hi = self.canvas.yview()
        if lo <= 0.0 and hi >= 1.0:
            return                          # không có gì để cuộn
        self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")


def thanh_tu_an(sb: ttk.Scrollbar):
    """xscrollcommand / yscrollcommand cho một thanh cuộn TỰ ẨN khi nội dung
    vừa khung (thanh phải được đặt bằng .grid())."""
    def dat(lo, hi):
        try:
            if float(lo) <= 0.0 and float(hi) >= 1.0:
                sb.grid_remove()
            else:
                sb.grid()
            sb.set(lo, hi)
        except tk.TclError:
            pass
    return dat


def vua_chu(cb: ttk.Combobox, toi_thieu: int = 6) -> int:
    """Đặt `width` của ô chọn vừa đúng giá trị DÀI NHẤT của nó; trả về width.

    #[[ ttk.Combobox mac dinh width=20 ky tu; grid chi keo GIAN no ra khi cot
    #   du rong. Cot hep thi chu bi CAT ngay trong o: "Dua mat ve muc sang ch",
    #   "Khuon mat + diem bat net (k" — loi da gap hai lan va van con o cua so
    #   1360/1660 px. Goc re: winfo_reqwidth() cua o chi bao 20 ky tu, nen
    #   _xep_cot (do bang reqwidth) tuong la du cho.
    #
    #   Dat width = chu dai nhat thi reqwidth noi THAT, va moi cho do bang
    #   reqwidth tu giu du cho cho chu. width tinh bang be ngang ky tu "0" cua
    #   phong o (dung don vi Tk dung) — do bang font.measure, khong uoc. ]]
    """
    try:
        f = tkfont.Font(root=cb, font=cb.cget("font") or "TkTextFont")
    except tk.TclError:
        f = tkfont.nametofont("TkTextFont")
    gia_tri = cb.tk.splitlist(cb.cget("values")) or ("",)
    dai = max(f.measure(str(v)) for v in gia_tri)
    w = max(toi_thieu, math.ceil(dai / max(1, f.measure("0"))) + 1)
    cb.configure(width=w)
    return w


# ── Hình khử răng cưa ───────────────────────────────────────────────────────
#[[ VI SAO VE BANG PIL ROI DAN VAO CANVAS.
#
#   Canvas cua Tk tren Windows KHONG khu rang cua: hinh bo goc ve bang
#   create_polygon(smooth=True) hien rang cua o goc — nut vien tron cao 28 px
#   trong re tien ngay. Ve bang PIL o gap 4 lan roi thu nho (LANCZOS) thi mep
#   min nhu Evoto; chu van ve bang create_text de giu phong cua he dieu hanh.
#
#   Anh dat NEN DAC bang dung mau cho dat (khong dung kenh trong suot): Tk 8.6
#   tron alpha duoc tren Canvas, nhung nen dac thi chac chan giong het tren moi
#   may, va moi widget deu biet nen cua chinh no.
#
#   Kho anh gan vao TUNG cua so goc (root): Tk huy root thi anh cung mat, giu
#   chung mot kho giua hai root la "image doesn't exist" o root sau (bai kiem
#   dung nhieu root lien tiep).
#]]
try:
    from PIL import Image, ImageDraw, ImageTk
except Exception:                                            # noqa: BLE001
    Image = ImageDraw = ImageTk = None


def _loc_thu_nho():
    return getattr(getattr(Image, "Resampling", Image), "LANCZOS")


def _kho_anh(w) -> dict:
    goc = w._root()
    kho = getattr(goc, "_gd_kho_anh", None)
    if kho is None or len(kho) > 600:
        #[[ Xoa ca kho khi qua lon (thanh truot keo dai doi be ngang -> moi be
        #   ngang mot anh). An toan: widget nao dang ve thi tu GIU tham chieu
        #   toi anh cua no, xoa kho khong lam anh dang hien bien mat. ]]
        kho = {}
        goc._gd_kho_anh = kho
    return kho


def _rgb(w, mau: str) -> tuple:
    mau = str(mau)
    if len(mau) == 7 and mau.startswith("#"):
        return tuple(int(mau[i:i + 2], 16) for i in (1, 3, 5))
    r, g, b = w.winfo_rgb(mau)
    return (r >> 8, g >> 8, b >> 8)


def _ve_bo_goc(d, x0, y0, x1, y1, r, fill) -> None:
    """Hình bo góc bằng chữ nhật + bốn hình tròn — chạy được cả Pillow cũ
    (rounded_rectangle mới có từ 8.2)."""
    r = max(0, min(int(r), (x1 - x0 + 1) // 2, (y1 - y0 + 1) // 2))
    if r <= 0:
        d.rectangle((x0, y0, x1, y1), fill=fill)
        return
    if x1 - r >= x0 + r:
        d.rectangle((x0 + r, y0, x1 - r, y1), fill=fill)
    if y1 - r >= y0 + r:
        d.rectangle((x0, y0 + r, x1, y1 - r), fill=fill)
    for cx, cy in ((x0, y0), (x1 - 2 * r, y0), (x0, y1 - 2 * r),
                   (x1 - 2 * r, y1 - 2 * r)):
        d.ellipse((cx, cy, cx + 2 * r, cy + 2 * r), fill=fill)


def anh_bo_goc(w, rong, cao, r, mau, nen, vien=None, day=1):
    """PhotoImage hình bo góc mép mịn, nền đặc = màu chỗ đặt nó."""
    rong, cao, r = max(1, int(rong)), max(1, int(cao)), max(0, int(r))
    mau = mau or nen
    key = ("bg", rong, cao, r, mau, nen, vien, day)
    kho = _kho_anh(w)
    a = kho.get(key)
    if a is None:
        hs = 4
        im = Image.new("RGB", (rong * hs, cao * hs), _rgb(w, nen))
        d = ImageDraw.Draw(im)
        W, H = rong * hs - 1, cao * hs - 1
        if vien:
            _ve_bo_goc(d, 0, 0, W, H, r * hs, _rgb(w, vien))
            k = max(1, int(day * hs))
            _ve_bo_goc(d, k, k, W - k, H - k, max(0, r * hs - k), _rgb(w, mau))
        else:
            _ve_bo_goc(d, 0, 0, W, H, r * hs, _rgb(w, mau))
        a = ImageTk.PhotoImage(im.resize((rong, cao), _loc_thu_nho()),
                               master=w._root())
        kho[key] = a
    return a


def anh_tron(w, d, mau, nen, vien=None, day=1):
    """Hình tròn đường kính d, mép mịn."""
    return anh_bo_goc(w, d, d, d, mau, nen, vien, day)


def nen_cua(w) -> str:
    """Màu nền THẬT của w (tk lẫn ttk) — để nút vẽ tay hoà vào chỗ đặt."""
    try:
        return str(w.cget("background"))
    except (tk.TclError, AttributeError):
        pass
    try:
        ten = str(w.cget("style")) or w.winfo_class()
        mau = ttk.Style(w).lookup(ten, "background") or \
            ttk.Style(w).lookup(w.winfo_class(), "background")
        if mau:
            return str(mau)
    except tk.TclError:
        pass
    return MAU["nen"]


def _phong(w, font):
    """Đối tượng Font dùng chung theo (root, mô tả phông) — khỏi tạo hàng trăm
    phông trùng nhau cho hàng trăm nút."""
    goc = w._root()
    kho = getattr(goc, "_gd_kho_phong", None)
    if kho is None:
        kho = {}
        goc._gd_kho_phong = kho
    key = tuple(font) if isinstance(font, (tuple, list)) else str(font)
    f = kho.get(key)
    if f is None:
        f = tkfont.Font(root=goc, font=font)
        kho[key] = f
    return f


def don_vi(w) -> int:
    """Một "dòng chữ" tính bằng pixel ở DPI đang chạy. Mọi kích thước vẽ tay
    lấy theo nó — Windows phóng 125–150% thì nút to theo chữ, không cắt chữ."""
    return _phong(w, CHU).metrics("linespace")


# ── Biểu tượng vẽ bằng nét ───────────────────────────────────────────────────
#[[ VE BANG NET CANVAS, KHONG DUNG PHONG BIEU TUONG.
#   "Segoe MDL2 Assets" chi co tu Windows 10, "Segoe Fluent Icons" chi Windows
#   11, macOS khong co ca hai — thieu phong la hien o vuong. Ve bang duong va
#   hinh tron thi giong nhau o moi may, phong to bao nhieu cung net. ]]
def ve_bieu_tuong(c: tk.Canvas, ten: str, cx: float, cy: float, s: float,
                  mau: str, tag: str = "icon") -> None:
    nh = max(1.0, s / 11)
    if ten == "tone":                       # ba thanh trượt
        for i, (dy, kx) in enumerate(((-0.32, -0.16), (0.0, 0.2), (0.32, -0.04))):
            y = cy + dy * s
            c.create_line(cx - 0.45 * s, y, cx + 0.45 * s, y, fill=mau,
                          width=nh, capstyle="round", tags=tag)
            r = 0.12 * s
            x = cx + kx * s
            c.create_oval(x - r, y - r, x + r, y + r, fill=mau, outline=mau,
                          tags=tag)
    elif ten == "retouch":                  # chân dung
        r = 0.2 * s
        c.create_oval(cx - r, cy - 0.42 * s, cx + r, cy - 0.42 * s + 2 * r,
                      fill=mau, outline=mau, tags=tag)
        c.create_arc(cx - 0.4 * s, cy + 0.04 * s, cx + 0.4 * s, cy + 0.84 * s,
                     start=0, extent=180, style="chord", fill=mau, outline=mau,
                     tags=tag)
    elif ten == "thu_muc":                  # thư mục
        x0, y0, x1, y1 = cx - 0.45 * s, cy - 0.32 * s, cx + 0.45 * s, cy + 0.34 * s
        c.create_polygon(x0, y0, x0 + 0.34 * s, y0, x0 + 0.44 * s, y0 + 0.12 * s,
                         x1, y0 + 0.12 * s, x1, y1, x0, y1, fill="", outline=mau,
                         width=nh, joinstyle="round", tags=tag)
    elif ten == "them":                     # ba chấm
        for dx in (-0.3, 0.0, 0.3):
            r = 0.07 * s
            x = cx + dx * s
            c.create_oval(x - r, cy - r, x + r, cy + r, fill=mau, outline=mau,
                          tags=tag)
    elif ten == "luoi":                     # lưới 2×2
        a, g = 0.36 * s, 0.08 * s
        for ox in (-1, 1):
            for oy in (-1, 1):
                x0 = cx + (g if ox > 0 else -a - g)
                y0 = cy + (g if oy > 0 else -a - g)
                c.create_rectangle(x0, y0, x0 + a, y0 + a, outline=mau,
                                   width=nh, tags=tag)
    elif ten == "bang":                     # danh sách
        for dy in (-0.3, 0.0, 0.3):
            y = cy + dy * s
            c.create_line(cx - 0.42 * s, y, cx - 0.28 * s, y, fill=mau,
                          width=nh * 1.4, capstyle="round", tags=tag)
            c.create_line(cx - 0.14 * s, y, cx + 0.44 * s, y, fill=mau,
                          width=nh, capstyle="round", tags=tag)
    elif ten == "dat_lai":                  # mũi tên vòng ↺
        r = 0.36 * s
        c.create_arc(cx - r, cy - r, cx + r, cy + r, start=110, extent=290,
                     style="arc", outline=mau, width=nh, tags=tag)
        x, y = cx + r * math.cos(math.radians(110)), cy - r * math.sin(math.radians(110))
        k = 0.16 * s
        c.create_polygon(x - k, y - k * 0.2, x + k * 0.5, y - k, x + k * 0.3, y + k * 0.6,
                         fill=mau, outline=mau, tags=tag)
    elif ten == "mui_xuong":                # ▾
        k = 0.22 * s
        c.create_polygon(cx - k, cy - k * 0.5, cx + k, cy - k * 0.5, cx, cy + k * 0.6,
                         fill=mau, outline=mau, tags=tag)


# ── Nút bo tròn ───────────────────────────────────────────────────────────────
class NutTron(tk.Canvas):
    """Nút bo tròn kiểu Evoto.

    kieu  "chinh" vàng chữ đen (một nút chính mỗi màn) · "phu" xám ·
          "toi" xám tối (như "Buy Now") · "chu" chỉ chữ, rê chuột mới có nền ·
          "bat" nút bật/tắt đang bật (chữ vàng).

    Nói chuyện như nút ttk: configure(text=, state=, command=), cget(),
    w["state"] = ..., invoke(), state([...]) — chỗ gọi cũ không phải sửa.
    """

    tu_cuon = False
    #  (nền, nền rê, nền bấm, chữ, nền khi tắt, chữ khi tắt)
    KIEU = {
        "chinh": ("nhan", "nhan2", "nhan3", "chu_nhan", "noi", "mo2"),
        "phu":   ("noi2", "noi3", "vien2", "chu", "noi", "mo2"),
        "toi":   ("noi", "noi2", "noi3", "chu", "tam", "mo2"),
        "chu":   (None, "noi", "noi2", "mo", None, "mo2"),
        #  "bat": nút bật/tắt đang BẬT (vd. Xem trước) — chữ vàng trên nền xám:
        #  thấy ngay đang bật mà không tranh vai với nút chính màu vàng.
        "bat":   ("noi2", "noi3", "vien2", "nhan", "noi", "mo2"),
    }

    def __init__(self, cha, text: str = "", command=None, kieu: str = "phu",
                 font=None, icon: str | None = None, mui_ten: bool = False,
                 rong: int | None = None, nen: str | None = None,
                 takefocus: int = 1):
        self._nen = nen or nen_cua(cha)
        self._kieu = kieu if kieu in self.KIEU else "phu"
        self._chu = str(text)
        self._lenh = command
        self._icon = icon
        self._mui_ten = mui_ten
        self._tt = "normal"
        self._re = self._bam = self._tieu_diem = False
        self._f = _phong(cha, font or CHU_DAM)
        lh = self._f.metrics("linespace")
        self._cao = lh + 2 * max(5, round(lh * 0.42))
        self._s_icon = round(lh * 0.95) if icon else 0
        self._padx = max(10, round(lh * 0.95))
        self._rong_dat = rong
        self._anh = None
        super().__init__(cha, width=self._rong_can(), height=self._cao,
                         highlightthickness=0, borderwidth=0,
                         background=self._nen, takefocus=takefocus,
                         cursor="hand2")
        self._i_nen = self.create_image(0, 0, anchor="nw")
        self._i_chu = self.create_text(0, 0, text="", font=self._f)
        for su_kien, ham in (("<Enter>", self._vao), ("<Leave>", self._ra),
                             ("<ButtonPress-1>", self._nhan),
                             ("<ButtonRelease-1>", self._tha),
                             ("<KeyPress-space>", lambda _e: self.invoke()),
                             ("<KeyPress-Return>", lambda _e: self.invoke()),
                             ("<FocusIn>", lambda _e: self._dat_td(True)),
                             ("<FocusOut>", lambda _e: self._dat_td(False)),
                             ("<Configure>", lambda _e: self._ve())):
            self.bind(su_kien, ham, add="+")
        self._ve()

    # ---- kích thước
    def rong_chu(self) -> int:
        """Bề ngang chữ + biểu tượng + lề — để bài kiểm hỏi “có bị cắt không”."""
        t = self._chu + ("  ▾" if self._mui_ten else "")
        w = self._f.measure(t) + 2 * self._padx
        if self._icon:
            w += self._s_icon + (6 if t else 0)
        return w

    def _rong_can(self) -> int:
        return self._rong_dat or max(self._cao, self.rong_chu())

    # ---- vẽ
    def _ve(self):
        #[[ BE NGANG THAT khi Tk da cap (winfo_width > 1), KE CA LUC CHUA MAP:
        #   <Configure> co the toi TRUOC <Map> (bang dieu khien vua grid lai) —
        #   ve theo be ngang dat luc do roi khong con <Configure> nao nua la
        #   nut / vien chon ket o be ngang hep. Da gap 3/10 o the nhom Retouch. ]]
        try:
            w = self.winfo_width()
            if w <= 1:
                w = int(float(tk.Canvas.cget(self, "width")))
            w = max(1, w)
        except tk.TclError:
            return
        h = self._cao
        ks = [MAU.get(k) if k else None for k in self.KIEU[self._kieu]]
        if self._tt == "disabled":
            mau, chu = ks[4], ks[5]
        elif self._bam:
            mau, chu = ks[2], ks[3]
        elif self._re:
            mau, chu = ks[1], ks[3]
        else:
            mau, chu = ks[0], ks[3]
        if self._kieu == "chu" and (self._re or self._bam) and self._tt != "disabled":
            chu = MAU["chu"]
        vien = MAU["chu"] if (self._tieu_diem and self._tt != "disabled") else None
        if mau is None and vien is None:
            self._anh = None
            self.itemconfigure(self._i_nen, image="")
        else:
            self._anh = anh_bo_goc(self, w, h, h // 2, mau or self._nen,
                                   self._nen, vien)
            self.itemconfigure(self._i_nen, image=self._anh)
        t = self._chu + ("  ▾" if self._mui_ten else "")
        self.delete("icon")
        if self._icon:
            ss = self._s_icon
            tw = self._f.measure(t)
            x0 = (w - (ss + (6 if t else 0) + tw)) / 2
            ve_bieu_tuong(self, self._icon, x0 + ss / 2, h / 2, ss, chu)
            self.coords(self._i_chu, x0 + ss + (6 if t else 0) + tw / 2, h / 2)
        else:
            self.coords(self._i_chu, w / 2, h / 2)
        self.itemconfigure(self._i_chu, text=t, fill=chu)

    # ---- sự kiện
    def _vao(self, _e=None):
        self._re = True
        self._ve()

    def _ra(self, _e=None):
        self._re = self._bam = False
        self._ve()

    def _nhan(self, _e=None):
        if self._tt != "disabled":
            self._bam = True
            self._ve()

    def _tha(self, e=None):
        bam, self._bam = self._bam, False
        self._ve()
        if bam and e is not None and 0 <= e.x < self.winfo_width() \
                and 0 <= e.y < self.winfo_height():
            self.invoke()

    def _dat_td(self, co: bool):
        self._tieu_diem = co
        self._ve()

    def invoke(self):
        if self._tt != "disabled" and self._lenh is not None:
            return self._lenh()
        return None

    # ---- nói chuyện như nút ttk
    def configure(self, cnf=None, **kw):
        if isinstance(cnf, dict):
            kw = {**cnf, **kw}
            cnf = None
        ve = False
        if "text" in kw:
            self._chu = str(kw.pop("text"))
            ve = True
        if "state" in kw:
            self._tt = "disabled" if str(kw.pop("state")) == "disabled" else "normal"
            if self._tt == "disabled":
                self._bam = False
            ve = True
        if "command" in kw:
            self._lenh = kw.pop("command")
        if "nen" in kw:                    # đổi màu chỗ đặt (vd. dải báo đổi mức)
            self._nen = kw.pop("nen")
            tk.Canvas.configure(self, background=self._nen)
            ve = True
        if "kieu" in kw:                   # đổi vai: nút chính (vàng) <-> phụ
            k = kw.pop("kieu")
            if k in self.KIEU and k != self._kieu:
                self._kieu = k
                ve = True
        if kw:
            tk.Canvas.configure(self, **kw)
        elif not ve and cnf is None and not kw:
            pass
        if ve:
            tk.Canvas.configure(self, width=self._rong_can(), cursor=(
                "arrow" if self._tt == "disabled" else "hand2"))
            self._ve()

    config = configure

    def cget(self, key):
        if key == "text":
            return self._chu
        if key == "state":
            return self._tt
        if key == "command":
            return self._lenh
        if key == "kieu":
            return self._kieu
        return tk.Canvas.cget(self, key)

    def __setitem__(self, key, value):
        self.configure({key: value})

    def __getitem__(self, key):
        return self.cget(key)

    def state(self, spec=None):
        if spec is None:
            return ("disabled",) if self._tt == "disabled" else ()
        for s in spec:
            if s == "disabled":
                self.configure(state="disabled")
            elif s == "!disabled":
                self.configure(state="normal")
        return self.state()

    def instate(self, spec) -> bool:
        tt = set(self.state())
        return all((s[1:] not in tt) if s.startswith("!") else (s in tt)
                   for s in spec)


# ── Công tắc ──────────────────────────────────────────────────────────────────
class CongTac(tk.Canvas):
    """Công tắc bật / tắt kiểu Evoto — thay ô tick. Gắn vào BooleanVar sẵn có
    nên read_cfg() và mọi chỗ .get() / .set() giữ nguyên."""

    tu_cuon = False

    def __init__(self, cha, variable: tk.Variable, command=None,
                 nen: str | None = None, takefocus: int = 1):
        self._bien = variable
        self._lenh = command
        self._nen = nen or nen_cua(cha)
        self._tt = "normal"
        self._re = self._td = False
        lh = don_vi(cha)
        self._cao_ct = max(14, round(lh * 0.98))
        self._rong_ct = round(self._cao_ct * 1.8)
        super().__init__(cha, width=self._rong_ct + 2, height=self._cao_ct + 2,
                         highlightthickness=0, borderwidth=0,
                         background=self._nen, takefocus=takefocus,
                         cursor="hand2")
        self._i_ranh = self.create_image(1, 1, anchor="nw")
        self._i_num = self.create_image(0, 0, anchor="nw")
        self._anh = []
        self._vet = variable.trace_add("write", lambda *_a: self._ve())
        for su_kien, ham in (("<ButtonRelease-1>", lambda _e: self.bat_tat()),
                             ("<KeyPress-space>", lambda _e: self.bat_tat()),
                             ("<Enter>", lambda _e: self._dat_re(True)),
                             ("<Leave>", lambda _e: self._dat_re(False)),
                             ("<FocusIn>", lambda _e: self._dat_td(True)),
                             ("<FocusOut>", lambda _e: self._dat_td(False)),
                             ("<Destroy>", self._huy)):
            self.bind(su_kien, ham, add="+")
        self._ve()

    def _huy(self, _e=None):
        try:
            self._bien.trace_remove("write", self._vet)
        except (tk.TclError, ValueError):
            pass

    def _dat_re(self, co):
        self._re = co
        self._ve()

    def _dat_td(self, co):
        self._td = co
        self._ve()

    def bat(self) -> bool:
        try:
            return bool(self._bien.get())
        except (tk.TclError, ValueError):
            return False

    def bat_tat(self):
        """Đảo trạng thái như bấm chuột — rồi gọi lệnh như ô tick cũ."""
        if self._tt == "disabled":
            return
        self._bien.set(not self.bat())
        if self._lenh is not None:
            self._lenh()

    def _ve(self):
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        h, w = self._cao_ct, self._rong_ct
        bat = self.bat()
        if self._tt == "disabled":
            ranh = MAU["vien"] if not bat else "#6b5f1e"
            num = MAU["mo2"]
        elif bat:
            ranh = MAU["nhan2"] if self._re else MAU["nhan"]
            num = MAU["chu_nhan"]
        else:
            ranh = MAU["noi3"] if self._re else MAU["noi2"]
            num = "#b4b7bc"
        vien = MAU["chu"] if (self._td and self._tt != "disabled") else None
        a1 = anh_bo_goc(self, w, h, h // 2, ranh, self._nen, vien)
        d = h - 4
        a2 = anh_tron(self, d, num, ranh)
        self._anh = [a1, a2]
        self.itemconfigure(self._i_ranh, image=a1)
        x = 1 + (w - d - 2 if bat else 2)
        self.coords(self._i_num, x, 3)
        self.itemconfigure(self._i_num, image=a2)

    def configure(self, cnf=None, **kw):
        if isinstance(cnf, dict):
            kw = {**cnf, **kw}
        if "state" in kw:
            self._tt = "disabled" if str(kw.pop("state")) == "disabled" else "normal"
            tk.Canvas.configure(self, cursor=("arrow" if self._tt == "disabled"
                                              else "hand2"))
            self._ve()
        if "command" in kw:
            self._lenh = kw.pop("command")
        if kw:
            tk.Canvas.configure(self, **kw)

    config = configure

    def cget(self, key):
        if key == "state":
            return self._tt
        return tk.Canvas.cget(self, key)

    def __setitem__(self, key, value):
        self.configure({key: value})

    def state(self, spec=None):
        if spec is None:
            return ("disabled",) if self._tt == "disabled" else ()
        for s in spec:
            if s == "disabled":
                self.configure(state="disabled")
            elif s == "!disabled":
                self.configure(state="normal")
        return self.state()

    def instate(self, spec) -> bool:
        tt = set(self.state())
        return all((s[1:] not in tt) if s.startswith("!") else (s in tt)
                   for s in spec)


# ── Nút chọn một trong nhiều (segmented) ─────────────────────────────────────
class PhanDoan(tk.Canvas):
    """Hàng viên chọn kiểu Evoto (Nam | Nữ | Trẻ con…). Gắn vào StringVar:
    lua_chon = [(giá trị, nhãn), ...]. Bấm viên nào thì biến nhận giá trị đó
    rồi gọi command. Mũi tên trái/phải đổi lựa chọn khi đang giữ tiêu điểm."""

    tu_cuon = False

    def __init__(self, cha, variable: tk.Variable, lua_chon, command=None,
                 nen: str | None = None, deu: bool = True, takefocus: int = 1,
                 font=None):
        self._bien = variable
        self._ds = [(str(a), str(b)) for a, b in lua_chon]
        self._lenh = command
        self._nen = nen or nen_cua(cha)
        self._deu = deu
        self._tt = "normal"
        self._re = None
        self._td = False
        self._f = _phong(cha, font or CHU)
        lh = self._f.metrics("linespace")
        self._h = lh + 2 * max(4, round(lh * 0.36))
        self._pad = max(9, round(lh * 0.75))
        self._gap = max(4, round(lh * 0.3))
        self._o: list = []          # (x0, x1) từng viên
        self._anh: list = []
        super().__init__(cha, width=self.rong_can(), height=self._h,
                         highlightthickness=0, borderwidth=0,
                         background=self._nen, takefocus=takefocus,
                         cursor="hand2")
        self._vet = variable.trace_add("write", lambda *_a: self._ve())
        for su_kien, ham in (("<ButtonRelease-1>", self._bam),
                             ("<Motion>", self._di),
                             ("<Leave>", lambda _e: self._dat_re(None)),
                             ("<KeyPress-Left>", lambda _e: self._buoc(-1)),
                             ("<KeyPress-Right>", lambda _e: self._buoc(1)),
                             ("<FocusIn>", lambda _e: self._dat_td(True)),
                             ("<FocusOut>", lambda _e: self._dat_td(False)),
                             ("<Configure>", lambda _e: self._ve()),
                             ("<Destroy>", self._huy)):
            self.bind(su_kien, ham, add="+")
        self._ve()

    def _huy(self, _e=None):
        try:
            self._bien.trace_remove("write", self._vet)
        except (tk.TclError, ValueError):
            pass

    def rong_tung_vien(self) -> list:
        return [self._f.measure(n) + 2 * self._pad for _g, n in self._ds]

    def rong_can(self) -> int:
        return sum(self.rong_tung_vien()) + self._gap * max(0, len(self._ds) - 1)

    def _vi_tri(self, w: int) -> list:
        tung = self.rong_tung_vien()
        can = sum(tung) + self._gap * max(0, len(tung) - 1)
        if self._deu and w > can and tung:
            moi = (w - self._gap * (len(tung) - 1)) / len(tung)
            if moi >= max(tung):
                tung = [moi] * len(tung)
            else:
                du = (w - can) / len(tung)
                tung = [t + du for t in tung]
        o, x = [], 0.0
        for t in tung:
            o.append((round(x), round(x + t)))
            x += t + self._gap
        return o

    def _ve(self):
        try:
            if not self.winfo_exists():
                return
            w = self.winfo_width()          # xem NutTron._ve: không đợi <Map>
            if w <= 1:
                w = self.rong_can()
        except tk.TclError:
            return
        w = max(w, 1)
        self.delete("vien")
        self._o = self._vi_tri(w)
        self._anh = []
        try:
            dang = str(self._bien.get())
        except tk.TclError:
            dang = ""
        for i, ((g, n), (x0, x1)) in enumerate(zip(self._ds, self._o)):
            chon = g == dang
            if self._tt == "disabled":
                mau, chu, vien = MAU["tam"], MAU["mo2"], (MAU["vien2"] if chon else None)
            elif chon:
                mau, chu, vien = MAU["noi2"], MAU["chu"], MAU["mo"]
            elif self._re == i:
                mau, chu, vien = MAU["noi2"], MAU["chu"], None
            else:
                mau, chu, vien = MAU["noi"], MAU["mo"], None
            if chon and self._td and self._tt != "disabled":
                vien = MAU["nhan"]
            a = anh_bo_goc(self, x1 - x0, self._h, round(self._h * 0.3), mau,
                           self._nen, vien)
            self._anh.append(a)
            self.create_image(x0, 0, image=a, anchor="nw", tags="vien")
            self.create_text((x0 + x1) / 2, self._h / 2, text=n, fill=chu,
                             font=self._f, tags="vien")

    def _o_tai(self, x):
        for i, (x0, x1) in enumerate(self._o):
            if x0 <= x <= x1:
                return i
        return None

    def _di(self, e):
        self._dat_re(self._o_tai(e.x))

    def _dat_re(self, i):
        if i != self._re:
            self._re = i
            self._ve()

    def _dat_td(self, co):
        self._td = co
        self._ve()

    def chon(self, gia_tri: str, goi: bool = True):
        if self._tt == "disabled":
            return
        if str(self._bien.get()) != gia_tri:
            self._bien.set(gia_tri)
        if goi and self._lenh is not None:
            self._lenh()

    def _bam(self, e):
        i = self._o_tai(e.x)
        if i is not None:
            self.chon(self._ds[i][0])

    def _buoc(self, huong):
        ds = [g for g, _n in self._ds]
        try:
            i = ds.index(str(self._bien.get()))
        except ValueError:
            i = 0
        j = min(max(i + huong, 0), len(ds) - 1)
        if j != i:
            self.chon(ds[j])
        return "break"

    def dat_lua_chon(self, lua_chon) -> None:
        """Đổi nhãn các viên — vd. nhóm khuôn mặt có mức riêng thì mang dấu ·."""
        moi = [(str(a), str(b)) for a, b in lua_chon]
        if moi == self._ds:
            return
        self._ds = moi
        tk.Canvas.configure(self, width=self.rong_can())
        self._ve()

    def nhan_cua(self, gia_tri: str) -> str:
        return dict(self._ds).get(str(gia_tri), "")

    def configure(self, cnf=None, **kw):
        if isinstance(cnf, dict):
            kw = {**cnf, **kw}
        if "state" in kw:
            self._tt = "disabled" if str(kw.pop("state")) == "disabled" else "normal"
            self._ve()
        if "command" in kw:
            self._lenh = kw.pop("command")
        if kw:
            tk.Canvas.configure(self, **kw)

    config = configure

    def state(self, spec=None):
        if spec is None:
            return ("disabled",) if self._tt == "disabled" else ()
        for s in spec:
            if s == "disabled":
                self.configure(state="disabled")
            elif s == "!disabled":
                self.configure(state="normal")
        return self.state()


# ── Thanh trượt ───────────────────────────────────────────────────────────────
class Truot(tk.Canvas):
    """Thanh trượt kiểu Evoto: rãnh mảnh, đoạn đã kéo sáng hơn, núm tròn.

    Nói chuyện như ttk.Scale: set() / get() / state() / bind — và set() gọi
    command y như ttk.Scale. `goc`: điểm bắt đầu tô (mặc định đầu trái; khoảng
    vắt qua 0 thì tô từ 0 — “Bù sáng −1…+1” đọc được ngay là đang cộng hay trừ).
    """

    tu_cuon = False

    def __init__(self, cha, from_: float, to: float, variable: tk.DoubleVar,
                 command=None, length: int = 160, goc: float | None = None,
                 nen: str | None = None, takefocus: int = 1):
        self.lo, self.hi = float(from_), float(to)
        self._bien = variable
        self._lenh = command
        self._nen = nen or nen_cua(cha)
        if goc is None:
            goc = 0.0 if self.lo < 0.0 < self.hi else self.lo
        self._goc = float(goc)
        self._tt = "normal"
        self._re = self._keo = self._td = False
        lh = don_vi(cha)
        self._r = max(5, round(lh * 0.36))
        self._h = 2 * self._r + 6
        self._anh = None
        super().__init__(cha, width=length, height=self._h,
                         highlightthickness=0, borderwidth=0,
                         background=self._nen, takefocus=takefocus)
        y = self._h / 2
        self._ranh = self.create_line(0, y, 0, y, width=2, capstyle="round",
                                      fill=MAU["vien2"])
        self._to = self.create_line(0, y, 0, y, width=2, capstyle="round",
                                    fill="#c4c7cc")
        self._num = self.create_image(0, 0, anchor="nw")
        self._vet = variable.trace_add("write", lambda *_a: self._ve())
        for su_kien, ham in (("<ButtonPress-1>", self._nhan),
                             ("<B1-Motion>", self._di_keo),
                             ("<ButtonRelease-1>", self._tha),
                             ("<Enter>", lambda _e: self._dat_re(True)),
                             ("<Leave>", lambda _e: self._dat_re(False)),
                             ("<FocusIn>", lambda _e: self._dat_td(True)),
                             ("<FocusOut>", lambda _e: self._dat_td(False)),
                             ("<Configure>", lambda _e: self._ve()),
                             ("<Destroy>", self._huy)):
            self.bind(su_kien, ham, add="+")
        self._ve()

    def _huy(self, _e=None):
        try:
            self._bien.trace_remove("write", self._vet)
        except (tk.TclError, ValueError):
            pass

    # ---- quy đổi giá trị <-> toạ độ
    def _bien_x(self):
        w = self.winfo_width()              # xem NutTron._ve: không đợi <Map>
        if w <= 1:
            w = int(float(tk.Canvas.cget(self, "width")))
        pad = self._r + 1
        return pad, max(pad + 1, w - pad)

    def _x(self, v):
        a, b = self._bien_x()
        if self.hi == self.lo:
            return a
        t = (min(max(v, self.lo), self.hi) - self.lo) / (self.hi - self.lo)
        return a + t * (b - a)

    def _v(self, x):
        a, b = self._bien_x()
        t = min(max((x - a) / max(1, b - a), 0.0), 1.0)
        return self.lo + t * (self.hi - self.lo)

    # ---- vẽ
    def _ve(self):
        try:
            if not self.winfo_exists():
                return
            v = float(self._bien.get())
        except (tk.TclError, ValueError):
            v = self.lo
        a, b = self._bien_x()
        y = self._h / 2
        tat = self._tt == "disabled"
        self.coords(self._ranh, a, y, b, y)
        self.itemconfigure(self._ranh, fill=MAU["vien"] if tat else MAU["vien2"])
        x, x0 = self._x(v), self._x(self._goc)
        self.coords(self._to, min(x, x0), y, max(x, x0), y)
        self.itemconfigure(self._to, fill=MAU["noi3"] if tat else "#c4c7cc")
        if tat:
            mau = MAU["noi3"]
        elif self._keo:
            mau = MAU["nhan"]
        elif self._re:
            mau = "#ffffff"
        else:
            mau = "#c4c7cc"
        vien = MAU["nhan"] if (self._td and not tat and not self._keo) else None
        d = 2 * self._r
        self._anh = anh_tron(self, d, mau, self._nen, vien, 1)
        self.itemconfigure(self._num, image=self._anh)
        self.coords(self._num, x - self._r, y - self._r)

    def _dat_re(self, co):
        self._re = co
        self._ve()

    def _dat_td(self, co):
        self._td = co
        self._ve()

    # ---- chuột
    def _nhan(self, e):
        if self._tt == "disabled":
            return
        self._keo = True
        self.set(self._v(e.x))

    def _di_keo(self, e):
        if self._keo and self._tt != "disabled":
            self.set(self._v(e.x))

    def _tha(self, _e=None):
        if self._keo:
            self._keo = False
            self._ve()

    # ---- nói chuyện như ttk.Scale
    def set(self, v):
        if self._tt == "disabled":
            return
        v = min(max(float(v), self.lo), self.hi)
        self._bien.set(v)
        if self._lenh is not None:
            self._lenh(v)

    def get(self) -> float:
        try:
            return float(self._bien.get())
        except (tk.TclError, ValueError):
            return self.lo

    def state(self, spec=None):
        if spec is None:
            return ("disabled",) if self._tt == "disabled" else ()
        for s in spec:
            if s == "disabled":
                self._tt = "disabled"
            elif s == "!disabled":
                self._tt = "normal"
        self._keo = self._keo and self._tt != "disabled"
        self._ve()
        return self.state()

    def instate(self, spec) -> bool:
        tt = set(self.state())
        return all((s[1:] not in tt) if s.startswith("!") else (s in tt)
                   for s in spec)

    #[[ configure(state=) / cget("state") NHU ttk.Scale — cho nao con goi
    #   sc.configure(state="disabled") (Retouch, _mo_hang) khong phai sua. Va
    #   cget("state") PHAI tra trang thai cua thanh truot: Canvas co san mot
    #   tuy chon "state" rieng (luon "normal"), hoi nham no la luon nghe thay
    #   "dang mo" du thanh da khoa. ]]
    def configure(self, cnf=None, **kw):
        if isinstance(cnf, dict):
            kw = {**cnf, **kw}
            cnf = None
        if not kw:
            return tk.Canvas.configure(self)
        st = kw.pop("state", None)
        if st is not None:
            self.state(["disabled"] if str(st) == "disabled" else ["!disabled"])
        if kw:
            return tk.Canvas.configure(self, **kw)
        return None

    config = configure

    def cget(self, key):
        if key == "state":
            return self._tt
        return tk.Canvas.cget(self, key)

    def __getitem__(self, key):
        return self.cget(key)

    def __setitem__(self, key, value):
        self.configure({key: value})


# ── Thanh mô-đun ─────────────────────────────────────────────────────────────
class ThanhMoDun(tk.Frame):
    """Cột biểu tượng sát mép phải, như cột Color / Portrait / Background của
    Evoto: mỗi mô-đun một nút, nút đang chọn có nền ô vuông bo góc.

    muc = [(mã, tên hiện trong chú thích nổi, tên biểu tượng), ...]
    """

    def __init__(self, cha, muc, khi_chon, nen: str | None = None):
        self._nen = nen or MAU["toi"]
        super().__init__(cha, background=self._nen, padx=5, pady=10)
        self._khi_chon = khi_chon
        self._dang = None
        self.nut: dict = {}
        lh = don_vi(cha)
        self._s = round(lh * 2.35)
        for ma, ten, bt in muc:
            c = tk.Canvas(self, width=self._s, height=self._s, background=self._nen,
                          highlightthickness=0, borderwidth=0, takefocus=1,
                          cursor="hand2")
            c.tu_cuon = False
            c.pack(pady=3)
            c._ma, c._bt, c._re, c._anh = ma, bt, False, None
            c.goi_y = GoiY(c, ten)
            c.bind("<ButtonRelease-1>", lambda _e, m=ma: self._bam(m), add="+")
            c.bind("<KeyPress-space>", lambda _e, m=ma: self._bam(m), add="+")
            c.bind("<KeyPress-Return>", lambda _e, m=ma: self._bam(m), add="+")
            c.bind("<Enter>", lambda _e, cc=c: self._dat_re(cc, True), add="+")
            c.bind("<Leave>", lambda _e, cc=c: self._dat_re(cc, False), add="+")
            self.nut[ma] = c
            self._ve(c)

    def _dat_re(self, c, co):
        c._re = co
        self._ve(c)

    def _bam(self, ma):
        self.chon(ma)
        if self._khi_chon is not None:
            self._khi_chon(ma)

    def chon(self, ma):
        self._dang = ma
        for c in self.nut.values():
            self._ve(c)

    @property
    def dang(self):
        return self._dang

    def _ve(self, c):
        c.delete("all")
        s = self._s
        chon = c._ma == self._dang
        if chon or c._re:
            c._anh = anh_bo_goc(c, s, s, round(s * 0.24),
                                MAU["noi2"] if chon else MAU["noi"], self._nen)
            c.create_image(0, 0, image=c._anh, anchor="nw")
        else:
            c._anh = None
        mau = MAU["chu"] if (chon or c._re) else MAU["mo"]
        ve_bieu_tuong(c, c._bt, s / 2, s / 2, s * 0.5, mau)


class GoiY:
    """Chú thích hiện ra khi rê chuột vào một widget, tắt khi chuột rời đi.

    VÌ SAO (3/10): user: "các chú thích để vào dấu ? cạnh mỗi tính năng, di
    chuột vào mới hiện, cho gọn giao diện". Màn Phân tích có ~20 dòng chữ phụ
    in sẵn — đọc một lần là thuộc, sau đó chỉ còn chiếm chỗ của bảng ảnh.

    Một cửa sổ nổi không viền (overrideredirect), đặt cạnh widget và KẸP
    TRONG CỬA SỔ APP chứ không kẹp theo màn hình: winfo_screenwidth() chỉ là
    màn chính, app nằm ở màn phụ thì chú thích bị đẩy sang màn kia.
    """

    TRE_MS = 280
    RONG = 380

    def __init__(self, w, chu: str = ""):
        self.w = w
        self.chu = chu or ""
        self._hen = None
        self.cua = None            # cửa sổ nổi đang hiện (để bài kiểm hỏi)
        for su_kien, ham in (("<Enter>", self._vao), ("<Leave>", self._ra),
                             ("<ButtonPress>", self._ra)):
            w.bind(su_kien, ham, add="+")

    def dat(self, chu: str) -> None:
        self.chu = chu or ""
        if self.cua is not None:
            self.an()

    def _vao(self, _e=None):
        self._huy_hen()
        if self.chu:
            self._hen = self.w.after(self.TRE_MS, self.hien)

    def _ra(self, _e=None):
        self._huy_hen()
        self.an()

    def _huy_hen(self):
        if self._hen is not None:
            try:
                self.w.after_cancel(self._hen)
            except tk.TclError:
                pass
            self._hen = None

    def hien(self):
        self._hen = None
        if self.cua is not None or not self.chu:
            return
        try:
            if not self.w.winfo_exists() or not self.w.winfo_ismapped():
                return
        except tk.TclError:
            return
        cua = tk.Toplevel(self.w)
        cua.wm_overrideredirect(True)
        try:
            cua.wm_attributes("-topmost", True)
        except tk.TclError:
            pass
        vien = tk.Frame(cua, background=MAU["vien2"], padx=1, pady=1)
        vien.pack()
        tk.Label(vien, text=self.chu, justify="left", anchor="w",
                 wraplength=self.RONG, background=MAU["noi"],
                 foreground=MAU["chu"], font=CHU, padx=11, pady=8).pack()
        cua.update_idletasks()
        cw, ch = cua.winfo_reqwidth(), cua.winfo_reqheight()
        top = self.w.winfo_toplevel()
        tx, ty = top.winfo_rootx(), top.winfo_rooty()
        tw, th = top.winfo_width(), top.winfo_height()
        x = self.w.winfo_rootx() + self.w.winfo_width() + 6
        y = self.w.winfo_rooty() - 4
        if x + cw > tx + tw - 4:                       # tràn phải -> sang trái
            x = max(tx + 4, self.w.winfo_rootx() - cw - 6)
        if y + ch > ty + th - 4:                       # tràn dưới -> nhấc lên
            y = max(ty + 4, ty + th - ch - 4)
        cua.wm_geometry(f"+{x}+{y}")
        self.cua = cua

    def an(self):
        if self.cua is not None:
            try:
                self.cua.destroy()
            except tk.TclError:
                pass
            self.cua = None


class NutHoi(tk.Canvas):
    """Dấu ? trong vòng tròn nhỏ — rê chuột vào là hiện chú thích (GoiY).

    Vẽ bằng Canvas chứ không phải Label "?" vì cần cái vòng — nhìn ra ngay là
    thứ để rê chuột, không lẫn với chữ. Cỡ vòng lấy theo PHÔNG chứ không đặt
    số px: Windows phóng 125–150% thì phông to theo, vòng cố định sẽ cắt chữ.
    Nền lấy theo chỗ đặt (nen_cua) — đặt trên bảng điều khiển hay vùng tối đều
    hoà vào, không thành một ô vuông lệch màu.
    """

    tu_cuon = False

    def __init__(self, cha, chu: str = "", nen: str | None = None):
        f = _phong(cha, (CHU_DAM[0], 8, "bold") if len(CHU_DAM) > 2
                   else (CHU_DAM[0], 8))
        d = f.metrics("linespace") + 3
        bg = nen or nen_cua(cha)
        super().__init__(cha, width=d, height=d, highlightthickness=0,
                         borderwidth=0, background=bg, takefocus=0)
        self._vong = self.create_oval(1, 1, d - 2, d - 2, outline=MAU["vien2"],
                                      width=1)
        self._chu = self.create_text(d / 2, d / 2, text="?", font=f,
                                     fill=MAU["mo"])
        self.goi_y = GoiY(self, chu)
        self.bind("<Enter>", lambda _e: self._sang(True), add="+")
        self.bind("<Leave>", lambda _e: self._sang(False), add="+")

    def _sang(self, vao: bool):
        self.itemconfigure(self._vong, outline=MAU["nhan"] if vao else MAU["vien2"])
        self.itemconfigure(self._chu, fill=MAU["nhan"] if vao else MAU["mo"])


class Nhom(ttk.Frame):
    """Một nhóm tuỳ chọn THU GỌN được: bấm đầu nhóm để mở / đóng.

    Đóng thì vẫn thấy MỘT dòng tóm tắt các giá trị đang chọn — thu gọn mà
    không giấu: nhìn lướt vẫn biết buổi này đang chạy với chế độ nào, khỏi
    phải mở ra kiểm. Phần thân (`.than`) chỉ bị pack_forget, không bị huỷ:
    mọi biến và widget bên trong vẫn sống, read_cfg() đọc như cũ.

    3/10 tối — dáng Evoto: "▶ Tên nhóm" chữ trắng đậm vừa (không in hoa, không
    xám), vạch mảnh ngăn giữa các nhóm.
    """

    def __init__(self, cha, tieu_de: str, mo: bool = False, khi_doi=None,
                 vach: bool = True):
        super().__init__(cha)
        self.tieu_de = tieu_de
        self._khi_doi = khi_doi
        self.dang_mo = False
        nen = nen_cua(self)
        self.dau = tk.Frame(self, background=nen, cursor="hand2",
                            takefocus=1, highlightthickness=1,
                            highlightbackground=nen,
                            highlightcolor=MAU["nhan"], pady=5)
        self.dau.pack(fill="x")
        self.l_mui = tk.Label(self.dau, text="▶", background=nen,
                              foreground=MAU["mo"], font=("Segoe UI", 7))
        self.l_mui.pack(side="left", padx=(0, 7))
        self.l_ten = tk.Label(self.dau, text=tieu_de, anchor="w",
                              background=nen, foreground=MAU["chu"],
                              font=CHU_DAM)
        self.l_ten.pack(side="left")
        self.l_tom = ttk.Label(self, text="", style="Mo2.TLabel",
                               wraplength=300, justify="left")
        self.than = ttk.Frame(self)
        self.vach = tk.Frame(self, height=1, background=MAU["vien"]) if vach else None
        for w in (self.dau, self.l_mui, self.l_ten):
            w.bind("<Button-1>", lambda _e: self.dao())
            w.bind("<Enter>", lambda _e: self._ro(True))
            w.bind("<Leave>", lambda _e: self._ro(False))
        for phim in ("<Return>", "<space>"):
            self.dau.bind(phim, lambda _e: self.dao())
        (self.mo if mo else self.dong)(bao=False)

    def _ro(self, vao: bool):
        self.l_mui.configure(foreground=MAU["chu"] if vao else MAU["mo"])

    def _vach_cuoi(self):
        if self.vach is not None:
            self.vach.pack_forget()
            self.vach.pack(fill="x", pady=(7, 0))

    def mo(self, bao: bool = True):
        self.dang_mo = True
        self.l_mui.configure(text="▼")
        self.l_tom.pack_forget()
        self.than.pack(fill="x", pady=(2, 0))
        self._vach_cuoi()
        if bao and self._khi_doi:
            self._khi_doi(self)

    def dong(self, bao: bool = True):
        self.dang_mo = False
        self.l_mui.configure(text="▶")
        self.than.pack_forget()
        self.l_tom.pack(anchor="w", fill="x", padx=(17, 0), pady=(0, 0))
        self._vach_cuoi()
        if bao and self._khi_doi:
            self._khi_doi(self)

    def dao(self):
        (self.dong if self.dang_mo else self.mo)()

    def dat_tom_tat(self, chu: str) -> None:
        self.l_tom.configure(text=chu)


class ThanhTruot(ttk.Frame):
    """Một tham số = nhãn · dấu ? · ô số ở hàng trên, thanh trượt ở hàng dưới
    (dáng Evoto). Giá trị thật vẫn nằm trong StringVar cũ của app — read_cfg(),
    _num() và mọi chỗ .set() giữ nguyên.

    VÌ SAO KHÔNG TÍNH LẠI MỖI LẦN KÉO
        refresh_plan() chạy at.plan() trên cả buổi (1074 ảnh ~1 giây). Gọi
        theo từng nhịp kéo thì thanh giật cục. Nên: kéo chỉ đổi con số đang
        hiện; THẢ CHUỘT, Enter, rời ô số, hoặc ngừng bấm phím mũi tên 0,4
        giây thì mới gọi `khi_xong` một lần.

    Thanh có KHOẢNG RIÊNG (lo..hi) hẹp hơn khoảng cho phép khi cần: "nghỉ
    quá" cho phép tới 240 phút nhưng thanh chỉ 1–60 — số lớn hơn gõ vào ô
    số, thanh đứng ở mép.

    Bấm đúp vào thanh = về giá trị mặc định (như Lightroom / Evoto).
    """

    def __init__(self, cha, bien: tk.StringVar, lo: float, hi: float,
                 buoc: float, khi_xong=None, phim: float | None = None,
                 so_le: int | None = None, dai: int = 100, nhan: str = "",
                 mo: str = "", mac_dinh: str | None = None):
        super().__init__(cha)
        self.bien = bien
        self.lo, self.hi, self.buoc = float(lo), float(hi), float(buoc)
        self.phim = float(phim or buoc)
        self.so_le = (so_le if so_le is not None
                      else max(0, -int(math.floor(math.log10(self.buoc) + 1e-9))))
        self._khi_xong = khi_xong
        self._mac_dinh = mac_dinh if mac_dinh is not None else str(bien.get())
        self._dang_dat = False
        self._hen = None
        self.columnconfigure(0, weight=1)

        hang = ttk.Frame(self)
        hang.grid(row=0, column=0, sticky="ew")
        self.lbl = ttk.Label(hang, text=nhan)
        self.lbl.pack(side="left")
        self.hoi = NutHoi(hang, mo) if mo else None
        if self.hoi is not None:
            self.hoi.pack(side="left", padx=(6, 0))
        #[[ O so khong vien, nen trung bang dieu khien — doc nhu mot con so,
        #   re chuot / bam vao moi hien vien (kieu "0 ▾" cua Evoto). ]]
        self.o = ttk.Entry(hang, textvariable=bien, width=6, justify="right",
                           style="So.TEntry")
        self.o.pack(side="right")

        self._dv = tk.DoubleVar(value=self._kep(self._doc(), self.lo))
        self.thanh = Truot(self, from_=self.lo, to=self.hi, variable=self._dv,
                           command=self._keo, length=dai)
        self.thanh.grid(row=1, column=0, sticky="ew", pady=(3, 0))

        #[[ CHI TINH LAI KHI SO THAT SU DOI. Bam vao con truot roi tha khong
        #   keo, hay bam vao o so roi bam ra cho khac, la khong doi gi — ma moi
        #   lan tinh lai mat ~1 giay tren buoi 1000 anh. Nen nho gia tri LUC BAT
        #   DAU thao tac (bam chuot / vao o), luc ket thuc so lai. Enter thi
        #   luon tinh: do la nguoi dung chu dong bao "xong". ]]
        self._luc_dau = None
        self.thanh.bind("<ButtonPress-1>", lambda _e: self._bat_dau(), add="+")
        self.thanh.bind("<ButtonRelease-1>", lambda _e: self._xong_neu_doi(),
                        add="+")
        self.thanh.bind("<Double-Button-1>", lambda _e: self.ve_mac_dinh(),
                        add="+")
        for phim_, huong in (("<Left>", -1), ("<Down>", -1),
                             ("<Right>", 1), ("<Up>", 1)):
            self.thanh.bind(phim_, lambda _e, h=huong: self._buoc_phim(h))
        self.o.bind("<FocusIn>", lambda _e: self._bat_dau(), add="+")
        self.o.bind("<Return>", lambda _e: self._xong())
        self.o.bind("<FocusOut>", lambda _e: self._xong_neu_doi())
        bien.trace_add("write", self._bien_doi)

    def _doc(self):
        try:
            return float(str(self.bien.get()).replace(",", "."))
        except (ValueError, tk.TclError):
            return None

    def _kep(self, v, mac_dinh):
        if v is None:
            return mac_dinh
        return min(max(v, self.lo), self.hi)

    def _ghi(self, v: float):
        txt = f"{v:.{self.so_le}f}"
        if self.bien.get() != txt:
            self._dang_dat = True
            try:
                self.bien.set(txt)
            finally:
                self._dang_dat = False

    def _keo(self, _v=None):
        if self._dang_dat:
            return
        v = round(self._dv.get() / self.buoc) * self.buoc
        self._ghi(self._kep(v, self.lo))

    def _bien_doi(self, *_a):
        if self._dang_dat:
            return
        v = self._doc()
        if v is None:
            return
        self._dang_dat = True
        try:
            self._dv.set(self._kep(v, self.lo))
        finally:
            self._dang_dat = False

    def _buoc_phim(self, huong: int):
        if "disabled" in self.thanh.state():
            return "break"
        v = self._kep(self._doc(), self.lo) + huong * self.phim
        v = round(v / self.buoc) * self.buoc
        self._ghi(self._kep(v, self.lo))
        self._bien_doi()
        if self._hen is not None:
            self.after_cancel(self._hen)
        self._hen = self.after(400, self._xong)
        return "break"

    def ve_mac_dinh(self):
        """Bấm đúp vào thanh: trả về mặc định rồi tính lại một lần."""
        if "disabled" in self.thanh.state():
            return
        self._bat_dau()
        self.bien.set(self._mac_dinh)
        self._xong_neu_doi()

    def _bat_dau(self):
        self._luc_dau = self.bien.get()

    def _xong_neu_doi(self):
        if self._luc_dau is not None and self.bien.get() == self._luc_dau:
            return
        self._xong()

    def _xong(self):
        self._hen = None
        self._luc_dau = self.bien.get()
        if self._khi_xong is not None:
            self._khi_xong()

    def configure(self, cnf=None, **kw):
        """Nhận state= như ô Spinbox cũ (chỗ gọi cũ không phải sửa).

        w["state"] = ... cũng đi qua đây (tkinter gọi configure({key: v})),
        nên gộp cnf vào kw trước — đưa thẳng state xuống ttk.Frame là TclError."""
        if isinstance(cnf, dict):
            kw = {**cnf, **kw}
            cnf = None
        st = kw.pop("state", None)
        if st is not None:
            co = ["disabled"] if str(st) == "disabled" else ["!disabled"]
            self.thanh.state(co)
            self.o.state(co)
            self.lbl.state(co)
        if kw:
            return super().configure(**kw)
        if st is None:
            return super().configure()
        return None

    config = configure

    def __setitem__(self, key, value):
        self.configure({key: value})

    def trang_thai(self) -> str:
        """"disabled" / "normal" — để bài kiểm hỏi, khỏi đoán theo widget con."""
        return "disabled" if "disabled" in self.thanh.state() else "normal"


# ── Dải báo nội tuyến ─────────────────────────────────────────────────────────
def _mau_dai(muc: str):
    """(nền dải | None = nền chỗ đặt, màu vạch, màu chữ) theo mức."""
    if muc == "loi":
        return "#3a1d1b", MAU["loi"], "#f6b8b1"
    if muc == "canh":
        return MAU["bang_canh_nen"], MAU["canh"], MAU["bang_canh_chu"]
    if muc == "xong":
        return None, MAU["xong"], MAU["mo"]
    return None, MAU["vien2"], MAU["mo"]


class _NhanDai(tk.Label):
    """Nhãn của DaiBao. Ai cũng configure(text=, foreground=) như Label thường;
    màu chữ truyền vào được hiểu là MỨC của cả dải, rồi dải tự đổi màu, tự
    hiện / ẩn theo."""

    def configure(self, cnf=None, **kw):
        if isinstance(cnf, dict):
            kw = {**cnf, **kw}
            cnf = None
        if not kw:
            return tk.Label.configure(self)
        dai = self.master
        for k in ("foreground", "fg"):
            if k in kw:
                dai.muc = dai._muc_cua(kw.pop(k))
        r = tk.Label.configure(self, **kw) if kw else None
        dai._cap_nhat()
        return r

    config = configure

    def __setitem__(self, key, value):
        self.configure({key: value})


class _NutDai(NutTron):
    """Nút hành động của DaiBao. Chỗ gọi cũ .pack(side="left") / .pack_forget()
    (từ thời nút nằm trên thanh công cụ) thành hiện / ẩn ở mép phải dải."""

    def pack(self, *_a, **_kw):
        self.grid(row=0, column=2, sticky="e", padx=(0, 10), pady=5)
        self.master._cap_nhat()

    pack_configure = pack

    def pack_forget(self):
        self.grid_remove()
        self.master._cap_nhat()


class DaiBao(tk.Frame):
    """Dải báo nội tuyến: vạch màu bên trái, chữ tự xuống dòng theo bề ngang
    thật, chỗ cho MỘT nút hành động ở mép phải. Không có chữ thì tự ẩn.

    VÌ SAO (3/10 tối)
        Dòng tình trạng quét buổi (lbl_scan) từng nằm giữa thanh công cụ. Câu
        của nó dài — "Chỉ 0/60 ảnh có sidecar .xmp — 60 ảnh còn lại sẽ bị bỏ
        qua → Đổi ô Nguồn…" — nên xuống hai ba dòng chữ đỏ, kéo cao cả thanh
        công cụ. Đó là chuyện của BUỔI đang mở, nên nó nằm ngay trên lưới ảnh
        của buổi đó, có nền theo mức: lỗi đỏ, cảnh báo cam, ổn thì chỉ một dòng
        chữ mờ với vạch xanh.

    Chỗ gọi cũ giữ nguyên: `.nhan` configure(text=, foreground=MAU["loi"|
    "canh"|"xong"|...]) như một Label; `.tao_nut()` trả về nút mà .pack() /
    .pack_forget() vẫn chạy. Dải phải được đặt bằng .grid().
    """

    def __init__(self, cha, nen: str | None = None):
        self._nen_ngoai = nen or nen_cua(cha)
        super().__init__(cha, background=self._nen_ngoai)
        self.muc = "mo"
        self._duoc_hien = True
        self._co_cho = False               # đã được .grid() lần nào chưa
        self.columnconfigure(1, weight=1)
        self.vach = tk.Frame(self, width=3, background=self._nen_ngoai)
        self.vach.grid(row=0, column=0, sticky="ns")
        #[[ wraplength ban dau 600 chu khong phai 0: 0 = khong xuong dong, cau
        #   dai 2000 px se doi ca cua so phinh ra truoc khi <Configure> dau tien
        #   kip dat lai theo be ngang that. ]]
        self.nhan = _NhanDai(self, text="", anchor="w", justify="left",
                             background=self._nen_ngoai, foreground=MAU["mo"],
                             font=CHU, padx=10, pady=6, wraplength=600)
        self.nhan.grid(row=0, column=1, sticky="ew")
        self.nut_hd = None
        self.bind("<Configure>", lambda _e: self._dat_rong(), add="+")

    def grid_configure(self, cnf={}, **kw):              # noqa: B006 (như tkinter)
        """Đặt chỗ như .grid() thường — nhưng chưa có chữ thì ẩn ngay (grid
        vẫn nhớ chỗ, lần có chữ sau hiện lại đúng chỗ đó)."""
        self._co_cho = True
        r = super().grid_configure(cnf, **kw)
        if not (self._duoc_hien and str(tk.Label.cget(self.nhan, "text")).strip()):
            super().grid_remove()
        return r

    grid = grid_configure

    @staticmethod
    def _muc_cua(mau) -> str:
        mau = str(mau or "").lower()
        for muc in ("loi", "canh", "xong"):
            if mau == MAU[muc].lower():
                return muc
        return "mo"

    def tao_nut(self, text: str, command=None) -> NutTron:
        nen = _mau_dai(self.muc)[0] or self._nen_ngoai
        self.nut_hd = _NutDai(self, text, command=command, kieu="phu", font=CHU,
                              nen=nen)
        return self.nut_hd

    def hien(self, co: bool) -> None:
        """Cho / không cho dải hiện (mô-đun Retouch không cần nó)."""
        self._duoc_hien = bool(co)
        self._cap_nhat()

    def dang_hien(self) -> bool:
        return bool(self.winfo_manager())

    def _cap_nhat(self):
        nen, vach, chu = _mau_dai(self.muc)
        nen = nen or self._nen_ngoai
        tk.Frame.configure(self, background=nen)
        self.vach.configure(background=vach)
        tk.Label.configure(self.nhan, background=nen, foreground=chu)
        if self.nut_hd is not None and self.nut_hd._nen != nen:
            self.nut_hd.configure(nen=nen)
        if self._co_cho:
            co = (self._duoc_hien
                  and bool(str(tk.Label.cget(self.nhan, "text")).strip()))
            try:
                if co and not self.winfo_manager():
                    self.grid()
                elif not co and self.winfo_manager():
                    self.grid_remove()
            except tk.TclError:
                pass
        self._dat_rong()

    def _dat_rong(self):
        """Xuống dòng theo bề ngang THẬT của dải (trừ vạch, lề, nút)."""
        try:
            w = self.winfo_width()
            if w <= 1:
                return
            bot = 3 + 2 * 10 + 4
            if self.nut_hd is not None and self.nut_hd.winfo_manager():
                bot += self.nut_hd.winfo_reqwidth() + 10
            rong = max(160, w - bot)
            if int(str(tk.Label.cget(self.nhan, "wraplength")) or 0) != rong:
                tk.Label.configure(self.nhan, wraplength=rong)
        except tk.TclError:
            pass


class TheBao(tk.Frame):
    """Khung báo nhỏ NẰM TRONG bảng điều khiển: nền theo mức (như DaiBao),
    vạch màu bên trái, chữ xuống dòng theo bề ngang thật, nút hành động ở dòng
    dưới (bảng điều khiển hẹp — chữ và nút đứng ngang nhau là chữ bị bóp).

    Hiện / ẩn do chỗ gọi lo (pack / pack_forget) — nó nằm giữa các hàng khác
    của một nhóm, chỉ chỗ gọi biết nó phải đứng trước hàng nào.
    """

    def __init__(self, cha, muc: str = "canh", chu: str = ""):
        nen, vach, mau_chu = _mau_dai(muc)
        self._nen = nen or nen_cua(cha)
        super().__init__(cha, background=self._nen)
        tk.Frame(self, width=3, background=vach).pack(side="left", fill="y")
        self.than = tk.Frame(self, background=self._nen, padx=10, pady=7)
        self.than.pack(side="left", fill="both", expand=True)
        self.nhan = tk.Label(self.than, text=chu, background=self._nen,
                             foreground=mau_chu, font=CHU, justify="left",
                             anchor="w", wraplength=280)
        self.nhan.pack(fill="x")
        self.than.bind("<Configure>", self._dat_rong, add="+")

    def _dat_rong(self, e):
        rong = max(120, e.width - 2 * 10 - 2)
        try:
            if int(str(self.nhan.cget("wraplength")) or 0) != rong:
                self.nhan.configure(wraplength=rong)
        except tk.TclError:
            pass

    def tao_nut(self, text: str, command=None) -> NutTron:
        nut = NutTron(self.than, text, command=command, kieu="phu", font=CHU,
                      nen=self._nen)
        nut.pack(anchor="w", pady=(6, 0))
        return nut


# ── Nhãn một dòng ─────────────────────────────────────────────────────────────
class NhanGon(tk.Label):
    """Nhãn MỘT dòng: chữ dài hơn chỗ thì cắt bằng "…", rê chuột hiện câu đủ.

    VÌ SAO (3/10 tối): thanh trạng thái chỉ cao một dòng. Câu lần gửi gần
    nhất có khi dài gấp đôi chỗ — xuống dòng là cả thanh phình ra, lưới ảnh
    nhảy lên nhảy xuống mỗi lần câu đổi. cget("text") vẫn trả câu ĐỦ: mọi chỗ
    đọc chữ (và bài kiểm) không phải đổi.

    toi_da: bề ngang tối đa (px). None = theo bề ngang THẬT đang được cấp —
    dùng khi nhãn nằm trong một cột giãn (pack fill="x", expand=True).
    """

    def __init__(self, cha, toi_da: int | None = None, **kw):
        self._chu_du = str(kw.pop("text", ""))
        self._toi_da = toi_da
        kw.pop("wraplength", None)
        self._f = _phong(cha, kw.get("font") or CHU)
        super().__init__(cha, **kw)
        self.goi_y = GoiY(self, "")
        if toi_da is None:
            self.bind("<Configure>", lambda _e: self._dat(), add="+")
        self._dat()

    def _gioi_han(self):
        if self._toi_da is not None:
            return self._toi_da
        try:
            w = self.winfo_width()
        except tk.TclError:
            return None
        if w <= 1:
            return None
        return w - 2 * int(str(tk.Label.cget(self, "padx")) or 0) - 2

    def _dat(self):
        t = " ".join(self._chu_du.split())
        gh = self._gioi_han()
        hien = t
        if gh is not None and gh > 0 and self._f.measure(t) > gh:
            lo, hi = 0, len(t)
            while lo < hi:
                giua = (lo + hi + 1) // 2
                if self._f.measure(t[:giua].rstrip() + "…") <= gh:
                    lo = giua
                else:
                    hi = giua - 1
            hien = t[:lo].rstrip() + "…"
        try:
            if str(tk.Label.cget(self, "text")) != hien:
                tk.Label.configure(self, text=hien)
        except tk.TclError:
            return
        moi = self._chu_du if hien != t else ""
        if moi != self.goi_y.chu:            # đừng tắt chú thích đang hiện vô cớ
            self.goi_y.dat(moi)

    def dang_cat(self) -> bool:
        """Chữ đang hiện có bị cắt không — để bài kiểm hỏi."""
        return str(tk.Label.cget(self, "text")) != " ".join(self._chu_du.split())

    def configure(self, cnf=None, **kw):
        if isinstance(cnf, dict):
            kw = {**cnf, **kw}
            cnf = None
        doi = "text" in kw
        if doi:
            self._chu_du = str(kw.pop("text"))
        kw.pop("wraplength", None)
        if "font" in kw:
            self._f = _phong(self, kw["font"])
            doi = True
        if not kw and not doi:
            return tk.Label.configure(self)
        r = tk.Label.configure(self, **kw) if kw else None
        if doi:
            self._dat()
        return r

    config = configure

    def cget(self, key):
        if key == "text":
            return self._chu_du
        return tk.Label.cget(self, key)

    def __getitem__(self, key):
        return self.cget(key)

    def __setitem__(self, key, value):
        self.configure({key: value})


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
