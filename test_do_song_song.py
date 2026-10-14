#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đo da SONG SONG ở lượt hoàn thiện (curve_da.BoDo — 14/10).

CHUYỆN ĐANG CANH
    User 14/10: "xử lý 1000 ảnh theo cách hiện tại thì thời gian phải tốn 15 phút".
    Lượt 2 buổi 2709 (1.074 ảnh): Lightroom trả preview xong sau 9 phút mà job curve 18
    phút mới ghi — đo một luồng ~0.5 s/ảnh, bị Lightroom giành CPU. BoDo đo nhiều tiến
    trình. Hỏng kiểu nào cũng KHÔNG được mất ảnh hay đổi số đo: tiến trình con chết /
    không mở được pool -> đo tại chỗ; số đo song song == số đo tuần tự.

Mục kiểm
    1. r_gon chỉ mang khoá cần đo; _gon: mảng float64 -> float32, giá trị khác giữ
    2. n = 1: đo tại chỗ, lay() trả ngay, đúng bằng do_anh
    3. n = 2 (tiến trình THẬT): số đo == tuần tự (mảng sai < 1e-6), đủ mọi ảnh
    4. submit hỏng -> đo tại chỗ, n = 1, không mất ảnh
    5. tiến trình con chết giữa chừng (future lỗi) -> đo lại tại chỗ
    6. bo(): bỏ việc đang chờ; so_tho(): AUTOTONE_CURVE_THO ép số tiến trình

Chạy:  python test_do_song_song.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

LOI: list = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


def giong(a: dict, b: dict) -> tuple[bool, str]:
    """Hai kết quả do_anh như nhau (mảng so gần đúng — float32 qua ống)."""
    if set(a) != set(b):
        return False, f"khoá khác: {sorted(set(a) ^ set(b))}"
    for k in a:
        x, y = a[k], b[k]
        if isinstance(x, np.ndarray) or isinstance(y, np.ndarray):
            if np.shape(x) != np.shape(y) or not np.allclose(x, y, atol=1e-6):
                return False, f"{k} lệch"
        elif x != y and not (isinstance(x, float) and isinstance(y, float) and abs(x - y) < 1e-9):
            return False, f"{k}: {x!r} != {y!r}"
    return True, ""


class _HuSubmit:
    def submit(self, *a, **k):
        raise RuntimeError("pool hỏng")

    def shutdown(self, *a, **k):
        pass


class _FutureChet:
    def done(self):
        return True

    def result(self):
        raise RuntimeError("A process in the process pool was terminated abruptly")

    def cancelled(self):
        return False

    def exception(self):
        return RuntimeError("chết")

    def cancel(self):
        return False


