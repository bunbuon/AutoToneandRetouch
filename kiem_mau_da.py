#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kiem_mau_da.py — Tool cân xong có ra ĐÚNG chỗ anh cân tay không.

    python kiem_mau_da.py "G:\\PUBGDay1" "F:\\Sản Phẩm Final\\Migimir\\PUBGM1"

VÌ SAO CẦN FILE NÀY, TRONG KHI ĐÃ CÓ hoc_mau_da.py
    hoc_mau_da.py chấm bằng ba ngưỡng tôi tự đặt, và MỘT TRONG BA ĐẶT SAI:

        "tỉ lệ kéo lạnh phải nằm trong 35-65%"

    Ngưỡng đó ngầm giả định một buổi chụp cân bằng thì phải nửa kéo ấm nửa kéo
    lạnh. Giả định ấy KHÔNG đúng cho một buổi mà ánh sáng vốn ấm đều từ đầu tới
    cuối: lúc đó cân đúng NGHĨA LÀ kéo lạnh gần hết. Số 85% mà nó chấm "hỏng"
    có thể chính là số đúng.

    Tôi không nới ngưỡng cho vừa kết quả — tôi bỏ hẳn cái ngưỡng đo nhầm thứ,
    và thay bằng câu hỏi thật sự cần trả lời:

        SAU KHI TOOL SỬA, MÀU DA CÓ RƠI VÀO ĐÚNG CHỖ ANH ĐÃ CÂN TAY KHÔNG?

    Câu này không cần giả định gì cả. Ảnh anh đã duyệt là mốc đúng, và sai số
    đo bằng stop — cùng đơn vị cho mọi buổi, mọi ánh sáng.

CÁCH ĐO
    Ghép từng ảnh RAW với đúng ảnh đã xuất của nó theo tên file, rồi so:
      · màu da trên ảnh ĐÃ DUYỆT            -> mốc đúng
      · màu da trên RAW + phần tool sẽ sửa  -> tool sẽ ra chỗ nào

MỘT ĐIỀU PHẢI NÓI RÕ
    Bước "RAW + phần tool sẽ sửa" là tính, không phải render thật qua Lightroom.
    Nó dùng đúng hằng số wb_temp_gain của app (900K cho mỗi stop) — tức chính
    cái quy đổi mà app vẫn dùng để ra quyết định. Nên phép kiểm này đo được app
    ĐỊNH đi tới đâu; nó không thay được việc mở ảnh ra nhìn.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at   # noqa: E402
from hoc_mau_da import linear_sang_srgb   # noqa: E402

ANH_XUAT = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

#[[ NGUONG DAT TRUOC KHI NHIN SO.
#
#   Don vi la stop cua log2(B/R) tren mau da. 0.1 stop = 90K o mac quy doi cua
#   app — mat thuong bat dau thay ám khi lech chung 0.15-0.2 stop tren mau da.
#]]
NGUONG_TRUNG_VI = 0.15     # stop
NGUONG_TRONG_BAND = 70.0   # % số ảnh phải nằm trong ±0.25 stop
BAND = 0.25


def gio_chup_anh(p: Path):
    """Giờ chụp trong EXIF của một ảnh ĐÃ XUẤT. None nếu không có.

    Đọc bằng PIL chứ không qua read_raw(): read_raw chỉ bóc EXIF khi file mở đầu
    bằng II/MM (kiểu TIFF), còn JPEG mở đầu bằng FFD8 nên nó không đọc tag nào —
    và parse_dt() sẽ lặng lẽ lùi về NGÀY SỬA FILE. Lấy ngày sửa file làm giờ
    chụp rồi đem đi ghép cặp thì ghép ra toàn cặp sai mà không ai biết.
    """
    try:
        from PIL import Image
        with Image.open(p) as im:
            ex = im.getexif()
            if not ex:
                return None
            s = None
            try:
                s = ex.get_ifd(0x8769).get(0x9003)     # DateTimeOriginal
            except Exception:                          # noqa: BLE001
                pass
            s = s or ex.get(0x0132)                    # DateTime
            if not s:
                return None
            return str(s).strip()[:19]
    except Exception:                                  # noqa: BLE001
        return None


