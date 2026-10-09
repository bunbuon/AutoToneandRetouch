#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""duong_dan.py — Chỗ nào chỉ ĐỌC, chỗ nào GHI ĐƯỢC.

VÌ SAO PHẢI TÁCH RA
    Chạy từ mã nguồn thì mọi thứ nằm chung một thư mục và ghi đâu cũng được.
    Đóng gói rồi thì không:

      * Windows: gói cài nằm trong C:\\Program Files — user thường KHÔNG ghi
        được vào đó. Ghi hỏng thì Windows còn âm thầm chuyển hướng sang
        VirtualStore, nên chương trình tưởng đã ghi xong mà file thật nằm chỗ
        khác — loại lỗi mất dữ liệu khó truy nhất.
      * macOS: nội dung trong .app được ký; ghi vào đó là phá chữ ký, lần mở
        sau Gatekeeper chặn luôn ứng dụng.
      * PyInstaller onefile: giải nén ra thư mục tạm rồi XOÁ khi thoát — ghi
        vào đó là mất sạch sau mỗi lần đóng app.

    Nên: tài nguyên (mô hình, bản gốc plugin) chỉ đọc, nằm trong gói.
    Dữ liệu (gu đã học, job gửi Lightroom, trạng thái buổi, cấu hình) ghi vào
    thư mục dữ liệu của người dùng.

PLUGIN LIGHTROOM LÀ TRƯỜNG HỢP ĐẶC BIỆT
    Nó vừa là tài nguyên (đi kèm gói) vừa phải GHI được (thư mục jobs nằm bên
    trong nó), và Lightroom phải nạp được nó. Nên lần chạy đầu, bản gốc trong
    gói được chép sang thư mục dữ liệu, và từ đó trở đi dùng bản chép.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

TEN_UD = "AutoTone"


def dong_goi() -> bool:
    """Đang chạy từ gói đã đóng (PyInstaller) hay từ mã nguồn?"""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def goc_tai_nguyen() -> Path:
    """Thư mục CHỈ ĐỌC: mô hình, bản gốc plugin, tài liệu."""
    if dong_goi():
        return Path(sys._MEIPASS)                    # noqa: SLF001
    return Path(__file__).resolve().parent


def goc_du_lieu() -> Path:
    """Thư mục GHI ĐƯỢC của người dùng.

    Đặt được bằng biến môi trường AUTOTONE_DATA — cần cho bài kiểm (chạy trên
    thư mục tạm) và cho máy muốn để dữ liệu sang ổ khác.
    """
    tu_dat = os.environ.get("AUTOTONE_DATA")
    if tu_dat:
        return Path(tu_dat)
    if not dong_goi():
        #[[ Chay tu ma nguon thi giu nguyen thoi quen cu: moi thu nam canh file
        #   .py. Doi cho luc nay se lam lac het gu.json va trang_thai/ dang co.
        #]]
        return Path(__file__).resolve().parent
    if sys.platform.startswith("win"):
        goc = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        goc = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        goc = os.environ.get("XDG_DATA_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "share")
    return Path(goc) / TEN_UD


def tao(p: Path) -> Path:
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return p


def du_lieu(*ten) -> Path:
    """Đường dẫn trong thư mục dữ liệu, tự tạo thư mục cha."""
    p = goc_du_lieu().joinpath(*ten)
    tao(p.parent)
    return p


def tai_nguyen(*ten) -> Path:
    return goc_tai_nguyen().joinpath(*ten)


#[[ File plugin vua duoc cap nhat tu goi o lan mo app nay (ten file). Giao dien
#   doc de nhac Reload plugin trong Lightroom. ]]
PLUGIN_CAP_NHAT: list = []
_DA_SOAT_PLUGIN: list = []


def _cap_nhat_plugin(nguon: Path, dich: Path) -> list:
    """Chép đè file MÃ của plugin (không đụng jobs/) khi khác bản trong gói.

    #[[ 6/10 — user: "AutoTone chi xu ly WB duoc 1 phan, Shadows / Contrast
    #   khong thay can thiep". Lightroom dang chay plugin 4/9 (7 file) o thu muc
    #   du lieu: plugin() truoc day CHI chep khi chua co, nen moi ban cai sau do
    #   (plugin 12 file, xuat them WhiteBalance / Contrast / Whites / Blacks) KHONG
    #   BAO GIO toi duoc Lightroom. Ban xuat thieu cac cot do -> preset_chua_ap()
    #   khong nhan ra preset bo trong WB / Tone -> 1743/1813 anh As Shot bi bo qua
    #   WB, khong ghi Contrast / Whites / Blacks. Canh bao "Reload plugin" cung vo
    #   ich: Reload nap lai dung ban cu nay.
    #
    #   Chep tung file khac noi dung, KHONG copytree de len: jobs/ la trang thai
    #   luc chay (job dang cho, ban xuat, nhat ky) — xem plugin(). ]]
    """
    doi = []
    for f in sorted(nguon.rglob("*")):
        rel = f.relative_to(nguon)
        if not f.is_file() or (rel.parts and rel.parts[0] == "jobs"):
            continue
        d = dich / rel
        try:
            if d.is_file() and d.read_bytes() == f.read_bytes():
                continue
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, d)
            doi.append(str(rel))
        except OSError:
            pass
    return doi


