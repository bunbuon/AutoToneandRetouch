#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kiem_ban_xuat.py — Kiểm app có ĐỌC LẠI bản xuất từ Lightroom hay không.

    python kiem_ban_xuat.py

LỖI NÀY LÀ GÌ
    Thứ tự thao tác tự nhiên: mở app → chọn thư mục → sang Lightroom xuất →
    quay lại bấm Phân tích. Bản cũ đọc bản xuất ĐÚNG MỘT LẦN, ngay lúc chọn thư
    mục — tức lúc chưa hề có bản xuất cho buổi này. Và plugin Lightroom thì
    "chỉ giữ lại bản mới nhất cho đỡ rác" (cleanupExports trong
    ExportForAutoTone.lua), nên cái app đọc được là bản xuất của BUỔI TRƯỚC.

    Hỏng thật 4/9: buổi G:\\0608 có 96 ảnh, plugin xuất đúng 96 dòng đúng đường
    dẫn G:\\0608\\..., app vẫn báo "bản xuất chỉ khớp 0 ảnh". App đang so với
    bản xuất của buổi 2905 hôm trước — khớp 0 là đúng, chỉ là so nhầm file.

    Nặng hơn cái nhãn sai: at.plan() nhận chính self.export đó, nên bấm Phân
    tích là TÍNH trên bản xuất cũ thật sự.

BÀI KIỂM NÀY DỰNG LẠI ĐÚNG TÌNH HUỐNG ĐÓ
    Không mở cửa sổ (chạy được trên máy không màn hình): gọi thẳng hàm THẬT
    _doc_xuat / _dem_khop của App trên một App giả chỉ có đúng những thuộc tính
    hai hàm đó cần. Không dựng lại một bản logic nào — kiểm cái app chạy, chứ
    không kiểm một bản chép lại của nó.
