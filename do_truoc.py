# -*- coding: utf-8 -*-
"""do_truoc.py — ĐO DA trên preview Lightroom của trạng thái HIỆN TẠI, TRƯỚC khi áp (14/10).

Chuỗi màu da MỘT LƯỢT (user 14/10: "Việc xử lý 1000 ảnh theo cách hiện tại thì thời gian
phải tốn 15 phút … Với mỗi 1 ảnh cần lấy ra được vùng da mặt và pixel vùng da đó để can
thiệp xử lý ánh sáng và màu sắc cho giống với màu da đích"): đo da / vùng trắng / khung
trên ảnh Lightroom ĐANG dựng, mô hình học (mo_hinh_lr) đoán ảnh sau khi đổi thông số, áp
MỘT lần — không còn lượt 2 dựng lại cả buổi sau khi áp.

Nguồn preview, theo thứ tự:
  1. CACHE của Lightroom (doc_cache_lr): preview còn mới (digest khớp) ≥ 1024 px — 13 ms/ảnh,
     Lightroom không phải làm gì.
  2. Còn thiếu (chưa từng xem / preview cũ / chỉ có mức nhỏ): nhờ plugin
     (DuyetCore.runRequestTruoc, khả năng truoc1) lấy preview — Lightroom dựng ~0.5 s/ảnh.
Đo song song (curve_da.BoDo) ngay khi ảnh tới. Kết quả gắn r["lr_truoc"]:
  do_anh() (mẫu điểm ảnh ở miền curve, mặt nạ da...) + "nguon" (cache / plugin) + "st"
  (thông số catalog ĐÚNG lúc preview được dựng — bảng Lua của Adobe_imageDevelopSettings).
"""
from __future__ import annotations

import os
import shutil
import time
from datetime import datetime
from pathlib import Path

import numpy as np

import autotone as at

TEN_YEU_CAU = "request_do_truoc.txt"
TEN_TIEN_DO = "do_truoc_tiendo.txt"
TEN_BANG = "do_truoc_anh.tsv"
TEN_CO_DUNG = "request_do_truoc_dung.txt"
KHA_NANG = "truoc1"
CANH = 1024
#: 14/10: preview 1024 làm mặt người trong ảnh toàn thân còn ~46 px (< 48 px mô hình phân
#: vùng cần) -> mặt nạ dự phòng; cache có mức ≥ 1600 thì dùng (do_anh thu về 1600)
UU_TIEN = 1600
#: điểm ảnh giữ lại mỗi tập (da / trung tính / khung) — kết quả cả buổi nằm trong RAM tới
#: lúc tính kế hoạch: 1.000 ảnh × 3 tập × 6000 điểm float32 ~ 200 MB
TOI_DA = 6000


def can_do(items: list) -> list:
    """Ảnh cần đo trước: có mặt, không đen trắng, không 1★, có trong catalog."""
    return [r for r in items if r.get("meter_boxes") and not r.get("bw") and r.get("ok", True)
            and int(r.get("rating") or 0) != 1 and not r.get("ngoai_xuat")]


def mau_loat(ds: list, cfg: dict, n: int = 2) -> list:
    """Tối đa `n` ảnh mỗi LOẠT chụp (rải đều trong loạt) — đủ cho chuỗi một lượt.

    #[[ 14/10 đo thật 2709 sau khi áp: trong một loạt da lệch nhau ~3% độ đậm / 0.004 L,
    #   giữa các loạt ~27% / 0.044 — mọi quyết định của chuỗi (Tone theo cảnh, Luminance /
    #   HSL / Curve theo loạt) cần số đo của LOẠT, không cần từng tấm. Đo đủ 1.056 ảnh mất
    #   ~4 phút (mô hình tách da ~0.5 s/ảnh). Tấm không đo theo loạt của nó. ]]"""
    #[[ 15/10: thêm mọi tấm mà mặt đo lệch trung vị CỤM CÙNG KHUNG (autotone.anh_lech_sang_cum
    #   — flash không kịp hồi, ra / vào bóng râm…): chuỗi một lượt cân sáng chúng trên da đo
    #   Lightroom (mau_mot_luot.can_sang_cum); 2709: ~140 tấm. ]]
    if n <= 0:
        return list(ds)
    out = []
    for g in at.nhom_loat(list(ds), cfg) if ds else []:
        if len(g) <= n:
            out += g
        else:
            out += [g[int(i)] for i in np.linspace(0, len(g) - 1, n).round()]
    co = {id(r) for r in out}
    them = at.anh_lech_sang_cum(list(ds), cfg) if ds else set()
    out += [r for r in ds if id(r) in them and id(r) not in co]
    return out


