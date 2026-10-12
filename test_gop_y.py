#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Góp dữ liệu buổi đã sửa tay (12/10) — gop_y.py + may_nhan/may_nhan_gop_y.py.

Mục kiểm (thư mục dữ liệu TẠM, plugin Lightroom GIẢ trả lời request_chup.txt):
    1. ghi_lan_day lưu cấu hình lúc đẩy (trần EV…), lan_day_cuoi đọc lại.
    2. Buổi chỉ 1 ảnh sửa tay -> KHÔNG đóng gói.
    3. Buổi 4 ảnh sửa -> gói có meta (cấu hình, số ảnh sửa, thân máy), số đo, job, bản chụp,
       baseline, ảnh nhỏ <= 384 px KHÔNG EXIF; KHÔNG còn đường dẫn thư mục thật (kể cả có dấu).
    4. Gói giải ra đọc được bằng chính cổng kiem_2ban_quay (nap_do / nap_dap_an / nap_preset).
    5. Gửi lên máy nhận thật (cổng ngẫu nhiên): lưu đúng chỗ + so_nhan.jsonl; hàng đợi trống,
       có biên nhận. Sai khoá -> 403, gói ở lại hàng đợi. Tắt góp dữ liệu -> không gửi.

    python test_gop_y.py
"""
from __future__ import annotations

import gzip
import io
import json
import os
import sys
import tempfile
import threading
import time
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

TAM = Path(tempfile.mkdtemp(prefix="kiem_gop_y_"))
os.environ["AUTOTONE_DATA"] = str(TAM / "data")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "may_nhan"))
import numpy as np            # noqa: E402
from PIL import Image         # noqa: E402

import autotone as at         # noqa: E402
import gop_y                  # noqa: E402
import kiem_2ban_quay as kb   # noqa: E402
import may_nhan_gop_y as mn   # noqa: E402

LOI = []


def ktra(ten, ok, chi=""):
    print(f"  [{'DAT' if ok else 'LOI'}] {ten}  {chi}")
    if not ok:
        LOI.append(ten)


BUOI = TAM / "G" / "Ăn hỏi 2009"           # thư mục CÓ DẤU — đường dẫn phải bị thay hết
BUOI.mkdir(parents=True)
JOBS = TAM / "jobs"
JOBS.mkdir()
TEN = [f"SAY0{8800 + i}" for i in range(6)]


def dung_buoi(so_sua):
    """6 ảnh JPEG (có EXIF), số đo đã lưu, job tool, plugin giả chụp catalog (so_sua ảnh sửa)."""
    items = []
    t0 = datetime(2026, 10, 11, 14, 0, 0)
    for i, t in enumerate(TEN):
        p = BUOI / f"{t}.jpg"
        im = Image.fromarray(np.full((1600, 2400, 3), 120 + i * 10, np.uint8))
        ex = Image.Exif()
        ex[0x010F] = "SONY"
        ex[0x0110] = "ILCE-7M5"
        im.save(p, "JPEG", exif=ex.tobytes())
        items.append({"path": str(p), "sidecar": str(p.with_suffix(".xmp")), "model": "ILCE-7M5",
                      "metered_face_ev": -1.2, "dt": (t0 + timedelta(seconds=i)).isoformat(),
                      "dt_obj": t0 + timedelta(seconds=i), "face_debug": [], "ok": True})
    at.luu_ket_qua_do(BUOI, dict(at.DEFAULTS), [(Path(r["path"]), None) for r in items], items, [])
    job = JOBS / "apply_20261011_140500_An_hoi_2009.done"
    dong = ["path\tExposure2012\tTemperature\tTint\tHighlights2012"]
    for t in TEN:
        dong.append(f"{BUOI / (t + '.jpg')}\t+0.30\t5200\t10\t-20")
    job.write_text("\n".join(dong) + "\n", encoding="utf-8")
    (BUOI / at.BASELINE_NAME).write_text(
        "path\tExposure2012\n" + "".join(f"{BUOI / (t + '.jpg')}\t0.00\n" for t in TEN), encoding="utf-8")
    return so_sua


SUA = [0]


def plugin_gia(dung):
    """Trả lời request_chup.txt như ChupCore.lua: ghi bản chụp vào thư mục dòng 2."""
    while not dung.is_set():
        yc = JOBS / "request_chup.txt"
        if yc.is_file():
            thu_muc, ra = yc.read_text(encoding="utf-8").splitlines()[:2]
            yc.unlink()
            ra = Path(ra)
            ra.mkdir(parents=True, exist_ok=True)
            p = ra / f"_autotone_da_sua_{datetime.now():%Y%m%d_%H%M%S}.tsv"
            dong = ["path\tRating\tsettings"]
            for i, t in enumerate(TEN):
                s = {"Exposure2012": 0.30 - (0.25 if i < SUA[0] else 0.0), "Temperature": 5200,
                     "Tint": 10, "Highlights2012": -20}
                dong.append(f"{Path(thu_muc) / (t + '.jpg')}\t0\t{json.dumps(s)}")
            p.write_text("\n".join(dong) + "\n", encoding="utf-8")
            (JOBS / "chup_xong.txt").write_text(f"{p}\t{len(TEN)}", encoding="utf-8")
        time.sleep(0.1)


def main() -> int:
    dung = threading.Event()
    threading.Thread(target=plugin_gia, args=(dung,), daemon=True).start()
    try:
        # 1
        gop_y.ghi_lan_day(BUOI, dict(at.DEFAULTS, max_ev_up=3.0, che_do_sang="trong"), [1, 2], "apply_x.tsv")
        ld = gop_y.lan_day_cuoi(BUOI)
        ktra("lưu cấu hình lúc đẩy (trần EV 3, trong nhà)", ld.get("cfg", {}).get("max_ev_up") == 3.0
             and ld.get("cfg", {}).get("che_do_sang") == "trong", str(ld.get("cfg", {}).get("max_ev_up")))
        ktra("dữ liệu ở thư mục tạm (bài kiểm) -> không tự báo / đóng gói nền",
             gop_y.ly_do_tat() == "thư mục dữ liệu là thư mục tạm", gop_y.ly_do_tat())
        # 2
        dung_buoi(1)
        SUA[0] = 1
        z = gop_y.dong_goi(BUOI, bao=lambda *_a: None, job_dir=JOBS, cho_chup=20)
        ktra("chỉ 1 ảnh sửa tay -> không đóng gói", z is None)
        # 3
        SUA[0] = 4
        z = gop_y.dong_goi(BUOI, bao=print, job_dir=JOBS, cho_chup=20)
        ktra("4 ảnh sửa tay -> có gói trong hàng đợi", z is not None and z.is_file())
        if z is None:
            raise SystemExit
        with zipfile.ZipFile(z) as zf:
            ten = zf.namelist()
            meta = json.loads(zf.read("meta.json"))
            van_ban = b"".join(zf.read(n) for n in ten if not n.endswith(".jpg"))
            van_ban += gzip.decompress(zf.read(next(n for n in ten if n.startswith("do_"))))
            nho = [n for n in ten if n.startswith("anh_nho/")]
            with Image.open(io.BytesIO(zf.read(nho[0]))) as im:   # zf.open giữ zip mở -> Windows khoá
                khong_exif = len(im.getexif()) == 0
                co = max(im.size)
        ktra("meta: cấu hình lúc đẩy + 4 ảnh sửa + thân máy",
             meta["anh_sua"] == 4 and meta["lan_day"]["cfg"]["max_ev_up"] == 3.0
             and meta["than_may"] == ["ILCE-7M5"], str({k: meta[k] for k in ("anh_sua", "than_may")}))
        ktra("gói đủ phần: số đo, job, bản chụp, baseline, 6 ảnh nhỏ",
             any(n.startswith("do_") for n in ten) and any(n.endswith(".done") for n in ten)
             and any(n.startswith("_autotone_da_sua_") for n in ten) and at.BASELINE_NAME in ten
             and len(nho) == 6, str(sorted(ten)[:6]))
        ktra("ảnh nhỏ <= 384 px và KHÔNG EXIF", co <= 384 and khong_exif, f"{co} px")
        goc = str(BUOI)
        con = [b for b in (goc, goc.replace("\\", "\\\\"), goc.replace("\\", "/"), "Ăn hỏi")
               if b.encode("utf-8") in van_ban]
        ktra("không còn đường dẫn / tên thư mục thật (kể cả có dấu) trong gói", not con, str(con))
        # 4
        giai = TAM / "giai" / meta["buoi"]
        jobs2 = TAM / "giai_jobs"
        jobs2.mkdir(parents=True)
        with zipfile.ZipFile(z) as zf:
            for n in zf.namelist():
                d = (jobs2 if n.endswith(".done") else giai) / n
                d.parent.mkdir(parents=True, exist_ok=True)
                d.write_bytes(zf.read(n))
        goi = kb.nap_do(giai)
        dap = kb.nap_dap_an(giai, meta["buoi"], jobs2)
        pre = kb.nap_preset(giai)
        sua_kb = sum(1 for k, a in dap.items() if not k.startswith("__")
                     and abs(a["user"]["Exposure2012"] - a["tool"]["Exposure2012"]) > 0.005)
        ktra("giải gói -> cổng kiem_2ban_quay đọc được (số đo, đáp án, preset)",
             len(goc and goi.get("items") or []) == 6 and sua_kb == 4 and len(pre) == 6,
             f"items {len(goi.get('items') or [])} · sửa {sua_kb} · preset {len(pre)}")
        # 4b — gói vượt giới hạn Cloudflare (100 MB/yêu cầu) -> đóng lại ảnh nhỏ hơn / bỏ ảnh nhỏ
        cu_td = gop_y.GOI_TOI_DA
        gioi = z.stat().st_size // 2
        gop_y.GOI_TOI_DA = gioi
        z2 = gop_y.dong_goi(BUOI, bao=lambda *_a: None, job_dir=JOBS, cho_chup=20)
        gop_y.GOI_TOI_DA = cu_td
        with zipfile.ZipFile(z2) as zf:
            m2 = json.loads(zf.read("meta.json"))
            nho2 = [n for n in zf.namelist() if n.startswith("anh_nho/")]
        ktra("gói vượt giới hạn -> đóng lại với ảnh nhỏ hơn (hoặc bỏ ảnh nhỏ), vẫn đủ số đo",
             m2["canh_anh_nho"] < 384 and (z2.stat().st_size <= gioi or not nho2)
             and m2["anh_sua"] == 4, f"cạnh {m2['canh_anh_nho']} · {len(nho2)} ảnh nhỏ · {z2.stat().st_size} B")
        z2.unlink()
        # 5
        kho = TAM / "kho"
        cf = dict(mn.MAC_DINH, kho=str(kho))
        may = mn.tao_may(cf, cong=0)
        threading.Thread(target=may.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{may.server_address[1]}"
        bm = gop_y.BI_MAT
        gop_y.BI_MAT = "sai"
        n = gop_y.gui_het(bao=lambda *_a: None, url=url)
        ktra("sai khoá -> máy nhận từ chối (403), gói ở lại hàng đợi",
             n == 0 and z.is_file() and not list(kho.rglob("*.zip")))
        gop_y.BI_MAT = bm
        gop_y.ghi_cau_hinh({"bat": False})
        ktra("tắt góp dữ liệu -> không gửi", gop_y.gui_het(url=url) == 0 and z.is_file())
        gop_y.ghi_cau_hinh({"bat": True})
        n = gop_y.gui_het(bao=print, url=url)
        luu = list(kho.rglob("*.zip"))
        so = (kho / "so_nhan.jsonl").read_text(encoding="utf-8") if (kho / "so_nhan.jsonl").is_file() else ""
        ktra("gửi được: máy nhận lưu <người>/<ngày>/gói.zip + so_nhan.jsonl; hàng đợi trống, có biên nhận",
             n == 1 and len(luu) == 1 and gop_y.ma_nguoi() in str(luu[0]) and '"anh_sua": 4' in so
             and not z.exists() and list((gop_y.thu() / "da_gui").glob("*.json")), str(luu[:1]))
        may.shutdown()
    finally:
        dung.set()
    print("TAT CA DAT" if not LOI else f"{len(LOI)} LOI: {LOI}")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
