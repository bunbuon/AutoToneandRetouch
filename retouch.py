#!/usr/bin/env python3
"""Gọi tool retouch (SAY · chỉnh ảnh chân dung) từ AutoTone — chặng cuối đường ống.

ĐƯỜNG ỐNG MỘT BUỔI CHỤP
    chụp -> Lightroom -> AutoTone cân sáng -> Export -> RETOUCH -> thư mục giao

    Chặng này chạy SAU khi Lightroom export xong, không song song. Người dùng
    đã chốt vậy: chạy chồng lên nhau thì hai tiến trình tranh cùng một card đồ
    hoạ và cùng một ổ đĩa, tổng thời gian không giảm mà log thì rối.

GỌI GÌ
    <goc>\\.venv\\Scripts\\python.exe -m saytool.cli chay VAO RA --vet 100 ...

    KHONG goi chay.bat: file .bat co lenh `pause` khi khong co tham so, va no
    doi trang thai console (chcp 65001). Goi thang python cua .venv thi bat
    duoc stdout sach, dung duoc chung mot cach tren moi may.

BỎ QUA ẢNH ĐÃ LÀM — KHÔNG PHẢI VIỆC CỦA FILE NÀY
    duong_ong.chay() ben tool retouch da tu loc: `if not lam_lai: files = [p
    for p in files if not (ra / ten[p]).exists()]`. Nen dang dở rồi chạy lại là
    tự tiếp tục, không cần ta đếm hộ. File này chỉ ĐỌC lại con số đó để báo
    trước cho người dùng biết còn bao nhiêu tấm.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import duong_dan as dd

# Đuôi ảnh tool retouch nhận — lấy đúng bộ trong saytool/duong_ong.py
DUOI = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

#[[ THANH KEO: HOI saytool, KHONG GHI CUNG.
#
#   Ban truoc ghi cung ba thanh keo o day. Den khi ToolCloneEvoto len v0.6.1,
#   no co them buoc "liquify" sinh ra thanh keo lq_thon_mat (Lam thon mat) tu
#   mo_hinh/liquify/danh_muc.json — va AutoTone KHONG hien no ra, cung khong
#   truyen no vao dong lenh. Tinh nang moi nhat coi nhu khong ton tai.
#
#   Kieu hong nay khong bao gio bao loi: giao dien van chay, retouch van chay,
#   chi la thieu mot thanh keo ma khong ai biet la thieu.
#
#   saytool von da co so dang ky (buoc.moi_thanh_keo()) va chinh ghi chu ben do
#   viet "them mot buoc moi la giao dien co them thanh keo, khong phai sua mot
#   dong nao trong giao dien". Nen o day HOI no, chu khong chep lai danh sach.
#
#   THANH_KEO duoi day chi con la ban DU PHONG cho luc chua chon duoc thu muc
#   tool, hoac hoi that bai.
#]]
THANH_KEO = [
    ("vet", "Xoá khuyết điểm", 100.0, "Mụn, vết thâm, nốt ruồi nhỏ"),
    ("nong_cam", "Xoá nọng cằm", 0.0, "Làm sâu đường bóng dưới hàm cho gọn"),
    ("chan", "Kéo dài chân", 0.0, "Mức 100 = giãn thêm 14.5%. Cần ảnh toàn thân"),
]

#[[ saytool viet nhan KHONG DAU ("Xoa khuyet diem") vi no con chay o terminal.
#   Giao dien AutoTone hien duoc dau nen doi lai cho de doc. Ten nao khong co
#   trong bang thi lay thang nhan cua saytool — buoc moi ben kia van hien ra
#   ngay, chi la chua co dau cho toi khi them vao day.
#]]
NHAN_DEP = {
    "vet": ("Xoá khuyết điểm", "Mụn, vết thâm, nốt ruồi nhỏ trên mặt"),
    "vet_body": ("Xoá khuyết điểm cơ thể",
                 "Mụn, vết thâm, nốt ruồi trên tay, vai, ngực, cổ"),
    "nhan_tran": ("Làm mờ nếp nhăn trán",
                  "Nếp nhăn ngang trên trán. Nhẹ tay, không xoá phẳng"),
    "nong_cam": ("Xoá nọng cằm", "Làm sâu đường bóng dưới hàm cho gọn"),
    "chan": ("Kéo dài chân", "Mức 100 = giãn thêm 14.5%. Cần ảnh toàn thân"),
    #[[ Thanh keo cua buoc liquify sinh ra tu mo_hinh/liquify/danh_muc.json,
    #   nen ten cua chung phu thuoc file tren dia. Ghi san cai da co; cai moi
    #   xuat hien van hien ra ngay voi nhan cua saytool, chi la chua co dau. ]]
    "lq_thon_mat": ("Làm thon mặt", "Thu hẹp gò má và đường hàm"),
    "da_body": ("Đều màu da cơ thể", "Cân lại chỗ da đậm nhạt trên tay, vai, cổ"),
    "toc": ("Lấp đầy điểm hói", "Đang tạm dừng bên ToolCloneEvoto — xem GHI_CHU_TOC.md"),
}

#[[ Co cua rieng de chay saytool khi app da dong goi. Xem worker o autotone_gui.
#]]
CO_SAY_CHAY = "--say-chay"
CO_SAY_KEO = "--say-keo"
CO_SAY_KIEM = "--say-kiem"

_KEO_NHO: dict = {}
_MH_NHO: dict = {}          # thư mục tool -> {tên thanh kéo: [file mô hình]}
#[[ VI SAO PHAI GIU LY DO.
#
#   Hoi that bai thi ham tra ve bang du phong ba thanh keo cu, va giao dien
#   hien ba thanh keo do NHU THE DO LA DAY DU. Nguoi dung nhin thay mot app
#   binh thuong, khong bao loi gi, chi thieu mat ba tinh nang moi — va khong co
#   duong nao tu ho lan ra duoc.
#
#   Da xay ra that 9/9: ban saytool tren may la 0.9.5 co sau thanh keo, app hien
#   dung ba. Khong mot dong nao noi vi sao.
#]]
_LOI_KEO: dict = {}         # thư mục tool -> vì sao hỏi không được
_TK_NHO: dict = {}          # thư mục tool -> {tên kéo: {nhom, ghi_chu, bo_qua…}}
_NHOM_NHO: dict = {}        # thư mục tool -> [[mã nhóm, nhãn]]
_MOC = "@@KEO@@"

CAU_HINH = dd.du_lieu("retouch.json")

#[[ SO LUONG: 0 = DE saytool TU DO. Day la mot thay doi co CAN CU, khong phai
#   noi long cho de.
#
#   LICH SU. Do that 3/9, may 32 loi + RTX 3060 Ti 8 GB, 140 anh: khong truyen
#   --luong thi saytool cu lay min(12, ncpu-2) = 12, va 12 luong deu thay
#   _APP is None nen deu dung mot phien InsightFace rieng tren card 8 GB ->
#   OOM -> sap ngay o anh dau (ma 3221225477). Nen ta ep --luong 1.
#
#   TAI SAO GIO BO EP. Ban 0.9.5 sua tan goc ca hai nua cua van de:
#     * khoa quanh cho khoi tao mo hinh (da them 3/9, duoc nguoi dung dong y)
#       — 12 luong chi nap mot lan;
#     * saytool/phan_cung.so_luong() chan boi CA hai phia: so loi VA BO NHO CON
#       TRONG THAT (doc qua psutil / /proc/meminfo), roi canh_o() con chia tiep
#       theo VRAM con trong. Tuc chinh no do may truoc khi chon, viec ma app
#       nay dung o ngoai khong lam duoc.
#
#   VA EP 1 GIO CON PHAN TAC DUNG: phan_cung.so_luong() co nhanh
#   `if xin > 0: return min(xin, ...)` — truyen --luong 1 la VO HIEU HOA toan
#   bo phan tu do do. Giu con so cu la tu tay bop toc do bang mot con so do tu
#   thang 9 tren mot may khac.
#
#   Nguoi dung van ep duoc: dat so > 0 o o "So luong" trong giao dien.
#]]
LUONG_MAC_DINH = 0

#[[ CHE DO CHAY, tham so moi cua 0.9.5 (saytool/cli.py --che-do):
#     auto        tu do cau hinh may roi chon — nen dung
#     tiet_kiem   mot luong, o nho nhat; cho may yeu hoac khi con chay viec khac
#     nhanh       dam dung nhieu bo nho hon
#   Khong truyen thi saytool mac dinh "auto"; ta van truyen ro de doc log la
#   biet no chay che do nao.
#]]
CHE_DO = ("auto", "tiet_kiem", "nhanh")
CHE_DO_MAC_DINH = "auto"

#[[ Nhung cho hay thay tool retouch. Chi de DO cho lan dau; tim thay thi ghi
#   vao retouch.json de lan sau khong phai do nua.
#]]
#[[ Cho do tool retouch. Ba o dia dau chi co nghia tren Windows; tren macOS
#   Path("F:/...") khong bao gio ton tai nen chi ton mot lan kiem, khong hai.
#   Nhung neu chi de bay nhieu thi tren Mac chi con dung mot cho duy nhat la
#   ~/ToolCloneEvoto — them may cho nguoi dung Mac hay dat du an.
#]]
TEN_TOOL = "ToolCloneEvoto"


def cho_hay_co() -> list:
    r"""Những chỗ hay thấy tool retouch. Tính mỗi lần gọi, không đóng băng.

    #[[ VI SAO KHONG CON LA MOT DANH SACH VIET CUNG.
    #
    #   8/9: nguoi dung chuyen du an tu F:\ToolCloneEvoto sang
    #   F:\Claude AI\ToolCloneEvoto. Danh sach cu khong co cho nao trung, va
    #   retouch.json van ghi duong dan cu. Ket qua: khau Retouch bao "Khong co
    #   thu muc" tren mot cai may ma tool van chay tot moi ngay — dung kieu
    #   hong "im lang, do loi cho nguoi dung" da chua o cho khac.
    #
    #   Nen doi cach do: luat manh nhat la TOOL NAM CANH CHINH DU AN NAY. Hai
    #   thu muc la anh em ruot ca truoc lan sau khi chuyen, va se con dung neu
    #   nguoi dung chuyen ca cum sang o khac. Do theo luat do truoc, roi moi do
    #   theo cac o dia quen thuoc.
    #]]
    """
    ra = []
    #[[ Anh em cua thu muc du an, va anh em cua thu muc CHA no — bat duoc ca
    #   "F:/Claude AI/{AutoToneImages,ToolCloneEvoto}" lan "F:/{...}". ]]
    try:
        minh = Path(__file__).resolve().parent
        for canh in (minh.parent, minh.parent.parent):
            ra.append(canh / TEN_TOOL)
    except (OSError, ValueError):
        pass
    for o in ("F:", "D:", "C:", "E:", "G:"):
        ra.append(Path(o + "/" + TEN_TOOL))
        #[[ "Claude AI" la thu muc nguoi dung dang gom cac du an lai. ]]
        ra.append(Path(o + "/Claude AI/" + TEN_TOOL))
    ra += [
        Path.home() / TEN_TOOL,
        Path.home() / "Documents" / TEN_TOOL,
        Path.home() / "Developer" / TEN_TOOL,
        Path.home() / "Desktop" / TEN_TOOL,
        Path("/Volumes/Data") / TEN_TOOL,
    ]
    #[[ Bo trung ma GIU THU TU: luat "nam canh du an" phai duoc thu truoc. ]]
    thay, sach = set(), []
    for c in ra:
        k = str(c).lower()
        if k not in thay:
            thay.add(k)
            sach.append(c)
    return sach


#[[ Giu ten cu de cho nao con goi thi van chay. Doc mot lan luc nap module. ]]
CHO_HAY_CO = cho_hay_co()


def python_venv(goc: Path) -> Path:
    return Path(goc) / (".venv/Scripts/python.exe" if os.name == "nt"
                        else ".venv/bin/python")


def python_cho(goc) -> str:
    """Python nào chạy được saytool — venv nếu có, không thì python đang chạy.

    VÌ SAO KHÔNG BẮT BUỘC PHẢI CÓ .venv
        chay.bat của tool retouch đòi .venv, nhưng đó chỉ là cách đóng gói mới.
        Trên máy thật (3/9) KHÔNG hề có .venv, và mọi batch file người dùng vẫn
        dùng hằng ngày đều gọi python hệ thống thẳng:
            python giao_dien.py ...
            python xoa_vet_batch.py ...
        tức torch, cv2, mediapipe đã nằm sẵn ở python hệ thống.

        Bản trước tôi lấy "có .venv" làm điều kiện để coi là ĐÃ CÀI. Sai: nó
        báo "tool có ở đó nhưng CHƯA CÀI" trên một cái máy mà tool vẫn chạy
        tốt mỗi ngày, và bắt người dùng đi cài lại một thứ không thiếu.

        saytool là một thư mục gói ngay trong thư mục tool, nên chạy với
        cwd = thư mục đó thì `python -m saytool.cli` import được, không cần
        pip install gì thêm.
    """
    v = python_venv(goc)
    if v.is_file():
        return str(v)
    #[[ Tranh pythonw.exe khi co the.
    #
    #   Giao dien AutoTone thuong duoc mo bang pythonw.exe (khong hien cua so
    #   console), nen sys.executable tra ve pythonw.exe. Chay tien trinh con
    #   bang no VAN bat duoc log vi ta cap san ong dan — da thay that o lan
    #   chay 3/9, vet stack hien day du trong o Nhat ky.
    #
    #   Nhung pythonw la ban dung de KHONG co console: mot so thu vien doc
    #   sys.stdout luc khoi dong va thay None thi xu ly khac di. python.exe nam
    #   ngay canh no va khong co nhuoc diem gi o day, nen uu tien dung.
    #]]
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        canh = exe.with_name("python.exe")
        if canh.is_file():
            return str(canh)
    return sys.executable


def trong_goi() -> bool:
    return bool(getattr(sys, "frozen", False))


def goc_trong_goi():
    """Thư mục tài nguyên có sẵn saytool + mo_hinh, khi app chạy từ gói.

    #[[ Ban all-in-one mang theo ca saytool lan mo_hinh. Luc do KHONG co .venv
    #   va cung khong chay duoc `python -m saytool.cli`, vi sys.executable la
    #   chinh file app da dong goi chu khong phai mot trinh thong dich.
    #]]
    """
    if not trong_goi():
        return None
    p = dd.goc_tai_nguyen()
    return p if (Path(p) / "saytool" / "cli.py").is_file() else None


def la_goc_trong_goi(goc) -> bool:
    g = goc_trong_goi()
    if g is None or not goc:
        return False
    try:
        return Path(goc).resolve() == Path(g).resolve()
    except OSError:
        return False


def lenh_saytool(goc, tham: list) -> list:
    """Dòng lệnh chạy saytool.cli với tham số cho trước.

    Hai đường khác hẳn nhau nên tách rõ ở đây, thay vì rải if khắp nơi:
      - chạy từ mã nguồn: python của tool  ->  -m saytool.cli ...
      - chạy từ gói:      chính file app   ->  --say-chay ...
    """
    if la_goc_trong_goi(goc):
        return [sys.executable, CO_SAY_CHAY] + [str(x) for x in tham]
    return [python_cho(goc), "-m", "saytool.cli"] + [str(x) for x in tham]


#[[ HOI CA MO HINH, KHONG CHI THANH KEO.
#
#   Ban 0.9.5 them ba buoc moi (xoa khuyet diem co the, nep nhan tran, tao hinh
#   khuon mat), moi buoc mot file mo hinh rieng. Bang MO_HINH viet cung o duoi
#   khong biet ba file do, nen mo_hinh_can() bao "du" trong khi thuc te thieu.
#
#   Va tu 0.9.5, thieu mo hinh KHONG con lam dung ca me nua — duong_ong.chay()
#   bat loi rieng tung buoc: "! BO QUA <nhan>: FileNotFoundError". Nghia la anh
#   van ra du, chi thieu mot tinh nang, va nguoi dung khong he biet. Kieu hong
#   im lang do lam viec kiem TRUOC khi chay quan trong hon han truoc day.
#
#   Nen hoi thang saytool: moi buoc tu khai file no can o thuoc tinh mo_hinh /
#   mo_hinh_mn. Them buoc moi ben kia la ben nay biet ngay, khong phai sua bang.
#]]
MA_DO_KEO = (
    "import json,sys\n"
    "from saytool.buoc import tat_ca, moi_thanh_keo\n"
    "try:\n"
    "    from saytool.nhom_mat import NHOM\n"
    "except Exception:\n"
    "    NHOM=[]\n"
    "ds=[[t.ten,t.nhan,float(t.mac_dinh),t.goi_y] for _b,t in moi_thanh_keo()]\n"
    "mh={}; tk={}\n"
    "for b in tat_ca():\n"
    "    f=[]\n"
    "    for a in ('mo_hinh','mo_hinh_mn'):\n"
    "        v=getattr(b,a,None)\n"
    "        if isinstance(v,str) and v: f.append(v)\n"
    "    for t in b.thanh_keo:\n"
    "        mh[t.ten]=list(f)\n"
    "        tk[t.ten]={'nhom':bool(getattr(b,'theo_nhom',False)),\n"
    "                   'ghi_chu':str(getattr(b,'ghi_chu_nhom','') or ''),\n"
    "                   'bo_qua':list(getattr(b,'nhom_bo_qua',()) or ()),\n"
    "                   'ca_khung':bool(getattr(b,'ca_khung',False)),\n"
    "                   'buoc':str(getattr(b,'nhan','') or '')}\n"
    #[[ ensure_ascii=True (mac dinh) LA CO Y, DUNG BO DI.
    #
    #   9/9: tien trinh con no ngay o dong nay:
    #       UnicodeEncodeError: 'charmap' codec can't encode character
    #       '\\u1ebf' in position 107   (cp1252.py)
    #   Chu 'ế' trong "Xoá khuyết điểm cơ thể" — nhan tieng Viet cua chinh ban
    #   0.9.5. Tren Windows, stdout cua tien trinh con lay ma trang he thong
    #   (cp1252) chu khong phai UTF-8, nen in mot chu tieng Viet la chet.
    #
    #   Hau qua nhin tu ngoai: app hien ba thanh keo du phong nhu the do la day
    #   du. Mat hai luot moi lan ra, vi khong ai in ly do ra ca.
    #
    #   ensure_ascii bien moi chu tieng Viet thanh \\uXXXX — thuan ASCII, ma
    #   trang nao cung in duoc. json.loads() ben nay tu doi nguoc lai. Sua o
    #   day la sua tan goc: khong phu thuoc vao viec truyen bien moi truong co
    #   toi noi hay khong.
    #]]
    "sys.stdout.write('" + _MOC +
    "'+json.dumps([ds,mh,tk,[list(x) for x in NHOM]]))\n"
)

#[[ VA VAN EP UTF-8 CHO TIEN TRINH CON.
#
#   Hai lop, co chu y. ensure_ascii lo phan JSON cua ta; con tat_ca() ben
#   saytool cung in ra "! khong nap duoc <buoc>: <loi>" — chuoi do la cua ho,
#   co the co tieng Viet, va no in TRUOC moc. Chet o do thi ta mat luon ca cau
#   giai thich vi sao mot buoc hong.
#
#   PYTHONIOENCODING doi ma trang cua stdout; PYTHONUTF8=1 bat che do UTF-8 cua
#   Python 3.7+ cho ca cho khac. Cung cap doi da dung o chay().
#]]
#[[ VA PYTHONUNBUFFERED=1 — do duoc, khong phai cho chac.
#
#   9/9, man hinh nguoi dung: sau dong "$ ...python.exe -m saytool.cli chay ..."
#   la MOT DONG TRONG, roi het. Trong khi duong_ong.chay() in ra ba dong ngay
#   truoc khi bat dau (cau hinh may, so anh, danh sach buoc) va cu 10 anh lai
#   in mot dong tien do. Khong dong nao toi noi.
#
#   Ly do: stdout cua tien trinh con noi vao mot ONG chu khong phai man hinh,
#   nen Python dem theo KHOI 8 KB. Ba dong dau nam trong dem; tien trinh chet
#   ngang (khong flush) thi ca dem bay theo. Do that trong container nay:
#
#       env sach                 ma=3  0 dong
#       env sach + UNBUFFERED    ma=3  2 dong   (den ngay tu +0,01s)
#
#   Dung con so 0 dong do: khong phai "tool im lang", ma la ta da lam mat loi.
#   Va vi loi thuong nam o dong CUOI truoc khi chet, day chinh la dong bi mat.
#]]
MOI_TRUONG_UTF8 = {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1",
                   "PYTHONUNBUFFERED": "1"}


def _hoi_keo(goc):
    """Hỏi saytool đang có những thanh kéo nào. -> (thanh_kéo, mô_hình).

    Hỏng ở đâu thì GHI LẠI vì sao vào _LOI_KEO — xem ghi chú ở đó.
    """
    khoa_loi = str(goc)
    _LOI_KEO.pop(khoa_loi, None)
    if la_goc_trong_goi(goc):
        cmd = [sys.executable, CO_SAY_KEO]
    else:
        cmd = [python_cho(goc), "-c", MA_DO_KEO]
    try:
        #[[ 180 giay: buoc_vet va buoc_nong_cam import torch ngay o dau file,
        #   ma lan dau nap torch tren o cung cham co the ton hon mot phut.
        #]]
        p = subprocess.run(cmd, cwd=str(goc), capture_output=True, text=True,
                           timeout=180, encoding="utf-8", errors="replace",
                           env=dict(os.environ, **MOI_TRUONG_UTF8),
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        _LOI_KEO[khoa_loi] = ("Hỏi quá 180 giây không xong. Máy đang bận, hoặc "
                              "lần đầu nạp torch trên ổ chậm.")
        return [], {}, {}, []
    except OSError as ex:
        _LOI_KEO[khoa_loi] = f"Không chạy được python của tool: {ex}"
        return [], {}, {}, []
    #[[ tat_ca() in ra dong "! khong nap duoc ..." khi mot buoc hong. Nen KHONG
    #   duoc coi ca stdout la JSON — phai cat tu dau moc.
    #]]
    out = p.stdout or ""
    ca = (out + "\n" + (p.stderr or "")).strip()
    i = out.find(_MOC)
    if i < 0:
        #[[ Day la duong hong hay gap nhat: python chay duoc nhung import mot
        #   buoc nao do that bai (thieu mediapipe / insightface / onnxruntime),
        #   nen tat_ca() tra ve rong hoac ca script no truoc khi in moc.
        #   Dua NGUYEN van ra ngoai — cat bot la mat dung dong noi vi sao. ]]
        _LOI_KEO[khoa_loi] = (f"saytool không trả về danh sách (mã thoát "
                              f"{p.returncode}).\n{ca[-1500:]}")
        return [], {}, {}, []
    try:
        d = json.loads(out[i + len(_MOC):].strip())
    except ValueError:
        _LOI_KEO[khoa_loi] = f"Đọc không ra JSON:\n{ca[-1500:]}"
        return [], {}, {}, []
    #[[ NHAN MOI HINH DANG DA TUNG TRA VE, tu cu toi moi:
    #     [ds]                   ban dau
    #     [ds, mh]               them bang mo hinh
    #     [ds, mh, tk, nhom]     them thong tin nhom (ban nay)
    #   Nguoi dung co the con saytool cu tren mot may khac; bo mat hinh dang cu
    #   la bat ho nang cap chi de mo duoc giao dien. ]]
    ds, mh, tk, nhom = [], {}, {}, []
    if isinstance(d, list) and d and isinstance(d[0], list):
        ds = d[0]
        if len(d) > 1 and isinstance(d[1], dict):
            mh = d[1]
        if len(d) > 2 and isinstance(d[2], dict):
            tk = d[2]
        if len(d) > 3 and isinstance(d[3], list):
            nhom = [x for x in d[3] if isinstance(x, list) and len(x) == 2]
        #[[ Mot mang thanh keo tran (hinh dang dau tien) cung khop nhanh tren,
        #   vi phan tu dau cua no cung la mot list. Phan biet bang: phan tu dau
        #   cua HINH DANG CU la [ten, nhan, so, goi] — tuc phan tu thu hai la
        #   chuoi, chu khong phai dict. ]]
        if not mh and not tk and len(d) > 1 and not isinstance(d[1], (dict, list)):
            ds = d
    elif isinstance(d, list):
        ds = d
    #[[ Chay duoc nhung KHONG buoc nao nap noi cung phai bao: luc do ds rong,
    #   va neu im lang thi giao dien hien ba thanh keo du phong nhu that. ]]
    if not ds:
        _LOI_KEO[khoa_loi] = (f"saytool chạy được nhưng KHÔNG bước nào nạp "
                              f"được.\n{ca[-1500:]}")
    return ds, mh, tk, nhom


def thanh_keo(goc=None, lam_lai: bool = False) -> list:
    """Thanh kéo saytool ĐANG có, dạng (tên, nhãn, mặc định, gợi ý).

    Hỏi một lần rồi nhớ, vì mỗi lần hỏi là một lần nạp torch.
    """
    goc = goc or tim_tool()
    if not hop_le(goc):
        return list(THANH_KEO)
    try:
        khoa = str(Path(goc).resolve())
    except OSError:
        khoa = str(goc)
    if not lam_lai and khoa in _KEO_NHO:
        return _KEO_NHO[khoa]
    ds, mh, tk, nhom = _hoi_keo(goc)
    _MH_NHO[khoa] = mh
    _TK_NHO[khoa] = tk
    if nhom:
        _NHOM_NHO[khoa] = nhom
    _LOI_KEO[khoa] = _LOI_KEO.get(str(goc), "")
    if not ds:
        #[[ KHONG nho ket qua rong: hoi that bai co the chi vi may dang ban,
        #   lan sau hoi lai co khi duoc. Nho lai thi bang keo thieu vinh vien.
        #]]
        return list(THANH_KEO)
    ra = []
    for m in ds:
        try:
            ten, nhan, md, goi = m[0], m[1], float(m[2]), m[3]
        except (IndexError, TypeError, ValueError):
            continue
        n2, g2 = NHAN_DEP.get(ten, (nhan, goi))
        ra.append((ten, n2, md, g2))
    if not ra:
        return list(THANH_KEO)
    _KEO_NHO[khoa] = ra
    return ra


#[[ NHOM KHUON MAT — vi sao AutoTone phai biet den chung.
#
#   Evoto khong de mot bo thanh keo cho ca buc anh: no chia Nu / Nam / Tre con
#   / Nu lon tuoi / Nam lon tuoi, moi nhom mot bo so. Ly do rat thuc te: anh ky
#   yeu co ca thay giao lan hoc sinh, keo "lam thon mat" 60 cho ca hai la sai
#   ca hai. saytool da lam tu ban 0.5.0 (nhom_mat.py), va giao dien rieng cua
#   no da co; chi rieng AutoTone la chua, nen chay qua day thi moi anh deu an
#   cung mot muc.
#
#   Cach ghi VAN LA MOT TU DIEN PHANG, khong phai bang long nhau:
#       "lq_thon_mat"        muc CHUNG, dung cho nhom nao khong khai rieng
#       "nam:lq_thon_mat"    chi ap cho nhom Nam
#   Nho vay retouch.json cu van doc duoc, va cho nao khong quan tam den nhom
#   thi cu doc khoa chung nhu truoc.
#]]
NHOM_DU_PHONG = [["nu", "Nữ"], ["nam", "Nam"], ["tre_con", "Trẻ con"],
                 ["nu_gia", "Nữ lớn tuổi"], ["nam_gia", "Nam lớn tuổi"]]


def _khoa_tool(goc) -> str:
    try:
        return str(Path(goc).resolve())
    except OSError:
        return str(goc)


def nhom_mat(goc=None) -> list:
    """[[mã, nhãn]] các nhóm khuôn mặt saytool đang chia."""
    goc = goc or tim_tool()
    if goc:
        ds = _NHOM_NHO.get(_khoa_tool(goc))
        if ds:
            return ds
    return [list(x) for x in NHOM_DU_PHONG]


def tin_keo(goc=None) -> dict:
    """{tên kéo: {nhom, ghi_chu, bo_qua, ca_khung, buoc}} — hỏi được thì thật."""
    goc = goc or tim_tool()
    return dict(_TK_NHO.get(_khoa_tool(goc)) or {}) if goc else {}


def theo_nhom(ten: str, goc=None) -> bool:
    """Thanh kéo này có chia mức riêng theo nhóm được không?

    #[[ Khong hoi duoc thi mac dinh la CO. saytool dat theo_nhom = True o lop
    #   cha, va ghi chu ben do noi ro: buoc nao that su khong chia duoc thi tu
    #   dat False va phai noi ro vi sao. Nen doan "co" la doan theo mac dinh
    #   cua chinh ho, khong phai doan bua. ]]
    """
    t = tin_keo(goc).get(ten)
    return bool(t.get("nhom", True)) if isinstance(t, dict) else True


def khoa_nhom(nh: str, ten: str) -> str:
    return f"{nh}:{ten}" if nh else ten


def muc_hieu_luc(muc: dict, ten: str, nh: str = "") -> float:
    """Mức thật sự áp cho một nhóm: có riêng thì lấy riêng, không thì lấy chung."""
    if nh:
        v = muc.get(khoa_nhom(nh, ten))
        if v is not None and v != "":
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    try:
        return float(muc.get(ten, 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def moi_muc(muc: dict, ten: str, goc=None) -> list:
    """Mọi mức một thanh kéo có thể nhận — mức chung và mọi mức riêng.

    Dùng để biết bước đó CÓ VIỆC không: mức chung 0 mà Nam đặt 60 thì bước vẫn
    chạy, và mô hình của nó vẫn phải có mặt.
    """
    ra = [muc_hieu_luc(muc, ten)]
    for nh, _nhan in nhom_mat(goc):
        v = muc.get(khoa_nhom(nh, ten))
        if v is not None and v != "":
            try:
                ra.append(float(v))
            except (TypeError, ValueError):
                pass
    return ra


def loi_hoi_keo(goc=None) -> str:
    """Vì sao lần hỏi thanh kéo gần nhất thất bại. "" nếu không sao cả."""
    goc = goc or tim_tool()
    if not goc:
        return ""
    try:
        khoa = str(Path(goc).resolve())
    except OSError:
        khoa = str(goc)
    return _LOI_KEO.get(khoa) or _LOI_KEO.get(str(goc)) or ""


def da_hoi_that(goc=None) -> bool:
    """Bảng thanh kéo đang hiện là của saytool thật, hay chỉ là bản dự phòng?"""
    goc = goc or tim_tool()
    if not goc:
        return False
    try:
        khoa = str(Path(goc).resolve())
    except OSError:
        khoa = str(goc)
    return khoa in _KEO_NHO


def quen_thanh_keo(goc=None) -> None:
    """Xoá bộ nhớ đệm để lần hỏi sau đi hỏi lại thật."""
    for d in (_KEO_NHO, _MH_NHO, _LOI_KEO):
        if goc is None:
            d.clear()
            continue
        try:
            d.pop(str(Path(goc).resolve()), None)
        except OSError:
            pass
        d.pop(str(goc), None)


def hop_le(goc) -> bool:
    """Có đúng là thư mục tool retouch không. KHÔNG đòi .venv — xem python_cho()."""
    if not goc:
        return False
    return (Path(goc) / "saytool" / "cli.py").is_file()


#[[ Ten MODULE thieu  ->  ten GOI trong tai_nguyen.GOI.
#
#   Khong phai cai nao cung anh xa 1-1: `saytool` thieu la loi that (no nam
#   trong goi, thieu nghia la goi hong), con `cv2`/`numpy` thi ban nhe VAN
#   mang theo — thieu chung cung la goi hong. Chi torch va mediapipe moi la
#   thu tai ve duoc.
#]]
MODULE_THANH_GOI = {"torch": "torch", "mediapipe": "mediapipe"}


def _goi_tai_duoc(ten_thieu) -> list:
    """Trong so module thieu, cai nao tai ve duoc? Tra ten goi tai nguyen."""
    ra = []
    for m in ten_thieu:
        g = MODULE_THANH_GOI.get(m)
        if g and g not in ra:
            ra.append(g)
    return ra


def kiem_tra(goc, timeout: float = 60.0) -> tuple:
    """Chạy thử một tiến trình con để BIẾT thiếu gì, thay vì đoán.

    Trả (ổn, mô tả). Đoán thì chỉ nói được "hình như chưa cài"; chạy thử thì
    nói được đúng tên gói còn thiếu.
    """
    g = Path(goc)
    if not hop_le(g):
        return False, vi_sao_khong_dung(g)
    py = python_cho(g)
    ma = ("import sys;"
          "thieu=[]\n"
          "for m in ('torch','cv2','numpy','saytool'):\n"
          "    try: __import__(m)\n"
          "    except Exception as e: thieu.append(m+': '+type(e).__name__)\n"
          "print('THIEU:'+';'.join(thieu) if thieu else 'OK')\n"
          "import saytool; print('phien ban', getattr(saytool,'__version__','?'))")
    cmd = [sys.executable, CO_SAY_KIEM] if la_goc_trong_goi(g) else [py, "-c", ma]
    try:
        #[[ Cung ly do voi _hoi_keo(): tien trinh con in ra chuoi co the co
        #   tieng Viet, ma stdout tren Windows lay cp1252. encoding="utf-8" o
        #   day chi lo phia DOC — phia GHI phai sua bang bien moi truong. ]]
        p = subprocess.run(cmd, cwd=str(g), capture_output=True,
                           text=True, timeout=timeout,
                           encoding="utf-8", errors="replace",
                           env=dict(os.environ, **MOI_TRUONG_UTF8),
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired) as ex:
        return False, f"Không chạy thử được:\n{type(ex).__name__}: {ex}\n\nPython: {py}"
    ra = (p.stdout or "") + (p.stderr or "")
    if "THIEU:" in ra:
        thieu = ra.split("THIEU:", 1)[1].splitlines()[0]
        #[[ GAN NHAN "TAI_DUOC:" khi ban .exe thieu goi tai ve duoc.
        #
        #   Ban nhe khong mang torch/mo hinh, nen thieu la chuyen BINH
        #   THUONG, va cach sua la bam nut Tai — khong phai "pip install
        #   torch". Trong .exe khong co pip, khong co Python nao de cai
        #   vao: bao nhu cu la dua nguoi dung vao ngo cut.
        #
        #   Giao dien doc chuoi nay, thay "TAI_DUOC:" thi MO CUA SO TAI.
        #   De nguyen dang chu cho truong hop chay tu ma nguon — luc do
        #   pip co that va van la cach dung.
        #]]
        ten_thieu = [x.split(":", 1)[0].strip()
                     for x in thieu.split(";") if x.strip()]
        if getattr(sys, "frozen", False):
            can = _goi_tai_duoc(ten_thieu)
            if can:
                return False, ("TAI_DUOC:" + ",".join(can) + "\n"
                               f"Bản cài chưa có: {', '.join(ten_thieu)}")
        return False, (f"Python đang dùng thiếu gói:\n  {thieu}\n\n"
                       f"Python: {py}\n\nCài bằng:\n"
                       f"    pip install torch opencv-python numpy")
    if "OK" not in ra:
        return False, f"Chạy thử không ra kết quả mong đợi:\n{ra[:400]}\n\nPython: {py}"
    pb = ""
    for d in ra.splitlines():
        if d.startswith("phien ban"):
            pb = "  " + d
    thieu = mo_hinh_can(g)          # kiem CA HAI, khong loc theo thanh keo
    if thieu:
        d = ["Thiếu file mô hình:"]
        for t in thieu:
            d.append(f"  {t['dich']}" +
                     (f"   (có sẵn: {t['ung_vien'][0]})" if t["ung_vien"]
                      else "   — KHÔNG tìm thấy file nào thay được"))
        d.append("")
        d.append("Bấm “Chạy retouch”, cửa sổ sẽ hỏi chép giúp.")
        return False, f"Python OK ({Path(py).name}) nhưng " + "\n".join(d)
    return True, f"Sẵn sàng — {Path(py).name}\n{pb}".rstrip()


#[[ MO HINH: saytool GHI CUNG duong dan trong tung buoc.
#
#     buoc_vet.py       __init__(self, mo_hinh="mo_hinh/vet.pt", ...)
#     buoc_vet_body.py  __init__(self, mo_hinh="mo_hinh/vet_body.pt", ...)
#     buoc_nong_cam.py  __init__(self, mo_hinh="mo_hinh/nong_cam.pt", ...)
#     buoc_nhan.py      __init__(self, mo_hinh="mo_hinh/nhan.pt", ...)
#
#   va buoc.tat_ca() dung BUOC() khong tham so, nen khong truyen duoc gi vao.
#   Duong dan tuong doi -> tinh theo cwd, ma ta dat cwd = thu muc tool.
#
#   HAI BANG, HAI VIEC KHAC NHAU:
#
#   MO_HINH  la ban DU PHONG cho luc hoi saytool that bai (may ban, torch nap
#            lau qua 180 giay). Khoa la TEN THANH KEO — chu y "nhan_tran" la
#            ten thanh keo con buoc thi ten "nhan"; lay nham la kiem nham cho.
#            Buoc "chan" va "liquify" khong co dong nao: keo dai chan khong can
#            mo hinh, con liquify chi sinh thanh keo cho nhung file .npz CO SAN
#            trong mo_hinh/liquify — thieu file thi thanh keo khong hien ra chu
#            khong phai hien ra roi chay hong.
#
#   UNG_VIEN khoa theo DUONG DAN DICH, khong theo ten thanh keo. Nho vay du
#            saytool doi ten buoc hay them buoc, chi can no van xin dung file
#            do la ta biet lay o dau ra. Danh sach nay KHONG phai toi doan: no
#            lay tu chinh chay_giao_dien.bat ma nguoi dung van chay hang ngay:
#              python giao_dien.py --model v14_out\gpu_all.pt \
#                                  --model-nong-cam nc_F2\tat_ca.pt
#            tuc chinh ho da khai file nao dong vai nao.
#
#            vet_body.pt va nhan.pt CO Y de rong. Canh vet_body.pt co
#            vet_body_magimir.pt — hoc tren bo anh MagiMir ma nguoi dung da bo
#            han. Chep no vao thay the la lang le giao mot ket qua khac han thu
#            ho duyet. Tha bao thieu.
#]]
MO_HINH = {
    "vet": ["mo_hinh/vet.pt"],
    "vet_body": ["mo_hinh/vet_body.pt"],
    "nong_cam": ["mo_hinh/nong_cam.pt"],
    "nhan_tran": ["mo_hinh/nhan.pt"],
}

UNG_VIEN = {
    "mo_hinh/vet.pt": ["v14_out/gpu_all.pt", "net5_all_v14.pt",
                       "net3_all_v13.pt"],
    "mo_hinh/nong_cam.pt": ["nc_F2/tat_ca.pt", "nc_mo_hinh/tat_ca.pt"],
    "mo_hinh/vet_body.pt": [],
    "mo_hinh/nhan.pt": [],
}


def mo_hinh_theo_keo(goc) -> dict:
    """{tên thanh kéo: [file mô hình cần]} — hỏi saytool, không thì bảng dự phòng."""
    try:
        khoa = str(Path(goc).resolve())
    except OSError:
        khoa = str(goc)
    if khoa not in _MH_NHO:
        thanh_keo(goc)              # lần hỏi này nhớ luôn bảng mô hình
    mh = _MH_NHO.get(khoa) or {}
    return mh if mh else dict(MO_HINH)


def mo_hinh_can(goc, muc: dict | None = None) -> list:
    """Những mô hình còn thiếu cho các thanh kéo ĐANG BẬT.

    Thanh kéo ở 0 thì buoc.bat() trả False, saytool không nạp mô hình đó, nên
    thiếu cũng không sao — báo ra chỉ tổ làm người dùng đi tìm thứ không cần.

    #[[ VI SAO VIEC NAY QUAN TRONG HON TRUOC.
    #
    #   Truoc 0.9.5, thieu mot file mo hinh la ca me anh dung ngay o anh dau —
    #   xau nhung nhin thay duoc. Tu 0.9.5, duong_ong.chay() bat loi rieng tung
    #   buoc va chi in "! BO QUA <nhan>", roi CHAY TIEP. Anh van ra du, nhin
    #   qua van dep, chi la thieu han mot tinh nang. Khong kiem truoc thi khong
    #   ai biet, va anh da giao cho khach roi.
    #]]
    """
    g = Path(goc)
    ra = []
    da_co = set()
    for ten, dich_ds in sorted(mo_hinh_theo_keo(goc).items()):
        #[[ Phai xet CA MUC RIENG. Muc chung 0 ma Nam dat 60 thi buoc do van
        #   chay, va mo hinh cua no van phai co mat. Chi nhin muc chung la bao
        #   "du" trong khi thuc te thieu — roi anh nam ra thieu mot tinh nang
        #   ma khong ai biet. ]]
        if muc is not None and not any(v > 0 for v in moi_muc(muc, ten, goc)):
            continue
        for dich in dich_ds:
            if dich in da_co or (g / dich).is_file():
                continue
            da_co.add(dich)
            co = [c for c in UNG_VIEN.get(dich, []) if (g / c).is_file()]
            ra.append({"buoc": ten, "dich": dich, "ung_vien": co})
    return ra


def chep_mo_hinh(goc, thieu: list) -> list:
    """Chép ứng viên đầu tiên vào đúng chỗ. Trả về danh sách dòng mô tả."""
    import shutil
    g = Path(goc)
    ra = []
    for t in thieu:
        if not t["ung_vien"]:
            ra.append(f"KHONG CO ung vien cho {t['dich']}")
            continue
        src, dst = g / t["ung_vien"][0], g / t["dich"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        ra.append(f"{t['ung_vien'][0]}  ->  {t['dich']}"
                  f"   ({dst.stat().st_size / 1e6:.1f} MB)")
    return ra


def doc_cau_hinh() -> dict:
    if not CAU_HINH.is_file():
        return {}
    try:
        d = json.loads(CAU_HINH.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def ghi_cau_hinh(d: dict) -> None:
    cu = doc_cau_hinh()
    cu.update(d)
    tmp = CAU_HINH.with_suffix(".part")
    tmp.write_text(json.dumps(cu, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, CAU_HINH)


def tim_tool() -> Path | None:
    """Chỗ đã ghi trước, rồi bản trong gói, rồi mới dò. None nếu không thấy đâu.

    #[[ Ban trong goi dat SAU cau hinh chu khong truoc: nguoi dung tu chon mot
    #   thu muc khac thi phai duoc ton trong, neu khong thi nut "Chon..." tro
    #   thanh vo dung. Nhung dat TRUOC CHO_HAY_CO, vi tren ban all-in-one thu
    #   vien di kem chinh ban trong goi — do mot ban ma nguon ngoai o dia roi
    #   chay bang no la de lech phien ban.
    #]]
    """
    g = doc_cau_hinh().get("goc")
    if hop_le(g):
        return Path(g)
    b = goc_trong_goi()
    if b is not None:
        return Path(b)
    #[[ TU CHUA KHI TOOL DA CHUYEN CHO.
    #
    #   Truoc day cho nay chi "khong tim thay thi thoi". Nhung truong hop that
    #   xay ra 8/9 khong phai la CHUA BAO GIO co, ma la DA TUNG co roi bi
    #   chuyen: retouch.json van ghi F:\ToolCloneEvoto trong khi tool nam o
    #   F:\Claude AI\ToolCloneEvoto. Do lai ra cho moi thi phai GHI DE duong
    #   dan cu, neu khong lan sau van doc phai cai chet.
    #
    #   Va nho lai cho cu de giao dien noi duoc "tool da chuyen tu X sang Y" —
    #   im lang doi duong dan duoi tay nguoi dung cung la mot kieu hong.
    #]]
    for c in cho_hay_co():
        if hop_le(c):
            if g and str(g) != str(c):
                ghi_cau_hinh({"goc": str(c), "goc_cu": str(g)})
            else:
                ghi_cau_hinh({"goc": str(c)})
            return c
    return None


def da_chuyen_cho() -> tuple:
    """(chỗ cũ, chỗ mới) nếu lần dò gần nhất phát hiện tool đã chuyển, không thì ()."""
    d = doc_cau_hinh()
    cu, moi = d.get("goc_cu"), d.get("goc")
    if cu and moi and str(cu) != str(moi):
        return (cu, moi)
    return ()


def quen_da_chuyen() -> None:
    """Xoá dấu 'đã chuyển' sau khi đã báo cho người dùng một lần."""
    d = doc_cau_hinh()
    if "goc_cu" in d:
        d.pop("goc_cu", None)
        tmp = CAU_HINH.with_suffix(".part")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        os.replace(tmp, CAU_HINH)


def vi_sao_khong_dung(goc) -> str:
    """Câu giải thích cụ thể, thay cho 'đường dẫn không hợp lệ'."""
    if not goc:
        return "Chưa chọn thư mục tool retouch."
    g = Path(goc)
    if not g.is_dir():
        return f"Không có thư mục:\n{g}"
    if not (g / "saytool" / "cli.py").is_file():
        return (f"{g}\nkhông phải thư mục tool retouch — thiếu saytool\\cli.py.\n"
                "Chọn đúng thư mục ToolCloneEvoto.")
    return ""


def dem(vao: Path, ra: Path, de_quy: bool = False) -> tuple[int, int]:
    """(tổng ảnh vào, số ảnh đã có kết quả) — để báo trước còn bao nhiêu tấm.

    Đếm theo ĐÚNG cách duong_ong.chay() lọc: cùng tên tệp là coi như đã làm.
    """
    vao, ra = Path(vao), Path(ra)
    if not vao.is_dir():
        return 0, 0
    it = vao.rglob("*") if de_quy else vao.iterdir()
    files = [p for p in it if p.is_file() and p.suffix.lower() in DUOI]
    if not ra.is_dir():
        return len(files), 0
    xong = sum(1 for p in files
               if (ra / (p.relative_to(vao) if de_quy else Path(p.name))).exists())
    return len(files), xong


def lenh(goc: Path, vao: Path, ra: Path, muc: dict,
         may: str = "auto", chat_luong: int = 98,
         de_quy: bool = False, lam_lai: bool = False,
         gioi_han: int = 0, luong: int = LUONG_MAC_DINH,
         che_do: str = CHE_DO_MAC_DINH) -> list:
    """Dựng dòng lệnh. Tách riêng để test được mà không cần chạy thật."""
    tham = ["chay", str(vao), str(ra), "--may", may,
            "--chat-luong", str(int(chat_luong))]
    #[[ CHI truyen --luong khi nguoi dung EP mot con so.
    #
    #   phan_cung.so_luong() co nhanh `if xin > 0: return min(xin, ...)`, nen
    #   truyen mot con so la vo hieu hoa toan bo phan tu do theo bo nho con
    #   trong. De trong (0) thi saytool tu do may — xem ghi chu o
    #   LUONG_MAC_DINH ve vi sao doi tu 1 sang 0.
    #]]
    if int(luong) > 0:
        tham += ["--luong", str(int(luong))]
    #[[ --che-do la tham so cua ban 0.9.5 tro len. Ban cu khong biet no va
    #   argparse se bao "unrecognized arguments" -> ca me anh khong chay. Nen
    #   chi truyen khi thanh keo cua ban do co dau hieu la ban moi... khong,
    #   khong doan: truyen khi va chi khi nguoi dung chon khac "auto". Khong
    #   truyen thi saytool ban nao cung mac dinh "auto", tuc y het nhau.
    #]]
    if che_do and che_do != "auto":
        tham += ["--che-do", str(che_do)]
    if de_quy:
        tham.append("--de-quy")
    if lam_lai:
        tham.append("--lam-lai")
    if gioi_han:
        tham += ["--gioi-han", str(int(gioi_han))]
    #[[ Duyet theo danh sach saytool DANG co, khong phai danh sach ghi cung.
    #
    #   Loc theo danh sach do la CAN THIET chu khong phai cho gon: muc duoc ghi
    #   vao retouch.json va con lai o day mai. Ben kia bo mot buoc di ma ta van
    #   truyen --<ten cu> thi argparse cua saytool bao "unrecognized arguments"
    #   va ca me anh khong chay — hong o cho khong ai ngo.
    #]]
    co_that = set()
    for ten, _nhan, _md, _goi in thanh_keo(goc):
        co_that.add(ten)
        v = muc.get(ten)
        if v is not None:
            tham += [f"--{ten.replace('_', '-')}", f"{float(v):g}"]
    #[[ MUC RIENG THEO NHOM -> --nhom nhom:keo=so
    #
    #   saytool khong sinh --nam-vet, --nu-vet... cho tung to hop (5 nhom x N
    #   thanh keo la mot rung tham so khong ai doc noi trong phan tro giup), ma
    #   gom ve mot tham so lap lai duoc. Chinh ta cung phai theo dung cach do.
    #
    #   CHI PHAT KHI CO THAT mot muc rieng: ban saytool cu khong biet --nhom va
    #   argparse se bao "unrecognized arguments" -> ca me anh khong chay. Khong
    #   ai dat muc rieng thi dong lenh y het truoc day.
    #
    #   Va van loc theo danh sach thanh keo DANG co, cung ly do voi muc chung:
    #   muc cu nam trong retouch.json mai mai, ben kia go mot buoc di ma ta van
    #   gui --nhom nu:<ten cu> thi saytool tu choi ca me.
    #]]
    ma_nhom = {n for n, _l in nhom_mat(goc)}
    for khoa in sorted(muc):
        if ":" not in str(khoa):
            continue
        nh, _, ten = str(khoa).partition(":")
        if nh not in ma_nhom or ten not in co_that:
            continue
        v = muc.get(khoa)
        if v is None or v == "":
            continue
        tham += ["--nhom", f"{nh}:{ten.replace('_', '-')}={float(v):g}"]
    return lenh_saytool(goc, tham)


def tool_doc_duoc_dau(goc) -> bool:
    r"""Bản saytool ở `goc` đã đọc/ghi được đường dẫn có dấu chưa?

    VÌ SAO HỎI THAY VÌ ĐOÁN
        Trước 14/9 thì cứ có dấu là chắc chắn trượt, nên bên này chặn thẳng.
        Nay saytool đã có `saytool/duong_dan.py`: Python đọc file thành byte rồi
        đưa cv2.imdecode (và ngược lại khi ghi), nên không còn đi qua API ANSI
        của Windows nữa — đường dẫn tiếng Việt chạy bình thường.

        Nhưng người dùng có thể đang trỏ sang một bản saytool CŨ. Nên không
        được đoán theo cả hai hướng: cứ nhìn thẳng vào bản đang dùng mà hỏi.

        Xem GHI_CHU_DUONG_DAN.md bên ToolCloneEvoto.
    """
    if not goc:
        return False
    try:
        return (Path(goc) / "saytool" / "duong_dan.py").is_file()
    except OSError:
        return False


def khong_ascii(*duong_dan, goc=None) -> list:
    r"""Những đường dẫn có ký tự ngoài ASCII mà bản saytool đang dùng KHÔNG kham nổi.

    VÌ SAO TỪNG PHẢI CHẶN
        cv2.imread / cv2.imwrite trên Windows đi qua API ANSI, nên đường dẫn có
        dấu tiếng Việt là chúng mở không được, dù file nằm sờ sờ ở đó. Lỗi báo
        ra lại là "can't open/read file: check file path/integrity" — nghe như
        file hỏng, nên rất dễ đi tìm sai chỗ.

        Đo thật 3/9: thư mục "F:\Sản Phẩm Final\Migimir\Test2905", cả 140 ảnh
        đều trượt, không tấm nào đọc được.

    VÌ SAO GIỜ THƯỜNG KHÔNG CHẶN NỮA
        14/9 saytool đã sửa (saytool/duong_dan.py). Chạy thử qua đúng hai đường
        dẫn trong thông báo cũ — "G:\TestRetouch\Giải Chạy" và "F:\Sản Phẩm
        Final\Tháng 9 2026\Bureau Veritas Company trip 2026\Giải chạy Yên Tử"
        — đều xong, ảnh ra đúng 1,00x, giữ nguyên EXIF và ICC.

        Truyền `goc` vào thì hàm này nhìn bản saytool ĐANG DÙNG mà quyết định.
        Không truyền thì giữ nguyên nết cũ (chặn hết) cho chỗ gọi cũ khỏi vỡ.
    """
    if goc is not None and tool_doc_duoc_dau(goc):
        return []          # bản này kham được, không có gì để chặn
    xau = []
    for d in duong_dan:
        if d and not str(d).isascii():
            xau.append(str(d))
    return xau


#[[ Ma thoat cua Windows in ra dang so thap phan chin chu so. "ma 3221225477"
#   khong noi len dieu gi, con "tien trinh bi he dieu hanh giet" thi noi duoc.
#]]
MA_THOAT = {
    0: "",
    1: "Tiến trình con báo lỗi Python — xem vệt lỗi ở mấy dòng cuối. "
       "(Trên Windows, bấm Dừng cũng cho mã 1.)",
    3221225477: "Tiến trình bị hệ điều hành giết (ACCESS_VIOLATION 0xC0000005).",
    3221225786: "Tiến trình bị ngắt (Ctrl-C / 0xC000013A).",
    3221226505: "Tiến trình tự huỷ vì phát hiện hỏng bộ nhớ (0xC0000409).",
    #[[ 0xC0000374 — gap that 14/9, chet o anh 556/3465 trong khi RAM con
    #   trong 16,8/34,1 GB. KHONG phai het bo nho: mot thu vien native ghi ra
    #   ngoai vung nho cua no, va Windows chi phat hien ra RAT MUON, o mot cho
    #   khac han noi gay loi. Nen vet loi Python (neu co) thuong tro sai cho.
    #]]
    3221226356: "Một thư viện nền làm hỏng vùng nhớ động (HEAP CORRUPTION "
                "0xC0000374). Đây KHÔNG phải hết bộ nhớ.",
}

DAU_HET_VRAM = ("out of memory", "memory allocation failed", "OOM on device",
                "CUDA error: out of memory")


def giai_thich_ma(ma: int, log: str = "", luong: int = 0) -> str:
    """Mã thoát + vài dòng log cuối -> một câu người dùng làm được gì với nó."""
    if not ma:
        return ""
    d = [MA_THOAT.get(int(ma), f"Mã thoát lạ: {ma}")]
    if any(k.lower() in (log or "").lower() for k in DAU_HET_VRAM):
        d.append("Nguyên nhân trong log: HẾT BỘ NHỚ CARD ĐỒ HOẠ (VRAM).")
        if luong > 1:
            d.append(f"Đang chạy {luong} luồng — mỗi luồng nạp một bộ mô hình "
                     f"riêng lên card. Hạ “Số luồng” về 1 rồi chạy lại.")
        else:
            d.append("Đang chạy 1 luồng mà vẫn hết VRAM: đóng bớt chương trình "
                     "khác đang dùng card (Lightroom, trình duyệt), hoặc đổi "
                     "“Máy” sang cpu.")
    elif int(ma) == 3221225477 and luong > 1:
        d.append(f"Hay gặp nhất khi {luong} luồng cùng nạp mô hình lên card. "
                 f"Hạ “Số luồng” về 1 rồi chạy lại.")
    elif int(ma) == 3221226356:
        #[[ Hai runtime GPU DOC LAP tren cung mot card: onnxruntime-directml
        #   (do khuon mat, phan vung da) va PyTorch CUDA (xoa khuyet diem, nong
        #   cam). Moi ben mot bo cap phat bo nho rieng. Day la nghi pham manh
        #   nhat cho 0xC0000374, va cung la thu NGUOI DUNG THU DUOC NGAY.
        #]]
        d.append("Máy này chạy hai bộ GPU song song trên cùng một card: "
                 "onnxruntime-DirectML và PyTorch-CUDA. Thử tách chúng ra — "
                 "đặt biến môi trường SAY_ORT=cpu rồi chạy lại "
                 "(chậm hơn chút ở khâu dò mặt, nhưng tách hẳn hai bộ).")
        if luong > 1:
            d.append(f"Nếu vẫn sập: hạ “Số luồng” từ {luong} về 1 — lỗi hỏng "
                     f"vùng nhớ hay lộ ra khi nhiều luồng dùng chung một bộ.")
        d.append("Chạy lại vẫn tiếp tục từ chỗ dừng, không mất ảnh đã xong.")
    return "\n".join(d)


_DA_TAT_HOP_THOAI = False


def _tat_hop_thoai_sap():
    r"""Tắt hộp thoại “Application Error” của Windows cho tiến trình con.

    VÌ SAO CẦN
        Khi tiến trình con sập ở tầng native (0xC0000005 / 0xC0000374), Windows
        bật một hộp thoại “The instruction at 0x… referenced memory at 0x…
        Click on OK to terminate the program” VÀ NGỒI CHỜ NGƯỜI BẤM.

        Với tự-chạy-lại thì đây là hỏng to: cả mẻ 3465 ảnh đứng im giữa đêm để
        chờ một cái OK không ai bấm. Đặt SEM_FAILCRITICALERRORS |
        SEM_NOGPFAULTERRORBOX thì tiến trình chết ngay và trả mã thoát về — ta
        đọc mã đó rồi tự chạy lại. Không mất thông tin: mã thoát vẫn nguyên.

        Cờ này DI TRUYỀN sang tiến trình con, nên đặt một lần ở app là đủ.
    """
    global _DA_TAT_HOP_THOAI
    if _DA_TAT_HOP_THOAI or os.name != "nt":
        return
    try:
        import ctypes
        SEM_FAILCRITICALERRORS = 0x0001
        SEM_NOGPFAULTERRORBOX = 0x0002
        ctypes.windll.kernel32.SetErrorMode(
            SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX)
        _DA_TAT_HOP_THOAI = True
    except Exception:
        pass          # không tắt được thì thôi, chỉ là phải bấm OK thủ công


def chay(goc: Path, vao: Path, ra: Path, muc: dict, **kw):
    """Chạy và sinh ra từng dòng log. Trả mã thoát ở dòng cuối dạng ('ma', n).

    Dùng generator chứ không gom hết rồi trả về: một buổi vài trăm ảnh chạy cả
    chục phút, gom hết thì giao diện đứng im suốt thời gian đó và người dùng
    không biết nó còn sống hay đã treo.
    """
    cmd = lenh(Path(goc), Path(vao), Path(ra), muc, **kw)
    yield ("lenh", " ".join(cmd))
    #[[ EP TIEN TRINH CON IN RA UTF-8.
    #
    #   Khong ep thi tren Windows no lay ma trang he thong (cp1252), va CHET
    #   ngay khi phai in mot ten file co dau tieng Viet:
    #       UnicodeEncodeError: 'charmap' codec can't encode character '\u1ea3'
    #   Cho chet lai nam trong doan tool bao LOI — tuc mot loi nho keo sap ca me,
    #   va thu hien ra man hinh la vet stack cua may in chu khong phai loi that.
    #   Da xay ra dung nhu vay 3/9.
    #
    #   errors="replace" o day chi lo phia DOC. Phia GHI cua tien trinh con phai
    #   sua bang bien moi truong.
    #]]
    env = dict(os.environ, **MOI_TRUONG_UTF8)
    #[[ GIAM PHAN MANH BO NHO CARD.
    #
    #   Do that 3/9 (do_vram.py, 34 anh, 1 luong, RTX 3060 Ti):
    #       torch_giu   : 200 -> 2,552 MB   (+2,352 MB qua 34 anh)
    #       ngoai_torch : 1,692 -> 1,692 MB (+0 MB)
    #   Tuc onnxruntime khong ro ri chut nao; phan phinh ra la cua torch.
    #
    #   Khong phai ro ri that (torch khong quen tra), ma la PHAN MANH: moi khuon
    #   mat mot kich thuoc khac nhau nen moi anh xin mot khoi co khac nhau. Bo
    #   cap phat cua torch giu lai khoi cu de dung tiep, nhung khoi 700 MB khong
    #   vua cho ai xin 900 MB, nen no cu phai xin them. 34 anh sau la giu 2.5 GB
    #   ma phan lon dang bo khong — tren card 8 GB thi do la mot phan tu the card.
    #
    #   expandable_segments doi cach xin bo nho: mot vung lien tuc no gian ra
    #   duoc, thay vi nhieu khoi roi rac co dinh kich thuoc. Dung cho truong hop
    #   kich thuoc thay doi lien tuc nhu o day.
    #
    #   Dat qua BIEN MOI TRUONG chu khong sua ma nguon ToolCloneEvoto: torch doc
    #   bien nay mot lan luc khoi tao, nen dat o day la du, va go ra cung de.
    #]]
    env.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    #[[ NUM DIEU CHINH BO NHO, doc tu retouch.json neu co.
    #
    #   BA KHOA CU DA CHET. Ban 0.9.5 khong con doc SAY_O_VET va
    #   SAY_LO_NONG_CAM nua (da grep ca goi: chi con SAY_RAM_MB, SAY_LOI,
    #   SAY_THREADS). Dat chung chi lam yen tam gia — env co day du ma khong ai
    #   doc. Nen doi sang dung ba bien that, va NOI RA neu retouch.json con khoa
    #   cu, thay vi lang le bo qua.
    #
    #       "ram_mb": 4000     -> SAY_RAM_MB, tu gioi han khi con chay viec khac
    #       "so_loi": 8        -> SAY_LOI, so loi CPU cho phep dung
    #       "luong_torch": 4   -> SAY_THREADS, so luong BLAS/onnxruntime moi phien
    #
    #   Khong dat gi thi KHONG dung toi env, de saytool tu quyet — mot cho
    #   quyet dinh chu khong phai hai.
    #]]
    cf = doc_cau_hinh()
    for khoa, bien in (("ram_mb", "SAY_RAM_MB"), ("so_loi", "SAY_LOI"),
                       ("luong_torch", "SAY_THREADS")):
        if cf.get(khoa) is not None:
            env[bien] = str(int(cf[khoa]))
            yield ("dong", f"  {bien}={env[bien]} (dat trong retouch.json)")
    for khoa_cu in ("o_vet", "lo_nong_cam"):
        if cf.get(khoa_cu) is not None:
            yield ("dong",
                   f"  ! retouch.json con khoa \"{khoa_cu}\" — ban saytool 0.9.5 "
                   f"khong con doc no. Dung ram_mb / so_loi / luong_torch.")
    #[[ TAT HOP THOAI "Application Error" CUA WINDOWS.
    #
    #   Khi tien trinh con sap o tang native (0xC0000005 / 0xC0000374),
    #   Windows bat mot hop thoai "The instruction at 0x... referenced memory
    #   at 0x... Click on OK to terminate the program" VA NGOI CHO NGUOI BAM.
    #
    #   Voi tu-chay-lai thi day la hong to: ca me anh dung im giua dem cho mot
    #   cai OK khong ai bam. Dat SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX
    #   thi tien trinh chet NGAY va tra ma thoat ve - ta doc ma do roi tu chay
    #   lai duoc. Khong mat thong tin gi: ma thoat van dung nguyen.
    #
    #   Chi dat cho TIEN TRINH CON (qua Popen), khong dong den app dang chay.
    #]]
    if os.name == "nt":
        env.setdefault("PYTHONFAULTHANDLER", "1")   # con in vet loi neu con kip
        _tat_hop_thoai_sap()
    try:
        p = subprocess.Popen(
            cmd, cwd=str(goc), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1, env=env,
            # Khong bat cua so console den nhay len tren Windows
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError as ex:
        yield ("loi", f"Khong chay duoc: {ex}")
        yield ("ma", 1)
        return
    yield ("pid", p)
    try:
        for line in p.stdout:
            yield ("dong", line.rstrip())
    finally:
        p.stdout.close()
        yield ("ma", p.wait())


#[[ BUOC BI BO GIUA CHUNG — kieu hong im lang moi cua 0.9.5.
#
#   duong_ong.chay() nap tung buoc rieng va bat loi rieng:
#       except Exception as e:
#           bao(f"  ! BO QUA {b.nhan}: {type(e).__name__}: {e}")
#   roi CHAY TIEP voi nhung buoc con lai. Truoc 0.9.5 thi thieu mot mo hinh la
#   dung ca me — xau nhung nhin thay ngay. Gio anh van ra du, nhin qua van dep,
#   chi la thieu han mot tinh nang; va neu khong ai doc ky nhat ky thi ca buoi
#   da giao cho khach roi moi phat hien.
#
#   Nen phai boi dong do ra khoi nhat ky va noi lai o cuoi.
#]]
_BO_QUA = re.compile(r"^\s*!\s*BO QUA\s+(.+?):\s*(.+)$")


def buoc_bi_bo(dong) -> list:
    """[(tên bước, lý do)] rút từ nhật ký một lượt chạy."""
    ra = []
    for d in dong or ():
        m = _BO_QUA.match(str(d))
        if m:
            ra.append((m.group(1).strip(), m.group(2).strip()))
    return ra


def main(argv=None) -> int:
    """Chạy tay từ dòng lệnh, chủ yếu để kiểm tra đường dẫn tool."""
    import argparse
    ap = argparse.ArgumentParser(description="Goi tool retouch tu AutoTone.")
    ap.add_argument("vao", nargs="?")
    ap.add_argument("ra", nargs="?")
    ap.add_argument("--goc", type=Path, default=None)
    ap.add_argument("--vet", type=float, default=None)
    ap.add_argument("--nong-cam", type=float, default=None, dest="nong_cam")
    ap.add_argument("--chan", type=float, default=None)
    ap.add_argument("--may", default="auto")
    ap.add_argument("--luong", type=int, default=LUONG_MAC_DINH,
                    help=f"So luong CPU khau chuan bi (mac dinh {LUONG_MAC_DINH})")
    ap.add_argument("--tim", action="store_true", help="Chi tim tool roi thoat")
    a = ap.parse_args(argv)

    goc = a.goc or tim_tool()
    if not hop_le(goc):
        print(vi_sao_khong_dung(goc))
        return 1
    print(f"Tool retouch: {goc}")
    print(f"Python      : {python_cho(goc)}")
    ok, mo = kiem_tra(goc)
    print(f"Kiem tra    : {'OK' if ok else 'HONG'}\n{mo}")
    if a.tim or not a.vao:
        return 0

    ra = Path(a.ra) if a.ra else Path(str(a.vao).rstrip("\\/") + "_retouch")
    tong, xong = dem(Path(a.vao), ra)
    print(f"Vao {tong} anh, da co ket qua {xong} -> con {tong - xong}")
    muc = {k: getattr(a, k) for k, _n, _m, _g in THANH_KEO}
    ma = 0
    cuoi = []
    for loai, gt in chay(goc, Path(a.vao), ra, muc, may=a.may, luong=a.luong):
        if loai == "dong":
            print(gt)
            cuoi.append(gt)
            del cuoi[:-80]
        elif loai == "lenh":
            print(f"$ {gt}")
        elif loai == "loi":
            print(gt, file=sys.stderr)
            cuoi.append(gt)
        elif loai == "ma":
            ma = gt
    print(f"Ket thuc, ma thoat {ma}")
    vi = giai_thich_ma(ma, "\n".join(cuoi), a.luong)
    if vi:
        print(vi)
    return ma


if __name__ == "__main__":
    sys.exit(main())
