#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mô hình màu Lightroom học trên ảnh dựng (mo_hinh_lr.py — 14/10) trên "Lightroom giả".

CHUYỆN ĐANG CANH
    User 14/10: "Cần học về hệ màu và cách bù trừ màu sắc trong Curve, CG để cho ra những
    bức ảnh có màu da và ánh sáng đúng với da đích". Chuỗi một lượt chỉ đúng khi mô hình
    đoán được Lightroom đổi điểm ảnh thế nào. Bài này dùng mo_phong_lr (hành vi BIẾT
    TRƯỚC, cùng kiểu đường dựng với Lightroom): phần học phải tìm lại đúng giả thuyết
    curve / kiểu đường tông / thứ tự, và đoán ảnh để lại trong ngưỡng ĐẠT.
    (Đúng với Lightroom thật hay không: HOC_MAU_LR trên máy user.)

Mục kiểm
    1. biến thể: đủ 28, k+ = Kelvin cao hơn, As Shot lấy AsShot K, curve biến thể đơn điệu;
       thong_so_bien đúng luật HocMauCore (khoá về gốc -> nen -> doi -> dat -> dat_anh)
    2. mô hình rỗng / không đổi thông số -> ảnh giữ nguyên
    3. học: miền curve prophoto22 / kenh, đường tông giữ sắc, curve trước HSL
    4. kiểm định để lại một ảnh: ĐẠT; tổ hợp lệch ≤ ngưỡng
    5. Lightroom giả kiểu đường tông "kenh" -> mô hình chọn "kenh"
    6. JSON / lưu / nạp / học lại từ mẫu đã lưu: dự đoán như nhau
    7. ngoài khoảng đã học -> gắn cờ
    8. bảng preview -> bản xuất
    9. mau_anh: cùng toạ độ trên mọi ảnh dựng, đủ ba loại điểm
    10. yêu cầu plugin: JSON đúng, nen mỗi ảnh; đọc tiến độ / bảng

Chạy:  python test_mo_hinh_lr.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
LOI: list = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


def lech_tb(mh, anh, ten):
    import mo_hinh_lr as m
    e = [m.lech(mh.ap(a["mau"]["px"]["nen"], a["st"]["nen"], a["st"][ten]), a["mau"]["px"][ten],
                a["mau"]["loai"]) for a in anh]
    return {k: float(np.median([x[k] for x in e if k in x])) for k in ("hue", "q", "L", "ab")}


