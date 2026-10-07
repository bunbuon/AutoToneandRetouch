#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cua_saytool.py — Cửa chạy saytool ngay trong app (tách từ autotone_gui.py, 7/10).

Bản đóng gói không có python riêng: `AutoTone.exe --say-chay / --say-keo /
--say-kiem / --say-tainguyen / --say-key / --say-tim / --say-xem` đi vào
_cua_saytool() rồi gọi thẳng saytool / xem_truoc.vong_xem trong tiến trình
này. _tro_insightface() trỏ insightface vào buffalo_l nằm trong gói.
autotone_gui.main() gọi sang đây; không import ngược autotone_gui.
"""

from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))



_IF_DA_TRO = []


def _tro_insightface(kho) -> None:
    """Cho insightface đọc buffalo_l NGAY TRONG GÓI, không qua ~/.insightface.

    #[[ 6/10 — user: cai ban moi xong van "tool khong thay khuon mat nao".
    #
    #   xem_truoc_loi.log: "InsightFace khong dung duoc: [WinError 448] The path
    #   cannot be traversed because it contains an untrusted mount point:
    #   'C:\\Users\\ipmac\\.insightface\\models'". ~/.insightface tren may user la
    #   JUNCTION sang o F: (doi cho cho o C). Inno Setup 6.5+ bat RedirectionGuard
    #   cho tien trinh Setup, app mo tu trang cuoi bo cai (postinstall) KE THUA no
    #   (tien trinh con cung vay — da thu) -> khong di qua junction do nguoi dung
    #   tao duoc -> insightface hong, yunet khong tai duoc vao Program Files -> 0
    #   mat -> moi buoc mat / da khong doi. Mo app tu Start menu thi khong co guard
    #   (vi vay truoc do khong tai hien duoc).
    #
    #   Truoc day CHEP buffalo_l sang ~/.insightface (_dat_buffalo) vi saytool goi
    #   FaceAnalysis(name="buffalo_l") khong truyen root. Nay doi MAC DINH root cua
    #   FaceAnalysis sang ban trong goi (thu muc that, chi doc, khong junction) —
    #   khong sua ToolCloneEvoto, khong ghi 326 MB vao ho so nguoi dung.
    #   INSIGHTFACE_HOME cho _thu_muc_ghim (duong DirectML) doc cung cho. ]]
    """
    import os
    goc_if = Path(kho) / "insightface"
    if not (goc_if / "models" / "buffalo_l").is_dir():
        return
    os.environ["INSIGHTFACE_HOME"] = str(goc_if)
    if _IF_DA_TRO:
        return
    try:
        from insightface.app import face_analysis as _fa
    except Exception:                                        # noqa: BLE001
        return
    cu = _fa.FaceAnalysis.__init__

    def __init__(self, name="buffalo_l", root="~/.insightface",
                 allowed_modules=None, **kw):
        if root == "~/.insightface":
            root = str(goc_if)
        cu(self, name, root, allowed_modules, **kw)

    _fa.FaceAnalysis.__init__ = __init__
    _IF_DA_TRO.append(True)


def _cua_saytool(co: str, tham: list) -> int:
    """Làm việc của saytool trong chính tiến trình này. -> mã thoát.

    Ba cửa, khớp với ba hằng CO_SAY_* trong retouch.py:
        --say-chay   chạy retouch thật, tham số y hệt saytool.cli
        --say-keo    in JSON danh sách thanh kéo saytool đang có
        --say-kiem   kiểm thư viện, in ra đúng dạng mà retouch.kiem_tra() đọc
    """
    #[[ EP UTF-8 CHO MOI CUA --say-*.
    #
    #   Console Windows mac dinh cp1252, khong ma hoa noi chu Viet. Cac cua nay
    #   in loi bang tieng Viet ("ly do: Máy này chưa kích hoạt..."), nen bat cu
    #   cua nao cham vao mot chuoi co dau la NEM UnicodeEncodeError — va trong
    #   ban .exe no hien ra thanh hop thoai "Failed to execute script", trong
    #   y het mot ban build hong.
    #
    #   Da dinh dung bon lan o bon cho khac nhau (cli.py, dong_goi.py,
    #   kiem_cu_phap.py, va --say-key). Ep mot lan ngay day thi moi cua sau nay
    #   deu khoi dinh lai.
    #]]
    for _luong in (sys.stdout, sys.stderr):
        try:
            _luong.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass

    #[[ mo_hinh/vet.pt, mo_hinh/nong_cam.pt va mo_hinh/liquify/ deu la DUONG DAN
    #   TUONG DOI trong saytool, tinh theo thu muc dang dung. Trong goi thi
    #   chung nam canh saytool o thu muc tai nguyen, nen phai chuyen sang do.
    #   Khong lam thi retouch chet ngay o anh dau: FileNotFoundError 'mo_hinh/vet.pt'.
    #]]
    import os
    try:
        import duong_dan as _dd
        tn = str(_dd.goc_tai_nguyen())
        if os.path.isdir(os.path.join(tn, "mo_hinh")):
            os.chdir(tn)
        if tn not in sys.path:
            sys.path.insert(0, tn)
    except Exception:                                        # noqa: BLE001
        pass

    #[[ Tro cac mo hinh saytool VON TU TAI ve ban da nam san trong goi. Hai bien
    #   moi truong nay la cua chinh saytool (skin_spike4.py dong 98 va 337), nen
    #   khong phai sua mot dong nao ben ToolCloneEvoto.
    #]]
    try:
        import duong_dan as _dd
        kho = _dd.goc_tai_nguyen() / "mo_hinh"
        os.environ.setdefault("SKIN_SPIKE_CACHE", str(kho))
        fp = kho / "resnet34_faceparse.onnx"
        if fp.is_file():
            os.environ.setdefault("FACE_PARSE_ONNX", str(fp))
        if co not in ("--say-keo", "--say-key", "--say-tainguyen"):
            _tro_insightface(kho)
    except Exception:                                        # noqa: BLE001
        pass

    #[[ macOS: onnxruntime (do mat insightface + phan vung da) chay CPU, KHONG
    #   CoreML. 6/10, ban Mac dau tien co du insightface: tren may build Actions
    #   bo do mat insightface ra 0 mat (khong bao loi) va lui ve yunet — khong
    #   diem moc -> moi tinh nang can moc mat khong doi. det_10g khai bao hinh
    #   dang DONG [1,3,?,?] (cung ly do DirectML phai ghim hinh dang, xem
    #   saytool/thiet_bi.py); CoreML chua tung duoc thu tren may Mac that. CPU
    #   Apple Silicon do mat ~0,1-0,2 s/anh, du nhanh. setdefault: van ep tay
    #   duoc bang SAY_ORT / SAY_ORT_MAT. ]]
    if sys.platform == "darwin":
        os.environ.setdefault("SAY_ORT", "cpu")
    #[[ Windows (7/10): goi mang onnxruntime-gpu. May KHONG co card NVIDIA thi noi
    #   ORT dung CPU ngay — khong de no thu CUDA (thieu DLL -> in loi do roi moi
    #   lui ve CPU, moi phien mot lan). May co card: CUDA, DLL lay tu torch/lib
    #   cua goi kem (saytool/cuda_dll.py). ]]
    if sys.platform.startswith("win"):
        try:
            import tai_nguyen as _tn
            if not _tn.co_card_nvidia():
                os.environ.setdefault("SAY_ORT", "cpu")
        except Exception:                                    # noqa: BLE001
            pass

    #[[ --say-xem: VONG LAP XEM TRUOC trong goi (keo thanh -> hien ket qua ngay).
    #
    #   Ban mã nguồn chay `python -c MA_CON`; ban DONG GOI khong chay `-c` duoc
    #   (frozen exe != python) nen MayXem.bat_dau() goi `AutoTone.exe --say-xem`.
    #   No chay xem_truoc.vong_xem() — doc JSON o stdin, tra anh nen o stdout —
    #   dung logic y het ban mã nguồn (cung ham). Da chdir sang thu muc tai
    #   nguyen + set model env o tren nen saytool nap duoc mo_hinh/*.pt. ]]
    if co == "--say-xem":
        try:
            import xem_truoc
            return int(xem_truoc.vong_xem() or 0)
        except Exception as ex:                              # noqa: BLE001
            import json as _json
            sys.stdout.write(_json.dumps(
                {"loai": "hong", "loi": f"{type(ex).__name__}: {ex}"}) + "\n")
            sys.stdout.flush()
            return 1

    if co == "--say-keo":
        import json
        try:
            from saytool.buoc import moi_thanh_keo
            ds = [[t.ten, t.nhan, float(t.mac_dinh), t.goi_y,
                   bool(getattr(_b, "can_torch", False))]
                  for _b, t in moi_thanh_keo()]
        except Exception as ex:                              # noqa: BLE001
            print(f"  ! khong doc duoc thanh keo: {type(ex).__name__}: {ex}")
            return 1
        sys.stdout.write("@@KEO@@" + json.dumps(ds, ensure_ascii=False))
        return 0

    #[[ --say-tainguyen: hoi ban DA DONG GOI xem trinh tai co song khong.
    #
    #   Can thiet vi ban nhe song bang tai_nguyen.py, ma duong import cua no
    #   trong diem vao nam trong try/except — thieu han no thi app van chay
    #   binh thuong, chi la khong bao gio tai duoc gi. Chay co nay tren goi
    #   vua build la biet ngay, khong phai doi nguoi dung bam Retouch moi lo.
    #]]
    #[[ --say-key: kiem ban quyen tren goi DA DONG.
    #
    #   Cung ly do voi --say-tainguyen: ban_quyen duoc import o dau file nen
    #   thieu no thi app sap ngay, nhung con CAP_KEY lot vao goi thi khong co
    #   dau hieu gi het — app chay binh thuong, chi la khach tu sinh key duoc.
    #   Co nay kiem ca hai chieu tren chinh goi vua build.
    #]]
    if co == "--say-key":
        try:
            import ban_quyen as _bq
        except Exception as ex:                               # noqa: BLE001
            print(f"THIEU BAN QUYEN: {type(ex).__name__}: {ex}")
            return 1
        #[[ Co the kem mot key de KICH HOAT luon: `AutoTone.exe --say-key <KEY>`.
        #
        #   Can cho hai viec: kiem duoc ca duong kich hoat tren goi da dong
        #   (giao dien thi phai bam tay), va cuu ho tu xa khi khach khong mo
        #   noi giao dien — doc lenh cho ho go vao Command Prompt.
        #]]
        if tham:
            _ok, _nhan = _bq.kich_hoat(tham[0])
            print(("" if _ok else "[!] ") + _nhan)
            if not _ok:
                return 1
        _g = _bq.kiem()
        print(f"may     : {_g['may']}")
        print(f"co phep : {_g['co_phep']}")
        print(f"goi     : {_g['goi'] or '(chua kich hoat)'}")
        if _g["het_han"]:
            print(f"han den : {_g['het_han'].astimezone():%H:%M %d/%m/%Y}")
        if _g["ly_do"]:
            print(f"ly do   : {_g['ly_do']}")
        #[[ Canh chuyen mat tien: cap_key.py lot vao goi. ]]
        try:
            import cap_key                                    # noqa: F401
            print("NGUY HIEM: cap_key.py NAM TRONG GOI — khach tu sinh key duoc!")
            return 1
        except ImportError:
            print("cap_key : khong co trong goi (dung)")
        return 0

    if co == "--say-tainguyen":
        try:
            import tai_nguyen as tn
        except Exception as ex:                               # noqa: BLE001
            print(f"THIEU TRINH TAI: {type(ex).__name__}: {ex}")
            return 1
        print(f"kho   : {tn.goc()}")
        print(f"can   : {', '.join(tn.can_cho_retouch()) or '(du)'}")
        for g in tn.tinh_trang():
            print(f"  {'[x]' if g['da_co'] else '[ ]'} {g['ten']:<10}"
                  f" {g['mb']:>5} MB  {g.get('mo_ta','')}")
        return 0

    if co == "--say-kiem":
        thieu = []
        for m in ("torch", "cv2", "numpy", "saytool"):
            try:
                __import__(m)
            except Exception as ex:                           # noqa: BLE001
                thieu.append(f"{m}: {type(ex).__name__}")
        print("THIEU:" + ";".join(thieu) if thieu else "OK")
        try:
            import saytool
            print("phien ban", getattr(saytool, "__version__", "?"))
        except Exception:                                     # noqa: BLE001
            pass
        return 1 if thieu else 0

    #[[ CHAN DOAN (--say-tim): in ra tim_tool / goc_trong_goi / la_goc_trong_goi
    #   + thu thanh_keo() de xem vi sao self-check bao "CHI CO ban du phong".
    #   Chi de go loi; khong anh huong nguoi dung. ]]
    if co == "--say-tim":
        import retouch as _rt
        _b = _rt.goc_trong_goi()
        _g = _rt.tim_tool()
        print("trong_goi    :", _rt.trong_goi())
        print("goc_trong_goi:", _b)
        print("tim_tool     :", _g)
        print("la_goc_trong_goi(tim_tool):",
              _rt.la_goc_trong_goi(_g) if _g else "n/a")
        try:
            _ds = _rt.thanh_keo(_g, lam_lai=True)
            print("thanh_keo so luong:", len(_ds))
            print("thanh_keo ten:", [t[0] for t in _ds])
        except Exception as _ex:                              # noqa: BLE001
            print("thanh_keo loi:", type(_ex).__name__, _ex)
        try:
            _loi = _rt._LOI_KEO.get(str(_g), "")
            print("_LOI_KEO:", (_loi[:500] if _loi else "(rong)"))
        except Exception:                                     # noqa: BLE001
            pass
        return 0

    from saytool.cli import main as say_main
    #[[ SO LUONG torch KHI CHAY HANG LOAT (5/10 — user: "sua not nut Chay
    #   retouch"). saytool/loi/blem_net2.py (+ blem_net3) co dong
    #   `torch.set_num_threads(2)` chay LUC NAP — ma no bi nap MUON, giua luc
    #   xu ly anh dau, SAU khi duong_ong.chay() da dat so luong theo may
    #   (duong_ong.py:248). Do that tren CPU: 248 dat 3, 4 s sau blem_net2:37
    #   bop con 2, moi buoc moi anh chay 2 luong. Tren GPU vo hai (248 cung dat
    #   2) nen ban local khong lo.
    #
    #   Nap san hai module do NGAY DAY: dong bop chay bay gio, roi chay() dat
    #   lai dung so luong, lan nap muon sau la no-op. Phai SAU `import
    #   saytool.cli` — cli goi ghim_luong() luc import, phai truoc torch. ]]
    for _m in ("saytool.loi.blem_net2", "saytool.loi.blem_net3"):
        try:
            __import__(_m)
        except Exception:                                    # noqa: BLE001
            pass
    #[[ MPS bao co ma khong chay duoc (may ao macOS) -> chay CPU thay vi de
    #   moi buoc nap mo hinh hong — xem xem_truoc.mps_hong(). ]]
    if sys.platform == "darwin" and "--may" in tham:
        i = tham.index("--may")
        if i + 1 < len(tham) and tham[i + 1] in ("auto", "mps"):
            try:
                from xem_truoc import mps_hong
                if mps_hong():
                    tham = tham[:i + 1] + ["cpu"] + tham[i + 2:]
                    print("  MPS báo có nhưng không chạy được — chạy bằng CPU.", flush=True)
            except Exception:                                # noqa: BLE001
                pass
    return int(say_main(tham) or 0)