#[[ PLUGIN TU CAI VAO THU MUC Modules CUA LIGHTROOM (9/10 — user: "co cach nao
#   de Lightroom tu dong nhan Plugin cua Tool khi lan dau cai Tool xong").
#
#   Lightroom Classic tu nap MOI plugin nam trong thu muc Modules moi lan khoi
#   dong — khong can Plug-in Manager → Add (may user da co thu muc nay, dang
#   chua saytool.lrdevplugin). Cung voi LrForceInitPlugin (Info.lua) la mo
#   Lightroom → vong nhan job tu chay.
#
#   App (KHONG phai bo cai: bo cai co the chay quyen admin -> ghi nham sang tai
#   khoan khac, va RedirectionGuard 6/10) chep plugin vao Modules o lan mo dau,
#   cac lan sau dong bo file ma nhu ban o thu muc du lieu, va ghi `jobs_dir.txt`
#   tro ve thu muc job THAT (cua ban o thu muc du lieu) — xem ThuMucJob.lua. Nho
#   vay ban trong Modules va ban nguoi dung tung Add dung CHUNG mot jobs/, phia
#   app khong doi gi.
#
#   KHONG cai khi: chay tu ma nguon; tu kiem (kiem_goi dat AUTOTONE_TU_KIEM +
#   AUTOTONE_DATA tam — cai luc do la tro plugin THAT cua nguoi dung vao thu muc
#   tam se bi xoa); thu muc du lieu nam trong thu muc tam; tien trinh con.
#   AUTOTONE_LR_MODULES = dat thu muc Modules (bai kiem). ]]
TEN_TRO_JOBS = "jobs_dir.txt"
#: Kết quả lần cài vào Modules của lần mở app này — giao diện đọc để nhắc.
#: {"duong": thư mục plugin trong Modules, "moi": lần đầu cài, "doi": [file đã
#:  cập nhật], "loi": lý do không cài được ("" = ổn), "bo_qua": lý do không cài}
PLUGIN_MODULES: dict = {}
_DA_CAI_MODULES: list = []


def thu_muc_modules_lr() -> Path | None:
    """Thư mục Lightroom tự nạp plugin (Modules) của người dùng này."""
    tu_dat = os.environ.get("AUTOTONE_LR_MODULES")
    if tu_dat:
        return Path(tu_dat)
    if sys.platform.startswith("win"):
        g = os.environ.get("APPDATA")
        return Path(g) / "Adobe" / "Lightroom" / "Modules" if g else None
    if sys.platform == "darwin":
        return (Path.home() / "Library" / "Application Support" / "Adobe"
                / "Lightroom" / "Modules")
    return None


def ly_do_khong_cai_modules() -> str:
    """"" = được cài vào Modules lúc này; khác "" = vì sao không."""
    if os.environ.get("AUTOTONE_LR_MODULES"):
        return ""
    if not dong_goi():
        return "chạy từ mã nguồn"
    if os.environ.get("AUTOTONE_TU_KIEM") or "--tu-kiem" in sys.argv[1:]:
        return "đang tự kiểm"
    try:
        import multiprocessing as _mp
        if _mp.current_process().name != "MainProcess":
            return "tiến trình con"
    except Exception:                                        # noqa: BLE001
        pass
    try:
        import tempfile
        tam = os.path.normcase(os.path.abspath(tempfile.gettempdir()))
        du = os.path.normcase(os.path.abspath(str(goc_du_lieu())))
        if du == tam or du.startswith(tam + os.sep):
            return "thư mục dữ liệu là thư mục tạm"
    except Exception:                                        # noqa: BLE001
        pass
    return ""


