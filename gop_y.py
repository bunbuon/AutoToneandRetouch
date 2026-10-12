# -*- coding: utf-8 -*-
"""gop_y.py — Góp dữ liệu buổi đã sửa tay về máy nhận của SAY Media (12/10/2026).

VÌ SAO
    User 12/10: "đẩy ứng dụng ra cho mọi người test để có nhiều dữ liệu hơn để train cho
    nhiều thiết bị, tình huống … sau mỗi bộ ảnh họ tự sửa tay thì lưu lại thông tin và gửi
    về". Chốt: thu CẢ ảnh nhỏ lẫn số đo · máy chủ tại nhà (đường hầm Cloudflare) · LUÔN GỬI.
    Báo cho người dùng MỘT lần (minh bạch), tắt được ở ⋯ › Góp dữ liệu.

GÓI MỘT BUỔI (zip, định dạng y như Claude outputs/do/<buổi>/ — cổng kiem_2ban_quay đọc thẳng)
    meta.json                  phiên bản app / engine, CẤU HÌNH lúc đẩy (trần EV, loại buổi…),
                               thiết bị, thân máy, số ảnh sửa / duyệt, người gửi (mã băm)
    do_<buổi>.json.gz          số đo từng ảnh (analyze) — chạy lại plan() bằng code mới được
    apply_*.done               thông số TOOL đã đẩy sang Lightroom
    _autotone_da_sua_*.tsv     bản chụp catalog lúc đóng gói = thông số NGƯỜI DÙNG chốt
    _autotone_baseline.tsv     preset gốc trước khi tool chạm
    anh_nho/<tên>.jpg          preview 384 px, KHÔNG EXIF / GPS
    toc_do.csv                 thời gian retouch từng khâu trên máy này (nếu có)
    Đường dẫn thư mục ảnh thay bằng X:\\<mã buổi> (tên file giữ để khớp các phần).

KHI NÀO
    Lúc bấm "3 · Xuất" (người dùng đã sửa xong) và ⋯ › Gửi góp ý buổi này. Chỉ gửi khi có
    >= SUA_TOI_THIEU ảnh bị sửa tay so với lần tool đẩy — không sửa thì không có gì để học.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import math
import os
import platform
import shutil
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

import duong_dan as dd

PHIEN_DINH_DANG = 1
#  Đường hầm Cloudflare autotone-gopy -> máy nhận tại nhà cổng 8100 (may_nhan/tao_duong_ham_gop_y.bat).
#  MỘT cấp dưới saymedia.com.vn: chứng chỉ miễn phí không phủ gopy.ai.saymedia.com.vn (hai cấp).
#  Máy nhận tắt -> gói nằm hàng đợi, 15 phút thử lại.
DIA_CHI_MAC_DINH = "https://gopy-ai.saymedia.com.vn"
#  Khoá chung app <-> máy nhận (may_nhan/may_nhan_gop_y.json). Chỉ cho GHI một gói, không đọc được gì.
BI_MAT = "jA4PRIql5Wzx9IgAtAQcawqSKjfXBG3C"
SUA_TOI_THIEU = 3
CANH_ANH_NHO = 384
GOI_TOI_DA = 95_000_000      # byte — Cloudflare miễn phí chặn yêu cầu > 100 MB (xem _dong_goi)
CHAT_LUONG_ANH_NHO = 72
CHO_CHUP_GIAY = 600          # chờ plugin Lightroom chụp catalog
NHIP_GUI_GIAY = 15 * 60      # thử gửi lại hàng đợi mỗi chừng này
GIU_DA_GUI = 200             # số biên nhận đã gửi giữ lại

SAI_SUA = {"Exposure2012": 0.005, "Temperature": 1.0, "Tint": 1.0, "Highlights2012": 1.0}

_KHOA_DONG_GOI = threading.Lock()


def thu() -> Path:
    return dd.goc_du_lieu() / "gop_y"


def _cau_hinh_file() -> Path:
    return thu() / "gop_y.json"


def doc_cau_hinh() -> dict:
    try:
        d = json.loads(_cau_hinh_file().read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def ghi_cau_hinh(d: dict) -> None:
    cu = doc_cau_hinh()
    cu.update(d)
    _cau_hinh_file().parent.mkdir(parents=True, exist_ok=True)
    dd.ghi_ben(_cau_hinh_file(), json.dumps(cu, ensure_ascii=False, indent=2))


def bat() -> bool:
    """LUÔN GỬI (user 12/10) — trừ khi người dùng tự tắt ở ⋯ › Góp dữ liệu."""
    return bool(doc_cau_hinh().get("bat", True))


def dia_chi() -> str:
    return (os.environ.get("AUTOTONE_GOP_Y_URL") or doc_cau_hinh().get("url")
            or DIA_CHI_MAC_DINH).strip().rstrip("/")


def ly_do_tat() -> str:
    """"" = được tự chạy (báo một lần, đóng gói khi Xuất, gửi nền); khác "" = vì sao không.

    Bài kiểm giao diện / tự kiểm gói chạy với thư mục dữ liệu TẠM: hộp thoại báo lần đầu
    là cửa sổ chặn -> treo bài kiểm, và không được gửi gói giả về máy nhận thật.
    Cùng lý lẽ với duong_dan.ly_do_khong_cai_modules (trừ "chạy từ mã nguồn": máy chủ
    chạy mã nguồn vẫn góp được)."""
    if os.environ.get("AUTOTONE_GOP_Y") == "0":
        return "tắt bằng AUTOTONE_GOP_Y=0"
    if os.environ.get("AUTOTONE_TU_KIEM") or "--tu-kiem" in sys.argv[1:]:
        return "đang tự kiểm"
    try:
        import multiprocessing as _mp
        if _mp.current_process().name != "MainProcess":
            return "tiến trình con"
    except Exception:                                        # noqa: BLE001
        pass
    try:
        tam = os.path.normcase(os.path.abspath(tempfile.gettempdir()))
        du = os.path.normcase(os.path.abspath(str(thu())))
        if du.startswith(tam + os.sep):
            return "thư mục dữ liệu là thư mục tạm"
    except Exception:                                        # noqa: BLE001
        pass
    return ""


def _bam(s: str, n: int = 12) -> str:
    return hashlib.sha256(s.encode("utf-8", "surrogatepass")).hexdigest()[:n]


def ma_nguoi() -> str:
    """Mã người gửi: băm key bản quyền (hoặc mã máy). Không tên, không email."""
    try:
        import khoa
        d = khoa.doc_trang_thai()
        k = str(d.get("bq_key") or "")
        if k:
            return _bam("key:" + k)
        return _bam("may:" + khoa.ma_may())
    except Exception:                                        # noqa: BLE001
        return _bam("node:" + platform.node())


def ma_buoi(thu_muc) -> str:
    return _bam("buoi:" + os.path.normcase(os.path.normpath(str(thu_muc))), 10)


def _json(o):
    if hasattr(o, "tolist"):
        return o.tolist()
    if isinstance(o, datetime):
        return o.isoformat()
    if isinstance(o, Path):
        return str(o)
    if isinstance(o, (set, tuple)):
        return list(o)
    return str(o)


# ---------------------------------------------------------------- cấu hình mỗi lần đẩy
def ghi_lan_day(thu_muc, cfg: dict, items: list, job=None) -> Path | None:
    """Lưu CẤU HÌNH lúc đẩy sang Lightroom (trần EV, loại buổi, ánh sáng…).

    #[[ 11/10 phải DÒ NGƯỢC cấu hình (trần EV 3) mới tái hiện được buổi 1010 — GUI không
    #   lưu. Dữ liệu người test gửi về mà thiếu cấu hình thì không so được. ]]"""
    try:
        import cap_nhat
        pb = cap_nhat.PHIEN_BAN_APP
    except Exception:                                        # noqa: BLE001
        pb = ""
    try:
        import autotone as at
        dau = at.dau_engine()
    except Exception:                                        # noqa: BLE001
        dau = ""
    goi = {"khi": datetime.now().isoformat(timespec="seconds"), "phien_ban": pb, "engine": dau,
           "job": Path(job).name if job else "", "so_anh": len(items or []),
           #  dict(...) chứ không (cfg or {}).items(): Cython (bản mã hoá) sập ở mẫu đó
           "cfg": {k: v for k, v in dict(cfg or {}).items() if isinstance(v, (int, float, str, bool, type(None)))
                   or (isinstance(v, (dict, list)) and len(json.dumps(v, default=_json)) < 4000)}}
    try:
        d = thu() / "lan_day" / ma_buoi(thu_muc)
        d.mkdir(parents=True, exist_ok=True)
        p = d / (datetime.now().strftime("%Y%m%d_%H%M%S") + ".json")
        dd.ghi_ben(p, json.dumps(goi, ensure_ascii=False, indent=1, default=_json))
        return p
    except OSError:
        return None


