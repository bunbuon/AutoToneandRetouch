"""Kiểm cấu trúc phần Duyệt nhanh trong autotone_gui.py — không cần mở cửa sổ.

VÌ SAO KIỂM BẰNG AST CHỨ KHÔNG PHẢI CHẠY THỬ
    Máy dựng gói không có màn hình, mà lỗi hay gặp nhất khi thêm việc vào một
    file 4600 dòng lại thuần cấu trúc: gắn hàm vào NHẦM LỚP, hoặc gọi một hàm
    chưa hề tồn tại. Cả hai đều không báo lỗi lúc import, chỉ nổ khi người dùng
    bấm nút.

    Ngày 6/9 đã dính đúng bẫy này theo chiều ngược lại: bài kiểm khoá theo TÊN
    hàm, mà file có hai hàm _pump ở hai lớp khác nhau, nên bài kiểm nhìn vào
    hàm sai và báo đạt. Nên ở đây mọi phép kiểm đều khoá theo LỚP SỞ HỮU
    _build_lrbox, không phải theo tên hàm.

Chạy:  python kiem_gui_duyet.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parent
LOI: list[str] = []


def ktra(ten: str, dieu: bool, mo: str = "") -> None:
    if dieu:
        print(f"  {ten:<52} {mo or 'đạt'}")
    else:
        LOI.append(f"{ten}: {mo}")


def goi_trong(fn: ast.FunctionDef) -> set[str]:
    """Tên các hàm/phương thức được gọi bên trong một hàm."""
    ra = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute):
                ra.add(f.attr)
            elif isinstance(f, ast.Name):
                ra.add(f.id)
    return ra


def gan_thuoc_tinh(fn: ast.FunctionDef) -> set[str]:
    """Các self.<x> được gán trong hàm."""
    ra = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store) \
                and isinstance(n.value, ast.Name) and n.value.id == "self":
            ra.add(n.attr)
    return ra


def main() -> int:
    src = (GOC / "autotone_gui.py").read_text(encoding="utf-8")
    cay = ast.parse(src)

    # ---- lớp nào sở hữu _build_lrbox? Mọi thứ sau đây phải nằm ở ĐÚNG lớp đó.
    lop = None
    for n in ast.walk(cay):
        if isinstance(n, ast.ClassDef):
            if any(isinstance(c, ast.FunctionDef) and c.name == "_build_lrbox"
                   for c in n.body):
                lop = n
                break
    ktra("tìm được lớp sở hữu _build_lrbox", lop is not None,
         lop.name if lop else "KHÔNG THẤY")
    if lop is None:
        print("\n  [!] không kiểm tiếp được")
        return 1

    ham = {c.name: c for c in lop.body if isinstance(c, ast.FunctionDef)}

    # ---- 1. import
    nhap = set()
    for n in ast.walk(cay):
        if isinstance(n, ast.Import):
            for a in n.names:
                nhap.add((a.asname or a.name).split(".")[0])
    ktra("đã import duyet và duyet_ui",
         {"duyet", "duyet_ui"} <= nhap,
         #[[ Phải là import ở đầu file chứ không import trong hàm: PyInstaller
         #   dò module theo import tĩnh, import muộn thì gói ra thiếu file và
         #   chỉ nổ khi người dùng bấm nút. ]]
         "import tĩnh ở đầu file để PyInstaller gói được")

    # ---- 2. các phương thức mới nằm đúng lớp
    can = ["_build_duyet", "_cap_nhat_duyet", "do_duyet", "_soi_duyet",
           "do_mo_duyet", "do_xoa_duyet", "do_dung_duyet"]
    thieu = [t for t in can if t not in ham]
    ktra("đủ phương thức Duyệt nhanh, cùng lớp với _build_lrbox",
         not thieu, f"thiếu {thieu}" if thieu else f"{len(can)} hàm ở {lop.name}")

    # ---- 3. _build_lrbox thật sự gọi _build_duyet
    ktra("_build_lrbox có gọi _build_duyet",
         "_build_duyet" in goi_trong(ham["_build_lrbox"]),
         "khối mới được dựng thật, không phải code chết")

    # ---- 4. các widget nút bấm trỏ tới có tồn tại
    dat = gan_thuoc_tinh(ham.get("_build_duyet", ham["_build_lrbox"]))
    ktra("dựng đủ widget của khối",
         {"btn_duyet", "btn_duyet20", "pb_duyet", "lbl_duyet",
          "btn_mo_duyet", "btn_dung_duyet"} <= dat,
         ", ".join(sorted(x for x in dat if x.startswith(("btn", "pb", "lbl")))))

    # ---- 5. hàng grid đặt THẲNG vào khung cha của khâu 3 không đè lên nhau
    #[[ Chỉ đếm widget có cha là `cha` (khung của khâu 3). Widget nằm trong
    #   khung phụ tự có hệ hàng riêng, trùng số cũng không sao — đếm cả vào là
    #   bài kiểm kêu oan. ]]
    def hang_cua_cha(fn: ast.FunctionDef, ten_cha: str = "cha") -> set[int]:
        def ten(nut):
            """Tên gọi được của một widget: 'x' hoặc 'self.x'."""
            if isinstance(nut, ast.Name):
                return nut.id
            if isinstance(nut, ast.Attribute) and isinstance(nut.value, ast.Name) \
                    and nut.value.id == "self":
                return "self." + nut.attr
            return None

        # widget nào được tạo với `cha` làm cha
        con = set()
        for n in ast.walk(fn):
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call):
                a = n.value.args
                if a and isinstance(a[0], ast.Name) and a[0].id == ten_cha:
                    for t in n.targets:
                        if ten(t):
                            con.add(ten(t))

        ra = set()
        for n in ast.walk(fn):
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "grid"):
                continue
            nhan = n.func.value
            if isinstance(nhan, ast.Call):
                # gd.tieu_muc(cha, ...).grid(...) — đặt thẳng, không qua biến
                a = nhan.args
                la_cha = bool(a) and isinstance(a[0], ast.Name) and a[0].id == ten_cha
            else:
                la_cha = ten(nhan) in con
            if not la_cha:
                continue
            for k in n.keywords:
                if k.arg == "row" and isinstance(k.value, ast.Constant):
                    ra.add(k.value.value)
        return ra

    cu = hang_cua_cha(ham["_build_lrbox"])
    moi_h = hang_cua_cha(ham["_build_duyet"])
    ktra("khối Duyệt nhanh không đè lên hàng của khâu 3 cũ",
         bool(moi_h) and not (cu & moi_h),
         f"cũ {sorted(cu)} · mới {sorted(moi_h)}")

    # ---- 6. đường ghi màu KHÔNG được đụng gì tới duyệt
    #[[ Bài học 6/9: warmPreviews nằm trong đường áp thông số, nó hỏng thì kéo
    #   sập cả việc ghi màu. Ở phía app cũng vậy — do_apply không được gọi gì
    #   của duyet. ]]
    for ten in ("do_apply", "_ghi_xong", "_pump"):
        if ten in ham:
            g = goi_trong(ham[ten])
            xau = {x for x in g if "duyet" in x.lower()}
            ktra(f"{ten}() không gọi gì của Duyệt nhanh", not xau,
                 "đường ghi màu sạch" if not xau else f"gọi {xau}")

    src_lop = ast.get_source_segment(src, ham["do_apply"]) if "do_apply" in ham else ""
    ktra("do_apply không nhắc tới module duyet",
         "duyet." not in (src_lop or ""),
         "việc phụ hỏng không được kéo sập việc ghi màu")

    # ---- 7. duyet_ui.py KHÔNG được đọc JPEG bằng tk.PhotoImage
    #[[ ĐÂY LÀ PHÉP KIỂM QUAN TRỌNG NHẤT CỦA FILE NÀY.
    #
    #   tk.PhotoImage chỉ đọc GIF / PGM / PPM / PNG. Nó KHÔNG đọc JPEG. Mà ảnh
    #   duyệt Lightroom xuất ra chính là JPEG. Bản đầu gọi thẳng
    #   tk.PhotoImage(file=<.jpg>) nên MỌI ô trong lưới đều ra "không mở được",
    #   dù file ảnh hoàn toàn bình thường.
    #
    #   Không bắt được bằng cách chạy thử ở đây (máy này không có màn hình),
    #   nhưng bắt được bằng cách đọc mã: hễ còn tk.PhotoImage(file=...) là sai.
    #   Đường đúng duy nhất là PIL.ImageTk.
    #]]
    ui_src = (GOC / "duyet_ui.py").read_text(encoding="utf-8")
    ui_cay = ast.parse(ui_src)
    xau = []
    for n in ast.walk(ui_cay):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr == "PhotoImage" \
                and isinstance(n.func.value, ast.Name) and n.func.value.id == "tk":
            if any(k.arg == "file" for k in n.keywords):
                xau.append(n.lineno)
    ktra("duyet_ui không đọc file bằng tk.PhotoImage",
         not xau,
         "tk.PhotoImage không đọc được JPEG" if not xau
         else f"còn ở dòng {xau} — mọi ô sẽ ra “không mở được”")

    ktra("duyet_ui đọc ảnh qua PIL.ImageTk",
         "ImageTk" in ui_src and "from PIL import" in ui_src,
         "đường duy nhất đọc được JPEG trong Tk")

    #[[ Anh Tk phai duoc GIU THAM CHIEU, neu khong Python thu hoi ngay va
    #   canvas hien o trong — bay kinh dien cua Tk, va trieu chung giong het
    #   loi JPEG o tren nen rat de chan doan nham. ]]
    ktra("giữ tham chiếu ảnh đã vẽ",
         "self._anh[i] = img" in ui_src,
         "không giữ thì Python thu hồi, canvas ra ô trống")

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