def cai_vao_modules(nguon: Path, jobs: Path, modules: Path | None = None) -> dict:
    """Chép / đồng bộ plugin vào thư mục Modules + ghi file trỏ jobs_dir.txt.
    Không bao giờ ném lỗi — lỗi nằm ở kq["loi"]."""
    kq = {"duong": "", "moi": False, "doi": [], "loi": "", "bo_qua": ""}
    modules = Path(modules) if modules else thu_muc_modules_lr()
    if modules is None:
        kq["loi"] = "không rõ thư mục Modules của Lightroom trên hệ điều hành này"
        return kq
    dich = modules / "AutoTone.lrplugin"
    kq["duong"] = str(dich)
    try:
        kq["moi"] = not (dich / "Info.lua").is_file()
        dich.mkdir(parents=True, exist_ok=True)
        kq["doi"] = _cap_nhat_plugin(Path(nguon), dich)
        tro = dich / TEN_TRO_JOBS
        noi = str(Path(jobs)) + "\n"
        cu = tro.read_text(encoding="utf-8") if tro.is_file() else None
        if cu != noi:
            tam = tro.with_suffix(".part")
            tam.write_text(noi, encoding="utf-8")
            os.replace(tam, tro)
            if not kq["moi"]:
                kq["doi"].append(TEN_TRO_JOBS)
        if not (dich / "Info.lua").is_file():
            kq["loi"] = "chép xong mà thiếu Info.lua"
    except OSError as ex:
        kq["loi"] = f"{type(ex).__name__}: {ex}"
    return kq


def plugin() -> Path:
    """Thư mục plugin Lightroom dùng thật — chép từ gói ra lần đầu, các lần sau
    cập nhật file mã khi bản cài mang plugin mới hơn (giữ nguyên jobs/).

    Không chép đè CẢ thư mục: sẽ xoá mất thư mục jobs đang chờ Lightroom xử
    lý, và ăn mất kết quả của lần chạy trước.
    """
    dich = goc_du_lieu() / "AutoTone.lrplugin"
    if not dong_goi():
        return Path(__file__).resolve().parent / "AutoTone.lrplugin"
    nguon = goc_tai_nguyen() / "AutoTone.lrplugin"
    if dich.exists() and nguon.is_dir() and not _DA_SOAT_PLUGIN:
        _DA_SOAT_PLUGIN.append(True)          # moi lan mo app soat MOT lan
        PLUGIN_CAP_NHAT[:] = _cap_nhat_plugin(nguon, dich)
    if not dich.exists() and nguon.is_dir():
        try:
            tao(dich.parent)
            #[[ KHONG CHEP THU MUC jobs THEO.
            #
            #   jobs/ la TRANG THAI LUC CHAY, khong phai tai nguyen: nhat ky
            #   plugin, job da xong, va ban xuat tu catalog Lightroom. Chep no
            #   sang may moi la moi ban cai deu khoi dong voi lich su cua studio
            #   khac — va te nhat, voi mot ban xuat CU.
            #
            #   Hong that 4/9: goi build ra mang theo export_20260903_105234.tsv
            #   (buoi 2905, 220 anh). Ban .exe chep no ra roi doc phai, nen buoi
            #   G:\\0608 96 anh bi bao "ban xuat chi khop 0 anh" — trong khi
            #   Lightroom van xuat dung, chi la xuat vao MOT THU MUC KHAC.
            #
            #   dong_goi.py cung da loc jobs/ ra khong cho vao goi. Chan o ca
            #   hai dau: goi cu (da lo build roi) van duoc cuu o day.
            #]]
            shutil.copytree(nguon, dich,
                            ignore=shutil.ignore_patterns("jobs"))
        except OSError:
            pass
    tao(dich / "jobs")
    #  9/10: bản tự nạp trong thư mục Modules của Lightroom (xem cai_vao_modules)
    if not _DA_CAI_MODULES and nguon.is_dir():
        _DA_CAI_MODULES.append(True)
        ly_do = ly_do_khong_cai_modules()
        if ly_do:
            PLUGIN_MODULES.clear()
            PLUGIN_MODULES.update({"duong": "", "moi": False, "doi": [], "loi": "",
                                   "bo_qua": ly_do})
        else:
            PLUGIN_MODULES.clear()
            PLUGIN_MODULES.update(cai_vao_modules(nguon, dich / "jobs"))
    return dich


def mo_ta() -> str:
    return (f"tài nguyên: {goc_tai_nguyen()}\n"
            f"dữ liệu   : {goc_du_lieu()}\n"
            f"plugin    : {plugin()}\n"
            f"đóng gói  : {'có' if dong_goi() else 'không (chạy từ mã nguồn)'}")


if __name__ == "__main__":
    print(mo_ta())
