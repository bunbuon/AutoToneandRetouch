#!/usr/bin/env python3
"""Buổi chụp đang ở khâu nào — suy từ chính các file đã có trên đĩa.

VÌ SAO SUY TỪ ĐĨA, KHÔNG PHẢI TIN VÀO MỘT FILE TRẠNG THÁI
    File trạng thái nói "đã đẩy thông số rồi" thì nó chỉ đúng nếu không ai làm
    gì ngoài app: không chạy dòng lệnh, không xoá thư mục, không chép ảnh sang
    ổ khác, app không tắt giữa chừng. Trong dự án này cả năm chuyện đó đều đã
    xảy ra thật.

    Còn `apply_20260901_153907_1308.done` nằm trong thư mục job thì KHÔNG THỂ
    sai: nó ở đó vì plugin đã ghi xong. Nên mọi thứ suy được từ file thì suy,
    và file trạng thái chỉ giữ đúng phần không suy nổi:

      - thư mục anh Export ra. KHÔNG có cách nào đoán TỪ NGOÀI: Lightroom
        không phát sự kiện Export nào và không để lại dấu vết nào trên đĩa.
        Câu đó vẫn đúng nguyên. Chỗ đổi là plugin không đứng ngoài nữa — nó
        cắm một Export Filter vào chính luồng Export nên đọc được thư mục
        đích từ bảng thông số người dùng vừa chọn (xem xuat_lr.py và
        AutoTone.lrplugin/BatDuongDan.lua). Nhưng filter chỉ chạy khi người
        dùng đã tích nó trong hộp thoại Export, nên ô nhập tay vẫn phải còn,
        và trạng thái vẫn là nơi giữ câu trả lời cuối cùng.
      - thư mục retouch ghi vào
      - thời gian từng khâu (file chỉ cho biết LÚC NÀO xong, không cho biết MẤT
        BAO LÂU)

    Hỏng file trạng thái thì mất mấy con số thời gian, không mất trạng thái.

BẢY KHÂU
    1. Nạp ảnh        đếm file RAW trong thư mục buổi
    2. Phân tích      báo cáo autotone*.csv gần nhất
    3. Đẩy vào catalog apply_*_<buổi>.done gần nhất — số ảnh, số ảnh gắn 1 sao
    4. Export         thư mục Export (ghi trong trạng thái) — đếm ảnh
    5. Retouch        thư mục ra so với thư mục vào
    6. Gói duyệt      gu/<buổi>/gu.csv — bao nhiêu ảnh sửa, bao nhiêu đã gắn lý do
    7. Học            gu.json — tham số đã học được gì chưa
"""
from __future__ import annotations

import csv
import io
import json
import ntpath
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import duong_dan as dd
import autotone as at   # noqa: E402

GOC = dd.goc_du_lieu()
THU_MUC = GOC / "trang_thai"
ANH_RETOUCH = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def ten_buoi(folder) -> str:
    return ntpath.basename(str(folder).rstrip("\\/")) or str(folder)


def duong_dan(buoi: str) -> Path:
    return THU_MUC / f"{buoi}.json"


def doc(buoi: str) -> dict:
    p = duong_dan(buoi)
    if not p.is_file():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def ghi(buoi: str, **kw) -> dict:
    """Gộp vào trạng thái đang có. .part rồi đổi tên, không để file ghi dở."""
    d = doc(buoi)
    d.update(kw)
    d["cap_nhat"] = datetime.now().isoformat(timespec="seconds")
    THU_MUC.mkdir(parents=True, exist_ok=True)
    tmp = duong_dan(buoi).with_suffix(".part")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, duong_dan(buoi))
    return d


def ghi_khau(buoi: str, khau: str, giay: float, **kw) -> dict:
    """Ghi thời gian một khâu. Giữ cả lịch sử để so buổi này với buổi trước."""
    d = doc(buoi)
    ds = d.get("khau", {})
    ds[khau] = dict(kw, giay=round(float(giay), 1),
                    khi=datetime.now().isoformat(timespec="seconds"))
    return ghi(buoi, khau=ds)


# ---------------------------------------------------------------- đọc từ đĩa

