#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bao_mat.py — biên dịch các module lõi sang mã máy (.pyd/.so) trước khi đóng gói.

VÌ SAO
    Gói PyInstaller để nguyên .py -> .pyc trong kho PYZ. Ai cũng chạy
    pyinstxtractor rồi dịch ngược .pyc ra Python đọc được trong vài phút — tức
    phát hành gói gần như phát hành luôn mã nguồn. Cython dịch .py -> C -> .so
    (Mac/Linux) / .pyd (Windows): mở ra chỉ còn mã máy, inspect.getsource() vô
    hiệu, các chuỗi hằng không còn nằm nguyên để grep.

AI (HAY NGƯỜI) CHỌC VÀO -> KHÔNG CÓ NGUỒN ĐỂ LẤY
    Sau khi biên dịch, autotone/retouch/khoa/... trong gói là .pyd/.so. Mở ra
    không còn một dòng Python nào. Đó là "không lấy được code" theo NGHĨA THẬT,
    không phải một câu comment doạ dẫm (một câu chữ thì ai đọc nguồn cũng bỏ qua).

NÓI THẲNG GIỚI HẠN — ĐỪNG TƯỞNG BẤT KHẢ XÂM PHẠM
    1. Mã vẫn chạy trên máy khách, nên người quyết tâm + đủ thời gian vẫn mở
       được (dump bộ nhớ, trace). Không có cách nào chặn tuyệt đối một app để
       trên máy người khác.
    2. HẰNG SỐ CẤP MODULE vẫn đọc được LÚC CHẠY: ai `import khoa; khoa.BI_MAT`
       là lấy được khoá bí mật — Cython KHÔNG giấu cái đó (đã kiểm tận tay).
       Khoá bản quyền vì vậy vẫn là khoá MỀM, đúng như ban_quyen.py đã ghi.
       Muốn cứng thật phải kiểm qua máy chủ (dự án cố ý không làm).
    Mục tiêu đạt được ở đây: chặn hẳn kiểu "giải nén + đọc nguồn", giấu thuật
    toán và các ngưỡng đã chỉnh, nâng chi phí cắp vượt cái lợi của kẻ cắp vặt.

CHẠY Ở ĐÂU — GIỐNG PyInstaller, KHÔNG BUILD CHÉO ĐƯỢC
    .pyd phải build TRÊN Windows, .so phải build TRÊN Mac. Cần trình biên dịch C:
      - Windows: Microsoft C++ Build Tools (hoặc Visual Studio Desktop C++)
      - macOS:   xcode-select --install
      - Linux:   gcc (thường có sẵn)
    Thiếu trình biên dịch thì bước này báo lỗi rõ và dong_goi.py dừng — KHÔNG
    âm thầm lùi về gói .py chưa mã hoá.
