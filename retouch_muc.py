#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""retouch_muc.py — MucMixin: bảng thanh kéo + mô hình mức Chung / Riêng của màn Retouch.

Tách từ man_retouch.RetouchWindow (7/10, giai đoạn 2b) — chỉ di chuyển, không
sửa thân hàm. Gồm: dựng bảng thanh kéo và thẻ nhóm, đổi mức (người kéo / nạp
lại), mức đầy đủ / hiệu lực / hiện tại, lưu mức riêng từng ảnh, mô tả phạm vi,
reset, đồng bộ chọn, cảnh báo thanh kéo. Trạng thái vẫn nằm trên RetouchWindow
(self._muc_anh, self.v_muc, self.v_rieng…); mixin không có __init__.
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

import tkinter as tk
from tkinter import messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import giao_dien as gd
from retouch_chung import _so_muc





class MucMixin:
    """Thanh kéo + mức Chung / Riêng (xem đầu tệp).
    """

    def nhan_nhom(self, ma: str) -> str:
        return dict(self._ds_the or [("", "Chung")]).get(ma, ma) or "Chung"

    def nhan_the(self, ma: str) -> str:
        """Nhãn đang hiện của thẻ nhóm `ma` (có dấu · khi nhóm có mức riêng)."""
        for pd in getattr(self, "_pd_the", []):
            t = pd.nhan_cua(ma)
            if t:
                return t
        return ""

    def _dung_thanh_keo(self, goc) -> int:
        """Dựng lại bảng thanh kéo theo saytool ở thư mục goc. -> số hàng đã dùng.

        Dựng LẠI chứ không chỉ dựng một lần: người dùng đổi thư mục tool sang
        một bản khác thì danh sách thanh kéo cũng khác, mà giao diện vẫn hiện
        bảng cũ thì họ kéo một thứ không còn tồn tại.

        BỐ CỤC MỚI — MỘT HÀNG THẺ NHÓM Ở TRÊN, BẢNG THANH KÉO Ở DƯỚI

        #[[ VI SAO KHONG DUNG 5 NHOM x N THANH KEO CUNG MOT LUC.
        #
        #   saytool chia nam nhom khuon mat (Nu / Nam / Tre con / Nu lon tuoi /
        #   Nam lon tuoi). Sau thanh keo nhan nam nhom la ba muoi thanh keo tren
        #   mot man hinh — khong ai doc noi, va 95% thoi gian moi nhom deu dung
        #   chung mot muc.
        #
        #   Nen: mot hang the o tren, moi luc chi hien MOT bang. The "Chung" la
        #   muc mac dinh cho moi nhom; the mot nhom chi hien nhung thanh keo
        #   nhom do KHAI RIENG. The nao dang co muc rieng thi mang mot dau cham.
        #
        #   Day cung la cach giao dien rieng cua saytool lam (tabs trong
        #   giao_dien.py), nen nguoi dung khong phai hoc lai lan hai.
        #]]
        """
        #[[ Go vet cu TRUOC khi huy hang: v_rieng song qua moi lan dung lai,
        #   trace de lai se ghi vao nhan da huy ("invalid command name"). ]]
        for b, t in getattr(self, "_vet_keo", []):
            try:
                b.trace_remove("write", t)
            except (tk.TclError, ValueError):
                pass
        self._vet_keo = []
        for w in self._o_keo:
            try:
                w.destroy()
            except Exception:                                # noqa: BLE001
                pass
        self._o_keo = []
        self._sc_theo = {}
        self.v_muc = {}
        ds0 = self.rt.thanh_keo(goc)
        #[[ saytool nay tra moi thanh keo dang [ten, nhan, mac_dinh, goi_y,
        #   can_torch?] (5 phan tu — them can_torch 5/10). Cac vong lap ben duoi
        #   unpack 4 phan tu, nen TACH can_torch ra dict _can_torch_keo va giu
        #   _ds_keo dung 4 phan tu (tuong thich saytool cu tra 4 phan tu). ]]
        self._can_torch_keo = {}
        ds = []
        for row in ds0:
            if len(row) >= 5:
                self._can_torch_keo[row[0]] = bool(row[4])
            ds.append(list(row[:4]))
        self._ds_keo = ds
        nhom = self.rt.nhom_mat(goc)
        self._nhom_ds = [tuple(x) for x in nhom]
        sb = self.o_hang_keo
        #[[ Gia tri ban dau = MUC CUA ANH DANG XEM (rieng neu co, khong thi muc
        #   chung) — khong phai gia tri cua bien cu: moi lan keo da ghi ngay vao
        #   _muc_anh / muc chung, nen doc lai tu do la dung ca khi tool vua tra
        #   loi bang thanh keo that (thanh moi lay muc chung / mac dinh). ]]
        muc_ht = self._muc_hien_tai()

        #[[ Biến của MỌI nhóm phải tồn tại kể cả khi thẻ đó không đang hiện —
        #   nếu chỉ tạo cho thẻ đang xem thì chuyển thẻ là mất mức vừa đặt. ]]
        if not hasattr(self, "v_rieng"):
            self.v_rieng, self.v_bat_rieng = {}, {}
        for ten, _nhan, md, _goi in ds:
            for nh, _l in nhom:
                k = (nh, ten)
                if k in self.v_rieng:
                    continue
                gt = muc_ht.get(f"{nh}:{ten}")
                #[[ Mac dinh 0 (khong lay md cua buoc): moi project = 0 het. ]]
                self.v_rieng[k] = tk.DoubleVar(
                    value=_so_muc(gt, _so_muc(muc_ht.get(ten), 0)))
                self.v_bat_rieng[k] = tk.BooleanVar(value=gt not in (None, ""))

        self._dung_the_nhom(goc)
        hang = 1
        for ten, nhan, md, goi in ds:
            v = tk.DoubleVar(value=_so_muc(muc_ht.get(ten), 0))  # mac dinh 0
            self.v_muc[ten] = v
            if self.nhom_dang and not self.rt.theo_nhom(ten, goc):
                #[[ Buoc tu khai theo_nhom = False thi khong chia duoc — khong
                #   hien o the nhom, thay vi hien mot thanh keo khong co tac
                #   dung gi. ]]
                continue
            hang = self._mot_hang_keo(sb, hang, goc, ten, nhan, md, goi, v)
        return hang

    def _mot_hang_keo(self, sb, i, goc, ten, nhan, md, goi, v) -> int:
        """Một tính năng = nhãn · dấu ? · số ở trên, thanh trượt ở dưới (dáng
        Evoto). Ở thẻ một nhóm thì công tắc “riêng” đứng đầu hàng.

        #[[ KHONG dat width= o nhan. ttk.Label(width=N) CAT chu dai hon N, va
        #   ten cua 0.9.5 dai hon han ba ten cu: "Xoá khuyết điểm cơ thể" la 22
        #   ky tu, "Làm mờ nếp nhăn trán" 20. kiem_retouch_gui.py do bang Tk
        #   that, voi ca nhan dai. ]]
        """
        nh = self.nhom_dang
        o = ttk.Frame(sb)
        o.pack(fill="x", pady=(6, 1))
        dong = ttk.Frame(o)
        dong.pack(fill="x")
        self._o_keo += [o, dong]
        if not nh:
            bien = v
        else:
            k = (nh, ten)
            bien = self.v_rieng[k]
            bat = self.v_bat_rieng[k]
            ct = gd.CongTac(dong, bat, command=lambda _k=k: self._doi_bat_rieng(_k))
            ct.pack(side="left", padx=(0, 8))
            ct.goi_y = gd.GoiY(ct, "Riêng cho nhóm này — tắt thì nhóm này theo "
                                   "mức chung.")
            self._o_keo.append(ct)
        l1 = ttk.Label(dong, text=nhan)
        l1.pack(side="left")
        self._o_keo.append(l1)
        #[[ CAN TAI TORCH: tinh nang nay can torch ma ban --nhe chua tai. Van
        #   hien thanh keo (de nguoi dung biet co + dat muc truoc), nhung ghi chu
        #   "cần tải torch" cho ro — khong phai thieu tinh nang. Tai torch (lan
        #   dau bam Chay retouch) xong, doc lai la het dau nay. ]]
        if getattr(self, "_can_torch_keo", {}).get(ten):
            lct = ttk.Label(dong, text="· cần tải torch", style="Mo2.TLabel")
            lct.pack(side="left", padx=(6, 0))
            self._o_keo.append(lct)
            lct.goi_y = gd.GoiY(lct, "Tính năng này cần thư viện AI (torch) — "
                                     "bản cài tải về lần đầu bấm “Chạy retouch”. "
                                     "Đặt mức trước cũng được; tải xong là chạy.")
        chu = goi
        if nh:
            t = self.rt.tin_keo(goc).get(ten) or {}
            if nh in (t.get("bo_qua") or ()):
                chu = ("Bước này mặc định KHÔNG chạy cho nhóm này — bật “riêng” "
                       "là ép nó chạy. " + goi)
            elif t.get("ghi_chu"):
                chu = t["ghi_chu"]
        if chu:
            h = gd.NutHoi(dong, chu)
            h.pack(side="left", padx=(6, 0))
            self._o_keo.append(h)
        lb = ttk.Label(dong, width=4, anchor="e")
        lb.pack(side="right")
        sc = gd.Truot(o, from_=0, to=100, variable=bien,
                      command=lambda gt, _b=bien: self._lam_tron(_b, gt))
        sc.pack(fill="x", pady=(3, 0))
        #[[ Ban phim: mui ten +-1, Shift +-10. Bam dup thanh = ve muc mac dinh
        #   cua tool (nhu Lightroom / Evoto). ]]
        for phim, buoc in (("<Left>", -1), ("<Down>", -1), ("<Right>", 1),
                           ("<Up>", 1), ("<Shift-Left>", -10), ("<Shift-Right>", 10)):
            sc.bind(phim, lambda _e, _s=sc, _b=buoc: (_s.set(_s.get() + _b), "break")[1])
        sc.bind("<Double-Button-1>", lambda _e, _s=sc, _m=md: _s.set(float(_m)))
        self._o_keo += [sc, lb]

        # đọc lại chính biến đó, không giữ giá trị chụp lúc dựng
        tid = bien.trace_add("write", lambda *_a, _v=bien, _l=lb: self._muc_doi(_l, _v))
        self._vet_keo.append((bien, tid))
        self._ghi_so(lb, bien)
        if nh:
            self._mo_hang(sc, lb, self.v_bat_rieng[(nh, ten)].get())
            self._sc_theo[(nh, ten)] = (sc, lb)
        return i + 1

    def _lam_tron(self, bien, gt):
        """Mức là số nguyên 0–100 — kéo chuột không đẻ ra 63,2847."""
        try:
            v = round(float(gt))
            if float(bien.get()) != v:
                bien.set(v)
        except (tk.TclError, ValueError):
            pass

    def _ghi_so(self, lb, bien):
        try:
            lb.configure(text=f"{float(bien.get()):.0f}")
        except (tk.TclError, ValueError):
            pass
        self._hen_tom_tat()

    def _muc_doi(self, lb, bien):
        """Một thanh vừa đổi số. NGƯỜI kéo (không phải lúc nạp mức của tấm vừa
        chọn) -> thành mức của ảnh đang xem, và ảnh lớn tính lại."""
        self._ghi_so(lb, bien)
        if not self._dang_nap_muc:
            self._nguoi_doi_muc()

    def _nguoi_doi_muc(self):
        """Người dùng vừa đổi mức trên bảng: (1) ghi thành mức của ẢNH ĐANG
        XEM — chưa có ảnh nào thì là mức chung; (2) ảnh lớn tính lại theo mức
        đó, chưa bật xem trước thì TỰ BẬT (không còn nút "Xem trước")."""
        self._ghi_muc_dang()
        #[[ Nguoi dung da KEO: xem truoc tu day la cua nguoi dung (giu bat khi
        #   sang tam khac), khong con la "tu bat theo tam" nua. ]]
        self._xem_tu_dong = False
        if self._xem_bat:
            self._hen_tinh_xem()
        elif self._anh_dang:
            self._mo_xem_truoc(tu_dong=True)

    def _mo_hang(self, sc, lb, bat: bool):
        """Chưa tick “riêng” thì thanh kéo mờ đi và không kéo được.

        #[[ De keo duoc ma khong co tac dung la kieu giao dien noi doi: nguoi
        #   dung keo, thay so doi, tuong da dat xong — roi chay ra ket qua y
        #   nhu cu. ]]
        """
        st = "normal" if bat else "disabled"
        try:
            sc.configure(state=st)
            lb.configure(foreground=gd.MAU["chu"] if bat else gd.MAU["mo2"])
        except tk.TclError:
            pass

    def _doi_bat_rieng(self, k):
        o = self._sc_theo.get(k)
        if o:
            self._mo_hang(o[0], o[1], self.v_bat_rieng[k].get())
        if not self._dang_nap_muc and self.v_bat_rieng[k].get():
            self._chung_ve_0_khi_rieng(k)
        self._danh_dau_the()
        if not self._dang_nap_muc:
            self._nguoi_doi_muc()

    def _ten_theo_nhom(self) -> set:
        """Tính năng chia được theo nhóm mặt (có thanh ở thẻ giới tính)."""
        goc = self._goc_hien()
        return {t for t, *_x in self._ds_keo if self.rt.theo_nhom(t, goc)}

    def _chung_ve_0_khi_rieng(self, k):
        """Bật “riêng” ĐẦU TIÊN cho một nhóm mặt -> mức CHUNG của ảnh về 0.

        #[[ 6/10 — user: "Buc nao chon gioi tinh rieng de chinh sua rieng thi
        #   mac dinh su dung thong so cua cac gioi tinh. Muc Chung se dua thong
        #   so ve 0." Truoc day muc chung VAN AP cho moi khuon mat khong dat
        #   rieng (ca tinh nang nhom do chua bat rieng) — dat rieng cho Nu ma Nam
        #   van bi lam min theo muc chung. Chi lam O LAN BAT DAU (chua nhom nao
        #   bat rieng): sau do nguoi dung tu keo lai muc chung thi la y ho — luc
        #   Chay retouch se hoi dung Chung hay Rieng (xem start). Tinh nang
        #   khong chia nhom (keo dai chan...) khong co the gioi tinh nen GIU muc
        #   chung. Thanh rieng vua bat lay so cua muc chung truoc khi ve 0. ]]
        """
        if any(v.get() for kk, v in self.v_bat_rieng.items() if kk != k):
            return
        nhom_duoc = self._ten_theo_nhom()
        doi = []
        self._dang_nap_muc = True
        try:
            rv = self.v_rieng.get(k)
            cv = self.v_muc.get(k[1])
            if rv is not None and cv is not None and float(rv.get()) == 0.0:
                rv.set(float(cv.get()))
            for ten, v in self.v_muc.items():
                if ten in nhom_duoc and float(v.get()) != 0.0:
                    v.set(0.0)
                    doi.append(ten)
        except (tk.TclError, ValueError):
            pass
        finally:
            self._dang_nap_muc = False
        if doi:
            p = self._anh_dang
            self._append(f"… {Path(p).name if p else 'Cả thư mục'}: đặt riêng theo "
                         "nhóm mặt — các thanh ở thẻ Chung về 0 (chỉ nhóm đặt "
                         "riêng được retouch)")
            self.app.status("Đã đưa mức Chung về 0 — ảnh này dùng mức riêng theo "
                            "giới tính", gd.MAU["xong"])

    def _dung_the_nhom(self, goc):
        """Thẻ nhóm: Chung + từng nhóm khuôn mặt, thành hàng viên chọn — ba
        viên một hàng (bảng điều khiển hẹp, sáu viên một hàng là cắt chữ).

        #[[ Chi dung lai khi DANH SACH NHOM doi. Doi the ma huy luon hang vien
        #   chon la huy chinh widget dang chay do su kien bam cua no. ]]
        """
        ds = [("", "Chung")] + [tuple(x) for x in self.rt.nhom_mat(goc)]
        if ds != self._ds_the or not getattr(self, "_pd_the", None):
            for w in self._o_the_nhom:
                try:
                    w.destroy()
                except Exception:                            # noqa: BLE001
                    pass
            self._o_the_nhom = []
            self._ds_the = ds
            self._pd_the = []
            n = self.MOI_HANG_THE
            for i in range(0, len(ds), n):
                pd = gd.PhanDoan(self.o_the, self.v_nhom, ds[i:i + n],
                                 command=lambda: self.doi_nhom(self.v_nhom.get()))
                pd.pack(fill="x", pady=(0, 4))
                self._pd_the.append(pd)
                self._o_the_nhom.append(pd)
            self.lbl_the = ttk.Label(self.o_the, style="Mo2.TLabel", text="",
                                     wraplength=300, justify="left")
            self.lbl_the.pack(anchor="w", fill="x", pady=(0, 2))
            self._o_the_nhom.append(self.lbl_the)
        if self.v_nhom.get() != self.nhom_dang:
            self.v_nhom.set(self.nhom_dang)
        self._danh_dau_the()

    def _danh_dau_the(self):
        """Thẻ đang chọn nổi lên (viên chọn tự lo); thẻ có mức riêng mang dấu ·."""
        if not getattr(self, "_pd_the", None):
            return
        co = {nh for (nh, _t), v in self.v_bat_rieng.items() if v.get()}
        n = self.MOI_HANG_THE
        for j, pd in enumerate(self._pd_the):
            phan = self._ds_the[n * j:n * j + n]
            pd.dat_lua_chon([(ma, (nhan + " ·") if ma and ma in co else nhan)
                             for ma, nhan in phan])
        if hasattr(self, "lbl_the"):
            self.lbl_the.configure(
                text="Mức dùng cho mọi nhóm không đặt riêng · 0 = tắt hẳn tính năng"
                     if not self.nhom_dang
                else "Chỉ áp cho nhóm này; tính năng chưa bật “riêng” thì theo "
                     "mức chung")
        self._hen_tom_tat()

    def doi_nhom(self, ma: str):
        self.nhom_dang = ma
        if self.v_nhom.get() != ma:
            self.v_nhom.set(ma)
        self._dung_lai_thanh_keo(self.v_goc.get().strip().strip('"'))

    def muc_day_du(self) -> dict:
        """Bảng mức phẳng: mức chung + mọi mức riêng theo nhóm.

        Đúng định dạng saytool dùng ({"vet": 100, "nam:vet": 40}), nên retouch.json
        cũ vẫn đọc được và chỗ nào không quan tâm đến nhóm cứ đọc khoá chung.
        """
        d = {k: v.get() for k, v in self.v_muc.items()}
        for (nh, ten), bat in self.v_bat_rieng.items():
            if bat.get() and ten in self.v_muc:
                d[f"{nh}:{ten}"] = self.v_rieng[(nh, ten)].get()
        return d

    # ------------------------------------------------------------ mức riêng từng ảnh
    #[[ MUC RIENG TUNG ANH + SYNC (sang 4/10 — user: "can them nut Sync All cac
    #   hieu ung da keo cho cac anh duoc chon hoac tat ca").
    #
    #   Bang thanh keo hien MUC CUA ANH DANG XEM. Keo = chinh anh do (luu vao
    #   _muc_anh, theo khoa rt.khoa_anh, ghi ra file rieng cua thu muc vao —
    #   rt.ghi_muc_anh). Anh khong co muc rieng thi theo MUC CHUNG (cf "muc").
    #   Muc rieng ma trung muc chung thi KHONG giu (bo khoi _muc_anh) — dau
    #   "riêng" tren dai anh chi hien khi that su khac. ]]
    def _goc_hien(self) -> str:
        return self.v_goc.get().strip().strip('"')

    def _vao_hien(self) -> str:
        return self.v_vao.get().strip().strip('"')

    def _khoa(self, p) -> str:
        return self.rt.khoa_anh(p, self._vao_hien(), bool(self.v_dequy.get()))

    def _muc_chung_day_du(self) -> dict:
        """Mức CHUNG (retouch.json "muc") đủ mọi tính năng tool đang có, dạng
        muc_day_du(): tính năng chưa có mức thì lấy mặc định của tool; mức
        riêng theo nhóm chỉ giữ cái tool còn có."""
        cf = self._muc_chung_tm or {}          # muc chung CUA THU MUC VAO dang mo
        ten_co = {t for t, *_x in self._ds_keo}
        #[[ MOI PROJECT = 0 HET (user 5/10, nhu Evoto): thu muc chua luu muc
        #   bao gio thi MOI thanh = 0, nguoi dung tu keo tinh nang muon dung.
        #   KHONG lay mac_dinh cua buoc (vet/min_da... mac_dinh 100) lam gia tri
        #   ban dau nua — gio 0 = tat, nguoi dung chu dong bat. Anh / thu muc DA
        #   luu muc cu van giu nguyen (cf.get(ten) co gia tri thi dung gia tri do). ]]
        d = {ten: _so_muc(cf.get(ten), 0) for ten, _n, _md, _g in self._ds_keo}
        #[[ Nhom mat lay tu ban da hoi luc dung bang (_nhom_ds), KHONG goi
        #   rt.nhom_mat(None) o day: ham nay chay moi nhip keo, ma nhom_mat(None)
        #   di do tim tool tren dia. ]]
        ma_nhom = {n for n, _l in self._nhom_ds}
        for k, v in cf.items():
            nh, co, ten = str(k).partition(":")
            if co and ten in ten_co and nh in ma_nhom and v not in (None, ""):
                d[str(k)] = _so_muc(v, 0)
        return d

    def _muc_hieu_luc(self, p) -> dict:
        """Bộ mức THẬT SỰ áp cho một ảnh: mức riêng của nó, không thì mức chung.
        Tính năng mức riêng chưa có (tool vừa thêm) thì theo mức chung — nhưng
        mức riêng theo NHÓM MẶT thì không: bộ riêng đã nói đủ nhóm nào riêng."""
        chung = self._muc_chung_day_du()
        rieng = self._muc_anh.get(self._khoa(p)) if p else None
        if rieng is None:
            return chung
        d = {k: v for k, v in chung.items() if ":" not in str(k)}
        d.update(rieng)
        return d

    def _muc_hien_tai(self) -> dict:
        return self._muc_hieu_luc(self._anh_dang) if self._anh_dang \
            else self._muc_chung_day_du()

    def _loc_muc(self, d: dict) -> dict:
        """Bỏ khoá của tính năng tool KHÔNG còn có (để gom nhóm lúc chạy không
        tách hai nhóm chỉ vì một khoá cũ). Bảng thanh kéo chưa phải của tool
        thật (bản dự phòng) thì không lọc — không đoán."""
        if not self._goc_hien() or not self.rt.da_hoi_that(self._goc_hien()):
            return dict(d)
        ten_co = {t for t, *_x in self._ds_keo}
        ma_nhom = {n for n, _l in self._nhom_ds}
        ra = {}
        for k, v in d.items():
            nh, co, ten = str(k).partition(":")
            if (not co and k in ten_co) or (co and ten in ten_co and nh in ma_nhom):
                ra[k] = v
        return ra

    def _nap_muc_vao_bang(self, muc: dict):
        """Đặt bảng thanh kéo theo một bộ mức (mức của tấm vừa chọn) — KHÔNG
        tính là người kéo: không ghi đè mức của ai, không tính lại ảnh lớn."""
        md_cua = {t: md for t, _n, md, _g in self._ds_keo}
        self._dang_nap_muc = True
        try:
            for ten, v in self.v_muc.items():
                gt = _so_muc(muc.get(ten), md_cua.get(ten, 0))
                try:
                    if float(v.get()) != gt:
                        v.set(gt)
                except (tk.TclError, ValueError):
                    v.set(gt)
            for (nh, ten), bat in self.v_bat_rieng.items():
                k = f"{nh}:{ten}"
                co = ten in md_cua and muc.get(k) not in (None, "")
                gt = _so_muc(muc.get(k), _so_muc(muc.get(ten), md_cua.get(ten, 0)))
                if bool(bat.get()) != co:
                    bat.set(co)
                rv = self.v_rieng.get((nh, ten))
                if rv is not None and float(rv.get()) != gt:
                    rv.set(gt)
                o = self._sc_theo.get((nh, ten))
                if o:
                    self._mo_hang(o[0], o[1], co)
        finally:
            self._dang_nap_muc = False
        self._danh_dau_the()
        self._hen_tom_tat()

    def _ghi_muc_dang(self):
        """Mức trên bảng -> mức của ảnh đang xem (hoặc mức chung khi chưa có
        ảnh). Trùng mức chung thì ảnh đó KHÔNG giữ mức riêng."""
        d = self.muc_day_du()
        p = self._anh_dang
        if not p:
            self._muc_chung_tm = dict(d)
            self._muc_chung_ban = True
        else:
            k = self._khoa(p)
            if self.rt.giong_muc(d, self._muc_chung_day_du()):
                self._muc_anh.pop(k, None)
            else:
                self._muc_anh[k] = dict(d)
            self._cap_nhat_dau_rieng(p)
        self._hen_luu_muc()
        self._cap_nhat_pham_vi()

    def _hen_luu_muc(self):
        """Ghi xuống đĩa SAU khi ngừng tay 0,6 s (kéo thanh là hàng chục lần
        đổi số một giây)."""
        if self._hen_luu_ma is not None:
            try:
                self.after_cancel(self._hen_luu_ma)
            except tk.TclError:
                pass
        try:
            self._hen_luu_ma = self.after(600, self._luu_muc)
        except tk.TclError:
            self._hen_luu_ma = None

    def _luu_muc(self):
        if self._hen_luu_ma is not None:
            try:
                self.after_cancel(self._hen_luu_ma)
            except tk.TclError:
                pass
        self._hen_luu_ma = None
        #[[ Muc rieng tung anh + MUC CHUNG cung nam o file cua thu muc vao
        #   (khong ghi muc chung vao retouch.json nua — xem _muc_chung_tm). ]]
        self._muc_chung_ban = False
        if self._muc_anh_vao:
            try:
                self.rt.ghi_muc_anh(self._muc_anh_vao, self._muc_anh,
                                    dict(self._muc_chung_tm))
            except OSError as ex:
                self._append(f"! không ghi được mức của thư mục này: {ex}")

    def _doi_bang_muc_anh(self, vao: str):
        """Đổi thư mục vào: ghi nốt mức riêng của thư mục cũ, đọc của thư mục
        mới (mỗi thư mục vào một bảng — tên ảnh hai buổi có thể trùng nhau)."""
        k = os.path.normcase(os.path.abspath(vao)) if vao else None
        if k == self._muc_anh_khoa:
            return
        if self._hen_luu_ma is not None:
            self._luu_muc()
        self._muc_anh_khoa = k
        self._muc_anh_vao = vao or None
        try:
            self._muc_anh = self.rt.doc_muc_anh(vao) if vao else {}
        except Exception:                                    # noqa: BLE001
            self._muc_anh = {}
        #[[ Muc chung CUA THU MUC NAY — thu muc moi chua co -> {} -> moi thanh 0. ]]
        try:
            self._muc_chung_tm = self.rt.doc_muc_chung(vao) if vao else {}
        except Exception:                                    # noqa: BLE001
            self._muc_chung_tm = {}

    def _cap_nhat_dau_rieng(self, p=None):
        """Nhãn "riêng" trên dải ảnh theo _muc_anh (p: chỉ một tấm)."""
        luoi = getattr(self, "luoi", None)
        if luoi is None:
            return
        doi = False
        for o in luoi.ds:
            if p is not None and o["path"] != p:
                continue
            r = self._khoa(o["path"]) in self._muc_anh
            if bool(o.get("rieng")) != r:
                o["rieng"] = r
                doi = True
        if doi:
            luoi._ve()
        self._hen_tom_tat()

    def _cap_nhat_pham_vi(self):
        """Dòng “đang chỉnh ảnh nào” + hai nút Sync, theo tấm đang xem và số
        tấm đang chọn ở dải ảnh."""
        if not hasattr(self, "lbl_pham_vi"):
            return
        p = self._anh_dang
        rieng = bool(p) and self._khoa(p) in self._muc_anh
        if not p:
            chu = "Chưa có ảnh — đang đặt MỨC CHUNG cho mọi ảnh."
        else:
            chu = f"{Path(p).name} · " + ("mức riêng của ảnh này" if rieng
                                          else "theo mức chung")
        n = len(self.luoi.ds_chon()) if p else 0
        #[[ Ham nay chay MOI nhip keo thanh — chi ve lai khi co gi doi (nut bo
        #   tron ve lai la dung lai anh nen). ]]
        moi = (chu, rieng, n, bool(p and self._muc_anh))
        if moi == getattr(self, "_pham_vi_cu", None):
            return
        self._pham_vi_cu = moi
        try:
            self.lbl_pham_vi.configure(text=chu, foreground=gd.MAU["nhan"] if rieng
                                       else gd.MAU["mo"])
        except tk.TclError:
            return
        self.btn_sync_chon.configure(
            text=f"Sync ảnh đã chọn ({n})" if n > 1 else "Sync ảnh đã chọn",
            state="normal" if n > 1 else "disabled")
        #[[ Reset ve 0: bat khi co anh dang xem (reset chinh anh do). ]]
        if hasattr(self, "btn_reset"):
            self.btn_reset.configure(state="normal" if p else "disabled")

    def _mo_ta_muc(self, muc: dict, toi_da: int = 4) -> str:
        """“Xoá khuyết điểm 60 · Làm mịn da 40 · riêng Nam: Làm thon mặt 30”."""
        nhan = {t: n for t, n, *_x in self._ds_keo}
        ten_nhom = dict(self._nhom_ds)
        chung, rieng = [], []
        for k, v in muc.items():
            gt = _so_muc(v, 0)
            nh, co, ten = str(k).partition(":")
            if not co and gt > 0:
                chung.append(f"{nhan.get(k, k)} {gt:.0f}")
            elif co:
                rieng.append(f"{ten_nhom.get(nh, nh)}: {nhan.get(ten, ten)} {gt:.0f}")
        ra = " · ".join(chung[:toi_da]) + (" …" if len(chung) > toi_da else "")
        if not chung:
            ra = "mọi tính năng ở 0"
        if rieng:
            ra += " · riêng " + ", ".join(rieng[:2]) + (" …" if len(rieng) > 2 else "")
        return ra

    def _reset_anh_0(self):
        """Đưa MỌI thanh của ảnh đang xem về 0 (tắt hết tính năng), rồi tính
        lại ảnh lớn — như kéo tay nhưng một phát về 0. Muốn reset nhiều ảnh:
        Reset tấm này rồi bấm Sync ảnh đã chọn.

        #[[ Dat var duoi co _dang_nap_muc = True de moi var ve 0 KHONG tung lan
        #   goi _nguoi_doi_muc (hang chuc lan ghi + tinh lai). Xong het thi goi
        #   MOT lan _nguoi_doi_muc -> ghi muc + tinh lai preview mot luot. ]]
        """
        self._dang_nap_muc = True
        try:
            for v in self.v_muc.values():
                try:
                    if float(v.get()) != 0.0:
                        v.set(0.0)
                except (tk.TclError, ValueError):
                    v.set(0.0)
            #[[ Tat luon moi muc RIENG theo nhom (bo tick "rieng") — reset la
            #   sach, khong de sot mot nhom nao con muc. ]]
            for (nh, ten), bat in self.v_bat_rieng.items():
                if bool(bat.get()):
                    bat.set(False)
                rv = self.v_rieng.get((nh, ten))
                if rv is not None and float(rv.get()) != 0.0:
                    rv.set(0.0)
                o = self._sc_theo.get((nh, ten))
                if o:
                    self._mo_hang(o[0], o[1], False)
        finally:
            self._dang_nap_muc = False
        self._danh_dau_the()
        self._nguoi_doi_muc()
        p = self._anh_dang
        if p:
            self._append(f"… Reset {Path(p).name} về 0 (tắt hết tính năng)")

    def _sync_chon(self):
        """Chép mức của ảnh đang xem sang mọi tấm đang chọn ở dải ảnh."""
        p = self._anh_dang
        ds = [q for q in self.luoi.ds_chon() if q != p]
        if not p or not ds:
            return
        muc = self.muc_day_du()
        giong = self.rt.giong_muc(muc, self._muc_chung_day_du())
        for q in ds:
            k = self._khoa(q)
            if giong:
                self._muc_anh.pop(k, None)
            else:
                self._muc_anh[k] = dict(muc)
        self._luu_muc()
        self._cap_nhat_dau_rieng()
        self._cap_nhat_pham_vi()
        self._append(f"… Sync mức của {Path(p).name} sang {len(ds)} ảnh đã chọn: "
                     + self._mo_ta_muc(muc))
        self.app.status(f"Đã Sync mức của {Path(p).name} sang {len(ds)} ảnh đã chọn",
                        gd.MAU["xong"])

    def _sync_het(self):
        """Chép mức của ảnh đang xem cho MỌI ảnh và lấy làm mức chung."""
        p = self._anh_dang
        if not p:
            return
        muc = self.muc_day_du()
        k_dang = self._khoa(p)
        khac = [k for k, m in self._muc_anh.items()
                if k != k_dang and not self.rt.giong_muc(m, muc)]
        if khac and not messagebox.askokcancel(
                "Sync tất cả?",
                f"{len(khac)} ảnh khác đang có mức riêng của nó. “Sync tất cả” sẽ "
                f"đưa MỌI ảnh về đúng mức của {Path(p).name}:\n\n"
                f"   {self._mo_ta_muc(muc, 8)}\n\n"
                "Mức riêng của những ảnh đó mất đi. Tiếp tục?", parent=self):
            return
        self._muc_chung_tm = dict(muc)
        self._muc_chung_ban = True
        self._muc_anh.clear()
        self._luu_muc()
        self._cap_nhat_dau_rieng()
        self._cap_nhat_pham_vi()
        n = len(self.luoi.ds)
        self._append(f"… Sync tất cả ({n} ảnh) theo mức của {Path(p).name}: "
                     + self._mo_ta_muc(muc))
        self.app.status(f"Đã Sync mức của {Path(p).name} cho cả {n} ảnh",
                        gd.MAU["xong"])

    def _ve_muc_chung(self):
        """Ảnh đang xem bỏ mức riêng, theo lại mức chung."""
        p = self._anh_dang
        if not p:
            return
        self._muc_anh.pop(self._khoa(p), None)
        self._luu_muc()
        self._nap_muc_vao_bang(self._muc_hieu_luc(p))
        self._cap_nhat_dau_rieng(p)
        self._cap_nhat_pham_vi()
        if self._xem_bat:
            self._hen_tinh_xem()

    def _dung_lai_thanh_keo(self, goc):
        """Dựng lại bảng thanh kéo (đổi thẻ nhóm, đổi tool, tool vừa trả lời)."""
        self._hang_keo = self._dung_thanh_keo(goc)
        self._canh_bao_keo(goc)

    def _canh_bao_keo(self, goc):
        """Nói ra khi bảng thanh kéo chỉ là bản dự phòng, và nói rõ vì sao."""
        if not hasattr(self, "lbl_keo"):
            return
        if not self._keo_dang_hoi and not self.rt.hop_le(goc):
            #[[ Chua co tool dung duoc thi dai bao tren luoi ("Chua dung duoc
            #   tool retouch — …") da noi NGUYEN NHAN; bang du phong chi la he
            #   qua. Noi them o day la hai canh bao cho mot chuyen. Canh bao
            #   nay danh cho truong hop co tool ma HOI KHONG DUOC (9/9). ]]
            self._hien_an(self.o_canh_keo, False)
            return
        if self._keo_dang_hoi:
            self.lbl_keo.configure(
                text="Đang hỏi tool xem nó có những tính năng nào… "
                     "(lần đầu phải nạp torch nên có thể mất một phút)")
            self._hien_an(self.btn_keo_lai, False)
            self._hien_an(self.o_canh_keo, True)
            return
        if self.rt.da_hoi_that(goc):
            self._hien_an(self.o_canh_keo, False)
            return
        vi_sao = self.rt.loi_hoi_keo(goc)
        self.lbl_keo.configure(
            text="Đang hiện bảng DỰ PHÒNG, không phải tính năng thật của tool. "
                 + (f"Vì: {vi_sao.splitlines()[0]}" if vi_sao
                    else "Chưa hỏi được tool.")
                 + "  Bấm “Đọc lại tính năng” để thử lại; chi tiết in ở Nhật ký.")
        self._hien_an(self.btn_keo_lai, True)
        self._hien_an(self.o_canh_keo, True)
        if vi_sao:
            for d in vi_sao.splitlines():
                self._append("   " + d)

    def do_doc_lai_keo(self):
        """Hỏi lại tool — chạy ở luồng nền, vì lần hỏi có thể tới 180 giây."""
        goc = self.v_goc.get().strip().strip('"')
        if not self.rt.hop_le(goc):
            self._append("! chưa chọn đúng thư mục tool, không hỏi được")
            return
        self._hoi_keo_nen(goc, ep=True)

    def _hoi_keo_nen(self, goc, ep: bool = False):
        #[[ PHAI CHAY O LUONG NEN.
        #
        #   rt.thanh_keo() mo mot tien trinh con nap torch — do duoc la hang
        #   chuc giay, toi da 180. Goi thang tren luong giao dien la Tk dung
        #   hinh dung nhu treo, va nguoi dung se tat app giua chung.
        #]]
        if self._keo_dang_hoi:
            return
        if not ep and self.rt.da_hoi_that(goc):
            return
        self._keo_dang_hoi = True
        self._canh_bao_keo(goc)
        if ep:
            self.rt.quen_thanh_keo(goc)
            self._append("… đang hỏi lại tool xem có những tính năng nào")

        def work():
            try:
                self.rt.thanh_keo(goc, lam_lai=True)
            except Exception:                                # noqa: BLE001
                pass
            self.log_q.put(("keo", goc))

        threading.Thread(target=work, daemon=True).start()
