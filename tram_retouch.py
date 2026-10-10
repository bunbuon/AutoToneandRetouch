#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tram_retouch.py — TRẠM RETOUCH cho lượt Export của Lightroom (10/10).

User 10/10: "đưa phần Retouch thành plugin add vào Lightroom, khi Export thì plugin
Retouch cũng chạy cùng để xuất bức ảnh ra là đã được retouch" + "nạp mô hình ngay khi
người dùng thay đổi thông số retouch hoặc chọn preset — bấm xuất là chỉ xuất ảnh".

ĐƯỜNG ĐI
  Lightroom render một ảnh -> hành động Post-Process "AutoTone: Retouch khi xuất"
  (AutoTone.lrplugin/RetouchKhiXuat.lua) ghi <jobs>/tram_retouch/yc_<id>.txt (ảnh vừa
  render + file RAW gốc + chế độ mức) rồi CHỜ -> trạm (file này) nhận, tra mức, chạy
  engine retouch, GHI ĐÈ TẠI CHỖ file Lightroom vừa render, ghi kq_<id>.txt -> plugin
  báo Lightroom xong ảnh đó -> Lightroom ghi ảnh (đã retouch) ra thư mục đích.

MỘT ENGINE CHO CẢ APP (GIU)
  Engine xem trước của màn Retouch (xem_truoc.MayXem — mô hình đã nạp) CHÍNH LÀ engine
  trạm dùng. Hai engine là hai bộ mô hình trên card 8 GB cùng Lightroom — không được.
  Người dùng kéo thanh / chọn preset -> app "giữ" engine 30 phút (GIU.giu) kể cả khi
  rời màn Retouch; Lightroom xuất trong lúc đó là chạy ngay, không nạp gì.

AI PHỤC VỤ
  - App đang mở: luồng Tram(loai="app") trong app, dùng GIU.
  - App tắt: plugin mở trạm chạy ngầm `AutoTone --say-tram <thư mục>` (Tram loai=
    "rieng", lệnh lấy từ tram_lenh.txt app ghi) ngay khi hộp thoại Export mở — nạp mô
    hình trong lúc người dùng còn chọn thông số. Rảnh 10 phút thì tự thoát.
  - Hai bên không tranh nhau: app chỉ nhận việc khi engine của nó đã nạp HOẶC không
    có trạm riêng; trạm riêng nhường hẳn khi thấy engine app đã sẵn sàng.

ẢNH HIỆN TRONG THƯ MỤC XUẤT LÀ ĐÃ RETOUCH (11/10 — thử thật: Lightroom render THẲNG
  vào thư mục xuất và render trước rất nhanh — 41 ảnh chưa retouch hiện hết rồi mới bị
  đè dần). Nay plugin bảo Lightroom render vào thư mục tạm ẩn <đích>/.autotone_dang_
  retouch (filterSettings của SDK), báo trước cho trạm (cho_<id>.txt). Trạm retouch SỚM
  theo lô ngay khi file render ghi trọn (JPEG có FFD9 + cỡ đứng yên), GIỮ kết quả; plugin
  tới ảnh đó (Lightroom đã xong với file) thì ghi san_<id>.txt -> trạm os.replace bản
  retouch sang đúng tên đích (cùng ổ: nguyên tử). Không chuyển file trước san_: Lightroom
  có thể còn đụng tới file nó vừa render.

TỆP TRONG <jobs>/tram_retouch/   (key=value, UTF-8 — Lua đọc / ghi được, khỏi JSON)
  cho_<id>.txt    plugin (lúc Lightroom định đường render): anh=<file tạm>, dich=<đích>,
                  goc=, che_do=
  san_<id>.txt    plugin: Lightroom đã render xong ảnh này -> trạm được giao sang đích
  yc_<id>.txt     plugin (Lightroom bỏ qua đường tạm, vd Export with Previous): sửa TẠI
                  CHỖ như bản đầu — anh=, goc=, che_do=, t=
  dang_<id>.txt   trạm đã nhận (đổi tên nguyên tử — hai trạm không cùng làm một ảnh)
  kq_<id>.txt     trạm: ok=1|0, bo_qua=1|0, loi=, mo_ta=, giay=
  huy_<id>.txt    plugin: quá giờ — trạm KHÔNG được đè file nữa
  tram_app.txt / tram_rieng.txt   nhịp: pid, san_sang, may, dang, t (giây epoch)
  xin_nap.txt     plugin: hộp Export vừa mở -> nạp + hâm nóng mô hình (che_do=)
  tram_lenh.txt   app: lệnh mở trạm chạy ngầm (plugin chạy khi không thấy trạm nào)
  presets.txt     tên preset retouch (hộp Export liệt kê)
  tram.log        nhật ký
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

TEN_THU_MUC = "tram_retouch"
LENH = "tram_lenh.txt"
XIN_NAP = "xin_nap.txt"
DS_PRESET = "presets.txt"
NHAT_KY = "tram.log"
GAN_NHAT = "tram_muc_gan_nhat.json"          # trong thư mục dữ liệu app
MOC_TAM = ".autotone_tam"
DUOI_NHAN = {".jpg", ".jpeg", ".tif", ".tiff", ".png"}

GIU_GIAY = 30 * 60        # giữ engine sau lần đổi mức / lần retouch cuối
RANH_THOAT = 10 * 60      # trạm chạy ngầm rảnh chừng này thì thoát
CU_GIAY = 5               # nhịp cũ hơn -> coi như trạm đó không chạy
CU_YEU_CAU = 15 * 60      # yêu cầu nằm lâu hơn (plugin đã bỏ) -> dọn
NHA_CPU_GIAY = 60         # rảnh chừng này thì trả CPU (an toàn máy)
LO_TOI_DA = 4             # ảnh mỗi mẻ engine (song song trong engine, kết quả ra theo lô)
ON_DINH_GIAY = 0.4        # file render đứng yên chừng này mới coi là ghi xong
NONG_SAU_GIAY = 2.0       # người dùng ngừng đổi mức chừng này thì hâm nóng


