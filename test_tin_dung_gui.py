# -*- coding: utf-8 -*-
"""Giao diện THẬT của credit + một key một máy một lúc (13/10).

App thật (autotone_gui.App) + Worker THẬT (`wrangler dev --local`, xem
test_tin_dung.py) + engine đo giả (at.analyze vá, như test_xu_ly_anh). "Máy khác"
là một tiến trình con với AUTOTONE_DATA và mã máy riêng.

    xvfb-run -a python3 test_tin_dung_gui.py     (Linux; macOS / Windows chạy thẳng)

Không có repo KeyActiveAutoTone đã `npm ci` thì in "bỏ qua" (xem test_tin_dung).
"""
from __future__ import annotations

import os
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

GOC = Path(__file__).resolve().parent
LOI: list = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {str(mo)[:300]}")
    if not dieu:
        LOI.append(ten)


def main() -> int:
    sys.path.insert(0, str(GOC))
    import test_tin_dung as ttd                     # Worker thật + key thử + "máy" con
    tm = ttd.tim_worker()
    if not tm:
        print("  [bỏ qua] không thấy repo KeyActiveAutoTone đã npm ci (AUTOTONE_KEYSERVER)")
        return 0
    tam = Path(tempfile.mkdtemp(prefix="td_gui_"))
    os.environ["AUTOTONE_DATA"] = str(tam / "du_lieu")
    os.environ["AUTOTONE_CATALOG_LR"] = str(tam / "Gia.lrcat")
    w = ttd.Worker(tm).bat()
    try:
        return _chay(ttd, w, tam)
    finally:
        w.tat()


