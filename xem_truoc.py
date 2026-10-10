#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xem_truoc.py — Máy tính ảnh xem trước retouch (tiến trình con dùng saytool).

TỪ TỐI 3/10 KHÔNG CÒN CỬA SỔ XEM TRƯỚC RIÊNG
    User: "Phần lưới ảnh của Retouch hãy làm giống Evoto. 1 ảnh mở to và lưới
    ảnh bên dưới. Sửa lại cả tính năng zoom ảnh." Như Evoto, bản xem trước
    hiện ngay trên ẢNH LỚN của mô-đun Retouch, theo đúng các thanh ở bảng điều
    khiển bên phải — không mở thêm một cửa sổ có ảnh lớn và thanh kéo thứ hai.
    File này chỉ còn phần máy: tiến trình con + giao thức. Khung vẽ, zoom ở
    khung_anh.py.

VÌ SAO CHẠY TRONG TIẾN TRÌNH CON
    App không có torch/onnxruntime (bản nhẹ tải chúng về sau, và ngay bản đầy
    đủ cũng không nạp chúng vào tiến trình giao diện). saytool thì có. Nên
    phần tính ảnh chạy ở tiến trình con dùng Python của ToolCloneEvoto.

    Trao đổi qua stdin/stdout bằng JSON một dòng — không cần cổng mạng, không
    đụng tường lửa, và tiến trình con chết thì app biết ngay.

VÌ SAO KHÔNG TÍNH THEO TỪNG NHỊP KÉO
    Đo thật trên ảnh 1600px có 3 mặt: mức 100 mất 2,76 giây. Nên ngừng kéo
    mới tính, và đang tính mà mức lại đổi thì chỉ tính thêm MỘT lần nữa khi
    lần đang chạy xong — không xếp hàng năm lượt cho năm lần thả tay.