# ====================================================================== tệp
def thu_muc(jd=None) -> Path:
    if jd is None:
        import autotone as at
        jd = at.LR_JOB_DIR
    d = Path(jd) / TEN_THU_MUC
    d.mkdir(parents=True, exist_ok=True)
    return d


def ghi_kv(p: Path, d: dict) -> None:
    """key=value mỗi dòng, ghi .part rồi đổi tên (bên đọc không gặp file dở)."""
    tam = p.with_name(p.name + ".part")
    dong = []
    for k, v in d.items():
        v = "" if v is None else str(v)
        dong.append(f"{k}={v.replace(chr(13), ' ').replace(chr(10), ' ')}")
    tam.write_text("\n".join(dong) + "\n", encoding="utf-8")
    os.replace(tam, p)


def doc_kv(p: Path) -> dict | None:
    try:
        txt = Path(p).read_text(encoding="utf-8-sig")
    except OSError:
        return None
    d = {}
    for dong in txt.splitlines():
        if "=" in dong:
            k, v = dong.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def doc_nhip(thu: Path, loai: str, cu: float = CU_GIAY) -> dict | None:
    """Nhịp của trạm `loai` ("app" | "rieng") nếu còn mới, không thì None."""
    d = doc_kv(Path(thu) / f"tram_{loai}.txt")
    if not d:
        return None
    try:
        if time.time() - float(d.get("t") or 0) > cu:
            return None
    except ValueError:
        return None
    return d


def nhat_ky(thu: Path, chu: str) -> None:
    f = Path(thu) / NHAT_KY
    try:
        if f.is_file() and f.stat().st_size > 2_000_000:
            f.replace(f.with_suffix(".log.cu"))
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(time.strftime("%m-%d %H:%M:%S ") + chu + "\n")
    except OSError:
        pass


def file_xong(p: Path, nho: dict, k) -> bool:
    """File Lightroom render đã ghi trọn chưa: cỡ / thời gian sửa đứng yên ON_DINH_GIAY,
    JPEG phải kết thúc bằng FFD9 (đang ghi dở thì chưa có)."""
    try:
        st = Path(p).stat()
    except OSError:
        return False
    if st.st_size <= 0:
        return False
    bay = time.monotonic()
    dau = (st.st_size, st.st_mtime_ns)
    cu = nho.get(k)
    t0 = cu[2] if cu and cu[:2] == dau else bay
    nho[k] = (dau[0], dau[1], t0)
    if bay - t0 < ON_DINH_GIAY:
        return False
    if Path(p).suffix.lower() in (".jpg", ".jpeg"):
        try:
            with open(p, "rb") as fh:
                fh.seek(-2, 2)
                return fh.read(2) == b"\xff\xd9"
        except OSError:
            return False
    return True


def an_thu_muc(p) -> None:
    """Ẩn thư mục render tạm trong thư mục xuất (Windows)."""
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.kernel32.SetFileAttributesW(str(p), 0x2)
    except Exception:                                        # noqa: BLE001
        pass


def anh_nong() -> Path | None:
    """Ảnh mẫu có mặt người để hâm nóng (đi kèm insightface trong gói / venv), phóng lên
    cỡ ảnh xuất thật (tool bỏ qua mặt < 150 px). None nếu không có."""
    g = None
    try:
        if getattr(sys, "frozen", False):
            g = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "insightface"
        else:
            import importlib.util
            sp = importlib.util.find_spec("insightface")
            if sp is not None and sp.submodule_search_locations:
                g = Path(list(sp.submodule_search_locations)[0])
    except Exception:                                        # noqa: BLE001
        g = None
    if g is None:
        return None
    nguon = g / "data" / "images" / "t1.jpg"
    if not nguon.is_file():
        return None
    try:
        import tempfile
        from PIL import Image
        ra = Path(tempfile.gettempdir()) / "autotone_anh_nong.jpg"
        if not ra.is_file():
            with Image.open(nguon) as im:
                im = im.convert("RGB")
                k = 3000 / max(im.size)
                im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
                tam = ra.with_suffix(".part.jpg")
                im.save(tam, "JPEG", quality=92)
                os.replace(tam, ra)
        return ra
    except Exception:                                        # noqa: BLE001
        return None


# ====================================================================== mức
def ghi_gan_nhat(muc: dict, preset: str = "", vao: str = "") -> None:
    """Mức người dùng vừa đặt trong app — trạm dùng khi buổi đang xuất chưa có mức."""
    try:
        import duong_dan as dd
        dd.ghi_ben(dd.du_lieu(GAN_NHAT), json.dumps(
            {"muc": dict(muc or {}), "preset": preset or "", "vao": str(vao or ""),
             "t": time.time()}, ensure_ascii=False))
    except Exception:                                        # noqa: BLE001
        pass


def doc_gan_nhat() -> dict | None:
    try:
        import duong_dan as dd
        d = json.loads(dd.du_lieu(GAN_NHAT).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) and isinstance(d.get("muc"), dict) else None
    except (OSError, ValueError, TypeError):
        return None
    except Exception:                                        # noqa: BLE001
        return None


