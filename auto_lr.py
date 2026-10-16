# -*- coding: utf-8 -*-
"""auto_lr.py — nhờ plugin bấm AUTO (bảng Basic của Lightroom) cho các ảnh (16/10).

#[[ User 16/10: "Bật chế độ Auto của phần Basic của tất cả các ảnh -> Đo các thông số hiện tại
#   trên vùng da để bắt đầu căn chỉnh lại cho về với da đích -> WB -> Tone -> Curve RGB -> Áp
#   lại LR -> Kiểm tra lại sau khi add thông số mới đã về với da đích chưa -> Nếu chưa thì xử
#   lý WB -> Tone -> áp lại LR". Chọn: chế độ mới bật / tắt ("Quy trình Auto Lightroom (thử
#   nghiệm)"), GIỮ tông của Auto (tool chỉ đổi WB, Exposure, Curve R/G/B), tối đa 2 vòng kiểm. ]]

Giao tiếp với AutoCore.lua qua thư mục job (như Denoise):
    request_auto.txt  — app ghi: "#ma=<mã>" + mỗi dòng một đường dẫn ảnh
    auto_tiendo.txt   — plugin ghi: ma, xong, tong, trang_thai
    auto_anh.tsv      — plugin ghi: "#ma=", tiêu đề, mỗi ảnh: path + thông số SAU Auto
    ketqua_auto.txt   — plugin ghi khi xong: ma, tong, bat, khong_doi, khong_thay, loi, dung…
    dung_auto.txt     — app ghi "ma=<mã>" để xin dừng ngay sau ảnh đang làm
Plugin cũ không khai "auto1" trong nhịp -> app không gửi (cần bộ cài đầy đủ — OTA không mang Lua).
"""
from __future__ import annotations

import os
from pathlib import Path

KHA_NANG = "auto1"
TEN_YEU_CAU = "request_auto.txt"
TEN_TIEN_DO = "auto_tiendo.txt"
TEN_BANG = "auto_anh.tsv"
TEN_KET_QUA = "ketqua_auto.txt"
TEN_DUNG = "dung_auto.txt"
#: ô tông + WB plugin đọc lại sau Auto (đúng thứ tự cột AutoCore.M.O)
O = ("Exposure2012", "Contrast2012", "Highlights2012", "Shadows2012", "Whites2012",
     "Blacks2012", "Vibrance", "Saturation", "Temperature", "Tint", "WhiteBalance")
#: ô Auto (bảng Basic) đổi — vào LỊCH SỬ GHI của tool (không WB: Auto tông không đụng WB)
O_TONE = O[:8]
#: bản ghi lịch sử: ghi_auto_<giờ>_<buổi>.done (at._lich_su_ghi gộp như job @curve)
TIEN_TO_LICH_SU = "ghi_auto_"


def _d(job_dir: Path | None = None) -> Path:
    import autotone as at
    return Path(job_dir or at.LR_JOB_DIR)


def yeu_cau(paths: list, ma: str, job_dir: Path | None = None) -> Path:
    """Nhờ plugin bấm Auto cho các ảnh. Xoá lệnh dừng / kết quả của lượt trước."""
    d = _d(job_dir)
    d.mkdir(parents=True, exist_ok=True)
    for ten in (TEN_DUNG, TEN_TIEN_DO, TEN_BANG, TEN_KET_QUA):
        try:
            (d / ten).unlink()
        except OSError:
            pass
    dest = d / TEN_YEU_CAU
    tmp = d / (TEN_YEU_CAU + ".part")
    tmp.write_text(f"#ma={ma}\n" + "".join(f"{p}\n" for p in paths), encoding="utf-8")
    os.replace(tmp, dest)
    return dest


def dang_cho(job_dir: Path | None = None) -> bool:
    return (_d(job_dir) / TEN_YEU_CAU).is_file()


def rut_yeu_cau(job_dir: Path | None = None) -> bool:
    """Plugin chưa nhận -> rút yêu cầu. True nếu rút được."""
    try:
        (_d(job_dir) / TEN_YEU_CAU).unlink()
        return True
    except OSError:
        return False


