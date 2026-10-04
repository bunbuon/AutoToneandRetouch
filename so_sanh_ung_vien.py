#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""so_sanh_ung_vien.py — Bảng ảnh trước/sau cho HAI ứng viên còn lại sau cổng 3/10.

    python so_sanh_ung_vien.py
    python so_sanh_ung_vien.py --anh TrainTool=D:\\copy\\TrainTool

Ra: Claude outputs\\do\\so_sanh_ung_vien.pdf

HAI ỨNG VIÊN (xem CLAUDE.md, mục "Năm phần học từ 2 bản quay")
    M3a  khung_sang_pct 12 + khung_sang_tran_da 210: khung cháy >= 12% thì
         trần sáng của da hạ từ 232 xuống 210. 2609 qua cả hai cổng; TrainTool
         trượt cổng B sát nút (12/426 ảnh đã duyệt bị dời > 0.30 EV).
    M2b  wb_tint_theo_may {"NIKON": -5}: ảnh Nikon giảm Tint 5. TrainTool
         57 sát / 0 xa; 2609 user không sửa Tint tấm Nikon nào nên cổng
         không đo được gì.

    Cổng không quyết được thì người dùng NHÌN TẬN MẮT rồi quyết — giống lần
    duyệt Nikon AF ngày 29/9 (gu/2609/so_sanh_nikon_2609.pdf).

MỖI CẶP ẢNH: TRÁI = con số ANH ĐÃ CHỌN, PHẢI = TOOL MỚI
    So với chính lựa chọn của người dùng chứ không so với tool hiện tại: ở
    2609 tool hiện tại đã khác lần đẩy 27/9 (code đo đã sửa từ đó), nên "ảnh
    đã duyệt" phải hiểu là đã duyệt CON SỐ LÚC ĐÓ.

MÔ PHỎNG — KHÔNG PHẢI LIGHTROOM
    Ảnh lấy từ JPEG xem trước trong file RAW (thu_gu.preview — đúng hàm sản
    phẩm), rồi:
      Exposure: nhân 2^EV trong không gian tuyến tính, có vai mềm ở vùng
                sáng cho đỡ cháy gắt hơn Lightroom.
      Tint:     kênh xanh lá x 2^(-dTint / wb_tint_gain) — đúng thang tool đang
                dùng để quy Tint ra stop (30 Tint = 1 stop xanh lá so với đỏ+lam).
    Hai bên dùng CÙNG một phép biến đổi, chỉ khác đúng con số đang so, nên độ
    CHÊNH giữa hai bên là thật; màu tuyệt đối thì là màu của máy, không phải
    màu preset trong Lightroom.

CHỈ ĐỌC ảnh. Không ghi gì vào thư mục buổi, không đụng catalog.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import autotone as at          # noqa: E402
import kiem_2ban_quay as k2    # noqa: E402
import thu_gu as tg            # noqa: E402

M3A = {"khung_sang_pct": 12.0, "khung_sang_tran_da": 210.0}
M2B = {"wb_tint_theo_may": {"NIKON": -5}}
TRAN_KEO_SANG = {"TrainTool": 3.0}       # do nguoc tu lan day — xem kiem_2ban_quay

W, H = 1754, 1240                        # A4 ngang, 150 dpi
NEN, CHU, PHU, VANG = (24, 24, 27), (238, 238, 242), (165, 165, 175), (255, 205, 120)
XANH, DO = (120, 220, 150), (255, 130, 120)


def _font(cao: int):
    for p in ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/Library/Fonts/Arial Unicode.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"):
        try:
            return ImageFont.truetype(p, cao)
        except OSError:
            continue
    return ImageFont.load_default()


F_TO, F_VUA, F_NHO = _font(34), _font(22), _font(18)


