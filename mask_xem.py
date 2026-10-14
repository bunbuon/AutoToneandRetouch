# -*- coding: utf-8 -*-
"""mask_xem.py — HIỆN MASK DA tool đang dùng ngay trên preview của app (14/10).

User 14/10: "hãy show cái lớp mask của da đang dùng để tool xử lý để tôi xem có mask đúng
không? show trên preview của app luôn cho từng ảnh". Nút "Mask da" trên đầu lưới Cân sáng:
lưới và ảnh lớn phủ màu đúng những điểm ảnh tool dùng — CÙNG phép tách da của lượt hoàn
thiện / chuỗi một lượt (mat_na_da.mat_na trên ảnh cạnh 1600, khung mặt của lần phân tích):

    xanh lá      da tool ĐO (sau khi bỏ điểm bóng loáng / quá tối)
    vàng         nằm trong vùng da nhưng BỊ BỎ (bóng loáng ≥ 250, hoặc tối hẳn so với da)
    đỏ           vùng CHÁY (kênh lớn nhất ≥ 250) — chỗ Highlights / nén cháy nhắm tới
    xanh dương   vùng TRẮNG trung tính tool dùng để xét lại WB (không lấy da)
    viền xanh lơ khung mặt; nhãn kiểu mặt nạ (phân vùng / dự phòng) ở góc khung

Mask tính trên ĐÚNG file ảnh đang hiện (preview Lightroom nếu có, không thì JPEG nhúng),
ở luồng nền, nhớ theo file (đĩa: <dữ liệu>/mask_da/) — mở lại buổi không tính lại.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from collections import OrderedDict
from pathlib import Path

import numpy as np

CANH = 1600
PHIEN = 2                        # đổi cách tính -> đổi khoá kho (2: vùng trắng bỏ mọi mặt + điểm cháy)
#: mã điểm ảnh -> (màu, độ phủ)
MAU = {1: ((60, 220, 90), 0.50), 2: ((255, 196, 40), 0.60), 3: ((255, 48, 48), 0.55),
       4: ((70, 150, 255), 0.35)}
VIEN = (60, 230, 255)
CHU_GIAI = ("xanh lá = da tool đo · vàng = da bị bỏ (bóng / tối) · đỏ = vùng cháy ≥ 250 · "
            "xanh dương = vùng trắng xét WB")


def _kho() -> Path:
    import duong_dan as dd
    return dd.goc_du_lieu() / "mask_da"


def _khoa(src, r: dict | None) -> str | None:
    try:
        st = os.stat(src)
    except OSError:
        return None
    hop = list((r or {}).get("meter_boxes") or [])
    van = (f"{os.path.normcase(os.path.abspath(str(src)))}|{st.st_mtime_ns}|{st.st_size}|{PHIEN}|"
           f"{hop}|{(r or {}).get('preview_wh')}|{(r or {}).get('cat_lr')}")
    return hashlib.sha1(van.encode("utf-8", "surrogatepass")).hexdigest()[:24]


def doc_anh(src) -> np.ndarray:
    """File ảnh để nhìn (preview Lightroom / ảnh duyệt / JPEG nhúng / RAW) -> sRGB uint8."""
    import curve_da
    p = Path(str(src))
    try:
        import nguon_xem
        if nguon_xem.la_raw(p):
            p = nguon_xem.anh_nhung(p) or p
    except Exception:                                        # noqa: BLE001
        pass
    return curve_da.doc_srgb(p)


def tinh(src, r: dict | None) -> dict | None:
    """Mã điểm ảnh (H, W) uint8 + khung mặt của MỘT ảnh — cùng phép tách da với
    curve_da.do_anh (mat_na_da.mat_na trên ảnh cạnh ≤ CANH)."""
    import cv2
    import autotone as at
    import curve_da
    import mat_na_da as mn
    try:
        img = doc_anh(src)
    except (OSError, ValueError):
        return None
    if max(img.shape[:2]) > CANH:
        k = CANH / max(img.shape[:2])
        img = cv2.resize(img, (max(1, round(img.shape[1] * k)), max(1, round(img.shape[0] * k))),
                         interpolation=cv2.INTER_AREA)
    H, W = img.shape[:2]
    m = mn.mat_na(img, r)
    ma = np.zeros((H, W), np.uint8)
    px = img.reshape(-1, 3).astype(np.float32) / 255.0
    lab = curve_da._lab_px(at.srgb_to_linear(px))              # noqa: SLF001
    lo, hi, cmax = curve_da.BO_TRUNG_TINH
    trong_mat = np.zeros((H, W), bool)
    for x, y, w, h in mn.moi_mat(r, W, H, m["mat"]):
        trong_mat[int(max(0, y - 0.3 * h)):int(y + 1.3 * h), int(max(0, x - 0.3 * w)):int(x + 1.3 * w)] = True
    trung = ((lab[:, 0] >= lo) & (lab[:, 0] <= hi) & (np.hypot(lab[:, 1], lab[:, 2]) < cmax)
             & ~at.skin_mask(px) & ~trong_mat.reshape(-1)
             & (px.max(axis=1) * 255 < curve_da.NGUONG_CHAY)).reshape(H, W)
    ma[trung] = 4
    ma[img.max(axis=2) >= curve_da.NGUONG_CHAY] = 3
    tho = m.get("da_tho")
    if tho is not None:
        ma[tho & ~m["da"]] = 2
    ma[m["da"]] = 1
    return {"wh": (W, H), "ma": ma, "mat": [list(b) for b in m["mat"]], "kieu": m.get("kieu"),
            "n": int(m.get("n") or 0), "ly_do": m.get("ly_do") or "", "do_lai": m.get("do_lai")}


def luu(k: str, kq: dict) -> None:
    from PIL import Image
    try:
        d = _kho()
        d.mkdir(parents=True, exist_ok=True)
        Image.fromarray(kq["ma"]).save(d / f"{k}.png")
        (d / f"{k}.json").write_text(json.dumps({x: v for x, v in kq.items() if x != "ma"},
                                                ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def nap(k: str) -> dict | None:
    from PIL import Image
    d = _kho()
    try:
        meta = json.loads((d / f"{k}.json").read_text(encoding="utf-8"))
        with Image.open(d / f"{k}.png") as im:
            meta["ma"] = np.asarray(im.convert("L"))
        return meta
    except (OSError, ValueError):
        return None


def phu(im, kq: dict | None, vien: bool = True):
    """Ảnh PIL + mask -> ảnh PIL phủ màu (mask co giãn theo cỡ ảnh, lân cận gần nhất)."""
    if kq is None or im is None:
        return im
    from PIL import Image, ImageDraw
    rgb = im.convert("RGB")
    W, H = rgb.size
    ma = np.asarray(Image.fromarray(kq["ma"]).resize((W, H), Image.NEAREST))
    a = np.asarray(rgb, dtype=np.float32)
    for code, (mau, alpha) in MAU.items():
        sel = ma == code
        if sel.any():
            a[sel] = a[sel] * (1.0 - alpha) + np.asarray(mau, np.float32) * alpha
    out = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    if vien and kq.get("mat"):
        sx, sy = W / kq["wh"][0], H / kq["wh"][1]
        d = ImageDraw.Draw(out)
        net = max(1, round(min(W, H) / 400))
        for x, y, w, h in kq["mat"]:
            d.rectangle([x * sx, y * sy, (x + w) * sx, (y + h) * sy], outline=VIEN, width=net)
    return out


def tom_tat(kq: dict | None) -> str:
    """"mặt nạ phân vùng · 3 mặt · 12.840 điểm da · cháy 37%"."""
    if kq is None:
        return "đang tính mask da…"
    kieu = {"parse": "mặt nạ phân vùng", "du_phong": "mặt nạ DỰ PHÒNG (elip — mặt nhỏ / không có mô hình)",
            "tron": "phân vùng + dự phòng"}.get(kq.get("kieu") or "", "không thấy da")
    ma = kq["ma"]
    cau = f"{kieu} · {len(kq.get('mat') or [])} mặt · {int((ma == 1).sum()):,} điểm da".replace(",", ".")
    chay = float((ma == 3).mean() * 100)
    if chay >= 0.1:
        cau += f" · cháy {chay:.0f}%"
    if kq.get("ly_do") and not kq.get("n"):
        cau += f" · {kq['ly_do']}"
    return cau


class BoMask:
    """Tính mask ở MỘT luồng nền (mô hình phân vùng dùng chung, có khoá), việc mới nhất
    trước; nhớ trong RAM (≤ 300 ảnh) + đĩa. khi_xong(src) gọi ở luồng nền khi xong một ảnh."""

    def __init__(self, khi_xong=None):
        self._khi_xong = khi_xong
        self._ram: OrderedDict = OrderedDict()
        self._ngan: list = []
        self._dang: set = set()
        self._co = threading.Condition()
        self._luong = None

    def lay(self, src, r: dict | None) -> dict | None:
        """Mask đã có (RAM / đĩa) hoặc None — chưa có thì xếp hàng tính."""
        if not src:
            return None
        k = _khoa(src, r)
        if k is None:
            return None
        with self._co:
            kq = self._ram.get(k)
            if kq is not None:
                self._ram.move_to_end(k)
                return kq
        kq = nap(k)
        if kq is not None:
            with self._co:
                self._ram[k] = kq
                self._gon()
            return kq
        with self._co:
            if k not in self._dang:
                self._dang.add(k)
                self._ngan.append((k, str(src), dict(r) if r else None))
                self._co.notify_all()
            if self._luong is None:
                self._luong = threading.Thread(target=self._chay, daemon=True)
                self._luong.start()
        return None

    def _gon(self):
        while len(self._ram) > 300:
            self._ram.popitem(last=False)

    def bo_hang(self) -> None:
        """Bỏ việc chưa làm (đổi buổi / tắt nút)."""
        with self._co:
            for k, _s, _r in self._ngan:
                self._dang.discard(k)
            self._ngan.clear()

    def _chay(self):
        while True:
            with self._co:
                while not self._ngan:
                    self._co.wait(1.0)
                k, src, r = self._ngan.pop()
            try:
                kq = tinh(src, r)
            except Exception:                                # noqa: BLE001
                kq = None
            with self._co:
                self._dang.discard(k)
                if kq is not None:
                    self._ram[k] = kq
                    self._gon()
            if kq is not None:
                luu(k, kq)
                if self._khi_xong:
                    try:
                        self._khi_xong(src)
                    except Exception:                        # noqa: BLE001
                        pass
