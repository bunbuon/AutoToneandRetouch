#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""do_ranh_canh.py — Ranh giới cảnh đặt đúng chỗ chưa?

    python do_ranh_canh.py autotone20260903_1010.csv
    python do_ranh_canh.py cu.csv moi.csv        # so hai lần chạy

CHỈ SỐ CHÍNH — VÀ VÌ SAO LÀ NÓ
    Ở mỗi ranh giới do BỐI CẢNH, lấy hai khung cuối của cảnh trước rồi xem
    chúng gần trung vị cảnh nào hơn.

    Nếu ranh giới đặt đúng, hai khung đó thuộc cảnh trước, nên tỉ lệ "gần cảnh
    sau hơn" phải quanh 50% — mức ngẫu nhiên. Càng cao hơn 50% thì càng nhiều
    khung bị bỏ nhầm lại cảnh cũ.

    Đo thật ngày 3/9 trên buổi 1308, bản CHƯA sửa: 75/96 = 78% theo đúng bộ
    lọc của file này. (Một phép đo chặt hơn — chỉ lấy cảnh sau có từ 5 ảnh —
    cho 40/46 = 87%. Hai con số cùng nói một chuyện; file này là định nghĩa
    chính thức từ giờ, vì nó chạy lại được.)

    Đây là chỉ số ĐỘC LẬP với bản sửa: nó không hỏi "code có chạy đúng ý không"
    mà hỏi "mấy tấm ảnh đó có nằm đúng cảnh không". Bản sửa có thể đúng ý mà
    vẫn sai chỗ — nếu lùi 2 khung là chưa đủ.

CỔNG NGHIỆM THU (đặt TRƯỚC khi chạy, 3/9)
    1. Tỉ lệ trên phải về khoảng 50%  (đạt: ≤ 60%)
    2. Số cảnh không đổi quá ±5%
    Không đạt thì bỏ bản sửa và ghi lại vì sao, không nới cổng.

BỎ QUA NHỮNG RANH GIỚI KHÔNG KẾT LUẬN ĐƯỢC
    Hai cảnh sáng như nhau (<0.25 EV) thì "gần cảnh nào hơn" là tung đồng xu —
    tính vào chỉ giống thêm nhiễu. Ngưỡng này chọn TRƯỚC khi nhìn số.
