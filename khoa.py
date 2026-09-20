#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""khoa.py — Hạn dùng thử của AutoTone, và mã gia hạn.

    python khoa.py            # xem còn bao lâu
    python khoa.py --may       # in mã máy (đọc cho người cấp mã)

NÓI THẲNG VỀ SỨC MẠNH CỦA NÓ
    Đây là khoá MỀM. Nó chặn được: quên mất đã hết hạn, chỉnh đồng hồ máy lùi
    lại, chép thư mục sang máy khác, sửa file trạng thái bằng tay.
    Nó KHÔNG chặn được người biết đọc mã nguồn hoặc dịch ngược file .exe —
    khoá bí mật nằm ngay trong gói, nên ai lấy được nó thì tự sinh mã được, mà
    thật ra người đó cũng gỡ luôn được đoạn kiểm tra này.
    Muốn chặn thật thì phải kiểm qua máy chủ. Ở đây cố tình không làm vậy: máy
    của studio thường không có mạng ổn định khi đang chạy job, và một cái khoá
    chặn người dùng hợp lệ vì rớt mạng thì hại hơn là lợi.

BA CÁCH GIAN LẬN VÀ CÁCH CHẶN
    1. Vặn đồng hồ máy lùi lại  -> ghi lại MỐC THỜI GIAN LỚN NHẤT từng thấy;
       thấy đồng hồ lùi quá 5 phút so với mốc đó là khoá, kèm thông báo riêng.
    2. Sửa/xoá file trạng thái  -> file có chữ ký HMAC gắn với mã máy; sửa tay
       là chữ ký sai. Xoá đi thì mất luôn quyền gia hạn đã nhập.
    3. Chép sang máy khác dùng tiếp -> mã gia hạn gắn với MÃ MÁY, không dùng
       chéo máy được.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import platform
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Hạn dùng thử ────────────────────────────────────────────────────────────
#[[ 72 gio ke tu 01:00 ngay 04/09/2026, gio Viet Nam (UTC+7).
#
#   Ghi KEM MUI GIO chu khong phai gio tran. Gio tran thi may cai dat mui gio
#   khac se hieu ra mot moc khac — chenh nhau toi 14 tieng giua VN va Hawaii,
#   va do la mot cach gian lan khong can ky nang gi ca.
#
#   Moi so sanh ben duoi deu quy ve UTC.
#]]
HAN_ISO = "2026-09-07T01:00:00+07:00"
#[[ KHOA DANG TAT TREN MAY NAY.
#
#   False = bo han phan han dung thu va phan gia han: app khong bao gio khoa,
#   khong hien dem nguoc, khong hoi ma.
#
#   VI SAO TAT: day la may cua chinh nguoi lam ra tool. Han 72 gio la de dua
#   ban thu cho nguoi khac, khong phai de chan chinh minh — ngay 7/9 no het han
#   luc 01:00 va khoa luon may dang phat trien.
#
#   BAT LAI: doi dong nay thanh True.
#
#   AN TOAN KHI DONG GOI: dong_goi.py TU CHOI dong goi khi bien nay la False,
#   tru khi go them --khong-khoa. Nen tat o day khong the lo ra ban cai dat
#   cho nguoi khac ma khong ai biet. Bai kiem kiem_khoa.py van kiem day du co
#   che khoa (no tu bat lai trong tien trinh cua no), nen tat o day cung khong
#   lam mu bai kiem.
#]]
BAT_KHOA = True

TEN_UD = "AutoTone"
#[[ Khoa bi mat. Doi no thi MOI ma gia han da phat deu het hieu luc, va file
#   trang thai cu bi coi la sua tay — nen chi doi khi thuc su muon nhu vay.
#]]
BI_MAT = b"AutoTone-SAY-Media-2026-khoa-thu-nghiem-v1"

DUNG_SAI_DONG_HO = timedelta(minutes=5)     # cho phép lệch chừng này
NHOM = 4                                     # mã gia hạn: nhóm 4 ký tự
SO_NHOM = 5                                  # tổng 20 ký tự