def _khoa(r) -> str:
    return at.khoa_duong_dan(r.get("lr_path") or r["path"])


def yeu_cau(folder, paths: list, ma: str, canh: int = CANH, job_dir: Path | None = None) -> Path:
    """Nhờ plugin lấy preview Lightroom (CHỈ preview) cho các ảnh thiếu trong cache."""
    import duong_dan as dd
    d = Path(job_dir or at.LR_JOB_DIR)
    d.mkdir(parents=True, exist_ok=True)
    for ten in (TEN_TIEN_DO, TEN_BANG, TEN_CO_DUNG):
        try:
            (d / ten).unlink()
        except OSError:
            pass
    dest = dd.goc_du_lieu() / "do_truoc_tam" / ma
    dest.mkdir(parents=True, exist_ok=True)
    body = [str(Path(str(folder))), f"dest={dest}", f"canh={int(canh)}", "chat=85", "bo_sao=0",
            f"ma={ma}", "nguon=preview", "chi_preview=1"] + [f"anh={p}" for p in paths]
    f = d / TEN_YEU_CAU
    tmp = d / (TEN_YEU_CAU + ".part")
    tmp.write_text("\n".join(body) + "\n", encoding="utf-8")
    os.replace(tmp, f)
    return f


def tien_do(job_dir: Path | None = None) -> dict:
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