# ------------------------------------------------------------------ chon anh
def chon_anh(goc_do: Path, jobs: Path) -> list:
    out = []
    for b in ("TrainTool", "2609"):
        d = goc_do / b
        goi = k2.nap_do(d)
        if not goi:
            continue
        pr, dap = k2.nap_preset(d), k2.nap_dap_an(d, b, jobs)
        c0 = k2.cfg_goc(TRAN_KEO_SANG.get(b, 1.0))
        kq0 = k2.chay(goi, pr, c0)
        kqa = k2.chay(goi, pr, dict(c0, **M3A))
        kqb = k2.chay(goi, pr, dict(c0, **M2B))
        tap = k2.tap_kiem(b, dap, kq0)
        duyet, sua = set(tap["exp"]["duyet"]), dict(tap["exp"]["sua"])
        tint_sua = dict(tap["tint"]["sua"])

        def rec(k, nhom, loai, kq1):
            r0, r1, a = kq0[k], kq1[k], dap[k]
            return dict(buoi=b, ten=k, path=r0["path"], nhom=nhom, loai=loai,
                        model=r0["model"],
                        exp_chon=a["user"]["Exposure2012"], tint_chon=a["user"]["Tint"],
                        exp_nay=float(r0["new_exposure"]), tint_nay=int(r0["new_tint"]),
                        exp_moi=float(r1["new_exposure"]), tint_moi=int(r1["new_tint"]),
                        exp_day=a["tool"]["Exposure2012"],
                        sat=float(r0["sat_frac"]) * 100,
                        p95=float(r0.get("face_p95") or 0) * 255)
        thu = lambda k: dap[k]["thu_tu"]   # noqa: E731
        for k in sorted(duyet, key=thu):
            if abs(kqa[k]["new_exposure"] - kq0[k]["new_exposure"]) > 0.30:
                out.append(rec(k, "M3a", "duyet_bi_doi", kqa))
        gan, xa = [], []
        for k, u in sua.items():
            e0, e1 = kq0[k]["new_exposure"], kqa[k]["new_exposure"]
            if abs(e1 - e0) >= 0.005:
                (gan if abs(e1 - u) < abs(e0 - u) else xa).append(
                    (abs(e0 - u) - abs(e1 - u), k))
        so_gan, so_xa = (6, 2) if b == "2609" else (4, 4)
        out += [rec(k, "M3a", "sua_gan", kqa) for _, k in sorted(gan, reverse=True)[:so_gan]]
        out += [rec(k, "M3a", "sua_xa", kqa) for _, k in sorted(xa)[:so_xa]]
        nik = sorted([k for k in kq0 if "NIKON" in str(kq0[k]["model"]).upper()
                      and k in dap and dap[k]["rating"] != 1
                      and kqb[k]["new_tint"] != kq0[k]["new_tint"]], key=thu)
        deu = lambda ds, n: [ds[int(i)] for i in np.linspace(0, len(ds) - 1, n)] if ds else []  # noqa: E731
        if b == "2609":
            out += [rec(k, "M2b", "nikon_khong_sua", kqb)
                    for k in deu([k for k in nik if k not in tint_sua], 10)]
        else:
            out += [rec(k, "M2b", "nikon_da_giam", kqb)
                    for k in deu([k for k in nik if k in tint_sua], 4)]
            out += [rec(k, "M2b", "nikon_giu", kqb)
                    for k in deu([k for k in nik if k not in tint_sua
                                  and k in set(tap["tint"]["duyet"])], 4)]
    return out


# ------------------------------------------------------------------ mo phong
def _vai(x: np.ndarray) -> np.ndarray:
    """Vai mem tren 0.75 tuyen tinh — de 2^EV khong cat gat hon Lightroom."""
    k = 0.75
    y = x.copy()
    m = x > k
    y[m] = k + (1 - k) * (1 - np.exp(-(x[m] - k) / (1 - k)))
    return y


def mo_phong(im: Image.Image, ev: float, d_tint: float) -> Image.Image:
    a = at.srgb_to_linear(np.asarray(im, dtype=np.float64) / 255.0)
    a = a * (2.0 ** ev)
    if d_tint:
        a[..., 1] *= 2.0 ** (-d_tint / float(at.DEFAULTS["wb_tint_gain"]))
    a = np.clip(_vai(np.clip(a, 0, None)), 0, 1)
    s = np.where(a <= 0.0031308, a * 12.92, 1.055 * np.power(a, 1 / 2.4) - 0.055)
    return Image.fromarray((np.clip(s, 0, 1) * 255 + 0.5).astype(np.uint8))


# ------------------------------------------------------------------ ve
MUC = {
    ("M3a", "duyet_bi_doi"): "Ảnh anh ĐÃ DUYỆT nhưng tool mới đổi Exposure quá 0,30 EV",
    ("M3a", "sua_gan"): "Ảnh anh ĐÃ SỬA — tool mới tiến lại gần con số anh chọn",
    ("M3a", "sua_xa"): "Ảnh anh ĐÃ SỬA — tool mới ra xa con số anh chọn",
    ("M2b", "nikon_khong_sua"): "Nikon buổi 2609 — anh KHÔNG sửa Tint tấm nào",
    ("M2b", "nikon_da_giam"): "Nikon TrainTool — anh ĐÃ giảm Tint (để đối chiếu)",
    ("M2b", "nikon_giu"): "Nikon TrainTool — anh GIỮ Tint",
}


def _tieu_de(d, y, chu, font=None, mau=CHU):
    d.text((40, y), chu, fill=mau, font=font or F_TO)


