#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kết quả phân tích lưu theo buổi, mở lại đúng thư mục thì nạp lại (8/10).

CHUYỆN ĐANG SỬA
    User: "Khi 1 buổi đã được phân tích cần lưu lại thông số đã phân tích và hiển
    thị nếu mở lại đúng folder đó. Như hiện tại mở lại là đang chưa load được các
    thông số đã phân tích trước đó." (BVDay3, 1813 RAW, "chưa phân tích").

Mục kiểm — engine (at.luu_ket_qua_do / at.nap_ket_qua_do)
    1. Buổi chưa từng phân tích: không nạp, không lý do.
    2. Lưu rồi nạp: đủ ảnh, đúng số đo, đúng giờ đo.
    3. KHÔNG nạp khi: đổi cách đo · một ảnh RAW đổi · có ảnh mới · bản engine
       khác · file hỏng — và nói đúng lý do.
    4. Ảnh bị xoá bớt khỏi thư mục: vẫn nạp, bỏ đúng ảnh đã xoá.
    5. Giữ tối đa GIU_KET_QUA_DO buổi, xoá buổi cũ nhất.
    6. analyze() dựng việc đo từ cau_hinh_do — đủ tham số cho measure().
Mục kiểm — giao diện thật
    7. Phân tích buổi A -> sang buổi B (chưa phân tích) -> quay lại A: kết quả
       hiện lại, KHÔNG đo lại, nhãn tổng nói "(đã lưu)".
    8. Bấm "1 · Phân tích" ở buổi đã lưu: VẪN đo lại thật.
    9. Một ảnh RAW của A đổi -> mở lại A: không nạp, dòng trạng thái nói lý do.

