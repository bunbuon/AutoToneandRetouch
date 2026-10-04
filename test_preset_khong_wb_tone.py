#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quy trinh moi 3/10: preset BO TRONG nhom WB va nhom Basic Tone — kiem bang
ham THAT (plan, decide, compute_values, write_lr_job, save_baseline,
attach_catalog_settings, apply_to_sidecar, write_sidecars).

CHUYEN DANG SUA
    User de xuat: import RAW -> ap preset KHONG ap White Balance va Basic Tone.
    WB o lai As Shot thi Lightroom render giong preview cua may (goc benh da
    vang buoi Hiu: may dat tay 3600-4000K, preset ep 5250K). Tool phai tu ghi
    hai nhom do.

    Buoc nay CHUA doi cach can mau: tinh tren nen SAY (5250/+16, Contrast 5,
    Highlights/Shadows moc 16, Whites -25, Blacks -18) nen ra Y HET quy trinh
    cu. Hoc lai WB theo As Shot la buoc sau, can so As Shot that.

    BUOC 2 (3/10 chieu, wb_theo_asshot BAT trong DEFAULTS) co bai rieng
    test_wb_asshot.py. Bai nay kiem BUOC 1 nen chay() TAT wb_theo_asshot —
    TRU duong sidecar: o do buoc 2 khong ap (xem plan()), nen kiem_sidecar
    chay voi DEFAULTS va phai van y het quy trinh cu.

TINH HUONG
    1. Cung mot buoi, ba kieu ban xuat: plugin cu + preset day du, plugin moi +
       preset day du, plugin moi + preset bo trong WB/Tone -> Exposure,
       Highlights, Shadows, Temp, Tint giong het tung anh.
    2. Bo trong WB/Tone thi job ghi Contrast/Whites/Blacks = 5/-25/-18 va LUON
       ghi Temp/Tint — ke ca canh tool khong doi WB (khong ghi la anh o lai
       As Shot). Preset day du thi ba cot do de trong, WB nhu cu.
    3. Chay lai sau khi day (catalog da mang so tool ghi, moc tren dia) -> ra
       y het lan dau: moc phai giu bon cot moi.
    4. Moc cu cua quy trinh cu + catalog dang As Shot / Tone 0 (import lai) ->
       lay catalog lam nen, van tu ghi du.
    5. Preset ap Tone mot phan (Contrast/Whites/Blacks 0 nhung Highlights 16)
       -> KHONG coi la bo trong: ton trong preset, khong ghi ba cot.
    6. Ban xuat co AsShotTemperature (phong khi Lightroom tra ve) va bat
       wb_theo_may_pull -> van y het quy trinh cu (nen phai che ca hai cho).
    7. Duong sidecar .xmp: moc atn ghi theo nen, chay lai ra y het.
