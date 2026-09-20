#!/usr/bin/env python3
"""Chẩn đoán khâu Phân tích — vì sao thư mục N ảnh mà chỉ ra được vài ảnh.

VÌ SAO CÓ FILE NÀY
    Máy Mac không nối được vào phiên làm việc, nên không ai nhìn tận mắt được.
    File này chạy ngay trên máy đó, GỌI CHÍNH mấy hàm thật của app (không chép
    lại một dòng logic nào) rồi ghi ra một bản báo cáo để gửi về.

    Nguyên tắc: chỉ ĐỌC. Không sửa file nào, không ghi .xmp, không đụng ảnh.

Chạy:
    python3 chan_doan.py "/duong/dan/thu/muc/anh"
    (hoặc bấm đúp CHAN_DOAN_MAC.command rồi kéo thả thư mục vào)
"""
from __future__ import annotations

import io
import os
import platform
import sys
import traceback
from collections import Counter
from pathlib import Path

GOC = Path(__file__).resolve().parent
sys.path.insert(0, str(GOC))

RA = io.StringIO()


def d(*a):
    print(*a)
    print(*a, file=RA)


def muc(ten):
    d("")
    d("=" * 68)
    d("  " + ten)
    d("=" * 68)


def bao_plugin() -> int:
    """In ra ĐÚNG thư mục plugin phải Add, và dựng nó nếu chưa có.

    #[[ VI SAO CAN MOT CHE DO RIENG CHO VIEC NAY.
    #
    #   Duong dan plugin KHAC NHAU tuy cach chay:
    #     chay tu ma nguon  -> AutoTone.lrplugin nam ngay canh file .py
    #     chay tu .app      -> ~/Library/Application Support/AutoTone/...
    #   Ban chep ra Application Support chi duoc tao khi .app chay LAN DAU. Neu
    #   nguoi dung chua mo .app lan nao (hoac mo ban khac) thi thu muc do CHUA
    #   TON TAI — va ho di tim mai khong thay, dung nhu 11/9.
    #
    #   Nen o day in ca hai, noi ro cai nao dang co, va neu ban Application
    #   Support chua co thi DUNG LUON cho ho — khong bat ho tu chep tay.
    #]]
    """
    import shutil
    import datetime as _dt
    try:
        import duong_dan as dd
        import autotone as at
    except Exception as ex:                                  # noqa: BLE001
        d(f"  Không nạp được mã app: {type(ex).__name__}: {ex}")
        return ghi_ra(1)

    muc("THƯ MỤC PLUGIN LIGHTROOM")
    canh = GOC / "AutoTone.lrplugin"
    kho = Path(os.path.expanduser("~")) / "Library" / "Application Support" \
        / "AutoTone" / "AutoTone.lrplugin"

    def ta(p_: Path) -> str:
        if not p_.is_dir():
            return "CHƯA CÓ"
        jobs = p_ / "jobs"
        n = len(list(jobs.glob("export_*.tsv"))) if jobs.is_dir() else 0
        t = ""
        if jobs.is_dir():
            moi_nhat = max((f.stat().st_mtime for f in jobs.glob("*")),
                           default=0.0)
            if moi_nhat:
                t = f", jobs sửa lần cuối {_dt.datetime.fromtimestamp(moi_nhat):%d/%m %H:%M}"
        return f"có ({n} bản xuất{t})"

    d(f"  cạnh mã nguồn      : {canh}")
    d(f"                       {ta(canh)}")
    d("")
    d(f"  Application Support: {kho}")
    d(f"                       {ta(kho)}")

    #[[ Chua co thi dung luon tu ban canh ma nguon — KHONG chep jobs/ theo, vi
    #   do la trang thai cua may khac va se thanh mot ban xuat cu ngay tu dau. ]]
    if not kho.is_dir() and canh.is_dir():
        try:
            kho.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(canh, kho, ignore=shutil.ignore_patterns("jobs"))
            (kho / "jobs").mkdir(parents=True, exist_ok=True)
            d("")
            d("  >>> Chưa có nên TÔI VỪA DỰNG XONG bản ở Application Support.")
            d(f"      {kho}")
        except OSError as ex:
            d(f"  [!] Không dựng được: {ex}")

    d("")
    d("  ======================================================")
    d("   Add vào Lightroom bản nào?")
    d("  ======================================================")
    d("   · Chạy AutoTone.app  ->  bản Application Support")
    d("   · Chạy từ mã nguồn   ->  bản cạnh mã nguồn")
    d("")
    d("   Không chắc đang chạy bản nào thì mở app, vào khâu 3, bấm nút")
    d("   plugin — nó in ra đúng đường dẫn app ĐANG dùng.")
    d("")
    d("   Trong hộp thoại Add của Lightroom, bấm Cmd+Shift+G rồi dán đường")
    d("   dẫn — thư mục Library bị Finder ẩn nên không bấm tới được.")
    try:
        d("")
        d(f"  App (chạy từ đây) đang dùng: {at.LR_PLUGIN_DIR}")
    except Exception:                                        # noqa: BLE001
        pass
    return ghi_ra(0)


