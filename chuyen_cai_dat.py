"""Chuyển CÀI ĐẶT sang máy khác — một file .zip (15/10). Không dùng Tk (xem chuyen_cai_dat_ui).

User 15/10: "giờ sẽ cần đóng gói để cho cài đặt trên các máy khác và thợ có thể sử dụng
các thiết bị khác nhau" -> chọn "Chuyển cài đặt sang máy khác".

GÓI = zip: manifest.json (kiểu, phiên bản app, ngày, hệ điều hành, sha256 từng file) +
du_lieu/<tên file trong thư mục dữ liệu app>. CHỈ những thứ trong DANH SÁCH CHO PHÉP:

  mau_da.json        mẫu màu da (bỏ _theo_buoi — đường dẫn buổi của máy cũ)
  gu.json            gu đã học (cả file)
  retouch.json       chỉ muc / che_do / ghi_de / nguon / chat_luong_ra (bỏ máy, luồng, thư mục)
  xuat.json          chỉ chat / va_cham / bo_sao1 / chi_chua_sao / retouch_ra / tu_retouch / preset
  preset_xem.json    uuid / ten / nhom
  luoi_xem.json      mau_mot_luot
  wb_may.json        lệch WB theo máy (cả file)
  retouch_preset/*.json, mo_hinh_lr/<khoá>.json (mẫu .npz: tuỳ chọn kem_mau)

CẤM CỨNG (dù gói có ghi): khoa.json* (bản quyền), may.txt, cache, phan_tich/, cap_nhat/,
jobs, gop_y/, credit/ — danh sách cho phép đã loại, _CAM chặn thêm một lớp.

NHẬP: kiểm kiểu gói, đường dẫn (không .., không tuyệt đối), sha256, dung lượng -> SAO LƯU
nguyên các file sắp đụng vào sao_luu_cai_dat/<giờ>.zip (Khôi phục dùng bản này, file chưa
từng có thì khôi phục = xoá) -> gộp: mẫu da theo tên (trùng thì lấy của gói), gu theo khoá,
JSON lọc khoá chỉ đè khoá cho phép, mô hình ĐẠT thắng CHƯA ĐẠT (cùng ĐẠT: bản mới hơn),
wb_may theo (máy, buổi). Nhập xong nên mở lại app.
"""
from __future__ import annotations

import hashlib
import json
import platform
import re
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

import duong_dan as dd

KIEU = "autotone-cai-dat"
PHIEN_BAN_GOI = 1
DUOI = ".atcaidat.zip"
TOI_DA_TEP = 20 * 1024 * 1024          # byte / file
TOI_DA_GOI = 80 * 1024 * 1024          # byte tổng sau giải nén
THU_MUC_SAO_LUU = "sao_luu_cai_dat"

#  file JSON chỉ chép một số khoá (None = cả file)
KHOA_CHO = {
    "mau_da.json": None,                  # lọc riêng (_loc_mau_da)
    "gu.json": None,
    "retouch.json": ("muc", "che_do", "ghi_de", "nguon", "chat_luong_ra"),
    "xuat.json": ("chat", "va_cham", "bo_sao1", "chi_chua_sao", "retouch_ra", "tu_retouch",
                  "preset"),
    "preset_xem.json": ("uuid", "ten", "nhom"),
    "luoi_xem.json": ("mau_mot_luot",),
    "wb_may.json": None,
}
_THU_MUC = {"retouch_preset": re.compile(r"^[^/\\]+\.json$"),
            "mo_hinh_lr": re.compile(r"^[^/\\]+(?:\.json|_mau\.npz)$")}
_CAM = re.compile(r"(^|/)(khoa\.json.*|may\.txt|phan_tich|cap_nhat|jobs|gop_y|credit|"
                  r"tai_nguyen|xem_.*|anh_.*|mask_da|retouch_anh|trang_thai)(/|$)", re.I)


class LoiGoi(Exception):
    """Gói cài đặt hỏng / không phải gói của app / bị sửa."""


def _goc() -> Path:
    return dd.goc_du_lieu()


