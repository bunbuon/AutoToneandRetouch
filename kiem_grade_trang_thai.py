# -*- coding: utf-8 -*-
"""Kiểm WB + Color Grading THEO TRẠNG THÁI (8/10) và các lỗi đi kèm.

CHUYỆN ĐANG SỬA (buổi kỷ yếu "raw 19.4", preset Bong22: Custom 5950 / +19,
Saturation +19, Vibrance +25, Highlights toning 36/10)
    · "ghi vào Lightroom lần 2 không hoạt động": at.LAST_JOB không ai gán ->
      giao diện báo "không gửi job nào"; hộp hỏi của nguồn catalog là hộp
      sidecar ("GHI ĐÈ… Tiếp tục?"); 1083 ảnh "CHƯA nhận" vì hai khoá
      ColorGradeShadow* Lightroom không có.
    · "bật Color Grading màu loạn, không còn trắng hồng": hue 350 (ĐỎ) thêm vào
      da cam; tính trên preview của máy chứ không trên ảnh Lightroom.
    · "WB tăng K quá nhiều": máy đặt 5000 K, preset 5950 K, tool còn cộng thêm.

Mục kiểm
    1. Mô hình WB Adobe: 2856 K -> xy nguồn A; tăng Temperature -> ảnh ấm hơn.
    2. Bảng hue Lightroom <-> OkLab đi về đúng.
    3. WB theo trạng thái: máy 5000 K + preset 5950 K -> tool hạ K so với cách cũ;
       máy đặt đúng 5950 K -> như cách cũ.
    4. Grade: da cam -> xoay về hồng (hue tool vùng tím-hồng 270-310, KHÔNG phải
       350), cộng vào bánh xe preset; da đã đúng hue -> không grade; cùng cảnh ->
       cùng vectơ.
    5. Tắt grade / ảnh B/W mà lần trước tool đã grade -> trả về số gốc.
    6. Bản xuất plugin cũ (thiếu cột màu) -> không grade, có cảnh báo; ảnh đã
       grade thì chỉ trả midtone về 0.
    7. Job: không còn ColorGradeShadow*, có hai cột Highlight, LAST_JOB được gán.
    8. Mốc: bu_cot_mau trả midtone về 0 cho ảnh đã grade; anh_da_grade và
       last_applied tìm đúng job của buổi tên có dấu cách.

Chạy:  python kiem_grade_trang_thai.py
"""
from __future__ import annotations

import contextlib
import copy
import io
import math
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at          # noqa: E402
import test_san_phang as ts    # noqa: E402

LOI: list = []
T0 = datetime(2026, 10, 8, 9, 0, 0)
PRESET = {"Exposure2012": "0", "Highlights2012": "16", "Shadows2012": "16",
          "Temperature": "5950", "Tint": "19", "WhiteBalance": "Custom",
          "Contrast2012": "5", "Whites2012": "-25", "Blacks2012": "-18",
          "Saturation": "19", "Vibrance": "25",
          "ColorGradeMidtoneHue": "0", "ColorGradeMidtoneSat": "0",
          "SplitToningShadowHue": "225", "SplitToningShadowSaturation": "0",
          "SplitToningHighlightHue": "36", "SplitToningHighlightSaturation": "10",
          "SplitToningBalance": "3", "ColorGradeBlending": "38",
          "ColorGradeGlobalHue": "0", "ColorGradeGlobalSat": "0"}
DA_CAM = [0.30, 0.19, 0.12]          # da tuyen tinh nga cam, nhu preview Sony


def ktra(ten, ok, ct=""):
    print(f"  [{'DAT ' if ok else 'HONG'}] {ten}  {ct}")
    if not ok:
        LOI.append(ten)


