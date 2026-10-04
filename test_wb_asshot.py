#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WB theo As Shot — quy trình preset bỏ trống WB, bước 2 (3/10). Kiểm bằng plan() THẬT.

CHUYỆN ĐANG SỬA
    G:\\2709 (cưới, Nikon đặt K tay 4760–6670K): nền 5250 bỏ qua WB người chụp
    đã đặt — Z 8 đặt 6670K mà tool ghi 5279K. User: "ảnh ngoài trời bị kéo về
    xanh". Sửa: Temp kéo thêm wb_asshot_pull × (As Shot − 5250), As Shot là
    trung vị theo (cảnh, máy), cộng SAU san phẳng màu; ảnh NGÀY chỉ kéo ấm, ảnh
    ĐÈN chỉ kéo lạnh; kéo dưới wb_asshot_min_K thì bỏ. Quy trình cũ không đổi.

Mục kiểm (mỗi nhóm một cảnh riêng; so cùng items khi TẮT wb_theo_asshot)
     1. Nikon Z 8 ngày, K máy 6670 -> As Shot thang Adobe 1e6/(1e6/K + lệch) ->
        Temp +pull×(A−5250), ghi chú wb-asshot.
     2. Nikon Z5_2 ngày, K 4760 -> kéo LẠNH ảnh ngày bị chặn -> đứng yên.
     3. ILCE-7M5 ngày, K 5600 -> As Shot 5317, kéo +23K < 50K -> đứng yên.
     4. ILCE-7M4 đèn, K 4800 -> ảnh đèn kéo lạnh được.
     5. ILCE-7M4 đèn, K 6250 -> kéo ẤM ảnh đèn bị chặn -> đứng yên.
     6. Một cảnh hai máy xen kẽ (Z 8 6670 + 7M5 5600) -> mỗi máy As Shot của
        mình: Z 8 kéo như mục 1, 7M5 đứng yên (không ăn As Shot của Z 8).
     7. Máy đổi K giữa cảnh (5880 -> 5560) -> trung vị (cảnh, máy): cùng Temp.
     8. As Shot THẬT trong catalog (WhiteBalance "As Shot", Temperature 6050)
        được ưu tiên hơn K máy.
     9. WhiteBalance "Auto" kèm Temperature -> KHÔNG phải As Shot -> dùng K máy.
    10. Buổi có >= 3 cặp (As Shot thật, K máy) của một máy -> học độ lệch từ
        chính buổi, không lấy bảng.
    11. Preset đầy đủ (quy trình cũ) -> không đổi một số nào, kể cả khi cùng cảnh
        cùng máy với ảnh đang As Shot.
    12. Tắt wb_theo_asshot -> y hệt; Exposure / Tint không bao giờ đổi.
    13. Chạy lại sau khi đẩy (catalog đã mang WB Custom của tool, mốc trên đĩa)
        -> ra y hệt lần đầu: As Shot phải lấy từ MỐC, không từ catalog.
    14. Máy để Auto (không có K), catalog chỉ có As Shot của 1/4 tấm (tấm user
        đã lướt qua) -> CẢ 4 tấm cùng cảnh cùng máy cùng kéo, không tấm ấm tấm lạnh.
    (Đường sidecar không áp bước này — test_preset_khong_wb_tone.py canh.)

