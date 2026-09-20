#!/usr/bin/env python3
"""Khôi phục những ảnh người dùng đã sửa tay rồi bị lần chạy sau ghi đè.

CHUYỆN ĐÃ XẢY RA
    31/8 lúc 16:18 tool áp thông số lần đầu (apply_20260831_161838_1308.done).
    Sau đó người dùng ngồi sửa tay 192 ảnh trong Lightroom.
    1/9 lúc 15:37 plugin xuất catalog ra export_20260901_153751.tsv — file này
    còn NGUYÊN 192 chỉnh sửa đó.
    1/9 lúc 15:39, 88 giây sau, nút "Chạy hết" áp một lượt mới và ghi đè lên.

    Cơ chế "bỏ qua ảnh đã sửa tay" chỉ vừa được thêm vào SAU sự cố này, nên nó
    không cứu được lượt đó. File export 15:37 là bản sao duy nhất còn lại của
    những gì người dùng đã chỉnh.

CÁCH TÌM RA ĐÚNG 192 ẢNH
    ghi_hong  = apply_*_<thư mục>.done mới nhất          (lượt ghi đè)
    ban_tot   = export_*.tsv mới nhất CŨ HƠN ghi_hong    (catalog trước khi đè)
    ghi_truoc = apply_*_<thư mục>.done mới nhất cũ hơn ban_tot

    Ảnh cần khôi phục = ảnh mà ban_tot KHÁC ghi_truoc.

    VÌ SAO KHÔNG LẤY TẤT CẢ ẢNH KHÁC GIỮA ban_tot VÀ ghi_hong: hiệu đó là 194
    ảnh, nhưng 2 trong số đó không phải người dùng sửa — chúng đổi vì luật "bỏ
    khung to mà điểm thấp" vừa bật. Khôi phục nhầm 2 ảnh này thì lần chạy sau
    tool sẽ mãi mãi coi chúng là "người dùng đã sửa" và không bao giờ dám tính
    lại — một vết bẩn vĩnh viễn trong dữ liệu.

CÁI BẪY ĐẶT TÊN FILE — ĐỌC TRƯỚC KHI ĐỔI TÊN
    Plugin chỉ nhận file "apply_*.tsv" (AutoToneCore.lua, M.pendingJobs) rồi
    đổi đuôi thành .done. Còn autotone.last_applied() lại tìm theo mẫu
    "apply_*_<thư mục>.done" để biết lần trước tool ghi gì.

    Nếu job khôi phục này tên là apply_..._1308.tsv thì sau khi áp xong nó
    thành apply_..._1308.done và trở thành "lần ghi gần nhất". Lúc đó catalog
    sẽ TRÙNG với lần ghi gần nhất, nên 192 ảnh vừa cứu về sẽ KHÔNG còn bị coi
    là sửa tay nữa — và lần chạy kế tiếp sẽ đè lên chúng lần thứ hai.

    Nên tên phải là  apply_<mốc>_<thư mục>-khoiphuc.tsv : vẫn lọt qua bộ lọc
    của plugin, nhưng không khớp mẫu của last_applied(). last_applied() cũng
    đã được thêm một câu chặn riêng cho chữ "khoiphuc" để chắc hai lớp.

CÁCH DÙNG
    python khoi_phuc.py G:\\1308            xem trước, KHÔNG ghi gì
    python khoi_phuc.py G:\\1308 --ghi      ghi job cho plugin áp

    Sau khi ghi: mở Lightroom, plugin tự nhặt job trong vòng vài giây.
"""
from __future__ import annotations

import argparse
import csv
import io
import ntpath
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at   # noqa: E402

# Chỉ năm cột này là thứ người dùng sửa được trong bảng Basic và plugin xuất ra
# được. Các cột còn lại của LR_JOB_FIELDS để TRỐNG — ô trống nghĩa là "không
# đụng tới" (AutoToneCore.lua dòng 101: val ~= "" mới ghi).
COT_PHUC = ["Exposure2012", "Highlights2012", "Shadows2012", "Temperature", "Tint"]


def ten(p) -> str:
    return ntpath.splitext(ntpath.basename(str(p)))[0].strip().lower()


def doc(p: Path) -> dict:
    with io.open(p, encoding="utf-8-sig", newline="") as fh:
        return {ten(r["path"]): r for r in csv.DictReader(fh, delimiter="\t")}


