#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mặt nạ DA MẶT trên ảnh Lightroom dựng (mat_na_da.py — 13/10).

CHUYỆN ĐANG CANH
    User 13/10: "cần tách ra được mask của da mặt". Mặt nạ sai thì đo da sai: lẫn môi /
    mắt là da đỏ hơn thật; lẫn viền tóc / nền là da tối / ám màu nền; lẫn điểm bóng loáng
    là da trắng hơn; chọn nhầm mặt khách phía sau là chỉnh màu theo người khác.

    Ảnh giả + bộ dò mặt / phân vùng giả (test_curve_da). Logic mặt nạ là hàm THẬT.

Mục kiểm
    1. phân vùng: chỉ nhãn da + mũi; mắt, môi KHÔNG vào mặt nạ
    2. co mép: điểm sát mép vùng da bị bỏ
    3. điểm bóng loáng (≥ 250) bị bỏ; da_tho vẫn giữ (để biết da sáng tới đâu)
    4. điểm quá tối so với da (bóng đổ) bị bỏ
    5. dự phòng (không có mô hình): elip − mắt − miệng ∩ skin_mask, ≥ 400 điểm
    6. chọn mặt: cùng tỉ lệ khung -> mặt TRÙNG khung tool đã đo (không lấy khách to hơn);
       khác tỉ lệ (đã crop) -> mặt lớn nhất điểm ≥ 0.7
    7. quá ít điểm da -> rỗng + lý do
    8. (tuỳ chọn) mô hình THẬT trên ảnh mặt thật: AUTOTONE_ANH_MAT=<ảnh> + mô hình
       (FACE_PARSE_ONNX hoặc mo_hinh/) — mắt / miệng không vào mặt nạ

Chạy:  python test_mat_na_da.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mat_na_da as mn  # noqa: E402
import test_curve_da as T  # noqa: E402

LOI = []
CX, CY = T.MAT[0] + T.MAT[2] / 2, T.MAT[1] + T.MAT[3] / 2


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


def gia(parse=True):
    T.cai_gia()
    if not parse:
        mn.trang_thai = lambda: {"co": False, "kieu": None, "duong": "", "ly_do": "gia"}


def anh_u8(**kw):
    return T.u8(T.canh(**kw))


def muc1():
    """1. phân vùng: mắt, môi không vào mặt nạ"""
    gia()
    m = mn.mat_na(anh_u8(mat_mau_da=True), T.anh())             # mắt / môi màu da
    da = m["da"]
    ktra("kiểu = parse, đủ điểm", m["kieu"] == "parse" and m["n"] >= 400, f"{m['kieu']} {m['n']}")
    ktra("tâm hai mắt KHÔNG trong mặt nạ", not da[int(CY - 30), int(CX - 35)] and not da[int(CY - 30), int(CX + 35)])
    ktra("môi KHÔNG trong mặt nạ", not da[int(CY + 65), int(CX)])
    ktra("má trong mặt nạ", bool(da[int(CY + 20), int(CX + 50)]))
    return m


def muc2(m):
    """2. co mép"""
    da = m["da"]
    #  mép phải elip mặt ở hàng CY: x = CX + 0.48·w
    mep = int(CX + T.MAT[2] * 0.48)
    ktra("điểm sát mép da (2 px) bị bỏ", not da[int(CY), mep - 2].any())


def muc3():
    """3. điểm bóng loáng bị bỏ; da_tho giữ"""
    gia()
    a = anh_u8()
    a[int(CY + 20) - 3:int(CY + 20) + 3, int(CX + 50) - 3:int(CX + 50) + 3] = 255
    m = mn.mat_na(a, T.anh())
    ktra("điểm 255 trên má KHÔNG trong mặt nạ", not m["da"][int(CY + 20), int(CX + 50)])
    ktra("da_tho vẫn có điểm đó", bool(m["da_tho"][int(CY + 20), int(CX + 50)]))


def muc4():
    """4. điểm quá tối so với da bị bỏ"""
    gia()
    a = anh_u8()
    y, x = int(CY + 20), int(CX - 50)
    a[y - 4:y + 4, x - 4:x + 4] = (a[y, x].astype(int) * 0.2).astype(np.uint8)
    m = mn.mat_na(a, T.anh())
    ktra("điểm tối 0.2× da KHÔNG trong mặt nạ", not m["da"][y, x])


