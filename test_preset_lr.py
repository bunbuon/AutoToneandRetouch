# -*- coding: utf-8 -*-
"""Kiểm xem trước preset Lightroom cho cả lưới (9/10 — preset_lr / preset_ui / lưới Cân tone).

  1. đọc file preset .xmp: tên, nhóm, loại (bỏ profile), có mask
  2. danh sách: bản plugin (uuid Lightroom) đi trước bản quét .xmp; ẩn preset Adobe;
     User Presets đứng đầu; tìm không dấu
  3. yêu cầu gửi plugin: đầu file + đường dẫn theo thứ tự; tiến độ lọc theo id; bảng
  4. kho ảnh theo preset: có file -> dùng; Lightroom vừa ÁP job của buổi (sau lúc dựng)
     -> hết hạn, không dùng ảnh mang thông số cũ
  5. giao diện: chọn preset -> gửi đúng ảnh còn thiếu, tấm đang mở đi trước; plugin
     trả ảnh -> lưới đọc lại ảnh theo preset; ảnh lớn nguồn "preset", Trước = preview
     RAW; bấm ô mở to / bấm đúp về lưới / ← →; lọc sao; bỏ preset -> dừng + lưới về cũ
Chạy: python test_preset_lr.py"""
import os
import sys
import tempfile
import time
from pathlib import Path

TAM = Path(tempfile.mkdtemp(prefix="kiem_preset_lr_"))
os.environ["AUTOTONE_DATA"] = str(TAM / "data")
os.environ["APPDATA"] = str(TAM / "appdata")
sys.path.insert(0, str(Path(__file__).resolve().parent))

LOI = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


import autotone as at  # noqa: E402

JOBS = TAM / "jobs"
JOBS.mkdir(parents=True)
at.LR_JOB_DIR = JOBS
import preset_lr  # noqa: E402

XMP = '''<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
 <rdf:Description rdf:about="" xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"
   crs:PresetType="{loai}" crs:UUID="{uuid}" crs:Exposure2012="+0.30">
   <crs:Name><rdf:Alt><rdf:li xml:lang="x-default">{ten}</rdf:li></rdf:Alt></crs:Name>
   <crs:Group><rdf:Alt>{nhom}</rdf:Alt></crs:Group>
   {mask}
 </rdf:Description></rdf:RDF></x:xmpmeta>'''


def xmp(thu_muc, file, ten, nhom="", loai="Normal", mask=False):
    thu_muc.mkdir(parents=True, exist_ok=True)
    (thu_muc / file).write_text(XMP.format(
        loai=loai, uuid="EFAD0BFA" + str(abs(hash(ten)))[:8], ten=ten,
        nhom=(f'<rdf:li xml:lang="x-default">{nhom}</rdf:li>' if nhom
              else '<rdf:li xml:lang="x-default"/>'),
        mask="<crs:MaskGroupBasedCorrections><rdf:Seq/></crs:MaskGroupBasedCorrections>" if mask else ""),
        encoding="utf-8")


# ---- 1. đọc .xmp
st = TAM / "appdata" / "Adobe" / "CameraRaw" / "Settings"
xmp(st, "a.xmp", "cưới trắng hồng 1")
xmp(st, "b.xmp", "Bong", nhom="22.GRADUATION TỐT NGHIỆP")
xmp(st, "c.xmp", "Hồ sơ máy", loai="Look")
xmp(st, "d.xmp", "Có mask", mask=True)
d = preset_lr.doc_xmp(st / "a.xmp")
ktra("xmp: tên có dấu, không nhóm", d and d["ten"] == "cưới trắng hồng 1" and d["nhom"] == "", str(d))
ktra("xmp: nhóm riêng", preset_lr.doc_xmp(st / "b.xmp")["nhom"] == "22.GRADUATION TỐT NGHIỆP")
ktra("xmp: profile (PresetType Look) không phải preset develop", preset_lr.doc_xmp(st / "c.xmp") is None)
ktra("xmp: preset có mask được đánh dấu", preset_lr.doc_xmp(st / "d.xmp")["co_mask"] is True)

# ---- 2. danh sách
ds = preset_lr.danh_sach(False)
ktra("chưa có danh sách plugin -> quét .xmp, uuid rỗng (plugin tìm theo tên + nhóm)",
     [p["ten"] for p in ds] == ["Có mask", "cưới trắng hồng 1", "Bong"]
     and all(p["uuid"] == "" for p in ds) and ds[0]["nhom"] == "User Presets",
     str([(p["ten"], p["nhom"]) for p in ds]))
