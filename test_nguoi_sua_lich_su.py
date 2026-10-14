# -*- coding: utf-8 -*-
"""Ảnh user SỬA TAY mà lượt trước BỎ QUA vẫn được nhận ra ở lượt sau (15/10).

User sửa tay DSC09296 (Exposure −0.2 -> −0.61) và DSC09338 (Luminance Cam 53 -> 34) lúc 23:35.
Lượt 23:43 nhận ra và bỏ qua — nên job của lượt đó KHÔNG có dòng của hai ảnh. Lượt 00:30:
last_applied() chỉ đọc job MỚI NHẤT -> không có số tool ghi để so -> coi là ảnh thường và
ghi đè. Nay last_applied đọc mọi job cũ -> mới: mỗi ảnh lấy lần tool ghi GẦN NHẤT của nó.

Mục kiểm
    1. last_applied: ảnh vắng trong job mới nhất vẫn có số của job trước; job mới đè job cũ
    2. danh_dau_nguoi_sua: ảnh user sửa (lượt trước đã bỏ qua) vẫn bị đánh dấu; ảnh khác không
    3. job khôi phục (-khoiphuc) không tính là lần tool ghi; job @curve chỉ không tính cho
       last_applied (Exposure)
    4. mọi ô tool ghi (lan_ghi_cuoi + số đọc thẳng catalog): user chỉ đổi Luminance Cam
       (SUB_6464 53 -> 44) / Contrast -> nhận ra; ô tool ghi TRƯỚC lần áp chính gần nhất
       (trước khi user đặt lại buổi) không so -> không nhận nhầm (SUB_6728 curve xanh)

Chạy:  python test_nguoi_sua_lich_su.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

for _l in (sys.stdout, sys.stderr):
    try:
        _l.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                        # noqa: BLE001
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at                                        # noqa: E402

LOI: list = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


def job(d: Path, ten: str, dong: dict) -> None:
    cot = ["path", "Exposure2012", "Highlights2012"]
    (d / ten).write_text("\t".join(cot) + "\n" + "".join(
        f"G:\\2709\\{k}.ARW\t{v}\t-29\n" for k, v in dong.items()), encoding="utf-8")


def main() -> int:
    d = Path(tempfile.mkdtemp(prefix="jobs_sua_tay_"))
    folder = Path(r"G:\2709")
    job(d, "apply_20261014_224100_2709.done", {"DSC09296": -0.2, "DSC09338": 0.1, "DSC09297": -0.2})
    #  lượt 23:43 bỏ qua hai ảnh user vừa sửa
    job(d, "apply_20261014_234313_2709.done", {"DSC09297": -0.25})
    job(d, "apply_20261014_234512_2709@curve.done", {"DSC09296": 0.9})
    job(d, "apply_20261015_010000_2709-khoiphuc.done", {"DSC09338": 0.7})

    print("1. last_applied đọc mọi job")
    la = at.last_applied(folder, d)
    ktra("ảnh vắng trong job mới nhất vẫn giữ số lần ghi trước", la.get("dsc09296") == -0.2 and la.get("dsc09338") == 0.1,
         str(la))
    ktra("job mới đè job cũ (DSC09297 −0.2 -> −0.25)", la.get("dsc09297") == -0.25, str(la.get("dsc09297")))
    ktra("job @curve / -khoiphuc không tính", la.get("dsc09296") != 0.9 and la.get("dsc09338") != 0.7)

    print("2. danh_dau_nguoi_sua")
    cu = at.LR_JOB_DIR
    at.LR_JOB_DIR = d
    try:
        items = [{"path": f"G:\\2709\\{t}.ARW"} for t in ("DSC09296", "DSC09338", "DSC09297")]
        export = {at.khoa_duong_dan(items[0]["path"]): {"Exposure2012": "-0.61"},
                  at.khoa_duong_dan(items[1]["path"]): {"Exposure2012": "-0.09"},
                  at.khoa_duong_dan(items[2]["path"]): {"Exposure2012": "-0.25"}}
        n = at.danh_dau_nguoi_sua(items, export, folder)
    finally:
        at.LR_JOB_DIR = cu
    ktra("hai ảnh user sửa (lượt trước đã bỏ qua) vẫn bị đánh dấu, ảnh tool ghi thì không",
         n == 2 and items[0].get("nguoi_sua") and items[1].get("nguoi_sua") and not items[2].get("nguoi_sua"),
         f"{n} · {[r.get('nguoi_sua') for r in items]}")
    print("4. mọi ô tool ghi")
    d4 = Path(tempfile.mkdtemp(prefix="jobs_sua_tay4_"))
    cot = ["path", "Exposure2012", "Contrast2012", "ToneCurvePV2012Blue", "LuminanceAdjustmentOrange"]
    (d4 / "apply_20261014_220000_2709.done").write_text("\t".join(cot) + "\n" + "".join(
        f"G:\\2709\\{t}.NEF\t0\t5\t0,0,75,72,127,125,255,255\t53\n" for t in ("SUB_6464", "SUB_6728", "DSC_9617")),
        encoding="utf-8")
    #  user đặt lại buổi; lần áp chính mới không đụng curve xanh
    (d4 / "apply_20261015_003006_2709.done").write_text("\t".join(cot) + "\n" + "".join(
        f"G:\\2709\\{t}.NEF\t0\t5\t\t53\n" for t in ("SUB_6464", "SUB_6728", "DSC_9617")), encoding="utf-8")
    (d4 / "apply_20261015_003307_2709@curve.done").write_text(
        "path\tLuminanceAdjustmentOrange\nG:\\2709\\SUB_6728.NEF\t40\n", encoding="utf-8")
    g4 = at.lan_ghi_cuoi(folder, d4)
    ktra("lan_ghi_cuoi: mốc so = lần áp chính gần nhất (+ lượt 2 sau nó)",
         "ToneCurvePV2012Blue" not in g4["sub_6728"] and g4["sub_6728"]["LuminanceAdjustmentOrange"] == "40", str(g4["sub_6728"]))
    it4 = [{"path": f"G:\\2709\\{t}.NEF"} for t in ("SUB_6464", "SUB_6728", "DSC_9617")]
    hien = {at.khoa_duong_dan(it4[0]["path"]): {"Exposure2012": "0", "Contrast2012": "5", "LuminanceAdjustmentOrange": "44"},
            at.khoa_duong_dan(it4[1]["path"]): {"Exposure2012": "0", "Contrast2012": "5", "LuminanceAdjustmentOrange": "40",
                                                "ToneCurvePV2012Blue": "0,0,127,125,255,255"},
            at.khoa_duong_dan(it4[2]["path"]): {"Exposure2012": "0", "Contrast2012": "14", "LuminanceAdjustmentOrange": "53"}}
    at.LR_JOB_DIR = d4
    try:
        n4 = at.danh_dau_nguoi_sua(it4, {}, folder, hien=hien)
    finally:
        at.LR_JOB_DIR = cu
    ktra("user chỉ đổi Luminance Cam / Contrast -> nhận ra; curve tool ghi trước lần đặt lại -> không",
         n4 == 2 and it4[0].get("nguoi_sua_o") == ["LuminanceAdjustmentOrange"]
         and it4[2].get("nguoi_sua_o") == ["Contrast2012"] and not it4[1].get("nguoi_sua"),
         f"{n4} · {[r.get('nguoi_sua_o') for r in it4]}")
    print("5. ảnh trả về bằng job khôi phục")
    #  ô khôi phục (Saturation Cam) mà job trước KHÔNG ghi -> so lan_ghi_cuoi không thấy gì
    (d4 / "apply_20261015_043301_2709-khoiphuc.done").write_text(
        "path\tExposure2012\tSaturationAdjustmentOrange\nG:\\2709\\SUB_6728.NEF\t0\t-5\n", encoding="utf-8")
    it5 = [{"path": "G:\\2709\\SUB_6728.NEF"}]
    h5 = {at.khoa_duong_dan(it5[0]["path"]): {"Exposure2012": "0", "Contrast2012": "5", "LuminanceAdjustmentOrange": "40",
                                             "SaturationAdjustmentOrange": "-5"}}
    at.LR_JOB_DIR = d4
    try:
        n5 = at.danh_dau_nguoi_sua(it5, {}, folder, hien=h5)
        (d4 / "apply_20261015_050000_2709.done").write_text(
            "path\tExposure2012\nG:\\2709\\SUB_6728.NEF\t0\n", encoding="utf-8")
        it6 = [{"path": "G:\\2709\\SUB_6728.NEF"}]
        n6 = at.danh_dau_nguoi_sua(it6, {}, folder, hien=h5)
    finally:
        at.LR_JOB_DIR = cu
    ktra("số khôi phục còn nguyên (ô job trước không ghi) -> vẫn là ảnh user", n5 == 1
         and it5[0].get("nguoi_sua_o") == ["khoi-phuc"], str(it5[0].get("nguoi_sua_o")))
    ktra("sau một lần áp chính mới (user cho tool chạy lại) -> khôi phục cũ hết tính", n6 == 0)

    print("6. chạy lại bằng đường cũ: dọn ô chuỗi một lượt ghi")
    d6 = Path(tempfile.mkdtemp(prefix="jobs_don_"))
    cot6 = ["path", "Exposure2012", *at.COT_CURVE, "LuminanceAdjustmentOrange"]
    cv = "0,0,138,132,188,184,255,241"
    (d6 / "apply_20261015_003006_2709.done").write_text("\t".join(cot6) + "\n" + "".join(
        f"G:\\2709\\{t}.NEF\t0.5\tCustom\t{cv}\t0,0,255,255\t0,0,255,255\t0,0,255,255\t53\n" for t in ("DSC_9800", "DSC_9791")),
        encoding="utf-8")
    at.LR_JOB_DIR = d6
    try:
        dc6 = at.anh_da_curve(folder, d6)
        it7 = [{"path": f"G:\\2709\\{t}.NEF", "crs": {"LuminanceAdjustmentOrange": "18"}} for t in ("DSC_9800", "DSC_9791")]
        it7[1]["mot_luot"] = True                       # tấm này lần này đi chuỗi một lượt
        n7 = at.tra_lum_ve_moc(it7, folder)
    finally:
        at.LR_JOB_DIR = cu
    ktra("curve chuỗi một lượt ghi ở job CHÍNH -> anh_da_curve biết là tool ghi",
         at.khoa_duong_dan("G:\\2709\\DSC_9800.NEF") in dc6
         and at.trang_thai_curve({"ToneCurvePV2012": "0,0,138,132,255,255", **{k: "0,0,255,255" for k in at.COT_CURVE[2:]}},
                                 dc6[at.khoa_duong_dan("G:\\2709\\DSC_9800.NEF")][0],
                                 dc6[at.khoa_duong_dan("G:\\2709\\DSC_9800.NEF")][0]) == "tool")
    ktra("Luminance Cam tool ghi -> ảnh đi đường cũ trả về mốc 18; ảnh đi một lượt để chuỗi lo",
         n7 == 1 and it7[0].get("hsl_l_moi") == {"LuminanceAdjustmentOrange": 18.0} and not it7[1].get("hsl_l_ghi"),
         str([r.get("hsl_l_moi") for r in it7]))
    print(f"\n{len(LOI)} LOI" if LOI else "\nTAT CA DAT")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
