"""Duyệt nhanh — phía Python của cầu nối sang plugin Lightroom.

VÌ SAO CÓ MODULE NÀY
    Sau khi plugin ghi màu mới vào catalog, còn một khâu bắt buộc trước khi
    Export: soát lại cả buổi xem tấm nào chưa ổn rồi sửa. Soát trong Lightroom
    thì phải chờ nó dựng preview — Standard preview cho hơn nghìn ảnh rất lâu,
    Smart Preview còn lâu hơn, và bật Smart Preview lúc Import làm Import chậm
    hẳn.

    SDK Lua của Lightroom KHÔNG có API nào cho preview. Nhưng nó có
    LrExportSession — bộ render thật của Lightroom, dùng GPU khi bật "Use
    Graphics Processor for Export". Nên plugin xuất ảnh JPEG nhỏ ra một thư mục,
    còn app mở mấy ảnh đó lên để soát. Ảnh JPEG thường thì mở tức thì, không
    dính preview cache của Lightroom chút nào.

    Xem AutoTone.lrplugin/DuyetCore.lua cho phía Lua.

CÁC FILE TRAO ĐỔI (đều nằm trong AutoTone.lrplugin/jobs)
    request_duyet.txt     app ghi  -> plugin đọc rồi xoá
    duyet_tiendo.txt      plugin ghi -> app đọc  (trang_thai / xong / tong ...)
    duyet_anh.tsv         plugin ghi -> app đọc  (path <TAB> jpg), ghi SAU MỖI LÔ
    request_danhdau.tsv   app ghi  -> plugin đọc rồi xoá

    Cùng một cơ chế file với job áp thông số, cố ý: không thêm công nghệ mới
    nào để phải đi gỡ khi hỏng.
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path

import autotone as at

CANH = 1600          # cạnh dài ảnh duyệt, px
CHAT = 70            # chất lượng JPEG, thang 0..100 (Lua đổi sang 0..1)
LO = 25              # số ảnh mỗi lô export

# Lưới soát: cạnh ảnh nhỏ và kích thước một ô (dùng chung với duyet_ui.py)
DEM = 14                # khoảng đệm quanh mỗi ô
CAO_TEN = 16            # chỗ cho dòng tên file dưới ảnh
VANH_DAI = 2            # số hàng dựng thêm trên/dưới vùng nhìn thấy
CANH_NHO = 240          # cạnh ảnh nhỏ trong lưới soát
O_NGANG = CANH_NHO + DEM
O_DOC = CANH_NHO + DEM + CAO_TEN

TEN_TIEN_DO = "duyet_tiendo.txt"
TEN_BANG = "duyet_anh.tsv"
TEN_YEU_CAU = "request_duyet.txt"
TEN_DANH_DAU = "request_danhdau.tsv"
TEN_CO_DUNG = "request_duyet_dung.txt"

#[[ So anh cua luot CHAY THU.
#   50 la muc do dai de biet toc do that (2 lo) ma van chi mat vai chuc giay.
#   Truoc day de 20; nguoi dung muon 50. ]]
GIOI_HAN_THU = 50


def thu_muc_job(job_dir: Path | None = None) -> Path:
    return Path(job_dir or at.LR_JOB_DIR)


def thu_muc_duyet(folder: Path | str) -> Path:
    """Nơi plugin đổ ảnh duyệt ra: <thư mục buổi chụp>/_duyet.

    Đặt cạnh ảnh gốc chứ không vào %TEMP%: người dùng nhìn thấy được, xoá được,
    và nếu ổ ảnh là SSD thì ghi/đọc cũng nhanh nhất ở đó."""
    return Path(folder) / "_duyet"


# ------------------------------------------------------------------ gửi yêu cầu

def yeu_cau(folder: Path | str, dest: Path | str | None = None,
            canh: int = CANH, chat: int = CHAT, lo: int = LO,
            bo_sao: int | None = None, gioi_han: int | None = None,
            job_dir: Path | None = None) -> Path:
    """Nhờ plugin dựng ảnh duyệt cho một thư mục. Trả về đường dẫn file yêu cầu.

    gioi_han: chỉ dựng N ảnh đầu — đường CHẠY THỬ để đo tốc độ thật trước khi
    cho chạy cả buổi.
    """
    d = thu_muc_job(job_dir)
    d.mkdir(parents=True, exist_ok=True)

    #[[ Xoá tiến trình CŨ trước khi gửi yêu cầu mới.
    #   Không xoá thì trong mấy giây đầu (plugin dò 5 giây một lần) app đọc
    #   phải trang_thai=xong của lần trước và tưởng đã xong ngay lập tức.
    #]]
    for ten in (TEN_TIEN_DO, TEN_BANG, TEN_CO_DUNG):
        try:
            (d / ten).unlink()
        except OSError:
            pass

    if dest is None:
        dest = thu_muc_duyet(folder)
    body = [str(Path(folder).resolve()),
            f"dest={Path(dest).resolve()}",
            f"canh={int(canh)}",
            f"chat={int(chat)}",
            f"lo={int(lo)}"]
    if bo_sao is None:
        bo_sao = at.DEFAULTS.get("export_skip_rating")
    if bo_sao:
        body.append(f"bo_sao={int(bo_sao)}")
    if gioi_han:
        body.append(f"gioi_han={int(gioi_han)}")

    dest_f = d / TEN_YEU_CAU
    tmp = d / (TEN_YEU_CAU + ".part")
    tmp.write_text("\n".join(body) + "\n", encoding="utf-8")
    os.replace(tmp, dest_f)
    return dest_f


def dang_cho(job_dir: Path | None = None) -> bool:
    """Yêu cầu đã gửi nhưng plugin chưa nhận (file vẫn còn đó)."""
    return (thu_muc_job(job_dir) / TEN_YEU_CAU).exists()


# --------------------------------------------------------------- xin dừng


def dung(job_dir: Path | None = None) -> Path:
    """Xin plugin dừng dựng ảnh duyệt. Nó dừng sau khi xong lô đang chạy.

    VÌ SAO CẦN: thư mục 2000 ảnh mà lỡ bấm chạy cả buổi thì không có đường nào
    thoát — vòng lặp nền của plugin không có nút bấm, còn tắt Lightroom giữa
    chừng là cách tệ nhất. Đặt một file cờ là đủ; plugin kiểm giữa hai lô.

    Không cắt ngang giữa một lô: LrExportSession đã chạy thì để nó chạy hết,
    cắt ngang là để lại file dở trên đĩa."""
    d = thu_muc_job(job_dir)
    d.mkdir(parents=True, exist_ok=True)
    p = d / TEN_CO_DUNG
    p.write_text("dung\n", encoding="utf-8")
    return p


def xoa_dung(job_dir: Path | None = None) -> None:
    """Xoá cờ dừng. Gọi trước mỗi lượt mới — sót cờ cũ thì lượt mới dừng ngay
    sau lô đầu mà không ai hiểu vì sao."""
    try:
        (thu_muc_job(job_dir) / TEN_CO_DUNG).unlink()
    except OSError:
        pass


def dang_xin_dung(job_dir: Path | None = None) -> bool:
    return (thu_muc_job(job_dir) / TEN_CO_DUNG).exists()


# ------------------------------------------------------------------ đọc kết quả

def tien_do(job_dir: Path | None = None) -> dict:
    """Trạng thái lần dựng ảnh duyệt gần nhất.

    Khoá: trang_thai (dang_chay/xong/loi), xong, tong, loi, thu_muc, tsv,
    thong_bao. Trả về {} nếu chưa có gì."""
    p = thu_muc_job(job_dir) / TEN_TIEN_DO
    out: dict[str, str] = {}
    try:
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            k, _, v = line.partition("=")
            if k:
                out[k.strip()] = v.strip()
    except OSError:
        return {}
    for k in ("xong", "tong", "loi"):
        if k in out:
            try:
                out[k] = int(out[k])                          # type: ignore[assignment]
            except ValueError:
                pass
    return out


def bang_anh(job_dir: Path | None = None) -> list[tuple[str, str]]:
    """Cặp (ảnh gốc, ảnh duyệt). Plugin ghi lại sau MỖI LÔ, nên đọc giữa chừng
    cũng ra danh sách hợp lệ — nhờ vậy soát được ngay khi lô đầu xong."""
    p = thu_muc_job(job_dir) / TEN_BANG
    out: list[tuple[str, str]] = []
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out
    for line in lines[1:]:
        if not line:
            continue
        v = line.split("\t")
        if len(v) >= 2 and v[0] and v[1]:
            out.append((v[0], v[1]))
    return out


# ------------------------------------------------------------- đánh dấu cần sửa

NHAN_HOP_LE = ("red", "yellow", "green", "blue", "purple", "none")

#[[ So sao gan cho anh CAN SUA.
#
#   3 sao — khong phai 1. Trong quy uoc cua buoi chup, 1 sao la ANH LOAI:
#   pick_burst tu gan 1 sao cho anh trung khung, va anh 1 sao khong duoc
#   Export cung khong duoc retouch. Gan 1 sao cho anh can sua la vut chung
#   di thay vi danh dau de sua.
#
#   LUU Y: dat sao la GHI DE len sao cu cua anh. Anh dang 5 sao ma bi danh dau
#   can sua se tut ve 3. Dat SAO_CAN_SUA = None neu khong muon dung toi sao.
#]]
SAO_CAN_SUA = 3


def ten_bo_suu_tap(folder: Path | str | None = None) -> str:
    """Tên bộ sưu tập Lightroom chứa ảnh cần sửa của buổi này."""
    ten = Path(folder).name if folder else ""
    return f"AutoTone cần sửa · {ten}" if ten else "AutoTone cần sửa"


def danh_dau(paths, nhan: str = "red", sao: int | None = None,
             bo_suu_tap: str | None = None,
             job_dir: Path | None = None) -> Path | None:
    """Gom mấy ảnh cần sửa lại để tìm lại được trong Lightroom.

    BỘ SƯU TẬP LÀ ĐƯỜNG CHÍNH, NHÃN MÀU CHỈ LÀ PHỤ.
        Nhãn màu lọc được thật (Library Filter Bar → Attribute), nhưng thanh
        lọc hay bị ẩn hoặc đang ở "Filters Off" nên nhìn như không có; nó còn
        đè lên hệ thống nhãn riêng của người dùng; và lọc xong phải nhớ tắt
        lọc đi.

        Bộ sưu tập nằm sẵn ở cột trái, bấm một cái ra đúng danh sách, không
        đụng nhãn hay sao của ảnh, xoá đi là hết. Đặt nhan="none" nếu chỉ muốn
        bộ sưu tập mà không đụng tới nhãn.
    """
    paths = [str(p) for p in paths if str(p).strip()]
    if not paths:
        return None
    if nhan not in NHAN_HOP_LE:
        raise ValueError(f"nhãn không hợp lệ: {nhan}")

    d = thu_muc_job(job_dir)
    d.mkdir(parents=True, exist_ok=True)
    lines = []
    if bo_suu_tap:
        #[[ Dong # o dau file la tuy chon; phia Lua doc chung TRUOC dong tieu
        #   de cot. Ban plugin cu (chi biet bo dung dong dau) se coi dong nay
        #   la tieu de va coi dong "path nhan sao" la du lieu — mat dung mot
        #   dong rac, khong anh huong anh that. Chap nhan duoc, nhung nho nap
        #   lai plugin de co bo suu tap. ]]
        lines.append(f"#bo_suu_tap={bo_suu_tap}")
    lines.append("path\tnhan\tsao")
    s = "" if sao is None else str(int(sao))
    for p in paths:
        lines.append(f"{p}\t{nhan}\t{s}")

    dest = d / TEN_DANH_DAU
    tmp = d / (TEN_DANH_DAU + ".part")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, dest)
    return dest


# ---------------------------------------------------------------- ảnh nhỏ (lưới)

def thu_muc_nho(dest: Path | str) -> Path:
    return Path(dest) / ".nho"


def anh_nho(jpg: Path | str, canh: int = CANH_NHO) -> Path | None:
    """Đường dẫn ảnh nhỏ dùng cho lưới soát, dựng nếu chưa có.

    Có bộ nhớ đệm trên đĩa: mở lại cửa sổ soát lần hai thì không phải thu nhỏ
    lại cả nghìn ảnh. Trả về None nếu không dựng được (thiếu Pillow, file hỏng)
    — nơi gọi phải chịu được None chứ không được vỡ."""
    jpg = Path(jpg)
    if not jpg.is_file():
        return None
    kho = thu_muc_nho(jpg.parent)
    ra = kho / f"{jpg.stem}_{canh}.jpg"
    try:
        if ra.is_file() and ra.stat().st_mtime >= jpg.stat().st_mtime:
            return ra
    except OSError:
        pass
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        kho.mkdir(parents=True, exist_ok=True)
        with Image.open(jpg) as im:
            im = im.convert("RGB")
            im.thumbnail((canh, canh))
            tmp = ra.with_suffix(".part")
            im.save(tmp, "JPEG", quality=82)
        os.replace(tmp, ra)
        return ra
    except Exception:                                          # noqa: BLE001
        return None


def don_dep(dest: Path | str) -> int:
    """Xoá cả thư mục ảnh duyệt. Trả về số byte đã giải phóng (ước lượng)."""
    dest = Path(dest)
    if not dest.is_dir():
        return 0
    tong = 0
    for p in dest.rglob("*"):
        try:
            if p.is_file():
                tong += p.stat().st_size
        except OSError:
            pass
    shutil.rmtree(dest, ignore_errors=True)
    return tong


# ------------------------------------------------------------------ ghi lựa chọn

def file_luu(dest: Path | str) -> Path:
    return Path(dest) / "da_soat.tsv"


def luu_lua_chon(dest: Path | str, can_sua, da_soat) -> Path:
    """Nhớ lại đã soát tới đâu và tấm nào cần sửa.

    Đóng cửa sổ giữa chừng rồi mở lại là chuyện thường với hơn nghìn ảnh; không
    lưu thì lần nào cũng phải soát lại từ đầu."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    can = {str(p) for p in can_sua}
    lines = ["path\tcan_sua"]
    for p in sorted({str(x) for x in da_soat} | can):
        lines.append(f"{p}\t{'1' if p in can else '0'}")
    ra = file_luu(dest)
    tmp = ra.with_suffix(".part")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, ra)
    return ra


