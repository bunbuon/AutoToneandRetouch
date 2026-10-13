#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đo vùng da sáng CHUYỂN DẦN — CHỈ Canon; Sony / Nikon giữ y hệt (14/10).

CHUYỆN ĐANG CANH
    Bộ CR3 Canon EOS R (G:\\TestThacCao\\test, nắng trưa, da trắng): cùng hai người, cùng
    1/500 f/4 ISO 250 mà Exposure −0.33 / +0.15 xen kẽ. kiem_raw_that mục 4b: số đo mặt
    chỉ có hai mức (−0.66 khi ≥ 30% da sáng quá 220/255 → đo riêng vùng sáng; −1.1..−1.2
    khi dưới) — tắt quy tắc thì cặp lệch > 0.30 từ 4 về 0. Sửa: Canon trộn dần hai cách
    đo trong dải ±hl_da_tron_theo_may["CANON"] mức sRGB quanh công tắc cũ.

    User: "Hãy đặt ra các case theo loại máy. Nếu sửa mà làm thay đổi hết những gì đã
    đạt được ở Sony và Nikon thì không được." → mỗi hãng một ca; Sony / Nikon / ảnh không
    EXIF phải ra Y HỆT cách cũ (so TOÀN BỘ kết quả measure, từng số) ở mọi mức sáng.

    Ảnh mặt GIẢ: nửa mặt dính nắng, nửa trong bóng (×0.5) — đúng dáng da làm công tắc cũ
    nhảy (đo thường lấy cả phần bóng, đo vùng sáng chỉ lấy phần nắng). Cùng điểm ảnh, chỉ
    khác hãng / máy trong EXIF. Tăng sáng từng 0.025 EV, đo bằng measure() THẬT
    (detect_faces giả trả đúng ô mặt — YuNet không nhận mặt vẽ).

Mục kiểm
    1. tron_theo_may: Canon khớp, Sony / Nikon / không EXIF không khớp; DEFAULTS chỉ có
       Canon; bảng nằm trong cau_hinh_do (đổi bảng = đo lại, không nạp kết quả cũ)
    2. Sony, Nikon, không EXIF: mặc định == công tắc cũ, TỪNG SỐ, mọi mức sáng; Sony khớp
       SỐ CHUẨN đo bằng code trước khi sửa (commit 8f50502)
    3. Canon, cách cũ: có cú nhảy ở chỗ da sáng vượt 30% (≥ 3 lần bước thường) — chứng
       tỏ ca này chạm đúng bệnh
    4. Canon, mặc định: bước ở đúng chỗ đó ≤ một nửa cú nhảy cũ và ≤ 2 lần bước thường;
       không sinh bước nhảy mới ở chỗ khác; số đo mặt không giảm khi ảnh sáng lên
    5. Canon ngoài dải chuyển (hai đầu): y hệt cách cũ
    6. Canon, mặt có đốm bóng sáng (vài % da vượt 220 trước phần còn lại): bản sửa không
       sinh bước nhảy khi vào dải chuyển

