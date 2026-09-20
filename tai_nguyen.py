#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tai_nguyen.py — tai va nap cac goi tai nguyen nang tu GitHub Releases.

VI SAO CO FILE NAY
    Ban dong goi day du nang 2.79 GB nen tai ve rat lau, trong khi phan lon
    nguoi dung chi can khau CAN SANG — khau do chi can numpy + Pillow + OpenCV,
    do duoc 184 MB. Ba phan nang con lai (torch, mo hinh, mediapipe) tach ra
    tai sau, va chi tai cai nao that su dung toi.

    Do that ngay 20.09 tren goi 4.1 GB:
        torch (co CUDA)   2779 MB   chi retouch can
        mo hinh retouch    554 MB   chi retouch can
        mediapipe          154 MB   chi de do do mo mat (EAR)
        --------------------------------------------
        loi (can sang)     184 MB   AI CUNG CAN

DA CHUNG MINH DUOC GI TRUOC KHI VIET
    Rui ro lon nhat la torch co nap duoc tu mot thu muc NGOAI goi khong —
    neu PyInstaller nhung cung duong dan .dll thi ca huong nay sup. Thu that:
    chep torch ra thu muc rieng, XOA site-packages khoi sys.path, roi nap
    bang sys.path + os.add_dll_directory:

        OK torch 2.13.0+cu130 | CUDA True

    Chay duoc, CUDA van nhan. Nen huong nay kha thi.

BA NGUYEN TAC
    1. THIEU TAI NGUYEN KHONG BAO GIO LAM HONG KHAU CAN SANG.
       nap() tra ve False va di tiep; chi khau nao thuc su can moi bao loi.

    2. TAI DO DANG THI COI NHU CHUA CO.
       Tai vao file .part, kiem tra kich thuoc + SHA-256, dat xong moi doi
       ten. Dang tai ma mat dien thi lan sau thay .part va tai lai tu dau —
       khong bao gio co mot thu muc giai nen do dang.

    3. PHIEN BAN GAN VAO TEN THU MUC.
       torch-2.13.0-cu130/ chu khong phai torch/. Doi phien ban la thu muc
       khac han, nen khong bao gio co chuyen ban cu ban moi tron nhau.
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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

import duong_dan as dd

# Kho phat hanh. Doi o day khi doi repo — moi cho khac deu doc tu day.
KHO = "https://github.com/bunbuon/AutoToneandRetouch/releases/download"

UA = "AutoTone/1.0 (resource-fetch)"
CHUNK = 1 << 20          # 1 MB moi lan doc — du lon de nhanh, du nho de ve
                         # thanh tien do muot


@dataclass(frozen=True)
class Goi:
    """Mot goi tai nguyen tai roi."""

    ten: str                       # ten ngan, dung lam ten thu muc
    phien_ban: str                 # gan vao ten thu muc, xem nguyen tac 3
    file_zip: str                  # ten file tren Releases
    mb: int                        # kich thuoc de bao truoc cho nguoi dung
    sha256: str = ""               # de trong = bo qua kiem tra (chi luc phat trien)
    mo_ta: str = ""
    # Thu muc con phai co sau khi giai nen — de biet goi con nguyen hay khong.
    dau_hieu: tuple[str, ...] = field(default_factory=tuple)

    @property
    def thu_muc(self) -> str:
        return f"{self.ten}-{self.phien_ban}"

    @property
    def url(self) -> str:
        return f"{KHO}/{self.ten}-{self.phien_ban}/{self.file_zip}"


