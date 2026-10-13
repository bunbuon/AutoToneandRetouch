#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kiem_raw_that.py — chẩn đoán MỘT thư mục RAW thật trên máy người dùng (13/10).

VÌ SAO CÓ
    User 13/10: bộ Canon CR3 "load preview không đúng định dạng — cùng cảnh, cùng thông số
    mà bức sáng bức tối". Bản sửa đọc CR3 / CRW (xem CLAUDE.md "Định dạng RAW") kiểm trên
    32 file mẫu, KHÔNG phải trên bộ ảnh của user (phiên Claude chạy trên máy chủ, không với
    tới ổ G:). Script này chạy TRÊN MÁY user, gọi đúng hàm thật của app, in ra một báo cáo
    gửi lại được:
      1. từng file đọc được gì: máy, hướng, ISO, tốc, khẩu, giờ — thiếu trường nào là lộ;
      2. đo bằng chính analyze(): ảnh xem trước đứng / nằm, có thấy mặt không;
      3. plan() thật (bản xuất catalog của đúng thư mục nếu có, cấu hình lần đẩy gần nhất
         nếu có): ΔEV từng tấm, cảnh, loạt (chia_loat);
      4. các cặp ảnh LIỀN NHAU cùng máy + cùng khẩu / tốc / ISO mà ΔEV lệch > 0.30 — đúng
         bệnh user tả — kèm số để xem vì sao chúng không vào cùng một loạt;
      5. tờ ảnh nhỏ (anh_nho, như lưới của app) để soát chiều xoay bằng mắt.

    Không ghi gì vào thư mục ảnh, không đụng Lightroom, không ghi job.

Dùng:  python kiem_raw_that.py "G:\\TestThacCao\\test" [--con] [--ra bao_cao.txt] [--luoi luoi.jpg]
       (KIEM_RAW_THAT.bat làm sẵn việc này)
