# -*- coding: utf-8 -*-
"""MẪU MÀU DA GỢI Ý theo loại buổi (autotone.MAU_DA_GOI_Y + autotone_gui; 17/10).

User 17/10: "Tham khảo tư liệu để tạo ra 3 skill tone cho màu da của sự kiện, đám cưới, kỷ yếu phổ
biến cho cả trong và ngoài nhà dành cho người Việt Nam được ưa chuộng nhất để recomment."

Mục kiểm
    1. số màu: cả 6 khe là da sáng (L 0.79–0.86), hue trong dải tông da (30–52°), đậm/L 0.05–0.085;
       Cưới dịu nhất, Kỷ yếu hồng + đậm nhất (đích học từ 564 ảnh kỷ yếu user sửa), Sự kiện ấm nhất;
       ba mẫu khác nhau thấy được (ΔE OkLab·100 ≥ 1.5); ngoài trời ấm hơn trong nhà; có vùng trắng
    2. giao diện: danh sách mẫu có 3 gợi ý ngay sau "Mặc định"; mẫu đang chọn -> mau_da_dich đủ khe
    3. tự chọn: buổi chưa chọn mẫu (lần trước "Mặc định" / gợi ý) -> gợi ý theo loại buổi; buổi đã
       chọn mẫu riêng / lần trước dùng mẫu riêng -> giữ; đổi loại buổi khi đang dùng gợi ý -> gợi ý mới
    4. gợi ý không ghi vào mau_da.json, không xoá được

Chạy:  python test_mau_da_goi_y.py
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
from pathlib import Path

for _l in (sys.stdout, sys.stderr):
    try:
        _l.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                        # noqa: BLE001
        pass

LOI: list = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


class Bien:
    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v

    def set(self, v):
        self.v = v


def main() -> int:
    tam = Path(tempfile.mkdtemp(prefix="mau_goi_y_"))
    os.environ["AUTOTONE_DATA"] = str(tam / "du_lieu")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import autotone as at
    import autotone_gui as ag

    print("1. số màu")
    so = {}
    for loai, m in at.MAU_DA_GOI_Y.items():
        for khe in ("trong", "ngoai"):
            L, a, b = at.mau_dich_lab(m[khe])
            so[(loai, khe)] = (L, math.degrees(math.atan2(b, a)), math.hypot(a, b) / L)
    ktra("6 khe: L 0.79–0.86, hue 30–52°, đậm/L 0.05–0.085",
         all(0.79 <= L <= 0.86 and 30 <= h <= 52 and 0.05 <= c <= 0.085 for L, h, c in so.values()),
         str({k: tuple(round(x, 3) for x in v) for k, v in so.items()}))
    ktra("Cưới dịu nhất, Kỷ yếu hồng + đậm nhất, Sự kiện ấm nhất (trong nhà)",
         so[("cuoi", "trong")][2] < min(so[("su_kien", "trong")][2], so[("ky_yeu", "trong")][2])
         and so[("ky_yeu", "trong")][1] < min(so[("cuoi", "trong")][1], so[("su_kien", "trong")][1])
         and so[("ky_yeu", "trong")][2] > so[("su_kien", "trong")][2]
         and so[("su_kien", "trong")][1] > so[("cuoi", "trong")][1])
    ktra("Kỷ yếu trong nhà = đích học từ ảnh kỷ yếu user sửa (skin_dich_hong)",
         at.MAU_DA_GOI_Y["ky_yeu"]["trong"] == list(at.DEFAULTS["skin_dich_hong"]))
    import itertools
    import numpy as np
    de = {(x, y, k): 100 * float(np.linalg.norm(np.array(at.mau_dich_lab(at.MAU_DA_GOI_Y[x][k]))
                                               - np.array(at.mau_dich_lab(at.MAU_DA_GOI_Y[y][k]))))
          for x, y in itertools.combinations(at.MAU_DA_GOI_Y, 2) for k in ("trong", "ngoai")}
    ktra("ba mẫu khác nhau thấy được (ΔE OkLab·100 ≥ 1.5 mọi cặp)", min(de.values()) >= 1.5,
         str({f"{x}-{y}-{k}": round(v, 1) for (x, y, k), v in de.items()}))
    ktra("ngoài trời ấm hơn trong nhà (hue lớn hơn) ở cả 3 mẫu",
         all(so[(lo, "ngoai")][1] > so[(lo, "trong")][1] for lo in at.MAU_DA_GOI_Y))
    ktra("mỗi mẫu có đích vùng trắng (WB theo vùng trắng)",
         all((m.get("trang") or {}).get("trong") for m in at.MAU_DA_GOI_Y.values()))

    print("2. giao diện")
    d_file: dict = {"Gu riêng": {"trong": [220, 180, 160], "ngoai": [218, 176, 156]}}
    gy = list(ag.MAU_DA_GOI_Y)

    class Gia:
        _ten_mau_da = ag.App._ten_mau_da
        _mau_da_cua = ag.App._mau_da_cua
        _goi_y_cho_buoi = ag.App._goi_y_cho_buoi
        _mau_da_dang_chon = ag.App._mau_da_dang_chon
        _nho_mau_da = ag.App._nho_mau_da

        def __init__(self, loai="Cưới"):
            self.v_mau_da = Bien(ag.MAU_DA_MAC_DINH)
            self.v_loai_buoi = Bien(loai)
            self.v_folder = Bien("")
            self.f = None

        def _doc_mau_da(self):
            return d_file

        def folder(self):
            return self.f

        def _ve_mau_da(self):
            pass

    g = Gia()
    ds = g._ten_mau_da()
    ktra("danh sách: Mặc định, 3 gợi ý, rồi mẫu riêng", ds[:4] == [ag.MAU_DA_MAC_DINH] + gy
         and ds[4:] == ["Gu riêng"], str(ds))
    g.v_mau_da.set(gy[0])
    md = g._mau_da_dang_chon()
    ktra("chọn gợi ý -> mau_da_dich đủ trong / ngoài / vùng trắng",
         md and md["trong"] == at.MAU_DA_GOI_Y["cuoi"]["trong"] and md["ngoai"] == at.MAU_DA_GOI_Y["cuoi"]["ngoai"]
         and md.get("trang"), str(md))

    print("3. tự chọn theo loại buổi")
    nhan = {ma: n for n, ma in ag.LOAI_BUOI}
    for loai, ma in (("cuoi", "cuoi"), ("su_kien", "su_kien"), ("ky_yeu", "ky_yeu")):
        g = Gia(nhan[ma])
        d_file.pop("_cuoi", None)
        g._nho_mau_da(theo_buoi=False)
        ktra(f"chưa từng chọn -> gợi ý {loai}", ag.MAU_DA_GOI_Y.get(g.v_mau_da.get(), ("?",))[0] == loai,
             g.v_mau_da.get())
    g = Gia(nhan["su_kien"])
    d_file["_cuoi"] = ag.MAU_DA_MAC_DINH
    g._nho_mau_da(theo_buoi=False)
    ktra("lần trước 'Mặc định' -> gợi ý theo loại buổi", ag.MAU_DA_GOI_Y.get(g.v_mau_da.get(), ("?",))[0] == "su_kien")
    d_file["_cuoi"] = "Gu riêng"
    g._nho_mau_da(theo_buoi=False)
    ktra("lần trước dùng mẫu riêng -> giữ mẫu riêng", g.v_mau_da.get() == "Gu riêng")
    g.f = "G:/Buoi1"
    d_file["_theo_buoi"] = {"G:/Buoi1": ag.MAU_DA_MAC_DINH}
    g._nho_mau_da()
    ktra("buổi đã chọn 'Mặc định' riêng -> giữ", g.v_mau_da.get() == ag.MAU_DA_MAC_DINH)
    src = Path(ag.__file__).read_text(encoding="utf-8")
    ktra("đổi loại buổi khi đang dùng gợi ý -> gợi ý mới (mã nguồn _doi_loai_buoi)",
         "self.v_mau_da.get() in MAU_DA_GOI_Y \\\n                and self.v_mau_da.get() != self._goi_y_cho_buoi()" in src)

    print("4. không ghi / không xoá")
    ktra("gợi ý không nằm trong mau_da.json", not any(k in d_file for k in gy))
    ktra("Xoá mẫu: tắt khi đang là gợi ý; sửa chấm màu gợi ý -> mẫu riêng mới",
         "and self.v_mau_da.get() not in MAU_DA_GOI_Y else \"disabled\"" in src
         and "if ten in MAU_DA_GOI_Y:              # 17/10: mẫu gợi ý sẵn có" in src)
    print(f"\n{len(LOI)} LOI" if LOI else "\nTAT CA DAT")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
