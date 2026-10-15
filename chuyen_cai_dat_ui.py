"""Menu ⋯ › Xuất / Nhập / Khôi phục cài đặt (15/10) — xem chuyen_cai_dat.py."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import giao_dien as gd

TIEU_DE = "Chuyển cài đặt"


class ChuyenCaiDatMixin:
    """Gắn vào App (autotone_gui)."""

    def _ccd_ban(self) -> bool:
        dang_hoc = getattr(self, "_hm_dang", None)
        if (self.busy or self._xl_dang() or (callable(dang_hoc) and dang_hoc())
                or getattr(self, "_xuat_dang_soi", False)):
            self.status("App đang bận — chờ xong việc đang chạy rồi nhập / khôi phục cài đặt.",
                        gd.MAU["canh"])
            return True
        return False

    def _ccd_hoi_mo_lai(self, cau: str):
        from retouch_chung import hoi_nut
        kq = hoi_nut(self.winfo_toplevel(), TIEU_DE, cau + "\n\nMở lại app để dùng cài đặt mới.",
                     [("lai", "Khởi động lại ngay", "chinh"), ("sau", "Để sau")])
        if kq == "lai":
            self._khoi_dong_lai()

    def xuat_cai_dat(self):
        import chuyen_cai_dat as cc
        cha = self.winfo_toplevel()
        ds = cc.ds_se_xuat()
        if not ds:
            messagebox.showinfo(TIEU_DE, "Máy này chưa có cài đặt nào để mang đi.", parent=cha)
            return
        f = filedialog.asksaveasfilename(
            parent=cha, title="Lưu gói cài đặt", defaultextension=".zip",
            initialfile=f"CaiDat_ToneRetouch_{datetime.now():%Y%m%d}{cc.DUOI}",
            filetypes=[("Gói cài đặt Tone&Retouch", "*.zip")])
        if not f:
            return
        try:
            kq = cc.xuat(Path(f))
        except OSError as ex:
            messagebox.showerror(TIEU_DE, f"Không ghi được gói: {ex}", parent=cha)
            return
        messagebox.showinfo(TIEU_DE, (
            f"Đã lưu gói cài đặt ({gd.so_vn(round(kq['byte'] / 1024))} KB):\n{kq['duong']}\n\n"
            f"Gồm: {cc.tom_tat(kq['tep'])}.\n\nKhông gồm bản quyền (key) — máy mới kích hoạt "
            "key riêng. Trên máy mới: ⋯ › Nhập cài đặt từ máy khác…"), parent=cha)

    def nhap_cai_dat(self):
        import chuyen_cai_dat as cc
        cha = self.winfo_toplevel()
        if self._ccd_ban():
            return
        f = filedialog.askopenfilename(parent=cha, title="Chọn gói cài đặt",
                                       filetypes=[("Gói cài đặt Tone&Retouch", "*.zip")])
        if not f:
            return
        try:
            g = cc.doc_goi(Path(f))
        except cc.LoiGoi as ex:
            messagebox.showerror(TIEU_DE, f"Không nhập được gói: {ex}.", parent=cha)
            return
        mf = g["manifest"]
        if not messagebox.askyesno(TIEU_DE, (
                f"Gói từ app {mf.get('app') or '?'} · {str(mf.get('ngay') or '')[:16].replace('T', ' ')}"
                f" · {mf.get('he_dieu_hanh') or ''}\nGồm: {cc.tom_tat(sorted(g['tep']))}.\n\n"
                "Mẫu màu da / preset trùng tên lấy theo gói; mô hình màu Lightroom đã đạt trên "
                "máy này được giữ. Cài đặt hiện tại được sao lưu trước — trả lại được ở ⋯ › "
                "Khôi phục cài đặt trước khi nhập…. Bản quyền (key) không bị đụng.\n\nNhập ngay?"),
                parent=cha):
            return
        try:
            kq = cc.nhap(Path(f))
        except (cc.LoiGoi, OSError) as ex:
            messagebox.showerror(TIEU_DE, f"Không nhập được gói: {ex}.", parent=cha)
            return
        self.status(f"Đã nhập cài đặt: {cc.tom_tat(kq['doi'])}.", gd.MAU["xong"])
        self._ccd_hoi_mo_lai(f"Đã nhập: {cc.tom_tat(kq['doi'])}.")

    def khoi_phuc_cai_dat(self):
        import chuyen_cai_dat as cc
        cha = self.winfo_toplevel()
        if self._ccd_ban():
            return
        ds = cc.ds_sao_luu()
        if not ds:
            messagebox.showinfo(TIEU_DE, "Chưa có bản sao lưu nào — máy này chưa nhập cài đặt "
                                "lần nào.", parent=cha)
            return
        sl = ds[0]
        luc = sl.stem[:15]
        try:
            luc = datetime.strptime(sl.stem[:15], "%Y%m%d_%H%M%S").strftime("%d/%m/%Y %H:%M")
        except ValueError:
            pass
        if not messagebox.askyesno(TIEU_DE, f"Trả cài đặt về như trước lần nhập lúc {luc}?",
                                   parent=cha):
            return
        try:
            kq = cc.khoi_phuc(sl)
        except (cc.LoiGoi, OSError) as ex:
            messagebox.showerror(TIEU_DE, f"Không khôi phục được: {ex}.", parent=cha)
            return
        self.status("Đã khôi phục cài đặt trước lần nhập.", gd.MAU["xong"])
        self._ccd_hoi_mo_lai(f"Đã khôi phục {len(kq['tra']) + len(kq['xoa'])} file cài đặt.")
