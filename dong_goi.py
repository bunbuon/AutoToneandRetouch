#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dong_goi.py — Đóng AutoTone thành gói chạy được trên máy khác.

    python dong_goi.py                 # đóng gói cho hệ điều hành đang chạy
    python dong_goi.py --thu           # chỉ in ra lệnh sẽ chạy, không chạy
    python dong_goi.py --khong-retouch # bỏ phần retouch cho gói nhẹ

KHÔNG BUILD CHÉO ĐƯỢC — ĐÂY LÀ GIỚI HẠN CỦA CÔNG CỤ, KHÔNG PHẢI CỦA SCRIPT
    File .exe cho Windows phải build TRÊN Windows. Gói .app cho macOS phải
    build TRÊN máy Mac. PyInstaller đóng gói bằng cách nhét chính trình thông
    dịch Python và các thư viện nhị phân của MÁY ĐANG CHẠY vào gói — không có
    đường vòng nào, kể cả Docker hay Wine.
    Nên file này chạy trên máy nào thì ra bản cho máy đó.

ONEDIR CHỨ KHÔNG ONEFILE
    --onefile gói tất cả vào một .exe rồi mỗi lần mở lại GIẢI NÉN ra thư mục
    tạm. Với phần retouch (torch + onnxruntime + insightface ~4 GB) thì mỗi lần
    mở app mất hàng phút và ngốn thêm 4 GB đĩa tạm. --onedir mở tức thì.
    Đổi lại là một thư mục thay vì một file — nén zip lại là gửi được.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parent
TEN = "AutoTone"

#[[ KHONG DUOC CO TRONG GOI CAI.
#
#   tao_ma.py dung chung khoa bi mat voi khoa.py — ai co no thi tu sinh ma gia
#   han duoc, tuc ca co che han dung thu thanh vo nghia. kiem_khoa.py co mot
#   phep kiem canh dung dong nay.
#
#   Cac file kiem/do khong nguy hiem, chi la rac trong goi cai.
#]]
LOAI_TRU = [
    "tao_ma.py",           # ⚠ khoá bí mật — xem trên
    #[[ cap_key.py dung chung khoa bi mat voi ban_quyen.py. Lot vao goi thi
    #   khach hang tu sinh key vinh vien duoc, va ca he thong ban quyen thanh
    #   vo nghia. so_key.csv la so ban hang — khong viec gi phai di theo app.
    #]]
    "cap_key.py", "so_key.csv", "kiem_ban_quyen.py", "quan_ly_key.py",
    "kiem_quan_ly_key.py",
    #[[ kiem_bq_giao_dien.py `import cap_key` -> keo ca khoa ky key vao goi neu
    #   lot. kiem_bq_online.py la file kiem, chi la rac. Ca hai bi kiem_dong_goi
    #   bao thieu (3/10 chua ai ke) — bo sung ca hai. ]]
    "kiem_bq_giao_dien.py", "kiem_bq_online.py",
    "kiem_khoa.py", "kiem_gu.py", "kiem_luat.py", "kiem_san.py",
    "kiem_do_mat.py", "kiem_goi.py", "kiem_ban_xuat.py", "do_trong_ngoai.py", "do_wb.py", "hoc_mau_da.py", "kiem_mau_da.py",
    "test_tach_canh.py", "test_cull_split.py", "test_san_phang.py",
    "test_trang_thai.py", "test_retouch_luong.py", "kiem_da_tien_trinh.py",
    "nap_mo_hinh.py", "kiem_exif_jpeg.py", "kiem_mau_lr.py",
    "kiem_duyet_py.py", "kiem_gui_duyet.py", "kiem_moc_va_xuat.py",
    "kiem_che_do_sang.py", "kiem_bo_cuc.py", "kiem_ve_that.py", "kiem_khung_anh.py",
    "kiem_man_hinh.py", "kiem_xuat_lr.py", "kiem_tim_tool.py", "kiem_retouch_095.py", "kiem_retouch_gui.py", "kiem_dong_goi.py", "kiem_mac.py", "kiem_cu_phap.py", "chan_doan.py", "kiem_xuatanh.lua",
    "kiem_batduongdan.lua", "kiem_duyet.lua", "kiem_dung_preview.lua",
    "do_ranh_canh.py", "do_chot_mat_ao.py", "so_sanh_do_mat.py",
    "xem_chot.py", "xem_do_sang.py", "eye_probe.py", "eye_sheet.py",
    "make_testdata.py", "tools_smoke_test.py", "dong_goi.py", "bao_mat.py",
    #[[ 3/10: kiem_dong_goi bao "moi file kiem/do deu bi loai" DO — nhieu file
    #   kiem them tu 29/9 toi 3/10 chua ai ke vao day. Bo sung ca loat. ]]
    "kiem_2ban_quay.py", "kiem_ghi_de.py", "kiem_nhan_keo.py", "kiem_tham_chieu.py",
    "kiem_xem_truoc.py", "test_2ban_quay.py", "test_af_xoay.py",
    "test_dung_lai_buoi.py", "test_mat_ao_to.py", "test_mat_lech_khung.py",
    "test_preset_khong_wb_tone.py", "kiem_chup.lua", "kiem_xuat_thong_so.lua",
    "kiem_ket_qua_xuat.lua", "do_buoi.py", "so_sanh_ung_vien.py",
    "test_bu_sang.py", "test_dong_bo_loat.py", "test_wb_asshot.py",
    "test_giao_dien_gon.py", "test_cap_nhat.py", "test_retouch_cwd.py",
    "kiem_xem_goi.py",
    #[[ Cong cu phat hanh — khong phai thu nguoi dung chay. tao_ban_cap_nhat.py
    #   dung chung bao_mat.MA_HOA de dong ban OTA; khong co bi mat nhung la rac
    #   trong goi cai. dong_installer.py + installer_win.iss chi de dong Setup.exe
    #   tren may build — khong di theo app. ]]
    "tao_ban_cap_nhat.py", "dong_installer.py",
    #[[ onnxruntime-gpu (7/10): do mat / phan vung da chay CUDA nhu ban ma nguon —
    #   ban cai cu dong goi onnxruntime CPU, moi phep ORT mo 32 luong, 4 luong chuan
    #   bi giam len nhau (60 giay-CPU / anh, 3,5 s/anh thay vi ~1,5). Provider
    #   TensorRT di kem wheel nhung khong co thu vien TensorRT -> bo cho khoi lot
    #   vao goi (0,8 MB) va khoi bi liet ke. ]]
    "onnxruntime_providers_tensorrt.dll",
]

# Module chính của app và các module nó gọi tới lúc chạy
DIEM_VAO = "autotone_gui.py"
#[[ tu_kiem PHAI co trong goi. autotone_gui chi import no BEN TRONG main(), ma
#   PyInstaller do import theo tinh nen khong thay — thieu no thi lenh tu kiem
#   tren goi da build khong chay duoc, tuc mat luon cach kiem thu goi.
#]]
#[[ MOI MODULE CUA CHINH DU AN MA APP CO GOI TOI DEU PHAI CO O DAY.
#
#   PyInstaller do import theo TINH. Module nao chi duoc import BEN TRONG mot
#   ham thi no khong thay, va goi ra thieu file do — app van mo binh thuong,
#   chi hong dung cai nut goi toi no, va hong trong im lang vi cho goi thuong
#   boc `except Exception`.
#
#   10/9 da phat hien dung kieu do: thongso_lr va xuat_lr (khau 5 — doc thong
#   so Export cua Lightroom, va nut Export trong app) deu chi duoc import trong
#   ham, va deu khong co trong bang nay. Ban .exe se im lang khong lam gi khi
#   bam. kiem_dong_goi.py gio tu ra soat bang nay theo cay cu phap.
#]]
NGAM = ["autotone", "giao_dien", "duong_dan", "khoa", "trang_thai", "thu_gu",
        "retouch", "learn_corrections", "khoi_phuc", "tu_kiem",
        "duyet", "duyet_ui", "xuat_lr", "thongso_lr", "tai_nguyen",
        "ban_quyen", "xem_truoc",
        #[[ cap_nhat: auto-update code + model. autotone_gui.main() va launcher
        #   chay.py deu import no trong try/except (de ban cu thieu no van chay)
        #   -> PyInstaller khong do duoc import trong try, phai khai o day. Thieu
        #   no thi ban .exe KHONG bao gio ap duoc ban va, va im lang. ]]
        "cap_nhat",
        #[[ luoi_anh: luoi anh cua man chinh (3/10 toi). autotone_gui import
        #   no BEN TRONG _build_luoi() — PyInstaller khong do duoc import nam
        #   trong ham, thieu o day la ban .exe mo len khong dung duoc man chinh. ]]
        "luoi_anh",
        #[[ khung_anh: anh lon cua mo-dun Retouch (3/10 toi) — cung import
        #   trong ham (_dung_trang), cung ly do. ]]
        "khung_anh"]

