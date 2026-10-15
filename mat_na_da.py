"""Mặt nạ DA MẶT trên ảnh Lightroom dựng — 13/10.

User 13/10: "cần tách ra được mask của da mặt để cân chỉnh… trên từng pixel đo được
của da". Trước đó tool chỉ có skin_mask (ngưỡng màu HSV trong lõi 55% ô mặt) — gom
cả môi, lông mày nhạt, tóc nâu, kính màu da vào "da".

Cách tách:
  · Chính: mô hình phân vùng mặt resnet34 (yakhyo/face-parsing, nhãn CelebAMask-HQ:
    1 = da, 10 = mũi) — mô hình CÔNG KHAI mà bộ Retouch (ToolCloneEvoto) đã mang
    theo trong mo_hinh/. Nạp bằng onnxruntime nếu có, không thì cv2.dnn (bản gói
    không có onnxruntime vẫn chạy được; chậm hơn ~3 lần).
  · Dự phòng (không có mô hình, ví dụ bản Mac --khong-retouch): elip theo khung YuNet
    trừ hai mắt và miệng (5 điểm mốc của YuNet) ∩ at.skin_mask.
  Cả hai: co mép (bỏ viền tóc / nền), bỏ điểm bóng loáng (kênh lớn nhất ≥ 250), bỏ điểm
  quá tối so với da (SKIN_DARK_REL — cùng luật measure()).

#[[ Dò mặt LẠI trên ảnh dựng thay vì lấy khung từ ảnh nhúng (13/10): user crop / xoay
#   trong Lightroom thì khung đo trên ảnh nhúng không còn đúng chỗ. Cùng tỉ lệ khung →
#   chỉ lấy mặt trùng khung tool đã đo (meter_boxes, IoU ≥ 0.3) — đúng CHỦ THỂ tool đã
#   chọn, không lẫn khách phía sau. Khác tỉ lệ (đã crop) → mặt lớn nhất, điểm ≥ 0.7.
#
#   Bộ dò YuNet và phiên mô hình ở đây là của RIÊNG module này: at.face_detector() dùng
#   chung một đối tượng, setInputSize/detect từ hai luồng là đua (bài học khung_anh). ]]
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

import numpy as np

import autotone as at

#: nhãn tính là da: 1 da, 10 mũi
LOP_DA = (1, 10)
TEN_MODEL = "resnet34_faceparse.onnx"
CO_VAO = 512
#: nới khung YuNet trước khi phân vùng — như saytool (--pad 0.45, phía trên ×1.2)
NOI = 0.45
DIEM_MAT_LON = 0.7
IOU_KHOP = 0.3
MAT_NHO_PARSE = 48
MAT_NHO_DU_PHONG = 40
DIEM_DA_TOI_THIEU = 400
BONG = 250 / 255.0
#: crop Lightroom coi là "không crop" khi lệch khung đầy đủ dưới mức này (toạ độ 0..1)
SAI_CAT = 0.002

_TB = np.float32([0.485, 0.456, 0.406]) * 255
_DL = 1.0 / (np.float32([0.229, 0.224, 0.225]) * 255)

_KHOA = threading.Lock()
_PHIEN = None            # None = chưa nạp; False = không nạp được; (kieu, obj)
_LY_DO = ""
_DUONG = None
_DO_MAT = None


def tim_model() -> Path | None:
    """Mô hình phân vùng mặt: biến FACE_PARSE_ONNX → mo_hinh/ của bộ Retouch trong gói
    → kho tải về của saytool (~/.cache/skin_spike) → models/ của app."""
    ung = []
    if os.environ.get("FACE_PARSE_ONNX"):
        ung.append(Path(os.environ["FACE_PARSE_ONNX"]))
    try:
        import duong_dan as dd
        ung.append(dd.goc_tai_nguyen() / "mo_hinh" / TEN_MODEL)
        ung.append(dd.tai_nguyen("models", TEN_MODEL))
    except Exception:                                        # noqa: BLE001
        pass
    kho = os.environ.get("SKIN_SPIKE_CACHE")
    ung.append(Path(kho) / TEN_MODEL if kho else Path.home() / ".cache" / "skin_spike" / TEN_MODEL)
    for p in ung:
        try:
            if p.is_file() and p.stat().st_size > 1_000_000:
                return p
        except OSError:
            continue
    return None


def so_luong_ort() -> int:
    """Số luồng ONNX Runtime của phiên phân vùng. 14/10: tiến trình đo song song
    (curve_da.BoDo) đặt AUTOTONE_ORT_THREADS — N tiến trình × 4 luồng mỗi tiến trình
    giành CPU với nhau và với Lightroom đang dựng preview."""
    try:
        n = int(os.environ.get("AUTOTONE_ORT_THREADS") or 0)
    except ValueError:
        n = 0
    return n if n > 0 else max(1, min(4, (os.cpu_count() or 2) // 2))


def _nap():
    """Nạp mô hình một lần. Trả (kieu, obj) hoặc None (lý do ở _LY_DO)."""
    global _PHIEN, _LY_DO, _DUONG
    if _PHIEN is not None:
        return _PHIEN or None
    p = tim_model()
    if p is None:
        _PHIEN, _LY_DO = False, "không có mô hình phân vùng mặt"
        return None
    _DUONG = p
    nhan = p.with_name(p.stem + "_nhan.onnx")       # bản saytool tạo sẵn: chỉ trả nhãn
    try:
        import onnxruntime as ort
        so = ort.SessionOptions()
        so.intra_op_num_threads = so_luong_ort()
        dung = nhan if nhan.is_file() else p
        _PHIEN = ("ort", ort.InferenceSession(str(dung), sess_options=so,
                                              providers=["CPUExecutionProvider"]))
        return _PHIEN
    except Exception as e:                                   # noqa: BLE001
        _LY_DO = f"onnxruntime: {e}"
    try:
        import cv2
        _PHIEN = ("dnn", cv2.dnn.readNetFromONNX(str(p)))
        return _PHIEN
    except Exception as e:                                   # noqa: BLE001
        _PHIEN, _LY_DO = False, f"{_LY_DO}; cv2.dnn: {e}".strip("; ")
    return None


def trang_thai() -> dict:
    """{"co": có mô hình chạy được, "kieu": ort/dnn, "duong": file, "ly_do": vì sao không}."""
    with _KHOA:
        ph = _nap()
    return {"co": bool(ph), "kieu": ph[0] if ph else None,
            "duong": str(_DUONG) if _DUONG else "", "ly_do": "" if ph else _LY_DO}


def nhan_vung(crop_rgb) -> np.ndarray | None:
    """Nhãn phân vùng (h, w) uint8 của một ô mặt RGB uint8. None = không có mô hình."""
    import cv2
    with _KHOA:
        ph = _nap()
        if not ph:
            return None
        kieu, m = ph
        h, w = crop_rgb.shape[:2]
        im = cv2.resize(crop_rgb, (CO_VAO, CO_VAO), interpolation=cv2.INTER_AREA)
        x = np.ascontiguousarray(((im.astype(np.float32) - _TB) * _DL).transpose(2, 0, 1)[None])
        if kieu == "ort":
            y = m.run(None, {m.get_inputs()[0].name: x})[0][0]
        else:
            m.setInput(x)
            y = m.forward()[0]
    if y.ndim == 3:
        y = y.argmax(0)
    return cv2.resize(y.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST)


# ------------------------------------------------------------------- dò mặt

def _bo_do():
    global _DO_MAT
    if _DO_MAT is None:
        try:
            import cv2
            _DO_MAT = (cv2.FaceDetectorYN.create(str(at.FACE_MODEL), "", (320, 320), 0.5, 0.3, 5000)
                       if at.FACE_MODEL.is_file() else False)
        except Exception:                                    # noqa: BLE001
            _DO_MAT = False
    return _DO_MAT or None


def tim_mat(img_rgb) -> list:
    """Mặt trên ảnh RGB uint8: [(x, y, w, h, điểm, mốc 5×(x, y) hoặc None)]."""
    with _KHOA:
        det = _bo_do()
        if det is None:
            return []
        h, w = img_rgb.shape[:2]
        try:
            det.setInputSize((w, h))
            _, faces = det.detect(np.ascontiguousarray(img_rgb[:, :, ::-1]))
        except Exception:                                    # noqa: BLE001
            return []
    out = []
    for f in (faces if faces is not None else []):
        x, y, fw, fh = (float(v) for v in f[:4])
        moc = [(float(f[4 + 2 * i]), float(f[5 + 2 * i])) for i in range(5)] if len(f) >= 15 else None
        out.append((x, y, fw, fh, float(f[-1]), moc))
    return out


def _iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = a[0], a[1], a[0] + a[2], a[1] + a[3]
    bx1, by1, bx2, by2 = b[0], b[1], b[0] + b[2], b[1] + b[3]
    iw, ih = max(0.0, min(ax2, bx2) - max(ax1, bx1)), max(0.0, min(ay2, by2) - max(ay1, by1))
    giao = iw * ih
    hop = a[2] * a[3] + b[2] * b[3] - giao
    return giao / hop if hop > 0 else 0.0


def chon_mat(mats: list, r: dict | None, W: int, H: int) -> tuple[list, bool]:
    """(mặt dùng để đo, ảnh đã crop?). Khung tool đã đo (meter_boxes, toạ độ ảnh nhúng
    preview_wh) quy sang ảnh dựng; cùng tỉ lệ khung thì chỉ lấy mặt trùng khung đó."""
    r = r or {}
    boxes = r.get("meter_boxes") or []
    pw, ph = r.get("preview_wh") or (0, 0)
    if boxes and pw and ph and abs((W / max(H, 1)) / (pw / ph) - 1.0) <= 0.02:
        sx, sy = W / pw, H / ph
        out = []
        for b in boxes:
            bq = (float(b[0]) * sx, float(b[1]) * sy, float(b[2]) * sx, float(b[3]) * sy)
            tot = max(mats, key=lambda m: _iou(m, bq), default=None)
            if tot is not None and _iou(tot, bq) >= IOU_KHOP:
                if tot not in out:
                    out.append(tot)
            else:
                out.append((*bq, 0.0, None))          # không dò lại được: dùng khung cũ
        return out, False
    lon = [m for m in mats if m[4] >= DIEM_MAT_LON]
    if not lon:
        return [], bool(boxes)
    return [max(lon, key=lambda m: m[2] * m[3])], bool(boxes)


def khong_cat(r: dict | None, W: int, H: int) -> bool:
    """Ảnh dựng KHÔNG crop / xoay so với ảnh nhúng: Lightroom báo crop đồng nhất
    (r["cat_lr"] = (trái, trên, phải, dưới, góc) — bản xuất thông số từ 14/10) VÀ cùng
    tỉ lệ khung với ảnh nhúng (preview_wh). Thiếu cat_lr (plugin cũ) -> False: không
    biết có crop cùng tỉ lệ hay không (khoá tỉ lệ là mặc định của công cụ Crop)."""
    r = r or {}
    c = r.get("cat_lr")
    pw, ph = r.get("preview_wh") or (0, 0)
    if not c or not pw or not ph or not W or not H:
        return False
    try:
        L, T, R, B, goc = (float(v) for v in c)
    except (TypeError, ValueError):
        return False
    e = SAI_CAT
    if abs(L) > e or abs(T) > e or R < 1.0 - e or B < 1.0 - e or abs(goc) > 0.01:
        return False
    return abs((W / max(H, 1)) / (pw / ph) - 1.0) <= 0.02


def moi_mat(r: dict | None, W: int, H: int, them: list | None = None) -> list:
    """Khung (x, y, w, h) của MỌI mặt lần phân tích dò được (r["all_boxes"], không chỉ
    mặt chủ thể) quy sang ảnh W×H — cùng tỉ lệ khung với ảnh nhúng mới quy được; cộng
    `them` (khung trên chính ảnh này).

    #[[ 14/10 (soi lớp mask da trên ảnh nhóm SAY08076 / DSC09395): vùng TRẮNG xét WB chỉ
    #   bỏ mặt CHỦ THỂ -> mặt sáng của người khác (da cháy gần như mất màu) bị tính là
    #   "trắng trung tính", kéo lệch phép xét WB. ]]"""
    out = [tuple(float(v) for v in b[:4]) for b in (them or [])]
    r = r or {}
    pw, ph = r.get("preview_wh") or (0, 0)
    if pw and ph and W and H and abs((W / max(H, 1)) / (pw / ph) - 1.0) <= 0.02:
        sx, sy = W / pw, H / ph
        for b in r.get("all_boxes") or r.get("meter_boxes") or []:
            out.append((float(b[0]) * sx, float(b[1]) * sy, float(b[2]) * sx, float(b[3]) * sy))
    return out


