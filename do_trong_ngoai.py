#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""do_trong_ngoai.py — ĐO xem có tách được ảnh ngoài trời khỏi ảnh trong nhà không.

    python do_trong_ngoai.py "G:\\PUBGDay1"
    python do_trong_ngoai.py "G:\\PUBGDay1" --so 400     # chỉ lấy 400 ảnh cho nhanh

ĐÂY LÀ CÔNG CỤ ĐO, KHÔNG PHẢI TÍNH NĂNG
    Nó không đổi một thông số nào của ảnh. Việc của nó là trả lời một câu duy
    nhất: mấy dấu hiệu dưới đây có TÁCH ĐƯỢC hai nhóm không, và tách ở đâu.
    Trả lời xong rồi mới bàn tới chuyện làm gì khác đi với ảnh ngoài trời.

VÌ SAO PHẢI ĐO TRƯỚC
    Số liệu buổi PUBGDay1 (1031 ảnh) cho thấy: 95% ảnh bị làm LẠNH đi, và 34%
    bị ghim đúng ở mức lạnh tối đa (4850K = 5250 - wb_temp_max 400). Không một
    ảnh nào được giữ nguyên. Tức phần cân WB đang kéo một chiều gần như tuyệt
    đối — và người dùng nhìn thấy đúng cái đó: ảnh ngoài nắng bị xanh.
    Nhưng "95% bị làm lạnh" CHƯA nói được rằng thủ phạm là chuyện trong/ngoài.
    Có thể mức lạnh tối đa rơi vào ảnh trong nhà cũng nhiều y như vậy. Phải đo.

BỐN DẤU HIỆU ĐEM RA SO
    ev_sang   — độ sáng môi trường, tính từ khẩu/tốc/ISO. KHÔNG nhìn pixel nên
                không bị màn LED, áo trắng hay phông tối đánh lừa. Trong nhà sự
                kiện thường EV 6-9; ngoài trời ban ngày EV 13-16.
    xanh_do   — log2(B/R) của cả khung. Trời xanh kéo số này lên.
    dinh_sang — độ sáng dải TRÊN CÙNG của khung so với cả khung. Ngoài trời thì
                bầu trời làm dải trên sáng vượt hẳn.
    chay      — tỉ lệ vùng cháy sáng. Trời trắng thường cháy.

    Ba cái sau đều nhìn pixel nên đều có cách bị đánh lừa (chụp ngược sáng trong
    nhà, trần nhà trắng, đèn sân khấu). Đưa cả bốn vào để so xem cái nào tách
    sạch hơn, chứ không phải để cộng đại lại thành một điểm số.

RA CÁI GÌ
    do_trong_ngoai.csv  — mỗi ảnh một dòng, đủ bốn dấu hiệu
    do_trong_ngoai.png  — bảng ảnh nhỏ xếp theo ev_sang, có ghi số trên từng ảnh
                          (để mắt người xác nhận: chỗ nào là ranh giới thật)
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autotone as at   # noqa: E402


