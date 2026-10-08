# -*- coding: utf-8 -*-
"""Buổi LÀM LẠI trong Lightroom sau lần tool ghi — không được coi là "sửa tay" (8/10).

CHUYỆN ĐANG SỬA (buổi kỷ yếu "raw 19.4")
    Người dùng xoá _autotone_baseline.tsv, áp lại preset cho cả buổi (WB 5000/+10,
    Tone 0, xoá sao) rồi phân tích lại. Job cũ 09:43 vẫn nằm trong thư mục jobs
    -> danh_dau_nguoi_sua thấy 856/1089 ảnh khác số tool đã ghi và báo "bỏ qua
    856 ảnh anh đã sửa tay" — người dùng chưa sửa ảnh nào.

Mục kiểm (plan() THẬT, nguồn catalog, thư mục buổi tên có dấu cách)
    1. Còn job, MẤT mốc -> "khong-moc": không lọc ảnh nào, tính trên catalog hiện tại.
    2. Còn mốc (preset cũ 5950/+19), cả buổi áp lại preset mới đồng loạt -> "dat-lai":
       không lọc, mốc MỚI = catalog hiện tại, ghi xong file mốc mang số mới.
    3. Sửa tay thật, lẻ tẻ (3/12 ảnh, mỗi ảnh một số) -> vẫn lọc 3 ảnh như cũ.
    4. Đổi đồng loạt nhưng chỉ ở thiểu số (3/12) -> vẫn là sửa tay.
    5. Cả buổi đồng bộ +0.3 EV (mỗi ảnh một số) -> không phải đặt lại, lọc hết.

Chạy:  python kiem_dat_lai_buoi.py
"""
from __future__ import annotations

import contextlib
import copy
import io
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at          # noqa: E402
import test_san_phang as ts    # noqa: E402

LOI: list = []
T0 = datetime(2026, 10, 8, 9, 0, 0)
N = 12
CU = {"Highlights2012": "16", "Shadows2012": "16", "Temperature": "5950", "Tint": "19",
      "WhiteBalance": "Custom", "Contrast2012": "5", "Whites2012": "-25", "Blacks2012": "-18"}


def ktra(ten, ok, ct=""):
    print(f"  [{'DAT ' if ok else 'HONG'}] {ten}  {ct}")
    if not ok:
        LOI.append(ten)


def anh_buoi() -> list:
    return [ts._anh(f"HUY0{4300 + i}", -1.2 + 0.05 * i, T0 + timedelta(seconds=6 * i))
            for i in range(N)]


def tool_exp(i: int) -> float:
    """Exposure tool đã ghi ở lần trước cho ảnh i (khác 0, mỗi ảnh một số)."""
    return round(-0.40 + 0.03 * i, 2)


def dung(td: Path, co_moc: bool) -> tuple[Path, Path]:
    """Thư mục buổi + thư mục jobs có job cũ của buổi (và mốc nếu co_moc)."""
    buoi = td / "buoi thu"
    buoi.mkdir()
    jobs = td / "jobs"
    jobs.mkdir()
    ds = anh_buoi()
    dong = ["path\tExposure2012\tTemperature\tTint"]
    dong += [f"{r['path']}\t{tool_exp(i):.2f}\t6230\t21" for i, r in enumerate(ds)]
    (jobs / f"apply_20261008_094312_{at.ten_job(buoi.name)}.done").write_text(
        "\n".join(dong) + "\n", encoding="utf-8")
    if co_moc:
        at.save_baseline(buoi, {at.khoa_duong_dan(r["path"]): dict(CU, Exposure2012="0")
                                for r in ds}, gop=False)
    return buoi, jobs


def chay(buoi: Path, jobs: Path, xuat: dict) -> list:
    at.LR_JOB_DIR = jobs
    ds = anh_buoi()
    export = {at.khoa_duong_dan(r["path"]): dict(xuat(i)) for i, r in enumerate(ds)}
    cfg = dict(at.DEFAULTS, source="catalog", burst=False, blink=False)
    #  ban xuat MOI hon job (nhu that: phan tich sau khi ap lai preset)
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        at.plan(ds, cfg, buoi, export, ban_xuat=None)
    return ds