def muc_cho(rt, che_do: str, goc: str) -> tuple:
    """(bộ mức, mô tả) cho một ảnh xuất. None = chưa có mức nào để áp.

    che_do "preset:<tên>": đúng preset đó cho mọi ảnh (user 9/10: chọn preset thì
    dùng thông số của preset). "app": mức người dùng đặt trong app cho BUỔI của file
    RAW gốc (mức riêng của chính ảnh > mức chung của buổi) — y như màn Retouch chế
    độ "Ảnh RAW của buổi" hiện trên preview; buổi chưa đặt gì thì mức gần nhất."""
    che_do = str(che_do or "app")
    if che_do.startswith("preset:"):
        ten = che_do[len("preset:"):]
        try:
            import retouch_preset as rp
            m = rp.doc(ten)
        except Exception:                                    # noqa: BLE001
            m = None
        if m is None:
            return None, f"không đọc được preset “{ten}”"
        return dict(m), f"preset “{ten}”"
    if goc:
        vao = str(Path(goc).parent)
        try:
            chung = rt.doc_muc_chung(vao)
            rieng = rt.doc_muc_anh(vao).get(rt.khoa_anh(goc, vao, False))
            ps = rt.doc_preset_thu_muc(vao)
        except Exception:                                    # noqa: BLE001
            chung, rieng, ps = {}, None, ""
        if rieng is not None:
            d = {k: v for k, v in dict(chung or {}).items() if ":" not in str(k)}
            d.update(rieng)
            return d, "mức riêng của ảnh"
        if chung:
            return dict(chung), ("mức buổi" + (f" (preset “{ps}”)" if ps else " (Tuỳ chỉnh)"))
    g = doc_gan_nhat()
    if g:
        ps = g.get("preset") or ""
        return dict(g["muc"]), "mức gần nhất đặt trong app" + (f" (preset “{ps}”)" if ps else "")
    return None, "chưa đặt mức retouch nào trong app"


# ====================================================================== engine chung
class GiuMay:
    """MỘT engine retouch cho cả app: xem trước (màn Retouch) và trạm (Lightroom xuất).

    lay(): có sẵn thì dùng chung, chưa có thì mở. tha(): người dùng xong — chỉ đóng
    thật khi không ai còn dùng, không đang chạy mẻ, và không còn được "giữ" (người
    dùng vừa đổi mức / vừa có lượt xuất -> giữ GIU_GIAY để lần sau khỏi nạp)."""

    def __init__(self):
        self.may = None
        self.goc = None
        self.so_dung = 0
        self.giu_toi = 0.0
        self._khoa = threading.RLock()

    def song(self) -> bool:
        m = self.may
        return m is not None and m.song()

    def san_sang(self) -> bool:
        m = self.may
        return m is not None and m.song() and bool(getattr(m, "co_chay", None))

    def thiet_bi(self) -> str:
        m = self.may
        t = getattr(m, "tin_san_sang", None) or {}
        return str(t.get("may") or "")

    def lay(self, rt, goc, may: str = "auto", dung: bool = True) -> tuple:
        """-> (MayXem | None, lỗi, mới mở?)."""
        with self._khoa:
            m = self.may
            if m is not None:
                khac = goc and self.goc and (os.path.normcase(os.path.abspath(str(goc)))
                                             != os.path.normcase(os.path.abspath(str(self.goc))))
                if not m.song() or khac:
                    self._dong()
            moi = False
            if self.may is None:
                import xem_truoc
                m = xem_truoc.MayXem(rt, goc)
                loi = m.bat_dau(may or "auto")
                if loi:
                    return None, loi, False
                self.may, self.goc, moi = m, str(goc), True
            if dung:
                self.so_dung += 1
            return self.may, "", moi

    def tha(self, m=None, dung: bool = True) -> bool:
        """Người dùng `m` không cần nữa. -> True nếu engine đã đóng thật."""
        with self._khoa:
            if dung and self.so_dung > 0:
                self.so_dung -= 1
            if m is not None and m is not self.may:
                try:
                    m.dong()
                except Exception:                            # noqa: BLE001
                    pass
                return True
            return self.don()

    def don(self, ep: bool = False) -> bool:
        with self._khoa:
            if self.may is None:
                return True
            if not ep:
                if not self.may.song():
                    self._dong()
                    return True
                if (self.so_dung > 0 or time.time() < self.giu_toi
                        or getattr(self.may, "dang_chay", False)):
                    return False
            self._dong()
            return True

    def _dong(self):
        m, self.may, self.goc = self.may, None, None
        if m is not None:
            try:
                m.dong()
            except Exception:                                # noqa: BLE001
                pass

    def giu(self, giay: float = GIU_GIAY) -> None:
        self.giu_toi = max(self.giu_toi, time.time() + giay)


GIU = GiuMay()


