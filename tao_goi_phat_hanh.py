#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đóng các gói tài nguyên .zip để tải lên GitHub Releases.

VÌ SAO LÀ MỘT SCRIPT CHỨ KHÔNG PHẢI NÉN TAY
    Ba gói này phải khớp CHÍNH XÁC với bảng `GOI` trong tai_nguyen.py: đúng
    tên file, đúng cấu trúc thư mục bên trong, đúng SHA-256. Sai một chỗ thì
    máy người dùng tải về rồi từ chối, hoặc tệ hơn là giải nén ra sai chỗ và
    báo "thiếu tài nguyên" mãi mãi.

    Script còn IN RA đoạn mã để dán ngược vào `GOI` — nên mã kiểm tra không
    bao giờ phải gõ tay.

CẤU TRÚC BÊN TRONG MỖI GÓI
    Phải khớp `dau_hieu` của gói tương ứng, vì tai_nguyen.da_co() soi đúng
    những đường dẫn đó để biết gói đã giải nén đủ chưa:

        torch-cu130.zip   torch/__init__.py, torch/lib/...  + 11 gói đi kèm
        mo-hinh.zip       mo_hinh/vet.pt, ...
        mediapipe.zip     mediapipe/__init__.py, ...

Chạy:
    python tao_goi_phat_hanh.py                 # đóng cả ba
    python tao_goi_phat_hanh.py torch mo-hinh   # chỉ đóng gói được nêu
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sys
import time
import zipfile
from pathlib import Path

GOC = Path(__file__).resolve().parent
RA = GOC / "phat_hanh"
SP = GOC / "venv_build" / "Lib" / "site-packages"

#[[ TORCH KÉO THEO 11 GÓI BẠN ĐỒNG HÀNH.
#
#   Đo được bằng cách thử nạp từng bước: bỏ gói nào thì `import torch` chết ở
#   gói đó. Không đoán theo requirements.txt — bản cài thực tế khác xa.
#
#   Thiếu một cái trong đây thì người dùng tải về 1.4 GB rồi vẫn không chạy
#   được, và thông báo lỗi chỉ nói "No module named sympy" — không ai đoán ra
#   là gói phát hành đóng thiếu.
#]]
TORCH_KEM = ["typing_extensions.py", "sympy", "networkx", "filelock", "fsspec",
             "jinja2", "markupsafe", "mpmath", "torchgen", "functorch"]

#[[ MEDIAPIPE KÉO THEO 13 GÓI — ĐO CHỨ KHÔNG ĐOÁN.
#
#   Đo bằng cách nạp thử trong thư mục CHỈ có mediapipe: thiếu gì thì lỗi nói
#   tên gói đó, thêm vào rồi nạp lại, lặp tới khi chạy trót lọt. Hết 9 vòng.
#
#   Bản đầu tôi chỉ đoán 5 gói, đóng xong mới lòi ra "No module named
#   'google'" — mediapipe cần protobuf, rồi kéo tiếp cả matplotlib. Đóng gói
#   thiếu kiểu này thì người dùng tải 49 MB về vẫn không dùng được, mà thông
#   báo lỗi không hề nhắc tới mediapipe.
#
#   `google` là protobuf. `matplotlib` kéo theo packaging, pyparsing, cycler,
#   dateutil, kiwisolver, fontTools, six.
#
#   KHÔNG có jax/jaxlib (229 MB): chúng vào theo mediapipe lúc pip cài nhưng
#   không file nào trong cả hai dự án import, và bài đo trên chạy trót lọt mà
#   không cần chúng.
#]]
MEDIAPIPE_KEM = ["absl", "attr", "attrs", "flatbuffers", "sounddevice.py",
                 "google", "matplotlib", "packaging", "pyparsing", "cycler",
                 "dateutil", "kiwisolver", "fontTools", "six"]


