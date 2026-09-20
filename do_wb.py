#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""do_wb.py — Vì sao phần cân WB kéo gần như một chiều.

    python do_wb.py "G:\\PUBGDay1" --so 400

ĐÂY LÀ CÔNG CỤ ĐO, KHÔNG ĐỔI THÔNG SỐ ẢNH NÀO.

CÂU HỎI NÓ TRẢ LỜI
    Buổi PUBGDay1: 95% ảnh bị làm lạnh, 34% bị ghim đúng ở mức lạnh tối đa
    (4850K = 5250 - wb_temp_max 400), KHÔNG ảnh nào giữ nguyên. Và mức ghim đó
    trải đều khắp mọi độ sáng môi trường — 31% ở EV 7-8.5, 33% ở EV 11-13 — nên
    KHÔNG phải chuyện trong nhà/ngoài trời.

    Còn lại đúng hai khả năng, và chúng đòi hai cách sửa khác hẳn nhau:

      A. MÀU DA ĐÍCH ĐẶT SAI (skin_ref_rgb = 244,212,202 — khá nhạt và hồng).
         Da thật dưới đèn sự kiện ấm hơn hẳn màu đó, nên MỌI ảnh đều bị đo là
         "quá ấm" và bị kéo lạnh. Dấu hiệu: skin_temp_ev lệch hẳn khỏi 0, cả
         đám nằm về một phía.
         -> sửa bằng cách đổi skin_ref_rgb cho đúng da người Việt.

      B. HỆ SỐ KHUẾCH ĐẠI QUÁ MẠNH (wb_temp_gain 900, skin_gain 0.6).
         Da đo được thực ra khá sát màu đích, nhưng một lệch nhỏ bị nhân lên
         thành hàng trăm Kelvin. Dấu hiệu: skin_temp_ev quanh quẩn số 0 nhưng
         temp_adj vẫn chạm trần.
         -> sửa bằng cách hạ hệ số, hoặc thêm vùng chết cho WB.

    Đổi nhầm cái thì hoặc là vẫn xanh, hoặc là hết xanh mà sang ám vàng. Nên
    phải đo trước.

CÁCH ĐO
    Chạy ĐÚNG đường app chạy: measure() -> plan() (gồm tách cảnh, nạp thông số
    catalog, decide, compute_values). Không dựng lại một mảnh logic nào.
