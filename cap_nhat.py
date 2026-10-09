#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cap_nhat.py — cap nhat CODE va MODEL cua app ma khong phai cai lai.

VI SAO CO FILE NAY
    Goi PyInstaller (Python runtime + torch + model ~2 GB) la phan NANG va it
    doi. Code app (.pyd loi + .py plumbing) va model retouch moi la phan hay
    doi. Cai lai ca goi moi lan sua mot dong logic la qua ton — nhat la torch
    1.8 GB. Nen tach ra: update chi tai CODE MOI (vai MB) ve thu muc ghi duoc
    cua nguoi dung, va app NAP CODE DO TRUOC code trong goi.

    Giong het tai_nguyen.py lo torch/model nang, file nay lo code + model nhe.
    Ba nguyen tac ben do giu nguyen o day:

    1. THIEU / HONG CAP NHAT KHONG BAO GIO LAM HONG APP.
       Khong co mang, URL chet, file hong SHA -> bo qua, chay ban dang co.
       kich_hoat() boc try/except rong: mot ban cap nhat loi KHONG duoc phep
       chan app mo len.

    2. TAI DO DANG THI COI NHU CHUA CO.
       Tai ra .part, kiem kich thuoc + SHA-256, giai nen ra thu muc TAM, xong
       xuoi moi doi ten. Mat dien giua chung thi lan sau tai lai tu dau, khong
       bao gio co mot thu muc code nua voi ma app lai di nap.

    3. PHIEN BAN GAN VAO TEN THU MUC.
       cap_nhat/2026.10.10/ chu khong phai cap_nhat/moi/. Ban moi la thu muc
       khac han; ban cu giu lai mot doi de con lui ve duoc neu ban moi loi.

VI TRI TRONG GOI (da kiem CHUNG tren chinh AutoTone.exe)
    Module app trong goi nam trong PYZ dang .pyc (loi da ma hoa thi la .pyd/.so
    ship rieng). PyInstaller >= 6.10 cai importer cua no la PATH-ENTRY-FINDER
    chay BEN TRONG PathFinder, KHONG con "nuot" sys.path nhu ban cu. Nen khi
    kich_hoat() chen thu muc cap_nhat len DAU sys.path, PathFinder hoi thu muc
    do (FileFinder) TRUOC sys._MEIPASS (PyiFrozenFinder) -> module o do thang.
    Ban update co the:
      - chi .py  : sua nhanh plumbing, khong can trinh bien dich C, chay moi he
      - .pyd/.so : giu kin loi, nhung .pyd/.so phai dung DUNG phien ban Python +
                   HE DIEU HANH cua goi (vi the latest.json tach theo nen tang).
    QUAN TRONG: build PHAI dung PyInstaller >= 6.10 (dong_goi.py co chot kiem).
    Voi < 6.10 importer la meta-path finder -> sys.path bi bo qua -> OTA hong.
    Model retouch: xem ap_model() va ghi chu o do.

NOI CHUYEN VOI tai_nguyen.py — KHAC VIEC, DUNG LAN
    tai_nguyen.py: torch / mediapipe / goi "mo-hinh" GOC (vai tram MB), tai
    LAN DAU dung toi. cap_nhat.py: ban VA (code + model da sua) CHONG len tren.
    Hai he doc lap, khong goi nhau.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

import duong_dan as dd

#[[ PHIEN BAN APP. Dinh theo NGAY phat hanh (YYYY.MM.DD) cho de so > <, va de
#   nhin biet ngay ban nao cu. Doi o day MOI khi phat hanh ban moi — va dat
#   dung so nay vao `moi` trong latest.json tren Releases. ]]
#[[ 9/10: PHAI khop --ban cua dong_installer o moi lan build (tu v56). Truoc do
#   dung o 2026.10.04 suot cac ban 2026.10.09.x: app "Gioi thieu" hien ban cu, va
#   mot ban OTA 2026.10.05 se bi coi la MOI hon ban cai 2026.10.09. ]]
PHIEN_BAN_APP = "2026.10.10.1"

#[[ Kho phat hanh — DUNG kho voi tai_nguyen.KHO. Doi o day khi doi repo. ]]
KHO = "https://github.com/bunbuon/AutoToneandRetouch/releases/download"