# ====================================================================== trạm
class Tram:
    """Một trạm nhận yêu cầu retouch. loai="app" (trong app) | "rieng" (chạy ngầm)."""

    NGU = 0.15

    def __init__(self, thu: Path, loai: str = "app", rt=None, giu: GiuMay | None = None,
                 goc_tool=None, dang_xuat=None, khoa_ok=None, chan=None):
        self.thu = Path(thu)
        self.thu.mkdir(parents=True, exist_ok=True)
        self.loai = loai
        self._rt = rt
        self.giu = giu or GIU
        self._goc_tool = goc_tool          # đường dẫn hoặc hàm trả đường dẫn tool retouch
        self._dang_xuat = dang_xuat        # app: lượt Xuất của chính app đang ghim CPU?
        self._khoa_ok = khoa_ok            # hàm -> bản quyền còn dùng được?
        self._chan = chan                  # hàm -> "" hoặc lý do tạm chưa retouch được
        self._dung = threading.Event()
        self._luong = None
        self.t_nhip = 0.0
        self.t_viec = time.time()          # lần cuối có việc
        self.dang = 0
        self.so_xong = 0
        self._ds_preset_cu = None
        self._ghim = []
        self._t_khoa = 0.0
        self._khoa_cache = True
        self._dem_tam = 0
        self._khoa_nhip = threading.Lock()
        self._kich: dict = {}              # id -> (cỡ, mtime, lúc đứng yên) — file_xong
        self._cho_giao: dict = {}          # id -> kết quả giữ chờ san_ (render vào thư mục tạm)
        self._da_an: set = set()
        self._buoc_nong: set = set()       # bước đã hâm nóng trên engine hiện tại
        self._may_nong = None
        self._nong_cho = None              # (bộ mức, lý do) chờ hâm nóng
        self._t_gan_nhat = self._mtime_gan_nhat()   # mức lúc trạm bật = mức cũ
        self._t_doi_gan_nhat = 0.0
        self.dang_nong = False

    # ------------------------------------------------------------ phụ
    @property
    def rt(self):
        if self._rt is None:
            import retouch
            self._rt = retouch
        return self._rt

    def goc_tool(self):
        g = self._goc_tool() if callable(self._goc_tool) else self._goc_tool
        if not g:
            try:
                g = self.rt.tim_tool()
            except Exception:                                # noqa: BLE001
                g = None
        return g

    def log(self, chu: str) -> None:
        nhat_ky(self.thu, f"[{self.loai}] {chu}")

    def ban_quyen_ok(self) -> bool:
        if self._khoa_ok is not None:
            try:
                return bool(self._khoa_ok())
            except Exception:                                # noqa: BLE001
                return True
        if time.time() - self._t_khoa < 60:
            return self._khoa_cache
        self._t_khoa = time.time()
        try:
            import ban_quyen as bq
            import khoa
            self._khoa_cache = bool(bq.kiem()["co_phep"] or khoa.kiem()["chay_duoc"])
        except Exception:                                    # noqa: BLE001
            self._khoa_cache = True
        return self._khoa_cache

    # ------------------------------------------------------------ nhịp
    def ghi_nhip(self, ep: bool = False) -> None:
        if not ep and time.time() - self.t_nhip < 1.0:
            return
        with self._khoa_nhip:
            self.t_nhip = time.time()
            try:
                ghi_kv(self.thu / f"tram_{self.loai}.txt", {
                    "pid": os.getpid(), "loai": self.loai,
                    "san_sang": 1 if self.giu.san_sang() else 0,
                    "may": self.giu.thiet_bi(), "dang": self.dang, "xong": self.so_xong,
                    "dang_nong": 1 if self.dang_nong else 0,
                    "nong": 1 if (self.giu.san_sang() and not self.dang_nong
                                  and self._nong_cho is None and self._buoc_nong) else 0,
                    "t": int(time.time())})
            except OSError:
                pass
            self._ghi_ds_preset()

    def _vong_nhip(self) -> None:
        """Nhịp ở LUỒNG RIÊNG (11/10): trạm đang làm mẻ / nạp mô hình vẫn báo sống —
        trước đây im 45 s ở ảnh đầu, plugin tưởng trạm chết, mở thêm trạm ngầm nạp bộ
        mô hình thứ hai."""
        while not self._dung.is_set():
            self.ghi_nhip(ep=True)
            self._dung.wait(1.0)

    def _ghi_ds_preset(self) -> None:
        try:
            import retouch_preset as rp
            ds = rp.danh_sach()
        except Exception:                                    # noqa: BLE001
            return
        if ds == self._ds_preset_cu:
            return
        self._ds_preset_cu = list(ds)
        try:
            tam = self.thu / (DS_PRESET + ".part")
            tam.write_text("\n".join(ds) + ("\n" if ds else ""), encoding="utf-8")
            os.replace(tam, self.thu / DS_PRESET)
        except OSError:
            pass

    def xoa_nhip(self) -> None:
        try:
            (self.thu / f"tram_{self.loai}.txt").unlink()
        except OSError:
            pass

    # ------------------------------------------------------------ ai phục vụ
    def duoc_nhan(self) -> bool:
        if self.loai == "app":
            #  trạm riêng đang chạy mà engine app chưa nạp -> để trạm riêng làm
            return self.giu.song() or doc_nhip(self.thu, "rieng") is None
        a = doc_nhip(self.thu, "app")
        return not (a and a.get("san_sang") == "1")

    # ------------------------------------------------------------ engine
    def lay_may(self, cho: float = 120.0):
        """Engine sẵn sàng chạy mẻ (mở nếu chưa có). None nếu không mở được."""
        goc = self.goc_tool()
        if not self.giu.song():
            if not goc or not self.rt.hop_le(goc):
                self.log(f"không có tool retouch hợp lệ ({goc})")
                return None
            m, loi, moi = self.giu.lay(self.rt, goc, dung=False)
            if loi:
                self.log(f"không mở được engine: {loi}")
                return None
            if moi:
                self.log("đang nạp mô hình retouch…")
        m = self.giu.may
        if m is None:
            return None
        t0 = time.monotonic()
        if not m.chay_duoc(cho):
            self.log("engine không sẵn sàng chạy mẻ (cũ / chết)")
            return None
        if time.monotonic() - t0 > 1:
            self.log(f"engine sẵn sàng sau {time.monotonic() - t0:.1f} s · {self.giu.thiet_bi()}")
        return m

    def xin_nap(self) -> None:
        """Hộp Export vừa mở (plugin ghi xin_nap.txt): nạp engine ngay."""
        f = self.thu / XIN_NAP
        if not f.exists():
            return
        if self.loai == "app" and not self.giu.song() and doc_nhip(self.thu, "rieng"):
            return                         # trạm riêng đang giữ việc này
        d = doc_kv(f) or {}
        try:
            f.unlink()
        except OSError:
            pass
        self.giu.giu()
        if not self.giu.song():
            goc = self.goc_tool()
            if goc and self.rt.hop_le(goc):
                m, loi, _moi = self.giu.lay(self.rt, goc, dung=False)
                self.log("hộp Export mở — nạp sẵn mô hình retouch" + (f" (lỗi: {loi})" if loi else ""))
        try:
            muc, _mt = muc_cho(self.rt, d.get("che_do") or "app", "")
        except Exception:                                    # noqa: BLE001
            muc = None
        if muc:
            self._nong_cho = (muc, "hộp Export mở")

    # ------------------------------------------------------------ hâm nóng
    @staticmethod
    def buoc_cua(muc: dict) -> set:
        ra = set()
        for k, v in dict(muc or {}).items():
            try:
                if float(v or 0) > 0:
                    ra.add(str(k).split(":")[-1])
            except (TypeError, ValueError):
                pass
        return ra

    def can_nong(self, muc: dict) -> bool:
        m = self.giu.may
        if m is not self._may_nong:
            self._may_nong, self._buoc_nong = m, set()
        return bool(self.buoc_cua(muc) - self._buoc_nong)

    @staticmethod
    def _mtime_gan_nhat() -> float:
        try:
            import duong_dan as dd
            return dd.du_lieu(GAN_NHAT).stat().st_mtime
        except Exception:                                    # noqa: BLE001
            return 0.0

    def _soi_gan_nhat(self) -> None:
        """App: người dùng vừa đổi mức / chọn preset (tram_muc_gan_nhat.json đổi, kể cả
        lần đầu được tạo) -> ngừng tay NONG_SAU_GIAY thì hâm nóng các bước đó."""
        mt = self._mtime_gan_nhat()
        if not mt:
            return
        if mt != self._t_gan_nhat:
            self._t_gan_nhat = mt
            self._t_doi_gan_nhat = time.time()
            return
        if self._t_doi_gan_nhat and time.time() - self._t_doi_gan_nhat > NONG_SAU_GIAY:
            self._t_doi_gan_nhat = 0.0
            g = doc_gan_nhat()
            if g and self.giu.song():
                self._nong_cho = (g["muc"], "đổi mức trong app")

    def ham_nong(self) -> None:
        """Chạy MỘT ảnh mẫu qua đúng các bước đang bật: mô hình từng bước (nạp lười ở ảnh
        đầu — thử thật 45 s) nạp xong TRƯỚC khi Lightroom xuất."""
        nong, self._nong_cho = self._nong_cho, None
        if not nong:
            return
        muc, ly_do = nong
        if not muc or self.rt.muc_trong(muc) or not self.can_nong(muc):
            return
        anh = anh_nong()
        if anh is None:
            return
        may = self.lay_may(cho=180)
        if may is None:
            return
        import tempfile
        tam = Path(tempfile.mkdtemp(prefix="autotone_nong_"))
        buoc = self.buoc_cua(muc)
        self.dang_nong = True
        self.ghi_nhip(ep=True)
        t0 = time.monotonic()
        try:
            (tam / "vao").mkdir()
            shutil.copy2(anh, tam / "vao" / "nong.jpg")
            for _loai, _gt in self.rt.chay(self.goc_tool(), tam / "vao", tam / "ra", muc,
                                           engine=may, lam_lai=True, chat_luong="auto"):
                pass
            self._buoc_nong |= buoc
            self.log(f"hâm nóng mô hình ({ly_do}): {', '.join(sorted(buoc))} · "
                     f"{time.monotonic() - t0:.1f} s")
        except Exception as ex:                              # noqa: BLE001
            self.log(f"hâm nóng lỗi: {type(ex).__name__}: {ex}")
        finally:
            self.dang_nong = False
            shutil.rmtree(tam, ignore_errors=True)
            self.ghi_nhip(ep=True)

    # ------------------------------------------------------------ CPU (an toàn máy)
    def _ghim_cpu(self) -> None:
        if self._ghim:
            return
        try:
            import xuat_ui as xu
            if not xu.doc_cai_dat().get("an_toan_cpu"):
                return
            if self._dang_xuat is not None and self._dang_xuat():
                return                     # lượt Xuất của app đã ghim (và sẽ tự trả)
            e = xu.nhan_e()
            if not e:
                return
            pids = list(xu.pid_lightroom()) + [os.getpid()]
            m = self.giu.may
            if m is not None and getattr(m, "proc", None) is not None:
                pids.append(m.proc.pid)
            self._ghim = xu.ghim_cpu(pids, e) or []
            if self._ghim:
                self.log(f"an toàn CPU: ghim {len(self._ghim)} tiến trình vào {len(e)} luồng nhân E")
        except Exception:                                    # noqa: BLE001
            self._ghim = []

    def _tra_cpu(self) -> None:
        if not self._ghim:
            return
        try:
            import xuat_ui as xu
            xu.tra_cpu(self._ghim)
        except Exception:                                    # noqa: BLE001
            pass
        self._ghim = []
        self.log("an toàn CPU: trả lại CPU")

    # ------------------------------------------------------------ một vòng
    def mot_vong(self) -> int:
        """Nhịp + xin nạp + nhận và làm các yêu cầu đang chờ. -> số ảnh đã làm."""
        self.ghi_nhip()
        self.xin_nap()
        self.giao_cho()
        if self.loai == "app":
            self._soi_gan_nhat()
        if time.time() - self.t_viec > NHA_CPU_GIAY:
            self._tra_cpu()
        if self.loai == "app" and time.time() - self.t_viec > 5 and not self._cho_giao:
            self.giu.don()                 # hết hạn giữ + không ai dùng -> trả card
        if not self.duoc_nhan():
            return 0
        ds = self.nhan()
        if not ds:
            if self._nong_cho is not None:
                self.ham_nong()
            return 0
        if self.loai == "app":
            self._t_doi_gan_nhat = 0.0     # đang có việc thật — khỏi hâm nóng
        self.t_viec = time.time()
        self.dang = len(ds)
        self.ghi_nhip(ep=True)
        try:
            self.lam(ds)
        except Exception as ex:                              # noqa: BLE001
            self.log("LỖI trạm: " + "".join(traceback.format_exception_only(type(ex), ex)).strip())
            for y in ds:
                if not (self.thu / f"kq_{y['id']}.txt").exists():
                    self.tra_loi(y, ok=False, loi=f"lỗi trạm: {type(ex).__name__}")
        finally:
            self.dang = 0
            self.t_viec = time.time()
            self.giu.giu()
            self.giao_cho()
            self.ghi_nhip(ep=True)
        return len(ds)

    def _cu_qua(self, f: Path) -> bool:
        """Tệp nằm quá CU_YEU_CAU (plugin đã bỏ) -> xoá, True."""
        try:
            if time.time() - f.stat().st_mtime > CU_YEU_CAU:
                f.unlink()
                return True
        except OSError:
            return True
        return False

    def nhan(self) -> list:
        """Giành (đổi tên nguyên tử) các ảnh đã render xong -> [yêu cầu].
        cho_: render vào thư mục tạm — nhận khi file ghi trọn hoặc plugin đã báo san_.
        yc_: sửa tại chỗ (Lightroom bỏ qua đường tạm)."""
        ra = []
        try:
            ds_cho = sorted(self.thu.glob("cho_*.txt"))
        except OSError:
            ds_cho = []
        for f in ds_cho:
            if len(ra) >= LO_TOI_DA * 2:
                break
            id_ = f.stem[4:]
            if self._cu_qua(f):
                continue
            if (self.thu / f"huy_{id_}.txt").exists():
                try:
                    f.unlink()
                except OSError:
                    pass
                continue
            d = doc_kv(f) or {}
            tam = d.get("anh") or ""
            if not tam or not d.get("dich"):
                continue
            if not ((self.thu / f"san_{id_}.txt").exists() or file_xong(Path(tam), self._kich, id_)):
                continue
            dang = self.thu / f"dang_{id_}.txt"
            try:
                os.replace(f, dang)
            except OSError:
                continue
            self._kich.pop(id_, None)
            cha = str(Path(tam).parent)
            if cha not in self._da_an:
                self._da_an.add(cha)
                an_thu_muc(cha)
            d["id"], d["_dang"], d["_cho"] = id_, str(dang), True
            ra.append(d)
        try:
            ds = sorted(self.thu.glob("yc_*.txt"))
        except OSError:
            return ra
        for f in ds:
            id_ = f.stem[3:]
            try:
                tuoi = time.time() - f.stat().st_mtime
            except OSError:
                continue
            if tuoi > CU_YEU_CAU:
                try:
                    f.unlink()
                except OSError:
                    pass
                continue
            dang = self.thu / f"dang_{id_}.txt"
            try:
                os.replace(f, dang)
            except OSError:
                continue                   # trạm khác vừa giành
            y = doc_kv(dang) or {}
            y["id"] = id_
            y["_dang"] = str(dang)
            ra.append(y)
        return ra

    def tra_loi(self, y: dict, ok: bool, bo_qua: bool = False, loi: str = "",
                mo_ta: str = "", giay: float = 0.0) -> None:
        if ok and not bo_qua:
            self.so_xong += 1
        try:
            ghi_kv(self.thu / f"kq_{y['id']}.txt", {
                "ok": 1 if ok else 0, "bo_qua": 1 if bo_qua else 0, "loi": loi,
                "mo_ta": mo_ta, "giay": f"{giay:.2f}"})
        except OSError:
            pass
        for f in (y.get("_dang") or "", str(self.thu / f"san_{y['id']}.txt")):
            try:
                Path(f).unlink()
            except OSError:
                pass

    def ket(self, y: dict, ra_f=None, ok: bool = True, bo_qua: bool = False, loi: str = "",
            mo_ta: str = "", giay: float = 0.0) -> None:
        """Kết quả một ảnh. ra_f: bản retouch (None = giữ ảnh như Lightroom render).
        Sửa tại chỗ (yc_): đè ngay. Render vào thư mục tạm (cho_): GIỮ, giao sang đích
        khi plugin báo Lightroom đã xong ảnh đó (giao_cho)."""
        if y.get("_cho"):
            giu_f = None
            if ra_f is not None:
                try:
                    giu_f = Path(y["anh"]).with_name(f".kq_{y['id']}{Path(y['anh']).suffix}")
                    os.replace(ra_f, giu_f)
                except OSError as ex:
                    giu_f, ok, loi = None, False, f"không giữ được bản retouch: {ex}"
            try:
                Path(y.get("_dang") or "").unlink()
            except OSError:
                pass
            self._cho_giao[y["id"]] = {"y": y, "f": giu_f, "ok": ok, "bo_qua": bo_qua,
                                       "loi": loi, "mo_ta": mo_ta, "giay": giay,
                                       "t": time.time()}
            return
        if ra_f is not None:
            try:
                os.replace(ra_f, y["anh"])
            except OSError as ex:
                ok, loi = False, f"không đè được ảnh: {ex}"
        self.tra_loi(y, ok=ok, bo_qua=bo_qua, loi=loi, mo_ta=mo_ta, giay=giay)

    def giao_cho(self) -> int:
        """Giao các kết quả đang giữ mà plugin đã báo san_ (Lightroom xong với file):
        os.replace sang đúng tên đích (cùng ổ — ảnh hiện ra một lần, trọn vẹn), xoá file
        render tạm. Plugin đã huỷ (quá giờ / bấm ✕) thì bỏ — plugin tự chuyển bản gốc."""
        n = 0
        for id_, g in list(self._cho_giao.items()):
            y = g["y"]
            if (self.thu / f"huy_{id_}.txt").exists() or time.time() - g["t"] > CU_YEU_CAU:
                if g["f"] is not None:
                    try:
                        Path(g["f"]).unlink()
                    except OSError:
                        pass
                del self._cho_giao[id_]
                continue
            if not (self.thu / f"san_{id_}.txt").exists():
                continue
            ok, loi = g["ok"], g["loi"]
            try:
                if g["f"] is not None:
                    os.replace(g["f"], y["dich"])
                    try:
                        os.remove(y["anh"])
                    except OSError:
                        pass
                elif os.path.isfile(y["anh"]):
                    os.replace(y["anh"], y["dich"])
                else:
                    ok, loi = False, loi or "không còn file render"
            except OSError as ex:
                ok, loi = False, f"không giao được sang thư mục xuất: {ex}"
            del self._cho_giao[id_]
            self.tra_loi(y, ok=ok, bo_qua=g["bo_qua"], loi=loi, mo_ta=g["mo_ta"], giay=g["giay"])
            n += 1
        return n

    def da_huy(self, y: dict) -> bool:
        return (self.thu / f"huy_{y['id']}.txt").exists()

    # ------------------------------------------------------------ làm
    def lam(self, ds: list) -> None:
        try:
            ly = self._chan() if self._chan is not None else ""
        except Exception:                                    # noqa: BLE001
            ly = ""
        if ly:
            for y in ds:
                self.tra_loi(y, ok=False, loi=f"{ly} — ảnh không retouch")
            self.log(f"{len(ds)} ảnh: {ly}")
            return
        if not self.ban_quyen_ok():
            for y in ds:
                self.tra_loi(y, ok=False, loi="hết hạn bản quyền Tone&Retouch — ảnh không retouch")
            self.log(f"{len(ds)} ảnh: hết hạn bản quyền — không retouch")
            return
        rt = self.rt
        nhom: dict = {}
        for y in ds:
            anh = y.get("anh") or ""
            if self.da_huy(y):
                self.tra_loi(y, ok=False, loi="plugin đã huỷ (quá giờ)")
                continue
            if not anh or not os.path.isfile(anh):
                self.tra_loi(y, ok=False, loi="không thấy file Lightroom vừa render")
                continue
            if Path(anh).suffix.lower() not in DUOI_NHAN:
                self.ket(y, ok=True, bo_qua=True, mo_ta="định dạng không retouch")
                continue
            muc, mo_ta = muc_cho(rt, y.get("che_do") or "app", y.get("goc") or "")
            if muc is None or rt.muc_trong(muc):
                self.ket(y, ok=True, bo_qua=True,
                         mo_ta=(mo_ta if muc is None else f"{mo_ta}: mọi mức ở 0"))
                continue
            k = (json.dumps(rt._chuan_muc(muc), sort_keys=True),
                 os.path.normcase(str(Path(anh).parent)))
            nhom.setdefault(k, (muc, mo_ta, []))[2].append(y)
        if not nhom:
            return
        self._ghim_cpu()
        for muc, mo_ta, ys in nhom.values():
            for i in range(0, len(ys), LO_TOI_DA):
                self.chay_nhom(muc, mo_ta, ys[i:i + LO_TOI_DA])
                self.giao_cho()            # ảnh plugin đang chờ ra NGAY, không đợi hết lô sau

    def chay_nhom(self, muc: dict, mo_ta: str, ys: list) -> None:
        """Một mẻ engine cho các ảnh cùng mức, cùng thư mục render: liên kết cứng vào
        thư mục tạm CẠNH chúng (cùng ổ), retouch ra thư mục tạm, rồi os.replace đè
        đúng file Lightroom render — nguyên tử, ảnh hoặc là bản cũ hoặc bản mới."""
        rt = self.rt
        t0 = time.monotonic()
        cha = Path(ys[0]["anh"]).parent
        self._dem_tam += 1
        tam = cha / f".autotone_tram_{os.getpid()}_{self._dem_tam}"
        try:
            vao, ra = tam / "vao", tam / "ra"
            vao.mkdir(parents=True, exist_ok=True)
            ra.mkdir(parents=True, exist_ok=True)
            (tam / MOC_TAM).write_text("AutoTone — thu muc tam, xoa duoc\n", encoding="utf-8")
        except OSError as ex:
            for y in ys:
                self.ket(y, ok=False, loi=f"không tạo được thư mục tạm: {ex}")
            return
        ten_cua = {}
        for y in ys:
            p = Path(y["anh"])
            dich = vao / p.name
            try:
                try:
                    os.link(p, dich)
                except OSError:
                    shutil.copy2(p, dich)
                ten_cua[y["id"]] = p.name
            except OSError as ex:
                self.ket(y, ok=False, loi=f"không chép được ảnh: {ex}")
        ys = [y for y in ys if y["id"] in ten_cua]
        if not ys:
            shutil.rmtree(tam, ignore_errors=True)
            return
        may = self.lay_may()
        cuoi: list = []
        ma = 1
        try:
            for loai, gt in rt.chay(self.goc_tool(), vao, ra, muc, engine=may,
                                    lam_lai=True, chat_luong="auto"):
                if loai == "dong":
                    cuoi.append(str(gt))
                    del cuoi[:-12]
                elif loai == "ma":
                    ma = int(gt or 0)
        except Exception as ex:                              # noqa: BLE001
            cuoi.append(f"{type(ex).__name__}: {ex}")
        giay = (time.monotonic() - t0) / max(1, len(ys))
        loi_tool = next((x.strip() for x in reversed(cuoi) if "!" in x or "LOI" in x.upper()), "")
        for y in ys:
            ra_f = ra / ten_cua[y["id"]]
            if self.da_huy(y):
                self.tra_loi(y, ok=False, loi="plugin đã huỷ (quá giờ) — không đè ảnh", giay=giay)
                continue
            if ra_f.is_file() and ra_f.stat().st_size > 0:
                self.ket(y, ra_f, ok=True, mo_ta=mo_ta, giay=giay)
                continue
            self.ket(y, ok=False, giay=giay,
                     loi=(f"tool không ra ảnh (mã {ma})" + (f": {loi_tool[:120]}" if loi_tool else "")))
        shutil.rmtree(tam, ignore_errors=True)
        self.log(f"{len(ys)} ảnh · {mo_ta} · {giay:.2f} s/ảnh · mã {ma}"
                 + (f" · {Path(ys[0]['anh']).name}" if len(ys) == 1 else ""))

    # ------------------------------------------------------------ luồng nền (app)
    def bat_nen(self) -> None:
        if self._luong is not None and self._luong.is_alive():
            return
        self._dung.clear()
        self._luong = threading.Thread(target=self._vong, name="tram_retouch", daemon=True)
        self._luong.start()
        threading.Thread(target=self._vong_nhip, name="tram_nhip", daemon=True).start()
        self.log(f"bắt đầu (pid {os.getpid()})")

    def _vong(self) -> None:
        while not self._dung.is_set():
            try:
                self.mot_vong()
            except Exception:                                # noqa: BLE001
                self.log("LỖI vòng trạm: " + traceback.format_exc()[-300:])
            self._dung.wait(self.NGU)

    def dung(self) -> None:
        self._dung.set()
        self._tra_cpu()
        self.xoa_nhip()