"""
from __future__ import annotations

import contextlib
import copy
import csv
import io
import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at          # noqa: E402
import test_2ban_quay as tq    # noqa: E402

TRUONG = ("new_exposure", "new_highlights", "new_shadows", "new_temp", "new_tint")
DAY_DU_CU = {"Exposure2012": "0", "Highlights2012": "16", "Shadows2012": "16",
             "Temperature": "5250", "Tint": "16"}
DAY_DU_MOI = dict(DAY_DU_CU, WhiteBalance="Custom", Contrast2012="5",
                  Whites2012="-25", Blacks2012="-18")
DA_VANG = tq._lin((236, 170, 120))       # da ngả vàng -> tool kéo WB


def as_shot(i: int) -> dict:
    """Ban xuat cua anh import theo quy trinh moi: WB As Shot (moi anh mot so,
    nhu may dat tay / Auto), Tone deu 0."""
    return {"WhiteBalance": "As Shot", "Temperature": str(3600 + 50 * i), "Tint": str(3 + i % 4),
            "Exposure2012": "0", "Contrast2012": "0", "Highlights2012": "0",
            "Shadows2012": "0", "Whites2012": "0", "Blacks2012": "0"}


def buoi() -> list:
    """Hai canh: canh 1 da dung mau dich (tool khong doi WB), canh 2 da vang."""
    ds = []
    for i in range(6):
        ds.append(tq.anh(f"A{i}", i * 8, -1.6 + 0.12 * i, da=tq.DA_TRONG, may_K=3600))
    for i in range(6):
        ds.append(tq.anh(f"B{i}", 1500 + i * 8, -0.7 - 0.15 * i, da=DA_VANG, may_K=4000))
    return ds


def khoa(r) -> str:
    return os.path.normcase(os.path.abspath(r["path"]))


def chay(items, ban_xuat, thu_muc: Path, **kw) -> dict:
    """plan() that, nguon catalog; ban_xuat(i) -> dict thong so catalog anh i."""
    items = copy.deepcopy(items)
    exp = {khoa(r): dict(ban_xuat(i)) for i, r in enumerate(items)}
    cfg = dict(at.DEFAULTS, source="catalog", bo_qua_nguoi_sua=False, wb_theo_asshot=False)
    cfg.update(kw)
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        at.plan(items, cfg, thu_muc, exp)
    return {r["path"]: r for r in items}


def doc_job(p: Path) -> dict:
    with io.open(p, encoding="utf-8", newline="") as fh:
        return {row["path"]: row for row in csv.DictReader(fh, delimiter="\t")}


def so_sanh(loi, ten, a, b):
    for k in a:
        for f in TRUONG:
            if abs(float(a[k][f]) - float(b[k][f])) > 1e-6:
                loi.append(f"{ten}: {k.split(chr(92))[-1]} {f} {a[k][f]} != {b[k][f]}")
                return


def main() -> int:
    loi: list = []
    goc = buoi()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        at.LR_JOB_DIR = td / "jobs"          # khong bao gio ghi vao plugin that
        (td / "a1").mkdir(); (td / "a2").mkdir(); (td / "b").mkdir()

        # 1. ba kieu ban xuat -> cung so
        a1 = chay(goc, lambda i: DAY_DU_CU, td / "a1")
        a2 = chay(goc, lambda i: DAY_DU_MOI, td / "a2")
        b = chay(goc, as_shot, td / "b")
        so_sanh(loi, "plugin moi + preset day du", a1, a2)
        so_sanh(loi, "preset bo trong WB/Tone", a1, b)
        if not any(abs(r["temp_adj"]) > 50 for r in a1.values()):
            loi.append("Canh da vang khong lam tool doi WB — bai kiem khong do duoc gi")
        if not any(r["new_temp"] == r["old_temp"] and r["new_tint"] == r["old_tint"]
                   for r in a1.values()):
            loi.append("Khong co anh nao tool giu nguyen WB — khong kiem duoc o 'phai ghi'")
        if any(r.get("nen_tone") or r.get("nen_wb") for r in list(a1.values()) + list(a2.values())):
            loi.append("Preset day du ma bi coi la bo trong WB/Tone")
        if not all(r.get("nen_tone") and r.get("nen_wb") for r in b.values()):
            loi.append("Preset bo trong WB/Tone ma khong duoc nhan ra")

        # 2. job: ba cot Tone + WB bat buoc
        ja = doc_job(at.write_lr_job(list(a1.values()), "a1", td / "ja"))
        jb = doc_job(at.write_lr_job(list(b.values()), "b", td / "jb"))
        for p, row in jb.items():
            if (row.get("Contrast2012"), row.get("Whites2012"), row.get("Blacks2012")) != ("5", "-25", "-18"):
                loi.append(f"Job bo trong Tone: {p} Contrast/Whites/Blacks = "
                           f"{row.get('Contrast2012')}/{row.get('Whites2012')}/{row.get('Blacks2012')}")
                break
        for p, row in jb.items():
            if not row.get("Temperature") or not row.get("Tint"):
                loi.append(f"Job bo trong WB: {p} de trong Temp/Tint -> anh o lai As Shot")
                break
        for p, row in ja.items():
            if row.get("Contrast2012") or row.get("Whites2012") or row.get("Blacks2012"):
                loi.append(f"Job preset day du lai ghi Contrast/Whites/Blacks ({p})")
                break
        trong_a = sum(1 for row in ja.values() if not row.get("Temperature"))
        if trong_a == 0:
            loi.append("Job preset day du phai de trong WB o anh tool khong doi (hanh vi cu)")
        for p, row in jb.items():
            if row["Temperature"] != str(int(a1[p]["new_temp"])) or \
                    row["Exposure2012"] != ja[p]["Exposure2012"]:
                loi.append(f"Job bo trong WB/Tone khac so voi quy trinh cu ({p})")
                break

        # 3. chay lai sau khi day: moc tren dia, catalog mang so tool ghi
        at.write_sidecars(list(b.values()), dict(at.DEFAULTS, source="catalog"), td / "b")
        moc = at.load_baseline(td / "b")
        m0 = next(iter(moc.values()), {})
        if m0.get("WhiteBalance") != "As Shot" or m0.get("Whites2012") != "0":
            loi.append(f"Moc khong giu cot WhiteBalance/Whites2012: {sorted(m0)}")

        def sau_day(i):
            r = b[goc[i]["path"]]
            return {"WhiteBalance": "Custom", "Temperature": str(r["new_temp"]),
                    "Tint": str(r["new_tint"]), "Exposure2012": str(r["new_exposure"]),
                    "Highlights2012": str(r["new_highlights"]),
                    "Shadows2012": str(r["new_shadows"]),
                    "Contrast2012": "5", "Whites2012": "-25", "Blacks2012": "-18"}
        b2 = chay(goc, sau_day, td / "b")
        so_sanh(loi, "chay lai sau khi day", b, b2)
        if not all(r.get("nen_tone") and r.get("nen_wb") for r in b2.values()):
            loi.append("Chay lai: khong con nhan ra anh dang o quy trinh moi (moc mat cot?)")

        # 4. moc cu (quy trinh cu) + catalog import lai theo quy trinh moi
        (td / "c").mkdir()
        at.save_baseline(td / "c", {khoa(r): dict(DAY_DU_CU) for r in goc})
        c = chay(goc, as_shot, td / "c")
        so_sanh(loi, "moc cu + import lai", a1, c)
        if not all(r.get("nen_tone") and r.get("nen_wb") for r in c.values()):
            loi.append("Moc cu + catalog As Shot/Tone 0: khong tu ghi WB va ba thanh Tone")
        if not all("moc-cu-khac-quy-trinh" in r.get("notes", "") for r in c.values()):
            loi.append("Moc cu + catalog As Shot/Tone 0: thieu ghi chu moc-cu-khac-quy-trinh")
        # moc QUY TRINH MOI + catalog As Shot: van dung moc (chay lai binh thuong)
        (td / "d").mkdir()
        at.save_baseline(td / "d", {khoa(r): as_shot(i) for i, r in enumerate(goc)})
        d_ = chay(goc, as_shot, td / "d")
        if any("moc-cu-khac-quy-trinh" in r.get("notes", "") for r in d_.values()):
            loi.append("Moc quy trinh moi bi coi la moc cu")

        # 5. preset ap Tone mot phan -> ton trong preset
        (td / "e").mkdir()
        mot_phan = lambda i: dict(as_shot(i), Highlights2012="16")   # noqa: E731
        e = chay(goc, mot_phan, td / "e")
        if any(r.get("nen_tone") for r in e.values()):
            loi.append("Preset co Highlights 16 ma bi coi la bo trong Tone")
        if any(r.get("new_Contrast2012") is not None for r in e.values()):
            loi.append("Preset ap Tone mot phan ma tool ghi de Contrast")

        # 6. AsShotTemperature co mat + wb_theo_may_pull bat
        co_as = lambda i: dict(as_shot(i), AsShotTemperature=str(3600 + 50 * i),  # noqa: E731
                               AsShotTint="3")
        (td / "f1").mkdir(); (td / "f2").mkdir(); (td / "g1").mkdir(); (td / "g2").mkdir()
        so_sanh(loi, "ban xuat co AsShotTemperature",
                chay(goc, lambda i: DAY_DU_CU, td / "f1"), chay(goc, co_as, td / "f2"))
        so_sanh(loi, "wb_theo_may_pull 0.35",
                chay(goc, lambda i: DAY_DU_CU, td / "g1", wb_theo_may_pull=0.35),
                chay(goc, as_shot, td / "g2", wb_theo_may_pull=0.35))

        # 7. duong sidecar
        loi += kiem_sidecar(goc, td / "xmp")

        # 8. plugin CU (khong co cot WhiteBalance) + preset bo trong Tone -> phai noi
        cu_khong_tone = lambda i: {k: v for k, v in as_shot(i).items()   # noqa: E731
                                   if k not in ("WhiteBalance", "Contrast2012",
                                                "Whites2012", "Blacks2012")}
        (td / "h1").mkdir(); (td / "h2").mkdir(); (td / "h3").mkdir()
        chay(goc, cu_khong_tone, td / "h1")
        if not at.CANH_BAO_PLUGIN:
            loi.append("Plugin cu + Highlights/Shadows 0: khong canh bao Reload plugin")
        chay(goc, lambda i: DAY_DU_CU, td / "h2")
        if at.CANH_BAO_PLUGIN:
            loi.append("Plugin cu + preset day du ma van canh bao (bao nham quy trinh cu)")
        chay(goc, as_shot, td / "h3")
        if at.CANH_BAO_PLUGIN:
            loi.append("Plugin moi ma van canh bao plugin cu")
        # 8b. giao dien NOI ra canh bao — goi ham THAT App._fill_table
        loi += kiem_giao_dien(list(chay(goc, cu_khong_tone, td / "h1").values()))

    for m in loi:
        print("  [!]", m)
    print("TAT CA DAT" if not loi else f"{len(loi)} LOI")
    return 1 if loi else 0


def kiem_giao_dien(items) -> list:
    """App._fill_table THAT tren mot App gia chi co dung thu ham do dung toi.
    Khong co tkinter (may chay kiem khong cai) thi bo qua, co noi ra."""
    try:
        import autotone_gui as gui
    except Exception as ex:                          # noqa: BLE001
        print(f"  (bo qua phan giao dien: {ex.__class__.__name__}: {ex})")
        return []
    if not at.CANH_BAO_PLUGIN:
        return ["Giao dien: chay plan() voi plugin cu ma CANH_BAO_PLUGIN rong"]

    class Cay:
        def get_children(self):
            return []

        def delete(self, *a):
            pass

        def insert(self, *a, **k):
            pass

    class Nhan:
        def __init__(self):
            self.text = ""

        def configure(self, text="", foreground=None):
            self.text = text

    class Gia:
        def __init__(self):
            self.tree, self.lbl_hint, self.items = Cay(), Nhan(), items
            #[[ 3/10 toi: _fill_table con do lai LUOI ANH va dong tong ket o
            #   dau trang (lbl_tong) — App gia phai co ca hai, khong thi bai
            #   nay chet o AttributeError truoc khi toi duoc cho no can kiem. ]]
            self.lbl_tong = Nhan()
            self.cfg = dict(at.DEFAULTS, mode="scene")
            self.trang_thai = ""

        def status(self, msg, mau=None):
            self.trang_thai = msg

        def _cap_nhat_luoi(self, giu_cuon=False):
            pass

        def _set_busy(self, b):
            pass

    g = Gia()
    g._row, g._tags = gui.App._row, gui.App._tags
    gui.App._fill_table(g)
    loi = []
    if "Reload" not in g.trang_thai:
        loi.append(f"Giao dien: dong trang thai khong noi plugin cu: {g.trang_thai[:120]}")
    if "plugin" not in g.lbl_hint.text.lower():
        loi.append(f"Giao dien: nhan goi y khong noi plugin cu: {g.lbl_hint.text}")
    return loi


XMP = """<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"
   xmp:MetadataDate="2026-10-03T07:00:00+07:00"
{thuoc_tinh}/>
 </rdf:RDF>
