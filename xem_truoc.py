#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xem_truoc.py — Máy tính ảnh xem trước retouch (tiến trình con dùng saytool).

TỪ TỐI 3/10 KHÔNG CÒN CỬA SỔ XEM TRƯỚC RIÊNG
    User: "Phần lưới ảnh của Retouch hãy làm giống Evoto. 1 ảnh mở to và lưới
    ảnh bên dưới. Sửa lại cả tính năng zoom ảnh." Như Evoto, bản xem trước
    hiện ngay trên ẢNH LỚN của mô-đun Retouch, theo đúng các thanh ở bảng điều
    khiển bên phải — không mở thêm một cửa sổ có ảnh lớn và thanh kéo thứ hai.
    File này chỉ còn phần máy: tiến trình con + giao thức. Khung vẽ, zoom ở
    khung_anh.py.

VÌ SAO CHẠY TRONG TIẾN TRÌNH CON
    App không có torch/onnxruntime (bản nhẹ tải chúng về sau, và ngay bản đầy
    đủ cũng không nạp chúng vào tiến trình giao diện). saytool thì có. Nên
    phần tính ảnh chạy ở tiến trình con dùng Python của ToolCloneEvoto.

    Trao đổi qua stdin/stdout bằng JSON một dòng — không cần cổng mạng, không
    đụng tường lửa, và tiến trình con chết thì app biết ngay.

VÌ SAO KHÔNG TÍNH THEO TỪNG NHỊP KÉO
    Đo thật trên ảnh 1600px có 3 mặt: mức 100 mất 2,76 giây. Nên ngừng kéo
    mới tính, và đang tính mà mức lại đổi thì chỉ tính thêm MỘT lần nữa khi
    lần đang chạy xong — không xếp hàng năm lượt cho năm lần thả tay.