def _hop_le(rel: str) -> bool:
    """rel (dạng a/b, tính từ thư mục dữ liệu) có thuộc danh sách cho phép không."""
    if not rel or "\\" in rel or rel.startswith("/") or ":" in rel:
        return False
    pp = PurePosixPath(rel)
    if any(x in ("", ".", "..") for x in pp.parts) or _CAM.search(rel):
        return False
    if len(pp.parts) == 1:
        return rel in KHOA_CHO
    if len(pp.parts) == 2 and pp.parts[0] in _THU_MUC:
        if pp.parts[0] == "mo_hinh_lr" and (pp.stem.endswith("_st") or pp.stem.startswith("du_doan")
                                            or pp.stem.startswith("lich_su")):
            return False
        return bool(_THU_MUC[pp.parts[0]].match(pp.parts[1]))
    return False


def _doc_json(p: Path):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _loc(rel: str, d):
    """Nội dung JSON của file rel CHỈ còn phần được mang đi (None = bỏ file)."""
    if not isinstance(d, dict):
        return None
    if rel == "mau_da.json":
        return {k: v for k, v in d.items() if k != "_theo_buoi"}
    khoa = KHOA_CHO.get(rel)
    if khoa is None:
        return d
    out = {k: d[k] for k in khoa if k in d}
    return out or None


def ds_se_xuat(kem_mau: bool = False) -> list:
    """[(rel, đường file)] sẽ vào gói — chỉ file đang có."""
    g = _goc()
    out = []
    for rel in KHOA_CHO:
        if (g / rel).is_file():
            out.append((rel, g / rel))
    for tm in _THU_MUC:
        d = g / tm
        if not d.is_dir():
            continue
        for f in sorted(d.iterdir()):
            rel = f"{tm}/{f.name}"
            if not f.is_file() or not _hop_le(rel):
                continue
            if f.suffix == ".npz" and not kem_mau:
                continue
            out.append((rel, f))
    return out


def xuat(dich: Path, kem_mau: bool = False) -> dict:
    """Ghi gói vào dich. -> {"duong", "tep": [rel], "byte"}."""
    import cap_nhat
    dich = Path(dich)
    tep: dict = {}
    noi_dung: dict = {}
    for rel, f in ds_se_xuat(kem_mau):
        if f.suffix == ".json":
            d = _loc(rel, _doc_json(f))
            if d is None:
                continue
            b = json.dumps(d, ensure_ascii=False, indent=1).encode("utf-8")
        else:
            try:
                b = f.read_bytes()
            except OSError:
                continue
        if len(b) > TOI_DA_TEP:
            continue
        noi_dung[rel] = b
        tep[rel] = hashlib.sha256(b).hexdigest()
    mf = {"kieu": KIEU, "phien_ban_goi": PHIEN_BAN_GOI,
          "app": getattr(cap_nhat, "PHIEN_BAN_APP", ""),
          "ngay": datetime.now().isoformat(timespec="seconds"),
          "he_dieu_hanh": f"{platform.system()} {platform.release()}", "tep": tep}
    dich.parent.mkdir(parents=True, exist_ok=True)
    tam = dich.with_name(dich.name + ".tmp")
    with zipfile.ZipFile(tam, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(mf, ensure_ascii=False, indent=1))
        for rel, b in noi_dung.items():
            z.writestr("du_lieu/" + rel, b)
    tam.replace(dich)
    return {"duong": str(dich), "tep": sorted(noi_dung), "byte": dich.stat().st_size}