def khung_san(r: dict, W: int, H: int) -> list:
    """Khung mặt tool đã đo (meter_boxes, toạ độ ảnh nhúng) quy THẲNG sang ảnh dựng —
    không dò lại (chỉ dùng khi khong_cat). Không có mốc mắt / miệng."""
    pw, ph = r["preview_wh"]
    sx, sy = W / pw, H / ph
    return [(float(b[0]) * sx, float(b[1]) * sy, float(b[2]) * sx, float(b[3]) * sy, 0.0, None)
            for b in r.get("meter_boxes") or []]


# ------------------------------------------------------------------- mặt nạ

def _vung_cat(m, W, H):
    x, y, fw, fh = m[:4]
    px, py = fw * NOI, fh * NOI
    return (int(max(0, x - px)), int(max(0, y - py * 1.2)),
            int(min(W, x + fw + px)), int(min(H, y + fh + py)))


def _du_phong(img, m) -> tuple:
    """Mặt nạ dự phòng (H, W) bool cho một mặt: elip − mắt − miệng ∩ skin_mask
    -> (mặt nạ, đã bù ám: bool). 15/10: ảnh ám xanh nặng — cổng tuyệt đối loại sạch da thì
    lọc lại trên điểm đã bù ám (at.bu_am_mau)."""
    import cv2
    H, W = img.shape[:2]
    x, y, fw, fh = m[:4]
    mk = np.zeros((H, W), np.uint8)
    cx, cy = x + fw / 2, y + fh * 0.52
    cv2.ellipse(mk, (int(cx), int(cy)), (int(fw * 0.42), int(fh * 0.55)), 0, 0, 360, 1, -1)
    moc = m[5]
    if moc:
        r_mat = max(2, int(fw * 0.12))
        for ex, ey in moc[:2]:
            cv2.circle(mk, (int(ex), int(ey)), r_mat, 0, -1)
        (mx1, my1), (mx2, my2) = moc[3], moc[4]
        rong = max(4.0, abs(mx2 - mx1))
        cv2.ellipse(mk, (int((mx1 + mx2) / 2), int((my1 + my2) / 2)),
                    (int(rong * 0.6), max(2, int(fh * 0.12))), 0, 0, 360, 0, -1)
    else:                                   # không có mốc: bỏ dải mắt và dải miệng ước lượng
        mk[int(y + fh * 0.30):int(y + fh * 0.48), int(x):int(x + fw)] = 0
        mk[int(y + fh * 0.72):int(y + fh * 0.86), int(x + fw * 0.30):int(x + fw * 0.70)] = 0
    da = mk.astype(bool)
    bu_dung = False
    if da.any():
        px = img[da].astype(np.float32) / 255.0
        sk = at.skin_mask(px)
        if int(sk.sum()) < DIEM_DA_TOI_THIEU:
            bu = at.bu_am_mau(px)
            if bu is not None:
                sk_bu = at.skin_mask(px, bu)
                if int(sk_bu.sum()) > int(sk.sum()):
                    sk, bu_dung = sk_bu, True
        da[da] = sk
    return da, bu_dung


