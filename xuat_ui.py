#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xuat_ui.py — Nút XUẤT: hộp thoại cài đặt + đo tài nguyên máy (9/10).

User 9/10: "Chuyển đổi nâng cấp tính năng xuất ảnh duyệt lên thành tự động
xuất ảnh từ Lightroom, có thêm các option: 1 chất lượng (tối đa 100 như
Lightroom), 2 đường dẫn thư mục, 3 khi trùng tên tệp (retouch có thay thế ảnh
gốc hay không), 4 bộ nhớ cache, 5 xuất ảnh đâu retouch đó luôn không. Thêm nút
Xuất, bấm hiện dialog. Máy vừa xuất vừa retouch nên cần kiểm tra môi trường và
tài nguyên, có cảnh báo nếu chọn vừa xuất vừa retouch."
Đã chốt: cảnh báo + TỰ ĐỔI sang "retouch sau khi xuất xong" khi máy yếu (người
dùng vẫn ép chạy song song được).

GỒM
    doc_cai_dat / ghi_cai_dat   <dữ liệu app>/xuat.json — nhớ mọi lựa chọn
    tai_nguyen_may              RAM / VRAM / GPU / CPU / đĩa trống (đo thật)
    danh_gia_song_song          đủ sức vừa xuất vừa retouch không, vì sao
    XuatDialog                  hộp thoại; .ket_qua = dict hoặc None (Huỷ)

Luồng thật (bắt đầu lượt xuất, theo dõi, retouch) nằm ở autotone_gui.App
(do_xuat_hop / bat_dau_xuat) và retouch_may.MayMixin (bat_dau_theo_xuat).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import duong_dan as dd
import giao_dien as gd

TEN_TEP = "xuat.json"
MAC_DINH = {
    "chat": 80,                 # chất lượng JPEG 1..100 (Lightroom 0..1)
    "va_cham": "overwrite",     # Lightroom gặp trùng tên: overwrite / skip / rename
    "bo_sao1": True,            # không xuất ảnh 1 sao
    "retouch_ra": "rieng",      # rieng = <xuất>_retouch · ghi_de = đè lên ảnh xuất
    "cache_mb": 2048,           # cache xem trước (cache_xem)
    "tu_retouch": True,         # retouch ngay trong lúc xuất
    "preset": "",               # preset retouch dùng cho lượt này ("" = mức đang đặt)
    "ep_song_song": False,      # máy yếu vẫn ép chạy song song
}
#[[ NGUONG MAY DU SUC VUA XUAT VUA RETOUCH. Lightroom export cỡ gốc ăn hết CPU
#   và vài GB RAM; retouch cần card (mô hình ~2–3 GB VRAM) + 2–4 GB RAM. Đo trên
#   máy 32 GB / 3060 Ti 8 GB (9/10): còn 10 GB RAM trống khi app + LR đang mở.
#   Dưới ngưỡng thì không cấm, chỉ TỰ ĐỔI sang chạy tuần tự + nói lý do. ]]
NGUONG = {"ram_gb": 6.0, "vram_gb": 3.0, "dia_gb": 5.0}


# ================================================================ cài đặt

def _tep() -> Path:
    return dd.du_lieu(TEN_TEP)


def doc_cai_dat() -> dict:
    d = dict(MAC_DINH)
    try:
        v = json.loads(_tep().read_text(encoding="utf-8"))
        if isinstance(v, dict):
            d.update({k: v[k] for k in MAC_DINH if k in v})
    except (OSError, ValueError):
        pass
    try:
        d["chat"] = int(min(100, max(1, int(d.get("chat") or 80))))
    except (TypeError, ValueError):
        d["chat"] = 80
    if d.get("va_cham") not in ("overwrite", "skip", "rename"):
        d["va_cham"] = "overwrite"
    if d.get("retouch_ra") not in ("rieng", "ghi_de"):
        d["retouch_ra"] = "rieng"
    try:
        d["cache_mb"] = int(max(64, int(d.get("cache_mb") or 2048)))
    except (TypeError, ValueError):
        d["cache_mb"] = 2048
    return d


