#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""retouch_may.py — MayMixin: máy xem trước, mẻ retouch và theo dõi thư mục của màn Retouch.

Tách từ man_retouch.RetouchWindow (7/10, giai đoạn 2b) — chỉ di chuyển, không
sửa thân hàm. Gồm: mở / tắt / nghỉ máy xem trước (xem_truoc.MayXem), xin mở
ảnh, hẹn tính, bơm kết quả; nút Chạy (start) + _chay_viec chạy mẻ NGAY TRONG
máy xem trước (engine thường trú) hoặc tiến trình con; Dừng; vòng tự retouch
ảnh mới; _pump / _xong. Trạng thái vẫn nằm trên RetouchWindow; mixin không có
__init__. hoi_nut tra tên ở module này — bài kiểm vá retouch_may.hoi_nut.
"""

from __future__ import annotations

import os
import queue
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import messagebox

sys.path.insert(0, str(Path(__file__).resolve().parent))
import giao_dien as gd
from retouch_chung import _RE_TIEN_DO, chon_anh_moi, hoi_nut





class MayMixin:
    """Máy xem trước + mẻ chạy + theo dõi thư mục (xem đầu tệp).
    """

    # ------------------------------------------------------------ xem trước
    #[[ XEM TRUOC NGAY TREN ANH LON — TU BAT KHI KEO (sang 4/10 — user: "bo nut
    #   xem truoc. Vi khi keo se load luon vao anh de thay dc luon").
    #
    #   Keo mot thanh la anh lon tinh lai theo muc cua ANH DANG XEM, nhu Evoto.
    #   May xem truoc (tien trinh con, nap mo hinh ~10 giay) duoc MO SAN khi vao
    #   mo-dun Retouch (_san_may_xem) — lan keo dau khoi cho nap. Tat: bam chip
    #   "Xem trước · …  ✕" duoi anh lon. Bam dup mot tam o dai anh van bat duoc.
    #
    #   Dang chay ca me thi KHONG bat: hai tien trinh cung nap mo hinh len mot
    #   card do hoa la duong ngan nhat toi "OOM on device 0". ]]
    def _mo_xem_truoc(self, anh: str | None = None, tu_dong: bool = False):
        """Bật xem trước: ẢNH LỚN tính lại theo mức của ảnh đang xem.

        tu_dong=True: bật vì người dùng KÉO THANH — không hộp thoại nào, chỉ
        nói ở chip dưới ảnh lớn; máy xem trước đã hỏng thì không tự thử lại
        (kéo thanh là hàng chục lần một giây). Bấm đúp một tấm ở dải ảnh là
        bật hẳn — thử lại cả khi đã hỏng."""
        goc = self._goc_hien()
        if not self.rt.hop_le(goc):
            self._dat_chip("loi", "Chưa xem trước được — chưa chọn đúng thư mục "
                                  "tool retouch")
            return
        if self.worker is not None and self.worker.is_alive():
            #[[ 9/10 (Xuat mot thao tac): dang chay me thi engine ban — nhung tam
            #   da tung xem truoc voi DUNG muc nay thi cache tren dia co
            #   (cache_xem) -> hien ngay, khong qua engine. ]]
            p = anh or self._anh_dang
            if anh and anh != self._anh_dang:
                self._anh_dang = anh
                self._ten_hien = Path(anh).name
                self._nap_muc_vao_bang(self._muc_hieu_luc(anh))
                if self.luoi.dang_chon != anh:
                    self.luoi.chon(anh)
            if p and self._hien_tu_cache(p, chip="đang chạy mẻ — xem trước lấy từ cache"):
                return
            self._dat_chip("chua", "Đang chạy retouch — xem trước tạm tắt tới khi "
                                   "chạy xong (ảnh đã xong thì bấm là thấy bản kết quả)")
            return
        if not tu_dong:
            self._xem_hong = ""
        elif self._xem_hong:
            self._dat_chip("loi", f"Xem trước đang lỗi: {self._xem_hong[:60]} — bấm "
                                  "đúp một tấm ở dải ảnh để thử lại")
            return
        if anh and anh != self._anh_dang:
            self._anh_dang = anh
            self._ten_hien = Path(anh).name
            self._nap_muc_vao_bang(self._muc_hieu_luc(anh))
        if anh and self.luoi.dang_chon != anh:
            self.luoi.chon(anh)
        self._cap_nhat_pham_vi()
        if not self._anh_dang:
            return
        if not self._dam_bao_may_xem():
            self._dat_chip("loi", "Không mở được xem trước: "
                                  + (self._xem_hong or "không rõ vì sao")[:70])
            return
        self._xem_bat = True
        #[[ 9/10: TU BAT theo tam da co muc (mo lai thu muc / sang tam khac) ma
        #   engine chua san sang hay chua mo tam nay -> co trong cache thi HIEN
        #   NGAY trong luc cho (~10 s nap mo hinh); engine mo xong van tinh lai
        #   nhu thuong (cung ket qua). Nguoi dung keo thanh thi khong qua day. ]]
        if getattr(self, "_xem_dung_cache", False):
            self._xem_dung_cache = False
            if not self._xem_san_sang or self._xem_fp != self._anh_dang \
                    or self._xem_goc_im is None:
                self._hien_tu_cache(self._anh_dang, chip="")
        self._xem_gui_mo(self._anh_dang)
        self._hen_bom_xem()

    # ------------------------------------------------------------ cache xem trước
    #[[ CACHE XEM TRUOC TREN DIA (9/10 — user: "tao bo nho Cache de luu cac Preview
    #   cua anh, khi xuat anh cung co the xem cac anh khac"). Moi ket qua engine
    #   tra ve duoc ghi xuong cache_xem (khoa = anh + mtime + muc + ban tool).
    #   Truoc khi hoi engine thi tra cache: trung la hien ngay (mo lai thu muc,
    #   hay dang chay me — engine ban). Xem cache_xem.py. ]]
    def _cache(self):
        try:
            import cache_xem
            return cache_xem.lay_chung()
        except Exception:                                    # noqa: BLE001
            return None

    def _ban_engine(self) -> str:
        return str(getattr(self, "_xem_ban", "") or self.cf.get("ban_engine") or "")

    def _khoa_cache(self, fp, muc: dict):
        try:
            import cache_xem
            return cache_xem.khoa(fp, muc, self._ban_engine())
        except Exception:                                    # noqa: BLE001
            return None

    def _cache_lay(self, k):
        c = self._cache()
        if c is None or not k:
            return None
        try:
            return c.lay(k)
        except Exception:                                    # noqa: BLE001
            return None

    def _cache_cat(self, k, im):
        c = self._cache()
        if c is None or not k or im is None:
            return
        try:
            c.cat(k, im)
        except Exception:                                    # noqa: BLE001
            pass

    def _anh_goc_nhanh(self, path):
        """Bản gốc 1400 px đọc thẳng từ đĩa (khi engine chưa mở tấm này) — để
        giữ chuột so bản gốc với bản xem trước lấy từ cache."""
        try:
            from PIL import Image
            with Image.open(path) as im:
                im.draft("RGB", (2800, 2800))
                im = im.convert("RGB")
                im.thumbnail((1400, 1400), Image.BILINEAR)
                return im
        except Exception:                                    # noqa: BLE001
            return None

    def _hien_xem_truoc(self, im, tu_cache: bool = False, chip: str = ""):
        """Đặt một ảnh xem trước lên ảnh lớn (từ engine hay từ cache)."""
        truoc = self._xem_goc_im if (self._xem_goc_im is not None
                                     and self._xem_fp == self._anh_dang) else None
        if truoc is None and tu_cache and self._anh_dang:
            truoc = self._anh_goc_nhanh(self._anh_dang)
        mat = self._xem_mat if self._xem_fp == self._anh_dang else []
        self.xem.dat_anh(im, truoc=truoc, mat=mat, giu_khung=True)
        self._xem_dang_hien = True
        self._anh_hien = self._anh_dang
        self._thanh_cu = None
        self._cap_nhat_thanh_xem()
        self._dat_chip_xem(chip or (self._nguon_muc() + (" · từ cache" if tu_cache else "")))

    def _hien_tu_cache(self, path, chip: str = "") -> bool:
        """Có bản xem trước trong cache cho (tấm, mức đang hiện) thì hiện. -> hit?"""
        if not path:
            return False
        try:
            muc = self._muc_xem() if path == self._anh_dang else \
                {k: round(float(v), 1) for k, v in self._muc_hieu_luc(path).items()}
        except Exception:                                    # noqa: BLE001
            return False
        if not any(float(v) > 0 for v in muc.values()):
            return False
        im = self._cache_lay(self._khoa_cache(path, muc))
        if im is None:
            return False
        if path != self._anh_dang:
            self._anh_dang = path
            self._ten_hien = Path(path).name
        self._hien_xem_truoc(im, tu_cache=True, chip=chip)
        return True

    def _tat_xem_truoc(self, dong_may: bool = False):
        """Tắt xem trước: ảnh lớn về bản trên đĩa, GIỮ chỗ đang soi. dong_may:
        tắt hẳn tiến trình con (nhường card đồ hoạ cho lượt chạy)."""
        self._xem_bat = False
        if self._hen_tinh is not None:
            try:
                self.after_cancel(self._hen_tinh)
            except tk.TclError:
                pass
            self._hen_tinh = None
        if dong_may:
            self._dong_may_xem()
        if self._anh_dang:
            if self._xem_dang_hien:
                self._hien_anh_dia(self._anh_dang, giu_khung=True)
            else:
                #[[ Anh lon van la ban tren dia (chua kip co ket qua xem
                #   truoc) — khoi nap lai, chi tra chip ve. ]]
                self._chip_dia(self._anh_kq_duong)

    def _dong_may_xem(self):
        m = self._may_xem
        self._may_xem = None
        self._xem_san_sang = False
        self._xem_fp = self._xem_cho_fp = self._xem_mo_dang = None
        self._xem_goc_im = None
        self._xem_dang_tinh = None
        self._xem_can_tinh = False
        self._xem_cuoi = None
        if m is not None:
            m.dong()

    def _nghi_may_xem(self):
        """Rời mô-đun Retouch: tắt máy xem trước — trả card đồ hoạ / bộ nhớ cho
        Lightroom. Quay lại thì _san_may_xem mở lại (ở nền)."""
        if self._xem_bat:
            self._tat_xem_truoc(dong_may=True)
        else:
            self._dong_may_xem()

    def _khi_huy(self, e=None):
        if e is not None and e.widget is not self:
            return
        for ten in ("_hen_xem", "_hen_tinh"):
            h = getattr(self, ten, None)
            if h is not None:
                try:
                    self.after_cancel(h)
                except tk.TclError:
                    pass
                setattr(self, ten, None)
        if self._hen_luu_ma is not None:
            try:
                self._luu_muc()
            except Exception:                                # noqa: BLE001
                pass
        self._dong_may_xem()

    def _dam_bao_may_xem(self) -> bool:
        """Có máy xem trước đang chạy (đúng tool đang chọn) chưa — chưa thì mở.
        False: không mở được (lý do ở _xem_hong) hoặc không được mở lúc này
        (chưa có tool, đang chạy cả mẻ)."""
        goc = self._goc_hien()
        if self._may_xem is not None and (not self._may_xem.song()
                                          or self._xem_goc_tool != goc):
            self._dong_may_xem()
        if self._may_xem is not None:
            return True
        if not self.rt.hop_le(goc) or (self.worker is not None and self.worker.is_alive()):
            return False
        try:
            import xem_truoc
        except Exception as ex:                              # noqa: BLE001
            self._xem_hong = f"{type(ex).__name__}: {ex}"
            return False
        may = xem_truoc.MayXem(self.rt, goc)
        loi = may.bat_dau(self.v_may.get() or "auto")
        if loi:
            self._xem_hong = loi
            self._append(f"! xem trước: {loi}")
            return False
        self._may_xem = may
        self._xem_goc_tool = goc
        self._xem_san_sang = False
        self._xem_fp = self._xem_cho_fp = self._xem_mo_dang = None
        self._xem_goc_im = None
        self._xem_dang_tinh = None
        self._xem_can_tinh = False
        self._xem_cuoi = None
        self._xem_loi_cuoi = ""
        self._append("… máy xem trước: đang nạp mô hình (lần đầu ~10 giây)")
        self._hen_bom_xem()
        return True

    def _san_may_xem(self):
        """Vào mô-đun Retouch / chạy xong: mở SẴN máy xem trước (ảnh lớn vẫn là
        bản trên đĩa) và mở ngầm tấm đang xem — lần kéo đầu khỏi chờ nạp."""
        try:
            if getattr(self.app, "khau_dang", "") != "retouch" or self._xem_hong:
                return
            #[[ Da co may (ke ca may vua chet ma _bom_xem chua kip doc tin
            #   "chet") thi KHONG mo may moi o day: mo de len la nuot mat tin
            #   chet, va vong "chet -> tu mo lai" khong ai chan. ]]
            if self._may_xem is None and not self._dam_bao_may_xem():
                return
            #[[ Tam dang xem DA CO thong so -> tinh xem truoc luon (5/10); chua
            #   co thi chi mo ngam nhu cu. ]]
            if self._anh_dang and not self._xem_bat \
                    and not self._tu_xem_neu_co_muc(self._anh_dang):
                self._xem_xin_mo(self._anh_dang)
        except Exception:                                    # noqa: BLE001
            traceback.print_exc()

    def _xem_xin_mo(self, path: str):
        """Xin tiến trình con mở `path`. MỘT lần mở mỗi lúc: đang mở dở tấm khác
        thì chỉ nhớ tấm mới, tấm kia xong mới gửi — lướt nhanh mười tấm không
        xếp hàng mười lần mở (tiến trình con làm tuần tự từng việc)."""
        self._xem_cho_fp = path
        m = self._may_xem
        if m is None or not self._xem_san_sang or self._xem_mo_dang is not None:
            return
        if path == self._xem_fp and self._xem_goc_im is not None:
            return
        if m.gui(viec="mo_anh", fp=path):
            self._xem_mo_dang = path

    def _xem_gui_mo(self, path: str, hien_dia: bool = False):
        """Đang xem trước mà tấm đổi (hoặc vừa bật): mở tấm đó ở tiến trình
        con rồi tính. Đã mở sẵn (mở ngầm lúc lướt) thì tính luôn.

        hien_dia: vừa bấm sang tấm KHÁC — hiện ngay bản trên đĩa trong lúc chờ,
        không để tên tấm mới nằm dưới ảnh của tấm cũ một hai giây."""
        if hien_dia:
            self._hien_anh_dia(path)
        self._xem_xin_mo(path)
        if self._xem_fp == path and self._xem_goc_im is not None \
                and self._xem_mo_dang is None:
            self._xem_tinh(ep=not self._xem_dang_hien)
        elif self._xem_san_sang and self._may_xem is not None:
            self._dat_chip_xem("đang mở ảnh…")
        else:
            self._dat_chip_xem("đang nạp mô hình…")

    def _nguon_muc(self) -> str:
        p = self._anh_dang
        return ("mức riêng của ảnh này" if p and self._khoa(p) in self._muc_anh
                else "theo mức chung")

    def _muc_xem(self) -> dict:
        """Mức gửi đi: mức chung + mức riêng theo nhóm (như lúc Chạy) — tool
        không nhận mức riêng thì chỉ mức chung (_xem_bo_nhom)."""
        d = self.muc_day_du()
        if self._xem_bo_nhom:
            d = {k: v for k, v in d.items() if ":" not in str(k)}
        return {k: round(float(v), 1) for k, v in d.items()}

    def _hen_tinh_xem(self):
        """Mức vừa đổi: tính lại SAU khi ngừng tay 0,2 s (đang tính thì chỉ
        tính thêm MỘT lần khi lần đó xong — xem _xem_tinh)."""
        if not self._xem_bat:
            return
        if self._hen_tinh is not None:
            try:
                self.after_cancel(self._hen_tinh)
            except tk.TclError:
                pass
        try:
            self._hen_tinh = self.after(200, self._xem_tinh)
        except tk.TclError:
            self._hen_tinh = None

    def _xem_tinh(self, ep: bool = False):
        self._hen_tinh = None
        m = self._may_xem
        if not self._xem_bat or m is None or not self._xem_fp \
                or self._xem_fp != self._anh_dang:
            return
        if self._xem_mo_dang is not None:
            #[[ Dang mo DO mot tam khac o tien trinh con: tinh bay gio la tinh
            #   tren tam do ("chua mo anh nay"). "da_mo" ve se tinh (ep=True). ]]
            return
        muc = self._muc_xem()
        if not ep and self._xem_cuoi == (self._xem_fp, muc):
            return
        if self._xem_dang_tinh is not None:
            #[[ Dang tinh -> chi danh dau, tinh MOT lan nua khi lan nay xong. ]]
            self._xem_can_tinh = True
            return
        if not any(float(v) > 0 for v in muc.values()):
            self._xem_cuoi = (self._xem_fp, muc)
            if self._xem_goc_im is not None:
                self.xem.dat_anh(self._xem_goc_im, truoc=None, mat=self._xem_mat,
                                 giu_khung=True)
                self._xem_dang_hien = True
                self._anh_hien = self._xem_fp
                self._thanh_cu = None
                self._cap_nhat_thanh_xem()
            self._dat_chip_xem("mọi mức đang ở 0")
            return
        #[[ Engine RANH thi LUON hoi engine (ket qua moi, dung tung diem anh) —
        #   cache chi duoc GHI THEM o day. Cache duoc TRA khi: engine ban (dang
        #   chay me — _mo_xem_truoc / _tu_xem_neu_co_muc), hoac tu bat theo tam
        #   da co muc ma engine chua san sang / chua mo tam do (_mo_xem_truoc:
        #   hien ngay trong luc cho, engine mo xong van tinh lai). ]]
        k = self._khoa_cache(self._xem_fp, muc)
        self._xem_ma += 1
        self._xem_dang_tinh = self._xem_ma
        self._xem_cuoi = (self._xem_fp, muc)
        self._xem_muc_gui = muc
        if k:
            self._xem_khoa_cua[self._xem_ma] = k
            #  không giữ khoá của các yêu cầu đã trôi (lướt nhanh hàng chục tấm)
            for ma_cu in [x for x in self._xem_khoa_cua if x < self._xem_ma - 20]:
                self._xem_khoa_cua.pop(ma_cu, None)
        m.gui(viec="tinh", ma=self._xem_ma, fp=self._xem_fp, muc=muc)
        self._xem_t0 = time.monotonic()
        self._dat_chip_xem("đang tính…")
        if getattr(self, "_hen_giay_xem", None) is not None:
            try:
                self.after_cancel(self._hen_giay_xem)   # mot bo dem moi luc
            except tk.TclError:
                pass
        self._dem_giay_xem()

    def _dem_giay_xem(self):
        """Đếm giây trên chip lúc đang tính xem trước.

        #[[ 5/10 — user: "keo thanh tren ban .exe khong thay thay doi". Ban cai
        #   chay torch CPU: moi lan keo 5-13 giay moi co anh (do that tren
        #   SAY00551: .exe 6-13 s, .bat / CUDA 0.3-2 s, KET QUA GIONG HET). Trong
        #   luc do anh lon dung yen voi dong "dang tinh…" nho -> tuong keo khong
        #   an. Dem giay de thay may DANG lam; may chay CPU ma CO card NVIDIA thi
        #   chi cho tai ban tang toc GPU. ]]
        """
        self._hen_giay_xem = None
        if self._xem_dang_tinh is None or not self._xem_bat:
            return
        n = int(time.monotonic() - getattr(self, "_xem_t0", time.monotonic()))
        chu = f"đang tính… {n} giây" if n >= 1 else "đang tính…"
        if n >= 3 and getattr(self, "_xem_may", "") == "cpu":
            if getattr(self, "_co_nvidia", None) is None:
                try:
                    import shutil as _sh
                    self._co_nvidia = bool(_sh.which("nvidia-smi"))
                except Exception:                            # noqa: BLE001
                    self._co_nvidia = False
            chu += (" (máy đang tính bằng CPU — menu ··· › Tải bản tăng tốc GPU "
                    "để nhanh hơn)" if self._co_nvidia else " (tính bằng CPU)")
        self._dat_chip_xem(chu)
        try:
            self._hen_giay_xem = self.after(1000, self._dem_giay_xem)
        except tk.TclError:
            self._hen_giay_xem = None

    def _hen_bom_xem(self):
        if self._hen_xem is None and self._may_xem is not None:
            try:
                self._hen_xem = self.after(80, self._bom_xem)
            except tk.TclError:
                self._hen_xem = None

    def _bom_xem(self):
        """Tin từ tiến trình con xem trước (luồng chính)."""
        self._hen_xem = None
        m = self._may_xem
        if m is None:
            return
        import xem_truoc
        for d in m.lay():
            t = d.get("loai")
            if t == "san_sang":
                self._xem_san_sang = True
                self._xem_may = str(d.get("may") or "")      # "cuda" / "cpu" / ...
                ban = str(d.get("ban") or "")
                if ban and ban != getattr(self, "_xem_ban", ""):
                    self._xem_ban = ban                      # khoá cache xem trước
                    try:
                        self.rt.ghi_cau_hinh({"ban_engine": ban})
                    except OSError:
                        pass
                #[[ Suc khoe engine (7/10 — giai doan 1): MOT dong trong nhat ky
                #   retouch (va retouch.log) moi lan engine mo, noi ro dang tinh
                #   bang gi — may (cuda/cpu/mps), bo do mat ORT (CUDA / DirectML /
                #   CoreML / CPU), ban saytool. Truoc day chay CPU hay do mat bang
                #   CPU deu im lang, chi thay "cham" / "khong thay mat". ]]
                self._append(f"[engine] máy={self._xem_may or '?'} · bộ dò mặt="
                             f"{d.get('ort') or '?'} · saytool {d.get('ban') or '?'}"
                             + ("" if d.get("ban") else
                                " (bản cũ: mẻ sẽ chạy bằng tiến trình riêng)"))
                if self._xem_cho_fp:
                    self._xem_xin_mo(self._xem_cho_fp)
                    if self._xem_bat:
                        self._dat_chip_xem("đang mở ảnh…")
            elif t == "da_mo":
                self._xem_mo_dang = None
                if d.get("fp") != self._xem_cho_fp:
                    #[[ Anh cu — da bam sang tam khac trong luc mo. Bo, mo tam
                    #   moi nhat (dung mot lan mo, xem _xem_xin_mo). ]]
                    self._xem_fp, self._xem_goc_im = None, None
                    if self._xem_cho_fp:
                        self._xem_xin_mo(self._xem_cho_fp)
                    continue
                self._xem_fp = d.get("fp")
                self._xem_goc_im = xem_truoc.giai_anh(d.get("goc", ""))
                self._xem_mat = d.get("mat") or []
                self._xem_so_mat = int(d.get("so_mat") or 0)
                self._xem_cuoi = None
                if self._xem_bat and self._xem_fp == self._anh_dang \
                        and self._xem_goc_im is not None:
                    #[[ Khong co mat van TINH: tu 0.9.5 co buoc chay tren co the
                    #   (khuyet diem co the, keo dai chan) — noi "keo thanh khong
                    #   doi gi" la sai. Chi noi ra la tool khong thay mat nao.
                    #   Trong luc tinh, anh lon GIU ban dang hien (ban tren dia) —
                    #   khong chop sang ban goc 1400 px roi moi ra ket qua. ]]
                    self._xem_tinh(ep=True)
            elif t == "ket_qua":
                if d.get("ma") == self._xem_dang_tinh:
                    self._xem_dang_tinh = None
                im = xem_truoc.giai_anh(d.get("anh", "")) if d.get("anh") else None
                #[[ 9/10: ket qua nao ve cung cat vao cache (ke ca tam da luot qua)
                #   — buoc bi bo qua thi khong cat: ban do khong phai ket qua that. ]]
                k_c = self._xem_khoa_cua.pop(d.get("ma"), None)
                if im is not None and k_c and not [x for x in (d.get("bo_qua") or []) if x]:
                    self._cache_cat(k_c, im)
                if self._xem_bat and im is not None and d.get("fp") == self._xem_fp \
                        and self._xem_fp == self._anh_dang:
                    self.xem.dat_anh(im, truoc=self._xem_goc_im, mat=self._xem_mat,
                                     giu_khung=True)
                    self._xem_dang_hien = True
                    self._anh_hien = self._xem_fp
                    self._thanh_cu = None
                    self._cap_nhat_thanh_xem()
                    #[[ BUOC BAT MA KHONG CHAY DUOC (5/10): truoc day tien trinh
                    #   xem truoc lang le bo qua — anh lon y nhu chua retouch ma
                    #   chip van bao "Xem truoc", user tuong keo thanh khong an.
                    #   Nay noi thang tren chip + ly do o Nhat ky (moi bo mot lan). ]]
                    bq = [x for x in (d.get("bo_qua") or []) if x]
                    canh = ""
                    if bq:
                        canh = " · KHÔNG chạy được: " + ", ".join(str(x[0]) for x in bq[:3]) \
                            + (" …" if len(bq) > 3 else "") + " (xem Nhật ký)"
                        khoa_bq = tuple(str(x[0]) for x in bq)
                        if khoa_bq != getattr(self, "_xem_bq_cuoi", None):
                            self._xem_bq_cuoi = khoa_bq
                            for x in bq:
                                self._append(f"! xem trước: bỏ qua “{x[0]}” — "
                                             f"{x[1] if len(x) > 1 else ''}")
                    else:
                        self._xem_bq_cuoi = None
                    self._dat_chip_xem(self._nguon_muc() + (
                        "" if self._xem_so_mat else
                        " · tool không thấy khuôn mặt nào") + canh)
                if self._xem_can_tinh:
                    self._xem_can_tinh = False
                    self._xem_tinh()
            elif t == "hong":
                if d.get("ma") is not None and d.get("ma") == self._xem_dang_tinh:
                    self._xem_dang_tinh = None
                    #[[ Ban saytool khong nhan muc rieng theo nhom (khoa
                    #   "nam:vet") -> tinh lai voi muc chung, va noi ra. ]]
                    gui = getattr(self, "_xem_muc_gui", {}) or {}
                    if "chua mo anh" in str(d.get("loi") or ""):
                        gui = {}      # ảnh ở tiến trình con đã đổi — không phải tool chê khoá nhóm
                    if not self._xem_bo_nhom and any(":" in str(k) for k in gui):
                        self._xem_bo_nhom = True
                        self._append("… xem trước: tool không nhận mức riêng theo "
                                     "nhóm — xem trước chỉ áp mức Chung")
                        self._xem_cuoi = None
                        self._xem_tinh(ep=True)
                        continue
                elif d.get("ma") is None:
                    if d.get("fp") is None:
                        #[[ Hong luc KHOI DONG (import saytool…): tien trinh con
                        #   thoat ngay sau dong nay — giu ly do de noi o "chet". ]]
                        self._xem_loi_cuoi = str(d.get("loi") or "")[:300]
                    else:
                        self._xem_mo_dang = None
                        if d.get("fp") != self._xem_cho_fp:
                            if self._xem_cho_fp:
                                self._xem_xin_mo(self._xem_cho_fp)
                            continue
                loi = str(d.get("loi") or "lỗi không rõ").splitlines()[0][:120]
                self._append(f"! xem trước: {loi}")
                if self._xem_bat:
                    self._dat_chip_xem(f"Xem trước lỗi: {loi[:60]}", loai="loi")
                if self._xem_can_tinh:
                    self._xem_can_tinh = False
                    self._xem_tinh()
            elif t == "chet":
                ly_do = (self._xem_loi_cuoi.splitlines() or [""])[0][:120]
                self._append("! tiến trình xem trước đã dừng"
                             + (f" — {ly_do}" if ly_do else ""))
                #[[ Danh dau HONG: keo thanh khong tu mo lai (tranh vong mo ->
                #   chet -> mo). Bam dup mot tam o dai anh la thu lai. ]]
                self._xem_hong = ly_do or "tiến trình xem trước đã dừng"
                bat = self._xem_bat
                self._may_xem = None
                self._xem_san_sang = False
                self._xem_dang_tinh = None
                self._xem_mo_dang = None
                self._xem_fp, self._xem_goc_im = None, None
                if bat:
                    self._tat_xem_truoc()
                    self._dat_chip("loi", "Xem trước đã dừng — bấm đúp một tấm ở dải "
                                          "ảnh để bật lại")
                return
        self._hen_bom_xem()

    def _nhip(self) -> str:
        """“· 4,9 s/ảnh · còn ~57 phút” — đo bằng SỐ FILE ĐÃ RA, không tin log.

        #[[ VI SAO TU DO CHU KHONG DOC DONG TIEN DO CUA TOOL.
        #
        #   saytool chi in tien do MOI 10 ANH. Voi 5 giay mot anh la gan mot
        #   phut moi co mot dong — nguoi dung nhin man hinh dung im, khong biet
        #   nhanh hay cham, va cau hoi dau tien luon la "bao lau nua thi xong".
        #
        #   Dem file trong thu muc ra thi biet lien tuc, va dung ke ca khi tool
        #   khong noi gi. Moc t0 lay tu luc bam Chay, va tru di so anh DA CO
        #   san tu luoc truoc — khong tru thi lan chay tiep tuc se ra toc do
        #   nhanh gia.
        #]]
        """
        t0 = getattr(self, "_t0", None)
        if not t0 or not (self.worker and self.worker.is_alive()):
            return ""
        giay = time.monotonic() - t0
        lam = self.pb.cget("value") - getattr(self, "_xong_dau", 0)
        try:
            lam = float(lam)
        except (TypeError, ValueError):
            return ""
        #  8/10: engine thường trú ra ảnh đầu sau ~1 s — đợi 5 s thì cả mẻ nhỏ
        #  xong mà dòng vẫn "đang khởi động"
        if lam < 1 or giay < 2:
            return "  ·  đang khởi động…"
        moi_anh = giay / lam
        con = max(0.0, float(self.pb.cget("maximum")) - self.pb.cget("value"))
        giay_con = con * moi_anh
        phut = giay_con / 60.0
        return (f"  ·  {moi_anh:.1f} s/ảnh  ·  còn ~"
                + (f"{giay_con:.0f} giây" if giay_con < 90
                   else f"{phut:.0f} phút" if phut < 90
                   else f"{phut / 60:.1f} giờ"))

    # ------------------------------------------------------------ chạy
    def _bi_khoa(self) -> bool:
        """Chốt bản quyền ngay đầu việc nặng (7/10).

        App._khoa_chan nói "mọi đường vào việc thật đều đi qua đây" — nhưng chỉ
        App.open_retouch gọi nó, còn hai đường khác vào màn này (thanh mô-đun,
        _chon_khau) và chính nút Chạy retouch / vòng tự retouch ảnh mới thì
        không: hết hạn mà lớp phủ chưa kịp hiện (soi mỗi phút) là vẫn chạy
        được mẻ mới. Bản không có App thật (bài kiểm dựng tay) thì không chặn."""
        chan = getattr(self.app, "_khoa_chan", None)
        return bool(chan is not None and chan())

    def start(self):
        if self._bi_khoa():
            return
        if not self._kiem():
            messagebox.showinfo("Chưa dùng được tool retouch",
                                self.lbl_goc.cget("text"), parent=self)
            return
        vao = Path(self.v_vao.get().strip().strip('"'))
        ra = Path(self.v_ra.get().strip().strip('"'))
        if not vao.is_dir():
            messagebox.showinfo("Thiếu thư mục vào", f"Không có:\n{vao}", parent=self)
            return
        ghi_de = bool(self.v_ghide.get())
        if not ghi_de:
            if not str(ra).strip():
                messagebox.showinfo("Thiếu thư mục ra",
                                    "Chọn nơi lưu ảnh đã retouch, hoặc tick "
                                    "“Ghi đè lên ảnh gốc”.", parent=self)
                return
            #[[ Ra TRUNG Vao la mat anh goc mot cach AM THAM. Nguoi dung muon
            #   ghi de thi co o tick rieng — o do co canh bao va hoi xac nhan.
            #]]
            try:
                if ra.resolve() == vao.resolve():
                    messagebox.showerror(
                        "Hai thư mục trùng nhau",
                        "Thư mục ra phải KHÁC thư mục vào.\n\n"
                        "Muốn retouch đè lên ảnh gốc thì tick "
                        "“Ghi đè lên ảnh gốc” — ở đó có cảnh báo rõ ràng.",
                        parent=self)
                    return
            except OSError:
                pass
        #[[ TU RETOUCH ANH MOI: chup danh sach anh CO SAN + muc cho anh moi NGAY
        #   LUC BAM — anh xuat hien sau moc nay (ke ca trong luot nay) moi la moi.
        #   Chi giao cho self._theo_doi luc THAT SU chay / vao theo doi (huy o
        #   hop hoi nao thi khong theo doi gi). ]]
        theo_doi = (self._chuan_bi_theo_doi(vao, ra, ghi_de)
                    if self.v_tu_moi.get() else None)
        tong_tm, _xong_tm = self._dem()
        if not tong_tm:
            if theo_doi:
                self._vao_theo_doi(theo_doi, "thư mục chưa có ảnh")
                return
            messagebox.showinfo("Không có ảnh", f"{vao}\nkhông có ảnh nào.",
                                parent=self)
            return
        #[[ CHI CHAY ANH DANG CHON (6/10 — user: "Khi bam Chay Retouch thi anh
        #   nao duoc Select thi se chay va xuat anh do"). Chon o dai anh (Ctrl+A
        #   = ca thu muc). Chon RIENG MOT PHAN la y muon xuat lai CHINH nhung tam
        #   do -> lam lai ca tam da co ket qua. Chon het thi giu nhu cu: bo qua tam
        #   da xong tru khi tick "Lam lai" — me hang nghin anh sap giua chung bam
        #   chay lai van di tiep tu cho dung. ]]
        tat_ca = [str(p) for p, _x in self._ds_luoi]
        luoi = getattr(self, "luoi", None)
        da_chon = {str(p) for p in (luoi.ds_chon() if luoi is not None else [])}
        ds_chay = [p for p in tat_ca if p in da_chon]
        if not ds_chay and theo_doi:
            self._vao_theo_doi(theo_doi, "chưa chọn ảnh nào để chạy trước")
            return
        if not ds_chay:
            messagebox.showinfo("Chưa chọn ảnh nào",
                                "Bấm chọn ảnh cần retouch ở dải ảnh (Ctrl+A để chọn "
                                "hết) rồi bấm Chạy retouch.", parent=self)
            return
        mot_phan = len(ds_chay) < len(tat_ca)
        xong_cua = {str(p): bool(x) for p, x in self._ds_luoi}
        tong = len(ds_chay)
        xong = sum(1 for p in ds_chay if xong_cua.get(p))
        lam_lai = bool(self.v_lamlai.get()) or mot_phan
        con = tong if (lam_lai or ghi_de) else tong - xong
        if not con and theo_doi:
            self._vao_theo_doi(theo_doi, "ảnh đã chọn đều có kết quả")
            return
        if not con:
            #[[ 7/10: cong tac "Lam lai ca anh da co ket qua" da bo cung nhom May &
            #   cach chay — nen HOI THANG thay vi bao "tick Lam lai". Chon het ma
            #   tam nao cung xong la y muon xuat lai ca loat. ]]
            if hoi_nut(self, "Đã có kết quả",
                       f"Cả {tong} ảnh đang chọn đều đã có kết quả.\n\n"
                       "Làm lại tất cả? Ảnh đã xuất sẽ được ghi đè bằng bản mới.",
                       [("lam_lai", "Làm lại tất cả", "chinh"),
                        ("huy", "Thôi", "phu")]) != "lam_lai":
                return
            lam_lai = True
            con = tong

        #[[ NHOM THEO MUC (sang 4/10 — muc rieng tung anh + Sync).
        #
        #   Moi anh mot bo muc HIEU LUC (muc rieng cua no, khong thi muc chung).
        #   saytool chi nhan MOT bo muc cho ca thu muc, nen anh cung muc gom mot
        #   luot: MOT nhom (khong ai dat rieng — truong hop thuong) thi chay y
        #   het truoc day, thang tren thu muc vao. Nhieu nhom thi moi nhom mot
        #   thu muc tam (lien ket cung) + mot luot `chay` cua CHINH saytool.
        #   Nhom muc 0 het (khong retouch) thi chep nguyen ban sang thu muc ra
        #   — thu muc giao khach du anh, va bo dem "da lam" dung. ]]
        de_quy = bool(self.v_dequy.get())
        muc_cua = {p: self._loc_muc(self._muc_hieu_luc(p)) for p in ds_chay}
        #[[ VUA MUC CHUNG VUA MUC RIENG GIOI TINH -> HOI (6/10). Xem
        #   rt.co_ca_chung_rieng. "Rieng": muc chung cua tinh nang chia nhom ve
        #   0 — chi nhom da dat rieng duoc retouch; "Chung": bo muc rieng, moi
        #   khuon mat theo muc chung. Chi doi muc CUA LUOT CHAY NAY, khong sua
        #   muc da luu. ]]
        nhom_duoc = self._ten_theo_nhom()
        ca_hai = [p for p in ds_chay if self.rt.co_ca_chung_rieng(muc_cua[p], nhom_duoc)]
        if ca_hai:
            ten = ", ".join(Path(p).name for p in ca_hai[:3]) + (" …" if len(ca_hai) > 3 else "")
            dung = hoi_nut(
                self, "Dùng mức Chung hay mức riêng giới tính?",
                f"{len(ca_hai)} ảnh ({ten}) đang bật CẢ mức Chung LẪN mức riêng "
                "theo giới tính / nhóm mặt.\n\n"
                "• Mức Chung: mọi khuôn mặt theo mức Chung, bỏ mức riêng.\n"
                "• Riêng giới tính: chỉ nhóm đã đặt riêng được retouch theo mức "
                "của nhóm đó — mức Chung về 0.\n\n"
                "Chỉ áp cho lượt chạy này, không đổi mức đã lưu.",
                [("chung", "Dùng mức Chung"), ("rieng", "Dùng riêng giới tính"),
                 (None, "Huỷ")])
            if dung is None:
                return
            for p in ca_hai:
                muc_cua[p] = self.rt.chon_chung_rieng(muc_cua[p], nhom_duoc, dung)
            self._append(f"… {len(ca_hai)} ảnh có cả mức Chung lẫn riêng giới tính: "
                         + ("dùng mức Chung" if dung == "chung"
                            else "dùng mức riêng giới tính (Chung về 0)"))
        nhom = self.rt.nhom_theo_muc(ds_chay, lambda p: muc_cua[p])
        #[[ any(muc.values()) da dung cho ca muc rieng, vi muc_day_du() gop
        #   ca hai vao mot tu dien phang. Chi doi loi chu: "ba thanh keo" la
        #   con so cua ban cu, gio la sau va con them nam nhom. ]]
        if (not nhom or all(self.rt.muc_trong(m) for m, _a in nhom)) and theo_doi:
            self._vao_theo_doi(theo_doi, "ảnh đã chọn đều ở mức 0")
            return
        if not nhom or all(self.rt.muc_trong(m) for m, _a in nhom):
            messagebox.showinfo(
                "Chưa bật tính năng nào",
                "Mọi thanh kéo đều ở 0 — kể cả mức riêng theo nhóm"
                + (" và mức riêng từng ảnh" if len(nhom) > 1 else "")
                + ". Không có gì để làm.", parent=self)
            return
        #[[ CHAY TREN THU MUC TAM khi: nhieu muc (moi muc mot luot), hoac chi
        #   chay MOT PHAN thu muc (anh dang chon). Ghi de + thu muc tam KHONG con
        #   bi chan (6/10 — user bi chan "Ghi de chi chay duoc MOT muc"): saytool
        #   ghi ra thu muc tam rieng, app tu thay anh goc — rt.dua_ket_qua_ra. ]]
        #[[ 8/10: GHI DE cung luon qua thu muc tam (user: "Retouch xong van bao
        #   0/13 anh"). Ghi de thang len thu muc vao thi KHONG dem duoc anh nao da
        #   xong (anh ra de len anh vao) — chi con dong tien do 10 anh mot lan cua
        #   tool, bi dat lai 0 sau moi luot -> luc xong bao 0/13, thanh tien do
        #   dung im. Qua thu muc tam: dem file ra cua luot tung anh mot, app thay
        #   anh goc (rt.dua_ket_qua_ra — duong da dung cho anh dang chon). ]]
        theo_tam = len(nhom) > 1 or mot_phan or ghi_de

        #[[ HOI XAC NHAN GHI DE — sau khi da dem duoc so anh.
        #
        #   saytool cung hoi, nhung bang input() tren dong lenh: tien trinh con
        #   cua app khong co ban phim nen cau hoi do se treo mai mai. Nen app
        #   phai hoi thay, va bao saytool khoi hoi (--dong-y-ghi-de).
        #
        #   Hoi SAU khi dem de noi duoc SO ANH va DUONG DAN that — saytool ghi
        #   chu ro ly do: "phai nhin thay so anh va duong dan TRUOC khi go dong
        #   y", vi hai lan retouch chong len nhau thi khong the biet tu noi
        #   dung anh la da lam roi hay chua.
        #]]
        if ghi_de and not messagebox.askokcancel(
                "Ghi đè lên ảnh gốc?",
                f"{tong} ảnh trong:\n    {vao}\n\n"
                "sẽ bị THAY THẾ bằng bản đã retouch. Ảnh gốc không còn bản "
                "sao, và KHÔNG lùi lại được.\n\n"
                "Chạy lại lần nữa sẽ retouch chồng lên kết quả lần này.\n\n"
                "Đồng ý ghi đè?", icon="warning", parent=self):
            return

        #[[ Viec tung nhom: chi nhung tam CON PHAI LAM (tool tu bo qua tam da
        #   co ket qua, nhung dung thu muc tam cho nhom da xong het la ton mot
        #   lan nap mo hinh vo ich). ]]
        viec = []
        for m, a in nhom:
            con_g = [p for p in a if lam_lai or ghi_de or not xong_cua.get(p)]
            if con_g:
                viec.append((m, con_g, self.rt.muc_trong(m)))
        if len(nhom) > 1:
            dong = []
            for m, a, la0 in viec:
                ten = ", ".join(Path(p).name for p in a[:3]) + (" …" if len(a) > 3 else "")
                dong.append(f"   • {len(a)} ảnh ({ten}): "
                            + ("mức 0 hết — chép nguyên bản sang thư mục ra, "
                               "không retouch" if la0 else self._mo_ta_muc(m)))
            n_chay = sum(1 for _m, _a, la0 in viec if not la0)
            if not messagebox.askokcancel(
                    "Chạy theo từng nhóm mức?",
                    "Các ảnh đang có mức KHÁC NHAU (mức riêng từng ảnh) — tool "
                    f"chạy {n_chay} lượt, mỗi lượt một mức:\n\n" + "\n".join(dong)
                    + "\n\nMỗi lượt nạp mô hình một lần (thêm ~10 giây). Chạy?",
                    parent=self):
                return

        #[[ Chan TRUOC khi chay, dung de no chet o anh dau — xem _hoi_chep().
        #   Hoi du mo hinh cho MOI nhom: muc lon nhat cua tung tinh nang. ]]
        if not self._hoi_chep(self.rt.gop_muc([m for m, _a, la0 in viec if not la0])):
            return

        tam_goc = None
        if theo_tam:
            try:
                tam_goc = self.rt.tao_thu_muc_tam(vao)
            except OSError as ex:
                messagebox.showerror("Không tạo được thư mục tạm",
                                     "Chạy ảnh đã chọn / theo nhóm mức cần một thư "
                                     f"mục tạm:\n{ex}", parent=self)
                return

        #[[ CHAN DUONG DAN CO DAU TIENG VIET — xem khong_ascii() ben retouch.py.
        #   TU 14/9: chi con chan khi ban saytool dang tro toi la ban CU (chua
        #   co saytool/duong_dan.py). Ban moi da doc/ghi duoc duong dan co dau,
        #   chan nua la chan oan — nguoi dung phai di doi ten thu muc vo co.
        #   Truyen goc vao de no nhin ban DANG DUNG ma quyet dinh, khong doan.
        #   Chay theo nhom thi xet ca thu muc tam (no co the nam o thu muc tam
        #   cua he thong — duong dan co ten nguoi dung co dau).
        #]]
        xau = self.rt.khong_ascii(vao, ra, *([tam_goc] if tam_goc else []),
                                  goc=self.v_goc.get().strip().strip('"'))
        if xau:
            self.rt.don_thu_muc_tam(tam_goc)
            messagebox.showerror(
                "Đường dẫn có dấu tiếng Việt",
                "Bản tool retouch đang chọn là bản CŨ — nó dùng OpenCV thẳng, "
                "mà OpenCV trên Windows không mở được file có dấu trong đường "
                "dẫn:\n\n"
                + "\n".join(f"   {x}" for x in xau)
                + "\n\nChạy tiếp thì cả mẻ trượt hết, và nó báo “check file "
                  "path/integrity” nghe như ảnh hỏng — dễ đi tìm sai chỗ.\n\n"
                  "Cách xử lý, chọn một trong hai:\n"
                  "   • Cập nhật tool retouch lên bản có saytool/duong_dan.py "
                  "(bản này đọc/ghi được đường dẫn có dấu)\n"
                  "   • Hoặc Export ra một thư mục tên không dấu, ví dụ "
                  "G:\\2905_export",
                parent=self)
            return
        #[[ "muc" trong retouch.json la MUC CHUNG (anh khong co muc rieng) —
        #   khong phai muc cua anh dang xem tren bang. Muc rieng tung anh ghi o
        #   file rieng cua thu muc vao (_luu_muc). ]]
        self._luu_muc()
        self.rt.ghi_cau_hinh({"vao": str(vao), "ra": str(ra),
                              "muc": self._muc_chung_day_du(),
                              "may": self.v_may.get(),
                              "luong": int(self.v_luong.get()),
                              "che_do": self.v_che_do.get(),
                              "ghi_de": bool(self.v_ghide.get())})
        #[[ Ghi hai thu muc vao TRANG THAI CUA BUOI, khong chi vao retouch.json.
        #   retouch.json giu lua chon GAN NHAT (dung chung moi buoi); bang trang
        #   thai can biet buoi 1308 export ra dau, buoi 0306 ra dau. Hai muc
        #   dich khac nhau nen giu ca hai cho.
        #]]
        self._t0 = time.monotonic()
        try:
            import trang_thai as tt
            goc = self.app.folder()
            if goc:
                tt.ghi(tt.ten_buoi(goc), thu_muc_export=str(vao),
                       thu_muc_retouch=str(ra))
        except Exception:                                    # noqa: BLE001
            pass

        self._dung_hen_quet()
        self._theo_doi = theo_doi
        if theo_doi:
            self._append("… bật “Tự retouch ảnh mới”: chạy xong sẽ theo dõi thư mục "
                         "Vào, ảnh mới dùng mức chung: " + self._mo_ta_muc(theo_doi["muc"]))
        self._chay_viec(
            vao=vao, ra=ra, ghi_de=ghi_de, lam_lai=lam_lai, de_quy=de_quy,
            viec=viec, tam_goc=tam_goc, muc_thang=nhom[0][0], xong_dau=xong,
            tieu_de=f"{con} ảnh cần làm"
                    + (f" (ảnh đã chọn, trên {len(tat_ca)} ảnh của thư mục)"
                       if mot_phan else "")
                    + (f", {sum(1 for *_x, la0 in viec if not la0)} lượt theo mức"
                       if len(nhom) > 1 else ""))

    def _chay_viec(self, *, vao, ra, ghi_de, lam_lai, de_quy, viec, tam_goc,
                   muc_thang, xong_dau, tieu_de):
        """Chạy retouch ở luồng nền — chung cho nút Chạy retouch (start) và lượt
        tự retouch ảnh mới (_chay_anh_moi). Mọi câu hỏi / kiểm tra đã xong ở bên
        gọi. viec = [(mức, [ảnh], mức 0 hết?)]; tam_goc None = MỘT lượt thẳng
        trên thư mục vào với muc_thang."""
        #[[ ENGINE THUONG TRU (7/10, giai doan 1 tai cau truc): me chay NGAY
        #   TRONG may xem truoc — mo hinh da nap, mot bo tren card (xem
        #   retouch.chay(engine=)). Chua co may thi mo luon (nap ~4 s — truoc
        #   day moi lan bam deu phai nap). Khong mo duoc (tool hong...) thi lui
        #   ve tien trinh con cu; luc do moi phai tat may xem truoc de nhuong
        #   card: no giu mo hinh tren card, ca me nap them mot bo nua la het. ]]
        if self._may_xem is None and not self._xem_hong:
            self._dam_bao_may_xem()
        self._engine_dung = self._may_xem is not None and self._may_xem.song()
        if self._engine_dung:
            self._tat_xem_truoc(dong_may=False)
            self._append("… chạy mẻ trong máy xem trước (mô hình đã nạp sẵn) — "
                         "xem trước tạm dừng tới khi xong")
        elif self._may_xem is not None:
            self._tat_xem_truoc(dong_may=True)
            self._append("… đã tắt xem trước để nhường card đồ hoạ cho lượt chạy")
        goc = Path(self.v_goc.get().strip().strip('"'))
        luong = int(self.v_luong.get())
        #[[ Doc bien Tk O DAY (luong chinh): luong nen chi cam gia tri. ]]
        may = self.v_may.get()
        che_do = self.v_che_do.get()
        #[[ 9/10: VUA XUAT VUA RETOUCH — Lightroom dang an het CPU va vai GB RAM;
        #   retouch ep 1 luong, che do tiet kiem (o nho nhat) de khong tranh
        #   RAM / VRAM toi muc sap. Cham hon ~30–50% nhung khong treo may. ]]
        x = getattr(self, "_xuat", None)
        if x and x.get("song_song") and x.get("trang_thai") not in ("xong", "dung", "loi"):
            luong, che_do = 1, "tiet_kiem"
        self._dat_dang_chay(True)
        #[[ Giu 80 dong log cuoi de con GIAI THICH duoc ma thoat.
        #   Ma 3221225477 mot minh khong noi gi; ma do CONG voi dong "OOM on
        #   device 0" thi noi duoc chinh xac phai lam gi.
        #]]
        self._luong_dang_chay = luong
        #[[ So anh DA CO truoc khi bam Chay. Khong tru no thi lan chay tiep tuc
        #   (600 anh da xong tu luot truoc) se ra toc do nhanh gia. ]]
        self._xong_dau = xong_dau
        self._log_cuoi: list[str] = []
        #[[ Gom RIENG cac dong "! BO QUA" thay vi doc lai tu _log_cuoi: chung
        #   duoc in luc NAP BUOC, tuc ngay dau lượt chay, nen mot buoi vai tram
        #   anh la chung da troi khoi 80 dong cuoi tu lau. ]]
        self._bi_bo: list = []
        self._so_dong_log = 0        # đếm để biết tool có nói gì không
        self._append(f"\n=== {datetime.now():%H:%M:%S}  {tieu_de}, {luong} luồng ===")

        #[[ MA SAP: tien trinh bi giet GIUA CHUNG, khong phai chay xong hay
        #   nguoi dung bam Dung. Gap mot trong so nay thi tu chay lai.
        #]]
        MA_SAP = (3221225477,   # 0xC0000005 ACCESS_VIOLATION
                  3221226356,   # 0xC0000374 HEAP_CORRUPTION
                  3221226505)   # 0xC0000409 FAIL_FAST
        self._dung_tay = False
        #[[ Dat lai tien do moi lan chay. Khong dat lai thi lan chay thu hai
        #   bat dau tu con so cua lan truoc — thanh tien do nhay vot roi dung
        #   im, te hon la dung im tu dau. ]]
        self._tien_do_tool = 0

        #[[ Tien do LUOT CHAY tren thu muc tam: ket qua chi ra thu muc that khi
        #   xong tung luot, dem file thu muc ra thi thanh tien do dung im. Dem bang
        #   so anh da dua ra + tien do tool cua luot dang chay (xem _dem). ]]
        self._luot_chay = ({"tong": sum(len(a) for _m, a, _l in viec), "xong": 0}
                           if tam_goc is not None else None)
        if tam_goc is not None:
            self._xong_dau = 0
        self._vao_luot = self._ra_luot = None
        #  thanh tiến độ ở đáy cửa sổ: hiện NGAY từ 0, không đợi nhịp đếm đầu
        try:
            n0 = (self._luot_chay or {}).get("tong") or sum(len(a) for _m, a, _l in viec)
            self._dat_tien_do_tt(0, n0, f"Đang retouch 0/{n0} ảnh  ·  đang khởi động…")
        except Exception:                                    # noqa: BLE001
            pass

        def chay_mot(thu_muc, muc, ra=ra, ghi_de=ghi_de, lam_lai=lam_lai):
            #[[ TU CHAY LAI khi sap giua me anh.
            #
            #   0xC0000374 lam sap tien trinh o anh 556/3465. Tien trinh da
            #   hong vung nho thi khong cuu duoc, nhung CA ME thi cuu duoc:
            #   tool tu bo qua anh da co ket qua, nen chay lai la di tiep tu
            #   dung cho dung. Truoc day nguoi dung phai ngoi canh bam Chay
            #   lai hang chuc lan cho het 3465 anh.
            #
            #   DIEU KIEN DUNG LAI: lan vua roi phai lam duoc THEM it nhat mot
            #   tam. Khong tien bo ma van chay lai la lap vo han o dung tam
            #   anh gay sap - te hon la dung han, vi nguoi dung tuong no dang
            #   chay.
            #]]
            lan = 0
            while True:
                lan += 1
                #[[ rt.dem() chu KHONG phai self._dem(): _dem() dong vao
                #   widget Tk (thanh tien do, nhan trang thai), ma day la
                #   LUONG NEN - dong vao Tk tu luong khac la mot nguon treo
                #   giao dien kinh dien. rt.dem() chi dem file, khong ve gi.
                #]]
                _, truoc = self.rt.dem(thu_muc, ra, de_quy)
                ma_cuoi = 0
                #[[ engine = may xem truoc DANG SONG luc goi (doc moi lan: no
                #   chet giua me thi lan tu-chay-lai di duong tien trinh con). ]]
                for loai, gt in self.rt.chay(
                        goc, thu_muc, ra, muc, may=may,
                        de_quy=de_quy, lam_lai=lam_lai,
                        luong=luong, che_do=che_do,
                        ghi_de=ghi_de,
                        engine=(self._may_xem if getattr(self, "_engine_dung", False)
                                else None)):
                    if loai == "pid":
                        self.proc = gt
                        continue
                    if loai == "ma":
                        ma_cuoi = int(gt or 0)
                        continue      # giu lai: con co the chay tiep
                    self.log_q.put((loai, gt))

                if ma_cuoi not in MA_SAP or self._dung_tay:
                    return ma_cuoi
                tong, sau = self.rt.dem(thu_muc, ra, de_quy)
                con = tong - sau
                if sau <= truoc or con <= 0:
                    return ma_cuoi
                self.log_q.put((
                    "dong",
                    f"=== sap (ma {ma_cuoi}) sau khi lam them {sau - truoc} anh"
                    f" - tu chay lai, con {con} anh (lan {lan + 1}) ==="))

        def work():
            ma = 0
            try:
                if tam_goc is None:
                    ma = chay_mot(vao, muc_thang)
                else:
                    n_luot = sum(1 for _m, _a, la0 in viec if not la0)
                    i = 0
                    lc = self._luot_chay
                    for m, a, la0 in viec:
                        if self._dung_tay:
                            break
                        if la0:
                            #[[ Muc 0 het = khong retouch. Ghi de thi anh goc giu
                            #   nguyen la dung; ra thu muc khac thi chep nguyen ban
                            #   sang de thu muc giao khach du anh. ]]
                            n = 0 if ghi_de else self.rt.chep_nguyen_ban(
                                a, vao, ra, de_quy, lam_lai)
                            if lc is not None:
                                lc["xong"] += len(a)
                            self.log_q.put(("dong", f"=== {len(a)} ảnh mức 0 hết: "
                                                    + ("giữ nguyên ảnh gốc" if ghi_de
                                                       else f"chép nguyên bản {n} ảnh "
                                                            "sang thư mục ra") + " ==="))
                            continue
                        i += 1
                        d = tam_goc / f"nhom_{i}"
                        d_ra = tam_goc / f"ra_{i}"
                        lien, chep = self.rt.dung_thu_muc_nhom(vao, a, d, de_quy)
                        self.log_q.put(("dong", f"=== lượt {i}/{n_luot}: {len(a)} ảnh"
                                                + (f" (chép {chep} ảnh vào thư mục "
                                                   f"tạm)" if chep else "") + " ==="))
                        #[[ saytool LUON ghi ra thu muc tam rieng (d_ra, moi tinh,
                        #   khong --ghi-de, khong --lam-lai — sap giua chung thi
                        #   chay lai di tiep dung cho), roi app dua tung tam ra
                        #   thu muc ra / de len anh goc. Dua ra CA KHI hong /
                        #   dung giua chung: tam nao da xong thi khong mat. ]]
                        self._tien_do_tool = 0
                        self._vao_luot, self._ra_luot = d, d_ra
                        try:
                            ma = chay_mot(d, m, ra=d_ra, ghi_de=False, lam_lai=False)
                        finally:
                            self._vao_luot = self._ra_luot = None
                        n_ra = self.rt.dua_ket_qua_ra(a, vao, d_ra, ra, de_quy, ghi_de)
                        if lc is not None:
                            lc["xong"] += n_ra
                        self._tien_do_tool = 0
                        self.log_q.put(("dong", f"=== đã {'ghi đè lên ảnh gốc' if ghi_de else 'đưa ra thư mục ra'}"
                                                f" {n_ra}/{len(a)} ảnh ==="))
                        if ma != 0 or self._dung_tay:
                            break
            except Exception:                                # noqa: BLE001
                self.log_q.put(("loi", traceback.format_exc()))
                ma = ma or 1
            finally:
                if tam_goc is not None:
                    self.rt.don_thu_muc_tam(tam_goc)
            self.log_q.put(("ma", ma))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    # ------------------------------------------------------------ tự retouch ảnh mới
    #[[ TU RETOUCH ANH MOI (7/10 — user: "Tu dong Retouch cac anh moi khi duoc
    #   them vao trong Folder dang duoc Retouch. Co the quet Folder de them cac anh
    #   duoc them moi vao trong qua trinh chay Retouch. Can Option chon bat len.
    #   Khi duoc bat thi chi dung thong so cua muc chung de ap vao cac anh moi roi
    #   export").
    #
    #   Bat cong tac roi bam Chay retouch: chup lai danh sach anh CO SAN (anh moi
    #   = xuat hien SAU moc nay, ke ca trong luc luot dau dang chay) va bo muc ap
    #   cho anh moi = cac thanh THE CHUNG dang dat (khong muc rieng gioi tinh —
    #   anh moi chua ai xem, chua biet mat ai). Luot dau xong, cu 5 giay quet thu
    #   muc Vao (o luong chinh, chi liet ke file): anh moi chua co ket qua, kich
    #   thuoc + gio sua KHONG DOI qua hai lan quet (Lightroom / the nho da chep
    #   xong) -> mot luot chay rieng cho nhung anh do (thu muc tam, _chay_viec).
    #   Dung = thoi theo doi. Anh hong khi chay khong thu lai (tranh lap vo han). ]]
    QUET_GIAY = 5

    def _doi_tu_moi(self):
        try:
            self.rt.ghi_cau_hinh({"tu_moi": bool(self.v_tu_moi.get())})
        except OSError:
            pass
        if not self.v_tu_moi.get() and self._theo_doi is not None \
                and not self._theo_doi.get("xuat") \
                and not (self.worker and self.worker.is_alive()):
            self._dung_theo_doi("đã tắt “Tự retouch ảnh mới”")

    def _chuan_bi_theo_doi(self, vao, ra, ghi_de):
        """Lúc bấm Chạy (công tắc đang bật): ảnh có sẵn + mức cho ảnh mới.
        None khi mức Chung đang 0 hết (đã nói ra) — lượt này vẫn chạy bình thường."""
        muc = self._loc_muc({k: v for k, v in self.muc_day_du().items()
                             if ":" not in str(k)})
        if self.rt.muc_trong(muc):
            messagebox.showinfo(
                "Tự retouch ảnh mới",
                "Các thanh ở thẻ Chung đang 0 hết — ảnh mới thêm vào sẽ không có "
                "gì để retouch, nên lần này KHÔNG theo dõi thư mục.\n\n"
                "Kéo các thanh ở thẻ Chung tới mức muốn dùng cho ảnh mới rồi bấm "
                "Chạy retouch lại.", parent=self)
            return None
        de_quy = bool(self.v_dequy.get())
        return {"vao": str(vao), "ra": str(ra), "ghi_de": bool(ghi_de),
                "de_quy": de_quy, "muc": muc, "so": 0, "cho": {},
                "biet": {str(p) for p, _x in self.rt.ds_anh(vao, None, de_quy)}}

    def _vao_theo_doi(self, td, ly_do: str = ""):
        """Bắt đầu / tiếp tục theo dõi (không có lượt nào đang chạy)."""
        self._theo_doi = td
        self._dung_tay = False
        self._dat_dang_chay(True)                # nút Dừng = thôi theo dõi
        self._append(f"=== THEO DÕI {td['vao']} — ảnh mới thêm vào sẽ tự retouch "
                     f"bằng mức chung: {self._mo_ta_muc(td['muc'])}"
                     + (f" ({ly_do})" if ly_do else "") + " ===")
        self._bao_theo_doi()
        self._hen_quet()

    def _bao_theo_doi(self):
        td = self._theo_doi
        if td is None:
            return
        if td.get("xuat"):
            self._hien_tien_do_xuat()
            return
        self.app.status(f"Đang theo dõi “{Path(td['vao']).name}” — ảnh mới tự retouch "
                        f"bằng mức chung (đã làm {td['so']} ảnh mới). Bấm Dừng để "
                        "thôi.", gd.MAU["xong"])

    def _hen_quet(self):
        self._dung_hen_quet()
        try:
            self._hen_quet_ma = self.after(int(self.QUET_GIAY * 1000), self._quet_moi)
        except tk.TclError:
            self._hen_quet_ma = None

    def _dung_hen_quet(self):
        if self._hen_quet_ma is not None:
            try:
                self.after_cancel(self._hen_quet_ma)
            except tk.TclError:
                pass
        self._hen_quet_ma = None

    def _dung_theo_doi(self, ly_do: str = ""):
        td = self._theo_doi
        self._dung_hen_quet()
        self._theo_doi = None
        if td is not None and td.get("xuat"):
            #  9/10: thôi theo lượt xuất (xong / Dừng) -> trả nhân CPU đã ghim
            self._xuat = None
            try:
                getattr(self.app, "tra_cpu_xuat", lambda: None)()
            except Exception:                                # noqa: BLE001
                pass
        if td is not None:
            self._append("=== thôi theo dõi thư mục" + (f" ({ly_do})" if ly_do else "")
                         + f" — đã tự retouch {td['so']} ảnh mới ===")
            self.app.status(f"Đã thôi theo dõi — tự retouch {td['so']} ảnh mới",
                            gd.MAU["mo"])
        if not (self.worker and self.worker.is_alive()):
            self._dat_dang_chay(False)

    def _quet_moi(self):
        """Một lần quét thư mục Vào tìm ảnh mới (luồng chính, chỉ liệt kê file)."""
        self._hen_quet_ma = None
        td = self._theo_doi
        if td is None or self._dung_tay:
            return
        xuat = bool(td.get("xuat"))
        if not xuat and not self.v_tu_moi.get():
            self._dung_theo_doi("đã tắt “Tự retouch ảnh mới”")
            return
        if self.worker and self.worker.is_alive():
            self._hen_quet()
            return
        x = getattr(self, "_xuat", None) or {}
        lr_xong = x.get("trang_thai") in ("xong", "dung", "loi")
        if xuat and not x.get("song_song") and not lr_xong:
            #[[ Che do TUAN TU: cho Lightroom xuat xong roi moi retouch. ]]
            self._hen_quet()
            return
        if xuat:
            try:
                import xuat_lr
                td["ban_do"] = {os.path.normcase(v) for v in xuat_lr.bang_anh().values()}
            except Exception:                                # noqa: BLE001
                pass
        try:
            ds = self.rt.ds_anh(Path(td["vao"]),
                                None if td["ghi_de"] else Path(td["ra"]), td["de_quy"])
        except OSError:
            ds = []
        ds_stat = []
        for p, xong in ds:
            try:
                st = os.stat(p)
            except OSError:
                continue
            ds_stat.append((str(p), bool(xong), st.st_size, st.st_mtime_ns, st.st_mtime))
        san, co_moi = chon_anh_moi(ds_stat, td)
        if co_moi or san:
            self._dem()                    # dải ảnh hiện ngay tấm mới
        if xuat and lr_xong and not san and not td["cho"]:
            self._ket_thuc_xuat()
            return
        if not san:
            self._hen_quet()
            return
        #[[ 9/10: VUA XUAT VUA RETOUCH — RAM trong duoi nguong thi TAM NGUNG nhan
        #   anh moi (anh dang lam van xong), 5 giay sau do lai. Khong tranh RAM
        #   voi Lightroom toi muc may sap. Anh van nam trong "cho" (chua vao biet)
        #   nen lan quet sau lai thay chung. ]]
        if xuat and x.get("song_song") and not lr_xong:
            ok, ly_do = self._du_tai_nguyen()
            if not ok:
                if x.get("tam_ngung") != ly_do:
                    x["tam_ngung"] = ly_do
                    self._append(f"… tạm ngưng nhận ảnh mới: {ly_do} — tự tiếp khi hồi")
                    self._hien_tien_do_xuat()
                self._hen_quet()
                return
            if x.get("tam_ngung"):
                self._append("… tài nguyên đã hồi — tiếp tục retouch ảnh mới")
                x["tam_ngung"] = ""
        for k in san:
            td["biet"].add(k)
            td["cho"].pop(k, None)
        self._chay_anh_moi(san)

    def _chay_anh_moi(self, ds: list):
        if self._bi_khoa():
            self._dung_theo_doi("hết hạn bản quyền")
            return
        td = self._theo_doi
        vao, ra = Path(td["vao"]), Path(td["ra"])
        try:
            tam_goc = self.rt.tao_thu_muc_tam(vao)
        except OSError as ex:
            self._append(f"! không tạo được thư mục tạm cho ảnh mới: {ex}")
            self._dung_theo_doi("lỗi thư mục tạm")
            return
        td["so"] += len(ds)
        ten = ", ".join(Path(p).name for p in ds[:3]) + (" …" if len(ds) > 3 else "")
        #[[ 9/10: luot Xuat voi muc 0 het (chua keo gi / preset rong) — khong
        #   retouch, chi chep nguyen ban sang thu muc ra (ghi de: giu nguyen). ]]
        la0 = bool(td.get("xuat")) and self.rt.muc_trong(td["muc"])
        self._chay_viec(vao=vao, ra=ra, ghi_de=td["ghi_de"], lam_lai=True,
                        de_quy=td["de_quy"], viec=[(dict(td["muc"]), list(ds), la0)],
                        tam_goc=tam_goc, muc_thang=dict(td["muc"]), xong_dau=0,
                        tieu_de=(f"retouch {len(ds)} ảnh Lightroom vừa xuất ({ten})"
                                 if td.get("xuat") else
                                 f"tự retouch {len(ds)} ảnh mới ({ten}) bằng mức chung"))
        self._bao_theo_doi()

    # ------------------------------------------------------------ xuất một thao tác
    #[[ XUAT MOT THAO TAC (9/10 — user: "Thay doi Flow lon nay de chay 1 thao tac
    #   khi bam xuat anh"): App gui yeu cau Lightroom xuat (xuat_lr), roi giao
    #   cho man nay: Vao = thu muc xuat, Ra theo lua chon, muc chung = preset.
    #   Vong theo doi thu muc (_quet_moi) chay o che do "xuat": anh thuoc luot
    #   nay = mtime >= luc bat dau HOAC co trong bang path->jpg plugin ghi; on
    #   dinh qua hai lan quet moi chay (Lightroom dang ghi do). Song song: chay
    #   ngay tung dot; tuan tu: doi Lightroom bao xong. App bao tien do Lightroom
    #   qua cap_nhat_xuat(); ket thuc khi Lightroom xong VA khong con anh cho. ]]
    def bat_dau_theo_xuat(self, *, vao: str, ra: str, ghi_de: bool, muc: dict | None,
                          song_song: bool, preset: str = "", ly_do_tuan_tu=()) -> bool:
        if self.worker is not None and self.worker.is_alive():
            messagebox.showinfo("Đang chạy retouch",
                                "Đợi lượt retouch đang chạy xong (hoặc bấm Dừng) rồi "
                                "mới Xuất.", parent=self)
            return False
        if self._theo_doi is not None:
            self._dung_theo_doi("bắt đầu lượt Xuất mới")
        vao = os.path.normpath(str(vao).strip().strip('"'))
        try:
            Path(vao).mkdir(parents=True, exist_ok=True)
        except OSError as ex:
            messagebox.showerror("Không tạo được thư mục xuất", f"{vao}\n{ex}", parent=self)
            return False
        self.v_ghide.set(bool(ghi_de))
        self.v_vao.set(vao)
        if not ghi_de:
            self.v_ra.set(os.path.normpath(str(ra).strip().strip('"')) if ra
                          else os.path.normpath(vao.rstrip("\\/") + "_retouch"))
        self._doi_bang_muc_anh(vao)
        if preset:
            self.ap_preset(preset, ca_thu_muc=True)
        elif muc is not None:
            self._muc_chung_tm = self._loc_muc({k: v for k, v in muc.items()
                                                if ":" not in str(k) or True})
            self._muc_chung_ban = True
            self._luu_muc()
            self._nap_muc_vao_bang(self._muc_chung_day_du())
        chung = self._loc_muc({k: v for k, v in self._muc_chung_day_du().items()})
        self._theo_doi = {"vao": vao, "ra": self.v_ra.get().strip(), "ghi_de": bool(ghi_de),
                          "de_quy": False, "muc": chung, "so": 0, "cho": {}, "biet": set(),
                          "xuat": True, "tu_luc": time.time() - 2.0, "ban_do": set(),
                          "xong_rt": 0, "loi_rt": 0}
        self._xuat = {"song_song": bool(song_song), "t0": time.time(), "tong": 0,
                      "xong_lr": 0, "loi_lr": 0, "trang_thai": "cho", "thu_muc": vao,
                      "thong_bao": "", "tam_ngung": "", "ly_do": list(ly_do_tuan_tu or [])}
        self._dung_tay = False
        self._dat_dang_chay(True)
        self.v_xem.set("luoi")
        try:
            self._doi_xem()
        except Exception:                                    # noqa: BLE001
            pass
        self._append(f"\n=== {datetime.now():%H:%M:%S}  XUẤT TỪ LIGHTROOM → {vao}"
                     + (" · retouch SONG SONG" if song_song else " · retouch SAU khi xuất xong")
                     + (f" (máy không đủ sức: {'; '.join(ly_do_tuan_tu)})" if ly_do_tuan_tu else "")
                     + (f" · preset “{preset}”" if preset else "")
                     + f" · mức: {self._mo_ta_muc(chung) if not self.rt.muc_trong(chung) else '0 hết → chỉ chép'}"
                     + (" · ghi đè lên ảnh xuất" if ghi_de else f" · ra {self.v_ra.get()}") + " ===")
        self._hien_tien_do_xuat()
        self._hen_quet()
        return True

    def cap_nhat_xuat(self, td: dict):
        """App gọi mỗi ~1,2 s với tiến độ Lightroom (xuat_lr.tien_do_xuat)."""
        x = getattr(self, "_xuat", None)
        if x is None:
            return
        tt = td.get("trang_thai") or ("cho" if not td else x.get("trang_thai"))
        doi = tt != x.get("trang_thai")
        x.update({"trang_thai": tt, "tong": int(td.get("tong") or x.get("tong") or 0),
                  "xong_lr": int(td.get("xong") or 0), "loi_lr": int(td.get("loi") or 0),
                  "thong_bao": str(td.get("thong_bao") or ""),
                  "bo_sao": int(td.get("bo_sao") or x.get("bo_sao") or 0)})
        if doi and tt in ("xong", "dung", "loi"):
            self._append(f"… Lightroom {'xuất xong' if tt == 'xong' else ('đã dừng' if tt == 'dung' else 'LỖI')}:"
                         f" {x['xong_lr']}/{x['tong']} ảnh"
                         + (f" ({x['loi_lr']} không ra file)" if x['loi_lr'] else "")
                         + (f" · bỏ {x['bo_sao']} ảnh đã lọc (có sao)" if x.get('bo_sao') else "")
                         + (f" · {x['thong_bao']}" if x['thong_bao'] else "")
                         + ("" if x.get("song_song") else " — bắt đầu retouch"))
            if self._theo_doi is not None and not (self.worker and self.worker.is_alive()):
                #  không chờ hết nhịp 5 s: quét ngay
                self._dung_hen_quet()
                try:
                    self._hen_quet_ma = self.after(300, self._quet_moi)
                except tk.TclError:
                    pass
        self._hien_tien_do_xuat()

    def _hien_tien_do_xuat(self):
        x = getattr(self, "_xuat", None)
        td = self._theo_doi
        if x is None:
            return
        tong_lr, xong_lr = int(x.get("tong") or 0), int(x.get("xong_lr") or 0)
        tt = x.get("trang_thai")
        if tt == "cho":
            lr = "Lightroom: chờ nhận yêu cầu…"
        elif tt == "dang_chay":
            lr = f"Lightroom xuất {xong_lr}/{tong_lr}"
        else:
            lr = f"Lightroom {'xong' if tt == 'xong' else tt} {xong_lr}/{tong_lr}"
        xong_rt = int((td or {}).get("xong_rt", 0))
        so_cho = len((td or {}).get("cho", {})) + (
            int(getattr(self, "_luot_chay", None) and self._luot_chay.get("tong") or 0)
            if (self.worker and self.worker.is_alive()) else 0)
        dich = max(tong_lr, xong_rt + so_cho)
        if x.get("song_song") or tt in ("xong", "dung", "loi"):
            rt = f"Retouch {xong_rt}/{dich}" + (f" (đang làm {so_cho})" if so_cho else "")
        else:
            rt = "Retouch: sau khi xuất xong"
        if x.get("tam_ngung"):
            rt += " · tạm ngưng: " + x["tam_ngung"]
        giay = time.time() - float(x.get("t0") or time.time())
        chu = f"{lr} · {rt} · {giay / 60:.0f} phút"
        self._dat_tien_do_tt(xong_rt, max(dich, 1), chu)
        self.app.status(chu, gd.MAU["nhan"])

    def _du_tai_nguyen(self) -> tuple:
        """RAM còn đủ để nhận thêm ảnh không (khi vừa xuất vừa retouch).
        -> (đủ, lý do). Chỉ xét RAM: VRAM do chính engine của ta giữ, xét nó là
        tự khoá mình; hết VRAM giữa mẻ đã có vòng tự chạy lại."""
        try:
            import xuat_ui
            trong, _tong = xuat_ui._ram_gb()                 # noqa: SLF001
        except Exception:                                    # noqa: BLE001
            return True, ""
        if trong and trong < 1.5:
            return False, f"RAM trống {trong:.1f} GB (< 1,5 GB)"
        return True, ""

    def _ket_thuc_xuat(self):
        x, td = getattr(self, "_xuat", None), self._theo_doi
        if x is None:
            return
        xong_rt = int((td or {}).get("xong_rt", 0))
        loi_rt = int((td or {}).get("loi_rt", 0))
        giay = time.time() - float(x.get("t0") or time.time())
        tt = x.get("trang_thai")
        cau = (f"Xuất + retouch {'xong' if tt == 'xong' else ('đã dừng' if tt == 'dung' else 'lỗi Lightroom')}: "
               f"Lightroom {x.get('xong_lr', 0)}/{x.get('tong', 0)} ảnh"
               + (f" ({x.get('loi_lr')} không ra file)" if x.get("loi_lr") else "")
               + f" · retouch {xong_rt} ảnh" + (f" ({loi_rt} lượt lỗi)" if loi_rt else "")
               + f" · {giay / 60:.1f} phút"
               + (f" · {x['thong_bao']}" if tt == "loi" and x.get("thong_bao") else ""))
        self._append("=== " + cau + " ===")
        self._xuat = None
        self._dung_theo_doi("xuất xong")
        mau = gd.MAU["xong"] if tt == "xong" and not loi_rt else gd.MAU["canh"]
        self._dat_tien_do_tt(xong_rt, max(xong_rt, 1), cau, mau)
        self.app.status(cau, mau)
        self._dem()

    def stop(self):
        #[[ Danh dau TRUOC khi giet: khong danh dau thi vong tu chay lai trong
        #   work() thay ma thoat 0xC0000005 (terminate cung cho ma do tren
        #   Windows) va lai chay tiep - nguoi dung bam Dung ma no khong dung.
        #]]
        self._dung_tay = True
        #[[ 9/10: dang Xuat mot thao tac -> Dung = xin Lightroom dung luot xuat
        #   (sau lo dang chay) VA thoi retouch anh moi. ]]
        x = getattr(self, "_xuat", None)
        if x and x.get("trang_thai") not in ("xong", "dung", "loi"):
            try:
                import xuat_lr
                xuat_lr.dung_xuat()
                self._append("… đã xin Lightroom dừng xuất (dừng sau lô đang chạy)")
            except Exception as ex:                          # noqa: BLE001
                self._append(f"! không gửi được lệnh dừng Lightroom: {ex}")
        #[[ Dang theo doi ma khong co luot nao chay -> Dung = thoi theo doi ngay. ]]
        if self._theo_doi is not None and not (self.worker and self.worker.is_alive()):
            self._dung_theo_doi("đã bấm Dừng")
            return
        #[[ Me dang chay trong ENGINE THUONG TRU: xin dung (anh dang lam xong roi
        #   thoi), khong giet — giet la mat luon may xem truoc. 20 s khong dung
        #   duoc (ket trong mot buoc) thi tat han engine. ]]
        m = self._may_xem
        if m is not None and getattr(m, "dang_chay", False):
            self._append("… đang dừng — ảnh đang làm sẽ xong rồi mới dừng")
            m.dung_chay()
            self.btn_stop.configure(state="disabled")
            try:
                self.after(20000, self._ep_dung_engine)
            except tk.TclError:
                pass
            return
        p = self.proc
        if p and p.poll() is None:
            self._append("… đang dừng")
            try:
                p.terminate()
            except OSError as ex:
                self._append(f"! không dừng được: {ex}")
        self.btn_stop.configure(state="disabled")

    def _ep_dung_engine(self):
        """Bấm Dừng đã 20 s mà mẻ trong engine chưa dừng -> tắt hẳn tiến trình."""
        m = self._may_xem
        if self.worker is not None and self.worker.is_alive() and m is not None \
                and getattr(m, "dang_chay", False):
            self._append("! engine không dừng được trong 20 s — tắt hẳn tiến trình")
            m.dong()

    def _pump(self):
        try:
            while True:
                loai, gt = self.log_q.get_nowait()
                if loai == "keo":
                    self._keo_dang_hoi = False
                    self._dung_lai_thanh_keo(gt)
                    n = len(self.v_muc)
                    #[[ Noi "tool bao N tinh nang" khi tool CHUA he noi gi la
                    #   mot cau sai — no khang dinh dung cai bang du phong la
                    #   cua tool. Da suyt lam nguoi dung tin nham mot lan. ]]
                    if self.rt.da_hoi_that(gt):
                        self._append(f"… tool báo {n} tính năng: "
                                     + ", ".join(self.v_muc.keys()))
                    else:
                        self._append(f"… vẫn chưa hỏi được tool — đang dùng "
                                     f"bảng dự phòng {n} tính năng")
                elif loai == "kiem":
                    ok, mo = gt
                    #[[ THIEU GOI TAI DUOC -> MO CUA SO TAI, khong chi bao loi.
                    #
                    #   retouch.kiem_tra() gan nhan "TAI_DUOC:<ten goi>" khi
                    #   ban .exe thieu dung nhung thu tai ve duoc. Do la tinh
                    #   huong BINH THUONG cua ban nhe o lan chay dau, khong
                    #   phai hong — nen phai mo duong sua ngay tai day.
                    #]]
                    if not ok and str(mo).startswith("TAI_DUOC:"):
                        dong1 = str(mo).splitlines()[0]
                        can = [x for x in dong1[len("TAI_DUOC:"):].split(",") if x]
                        self.lbl_goc.configure(
                            text="Chưa có tài nguyên retouch — đang mở cửa sổ tải.",
                            foreground=gd.MAU["canh"])
                        if self._mo_cua_so_tai(can):
                            self.after(60, lambda: self._kiem(chay_thu=True))
                        continue
                    self.lbl_goc.configure(text=mo,
                                           foreground=gd.MAU["xong"] if ok else gd.MAU["loi"])
                    #[[ Sua duoc thi sua luon, dung bat nguoi dung di tim nut khac.
                    #]]
                    if not ok and self._hoi_chep():
                        self.after(60, lambda: self._kiem(chay_thu=True))
                elif loai == "lenh":
                    self._append(f"$ {gt}")
                elif loai == "ma":
                    self._xong(gt)
                else:
                    #[[ BAT DONG TIEN DO CUA TOOL — can cho che do ghi de.
                    #
                    #   saytool in "  10/2021  0.74s/anh  con lai ~24.8 phut"
                    #   moi 10 anh. Ghi de thi khong dem duoc bang file (anh ra
                    #   de len anh vao), nen day la nguon duy nhat biet no lam
                    #   toi dau. Xem _dem().
                    #]]
                    m = _RE_TIEN_DO.match(str(gt))
                    if m:
                        self._tien_do_tool = int(m.group(1))
                    bo = self.rt.buoc_bi_bo([gt])
                    if bo:
                        self._bi_bo.extend(bo)
                    self._append(gt)
                    self._so_dong_log = getattr(self, "_so_dong_log", 0) + 1
                    ds = getattr(self, "_log_cuoi", None)
                    if ds is not None:
                        ds.append(str(gt))
                        del ds[:-80]
        except queue.Empty:
            pass
        #[[ Dem file THUA hon moi 1.5 giay, khong phai moi vong bom log.
        #   _dem() goi iterdir() tren thu muc co the hang nghin anh; goi 3
        #   lan/giay tren o mang la tu lam cham chinh tien trinh dang do.
        #]]
        song = bool(self.worker and self.worker.is_alive())
        if song:
            now = time.monotonic()
            if now - getattr(self, "_lan_dem", 0.0) >= 1.5:
                self._lan_dem = now
                self._dem()
        self._dong_bo_dai()
        self.after(250 if song else 800, self._pump)

    def _xong(self, ma: int):
        self.proc = None
        try:
            import trang_thai as tt
            goc = self.app.folder()
            if goc and getattr(self, "_t0", None):
                tt.ghi_khau(tt.ten_buoi(goc), "retouch",
                            time.monotonic() - self._t0, ma_thoat=ma)
        except Exception:                                    # noqa: BLE001
            pass
        self._dat_dang_chay(False)
        #[[ Chay xong: mo lai may xem truoc o nen (da tat luc bam Chay de
        #   nhuong card do hoa) — keo thanh tiep la thay ngay. Engine thuong
        #   tru chet GIUA ME (sap 0xC0000005...) thi xoa dau "hong" de mo lai:
        #   dau do la cua lan chet nay, khong phai xem truoc hong that. ]]
        if getattr(self, "_engine_dung", False) and (
                self._may_xem is None or not self._may_xem.song()):
            self._xem_hong = ""
        try:
            self.after(800, self._san_may_xem)
        except tk.TclError:
            pass
        tong, xong = self._dem()
        #[[ 8/10: chay qua thu muc tam (anh dang chon / nhieu muc / ghi de) thi
        #   SO CUA LUOT CHAY moi dung — _dem() dem ca thu muc, va o che do ghi de
        #   khong dem duoc bang file (ra 0/13 du da xong het). ]]
        lc = getattr(self, "_luot_chay", None)
        if lc:
            tong, xong = int(lc["tong"]), min(int(lc["xong"]), int(lc["tong"]))
        ghi_de_luot = bool(self.v_ghide.get())
        noi_ra = ("đã ghi đè lên ảnh gốc" if ghi_de_luot
                  else f"→ {self.v_ra.get()}")
        #[[ TINH NANG BI BO GIUA CHUNG PHAI DUOC NOI LAI O CUOI.
        #
        #   Tu ban 0.9.5, buoc nao nap khong duoc (thieu file mo hinh chang han)
        #   thi saytool in mot dong "! BO QUA <ten>" roi CHAY TIEP. Anh van ra
        #   du, nhin qua van dep — chi la thieu han mot tinh nang. Dong do in ra
        #   ngay dau luot chay, tram dong log truoc khi xong, nen khong ai thay.
        #
        #   Bao o cuoi, va bao mau CANH chu khong phai mau XONG: mot buoi giao
        #   khach thieu buoc xoa khuyet diem thi khong the goi la "xong tot".
        #]]
        bo = getattr(self, "_bi_bo", [])
        if bo:
            self._append("")
            self._append("!!! Mấy tính năng sau KHÔNG chạy trong lượt này:")
            for ten, vi_sao in bo:
                self._append(f"    · {ten} — {vi_sao}")
            self._append("    Ảnh vẫn ra đủ nhưng THIẾU mấy tính năng đó. "
                         "Kiểm lại file mô hình rồi chạy lại với “Làm lại cả "
                         "ảnh đã có kết quả”.")
        if ma == 0 and bo:
            ten_bo = ", ".join(t for t, _ in bo)
            self._append(f"=== xong, {xong}/{tong} ảnh — NHƯNG thiếu: {ten_bo} ===")
            self.app.status(
                f"Retouch xong {xong}/{tong} ảnh nhưng THIẾU: {ten_bo} — "
                f"xem nhật ký", gd.MAU["canh"])
            self._dat_tien_do_tt(xong, tong, f"Retouch xong {xong}/{tong} ảnh",
                                 gd.MAU["canh"])
        elif ma == 0:
            self._append(f"=== xong, {xong}/{tong} ảnh có kết quả ===")
            self.app.status(f"Retouch xong {xong}/{tong} ảnh · {noi_ra}",
                            gd.MAU["xong"])
            self._dat_tien_do_tt(xong, tong, f"Retouch xong {xong}/{tong} ảnh")
        else:
            #[[ Dung tay cung ve day. Phan biet bang con lai, khong bang ma
            #   thoat: terminate() tren Windows tra ma khac tren Linux, con
            #   "con bao nhieu anh" thi luon dung.
            #]]
            self._append(f"=== dừng ở {xong}/{tong} ảnh (mã {ma}) ===")
            #[[ KHONG IN RA DONG NAO LA MOT MANH BANG CHUNG, KHONG PHAI "im lang".
            #
            #   duong_ong.chay() in ba dong ngay truoc khi bat dau (cau hinh
            #   may, so anh, danh sach buoc). Khong thay dong nao nghia la no
            #   chet TRUOC ca ba dong do — tuc chet luc NAP MO HINH, khong phai
            #   luc xu ly anh. Hai cho do bao hoan toan khac nhau, nen phai noi
            #   ro thay vi de nguoi dung doan. ]]
            if not getattr(self, "_so_dong_log", 0):
                self._append(
                    "   Tool KHÔNG in ra dòng nào — nó chết trước cả dòng "
                    "“cấu hình máy”, tức là chết lúc NẠP MÔ HÌNH chứ không "
                    "phải lúc xử lý ảnh. Thường là hết bộ nhớ card, hoặc một "
                    "file mô hình hỏng.")
            #[[ Dich ma thoat ra tieng nguoi NGAY TRONG NHAT KY.
            #   Ban truoc chi in "ma 3221225477" roi bao "chay lai la tiep tuc"
            #   — loi khuyen do sai han: chay lai voi 12 luong thi lai OOM o
            #   dung cho cu, va nguoi dung se lap lai mai.
            #]]
            vi = self.rt.giai_thich_ma(ma, "\n".join(getattr(self, "_log_cuoi", [])),
                                       getattr(self, "_luong_dang_chay", 0))
            for d in (vi.splitlines() if vi else []):
                self._append("   " + d)
            self._append("Chạy lại là tiếp tục từ chỗ dừng — tool tự bỏ qua "
                         "ảnh đã có kết quả.")
            self.app.status(f"Retouch dừng ở {xong}/{tong} ảnh", gd.MAU["canh"])
            self._dat_tien_do_tt(xong, tong, f"Retouch dừng ở {xong}/{tong} ảnh",
                                 gd.MAU["canh"])
            #[[ Dung giua chung thi LY DO nam trong nhat ky — dua nguoi dung
            #   toi do, dung de ho nhin luoi anh ma doan. ]]
            self.v_xem.set("nhat_ky")
            self._doi_xem()
        #[[ TU RETOUCH ANH MOI: luot vua xong (luot dau hay luot anh moi, ke ca
        #   hong — anh hong da nam trong "biet", khong thu lai) -> quay lai theo
        #   doi, tru khi nguoi dung bam Dung / tat cong tac. ]]
        td = self._theo_doi
        if td is not None and td.get("xuat"):
            if lc:
                td["xong_rt"] = int(td.get("xong_rt", 0)) + int(lc.get("xong", 0))
            if ma != 0 and not self._dung_tay:
                td["loi_rt"] = int(td.get("loi_rt", 0)) + 1
            self._hien_tien_do_xuat()
        if self._theo_doi is not None:
            if self._dung_tay or (not self._theo_doi.get("xuat") and not self.v_tu_moi.get()):
                self._dung_theo_doi("đã bấm Dừng" if self._dung_tay
                                    else "đã tắt “Tự retouch ảnh mới”")
            else:
                self._dat_dang_chay(True)
                self._bao_theo_doi()
                self._hen_quet()