#[[ Tag CO DINH chua ban cap nhat moi nhat. Moi lan phat hanh thi up de len
#   tag nay (xoa asset cu, up asset moi) — URL khong doi nen app luon biet cho
#   hoi. `latest.json` nho vai tram byte; chi tai no khi kiem, chua tai code. ]]
TAG_MOI = "app-latest"
TEN_META = "latest.json"

UA = "AutoTone/1.0 (app-update)"
CHUNK = 1 << 20
CHO_META = 8          # giay — het thi coi nhu khong co mang, KHONG phai loi
CHO_TAI = 60


def nen_may() -> str:
    """Khoa nen tang cua may dang chay: 'win' | 'mac-arm64' | 'mac-x86_64' | 'linux'.

    VI SAO CAN: ban cap nhat MA HOA chua .pyd (Windows) hoac .so (Mac), va .so
    con khac nhau giua Apple Silicon (arm64) va Intel (x86_64). Ban .py thuan
    thi chay dau cung — luc do latest.json khong can tach nen, dung truong goc.
    Khoa nay de app lay dung file cho may minh tu khoi `nen` trong latest.json."""
    import platform
    if sys.platform.startswith("win"):
        return "win"
    if sys.platform == "darwin":
        may = platform.machine().lower()
        return "mac-arm64" if may in ("arm64", "aarch64") else "mac-x86_64"
    return "linux"


# ---------------------------------------------------------------- duong dan

def goc() -> Path:
    """Thu muc chua moi ban cap nhat. Ghi duoc, canh du lieu nguoi dung."""
    p = dd.goc_du_lieu() / "cap_nhat"
    p.mkdir(parents=True, exist_ok=True)
    return p


def thu_muc_ban(ver: str) -> Path:
    return goc() / ver


def _hop_le(ver: str) -> bool:
    """Ten phien ban co an toan de lam ten thu muc khong?

    Chi cho so, dau cham, gach ngang. Chan '..', dau gach cheo, ky tu la —
    JSON tren Releases la du lieu NGOAI, khong duoc bien thanh duong dan tuy y.
    """
    return bool(ver) and all(c.isdigit() or c in ".-" for c in ver) \
        and ".." not in ver and len(ver) <= 32


# ---------------------------------------------------------------- so sanh ver

def _bo(ver: str) -> tuple:
    """Tach '2026.10.4' -> (2026, 10, 4) de so sanh dung kieu so, khong phai
    chuoi ('2026.9' > '2026.10' neu so chuoi — sai)."""
    ra = []
    for phan in str(ver).replace("-", ".").split("."):
        ra.append(int(phan) if phan.isdigit() else 0)
    return tuple(ra)


def moi_hon(a: str, b: str) -> bool:
    """a moi hon b?"""
    return _bo(a) > _bo(b)


# ---------------------------------------------------------------- kiem bang