"""
from __future__ import annotations


import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at   # noqa: E402


class AppGia:
    """Chỉ đủ để chạy ba hàm thật của App. Không dựng lại logic nào cả."""

    def __init__(self, pairs):
        self.pairs = pairs
        self.export = {}
        self.nhan = ""
        self.mau = ""

    # ba hàm dưới đây là BẢN SAO THAM CHIẾU tới hàm thật của App — gán ở dưới
    def _cau_hinh_nhan(self, text, foreground=None):
        self.nhan, self.mau = text, foreground


#[[ DUNG DUNG os.path MA APP DUNG, khong dung ntpath cho "giong Windows hon".
#
#   Da thu ntpath va SAI: _read_tsv() ben trong autotone.py chuan hoa khoa bang
#   os.path, nen tren Linux khoa la duong dan kieu posix. Bai kiem lai tra bang
#   ntpath thi hai ben chuan hoa hai kieu, ra "khop 0/96" — mot cai HONG do
#   chinh bai kiem tu tao ra, khong phai loi cua app.
#
#   Hai ben cung mot ham thi phep kiem nay do dung cai no dinh do: APP CO DOC
#   LAI BAN XUAT KHONG. Con chuyen hoa/thuong va dau gach cua duong dan Windows
#   thi chi may Windows that moi tra loi duoc — va o do os.path CHINH LA ntpath.
#]]
def _chuan(s: str) -> str:
    import os
    return os.path.normcase(os.path.abspath(s))


def viet_xuat(d: Path, ten: str, duong_dan: list) -> Path:
    p = d / ten
    dong = ["path\tExposure2012\tHighlights2012\tShadows2012\tTemperature\tTint"]
    dong += [f"{x}\t0\t16\t16\t5250\t16" for x in duong_dan]
    p.write_text("\r\n".join(dong) + "\r\n", encoding="utf-8")
    return p


def main() -> int:
    loi = []
    with tempfile.TemporaryDirectory() as t:
        jobs = Path(t) / "jobs"
        jobs.mkdir()

        cu = [f"G:\\2905\\OLD{i:05d}.ARW" for i in range(220)]
        moi = [f"G:\\0608\\DSC{i:05d}.ARW" for i in range(96)]

        #[[ pairs cua buoi 0608 — dung dang (raw, sidecar) nhu collect_pairs tra ve.
        #]]
        pairs = [(x, None) for x in moi]

        # ── 1. Đọc bản xuất CŨ (buổi khác) -> phải khớp 0 ────────────────────
        viet_xuat(jobs, "export_20260903_105234.tsv", cu)
        ex = at.read_catalog_export(at.latest_catalog_export(jobs))
        khop = sum(1 for p, _ in pairs if _chuan(str(p)) in ex)
        if not ex:
            loi.append("Doc ban xuat cu ma ra rong — bai kiem hong, khong phai app")
        if khop != 0:
            loi.append(f"Ban xuat cua buoi khac ma khop {khop} anh")

        #[[ 2. PLUGIN XOA BAN CU roi ghi ban moi — dung nhu cleanupExports lam.
        #   Ghi de len cung thu muc chu khong them file, vi neu chi them thi
        #   latest_catalog_export() van co the vo phai ban cu do no sort theo TEN.
        #]]
        time.sleep(0.01)
        for f in jobs.glob("export_*.tsv"):
            f.unlink()
        moi_p = viet_xuat(jobs, "export_20260904_100640.tsv", moi)

        # ── 3. latest_catalog_export phải trỏ vào bản mới ────────────────────
        lay = at.latest_catalog_export(jobs)
        if lay is None or lay.name != moi_p.name:
            loi.append(f"latest_catalog_export tra ve {lay} thay vi {moi_p.name}")

        # ── 4. Đọc lại thì phải khớp đủ 96 ───────────────────────────────────
        ex2 = at.read_catalog_export(lay)
        khop2 = sum(1 for p, _ in pairs if _chuan(str(p)) in ex2)
        if khop2 != len(moi):
            loi.append(f"Doc lai ban xuat moi ma chi khop {khop2}/{len(moi)} anh "
                       f"— duong dan trong file va duong dan app quet khong khop nhau")

        #[[ 5. DAY MOI LA PHEP KIEM CHINH: app co NHAN RA ban xuat da doi khong.
        #   Phep 1-4 chi chung minh doc file thi dung. Cai hong that su la app
        #   khong bao gio doc lai. Nen kiem thang _doc_xuat(): lan dau phai bao
        #   "co doi", doc lai ngay sau do phai bao "khong doi" (khong lang phi),
        #   va sau khi file bi thay thi lai phai bao "co doi".
        #]]
        import autotone_gui as ag

        app = AppGia(pairs)
        cu_job = at.LR_JOB_DIR
        try:
            at.LR_JOB_DIR = jobs           # tro ham that vao thu muc tam
            for f in jobs.glob("export_*.tsv"):
                f.unlink()
            viet_xuat(jobs, "export_20260903_105234.tsv", cu)

            if not ag.App._doc_xuat(app):
                loi.append("Lan doc dau tien ma bao 'khong doi'")
            n1 = ag.App._dem_khop(app)
            if n1 != 0:
                loi.append(f"Ban cu ma khop {n1}")

            if ag.App._doc_xuat(app):
                loi.append("Doc lai khi file KHONG doi ma van bao 'co doi' — "
                           "se lam dong ho 3 giay ve lai bang lien tuc")

            # người dùng sang Lightroom xuất
            time.sleep(0.01)
            for f in jobs.glob("export_*.tsv"):
                f.unlink()
            viet_xuat(jobs, "export_20260904_100640.tsv", moi)

            if not ag.App._doc_xuat(app):
                loi.append("BAN XUAT DA DOI MA APP KHONG NHAN RA — dung cai loi "
                           "ngay 4/9: nguoi dung xuat xong roi ma app van bao "
                           "khop 0 anh")
            n2 = ag.App._dem_khop(app)
            if n2 != len(moi):
                loi.append(f"Sau khi doc lai chi khop {n2}/{len(moi)}")

            #[[ 6. Xoa het ban xuat -> phai ve rong, khong duoc giu ban cu trong
            #   bo nho roi tinh tiep tren no.
            #]]
            for f in jobs.glob("export_*.tsv"):
                f.unlink()
            ag.App._doc_xuat(app)
            if app.export:
                loi.append("Khong con ban xuat nao ma app van giu du lieu cu")
        finally:
            at.LR_JOB_DIR = cu_job

    for m in loi:
        print("  [!]", m)
    print("TAT CA DAT" if not loi else f"{len(loi)} LOI")
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