def mat_na(img_rgb, r: dict | None = None, dung_parse: bool = True,
           tim_lai: str = "tu_dong") -> dict:
    """Mặt nạ da của CHỦ THỂ trên một ảnh dựng (RGB uint8).

    tim_lai: "tu_dong" (14/10) — ảnh KHÔNG crop (khong_cat) và có mô hình phân vùng thì
    dùng thẳng khung tool đã đo, bỏ YuNet (~65 ms / ảnh 2048 px); "luon" — luôn dò lại.

    -> {"da": (H, W) bool, "da_tho": mặt nạ TRƯỚC khi bỏ điểm bóng / tối (để biết da sáng
        tới đâu — da cháy hẳn thì "da" rỗng), "kieu": "parse" | "du_phong" | "tron" | None,
        "mat": [khung (x, y, w, h)], "do_lai": đã dò mặt lại trên ảnh dựng,
        "crop": ảnh đã crop so với ảnh nhúng, "n": số điểm da, "ly_do": khi không có da}."""
    import cv2
    H, W = img_rgb.shape[:2]
    co_parse = dung_parse and bool(trang_thai()["co"])
    #[[ 14/10: khung đo trên ảnh nhúng trùng chỗ trên ảnh dựng khi Lightroom không crop
    #   (cat_lr đồng nhất + cùng tỉ lệ) — chon_mat cũng đã dùng khung cũ cho mặt YuNet
    #   không dò ra. Ô phân vùng nới 45% mỗi phía nên lệch vài % (hiệu chỉnh ống kính)
    #   vẫn trọn mặt. Không có mô hình phân vùng thì vẫn dò: mặt nạ dự phòng cần mốc
    #   mắt / miệng của YuNet. ]]
    do_lai = not (tim_lai == "tu_dong" and co_parse and (r or {}).get("meter_boxes")
                  and khong_cat(r, W, H))
    if do_lai:
        mats, crop = chon_mat(tim_mat(img_rgb), r, W, H)
    else:
        mats, crop = khung_san(r, W, H), False
    da = np.zeros((H, W), bool)
    kieu_dung = None
    bu_am = False
    ly_do = "" if mats else "không thấy mặt"
    for m in mats:
        fw = m[2]
        mk = None
        if co_parse and fw >= MAT_NHO_PARSE:
            x0, y0, x1, y1 = _vung_cat(m, W, H)
            if x1 - x0 >= 32 and y1 - y0 >= 32:
                L = nhan_vung(np.ascontiguousarray(img_rgb[y0:y1, x0:x1]))
                if L is not None:
                    mk = np.zeros((H, W), bool)
                    mk[y0:y1, x0:x1] = np.isin(L, LOP_DA)
                    kieu = "parse"
        if mk is None:
            if fw < MAT_NHO_DU_PHONG:
                continue
            (mk, bu_m), kieu = _du_phong(img_rgb, m), "du_phong"
            bu_am = bu_am or bu_m
        #  co mép: bỏ viền tóc / tai / nền dính mép mặt nạ
        k = max(2, int(round(0.02 * fw)))
        mk = cv2.erode(mk.astype(np.uint8),
                       cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1))).astype(bool)
        if mk.any():
            da |= mk
            kieu_dung = kieu if kieu_dung in (None, kieu) else "tron"
    da_tho = da.copy()                   # trước khi bỏ bóng / tối: biết da sáng tới đâu
    if da.any():
        px = img_rgb[da].astype(np.float32) / 255.0
        giu = px.max(axis=1) < BONG                      # bỏ điểm bóng loáng
        y = at.srgb_to_linear(px) @ at._SRGB_XYZ[1]         # noqa: SLF001
        if giu.any() and at.SKIN_DARK_REL > 0:
            giu &= y >= at.SKIN_DARK_REL * np.quantile(y[giu], 0.90)
        da[da] = giu
    n = int(da.sum())
    if mats and n < DIEM_DA_TOI_THIEU:
        ly_do = f"quá ít điểm da ({n})"
    return {"da": da if n >= DIEM_DA_TOI_THIEU else np.zeros((H, W), bool),
            "da_tho": da_tho,
            "kieu": kieu_dung if n >= DIEM_DA_TOI_THIEU else None,
            "mat": [tuple(float(v) for v in m[:4]) for m in mats], "do_lai": do_lai,
            "crop": crop, "n": n if n >= DIEM_DA_TOI_THIEU else 0, "ly_do": ly_do,
            "bu_am": bool(bu_am and n >= DIEM_DA_TOI_THIEU)}
