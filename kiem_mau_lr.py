#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kiem_mau_lr.py — Ảnh Lightroom xuất ra ĐÃ ĐÚNG MÀU chưa. Đo điểm ảnh thật.

    python kiem_mau_lr.py "F:\\Day2"

VÌ SAO CẦN, KHI PLUGIN ĐÃ KIỂM CHỨNG RỒI
    Plugin đọc lại getDevelopSettings() từng ảnh và so với thứ AutoTone yêu cầu.
    Buổi PUBGday2: 741/741 "kiem chung DU". Nhưng ảnh ngoài trời VẪN xanh.

    Không mâu thuẫn: hai phép kiểm ở hai tầng khác nhau.

        plugin kiểm : con số đã vào đúng catalog chưa
        file này kiểm: con số đó có làm ra đúng màu không

    Tầng trên đạt 100% trong khi tầng dưới sai — vì màu ĐÍCH vốn đã sai. Đây là
    kiểu lỗi mà kiểm ở tầng thông số không bao giờ bắt được, dù có kiểm kỹ đến
    đâu. Phải đo điểm ảnh của ảnh Lightroom thật sự vẽ ra.

ĐO TRÊN CÁI GÌ
    Thư mục ảnh ĐÃ XUẤT từ Lightroom. Đó chính là thứ Lightroom vẽ ra với thông
    số mới — không phải bản dựng lại của ta, nên không có chỗ nào để lệch.

    KHÔNG đo trên RAW: preview trong RAW là bản máy ảnh render, không mang thông
    số Lightroom. Nhìn vào đó là nhìn thấy màu TRƯỚC khi áp.

ĐO BẰNG CHÍNH HÀM CỦA APP
    Gọi thẳng at.measure() rồi lấy face_rgb — cùng bộ nhận mặt, cùng bộ lọc da,
    cùng cách lấy trung bình mà lúc quyết định đã dùng. Tự viết một cách đo
    "gần giống" ở đây thì con số rút ra không so được với con số app dùng.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at   # noqa: E402

DUOI = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}

#[[ NGUONG DAT TRUOC KHI CHAY.
#
#   0.17 stop khong phai so tuy tien: ba nguong cua dot hieu chinh mau da dat
#   "trung vi |temp_adj| < 150K", ma 150K / wb_temp_gain = 0.166 stop. Dung lai
#   dung con so do de hai phep kiem noi cung mot ngon ngu.
#]]
NGUONG_STOP = 0.17


def _t(rgb) -> float:
    """log2(B/R) của một màu tuyến tính. Lớn = lạnh/xanh, nhỏ = ấm."""
    return at.wb_cast(np.asarray(rgb, dtype=np.float64))[0]


def _dich(cfg: dict, ngoai: bool) -> float:
    ref = cfg.get("skin_ref_rgb_ngoai") if ngoai else None
    ref = ref or cfg["skin_ref_rgb"]
    return _t(at.srgb_to_linear(np.asarray(ref, dtype=np.float64) / 255.0))


def do_thu_muc(d: Path, cfg: dict, so: int) -> list:
    ds = sorted(p for p in d.iterdir()
                if p.is_file() and p.suffix.lower() in DUOI)
    if so and len(ds) > so:
        #[[ Lay RAI DEU chu khong lay N tam dau: anh dau buoi thuong cung mot
        #   boi canh, do xong lai tuong ca buoi deu vay.
        #]]
        idx = np.linspace(0, len(ds) - 1, so).astype(int)
        ds = [ds[i] for i in sorted(set(idx.tolist()))]

    ra = []
    for i, p in enumerate(ds, 1):
        r = at.measure(p, cfg["preview_px"], cfg["meter"], wb_needs_faces=True)
        ra.append({
            "ten": p.name,
            "ok": bool(r.get("ok")),
            "iso": r.get("iso"),
            "ngoai": at.ngoai_troi(r, cfg),
            "face_rgb": r.get("face_rgb"),
            "loi": r.get("error") or "",
        })
        if i % 50 == 0:
            print(f"    {i}/{len(ds)}")
    return ra