def gio_chup_raw(p: Path):
    """Giờ chụp của file RAW, CHỈ khi lấy được từ EXIF thật."""
    try:
        _b, t = at.read_raw(p)
    except Exception:                                  # noqa: BLE001
        return None
    s = t.get("datetime_original") or t.get("datetime")
    return str(s).strip()[:19] if s else None


def ghep(ds_raw: list, ds_duyet: list) -> tuple[list, str]:
    """Ghép RAW với ảnh đã duyệt. -> (danh sách cặp, tên cách ghép đã dùng).

    THỬ TÊN TRƯỚC, RỒI MỚI TỚI GIỜ CHỤP
        Tên file là cách chắc nhất khi nó còn nguyên. Nhưng Lightroom lúc Export
        thường đổi tên theo dãy số, và lúc đó tên hai bên không còn liên quan gì
        tới nhau — buổi PUBGDay1 ngày 5/9: 1031 RAW, 773 ảnh đã xuất, khớp đúng
        0 cặp theo tên.

        Giờ chụp thì sống sót qua mọi kiểu đổi tên, vì nó nằm trong EXIF chứ
        không nằm ở tên file.
    """
    d_ten = {}
    for p in ds_duyet:
        d_ten.setdefault(p.stem.lower(), p)
    cap = [(p, d_ten[p.stem.lower()]) for p in ds_raw if p.stem.lower() in d_ten]
    if cap:
        return cap, "tên file"

    #[[ GIAY NAO TRUNG THI BO HAN, KHONG DOAN.
    #
    #   EXIF chi ghi toi GIAY, ma may chup lien thanh thi vai tam roi vao cung
    #   mot giay. Ban dau toi giu "tam dau tien cua moi giay" — va no ghep SAI
    #   1/10 cap khi thu: hai file RAW cung giay deu tro ve cung mot anh duyet,
    #   mot cap dung mot cap sai, va cai sai di thang vao ket qua do duoi dang
    #   mot con so lech bia dat.
    #
    #   Mat vai cap thi chi thua it so lieu. Ghep sai mot cap thi hong so lieu
    #   ma khong ai nhin ra. Nen giay nao xuat hien hon mot lan o BAT KY BEN NAO
    #   deu bi loai.
    #]]
    from collections import Counter
    gio_duyet = {p: gio_chup_anh(p) for p in ds_duyet}
    gio_raw = {p: gio_chup_raw(p) for p in ds_raw}
    dem_d = Counter(g for g in gio_duyet.values() if g)
    dem_r = Counter(g for g in gio_raw.values() if g)
    if not dem_d:
        return [], "không ghép được"

    d_gio = {g: p for p, g in gio_duyet.items()
             if g and dem_d[g] == 1 and dem_r.get(g, 0) == 1}
    cap = [(p, d_gio[g]) for p, g in gio_raw.items() if g and g in d_gio]
    cap.sort(key=lambda x: x[0].name)
    bo = sum(1 for g, n in dem_r.items() if n > 1 or dem_d.get(g, 0) > 1)
    if cap:
        if bo:
            print(f"  (bỏ {bo} mốc giây có nhiều hơn một ảnh — chụp liên thanh, "
                  f"không ghép chắc được)")
        return cap, "giờ chụp trong EXIF"
    return [], "không ghép được"


