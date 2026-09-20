"""Kiểm phần nối AutoTone ↔ tool retouch, lấy mốc theo saytool 0.9.5.

VÌ SAO CÓ FILE NÀY
    Bản 0.9.5 đổi ba thứ mà nếu app không theo kịp thì hỏng trong im lặng —
    ảnh vẫn ra đủ, nhìn qua vẫn đẹp, chỉ là sai:

      1. Thêm ba bước mới, mỗi bước một file mô hình riêng (xoá khuyết điểm cơ
         thể, nếp nhăn trán, tạo hình khuôn mặt). Bảng mô hình cũ của app chỉ
         biết hai file, nên báo "đủ" trong khi thiếu.
      2. Thiếu mô hình KHÔNG còn làm dừng cả mẻ nữa: saytool in "! BO QUA
         <tên>" rồi chạy tiếp. Không bắt dòng đó thì cả buổi giao khách thiếu
         một tính năng mà không ai biết.
      3. saytool tự dò cấu hình máy (phan_cung.so_luong / canh_o). Truyền
         --luong một con số là VÔ HIỆU HOÁ toàn bộ phần tự dò đó.

    Bài này KHÔNG cần cài saytool: nó dựng một gói giả đúng hình dạng 0.9.5 rồi
    chạy CHÍNH câu lệnh hỏi mà retouch.py dùng thật.

Chạy:  python3 kiem_retouch_095.py
"""
from __future__ import annotations

import ast
import os
import sys
import tempfile
from pathlib import Path

GOC = Path(__file__).resolve().parent
LOI: list[str] = []


def ktra(ten: str, dieu: bool, mo: str = "") -> None:
    if dieu:
        print(f"  {ten:<58} {mo or 'đạt'}")
    else:
        LOI.append(f"{ten}: {mo}")


#[[ Goi gia dung hinh dang 0.9.5: moi buoc tu khai mo_hinh cua no, va ten
#   THANH KEO khong nhat thiet trung ten BUOC (buoc "nhan" -> keo "nhan_tran").
#   Do la cai bay chinh ma bai nay canh. ]]
GOI_GIA = '''
class T:
    def __init__(s, ten, nhan, mac_dinh=0.0, goi_y=""):
        s.ten, s.nhan, s.mac_dinh, s.goi_y = ten, nhan, mac_dinh, goi_y


class B:
    theo_nhom = True
    ghi_chu_nhom = ""
    nhom_bo_qua = ()
    ca_khung = False

    def __init__(s, ten, nhan, keo, mo_hinh=None, **kw):
        s.ten, s.nhan, s.thanh_keo = ten, nhan, keo
        if mo_hinh:
            s.mo_hinh = mo_hinh
        for k, v in kw.items():
            setattr(s, k, v)


_DS = [
    B("vet", "Xoa khuyet diem", [T("vet", "Xoa khuyet diem", 100)],
      "mo_hinh/vet.pt"),
    B("vet_body", "Xoa khuyet diem co the",
      [T("vet_body", "Xoá khuyết điểm cơ thể", 0)], "mo_hinh/vet_body.pt"),
    B("nong_cam", "Xoa nong cam", [T("nong_cam", "Xoa nong cam", 0)],
      "mo_hinh/nong_cam.pt"),
    B("nhan", "Lam mo nep nhan tran", [T("nhan_tran", "Nep nhan tran", 0)],
      "mo_hinh/nhan.pt"),
    B("liquify", "Tao hinh khuon mat", [T("lq_thon_mat", "Lam thon mat", 0)]),
    B("toc", "Lap day diem hoi", [T("toc", "Lap day diem hoi", 0)],
      "mo_hinh/toc.pt", nhom_bo_qua=("nam", "nam_gia")),
    B("chan", "Keo dai chan", [T("chan", "Keo dai chan", 0)],
      theo_nhom=False, ca_khung=True,
      ghi_chu_nhom="Keo chan doi ca khung anh nen moi anh chi một mức"),
]


def tat_ca():
    return _DS


def moi_thanh_keo():
    return [(b, t) for b in _DS for t in b.thanh_keo]
'''

#[[ nhom_mat that cua saytool. Chep DUNG nam nhom va dung thu tu — bai kiem so
#   thang vao danh sach nay nen lech mot cai la bat duoc ngay. ]]
NHOM_GIA = '''
NHOM = [("nu", "Nữ"), ("nam", "Nam"), ("tre_con", "Trẻ con"),
        ("nu_gia", "Nữ lớn tuổi"), ("nam_gia", "Nam lớn tuổi")]
TEN_NHOM = [k for k, _ in NHOM]
NHAN_NHOM = dict(NHOM)
'''


