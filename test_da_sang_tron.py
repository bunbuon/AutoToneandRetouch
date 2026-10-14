#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đo vùng da sáng THEO MÁY — Canon không đo vùng da sáng; Sony / Nikon giữ y hệt (14/10).

CHUYỆN ĐANG CANH
    Bộ CR3 Canon EOS R (G:\\TestThacCao\\test, nắng trưa, da trắng): cùng hai người, cùng
    1/500 f/4 ISO 250 mà Exposure −0.33 / +0.15 xen kẽ. Gốc: công tắc hl_da_ti_le 30% —
    ≥ 30% da quá 220/255 thì đo RIÊNG vùng sáng; đổi chế độ là đổi cả tập điểm đo (số đo
    mặt, p95 da, màu da cùng nhảy). kiem_raw_that v4 (14/10 07:26), số cặp liền nhau cùng
    thông số lệch > 0.30: công tắc cũ 4 · CHUYỂN DẦN (hl_da_tron_theo_may Canon 15) 2 ·
    tắt hẳn đo vùng sáng 0. Tiêu chí đặt trước cho chuyển dần là 0 → TRƯỢT, bảng {}.
    User chọn: Canon tắt hẳn (hl_da_ti_le_theo_may {"CANON": 0}).

    User: "Hãy đặt ra các case theo loại máy. Nếu sửa mà làm thay đổi hết những gì đã
    đạt được ở Sony và Nikon thì không được." → mỗi hãng một ca; Sony / Nikon / ảnh không
    EXIF phải ra Y HỆT cách cũ (so TOÀN BỘ kết quả measure, từng số) ở mọi mức sáng.

    Ảnh mặt GIẢ: nửa mặt dính nắng, nửa trong bóng (×0.5) — đúng dáng da làm công tắc cũ
    nhảy (đo thường lấy cả phần bóng, đo vùng sáng chỉ lấy phần nắng). Cùng điểm ảnh, chỉ
    khác hãng / máy trong EXIF. Tăng sáng từng 0.025 EV, đo bằng measure() THẬT
    (detect_faces giả trả đúng ô mặt — YuNet không nhận mặt vẽ).

Mục kiểm
    1. Bảng: chuyển dần TẮT ({}), Canon 0 trong hl_da_ti_le_theo_may, Sony / Nikon không
       có; so_theo_may khớp đúng hãng; cả hai bảng nằm trong cau_hinh_do (đổi bảng = đo
       lại, không nạp kết quả cũ)
    2. Sony, Nikon, không EXIF: mặc định == công tắc cũ, TỪNG SỐ, mọi mức sáng (cả khi bảng
       chuyển dần có Canon — bảng chỉ chạm đúng hãng của nó); Sony khớp
       SỐ CHUẨN đo bằng code trước 14/10 (commit 8f50502)
    3. Canon, cách cũ: có cú nhảy ở chỗ da sáng vượt 30% (≥ 3 lần bước thường) — chứng
       tỏ ca này chạm đúng bệnh
    4. Canon mặc định == đo với hl_da_ti_le 0 (toàn bộ kết quả, trừ da_sang chỉ để truy
       lỗi — vẫn phải ghi); không bước nào lớn hơn bước thường lớn nhất của cách cũ; số
       đo mặt không giảm khi ảnh sáng lên
       4b. bảng ghi đè đúng số: Canon 40 == hl_da_ti_le 40 (cả công tắc lẫn chuyển dần)
    5. Chuyển dần (mã còn giữ, bảng truyền TAY {"CANON": 15}): bước ở chỗ đó ≤ ½ cú nhảy
       cũ, không sinh bước mới, hai đầu y hệt cách cũ, ca đốm sáng không sinh bước mới

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


def mat_gia(im, score=0.5, **_kw):
    k = im.size[0] / W
    return [(MAT[0] * k, MAT[1] * k, MAT[2] * k, MAT[3] * k, 0.95, None)]


#  các cách đo đem so — mỗi cách là phần ghi đè lên DEFAULTS
CU = {"hl_da_tron_theo_may": {}, "hl_da_ti_le_theo_may": {}}            # công tắc cứng cũ
TRON = {"hl_da_tron_theo_may": {"CANON": 15.0}, "hl_da_ti_le_theo_may": {}}  # chuyển dần
TAT = {"hl_da_ti_le": 0.0, "hl_da_tron_theo_may": {}, "hl_da_ti_le_theo_may": {}}


