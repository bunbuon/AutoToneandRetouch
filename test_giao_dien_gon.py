#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Giao diện gọn + khung kiểu Evoto (3/10) — mở ỨNG DỤNG THẬT và bấm thử.

USER YÊU CẦU
    Chiều 3/10: "Dọn dẹp lại 1 chút ở giao diện. Tôi thấy các bước Tổng quan,
    3 4 6 7 gần như không cần tới. Đưa phần Ghi và đẩy vào Lightroom lên giao
    diện của Phân Tích. Chuyển giao diện của phần chọn các option của phân
    tích thu gọn theo các nhóm. Các tính năng có thông số thêm option thành
    thanh trượt. Các chú thích hiện tại sẽ để vào bên trong biểu tượng dấu ?
    ở bên cạnh mỗi tính năng. Khi di chuột vào thì mới hiển thị chú thích để
    làm gọn giao diện."
    Tối 3/10: "bỏ luôn phần giao diện này vì k cần dùng tới. Sau khi bỏ. thì
    có thể tham khảo giao diện của Evoto để thiết kế lại toàn bộ giao diện của
    ứng dụng" — chọn "Lưới ảnh như Evoto", màu nhấn vàng.

MỤC KIỂM
    1. Khung Evoto: không còn cột trái; mở app là vào lưới ảnh; thanh công cụ
       có buổi ▾ · lần gửi · Phân tích · Ghi · ⋯; cột mô-đun đổi Cân tone /
       Retouch; Duyệt nhanh mở từ ⋯, nút ← đưa về.
    2. Nút "2 · Ghi và đẩy vào Lightroom" trên thanh công cụ, và cả app chỉ có
       MỘT widget / mục menu gọi do_apply. Dòng lần gửi ngay cạnh nút Ghi, chỉ
       nói về job của ĐÚNG buổi đang mở. Nút vàng là việc kế tiếp.
    2b. Dải báo của buổi + lưới: thiếu .xmp thì dải đỏ, nút sửa, lưới vẫn hiện
       đủ RAW và đánh dấu tấm thiếu; thanh công cụ KHÔNG phình. Thanh trạng
       thái và dòng lần gửi luôn MỘT dòng, câu dài cắt "…" và rê chuột hiện đủ.
    3. Bảy nhóm tuỳ chọn, ĐÓNG sẵn, mỗi nhóm một dòng tóm tắt; bấm đầu nhóm
       (chuột hoặc Enter) là mở / đóng; tóm tắt chạy theo giá trị.
    4. Thanh trượt: kéo thì số nhảy theo BƯỚC; gõ số thì thanh chạy theo; số
       ngoài khoảng thanh vẫn giữ nguyên trong ô; kéo KHÔNG tính lại kế hoạch,
       thả chuột mới tính, và thả mà số không đổi thì không tính; phím mũi tên
       tính một lần sau khi ngừng bấm; khoá / mở theo chế độ như ô số cũ.
    5. Dấu ?: rê chuột vào hiện chú thích, rời ra thì tắt; MỌI dòng chú thích
       cũ đều còn nguyên trong một dấu ? nào đó.
    6. Cảnh báo im lặng (plugin chết) hiện ở dải trên cùng — Tổng quan đã ẩn.