def muc5():
    """5. dự phòng"""
    gia(parse=False)
    m = mn.mat_na(anh_u8(mat_mau_da=True), T.anh())             # mắt / môi màu da
    da = m["da"]
    ktra("kiểu = du_phong, ≥ 400 điểm", m["kieu"] == "du_phong" and m["n"] >= 400, f"{m['kieu']} {m['n']}")
    ktra("dự phòng: mắt KHÔNG trong mặt nạ", not da[int(CY - 30), int(CX - 35)] and not da[int(CY - 30), int(CX + 35)])
    ktra("dự phòng: miệng KHÔNG trong mặt nạ", not da[int(CY + 65), int(CX)])
    ktra("dự phòng: nền ngoài elip KHÔNG trong mặt nạ", not da[int(CY), int(T.MAT[0] + 3)])


def muc6():
    """6. chọn mặt"""
    W, H = T.W, T.H
    khach = (600.0, 60.0, 240.0, 300.0, 0.97, None)               # khách to hơn, điểm cao hơn
    chu = (360.0, 160.0, 180.0, 240.0, 0.80, None)
    r = {"meter_boxes": [[360 / 2, 160 / 2, 180 / 2, 240 / 2]], "preview_wh": (W // 2, H // 2)}
    ds, crop = mn.chon_mat([khach, chu], r, W, H)
    ktra("cùng tỉ lệ: lấy mặt TRÙNG khung tool đo, không lấy khách", ds == [chu] and not crop, str(ds))
    r2 = dict(r, preview_wh=(W // 2, H // 3))                          # đã crop
    ds2, crop2 = mn.chon_mat([chu, khach], r2, W, H)
    ktra("khác tỉ lệ (crop): mặt lớn nhất điểm ≥ 0.7", ds2 == [khach] and crop2, str(ds2))
    ds3, _ = mn.chon_mat([], r, W, H)
    ktra("không dò lại được: dùng khung tool đã đo (quy đổi)", len(ds3) == 1
         and abs(ds3[0][0] - 360) < 1e-6 and ds3[0][4] == 0.0, str(ds3))


def muc7():
    """7. quá ít điểm da"""
    gia()
    mn.tim_mat = lambda img: [(440.0, 260.0, 30.0, 30.0, 0.95, None)]   # mặt tí hon (< 40 px)
    m = mn.mat_na(anh_u8(), None)                       # không có khung tool đo để lùi về
    ktra("mặt tí hon: rỗng + lý do", m["n"] == 0 and not m["da"].any() and m["ly_do"], m["ly_do"])


def muc8():
    """8. mô hình THẬT (tuỳ chọn)"""
    p = os.environ.get("AUTOTONE_ANH_MAT")
    import importlib
    importlib.reload(mn)                                          # bỏ hàm giả
    if not p or not Path(p).is_file() or not mn.trang_thai()["co"]:
        print("  BỎ QUA: đặt AUTOTONE_ANH_MAT=<ảnh có mặt> và có mô hình phân vùng mặt")
        return
    from PIL import Image
    img = np.asarray(Image.open(p).convert("RGB"))
    mats = mn.tim_mat(img)
    m = mn.mat_na(img, None)
    ktra("ảnh thật: kiểu parse, ≥ 400 điểm", m["kieu"] == "parse" and m["n"] >= 400, f"{m['kieu']} {m['n']}")
    lon = max(mats, key=lambda f: f[2] * f[3]) if mats else None
    if lon and lon[5]:
        moc = lon[5]
        mat_ngoai = [not m["da"][int(y), int(x)] for x, y in moc[:2]]
        mieng = ((moc[3][0] + moc[4][0]) / 2, (moc[3][1] + moc[4][1]) / 2)
        ktra("ảnh thật: hai mắt KHÔNG trong mặt nạ", all(mat_ngoai))
        ktra("ảnh thật: giữa miệng KHÔNG trong mặt nạ", not m["da"][int(mieng[1]), int(mieng[0])])


def main():
    m = None
    for f in (muc1, muc2, muc3, muc4, muc5, muc6, muc7, muc8):
        print(f.__doc__.splitlines()[0])
        try:
            if f is muc1:
                m = f()
            elif f is muc2:
                if m is not None:
                    f(m)
            else:
                f()
        except Exception as ex:                                  # noqa: BLE001
            import traceback
            traceback.print_exc()
            ktra(f"{f.__name__} không sập", False, repr(ex))
    print(f"\n{len(LOI)} LOI" if LOI else "\nTAT CA DAT")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