def _moi_nhat(paths):
    ps = [p for p in paths if p.is_file()]
    return max(ps, key=lambda p: p.stat().st_mtime) if ps else None


def dem_raw(folder: Path) -> int:
    try:
        return sum(1 for p in Path(folder).iterdir()
                   if p.suffix.lower() in at.RAW_EXTS)
    except OSError:
        return 0


def dem_anh(folder) -> int:
    try:
        return sum(1 for p in Path(folder).iterdir()
                   if p.suffix.lower() in ANH_RETOUCH)
    except (OSError, TypeError):
        return 0


def _dem_tsv(p: Path) -> tuple:
    """(số dòng, số ảnh gắn 1 sao) trong một file job."""
    n = sao = 0
    try:
        with io.open(p, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh, delimiter="\t"):
                n += 1
                try:
                    if int(float(r.get("Rating") or 0)) == 1:
                        sao += 1
                except (TypeError, ValueError):
                    pass
    except OSError:
        return 0, 0
    return n, sao


def _khi(p: Path) -> str:
    try:
        return datetime.fromtimestamp(p.stat().st_mtime).strftime("%d/%m %H:%M")
    except OSError:
        return ""


def khau(ten: str, nhan: str, xong: bool, mo_ta: str, khi: str = "",
         giay: float | None = None, viec: str = "") -> dict:
    return {"ten": ten, "nhan": nhan, "xong": xong, "mo_ta": mo_ta,
            "khi": khi, "giay": giay, "viec": viec}


def tinh(folder, job_dir: Path | None = None) -> list:
    """Bảy khâu, mỗi khâu một dòng. Không đụng gì tới giao diện."""
    folder = Path(folder)
    buoi = ten_buoi(folder)
    st = doc(buoi)
    ds = st.get("khau", {})
    jd = Path(job_dir or at.LR_JOB_DIR)

    def g(k):
        return (ds.get(k) or {}).get("giay")

    out = []

    # 1 — nạp ảnh
    n_raw = dem_raw(folder)
    out.append(khau("nap", "Nạp ảnh", n_raw > 0,
                    f"{n_raw} ảnh RAW" if n_raw else "Chưa thấy ảnh RAW nào",
                    viec="" if n_raw else "Chọn đúng thư mục buổi chụp"))

    # 2 — phân tích
    bc = _moi_nhat(list(folder.glob("autotone*.csv")) + list(GOC.glob("autotone*.csv")))
    out.append(khau("phan_tich", "Phân tích", bc is not None,
                    f"Báo cáo {bc.name}" if bc else
                    "Chưa có báo cáo — bấm 1 · Phân tích rồi Xuất CSV",
                    _khi(bc) if bc else "", g("phan_tich"),
                    viec="" if bc else "1 · Phân tích"))

    # 3 — đẩy vào catalog
    ap = _moi_nhat([p for p in jd.glob(f"apply_*_{buoi}.done")
                    if "khoiphuc" not in p.name.lower()]) if jd.is_dir() else None
    if ap:
        n, sao = _dem_tsv(ap)
        mo = f"{n} ảnh đã ghi vào catalog" + (f", {sao} ảnh gắn 1 sao (bị lọc)" if sao else "")
    else:
        mo = "Chưa đẩy thông số nào cho buổi này"
    out.append(khau("day", "Đẩy vào Lightroom", ap is not None, mo,
                    _khi(ap) if ap else "", g("day"),
                    viec="" if ap else "2 · Ghi vào .xmp"))

    # 4 — Export
    #[[ KHONG DOAN duoc thu muc Export. Lightroom ghi ra dau la tuy nguoi dung
    #   chon trong hop thoai cua no, khong de lai dau vet nao ma app doc duoc.
    #   Nen day la mot trong ba thu PHAI luu vao file trang thai.
    #]]
    vao = st.get("thu_muc_export")
    n_vao = dem_anh(vao) if vao else 0
    out.append(khau("export", "Export", bool(vao and n_vao),
                    f"{n_vao} ảnh trong {Path(vao).name}" if vao and n_vao else
                    (f"Thư mục {vao} chưa có ảnh nào" if vao else
                     "Chưa biết anh Export ra đâu"),
                    _khi(Path(vao)) if vao and Path(vao).exists() else "",
                    g("export"),
                    viec="" if (vao and n_vao) else "Chỉ chỗ đã Export"))

    # 5 — retouch
    ra = st.get("thu_muc_retouch")
    n_ra = dem_anh(ra) if ra else 0
    xong_rt = bool(n_vao and n_ra >= n_vao)
    if not ra:
        mo = "Chưa chạy retouch"
    elif not n_vao:
        mo = f"{n_ra} ảnh trong {Path(ra).name}"
    else:
        mo = f"{n_ra}/{n_vao} ảnh" + ("" if xong_rt else f" — còn {n_vao - n_ra}")
    out.append(khau("retouch", "Retouch", xong_rt, mo,
                    _khi(Path(ra)) if ra and Path(ra).exists() else "", g("retouch"),
                    viec="" if xong_rt else "3 · Retouch"))

    # 6 — gói duyệt
    gu = GOC / "gu" / buoi / "gu.csv"
    if gu.is_file():
        tong = gan = 0
        try:
            with io.open(gu, encoding="utf-8-sig", newline="") as fh:
                for r in csv.DictReader(fh):
                    tong += 1
                    if (r.get("ly_do") or "").strip():
                        gan += 1
        except OSError:
            pass
        mo = f"{gan}/{tong} ảnh đã gắn lý do"
        xong_gu = tong > 0 and gan >= tong
    else:
        mo, xong_gu, tong, gan = "Chưa thu gói duyệt", False, 0, 0
    out.append(khau("gu", "Vì sao tôi sửa", xong_gu, mo,
                    _khi(gu) if gu.is_file() else "", g("gu"),
                    viec="" if xong_gu else "Vì sao tôi sửa"))

    # 7 — gu đã học
    out.append(khau("hoc", "Gu đã học", bool(at.GU_DA_HOC), at.mo_ta_gu()))
    return out


