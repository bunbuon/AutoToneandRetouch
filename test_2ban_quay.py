#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nam phan sua tu hai ban quay 2/10/2026 — kiem bang decide() THAT.

Khong dung lai logic nao: anh gia di qua dung group_scenes() + decide() cua
autotone, cac co ghi chu do chinh decide() gan.

MOI PHAN KIEM HAI CHIEU
    TAT (mac dinh) -> dung hanh vi cu, va bai kiem phai TAI HIEN DUOC LOI ma
                      user da chi ra (khong tai hien duoc thi bai kiem vo nghia).
    BAT            -> loi do het, va khong dung toi anh khong lien quan.

    1. Mot anh sang mot ket qua (canh_ev100) — DSC08668-72: cung f/2.2 1/100
       ISO 500, mat do trai -1.30..-0.79 -> tool +0.03..-0.40, user -0.61 het.
    2. WB theo may: nhiet do may (Nikon Auto), Tint theo may, san WB tung may,
       da am duoi den trong canh "sang".
    3. Khung chay: tran da thap hon + phanh da hai chieu.
    4. Bu phep do theo than may.
    5. Highlights cho ao/vay trang.
    6. Bat roi tat tren CUNG items (GUI lam vay) -> tra ve so goc.
    7. Mac dinh 3/10: dung hai phan user duyet (3a, 2b) dang bat, con lai tat.