# ── Mã máy ──────────────────────────────────────────────────────────────────
#[[ VI SAO KHONG DUNG THANG uuid.getnode().
#
#   Ban dau ham nay bam uuid.getnode() (dia chi MAC). Nhung getnode() KHONG bao
#   dam tra ve MAC: khi khong doc duoc card mang — may ao, container, may tat
#   Wi-Fi, may chi co adapter ao — Python BIA RA mot so ngau nhien MOI MOI LAN
#   CHAY. Do la hanh vi co tai lieu, khong phai loi.
#
#   Hau qua neu de nguyen: ma may doi sau moi lan mo app. Nguoi dung doc ma may
#   gui cho minh, minh cap ma gia han, ho nhap vao chay duoc — den lan mo app
#   TIEP THEO thi ma may da khac, chu ky file trang thai khong khop, app bao
#   "giay phep khong khop voi may nay" va khoa lai. Nguoi dung hop le bi chan,
#   con nguoi muon gian lan thi chang lien quan gi.
#
#   Bat duoc trong chinh container nay: ba lan chay lien tiep ra ba ma may khac
#   nhau. Bai kiem cu khong bat duoc vi no goi ma_may() HAI LAN TRONG MOT TIEN
#   TRINH, ma getnode() nho ket qua trong bien module — nen no luon "on dinh".
#   Bai kiem moi goi qua tien trinh con (xem kiem_khoa.py, phep 9).
#
#   Thu tu uu tien duoi day: cai nao that su gan voi may thi dung truoc.
#]]
def _may_theo_he() -> str | None:
    """Số định danh máy do hệ điều hành cấp. None nếu không đọc được."""
    try:
        if sys.platform.startswith("win"):
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"SOFTWARE\Microsoft\Cryptography", 0,
                                winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
                v = winreg.QueryValueEx(k, "MachineGuid")[0]
                return f"win:{v}" if v else None
        if sys.platform == "darwin":
            import subprocess
            r = subprocess.run(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                               capture_output=True, text=True, timeout=10)
            for d in r.stdout.splitlines():
                if "IOPlatformUUID" in d:
                    return "mac:" + d.split('"')[-2]
            return None
        for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            f = Path(p)
            if f.is_file():
                v = f.read_text(encoding="utf-8").strip()
                if v:
                    return f"nix:{v}"
    except Exception:                                        # noqa: BLE001
        return None
    return None


def _mac_that() -> str | None:
    """MAC thật, hoặc None nếu Python bịa ra số ngẫu nhiên.

    getnode() bật BIT MULTICAST (bit 40) ở số nó tự bịa — đó là cách phân biệt
    duy nhất, và là cách chính tài liệu Python chỉ ra.
    """
    try:
        n = uuid.getnode()
    except Exception:                                        # noqa: BLE001
        return None
    if not n or (n >> 40) & 1:
        return None
    return f"mac:{n}"


def _may_du_phong() -> str:
    """Chốt cuối: một số ngẫu nhiên sinh một lần rồi GIỮ LẠI trong thư mục dữ liệu.

    Yếu hơn hai cách trên — chép thư mục dữ liệu sang máy khác là mang theo cả
    mã máy. Nhưng thà vậy còn hơn để mã máy đổi mỗi lần mở app, vì cái đó chặn
    đúng người dùng hợp lệ. Chỉ chạm tới khi cả hai cách trên đều thất bại.
    """
    p = thu_muc_trang_thai() / "may.txt"
    try:
        if p.is_file():
            v = p.read_text(encoding="utf-8").strip()
            if v:
                return f"luu:{v}"
    except OSError:
        pass
    v = base64.b32encode(os.urandom(20)).decode("ascii").rstrip("=")
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(v, encoding="utf-8")
    except OSError:
        pass
    return f"luu:{v}"


def nguon_ma_may() -> str:
    """Chuỗi thô dùng để băm ra mã máy. Tách riêng để bài kiểm nhìn được nguồn."""
    return (_may_theo_he() or _mac_that() or _may_du_phong()) + "|" + platform.system()


def ma_may() -> str:
    """Mã nhận dạng máy, ổn định giữa các lần chạy, không chứa thông tin cá nhân.

    Băm nguồn định danh ở trên, nên chuỗi đọc cho người cấp mã không lộ số máy
    hay MAC thật.

    KHÔNG còn lấy tên máy (platform.node()) vào chuỗi băm: nó chỉ làm mã máy đổi
    thêm — đổi tên máy tính là mất giấy phép — mà không thêm được gì cho việc
    phân biệt máy, vì mã định danh hệ điều hành cấp đã đủ.
    """
    d = hashlib.sha256(nguon_ma_may().encode("utf-8")).digest()
    return base64.b32encode(d)[:12].decode("ascii")


