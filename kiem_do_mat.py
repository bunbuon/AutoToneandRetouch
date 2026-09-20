#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kiem_do_mat.py — Kiểm measure() chạy được với MỌI cách đo, không chỉ cách mặc định.

    python kiem_do_mat.py

VÌ SAO CÓ FILE NÀY
    measure() bọc toàn thân trong try/except và trả về {"ok": False, "error": ...}.
    Rất tiện lúc chạy thật — một ảnh hỏng không làm gãy cả buổi — nhưng nó cũng
    NUỐT LUÔN lỗi lập trình. Một UnboundLocalError trong đó không nổ ra màn hình
    mà biến thành "không đọc được ảnh" cho cả thư mục.

    Đúng lỗi đó đã có thật: face_stats, best_eye, best_sharp, fw_, fh_ chỉ được
    gán bên trong "if want_faces", trong khi out.update(...) đọc chúng vô điều
    kiện. Chạy với cách đo mặc định (face + wb skin) thì không bao giờ lộ, vì
    want_faces luôn True. Đổi sang "Trung bình toàn khung" + WB "Không đụng tới"
    là hỏng sạch.

HAI LỚP KIỂM, CỐ Ý KHÁC NHAU
    1. Chạy thật 6 cách đo × 2 giá trị wb_needs_faces = 12 tổ hợp.
    2. Quét AST tìm tên "chỉ gán trong khối if mà vẫn đọc sau khối".
    Lớp 1 bắt lỗi đang có; lớp 2 bắt lỗi cùng loại SẼ thêm vào sau này, kể cả ở
    nhánh mà lớp 1 chưa nghĩ ra tổ hợp để chạm tới.
"""
from __future__ import annotations

import ast
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at   # noqa: E402

CACH_DO = ("face", "focus", "subject", "center", "average", "median")


def anh_thu(d: Path) -> Path:
    """Một JPEG nhiễu. read_raw() dò preview bằng cách quét marker JPEG nên file
    .jpg thường cũng đi qua đúng đường mà file RAW đi."""
    a = np.random.default_rng(7).normal(118, 26, (900, 1350, 3)).clip(0, 255)
    p = d / "thu.jpg"
    Image.fromarray(a.astype("uint8")).save(p, quality=88)
    return p


def quet_ast() -> list:
    """Tên nào chỉ gán trong 'if want_faces' mà vẫn bị đọc sau khối đó."""
    src = Path(at.__file__).read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "measure")
    blk = next(n for n in ast.walk(fn)
               if isinstance(n, ast.If) and isinstance(n.test, ast.Name)
               and n.test.id == "want_faces")
    lo = blk.lineno
    hi = max((getattr(x, "end_lineno", 0) or 0) for x in ast.walk(blk))

    trong = {n.id for n in ast.walk(blk)
             if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    ngoai, doc_sau = set(), set()
    for n in ast.walk(fn):
        if not isinstance(n, ast.Name) or lo <= n.lineno <= hi:
            continue
        if isinstance(n.ctx, ast.Store):
            ngoai.add(n.id)
        elif n.lineno > hi:
            doc_sau.add(n.id)
    return sorted((trong - ngoai) & doc_sau)


def main() -> int:
    loi = []
    with tempfile.TemporaryDirectory() as d:
        p = anh_thu(Path(d))
        for m in CACH_DO:
            for nf in (False, True):
                r = at.measure(p, 480, m, wb_needs_faces=nf)
                if not r["ok"]:
                    loi.append(f"do={m} wb_needs_faces={nf}: {r['error'][:90]}")
                elif r.get("metered_ev") is None:
                    loi.append(f"do={m} wb_needs_faces={nf}: ok nhung metered_ev rong")

    sot = quet_ast()
    if sot:
        loi.append("Ten chi gan trong 'if want_faces' ma van doc sau khoi: "
                   + ", ".join(sot) + " — se thanh UnboundLocalError bi except "
                   "cua measure() nuot mat")

    for m in loi:
        print("  [!]", m)
    print("TAT CA DAT" if not loi else f"{len(loi)} LOI")
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
