#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""thu_may_thu_hai.py — mở AutoTone như một MÁY THỨ HAI trên chính máy này (13/10).

Để thử "một key một máy một lúc" + credit dùng chung mà không cần hai máy thật:
    - thư mục dữ liệu riêng (%TEMP%\\AutoTone_may_thu_hai) — giấy phép, phiên riêng
    - mã máy giả "THUMAYHAI001", tên máy "MAY-THU-HAI"
Mở song song với app thường (THU_CREDIT_2_MAY.bat làm sẵn), nhập cùng một key ở
cả hai: cửa sổ mở sau sẽ hỏi "Key đang dùng trên máy khác".

CHỈ để thử — không đóng gói (dong_goi.LOAI_TRU).
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("AUTOTONE_DATA",
                      str(Path(tempfile.gettempdir()) / "AutoTone_may_thu_hai"))
Path(os.environ["AUTOTONE_DATA"]).mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(Path(__file__).resolve().parent))

import khoa  # noqa: E402
import tin_dung  # noqa: E402

khoa.ma_may = lambda: "THUMAYHAI001"
tin_dung.ten_may = lambda: "MAY-THU-HAI"

if __name__ == "__main__":
    import autotone_gui
    autotone_gui.main()
