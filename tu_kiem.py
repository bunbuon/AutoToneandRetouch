#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tu_kiem.py — App tự kiểm chính nó, chạy được CẢ khi đã đóng gói.

    python tu_kiem.py                 # chạy từ mã nguồn
    AutoTone.exe  (với AUTOTONE_TU_KIEM=<file báo cáo>)

VÌ SAO KIỂM TỪ BÊN TRONG GÓI CHỨ KHÔNG KIỂM TỪ NGOÀI
    Nhìn từ ngoài chỉ thấy được có file hay không. Những thứ hay hỏng nhất khi
    đóng gói lại vô hình từ ngoài:

      * đường dẫn tài nguyên: sys._MEIPASS khác hẳn thư mục mã nguồn, nên
        mô hình nhận mặt có thể "có trong gói" mà app vẫn không mở được;
      * import ngầm: PyInstaller dò import theo tĩnh, module nào chỉ được import
        bên trong hàm thì nó bỏ qua — chạy đến đó mới nổ;
      * chỗ ghi: Program Files không ghi được, và Windows còn âm thầm chuyển
        hướng sang VirtualStore nên ghi "thành công" mà file nằm nơi khác;
      * DLL nhị phân của torch/onnxruntime thiếu một file là import gãy.

    Chỉ tiến trình CHẠY BÊN TRONG gói mới trả lời được mấy câu đó. Nên bài kiểm
    nằm trong app, và kiem_goi.py bên ngoài chỉ việc chạy app rồi đọc báo cáo.

APP KHÔNG CÓ CỬA SỔ CONSOLE
    Gói build bằng --windowed nên print() không đi đâu cả. Vì vậy báo cáo được
    GHI RA FILE (đường dẫn lấy từ biến môi trường AUTOTONE_TU_KIEM), và kết quả
    đạt/không đạt trả về bằng mã thoát 0/1.
