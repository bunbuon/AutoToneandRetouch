"""Học màu Lightroom TỪ APP — ⋯ › “Học màu Lightroom cho máy ảnh này…” (15/10).

User 15/10: "giờ sẽ cần đóng gói để cho cài đặt trên các máy khác và thợ có thể sử
dụng các thiết bị khác nhau" -> chọn "Đưa nút học + 4 mô hình + công tắc". Trước đây
chỉ có HOC_MAU_LR.bat (dòng lệnh, cần Python hệ thống, không có trong gói cài).

  · HỌC = plugin dựng ~20 ảnh của buổi × 29 biến thể (WB / sáng / HSL / curve / CG) rồi
    TRẢ LẠI thông số gốc; app học bảng "thông số -> màu da Lightroom dựng ra" của đúng
    máy + profile đó (mo_hinh_lr). Dùng cho "Chế độ nhanh một lượt" (mau_mot_luot).
    Đo trên máy này: ~5 phút mỗi máy (580 lần dựng).
  · TRONG LÚC HỌC chặn mọi việc GHI vào Lightroom (_hm_chan: Xử lý ảnh, Áp, Hoàn tác,
    Xuất, Đọc từ Lightroom, Học từ buổi này, xem preset): plugin trả thông số gốc giữa
    các mẻ — một job áp chen vào sẽ bị đè mất. Đóng app = hỏi, rồi xin plugin dừng và
    chờ nó trả ảnh (hoc_mau_lr._xin_dung_cho_tra) mới thoát.
  · Luồng nền chỉ ghi vào self._hm (dict); Tk đọc bằng after() — không gọi Tk từ luồng
    nền.
"""
from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import giao_dien as gd

TIEU_DE = "Học màu Lightroom"
NHAN_MENU = "Học màu Lightroom cho máy ảnh này…"
TOI_THIEU = 6                 # = hoc_mau_lr.TOI_THIEU (ảnh dùng được tối thiểu của một máy)
PHUT_MOI_MAY = (5, 10)        # máy này ~5.3 phút / máy; máy yếu hơn lâu hơn

TRANG_THAI = {"chua_hoc": "chưa học", "chua_dat": "đã học, CHƯA ĐẠT",
              "goi": "có sẵn trong bộ cài", "dat": "đã học (ĐẠT)"}


def ten_khoa(k: str) -> str:
    """'NIKON_Z_8__Adobe_Standard__15.4' -> 'NIKON Z 8 · Adobe Standard'."""
    p = str(k).split("__")
    if len(p) < 2:
        return str(k).replace("_", " ")
    return f"{p[0].replace('_', ' ')} · {p[1].replace('_', ' ')}"