</x:xmpmeta>
"""


def _xmp(crs: dict) -> str:
    return XMP.format(thuoc_tinh="\n".join(f'   crs:{k}="{v}"' for k, v in crs.items()))


def kiem_sidecar(goc, thu_muc: Path) -> list:
    loi = []
    cfg = dict(at.DEFAULTS, source="sidecar", lr_push=False)
    kq = {}
    for ten, ban in (("a", lambda i: dict(DAY_DU_MOI, Tint="+16")), ("b", as_shot)):
        d = thu_muc / ten
        d.mkdir(parents=True)
        items = copy.deepcopy(goc)
        for i, r in enumerate(items):
            sc = d / (Path(r["path"].replace("\\", "/")).stem + ".xmp")
            sc.write_text(_xmp(ban(i)), encoding="utf-8")
            r["sidecar"] = str(sc)
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            at.plan(items, cfg, d)
        kq[ten] = (items, {r["path"]: r for r in items})
    so_sanh(loi, "sidecar: preset bo trong WB/Tone", kq["a"][1], kq["b"][1])

    items_b = kq["b"][0]
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        at.write_sidecars(items_b, cfg, thu_muc / "b", backup_dir=thu_muc / "bk")
    txt = Path(items_b[0]["sidecar"]).read_text(encoding="utf-8")
    crs, atn = at.read_crs(txt), at.read_ns(txt, at.ATN_PREFIX)
    if (crs.get("Contrast2012"), crs.get("Whites2012"), crs.get("Blacks2012")) != ("+5", "-25", "-18"):
        loi.append(f"Sidecar: Contrast/Whites/Blacks sau khi ghi = {crs.get('Contrast2012')}/"
                   f"{crs.get('Whites2012')}/{crs.get('Blacks2012')}")
    if crs.get("WhiteBalance") != "Custom":
        loi.append(f"Sidecar: WhiteBalance sau khi ghi = {crs.get('WhiteBalance')}")
    if atn.get("BaseTemperature") != "5250" or atn.get("BaseHighlights") != "16":
        loi.append(f"Sidecar: moc atn ghi theo As Shot chu khong theo nen "
                   f"(BaseTemperature {atn.get('BaseTemperature')}, BaseHighlights {atn.get('BaseHighlights')})")
    lai = copy.deepcopy(goc)
    for r, r0 in zip(lai, items_b):
        r["sidecar"] = r0["sidecar"]
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        at.plan(lai, cfg, thu_muc / "b")
    so_sanh(loi, "sidecar: chay lai sau khi ghi", kq["b"][1], {r["path"]: r for r in lai})
    return loi


if __name__ == "__main__":
    sys.exit(main())
