#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""thanh_luoi.py — Thanh trên lưới ảnh: lọc theo sao + cỡ ô (9/10).

User 9/10 (gửi mẫu giao diện): "Tuỳ chọn được lưới xem ảnh to hay nhỏ", bộ lọc dải
ảnh "Tất cả / Chưa gắn sao / Đã lọc (có sao)" — khớp tuỳ chọn Xuất "Chỉ xuất ảnh
chưa gắn sao" (ảnh có sao = ảnh đã lọc). Dùng chung cho lưới Cân tone và Retouch;
cỡ ô nhớ chung một chỗ (<dữ liệu app>/luoi_xem.json).

    ThanhLuoi(cha, khi_loc(loc), khi_co(px))   loc: "tat_ca" | "chua_sao" | "co_sao"
    .dat_so(tat_ca, chua_sao, co_sao)          số trên ba viên lọc
    loc_ds(ds, loc)                            lọc danh sách ô (o["sao"])
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import tkinter as tk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import duong_dan as dd
import giao_dien as gd

TEN_TEP = "luoi_xem.json"


def _doc() -> dict:
    try:
        d = json.loads(dd.du_lieu(TEN_TEP).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def doc_kv(k: str, md=None):
    return _doc().get(k, md)


def ghi_kv(k: str, v) -> None:
    d = _doc()
    d[k] = v
    try:
        dd.ghi_ben(dd.du_lieu(TEN_TEP), json.dumps(d, ensure_ascii=False))
    except OSError:
        pass


def doc_co_o(md: int) -> int:
    try:
        return int(doc_kv("co_o") or md)
    except (TypeError, ValueError):
        return md


def ghi_co_o(px: int) -> None:
    ghi_kv("co_o", int(px))


def sao_cua(o: dict) -> int:
    try:
        return int(o.get("sao") or (1 if o.get("sao1") else 0) or 0)
    except (TypeError, ValueError):
        return 0


def loc_ds(ds: list, loc: str) -> list:
    if loc == "chua_sao":
        return [o for o in ds if sao_cua(o) <= 0]
    if loc == "co_sao":
        return [o for o in ds if sao_cua(o) >= 1]
    return list(ds)


def dem(ds: list) -> tuple:
    co = sum(1 for o in ds if sao_cua(o) >= 1)
    return len(ds), len(ds) - co, co


class ThanhLuoi(tk.Frame):
    """[Tất cả N | Chưa gắn sao N | Đã lọc N] ··········· ▫ ━━━●━━ ▣"""

    def __init__(self, cha, khi_loc=None, khi_co=None, nen: str | None = None,
                 co_md: int = 160):
        self._nen = nen or gd.MAU["toi"]
        super().__init__(cha, background=self._nen)
        self._khi_loc = khi_loc
        self._khi_co = khi_co
        self.v_loc = tk.StringVar(value="tat_ca")
        self.pd_loc = gd.PhanDoan(self, self.v_loc, self._nhan_loc(0, 0, 0),
                                  command=self._doi_loc, nen=self._nen, deu=False)
        self.pd_loc.pack(side="left")
        lh = gd.don_vi(self)
        self.v_co = tk.DoubleVar(value=float(doc_co_o(co_md)))
        o = tk.Frame(self, background=self._nen)
        o.pack(side="right")
        nho = tk.Canvas(o, width=lh, height=lh, background=self._nen, highlightthickness=0)
        nho.tu_cuon = False
        gd.ve_bieu_tuong(nho, "luoi", lh / 2, lh / 2, lh * 0.62, gd.MAU["mo"])
        nho.pack(side="left", padx=(0, 6))
        self.tr_co = gd.Truot(o, from_=round(lh * 5.5), to=round(lh * 30),
                              variable=self.v_co, command=self._doi_co,
                              length=round(lh * 9), nen=self._nen)
        self.tr_co.pack(side="left")
        to = tk.Canvas(o, width=lh + 4, height=lh + 4, background=self._nen,
                       highlightthickness=0)
        to.tu_cuon = False
        gd.ve_bieu_tuong(to, "anh", (lh + 4) / 2, (lh + 4) / 2, lh * 0.9, gd.MAU["mo"])
        to.pack(side="left", padx=(6, 0))
        self._hen = None

    @staticmethod
    def _nhan_loc(n, chua, co):
        return [("tat_ca", f"Tất cả  {n}"), ("chua_sao", f"Chưa gắn sao  {chua}"),
                ("co_sao", f"Đã lọc (có sao)  {co}")]

    def dat_so(self, n: int, chua: int, co: int) -> None:
        try:
            self.pd_loc.dat_lua_chon(self._nhan_loc(n, chua, co))
        except Exception:                                    # noqa: BLE001
            pass

    @property
    def loc(self) -> str:
        return self.v_loc.get()

    def co_o(self) -> int:
        try:
            return int(float(self.v_co.get()))
        except (tk.TclError, ValueError):
            return 160

    def _doi_loc(self):
        if self._khi_loc is not None:
            self._khi_loc(self.v_loc.get())

    def _doi_co(self, _v=None):
        px = self.co_o()
        if self._khi_co is not None:
            self._khi_co(px)
        #  ghi xuống đĩa khi ngừng kéo 0,5 s
        if self._hen is not None:
            try:
                self.after_cancel(self._hen)
            except tk.TclError:
                pass
        try:
            self._hen = self.after(500, lambda: ghi_co_o(self.co_o()))
        except tk.TclError:
            self._hen = None
