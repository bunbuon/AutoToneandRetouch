#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bù sáng cả buổi + Loại buổi (3/10) — kiểm bằng plan() THẬT.

CHUYỆN ĐANG SỬA
    Buổi sự kiện G:\\1005 (630 ảnh, quy trình preset mới). User xem tận mắt:
    "các bức ảnh đang hơi tối, cần tăng thêm một chút sáng thôi". 38 ảnh user
    sửa = 10 quyết định (sync theo nhóm): 9 TĂNG, 1 giảm; trung vị +0.30 EV.
    Tool để mặt đúng đích −1.19 (delta trung vị 0.00) — không phải đo sai.
    Buổi CƯỚI thì ngược lại (TrainTool −0.09, 2609 −0.13) nên KHÔNG đổi mốc
    chung; và 287/630 ảnh của 1005 do phanh chống cháy quyết định chứ không
    phải mốc, nên đổi mốc thì nửa buổi đứng yên. Cách sửa: "Loại buổi" điền
    một số "Bù sáng cả buổi", cộng vào delta CUỐI, SAU phanh và san phẳng.

Mục kiểm
    1. bu = 0 (mặc định) -> y hệt khi không có khoá, mọi trường new_*.
    2. bu = +0.30 -> ảnh có mặt: Exposure = cũ + 0.30, có cờ bu-sang+0.30.
    3. Ảnh KHÔNG có mặt (giu_nguyen_exposure) -> không đổi.
    4. Trần max_ev_up vẫn giữ: ảnh đã chạm trần không vượt.
    5. bu âm -> giảm, sàn −max_ev.
    6. Bù chỉ đụng Exposure: Highlights / Shadows / Temp / Tint đứng yên.
    7. Giao diện (khi có tkinter + màn hình): chọn "Sự kiện" -> ô bù =
       DEFAULTS["bu_sang_su_kien"] và read_cfg() mang số đó; "Cưới" -> 0;
       "Kỷ yếu" -> bù kỷ yếu và KHÔNG tự bật "Đẩy tone về da trắng hồng".