class HopChonMay(tk.Toplevel):
    """Chọn máy / profile sẽ học. ds: [(khoá, số ảnh, trạng thái)] -> self.kq: [khoá] | None."""

    def __init__(self, app, ds: list, khoa_ds: list | None = None):
        super().__init__(app.winfo_toplevel())
        m = gd.MAU
        self.kq = None
        self.title(TIEU_DE)
        self.transient(app.winfo_toplevel())
        self.resizable(False, False)
        self.configure(background=m["nen"])
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        o = tk.Frame(self, background=m["nen"], padx=22, pady=18)
        o.pack(fill="both", expand=True)
        tk.Label(o, text="Học màu Lightroom cho máy ảnh", background=m["nen"],
                 foreground=m["chu"], font=gd.phong(13, "dam2")).pack(anchor="w")
        tk.Label(o, text=("Lightroom dựng thử khoảng 20 ảnh của buổi với vài chục thông số khác "
                          "nhau, rồi trả lại đúng thông số cũ. App học cách Lightroom ra màu da "
                          "trên đúng máy + profile đó — dùng cho “Chế độ nhanh một lượt”."),
                 background=m["nen"], foreground=m["mo"], font=gd.CHU, justify="left",
                 wraplength=500).pack(anchor="w", pady=(4, 12))
        self.bien: dict = {}
        #  máy gợi ý (tổng kết Xử lý ảnh) không khớp khoá đọc từ catalog -> chọn sẵn như thường
        if khoa_ds and not set(khoa_ds) & {k for k, _n, _t in ds}:
            khoa_ds = None
        for k, n, tt in ds:
            h = tk.Frame(o, background=m["nen"])
            h.pack(fill="x", pady=3)
            du = int(n) >= TOI_THIEU
            chon = (k in khoa_ds) if khoa_ds else tt in ("chua_hoc", "chua_dat")
            v = tk.BooleanVar(value=bool(du and chon))
            ct = gd.CongTac(h, v, nen=m["nen"], command=self._dem)
            ct.pack(side="left", padx=(0, 10))
            if not du:
                ct.configure(state="disabled")
            else:
                self.bien[k] = v
            tk.Label(h, text=ten_khoa(k), background=m["nen"],
                     foreground=m["chu"] if du else m["mo"], font=gd.CHU_DAM).pack(side="left")
            ghi = (f"{gd.so_vn(n)} ảnh · {TRANG_THAI.get(tt, tt)}" if du else
                   f"{gd.so_vn(n)} ảnh — cần ít nhất {TOI_THIEU} ảnh có mặt")
            tk.Label(h, text=ghi, background=m["nen"],
                     foreground=m["xong"] if tt in ("dat", "goi") and du else m["mo"],
                     font=gd.CHU_NHO).pack(side="right", padx=(16, 0))
        gd.TheBao(o, muc="canh", chu=(
            "Trong lúc học: để Lightroom mở, đừng sửa ảnh của buổi này. History của các ảnh "
            "được dựng thử có thêm vài bước; ảnh được trả lại đúng thông số cũ. App tạm khoá "
            "Xử lý ảnh / Áp / Xuất tới khi học xong (bấm Dừng bất cứ lúc nào).")).pack(
            fill="x", pady=(14, 0))
        self.lbl_so = tk.Label(o, text="", background=m["nen"], foreground=m["mo"],
                               font=gd.phong(9, "so"), anchor="w")
        self.lbl_so.pack(fill="x", pady=(10, 0))
        day = tk.Frame(o, background=m["nen"])
        day.pack(fill="x", pady=(14, 0))
        self.btn_hoc = gd.NutTron(day, "Bắt đầu học", kieu="chinh", nen=m["nen"],
                                  command=self._hoc)
        self.btn_hoc.pack(side="right")
        gd.NutTron(day, "Huỷ", kieu="phu", nen=m["nen"], command=self.destroy).pack(
            side="right", padx=(0, 8))
        self.bind("<Escape>", lambda _e: self.destroy())
        self._dem()
        try:
            self.update_idletasks()
            cha = app.winfo_toplevel()
            x = cha.winfo_rootx() + (cha.winfo_width() - self.winfo_width()) // 2
            y = cha.winfo_rooty() + (cha.winfo_height() - self.winfo_height()) // 3
            self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
            self.grab_set()
        except tk.TclError:
            pass

    def chon(self) -> list:
        return [k for k, v in self.bien.items() if v.get()]

    def _dem(self):
        n = len(self.chon())
        try:
            self.lbl_so.configure(text=(f"Học {n} máy · khoảng {n * PHUT_MOI_MAY[0]}–"
                                        f"{n * PHUT_MOI_MAY[1]} phút" if n else
                                        "Chưa chọn máy nào."))
            self.btn_hoc.configure(state="normal" if n else "disabled")
        except tk.TclError:
            pass

    def _hoc(self):
        if self.chon():
            self.kq = self.chon()
            self.destroy()