Chạy:  python test_da_sang_tron.py
"""
from __future__ import annotations

import shutil
import statistics
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at  # noqa: E402

LOI = []
TAM = Path(tempfile.mkdtemp(prefix="test_da_sang_"))
W, H = 800, 1000
MAT = (290, 200, 220, 290)                       # x, y, rộng, cao của ô mặt
MAY = {"canon": ("Canon", "Canon EOS R"), "sony": ("SONY", "ILCE-7M4"),
       "nikon": ("NIKON CORPORATION", "NIKON Z 6_2"), "khong_exif": None}
GAIN = [round(0.025 * k, 3) for k in range(-16, 7)]      # −0.40 .. +0.15 EV


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


def anh(gain_ev: float, exif, p: Path, kieu: str = "nua_nang") -> Path:
    """Chân dung giả, vân da nhẹ. nua_nang: nửa trái mặt dính nắng, nửa phải trong bóng
    ×0.5. dom_sang: da đều, thêm đốm bóng (trán + gò má) sáng hơn ×1.3 — vài % da vượt
    220 trước khi phần lớn da tới đó."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    cx, cy = MAT[0] + MAT[2] / 2, MAT[1] + MAT[3] / 2
    e = ((xx - cx) / (MAT[2] * 0.46)) ** 2 + ((yy - cy) / (MAT[3] * 0.48)) ** 2
    rng = np.random.default_rng(7)
    if kieu == "nua_nang":
        nen = np.where(xx < cx + 20, 1.0, 0.5)
    else:
        dom = (((xx - cx) / 45) ** 2 + ((yy - (cy - 80)) / 22) ** 2 <= 1) \
            | (((xx - (cx - 50)) / 22) ** 2 + ((yy - (cy + 10)) / 18) ** 2 <= 1)
        nen = np.where(dom, 1.3, 0.85)
    tg = nen * (0.93 + 0.08 * np.clip(1 - e, 0, 1) ** 0.6) + rng.normal(0, 0.015, e.shape)
    lin = np.where((e <= 1)[..., None], np.array([0.80, 0.50, 0.38]) * tg[..., None], 0.18)
    lin[700:, 200:600] = [0.05, 0.05, 0.08]
    lin = np.clip(lin * 2 ** gain_ev, 0, 1)
    s = np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * lin ** (1 / 2.4) - 0.055)
    im = Image.fromarray((s * 255 + 0.5).astype(np.uint8))
    if exif:
        ex = Image.Exif()
        ex[271], ex[272] = exif
        im.save(p, quality=95, exif=ex.tobytes())
    else:
        im.save(p, quality=95)
    return p


def mat_gia(im, score=0.5):
    k = im.size[0] / W
    return [(MAT[0] * k, MAT[1] * k, MAT[2] * k, MAT[3] * k, 0.95, None)]


def do(p: Path, bang) -> dict:
    cfg = dict(at.DEFAULTS, canh_p365=False)
    if bang is not None:
        cfg["hl_da_tron_theo_may"] = bang
    r = at.measure(p, *at.cau_hinh_do(cfg))
    r.pop("path", None)
    return r


def bang_nhau(a, b) -> bool:
    if isinstance(a, dict):
        return isinstance(b, dict) and a.keys() == b.keys() and all(bang_nhau(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)):
        return isinstance(b, (list, tuple)) and len(a) == len(b) and all(bang_nhau(x, y) for x, y in zip(a, b))
    if isinstance(a, np.ndarray):
        return np.array_equal(a, b)
    if isinstance(a, float) and isinstance(b, float) and a != a and b != b:
        return True
    return a == b


def quet(ten: str, kieu: str = "nua_nang", gain=None) -> list:
    """[(gain, kết quả mặc định, kết quả công tắc cũ)] cho một hãng."""
    ra = []
    for g in gain or GAIN:
        p = anh(g, MAY[ten], TAM / f"{ten}_{kieu}_{g:+.3f}.jpg", kieu)
        ra.append((g, do(p, None), do(p, {})))
    return ra


#  SỐ CHUẨN: ca Sony nửa nắng đo bằng CODE TRƯỚC 14/10 (commit 8f50502, công tắc cứng) —
#  (gain, mặt EV, p95 da, màu da R G B). So code của chính bản này ở chế độ "công tắc cũ"
#  là chưa đủ: sửa nhầm cả công tắc cũ thì Sony đổi mà hai bên vẫn bằng nhau.
CHUAN_SONY = [
    (-0.4, -1.34467, 0.80392, (0.572731, 0.361056, 0.276049)), (-0.375, -1.32707, 0.80784, (0.579139, 0.366178, 0.278859)),
    (-0.35, -1.29425, 0.82353, (0.596964, 0.372954, 0.281521)), (-0.325, -1.2294, 0.82745, (0.624869, 0.386223, 0.292079)),
    (-0.3, -1.20198, 0.83529, (0.636534, 0.393981, 0.29891)), (-0.275, -1.18602, 0.83922, (0.643096, 0.399226, 0.303527)),
    (-0.25, -1.15593, 0.84706, (0.65469, 0.40783, 0.310816)), (-0.225, -1.15025, 0.85098, (0.658283, 0.410772, 0.313804)),
    (-0.2, -1.13189, 0.8549, (0.665981, 0.416523, 0.318866)), (-0.175, -1.1082, 0.86667, (0.68084, 0.4218, 0.325881)),
    (-0.15, -0.99809, 0.87451, (0.724687, 0.450166, 0.34175)), (-0.125, -0.97567, 0.87843, (0.733314, 0.458359, 0.343936)),
    (-0.1, -0.95225, 0.88627, (0.743405, 0.466348, 0.350381)), (-0.075, -0.92825, 0.8902, (0.754095, 0.474581, 0.357506)),
    (-0.05, -0.90304, 0.89804, (0.765574, 0.483389, 0.364907)), (-0.025, -0.87644, 0.9098, (0.781304, 0.491822, 0.372983)),
    (0.0, -0.84962, 0.91765, (0.803772, 0.498573, 0.381635)), (0.025, -0.82238, 0.92549, (0.819899, 0.507687, 0.390314)),
    (0.05, -0.79636, 0.92941, (0.833164, 0.517332, 0.398047)), (0.075, -0.77336, 0.93725, (0.845304, 0.526641, 0.398196)),
    (0.1, -0.74956, 0.94118, (0.857538, 0.535978, 0.404458)), (0.125, -0.72566, 0.94902, (0.870495, 0.545242, 0.412198)),
    (0.15, -0.69949, 0.95686, (0.888299, 0.55461, 0.420332))]