Chạy:  python test_bu_sang.py      (phần giao diện: xvfb-run -a trên Linux)
"""
from __future__ import annotations

import contextlib
import copy
import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at          # noqa: E402
import test_2ban_quay as tq    # noqa: E402

TRUONG = ("new_exposure", "new_highlights", "new_shadows", "new_temp", "new_tint")


def bo_anh(thu_muc: Path) -> list:
    """6 ảnh có mặt (mặt tối dần -> tool kéo sáng dần) + 1 ảnh không mặt."""
    items = [tq.anh(f"M{i}", i * 8, -1.9 + 0.12 * i, da=tq.DA_TRONG) for i in range(6)]
    kmat = tq.anh("K0", 60, -1.5, da=tq.DA_TRONG)
    kmat.update(faces_n=0, faces_found=0, metered_face_ev=None, meter_used="subject")
    items.append(kmat)
    for r in items:
        r["path"] = str(thu_muc / Path(r["path"].replace("\\", "/")).name)
    return items


def chay(items, thu_muc: Path, **kw) -> dict:
    its = copy.deepcopy(items)
    exp = {at.khoa_duong_dan(r["path"]): dict(tq.PRESET) for r in its}
    cfg = dict(at.DEFAULTS, source="catalog", bo_qua_nguoi_sua=False)
    cfg.update(kw)
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        at.plan(its, cfg, thu_muc, exp)
    return {Path(r["path"]).stem: r for r in its}


def main() -> int:
    loi: list = []
    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "1005"
        d.mkdir()
        items = bo_anh(d)

        goc = chay(items, d)                                    # không khoá nào
        khong = chay(items, d, bu_sang_ca_buoi=0.0)
        if any(goc[k][t] != khong[k][t] for k in goc for t in TRUONG):
            loi.append("bu = 0 phai y het khi khong co khoa")
        if not goc["K0"].get("giu_nguyen_exposure"):
            loi.append("Dung bai: anh K0 phai la anh 'khong mat, giu nguyen' — bai kiem muc 3 vo nghia")
        co_mat = [k for k in goc if k != "K0"]
        if not any(goc[k]["new_exposure"] > 0.05 for k in co_mat):
            loi.append("Dung bai: tool phai keo sang it nhat mot anh co mat")

        bu = chay(items, d, bu_sang_ca_buoi=0.30, max_ev_up=3.0)
        nen = chay(items, d, max_ev_up=3.0)
        for k in co_mat:
            mong = round(nen[k]["new_exposure"] + 0.30, 2)
            if abs(bu[k]["new_exposure"] - mong) > 0.011:
                loi.append(f"{k}: bu +0.30 phai ra {mong:+.2f}, dang {bu[k]['new_exposure']:+.2f}")
            if "bu-sang+0.30" not in bu[k].get("notes", ""):
                loi.append(f"{k}: thieu co bu-sang+0.30 trong notes")
            for t in TRUONG[1:]:
                if bu[k][t] != nen[k][t]:
                    loi.append(f"{k}: bu sang khong duoc dung {t} ({nen[k][t]} -> {bu[k][t]})")
        if bu["K0"]["new_exposure"] != nen["K0"]["new_exposure"]:
            loi.append("Anh khong mat (giu nguyen) bi bu sang — pha luat 'khong mat thi khong chinh'")

        # 4. tran max_ev_up van giu
        tran = 0.2
        sat = chay(items, d, max_ev_up=tran)
        sat_bu = chay(items, d, max_ev_up=tran, bu_sang_ca_buoi=0.30)
        cham = [k for k in co_mat if sat[k]["new_exposure"] >= tran - 1e-6]
        if not cham:
            loi.append("Dung bai: phai co anh cham tran max_ev_up")
        for k in cham:
            if sat_bu[k]["new_exposure"] > tran + 1e-6:
                loi.append(f"{k}: da cham tran {tran} ma bu sang day len {sat_bu[k]['new_exposure']:+.2f}")

        # 5. bu am, san -max_ev
        am = chay(items, d, max_ev_up=3.0, bu_sang_ca_buoi=-0.25)
        for k in co_mat:
            mong = max(round(nen[k]["new_exposure"] - 0.25, 2), -float(at.DEFAULTS["max_ev"]))
            if abs(am[k]["new_exposure"] - mong) > 0.011:
                loi.append(f"{k}: bu -0.25 phai ra {mong:+.2f}, dang {am[k]['new_exposure']:+.2f}")

    loi += kiem_giao_dien()
    for m in loi:
        print("  [!]", m)
    print("TAT CA DAT" if not loi else f"{len(loi)} LOI")
    return 1 if loi else 0


def kiem_giao_dien() -> list:
    try:
        import tkinter as tk
        import autotone_gui as ag
        root = tk.Tk()
    except Exception as ex:                          # noqa: BLE001
        print(f"  (bo qua phan giao dien: {ex.__class__.__name__}: {ex})")
        return []
    loi = []
    try:
        root.withdraw()
        app = ag.App(root)
        if float(app.read_cfg().get("bu_sang_ca_buoi", -9)) != 0.0:
            loi.append("Giao dien mo len phai la bu sang 0 (Cuoi)")
        nhan = dict((m, n) for n, m in ag.LOAI_BUOI)
        app.v_loai_buoi.set(nhan["su_kien"])
        app._doi_loai_buoi()
        mong = float(at.DEFAULTS["bu_sang_su_kien"])
        cfg = app.read_cfg()
        if abs(float(app.v_bu_sang.get()) - mong) > 1e-9 or abs(cfg["bu_sang_ca_buoi"] - mong) > 1e-9:
            loi.append(f"Chon 'Su kien': o bu = {app.v_bu_sang.get()}, cfg = {cfg.get('bu_sang_ca_buoi')}, phai {mong}")
        if cfg.get("loai_buoi") != "su_kien":
            loi.append(f"read_cfg loai_buoi = {cfg.get('loai_buoi')}, phai su_kien")
        app.v_bu_sang.set("0.45")                     # user tu sua o so
        if abs(app.read_cfg()["bu_sang_ca_buoi"] - 0.45) > 1e-9:
            loi.append("Sua tay o bu sang thi read_cfg phai lay dung so do")
        app.v_loai_buoi.set(nhan["cuoi"])
        app._doi_loai_buoi()
        if abs(app.read_cfg()["bu_sang_ca_buoi"]) > 1e-9:
            loi.append("Chon lai 'Cuoi' phai tra bu sang ve 0")
        #  8/10 vong 3: Ky yeu KHONG tu bat Color Grading trang hong nua
        app.v_grade.set(False)
        app.v_loai_buoi.set(nhan["ky_yeu"])
        app._doi_loai_buoi()
        cfg = app.read_cfg()
        if cfg.get("loai_buoi") != "ky_yeu" or abs(cfg["bu_sang_ca_buoi"] - float(at.DEFAULTS["bu_sang_ky_yeu"])) > 1e-9:
            loi.append(f"Chon 'Ky yeu': loai {cfg.get('loai_buoi')}, bu {cfg.get('bu_sang_ca_buoi')}")
        if app.v_grade.get() or cfg.get("grade"):
            loi.append("Chon 'Ky yeu' khong duoc tu bat 'Day tone ve da trang hong'")
    finally:
        root.destroy()
    return loi


if __name__ == "__main__":
    sys.exit(main())
