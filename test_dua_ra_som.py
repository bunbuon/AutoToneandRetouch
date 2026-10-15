#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đưa kết quả ra SỚM trong lúc lượt còn chạy (13/10) — retouch.dua_ket_qua_ra(chi_on_dinh=True).

Ba điều phải đúng, mỗi điều từng gây giao khách ảnh hỏng nếu sai:
  1. file ra tạm vừa ghi (chưa đứng yên ON_DINH_RA_GIAY) KHÔNG được đưa ra;
  2. file engine còn đang cầm (os.replace lỗi) KHÔNG được chép dự phòng — để lần sau;
  3. file đã yên thì đưa ra, trả đúng số và đúng danh sách ảnh vào (da_ra);
     gọi lại lần nữa không đưa gì thêm; lượt cuối (chi_on_dinh=False) vẫn dọn phần còn lại.

    python3 test_dua_ra_som.py
"""
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import retouch as rt  # noqa: E402

LOI = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    vao, tam, ra = td / "vao", td / "ra_tam", td / "ra"
    for d in (vao, tam, ra):
        d.mkdir()
    anh = []
    for i in range(3):
        p = vao / f"a{i}.jpg"
        p.write_bytes(b"goc")
        anh.append(str(p))
    # a0: ra tạm đã yên lâu; a1: vừa ghi; a2: chưa có kết quả
    (tam / "a0.jpg").write_bytes(b"ket qua 0")
    cu = time.time() - 5
    os.utime(tam / "a0.jpg", (cu, cu))
    (tam / "a1.jpg").write_bytes(b"ket qua 1")

    da = []
    n = rt.dua_ket_qua_ra(anh, vao, tam, ra, chi_on_dinh=True, da_ra=da)
    ktra("file đã yên được đưa ra, file vừa ghi thì chưa", n == 1 and da == [anh[0]], f"n={n} da={da}")
    ktra("thư mục ra có đúng a0, chưa có a1", (ra / "a0.jpg").is_file() and not (ra / "a1.jpg").exists())
    ktra("ra tạm còn a1", (tam / "a1.jpg").is_file())

    n2 = rt.dua_ket_qua_ra(anh, vao, tam, ra, chi_on_dinh=True)
    ktra("gọi lại ngay: không đưa gì thêm", n2 == 0, f"n2={n2}")

    # a1 đã yên nhưng engine còn cầm (mở file ghi) -> os.replace lỗi trên Windows -> bỏ qua, KHÔNG chép
    cu = time.time() - 5
    os.utime(tam / "a1.jpg", (cu, cu))
    if os.name == "nt":
        f = open(tam / "a1.jpg", "ab")
        n3 = rt.dua_ket_qua_ra(anh, vao, tam, ra, chi_on_dinh=True)
        f.close()
        ktra("file engine còn cầm: để lần sau, không chép dự phòng",
             n3 == 0 and not (ra / "a1.jpg").exists(), f"n3={n3}")
    n4 = rt.dua_ket_qua_ra(anh, vao, tam, ra, chi_on_dinh=True)
    ktra("file đã yên và đã buông: đưa ra", n4 == 1 and (ra / "a1.jpg").read_bytes() == b"ket qua 1")

    # lượt cuối (như cũ): dọn phần còn lại, không đụng tấm đã ra
    (tam / "a2.jpg").write_bytes(b"ket qua 2")
    n5 = rt.dua_ket_qua_ra(anh, vao, tam, ra)
    ktra("lượt cuối dọn đúng phần còn lại", n5 == 1 and (ra / "a2.jpg").is_file(), f"n5={n5}")
    ktra("tổng ba lần = đủ 3 ảnh, không đếm trùng", n + n4 + n5 == 3)

# ---- MayMixin._don_som — ĐÈ LÊN ẢNH GỐC giữa lượt (15/10, user Vtt 775 ảnh: "Retouching
#  đang xử lý rất nhiều nhưng không thấy trả ra kết quả ngoài folder" — 495 tấm xong vẫn
#  nằm ẩn trong .autotone_retouch_tam_1/ra_1 vì chỉ đưa ra khi cả lượt xong)
import threading  # noqa: E402
import retouch_may  # noqa: E402


class GiaMay:
    rt = rt
    _xem_dang_hien = False

    def __init__(self):
        self.hien = []

    def _hien_anh_dia(self, path, giu_khung=False):
        self.hien.append((path, giu_khung))


with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    vao, nhom, tam = td / "Số 1", td / ".autotone_retouch_tam" / "nhom_1", td / ".autotone_retouch_tam" / "ra_1"
    for d in (vao, nhom, tam):
        d.mkdir(parents=True)
    anh = []
    for i in range(3):
        q = vao / f"SAY-Media-{i}.jpg"
        q.write_bytes(b"goc")
        os.link(q, nhom / q.name)          # như dung_thu_muc_nhom: liên kết cứng
        anh.append(str(q))
    may = GiaMay()
    may._khoa_som = threading.Lock()
    may._som_luot = 0
    may._anh_dang = anh[0]
    may._luot_hien = (anh, vao, tam, None, False, True)        # ghi_de=True, ra=None
    cu = time.time() - 5
    for i in (0, 1):
        (tam / f"SAY-Media-{i}.jpg").write_bytes(f"retouch {i}".encode())
        os.utime(tam / f"SAY-Media-{i}.jpg", (cu, cu))
    retouch_may.MayMixin._don_som(may)
    ktra("ghi đè giữa lượt: 2 tấm engine đã xong đè lên ảnh gốc NGAY, tấm chưa xong giữ gốc",
         Path(anh[0]).read_bytes() == b"retouch 0" and Path(anh[1]).read_bytes() == b"retouch 1"
         and Path(anh[2]).read_bytes() == b"goc", f"som={may._som_luot}")
    ktra("…bản liên kết cứng engine đang đọc (nhom_1) vẫn là ảnh gốc",
         (nhom / "SAY-Media-0.jpg").read_bytes() == b"goc")
    ktra("…đếm 2 tấm đã đưa ra sớm, ảnh lớn đang xem tải lại bản đã retouch",
         may._som_luot == 2 and may.hien == [(anh[0], True)], str(may.hien))
    may._luot_hien = None                  # lượt đã kết thúc -> _don_som không đụng gì nữa
    (tam / "SAY-Media-2.jpg").write_bytes(b"retouch 2")
    retouch_may.MayMixin._don_som(may)
    ktra("…lượt đã kết thúc (khoá về None): _don_som không làm gì",
         Path(anh[2]).read_bytes() == b"goc" and may._som_luot == 2)
    n_cuoi = rt.dua_ket_qua_ra(anh, vao, tam, None, False, True) + may._som_luot
    ktra("…cuối lượt: dọn tấm còn lại, tổng = 3, không đếm trùng",
         n_cuoi == 3 and Path(anh[2]).read_bytes() == b"retouch 2", f"n={n_cuoi}")

# ---- dọn thư mục tạm: MỐC XOÁ SAU CÙNG (15/10 — thư mục vào trong Google Drive: Drive cầm
#  file + thả desktop.ini -> rmtree xoá mốc rồi kẹt -> lần sau tạo .autotone_retouch_tam_1, _2…)
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    vao = td / "Số 1"
    vao.mkdir()
    d = rt.tao_thu_muc_tam(vao)
    ktra("tạo thư mục tạm cạnh thư mục vào, có mốc",
         d.name == ".autotone_retouch_tam" and (d / rt.MOC_TAM).is_file(), str(d))
    for con in ("nhom_1", "ra_1"):
        (d / con).mkdir()
        (d / con / "SAY-Media-1.jpg").write_bytes(b"x")
    (d / "ra_1" / "desktop.ini").write_text("[.ShellClassInfo]", encoding="utf-8")
    if os.name == "nt":
        f = open(d / "ra_1" / "SAY-Media-1.jpg", "rb")     # như Drive đang cầm file để tải lên
        sach = rt.don_thu_muc_tam(d)
        ktra("file còn bị cầm: chưa sạch nhưng GIỮ mốc (lần sau dọn tiếp được)",
             not sach and (d / rt.MOC_TAM).is_file(), f"sach={sach}")
        f.close()
    sach = rt.don_thu_muc_tam(d)
    ktra("buông file: dọn sạch, kể cả desktop.ini", sach and not d.exists())
    d2 = rt.tao_thu_muc_tam(vao)
    ktra("lần chạy sau dùng lại đúng tên, không đẻ _1", d2.name == ".autotone_retouch_tam", d2.name)
    rt.don_thu_muc_tam(d2)

print()
print("TẤT CẢ ĐẠT" if not LOI else f"{len(LOI)} LỖI: " + "; ".join(LOI))
sys.exit(1 if LOI else 0)