def doc_goi(goi: Path) -> dict:
    """Kiểm + đọc gói -> {"manifest", "tep": {rel: bytes}}. Sai thì LoiGoi."""
    try:
        z = zipfile.ZipFile(Path(goi))
    except (OSError, zipfile.BadZipFile) as ex:
        raise LoiGoi(f"không mở được file: {ex}") from ex
    with z:
        try:
            mf = json.loads(z.read("manifest.json").decode("utf-8"))
        except (KeyError, ValueError, UnicodeDecodeError) as ex:
            raise LoiGoi("không phải gói cài đặt của app (thiếu manifest)") from ex
        if not isinstance(mf, dict) or mf.get("kieu") != KIEU:
            raise LoiGoi("không phải gói cài đặt của app")
        if int(mf.get("phien_ban_goi") or 0) > PHIEN_BAN_GOI:
            raise LoiGoi("gói tạo từ bản app mới hơn — cập nhật app trước")
        ten_sha = mf.get("tep") or {}
        if not isinstance(ten_sha, dict):
            raise LoiGoi("manifest hỏng")
        tong = 0
        out = {}
        for info in z.infolist():
            ten = info.filename
            if ten == "manifest.json" or ten.endswith("/"):
                continue
            if not ten.startswith("du_lieu/"):
                raise LoiGoi(f"file lạ trong gói: {ten}")
            rel = ten[len("du_lieu/"):]
            if not _hop_le(rel):
                raise LoiGoi(f"file không được phép trong gói: {rel}")
            if rel not in ten_sha:
                raise LoiGoi(f"file không có trong manifest: {rel}")
            if info.file_size > TOI_DA_TEP:
                raise LoiGoi(f"file quá lớn: {rel}")
            tong += info.file_size
            if tong > TOI_DA_GOI:
                raise LoiGoi("gói quá lớn")
            b = z.read(info)
            if hashlib.sha256(b).hexdigest() != ten_sha[rel]:
                raise LoiGoi(f"file bị sửa / hỏng (sha256 sai): {rel}")
            out[rel] = b
        thieu = sorted(set(ten_sha) - set(out))
        if thieu:
            raise LoiGoi(f"gói thiếu file: {', '.join(thieu[:3])}")
    return {"manifest": mf, "tep": out}


# ------------------------------------------------------------------ gộp
def _gop_mo_hinh(cu, moi):
    """Mô hình: ĐẠT thắng CHƯA ĐẠT; cùng ĐẠT / cùng chưa: bản mới hơn (thong_tin.ngay)."""
    if not isinstance(cu, dict):
        return moi
    if not isinstance(moi, dict):
        return cu
    dc, dm = bool(cu.get("dat")), bool(moi.get("dat"))
    if dc != dm:
        return moi if dm else cu
    nc = str((cu.get("thong_tin") or {}).get("ngay") or "")
    nm = str((moi.get("thong_tin") or {}).get("ngay") or "")
    return moi if nm >= nc else cu


def _gop_wb_may(cu, moi):
    if not isinstance(cu, dict) or not isinstance(cu.get("may"), dict):
        return moi
    out = {"may": {k: list(v or []) for k, v in cu["may"].items()}}
    for model, ds in dict((moi or {}).get("may") or {}).items():
        co = {x.get("buoi"): x for x in out["may"].get(model, [])}
        for x in ds or []:
            co[x.get("buoi")] = x
        out["may"][model] = sorted(co.values(), key=lambda x: str(x.get("luc", "")))[-20:]
    return out


def _gop(rel: str, cu, moi):
    if rel.startswith("mo_hinh_lr/") and rel.endswith(".json"):
        return _gop_mo_hinh(cu, moi)
    if rel == "wb_may.json":
        return _gop_wb_may(cu, moi)
    if rel == "mau_da.json":
        out = dict(cu) if isinstance(cu, dict) else {}
        out.update({k: v for k, v in dict(moi or {}).items() if k != "_theo_buoi"})
        return out
    if isinstance(cu, dict) and isinstance(moi, dict):
        khoa = KHOA_CHO.get(rel)
        out = dict(cu)
        out.update({k: v for k, v in moi.items() if khoa is None or k in khoa})
        return out
    return moi


def ds_sao_luu() -> list:
    """Bản sao lưu trước các lần nhập, mới nhất trước."""
    d = _goc() / THU_MUC_SAO_LUU
    return sorted(d.glob("*.zip"), key=lambda f: (f.stat().st_mtime, f.name), reverse=True) if d.is_dir() else []