Chạy:  python test_wb_asshot.py
"""
from __future__ import annotations

import contextlib
import copy
import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at          # noqa: E402
import test_2ban_quay as tq    # noqa: E402

B_MODE = {"Exposure2012": "0", "Highlights2012": "0", "Shadows2012": "0",
          "Contrast2012": "0", "Whites2012": "0", "Blacks2012": "0",
          "WhiteBalance": "As Shot", "Temperature": "", "Tint": ""}
NGAY = dict(f=2.2, t=1 / 800, iso=125)       # EV100 ~11.6 -> anh sang ngay
DEN = dict(f=2.2, t=1 / 100, iso=1600)       # EV100 ~4.9  -> anh den


def nhom(ten, phut, model, ks, kieu, preset=None, n=4, cach=10):
    """n ảnh cách nhau `cach` giây, bắt đầu ở phút `phut`; mỗi nhóm một cảnh."""
    out = []
    for i in range(n):
        r = tq.anh(f"{ten}{i}", phut * 60 + i * cach, -1.3, model=model, da=tq.DA_TRONG,
                   may_K=ks[i] if isinstance(ks, list) else ks, **kieu)
        p = preset[i] if isinstance(preset, list) else preset
        r["__xuat"] = dict(p if p is not None else B_MODE)
        out.append(r)
    return out


def bo_anh(thu_muc: Path) -> list:
    items = []
    items += nhom("NGAYZ8_", 0, "NIKON Z 8", 6670, NGAY)
    items += nhom("NGAYZ5_", 20, "NIKON Z5_2", 4760, NGAY)
    items += nhom("NGAY7M5_", 40, "ILCE-7M5", 5600, NGAY)
    items += nhom("DENLANH_", 60, "ILCE-7M4", 4800, DEN)
    items += nhom("DENAM_", 80, "ILCE-7M4", 6250, DEN)
    tron = nhom("TRONZ8_", 100, "NIKON Z 8", 6670, NGAY, cach=20)
    tron += nhom("TRON7M5_", 100, "ILCE-7M5", 5600, NGAY, cach=20)
    for i, r in enumerate(tron[4:]):                       # xen ke 10 giay
        r["dt_obj"] = tron[i]["dt_obj"] + (tron[1]["dt_obj"] - tron[0]["dt_obj"]) / 2
        r["dt"] = r["dt_obj"].isoformat()
    items += tron
    items += nhom("DOIK_", 120, "NIKON Z 8", [5880, 5880, 5560, 5560, 5560], NGAY, n=5)
    #[[ May RIENG cho nhom catalog: 4 cap (As Shot that, K may) cua mot may la du
    #   de uoc_asshot hoc do lech tu chinh buoi — dung chung 7M4 thi do lech hoc
    #   duoc (6050 vs 5400) lan sang nhom DEN / AUTO. ]]
    items += nhom("CAT_", 140, "ILCE-7RM5", 5400, NGAY,
                  preset=dict(B_MODE, Temperature="6050", Tint="10"))
    items += nhom("AUTO_", 160, "ILCE-7M4", 6250, NGAY,
                  preset=dict(B_MODE, WhiteBalance="Auto", Temperature="6500", Tint="5"))
    hoc = [dict(B_MODE, Temperature="5700", Tint="12")] * 3 + [B_MODE] * 3
    items += nhom("HOC_", 180, "NIKON Z 6_2", 6000, NGAY, preset=hoc, n=6)
    items += nhom("CU_", 200, "NIKON Z 8", 6670, NGAY, preset=dict(tq.PRESET))
    items += nhom("CUNGCANH_", 210, "NIKON Z 8", 6670, NGAY, preset=[B_MODE, dict(tq.PRESET)] * 2)
    items += nhom("AWB_", 220, "ILCE-7M3", None, NGAY,
                  preset=[dict(B_MODE, Temperature="6050", Tint="9")] + [B_MODE] * 3)
    for r in items:
        r["path"] = str(thu_muc / Path(r["path"].replace("\\", "/")).name)
    return items


def cau_hinh(**kw) -> dict:
    cfg = dict(at.DEFAULTS, source="catalog", bo_qua_nguoi_sua=False, max_ev_up=3.0)
    cfg.update(kw)
    return cfg


def chay(items, thu_muc: Path, xuat=None, **kw) -> dict:
    its = copy.deepcopy(items)
    exp = {at.khoa_duong_dan(r["path"]): (xuat(r) if xuat else r["__xuat"]) for r in its}
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        at.plan(its, cau_hinh(**kw), thu_muc, exp)
    return {Path(r["path"]).stem: r for r in its}


def chay_lai_sau_khi_day(items, thu_muc: Path, lan_dau: dict) -> dict:
    """Ghi THAT (mốc + job) roi chay lai voi catalog mang so tool vua ghi."""
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        at.write_sidecars(list(lan_dau.values()), cau_hinh(), thu_muc)

    def sau_day(r):
        x = lan_dau[Path(r["path"]).stem]
        return {"WhiteBalance": "Custom", "Temperature": str(x["new_temp"]),
                "Tint": str(x["new_tint"]), "Exposure2012": str(x["new_exposure"]),
                "Highlights2012": str(x["new_highlights"]), "Shadows2012": str(x["new_shadows"]),
                "Contrast2012": "5", "Whites2012": "-25", "Blacks2012": "-18"}
    return chay(items, thu_muc, xuat=sau_day)


def as_shot(k: float, lech: float) -> float:
    return 1e6 / (1e6 / k + lech)


def main() -> int:
    loi: list = []
    D = at.DEFAULTS
    if not D.get("wb_theo_asshot"):
        loi.append("DEFAULTS: wb_theo_asshot phai BAT")
    pull, min_k = float(D["wb_asshot_pull"]), float(D["wb_asshot_min_K"])
    bang = D["wb_asshot_lech_mired"]
    with tempfile.TemporaryDirectory() as td:
        at.LR_JOB_DIR = Path(td) / "jobs"          # khong bao gio ghi vao plugin that
        d = Path(td) / "2709"
        d.mkdir()
        items = bo_anh(d)
        tat = chay(items, d, wb_theo_asshot=False)
        bat = chay(items, d)
        lai = chay(items, d, wb_theo_asshot=False)
        sau = chay_lai_sau_khi_day(items, d, bat)

    def doi(k):
        return bat[k]["new_temp"] - tat[k]["new_temp"]

    def nhom_k(tien):
        return sorted(k for k in bat if k.startswith(tien))

    def mong(tien, keo, nhan):
        for k in nhom_k(tien):
            if abs(doi(k) - keo) > 1.5:
                loi.append(f"{nhan}: {k} Temp {tat[k]['new_temp']} -> {bat[k]['new_temp']}, "
                           f"phai {keo:+.0f}K")

    def dung_yen(tien, nhan):
        for k in nhom_k(tien):
            if doi(k) != 0:
                loi.append(f"{nhan}: {k} phai dung yen, dang {doi(k):+d}K")

    # Dung bai: dung nhan ngay/den, dung nhom canh
    for tien, ngoai in (("NGAYZ8_", True), ("DENLANH_", False), ("DENAM_", False)):
        if any(bool(bat[k].get("ngoai_troi")) != ngoai for k in nhom_k(tien)):
            loi.append(f"Dung bai: nhom {tien} phai la anh {'ngay' if ngoai else 'den'}")
    if len({bat[k].get("scene") for k in nhom_k("TRON")}) != 1:
        loi.append("Dung bai: hai may xen ke phai CUNG mot canh")

    # 1
    a = as_shot(6670, bang["NIKON Z 8"])
    mong("NGAYZ8_", pull * (a - 5250), "Z 8 ngay 6670K")
    if not all("wb-asshot+" in bat[k].get("notes", "") for k in nhom_k("NGAYZ8_")):
        loi.append("Z 8 ngay: thieu co wb-asshot trong notes")
    # 2, 3
    dung_yen("NGAYZ5_", "Z5_2 dat 4760K giua nang — khong duoc keo xanh them")
    if abs(pull * (as_shot(5600, bang["ILCE-7M5"]) - 5250)) >= min_k:
        loi.append("Dung bai: 7M5 5600K phai keo duoi wb_asshot_min_K")
    dung_yen("NGAY7M5_", "7M5 5600K (keo < min)")
    # 4, 5
    mong("DENLANH_", pull * (as_shot(4800, bang["ILCE-7M4"]) - 5250), "Anh den, may 4800K")
    dung_yen("DENAM_", "Anh den, may 6250K — khong keo am anh den")
    # 6
    mong("TRONZ8_", pull * (a - 5250), "Canh hai may — Z 8")
    dung_yen("TRON7M5_", "Canh hai may — 7M5 khong an As Shot cua Z 8")
    # 7
    ds = nhom_k("DOIK_")
    if len({bat[k]["new_temp"] for k in ds}) != 1 or len({tat[k]["new_temp"] for k in ds}) != 1:
        loi.append("May doi K giua canh: ca canh phai CUNG Temp (trung vi canh, may)")
    mong("DOIK_", pull * (as_shot(5560, bang["NIKON Z 8"]) - 5250), "May doi K giua canh")
    # 8, 9
    mong("CAT_", pull * (6050 - 5250), "As Shot that trong catalog")
    if any(bat[k].get("asshot_nguon") != "catalog" for k in nhom_k("CAT_")):
        loi.append("As Shot that trong catalog: asshot_nguon phai la catalog")
    mong("AUTO_", pull * (as_shot(6250, bang["ILCE-7M4"]) - 5250), "WhiteBalance Auto")
    # 10
    hoc = 1e6 / 5700 - 1e6 / 6000
    mong("HOC_", pull * (as_shot(6000, hoc) - 5250), "Hoc do lech tu chinh buoi")
    # 11
    dung_yen("CU_", "Preset day du (quy trinh cu)")
    if len({bat[k].get("scene") for k in nhom_k("CUNGCANH_")}) != 1:
        loi.append("Dung bai: nhom CUNGCANH_ phai la mot canh")
    for i, k in enumerate(nhom_k("CUNGCANH_")):
        if i % 2 and doi(k) != 0:
            loi.append(f"Preset day du cung canh voi anh As Shot: {k} bi keo {doi(k):+d}K")
        if not i % 2 and abs(doi(k) - pull * (a - 5250)) > 1.5:
            loi.append(f"Anh As Shot cung canh voi anh preset day du: {k} {doi(k):+d}K")
    if any(bat[k].get("asshot_K") for k in nhom_k("CU_")):
        loi.append("Preset day du: khong duoc gan asshot_K")
    # 12
    for k in bat:
        for t in ("new_temp", "new_tint", "new_exposure"):
            if tat[k][t] != lai[k][t]:
                loi.append(f"Tat hai lan phai y het: {k} {t}")
        for t in ("new_tint", "new_exposure", "new_highlights", "new_shadows"):
            if bat[k][t] != tat[k][t]:
                loi.append(f"{k}: WB theo As Shot khong duoc dung {t} ({tat[k][t]} -> {bat[k][t]})")
    # 14
    mong("AWB_", pull * (6050 - 5250), "May Auto, catalog chi co As Shot 1/4 tam")
    # 13
    for k in bat:
        if sau[k]["new_temp"] != bat[k]["new_temp"]:
            loi.append(f"Chay lai sau khi day: {k} Temp {bat[k]['new_temp']} -> {sau[k]['new_temp']}"
                       " — As Shot phai lay tu moc")
            break
    for m in loi:
        print("  [!]", m)
    print("TAT CA DAT" if not loi else f"{len(loi)} LOI")
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
