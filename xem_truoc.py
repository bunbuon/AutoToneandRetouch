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
import sys
import threading

#[[ Ma chay o TIEN TRINH CON. De thang day chu khong tach file rieng: file
#   rieng thi phai nho chep no sang may Mac, nho them vao LOAI_TRU, nho dong
#   vao goi... mot chuoi cho de quen. Chuoi nay di theo module luon.
#
#   Moi tin tra ve mang lai "fp" cua anh no noi toi: doi anh nhanh thi tin
#   cua anh cu van ve sau — phai biet ma bo.
#]]
#[[ VONG LAP TIEN TRINH CON XEM TRUOC — tach thanh HAM de dung duoc o CA HAI:
#
#   1. Chay tu MA NGUON: MayXem chay `python -c MA_CON`, MA_CON goi vong_xem().
#   2. Chay TU GOI (dong goi): frozen AutoTone.exe KHONG chay `python -c` duoc
#      (no khong phai trinh thong dich). Nen autotone_gui them co `--say-xem`:
#      no import xem_truoc.vong_xem() va chay THANG trong goi. MayXem khi frozen
#      goi [sys.executable, "--say-xem"] thay vi [python_cho, "-c", MA_CON].
#      (Cung bay voi _hoi_keo/kiem_tra/lenh_saytool: frozen exe != python.)
#
#   Nho tach ham, logic xem truoc chi viet MOT lan, hai duong goi cung no. ]]
def vong_xem():
    """Vòng lặp tiến trình con tính ảnh xem trước: đọc JSON ở stdin, trả JSON
    (ảnh nén base64) ở stdout. Dùng chung cho bản mã nguồn (qua MA_CON) và bản
    đóng gói (qua cờ --say-xem)."""
    import json as _json
    import sys as _sys
    import base64 as _b64
    import cv2 as _cv2
    from pathlib import Path as _Path

    def ra(**kw):
        _sys.stdout.write(_json.dumps(kw) + "\n")
        _sys.stdout.flush()

    try:
        from saytool.mot_anh import Bo
        from saytool.ngu_canh import NguCanh
        from saytool.buoc import tat_ca
    except Exception as e:                                   # noqa: BLE001
        ra(loai="hong", loi=f"{type(e).__name__}: {e}")
        return 1

    BO = None
    NC = None
    FP = None
    CANH = 1400

    def nen(img):
        #[[ PNG: khong mat chi tiet, ban truoc / sau so diem voi diem duoc. Anh
        #   1400px qua ong noi bo, khong qua mang. Nen muc 3: nhanh. ]]
        ok, buf = _cv2.imencode(".png", img, [_cv2.IMWRITE_PNG_COMPRESSION, 3])
        return _b64.b64encode(buf).decode("ascii") if ok else ""

    for dong in _sys.stdin:
        dong = dong.strip()
        if not dong:
            continue
        try:
            y = _json.loads(dong)
        except Exception:                                    # noqa: BLE001
            continue
        v = y.get("viec")
        try:
            if v == "khoi_dong":
                BO = Bo(y.get("may", "auto"))
                #[[ may = thiet bi THAT dang tinh ("cuda" / "cpu" / "mps") — giao
                #   dien dung de noi ro khi dang chay CPU (moi lan keo ~5-13 s
                #   tren ban cai torch CPU) va goi y tai ban tang toc GPU. ]]
                ra(loai="san_sang", may=str(getattr(BO, "dev", "")),
                   keo=[{"ten": b.ten, "nhan": b.nhan} for b in tat_ca()])
            elif v == "mo_anh":
                NC = NguCanh(_Path(y["fp"]), canh_toi_da=CANH)
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
        except Exception as e:                               # noqa: BLE001
            ra(loai="hong", loi=f"{type(e).__name__}: {e}", ma=y.get("ma"),
               fp=y.get("fp"))
    return 0


