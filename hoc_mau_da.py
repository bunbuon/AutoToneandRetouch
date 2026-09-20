#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hoc_mau_da.py — Rút màu da đích từ chính những ảnh anh đã cân tay và thấy ưng.

    python hoc_mau_da.py "F:\\PUBGDay1_export"
    python hoc_mau_da.py "F:\\PUBGDay1_export" --buoi "G:\\PUBGDay1"

ĐƯA VÀO CÁI GÌ
    Một thư mục ảnh ĐÃ XUẤT (JPEG) — bản cuối cùng anh duyệt. Không phải RAW.

    Vì sao phải là ảnh đã xuất: autotone đo trên preview nhúng trong file RAW,
    mà preview đó là bản máy ảnh render, KHÔNG mang thông số anh chỉnh trong
    Lightroom. Nhìn vào RAW là nhìn thấy màu da TRƯỚC khi anh sửa — đúng cái ta
    đang muốn thay. Ảnh JPEG đã xuất mới là màu da anh gật đầu.

    Càng nhiều mặt càng chắc. 30-50 ảnh có người là đủ; vài trăm thì tốt.

LẤY RA CÁI GÌ
    Một bộ ba số để thay cho skin_ref_rgb = [244, 212, 202] đang dùng.

    CHỈ TỈ LỆ MÀU LÀ QUAN TRỌNG, không phải độ sáng: decide() chỉ lấy
    log2(B/R) và log2(G/√(R·B)) của màu đích (xem wb_cast). Nên bộ ba mới có thể
    tối hơn hay sáng hơn bộ cũ mà không ảnh hưởng gì tới độ sáng ảnh — nó chỉ
    dời cái ĐÍCH MÀU.

ĐO BẰNG CHÍNH HÀM CỦA APP
    Gọi thẳng at.measure() lên từng ảnh JPEG, rồi lấy face_rgb nó trả về. Cùng
    bộ nhận mặt, cùng bộ lọc da theo hue/sat, cùng cách lấy trung bình. Tự viết
    lại một cách đo "gần giống" ở đây thì con số rút ra sẽ không so được với con
    số app dùng lúc chạy — và đó là kiểu sai không ai nhìn ra.

NGƯỠNG ĐẶT TRƯỚC KHI ĐO
    Buổi PUBGDay1 với màu đích hiện tại: 95% ảnh bị kéo lạnh, 34% ghim ở trần
    ±400K, 0 ảnh giữ nguyên. Màu đích mới chỉ đáng thay nếu:

      1. tỉ lệ ghim trần            < 10%   (đang 34%)
      2. tỉ lệ kéo lạnh          35% - 65%  (đang 95%)
      3. trung vị |temp_adj|       < 150K   (đang 400K)

    Ghi ra đây TRƯỚC khi chạy. Không đạt thì bỏ đề xuất và ghi lại vì sao, chứ
    không nới ngưỡng cho vừa kết quả.