# ====================================================================== lệnh mở trạm
def lenh_mo_tram(thu: Path) -> str:
    """Dòng lệnh plugin chạy để mở trạm chạy ngầm (ghi vào tram_lenh.txt)."""
    thu = str(thu)
    if getattr(sys, "frozen", False):
        chay = f'"{sys.executable}" --say-tram "{thu}"'
    else:
        py = Path(sys.executable)
        if sys.platform.startswith("win"):
            pw = py.with_name("pythonw.exe")
            py = pw if pw.is_file() else py
        kich = Path(__file__).resolve().parent / "autotone_gui.py"
        chay = f'"{py}" "{kich}" --say-tram "{thu}"'
    if sys.platform.startswith("win"):
        return f'start "" {chay}'
    return f"{chay} >/dev/null 2>&1 &"


def ghi_lenh(thu: Path) -> None:
    try:
        tam = Path(thu) / (LENH + ".part")
        tam.write_text(lenh_mo_tram(thu) + "\n", encoding="utf-8")
        os.replace(tam, Path(thu) / LENH)
    except OSError:
        pass


def ly_do_khong_mo() -> str:
    """"" = được mở trạm trong app lúc này; khác "" = vì sao không (bài kiểm…)."""
    if os.environ.get("AUTOTONE_TRAM") == "0":
        return "AUTOTONE_TRAM=0"
    if os.environ.get("AUTOTONE_TRAM") == "1":
        return ""
    if os.environ.get("AUTOTONE_TU_KIEM") or "--tu-kiem" in sys.argv[1:]:
        return "đang tự kiểm"
    try:
        import multiprocessing as _mp
        if _mp.current_process().name != "MainProcess":
            return "tiến trình con"
    except Exception:                                        # noqa: BLE001
        pass
    try:
        import tempfile
        import duong_dan as dd
        tam = os.path.normcase(os.path.abspath(tempfile.gettempdir()))
        du = os.path.normcase(os.path.abspath(str(dd.goc_du_lieu())))
        if du == tam or du.startswith(tam + os.sep):
            return "thư mục dữ liệu là thư mục tạm (bài kiểm)"
    except Exception:                                        # noqa: BLE001
        pass
    return ""