#[[ DANH SACH GOI.
#
#   `sha256` de trong cho toi khi tai len that — luc do dien vao. Xem
#   `bam_file()` o duoi de tinh.
#
#   `dau_hieu` la thu muc/file PHAI co sau khi giai nen. Dung de phat hien
#   goi giai nen do dang: co thu muc nhung thieu ruot thi coi nhu chua tai.
#]]
GOI = {
    #[[ CHI MOT BAN TORCH, LA BAN CUDA.
    #
    #   Truoc day co them ban CPU 114 MB va do nvidia-smi de chon. Bo di:
    #   ban CUDA chay duoc tren CA HAI loai may — khong co card thi torch tu
    #   lui ve CPU, retouch cham hon chu khong hong. Doi lay viec do, nguoi
    #   dung khong phai chon gi, va khong con canh do sai (may co card ma
    #   nvidia-smi khong nam trong PATH) roi tai ve ban chay cham vinh vien.
    #
    #   Gia: may khong card van tai 1447 MB thay vi 114 MB.
    #]]
    "torch": Goi(
        ten="torch", phien_ban="2.13.0-cu130", file_zip="torch-cu130.zip",
        mb=1819, mo_ta="Torch + CUDA — co card NVIDIA thi chay tren card",
        sha256="0409fd33256dba936a3d80440b8d48d6870849665850a09bb688afd925dca003",
        dau_hieu=("torch/lib", "torch/__init__.py"),
    ),
    "mo-hinh": Goi(
        ten="mo-hinh", phien_ban="1", file_zip="mo-hinh.zip",
        mb=487, mo_ta="Mo hinh retouch: vet, da, dodge/burn, liquify",
        sha256="7b25a702ac84d94edb683cad3a36978f6ca3b1d9cd9a42b479135eb1e9557484",
        dau_hieu=("mo_hinh/vet.pt",),
    ),
    "mediapipe": Goi(
        ten="mediapipe", phien_ban="0.10.14", file_zip="mediapipe.zip",
        mb=61, mo_ta="Do do mo mat (EAR) — chi dung khi loc anh nham mat",
        sha256="f3cbe7dca75e7a77f6dc1c54b1cc108d2c5aa01078fd2dcf2612545c184190e4",
        dau_hieu=("mediapipe/__init__.py",),
    ),
}

# Goi nao da them vao duong tim module trong phien nay.
_DA_NAP: set[str] = set()


# ---------------------------------------------------------------- duong dan

def goc() -> Path:
    """Thu muc chua moi goi tai nguyen. Ghi duoc, nam canh du lieu nguoi dung."""
    p = dd.goc_du_lieu() / "tai_nguyen"
    p.mkdir(parents=True, exist_ok=True)
    return p


def thu_muc_goi(g: Goi) -> Path:
    return goc() / g.thu_muc


def da_co(g: Goi) -> bool:
    """Goi da tai ve VA giai nen day du chua?

    Chi kiem tra thu muc ton tai la khong du: lan tai truoc co the dut giua
    chung, de lai mot thu muc co vai file. Nen phai soi `dau_hieu`.
    """
    d = thu_muc_goi(g)
    if not d.is_dir():
        return False
    return all((d / x).exists() for x in g.dau_hieu) if g.dau_hieu else True


# ---------------------------------------------------------------- tai ve

def bam_file(p: Path) -> str:
    """SHA-256 cua mot file. Dung de dien vao GOI luc phat hanh."""
    h = hashlib.sha256()
    with p.open("rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _tai_file(url: str, dich: Path,
              tien_do: Callable[[int, int], None] | None = None,
              dung: Callable[[], bool] | None = None) -> None:
    """Tai mot URL vao `dich`. Ghi ra .part roi moi doi ten — xem nguyen tac 2."""
    tam = dich.with_suffix(dich.suffix + ".part")
    tam.parent.mkdir(parents=True, exist_ok=True)
    if tam.exists():
        tam.unlink()

    #[[ Xoa .part PHAI nam ngoai khoi `with`.
    #
    #   Windows khong cho xoa file dang mo. Goi unlink() trong vong lap —
    #   luc file handle con song — nem PermissionError, va loi do de len
    #   InterruptedError nen ben goi thay mot loi hoan toan khac voi thu
    #   thuc su xay ra. Bat duoc khi viet bai kiem "dut giua chung".
    #]]
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
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
        tam.unlink(missing_ok=True)
        raise
    os.replace(tam, dich)