def lan_day_cuoi(thu_muc) -> dict:
    d = thu() / "lan_day" / ma_buoi(thu_muc)
    ds = sorted(d.glob("*.json")) if d.is_dir() else []
    if not ds:
        return {}
    try:
        return json.loads(ds[-1].read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


# ---------------------------------------------------------------- đọc các phần của buổi
def _cung_thu_muc(a, b) -> bool:
    return os.path.normcase(os.path.normpath(str(a))) == os.path.normcase(os.path.normpath(str(b)))


def tim_job(thu_muc, job_dir: Path) -> Path | None:
    """Job tool đẩy gần nhất cho thư mục này (apply_*.done, hoặc .tsv chưa áp)."""
    ds = []
    for p in list(job_dir.glob("apply_*.done")) + list(job_dir.glob("apply_*.tsv")):
        try:
            with io.open(p, encoding="utf-8-sig", newline="") as fh:
                next(fh, None)
                dong = next(fh, "")
            duong = dong.split("\t", 1)[0]
            if duong and _cung_thu_muc(os.path.dirname(duong.replace("/", "\\") if os.name == "nt" else duong),
                                       thu_muc):
                ds.append(p)
        except OSError:
            continue
    return max(ds, key=lambda p: p.stat().st_mtime) if ds else None


def doc_tsv(p: Path) -> dict:
    """{tên: {cột: giá trị}} cho job / baseline (cột đầu = path)."""
    out = {}
    with io.open(p, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            k = r.get("path") or next(iter(r.values()), "")
            out[_ten(k)] = r
    return out


def _ten(p: str) -> str:
    return os.path.splitext(os.path.basename(str(p).replace("\\", "/")))[0].strip().lower()


def _so(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def dem_sua(job: dict, chup_tsv: Path) -> tuple[int, int]:
    """(số ảnh người dùng SỬA so với job, số ảnh có trong cả hai)."""
    sua = chung = 0
    with io.open(chup_tsv, encoding="utf-8", newline="") as fh:
        next(fh, None)
        for dong in fh:
            dong = dong.rstrip("\r\n")
            if not dong:
                continue
            try:
                path, _sao, js = dong.split("\t", 2)
                s = json.loads(js)
            except (ValueError, json.JSONDecodeError):
                continue
            t = job.get(_ten(path))
            if not t:
                continue
            chung += 1
            for c, nguong in SAI_SUA.items():
                a, b = _so(t.get(c)), _so(s.get(c))
                if a is not None and b is not None and abs(a - b) > nguong:
                    sua += 1
                    break
    return sua, chung


def xin_chup(thu_muc, ra: Path, job_dir: Path, cho: float = CHO_CHUP_GIAY,
             dung=lambda: False) -> Path | None:
    """Nhờ plugin Lightroom chụp catalog của thư mục (ChupCore) vào `ra`. None nếu hỏng."""
    ra.mkdir(parents=True, exist_ok=True)
    xong = job_dir / "chup_xong.txt"
    try:
        xong.unlink()
    except OSError:
        pass
    yc = job_dir / "request_chup.txt"
    tam = yc.with_name(yc.name + ".part")
    tam.write_text(f"{thu_muc}\n{ra}\n", encoding="utf-8")
    os.replace(tam, yc)
    t0 = time.time()
    while time.time() - t0 < cho and not dung():
        if xong.is_file():
            try:
                kq = xong.read_text(encoding="utf-8").strip().split("\t")
            except OSError:
                kq = []
            if kq and kq[0] != "LOI" and Path(kq[0]).is_file():
                return Path(kq[0])
            if kq and kq[0] == "LOI":
                return None
        time.sleep(1.0)
    return None


def anh_nho(nguon: Path, dich: Path, canh: int = CANH_ANH_NHO) -> bool:
    """Preview `canh` px (mặc định 384), KHÔNG EXIF/GPS (chỉ đọc ảnh gốc)."""
    try:
        from PIL import Image
        import autotone as at
        if nguon.suffix.lower() in (".jpg", ".jpeg", ".png", ".tif", ".tiff"):
            im = Image.open(nguon)
            huong = None
            try:
                huong = im.getexif().get(0x0112)
            except Exception:                                # noqa: BLE001
                pass
        else:
            blob, tags = at.read_raw(nguon)
            if blob is None:
                return False
            im = Image.open(io.BytesIO(blob))
            huong = (tags or {}).get("orientation")
        im.draft("RGB", (canh * 2, canh * 2))
        im = im.convert("RGB")
        if huong:
            im = at.apply_orientation(im, huong)
        im.thumbnail((canh, canh))
        dich.parent.mkdir(parents=True, exist_ok=True)
        im.save(dich, "JPEG", quality=CHAT_LUONG_ANH_NHO, optimize=True)   # không truyền exif
        return True
    except Exception:                                        # noqa: BLE001
        return False


def _thiet_bi() -> dict:
    d = {"he": platform.system(), "ban_he": platform.release(), "may": platform.machine(),
         "cpu": platform.processor(), "loi": os.cpu_count()}
    try:
        import psutil
        d["ram_gb"] = round(psutil.virtual_memory().total / 2 ** 30, 1)
    except Exception:                                        # noqa: BLE001
        pass
    #  Tên card: chỉ khi torch ĐÃ nạp sẵn (engine retouch) — không bắt giao diện nạp torch.
    import sys
    tc = sys.modules.get("torch")
    if tc is not None:
        try:
            if tc.cuda.is_available():
                d["gpu"] = tc.cuda.get_device_name(0)
            elif getattr(tc.backends, "mps", None) is not None and tc.backends.mps.is_available():
                d["gpu"] = "Apple MPS"
        except Exception:                                    # noqa: BLE001
            pass
    return d


def _file_toc_do() -> Path | None:
    """nhat_ky_toc_do.csv của engine retouch (saytool/nhat_ky._noi_ghi: cạnh gói saytool,
    không ghi được thì ~/.say_anh)."""
    ung = [Path.home() / ".say_anh" / "nhat_ky_toc_do.csv"]
    try:
        import importlib.util
        sp = importlib.util.find_spec("saytool")
        if sp is not None and sp.origin:
            ung.insert(0, Path(sp.origin).resolve().parents[1] / "nhat_ky_toc_do.csv")
    except Exception:                                        # noqa: BLE001
        pass
    for p in ung:
        if p.is_file():
            return p
    return None


def _thay_duong(txt: str, thu_muc, ma: str) -> str:
    """Thay thư mục ảnh thật bằng X:\\<mã buổi>: dạng thường, dạng JSON (\\\\) và dạng /,
    không phân biệt hoa thường, cùng chuẩn Unicode NFC (Mac lưu tên tệp NFD)."""
    import re
    import unicodedata
    txt = unicodedata.normalize("NFC", txt)
    goc = unicodedata.normalize("NFC", os.path.normpath(str(thu_muc)))
    for bien, thay in ((goc.replace("\\", "\\\\"), "X:\\\\" + ma),
                       (goc, "X:\\" + ma),
                       (goc.replace("\\", "/"), "X:/" + ma)):
        txt = re.sub(re.escape(bien), lambda _m, t=thay: t, txt, flags=re.IGNORECASE)
    return txt


# ---------------------------------------------------------------- đóng gói
def dong_goi(thu_muc, bao=print, job_dir: Path | None = None, dung=lambda: False,
             cho_chup: float = CHO_CHUP_GIAY) -> Path | None:
    """Đóng gói một buổi đã sửa tay -> zip trong hàng đợi. None nếu không có gì để gửi."""
    if not _KHOA_DONG_GOI.acquire(blocking=False):
        bao("góp ý: đang đóng gói buổi khác — bỏ qua lần này")
        return None
    try:
        return _dong_goi(Path(thu_muc), bao, job_dir, dung, cho_chup)
    finally:
        _KHOA_DONG_GOI.release()


def _dong_goi(thu_muc: Path, bao, job_dir, dung, cho_chup) -> Path | None:
    import pickle
    import zlib
    import autotone as at
    job_dir = Path(job_dir or at.LR_JOB_DIR)
    f = at.file_ket_qua_do(thu_muc)
    if not f.is_file():
        bao("góp ý: buổi chưa phân tích — không có số đo")
        return None
    goi = pickle.loads(zlib.decompress(f.read_bytes()))
    items = goi.get("items") or []
    job = tim_job(thu_muc, job_dir)
    if job is None:
        bao("góp ý: tool chưa đẩy buổi này sang Lightroom — không có gì để so")
        return None
    ma = ma_buoi(thu_muc)
    nguoi = ma_nguoi()
    luc = datetime.now().strftime("%Y%m%d_%H%M%S")
    tam = thu() / "tam" / f"{ma}_{luc}"
    shutil.rmtree(tam, ignore_errors=True)
    tam.mkdir(parents=True)
    try:
        bao("góp ý: nhờ Lightroom chụp thông số đã sửa…")
        chup = xin_chup(thu_muc, tam / "_chup", job_dir, cho_chup, dung)
        if chup is None:
            bao("góp ý: Lightroom không chụp được catalog (chưa mở / plugin cũ) — để lần sau")
            return None
        jt = doc_tsv(job)
        sua, chung = dem_sua(jt, chup)
        if sua < SUA_TOI_THIEU:
            bao(f"góp ý: chỉ {sua} ảnh sửa tay — không gửi")
            return None
        ten_b = f"{nguoi}_{ma}"
        # số đo — định dạng do_buoi.py (kiem_2ban_quay.nap_do)
        for r in items:
            r.pop("dt_obj", None)
        so_do = {"buoi": ten_b, "thu_muc": "X:\\" + ma, "khi": goi.get("luc"), "so_anh": len(items),
                 "autotone_sha1": goi.get("engine"), "loi": [], "items": items}
        #  ensure_ascii=False: thư mục có dấu (G:\\Ănhoi2009) phải còn nguyên chữ để thay đường dẫn
        txt = _thay_duong(json.dumps(so_do, default=_json, ensure_ascii=False), thu_muc, ma)
        with gzip.open(tam / f"do_{ten_b}.json.gz", "wt", encoding="utf-8") as fh:
            fh.write(txt)
        # job / bản chụp / baseline — thay đường dẫn. Tên job: apply_<ngày>_<giờ>_<buổi>.done
        # (kiem_2ban_quay tìm apply_*_<buổi>.done) — tên thư mục có "_" (raw_19.4) nên cắt theo mẫu
        import re
        m = re.match(r"^(apply_\d{8}_\d{6})_", job.name)
        dau = m.group(1) if m else "apply_" + datetime.fromtimestamp(job.stat().st_mtime).strftime("%Y%m%d_%H%M%S")
        (tam / f"{dau}_{ten_b}.done").write_text(
            _thay_duong(job.read_text(encoding="utf-8-sig"), thu_muc, ma), encoding="utf-8")
        (tam / chup.name).write_text(_thay_duong(chup.read_text(encoding="utf-8"), thu_muc, ma),
                                     encoding="utf-8")
        bl = thu_muc / at.BASELINE_NAME
        if bl.is_file():
            (tam / at.BASELINE_NAME).write_text(_thay_duong(bl.read_text(encoding="utf-8"), thu_muc, ma),
                                                encoding="utf-8")
        shutil.rmtree(tam / "_chup", ignore_errors=True)
        # tốc độ retouch trên máy này
        nk = _file_toc_do()
        if nk is not None:
            try:
                shutil.copy2(nk, tam / "toc_do.csv")
            except OSError:
                pass
        may = sorted({str(r.get("model") or "") for r in items if r.get("model")})
        cho = thu() / "cho"
        cho.mkdir(parents=True, exist_ok=True)
        z = cho / f"{ten_b}_{luc}.zip"
        zt = z.with_name(z.name + ".part")
        #[[ GOI_TOI_DA: Cloudflare (goi mien phi) chan than yeu cau > 100 MB -> goi to hon
        #   khong bao gio gui duoc, nam hang doi mai. Do that 12/10: ~22 MB / 1000 anh (anh
        #   nho 18 KB + so do) -> buoi ~4500 anh tro len vuot. Vuot thi dong lai voi anh nho
        #   thu theo ti le that; duoi 128 px van vuot -> bo anh nho, giu so do. ]]
        canh = CANH_ANH_NHO
        while True:
            shutil.rmtree(tam / "anh_nho", ignore_errors=True)
            n_anh = 0
            for r in items if canh else []:
                if dung():
                    return None
                p = Path(str(r.get("path") or ""))
                if p.is_file() and anh_nho(p, tam / "anh_nho" / (p.stem + ".jpg"), canh):
                    n_anh += 1
            meta = {"dinh_dang": PHIEN_DINH_DANG, "nguoi": nguoi, "buoi": ten_b, "ma_buoi": ma,
                    "khi": datetime.now().isoformat(timespec="seconds"),
                    "phien_ban": lan_day_cuoi(thu_muc).get("phien_ban") or _phien_ban(),
                    "lan_day": lan_day_cuoi(thu_muc), "thiet_bi": _thiet_bi(), "than_may": may,
                    "so_anh": len(items), "anh_sua": sua, "anh_chung": chung, "anh_nho": n_anh,
                    "canh_anh_nho": canh, "ten_thu_muc_goc_bam": _bam(thu_muc.name, 8)}
            (tam / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1, default=_json),
                                           encoding="utf-8")
            with zipfile.ZipFile(zt, "w", zipfile.ZIP_DEFLATED) as zf:
                for p in sorted(tam.rglob("*")):
                    if p.is_file():
                        zf.write(p, p.relative_to(tam).as_posix())
            co = zt.stat().st_size
            if co <= GOI_TOI_DA or not canh:
                break
            canh = int(canh * math.sqrt(GOI_TOI_DA * 0.85 / co)) // 16 * 16
            canh = canh if canh >= 128 else 0
            bao(f"góp ý: gói {co / 1e6:.0f} MB vượt {GOI_TOI_DA / 1e6:.0f} MB — đóng lại "
                + (f"với ảnh nhỏ {canh} px" if canh else "không kèm ảnh nhỏ"))
        os.replace(zt, z)
        bao(f"góp ý: đóng gói {len(items)} ảnh ({sua} ảnh sửa tay, {n_anh} ảnh nhỏ) — "
            f"{z.stat().st_size / 1e6:.1f} MB")
        return z
    finally:
        shutil.rmtree(tam, ignore_errors=True)


def _phien_ban() -> str:
    try:
        import cap_nhat
        return cap_nhat.PHIEN_BAN_APP
    except Exception:                                        # noqa: BLE001
        return ""


# ---------------------------------------------------------------- gửi
def gui(z: Path, url: str | None = None, timeout: float = 600) -> tuple[bool, str]:
    """POST một gói lên máy nhận. (được không, lời nhắn)."""
    url = (url or dia_chi()).rstrip("/")
    if not url:
        return False, "chưa có địa chỉ máy nhận"
    try:
        with open(z, "rb") as fh:
            yc = urllib.request.Request(
                url + "/gop-y", data=fh, method="POST",
                headers={"Content-Type": "application/zip", "Content-Length": str(z.stat().st_size),
                         "X-Gop-Y-Khoa": BI_MAT, "X-Nguoi": ma_nguoi(), "X-Goi": z.name,
                         "User-Agent": f"ToneRetouch/{_phien_ban()}"})
            with urllib.request.urlopen(yc, timeout=timeout) as tl:
                ok = 200 <= tl.status < 300
                return ok, tl.read(300).decode("utf-8", "replace")
    except urllib.error.HTTPError as ex:
        return False, f"HTTP {ex.code}"
    except (OSError, ValueError) as ex:
        return False, f"{type(ex).__name__}: {ex}"


def _bo(z: Path) -> None:
    """Xoá gói đã gửi. Diệt virus / chỉ mục Windows hay giữ file mới ghi vài giây: thử lại,
    không được thì đổi đuôi .da_gui để vòng sau KHÔNG gửi trùng (xoá ở vòng sau)."""
    for _ in range(10):
        try:
            z.unlink()
            return
        except FileNotFoundError:
            return
        except OSError:
            time.sleep(0.3)
    try:
        os.replace(z, z.with_suffix(".da_gui"))
    except OSError:
        pass


def gui_het(bao=print, url: str | None = None) -> int:
    """Gửi mọi gói trong hàng đợi; được thì chuyển biên nhận sang da_gui/ và xoá zip."""
    if not bat():
        return 0
    cho = thu() / "cho"
    da = thu() / "da_gui"
    n = 0
    for z in sorted(cho.glob("*.zip")) if cho.is_dir() else []:
        ok, chu = gui(z, url)
        if not ok:
            bao(f"góp ý: chưa gửi được {z.name} ({chu}) — thử lại sau")
            break
        da.mkdir(parents=True, exist_ok=True)
        (da / (z.stem + ".json")).write_text(json.dumps(
            {"goi": z.name, "co_mb": round(z.stat().st_size / 1e6, 2),
             "gui_luc": datetime.now().isoformat(timespec="seconds"), "may_nhan": chu[:200]},
            ensure_ascii=False), encoding="utf-8")
        _bo(z)
        n += 1
    try:
        for p in cho.glob("*.da_gui"):
            p.unlink()
        cu = sorted(da.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for p in cu[GIU_DA_GUI:]:
            p.unlink()
    except OSError:
        pass
    return n


def ghi_nhat_ky(s: str) -> None:
    """gop_y/nhat_ky.txt — luồng nền KHÔNG chạm giao diện Tk."""
    try:
        thu().mkdir(parents=True, exist_ok=True)
        with open(thu() / "nhat_ky.txt", "a", encoding="utf-8") as fh:
            fh.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S  ") + str(s) + "\n")
    except OSError:
        pass


_LUONG_GUI: list = []


def chay_nen(bao=ghi_nhat_ky) -> None:
    """Luồng nền: thử gửi hàng đợi mỗi NHIP_GUI_GIAY (máy nhận tại nhà có lúc tắt)."""
    if _LUONG_GUI:
        return

    def vong():
        time.sleep(30)
        while True:
            try:
                if bat() and dia_chi():
                    gui_het(bao)
            except Exception:                                # noqa: BLE001
                pass
            time.sleep(NHIP_GUI_GIAY)

    t = threading.Thread(target=vong, daemon=True, name="gop_y_gui")
    _LUONG_GUI.append(t)
    t.start()


def dong_goi_nen(thu_muc, bao=ghi_nhat_ky) -> None:
    """Đóng gói rồi gửi, trên luồng nền (gọi từ giao diện)."""
    if not bat() or ly_do_tat():
        return

    def lam():
        try:
            z = dong_goi(thu_muc, bao)
            if z is not None and dia_chi():
                gui_het(bao)
        except Exception as ex:                              # noqa: BLE001
            bao(f"góp ý: lỗi đóng gói ({type(ex).__name__}: {ex})")

    threading.Thread(target=lam, daemon=True, name="gop_y_dong_goi").start()