"""
from __future__ import annotations

import argparse
import multiprocessing
import os
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

LECH_EV = 0.30          # cặp liền nhau lệch hơn mức này thì liệt kê (ngưỡng "dời" của các cổng)
PHIEN = "v4 14/10 (4b: A = Canon chuyển dần, A0 = công tắc cũ)"   # in ở đầu báo cáo: biết bản nào đã chạy


def _so(v):
    import autotone as at
    return at._rat(v) if isinstance(v, tuple) else at._so(v)              # noqa: SLF001


def _toc(t) -> str:
    t = _so(t)
    if not t:
        return "-"
    return f"1/{round(1 / t)}" if t < 1 else f"{t:g}s"


def _f(v, mau="{:+.2f}") -> str:
    try:
        return mau.format(float(v))
    except (TypeError, ValueError):
        return "-"


def doc_cfg(folder: Path) -> tuple[dict, str]:
    """DEFAULTS + cấu hình lần đẩy gần nhất của buổi này (nếu app đã lưu). Bỏ lọc
    'người sửa' để thấy số tool tính cho MỌI ảnh (như kiem_gu)."""
    import autotone as at
    cfg = dict(at.DEFAULTS)
    nguon = "mặc định (chưa có lần đẩy nào lưu cấu hình cho buổi này)"
    try:
        import gop_y
        ld = gop_y.lan_day_cuoi(folder)
        if ld.get("cfg"):
            cfg.update(ld["cfg"])
            nguon = f"lần đẩy {ld.get('khi', '?')} (bản {ld.get('phien_ban', '?')})"
    except Exception as ex:                                  # noqa: BLE001
        nguon += f" — không đọc được lần đẩy: {ex}"
    cfg.update(source="catalog", bo_qua_nguoi_sua=False)
    return cfg, nguon


def cap_lech(items: list) -> list:
    """Cặp ảnh LIỀN NHAU (theo giờ, trong từng máy) cùng khẩu / tốc / ISO mà ΔEV lệch > LECH_EV."""
    ds = sorted(items, key=lambda r: (str(r.get("model") or ""), r["dt_obj"]))
    cap = []
    for x, y in zip(ds, ds[1:]):
        if str(x.get("model")) != str(y.get("model")):
            continue
        cung = all(_so(x.get(k)) == _so(y.get(k)) and _so(x.get(k)) is not None
                   for k in ("fnumber", "exposure_time", "iso"))
        if not cung or x.get("delta_ev") is None or y.get("delta_ev") is None:
            continue
        lech = abs(float(x["delta_ev"]) - float(y["delta_ev"]))
        if lech > LECH_EV:
            cap.append((lech, x, y))
    return cap


def to_mat(ds: list, dest: Path, so_a: dict, so_c: dict, toi_da: int = 40) -> int:
    """Tờ ảnh CẬN MẶT: khung mặt đem đo, điểm có kênh lớn nhất ≥ 220/255 tô hồng (vùng
    "da sáng" mà cách đo theo vùng da sáng nhìn vào). Nhãn: mặt đo công tắc cũ (A0) / hiện tại (A)."""
    import autotone as at
    import numpy as np
    from PIL import Image, ImageDraw
    o, cot = 180, 8
    ds = ds[:toi_da]
    hang = (len(ds) + cot - 1) // cot
    to = Image.new("RGB", (cot * o, max(1, hang) * (o + 34)), (24, 24, 26))
    d = ImageDraw.Draw(to)
    f1, f2 = _phong(12), _phong(11)
    for i, r in enumerate(ds):
        x, y = (i % cot) * o, (i // cot) * (o + 34)
        b, wh = r.get("subject_box"), r.get("preview_wh")
        im = at.anh_nho(r["path"], 1600) if b and wh else None
        if im is not None:
            k = im.size[0] / float(wh[0])
            cx, cy, c = (b[0] + b[2] / 2) * k, (b[1] + b[3] / 2) * k, max(b[2], b[3]) * k * 0.75
            cat = im.crop((int(cx - c), int(cy - c), int(cx + c), int(cy + c))).resize((o - 8, o - 8))
            a = np.asarray(cat).copy()
            sang = a.max(axis=2) >= 220
            a[sang] = (0.5 * a[sang] + 0.5 * np.array([255, 0, 200])).astype(np.uint8)
            to.paste(Image.fromarray(a), (x + 4, y + 4))
            pct = f"{100 * sang.mean():.0f}% ≥220"
        else:
            pct = "không mặt"
        d.text((x + 6, y + o + 2), Path(r["path"]).name[:26], fill=(237, 235, 231), font=f1)
        d.text((x + 6, y + o + 17), f"mặt {_f(so_a.get(r['path']))} / {_f(so_c.get(r['path']))} · {pct}",
               fill=(166, 163, 157), font=f2)
    dest.parent.mkdir(parents=True, exist_ok=True)
    to.save(dest, quality=88)
    return len(ds)


def khung_do(r: dict) -> str:
    """Khung mặt ĐEM ĐO (meter_boxes của chính measure): rộng×cao điểm, + số khung YuNet."""
    mb = r.get("meter_boxes") or []
    if not mb:
        return f"không mặt ({len(r.get('all_boxes') or [])} khung)"
    b = max(mb, key=lambda b: b[2] * b[3])
    return f"{b[2]:.0f}×{b[3]:.0f} điểm {b[4]:.2f} ({len(mb)}/{len(r.get('all_boxes') or [])} khung)"


def mat_gia_thang(r: dict) -> bool:
    """Khung đem đo có điểm < mat_ao_diem trong khi ảnh CÓ khung điểm cao hơn bị bỏ."""
    import autotone as at
    nguong = float(at.DEFAULTS.get("mat_ao_diem", 0.6))
    mb, ab = r.get("meter_boxes") or [], r.get("all_boxes") or []
    return bool(mb) and max(b[4] for b in mb) < nguong and any(b[4] >= nguong for b in ab)


def _phong(co: int):
    from PIL import ImageFont
    for ten in ("BeVietnamPro-Regular.ttf", "BeVietnamPro-Medium.ttf"):
        f = Path(__file__).resolve().parent / "fonts" / ten
        if f.is_file():
            try:
                return ImageFont.truetype(str(f), co)
            except OSError:
                pass
    return ImageFont.load_default()


def to_luoi(items_theo_ten: dict, paths: list, dest: Path, toi_da: int = 48) -> int:
    """Tờ ảnh nhỏ: đúng ảnh lưới của app (at.anh_nho), nhãn tên · hướng · ΔEV; khung ĐỎ =
    mặt đem đo (meter_boxes), khung xám = khung YuNet bị bỏ."""
    import autotone as at
    from PIL import Image, ImageDraw
    if len(paths) > toi_da:                                  # rải đều cả buổi
        buoc = len(paths) / toi_da
        paths = [paths[int(i * buoc)] for i in range(toi_da)]
    o, cot = 220, 8
    hang = (len(paths) + cot - 1) // cot
    to = Image.new("RGB", (cot * o, hang * (o + 34)), (24, 24, 26))
    d = ImageDraw.Draw(to)
    f1, f2 = _phong(12), _phong(11)
    for i, p in enumerate(paths):
        x, y = (i % cot) * o, (i // cot) * (o + 34)
        try:
            im = at.anh_nho(p, o - 8)
        except Exception:                                    # noqa: BLE001
            im = None
        r = items_theo_ten.get(str(p)) or {}
        if im is not None:
            x0, y0 = x + (o - im.size[0]) // 2, y + (o - im.size[1]) // 2
            to.paste(im, (x0, y0))
            wh = r.get("preview_wh")
            if wh and wh[0]:
                k = im.size[0] / float(wh[0])               # khung theo ảnh đo đã xoay
                do = {tuple(b[:4]) for b in r.get("meter_boxes") or []}
                for b in r.get("all_boxes") or []:
                    mau = (255, 70, 60) if tuple(b[:4]) in do else (150, 150, 150)
                    d.rectangle([x0 + b[0] * k, y0 + b[1] * k,
                                 x0 + (b[0] + b[2]) * k, y0 + (b[1] + b[3]) * k],
                                outline=mau, width=2 if mau[0] == 255 else 1)
        else:
            d.text((x + 8, y + o // 2), "không đọc được", fill=(252, 161, 142), font=f1)
        d.text((x + 6, y + o + 2), Path(p).name[:30], fill=(237, 235, 231), font=f1)
        d.text((x + 6, y + o + 17), f"hướng {r.get('orientation') or at.doc_the(p).get('orientation') or '-'}"
               f"  Exp {_f(r.get('delta_ev'))}" + ("  MẶT GIẢ?" if mat_gia_thang(r) else ""),
               fill=(252, 161, 142) if mat_gia_thang(r) else (166, 163, 157), font=f2)
    dest.parent.mkdir(parents=True, exist_ok=True)
    to.save(dest, quality=88)
    return len(paths)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--con", action="store_true", help="gồm thư mục con")
    ap.add_argument("--ra", default="")
    ap.add_argument("--luoi", default="")
    ap.add_argument("--mat", default="", help="tờ ảnh cận mặt của các cảnh có cặp lệch")
    ap.add_argument("--jobs", type=int, default=0)
    a = ap.parse_args()

    import autotone as at
    folder = Path(a.folder)
    dong: list = []

    def p(s=""):
        dong.append(str(s))
        print(s, flush=True)

    p(f"KIỂM RAW THẬT — {folder}   ({time.strftime('%d/%m/%Y %H:%M')})")
    p(f"công cụ {PHIEN} · engine {at.dau_engine()}")
    if not folder.is_dir():
        p("KHÔNG THẤY THƯ MỤC.")
        return 2
    pairs, _ = at.collect_pairs(folder, recursive=a.con, need_sidecar=False)
    p(f"{len(pairs)} file RAW · đuôi: "
      + ", ".join(f"{k} {n}" for k, n in Counter(q.suffix.upper() for q, _ in pairs).most_common()))
    if not pairs:
        p("Không có file RAW nào (đuôi app nhận: " + " ".join(sorted(at.RAW_EXTS)) + ").")
        return 1

    # ---------------------------------------------------------------- 1. thông tin chụp
    p("\n1. THÔNG TIN CHỤP (doc_the)")
    tags = {str(q): at.doc_the(q) for q, _ in pairs}
    truong = {"máy": "model", "hướng": "orientation", "ISO": "iso", "tốc": "exposure_time",
              "khẩu": "fnumber", "giờ chụp": "datetime_original"}
    for ten, k in truong.items():
        thieu = [Path(q).name for q, t in tags.items() if t.get(k) in (None, "")]
        p(f"   {ten:9}: {'đủ' if not thieu else f'THIẾU {len(thieu)}/{len(pairs)}'}"
          + (f"  vd. {', '.join(thieu[:5])}" if thieu else ""))
    p("   máy / ống kính: " + "; ".join(f"{m or '?'} · {l or '-'} ({n})" for (m, l), n in Counter(
        (t.get("model"), t.get("lens")) for t in tags.values()).most_common(6)))
    p("   hướng: " + ", ".join(f"{h} ×{n}" for h, n in Counter(
        t.get("orientation") for t in tags.values()).most_common()))

    # ---------------------------------------------------------------- 2. đo
    cfg, nguon_cfg = doc_cfg(folder)
    jobs = at.safe_jobs(a.jobs or 8, cfg)
    p(f"\n2. ĐO (analyze, {jobs} tiến trình) — cấu hình: {nguon_cfg}")
    t0 = time.time()
    items, failed = at.analyze(pairs, cfg, jobs)
    p(f"   đo xong {len(items)}/{len(pairs)} ảnh trong {time.time() - t0:.0f} s"
      + (f" · LỖI {len(failed)}: " + "; ".join(f"{Path(r.get('path', '?')).name}: {r.get('loi') or r.get('err') or r.get('notes')}"
                                                for r in failed[:5]) if failed else ""))
    if not items:
        return 1
    dung = [r for r in items if (r.get("preview_wh") or (1, 0))[1] > (r.get("preview_wh") or (1, 0))[0]]
    huong_doc = [r for r in items if tags.get(r["path"], {}).get("orientation") in (5, 6, 7, 8)]
    p(f"   ảnh xem trước ĐỨNG {len(dung)} · EXIF ghi ảnh dọc {len(huong_doc)}")
    co_mat = [r for r in items if r.get("metered_face_ev") is not None]
    p(f"   thấy mặt {len(co_mat)}/{len(items)} · EV100 có {sum(at.ev100(r) is not None for r in items)}/{len(items)}")
    gia = [r for r in co_mat if mat_gia_thang(r)]
    p(f"   khung đem đo điểm < {at.DEFAULTS.get('mat_ao_diem', 0.6)} trong khi ảnh có khung tin chắc hơn: "
      f"{len(gia)}" + (f"  vd. {', '.join(Path(r['path']).name for r in gia[:8])}" if gia else ""))
    p(f"   ảnh xem trước dùng để đo: " + ", ".join(f"{w}×{h} ({n})" for (w, h), n in Counter(
        tuple(r.get("preview_wh") or (0, 0)) for r in items).most_common(4)))

    # ---------------------------------------------------------------- 3. plan
    bx = at.ban_xuat_cho_thu_muc(folder, gom_con=a.con)
    export = at.read_catalog_export(bx) if bx is not None else {}
    p(f"\n3. PLAN — bản xuất catalog: {bx.name if bx else 'KHÔNG CÓ (ΔEV tính trên nền 0)'}"
      + (f", khớp {sum(1 for q, _ in pairs if at.khoa_duong_dan(q) in export)}/{len(pairs)} ảnh" if bx else ""))
    import copy
    goc_do = copy.deepcopy(items)                            # số đo trước plan (plan sửa tại chỗ)
    at.plan(items, cfg, folder=folder, export=export, ban_xuat=bx)
    loat = at.chia_loat(items, cfg)
    so_loat = {id(r): i + 1 for i, ds in enumerate(loat) for r in ds}
    p(f"   {len({r.get('scene') for r in items})} cảnh · {len(loat)} loạt gom {sum(len(x) for x in loat)} ảnh "
      f"(loạt: cùng máy + cảnh + khẩu/tốc/ISO, ≤ {cfg.get('loat_gio_s', 60)} s, bố cục ≤ "
      f"{cfg.get('loat_bo_cuc', 0.10)}, khung ≤ {cfg.get('loat_khung_ev', 0.25)} EV so tấm đầu loạt)")

    # ---------------------------------------------------------------- 4. cặp lệch
    cap = cap_lech(items)
    p(f"\n4. CẶP LIỀN NHAU cùng máy + cùng khẩu/tốc/ISO mà ΔEV lệch > {LECH_EV:.2f}: {len(cap)}")
    import numpy as np
    for lech, x, y in sorted(cap, key=lambda c: -c[0])[:30]:
        sx, sy = x.get("scene_sig"), y.get("scene_sig")
        bo_cuc = (float(np.abs(np.asarray(sx) - np.asarray(sy)).mean())
                  if sx and sy and len(sx) == len(sy) else None)
        p(f"   {Path(x['path']).name} {_f(x['delta_ev'])} | {Path(y['path']).name} {_f(y['delta_ev'])}"
          f"  lệch {lech:.2f} · cách {(y['dt_obj'] - x['dt_obj']).total_seconds():.0f} s"
          f" · cảnh {x.get('scene')}/{y.get('scene')} · loạt {so_loat.get(id(x), '-')}/{so_loat.get(id(y), '-')}"
          f" · bố cục lệch {_f(bo_cuc, '{:.3f}')}"
          f" · khung {_f(x.get('metered_subject_ev'))}/{_f(y.get('metered_subject_ev'))}"
          f" · mặt {_f(x.get('metered_face_ev'))}/{_f(y.get('metered_face_ev'))}"
          f" · khung đo {khung_do(x)} / {khung_do(y)}")

    # ---------------------------------------------------------------- 4b. thử tắt từng cơ chế
    #  Chỉ CHẨN ĐOÁN: đo lại / tính lại bằng chính analyze() + plan() với một khoá cfg đổi.
    #  Biến thể nào làm hết cặp lệch thì cơ chế đó là thủ phạm trên bộ ảnh này.
    p("\n4b. THỬ TẮT TỪNG CƠ CHẾ (đo lại / tính lại bằng hàm thật — chỉ để chẩn đoán)")
    p(f"   A hiện tại (đo vùng da sáng chuyển dần theo máy: {cfg.get('hl_da_tron_theo_may')})"
      " · A0 công tắc cũ trước 14/10 (hl_da_tron_theo_may = {})"
      " · B tắt 'mặt nét sáng nhất' (mat_sang_nhat) · C tắt hẳn 'đo theo vùng da sáng'"
      f" (hl_da_ti_le {cfg.get('hl_da_ti_le')} -> 0) · D tắt cả hai")
    do_c, _ = at.analyze(pairs, dict(cfg, hl_da_ti_le=0.0), jobs)
    do_a0, _ = at.analyze(pairs, dict(cfg, hl_da_tron_theo_may={}), jobs)
    bien: dict = {"A": items}
    for ten, goc, them in (("A0", do_a0, {"hl_da_tron_theo_may": {}}),
                           ("B", goc_do, {"mat_sang_nhat": False}),
                           ("C", do_c, {"hl_da_ti_le": 0.0}),
                           ("D", do_c, {"hl_da_ti_le": 0.0, "mat_sang_nhat": False})):
        ds_b = copy.deepcopy(goc)
        at.plan(ds_b, dict(cfg, **them), folder=folder, export=export, ban_xuat=bx)
        bien[ten] = ds_b
    dv = {k: {r["path"]: r.get("delta_ev") for r in v} for k, v in bien.items()}
    mat_c = {r["path"]: r.get("metered_face_ev") for r in do_c}
    mat_a = {r["path"]: r.get("metered_face_ev") for r in goc_do}      # số đo của measure, trước plan
    mat_a0 = {r["path"]: r.get("metered_face_ev") for r in do_a0}
    p("   số cặp lệch > %.2f:  " % LECH_EV + " · ".join(f"{k} {len(cap_lech(v))}" for k, v in bien.items()))
    nghi = {r["path"] for v in (items, bien["A0"]) for _, x, y in cap_lech(v) for r in (x, y)}
    canh = {r.get("scene") for r in items if r["path"] in nghi}
    xem = [r for r in sorted(items, key=lambda r: r["dt_obj"]) if r.get("scene") in canh][:60]
    if xem:
        p("   tên | ΔEV A | A0 | B | C | D | mặt đo A | A0 | C (không đo vùng da sáng) | mặt sau plan A | cảnh")
        for r in xem:
            q = r["path"]
            p(f"   {Path(q).name} | {_f(dv['A'].get(q))} | {_f(dv['A0'].get(q))} | {_f(dv['B'].get(q))} | "
              f"{_f(dv['C'].get(q))} | {_f(dv['D'].get(q))} | {_f(mat_a.get(q))} | {_f(mat_a0.get(q))} | "
              f"{_f(mat_c.get(q))} | {_f(r.get('metered_face_ev'))} | {r.get('scene')}")
    if a.mat and xem:
        n = to_mat(xem, Path(a.mat), mat_a0, mat_a)
        p(f"   tờ ảnh cận mặt ({n} tấm, hồng = điểm ≥ 220/255): {a.mat}")

    # ---------------------------------------------------------------- 5. từng ảnh
    p("\n5. TỪNG ẢNH")
    p("   tên | máy | hướng | ISO | tốc | khẩu | giờ | xem trước | khung mặt đo | mặt EV | khung EV | EV100 | cảnh | loạt | ΔEV | ghi chú")
    for r in sorted(items, key=lambda r: (str(r.get("model") or ""), r["dt_obj"])):
        t = tags.get(r["path"], {})
        wh = r.get("preview_wh") or ("?", "?")
        p(f"   {Path(r['path']).name} | {t.get('model') or '-'} | {t.get('orientation') or '-'} | "
          f"{t.get('iso') or '-'} | {_toc(t.get('exposure_time'))} | f/{_f(_so(t.get('fnumber')), '{:g}')} | "
          f"{(t.get('datetime_original') or '-')[11:]} | {wh[0]}×{wh[1]} | {khung_do(r)} | {_f(r.get('metered_face_ev'))} | "
          f"{_f(r.get('metered_subject_ev'))} | {_f(at.ev100(r), '{:.1f}')} | {r.get('scene')} | "
          f"{so_loat.get(id(r), '-')} | {_f(r.get('delta_ev'))} | {(r.get('notes') or '')[:80]}")
    if items:
        dl = [float(r["delta_ev"]) for r in items if r.get("delta_ev") is not None]
        if dl:
            p(f"\n   ΔEV: trung vị {statistics.median(dl):+.2f}, thấp nhất {min(dl):+.2f}, cao nhất {max(dl):+.2f}")

    # ---------------------------------------------------------------- 6. tờ ảnh nhỏ
    if a.luoi:
        n = to_luoi({r["path"]: dict(r, orientation=tags.get(r["path"], {}).get("orientation"))
                     for r in items}, [str(q) for q, _ in pairs], Path(a.luoi))
        p(f"\n6. Tờ ảnh nhỏ ({n} tấm, như lưới của app): {a.luoi}")
    if a.ra:
        Path(a.ra).write_text("\n".join(dong) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
