#!/usr/bin/env python3
"""Mốc cảnh chỉ tính trên ảnh không bị ghìm — kiểm bằng hàm THẬT.

Gọi thẳng autotone.decide(). Không dựng lại một dòng logic nào: bài học đã trả
giá bốn lần trong dự án này là mỗi lần logic được viết lại ở file kiểm thì bản
viết lại thiếu mất một vòng lọc, và kết luận rút ra là sai.

CHUYỆN ĐANG SỬA
    Bước san phẳng lấy TRUNG VỊ độ sáng sau chỉnh của cảnh làm mốc chung. Mốc
    đó đúng khi cả cảnh khoẻ mạnh. Nó sai khi trong cảnh có nhiều ảnh bị ghìm
    lại vì cháy sáng: mức chúng dừng lại KHÔNG phải mức đúng của cảnh, mà là
    mức chúng KHÔNG THỂ vượt qua. Lấy đó làm mốc thì ảnh khoẻ bị kéo xuống theo.

    Buổi 0306, cảnh 3: 9/11 ảnh mang cờ "ha-vi-chay-sang", đứng ở -1.83 trong
    khi đích là -1.19. SAY09660 đang ở ĐÚNG đích (delta +0.48, người dùng tự
    chỉnh +0.44) bị kéo thành -0.16. Sai 0.64 EV vì lý do của ảnh khác.

CẢNH DỰNG LẠI ĐÚNG HÌNH DẠNG ĐÓ
    9 ảnh có mảng cháy lớn -> vòng lặp chống cháy ghìm chúng ở sàn chủ thể,
      mang cờ "ha-vi-chay-sang", đứng thấp hơn đích rất nhiều.
    2 ảnh sạch -> tới đúng đích.
    Trung vị CẢ CẢNH rơi vào nhóm bị ghìm. Trung vị nhóm TỰ DO bằng đích.

    Cả hai nhóm ảnh đều đi qua đúng vòng lặp chống cháy thật của decide(), cờ
    "ha-vi-chay-sang" do chính nó gắn — không phải do file này gán tay.

CÁCH TIẾP CẬN NÀY THAY CHO MỘT CHỐT ĐÃ BỊ BÁC BỎ
    Bản trước chặn từng ảnh: "không được đẩy ra xa đích hơn lúc chưa san".
    Chạy trên buổi 1308 (1464 ảnh): cổng B 2.42% (cổng cho 2%), cổng A kéo lại
    gần 3 ảnh nhưng đẩy ra xa 11. Bị bác bỏ, không chỉnh tham số cho vừa cổng.
    Bản này sửa MỐC chứ không chặn từng ảnh, nên cảnh nào không có ảnh bị ghìm
    thì kết quả giống hệt như cũ — đó là điều kiện được kiểm ở cuối file.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at   # noqa: E402

DICH = at.DEFAULTS["face_target_ev"]


def _anh(ten: str, metered_ev: float, khi: datetime, chay_sang: float = 0.0) -> dict:
    """Một ảnh giả nhưng histogram dựng bằng chính _hist() của autotone.

    chay_sang = tỉ lệ pixel nằm NGAY DƯỚI ngưỡng cháy. Kéo sáng lên là chúng
    vượt ngưỡng, đúng thứ vòng lặp chống cháy trong decide() canh. Đây là cách
    duy nhất làm ảnh mang cờ "ha-vi-chay-sang" mà không phải gán tay cờ đó.
    """
    n = 4096
    logY = np.full(n, metered_ev, dtype=np.float64)
    if chay_sang > 0:
        k = int(n * chay_sang)
        # -0.40: vuot nguong CLIP_HI_LOG (-0.065) khi keo sang them >= 0.335 EV
        logY[:k] = -0.40
    lin = float(2.0 ** metered_ev)
    return {
        "path": f"X:\\test\\{ten}.ARW", "sidecar": f"X:\\test\\{ten}.xmp",
        "ok": True, "error": "", "notes": "",
        "dt": khi.isoformat(), "dt_obj": khi,
        "hist_y": at._hist(logY).tolist(),
        "hist_max": at._hist(logY).tolist(),
        "metered": lin, "metered_ev": metered_ev,
        "metered_face_ev": metered_ev, "metered_focus_ev": None,
        "metered_subject_ev": metered_ev,
        "sat_frac": 0.0, "bright_frac": 0.0, "crush_frac": 0.0,
        "p50": lin, "rgb_mean": (lin, lin, lin), "face_rgb": None,
        "faces_n": 1, "faces_found": 1, "meter_used": "face",
        "width": 6000, "height": 4000, "iso": 1600, "model": "ILCE-7M4",
        "crs": {}, "atn": {}, "scene_sig": None,
    }


def _cfg(**kw) -> dict:
    #[[ Goi dict(...).update() chu khong truyen thang **kw vao dict(a=1, **kw):
    #   cach kia bao "got multiple values" ngay khi bai kiem muon GHI DE mot
    #   khoa da co san o day — dung viec no phai lam.
    #]]
    c = dict(at.DEFAULTS, meter="face", mode="absolute", wb="off",
             source="sidecar", burst=False, blink=False,
             max_ev=2.0, max_ev_up=1.00,
             scene_level=1.0, scene_level_min=4, scene_level_extra_ev=0.0,
             scene_aim_slack_ev=99.0)
    c.update(kw)
    return c


def _chay(items: list, cfg: dict) -> list:
    at.group_scenes(items, cfg["gap_minutes"])
    at.decide(items, cfg)
    return items


def _sau(r: dict) -> float:
    return r["metered_ev"] + r["delta_ev"]


def canh_hon_hop(free_min: int) -> list:
    t0 = datetime(2026, 6, 3, 19, 0, 0)
    items = [_anh(f"GHIM{i:02d}", -3.50, t0 + timedelta(seconds=i * 3), chay_sang=0.40)
             for i in range(9)]
    items += [_anh(f"KHOE{i:02d}", -1.67, t0 + timedelta(seconds=30 + i * 3))
              for i in range(2)]
    return _chay(items, _cfg(scene_aim_free_min=free_min))


def canh_lanh(free_min: int) -> list:
    t0 = datetime(2026, 6, 3, 20, 0, 0)
    items = [_anh(f"L{i:02d}", DICH - 0.30 + 0.06 * i, t0 + timedelta(seconds=i * 3))
             for i in range(11)]
    return _chay(items, _cfg(scene_aim_free_min=free_min))


def main() -> int:
    loi = []
    lay = lambda ds, t: next(r for r in ds if t in r["path"])   # noqa: E731

    tat = canh_hon_hop(0)      # 0 = lay trung vi ca canh, tuc cach chay cu
    bat = canh_hon_hop(2)

    g_tat, g_bat = lay(tat, "GHIM00"), lay(bat, "GHIM00")
    k_tat, k_bat = lay(tat, "KHOE00"), lay(bat, "KHOE00")

    print(f"dich = {DICH:+.2f} EV")
    print(f"  anh GHIM  co: {'ha-vi-chay-sang' in g_tat['notes']}"
          f"    moc ca canh -> {_sau(g_tat):+.2f}   moc anh tu do -> {_sau(g_bat):+.2f}")
    print(f"  anh KHOE                       "
          f"    moc ca canh -> {_sau(k_tat):+.2f}   moc anh tu do -> {_sau(k_bat):+.2f}")

    # 1. Canh dung phai THAT SU tai hien duoc su co, khong thi bai kiem vo nghia
    if "ha-vi-chay-sang" not in g_tat["notes"]:
        loi.append("Anh GHIM khong mang co 'ha-vi-chay-sang' — vong lap chong "
                   "chay khong he ghim no, canh dung sai, bai kiem vo nghia")
    if abs(_sau(k_tat) - DICH) < 0.25:
        loi.append(f"Moc ca canh ma anh khoe van sat dich ({_sau(k_tat):+.2f}) — "
                   f"chua tai hien duoc su co")

    # 2. Lay moc tren anh tu do thi anh khoe phai ve dung dich
    if abs(_sau(k_bat) - DICH) > 0.02:
        loi.append(f"Anh khoe van lech dich: {_sau(k_bat):+.3f} thay vi {DICH:+.2f}")

    # 3. Anh bi ghim KHONG duoc keo len — ly do ghim van con nguyen
    if _sau(g_bat) > _sau(g_tat) + 0.02:
        loi.append(f"Anh bi ghim vi chay sang lai bi keo len: {_sau(g_tat):+.3f} "
                   f"-> {_sau(g_bat):+.3f}")

    # 4. ĐIỀU KIỆN SỐNG CÒN: cảnh không có ảnh bị ghìm thì KHÔNG được đổi gì.
    #    Đây là chỗ chốt phiên bản trước chết — nó đụng tới 149 ảnh ở buổi 1308.
    lt = {r["path"]: _sau(r) for r in canh_lanh(0)}
    lb = {r["path"]: _sau(r) for r in canh_lanh(2)}
    xe = max(abs(lb[k] - lt[k]) for k in lt)
    print(f"  canh lanh manh (khong anh nao bi ghim): xe dich lon nhat {xe:.4f} EV")
    if xe > 1e-6:
        loi.append(f"Canh lanh manh bi doi {xe:.4f} EV — phai la 0 tuyet doi")

    # 5. Khong du anh tu do thi lui ve cach cu, khong duoc tu tat san phang
    it_tu_do = canh_hon_hop(20)     # doi 20 anh tu do, canh chi co 2
    if abs(_sau(lay(it_tu_do, "KHOE00")) - _sau(k_tat)) > 1e-6:
        loi.append("Khong du anh tu do ma van khong lui ve trung vi ca canh")

    # ---- THU HOI VUNG CHAY ----
    #[[ Dung ham that: decide() cua autotone, khong dung lai phep tinh nao.
    #]]
    t0 = datetime(2026, 6, 3, 21, 0, 0)

    def _thu(sat, **kw):
        it = [_anh(f"S{i:02d}", DICH, t0 + timedelta(seconds=i * 3)) for i in range(6)]
        for r in it:
            r["sat_frac"] = sat
        return _chay(it, _cfg(scene_level=0.0, **kw))[0]

    tat = _thu(0.30)
    bat = _thu(0.30, hl_thu_hoi_nguong=0.08, hl_thu_hoi_ev=0.42,
               hl_thu_hoi_san_ev=0.60)
    duoi = _thu(0.05, hl_thu_hoi_nguong=0.08, hl_thu_hoi_ev=0.42,
                hl_thu_hoi_san_ev=0.60)
    print(f"\n  thu hoi vung chay:")
    print(f"    bao hoa 30%, chot TAT -> delta {tat['delta_ev']:+.2f}")
    print(f"    bao hoa 30%, chot BAT -> delta {bat['delta_ev']:+.2f}"
          f"   ({'co' if 'thu-hoi-vung-chay' in bat['notes'] else 'KHONG'} co co)")
    print(f"    bao hoa  5%, chot BAT -> delta {duoi['delta_ev']:+.2f}"
          f"   (duoi nguong, phai giong luc tat)")

    if abs(bat["delta_ev"] - (tat["delta_ev"] - 0.42)) > 0.02:
        loi.append(f"Keo sai luong: {tat['delta_ev']:+.3f} -> {bat['delta_ev']:+.3f}, "
                   f"dang le -0.42")
    if "thu-hoi-vung-chay" not in bat.get("notes", ""):
        loi.append("Thieu co 'thu-hoi-vung-chay' — bao cao se khong noi duoc vi sao")
    if abs(duoi["delta_ev"] - tat["delta_ev"]) > 1e-6:
        loi.append(f"Anh DUOI nguong cung bi keo: {tat['delta_ev']:+.3f} -> "
                   f"{duoi['delta_ev']:+.3f}. Chot phai la con so khong o day.")

    # San: khong duoc day mat xuong qua sau so voi dich
    sau = _thu(0.30, hl_thu_hoi_nguong=0.08, hl_thu_hoi_ev=3.0,
               hl_thu_hoi_san_ev=0.60)
    thap = sau["metered_ev"] + sau["delta_ev"]
    print(f"    keo 3.0 EV nhung co san 0.60 -> mat dung o {thap:+.2f} "
          f"(dich {DICH:+.2f}, khong duoc thap hon {DICH - 0.60:+.2f})")
    if thap < DICH - 0.60 - 0.02:
        loi.append(f"San khong giu: mat tut xuong {thap:+.3f}, duoi muc cho phep "
                   f"{DICH - 0.60:+.3f}")

    print()
    for m in loi:
        print("  [!]", m)
    print("TAT CA DAT" if not loi else f"{len(loi)} LOI")
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