def do(p: Path, ghi_de=None) -> dict:
    cfg = dict(at.DEFAULTS, canh_p365=False)
    cfg.update(ghi_de or {})
    r = at.measure(p, *at.cau_hinh_do(cfg))
    r.pop("path", None)
    return r


def bo_da_sang(r: dict) -> dict:
    """Bản sao bỏ face_debug[].da_sang (chỉ để truy lỗi, không đi vào phép đo)."""
    r = dict(r)
    if r.get("face_debug"):
        r["face_debug"] = [{k: v for k, v in f.items() if k != "da_sang"} for f in r["face_debug"]]
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


def quet(ten: str, kieu: str = "nua_nang", gain=None, cach=("moi", "cu")) -> list:
    """[(gain, {cách: kết quả})] cho một hãng. moi = DEFAULTS, cu / tron / tat xem trên."""
    bang = {"moi": None, "cu": CU, "tron": TRON, "tat": TAT}
    ra = []
    for g in gain or GAIN:
        p = anh(g, MAY[ten], TAM / f"{ten}_{kieu}_{g:+.3f}.jpg", kieu)
        ra.append((g, {c: do(p, bang[c]) for c in cach}))
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
    d = at.DEFAULTS
    ktra("chuyển dần TẮT ({}): trượt tiêu chí kiem_raw_that v4", d["hl_da_tron_theo_may"] == {},
         str(d["hl_da_tron_theo_may"]))
    ktra("hl_da_ti_le_theo_may chỉ Canon = 0 (Sony / Nikon không có trong bảng)",
         d["hl_da_ti_le_theo_may"] == {"CANON": 0.0}, str(d["hl_da_ti_le_theo_may"]))
    ch = at.cau_hinh_do(dict(d))
    ktra("cau_hinh_do mang cả hai bảng (đổi bảng = khoá đo khác)",
         ch[-2] == (("CANON", 0.0),) and ch[-3] == ()       # 15/10: cờ chu_the_chinh đứng cuối
         and at.cau_hinh_do(dict(d, hl_da_ti_le_theo_may={}))[-2] == ()
         and at.cau_hinh_do(dict(d, hl_da_tron_theo_may={"canon": 15}))[-3] == (("CANON", 15.0),),
         str(ch[-2:]))
    ca = {("Canon", "Canon EOS R"): 0.0, ("Canon", "Canon PowerShot S40"): 0.0,
          ("SONY", "ILCE-7M4"): 30.0, ("NIKON CORPORATION", "NIKON Z 6_2"): 30.0,
          (None, None): 30.0, ("FUJIFILM", "X-T5"): 30.0}
    sai = {k: at.so_theo_may({"make": k[0], "model": k[1]}, ch[-2], d["hl_da_ti_le"]) for k in ca
           if at.so_theo_may({"make": k[0], "model": k[1]}, ch[-2], d["hl_da_ti_le"]) != ca[k]}
    ktra("so_theo_may: Canon 0, Sony / Nikon / Fuji / không EXIF giữ 30", not sai, str(sai))
    sai = {k: at.tron_theo_may({"make": k[0], "model": k[1]}, (("CANON", 15.0),)) for k in ca
           if at.tron_theo_may({"make": k[0], "model": k[1]}, (("CANON", 15.0),)) != (15.0 if k[0] == "Canon" else 0.0)}
    ktra("tron_theo_may (bảng tay): Canon 15, máy khác 0", not sai, str(sai))


def muc2(kq):
    """2. Sony, Nikon, không EXIF: y hệt cách cũ"""
    for ten in ("sony", "nikon", "khong_exif"):
        lech = [g for g, r in kq[ten] if not bang_nhau(r["moi"], r["cu"])]
        ktra(f"{ten}: mặc định == công tắc cũ, toàn bộ kết quả measure, {len(GAIN)} mức sáng",
             not lech, f"lệch ở {lech}")
        lech = [g for g, r in kq[ten] if not bang_nhau(r["tron"], r["cu"])]
        ktra(f"{ten}: bảng chuyển dần {{'CANON': 15}} không chạm máy này (y hệt công tắc cũ)",
             not lech, f"lệch ở {lech}")
    lech = []
    for (g, r), (g0, ev0, p0, rgb0) in zip(kq["sony"], CHUAN_SONY):
        moi = r["moi"]
        if (abs(g - g0) > 1e-9 or abs(moi["metered_face_ev"] - ev0) > 2e-4 or abs(moi["face_p95"] - p0) > 2e-4
                or max(abs(a - b) for a, b in zip(moi["face_rgb"], rgb0)) > 2e-5):
            lech.append((g, round(moi["metered_face_ev"], 5), ev0))
    ktra("sony: khớp SỐ CHUẨN đo bằng code trước 14/10 (mặt EV, p95, màu da), mọi mức sáng",
         not lech, str(lech[:3]))
    co_mat = sum(1 for g, r in kq["sony"] if r["moi"].get("metered_face_ev") is not None)
    ktra("ca Sony thật sự đo mặt (không phải đạt vì không thấy mặt)", co_mat == len(GAIN), str(co_mat))


