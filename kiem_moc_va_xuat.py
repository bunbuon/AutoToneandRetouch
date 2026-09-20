"""Kiểm hai lỗi đã gây hỏng thật ở buổi 2705 ngày 7/9.

  1. MỐC BỊ GHI ĐÈ -> LẦN CHẠY SAU CỘNG DỒN GẤP ĐÔI
     save_baseline() dựng lại cả file từ đúng ảnh của lượt chạy này rồi ghi đè,
     nên một lượt chạy nhỏ xoá sạch mốc của mọi ảnh khác. Lần chạy đầy đủ kế
     tiếp không còn mốc nên lấy giá trị catalog HIỆN TẠI (đã sửa rồi) làm mốc và
     cộng thêm một lần nữa. Đo trên máy: 1889/1890 ảnh bị ghi gấp đôi, tỷ lệ
     trung vị đúng 2.000.

  2. BẢN XUẤT CŨ HƠN LẦN GHI -> BỎ QUA GẦN HẾT BUỔI TRONG IM LẶNG
     Lightroom không chạy nên app dùng lại bản xuất cũ (11:02), cũ hơn job đã
     ghi lúc 11:04. Bước lọc "ảnh sửa tay" so nhầm và bỏ đúng 2032/2087 ảnh;
     55 ảnh còn lại đều ra ΔEV +0.00 nên khâu 3 không có gì để ghi.

Cả hai đều KHÔNG báo lỗi gì — đó là lý do phải có bài kiểm riêng.

Chạy:  python kiem_moc_va_xuat.py
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import autotone as at                                          # noqa: E402

LOI: list[str] = []


def ktra(ten: str, dieu: bool, mo: str = "") -> None:
    if dieu:
        print(f"  {ten:<52} {mo or 'đạt'}")
    else:
        LOI.append(f"{ten}: {mo}")


def main() -> int:
    san = Path(tempfile.mkdtemp(prefix="kiem_moc_"))
    buoi = san / "2705"
    buoi.mkdir()
    jobs = san / "jobs"
    jobs.mkdir()

    # ============================================================ 1. MỐC
    #[[ Dung lai dung chuoi su kien da xay ra: chay day du -> chay nho ->
    #   chay day du. Sau luot thu hai, moc cua nhung anh KHONG nam trong luot
    #   do phai con nguyen. ]]
    day_du = {f"{buoi}\\a{i}.arw": {"Exposure2012": "0.00"} for i in range(10)}
    at.save_baseline(buoi, day_du)
    ktra("lượt đầu ghi đủ mốc", len(at.load_baseline(buoi)) == 10,
         f"{len(at.load_baseline(buoi))} ảnh")

    nho = {f"{buoi}\\a0.arw": {"Exposure2012": "0.00"},
           f"{buoi}\\a1.arw": {"Exposure2012": "0.00"}}
    at.save_baseline(buoi, nho)
    con = at.load_baseline(buoi)
    ktra("lượt nhỏ KHÔNG xoá mốc của ảnh khác", len(con) == 10,
         f"còn {len(con)}/10 ảnh — mất mốc là lần sau cộng dồn gấp đôi")

    #[[ Moc CU phai thang. Neu de gia tri moi (da qua tay tool) de len thi
    #   dung bang mat moc: lan sau lai cong them mot lan nua. ]]
    de_len = {f"{buoi}\\a0.arw": {"Exposure2012": "0.90"}}
    at.save_baseline(buoi, de_len)
    ktra("mốc cũ luôn thắng, giá trị mới không đè lên",
         at.load_baseline(buoi)[
             at.os.path.normcase(at.os.path.abspath(f"{buoi}\\a0.arw"))
         ].get("Exposure2012") == "0.00",
         "mốc = giá trị TRƯỚC khi tool chạm vào")

    moi = {f"{buoi}\\b0.arw": {"Exposure2012": "0.30"}}
    at.save_baseline(buoi, moi)
    ktra("ảnh mới vẫn được thêm vào mốc",
         len(at.load_baseline(buoi)) == 11, f"{len(at.load_baseline(buoi))} ảnh")

    ktra("gop=False vẫn dựng lại mốc từ đầu khi cần",
         len(at.load_baseline(buoi)) == 11
         and (at.save_baseline(buoi, moi, gop=False) is not None)
         and len(at.load_baseline(buoi)) == 1,
         "đường thoát cho lúc thật sự muốn đặt lại mốc")

    # ====================================================== 2. BẢN XUẤT CŨ
    def cham(p: Path, tre: float):
        p.write_text("path\tExposure2012\n", encoding="utf-8")
        t = time.time() + tre
        at.os.utime(p, (t, t))

    ktra("chưa có file nào thì không kêu oan",
         at.ban_xuat_cu_hon_lan_ghi(buoi, jobs)[0] is False,
         "không có bản xuất / job nào")

    cham(jobs / "export_20260907_110210.tsv", -300)      # 11:02
    cham(jobs / "apply_20260907_110421_2705.done", 0)    # 11:04 — SAU
    cu, t_xuat, t_ghi = at.ban_xuat_cu_hon_lan_ghi(buoi, jobs)
    ktra("bắt được bản xuất cũ hơn lần ghi", cu is True,
         f"xuất {t_xuat:%H:%M:%S} < ghi {t_ghi:%H:%M:%S}")

    cham(jobs / "export_20260907_190000.tsv", 300)       # bản xuất mới hơn
    ktra("có bản xuất mới hơn thì không kêu nữa",
         at.ban_xuat_cu_hon_lan_ghi(buoi, jobs)[0] is False,
         "đúng thứ tự thì im lặng")

    #[[ Job KHOI PHUC khong duoc tinh la "lan tool ghi". No tra lai ban sua tay,
    #   nen catalog trung voi no la chuyen binh thuong. ]]
    #[[ Don sach san truoc, ke ca job apply cua phep kiem tren. Bo sot no thi
    #   phep kiem nay "dat" vi mot ly do khac han — bai kiem mu. ]]
    for p in list(jobs.glob("export_*.tsv")) + list(jobs.glob("apply_*")):
        p.unlink()
    cham(jobs / "export_20260907_110210.tsv", -300)
    cham(jobs / "apply_20260907_120000_khoiphuc_2705.done", 0)
    ktra("job khôi phục không bị tính là lần tool ghi",
         at.ban_xuat_cu_hon_lan_ghi(buoi, jobs)[0] is False,
         "chỉ đếm job apply thật")

    ktra("thư mục job không tồn tại thì không nổ",
         at.ban_xuat_cu_hon_lan_ghi(buoi, san / "khong_co") == (False, None, None),
         "chịu được")

    # ============================== 3. CHỐT PHẢI ĐƯỢC NỐI VÀO ĐƯỜNG CHẠY
    #[[ Ham dung ma khong ai goi thi vo dung. Day dung la kieu hong da gap
    #   ngay 6/9 theo chieu nguoc lai: bai kiem nhin vao ham, con duong chay
    #   that thi khong di qua no. Nen kiem ca day noi. ]]
    import ast
    goc = Path(__file__).resolve().parent
    cay = ast.parse((goc / "autotone.py").read_text(encoding="utf-8"))
    plan_fn = next((n for n in ast.walk(cay)
                    if isinstance(n, ast.FunctionDef) and n.name == "plan"), None)
    goi = {n.func.id for n in ast.walk(plan_fn) if isinstance(n, ast.Call)
           and isinstance(n.func, ast.Name)} if plan_fn else set()
    ktra("plan() thật sự gọi chốt bản xuất cũ",
         "ban_xuat_cu_hon_lan_ghi" in goi,
         "không gọi thì cả cái chốt là code chết")

    gui = (goc / "autotone_gui.py").read_text(encoding="utf-8")
    ktra("giao diện có đọc và hiện CANH_BAO_XUAT",
         "CANH_BAO_XUAT" in gui,
         "chốt tự tắt một bước lọc mà im lặng thì không ai biết")

    ws = (goc / "autotone.py").read_text(encoding="utf-8")
    ktra("write_sidecars vẫn gọi save_baseline (mốc được chốt khi ghi)",
         "save_baseline(root, base)" in ws, "đường chốt mốc còn nguyên")

    print()
    if LOI:
        for m in LOI:
            print("  [!] " + m)
        print(f"{len(LOI)} LỖI  (sân kiểm giữ lại ở {san})")
        return 1
    print("TẤT CẢ ĐẠT")
    import shutil
    shutil.rmtree(san, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