def trang_bia(muc_luc: list) -> Image.Image:
    im = Image.new("RGB", (W, H), NEN)
    d = ImageDraw.Draw(im)
    y = 60
    _tieu_de(d, y, "So sánh trước/sau — 2 ứng viên còn lại sau cổng 3/10")
    y += 80
    for i, t in enumerate(muc_luc):
        d.text((1180, 140 + 34 * i), t, fill=PHU, font=F_NHO)
    dong = [
        ("Cách xem", VANG),
        ("Mỗi cặp: TRÁI = con số ANH ĐÃ CHỌN trong Lightroom, PHẢI = TOOL MỚI nếu bật ứng viên.", CHU),
        ("Ghi chú nhỏ dưới mỗi cặp: tool hiện tại cho bao nhiêu, khung cháy bao nhiêu %, da sáng tới đâu.", CHU),
        ("Đây là MÔ PHỎNG trên ảnh xem trước của máy, không phải Lightroom: độ CHÊNH giữa hai bên", PHU),
        ("là thật, còn màu/độ tương phản tuyệt đối là của máy ảnh, không phải preset SAY.", PHU),
        ("", CHU),
        ("Ứng viên 1 — hạ trần sáng của da khi khung cháy (M3a)", VANG),
        ("Khung có từ 12% điểm ảnh cháy trở lên thì da mặt không được đẩy sáng quá mức 210/255", CHU),
        ("(bình thường là 232). Cổng: 2609 ĐẠT cả hai (sát 17 / xa 2, dời 0,4% ảnh đã duyệt);", CHU),
        ("TrainTool trượt sát nút (sát 43 / xa 22, dời 2,8% ảnh đã duyệt — ngưỡng 2%).", CHU),
        ("→ Câu cần anh trả lời: các tấm ĐÃ DUYỆT bị đổi (phần 1A) — bản phải có chấp nhận được không?", XANH),
        ("", CHU),
        ("Ứng viên 2 — giảm Tint 5 cho mọi ảnh Nikon (M2b)", VANG),
        ("TrainTool: 57 tấm sát hơn, 0 tấm xa hơn. 2609: anh không sửa Tint tấm Nikon nào (137 tấm),", CHU),
        ("nên cổng không nói được gì — phần 2A là 10 tấm Nikon 2609 trải đều buổi.", CHU),
        ("→ Câu cần anh trả lời: ở 2609, bản phải (bớt tím) có đẹp hơn / ngang / tệ hơn bản trái?", XANH),
        ("", CHU),
        ("Anh chỉ cần nhắn kiểu: \"1A ổn hết\", \"1A tấm 5, 7 tệ hơn\", \"2A bên phải đẹp hơn\".", VANG),
    ]
    for t, mau in dong:
        d.text((60, y), t, fill=mau, font=F_VUA)
        y += 40
    return im


