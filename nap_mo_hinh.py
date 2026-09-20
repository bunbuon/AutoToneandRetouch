#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nap_mo_hinh.py — tải sẵn những mô hình mà saytool vốn tự tải lúc chạy.

    python nap_mo_hinh.py <thư mục ToolCloneEvoto>

VÌ SAO CẦN
    saytool tải hai thứ về lúc chạy lần đầu:

        buffalo_l                 326 MB  -> ~/.insightface/models/buffalo_l
        resnet34_faceparse.onnx    94 MB  -> ~/.cache/skin_spike/

    Chạy từ mã nguồn thì không sao — tải một lần rồi thôi. Nhưng bản đóng gói
    mà vẫn phải tải thì lần đầu người dùng bấm Retouch sẽ đứng vài phút không
    biết vì sao, và tải từ github.com — địa chỉ bị chặn ở khá nhiều mạng công
    ty. Nên tải sẵn lúc ĐÓNG GÓI rồi mang theo trong gói.

    File này KHÔNG tự viết lại cách tải: nó gọi đúng hàm của insightface và của
    saytool. Hai bên đổi địa chỉ tải thì ở đây theo luôn, không phải sửa.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def nap(goc_tool: Path) -> int:
    goc_tool = Path(goc_tool).resolve()
    if not (goc_tool / "saytool" / "cli.py").is_file():
        print(f"  [!] {goc_tool} không phải thư mục ToolCloneEvoto")
        return 2
    sys.path.insert(0, str(goc_tool))
    os.chdir(goc_tool)
    loi = []

    #[[ 1 — buffalo_l. Goi chinh ensure_available cua insightface, khong tu
    #   dung lai dia chi tai va cach giai nen.
    #]]
    print("  [1/2] buffalo_l (nhận diện mặt, ~326 MB)")
    try:
        from insightface.utils.storage import ensure_available
        d = ensure_available("models", "buffalo_l")
        n = len(list(Path(d).glob("*.onnx")))
        print(f"        {d}  ({n} file .onnx)")
        if n == 0:
            loi.append("buffalo_l tải xong nhưng không có file .onnx nào")
    except Exception as ex:                                  # noqa: BLE001
        loi.append(f"buffalo_l: {type(ex).__name__}: {ex}")

    #[[ 2 — face parsing. Dung chinh _download cua skin_spike4, nen dia chi va
    #   thu muc dem deu lay tu ben do.
    #]]
    print("  [2/2] resnet34_faceparse.onnx (phân vùng da, ~94 MB)")
    try:
        from saytool.loi import skin_spike4 as s4
        p = s4._download("resnet34_faceparse.onnx", s4.PARSE_URL)
        if p is None or not Path(p).is_file():
            loi.append("không tải được resnet34_faceparse.onnx")
        else:
            print(f"        {p}  ({Path(p).stat().st_size / 1e6:.0f} MB)")
    except Exception as ex:                                  # noqa: BLE001
        loi.append(f"face parsing: {type(ex).__name__}: {ex}")

    for m in loi:
        print("  [!]", m)
    if loi:
        print("\n  Gói vẫn đóng được, nhưng lần đầu bấm Retouch máy sẽ phải tự")
        print("  tải những thứ trên — cần mạng vào được github.com.")
    else:
        print("\n  Đủ mô hình. Gói sẽ chạy được ngay, không phải tải gì.")
    return 1 if loi else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(nap(Path(sys.argv[1])))