"""
from __future__ import annotations

import base64
import io
import json
import os
import queue
import subprocess
import threading

#[[ Ma chay o TIEN TRINH CON. De thang day chu khong tach file rieng: file
#   rieng thi phai nho chep no sang may Mac, nho them vao LOAI_TRU, nho dong
#   vao goi... mot chuoi cho de quen. Chuoi nay di theo module luon.
#
#   Moi tin tra ve mang lai "fp" cua anh no noi toi: doi anh nhanh thi tin
#   cua anh cu van ve sau — phai biet ma bo.
#]]
MA_CON = r'''
import json, sys, base64
import numpy as np, cv2
from pathlib import Path

def ra(**kw):
    sys.stdout.write(json.dumps(kw) + "\n")
    sys.stdout.flush()

try:
    from saytool.mot_anh import Bo
    from saytool.ngu_canh import NguCanh
    from saytool.buoc import tat_ca
except Exception as e:
    ra(loai="hong", loi=f"{type(e).__name__}: {e}")
    sys.exit(1)

BO = None
NC = None
FP = None
CANH = 1400

def nen(img):
    #[[ PNG: khong mat chi tiet, ban truoc / sau so diem voi diem duoc. Anh
    #   1400px qua ong noi bo, khong qua mang. Nen muc 3: nhanh. ]]
    ok, buf = cv2.imencode(".png", img, [cv2.IMWRITE_PNG_COMPRESSION, 3])
    return base64.b64encode(buf).decode("ascii") if ok else ""

for dong in sys.stdin:
    dong = dong.strip()
    if not dong:
        continue
    try:
        y = json.loads(dong)
    except Exception:
        continue
    v = y.get("viec")
    try:
        if v == "khoi_dong":
            BO = Bo(y.get("may", "auto"))
            ra(loai="san_sang",
               keo=[{"ten": b.ten, "nhan": b.nhan} for b in tat_ca()])
        elif v == "mo_anh":
            NC = NguCanh(Path(y["fp"]), canh_toi_da=CANH)
            FP = y["fp"]
            _ = NC.anh
            H, W = NC.anh.shape[:2]
            #[[ Moi mat: [x, y, rong, cao] theo diem anh cua ban 1400px, mat
            #   TO truoc — nut "Vao mat" cua khung anh di lan luot. ]]
            mat = []
            for f in sorted(NC.mat or [], key=lambda m: -float(m.width)):
                bx1, by1, bx2, by2 = [float(t) for t in f.bbox[:4]]
                mat.append([bx1, by1, bx2 - bx1, by2 - by1])
            ra(loai="da_mo", fp=FP, so_mat=len(mat), mat=mat, rong=W, cao=H,
               goc=nen(NC.anh))
        elif v == "tinh":
            if NC is None or BO is None or y.get("fp") != FP:
                ra(loai="hong", loi="chua mo anh nay", ma=y.get("ma"),
                   fp=y.get("fp"))
                continue
            out = BO.chay(NC, y["muc"])
            ra(loai="ket_qua", ma=y.get("ma"), fp=FP, anh=nen(out))
        elif v == "thoat":
            break
    except Exception as e:
        ra(loai="hong", loi=f"{type(e).__name__}: {e}", ma=y.get("ma"),
           fp=y.get("fp"))
'''


def giai_anh(b64: str):
    """PNG base64 từ tiến trình con -> ảnh PIL RGB (None nếu hỏng)."""
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(base64.b64decode(b64)))
        im.load()
        return im.convert("RGB")
    except Exception:                                        # noqa: BLE001
        return None


class MayXem:
    """Tiến trình con tính ảnh xem trước. Không vẽ gì: ai dùng thì gửi việc
    (gui) và bơm tin về (lay) ở luồng chính.

    Tin về (dict): san_sang{keo} · da_mo{fp, so_mat, mat, rong, cao, goc} ·
    ket_qua{ma, fp, anh} · hong{loi, ma, fp} · chet{}.
    """

    def __init__(self, rt, goc_tool: str):
        self.rt = rt
        self.goc_tool = str(goc_tool)
        self.q: queue.Queue = queue.Queue()
        self.proc = None

    def bat_dau(self, may: str = "auto") -> str:
        """'' nếu khởi động được, không thì câu lỗi để nói ra."""
        #[[ Lay DUNG trinh thong dich cua ToolCloneEvoto (python_cho) — noi co
        #   torch va onnxruntime — roi chay -c MA_CON voi cwd = thu muc tool. ]]
        try:
            py = self.rt.python_cho(self.goc_tool)
            self.proc = subprocess.Popen(
                [str(py), "-c", MA_CON], cwd=self.goc_tool,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                errors="replace", bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                env=dict(os.environ, **self.rt.MOI_TRUONG_UTF8))
        except Exception as ex:                              # noqa: BLE001
            self.proc = None
            return f"Không chạy được Python của tool: {type(ex).__name__}: {ex}"
        threading.Thread(target=self._doc, daemon=True).start()
        self.gui(viec="khoi_dong", may=may or "auto")
        return ""

    def _doc(self):
        p = self.proc
        try:
            for dong in p.stdout:
                dong = dong.strip()
                if dong.startswith("{"):
                    try:
                        self.q.put(json.loads(dong))
                    except Exception:                        # noqa: BLE001
                        pass
        except Exception:                                    # noqa: BLE001
            pass
        self.q.put({"loai": "chet"})

    def gui(self, **kw) -> bool:
        p = self.proc
        if not p or p.poll() is not None:
            return False
        try:
            p.stdin.write(json.dumps(kw) + "\n")
            p.stdin.flush()
            return True
        except OSError:
            return False

    def lay(self) -> list:
        ra = []
        try:
            while True:
                ra.append(self.q.get_nowait())
        except queue.Empty:
            pass
        return ra

    def song(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def dong(self) -> None:
        self.gui(viec="thoat")
        p = self.proc
        if p and p.poll() is None:
            try:
                p.terminate()
            except OSError:
                pass
        self.proc = None
