# -*- coding: utf-8 -*-
"""PHẠM VI CHỈNH — chỉ cân WB và / hoặc Exposure (autotone.pham_vi / moc_hien_tai / chot_pham_vi,
write_lr_job; 17/10).

User 17/10: "Thêm option khi người dùng chỉ muốn chạy cân WB và Exposure or 1 trong 2. Khi đó sẽ
chỉ xử lý cân lại WB và Exposure để da đạt được đích".

Mục kiểm
    1. pham_vi: "day_du" / thiếu -> None; "wb_ev" / "wb" / "ev" -> nhóm ô
    2. moc_hien_tai: mốc (lr_auto) = thông số Lightroom HIỆN TẠI (crs_hien); đầy đủ / sidecar /
       ảnh đen trắng -> không đụng
    3. giu_auto trên mốc hiện tại: WB xuất phát = WB hiện tại (không phải mốc preset); chỉ
       Exposure -> không cộng bù K / Tint; chỉ WB -> không cộng bù sáng
    4. chot_pham_vi: ô ngoài phạm vi về số hiện tại, HL / SH giữ, bỏ HSL / CG / curve / tông
    5. write_lr_job: chỉ ghi ô được chọn, ô khác TRỐNG (plugin không đụng); đủ số cột
    6. giao diện: read_cfg chỉ WB -> đường Auto không bấm Auto, Curve / HSL / CG / Denoise tắt;
       Giới hạn chỉnh cố định 5 / 5 / ×1 và nhóm đã ẩn; Quy trình Auto mặc định BẬT

Chạy:  python test_pham_vi.py
"""
from __future__ import annotations

import os
import sys
import tempfile
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


PRESET = {"Exposure2012": "0.50", "Highlights2012": "-29", "Shadows2012": "16", "Contrast2012": "5",
          "Whites2012": "-25", "Blacks2012": "-18", "Temperature": "5000", "Tint": "10",
          "WhiteBalance": "Custom"}
HIEN = dict(PRESET, **{"Exposure2012": "0.85", "Highlights2012": "-40", "Shadows2012": "22",
                       "Temperature": "5600", "Tint": "14", "Vibrance": "9"})