Chạy:  python test_luu_phan_tich.py
"""
from __future__ import annotations

import inspect
import os
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

LOI: list[str] = []


def ktra(ten: str, dieu: bool, mo: str = "") -> None:
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(f"{ten}: {mo}")


def lam_buoi(goc: Path, ten: str, n: int) -> Path:
    d = goc / ten
    d.mkdir()
    for i in range(n):
        (d / f"{ten}_{i}.ARW").write_bytes(b"RAW" + bytes([i]) * 64)
        (d / f"{ten}_{i}.xmp").write_text("<x/>", encoding="utf-8")
    return d


def main() -> int:
    tam = Path(tempfile.mkdtemp(prefix="luu_pt_"))
    os.environ["AUTOTONE_DATA"] = str(tam / "du_lieu")       # khong ghi vao repo
    import autotone as at
    import test_2ban_quay as tq

    def items_cua(d: Path) -> list:
        out = []
        for i, p in enumerate(sorted(d.glob("*.ARW"))):
            r = tq.anh(p.stem, i * 8, -1.4 + 0.1 * i, da=tq.DA_TRONG)
            r["path"] = str(p)
            r["sidecar"] = str(p.with_suffix(".xmp"))
            out.append(r)
        return out

    cfg = dict(at.DEFAULTS)
    a = lam_buoi(tam, "BVDay3", 5)
    pairs, _ = at.collect_pairs(a)

    # ---- 1-2
    ktra("chua phan tich: khong nap, khong ly do", at.nap_ket_qua_do(a, cfg, pairs) == (None, ""))
    its = items_cua(a)
    f = at.luu_ket_qua_do(a, cfg, pairs, its, [{"path": str(pairs[0][0]), "error": "x"}])
    ktra("luu ra file trong thu muc du lieu", f is not None and f.is_file()
         and f.parent == tam / "du_lieu" / at.THU_MUC_KET_QUA_DO, str(f))
    kq, ly = at.nap_ket_qua_do(a, cfg, pairs)
    ktra("nap lai: du anh, dung so do, dung gio",
         kq is not None and len(kq["items"]) == 5
         and [r["metered_ev"] for r in kq["items"]] == [r["metered_ev"] for r in its]
         and kq["items"][2]["dt_obj"] == its[2]["dt_obj"]
         and abs(kq["luc"] - time.time()) < 60 and len(kq["failed"]) == 1, ly)

    # ---- 3
    cfg2 = dict(cfg, meter="frame" if cfg["meter"] != "frame" else "face")
    kq, ly = at.nap_ket_qua_do(a, cfg2, pairs)
    ktra("doi cach do -> khong nap, noi ly do", kq is None and "cách đo" in ly, ly)

    p1 = pairs[1][0]
    st = p1.stat()
    os.utime(p1, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    kq, ly = at.nap_ket_qua_do(a, cfg, pairs)
    ktra("mot anh RAW doi -> khong nap", kq is None and "1 ảnh đã đổi" in ly, ly)
    os.utime(p1, ns=(st.st_atime_ns, st.st_mtime_ns))

    (a / "BVDay3_9.ARW").write_bytes(b"RAW9")
    (a / "BVDay3_9.xmp").write_text("<x/>", encoding="utf-8")
    p_moi, _ = at.collect_pairs(a)
    kq, ly = at.nap_ket_qua_do(a, cfg, p_moi)
    ktra("co anh moi -> khong nap", kq is None and "1 ảnh mới" in ly, ly)
    (a / "BVDay3_9.ARW").unlink()
    (a / "BVDay3_9.xmp").unlink()

    cu = list(at._DAU_ENGINE)
    at._DAU_ENGINE[:] = ["ban-khac"]
    kq, ly = at.nap_ket_qua_do(a, cfg, pairs)
    ktra("ban engine khac -> khong nap", kq is None and "bản app khác" in ly, ly)
    at._DAU_ENGINE[:] = cu

    # ---- 4
    pairs[4][0].unlink()
    p_bot, _ = at.collect_pairs(a)
    kq, ly = at.nap_ket_qua_do(a, cfg, p_bot)
    ktra("xoa bot 1 anh -> van nap 4 anh, bo anh da xoa",
         kq is not None and len(kq["items"]) == 4 and kq["n_bo"] == 1
         and str(pairs[4][0]) not in {r["path"] for r in kq["items"]}, ly)
    pairs[4][0].write_bytes(b"RAW" + bytes([4]) * 64)            # tra lai cho phan giao dien

    noi = f.read_bytes()
    f.write_bytes(b"hong")
    kq, ly = at.nap_ket_qua_do(a, cfg, pairs)
    ktra("file hong -> khong nap", kq is None and "hỏng" in ly, ly)
    f.write_bytes(noi)

    # ---- 5
    giu = at.GIU_KET_QUA_DO
    at.GIU_KET_QUA_DO = 3
    try:
        for i in range(4):
            b = lam_buoi(tam, f"Buoi{i}", 1)
            pb, _ = at.collect_pairs(b)
            ff = at.luu_ket_qua_do(b, cfg, pb, items_cua(b), [])
            os.utime(ff, (time.time() - 100 + i, time.time() - 100 + i))
        con = sorted(x.name for x in f.parent.glob("*.pkl"))
        ktra("giu toi da GIU_KET_QUA_DO buoi, xoa buoi cu nhat",
             len(con) == 3 and any(x.startswith("Buoi3") for x in con)
             and not any(x.startswith(("Buoi0", "Buoi1")) for x in con), str(con))
        #  dong ho lech: file khac co mtime o TUONG LAI -> file vua ghi van phai con
        for x in f.parent.glob("*.pkl"):
            os.utime(x, (time.time() + 999, time.time() + 999))
        b = lam_buoi(tam, "BuoiMoi", 1)
        pb, _ = at.collect_pairs(b)
        ff = at.luu_ket_qua_do(b, cfg, pb, items_cua(b), [])
        ktra("file vua ghi khong bao gio bi don", ff is not None and ff.is_file()
             and len(list(f.parent.glob("*.pkl"))) == 3)
    finally:
        at.GIU_KET_QUA_DO = giu

    # ---- 6
    so_tham = len(inspect.signature(at.measure).parameters)
    ktra("cau_hinh_do du tham so cho measure()",
         len(at.cau_hinh_do(cfg)) + 1 == so_tham, f"{len(at.cau_hinh_do(cfg)) + 1} / {so_tham}")

    # ---- 7-9 giao dien that
    try:
        import tkinter as tk
        import autotone_gui as ag
        import giao_dien as gd
        root = tk.Tk()
    except Exception as ex:                                  # noqa: BLE001
        print(f"  (bo qua phan giao dien: {ex.__class__.__name__}: {ex})")
        print("TAT CA DAT" if not LOI else f"{len(LOI)} LOI")
        return 1 if LOI else 0
    ag.bq.kiem = lambda: {"co_phep": True, "con_lai": timedelta(days=300), "nhac": "",
                          "goi": "1 năm", "may": "TEST01", "het_han": False, "ly_do": ""}
    root.geometry("1500x900+0+0")
    gd.dat_theme(root)
    job_cu, analyze_cu = at.LR_JOB_DIR, at.analyze
    at.LR_JOB_DIR = tam / "jobs"
    at.LR_JOB_DIR.mkdir()
    lan_do: list = []

    def analyze_gia(pairs_, cfg_, jobs=1, progress=None, cancel=None):
        lan_do.append(len(pairs_))
        d = Path(pairs_[0][0]).parent
        return items_cua(d), []

    at.analyze = analyze_gia
    try:
        app = ag.App(root)
        app.grid(row=0, column=0, sticky="nsew")

        def vong(n=4):
            for _ in range(n):
                root.update_idletasks()
                root.update()
                time.sleep(0.02)

        def cho_do_xong(giay=15.0):
            het = time.time() + giay
            while time.time() < het:
                vong(1)
                if app.items and not app.busy:
                    return True
            return False

        vong(8)
        ga = lam_buoi(tam, "KyYeuA", 6)
        gb = lam_buoi(tam, "KyYeuB", 4)
        app.v_folder.set(str(ga))
        app.scan_folder()
        vong()
        ktra("buoi A moi: chua phan tich", not app.items and "chưa phân tích" in app.lbl_tong.cget("text"),
             app.lbl_tong.cget("text"))
        app.start_analyze()
        ktra("phan tich A xong", cho_do_xong() and len(app.items) == 6 and lan_do == [6], str(lan_do))
        ktra("da luu ket qua A", at.file_ket_qua_do(ga).is_file())
        ktra("nhan tong sau khi do: co gio do, khong '(đã lưu)'",
             "đo lúc" in app.lbl_tong.cget("text") and "đã lưu" not in app.lbl_tong.cget("text"),
             app.lbl_tong.cget("text"))

        app.v_folder.set(str(gb))
        app.scan_folder()
        vong()
        ktra("sang B (chua phan tich): khong co ket qua", not app.items
             and "chưa phân tích" in app.lbl_tong.cget("text"), app.lbl_tong.cget("text"))

        app.v_folder.set(str(ga))
        app.scan_folder()
        vong()
        ktra("quay lai A: NAP lai 6 anh, KHONG do lai",
             len(app.items) == 6 and lan_do == [6], f"{len(app.items)} anh, lan do {lan_do}")
        ktra("nhan tong noi '(đã lưu)'", "(đã lưu)" in app.lbl_tong.cget("text"),
             app.lbl_tong.cget("text"))
        ktra("dong trang thai noi da nap", "Đã nạp kết quả phân tích" in app.lbl_status.cget("text"),
             app.lbl_status.cget("text")[:80])
        ktra("bang so co du dong", len(app.tree.get_children()) == 6)
        ktra("nut Ghi mo duoc", str(app.btn_ghi3.cget("state")) == "normal")

        # 7b. che do catalog: ban xuat app nho Lightroom lam luc mo buoi ve SAU khi nap
        yc = at.LR_JOB_DIR / "request_export.txt"
        ktra("nap o che do catalog: cho ban xuat moi da nho", app._cho_xuat_sau_nap and yc.exists())
        app._soi_xuat()
        ktra("Lightroom chua xuat -> van cho, chua tinh lai", app._cho_xuat_sau_nap and not app.export)
        yc.unlink()
        hd = "path\tExposure2012\tHighlights2012\tShadows2012\tTemperature\tTint\tRating"
        (at.LR_JOB_DIR / "export_20261008_220000.tsv").write_text(
            "\n".join([hd] + [f"{x}\t0\t16\t16\t5250\t16\t" for x in sorted(ga.glob("*.ARW"))])
            + "\n", encoding="utf-8")
        app._soi_xuat()
        vong()
        ktra("ban xuat ve -> tinh lai MOT lan bang ban moi, roi dung yen",
             not app._cho_xuat_sau_nap and len(app.export) == 6 and app._xuat_khoa
             and len(app.items) == 6, f"export {len(app.export)}, khoa {app._xuat_khoa}")

        # 8. bam Phan tich o buoi da luu -> do lai that
        app.items = []
        app.start_analyze()
        ktra("bam Phan tich: VAN do lai", cho_do_xong() and lan_do == [6, 6], str(lan_do))
        ktra("sau khi do lai: nhan khong con '(đã lưu)'", "đã lưu" not in app.lbl_tong.cget("text"))

        # 9. mot anh RAW doi
        p = sorted(ga.glob("*.ARW"))[0]
        st = p.stat()
        os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 7_000_000_000))
        app.v_folder.set(str(gb))
        app.scan_folder()
        app.v_folder.set(str(ga))
        app.scan_folder()
        vong()
        ktra("anh RAW doi: KHONG nap, noi ly do",
             not app.items and "1 ảnh đã đổi" in app.lbl_status.cget("text"),
             app.lbl_status.cget("text")[:90])
    finally:
        at.LR_JOB_DIR, at.analyze = job_cu, analyze_cu
        try:
            root.destroy()
        except Exception:                                    # noqa: BLE001
            pass

    print("TAT CA DAT" if not LOI else f"{len(LOI)} LOI")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
