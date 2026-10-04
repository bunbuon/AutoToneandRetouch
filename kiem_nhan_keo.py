#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kiem_nhan_keo.py — Nhãn ghi cứng không được nói khác saytool.

VÌ SAO CẦN BÀI NÀY
    retouch.NHAN_DEP chép lại nhãn thanh kéo để thêm dấu tiếng Việt. Nhưng
    saytool thỉnh thoảng ĐỔI CÔNG DỤNG một bước, và khi đó nhãn ghi cứng
    thành lời nói dối — mà không có gì báo cả.

    Hỏng thật 02/10: bước `da_body` ban đầu là "Dong deu mau da co the", bảng
    ghi "Đều màu da cơ thể". Sau đó saytool huấn luyện lại thành "Làm mịn da
    cơ thể" — đổi hẳn công dụng. Bảng không ai sửa, nên AutoTone hiển thị nhãn
    cũ ĐÈ LÊN nhãn mới. Người dùng thấy saytool gọi một đằng, AutoTone gọi một
    nẻo, và đi tìm tính năng "làm mịn da cơ thể" trong khi nó nằm ngay đó.

    Bài này bắt đúng chuyện đó: chỉ cho phép ghi cứng khi saytool còn viết
    KHÔNG DẤU. Bước nào bên kia đã có dấu thì để nó tự nói.

    python kiem_nhan_keo.py
"""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

GOC = Path(__file__).resolve().parent
sys.path.insert(0, str(GOC))

dat = hong = 0


def ket(t, ok, ghi=""):
    global dat, hong
    if ok:
        dat += 1
        print(f"  [DAT ] {t}")
    else:
        hong += 1
        print(f"  [HONG] {t}  {str(ghi)[:160]}")


def co_dau(t: str) -> bool:
    """Chuỗi có chữ tiếng Việt có dấu không?"""
    return any(unicodedata.combining(c) for c in unicodedata.normalize("NFD", t))


def main() -> int:
    for _l in (sys.stdout, sys.stderr):
        try:
            _l.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass

    import retouch as rt

    tool = rt.tim_tool()
    if not tool or not rt.hop_le(tool):
        print("  (bỏ qua: chưa có ToolCloneEvoto)")
        return 0

    #[[ Hoi THAT, khong dung bang du phong: bang du phong chinh la cai ta dang
    #   nghi ngo. ]]
    ds = rt.thanh_keo(tool, lam_lai=True)
    that = {}
    for ten, nhan, _md, _goi in ds:
        that[ten] = nhan

    ket("hỏi được thanh kéo thật từ saytool", len(that) >= 5, list(that))

    #[[ Doc nhan GOC cua saytool (truoc khi NHAN_DEP de len) qua tien trinh
    #   con — day la nguon su that de doi chieu. ]]
    import json
    import subprocess
    ma = ("import json\n"
          "from saytool.buoc import tat_ca\n"
          "d = {}\n"
          "for b in tat_ca():\n"
          "    for tk in getattr(b, 'thanh_keo', []):\n"
          "        d[tk.ten] = tk.nhan\n"
          "print(json.dumps(d, ensure_ascii=False))\n")
    try:
        r = subprocess.run([str(rt.python_cho(tool)), "-c", ma],
                           cwd=str(tool), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300)
        goc = json.loads([x for x in r.stdout.splitlines()
                          if x.startswith("{")][-1])
    except Exception as ex:                                  # noqa: BLE001
        ket("đọc được nhãn gốc của saytool", False, repr(ex))
        print(f"\n  {dat} đạt / {hong} hỏng")
        return 1
    ket("đọc được nhãn gốc của saytool", bool(goc), list(goc))

    #[[ PHEP CHINH: moi muc trong NHAN_DEP chi duoc ton tai neu saytool con
    #   viet khong dau. Co dau roi ma van de len = dang che mat nhan that. ]]
    thua = [t for t, g in goc.items()
            if t in rt.NHAN_DEP and co_dau(g)]
    ket("không đè lên nhãn saytool đã có dấu", not thua,
        f"đang đè: {thua} — bỏ chúng khỏi NHAN_DEP")

    #[[ Chieu nguoc lai: buoc nao saytool viet khong dau thi NEN co trong bang,
    #   khong thi giao dien hien chu khong dau. Chi nhac, khong tinh la hong —
    #   buoc moi xuat hien van dung duoc ngay. ]]
    thieu = [t for t, g in goc.items()
             if t not in rt.NHAN_DEP and not co_dau(g)]
    if thieu:
        print(f"  [ nhắc ] saytool còn viết không dấu, nên thêm vào NHAN_DEP: "
              f"{thieu}")

    #[[ Nhan app hien ra phai KHOP voi saytool ve NGHIA. Khong so sanh duoc
    #   nghia bang may, nhung so sanh duoc khi saytool da co dau: luc do nhan
    #   app phai giong het. ]]
    lech = [(t, goc[t], that[t]) for t in that
            if t in goc and co_dau(goc[t]) and that[t] != goc[t]]
    ket("nhãn app khớp nhãn saytool (ở bước đã có dấu)", not lech, lech)

    print(f"\n  {dat} đạt / {hong} hỏng")
    return 1 if hong else 0


if __name__ == "__main__":
    sys.exit(main())