"""
from __future__ import annotations

import argparse
import ntpath
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at   # noqa: E402

ANH_XUAT = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

# Ngưỡng đặt trước — xem phần đầu file
NGUONG_GHIM = 10.0        # %
NGUONG_LANH = (35.0, 65.0)  # %
NGUONG_TRUNG_VI = 150.0   # K


def linear_sang_srgb(v: np.ndarray) -> np.ndarray:
    """Nghịch đảo của at.srgb_to_linear, để in ra bộ ba 0..255 dễ đọc."""
    v = np.clip(np.asarray(v, dtype=np.float64), 0.0, 1.0)
    ra = np.where(v <= 0.0031308, v * 12.92, 1.055 * np.power(v, 1 / 2.4) - 0.055)
    #[[ .tolist() ngay tai day: khong tra ve mang numpy. In mang numpy ra thi
    #   thanh "np.int64(244)" — vua kho doc, vua khong dan thang vao file cau
    #   hinh duoc, ma do la muc dich cuoi cung cua ca cong cu nay.
    #]]
    return np.clip(np.round(ra * 255.0), 0, 255).astype(int).tolist()


def gom_mau_da(d: Path, cfg: dict, so: int = 0) -> tuple[list, int]:
    """-> (danh sách face_rgb tuyến tính, số ảnh đã xem)."""
    ds = sorted(p for p in d.iterdir()
                if p.is_file() and p.suffix.lower() in ANH_XUAT)
    if so and len(ds) > so:
        idx = np.linspace(0, len(ds) - 1, so).astype(int)
        ds = [ds[i] for i in idx]
    #[[ DEM RIENG TUNG LY DO TRUOT, khong gop lam mot.
    #
    #   Ban dau chi dem "thay mat o N anh" roi bo qua phan con lai khong noi gi.
    #   Ngay 5/9 no in "thay mat o 0/300 anh" va cau tiep theo la "kiem lai thu
    #   muc co dung la JPEG khong" — chi sai duong hoan toan: file dung la anh
    #   da xuat, chi la read_raw() khong doc duoc dinh dang do. Mat gan mot vong
    #   doan mo.
    #
    #   "Khong doc duoc anh" va "doc duoc nhung khong co ai trong khung" la hai
    #   chuyen khac han nhau va can hai cach xu ly khac han nhau. Dem rieng, va
    #   giu lai vai cau bao loi that de con biet duong ma lan.
    #]]
    mau, mau_ngoai, loi_doc, khong_mat, khong_da = [], [], [], 0, 0
    for i, p in enumerate(ds, 1):
        #[[ wb_needs_faces=True de chac chan nhanh do mat duoc chay, du cach do
        #   sang dang dat la gi.
        #]]
        r = at.measure(p, cfg["preview_px"], cfg["meter"], wb_needs_faces=True)
        if not r["ok"]:
            if len(loi_doc) < 3:
                loi_doc.append(f"{p.name}: {r['error'][:70]}")
            else:
                loi_doc.append("")
        elif not r.get("faces_n"):
            khong_mat += 1
        elif not r.get("face_rgb"):
            khong_da += 1
        else:
            mau.append(r["face_rgb"])
            #[[ Gom rieng nhom ngoai troi. Dung CHINH ham ngoai_troi() cua app —
            #   nguong doi trong DEFAULTS thi cong cu nay doi theo, khong lech.
            #]]
            if at.ngoai_troi(r, cfg):
                mau_ngoai.append(r["face_rgb"])
        if i % 50 == 0:
            print(f"    {i}/{len(ds)}  (đo được màu da ở {len(mau)} ảnh)")
    return mau, {"tong": len(ds), "loi_doc": loi_doc, "ngoai": mau_ngoai,
                 "khong_mat": khong_mat, "khong_da": khong_da}


def thu_tren_buoi(buoi: Path, cfg: dict, ref, so: int) -> dict | None:
    """Chạy thật cả buổi RAW với màu đích cho trước -> thống kê temp_adj."""
    ds = sorted(p for p in buoi.iterdir()
                if p.is_file() and p.suffix.lower() in at.RAW_EXTS)
    if not ds:
        return None
    if so and len(ds) > so:
        idx = np.linspace(0, len(ds) - 1, so).astype(int)
        ds = [ds[i] for i in idx]

    xuat = at.read_catalog_export(at.latest_catalog_export() or Path("x"))
    c = dict(cfg)
    c["skin_ref_rgb"] = list(ref)
    #[[ Tat "bo qua anh nguoi sua tay": buoi da chay tool roi thi gan nhu moi anh
    #   deu bi danh dau, va plan() RUT HAN chung khoi danh sach — thong ke se
    #   tinh tren vai anh con sot. Da mac dung bay nay.
    #]]
    c["bo_qua_nguoi_sua"] = False
    if xuat:
        c["source"] = "catalog"

    items = []
    for p in ds:
        r = at.measure(p, c["preview_px"], c["meter"],
                       wb_needs_faces=(c["wb"] == "skin"))
        if not r["ok"]:
            continue
        r["dt_obj"] = datetime.fromisoformat(r["dt"])
        if not xuat:
            sc = at.sidecar_for(p)
            if sc is None:
                continue
            r["sidecar"] = str(sc)
        items.append(r)
    if not items:
        return None

    at.plan(items, c, buoi, xuat)
    adj = np.array([r["temp_adj"] for r in items if r.get("temp_adj") is not None])
    if not len(adj):
        return None
    tran = float(c["wb_temp_max"])
    return {
        "n": len(adj),
        "ghim": 100.0 * float((np.abs(adj) >= tran - 0.5).sum()) / len(adj),
        "lanh": 100.0 * float((adj < 0).sum()) / len(adj),
        "trung_vi": float(np.median(np.abs(adj))),
    }


def in_thong_ke(ten: str, t: dict | None) -> None:
    if t is None:
        print(f"    {ten}: không chạy được")
        return
    print(f"    {ten:14s} ghim trần {t['ghim']:5.1f}%  ·  kéo lạnh {t['lanh']:5.1f}%"
          f"  ·  trung vị |temp_adj| {t['trung_vi']:5.0f}K   (n={t['n']})")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Rut mau da dich tu anh da xuat va duyet.")
    ap.add_argument("thu_muc_da_xuat", type=Path)
    ap.add_argument("--buoi", type=Path, default=None,
                    help="Thu muc RAW de thu xem doi mau dich thi ra sao")
    ap.add_argument("--so", type=int, default=300)
    a = ap.parse_args(argv)

    d = a.thu_muc_da_xuat
    if not d.is_dir():
        print(f"  [!] Không thấy thư mục {d}")
        return 2

    cfg = dict(at.DEFAULTS)
    print(f"  Đang đo màu da trên ảnh đã xuất trong {d} ...")
    mau, td = gom_mau_da(d, cfg, a.so)

    print(f"\n  Trong {td['tong']} ảnh:")
    print(f"    đo được màu da       : {len(mau)}")
    if td["khong_mat"]:
        print(f"    đọc được, không có mặt: {td['khong_mat']}")
    if td["khong_da"]:
        print(f"    có mặt, lọc da ra rỗng: {td['khong_da']}")
    if td["loi_doc"]:
        print(f"    KHÔNG ĐỌC ĐƯỢC ẢNH   : {len(td['loi_doc'])}")
        for m in [x for x in td["loi_doc"] if x][:3]:
            print(f"        {m}")

    if len(mau) < 10:
        print(f"\n  [!] Chỉ đo được màu da ở {len(mau)}/{td['tong']} ảnh — quá ít "
              f"để rút ra một màu đích đáng tin.")
        print("      Cần ít nhất 10 ảnh có người, nên có 30-50 ảnh trở lên.")
        if td["loi_doc"]:
            print("\n      Phần lớn là KHÔNG ĐỌC ĐƯỢC ẢNH — xem thông báo lỗi ở trên.")
            print("      Không phải chuyện thư mục sai; là định dạng file.")
        elif td["khong_mat"]:
            print("\n      Ảnh đọc được hết, chỉ là KHÔNG CÓ NGƯỜI trong khung.")
            print("      Chọn thư mục có ảnh chụp người — ảnh sản phẩm, ảnh")
            print("      không gian, ảnh backdrop thì không rút được màu da.")
        return 1

    A = np.asarray(mau, dtype=np.float64)
    #[[ TRUNG VI chu khong phai trung binh: mot ao cam hay mot manh tuong go lot
    #   qua bo loc da se keo trung binh di, con trung vi thi khong.
    #]]
    med = np.median(A, axis=0)

    #[[ CHON DO SANG SAO CHO LAM TRON 0..255 IT LAM HONG TI LE NHAT.
    #
    #   Chi ti le mau moi co nghia (wb_cast chi lay B/R va G/sqrt(RB)), nen ve
    #   nguyen tac nhan med voi so nao cung duoc. Nhung buoc cuoi phai lam tron
    #   ve so nguyen 0..255, va viec lam tron do LAM LECH ti le — do that: he so
    #   0.9 lech 13.5K, he so 0.5 chi lech 6.0K.
    #
    #   Vai chuc Kelvin thi nho so voi tran 400K, nhung day la con so ta se dat
    #   lam DICH cho ca he thong; khong co ly do gi de mang theo mot sai so ma
    #   chon giup mot dong lenh la het. Nen thu mot dai he so roi giu cai giu
    #   duoc ti le sat nhat.
    #]]
    goc_t, goc_i = at.wb_cast(med)
    tot, sai_tot = None, None
    for hs in np.linspace(0.25, 0.95, 71):
        thu = linear_sang_srgb(med / max(med.max(), 1e-9) * hs)
        lin = at.srgb_to_linear(np.asarray(thu, dtype=np.float64) / 255.0)
        if lin.min() <= 0:
            continue
        t_, i_ = at.wb_cast(lin)
        sai = abs(t_ - goc_t) + abs(i_ - goc_i)
        if sai_tot is None or sai < sai_tot:
            tot, sai_tot = thu, sai
    moi = tot if tot is not None else linear_sang_srgb(med / max(med.max(), 1e-9) * 0.5)

    #[[ MAU DICH RIENG CHO ANH NGOAI TROI.
    #
    #   Cung cach rut, chi khac tap anh: chi nhung tam co ISO <= iso_ngoai_troi.
    #   Neu ca thu muc khong co tam nao ngoai troi thi khong in gi — thieu du
    #   lieu thi noi thieu, khong bia ra mot con so.
    #]]
    def _rut(A_):
        m_ = np.median(np.asarray(A_, dtype=np.float64), axis=0)
        gt, gi = at.wb_cast(m_)
        best, sai_best = None, None
        for hs_ in np.linspace(0.25, 0.95, 71):
            th = linear_sang_srgb(m_ / max(m_.max(), 1e-9) * hs_)
            li = at.srgb_to_linear(np.asarray(th, dtype=np.float64) / 255.0)
            if li.min() <= 0:
                continue
            t2, i2 = at.wb_cast(li)
            sa = abs(t2 - gt) + abs(i2 - gi)
            if sai_best is None or sa < sai_best:
                best, sai_best = th, sa
        return best or linear_sang_srgb(m_ / max(m_.max(), 1e-9) * 0.5)

    ng = td.get("ngoai") or []
    moi_ngoai = _rut(ng) if len(ng) >= 10 else None

    cu = np.asarray(cfg["skin_ref_rgb"], dtype=np.float64)
    cu_lin = at.srgb_to_linear(cu / 255.0)
    t_cu, i_cu = at.wb_cast(cu_lin)
    t_moi, i_moi = at.wb_cast(at.srgb_to_linear(np.asarray(moi, dtype=np.float64) / 255.0))


    print(f"  Màu da đích ĐANG DÙNG : {cu.astype(int).tolist()}"
          f"   log2(B/R) {t_cu:+.3f}")
    print(f"  Màu da ĐỀ XUẤT        : {moi}"
          f"   log2(B/R) {t_moi:+.3f}")
    print(f"\n  Chênh {t_moi - t_cu:+.3f} stop "
          f"(≈ {(t_moi - t_cu) * cfg['wb_temp_gain']:+.0f}K ở mức khuếch đại hiện tại)")
    print("  (chỉ TỈ LỆ màu là quan trọng — độ sáng của bộ ba này không ảnh hưởng gì)")

    print(f"\n  TÁCH THEO ISO (ngưỡng ngoài trời: ISO ≤ {cfg['iso_ngoai_troi']}):")
    print(f"    ảnh ngoài trời: {len(ng)} / {len(mau)} đo được màu da")
    if moi_ngoai is None:
        print("    Chưa đủ 10 ảnh ngoài trời để rút ra một màu đích riêng.")
        print("    Cần thư mục ảnh đã duyệt có nhiều ảnh chụp ngoài trời hơn —")
        print("    hoặc gộp thêm buổi khác. KHÔNG đặt số bừa cho nhóm này:")
        print("    đặt sai thì mọi ảnh ngoài trời lệch cùng một chiều, đúng cái")
        print("    lỗi vừa sửa xong ở màu đích chung.")
    else:
        t_ng = at.wb_cast(at.srgb_to_linear(
            np.asarray(moi_ngoai, dtype=np.float64) / 255.0))[0]
        print(f"    màu đích ngoài trời : {moi_ngoai}   log2(B/R) {t_ng:+.3f}")
        print(f"    màu đích chung      : {moi}   log2(B/R) {t_moi:+.3f}")
        print(f"    chênh {t_ng - t_moi:+.3f} stop "
              f"({(t_ng - t_moi) * cfg['wb_temp_gain']:+.0f}K)")
        #[[ Chenh qua nho thi tach lam gi cho phuc tap. 0.05 stop = 45K, duoi
        #   muc mat thuong thay tren mau da.
        #]]
        if abs(t_ng - t_moi) < 0.05:
            print("\n    Hai nhóm gần như trùng nhau (dưới 45K) — tách trong/ngoài")
            print("    KHÔNG đem lại gì ở buổi này. Cứ để skin_ref_rgb_ngoai = None.")
        else:
            print("\n    Đặt trong autotone.py, mục DEFAULTS:")
            print(f'        "skin_ref_rgb_ngoai": {moi_ngoai},')

    if a.buoi is None:
        print("\n  Chưa thử trên buổi thật. Thêm  --buoi \"G:\\PUBGDay1\"  để xem "
              "đổi màu đích\n  thì phần cân WB đổi ra sao TRƯỚC KHI đụng vào cấu hình.")
        return 0

    if not a.buoi.is_dir():
        print(f"\n  [!] Không thấy thư mục buổi {a.buoi}")
        return 2

    print(f"\n  Đang chạy thử cả hai màu đích trên {a.buoi} ...")
    t_truoc = thu_tren_buoi(a.buoi, cfg, cu.astype(int).tolist(), a.so)
    t_sau = thu_tren_buoi(a.buoi, cfg, moi, a.so)

    print("\n  KẾT QUẢ:")
    in_thong_ke("màu đích CŨ:", t_truoc)
    in_thong_ke("màu đích MỚI:", t_sau)

    if t_sau is None:
        print("\n  Không chạy được trên buổi này — chưa kết luận được gì.")
        return 1

    print(f"\n  NGƯỠNG ĐẶT TRƯỚC KHI ĐO:")
    dat = []
    for ten, gia, ok in (
            (f"ghim trần < {NGUONG_GHIM:.0f}%", f"{t_sau['ghim']:.1f}%",
             t_sau["ghim"] < NGUONG_GHIM),
            (f"kéo lạnh {NGUONG_LANH[0]:.0f}-{NGUONG_LANH[1]:.0f}%",
             f"{t_sau['lanh']:.1f}%",
             NGUONG_LANH[0] <= t_sau["lanh"] <= NGUONG_LANH[1]),
            (f"trung vị |temp_adj| < {NGUONG_TRUNG_VI:.0f}K",
             f"{t_sau['trung_vi']:.0f}K", t_sau["trung_vi"] < NGUONG_TRUNG_VI)):
        print(f"    [{'ĐẠT ' if ok else 'HỎNG'}] {ten:32s} -> {gia}")
        dat.append(ok)

    print()
    if all(dat):
        print("  ĐẠT CẢ BA. Đổi trong autotone.py, mục DEFAULTS:")
        print(f'      "skin_ref_rgb": {moi},')
        print("\n  Rồi chạy lại một buổi và NHÌN ẢNH — số liệu chỉ nói phần cân WB")
        print("  đã hết lệch một chiều, không nói ảnh đã đẹp.")
    else:
        print("  CHƯA ĐẠT ĐỦ. Không đổi vội — màu đích rút ra từ ảnh đã xuất mà vẫn")
        print("  không cân được nghĩa là còn một nguyên nhân khác nữa (nhiều khả")
        print("  năng là wb_temp_gain / skin_gain). Gửi lại bảng này.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
