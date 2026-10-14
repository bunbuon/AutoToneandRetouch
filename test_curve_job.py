#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Curve điểm qua mốc / bản xuất / job — chạy lại KHÔNG cộng dồn (13/10).

CHUYỆN ĐANG CANH
    Curve da / nén cháy ghép vào curve MỐC (preset). Bài học 2705 (Exposure bị ghi gấp
    đôi) áp nguyên cho curve: lần chạy sau mà lấy curve ĐANG có trong catalog (đã mang
    curve tool ghi) làm nền là ghép chồng g2∘g1∘preset. Và curve người dùng tự kéo tay
    thì không bao giờ được đè.

    Hàm THẬT: attach_catalog_settings, save_baseline / load_baseline, write_lr_job,
    anh_da_curve, thong_so_trong_lr, last_applied, anh_da_hsl, anh_mang_curve_tool,
    curve_da.ket_thuc / ghi_job / du_dieu_kien.

Mục kiểm
    1. mốc cũ chưa có curve + bản xuất có (tool chưa ghi curve) -> bù vào mốc; trạng thái moc
    2. catalog đang mang ĐÚNG curve lượt 2 tool ghi -> "tool"; job lượt 1 trả về curve mốc
    3. catalog curve khác cả mốc lẫn tool -> "nguoi_sua": không reset, không làm curve
    4. bản xuất không có curve (plugin cũ) -> "khong_ro": không làm curve, job không ô curve
    5. job @curve không lọt glob cũ (thong_so_trong_lr, last_applied, anh_da_hsl)
    6. chạy lại: curve mới = g∘MỐC, không phải g∘(curve đang có)
    7. ảnh duyệt vẽ sau job curve (mới hơn job WB / Tone) -> chuỗi màu da không dùng
    8. đặt lại mốc (bo_moc) khi catalog mang curve tool -> mốc mới GIỮ curve mốc cũ
    9. LR_JOB_FIELDS: cột cũ giữ vị trí, curve ở cuối

Chạy:  python test_curve_job.py
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at  # noqa: E402
import curve_da as cd  # noqa: E402
import curve_lr as cl  # noqa: E402
import test_curve_da as T  # noqa: E402

LOI = []
TAM = Path(tempfile.mkdtemp(prefix="test_curve_job_"))
BUOI = TAM / "Buoi"
JOBS = TAM / "jobs"
PRESET = {"ToneCurveName2012": "Custom", "ToneCurvePV2012": "0,0,64,60,138,132,255,255",
          "ToneCurvePV2012Red": "0,0,255,255", "ToneCurvePV2012Green": "0,0,255,255",
          "ToneCurvePV2012Blue": "0,0,255,255"}
TOOL = dict(PRESET, ToneCurvePV2012Red="0,0,128,124,255,255")
TAY = dict(PRESET, ToneCurvePV2012Blue="0,0,100,110,255,255")


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


def p_(ten):
    return str(BUOI / f"{ten}.ARW").replace("\\", "/")


def xuat(ten, **cot):
    rec = {"Exposure2012": "0", "Highlights2012": "16", "Shadows2012": "16",
           "Temperature": "5250", "Tint": "16", "WhiteBalance": "Custom", at.LR_PATH_KEY: p_(ten)}
    rec.update(cot)
    return rec


def moc_cu(ten):
    """Bản ghi mốc chốt TRƯỚC 13/10 — không có cột curve."""
    return {k: v for k, v in xuat(ten).items() if k != at.LR_PATH_KEY}


def ghi_moc(recs: dict):
    at.save_baseline(BUOI, {at.khoa_duong_dan(p_(t)): dict(r, **{at.LR_PATH_KEY: p_(t)})
                            for t, r in recs.items()}, gop=False)


def job_curve(ten_anh, cot: dict, mt: float | None = None):
    JOBS.mkdir(parents=True, exist_ok=True)
    f = JOBS / f"apply_20261013_10{len(list(JOBS.glob('*'))):04d}_{at.ten_job(BUOI.name)}@curve.done"
    f.write_text("path\t" + "\t".join(at.COT_CURVE) + "\n" + p_(ten_anh) + "\t"
                 + "\t".join(cot.get(k, "") for k in at.COT_CURVE) + "\n", encoding="utf-8")
    if mt:
        os.utime(f, (mt, mt))
    return f