(JOBS / "lr_presets.tsv").write_text(
    "FEC09590\tcưới trắng hồng 1\tUser Presets\t" + str(st) + "\n"
    "A04EDE4F\tNoWBExposure\tUser Presets\t" + str(st) + "\n"
    "8D34416F\tBong\t22.GRADUATION TỐT NGHIỆP\t" + str(st) + "\n"
    "AD0001\tPortrait 1\tAdaptive: Portrait\tC:\\Program Files\\Adobe\\Adobe Lightroom Classic"
    "\\Resources\\Settings\\Adaptive\n", encoding="utf-8")
ds = preset_lr.danh_sach(False)
ktra("có danh sách plugin -> dùng uuid Lightroom, ẩn preset Adobe, User Presets đầu",
     [p["uuid"] for p in ds] == ["FEC09590", "A04EDE4F", "8D34416F"], str([p["uuid"] for p in ds]))
ktra("bật “Hiện preset của Adobe” -> có preset Adobe, xếp cuối",
     preset_lr.danh_sach(True)[-1]["ten"] == "Portrait 1")
ktra("tìm không dấu, không hoa thường", [p["ten"] for p in preset_lr.loc(ds, "CUOI trang")]
     == ["cưới trắng hồng 1"])

# ---- 3. yêu cầu plugin
buoi = TAM / "G" / "BVDay3"
buoi.mkdir(parents=True)
raws = []
for i in range(1, 7):
    f = buoi / f"DSC{i:04d}.ARW"
    f.write_bytes(b"II*\x00khong-phai-raw-that")
    raws.append(str(f))
P = {"uuid": "FEC09590", "ten": "cưới trắng hồng 1", "nhom": "User Presets"}
id_ = preset_lr.gui_xem(P, [raws[3], raws[0]], buoi)
yc = (JOBS / "request_xempreset.txt").read_text(encoding="utf-8").splitlines()
kho = preset_lr.thu_muc_kho(buoi, P)
ktra("yêu cầu: đầu file đủ khoá, đường dẫn theo thứ tự gửi",
     yc[0] == f"id={id_}" and "uuid=FEC09590" in yc and "ap=0" in yc and f"dest={kho}" in yc
     and yc[yc.index("---") + 1:] == [raws[3], raws[0]], str(yc))
ktra("tiến độ của lượt khác id -> None", preset_lr.tien_do(id_) is None)
(JOBS / "xempreset_tiendo.txt").write_text(f"id={id_}\ntrang_thai=dang_chay\nxong=1\ntong=2\n"
                                            "thieu=0\nlech=0\n", encoding="utf-8")
td = preset_lr.tien_do(id_)
ktra("tiến độ đúng id -> số", td and td["xong"] == 1 and td["tong"] == 2, str(td))

# ---- 4. kho
from PIL import Image  # noqa: E402


def render(path, mau):
    kho.mkdir(parents=True, exist_ok=True)
    out = kho / (Path(path).stem + ".jpg")
    Image.new("RGB", (240, 160), mau).save(out, "JPEG")
    return out


ktra("chưa render -> không có ảnh preset", preset_lr.anh_preset(raws[3], P) is None)
r4 = render(raws[3], (200, 40, 40))
ktra("đã render -> ảnh preset của đúng tấm", preset_lr.anh_preset(raws[3], P) == r4)
time.sleep(0.05)
done = JOBS / f"apply_20261010_101010_{at.ten_job(buoi.name)}.done"
done.write_text("x", encoding="utf-8")
preset_lr._hop_le.clear()
ktra("Lightroom vừa ÁP job của buổi sau lúc dựng -> ảnh preset hết hạn",
     preset_lr.anh_preset(raws[3], P) is None)
preset_lr.gui_xem(P, [raws[3]], buoi)
ktra("gửi lại -> kho cũ bị dọn (ảnh mang thông số trước lần ghi)", not r4.exists())

# ---- 5. giao diện
try:
    import tkinter as tk
    from datetime import timedelta
    import autotone_gui as ag
    import giao_dien as gd
    root = tk.Tk()
except Exception as ex:                                      # noqa: BLE001
    print(f"  (bo qua phan giao dien: {ex.__class__.__name__}: {ex})")
    root = None
