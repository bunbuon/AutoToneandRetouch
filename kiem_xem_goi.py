#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kiem_xem_goi.py — thử XEM TRƯỚC retouch thật trên gói đã đóng (Windows / macOS).

    python kiem_xem_goi.py <thư mục gói> <ảnh có mặt>

Chạy chính app trong gói với cờ --say-xem (đúng đường giao diện dùng), trên một
thư mục dữ liệu TẠM, mở ảnh, bật từng thanh = 100 rồi bật hết. ĐẠT khi:
    - nhận ra ít nhất một khuôn mặt bằng insightface, CÓ điểm mốc (lmk)
    - không bước nào bị bỏ qua vì nạp mô hình hỏng (bo_qua rỗng)
    - bật hết các thanh thì ảnh đổi rõ (> 0.5 % điểm ảnh)
    - xem_truoc_loi.log không có lỗi insightface / tải mô hình

#[[ VI SAO CO BAI NAY (6/10). kiem_goi.py chi kiem buoc retouch NAP DUOC, khong
#   chay that tren anh co mat. Ban macOS truoc nay dong goi THIEU insightface /
#   onnxruntime / mediapipe va mo hinh phan vung da ma van "GOI DAT" — tren may
#   that, moi tinh nang can diem moc mat se lang le khong doi gi. Ban Windows
#   cung tung "dat" kiem goi ma user mo len bao "khong thay khuon mat nao". ]]
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np


def _exe(goi: Path) -> Path:
    for ten in ("AutoTone.exe", "AutoTone"):
        if (goi / ten).is_file():
            return goi / ten
    raise SystemExit(f"Không thấy file chạy AutoTone trong {goi}")


def _de(b64: str):
    return cv2.imdecode(np.frombuffer(base64.b64decode(b64), np.uint8), cv2.IMREAD_COLOR)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 2:
        print(__doc__)
        return 2
    goi, anh = Path(argv[0]).resolve(), str(Path(argv[1]).resolve())
    exe = _exe(goi)
    cwd = goi / "_internal" if (goi / "_internal").is_dir() else goi
    du_lieu = Path(tempfile.mkdtemp(prefix="kiem_xem_goi_"))
    env = dict(os.environ, AUTOTONE_DATA=str(du_lieu), PYTHONIOENCODING="utf-8",
               PYTHONUTF8="1", PYTHONUNBUFFERED="1")
    loi: list = []
    try:
        r = subprocess.run([str(exe), "--say-keo"], cwd=str(cwd), env=env,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=600)
        ds = None
        for ln in r.stdout.splitlines()[::-1]:
            i = ln.find("[[")
            if i >= 0:
                try:
                    ds = json.loads(ln[i:])
                    break
                except ValueError:
                    pass
        if not ds:
            print("KHÔNG đọc được --say-keo:", r.stdout[-400:], r.stderr[-400:])
            return 1
        if isinstance(ds[0], list) and ds[0] and isinstance(ds[0][0], list):
            ds = [m for nhom in ds for m in nhom]
        thanh = [(m[0], m[1]) for m in ds]
        print(f"{len(thanh)} thanh:", [t for t, _ in thanh])

        p = subprocess.Popen([str(exe), "--say-xem"], cwd=str(cwd), env=env,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                             errors="replace", bufsize=1)

        def gui(**kw):
            p.stdin.write(json.dumps(kw) + "\n")
            p.stdin.flush()

        def doc(loai):
            for _ in range(2000):
                ln = p.stdout.readline()
                if not ln:
                    return None
                ln = ln.strip()
                if ln.startswith("{"):
                    d = json.loads(ln)
                    if d.get("loai") in (loai, "hong"):
                        return d
            return None

        gui(viec="khoi_dong", may="auto")
        s = doc("san_sang") or {}
        print("máy tính:", s.get("may"), s.get("loi", ""))
        gui(viec="mo_anh", fp=anh)
        d = doc("da_mo") or {}
        if d.get("loai") != "da_mo":
            print("MỞ ẢNH HỎNG:", d)
            return 1
        goc = _de(d["goc"])
        so_mat = int(d.get("so_mat") or 0)
        print(f"so_mat={so_mat}  ảnh {goc.shape[1]}x{goc.shape[0]}")
        if so_mat < 1:
            loi.append("không nhận ra khuôn mặt nào")

        ma = [0]

        def do(muc, nhan):
            ma[0] += 1
            gui(viec="tinh", ma=ma[0], fp=anh, muc=muc)
            k = doc("ket_qua")
            if not k or k.get("loai") != "ket_qua":
                print(f"  {nhan:<36} HỎNG: {k}")
                loi.append(f"{nhan}: tính hỏng")
                return 0.0
            out = _de(k["anh"])
            if out.shape != goc.shape:
                pt = 100.0          # đổi khung (kéo dài chân) = có đổi
            else:
                pt = 100.0 * float((np.abs(goc.astype(int) - out.astype(int)).sum(2) > 3).mean())
            bq = k.get("bo_qua") or []
            print(f"  {nhan:<36} đổi {pt:5.1f}%" + (f"   BỎ QUA: {bq}" if bq else ""))
            if bq:
                loi.append(f"{nhan}: bước bị bỏ qua {bq}")
            return pt

        for ten, nhan in thanh:
            do({k: (100.0 if k == ten else 0.0) for k, _ in thanh}, f"{nhan} [{ten}]")
        tat_ca = do({k: 100.0 for k, _ in thanh}, "TẤT CẢ = 100")
        if tat_ca <= 0.5:
            loi.append(f"bật hết các thanh mà ảnh chỉ đổi {tat_ca:.2f}%")
        gui(viec="thoat")
        try:
            p.wait(timeout=30)
        except subprocess.TimeoutExpired:
            p.kill()

        nk = du_lieu / "xem_truoc.log"
        nk_loi = du_lieu / "xem_truoc_loi.log"
        dong_mo = [x for x in (nk.read_text(encoding="utf-8", errors="replace").splitlines()
                               if nk.is_file() else []) if " mo_anh " in x]
        print("nhật ký:", dong_mo[-1] if dong_mo else "(không có — bản mã nguồn?)")
        if dong_mo and not ("insightface" in dong_mo[-1] and "'lmk'" in dong_mo[-1]):
            loi.append("mặt không do insightface nhận / thiếu điểm mốc (lmk)")
        if nk_loi.is_file():
            hong = [x.strip() for x in nk_loi.read_text(encoding="utf-8", errors="replace").splitlines()
                    if "InsightFace" in x or "khong tai duoc" in x or "khong tao duoc" in x]
            for x in hong[:5]:
                print("  lỗi:", x)
            if hong:
                loi.append("xem_truoc_loi.log có lỗi insightface / tải mô hình")
    finally:
        shutil.rmtree(du_lieu, ignore_errors=True)

    for m in loi:
        print("  [!]", m)
    print("XEM TRƯỚC ĐẠT" if not loi else f"XEM TRƯỚC HỎNG ({len(loi)} lỗi)")
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