def main() -> int:
    MOI = {"Exposure2012": "0", "Highlights2012": "0", "Shadows2012": "0", "Temperature": "5000",
           "Tint": "10", "WhiteBalance": "Custom", "Contrast2012": "0", "Whites2012": "0",
           "Blacks2012": "0"}

    def tool_con(i):                       # catalog van mang so tool ghi
        return dict(CU, Exposure2012=f"{tool_exp(i):.2f}", Temperature="6230", Tint="21")

    # ---- 1. mat moc
    with tempfile.TemporaryDirectory(prefix="kiem_dat_lai_") as t:
        buoi, jobs = dung(Path(t), co_moc=False)
        ds = chay(buoi, jobs, lambda i: MOI)
        ktra("mất mốc + còn job cũ -> 'khong-moc'", at.DAT_LAI_BUOI == "khong-moc", repr(at.DAT_LAI_BUOI))
        ktra("… không lọc ảnh nào là 'sửa tay'", at.SO_ANH_NGUOI_SUA == 0 and len(ds) == N,
             f"lọc {at.SO_ANH_NGUOI_SUA}, còn {len(ds)}")
        ktra("… tính trên catalog hiện tại (5000 K)", all(at.get_f(r["crs"], "Temperature") == 5000 for r in ds))

    # ---- 2. dat lai dong loat, con moc
    with tempfile.TemporaryDirectory(prefix="kiem_dat_lai_") as t:
        buoi, jobs = dung(Path(t), co_moc=True)
        ds = chay(buoi, jobs, lambda i: MOI)
        ktra("áp lại preset cả buổi -> 'dat-lai'", at.DAT_LAI_BUOI == "dat-lai", repr(at.DAT_LAI_BUOI))
        ktra("… không lọc ảnh nào", at.SO_ANH_NGUOI_SUA == 0 and len(ds) == N, f"lọc {at.SO_ANH_NGUOI_SUA}")
        ktra("… mốc MỚI = catalog hiện tại, không dùng preset cũ 5950",
             all(at.get_f(r["crs"], "Temperature") == 5000 and r.get("moc_moi") for r in ds))
        at.LAST_JOB = None
        with contextlib.redirect_stderr(io.StringIO()):
            at.write_sidecars(ds, dict(at.DEFAULTS, source="catalog"), buoi)
        moc = at.load_baseline(buoi)
        ktra("… ghi xong: file mốc mang số mới (5000 K), không giữ mốc cũ",
             len(moc) == N and all(at.get_f(v, "Temperature") == 5000 for v in moc.values()),
             f"{sorted({v.get('Temperature') for v in moc.values()})}")
        ktra("… có job gửi đi", at.LAST_JOB is not None)
        #  lan sau: plugin da ap job vua ghi (doi .done, catalog mang so tool ghi)
        #  -> khong "dat lai", khong loc ai, van tinh tren moc MOI 5000 K
        job = at.LAST_JOB
        da_gui = {Path(d.split("\t")[0]).stem: d.split("\t")
                  for d in job.read_text(encoding="utf-8").splitlines()[1:]}
        cot = job.read_text(encoding="utf-8").splitlines()[0].split("\t")
        job.rename(job.with_suffix(".done"))
        (jobs / job.with_suffix(".done").name).touch()

        def sau_ghi(i):
            h = da_gui[f"HUY0{4300 + i}"]
            return dict(MOI, Exposure2012=h[cot.index("Exposure2012")])
        ds2 = chay(buoi, jobs, sau_ghi)
        ktra("… lần chạy kế tiếp (catalog = số tool vừa ghi): không 'dat-lai', không lọc",
             at.DAT_LAI_BUOI == "" and at.SO_ANH_NGUOI_SUA == 0 and len(ds2) == N,
             f"{at.DAT_LAI_BUOI!r} lọc {at.SO_ANH_NGUOI_SUA}")
        ktra("… vẫn tính trên mốc MỚI 5000 K (không cộng dồn lên số tool ghi)",
             all(at.get_f(r["crs"], "Temperature") == 5000 and at.get_f(r["crs"], "Exposure2012") == 0
                 for r in ds2))

    # ---- 3. sua tay that, le te
    with tempfile.TemporaryDirectory(prefix="kiem_dat_lai_") as t:
        buoi, jobs = dung(Path(t), co_moc=True)
        sua = {2: "0.35", 5: "-0.80", 9: "0.10"}
        ds = chay(buoi, jobs, lambda i: dict(tool_con(i), Exposure2012=sua[i]) if i in sua else tool_con(i))
        ktra("sửa tay 3/12 ảnh, mỗi ảnh một số -> vẫn lọc 3 ảnh", at.SO_ANH_NGUOI_SUA == 3
             and at.DAT_LAI_BUOI == "" and len(ds) == N - 3, f"lọc {at.SO_ANH_NGUOI_SUA}, {at.DAT_LAI_BUOI!r}")

    # ---- 4. dong loat nhung thieu so
    with tempfile.TemporaryDirectory(prefix="kiem_dat_lai_") as t:
        buoi, jobs = dung(Path(t), co_moc=True)
        ds = chay(buoi, jobs, lambda i: MOI if i < 3 else tool_con(i))
        ktra("đặt lại chỉ 3/12 ảnh -> vẫn là sửa tay (lọc 3)", at.SO_ANH_NGUOI_SUA == 3
             and at.DAT_LAI_BUOI == "", f"lọc {at.SO_ANH_NGUOI_SUA}, {at.DAT_LAI_BUOI!r}")

    # ---- 5. dong bo +0.3 ca buoi
    with tempfile.TemporaryDirectory(prefix="kiem_dat_lai_") as t:
        buoi, jobs = dung(Path(t), co_moc=True)
        ds = chay(buoi, jobs, lambda i: dict(tool_con(i), Exposure2012=f"{tool_exp(i) + 0.3:.2f}"))
        ktra("đồng bộ +0.3 EV cả buổi (mỗi ảnh một số) -> lọc hết, không coi là đặt lại",
             at.SO_ANH_NGUOI_SUA == N and at.DAT_LAI_BUOI == "", f"lọc {at.SO_ANH_NGUOI_SUA}, {at.DAT_LAI_BUOI!r}")

    print("TAT CA DAT" if not LOI else f"{len(LOI)} LOI: {LOI}")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
