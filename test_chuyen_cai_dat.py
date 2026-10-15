#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chuyển cài đặt sang máy khác (chuyen_cai_dat.py — 15/10).

  1. xuất: chỉ danh sách cho phép, lọc khoá (máy / thư mục / luồng không đi), KHÔNG BAO GIỜ
     có khoa.json / may.txt / phan_tich / cache; mẫu da bỏ _theo_buoi; mô hình bỏ _st / npz
  2. nhập vào máy trống: đủ file, khoa.json của máy mới không bị đụng
  3. gộp vào máy đang có: mẫu da theo tên, JSON chỉ đè khoá cho phép, mô hình ĐẠT thắng,
     wb_may theo (máy, buổi)
  4. sao lưu trước khi nhập + khôi phục (file chưa từng có -> xoá)
  5. gói độc: '..', đường tuyệt đối, file lạ, sha256 sai, không phải gói của app -> từ chối,
     chưa đụng gì

    python3 test_chuyen_cai_dat.py
"""
import hashlib
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

TAM = Path(tempfile.mkdtemp(prefix="chuyen_cai_dat_"))
os.environ["AUTOTONE_DATA"] = str(TAM / "may_cu")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import chuyen_cai_dat as cc  # noqa: E402

LOI = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


def ghi(goc: Path, rel: str, d):
    f = goc / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(d, ensure_ascii=False) if not isinstance(d, str) else d, encoding="utf-8")


def doc(goc: Path, rel: str):
    return json.loads((goc / rel).read_text(encoding="utf-8"))


cu = TAM / "may_cu"
ghi(cu, "mau_da.json", {"Cưới": {"trong": [1, 2, 3]}, "_cuoi": "Cưới", "_theo_buoi": {"G:\\X": "Cưới"}})
ghi(cu, "gu.json", {"face_target_ev": -0.9})
ghi(cu, "retouch.json", {"muc": {"mun": 50}, "che_do": "nhanh", "may": "RTX 4090", "luong": 8,
                         "vao": "G:/in", "ra": "G:/out", "chat_luong_ra": 95})
ghi(cu, "xuat.json", {"chat": 92, "thu_muc": "G:/xuat", "an_toan_cpu": True, "preset": "Cưới"})
ghi(cu, "preset_xem.json", {"uuid": "U1", "ten": "Film", "nhom": "SAY", "thu_muc": "C:/x"})
ghi(cu, "luoi_xem.json", {"mau_mot_luot": True, "co_o": 3, "thu_muc_da_mo": ["G:/a"]})
ghi(cu, "wb_may.json", {"may": {"ILCE-9M3": [{"buoi": "g:/a", "lech": 5.0, "n": 4, "luc": "2026-10-01"}]}})
ghi(cu, "khoa.json", {"key": "BI-MAT"})
ghi(cu, "khoa.json.bak", {"key": "BI-MAT"})
ghi(cu, "may.txt", "MAY-CU")
ghi(cu, "phan_tich/x.pkl", "pkl")
ghi(cu, "retouch_preset/Cuoi.json", {"mun": 60})
ghi(cu, "mo_hinh_lr/SIM__P__15.4.json", {"khoa": "SIM__P__15.4", "dat": True, "thong_tin": {"ngay": "2026-10-10"}})
ghi(cu, "mo_hinh_lr/SIM__P__15.4_st.json", [1])
ghi(cu, "mo_hinh_lr/du_doan_2709.json", {})
(cu / "mo_hinh_lr/SIM__P__15.4_mau.npz").write_bytes(b"npz")

print("1. xuất")
goi = TAM / "goi.atcaidat.zip"
kq = cc.xuat(goi)
with zipfile.ZipFile(goi) as z:
    ten = sorted(z.namelist())
    mf = json.loads(z.read("manifest.json"))
    ret = json.loads(z.read("du_lieu/retouch.json"))
    xu = json.loads(z.read("du_lieu/xuat.json"))
    md = json.loads(z.read("du_lieu/mau_da.json"))
ktra("không bao giờ có khoa.json / may.txt / phan_tich", not any(
    "khoa.json" in t or "may.txt" in t or "phan_tich" in t for t in ten), " ".join(ten))
ktra("đủ file cho phép", {"du_lieu/" + r for r in ("mau_da.json", "gu.json", "retouch.json", "xuat.json",
                                                   "preset_xem.json", "luoi_xem.json", "wb_may.json",
                                                   "retouch_preset/Cuoi.json", "mo_hinh_lr/SIM__P__15.4.json")}
     <= set(ten))
ktra("mô hình: bỏ _st / du_doan / mẫu npz (mặc định)", not any(
    t.endswith("_st.json") or "du_doan" in t or t.endswith(".npz") for t in ten))
ktra("retouch.json bỏ máy / luồng / thư mục, giữ mức + chất lượng",
     ret == {"muc": {"mun": 50}, "che_do": "nhanh", "chat_luong_ra": 95}, str(ret))
ktra("xuat.json bỏ thư mục / an_toan_cpu", xu == {"chat": 92, "preset": "Cưới"}, str(xu))
ktra("mẫu da bỏ _theo_buoi", "_theo_buoi" not in md and "Cưới" in md)
ktra("manifest: kiểu + sha256 từng file", mf["kieu"] == cc.KIEU and set(mf["tep"]) == {
    t[len("du_lieu/"):] for t in ten if t.startswith("du_lieu/")})
cc.xuat(TAM / "goi_mau.zip", kem_mau=True)
with zipfile.ZipFile(TAM / "goi_mau.zip") as z:
    ktra("kem_mau=True -> có mẫu npz", "du_lieu/mo_hinh_lr/SIM__P__15.4_mau.npz" in z.namelist())

print("2. nhập vào máy trống")
moi = TAM / "may_moi"
os.environ["AUTOTONE_DATA"] = str(moi)
ghi(moi, "khoa.json", {"key": "KEY-MAY-MOI"})
kq = cc.nhap(goi)
ktra("đủ file", (moi / "retouch_preset/Cuoi.json").is_file() and doc(moi, "gu.json") == {"face_target_ev": -0.9}
     and doc(moi, "mo_hinh_lr/SIM__P__15.4.json")["dat"], str(kq["doi"]))
ktra("khoa.json của máy mới nguyên vẹn, không có may.txt", doc(moi, "khoa.json") == {"key": "KEY-MAY-MOI"}
     and not (moi / "may.txt").exists())
ktra("luoi_xem.json chỉ có mau_mot_luot", doc(moi, "luoi_xem.json") == {"mau_mot_luot": True})

print("3. gộp vào máy đang có")
dang = TAM / "may_dang"
os.environ["AUTOTONE_DATA"] = str(dang)
ghi(dang, "mau_da.json", {"Riêng": {"trong": [9]}, "Cưới": {"trong": [0]}, "_theo_buoi": {"G:\\Y": "Riêng"}})
ghi(dang, "retouch.json", {"muc": {"mun": 10}, "may": "GTX 1060", "luong": 2, "vao": "D:/in"})
ghi(dang, "luoi_xem.json", {"co_o": 5, "ngon_ngu": "en"})
ghi(dang, "mo_hinh_lr/SIM__P__15.4.json", {"khoa": "SIM__P__15.4", "dat": False, "thong_tin": {"ngay": "2026-10-14"}})
ghi(dang, "wb_may.json", {"may": {"ILCE-9M3": [{"buoi": "g:/b", "lech": 7.0, "n": 5, "luc": "2026-10-05"}]}})
cc.nhap(goi)
md = doc(dang, "mau_da.json")
ktra("mẫu da: giữ mẫu riêng + _theo_buoi của máy này, trùng tên lấy của gói",
     md["Riêng"] == {"trong": [9]} and md["Cưới"] == {"trong": [1, 2, 3]} and md["_theo_buoi"] == {"G:\\Y": "Riêng"})
r = doc(dang, "retouch.json")
ktra("retouch.json: mức theo gói, máy / luồng / thư mục của máy này giữ nguyên",
     r["muc"] == {"mun": 50} and r["may"] == "GTX 1060" and r["luong"] == 2 and r["vao"] == "D:/in", str(r))
ktra("luoi_xem.json: thêm mau_mot_luot, giữ khoá khác", doc(dang, "luoi_xem.json") == {
    "co_o": 5, "ngon_ngu": "en", "mau_mot_luot": True})
ktra("mô hình: ĐẠT (gói) thắng CHƯA ĐẠT (máy này) dù cũ hơn", doc(dang, "mo_hinh_lr/SIM__P__15.4.json")["dat"])
w = doc(dang, "wb_may.json")["may"]["ILCE-9M3"]
ktra("wb_may: gộp theo (máy, buổi)", sorted(x["buoi"] for x in w) == ["g:/a", "g:/b"])
ghi(dang, "mo_hinh_lr/SIM__P__15.4.json", {"khoa": "SIM__P__15.4", "dat": True, "thong_tin": {"ngay": "2026-10-20"}})
cc.nhap(goi)
ktra("mô hình cùng ĐẠT: bản mới hơn (máy này) giữ", doc(dang, "mo_hinh_lr/SIM__P__15.4.json")["thong_tin"]["ngay"]
     == "2026-10-20")

print("4. sao lưu + khôi phục")
ds = cc.ds_sao_luu()
ktra("mỗi lần nhập một bản sao lưu", len(ds) == 2, str([p.name for p in ds]))
kq = cc.khoi_phuc(ds[-1])                                  # bản trước lần nhập ĐẦU
ktra("khôi phục: file về như trước", doc(dang, "retouch.json")["muc"] == {"mun": 10}
     and doc(dang, "mau_da.json")["Cưới"] == {"trong": [0]}, str(kq))
ktra("…file chưa từng có trước lần nhập -> xoá", not (dang / "gu.json").exists()
     and not (dang / "retouch_preset/Cuoi.json").exists(), str(kq["xoa"]))
os.environ["AUTOTONE_DATA"] = str(TAM / "may_trong")
try:
    cc.khoi_phuc()
    ktra("chưa nhập lần nào -> LoiGoi", False)
except cc.LoiGoi:
    ktra("chưa nhập lần nào -> LoiGoi", True)

print("5. gói độc")
dich = TAM / "may_doc"
os.environ["AUTOTONE_DATA"] = str(dich)
ghi(dich, "khoa.json", {"key": "K"})


def goi_doc(ten, tep: dict, mf_sua=None):
    f = TAM / ten
    mf = {"kieu": cc.KIEU, "phien_ban_goi": 1, "tep": {k.split("du_lieu/", 1)[-1]: hashlib.sha256(v).hexdigest()
                                                       for k, v in tep.items()}}
    if mf_sua:
        mf_sua(mf)
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("manifest.json", json.dumps(mf))
        for k, v in tep.items():
            z.writestr(k, v)
    return f


for ten, f in (
        ("đường dẫn '..'", goi_doc("a.zip", {"du_lieu/../khoa.json": b'{"key":"X"}'})),
        ("ghi đè khoa.json", goi_doc("b.zip", {"du_lieu/khoa.json": b'{"key":"X"}'})),
        ("file ngoài du_lieu/", goi_doc("c.zip", {"chay.py": b"print(1)"})),
        ("file lạ (.py trong retouch_preset)", goi_doc("d.zip", {"du_lieu/retouch_preset/x.py": b"1"})),
        ("sha256 sai", goi_doc("e.zip", {"du_lieu/gu.json": b"{}"},
                               lambda mf: mf["tep"].__setitem__("gu.json", "0" * 64))),
        ("không phải gói của app", goi_doc("f.zip", {"du_lieu/gu.json": b"{}"},
                                           lambda mf: mf.__setitem__("kieu", "khac"))),
        ("gói bản mới hơn", goi_doc("g.zip", {"du_lieu/gu.json": b"{}"},
                                    lambda mf: mf.__setitem__("phien_ban_goi", 99)))):
    try:
        cc.nhap(f)
        ktra(f"{ten} -> từ chối", False)
    except cc.LoiGoi as ex:
        ktra(f"{ten} -> từ chối", True, str(ex))
(TAM / "rac.zip").write_bytes(b"khong phai zip")
try:
    cc.nhap(TAM / "rac.zip")
    ktra("file không phải zip -> từ chối", False)
except cc.LoiGoi:
    ktra("file không phải zip -> từ chối", True)
ktra("gói độc không đụng gì (khoa.json nguyên, không sao lưu)", doc(dich, "khoa.json") == {"key": "K"}
     and not cc.ds_sao_luu() and not (dich / "gu.json").exists())
ktra("tom_tat", cc.tom_tat(["mau_da.json", "mo_hinh_lr/A.json", "retouch_preset/B.json"])
     == "mẫu màu da, 1 mô hình màu Lightroom, 1 preset retouch")

print()
print("TẤT CẢ ĐẠT" if not LOI else f"{len(LOI)} LỖI: " + "; ".join(LOI))
sys.exit(1 if LOI else 0)