def bam(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def them(z: zipfile.ZipFile, nguon: Path, goc_tuong_doi: Path) -> int:
    """Chép một file/thư mục vào zip, giữ đường dẫn tương đối. -> số file."""
    n = 0
    if nguon.is_file():
        z.write(nguon, str(nguon.relative_to(goc_tuong_doi)))
        return 1
    for f in nguon.rglob("*"):
        if not f.is_file():
            continue
        #[[ __pycache__ chiếm chỗ mà vô dụng: .pyc gắn với đúng một phiên bản
        #   Python, máy người dùng nạp lại từ .py là xong. ]]
        if "__pycache__" in f.parts or f.suffix == ".pyc":
            continue
        #[[ BỎ ĐỒ BIÊN DỊCH: torch/include/ (9245 file .h) và 12 file .lib chỉ
        #   dùng khi BIÊN DỊCH extension C++ — chạy thì không đụng tới.
        #
        #   Đã kiểm chứ không đoán: đổi tên cả include/ lẫn .lib đi rồi chạy
        #   `import torch` trong tiến trình sạch — vẫn ra 2.13.0+cu130,
        #   cuda.is_available() vẫn True, nhân ma trận vẫn đúng.
        #
        #   Bớt được ~77 MB chưa nén, và quan trọng hơn là nới khoảng cách tới
        #   giới hạn 2 GB/file của GitHub.
        #]]
        if f.suffix in (".lib", ".h", ".hpp") or "include" in f.parts:
            continue
        z.write(f, str(f.relative_to(goc_tuong_doi)))
        n += 1
    return n


def dong_goi(ten: str, muc: list[tuple[Path, Path]], file_zip: str) -> Path | None:
    """muc: danh sách (đường dẫn nguồn, gốc để tính đường dẫn tương đối)."""
    thieu = [str(p) for p, _ in muc if not p.exists()]
    if thieu:
        print(f"  [!] Bỏ qua {ten} — chưa có:")
        for t in thieu:
            print(f"        {t}")
        return None

    RA.mkdir(parents=True, exist_ok=True)
    dich = RA / file_zip
    tam = dich.with_suffix(".zip.part")
    tam.unlink(missing_ok=True)

    print(f"  Đang nén {ten} ...")
    t0 = time.perf_counter()
    n = 0
    #[[ compresslevel=6 chứ không phải 9: thử cả hai trên torch, 9 chậm hơn
    #   khoảng 4 lần mà chỉ nhỏ hơn ~2%. Không đáng. ]]
    with zipfile.ZipFile(tam, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for nguon, goc_td in muc:
            n += them(z, nguon, goc_td)
    os.replace(tam, dich)

    mb = dich.stat().st_size / 1048576
    print(f"      {n} file  →  {mb:.0f} MB  ({time.perf_counter() - t0:.0f}s)")
    return dich


def goi_torch():
    muc = [(SP / "torch", SP)]
    thieu = []
    for t in TORCH_KEM:
        for ten in (t, t + ".py"):
            p = SP / ten
            if p.exists():
                muc.append((p, SP))
                break
        else:
            thieu.append(t)
    if thieu:
        print(f"  [!] torch thiếu gói đi kèm: {', '.join(thieu)}")
        print("      Gói đóng ra sẽ KHÔNG nạp được. Cài chúng rồi đóng lại.")
        return None
    return dong_goi("torch (CUDA)", muc, "torch-cu130.zip")


def goi_mo_hinh():
    #[[ Nguồn là build/mo_hinh_du — thư mục dong_goi.py đã gom sẵn từ BA chỗ
    #   (mo_hinh/ của tool + faceparse onnx + insightface buffalo_l). Gom lại
    #   ở đây nữa thì hai đường gom dễ lệch nhau. Chưa có thì chạy:
    #       python dong_goi.py --thu --tool-retouch <đường dẫn tool>
    #]]
    d = GOC / "build" / "mo_hinh_du"
    if not d.is_dir():
        print("  [!] Chưa có build/mo_hinh_du.")
        print("      Dựng bằng:  python dong_goi.py --thu "
              "--tool-retouch \"F:\\Claude AI\\ToolCloneEvoto\"")
        return None
    # Bên trong zip phải là mo_hinh/... nên lấy gốc tương đối là build/
    tam_goc = GOC / "build"
    lien_ket = tam_goc / "mo_hinh"
    if lien_ket.exists() and not lien_ket.is_symlink():
        shutil.rmtree(lien_ket, ignore_errors=True)
    shutil.copytree(d, lien_ket, dirs_exist_ok=True)
    try:
        return dong_goi("mô hình retouch", [(lien_ket, tam_goc)], "mo-hinh.zip")
    finally:
        shutil.rmtree(lien_ket, ignore_errors=True)


def goi_mediapipe():
    muc = [(SP / "mediapipe", SP)]
    thieu = []
    for t in MEDIAPIPE_KEM:
        #[[ Gói có thể là thư mục (matplotlib/) hoặc MỘT file .py đơn
        #   (six.py, sounddevice.py). Chỉ thử đúng một dạng là sót. ]]
        for ten in (t, t + ".py"):
            p = SP / ten
            if p.exists():
                muc.append((p, SP))
                break
        else:
            thieu.append(t)
    if thieu:
        print(f"  [!] mediapipe thiếu gói đi kèm: {', '.join(thieu)}")
        print("      Gói đóng ra sẽ KHÔNG nạp được. Cài chúng vào venv_build rồi đóng lại.")
        return None
    return dong_goi("mediapipe", muc, "mediapipe.zip")


LAM = {"torch": goi_torch, "mo-hinh": goi_mo_hinh, "mediapipe": goi_mediapipe}


def main(argv=None) -> int:
    for _l in (sys.stdout, sys.stderr):
        try:
            _l.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass

    tham = list(argv if argv is not None else sys.argv[1:])
    ten_goi = [t for t in tham if not t.startswith("-")] or list(LAM)
    xau = [t for t in ten_goi if t not in LAM]
    if xau:
        print(f"Không biết gói: {', '.join(xau)}")
        print(f"Có: {', '.join(LAM)}")
        return 2

    sys.path.insert(0, str(GOC))
    import tai_nguyen as tn

    print(f"\n  Nguồn thư viện: {SP}")
    print(f"  Ra:             {RA}\n")

    ket = {}
    for t in ten_goi:
        p = LAM[t]()
        if p:
            ket[t] = p

    if not ket:
        print("\n  Không đóng được gói nào.")
        return 1

    print("\n  ─── Dán đoạn này vào GOI trong tai_nguyen.py ───\n")
    for t, p in ket.items():
        g = tn.GOI.get(t)
        mb = round(p.stat().st_size / 1048576)
        print(f'    "{t}": Goi(')
        print(f'        ten="{t}", phien_ban="{g.phien_ban if g else "1"}", '
              f'file_zip="{p.name}",')
        print(f'        mb={mb}, mo_ta="{g.mo_ta if g else ""}",')
        print(f'        sha256="{bam(p)}",')
        print(f'        dau_hieu={g.dau_hieu if g else ()},')
        print('    ),')

    print("\n  ─── Tải lên GitHub Releases ───\n")
    for t, p in ket.items():
        g = tn.GOI.get(t)
        tag = f"{t}-{g.phien_ban}" if g else f"{t}-1"
        print(f'    gh release create {tag} "{p}" \\')
        print(f'        --repo bunbuon/AutoToneandRetouch \\')
        print(f'        --title "{tag}" --notes "Tài nguyên {t}"')
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