def main() -> int:
    import autotone as at
    import curve_da as cd
    import test_curve_da as T

    os.environ.pop("AUTOTONE_CURVE_THO", None)
    cfg = dict(at.DEFAULTS)
    anh = [T.luu(T.canh(lech=(0.02 * i, 0.0, -0.01 * i), chay_pct=3.0 * i), f"ss{i}") for i in range(3)]
    r = dict(T.anh("SS"), cat_lr=(0.0, 0.0, 1.0, 1.0, 0.0))

    print("1. r_gon / _gon")
    g = cd.r_gon(dict(r, crs_hien={"Exposure2012": "0"}, curve_moc={"x": 1}))
    ktra("r_gon chỉ mang meter_boxes / preview_wh / cat_lr",
         set(g) == {"meter_boxes", "preview_wh", "cat_lr"}, str(sorted(g)))
    ktra("r_gon(None) -> None", cd.r_gon(None) is None)
    o = cd._gon({"a": np.zeros(3, np.float64), "b": np.zeros(2, np.int64), "c": 1.5})
    ktra("_gon: float64 -> float32, mảng nguyên / số giữ nguyên",
         o["a"].dtype == np.float32 and o["b"].dtype == np.int64 and o["c"] == 1.5)

    tuan_tu = [cd.do_anh(r, a, cfg) for a in anh]

    print("2. n = 1: đo tại chỗ")
    bo = cd.BoDo(cfg, n=1)
    for i, a in enumerate(anh):
        bo.gui(i, r, a)
    ra = dict(bo.lay())
    ktra("n=1: không mở pool, lay() trả ngay đủ ảnh", bo.ex is None and bo.n == 1 and len(ra) == 3)
    ok = [giong(cd._gon(tuan_tu[i]), ra[i]) for i in range(3)]
    ktra("n=1: kết quả == do_anh", all(x for x, _ in ok), "; ".join(m for _, m in ok if m))
    bo.dong()

    print("3. n = 2: tiến trình thật")
    bo = cd.BoDo(cfg, n=2)
    ktra("n=2: mở được pool", bo.ex is not None and bo.n == 2)
    for i, a in enumerate(anh * 2):
        bo.gui(i, r, a)
    import time
    ra, het = {}, time.monotonic() + 180
    while len(ra) < 6 and time.monotonic() < het:
        ra.update(bo.lay())
        time.sleep(0.05)
    bo.dong()
    ktra("n=2: đủ 6 ảnh, không còn việc chờ", len(ra) == 6 and bo.con() == 0, f"{len(ra)}")
    ok = [giong(cd._gon(tuan_tu[i % 3]), ra.get(i, {})) for i in range(6)]
    ktra("n=2: số đo song song == tuần tự", all(x for x, _ in ok), "; ".join(m for _, m in ok if m))
    ktra("n=2: mảng về là float32 (nửa RAM)",
         all(v.dtype == np.float32 for k in ra.values() for v in k.values() if isinstance(v, np.ndarray)))

    print("4. submit hỏng")
    bo = cd.BoDo(cfg, n=1)
    bo.ex, bo.n = _HuSubmit(), 2
    bo.gui("a", r, anh[0])
    ra = dict(bo.lay())
    ktra("submit hỏng: đo tại chỗ, n = 1, ảnh không mất", bo.ex is None and bo.n == 1 and "a" in ra
         and ra["a"].get("ok"), str(list(ra)))

    print("5. tiến trình con chết")
    bo = cd.BoDo(cfg, n=1)
    bo.ex, bo.n = _HuSubmit(), 2
    bo.cho = {"x": (_FutureChet(), r, anh[1]), "y": (_FutureChet(), r, anh[2])}
    ra = dict(bo.lay())
    ktra("future lỗi: cả hai ảnh đo lại tại chỗ", set(ra) == {"x", "y"} and all(v.get("ok") for v in ra.values())
         and bo.con() == 0, str(sorted(ra)))
    ok = giong(cd._gon(tuan_tu[1]), ra["x"])
    ktra("đo lại tại chỗ == do_anh", ok[0], ok[1])

    print("6. bo() / so_tho()")
    bo = cd.BoDo(cfg, n=1)
    bo.cho = {"z": (_FutureChet(), r, anh[0])}
    bo.xong = [("w", {})]
    bo.bo()
    ktra("bo(): không còn việc chờ, không trả kết quả cũ", bo.con() == 0 and bo.lay() == [])
    os.environ["AUTOTONE_CURVE_THO"] = "3"
    n, luong = cd.so_tho()
    ktra("AUTOTONE_CURVE_THO=3 -> 3 tiến trình", n == 3 and luong >= 1, f"{n}, {luong}")
    os.environ["AUTOTONE_CURVE_THO"] = "1"
    ktra("AUTOTONE_CURVE_THO=1 -> đo tại chỗ", cd.BoDo(cfg).ex is None)
    os.environ.pop("AUTOTONE_CURVE_THO", None)
    n, luong = cd.so_tho()
    ktra("mặc định: 1..4 tiến trình, 1..2 luồng ORT", 1 <= n <= 4 and 1 <= luong <= 2, f"{n}, {luong}")

    print(f"\n{len(LOI)} LOI" if LOI else "\nTAT CA DAT")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