"""
from __future__ import annotations

import contextlib
import io
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at          # noqa: E402
import test_san_phang as ts    # noqa: E402

DICH = at.DEFAULTS["face_target_ev"]
T0 = datetime(2026, 9, 26, 9, 0, 0)
PRESET = {"Exposure2012": "0", "Highlights2012": "16", "Shadows2012": "16",
          "Temperature": "5250", "Tint": "16"}


def _lin(rgb255):
    return [at._srgb_to_lin_1(v / 255.0) for v in rgb255]


DA_TRONG = _lin(at.DEFAULTS["skin_ref_rgb"])      # da dung mau dich trong nha


def anh(ten, giay, mat, khung=None, model="ILCE-7M4", f=2.2, t=1 / 100, iso=500,
        p95=None, sat=0.0, sub_br=None, da=None, may_K=None):
    r = ts._anh(ten, mat, T0 + timedelta(seconds=giay))
    r.update(metered_subject_ev=(mat - 1.3) if khung is None else khung,
             model=model, fnumber=f, exposure_time=t, iso=iso,
             face_p95=p95, sat_frac=sat, bright_frac=0.0,
             subj_bright_frac=sub_br, subj_sat_frac=None,
             face_rgb=da, wb_may_K=may_K, crs=dict(PRESET), atn={})
    return r


#[[ "TAT" trong bai kiem nay = ca nam phan TAT, de do tung phan rieng.
#   Tu 3/10 hai phan da BAT trong DEFAULTS (khung_sang_pct 12, Tint Nikon -5)
#   nen phai dat TAT tuong minh, khong dua vao DEFAULTS. ]]
TAT_HET = dict(canh_ev100=0.0, wb_theo_may_pull=0.0, wb_tint_theo_may={},
               wb_san_theo_may=False, da_vang_lech_ngoai=0.0, khung_sang_pct=0.0,
               phanh_da_hai_chieu=False, bu_exp_theo_may={}, hl_ao_trang_max=0)


def chay(items, **kw):
    cfg = ts._cfg(**dict(TAT_HET, **kw))
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        for r in items:
            r.pop("ngoai_troi", None)
            r["ngoai_troi"] = at.ngoai_troi(r, cfg)
        at.group_scenes(items, cfg["gap_minutes"])
        at.decide(items, cfg)
    return {r["path"].split("\\")[-1].split(".")[0]: r for r in items}


def d(kq, k):
    return float(kq[k]["delta_ev"])


def co(kq, k, nhan):
    return nhan in (kq[k].get("notes") or "")


# ------------------------------------------------------------------ muc 1
#[[ 4/10: moc mat mac dinh -1.19 -> -1.00 (user chot). So lieu muc 1 dung lai
#   DSC08668-72 (mat -1.52..-1.09) DO TREN MOC -1.19: voi -1.00 nhom A keo
#   +0.44 nen A6 (f/2.8, can them +0.69) cham tran max_ev_up 1.00 cua
#   ts._cfg — bai do bu khau bien thanh do tran (+0.56). Muc 1 kiem CO CHE
#   gop theo anh sang, khong kiem moc, nen ghim moc luc lay so lieu. Cac muc
#   khac dat mat dung DICH (theo DEFAULTS) hoac xa tran nen khong ghim. ]]
MOC_MUC_1 = -1.19


def chay1(items, **kw):
    return chay(items, face_target_ev=MOC_MUC_1, **kw)


def loat_mot_anh_sang():
    """A1-A5: cung thong so, cung khung, mat do nhieu (nhu DSC08668-72).
    A6: cung anh sang nhung f/2.8 (EV100 +0.69) -> preview toi hon 0.69.
    A7: cung thong so A1 nhung KHUNG sang han len 0.9 EV -> den doi that."""
    mat = [-1.52, -1.09, -1.11, -1.60, -1.52]
    ds = [anh(f"A{i + 1}", 3 * i, m, khung=-2.90) for i, m in enumerate(mat)]
    ds.append(anh("A6", 15, -2.05, khung=-3.59, f=2.8))
    ds.append(anh("A7", 18, -0.90, khung=-2.00))
    # A8: khung (quy EV100) TRUNG nhom A nhung thong so lech 1.72 EV (f/4) —
    # nguoi chup da doi hon 1 stop, mat nguoc sang (nhu HIU_4113): khong gop.
    ds.append(anh("A8", 21, -3.60, khung=-4.62, f=4.0))
    return ds


def kiem_muc_1(loi):
    tat = chay1(loat_mot_anh_sang())
    nam = [d(tat, f"A{i}") for i in range(1, 6)]
    if max(nam) - min(nam) < 0.30:
        loi.append(f"M1 TAT: phai tai hien loi 'buc sang buc toi' (dai {max(nam) - min(nam):.2f})")

    bat = chay1(loat_mot_anh_sang(), canh_ev100=0.5)
    nam = [d(bat, f"A{i}") for i in range(1, 6)]
    if max(nam) - min(nam) > 0.02:
        loi.append(f"M1 BAT: cung anh sang ma Exposure van lech {max(nam) - min(nam):.2f}")
    ev_a1 = at.ev100(bat["A1"])
    ev_a6 = at.ev100(bat["A6"])
    bu = d(bat, "A6") - d(bat, "A1")
    if abs(bu - (ev_a6 - ev_a1)) > 0.05:
        loi.append(f"M1 BAT: doi khau +{ev_a6 - ev_a1:.2f} EV ma Exposure chi bu {bu:+.2f}")
    if not all(co(bat, f"A{i}", "do-theo-anh-sang") for i in (1, 2, 3, 4, 5)):
        loi.append("M1 BAT: thieu ghi chu do-theo-anh-sang")
    if co(bat, "A7", "do-theo-anh-sang") or abs(d(bat, "A7") - d(tat, "A7")) > 1e-6:
        loi.append("M1 BAT: A7 den doi that (khung +0.9 EV) ma van bi gop")
    if co(bat, "A8", "do-theo-anh-sang") or abs(d(bat, "A8") - d(tat, "A8")) > 1e-6:
        loi.append("M1 BAT: A8 doi thong so 1.72 EV ma van bi gop")

    # Bat roi tat tren CUNG items -> tra so goc, ke ca face_p95_dong
    def co_p95():
        ds = loat_mot_anh_sang()
        for i, r in enumerate(ds):
            r["face_p95"] = 0.74 + 0.02 * i
        return ds
    goc = chay1(co_p95())
    ds = co_p95()
    chay1(ds, canh_ev100=0.5)
    if not any("face_p95_dong" in r for r in ds):
        loi.append("M1 BAT: khong ghi face_p95_dong (phanh da se khong dong thuan)")
    lai = chay1(ds)
    for i in range(1, 9):
        k = f"A{i}"
        if (abs(d(lai, k) - d(goc, k)) > 1e-6 or "face_p95_dong" in lai[k]
                or lai[k]["metered_face_ev"] != goc[k]["metered_face_ev"]):
            loi.append(f"M1: bat roi tat khong tra ve so goc o {k}")
            break


# ------------------------------------------------------------------ muc 4
def kiem_muc_4(loi):
    def hai():
        return [anh("N1", 0, -1.60, model="NIKON Z 6_2"),
                anh("S1", 900, -1.60, model="ILCE-7M4")]
    tat = chay(hai())
    bat = chay(hai(), bu_exp_theo_may={"NIKON": 0.2})
    if abs((d(bat, "N1") - d(tat, "N1")) - 0.2) > 1e-6:
        loi.append(f"M4: Nikon phai sang them 0.20, ra {d(bat, 'N1') - d(tat, 'N1'):+.3f}")
    if abs(d(bat, "S1") - d(tat, "S1")) > 1e-9:
        loi.append("M4: anh Sony bi dung toi")
    if not co(bat, "N1", "bu-theo-may"):
        loi.append("M4: thieu ghi chu bu-theo-may")


# ------------------------------------------------------------------ muc 3
def kiem_muc_3(loi):
    p95 = 219 / 255.0

    def mot(sat):
        return [anh("B1", 0, -1.60, p95=p95, sat=sat)]
    lin_ = at._srgb_to_lin_1(p95)
    con = lambda tran: math.log2(at._srgb_to_lin_1(tran / 255.0) / lin_)   # noqa: E731

    tat = chay(mot(0.20))
    if abs(d(tat, "B1") - con(232)) > 0.01:
        loi.append(f"M3 TAT: phanh da cu (232) phai giu o {con(232):+.3f}, ra {d(tat, 'B1'):+.3f}")
    bat = chay(mot(0.20), khung_sang_pct=12.0, khung_sang_tran_da=210.0)
    if abs(d(bat, "B1")) > 1e-9:
        loi.append(f"M3a: khung chay 20% -> tran 210 -> phai ghim 0, ra {d(bat, 'B1'):+.3f}")
    it = chay(mot(0.05), khung_sang_pct=12.0, khung_sang_tran_da=210.0)
    if abs(d(it, "B1") - d(tat, "B1")) > 1e-9:
        loi.append("M3a: khung chay it (5%) ma tran van bi ha")
    hai = chay(mot(0.20), khung_sang_pct=12.0, khung_sang_tran_da=210.0,
               phanh_da_hai_chieu=True)
    if abs(d(hai, "B1") - con(210)) > 0.01:
        loi.append(f"M3b: da vuot tran 210 phai keo XUONG {con(210):+.3f}, ra {d(hai, 'B1'):+.3f}")

    # Da da chay ma delta dang am -> phanh mot chieu dung yen, hai chieu keo xuong
    # — nhung CHI trong khung chay. San phang canh khong duoc keo nguoc len.
    def canh(sat):
        ds = [anh("C1", 0, -1.00, p95=254 / 255.0, sat=sat)]
        ds += [anh(f"C{i}", 3 * i, DICH, p95=0.80) for i in range(2, 6)]
        return ds
    M3 = dict(khung_sang_pct=12.0, khung_sang_tran_da=210.0)
    tat = chay(canh(0.20), **M3)
    if abs(d(tat, "C1") - (DICH + 1.00)) > 1e-6:
        loi.append(f"M3b TAT: C1 phai giu {DICH + 1.0:+.2f} (phanh cu khong nhin delta am), "
                   f"ra {d(tat, 'C1'):+.3f}")
    bat = chay(canh(0.20), phanh_da_hai_chieu=True, **M3)
    muon = math.log2(at._srgb_to_lin_1(210 / 255.0) / at._srgb_to_lin_1(254 / 255.0))
    if abs(d(bat, "C1") - muon) > 0.01:
        loi.append(f"M3b BAT: C1 khung chay, da 254 > tran 210 -> phai ve {muon:+.3f}, "
                   f"ra {d(bat, 'C1'):+.3f}")
    if not co(bat, "C1", "ha-vi-chay-sang"):
        loi.append("M3b BAT: thieu co ha-vi-chay-sang -> san phang se keo nguoc len")
    if any(abs(d(bat, f"C{i}") - d(tat, f"C{i}")) > 1e-9 for i in range(2, 6)):
        loi.append("M3b BAT: dung toi anh da khong vuot tran")
    # Khung KHONG chay: da 254 user van nhan (say06085-06110) -> khong keo
    sach = chay(canh(0.0), phanh_da_hai_chieu=True, **M3)
    if abs(d(sach, "C1") - (DICH + 1.00)) > 1e-6:
        loi.append(f"M3b BAT: khung khong chay ma van keo da xuong ({d(sach, 'C1'):+.3f})")


# ------------------------------------------------------------------ muc 2
def kiem_muc_2(loi):
    WB = dict(wb="skin")

    # a + b: Nikon Auto (may tu do 6500K), preset 5250K, catalog khong co AsShot
    def hai():
        return [anh("N1", 0, DICH, model="NIKON Z 6_2", da=list(DA_TRONG), may_K=6500),
                anh("S1", 900, DICH, model="ILCE-7M4", da=list(DA_TRONG), may_K=5300)]
    tat = chay(hai(), **WB)
    bat = chay(hai(), wb_theo_may_pull=0.35, **WB)
    dn = bat["N1"]["temp_adj"] - tat["N1"]["temp_adj"]
    if abs(dn - 0.35 * (6500 - 5250)) > 1.0:
        loi.append(f"M2a: Nikon may do 6500K phai am them {0.35 * 1250:.0f}K, ra {dn:+.0f}")
    if not co(bat, "N1", "wb-theo-may"):
        loi.append("M2a: thieu ghi chu wb-theo-may")
    if abs(tat["N1"]["temp_adj"]) > 1.0:
        loi.append(f"M2a TAT: da dung mau dich ma van keo WB {tat['N1']['temp_adj']:+.0f}")
    bat = chay(hai(), wb_tint_theo_may={"NIKON": -5}, **WB)
    if abs((bat["N1"]["tint_adj"] - tat["N1"]["tint_adj"]) + 5) > 1e-6:
        loi.append("M2b: Nikon phai giam Tint 5")
    if abs(bat["S1"]["tint_adj"] - tat["S1"]["tint_adj"]) > 1e-9:
        loi.append("M2b: Tint anh Sony bi dung toi")

    # b': canh TRON hai may — san phang mau khong duoc lam troi so lech theo
    # da so (Nikon dong hon thi Sony bi -5; Sony dong hon thi Nikon mat -5).
    def tron_may(n_nik, n_sony):
        ds = [anh(f"K{i}", 3 * i, DICH, model="NIKON Z 6_2", da=list(DA_TRONG))
              for i in range(n_nik)]
        ds += [anh(f"Y{i}", 3 * (n_nik + i), DICH, model="ILCE-7M4", da=list(DA_TRONG))
               for i in range(n_sony)]
        return ds
    for n_nik, n_sony in ((4, 2), (2, 4)):
        t0 = chay(tron_may(n_nik, n_sony), **WB)
        t1 = chay(tron_may(n_nik, n_sony), wb_tint_theo_may={"NIKON": -5}, **WB)
        sai = [k for k in t0 if abs((t1[k]["tint_adj"] - t0[k]["tint_adj"])
                                    - (-5 if k.startswith("K") else 0)) > 1e-6]
        if sai:
            loi.append(f"M2b: canh {n_nik} Nikon + {n_sony} Sony — lech Tint sai o {sai}")

    # c: canh tron hai than may, da do duoc khac nhau theo may
    am = [DA_TRONG[0] * 1.15, DA_TRONG[1], DA_TRONG[2] * 0.80]      # da A7IV am hon

    def tron():
        ds = [anh(f"M{i}", 3 * i, DICH, model="ILCE-7M4", da=list(am)) for i in range(4)]
        ds += [anh(f"V{i}", 12 + 3 * i, DICH, model="ILCE-7M5", da=list(DA_TRONG))
               for i in range(4)]
        return ds
    tat = chay(tron(), **WB)
    if len({round(r["temp_adj"], 3) for r in tat.values()}) != 1:
        loi.append("M2c TAT: san WB cu phai dua ca canh ve MOT so")
    bat = chay(tron(), wb_san_theo_may=True, **WB)
    t4 = {round(bat[f"M{i}"]["temp_adj"], 3) for i in range(4)}
    t5 = {round(bat[f"V{i}"]["temp_adj"], 3) for i in range(4)}
    if len(t4) != 1 or len(t5) != 1:
        loi.append("M2c BAT: trong cung mot may phai con mot so")
    elif not (min(t4) < min(t5) - 50):
        loi.append(f"M2c BAT: A7IV da am phai lanh hon A7V ({min(t4):+.0f} vs {min(t5):+.0f})")

    # d: canh "sang" (EV100 cao -> nhan anh sang ngay) ma da rat am (den am chieu)
    rat_am = [0.40, 0.20, 0.10]           # log2(B/R) = -2.0, mau dich ngoai troi -1.43

    def ngoai():
        return [anh("O1", 0, DICH, f=8.0, t=1 / 250, iso=100, da=list(rat_am))]
    tat = chay(ngoai(), **WB)
    if not tat["O1"]["ngoai_troi"]:
        loi.append("M2d: canh dung sai — anh phai mang nhan anh sang ngay")
    bat = chay(ngoai(), da_vang_lech_ngoai=0.40, **WB)
    if not (bat["O1"]["temp_adj"] < tat["O1"]["temp_adj"] - 200):
        loi.append(f"M2d: da am duoi den phai dung mau dich trong nha (lanh hon), "
                   f"{tat['O1']['temp_adj']:+.0f} -> {bat['O1']['temp_adj']:+.0f}")
    vua = [0.30, 0.20, 0.12]               # log2(B/R) = -1.32: da ngoai troi binh thuong
    ds = [anh("O2", 0, DICH, f=8.0, t=1 / 250, iso=100, da=list(vua))]
    a = chay([dict(r) for r in ds], **WB)["O2"]["temp_adj"]
    b = chay([dict(r) for r in ds], da_vang_lech_ngoai=0.40, **WB)["O2"]["temp_adj"]
    if abs(a - b) > 1e-9:
        loi.append("M2d: da ngoai troi binh thuong bi doi mau dich")


# ------------------------------------------------------------------ muc 5
def kiem_muc_5(loi):
    def mot(sub_br):
        return [anh("H1", 0, DICH, sat=0.10, sub_br=sub_br)]
    tat = chay(mot(0.30))
    if tat["H1"]["hl_adj"] != -int(at.DEFAULTS["hl_max"]):
        loi.append(f"M5 TAT: canh dung sai — HL phai cham tran cu {-at.DEFAULTS['hl_max']}, "
                   f"ra {tat['H1']['hl_adj']}")
    bat = chay(mot(0.30), hl_ao_trang_max=65, hl_ao_trang_pct=15.0)
    if bat["H1"]["hl_adj"] != -65:
        loi.append(f"M5 BAT: vay trang 30% phai keo HL toi -65, ra {bat['H1']['hl_adj']}")
    if not co(bat, "H1", "keo-HL-ao-trang"):
        loi.append("M5 BAT: thieu ghi chu keo-HL-ao-trang")
    it = chay(mot(0.05), hl_ao_trang_max=65, hl_ao_trang_pct=15.0)
    if it["H1"]["hl_adj"] != tat["H1"]["hl_adj"]:
        loi.append("M5 BAT: vung chu the sang it (5%) ma van noi tran")


def kiem_mac_dinh(loi):
    """Dung HAI phan user da duyet 3/10 duoc bat, khong hon khong kem."""
    d = at.DEFAULTS
    if float(d["khung_sang_pct"]) != 12.0 or float(d["khung_sang_tran_da"]) != 210.0:
        loi.append("Mac dinh: khung_sang_pct 12 / tran 210 (user duyet 3/10) da bi doi")
    if d["wb_tint_theo_may"] != {"NIKON": -5}:
        loi.append("Mac dinh: wb_tint_theo_may phai la {'NIKON': -5} (user duyet 3/10)")
    con_tat = {k: v for k, v in TAT_HET.items()
               if k not in ("khung_sang_pct", "wb_tint_theo_may") and d[k] != v}
    if con_tat:
        loi.append(f"Mac dinh: phan da TRUOT cong lai dang bat: {con_tat}")


def main() -> int:
    loi: list = []
    for f in (kiem_mac_dinh, kiem_muc_1, kiem_muc_2, kiem_muc_3, kiem_muc_4, kiem_muc_5):
        truoc = len(loi)
        f(loi)
        print(f"  {f.__name__:12} {'dat' if len(loi) == truoc else 'LOI'}")
    for m in loi:
        print("  [!]", m)
    print("TAT CA DAT" if not loi else f"{len(loi)} LOI")
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
