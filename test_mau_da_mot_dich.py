#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chuỗi màu da MỘT ĐÍCH khi chọn mẫu màu da (13/10) — at.chuoi_mau_da_mau.

CHUYỆN ĐANG SỬA (user 13/10)
    "Đo được màu da đích người dùng mong muốn ... sau Exposure -> HL/SH -> WB -> Exposure
    chỉnh lại theo WB thì đưa ra thông số hiện tại so với đích, xem đang ở đâu; cân nhắc
    chỉnh lại WB; HSL / CG bật thì can thiệp để ra màu đích từ những thứ đã chỉnh; không
    can thiệp được thêm thì giữ nguyên." Chốt: (1) đích lấy từ MẪU màu da; (2) không tới
    được đích thì VẪN áp phần làm da gần đích hơn, miễn không làm vùng trắng ám.
    Trước đó: WB nhắm điểm điều khiển 16.6°, HSL Cưới khoảng 36–41°, CG 34.4° — CG kéo da
    đúng gu (38.5–41°) về phía ĐỎ.

Mục kiểm (plan() thật, nguồn catalog, Loại buổi Cưới)
    1. Da vàng hơn mẫu 10°: HSL Cam xoay về đỏ, chạm trần 15 VẪN áp (gần đích hơn);
       báo cáo từng ảnh có đích / sau WB / sau HSL; tóm tắt MAU_DA["mau"].
    2. Da trong vùng ổn (±2°): không ghi HSL, không Color Grading.
    3. Một đích: CG nhắm hue của MẪU — mẫu 45°, da 45° thì không grade (đích cũ 34.4°
       sẽ grade về đỏ).
    4. CG không làm vùng trắng ám: vecto ≤ trang_tran_cg; bỏ trần thì Sat lớn hơn hẳn;
       hue sau CG nằm giữa sau-HSL và đích (không vượt).
    5. Chốt vượt đích: cảnh nửa vàng hơn 14°, nửa ĐỎ hơn 2° -> HSL chỉ xoay rất ít về đỏ
       (không đẩy nửa đỏ quá đích hơn vùng ổn).
    6. Xét lại WB theo vùng trắng (ảnh duyệt + job thật trên đĩa): vùng trắng ám hồng
       (+a) -> Tint GIẢM; lưu sổ; tính lại với ảnh duyệt cũ -> WB y nguyên (không trôi);
       Ghi lại + duyệt với vùng trắng đã khớp -> "giữ", WB vẫn y nguyên.
    7. Vùng trắng lệch dưới ngưỡng -> giữ WB; mẫu không có số vùng trắng -> giữ, báo.
    8. Không chọn mẫu -> đường cũ (không có mau_da_bao).