def _buoc(kq_hang, cach):
    ev = [r[cach].get("metered_face_ev") for g, r in kq_hang]
    return [b - a for a, b in zip(ev, ev[1:])]


def _cho_nhay(kq_hang):
    sang = [(r["cu"].get("face_debug") or [{}])[0].get("da_sang") or 0.0 for g, r in kq_hang]
    return next((k for k in range(1, len(sang)) if sang[k - 1] < at.DEFAULTS["hl_da_ti_le"] <= sang[k]), None), sang


def muc3_4(kq):
    """3–4. Canon theo mặc định"""
    ca = kq["canon"]
    i, sang = _cho_nhay(ca)
    if i is None:
        ktra("ca Canon có chỗ da sáng vượt 30%", False, str(sang))
        return
    b_cu, b_moi = _buoc(ca, "cu"), _buoc(ca, "moi")
    thuong = statistics.median(abs(x) for x in b_cu)
    ktra("3. cách cũ nhảy ≥ 3 lần bước thường ở chỗ da sáng vượt 30%",
         b_cu[i - 1] >= 3 * thuong, f"nhảy {b_cu[i - 1]:+.3f}, bước thường {thuong:.3f}, tại {GAIN[i]:+.3f} EV")
    lech = [g for g, r in ca if not bang_nhau(bo_da_sang(r["moi"]), bo_da_sang(r["tat"]))]
    ktra("4. Canon mặc định == đo với hl_da_ti_le 0, toàn bộ kết quả (trừ da_sang)", not lech,
         f"lệch ở {lech}")
    ghi = [((r["moi"].get("face_debug") or [{}])[0].get("da_sang")) for g, r in ca]
    ktra("4. Canon mặc định vẫn ghi da_sang (truy lỗi) và khớp số của cách cũ",
         all(x is not None for x in ghi) and ghi == sang, str(ghi[:4]))
    thuong_max = max(abs(x) for k, x in enumerate(b_cu) if k != i - 1)
    ktra("4. Canon mặc định: không bước nào lớn hơn bước thường lớn nhất của cách cũ (+0.01)",
         max(abs(x) for x in b_moi) <= thuong_max + 0.01,
         f"lớn nhất {max(abs(x) for x in b_moi):.3f}, cũ (trừ cú nhảy) {thuong_max:.3f}")
    ktra("4. Canon mặc định: số đo mặt không giảm khi ảnh sáng lên",
         all(x >= -0.005 for x in b_moi), str([round(x, 3) for x in b_moi]))
    khac = [g for g, r in ca if not bang_nhau(r["moi"], r["cu"])]
    bat = [g for (g, r), x in zip(ca, sang) if x >= at.DEFAULTS["hl_da_ti_le"]]
    ktra("4. Canon khác cách cũ ĐÚNG ở các mức công tắc cũ bật (da sáng ≥ 30%), dưới đó y hệt",
         khac == bat and len(bat) > 0, f"khác {len(khac)} mức, công tắc bật {len(bat)} mức")