"""
from __future__ import annotations

import base64
import io
import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

#[[ Ma chay o TIEN TRINH CON. De thang day chu khong tach file rieng: file
#   rieng thi phai nho chep no sang may Mac, nho them vao LOAI_TRU, nho dong
#   vao goi... mot chuoi cho de quen. Chuoi nay di theo module luon.
#
#   Moi tin tra ve mang lai "fp" cua anh no noi toi: doi anh nhanh thi tin
#   cua anh cu van ve sau — phai biet ma bo.
#]]
def ort_mat() -> str:
    """Bộ dò mặt insightface đang chạy trên provider nào của onnxruntime (để ghi
    nhật ký — 7/10: bản cài cũ dò mặt bằng CPU mà không ai biết)."""
    try:
        from saytool.loi import skin_spike4 as _s4
        app = getattr(_s4, "_APP", None)
        m = (getattr(app, "models", None) or {}).get("detection") if app else None
        return (m.session.get_providers() or ["?"])[0] if m is not None else "?"
    except Exception:                                        # noqa: BLE001
        return "?"


def mps_hong() -> bool:
    """True khi torch BÁO có MPS (GPU Apple) nhưng KHÔNG chạy được thật.

    #[[ 6/10, may macOS cua GitHub Actions (may ao, khong co GPU that): MPS
    #   is_available() = True nhung nap mo hinh nao cung "MPS backend out of
    #   memory (MPS allocated: 0 bytes ...) Tried to allocate 18.00 KiB" -> 6/9
    #   buoc retouch bi bo qua. May Mac that thuong khong sao, nhung khong duoc
    #   tin is_available(): THU tinh mot phep nho, hong thi chay CPU. Phai goi
    #   SAU khi da import saytool (cli ghim so luong truoc torch). ]]
    """
    try:
        import torch
        b = getattr(torch.backends, "mps", None)
        if not (b and b.is_available()):
            return False
        x = torch.ones(1024, 1024, device="mps")      # 4 MB — co mau that, khong
        float((x @ x).sum().item())                   # chi vai KB lot qua
        return False
    except Exception:                                        # noqa: BLE001
        return True


#[[ VONG LAP TIEN TRINH CON XEM TRUOC — tach thanh HAM de dung duoc o CA HAI:
#
#   1. Chay tu MA NGUON: MayXem chay `python -c MA_CON`, MA_CON goi vong_xem().
#   2. Chay TU GOI (dong goi): frozen AutoTone.exe KHONG chay `python -c` duoc
#      (no khong phai trinh thong dich). Nen autotone_gui them co `--say-xem`:
#      no import xem_truoc.vong_xem() va chay THANG trong goi. MayXem khi frozen
#      goi [sys.executable, "--say-xem"] thay vi [python_cho, "-c", MA_CON].
#      (Cung bay voi _hoi_keo/kiem_tra/lenh_saytool: frozen exe != python.)
#
#   Nho tach ham, logic xem truoc chi viet MOT lan, hai duong goi cung no. ]]
def vong_xem():
    """Vòng lặp tiến trình con tính ảnh xem trước: đọc JSON ở stdin, trả JSON
    (ảnh nén base64) ở stdout. Dùng chung cho bản mã nguồn (qua MA_CON) và bản
    đóng gói (qua cờ --say-xem)."""
    import json as _json
    import sys as _sys
    import base64 as _b64
    import cv2 as _cv2
    import queue as _queue
    import threading as _threading
    from pathlib import Path as _Path

    #[[ MOT ONG RA DUY NHAT (7/10 — engine thuong tru). Tin JSON ghi vao stdout
    #   THAT qua mot khoa, MOT lan write moi dong. Moi print khac (insightface
    #   "Applied providers", saytool "set det-size", duong ong chay me...) di
    #   sang stderr (= xem_truoc_loi.log o ban dong goi) — truoc day chung chen
    #   vao giua dong JSON duoc thi giao dien chi viec bo dong hong, nhung tu khi
    #   me chay o luong khac thi khong duoc phep may rui nua. ]]
    _ONG_RA = _sys.stdout
    _KHOA_RA = _threading.Lock()

    def ra(**kw):
        dong_ = _json.dumps(kw) + "\n"
        with _KHOA_RA:
            _ONG_RA.write(dong_)
            _ONG_RA.flush()

    _sys.stdout = _sys.stderr

    #[[ SO LUONG torch TREN CPU (5/10 — user: ".exe keo thanh khong thay doi",
    #   ban local chay tot). saytool/loi/blem_net2.py va blem_net3.py co dong
    #   `torch.set_num_threads(2)` chay NGAY LUC NAP (buoc Xoa khuyet diem nap
    #   chung). Tren GPU (ban local) khong sao; tren CPU (ban cai .exe — torch
    #   CPU) MOI buoc sau do bi bop con 2 luong: may 32 luong ma moi lan keo mat
    #   ~15 s thay vi ~5,5 s (do that tren SAY00551). Ghi so luong mac dinh
    #   TRUOC khi saytool kip bop, nap san hai module do (dong bop chay luon bay
    #   gio, lan nap sau la no-op), roi tra lai so luong cu truoc moi lan tinh.
    #   Chi khi tinh bang CPU — GPU giu nguyen nhu saytool muon. ]]
    try:
        import torch as _torch
        _LUONG = int(_torch.get_num_threads())
    except Exception:                                        # noqa: BLE001
        _torch, _LUONG = None, 0

    try:
        from saytool.mot_anh import Bo
        from saytool.ngu_canh import NguCanh
        from saytool.buoc import tat_ca
    except Exception as e:                                   # noqa: BLE001
        ra(loai="hong", loi=f"{type(e).__name__}: {e}")
        return 1
    try:
        from saytool.cai_dat import chuan as _chuan
    except Exception:                                        # noqa: BLE001
        _chuan = None                # saytool cu / gia: khong dem, tinh ca chuoi
    for _m in ("saytool.loi.blem_net2", "saytool.loi.blem_net3"):
        try:
            __import__(_m)
        except Exception:                                    # noqa: BLE001
            pass

    BO = None
    NC = None
    FP = None
    CANH = 1400

    def mo_luong():
        if _torch is not None and _LUONG > 2 and str(getattr(BO, "dev", "")) == "cpu":
            try:
                if _torch.get_num_threads() != _LUONG:
                    _torch.set_num_threads(_LUONG)
            except Exception:                                # noqa: BLE001
                pass

    #[[ CHI TINH LAI TU BUOC VUA KEO (5/10). Cac buoc chay NOI TIEP (tat_ca()
    #   theo thu_tu): keo "Lam thon mat" thi anh sau "Xoa khuyet diem", "Lam
    #   min da"... KHONG doi — tinh lai ca chuoi moi lan keo la phi (tren CPU
    #   5-15 s). Giu anh SAU MOI BUOC cua anh dang xem, khoa bang muc cua cac
    #   buoc tu dau toi buoc do; lan sau chi chay tu buoc dau tien co muc khac.
    #   Lap DUNG vong cua saytool Bo.chay() (bat / _san_sang / _dat_phan_cung /
    #   chuan_bi / chay_may / ap) nen ket qua y het — da so tung diem anh.
    #   Luu BAN CHEP: ap() cua vai buoc sua thang vao mang dau vao. ]]
    DEM: list = []                   # [(khoa_tien_to, anh_sau_buoc)] cua anh FP
    NAP_SAN = [False]                # da nap san mo hinh (sau lan mo anh dau)

    def _khoa_buoc(b, cd):
        ten = {t.ten for t in getattr(b, "thanh_keo", [])}
        return tuple(sorted((k, cd[k]) for k in cd
                            if k in ten or str(k).rpartition(":")[2] in ten))

    def chay_dem(nc, muc):
        if _chuan is None:
            raise RuntimeError("khong co saytool.cai_dat")
        cd = _chuan(muc)
        ds = list(tat_ca())
        khoa, tich = [], ()
        for b in ds:
            tich = tich + (_khoa_buoc(b, cd),)
            khoa.append(tich)
        i0 = 0
        while i0 < len(ds) and i0 < len(DEM) and DEM[i0][0] == khoa[i0]:
            i0 += 1
        anh = DEM[i0 - 1][1].copy() if i0 > 0 else nc.anh.copy()
        del DEM[i0:]
        #[[ BUOC BI BO QUA (nap mo hinh hong) THI KHONG DEM TU DO TRO DI.
        #   Neu dem, anh "thieu buoc do" nam trong dem voi khoa binh thuong: keo
        #   thanh PHIA SAU se dung lai no -> tinh nang do mat han voi anh nay du
        #   lan sau nap duoc (loi gap that 5/10 — "keo khong thay doi"). ]]
        thieu = False
        for i in range(i0, len(ds)):
            b = ds[i]
            if b.bat(cd):
                if BO._san_sang(b, nc):
                    BO._dat_phan_cung(b, nc)
                    viec = b.chuan_bi(nc, cd)
                    if viec:
                        viec = b.chay_may(viec)
                    anh = b.ap(nc, anh, viec, cd)
                else:
                    thieu = True
            if not thieu:
                DEM.append((khoa[i], anh.copy()))
        return anh

    def bo_qua(muc):
        """[[nhãn, lý do]] các bước ĐANG BẬT mà không chạy được (nạp hỏng)."""
        try:
            cd = _chuan(muc) if _chuan is not None else dict(muc)
            hong = getattr(BO, "_hong", {}) or {}
            return [[b.nhan, str(hong[b.ten])[:200]] for b in tat_ca()
                    if b.ten in hong and b.bat(cd)]
        except Exception:                                    # noqa: BLE001
            return []

    #[[ NHAT KY NHO cua tien trinh xem truoc (5/10): ban cai khong co cua so
    #   console, loi o day truoc gio CHET LANG — phai lap ban chan doan qua OTA
    #   moi biet. Ghi su kien chinh vao <du lieu app>/xem_truoc.log (toi da
    #   ~512 KB, qua thi cat). Chi ban dong goi; chay ma nguon thi khong ghi. ]]
    _NK = None
    if getattr(_sys, "frozen", False) or os.environ.get("XEM_NHAT_KY"):
        _g = os.environ.get("AUTOTONE_DATA") or os.path.join(
            os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "AutoTone")
        _NK = os.path.join(_g, "xem_truoc.log")

    def nk(*a):
        if not _NK:
            return
        try:
            if os.path.isfile(_NK) and os.path.getsize(_NK) > 512 * 1024:
                os.replace(_NK, _NK + ".cu")
            import time as _t
            with open(_NK, "a", encoding="utf-8") as fh:
                fh.write(_t.strftime("%m-%d %H:%M:%S ") + " ".join(str(x) for x in a) + "\n")
        except Exception:                                    # noqa: BLE001
            pass

    #[[ LOI CUA saytool / onnxruntime VAO FILE (6/10). Giao dien mo tien trinh
    #   nay voi stderr=DEVNULL, nen "[!] InsightFace khong dung duoc: ..." va
    #   canh bao cua onnxruntime (in thang ra fd 2) MAT HET — user bao "tool
    #   khong thay khuon mat nao" ma khong con dau vet. Ghi vao
    #   <du lieu app>/xem_truoc_loi.log (qua ~512 KB thi ghi lai tu dau). ]]
    if _NK:
        try:
            _floi = _NK[:-4] + "_loi.log"
            _cu = os.path.isfile(_floi) and os.path.getsize(_floi) > 512 * 1024
            _fe = open(_floi, "w" if _cu else "a", encoding="utf-8",
                       errors="replace", buffering=1)
            _sys.stderr = _fe
            try:
                os.dup2(_fe.fileno(), 2)
            except Exception:                                # noqa: BLE001
                pass
        except Exception:                                    # noqa: BLE001
            pass

    #[[ Chan doan treo: XEM_VET_TREO=<giay> -> cu moi <giay> giay ghi stack moi
    #   luong vao xem_truoc_loi.log (faulthandler). Chi khi dat bien moi truong. ]]
    if os.environ.get("XEM_VET_TREO"):
        try:
            import faulthandler as _fh
            _fh.dump_traceback_later(float(os.environ["XEM_VET_TREO"]), repeat=True,
                                     file=_sys.stderr)
        except Exception:                                    # noqa: BLE001
            pass

    #[[ BO DO MAT TREN GPU RA 0 MAT -> DO LAI BANG CPU (6/10).
    #   May user (RTX 3060 Ti, ban cai kem torch CUDA): mo anh chan dung ro mat
    #   ma xem truoc bao "khong thay khuon mat nao" -> moi buoc lam mat / da
    #   khong doi. Cung goi do, chay lai thi thay mat — loi den tu bo do mat
    #   onnxruntime tren GPU, va trong goi KHONG co du phong (yunet phai tai,
    #   haar khong dong goi) nen insightface hong la ra 0 mat. Ra 0 mat ma bo
    #   do mat CHUA tung thay mat nao tren GPU trong phien nay -> do lai bang
    #   CPU (SAY_ORT_MAT=cpu, ~0,5 s). CPU thay mat: giu CPU cho do mat ca
    #   phien. CPU cung 0 mat: anh that su khong co mat -> tra lai nhu cu. ]]
    MAT = {"gpu_thay": False, "cpu": False}

    def do_lai_mat_cpu(nc):
        if MAT["cpu"] or MAT["gpu_thay"] or \
                (os.environ.get("SAY_ORT_MAT") or "").strip().lower() == "cpu":
            return []
        try:
            from saytool.loi import skin_spike4 as _s4
        except Exception:                                    # noqa: BLE001
            return []
        cu_app, cu_env = getattr(_s4, "_APP", None), os.environ.get("SAY_ORT_MAT")
        os.environ["SAY_ORT_MAT"] = "cpu"
        _s4._APP = None
        nc._mat = None
        try:
            m = list(nc.mat or [])
        except Exception as e:                               # noqa: BLE001
            nk("do lai mat CPU loi:", type(e).__name__, e)
            m = []
        if m:
            MAT["cpu"] = True
            nc.dinh[:] = [g for g in nc.dinh if "khong thay khuon mat" not in g]
            nk("do mat GPU ra 0 mat, CPU ra", len(m), "-> giu CPU cho do mat")
            return m
        if cu_env is None:
            os.environ.pop("SAY_ORT_MAT", None)
        else:
            os.environ["SAY_ORT_MAT"] = cu_env
        _s4._APP = cu_app or None
        return []

    def nen(img):
        #[[ PNG: khong mat chi tiet, ban truoc / sau so diem voi diem duoc. Anh
        #   1400px qua ong noi bo, khong qua mang. Nen muc 3: nhanh. ]]
        ok, buf = _cv2.imencode(".png", img, [_cv2.IMWRITE_PNG_COMPRESSION, 3])
        return _b64.b64encode(buf).decode("ascii") if ok else ""

    #[[ ENGINE THUONG TRU (7/10 — giai doan 1 tai cau truc): tien trinh nay
    #   CHAY CA ME ("chay") ngay trong no, mo hinh da nap san — truoc day moi
    #   lan bam Chay retouch la mot AutoTone.exe --say-chay moi, nap lai mo hinh
    #   ~4 s, va phai tat xem truoc de nhuong card. Lenh doc o LUONG RIENG: me
    #   dang chay van nhan duoc "dung_chay" / "thoat" ngay; lenh khac (mo_anh,
    #   tinh) xep hang, lam sau khi me xong — hai viec KHONG chay chong nhau vi
    #   dung chung cac buoc (dat_phan_cung, luong torch) va mot card. ]]
    Q_LENH: _queue.Queue = _queue.Queue()
    DUNG = [False]
    DANG_CHAY = [False]

    def _dong_stdin():
        """Sinh từng dòng lệnh từ stdin.

        Windows KHÔNG được để một lệnh đọc đồng bộ treo sẵn trên ống stdin ở
        luồng nền: nhân Windows xếp hàng MỌI thao tác trên cùng một file object
        đồng bộ (ReadFile đang chờ chặn cả fstat / lseek / GetFileType của luồng
        khác). Luồng chính nạp lười một DLL có chạm stdin lúc khởi tạo — libgfortran
        của scipy.linalg (insightface -> skimage -> scipy) gọi fstat(0) — là đứng
        im tới khi giao diện gửi lệnh tiếp theo (treo thật 7/10: "mo_anh" không
        bao giờ trả lời). Đọc kiểu hỏi-trước (PeekNamedPipe) rồi mới ReadFile đúng
        số byte có sẵn: không bao giờ có lệnh đọc treo, trễ tối đa ~15 ms.
        Mac / Linux: read() không khoá fstat, đọc thẳng như cũ."""
        if os.name != "nt":
            for dong_ in _sys.stdin:
                yield dong_
            return
        import msvcrt as _ms
        import _winapi as _wa
        import time as _t
        try:
            h = _ms.get_osfhandle(0)
        except OSError:
            return
        dem = b""
        while True:
            try:
                n, _ = _wa.PeekNamedPipe(h)
                if not n:
                    _t.sleep(0.015)
                    continue
                du, _ = _wa.ReadFile(h, n)
            except OSError:                              # ống đóng / không phải ống
                break
            if not du:
                break
            dem += du
            while b"\n" in dem:
                dong_, dem = dem.split(b"\n", 1)
                yield dong_.decode("utf-8", "replace")
        if dem:
            yield dem.decode("utf-8", "replace")

    def _doc_lenh():
        try:
            for dong_ in _dong_stdin():
                dong_ = dong_.strip()
                if not dong_:
                    continue
                try:
                    y_ = _json.loads(dong_)
                except Exception:                            # noqa: BLE001
                    continue
                v_ = y_.get("viec")
                if v_ == "dung_chay":
                    DUNG[0] = True
                    continue
                if v_ == "thoat":
                    DUNG[0] = True
                Q_LENH.put(y_)
                if v_ == "thoat":
                    return
        except Exception:                                    # noqa: BLE001
            pass
        Q_LENH.put({"viec": "thoat"})

    _threading.Thread(target=_doc_lenh, daemon=True).start()

    def chay_me(y):
        """Một mẻ retouch bằng chính đường ống saytool, ngay trong tiến trình này."""
        from saytool import duong_ong as _do
        import inspect as _ins
        ma = y.get("ma")
        DUNG[0] = False
        DANG_CHAY[0] = True
        n = 0
        try:
            def bao(*a, **_k):
                ra(loai="dong", ma=ma, chu=" ".join(str(x) for x in a))
            kw = dict(dev=y.get("may") or "auto", luong=int(y.get("luong") or 0),
                      chat_luong=y.get("chat_luong", "auto"),
                      de_quy=bool(y.get("de_quy")), lam_lai=bool(y.get("lam_lai")),
                      gioi_han=int(y.get("gioi_han") or 0), bao=bao,
                      che_do=y.get("che_do") or "auto", mau=y.get("mau", "auto"),
                      nguyen_ven=bool(y.get("nguyen_ven", True)),
                      ghi_de=bool(y.get("ghi_de")))
            if "dung" in _ins.signature(_do.chay).parameters:
                kw["dung"] = lambda: DUNG[0]
            nk("chay me ma=", ma, "vao=", y.get("vao"), "ra=", y.get("ra"),
               "muc=", y.get("muc"), "ghi_de=", kw["ghi_de"])
            n = _do.chay(y["vao"], y.get("ra") or y["vao"], y.get("muc") or {}, **kw)
            ra(loai="xong_chay", ma=ma, so=int(n or 0), ma_thoat=0, dung=bool(DUNG[0]))
            nk("xong me ma=", ma, "so=", n, "dung=", DUNG[0])
        except Exception as e:                               # noqa: BLE001
            nk("LOI chay me", type(e).__name__, e)
            ra(loai="xong_chay", ma=ma, so=n, ma_thoat=1, loi=f"{type(e).__name__}: {e}")
        finally:
            DUNG[0] = False
            DANG_CHAY[0] = False
            #[[ Tra phan cung ve cho xem truoc: duong ong dat luong / canh o /
            #   so luong torch theo me — xem truoc la mot anh, mot luong. ]]
            try:
                if BO is not None:
                    for _b in tat_ca():
                        BO._dat_phan_cung(_b, None)
            except Exception:                                # noqa: BLE001
                pass
            mo_luong()

    def _ort_cau_hinh() -> str:
        try:
            from saytool import thiet_bi as _tb
            p0 = _tb.providers("mat")[0]
            return p0[0] if isinstance(p0, (tuple, list)) else str(p0)
        except Exception:                                    # noqa: BLE001
            return "?"

    while True:
        y = Q_LENH.get()
        v = y.get("viec")
        try:
            if v == "khoi_dong":
                may = y.get("may", "auto")
                if may in ("auto", "mps") and mps_hong():
                    nk("MPS bao co nhung khong chay duoc -> CPU")
                    may = "cpu"
                BO = Bo(may)
                mo_luong()
                #[[ may = thiet bi THAT dang tinh ("cuda" / "cpu" / "mps") — giao
                #   dien dung de noi ro khi dang chay CPU (moi lan keo ~5-13 s
                #   tren ban cai torch CPU) va goi y tai ban tang toc GPU. ]]
                try:
                    import saytool as _st
                    _ban = str(getattr(_st, "__version__", "?"))
                except Exception:                            # noqa: BLE001
                    _ban = "?"
                ra(loai="san_sang", may=str(getattr(BO, "dev", "")),
                   keo=[{"ten": b.ten, "nhan": b.nhan} for b in tat_ca()],
                   ort=_ort_cau_hinh(), ban=_ban)
                nk("khoi_dong may=", getattr(BO, "dev", "?"), "luong=",
                   _torch.get_num_threads() if _torch is not None else "?",
                   "ort=", _ort_cau_hinh(), "saytool=", _ban)
            elif v == "chay":
                if BO is None:
                    ra(loai="xong_chay", ma=y.get("ma"), so=0, ma_thoat=1,
                       loi="chua khoi_dong")
                else:
                    chay_me(y)
            elif v == "mo_anh":
                NC = NguCanh(_Path(y["fp"]), canh_toi_da=CANH)
                FP = y["fp"]
                DEM.clear()                  # anh moi: bo dem cua anh cu
                _ = NC.anh
                H, W = NC.anh.shape[:2]
                #[[ Moi mat: [x, y, rong, cao] theo diem anh cua ban 1400px, mat
                #   TO truoc — nut "Vao mat" cua khung anh di lan luot. ]]
                ds_mat = list(NC.mat or [])
                if ds_mat:
                    MAT["gpu_thay"] = MAT["gpu_thay"] or not MAT["cpu"]
                else:
                    ds_mat = do_lai_mat_cpu(NC)
                mat = []
                for f in sorted(ds_mat, key=lambda m: -float(m.width)):
                    bx1, by1, bx2, by2 = [float(t) for t in f.bbox[:4]]
                    mat.append([bx1, by1, bx2 - bx1, by2 - by1])
                ra(loai="da_mo", fp=FP, so_mat=len(mat), mat=mat, rong=W, cao=H,
                   goc=nen(NC.anh))
                nk("mo_anh", FP, f"{W}x{H}", "mat=",
                   [(getattr(f, "src", "?"), round(float(f.width)),
                     "lmk" if getattr(f, "lmk", None) is not None else "KHONG-lmk")
                    for f in (NC.mat or [])], "ort=", ort_mat())
                #[[ NAP SAN MO HINH ngay sau lan mo anh dau (5/10): ban cai phai
                #   giai ma + nap ~6 s o lan tinh DAU — de luc do thi lan keo dau
                #   tien cho ~15 s. Giao dien da nhan "da_mo" (hien anh goc) roi;
                #   nguoi dung con dang nhin anh thi mo hinh nap xong. Nap loi
                #   thi _san_sang ghi lai nhu cu, buoc do bo qua. ]]
                if not NAP_SAN[0]:
                    NAP_SAN[0] = True
                    for _b in tat_ca():
                        try:
                            BO._san_sang(_b, NC)
                        except Exception:                    # noqa: BLE001
                            pass
                    mo_luong()
                    nk("nap san xong, hong=", dict(getattr(BO, "_hong", {}) or {}))
            elif v == "tinh":
                if NC is None or BO is None or y.get("fp") != FP:
                    ra(loai="hong", loi="chua mo anh nay", ma=y.get("ma"),
                       fp=y.get("fp"))
                    continue
                #[[ Bo.chay nho buoc nap HONG suot phien (_hong) roi lang le bo
                #   qua — mot lan hong tam (thieu RAM luc do, file dang bi khoa...)
                #   la tinh nang do chet ca phien. Xem truoc thi nap LAI moi lan
                #   tinh: hong that (thieu mo hinh) thi hong lai ngay, va bao ra. ]]
                try:
                    if getattr(BO, "_hong", None):
                        BO._hong.clear()
                except Exception:                            # noqa: BLE001
                    pass
                mo_luong()
                import time as _t
                _t0 = _t.time()
                try:
                    if os.environ.get("XEM_KHONG_DEM"):      # tat dem (so sanh / lui)
                        raise RuntimeError("khong dem")
                    out = chay_dem(NC, y["muc"])
                except Exception as _ex:                     # noqa: BLE001
                    #[[ Duong dem hong (saytool doi ham noi bo...) -> bo dem,
                    #   tinh ca chuoi bang Bo.chay nhu cu — khong duoc chet. ]]
                    if not os.environ.get("XEM_KHONG_DEM"):
                        nk("dem hong -> Bo.chay:", type(_ex).__name__, _ex)
                    DEM.clear()
                    out = BO.chay(NC, y["muc"])
                bq = bo_qua(y["muc"])
                ra(loai="ket_qua", ma=y.get("ma"), fp=FP, anh=nen(out), bo_qua=bq)
                if _NK:
                    try:
                        import numpy as _np
                        _d = (float((_np.abs(NC.anh.astype(int) - out.astype(int)).sum(2) > 3).mean()) * 100
                              if out.shape == NC.anh.shape else -1)
                    except Exception:                        # noqa: BLE001
                        _d = "?"
                    nk("tinh ma=", y.get("ma"), f"{_t.time() - _t0:.1f}s", "doi%=",
                       round(_d, 2) if isinstance(_d, float) else _d,
                       "muc=", y["muc"], "bo_qua=", bq)
            elif v == "thoat":
                break
        except Exception as e:                               # noqa: BLE001
            nk("LOI", v, type(e).__name__, e)
            ra(loai="hong", loi=f"{type(e).__name__}: {e}", ma=y.get("ma"),
               fp=y.get("fp"))
    return 0


#[[ MA_CON: ban mã nguồn chay `python -c MA_CON`. No chi import xem_truoc roi
#   goi vong_xem() — logic nam o vong_xem(), khong nhan doi. cwd = thu muc tool
#   nen `import xem_truoc` thay file nay (hoac saytool import truc tiep). Phong
#   khi xem_truoc khong nam tren sys.path cua tool, fallback import saytool va
#   dinh nghia lai o cho — nhung ban dong goi KHONG di duong nay (dung --say-xem). ]]
MA_CON = r'''
import sys
try:
    import xem_truoc
    sys.exit(xem_truoc.vong_xem())
except Exception:
    pass
# Fallback: khong import duoc xem_truoc (vi tri khac) -> chay noi dung toi thieu.
import json, base64
import cv2
from pathlib import Path
def ra(**kw):
    sys.stdout.write(json.dumps(kw) + "\n"); sys.stdout.flush()
try:
    from saytool.mot_anh import Bo
    from saytool.ngu_canh import NguCanh
    from saytool.buoc import tat_ca
except Exception as e:
    ra(loai="hong", loi=f"{type(e).__name__}: {e}"); sys.exit(1)
BO = None; NC = None; FP = None; CANH = 1400
def nen(img):
    ok, buf = cv2.imencode(".png", img, [cv2.IMWRITE_PNG_COMPRESSION, 3])
    return base64.b64encode(buf).decode("ascii") if ok else ""
for dong in sys.stdin:
    dong = dong.strip()
    if not dong: continue
    try: y = json.loads(dong)
    except Exception: continue
    v = y.get("viec")
    try:
        if v == "khoi_dong":
            BO = Bo(y.get("may", "auto"))
            ra(loai="san_sang", keo=[{"ten": b.ten, "nhan": b.nhan} for b in tat_ca()])
        elif v == "mo_anh":
            NC = NguCanh(Path(y["fp"]), canh_toi_da=CANH); FP = y["fp"]; _ = NC.anh
            H, W = NC.anh.shape[:2]
            mat = []
            for f in sorted(NC.mat or [], key=lambda m: -float(m.width)):
                bx1, by1, bx2, by2 = [float(t) for t in f.bbox[:4]]
                mat.append([bx1, by1, bx2 - bx1, by2 - by1])
            ra(loai="da_mo", fp=FP, so_mat=len(mat), mat=mat, rong=W, cao=H, goc=nen(NC.anh))
        elif v == "tinh":
            if NC is None or BO is None or y.get("fp") != FP:
                ra(loai="hong", loi="chua mo anh nay", ma=y.get("ma"), fp=y.get("fp")); continue
            out = BO.chay(NC, y["muc"]); ra(loai="ket_qua", ma=y.get("ma"), fp=FP, anh=nen(out))
        elif v == "thoat":
            break
    except Exception as e:
        ra(loai="hong", loi=f"{type(e).__name__}: {e}", ma=y.get("ma"), fp=y.get("fp"))
'''


def giai_anh(b64: str):
    """PNG base64 từ tiến trình con -> ảnh PIL RGB (None nếu hỏng)."""
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(base64.b64decode(b64)))
        im.load()
        return im.convert("RGB")
    except Exception:                                        # noqa: BLE001
        return None


class MayXem:
    """Tiến trình con tính ảnh xem trước — và từ 7/10 là ENGINE THƯỜNG TRÚ:
    chạy cả mẻ retouch (chay_me) ngay trong nó, mô hình đã nạp sẵn. Không vẽ
    gì: ai dùng thì gửi việc (gui) và bơm tin về (lay) ở luồng chính.

    Tin về (dict): san_sang{keo, may, ort, ban} · da_mo{fp, so_mat, mat, rong,
    cao, goc} · ket_qua{ma, fp, anh} · hong{loi, ma, fp} · chet{}.
    Tin của MẺ đi hàng riêng (q_chay, chay_me đọc ở luồng chạy): dong{ma, chu}
    · xong_chay{ma, so, ma_thoat, loi, dung}.
    """

    def __init__(self, rt, goc_tool: str):
        self.rt = rt
        self.goc_tool = str(goc_tool)
        self.q: queue.Queue = queue.Queue()
        self.q_chay: queue.Queue = queue.Queue()
        self.proc = None
        self._khoa_gui = threading.Lock()
        self._ma_chay = 0
        self.dang_chay = False
        #[[ Tien trinh con co biet "chay" khong: vong lap moi bao san_sang kem
        #   "ban"; vong lap toi thieu (MA_CON fallback) / ban cu thi khong ->
        #   retouch.chay di duong tien trinh con. ]]
        self.co_chay = None
        #[[ 10/10 (tram_retouch): engine dung CHUNG giua xem truoc va tram retouch
        #   cho Lightroom. Tin san_sang giu lai de nguoi dung sau (man Retouch mo lai
        #   engine da nap san) biet ngay la san sang; khoa me: hai mẻ (app chay
        #   retouch + Lightroom xuat) KHONG duoc chen nhau — chay_me tu doc hang
        #   q_chay, mẻ thu hai cho mẻ dau xong. ]]
        self.tin_san_sang = None
        self._khoa_me = threading.Lock()

    def bat_dau(self, may: str = "auto") -> str:
        """'' nếu khởi động được, không thì câu lỗi để nói ra."""
        #[[ CHON LENH CHAY TIEN TRINH CON XEM TRUOC.
        #
        #   Ban DONG GOI: PHAI `AutoTone.exe --say-xem` (chinh app chay
        #   vong_xem). KHONG duoc `python_cho(goc) -c MA_CON`: ban all-in-one
        #   khong co .venv nen python_cho() tra sys.executable = AutoTone.exe,
        #   ma frozen exe KHONG hieu `-c <code>` -> tien trinh con khong chay ->
        #   KEO THANH KHONG HIEN KET QUA tren preview (loi user bao 5/10).
        #   Cung bay voi _hoi_keo/kiem_tra/lenh_saytool. Khi frozen va goi CO
        #   saytool -> --say-xem voi sys.executable, cwd = thu muc tai nguyen
        #   (noi co saytool + mo_hinh). Chay tu ma nguon moi dung -c MA_CON.
        #]]
        try:
            import retouch as _rt_mod
            frozen = (getattr(_rt_mod, "trong_goi", lambda: False)()
                      and _rt_mod.goc_trong_goi() is not None)
        except Exception:                                    # noqa: BLE001
            frozen = bool(getattr(sys, "frozen", False))
        try:
            if frozen:
                cmd = [sys.executable, "--say-xem"]
            else:
                py = self.rt.python_cho(self.goc_tool)
                cmd = [str(py), "-c", MA_CON]
            #[[ Cung moi truong voi tien trinh chay me cu (retouch.moi_truong_con:
            #   UTF-8, PYTORCH_CUDA_ALLOC_CONF, SAY_* tu retouch.json) — tu 7/10 me
            #   chay ngay trong tien trinh nay. ]]
            lam_env = getattr(self.rt, "moi_truong_con", None)
            env = lam_env() if lam_env else dict(os.environ, **self.rt.MOI_TRUONG_UTF8)
            if not frozen:
                #[[ Chay tu ma nguon: `python -c MA_CON` voi cwd = thu muc tool, o do
                #   KHONG co xem_truoc.py -> MA_CON roi ve vong lap toi thieu (khong
                #   biet "chay", khong dem, khong nhat ky). Dua thu muc app vao
                #   PYTHONPATH de `import xem_truoc` thay dung file nay. ]]
                goc_app = str(Path(__file__).resolve().parent)
                env["PYTHONPATH"] = goc_app + os.pathsep + env.get("PYTHONPATH", "")
            self.proc = subprocess.Popen(
                cmd, cwd=self.goc_tool,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                errors="replace", bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                env=env)
        except Exception as ex:                              # noqa: BLE001
            self.proc = None
            return f"Không chạy được Python của tool: {type(ex).__name__}: {ex}"
        self.dang_chay = False
        threading.Thread(target=self._doc, daemon=True).start()
        self.gui(viec="khoi_dong", may=may or "auto")
        return ""

    def _doc(self):
        p = self.proc
        try:
            for dong in p.stdout:
                dong = dong.strip()
                if dong.startswith("{"):
                    try:
                        d = json.loads(dong)
                    except Exception:                        # noqa: BLE001
                        continue
                    if d.get("loai") == "san_sang":
                        self.co_chay = "ban" in d
                        self.tin_san_sang = dict(d)
                    (self.q_chay if d.get("loai") in ("dong", "xong_chay") else self.q).put(d)
        except Exception:                                    # noqa: BLE001
            pass
        self.q.put({"loai": "chet"})
        self.q_chay.put({"loai": "chet"})

    def gui(self, **kw) -> bool:
        p = self.proc
        if not p or p.poll() is not None:
            return False
        try:
            with self._khoa_gui:                # luong chay me va luong chinh cung gui
                p.stdin.write(json.dumps(kw) + "\n")
                p.stdin.flush()
            return True
        except OSError:
            return False

    def chay_me(self, tham: dict):
        """Chạy MỘT mẻ trong tiến trình này (gọi ở luồng nền). Sinh ("dong", chữ)…
        rồi ("ma", mã thoát): 0 xong, 1 lỗi đường ống, mã tiến trình nếu nó chết
        giữa chừng (để vòng tự-chạy-lại của giao diện nhận ra 0xC0000005...).
        Mẻ khác đang chạy (trạm retouch / app) thì chờ nó xong."""
        with self._khoa_me:
            yield from self._chay_me(tham)

    def _chay_me(self, tham: dict):
        try:
            while True:
                self.q_chay.get_nowait()
        except queue.Empty:
            pass
        self._ma_chay += 1
        ma = self._ma_chay
        self.dang_chay = True
        try:
            if not self.gui(viec="chay", ma=ma, **tham):
                yield ("dong", "  ! máy xem trước không nhận được lệnh chạy")
                yield ("ma", 1)
                return
            while True:
                d = self.q_chay.get()
                t = d.get("loai")
                if t == "chet":
                    p = self.proc
                    rc = p.poll() if p is not None else None
                    yield ("dong", f"  ! tiến trình engine đã dừng giữa mẻ (mã {rc})")
                    yield ("ma", int(rc) if rc else 3221225477)
                    return
                if d.get("ma") != ma:
                    continue                      # tin của mẻ cũ
                if t == "dong":
                    yield ("dong", str(d.get("chu", "")))
                elif t == "xong_chay":
                    if d.get("loi"):
                        yield ("dong", f"  ! {d['loi']}")
                    yield ("ma", int(d.get("ma_thoat") or 0))
                    return
        finally:
            self.dang_chay = False

    def dung_chay(self) -> bool:
        """Xin dừng mẻ đang chạy: ảnh đang làm xong thì thôi, không giết tiến trình."""
        return self.gui(viec="dung_chay")

    def lay(self) -> list:
        ra = []
        try:
            while True:
                ra.append(self.q.get_nowait())
        except queue.Empty:
            pass
        return ra

    def song(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def chay_duoc(self, cho: float = 60.0) -> bool:
        """Đang sống VÀ biết chạy mẻ (san_sang có 'ban'). Mới mở, chưa kịp
        san_sang (đang nạp mô hình ~4 s): CHỜ tới `cho` giây — lệnh trong tiến
        trình con xử lý tuần tự nên chờ xong là gửi được ngay; đi đường tiến
        trình con lúc này cũng phải nạp mô hình chừng ấy."""
        het = time.monotonic() + cho
        while self.song() and self.co_chay is None and time.monotonic() < het:
            time.sleep(0.1)
        return self.song() and bool(self.co_chay)

    def dong(self) -> None:
        self.gui(viec="thoat")
        p = self.proc
        if p and p.poll() is None:
            try:
                p.terminate()
            except OSError:
                pass
        self.proc = None