class HocMauMixin:
    """Gắn vào App (autotone_gui)."""

    # ------------------------------------------------------------ trạng thái
    def _hm_dang(self) -> bool:
        hm = getattr(self, "_hm", None)
        return bool(hm) and not hm.get("xong")

    def _hm_chan(self) -> bool:
        """True = đang học màu, đã báo — gọi ở đầu mọi việc GHI vào Lightroom."""
        if not self._hm_dang():
            return False
        self.status("Đang học màu Lightroom — chờ học xong (hoặc bấm Dừng trong cửa sổ học) "
                    "rồi làm việc này.", gd.MAU["canh"])
        hop = self._hm.get("hop")
        if hop is not None:
            hop.hien()
        return True

    # ------------------------------------------------------------ bắt đầu
    def hoc_mau_lr(self, khoa_ds: list | None = None):
        """⋯ › Học màu Lightroom cho máy ảnh này… (khoa_ds: máy chọn sẵn — từ tổng kết
        Xử lý ảnh)."""
        if self._khoa_chan():
            return
        if self._hm_dang():
            self._hm["hop"].hien()
            return
        root = self.folder()
        cha = self.winfo_toplevel()
        if not root:
            messagebox.showinfo(TIEU_DE, "Chọn thư mục buổi chụp trước.", parent=cha)
            return
        if self.source_value() != "catalog":
            messagebox.showinfo(TIEU_DE, "Học màu Lightroom cần nguồn ảnh là Catalog Lightroom "
                                "(Thiết lập › Nguồn) — Lightroom phải đang mở buổi này.", parent=cha)
            return
        if self._hm_ban():
            return
        self.status("Đang kiểm plugin Lightroom + máy ảnh của buổi…")
        kq: dict = {}

        def nen():
            try:
                import hoc_mau_lr as H
                loi, items = H.kiem_san_sang(root)
                kq["loi"] = loi
                if not loi:
                    kq["ds"] = H.cac_khoa_cho(root, items)
            except Exception as ex:                          # noqa: BLE001
                kq["loi"] = f"Không chuẩn bị được: {ex}"
            kq["xong"] = True

        threading.Thread(target=nen, daemon=True, name="hoc_mau_kiem").start()
        self._hm_cho_kiem(kq, root, khoa_ds)

    def _hm_ban(self) -> bool:
        if (self.busy or self._xl_dang() or getattr(self, "_dang_cho_lr", False)
                or getattr(self, "_xuat_dang_soi", False)):
            self.status("App đang bận (xử lý / áp / xuất ảnh) — chờ xong rồi học màu Lightroom.",
                        gd.MAU["canh"])
            return True
        return False

    def _hm_cho_kiem(self, kq: dict, root: Path, khoa_ds):
        if not kq.get("xong"):
            self.after(200, lambda: self._hm_cho_kiem(kq, root, khoa_ds))
            return
        cha = self.winfo_toplevel()
        self.status("")
        if kq.get("loi"):
            messagebox.showinfo(TIEU_DE, kq["loi"], parent=cha)
            return
        if self.folder() != root:
            return                                  # đổi buổi trong lúc kiểm
        ds = kq.get("ds") or []
        if not ds:
            messagebox.showinfo(TIEU_DE, "Buổi này không có ảnh dùng để học (cần ảnh RAW có mặt, "
                                "không 1★, không chỉnh cục bộ).", parent=cha)
            return
        hop = HopChonMay(self, ds, khoa_ds)
        hop.wait_window()
        if not hop.kq or self._hm_ban() or self._hm_dang():
            return
        self._hm_bat_dau(root, hop.kq)

    def _hm_bat_dau(self, root: Path, khoa_ds: list):
        from xu_ly_anh_ui import HopXuLy
        import autotone as at
        hm = self._hm = {"xong": False, "dung": False, "thoat": False, "buoc": [], "td": None,
                         "dong": "", "kq": None, "khoa": list(khoa_ds), "root": root}
        buoc = (("chuan_bi", "Đọc thông số Lightroom"),) + tuple((k, ten_khoa(k)) for k in khoa_ds)
        hop = hm["hop"] = HopXuLy(self, False, self._hm_dung, buoc=buoc, tieu_de=TIEU_DE,
                                  dang="Đang học màu Lightroom…")
        hop.dat_buoi(f"{root.name} · {len(khoa_ds)} máy · đừng sửa ảnh trong Lightroom lúc này")
        #  đóng app lúc đang học: hỏi, rồi xin plugin dừng + chờ trả ảnh mới thoát
        try:
            self.winfo_toplevel().protocol("WM_DELETE_WINDOW", self._hm_dong_app)
        except tk.TclError:
            pass

        def chay():
            import hoc_mau_lr as H
            try:
                hm["kq"] = H.chay(
                    root, at.LR_JOB_DIR, khoa_ds=list(khoa_ds),
                    bao=lambda s: hm.__setitem__("dong", str(s).strip()),
                    tien=lambda x, t, b, c: hm.__setitem__("td", (int(x), int(t), str(b), str(c))),
                    dung=lambda: bool(hm["dung"]),
                    buoc=lambda ma, tt, ct: hm["buoc"].append((ma, tt, ct)))
            except Exception as ex:                          # noqa: BLE001
                hm["kq"] = {"ma": 2, "ket": [], "bao_cao": "", "loi": str(ex)}
            hm["het"] = True

        threading.Thread(target=chay, daemon=True, name="hoc_mau").start()
        self._hm_soi()

    # ------------------------------------------------------------ theo dõi
    def _hm_soi(self):
        hm = getattr(self, "_hm", None)
        if not hm or hm.get("xong"):
            return
        hop = hm["hop"]
        while hm["buoc"]:
            ma, tt, ct = hm["buoc"].pop(0)
            hm["dang"] = ma if tt == "dang" else hm.get("dang")
            hop.buoc(ma, tt, ct)
        td = hm.get("td")
        if hm["dung"]:
            hop.tien_do(0, 0, "Đang dừng — chờ Lightroom trả lại ảnh về thông số cũ…")
        elif td is not None:
            x, t, b, c = td
            hop.tien_do(x, t, f"Lightroom dựng {gd.so_vn(x)} / {gd.so_vn(t)}"
                              + (f" · {b}" if b else "") + c)
            if td[:2] != hm.get("td_bao"):          # thanh dưới: còn thấy khi bấm Chạy ngầm
                hm["td_bao"] = td[:2]
                self.status(f"Đang học màu Lightroom… · Lightroom dựng {gd.so_vn(x)} / "
                            f"{gd.so_vn(t)}" + c, gd.MAU["canh"])
        elif hm.get("dong"):
            hop.tien_do(0, 0, hm["dong"][:90])
        if hm.get("het"):
            self._hm_xong()
            return
        self.after(500, self._hm_soi)

    def _hm_dung(self):
        hm = getattr(self, "_hm", None)
        if not hm or hm.get("xong") or hm["dung"]:
            return
        hm["dung"] = True
        self.status("Đang dừng học màu — chờ Lightroom trả lại ảnh…", gd.MAU["canh"])
        try:
            hm["hop"].btn_dung.configure(state="disabled")
        except (tk.TclError, AttributeError):
            pass

    def _hm_dong_app(self):
        hm = getattr(self, "_hm", None)
        cha = self.winfo_toplevel()
        if not self._hm_dang():
            cha.destroy()
            return
        if not messagebox.askyesno(TIEU_DE, "Đang học màu Lightroom. Dừng học, chờ Lightroom trả "
                                   "lại ảnh về thông số cũ rồi thoát app?", parent=cha):
            return
        hm["thoat"] = True
        self._hm_dung()
        hm["hop"].hien()

    def _hm_xong(self):
        hm = self._hm
        hm["xong"] = True
        try:
            self.winfo_toplevel().protocol("WM_DELETE_WINDOW", "")
        except tk.TclError:
            pass
        try:
            import mau_mot_luot as ml
            ml.quen_mo_hinh()                       # mô hình mới có hiệu lực ngay lượt sau
        except ImportError:
            pass
        kq = hm.get("kq") or {}
        ket = kq.get("ket") or []
        dat = [k for k, v in ket if v == "ĐẠT"]
        dong = []
        for k, v in ket:
            dong.append(f"· {ten_khoa(k)}: {v}")
        if kq.get("loi"):
            dong.append(kq["loi"])
        if dat:
            bat = bool((self.read_cfg() or {}).get("mau_mot_luot"))
            dong.append(f"✓ {len(dat)} máy đã có mô hình màu Lightroom (lưu trong thư mục dữ liệu "
                        "của app).")
            if not bat:
                dong.append("Bật Thiết lập › Tone › “Chế độ nhanh một lượt (thử nghiệm)” để dùng.")
        if any(v == "CHƯA ĐẠT / không chạy hết" for _k, v in ket):
            dong.append("Máy CHƯA ĐẠT vẫn dùng đường thường — thử học lại trên một buổi khác "
                        "(nhiều ảnh có mặt, ánh sáng đa dạng hơn).")
        if hm["dung"]:
            dong.append("Đã dừng — ảnh đã được trả lại thông số cũ (kiểm vài ảnh trong Lightroom "
                        "nếu muốn chắc).")
        if kq.get("bao_cao"):
            dong.append(f"Báo cáo: {kq['bao_cao']}")
        tieu_de = ("Đã dừng học màu" if hm["dung"] else
                   "Học màu xong" if dat and len(dat) == len(ket) else
                   "Học màu chưa đạt hết" if ket else "Chưa học được")
        loi = not dat and not hm["dung"]
        hm["hop"].ket_thuc(tieu_de, dong, loi=loi)
        self.status(f"{tieu_de}: " + "; ".join(f"{ten_khoa(k)} {v}" for k, v in ket)[:160],
                    gd.MAU["xong"] if dat else gd.MAU["canh"])
        if hm.get("thoat"):
            try:
                self.winfo_toplevel().destroy()
            except tk.TclError:
                pass