def main() -> int:
    tam = Path(tempfile.mkdtemp(prefix="pham_vi_"))
    os.environ["AUTOTONE_DATA"] = str(tam / "du_lieu")
    os.environ["AUTOTONE_CATALOG_LR"] = "0"
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import autotone as at

    cfg = dict(at.DEFAULTS, source="catalog", wb="skin", quy_trinh_auto=True)

    def anh(ten, **kw):
        r = {"path": str(tam / f"{ten}.ARW"), "crs": dict(PRESET), "atn": {}, "crs_hien": dict(HIEN),
             "delta_ev": 0.4, "hl_adj": -10, "sh_adj": 8, "temp_adj": -300.0, "tint_adj": 4.0,
             "cv_dk": -6, "cv_lt": 6, "meter_boxes": [[10, 10, 50, 60]], "notes": "", "rating": 0}
        r.update(kw)
        at.compute_values(r, cfg, r["crs"], r["atn"])
        return r

    print("1. pham_vi")
    ktra("đầy đủ / thiếu -> None", at.pham_vi({}) is None and at.pham_vi({"pham_vi": "day_du"}) is None)
    ktra("wb_ev / wb / ev", at.pham_vi({"pham_vi": "wb_ev"}) == {"wb", "ev"}
         and at.pham_vi({"pham_vi": "wb"}) == {"wb"} and at.pham_vi({"pham_vi": "ev"}) == {"ev"})

    print("2. moc_hien_tai")
    a, bw = anh("A"), anh("BW", bw=True)
    n = at.moc_hien_tai([a, bw], dict(cfg, pham_vi="wb"))
    ktra("mốc = số hiện tại (crs_hien), ảnh đen trắng bỏ qua",
         n == 1 and a["lr_auto"]["Exposure2012"] == "0.85" and a["lr_auto"]["Temperature"] == "5600"
         and a.get("lr_hien_tai") and not bw.get("lr_auto"), str(a.get("lr_auto")))
    b = anh("B")
    ktra("đầy đủ / sidecar -> không đụng",
         at.moc_hien_tai([b], cfg) == 0 and at.moc_hien_tai([b], dict(cfg, pham_vi="wb", source="sidecar")) == 0
         and not b.get("lr_auto"))

    print("3. giu_auto trên mốc hiện tại")
    bu = dict(bu_sang_ca_buoi=0.2, bu_k_ca_buoi=150.0, bu_tint_ca_buoi=-2.0)
    kq = {}
    for pv in ("wb_ev", "wb", "ev"):
        r = anh(pv)
        c = dict(cfg, pham_vi=pv, **bu)
        at.moc_hien_tai([r], c)
        at.giu_auto([r], c)
        kq[pv] = r
    r = kq["wb_ev"]
    ktra("WB + Exposure: xuất phát từ số HIỆN TẠI (EV 0.85, WB 5600/14) + bù người dùng",
         abs(r["new_exposure"] - 1.05) < 1e-6 and r["new_temp"] == 5750 and r["new_tint"] == 12
         and r["new_highlights"] == -40 and r["new_shadows"] == 22,
         f"EV {r['new_exposure']} WB {r['new_temp']}/{r['new_tint']} HL {r['new_highlights']}")
    ktra("chỉ WB: không cộng bù sáng", abs(kq["wb"]["new_exposure"] - 0.85) < 1e-6 and kq["wb"]["new_temp"] == 5750)
    ktra("chỉ Exposure: không cộng bù K / Tint (WB đứng yên ở số hiện tại)",
         kq["ev"]["new_temp"] == 5600 and kq["ev"]["new_tint"] == 14 and abs(kq["ev"]["new_exposure"] - 1.05) < 1e-6)

    print("4. chot_pham_vi")
    r = anh("C")
    at.moc_hien_tai([r], dict(cfg, pham_vi="ev"))
    at.giu_auto([r], dict(cfg, pham_vi="ev"))
    r.update(new_exposure=1.3, new_temp=4800, new_tint=2, new_highlights=-60, hsl_ghi=True,
             hsl_moi={"HueAdjustmentOrange": 3}, gr_ghi=True, gr_mid=(30, 5),
             curve_ghi_mot_luot={"ToneCurvePV2012Red": "0,0,255,255"}, new_Contrast2012=7,
             new_ParametricDarks=-6)
    at.chot_pham_vi([r], dict(cfg, pham_vi="ev"))
    ktra("chỉ Exposure: WB về số hiện tại, Exposure giữ số mới, HL về hiện tại",
         r["new_temp"] == 5600 and r["new_tint"] == 14 and abs(r["new_exposure"] - 1.3) < 1e-6
         and r["new_highlights"] == -40 and r["pham_vi"] == ("ev",),
         f"{r['new_temp']}/{r['new_tint']} EV {r['new_exposure']} HL {r['new_highlights']}")
    ktra("…bỏ HSL / CG / curve / Contrast / Parametric",
         not any(r.get(k) for k in ("hsl_ghi", "gr_ghi", "curve_ghi_mot_luot", "new_Contrast2012",
                                    "new_ParametricDarks")))
    r2 = anh("D")
    at.moc_hien_tai([r2], dict(cfg, pham_vi="wb"))
    at.giu_auto([r2], dict(cfg, pham_vi="wb"))
    r2.update(new_exposure=1.3, new_temp=4800, new_tint=2)
    at.chot_pham_vi([r2], dict(cfg, pham_vi="wb"))
    ktra("chỉ WB: Exposure về số hiện tại, WB giữ số mới",
         abs(r2["new_exposure"] - 0.85) < 1e-6 and r2["new_temp"] == 4800 and r2["delta_ev"] == 0.0)
    r3 = anh("E", pham_vi=("ev",))
    at.chot_pham_vi([r3], cfg)
    ktra("đầy đủ: không đụng, bỏ dấu phạm vi cũ", "pham_vi" not in r3)

    print("5. write_lr_job")
    jobs = tam / "jobs"
    rows = {}
    for ten, rr in (("ev", r), ("wb", r2)):
        rr.update(rating=1, upright=1, lr_path=rr["path"])
        job = at.write_lr_job([rr], ten, job_dir=jobs)
        dong = job.read_text(encoding="utf-8").splitlines()
        hd, val = dong[0].split("\t"), dong[1].split("\t")
        rows[ten] = dict(zip(hd, val))
        ktra(f"'{ten}': đủ số cột ({len(hd)})", len(hd) == len(val) == len(at.LR_JOB_FIELDS) + 1)
    co = {k for k, v in rows["ev"].items() if v and k != "path"}
    ktra("chỉ Exposure: chỉ ô Exposure2012 có số (Rating / Upright / HL / WB… trống)", co == {"Exposure2012"},
         str(co))
    co = {k for k, v in rows["wb"].items() if v and k != "path"}
    ktra("chỉ WB: chỉ Temperature / Tint có số", co == {"Temperature", "Tint"}, str(co))

    print("6. giao diện (mã nguồn)")
    g = Path(at.__file__).with_name("autotone_gui.py").read_text(encoding="utf-8")
    ktra("Giới hạn chỉnh cố định 5 / 5 / ×1, read_cfg dùng số đó, nhóm 'tran' ẩn",
         'GIOI_HAN_CO_DINH = {"max_ev": 5.0, "max_ev_up": 5.0, "exposure_gain": 1.0}' in g
         and 'max_ev=GIOI_HAN_CO_DINH["max_ev"]' in g and 'max_ev_up=GIOI_HAN_CO_DINH["max_ev_up"]' in g
         and 'self._nhom_tuy_chon.pop("tran").pack_forget()' in g)
    ktra("Quy trình Auto Lightroom: không còn công tắc trên giao diện, luôn BẬT",
         "ct(g_tone, self.v_auto_lr" not in g and "self.v_auto_lr = tk.BooleanVar(value=True)" in g
         and "quy_trinh_auto_chinh" not in g.split("self.v_auto_lr = tk.BooleanVar(value=True)")[1][:400])
    ktra("read_cfg phạm vi chỉnh: đường Auto + tắt Curve / HSL / CG / Denoise",
         "cfg.update(pham_vi=pv, quy_trinh_auto=True" in g and "curve_da=False" in g and "denoise=False" in g)
    print(f"\n{len(LOI)} LOI" if LOI else "\nTAT CA DAT")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