def _sao_luu(ds_rel: list) -> Path:
    g = _goc()
    d = g / THU_MUC_SAO_LUU
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{datetime.now():%Y%m%d_%H%M%S}.zip"
    i = 1
    while f.exists():
        f = d / f"{datetime.now():%Y%m%d_%H%M%S}_{i}.zip"
        i += 1
    chua_co = []
    with zipfile.ZipFile(f, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in ds_rel:
            p = g / rel
            if p.is_file():
                z.write(p, "du_lieu/" + rel)
            else:
                chua_co.append(rel)
        z.writestr("sao_luu.json", json.dumps({"kieu": KIEU + "-sao-luu", "chua_co": chua_co,
                                               "ngay": datetime.now().isoformat(timespec="seconds")},
                                              ensure_ascii=False))
    return f


def nhap(goi: Path) -> dict:
    """Nhập gói -> {"sao_luu", "doi": [rel], "manifest"}. Sai gói thì LoiGoi (chưa đụng gì)."""
    g = doc_goi(goi)
    g_dl = _goc()
    ds = sorted(g["tep"])
    sl = _sao_luu(ds)
    doi = []
    for rel in ds:
        b = g["tep"][rel]
        dich = g_dl / rel
        if not _hop_le(rel):                   # doc_goi đã kiểm — thêm một lớp
            continue
        if rel.endswith(".json"):
            try:
                moi = json.loads(b.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                continue
            cu = _doc_json(dich) if dich.is_file() else None
            ra = _gop(rel, cu, moi)
            b = json.dumps(ra, ensure_ascii=False, indent=1).encode("utf-8")
        dich.parent.mkdir(parents=True, exist_ok=True)
        if rel.endswith(".json"):
            dd.ghi_ben(dich, b.decode("utf-8"))
        else:
            dich.write_bytes(b)
        doi.append(rel)
    return {"sao_luu": str(sl), "doi": doi, "manifest": g["manifest"]}


def khoi_phuc(sao_luu: Path | None = None) -> dict:
    """Trả các file về như trước lần nhập (bản sao lưu mới nhất nếu không chỉ định).
    -> {"sao_luu", "tra": [rel], "xoa": [rel]}."""
    sl = Path(sao_luu) if sao_luu else (ds_sao_luu() or [None])[0]
    if sl is None or not Path(sl).is_file():
        raise LoiGoi("chưa có bản sao lưu nào (chưa nhập cài đặt lần nào)")
    g = _goc()
    tra, xoa = [], []
    with zipfile.ZipFile(sl) as z:
        try:
            tt = json.loads(z.read("sao_luu.json").decode("utf-8"))
        except (KeyError, ValueError) as ex:
            raise LoiGoi("bản sao lưu hỏng") from ex
        for info in z.infolist():
            ten = info.filename
            if not ten.startswith("du_lieu/"):
                continue
            rel = ten[len("du_lieu/"):]
            if not _hop_le(rel):
                continue
            b = z.read(info)
            (g / rel).parent.mkdir(parents=True, exist_ok=True)
            (g / rel).write_bytes(b)
            tra.append(rel)
        for rel in tt.get("chua_co") or []:
            if _hop_le(str(rel)) and (g / rel).is_file():
                (g / rel).unlink()
                xoa.append(rel)
    return {"sao_luu": str(sl), "tra": tra, "xoa": xoa}


def tom_tat(rel_ds: list) -> str:
    """Danh sách file -> câu ngắn cho người dùng."""
    ten = {"mau_da.json": "mẫu màu da", "gu.json": "gu đã học", "retouch.json": "mức retouch",
           "xuat.json": "thiết lập xuất", "preset_xem.json": "preset xem",
           "luoi_xem.json": "chế độ một lượt", "wb_may.json": "lệch WB theo máy"}
    out = [ten[r] for r in rel_ds if r in ten]
    n_mh = sum(1 for r in rel_ds if r.startswith("mo_hinh_lr/") and r.endswith(".json"))
    n_rp = sum(1 for r in rel_ds if r.startswith("retouch_preset/"))
    if n_mh:
        out.append(f"{n_mh} mô hình màu Lightroom")
    if n_rp:
        out.append(f"{n_rp} preset retouch")
    return ", ".join(out) or "không có gì"