def dau_hieu_anh(p: Path, cfg: dict) -> dict | None:
    """Gọi HÀM THẬT của app để đo, rồi thêm mấy chỉ số chỉ dùng cho bài đo này.

    Không tự đọc file, không tự dựng lại đường đo — measure() là cái app chạy,
    nên số ra ở đây đúng bằng số app nhìn thấy.
    """
    r = at.measure(p, cfg["preview_px"], cfg["meter"],
                   wb_needs_faces=(cfg["wb"] == "skin"))
    if not r["ok"]:
        return None

    rgb = r.get("rgb_mean")
    xanh_do = None
    if rgb and rgb[0] > 0 and rgb[2] > 0:
        xanh_do = float(np.log2(rgb[2] / rgb[0]))

    #[[ Dai TREN CUNG cua khung so voi ca khung.
    #
    #   Doc lai preview mot lan nua chi de lay cho nay. Ton them mot lan giai
    #   nen, nhung day la BAI DO chay mot lan — khong phai duong chay hang ngay —
    #   nen chon cach ro rang thay vi nhet them vao measure() mot chi so ma chua
    #   biet co dung den hay khong.
    #]]
    dinh = None
    try:
        blob, tags = at.read_raw(p)
        if blob is not None:
            import io
            im = Image.open(io.BytesIO(blob))
            im.draft("RGB", (320, 320))
            im = at.apply_orientation(im.convert("RGB"), tags.get("orientation"))
            a = np.asarray(im, dtype=np.float64) / 255.0
            y = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
            tren = y[: max(1, y.shape[0] // 5), :].mean()
            ca = y.mean()
            dinh = float(tren / (ca + 1e-6))
    except Exception:                                        # noqa: BLE001
        pass

    return {
        "path": str(p),
        "ten": p.name,
        "ev_sang": r.get("ev_sang"),
        "iso": r.get("iso"),
        "toc": r.get("exposure_time"),
        "khau": r.get("fnumber"),
        "xanh_do": xanh_do,
        "dinh_sang": dinh,
        "chay": r.get("sat_frac"),
        "metered_ev": r.get("metered_ev"),
        "so_mat": r.get("faces_n"),
        "dt": r.get("dt"),
    }


def tach_duoc_khong(gt: list, ten: str) -> str:
    """Một dấu hiệu tách được hai nhóm tới đâu.

    Dùng khoảng trống LỚN NHẤT giữa hai giá trị liền kề khi đã sắp xếp. Tách
    thành hai cụm rõ ràng thì khoảng trống đó vượt hẳn mọi khoảng còn lại; là
    một đám liên tục thì không có khoảng nào nổi bật.

    KHÔNG dùng max-min: nó chỉ nói dải rộng bao nhiêu, không nói có tách hay
    không. Đã mắc đúng lỗi này khi phân tích tách cảnh hồi 3/9.
    """
    v = sorted(x for x in gt if x is not None)
    if len(v) < 20:
        return "quá ít số liệu"
    kh = [(v[i + 1] - v[i], v[i], v[i + 1]) for i in range(len(v) - 1)]
    kh.sort(reverse=True)
    lon, a, b = kh[0]
    iqr = float(np.percentile(v, 75) - np.percentile(v, 25))
    duoi = sum(1 for x in v if x <= a)
    ty = 100.0 * duoi / len(v)

    #[[ SO KHOANG TRONG LON NHAT VOI IQR, khong so voi khoang trong TRUNG VI.
    #
    #   Ban dau chia cho trung vi cua cac khoang trong, va no ra 0: khau/toc/ISO
    #   lap lai y het nhau tren hang loat anh nen qua nua so khoang trong bang 0,
    #   trung vi = 0, phep chia thanh vo nghia. Bai kiem tren 55 anh in ra
    #   "gap 0x" cho dung cai dau hieu manh nhat.
    #
    #   IQR khong bao gio bang 0 tru khi ca bo so giong het nhau, va no la thuoc
    #   do "do rong binh thuong" cua chinh dau hieu do. Khoang trong lon nhat ma
    #   bang nua IQR tro len thi day la hai cum, khong phai mot dam lien tuc.
    #]]
    if iqr <= 0:
        return f"mọi ảnh gần như cùng một giá trị ({v[0]:.2f}) — không tách được gì"
    ty_le = lon / iqr
    if ty_le >= 0.5 and 5 <= ty <= 95:
        nhan = "TÁCH RÕ hai cụm"
    elif ty_le >= 0.5:
        nhan = f"có khoảng trống to nhưng một bên chỉ {min(ty, 100 - ty):.0f}% — nhiều khả năng chỉ là vài ảnh cá biệt"
    else:
        nhan = "một đám liên tục, KHÔNG tách được"
    return (f"IQR {iqr:.2f} · khoảng trống lớn nhất {lon:.2f} tại {a:.2f}|{b:.2f} "
            f"(= {ty_le:.2f}× IQR) · chia {ty:.0f}%/{100 - ty:.0f}%\n"
            f"        -> {nhan}")


def bang_anh(rows: list, dest: Path, cot: int = 10, o: int = 150) -> Path:
    """Bảng ảnh nhỏ xếp theo ev_sang tăng dần, có ghi số lên từng ảnh."""
    co = [r for r in rows if r["ev_sang"] is not None]
    co.sort(key=lambda r: r["ev_sang"])
    #[[ Lay MAU TRAI DEU chu khong lay 100 anh dau: can nhin duoc CA HAI dau va
    #   nhat la vung GIUA, vi ranh gioi neu co thi nam o do.
    #]]
    n = min(100, len(co))
    idx = np.linspace(0, len(co) - 1, n).astype(int)
    lay = [co[i] for i in idx]

    hang = (len(lay) + cot - 1) // cot
    tam = Image.new("RGB", (cot * o, hang * (o + 16)), (24, 24, 26))
    ve = ImageDraw.Draw(tam)
    for i, r in enumerate(lay):
        try:
            blob, tags = at.read_raw(Path(r["path"]))
            im = Image.open(__import__("io").BytesIO(blob))
            im.draft("RGB", (o * 2, o * 2))
            im = at.apply_orientation(im.convert("RGB"), tags.get("orientation"))
            im.thumbnail((o, o))
        except Exception:                                    # noqa: BLE001
            im = Image.new("RGB", (o, o), (60, 60, 60))
        x, y = (i % cot) * o, (i // cot) * (o + 16)
        tam.paste(im, (x, y))
        ve.text((x + 3, y + o + 2), f"EV{r['ev_sang']:.1f}  {r['ten'][:12]}",
                fill=(210, 210, 210))
    tam.save(dest)
    return dest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Do kha nang tach anh trong/ngoai.")
    ap.add_argument("folder", type=Path)
    ap.add_argument("--so", type=int, default=0, help="Chi lay N anh (0 = het)")
    ap.add_argument("--ra", type=Path, default=None, help="Thu muc ghi ket qua")
    a = ap.parse_args(argv)

    d = a.folder
    if not d.is_dir():
        print(f"  [!] Không thấy thư mục {d}")
        return 2
    ra = a.ra or d
    ds = sorted(p for p in d.iterdir()
                if p.is_file() and p.suffix.lower() in at.RAW_EXTS)
    if a.so:
        #[[ Lay trai deu ca buoi, khong lay N anh dau: buoi chup thuong doi boi
        #   canh theo thoi gian, lay dau la chi thay mot loai.
        #]]
        idx = np.linspace(0, len(ds) - 1, min(a.so, len(ds))).astype(int)
        ds = [ds[i] for i in idx]
    if not ds:
        print(f"  [!] {d} không có file RAW nào")
        return 2

    cfg = dict(at.DEFAULTS)
    print(f"  Đang đo {len(ds)} ảnh trong {d} ...")
    rows = []
    for i, p in enumerate(ds, 1):
        r = dau_hieu_anh(p, cfg)
        if r:
            rows.append(r)
        if i % 50 == 0:
            print(f"    {i}/{len(ds)}")
    if not rows:
        print("  [!] Không đo được ảnh nào")
        return 1

    csv_p = ra / "do_trong_ngoai.csv"
    with csv_p.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    print(f"\n  Đo xong {len(rows)} ảnh.\n")
    print("  DẤU HIỆU NÀO TÁCH ĐƯỢC HAI NHÓM:")
    #[[ ISO tinh tren THANG LOGA.
    #
    #   ISO la thang nhan: 100->200 va 800->1600 deu la mot stop, nhung tren
    #   thang thang thi mot cai cach 100 con cai kia cach 800. Do "khoang trong"
    #   bang so ISO tho thi moi khoang trong to nhat luon roi vao dau ISO cao,
    #   du do chi la buoc nhay binh thuong cua may.
    #
    #   Nguoi dung de xuat ISO lam dau hieu (ngoai troi 100-400, trong nha 600+)
    #   — dung ve kinh nghiem chup, nen dua han vao day de moi buoi deu duoc
    #   kiem thay vi phai hoi lai.
    #]]
    lg_iso = [float(np.log2(r["iso"])) if r.get("iso") else None for r in rows]
    for k, nhan, lay in (
            ("ev_sang",   "ev_sang   (khẩu/tốc/ISO, không nhìn pixel)", None),
            ("iso",       "ISO       (đo trên thang loga)", lg_iso),
            ("xanh_do",   "xanh_do   (log2 B/R cả khung)", None),
            ("dinh_sang", "dinh_sang (dải trên khung / cả khung)", None),
            ("chay",      "chay      (tỉ lệ cháy sáng)", None)):
        gt = lay if lay is not None else [r[k] for r in rows]
        print(f"    {nhan}\n        {tach_duoc_khong(gt, k)}")

    co_iso = [r["iso"] for r in rows if r.get("iso")]
    if co_iso:
        print("\n  ISO theo ngưỡng thường dùng (ngoài trời 100-400, trong nhà 600+):")
        for ten, dk in (("ISO ≤400  (thường là ngoài trời)", lambda v: v <= 400),
                        ("ISO 500   (vùng giữa)", lambda v: 400 < v < 600),
                        ("ISO ≥600  (thường là trong nhà)", lambda v: v >= 600)):
            n = sum(1 for v in co_iso if dk(v))
            print(f"    {ten}: {n} ảnh ({100.0 * n / len(co_iso):.0f}%)")

    ev = [r["ev_sang"] for r in rows if r["ev_sang"] is not None]
    if ev:
        print(f"\n  ev_sang: thấp nhất {min(ev):.1f} · trung vị "
              f"{float(np.median(ev)):.1f} · cao nhất {max(ev):.1f}")
        for lo, hi, nhan in ((0, 10, "EV <10  — gần như chắc chắn trong nhà"),
                             (10, 12, "EV 10-12 — vùng lẫn, phải nhìn ảnh"),
                             (12, 30, "EV >12  — gần như chắc chắn ngoài trời")):
            n = sum(1 for x in ev if lo <= x < hi)
            print(f"    {nhan}: {n} ảnh ({100.0 * n / len(ev):.0f}%)")
    else:
        print("\n  [!] Không đọc được khẩu/tốc/ISO của ảnh nào — dấu hiệu ev_sang "
              "không dùng được với máy ảnh này.")

    png = ra / "do_trong_ngoai.png"
    print("\n  Đang vẽ bảng ảnh...")
    bang_anh(rows, png)

    print(f"\n  {csv_p}")
    print(f"  {png}")
    print("\n  Mở file .png xem: xếp theo ev_sang tăng dần. Nhìn xem ranh giới "
          "trong/ngoài\n  rơi vào quãng EV nào — rồi gửi lại cả hai file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