def bao_cao(ra: list, cfg: dict) -> int:
    doc_duoc = [x for x in ra if x["ok"]]
    co_da = [x for x in doc_duoc if x["face_rgb"]]
    print(f"\n  Trong {len(ra)} ảnh đã đo:")
    print(f"    đọc được            : {len(doc_duoc)}")
    print(f"    đo được màu da      : {len(co_da)}")
    if len(doc_duoc) < len(ra):
        for x in [y for y in ra if not y["ok"]][:3]:
            print(f"      KHÔNG ĐỌC ĐƯỢC {x['ten']}: {x['loi'][:60]}")
    if not co_da:
        print("\n  [!] Không đo được màu da ở ảnh nào — không kết luận được gì.")
        print("      Chọn thư mục có ảnh chụp người.")
        return 2

    loi = []
    for ngoai, ten_nhom in ((False, "TRONG NHÀ"), (True, "NGOÀI TRỜI")):
        nhom = [x for x in co_da if x["ngoai"] is ngoai]
        if not nhom:
            continue
        dich = _dich(cfg, ngoai)
        lech = np.array([_t(x["face_rgb"]) - dich for x in nhom])
        tv = float(np.median(lech))
        tv_abs = float(np.median(np.abs(lech)))
        trong_nguong = 100.0 * float((np.abs(lech) <= NGUONG_STOP).mean())
        print(f"\n  {ten_nhom}  ({len(nhom)} ảnh, ngưỡng ISO ≤ {cfg['iso_ngoai_troi']})")
        print(f"    màu da đích         : log2(B/R) {dich:+.3f}")
        print(f"    lệch trung vị       : {tv:+.3f} stop "
              f"({tv * cfg['wb_temp_gain']:+.0f}K)  "
              f"{'← LẠNH hơn đích' if tv > 0 else '← ấm hơn đích'}")
        print(f"    lệch tuyệt đối tv   : {tv_abs:.3f} stop "
              f"({tv_abs * cfg['wb_temp_gain']:.0f}K)")
        print(f"    trong ngưỡng ±{NGUONG_STOP} : {trong_nguong:.0f}%")
        if tv_abs > NGUONG_STOP:
            loi.append(f"{ten_nhom}: lệch trung vị {tv_abs:.3f} stop "
                       f"> ngưỡng {NGUONG_STOP}")
        #[[ Neu ca nhom lech CUNG MOT CHIEU thi do la mau dich sai, khong phai
        #   vai tam ca biet. Phan biet duoc hai chuyen nay moi biet nen sua cai
        #   gi: doi mau dich, hay di sua tay may tam.
        #]]
        mot_chieu = 100.0 * float((lech > 0).mean())
        if len(nhom) >= 8 and (mot_chieu > 85 or mot_chieu < 15):
            print(f"    [!] {mot_chieu:.0f}% lệch cùng một chiều — đây là MÀU ĐÍCH "
                  f"sai,\n        không phải vài tấm cá biệt.")
        xau = sorted(nhom, key=lambda x: -abs(_t(x["face_rgb"]) - dich))[:5]
        if abs(tv_abs) > NGUONG_STOP:
            print("    lệch nhiều nhất:")
            for x in xau:
                print(f"      {x['ten']:26s} ISO {str(x['iso']):>5s}  "
                      f"{_t(x['face_rgb']) - dich:+.3f} stop")

    print()
    if loi:
        for m in loi:
            print("  [!]", m)
        print("CHƯA ĐẠT — ảnh trong Lightroom chưa đúng màu đích.")
        return 1
    print("ĐẠT — màu ảnh Lightroom xuất ra khớp màu đích.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Do mau anh Lightroom da xuat, so voi mau dich cua AutoTone.")
    ap.add_argument("thu_muc")
    ap.add_argument("--so", type=int, default=200,
                    help="do toi da bao nhieu anh (lay rai deu). 0 = do het")
    a = ap.parse_args(argv)

    d = Path(a.thu_muc).expanduser()
    if not d.is_dir():
        print(f"  [!] Không thấy thư mục {d}")
        return 2
    cfg = dict(at.DEFAULTS)
    print(f"  Đang đo ảnh trong {d} ...")
    ra = do_thu_muc(d, cfg, a.so)
    if not ra:
        print("  [!] Thư mục không có ảnh nào đọc được.")
        return 2
    return bao_cao(ra, cfg)


if __name__ == "__main__":
    sys.exit(main())