def bam_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def kiem_tra():
    """Hoi Releases xem co ban moi hon dang chay khong.

    Tra ve dict {ver, file_zip, sha256, mb, ghi_chu, url} neu CO ban moi hop le
    va moi hon PHIEN_BAN_APP; None neu khong co / khong hop le / khong co mang.

    KHONG tai gi — chi lay file meta nho. Ben goi quyet dinh co tai khong.
    Khong bao gio nem loi: khong mang thi tra None.
    """
    url = f"{KHO}/{TAG_MOI}/{TEN_META}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=CHO_META) as r:
            raw = r.read(1 << 16)          # meta nho; chan file khong lo
        meta = json.loads(raw.decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return None

    ver = str(meta.get("moi", "")).strip()
    if not _hop_le(ver) or not moi_hon(ver, PHIEN_BAN_APP):
        return None

    #[[ CHON KHOI THEO NEN TANG.
    #
    #   latest.json co the:
    #     - don gian: {moi, file_zip, sha256, mb, ghi_chu}  -> dung cho ban .py
    #       thuan (chay dau cung). Dung thang cac truong goc.
    #     - tach nen:  {moi, ghi_chu, nen: {win:{file_zip,sha256,mb},
    #                   mac-arm64:{...}, ...}} -> ban MA HOA .pyd/.so. Lay khoi
    #       dung may minh. Khong co khoi cho may nay -> coi nhu chua co ban
    #       (tra None), KHONG tai nham .so cua he khac ve.
    #]]
    nen = meta.get("nen")
    if isinstance(nen, dict):
        khoi = nen.get(nen_may())
        if not isinstance(khoi, dict):
            return None                     # chua co ban cho nen tang nay
        file_zip = str(khoi.get("file_zip", f"app-{ver}-{nen_may()}.zip"))
        sha = str(khoi.get("sha256", ""))
        mb = int(khoi.get("mb", 0) or 0)
    else:
        file_zip = str(meta.get("file_zip", f"app-{ver}.zip"))
        sha = str(meta.get("sha256", ""))
        mb = int(meta.get("mb", 0) or 0)

    #[[ Chan ten file la: chi cho ten tep tran, khong thu muc. Meta la du lieu
    #   ngoai — khong duoc dieu khien duong tai. ]]
    if "/" in file_zip or "\\" in file_zip or ".." in file_zip:
        return None
    return {
        "ver": ver,
        "file_zip": file_zip,
        "sha256": sha,
        "mb": mb,
        "ghi_chu": str(meta.get("ghi_chu", "")),
        "url": f"{KHO}/{TAG_MOI}/{file_zip}",
    }


def da_co(ver: str) -> bool:
    """Ban `ver` da tai ve VA giai nen (co dau hieu) chua?"""
    d = thu_muc_ban(ver)
    return d.is_dir() and (d / ".xong").is_file()


# ---------------------------------------------------------------- tai ve

def _tai_file(url: str, dich: Path,
              tien_do: Callable[[int, int], None] | None = None,
              dung: Callable[[], bool] | None = None) -> None:
    """Tai URL ra .part roi doi ten — xem nguyen tac 2."""
    tam = dich.with_suffix(dich.suffix + ".part")
    tam.parent.mkdir(parents=True, exist_ok=True)
    if tam.exists():
        tam.unlink()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=CHO_TAI) as r:
            tong = int(r.headers.get("Content-Length") or 0)
            da = 0
            with tam.open("wb") as f:
                while True:
                    if dung is not None and dung():
                        raise InterruptedError("nguoi dung dung tai")
                    b = r.read(CHUNK)
                    if not b:
                        break
                    f.write(b)
                    da += len(b)
                    if tien_do is not None:
                        tien_do(da, tong)
        if tong and tam.stat().st_size != tong:
            raise OSError(f"tai thieu: {tam.stat().st_size}/{tong} byte")
    except BaseException:
        #[[ Xoa .part NGOAI `with` — Windows khong cho xoa file dang mo (xem
        #   cung cho trong tai_nguyen._tai_file). ]]
        tam.unlink(missing_ok=True)
        raise
    os.replace(tam, dich)


def tai(ban: dict, tien_do: Callable[[str, int, int], None] | None = None,
        dung: Callable[[], bool] | None = None) -> Path:
    """Tai va giai nen mot ban cap nhat (dict tu kiem_tra()). -> thu muc ban.

    `tien_do(pha, da, tong)`: pha la "tai" | "giai-nen".
    `dung()`: True de huy giua chung.
    """
    ver = ban["ver"]
    if not _hop_le(ver):
        raise ValueError(f"phien ban khong hop le: {ver!r}")
    d = thu_muc_ban(ver)
    if da_co(ver):
        return d

    #[[ Xoa sach truoc khi tai lai: den day nghia la chua co hoac co ma dang
    #   do (thieu .xong). Giai nen de len ban do thi file cu lan file moi. ]]
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)

    zip_tam = goc() / f"_{ver}.zip"
    try:
        _tai_file(ban["url"], zip_tam,
                  (lambda a, b: tien_do("tai", a, b)) if tien_do else None,
                  dung)

        if ban.get("sha256"):
            thuc = bam_file(zip_tam)
            if thuc.lower() != ban["sha256"].lower():
                zip_tam.unlink(missing_ok=True)
                raise OSError(
                    "ban cap nhat tai ve khong khop ma kiem tra.\n"
                    f"  mong doi: {ban['sha256'][:16]}...\n"
                    f"  nhan duoc: {thuc[:16]}...\n"
                    "Thuong la mang chen giua. Thu lai bang mang khac.")

        tam_gn = Path(tempfile.mkdtemp(prefix=f"{ver}_", dir=str(goc())))
        try:
            with zipfile.ZipFile(zip_tam) as z:
                #[[ Chan Zip Slip: khong cho entry thoat ra ngoai thu muc dich.
                #   zip la file tai tu mang — khong duoc ghi ra cho tuy y. ]]
                for it in z.infolist():
                    muc = tam_gn / it.filename
                    if not str(muc.resolve()).startswith(str(tam_gn.resolve())):
                        raise OSError(f"zip chua duong dan la: {it.filename!r}")
                ds = z.infolist()
                for i, it in enumerate(ds, 1):
                    if dung is not None and dung():
                        raise InterruptedError("nguoi dung dung tai")
                    z.extract(it, tam_gn)
                    if tien_do is not None:
                        tien_do("giai-nen", i, len(ds))
            (tam_gn / ".xong").write_text(ver, encoding="utf-8")
            os.replace(tam_gn, d)
        except BaseException:
            shutil.rmtree(tam_gn, ignore_errors=True)
            raise
    finally:
        zip_tam.unlink(missing_ok=True)

    if not da_co(ver):
        raise OSError(f"ban {ver} giai nen xong nhung thieu dau hieu .xong")
    return d


