#!/usr/bin/env python3
"""Đọc thông số Export mà Lightroom đang dùng — để app Export ra y hệt anh làm tay.

VÌ SAO KHÔNG HỎI NGƯỜI DÙNG TỪNG Ô
    Hộp thoại Export của Lightroom có gần bốn chục ô. Dựng lại chúng trong app
    là vừa tốn công vừa chắc chắn lệch: chỉ cần quên một ô (độ nét đầu ra, không
    gian màu, quy tắc đặt tên) là ảnh giao khách khác với ảnh anh vẫn giao.

    Nên không hỏi. Lấy đúng thông số Lightroom đang có, theo hai nguồn:

    1. THÔNG SỐ LẦN EXPORT GẦN NHẤT — nằm trong file cấu hình của Lightroom:
           %APPDATA%\\Adobe\\Lightroom\\Preferences\\
               Lightroom Classic CC 7 Preferences.agprefs
       Mọi khoá bắt đầu bằng "AgExport_". Đổi tiền tố thành "LR_" là ra đúng
       tên khoá của LrExportSession — cùng bộ tên đã lấy từ .lrtemplate hồi
       làm Duyệt nhanh, nên không phải đoán.

    2. PRESET NGƯỜI DÙNG TỰ LƯU — các file .lrtemplate trong
           %APPDATA%\\Adobe\\Lightroom\\Export Presets\\User Presets\\
       (Máy này hiện chưa có cái nào — thư mục rỗng. Vẫn đọc được nếu sau này
       anh lưu preset.)

CHỖ KHÔNG ĐÁNG TIN, NÓI THẲNG
    File .agprefs do Lightroom ghi theo nhịp của nó, không ghi ngay lúc anh
    bấm OK. Nên nó có thể CŨ hơn lần Export gần nhất. Vì vậy hàm doc_prefs()
    trả về cả thời điểm sửa file, và nơi gọi phải cho người dùng thấy con số
    đó thay vì im lặng tin.

    Thư mục đích thì KHÔNG có trong file này (đã tìm: không có khoá nào chứa
    destinationPathPrefix). Đó đúng là chỗ Export Filter dùng để làm —
    xem xuat_lr.py.
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

#[[ DANH SACH TRANG, KHONG PHAI "lay tuot".
#
#   Cam do de tren duong LR_ va nem het vao LrExportSession. Nhung file cau
#   hinh chua ca khoa cua hop thoai, cua Publish, cua bo chuyen DNG... Mot khoa
#   la co the lam Lightroom xuat ra anh 1 diem anh MA KHONG BAO LOI GI — dung
#   cai benh da ghi o dau DuyetCore.lua.
#
#   Nen chi cho qua nhung khoa da biet mat. Danh sach nay la hop cua: bang
#   thong so trong DuyetCore.lua (lay tu .lrtemplate that) va cac khoa
#   AgExport_ doc duoc tu file cau hinh that cua may nay.
#]]
CHO_PHEP = {
    "exportServiceProvider", "exportServiceProviderTitle",
    "export_colorSpace", "export_colorSpaceJPEG", "export_bitDepth",
    "export_postProcessing", "export_useParentFolder",
    "format", "jpeg_quality", "jpeg_useLimitSize", "jpeg_limitSize",
    "extensionCase", "maximumCompatibility",
    "tiff_compressionMethod", "tiff_preserveTransparency",
    "png_interlaced", "avif_quality", "jxl_quality", "jxl_losslessQuality",
    "renamingTokensOn", "tokens", "tokenCustomString", "initialSequenceNumber",
    "size_doConstrain", "size_doNotEnlarge", "size_maxWidth", "size_maxHeight",
    "size_megapixels", "size_percentage", "size_resizeType", "size_resolution",
    "size_resolutionUnits", "size_units", "size_userWantsConstrain",
    "outputSharpeningOn", "outputSharpeningLevel", "outputSharpeningMedia",
    "metadata_keywordOptions", "minimizeEmbeddedMetadata",
    "embeddedMetadataOption", "removeLocationMetadata", "removeFaceMetadata",
    "includeFaceTagsAsKeywords", "includeFaceTagsInIptc",
    "includeVideoFiles", "export_videoFileHandling", "export_videoPreset",
    "useWatermark", "watermarking_id",
    "collisionHandling",
    "reimportExportedPhoto", "reimport_stackWithOriginal",
}

#[[ Mot dong scalar trong .agprefs. CO Y khong bat chuoi nhieu dong: khoa
#   AgExport_markedPresets chua ca mot bang Lua viet trong chuoi, nuot no vao
#   se keo theo rac. Khong khop thi bo qua — dung cai ta can. ]]
_DONG = re.compile(
    r'^\s*AgExport_(\w+)\s*=\s*'
    r'(true|false|-?\d+(?:\.\d+)?|"(?:[^"\\\n]*)")\s*,\s*$',
    re.MULTILINE)


def _gia_tri(raw: str):
    if raw == "true":
        return True
    if raw == "false":
        return False
    if raw.startswith('"'):
        return raw[1:-1]
    return float(raw) if "." in raw else int(raw)


def thu_muc_lr() -> Path | None:
    """%APPDATA%\\Adobe\\Lightroom — None nếu không phải Windows / không có."""
    app = os.environ.get("APPDATA")
    if not app:
        return None
    d = Path(app) / "Adobe" / "Lightroom"
    return d if d.is_dir() else None


def file_prefs(goc: Path | None = None) -> Path | None:
    """File cấu hình Lightroom mới nhất, bỏ file "Startup Preferences"."""
    goc = goc or thu_muc_lr()
    if not goc:
        return None
    d = goc / "Preferences"
    if not d.is_dir():
        return None
    ds = [p for p in d.glob("*.agprefs") if "Startup" not in p.name]
    if not ds:
        return None
    return max(ds, key=lambda p: p.stat().st_mtime)


def doc_prefs(p: Path | None = None, goc: Path | None = None) -> tuple[dict, datetime | None]:
    """Thông số Export lần gần nhất -> ({LR_...: giá trị}, lúc file được ghi)."""
    p = p or file_prefs(goc)
    if not p or not p.is_file():
        return {}, None
    try:
        van = p.read_text(encoding="utf-8", errors="replace")
        luc = datetime.fromtimestamp(p.stat().st_mtime)
    except OSError:
        return {}, None
    out = {}
    for khoa, raw in _DONG.findall(van):
        if khoa in CHO_PHEP:
            out["LR_" + khoa] = _gia_tri(raw)
    return out, luc


# ------------------------------------------------------------- preset .lrtemplate

#[[ .lrtemplate la mot bang Lua. Khong nap bang Lua that (khong co Lua o day, va
#   nap ma la nap ma), cung khong viet ca mot bo phan tich Lua. Chi can rut phan
#   value = { ... } roi doc tung dong scalar — dung ky thuat va dung gioi han
#   nhu voi .agprefs o tren. ]]
_DONG_TPL = re.compile(
    r'^\s*(\w+)\s*=\s*'
    r'(true|false|-?\d+(?:\.\d+)?|"(?:[^"\\\n]*)")\s*,\s*$',
    re.MULTILINE)


def doc_lrtemplate(p: Path) -> dict:
    """Thông số trong một file preset Export. {} nếu không đọc được."""
    try:
        van = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    i = van.find("value = {")
    if i < 0:
        return {}
    out = {}
    for khoa, raw in _DONG_TPL.findall(van[i:]):
        #[[ Trong .lrtemplate khoa KHONG co tien to; nhung mot so plugin ghi
        #   san "LR_". Nhan ca hai, dung them tien to hai lan. ]]
        goc = khoa[3:] if khoa.startswith("LR_") else khoa
        if goc in CHO_PHEP:
            out["LR_" + goc] = _gia_tri(raw)
    return out


def preset_nguoi_dung(goc: Path | None = None) -> list[tuple[str, Path]]:
    """Danh sách preset Export do người dùng tự lưu, [(tên, đường dẫn)]."""
    goc = goc or thu_muc_lr()
    if not goc:
        return []
    d = goc / "Export Presets" / "User Presets"
    if not d.is_dir():
        return []
    return sorted(((p.stem, p) for p in d.glob("*.lrtemplate")),
                  key=lambda x: x[0].lower())


# --------------------------------------------------------------- ép thông số

#[[ NHUNG KHOA APP LUON DAT DE, VA VI SAO TUNG CAI.
#
#   Day khong phai "app biet hon anh". Day la ba thu chi dung trong hop thoai
#   co nguoi ngoi truoc man hinh, ma vong lap nen thi khong co ai bam.
#]]
def ep(thong_so: dict, dest: str, va_cham: str = "overwrite") -> dict:
    st = dict(thong_so)
    st.update({
        # Ghi ra o cung, dung thu muc app chon — khong phai thu muc lan truoc.
        "LR_exportServiceProvider": "com.adobe.ag.export.file",
        "LR_exportServiceProviderTitle": "Hard Drive",
        "LR_export_destinationType": "specificFolder",
        "LR_export_destinationPathPrefix": dest,
        "LR_export_destinationPathSuffix": "",
        "LR_export_useSubfolder": False,
        "LR_export_useParentFolder": False,

        #[[ "ask" (dang la cai anh dung) se dung mot hop thoai giua chung. Vong
        #   lap nen khong co ai bam -> Lightroom treo, va nhin tu ngoai giong
        #   het "app hong". Bat buoc phai chon truoc. ]]
        "LR_collisionHandling": va_cham,

        # Khong mo Explorer sau moi lo.
        "LR_export_postProcessing": "doNothing",

        # Khong nem anh vua xuat nguoc vao catalog.
        "LR_reimportExportedPhoto": False,
        "LR_reimport_stackWithOriginal": False,
    })
    return st


def mo_ta(thong_so: dict) -> str:
    """Một dòng tóm tắt cho giao diện — thứ người dùng cần liếc để yên tâm."""
    if not thong_so:
        return ""
    dinh = str(thong_so.get("LR_format", "?"))
    phan = [dinh]
    if dinh.upper() == "JPEG":
        q = thong_so.get("LR_jpeg_quality")
        if isinstance(q, (int, float)):
            phan.append(f"chất lượng {round(float(q) * 100)}")
    if thong_so.get("LR_size_doConstrain"):
        phan.append(f'{thong_so.get("LR_size_maxWidth")}×'
                    f'{thong_so.get("LR_size_maxHeight")} px')
    else:
        phan.append("nguyên cỡ")
    phan.append(str(thong_so.get("LR_export_colorSpace", "")))
    if thong_so.get("LR_outputSharpeningOn"):
        phan.append("có làm nét")
    if thong_so.get("LR_useWatermark"):
        phan.append("CÓ watermark")
    if thong_so.get("LR_renamingTokensOn"):
        phan.append(f'đổi tên: {thong_so.get("LR_tokens", "")}')
    return " · ".join(x for x in phan if x)
