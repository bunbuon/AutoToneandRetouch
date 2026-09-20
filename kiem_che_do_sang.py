"""Kiểm cách nhận ánh sáng ngày / ánh đèn: ba chế độ và ngưỡng EV100.

Chạy trên DỮ LIỆU THẬT khi có: trỏ vào một thư mục ảnh (JPEG đã export hoặc
RAW) thì in ra bảng EV100 / ISO của cả thư mục và cho thấy cùng một ISO ứng với
bao nhiêu mức sáng khác nhau.

    python kiem_che_do_sang.py                 # chỉ chạy phần kiểm logic
    python kiem_che_do_sang.py <thư mục ảnh>   # kiểm thêm trên ảnh thật
"""

from __future__ import annotations

import collections
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import autotone as at                                          # noqa: E402

LOI: list[str] = []


def ktra(ten: str, dieu: bool, mo: str = "") -> None:
    if dieu:
        print(f"  {ten:<54} {mo or 'đạt'}")
    else:
        LOI.append(f"{ten}: {mo}")


def anh(iso=None, toc=None, khau=None) -> dict:
    return {"iso": iso, "exposure_time": toc, "fnumber": khau}


def main() -> int:
    # ------------------------------------------------------------ 1. EV100
    #[[ Ba moc doi chieu, tinh tay tu cong thuc EV100 = log2(N^2/t) - log2(ISO/100).
    #   Sai cong thuc mot dau tru la moi nguong deu vo nghia ma khong ai thay. ]]
    ktra("EV100 f/2.8 · 1/160 · ISO 500",
         abs(at.ev100(anh(500, 1 / 160, 2.8)) - 7.97) < 0.02,
         f"{at.ev100(anh(500, 1 / 160, 2.8)):.2f}")
    ktra("EV100 f/4 · 1/250 · ISO 400",
         abs(at.ev100(anh(400, 1 / 250, 4.0)) - 9.97) < 0.02,
         f"{at.ev100(anh(400, 1 / 250, 4.0)):.2f}")
    ktra("EV100 f/16 · 1/125 · ISO 100 (nắng mở, quy tắc Sunny 16)",
         abs(at.ev100(anh(100, 1 / 125, 16.0)) - 15.0) < 0.05,
         f"{at.ev100(anh(100, 1 / 125, 16.0)):.2f} — phải ≈ 15")

    #[[ Tag EXIF hay ve duoi dang (tu, mau) hoac [(tu, mau)]. Khong ha duoc
    #   phan so thi ev100 tra ve None va CA TINH NANG lang le lui ve duong ISO. ]]
    ktra("đọc được tag dạng phân số (tử, mẫu)",
         at.ev100({"iso": [(500, 1)], "exposure_time": [(1, 160)],
                   "fnumber": [(28, 10)]}) is not None,
         "định dạng EXIF thật của Sony")

    for thieu in ("iso", "exposure_time", "fnumber"):
        r = anh(500, 1 / 160, 2.8)
        r[thieu] = None
        ktra(f"thiếu {thieu} -> None, không đoán bừa",
             at.ev100(r) is None, "để nơi gọi lùi về đường ISO")
    ktra("giá trị 0 hoặc rác -> None",
         at.ev100(anh(0, 1 / 160, 2.8)) is None
         and at.ev100(anh("x", "y", "z")) is None, "không nổ")

    # ------------------------------------------------------ 2. ba chế độ
    toi = anh(6400, 1 / 100, 2.8)      # hội trường đèn, EV100 ≈ 3.9
    sang = anh(100, 1 / 250, 8.0)      # trời mở, EV100 ≈ 14
    ktra("chế độ 'ngay' -> mọi ảnh là ánh sáng ngày",
         at.ngoai_troi(toi, {"che_do_sang": "ngay"}) is True,
         "kể cả ảnh tối thui — người dùng đã chốt")
    ktra("chế độ 'den' -> mọi ảnh là ánh đèn",
         at.ngoai_troi(sang, {"che_do_sang": "den"}) is False,
         "kể cả ảnh sáng trưng")

    cfg = {"che_do_sang": "tron", "ev_ngoai_troi": 8.5, "iso_ngoai_troi": 400}
    ktra("chế độ 'tron' tách đúng hai đầu",
         at.ngoai_troi(sang, cfg) is True and at.ngoai_troi(toi, cfg) is False,
         "EV100 14 -> ngày · EV100 3,9 -> đèn")

    #[[ DAY LA PHEP KIEM QUAN TRONG NHAT. Hai anh CUNG ISO 500 nhung lech 1
    #   stop anh sang that. Nguong ISO xep chung vao mot nhom; EV100 tach dung.
    #   Do tren anh that cua nguoi dung: SAY-Media-07207 va SAY-Media-03712. ]]
    a = anh(500, 1 / 160, 4.0)        # EV100 9.00 — dưới mái, ban ngày
    b = anh(500, 1 / 160, 2.8)        # EV100 7.97 — tối hơn 1 stop
    ktra("cùng ISO 500, EV100 tách được còn ISO thì không",
         at.ngoai_troi(a, cfg) is True and at.ngoai_troi(b, cfg) is False
         and at._ngoai_troi_theo_iso(a, cfg) == at._ngoai_troi_theo_iso(b, cfg),
         f"EV {at.ev100(a):.2f} vs {at.ev100(b):.2f} — ISO xếp chung một nhóm")

    # -------------------------------------------------- 3. đường dự phòng
    #[[ Thieu tag thi phai LUI VE ISO, khong duoc tra ve False luon — tra ve
    #   False la lang le xep het anh cu vao nhom anh den. ]]
    cu = {"iso": 200}                 # ảnh cũ, không có tốc/khẩu
    ktra("thiếu tag để tính EV100 -> lùi về ngưỡng ISO",
         at.ngoai_troi(cu, cfg) is True,
         "ISO 200 ≤ 400 nên vẫn là ánh sáng ngày")
    ktra("ảnh không có ISO lẫn EV100 -> ánh đèn (đoán an toàn)",
         at.ngoai_troi({}, cfg) is False,
         "sai về phía đèn thì chỉ là giữ nguyên cách cũ")

    ktra("ev_ngoai_troi = 0 thì bỏ EV100, dùng ISO",
         at.ngoai_troi(anh(200, 1 / 160, 2.8),
                       {"che_do_sang": "tron", "ev_ngoai_troi": 0,
                        "iso_ngoai_troi": 400}) is True,
         "van còn tắt được")
    ktra("tắt cả hai ngưỡng thì không phân loại gì",
         at.ngoai_troi(anh(100, 1 / 250, 8.0),
                       {"che_do_sang": "tron", "ev_ngoai_troi": 0,
                        "iso_ngoai_troi": 0}) is False,
         "mọi ảnh về chung một nhóm như trước")

    # ------------------------------------------------------ 4. mặc định
    d = at.DEFAULTS
    ktra("mặc định là 'tron' — không tự ý chốt hộ người dùng",
         d.get("che_do_sang") == "tron", d.get("che_do_sang"))
    #[[ 8.5 giu DUNG nhom anh ma mau dich ngoai troi da duoc duyet tren do
    #   (nhom ay chon bang ISO <= 400, ung voi EV100 >= 8,68 trong mau thuc). ]]
    ktra("ngưỡng EV100 nằm giữa nhà bạt ban ngày và hội trường đèn",
         6.5 < float(d.get("ev_ngoai_troi", 0)) < 10.0,
         f"ev_ngoai_troi = {d.get('ev_ngoai_troi')} "
         "(bạt ban ngày 7,6-10 · hội trường đèn 5-6,5)")

    # ------------------------------- 5. ô chọn phải NỐI được vào đường chạy
    #[[ Mot o chon khong noi vao read_cfg() la mot cai nut bam thay doi ma phan
    #   tich khong he doi — kieu hong im lang, chi lo ra khi ngoi so anh. ]]
    import ast
    goc = Path(__file__).resolve().parent
    gui = (goc / "autotone_gui.py").read_text(encoding="utf-8")
    cay = ast.parse(gui)
    lop = next((n for n in ast.walk(cay) if isinstance(n, ast.ClassDef)
                and any(isinstance(c, ast.FunctionDef) and c.name == "read_cfg"
                        for c in n.body)), None)
    ham = {c.name: c for c in lop.body
           if isinstance(c, ast.FunctionDef)} if lop else {}
    rc = ast.get_source_segment(gui, ham["read_cfg"]) if "read_cfg" in ham else ""
    ktra("read_cfg có truyền che_do_sang xuống autotone",
         "che_do_sang=self.v_che_do_sang.get()" in (rc or ""),
         "ô chọn nối thẳng vào cfg")
    ktra("có dựng ô chọn v_che_do_sang trong giao diện",
         "self.v_che_do_sang = tk.StringVar" in gui, "widget có thật")
    ktra("ba chế độ đều có mặt trong giao diện",
         all(f'rd("{m}"' in gui for m in ("tron", "ngay", "den")),
         "trộn / ngày / đèn")
    #[[ Doi o chon thi TINH LAI ke hoach, khong duoc vut ca luot do. ]]
    #[[ Doc theo LOI GOI THAT (nut Call trong AST), khong grep chu.
    #   Grep chu thi mot dong chu thich giai thich "khong duoc goi X" cung bi
    #   tinh la co goi X — bai kiem keu oan chinh cai chu thich noi dung. ]]
    fn = ham.get("_doi_che_do_sang")
    goi = set()
    if fn:
        for m in ast.walk(fn):
            if isinstance(m, ast.Call) and isinstance(m.func, ast.Attribute):
                goi.add(m.func.attr)
    ktra("đổi ô chọn thì tính lại, KHÔNG quét lại ảnh",
         "refresh_plan" in goi and "_invalidate_measurements" not in goi,
         f"gọi {sorted(goi) or '(không gọi gì)'} — "
         "không vứt lượt phân tích hàng chục phút")

    ktra("CLI có --anh-sang và --ev-ngoai-troi",
         at.build_parser().parse_args([".", "--anh-sang", "den"]).che_do_sang
         == "den", "chạy được từ dòng lệnh")

    # --------------------------------------------- 6. chạy trên ảnh thật
    if len(sys.argv) > 1:
        thu_muc = Path(sys.argv[1])
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS
        except ImportError:
            print("\n  (bỏ qua phần ảnh thật — chưa có Pillow)")
            Image = None
        if Image is not None:
            ds = sorted(list(thu_muc.glob("*.jpg")) + list(thu_muc.glob("*.JPG")))
            theo_iso = collections.defaultdict(list)
            n_ngay = n_den = 0
            for p in ds:
                try:
                    ex = Image.open(p).getexif()
                    sub = ex.get_ifd(0x8769)
                    dd = {TAGS.get(k, k): v
                          for k, v in list(ex.items()) + list(sub.items())}
                except Exception:                              # noqa: BLE001
                    continue
                r = {"iso": dd.get("ISOSpeedRatings")
                     or dd.get("PhotographicSensitivity"),
                     "exposure_time": dd.get("ExposureTime"),
                     "fnumber": dd.get("FNumber")}
                ev = at.ev100(r)
                if ev is None:
                    continue
                theo_iso[int(at._so(r["iso"]))].append(round(ev, 2))
                if at.ngoai_troi(r, cfg):
                    n_ngay += 1
                else:
                    n_den += 1
            if theo_iso:
                lech = max((max(v) - min(v)) for v in theo_iso.values())
                print(f"\n  Trên {n_ngay + n_den} ảnh thật ở {thu_muc}:")
                print(f"    ánh sáng ngày {n_ngay} · ánh đèn {n_den}")
                for iso in sorted(theo_iso):
                    v = theo_iso[iso]
                    if len(v) > 1 and max(v) - min(v) > 0.4:
                        print(f"    ISO {iso:>5}: EV100 {min(v):.2f} … {max(v):.2f}"
                              f"   (lệch {max(v) - min(v):.2f} stop)")
                ktra("trên ảnh thật, cùng ISO vẫn lệch > 0,5 stop",
                     lech > 0.5,
                     f"lệch tối đa {lech:.2f} stop — đây là lý do bỏ ISO")

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