# ---------------------------------------------------------------- kich hoat

def _ban_moi_nhat_da_co() -> str | None:
    """Phien ban MOI NHAT da tai ve day du (co .xong) va moi hon ban trong goi.

    Chi tra ve ban THUC SU moi hon PHIEN_BAN_APP: neu goi da duoc build moi hon
    moi ban tung tai (vd cai de len), thi KHONG nap ban cu nua."""
    tot = None
    if not goc().exists():
        return None
    for p in goc().iterdir():
        if not p.is_dir() or not (p / ".xong").is_file():
            continue
        ver = p.name
        if not _hop_le(ver) or not moi_hon(ver, PHIEN_BAN_APP):
            continue
        if tot is None or moi_hon(ver, tot):
            tot = ver
    return tot


def ap_model(d: Path) -> None:
    """Neu ban cap nhat co thu muc mo_hinh/ thi bao retouch dung mo hinh do.

    CACH NOI (da kiem: saytool KHONG doc bien mo hinh rieng — no nap theo duong
    TUONG DOI `mo_hinh/vet.pt` so voi CWD cua tien trinh con). Nen o day KHONG
    dat bien cho saytool, ma dat AUTOTONE_MO_HINH_VA = thu muc mo_hinh/ cua ban
    va, cho RETOUCH.PY doc. retouch.cwd_retouch() thay co bien nay thi dung mot
    thu muc LOP PHU (mo hinh goi + mo hinh va, va de len) lam CWD khi chay
    saytool -> saytool nap trung mo hinh moi ma khong phai sua mot dong saytool.

    Khong co mo_hinh/ trong ban va -> khong dat gi -> retouch chay voi mo hinh
    goi nhu cu."""
    mh = d / "mo_hinh"
    if mh.is_dir() and any(mh.iterdir()):
        os.environ["AUTOTONE_MO_HINH_VA"] = str(mh)


def kich_hoat() -> str | None:
    """Chen ban cap nhat moi nhat (neu co) len DAU sys.path. -> ver da ap, hoac None.

    GOI O DONG DAU KHOI DONG, truoc moi `import` module app (truoc ca
    `import tai_nguyen`). Khong bao gio nem loi: ban cap nhat hong KHONG duoc
    chan app mo len — bat het va chay ban trong goi.

    VI SAO CHEN LEN DAU sys.path (da kiem CHUNG tren chinh AutoTone.exe):
        PyInstaller >= 6.10 cai importer cua no la PATH-ENTRY-FINDER chay BEN
        TRONG PathFinder (khong con la meta-path finder "nuot" sys.path nhu ban
        cu). Nen thu muc nao dung TRUOC trong sys.path thi thang: thu muc cap
        nhat (FileFinder) dung truoc sys._MEIPASS (PyiFrozenFinder) -> module
        trong do (ca .py lan .pyd) de len ban trong PYZ. Loi app trong goi la
        .pyc trong PYZ (KHONG phai .pyd) — nhung quy luat van la THU TU sys.path,
        khong phai "la .pyd". Build PHAI dung PyInstaller >= 6.10 cho dung nay.

    CAM BAY sys.modules (lop phong ve o duoi): thu thuat sys.path chi an LUC
        import DAU TIEN. Neu mot module app nao do lo bi import TRUOC khi chen
        (vd goi kich_hoat muon), no da nam trong sys.modules va `import` sau tra
        ve ban CU da cache — sys.path khong duoc hoi lai. Nen o day, sau khi chen
        duong, ta XOA khoi sys.modules nhung module app ma ban cap nhat co mang
        (chi nhung ten do — KHONG dung toi stdlib/thu vien dang chay), roi
        invalidate_caches() de lan import ke tiep hoi lai PathFinder.
    """
    try:
        ver = _ban_moi_nhat_da_co()
        if not ver:
            return None
        d = thu_muc_ban(ver)
        ds = str(d)
        #[[ Bo di neu da co o giua chung roi chen len dau, de chac chan no
        #   dung TRUOC thu muc goi (sys._MEIPASS). ]]
        while ds in sys.path:
            sys.path.remove(ds)
        sys.path.insert(0, ds)

        #[[ LOP PHONG VE sys.modules — xem docstring. Chi dong vao nhung module
        #   ma ban cap nhat THUC SU mang (ten tep .py / .pyd trong thu muc va,
        #   bo duoi va ABI tag). Dong `cap_nhat` thi khong tu xoa chinh minh. ]]
        import importlib
        ten_va = set()
        for p in d.iterdir():
            if p.suffix == ".py":
                ten_va.add(p.stem)
            elif p.suffix in (".pyd", ".so"):
                ten_va.add(p.name.split(".")[0])   # bo .cp312-... .pyd
        ten_va.discard("cap_nhat")
        ten_va.discard("chay")
        for ten in ten_va:
            sys.modules.pop(ten, None)
        importlib.invalidate_caches()

        ap_model(d)
        return ver
    except Exception:                                    # noqa: BLE001
        return None


