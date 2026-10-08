#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nút Ghi khi Lightroom CHƯA nhận job (8/10) — mở ỨNG DỤNG THẬT và bấm thử.

CHUYỆN ĐANG SỬA
    User: "bấm ghi và đẩy vào Lightroom cần check xem Lightroom đã nhận chưa. Nếu
    chưa nhận thì chuyển trạng thái hoặc cần có nút ngắt tiến trình. Hiện tại nếu
    bấm 2 lần thì sẽ chạy loading 2 lần."
    Trước đó: ghi job xong là nút Ghi mở lại ngay; bấm lần hai sinh job thứ hai và
    một vòng chờ thứ hai. Và at.job_state() không bao giờ thấy "đang áp" — plugin
    giành job bằng tên `<job>.<id>-<giờ>-<số>.running`.

Mục kiểm
    1. at.job_state: .tsv = cho; `.tsv.<id>.running` = dang; .done = xong; .huy = huy.
    2. at.huy_job: job chờ -> .huy (plugin chỉ quét apply_*.tsv); job đang áp -> "da-nhan".
    3. App: job chờ -> nút Ghi khoá, "Huỷ gửi" hiện, dòng trạng thái nói Lightroom
       CHƯA nhận (nhịp plugin cũ -> "plugin không chạy").
    4. Bấm Ghi lần hai khi đang chờ: KHÔNG sinh job mới.
    5. Bấm "Huỷ gửi": job -> .huy, nút Ghi mở, "Huỷ gửi" ẩn.
    6. Plugin đã giành job (.running): "Huỷ gửi" ẩn, huỷ không được; xong (.done) -> mở khoá.
    7. Chỉ MỘT vòng theo dõi: gọi _watch_job hai lần cho hai job -> vòng cũ tự dừng.

