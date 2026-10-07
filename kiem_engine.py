#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kiem_engine.py — engine THƯỜNG TRÚ (7/10): máy xem trước chạy cả mẻ.

    python kiem_engine.py <thư mục ảnh> [<thư mục gói>]

Mở máy xem trước (từ mã nguồn, hoặc từ gói đã đóng nếu đưa thư mục gói), rồi:
    1. khởi động · mở một tấm · tính xem trước (như kéo thanh)
    2. chạy mẻ 3 ảnh QUA ENGINE (retouch.chay(engine=)) -> 3 ảnh ra, mã 0,
       không mở tiến trình nào khác
    3. xem trước lại tấm đó: vẫn tính được, cùng tiến trình (pid không đổi)
    4. chạy mẻ 6 ảnh rồi xin DỪNG ngay -> dừng sớm (< 6 ảnh ra), mã 0, engine
       vẫn sống
    5. thoát sạch
In thời gian từng bước. ĐẠT / HỎNG ở cuối, mã thoát 0 / 1.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

LOI: list = []


def ktra(ten, ok, chi_tiet=""):
    print(f"  [{'DAT ' if ok else 'HONG'}] {ten}  {chi_tiet}")
    if not ok:
        LOI.append(ten)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    nguon = Path(sys.argv[1])
    goi = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else None
    anh = sorted(p for p in nguon.iterdir() if p.suffix.lower() in (".jpg", ".jpeg"))[:6]
    if len(anh) < 6:
        print("cần ít nhất 6 ảnh jpg trong", nguon)
        return 2
    td = Path(tempfile.mkdtemp(prefix="kiem_engine_"))
    os.environ["AUTOTONE_DATA"] = str(td / "du_lieu")
    (td / "du_lieu").mkdir()
    k = Path(os.environ.get("LOCALAPPDATA", "")) / "AutoTone" / "khoa.json"
    if k.is_file():
        shutil.copy2(k, td / "du_lieu")
    os.environ["SAY_KHONG_GHI_NHAT_KY"] = "1"
    import retouch as rt
    import xem_truoc

    if goi is not None:
        #[[ Goi da dong: MayXem chay AutoTone.exe --say-xem khi retouch.trong_goi()
        #   — o day ta khong frozen, nen gia lap: tro sys.executable. ]]
        exe = goi / ("AutoTone.exe" if (goi / "AutoTone.exe").is_file() else "AutoTone")
        rt.trong_goi = lambda: True
        rt.goc_trong_goi = lambda: goi / "_internal"
        sys.executable = str(exe)
        goc_tool = goi / "_internal"
    else:
        goc_tool = rt.tim_tool()
        if not goc_tool:
            print("không tìm thấy tool retouch (ToolCloneEvoto)")
            return 2
    may = xem_truoc.MayXem(rt, str(goc_tool))
    t0 = time.perf_counter()
    loi = may.bat_dau("auto")
    ktra("mở máy xem trước", not loi, loi)
    if loi:
        return 1
    pid = may.proc.pid

    def cho(loai, giay=600):
        het = time.time() + giay
        while time.time() < het:
            for d in may.lay():
                if d.get("loai") in (loai, "hong", "chet"):
                    return d
            time.sleep(0.05)
        return None

    d = cho("san_sang")
    ktra("khởi động xong", bool(d) and d.get("loai") == "san_sang",
         f"{time.perf_counter() - t0:.1f}s · may={d and d.get('may')} · ort={d and d.get('ort')} · saytool {d and d.get('ban')}")
    may.gui(viec="mo_anh", fp=str(anh[0]))
    d = cho("da_mo")
    ktra("mở ảnh", bool(d) and d.get("loai") == "da_mo",
         f"so_mat={d and d.get('so_mat')}" if d and d.get("loai") == "da_mo"
         else f"tin nhận được: {({k: v for k, v in (d or {}).items() if k != 'goc'})}")
    muc = {"vet": 100, "min_da": 60, "da_body": 50}
    t1 = time.perf_counter()
    may.gui(viec="tinh", ma=1, fp=str(anh[0]), muc=muc)
    d = cho("ket_qua")
    ktra("xem trước tính được", bool(d) and d.get("loai") == "ket_qua" and bool(d.get("anh")),
         f"{time.perf_counter() - t1:.1f}s")

    # 2. me 3 anh qua engine
    vao = td / "vao3"; vao.mkdir()
    for p in anh[:3]:
        shutil.copy2(p, vao / p.name)
    ra = td / "ra3"
    t2 = time.perf_counter()
    dong = []; ma = None; pid_con = "khong"
    for loai, gt in rt.chay(goc_tool, vao, ra, muc, may="auto", luong=0, engine=may):
        if loai == "dong":
            dong.append(gt)
        elif loai == "ma":
            ma = gt
        elif loai == "pid":
            pid_con = gt
    so_ra = len(list(ra.glob("*.jp*g"))) if ra.is_dir() else 0
    ktra("mẻ 3 ảnh qua engine: 3 ảnh ra, mã 0, không mở tiến trình con",
         so_ra == 3 and ma == 0 and pid_con is None and may.song() and may.proc.pid == pid,
         f"{time.perf_counter() - t2:.1f}s · ra {so_ra} · mã {ma} · {len(dong)} dòng nhật ký")
    ktra("…nhật ký mẻ có dòng 'xong 3 anh'", any("xong 3 anh" in x for x in dong),
         (dong[-3] if len(dong) >= 3 else str(dong))[:90])

    # 3. xem truoc lai, cung tien trinh
    t3 = time.perf_counter()
    may.gui(viec="tinh", ma=2, fp=str(anh[0]), muc={"vet": 100, "min_da": 80, "da_body": 50})
    d = cho("ket_qua")
    ktra("xem trước lại sau mẻ: vẫn tính được, cùng pid", bool(d) and d.get("loai") == "ket_qua"
         and bool(d.get("anh")) and may.proc.pid == pid, f"{time.perf_counter() - t3:.1f}s")

    # 4. me 6 anh roi dung ngay
    vao6 = td / "vao6"; vao6.mkdir()
    for p in anh[:6]:
        shutil.copy2(p, vao6 / p.name)
    ra6 = td / "ra6"
    t4 = time.perf_counter()
    ma = None; n_dong = 0
    import threading
    gen = rt.chay(goc_tool, vao6, ra6, muc, may="auto", luong=0, engine=may)
    threading.Timer(1.5, may.dung_chay).start()
    for loai, gt in gen:
        if loai == "dong":
            n_dong += 1
        elif loai == "ma":
            ma = gt
    so6 = len(list(ra6.glob("*.jp*g"))) if ra6.is_dir() else 0
    ktra("xin dừng giữa mẻ 6 ảnh: dừng sớm, mã 0, engine còn sống",
         0 < so6 < 6 and ma == 0 and may.song(),
         f"{time.perf_counter() - t4:.1f}s · ra {so6}/6 · mã {ma}")

    # 5. thoat
    may.dong()
    time.sleep(1.0)
    ktra("thoát sạch", not may.song())
    shutil.rmtree(td, ignore_errors=True)
    print("TAT CA DAT" if not LOI else f"{len(LOI)} LOI")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