def bang_anh(job_dir: Path | None = None) -> list:
    try:
        lines = (Path(job_dir or at.LR_JOB_DIR) / TEN_BANG).read_text(
            encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return [(v[0], v[1]) for v in (ln.split("\t") for ln in lines[1:]) if len(v) >= 2 and v[0] and v[1]]


def xin_dung(job_dir: Path | None = None) -> None:
    d = Path(job_dir or at.LR_JOB_DIR)
    d.mkdir(parents=True, exist_ok=True)
    (d / TEN_CO_DUNG).write_text("dung\n", encoding="utf-8")


def rut_yeu_cau(job_dir: Path | None = None) -> None:
    try:
        (Path(job_dir or at.LR_JOB_DIR) / TEN_YEU_CAU).unlink()
    except OSError:
        pass


def chay(folder, items: list, cfg: dict, huy=None, bao=None, job_dir: Path | None = None,
         catalog=None, cho_nhan: float = 60.0, cho_toi_da: float = 1800.0) -> dict:
    """Đo trước cho cả buổi (CHẶN — chạy ở luồng nền). huy() -> True thì dừng; bao(xong,
    tong, chu) báo tiến độ. Gắn r["lr_truoc"]; trả tóm tắt
    {"tong", "cache", "plugin", "do", "loi", "khong_co", "giay", "ly_do"}."""
    import curve_da
    import doc_cache_lr as dc
    t0 = time.monotonic()
    huy = huy or (lambda: False)
    #  15/10: khung đo da = mặt CHỦ THỂ CHÍNH (gan_chu_the) — như plan() sẽ dùng
    try:
        at.gan_chu_the(items, cfg)
    except Exception:                                        # noqa: BLE001
        pass
    ds = can_do(items)
    if cfg.get("mot_luot_do_moi_loat", 2):
        ds = mau_loat(ds, cfg, int(cfg.get("mot_luot_do_moi_loat", 2)))
    theo = {_khoa(r): r for r in ds}
    for r in items:
        r.pop("lr_truoc", None)
    kq = {"tong": len(ds), "cache": 0, "plugin": 0, "do": 0, "loi": 0, "khong_co": 0,
          "giay": 0.0, "ly_do": ""}
    if not ds:
        return kq
    #  1. thông số + preview còn mới trong cache của Lightroom
    if catalog is None:
        import catalog_lr
        catalog = catalog_lr.duong_catalog()
    anh = {}
    if catalog is not None:
        con = dc.mo_catalog(catalog)
        if con is not None:
            try:
                anh = dc.anh_buoi(con, folder, gom_con=True)
            finally:
                con.close()
    pv = dc.preview_moi(catalog, {k: anh[k] for k in theo if k in anh}, CANH, UU_TIEN) if anh else {}
    cfg_do = dict(cfg, _toi_da=TOI_DA)
    #  máy rảnh (Lightroom chưa phải dựng gì) -> nhiều tiến trình hơn lượt 2
    n = max(1, min(8, (os.cpu_count() or 4) // 3))
    bo = curve_da.BoDo(cfg_do, n=at.safe_jobs(n) if not os.environ.get("AUTOTONE_CURVE_THO") else None)
    meta: dict = {}
    for k, r in theo.items():
        if k in pv:
            a = anh[k]
            meta[k] = {"nguon": "cache", "digest": a.get("digest"),
                       "st": dc.dong_xuat(dc.thong_so(a.get("text")))}
            bo.gui(k, r, pv[k]["tep"], pv[k]["xoay"])
    kq["cache"] = len(meta)
    ket: dict = {}

    def thu():
        for k, v in bo.lay():
            ket[k] = v
        if bao:
            bao(len(ket), len(ds), f"đo da trên preview Lightroom {len(ket)}/{len(ds)}")
    #  2. ảnh thiếu: nhờ plugin
    thieu = [r for k, r in theo.items() if k not in pv]
    ma = ""
    td: dict = {}
    if thieu and KHA_NANG in at.plugin_kha_nang(job_dir) and not huy():
        ma = datetime.now().strftime("%Y%m%d_%H%M%S") + "t"
        yeu_cau(folder, [r.get("lr_path") or r["path"] for r in thieu], ma, canh=UU_TIEN,
                job_dir=job_dir)
        t_gui = time.monotonic()
        da = set()
        while not huy():
            thu()
            td = tien_do(job_dir)
            if td.get("ma") != ma:
                if time.monotonic() - t_gui > cho_nhan:
                    rut_yeu_cau(job_dir)
                    kq["ly_do"] = "Lightroom không nhận yêu cầu preview"
                    break
                time.sleep(0.3)
                continue
            for p, j in bang_anh(job_dir):
                k = at.khoa_duong_dan(p)
                if p in da or k not in theo:
                    continue
                da.add(p)
                a = anh.get(k) or {}
                meta[k] = {"nguon": "plugin", "digest": a.get("digest"),
                           "st": dc.dong_xuat(dc.thong_so(a.get("text"))) if a.get("text") else None}
                bo.gui(k, theo[k], j)
            if td.get("trang_thai") in ("xong", "dung", "loi"):
                if td.get("trang_thai") == "loi" and not da:
                    kq["ly_do"] = td.get("thong_bao") or "plugin báo lỗi"
                break
            if time.monotonic() - t_gui > cho_toi_da:
                xin_dung(job_dir)
                kq["ly_do"] = "quá giờ chờ Lightroom dựng preview"
                break
            time.sleep(0.3)
        if huy():
            if td.get("ma") == ma:
                xin_dung(job_dir)
            else:
                rut_yeu_cau(job_dir)
    elif thieu and not huy() and not kq["ly_do"]:
        kq["ly_do"] = "plugin chưa có khả năng truoc1 — ảnh thiếu preview không đo trước"
    elif thieu and huy():
        kq["ly_do"] = "đã dừng"
    #  3. đợi đo xong
    while bo.con() and not huy():
        thu()
        time.sleep(0.1)
    thu()
    bo.dong(huy=huy())
    if ma:
        import duong_dan as dd
        shutil.rmtree(dd.goc_du_lieu() / "do_truoc_tam" / ma, ignore_errors=True)
    for k, v in ket.items():
        r = theo.get(k)
        if r is None:
            continue
        if not v.get("ok"):
            kq["loi"] += 1
            continue
        r["lr_truoc"] = dict(v, **meta.get(k, {}))
        kq["do"] += 1
        kq["plugin"] += int(meta.get(k, {}).get("nguon") == "plugin")
    kq["khong_co"] = len(ds) - kq["do"] - kq["loi"]
    kq["giay"] = round(time.monotonic() - t0, 1)
    return kq