Chạy:  python test_mau_da_mot_dich.py
"""
from __future__ import annotations

import contextlib
import io
import math
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
TAM = Path(tempfile.mkdtemp(prefix="mau_da_1dich_"))
os.environ["AUTOTONE_DATA"] = str(TAM / "du_lieu")

import numpy as np               # noqa: E402
from PIL import Image            # noqa: E402

import autotone as at            # noqa: E402
import test_chuoi_mau_da as tc   # noqa: E402
import test_2ban_quay as tq      # noqa: E402

LOI: list = []


def ktra(ten, dk, chi_tiet=""):
    print(f"  [{'DAT' if dk else 'LOI'}] {ten}  {chi_tiet}")
    if not dk:
        LOI.append(ten)


def mau_tu_hue(hue: float, chroma: float = 0.045, L: float = 0.80) -> list:
    """sRGB 0-255 của màu OkLab (L, chroma, hue°)."""
    lab = np.array([L, chroma * math.cos(math.radians(hue)), chroma * math.sin(math.radians(hue))])
    lin = np.linalg.inv(tc.M1) @ ((np.linalg.inv(tc.M2) @ lab) ** 3)
    return [int(round(255 * at._lin_to_srgb(v))) for v in lin]


def mau_mau(hue=40.0, trang=(0.0, 0.0)):
    rgb = mau_tu_hue(hue)
    md = {"ten": "Thử", "trong": rgb, "ngoai": rgb}
    if trang is not None:
        md["trang"] = {"trong": list(trang), "ngoai": list(trang)}
    return md


def hue_mau(md) -> float:
    lab = at.mau_dich_lab(md["trong"])
    return math.degrees(math.atan2(lab[2], lab[1]))


def cfg_cuoi(md, **kw):
    c = dict(at.DEFAULTS, loai_buoi="cuoi", mau_da_dich=md, hsl_da_ky_yeu=False,
             hsl_da_cuoi=True)
    c.update(kw)
    return c


def bo(d: Path, mat_xoay: list, md) -> list:
    """Ảnh liền nhau (một cảnh), da DỰ ĐOÁN lệch hue mẫu theo từng số trong mat_xoay
    (độ OkLab; dương = đỏ hơn)."""
    c = cfg_cuoi(md)
    items = []
    for i, x in enumerate(mat_xoay):
        r = tq.anh(f"M{i}", i * 5, -1.0, da=tc.da_lech(c, x, 1.0), may_K=5000)
        r["path"] = str(d / f"M{i}.ARW")
        r["crs"] = dict(tc.PRESET)
        r["meter_boxes"] = [[60.0, 40.0, 40.0, 40.0]]
        r["preview_wh"] = (160, 120)
        items.append(r)
    return items


def chay(items, d, jobs, md, **kw):
    return tc.chay(items, d, jobs, loai_buoi="cuoi", mau_da_dich=md, hsl_da_ky_yeu=False,
                   hsl_da_cuoi=kw.pop("hsl_da_cuoi", True), **kw)


def anh_duyet(d: Path, ten: str, da_rgb, trang_ab) -> None:
    """Ảnh duyệt giả 160×120: nền XÁM sáng mang độ ám trang_ab (OkLab), ô mặt màu da."""
    a, b = trang_ab
    lin = np.linalg.inv(tc.M1) @ ((np.linalg.inv(tc.M2) @ np.array([0.82, a, b])) ** 3)
    nen = [int(round(255 * at._lin_to_srgb(v))) for v in lin]
    arr = np.zeros((120, 160, 3), dtype=np.uint8)
    arr[:, :] = nen
    arr[40:80, 60:100] = da_rgb
    (d / "_duyet").mkdir(exist_ok=True)
    Image.fromarray(arr).save(d / "_duyet" / f"{ten}.jpg", quality=100, subsampling=0)


def ghi_job(kq: dict, d: Path, jobs: Path) -> None:
    """Job như plugin đã áp: write_lr_job thật -> .done, mtime lùi 60 s."""
    cu = at.LR_JOB_DIR
    at.LR_JOB_DIR = jobs
    try:
        p = at.write_lr_job(list(kq.values()), d.name)
    finally:
        at.LR_JOB_DIR = cu
    done = p.with_suffix(".done")
    os.replace(p, done)
    t = time.time() - 60
    os.utime(done, (t, t))


def main() -> int:
    jobs = TAM / "jobs"
    jobs.mkdir()

    # 1. da vang hon mau 10 do -> HSL ve do, cham tran van ap
    md = mau_mau(40.0)
    H = hue_mau(md)
    d1 = TAM / "vang"
    d1.mkdir()
    kq, mt = chay(bo(d1, [-10.0] * 6, md), d1, jobs, md)
    r = kq["M0"]
    b = r.get("mau_da_bao") or {}
    ktra("1 tom tat MAU_DA la chuoi mau", bool(mt.get("mau")) and mt.get("n") == 6, str(mt.get("n")))
    ktra("1 bao cao: dich = hue mau", abs(b.get("dich", (0,))[0] - H) < 0.6, f"{b.get('dich')} vs {H:.1f}")
    ktra("1 bao cao: sau WB vang hon ~10", abs(b.get("sau_wb", (0,))[0] - (H + 10)) < 1.5,
         str(b.get("sau_wb")))
    ktra("1 HSL Cam xoay ve do, cham tran -15 van ap", b.get("hsl", (0, 0))[0] == -15
         and r.get("hsl_ghi"), str(b.get("hsl")))
    ktra("1 sau HSL gan dich hon", abs(b["sau_hsl"][0] - H) < abs(b["sau_wb"][0] - H) - 4,
         f"{b.get('sau_wb')} -> {b.get('sau_hsl')}")
    ktra("1 job mang HSL moi", float(r["hsl_moi"]["HueAdjustmentOrange"]) == -15.0,
         str(r.get("hsl_moi", {}).get("HueAdjustmentOrange")))

    # 2. vung on
    d2 = TAM / "on"
    d2.mkdir()
    kq, _ = chay(bo(d2, [2.0, -2.0, 1.0, -1.0, 2.0, -2.0], md), d2, jobs, md, grade=True)
    ktra("2 da trong vung on: khong HSL", not any(x.get("hsl_ghi") for x in kq.values()))
    ktra("2 da trong vung on: khong CG", not any(x.get("gr_ghi") for x in kq.values()))

    # 3. mot dich cho CG: mau 45 do, da 45 do -> khong grade
    md45 = mau_mau(45.0)
    d3 = TAM / "mot_dich"
    d3.mkdir()
    kq, _ = chay(bo(d3, [0.0] * 6, md45), d3, jobs, md45, grade=True, hsl_da_cuoi=False)
    ktra("3 CG nham hue MAU (da = mau 45 -> khong grade)",
         not any(x.get("gr_ghi") for x in kq.values()),
         str([x.get("gr_sat") for x in kq.values()]))

    # 4. CG: vung trang khong am
    d4 = TAM / "cg"
    d4.mkdir()
    it4 = bo(d4, [-20.0] * 6, md)
    kq, _ = chay(it4, d4, jobs, md, grade=True, hsl_da_cuoi=False)
    r = kq["M0"]
    v = at.banh_xe(r.get("gr_hue", 0), r.get("gr_sat", 0))
    ktra("4 CG co grade", bool(r.get("gr_ghi") and r.get("gr_sat")), str(r.get("gr_sat")))
    ktra("4 vecto CG <= trang_tran_cg", float(np.hypot(*v)) <= at.DEFAULTS["trang_tran_cg"] + 1e-9,
         f"{np.hypot(*v):.4f}")
    b = r.get("mau_da_bao") or {}
    ktra("4 sau CG nam giua sau HSL va dich",
         abs(b["sau_cg"][0] - H) < abs(b["sau_hsl"][0] - H)
         and (b["sau_cg"][0] - H) * (b["sau_hsl"][0] - H) > 0, f"{b.get('sau_hsl')} -> {b.get('sau_cg')}")
    kq2, _ = chay(it4, d4, jobs, md, grade=True, hsl_da_cuoi=False, trang_tran_cg=1.0)
    ktra("4 dung bai: bo tran vung trang thi Sat lon hon han",
         kq2["M0"].get("gr_sat", 0) >= r.get("gr_sat", 0) + 3,
         f"{r.get('gr_sat')} vs {kq2['M0'].get('gr_sat')}")

    # 5. chot vuot dich
    d5 = TAM / "chot"
    d5.mkdir()
    kq, mt = chay(bo(d5, [-14.0, -14.0, -14.0, 2.0, 2.0, 2.0], md), d5, jobs, md)
    u = (kq["M0"].get("mau_da_bao") or {}).get("hsl", (0, 0))[0]
    ktra("5 nua do hon dich: HSL chi xoay it ve do (khong -11)", -4 <= u <= 0, str(u))

    # 6. xet lai WB theo vung trang
    d6 = TAM / "trang"
    d6.mkdir()
    it6 = bo(d6, [0.0] * 6, md)
    kw = dict(wb="skin", hsl_da_cuoi=False)
    k1, _ = chay(it6, d6, jobs, md, **kw)
    ghi_job(k1, d6, jobs)
    for ten in k1:
        anh_duyet(d6, ten, md["trong"], (0.010, 0.0))           # trang am hong
    k2, mt2 = chay(it6, d6, jobs, md, **kw)
    t1 = {t: (x["new_temp"], x["new_tint"]) for t, x in k1.items()}
    t2 = {t: (x["new_temp"], x["new_tint"]) for t, x in k2.items()}
    b = k2["M0"].get("mau_da_bao") or {}
    ktra("6 do duoc vung trang tren anh duyet", b.get("trang_lech") is not None
         and abs(b["trang_lech"][0] - 0.010) < 0.003, str(b.get("trang_lech")))
    ktra("6 trang am hong -> WB chinh, Tint GIAM", b.get("wb") == "chinh"
         and all(t2[t][1] < t1[t][1] for t in t1), f"{t1['M0']} -> {t2['M0']}")
    ktra("6 tom tat: 1 canh chinh", mt2.get("wb_canh_chinh") == 1, str(mt2.get("wb_canh_chinh")))
    ktra("6 so luu theo buoi", at.file_wb_xet_lai(d6).is_file())
    k3, mt3 = chay(it6, d6, jobs, md, **kw)
    t3 = {t: (x["new_temp"], x["new_tint"]) for t, x in k3.items()}
    ktra("6 tinh lai voi anh duyet cu -> WB y nguyen (khong troi)", t3 == t2, f"{t2['M0']} vs {t3['M0']}")
    #  giao dien goi plan() lai TREN CUNG danh sach anh (refresh_plan) — phan xet lai WB
    #  cua lan truoc khong duoc cong don
    tai_cho = list(k3.values())
    exp = {at.khoa_duong_dan(x["path"]): dict(tc.PRESET) for x in tai_cho}
    cfg6 = dict(at.DEFAULTS, source="catalog", bo_qua_nguoi_sua=False, burst=False, blink=False,
                bu_sang_ca_buoi=0.0, max_ev_up=1.0, dong_bo_loat=False, loai_buoi="cuoi",
                mau_da_dich=md, hsl_da_ky_yeu=False, **kw)
    cu = at.LR_JOB_DIR
    at.LR_JOB_DIR = jobs
    lan = []
    try:
        for _ in range(2):
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                at.plan(tai_cho, cfg6, d6, exp)
            lan.append({Path(x["path"]).stem: (x["new_temp"], x["new_tint"]) for x in tai_cho})
    finally:
        at.LR_JOB_DIR = cu
    ktra("6 plan() lai tren cung danh sach (moi lan) -> WB y nguyen", all(t_ == t3 for t_ in lan),
         f"{t3['M0']} vs {[t_['M0'] for t_ in lan]}")
    #  Ghi lai + duyet: vung trang da khop mau
    ghi_job(k3, d6, jobs)
    time.sleep(0.05)
    for ten in k3:
        anh_duyet(d6, ten, md["trong"], (0.0005, 0.0))
    k4, mt4 = chay(it6, d6, jobs, md, **kw)
    t4 = {t: (x["new_temp"], x["new_tint"]) for t, x in k4.items()}
    ktra("6 duyet lai vung trang khop -> giu, WB y nguyen",
         (k4["M0"].get("mau_da_bao") or {}).get("wb") == "giu" and t4 == t3,
         f"{(k4['M0'].get('mau_da_bao') or {}).get('wb')} {t3['M0']} vs {t4['M0']}")

    # 7. duoi nguong / mau khong co vung trang
    d7 = TAM / "nho"
    d7.mkdir()
    it7 = bo(d7, [0.0] * 6, md)
    k1, _ = chay(it7, d7, jobs, md, **kw)
    ghi_job(k1, d7, jobs)
    for ten in k1:
        anh_duyet(d7, ten, md["trong"], (0.002, 0.0))
    k2, mt = chay(it7, d7, jobs, md, **kw)
    ktra("7 vung trang lech duoi nguong -> giu WB",
         (k2["M0"].get("mau_da_bao") or {}).get("wb") == "giu"
         and all((k1[t]["new_temp"], k1[t]["new_tint"]) == (k2[t]["new_temp"], k2[t]["new_tint"])
                 for t in k1))
    md_cu = mau_mau(40.0, trang=None)
    k3, mt = chay(it7, d7, jobs, md_cu, **kw)
    ktra("7 mau cu khong co vung trang -> giu, bao", mt.get("wb_co_trang") is False
         and (k3["M0"].get("mau_da_bao") or {}).get("wb") == "chua_do")

    # 8. khong chon mau -> duong cu
    d8 = TAM / "cu"
    d8.mkdir()
    k8, mt = tc.chay(bo(d8, [0.0] * 6, md), d8, jobs, loai_buoi="cuoi", hsl_da_ky_yeu=False)
    ktra("8 khong mau -> duong cu", not mt.get("mau")
         and not any(x.get("mau_da_bao") for x in k8.values()))

    print("TAT CA DAT" if not LOI else f"{len(LOI)} LOI")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