if root is not None:
    root.withdraw()
    ag.bq.kiem = lambda: {"co_phep": True, "con_lai": timedelta(days=300), "nhac": "",
                          "goi": "1 năm", "may": "TEST01", "het_han": False, "ly_do": ""}
    gd.dat_theme(root)
    app = ag.App(root)

    def chay(n=3):
        for _ in range(n):
            app.update()
            time.sleep(0.02)

    app.v_folder.set(str(buoi))
    app.items = [{"path": p, "delta_ev": 0.1, "scene": 1, "rating": (1 if i == 2 else 0)}
                 for i, p in enumerate(raws)]
    app._tags = lambda r: ("",)
    preset_lr.dat_chon(None)
    app.dp_preset().chon(None)
    app._cap_nhat_luoi()
    chay(5)
    tl = app.thanh_luoi_ct
    ktra("thanh lưới Cân tone: đếm sao trên cả buổi",
         "Tất cả  6" in str(tl.pd_loc._lua_chon if hasattr(tl.pd_loc, "_lua_chon") else
                            tl._nhan_loc(6, 5, 1)) and len(app.luoi.ds) == 6)
    tl.v_loc.set("co_sao")
    tl._doi_loc()
    chay(3)
    ktra("lọc “Đã lọc (có sao)” -> lưới chỉ còn ảnh có sao",
         [Path(o["path"]).name for o in app.luoi.ds] == ["DSC0003.ARW"],
         str([Path(o["path"]).name for o in app.luoi.ds]))
    tl.v_loc.set("tat_ca")
    tl._doi_loc()
    chay(3)

    # bấm một ô -> ảnh lớn; bấm đúp -> lưới
    app.luoi.chon(raws[1])
    app._mo_mot_ct(raws[1])
    chay(5)
    ktra("bấm một ô -> ảnh lớn của tấm đó, lưới ẩn",
         app._che_do_ct == "mot" and app.o_mot_ct.winfo_manager() == "grid"
         and not app.luoi.winfo_manager() and app._anh_ct == raws[1])
    app._buoc_ct(1)
    chay(3)
    ktra("→ trên ảnh lớn: tấm kế theo thứ tự lưới", app._anh_ct == raws[2], Path(app._anh_ct).name)

    # chọn preset: tấm đang mở đi đầu, chỉ gửi ảnh còn thiếu
    render(raws[5], (40, 200, 40))
    dp = app.dp_preset()
    dp.chon(dict(P))
    yc = (JOBS / "request_xempreset.txt").read_text(encoding="utf-8").splitlines()
    gui = yc[yc.index("---") + 1:]
    ktra("chọn preset: gửi Lightroom 5 ảnh còn thiếu, tấm đang mở to đi đầu",
         len(gui) == 5 and gui[0] == raws[2] and raws[5] not in gui, str([Path(x).name for x in gui]))
    ktra("nút trên thanh lưới đổi theo preset", "cưới trắng hồng 1" in app.nut_preset_ct.btn.cget("text"),
         app.nut_preset_ct.btn.cget("text"))
    # plugin "render" tấm đang mở + ghi tiến độ / bảng
    r3 = render(raws[2], (30, 60, 220))
    (JOBS / "xempreset_tiendo.txt").write_text(f"id={dp.id}\ntrang_thai=dang_chay\nxong=1\ntong=5\n"
                                                "thieu=0\nlech=0\n", encoding="utf-8")
    (JOBS / "xempreset_anh.tsv").write_text(f"{raws[2]}\t{r3}\n", encoding="utf-8")
    nap = []
    goc_nap = app._nap_mot_ct
    app._nap_mot_ct = lambda p, giu_khung=False: (nap.append((p, giu_khung)), goc_nap(p, giu_khung))
    dp._soi()
    chay(5)
    ktra("Lightroom trả ảnh tấm đang mở -> ảnh lớn nạp lại, giữ chỗ đang soi",
         nap and nap[-1] == (raws[2], True), str(nap))
    import nguon_xem
    src, ng = nguon_xem.anh_xem(raws[2])
    ktra("ảnh lớn lấy nguồn “preset” (Lightroom render theo preset)", ng == "preset" and src == r3,
         f"{ng} {src}")
    ktra("nút báo tiến độ Lightroom", "2/6" in app.nut_preset_ct.lbl.cget("text"),
         app.nut_preset_ct.lbl.cget("text"))
    import luoi_anh
    ktra("lưới đọc ảnh nhỏ theo preset (nguồn chung các lưới)",
         luoi_anh.NGUON is not None and str(luoi_anh.NGUON(raws[2])) == str(r3))
    app._ve_luoi_ct()
    chay(3)
    ktra("bấm đúp ảnh lớn (về lưới) -> lưới hiện, cuộn tới tấm đang xem",
         app._che_do_ct == "luoi" and app.luoi.winfo_manager() == "grid"
         and app.luoi.dang_chon == raws[2])
    # bỏ preset
    dp.chon(None)
    ktra("bỏ preset -> xin dừng plugin, lưới đọc ảnh như cũ",
         (JOBS / "request_xempreset_dung.txt").exists() and luoi_anh.NGUON is None
         and preset_lr.chon_hien() is None)
    app._nap_mot_ct = goc_nap
    try:
        app.destroy()
        root.destroy()
    except tk.TclError:
        pass

print()
print("KET QUA:", "TAT CA DAT" if not LOI else f"{len(LOI)} LOI: {LOI}")
sys.exit(1 if LOI else 0)
