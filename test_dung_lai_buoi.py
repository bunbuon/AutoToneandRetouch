#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dùng lại một buổi đã chạy qua tool — kiểm bằng hàm THẬT.

CHUYỆN ĐANG SỬA (3/10)
    Người dùng: "Khi muốn sử dụng lại 1 folder đã chạy qua tool thì catalog
    không nhận đủ ảnh hoặc không nhận được catalog". Ảnh chụp màn hình: buổi
    G:\\1009, 437 ảnh RAW, "bản xuất chỉ khớp 0 ảnh — 437 ảnh sẽ bị bỏ qua",
    đang đọc export_20261003_082531.tsv — mà file đó là 630 ảnh của G:\\1005
    (Lightroom đang mở 1005, lệnh xuất ở menu lấy theo vùng đang xem).

    Năm chỗ hỏng, mỗi chỗ một mục kiểm:
      1. App lấy bản xuất "mới nhất" bất kể của buổi nào.
      2. Nút "Xoá dữ liệu cũ" gọi một hàm không tồn tại — bấm là văng lỗi
         ngầm, không xoá gì (xem kiem_tham_chieu.py).
      3. Xoá dữ liệu thì xoá luôn bản xuất của MỌI buổi.
      4. Ảnh không có trong bản xuất vẫn bị đẩy vào Lightroom với nền 0
         (Highlights tính từ 0 thay vì 16) — trong khi giao diện bảo "bỏ qua".
      5. Khoá đường dẫn ở attach_catalog_settings dùng normcase — trên macOS
         không viết thường nên cả buổi khớp 0 ảnh.
    Kèm: phần giao diện nói đúng bệnh (ảnh 1 sao / chưa import / đang chờ
    Lightroom) — chạy khi máy có tkinter, không có thì bỏ qua và nói ra.