#[[ MODULE THU VIEN NGOAI PyInstaller KHONG TU THAY (NGAM chi cho module cua du
#   an — kiem_dong_goi canh).
#
#   PIL._tkinter_finder (6/10 — ban macOS mo len chet NGAY: "No module named
#   'PIL._tkinter_finder'" o ImageTk.PhotoImage khi dung nut dau tien). Lan dau
#   dua anh vao Tk, Pillow nap _imagingtk (ma C); tren macOS / Linux CHINH
#   _imagingtk import PIL._tkinter_finder de tim thu vien tkinter — import tu ma
#   C nen PyInstaller khong thay. Windows khong can (_imagingtk tu tim) nen ban
#   .exe chua tung loi. ]]
NGAM_NGOAI = ["PIL._tkinter_finder", "PIL._imagingtk"]

#[[ `tai_nguyen` PHAI co trong NGAM, ke ca o ban day du.
#
#   autotone_gui goi no trong `try: import tai_nguyen / except: pass` — nen
#   thieu no thi KHONG co loi nao het, chi la khong bao gio tai duoc gi. Ban
#   nhe lai song bang dung no: goi 82 MB ma khong co trinh tai thi vinh vien
#   khong co torch, va nut Retouch bao thieu tai nguyen mai mai.
#
#   Hong that 20.09: build xong, chay tron, `find dist -name tai_nguyen*`
#   khong ra gi. PyInstaller khong do ra vi duong import nam trong try/except.
#]]

#[[ Module chi co nghia khi goi CO phan retouch. Ban --khong-retouch bo han
#   chung ra, va giao dien tu bao "phan Retouch tam tach khoi ban nay". ]]
NGAM_RETOUCH = ["retouch"]

# Thư mục/dữ liệu phải mang theo: (nguồn, tên trong gói)
TAI_NGUYEN = [("models", "models"), ("AutoTone.lrplugin", "AutoTone.lrplugin")]

#[[ THU MUC jobs/ KHONG DUOC VAO GOI.
#
#   Trong thu muc plugin co jobs/ — nhat ky plugin, cac job da xong, va ban xuat
#   tu catalog Lightroom. Do la TRANG THAI LUC CHAY, khong phai tai nguyen.
#
#   Hong that 4/9: --add-data chep ca thu muc plugin nen goi mang theo luon
#   export_20260903_105234.tsv (buoi 2905, 220 anh) va 40 file .done. Ban .exe
#   chep no ra %LOCALAPPDATA% roi doc phai ban xuat hoa thach do, nen buoi
#   G:\0608 96 anh bi bao "ban xuat chi khop 0 anh" — Lightroom van xuat dung,
#   chi la xuat vao thu muc plugin CUA NO tren o F, con .exe thi doc thu muc
#   plugin cua rieng minh. Hai cho khac nhau va khong ai noi ra.
#
#   Nen truoc khi build, plugin duoc chep sang mot ban SACH trong build/ va
#   --add-data lay tu do. Xem plugin_sach().
#]]
BO_KHOI_PLUGIN = ["jobs"]

# Gói nặng của phần retouch — PyInstaller không tự dò ra hết
RETOUCH_GOI = ["torch", "torchvision", "onnxruntime", "insightface",
               "mediapipe", "cv2", "scipy", "sklearn", "joblib", "skimage"]

#[[ PHAI DONG GOI BANG MOT VENV SACH, KHONG PHAI PYTHON HE THONG.
#
#   Ngay 17.09 build tu Python he thong chet sach: `--collect-submodules`
#   (nam trong `--collect-all`) lam PyInstaller sap voi 0xC0000005, va sap
#   voi MOI goi lon — ke ca numpy. Loi that nam o modulegraph.py:1805,
#   `compile(co_ast, ...)` nem TypeError 'required field missing' vi cay AST
#   bi sua hong truoc do.
#
#   Da loai tru: khong phai loi thu vien nao rieng (numpy cung sap), khong
#   phai phien ban PyInstaller (thu 6.11.1 / 6.22.2 / 6.22.3 deu sap), khong
#   phai tran stack (tang len 64MB van sap), khong phai shell.
#
#   Nguyen nhan: mot goi nao do trong Python he thong lam hong trinh phan
#   tich AST. Tat hook ben ngoai thi het sap — va venv sach chi chua dung
#   thu can thi `--collect-all torch` chay tron.
#
#   CACH DONG GOI:
#       python -m venv venv_build
#       venv_build\Scripts\python -m pip install pyinstaller
#       venv_build\Scripts\python -m pip install torch==2.13.0 ^
#           --index-url https://download.pytorch.org/whl/cu130
#       venv_build\Scripts\python -m pip install pillow opencv-python ^
#           onnxruntime insightface pillow-heif scipy scikit-learn ^
#           scikit-image joblib mediapipe requests psutil tqdm
#       venv_build\Scripts\python dong_goi.py
#
#   `cmd` o duoi dung sys.executable, nen chay file nay BANG venv do la du —
#   khong phai sua gi them.
#]]



def plugin_sach(goc: Path | None = None) -> Path:
    """Bản plugin đã bỏ jobs/ — đây mới là bản được đóng vào gói.

    Trả về đường dẫn bản sạch. Dựng lại mỗi lần build để không bao giờ lệch với
    bản gốc.
    """
    g = Path(goc or GOC)
    nguon = g / "AutoTone.lrplugin"
    dich = g / "build" / "plugin_sach" / "AutoTone.lrplugin"
    if dich.exists():
        shutil.rmtree(dich, ignore_errors=True)
    dich.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(nguon, dich,
                    ignore=shutil.ignore_patterns(*BO_KHOI_PLUGIN))
    return dich


