#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Loại buổi Kỷ yếu — vòng 3 (8/10, sau khi user TẮT Color Grading) — kiểm bằng plan() THẬT.

CHUYỆN ĐANG SỬA
    Buổi raw 19.4 (1089 ảnh, 564 ảnh user tự sửa). So 1087 ảnh Lightroom vẽ thật
    (v42, Color Grading tắt) với ảnh duyệt:
    - 193 ảnh fisheye dưới đèn ấm: da preview cam đặc nên kênh R chạm 251-252 trên
      mọi mặt -> phanh da ghim Exposure, mặt tối hơn ảnh duyệt +0.43 EV.
    - Cùng nhóm đó tool mở Shadows +47 / ParametricShadows +35; ảnh duyệt TỐI hơn
      LR ở p10 0.5-0.8 EV — user giữ đen sâu.
    - Pixel trung tính: ảnh duyệt ấm/hồng hơn LR ~ +130 K / Tint +7 (trừ ảnh đèn
      màu nặng, WB đang chạm trần).
    - Trung tính sáng hơn (p25 +0.30, p50 +0.22), đen sâu hơn (p1 -0.30).

Mục kiểm
    1. Phanh da: Cưới ghim 0 như cũ; Kỷ yếu đưa mặt tới đích (≤ phanh_da_san_ky_yeu),
       có cờ phanh-da-nhuong-ky-yeu. Mặt đã sáng hơn đích thì không đổi gì.
    2. Kỷ yếu không tự mở vùng tối (sh_adj, cv_sh = 0); mo_toi_ky_yeu=True thì mở lại.
    3. Đường S: Cưới Darks -c, Kỷ yếu Darks +c.
    4. Tone nền kỷ yếu (preset bỏ trống Tone): Shadows / Blacks lấy từ nen_tone_ky_yeu.
    5. WB kỷ yếu: +wb_bu_ky_yeu so với Cưới, cờ wb-ky-yeu…; bỏ qua khi bật trắng hồng
       (grade) và khi WB đang chạm trần wb_temp_max.