Chạy:  python test_cho_lightroom.py
"""
from __future__ import annotations

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


def main() -> int:
    import autotone as at
    tam = Path(tempfile.mkdtemp(prefix="cho_lr_"))
    jobs = tam / "jobs"
    jobs.mkdir()
    buoi = tam / "BVDay3"
    buoi.mkdir()
    ten = at.ten_job(buoi.name)

    # ---- 1-2. trang thai / huy (khong can giao dien)
    j = jobs / f"apply_20261008_213022_{ten}.tsv"
    j.write_text("path\n", encoding="utf-8")
    ktra("job_state .tsv = cho", at.job_state(j) == "cho")
    chay = jobs / (j.name + ".ab12cd-1760000000-1.running")
    os.replace(j, chay)
    ktra("job_state .tsv.<id>.running = dang (plugin dang ap)", at.job_state(j) == "dang", at.job_state(j))
    ktra("huy_job khi dang ap -> da-nhan", at.huy_job(j) == "da-nhan")
    os.replace(chay, j.with_suffix(".done"))
    ktra("job_state .done = xong", at.job_state(j) == "xong")
    j2 = jobs / f"apply_20261008_213500_{ten}.tsv"
    j2.write_text("path\n", encoding="utf-8")
    ktra("huy_job job cho -> da-huy, thanh .huy",
         at.huy_job(j2) == "da-huy" and j2.with_suffix(".huy").exists() and not j2.exists())
    ktra("job_state sau huy = huy", at.job_state(j2) == "huy")
    ktra("job_dang_cho khong tinh .huy / .done", at.job_dang_cho(buoi, jobs) == [])

    # ---- 3-7. giao dien that
    try:
        import tkinter as tk
        import autotone_gui as ag
        import giao_dien as gd
        root = tk.Tk()
    except Exception as ex:                                  # noqa: BLE001
        print(f"  (bo qua phan giao dien: {ex.__class__.__name__}: {ex})")
        return 1 if LOI else 0
    ag.bq.kiem = lambda: {"co_phep": True, "con_lai": timedelta(days=300), "nhac": "",
                          "goi": "1 năm", "may": "TEST01", "het_han": False, "ly_do": ""}
    root.geometry("1500x900+0+0")
    gd.dat_theme(root)
    job_cu = at.LR_JOB_DIR
    at.LR_JOB_DIR = jobs
    try:
        app = ag.App(root)
        app.grid(row=0, column=0, sticky="nsew")

        def vong(n=4):
            for _ in range(n):
                root.update_idletasks()
                root.update()
                time.sleep(0.02)

        vong(8)
        app.v_folder.set(str(buoi))
        app.items = [{"path": str(buoi / "DC_1.ARW")}]      # co ket qua -> nut Ghi duoc mo
        app._set_busy(False)
        ktra("Dung bai: co ket qua, khong cho job -> nut Ghi mo",
             str(app.btn_ghi3.cget("state")) == "normal")

        # 3. gui xong, Lightroom chua nhan (khong co nhip plugin)
        j3 = jobs / f"apply_20261008_214000_{ten}.tsv"
        j3.write_text("path\n", encoding="utf-8")
        app._dang_cho_lr = True
        app._watch_job(j3)
        vong()
        ktra("job cho -> nut Ghi KHOA", str(app.btn_ghi3.cget("state")) == "disabled")
        ktra("job cho -> 'Huy gui' hien", bool(app.btn_huy_gui.winfo_manager()))
        chu = str(app.lbl_job.cget("text"))
        ktra("dong trang thai noi Lightroom CHUA nhan, plugin khong chay",
             "CHƯA nhận" in chu and "plugin không chạy" in chu, chu[:90])

        # 4. bam Ghi lan hai
        truoc = sorted(p.name for p in jobs.iterdir())
        app.do_apply(hoi=False)
        vong()
        ktra("bam Ghi lan hai khi dang cho -> KHONG sinh job moi",
             sorted(p.name for p in jobs.iterdir()) == truoc, str(app.lbl_status.cget("text"))[:80])

        # 7. mot vong theo doi
        j4 = jobs / f"apply_20261008_214100_{ten}.tsv"
        j4.write_text("path\n", encoding="utf-8")
        app._watch_job(j4)
        ktra("vong theo doi moi thay vong cu", app._job_dang_theo == j4)

        # 5. huy gui: huy CA HAI job cho cua buoi
        app.huy_gui()
        vong()
        ktra("Huy gui -> ca hai job thanh .huy",
             j3.with_suffix(".huy").exists() and j4.with_suffix(".huy").exists()
             and not j3.exists() and not j4.exists())
        ktra("Huy gui -> nut Ghi mo, 'Huy gui' an",
             str(app.btn_ghi3.cget("state")) == "normal" and not app.btn_huy_gui.winfo_manager()
             and not app._dang_cho_lr)

        # 6. plugin da gianh job -> khong huy duoc; xong -> mo khoa
        (jobs / at.NHIP_PLUGIN).write_text("song\n", encoding="utf-8")     # plugin dang chay
        j5 = jobs / f"apply_20261008_214500_{ten}.tsv"
        j5.write_text("path\n", encoding="utf-8")
        app._dang_cho_lr = True
        app._watch_job(j5)
        vong()
        ktra("plugin song, job cho -> 'dang cho Lightroom nhan'",
             "đang chờ Lightroom nhận" in str(app.lbl_job.cget("text")))
        r5 = jobs / (j5.name + ".zz99-1760000100-2.running")
        os.replace(j5, r5)
        app._watch_job(j5)
        vong()
        ktra("plugin da gianh -> 'Huy gui' an, nut Ghi van khoa",
             not app.btn_huy_gui.winfo_manager() and str(app.btn_ghi3.cget("state")) == "disabled",
             str(app.lbl_job.cget("text"))[:70])
        app.huy_gui()
        ktra("Huy khi Lightroom dang ap -> khong huy, van theo doi",
             r5.exists() and app._dang_cho_lr)
        os.replace(r5, j5.with_suffix(".done"))
        app._watch_job(j5)
        vong()
        ktra("Lightroom ap xong -> nut Ghi mo lai",
             str(app.btn_ghi3.cget("state")) == "normal" and not app._dang_cho_lr)
    finally:
        at.LR_JOB_DIR = job_cu
        try:
            root.destroy()
        except Exception:                                    # noqa: BLE001
            pass

    print("TAT CA DAT" if not LOI else f"{len(LOI)} LOI")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