def ve_cap(im_trai, im_phai, o: dict, so: int, khung_w: int, khung_h: int) -> Image.Image:
    for x in (im_trai, im_phai):
        x.thumbnail(((khung_w - 30) // 2, khung_h - 120))
    w1, h1 = im_trai.size
    o_im = Image.new("RGB", (khung_w, khung_h), NEN)
    d = ImageDraw.Draw(o_im)
    x0 = (khung_w - 2 * w1 - 20) // 2
    o_im.paste(im_trai, (x0, 44))
    o_im.paste(im_phai, (x0 + w1 + 20, 44))
    ten = Path(str(o["path"]).replace("\\", "/")).name
    d.text((x0, 8), f"{so}. {ten}  ·  {o['buoi']}  ·  {o['model']}", fill=CHU, font=F_VUA)
    if o["nhom"] == "M3a":
        trai = f"Anh chọn: Exposure {o['exp_chon']:+.2f}"
        phai = f"Tool mới: Exposure {o['exp_moi']:+.2f}"
        ghi = (f"tool hiện tại {o['exp_nay']:+.2f}   ·   khung cháy {o['sat']:.1f}%   ·   "
               f"da sáng (p95) {o['p95']:.0f}/255 → trần {'210' if o['sat'] >= 12 else '232'}")
    else:
        trai = f"Anh chọn: Tint {o['tint_chon']:+.0f}"
        phai = f"Tool mới: Tint {o['tint_moi']:+d}"
        ghi = f"tool hiện tại Tint {o['tint_nay']:+d}   ·   Exposure hai bên như nhau ({o['exp_chon']:+.2f})"
    y = 44 + h1 + 8
    d.text((x0, y), trai, fill=VANG, font=F_VUA)
    d.text((x0 + w1 + 20, y), phai, fill=XANH, font=F_VUA)
    d.text((x0, y + 32), ghi, fill=PHU, font=F_NHO)
    return o_im


def _ma(ds: list) -> dict:
    """(nhom, loai) -> "1A", "2C"... theo thu tu xuat hien."""
    ma, dem = {}, {}
    for o in ds:
        key = (o["nhom"], o["loai"])
        if key not in ma:
            n = {"M3a": "1", "M2b": "2"}[o["nhom"]]
            dem[n] = dem.get(n, 0) + 1
            ma[key] = n + "ABCDEF"[dem[n] - 1]
    return ma


def dung_pdf(ds: list, anh_dir: dict, dest: Path) -> int:
    ma = _ma(ds)
    muc_luc = ["Mục lục"]
    for key, m in ma.items():
        n_tt = sum(1 for o in ds if (o["nhom"], o["loai"]) == key and o["buoi"] == "TrainTool")
        n_26 = sum(1 for o in ds if (o["nhom"], o["loai"]) == key and o["buoi"] == "2609")
        muc_luc.append(f"{m}: {n_tt + n_26} tấm (TrainTool {n_tt}, 2609 {n_26})")
    trang = [trang_bia(muc_luc)]
    nhom_cu = None
    hang = []                     # cac cap cua trang dang dung
    so = 0

    def xong_trang(tieu):
        if not hang:
            return
        im = Image.new("RGB", (W, H), NEN)
        d = ImageDraw.Draw(im)
        d.text((40, 20), tieu, fill=VANG, font=F_VUA)
        y = 70
        for c in hang:
            im.paste(c, (0, y))
            y += c.size[1]
        trang.append(im)
        hang.clear()

    tieu = ""
    for o in ds:
        key = (o["nhom"], o["loai"])
        if key != nhom_cu:
            xong_trang(tieu)
            tieu = f"{ma[key]}. {MUC.get(key, o['loai'])}"
            nhom_cu = key
        p = anh_dir.get(o["buoi"], {}).get(o["ten"])
        if p is None or not Path(p).is_file():
            print(f"[!] thieu file {o['path']} — bo qua", file=sys.stderr)
            continue
        im = tg.preview(Path(p), 1100)
        if im is None:
            print(f"[!] khong doc duoc preview {p}", file=sys.stderr)
            continue
        so += 1
        if o["nhom"] == "M3a":
            trai = mo_phong(im, o["exp_chon"], 0.0)
            phai = mo_phong(im, o["exp_moi"], 0.0)
        else:
            trai = mo_phong(im, o["exp_chon"], 0.0)
            phai = mo_phong(im, o["exp_chon"], o["tint_moi"] - o["tint_chon"])
        hang.append(ve_cap(trai, phai, o, so, W, (H - 80) // 2))
        if len(hang) == 2:
            xong_trang(tieu)
    xong_trang(tieu)
    dest.parent.mkdir(parents=True, exist_ok=True)
    trang[0].save(dest, "PDF", resolution=150.0, save_all=True, append_images=trang[1:])
    return so


def main(argv=None) -> int:
    for _l in (sys.stdout, sys.stderr):
        try:
            _l.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description="Bang anh truoc/sau cho 2 ung vien.")
    ap.add_argument("--do", type=Path, default=HERE / "Claude outputs" / "do")
    ap.add_argument("--jobs", type=Path, default=at.LR_JOB_DIR)
    ap.add_argument("--anh", action="append", default=[],
                    help="Thu muc RAW thay cho duong dan trong so do, vd TrainTool=D:\\copy")
    ap.add_argument("--ra", type=Path, default=None)
    a = ap.parse_args(argv)
    doi = dict(x.split("=", 1) for x in a.anh)
    #[[ Xep theo MUC truoc, buoi sau — trang bia goi "1A", "2A" theo thu tu
    #   nay; de theo buoi thi 1A bi xe lam hai doan o hai dau tep. ]]
    thu_tu = list(MUC)
    ds = sorted(chon_anh(a.do, a.jobs),
                key=lambda o: (thu_tu.index((o["nhom"], o["loai"])),
                               o["buoi"] != "TrainTool"))
    anh_dir: dict = {}
    for o in ds:
        goc = doi.get(o["buoi"])
        ten_f = Path(str(o["path"]).replace("\\", "/")).name
        p = Path(goc) / ten_f if goc else Path(o["path"])
        anh_dir.setdefault(o["buoi"], {})[o["ten"]] = p
    dest = a.ra or (a.do / "so_sanh_ung_vien.pdf")
    n = dung_pdf(ds, anh_dir, dest)
    print(f"{n} cap anh -> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
