# -*- coding: utf-8 -*-
"""xem_lr.py — Lưới / ảnh lớn của tool hiện PREVIEW LIGHTROOM sau khi áp (14/10).

User 14/10 (sau khi nghe: preview của tool là ảnh nhúng trong RAW — màu máy ảnh, lệch da
so với Lightroom hue ~3.8° / độ đậm ~15% dù khớp Exposure / WB tối ưu): "oke làm luôn
hiện preview" — sau khi Xử lý ảnh áp xong, ảnh thấy trên tool phải GIỐNG Lightroom.

Luồng: Xử lý ảnh xong -> yeu_cau() nhờ plugin (DuyetCore.runRequestXem) lấy preview
Lightroom (requestJpegThumbnail, CHỈ preview — không bao giờ Export bù) cho các ảnh vừa
áp + XUẤT THẬT vài ảnh để soát preview còn tươi (curve_da.so_tuoi). Tươi thì nhan()
cất từng ảnh vào <dữ liệu>/xem_lr/ kèm thông số LÚC ÁP (Exposure, K, Tint); lệch thì bỏ
cả lượt — lưới giữ ảnh của tool.

    anh(p)       file preview Lightroom của ảnh p (None nếu chưa có)
    ap_cua(p)    (exposure, temp, tint) lúc áp — mô phỏng chỉ phần ĐỔI sau đó
    yeu_cau(...) / tien_do() / bang_anh(ten) / nhan(...)
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import time
from pathlib import Path

import duong_dan as dd

TEN_KHO = "xem_lr"
TEN_CHI_MUC = "chi_muc.json"
TRAN = 20000                      # quá chừng này ảnh trong kho thì bỏ 1/4 ảnh cũ nhất

TEN_YEU_CAU = "request_xem_lr.txt"
TEN_TIEN_DO = "xem_lr_tiendo.txt"
TEN_BANG = "xem_lr_anh.tsv"
TEN_KIEM = "xem_lr_kiem.tsv"
TEN_CO_DUNG = "request_xem_lr_dung.txt"
KHA_NANG = "xem1"

_KHOA = threading.Lock()
_CM: dict | None = None           # chỉ mục trong bộ nhớ (đọc một lần)


def _khoa(p) -> str:
    import autotone as at
    return at.khoa_duong_dan(str(p))


def kho() -> Path:
    return dd.goc_du_lieu() / TEN_KHO


def _doc_cm() -> dict:
    global _CM
    if _CM is None:
        try:
            _CM = json.loads((kho() / TEN_CHI_MUC).read_text(encoding="utf-8"))
            if not isinstance(_CM, dict):
                _CM = {}
        except (OSError, ValueError):
            _CM = {}
    return _CM


def _ghi_cm() -> None:
    try:
        kho().mkdir(parents=True, exist_ok=True)
        dd.ghi_ben(kho() / TEN_CHI_MUC, json.dumps(_CM or {}, ensure_ascii=False))
    except OSError:
        pass


def anh(p) -> Path | None:
    """File preview Lightroom của ảnh p, None nếu chưa có / file đã mất."""
    with _KHOA:
        m = _doc_cm().get(_khoa(p))
    if not m:
        return None
    f = kho() / m["f"]
    return f if f.is_file() else None


def ap_cua(p) -> tuple | None:
    """(exposure, temp, tint) lúc áp của ảnh có preview Lightroom."""
    with _KHOA:
        m = _doc_cm().get(_khoa(p))
    if not m or anh(p) is None:
        return None
    a = m.get("ap")
    return tuple(a) if isinstance(a, (list, tuple)) and len(a) == 3 else None


def nhan(cap: list, ap_map: dict) -> list:
    """Cất các preview (đường dẫn Lightroom, file jpg) vào kho; ap_map {khoá: (exp, K, tint)}.
    Trả về danh sách đường dẫn đã nhận."""
    d = kho()
    d.mkdir(parents=True, exist_ok=True)
    da = []
    with _KHOA:
        cm = _doc_cm()
        for p, jpg in cap:
            k = _khoa(p)
            ten = hashlib.sha1(k.encode("utf-8", "surrogatepass")).hexdigest()[:20] + \
                f"_{int(time.time() * 1000) % 100000}.jpg"
            try:
                shutil.copyfile(jpg, d / ten)
            except OSError:
                continue
            cu = cm.get(k)
            if cu and cu.get("f") != ten:
                try:
                    (d / cu["f"]).unlink()
                except OSError:
                    pass
            ap = ap_map.get(k)
            cm[k] = {"f": ten, "ap": list(ap) if ap else None, "luc": time.time()}
            da.append(p)
        if len(cm) > TRAN:
            bo = sorted(cm, key=lambda x: cm[x].get("luc") or 0)[:len(cm) // 4]
            for x in bo:
                try:
                    (d / cm[x]["f"]).unlink()
                except OSError:
                    pass
                cm.pop(x, None)
        _ghi_cm()
    return da


def quen(paths) -> None:
    """Bỏ preview của các ảnh (vd. áp lại mà Lightroom không trả preview mới)."""
    with _KHOA:
        cm = _doc_cm()
        for p in paths:
            m = cm.pop(_khoa(p), None)
            if m:
                try:
                    (kho() / m["f"]).unlink()
                except OSError:
                    pass
        _ghi_cm()


# ── yêu cầu plugin ───────────────────────────────────────────────────────────
def yeu_cau(folder, paths: list, ma: str, kiem: list | None = None, canh: int = 1600,
            job_dir: Path | None = None) -> Path:
    """Nhờ plugin lấy preview Lightroom cho ĐÚNG các ảnh (CHỈ preview, chi_preview=1)."""
    import autotone as at
    d = Path(job_dir or at.LR_JOB_DIR)
    d.mkdir(parents=True, exist_ok=True)
    for ten in (TEN_TIEN_DO, TEN_BANG, TEN_KIEM, TEN_CO_DUNG):
        try:
            (d / ten).unlink()
        except OSError:
            pass
    dest = dd.goc_du_lieu() / "xem_lr_tam" / ma
    dest.mkdir(parents=True, exist_ok=True)
    body = [str(Path(str(folder))), f"dest={dest}", f"canh={int(canh)}", "chat=85",
            "bo_sao=0", f"ma={ma}", "nguon=preview", "chi_preview=1"]
    body += [f"anh={p}" for p in paths]
    body += [f"kiem_anh={p}" for p in (kiem or [])]
    f = d / TEN_YEU_CAU
    tmp = d / (TEN_YEU_CAU + ".part")
    tmp.write_text("\n".join(body) + "\n", encoding="utf-8")
    os.replace(tmp, f)
    return f


def dang_cho(job_dir: Path | None = None) -> bool:
    import autotone as at
    return (Path(job_dir or at.LR_JOB_DIR) / TEN_YEU_CAU).exists()


def rut_yeu_cau(job_dir: Path | None = None) -> None:
    import autotone as at
    try:
        (Path(job_dir or at.LR_JOB_DIR) / TEN_YEU_CAU).unlink()
    except OSError:
        pass


def xin_dung(job_dir: Path | None = None) -> None:
    import autotone as at
    d = Path(job_dir or at.LR_JOB_DIR)
    d.mkdir(parents=True, exist_ok=True)
    (d / TEN_CO_DUNG).write_text("dung\n", encoding="utf-8")


def tien_do(job_dir: Path | None = None) -> dict:
    import autotone as at
    out: dict = {}
    try:
        txt = (Path(job_dir or at.LR_JOB_DIR) / TEN_TIEN_DO).read_text(encoding="utf-8",
                                                                      errors="replace")
    except OSError:
        return {}
    for dong in txt.splitlines():
        k, _, v = dong.partition("=")
        if k:
            out[k.strip()] = v.strip()
    for k in ("xong", "tong", "loi"):
        try:
            out[k] = int(out[k])
        except (KeyError, ValueError):
            pass
    return out


def bang_anh(ten: str = TEN_BANG, job_dir: Path | None = None) -> list[tuple[str, str]]:
    import autotone as at
    try:
        lines = (Path(job_dir or at.LR_JOB_DIR) / ten).read_text(
            encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return [(v[0], v[1]) for v in (ln.split("\t") for ln in lines[1:])
            if len(v) >= 2 and v[0] and v[1]]


def don_tam(ma: str | None = None) -> None:
    """Xoá thư mục tạm của lượt (ảnh đã cất vào kho)."""
    goc = dd.goc_du_lieu() / "xem_lr_tam"
    shutil.rmtree(goc / ma if ma else goc, ignore_errors=True)