"""
from __future__ import annotations

import io
import os
import shutil
import sys
import tempfile
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

BIEN = "AUTOTONE_TU_KIEM"


class Bao:
    """Gom kết quả. Mỗi mục: (đạt?, tên, ghi chú)."""

    def __init__(self):
        self.muc: list[tuple[bool, str, str]] = []

    def dat(self, ten, ghi=""):
        self.muc.append((True, ten, str(ghi)))

    def hong(self, ten, ghi=""):
        self.muc.append((False, ten, str(ghi)))

    def thu(self, ten, ham):
        """Chạy một phép kiểm, ngoại lệ tính là hỏng chứ không làm gãy cả bài."""
        try:
            ghi = ham()
            self.dat(ten, ghi if ghi is not None else "")
        except Exception as e:                                   # noqa: BLE001
            self.hong(ten, f"{type(e).__name__}: {e}")

    @property
    def so_hong(self) -> int:
        return sum(1 for ok, _, _ in self.muc if not ok)

    def van(self) -> str:
        d = []
        for ok, ten, ghi in self.muc:
            d.append(f"[{'DAT ' if ok else 'HONG'}] {ten}" + (f"  — {ghi}" if ghi else ""))
        d.append("")
        d.append("TAT CA DAT" if not self.so_hong else f"{self.so_hong} MUC HONG")
        return "\n".join(d)


def _anh_thu(d: Path) -> Path:
    import numpy as np
    from PIL import Image
    a = np.random.default_rng(11).normal(120, 28, (900, 1350, 3)).clip(0, 255)
    p = d / "tu_kiem.jpg"
    Image.fromarray(a.astype("uint8")).save(p, quality=88)
    return p


def chay(nhanh: bool = False) -> Bao:
    b = Bao()
    import duong_dan as dd

    # --- 1. Môi trường ------------------------------------------------------
    b.dat("Môi trường",
          f"python {sys.version.split()[0]} · {sys.platform} · "
          f"{'ĐÃ ĐÓNG GÓI' if dd.dong_goi() else 'chạy từ mã nguồn'}")
    b.dat("Thư mục tài nguyên", dd.goc_tai_nguyen())
    b.dat("Thư mục dữ liệu", dd.goc_du_lieu())

    #[[ Du lieu KHONG DUOC nam trong goi. Neu nam trong thi tren Windows se roi
    #   vao VirtualStore, con tren macOS la pha chu ky cua .app.
    #]]
    def _tach_bach():
        if not dd.dong_goi():
            return "bỏ qua (chạy từ mã nguồn thì hai chỗ vốn là một)"
        tn, dl = dd.goc_tai_nguyen().resolve(), dd.goc_du_lieu().resolve()
        if dl == tn or tn in dl.parents:
            raise AssertionError(f"dữ liệu {dl} nằm TRONG gói {tn}")
        return "dữ liệu nằm ngoài gói"
    b.thu("Dữ liệu tách khỏi gói", _tach_bach)

    def _ghi_duoc():
        p = dd.du_lieu("tu_kiem_thu.txt")
        p.write_text("x" * 64, encoding="utf-8")
        if p.read_text(encoding="utf-8") != "x" * 64:
            raise AssertionError("ghi xong đọc lại không khớp")
        #[[ Doc lai bang duong dan TUYET DOI da giai quyet symlink: tren Windows
        #   VirtualStore chuyen huong am tham, file "co" nhung khong o cho minh
        #   tuong. So st_dev/st_ino de biet chac la cung mot file.
        #]]
        that = Path(os.path.realpath(p))
        if that.parent.resolve() != dd.goc_du_lieu().resolve():
            raise AssertionError(f"ghi bị chuyển hướng sang {that}")
        p.unlink()
        return str(dd.goc_du_lieu())
    b.thu("Thư mục dữ liệu ghi được", _ghi_duoc)

    # --- 2. Tài nguyên đi kèm ----------------------------------------------
    import autotone as at

    def _mo_hinh():
        p = Path(at.FACE_MODEL)
        if not p.is_file():
            raise AssertionError(f"không thấy {p}")
        kb = p.stat().st_size / 1024
        if kb < 50:
            raise AssertionError(f"file chỉ {kb:.0f} KB — nhiều khả năng là rác")
        return f"{p.name} · {kb:.0f} KB"
    b.thu("Mô hình nhận mặt", _mo_hinh)

    def _plugin():
        d = Path(at.LR_PLUGIN_DIR)
        thieu = [f for f in ("Info.lua", "AutoToneCore.lua", "ApplyNow.lua")
                 if not (d / f).is_file()]
        if thieu:
            raise AssertionError(f"{d} thiếu {', '.join(thieu)}")
        j = d / "jobs"
        j.mkdir(parents=True, exist_ok=True)
        t = j / "tu_kiem.tmp"
        t.write_text("x", encoding="utf-8")
        t.unlink()
        return f"{d} (jobs ghi được)"
    b.thu("Plugin Lightroom", _plugin)

    #[[ GOI KHONG DUOC MANG THEO jobs/ CUA MAY BUILD.
    #
    #   jobs/ chua nhat ky plugin, job da xong, va ban xuat tu catalog. Do la
    #   trang thai luc chay. Goi build ngay 4/9 da mang theo
    #   export_20260903_105234.tsv (buoi 2905, 220 anh); ban .exe chep no ra roi
    #   doc phai, nen buoi 96 anh bi bao "ban xuat chi khop 0 anh" trong khi
    #   Lightroom van xuat dung — chi la xuat vao mot thu muc khac.
    #
    #   Kiem tren TAI NGUYEN TRONG GOI chu khong phai tren thu muc da chep ra:
    #   thu muc chep ra co jobs/ la binh thuong (app tu tao de dung), con goi ma
    #   co la sai tu luc build.
    #]]
    def _plugin_sach():
        if not dd.dong_goi():
            return "bỏ qua (chỉ kiểm được trên gói đã đóng)"
        g = dd.goc_tai_nguyen() / "AutoTone.lrplugin"
        if not g.is_dir():
            raise AssertionError(f"không thấy plugin trong gói: {g}")
        rac = sorted(p.name for p in g.rglob("*")
                     if p.is_file() and (p.suffix in (".tsv", ".done", ".log")
                                         or p.parent.name == "jobs"))
        if rac:
            raise AssertionError(
                f"gói mang theo {len(rac)} file trạng thái trong jobs/ "
                f"({', '.join(rac[:3])}...) — bản xuất cũ trong đó sẽ bị app đọc "
                f"nhầm thành bản xuất của buổi đang làm")
        return "không kèm jobs/"
    b.thu("Plugin trong gói sạch", _plugin_sach)

    # --- 3. Khoá hạn dùng ---------------------------------------------------
    def _khoa():
        import khoa
        m = khoa.ma_may()
        if len(m) != 12:
            raise AssertionError(f"mã máy dài {len(m)}, đáng lẽ 12")
        k = khoa.kiem()
        for c in ("chay_duoc", "ly_do", "con_lai", "han", "may"):
            if c not in k:
                raise AssertionError(f"kiem() thiếu khoá {c!r}")
        return (f"máy {m} · {'còn hạn' if k['chay_duoc'] else 'ĐÃ KHOÁ'} · "
                f"{khoa.mo_ta_con_lai(k['con_lai'])}")
    b.thu("Khoá hạn dùng", _khoa)

    #[[ tao_ma.py dung chung khoa bi mat voi khoa.py. Co no trong goi la ai cung
    #   tu sinh duoc ma gia han. dong_goi.py loai no o hai muc, day la cho kiem
    #   lai tren chinh cai goi da build ra.
    #]]
    def _khong_tao_ma():
        try:
            import tao_ma                                        # noqa: F401
        except ImportError:
            return "không có trong gói (đúng)"
        if not dd.dong_goi():
            return "có, nhưng đang chạy từ mã nguồn nên không sao"
        raise AssertionError("tao_ma LỌT VÀO GÓI — ai có gói đều tự sinh được "
                             "mã gia hạn, cơ chế hạn dùng thành vô nghĩa")
    b.thu("tao_ma.py không lọt vào gói", _khong_tao_ma)

    # --- 4. Module nạp được -------------------------------------------------
    def _nap():
        ten = ["autotone", "giao_dien", "duong_dan", "khoa", "trang_thai",
               "thu_gu", "retouch", "learn_corrections", "khoi_phuc"]
        hong = []
        for t in ten:
            try:
                __import__(t)
            except Exception as e:                               # noqa: BLE001
                hong.append(f"{t} ({type(e).__name__})")
        if hong:
            raise AssertionError("không nạp được: " + ", ".join(hong))
        return f"{len(ten)}/{len(ten)} module"
    b.thu("Module của app", _nap)

    def _thu_vien():
        import numpy, PIL                                        # noqa: F401
        v = [f"numpy {numpy.__version__}", f"pillow {PIL.__version__}"]
        try:
            import cv2
            v.append(f"opencv {cv2.__version__}")
        except Exception as e:                                   # noqa: BLE001
            raise AssertionError(f"cv2 hỏng ({type(e).__name__}) — không nhận "
                                 "được mặt thì cách đo mặc định vô dụng")
        return " · ".join(v)
    b.thu("Thư viện nền", _thu_vien)

    # --- 5. Chạy thật đường xử lý ------------------------------------------
    def _nhan_mat():
        d = at.face_detector()
        if d is None:
            raise AssertionError("face_detector() trả về None")
        return "nạp được từ mô hình trong gói"
    b.thu("Bộ nhận mặt", _nhan_mat)

    if not nhanh:
        def _do_anh():
            #[[ Chay CA 6 cach do. measure() boc try/except toan than nen loi lap
            #   trinh trong do bien thanh ok=False chu khong nem ra — tung co that:
            #   4 cach do bi UnboundLocalError ma app chi bao "khong doc duoc anh".
            #]]
            with tempfile.TemporaryDirectory() as t:
                p = _anh_thu(Path(t))
                hong = []
                for m in ("face", "focus", "subject", "center", "average", "median"):
                    r = at.measure(p, 480, m)
                    if not r["ok"]:
                        hong.append(f"{m}: {r['error'][:60]}")
                if hong:
                    raise AssertionError(" | ".join(hong))
            return "6/6 cách đo"
        b.thu("Đo ảnh", _do_anh)

        #[[ Di DUNG THU TU that: do -> tach canh -> tinh delta -> ra gia tri crs.
        #   decide() doc r["scene"], ma "scene" do group_scenes() dat. Goi decide()
        #   thang se KeyError — tuc bai kiem phai chay dung chuoi ma app chay,
        #   khong duoc goi le tung ham cho tien.
        #]]
        def _tinh():
            from datetime import datetime, timedelta
            moc = datetime(2026, 9, 4, 9, 0)
            with tempfile.TemporaryDirectory() as t:
                p = _anh_thu(Path(t))
                r = at.measure(p, 480, "face")
                if not r["ok"]:
                    raise AssertionError(f"đo hỏng: {r['error'][:80]}")
                r["dt_obj"] = moc
                #[[ crs/atn la thong so preset doc tu sidecar .xmp. Anh thu khong
                #   co sidecar, nen dat rong — dung y het nhanh du phong cua app
                #   khi khong doc duoc sidecar. decide() doc r["crs"] vo dieu
                #   kien o che do WB "skin"/"asshot", bo qua la KeyError.
                #]]
                r["crs"], r["atn"] = {}, {}
                at.group_scenes([r], 5.0, 0.0)
                cfg = dict(at.DEFAULTS)
                at.decide([r], cfg)
                if r.get("delta_ev") is None:
                    raise AssertionError("decide() không tính ra delta_ev")
                gt = at.compute_values(r, cfg, {}, {})
                if "Exposure2012" not in gt:
                    raise AssertionError(f"compute_values() thiếu Exposure2012: {list(gt)}")
                return f"delta {r['delta_ev']:+.2f} EV → Exposure2012={gt['Exposure2012']}"
        b.thu("Tính giá trị", _tinh)

        def _tach_canh():
            from datetime import datetime, timedelta
            moc = datetime(2026, 9, 4, 9, 0)
            items = [{"ok": True, "dt_obj": moc + timedelta(minutes=i * 3),
                      "scene_sig": [1.0, 1.0, 1.0], "path": f"{i}.jpg"}
                     for i in range(6)]
            items += [{"ok": True, "dt_obj": moc + timedelta(minutes=60 + i * 3),
                       "scene_sig": [0.2, 1.8, 1.0], "path": f"b{i}.jpg"}
                      for i in range(6)]
            at.group_scenes(items, 5.0, 0.35)
            n = len({r["scene"] for r in items})
            if n != 2:
                raise AssertionError(f"12 ảnh hai bối cảnh cách nhau 1 giờ mà "
                                     f"tách ra {n} cảnh")
            return "2 cảnh, đúng như mong đợi"
        b.thu("Tách cảnh", _tach_canh)

    # --- 5b. Chạy thật trên ẢNH RAW THẬT của người dùng ---------------------
    #[[ VI SAO PHAI CO PHAN NAY, DU DA CO PHAN TREN.
    #
    #   Cac phep o tren chay tren mot file JPEG nhieu do bai kiem tu sinh. No
    #   chung minh duong xu ly khong gay, nhung KHONG cham toi hai thu de hong
    #   nhat khi doi may:
    #
    #     1. Doc RAW. read_raw() do preview JPEG nhung trong file .ARW bang cach
    #        quet IFD va marker. Moi hang may, moi doi may nhet preview mot kieu
    #        va mot co khac nhau. Anh tu sinh khong bao gio lo ra duoc chuyen do.
    #     2. Ghi .xmp. Day la buoc DUY NHAT dong vao file cua nguoi dung. Ghi
    #        hong thi mat thong so ca buoi, va chi biet khi da muon.
    #
    #   Nen dat thu muc anh that qua bien AUTOTONE_TU_KIEM_ANH thi bai kiem se
    #   doc that, do that, ghi .xmp that — nhung ghi tren BAN CHEP trong thu muc
    #   tam, khong bao gio dung vao file goc cua nguoi dung.
    #]]
    thu_muc_anh = os.environ.get("AUTOTONE_TU_KIEM_ANH")
    if thu_muc_anh and not nhanh:
        d_anh = Path(thu_muc_anh)

        def _raw_that():
            if not d_anh.is_dir():
                raise AssertionError(f"không thấy thư mục {d_anh}")
            ds = sorted(p for p in d_anh.iterdir()
                        if p.is_file() and p.suffix.lower() in at.RAW_EXTS)[:5]
            if not ds:
                raise AssertionError(f"{d_anh} không có file RAW nào "
                                     f"(đuôi nhận: {', '.join(sorted(at.RAW_EXTS))})")
            hong, cx = [], []
            for p in ds:
                blob, tags = at.read_raw(p)
                if blob is None:
                    hong.append(f"{p.name}: không tìm thấy preview JPEG nhúng")
                    continue
                from PIL import Image
                im = Image.open(io.BytesIO(blob))
                cx.append(f"{im.width}x{im.height}")
                if at.parse_dt(tags, p) is None:
                    hong.append(f"{p.name}: không đọc được giờ chụp")
            if hong:
                raise AssertionError(" | ".join(hong))
            return f"{len(ds)} file · preview {cx[0]} · đọc được giờ chụp"
        b.thu("Đọc RAW thật", _raw_that)

        def _do_raw_that():
            ds = sorted(p for p in d_anh.iterdir()
                        if p.is_file() and p.suffix.lower() in at.RAW_EXTS)[:3]
            if not ds:
                raise AssertionError("không có RAW để đo")
            cfg = dict(at.DEFAULTS)
            so_mat = 0
            for p in ds:
                r = at.measure(p, cfg["preview_px"], cfg["meter"],
                               wb_needs_faces=(cfg["wb"] == "skin"))
                if not r["ok"]:
                    raise AssertionError(f"{p.name}: {r['error'][:70]}")
                if r.get("metered_ev") is None:
                    raise AssertionError(f"{p.name}: đo xong mà metered_ev rỗng")
                so_mat += int(r.get("faces_n") or 0)
            return f"{len(ds)} ảnh · tổng {so_mat} khuôn mặt nhận được"
        b.thu("Đo ảnh RAW thật", _do_raw_that)

        def _ghi_xmp():
            #[[ CHEP RA THU MUC TAM ROI MOI GHI. Khong bao gio ghi vao file that
            #   cua nguoi dung trong mot bai kiem — du apply_to_sidecar co backup.
            #]]
            ds = [p for p in sorted(d_anh.iterdir())
                  if p.is_file() and p.suffix.lower() in at.RAW_EXTS
                  and at.sidecar_for(p) is not None]
            if not ds:
                return ("bỏ qua — không ảnh nào có sẵn .xmp "
                        "(bình thường khi lấy thông số từ catalog)")
            goc_raw = ds[0]
            goc_sc = at.sidecar_for(goc_raw)
            with tempfile.TemporaryDirectory() as t:
                td = Path(t)
                raw = td / goc_raw.name
                shutil.copy2(goc_raw, raw)
                sc = td / goc_sc.name
                shutil.copy2(goc_sc, sc)
                truoc = sc.read_bytes()

                cfg = dict(at.DEFAULTS)
                r = at.measure(raw, cfg["preview_px"], cfg["meter"],
                               wb_needs_faces=(cfg["wb"] == "skin"))
                if not r["ok"]:
                    raise AssertionError(f"đo hỏng: {r['error'][:70]}")
                r["sidecar"] = str(sc)
                #[[ measure() tra ve "dt" dang chuoi; dt_obj la do analyze() doi
                #   ra (xem autotone.py, cho r["dt_obj"] = datetime.fromisoformat).
                #   group_scenes() doc dt_obj nen phai doi o day.
                #]]
                r["dt_obj"] = datetime.fromisoformat(r["dt"])
                txt = sc.read_bytes().decode("utf-8")
                r["crs"], r["atn"] = at.read_crs(txt), at.read_ns(txt, at.ATN_PREFIX)
                at.group_scenes([r], 5.0, 0.0)
                at.decide([r], cfg)

                bk = td / "_xmp_backup" / "lan1"
                at.apply_to_sidecar(r, cfg, bk, td, dry=False)
                sau = sc.read_bytes()
                if sau == truoc:
                    raise AssertionError("ghi .xmp xong mà file không đổi gì")
                crs2 = at.read_crs(sau.decode("utf-8"))
                if "Exposure2012" not in crs2:
                    raise AssertionError("file .xmp sau khi ghi không có Exposure2012")

                #[[ HOAN TAC cung phai chay that. Nut Hoan tac la cai duy nhat
                #   cuu duoc nguoi dung khi ghi nham ca buoi — no hong thi ca
                #   buoc ghi tro thanh mot chieu.
                #]]
                n = at.undo(bk, td)
                if n < 1:
                    raise AssertionError(f"hoàn tác chỉ khôi phục {n} file")
                if sc.read_bytes() != truoc:
                    raise AssertionError("hoàn tác xong mà file .xmp không "
                                         "trở lại y như cũ")
            return (f"{goc_sc.name}: ghi Exposure2012={crs2.get('Exposure2012')} "
                    f"rồi hoàn tác lại đúng bản gốc")
        b.thu("Ghi .xmp rồi hoàn tác", _ghi_xmp)

        def _job_lr():
            """Job gửi sang Lightroom có ghi ra đúng thư mục plugin không."""
            ds = sorted(p for p in d_anh.iterdir()
                        if p.is_file() and p.suffix.lower() in at.RAW_EXTS)[:2]
            if not ds:
                raise AssertionError("không có RAW")
            #[[ Goi at.plan() chu KHONG tu xau chuoi group_scenes -> decide.
            #
            #   write_lr_job() bo qua moi anh khong co "new_exposure", ma khoa do
            #   la do compute_values() dat — mot buoc NAM TRONG plan(). Ban dau
            #   bai kiem tu goi decide() cho gon va write_lr_job tra ve None: no
            #   "chay" nhung khong sinh ra dong nao, tuc kiem mot duong di khong
            #   phai duong app di. Goi ham that thi khong lech duoc.
            #]]
            cfg = dict(at.DEFAULTS)
            cfg["source"] = "catalog"
            #[[ TAT "bo qua anh nguoi sua tay" cho rieng phep kiem nay.
            #
            #   Ban xuat gia o duoi khai Exposure2012 = 0. Neu thu muc anh nay
            #   da tung duoc tool ghi that, thi last_applied() se thay gia tri
            #   cu khac 0 va ket luan NGUOI DUNG DA SUA TAY — dung theo dung
            #   nghia cua tinh nang do, va anh bi rut hoan toan khoi duong ong
            #   nen khong co "new_exposure", nen write_lr_job tra ve None.
            #
            #   Da mac dung bay nay: "write_lr_job khong tao ra file nao" trong
            #   khi ca app lan tinh nang deu dang chay dung. Phep kiem nay hoi
            #   ve viec GHI JOB, nen tat cai cong do di cho no hoi dung mot thu.
            #]]
            cfg["bo_qua_nguoi_sua"] = False
            xuat = {}
            items = []
            for p in ds:
                r = at.measure(p, cfg["preview_px"], cfg["meter"],
                               wb_needs_faces=(cfg["wb"] == "skin"))
                if not r["ok"]:
                    raise AssertionError(f"{p.name}: {r['error'][:70]}")
                r["dt_obj"] = datetime.fromisoformat(r["dt"])
                items.append(r)
                #[[ Gia lap ban xuat tu catalog: khong co no thi che do catalog
                #   khong co thong so preset goc de cong delta vao.
                #]]
                xuat[os.path.normcase(os.path.abspath(str(p)))] = {
                    "Exposure2012": "0", "Highlights2012": "0",
                    "Shadows2012": "0", at.LR_PATH_KEY: str(p)}
            at.plan(items, cfg, d_anh, xuat)
            job = at.write_lr_job(items, "tu_kiem")
            if job is None:
                raise AssertionError("write_lr_job không tạo ra file nào")
            try:
                dong = job.read_text(encoding="utf-8").splitlines()
                if len(dong) < 2:
                    raise AssertionError(f"job chỉ có {len(dong)} dòng")
                if not dong[0].startswith("path\t"):
                    raise AssertionError(f"dòng đầu sai: {dong[0][:40]!r}")
                cho = job.parent
            finally:
                job.unlink(missing_ok=True)
            return f"{len(dong) - 1} dòng, ghi vào {cho}"
        b.thu("Job gửi Lightroom", _job_lr)

    # --- 6. Phần retouch ----------------------------------------------------
    def _retouch():
        import retouch
        goc = retouch.tim_tool()
        if goc is None:
            return "KHÔNG có trong gói — nút Retouch sẽ báo chưa sẵn sàng"
        if not retouch.hop_le(goc):
            raise AssertionError(f"tìm thấy {goc} nhưng thiếu file: "
                                 + retouch.vi_sao_khong_dung(goc))
        return f"có tại {goc}"
    b.thu("Công cụ retouch", _retouch)

    #[[ BA PHEP KIEM DUOI DAY LA DE CHAN MOT KIEU HONG CU THE.
    #
    #   saytool KHONG dung lai khi mot buoc hong. No in mot dong
    #       ! BO QUA Xoa khuyet diem: ModuleNotFoundError: No module named 'blem_net3'
    #   roi chay tiep cac buoc con lai. Nghia la goi van chay, van ra anh, chi la
    #   tinh nang chinh da tat — va dong bao do troi qua giua hang tram dong nhat
    #   ky. Da tai hien duoc that: dat mot thu muc chi co saytool/ + mo_hinh/
    #   (dung hinh dang ban dong goi) thi blemish_apply nap khong duoc, vi
    #   blem_net3.py va blem_gpu.py nam o THU MUC GOC ToolCloneEvoto chu khong
    #   nam trong goi saytool.
    #
    #   Nen phai kiem BANG CACH NAP THAT, khong phai bang cach dem file.
    #]]
    def _mo_hinh_retouch():
        import retouch
        goc = retouch.tim_tool()
        if goc is None:
            return "bỏ qua — gói không kèm retouch"
        kho = Path(goc) / "mo_hinh"
        can = {
            "vet.pt": "xoá khuyết điểm",
            "nong_cam.pt": "xoá nọng cằm",
        }
        thieu = [f"{f} ({v})" for f, v in can.items() if not (kho / f).is_file()]

        #[[ BAN NHE: thieu mo hinh la BINH THUONG, khong phai hong.
        #
        #   Bai kiem nay viet truoc khi co ban nhe, nen no chi biet hai trang
        #   thai: "goi khong kem retouch" hoac "mo hinh phai co san". Ban nhe
        #   la trang thai THU BA — co day du phan retouch, nhung mo hinh
        #   (487 MB) tai ve lan dau bam nut.
        #
        #   De nguyen thi moi lan dong goi ban nhe deu ra mot dong [HONG] —
        #   va mot bai kiem luon do khi moi thu van dung se day nguoi ta toi
        #   cho bo qua no, ke ca luc no bao dung.
        #
        #   Phan biet bang chinh trinh tai: no biet goi "mo-hinh" da ve chua.
        #]]
        if thieu:
            try:
                import tai_nguyen as _tn
                chua_tai = "mo-hinh" in _tn.can_cho_retouch()
            except Exception:                                # noqa: BLE001
                chua_tai = False
            if chua_tai:
                return (f"bản nhẹ — mô hình chưa tải ({len(thieu)}/{len(can)} "
                        f"thiếu). Bấm Retouch lần đầu sẽ tải về.")

        them_ = []
        if (kho / "resnet34_faceparse.onnx").is_file():
            them_.append("phân vùng da")
        if list((kho / "insightface" / "models" / "buffalo_l").glob("*.onnx")):
            them_.append("nhận diện mặt")
        if (kho / "liquify" / "danh_muc.json").is_file():
            them_.append("tạo hình khuôn mặt")
        if thieu:
            raise AssertionError("thiếu mô hình: " + ", ".join(thieu))
        d = f"{len(can)} mô hình chính"
        if them_:
            d += " + mang sẵn: " + ", ".join(them_)
        else:
            d += " — CHƯA mang sẵn mô hình tải về, lần đầu chạy sẽ phải tải ~420 MB"
        return d
    b.thu("Mô hình retouch", _mo_hinh_retouch)

    def _nap_buoc_retouch():
        """Nạp THẬT từng bước của saytool, không chỉ đếm file."""
        import retouch
        goc = retouch.tim_tool()
        if goc is None:
            return "bỏ qua — gói không kèm retouch"
        try:
            import torch                                    # noqa: F401
        except ImportError:
            return "bỏ qua — gói nhẹ, không có torch"
        cu = os.getcwd()
        try:
            os.chdir(goc)
            sys.path.insert(0, str(goc))
            from saytool.buoc import tat_ca
            ds = tat_ca()
            if not ds:
                raise AssertionError("saytool không nạp được bước nào")
            #[[ Nap module dung sau tung buoc. buoc_vet chi import blemish_apply
            #   trong nap(), nen chi import saytool.buoc_vet thi KHONG lo ra
            #   thieu blem_net3 — phai cham toi dung cho do.
            #]]
            from saytool.loi import blemish_apply as ba
            net = ba.load_net(str(Path(goc) / "mo_hinh" / "vet.pt"))
            ten = type(net).__name__
        finally:
            os.chdir(cu)
        return f"{len(ds)} bước ({', '.join(b_.ten for b_ in ds)}) · mô hình vết: {ten}"
    b.thu("Nạp bước retouch", _nap_buoc_retouch)

    def _keo_retouch():
        import retouch
        goc = retouch.tim_tool()
        if goc is None:
            return "bỏ qua — gói không kèm retouch"
        ds = retouch.thanh_keo(goc, lam_lai=True)
        if len(ds) <= len(retouch.THANH_KEO) and \
                [t[0] for t in ds] == [t[0] for t in retouch.THANH_KEO]:
            #[[ Hoi that bai thi thanh_keo() lui ve ban du phong, va giao dien se
            #   THIEU thanh keo moi ma khong bao gi. Phai bat duoc o day.
            #]]
            return ("CHỈ CÓ bản dự phòng — hỏi saytool không được, "
                    "giao diện sẽ thiếu thanh kéo mới")
        return f"{len(ds)} thanh kéo: " + ", ".join(t[0] for t in ds)
    b.thu("Thanh kéo retouch", _keo_retouch)

    def _torch():
        try:
            import torch
        except ImportError:
            return "không đóng kèm (gói nhẹ)"
        return (f"torch {torch.__version__} · "
                f"CUDA {'có' if torch.cuda.is_available() else 'không'}")
    b.thu("torch", _torch)

    # --- 7. Giao diện -------------------------------------------------------
    def _giao_dien():
        import tkinter as tk
        import giao_dien as gd
        try:
            r = tk.Tk()
        except Exception as e:                                   # noqa: BLE001
            return f"bỏ qua — máy không có màn hình ({type(e).__name__})"
        try:
            gd.dat_theme(r)
            from tkinter import ttk
            if ttk.Style(r).theme_use() != "clam":
                raise AssertionError("theme không phải clam — trên Windows các "
                                     "lệnh đổi màu sẽ bị bỏ qua, giao diện trắng bốc")
            #[[ PHIEN BAN Tk — cho macOS.
            #
            #   Python he thong cua macOS di kem Tk 8.5, ban do tren macOS hien
            #   dai bi loi ve: chu mo, o nhap khong nhan chuot, cua so nhay lung
            #   tung. PyInstaller dong theo dung ban Tk cua Python dung de build,
            #   nen build bang Python he thong la ca goi mang theo cai Tk hong do.
            #   Can Tk 8.6 tro len — python.org hoac Homebrew deu co.
            #]]
            tk_ver = float(r.tk.call("info", "patchlevel").rsplit(".", 1)[0])
            if tk_ver < 8.6:
                raise AssertionError(
                    f"Tk {r.tk.call('info', 'patchlevel')} — quá cũ. Trên macOS "
                    f"bản 8.5 vẽ giao diện hỏng. Build lại bằng Python từ "
                    f"python.org hoặc Homebrew (brew install python-tk).")
            return f"tkinter Tk {r.tk.call('info', 'patchlevel')} + theme clam"
        finally:
            r.destroy()
    b.thu("Giao diện", _giao_dien)

    return b


def main(argv=None) -> int:
    nhanh = "--nhanh" in (argv if argv is not None else sys.argv[1:])
    try:
        b = chay(nhanh)
        van = b.van()
        ma = 1 if b.so_hong else 0
    except Exception:                                            # noqa: BLE001
        van = "BÀI KIỂM GÃY GIỮA CHỪNG:\n" + traceback.format_exc()
        ma = 2

    dich = os.environ.get(BIEN)
    if dich:
        try:
            p = Path(dich)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(van, encoding="utf-8")
        except OSError:
            pass
    #[[ Goi build bang --windowed KHONG CO console: tren Windows sys.stdout la
    #   None, va print() nem AttributeError. Bao cao that nam trong file o tren;
    #   print chi la tien nghi khi chay tu dong lenh.
    #]]
    try:
        print(van)
    except Exception:                                        # noqa: BLE001
        pass
    return ma


if __name__ == "__main__":
    sys.exit(main())
