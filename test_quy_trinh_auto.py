# -*- coding: utf-8 -*-
"""Quy trình Auto Lightroom (16/10; chính thức 17/10) — lõi + luồng hộp Xử lý ảnh.

User 16/10: "Khách hàng Import 1 bộ ảnh vào Lightroom -> Chọn preset của họ -> Xuất thông số cho
AutoTone bắt đầu xử lý. Đổi quy trình sang bước đầu tiên sau khi nhận đc thông số. Bật chế độ Auto
của phần Basic của tất cả các ảnh -> Đo các thông số hiện tại trên vùng da để bắt đầu căn chỉnh lại
cho về với da đích -> WB -> Tone -> Curve RGB -> Áp lại LR -> Kiểm tra lại sau khi add thông số mới
đã về với da đích chưa -> Nếu chưa thì xử lý WB -> Tone -> áp lại LR". Chọn: chế độ bật / tắt,
GIỮ tông Auto (tool chỉ đổi WB, Exposure, Curve R/G/B), tối đa 2 vòng kiểm.

  1. giu_auto: mốc = số Auto (Exposure / HL / SH / Contrast / Whites / Blacks), chỉnh tự động của
     tool về 0, GIỮ bù người dùng (Bù sáng / K / Tint cả buổi); ảnh không có số Auto / đen trắng
     không đụng. plan() gọi nó khi bật quy trình (nguồn catalog).
  2. danh_dau_nguoi_sua: ảnh vừa được Lightroom Auto không bị coi là "sửa tay".
  3. tone_da_luot2: da tối hơn đích -> tăng (trần +0.3), sáng hơn -> giảm (trần −0.6), lệch nhỏ
     giữ, một mức mỗi loạt; tắt quy trình -> không làm. ghi_job có cột Exposure2012.
  4. Luồng: công tắc nhớ + read_cfg (một lượt + Curve R/G/B, HSL / CG / đường S tắt); hộp có bước
     "Auto Lightroom"; gửi Auto -> plugin xong -> số Auto gắn vào ảnh -> tính lại -> Áp; Dừng lúc
     chờ; plugin cũ -> chạy như thường + nói rõ; vòng kiểm: số mới vào ảnh, tối đa 2 vòng.
Chạy:  python test_quy_trinh_auto.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from datetime import datetime, timedelta
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
    tam = Path(tempfile.mkdtemp(prefix="quy_trinh_auto_"))
    os.environ["AUTOTONE_DATA"] = str(tam / "du_lieu")
    os.environ["AUTOTONE_CATALOG_LR"] = "0"
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import numpy as np
    import autotone as at
    import auto_lr
    import curve_da as cd
    import curve_lr as cl
    import test_2ban_quay as tq
    jobs = tam / "jobs"
    jobs.mkdir()
    job_cu = at.LR_JOB_DIR
    at.LR_JOB_DIR = jobs
    try:
        print("1. giu_auto")
        PRESET = {"Exposure2012": "0.50", "Highlights2012": "-29", "Shadows2012": "16",
                  "Contrast2012": "5", "Whites2012": "-25", "Blacks2012": "-18",
                  "Temperature": "5000", "Tint": "10", "WhiteBalance": "Custom"}
        AUTO = {"Exposure2012": -0.37, "Contrast2012": 7.0, "Highlights2012": -32.0, "Shadows2012": 40.0,
                "Whites2012": 45.0, "Blacks2012": -27.0, "Vibrance": 14.0, "Saturation": 0.0,
                "Temperature": 5000.0, "Tint": 10.0, "WhiteBalance": "Custom"}
        cfg0 = dict(at.DEFAULTS, source="catalog", wb="skin", quy_trinh_auto=True)

        def r_(ten, auto=True, **kw):
            r = tq.anh(ten, 0, -1.2, da=tq.DA_TRONG)
            r.update(path=str(tam / f"{ten}.ARW"), crs=dict(PRESET), atn={}, delta_ev=0.4, hl_adj=-10,
                     meter_boxes=[[10, 10, 50, 60]], fnumber=2.8, exposure_time=1 / 200, iso=800,
                     scene=0, scene_sig=[0.5] * 16, metered_subject_ev=-2.0,
                     sh_adj=8, temp_adj=-300.0, tint_adj=4.0, cv_dk=-6, cv_lt=6, **kw)
            if auto:
                r["lr_auto"] = dict(AUTO)
            at.compute_values(r, cfg0, r["crs"], r["atn"])
            return r
        a, b, bw = r_("A"), r_("B", auto=False), r_("BW", bw=True)
        n = at.giu_auto([a, b, bw], dict(cfg0, bu_sang_ca_buoi=0.2, bu_k_ca_buoi=150.0, bu_tint_ca_buoi=-2.0))
        ktra("ảnh có số Auto: mốc = số Auto; tool chỉ cộng bù người dùng (Bù sáng +0.2, K +150, Tint −2)",
             n == 1 and abs(a["new_exposure"] - (-0.37 + 0.2)) < 1e-6 and a["new_highlights"] == -32
             and a["new_shadows"] == 40 and a["new_temp"] == 5150 and a["new_tint"] == 8,
             f"EV {a['new_exposure']} HL {a['new_highlights']} SH {a['new_shadows']} WB {a['new_temp']}/{a['new_tint']}")
        ktra("…Contrast / Whites / Blacks của Auto được giữ (ghi lại đúng số Auto)",
             a.get("new_Contrast2012") == 7 and a.get("new_Whites2012") == 45 and a.get("new_Blacks2012") == -27)
        ktra("…chỉnh tự động của tool (delta / HL / SH / đường S) về 0",
             a["hl_adj"] == 0 and a["sh_adj"] == 0 and a["cv_dk"] == 0 and a["cv_lt"] == 0
             and "quy-trinh-auto" in a["notes"])
        ktra("…ảnh chưa có số Auto / đen trắng: không đụng",
             b["new_highlights"] == -39 and b["hl_adj"] == -10 and bw.get("lr_auto")
             and bw["hl_adj"] == -10, f"B HL {b['new_highlights']} · BW hl_adj {bw['hl_adj']}")
        src = Path(at.__file__).read_text(encoding="utf-8")
        ktra("plan() gọi giu_auto khi bật quy trình (nguồn catalog), TRƯỚC chuỗi màu da",
             src.index("giu_auto(items, cfg)") < src.index("chinh_mau_da(items, cfg, folder)")
             and 'cfg.get("quy_trinh_auto") and cfg.get("source") == "catalog"' in src)

        print("1b. tông Auto của TỪNG ảnh (16/10 TestAnhCuoi: đồng bộ cụm chép tông đại diện)")
        T_C = datetime(2026, 10, 15, 14, 57, 40)
        SIG_C = list(np.linspace(0.2, 0.8, 72))

        def cum(ten, giay, hl, sh, wh=16, bl=-17, ev=-0.3):
            st = {"Exposure2012": ev, "Highlights2012": hl, "Shadows2012": sh, "Contrast2012": 6,
                  "Whites2012": wh, "Blacks2012": bl}
            return {"path": str(tam / f"{ten}.ARW"), "dt_obj": T_C + timedelta(seconds=giay), "model": "ILCE-7M4",
                    "fnumber": 3.5, "exposure_time": 1 / 400, "iso": 100, "flash": 16, "scene_sig": SIG_C,
                    "metered_subject_ev": -2.0, "meter_boxes": [[10, 10, 50, 60]], "old_exposure": ev,
                    "new_exposure": ev, "delta_ev": 0.0, "old_temp": 5250, "old_tint": 16, "new_temp": 5550,
                    "new_tint": 22, "new_highlights": hl, "new_shadows": sh, "new_Contrast2012": 6,
                    "new_Whites2012": wh, "new_Blacks2012": bl, "crs": {}, "crs_hien": {}, "notes": "",
                    "lr_auto": st}
        cum_ds = [cum("C1", 0, -77, 47), cum("C2", 1, -77, 50, wh=17, ev=-0.38), cum("C3", 2, -76, 49, bl=-19)]
        nhom_c = at.nhom_cum(cum_ds, cfg0)
        at.dong_bo_cum(cum_ds, cfg0)
        ktra("đồng bộ cụm cùng khung: KHÔNG chép tông của ảnh đại diện — mỗi ảnh giữ HL / SH / Whites / "
             "Blacks Auto của nó",
             len(nhom_c) == 1 and len(nhom_c[0]) == 3
             and [(r["new_highlights"], r["new_shadows"], r["new_Whites2012"], r["new_Blacks2012"]) for r in cum_ds]
             == [(-77, 47, 16, -17), (-77, 50, 17, -17), (-76, 49, 16, -19)],
             str([(r["new_highlights"], r["new_shadows"]) for r in cum_ds]))
        cum_ds[0]["new_highlights"], cum_ds[1]["new_shadows"] = -10, 0
        n_g = at.giu_tong_auto(cum_ds, cfg0)
        ktra("giu_tong_auto (chốt cuối plan): bước nào đổi tông Auto cũng trả lại đúng số Auto của ảnh",
             n_g == 2 and cum_ds[0]["new_highlights"] == -77 and cum_ds[1]["new_shadows"] == 50
             and "giu-tong-auto" in cum_ds[0]["notes"], f"{n_g}")
        cum_ds[0]["new_highlights"] = -10
        ktra("…tắt quy trình Auto -> không đụng",
             at.giu_tong_auto(cum_ds, dict(cfg0, quy_trinh_auto=False)) == 0 and cum_ds[0]["new_highlights"] == -10)
        ktra("plan() gọi giu_tong_auto SAU dong_bo_cum (bước cuối)",
             src.rindex("giu_tong_auto(items, cfg)") > src.rindex("dong_bo_cum(items, cfg)"))

        print("1c. đích SÁNG của da (16/10 khuya — 'bù +0.3 mà vẫn tối hơn 0.5 EV')")
        import curve_da as cdm
        cfg_d = dict(at.DEFAULTS, source="catalog", loai_buoi="cuoi")
        cfg_d["mau_da_dich"] = at.dich_mac_dinh(cfg_d)
        r_ng = {"fnumber": 3.5, "exposure_time": 1 / 400, "iso": 100, "flash": 16, "ngoai_troi": True}
        r_tr = {"fnumber": 2.8, "exposure_time": 1 / 100, "iso": 1600, "flash": 13, "ngoai_troi": False}
        Lab = lambda rgb: at.mau_dich_lab(rgb)                                       # noqa: E731
        ng0, tr0 = Lab(cdm.dich_cua(r_ng, cfg_d, "cu")[0]), Lab(cdm.dich_cua(r_tr, cfg_d, "cu")[0])
        h_ng = np.degrees(np.arctan2(ng0[2], ng0[1]))
        h_ram = np.degrees(np.arctan2(Lab(cfg_d["mau_da_dich"]["ngoai"])[2], Lab(cfg_d["mau_da_dich"]["ngoai"])[1]))
        ktra("mẫu Mặc định NGOÀI TRỜI: độ sáng = khe trong nhà (da trắng hồng), màu (hue) vẫn của da rám",
             abs(ng0[0] - tr0[0]) < 0.003 and abs(h_ng - h_ram) < 0.5 and ng0[0] > 0.70,
             f"L ngoài {ng0[0]:.3f} / trong {tr0[0]:.3f} · hue {h_ng:.1f}° (rám {h_ram:.1f}°)")
        ng3 = Lab(cdm.dich_cua(r_ng, dict(cfg_d, bu_sang_ca_buoi=0.3), "cu")[0])
        ktra("bù sáng cả buổi +0.3 -> L đích × 2^(0.3/3) (bước Tone / duyệt lại không xoá phần bù)",
             abs(ng3[0] / ng0[0] - 2 ** 0.1) < 0.004, f"{ng0[0]:.3f} -> {ng3[0]:.3f}")
        lv = {"ten": "LVQ", "trong": [218, 184, 165], "ngoai": [237, 199, 190]}
        Lv = Lab(cdm.dich_cua(r_ng, dict(cfg_d, mau_da_dich=lv), "cu")[0])[0]
        ktra("mẫu có tên (học từ ảnh sửa): ngoài trời giữ độ sáng của chính nó (− da_dich_L_bu)",
             abs(Lv - (Lab(lv["ngoai"])[0] + at.DEFAULTS["da_dich_L_bu"])) < 0.003, f"{Lv:.3f}")

        print("2. danh_dau_nguoi_sua bỏ qua ảnh vừa Auto")
        goc_ls = at._lich_su_ghi
        at._lich_su_ghi = lambda folder, job_dir=None: ({"a": {"Exposure2012": "0.90"}, "b": {"Exposure2012": "0.90"}}, {})
        a2, b2 = r_("A"), r_("B", auto=False)
        hien = {at.khoa_duong_dan(a2["path"]): {"Exposure2012": -0.37},
                at.khoa_duong_dan(b2["path"]): {"Exposure2012": -0.37}}
        n_s = at.danh_dau_nguoi_sua([a2, b2], {}, tam, hien=hien)
        at._lich_su_ghi = goc_ls
        ktra("số khác lần ghi trước: ảnh vừa Auto KHÔNG sửa tay, ảnh thường vẫn bị nhận",
             n_s == 1 and not a2.get("nguoi_sua") and b2.get("nguoi_sua"), f"{n_s}")
        #  16/10 TEST: dừng quy trình Auto giữa chừng -> ảnh đã Auto mang số Auto, job cuối của tool
        #  ghi số khác. Lượt SAU (chưa có lr_auto) phải nhờ bản ghi ghi_auto_* mà không nhận nhầm.
        b_auto = tam / "BuoiAuto"
        b_auto.mkdir()
        tj = at.ten_job(b_auto.name)
        (jobs / f"apply_20261016_170230_{tj}.done").write_text(
            "path\tExposure2012\tContrast2012\tTemperature\n"
            f"{tam / 'A.ARW'}\t+0.90\t5\t5200\n{tam / 'B.ARW'}\t+0.90\t5\t5200\n", encoding="utf-8")
        (jobs / "auto_anh.tsv").write_text(
            "#ma=m-dung\npath\t" + "\t".join(auto_lr.O) + "\n"
            + f"{tam / 'A.ARW'}\t-0.37\t7\t-32\t40\t45\t-27\t14\t0\t5200\t10\tCustom\n", encoding="utf-8")
        f_ls = auto_lr.ghi_lich_su("m-dung", b_auto, job_dir=jobs)
        ktra("auto_lr.ghi_lich_su: ghi_auto_<giờ>_<buổi>.done, chỉ ô tông Auto (không WB), KHÔNG theo mẫu apply_*",
             f_ls is not None and f_ls.name.startswith("ghi_auto_") and f_ls.name.endswith(f"_{tj}.done")
             and "Temperature" not in f_ls.read_text(encoding="utf-8")
             and not list(jobs.glob(f"apply_*_{tj}@auto*")), str(f_ls))
        ktra("…mã lượt khác -> không ghi", auto_lr.ghi_lich_su("m-khac", b_auto, job_dir=jobs) is None)
        a3, b3 = r_("A", auto=False), r_("B", auto=False)
        hien3 = {at.khoa_duong_dan(a3["path"]): {"Exposure2012": "-0.37", "Contrast2012": "7",
                                                  "Temperature": "5200"},
                 at.khoa_duong_dan(b3["path"]): {"Exposure2012": "-0.37", "Contrast2012": "7",
                                                  "Temperature": "5200"}}
        n3 = at.danh_dau_nguoi_sua([a3, b3], {}, b_auto, hien=hien3)
        ktra("lượt sau: ảnh trong bản ghi Auto (số = Auto) KHÔNG sửa tay; ảnh ngoài bản ghi vẫn bị nhận",
             n3 == 1 and not a3.get("nguoi_sua") and b3.get("nguoi_sua"), f"{n3}")
        (jobs / f"apply_20991231_235959_{tj}.done").write_text(       # giờ SAU bản ghi Auto (giờ thật)
            f"path\tExposure2012\n{tam / 'A.ARW'}\t+0.10\n", encoding="utf-8")
        a4 = r_("A", auto=False)
        n4 = at.danh_dau_nguoi_sua([a4], {}, b_auto, hien={at.khoa_duong_dan(a4["path"]): {"Exposure2012": "-0.37"}})
        ktra("…job chính ghi SAU bản ghi Auto đặt lại mốc so (xếp theo giờ trong tên, hai tiền tố)",
             n4 == 1 and a4.get("nguoi_sua"), f"{n4}")
        for f_ in [*jobs.glob(f"*_{tj}.done"), jobs / "auto_anh.tsv"]:
            f_.unlink()
        #  16/10 TEST: chỉ có bản ghi Auto (chưa job chính) rồi user Synchronize Settings cả loạt
        #  -> buoi_dat_lai phải nhận "đặt lại" (không coi cả loạt là sửa tay)
        b_dl = tam / "BuoiDongBo"
        b_dl.mkdir()
        tj2 = at.ten_job(b_dl.name)
        dong_dl = ["path\t" + "\t".join(auto_lr.O_TONE)]
        xuat_dl = {}
        for i in range(12):
            p_ = str(b_dl / f"S{i:02d}.ARW")
            dong_dl.append(f"{p_}\t{-0.6 + 0.07 * i:.2f}\t7\t{-40 - i}\t{20 + i}\t10\t-15\t14\t0")
            xuat_dl[at.khoa_duong_dan(p_)] = {"Exposure2012": "0.30", "Highlights2012": "-29",
                                               "Shadows2012": "16"}
        (jobs / f"ghi_auto_20261016_194924_{tj2}.done").write_text("\n".join(dong_dl) + "\n", encoding="utf-8")
        at.baseline_path(b_dl).write_text("path\n", encoding="utf-8")
        ds_dl = [{"path": str(b_dl / f"S{i:02d}.ARW")} for i in range(12)]
        ktra("chỉ có bản ghi Auto, user đồng bộ cả loạt về một bộ số -> buoi_dat_lai nhận 'dat-lai'",
             at.buoi_dat_lai(ds_dl, xuat_dl, b_dl) == "dat-lai", at.buoi_dat_lai(ds_dl, xuat_dl, b_dl))
        for f_ in jobs.glob(f"*_{tj2}.done"):
            f_.unlink()

        print("3. tone_da_luot2 (vòng kiểm — Exposure theo da đo thật)")
        DICH = [227, 184, 185]
        cfg3 = dict(cfg0, mau_da_dich={"ten": "m", "trong": DICH, "ngoai": DICH}, da_dich_L_bu=0.0)
        lt = float(at.mau_dich_lab(DICH)[0])

        def do_(L_ti):
            """da cùng màu đích, độ sáng L_ti × L đích (OkLab) — miền Melissa như do_anh."""
            lin = at.srgb_to_linear(np.asarray(DICH, float) / 255.0) * (L_ti ** 3)
            px = np.tile(at.linear_to_srgb(np.clip(lin, 0, 1)), (200, 1))
            return {"ok": True, "mien": "melissa", "da_cu": cl.srgb_sang_mien(px, "melissa")}

        def loat(ten, giay, n_=3):
            ds = []
            for i in range(n_):
                r = r_(f"{ten}{i}")
                r["dt_obj"] = r["dt_obj"] + timedelta(seconds=giay + 2 * i)
                r["new_exposure"] = 0.1
                ds.append(r)
            return ds
        toi = loat("T", 0)
        cd.dich_cua(toi[0], cfg3, "cu")
        n_t = at.tone_da_luot2([toi[0]], {id(toi[0]): do_(0.85)}, cfg3, tat_ca=toi)
        ktra("da TỐI hơn đích -> Exposure tăng, trần +0.3, cả loạt (kể cả tấm không đo)",
             n_t == 3 and all(abs(r["tone_l2"] - 0.4) < 1e-6 for r in toi), str([r.get("tone_l2") for r in toi]))
        sang = loat("S", 900)
        at.tone_da_luot2([sang[0]], {id(sang[0]): do_(1.10)}, cfg3, tat_ca=sang)
        e_s = sang[0].get("tone_l2")
        ktra("da SÁNG hơn đích -> Exposure giảm (0.7 quãng của 3·log2), trong trần −0.6",
             e_s is not None and -0.5 < e_s - 0.1 < -0.2, str(e_s))
        gan = loat("G", 1800)
        at.tone_da_luot2([gan[0]], {id(gan[0]): do_(1.005)}, cfg3, tat_ca=gan)
        ktra("lệch nhỏ (< 0.1 EV) -> giữ", all(r.get("tone_l2") is None for r in gan))
        tat = loat("X", 2700)
        at.tone_da_luot2([tat[0]], {id(tat[0]): do_(0.85)}, dict(cfg3, quy_trinh_auto=False), tat_ca=tat)
        ktra("tắt quy trình Auto -> không làm", all(r.get("tone_l2") is None for r in tat))
        toi[0]["wb_l2"] = (5100, 8)
        job = cd.ghi_job(toi, "Buoi", jobs)
        dong = job.read_text(encoding="utf-8").splitlines()
        cot = dong[0].split("\t")
        ktra("job vòng kiểm: cột Exposure2012 (+ Temperature / Tint), mọi ảnh có số mới",
             "Exposure2012" in cot and "Temperature" in cot and len(dong) == 4
             and all(d.split("\t")[cot.index("Exposure2012")] == "+0.40" for d in dong[1:]), dong[0])
        job.unlink()

        print("4. luồng hộp Xử lý ảnh")
        import tkinter as tk
        import autotone_gui as ag
        import giao_dien as gd
        import thanh_luoi
        import xu_ly_anh_ui as xu
        (jobs / at.NHIP_PLUGIN).write_text("vong=1\nkha_nang=curve1,xem1,truoc1,auto1\n", encoding="utf-8")
        root = tk.Tk()
        ag.bq.kiem = lambda: {"co_phep": True, "con_lai": timedelta(days=300), "nhac": "",
                              "goi": "1 năm", "may": "TEST01", "het_han": False, "ly_do": ""}
        root.geometry("1600x940+0+0")
        gd.dat_theme(root)
        try:
            app = ag.App(root)
            app.grid(row=0, column=0, sticky="nsew")

            def vong(k=4):
                for _ in range(k):
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
            buoi = tam / "Buoi"
            buoi.mkdir()
            app.folder = lambda: buoi
            doc_cfg = app.read_cfg
            app.source_value = lambda: "catalog"
            ktra("17/10 bản chính thức: công tắc Quy trình Auto mặc định BẬT (máy mới)",
                 bool(app.v_auto_lr.get()) is True)
            app.v_auto_lr.set(True)
            c = doc_cfg()
            ktra("công tắc bật (nguồn catalog) -> read_cfg: quy trình Auto + một lượt; Curve R/G/B THEO Ô "
                 "(không ép); HSL / CG / đường S tắt",
                 c.get("quy_trinh_auto") and c.get("mau_mot_luot")
                 and bool(c.get("curve_da")) == bool(app.v_curve_da.get())
                 and not c.get("hsl_da_cuoi") and not c.get("grade") and not c.get("curve"), str({k: c.get(k) for k in (
                     "quy_trinh_auto", "mau_mot_luot", "curve_da", "hsl_da_cuoi", "grade", "curve")}))
            ktra("…nhớ vào luoi_xem.json", thanh_luoi.doc_kv("quy_trinh_auto_chinh") is True)
            app.read_cfg = lambda: dict(doc_cfg(), mau_mot_luot=False)     # không mô hình -> không đo trước
            ap_goi = []
            app.do_apply = lambda **kw: ap_goi.append(kw)
            app._plan_tinh = lambda: None
            app._plan_ve = lambda: None
            ds = [dict(r_(f"U{i}", auto=False), path=str(buoi / f"U{i}.ARW")) for i in range(3)]

            def mo_luot(items):
                t = time.monotonic()
                app._xl = {"t0": t - 2.0, "pha": "do", "hop": None, "xong": False, "items_ghi": items,
                           "so_gui": len(items), "moc": {"phan_tich": t - 1.0}}
                app._xl_bat_dau(0, len(items), len(items))
                return app._xl["hop"]
            app.items = ds
            hop = mo_luot(ds)
            ktra("hộp KHÔNG có dòng 'Auto Lightroom' riêng — Auto nằm trong 'Phân tích ảnh' (Phân tích -> Áp)",
                 "auto" not in hop.hang and list(hop.hang)[:2] == ["do", "ap"], str(list(hop.hang)))
            app.cancel_flag = False
            at.CANH_BAO_XUAT = at.CANH_BAO_PLUGIN = ""
            ds[0]["meter_boxes"] = []                 # ảnh không mặt -> gửi CUỐI (ảnh thử là ảnh có mặt)
            app._xl_sau_do(ds, app.read_cfg())
            yc = jobs / auto_lr.TEN_YEU_CAU
            dong_yc = ([d for d in yc.read_text(encoding="utf-8").splitlines() if not d.startswith("#")]
                       if yc.is_file() else [])
            ktra("phân tích xong -> gửi lệnh Auto (đủ 3 ảnh), pha 'auto', chưa Áp",
                 len(dong_yc) == 3 and app._xl.get("pha") == "auto" and not ap_goi, str(app._xl.get("pha")))
            ktra("…ảnh có mặt lên trước (plugin thử cách gom trên vài ảnh đầu), ảnh không mặt cuối",
                 dong_yc == [ds[1]["path"], ds[2]["path"], ds[0]["path"]], str(dong_yc))
            ktra("…dòng Phân tích ảnh CHƯA xong mà báo 'Lightroom đang bấm Auto…'",
                 hop.tt.get("do") == "dang" and "bấm Auto" in str(hop.hang["do"][2].cget("text")),
                 f"{hop.tt.get('do')} · {hop.hang['do'][2].cget('text')}")
            ds[0]["meter_boxes"] = [[10, 10, 50, 60]]
            ma = app._xl["auto_ma"]
            yc.unlink()                                       # "plugin" nhận
            f_td = jobs / auto_lr.TEN_TIEN_DO
            f_td.write_text(f"ma={ma}\nxong=1\ntong=3\ntrang_thai=dang_chay\n", encoding="utf-8")
            cho(lambda: "1 / 3" in str(hop.lbl_td.cget("text")), 5)
            ktra("…tiến độ Auto hiện dưới Phân tích ảnh ('Lightroom bấm Auto 1 / 3 ảnh')",
                 "Lightroom bấm Auto 1 / 3 ảnh" in str(hop.lbl_td.cget("text")), str(hop.lbl_td.cget("text")))
            app._xl["t_auto_dau"] -= 10
            app._xl["auto_x0"] = 0
            f_td.write_text(f"ma={ma}\nxong=2\ntong=3\ntrang_thai=dang_chay\n", encoding="utf-8")
            cho(lambda: "2 / 3" in str(hop.lbl_td.cget("text")), 5)
            ktra("…có ước lượng còn bao lâu (2 ảnh / 10 giây -> 'còn ~5 giây')",
                 "còn ~5 giây" in str(hop.lbl_td.cget("text")), str(hop.lbl_td.cget("text")))
            bang = ["#ma=" + ma, "path\t" + "\t".join(auto_lr.O)]
            for r in ds:
                bang.append("\t".join([r["path"]] + [str(AUTO[k]) for k in auto_lr.O]))
            (jobs / auto_lr.TEN_BANG).write_text("\n".join(bang) + "\n", encoding="utf-8")
            (jobs / auto_lr.TEN_KET_QUA).write_text(f"ma={ma}\ntong=3\nbat=3\nlo=1\ncach=gom\ngiay=190\n",
                                                   encoding="utf-8")
            ok = cho(lambda: bool(ap_goi), 15)
            ktra("plugin xong -> số Auto gắn vào ảnh, Phân tích ảnh 'xong' (không dòng Auto), tính lại rồi ÁP",
                 ok and all(r.get("lr_auto", {}).get("Exposure2012") == -0.37 for r in ds)
                 and hop.tt.get("do") == "xong" and "auto" not in hop.tt and app._xl.get("auto_n") == 3,
                 f"ap {len(ap_goi)} · {hop.tt}")
            ls_ = list(jobs.glob(f"ghi_auto_*_{at.ten_job(buoi.name)}.done"))
            ktra("…số Auto vào lịch sử ghi của tool (ghi_auto_*): đủ 3 ảnh -> lượt sau không nhận nhầm sửa tay",
                 len(ls_) == 1 and len(ls_[0].read_text(encoding="utf-8").splitlines()) == 4
                 and all(v.get("Exposure2012") == "-0.37" for v in at.lan_ghi_cuoi(buoi).values())
                 and len(at.lan_ghi_cuoi(buoi)) == 3, str(ls_))
            app._xl["items_ghi"] = ds
            app._xl_ket_thuc("xong")
            ktra("…tổng kết nói Lightroom mất bao lâu ('bấm Auto 3 ảnh trong 3 phút 10 giây')",
                 "bấm Auto 3 ảnh trong 3 phút 10 giây" in hop.lbl_tong.cget("text"),
                 hop.lbl_tong.cget("text")[:200])
            #  Dừng lúc Lightroom chưa nhận lệnh Auto
            hop.destroy()
            for r in ds:
                r.pop("lr_auto", None)
            hop = mo_luot(ds)
            app._xl_sau_do(ds, app.read_cfg())
            app._xl_dung()
            vong(3)
            ktra("Dừng khi Lightroom chưa nhận lệnh Auto -> rút lệnh, 'Đã dừng', không Áp",
                 app._xl.get("xong") and not yc.is_file() and len(ap_goi) == 1
                 and "dừng" in str(hop.lbl_tieu_de.cget("text")).lower())
            #  plugin cũ (không khai auto1) -> chạy như thường, tổng kết nói rõ
            hop.destroy()
            (jobs / at.NHIP_PLUGIN).write_text("vong=1\nkha_nang=curve1,xem1,truoc1\n", encoding="utf-8")
            hop = mo_luot(ds)
            app._xl_sau_do(ds, app.read_cfg())
            cho(lambda: len(ap_goi) >= 2, 10)
            app._xl["items_ghi"] = ds
            app._xl_ket_thuc("xong")
            ktra("plugin cũ -> không gửi Auto, Áp như thường, tổng kết nói cần bộ cài đầy đủ",
                 len(ap_goi) == 2 and not yc.is_file() and "bộ cài đầy đủ" in hop.lbl_tong.cget("text"),
                 hop.lbl_tong.cget("text")[:160])
            hop.destroy()
            #  16/10 tối: áp MỘT lần — không còn lượt kiểm dựng lại ảnh sau khi áp
            den = []
            app._xl_denoise = lambda: den.append(1)
            hop = mo_luot(ds)
            app._xl.update(auto=True, curve=True, wb_da_can=True)
            app._xl_curve()
            del app._xl_denoise
            ktra("quy trình Auto: áp xong đi thẳng Denoise / kết thúc — không dựng lại ảnh để kiểm",
                 den == [1] and app._xl.get("pha") != "curve", str(app._xl.get("pha")))
            hop.destroy()

            #  16/10 tối: lệnh Auto gửi NGAY khi lượt bắt đầu (song song phân tích), preview Lightroom
            #  chụp trước Auto, ảnh người dùng sửa tay không bấm Auto
            import do_truoc as dtm
            (jobs / at.NHIP_PLUGIN).write_text("vong=1\nkha_nang=curve1,xem1,truoc1,auto1\n", encoding="utf-8")
            tj_b = at.ten_job(buoi.name)
            for f_ in jobs.glob(f"*_{tj_b}.done"):              # lịch sử ghi của các mục trên
                f_.unlink()
            (jobs / f"apply_20261016_170000_{tj_b}.done").write_text(
                f"path\tExposure2012\n{ds[1]['path']}\t+0.90\n", encoding="utf-8")
            at.baseline_path(buoi).write_text("path\n", encoding="utf-8")
            chup_gia = {"ma": "c1", "thu_muc": None, "pv": {},
                        "anh": {at.khoa_duong_dan(r["path"]): {"path": r["path"],
                                                                "text": "s = { Exposure2012 = -0.20, }"}
                                for r in ds}}
            goi_chup = []
            cu_chup = dtm.chup_cache
            dtm.chup_cache = lambda root, catalog=None, chi=None: (goi_chup.append(sorted(chi or [])),
                                                                    chup_gia)[1]

            def mo_som(items):
                t = time.monotonic()
                app._xl = {"t0": t - 2.0, "pha": "do", "hop": None, "xong": False, "items_ghi": items,
                           "so_gui": len(items), "moc": {"phan_tich": t - 1.0}}
                app._xl_bat_dau(len(items), 0, len(items), anh=[r["path"] for r in items])
                return app._xl["hop"]
            try:
                for r in ds:
                    r.pop("lr_auto", None)
                hop = mo_som(ds)
                ok_gui = cho(lambda: yc.is_file(), 10)
                dong_som = ([d for d in yc.read_text(encoding="utf-8").splitlines() if not d.startswith("#")]
                            if yc.is_file() else [])
                ktra("lượt bắt đầu -> chụp preview trước Auto + gửi lệnh Auto NGAY (chưa phân tích xong)",
                     ok_gui and goi_chup and app._xl.get("chup") is chup_gia and app._xl.get("pha") == "do",
                     f"{ok_gui} · {app._xl.get('pha')}")
                ktra("…ảnh người dùng đã sửa tay (khác số tool ghi) KHÔNG bấm Auto",
                     sorted(dong_som) == sorted([ds[0]["path"], ds[2]["path"]]) and app._xl.get("auto_bo_sua") == 1,
                     str(dong_som))
                n_ap = len(ap_goi)
                app._xl_sau_do(ds, app.read_cfg())
                ktra("phân tích xong mà Lightroom chưa Auto xong -> CHỜ (chưa áp)",
                     app._xl.get("pha") == "auto" and len(ap_goi) == n_ap
                     and "Auto" in str(hop.hang["do"][2].cget("text")), str(hop.hang["do"][2].cget("text")))
                ma2 = app._xl["auto_ma"]
                yc.unlink()
                bang2 = ["#ma=" + ma2, "path\t" + "\t".join(auto_lr.O)]
                for r in (ds[0], ds[2]):
                    bang2.append("\t".join([r["path"]] + [str(AUTO[k]) for k in auto_lr.O]))
                (jobs / auto_lr.TEN_BANG).write_text("\n".join(bang2) + "\n", encoding="utf-8")
                (jobs / auto_lr.TEN_KET_QUA).write_text(f"ma={ma2}\ntong=2\nbat=2\nlo=1\ncach=gom\ngiay=40\n",
                                                       encoding="utf-8")
                ok_ap = cho(lambda: len(ap_goi) > n_ap, 15)
                ktra("…Auto xong -> số Auto vào ảnh đã Auto, tính lại rồi ÁP một lần",
                     ok_ap and ds[0].get("lr_auto") and ds[2].get("lr_auto") and not ds[1].get("lr_auto"),
                     f"ap {len(ap_goi) - n_ap}")
                hop.destroy()
                #  Auto xong NGAY trong lúc phân tích -> phân tích xong là đi tiếp, không chờ
                for r in ds:
                    r.pop("lr_auto", None)
                for f_ in jobs.glob(f"ghi_auto_*_{tj_b}.done"):   # bản ghi Auto của lượt vừa rồi
                    f_.unlink()
                hop = mo_som(ds)
                cho(lambda: yc.is_file(), 10)
                ma3 = app._xl["auto_ma"]
                yc.unlink()
                (jobs / auto_lr.TEN_BANG).write_text("\n".join([bang2[0].replace(ma2, ma3)] + bang2[1:]) + "\n",
                                                    encoding="utf-8")
                (jobs / auto_lr.TEN_KET_QUA).write_text(f"ma={ma3}\ntong=2\nbat=2\n", encoding="utf-8")
                cho(lambda: app._xl.get("auto_ket_thuc"), 10)
                n_ap = len(ap_goi)
                app._xl_sau_do(ds, app.read_cfg())
                ok3 = cho(lambda: len(ap_goi) > n_ap, 15)
                ktra("Auto xong trong lúc phân tích -> phân tích xong là tính + áp ngay",
                     ok3 and ds[0].get("lr_auto"), f"{ok3}")
                hop.destroy()
                #  17/10: PHẠM VI CHỈNH chỉ WB -> KHÔNG gửi lệnh Auto; chụp preview rồi tính + áp
                for r in ds:
                    r.pop("lr_auto", None)
                app.v_pham_vi.set("Chỉ WB")
                ktra("chọn 'Chỉ WB' -> read_cfg: phạm vi wb, đường Auto, Curve / Denoise tắt",
                     doc_cfg().get("pham_vi") == "wb" and doc_cfg().get("quy_trinh_auto")
                     and not doc_cfg().get("curve_da") and not doc_cfg().get("denoise"))
                goi_chup.clear()
                hop = mo_som(ds)
                cho(lambda: bool((app._xl.get("auto_kq") or {}).get("bo")), 10)
                ktra("…lượt bắt đầu: chụp preview, KHÔNG gửi lệnh Auto",
                     goi_chup and not yc.is_file() and (app._xl.get("auto_kq") or {}).get("bo") == "khong-auto",
                     str(app._xl.get("auto_kq")))
                n_ap = len(ap_goi)
                app._xl_sau_do(ds, app.read_cfg())
                ok4 = cho(lambda: len(ap_goi) > n_ap, 15)
                app._xl["items_ghi"] = ds
                app._xl_ket_thuc("xong")
                ktra("…phân tích xong -> tính + áp ngay (không chờ Auto), tổng kết 'Chỉ cân WB'",
                     ok4 and not yc.is_file() and "Chỉ cân WB cho da về đích" in hop.lbl_tong.cget("text")
                     and "bấm Auto" not in hop.lbl_tong.cget("text"), hop.lbl_tong.cget("text")[:200])
                hop.destroy()
                app.v_pham_vi.set("Đầy đủ")
                ktra("…về 'Đầy đủ' -> read_cfg phạm vi day_du", doc_cfg().get("pham_vi") == "day_du")
            finally:
                dtm.chup_cache = cu_chup
                for f_ in jobs.glob(f"*_{tj_b}.done"):
                    f_.unlink()
            #  16/10 (user: "chỉ cần hiện chữ đang chạy … ở phía bản đóng gói"): hộp GỌN
            xu.HopXuLy.GON = True
            try:
                hg = xu.HopXuLy(app, False, lambda: None)
                hg.buoc("do", "dang", "Lightroom đang bấm Auto cho 3 ảnh…")
                hg.tien_do(1, 3, "Lightroom bấm Auto 1 / 3 ảnh · còn ~5 giây")
                chu_dang, chu_td = hg.hang["do"][2].cget("text"), hg.lbl_td.cget("text")
                hg.buoc("ap", "dang", "đang dừng…")
                chu_dung = hg.hang["ap"][2].cget("text")
                hg.buoc("do", "xong", "693 ảnh · đo da trên preview 120 ảnh (80 từ cache Lightroom)")
                chu_xong = hg.hang["do"][2].cget("text")
                hg.buoc("ap", "loi", "Lightroom chưa nhận lệnh Auto")
                chu_loi = hg.hang["ap"][2].cget("text")
                hg.destroy()
            finally:
                xu.HopXuLy.GON = None
            ktra("bản đóng gói: bước đang chạy chỉ 'đang chạy…', dòng tiến độ trống (không nói đang làm gì)",
                 chu_dang == "đang chạy…" and chu_td == "", f"{chu_dang!r} · {chu_td!r}")
            ktra("…'đang dừng…' giữ (khách biết đã nhận lệnh), bước xong chỉ phần đầu, lỗi đủ chữ",
                 chu_dung == "đang dừng…" and chu_xong == "693 ảnh" and chu_loi == "Lightroom chưa nhận lệnh Auto",
                 f"{chu_dung!r} · {chu_xong!r} · {chu_loi!r}")
            ktra("bản dev (không đóng gói) vẫn đủ chi tiết", xu.HopXuLy.GON is None and not hop.gon)
            app.v_auto_lr.set(False)
            ktra("tắt công tắc -> read_cfg không còn quy trình Auto", not doc_cfg().get("quy_trinh_auto"))
        finally:
            try:
                root.destroy()
            except Exception:                                # noqa: BLE001
                pass
        del xu
    finally:
        at.LR_JOB_DIR = job_cu
    print()
    print("TAT CA DAT" if not LOI else f"{len(LOI)} LOI: {LOI}")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