def saytool_du(goc_tool) -> Path:
    """Bản saytool ĐỦ để chạy khi không còn thư mục gốc. -> đường dẫn bản đó.

    #[[ VI SAO PHAI CO HAM NAY — mot cai bay that, o dung tinh nang chinh.
    #
    #   saytool/loi/blemish_apply.py (chinh la buoc "Xoa khuyet diem", mac dinh
    #   100) goi:
    #       import blem_net3 as b3      (dong 24)
    #       import blem_gpu as bg       (trong load_net, khi mo hinh la ban U-net)
    #
    #   Hai module do KHONG nam trong goi saytool — chung nam o THU MUC GOC cua
    #   ToolCloneEvoto. Chay tu ma nguon thi khong lo ra, vi retouch.py dat
    #   cwd = thu muc goc nen Python tim thay chung. Nhung ban dong goi chi mang
    #   theo saytool/ va mo_hinh/, khong mang thu muc goc.
    #
    #   Do that: dat mot thu muc chi co saytool/ + mo_hinh/ roi nap thu ->
    #       ModuleNotFoundError: No module named 'blem_net3'
    #   va saytool KHONG dung lai: no in mot dong "! BO QUA Xoa khuyet diem: ..."
    #   roi chay tiep cac buoc khac. Tuc goi van chay, van ra anh, chi la tinh
    #   nang chinh da tat — va dong bao do troi qua giua hang tram dong nhat ky.
    #
    #   dong_bo.py ben ToolCloneEvoto co danh sach FILES de chep module loi vao
    #   goi, nhung blem_net3.py va blem_gpu.py khong co trong danh sach do.
    #
    #   O day KHONG ghi cung ten hai file. Doc cay cu phap cua tung file trong
    #   saytool/loi/, tim moi `import X` cap cao nhat khong giai duoc trong goi,
    #   roi chep X.py tu thu muc goc vao. Them module moi ben kia thi cho nay tu
    #   theo. Thieu file thi DUNG BUILD, chu khong dong ra mot goi tat tinh nang.
    #]]
    """
    import ast
    import sys as _sys
    g = Path(goc_tool)
    nguon = g / "saytool"
    dich = GOC / "build" / "saytool_du" / "saytool"
    if dich.parent.exists():
        shutil.rmtree(dich.parent)
    shutil.copytree(nguon, dich, ignore=shutil.ignore_patterns("__pycache__"))

    trong_goi = {f.stem for f in dich.rglob("*.py")}
    ben_ngoai = set(_sys.stdlib_module_names) | {
        "cv2", "numpy", "torch", "torchvision", "PIL", "scipy", "skimage",
        "sklearn", "mediapipe", "insightface", "onnxruntime", "onnx", "tqdm",
        "matplotlib", "requests", "joblib", "flask", "werkzeug", "gradio",
        # Hai ten duoi day la thu vien PyPI, khong phai module noi bo cua
        # ToolCloneEvoto. Thieu chung o danh sach nay thi vong quet doi phai
        # co file .py cung thu muc va chan dong goi — dung loi gap 17.09.
        #
        #   psutil  : ghep_dct/toc_do dung de doc RAM
        #   jpeglib : TUY CHON. ghep_dct.co_the_dung() tu kiem tra va lui ve
        #             cach ghi thuong khi khong co. Ban .exe dang chay cung
        #             khong co no.
        "psutil", "jpeglib"}

    can, da_xet = [], set()
    hang_doi = sorted(dich.rglob("*.py"))
    while hang_doi:
        f = hang_doi.pop()
        try:
            cay = ast.parse(f.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for n in ast.walk(cay):
            if not isinstance(n, ast.Import):
                continue
            for a in n.names:
                ten = a.name.split(".")[0]
                if ten in trong_goi or ten in ben_ngoai or ten in da_xet:
                    continue
                da_xet.add(ten)
                nguon_f = g / f"{ten}.py"
                if not nguon_f.is_file():
                    raise SystemExit(
                        f"  [!] {f.name} goi `import {ten}` nhung khong thay "
                        f"{nguon_f}." + chr(10) +
                        "      Khong dong goi tiep — goi ra se tat "
                        f"mot tinh nang ma khong bao loi.")
                #[[ Chep vao saytool/loi/: loi/__init__.py da tu them chinh thu
                #   muc do vao duong tim module, nen `import blem_net3` giai duoc
                #   ma khong phai sua mot dong nao ben ToolCloneEvoto.
                #]]
                shutil.copy2(nguon_f, dich / "loi" / nguon_f.name)
                trong_goi.add(ten)
                can.append(ten)
                hang_doi.append(dich / "loi" / nguon_f.name)
    if can:
        print(f"  saytool: chép thêm {len(can)} module lõi từ thư mục gốc: "
              + ", ".join(sorted(can)))
    return dich


def mo_hinh_du(goc_tool) -> Path:
    """Thư mục mô hình ĐỦ để chạy mà không phải tải gì. -> đường dẫn thư mục đó.

    Gom ba nguồn vào một chỗ rồi mới đóng vào gói:

        <tool>/mo_hinh/                  vet.pt, nong_cam.pt, liquify/
        ~/.cache/skin_spike/             resnet34_faceparse.onnx   (94 MB)
        ~/.insightface/models/buffalo_l  nhận diện mặt            (326 MB)

    Hai thứ sau saytool VỐN TỰ TẢI lúc chạy. Mang theo thì gói nặng thêm ~420 MB
    nhưng chạy được ngay, không cần mạng và không phụ thuộc github.com — địa chỉ
    bị chặn ở khá nhiều mạng công ty. Chưa có sẵn thì vẫn đóng gói, chỉ cảnh báo:
    lúc đó máy người dùng sẽ tự tải như cũ. Chạy nap_mo_hinh.py trước để có.
    """
    g = Path(goc_tool)
    dich = GOC / "build" / "mo_hinh_du"
    if dich.exists():
        shutil.rmtree(dich)
    dich.mkdir(parents=True)

    nguon = g / "mo_hinh"
    if nguon.is_dir():
        #[[ CHI CHEP MO HINH SAYTOOL THAT SU NAP.
        #
        #   Thu muc mo_hinh/ cua may huan luyen con giu ca ban nhap: vet.pt
        #   dang dung, nhung canh no la vet_cu_2609.pt, vet_700_3009.pt,
        #   vet_b48_3009.pt, vet_16k_2909.pt... Moi ban 10-22 MB.
        #
        #   Do that 01/10: chep ca thu muc ra 854 MB, trong khi phan THAT SU
        #   can chi 300 MB. Nguoi dung tai them 554 MB ban nhap cua mot cuoc
        #   huan luyen ho khong lien quan.
        #
        #   Danh sach duoi lay tu chinh ma saytool: grep "mo_hinh/..." trong
        #   saytool/*.py. Them mo hinh moi ben do thi phai them vao day — neu
        #   quen, goi se thieu file va buoc do tat lang le.
        #]]
        CAN = {"vet.pt", "vet_body.pt", "min_da.pt", "dodge_burn.pt",
               "da_body.pt", "da_body_nho.pt", "da_deu.pt",
               "nhan.pt", "nong_cam.pt", "toc.pt", "toc_mn.pt",
               # 4/10: 7 tinh nang mat moi (saytool/buoc_mat_them.py, du lieu ev3) - chua hoc xong thi
               # tep chua co, mo_hinh_du bo qua; co roi thi tu vao goi (khong co o day = buoc tat lang le)
               "not_ruoi.pt", "bong_dau.pt", "quang_tham.pt", "bong_mat.pt",
               "kinh.pt", "lo_mui.pt", "nhan_moi.pt"}
        bo_qua = []
        for f in sorted(nguon.iterdir()):
            if f.is_dir():
                shutil.copytree(f, dich / f.name, dirs_exist_ok=True)
            elif f.suffix == ".pt" and f.name not in CAN:
                bo_qua.append(f.name)
            else:
                shutil.copy2(f, dich / f.name)
        if bo_qua:
            print(f"  bỏ {len(bo_qua)} mô hình bản nháp "
                  f"({', '.join(bo_qua[:3])}{'…' if len(bo_qua) > 3 else ''})")

    thieu = []
    dem = Path(os.environ.get("SKIN_SPIKE_CACHE",
                              Path.home() / ".cache" / "skin_spike"))
    fp = dem / "resnet34_faceparse.onnx"
    if fp.is_file():
        shutil.copy2(fp, dich / fp.name)
    else:
        thieu.append("resnet34_faceparse.onnx (phân vùng da)")
    #[[ YuNet = bo do mat DU PHONG cua saytool khi insightface hong. saytool tu
    #   TAI no vao SKIN_SPIKE_CACHE (= mo_hinh trong goi) — Program Files khong
    #   ghi duoc nen ban cai khong bao gio co (6/10: insightface hong -> 0 mat). ]]
    yn = dem / "face_detection_yunet_2023mar.onnx"
    if yn.is_file():
        shutil.copy2(yn, dich / yn.name)
    else:
        thieu.append("face_detection_yunet_2023mar.onnx (dò mặt dự phòng)")

    bf = Path.home() / ".insightface" / "models" / "buffalo_l"
    if bf.is_dir() and list(bf.glob("*.onnx")):
        shutil.copytree(bf, dich / "insightface" / "models" / "buffalo_l")
    else:
        thieu.append("buffalo_l (nhận diện mặt)")

    co = sum(f.stat().st_size for f in dich.rglob("*") if f.is_file())
    print(f"  mô hình: {co / 1e6:.0f} MB")
    if thieu:
        print("  [ ] Chưa có sẵn: " + ", ".join(thieu))
        print("      Gói vẫn đóng được, nhưng lần đầu bấm Retouch máy sẽ tự tải.")
        print(f"      Muốn mang theo: python nap_mo_hinh.py \"{g}\"  rồi đóng lại.")
    return dich


#[[ CAC GOI TACH RA TAI SAU (ban --nhe).
#
#   Do that tren goi 4.1 GB ngay 20.09:
#       torch (co CUDA)   2779 MB
#       mo hinh retouch    554 MB
#       mediapipe          154 MB   (keo theo jaxlib 229 MB + matplotlib)
#       scipy              115 MB
#       sklearn             45 MB
#       onnxruntime         45 MB
#       skimage             25 MB
#       ------------------------------------
#       loi (can sang)     189 MB   <- numpy 34 + cv2 139 + Pillow 16
#
#   Ban --nhe bo het phan tren ra. Nguoi dung tai app xong la can sang duoc
#   ngay; retouch tai them khi bam nut lan dau.
#
#   DA DO, KHONG DOAN: chan ca 12 goi duoi bang meta_path roi nap thu thi
#   autotone, autotone_gui, retouch, tu_kiem, duyet, xuat_lr, thongso_lr,
#   eye_ear DEU nap tron. Tuc khau can sang khong cham vao goi nao o day —
#   chung chi duoc goi ben trong ham, luc nguoi dung bam Retouch.
#
#   `scipy` khong file nao import thang, nhung sklearn/skimage keo theo, nen
#   phai di cung ca cum — bo le mot minh sklearn thi van con 115 MB scipy.
#
#   `jax`/`jaxlib` KHONG file nao trong ca hai du an import — chung vao theo
#   mediapipe. Loai luon o moi ban, ke ca ban day du: bot 229 MB khong mat gi.
#]]
GOI_TACH = ["torch", "torchvision", "torchgen", "functorch",
            "mediapipe", "sympy", "networkx", "mpmath",
            "matplotlib", "mpl_toolkits", "fontTools", "sounddevice",
            "onnxruntime", "insightface", "scipy", "sklearn", "skimage",
            "joblib"]

# Vao theo mediapipe nhung khong ai import — bo o MOI ban.
GOI_BO_HAN = ["jax", "jaxlib"]

#[[ BAN DAY DU (--torch-trong-goi): NHOI torch vao goi de Retouch hien DU 8 tinh
#   nang NGAY, khong phai tai gi, khong con "can tai torch"/"chua hoi duoc tool".
#
#   HAI BAY DA GAP (ghi lai de khong di lai):
#
#   BAY 1 — de quy khi phan tich torch.
#     collect_submodules("torch") (goi boi --collect-all va boi hook-torch) DUYET
#     DE QUY ca cay torch. Mac dinh gioi han de quy Python 1000 -> tran stack C
#     -> tien trinh PyInstaller chet 0xC0000005. Da chan bang
#     sys.setrecursionlimit(5000) o DAU tien trinh (cmd qua `-c`, xem lenh()).
#
#   BAY 2 — AST hong khi di qua fsspec (va vai dep async cua torch).
#     Ngay ca khi khong tran, modulegraph di SAU qua torch -> torch.hub ->
#     fsspec -> fsspec.asyn -> ... (636 frame). Toi mot module nao do,
#     modulegraph._safe_import_module goi compile(co_ast, ...) voi mot cay AST no
#     tu sua HONG -> TypeError: required field "id" missing from Name. Day KHONG
#     phai loi fsspec (ma no sach), ma la loi modulegraph tren Python 3.12 khi
#     cay import qua sau. saytool KHONG dung fsspec (torch.load tren file CUC BO,
#     khong tai tu xa), nen LOAI fsspec + may dep async di kem. Cat duoc nhanh do
#     thi do thi torch nong hon nhieu va het luon bay AST.
#
#   CACH DUNG (da kiem): --collect-all torch (de DANG KY submodule — neu chi
#   --hidden-import+--copy-metadata thi file torch co mat nhung KHONG dang ky,
#   `import torch` trong goi bao ModuleNotFoundError) + LOAI cac nhanh duoi.
#
#   saytool nap model bang torch.load + load_state_dict, KHONG dung torch.jit/
#   compile/onnx/fx/distributed. Nhung torch.fx KHONG loai duoc: torch/__init__.py
#   co `import torch.fx.experimental.sym_node` o top-level -> loai la `import
#   torch` gay. Nen chi loai nhung nhanh KHONG bi __init__ cham toi.
#
#   TORCH_NE: cac GOI CHI de CAT CHUOI IMPORT lam modulegraph sap voi
#   "TypeError: required field 'id' missing from Name" (bug AST cua modulegraph
#   tren Python 3.12 khi di qua mot so chuoi import sau). KHONG loai nhanh con
#   cua torch (vd torch.utils.benchmark): --collect-all torch gom chung roi, loai
#   lai chi tao "Hidden import not found" va KHONG chan duoc bug AST (bug nam o
#   chuoi fsspec/narwhals, khong phai torch). Chi loai cac GOI NGOAI ma saytool
#   khong dung va la thu pham cat chuoi:
#     fsspec + async (aiohttp/yarl/multidict/requests_oauthlib): torch.hub tai xa
#     narwhals: adapter pandas/polars keo theo sklearn/skimage -> chuoi sap AST
#   saytool khong dung cai nao trong so nay (torch.load file CUC BO, khong narwhals).
TORCH_NE = [
    "fsspec", "aiohttp", "requests_oauthlib", "yarl", "multidict",
    "narwhals",
]


def co_retouch(goc_tool: Path | None) -> bool:
    return bool(goc_tool and (Path(goc_tool) / "saytool" / "cli.py").is_file())


#[[ BAO MAT (4/10): False = chỉ mã hoá LÕI (bao_mat.MA_HOA: thuật toán, retouch,
#   khoá, giao diện, điểm vào). True = mã hoá MỌI .py ship được — kín hơn nhưng
#   build lâu hơn và nhiều module hơn là nhiều chỗ có thể vướng. Chỉ bật khi đã
#   build trót lọt bản chỉ-lõi trên cả Windows lẫn Mac. ]]
MA_HOA_HET = False


def co_the_import(ten: str) -> bool:
    """True nếu gói `ten` CÓ THỂ import trong môi trường đang build.

    #[[ --collect-all X BẮT BUỘC X phải cài trong venv build: no goi
    #   collect_submodules(X) — import X de duyet cay con; X khong co thi
    #   PyInstaller BAO LOI va dung ca build. Venv build (venv_build) co du
    #   torch/cv2/onnx/insightface/mediapipe/scipy/sklearn/skimage/joblib NHUNG
    #   KHONG co torchvision (saytool khong dung — model nap bang torch.load +
    #   load_state_dict, da kiem 8 buoc nap du khong co torchvision). Nen o day
    #   BO QUA goi nao khong import duoc, thay vi ep cai hay lam chet build.
    #   importlib.util.find_spec KHONG thuc thi goi (nhanh, khong keo torch vao
    #   RAM) — chi tra None neu khong tim thay. ]]
    """
    import importlib.util
    try:
        return importlib.util.find_spec(ten) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def lenh(he: str, retouch: bool = True, goc_tool: Path | None = None,
         sach: bool = True, nhe: bool = False,
         goc_nguon: Path | None = None, diem_vao: str | None = None,
         ngam_them=None, giu_mo_hinh: bool = False,
         icon: Path | None = None, mac_thu_muc: bool = True,
         torch_trong_goi: bool = False) -> list:
    """Dựng dòng lệnh PyInstaller. Tách riêng để kiểm được mà không phải build.

    he:  "win" | "mac"
    nhe: bỏ thư viện nặng ra khỏi gói — xem GOI_TACH.
    icon: file .ico (Windows) / .icns (macOS) gắn cho .exe/.app. None = mặc định.
    giu_mo_hinh: với --nhe, VẪN mang mô hình (dùng cho bản bảo mật: mô hình đã
        mã hoá ~300 MB, mang theo để tránh lỗ hổng cwd và chạy offline). Không
        ảnh hưởng torch — torch vẫn tải sau theo --nhe.
    torch_trong_goi: NHỒI torch vào gói (bản đầy đủ). Dùng --hidden-import torch
        + --copy-metadata torch thay cho --collect-all torch, kèm loại TORCH_LOAI
        các nhánh nặng không dùng. Bật cái này thì KHÔNG được --nhe (torch phải
        ở lại). Xem TORCH_LOAI. Retouch khi đó hiện đủ 8 tính năng ngay.

    #[[ BAO MAT (4/10): goc_nguon = cây nguồn đã mã hoá (bao_mat.dung_cay_nguon)
    #   thay cho GOC. diem_vao = launcher mỏng "chay.py". ngam_them = MỌI module
    #   trong cây đó: điểm vào đã biên dịch nên PyInstaller không tự dò được
    #   import của nó, phải khai hết. --paths trỏ PyInstaller tìm module trong
    #   cây mã hoá TRƯỚC. Mặc định (không bật) thì y hệt bản cũ: goc_nguon=GOC,
    #   diem_vao=autotone_gui.py. ]]
    """
    goc_nguon = goc_nguon or GOC
    diem_vao = diem_vao or DIEM_VAO
    ngan = ";" if he == "win" else ":"        # dấu ngăn của --add-data
    #[[ GOI PyInstaller qua -c, CHAY TREN MOT THREAD STACK LON.
    #
    #   Nhoi torch vao goi lam PyInstaller phan tich hang nghin submodule torch
    #   bang DE QUY sau. Hai lop phai lo:
    #     1) Gioi han de quy PYTHON (mac dinh 1000) -> RecursionError.
    #        -> sys.setrecursionlimit(5000).
    #     2) Stack C cua THREAD (mac dinh Windows ~1 MB) tran TRUOC khi cham
    #        limit Python -> 0xC0000005 (access violation), KHONG phai
    #        RecursionError, va KHONG deterministic (tuy thu tu module). Da gap
    #        that: build chay tron mot lan, lan sau cung tham so chet 0xC0000005
    #        ngay giua phan tich (sau hook-urllib3). setrecursionlimit KHONG cuu
    #        duoc cai nay vi no la stack C, khong phai Python.
    #        -> threading.stack_size(256 MB) + chay run() TREN MOT THREAD moi:
    #           thread do co stack 256 MB, du sau cho cay torch. Main thread
    #           khong doi stack size duoc giua chung, nen phai la thread rieng.
    #
    #   CLI thuan khong set duoc hai cai nay. Code nhieu dong (def _go) truyen
    #   qua -c de hong xuong dong tren shell, nen GHI RA MOT FILE wrapper roi
    #   chay `python wrapper.py <args>`. File nam trong build/, dung lai moi lan.
    #   Loi trong thread tra ve dung ma thoat (SystemExit tu run() bat rieng). ]]
    _wrapper = GOC / "build" / "chay_pyinstaller.py"
    _wrapper.parent.mkdir(parents=True, exist_ok=True)
    _wrapper.write_text(
        "import sys, threading, traceback\n"
        "sys.setrecursionlimit(50000)\n"
        #[[ Stack 128 MB: Windows threading.stack_size KHONG nhan 256 MB
        #   (ValueError) nhung NHAN 128 MB. 64 MB van thinh thoang 0xC0000005 giua
        #   luc gom torch (de quy sau, khong deterministic) — da gap v10/v11. 128
        #   MB (boi so 64 KB) gap doi, giam xac suat tran. Boc try: ban nao khong
        #   nhan thi ha ve 64 MB roi mac dinh. ]]
        "for _mb in (128, 64):\n"
        "    try:\n"
        "        threading.stack_size(_mb * 1024 * 1024)\n"
        "        break\n"
        "    except (ValueError, RuntimeError):\n"
        "        pass\n"
        "from PyInstaller.__main__ import run\n"
        "_ret = {'code': 0}\n"
        "def _go():\n"
        "    try:\n"
        "        run()\n"
        "    except SystemExit as e:\n"
        "        _ret['code'] = e.code if e.code is not None else 0\n"
        "    except BaseException:\n"
        "        traceback.print_exc()\n"
        "        _ret['code'] = 1\n"
        "t = threading.Thread(target=_go)\n"
        "t.start()\n"
        "t.join()\n"
        "sys.exit(_ret['code'] or 0)\n",
        encoding="utf-8",
    )
    cmd = [sys.executable, str(_wrapper), "--noconfirm", "--onedir",
           "--name", TEN]
    #[[ --windowed: Windows -> .exe GUI (khong console). macOS -> LUON tao .app
    #   BUNDLE. Nhung .app bundle lam cv2 recursion KHONG sua duoc (symlink
    #   Frameworks<->Resources -> loader cv2 lac duong, du .so + config day du —
    #   da thu pin version, collect-binaries, runtime hook, copy tay .so/.dylibs,
    #   TAT CA van recursion). Nen tren macOS KHONG --windowed -> ra THU MUC phang
    #   dist/AutoTone/ (cv2 nam canh nhau nhu Windows/Linux -> het recursion). App
    #   van chay (Tkinter tu mo cua so); bo .command launcher cho de bam, dong ca
    #   thu muc vao .dmg. Windows + bản .app (neu sau nay sua duoc symlink) van
    #   --windowed. ]]
    if not (he == "mac" and mac_thu_muc):
        cmd.append("--windowed")
    #[[ ICON cho .exe/.app. GIU TEN KY THUAT la "AutoTone" (--name), KHONG doi
    #   theo ten hien thi: thu muc du lieu, bundle id, duong_dan.TEN_UD, kiem_goi
    #   deu dua vao "AutoTone". Ten hien thi (shortcut, tieu de cua so) doi o Inno
    #   Setup / tieu de — khong dung toi day. PyInstaller nhan .ico (Windows) hoac
    #   .icns (macOS); truyen .png thi no tu doi tren mot so ban, nhung an toan
    #   nhat la .ico/.icns dung he. ]]
    if icon:
        cmd += ["--icon", str(icon)]
        #[[ --icon chi NHUNG icon vao .exe (Explorer/shortcut thay). Nhung CUA SO
        #   Tkinter luc chay KHONG lay tu .exe — no can mot file .ico de goi
        #   root.iconbitmap(). Nen mang luon file icon vao GOC tai nguyen goi
        #   (DEST = ".", GIU TEN GOC icon.ico), de autotone_gui.main() goi
        #   dd.tai_nguyen("icon.ico").
        #
        #   BAY (da sap 4/10): --add-data SRC;DEST thi DEST la THU MUC DICH,
        #   KHONG phai ten file moi. "icon.ico;app.ico" tao THU MUC app.ico/
        #   chua icon.ico -> dd.tai_nguyen("app.ico") tro vao mot THU MUC, khong
        #   phai .ico -> iconbitmap im lang that bai -> cua so van long vu. Dung:
        #   DEST = "." (goc), roi tim theo TEN GOC cua file icon. ]]
        cmd += ["--add-data", f"{Path(icon)}{ngan}."]
    if sach:
        cmd.append("--clean")
    #[[ Chi them --paths khi ma hoa (goc_nguon la cay staging): de duong build
    #   mac dinh KHONG doi mot chu so voi ban cu. ]]
    if goc_nguon != GOC:
        cmd += ["--paths", str(goc_nguon)]

    for nguon, dich in TAI_NGUYEN:
        #[[ Rieng plugin thi lay BAN SACH (da bo jobs/) — xem BO_KHOI_PLUGIN.
        #]]
        p = plugin_sach() if nguon == "AutoTone.lrplugin" else (GOC / nguon)
        cmd += ["--add-data", f"{p}{ngan}{dich}"]

    for m in NGAM:
        if not retouch and m in NGAM_RETOUCH:
            continue
        cmd += ["--hidden-import", m]
    for m in NGAM_NGOAI:
        cmd += ["--hidden-import", m]
    #[[ Khi mã hoá: khai HẾT module trong cây — xem chú thích đầu hàm. ]]
    for m in (ngam_them or []):
        if not retouch and m in NGAM_RETOUCH:
            continue
        cmd += ["--hidden-import", m]

    #[[ Loai tru o CA HAI muc: --exclude-module chan PyInstaller keo module vao
    #   theo duong import, con phan xoa file sau khi build (xem don_goi) chan
    #   duong chep thang. Chi lam mot trong hai thi tao_ma.py van co the lot.
    #]]
    for f in LOAI_TRU:
        cmd += ["--exclude-module", Path(f).stem]

    #[[ Bo jax/jaxlib o MOI ban: khong ai import, ma nang 229 MB.
    #   Ban --nhe bo them cac goi nang khac — chung se tai ve sau.
    #]]
    for g in GOI_BO_HAN + (GOI_TACH if nhe else []):
        cmd += ["--exclude-module", g]

    if retouch:
        #[[ Ban --nhe van mang saytool + retouch.py (vai MB), chi bo THU VIEN.
        #   Nho vay giao dien van co day du nut retouch va biet phai tai gi;
        #   thieu thu vien thi no bao "chua tai tai nguyen", khong phai bien mat.
        #]]
        for g in RETOUCH_GOI:
            if nhe and g in GOI_TACH:
                continue
            #[[ torch TRONG BAN DAY DU (torch_trong_goi): DUNG --collect-all torch.
            #
            #   DA THU --hidden-import + --copy-metadata (khong collect-all) de ne
            #   de quy: KET QUA torch/ co file (284 MB, du .pyd + torch/lib/*.dll)
            #   NHUNG `import torch` trong goi bao ModuleNotFoundError. Vi sao:
            #   --copy-metadata chi chep metadata, --hidden-import chi them MOI
            #   `torch` goc vao do thi; hook-torch chep .py/.dll vao _internal/torch
            #   NHU DU LIEU, nhung cac SUBMODULE torch KHONG duoc dang ky vao bang
            #   module cua goi -> trinh nap dong bang (PyiFrozenImporter) khong biet
            #   torch nam o do -> khong tim thay. (File co mat != module nap duoc.)
            #
            #   --collect-all torch goi collect_submodules("torch") -> DANG KY het
            #   submodule vao do thi, va do la cach DUY NHAT torch nap duoc trong
            #   goi. De quy cua collect_submodules da duoc chan bang
            #   setrecursionlimit(5000) o dau tien trinh (xem cmd qua `-c`). Van
            #   --collect-all torch de DANG KY submodule (xem TORCH_NE: chi
            #   --hidden-import+--copy-metadata thi `import torch` bao
            #   ModuleNotFoundError). Kem LOAI TORCH_NE: cat nhanh fsspec/async
            #   (bay AST modulegraph) + vai nhanh nang khong dung. Dat
            #   --exclude-module TRUOC --collect-all de modulegraph khong di vao
            #   chung luc duyet torch. setrecursionlimit(5000) lo phan de quy.
            #   Chi ap khi torch_trong_goi. ]]
            if g == "torch" and torch_trong_goi:
                for _x in TORCH_NE:
                    cmd += ["--exclude-module", _x]
                cmd += ["--collect-all", "torch"]
                continue
            #[[ cv2 TREN macOS — KHONG --collect-all, MA --collect-binaries +
            #   --collect-data (da tra tan goc 4/10, bản .app van recursion sau
            #   khi pin opencv 4.11).
            #
            #   LOI THAT: ".app" chay len bao "recursion is detected during
            #   loading of cv2 binary extensions". Day KHONG phai de quy that, ma
            #   la loader cv2 KHONG tim thay cv2.abi3.so + .dylibs canh __init__
            #   -> importlib nap lai cv2/__init__ -> co OpenCV_LOADER da set ->
            #   nem "recursion". Tuc THIEU native .so trong goi.
            #
            #   VI SAO THIEU, va vi sao Windows khong bi: app nay dung CYTHON —
            #   cv2 duoc import boi module .so da bien dich (khong phai .py trong
            #   PYZ), nen PyInstaller do import TINH KHONG thay `import cv2` ->
            #   hook-cv2.py KHONG chay -> .so + .dylibs khong vao goi. Windows
            #   dung --collect-all cv2 nen binaries vao du (may rui). macOS bo
            #   --collect-all (dung, vi no keo .py config dat lech cho sau khi
            #   .app cross-link Frameworks/Resources) NHUNG lai thanh KHONG gi
            #   collect cv2 -> thieu .so. Nen o day collect DUNG binaries + data:
            #     --collect-binaries cv2 : cv2.abi3.so + .dylibs/*.dylib  <- quan trong nhat
            #     --collect-data cv2     : config.py / config-3.py loader doc
            #   (hook-cv2 chuan cung chi lam dung hai cai nay.) Them hidden-import
            #   cv2 o NGAM. Van KHONG --collect-all tren mac. ]]
            if he == "mac" and g == "cv2":
                cmd += ["--collect-binaries", "cv2", "--collect-data", "cv2",
                        "--hidden-import", "cv2"]
                continue
            #[[ --collect-all can goi PHAI cai trong venv build — khong co thi
            #   PyInstaller chet. Bo qua goi vang mat (vd torchvision: saytool
            #   khong dung, venv build khong cai). Xem co_the_import(). CHI bo
            #   khi build that (co the_import doc venv hien tai); o che do --thu
            #   van bo giong het de dong lenh in ra trung voi luc build. ]]
            if not co_the_import(g):
                print(f"  (bỏ --collect-all {g}: không có trong môi trường build)")
                continue
            cmd += ["--collect-all", g]
        if goc_tool:
            cmd += ["--add-data", f"{saytool_du(goc_tool)}{ngan}saytool"]
            #[[ MO HINH TRONG GOI HAY TAI SAU.
            #
            #   Ban --nhe THUONG (chua ma hoa): mo_hinh/ nang 554 MB nen KHONG
            #   mang, tai_nguyen.py tai goi "mo-hinh" ve lan dau bam Retouch.
            #
            #   Ban --nhe CO BAO MAT (giu_mo_hinh=True): mo hinh DA MA HOA (~300
            #   MB, IP tu train) VAN mang theo — nhe hon ban tho, va quan trong
            #   hon: saytool nap mo hinh theo CWD = thu muc goi; de model trong
            #   goi thi khong dinh lo hong "model o tai_nguyen nhung cwd o goi".
            #   torch (thu vien, khong phai IP) van tai sau nhu --nhe.
            #
            #   Van mang saytool/ (vai MB) de giao dien biet co nhung buoc nao.
            #]]
            if (not nhe) or giu_mo_hinh:
                cmd += ["--add-data", f"{mo_hinh_du(goc_tool)}{ngan}mo_hinh"]
    else:
        for g in RETOUCH_GOI:
            if g != "cv2":                     # cv2 thì AutoTone vẫn cần
                cmd += ["--exclude-module", g]
        #[[ Bo han retouch.py ra khoi goi, khong chi bo thu vien nang.
        #
        #   De no lai thi giao dien van dung duoc khung Retouch, van do tim
        #   ToolCloneEvoto, van hien ba thanh keo du phong — tuc trong y het
        #   mot tinh nang co that ma bam vao khong bao gio chay. Bo han ra thi
        #   _lam_retouch() bat duoc ImportError va noi thang la phan nay da
        #   tach khoi ban nay. ]]
        for m in NGAM_RETOUCH:
            cmd += ["--exclude-module", m]

    if he == "mac":
        #[[ --osx-bundle-identifier chi co nghia khi tao .app BUNDLE. Onedir thu
        #   muc (mac_thu_muc) khong co bundle nen bo. ]]
        if not mac_thu_muc:
            cmd += ["--osx-bundle-identifier", "vn.saymedia.autotone"]
        #[[ RUNTIME HOOK cv2 — du phong cho --collect-binaries cv2 o tren. Neu
        #   cv2 nam trong thu muc con python-3.x (mot so build), hook nay chen
        #   duong dan .so len sys.path truoc _MEIPASS de tranh recursion. Khong
        #   co thu muc do thi hook no-op. Chi gan tren mac (loi .app). Chay tu
        #   goc_nguon neu la cay ma hoa, else GOC. ]]
        rthook = (goc_nguon / "rthook_cv2.py")
        if not rthook.is_file():
            rthook = GOC / "rthook_cv2.py"
        if rthook.is_file():
            cmd += ["--runtime-hook", str(rthook)]

    cmd.append(str(goc_nguon / diem_vao))
    return cmd


def kem_goi_gpu(ra_goi: Path) -> bool:
    """Đặt gói torch CUDA vào <gói>/goi_kem/ — bản cài Windows mang sẵn, khỏi tải.

    #[[ 6/10 — user: "dong goi chung het vao thanh 1 file cai dat de khong bi
    #   tinh trang thieu file". Lay DUNG goi app von tai (tai_nguyen.GOI["torch"],
    #   tai tu Releases, kiem SHA-256 cua zip noi lai) vao build/goi_kem_tai/ —
    #   tai MOT lan, lan build sau dung lai — roi chep vao goi. App nap no qua
    #   tai_nguyen.nap("torch") (uu tien goi kem, chi khi may co card NVIDIA). ]]
    """
    try:
        sys.path.insert(0, str(GOC))
        import tai_nguyen as tn
    except Exception as ex:                                  # noqa: BLE001
        print(f"  [!] Không nạp được tai_nguyen: {ex}")
        return False
    g = tn.GOI.get("torch")
    if g is None:
        print("  [!] tai_nguyen không khai gói torch.")
        return False
    kho = GOC / "build" / "goi_kem_tai"
    cu = os.environ.get("AUTOTONE_DATA")
    os.environ["AUTOTONE_DATA"] = str(kho)
    try:
        if not tn.da_co(g):
            print(f"  Tải gói kèm {g.thu_muc} ({g.mb} MB, một lần)...", flush=True)
            moc = [0]

            def td(pha, da, tong):
                pt = int(100 * da / tong) if tong else 0
                if pt >= moc[0] + 10:
                    moc[0] = pt - pt % 10
                    print(f"    {pha} {pt}%", flush=True)
            tn.tai(g, tien_do=td)
        nguon = tn.thu_muc_goi(g)
    except Exception as ex:                                  # noqa: BLE001
        print(f"  [!] Không tải được gói kèm torch: {type(ex).__name__}: {ex}")
        return False
    finally:
        if cu is None:
            os.environ.pop("AUTOTONE_DATA", None)
        else:
            os.environ["AUTOTONE_DATA"] = cu
    dich = Path(ra_goi) / tn.TEN_KEM / g.thu_muc
    if dich.exists():
        shutil.rmtree(dich, ignore_errors=True)
    shutil.copytree(nguon, dich)
    co = sum(f.stat().st_size for f in dich.rglob("*") if f.is_file())
    print(f"  Gói kèm: {dich}  ({co / 1e9:.2f} GB)")
    return True


def tao_ban_nhan(ra_goi: Path) -> list:
    """Tạo sẵn resnet34_faceparse_nhan.onnx trong gói. -> danh sách đã tạo.

    #[[ 6/10. saytool (skin_spike4._ban_nhan) TU TAO ban '_nhan' (mo hinh phan
    #   vung da them ArgMax + Cast uint8: 256 KB/mat thay vi 60 MB, argmax chay
    #   tren GPU) CANH tep goc o lan chay dau. Ban cai o C:\\Program Files (va
    #   .app trong /Applications) KHONG ghi duoc -> moi lan mo xem truoc / chay
    #   retouch lai nap 93 MB, ghi hong, lui ve ban goc (cham hon). Ban cai v21
    #   co tep nay chi vi TINH CO: bai kiem chay tren dist/ da tao no. Tao o day
    #   cho moi ban cai deu co. Bien doi GIONG HET _ban_nhan. Thieu goi onnx thi
    #   bo qua (app van dung ban goc). ]]
    """
    da_tao = []
    for p in Path(ra_goi).rglob("resnet34_faceparse.onnx"):
        q = p.with_name(p.stem + "_nhan.onnx")
        if q.exists():
            continue
        try:
            import onnx
            from onnx import TensorProto, helper
            m = onnx.load(str(p))
            g = m.graph
            g.node.append(helper.make_node("ArgMax", [g.output[0].name], ["nhan64"],
                                           axis=1, keepdims=0))
            g.node.append(helper.make_node("Cast", ["nhan64"], ["nhan"],
                                           to=TensorProto.UINT8))
            del g.output[:]
            g.output.append(helper.make_tensor_value_info("nhan", TensorProto.UINT8, None))
            tam = q.with_suffix(".tam")
            onnx.save(m, str(tam))
            os.replace(tam, q)
            da_tao.append(q)
        except Exception as ex:                              # noqa: BLE001
            print(f"  [!] Không tạo được {q.name}: {type(ex).__name__}: {ex}")
    return da_tao


def don_goi(thu_muc: Path) -> list:
    """Xoá những file lọt vào gói mà lẽ ra không được có. -> danh sách đã xoá."""
    da_xoa = []
    for f in LOAI_TRU:
        for p in Path(thu_muc).rglob(f):
            try:
                p.unlink()
                da_xoa.append(str(p))
            except OSError:
                pass
    return da_xoa


def nen_goi(ra: Path, nen: Path, he: str):
    """Nén gói lại. -> đường dẫn file nén, hoặc None nếu hỏng.

    #[[ TREN macOS PHAI DUNG ditto, KHONG DUOC dung shutil.make_archive.
    #
    #   Goi .app cua PyInstaller CHUA SYMLINK: Contents/Resources va
    #   Contents/Frameworks tro qua lai nhau. shutil.make_archive("zip") di qua
    #   cay thu muc bang os.walk, ma os.walk THEO symlink thu muc — nen no chep
    #   lai toan bo noi dung mot lan nua (zip phinh gap doi), va sau khi giai nen
    #   thi symlink bien thanh ban sao that. Bo cuc .app hong tu do.
    #
    #   ditto la cong cu cua Apple, giu nguyen symlink, quyen chay va co ky.
    #   Khong co ditto thi lui ve tar (cung giu symlink) chu KHONG lui ve zip.
    #]]
    """
    if he == "mac":
        dich = Path(str(nen) + ".zip")
        if shutil.which("ditto"):
            r = subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc",
                                "--keepParent", str(ra), str(dich)])
            return dich if r.returncode == 0 else None
        print("  [!] Không có ditto — dùng tar để giữ symlink.")
        tgz = Path(str(nen) + ".tgz")
        r = subprocess.run(["tar", "-czf", str(tgz),
                            "-C", str(ra.parent), ra.name])
        return tgz if r.returncode == 0 else None

    return Path(shutil.make_archive(str(nen), "zip", root_dir=str(ra.parent),
                                    base_dir=ra.name))