def gan(ten, cur, **kw):
    r = {"path": p_(ten), "ok": True}
    at.attach_catalog_settings([r], {at.khoa_duong_dan(p_(ten)): cur}, BUOI, **kw)
    return r


def don():
    shutil.rmtree(BUOI, ignore_errors=True)
    shutil.rmtree(JOBS, ignore_errors=True)
    BUOI.mkdir(parents=True)


def muc1():
    """1. mốc cũ chưa có curve -> bù từ bản xuất"""
    don()
    ghi_moc({"A": moc_cu("A")})
    r = gan("A", xuat("A", **PRESET))
    moc = at.load_baseline(BUOI)[at.khoa_duong_dan(p_("A"))]
    ktra("mốc được bù bốn curve + tên", all(moc.get(k) == PRESET[k] for k in at.COT_CURVE), str(moc.get("ToneCurvePV2012")))
    ktra("trạng thái moc, curve_moc = preset", r["curve_tt"] == "moc" and r["curve_moc"] == PRESET)
    ktra("du_dieu_kien: làm curve được", cd.du_dieu_kien(r) == "")


def muc2():
    """2. catalog mang curve tool ghi -> lượt 1 trả về mốc"""
    don()
    ghi_moc({"A": dict(moc_cu("A"), **PRESET)})
    job_curve("A", TOOL)
    r = gan("A", xuat("A", **TOOL))
    ktra("trạng thái tool", r["curve_tt"] == "tool", r["curve_tt"])
    ktra("curve_reset = curve mốc", r.get("curve_reset") == PRESET)
    r.update(new_exposure=0.0, new_highlights=16, new_shadows=16, new_temp=5250, new_tint=16,
             old_temp=5250, old_tint=16)
    job = at.write_lr_job([r], BUOI.name, job_dir=JOBS)
    row = list(cd.doc_job(job).values())[0]
    ktra("job lượt 1: ô curve = curve mốc", all(row.get(k) == PRESET[k] for k in at.COT_CURVE),
         row.get("ToneCurvePV2012Red"))
    ktra("du_dieu_kien: vẫn làm curve (ghép lại lên mốc)", cd.du_dieu_kien(r) == "")


def muc3():
    """3. người dùng sửa curve tay"""
    don()
    ghi_moc({"A": dict(moc_cu("A"), **PRESET)})
    job_curve("A", TOOL)
    r = gan("A", xuat("A", **TAY))
    ktra("trạng thái nguoi_sua", r["curve_tt"] == "nguoi_sua", r["curve_tt"])
    ktra("không reset", not r.get("curve_reset"))
    ktra("du_dieu_kien: nguoi-sua-curve", cd.du_dieu_kien(r) == "nguoi-sua-curve")
    r.update(new_exposure=0.0, new_highlights=16, new_shadows=16, new_temp=5250, new_tint=16,
             old_temp=5250, old_tint=16)
    row = list(cd.doc_job(at.write_lr_job([r], BUOI.name, job_dir=JOBS)).values())[0]
    ktra("job lượt 1: ô curve TRỐNG (không đụng curve tay)", not any(row.get(k) for k in at.COT_CURVE))


def muc4():
    """4. plugin cũ: bản xuất không có curve"""
    don()
    r = gan("A", xuat("A"))
    ktra("trạng thái khong_ro", r["curve_tt"] == "khong_ro")
    ktra("du_dieu_kien: plugin-cu", cd.du_dieu_kien(r) == "plugin-cu")


def muc5():
    """5. job @curve không lọt glob cũ"""
    don()
    job_curve("A", TOOL)
    ktra("thong_so_trong_lr bỏ job @curve", at.thong_so_trong_lr(BUOI, JOBS) == {})
    ktra("last_applied bỏ job @curve", at.last_applied(BUOI, JOBS) == {})
    ktra("anh_da_hsl bỏ job @curve", at.anh_da_hsl(BUOI, JOBS) == set())
    ktra("anh_da_curve nhặt job @curve", at.khoa_duong_dan(p_("A")) in at.anh_da_curve(BUOI, JOBS))


