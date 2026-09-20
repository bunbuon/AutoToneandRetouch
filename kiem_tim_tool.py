"""Kiểm việc tìm tool retouch — canh đúng cái đã hỏng thật hôm 8/9.

CHUYỆN ĐÃ XẢY RA
    Người dùng chuyển dự án retouch từ F:\\ToolCloneEvoto sang
    F:\\Claude AI\\ToolCloneEvoto. retouch.json vẫn ghi đường dẫn cũ, và danh
    sách dò trong retouch.py không có chỗ nào trùng. Khâu Retouch báo "Không có
    thư mục" trên một cái máy mà tool vẫn chạy tốt mỗi ngày.

    Đó là kiểu hỏng tệ nhất trong dự án này: app im lặng, và lỗi trông như lỗi
    của người dùng.

BÀI NÀY CANH BA THỨ
    1. Tool nằm CẠNH dự án thì phải tìm ra — luật này sống sót qua mọi lần
       chuyển ổ, miễn hai thư mục còn là anh em.
    2. Đường dẫn đã ghi mà chết thì phải TỰ CHỮA: dò lại, ghi đè, và nhớ chỗ
       cũ để giao diện nói được "tool đã chuyển từ X sang Y".
    3. Đường dẫn đã ghi mà CÒN SỐNG thì phải thắng — người dùng tự chọn thư
       mục khác là có lý do, không được lặng lẽ đổi dưới tay họ.

Chạy:  python3 kiem_tim_tool.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

GOC = Path(__file__).resolve().parent
LOI: list[str] = []


def ktra(ten: str, dieu: bool, mo: str = "") -> None:
    if dieu:
        print(f"  {ten:<56} {mo or 'đạt'}")
    else:
        LOI.append(f"{ten}: {mo}")


def tao_tool(p: Path) -> Path:
    """Một thư mục trông đủ giống tool retouch để hop_le() nhận."""
    (p / "saytool").mkdir(parents=True, exist_ok=True)
    (p / "saytool" / "cli.py").write_text("# gia\n", encoding="utf-8")
    return p


def main() -> int:
    tmp = tempfile.mkdtemp()
    os.environ["AUTOTONE_DATA"] = tmp          # phải đặt TRƯỚC khi import
    sys.path.insert(0, str(GOC))
    import retouch as rt

    ds = rt.cho_hay_co()
    ktra("danh sách dò không có chỗ trùng",
         len({str(c).lower() for c in ds}) == len(ds), f"{len(ds)} chỗ")
    #[[ Luat "nam canh du an" phai duoc thu TRUOC cac o dia quen thuoc, khong
    #   thi mot thu muc cu con sot lai o F:\\ToolCloneEvoto se thang ban that. ]]
    canh = str(GOC.parent / rt.TEN_TOOL).lower()
    vi_tri = [i for i, c in enumerate(ds) if str(c).lower() == canh]
    ktra("chỗ “nằm cạnh dự án” được xếp đầu",
         vi_tri and vi_tri[0] <= 1, f"vị trí {vi_tri[0] if vi_tri else '?'}")
    ktra("có dò cả thư mục “Claude AI”",
         any("claude ai" in str(c).lower() for c in ds),
         "chỗ người dùng đang gom dự án")

    ktra("thư mục rỗng KHÔNG được coi là tool",
         not rt.hop_le(Path(tmp)), "phải có saytool/cli.py")
    ktra("None cũng không", not rt.hop_le(None))

    # ---- 1. đường dẫn đã ghi còn sống thì thắng
    that = tao_tool(Path(tmp) / "tool_that")
    khac = tao_tool(Path(tmp) / "tool_nguoi_dung_chon")
    rt.ghi_cau_hinh({"goc": str(khac)})
    ktra("đường dẫn người dùng tự chọn được tôn trọng",
         rt.tim_tool() == khac, str(rt.tim_tool()))

    # ---- 2. đường dẫn đã ghi bị chết -> tự chữa
    #[[ Ep cho ham do CHI thay mot cho duy nhat, de bai kiem khong phu thuoc
    #   vao may that co gi. Vá đúng hàm thật, không chép lại nó. ]]
    do_that = rt.cho_hay_co
    rt.cho_hay_co = lambda: [Path(tmp) / "khong_co_dau", that]
    try:
        rt.ghi_cau_hinh({"goc": str(Path(tmp) / "da_bi_xoa")})
        tim = rt.tim_tool()
        ktra("đường dẫn đã ghi bị chết -> dò lại ra chỗ mới",
             tim == that, str(tim))
        d = json.loads(rt.CAU_HINH.read_text(encoding="utf-8"))
        #[[ Khong ghi de thi lan sau van doc phai cai chet — dung cai da xay ra. ]]
        ktra("và GHI ĐÈ vào cấu hình, không để lần sau đọc lại chỗ chết",
             d.get("goc") == str(that), d.get("goc", ""))
        ktra("nhớ chỗ cũ để còn báo cho người dùng",
             d.get("goc_cu") == str(Path(tmp) / "da_bi_xoa"), d.get("goc_cu", ""))
        cu, moi = rt.da_chuyen_cho()
        ktra("da_chuyen_cho() trả đúng (cũ, mới)",
             cu == str(Path(tmp) / "da_bi_xoa") and moi == str(that))
        rt.quen_da_chuyen()
        ktra("báo một lần rồi quên, không nhắc mãi", rt.da_chuyen_cho() == ())

        #[[ Chua tung ghi gi ma do ra thi KHONG duoc bia ra mot lan "da chuyen":
        #   nguoi dung se di tim mot chuyen chua he xay ra. ]]
        rt.CAU_HINH.unlink(missing_ok=True)
        rt.tim_tool()
        ktra("lần đầu cài đặt thì không báo “đã chuyển chỗ”",
             rt.da_chuyen_cho() == ())
    finally:
        rt.cho_hay_co = do_that

    # ---- 3. không thấy đâu thì trả None, không nổ
    rt.cho_hay_co = lambda: [Path(tmp) / "khong_co_1", Path(tmp) / "khong_co_2"]
    try:
        rt.CAU_HINH.unlink(missing_ok=True)
        ktra("không thấy tool ở đâu -> None, không nổ", rt.tim_tool() is None)
    finally:
        rt.cho_hay_co = do_that

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