def chot_khoa(cho_phep: bool) -> bool:
    """Chặn đóng gói khi khoá hạn dùng thử đang TẮT.

    VÌ SAO CẦN
        khoa.BAT_KHOA có thể để False trên máy phát triển — hợp lý, vì hạn 72
        giờ là để đưa bản thử cho người khác, không phải để chặn chính mình.
        Nhưng biến đó nằm trong mã nguồn, nên nếu quên bật lại thì bản cài đặt
        giao cho người khác cũng không có khoá, và KHÔNG CÓ DẤU HIỆU GÌ cả —
        app chạy bình thường, chỉ là chạy mãi mãi.

        Một biến tắt/bật lặng lẽ mà hậu quả chỉ lộ ra sau khi đã giao hàng thì
        sớm muộn cũng gây chuyện. Nên chốt ở đây: đóng gói thì phải trả lời
        câu hỏi đó, hoặc bật lại, hoặc gõ --khong-khoa để nói rõ là cố ý.

    Trả về True nếu được phép đóng gói tiếp.
    """
    try:
        sys.path.insert(0, str(GOC))
        import khoa
    except Exception as ex:                                  # noqa: BLE001
        print(f"  [!] Không đọc được khoa.py ({ex}) — bỏ qua chốt khoá.")
        return True
    if getattr(khoa, "BAT_KHOA", True):
        return True
    if cho_phep:
        print("  [!] Đóng gói bản KHÔNG CÓ KHOÁ hạn dùng thử (đã gõ "
              "--khong-khoa). Bản này chạy vĩnh viễn trên mọi máy.")
        return True
    print("  [!] khoa.BAT_KHOA đang là False — khoá hạn dùng thử đang TẮT.")
    print("      Đóng gói lúc này sẽ ra bản chạy vĩnh viễn, không hạn, không "
          "hỏi mã gia hạn.")
    print("      Sửa: mở khoa.py, đổi BAT_KHOA thành True (và đặt lại HAN_ISO "
          "cho đúng đợt).")
    print("      Hoặc nếu CỐ Ý muốn bản không khoá: chạy lại kèm --khong-khoa.")
    return False