def muc6():
    """6. chạy lại: ghép lên MỐC"""
    T.cai_gia()
    cfg = T.cfg_()
    a = T.canh(lech=(0.02, 0.0, -0.015))
    kq = []
    for cur in (PRESET, TOOL):
        #  crs = bản xuất HIỆN TẠI (đường moc-cu-khac-quy-trinh / mốc mới lấy catalog) —
        #  curve tool cũ nằm ngay đó; ghép phải lấy curve_moc, không lấy crs
        r = T.anh(curve_moc=dict(PRESET), curve_tt="moc" if cur is PRESET else "tool",
                  crs=dict(cur))
        d = T.do_lai(a, r, cfg, "j6")
        cd.ket_thuc([r], {id(r): d}, cfg)
        kq.append(r.get("curve_ghi"))
    ktra("cùng ảnh dựng, catalog đang preset hay đang curve tool -> CÙNG curve ghi",
         kq[0] is not None and kq[0] == kq[1])
    red = cl.doc_o(kq[0]["ToneCurvePV2012Red"])
    ktra("curve Red không chứa nút của curve tool cũ (128,124)", (128.0, 124.0) not in red, str(red))


def muc7():
    """7. ảnh duyệt mang curve tool"""
    don()
    anh = BUOI / "_duyet" / "A.jpg"
    anh.parent.mkdir(parents=True)
    anh.write_bytes(b"x")
    now = time.time()
    os.utime(anh, (now, now))
    r = {"curve_tool_gio": now - 10}
    ktra("job curve mới hơn job WB / Tone, ảnh vẽ sau job curve -> bỏ",
         at.anh_mang_curve_tool(r, anh, gio_job=now - 60))
    ktra("job WB / Tone mới hơn job curve (lượt 1 đã trả curve mốc) -> dùng được",
         not at.anh_mang_curve_tool(r, anh, gio_job=now - 5))
    ktra("chưa từng ghi curve -> dùng được", not at.anh_mang_curve_tool({}, anh, gio_job=now - 60))


def muc8():
    """8. đặt lại mốc khi catalog mang curve tool"""
    don()
    ghi_moc({"A": dict(moc_cu("A"), **PRESET)})
    job_curve("A", TOOL)
    r = gan("A", xuat("A", Exposure2012="0.5", **TOOL), bo_moc=True)
    ktra("mốc mới: curve_moc vẫn là preset", r["curve_moc"] == PRESET, str(r["curve_moc"].get("ToneCurvePV2012Red")))
    ktra("crs (mốc mới sẽ lưu) giữ curve preset", r["crs"].get("ToneCurvePV2012Red") == PRESET["ToneCurvePV2012Red"])
    ktra("trạng thái tool (lượt 1 trả về mốc)", r["curve_tt"] == "tool", r["curve_tt"])


def muc9():
    """9. thứ tự cột job"""
    f = at.LR_JOB_FIELDS
    ktra("cột đầu không đổi", f[:5] == ["Exposure2012", "Highlights2012", "Shadows2012", "Temperature", "Tint"])
    n_l = len(at.COT_HSL_L)
    ktra("COT_HSL_L (Luminance Cam, 14/10) ở cuối", f[-n_l:] == list(at.COT_HSL_L))
    ktra("COT_CURVE ngay trước", f[-n_l - len(at.COT_CURVE):-n_l] == list(at.COT_CURVE))
    ktra("COT_HSL ngay trước curve",
         f[-n_l - len(at.COT_CURVE) - len(at.COT_HSL):-n_l - len(at.COT_CURVE)] == list(at.COT_HSL))


def main():
    at.LR_JOB_DIR = JOBS
    for f in (muc1, muc2, muc3, muc4, muc5, muc6, muc7, muc8, muc9):
        print(f.__doc__.splitlines()[0])
        try:
            f()
        except Exception as ex:                                  # noqa: BLE001
            import traceback
            traceback.print_exc()
            ktra(f"{f.__name__} không sập", False, repr(ex))
    shutil.rmtree(TAM, ignore_errors=True)
    print(f"\n{len(LOI)} LOI" if LOI else "\nTAT CA DAT")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