def ghi_cai_dat(d: dict) -> None:
    cu = doc_cai_dat()
    cu.update({k: v for k, v in (d or {}).items() if k in MAC_DINH})
    f = _tep()
    tmp = f.with_suffix(".part")
    tmp.write_text(json.dumps(cu, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, f)


def thu_muc_retouch_cua(thu_muc_xuat: str) -> str:
    """Thư mục ảnh retouch mặc định: <xuất>_retouch, cạnh thư mục xuất."""
    t = str(thu_muc_xuat or "").strip().strip('"').rstrip("\\/")
    return os.path.normpath(t + "_retouch") if t else ""


# ================================================================ tài nguyên

def _ram_gb() -> tuple[float, float]:
    """(trống, tổng) GB. psutil có trong gói (saytool cần); không có thì ctypes."""
    try:
        import psutil
        m = psutil.virtual_memory()
        return m.available / 1e9, m.total / 1e9
    except Exception:                                        # noqa: BLE001
        pass
    try:
        import autotone as at
        trong = at.free_ram_mb() / 1024.0
        return trong, 0.0
    except Exception:                                        # noqa: BLE001
        return 0.0, 0.0


def _vram_nvidia(timeout: float = 4.0) -> tuple[float, float, str]:
    """(trống, tổng) GB và tên card qua nvidia-smi; (0, 0, "") khi không có."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return 0.0, 0.0, ""
    kw = {}
    if sys.platform == "win32":
        kw["creationflags"] = 0x08000000           # CREATE_NO_WINDOW
    try:
        r = subprocess.run([exe, "--query-gpu=memory.free,memory.total,name",
                            "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=timeout, **kw)
        dong = (r.stdout or "").strip().splitlines()
        if not dong:
            return 0.0, 0.0, ""
        phan = [x.strip() for x in dong[0].split(",")]
        return float(phan[0]) / 1024.0, float(phan[1]) / 1024.0, ",".join(phan[2:]).strip()
    except (OSError, ValueError, subprocess.SubprocessError, IndexError):
        return 0.0, 0.0, ""


def _dia_gb(thu_muc: str) -> float:
    p = Path(str(thu_muc or "").strip().strip('"') or ".")
    while not p.exists() and p.parent != p:
        p = p.parent
    try:
        return shutil.disk_usage(p).free / 1e9
    except OSError:
        return 0.0


def tai_nguyen_may(thu_muc_xuat: str = "") -> dict:
    """Đo máy NGAY LÚC GỌI (RAM / VRAM thay đổi theo phút)."""
    ram_trong, ram_tong = _ram_gb()
    vram_trong, vram_tong, card = _vram_nvidia()
    return {"ram_trong_gb": ram_trong, "ram_tong_gb": ram_tong,
            "vram_trong_gb": vram_trong, "vram_tong_gb": vram_tong, "card": card,
            "cpu": int(os.cpu_count() or 0),
            "dia_trong_gb": _dia_gb(thu_muc_xuat) if thu_muc_xuat else 0.0}


def danh_gia_song_song(tn: dict, nguong: dict | None = None) -> tuple[bool, list]:
    """Máy có đủ sức VỪA xuất VỪA retouch không. -> (đủ, [lý do không đủ])."""
    ng = dict(NGUONG, **(nguong or {}))
    ly_do = []
    if not tn.get("card"):
        ly_do.append("không thấy card NVIDIA — retouch bằng CPU sẽ giành CPU với "
                     "Lightroom, cả hai cùng chậm")
    elif float(tn.get("vram_trong_gb") or 0) < ng["vram_gb"]:
        ly_do.append(f"VRAM trống {float(tn.get('vram_trong_gb') or 0):.1f} GB "
                     f"(cần ≥ {ng['vram_gb']:.0f} GB cho mô hình retouch)")
    if float(tn.get("ram_trong_gb") or 0) < ng["ram_gb"]:
        ly_do.append(f"RAM trống {float(tn.get('ram_trong_gb') or 0):.1f} GB "
                     f"(cần ≥ {ng['ram_gb']:.0f} GB: Lightroom xuất + retouch)")
    if tn.get("dia_trong_gb") is not None and float(tn.get("dia_trong_gb") or 0) < ng["dia_gb"] \
            and tn.get("dia_trong_gb", 0.0) > 0.0:
        ly_do.append(f"ổ đích chỉ còn {float(tn['dia_trong_gb']):.1f} GB trống")
    return (not ly_do), ly_do


def mo_ta_tai_nguyen(tn: dict) -> str:
    phan = [f"RAM trống {tn.get('ram_trong_gb', 0):.1f}/{tn.get('ram_tong_gb', 0):.0f} GB"]
    if tn.get("card"):
        phan.append(f"{tn['card']}: VRAM trống {tn.get('vram_trong_gb', 0):.1f}/"
                    f"{tn.get('vram_tong_gb', 0):.0f} GB")
    else:
        phan.append("không thấy card NVIDIA")
    phan.append(f"{tn.get('cpu', 0)} luồng CPU")
    if tn.get("dia_trong_gb"):
        phan.append(f"ổ đích trống {tn['dia_trong_gb']:.0f} GB")
    return " · ".join(phan)


# ================================================================ hộp thoại

class XuatDialog(tk.Toplevel):
    """Hộp thoại Xuất. Sau wait_window(): .ket_qua là dict (Bắt đầu) hoặc None.

    ket_qua: chat (1..100) · thu_muc · va_cham · bo_sao1 · retouch_ra ·
             thu_muc_retouch · cache_mb · tu_retouch · song_song (tu_retouch VÀ
             (máy đủ sức HOẶC ép)) · preset · tai_nguyen (bản đo lúc bấm).
    """

    def __init__(self, cha, buoi: str = "", thu_muc_goi_y: str = "",
                 thong_so_lr: dict | None = None, luc_lr=None,
                 ds_preset: list | None = None, muc_dang: dict | None = None):
        super().__init__(cha)
        self.title("Xuất ảnh từ Lightroom")
        self.transient(cha)
        self.resizable(False, False)
        self.ket_qua = None
        self._ds_preset = list(ds_preset or [])
        self._muc_dang = dict(muc_dang or {})
        cd = doc_cai_dat()
        st = dict(thong_so_lr or {})
        try:
            chat_lr = int(round(float(st.get("LR_jpeg_quality", cd["chat"] / 100.0)) * 100))
        except (TypeError, ValueError):
            chat_lr = cd["chat"]
        self.v_chat = tk.StringVar(value=str(cd["chat"]))
        self.v_thu_muc = tk.StringVar(value=str(thu_muc_goi_y or ""))
        self.v_va_cham = tk.StringVar(value=cd["va_cham"])
        self.v_bo_sao1 = tk.BooleanVar(value=bool(cd["bo_sao1"]))
        self.v_retouch_ra = tk.StringVar(value=cd["retouch_ra"])
        self.v_cache_gb = tk.StringVar(value=f"{cd['cache_mb'] / 1024.0:.1f}".rstrip("0").rstrip("."))
        self.v_tu_retouch = tk.BooleanVar(value=bool(cd["tu_retouch"]))
        self.v_preset = tk.StringVar(value=cd.get("preset") or "")
        self.v_ep = tk.BooleanVar(value=bool(cd["ep_song_song"]))
        self._tn: dict = {}
        self._du_suc = True

        m = gd.MAU
        try:
            self.configure(background=m["nen"])
        except tk.TclError:
            pass
        frm = ttk.Frame(self, padding=14)
        frm.pack(fill="both", expand=True)
        WRAP = 540

        def tieu_de(chu, pady=(14, 4)):
            ttk.Label(frm, text=chu, font=gd.CHU_TIEU_DE).pack(anchor="w", pady=pady)

        def mo(chu):
            ttk.Label(frm, text=chu, style="Mo.TLabel", wraplength=WRAP,
                      justify="left").pack(anchor="w")

        ttk.Label(frm, justify="left", wraplength=WRAP, text=(
            f"Buổi: {buoi}" if buoi else "Xuất ảnh của buổi đang mở")).pack(anchor="w")
        mo("Một thao tác: Lightroom xuất ảnh cỡ gốc → app retouch (ngay trong lúc "
           "xuất, hoặc sau khi xuất xong). Kích thước, không gian màu, metadata, "
           "quy tắc đặt tên vẫn theo thông số Export của Lightroom.")

        # ---- 1. chất lượng
        tieu_de("1 · Chất lượng JPEG")
        self.tt_chat = gd.ThanhTruot(frm, self.v_chat, 1, 100, 1, nhan="Chất lượng",
                                     mo="1–100 như hộp thoại Export của Lightroom. "
                                        "Ảnh giao khách thường 80–92; 100 nặng gấp "
                                        "đôi mà mắt không thấy khác.",
                                     mac_dinh=str(chat_lr), dai=WRAP - 60)
        self.tt_chat.pack(fill="x")
        khi = luc_lr.strftime("%d/%m %H:%M") if luc_lr else "không rõ lúc nào"
        dinh_dang = str(st.get("LR_format") or "JPEG")
        if st:
            mo(f"Lightroom đang dùng {chat_lr} ({dinh_dang}; đọc lúc {khi}). Các ô khác "
               f"giữ nguyên theo Lightroom.")
        else:
            mo("Chưa đọc được thông số Export của Lightroom — app sẽ KHÔNG xuất "
               "(không tự bịa thông số cho ảnh giao khách).")

        # ---- 2. thư mục
        tieu_de("2 · Thư mục xuất")
        o = ttk.Frame(frm)
        o.pack(fill="x")
        nut = gd.NutTron(o, "", kieu="phu", font=gd.CHU, icon="thu_muc", command=self._chon_thu_muc)
        nut.goi_y = gd.GoiY(nut, "Chọn thư mục ảnh sẽ xuất ra…")
        nut.pack(side="right", padx=(6, 0))
        ttk.Entry(o, textvariable=self.v_thu_muc).pack(side="left", fill="x", expand=True)
        o2 = ttk.Frame(frm)
        o2.pack(fill="x", pady=(6, 0))
        ttk.Label(o2, text="Lightroom gặp file trùng tên:").pack(side="left")
        gd.PhanDoan(o2, self.v_va_cham, [("overwrite", "Ghi đè"), ("skip", "Bỏ qua"),
                                         ("rename", "Đổi tên")]).pack(side="left", padx=(8, 0))
        o3 = ttk.Frame(frm)
        o3.pack(fill="x", pady=(6, 0))
        gd.CongTac(o3, self.v_bo_sao1).pack(side="right")
        ttk.Label(o3, text="Bỏ ảnh 1 sao (ảnh đã loại khi lọc)").pack(side="left")

        # ---- 3. ảnh retouch
        tieu_de("3 · Ảnh retouch ghi ở đâu")
        gd.PhanDoan(frm, self.v_retouch_ra,
                    [("rieng", "Thư mục riêng"), ("ghi_de", "Ghi đè lên ảnh Lightroom xuất ra")],
                    command=self._lam_moi_ra).pack(anchor="w")
        self.lbl_ra = ttk.Label(frm, text="", style="Mo.TLabel", wraplength=WRAP, justify="left")
        self.lbl_ra.pack(anchor="w", pady=(4, 0))

        # ---- 4. cache
        tieu_de("4 · Bộ nhớ cache xem trước")
        self.tt_cache = gd.ThanhTruot(frm, self.v_cache_gb, 0.5, 20, 0.5, nhan="Dung lượng (GB)",
                                      mo="Ảnh xem trước retouch đã tính được lưu lại để "
                                         "mở lại thư mục / đang chạy mẻ vẫn xem được "
                                         "ngay. Vượt dung lượng thì tự xoá tấm lâu không "
                                         "xem nhất.", dai=WRAP - 60)
        self.tt_cache.pack(fill="x")
        o4 = ttk.Frame(frm)
        o4.pack(fill="x", pady=(4, 0))
        self.lbl_cache = ttk.Label(o4, text="", style="Mo.TLabel")
        self.lbl_cache.pack(side="left")
        gd.NutTron(o4, "Xoá cache", kieu="phu", font=gd.CHU, command=self._xoa_cache).pack(side="right")

        # ---- 5. retouch ngay
        tieu_de("5 · Xuất ảnh đâu retouch đó luôn")
        o5 = ttk.Frame(frm)
        o5.pack(fill="x")
        gd.CongTac(o5, self.v_tu_retouch, command=self._doi_tu_retouch).pack(side="right")
        ttk.Label(o5, text="Retouch ngay trong lúc Lightroom đang xuất (song song)").pack(side="left")
        o6 = ttk.Frame(frm)
        o6.pack(fill="x", pady=(6, 0))
        ttk.Label(o6, text="Preset retouch").pack(side="left")
        self.cb_preset = ttk.Combobox(o6, textvariable=self.v_preset, state="readonly", width=34,
                                      values=["(mức đang đặt trong Retouch)"] + self._ds_preset)
        if not self.v_preset.get() or self.v_preset.get() not in self._ds_preset:
            self.cb_preset.current(0)
        self.cb_preset.pack(side="left", padx=(8, 0))
        self.lbl_preset = ttk.Label(frm, text="", style="Mo.TLabel", wraplength=WRAP, justify="left")
        self.lbl_preset.pack(anchor="w", pady=(2, 0))
        self.cb_preset.bind("<<ComboboxSelected>>", lambda _e: self._lam_moi_preset())
        self.the_tn = gd.TheBao(frm, muc="canh", chu="")
        self.the_tn.pack(fill="x", pady=(8, 0))
        o7 = ttk.Frame(frm)
        gd.CongTac(o7, self.v_ep).pack(side="right")
        ttk.Label(o7, text="Vẫn chạy song song dù máy không đủ sức (tự chịu chậm / treo)").pack(side="left")
        self.o_ep = o7

        # ---- nút
        nut_ = ttk.Frame(frm)
        nut_.pack(fill="x", pady=(14, 0))
        self.btn_bat_dau = gd.NutTron(nut_, "Bắt đầu xuất", kieu="chinh", command=self._bat_dau)
        self.btn_bat_dau.pack(side="right")
        gd.NutTron(nut_, "Huỷ", kieu="phu", command=self._huy).pack(side="right", padx=(0, 8))
        if not st:
            self.btn_bat_dau.configure(state="disabled")

        self.v_thu_muc.trace_add("write", lambda *_: self._lam_moi_ra())
        self._lam_moi_ra()
        self._lam_moi_cache()
        self._lam_moi_preset()
        self.protocol("WM_DELETE_WINDOW", self._huy)
        self.after(50, self._do_tai_nguyen)
        try:
            self.update_idletasks()
            x = cha.winfo_rootx() + max(0, (cha.winfo_width() - self.winfo_reqwidth()) // 2)
            y = cha.winfo_rooty() + max(0, (cha.winfo_height() - self.winfo_reqheight()) // 3)
            self.geometry(f"+{x}+{y}")
        except tk.TclError:
            pass
        self.grab_set()

    # ------------------------------------------------------------ cập nhật
    def _chon_thu_muc(self):
        d = filedialog.askdirectory(title="Thư mục ảnh sẽ xuất ra",
                                    initialdir=self.v_thu_muc.get() or None, parent=self)
        if d:
            self.v_thu_muc.set(os.path.normpath(d))

    def _lam_moi_ra(self):
        tm = self.v_thu_muc.get().strip().strip('"')
        if self.v_retouch_ra.get() == "ghi_de":
            self.lbl_ra.configure(
                text="Ảnh retouch THAY THẾ ảnh Lightroom vừa xuất (không lùi lại được — "
                     "muốn giữ bản chưa retouch thì chọn thư mục riêng).")
        else:
            self.lbl_ra.configure(text=f"Ảnh retouch ghi vào: {thu_muc_retouch_cua(tm) or '(chọn thư mục xuất trước)'}")

    def _lam_moi_cache(self):
        try:
            import cache_xem
            self.lbl_cache.configure(text="Đang dùng: " + cache_xem.mo_ta_dung_luong())
        except Exception:                                    # noqa: BLE001
            self.lbl_cache.configure(text="")

    def _xoa_cache(self):
        try:
            import cache_xem
            n = cache_xem.lay_chung().xoa_het()
            self.lbl_cache.configure(text=f"Đã xoá {n} tấm · " + cache_xem.mo_ta_dung_luong())
        except Exception as ex:                              # noqa: BLE001
            self.lbl_cache.configure(text=f"Không xoá được: {ex}")

    def _ten_preset(self) -> str:
        t = self.v_preset.get()
        return t if t in self._ds_preset else ""

    def _lam_moi_preset(self):
        t = self._ten_preset()
        if t:
            self.lbl_preset.configure(text=f"Mọi ảnh xuất ra retouch theo preset “{t}” "
                                           "(ảnh đã đặt mức riêng vẫn giữ mức riêng).")
        else:
            muc = {k: v for k, v in self._muc_dang.items() if v not in (None, "") and float(v) > 0}
            self.lbl_preset.configure(
                text="Dùng mức CHUNG đang đặt ở bảng Retouch" + (
                    f" ({len(muc)} tính năng đang bật)." if muc else
                    " — đang 0 hết: ảnh xuất ra sẽ chỉ được chép sang, không retouch gì."))

    def _doi_tu_retouch(self):
        self._hien_tn()

    def _do_tai_nguyen(self):
        """Đo máy ở luồng nền (nvidia-smi mất ~0,2 s) rồi hiện. Biến Tk chỉ đọc
        ở luồng chính; luồng nền trả kết quả qua hàng đợi, luồng chính bơm."""
        import queue
        import threading
        tm = self.v_thu_muc.get()
        self._q_tn: queue.Queue = queue.Queue()

        def work():
            try:
                self._q_tn.put(tai_nguyen_may(tm))
            except Exception:                                # noqa: BLE001
                self._q_tn.put({})
        threading.Thread(target=work, daemon=True).start()
        self.the_tn.nhan.configure(text="Đang đo RAM / card đồ hoạ…")
        self.after(100, self._bom_tn)

    def _bom_tn(self):
        import queue
        try:
            tn = self._q_tn.get_nowait()
        except queue.Empty:
            try:
                self.after(100, self._bom_tn)
            except tk.TclError:
                pass
            return
        except AttributeError:
            return
        if tn:
            self._nhan_tn(tn)

    def _nhan_tn(self, tn: dict):
        self._tn = tn
        self._du_suc, self._ly_do = danh_gia_song_song(tn)
        self._hien_tn()

    def _hien_tn(self):
        tn = self._tn
        if not tn:
            return
        mo_ta = mo_ta_tai_nguyen(tn)
        if not self.v_tu_retouch.get():
            self.the_tn.nhan.configure(text=f"Retouch chạy SAU khi Lightroom xuất xong. Máy: {mo_ta}.")
            self._dat_muc_the("xong")
            self.o_ep.pack_forget()
            return
        if self._du_suc:
            self.the_tn.nhan.configure(
                text="Vừa xuất vừa retouch: Lightroom dùng hết CPU, retouch dùng card + "
                     f"CPU. Máy đủ sức ({mo_ta}). Retouch sẽ chậm hơn ~30–50% trong lúc "
                     "xuất; app chạy retouch 1 luồng, chế độ tiết kiệm, và tạm ngưng "
                     "nhận ảnh mới nếu RAM trống dưới 1,5 GB.")
            self._dat_muc_the("canh")
            self.o_ep.pack_forget()
        else:
            self.the_tn.nhan.configure(
                text="MÁY KHÔNG ĐỦ SỨC vừa xuất vừa retouch — " + "; ".join(self._ly_do)
                     + f". ({mo_ta}.) App sẽ retouch SAU khi Lightroom xuất xong, trừ khi "
                       "anh bật ô dưới.")
            self._dat_muc_the("loi")
            self.o_ep.pack(fill="x", pady=(6, 0), after=self.the_tn)

    def _dat_muc_the(self, muc: str):
        try:
            nen, vach, chu = gd._mau_dai(muc)                # noqa: SLF001
            nen = nen or gd.nen_cua(self)
            self.the_tn.configure(background=nen)
            self.the_tn.than.configure(background=nen)
            self.the_tn.nhan.configure(background=nen, foreground=chu)
            for w in self.the_tn.winfo_children():
                if isinstance(w, tk.Frame) and w is not self.the_tn.than:
                    w.configure(background=vach)
        except Exception:                                    # noqa: BLE001
            pass

    # ------------------------------------------------------------ kết thúc
    def _huy(self):
        self.ket_qua = None
        self.destroy()

    def _bat_dau(self):
        tm = self.v_thu_muc.get().strip().strip('"')
        if not tm:
            messagebox.showinfo("Chưa có thư mục xuất",
                                "Chọn thư mục ảnh sẽ xuất ra (mục 2).", parent=self)
            return
        tm = os.path.normpath(tm)
        try:
            chat = int(min(100, max(1, int(float(self.v_chat.get())))))
        except (TypeError, ValueError):
            chat = 80
        try:
            cache_mb = int(max(64, round(float(self.v_cache_gb.get()) * 1024)))
        except (TypeError, ValueError):
            cache_mb = 2048
        ghi_de = self.v_retouch_ra.get() == "ghi_de"
        if ghi_de and not messagebox.askyesno(
                "Ghi đè lên ảnh Lightroom xuất ra?",
                "Ảnh retouch sẽ THAY THẾ ảnh Lightroom vừa xuất trong\n" + tm
                + "\n\nKhông lùi lại được. Tiếp tục?", parent=self):
            return
        tu = bool(self.v_tu_retouch.get())
        song_song = tu and (self._du_suc or bool(self.v_ep.get()))
        if tu and not self._du_suc and bool(self.v_ep.get()) and not messagebox.askyesno(
                "Ép chạy song song?",
                "Máy không đủ sức: " + "; ".join(self._ly_do)
                + ".\n\nVẫn chạy song song? Có thể rất chậm hoặc hết bộ nhớ.", parent=self):
            return
        preset = self._ten_preset()
        ghi_cai_dat({"chat": chat, "va_cham": self.v_va_cham.get(),
                     "bo_sao1": bool(self.v_bo_sao1.get()),
                     "retouch_ra": self.v_retouch_ra.get(), "cache_mb": cache_mb,
                     "tu_retouch": tu, "preset": preset, "ep_song_song": bool(self.v_ep.get())})
        try:
            import cache_xem
            cache_xem.lay_chung().dat_gioi_han_mb(cache_mb)
        except Exception:                                    # noqa: BLE001
            pass
        self.ket_qua = {
            "chat": chat, "thu_muc": tm, "va_cham": self.v_va_cham.get(),
            "bo_sao1": bool(self.v_bo_sao1.get()), "retouch_ra": self.v_retouch_ra.get(),
            "thu_muc_retouch": "" if ghi_de else thu_muc_retouch_cua(tm),
            "cache_mb": cache_mb, "tu_retouch": tu, "song_song": song_song,
            "preset": preset, "tai_nguyen": dict(self._tn),
            "ly_do_tuan_tu": list(getattr(self, "_ly_do", [])) if (tu and not song_song) else [],
        }
        self.destroy()