def so(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def tim_bo_ba(job_dir: Path, folder: Path):
    """Trả về (ghi_hong, ban_tot, ghi_truoc) — hoặc None kèm lý do."""
    #[[ ntpath chu khong phai Path: duong dan Windows "G:\\1308" chay tren Linux
    #   thi Path().name tra ve nguyen ca chuoi. Cung cai bay da lam _stem_any()
    #   ra doi trong autotone.py.
    #]]
    thu_muc = ntpath.basename(str(folder).rstrip("\\/")) or str(folder)
    applies = sorted(job_dir.glob(f"apply_*_{thu_muc}.done"),
                     key=lambda p: p.stat().st_mtime)
    applies = [p for p in applies if "khoiphuc" not in p.name.lower()]
    if not applies:
        return None, f"Khong thay apply_*_{thu_muc}.done nao trong {job_dir}"
    ghi_hong = applies[-1]
    t_hong = ghi_hong.stat().st_mtime

    exports = sorted((p for p in job_dir.glob("export_*.tsv")
                      if p.stat().st_mtime < t_hong),
                     key=lambda p: p.stat().st_mtime)
    if not exports:
        return None, "Khong thay file export_*.tsv nao cu hon lan ghi de"
    ban_tot = exports[-1]
    t_tot = ban_tot.stat().st_mtime

    truoc = [p for p in applies if p.stat().st_mtime < t_tot]
    if not truoc:
        return None, "Khong thay lan ghi nao cu hon file export"
    return (ghi_hong, ban_tot, truoc[-1]), ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Khoi phuc anh nguoi dung sua tay bi ghi de.")
    ap.add_argument("folder", type=Path)
    ap.add_argument("--ghi", action="store_true",
                    help="Ghi job that. Khong co co nay thi chi xem truoc.")
    ap.add_argument("--dung-sai", type=float, default=0.005,
                    help="Lech Exposure qua bay nhieu thi coi la nguoi dung sua (md: 0.005)")
    ap.add_argument("--jobs-dir", type=Path, default=None)
    a = ap.parse_args(argv)

    job_dir = Path(a.jobs_dir or at.LR_JOB_DIR)
    bo_ba, ly_do = tim_bo_ba(job_dir, a.folder)
    if bo_ba is None:
        print(ly_do)
        return 1
    ghi_hong, ban_tot, ghi_truoc = bo_ba

    def gio(p):
        return datetime.fromtimestamp(p.stat().st_mtime).strftime("%d/%m %H:%M")

    print(f"Thu muc job : {job_dir}")
    print(f"  ghi truoc : {ghi_truoc.name:<42} {gio(ghi_truoc)}   (tool ghi, truoc khi nguoi dung sua)")
    print(f"  ban tot    : {ban_tot.name:<42} {gio(ban_tot)}   (catalog CON NGUYEN chinh sua)")
    print(f"  ghi hong   : {ghi_hong.name:<42} {gio(ghi_hong)}   (lan ghi de)\n")

    tot = doc(ban_tot)
    truoc = doc(ghi_truoc)
    hong = doc(ghi_hong)

    can_phuc, chi_luat = [], []
    for k, r in tot.items():
        p = truoc.get(k)
        h = hong.get(k)
        if not p or not h:
            continue
        e_tot, e_truoc, e_hong = so(r.get("Exposure2012")), so(p.get("Exposure2012")), so(h.get("Exposure2012"))
        if None in (e_tot, e_truoc, e_hong):
            continue
        if abs(e_tot - e_hong) <= a.dung_sai:
            continue                      # khong bi doi -> khong can lam gi
        if abs(e_tot - e_truoc) > a.dung_sai:
            can_phuc.append((k, r, e_truoc, e_tot, e_hong))
        else:
            chi_luat.append((k, e_tot, e_hong))

    print(f"Bi ghi de           : {len(can_phuc) + len(chi_luat)} anh")
    print(f"  nguoi dung sua tay: {len(can_phuc)} anh  -> KHOI PHUC")
    print(f"  do luat moi doi   : {len(chi_luat)} anh  -> de nguyen, khong dung toi")
    if chi_luat:
        for k, e_tot, e_hong in chi_luat[:6]:
            print(f"      {k:<12} {e_tot:+.2f} -> {e_hong:+.2f}")
    if not can_phuc:
        print("\nKhong co gi de khoi phuc.")
        return 0

    print("\n12 anh dau se duoc tra lai:")
    for k, _r, e_truoc, e_tot, e_hong in can_phuc[:12]:
        print(f"   {k:<12} tool {e_truoc:+.2f} | nguoi dung {e_tot:+.2f} | dang bi {e_hong:+.2f}")

    thu_muc = ntpath.basename(str(a.folder).rstrip("\\/")) or str(a.folder)
    dest = job_dir / f"apply_{datetime.now():%Y%m%d_%H%M%S}_{thu_muc}-khoiphuc.tsv"
    lines = ["path\t" + "\t".join(at.LR_JOB_FIELDS)]
    for _k, r, _a1, _a2, _a3 in can_phuc:
        o = [r["path"]]
        for c in at.LR_JOB_FIELDS:
            v = r.get(c) if c in COT_PHUC else ""
            o.append("" if v is None else str(v).strip())
        lines.append("\t".join(o))

    if not a.ghi:
        #[[ In NGUYEN CA DONG LENH, khong phai moi cai co.
        #   Ban truoc chi ghi "chay lai voi --ghi" va nguoi dung go dung hai chu
        #   do vao PowerShell -> shell hieu "--" la toan tu tru va bao loi cu
        #   phap. Cai gi copy-paste duoc thi in ra day du.
        #]]
        print(f"\nXEM TRUOC — chua ghi gi. Muon ghi that thi go NGUYEN dong nay:")
        print(f"   python khoi_phuc.py {a.folder} --ghi")
        print(f"   -> se tao {dest.name}")
        return 0

    # .part roi doi ten: plugin khong bao gio doc phai file dang ghi do
    tmp = dest.with_suffix(".part")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, dest)
    print(f"\nDa ghi job: {dest.name}")
    print(f"  {len(can_phuc)} anh, chi ghi 5 cot: {', '.join(COT_PHUC)}")
    print("  Mo Lightroom — plugin se tu nhat job trong vai giay.")
    print("  Ten file co chu 'khoiphuc' nen last_applied() se bo qua no, va lan")
    print("  chay sau van nhan ra 192 anh nay la nguoi dung sua -> khong de len.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
