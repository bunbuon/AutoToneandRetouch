"""Kiểm mấy chỗ CHỈ hỏng khi mang app sang macOS.

Windows không có mấy chuyện này nên chạy cả năm cũng không lộ ra. Sang Mac thì
lộ ngay ở lần chạy đầu, và lộ dưới dạng con số sai chứ không phải thông báo lỗi
— kiểu khó truy nhất.

Chạy:  python3 kiem_mac.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

GOC = Path(__file__).resolve().parent
sys.path.insert(0, str(GOC))
LOI: list[str] = []


def ktra(ten: str, dieu: bool, mo: str = "") -> None:
    if dieu:
        print(f"  {ten:<56} {mo or 'đạt'}")
    else:
        LOI.append(f"{ten}: {mo}")


def main() -> int:
    import autotone as at

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        #[[ Dung canh ngo that: 63 anh RAW, moi anh mot file "._" di kem do
        #   macOS de lai khi chep qua USB exFAT/NTFS, va DUY NHAT mot anh co
        #   sidecar .xmp. ]]
        for i in range(1, 64):
            (d / f"SAY-{i:03d}.ARW").write_bytes(b"x")
            (d / f"._SAY-{i:03d}.ARW").write_bytes(b"x")   # rác macOS
        (d / "SAY-001.xmp").write_text("<x/>", encoding="utf-8")

        cap, thieu = at.collect_pairs(d, False, need_sidecar=False)
        ktra("file “._…” của macOS KHÔNG bị tính là ảnh",
             len(cap) == 63, f"{len(cap)} ảnh (đúng phải là 63, không phải 126)")
        ktra("và cũng không lọt vào danh sách thiếu .xmp",
             not any(Path(p).name.startswith("._") for p, _ in cap))

        cap2, thieu2 = at.collect_pairs(d, False, need_sidecar=True)
        #[[ Day la con so nguoi dung gap: 63 anh ma chi ra 1. Khong phai loi —
        #   la che do .xmp chi nhan anh co sidecar. Bai nay chot hanh vi do de
        #   sau nay ai sua cung biet no la CO Y. ]]
        ktra("chế độ .xmp chỉ nhận ảnh CÓ sidecar",
             len(cap2) == 1 and len(thieu2) == 62,
             f"{len(cap2)} ghép được, {len(thieu2)} thiếu")

        #[[ Sidecar hoa thuong: tren o dia phan biet hoa thuong (Mac co the
        #   dinh dang APFS case-sensitive) thi ".XMP" phai van ghep duoc. ]]
        (d / "SAY-002.XMP").write_text("<x/>", encoding="utf-8")
        cap3, _ = at.collect_pairs(d, False, need_sidecar=True)
        ktra("sidecar viết HOA .XMP vẫn ghép được",
             len(cap3) == 2, f"{len(cap3)} ghép được")

    # ---- khớp đường dẫn giữa bản xuất Lightroom và file trên đĩa
    #[[ O dia mac dinh cua macOS (APFS, HFS+) KHONG phan biet hoa thuong, y het
    #   Windows. Nhung os.path.normcase() chi viet thuong tren Windows. Nen
    #   tren Mac, Lightroom bao ".../Anh/DSC01.ARW" con Python liet ke ra
    #   ".../anh/dsc01.arw" la hai chuoi khac nhau — va app bao "ban xuat chi
    #   khop 0 anh" tren mot ban xuat hoan toan dung. ]]
    import sys as _s
    that = _s.platform
    for he, phai_khop in (("darwin", True), ("win32", True), ("linux", False)):
        _s.platform = he
        a = at.khoa_duong_dan("/Users/x/Anh/DSC01.ARW")
        b = at.khoa_duong_dan("/Users/x/anh/dsc01.arw")
        ktra(f"{he}: hai cách viết hoa thường "
             + ("PHẢI khớp" if phai_khop else "KHÔNG được gộp"),
             (a == b) == phai_khop, f"{a}  vs  {b}")
    _s.platform = that

    #[[ Hai ben phai dung CHUNG mot ham chuan hoa. Mot ben viet thuong mot ben
    #   khong thi khop ra 0 ma khong ai hieu vi sao. ]]
    src_gui = (GOC / "autotone_gui.py").read_text(encoding="utf-8")
    ktra("giao diện đếm khớp bằng at.khoa_duong_dan()",
         "at.khoa_duong_dan(" in src_gui
         and "normcase(os.path.abspath(str(p))) in self.export" not in src_gui)

    # ---- ảnh đo hỏng phải ở lại trên màn hình
    #[[ 11/9: 64/64 do xong ma bang chi 1 anh. Hop thoai co bao, nhung bam OK
    #   la mat, va dong trang thai chi con "1 anh · 1 canh" — trong y het mot
    #   thu muc mot anh. Con so 63 anh hong phai o lai cho nguoi dung nhin. ]]
    import ast as _ast
    src_gui = (GOC / "autotone_gui.py").read_text(encoding="utf-8")
    cay = _ast.parse(src_gui)
    ten_ham = {h.name for h in _ast.walk(cay) if isinstance(h, _ast.FunctionDef)}
    ktra("giao diện giữ lại danh sách ảnh đo hỏng",
         "_do_hong" in src_gui and "_fill_table" in ten_ham)
    ktra("dòng trạng thái có nói số ảnh đo hỏng",
         "ĐO HỎNG" in src_gui, "không thì bảng ít ảnh mà không ai biết vì sao")

    # ---- freeze_support phải được gọi, nếu không .app tự nhân bản chính nó
    #[[ Tren macOS va Windows, multiprocessing khoi dong tien trinh con bang
    #   SPAWN — tien trinh con chay lai chinh file thuc thi. Trong mot goi
    #   PyInstaller ma thieu freeze_support() thi moi tien trinh con mo lai ca
    #   giao dien, va man hinh moc ra hang loat cua so. ]]
    import ast
    src = (GOC / "autotone_gui.py").read_text(encoding="utf-8")
    goi = [n for n in ast.walk(ast.parse(src))
           if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
           and n.func.attr == "freeze_support"]
    ktra("autotone_gui có gọi multiprocessing.freeze_support()", bool(goi),
         "thiếu thì gói .app tự nhân bản chính nó khi đo ảnh")

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
