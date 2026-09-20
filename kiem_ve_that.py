"""Dựng thật ba cột tuỳ chọn bằng Tk và kiểm _xep_cot() trên hình học thật.

VÌ SAO CẦN FILE NÀY BÊN CẠNH kiem_bo_cuc.py
    kiem_bo_cuc.py đọc mã nguồn — bắt được "quên nối <Configure>", "quên chốt
    chống vòng lặp". Nhưng nó KHÔNG chạy được _xep_cot(), nên không biết hàm đó
    có thật sự đổi cột đúng lúc không, và có tự gọi lại vô tận không.

    File này mở một màn hình ảo (Xvfb), dựng ba cột bằng widget Tk thật, rồi
    gọi CHÍNH hàm _xep_cot() trong autotone_gui.py — cắt ra bằng ast, không
    chép lại một dòng nào.

LƯU Ý VỀ PHÔNG CHỮ
    Máy này không có Segoe UI nên bề ngang đo được khác Windows. Vì vậy file
    này KHÔNG khẳng định "ở 1360 px thì ra 3 cột" — nó kiểm thứ không phụ thuộc
    phông: rộng thì phải nhiều cột hơn hẹp, số cột chỉ nằm trong {1,2,3}, và
    gọi lại nhiều lần thì không bao giờ đổi qua đổi lại.

Chạy:  xvfb-run -a python3.12 kiem_ve_that.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import tkinter as tk
from tkinter import ttk

GOC = Path(__file__).resolve().parent
LOI: list[str] = []


def ktra(ten: str, dieu: bool, mo: str = "") -> None:
    if dieu:
        print(f"  {ten:<52} {mo or 'đạt'}")
    else:
        LOI.append(f"{ten}: {mo}")


def lay_ham(ten: str):
    """Cắt đúng hàm thật ra khỏi autotone_gui.py rồi nạp — không chép lại."""
    src = (GOC / "autotone_gui.py").read_text(encoding="utf-8")
    cay = ast.parse(src)
    for n in ast.walk(cay):
        if isinstance(n, ast.FunctionDef) and n.name == ten:
            doan = ast.get_source_segment(src, n)
            # bỏ thụt đầu dòng của phương thức trong lớp
            dong = doan.splitlines()
            lui = len(dong[0]) - len(dong[0].lstrip())
            doan = "\n".join(d[lui:] if len(d) > lui else d.strip()
                             for d in dong)
            ns: dict = {}
            exec(compile(doan, f"<{ten}>", "exec"), ns)     # noqa: S102
            return ns[ten]
    raise SystemExit(f"khong tim thay ham {ten}")


class Gia:
    """Đủ thuộc tính để _xep_cot() chạy — không cần cả lớp App."""

    def __init__(self, bo):
        self._cot_tuy_chon = bo
        self._so_cot_hien = 0


NHAN = {
    "c1": ["Chế độ", "Đo sáng", "Cân bằng trắng", "Mặt sáng tới mức",
           "Độ trộn", "Tách cảnh khi cách", "Chỉnh tối đa ±",
           "Kéo sáng tối đa +", "Mức độ can thiệp"],
    "c2": ["Trộn — tự tách theo mức sáng", "Cả buổi ánh sáng ngày",
           "Cả buổi ánh đèn", "Tự kéo Highlights khi cháy sáng",
           "Tự kéo Shadows khi bết tối", "Đẩy tone về da trắng hồng",
           "Tự chỉnh Curve (parametric)"],
    "c3": ["Tách cảnh theo thời gian", "…nhưng chỉ khi bối cảnh cũng đổi",
           "Tách cảnh theo bối cảnh khung hình",
           "Đồng bộ sáng + màu trong cùng bối cảnh", "Lọc ảnh trùng khung",
           "Lọc ảnh mắt không dùng được",
           "Auto Transform cho ảnh backdrop / màn LED"],
}


def main() -> int:
    xep_cot = lay_ham("_xep_cot")

    root = tk.Tk()
    root.geometry("1400x700")
    khung = ttk.Frame(root)
    khung.pack(fill="both", expand=True)
    cot = []
    for k in ("c1", "c2", "c3"):
        c = ttk.Frame(khung)
        for t in NHAN[k]:
            (ttk.Label(c, text=t) if k == "c1"
             else ttk.Checkbutton(c, text=t)).pack(anchor="w")
        cot.append(c)
    gia = Gia((khung, *cot))

    def do(be_ngang: int) -> int:
        root.geometry(f"{be_ngang}x700")
        root.update_idletasks()
        root.update()
        xep_cot(gia)
        root.update_idletasks()
        return gia._so_cot_hien

    can = [c.winfo_reqwidth() for c in cot]
    root.update_idletasks()
    can = [c.winfo_reqwidth() for c in cot]
    print(f"  (phông của máy này: ba cột cần {can} px)\n")

    rong_du = sum(can) + 60
    ktra("rộng rãi thì ra 3 cột", do(rong_du + 200) == 3,
         f"tại {rong_du + 200} px")

    #[[ Hep dan thi so cot phai GIAM DAN, khong duoc nhay lung tung. Day la
    #   thu khong phu thuoc phong chu. ]]
    day = [do(w) for w in range(rong_du + 200, 200, -60)]
    ktra("hẹp dần thì số cột chỉ giảm, không nhảy lung tung",
         all(b <= a for a, b in zip(day, day[1:])),
         " ".join(map(str, day)))
    ktra("số cột luôn nằm trong {1, 2, 3}", set(day) <= {1, 2, 3},
         f"các mức gặp: {sorted(set(day))}")
    ktra("hẹp nhất thì về 1 cột", day[-1] == 1, f"cuối cùng = {day[-1]} cột")
    ktra("có đi qua mức 2 cột", 2 in day, "không nhảy thẳng 3 → 1")

    #[[ CHONG VONG LAP. Xep lai cot lam Tk ban <Configure>, ban tiep vao
    #   _xep_cot. Khong co chot thi treo app. Goi 30 lan o cung be ngang: tu
    #   lan thu hai tro di phai KHONG doi gi nua. ]]
    do(rong_du + 200)
    truoc = gia._so_cot_hien
    for _ in range(30):
        xep_cot(gia)
    ktra("gọi lại 30 lần cùng bề ngang: không đổi gì",
         gia._so_cot_hien == truoc, f"vẫn {truoc} cột — không có vòng lặp")

    #[[ Chua ve lan nao (winfo_width = 1) thi phai thoat ngay, khong duoc
    #   quyet dinh dua tren kich thuoc gia. ]]
    r2 = tk.Toplevel(root)
    k2 = ttk.Frame(r2)
    c = [ttk.Frame(k2) for _ in range(3)]
    g2 = Gia((k2, *c))
    xep_cot(g2)
    ktra("chưa vẽ lần nào thì không quyết định gì",
         g2._so_cot_hien == 0, "thoát sớm, không xếp theo kích thước giả")

    root.destroy()
    print()
    if LOI:
        for m in LOI:
            print("  [!] " + m)
        print(f"{len(LOI)} LỖI")
        return 1
    print("TẤT CẢ ĐẠT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