def bao_mot_anh(duong) -> int:
    """In MỌI số đo thô của MỘT tấm ảnh, để so hai máy với nhau.

    #[[ VI SAO PHAI SO SO DO THO, KHONG SO CON SO dEV TREN BANG.
    #
    #   11/9: cung mot tam, Windows ra dEV -0.26 con Mac ra +1.20. Nhin con so
    #   cuoi thi khong the biet lech o dau, vi dEV KHONG chi phu thuoc tam anh
    #   do — no con phu thuoc CA ME:
    #
    #     * che do "scene" (mac dinh) tinh delta so voi TRUNG VI CUA CANH. Doi
    #       so anh trong me la doi moc, tuc doi delta cua MOI tam.
    #     * che do "face" con lay trung vi ca me de quy hai thang do ve mot.
    #     * muc dich (target) va bo tham so da hoc (gu.json) co the khac nhau
    #       giua hai may.
    #
    #   Nen: in ra so do THO cua rieng tam do — thu khong phu thuoc me nao ca.
    #   Neu hai may ra so do tho GIONG NHAU thi lech nam o boi canh (so anh,
    #   cau hinh), khong phai o cach doc anh. Neu so do tho da khac thi loi nam
    #   o thu vien giai nen — hai huong sua hoan toan khac nhau.
    #]]
    """
    import json as _json
    try:
        import autotone as at
    except Exception as ex:                                  # noqa: BLE001
        d(f"  Không nạp được autotone: {type(ex).__name__}: {ex}")
        return ghi_ra(1)

    p_ = Path(duong).expanduser()
    muc("SỐ ĐO THÔ CỦA MỘT ẢNH")
    d(f"  file : {p_}")
    if not p_.is_file():
        d("  [!] Không có file này.")
        return ghi_ra(1)
    d(f"  cỡ   : {p_.stat().st_size} byte")
    d("")
    d(f"  python {sys.version.split()[0]} · {platform.platform()}")
    for m in ("numpy", "PIL", "cv2"):
        try:
            d(f"  {m:<6}: {getattr(__import__(m), '__version__', '?')}")
        except Exception as ex:                              # noqa: BLE001
            d(f"  {m:<6}: THIẾU ({type(ex).__name__})")

    cfg = dict(at.DEFAULTS)
    d("")
    d(f"  cách đo: {cfg['meter']} · cân trắng: {cfg['wb']} · "
      f"preview_px: {cfg['preview_px']}")
    #[[ Bo tham so DA HOC co the khac nhau giua hai may — no nam trong gu.json
    #   o thu muc du lieu, va thu muc do KHONG di theo bo cai. Phai in ra. ]]
    try:
        gu = at.nap_gu()
        d(f"  gu đã học: {len(gu)} tham số" + (f" — {at.mo_ta_gu()}" if gu else " (chưa học gì)"))
    except Exception as ex:                                  # noqa: BLE001
        d(f"  gu đã học: không đọc được ({type(ex).__name__})")

    #[[ BO NHAN DIEN MAT — nghi pham hang dau cua vu lech 1,46 EV.
    #
    #   O che do do "face" (mac dinh), anh THAY MAT do theo do sang khuon mat,
    #   anh KHONG thay mat phai lui ve thang do chu the — hai thang khac nhau,
    #   va decide() bu chenh bang trung vi cua nhung anh co CA HAI.
    #
    #   Neu tren mot may bo nhan dien khong chay duoc thi KHONG anh nao co
    #   metered_face_ev: khong con anh nao de tinh do lech, bu thanh 0, trong
    #   khi muc dich van lay theo thang MAT (face_target_ev). Ket qua la ca me
    #   lech di mot khoang gan nhu co dinh — dung hinh dang cua 1,46 EV.
    #
    #   Va face_detector() NUOT MOI LOI roi tra None. Nen nhin tu ngoai khong
    #   co dau hieu gi: anh van do duoc, chi la do bang thang khac.
    #]]
    d("")
    d(f"  file mô hình mặt: {at.FACE_MODEL}")
    d(f"                    {'CÓ' if at.FACE_MODEL.is_file() else 'KHÔNG CÓ — đây là lỗi'}")
    try:
        bo = at.face_detector()
        d(f"  bộ nhận diện    : {'chạy được' if bo is not None else 'KHÔNG chạy được'}")
        if bo is None:
            d("  [!] Không nhận diện được mặt thì mọi ảnh lùi về thang “chủ thể”,")
            d("      trong khi mục đích vẫn lấy theo thang “mặt” — lệch cả mẻ một")
            d("      khoảng gần như cố định. Đây rất có thể là nguyên nhân.")
    except Exception as ex:                                  # noqa: BLE001
        d(f"  bộ nhận diện    : NỔ — {type(ex).__name__}: {ex}")

    r = at.measure(p_, cfg["preview_px"], cfg["meter"],
                   cfg["meter_highlight_cut"])
    d("")
    if not r.get("ok"):
        d(f"  [!] ĐO HỎNG: {r.get('error')}")
        return ghi_ra(1)

    #[[ In het, khong loc — cai minh nghi la khong quan trong lai hay la cho
    #   lech. Bo cac truong qua dai (histogram) cho ban bao cao con doc duoc. ]]
    bo = {"hist", "hist_log", "crs", "atn"}
    d("  ---- số đo thô (giống nhau ở hai máy thì lỗi KHÔNG ở khâu đọc ảnh) ----")
    for k in sorted(r):
        if k in bo:
            continue
        v = r[k]
        if isinstance(v, float):
            d(f"    {k:<26} {v:+.6f}")
        else:
            d(f"    {k:<26} {v}")
    d("")
    d("  Mấy dòng đáng so nhất: metered_ev, metered_face_ev, metered_focus_ev,")
    d("  metered_subject_ev, iso, ev_exif, w, h.")
    #[[ Neu mot may co metered_face_ev con may kia khong, thi khong can so gi
    #   them nua — do chinh la cho lech. ]]
    if r.get("metered_face_ev") is None:
        d("")
        d("  >>> ẢNH NÀY KHÔNG CÓ metered_face_ev — tức KHÔNG thấy mặt nào.")
        d("      Nếu máy kia CÓ số này cho cùng tấm ảnh thì không phải so tiếp:")
        d("      đó chính là chỗ lệch. Xem dòng “bộ nhận diện” ở trên.")
    else:
        d(f"  (ảnh này CÓ thấy mặt: metered_face_ev = {r['metered_face_ev']:+.4f})")
    d("")
    d("  Chạy ĐÚNG lệnh này trên máy kia rồi so hai bản báo cáo:")
    d(f"    python3 chan_doan.py --anh \"{p_.name}\"")
    return ghi_ra(0)