def dung_goi_gia(d: Path) -> Path:
    (d / "saytool").mkdir(parents=True, exist_ok=True)
    (d / "saytool" / "__init__.py").write_text("", encoding="utf-8")
    (d / "saytool" / "buoc.py").write_text(GOI_GIA, encoding="utf-8")
    (d / "saytool" / "nhom_mat.py").write_text(NHOM_GIA, encoding="utf-8")
    (d / "saytool" / "cli.py").write_text("# gia\n", encoding="utf-8")
    return d


def main() -> int:
    tmp = tempfile.mkdtemp()
    os.environ["AUTOTONE_DATA"] = tmp
    sys.path.insert(0, str(GOC))
    import retouch as rt

    tool = dung_goi_gia(Path(tmp) / "tool")

    # ---------- hỏi thanh kéo + mô hình bằng CHÍNH câu lệnh thật
    ds, mh, tk, nhom = rt._hoi_keo(tool)
    ten_keo = [m[0] for m in ds]
    ktra("hỏi được đủ thanh kéo của 0.9.5", len(ds) == 7, " ".join(ten_keo))
    ktra("có thanh kéo xoá khuyết điểm cơ thể", "vet_body" in ten_keo)
    ktra("có thanh kéo nếp nhăn trán", "nhan_tran" in ten_keo)
    ktra("có thanh kéo tạo hình khuôn mặt", "lq_thon_mat" in ten_keo)

    ktra("hỏi được cả bảng mô hình", bool(mh), f"{len(mh)} thanh kéo")
    #[[ CAI BAY: buoc ten "nhan", thanh keo ten "nhan_tran". Bang mo hinh phai
    #   khoa theo TEN THANH KEO, vi 'muc' o giao dien khoa theo thanh keo. Sai
    #   cho nay thi mo_hinh_can() khong bao gio kiem toi nhan.pt. ]]
    ktra("bảng mô hình khoá theo TÊN THANH KÉO, không theo tên bước",
         mh.get("nhan_tran") == ["mo_hinh/nhan.pt"] and "nhan" not in mh,
         str(mh.get("nhan_tran")))
    ktra("bước không cần mô hình thì để rỗng, không bịa",
         mh.get("chan") == [] and mh.get("lq_thon_mat") == [])

    # ---------- thông tin nhóm khuôn mặt
    ktra("hỏi được cả năm nhóm khuôn mặt của saytool",
         [n[0] for n in nhom] == ["nu", "nam", "tre_con", "nu_gia", "nam_gia"],
         " ".join(n[0] for n in nhom))
    ktra("biết thanh kéo nào chia được theo nhóm",
         tk.get("vet", {}).get("nhom") is True
         and tk.get("chan", {}).get("nhom") is False,
         f'vet={tk.get("vet", {}).get("nhom")} · chan={tk.get("chan", {}).get("nhom")}')
    ktra("giữ được câu ghi chú riêng của bước",
         "một mức" in (tk.get("chan", {}).get("ghi_chu") or ""),
         (tk.get("chan", {}).get("ghi_chu") or "")[:40])
    #[[ Buoc "lap day diem hoi" chi chay voi anh nu; nhom_bo_qua noi ra dieu do
    #   va giao dien phai hien duoc, khong thi nguoi dung keo cho Nam mai ma
    #   khong hieu vi sao khong an. ]]
    ktra("giữ được danh sách nhóm bị bỏ qua",
         tk.get("toc", {}).get("bo_qua") == ["nam", "nam_gia"],
         str(tk.get("toc", {}).get("bo_qua")))

    #[[ theo_nhom() doc tu bo nho dem ma thanh_keo() nap — hoi thang _hoi_keo()
    #   khong nap vao do. Goi mot lan cho dung duong that. ]]
    rt.thanh_keo(tool, lam_lai=True)
    ktra("thanh kéo chia theo nhóm -> theo_nhom() trả True",
         rt.theo_nhom("vet", tool) and not rt.theo_nhom("chan", tool),
         f'vet={rt.theo_nhom("vet", tool)} · chan={rt.theo_nhom("chan", tool)}')
    #[[ Khong hoi duoc thi mac dinh CO chia — dung mac dinh cua chinh saytool
    #   (Buoc.theo_nhom = True o lop cha), khong phai doan bua. ]]
    ktra("chưa hỏi được thì mặc định là CÓ chia nhóm",
         rt.theo_nhom("keo_la_hoac", "/khong/co/dau"))

    # ---------- mức hiệu lực
    m = {"vet": 100, "nam:vet": 40}
    ktra("nhóm có mức riêng thì lấy mức riêng",
         rt.muc_hieu_luc(m, "vet", "nam") == 40)
    ktra("nhóm không đặt riêng thì lấy mức chung",
         rt.muc_hieu_luc(m, "vet", "nu") == 100)
    ktra("không nêu nhóm thì là mức chung",
         rt.muc_hieu_luc(m, "vet") == 100)
    ktra("mức riêng rỗng = quay về mức chung",
         rt.muc_hieu_luc({"vet": 100, "nam:vet": ""}, "vet", "nam") == 100)

    # ---------- BẢNG MÃ: lỗi thật đã xảy ra 9/9
    #[[ Tien trinh con no ngay o dong in ket qua:
    #     UnicodeEncodeError: 'charmap' codec can't encode character '\u1ebf'
    #   Chu 'ế' trong "Xoá khuyết điểm cơ thể". Tren Windows stdout cua tien
    #   trinh con lay ma trang he thong (cp1252), khong phai UTF-8.
    #
    #   Hau qua: app hien ba thanh keo du phong nhu the do la day du.
    #
    #   Ba bai duoi kiem ca hai lop chan, va lop nao cung phai tu du.
    #]]
    ktra("JSON gửi về phải thuần ASCII (đừng bỏ ensure_ascii)",
         "ensure_ascii=False" not in rt.MA_DO_KEO,
         "chữ tiếng Việt đi ra dạng \\uXXXX")

    #[[ Lop 1: chay CHINH cau lenh do voi stdout bi ep ve cp1252 — dung canh
    #   ngo cua may nguoi dung. Khong bao gio duoc no. ]]
    import subprocess
    r = subprocess.run([sys.executable, "-c", rt.MA_DO_KEO], cwd=str(tool),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace",
                       env=dict(os.environ, PYTHONIOENCODING="cp1252",
                                PYTHONUTF8="0"))
    ktra("stdout bị ép về cp1252 thì vẫn in ra được", r.returncode == 0,
         (r.stderr or "").strip().splitlines()[-1] if r.returncode else "mã 0")
    ktra("và vẫn đọc ra đủ thanh kéo",
         rt._MOC in (r.stdout or "") and "vet_body" in (r.stdout or ""))

    #[[ Lop 2: co bien moi truong thu dich o phia cha thi lenh hoi VAN phai
    #   chay — tuc ta phai TU dat env cho tien trinh con, khong ke thua bua. ]]
    cu_env = os.environ.get("PYTHONIOENCODING")
    os.environ["PYTHONIOENCODING"] = "cp1252"
    try:
        rt.quen_thanh_keo(tool)
        ds2, _mh2, _tk2, _n2 = rt._hoi_keo(tool)
        ktra("máy đặt sẵn PYTHONIOENCODING=cp1252 thì vẫn hỏi được",
             len(ds2) == 7, f"{len(ds2)} thanh kéo · {rt.loi_hoi_keo(tool)[:60]}")
    finally:
        if cu_env is None:
            os.environ.pop("PYTHONIOENCODING", None)
        else:
            os.environ["PYTHONIOENCODING"] = cu_env

    # ---------- nhãn tiếng Việt
    keo = rt.thanh_keo(tool, lam_lai=True)
    nhan = {k[0]: k[1] for k in keo}
    ktra("nhãn tiếng Việt cho bước mới",
         nhan.get("vet_body") == "Xoá khuyết điểm cơ thể"
         and nhan.get("nhan_tran") == "Làm mờ nếp nhăn trán",
         f'{nhan.get("vet_body")} · {nhan.get("nhan_tran")}')

    # ---------- mô hình còn thiếu
    (tool / "mo_hinh").mkdir(exist_ok=True)
    (tool / "mo_hinh" / "vet.pt").write_bytes(b"x")
    thieu = rt.mo_hinh_can(tool, {"vet": 100})
    ktra("bật mỗi xoá khuyết điểm, mô hình có sẵn -> không báo thiếu",
         thieu == [], str(thieu))

    thieu = rt.mo_hinh_can(tool, {"vet": 100, "vet_body": 100})
    ktra("bật thêm xoá khuyết điểm cơ thể -> BÁO thiếu vet_body.pt",
         [t["dich"] for t in thieu] == ["mo_hinh/vet_body.pt"], str(thieu))

    thieu = rt.mo_hinh_can(tool, {"nhan_tran": 60})
    ktra("bật nếp nhăn trán -> báo thiếu nhan.pt",
         [t["dich"] for t in thieu] == ["mo_hinh/nhan.pt"], str(thieu))

    ktra("thanh kéo để 0 thì không báo thiếu gì",
         rt.mo_hinh_can(tool, {"vet": 100, "vet_body": 0, "nhan_tran": 0}) == [])

    #[[ Canh vet_body.pt co vet_body_magimir.pt — hoc tren bo anh MagiMir ma
    #   nguoi dung da bo han. Chep no vao thay the la lang le giao mot ket qua
    #   KHAC HAN thu ho duyet. Tha bao thieu. ]]
    (tool / "mo_hinh" / "vet_body_magimir.pt").write_bytes(b"x")
    thieu = rt.mo_hinh_can(tool, {"vet_body": 100})
    ktra("KHÔNG lấy bản MagiMir thay cho vet_body.pt",
         thieu and thieu[0]["ung_vien"] == [],
         "người dùng đã bỏ hẳn bộ ảnh MagiMir")

    #[[ MUC CHUNG 0 MA NHOM DAT 60 THI BUOC VAN CHAY.
    #
    #   Chi nhin muc chung la bao "du mo hinh" trong khi thuc te thieu, roi
    #   saytool in "! BO QUA" giua chung va anh nam ra thieu mot tinh nang ma
    #   khong ai biet. ]]
    thieu = rt.mo_hinh_can(tool, {"vet_body": 0, "nam:vet_body": 60})
    ktra("mức chung 0 nhưng nhóm đặt riêng -> VẪN kiểm mô hình",
         [t["dich"] for t in thieu] == ["mo_hinh/vet_body.pt"], str(thieu))
    ktra("mọi mức đều 0, kể cả riêng -> không báo gì",
         rt.mo_hinh_can(tool, {"vet_body": 0, "nam:vet_body": 0}) == [])

    # ---------- ứng viên thật thì vẫn phải thấy
    (tool / "v14_out").mkdir(exist_ok=True)
    (tool / "v14_out" / "gpu_all.pt").write_bytes(b"x")
    (tool / "mo_hinh" / "vet.pt").unlink()
    thieu = rt.mo_hinh_can(tool, {"vet": 100})
    ktra("thiếu vet.pt thì chỉ ra được ứng viên có sẵn",
         thieu and thieu[0]["ung_vien"] == ["v14_out/gpu_all.pt"], str(thieu))

    # ---------- dòng lệnh
    c = rt.lenh(tool, "/vao", "/ra", {"vet": 100, "vet_body": 50})
    ktra("mặc định KHÔNG truyền --luong (để saytool tự dò máy)",
         "--luong" not in c, " ".join(c[-8:]))
    ktra("mặc định không truyền --che-do (saytool vốn auto)", "--che-do" not in c)
    ktra("truyền đúng mức từng thanh kéo",
         "--vet" in c and "--vet-body" in c and c[c.index("--vet-body") + 1] == "50",
         " ".join(c[-6:]))
    #[[ Gach duoi trong ten thanh keo phai thanh gach ngang: saytool khai
    #   --vet-body chu khong phai --vet_body, sai la argparse tu choi CA me. ]]
    ktra("tên thanh kéo đổi _ thành - đúng kiểu argparse", "--vet_body" not in c)

    c = rt.lenh(tool, "/vao", "/ra", {}, luong=4, che_do="tiet_kiem")
    ktra("ép số luồng thì có truyền --luong",
         "--luong" in c and c[c.index("--luong") + 1] == "4")
    ktra("chọn chế độ tiết kiệm thì có truyền --che-do",
         "--che-do" in c and c[c.index("--che-do") + 1] == "tiet_kiem")

    #[[ Muc cua thanh keo KHONG con ben kia nua thi khong duoc truyen: argparse
    #   bao "unrecognized arguments" va ca me anh khong chay. Muc cu con nam
    #   trong retouch.json mai mai nen chuyen nay se xay ra that. ]]
    c = rt.lenh(tool, "/vao", "/ra", {"vet": 100, "buoc_da_bi_go": 80})
    ktra("mức của thanh kéo đã bị gỡ thì KHÔNG truyền sang",
         "--buoc-da-bi-go" not in c and "--buoc_da_bi_go" not in c)

    #[[ MUC RIENG PHAI SANG DUOC DONG LENH. Thieu no thi nguoi dung dat rieng
    #   cho Nam xong bam Chay, va no chay y nhu khong dat gi. ]]
    c = rt.lenh(tool, "/vao", "/ra", {"vet": 100, "nam:vet": 40,
                                      "nu_gia:nhan_tran": 30})
    ktra("mức riêng đi ra thành --nhom", c.count("--nhom") == 2,
         " ".join(x for x in c if ":" in x))
    ktra("đúng dạng nhom:keo=so mà saytool đọc",
         "nam:vet=40" in c and "nu_gia:nhan-tran=30" in c,
         " ".join(x for x in c if ":" in x))
    #[[ Nhom la va thi bo: saytool tu choi ca me neu ten nhom sai. ]]
    c = rt.lenh(tool, "/vao", "/ra", {"vet": 100, "khonghe:vet": 40})
    ktra("nhóm không có thật thì KHÔNG gửi đi", "--nhom" not in c)
    #[[ Ban saytool cu khong biet --nhom. Khong ai dat muc rieng thi dong lenh
    #   phai y het truoc day, de ban cu van chay duoc. ]]
    c = rt.lenh(tool, "/vao", "/ra", {"vet": 100})
    ktra("không ai đặt mức riêng thì không có --nhom nào", "--nhom" not in c)

    # ---------- NHẬT KÝ PHẢI TỚI NƠI, KỂ CẢ KHI TOOL CHẾT NGANG
    #[[ 9/9: sau dong "$ ...saytool.cli chay ..." la mot dong trong, roi het.
    #   duong_ong.chay() in ba dong ngay truoc khi chay, va cu 10 anh mot dong
    #   tien do — khong dong nao toi noi.
    #
    #   stdout cua tien trinh con noi vao ONG chu khong phai man hinh, nen
    #   Python dem theo khoi 8 KB; chet ngang thi ca dem bay theo, mang theo
    #   dung dong noi vi sao chet.
    #
    #   Bai nay dung mot tien trinh con in vai dong roi os._exit() — chet han,
    #   khong flush. Dung canh ngo cua may nguoi dung.
    #]]
    import subprocess
    CON = ("import os\n"
           "print('  may: gia lap')\n"
           "print('  734 anh')\n"
           "os._exit(3)\n")

    def chay_thu(env):
        pr = subprocess.Popen([sys.executable, "-c", CON],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, bufsize=1, env=env)
        d = [l.rstrip() for l in pr.stdout]
        pr.wait()
        return d

    sach = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
    ktra("có ép PYTHONUNBUFFERED cho tiến trình con",
         rt.MOI_TRUONG_UTF8.get("PYTHONUNBUFFERED") == "1")
    ktra("không ép thì mất sạch nhật ký khi tool chết ngang",
         chay_thu(sach) == [], "đúng cái đã xảy ra 9/9")
    ktra("ép rồi thì nhật ký vẫn tới nơi",
         len(chay_thu(dict(sach, **rt.MOI_TRUONG_UTF8))) == 2,
         "2 dòng, kể cả khi os._exit không flush")

    # ---------- bước bị bỏ giữa chừng
    log = ["  140 anh",
           "  ! BO QUA Xoa khuyet diem co the: FileNotFoundError: mo_hinh/vet_body.pt",
           "  ! BO QUA Lam mo nep nhan tran: RuntimeError: het bo nho",
           "  10/140  0.42s/anh"]
    bo = rt.buoc_bi_bo(log)
    ktra("bắt được các bước bị bỏ giữa chừng", len(bo) == 2,
         " · ".join(t for t, _ in bo))
    ktra("giữ luôn lý do để còn biết đường sửa",
         "vet_body.pt" in bo[0][1], bo[0][1])
    ktra("dòng bình thường không bị nhận nhầm", rt.buoc_bi_bo(["  10/140"]) == [])

    # ---------- giao diện có nối đủ không
    src = (GOC / "autotone_gui.py").read_text(encoding="utf-8")
    cay = ast.parse(src)
    goi_chay = []
    for ham in ast.walk(cay):
        if not isinstance(ham, ast.FunctionDef):
            continue
        for n in ast.walk(ham):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "chay"):
                goi_chay.append({k.arg for k in n.keywords})
    ktra("giao diện có truyền che_do khi chạy retouch",
         any("che_do" in k for k in goi_chay), f"{len(goi_chay)} chỗ gọi")
    goi_bo = [h.name for h in ast.walk(cay) if isinstance(h, ast.FunctionDef)
              for n in ast.walk(h)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and n.func.attr == "buoc_bi_bo"]
    ktra("giao diện có bắt dòng “! BO QUA”", bool(goi_bo), " ".join(goi_bo))

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
