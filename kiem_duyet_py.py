"""Kiểm phía Python của Duyệt nhanh: giao thức file và toán bố cục lưới.

Không cần Lightroom và không cần màn hình. Chỗ dễ sai nhất ở đây là giao thức
file — hai bên Lua/Python phải hiểu giống hệt nhau, lệch một chữ là im lặng
không chạy chứ không báo lỗi.

Chạy:  python kiem_duyet_py.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import duyet                                                    # noqa: E402

#[[ Toán bố cục lấy từ duyet.py chứ không từ duyet_ui.py.
#   duyet_ui.py import tkinter; bài kiểm này phải chạy được cả trên máy dựng
#   gói không có Tk. Phần dễ sai nhất của lưới lại thuần số học nên tách ra
#   được — xem ghi chú trong duyet_ui.py. ]]
ui = duyet

LOI: list[str] = []


def ktra(ten: str, dieu: bool, mo: str = "") -> None:
    if dieu:
        print(f"  {ten:<48} {mo or 'đạt'}")
    else:
        LOI.append(f"{ten}: {mo}")


def doc_kv(p: Path) -> dict:
    out = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip()
    return out


def main() -> int:
    san = Path(tempfile.mkdtemp(prefix="kiem_duyet_"))
    jobs = san / "jobs"
    jobs.mkdir(parents=True)
    anh = san / "anh"
    anh.mkdir()

    # ---------------------------------------------------------- 1. gửi yêu cầu
    req = duyet.yeu_cau(anh, dest=san / "ra", canh=1600, chat=70, lo=25,
                        bo_sao=1, gioi_han=20, job_dir=jobs)
    lines = req.read_text(encoding="utf-8").splitlines()
    ktra("dòng đầu là thư mục ảnh gốc",
         lines[0] == str(anh.resolve()), lines[0])
    kv = doc_kv(req)
    ktra("có đủ khoá plugin cần đọc",
         kv.get("canh") == "1600" and kv.get("chat") == "70"
         and kv.get("lo") == "25" and kv.get("bo_sao") == "1"
         and kv.get("gioi_han") == "20",
         ", ".join(f"{k}={v}" for k, v in kv.items() if k != lines[0]))
    ktra("tên file yêu cầu khớp phía Lua",
         req.name == "request_duyet.txt" and duyet.TEN_YEU_CAU == "request_duyet.txt",
         req.name)
    ktra("không còn file .part", not (jobs / "request_duyet.part").exists(),
         "ghi .part rồi đổi tên")
    ktra("dang_cho() thấy yêu cầu chưa nhận",
         duyet.dang_cho(job_dir=jobs), "đúng")

    #[[ Tiến trình CŨ phải bị xoá khi gửi yêu cầu mới. Không xoá thì mấy giây
    #   đầu app đọc phải trang_thai=xong của lần trước và tưởng xong ngay. ]]
    (jobs / duyet.TEN_TIEN_DO).write_text("trang_thai=xong\nxong=999\n",
                                          encoding="utf-8")
    (jobs / duyet.TEN_BANG).write_text("path\tjpg\ncu\tcu.jpg\n", encoding="utf-8")
    duyet.yeu_cau(anh, dest=san / "ra", job_dir=jobs)
    ktra("gửi yêu cầu mới thì xoá tiến trình cũ",
         duyet.tien_do(job_dir=jobs) == {} and duyet.bang_anh(job_dir=jobs) == [],
         "không đọc nhầm kết quả lần trước")

    # ------------------------------------------------------------ 2. đọc kết quả
    (jobs / duyet.TEN_TIEN_DO).write_text(
        "trang_thai=dang_chay\nxong=25\ntong=1030\nloi=0\n"
        f"thu_muc={san / 'ra'}\n", encoding="utf-8")
    td = duyet.tien_do(job_dir=jobs)
    ktra("đọc tiến trình, số ra số",
         td["trang_thai"] == "dang_chay" and td["xong"] == 25
         and td["tong"] == 1030 and isinstance(td["xong"], int),
         duyet.mo_ta(td))

    (jobs / duyet.TEN_BANG).write_text(
        "path\tjpg\n"
        f"{anh / 'A.ARW'}\t{san / 'ra' / 'a.jpg'}\n"
        "\n"                                    # dòng rỗng giữa chừng
        "thieu_cot\n"                           # dòng hỏng
        f"{anh / 'B.ARW'}\t{san / 'ra' / 'b.jpg'}\n", encoding="utf-8")
    cap = duyet.bang_anh(job_dir=jobs)
    ktra("bảng ảnh bỏ qua dòng rỗng và dòng hỏng",
         len(cap) == 2 and cap[0][0].endswith("A.ARW"), f"{len(cap)} cặp")

    ktra("chưa có file thì trả rỗng, không nổ",
         duyet.tien_do(job_dir=san / "khong_co") == {}
         and duyet.bang_anh(job_dir=san / "khong_co") == [],
         "chịu được thiếu file")

    # ---------------------------------------------------------- 2b. xin dừng
    duyet.dung(job_dir=jobs)
    ktra("đặt được cờ dừng",
         duyet.dang_xin_dung(job_dir=jobs)
         and (jobs / "request_duyet_dung.txt").exists(),
         "tên khớp phía Lua: request_duyet_dung.txt")
    #[[ Gửi yêu cầu mới PHẢI xoá cờ dừng cũ. Sót cờ thì lượt mới dừng ngay sau
    #   lô đầu mà không ai hiểu vì sao — kiểu hỏng rất khó đoán. ]]
    duyet.yeu_cau(anh, dest=san / "ra", job_dir=jobs)
    ktra("gửi yêu cầu mới thì xoá cờ dừng cũ",
         not duyet.dang_xin_dung(job_dir=jobs),
         "lượt mới không bị dừng oan")
    duyet.xoa_dung(job_dir=jobs)
    duyet.xoa_dung(job_dir=jobs)          # xoá hai lần không được nổ
    ktra("xoá cờ dừng khi không có cờ vẫn không nổ",
         not duyet.dang_xin_dung(job_dir=jobs), "chịu được")

    (jobs / duyet.TEN_TIEN_DO).write_text(
        "trang_thai=dung\nxong=50\ntong=50\nloi=0\n"
        "thong_bao=41 giay, 0.82 giay/anh\n", encoding="utf-8")
    mo = duyet.mo_ta(duyet.tien_do(job_dir=jobs))
    ktra("trạng thái 'dừng' được nói đúng, không báo là lỗi",
         "dừng" in mo.lower() and "0.82" in mo, mo)

    ktra("lượt chạy thử là 50 ảnh", duyet.GIOI_HAN_THU == 50,
         f"GIOI_HAN_THU = {duyet.GIOI_HAN_THU}")

    # ------------------------------------------------------------ 3. đánh dấu
    p = duyet.danh_dau([anh / "A.ARW", anh / "B.ARW"], "red", job_dir=jobs)
    body = p.read_text(encoding="utf-8").splitlines()
    ktra("file đánh dấu đúng tên và đúng cột",
         p.name == "request_danhdau.tsv" and body[0] == "path\tnhan\tsao"
         and body[1].endswith("\tred\t"), body[0])
    ktra("danh sách rỗng thì không ghi gì",
         duyet.danh_dau([], job_dir=jobs) is None, "trả về None")
    bat = False
    try:
        duyet.danh_dau([anh / "A.ARW"], "hong", job_dir=jobs)
    except ValueError:
        bat = True
    ktra("nhãn sai bị chặn ngay", bat, "ValueError")

    #[[ BO SUU TAP la duong chinh de tim lai anh can sua, khong phai nhan mau.
    #   Nhan mau loc duoc that nhung thanh loc hay bi an / dang "Filters Off",
    #   va no de len he thong nhan rieng cua nguoi dung. ]]
    bst = duyet.ten_bo_suu_tap("G:/2705")
    ktra("tên bộ sưu tập gắn với tên buổi",
         bst.endswith("2705") and "AutoTone" in bst, bst)
    ktra("không có tên buổi vẫn ra tên dùng được",
         duyet.ten_bo_suu_tap(None) == "AutoTone cần sửa",
         duyet.ten_bo_suu_tap(None))

    p2 = duyet.danh_dau([anh / "A.ARW"], "red", bo_suu_tap=bst, job_dir=jobs)
    d2 = p2.read_text(encoding="utf-8").splitlines()
    ktra("dòng # tuỳ chọn đứng TRƯỚC dòng tiêu đề cột",
         d2[0] == f"#bo_suu_tap={bst}" and d2[1] == "path\tnhan\tsao",
         d2[0])
    ktra("không truyền bộ sưu tập thì không có dòng #",
         duyet.danh_dau([anh / "A.ARW"], "red", job_dir=jobs)
         .read_text(encoding="utf-8").splitlines()[0] == "path\tnhan\tsao",
         "giữ nguyên định dạng cũ")
    p3 = duyet.danh_dau([anh / "A.ARW"], "red", sao=duyet.SAO_CAN_SUA,
                        bo_suu_tap=bst, job_dir=jobs)
    dong = p3.read_text(encoding="utf-8").splitlines()[2]
    ktra("ghi được cả nhãn và số sao trên một dòng",
         dong.endswith(f"\tred\t{duyet.SAO_CAN_SUA}"), dong.split("\t", 1)[1])
    #[[ 1 sao la ANH LOAI trong quy uoc buoi chup (pick_burst tu gan 1 sao, va
    #   anh 1 sao khong Export khong retouch). Gan 1 sao cho anh CAN SUA la vut
    #   chung di thay vi danh dau de sua. ]]
    ktra("số sao cho ảnh cần sửa không được là 1",
         duyet.SAO_CAN_SUA != 1 and 2 <= duyet.SAO_CAN_SUA <= 5,
         f"SAO_CAN_SUA = {duyet.SAO_CAN_SUA} (1 sao = ảnh loại)")

    ktra("nhan='none' được chấp nhận (chỉ gom, không đụng nhãn)",
         duyet.danh_dau([anh / "A.ARW"], "none", bo_suu_tap=bst,
                        job_dir=jobs) is not None,
         "người dùng có hệ thống nhãn riêng thì đừng đụng vào")

    # -------------------------------------------------------- 4. nhớ lựa chọn
    dest = san / "ra"
    dest.mkdir(exist_ok=True)
    duyet.luu_lua_chon(dest, {"x.ARW"}, {"x.ARW", "y.ARW"})
    can, soat = duyet.doc_lua_chon(dest)
    ktra("nhớ được tấm nào cần sửa, tấm nào đã soát",
         can == {"x.ARW"} and soat == {"x.ARW", "y.ARW"},
         f"cần sửa {sorted(can)}, đã soát {len(soat)}")
    ktra("thư mục chưa có gì thì trả rỗng",
         duyet.doc_lua_chon(san / "chua_co") == (set(), set()), "không nổ")

    # ------------------------------------------------------------- 5. ảnh nhỏ
    try:
        from PIL import Image
        goc = dest / "to.jpg"
        Image.new("RGB", (1600, 1067), (120, 90, 60)).save(goc, "JPEG")
        nho = duyet.anh_nho(goc, 240)
        with Image.open(nho) as im:
            co = im.size
        ktra("ảnh nhỏ lọt trong khung 240",
             nho is not None and max(co) == 240, f"{co[0]}x{co[1]}")
        t1 = nho.stat().st_mtime_ns
        nho2 = duyet.anh_nho(goc, 240)
        ktra("lần hai dùng lại bản đệm, không dựng lại",
             nho2 == nho and nho2.stat().st_mtime_ns == t1, "đệm trên đĩa")
    except ImportError:
        print("  (bỏ qua phần ảnh nhỏ — máy này chưa có Pillow)")
    ktra("file không tồn tại thì trả None, không nổ",
         duyet.anh_nho(dest / "khong_co.jpg") is None, "None")

    # -------------------------------------------------------- 6. toán bố cục
    ktra("số cột theo bề ngang",
         ui.so_cot(1280, 254) == 5 and ui.so_cot(10, 254) == 1,
         "cửa sổ hẹp bất thường vẫn >= 1 cột")

    lech = []
    for cot in (1, 3, 5, 7):
        for i in range(37):
            x, y = ui.vi_tri(i, cot)
            j = ui.chi_so_tai(x + 5, y + 5, cot, 37)
            if j != i:
                lech.append((cot, i, j))
    ktra("bấm vào ô nào ra đúng ô đó", not lech,
         f"đã thử {4 * 37} ô ở 4 bề ngang khác nhau")

    ktra("bấm ra ngoài lưới trả về None",
         ui.chi_so_tai(-5, 10, 5, 20) is None
         and ui.chi_so_tai(10, -5, 5, 20) is None
         and ui.chi_so_tai(5000, 10, 5, 20) is None
         and ui.chi_so_tai(5, 100000, 5, 20) is None,
         "không lấy nhầm ô")

    dau, cuoi = ui.khoang_hang(0, 800, 270, 2)
    ktra("khoảng hàng cần dựng không âm và có đệm",
         dau == 0 and cuoi >= 800 // 270, f"hàng {dau}..{cuoi}")
    dau2, _ = ui.khoang_hang(5400, 800, 270, 2)
    ktra("cuộn xuống thì cửa sổ dựng trượt theo",
         dau2 == 5400 // 270 - 2, f"bắt đầu từ hàng {dau2}")

    ktra("chiều cao tổng đủ cho hàng lẻ cuối",
         ui.tong_cao(11, 5, 270) == 3 * 270 and ui.tong_cao(0, 5, 270) == 270,
         "11 ảnh / 5 cột = 3 hàng")

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