# ====================================================================== trạm chạy ngầm
def main_rieng(args: list) -> int:
    """`AutoTone --say-tram <thư mục trạm>`: trạm không giao diện (app đang tắt)."""
    thu = Path(args[0]) if args else thu_muc()
    thu.mkdir(parents=True, exist_ok=True)
    n = doc_nhip(thu, "rieng")
    if n and str(n.get("pid")) != str(os.getpid()):
        return 0                           # đã có trạm riêng khác đang chạy
    tram = Tram(thu, "rieng")
    tram.log(f"trạm chạy ngầm bắt đầu (pid {os.getpid()})")
    tram.ghi_nhip(ep=True)
    threading.Thread(target=tram._vong_nhip, name="tram_nhip", daemon=True).start()
    try:
        if tram.duoc_nhan():
            goc = tram.goc_tool()
            if goc and tram.rt.hop_le(goc):
                tram.giu.lay(tram.rt, goc, dung=False)    # nạp mô hình NGAY
        while True:
            lam = tram.mot_vong()
            ranh = time.time() - tram.t_viec
            if not lam and ranh > RANH_THOAT and not tram._cho_giao:
                tram.log("rảnh 10 phút — thoát")
                break
            if not lam and not tram.duoc_nhan() and ranh > 3 and not tram._cho_giao:
                tram.log("engine app đã sẵn sàng — nhường app, thoát")
                break
            time.sleep(Tram.NGU)
    finally:
        tram.dung()
        GIU.don(ep=True)
    return 0


def tat_het(tram: Tram | None = None) -> None:
    """App đóng: dừng trạm, đóng engine dù đang được giữ."""
    if tram is not None:
        try:
            tram.dung()
        except Exception:                                    # noqa: BLE001
            pass
    GIU.don(ep=True)
