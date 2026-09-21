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
    "kiem_khoa.py", "kiem_gu.py", "kiem_luat.py", "kiem_san.py",
    "kiem_do_mat.py", "kiem_goi.py", "kiem_ban_xuat.py", "do_trong_ngoai.py", "do_wb.py", "hoc_mau_da.py", "kiem_mau_da.py",
    "test_tach_canh.py", "test_cull_split.py", "test_san_phang.py",
    "test_trang_thai.py", "test_retouch_luong.py", "kiem_da_tien_trinh.py",
    "nap_mo_hinh.py", "kiem_exif_jpeg.py", "kiem_mau_lr.py",
    "kiem_duyet_py.py", "kiem_gui_duyet.py", "kiem_moc_va_xuat.py",
    "kiem_che_do_sang.py", "kiem_bo_cuc.py", "kiem_ve_that.py",
    "kiem_man_hinh.py", "kiem_xuat_lr.py", "kiem_tim_tool.py", "kiem_retouch_095.py", "kiem_retouch_gui.py", "kiem_dong_goi.py", "kiem_mac.py", "kiem_cu_phap.py", "chan_doan.py", "kiem_xuatanh.lua",
    "kiem_batduongdan.lua", "kiem_duyet.lua", "kiem_dung_preview.lua",
    "do_ranh_canh.py", "do_chot_mat_ao.py", "so_sanh_do_mat.py",
    "xem_chot.py", "xem_do_sang.py", "eye_probe.py", "eye_sheet.py",
    "make_testdata.py", "tools_smoke_test.py", "dong_goi.py",
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
        "ban_quyen"]

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
        shutil.copytree(nguon, dich, dirs_exist_ok=True)

    thieu = []
    dem = Path(os.environ.get("SKIN_SPIKE_CACHE",
                              Path.home() / ".cache" / "skin_spike"))
    fp = dem / "resnet34_faceparse.onnx"
    if fp.is_file():
        shutil.copy2(fp, dich / fp.name)
    else:
        thieu.append("resnet34_faceparse.onnx (phân vùng da)")

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


def co_retouch(goc_tool: Path | None) -> bool:
    return bool(goc_tool and (Path(goc_tool) / "saytool" / "cli.py").is_file())


def lenh(he: str, retouch: bool = True, goc_tool: Path | None = None,
         sach: bool = True, nhe: bool = False) -> list:
    """Dựng dòng lệnh PyInstaller. Tách riêng để kiểm được mà không phải build.

    he:  "win" | "mac"
    nhe: bỏ thư viện nặng ra khỏi gói — xem GOI_TACH.
    """
    ngan = ";" if he == "win" else ":"        # dấu ngăn của --add-data
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir",
           "--windowed", "--name", TEN]
    if sach:
        cmd.append("--clean")

    for nguon, dich in TAI_NGUYEN:
        #[[ Rieng plugin thi lay BAN SACH (da bo jobs/) — xem BO_KHOI_PLUGIN.
        #]]
        p = plugin_sach() if nguon == "AutoTone.lrplugin" else (GOC / nguon)
        cmd += ["--add-data", f"{p}{ngan}{dich}"]

    for m in NGAM:
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
            cmd += ["--collect-all", g]
        if goc_tool:
            cmd += ["--add-data", f"{saytool_du(goc_tool)}{ngan}saytool"]
            #[[ mo_hinh/ nang 554 MB — ban nhe KHONG mang theo, tai_nguyen.py
            #   tai goi "mo-hinh" ve %LOCALAPPDATA% lan dau bam Retouch.
            #   Van mang saytool/ (vai MB) de giao dien biet co nhung buoc nao.
            #]]
            if not nhe:
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
        #[[ Universal2 chi lam duoc khi MOI thu vien deu co ban universal.
        #   torch thi khong — nen de PyInstaller lay dung kien truc may dang
        #   chay. May Apple Silicon ra ban arm64, may Intel ra ban x86_64.
        #]]
        cmd += ["--osx-bundle-identifier", "vn.saymedia.autotone"]

    cmd.append(str(GOC / DIEM_VAO))
    return cmd


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
    a = ap.parse_args(argv)

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

    cmd = lenh(he, retouch_vao, goc_tool, nhe=a.nhe)
    print(f"  Hệ: {he}   retouch: {'có' if retouch_vao else 'không'}"
          + (f"   ({goc_tool})" if retouch_vao else "")
          + ("   [BAN NHE: thu vien nang tai sau]" if a.nhe else ""))
    print("\n  " + " ".join(f'"{c}"' if " " in c else c for c in cmd) + "\n")
    if a.thu:
        return 0

    try:
        import PyInstaller           # noqa: F401
    except ImportError:
        print("  [!] Chưa có PyInstaller.  pip install pyinstaller")
        return 1

    r = subprocess.run(cmd, cwd=str(GOC))
    if r.returncode:
        print(f"  [!] PyInstaller lỗi, mã {r.returncode}")
        return r.returncode

    ra = GOC / "dist" / (f"{TEN}.app" if he == "mac" else TEN)
    xoa = don_goi(ra)
    for p in xoa:
        print(f"  đã loại khỏi gói: {p}")

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