"""
from __future__ import annotations

import argparse
import csv
import statistics as st
import sys
from datetime import datetime
from pathlib import Path

NGUONG_LECH_EV = 0.25       # dưới mức này thì không kết luận được
SO_KHUNG = 2                # sig_min_shots (3) trừ 1
DAT_TI_LE = 60.0            # %
DAT_LECH_CANH = 5.0         # %


def nap(fp: Path) -> list:
    out = []
    with open(fp, encoding="utf-8-sig", newline="") as fh:
        for x in csv.DictReader(fh):
            d = (x.get("dt") or "").strip()
            try:
                x["t"] = datetime.fromisoformat(d)
            except ValueError:
                continue
            try:
                x["s"] = int(x["scene"])
                x["ev"] = float(x["metered_ev"] or 0)
            except (TypeError, ValueError):
                continue
            out.append(x)
    return sorted(out, key=lambda z: z["t"])


def ranh_gioi(r: list) -> list:
    """[(chỉ số khung đầu cảnh mới, 'gio'|'boi-canh'|'?')]"""
    ra = []
    for i in range(1, len(r)):
        if r[i]["s"] == r[i - 1]["s"]:
            continue
        vi = (r[i].get("scene_cut") or "").strip()
        if not vi:
            #[[ Bao cao cu khong co cot scene_cut. Doan lai bang khoang thoi
            #   gian: cach > 5 phut thi gan nhu chac chan la luat thoi gian.
            #   Chi la PHONG DOAN — danh dau '?' de bao cao noi ro.
            #]]
            vi = "gio" if (r[i]["t"] - r[i - 1]["t"]).total_seconds() > 300 else "?"
        ra.append((i, vi))
    return ra


def do(r: list, ten: str) -> dict:
    canh: dict = {}
    for x in r:
        canh.setdefault(x["s"], []).append(x)
    rg = ranh_gioi(r)
    xet = lac = bo_qua = 0
    vd = []
    for i, vi in rg:
        if vi == "gio":
            continue
        A, B = canh[r[i - 1]["s"]], canh[r[i]["s"]]
        if len(A) < SO_KHUNG + 3 or len(B) < 3:
            bo_qua += 1
            continue
        mA = st.median([x["ev"] for x in A[:-SO_KHUNG]])
        mB = st.median([x["ev"] for x in B])
        if abs(mA - mB) < NGUONG_LECH_EV:
            bo_qua += 1
            continue
        for x in A[-SO_KHUNG:]:
            xet += 1
            if abs(x["ev"] - mB) < abs(x["ev"] - mA):
                lac += 1
                if len(vd) < 4:
                    vd.append((Path(x["path"]).name, x["ev"], mA, mB))
    ti = 100.0 * lac / xet if xet else 0.0

    print(f"\n{'=' * 68}\n{ten}   {len(r)} ảnh, {len(canh)} cảnh")
    n_gio = sum(1 for _i, v in rg if v == "gio")
    n_bc = sum(1 for _i, v in rg if v == "boi-canh")
    n_ko = sum(1 for _i, v in rg if v == "?")
    print(f"  ranh giới: {len(rg)}   giờ {n_gio}   bối cảnh {n_bc}"
          + (f"   chưa rõ {n_ko} (báo cáo cũ, phỏng đoán)" if n_ko else ""))
    print(f"  {SO_KHUNG} khung cuối trước ranh giới bối cảnh:")
    print(f"     xét {xet}, nằm gần cảnh SAU hơn: {lac}  →  {ti:.0f}%"
          f"   (ngẫu nhiên 50%, chưa sửa 78%)")
    if bo_qua:
        print(f"     bỏ qua {bo_qua} ranh giới (cảnh quá ngắn, hoặc hai bên "
              f"sáng chênh < {NGUONG_LECH_EV} EV nên không kết luận được)")
    for p, ev, mA, mB in vd:
        print(f"       {p}  ev {ev:+.2f} | cảnh trước {mA:+.2f} → cảnh sau {mB:+.2f}")

    #[[ Cau hoi con treo: nhat cat theo GIO co duoc boi canh dong y khong?
    #   Chi tra loi duoc khi bao cao co cot scene_sig_lech.
    #]]
    lech = [(i, float(r[i]["scene_sig_lech"]))
            for i, v in rg if v == "gio" and (r[i].get("scene_sig_lech") or "") != ""]
    if lech:
        nho = [x for x in lech if x[1] <= 0.30]
        print(f"  nhát cắt theo giờ có số liệu chữ ký: {len(lech)}/{n_gio}")
        print(f"     bối cảnh KHÔNG đổi (lệch ≤ 0.30): {len(nho)}  "
              f"← đây là những nhát mà luật 'giờ phải được bối cảnh đồng ý' sẽ bỏ")
    elif n_gio:
        print("  (báo cáo chưa có cột scene_sig_lech — chưa trả lời được câu "
              "'bối cảnh có đồng ý với nhát cắt theo giờ không')")

    #[[ Nhung khoang nghi da bi PHU QUYET vi khung hinh khong doi. Chung khong
    #   con la ranh gioi nua nen khong hien o dong tren — phai dem rieng, neu
    #   khong thi mot thay doi hanh vi lon lai khong de lai dau vet nao trong
    #   bao cao.
    #]]
    bo_qua_gio = [x for x in r if x.get("scene_cut") == "gio-bo-vi-cung-phong"]
    if bo_qua_gio:
        print(f"  khoảng nghỉ bị BỎ QUA vì khung hình không đổi: "
              f"{len(bo_qua_gio)}  (check-in cùng một phông)")
    return {"ti_le": ti, "xet": xet, "canh": len(canh), "anh": len(r)}


def go_ra(ds: list) -> list:
    """Đưa vào thư mục buổi chụp cũng được — tự tìm hai báo cáo mới nhất.

    VÌ SAO
        Bắt người dùng gõ hai đường dẫn CSV đầy đủ là mời gõ sai, mà báo cáo
        nằm trong thư mục buổi chụp giữa hàng nghìn file .ARW nên tìm ra tên nó
        đã mất công rồi. Thư mục thì gõ một lần là xong, và tên báo cáo có sẵn
        mốc thời gian nên "hai cái mới nhất" gần như luôn đúng ý.
    """
    ra = []
    for p in ds:
        if p.is_dir():
            cs = sorted(p.glob("autotone*.csv"), key=lambda x: x.stat().st_mtime)
            if not cs:
                print(f"  [!] {p} không có file autotone*.csv nào")
                continue
            lay = cs[-2:]
            print(f"  Trong {p}: lấy {len(lay)} báo cáo mới nhất — "
                  + ", ".join(x.name for x in lay))
            ra += lay
        else:
            ra.append(p)
    return ra


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Ranh gioi canh dat dung cho chua.",
        epilog="Dua vao mot THU MUC buoi chup cung duoc — tu lay hai bao cao "
               "autotone*.csv moi nhat trong do.")
    ap.add_argument("csv", type=Path, nargs="+",
                    help="Bao cao autotone*.csv, hoac thu muc buoi chup")
    a = ap.parse_args(argv)

    kq = []
    for fp in go_ra(a.csv):
        if not fp.is_file():
            print(f"\n  [!] Không có file: {fp}")
            continue
        r = nap(fp)
        if len(r) < 20:
            print(f"\n{fp.name}: chỉ {len(r)} dòng đọc được — bỏ qua")
            continue
        kq.append((fp.name, do(r, fp.name)))

    if len(kq) == 2:
        (t0, a0), (t1, a1) = kq
        #[[ Chi so sanh duoc CUNG MOT BUOI truoc/sau khi sua. So hai buoi khac
        #   nhau thi moi con so deu doi vi ly do khong lien quan gi toi ban sua,
        #   va cong nghiem thu tro thanh vo nghia — de im thi rat de doc nham.
        #]]
        n0, n1 = a0.get("anh", 0), a1.get("anh", 0)
        if n0 and abs(n1 - n0) > 0.1 * n0:
            print(f"\n  [!] Hai file lech nhau {n0} vs {n1} anh — nhieu kha nang "
                  f"KHONG phai cung mot buoi. Cong nghiem thu duoi day vo nghia; "
                  f"chay lai dung mot buoi truoc va sau khi sua.")
        #[[ NOI RO cai nao la CU, cai nao la MOI.
        #   Thu tu lay theo mtime. Chep file quanh o dia la mtime doi, va luc do
        #   cong doc NGUOC ma van in ra mot ket luan tron tru — kieu sai te nhat
        #   vi no khong trong giong sai. Ten bao cao co san moc thoi gian, nen
        #   chi can bay ra la nguoi doc thay ngay.
        #]]
        print(f"\n{'=' * 68}\nCỔNG NGHIỆM THU")
        print(f"  coi {t0}  là bản CŨ")
        print(f"  coi {t1}  là bản MỚI   (nếu ngược thì đảo lại hai đường dẫn)")
        d_canh = 100.0 * abs(a1["canh"] - a0["canh"]) / max(a0["canh"], 1)
        c1 = a1["ti_le"] <= DAT_TI_LE
        c2 = d_canh <= DAT_LECH_CANH
        print(f"  1. tỉ lệ khung nằm nhầm cảnh: {a0['ti_le']:.0f}% → "
              f"{a1['ti_le']:.0f}%   (đạt nếu ≤ {DAT_TI_LE:.0f}%)   "
              f"{'ĐẠT' if c1 else 'KHÔNG ĐẠT'}")
        print(f"  2. số cảnh: {a0['canh']} → {a1['canh']}  (lệch {d_canh:.1f}%, "
              f"đạt nếu ≤ {DAT_LECH_CANH:.0f}%)   {'ĐẠT' if c2 else 'KHÔNG ĐẠT'}")
        print(f"\n  => {'ĐẠT CẢ HAI CỔNG' if c1 and c2 else 'KHÔNG ĐẠT — bỏ bản sửa, ghi lại vì sao'}")
        return 0 if (c1 and c2) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
