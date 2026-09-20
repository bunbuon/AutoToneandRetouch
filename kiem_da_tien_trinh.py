#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kiem_da_tien_trinh.py — Bước đo ảnh có chạy được kiểu SPAWN không.

    python kiem_da_tien_trinh.py

VÌ SAO CẦN
    Bước đo ảnh chạy tới 8 tiến trình song song. Ba hệ điều hành khởi động tiến
    trình con theo hai kiểu khác nhau:

        Linux  -> fork  : tiến trình con là bản sao của tiến trình mẹ, có sẵn
                          mọi thứ đã nạp. Gần như không bao giờ hỏng.
        macOS  -> spawn : chạy LẠI file thực thi từ đầu, rồi nạp lại module và
        Windows          gỡ (unpickle) tham số. Hỏng ở đây thì rất khó đoán.

    Máy phát triển ở đây là Linux, tức là hệ DUY NHẤT không lộ ra lỗi loại này.
    Nên bài kiểm ÉP dùng spawn, để lỗi của macOS/Windows hiện ra ngay tại đây.

BA THỨ SPAWN ĐÒI MÀ FORK KHÔNG
    1. Tham số truyền cho worker phải pickle được.
    2. Module phải import lại được trong tiến trình con.
    3. File thực thi khi bị chạy lại KHÔNG được làm lại việc của tiến trình mẹ.
       Với bản đóng gói, đó chính là multiprocessing.freeze_support(): thiếu nó
       thì mỗi tiến trình con MỞ THÊM MỘT CỬA SỔ APP, và mỗi cửa sổ lại mở tiếp
       8 cửa sổ nữa.
"""
from __future__ import annotations

import ast
import multiprocessing
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at   # noqa: E402


def anh_thu(d: Path, n: int) -> list:
    rng = np.random.default_rng(3)
    ra = []
    for i in range(n):
        a = rng.normal(120, 26, (700, 1000, 3)).clip(0, 255).astype("uint8")
        p = d / f"t{i:03d}.jpg"
        Image.fromarray(a).save(p, quality=85)
        ra.append(p)
    return ra


def co_freeze_support() -> bool:
    """main() của autotone_gui có gọi freeze_support KHÔNG, và có gọi SỚM không.

    Kiểm bằng cây cú pháp chứ không phải bằng chuỗi: viết freeze_support trong
    một dòng chú thích cũng khớp nếu tìm bằng chuỗi, mà chú thích thì không chạy.
    """
    src = Path(at.__file__).with_name("autotone_gui.py").read_text(encoding="utf-8")
    fn = next((n for n in ast.walk(ast.parse(src))
               if isinstance(n, ast.FunctionDef) and n.name == "main"), None)
    if fn is None:
        return False
    for i, stmt in enumerate(fn.body[:6]):     # phải nằm trong vài câu lệnh đầu
        for node in ast.walk(stmt):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "freeze_support"):
                return True
    return False


def main() -> int:
    loi = []

    #[[ 1 — freeze_support phai co, va phai o dau main().
    #]]
    if not co_freeze_support():
        loi.append("autotone_gui.main() KHONG goi multiprocessing.freeze_support() "
                   "trong vai cau lenh dau — ban dong goi tren macOS/Windows se mo "
                   "them mot cua so app cho MOI tien trinh con")

    #[[ 2 — CHAY THAT bang spawn. Day moi la phep kiem, phan tren chi la doc code.
    #]]
    try:
        ctx = multiprocessing.get_context("spawn")
    except ValueError:
        print("  [!] Hệ này không có spawn — bỏ qua phần chạy thật.")
        ctx = None

    if ctx is not None:
        with tempfile.TemporaryDirectory() as t:
            ds = anh_thu(Path(t), 6)
            cfg = dict(at.DEFAULTS)
            tasks = [(str(p), cfg["preview_px"], cfg["meter"],
                      cfg["meter_highlight_cut"], False, cfg["face_px"],
                      cfg["face_score"], cfg["focus_quantile"],
                      cfg["focus_face_gain"], cfg.get("face_min_ratio", 0.25),
                      cfg.get("subject_keep", 0.60), cfg.get("subject_dark_ev", 2.0),
                      cfg.get("face_min_score_sub", 0.0),
                      cfg.get("big_low_ratio", 0.0), cfg.get("big_low_gap", 0.15),
                      cfg.get("big_low_floor", 0.70), False)
                     for p in ds]
            #[[ Goi CHINH _measure_star ma analyze() goi, khong viet mot ham
            #   tuong duong o day — kiem dung cai chay that.
            #]]
            try:
                with ctx.Pool(processes=2) as pool:
                    ket = pool.map(at._measure_star, tasks)
            except Exception as ex:                          # noqa: BLE001
                loi.append(f"Chay spawn that bai: {type(ex).__name__}: {ex}")
                ket = []
            hong = [r for r in ket if not r.get("ok")]
            if ket and hong:
                loi.append(f"{len(hong)}/{len(ket)} anh do hong khi chay spawn: "
                           f"{hong[0].get('error', '')[:70]}")
            elif ket:
                print(f"  spawn: {len(ket)}/{len(ds)} ảnh đo xong, 2 tiến trình con")

    for m in loi:
        print("  [!]", m)
    print("TAT CA DAT" if not loi else f"{len(loi)} LOI")
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