def xin_dung(ma: str, job_dir: Path | None = None) -> None:
    d = _d(job_dir)
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / (TEN_DUNG + ".part")
    tmp.write_text(f"ma={ma}\n", encoding="utf-8")
    os.replace(tmp, d / TEN_DUNG)


def _kv(f: Path) -> dict:
    try:
        return {k.strip(): v.strip() for k, _, v in
                (dong.partition("=") for dong in f.read_text(encoding="utf-8", errors="replace").splitlines())
                if k.strip()}
    except OSError:
        return {}


def tien_do(ma: str, job_dir: Path | None = None) -> dict:
    """{cho (chưa nhận), xong, tong, ket_qua (dict khi xong)} của lượt `ma`."""
    d = _d(job_dir)
    td, kq = _kv(d / TEN_TIEN_DO), _kv(d / TEN_KET_QUA)
    ra = {"cho": (d / TEN_YEU_CAU).is_file(), "xong": 0, "tong": 0, "ket_qua": None}
    if td.get("ma") == ma:
        for k in ("xong", "tong"):
            try:
                ra[k] = int(float(td.get(k) or 0))
            except ValueError:
                pass
    if kq.get("ma") == ma:
        ra["ket_qua"] = kq
    return ra


def _so(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def bang(ma: str, job_dir: Path | None = None) -> dict:
    """{khoá đường dẫn: {ô: số}} — thông số SAU Auto plugin đọc lại, của đúng lượt `ma`."""
    import autotone as at
    try:
        dong = (_d(job_dir) / TEN_BANG).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {}
    if not dong or dong[0].strip() != f"#ma={ma}" or len(dong) < 2:
        return {}
    cot = dong[1].split("\t")
    ra = {}
    for d in dong[2:]:
        o = d.split("\t")
        if not o or not o[0]:
            continue
        st = {}
        for k, v in zip(cot[1:], o[1:]):
            if v == "":
                continue
            st[k] = v if k == "WhiteBalance" else _so(v)
        ra[at.khoa_duong_dan(o[0])] = {k: v for k, v in st.items() if v is not None}
    return ra


def ghi_lich_su(ma: str, folder, job_dir: Path | None = None) -> Path | None:
    """Số Auto plugin vừa ghi (bảng của lượt `ma`) vào LỊCH SỬ GHI của tool -> lượt sau
    at.danh_dau_nguoi_sua không coi ảnh vừa Auto là ảnh người dùng sửa tay. -> file đã ghi.

    #[[ 16/10 TEST: dừng quy trình Auto ở 367/693 — 366 ảnh mang số Auto mà job cuối của tool
    #   (17:02) ghi số khác -> lượt sau bị nhận "sửa tay" và bị LOẠI khỏi lượt, lặng lẽ.
    #   Tên KHÔNG theo mẫu apply_*.done: nhiều chỗ quét apply_*.done (lần áp gần nhất, tổng kết,
    #   góp ý) — chỉ at._lich_su_ghi đọc ghi_auto_*. ]]"""
    import autotone as at
    from datetime import datetime
    d = _d(job_dir)
    try:
        dong = (d / TEN_BANG).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    if len(dong) < 3 or dong[0].strip() != f"#ma={ma}":
        return None
    cot = dong[1].split("\t")
    vi = [cot.index(k) if k in cot else -1 for k in O_TONE]
    ra = ["path\t" + "\t".join(O_TONE)]
    for d_ in dong[2:]:
        o = d_.split("\t")
        if not o or not o[0]:
            continue
        gt = [o[i] if 0 <= i < len(o) else "" for i in vi]
        if any(gt):
            ra.append("\t".join([o[0]] + gt))
    if len(ra) < 2:
        return None
    f = d / f"{TIEN_TO_LICH_SU}{datetime.now():%Y%m%d_%H%M%S}_{at.ten_job(Path(folder).name)}.done"
    tmp = f.with_name(f.name + ".part")
    tmp.write_text("\n".join(ra) + "\n", encoding="utf-8")
    os.replace(tmp, f)
    return f
