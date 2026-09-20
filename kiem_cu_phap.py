"""Biên dịch MỌI file .py trong dự án. Bài rẻ nhất, bắt lỗi ngớ ngẩn nhất.

VÌ SAO CẦN MỘT BÀI TẦM THƯỜNG NHƯ THẾ NÀY
    Dự án viết chú thích theo khối #[[ ... #]] đặt NGAY TRONG docstring. Quên
    một dấu \"\"\" đóng thì docstring nuốt luôn mấy chục dòng mã bên dưới, và
    Python báo lỗi ở một dòng HOÀN TOÀN KHÁC — thường là một chữ tiếng Việt
    trong docstring của hàm kế tiếp. Đọc thông báo đó không ai nghĩ tới nguyên
    nhân thật.

    Đã xảy ra ba lần trong hai ngày. Mỗi lần đều mất một vòng chạy thử mới phát
    hiện, vì mấy bài kiểm khác chỉ nạp file chúng cần.

    Bài này nạp HẾT, nên hỏng ở file nào cũng lộ ngay.

Chạy:  python3 kiem_cu_phap.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parent


def main() -> int:
    #[[ Console Windows la cp1252, khong in noi chu Viet — bai kiem DAT van
    #   chet o dong tong ket, trong y het bai kiem hong. Ep UTF-8 truoc. ]]
    for _l in (sys.stdout, sys.stderr):
        try:
            _l.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass

    loi = []
    n = 0
    for p in sorted(GOC.glob("*.py")):
        n += 1
        try:
            ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
        except SyntaxError as ex:
            loi.append(f"{p.name}:{ex.lineno}  {ex.msg}")
        except OSError as ex:
            loi.append(f"{p.name}  không đọc được: {ex}")
    print(f"  nạp thử {n} file .py")
    if loi:
        print()
        for m in loi:
            print("  [!] " + m)
        print(f"{len(loi)} LỖI")
        return 1
    print("TẤT CẢ ĐẠT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