def he_dieu_hanh() -> str:
    if sys.platform.startswith("win"):
        return "win"
    if sys.platform == "darwin":
        return "mac"
    return "linux"


def main(argv=None) -> int:
    #[[ Console Windows mac dinh la cp1252, khong ma hoa noi chu Viet — script
    #   nay in "Dang dong goi...", "Da loai khoi goi..." bang tieng Viet nen
    #   chet ngay dong print dau tien voi UnicodeEncodeError, TRUOC khi kip
    #   goi PyInstaller. Ep UTF-8 o day de build chay duoc tu moi console.
    #]]
    for _luong in (sys.stdout, sys.stderr):
        try:
            _luong.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass

    ap = argparse.ArgumentParser(description="Dong goi AutoTone.")
    ap.add_argument("--thu", action="store_true", help="Chi in lenh, khong chay")
    ap.add_argument("--khong-retouch", action="store_true", dest="khong_retouch")
    ap.add_argument("--tool-retouch", type=Path, default=None,
                    help="Thu muc ToolCloneEvoto (mac dinh: do tu retouch.py)")
    ap.add_argument("--khong-nen", action="store_true", dest="khong_nen",
                    help="Khong tao file .zip sau khi build")
    #[[ Ban Linux KHONG PHAI san pham giao cho ai ca. Co co nay de kiem chinh
    #   script build: chay that mot lan tren Linux thi biet duong dan tai nguyen
    #   sau khi dong goi, danh sach loai tru, va kiem_goi.py co dung khong —
    #   nhung phan RIENG CUA WINDOWS thi van phai build tren Windows moi biet.
    #]]
    ap.add_argument("--ke-ca-linux", action="store_true", dest="ke_ca_linux",
                    help="Van build tren Linux (chi de tu kiem script build)")
    #[[ Xem chot_khoa() ben duoi. Co nay la loi cam ket CO Y dong goi ban
    #   khong khoa, khong phai duong tat cho tien tay. ]]
    ap.add_argument("--khong-khoa", action="store_true", dest="khong_khoa",
                    help="Dong goi ke ca khi khoa.BAT_KHOA = False")
    #[[ Ban nhe: goi khong mang thu vien nang lan mo hinh, may tu tai ve lan
    #   dau bam Retouch. Xem GOI_TACH va tai_nguyen.py. ]]
    ap.add_argument("--nhe", action="store_true",
                    help="Ban nhe: tai thu vien nang ve sau, khong nhet vao goi")
    #[[ ICON: .ico (Windows) / .icns (macOS) cho .exe/.app. Ten ky thuat van la
    #   "AutoTone"; chi doi icon. ]]
    ap.add_argument("--icon", type=Path, default=None,
                    help="File .ico (Win) / .icns (Mac) gan cho .exe/.app")
    #[[ macOS: mac dinh dong THU MUC (khong .app) vi .app bundle lam cv2
    #   recursion khong sua duoc. --mac-app ep tao .app (chi dung khi da sua
    #   duoc loi cv2 cho .app). Khong anh huong Windows. ]]
    ap.add_argument("--mac-app", action="store_true", dest="mac_app",
                    help="macOS: tao .app bundle thay vi thu muc (hien cv2 loi)")
    #[[ BAO MAT (4/10): bien dich loi sang .pyd/.so truoc khi build — xem
    #   bao_mat.py. Tuy chon, KHONG mac dinh: bat tay de ban build cu van chay
    #   nguyen ven cho toi khi xac nhan ban ma hoa build tron tren tung may. ]]
    ap.add_argument("--bao-mat", action="store_true", dest="bao_mat",
                    help="Ma hoa loi (Cython -> .pyd/.so) truoc khi dong goi")
    #[[ Voi --bao-mat: chay THAT 7 buoc retouch tren vai anh bang tool goc va ban
    #   da bao mat roi so anh ra (dong_goi_bao_mat.py --so-anh). Them vai phut —
    #   dung cho lan build giao khach. ]]
    ap.add_argument("--so-anh", type=Path, default=None, dest="so_anh",
                    help="(voi --bao-mat) thu muc anh: chay that retouch, so ban "
                         "bao mat voi tool goc")
    #[[ --torch-trong-goi: NHOI torch vao goi (ban day du) de Retouch hien du 8
    #   tinh nang NGAY, khong con "can tai torch"/"chua hoi duoc tool". Loai tru
    #   nhau voi --nhe (torch phai o lai). Xem TORCH_LOAI va lenh(). ]]
    ap.add_argument("--torch-trong-goi", action="store_true",
                    dest="torch_trong_goi",
                    help="Nhoi torch vao goi (ban day du); khong di cung --nhe")
    #[[ --kem-gpu (6/10): Windows — dat goi torch CUDA vao <goi>/goi_kem/ de
    #   ban cai mang san, khong tai ngam. Xem kem_goi_gpu(). ]]
    ap.add_argument("--kem-gpu", action="store_true", dest="kem_gpu",
                    help="(Windows) Kem san goi torch CUDA trong goi, khoi tai")
    a = ap.parse_args(argv)

    #[[ --torch-trong-goi va --nhe doi nghich: --nhe bo torch ra de tai sau, con
    #   --torch-trong-goi giu torch lai trong goi. Bat ca hai la mau thuan — tu
    #   tat --nhe de khong am tham bo torch rồi lai khai nhoi no. ]]
    if a.torch_trong_goi and a.nhe:
        print("  [!] --torch-trong-goi va --nhe doi nghich nhau. Bo --nhe.")
        a.nhe = False

    if not chot_khoa(a.khong_khoa) and not a.thu:
        return 1

    he = he_dieu_hanh()
    if he == "linux":
        print("  [!] Đang chạy trên Linux. Script này chỉ ra bản cho Windows "
              "hoặc macOS.\n      Chạy nó trên đúng máy đích.")
        if not (a.thu or a.ke_ca_linux):
            return 1

    goc_tool = a.tool_retouch
    if goc_tool is None and not a.khong_retouch:
        try:
            sys.path.insert(0, str(GOC))
            import retouch
            goc_tool = retouch.tim_tool()
        except Exception:                                    # noqa: BLE001
            goc_tool = None

    retouch_vao = (not a.khong_retouch) and co_retouch(goc_tool)
    if not a.khong_retouch and not retouch_vao:
        print(f"  [!] Không tìm thấy ToolCloneEvoto (đã dò: {goc_tool}).")
        print("      Gói sẽ KHÔNG có phần retouch. Chỉ rõ bằng --tool-retouch, "
              "hoặc chấp nhận bằng --khong-retouch.")
        if not a.thu:
            return 1

    #[[ BAO MAT: dung cay nguon da ma hoa roi tro PyInstaller vao do. Lam
    #   TRUOC khi dung lenh() de co danh sach hidden-import day du. ]]
    goc_nguon = diem_vao_bm = None
    ngam_them = None
    if a.bao_mat:
        try:
            sys.path.insert(0, str(GOC))
            import bao_mat
        except ImportError as ex:
            print(f"  [!] Khong nap duoc bao_mat.py: {ex}")
            return 1
        #[[ retouch tat -> KHONG mang retouch (khong ma hoa, khong de .py): them
        #   vao loai_tru cua cay. retouch bat -> no nam trong MA_HOA san. ]]
        loai_tru_cay = list(LOAI_TRU) + ([] if retouch_vao else ["retouch.py"])
        if MA_HOA_HET:
            ship = [p.stem for p in GOC.glob("*.py")
                    if p.stem not in {Path(f).stem for f in loai_tru_cay}
                    and p.stem not in ("chay",)]
            ma_hoa = [m for m in ship if retouch_vao or m != "retouch"]
        else:
            ma_hoa = [m for m in bao_mat.MA_HOA if retouch_vao or m != "retouch"]
        ra_cay = GOC / "build" / "nguon_bao_mat"
        print(f"  Mã hoá lõi ({'HẾT' if MA_HOA_HET else 'chỉ lõi'}: "
              f"{len(ma_hoa)} module) — cần vài phút...")
        try:
            goc_nguon = bao_mat.dung_cay_nguon(
                GOC, loai_tru_cay, ra_cay, ma_hoa=ma_hoa,
                diem_vao="autotone_gui", launcher="chay.py")
        except Exception as ex:                              # noqa: BLE001
            print(f"  [!] Mã hoá hỏng — DỪNG, không lùi về gói .py chưa mã hoá.\n"
                  f"      {type(ex).__name__}: {ex}")
            return 1
        diem_vao_bm = "chay.py"
        #[[ Hidden-import = module ứng dụng trong cây + MỌI import của module đã
        #   biên dịch (kể cả submodule thư viện như tkinter.filedialog) — vì
        #   PyInstaller không còn đọc được import của mã đã thành .pyd/.so.
        #   Thiếu phần sau thì gói chạy lên báo "cannot import name filedialog"
        #   (bắt được 4/10 ở lần build Linux đầu). ]]
        ngam_them = sorted(set(bao_mat.ten_module_cay(goc_nguon))
                           | set(bao_mat.quet_import_an(GOC, ma_hoa)))

        #[[ BAO MAT PHAN RETOUCH (4/10): bao_mat.py o tren chi dich LOI AutoTone.
        #   saytool (thuat toan retouch) van la .py, mo hinh tu hoc (mo_hinh/*.pt,
        #   *.npz) van doc duoc — ma hai thu do moi la phan dang giau nhat.
        #
        #   dong_goi_bao_mat.py NAM TRONG ToolCloneEvoto lo phan nay: dich saytool
        #   -> .pyd/.so (tru vo __init__/cli/duong_dan), ma hoa mo hinh (saytool
        #   giai trong RAM luc nap), roi TU KIEM (giai ma khop SHA-256, ban dich
        #   nap duoc moi module ban .py nap duoc). Hong -> ma != 0 -> DUNG, khong
        #   lui ve goi co saytool .py / mo hinh ro.
        #
        #   Xong thi tro goc_tool vao cay do: saytool_du() / mo_hinh_du() trong
        #   lenh() tu lay ban dich + mo hinh ma hoa (cung ten tep) — khong sua gi
        #   them. Bo qua o --thu (dich mat vai phut). ]]
        if retouch_vao and not a.thu:
            script_bm = Path(goc_tool) / "dong_goi_bao_mat.py"
            if not script_bm.is_file():
                print(f"  [!] Không thấy {script_bm}.")
                print("      Cập nhật ToolCloneEvoto (dong_goi_bao_mat.py + "
                      "saytool/bao_mat.py), hoặc đóng gói kèm --khong-retouch.")
                return 1
            ra_tool = GOC / "build" / "retouch_bao_mat"
            print("  Bảo mật retouch: saytool -> mã máy, mô hình -> mã hoá "
                  "(vài phút)...")
            r_bm = subprocess.run([sys.executable, str(script_bm),
                                   "--ra", str(ra_tool)]
                                  + (["--so-anh", str(a.so_anh)] if a.so_anh else []),
                                  cwd=str(goc_tool))
            if r_bm.returncode:
                print(f"  [!] Bảo mật retouch HỎNG (mã {r_bm.returncode}) — DỪNG, "
                      "không đóng gói bản chưa bảo mật.")
                return r_bm.returncode
            goc_tool = ra_tool
    elif retouch_vao and not a.thu:
        print("  [!] Đóng retouch KHÔNG --bao-mat: gói sẽ mang saytool .py và mô "
              "hình đọc được.\n      Bản giao khách: chạy lại kèm --bao-mat.")

    #[[ --nhe CO --bao-mat: giu mo hinh DA MA HOA trong goi (xem lenh()). Mo
    #   hinh ma hoa la IP, nhe (~300 MB), va de trong goi thi saytool (cwd=goi)
    #   nap duoc ngay — khong dinh lo hong "model o tai_nguyen, cwd o goi". ]]
    mac_thu_muc = (he == "mac") and not a.mac_app
    cmd = lenh(he, retouch_vao, goc_tool, nhe=a.nhe,
               goc_nguon=goc_nguon, diem_vao=diem_vao_bm, ngam_them=ngam_them,
               giu_mo_hinh=bool(a.bao_mat and a.nhe), icon=a.icon,
               mac_thu_muc=mac_thu_muc, torch_trong_goi=a.torch_trong_goi)
    print(f"  Hệ: {he}   retouch: {'có' if retouch_vao else 'không'}"
          + (f"   ({goc_tool})" if retouch_vao else "")
          + ("   [BAN NHE: thu vien nang tai sau]" if a.nhe else "")
          + ("   [TORCH TRONG GÓI: đủ 8 tính năng ngay]"
             if a.torch_trong_goi else "")
          + ("   [ĐÃ MÃ HOÁ LÕI]" if a.bao_mat else ""))
    print("\n  " + " ".join(f'"{c}"' if " " in c else c for c in cmd) + "\n")
    if a.thu:
        return 0

    try:
        import PyInstaller           # noqa: F401
    except ImportError:
        print("  [!] Chưa có PyInstaller.  pip install pyinstaller")
        return 1

    #[[ CHOT: PyInstaller >= 6.10 cho CO CHE CAP NHAT (cap_nhat.py).
    #
    #   Tu 6.10 importer cua PyInstaller la path-entry-finder chay trong
    #   PathFinder, nen ban cap nhat chen len dau sys.path moi de duoc code trong
    #   goi. Ban < 6.10 thi importer la meta-path finder "nuot" sys.path -> OTA
    #   AM THAM khong an (goi van chay, chi la khong bao gio nhan ban va). Da
    #   kiem tra tren chinh AutoTone.exe (PyInstaller 6.21). Chan o day de khong
    #   lo dong goi mot ban ma tinh nang cap nhat chet lang le. ]]
    try:
        _pv = tuple(int(x) for x in PyInstaller.__version__.split(".")[:2])
    except Exception:                                    # noqa: BLE001
        _pv = (0, 0)
    if _pv < (6, 10):
        print(f"  [!] PyInstaller {PyInstaller.__version__} < 6.10 — cơ chế cập "
              "nhật (OTA) sẽ KHÔNG hoạt động trên gói này.")
        print("      Nâng cấp:  pip install -U \"pyinstaller>=6.10\"")
        return 1

    r = subprocess.run(cmd, cwd=str(GOC))
    if r.returncode:
        print(f"  [!] PyInstaller lỗi, mã {r.returncode}")
        return r.returncode

    #[[ macOS .app chi khi --mac-app; mac dinh (mac_thu_muc) ra THU MUC dist/TEN
    #   nhu Windows/Linux. ]]
    ra = GOC / "dist" / (f"{TEN}.app" if (he == "mac" and not mac_thu_muc) else TEN)
    xoa = don_goi(ra)
    for p in xoa:
        print(f"  đã loại khỏi gói: {p}")
    for p in tao_ban_nhan(ra):
        print(f"  đã tạo sẵn: {p.name}")
    if a.kem_gpu and he == "win":
        if not kem_goi_gpu(ra):
            print("  [!] Gói KHÔNG kèm torch CUDA — máy có card sẽ tự tải khi mở app.")
            return 1

    print(f"\n  Gói: {ra}")
    if not a.khong_nen:
        nen = GOC / "dist" / f"{TEN}-{he}"
        print("  Đang nén...")
        goi_nen = nen_goi(ra, nen, he)
        if goi_nen is None:
            print("  [!] Nén thất bại — gói vẫn dùng được, chỉ là không có .zip")
        else:
            print(f"  Nén: {goi_nen}  "
                  f"({goi_nen.stat().st_size / 1e9:.2f} GB)")
    print("\n  Bước tiếp: chạy kiem_goi.py trỏ vào gói vừa tạo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
