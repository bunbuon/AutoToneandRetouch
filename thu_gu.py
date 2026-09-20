#!/usr/bin/env python3
"""Gói duyệt sau mỗi buổi — thu lại ĐÚNG những ảnh anh đã sửa tay, kèm bằng chứng.

VÌ SAO CẦN CÁI NÀY, KHI ĐÃ CÓ learn_corrections.py
    learn_corrections chỉ lưu hai cột số: tool ghi bao nhiêu, người dùng chọn
    bao nhiêu. Hai cột đó không trả lời được câu quyết định:

        Anh sửa vì TOOL SAI, hay vì GU CỦA ANH khác?

    Trộn hai loại đó vào một phép trung vị là hỏng. Đo thật trên buổi 1308:
    khớp theo 185 ảnh đã sửa ra mốc -1.42; tính cả 532 ảnh cùng nhóm ra -1.19,
    tức mốc đang dùng KHÔNG sai. Nghe theo con số đầu là phá 893 ảnh đã duyệt
    để chiều 185 ảnh bị sửa — mà trong 185 ảnh đó phần lớn là tool đo nhầm mặt,
    chuyện chẳng liên quan gì tới mốc sáng.

    File này thu thêm hai thứ learn_corrections không có:
      1. BỐI CẢNH đầy đủ của từng ảnh (metered_ev, cháy trước, số mặt, cảnh...)
      2. ẢNH có vẽ khung mặt — nhìn là biết ngay tool đo vào đâu

    Có ảnh thì phân biệt được "đo nhầm mặt" với "đo đúng mà tôi thích sáng hơn"
    mà gần như không cần anh giải thích. Đó là hai nhóm lớn nhất.

KHUNG MÀU — LẤY THẲNG TỪ measure(), KHÔNG DỰNG LẠI
    XANH LÁ dày   khung tool dùng làm chủ thể chính của phép đo
    XANH DƯƠNG    khung cũng được tính vào phép đo
    XÁM gạch chéo khung nhận ra nhưng đã bị loại

    Trong dự án này đã bốn lần tôi dựng lại logic chọn chủ thể ở file phân tích
    rồi kết luận sai, vì bản dựng lại thiếu mất một vòng lọc. Nên mọi khung ở
    đây đều là thứ measure() TỰ BÁO VỀ, không phải thứ file này tính ra.

CÁCH DÙNG
    Sau khi sửa tay xong trong Lightroom, chạy "AutoTone: xuất thông số", rồi:

        python thu_gu.py G:\\1308

    -> gu\\1308\\gu.csv          mỗi ảnh đã sửa một dòng, cột ly_do để trống
       gu\\1308\\anh_01.png ...  ảnh có khung, đánh số khớp cột `so`
       gu\\1308\\boi_canh.json   tóm tắt cho Agent đọc

    Sau đó gắn lý do bằng nút "Vì sao tôi sửa" trong giao diện, hoặc đưa cả
    thư mục gu\\<buổi> cho Claude.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import ntpath
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import duong_dan as dd
import autotone as at   # noqa: E402

# Dưới mức này coi như làm tròn, không phải người dùng sửa thật.
NGUONG_SUA_EV = 0.05

CELL = 430
PAD = 30
COLS = 4
MOI_TAM = 12

#[[ DANH SACH LY DO — moi ly do tro toi MOT nhom tham so khac nhau.
#
#   Day la phan quan trong nhat cua ca co che. Neu chi co mot o "nguoi dung
#   muon khac" thi ta quay lai dung cho cu: mot phep trung vi tron lan bug voi
#   gu. Moi dong duoi day tach ra mot nguyen nhan co CACH SUA RIENG.
#
#   Cot thu hai khong phai de tool tu doi — no de Agent biet phai de xuat vao
#   dau, va de nguoi doc kiem tra duoc de xuat co hop ly khong.
#]]
LY_DO = [
    ("do-nham-mat", "Tool đo vào thứ không phải mặt chủ thể (phông, gáy, người phụ)",
     "luật chọn chủ thể: big_low_ratio, face_min_ratio, subject_keep"),
    ("toi-qua", "Đo đúng mặt, nhưng tôi muốn SÁNG hơn",
     "face_target_ev"),
    ("sang-qua", "Đo đúng mặt, nhưng tôi muốn TỐI hơn",
     "face_target_ev"),
    ("nen-chay", "Nền/vùng sáng bị cháy mất chi tiết — ghìm chưa đủ",
     "hl_hard_pct, hl_trigger_pct, hl_heavy_clip_pct"),
    ("chu-the-toi", "Ghìm quá tay, người bị tối đi",
     "hl_subject_floor_ev"),
    ("lech-anh-ben", "Tấm này lệch hẳn so với ảnh chụp cùng lúc",
     "san phẳng cảnh: scene_aim_slack_ev, scene_level, gom cảnh"),
    ("khac", "Lý do khác — gõ vào cột giai_thich", ""),
]
MA_LY_DO = [m for m, _, _ in LY_DO]

#[[ Cot boi canh lay tu HAI nguon, uu tien nguon do duoc ngay tai cho.
#
#   measure() da phai chay o day de ve khung, nen no san sang tra ve metered_ev,
#   so mat, do sang cua ca khung... mien phi. Truoc day file nay bo qua het va
#   chi doc tu bao cao autotone*.csv — bao cao do LA TUY CHON, nguoi dung phai
#   nho bam "Luu CSV". Khong bam thi ca goi duyet mat sach boi canh: do that
#   tren buoi 1308, metered_ev rong 0/187 dong. Agent khong con gi de tim quy
#   luat, dung benh cu cua corrections.csv lap lai.
#
#   Bao cao van duoc dung, nhung chi cho nhung cot measure() KHONG biet:
#   canh, target_ev, clip_before/after — nhung thu chi co sau khi chay ca thu muc.
#]]
COT = ["so", "file", "ly_do", "giai_thich",
       "tool_exposure", "user_exposure", "sua_bao_nhieu",
       # do duoc ngay tai cho tu measure()
       "metered_ev", "mat_ev", "chu_the_ev", "khung_ev", "mat_hon_khung_ev",
       "vung_bao_hoa", "vung_sang", "vung_bet",
       "faces_n", "faces_found",
       # chi co khi co bao cao autotone*.csv
       "target_ev", "clip_before", "clip_after", "scene", "scene_size",
       "khung_tong", "khung_do_sang", "nguon_do", "diem_chu_the",
       "iso", "notes", "anh", "anh_le"]


def ten(p) -> str:
    return ntpath.splitext(ntpath.basename(str(p)))[0].strip().lower()


def doc_tsv(p: Path) -> dict:
    if not p or not Path(p).is_file():
        return {}
    with io.open(p, encoding="utf-8-sig", newline="") as fh:
        return {ten(r["path"]): r for r in csv.DictReader(fh, delimiter="\t")}


def doc_bao_cao(p: Path) -> dict:
    if not p or not Path(p).is_file():
        return {}
    with io.open(p, encoding="utf-8-sig", newline="") as fh:
        return {ten(r["path"]): r for r in csv.DictReader(fh)}


def so(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def tim_bao_cao(folder: Path, here: Path) -> Path | None:
    #[[ Tim CA HAI cho. write_report() ghi vao thu muc buoi chup, nhung nguoi
    #   dung cung hay luu canh script. Ban cu cua learn_corrections chi tim mot
    #   cho va do la ly do 185/185 dong trong corrections.csv khong co boi canh.
    #]]
    c = sorted([p for d in (folder, here) for p in d.glob("autotone*.csv")],
               key=lambda p: p.stat().st_mtime)
    return c[-1] if c else None


def preview(p: Path, px: int):
    blob, tags = at.read_raw(p)
    if blob is None:
        return None
    im = Image.open(io.BytesIO(blob))
    im.draft("RGB", (px, px))
    im = at.apply_orientation(im.convert("RGB"), tags.get("orientation"))
    im.thumbnail((px, px), Image.BILINEAR)
    return im.convert("RGB")


def _gan(a, b, eps: float = 1.5) -> bool:
    return all(abs(u - v) <= eps for u, v in zip(a, b))


def ve_khung(im: Image.Image, r: dict) -> Image.Image:
    """Vẽ đúng ba loại khung measure() trả về. Không tự chọn gì cả."""
    d = ImageDraw.Draw(im)
    meter = [tuple(b[:4]) for b in (r.get("meter_boxes") or [])]
    sub = r.get("subject_box")
    sub4 = tuple(sub[:4]) if sub else None
    for b in (r.get("all_boxes") or []):
        x, y, w, h, s = b
        key = (x, y, w, h)
        if sub4 is not None and _gan(key, sub4):
            col, wd = (60, 220, 120), 5
        elif any(_gan(key, m) for m in meter):
            col, wd = (80, 170, 255), 4
        else:
            col, wd = (155, 155, 160), 2
            d.line([x, y, x + w, y + h], fill=col, width=1)
        d.rectangle([x, y, x + w, y + h], outline=col, width=wd)
        d.text((x + 3, y + 3), f"{s:.2f}", fill=(245, 245, 250))
    return im


def do_lai(p: Path, cfg: dict) -> dict:
    """Gọi ĐÚNG hàm sản phẩm để lấy khung. Không thêm, không bớt."""
    return at.measure(
        p, cfg["preview_px"], cfg["meter"], cfg["meter_highlight_cut"],
        cfg["wb"] == "skin", cfg["face_px"], cfg["face_score"],
        cfg["focus_quantile"], cfg["focus_face_gain"],
        cfg.get("face_min_ratio", 0.0), cfg.get("subject_keep", 0.60),
        cfg.get("subject_dark_ev", 2.0), cfg.get("face_min_score_sub", 0.0),
        cfg.get("big_low_ratio", 0.0), cfg.get("big_low_gap", 0.13),
        cfg.get("big_low_floor", 0.70))


def ve_tam(cells: list, dest_dir: Path, buoi: str) -> list:
    """Xếp ảnh thành các tấm 12 ô. Mỗi hàng tính chiều cao riêng."""
    made = []
    for s in range(0, len(cells), MOI_TAM):
        chunk = cells[s:s + MOI_TAM]
        for c in chunk:
            c["im"].thumbnail((CELL - 10, CELL - 10))
        cols = min(COLS, len(chunk))
        nrow = (len(chunk) + cols - 1) // cols
        #[[ Chieu cao TUNG HANG rieng: anh doc cao gan gap doi anh ngang, lay
        #   chung mot chieu cao thi hang toan anh ngang chua mot mang den to.
        #]]
        hrow = [max(c["im"].size[1] for c in chunk[ri * cols:(ri + 1) * cols])
                for ri in range(nrow)]
        ytop = [10 + sum(h + PAD + 28 for h in hrow[:ri]) for ri in range(nrow)]
        H = ytop[-1] + hrow[-1] + PAD + 28
        sheet = Image.new("RGB", (cols * CELL, H), (22, 22, 24))
        d = ImageDraw.Draw(sheet)
        for k, c in enumerate(chunk):
            cx = (k % cols) * CELL
            cy = ytop[k // cols] - 5
            sheet.paste(c["im"], (cx + 5, cy + 5))
            ty = cy + c["im"].size[1] + 10
            d.text((cx + 6, ty), f"{c['so']}. {c['ten']}", fill=(238, 238, 242))
            d.text((cx + 6, ty + 14),
                   f"    tool {c['tool']:+.2f}  ->  ban chon {c['user']:+.2f}"
                   f"   ({c['diff']:+.2f})", fill=(255, 205, 120))
            d.text((cx + 6, ty + 28),
                   f"    {c['khung_tong']} khung -> {c['khung_do']} do sang"
                   f"   chay truoc {c['clip']}", fill=(172, 172, 180))
        d.text((8, H - 16),
               f"[{buoi}]  xanh la = mat tool dung do sang | xanh duong = cung tinh"
               f" | xam = da loai", fill=(150, 150, 158))
        dest = dest_dir / f"anh_{s // MOI_TAM + 1:02d}.png"
        sheet.save(dest)
        made.append(dest)
    return made


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Thu goi duyet sau mot buoi chup.")
    ap.add_argument("folder", type=Path)
    ap.add_argument("--export", type=Path, default=None,
                    help="export_*.tsv (md: file moi nhat trong thu muc jobs)")
    ap.add_argument("--bao-cao", type=Path, default=None,
                    help="autotone*.csv (md: moi nhat trong thu muc buoi hoac canh script)")
    ap.add_argument("--ra", type=Path, default=None,
                    help="Thu muc goi duyet (md: <canh script>\\gu\\<ten buoi>)")
    ap.add_argument("--khong-ve", action="store_true",
                    help="Bo qua buoc ve anh — chi ra gu.csv, nhanh hon nhieu")
    #[[ --toi-da chi gioi han viec VE, khong gioi han viec DO.
    #
    #   Truoc day mot con so cat ca hai: anh thu 121 tro di khong duoc ve VA
    #   khong duoc do, nen dong cua no trong gu.csv trong tron boi canh. Buoi
    #   1308 co 187 anh sua -> 67 dong cuoi khong co so lieu gi, ma khong co
    #   dong nao noi vi sao.
    #
    #   Do la thu Agent can nhat; ve chi de nguoi xem. Nen tach hai gioi han.
    #]]
    ap.add_argument("--toi-da", type=int, default=400,
                    help="Ve toi da bay nhieu anh (md: 400). Do sang thi luon "
                         "do het, khong bi gioi han nay.")
    a = ap.parse_args(argv)

    here = dd.goc_du_lieu()
    buoi = ntpath.basename(str(a.folder).rstrip("\\/")) or str(a.folder)

    exp_p = a.export or at.latest_catalog_export(at.LR_JOB_DIR)
    if not exp_p or not Path(exp_p).is_file():
        print("Khong thay export_*.tsv nao.\n"
              "Trong Lightroom: Library -> Plug-in Extras ->\n"
              '  "AutoTone: xuat thong so cho autotone"\n'
              "Phai chay SAU khi da sua tay xong.")
        return 1
    export = doc_tsv(Path(exp_p))

    #[[ Gop MOI job da ap, moi de cu — nhung BO job khoi phuc.
    #
    #   Job khoi phuc chinh la de dua lai gia tri NGUOI DUNG chon. Coi no la
    #   "tool da ghi" thi 192 anh do bong nhien thanh "tool va nguoi dung trung
    #   nhau" — mat sach tin hieu quy nhat ma ta dang di tim.
    #]]
    applied: dict = {}
    jobs = [p for p in sorted(at.LR_JOB_DIR.glob(f"apply_*_{buoi}.done"),
                              key=lambda p: p.stat().st_mtime)
            if "khoiphuc" not in p.name.lower()]
    for jp in jobs:
        applied.update(doc_tsv(jp))
    if not applied:
        print(f"Khong co job apply_*_{buoi}.done nao trong {at.LR_JOB_DIR}.\n"
              "Nghia la tool chua tung ghi cho buoi nay — chua co gi de so.")
        return 1

    #[[ BAN XUAT CU HON LAN GHI CUOI = doc nham catalog cua qua khu.
    #
    #   Ta so "catalog hien tai" voi "tool da ghi gi". Neu ban xuat duoc tao
    #   TRUOC lan tool ghi gan nhat thi no khong phai catalog hien tai — no la
    #   anh chup mot thoi diem da qua. Ket qua van ra mot danh sach trong nhu
    #   that, chi la sai: no liet ke nhung cho tool vua doi, chu khong phai
    #   nhung cho nguoi dung sua.
    #
    #   Gap thuc: sau khi khoi phuc 192 anh ngay 1/9, ban xuat moi nhat van la
    #   ban 15:37 — cu hon ca hai lan ghi sau do.
    #]]
    if jobs and Path(exp_p).stat().st_mtime < jobs[-1].stat().st_mtime:
        print(f"\n  [!] {Path(exp_p).name} duoc tao TRUOC {jobs[-1].name}.")
        print("      Ban xuat nay khong phai catalog hien tai, danh sach se sai.")
        print("      Trong Lightroom chay 'AutoTone: xuat thong so' roi chay lai,")
        print("      hoac dung nut \"Vi sao toi sua\" trong giao dien (no tu lam "
              "buoc do).")

    bc_p = a.bao_cao or tim_bao_cao(a.folder, here)
    ctx = doc_bao_cao(Path(bc_p)) if bc_p else {}
    print(f"Buoi        : {buoi}")
    print(f"Ban xuat    : {Path(exp_p).name}  ({len(export)} anh)")
    print(f"Job da ap   : {len(jobs)} file, gop lai {len(applied)} anh")
    print(f"Bao cao     : {Path(bc_p).name if bc_p else 'KHONG CO — se thieu boi canh'}"
          f"  ({len(ctx)} anh)")
    if not ctx:
        print("  [!] Thieu autotone*.csv thi moi dong se khong co metered_ev,")
        print("      chay sang, so mat... Agent gan nhu khong ket luan duoc gi.")
        print("      Bam 'Luu CSV' trong giao dien roi chay lai.")

    sua = []
    for k, cur in export.items():
        job = applied.get(k)
        if not job:
            continue
        t, u = so(job.get("Exposure2012")), so(cur.get("Exposure2012"))
        if t is None or u is None or abs(u - t) < NGUONG_SUA_EV:
            continue
        sua.append((k, t, u))
    sua.sort(key=lambda x: -abs(x[2] - x[1]))
    print(f"\nAnh anh da sua tay: {len(sua)}"
          f"  (nguong {NGUONG_SUA_EV} EV, duoi do coi la lam tron)")
    if not sua:
        print("Khong co gi de hoc lan nay.")
        return 0

    ra = Path(a.ra) if a.ra else (here / "gu" / buoi)
    ra.mkdir(parents=True, exist_ok=True)

    #[[ GIU LAI CONG GAN LY DO KHI CHAY LAI.
    #
    #   Chay lai la chuyen binh thuong: bo sung boi canh, doi ban xuat moi hon,
    #   hoac sau khi sua mot loi trong chinh file nay. Nhung ly_do va giai_thich
    #   la thu NGUOI DUNG go tay, co khi ca tieng dong ho — ghi de len chung la
    #   mat trang, va mat mot cach im lang: file van day du cot, chi la trong.
    #
    #   Ghep theo TEN ANH chu khong theo so thu tu: so thu tu sap theo do lech
    #   nen doi moi lan chay.
    #]]
    cu = {}
    f_cu = ra / "gu.csv"
    if f_cu.is_file():
        try:
            with io.open(f_cu, encoding="utf-8-sig", newline="") as fh:
                for r in csv.DictReader(fh):
                    ly = (r.get("ly_do") or "").strip()
                    gt = (r.get("giai_thich") or "").strip()
                    if ly or gt:
                        cu[ten(r.get("file", ""))] = (ly, gt)
        except OSError:
            pass
        if cu:
            print(f"Giu lai ly do da gan: {len(cu)} anh")

    #[[ Lap chi muc file RAW MOT LAN, khoa la ten khong duoi da ha chu thuong.
    #   Truoc do doan ten bang cach ghep duoi hoa/thuong roi thu is_file() —
    #   chay duoc tren Windows (khong phan biet hoa thuong) nhung sai tren may
    #   khac, va sai kieu im lang: khong tim thay anh thi cot khung bo trong,
    #   nhin cu tuong anh do khong co mat nao.
    #]]
    kho_raw = {p.stem.strip().lower(): p for p in a.folder.iterdir()
               if p.suffix.lower() in at.RAW_EXTS}

    cfg = dict(at.DEFAULTS)
    cells, rows = [], []
    ve = not a.khong_ve
    for i, (k, t, u) in enumerate(sua, 1):
        c = ctx.get(k, {})
        raw = kho_raw.get(k)
        m = {}
        if ve and raw:
            try:
                m = do_lai(raw, cfg)
            except Exception as ex:                       # noqa: BLE001
                print(f"  [!] {k}: {type(ex).__name__}: {ex}")
                m = {}
        sub = m.get("subject_box")

        #[[ Do sang CA KHUNG, quy ve cung thang EV voi phep do mat.
        #
        #   Day la con so nguoi dung dang mo ta ma chua ai do: "background dang
        #   sang hon nen can giam sang", "tong the buc hinh nhieu mau trang nen
        #   bi day len sang chay". Tool keo MAT ve dich va khong nhin gi khac,
        #   nen khung nao von da sang thi bi day sang them.
        #
        #   mat_hon_khung_ev am = mat TOI hon phan con lai cua khung, tuc keo
        #   mat len dich se lam ca khung sang qua. Do chinh la nhom "sang-qua".
        #]]
        p50 = so(m.get("p50")) if m else None
        khung_ev = (float(np.log2(p50 + 1e-9)) if p50 and p50 > 0 else None)
        mat_ev = so(m.get("metered_face_ev")) if m else None
        hon = (mat_ev - khung_ev) if (mat_ev is not None and khung_ev is not None) else None

        def _s(v, n=3):
            return "" if v is None else f"{float(v):.{n}f}"

        rows.append({
            "so": i, "file": k, "ly_do": "", "giai_thich": "",
            "tool_exposure": f"{t:.2f}", "user_exposure": f"{u:.2f}",
            "sua_bao_nhieu": f"{u - t:+.2f}",
            # --- do ngay tai cho, luon co neu doc duoc file RAW
            "metered_ev": _s(m.get("metered_ev")) if m else c.get("metered_ev", ""),
            "mat_ev": _s(mat_ev),
            "chu_the_ev": _s(m.get("metered_subject_ev")) if m else "",
            "khung_ev": _s(khung_ev),
            "mat_hon_khung_ev": _s(hon),
            "vung_bao_hoa": _s(m.get("sat_frac"), 4) if m else "",
            "vung_sang": _s(m.get("bright_frac"), 4) if m else "",
            "vung_bet": _s(m.get("crush_frac"), 4) if m else "",
            "faces_n": (m.get("faces_n") if m else c.get("faces_n", "")),
            "faces_found": (m.get("faces_found") if m else c.get("faces_found", "")),
            # --- chi co khi co bao cao autotone*.csv
            "target_ev": c.get("target_ev", ""),
            "clip_before": c.get("clip_before_pct", ""),
            "clip_after": c.get("clip_after_pct", ""),
            "scene": c.get("scene", ""), "scene_size": c.get("scene_size", ""),
            "khung_tong": len(m.get("all_boxes") or []) if m else "",
            "khung_do_sang": len(m.get("meter_boxes") or []) if m else "",
            "nguon_do": ("mat" if m.get("metered_face_ev") is not None else
                         "vung-bat-net" if m.get("metered_focus_ev") is not None
                         else "ca-khung") if m else "",
            "diem_chu_the": f"{sub[4]:.2f}" if sub else "",
            "iso": (m.get("iso") if m else c.get("iso", "")) or "",
            "notes": c.get("notes", ""),
            "anh": "", "anh_le": "",
        })
        if ve and raw and m.get("ok") and len(cells) < a.toi_da:
            # ve thi co gioi han, do thi khong — xem chu thich o --toi-da
            im = preview(raw, cfg["face_px"])
            if im is not None:
                khung = ve_khung(im, m)
                cells.append({"so": i, "ten": k, "im": khung,
                              # ve_tam() goi thumbnail() lam nho anh TAI CHO;
                              # giu mot ban rieng cho cua so xem tung tam.
                              "le": khung.copy(),
                              "tool": t, "user": u, "diff": u - t,
                              "khung_tong": len(m.get("all_boxes") or []),
                              "khung_do": len(m.get("meter_boxes") or []),
                              "clip": (f"{so(c.get('clip_before_pct')):.1f}%"
                                       if so(c.get("clip_before_pct")) is not None
                                       else "?")})
        if i % 20 == 0:
            print(f"  {i}/{len(sua)}")

    if cu:
        n_giu = 0
        for r in rows:
            g = cu.get(r["file"])
            if g:
                r["ly_do"], r["giai_thich"] = g
                n_giu += 1
        mat = sorted(set(cu) - {r["file"] for r in rows})
        print(f"Da gan lai ly do cho {n_giu}/{len(cu)} anh")
        if mat:
            #[[ Anh co ly do nhung khong con trong danh sach = ban xuat doi.
            #   Bao ten ra, dung im lang: do la cong nguoi dung da bo ra.
            #]]
            print(f"  [!] {len(mat)} anh co ly do nhung khong con trong danh sach "
                  f"lan nay: {', '.join(mat[:8])}{' ...' if len(mat) > 8 else ''}")
            print("      (ban xuat lan nay khac lan truoc — ly do cua chung nam "
                  "trong gu.csv.cu)")
            try:
                (ra / "gu.csv").replace(ra / "gu.csv.cu")
            except OSError:
                pass

    tam = ve_tam(cells, ra, buoi) if cells else []
    for k, c in enumerate(cells):
        rows[c["so"] - 1]["anh"] = tam[k // MOI_TAM].name

    #[[ Luu THEM tung anh rieng, ngoai cac tam gop.
    #
    #   Hai cach xem phuc vu hai viec khac nhau va deu can:
    #     tam gop  — luot nhanh ca buoi, va la thu dua duoc cho Claude xem
    #     anh le   — cua so "Vi sao toi sua" hien tung tam mot de bam ly do
    #   Dung tam gop cho cua so thi phai cat anh ra lai, va toa do se lech.
    #]]
    o = ra / "o"
    o.mkdir(exist_ok=True)
    for c in cells:
        c["le"].save(o / f"{c['so']:04d}.jpg", quality=88)
        rows[c["so"] - 1]["anh_le"] = f"o/{c['so']:04d}.jpg"

    dest = ra / "gu.csv"
    with io.open(dest, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COT)
        w.writeheader()
        w.writerows(rows)

    (ra / "boi_canh.json").write_text(json.dumps({
        "buoi": buoi,
        "thu_muc_anh": str(a.folder),
        "khi": datetime.now().isoformat(timespec="seconds"),
        "ban_xuat": Path(exp_p).name,
        "bao_cao": Path(bc_p).name if bc_p else None,
        "so_anh_trong_job": len(applied),
        "so_anh_da_sua": len(sua),
        "nguong_sua_ev": NGUONG_SUA_EV,
        "gu_dang_chay": at.mo_ta_gu(),
        "tham_so_hien_tai": {k: at.DEFAULTS[k] for k in (
            "face_target_ev", "max_ev", "max_ev_up", "exposure_gain",
            "big_low_ratio", "big_low_gap", "big_low_floor",
            "scene_level", "scene_aim_slack_ev", "scene_level_extra_ev",
            "hl_subject_floor_ev", "hl_heavy_clip_pct", "hl_hard_pct",
            "hl_trigger_pct", "hl_gain", "hl_max",
            "face_min_ratio", "subject_keep", "subject_dark_ev")
            if k in at.DEFAULTS},
        "ly_do": [{"ma": m, "nghia": ng, "tham_so_lien_quan": ts}
                  for m, ng, ts in LY_DO],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n-> {dest}")
    for f in tam:
        print(f"-> {f.name}")
    print(f"-> boi_canh.json")
    print("\nBuoc tiep: gan ly do cho tung anh.")
    print("  - trong giao dien: nut \"Vi sao toi sua\"")
    print(f"  - hoac dua ca thu muc {ra} cho Claude")
    return 0


if __name__ == "__main__":
    sys.exit(main())