def anh(i, face=None, may_k=5000, crs=None, giay=None):
    r = ts._anh(f"HUY0{4200 + i}", -1.0, T0 + timedelta(seconds=giay if giay is not None else 8 * i))
    r["face_rgb"] = list(face or DA_CAM)
    r["wb_may_K"] = may_k
    r["model"] = "ILCE-7M4"
    r["crs"] = dict(crs or PRESET)
    r["atn"] = {}
    r["ngoai_troi"] = False
    r["fnumber"], r["exposure_time"], r["iso"] = 4.0, 1 / 500, 200
    return r


def cfg_(**kw):
    c = ts._cfg(wb="skin", source="catalog", che_do_sang="den", grade=False)
    c.update(kw)
    return c


def chay(items, cfg):
    """decide -> compute_values -> grade_theo_trang_thai, như plan() đường catalog."""
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        at.group_scenes(items, cfg["gap_minutes"], float(cfg.get("scene_sig_thresh", 0.0)),
                        int(cfg.get("scene_sig_min_shots", 3)),
                        bool(cfg.get("scene_gap_can_sig", True)))
        at.decide(items, cfg)
        for r in items:
            at.compute_values(r, cfg, r["crs"], r["atn"])
        at.grade_theo_trang_thai(items, cfg)
    return items


