"""Cửa sổ soát ảnh sau khi đã ghi màu — lưới ảnh nhỏ, đánh dấu tấm cần sửa.

VỊ TRÍ TRONG QUY TRÌNH
    Ghi màu (khâu 3)  ->  DỰNG ẢNH DUYỆT  ->  SOÁT Ở ĐÂY  ->  sửa mấy tấm được
    đánh dấu trong Lightroom  ->  mới Export (khâu 4).

    Đúng thứ tự người dùng chốt: "sau khi ghi màu mới vào Lightroom thì vẫn cần
    đi check lại một lượt xem ảnh đã thực sự ổn chưa. Nếu chưa cần sửa ngay.
    Sau khi check hết thì mới Export được."

VÌ SAO VẼ TRÊN CANVAS CHỨ KHÔNG PHẢI MỖI ẢNH MỘT WIDGET
    Một buổi hơn nghìn ảnh. Mỗi Label giữ một PhotoImage 240px là khoảng 300 KB
    bộ nhớ — nghìn tấm là ~300 MB chỉ để hiện lưới, chưa kể Tk chậm hẳn khi
    phải quản nghìn widget. Nên: một Canvas duy nhất, chỉ dựng ảnh cho những
    hàng ĐANG NHÌN THẤY (cộng một vành đai đệm), ra khỏi vùng thì thả ra. Bộ
    nhớ theo màn hình chứ không theo số ảnh.

VÌ SAO ĐỌC BẢNG ẢNH LẶP LẠI
    Plugin ghi duyet_anh.tsv sau MỖI LÔ chứ không đợi hết. Cửa sổ này đọc lại
    mỗi 1,5 giây nên soát được ngay từ lô đầu, trong lúc các lô sau còn đang
    render. Không phải ngồi chờ cả buổi rồi mới bắt đầu nhìn.
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path

import tkinter as tk
from tkinter import messagebox, ttk

import duyet
import giao_dien as gd

#[[ Toán bố cục nằm trong duyet.py chứ không ở đây.
#   Lý do: file này import tkinter, mà bài kiểm thì phải chạy được trên máy
#   không có màn hình và không có Tk. Để chung thì không kiểm được phần dễ sai
#   nhất (bấm vào ô nào ra ô nào) mà lại là phần thuần số học. ]]
from duyet import CANH_NHO, DEM, CAO_TEN, VANH_DAI, so_cot, vi_tri, chi_so_tai, khoang_hang, tong_cao   # noqa: E402,F401


# ------------------------------------------------------------------- cửa sổ soát

class CuaSoDuyet(tk.Toplevel):
    """Lưới ảnh duyệt. Bấm một tấm = đánh dấu "cần sửa"."""

    O_NGANG = CANH_NHO + DEM
    O_DOC = CANH_NHO + DEM + CAO_TEN

    def __init__(self, app, folder: Path, dest: Path):
        super().__init__(app)
        self.app = app
        self.folder = Path(folder)
        self.dest = Path(dest)

        self.title(f"Duyệt nhanh — {self.folder.name}")
        self.geometry("1280x820")
        self.configure(background=gd.MAU["nen"])

        self.muc: list[dict] = []          # {src, jpg}
        self.co_roi: set[str] = set()      # src đã có trong lưới, tránh thêm trùng
        self.can_sua, self.da_soat = duyet.doc_lua_chon(self.dest)
        self.i = 0
        self.cot = 1
        self._anh: dict[int, object] = {}   # ImageTk.PhotoImage vùng đang nhìn
        self._ve_roi: set[int] = set()
        self.q: queue.Queue = queue.Queue()
        self._dung = threading.Event()

        self._dung_giao_dien()
        self._nap_nen()
        self.after(120, self._bom)
        self.protocol("WM_DELETE_WINDOW", self._dong)
        self.bind("<Escape>", lambda _e: self._dong())
        self.canvas.focus_set()

    # ------------------------------------------------------------ dựng giao diện
    def _dung_giao_dien(self):
        m = gd.MAU
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        dau = tk.Frame(self, background=m["tam"], padx=16, pady=10)
        dau.grid(row=0, column=0, sticky="ew")
        dau.columnconfigure(1, weight=1)
        tk.Label(dau, text="Soát màu trước khi Export", background=m["tam"],
                 foreground=m["chu"], font=gd.CHU_TO).grid(row=0, column=0, sticky="w")
        self.lbl_tt = tk.Label(dau, text="", background=m["tam"],
                               foreground=m["mo"], font=gd.CHU, anchor="e")
        self.lbl_tt.grid(row=0, column=1, sticky="e")
        tk.Label(dau, background=m["tam"], foreground=m["mo2"], font=gd.CHU_NHO,
                 anchor="w",
                 text="Bấm vào ảnh = đánh dấu cần sửa · phím cách = đánh dấu · "
                      "Enter = xem to · mũi tên = di chuyển"
                 ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        giua = tk.Frame(self, background=m["nen"])
        giua.grid(row=1, column=0, sticky="nsew")
        giua.columnconfigure(0, weight=1)
        giua.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(giua, background=m["nen"], highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(giua, orient="vertical", command=self.canvas.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=sb.set)

        self.canvas.bind("<Configure>", self._doi_co)
        self.canvas.bind("<Button-1>", self._bam)
        self.canvas.bind("<Double-1>", lambda e: (self._bam(e, dao=False),
                                                  self._xem_to()))
        #[[ Cuộn chuột: Windows gửi <MouseWheel> với delta bội 120, Linux gửi
        #   Button-4/5. Bắt cả hai thì cùng một bản chạy được trên máy Mac của
        #   người dùng lẫn máy Windows. ]]
        self.canvas.bind("<MouseWheel>",
                         lambda e: self._cuon(-1 if e.delta > 0 else 1))
        self.canvas.bind("<Button-4>", lambda _e: self._cuon(-1))
        self.canvas.bind("<Button-5>", lambda _e: self._cuon(1))
        for phim, buoc in (("<Left>", -1), ("<Right>", 1)):
            self.canvas.bind(phim, lambda _e, b=buoc: self._di(b))
        self.canvas.bind("<Up>", lambda _e: self._di(-self.cot))
        self.canvas.bind("<Down>", lambda _e: self._di(self.cot))
        self.canvas.bind("<space>", lambda _e: self._dao(self.i))
        self.canvas.bind("<Return>", lambda _e: self._xem_to())

        duoi = tk.Frame(self, background=m["tam"], padx=16, pady=10)
        duoi.grid(row=2, column=0, sticky="ew")
        duoi.columnconfigure(0, weight=1)
        self.lbl_dem = tk.Label(duoi, text="", background=m["tam"],
                                foreground=m["chu"], font=gd.CHU, anchor="w")
        self.lbl_dem.grid(row=0, column=0, sticky="w")
        self.btn_dau = ttk.Button(duoi, text="Gom vào Lightroom để sửa",
                                  style="Chinh.TButton", command=self._gui_danh_dau)
        self.btn_dau.grid(row=0, column=1, padx=(10, 6))
        ttk.Button(duoi, text="Bỏ hết đánh dấu", style="Pha.TButton",
                   command=self._bo_het).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(duoi, text="Đóng", style="Pha.TButton",
                   command=self._dong).grid(row=0, column=3)

    # ------------------------------------------------------------- nạp nền
    def _nap_nen(self):
        """Đọc bảng ảnh và dựng ảnh nhỏ ở luồng riêng.

        Ở luồng riêng vì thu nhỏ một nghìn ảnh mất vài chục giây; làm trong
        luồng giao diện thì cửa sổ đứng hình suốt thời gian đó."""
        def chay():
            cho = 0.0
            while not self._dung.is_set():
                cap = duyet.bang_anh()
                moi = [(s, j) for s, j in cap if s not in self.co_roi]
                for s, j in moi:
                    if self._dung.is_set():
                        return
                    self.co_roi.add(s)
                    duyet.anh_nho(j, CANH_NHO)      # dựng sẵn, ghi đệm ra đĩa
                    self.q.put(("them", s, j))
                td = duyet.tien_do()
                self.q.put(("tiendo", td, None))
                if td.get("trang_thai") in ("xong", "loi") and not moi:
                    #[[ Xong rồi thì ngừng dò — nhưng chỉ khi lượt này không
                    #   thêm ảnh nào nữa. Ngừng ngay lúc thấy "xong" có thể bỏ
                    #   sót lô cuối vừa được ghi. ]]
                    cho += 1
                    if cho >= 2:
                        return
                else:
                    cho = 0
                self._dung.wait(1.5)

        threading.Thread(target=chay, daemon=True).start()

    def _bom(self):
        """Chuyển kết quả từ luồng nền sang giao diện. Chạy trong luồng Tk."""
        doi = False
        try:
            while True:
                loai, a, b = self.q.get_nowait()
                if loai == "them":
                    self.muc.append({"src": a, "jpg": b})
                    doi = True
                elif loai == "tiendo":
                    self.lbl_tt.configure(text=duyet.mo_ta(a) or "")
        except queue.Empty:
            pass
        if doi:
            self._dat_vung_cuon()
            self._ve()
            self._dem()
        if not self._dung.is_set():
            self.after(200, self._bom)

    # ---------------------------------------------------------------- bố cục
    def _doi_co(self, _e=None):
        cot = so_cot(self.canvas.winfo_width(), self.O_NGANG)
        if cot != self.cot:
            self.cot = cot
            self._xoa_het_ve()
            self._dat_vung_cuon()
        self._ve()

    def _dat_vung_cuon(self):
        cao = tong_cao(len(self.muc), self.cot, self.O_DOC)
        self.canvas.configure(scrollregion=(0, 0, self.cot * self.O_NGANG, cao))

    def _cuon(self, huong: int):
        self.canvas.yview_scroll(huong * 2, "units")
        self._ve()

    def _dinh(self) -> int:
        """Vị trí cuộn hiện tại, tính bằng pixel."""
        try:
            dau = self.canvas.yview()[0]
        except Exception:                                      # noqa: BLE001
            return 0
        return int(dau * tong_cao(len(self.muc), self.cot, self.O_DOC))

    # ------------------------------------------------------------------ vẽ
    def _xoa_het_ve(self):
        self.canvas.delete("o")
        self._anh.clear()
        self._ve_roi.clear()

    def _ve(self):
        """Dựng ảnh cho vùng đang nhìn thấy, thả ảnh đã ra khỏi vành đai."""
        if not self.muc:
            return
        cao = self.canvas.winfo_height() or 600
        dau_h, cuoi_h = khoang_hang(self._dinh(), cao, self.O_DOC, VANH_DAI)
        dau = max(0, dau_h * self.cot)
        cuoi = min(len(self.muc), (cuoi_h + 1) * self.cot)

        for i in list(self._ve_roi):
            if i < dau or i >= cuoi:
                self.canvas.delete(f"o{i}")
                self._anh.pop(i, None)
                self._ve_roi.discard(i)

        for i in range(dau, cuoi):
            if i not in self._ve_roi:
                self._ve_mot(i)
        self._ve_vien()

    def _doc_anh(self, jpg):
        """Đọc ảnh nhỏ thành đối tượng Tk vẽ được. None nếu không đọc nổi.

        PHẢI QUA PIL, KHÔNG DÙNG tk.PhotoImage ĐƯỢC.
            tk.PhotoImage chỉ đọc GIF / PGM / PPM / PNG. Nó KHÔNG đọc JPEG —
            mà ảnh duyệt Lightroom xuất ra chính là JPEG. Bản đầu gọi thẳng
            tk.PhotoImage(file=<.jpg>) nên MỌI ô đều ra "không mở được", dù
            file ảnh hoàn toàn bình thường. Lỗi này không lộ ra ở máy dựng gói
            vì ở đó không mở được cửa sổ nào để nhìn.

        Ảnh phải được GIỮ THAM CHIẾU ở nơi gọi (self._anh), nếu không Python
        thu hồi ngay và canvas hiện ô trống — bẫy kinh điển của Tk.
        """
        if not jpg:
            return None, "chưa dựng được ảnh nhỏ"
        try:
            from PIL import Image, ImageTk
        except ImportError:
            return None, "thiếu Pillow"
        try:
            with Image.open(jpg) as im:
                im = im.convert("RGB")
                return ImageTk.PhotoImage(im), ""
        except Exception as ex:                                # noqa: BLE001
            return None, type(ex).__name__

    def _ve_mot(self, i: int):
        m = gd.MAU
        x, y = vi_tri(i, self.cot, self.O_NGANG, self.O_DOC)
        r = self.muc[i]
        tag = ("o", f"o{i}")
        # góc trái trên và cạnh của khung ảnh trong ô
        ax, ay = x + DEM // 2, y + DEM // 2

        img, vi_sao = self._doc_anh(duyet.anh_nho(r["jpg"], CANH_NHO))
        if img is not None:
            self._anh[i] = img
            self.canvas.create_image(ax, ay, image=img, anchor="nw", tags=tag)
        else:
            #[[ Không dựng được ảnh thì vẫn phải có một ô để bấm — bỏ trống thì
            #   ảnh đó biến mất khỏi lượt soát mà không ai biết. Và phải NÓI RA
            #   vì sao: "không mở được" không phân biệt được thiếu thư viện với
            #   file hỏng, mà hai cái đó chữa khác hẳn nhau. ]]
            self.canvas.create_rectangle(ax, ay, ax + CANH_NHO, ay + CANH_NHO,
                                         fill=m["noi"], outline=m["vien"], tags=tag)
            self.canvas.create_text(ax + CANH_NHO // 2, ay + CANH_NHO // 2,
                                    text=vi_sao or "không mở được", fill=m["mo2"],
                                    font=gd.CHU_NHO, tags=tag)
        # tên file nằm DƯỚI khung ảnh, không đè lên nó
        self.canvas.create_text(ax, ay + CANH_NHO + 3,
                                text=Path(r["src"]).name, anchor="nw",
                                fill=m["mo"], font=gd.CHU_NHO, tags=tag)
        self._ve_roi.add(i)

    def _ve_vien(self):
        """Viền trạng thái: đỏ = cần sửa, xanh = đang chọn, mờ = đã soát."""
        m = gd.MAU
        self.canvas.delete("vien")
        for i in sorted(self._ve_roi):
            src = self.muc[i]["src"]
            x, y = vi_tri(i, self.cot, self.O_NGANG, self.O_DOC)
            mau, day = None, 2
            if src in self.can_sua:
                mau, day = m["loi"], 3
            elif src in self.da_soat:
                mau, day = m["xong"], 1
            if i == self.i:
                mau, day = m["nhan"], 3
            if mau:
                ax, ay = x + DEM // 2, y + DEM // 2
                self.canvas.create_rectangle(
                    ax - 2, ay - 2, ax + CANH_NHO + 2, ay + CANH_NHO + 2,
                    outline=mau, width=day, tags="vien")

    def _dem(self):
        n = len(self.muc)
        self.lbl_dem.configure(
            text=f"{n} ảnh · đã soát {len(self.da_soat & self.co_roi)} · "
                 f"cần sửa {len(self.can_sua)}")
        self.btn_dau.configure(state="normal" if self.can_sua else "disabled")

    # ------------------------------------------------------------- tương tác
    def _bam(self, e, dao: bool = True):
        x = int(self.canvas.canvasx(e.x))
        y = int(self.canvas.canvasy(e.y))
        i = chi_so_tai(x, y, self.cot, len(self.muc), self.O_NGANG, self.O_DOC)
        if i is None:
            return
        self.i = i
        if dao:
            self._dao(i)
        else:
            self._ve_vien()

    def _dao(self, i: int):
        if not (0 <= i < len(self.muc)):
            return
        src = self.muc[i]["src"]
        if src in self.can_sua:
            self.can_sua.discard(src)
        else:
            self.can_sua.add(src)
        self.da_soat.add(src)
        self._ve_vien()
        self._dem()
        self._luu()

    def _di(self, buoc: int):
        if not self.muc:
            return
        self.i = max(0, min(len(self.muc) - 1, self.i + buoc))
        self.da_soat.add(self.muc[self.i]["src"])
        self._hien_ra(self.i)
        self._ve()
        self._dem()

    def _hien_ra(self, i: int):
        """Cuộn sao cho ô thứ i nằm trong khung nhìn."""
        _x, y = vi_tri(i, self.cot, self.O_NGANG, self.O_DOC)
        cao_tong = tong_cao(len(self.muc), self.cot, self.O_DOC)
        cao = self.canvas.winfo_height() or 600
        dinh = self._dinh()
        if y < dinh:
            self.canvas.yview_moveto(max(0.0, y / cao_tong))
        elif y + self.O_DOC > dinh + cao:
            self.canvas.yview_moveto(
                max(0.0, (y + self.O_DOC - cao) / cao_tong))

    def _luu(self):
        try:
            duyet.luu_lua_chon(self.dest, self.can_sua, self.da_soat)
        except OSError:
            pass          # mất bản nhớ thì soát lại, không đáng để vỡ cửa sổ

    def _bo_het(self):
        if not self.can_sua:
            return
        if not messagebox.askokcancel(
                "Bỏ hết đánh dấu",
                f"Bỏ đánh dấu của {len(self.can_sua)} ảnh?", parent=self):
            return
        self.can_sua.clear()
        self._ve_vien()
        self._dem()
        self._luu()

    def _gui_danh_dau(self):
        n = len(self.can_sua)
        if not n:
            return
        bst = duyet.ten_bo_suu_tap(self.folder)
        if not messagebox.askokcancel(
                "Gom ảnh cần sửa vào Lightroom",
                f"{n} ảnh cần sửa sẽ được:\n\n"
                f"    · gắn nhãn ĐỎ\n"
                f"    · gắn {duyet.SAO_CAN_SUA} SAO\n"
                f"    · gom vào bộ sưu tập “{bst}”\n\n"
                "Trong Lightroom lọc theo nhãn đỏ ở Library Filter, hoặc bấm "
                "thẳng bộ sưu tập ở cột trái.\n\n"
                f"Lưu ý: số sao cũ của mấy tấm này sẽ bị ghi đè thành "
                f"{duyet.SAO_CAN_SUA}.\n\n"
                "Lightroom phải đang mở thì plugin mới nhận được.",
                parent=self):
            return
        try:
            duyet.danh_dau(sorted(self.can_sua), "red",
                           sao=duyet.SAO_CAN_SUA, bo_suu_tap=bst)
        except (OSError, ValueError) as ex:
            messagebox.showerror("Không gửi được", str(ex), parent=self)
            return
        self.app.status(
            f"Đã gửi {n} ảnh sang Lightroom — nhãn đỏ + {duyet.SAO_CAN_SUA} sao, "
            f"và bộ sưu tập “{bst}” (plugin dò 5 giây một lần)", gd.MAU["nhan"])

    # ------------------------------------------------------------- xem ảnh to
    def _xem_to(self):
        if not (0 <= self.i < len(self.muc)):
            return
        XemTo(self, self.i)

    def _dong(self):
        self._dung.set()
        self._luu()
        n = len(self.can_sua)
        if n:
            self.app.status(f"Soát xong — {n} ảnh cần sửa. Bấm “Gom vào "
                            "Lightroom để sửa” để tìm lại chúng ở Collections.",
                            gd.MAU["canh"])
        self.destroy()


class XemTo(tk.Toplevel):
    """Xem một tấm ở cỡ lớn. Mũi tên đi tiếp, phím cách đánh dấu."""

    def __init__(self, cha: CuaSoDuyet, i: int):
        super().__init__(cha)
        self.cha = cha
        self.i = i
        self.title("Xem to")
        self.geometry("1400x900")
        self.configure(background="#0c0c0c")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.lbl = tk.Label(self, background="#0c0c0c", foreground=gd.MAU["mo"])
        self.lbl.grid(row=0, column=0, sticky="nsew")
        self.chu = tk.Label(self, background="#0c0c0c", foreground=gd.MAU["chu"],
                            font=gd.CHU, pady=8)
        self.chu.grid(row=1, column=0, sticky="ew")

        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Left>", lambda _e: self._di(-1))
        self.bind("<Right>", lambda _e: self._di(1))
        self.bind("<space>", lambda _e: self._dao())
        self.bind("<Configure>", self._ve_lai)
        self._anh = None
        self._co = (0, 0)
        self.focus_set()
        self.after(50, self._hien)

    def _di(self, buoc: int):
        self.i = max(0, min(len(self.cha.muc) - 1, self.i + buoc))
        self.cha.i = self.i
        self.cha.da_soat.add(self.cha.muc[self.i]["src"])
        self.cha._ve_vien()
        self.cha._dem()
        self._hien()

    def _dao(self):
        self.cha._dao(self.i)
        self._nhan()

    def _ve_lai(self, _e=None):
        co = (self.lbl.winfo_width(), self.lbl.winfo_height())
        if co != self._co and co[0] > 1:
            self._co = co
            self._hien()

    def _hien(self):
        r = self.cha.muc[self.i]
        w = max(self.lbl.winfo_width(), 900)
        h = max(self.lbl.winfo_height(), 600)
        try:
            from PIL import Image, ImageTk
            with Image.open(r["jpg"]) as im:
                im = im.convert("RGB")
                im.thumbnail((w, h))
                self._anh = ImageTk.PhotoImage(im)
            self.lbl.configure(image=self._anh, text="")
        except Exception as ex:                                # noqa: BLE001
            self._anh = None
            self.lbl.configure(image="",
                               text=f"Không mở được ảnh:\n{type(ex).__name__}: {ex}")
        self._nhan()

    def _nhan(self):
        r = self.cha.muc[self.i]
        dau = "  ●  CẦN SỬA" if r["src"] in self.cha.can_sua else ""
        self.chu.configure(
            text=f"{self.i + 1}/{len(self.cha.muc)}   {Path(r['src']).name}{dau}"
                 "        ← →  đi tiếp   ·   phím cách  đánh dấu   ·   Esc  đóng",
            foreground=gd.MAU["loi"] if dau else gd.MAU["chu"])
