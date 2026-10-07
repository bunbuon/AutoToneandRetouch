#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kiem_den_trang.py — Ảnh ĐEN TRẮNG (máy chụp kiểu ảnh B/W) giữ BW (8/10).

    python kiem_den_trang.py [thư mục ARW có cả ảnh B/W lẫn ảnh màu]

User 8/10: "Ở ảnh Raw load Preview nhìn thấy được bức ảnh đang để chế độ BW. Vậy
cũng sẽ cần giữ nguyên màu BW này và vẫn sửa các thông số khác."

Không cần ảnh thật thì bài 1–3 vẫn chạy (ảnh tổng hợp); có thư mục ARW thì chép
3 ảnh B/W + 3 ảnh màu vào thư mục tạm (KHÔNG ghi gì vào thư mục gốc), đo, tính,
ghi job thật rồi kiểm:
    1. la_den_trang: ảnh xám (R=G=B, kể cả nhiễu JPEG nhẹ) -> True; ảnh màu,
       kể cả ảnh gần xám có da người -> False
    2. la_bw_catalog đọc ConvertToGrayscale "True"/"1" của Lightroom / sidecar
    3. compute_values ảnh B/W: ghi ConvertToGrayscale, KHÔNG ghi Temperature /
       Tint / Color Grading, VẪN ghi Exposure / Highlights / Shadows / curve
    4. (ARW thật) đo ra đúng 3 B/W + 3 màu; job: hàng B/W có cột
       ConvertToGrayscale = 1, ô WB / Color Grading trống; hàng màu ngược lại
ĐẠT / HỎNG ở cuối, mã thoát 0 / 1.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at                                           # noqa: E402

LOI: list = []


def ktra(ten, ok, chi_tiet=""):
    print(f"  [{'DAT ' if ok else 'HONG'}] {ten}  {chi_tiet}")
    if not ok:
        LOI.append(ten)


def anh(rgb_fn, w=320, h=240, seed=0):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w]
    a = rgb_fn(xx / w, yy / h, rng)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