def main() -> int:
    # ---- 1. mo hinh WB Adobe
    x, y = at.xy_adobe(2856, 0)
    ktra("2856 K -> xy nguồn chuẩn A (0.4476, 0.4074)", abs(x - 0.4476) < 0.0005 and abs(y - 0.4074) < 0.0005,
         f"({x:.4f}, {y:.4f})")
    c = np.array([0.5, 0.35, 0.25])
    d = at.doi_wb(c, (5000, 12), (5950, 19))
    lech = math.log2(d[2] / d[0]) - math.log2(c[2] / c[0])
    ktra("preview máy 5000 K -> Lightroom 5950 K: ẤM hơn ~0.46 stop", -0.52 < lech < -0.40, f"{lech:+.3f}")
    ktra("cùng WB -> giữ nguyên màu", np.allclose(at.doi_wb(c, (5600, 10), (5600, 10)), c))

    # ---- 2. hue
    ok = all(abs(((at.hue_oklab_sang_lr(at.hue_lr_sang_oklab(h)) - h + 180) % 360) - 180) < 0.3
             for h in range(0, 360, 5))
    ktra("hue Lightroom -> OkLab -> Lightroom đi về đúng", ok)
    ktra("bánh xe (36, 10) -> vectơ -> (36, 10)", at.banh_xe_nguoc(at.banh_xe(36, 10)) == (36, 10))

    # ---- 3. WB theo trang thai
    def tb_temp(may_k, bat):
        ds = chay([anh(i, may_k=may_k) for i in range(6)], cfg_(wb_theo_trang_thai=bat))
        return float(np.median([r["new_temp"] for r in ds]))
    cu, moi = tb_temp(5000, False), tb_temp(5000, True)
    ktra("máy 5000 K, preset 5950 K: WB theo trạng thái HẠ K so với cách cũ (~250 K)",
         120 < cu - moi < 400, f"cũ {cu:.0f} -> mới {moi:.0f}")
    cu2, moi2 = tb_temp(5950, False), tb_temp(5950, True)
    ktra("máy đặt đúng 5950 K: gần như không đổi (lệch tint +12 -> +19 chỉ vài chục K)",
         abs(cu2 - moi2) < 60, f"cũ {cu2:.0f} -> mới {moi2:.0f}")
    nen = chay([anh(i, crs=dict(PRESET, WhiteBalance="As Shot", Temperature="", Tint=""))
                for i in range(6)], cfg_(wb_theo_trang_thai=True))
    ktra("quy trình preset bỏ trống WB (As Shot): KHÔNG dùng WB theo trạng thái",
         not any(r.get("wb_trang_thai") for r in nen))

    # ---- 4. grade
    ds = chay([anh(i) for i in range(6)], cfg_(grade=True))
    r = ds[0]
    ktra("da cam -> có grade", bool(r.get("gr_ghi")) and r.get("gr_sat", 0) >= 1,
         f"tool {r.get('gr_hue')}/{r.get('gr_sat')} mid {r.get('gr_mid')} hi {r.get('gr_hi')}")
    ktra("hướng xoay về hồng = tím-hồng (270-310), KHÔNG phải đỏ 350", 270 <= r.get("gr_hue", 0) <= 310,
         f"hue {r.get('gr_hue')}")
    ktra("không vượt trần grade_sat_max", r.get("gr_sat", 99) <= at.DEFAULTS["grade_sat_max"])
    vm = at.banh_xe(0, 0) + at.banh_xe(r["gr_hue"], r["gr_sat"])
    ktra("midtone = preset (0/0) + vectơ tool", at.banh_xe_nguoc(vm) == tuple(r["gr_mid"]),
         f"{at.banh_xe_nguoc(vm)} vs {r['gr_mid']}")
    #  gr_hue / gr_sat la so DA LAM TRON cua vecto -> cho lech 1
    kv = at.banh_xe_nguoc(at.banh_xe(36, 10) + at.banh_xe(r["gr_hue"], r["gr_sat"]))
    ktra("highlight = preset 36/10 + vectơ tool (không ghi đè)",
         tuple(r["gr_hi"]) != (36, 10)
         and abs(kv[0] - r["gr_hi"][0]) <= 1 and abs(kv[1] - r["gr_hi"][1]) <= 1,
         f"hi {r['gr_hi']} ~ {kv}")
    ktra("cùng cảnh -> cùng một grade", len({(x["gr_mid"], x["gr_hi"]) for x in ds}) == 1)
    #  da dung hue dich (sau WB preset va Saturation/Vibrance cua preset) -> khong grade
    dich = at.srgb_to_linear(np.asarray(at.DEFAULTS["skin_ref_rgb"]) / 255.0)
    trung = chay([anh(i, face=list(dich), may_k=5950, crs=dict(PRESET, Saturation="0", Vibrance="0",
                                                                 SplitToningHighlightSaturation="0",
                                                                 Tint="12"))
                  for i in range(6)], cfg_(grade=True, wb="off"))
    ktra("da đã đúng hue đích -> không grade", not any(x.get("gr_ghi") for x in trung),
         f"{[x.get('gr_sat') for x in trung]}")
    ktra("ghi chú có grade-trang-hong", "grade-trang-hong" in r.get("notes", ""))
    c_mau = at.compute_values(r, cfg_(grade=True), r["crs"], {})
    ktra("compute_values ghi đủ 4 ô Color Grading",
         all(k in c_mau for k in at.COT_GRADE) and "ColorGradeShadowHue" not in c_mau, ", ".join(sorted(c_mau)))

    # ---- 5. tra ve so goc
    tat = chay([dict(anh(i), da_grade=True) for i in range(6)], cfg_(grade=False))
    ktra("tắt grade, lần trước đã grade -> trả bánh xe về số preset",
         all(x.get("gr_ghi") and tuple(x["gr_mid"]) == (0, 0) and tuple(x["gr_hi"]) == (36, 10) for x in tat),
         f"{tat[0].get('gr_mid')} {tat[0].get('gr_hi')}")
    bw = chay([dict(anh(i), da_grade=True, bw=True) for i in range(6)], cfg_(grade=True))
    ktra("ảnh B/W đã bị grade -> trả về số preset, không grade mới",
         all(x.get("gr_ghi") and x.get("gr_sat") == 0 and tuple(x["gr_mid"]) == (0, 0) for x in bw))
    chua = chay([anh(i) for i in range(6)], cfg_(grade=False))
    ktra("tắt grade, chưa từng grade -> không ghi ô nào", not any(x.get("gr_ghi") for x in chua))

    # ---- 6. plugin cu
    thieu = {k: v for k, v in PRESET.items() if k not in at.COT_MAU}
    pc = chay([anh(i, crs=thieu) for i in range(3)] + [dict(anh(5, crs=thieu), da_grade=True)], cfg_(grade=True))
    ktra("bản xuất thiếu cột màu -> không grade ảnh mới",
         not any(x.get("gr_ghi") for x in pc[:3]) and all(x.get("gr_thieu_cot") for x in pc))
    ktra("… ảnh đã grade thì chỉ trả midtone về 0, không đụng highlight",
         pc[3].get("gr_ghi") and tuple(pc[3]["gr_mid"]) == (0, 0) and not pc[3].get("gr_hi"))
    ktra("cảnh báo Reload plugin khi bật grade mà bản xuất thiếu cột",
         "Reload" in at.canh_bao_plugin_cu({"a": thieu}, {"grade": True})
         and at.canh_bao_plugin_cu({"a": PRESET}, {"grade": True}) == "")

    # ---- 7. job
    td = Path(tempfile.mkdtemp(prefix="kiem_grade_"))
    try:
        for x in ds:
            x["lr_path"] = x["path"]
        at.LAST_JOB = None
        job = at.write_lr_job(ds + pc, "raw 19.4", job_dir=td / "jobs")
        dong = job.read_text(encoding="utf-8").splitlines()
        cot = dong[0].split("\t")
        ktra("LAST_JOB = job vừa ghi", at.LAST_JOB == job)
        ktra("job không còn ColorGradeShadow*, có hai cột Highlight",
             not any(c_.startswith("ColorGradeShadow") for c_ in cot)
             and "SplitToningHighlightHue" in cot and "SplitToningHighlightSaturation" in cot)
        ktra("mỗi hàng đủ số cột", all(len(d_.split("\t")) == len(cot) for d_ in dong[1:]))
        h0 = dong[1].split("\t")
        ktra("hàng có grade: ô midtone + highlight có số",
             h0[cot.index("ColorGradeMidtoneSat")] != "" and h0[cot.index("SplitToningHighlightSaturation")] != "")
        h_pc = dong[-1].split("\t")
        ktra("hàng chỉ trả midtone: ô highlight trống",
             h_pc[cot.index("ColorGradeMidtoneSat")] == "0" and h_pc[cot.index("SplitToningHighlightSaturation")] == "")

        # ---- 8. moc + tim job theo ten buoi co dau cach
        bu = at.bu_cot_mau({"Exposure2012": "0"}, dict(PRESET, ColorGradeMidtoneHue="350",
                                                        ColorGradeMidtoneSat="9"), True)
        ktra("bu_cot_mau: ảnh đã grade -> midtone gốc 0, phần còn lại lấy bản xuất",
             bu.get("ColorGradeMidtoneSat") == "0" and bu.get("SplitToningHighlightHue") == "36"
             and bu.get("Saturation") == "19")
        ktra("bu_cot_mau: mốc đã có số thì mốc thắng",
             "Saturation" not in at.bu_cot_mau({"Saturation": "5"}, PRESET, False))
        jd = td / "jobs"
        (jd / (job.stem + ".done")).write_bytes(job.read_bytes())
        k = at.anh_da_grade(Path("G:/raw 19.4/raw 19.4"), jd)
        ktra("anh_da_grade tìm job của buổi 'raw 19.4' (tên job raw_19.4)",
             at.khoa_duong_dan(ds[0]["path"]) in k, f"{len(k)} ảnh")
        ktra("last_applied tìm job của buổi tên có dấu cách",
             len(at.last_applied(Path("G:/raw 19.4/raw 19.4"), jd)) > 0)
        moc = td / "raw 19.4"
        moc.mkdir()
        at.save_baseline(moc, {"g:/x.arw": dict(PRESET)})
        doc = at.load_baseline(moc)
        ktra("mốc lưu thêm cột màu", all(c_ in next(iter(doc.values())) for c_ in at.COT_MAU))
    finally:
        shutil.rmtree(td, ignore_errors=True)

    print("TAT CA DAT" if not LOI else f"{len(LOI)} LOI: {LOI}")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
