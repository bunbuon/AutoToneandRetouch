# -*- coding: utf-8 -*-
"""Học màu Lightroom TỪ APP (hoc_mau_ui — 15/10) — giao diện THẬT, hoc_mau_lr giả.

hoc_mau_lr.chay có bài riêng (test_hoc_mau_lr §6); bài này canh LUỒNG của app:
    1. kiểm trước: chưa chọn buổi / nguồn không phải catalog / app bận / plugin chưa sẵn sàng
    2. hộp chọn máy: máy chưa học có đủ ảnh chọn sẵn, máy đã ĐẠT không, máy < 6 ảnh khoá
    3. đang học: cửa sổ tiến trình (bước + tiến độ), CHẶN Xử lý ảnh / Áp / Xuất / Hoàn tác /
       Đọc từ Lightroom / xem preset; học xong -> quên mô hình cũ, tổng kết, mở khoá
    4. Dừng -> xin dừng (dung() True), "Đã dừng học màu"
    5. đóng app lúc đang học -> hỏi, xin dừng, chờ xong mới thoát

Chạy:  python test_hoc_mau_ui.py
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path

for _l in (sys.stdout, sys.stderr):
    try:
        _l.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                        # noqa: BLE001
        pass

LOI: list = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


def main() -> int:
    tam = Path(tempfile.mkdtemp(prefix="hoc_mau_ui_"))
    os.environ["AUTOTONE_DATA"] = str(tam / "du_lieu")
    os.environ["AUTOTONE_CATALOG_LR"] = "0"
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import tkinter as tk
    from tkinter import messagebox
    import autotone as at
    import autotone_gui as ag
    import giao_dien as gd
    import hoc_mau_lr as H
    import hoc_mau_ui as hu
    import mau_mot_luot as ml

    jobs = tam / "jobs"
    jobs.mkdir()
    at.LR_JOB_DIR = jobs
    buoi = tam / "Buoi"
    buoi.mkdir()
    root = tk.Tk()
    ag.bq.kiem = lambda: {"co_phep": True, "con_lai": timedelta(days=300), "nhac": "",
                          "goi": "1 năm", "may": "TEST01", "het_han": False, "ly_do": ""}
    root.geometry("1600x940+0+0")
    gd.dat_theme(root)
    hop_tin: list = []
    goc_info, goc_hoi = messagebox.showinfo, messagebox.askyesno
    messagebox.showinfo = lambda t, m, **k: hop_tin.append(m)
    try:
        app = ag.App(root)
        #  17/10: Quy trình Auto mặc định BẬT, mẫu da tự chọn gợi ý theo loại buổi — bài này kiểm
        #  luồng thường với mẫu "Mặc định"
        app.v_auto_lr.set(False)
        app.v_mau_da.set(ag.MAU_DA_MAC_DINH)
        app.grid(row=0, column=0, sticky="nsew")

        def vong(n=4):
            for _ in range(n):
                root.update_idletasks()
                root.update()
                time.sleep(0.02)

        def cho(dieu, giay=20.0):
            het = time.time() + giay
            while time.time() < het:
                vong(1)
                if dieu():
                    return True
            return False

        vong(8)
        K1, K2, K3 = "NIKON_Z_6_2__Camera_Standard__15.4", "ILCE-7M4__Adobe_Standard__15.4", "X__P__15.4"

        # ------------------------------------------------------------ 1
        print("1. kiểm trước")
        app.folder = lambda: None
        app.hoc_mau_lr()
        ktra("chưa chọn buổi -> báo, không chạy", hop_tin and "thư mục buổi" in hop_tin[-1] and not app._hm_dang())
        app.folder = lambda: buoi
        app.source_value = lambda: "sidecar"
        app.hoc_mau_lr()
        ktra("nguồn .xmp -> báo cần Catalog Lightroom", "Catalog Lightroom" in hop_tin[-1])
        app.source_value = lambda: "catalog"
        app.busy = True
        app.hoc_mau_lr()
        ktra("app bận -> không mở", not app._hm_dang() and "bận" in str(app.lbl_status.cget("text")))
        app.busy = False
        H.kiem_san_sang = lambda folder, jobs=None: ("Plugin AutoTone trong Lightroom chưa chạy — mở "
                                                     "Lightroom rồi thử lại.", [])
        app.hoc_mau_lr()
        ktra("plugin chưa chạy -> báo đúng lý do", cho(lambda: "chưa chạy" in (hop_tin[-1] if hop_tin else "")))

        # ------------------------------------------------------------ 2
        print("2. hộp chọn máy")
        ds = [(K1, 24, "chua_hoc"), (K2, 30, "goi"), (K3, 3, "chua_hoc")]
        h = hu.HopChonMay(app, ds)
        vong(3)
        ktra("máy chưa học đủ ảnh chọn sẵn; máy có mô hình kèm gói không; máy 3 ảnh khoá",
             h.chon() == [K1] and K3 not in h.bien, str(h.chon()))
        ktra("…số phút ước tính theo số máy chọn", "Học 1 máy" in h.lbl_so.cget("text"), h.lbl_so.cget("text"))
        h.bien[K2].set(True)
        h._dem()
        ktra("…chọn thêm -> 2 máy", "Học 2 máy" in h.lbl_so.cget("text"))
        h._hoc()
        ktra("Bắt đầu học -> kết quả = máy đã chọn", h.kq == [K1, K2])
        h = hu.HopChonMay(app, ds, khoa_ds=[K2])
        ktra("mở từ tổng kết Xử lý ảnh -> chọn sẵn đúng máy gợi ý", h.chon() == [K2])
        h.destroy()
        h = hu.HopChonMay(app, ds, khoa_ds=["KHONG_KHOP"])
        ktra("…gợi ý không khớp khoá catalog -> chọn sẵn như thường", h.chon() == [K1])
        h.destroy()

        # ------------------------------------------------------------ 3
        print("3. đang học: chặn ghi Lightroom; xong -> tổng kết")
        H.kiem_san_sang = lambda folder, jobs=None: ("", [{"path": "x"}])
        H.cac_khoa_cho = lambda folder, items: ds

        class ChonGia:
            kq_lan_sau = [K1]

            def __init__(self, app_, ds_, khoa_ds=None):
                self.kq = list(ChonGia.kq_lan_sau)

            def wait_window(self):
                pass
        hu.HopChonMay = ChonGia
        trang = {"di": False, "dung_thay": False}
        goi_chay: list = []

        def chay_gia(folder, jobs=None, *, khoa_ds=None, bao=None, tien=None, dung=None, buoc=None, **k):
            goi_chay.append(list(khoa_ds))
            buoc("chuan_bi", "dang", "plugin xuất thông số hiện tại…")
            bao("Đọc thông số hiện tại (catalog + bản xuất của plugin)…")
            buoc("chuan_bi", "xong", "24 ảnh")
            ket = []
            for kk in khoa_ds:
                buoc(kk, "dang", "chọn ảnh học…")
                for x in range(1, 41):
                    tien(x, 580, "k+", "")
                    time.sleep(0.02)
                    while not trang["di"] and not dung():
                        time.sleep(0.02)
                    if dung():
                        trang["dung_thay"] = True
                        buoc(kk, "bo", "đã dừng — ảnh đã trả lại")
                        ket.append((kk, "đã dừng"))
                        return {"ma": 1, "ket": ket, "bao_cao": str(tam / "bc.txt"), "loi": ""}
                buoc(kk, "xong", "ĐẠT")
                ket.append((kk, "ĐẠT"))
            return {"ma": 0, "ket": ket, "bao_cao": str(tam / "bc.txt"), "loi": ""}
        H.chay = chay_gia
        quen = []
        ml.quen_mo_hinh = lambda: quen.append(1)
        app.hoc_mau_lr()
        ktra("bắt đầu học: _hm_dang, cửa sổ tiến trình", cho(lambda: app._hm_dang() and app._hm.get("hop")
                                                              is not None), str(goi_chay))
        hop = app._hm["hop"]
        ktra("…chạy đúng máy đã chọn", cho(lambda: goi_chay == [[K1]]), str(goi_chay))
        ktra("…bước + tiến độ dựng hiện trên cửa sổ", cho(lambda: hop.tt.get(K1) == "dang"
                                                         and "Lightroom dựng" in hop.lbl_td.cget("text")),
             f"{hop.tt} {hop.lbl_td.cget('text')}")
        ktra("…tiêu đề cửa sổ học màu", hop.title() == hu.TIEU_DE and "học màu" in hop.lbl_tieu_de.cget("text"))
        ktra("…đóng cửa sổ chính bị chặn (hỏi trước)",
             str(root.protocol("WM_DELETE_WINDOW")) != "" and "_hm_dong_app" in str(root.protocol("WM_DELETE_WINDOW")))
        xl_truoc = getattr(app, "_xl", None)
        app.xu_ly_anh()
        ktra("chặn Xử lý ảnh", getattr(app, "_xl", None) is xl_truoc and "học màu" in str(app.lbl_status.cget("text")))
        app.items = [{"path": "x"}]
        dang_ap = []
        goc_ap = app._xl_ap_loi
        app._xl_ap_loi = lambda ly_do: dang_ap.append(ly_do)
        app.do_apply(hoi=False, tu_dong=True)
        app._xl_ap_loi = goc_ap
        ktra("chặn Áp (báo vào hộp Xử lý)", dang_ap and "học màu" in dang_ap[-1], str(dang_ap))
        ktra("chặn Xuất / Hoàn tác / Đọc từ Lightroom (_hm_chan)", app.do_xuat_hop() is None
             and app.do_undo() is None and app.do_read_from_lr() is None and app._hm_chan())
        import preset_ui
        dp = preset_ui.DieuPhoiPreset(app)
        dp.p, dp.hang_doi = {"uuid": "U", "ten": "Film"}, [(str(buoi), [str(buoi / "a.ARW")])]
        dp._gui_tiep()
        ktra("chặn xem preset (áp tạm)", "học màu" in dp.loi and not dp.hang_doi and dp.id is None, dp.loi)
        app.hoc_mau_lr()
        ktra("bấm menu lần nữa -> chỉ hiện lại cửa sổ, không chạy lượt hai", len(goi_chay) == 1)
        trang["di"] = True
        ktra("học xong -> 'Học màu xong', mở khoá", cho(lambda: not app._hm_dang())
             and hop.lbl_tieu_de.cget("text") == "Học màu xong", hop.lbl_tieu_de.cget("text"))
        tong = hop.lbl_tong.cget("text")
        ktra("…tổng kết: máy ĐẠT + nhắc bật công tắc một lượt + báo cáo",
             "ĐẠT" in tong and "Chế độ nhanh một lượt" in tong and "Báo cáo" in tong, tong.replace("\n", " | "))
        ktra("…quên mô hình cũ (mô hình mới có hiệu lực ngay)", quen == [1])
        ktra("…bỏ chặn đóng cửa sổ chính", str(root.protocol("WM_DELETE_WINDOW")) == "")
        ktra("…hết chặn ghi Lightroom", not app._hm_chan())
        hop.destroy()

        # ------------------------------------------------------------ 4
        print("4. Dừng")
        trang.update(di=False, dung_thay=False)
        app.hoc_mau_lr()
        ktra("bắt đầu lượt mới", cho(lambda: app._hm_dang() and app._hm.get("td") is not None))
        hop = app._hm["hop"]
        hop.btn_dung.invoke()
        ktra("Dừng -> plugin được xin dừng, 'Đã dừng học màu'", cho(lambda: not app._hm_dang())
             and trang["dung_thay"] and hop.lbl_tieu_de.cget("text") == "Đã dừng học màu",
             hop.lbl_tieu_de.cget("text"))
        ktra("…tổng kết nói ảnh đã trả lại", "trả lại" in hop.lbl_tong.cget("text"))
        hop.destroy()

        # ------------------------------------------------------------ 5
        print("5. đóng app lúc đang học")
        trang.update(di=False, dung_thay=False)
        app.hoc_mau_lr()
        ktra("bắt đầu lượt mới", cho(lambda: app._hm_dang() and app._hm.get("td") is not None))
        messagebox.askyesno = lambda *a, **k: False
        app._hm_dong_app()
        ktra("hỏi -> Không: vẫn học", app._hm_dang() and not app._hm["dung"])
        messagebox.askyesno = lambda *a, **k: True
        app._hm_dong_app()
        ktra("hỏi -> Có: xin dừng, chưa thoát ngay", app._hm["dung"] and app._hm["thoat"] and root.winfo_exists())
        het = time.time() + 20
        con = True
        while time.time() < het and con:
            try:
                vong(1)
                con = bool(root.winfo_exists())
            except tk.TclError:
                con = False
        ktra("…plugin dừng xong -> app thoát", not con and trang["dung_thay"])
    finally:
        messagebox.showinfo, messagebox.askyesno = goc_info, goc_hoi
        try:
            root.destroy()
        except Exception:                                    # noqa: BLE001
            pass
        shutil.rmtree(tam, ignore_errors=True)
    print(f"\n{len(LOI)} LOI" if LOI else "\nTAT CA DAT")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