# ── Chỗ lưu trạng thái ──────────────────────────────────────────────────────
def thu_muc_trang_thai() -> Path:
    """Cùng thư mục dữ liệu với phần còn lại của app — xem duong_dan.py.

    Trước đây file này tự tính lấy một chỗ riêng. Hai chỗ cùng quyết định "dữ
    liệu người dùng nằm đâu" thì sớm muộn cũng lệch nhau, và lúc lệch thì giấy
    phép nằm một nơi còn gu.json nằm nơi khác — chép thư mục dữ liệu sang máy
    mới là mất giấy phép mà không hiểu vì sao.
    """
    try:
        import duong_dan as dd
        return dd.goc_du_lieu()
    except Exception:                                        # noqa: BLE001
        if sys.platform.startswith("win"):
            goc = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        elif sys.platform == "darwin":
            goc = os.path.join(os.path.expanduser("~"), "Library",
                               "Application Support")
        else:
            goc = os.environ.get("XDG_STATE_HOME") or os.path.join(
                os.path.expanduser("~"), ".local", "state")
        return Path(goc) / TEN_UD


def _file() -> Path:
    return thu_muc_trang_thai() / "khoa.json"


def _ky(d: dict) -> str:
    """Chữ ký của phần dữ liệu, gắn với mã máy."""
    tho = json.dumps({k: v for k, v in d.items() if k != "ky"},
                     sort_keys=True, separators=(",", ":"))
    return hmac.new(BI_MAT, (tho + ma_may()).encode("utf-8"),
                    hashlib.sha256).hexdigest()[:32]


def doc_trang_thai() -> dict:
    p = _file()
    if not p.is_file():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(d, dict) or d.get("ky") != _ky(d):
        #[[ Chu ky sai = file bi sua tay HOAC bi chep tu may khac sang.
        #   Tra ve co rieng chu khong im lang bo qua: bo qua thi sua file la
        #   xoa sach lich su dong ho, tuc mo lai duong van dong ho.
        #]]
        return {"hong": True}
    return d


def ghi_trang_thai(**kw) -> dict:
    d = doc_trang_thai()
    if d.get("hong"):
        d = {}
    d.update(kw)
    d.pop("ky", None)
    d["ky"] = _ky(d)
    p = _file()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".part")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, p)
    except OSError:
        pass                      # không ghi được thì thôi, đừng làm sập app
    return d


# ── Mã gia hạn ──────────────────────────────────────────────────────────────
def _chuoi_ma(may: str, han_iso: str) -> str:
    tho = f"{may}|{han_iso}"
    h = hmac.new(BI_MAT, tho.encode("utf-8"), hashlib.sha256).digest()
    s = base64.b32encode(h).decode("ascii")
    #[[ Bo I, O, 0, 1 — bon ky tu de doc nham nhau khi doc qua dien thoai.
    #   Base32 chuan da khong co 0 va 1, con lai bo I va O.
    #]]
    s = s.replace("I", "8").replace("O", "9")
    return s[:NHOM * SO_NHOM]


def tao_ma(may: str, han_moi: datetime) -> str:
    """Sinh mã gia hạn. CHỈ dùng ở máy người cấp mã, không đưa vào gói cài."""
    iso = han_moi.astimezone(timezone.utc).isoformat()
    s = _chuoi_ma(may, iso)
    return "-".join(s[i:i + NHOM] for i in range(0, len(s), NHOM))


def _sach(ma: str) -> str:
    return "".join(c for c in (ma or "").upper() if c.isalnum())


def kiem_ma(ma: str, han_moi: datetime, may: str | None = None) -> bool:
    return hmac.compare_digest(_sach(ma),
                               _sach(_chuoi_ma(may or ma_may(),
                                               han_moi.astimezone(timezone.utc)
                                               .isoformat())))


def nhap_ma(ma: str, so_gio_thu: tuple = (24, 48, 72, 24 * 7, 24 * 30)) -> tuple:
    """Thử mã cho các mốc gia hạn thông dụng. -> (được không, hạn mới, lời nhắn).

    VÌ SAO PHẢI DÒ QUA MỘT DANH SÁCH
        Mã chỉ là chữ ký của (mã máy + hạn mới) — bản thân nó không mang hạn.
        Nên app phải đoán hạn rồi thử. Danh sách này phải KHỚP với script sinh
        mã; thêm mốc mới ở một bên mà quên bên kia thì mã hợp lệ vẫn bị từ chối.
    """
    if not _sach(ma):
        return False, None, "Chưa nhập mã."
    goc = _moc_han()
    for gio in so_gio_thu:
        moi = goc + timedelta(hours=gio)
        if kiem_ma(ma, moi):
            ghi_trang_thai(han_gia=moi.astimezone(timezone.utc).isoformat(),
                           ma_da_dung=_sach(ma))
            return True, moi, f"Đã gia hạn thêm {gio} giờ."
    return False, None, ("Mã không đúng cho máy này. Kiểm tra lại mã máy đã gửi "
                         "cho người cấp mã.")