def phien_ban_dang_chay() -> str:
    """Phien ban THUC SU dang chay: ban cap nhat da kich_hoat, hoac ban goi.

    Doc tu file .xong cua ban moi nhat da ap. Dung de hien trong 'Gioi thieu'
    va de so khi kiem — chu khong lay cung PHIEN_BAN_APP (hang so trong goi)."""
    ver = _ban_moi_nhat_da_co()
    return ver or PHIEN_BAN_APP


# ---------------------------------------------------------------- don dep

def don_ban_cu(giu: int = 1) -> int:
    """Xoa cac ban cap nhat cu, giu `giu` ban moi nhat. -> so thu muc xoa.

    Moi ban code vai MB nen khong gap nhu torch, nhung van don de khoi phinh.
    Chi don ban CU HON ban dang ap — khong bao gio xoa ban dang nap."""
    if not goc().exists():
        return 0
    cac = []
    for p in goc().iterdir():
        if p.is_dir() and _hop_le(p.name) and (p / ".xong").is_file():
            cac.append(p.name)
    cac.sort(key=_bo, reverse=True)      # moi nhat truoc
    dang_ap = _ban_moi_nhat_da_co()
    n = 0
    for ver in cac[giu:]:
        if ver == dang_ap:
            continue
        shutil.rmtree(thu_muc_ban(ver), ignore_errors=True)
        n += 1
    #[[ Don ca .zip/.part roi rot neu co. ]]
    for p in goc().glob("_*.zip*"):
        try:
            p.unlink()
            n += 0
        except OSError:
            pass
    return n


# ---------------------------------------------------------------- bao cao

def tinh_trang() -> dict:
    """Cho giao dien ve: dang chay ban nao, co ban nao tai san chua."""
    return {
        "phien_ban_goi": PHIEN_BAN_APP,
        "dang_chay": phien_ban_dang_chay(),
        "da_tai": sorted(
            (p.name for p in goc().iterdir()
             if p.is_dir() and (p / ".xong").is_file()),
            key=_bo, reverse=True) if goc().exists() else [],
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Kiem/quan ly cap nhat AutoTone.")
    ap.add_argument("--kiem", action="store_true", help="Hoi Releases co ban moi khong")
    ap.add_argument("--trang-thai", action="store_true", dest="trang_thai")
    ap.add_argument("--don", action="store_true", help="Xoa ban cu, giu ban moi nhat")
    a = ap.parse_args()
    if a.kiem:
        b = kiem_tra()
        print("Co ban moi:", b) if b else print(f"Dang la ban moi nhat ({PHIEN_BAN_APP}).")
    if a.trang_thai:
        print(json.dumps(tinh_trang(), ensure_ascii=False, indent=2))
    if a.don:
        print(f"Da xoa {don_ban_cu()} thu muc ban cu.")
    if not (a.kiem or a.trang_thai or a.don):
        print(f"Phien ban: {PHIEN_BAN_APP}")
        print(mo_ta := tinh_trang())