def tom_tat(folder, job_dir: Path | None = None) -> str:
    """Bản tóm tắt cuối buổi — dán được vào tin nhắn."""
    ks = tinh(folder, job_dir)
    buoi = ten_buoi(folder)
    d = ["=" * 58, f"BUOI {buoi}", "=" * 58]
    tong_giay = 0.0
    for k in ks:
        dau = "x" if k["xong"] else "."
        t = ""
        if k["giay"]:
            tong_giay += k["giay"]
            t = f"   [{k['giay'] / 60:.1f} phut]"
        d.append(f"  [{dau}] {k['nhan']:<20}{k['mo_ta']}{t}")
        if k["khi"]:
            d[-1] += f"   ({k['khi']})"
    if tong_giay:
        d.append("-" * 58)
        d.append(f"  Tong thoi gian may chay: {tong_giay / 60:.1f} phut")
        #[[ Chi cong nhung khau CO do. Khau khong do thi bo qua, khong doan —
        #   mot con so tong ma mot nua la uoc luong thi khong so sanh duoc voi
        #   buoi sau, ma so sanh moi la ly do co no.
        #]]
        thieu = [k["nhan"] for k in ks if not k["giay"] and k["xong"]
                 and k["ten"] not in ("nap", "hoc")]
        if thieu:
            d.append(f"  (chua do: {', '.join(thieu)})")
    con = [k for k in ks if not k["xong"] and k["viec"]]
    if con:
        d.append("-" * 58)
        d.append(f"  Viec tiep theo: {con[0]['viec']}")
    return "\n".join(d)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Buoi chup dang o khau nao.")
    ap.add_argument("folder", type=Path)
    ap.add_argument("--export", type=Path, default=None,
                    help="Chi ro thu muc da Export ra (luu lai cho lan sau)")
    ap.add_argument("--retouch", type=Path, default=None,
                    help="Chi ro thu muc retouch ghi vao")
    a = ap.parse_args(argv)
    buoi = ten_buoi(a.folder)
    if a.export:
        ghi(buoi, thu_muc_export=str(a.export))
    if a.retouch:
        ghi(buoi, thu_muc_retouch=str(a.retouch))
    print(tom_tat(a.folder))
    return 0


if __name__ == "__main__":
    sys.exit(main())