Chạy:  python test_giao_dien_gon.py        (Linux: xvfb-run -a python3.12 ...)
"""
from __future__ import annotations

import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

LOI: list[str] = []


def ktra(ten: str, dieu: bool, mo: str = "") -> None:
    if dieu:
        print(f"  {ten:<58} {mo or 'đạt'}")
    else:
        LOI.append(f"{ten}: {mo}")


def di_khap(w, ra):
    ra.append(w)
    for c in w.winfo_children():
        di_khap(c, ra)


def la_con_cua(w, cha) -> bool:
    while w is not None:
        if w is cha:
            return True
        w = w.master
    return False


def raw_gia(p: Path, mau=(120, 140, 170)) -> Path:
    """File "RAW" giả: khung TIFF có JPEG nhúng (thẻ 0x0201/0x0202) — đủ để
    at.anh_nho() đọc ra ảnh nhỏ, khỏi mang RAW thật vào bài kiểm."""
    import io
    import struct
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (480, 320), mau).save(b, "JPEG", quality=80)
    j = b.getvalue()
    ent = [(0x0112, 3, 1, 1), (0x0201, 4, 1, 0), (0x0202, 4, 1, len(j))]
    off = 8 + 2 + len(ent) * 12 + 4 + 16
    ent[1] = (0x0201, 4, 1, off)
    d = bytearray(b"II*\x00" + struct.pack("<I", 8) + struct.pack("<H", len(ent)))
    for tag, typ, cnt, val in ent:
        d += (struct.pack("<HHIHH", tag, typ, cnt, val, 0) if typ == 3
              else struct.pack("<HHII", tag, typ, cnt, val))
    d += struct.pack("<I", 0)
    d += b"\x00" * (off - len(d)) + j + b"\x00" * 4096
    p.write_bytes(bytes(d))
    return p


XMP_GIA = ('<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org'
           '/1999/02/22-rdf-syntax-ns#"><rdf:Description rdf:about="" xmlns:crs="'
           'http://ns.adobe.com/camera-raw-settings/1.0/" crs:Exposure2012="+0.00"/>'
           '</rdf:RDF></x:xmpmeta>')


#[[ Chu thich CU — lay nguyen van tu _build_options ban truoc 3/10 (chu phu in
#   san duoi tung tinh nang). Moi dong phai con NGUYEN VAN trong mot dau ?;
#   rot mot dong la mat thong tin ma user chi bao "doi cho", khong bao "bo". ]]
def chu_thich_cu(at) -> list[str]:
    ev = at.DEFAULTS.get("ev_ngoai_troi")
    bu = float(at.DEFAULTS.get("bu_sang_su_kien", 0.3))
    dich = float(at.DEFAULTS["face_target_ev"])
    return [
        #[[ 4/10: o "Mat sang toi muc" AN, moc -1.19 -> -1.00 (user). Hai dong
        #   duoi doi CHU vi su that da doi: cau cu "−1.19 lấy từ ảnh anh chấm
        #   tay" sai so, "mức đích ở trên" chi vao mot o khong con thay. Van
        #   kiem tung chu — khong bot dong nao. ]]
        "Mức sáng ĐÍCH của da mặt (EV log2, càng âm càng tối). Mặc định "
        f"{dich:+.2f}. Chỉ dùng ở chế độ “Đưa mặt về mức sáng chuẩn” và “Trộn”.",
        "Chỉ ở chế độ “Trộn”. 0 = theo trung vị cảnh, 1 = theo mức sáng chuẩn.",
        f"Ngưỡng EV100 {ev} · tính từ ISO + tốc + khẩu, không phải ISO không",
        "Kể cả ảnh chụp trong nhà bạt hay dưới mái che ban ngày",
        "Hội trường, sân khấu, hoặc chụp sau khi trời tối",
        "Trần cho chiều DÌM TỐI. Đo ra phải dìm 1.8 EV mà đặt 1.00 thì chỉ dìm "
        "1.00. Chiều kéo sáng do ô dưới quyết định.",
        "Trần cho chiều KÉO SÁNG, để riêng vì hai chiều không đối xứng: dìm quá "
        "tay chỉ mất công, kéo sáng thì cứu được ảnh ngược sáng hay chụp trước "
        "màn LED. Phần chống cháy sáng vẫn gác.",
        "Nhân vào mức chỉnh trước khi kẹp trần. 1.0 = đủ như đo được, 0.7 = dè "
        "dặt, 1.2 = mạnh tay.",
        "Ngăn làm cháy thêm — không gỡ được chỗ đã cháy sẵn",
        "Nghỉ lâu mà vẫn đứng nguyên một phông thì không tính là cảnh mới",
        "Chụp liên tiếp — giữ 2 tấm đẹp nhất mỗi pose, ảnh loại gắn 1 sao",
        "1 người hoặc nhóm 2–4; ảnh tập thể đông người bỏ qua. Đo luôn khi phân "
        "tích, chậm thêm ~0.8s/ảnh",
        f"EV, cộng sau chống cháy. Cưới 0 · Sự kiện {bu:+.2f}. Ảnh không có mặt "
        "giữ nguyên.",
        # "nghỉ quá [5] phút thì coi là cảnh mới" — nhãn đổi thành "nghỉ quá
        # (phút)" nên câu viết lại cho đứng một mình; ý giữ nguyên:
        "thì coi là cảnh mới",
    ]


def main() -> int:
    try:
        import tkinter as tk
        import autotone as at
        import autotone_gui as ag
        import giao_dien as gd
        root = tk.Tk()
    except Exception as ex:                                  # noqa: BLE001
        print(f"  (bỏ qua: không mở được Tk — {ex.__class__.__name__}: {ex})")
        return 0

    # Lớp phủ bản quyền che mất giao diện — bài này kiểm giao diện, không kiểm
    # bản quyền (đã có kiem_ban_quyen riêng).
    ag.bq.kiem = lambda: {"co_phep": True, "con_lai": timedelta(days=300),
                          "nhac": "", "goi": "1 năm", "may": "TEST01",
                          "het_han": False, "ly_do": ""}
    root.geometry("1660x940+0+0")
    gd.dat_theme(root)
    app = ag.App(root)
    app.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    def chay(n=6, ngu=0.0):
        for _ in range(n):
            root.update_idletasks()
            root.update()
            if ngu:
                time.sleep(ngu)

    chay(8)
    job_cu = at.LR_JOB_DIR
    tam = Path(tempfile.mkdtemp(prefix="gon_"))
    try:
        _kiem(app, root, chay, tk, at, ag, gd, tam)
    finally:
        at.LR_JOB_DIR = job_cu
        try:
            root.destroy()
        except tk.TclError:
            pass

    print()
    if LOI:
        for m in LOI:
            print("  [!] " + m)
        print(f"{len(LOI)} LỖI")
        return 1
    print("TẤT CẢ ĐẠT")
    return 0


def _kiem(app, root, chay, tk, at, ag, gd, tam: Path) -> None:
    # ------------------------------------------------ 0. nguồn mặc định
    #[[ User 4/10: "Mặc định sẽ chỉ dùng Lightroom Catalog." Hoi NGAY khi mo
    #   app, truoc moi thao tac — muc 2b doi sang sidecar co y. Sidecar van
    #   phai con trong menu (may chua cai plugin). ]]
    nhan_cat = next(nhan for nhan, ma in ag.SOURCES if ma == "catalog")
    menu_nguon = []
    for i in range((app.menu_buoi.index("end") or 0) + 1):
        if app.menu_buoi.type(i) == "radiobutton":
            menu_nguon.append(str(app.menu_buoi.entrycget(i, "label")).strip())
    ktra("mở app lên là nguồn Lightroom catalog, Sidecar vẫn chọn được",
         app.source_value() == "catalog" and app.v_source.get() == nhan_cat
         and any(m.startswith("Sidecar") for m in menu_nguon)
         and any(m.startswith("Lightroom catalog") for m in menu_nguon),
         f"“{app.v_source.get()[:40]}” · menu {len(menu_nguon)} nguồn")

    # ------------------------------------------------ 1. khung kiểu Evoto
    ktra("mở app lên là vào trang chính, lưới ảnh là mặc định",
         app.khau_dang == "phan_tich" and app.khung_ngoai["phan_tich"].winfo_ismapped()
         and app.v_xem.get() == "luoi" and app.khung_luoi.winfo_ismapped()
         and not app.khung_bang.winfo_ismapped(), f"đang ở “{app.khau_dang}”")
    ds = []
    di_khap(root, ds)
    #[[ Hoi thang cay widget, khong hoi bien: con mot Ray nao do (du khong gan
    #   vao self.ray) la cot trai van dang chiem cho. ]]
    ktra("không còn cột trái bảy khâu",
         not hasattr(app, "ray") and not any(type(w).__name__ == "Ray" for w in ds),
         "bỏ hẳn theo yêu cầu tối 3/10")
    ktra("cột mô-đun: Cân tone · Retouch",
         list(app.thanh_md.nut) == ["tone", "retouch"] and app.thanh_md.dang == "tone",
         " · ".join(app.thanh_md.nut))
    cc = app.thanh_cc
    tren = {"nút buổi": app.nut_buoi, "lần gửi": app.lbl_job,
            "Phân tích": app.btn_analyze, "Ghi": app.btn_ghi3, "⋯": app.btn_them}
    vang = [k for k, w in tren.items()
            if not (la_con_cua(w, cc) and w.winfo_ismapped())]
    ktra("thanh công cụ: buổi ▾ · lần gửi · Phân tích · Ghi · ⋯", not vang,
         f"thiếu {vang}" if vang else "một hàng, như thanh trên của Evoto")
    ktra("hạn dùng luôn hiện ở thanh trạng thái",
         la_con_cua(app.lbl_han, app.thanh_tt) and app.lbl_han.winfo_ismapped()
         and bool(app.lbl_han.cget("text")), app.lbl_han.cget("text")[:40])
    #[[ Bam BIEU TUONG THAT (su kien chuot tren canvas), khong goi ham — noi
    #   sai su kien la bam mai khong an ma goi ham thi van "dat". ]]
    #[[ Toi 3/10 Retouch cung theo dang Evoto (user: "dua ca phan Retouch
    #   thay doi luon"): MOI mo-dun mot bang dieu khien + mot bo nut tren thanh
    #   cong cu. Doi mo-dun la doi CA HAI — sot mot cai la bam "Chay" o mo-dun
    #   nay chay viec cua mo-dun kia. ]]
    app.thanh_md.nut["retouch"].event_generate("<ButtonRelease-1>", x=5, y=5)
    chay(4)
    rt_win = getattr(app, "_retouch_win", None)
    sang_rt = (app.khau_dang == "retouch" and app.thanh_md.dang == "retouch"
               and app.khung_ngoai["retouch"].winfo_ismapped()
               and not app.cuon_phai.winfo_ismapped()
               and not app.cc_phai.winfo_ismapped() and app.cc_phai_rt.winfo_ismapped()
               and (rt_win is None or (app.cuon_phai_rt.winfo_ismapped()
                                       and rt_win.btn_run.winfo_ismapped())))
    app.thanh_md.nut["tone"].event_generate("<ButtonRelease-1>", x=5, y=5)
    chay(4)
    ktra("bấm biểu tượng là đổi mô-đun: bảng điều khiển + nút theo mô-đun",
         sang_rt and app.khau_dang == "phan_tich" and app.cuon_phai.winfo_ismapped()
         and not app.cuon_phai_rt.winfo_ismapped() and app.cc_phai.winfo_ismapped()
         and not app.cc_phai_rt.winfo_ismapped(),
         "Retouch không mang bảng / nút của Cân tone, và ngược lại")
    m = app.menu_them
    i_duyet = next((i for i in range(m.index("end") + 1) if m.type(i) == "command"
                    and "Duyệt nhanh" in m.entrycget(i, "label")), None)
    if i_duyet is not None:
        m.invoke(i_duyet)
        chay(3)
    ktra("Duyệt nhanh mở được từ menu ⋯, tiêu đề là tên trang",
         i_duyet is not None and app.khau_dang == "day"
         and app.khung_ngoai["day"].winfo_ismapped() and app.dau_phu.winfo_ismapped()
         and app.lbl_khau.cget("text") == dict(ag.KHAU)["day"],
         app.lbl_khau.cget("text"))
    app.nut_ve.invoke()
    chay(3)
    ktra("nút ← đưa về trang chính", app.khau_dang == "phan_tich"
         and app.dau_chinh.winfo_ismapped() and not app.dau_phu.winfo_ismapped(),
         app.nut_ve.cget("text"))

    # ------------------------------------------------ 2. nút Ghi
    ktra("nút Ghi trên thanh công cụ, nhìn thấy được",
         la_con_cua(app.btn_ghi3, cc) and app.btn_ghi3.winfo_ismapped()
         and "Ghi" in str(app.btn_ghi3.cget("text")), str(app.btn_ghi3.cget("text")))
    #[[ Dong lan gui NGAY CANH nut Ghi: cung mot hang, nam ben trai cac nut —
    #   bam gui xong la thay "dang cho / da ap" ngay canh cho vua bam. ]]
    lj, bt = app.lbl_job, app.btn_analyze
    giua_j = lj.winfo_rooty() + lj.winfo_height() / 2
    giua_b = bt.winfo_rooty() + bt.winfo_height() / 2
    ktra("dòng lần gửi cạnh nút Ghi, cùng một hàng",
         lj.winfo_rootx() + lj.winfo_width() <= bt.winfo_rootx() + 2
         and abs(giua_j - giua_b) < bt.winfo_height() / 2,
         "bên trái “1 · Phân tích”")
    #[[ Dem theo LENH THAT cua widget (ca nut ve tay — cget("command") tra ve
    #   ham Python — lan nut tk/ttk va muc menu, von dang ky thanh lenh Tcl ten
    #   "<so>do_apply"). Dung moi khau dung cham truoc khi dem: hai nut mot
    #   viec la _set_busy phai nho khoa ca hai. ]]
    for ma in list(app._khung_lam):
        app._chon_khau(ma)
    app._chon_khau("phan_tich")
    chay(3)
    ds = []
    di_khap(root, ds)
    goi_ghi = []
    for w in ds:
        try:
            lenh = w.cget("command")
        except (tk.TclError, ValueError, AttributeError):
            lenh = None
        if lenh is not None and (lenh == app.do_apply or str(lenh).endswith("do_apply")):
            goi_ghi.append(w)
        if w.winfo_class() == "Menu":
            cuoi = w.index("end")
            for i in range(0 if cuoi is None else cuoi + 1):
                try:
                    if str(w.entrycget(i, "command")).endswith("do_apply"):
                        goi_ghi.append((w, i))
                except tk.TclError:
                    pass
    ktra("cả app chỉ có MỘT widget gọi do_apply",
         goi_ghi == [app.btn_ghi3], f"{len(goi_ghi)} widget / mục menu")

    # ---- lbl_job chỉ nói về job của đúng buổi
    at.LR_JOB_DIR = tam / "jobs"
    at.LR_JOB_DIR.mkdir()
    buoi = tam / "G0310"
    buoi.mkdir()
    (at.LR_JOB_DIR / "apply_20261003_100000_Hiu.done").write_text("x\n", encoding="utf-8")
    app.v_folder.set(str(buoi))
    app.refresh_job_state()
    chu1 = app.lbl_job.cget("text")
    (at.LR_JOB_DIR / "apply_20261003_110000_G0310.done").write_text("x\n", encoding="utf-8")
    app.refresh_job_state()
    chu2 = app.lbl_job.cget("text")
    ktra("trạng thái lần gửi không lấy job của buổi khác",
         "G0310" in chu1 and "chưa gửi" in chu1 and "Hiu" not in chu1,
         chu1[:60])
    ktra("có job của buổi này thì báo đúng job đó",
         "Lần gửi gần nhất" in chu2 and "G0310" in chu2, chu2[:60])
    app.scan_folder()
    chay(3)
    ktra("chọn buổi xong nút buổi đổi tên ngay", app.nut_buoi.cget("text") == "G0310",
         app.nut_buoi.cget("text"))

    # ------------------------------------------------ 2b. dải báo · lưới · một dòng
    #[[ Buoi that: 6 RAW, 2 tam chua co .xmp, nguon sidecar. Truoc 3/10 toi:
    #   cau "⚠ Chi 4/6 anh co sidecar…" nam giua thanh cong cu, xuong 2-3 dong
    #   chu do keo cao ca thanh; va luoi trong tron "Khong tim thay file RAW
    #   nao" khi CA buoi thieu .xmp. ]]
    buoi2 = tam / "G0311"
    buoi2.mkdir()
    for i in range(6):
        raw_gia(buoi2 / f"SAY0{i}.ARW", mau=(60 + 30 * i, 120, 160))
        if i not in (2, 4):
            (buoi2 / f"SAY0{i}.xmp").write_text(XMP_GIA, encoding="utf-8")
    app.v_source.set(ag.SOURCES[0][0])
    app.v_folder.set("")
    app.scan_folder()
    chay(3)
    cao_cc = cc.winfo_height()
    vang_luc_trong = (app.btn_analyze.cget("kieu"), app.btn_ghi3.cget("kieu"))
    app.v_folder.set(str(buoi2))
    app.scan_folder()
    chay(6)
    dq = app.dai_quet
    ktra("thiếu .xmp: dải báo đỏ trên lưới, có nút sửa",
         dq.dang_hien() and dq.muc == "loi" and app.btn_fix.winfo_ismapped()
         and "sidecar" in app.lbl_scan.cget("text"),
         app.lbl_scan.cget("text")[:50])
    ktra("thanh công cụ không phình vì câu báo dài",
         abs(cc.winfo_height() - cao_cc) <= 1, f"{cao_cc} → {cc.winfo_height()} px")
    thieu = sorted(Path(o["path"]).name for o in app.luoi.ds if o.get("bo") == "thiếu .xmp")
    ktra("lưới vẫn hiện đủ 6 RAW, đánh dấu đúng 2 tấm thiếu .xmp",
         len(app.luoi.ds) == 6 and thieu == ["SAY02.ARW", "SAY04.ARW"]
         and app.lbl_tong.cget("text").startswith("6 ảnh RAW"),
         f"{len(app.luoi.ds)} ô · thiếu {thieu} · “{app.lbl_tong.cget('text')}”")
    ktra("nút vàng là việc kế tiếp",
         vang_luc_trong == ("phu", "phu") and app.btn_analyze.cget("kieu") == "chinh"
         and app.btn_ghi3.cget("kieu") == "phu",
         "chưa có buổi: không nút nào vàng · có ảnh: Phân tích vàng")
    app.items = [{"path": "gia"}]
    app._set_busy(False)
    vang_co_kq = (app.btn_analyze.cget("kieu"), app.btn_ghi3.cget("kieu"))
    app.items = []
    app._set_busy(False)
    ktra("có kết quả thì nút Ghi vàng, Phân tích lùi về nút phụ",
         vang_co_kq == ("phu", "chinh"), f"{vang_co_kq}")
    app.thanh_md.nut["retouch"].event_generate("<ButtonRelease-1>", x=5, y=5)
    chay(3)
    an_o_rt = not dq.dang_hien()
    app.thanh_md.nut["tone"].event_generate("<ButtonRelease-1>", x=5, y=5)
    chay(3)
    ktra("Retouch không mang dải báo của Cân tone", an_o_rt and dq.dang_hien(),
         "về Cân tone thì dải hiện lại")
    for i in (2, 4):
        (buoi2 / f"SAY0{i}.xmp").write_text(XMP_GIA, encoding="utf-8")
    app.scan_folder()
    chay(4)
    ktra("đủ .xmp: dải chỉ còn một dòng ổn, hết nút sửa, hết ô bị đánh dấu",
         dq.muc == "xong" and not app.btn_fix.winfo_ismapped()
         and not any(o.get("bo") for o in app.luoi.ds), app.lbl_scan.cget("text")[:50])
    tt_bar = app.thanh_tt
    cao_tt = tt_bar.winfo_height()
    dai = "Đang đo 1400 ảnh · " + "rất dài " * 120 + "· ĐUÔI CÂU"
    app.status(dai)
    app.lbl_job.configure(text="✓ Lần gửi gần nhất · " + "job dài " * 120)
    chay(4)
    ktra("thanh trạng thái và thanh công cụ vẫn MỘT dòng khi câu rất dài",
         abs(tt_bar.winfo_height() - cao_tt) <= 1
         and abs(cc.winfo_height() - cao_cc) <= 1,
         f"trạng thái {cao_tt}→{tt_bar.winfo_height()} · công cụ "
         f"{cao_cc}→{cc.winfo_height()} px")
    #[[ getattr: nhan thuong (khong phai NhanGon) thi khong co dang_cat / goi_y
    #   — bai kiem phai BAO muc nay truot, khong phai chet AttributeError. ]]
    def cat_ma_du(w, mau):
        dc = getattr(w, "dang_cat", None)
        gy = getattr(getattr(w, "goi_y", None), "chu", "")
        return bool(dc and dc()) and mau in gy and mau in str(w.cget("text"))
    ktra("câu bị cắt thì rê chuột hiện đủ, cget vẫn trả câu đủ",
         cat_ma_du(app.lbl_status, "ĐUÔI CÂU") and cat_ma_du(app.lbl_job, "job dài"),
         "không mất chữ nào")
    app.status("")
    app.refresh_job_state()
    app.v_folder.set(str(buoi))

    # ------------------------------------------------ 3. nhóm thu gọn
    nhom = app._nhom_tuy_chon
    ktra("bảy nhóm tuỳ chọn", len(nhom) == 7, " · ".join(n.tieu_de for n in nhom.values()))
    ktra("mở app lên thì nhóm nào cũng đóng, có dòng tóm tắt",
         all(not n.dang_mo and not n.than.winfo_ismapped()
             and n.l_tom.winfo_ismapped() and n.l_tom.cget("text")
             for n in nhom.values()),
         "thu gọn mà không giấu")
    n = nhom["tran"]
    n.dau.event_generate("<Button-1>")
    chay(3)
    mo_chuot = n.dang_mo and n.than.winfo_ismapped() and not n.l_tom.winfo_ismapped()
    n.dau.focus_force()
    chay(2)
    n.dau.event_generate("<Return>")
    chay(3)
    ktra("bấm đầu nhóm là mở, Enter là đóng",
         mo_chuot and not n.dang_mo and not n.than.winfo_ismapped(),
         "chuột và bàn phím đều dùng được")
    app.v_maxev.set("2.50")
    app.v_burst.set(True)
    app.v_gap_on.set(False)
    app.v_scenesig.set(False)
    chay(4)
    ktra("dòng tóm tắt chạy theo giá trị",
         "2.50" in nhom["tran"].l_tom.cget("text")
         and "trùng khung" in nhom["loc"].l_tom.cget("text")
         and nhom["canh"].l_tom.cget("text").startswith("⚠"),
         nhom["canh"].l_tom.cget("text")[:50])
    app.v_maxev.set("1.00")
    app.v_burst.set(False)
    app.v_gap_on.set(True)
    app.v_scenesig.set(True)
    for x in nhom.values():
        x.mo()
    chay(4)

    # ------------------------------------------------ 4. thanh trượt
    #[[ 4/10: o "Mat sang toi muc" da AN (xem 4b) — kiem hanh vi thanh truot
    #   tren "Bu sang ca buoi", thanh nguoi dung thay va keo that. Buoc 0.05,
    #   hai so le. ]]
    dem = []
    tt = app.sp_bu_sang
    tt._khi_xong = lambda: dem.append(1)
    ktra("ô số có thanh trượt", isinstance(tt, gd.ThanhTruot)
         and isinstance(app.sp_gap, gd.ThanhTruot)
         and isinstance(app.sp_blend, gd.ThanhTruot), "Bù sáng · Độ trộn · nghỉ quá")
    app.v_bu_sang.set("-0.50")
    chay(2)
    ktra("gõ số thì thanh chạy theo", abs(tt._dv.get() + 0.5) < 1e-9,
         f"thanh = {tt._dv.get():.2f}")
    tt._bat_dau()
    for v in (-0.8031, 0.1777, 0.2349):
        tt.thanh.set(v)
        chay(1)
    giua = len(dem)
    ktra("kéo thì số nhảy theo bước 0.05, KHÔNG tính lại giữa chừng",
         app.v_bu_sang.get() == "0.25" and giua == 0,
         f"ô = {app.v_bu_sang.get()} · tính lại {giua} lần lúc kéo")
    tt._xong_neu_doi()
    ktra("thả chuột thì tính lại đúng một lần", len(dem) == 1, f"{len(dem)} lần")
    tt._bat_dau()
    tt._xong_neu_doi()
    ktra("bấm rồi thả mà số không đổi thì không tính lại", len(dem) == 1,
         "khỏi mất ~1 giây trên buổi 1000 ảnh")
    ktra("thả chuột / rời ô số đều có nối sự kiện",
         bool(tt.thanh.bind("<ButtonRelease-1>")) and bool(tt.o.bind("<FocusOut>"))
         and bool(tt.o.bind("<Return>")), "ButtonRelease-1 · FocusOut · Return")
    tt._buoc_phim(1)
    tt._buoc_phim(1)
    chay(2)
    sau_phim = app.v_bu_sang.get()
    truoc_hen = len(dem)
    chay(12, 0.05)
    ktra("phím mũi tên: mỗi lần một bước, ngừng bấm mới tính một lần",
         sau_phim == "0.35" and truoc_hen == 1 and len(dem) == 2,
         f"ô = {sau_phim} · tính {len(dem) - 1} lần sau khi ngừng")
    tt._khi_xong = app.refresh_plan
    app.v_bu_sang.set("0.00")
    chay(2)

    # ------------------------------------------------ 4b. "Mặt sáng tới mức" ẩn
    #[[ User 4/10: "Do da co tinh nang bu sang ca buoi nen an di phan Mat sang
    #   toi muc di. Co the set phan mat sang toi muc ve -1.00". Nhom "Cach can
    #   tone" dang MO (vong x.mo() o muc 3) — hoi luon o "Do tron" ngay duoi
    #   co dang hien khong, khong thi "khong thay o Mat sang" la vo nghia.
    #   Moc goc lay qua GU_MAC_DINH: may co gu.json hoc duoc moc khac thi
    #   DEFAULTS mang so cua gu, con so trong code van phai la -1.00. ]]
    nt = nhom["tone"]
    ktra("ô “Mặt sáng tới mức” không còn hiện (nhóm Cách cân tone đang mở)",
         nt.dang_mo and app.sp_blend.winfo_ismapped()
         and not app.sp_target.winfo_ismapped(),
         f"nhóm mở {nt.dang_mo} · Độ trộn {app.sp_blend.winfo_ismapped()} · "
         f"Mặt sáng {app.sp_target.winfo_ismapped()}")
    goc = at.GU_MAC_DINH.get("face_target_ev", at.DEFAULTS["face_target_ev"])
    ktra("mốc mặt sáng trong code là −1.00", abs(float(goc) + 1.0) < 1e-9, f"{goc}")
    moc = f"{float(at.DEFAULTS['face_target_ev']):.2f}"
    cfg = app.read_cfg()
    ktra("ô ẩn mang đúng mốc và phân tích dùng mốc đó",
         app.v_target.get() == moc and abs(cfg["face_target_ev"] - float(moc)) < 1e-9,
         f"ô {app.v_target.get()} · cfg {cfg['face_target_ev']}")
    mat = next(nhan for nhan, ma in ag.METERS if ma == "face")
    khung = next(nhan for nhan, ma in ag.METERS if ma == "average")
    app.v_meter.set(khung)
    app._on_meter_change()
    o_khung = app.v_target.get()
    app.v_meter.set(mat)
    app._on_meter_change()
    chay(3)
    ktra("đổi cách đo rồi đổi lại: mốc theo đúng thang, về lại mốc mặt",
         o_khung == f"{float(at.DEFAULTS['target_ev']):.2f}"
         and app.v_target.get() == moc,
         f"cả khung {o_khung} · mặt {app.v_target.get()}")
    ktra("dòng tóm tắt Cách cân tone không nói mức đích (ô đã ẩn)",
         "đích" not in nt.l_tom.cget("text") and moc not in nt.l_tom.cget("text"),
         nt.l_tom.cget("text")[:60])
    ktra("dấu ? của Bù sáng cả buổi nói mốc sáng mặt",
         app.sp_bu_sang.hoi is not None
         and f"Mốc sáng mặt: {float(moc):+.2f} EV" in app.sp_bu_sang.hoi.goi_y.chu,
         "số 0 của thanh bù nghĩa là mặt về mốc này")
    sg = app.sp_gap
    sg._khi_xong = lambda: None
    sg.thanh.set(7.3)
    chay(1)
    buoc_gap = app.v_gap.get()
    app.v_gap.set("120")
    chay(2)
    ktra("số ngoài khoảng thanh vẫn giữ nguyên trong ô",
         buoc_gap == "7.5" and app.v_gap.get() == "120"
         and abs(sg._dv.get() - 60.0) < 1e-9,
         f"kéo 7.3 → {buoc_gap} · gõ 120 → thanh đứng ở mép 60")
    app.v_gap.set("5")
    ma_tron = next(nhan for nhan, ma in ag.MODES if ma == "hybrid")
    ma_dau = app.v_mode.get()
    tat = app.sp_blend.trang_thai()
    app.v_mode.set(ma_tron)
    app._on_mode_change()
    mo = app.sp_blend.trang_thai()
    o_mo = "disabled" not in app.sp_blend.o.state()
    app.v_mode.set(ma_dau)
    app._on_mode_change()
    ktra("Độ trộn khoá / mở theo chế độ như ô số cũ",
         tat == "disabled" and mo == "normal" and o_mo
         and app.sp_blend.trang_thai() == "disabled",
         f"{tat} → {mo} → {app.sp_blend.trang_thai()}")

    # ------------------------------------------------ 5. dấu ?
    ds = []
    di_khap(app, ds)
    hoi = [w for w in ds if isinstance(w, gd.NutHoi)]
    chu = [w.goi_y.chu for w in hoi]
    thieu = [c[:40] for c in chu_thich_cu(at) if not any(c in x for x in chu)]
    ktra("mọi dòng chú thích cũ còn nguyên trong một dấu ?", not thieu,
         " | ".join(thieu) if thieu else f"{len(chu_thich_cu(at))} dòng · {len(hoi)} dấu ?")
    #[[ Tuy chon cua Can tone nay o BANG DIEU KHIEN PHAI (app.cuon_phai), dau
    #   bang co dau ? mang dong mo ta khau cu (MO_KHAU) — cai NHIN THAY duoc,
    #   khong phai hoi_khau cua dong dau trang phu dang an. ]]
    bang = app.cuon_phai.trong
    ktra("đầu bảng điều khiển có dấu ? mang dòng mô tả khâu",
         app.hoi_md.goi_y.chu == ag.MO_KHAU.get("phan_tich")
         and app.hoi_md.winfo_ismapped(), "dòng mô tả cũ, nhìn thấy được")
    trong = [w for w in hoi if la_con_cua(w, bang)]
    ktra("dấu ? nào trong bảng điều khiển cũng có chữ",
         len(trong) >= 20 and all(w.goi_y.chu for w in trong), f"{len(trong)} dấu ?")
    h = next(w for w in trong if "KÉO SÁNG" in w.goi_y.chu)
    h.event_generate("<Enter>", x=3, y=3)
    chay(2)
    chua = h.goi_y.cua is None
    chay(12, 0.04)
    hien = h.goi_y.cua is not None
    nhan = ""
    if hien:
        nds = []
        di_khap(h.goi_y.cua, nds)
        nhan = " ".join(str(x.cget("text")) for x in nds if x.winfo_class() == "Label")
    h.event_generate("<Leave>", x=40, y=40)
    chay(3)
    ktra("rê chuột vào dấu ? thì hiện chú thích (sau một nhịp), rời ra thì tắt",
         chua and hien and "KÉO SÁNG" in nhan and h.goi_y.cua is None,
         "không hiện ngay khi chuột lướt qua")
    ktra("chữ phụ không còn in sẵn dưới tính năng",
         not [w for w in ds if la_con_cua(w, bang)
              and w.winfo_class() == "TLabel"
              and str(w.cget("style")) == "Mo2.TLabel"
              and not any(w is n2.l_tom for n2 in nhom.values())],
         "chỉ còn dòng tóm tắt của nhóm")

    # ------------------------------------------------ 6. cảnh báo im lặng
    for p in at.LR_JOB_DIR.iterdir():
        p.unlink()
    app.v_folder.set("")
    app._lam_moi_ray()
    chay(3)
    an_luc_dau = not app.dai_canh.winfo_ismapped()
    (at.LR_JOB_DIR / "apply_20261003_120000_G0310.tsv").write_text("x\n", encoding="utf-8")
    app._lam_moi_ray()
    chay(3)
    hien_canh = app.dai_canh.winfo_ismapped() and "job đang chờ" in app.lbl_im_lang.cget("text")
    (at.LR_JOB_DIR / "apply_20261003_120000_G0310.tsv").unlink()
    app._lam_moi_ray()
    chay(3)
    ktra("plugin không nhận job → dải cảnh báo trên cùng, hết thì tắt",
         an_luc_dau and hien_canh and not app.dai_canh.winfo_ismapped(),
         "khâu nào cũng thấy — Tổng quan đã ẩn")


if __name__ == "__main__":
    sys.exit(main())