"""
from __future__ import annotations

import os
import shutil
import sys
import sysconfig
import tempfile
from pathlib import Path

#[[ MODULE LÕI đáng giấu nhất — thuật toán + hằng số đã chỉnh hàng tuần + hệ
#   khoá. Phần còn lại (plumbing: duong_dan, trang_thai, luoi_anh...) để .py
#   cũng không lộ bí quyết; muốn giấu HẾT thì bật dong_goi.MA_HOA_HET. Thêm /
#   bớt tên ở đây là biên dịch thêm / bớt. ]]
MA_HOA = ["autotone", "retouch", "khoa", "ban_quyen",
          "thu_gu", "learn_corrections", "giao_dien", "autotone_gui",
          #[[ 7/10 giai doan 2: autotone_gui tach ba phan — cung la ruot app. ]]
          "man_retouch", "hop_thoai", "cua_saytool",
          "retouch_chung", "retouch_muc", "retouch_may"]

#[[ Banner CẢNH BÁO + BẢN QUYỀN. Với module .py còn ship (plumbing) thì đây là
#   răn đe; với module đã biên dịch thì nguồn không còn nên banner chỉ còn trong
#   launcher và file BAN_QUYEN.txt. Lớp bảo vệ THẬT là biên dịch, không phải
#   dòng chữ này. ]]
BANNER = (
    "# ==========================================================================\n"
    "#  (c) SAY MEDIA - AutoTone. Ma nguon doc quyen. KHONG duoc sao chep, phat\n"
    "#  tan hay dich nguoc. Phan loi cua san pham DA BIEN DICH sang ma may\n"
    "#  (.pyd/.so) - mo ra khong con ma Python de lay. Moi no luc dich nguoc la\n"
    "#  vi pham ban quyen va se bi xu ly.\n"
    "# ==========================================================================\n"
)

LAUNCHER = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""chay.py - diem vao cua ban da ma hoa.

Khong co logic nghiep vu nao o day. Toan bo loi (can sang, retouch, ban quyen,
giao dien) nam trong cac module DA BIEN DICH (.pyd tren Windows / .so tren Mac)
di kem goi. Mo cac file do ra chi thay ma may, khong con Python de doc. Co y.

(c) SAY MEDIA. Ma nguon doc quyen - khong sao chep, khong dich nguoc.
"""
#[[ freeze_support() PHAI LA LENH DAU TIEN — truoc moi import/logic khac.
#
#   Day la DIEM VAO THAT (__main__) cua ban ma hoa. Tren Windows/macOS,
#   multiprocessing SPAWN chay lai chinh file nay trong MOI tien trinh con, roi
#   RE-IMPORT __main__. freeze_support() chan dung cho do: trong tien trinh con
#   no lam phan viec cua worker roi THOAT, khong di tiep xuong duoi. Nhung no chi
#   chan duoc neu chay TRUOC moi thu khac o __main__. Neu de cap_nhat.kich_hoat()
#   hay `import autotone_gui` chay truoc, moi tien trinh con se lam viec thua
#   roi MO THEM MOT CUA SO APP (bug "bam Retouch mo cua so thu 2" — khau Phan
#   tich / Retouch dung ProcessPoolExecutor spawn). autotone_gui.main() cung co
#   freeze_support() dau ham, nhung voi diem vao chay.py thi __main__ la day,
#   nen phai goi O DAY, SOM NHAT. ]]
import sys
import multiprocessing
multiprocessing.freeze_support()

#[[ CHAN TUYET DOI tien trinh con multiprocessing — KHONG de roi xuong mo GUI.
#
#   freeze_support() o tren DANG LE tu sys.exit() khi la tien trinh con spawn
#   (worker '--multiprocessing-fork', hay helper tracker/forkserver dang
#   '-c ...'). Nhung thuc te (ban mã hoá, diem vao chay.py) no KHONG chan het:
#   bam Retouch/Phan tich van mo cua so app thu 2. Nen o day CHAN TUONG MINH:
#   neu argv co dau hieu tien trinh con multiprocessing, thi sau freeze_support
#   (da lo phan viec worker) ta ep thoat, KHONG chay kich_hoat/import/main.
#
#   is_forking: worker spawn. '-c' + co interpreter flags: helper. Them
#   '--multiprocessing-fork' / 'spawn_main' / 'resource_tracker' / 'forkserver'
#   trong argv de chac. ]]
def _la_tien_trinh_con_mp():
    av = sys.argv
    try:
        if multiprocessing.spawn.is_forking(av):
            return True
    except Exception:
        pass
    noi = " ".join(av[1:])
    for dau in ("--multiprocessing-fork", "spawn_main", "resource_tracker",
                "from multiprocessing.forkserver", "from multiprocessing.resource_tracker"):
        if dau in noi:
            return True
    #[[ '-c' dung ngay sau cac co interpreter (vd -S -E) la helper mp. ]]
    if "-c" in av[1:]:
        return True
    return False