def _chay(ttd, w, tam: Path) -> int:
    import autotone as at
    import test_2ban_quay as tq
    import test_giao_dien_gon as tg
    import ban_quyen as bq
    import khoa
    import tin_dung as td
    from tkinter import messagebox

    khoa.ma_may = lambda: "GUIA00000001"
    td.ten_may = lambda: "MAY-GUI"
    bq.MAY_CHU = w.url
    K = ttd.tao_key(301, 365)
    ok, nhan = bq.kich_hoat(K)
    ktra("kích hoạt key thử với Worker thật", ok, nhan)
    MAY_B = (tam / "may_B", "BBBBBBBB0002", "MAY-B")
    MAY_B[0].mkdir(parents=True)

    def tren_B(than):
        return ttd.may(MAY_B[0], MAY_B[1], MAY_B[2], w.url, than)

    r = tren_B(f"ok, n = bq.kich_hoat({K!r}); ra(td.vao_phien(chiem=True))")
    ktra("máy B đang dùng key trước khi mở app", r.get("tt") == "dung", r)

    buoi = tam / "SuKien"
    buoi.mkdir()

    def them_anh(i):
        tg.raw_gia(buoi / f"SK_{i}.ARW", mau=(90 + 9 * i, 120, 150))
        (buoi / f"SK_{i}.xmp").write_text(tg.XMP_GIA, encoding="utf-8")
    for i in range(6):
        them_anh(i)

    def items_cua(pairs_) -> list:
        out = []
        for p, sc in pairs_:
            i = int(Path(p).stem.split("_")[1])
            rr = tq.anh(Path(p).stem, i * 8, -1.6 + 0.05 * i, da=tq.DA_TRONG, iso=400)
            rr["path"] = str(p)
            rr["sidecar"] = str(sc) if sc else str(Path(p).with_suffix(".xmp"))
            out.append(rr)
        return out

    lan_do: list = []
    cham = {"v": False, "bi_dung": None}

    def analyze_gia(pairs_, cfg_, jobs_=1, progress=None, cancel=None):
        lan_do.append(len(pairs_))
        if cham["v"]:
            #  đo "chậm": chờ tới khi app xin dừng (tối đa 40 giây)
            het = time.time() + 40
            while time.time() < het and not (cancel and cancel()):
                time.sleep(0.1)
            cham["bi_dung"] = bool(cancel and cancel())
        return items_cua(pairs_), []
    at.analyze = analyze_gia
    at.LR_JOB_DIR = tam / "jobs"
    at.LR_JOB_DIR.mkdir()

    hoi: list = []
    tra_loi = {"askyesno": True}
    messagebox.askyesno = lambda t, m, **k: (hoi.append(("askyesno", t, m)), tra_loi["askyesno"])[1]
    for ten in ("showinfo", "showwarning", "showerror"):
        setattr(messagebox, ten, (lambda ten_: lambda t, m, **k: hoi.append((ten_, t, m)))(ten))

    import tkinter as tk
    import autotone_gui as ag
    import giao_dien as gd
    ag.bq.kiem = lambda: {"co_phep": True, "con_lai": timedelta(days=300), "nhac": "",
                          "goi": "1 năm", "may": "GUIA00000001", "het_han": False, "ly_do": ""}
    root = tk.Tk()
    root.geometry("1600x940+0+0")
    gd.dat_theme(root)
    app = ag.App(root)
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

    def hop_mo():
        lop = getattr(app, "_td_lop", None)
        try:
            return lop is not None and bool(lop.winfo_exists())
        except tk.TclError:
            return False

    def vi():
        return w.quan_tri(f"/credit/xem?key={K}").get("vi") or {}

    try:
        vong(8)
        # ── 1. Mở app khi máy B đang dùng: hộp cảnh báo ──
        ktra("mở app khi B đang dùng: hiện hộp 'Key đang dùng trên máy khác'",
             cho(hop_mo) and "máy khác" in app._td_lbl_tieu_de.cget("text")
             and "MAY-B" in app._td_lbl_ly_do.cget("text"),
             getattr(app, "_td_lbl_ly_do", None) and app._td_lbl_ly_do.cget("text"))
        ktra("…trong lúc đó mọi việc nặng bị chặn (_khoa_chan)", app._khoa_chan() is True)
        app.btn_td_chiem.invoke()
        ktra("bấm 'Tiếp tục dùng trên máy này': hộp đóng, máy này giữ phiên",
             cho(lambda: not hop_mo()) and td.trang_thai().get("tt") == "dung")
        r = tren_B("ra(td.nhip())")
        ktra("…máy B bị đẩy ra, nghe tên máy này", r.get("tt") == "bi_day_ra"
             and r.get("ten_may") == "MAY-GUI", r)
        ktra("nhãn thanh dưới có số credit", cho(lambda: "500.000 credit" in app.lbl_han.cget("text")),
             app.lbl_han.cget("text"))

        #  nhịp 60 giây của hạn bản quyền (_soi_khoa) vẽ lại hạn mới mà vẫn giữ số credit
        ag.bq.kiem = lambda: {"co_phep": True, "con_lai": timedelta(days=40), "nhac": "",
                              "goi": "1 năm", "may": "GUIA00000001", "het_han": False,
                              "ly_do": ""}
        app._soi_khoa()
        ktra("nhịp hạn bản quyền vẽ lại hạn mới + vẫn giữ số credit",
             "còn 40 ngày" in app.lbl_han.cget("text")
             and "500.000 credit" in app.lbl_han.cget("text"), app.lbl_han.cget("text"))

        # ── 2. Phân tích: trừ đúng số ảnh, phân tích lại không trừ ──
        app.v_source.set(ag.SOURCES[0][0])
        app.v_folder.set(str(buoi))
        app.scan_folder()
        vong()
        app.start_analyze()
        ktra("phân tích 6 ảnh: trừ 6 credit trên máy chủ",
             cho(lambda: lan_do == [6]) and vi().get("da_dung") == 6, (lan_do, vi()))
        ktra("…dòng trạng thái (sau khi phân tích xong) còn câu 'Trừ 6 credit · còn 499.994'",
             cho(lambda: not app.busy) and cho(lambda: "Trừ 6 credit · còn 499.994"
                                                in app.lbl_status.cget("text")),
             app.lbl_status.cget("text"))
        ktra("…nhãn thanh dưới cập nhật số mới", "499.994 credit" in app.lbl_han.cget("text"),
             app.lbl_han.cget("text"))
        app.start_analyze()
        ktra("phân tích lại cả buổi: đo lại nhưng KHÔNG trừ thêm",
             cho(lambda: lan_do == [6, 6]) and vi().get("da_dung") == 6, (lan_do, vi()))
        ktra("…dòng trạng thái nói 6 ảnh đã trừ trước",
             cho(lambda: "Trừ 0 credit (6 ảnh đã trừ trước)" in app.lbl_status.cget("text")),
             app.lbl_status.cget("text"))

        # ── 3. Hết credit: hộp đề nghị phân tích phần vừa đủ ──
        w.quan_tri("/credit/dat", {"key": K, "tong": 8})
        for i in range(6, 10):
            them_anh(i)
        cho(lambda: not app.busy)
        app.start_analyze()
        ktra("còn 2 credit, 4 ảnh mới: hỏi 'phân tích 8 ảnh vừa đủ' (2 mới + 6 đã trừ)",
             cho(lambda: any(h[0] == "askyesno" for h in hoi))
             and "Cần 4 credit" in hoi[-1][2] and "còn 2" in hoi[-1][2], hoi[-1:] if hoi else "")
        ktra("…đồng ý thì đo đúng 8 ảnh, server đã dùng 8 / 8",
             cho(lambda: lan_do[-1:] == [8]) and vi().get("da_dung") == 8, (lan_do, vi()))

        # ── 4. Đang phân tích thì máy B "Vẫn truy cập": máy này dừng ngay ──
        w.quan_tri("/credit/nap", {"key": K, "them": 100})
        cho(lambda: not app.busy)
        cham["v"] = True
        app.start_analyze()
        ktra("đang phân tích (engine đo giả đang chạy)",
             cho(lambda: app.busy and len(lan_do) == 4, 15), (app.busy, lan_do))
        t_chiem = time.time()
        r = tren_B("ra(td.vao_phien(chiem=True))")
        ktra("máy B bấm Vẫn truy cập (KHÔNG đụng gì vào app này)", r.get("tt") == "dung", r)
        ktra("≤ 8 giây sau: app này tự dừng phân tích (nhịp 5 giây khi đang chạy việc)",
             cho(lambda: cham["bi_dung"] is not None, 12) and cham["bi_dung"] is True
             and time.time() - t_chiem <= 8.5, (cham, round(time.time() - t_chiem, 1)))
        cham["v"] = False
        ktra("…hiện hộp 'Máy này đã bị đẩy ra', nêu MAY-B, nói việc đang chạy đã dừng",
             cho(hop_mo) and "đẩy ra" in app._td_lbl_tieu_de.cget("text")
             and "MAY-B" in app._td_lbl_ly_do.cget("text")
             and "đã dừng" in app._td_lbl_ly_do.cget("text"),
             app._td_lbl_ly_do.cget("text") if hop_mo() else "")
        b = app.btn_td_chiem
        ktra("…nút 'Vẫn truy cập'", b.itemcget(b._i_chu, "text") == "Vẫn truy cập",
             b.itemcget(b._i_chu, "text"))
        so = len(lan_do)
        cho(lambda: not app.busy)
        app.start_analyze()
        vong(10)
        ktra("…bị đẩy ra thì Phân tích không chạy", len(lan_do) == so, lan_do)
        import xuat_ui
        mo_xuat: list = []
        xd_cu = xuat_ui.XuatDialog
        xuat_ui.XuatDialog = lambda *a, **k: mo_xuat.append(1) or (_ for _ in ()).throw(
            RuntimeError("không được mở hộp Xuất khi đã bị đẩy ra"))
        try:
            app.do_xuat_hop()
        except RuntimeError:
            pass
        finally:
            xuat_ui.XuatDialog = xd_cu
        ktra("…và Export… cũng không mở (đường xuất có chốt)", not mo_xuat, mo_xuat)

        # ── 5. Bảng Credit & thiết bị ──
        app.btn_td_chiem.invoke()
        cho(lambda: not hop_mo())
        nhan_menu = [app.menu_them.entrycget(i, "label")
                     for i in range(app.menu_them.index("end") + 1)
                     if app.menu_them.type(i) == "command"]
        ktra("menu ⋯ có 'Credit & thiết bị…'", "Credit & thiết bị…" in nhan_menu)
        app.xem_credit()
        ktra("bảng Credit & thiết bị: số còn lại + đếm theo máy",
             cho(lambda: any(h[1] == "Credit & thiết bị" for h in hoi))
             and "còn 98 / 108" in hoi[-1][2] and "MAY-GUI: 10 / 30" in hoi[-1][2],
             hoi[-1:] if hoi else "")

        # ── 6. Đóng app: KHÔNG nhả phiên (đóng app / tắt máy vẫn là đang đăng nhập) ──
        app._td_dung()
        r = tren_B("ra(td.vao_phien())")
        ktra("đóng app vẫn giữ key — máy B mở sau bị hỏi, nêu MAY-GUI",
             r.get("tt") == "xung_dot" and r.get("ten_may") == "MAY-GUI", r)
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass
    print(f"\n  {len(LOI)} lỗi" if LOI else "\n  TẤT CẢ ĐẠT")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
