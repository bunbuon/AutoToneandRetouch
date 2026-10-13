# -*- coding: utf-8 -*-
"""tin_dung_ui.py — Giao diện cho credit + một key một máy một lúc (13/10).

Gắn vào App (autotone_gui) như XuLyAnhMixin. Phần "số thật" nằm ở tin_dung.py
và máy chủ; ở đây chỉ:
    - luồng nhịp phiên (tin_dung.NhipPhien) báo về hàng đợi self.q
    - hộp "Key đang dùng trên máy khác" / "Máy này đã bị đẩy ra"
    - trừ credit trong luồng đo (gọi từ start_analyze -> work())
    - hộp "Hết credit" (phân tích phần còn đủ credit)
    - nhãn credit cạnh hạn bản quyền, bảng "Credit & thiết bị…"
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox

import giao_dien as gd
import tin_dung as td


def _gio_phut(iso) -> str:
    """"14:05" (giờ máy này) từ thời điểm ISO máy chủ trả; hỏng thì ""."""
    try:
        from datetime import datetime
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone().strftime("%H:%M")
    except (TypeError, ValueError):
        return ""


def _lan_cuoi(giay) -> str:
    """Khoảng từ lần cuối máy kia hỏi máy chủ, đọc được: "3 phút trước"..."""
    if not isinstance(giay, (int, float)) or giay < 0:
        return ""
    g = int(giay)
    if g < 60:
        return "vừa xong"
    if g < 3600:
        return f"{g // 60} phút trước"
    if g < 86400:
        return f"{g // 3600} giờ trước"
    return f"{g // 86400} ngày trước"


class TinDungMixin:
    """Credit + phiên một máy — gắn vào App."""

    # ------------------------------------------------------------ khởi động
    def _td_khoi_dong(self):
        """Mở app: vào phiên ở luồng nền, rồi hỏi máy chủ 5 s (đang chạy việc) / 30 s."""
        if getattr(self, "_td_nhip", None) is not None:
            return
        self._td_nhip = td.NhipPhien(lambda kq: self.q.put(("phien", kq)),
                                     dang_ban=self._td_dang_ban).bat_dau()

    def _td_dung(self):
        """Đóng app: chỉ dừng nhịp. KHÔNG nhả phiên — user 13/10: "máy A đang đăng
        nhập thì dù có tắt máy cũng là đang đăng nhập"."""
        n = getattr(self, "_td_nhip", None)
        if n is not None:
            n.dung()

    def _td_dang_ban(self) -> bool:
        """App có việc đang chạy không. GỌI TỪ LUỒNG NỀN (NhipPhien): chỉ đọc thuộc
        tính Python, không gọi Tk."""
        if getattr(self, "busy", False) or getattr(self, "_dang_cho_lr", False):
            return True
        xl = getattr(self, "_xl", None)
        if xl and not xl.get("xong"):
            return True
        rw = getattr(self, "_retouch_win", None)
        if rw is not None:
            w = getattr(rw, "worker", None)
            if w is not None and w.is_alive():
                return True
            x = getattr(rw, "_xuat", None)
            if x and x.get("trang_thai") not in ("xong", "dung", "loi"):
                return True
        return False

    def _td_dung_viec(self) -> list:
        """Máy này vừa bị đẩy ra: dừng NGAY mọi việc đang chạy. -> tên các việc đã dừng.

        #[[ User 13/10: "Khi may B bam Van truy cap la may A da phai out ra khoi
        #   tien trinh dang chay roi." Phan tich: co dung (anh dang do xong la
        #   thoi). Job gui Lightroom ma Lightroom CHUA nhan: huy. Retouch / luot
        #   xuat: xin dung roi tat han engine ngay (Dung thuong cho anh dang lam
        #   xong + 20 s moi tat). Tram retouch tu tu choi vi trang thai da ghi
        #   "bi_day_ra" (tin_dung.phien_ok doc file, khong goi mang). ]]
        """
        da = []
        try:
            if getattr(self, "_xl_dang", lambda: False)():
                self._xl_dung()
                da.append("xu_ly")
            if getattr(self, "busy", False):
                self.do_cancel()
                da.append("phan_tich")
            if getattr(self, "_dang_cho_lr", False):
                self.huy_gui()
                da.append("gui_lr")
        except Exception:                                    # noqa: BLE001
            pass
        rw = getattr(self, "_retouch_win", None)
        if rw is not None:
            try:
                w = getattr(rw, "worker", None)
                x = getattr(rw, "_xuat", None)
                if (w is not None and w.is_alive()) or \
                        (x and x.get("trang_thai") not in ("xong", "dung", "loi")):
                    rw.stop()
                    m = getattr(rw, "_may_xem", None)
                    if m is not None and getattr(m, "dang_chay", False):
                        m.dong()
                    da.append("retouch")
                rw._nghi_may_xem()
            except Exception:                                # noqa: BLE001
                pass
        return da

    # ------------------------------------------------------------ tin từ luồng nền
    def _td_tin(self, kind: str, kq: dict):
        """_pump chuyển tin "phien" / "phien_chiem" tới đây (luồng chính)."""
        tt = (kq or {}).get("tt")
        if tt == "bi_day_ra":
            da = self._td_dung_viec()
            self._td_hop_phien({**kq, "da_dung": da})
        elif tt == "xung_dot":
            self._td_hop_phien(kq)
        elif tt == "dung":
            self._td_dong_hop()
            if kind == "phien_chiem":
                self.status("Đã chuyển key về máy này — máy kia đã bị đẩy ra.",
                            gd.MAU["xong"])
        elif kind == "phien_chiem":
            self._td_hop_loi((kq or {}).get("nhan")
                             or ("Không nối được máy chủ. Kiểm tra mạng rồi bấm lại."
                                 if tt == "mat_mang" else "Không chuyển được key về máy này."))
        self._td_ve_nhan()

    # ------------------------------------------------------------ nhãn credit
    def _td_ve_nhan(self):
        """Ghép số credit vào nhãn hạn bản quyền (thanh dưới)."""
        goc = getattr(self, "_han_goc", None)
        if not goc:
            return
        chu, mau = goc
        try:
            them = td.tom_tat()
        except Exception:                                    # noqa: BLE001
            them = ""
        try:
            self.lbl_han.configure(text=f"{chu}   ·   {them}" if them else chu, foreground=mau)
        except tk.TclError:
            pass

    # ------------------------------------------------------------ chốt việc nặng
    def _td_chan(self) -> bool:
        """True = máy này không giữ phiên (máy khác đang dùng / đã bị đẩy ra) — đã báo."""
        try:
            t = td.trang_thai()
        except Exception:                                    # noqa: BLE001
            return False
        if t.get("bat") and t.get("tt") in ("xung_dot", "bi_day_ra"):
            self._td_hop_phien({"tt": t["tt"], **(t.get("khac") or {})})
            return True
        return False

    # ------------------------------------------------------------ hộp phiên
    def _td_hop_phien(self, kq: dict):
        """Hộp chặn: key đang dùng trên máy khác / máy này vừa bị đẩy ra.

        #[[ Khuon cua hop kich hoat (_hien_khoa): Toplevel transient + grab + man
        #   toi che ca app. Dong hop = thoat app — user 13/10: "neu chon tiep tuc
        #   dang nhap se day thiet bi dang dung kia ra"; khong chon thi khong dung
        #   duoc o may nay. ]]
        """
        m = gd.MAU
        ten = (kq.get("ten_may") or "").strip() or "khác"
        #  mỗi ý MỘT dòng: bản tiếng Anh (ngon_ngu) dịch theo từng dòng
        if kq.get("tt") == "bi_day_ra":
            tieu_de = "Máy này đã bị đẩy ra"
            luc = _gio_phut(kq.get("luc"))
            dong = [f"Máy «{ten}» vừa đăng nhập key này lúc {luc}." if luc else
                    f"Máy «{ten}» vừa đăng nhập key này."]
            if kq.get("da_dung"):
                dong.append("Mọi việc đang chạy trên máy này đã dừng.")
        else:
            tieu_de = "Key đang dùng trên máy khác"
            dong = [f"Key này đang đăng nhập trên máy «{ten}»."]
            lan_cuoi = _lan_cuoi(kq.get("cach_giay"))
            if lan_cuoi:
                dong.append(f"Lần cuối máy đó hoạt động: {lan_cuoi}.")
        dong += ["Mỗi key chỉ đăng nhập trên MỘT máy — đóng app hay tắt máy vẫn là đang "
                 "đăng nhập.", "",
                 "Bấm “Vẫn truy cập” để dùng key trên máy này — máy kia bị đẩy ra ngay, mọi "
                 "việc đang chạy trên máy đó dừng lại. Credit dùng chung, ảnh đã trừ credit "
                 "ở máy kia không bị trừ lại."]
        ly_do = "\n".join(dong)
        hop = getattr(self, "_td_lop", None)
        if hop is not None and hop.winfo_exists():
            self._td_lbl_tieu_de.configure(text=tieu_de)
            self._td_lbl_ly_do.configure(text=ly_do)
            self._td_noi()
            return
        goc = self.winfo_toplevel()
        nen = tk.Frame(self, background=m["toi"])
        nen.grid(row=0, column=0, rowspan=8, columnspan=4, sticky="nsew")
        nen.lift()
        self._td_man = nen
        lop = tk.Toplevel(goc)
        lop.withdraw()
        lop.title("Key đang dùng trên máy khác")
        lop.configure(background=m["tam"])
        lop.resizable(False, False)
        lop.transient(goc)
        lop.protocol("WM_DELETE_WINDOW", self._td_thoat)
        self._td_lop = lop
        than = tk.Frame(lop, background=m["tam"], padx=34, pady=28,
                        highlightthickness=1, highlightbackground=m["canh"])
        than.pack(fill="both", expand=True)
        self._td_lbl_tieu_de = tk.Label(than, text=tieu_de, background=m["tam"],
                                        foreground=m["canh"], font=gd.phong(15, "dam2"))
        self._td_lbl_tieu_de.pack(anchor="w")
        self._td_lbl_ly_do = tk.Label(than, text=ly_do, background=m["tam"],
                                      foreground=m["chu"], font=gd.CHU, justify="left",
                                      wraplength=520)
        self._td_lbl_ly_do.pack(anchor="w", pady=(8, 12))
        self._td_lbl_loi = tk.Label(than, text="", background=m["tam"], foreground=m["loi"],
                                    font=gd.CHU, justify="left", wraplength=520)
        self._td_lbl_loi.pack(anchor="w")
        hang = tk.Frame(than, background=m["tam"])
        hang.pack(fill="x", pady=(16, 0))
        gd.NutTron(hang, "Thoát app", kieu="phu", nen=m["tam"],
                   command=self._td_thoat).pack(side="right")
        self.btn_td_chiem = gd.NutTron(hang, "Vẫn truy cập", kieu="chinh",
                                       nen=m["tam"], command=self._td_chiem)
        self.btn_td_chiem.pack(side="right", padx=(0, 8))
        try:
            lop.update_idletasks()
            gx, gy = goc.winfo_rootx(), goc.winfo_rooty()
            gw, gh = max(goc.winfo_width(), 400), max(goc.winfo_height(), 300)
            lop.geometry(f"+{max(gx + (gw - lop.winfo_reqwidth()) // 2, 0)}"
                         f"+{max(gy + max(0, (gh - lop.winfo_reqheight()) // 3), 0)}")
        except tk.TclError:
            pass
        lop.deiconify()
        self._td_noi()

    def _td_noi(self):
        lop = getattr(self, "_td_lop", None)
        try:
            if lop is not None and lop.winfo_exists():
                lop.lift()
                lop.focus_force()
                lop.grab_set()
        except tk.TclError:
            pass

    def _td_hop_loi(self, nhan: str):
        lbl = getattr(self, "_td_lbl_loi", None)
        try:
            if lbl is not None and lbl.winfo_exists():
                lbl.configure(text=nhan)
        except tk.TclError:
            pass
        b = getattr(self, "btn_td_chiem", None)
        if b is not None:
            try:
                b.configure(state="normal")
            except tk.TclError:
                pass

    def _td_chiem(self):
        """Bấm "Vẫn truy cập": chiếm phiên ở luồng nền."""
        b = getattr(self, "btn_td_chiem", None)
        if b is not None:
            try:
                b.configure(state="disabled")
            except tk.TclError:
                pass
        self._td_hop_loi("")

        def lam():
            try:
                kq = td.vao_phien(chiem=True)
            except Exception as e:                           # noqa: BLE001
                kq = {"tt": "loi", "nhan": str(e)}
            self.q.put(("phien_chiem", kq))
            n = getattr(self, "_td_nhip", None)
            if n is not None:
                n.ngay()
        threading.Thread(target=lam, daemon=True, name="credit_chiem").start()

    def _td_dong_hop(self):
        lop = getattr(self, "_td_lop", None)
        if lop is not None:
            try:
                lop.grab_release()
                lop.destroy()
            except tk.TclError:
                pass
            self._td_lop = None
        nen = getattr(self, "_td_man", None)
        if nen is not None:
            try:
                nen.destroy()
            except tk.TclError:
                pass
            self._td_man = None

    def _td_thoat(self):
        try:
            self.winfo_toplevel().destroy()
        except tk.TclError:
            pass

    # ------------------------------------------------------------ trừ khi phân tích
    def _td_tru_cho_do(self, pairs) -> dict:
        """GỌI Ở LUỒNG NỀN (work() của start_analyze), ngay trước at.analyze.

        -> kết quả tin_dung.tru() + "ma": mã từng ảnh (None = không đọc được). Ảnh
        không đọc được thì không trừ — đo cũng sẽ hỏng, báo như ảnh hỏng.
        """
        if not td.bat():
            return {"tt": "tat"}
        self.q.put(("status_credit", f"Đang kiểm credit cho {gd.so_vn(len(pairs))} ảnh…"))
        ma = td.ma_nhieu([str(pr[0]) for pr in pairs])
        ids, vi_tri = [], []
        for i, x in enumerate(ma):
            if x:
                ids.append(x)
                vi_tri.append(i)
        kq = td.tru(ids)
        kq["ma"] = ma
        if "cu_idx" in kq:
            kq["cu_pairs"] = [vi_tri[i] for i in kq["cu_idx"] if 0 <= i < len(vi_tri)]
            kq["moi_pairs"] = [vi_tri[i] for i in range(len(vi_tri))
                               if i not in set(kq["cu_idx"])]
        return kq

    def _td_bi_chan(self, kq: dict, pairs, lam_lai):
        """Luồng chính: trừ credit không qua -> báo, kết thúc lượt. lam_lai(paths)
        chạy lại start_analyze chỉ với các ảnh đó (hộp hết credit)."""
        self._set_busy(False)
        try:
            self.pb.configure(value=0)
        except tk.TclError:
            pass
        tt = kq.get("tt")
        cau = {
            "het_credit": "Hết credit — không phân tích ảnh mới.",
            "het_ung_truoc": (f"Mất mạng và đã ứng trước đủ {gd.so_vn(td.UNG_TRUOC_TOI_DA)} ảnh "
                              "— nối mạng để trừ bù rồi phân tích tiếp."),
            "bi_day_ra": "Máy này đã bị đẩy ra — key đang dùng ở máy khác.",
            "xung_dot": "Key đang dùng ở máy khác.",
        }.get(tt, kq.get("nhan") or "Không trừ được credit.")
        self.status(cau, gd.MAU["loi"])
        if getattr(self, "_xl_dang", lambda: False)():
            self._xl_hop().buoc("do", "loi", "credit")
            self._xl_ket_thuc("loi", cau)
        if tt in ("bi_day_ra", "xung_dot"):
            self._td_hop_phien(kq)
            return
        if tt == "het_credit":
            self._td_hop_het_credit(kq, pairs, lam_lai)
            return
        if tt == "het_ung_truoc":
            messagebox.showwarning("Cần nối mạng", cau)
            return
        messagebox.showerror("Credit", cau)

    def _td_hop_het_credit(self, kq: dict, pairs, lam_lai):
        """Còn ít credit hơn số ảnh mới: đề nghị phân tích phần vừa đủ."""
        con = int(kq.get("con_lai") or 0)
        can = int(kq.get("can") or 0)
        cu = list(kq.get("cu_pairs") or [])
        moi = list(kq.get("moi_pairs") or [])
        chon = cu + moi[:con]
        dong = [f"Cần {gd.so_vn(can)} credit cho ảnh mới, key này còn {gd.so_vn(con)}."]
        if cu:
            dong.append(f"{gd.so_vn(len(cu))} ảnh đã trừ credit từ trước — phân tích lại "
                        f"miễn phí.")
        dong.append("Liên hệ SAY Media để nạp thêm credit.")
        if chon:
            dong.append(f"\nPhân tích {gd.so_vn(len(chon))} ảnh vừa đủ credit"
                        + (f" ({gd.so_vn(min(con, len(moi)))} ảnh mới + "
                           f"{gd.so_vn(len(cu))} ảnh đã trừ)" if cu else "") + "?")
            if messagebox.askyesno("Hết credit", "\n".join(dong)):
                lam_lai({str(pairs[i][0]) for i in chon})
        else:
            messagebox.showwarning("Hết credit", "\n".join(dong))

    def _td_bao_tru(self, kq: dict, so_anh: int):
        """Luồng chính: trừ xong -> một câu ở dòng trạng thái + nhãn credit."""
        cau = td.cau_ket_qua(kq, so_anh)
        self._td_cau_luot = cau
        if cau:
            self.status(cau, gd.MAU["canh"] if kq.get("tt") == "ung_truoc" else gd.MAU["chu"])
            xl = getattr(self, "_xl", None)
            if xl:
                xl["credit_cau"] = cau          # hộp Xử lý ảnh in ở tổng kết
        self._td_ve_nhan()

    # ------------------------------------------------------------ bảng Credit & thiết bị
    def xem_credit(self):
        """⋯ → Credit & thiết bị…: hỏi máy chủ ở luồng nền rồi hiện bảng."""
        if not td.key_hien():
            messagebox.showinfo("Credit & thiết bị", "Máy này chưa kích hoạt bản quyền.")
            return
        self.status("Đang hỏi máy chủ số credit…")

        def lam():
            try:
                kq = td.lay_tom_tat()
            except Exception as e:                           # noqa: BLE001
                kq = {"ok": False, "nhan": str(e)}
            self.q.put(("credit_bang", kq))
        threading.Thread(target=lam, daemon=True, name="credit_xem").start()

    def _td_bang(self, kq: dict):
        dong = []
        cr = kq.get("credit") or {}
        if not kq.get("ok"):
            dong.append((kq.get("nhan") or "Không hỏi được máy chủ.")
                        + (" Số dưới là lần cập nhật gần nhất." if cr else ""))
        if cr:
            dong.append(f"Credit: còn {gd.so_vn(cr.get('con_lai', 0))} / "
                        f"{gd.so_vn(cr.get('tong', 0))}  (đã dùng {gd.so_vn(cr.get('da_dung', 0))})")
        try:
            ung = td.SoCai().so_ung()
        except Exception:                                    # noqa: BLE001
            ung = 0
        if ung:
            dong.append(f"Ứng trước lúc mất mạng: {gd.so_vn(ung)} ảnh, chờ trừ bù.")
        dd = kq.get("dang_dung")
        if dd:
            ma_minh = ""
            try:
                import khoa
                ma_minh = khoa.ma_may()
            except Exception:                                # noqa: BLE001
                pass
            la_minh = dd.get("may") == ma_minh
            dong.append(f"Máy đang dùng key: {dd.get('ten_may') or dd.get('may')}"
                        + (" (máy này)" if la_minh else ""))
        dm = kq.get("dem_may") or []
        if dm:
            dong.append("\nẢnh đã phân tích theo máy (trừ credit / tổng lượt phân tích):")
            for x in dm:
                dong.append(f"  • {x.get('ten_may') or x.get('may')}: "
                            f"{gd.so_vn(x.get('so_tru', 0))} / {gd.so_vn(x.get('so_phan_tich', 0))}")
        self.status("")
        self._td_ve_nhan()
        messagebox.showinfo("Credit & thiết bị", "\n".join(dong) or "Chưa có số liệu.")