def muc1():
    """1. bảng theo máy"""
    b = at.cau_hinh_do(dict(at.DEFAULTS))[-1]
    ktra("DEFAULTS chỉ Canon (Sony / Nikon không có trong bảng)",
         set(at.DEFAULTS["hl_da_tron_theo_may"]) == {"CANON"}, str(at.DEFAULTS["hl_da_tron_theo_may"]))
    ktra("cau_hinh_do mang bảng (đổi bảng = khoá đo khác)",
         b == (("CANON", 15.0),) and at.cau_hinh_do(dict(at.DEFAULTS, hl_da_tron_theo_may={}))[-1] == (),
         str(b))
    ca = {("Canon", "Canon EOS R"): 15.0, ("Canon", "Canon PowerShot S40"): 15.0,
          ("SONY", "ILCE-7M4"): 0.0, ("NIKON CORPORATION", "NIKON Z 6_2"): 0.0,
          (None, None): 0.0, ("FUJIFILM", "X-T5"): 0.0}
    sai = {k: at.tron_theo_may({"make": k[0], "model": k[1]}, b) for k in ca
           if at.tron_theo_may({"make": k[0], "model": k[1]}, b) != ca[k]}
    ktra("tron_theo_may: Canon 15, Sony / Nikon / Fuji / không EXIF 0", not sai, str(sai))


def muc2(kq):
    """2. Sony, Nikon, không EXIF: y hệt cách cũ"""
    for ten in ("sony", "nikon", "khong_exif"):
        lech = [g for g, moi, cu in kq[ten] if not bang_nhau(moi, cu)]
        ktra(f"{ten}: mặc định == công tắc cũ, toàn bộ kết quả measure, {len(GAIN)} mức sáng",
             not lech, f"lệch ở {lech}")
    lech = []
    for (g, moi, _cu), (g0, ev0, p0, rgb0) in zip(kq["sony"], CHUAN_SONY):
        if (abs(g - g0) > 1e-9 or abs(moi["metered_face_ev"] - ev0) > 2e-4 or abs(moi["face_p95"] - p0) > 2e-4
                or max(abs(a - b) for a, b in zip(moi["face_rgb"], rgb0)) > 2e-5):
            lech.append((g, round(moi["metered_face_ev"], 5), ev0))
    ktra("sony: khớp SỐ CHUẨN đo bằng code trước 14/10 (mặt EV, p95, màu da), mọi mức sáng",
         not lech, str(lech[:3]))
    co_mat = sum(1 for g, moi, cu in kq["sony"] if moi.get("metered_face_ev") is not None)
    ktra("ca Sony thật sự đo mặt (không phải đạt vì không thấy mặt)", co_mat == len(GAIN), str(co_mat))


def _buoc(kq_hang, i_kq):
    ev = [r[i_kq].get("metered_face_ev") for r in kq_hang]
    return [b - a for a, b in zip(ev, ev[1:])]


