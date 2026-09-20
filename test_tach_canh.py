#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kiểm hai luật tách cảnh — gọi thẳng group_scenes() thật, không dựng lại.

BỐN TỔ HỢP, VÀ MỘT CÁI BẪY
    Luật thời gian giờ tắt được bằng gap_minutes <= 0. Cái bẫy: timedelta(0)
    nghĩa là "cách nhau hơn 0 giây là cảnh mới" — tức MỖI ẢNH một cảnh, gần
    như đúng ngược lại với ý định. Nó không sập, không báo gì, chỉ ra 1464 cảnh
    thay vì 132 rồi mọi phép trung vị theo cảnh mất nghĩa. Bài này canh đúng
    chỗ đó.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at   # noqa: E402

T0 = datetime(2026, 8, 13, 13, 0, 0)


def anh(giay, sig=None):
    r = {"dt_obj": T0 + timedelta(seconds=giay)}
    if sig is not None:
        r["scene_sig"] = [float(sig)] * 4
    return r


def canh(ds):
    return [r["scene"] for r in ds]


def main() -> int:
    loi = []

    #[[ Bo anh mau: 4 khung cach nhau 3 giay (mot loat), NGHI 10 PHUT, roi 4
    #   khung nua. Boi canh doi dung o cho nghi.
    #]]
    def bo():
        return ([anh(i * 3, 0.10) for i in range(4)]
                + [anh(600 + i * 3, 0.90) for i in range(4)])

    # 1 — chỉ thời gian
    ds = bo()
    at.group_scenes(ds, 5.0, 0.0)
    if canh(ds) != [0, 0, 0, 0, 1, 1, 1, 1]:
        loi.append(f"Chi thoi gian: {canh(ds)}, dang le 0000 1111")

    # 2 — chỉ bối cảnh (nghỉ 10 phút KHÔNG được tách)
    ds = bo()
    at.group_scenes(ds, 0.0, 0.30, sig_min_shots=3)
    c = canh(ds)
    if c[0] != 0 or len(set(c)) != 2:
        loi.append(f"Chi boi canh: {c}, dang le dung 2 canh")
    if c[3] != 0:
        loi.append(f"Chi boi canh: nghi 10 phut khong duoc tach, {c}")

    # 3 — cả hai
    ds = bo()
    at.group_scenes(ds, 5.0, 0.30)
    if canh(ds) != [0, 0, 0, 0, 1, 1, 1, 1]:
        loi.append(f"Ca hai: {canh(ds)}, dang le 0000 1111")

    #[[ 4 — TAT CA HAI. Day la cai bay: gap_minutes = 0 phai la TAT, khong phai
    #   "cach nhau hon 0 giay la canh moi".
    #]]
    ds = bo()
    at.group_scenes(ds, 0.0, 0.0)
    c = canh(ds)
    if c != [0] * 8:
        loi.append(f"Tat ca hai: {c}, dang le ca buoi mot canh (toan so 0). "
                   f"Neu ra 0..7 thi gap_minutes=0 dang bi hieu la 'moi anh mot "
                   f"canh' — dung cai bay da canh trong group_scenes()")

    # 5 — số âm cũng phải là tắt, không được ném lỗi
    ds = bo()
    try:
        at.group_scenes(ds, -1.0, 0.0)
        if canh(ds) != [0] * 8:
            loi.append(f"gap am: {canh(ds)}, dang le toan 0")
    except Exception as e:                                   # noqa: BLE001
        loi.append(f"gap am nem loi: {type(e).__name__}: {e}")

    # 6 — không có scene_sig thì bật luật bối cảnh cũng vô hại
    ds = [anh(i * 3) for i in range(4)] + [anh(600 + i * 3) for i in range(4)]
    at.group_scenes(ds, 5.0, 0.30)
    if canh(ds) != [0, 0, 0, 0, 1, 1, 1, 1]:
        loi.append(f"Khong co chu ky: {canh(ds)}, dang le van tach theo gio")

    # 7 — một khung lệch đơn lẻ KHÔNG được tách (phải đủ sig_min_shots)
    ds = ([anh(i * 3, 0.10) for i in range(6)]
          + [anh(18, 0.90)]                       # một khung lạ
          + [anh(21 + i * 3, 0.10) for i in range(6)])
    ds.sort(key=lambda r: r["dt_obj"])
    at.group_scenes(ds, 5.0, 0.30, sig_min_shots=3)
    if len(set(canh(ds))) != 1:
        loi.append(f"Mot khung le lam tach canh: {canh(ds)}")

    # 8 — thứ tự: hàm phải sắp xếp theo giờ chụp, id cảnh không lùi
    ds = bo()[::-1]
    at.group_scenes(ds, 5.0, 0.0)
    c = canh(ds)
    if c != sorted(c):
        loi.append(f"Id canh khong tang dan sau khi sap xep: {c}")

    #[[ 9 — RANH GIOI PHAI DAT O KHUNG BAT DAU LECH, khong phai khung xac nhan.
    #
    #   Day la loi da do duoc tren buoi 1308: 40/46 = 87% hai khung cuoi cua
    #   canh cu that ra thuoc canh sau. Bai nay dung mot bo anh KHONG co khoang
    #   nghi (de luat thoi gian khong xen vao): 5 khung boi canh A, roi 5 khung
    #   boi canh B, tat ca cach nhau 3 giay.
    #
    #   Dung: 00000 11111. Sai (ranh gioi muon 2 khung): 0000000 111.
    #]]
    ds = ([anh(i * 3, 0.10) for i in range(5)]
          + [anh(15 + i * 3, 0.90) for i in range(5)])
    at.group_scenes(ds, 0.0, 0.30, sig_min_shots=3)
    c = canh(ds)
    if c != [0] * 5 + [1] * 5:
        loi.append(f"Ranh gioi boi canh dat sai cho: {c}, dang le 00000 11111. "
                   f"Neu ra 0000000 111 thi no van muon 2 khung — dung loi da do "
                   f"duoc 87% tren buoi 1308")

    # 10 — khung mở màn cảnh mới phải được đánh dấu vì sao cắt
    dau = [r for r in ds if r.get("scene_cut")]
    if len(dau) != 1 or dau[0] is not ds[5]:
        loi.append(f"scene_cut danh dau sai khung: "
                   f"{[ds.index(x) for x in dau]}, dang le [5]")
    if dau and dau[0].get("scene_cut") != "boi-canh":
        loi.append(f"scene_cut = {dau[0].get('scene_cut')!r}, dang le 'boi-canh'")

    # 11 — cắt theo giờ thì KHÔNG được lùi ranh giới (khoảng nghỉ chính là bằng chứng)
    ds = bo()
    at.group_scenes(ds, 5.0, 0.30, sig_min_shots=3)
    if canh(ds) != [0, 0, 0, 0, 1, 1, 1, 1]:
        loi.append(f"Cat theo gio ma bi lui ranh gioi: {canh(ds)}")
    if ds[4].get("scene_cut") != "gio":
        loi.append(f"Khung dau canh 2 phai ghi 'gio', duoc {ds[4].get('scene_cut')!r}")

    # 12 — độ lệch chữ ký phải được ghi lại, kể cả ở khung bị cắt theo giờ
    if "scene_sig_lech" not in ds[4]:
        loi.append("Khung cat theo gio khong ghi scene_sig_lech — mat dung so "
                   "lieu can de tra loi 'boi canh co dong y voi nhat cat nay khong'")
    elif not ds[4]["scene_sig_lech"] > 0.3:
        loi.append(f"scene_sig_lech tai khung doi boi canh = "
                   f"{ds[4]['scene_sig_lech']}, dang le > 0.3")

    #[[ 13 — GIO PHAI DUOC BOI CANH DONG Y.
    #   Nghi 10 phut ma khung hinh y NGUYEN (cung chu ky) -> khong phai canh moi.
    #   Day la doan check-in: chup ~30 phut tai mot phong, nghi vai phut giua
    #   chung la binh thuong. Tach doi ra thi hai nua duoc san sang doc lap va
    #   khach dung cung mot phong lai ra hai muc sang khac nhau.
    #]]
    cung = ([anh(i * 3, 0.10) for i in range(4)]
            + [anh(600 + i * 3, 0.10) for i in range(4)])
    at.group_scenes(cung, 5.0, 0.30)
    if canh(cung) != [0] * 8:
        loi.append(f"Nghi 10 phut CUNG phong ma van tach: {canh(cung)}")

    # 14 — nhưng nghỉ 10 phút mà phông ĐỔI thì vẫn phải tách
    ds = bo()
    at.group_scenes(ds, 5.0, 0.30)
    if canh(ds) != [0, 0, 0, 0, 1, 1, 1, 1]:
        loi.append(f"Nghi 10 phut va phong DOI ma khong tach: {canh(ds)}")

    # 15 — tắt phủ quyết thì trở về hành vi cũ
    cung2 = ([anh(i * 3, 0.10) for i in range(4)]
             + [anh(600 + i * 3, 0.10) for i in range(4)])
    at.group_scenes(cung2, 5.0, 0.30, can_sig=False)
    if canh(cung2) != [0, 0, 0, 0, 1, 1, 1, 1]:
        loi.append(f"can_sig=False ma van phu quyet: {canh(cung2)}")

    #[[ 16 — TAT luat boi canh thi KHONG con y kien nao de hoi.
    #   Neu quen dieu kien nay thi luat thoi gian bi phu quyet boi mot chu ky
    #   khong ton tai — tuc tat luat boi canh lai lam tat luon luat thoi gian,
    #   va ca buoi thanh mot canh ma khong ai hieu vi sao.
    #]]
    cung3 = ([anh(i * 3, 0.10) for i in range(4)]
             + [anh(600 + i * 3, 0.10) for i in range(4)])
    at.group_scenes(cung3, 5.0, 0.0)
    if canh(cung3) != [0, 0, 0, 0, 1, 1, 1, 1]:
        loi.append(f"Tat luat boi canh ma luat thoi gian cung bi phu quyet: "
                   f"{canh(cung3)}")

    # 17 — ảnh không có chữ ký: không có ý kiến, giờ làm việc một mình
    khong = [anh(i * 3) for i in range(4)] + [anh(600 + i * 3) for i in range(4)]
    at.group_scenes(khong, 5.0, 0.30)
    if canh(khong) != [0, 0, 0, 0, 1, 1, 1, 1]:
        loi.append(f"Khong co chu ky ma van phu quyet: {canh(khong)}")

    # 18 — chỗ bị phủ quyết phải để lại dấu vết, không im lặng
    if not any(x.get("scene_cut") == "gio-bo-vi-cung-phong" for x in cung):
        loi.append("Bo mot nhat cat theo gio ma khong ghi lai dau vet nao — "
                   "sau nay khong ai truy duoc vi sao hai doan lai lien nhau")

    for m in loi:
        print("  [!]", m)
    print("TAT CA DAT" if not loi else f"{len(loi)} LOI")
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
