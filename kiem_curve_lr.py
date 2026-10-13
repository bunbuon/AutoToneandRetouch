# -*- coding: utf-8 -*-
"""V0 — đo curve điểm của LIGHTROOM THẬT để chốt toán của curve_lr (13/10).

VÌ SAO
    curve_da giải curve kênh / curve tổng bằng mô hình curve_lr: miền curve ("melissa" =
    gốc ProPhoto + TRC sRGB?), spline (dng_spline_solver?), thứ tự curve tổng / kênh,
    curve tổng áp từng kênh hay giữ sắc. Viết lúc chưa có Lightroom — mọi cái đó là GIẢ
    THUYẾT. Lệch mô hình = dự đoán sai = curve chỉnh sai màu da. V0 đo thật trước khi chạy
    cổng (luật dự án: số chốt TRƯỚC khi chạy cổng).

CÁCH ĐO
    Bảng thử (ảnh TIFF 8 bit sRGB): thang xám 256 nấc + 32 mảng màu (12 tông da, 6 bão
    hoà, 6 xám, 8 nhạt). Import vào Lightroom KHÔNG kèm preset (Develop Settings: None).
    Mỗi ca: tool ghi curve qua job (đường áp thật của plugin) -> nhờ plugin dựng JPEG
    (đường lượt 2 thật) -> đo. Ca gốc c0 = curve đồng nhất; dự đoán ca k = áp curve ca k
    lên c0 theo từng giả thuyết; giả thuyết nào lệch ít nhất thì chốt.

CHẠY (máy Windows, Lightroom đang mở, plugin bản mới)
    python kiem_curve_lr.py tao  <thư mục>     -> tạo bảng thử; import thư mục vào Lightroom
    python kiem_curve_lr.py chay <thư mục>     -> chạy các ca (~2–4 phút), rồi phân tích
    python kiem_curve_lr.py phan_tich <thư mục> -> chỉ phân tích lại ảnh đã dựng (_v0/)
    Ra: <thư mục>/curve_lr_hieu_chinh.json + bảng in ra màn hình.

ĐẠT: thang xám lệch ≤ 2 mã, mảng màu ≤ 3 mã (ca c1–c4, giả thuyết tốt nhất).
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at  # noqa: E402
import curve_da as cd  # noqa: E402
import curve_lr as cl  # noqa: E402

TEN_BANG = "curve_v0_bang_thu.tif"
RONG, CAO = 1536, 1024
O = 192                                                   # cạnh mảng màu
DA = [(227, 184, 185), (246, 194, 181), (166, 123, 105), (210, 160, 140), (190, 140, 120),
      (240, 200, 180), (150, 105, 85), (120, 85, 70), (230, 175, 160), (200, 150, 150),
      (220, 185, 160), (180, 130, 110)]
BAO_HOA = [(204, 30, 30), (30, 204, 30), (30, 30, 204), (30, 204, 204), (204, 30, 204), (204, 204, 30)]
XAM = [(v, v, v) for v in (40, 80, 120, 160, 200, 235)]
NHAT = [(250, 220, 220), (220, 250, 220), (220, 220, 250), (250, 240, 200), (200, 240, 250),
        (240, 200, 250), (180, 200, 190), (200, 180, 170)]
MANG = DA + BAO_HOA + XAM + NHAT                          # 32 mảng, 8 cột × 4 hàng

DONG = [(0, 0), (255, 255)]
S_TONG = [(0, 0), (64, 44), (192, 212), (255, 255)]
DO_LEN = [(0, 0), (128, 150), (255, 255)]
LAM_16 = [(0, 0)] + [(x, min(255, round(x * 1.04 - 3 * np.sin(x / 40)))) for x in range(16, 240, 16)] + [(255, 255)]
CA = {
    "c0": {},
    "c1": {"master": S_TONG},
    "c2": {"r": DO_LEN},
    "c3": {"master": S_TONG, "r": DO_LEN},
    "c4": {"b": LAM_16},
    "c5": {"r": [(0, 0), (128, 140.5), (255, 255)]},          # số lẻ: Lightroom giữ không?
    "c6": {"r": DO_LEN, "_ten": "Linear"},                     # tên curve dựng sẵn: còn áp?
    "c7": {"_hsl": {"SaturationAdjustmentOrange": 40}},
    "c8": {"r": DO_LEN, "_hsl": {"SaturationAdjustmentOrange": 40}},
}


def tao(thu_muc: Path) -> Path:
    thu_muc.mkdir(parents=True, exist_ok=True)
    a = np.zeros((CAO, RONG, 3), np.uint8)
    buoc = RONG // 256
    for v in range(256):
        a[0:128, v * buoc:(v + 1) * buoc] = v
    for i, c in enumerate(MANG):
        h, k = divmod(i, 8)
        a[128 + h * O + 8:128 + (h + 1) * O - 8, k * O + 8:(k + 1) * O - 8] = c
    p = thu_muc / TEN_BANG
    Image.fromarray(a).save(p)
    print(f"Đã tạo {p}\nImport thư mục này vào Lightroom (Develop Settings: None), rồi chạy:\n"
          f"  python kiem_curve_lr.py chay \"{thu_muc}\"")
    return p


def do_mang(anh: Path) -> dict:
    """Trung bình sRGB 0..1 lõi 50% của từng nấc thang + từng mảng."""
    a = np.asarray(Image.open(anh).convert("RGB"), dtype=np.float64) / 255.0
    if a.shape[:2] != (CAO, RONG):
        a = np.asarray(Image.open(anh).convert("RGB").resize((RONG, CAO), Image.BILINEAR),
                       dtype=np.float64) / 255.0
    buoc = RONG // 256
    thang = np.array([a[32:96, v * buoc + 1:(v + 1) * buoc - 1].reshape(-1, 3).mean(axis=0)
                      for v in range(256)])
    mang = []
    for i in range(len(MANG)):
        h, k = divmod(i, 8)
        y0, x0 = 128 + h * O + O // 4, k * O + O // 4
        mang.append(a[y0:y0 + O // 2, x0:x0 + O // 2].reshape(-1, 3).mean(axis=0))
    return {"thang": thang, "mang": np.array(mang)}


def _du_doan(px, curves, mien, kieu, thu_tu):
    if thu_tu == "tong_truoc":
        return cl.ap_curve_tu_dau(px, curves, mien, kieu)
    w = cl.srgb_sang_mien(px, mien)                       # kênh trước, tổng sau
    out = np.empty_like(w)
    for i, c in enumerate(cl.KENH):
        out[..., i] = cl._ap_bang(w[..., i], cl.bang(curves.get(c) or cl.DONG_NHAT))  # noqa: SLF001
    bt = cl.bang(curves.get("master") or cl.DONG_NHAT)
    out = cl._rgb_tone(out, lambda v: cl._ap_bang(v, bt)) if kieu == "rgb_tone" else cl._ap_bang(out, bt)  # noqa: SLF001
    return cl.mien_sang_srgb(out, mien)


def phan_tich(thu_muc: Path) -> dict:
    v0 = thu_muc / "_v0"
    do = {k: do_mang(v0 / f"{k}.jpg") for k in CA if (v0 / f"{k}.jpg").exists()}
    if "c0" not in do:
        raise SystemExit("Thiếu _v0/c0.jpg — chạy 'chay' trước.")
    ket = []
    for mien in cl.MIEN:
        for kieu in cl.KIEU_TONG:
            for thu_tu in ("tong_truoc", "kenh_truoc"):
                lech_t, lech_m = [], []
                for k in ("c1", "c2", "c3", "c4"):
                    if k not in do:
                        continue
                    cv = {c: v for c, v in CA[k].items() if not c.startswith("_")}
                    lech_t.append(np.abs(_du_doan(do["c0"]["thang"], cv, mien, kieu, thu_tu)
                                         - do[k]["thang"]).max() * 255)
                    lech_m.append(np.abs(_du_doan(do["c0"]["mang"], cv, mien, kieu, thu_tu)
                                         - do[k]["mang"]).max() * 255)
                ket.append({"mien": mien, "kieu_tong": kieu, "thu_tu": thu_tu,
                            "thang": float(max(lech_t)), "mang": float(max(lech_m))})
    ket.sort(key=lambda x: x["thang"] + x["mang"])
    tot = ket[0]
    out = {"khi": datetime.now().isoformat(timespec="seconds"), "tot_nhat": tot, "tat_ca": ket,
           "dat": tot["thang"] <= 2.0 and tot["mang"] <= 3.0}
    #  HSL trước hay sau curve: c8 = curve đỏ áp lên c7 (HSL đã có) thì HSL đứng TRƯỚC curve
    if "c7" in do and "c8" in do:
        d = _du_doan(do["c7"]["mang"], {"r": DO_LEN}, tot["mien"], tot["kieu_tong"], tot["thu_tu"])
        out["hsl_truoc_curve_lech"] = float(np.abs(d - do["c8"]["mang"]).max() * 255)
    #  tên curve dựng sẵn ("Linear") + điểm Custom: Lightroom còn áp điểm không
    if "c6" in do and "c2" in do:
        out["ten_dung_san_van_ap"] = bool(np.abs(do["c6"]["mang"] - do["c2"]["mang"]).max() * 255 < 2)
    ghi = thu_muc / "curve_lr_hieu_chinh.json"
    ghi.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{'giả thuyết':<34} thang  mảng (mã, lệch lớn nhất)")
    for x in ket:
        print(f"{x['mien']:<11} {x['kieu_tong']:<9} {x['thu_tu']:<12} {x['thang']:5.1f} {x['mang']:5.1f}")
    print(f"\nTỐT NHẤT: {tot}  ->  {'ĐẠT' if out['dat'] else 'TRƯỢT'} (thang ≤ 2, mảng ≤ 3)")
    for k in ("hsl_truoc_curve_lech", "ten_dung_san_van_ap", "so_le", "16_diem"):
        if k in out:
            print(f"  {k}: {out[k]}")
    print(f"Đã ghi {ghi}")
    return out


def _cho(dieu, giay, chu):
    het = time.time() + giay
    while time.time() < het:
        v = dieu()
        if v:
            return v
        time.sleep(1.0)
    raise SystemExit(f"Hết giờ chờ: {chu} — Lightroom mở chưa, plugin bản mới chưa?")


def chay(thu_muc: Path) -> None:
    bang = thu_muc / TEN_BANG
    if not bang.exists():
        raise SystemExit(f"Chưa có {bang} — chạy 'tao' rồi import vào Lightroom trước.")
    if cd.KHA_NANG not in at.plugin_kha_nang():
        raise SystemExit("Plugin trong Lightroom chưa phải bản có curve (nhịp không khai curve1) — "
                         "cài lại AutoTone bản đầy đủ rồi khởi động lại Lightroom.")
    v0 = thu_muc / "_v0"
    v0.mkdir(exist_ok=True)
    jobs = Path(at.LR_JOB_DIR)
    ghi_chu = {}
    for k, ca in CA.items():
        cv = {c: v for c, v in ca.items() if not c.startswith("_")}
        hang = {"path": str(bang)}
        for c, khoa in cl.KHOA.items():
            hang[khoa] = cl.ghi_o(cv.get(c) or DONG)
        hang[cl.KHOA_TEN] = ca.get("_ten", "Custom")
        hsl = {h: "0" for h in at.COT_HSL}
        hsl.update({h: str(v) for h, v in (ca.get("_hsl") or {}).items()})
        cot = [*at.COT_CURVE, *at.COT_HSL]
        job = jobs / f"apply_{datetime.now():%Y%m%d_%H%M%S}_curve_v0_{k}.tsv"
        tmp = job.with_suffix(".part")
        tmp.write_text("path\t" + "\t".join(cot) + "\n" + str(bang) + "\t"
                       + "\t".join(str(hang.get(c, hsl.get(c, ""))) for c in cot) + "\n", encoding="utf-8")
        os.replace(tmp, job)
        _cho(lambda: at.job_state(job) in ("xong", "mat"), 120, f"Lightroom áp ca {k}")
        ghi_chu[k] = {"chua_nhan": [w for _p, w in at.job_unverified(job)]}
        ma = f"v0_{k}_{int(time.time())}"
        dest = thu_muc / "_v0_tam" / k
        cd.yeu_cau_dung(thu_muc, [{"path": str(bang)}], dest, ma, chat=100)
        _cho(lambda: cd.tien_do().get("ma") == ma and cd.tien_do().get("trang_thai") in ("xong", "loi"),
             180, f"Lightroom dựng ca {k}")
        ra = dict(cd.bang_anh())
        jpg = next(iter(ra.values()), None)
        if not jpg:
            raise SystemExit(f"Ca {k}: Lightroom không dựng ra ảnh ({cd.tien_do()})")
        shutil.copy2(jpg, v0 / f"{k}.jpg")
        print(f"  {k}: xong{'  (chưa nhận: ' + ', '.join(ghi_chu[k]['chua_nhan']) + ')' if ghi_chu[k]['chua_nhan'] else ''}")
    shutil.rmtree(thu_muc / "_v0_tam", ignore_errors=True)
    kq = phan_tich(thu_muc)
    kq["so_le"] = "giữ số lẻ" if not ghi_chu.get("c5", {}).get("chua_nhan") else "LÀM TRÒN (ghi số nguyên)"
    kq["16_diem"] = "giữ đủ" if not ghi_chu.get("c4", {}).get("chua_nhan") else "KHÔNG giữ đủ"
    (thu_muc / "curve_lr_hieu_chinh.json").write_text(json.dumps(kq, ensure_ascii=False, indent=1),
                                                      encoding="utf-8")
    print(f"  số lẻ: {kq['so_le']} · 16 điểm: {kq['16_diem']}")


def main(argv):
    if len(argv) < 3 or argv[1] not in ("tao", "chay", "phan_tich"):
        print(__doc__)
        return 2
    thu_muc = Path(argv[2])
    {"tao": tao, "chay": chay, "phan_tich": phan_tich}[argv[1]](thu_muc)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