def main(argv=None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if args and args[0] == "--plugin":
        return bao_plugin()
    if args and args[0] == "--anh":
        if len(args) < 2:
            print("  Dùng: python3 chan_doan.py --anh <đường dẫn ảnh>")
            return 1
        return bao_mot_anh(args[1])
    thu_muc = Path(args[0]).expanduser() if args else None

    muc("1. MÁY VÀ MÔI TRƯỜNG")
    d(f"  hệ điều hành : {platform.platform()}")
    d(f"  kiến trúc    : {platform.machine()}")
    d(f"  python       : {sys.version.split()[0]}  ({sys.executable})")
    d(f"  đóng gói     : {'CÓ (chạy từ .app)' if getattr(sys, 'frozen', False) else 'không (chạy từ mã nguồn)'}")
    try:
        import tkinter
        d(f"  Tk           : {tkinter.TkVersion}")
    except Exception as ex:                                  # noqa: BLE001
        d(f"  Tk           : KHÔNG NẠP ĐƯỢC — {type(ex).__name__}: {ex}")
    #[[ Thieu mot trong ba module nay thi moi anh deu do hong — nhung app bat
    #   loi tung anh nen nhin ra ngoai chi thay "it anh qua duoc". ]]
    for m in ("numpy", "PIL", "cv2"):
        try:
            mod = __import__(m)
            d(f"  {m:<13}: {getattr(mod, '__version__', '?')}")
        except Exception as ex:                              # noqa: BLE001
            d(f"  {m:<13}: THIẾU — {type(ex).__name__}: {ex}")

    muc("2. NẠP ĐƯỢC MÃ CỦA APP KHÔNG")
    try:
        import autotone as at
        d(f"  autotone.py  : nạp được ({len(at.RAW_EXTS)} đuôi RAW nhận biết)")
    except Exception:                                        # noqa: BLE001
        d("  autotone.py  : NẠP KHÔNG ĐƯỢC")
        d(traceback.format_exc())
        return ghi_ra(1)
    try:
        import duong_dan as dd
        kho = dd.goc_du_lieu()
        d(f"  thư mục dữ liệu: {kho}")
        d(f"  ghi được       : {'có' if os.access(kho, os.W_OK) else 'KHÔNG — đây là lỗi'}")
    except Exception as ex:                                  # noqa: BLE001
        d(f"  duong_dan.py : {type(ex).__name__}: {ex}")

    if not thu_muc:
        muc("KẾT")
        d("  Chưa cho thư mục ảnh. Chạy lại kèm đường dẫn thư mục.")
        return ghi_ra(1)

    muc("3. THƯ MỤC ẢNH")
    d(f"  đường dẫn    : {thu_muc}")
    if not thu_muc.is_dir():
        d("  [!] KHÔNG PHẢI THƯ MỤC hoặc không đọc được.")
        return ghi_ra(1)
    d(f"  đọc được     : {'có' if os.access(thu_muc, os.R_OK) else 'KHÔNG'}")
    #[[ Duong dan co dau tieng Viet: OpenCV tren Windows mo khong duoc. Tren
    #   macOS thi mo duoc, nhung van ghi ra de con biet khi so hai may. ]]
    khong_ascii = [c for c in str(thu_muc) if ord(c) > 127]
    if khong_ascii:
        d(f"  [ ] đường dẫn có ký tự ngoài ASCII: {''.join(sorted(set(khong_ascii)))}")

    tat_ca = sorted(p for p in thu_muc.iterdir() if p.is_file())
    dem = Counter(p.suffix for p in tat_ca)
    d(f"  tổng số file : {len(tat_ca)}")
    for duoi, n in sorted(dem.items(), key=lambda x: -x[1]):
        d(f"      {duoi or '(không đuôi)':<12} {n}")

    #[[ File "._TEN" la resource fork macOS de lai khi chep qua exFAT/NTFS.
    #   Chung co dung duoi .ARW nen NHIN QUA giong anh that, va neu dem tay thi
    #   ra so khac han so app doc duoc. ]]
    apple = [p for p in tat_ca if p.name.startswith("._")]
    an = [p for p in tat_ca if p.name.startswith(".") and not p.name.startswith("._")]
    if apple:
        d(f"  [ ] {len(apple)} file “._…” (rác macOS để lại khi chép qua USB) — "
          f"app bỏ qua, nhưng đếm tay thì lệch")
    if an:
        d(f"  [ ] {len(an)} file ẩn khác")

    muc("4. APP ĐẾM ĐƯỢC BAO NHIÊU — GỌI CHÍNH HÀM THẬT")
    #[[ Goi at.collect_pairs() chu khong tu viet lai vong lap. Viet lai thi bai
    #   chan doan se dung, ma app van sai — dung cai bay can tranh nhat. ]]
    for ten, can_sc in (("chế độ .xmp  (cần sidecar)", True),
                        ("chế độ catalog (không cần)", False)):
        try:
            cap, thieu = at.collect_pairs(thu_muc, False, need_sidecar=can_sc)
            d(f"  {ten}: {len(cap)} ảnh xử lý được, {len(thieu)} ảnh thiếu .xmp")
        except Exception as ex:                              # noqa: BLE001
            d(f"  {ten}: LỖI {type(ex).__name__}: {ex}")
            cap, thieu = [], []

    cap, thieu = at.collect_pairs(thu_muc, False, need_sidecar=True)
    raw = [p for p in tat_ca if p.suffix.lower() in at.RAW_EXTS
           and not p.name.startswith("._")]
    d("")
    d(f"  RAW có thật trên đĩa            : {len(raw)}")
    d(f"  RAW có .xmp đi kèm              : {len(cap)}")
    d(f"  RAW KHÔNG có .xmp               : {len(thieu)}")
    if thieu:
        #[[ Day gan nhu chac chan la cau tra loi khi "63 anh ra 1 anh": khau
        #   Phan tich o che do .xmp chi nhan anh NAO CO sidecar. Lightroom ghi
        #   .xmp canh anh; chep thieu chung sang la mat sach. ]]
        d("")
        d("  >>> ĐÂY RẤT CÓ THỂ LÀ NGUYÊN NHÂN <<<")
        d("      Khâu Phân tích ở chế độ “.xmp” chỉ nhận ảnh CÓ file .xmp đi kèm.")
        d("      Cách xử lý: hoặc chép nốt mấy file .xmp sang, hoặc trong app")
        d("      đổi nguồn sang “catalog” (không cần .xmp).")
        d("      Vài ảnh thiếu đầu tiên:")
        for p in thieu[:8]:
            d(f"        {p.name}")

    #[[ Doc ca sidecar_for() cua app cho tung anh: co the file .xmp CO o do
    #   nhung ten khong khop (hoa thuong, hoac ".ARW.xmp" so voi ".xmp"). ]]
    xmp = [p for p in tat_ca if p.suffix.lower() == ".xmp"]
    d("")
    d(f"  file .xmp có trong thư mục      : {len(xmp)}")
    if xmp and len(cap) < len(xmp):
        d("  [ ] Có .xmp nhưng app ghép được ít hơn — nhiều khả năng lệch TÊN.")
        for p in raw[:5]:
            d(f"        {p.name}  ->  {at.sidecar_for(p) or 'KHÔNG GHÉP ĐƯỢC'}")

    muc("5. CHẾ ĐỘ CATALOG — CÓ BẢN XUẤT TỪ LIGHTROOM CHƯA")
    #[[ Che do catalog khong can .xmp, nhung KHONG phai cu load anh vao
    #   Lightroom la xong: phai chay mot lan lenh cua plugin de no ghi ra
    #   export_*.tsv. Hai viec do de bi hieu thanh mot. ]]
    try:
        import duong_dan as _dd
        job = _dd.plugin() / "jobs"
        d(f"  thư mục plugin : {_dd.plugin()}")
        d(f"  thư mục jobs   : {job}  ({'có' if job.is_dir() else 'CHƯA CÓ'})")
        d("")
        d("  >>> ĐÂY LÀ THƯ MỤC PHẢI Add TRONG Plug-in Manager CỦA LIGHTROOM:")
        d(f"      {_dd.plugin()}")
        d("      Add từ bản nằm chỗ khác (trong .app, trong AutoTone-mac) thì")
        d("      Lightroom ghi một nơi, app đọc một nơi — không bên nào báo lỗi.")
        khac = at.plugin_khac(_dd.plugin())
        if khac:
            import datetime as _d2
            d("")
            d("  [!] CÓ BẢN PLUGIN KHÁC ĐÃ TỪNG CHẠY:")
            for c_, t_ in khac:
                d(f"      {c_}   (jobs sửa lần cuối "
                  f"{_d2.datetime.fromtimestamp(t_):%d/%m %H:%M:%S})")
            d("      Nếu bản đó MỚI HƠN bản ở trên thì Lightroom đang ghi vào nó")
            d("      — tức Plug-in Manager đang trỏ nhầm. Gỡ nó ra và Add lại")
            d("      đúng thư mục ghi ở trên.")
        #[[ LIET KE HET, khong chi ban duoc chon. Nguoi dung hoi "file nay co
        #   phai file cu khong" — cau tra loi nam o cho co bao nhieu file va
        #   moi file ghi luc nao, chu khong nam o mot cai ten. ]]
        import datetime as _dt
        ds_x = sorted(job.glob("export_*.tsv")) if job.is_dir() else []
        d(f"  số file export : {len(ds_x)}")
        for f_ in ds_x:
            try:
                d(f"      {f_.name}   ghi lúc "
                  f"{_dt.datetime.fromtimestamp(f_.stat().st_mtime):%d/%m %H:%M:%S}"
                  f"   {f_.stat().st_size} byte")
            except OSError:
                d(f"      {f_.name}   (không đọc được)")
        if len(ds_x) > 1:
            d("  [ ] Có NHIỀU hơn một bản xuất — bình thường plugin tự xoá bản cũ.")
            d("      Nhiều file nghĩa là bước dọn của plugin không chạy được.")

        #[[ Nhat ky plugin tra loi dut khoat cau "lenh xuat cua toi co chay
        #   khong" — chay thi co mot dong, khong chay thi khong co dong nao. ]]
        nk = job / "plugin.log"
        d("")
        if nk.is_file():
            try:
                dong_nk = nk.read_text(encoding="utf-8", errors="replace").splitlines()
                d(f"  nhật ký plugin : {len(dong_nk)} dòng, "
                  f"sửa lần cuối {_dt.datetime.fromtimestamp(nk.stat().st_mtime):%d/%m %H:%M:%S}")
                d("  15 dòng cuối:")
                for l_ in dong_nk[-15:]:
                    d("      " + l_)
            except OSError as ex:
                d(f"  nhật ký plugin : không đọc được ({ex})")
        else:
            d("  nhật ký plugin : CHƯA CÓ — plugin chưa từng chạy lần nào")
            d("      Nghĩa là Lightroom chưa nạp plugin ở thư mục này, hoặc")
            d("      nó nạp plugin ở một thư mục KHÁC (bản trong .app, hoặc bản")
            d("      trong thư mục AutoTone-mac). Xem lại Plug-in Manager.")
        d("")

        bx = at.latest_catalog_export()
        if bx is None:
            d("  bản xuất       : CHƯA CÓ file export_*.tsv nào.")
            d("")
            d("      Chế độ catalog cần một lần xuất từ plugin, KHÔNG phải chỉ")
            d("      load ảnh vào catalog. Trong Lightroom:")
            d("        Library → Plug-in Extras → “AutoTone: xuất thông số cho autotone”")
            d("      Plugin phải được Add từ đúng thư mục ghi ở trên.")
        else:
            import datetime as _dt
            xu = at.read_catalog_export(bx)
            khop = sum(1 for p_, _ in cap for _x in (0,)
                       if at.khoa_duong_dan(p_) in xu)
            raw_khop = sum(1 for p_ in raw if at.khoa_duong_dan(p_) in xu)
            d(f"  bản xuất       : {bx.name}")
            d(f"  ghi lúc        : {_dt.datetime.fromtimestamp(bx.stat().st_mtime)}")
            d(f"  số dòng        : {len(xu)}")
            d(f"  khớp với thư mục này: {raw_khop}/{len(raw)} ảnh")
            if raw_khop == 0 and xu:
                d("  [!] Có bản xuất nhưng KHỚP 0 ẢNH — bản xuất của buổi khác,")
                d("      hoặc đường dẫn Lightroom ghi ra khác đường dẫn thật.")
                mau = list(xu.values())[:2]
                for r_ in mau:
                    d(f"        Lightroom ghi: {r_.get(at.LR_PATH_KEY, '?')}")
                if raw:
                    d(f"        trên đĩa     : {raw[0]}")
    except Exception as ex:                                  # noqa: BLE001
        d(f"  không kiểm được: {type(ex).__name__}: {ex}")

    muc("6. ĐO THỬ — GOM LỖI THEO NHÓM")
    #[[ VI SAO DO HET CHU KHONG DO BA TAM.
    #
    #   11/9: tien do chay het 64/64 ma bang ket qua chi ra 1 anh. Tuc 63 anh
    #   DO HONG va bi loai. App co hien mot hop thoai liet ke 12 anh dau, nhung
    #   hop thoai do bam OK la mat, va cau hoi "63 anh kia hong vi cai gi" thi
    #   khong con dau vet nao tra loi.
    #
    #   Do ba tam thi co the roi dung vao ba tam cung mot kieu. Do het roi GOM
    #   THEO NOI DUNG LOI moi thay duoc hinh dang that: tat ca cung mot loi, hay
    #   moi tam mot kieu — hai truong hop do bao hoan toan khac nhau.
    #]]
    loi_nhom = {}
    dat = 0
    if not raw:
        d("  Không có ảnh RAW nào để thử.")
    else:
        cfg = dict(at.DEFAULTS)
        d(f"  đang đo {len(raw)} ảnh (cách đo: {cfg['meter']}, "
          f"cân trắng: {cfg['wb']})…")
        d("")
        for p_ in raw:
            try:
                r = at.measure(p_, cfg["preview_px"], cfg["meter"],
                               cfg["meter_highlight_cut"])
                if r.get("ok"):
                    dat += 1
                    if dat <= 2:
                        d(f"  [đạt ] {p_.name}  ISO {r.get('iso')}  "
                          f"{r.get('w')}x{r.get('h')}")
                else:
                    loi_nhom.setdefault(str(r.get("error")), []).append(p_.name)
            except Exception as ex:                          # noqa: BLE001
                key = f"{type(ex).__name__}: {ex}"
                loi_nhom.setdefault(key, []).append(p_.name)
                if len(loi_nhom[key]) == 1:
                    #[[ Chi in vet stack cho LAN DAU moi loai loi. In 63 lan
                    #   thi bao cao dai vo ich ma van chi noi dung mot chuyen. ]]
                    d("  vết stack lần đầu gặp lỗi này:")
                    d("    " + traceback.format_exc().replace("\n", "\n    "))
        d("")
        d(f"  ĐO ĐƯỢC : {dat}/{len(raw)}")
        d(f"  ĐO HỎNG : {len(raw) - dat}/{len(raw)}")
        if loi_nhom:
            d("")
            d("  Các loại lỗi (nhóm theo nội dung):")
            for k, ds_ in sorted(loi_nhom.items(), key=lambda x: -len(x[1])):
                d(f"    {len(ds_):>4} ảnh · {k}")
                d(f"           ví dụ: {', '.join(ds_[:4])}")

    muc("7. KẾT LUẬN NGẮN")
    if raw and dat < len(raw):
        d(f"  Ghép file thì đủ, nhưng ĐO chỉ được {dat}/{len(raw)} ảnh.")
        d("  Nút thắt nằm ở khâu ĐO, không phải khâu ghép .xmp/catalog.")
        d("  Xem mục 6: loại lỗi nào nhiều nhất thì đó là thứ phải sửa.")
    elif thieu and len(cap) < len(raw):
        d(f"  {len(raw)} ảnh RAW, nhưng chỉ {len(cap)} ảnh có .xmp đi kèm.")
        d("  Khâu Phân tích ở chế độ .xmp vì vậy chỉ xử lý được chừng đó.")
    elif len(cap) == len(raw) and raw:
        d(f"  Ghép đủ {len(cap)}/{len(raw)} ảnh — nút thắt KHÔNG nằm ở khâu ghép")
        d("  .xmp. Xem lại mục 5 và mục 1 (thiếu thư viện?).")
    else:
        d("  Xem lại mục 3 và 4 ở trên.")
    return ghi_ra(0)


def ghi_ra(ma: int) -> int:
    p = GOC / "chan_doan.txt"
    try:
        p.write_text(RA.getvalue(), encoding="utf-8")
        print(f"\n  Đã ghi báo cáo: {p}")
    except OSError as ex:
        print(f"\n  Không ghi được báo cáo: {ex}")
    return ma


if __name__ == "__main__":
    sys.exit(main())