def doc_lua_chon(dest: Path | str) -> tuple[set[str], set[str]]:
    """Trả về (cần sửa, đã soát)."""
    can: set[str] = set()
    soat: set[str] = set()
    try:
        lines = file_luu(dest).read_text(encoding="utf-8",
                                         errors="replace").splitlines()
    except OSError:
        return can, soat
    for line in lines[1:]:
        if not line:
            continue
        v = line.split("\t")
        if v and v[0]:
            soat.add(v[0])
            if len(v) > 1 and v[1] == "1":
                can.add(v[0])
    return can, soat


# ------------------------------------------------- toán bố cục lưới soát (thuần)
#
# Để ở đây chứ không ở duyet_ui.py: file kia import tkinter, mà phần này phải
# kiểm được trên máy không màn hình. Đây cũng là chỗ dễ sai nhất của lưới —
# "bấm vào ô nào ra đúng ô đó" — nên càng phải kiểm được.

def so_cot(be_ngang: int, o: int = O_NGANG) -> int:
    """Số cột vừa trong bề ngang này. Luôn >= 1, kể cả cửa sổ hẹp bất thường."""
    return max(1, int(be_ngang) // max(1, o))


def vi_tri(i: int, cot: int, o_ngang: int = O_NGANG,
           o_doc: int = O_DOC) -> tuple[int, int]:
    """Toạ độ góc trái trên của ô thứ i (đếm từ 0)."""
    cot = max(1, cot)
    return (i % cot) * o_ngang, (i // cot) * o_doc


def chi_so_tai(x: int, y: int, cot: int, tong: int,
               o_ngang: int = O_NGANG, o_doc: int = O_DOC) -> int | None:
    """Ô nào nằm ở toạ độ này. None nếu bấm vào chỗ trống ngoài lưới."""
    cot = max(1, cot)
    if x < 0 or y < 0:
        return None
    c = int(x) // o_ngang
    if c >= cot:
        return None
    i = (int(y) // o_doc) * cot + c
    return i if 0 <= i < tong else None


def khoang_hang(dinh: int, cao: int, o_doc: int = O_DOC,
                vanh: int = VANH_DAI) -> tuple[int, int]:
    """Khoảng hàng cần dựng ảnh, tính từ vị trí cuộn và chiều cao khung nhìn."""
    dau = max(0, int(dinh) // o_doc - vanh)
    cuoi = int(dinh + cao) // o_doc + vanh
    return dau, cuoi


def tong_cao(tong: int, cot: int, o_doc: int = O_DOC) -> int:
    cot = max(1, cot)
    return max(1, -(-tong // cot)) * o_doc



def mo_ta(td: dict) -> str:
    """Một dòng mô tả trạng thái, dùng chung cho nhãn trong app."""
    tt = td.get("trang_thai")
    if not tt:
        return ""
    if tt == "dang_chay":
        return f"Đang dựng ảnh duyệt {td.get('xong', 0)}/{td.get('tong', 0)}…"
    if tt in ("xong", "dung"):
        n = td.get("xong", 0)
        loi = int(td.get("loi") or 0)
        s = (f"Đã dừng sau {n} ảnh duyệt" if tt == "dung"
             else f"Đã dựng xong {n} ảnh duyệt")
        if td.get("thong_bao"):
            s += f" ({td['thong_bao']})"
        if loi:
            s += f" · {loi} ảnh không ra file"
        return s
    return f"Lỗi khi dựng ảnh duyệt: {td.get('thong_bao') or 'không rõ'}"


def stamp() -> str:
    return datetime.now().strftime("%H:%M:%S")