def tai(g: Goi, tien_do: Callable[[str, int, int], None] | None = None,
        dung: Callable[[], bool] | None = None) -> Path:
    """Tai va giai nen mot goi. Tra ve thu muc goi.

    `tien_do(pha, da, tong)`: pha la "tai" hoac "giai-nen".
    `dung()`: tra True de huy giua chung.
    """
    d = thu_muc_goi(g)
    if da_co(g):
        return d

    #[[ Xoa sach truoc khi tai lai.
    #
    #   Den day nghia la thu muc hoac chua co, hoac co ma THIEU RUOT (lan
    #   truoc dut giua chung). Truong hop thu hai ma giai nen de len thi
    #   file cu con lai lan voi file moi — dung kieu loi khong ai truy ra.
    #]]
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)

    zip_tam = goc() / f"_{g.ten}.zip"
    try:
        _tai_file(g.url, zip_tam,
                  (lambda a, b: tien_do("tai", a, b)) if tien_do else None,
                  dung)

        if g.sha256:
            thuc = bam_file(zip_tam)
            if thuc.lower() != g.sha256.lower():
                zip_tam.unlink(missing_ok=True)
                raise OSError(
                    f"file tai ve khong khop ma kiem tra.\n"
                    f"  mong doi: {g.sha256[:16]}...\n"
                    f"  nhan duoc: {thuc[:16]}...\n"
                    f"Thuong la mang chen giua (wifi cong cong, proxy). "
                    f"Thu lai bang mang khac.")

        #[[ Giai nen ra thu muc TAM roi moi doi ten.
        #
        #   Giai thang vao dich thi mat dien giua chung se de lai thu muc
        #   nua voi — ma `da_co()` co the van cho la du neu dau hieu tinh co
        #   da nam trong phan da giai.
        #]]
        tam_gn = Path(tempfile.mkdtemp(prefix=f"{g.ten}_", dir=str(goc())))
        try:
            with zipfile.ZipFile(zip_tam) as z:
                ds = z.infolist()
                for i, it in enumerate(ds, 1):
                    if dung is not None and dung():
                        raise InterruptedError("nguoi dung dung tai")
                    z.extract(it, tam_gn)
                    if tien_do is not None:
                        tien_do("giai-nen", i, len(ds))
            os.replace(tam_gn, d)
        except BaseException:
            shutil.rmtree(tam_gn, ignore_errors=True)
            raise
    finally:
        zip_tam.unlink(missing_ok=True)

    if not da_co(g):
        raise OSError(f"goi {g.ten} giai nen xong nhung thieu: "
                      f"{[x for x in g.dau_hieu if not (d / x).exists()]}")
    return d


# ---------------------------------------------------------------- nap

def nap(ten: str) -> bool:
    """Them mot goi da tai vao duong tim module. Tra ve co nap duoc khong.

    KHONG tai ve — chi nap cai da co. Ben goi tu quyet dinh co tai hay khong,
    vi tai la viec mat nhieu phut va phai hoi nguoi dung truoc.
    """
    if ten in _DA_NAP:
        return True
    g = GOI.get(ten)
    if g is None or not da_co(g):
        return False

    d = str(thu_muc_goi(g))
    if d not in sys.path:
        sys.path.insert(0, d)

    #[[ .dll cua torch nam trong torch/lib va KHONG tu tim thay.
    #
    #   Tu Python 3.8, Windows khong con doc PATH de tim .dll cua module mo
    #   rong. Thieu dong nay thi `import torch` bao "DLL load failed" —
    #   thong bao khong he nhac gi toi duong dan.
    #]]
    if hasattr(os, "add_dll_directory"):
        for con in ("torch/lib", "lib"):
            p = Path(d) / con
            if p.is_dir():
                try:
                    os.add_dll_directory(str(p))
                except OSError:
                    pass

    _DA_NAP.add(ten)
    return True


def nap_het(tens: Iterable[str]) -> list[str]:
    """Nap nhieu goi. Tra ve danh sach goi KHONG nap duoc."""
    return [t for t in tens if not nap(t)]


def can_cho_retouch() -> list[str]:
    """Cac goi retouch bat buoc phai co.

    Khong do may nua — xem ghi chu o GOI["torch"]. Mot ban torch duy nhat,
    chay duoc ca tren may co card lan khong.
    """
    return ["torch", "mo-hinh"]


# ---------------------------------------------------------------- bao cao

def tinh_trang() -> list[dict]:
    """Bang trang thai moi goi — giao dien doc de ve."""
    ra = []
    for ten, g in GOI.items():
        d = thu_muc_goi(g)
        ra.append({
            "ten": ten,
            "mo_ta": g.mo_ta,
            "mb": g.mb,
            "phien_ban": g.phien_ban,
            "da_co": da_co(g),
            "duong_dan": str(d) if d.exists() else "",
        })
    return ra


def don_ban_cu() -> int:
    """Xoa thu muc cua cac PHIEN BAN CU, giu ban dang dung. Tra ve so thu muc xoa.

    Doi phien ban goi thi thu muc cu thanh rac — moi ban torch chiem vai GB
    nen phai don, nhung chi don khi ban moi DA TAI XONG.
    """
    dang_dung = {g.thu_muc for g in GOI.values()}
    ten_goi = {g.ten for g in GOI.values()}
    n = 0
    for p in goc().iterdir():
        if not p.is_dir() or p.name in dang_dung:
            continue
        # Chi dung toi thu muc dung quy uoc <ten>-<phien ban> cua chinh minh
        if p.name.rsplit("-", 1)[0] in ten_goi or p.name.split("-")[0] in ten_goi:
            shutil.rmtree(p, ignore_errors=True)
            n += 1
    return n


def dung_luong_da_tai() -> float:
    """Tong MB tai nguyen dang chiem tren dia."""
    t = 0
    for p in goc().rglob("*"):
        if p.is_file():
            t += p.stat().st_size
    return t / 1048576
