#!/usr/bin/env python3
"""Cổng kiểm cho MỌI đề xuất chỉnh tham số — Agent phải qua đây trước khi mở miệng.

VÌ SAO PHẢI CÓ CỔNG
    Mọi thứ học được từ ảnh người dùng sửa đều có một điểm mù chung: mẫu toàn
    là những ca tool làm SAI. Ảnh tool làm đúng thì người dùng không động vào,
    nên không để lại dấu vết nào — mà đó mới là đa số.

    Đo thật trên buổi 1308: khớp theo 185 ảnh đã sửa ra mốc -1.42; tính cả 532
    ảnh cùng nhóm ra -1.19, đúng bằng mốc đang dùng. Nghe theo con số đầu là
    phá 893 ảnh đã duyệt để chiều 185 ảnh bị sửa.

    Nên không đề xuất nào được tin bằng lý lẽ. Chỉ được tin bằng số đo trên
    chính những ảnh người dùng ĐÃ DUYỆT.

HAI CỔNG — đặt trước khi chạy, không nới sau
    A. Ảnh có đích đúng (người dùng sửa tay): số ảnh được kéo LẠI GẦN phải
       NHIỀU HƠN số bị đẩy RA XA.
    B. Ảnh đã duyệt (xuất ra, không sửa gì -> tool đã đúng): dưới 2% bị xê
       dịch quá 0.30 EV.

    Không đạt thì bỏ đề xuất và ghi lý do. KHÔNG chỉnh tham số cho vừa cổng —
    làm thế là biến cổng thành thứ trang trí.

CHẠY ĐÚNG ĐƯỜNG SẢN PHẨM
    Gọi thẳng analyze() + plan() của autotone, hai lượt, chỉ khác nhau đúng
    những khoá trong file đề xuất. Không dựng lại logic nào.

CÁCH DÙNG
    Viết đề xuất ra một file JSON, ví dụ de_xuat.json:
        {"face_target_ev": -1.24, "big_low_floor": 0.65}

    rồi:
        python kiem_gu.py G:\\1308 --de-xuat de_xuat.json

    Đạt cả hai cổng thì ghi vào gu.json để mọi công cụ dùng chung:
        python kiem_gu.py G:\\1308 --de-xuat de_xuat.json --ghi-gu
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import ntpath
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at   # noqa: E402


def ten(p) -> str:
    return ntpath.splitext(ntpath.basename(str(p)))[0].strip().lower()


def doc_export(p: Path) -> dict:
    out = {}
    with io.open(p, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            try:
                out[ten(r["path"])] = int(float(r.get("Rating") or 0))
            except (TypeError, ValueError):
                out[ten(r["path"])] = 0
    return out


CHUA_GAN = "chua-gan-ly-do"


def dich_dung(folder: Path, here: Path, export_p: Path | None) -> dict:
    """Ảnh có đích đúng -> (Exposure người dùng chọn, lý do họ sửa).

    Nguồn 1: corrections.csv — kho cũ, KHÔNG có lý do.
    Nguồn 2: gu/<buổi>/gu.csv — bản mới, có lý do. Đè lên nguồn 1.

    VÌ SAO PHẢI CÓ LÝ DO Ở ĐÂY
        Không có lý do thì cổng A chấm mù. Đo thật ngày 2/9: đề xuất sửa MỐC
        CẢNH bị cổng A đánh trượt 0-10 trên 185 ảnh của buổi 1308 — nhưng phần
        lớn 185 ảnh đó người dùng sửa vì tool ĐO NHẦM MẶT, chuyện chẳng liên
        quan gì tới mốc cảnh. Cổng vừa không đo được cái cần đo, vừa phạt oan
        một đề xuất chỉ vì nó chạm nhẹ vào mấy tấm không liên quan.

        Có lý do thì chấm được đúng nhóm: sửa mốc cảnh thì chấm trên nhóm
        "lech-anh-ben", sửa mốc sáng thì chấm trên "toi-qua"/"sang-qua".
    """
    out = {}
    store = here / "corrections.csv"
    if store.is_file():
        with io.open(store, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                try:
                    out[ten(r["file"])] = (float(r["user_exposure"]), CHUA_GAN)
                except (TypeError, ValueError, KeyError):
                    continue
    buoi = ntpath.basename(str(folder).rstrip("\\/")) or str(folder)
    g = here / "gu" / buoi / "gu.csv"
    if g.is_file():
        with io.open(g, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                try:
                    out[ten(r["file"])] = (float(r["user_exposure"]),
                                           (r.get("ly_do") or "").strip() or CHUA_GAN)
                except (TypeError, ValueError, KeyError):
                    continue
    return out


def cham(ds) -> tuple:
    """(kéo lại gần, đẩy ra xa, sai trung bình cũ, sai trung bình mới).

    Để ngoài main() để bài kiểm gọi được đúng hàm này thay vì viết lại phép
    chấm — viết lại là cách chắc chắn nhất để bài kiểm và cổng thật lệch nhau.
    """
    gan = xa = 0
    sc = sm = 0.0
    for r in ds:
        u = float(r["nguoi_dung"])
        sc += abs(r["ev_cu"] - u)
        sm += abs(r["ev_moi"] - u)
        if abs(r["ev_moi"] - u) < abs(r["ev_cu"] - u) - 1e-6:
            gan += 1
        elif abs(r["ev_moi"] - u) > abs(r["ev_cu"] - u) + 1e-6:
            xa += 1
    n = max(len(ds), 1)
    return gan, xa, sc / n, sm / n


def chay_mot_luot(folder: Path, cfg: dict, jobs: int, export: dict) -> dict:
    catalog = cfg.get("source") == "catalog"
    pairs, thieu = at.collect_pairs(folder, need_sidecar=not catalog)
    if thieu:
        print(f"    ({len(thieu)} anh thieu sidecar, bo qua)")
    t0 = time.time()
    items, failed = at.analyze(pairs, cfg, jobs)
    at.plan(items, cfg, folder, export)
    print(f"    {len(items)} anh, {len(failed)} loi, {time.time() - t0:.0f}s")
    return {ten(r["path"]): r for r in items}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Cong kiem cho de xuat chinh tham so.")
    ap.add_argument("folder", type=Path)
    ap.add_argument("--de-xuat", type=Path, required=True,
                    help="File JSON chua cac khoa muon doi")
    ap.add_argument("--ghi-gu", action="store_true",
                    help="Dat ca hai cong thi ghi vao gu.json")
    ap.add_argument("--chuan", action="append", default=[],
                    help="Dich dung biet truoc, vd --chuan SAY09660=0.44. Lap lai duoc. "
                         "Cong hem vao tap 'anh co dich dung'.")
    ap.add_argument("--nhom", action="append", default=[],
                    help="Chi cham cong A tren anh mang ly do nay, vd "
                         "--nhom lech-anh-ben. Lap lai duoc. Khong dat thi cham "
                         "tren tat ca (va bao rieng tung nhom).")
    ap.add_argument("--nhom-it-nhat", type=int, default=8,
                    help="Nhom duoi bay nhieu ca thi KHONG ket luan (md: 8)")
    ap.add_argument("--cap", action="append", default=[],
                    help="Hai anh CUNG MOT KHUNG HINH, vd --cap SAY09787,SAY09788. "
                         "Lap lai duoc. Bao khoang cach truoc/sau khi doi tham so.")
    ap.add_argument("--export", type=Path, default=None)
    ap.add_argument("--nguong-lech", type=float, default=0.30)
    ap.add_argument("--cong", type=float, default=2.0)
    ap.add_argument("--jobs", type=int, default=0)
    ap.add_argument("--nguon", default="catalog", choices=["catalog", "sidecar"])
    a = ap.parse_args(argv)

    here = Path(__file__).resolve().parent
    try:
        dx = json.loads(Path(a.de_xuat).read_text(encoding="utf-8"))
    except (OSError, ValueError) as ex:
        print(f"Khong doc duoc {a.de_xuat}: {ex}")
        return 1
    if not isinstance(dx, dict) or not dx:
        print("File de xuat phai la mot doi tuong JSON khong rong.")
        return 1
    la = sorted(set(dx) - set(at.DEFAULTS))
    if la:
        print(f"De xuat co khoa khong dung den: {', '.join(la)}")
        return 1

    print("De xuat doi:")
    for k, v in sorted(dx.items()):
        print(f"  {k:24} {at.DEFAULTS[k]}  ->  {v}")
    khong_doi = [k for k, v in dx.items() if v == at.DEFAULTS[k]]
    if khong_doi:
        print(f"\n[!] {', '.join(khong_doi)} bang y gia tri dang chay — de xuat "
              f"nay khong doi gi ca.")

    if a.export is None:
        a.export = at.latest_catalog_export(here / "AutoTone.lrplugin" / "jobs")
    if a.export is None and a.nguon == "catalog":
        print("Khong thay export_*.tsv nao. Chi ro bang --export.")
        return 1
    if a.export is not None:
        print(f"\nDung file export: {Path(a.export).name}")

    chuan = dich_dung(a.folder, here, a.export)
    #[[ --chuan de len corrections.csv chu khong nguoc lai: no la thu nguoi
    #   dung vua go tay o dong lenh cho dung ca nay, con kho la so cu.
    #]]
    for c in a.chuan:
        k, _, v = c.partition("=")
        try:
            chuan[ten(k)] = (float(v), "chuan-dong-lenh")
        except ValueError:
            print(f"--chuan doc khong ra: {c}")
            return 1
    rating = doc_export(a.export) if a.export else {}
    print(f"Tap kiem: {len(chuan)} anh co dich dung"
          f" | {sum(1 for k, v in rating.items() if v != 1 and k not in chuan)} anh da duyet")

    jobs = at.safe_jobs(a.jobs or 8, dict(at.DEFAULTS))
    #[[ bo_qua_nguoi_sua PHAI TAT trong bai kiem.
    #   Bat len thi dung nhung anh co dich dung bi loai khoi `items` — tuc mat
    #   sach co so cua cong A, va cong A la cong quan trong hon trong hai cai.
    #]]
    chung = dict(at.DEFAULTS, source=a.nguon, bo_qua_nguoi_sua=False)
    exp = at.read_catalog_export(a.export) if (a.nguon == "catalog" and a.export) else {}

    print(f"So tien trinh: {jobs}\n")
    print("Luot 1/2 — tham so DANG CHAY")
    cu = chay_mot_luot(a.folder, dict(chung), jobs, exp)
    print("Luot 2/2 — tham so DE XUAT")
    moi = chay_mot_luot(a.folder, dict(chung, **dx), jobs, exp)

    rows = []
    for k, r0 in cu.items():
        r1 = moi.get(k)
        if r1 is None:
            continue
        e0, e1 = r0.get("new_exposure"), r1.get("new_exposure")
        if e0 is None or e1 is None:
            continue
        #[[ GHI KEM DAC TRUNG CUA TUNG ANH — cho CA anh da duyet.
        #
        #   Thieu no thi khong tinh duoc TI LE NEN, va khong co ti le nen thi
        #   moi con so "do chinh xac" deu vo nghia.
        #
        #   Da tra gia that ngay 2/9: toi do rang nguong bao hoa 8% bat dung
        #   73/78 anh trong tap NGUOI DUNG DA SUA -> ket luan "94% chinh xac".
        #   Nhung 44% anh CUA CA BUOI cung tren nguong do. Chot bat trung 36
        #   anh dung va 417 anh sai. Con so 94% do chi ra vay vi tap do chi
        #   gom anh tool lam sai — toi khong he doi chieu voi anh binh thuong.
        #
        #   Tu gio moi dac trung deu ra file, de lan sau so sanh duoc hai phan
        #   bo truoc khi tin bat ky nguong nao.
        #]]
        def _s(r, k, n=4):
            v = r.get(k)
            try:
                return round(float(v), n)
            except (TypeError, ValueError):
                return ""

        rows.append({"file": k, "canh": r0.get("scene", ""),
                     "canh_n": r0.get("scene_size", ""),
                     "ev_cu": round(float(e0), 4), "ev_moi": round(float(e1), 4),
                     "lech": round(float(e1) - float(e0), 4),
                     "nguoi_dung": chuan.get(k, ("", ""))[0],
                     "ly_do": chuan.get(k, ("", ""))[1],
                     "duyet": int(k not in chuan and rating.get(k, 0) != 1),
                     "metered_ev": _s(r0, "metered_ev"),
                     "target_ev": _s(r0, "target_ev"),
                     "vung_bao_hoa": _s(r0, "sat_frac"),
                     "vung_sang": _s(r0, "bright_frac"),
                     "vung_bet": _s(r0, "crush_frac"),
                     "clip_before": _s(r0, "clip_before_pct", 2),
                     "clip_after": _s(r0, "clip_after_pct", 2),
                     "faces_n": r0.get("faces_n", ""),
                     "iso": r0.get("iso", ""),
                     "notes": r0.get("notes", "")})
    if not rows:
        print("\nKhong ghep duoc anh nao giua hai luot. Kiem thu muc RAW va --nguon.")
        return 1

    dest = a.folder / "kiem_gu.csv"
    with io.open(dest, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ---------- CỔNG A ----------
    s = [r for r in rows if r["nguoi_dung"] != ""]
    if a.nhom:
        s = [r for r in s if r["ly_do"] in set(a.nhom)]
    print(f"\n{'=' * 66}\nCONG A — {len(s)} anh co dich dung"
          + (f"  (chi nhom: {', '.join(a.nhom)})" if a.nhom else ""))
    cong_a = True
    if not s:
        if a.nhom:
            print(f"  Khong anh nao mang ly do {', '.join(a.nhom)}.")
            print("  Chay thu_gu.py roi gan ly do bang nut \"Vi sao toi sua\".")
            cong_a = False
        else:
            print("  (khong co anh nao — chay thu_gu.py truoc de co dich dung)")
    elif len(s) < a.nhom_it_nhat:
        #[[ KHONG ket luan khi qua it ca. Vai anh khong noi len duoc gi, va mot
        #   cong "dat" dua tren 3 anh con nguy hiem hon khong co cong: no cho
        #   phep doi tham so ma van thay minh dang can than.
        #]]
        gan, xa, sc, sm = cham(s)
        print(f"  keo LAI GAN {gan} | day RA XA {xa} | sai t.b {sc:.3f} -> {sm:.3f} EV")
        print(f"  -> CHUA KET LUAN DUOC: chi {len(s)} ca, can it nhat {a.nhom_it_nhat}")
        cong_a = False
    else:
        gan, xa, sc, sm = cham(s)
        print(f"  keo LAI GAN dich : {gan} anh")
        print(f"  day RA XA        : {xa} anh")
        print(f"  sai trung binh   : {sc:.3f} -> {sm:.3f} EV")
        cong_a = gan >= xa
        print(f"  -> {'DAT' if cong_a else 'KHONG DAT'}")
        for r in sorted(s, key=lambda r: -abs(r["lech"]))[:8]:
            u = float(r["nguoi_dung"])
            print(f"     {r['file']:<12} {r['ev_cu']:+.2f} -> {r['ev_moi']:+.2f}"
                  f"   (ban chon {u:+.2f}; sai {abs(r['ev_cu']-u):.2f} -> "
                  f"{abs(r['ev_moi']-u):.2f})")

    #[[ Bang theo tung ly do — luon in, ke ca khi khong dat --nhom.
    #
    #   Con so tong gop moi ly do lai thi giau mat dieu quan trong nhat: mot de
    #   xuat co the giup dung nhom no nham toi va cham nhe vao ba nhom khac,
    #   roi bi cham truot vi tong. Da xay ra that ngay 2/9 voi de xuat moc canh.
    #]]
    tat = [r for r in rows if r["nguoi_dung"] != ""]
    if tat:
        nhom = {}
        for r in tat:
            nhom.setdefault(r["ly_do"] or CHUA_GAN, []).append(r)
        print(f"\n  Theo tung ly do:")
        print(f"    {'ly do':<20}{'n':>5}{'gan':>6}{'xa':>5}{'dong toi':>10}"
              f"{'sai t.b cu -> moi':>22}")
        for k in sorted(nhom, key=lambda k: -len(nhom[k])):
            g = nhom[k]
            gan, xa, sc, sm = cham(g)
            dong = sum(1 for r in g if abs(r["lech"]) > 0.005)
            print(f"    {k:<20}{len(g):>5}{gan:>6}{xa:>5}{dong:>10}"
                  f"{sc:>11.3f} ->{sm:>8.3f}")
        if CHUA_GAN in nhom:
            print(f"    ({len(nhom[CHUA_GAN])} anh chua co ly do — cong cham mu tren "
                  f"nhom nay)")

    # ---------- CỔNG B ----------
    d = [r for r in rows if r["duyet"]]
    dung = [r for r in d if abs(r["lech"]) > a.nguong_lech]
    pct = 100.0 * len(dung) / max(len(d), 1)
    print(f"\nCONG B — {len(d)} anh da duyet")
    print(f"  xe dich qua {a.nguong_lech} EV: {len(dung)}  ({pct:.2f}%)")
    cong_b = pct < a.cong
    print(f"  cong cho phep duoi {a.cong}%  -> {'DAT' if cong_b else 'KHONG DAT'}")
    if dung:
        v = sorted(abs(r["lech"]) for r in dung)
        print(f"  bien do nhom bi dung: trung vi {v[len(v) // 2]:.2f}, "
              f"lon nhat {v[-1]:.2f} EV")
        for r in sorted(dung, key=lambda r: -abs(r["lech"]))[:8]:
            print(f"     {r['file']:<12} {r['ev_cu']:+.2f} -> {r['ev_moi']:+.2f}"
                  f"  ({r['lech']:+.2f})")

    # ---------- Cặp ảnh cùng khung hình ----------
    #[[ Khong tinh vao cong. Day la thuoc do RIENG cho benh "cung mot khung
    #   hinh ra hai muc sang khac nhau" — thu ma ca hai cong deu khong thay,
    #   vi ca hai anh deu co the "dung" theo tung tieu chi rieng le.
    #]]
    for c in a.cap:
        pr = [ten(x) for x in c.split(",")]
        if len(pr) != 2 or any(x not in cu for x in pr):
            print(f"\nCAP {c}: khong tim thay du hai anh, bo qua")
            continue
        d0 = abs(float(cu[pr[0]]["new_exposure"]) - float(cu[pr[1]]["new_exposure"]))
        d1 = abs(float(moi[pr[0]]["new_exposure"]) - float(moi[pr[1]]["new_exposure"]))
        print(f"\nCAP {pr[0]} / {pr[1]} — cung mot khung hinh")
        print(f"  canh {cu[pr[0]].get('scene')} (n={cu[pr[0]].get('scene_size')})"
              f"  vs  canh {cu[pr[1]].get('scene')} (n={cu[pr[1]].get('scene_size')})")
        print(f"  cach nhau: {d0:.2f} EV  ->  {d1:.2f} EV   "
              f"{'(gan lai)' if d1 < d0 - 1e-6 else '(khong doi hoac xa hon)'}")

    ok = cong_a and cong_b
    print(f"\n{'=' * 66}")
    print("KET LUAN: " + ("CA HAI CONG DAT" if ok else
                          "KHONG DAT — bo de xuat nay, ghi lai ly do"))
    print(f"-> {dest.name}")

    if a.ghi_gu:
        if not ok:
            print("\nKhong ghi gu.json vi de xuat chua qua cong.")
            return 1
        gu = {}
        if at.GU_FILE.is_file():
            try:
                gu = json.loads(at.GU_FILE.read_text(encoding="utf-8"))
            except ValueError:
                gu = {}
        gu.update(dx)
        tmp = at.GU_FILE.with_suffix(".part")
        tmp.write_text(json.dumps(gu, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(at.GU_FILE)
        print(f"\nDa ghi {at.GU_FILE.name}. Moi cong cu se dung tham so nay tu lan chay sau.")
    elif ok:
        print("\nMuon ap dung: chay lai voi them co --ghi-gu")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