"""
from __future__ import annotations

import argparse
import csv
import ntpath
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at   # noqa: E402


def doc_ban_xuat(p: Path | None) -> dict:
    """Bản xuất thật từ Lightroom nếu có — để chạy đúng như buổi thật."""
    if p and Path(p).is_file():
        return at.read_catalog_export(Path(p))
    return {}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Do phan can WB.")
    ap.add_argument("folder", type=Path)
    ap.add_argument("--so", type=int, default=400)
    ap.add_argument("--ban-xuat", type=Path, default=None, dest="ban_xuat",
                    help="File export_*.tsv tu Lightroom (mac dinh: ban moi nhat)")
    ap.add_argument("--ra", type=Path, default=None)
    a = ap.parse_args(argv)

    d = a.folder
    if not d.is_dir():
        print(f"  [!] Không thấy thư mục {d}")
        return 2
    ra = a.ra or d

    ds = sorted(p for p in d.iterdir()
                if p.is_file() and p.suffix.lower() in at.RAW_EXTS)
    if a.so and len(ds) > a.so:
        idx = np.linspace(0, len(ds) - 1, a.so).astype(int)
        ds = [ds[i] for i in idx]
    if not ds:
        print(f"  [!] {d} không có RAW nào")
        return 2

    xuat_p = a.ban_xuat or at.latest_catalog_export()
    xuat = doc_ban_xuat(xuat_p)
    print(f"  Bản xuất: {xuat_p if xuat else 'KHÔNG có — sẽ chạy chế độ sidecar'}"
          f" ({len(xuat)} dòng)")

    cfg = dict(at.DEFAULTS)
    if xuat:
        cfg["source"] = "catalog"
    #[[ TAT "bo qua anh nguoi sua tay" cho bai do nay.
    #
    #   plan() RUT HAN nhung anh do ra khoi danh sach (items[:] = ...), nen bai
    #   do se ket thuc voi 0 anh va bao "khong anh nao do duoc mau da" — mot ket
    #   luan sai hoan toan. Da mac dung bay nay mot lan.
    #
    #   Voi buoi da tung chay tool, gan nhu MOI anh deu bi danh dau nhu vay, vi
    #   gia tri trong catalog bay gio la gia tri tool ghi lan truoc chu khong con
    #   la preset goc. Bai do can nhin ca buoi, khong phai phan con sot.
    #]]
    cfg["bo_qua_nguoi_sua"] = False

    print(f"  Đang đo {len(ds)} ảnh ...")
    items = []
    for i, p in enumerate(ds, 1):
        r = at.measure(p, cfg["preview_px"], cfg["meter"],
                       wb_needs_faces=(cfg["wb"] == "skin"))
        if not r["ok"]:
            continue
        r["dt_obj"] = datetime.fromisoformat(r["dt"])
        #[[ plan() o che do sidecar doc r["sidecar"] VO DIEU KIEN — thieu la
        #   KeyError giua chung. Buoi that luon co ban xuat nen khong dinh, nhung
        #   bai do chay tren thu muc bat ky thi phai chuan bi san.
        #]]
        if not xuat:
            sc = at.sidecar_for(p)
            if sc is None:
                continue
            r["sidecar"] = str(sc)
        items.append(r)
        if i % 50 == 0:
            print(f"    {i}/{len(ds)}")

    if not items:
        print("  [!] Không đo được ảnh nào dùng được.")
        if not xuat:
            print("      Không có bản xuất từ Lightroom, và cũng không ảnh nào có")
            print("      sẵn file .xmp — nên không có thông số preset gốc để tính.")
            print("      Trong Lightroom chạy “AutoTone: xuất thông số” rồi chạy lại,")
            print("      hoặc chỉ rõ bằng  --ban-xuat <đường dẫn export_*.tsv>")
        return 1

    # Chạy đúng đường app chạy
    at.plan(items, cfg, d, xuat)

    # ── Kết quả ─────────────────────────────────────────────────────────────
    ste = np.array([r["skin_temp_ev"] for r in items
                    if r.get("skin_temp_ev") is not None])
    adj = np.array([r["temp_adj"] for r in items if r.get("temp_adj") is not None])
    mat = np.array([r.get("faces_n") or 0 for r in items])

    print(f"\n  Đo xong {len(items)} ảnh · {int((mat > 0).sum())} ảnh có thấy mặt\n")

    tran = float(cfg["wb_temp_max"])
    if len(adj):
        cham = int((np.abs(adj) >= tran - 0.5).sum())
        lanh = int((adj < 0).sum())
        giu = int((np.abs(adj) < 1).sum())
        print("  temp_adj (số Kelvin app cộng vào, âm = lạnh đi):")
        print(f"    trung vị {np.median(adj):+7.0f}K · từ {adj.min():+.0f} "
              f"đến {adj.max():+.0f}")
        print(f"    kéo LẠNH: {lanh}/{len(adj)} ({100 * lanh / len(adj):.0f}%)"
              f" · chạm trần ±{tran:.0f}K: {cham} ({100 * cham / len(adj):.0f}%)"
              f" · gần như giữ nguyên: {giu}")

    if not len(ste):
        print("\n  [!] Không ảnh nào đo được màu da (skin_temp_ev rỗng).")
        print("      Nghĩa là phần cân WB đang chạy bằng nhánh 'không thấy mặt' —")
        print("      cộng một lượng CỐ ĐỊNH wb_skin_temp_bias cho mọi ảnh.")
        print("      Đó tự nó đã giải thích được vì sao mọi ảnh lệch cùng một chiều.")
        return 0

    print(f"\n  skin_temp_ev (da đo được LỆCH bao nhiêu stop so với màu da đích;")
    print(f"                âm = da ẤM hơn đích, nên app kéo lạnh lại):")
    print(f"    trung vị {np.median(ste):+.3f} · p25 {np.percentile(ste, 25):+.3f}"
          f" · p75 {np.percentile(ste, 75):+.3f}")
    print(f"    từ {ste.min():+.3f} đến {ste.max():+.3f}")
    am = int((ste < 0).sum())
    print(f"    lệch về phía DA ẤM HƠN ĐÍCH: {am}/{len(ste)} "
          f"({100 * am / len(ste):.0f}%)")

    #[[ PHAN XU: A hay B. Nguong dat TRUOC khi nhin so.
    #
    #   Neu chi mot lech DIEN HINH (trung vi) da du sinh ra qua nua muc tran, thi
    #   cai sai nam o CHO DAT MAU DICH — mau da that cua ca buoi cach mau dich
    #   mot khoang lon va on dinh, khong phai nhieu ngau nhien.
    #]]
    g = float(cfg["skin_gain"]) * float(cfg["wb_temp_gain"])
    tu_trung_vi = abs(float(np.median(ste)) * g)
    print(f"\n  Một lệch ĐIỂN HÌNH sinh ra {tu_trung_vi:.0f}K "
          f"(= |trung vị| × skin_gain {cfg['skin_gain']} × wb_temp_gain "
          f"{cfg['wb_temp_gain']:.0f})")
    print(f"  Trần đang đặt: {tran:.0f}K")
    if tu_trung_vi >= 0.5 * tran and abs(np.median(ste)) > 0.05:
        print("\n  -> NGHIÊNG VỀ (A): MÀU DA ĐÍCH ĐẶT SAI." )
        print("     Cả buổi lệch cùng một phía và lệch lớn, tức màu da đích không")
        print("     phải màu da thật của khách dưới ánh sáng buổi này. Hạ hệ số chỉ")
        print("     làm mọi ảnh sai ÍT hơn chứ vẫn sai cùng một chiều.")
        med_rgb = np.median(np.asarray([r["face_rgb"] for r in items
                                        if r.get("face_rgb")],
                                       dtype=np.float64), axis=0)
        print(f"     Màu da đo được (trung vị, tuyến tính): "
              f"{np.round(med_rgb, 4).tolist()}")
        print(f"     Màu da đích đang đặt (skin_ref_rgb): {cfg['skin_ref_rgb']}")
    elif tu_trung_vi < 0.5 * tran:
        print("\n  -> NGHIÊNG VỀ (B): HỆ SỐ KHUẾCH ĐẠI QUÁ MẠNH.")
        print("     Lệch điển hình nhỏ, nhưng vẫn nhiều ảnh chạm trần — tức đuôi")
        print("     phân bố bị nhân lên quá tay. Hạ wb_temp_gain / skin_gain, và")
        print("     thêm vùng chết để lệch nhỏ không sinh ra chỉnh sửa.")
    else:
        print("\n  -> CHƯA NGÃ NGŨ: xem CSV rồi bàn tiếp.")

    p_csv = ra / "do_wb.csv"
    cot = ["ten", "ev_sang", "so_mat", "skin_temp_ev", "skin_tint_ev",
           "temp_adj", "tint_adj", "scene", "metered_ev", "notes"]
    with p_csv.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(cot)
        for r in items:
            w.writerow([ntpath.basename(r["path"])] +
                       [r.get(k) for k in cot[1:]])
    print(f"\n  {p_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