def mau_da(p: Path, cfg: dict):
    r = at.measure(p, cfg["preview_px"], cfg["meter"], wb_needs_faces=True)
    if not r["ok"] or not r.get("face_rgb"):
        return None, r
    return at.wb_cast(np.asarray(r["face_rgb"], dtype=np.float64))[0], r


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Kiem tool co ra dung cho user can tay.")
    ap.add_argument("buoi", type=Path, help="Thu muc RAW")
    ap.add_argument("da_duyet", type=Path, help="Thu muc anh da xuat va duyet")
    ap.add_argument("--so", type=int, default=200)
    ap.add_argument("--ref", type=str, default=None,
                    help="Mau da dich muon thu, vi du 227,184,168")
    a = ap.parse_args(argv)

    for d in (a.buoi, a.da_duyet):
        if not d.is_dir():
            print(f"  [!] Không thấy thư mục {d}")
            return 2

    cfg = dict(at.DEFAULTS)
    if a.ref:
        cfg["skin_ref_rgb"] = [int(x) for x in a.ref.split(",")]

    ds_duyet = [p for p in sorted(a.da_duyet.iterdir())
                if p.is_file() and p.suffix.lower() in ANH_XUAT]
    ds_raw = [p for p in sorted(a.buoi.iterdir())
              if p.is_file() and p.suffix.lower() in at.RAW_EXTS]
    cap, cach = ghep(ds_raw, ds_duyet)

    if not cap:
        print("  [!] Không ghép được cặp nào.")
        print(f"      RAW  : {len(ds_raw)} file · ví dụ: "
              + ", ".join(p.name for p in ds_raw[:3]))
        print(f"      duyệt: {len(ds_duyet)} file · ví dụ: "
              + ", ".join(p.name for p in ds_duyet[:3]))
        print("\n      Đã thử ghép theo TÊN FILE và theo GIỜ CHỤP trong EXIF, đều trượt.")
        n_dt = sum(1 for p in ds_duyet[:20] if gio_chup_anh(p) is not None)
        if n_dt == 0:
            print("      Ảnh đã xuất KHÔNG còn EXIF giờ chụp — nên chỉ còn cách")
            print("      ghép theo tên. Trong Lightroom lúc Export, phần Metadata")
            print("      chọn 'All Metadata' (đừng chọn 'Copyright Only'), hoặc")
            print("      xuất lại với File Naming giữ nguyên tên gốc.")
        else:
            print("      Ảnh đã xuất CÓ EXIF giờ chụp, nhưng không giờ nào khớp với")
            print("      buổi RAW này — nhiều khả năng hai thư mục là hai buổi khác nhau.")
        return 1

    print(f"  Ghép được {len(cap)} cặp RAW ↔ ảnh đã duyệt (theo {cach}). Đang đo ...")
    if a.so and len(cap) > a.so:
        idx = np.linspace(0, len(cap) - 1, a.so).astype(int)
        cap = [cap[i] for i in idx]

    ref_lin = at.srgb_to_linear(np.asarray(cfg["skin_ref_rgb"], dtype=np.float64) / 255.0)
    rt = at.wb_cast(ref_lin)[0]
    G = float(cfg["wb_temp_gain"])
    g = float(cfg["skin_gain"])
    tran = float(cfg["wb_temp_max"])

    lech_truoc, lech_sau, doi_hoi, n = [], [], [], 0
    c_raw_all, c_duyet_all = [], []
    for i, (p, q) in enumerate(cap, 1):
        c_raw, _ = mau_da(p, cfg)
        c_duyet, _ = mau_da(q, cfg)
        if c_raw is None or c_duyet is None:
            continue
        #[[ Dung DUNG cong thuc trong decide(): skin_temp_ev = do duoc - dich,
        #   temp_adj = skin_gain * wb_temp_gain * skin_temp_ev, roi kep trong tran.
        #   Ap nguoc lai bang chinh he so quy doi do.
        #]]
        adj = float(np.clip(g * G * (c_raw - rt), -tran, tran))
        c_sau = c_raw - adj / G
        lech_truoc.append(c_raw - c_duyet)
        lech_sau.append(c_sau - c_duyet)
        # muc sua ma cong thuc DOI HOI, truoc khi bi kep vao tran
        doi_hoi.append(g * G * (c_raw - rt))
        c_raw_all.append(c_raw)
        c_duyet_all.append(c_duyet)
        n += 1
        if i % 50 == 0:
            print(f"    {i}/{len(cap)}")

    if n < 10:
        print(f"  [!] Chỉ đo được {n} cặp — quá ít.")
        return 1

    lt = np.abs(np.array(lech_truoc))
    ls = np.abs(np.array(lech_sau))
    print(f"\n  Đo được {n} cặp. Màu da đích đang thử: {cfg['skin_ref_rgb']}\n")
    print("  LỆCH so với ảnh anh đã duyệt (stop; 0.1 stop ≈ 90K):")
    print(f"    RAW chưa sửa gì      : trung vị {np.median(lt):.3f} · "
          f"p75 {np.percentile(lt, 75):.3f} · trong ±{BAND} "
          f"{100.0 * (lt <= BAND).mean():.0f}%")
    print(f"    SAU KHI TOOL SỬA     : trung vị {np.median(ls):.3f} · "
          f"p75 {np.percentile(ls, 75):.3f} · trong ±{BAND} "
          f"{100.0 * (ls <= BAND).mean():.0f}%")

    #[[ Chi in ti le cai thien khi lech ban dau du lon de ty le co nghia.
    #   Anh vao gan nhu khong lech san (trung vi 0.004) thi phep chia ra nhung
    #   con so kieu "-3779%" — dung ve so hoc, vo nghia ve noi dung.
    #]]
    if np.median(lt) >= 0.05:
        cai_thien = 100.0 * (1 - np.median(ls) / np.median(lt))
        print(f"\n    -> tool thu hẹp được {cai_thien:.0f}% khoảng cách")
    else:
        print("\n    -> ảnh vào vốn đã sát ảnh duyệt (lệch dưới 0.05 stop), "
              "không có khoảng cách nào để thu hẹp")

    print(f"\n  NGƯỠNG ĐẶT TRƯỚC KHI ĐO:")
    d1 = float(np.median(ls)) < NGUONG_TRUNG_VI
    d2 = 100.0 * float((ls <= BAND).mean()) >= NGUONG_TRONG_BAND
    print(f"    [{'ĐẠT ' if d1 else 'HỎNG'}] trung vị lệch < {NGUONG_TRUNG_VI} stop"
          f"        -> {np.median(ls):.3f}")
    print(f"    [{'ĐẠT ' if d2 else 'HỎNG'}] ≥{NGUONG_TRONG_BAND:.0f}% ảnh trong ±{BAND} stop"
          f"    -> {100.0 * (ls <= BAND).mean():.0f}%")

    #[[ skin_gain < 1 KHONG PHAI LA "KEO CHUA TOI", NO LA MOT PHEP HOI QUY.
    #
    #   Ban dau toi dinh ghi o day rang san cua cach lam nay la do tan cua anh da
    #   duyet quanh mau dich — vi g=1 thi moi anh roi dung vao rt. Sai.
    #
    #   Cong thuc thuc te la:  c_sau = (1-g)*c_raw + g*rt
    #   Voi g<1, ket qua GIU LAI mot phan mau da tho cua chinh tam anh do. Ma mau
    #   da tho co mang thong tin that ve tam anh (nguoi da ngam hon, anh sang cho
    #   do khac) — thu ma mot con so chung khong the biet. Nen g<1 co the CHINH
    #   XAC HON g=1, chu khong phai kem hon.
    #
    #   Mo phong voi dap an biet truoc da chi ra dung dieu do: du lieu sinh ra
    #   quanh mot mau dich -0.95 voi do tan 0.10, vay ma bo so tot nhat lai la
    #   g=0.7 voi sai so 0.049 — thap hon han cai "san 0.175" ma toi tuong.
    #
    #   Nen o day khong in ra "san" nao ca. Chi in do tan de biet buoi nay dong
    #   deu hay tan mat, roi de phep quet tu tim bo so.
    #]]
    tan = np.abs(np.array(c_duyet_all) - np.median(c_duyet_all))
    print(f"\n  Ảnh anh đã duyệt tản quanh mức chung của chính chúng: trung vị "
          f"{np.median(tan):.3f} · p75 {np.percentile(tan, 75):.3f} stop")
    print(f"    (tản rộng thì một màu đích chung khó bám; tản hẹp thì dễ)")

    #[[ QUET THAM SO, CO CHIA DOI DU LIEU.
    #
    #   175 cap ma do 3 tham so thi rat de chon trung bo so chi dep tren dung bo
    #   so nay. Nen: chon tren NUA DAU, roi bao cao tren NUA SAU chua he duoc
    #   nhin toi. Hai con so lech nhau nhieu tuc la da khop qua tay.
    #]]
    cr = np.array(c_raw_all)
    cd = np.array(c_duyet_all)
    chia = np.arange(len(cr)) % 2 == 0          # xen ke, khong cat theo thoi gian
    def cham_diem(rt_, g_, tran_, m):
        adj = np.clip(g_ * G * (cr[m] - rt_), -tran_, tran_)
        e = np.abs(cr[m] - adj / G - cd[m])
        return float(np.median(e)), 100.0 * float((e <= BAND).mean())

    tot = None
    for rt_ in np.linspace(cd.min(), cd.max(), 41):
        for g_ in (0.6, 0.7, 0.8, 0.9, 1.0):
            for tran_ in (400.0, 500.0, 600.0, 800.0, 1000.0):
                tv, band = cham_diem(rt_, g_, tran_, chia)
                if tot is None or tv < tot[0]:
                    tot = (tv, band, rt_, g_, tran_)
    _tv, _band, rt_b, g_b, tran_b = tot
    tv_ktra, band_ktra = cham_diem(rt_b, g_b, tran_b, ~chia)
    rgb_b = linear_sang_srgb(at.srgb_to_linear(
        np.asarray(cfg["skin_ref_rgb"], dtype=np.float64) / 255.0)
        * np.array([1.0, 1.0, 2.0 ** (rt_b - rt)]))

    print(f"\n  QUÉT THAM SỐ (chọn trên nửa dữ liệu, chấm trên nửa còn lại):")
    print(f"    tốt nhất: skin_gain {g_b} · wb_temp_max {tran_b:.0f}K · "
          f"màu đích ≈ {rgb_b}")
    print(f"    trên nửa đã dùng để chọn : trung vị {_tv:.3f} · trong ±{BAND} {_band:.0f}%")
    print(f"    trên nửa CHƯA nhìn tới   : trung vị {tv_ktra:.3f} · "
          f"trong ±{BAND} {band_ktra:.0f}%")
    #[[ CAU HOI DUNG LA "TREN DU LIEU CHUA NHIN TOI, NO CO HON CAU HINH DANG
    #   DUNG KHONG", chu khong phai "hai nua co giong nhau khong".
    #
    #   Ban dau toi chi bao dong khi hai nua lech qua 0.03. Chay that ra 0.118 va
    #   0.152 — lech 0.034, va no keu "dung dung". Nhung 0.034 stop = 30K, nam
    #   trong nhieu lay mau voi ~88 anh moi nua; va quan trong hon, 0.152 tren
    #   nua CHUA nhin toi van hon han 0.212 cua cau hinh dang chay. Bo so do dung
    #   duoc.
    #
    #   Nguong 0.03 do la mot phep do gian tiep, va no tra loi nham cau hoi. Toi
    #   khong noi nguong cho vua ket qua — toi doi sang so sanh THANG voi cau
    #   hinh hien tai, la thu quyet dinh co nen doi hay khong.
    #]]
    hon_hien_tai = tv_ktra < float(np.median(ls))
    if abs(tv_ktra - _tv) > 0.03:
        print(f"    (hai nửa lệch {abs(tv_ktra - _tv):.3f} — có nhiễu lấy mẫu, "
              f"đừng tin con số 'nửa đã chọn')")
    if hon_hien_tai:
        print(f"    -> TRÊN DỮ LIỆU CHƯA NHÌN TỚI vẫn hơn cấu hình đang chạy "
              f"({tv_ktra:.3f} so với {np.median(ls):.3f}). Dùng được.")
    else:
        print(f"    -> trên dữ liệu chưa nhìn tới KHÔNG hơn cấu hình đang chạy "
              f"({tv_ktra:.3f} so với {np.median(ls):.3f}). Đừng đổi.")

    if not (d1 and d2):
        dh = np.abs(np.array(doi_hoi))
        cham = 100.0 * float((dh >= tran).mean())
        print(f"\n  {cham:.0f}% ảnh đòi mức sửa vượt trần ±{tran:.0f}K "
              f"(đòi hỏi trung vị {np.median(dh):.0f}K).")
        print("  Hai chỗ có thể nới, và chúng chữa hai bệnh khác nhau:")
        print(f"    · wb_temp_max ({tran:.0f}K) — trần. Nới nếu nhiều ảnh chạm trần.")
        print(f"    · skin_gain ({g}) — giữ lại bao nhiêu phần màu da gốc của")
        print(f"      chính tấm ảnh đó. KHÔNG phải càng cao càng đúng: giữ lại một")
        print(f"      phần màu gốc là cách mang theo thông tin riêng của từng ảnh")
        print(f"      mà một màu đích chung không biết. Để phép quét ở trên chọn.")
    else:
        print("\n  ĐẠT. Đổi trong autotone.py, mục DEFAULTS:")
        print(f'      "skin_ref_rgb": {cfg["skin_ref_rgb"]},')
        print("\n  Rồi chạy một buổi và MỞ ẢNH RA NHÌN — số chỉ nói tool định đi tới")
        print("  đâu, không nói ảnh đã đẹp.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
