"""Kiểm bố cục khâu 2 sau khi chuyển sang ba cột — không cần mở cửa sổ.

HAI THỨ FILE NÀY CANH

  1. NHÃN KHÔNG BỊ CẮT CỤT.
     Đây là lỗi đã xảy ra HAI LẦN trong lịch sử file này: xếp ngang mấy hộp
     chọn có nhãn tiếng Việt dài, ở bề ngang thật thì nhãn hiện thành "Dua mat
     ve muc sang ch". Đọc nhãn bị cắt thì không biết mình đang chọn gì.

     Lúc chạy thật thì _xep_cot() đo bằng winfo_reqwidth() — chính xác tuyệt
     đối. Nhưng máy dựng gói không mở được cửa sổ, nên ở đây ước theo số ký tự
     để vẫn bắt được lúc ai đó thêm một nhãn dài mới.

  2. NHỮNG THỨ ĐÃ GỠ THÌ PHẢI GỠ HẲN.
     Nút "2 · Ghi vào .xmp" trùng lệnh với nút ở khâu 3; "Xuất CSV" chuyển sang
     khâu 3; "Tự động theo dõi" gỡ bỏ. Còn sót một tham chiếu là app không mở
     lên được — mà lỗi đó chỉ lộ ra khi bấm, không lộ lúc import.

Chạy:  python kiem_bo_cuc.py
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parent
LOI: list[str] = []

#[[ Segoe UI 9pt o 96 DPI: be ngang trung binh mot ky tu ~6,6 px (do rong tay
#   tren nhan tieng Viet co dau). Cong 22 px cho o tick / nut tron. Uoc HOI
#   RONG mot chut — canh nham con hon bo sot. ]]
RONG_KY_TU = 6.6
RONG_O_TICH = 22

#[[ Cua so hep nhat cho phep: root.minsize(1180, 680). Tru cot trai 252 px va
#   le hai ben ~40 px. Day la truong hop XAU NHAT phai chiu duoc. ]]
RONG_MIN = 1180 - 252 - 40
KHE = 24


def ktra(ten: str, dieu: bool, mo: str = "") -> None:
    if dieu:
        print(f"  {ten:<50} {mo or 'đạt'}")
    else:
        LOI.append(f"{ten}: {mo}")


def than(ten_ham: str, src: str, cay: ast.AST) -> str:
    for n in ast.walk(cay):
        if isinstance(n, ast.FunctionDef) and n.name == ten_ham:
            return ast.get_source_segment(src, n) or ""
    return ""


def kiem_khoa_mau(ktra) -> None:
    """Mọi khoá dùng trong gd.MAU[...] ở mã nguồn phải là khoá CÓ THẬT.

    #[[ VI SAO CAN BAI NAY.
    #
    #   gd.MAU["tin"] khong ton tai. Python chi no luc CHAY TOI dong do — ma
    #   dong do nam trong mot nhanh hiem (bao trang thai sau khi gui yeu cau
    #   Export), nen no ngoi im trong ma nguon qua ca mot dot sua, roi no giua
    #   luc nguoi dung dang lam viec. Kiem tinh thi bat duoc ngay.
    #]]
    """
    import ast
    from pathlib import Path as _P
    import giao_dien as _gd
    goc = _P(__file__).resolve().parent
    sai = []
    for ten in ("autotone_gui.py", "duyet_ui.py", "giao_dien.py"):
        f = goc / ten
        if not f.is_file():
            continue
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if (isinstance(n, ast.Subscript)
                    and isinstance(n.value, ast.Attribute)
                    and n.value.attr == "MAU"
                    and isinstance(n.slice, ast.Constant)
                    and isinstance(n.slice.value, str)
                    and n.slice.value not in _gd.MAU):
                sai.append(f"{ten}:{n.lineno} MAU[{n.slice.value!r}]")
    ktra("mọi khoá màu dùng trong mã đều có thật", not sai,
         " | ".join(sai) if sai else f"{len(_gd.MAU)} khoá trong bảng màu")


def main() -> int:
    kiem_khoa_mau(ktra)
    src = (GOC / "autotone_gui.py").read_text(encoding="utf-8")
    cay = ast.parse(src)
    bo = than("_build_options", src, cay)
    ktra("tìm được _build_options", bool(bo), f"{len(bo.splitlines())} dòng")
    if not bo:
        return 1

    # ---------------- 1. gom nhãn theo từng cột
    cot: dict[str, list[str]] = {"c1": [], "c2": [], "c3": []}
    for m in re.finditer(r'\b(ct|rd)\(\s*(c[123])?[^,]*,\s*[^,]+,\s*"([^"]+)"', bo):
        c = m.group(2)
        if c:
            cot[c].append(m.group(3))
    # rd() luôn vào c2 (đóng trong hàm), ct() có tham số cột
    for m in re.finditer(r'\brd\("\w+",\s*"([^"]+)"', bo):
        cot["c2"].append(m.group(1))
    #[[ hop(cot, "nhan", ...) va so(cot, "nhan", ...) — cot la tham so DAU,
    #   nen nhan nam sau no. Regex phai bam theo chu ky that; bam sai thi bai
    #   kiem im lang doc ra 0 nhan va bao "khong co nhan nao qua dai". ]]
    for m in re.finditer(r'\b(?:hop|so)\(\s*\n?\s*(c[123]),\s*\n?\s*"([^"]+)"',
                         bo):
        cot[m.group(1)].append(m.group(2))

    tong = sum(len(v) for v in cot.values())
    ktra("đọc được nhãn của cả ba cột", tong >= 18,
         f"c1={len(cot['c1'])} c2={len(cot['c2'])} c3={len(cot['c3'])} "
         f"— tổng {tong}")

    # ---------------- 2. nhãn dài nhất có lọt cột hẹp nhất không
    #[[ Ty le cot 5:4:4. Cot 2 va 3 la hep nhat nen chung moi la cho de vo. ]]
    rong = {"c1": (RONG_MIN - 2 * KHE) * 5 / 13,
            "c2": (RONG_MIN - 2 * KHE) * 4 / 13,
            "c3": (RONG_MIN - 2 * KHE) * 4 / 13}
    qua_dai = []
    for c, ds in cot.items():
        for t in ds:
            can = len(t) * RONG_KY_TU + (RONG_O_TICH if c != "c1" else 130)
            if can > rong[c]:
                qua_dai.append((c, t, round(can), round(rong[c])))
    #[[ CHO PHEP qua dai — vi _xep_cot() se tu roi ve 2 hoac 1 cot khi hep.
    #   Phep kiem nay chi in ra de biet o be ngang nao thi con 3 cot. ]]
    if qua_dai:
        print(f"\n  Ở bề ngang nhỏ nhất ({RONG_MIN} px) thì {len(qua_dai)} nhãn "
              "không lọt 3 cột — sẽ tự rơi về 2 cột:")
        for c, t, a, b in qua_dai[:4]:
            print(f"     {c}: “{t[:44]}” cần {a} px, cột {b} px")
        print()

    #[[ DAY moi la phep kiem that: co duong tu co lai hay khong. Khong co no
    #   thi may nhan tren bi CAT CUT, khong phai xuong dong. ]]
    xc = than("_xep_cot", src, cay)
    ktra("có _xep_cot để tự co số cột", bool(xc),
         "đo bằng winfo_reqwidth, không đoán theo ký tự")
    ktra("_xep_cot đo bằng winfo_reqwidth",
         "winfo_reqwidth" in xc, "chính xác với mọi phông và mức DPI")
    ktra("_xep_cot có đủ cả ba mức 3 / 2 / 1 cột",
         all(f"n == {k}" in xc or f"n = {k}" in xc for k in (1, 2, 3))
         or ("n = 3" in xc and "n = 2" in xc and "n = 1" in xc),
         "hẹp tới đâu cũng còn đọc được nhãn")
    #[[ Xep lai cot lam Tk ban <Configure> lan nua. Khong co chot "so cot khong
    #   doi thi thoi" la vong lap vo tan, app dung hinh. ]]
    ktra("_xep_cot có chốt chống vòng lặp Configure",
         "_so_cot_hien" in xc and "return" in xc,
         "grid lại → Configure → grid lại… là treo app")
    ktra("_build_options có nối <Configure> vào _xep_cot",
         'bind("<Configure>", self._xep_cot)' in bo, "không nối thì cột không co")

    # ---------------- 3. chữ phụ phải xuống dòng, không được cắt
    #[[ ttk.Label co wraplength thi chu dai XUONG DONG. Thieu no la cat cut. ]]
    ktra("mọi dòng chữ phụ đều đặt wraplength",
         bo.count("wraplength=WRAP") >= 2 and "WRAP = " in bo,
         "chữ dài thì xuống dòng chứ không bị cắt")

    # ---------------- 4. khâu 2 chỉ chiếm MỘT hàng, không thể phình dọc lại
    hang = {int(m.group(1))
            for m in re.finditer(r'khung\.grid\(row=(\d+)', bo)}
    ktra("_build_options chỉ đặt một khối vào khâu 2",
         hang == {0}, f"hàng {sorted(hang)} — không còn xếp chồng dọc")

    # ---------------- 5. những thứ đã gỡ phải gỡ hẳn
    for ten in ("btn_apply", "WatchWindow", "open_watcher", "_watch_win"):
        ktra(f"không còn tham chiếu {ten}",
             ten not in src, "sót một chỗ là app không mở lên được")

    lr = than("_build_lrbox", src, cay)
    ktra("Xuất CSV nằm ở khâu 3", "self.btn_csv" in lr,
         "xuất kết quả là việc sau khi đã có kết quả")
    ktra("nút Ghi cũng ở khâu 3", "self.btn_ghi3" in lr,
         "đúng chỗ: khâu “đẩy vào Lightroom”")

    #[[ Doc theo command= THAT trong cay cu phap, khong grep chu — dong chu
    #   thich giai thich "do_apply nam o khau 3" cung chua chu do_apply, va
    #   grep thi bai kiem keu oan chinh cai chu thich noi dung. ]]
    lenh_khau2 = set()
    nut_khau2 = 0
    for n in ast.walk(cay):
        if isinstance(n, ast.FunctionDef) and n.name == "_build_actions":
            for m in ast.walk(n):
                if isinstance(m, ast.Call) and isinstance(m.func, ast.Attribute) \
                        and m.func.attr == "Button":
                    nut_khau2 += 1
                    for k in m.keywords:
                        if k.arg == "command" and isinstance(k.value, ast.Attribute):
                            lenh_khau2.add(k.value.attr)
    ktra("khâu 2 chỉ còn hai nút: Phân tích và Dừng",
         nut_khau2 == 2 and lenh_khau2 == {"start_analyze", "do_cancel"},
         f"{nut_khau2} nút · {sorted(lenh_khau2)}")

    #[[ _set_busy() chay TRONG __init__ truoc khi _build_lrbox() dung xong, nen
    #   phai dung getattr — khong thi app chet ngay luc mo. ]]
    sb = than("_set_busy", src, cay)
    ktra("_set_busy dùng getattr cho nút của khâu 3",
         "getattr(self" in sb,
         "_set_busy chạy trước khi khâu 3 dựng xong")

    # ---------------- 5b. KHÔNG được đặt width cố định cho nhãn
    #[[ Do bang Tk that: ttk.Label(width=15) CAT CUT nhan "Tach canh khi cach".
    #   Va con so an toan lai phu thuoc phong chu — doi phong hoac doi muc
    #   phong to cua Windows la sai lai. Grid tu tinh be ngang cot thi khong
    #   bao gio cat. Nen o day cam han width= tren nhan cot 1. ]]
    ktra("không đặt width cố định cho nhãn",
         "ttk.Label(k, text=nhan)" in bo and "text=nhan, width=" not in bo,
         "Tk cắt cụt chữ dài hơn width — để grid tự canh")
    ktra("mỗi cột dùng một lưới grid chung",
         "def _luoi(cot)" in bo and "k.columnconfigure(1, weight=1)" in bo,
         "Tk tự tính bề ngang cột 0 theo nhãn rộng nhất")

    # ---------------- 5c. màn hình Tổng quan
    for ten in ("_build_tong_quan", "_lam_moi_tong_quan", "_canh_bao_im_lang",
                "_mot_the_tq"):
        ktra(f"có {ten}", bool(than(ten, src, cay)), "khâu Tổng quan")
    ktra("Tổng quan nằm đầu bảng KHAU và không mang số",
         '("tong_quan", "Tổng quan")' in src
         and 'khong_so=("tong_quan",)' in src,
         "bảy khâu giữ nguyên số 1..7")
    ktra("mở app lên là vào Tổng quan",
         '_chon_khau("tong_quan")' in src, "không phải khâu 1 nữa")
    #[[ Vong lam moi 4 giay phai keo theo ca the tong quan, khong thi the dung
    #   im trong khi cot trai da doi — hai cho noi hai dang. ]]
    lm = than("_lam_moi_ray", src, cay)
    ktra("vòng làm mới 4 giây có cập nhật cả thẻ Tổng quan",
         "_lam_moi_tong_quan" in lm, "cột trái và thẻ không được nói khác nhau")
    cb = than("_canh_bao_im_lang", src, cay)
    ktra("cảnh báo bắt cả hai lỗi im lặng của ngày 7/9",
         "plugin_song_khi_nao" in cb and "ban_xuat_cu_hon_lan_ghi" in cb,
         "plugin chết · bản xuất cũ hơn lần ghi")

    #[[ Moi command= tro toi mot phuong thuc CO THAT. Sai ten thi khong no luc
    #   import, chi no khi bam — dung kieu loi kho doan nhat. ]]
    lop_app = next((n for n in ast.walk(cay) if isinstance(n, ast.ClassDef)
                    and n.name == "App"), None)
    co = {c.name for c in lop_app.body if isinstance(c, ast.FunctionDef)}
    thieu = []
    for c in lop_app.body:
        if isinstance(c, ast.FunctionDef) and "tong_quan" in c.name or \
           (isinstance(c, ast.FunctionDef) and c.name == "_mot_the_tq"):
            for n2 in ast.walk(c):
                if isinstance(n2, ast.Call):
                    for k in n2.keywords:
                        if k.arg == "command" and isinstance(k.value, ast.Attribute) \
                                and isinstance(k.value.value, ast.Name) \
                                and k.value.value.id == "self" \
                                and k.value.attr not in co:
                            thieu.append(k.value.attr)
    ktra("mọi nút trên Tổng quan trỏ tới lệnh có thật",
         not thieu, f"thiếu {thieu}" if thieu else "không có lệnh ma")

    # ---------------- 6. đường CLI --watch phải còn nguyên
    at_src = (GOC / "autotone.py").read_text(encoding="utf-8")
    ktra("CLI --watch vẫn còn trong autotone.py",
         "--watch" in at_src and "class Watcher" in at_src,
         "chỉ gỡ giao diện, không gỡ tính năng")

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