Chạy:  python test_ky_yeu_vong3.py
"""
from __future__ import annotations

import contextlib
import copy
import io
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at          # noqa: E402
import test_2ban_quay as tq    # noqa: E402

#  Preset nhu buoi raw 19.4: WB Custom 5000 / +10, bo trong Basic Tone
PRESET_TRONG = {"Exposure2012": "0", "Highlights2012": "0", "Shadows2012": "0",
                "Contrast2012": "0", "Whites2012": "0", "Blacks2012": "0",
                "Temperature": "5000", "Tint": "10", "WhiteBalance": "Custom"}
CAM_DAC = [0.77, 0.23, 0.07]     # da preview duoi den am (HUY04922)


def bo_anh(thu_muc: Path) -> list:
    """Moi anh mot canh rieng (cach nhau 1 gio) de san phang canh khong tron."""
    items = [
        tq.anh("PHANH", 0, -1.5, p95=251 / 255, da=tq.DA_TRONG),       # muon +0.50
        tq.anh("PHANH2", 3600, -2.0, p95=251 / 255, da=tq.DA_TRONG),   # muon +1.00
        tq.anh("SANG", 7200, -0.5, p95=251 / 255, da=tq.DA_TRONG),     # da tren dich
        tq.anh("TOI", 10800, -1.0, da=tq.DA_TRONG),                    # canh nhieu bong
        tq.anh("WB", 14400, -1.0, da=tq.DA_TRONG),
        tq.anh("CAM", 18000, -1.0, da=CAM_DAC),                        # WB cham tran
    ]
    logY = np.full(4096, -1.0)
    logY[:820] = -9.5                                                  # 20% bet toi
    items[3]["hist_y"] = at._hist(logY).tolist()
    for r in items:
        r["path"] = str(thu_muc / Path(r["path"].replace("\\", "/")).name)
        r["crs"] = dict(PRESET_TRONG)
    return items


def chay(items, thu_muc: Path, **kw) -> dict:
    its = copy.deepcopy(items)
    exp = {at.khoa_duong_dan(r["path"]): dict(PRESET_TRONG) for r in its}
    cfg = dict(at.DEFAULTS, source="catalog", bo_qua_nguoi_sua=False, burst=False,
               blink=False, wb="skin", bu_sang_ca_buoi=0.0, max_ev_up=1.0)
    cfg.update(kw)
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        at.plan(its, cfg, thu_muc, exp)
    return {Path(r["path"]).stem: r for r in its}


def co(r, nhan):
    return nhan in (r.get("notes") or "")


def main() -> int:
    loi: list = []
    D = at.DEFAULTS
    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "raw 19.4"
        d.mkdir()
        items = bo_anh(d)
        cu = chay(items, d, loai_buoi="cuoi")
        ky = chay(items, d, loai_buoi="ky_yeu")

        # 1. phanh da
        if not co(cu["PHANH"], "ha-vi-da-sap-chay") or abs(cu["PHANH"]["delta_ev"]) > 1e-6:
            loi.append(f"Dung bai: Cuoi phai ghim PHANH ve 0 (delta {cu['PHANH']['delta_ev']:+.2f})")
        if abs(ky["PHANH"]["delta_ev"] - 0.50) > 0.011:
            loi.append(f"Ky yeu: PHANH phai len dich +0.50, dang {ky['PHANH']['delta_ev']:+.2f}")
        if not co(ky["PHANH"], "phanh-da-nhuong-ky-yeu") or co(ky["PHANH"], "ha-vi-da-sap-chay"):
            loi.append(f"Ky yeu: PHANH co sai: {ky['PHANH'].get('notes')}")
        san = float(D["phanh_da_san_ky_yeu"])
        if abs(ky["PHANH2"]["delta_ev"] - san) > 0.011:
            loi.append(f"Ky yeu: PHANH2 phai dung o san {san:+.2f}, dang {ky['PHANH2']['delta_ev']:+.2f}")
        if not (co(ky["PHANH2"], "ha-vi-da-sap-chay") and co(ky["PHANH2"], "phanh-da-nhuong-ky-yeu")):
            loi.append(f"Ky yeu: PHANH2 phai mang ca hai co, dang {ky['PHANH2'].get('notes')}")
        if abs(ky["SANG"]["delta_ev"] - cu["SANG"]["delta_ev"]) > 1e-6 or cu["SANG"]["delta_ev"] > 0:
            loi.append(f"Mat tren dich: Ky yeu {ky['SANG']['delta_ev']:+.2f} phai bang Cuoi {cu['SANG']['delta_ev']:+.2f} (<= 0)")
        tat = chay(items, d, loai_buoi="ky_yeu", phanh_da_san_ky_yeu=0.0)
        if abs(tat["PHANH"]["delta_ev"]) > 1e-6:
            loi.append("phanh_da_san_ky_yeu = 0 phai y nhu cu (ghim 0)")

        # 2. khong mo vung toi
        if not (cu["TOI"]["sh_adj"] > 0 and cu["TOI"]["cv_sh"] > 0):
            loi.append(f"Dung bai: Cuoi phai mo toi TOI (sh {cu['TOI']['sh_adj']}, cv_sh {cu['TOI']['cv_sh']})")
        if ky["TOI"]["sh_adj"] or ky["TOI"]["cv_sh"]:
            loi.append(f"Ky yeu khong duoc mo toi: sh {ky['TOI']['sh_adj']}, cv_sh {ky['TOI']['cv_sh']}")
        mo = chay(items, d, loai_buoi="ky_yeu", mo_toi_ky_yeu=True)
        if not (mo["TOI"]["sh_adj"] > 0 and mo["TOI"]["cv_sh"] > 0):
            loi.append("mo_toi_ky_yeu=True phai mo toi lai")

        # 3. duong S
        c = int(D["curve_contrast"])
        if cu["WB"]["cv_dk"] != -c or ky["WB"]["cv_dk"] != c:
            loi.append(f"Darks: Cuoi {cu['WB']['cv_dk']} (phai {-c}), Ky yeu {ky['WB']['cv_dk']} (phai {c})")

        # 4. tone nen ky yeu
        nt = D["nen_tone_ky_yeu"]
        if ky["WB"].get("new_shadows") != nt["Shadows2012"]:
            loi.append(f"Shadows nen ky yeu {ky['WB'].get('new_shadows')} phai {nt['Shadows2012']}")
        if ky["WB"].get("new_Blacks2012") != nt["Blacks2012"]:
            loi.append(f"Blacks nen ky yeu {ky['WB'].get('new_Blacks2012')} phai {nt['Blacks2012']}")
        if cu["WB"].get("new_Blacks2012") != D["nen_tone"]["Blacks2012"]:
            loi.append(f"Cuoi phai giu Blacks nen SAY {D['nen_tone']['Blacks2012']}")

        # 5. WB ky yeu
        bu = D["wb_bu_ky_yeu"]
        dT = ky["WB"]["new_temp"] - cu["WB"]["new_temp"]
        dn = ky["WB"]["new_tint"] - cu["WB"]["new_tint"]
        if abs(dT - bu["Temperature"]) > 1 or abs(dn - bu["Tint"]) > 1:
            loi.append(f"WB ky yeu phai +{bu['Temperature']} K / +{bu['Tint']}, dang {dT:+.0f} / {dn:+.0f}")
        if not co(ky["WB"], "wb-ky-yeu"):
            loi.append("Thieu co wb-ky-yeu")
        if abs(abs(cu["CAM"]["temp_adj"]) - float(D["wb_temp_max"])) > 1:
            loi.append(f"Dung bai: CAM phai cham tran WB (temp_adj {cu['CAM']['temp_adj']:+.0f})")
        if co(ky["CAM"], "wb-ky-yeu") or ky["CAM"]["new_temp"] != cu["CAM"]["new_temp"]:
            loi.append("Anh WB cham tran khong duoc cong WB ky yeu")
        gr = chay(items, d, loai_buoi="ky_yeu", grade=True)
        if any(co(r, "wb-ky-yeu") for r in gr.values()):
            loi.append("Bat trang hong (grade) thi khong cong WB ky yeu")

    for m in loi:
        print("  [!]", m)
    print("TAT CA DAT" if not loi else f"{len(loi)} LOI")
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