def main() -> int:
    tam = Path(tempfile.mkdtemp(prefix="mo_hinh_lr_"))
    os.environ["AUTOTONE_DATA"] = str(tam / "du_lieu")
    import curve_lr as cl
    import mo_hinh_lr as m
    import mo_phong_lr as sim

    print("1. biến thể")
    cur = {"WhiteBalance": "As Shot", "AsShotTemperature": "5200", "AsShotTint": "4",
           "Exposure2012": "0.3", "ToneCurvePV2012": "0,0,128,132,255,255"}
    ds = [{"path": "G:/B/A.ARW", "cur": cur}]
    b = m.bien_the(ds)
    ten = [x["ten"] for x in b]
    ktra("28 biến thể, mở đầu goc / nen, cuối hai tổ hợp", len(b) == 28 and ten[:2] == ["goc", "nen"]
         and ten[-2:] == ["tohop1", "tohop2"], str(ten))
    kp = next(x for x in b if x["ten"] == "k+")["dat_anh"]["G:/B/A.ARW"]["Temperature"]
    ktra("k+ = Kelvin CAO hơn As Shot (Δmired −25)", kp > 5200 and abs(1e6 / kp - (1e6 / 5200 - 25)) < 1.5, str(kp))
    ktra("nen = WB Custom ở AsShot K / tint", m.nen_cua(cur) == {"WhiteBalance": "Custom", "Temperature": 5200, "Tint": 4})
    cv = next(x for x in b if x["ten"] == "cv_r")["dat_anh"]["G:/B/A.ARW"]["ToneCurvePV2012Red"]
    d = list(zip(cv[0::2], cv[1::2]))
    ktra("cv_r: curve đỏ đơn điệu, nhô ~12 mã ở dải da", np.all(np.diff(cl.spline(d)(np.arange(256.0))) >= -1e-6)
         and 10 <= max(cl.spline(d)(np.arange(256.0)) - np.arange(256.0)) <= 13, str(d))
    st = m.thong_so_bien(cur, {"ten": "x", "doi": {"Exposure2012": 0.7}, "dat": {"ToneCurveName2012": "Custom"},
                               "dat_anh": {"G:/B/A.ARW": {"Tint": 9}}}, "G:/B/A.ARW", set())
    ktra("thong_so_bien: nen -> doi (cộng gốc) -> dat -> dat_anh",
         st["WhiteBalance"] == "Custom" and abs(st["Exposure2012"] - 1.0) < 1e-9 and st["Tint"] == 9
         and st["ToneCurveName2012"] == "Custom" and st["Temperature"] == 5200, str(st))
    ktra("thong_so_bien goc: nguyên trạng", m.thong_so_bien(cur, {"goc": True}, "G:/B/A.ARW", set()) == cur)

    print("2. không đổi -> giữ nguyên")
    px = np.random.default_rng(1).random((400, 3))
    mh0 = m.MoHinh()
    ktra("mô hình rỗng, cu == moi: ảnh giữ nguyên", float(np.abs(mh0.ap(px, cur, cur) - px).max()) < 1e-9)

    print("3. học trên Lightroom giả")
    anh = sim.bo_anh(8)
    mh = m.khop(anh)
    ktra("miền curve = prophoto22 / kenh (như Lightroom giả)",
         mh.curve == {"mien": sim.MIEN_THAT, "kieu": sim.KIEU_THAT}, str(mh.thong_tin.get("curve_sai")))
    ktra("đường tông giữ sắc (rgb_tone)", mh.kieu_g == "rgb_tone", str(mh.thong_tin.get("g_sai")))
    ktra("curve TRƯỚC HSL", mh.thu_tu == "curve_truoc", str(mh.thong_tin.get("thu_tu_sai")))
    ktra("không đổi thông số sau khi học: ảnh giữ nguyên",
         float(np.abs(mh.ap(anh[0]["mau"]["px"]["nen"], anh[0]["st"]["nen"], anh[0]["st"]["nen"])
                      - anh[0]["mau"]["px"]["nen"]).max()) < 1e-6)
    for t in ("ev+", "k-", "o_hue+", "cv_r", "cg_m150", "tohop1", "tohop2"):
        e, e0 = lech_tb(mh, anh, t), m.lech(anh[0]["mau"]["px"]["nen"], anh[0]["mau"]["px"][t], anh[0]["mau"]["loai"])
        ktra(f"{t}: da lệch ≤ 1° / 4%, trung tính ≤ 0.002",
             e["hue"] <= 1.0 and e["q"] <= 0.04 and e["ab"] <= 0.002,
             f"hue {e['hue']:.2f}° q {e['q'] * 100:.1f}% ab {e['ab']:.4f} (không đổi: hue {e0.get('hue', 0):.2f}°)")

    print("4. kiểm định để lại một ảnh")
    kd = m.kiem_dinh(anh)
    ktra("ĐẠT", kd["dat"] is True, json.dumps({k: kd[k] for k in m.TO_HOP if k in kd})[:300])
    ktra("biến thể có đủ chỉ số + p90 + 'không đổi'", all(k in kd["tohop1"] for k in ("hue", "hue_p90", "hue_khong_doi", "n")))
    ktra("so_goc: nen / sau như goc", all(v["max"] < 0.5 for v in m.so_goc(anh).values()), str(m.so_goc(anh)))

    print("5. Lightroom giả đường tông từng kênh")
    cu_tong = sim.TONG_THAT
    sim.TONG_THAT = "kenh"
    try:
        mh_k = m.khop(sim.bo_anh(6, seed=3))
    finally:
        sim.TONG_THAT = cu_tong
    ktra("-> mô hình chọn 'kenh'", mh_k.kieu_g == "kenh", str(mh_k.thong_tin.get("g_sai")))

    print("6. JSON / lưu / nạp")
    mh.khoa = m.khoa_cua("ILCE-7M4", "Adobe Standard", "15.4")
    mh.kiem_dinh, mh.dat = kd, kd["dat"]
    mh2 = m.MoHinh.tu_dict(json.loads(json.dumps(mh.thanh_dict())))
    a0 = anh[1]
    p1 = mh.ap(a0["mau"]["px"]["nen"], a0["st"]["nen"], a0["st"]["tohop1"])
    p2 = mh2.ap(a0["mau"]["px"]["nen"], a0["st"]["nen"], a0["st"]["tohop1"])
    ktra("JSON giữ nguyên dự đoán", float(np.abs(p1 - p2).max()) < 1e-9)
    f = m.luu(mh, anh)
    mh3 = m.nap(mh.khoa)
    ktra("lưu / nạp theo khoá máy__profile__PV", f.is_file() and mh3 is not None and mh3.dat
         and mh.khoa == "ILCE-7M4__Adobe_Standard__15.4", mh.khoa)
    mau = m.nap_mau(mh.khoa)
    ktra("mẫu đã lưu -> học lại như cũ (không cần Lightroom)",
         len(mau) == 8 and float(np.abs(m.khop(mau).ap(a0["mau"]["px"]["nen"], a0["st"]["nen"], a0["st"]["tohop1"])
                                        - p1).max()) < 1e-4)

    print("7. ngoài khoảng đã học")
    base = anh[0]["st"]["nen"]
    ktra("Exposure +1.5 -> ngoại suy", "Exposure2012" in mh.ngoai_pham_vi(base, dict(base, Exposure2012=m._so(base["Exposure2012"]) + 1.5)))
    K = m.wb_cua(base)[0]
    ktra("Δmired 40 -> ngoại suy", "mired" in mh.ngoai_pham_vi(base, dict(base, Temperature=m.mired_doi(K, -40))))
    ktra("đổi nhỏ trong khoảng -> không cờ", mh.ngoai_pham_vi(base, dict(base, Exposure2012=m._so(base["Exposure2012"]) + 0.2)) == [])

    print("8. bảng preview -> bản xuất")
    rng = np.random.default_rng(5)
    xuat = rng.random((20000, 3))
    pv = xuat ** 1.06
    mh.preview_sua = m.khop_preview([(pv, xuat)])
    ktra("preview sửa về như bản xuất (< 1.5 mã)", float(np.abs(mh.sua_preview(pv) - xuat).mean()) * 255 < 1.5,
         f"{float(np.abs(mh.sua_preview(pv) - xuat).mean()) * 255:.2f} mã")

    print("9. mau_anh")
    import mat_na_da as mn
    from PIL import Image
    H, W = 60, 80
    anh_dir = tam / "dung"
    anh_dir.mkdir()
    goc = (np.random.default_rng(2).random((H, W, 3)) * 200 + 20).astype(np.uint8)
    goc[10:30, 20:40] = (128, 128, 128)                 # vùng xám -> trung tính
    cap = {}
    for i, t in enumerate(("goc", "nen", "ev+")):
        f = anh_dir / f"{t}.png"
        Image.fromarray(np.clip(goc.astype(int) + 10 * i, 0, 255).astype(np.uint8)).save(f)
        cap[t] = str(f)
    Image.fromarray(np.zeros((10, 10, 3), np.uint8)).save(anh_dir / "le.png")
    cap["le"] = str(anh_dir / "le.png")
    mk = np.zeros((H, W), bool)
    mk[35:55, 50:75] = True
    that = mn.mat_na
    mn.mat_na = lambda img, r=None, **k: {"da": mk, "n": int(mk.sum()), "mat": [(50, 35, 25, 20)]}
    try:
        mu = m.mau_anh(None, cap)
    finally:
        mn.mat_na = that
    da = mu["loai"] == 0
    ktra("đủ ba loại điểm (da / trung tính / khung)", set(np.unique(mu["loai"]).tolist()) == {0, 1, 2},
         str(np.bincount(mu["loai"])))
    ktra("cùng toạ độ trên mọi ảnh dựng (ev+ = nen + 10 mã)",
         np.allclose(mu["px"]["ev+"] - mu["px"]["nen"], 10 / 255, atol=1.01 / 255)
         or float(np.median(mu["px"]["ev+"] - mu["px"]["nen"])) * 255 > 9)
    ktra("ảnh dựng khác cỡ -> bỏ, không làm hỏng", "le" not in mu["px"] and da.sum() == mk.sum())

    print("10. yêu cầu plugin")
    jobs = tam / "jobs"
    req = m.yeu_cau(tam / "ra", ds, b, job_dir=jobs, ma="m1")
    j = json.loads(req.read_text(encoding="utf-8"))
    ktra("request_hocmau.txt: JSON, nen mỗi ảnh, đủ biến thể",
         j["id"] == "m1" and j["anh"][0]["nen"]["WhiteBalance"] == "Custom" and len(j["bien"]) == 28)
    (jobs / m.TEN_TIEN_DO).write_text("id=m1\ntrang_thai=dang_chay\nxong=12\ntong=58\n", encoding="utf-8")
    (jobs / m.TEN_BANG).write_text("bien\tpath\tjpg\nnen\tG:/B/A.ARW\tC:/ra/nen/A.jpg\n", encoding="utf-8")
    ktra("đọc tiến độ / bảng", m.tien_do(jobs).get("xong") == 12
         and m.bang_anh(jobs) == {"G:/B/A.ARW": {"nen": "C:/ra/nen/A.jpg"}})

    print(f"\n{len(LOI)} LOI" if LOI else "\nTAT CA DAT")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
