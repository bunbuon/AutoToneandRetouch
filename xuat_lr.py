#!/usr/bin/env python3
"""Đọc thư mục Export mà plugin bắt được từ chính hộp thoại Export của Lightroom.

VÌ SAO CÓ FILE NÀY
    trang_thai.py vẫn ghi trong chú thích rằng thư mục Export là một trong ba
    thứ "không có cách nào đoán" — vì Lightroom không phát sự kiện Export nào
    để nghe từ ngoài, và không để lại dấu vết nào trên đĩa.

    Câu đó đúng với MỌI CÁCH ĐỌC TỪ NGOÀI, và bây giờ vẫn đúng. Chỗ đổi là ta
    không đọc từ ngoài nữa: plugin tự cắm vào bên trong luồng Export dưới dạng
    Export Filter, nên nhận thẳng bảng thông số người dùng vừa chọn. Xem đầu
    AutoTone.lrplugin/BatDuongDan.lua.

    File này chỉ là phía đọc: nó KHÔNG suy diễn gì thêm, chỉ đọc lại đúng thứ
    plugin đã ghi, kèm mốc thời gian để nơi gọi tự quyết định có tin hay không.

KHÔNG TỰ ĐIỀN ĐÈ LÊN LỰA CHỌN CỦA NGƯỜI DÙNG
    Người dùng đã tự gõ thư mục Export rồi thì cái họ gõ thắng. Bản bắt được
    chỉ dùng để GỢI Ý khi ô còn trống, hoặc để cảnh báo khi hai bên lệch nhau.
    Lặng lẽ thay đường dẫn dưới tay người dùng là kiểu lỗi không ai lần ra được.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at   # noqa: E402

TEN_FILE = "export_lr_duongdan.txt"


def thu_muc_job(job_dir: Path | None = None) -> Path:
    return Path(job_dir or at.LR_JOB_DIR)


def doc(job_dir: Path | None = None) -> dict:
    """Bản ghi gần nhất plugin bắt được, {} nếu chưa có lần Export nào.

    Trả về các khoá: thu_muc, kieu, thu_muc_con, dinh_dang, tem, nguon,
    và thêm 'luc' (datetime) nếu đọc được mốc thời gian.
    """
    p = thu_muc_job(job_dir) / TEN_FILE
    if not p.is_file():
        return {}
    out: dict = {}
    try:
        for dong in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in dong:
                k, v = dong.split("=", 1)
                out[k.strip()] = v.strip()
    except OSError:
        return {}
    if not out.get("thu_muc"):
        return {}
    tem = out.get("tem", "")
    try:
        out["luc"] = datetime.strptime(tem, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        #[[ Khong co moc thoi gian thi VAN tra ve duong dan. Duong dan la thu
        #   dang gia tri; moc thoi gian chi de xep hang moi/cu. Vut ca ban ghi
        #   chi vi thieu mot dong la tu lam minh mu. ]]
        pass
    return out


def con_moi(job_dir: Path | None = None, gio: float = 24.0) -> bool:
    """Bản bắt được có mới trong vòng `gio` tiếng không."""
    d = doc(job_dir)
    luc = d.get("luc")
    if not isinstance(luc, datetime):
        return False
    return (datetime.now() - luc).total_seconds() <= gio * 3600


def cung_mot_cho(a: str, b: str) -> bool:
    """Hai đường dẫn có trỏ về cùng một thư mục không.

    Windows: không phân biệt hoa thường, và dấu \\ với / như nhau. So chuỗi
    thẳng thì "F:/Out" với "F:\\out\\" thành hai chỗ khác nhau — rồi app dựng
    một cảnh báo lệch thư mục hoàn toàn vô nghĩa.
    """
    def chuan(x: str) -> str:
        return str(x or "").replace("/", "\\").rstrip("\\").lower()
    return bool(a) and bool(b) and chuan(a) == chuan(b)


def mo_ta(job_dir: Path | None = None) -> str:
    """Một dòng chữ cho giao diện. "" nếu chưa bắt được lần nào."""
    d = doc(job_dir)
    if not d:
        return ""
    tem = d.get("tem", "")
    return f"Lightroom vừa Export ra {d['thu_muc']}" + (f" · {tem}" if tem else "")


# ===================================================================
#  PHÍA GỬI: bảo plugin tự chạy một lượt Export
# ===================================================================
#
#[[ VI SAO CO NUA NAY.
#
#   Nua tren cua file la duong "nghe": anh Export bang Lightroom, plugin chep
#   lai thu muc. Nua nay la duong "bao": app tu chay luot Export, nen thu muc
#   dich la do app dat ra — khong con gi de nghe, de doan, de hoi.
#
#   Hai duong doc lap. Hong duong nay thi duong kia van chay.
#]]

TEN_YEU_CAU_XUAT = "request_xuatanh.txt"
TEN_TIEN_DO_XUAT = "xuatanh_tiendo.txt"
TEN_CO_DUNG_XUAT = "request_xuatanh_dung.txt"


def _dong_thongso(thong_so: dict) -> list[str]:
    """Mỗi khoá thành một dòng CÓ MANG KIỂU.

    Gửi qua file văn bản thì "false" và 0.7 mất kiểu. Lightroom nhận sai kiểu
    thì lặng lẽ bỏ qua khoá đó — đúng cái bệnh "xuất ra ảnh 1 điểm ảnh mà
    không báo lỗi gì". Nên kiểu đi kèm giá trị, không suy lại ở đầu kia.
    """
    ra = []
    for k in sorted(thong_so):
        v = thong_so[k]
        if isinstance(v, bool):
            ra.append(f"ts\tb\t{k}\t{'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            ra.append(f"ts\tn\t{k}\t{v!r}" if isinstance(v, float)
                      else f"ts\tn\t{k}\t{v}")
        else:
            s = str(v)
            #[[ Gia tri co TAB hoac xuong dong se pha vo dinh dang dong. Chua
            #   gap bao gio, nhung bo qua con hon gui sang mot dong rac ma dau
            #   kia doc thanh khoa khac. ]]
            if "\t" in s or "\n" in s:
                continue
            ra.append(f"ts\ts\t{k}\t{s}")
    return ra


def yeu_cau_xuat(folder, dest, thong_so: dict, bo_sao: int | None = 1,
                 lo: int | None = None, job_dir: Path | None = None) -> Path:
    """Đặt yêu cầu để plugin chạy một lượt Export. Trả về đường dẫn file yêu cầu."""
    if not thong_so.get("LR_format"):
        raise ValueError("thiếu thông số export — không tự bịa")
    d = thu_muc_job(job_dir)
    d.mkdir(parents=True, exist_ok=True)
    dong = [str(folder), f"dest={dest}"]
    if bo_sao:
        dong.append(f"bo_sao={int(bo_sao)}")
    if lo:
        dong.append(f"lo={int(lo)}")
    dong += _dong_thongso(thong_so)
    p = d / TEN_YEU_CAU_XUAT
    #[[ .part roi doi ten: plugin do thu muc 5 giay mot lan, doc phai file dang
    #   ghi do la mot luot Export thieu thong so. ]]
    tmp = p.with_suffix(".part")
    tmp.write_text("\n".join(dong) + "\n", encoding="utf-8")
    tmp.replace(p)
    return p


def dang_cho_xuat(job_dir: Path | None = None) -> bool:
    d = thu_muc_job(job_dir)
    return (d / TEN_YEU_CAU_XUAT).exists() or (d / (TEN_YEU_CAU_XUAT + ".running")).exists()


def dung_xuat(job_dir: Path | None = None) -> Path:
    d = thu_muc_job(job_dir)
    d.mkdir(parents=True, exist_ok=True)
    p = d / TEN_CO_DUNG_XUAT
    p.write_text("dung\n", encoding="utf-8")
    return p


def tien_do_xuat(job_dir: Path | None = None) -> dict:
    p = thu_muc_job(job_dir) / TEN_TIEN_DO_XUAT
    if not p.is_file():
        return {}
    out: dict = {}
    try:
        for dong in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in dong:
                k, v = dong.split("=", 1)
                out[k.strip()] = v.strip()
    except OSError:
        return {}
    for k in ("xong", "tong", "loi", "bo_sao"):
        if k in out:
            try:
                out[k] = int(out[k])
            except ValueError:
                pass
    return out