"""
from __future__ import annotations

import contextlib
import copy
import io
import os
import sys
import tempfile
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at          # noqa: E402
import test_2ban_quay as tq    # noqa: E402

HEADER = "path\tExposure2012\tHighlights2012\tShadows2012\tTemperature\tTint\tRating"


def ghi_xuat(jobs: Path, ten: str, duong: list, tuoi_giay: float = 0.0) -> Path:
    p = jobs / ten
    dong = [HEADER] + [f"{x}\t0\t16\t16\t5250\t16\t" for x in duong]
    p.write_text("\n".join(dong) + "\n", encoding="utf-8")
    if tuoi_giay:
        t = time.time() - tuoi_giay
        os.utime(p, (t, t))
    return p


def ghi_ket_qua(jobs: Path, **kv) -> None:
    (jobs / at.KET_QUA_XUAT).write_text(
        "".join(f"{k}={v}\n" for k, v in kv.items()), encoding="utf-8")


def anh_trong(thu_muc: Path, ten: str) -> Path:
    p = thu_muc / ten
    p.write_bytes(b"x")
    return p


def main() -> int:
    loi: list = []
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        jobs = td / "jobs"
        jobs.mkdir()
        at.LR_JOB_DIR = jobs
        x, y = td / "1009", td / "1005"
        x.mkdir(); y.mkdir(); (x / "con").mkdir()
        ax = [str(anh_trong(x, f"SAY{i:05d}.ARW")) for i in range(4)]
        ay = [str(anh_trong(y, f"SAY{i:05d}.ARW")) for i in range(6)]
        acon = [str(anh_trong(x / "con", "DSC00001.ARW"))]

        # 1. ban xuat cua DUNG thu muc, du co ban moi hon cua buoi khac
        bx = ghi_xuat(jobs, "export_20261003_080000.tsv", ax, tuoi_giay=600)
        by = ghi_xuat(jobs, "export_20261003_082531.tsv", ay, tuoi_giay=30)
        if at.latest_catalog_export() != by:
            loi.append("Dung bai: ban moi nhat phai la cua 1005 (tinh huong 3/10)")
        if at.ban_xuat_cho_thu_muc(x) != bx:
            loi.append(f"1009 phai doc ban xuat cua 1009, dang doc {at.ban_xuat_cho_thu_muc(x)}")
        if at.ban_xuat_cho_thu_muc(td / "khac") is not None:
            loi.append("Thu muc khong co ban xuat nao phai tra None")
        bcon = ghi_xuat(jobs, "export_20261003_083000.tsv", acon, tuoi_giay=5)
        if at.ban_xuat_cho_thu_muc(x) != bx:
            loi.append("Ban xuat chi co anh thu muc CON khong duoc tinh khi khong gom con")
        if at.ban_xuat_cho_thu_muc(x, gom_con=True) != bcon:
            loi.append("Gom con: ban xuat cua thu muc con moi nhat phai duoc chon")
        if at.export_stamp(thu_muc=x) != bx.stat().st_mtime:
            loi.append("export_stamp(thu_muc=) phai bo qua ban xuat cua buoi khac")
        # file doi noi dung -> phai doc lai, khong dung ket qua nho cu
        ghi_xuat(jobs, by.name, ay + ax, tuoi_giay=1)
        if at.ban_xuat_cho_thu_muc(x) != by:
            loi.append("Ban xuat doi noi dung (them anh 1009) ma van dung ket qua nho cu")
        ghi_xuat(jobs, by.name, ay, tuoi_giay=30)

        # ket qua cua plugin
        ghi_ket_qua(jobs, thu_muc=str(x), so_anh=3, bo_sao=1, file=bx.name, cach="theo thu muc")
        kq = at.ket_qua_xuat()
        if (kq.get("so_anh"), kq.get("bo_sao"), kq.get("file")) != (3, 1, bx.name):
            loi.append(f"ket_qua_xuat doc sai: {kq}")

        # 4. anh ngoai ban xuat KHONG vao job
        loi += kiem_ngoai_xuat(td, jobs)

        # 5. khoa duong dan tren macOS
        loi += kiem_mac(td)

        # 6. dung lai buoi ma anh trong Lightroom CHUA Reset: khong cong chong
        loi += kiem_cong_chong(td, jobs)

        # 7. ban xuat CUA BUOI cu hon lan ghi + ban buoi khac moi hon (3/10)
        loi += kiem_chot_xuat_cu(td, jobs)

        # GUI (neu co tkinter) — truoc muc 3 vi muc 3 xoa file
        loi += kiem_giao_dien(td, jobs, x, ax, bx)

        # 3. xoa du lieu: chi ban xuat cua buoi nay
        at.save_baseline(x, {at.khoa_duong_dan(p): {"Exposure2012": "0"} for p in ax})
        (jobs / "apply_20261003_070000_1009.done").write_text("path\tExposure2012\n", encoding="utf-8")
        (jobs / "apply_20261003_070000_1005.done").write_text("path\tExposure2012\n", encoding="utf-8")
        ghi_xuat(jobs, "export_20261003_080000.tsv", ax, tuoi_giay=600)
        ghi_xuat(jobs, "export_20261003_083000.tsv", acon, tuoi_giay=5)
        ghi_ket_qua(jobs, thu_muc=str(x), so_anh=4, file="export_20261003_080000.tsv")
        r = at.xoa_du_lieu_buoi(x, jobs, ca_ban_xuat=True)
        if (jobs / "export_20261003_080000.tsv").exists() or not by.exists():
            loi.append("Xoa du lieu 1009: phai xoa ban xuat 1009 va GIU ban xuat 1005")
        if (jobs / "export_20261003_083000.tsv").exists():
            loi.append("Xoa du lieu 1009: ban xuat thu muc con cua 1009 cung phai xoa")
        if (jobs / "apply_20261003_070000_1009.done").exists() or \
                not (jobs / "apply_20261003_070000_1005.done").exists():
            loi.append("Xoa du lieu 1009: chi xoa so ghi cua 1009")
        if not at.baseline_path(x).exists():
            loi.append("Xoa du lieu 1009: phai GIU moc goc (xoa moc + anh chua Reset = cong chong)")
        if (jobs / at.KET_QUA_XUAT).exists():
            loi.append("Xoa du lieu 1009: ket qua xuat cu cua 1009 chua bi xoa")
        if r.get("ban_xuat") != 2:
            loi.append(f"Xoa du lieu 1009: dem ban xuat da xoa = {r.get('ban_xuat')}, phai 2")
        r2 = at.xoa_du_lieu_buoi(x, jobs, xoa_moc=True)
        if at.baseline_path(x).exists() or r2.get("baseline") != 1:
            loi.append("xoa_moc=True phai xoa moc goc")
        ghi_ket_qua(jobs, thu_muc=str(y), so_anh=6, file=by.name)
        at.xoa_du_lieu_buoi(x, jobs, ca_ban_xuat=True)
        if not (jobs / at.KET_QUA_XUAT).exists():
            loi.append("Xoa du lieu 1009 khong duoc xoa ket qua xuat cua 1005")

    for m in loi:
        print("  [!]", m)
    print("TAT CA DAT" if not loi else f"{len(loi)} LOI")
    return 1 if loi else 0


def kiem_ngoai_xuat(td: Path, jobs: Path) -> list:
    """plan() that + write_lr_job that: anh khong co trong ban xuat khong vao job."""
    loi = []
    items = [tq.anh(f"N{i}", i * 8, -1.4 + 0.1 * i, da=tq.DA_TRONG) for i in range(6)]
    for r in items:
        r["path"] = str(td / "nx" / Path(r["path"].replace("\\", "/")).name)
    (td / "nx").mkdir()
    co = items[:4]
    exp = {at.khoa_duong_dan(r["path"]): dict(tq.PRESET, **{at.LR_PATH_KEY: r["path"]})
           for r in co}
    cfg = dict(at.DEFAULTS, source="catalog", bo_qua_nguoi_sua=False)
    its = copy.deepcopy(items)
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        at.plan(its, cfg, td / "nx", exp)
    ngoai = [r for r in its if r.get("ngoai_xuat")]
    if len(ngoai) != 2:
        loi.append(f"Phai co dung 2 anh ngoai ban xuat, dang {len(ngoai)}")
    job = at.write_lr_job(its, "nx", jobs / "nx")
    duong = [ln.split("\t")[0] for ln in job.read_text(encoding="utf-8").splitlines()[1:]]
    if sorted(duong) != sorted(r["path"] for r in co):
        loi.append(f"Job phai CHI co 4 anh trong ban xuat, dang co {len(duong)}")
    if not all(r.get("new_highlights") is not None for r in its if not r.get("ngoai_xuat")):
        loi.append("Anh trong ban xuat phai van duoc tinh")
    return loi


def kiem_chot_xuat_cu(td: Path, jobs: Path) -> list:
    """plan() THẬT: bản xuất của buổi chụp TRƯỚC lần tool ghi, trong khi một
    buổi KHÁC vừa xuất xong (mới hơn lần ghi). Chốt cũ lấy mtime của MỌI bản
    xuất nên im, và bước lọc "ảnh sửa tay" bỏ cả buổi — bệnh 2705 ngày 7/9,
    quay lại từ khi app đọc bản xuất theo thư mục. Đúng thứ tự thì bước lọc
    vẫn phải bắt đúng ảnh user sửa."""
    loi = []
    d = td / "cx"
    d.mkdir()
    items = [tq.anh(f"X{i}", i * 8, -1.6 + 0.05 * i, da=tq.DA_TRONG) for i in range(6)]
    for r in items:
        r["path"] = str(d / Path(r["path"].replace("\\", "/")).name)
    cfg = dict(at.DEFAULTS, source="catalog", bo_qua_nguoi_sua=True)
    tao = []

    done = jobs / "apply_20261003_100000_cx.done"          # tool ghi Exposure +0.40
    done.write_text("path\tExposure2012\n"
                    + "".join(f"{r['path']}\t0.40\n" for r in items), encoding="utf-8")
    t = time.time() - 300
    os.utime(done, (t, t))
    cu = ghi_xuat(jobs, "export_20261003_095500.tsv",       # chụp TRƯỚC lần ghi
                  [r["path"] for r in items], tuoi_giay=600)
    khac = ghi_xuat(jobs, "export_20261003_100500.tsv",     # buổi khác, SAU lần ghi
                    [str(td / "yy" / "SAY99999.ARW")], tuoi_giay=10)
    tao += [done, cu, khac]

    def chay(exp, **kw):
        its = copy.deepcopy(items)
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            at.plan(its, cfg, d, exp, **kw)
        return its

    exp_cu = at.read_catalog_export(cu)
    for nhan, kw in (("giao dien truyen file", {"ban_xuat": cu}), ("tu tim theo thu muc", {})):
        its = chay(exp_cu, **kw)
        if len(its) != 6 or at.SO_ANH_NGUOI_SUA:
            loi.append(f"Ban xuat cu hon lan ghi ({nhan}): bo {6 - len(its)}/6 anh "
                       "vi 'sua tay' — benh 2705")
        if not at.CANH_BAO_XUAT:
            loi.append(f"Ban xuat cu hon lan ghi ({nhan}): phai bao CANH_BAO_XUAT")

    moi = jobs / "export_20261003_101000.tsv"               # đúng thứ tự, 1 ảnh user sửa
    moi.write_text("\n".join([HEADER] + [
        f"{r['path']}\t{'0.90' if i == 0 else '0.40'}\t16\t16\t5250\t16\t"
        for i, r in enumerate(items)]) + "\n", encoding="utf-8")
    tao.append(moi)
    its = chay(at.read_catalog_export(moi), ban_xuat=moi)
    if at.CANH_BAO_XUAT or at.SO_ANH_NGUOI_SUA != 1 or len(its) != 5:
        loi.append(f"Ban xuat moi hon lan ghi: phai bo dung 1 anh sua tay, dang bo "
                   f"{at.SO_ANH_NGUOI_SUA} (canh bao: {bool(at.CANH_BAO_XUAT)})")
    for p in tao:
        p.unlink()
    return loi


def kiem_cong_chong(td: Path, jobs: Path) -> list:
    """Chay -> day -> Xoa du lieu cu -> chay lai tren catalog CON MANG SO CU.
    Giu moc: ra y het lan dau. Xoa moc: cong chong (chung minh vi sao giu)."""
    loi = []
    d = td / "cc"
    d.mkdir()
    items = [tq.anh(f"C{i}", i * 8, -1.9 + 0.05 * i, da=tq.DA_TRONG) for i in range(6)]
    for r in items:
        r["path"] = str(d / Path(r["path"].replace("\\", "/")).name)
    cfg = dict(at.DEFAULTS, source="catalog")

    def chay(ban_xuat):
        its = copy.deepcopy(items)
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            at.plan(its, cfg, d, ban_xuat)
        return its

    exp0 = {at.khoa_duong_dan(r["path"]): dict(tq.PRESET) for r in items}
    r1 = chay(exp0)
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        at.write_sidecars(r1, cfg, d)                 # chot moc + ghi job (vao jobs tam)
    exp1 = {at.khoa_duong_dan(r["path"]): {
        "Exposure2012": str(r["new_exposure"]), "Highlights2012": str(r["new_highlights"]),
        "Shadows2012": str(r["new_shadows"]), "Temperature": str(r["new_temp"]),
        "Tint": str(r["new_tint"])} for r in r1}
    if not any(abs(r["new_exposure"]) > 0.05 for r in r1):
        loi.append("Bai cong chong vo nghia: lan dau tool khong doi Exposure anh nao")
    at.xoa_du_lieu_buoi(d, jobs, ca_ban_xuat=True)          # nhu nut tren giao dien
    r2 = chay(exp1)
    lech = [r for a, r in zip(r1, r2) if abs(a["new_exposure"] - r["new_exposure"]) > 0.005]
    if lech:
        loi.append(f"Giu moc ma chay lai van lech {len(lech)} anh: "
                   f"{r1[0]['new_exposure']:+.2f} -> {r2[0]['new_exposure']:+.2f}")
    at.xoa_du_lieu_buoi(d, jobs, ca_ban_xuat=True, xoa_moc=True)
    r3 = chay(exp1)
    if not any(abs(a["new_exposure"] - r["new_exposure"]) > 0.05 for a, r in zip(r1, r3)):
        loi.append("Xoa moc + catalog con so cu ma KHONG cong chong — ly do giu moc khong con dung?")
    return loi


def kiem_mac(td: Path) -> list:
    """Tren macOS khoa_duong_dan viet thuong, normcase thi khong -> khop 0 anh."""
    loi = []
    d = td / "MacBuoi"
    d.mkdir()
    p = d / "SAY00001.ARW"
    p.write_bytes(b"x")
    goc = at.sys.platform
    try:
        at.sys.platform = "darwin"
        xuat = td / "xuat_mac.tsv"
        xuat.write_text(HEADER + "\n" + f"{p}\t0\t16\t16\t5250\t16\t\n", encoding="utf-8")
        export = at.read_catalog_export(xuat)
        r = {"path": str(p)}
        khop, thieu = at.attach_catalog_settings([r], export, d, persist=False)
        if (khop, thieu) != (1, 0):
            loi.append(f"macOS: anh co trong ban xuat ma attach bao khop {khop}, thieu {thieu}")
    finally:
        at.sys.platform = goc
    return loi


def kiem_giao_dien(td: Path, jobs: Path, x: Path, ax: list, bx: Path) -> list:
    try:
        import autotone_gui as gui
    except Exception as ex:                          # noqa: BLE001
        print(f"  (bo qua phan giao dien: {ex.__class__.__name__}: {ex})")
        return []
    loi = []

    class Nhan:
        def __init__(self):
            self.text, self.mau = "", None

        def configure(self, text=None, foreground=None, **_k):
            if text is not None:
                self.text = text
            self.mau = foreground

    class Nut:
        def pack(self, *a, **k):
            pass

        def configure(self, **k):
            pass

        def pack_forget(self):
            pass

    class Gia:
        pass

    def gia(thu_muc):
        g = Gia()
        g.lbl_scan, g.btn_fix, g.lbl_job = Nhan(), Nut(), Nhan()
        g.v_folder = types.SimpleNamespace(get=lambda: str(thu_muc))
        g.v_recursive = types.SimpleNamespace(get=lambda: False)
        g.pairs = [(p, None) for p in ax]
        g.export = {}
        for ten in ("folder", "_doc_xuat", "_dem_khop", "_nhan_catalog", "_xin_xuat_nen",
                    "_kq_cua_thu_muc", "_dang_cho_xuat", "source_value", "xoa_du_lieu_buoi",
                    "_xem_anh_thieu"):
            setattr(g, ten, types.MethodType(getattr(gui.App, ten), g))
        g.v_source = types.SimpleNamespace(get=lambda: dict((v, k) for k, v in gui.SOURCES)["catalog"])
        return g

    # a. doc dung ban xuat cua thu muc + noi dung 1 sao
    ghi_xuat(jobs, bx.name, ax[:3], tuoi_giay=600)
    ghi_ket_qua(jobs, thu_muc=str(x), so_anh=3, bo_sao=1, file=bx.name)
    g = gia(x)
    g._doc_xuat()
    g._nhan_catalog()
    if "1 sao" not in g.lbl_scan.text or g.lbl_scan.mau != gui.gd.MAU["xong"]:
        loi.append(f"Giao dien: thieu 1 anh 1 sao phai bao binh thuong: {g.lbl_scan.text[:120]}")
    if "Synchronize" in g.lbl_scan.text:
        loi.append("Giao dien: anh 1 sao bi goi la chua import")
    # b. thu muc khong co trong catalog
    z = td / "chua_import"
    z.mkdir()
    ghi_ket_qua(jobs, thu_muc=str(z), so_anh=0, loi="khong-co-trong-catalog")
    g2 = gia(z)
    g2._doc_xuat()
    g2._nhan_catalog()
    if "KHÔNG có ảnh nào" not in g2.lbl_scan.text:
        loi.append(f"Giao dien: thu muc chua import phai noi ro: {g2.lbl_scan.text[:120]}")
    # c. dang cho Lightroom
    g3 = gia(z)
    g3._xin_xuat_nen()
    g3._doc_xuat()
    g3._nhan_catalog()
    if "đang nhờ Lightroom" not in g3.lbl_scan.text:
        loi.append(f"Giao dien: yeu cau dang cho phai noi 'dang nho': {g3.lbl_scan.text[:120]}")
    if not at.export_request_pending():
        loi.append("Giao dien: _xin_xuat_nen phai ghi request_export.txt")
    else:
        req = (jobs / "request_export.txt").read_text(encoding="utf-8").splitlines()[0]
        if at.khoa_duong_dan(req) != at.khoa_duong_dan(z):
            loi.append("Giao dien: yeu cau xuat phai la cua DUNG thu muc dang chon")
        # c2. yeu cau nam im > 6 giay, KHONG co nhip -> plugin khong chay, noi ngay
    #     (xoa ket qua cu cua z: lui gio yeu cau 10 giay thi ket qua vua ghi o muc b
    #     se trong nhu cau tra loi cho yeu cau nay — chuyen khong xay ra ngoai doi)
    (jobs / at.KET_QUA_XUAT).unlink()
    nhip = jobs / at.NHIP_PLUGIN
    if nhip.exists():
        nhip.unlink()
    g5 = gia(z)
    g5._xin_xuat_nen()
    g5._yeu_cau_xuat = (g5._yeu_cau_xuat[0], time.time() - 10)
    g5._doc_xuat()
    g5._nhan_catalog()
    if "KHÔNG chạy" not in g5.lbl_scan.text or "Reload" not in g5.lbl_scan.text:
        loi.append(f"Giao dien: yeu cau nam im 10s, khong co nhip -> phai bao plugin khong chay: "
                   f"{g5.lbl_scan.text[:120]}")
    if at.plugin_nhip() is not None:
        loi.append("plugin_nhip phai tra None khi chua co file nhip")
    # c3. co nhip moi (vong lap song) -> chi la dang cho, khong bao chet
    nhip.write_text("vong=51\n", encoding="utf-8")
    if not (at.plugin_nhip() is not None and at.plugin_nhip() < 5):
        loi.append(f"plugin_nhip doc sai: {at.plugin_nhip()}")
    g5._nhan_catalog()
    if "KHÔNG chạy" in g5.lbl_scan.text or "đang nhờ Lightroom" not in g5.lbl_scan.text:
        loi.append(f"Giao dien: co nhip moi ma van bao plugin chet: {g5.lbl_scan.text[:120]}")
    # c4. nhip cu 5 phut -> chet
    cu5 = time.time() - 300
    os.utime(nhip, (cu5, cu5))
    g5._nhan_catalog()
    if "KHÔNG chạy" not in g5.lbl_scan.text:
        loi.append(f"Giao dien: nhip cu 5 phut phai bao plugin khong chay: {g5.lbl_scan.text[:120]}")
    # c5. plugin da NHAN (file yeu cau mat), chua co ket qua -> "dang doc"
    (jobs / "request_export.txt").unlink()
    g5._nhan_catalog()
    if "đang đọc thư mục" not in g5.lbl_scan.text:
        loi.append(f"Giao dien: plugin da nhan, dang xuat -> phai bao 'dang doc': {g5.lbl_scan.text[:120]}")
    nhip.unlink()

    # c6. "Anh nao thieu?" — noi nguyen nhan trung anh + liet ke ten
    ghi_xuat(jobs, bx.name, ax[:3], tuoi_giay=600)
    ghi_ket_qua(jobs, thu_muc=str(x), so_anh=3, bo_sao=0, file=bx.name)
    g6 = gia(x)
    g6._doc_xuat()
    dong_ra = []
    cu_lw = gui.LogWindow
    try:
        gui.LogWindow = lambda app, lines, **k: dong_ra.extend(lines)
        g6._xem_anh_thieu()
    finally:
        gui.LogWindow = cu_lw
    van_ban = "\n".join(dong_ra)
    #   3/10 G:\1009: 111 anh thieu = 111 ban sao da co o G:\Test1009 -> phai noi CA
    #   nguyen nhan (Lightroom coi la trung) LAN cach sua (bo tick o hop Import).
    if "coi chúng là “Suspected Duplicates”" not in van_ban:
        loi.append("'Anh nao thieu?' phai noi nguyen nhan: Lightroom coi la Suspected Duplicates")
    if "Don't Import Suspected Duplicates" not in van_ban or "Synchronize Folder" not in van_ban:
        loi.append("'Anh nao thieu?' phai noi cach sua: Synchronize Folder + bo tick Don't Import...")
    if Path(ax[3]).name not in van_ban:
        loi.append("'Anh nao thieu?' phai liet ke ten anh thieu")
    if Path(ax[0]).name in van_ban.split("Ảnh thiếu:")[-1]:
        loi.append("'Anh nao thieu?' liet ke ca anh DA co trong ban xuat")

    # d. nut Xoa du lieu cu chay het, khong vang loi, va tu xin xuat lai
    at.save_baseline(x, {at.khoa_duong_dan(p): {"Exposure2012": "0"} for p in ax})
    goi = {"scan": 0}
    hoi = []
    g4 = gia(x)
    g4.scan_folder = lambda: goi.__setitem__("scan", goi["scan"] + 1)
    mb = gui.messagebox
    cu = (mb.askyesno, mb.showinfo, mb.showerror)
    try:
        mb.askyesno = lambda *a, **k: (hoi.append(a), True)[1]
        mb.showinfo = lambda *a, **k: hoi.append(a)
        mb.showerror = lambda *a, **k: hoi.append(("LOI",) + a)
        try:
            g4.xoa_du_lieu_buoi()
        except Exception as ex:                      # noqa: BLE001
            loi.append(f"Nut Xoa du lieu cu VANG LOI: {ex.__class__.__name__}: {ex}")
    finally:
        mb.askyesno, mb.showinfo, mb.showerror = cu
    if goi["scan"] != 1:
        loi.append("Nut Xoa du lieu cu phai quet lai (va tu xin xuat) sau khi xoa")
    if bx.exists():
        loi.append("Nut Xoa du lieu cu khong xoa ban xuat cua buoi nay")
    if not any("tu nho Lightroom" in str(a) for a in hoi):
        loi.append("Hop thoai sau khi xoa phai noi app tu nho Lightroom doc lai")
    if not at.baseline_path(x).exists():
        loi.append("Nut Xoa du lieu cu da xoa MOC GOC — lan sau se cong chong len so cu")
    return loi


if __name__ == "__main__":
    sys.exit(main())