def main() -> int:
    # ---- 1. nhan dien tren anh tong hop
    def xam(x, y, rng):
        g = 40 + 180 * x + rng.normal(0, 3, x.shape)
        a = np.stack([g, g, g], -1)
        return a + rng.integers(-1, 2, a.shape)          # nhieu kenh 1 muc (JPEG)

    def gan_xam_co_da(x, y, rng):
        g = 200 + 30 * y
        a = np.stack([g, g, g], -1).astype(float)
        m = ((x - 0.5) ** 2 + (y - 0.4) ** 2) < 0.02        # mot khuon mat
        a[m] = [205, 160, 140]                               # da nguoi
        return a

    def mau(x, y, rng):
        return np.stack([255 * x, 255 * y, 128 + 0 * x], -1)

    ktra("ảnh xám (R=G=B, nhiễu JPEG 1 mức) -> đen trắng",
         at.la_den_trang(anh(xam)) is True)
    ktra("ảnh gần xám nhưng có da người -> KHÔNG phải đen trắng",
         at.la_den_trang(anh(gan_xam_co_da)) is False)
    ktra("ảnh màu -> không phải đen trắng", at.la_den_trang(anh(mau)) is False)
    ktra("ảnh 1 kênh (L) -> đen trắng",
         at.la_den_trang(anh(xam).convert("L")) is True)

    # ---- 2. co Black & White cua Lightroom / sidecar
    ktra("ConvertToGrayscale True / 1 / true -> BW; False / 0 / trống -> màu",
         all(at.la_bw_catalog({"ConvertToGrayscale": v}) for v in ("True", "1", "true"))
         and not any(at.la_bw_catalog({"ConvertToGrayscale": v}) for v in ("False", "0", ""))
         and not at.la_bw_catalog({}))

    # ---- 3. compute_values
    cfg = dict(at.DEFAULTS)
    cfg.update(wb="skin", grade=True, curve=True, highlights=True, shadows=True)
    crs = {"Exposure2012": "0", "Highlights2012": "0", "Shadows2012": "0",
           "Temperature": "5500", "Tint": "0", "WhiteBalance": "As Shot"}

    def r0(bw):
        return {"path": "x.ARW", "bw": bw, "delta_ev": 0.4, "hl_adj": -20, "sh_adj": 10,
                "temp_adj": 300.0, "tint_adj": 8.0, "gr_hue": 40, "gr_sat": 12,
                "gr_shue": 220, "gr_ssat": 5, "gr_lum": 0,
                "cv_hl": -5, "cv_lt": 3, "cv_dk": 2, "cv_sh": 0}
    r_bw, r_mau = r0(True), r0(False)
    c_bw = at.compute_values(r_bw, cfg, dict(crs), {})
    c_mau = at.compute_values(r_mau, cfg, dict(crs), {})
    ktra("B/W: ghi ConvertToGrayscale=True", c_bw.get("ConvertToGrayscale") == "True")
    ktra("B/W: KHÔNG ghi Temperature / Tint / Color Grading",
         not any(k in c_bw for k in ("Temperature", "Tint", "WhiteBalance",
                                     "ColorGradeMidtoneHue", "ColorGradeMidtoneSat")),
         ", ".join(sorted(c_bw)))
    ktra("B/W: VẪN chỉnh Exposure / Highlights / Shadows / curve",
         c_bw.get("Exposure2012") == c_mau.get("Exposure2012") != "0.00"
         and "Highlights2012" in c_bw and "ParametricHighlights" in c_bw)
    ktra("ảnh màu: như cũ (có WB, có Color Grading, không ép B/W)",
         "Temperature" in c_mau and "ColorGradeMidtoneHue" in c_mau
         and "ConvertToGrayscale" not in c_mau)
    r_lai = dict(r0(True), rerun=True)
    c_lai = at.compute_values(r_lai, cfg, dict(crs), {})
    ktra("B/W chạy lại (có mốc gốc): WB trả về đúng số gốc, không thêm WB mới",
         c_lai.get("Temperature") == "5500" and c_lai.get("Tint") == "0"
         and r_lai.get("bw_tra_wb") is True and "ColorGradeMidtoneHue" not in c_lai,
         f"T={c_lai.get('Temperature')} tint={c_lai.get('Tint')}")
    ktra("B/W lấy từ catalog dù preview màu (người dùng bật B&W trong Lightroom)",
         at.compute_values(r0(False), cfg, dict(crs, ConvertToGrayscale="1"), {})
         .get("ConvertToGrayscale") == "True")

    # ---- 4. ARW that (tuy chon)
    goc = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("G:/Kyyeu")
    ten_bw = ["VT_08580.ARW", "VT_08595.ARW", "VT_08610.ARW"]
    ten_mau = ["VT_08560.ARW", "VT_08620.ARW", "VT_08638.ARW"]
    if not all((goc / t).is_file() for t in ten_bw + ten_mau):
        print("  (bỏ qua bài 4: không có ARW mẫu ở", goc, ")")
    else:
        td = Path(tempfile.mkdtemp(prefix="kiem_den_trang_"))
        for t in ten_bw + ten_mau:
            shutil.copy2(goc / t, td / t)
        pairs = [(td / t, None) for t in ten_bw + ten_mau]
        items, _hong = at.analyze(pairs, dict(cfg, meter="face"), jobs=1)
        bw = {Path(r["path"]).name: bool(r.get("bw")) for r in items}
        ktra("đo ARW thật: đúng 3 ảnh B/W + 3 ảnh màu",
             all(bw.get(t) for t in ten_bw) and not any(bw.get(t) for t in ten_mau),
             str(bw))
        export = {at.khoa_duong_dan(r["path"]): {
            "Exposure2012": "0", "Highlights2012": "0", "Shadows2012": "0",
            "Temperature": "5500", "Tint": "0", "WhiteBalance": "As Shot"} for r in items}
        at.plan(items, dict(cfg, source="catalog"), td, export)
        for r in items:                       # dam bao co WB / grading de kiem cot
            r.setdefault("new_temp", r.get("old_temp"))
        job = at.write_lr_job(items, "kiem_bw", job_dir=td / "jobs")
        if job is None:
            ktra("ghi được job", False, "write_lr_job trả None")
        else:
            dong = job.read_text(encoding="utf-8").splitlines()
            cot = dong[0].split("\t")
            i_bw, i_t = cot.index("ConvertToGrayscale"), cot.index("Temperature")
            i_g = cot.index("ColorGradeMidtoneSat")
            hang = {Path(d.split("\t")[0]).name: d.split("\t") for d in dong[1:]}
            ok_bw = all(hang[t][i_bw] == "1" and hang[t][i_t] == "" and hang[t][i_g] == ""
                        for t in ten_bw if t in hang)
            ok_mau = all(hang[t][i_bw] == "" for t in ten_mau if t in hang)
            ktra("job: hàng B/W có ConvertToGrayscale=1, ô WB / Color Grading trống",
                 ok_bw and all(t in hang for t in ten_bw),
                 " | ".join(f"{t}: bw={hang[t][i_bw]!r} T={hang[t][i_t]!r}"
                            for t in ten_bw if t in hang))
            ktra("job: hàng màu không ép B/W", ok_mau and all(t in hang for t in ten_mau))
            ktra("job: mỗi hàng đủ số cột như tiêu đề",
                 all(len(h) == len(cot) for h in hang.values()))
        shutil.rmtree(td, ignore_errors=True)

    print("TAT CA DAT" if not LOI else f"{len(LOI)} LOI")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