#[[ MA_CON: ban mã nguồn chay `python -c MA_CON`. No chi import xem_truoc roi
#   goi vong_xem() — logic nam o vong_xem(), khong nhan doi. cwd = thu muc tool
#   nen `import xem_truoc` thay file nay (hoac saytool import truc tiep). Phong
#   khi xem_truoc khong nam tren sys.path cua tool, fallback import saytool va
#   dinh nghia lai o cho — nhung ban dong goi KHONG di duong nay (dung --say-xem). ]]
MA_CON = r'''
import sys
try:
    import xem_truoc
    sys.exit(xem_truoc.vong_xem())
except Exception:
    pass
# Fallback: khong import duoc xem_truoc (vi tri khac) -> chay noi dung toi thieu.
import json, base64
import cv2
from pathlib import Path
def ra(**kw):
    sys.stdout.write(json.dumps(kw) + "\n"); sys.stdout.flush()
try:
    from saytool.mot_anh import Bo
    from saytool.ngu_canh import NguCanh
    from saytool.buoc import tat_ca
except Exception as e:
    ra(loai="hong", loi=f"{type(e).__name__}: {e}"); sys.exit(1)
BO = None; NC = None; FP = None; CANH = 1400
def nen(img):
    ok, buf = cv2.imencode(".png", img, [cv2.IMWRITE_PNG_COMPRESSION, 3])
    return base64.b64encode(buf).decode("ascii") if ok else ""
for dong in sys.stdin:
    dong = dong.strip()
    if not dong: continue
    try: y = json.loads(dong)
    except Exception: continue
    v = y.get("viec")
    try:
        if v == "khoi_dong":
            BO = Bo(y.get("may", "auto"))
            ra(loai="san_sang", keo=[{"ten": b.ten, "nhan": b.nhan} for b in tat_ca()])
        elif v == "mo_anh":
            NC = NguCanh(Path(y["fp"]), canh_toi_da=CANH); FP = y["fp"]; _ = NC.anh
            H, W = NC.anh.shape[:2]
            mat = []
            for f in sorted(NC.mat or [], key=lambda m: -float(m.width)):
                bx1, by1, bx2, by2 = [float(t) for t in f.bbox[:4]]
                mat.append([bx1, by1, bx2 - bx1, by2 - by1])
            ra(loai="da_mo", fp=FP, so_mat=len(mat), mat=mat, rong=W, cao=H, goc=nen(NC.anh))
        elif v == "tinh":
            if NC is None or BO is None or y.get("fp") != FP:
                ra(loai="hong", loi="chua mo anh nay", ma=y.get("ma"), fp=y.get("fp")); continue
            out = BO.chay(NC, y["muc"]); ra(loai="ket_qua", ma=y.get("ma"), fp=FP, anh=nen(out))
        elif v == "thoat":
            break
    except Exception as e:
        ra(loai="hong", loi=f"{type(e).__name__}: {e}", ma=y.get("ma"), fp=y.get("fp"))
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
        #[[ CHON LENH CHAY TIEN TRINH CON XEM TRUOC.
        #
        #   Ban DONG GOI: PHAI `AutoTone.exe --say-xem` (chinh app chay
        #   vong_xem). KHONG duoc `python_cho(goc) -c MA_CON`: ban all-in-one
        #   khong co .venv nen python_cho() tra sys.executable = AutoTone.exe,
        #   ma frozen exe KHONG hieu `-c <code>` -> tien trinh con khong chay ->
        #   KEO THANH KHONG HIEN KET QUA tren preview (loi user bao 5/10).
        #   Cung bay voi _hoi_keo/kiem_tra/lenh_saytool. Khi frozen va goi CO
        #   saytool -> --say-xem voi sys.executable, cwd = thu muc tai nguyen
        #   (noi co saytool + mo_hinh). Chay tu ma nguon moi dung -c MA_CON.
        #]]
        try:
            import retouch as _rt_mod
            frozen = (getattr(_rt_mod, "trong_goi", lambda: False)()
                      and _rt_mod.goc_trong_goi() is not None)
        except Exception:                                    # noqa: BLE001
            frozen = bool(getattr(sys, "frozen", False))
        try:
            if frozen:
                cmd = [sys.executable, "--say-xem"]
            else:
                py = self.rt.python_cho(self.goc_tool)
                cmd = [str(py), "-c", MA_CON]
            self.proc = subprocess.Popen(
                cmd, cwd=self.goc_tool,
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
