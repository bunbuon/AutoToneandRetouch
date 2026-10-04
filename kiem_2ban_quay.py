#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kiem_2ban_quay.py — CONG cho nam phan sua hoc tu hai ban quay 2/10/2026.

    python kiem_2ban_quay.py                    (moi buoi trong Claude outputs\\do)
    python kiem_2ban_quay.py TrainTool 2609

Doc so do cua DO_BUOI.bat (Claude outputs\\do\\<buoi>\\do_<buoi>.json.gz), roi
chay plan() THAT cua autotone nhieu luot tren cung so do — moi luot chi khac
nhau dung nhung khoa cua mot phan sua. Khong dung lai logic nao.

DAP AN CUA NGUOI DUNG
    Ban chup catalog (_autotone_da_sua_*.tsv) so voi lan tool day ngay truoc
    no (jobs\\apply_*_<buoi>.done): khac nhau = anh nguoi dung SUA (dich dung la
    so cua ho); giong nhau = anh DA DUYET (tool da dung). Tung truong rieng:
    Exposure, Temperature, Tint, Highlights.
    Khong co ban chup thi lui ve corrections.csv + gu\\<buoi>\\gu.csv (chi
    Exposure) giong kiem_gu.py.

CONG — DAT TRUOC KHI CHAY, KHONG NOI SAU (cung tinh than kiem_gu.py)
    Exposure  A: anh nguoi dung sua: keo LAI GAN >= day RA XA.
              B: anh da duyet: duoi 2% bi xe dich qua 0.30 EV.
    Temp/Tint A: nhu tren, rieng tung truong.
              B: anh da duyet WB (tru Nikon — user noi "anh Nikon qua tool DEU
                 am tim", anh Nikon ho chua sua khong co nghia la dung):
                 duoi 5% bi xe dich qua 250K hoac qua 4 Tint.
    HL        A: nhu tren.  B: duoi 5% anh da duyet bi xe dich qua 10.
    Nhom duoi 8 anh thi CHUA KET LUAN.

    TrainTool la buoi DA DUNG DE THIET KE nam phan (trong mau). Con so that la
    o buoi KHAC (2609, 1308...). Muc 4 (bu theo may) HOC so bu tren anh da duyet
    cua TrainTool roi moi dem ra kiem.

KHONG GHI gu.json. Dat cong thi user duyet roi moi bat.
"""
from __future__ import annotations

import contextlib
import copy
import csv
import gzip
import io
import json
import ntpath
import os
import re
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import autotone as at        # noqa: E402
import kiem_gu as kg         # noqa: E402
import xem_ban_chup as xbc   # noqa: E402

#[[ CAC DE XUAT — CHOT TRUOC KHI CHAY. Sua so o day sau khi da xem ket qua la
#   bien cong thanh do trang tri (CLAUDE.md: "Khong noi nguong da dat").
#
#   Tu 3/10 hai manh M3a (khung_sang_pct 12) va M2b (Tint Nikon -5) da nam
#   trong DEFAULTS, nen luot "goc" o duoi DA GOM hai manh do.
#]]
DE_XUAT = {
    "M1 mot anh sang": {"canh_ev100": 0.5},
    "M2 WB theo may": {"wb_theo_may_pull": 0.35, "wb_tint_theo_may": {"NIKON": -5},
                       "wb_san_theo_may": True, "da_vang_lech_ngoai": 0.40},
    "M3 khung chay": {"khung_sang_pct": 12.0, "khung_sang_tran_da": 210.0,
                      "phanh_da_hai_chieu": True},
    "M4 bu theo may": None,          # hoc tren TrainTool, xem hoc_bu_theo_may()
    "M5 ao trang": {"hl_ao_trang_max": 65, "hl_ao_trang_pct": 15.0},
}
#[[ --tach: chay them tung MANH cua muc 2 va muc 3 de biet manh nao keo ket qua
#   ve dau. Chi de CHAN DOAN — cong tinh tren de xuat chot o tren. ]]
TACH = {
    "(tach) M2a nhiet do may": {"wb_theo_may_pull": 0.35},
    "(tach) M2b Tint Nikon": {"wb_tint_theo_may": {"NIKON": -5}},
    "(tach) M2c san WB theo may": {"wb_san_theo_may": True},
    "(tach) M2d da vang duoi den": {"da_vang_lech_ngoai": 0.40},
    "(tach) M3a chi ha tran": {"khung_sang_pct": 12.0, "khung_sang_tran_da": 210.0},
}
#[[ Muc 4: hoc so bu = trung vi (user - tool) tren anh Nikon CO MAT da duyet cua
#   buoi hoc, tinh SAU KHI bat bon muc kia. Chi dung khi |so bu| >= 0.10 EV va
#   co >= 30 anh — duoi do la nhieu, khong phai lech theo may. ]]
BU_MAY = "NIKON"
BU_MIN_EV, BU_MIN_ANH = 0.10, 30
BUOI_HOC = "TrainTool"
#[[ Pham vi user da duyet trong hai ban quay (thu tu dong trong file .done =
#   thu tu gio chup). Ngoai pham vi do user CHUA XEM — khong tinh la da duyet. ]]
DA_DUYET_THEO_BUOI = {"TrainTool": [(0, 323), (512, 921)]}

#[[ Nhung tam user NOI RO ly do trong hai ban quay — in rieng tung tam de doi
#   chieu bang mat, ngoai con so cong. ]]
ANH_DA_NOI = {"TrainTool": [
    "dsc08564", "dsc08576", "dsc08593", "dsc08607", "dsc08612", "dsc08656", "dsc08665",
    "dsc08668", "dsc08669", "dsc08670", "dsc08671", "dsc08672", "dsc08681", "dsc08688",
    "dsc08693", "dsc08699", "say06085", "hiu_4051", "hiu_4055", "bne02293", "bne02296",
    "bne02302", "bne02316", "hiu_4093", "hiu_4098", "hiu_4100", "hiu_4106", "hiu_4113",
    "hiu_4161", "bne02387", "say07160", "say07166", "say07172"]}

NGUONG = dict(exp_b=0.30, exp_b_pct=2.0, temp_b=250.0, tint_b=4.0, wb_b_pct=5.0,
              hl_b=10.0, hl_b_pct=5.0, it_nhat=8)
TRUONG = {"exp": ("Exposure2012", "new_exposure"), "temp": ("Temperature", "new_temp"),
          "tint": ("Tint", "new_tint"), "hl": ("Highlights2012", "new_highlights")}
SAI_SUA = {"exp": 0.005, "temp": 1.0, "tint": 1.0, "hl": 1.0}


def ten(p) -> str:
    return ntpath.splitext(ntpath.basename(str(p).replace("/", "\\")))[0].strip().lower()


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ nap du lieu
def nap_do(thu_muc: Path) -> dict:
    p = next(iter(sorted(thu_muc.glob("do_*.json.gz"))), None)
    if p is None:
        return {}
    with gzip.open(p, "rt", encoding="utf-8") as fh:
        goi = json.load(fh)
    for r in goi["items"]:
        r["dt_obj"] = datetime.fromisoformat(r["dt"])
    return goi


def nap_preset(thu_muc: Path) -> dict:
    """Preset goc tung anh (truoc khi tool cham) tu _autotone_baseline.tsv."""
    p = thu_muc / at.BASELINE_NAME
    out = {}
    if not p.is_file():
        return out
    dong = p.read_text(encoding="utf-8").splitlines()
    cot = dong[0].split("\t")
    for ln in dong[1:]:
        v = ln.split("\t")
        if v and v[0]:
            out[ten(v[0])] = {cot[i]: v[i] for i in range(1, min(len(cot), len(v))) if v[i] != ""}
    return out


def _moc_ten(p: Path) -> str:
    m = re.search(r"(\d{8}_\d{6})", p.name)
    return m.group(1) if m else ""


def nap_dap_an(thu_muc: Path, buoi: str, jobs_dir: Path) -> dict:
    """{ten: {"user": {...}, "tool": {...}, "rating", "thu_tu"}} hoac {} neu thieu."""
    chup = xbc.ban_moi_nhat(thu_muc)
    if chup is None:
        return {}
    moc = _moc_ten(chup)
    dones = [q for q in sorted(jobs_dir.glob(f"apply_*_{buoi}.done"))
             if "khoiphuc" not in q.name.lower() and _moc_ten(q) and _moc_ten(q) <= moc]
    if not dones:
        return {}
    tool = {}
    with io.open(dones[-1], encoding="utf-8-sig", newline="") as fh:
        for i, r in enumerate(csv.DictReader(fh, delimiter="\t")):
            tool[ten(r["path"])] = (i, r)
    user = xbc.doc_ban_chup(chup)
    out = {}
    for k, (i, t) in tool.items():
        u = user.get(k)
        if u is None:
            continue
        out[k] = {"thu_tu": i, "rating": u["rating"],
                  "user": {c: _f(u["s"].get(c)) for c, _ in TRUONG.values()},
                  "tool": {c: _f(t.get(c)) for c, _ in TRUONG.values()}}
    out["__nguon__"] = f"{chup.name} vs {dones[-1].name}"
    return out


# ------------------------------------------------------------------ chay plan()
def chay(goi: dict, preset: dict, cfg: dict) -> dict:
    items = copy.deepcopy(goi["items"])
    exp = {}
    for r in items:
        p = preset.get(ten(r["path"]))
        if p:
            exp[at.khoa_duong_dan(r["path"])] = dict(p)    # cung khoa voi attach_catalog_settings
    #[[ Thu muc RONG cho plan(): khong de no doc _autotone_baseline.tsv theo
    #   duong dan (khoa duong dan Windows/Linux khac nhau) — preset da nam san
    #   trong `exp`, khop theo ten file. ]]
    with tempfile.TemporaryDirectory() as td, \
            contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        at.plan(items, cfg, Path(td), exp)
    return {ten(r["path"]): r for r in items}


def cfg_goc(max_ev_up: float = 1.0) -> dict:
    #[[ Dung cau hinh GUI luc day: DEFAULTS + nguon catalog + o "max EV keo
    #   sang" cua GUI (xem chon_tran_keo_sang). bo_qua_nguoi_sua TAT: bat len
    #   thi chinh nhung anh co dich dung bi loai khoi bai kiem. ]]
    return dict(at.DEFAULTS, source="catalog", bo_qua_nguoi_sua=False, max_ev_up=max_ev_up)


TRAN_THU = (1.0, 1.5, 2.0, 2.5, 3.0)


def chon_tran_keo_sang(goi, preset, dap) -> tuple:
    """O "max EV keo sang" cua GUI KHONG duoc luu lai, nen do nguoc tu lan day:
    lay muc tai hien dung nhieu anh nhat. (muc, so khop, tong).

    #[[ Gap that 3/10: chay voi 1.00 (mac dinh GUI) chi khop 1437/1502 anh
    #   TrainTool; DSC08727-31 tool da day +1.55/+1.60, BNM00350 +2.34 — vuot
    #   tran 1.00 + 0.75. Voi 3.00 khop 1502/1502: hom do user de o 3.0.
    #   So sanh voi mot luot goc SAI cau hinh thi moi con so cong deu lech. ]]
    """
    tot = (1.0, -1, 0)
    for up in TRAN_THU:
        kq = chay(goi, preset, cfg_goc(up))
        n = m = 0
        for k, a in dap.items():
            if k.startswith("__") or k not in kq or a["tool"].get("Exposure2012") is None:
                continue
            n += 1
            m += abs(float(kq[k]["new_exposure"]) - a["tool"]["Exposure2012"]) < 0.006
        if m > tot[1]:
            tot = (up, m, n)
    return tot


# ------------------------------------------------------------------ cham
def _cham_truong(ds, kq0, kq1, f_new):
    """[(user, cu, moi)] -> (gan, xa, sai tb cu, sai tb moi, n)."""
    rows = []
    for k, u in ds:
        a, b = kq0.get(k), kq1.get(k)
        if a is None or b is None or a.get(f_new) is None or b.get(f_new) is None:
            continue
        rows.append({"nguoi_dung": u, "ev_cu": float(a[f_new]), "ev_moi": float(b[f_new])})
    if not rows:
        return 0, 0, 0.0, 0.0, 0
    gan, xa, sc, sm = kg.cham(rows)
    return gan, xa, sc, sm, len(rows)


def _dung(ds, kq0, kq1, f_new, nguong):
    n = dong = 0
    for k in ds:
        a, b = kq0.get(k), kq1.get(k)
        if a is None or b is None or a.get(f_new) is None or b.get(f_new) is None:
            continue
        n += 1
        if abs(float(b[f_new]) - float(a[f_new])) > nguong:
            dong += 1
    return dong, n


def tap_kiem(buoi: str, dap: dict, kq0: dict) -> dict:
    """Chia anh thanh tap SUA (co dich) / DUYET cho tung truong."""
    tap = {t: {"sua": [], "duyet": []} for t in TRUONG}
    pham_vi = DA_DUYET_THEO_BUOI.get(buoi)
    for k, a in dap.items():
        if k.startswith("__") or k not in kq0 or a["rating"] == 1:
            continue
        da_xem = (pham_vi is None
                  or any(lo <= a["thu_tu"] <= hi for lo, hi in pham_vi))
        for t, (c, _) in TRUONG.items():
            u, tl = a["user"].get(c), a["tool"].get(c)
            if u is None or tl is None:
                continue
            if abs(u - tl) > SAI_SUA[t]:
                tap[t]["sua"].append((k, u))
            elif da_xem:
                tap[t]["duyet"].append(k)
    return tap


def tap_tu_gu(folder_name: str, kq0: dict) -> dict:
    """Khong co ban chup: dich Exposure tu corrections.csv + gu.csv (kiem_gu)."""
    chuan = kg.dich_dung(Path(folder_name), HERE, None)
    tap = {t: {"sua": [], "duyet": []} for t in TRUONG}
    for k in kq0:
        if k in chuan:
            tap["exp"]["sua"].append((k, chuan[k][0]))
        else:
            tap["exp"]["duyet"].append(k)
    return tap


def nhom_dong_bo(dap: dict, kq0: dict) -> list:
    """Loat >= 3 anh lien nhau (cung may) ma user de CUNG MOT Exposure —
    'mot anh sang mot ket qua' theo chinh mat user. Chi anh co mat."""
    ds = sorted((a["thu_tu"], k) for k, a in dap.items()
                if not k.startswith("__") and k in kq0 and a["rating"] != 1
                and a["user"].get("Exposure2012") is not None and kq0[k].get("faces_n"))
    nhom, cur = [], []
    for _, k in ds:
        if cur:
            k0 = cur[-1]
            if (abs(dap[k]["user"]["Exposure2012"] - dap[k0]["user"]["Exposure2012"]) < 0.005
                    and kq0[k].get("model") == kq0[k0].get("model")):
                cur.append(k)
                continue
            if len(cur) >= 3:
                nhom.append(cur)
        cur = [k]
    if len(cur) >= 3:
        nhom.append(cur)
    return nhom


def do_lech_nhom(nhom: list, kq: dict) -> tuple:
    """(trung vi dai Exposure trong nhom, so nhom dai > 0.15)."""
    dai = []
    for g in nhom:
        v = [float(kq[k]["new_exposure"]) for k in g if k in kq]
        if len(v) >= 3:
            dai.append(max(v) - min(v))
    if not dai:
        return 0.0, 0, 0
    dai.sort()
    return dai[len(dai) // 2], sum(1 for x in dai if x > 0.15), len(dai)


# ------------------------------------------------------------------ muc 4
def hoc_bu_theo_may(goi, preset, dap, cfg_bon) -> tuple:
    kq = chay(goi, preset, cfg_bon)
    pham_vi = DA_DUYET_THEO_BUOI.get(BUOI_HOC)
    lech = []
    for k, a in dap.items():
        if k.startswith("__") or k not in kq or a["rating"] == 1:
            continue
        if pham_vi and not any(lo <= a["thu_tu"] <= hi for lo, hi in pham_vi):
            continue
        r = kq[k]
        if BU_MAY not in str(r.get("model") or "").upper() or not r.get("faces_n"):
            continue
        u = a["user"].get("Exposure2012")
        if u is None:
            continue
        lech.append(u - float(r["new_exposure"]))
    if not lech:
        return {}, 0.0, 0
    lech.sort()
    x = lech[len(lech) // 2]
    if abs(x) >= BU_MIN_EV and len(lech) >= BU_MIN_ANH:
        return {"bu_exp_theo_may": {BU_MAY: round(x, 2)}}, x, len(lech)
    return {}, x, len(lech)


# ------------------------------------------------------------------ bao cao
def _ket(gan, xa, n):
    if n == 0:
        return "-"
    if n < NGUONG["it_nhat"]:
        return "chua ket luan"
    return "DAT" if gan >= xa else "KHONG DAT"


def bao_cao_buoi(buoi, goi, preset, dap, tap, nhom, bien, out):
    p = lambda s="": out.append(s)   # noqa: E731
    kq0 = bien["goc"]
    p(f"\n{'=' * 78}\nBUOI {buoi} — {len(kq0)} anh"
      + (f"  | dap an: {dap.get('__nguon__')}" if dap.get("__nguon__") else
         "  | dap an: corrections.csv + gu.csv (chi Exposure)"))
    p("  " + " | ".join(f"{t}: sua {len(tap[t]['sua'])}, duyet {len(tap[t]['duyet'])}"
                        for t in TRUONG))
    ket = {}
    for ten_bien, kq1 in bien.items():
        if ten_bien == "goc":
            continue
        p(f"\n  --- {ten_bien}")
        dat_ca = True
        for t, (_, f_new) in TRUONG.items():
            gan, xa, sc, sm, n = _cham_truong(tap[t]["sua"], kq0, kq1, f_new)
            if t == "exp":
                nb = NGUONG["exp_b"]
                dong, nd = _dung(tap[t]["duyet"], kq0, kq1, f_new, nb)
                pct_b = 100.0 * dong / max(nd, 1)
                ok_b = pct_b < NGUONG["exp_b_pct"]
                mo_b = f"B {dong}/{nd} xe dich >{nb} EV = {pct_b:.2f}% (<{NGUONG['exp_b_pct']}%)"
            elif t in ("temp", "tint"):
                duyet = [k for k in tap["temp"]["duyet"] if k in set(tap["tint"]["duyet"])
                         and "NIKON" not in str(kq0[k].get("model") or "").upper()]
                d1, nd = _dung(duyet, kq0, kq1, "new_temp", NGUONG["temp_b"])
                d2, _ = _dung(duyet, kq0, kq1, "new_tint", NGUONG["tint_b"])
                dong = len({k for k in duyet
                            if abs(kq1[k]["new_temp"] - kq0[k]["new_temp"]) > NGUONG["temp_b"]
                            or abs(kq1[k]["new_tint"] - kq0[k]["new_tint"]) > NGUONG["tint_b"]})
                pct_b = 100.0 * dong / max(nd, 1)
                ok_b = pct_b < NGUONG["wb_b_pct"]
                mo_b = (f"B(WB, tru Nikon) {dong}/{nd} xe dich >{NGUONG['temp_b']:.0f}K/"
                        f">{NGUONG['tint_b']:.0f}Tint = {pct_b:.2f}% (<{NGUONG['wb_b_pct']}%)")
            else:
                dong, nd = _dung(tap[t]["duyet"], kq0, kq1, f_new, NGUONG["hl_b"])
                pct_b = 100.0 * dong / max(nd, 1)
                ok_b = pct_b < NGUONG["hl_b_pct"]
                mo_b = (f"B {dong}/{nd} xe dich >{NGUONG['hl_b']:.0f} = {pct_b:.2f}% "
                        f"(<{NGUONG['hl_b_pct']}%)")
            ka = _ket(gan, xa, n)
            doi_gi = sum(1 for k in kq0 if k in kq1 and kq0[k].get(f_new) is not None
                         and abs(float(kq1[k][f_new]) - float(kq0[k][f_new])) > SAI_SUA[t])
            if doi_gi == 0:
                p(f"    {t:4}: khong doi anh nao")
                continue
            if ka == "KHONG DAT" or not ok_b:
                dat_ca = False
            don = "EV" if t == "exp" else ("K" if t == "temp" else "")
            p(f"    {t:4}: doi {doi_gi} anh | A {ka}: gan {gan} / xa {xa} / {n} sua, "
              f"sai tb {sc:.3f}->{sm:.3f}{don} | {mo_b} -> {'DAT' if ok_b else 'KHONG DAT'}")
        if nhom:
            m0, c0, n0 = do_lech_nhom(nhom, kq0)
            m1, c1, _ = do_lech_nhom(nhom, kq1)
            p(f"    mot anh sang: {n0} loat user dong bo 1 Exposure — dai Exposure tool "
              f"trung vi {m0:.2f} -> {m1:.2f} EV, loat lech >0.15: {c0} -> {c1}")
        ket[ten_bien] = dat_ca
        p(f"    => {'QUA CONG' if dat_ca else 'TRUOT'}")

    ds_noi = [k for k in ANH_DA_NOI.get(buoi, []) if k in kq0 and k in dap]
    if ds_noi and "ca 5 muc" in bien:
        kq5 = bien["ca 5 muc"]
        p(f"\n  NHUNG TAM ANH DA NOI LY DO — user | tool da day | ca 5 muc"
          f"   (Exp, Temp, Tint, HL)")
        for k in ds_noi:
            u, t = dap[k]["user"], dap[k]["tool"]
            r5 = kq5[k]
            def _o(a, c, w, n=0):
                v = a.get(c)
                return f"{v:+{w}.{n}f}" if v is not None else " " * w
            p(f"    {k:9} Exp {_o(u, 'Exposure2012', 6, 2)} |{_o(t, 'Exposure2012', 6, 2)} |"
              f"{float(r5['new_exposure']):+6.2f}   Temp {_o(u, 'Temperature', 5)} |"
              f"{_o(t, 'Temperature', 5)} |{int(r5['new_temp']):5d}   Tint {_o(u, 'Tint', 3)} |"
              f"{_o(t, 'Tint', 3)} |{int(r5['new_tint']):+3d}   HL {_o(u, 'Highlights2012', 3)} |"
              f"{_o(t, 'Highlights2012', 3)} |{int(r5['new_highlights']):+3d}")
    return ket


def ghi_csv(dest: Path, dap, bien):
    cot = ["file", "model", "thu_tu", "rating"]
    for t, (c, f_new) in TRUONG.items():
        cot += [f"user_{t}", f"tool_day_{t}"] + [f"{b}_{t}" for b in bien]
    cot += ["notes_ca5"]
    kq0 = bien["goc"]
    with io.open(dest, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cot)
        for k in sorted(kq0, key=lambda k: dap.get(k, {}).get("thu_tu", 10 ** 9)):
            a = dap.get(k, {})
            row = [k, kq0[k].get("model", ""), a.get("thu_tu", ""), a.get("rating", "")]
            for t, (c, f_new) in TRUONG.items():
                row += [a.get("user", {}).get(c, ""), a.get("tool", {}).get(c, "")]
                row += [bien[b].get(k, {}).get(f_new, "") for b in bien]
            row.append(bien.get("ca 5 muc", {}).get(k, {}).get("notes", ""))
            w.writerow(row)


def main(argv=None) -> int:
    for _l in (sys.stdout, sys.stderr):
        try:
            _l.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass
    goc_do = HERE / "Claude outputs" / "do"
    jobs_dir = at.LR_JOB_DIR
    a = list(argv if argv is not None else sys.argv[1:])
    if "--jobs" in a:
        i = a.index("--jobs")
        jobs_dir = Path(a[i + 1])
        del a[i:i + 2]
    if "--do" in a:
        i = a.index("--do")
        goc_do = Path(a[i + 1])
        del a[i:i + 2]
    tach = "--tach" in a
    if tach:
        a.remove("--tach")
    buoi_ds = a or sorted(p.name for p in goc_do.iterdir() if p.is_dir())
    if BUOI_HOC in buoi_ds:
        buoi_ds.remove(BUOI_HOC)
        buoi_ds.insert(0, BUOI_HOC)
    out: list = []
    t0 = time.time()
    du_lieu = {}
    tran: dict = {}
    for b in buoi_ds:
        d = goc_do / b
        goi = nap_do(d)
        if not goi:
            out.append(f"[!] {b}: khong co do_{b}.json.gz — bo qua")
            continue
        preset = nap_preset(d)
        dap = nap_dap_an(d, b, jobs_dir)
        up, khop, tong_so = (chon_tran_keo_sang(goi, preset, dap) if dap
                             else (1.0, 0, 0))
        tran[b] = up
        if dap:
            #[[ Tai hien: luot goc phai ra DUNG so tool da day (cung code, cung
            #   cau hinh). Lech nhieu = do sang da doi tu luc day (code moi hon,
            #   bot anh trong thu muc) — cong van so tuong doi voi luot goc. ]]
            out.append(f"[{b}] tai hien lan day: {khop}/{tong_so} anh khop Exposure "
                       f"({100.0 * khop / max(tong_so, 1):.1f}%) voi max EV keo sang = {up}")
        du_lieu[b] = (goi, preset, dap)

    # ---- Muc 4: hoc tren buoi hoc, bon muc kia BAT
    bon = {}
    for k_, v_ in DE_XUAT.items():
        if v_:
            bon.update(v_)
    bu, x, n_bu = {}, 0.0, 0
    if BUOI_HOC in du_lieu and du_lieu[BUOI_HOC][2]:
        g, pr, dp = du_lieu[BUOI_HOC]
        bu, x, n_bu = hoc_bu_theo_may(g, pr, dp, dict(cfg_goc(tran[BUOI_HOC]), **bon))
    out.append(f"Muc 4 hoc tren {BUOI_HOC}: trung vi (user - tool) anh {BU_MAY} co mat da duyet"
               f" = {x:+.3f} EV tren {n_bu} anh -> "
               + (f"bu_exp_theo_may = {bu}" if bu else
                  f"KHONG DU BANG CHUNG (can |x| >= {BU_MIN_EV} va >= {BU_MIN_ANH} anh) — bo muc 4"))
    de_xuat = {k_: (bu if v_ is None else v_) for k_, v_ in DE_XUAT.items()}
    ca5 = {}
    for v_ in de_xuat.values():
        ca5.update(v_ or {})

    tong = {}
    for b, (goi, preset, dap) in du_lieu.items():
        c0 = cfg_goc(tran[b])
        bien = {"goc": chay(goi, preset, c0)}
        for ten_m, dx in de_xuat.items():
            if dx:
                bien[ten_m] = chay(goi, preset, dict(c0, **dx))
        bien["ca 5 muc"] = chay(goi, preset, dict(c0, **ca5))
        if tach:
            for ten_m, dx in TACH.items():
                bien[ten_m] = chay(goi, preset, dict(c0, **dx))
        kq0 = bien["goc"]
        if dap:
            tap = tap_kiem(b, dap, kq0)
            nhom = nhom_dong_bo(dap, kq0)
        else:
            tap = tap_tu_gu(b, kq0)
            nhom = []
        tong[b] = bao_cao_buoi(b, goi, preset, dap, tap, nhom, bien, out)
        try:
            ghi_csv(goc_do / b / f"kiem_2ban_quay_{b}.csv", dap, bien)
        except OSError as ex:
            out.append(f"[!] khong ghi duoc csv: {ex}")

    out.append(f"\n{'=' * 78}\nTONG KET (de xuat chot truoc khi chay):")
    for k_, v_ in de_xuat.items():
        out.append(f"  {k_:18} {json.dumps(v_, ensure_ascii=False) if v_ else '(bo)'}")
    for b, ket in tong.items():
        nhan = " (TRONG MAU — buoi da dung de thiet ke)" if b == BUOI_HOC else ""
        out.append(f"  {b}{nhan}: " + ", ".join(f"{k_}: {'qua' if v_ else 'TRUOT'}"
                                                 for k_, v_ in ket.items()))
    out.append(f"({time.time() - t0:.0f}s)")
    txt = "\n".join(out)
    print(txt)
    try:
        (goc_do / "ket_qua_2ban_quay.txt").write_text(txt, encoding="utf-8")
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