if _la_tien_trinh_con_mp():
    #[[ freeze_support() o tren da xu ly phan viec can thiet. Neu toi day van
    #   chua thoat (vi freeze_support khong exit), ep thoat de KHONG mo GUI. ]]
    sys.exit(0)

#[[ CAP NHAT: chen thu muc ban va len dau sys.path TRUOC `import {diem_vao}` —
#   loi app trong goi la .pyd/.so, muon ban CODE MOI de len thi thu muc cap nhat
#   phai dung TRUOC. Chi tien trinh CHINH toi day. kich_hoat() boc try/except. ]]
try:
    import cap_nhat as _cn
    _cn.kich_hoat()
except Exception:
    pass
import {diem_vao} as _app
_app.main()
'''

NOI_DUNG_BAN_QUYEN = (
    "AutoTone (c) SAY MEDIA - Story About You\n"
    "=========================================\n\n"
    "Phan loi cua phan mem nay da duoc bien dich sang ma may (.pyd / .so).\n"
    "Trong goi KHONG co ma nguon Python de doc hay lay di.\n\n"
    "Moi no luc dich nguoc, sao chep, go khoa ban quyen hay phat tan lai deu\n"
    "vi pham ban quyen cua SAY MEDIA va se bi xu ly theo phap luat.\n"
)


def duoi_mo_rong() -> str:
    """Đuôi file extension đúng cho máy đang chạy: .pyd (Windows) / .so (Mac,
    Linux). Lấy từ sysconfig để kèm luôn cả tag ABI (vd .cp312-win_amd64.pyd)."""
    return sysconfig.get_config_var("EXT_SUFFIX") or (
        ".pyd" if sys.platform == "win32" else ".so")


def co_trinh_bien_dich() -> tuple[bool, str]:
    """(Có đủ đồ nghề không, lời nhắn nếu thiếu). Kiểm Cython + trình biên dịch
    C trước khi bắt đầu, để báo lỗi NGAY thay vì chết giữa chừng."""
    try:
        import Cython  # noqa: F401
    except ImportError:
        return False, ("Thieu Cython. Cai: pip install cython")
    # setuptools se goi trinh bien dich C cua he; chi can bao truoc neu Windows
    # chua co cl.exe / Mac chua co clang.
    if sys.platform == "win32" and not (shutil.which("cl") or os.environ.get("VSINSTALLDIR")):
        return True, ("[!] Chua thay cl.exe. Neu build loi, cai 'Microsoft C++ "
                      "Build Tools' roi mo 'x64 Native Tools Command Prompt'.")
    if sys.platform == "darwin" and not shutil.which("clang"):
        return True, "[!] Chua thay clang. Chay: xcode-select --install"
    return True, ""


def bien_dich_mot(src: Path, ra_dir: Path, lang: bool = True) -> Path:
    """Cython-hoá MỘT file .py -> .pyd/.so, bỏ vào ra_dir. Trả đường dẫn artifact.

    Biên dịch trong thư mục tạm để không rải .c / build/ ra cây nguồn. Không
    nuốt lỗi: Cython hay trình C hỏng thì ném ra để dong_goi dừng hẳn."""
    #[[ BUG MSVC 14.51 (Build Tools 2026, VS18) + Cython + Python 3.12 — KHONG
    #   co MOT flag chung cho moi module, va loi KHONG ON DINH:
    #     - autotone          : CAN giu /GL. Bo /GL -> C2059 (_Py_CAST hong).
    #     - learn_corrections : CAN /GL-. Giu /GL -> C1001 (LTCG internal error).
    #   Hai doi hoi trai nguoc nhau. Nen THU NHIEU CHIEN LUOC flag, lay cai chay.
    #   Thu tu: (1) mac dinh /O2 /GL  (2) /O1 /GL-  (3) /Od /GL. Linux/Mac
    #   (gcc/clang) chi co 1 chien luoc rong (dung mac dinh trinh dich).
    #
    #   Day la chua NGON cho bug compiler qua moi. Cach sach hon la cai MSVC
    #   v14.3x (VS 2022) dung ban Python 3.12 — nhung thu-lai nay cho ra .pyd
    #   dung tren CHINH may nay ma khong phai cai them 7 GB toolset cu. ]]
    if sys.platform == "win32":
        chien_luoc = [
            (["/O2", "/GL"], ["/LTCG"]),      # mac dinh — autotone can /GL
            (["/O1", "/GL-"], ["/LTCG:OFF"]),  # learn_corrections can /GL-
            (["/Od", "/GL"], ["/LTCG"]),      # du phong
        ]
    else:
        chien_luoc = [([], [])]

    from Cython.Build import cythonize
    from setuptools import setup, Extension

    ten = src.stem
    loi_cuoi = None
    for i, (cc_args, ld_args) in enumerate(chien_luoc):
        with tempfile.TemporaryDirectory(prefix="baomat_") as tam_s:
            tam = Path(tam_s)
            shutil.copy2(src, tam / f"{ten}.py")
            cwd, argv = os.getcwd(), sys.argv
            try:
                os.chdir(tam)
                sys.argv = ["setup.py", "build_ext", "--inplace"]
                ext = Extension(ten, [f"{ten}.py"],
                                extra_compile_args=cc_args,
                                extra_link_args=ld_args)
                setup(
                    ext_modules=cythonize(
                        [ext],
                        compiler_directives={"language_level": 3},
                        quiet=True,
                    ),
                    script_args=["build_ext", "--inplace"],
                )
                arts = sorted(tam.glob(f"{ten}*.so")) + sorted(tam.glob(f"{ten}*.pyd"))
                if not arts:
                    raise RuntimeError(f"Cython khong sinh ra .so/.pyd cho {ten}")
                dich = ra_dir / arts[0].name
                shutil.copy2(arts[0], dich)
                if lang:
                    nhan = f" [{' '.join(cc_args)}]" if i else ""
                    print(f"      ma hoa: {ten}.py -> {dich.name}{nhan}")
                return dich
            except BaseException as ex:         # noqa: BLE001
                loi_cuoi = ex
                if lang and len(chien_luoc) > 1:
                    print(f"      (thu flag {cc_args} cho {ten} khong xong, "
                          f"thu cach khac...)")
            finally:
                os.chdir(cwd)
                sys.argv = argv
    #[[ Het chien luoc ma van hong -> nem loi cuoi de dong_goi dung han. ]]
    raise RuntimeError(f"Khong bien dich duoc {ten} voi moi flag da thu: "
                       f"{type(loi_cuoi).__name__}: {loi_cuoi}")


def dung_cay_nguon(goc: Path, loai_tru, ra: Path,
                   ma_hoa=None, diem_vao: str = "autotone_gui",
                   launcher: str = "chay.py", lang: bool = True) -> Path:
    """Dựng CÂY NGUỒN để PyInstaller build, với lõi đã thành .pyd/.so.

    - Mọi .py sẽ ship (trừ loai_tru và trừ module đem mã hoá) được chép sang,
      có gắn banner bản quyền ở đầu.
    - Mỗi module trong ma_hoa được biên dịch THẲNG vào ra/ (không kèm .py của
      nó) — nên trong cây này KHÔNG có mã nguồn của lõi.
    - Thêm launcher mỏng + file BAN_QUYEN.txt.

    PyInstaller trỏ điểm vào vào ra/launcher và --paths ra, nên mọi import giải
    về ra/: lõi -> .pyd/.so, phần còn lại -> .py. Cây GỐC không bị đụng tới.
    """
    goc = Path(goc)
    ma_hoa = list(MA_HOA if ma_hoa is None else ma_hoa)
    bo = {Path(f).stem for f in loai_tru}
    gjewel = set(ma_hoa)

    if ra.exists():
        shutil.rmtree(ra)
    ra.mkdir(parents=True)

    # 1) chép .py plumbing (có banner), bỏ qua loai_tru + module sẽ mã hoá
    n_py = 0
    for p in sorted(goc.glob("*.py")):
        if p.stem in bo or p.stem in gjewel or p.name == launcher:
            continue
        txt = p.read_text(encoding="utf-8")
        (ra / p.name).write_text(BANNER + txt, encoding="utf-8")
        n_py += 1

    # 2) biên dịch lõi thẳng vào ra/
    ok, nhac = co_trinh_bien_dich()
    if not ok:
        raise RuntimeError(nhac)
    if nhac and lang:
        print("  " + nhac)
    da = []
    for m in ma_hoa:
        src = goc / f"{m}.py"
        if not src.is_file():
            if lang:
                print(f"      (bo qua, khong co: {m}.py)")
            continue
        da.append(bien_dich_mot(src, ra, lang=lang))
        # chắc chắn KHÔNG còn .py của lõi lọt vào cây
        (ra / f"{m}.py").unlink(missing_ok=True)

    # 3) launcher + giấy bản quyền
    (ra / launcher).write_text(LAUNCHER.format(diem_vao=diem_vao), encoding="utf-8")
    (ra / "BAN_QUYEN.txt").write_text(NOI_DUNG_BAN_QUYEN, encoding="utf-8")

    if lang:
        print(f"  cay nguon bao mat: {ra}  ({n_py} .py + {len(da)} module ma hoa)")
    return ra


def quet_import_an(goc: Path, ma_hoa) -> list[str]:
    """Quét mã NGUỒN của các module đem biên dịch, trả về MỌI tên module chúng
    import — để nhét vào --hidden-import.

    VÌ SAO BẮT BUỘC: một khi module thành .pyd/.so, PyInstaller không đọc được
    import của nó nữa. Import module ứng dụng thì đã có trong cây (ten_module_cay),
    nhưng `from tkinter import filedialog`, `from PIL import Image`... là
    submodule thư viện — thiếu khai thì gói chạy lên báo "cannot import name
    filedialog" (bắt được 4/10 ở lần build Linux đầu). Khai dư một tên không tồn
    tại chỉ làm PyInstaller cảnh báo rồi bỏ qua, nên quét rộng là an toàn.
    """
    import ast
    ten: set[str] = set()
    for m in ma_hoa:
        src = goc / f"{m}.py"
        if not src.is_file():
            continue
        try:
            cay = ast.parse(src.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for nut in ast.walk(cay):
            if isinstance(nut, ast.Import):
                for a in nut.names:
                    ten.add(a.name)                         # "a", "a.b.c"
            elif isinstance(nut, ast.ImportFrom):
                if nut.level or not nut.module:             # bỏ import tương đối
                    continue
                ten.add(nut.module)                         # "tkinter", "PIL"
                for a in nut.names:                         # + submodule có thể có
                    if a.name != "*":
                        ten.add(f"{nut.module}.{a.name}")    # "tkinter.filedialog"
    #[[ Bỏ __future__ và chính các module app (đã có trong cây) cho gọn — nhưng
    #   giữ lại cũng vô hại. Lọc __future__ vì PyInstaller cảnh báo thừa. ]]
    ten.discard("__future__")
    return sorted(ten)


def ten_module_cay(ra: Path) -> list[str]:
    """Tên mọi module trong cây staging (cả .py lẫn .pyd/.so) — để dong_goi
    nhét HẾT vào --hidden-import: điểm vào đã biên dịch nên PyInstaller không tự
    dò ra được các import của nó nữa."""
    ten = set()
    for p in ra.iterdir():
        if p.suffix == ".py" and p.stem != "chay":
            ten.add(p.stem)
        elif p.suffix in (".so", ".pyd"):
            ten.add(p.name.split(".")[0])      # bỏ .cp312-... .so
    return sorted(ten)