def muc4b():
    """4b. Bảng ghi đè ĐÚNG số (không chỉ 0): Canon 40 == hl_da_ti_le 40 cho mọi máy"""
    #  mịn quanh chỗ da sáng đi qua 30–40% (−0.17 EV: 35% — công tắc 30 bật, 40 chưa)
    g4 = [-0.25, -0.19, -0.18, -0.175, -0.17, -0.165, -0.16, -0.15, 0.0, 0.1]
    for ten, them in (("công tắc", {}), ("chuyển dần", {"hl_da_tron_theo_may": {"CANON": 15.0}})):
        lech, bat = [], 0
        for g in g4:
            pth = anh(g, MAY["canon"], TAM / f"canon_40_{g:+.3f}.jpg")
            r1 = do(pth, dict({"hl_da_tron_theo_may": {}, "hl_da_ti_le_theo_may": {"canon": 40.0}}, **them))
            r2 = do(pth, dict({"hl_da_ti_le": 40.0, "hl_da_tron_theo_may": {}, "hl_da_ti_le_theo_may": {}}, **them))
            r3 = do(pth, CU)
            if not bang_nhau(r1, r2):
                lech.append(g)
            bat += not bang_nhau(r1, r3)
        ktra(f"4b. {ten}: Canon 40 trong bảng == hl_da_ti_le 40, {len(g4)} mức sáng (và khác ngưỡng 30 ở {bat} mức)",
             not lech and bat > 0, f"lệch ở {lech}")


def muc5(kq):
    """5. Chuyển dần (bảng truyền tay — mã còn giữ)"""
    ca = kq["canon"]
    i, sang = _cho_nhay(ca)
    if i is None:
        return
    b_cu, b_tron = _buoc(ca, "cu"), _buoc(ca, "tron")
    thuong = statistics.median(abs(x) for x in b_cu)
    ktra("5. chuyển dần: bước ở đó ≤ ½ cú nhảy cũ và ≤ 2 lần bước thường",
         b_tron[i - 1] <= 0.5 * b_cu[i - 1] and b_tron[i - 1] <= 2 * thuong,
         f"{b_tron[i - 1]:+.3f} (cũ {b_cu[i - 1]:+.3f})")
    thuong_max = max(abs(x) for k, x in enumerate(b_cu) if k != i - 1)
    ktra("5. chuyển dần: không sinh bước nhảy mới ở chỗ khác",
         max(abs(x) for x in b_tron) <= thuong_max + 0.01,
         f"lớn nhất {max(abs(x) for x in b_tron):.3f}, cũ (trừ cú nhảy) {thuong_max:.3f}")
    ktra("5. chuyển dần: số đo mặt không giảm khi ảnh sáng lên",
         all(x >= -0.005 for x in b_tron), str([round(x, 3) for x in b_tron]))
    dau, cuoi = bang_nhau(ca[0][1]["tron"], ca[0][1]["cu"]), bang_nhau(ca[-1][1]["tron"], ca[-1][1]["cu"])
    ktra("5. chuyển dần, hai đầu (ngoài dải chuyển): y hệt cách cũ", dau and cuoi,
         f"đầu {GAIN[0]:+.3f} {dau} · cuối {GAIN[-1]:+.3f} {cuoi}")
    giua = sum(1 for g, r in ca if not bang_nhau(r["tron"], r["cu"]))
    ktra("5. chuyển dần thật sự có tác dụng trong dải chuyển", giua > 0, f"{giua} mức sáng khác")
    g6 = [round(0.025 * k, 3) for k in range(-16, 13)]          # −0.40 .. +0.30: qua hết dải chuyển
    ds = quet("canon", "dom_sang", g6, cach=("cu", "tron"))
    b_cu, b_tron = _buoc(ds, "cu"), _buoc(ds, "tron")
    ktra("5. đốm sáng: chuyển dần không sinh bước lớn hơn bước lớn nhất của cách cũ (+0.01)",
         max(abs(x) for x in b_tron) <= max(abs(x) for x in b_cu) + 0.01,
         f"lớn nhất {max(abs(x) for x in b_tron):.3f}, cũ lớn nhất {max(abs(x) for x in b_cu):.3f}")
    ktra("5. đốm sáng: hai đầu y hệt cách cũ",
         bang_nhau(ds[0][1]["tron"], ds[0][1]["cu"]) and bang_nhau(ds[-1][1]["tron"], ds[-1][1]["cu"]))


def main():
    goc_det = at.detect_faces
    at.detect_faces = mat_gia
    try:
        print(muc1.__doc__)
        muc1()
        kq = {ten: quet(ten, cach=("moi", "cu", "tron")) for ten in ("sony", "nikon", "khong_exif")}
        kq["canon"] = quet("canon", cach=("moi", "cu", "tron", "tat"))
        print(muc2.__doc__)
        muc2(kq)
        print(muc3_4.__doc__)
        muc3_4(kq)
        print(muc4b.__doc__)
        muc4b()
        print(muc5.__doc__)
        muc5(kq)
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