# ── Kiểm hạn ────────────────────────────────────────────────────────────────
def _moc_han() -> datetime:
    return datetime.fromisoformat(HAN_ISO)


def han_hien_tai() -> datetime:
    """Hạn đang có hiệu lực: hạn gốc, hoặc hạn đã gia hạn nếu nó xa hơn."""
    han = _moc_han()
    d = doc_trang_thai()
    if not d.get("hong") and d.get("han_gia"):
        try:
            g = datetime.fromisoformat(d["han_gia"])
            if g > han:
                han = g
        except ValueError:
            pass
    return han


def kiem() -> dict:
    """Trạng thái khoá lúc này.

    -> {"chay_duoc": bool, "ly_do": str, "con_lai": timedelta|None,
        "han": datetime, "may": str}
    """
    bay_gio = datetime.now(timezone.utc)
    han = han_hien_tai()
    ra = {"chay_duoc": True, "ly_do": "", "con_lai": han - bay_gio,
          "han": han, "may": ma_may(), "tat": False}
    if not BAT_KHOA:
        #[[ con_lai = None chu khong de nguyen hieu so.
        #   Han goc da qua tu lau, nen de nguyen thi giao dien in ra "Ban dung
        #   thu · con da het han" mau cam — bao dung mot thu da tat. Tra ve
        #   None la cach noi "khong co han nao ca", va mo_ta_con_lai() dich
        #   None thanh "—".
        #]]
        ra.update(con_lai=None, tat=True,
                  ly_do="Khoá đang tắt trên máy này.")
        return ra

    d = doc_trang_thai()
    if d.get("hong"):
        ra.update(chay_duoc=False, con_lai=None,
                  ly_do="File giấy phép không khớp với máy này — có thể đã bị "
                        "sửa, hoặc thư mục được chép từ máy khác sang. "
                        "Xin mã gia hạn mới cho đúng máy này.")
        return ra

    #[[ CHONG VAN DONG HO LUI. Moc lon nhat tung thay duoc ghi lai moi lan chay.
    #]]
    try:
        cao = datetime.fromisoformat(d["moc_cao"]) if d.get("moc_cao") else None
    except ValueError:
        cao = None
    if cao and bay_gio < cao - DUNG_SAI_DONG_HO:
        ra.update(chay_duoc=False, con_lai=None,
                  ly_do=f"Đồng hồ máy đang chạy lùi so với lần dùng gần nhất "
                        f"({cao.astimezone().strftime('%d/%m %H:%M')}). "
                        f"Chỉnh lại đồng hồ cho đúng rồi mở lại.")
        return ra

    if cao is None or bay_gio > cao:
        ghi_trang_thai(moc_cao=bay_gio.isoformat(),
                       lan_dau=d.get("lan_dau") or bay_gio.isoformat())

    if bay_gio >= han:
        ra.update(chay_duoc=False, con_lai=timedelta(0),
                  ly_do=f"Hết hạn dùng thử lúc "
                        f"{han.astimezone().strftime('%H:%M %d/%m/%Y')}.")
    return ra


def mo_ta_con_lai(td) -> str:
    if td is None:
        return "—"
    g = int(td.total_seconds())
    if g <= 0:
        return "đã hết hạn"
    ngay, g = divmod(g, 86400)
    gio, g = divmod(g, 3600)
    phut = g // 60
    if ngay:
        return f"{ngay} ngày {gio} giờ"
    if gio:
        return f"{gio} giờ {phut} phút"
    return f"{phut} phút"


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Han dung thu AutoTone.")
    ap.add_argument("--may", action="store_true", help="Chi in ma may")
    a = ap.parse_args(argv)
    if a.may:
        print(ma_may())
        return 0
    k = kiem()
    print(f"  Mã máy   : {k['may']}")
    print(f"  Hạn dùng : {k['han'].astimezone():%H:%M %d/%m/%Y}")
    print(f"  Còn lại  : {mo_ta_con_lai(k['con_lai'])}")
    print(f"  Trạng thái: {'CHẠY ĐƯỢC' if k['chay_duoc'] else 'ĐÃ KHOÁ'}")
    if k["ly_do"]:
        print(f"  {k['ly_do']}")
    return 0 if k["chay_duoc"] else 1


if __name__ == "__main__":
    sys.exit(main())