def muc3_4_5(kq):
    """3–5. Canon"""
    ca = kq["canon"]
    sang = [(r[2].get("face_debug") or [{}])[0].get("da_sang") or 0.0 for r in ca]
    i = next((k for k in range(1, len(sang)) if sang[k - 1] < at.DEFAULTS["hl_da_ti_le"] <= sang[k]), None)
    if i is None:
        ktra("ca Canon có chỗ da sáng vượt 30%", False, str(sang))
        return
    b_cu, b_moi = _buoc(ca, 2), _buoc(ca, 1)
    thuong = statistics.median(abs(x) for x in b_cu)
    ktra("3. cách cũ nhảy ≥ 3 lần bước thường ở chỗ da sáng vượt 30%",
         b_cu[i - 1] >= 3 * thuong, f"nhảy {b_cu[i - 1]:+.3f}, bước thường {thuong:.3f}, tại {GAIN[i]:+.3f} EV")
    ktra("4. Canon mặc định: bước ở đó ≤ ½ cú nhảy cũ và ≤ 2 lần bước thường",
         b_moi[i - 1] <= 0.5 * b_cu[i - 1] and b_moi[i - 1] <= 2 * thuong,
         f"{b_moi[i - 1]:+.3f} (cũ {b_cu[i - 1]:+.3f})")
    thuong_max = max(abs(x) for k, x in enumerate(b_cu) if k != i - 1)
    ktra("4. Canon mặc định: không sinh bước nhảy mới ở chỗ khác (≤ bước thường lớn nhất của cách cũ)",
         max(abs(x) for x in b_moi) <= thuong_max + 0.01,
         f"lớn nhất {max(abs(x) for x in b_moi):.3f}, cũ (trừ cú nhảy) {thuong_max:.3f}")
    ktra("4. Canon mặc định: số đo mặt không giảm khi ảnh sáng lên",
         all(x >= -0.005 for x in b_moi), str([round(x, 3) for x in b_moi]))
    dau, cuoi = bang_nhau(ca[0][1], ca[0][2]), bang_nhau(ca[-1][1], ca[-1][2])
    ktra("5. Canon hai đầu (ngoài dải chuyển): y hệt cách cũ", dau and cuoi,
         f"đầu {GAIN[0]:+.3f} {dau} · cuối {GAIN[-1]:+.3f} {cuoi}")
    giua = sum(1 for g, moi, cu in ca if not bang_nhau(moi, cu))
    ktra("Canon: bản sửa thật sự có tác dụng trong dải chuyển", giua > 0, f"{giua} mức sáng khác")


def muc6():
    """6. Canon, mặt có đốm bóng sáng"""
    g6 = [round(0.025 * k, 3) for k in range(-16, 13)]          # −0.40 .. +0.30: qua hết dải chuyển
    ca = quet("canon", "dom_sang", g6)
    b_cu, b_moi = _buoc(ca, 2), _buoc(ca, 1)
    ktra("6. đốm sáng: bản sửa không sinh bước lớn hơn bước lớn nhất của cách cũ (+0.01)",
         max(abs(x) for x in b_moi) <= max(abs(x) for x in b_cu) + 0.01,
         f"lớn nhất {max(abs(x) for x in b_moi):.3f} tại {g6[1 + b_moi.index(max(b_moi))]:+.3f}, "
         f"cũ lớn nhất {max(abs(x) for x in b_cu):.3f}")
    ktra("6. đốm sáng: hai đầu y hệt cách cũ", bang_nhau(ca[0][1], ca[0][2]) and bang_nhau(ca[-1][1], ca[-1][2]))


def main():
    goc_det = at.detect_faces
    at.detect_faces = mat_gia
    try:
        print(muc1.__doc__)
        muc1()
        kq = {ten: quet(ten) for ten in MAY}
        print(muc2.__doc__)
        muc2(kq)
        print(muc3_4_5.__doc__)
        muc3_4_5(kq)
        print(muc6.__doc__)
        muc6()
    except Exception as ex:                                      # noqa: BLE001
        import traceback
        traceback.print_exc()
        ktra("không sập", False, repr(ex))
    finally:
        at.detect_faces = goc_det
        shutil.rmtree(TAM, ignore_errors=True)
    print(f"\n{len(LOI)} LOI" if LOI else "\nTAT CA DAT")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
