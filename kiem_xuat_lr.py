"""Kiểm phía đọc đường dẫn Export mà plugin bắt được, và chỗ nối vào khâu 5.

VÌ SAO KIỂM MẤY THỨ NÀY
    Phần Lua đã có kiem_batduongdan.lua canh. Ở đây canh phía Python, và canh
    đúng ba cái bẫy:

      1. So đường dẫn trên Windows. "F:/Out" và "F:\\out\\" là CÙNG một chỗ.
         So chuỗi thẳng thì app dựng ra một cảnh báo "Lightroom Export ra chỗ
         khác" hoàn toàn vô nghĩa, và người dùng sẽ học cách phớt lờ cảnh báo —
         hỏng luôn cả những cảnh báo thật.
      2. File ghi dở / thiếu dòng. Đọc được đường dẫn thì phải dùng, đừng vì
         thiếu mốc thời gian mà vứt cả bản ghi.
      3. Giao diện KHÔNG được tự điền đè lên cái người dùng đã gõ. Kiểm bằng
         cách đọc cây cú pháp: chỉ _dung_batduoc (chạy khi người dùng tự bấm
         nút) mới được gọi v_export_dir.set().

Chạy:  python3 kiem_xuat_lr.py
"""
from __future__ import annotations

import ast
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

GOC = Path(__file__).resolve().parent
sys.path.insert(0, str(GOC))

import xuat_lr    # noqa: E402

LOI: list[str] = []


def ktra(ten: str, dieu: bool, mo: str = "") -> None:
    if dieu:
        print(f"  {ten:<54} {mo or 'đạt'}")
    else:
        LOI.append(f"{ten}: {mo}")


def viet(d: Path, noi_dung: str) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / xuat_lr.TEN_FILE).write_text(noi_dung, encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        job = Path(tmp) / "jobs"
        job.mkdir()

        # ---- chưa có gì
        ktra("chưa Export lần nào -> bảng rỗng", xuat_lr.doc(job) == {})
        ktra("chưa Export lần nào -> không có chữ mô tả", xuat_lr.mo_ta(job) == "")
        ktra("chưa Export lần nào -> không tính là mới", not xuat_lr.con_moi(job))

        # ---- bản ghi đầy đủ
        gio = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        viet(job, f"thu_muc=F:\\Giao\\2705\\JPG\nkieu=specificFolder\n"
                  f"thu_muc_con=JPG\ndinh_dang=JPEG\ntem={gio}\nnguon=filter\n")
        d = xuat_lr.doc(job)
        ktra("đọc đúng thư mục", d.get("thu_muc") == "F:\\Giao\\2705\\JPG",
             d.get("thu_muc", ""))
        ktra("đọc được mốc thời gian thành datetime",
             isinstance(d.get("luc"), datetime))
        ktra("bản vừa ghi được coi là mới", xuat_lr.con_moi(job))
        ktra("có chữ mô tả cho giao diện",
             "F:\\Giao\\2705\\JPG" in xuat_lr.mo_ta(job))

        # ---- bản cũ
        cu = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
        viet(job, f"thu_muc=F:\\Giao\\cu\ntem={cu}\n")
        ktra("bản Export 3 ngày trước KHÔNG còn tính là mới",
             not xuat_lr.con_moi(job), "ngưỡng 24 giờ")
        ktra("nhưng vẫn đọc được đường dẫn của nó",
             xuat_lr.doc(job).get("thu_muc") == "F:\\Giao\\cu")

        # ---- file thiếu dòng / hỏng
        #[[ Thieu moc thoi gian van phai giu duong dan. Vut ca ban ghi chi vi
        #   thieu mot dong la tu lam minh mu. ]]
        viet(job, "thu_muc=F:\\Giao\\khong_co_tem\n")
        ktra("thiếu mốc thời gian -> vẫn giữ đường dẫn",
             xuat_lr.doc(job).get("thu_muc") == "F:\\Giao\\khong_co_tem")
        ktra("thiếu mốc thời gian -> không dám gọi là mới",
             not xuat_lr.con_moi(job))

        viet(job, "linh tinh\nkhong co dau bang\n")
        ktra("file rác -> bảng rỗng, không nổ", xuat_lr.doc(job) == {})

        viet(job, "thu_muc=\ntem=2026-01-01 00:00:00\n")
        ktra("thư mục rỗng -> coi như chưa có", xuat_lr.doc(job) == {})

    # ---- so đường dẫn kiểu Windows
    ktra("F:/Out và F:\\out\\ là cùng một chỗ",
         xuat_lr.cung_mot_cho("F:/Out", "F:\\out\\"))
    ktra("khác hoa thường vẫn là cùng một chỗ",
         xuat_lr.cung_mot_cho("F:\\GIAO", "f:\\giao"))
    ktra("thư mục con thì KHÁC chỗ",
         not xuat_lr.cung_mot_cho("F:\\Giao", "F:\\Giao\\JPG"))
    ktra("rỗng thì không khớp với gì cả",
         not xuat_lr.cung_mot_cho("", "F:\\Giao")
         and not xuat_lr.cung_mot_cho("F:\\Giao", ""))

    # ---- giao diện: không được tự điền đè
    #[[ Doc CAY CU PHAP, khong grep chuoi. Da hai lan bai kiem bao sai chi vi
    #   mot dong chu thich co nhac ten ham bi cam. ]]
    src = (GOC / "autotone_gui.py").read_text(encoding="utf-8")
    cay = ast.parse(src)
    dat_o_dau: list[str] = []
    for ham in ast.walk(cay):
        if not isinstance(ham, ast.FunctionDef):
            continue
        for n in ast.walk(ham):
            if (isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "set"
                    and isinstance(n.func.value, ast.Attribute)
                    and n.func.value.attr == "v_export_dir"):
                dat_o_dau.append(ham.name)
    cho_phep = {"_chon_export", "_dung_batduoc", "_lam_moi_export"}
    ktra("chỉ những hàm được phép mới đổi ô Thư mục Export",
         set(dat_o_dau) <= cho_phep, " · ".join(sorted(set(dat_o_dau))))
    ktra("có hàm _dung_batduoc (chạy khi người dùng tự bấm)",
         "_dung_batduoc" in dat_o_dau)

    ten_ham = {h.name for h in ast.walk(cay) if isinstance(h, ast.FunctionDef)}
    ktra("có hàm dựng lại dòng gợi ý", "_lam_moi_batduoc" in ten_ham)

    #[[ Nut Export trong app phai co, va phai di qua tl.ep(). Goi thang
    #   yeu_cau_xuat() voi thong so THO la gui ca collisionHandling="ask" sang
    #   — Lightroom dung hop thoai giua chung, vong lap nen khong ai bam, va
    #   nhin tu ngoai giong het "app treo". ]]
    goi_ep, goi_yc = set(), set()
    for ham in ast.walk(cay):
        if not isinstance(ham, ast.FunctionDef):
            continue
        for n in ast.walk(ham):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                if n.func.attr == "ep":
                    goi_ep.add(ham.name)
                if n.func.attr == "yeu_cau_xuat":
                    goi_yc.add(ham.name)
    ktra("có nút Export trong app (do_xuat)", "do_xuat" in ten_ham)
    ktra("mọi chỗ gửi yêu cầu đều ép thông số trước",
         goi_yc and goi_yc <= goi_ep,
         f"gửi ở: {sorted(goi_yc)} · ép ở: {sorted(goi_ep)}")
    for ten in ("do_dung_xuat", "_soi_xuat_anh", "_lam_moi_xuat_ts"):
        ktra(f"có {ten}", ten in ten_ham)

    phan_thong_so()
    phan_yeu_cau()

    print()
    if LOI:
        for m in LOI:
            print("  [!] " + m)
        print(f"{len(LOI)} LỖI")
        return 1
    print("TẤT CẢ ĐẠT")
    return 0


# ===================================================================
#  Đọc thông số Export của Lightroom, và gửi yêu cầu xuất
# ===================================================================

MAU_PREFS = """s = {
	AgDevelop_target = "activePhoto",
	AgExport_collisionHandling = "ask",
	AgExport_exportServiceProvider = "com.adobe.ag.export.file",
	AgExport_format = "JPEG",
	AgExport_jpeg_quality = 0.7,
	AgExport_size_doConstrain = false,
	AgExport_size_maxWidth = 1000,
	AgExport_outputSharpeningOn = false,
	AgExport_useWatermark = false,
	AgExport_tokenCustomString = "SAY-Media",
	AgExport_tokens = "{{custom_token}}-{{image_filename_number_suffix}}",
	AgExport_markedPresets = "t = {\\
}\\
",
	AgExport_DNG_compressed = true,
	AgPublish_format = "JPEG",
	AgImport_advancedMode = true,
}
"""


def phan_thong_so() -> None:
    import thongso_lr as tl

    with tempfile.TemporaryDirectory() as tmp:
        goc = Path(tmp)
        (goc / "Preferences").mkdir()
        pf = goc / "Preferences" / "Lightroom Classic CC 7 Preferences.agprefs"
        pf.write_text(MAU_PREFS, encoding="utf-8")
        #[[ File "Startup Preferences" phai bi bo qua: no moi hon nhung khong
        #   chua thong so export nao. Chon nham la doc ra bang rong. ]]
        (goc / "Preferences" / "Lightroom Classic CC 7 Startup Preferences.agprefs"
         ).write_text("s = {}\n", encoding="utf-8")

        chon = tl.file_prefs(goc)
        ktra("bỏ qua file Startup Preferences",
             chon is not None and "Startup" not in chon.name,
             chon.name if chon else "không thấy")

        st, luc = tl.doc_prefs(goc=goc)
        ktra("đọc được thông số Export", bool(st), f"{len(st)} khoá")
        ktra("đổi đúng tiền tố AgExport_ -> LR_",
             st.get("LR_format") == "JPEG")
        ktra("số đọc thành số", st.get("LR_jpeg_quality") == 0.7,
             repr(st.get("LR_jpeg_quality")))
        ktra("false đọc thành False, không phải chuỗi",
             st.get("LR_useWatermark") is False,
             type(st.get("LR_useWatermark")).__name__)
        ktra("giá trị có {{ }} không bị cắt",
             st.get("LR_tokens") == "{{custom_token}}-{{image_filename_number_suffix}}",
             str(st.get("LR_tokens")))
        #[[ AgExport_markedPresets chua ca mot bang Lua viet trong chuoi nhieu
        #   dong. Nuot no vao la keo theo rac va co the lam hong ca luot xuat. ]]
        ktra("KHÔNG nuốt khoá chuỗi nhiều dòng (markedPresets)",
             "LR_markedPresets" not in st)
        #[[ Danh sach trang: chi cho qua khoa da biet mat. Mot khoa la co the
        #   lam Lightroom xuat ra anh 1 diem anh ma khong bao gi. ]]
        ktra("không lấy khoá của Publish / Import",
             not any(k.startswith(("LR_Ag", "LR_advancedMode")) for k in st))
        ktra("có mốc thời gian của file", luc is not None)

        ktra("không có preset người dùng nào thì trả về rỗng",
             tl.preset_nguoi_dung(goc) == [])

        # ---- .lrtemplate
        d = goc / "Export Presets" / "User Presets"
        d.mkdir(parents=True)
        (d / "Giao khach.lrtemplate").write_text(
            's = {\n\tid = "abc",\n\ttitle = "Giao khach",\n\tvalue = {\n'
            '\t\tformat = "JPEG",\n\t\tjpeg_quality = 1,\n'
            '\t\tuseWatermark = false,\n\t\tsize_doConstrain = true,\n'
            '\t\tsize_maxWidth = 2048,\n\t},\n\tversion = 0,\n}\n',
            encoding="utf-8")
        ds = tl.preset_nguoi_dung(goc)
        ktra("thấy preset người dùng tự lưu",
             [t[0] for t in ds] == ["Giao khach"], str([t[0] for t in ds]))
        tp = tl.doc_lrtemplate(ds[0][1])
        ktra("preset: khoá không tiền tố -> thêm LR_",
             tp.get("LR_format") == "JPEG" and tp.get("LR_size_maxWidth") == 2048)
        ktra("preset: false vẫn là False", tp.get("LR_useWatermark") is False)
        #[[ Chi doc phan value = {...}. Doc ca file thi 'id' va 'title' cua
        #   preset se lot vao bang thong so. ]]
        ktra("preset: không lấy id / title ngoài khối value",
             "LR_id" not in tp and "LR_title" not in tp)

    # ---- ép thông số
    st = {"LR_format": "JPEG", "LR_collisionHandling": "ask",
          "LR_export_destinationPathPrefix": "F:\\CHO_CU",
          "LR_export_postProcessing": "showInExplorer",
          "LR_reimportExportedPhoto": True, "LR_jpeg_quality": 0.7}
    e = thongso_ep(st)
    ktra("ép thư mục đích do app chọn",
         e["LR_export_destinationPathPrefix"] == "F:\\Giao")
    #[[ "ask" dung mot hop thoai giua chung. Vong lap nen khong co ai bam ->
    #   Lightroom treo, nhin tu ngoai giong het "app hong". ]]
    ktra("KHÔNG để lại collisionHandling = ask",
         e["LR_collisionHandling"] != "ask", e["LR_collisionHandling"])
    ktra("không mở Explorer sau mỗi lô",
         e["LR_export_postProcessing"] == "doNothing")
    ktra("không nhập ngược ảnh vừa xuất vào catalog",
         e["LR_reimportExportedPhoto"] is False)
    ktra("giữ nguyên những thứ của người dùng",
         e["LR_jpeg_quality"] == 0.7 and e["LR_format"] == "JPEG")
    ktra("KHÔNG sửa bảng gốc (trả bảng mới)",
         st["LR_collisionHandling"] == "ask", "bảng gốc còn nguyên")

    mo = thongso_mota({"LR_format": "JPEG", "LR_jpeg_quality": 0.7,
                       "LR_size_doConstrain": False,
                       "LR_export_colorSpace": "sRGB"})
    ktra("có một dòng tóm tắt đọc được",
         "JPEG" in mo and "70" in mo and "nguyên cỡ" in mo, mo)
    ktra("chưa có thông số thì mô tả rỗng", thongso_mota({}) == "")


def thongso_ep(st):
    import thongso_lr as tl
    return tl.ep(st, "F:\\Giao")


def thongso_mota(st):
    import thongso_lr as tl
    return tl.mo_ta(st)


def phan_yeu_cau() -> None:
    """Gửi yêu cầu xuất: đúng định dạng plugin đọc được, và không tự bịa."""
    with tempfile.TemporaryDirectory() as tmp:
        job = Path(tmp) / "jobs"
        st = {"LR_format": "JPEG", "LR_jpeg_quality": 0.7,
              "LR_useWatermark": False, "LR_size_maxWidth": 2048,
              "LR_tokens": "{{custom_token}}-x"}
        p = xuat_lr.yeu_cau_xuat("F:\\Buoi", "F:\\Giao", st, bo_sao=1,
                                 job_dir=job)
        dong = p.read_text(encoding="utf-8").splitlines()
        ktra("dòng đầu là thư mục nguồn", dong[0] == "F:\\Buoi", dong[0])
        ktra("có dòng dest", "dest=F:\\Giao" in dong)
        ktra("có dòng bo_sao", "bo_sao=1" in dong)
        ktra("chuỗi mang nhãn s", "ts\ts\tLR_format\tJPEG" in dong)
        ktra("số mang nhãn n", "ts\tn\tLR_jpeg_quality\t0.7" in dong)
        #[[ Day la dong quan trong nhat: b|false. Gui sang thanh chuoi "false"
        #   la Lightroom hieu thanh DUNG (trong Lua moi chuoi deu dung) -> bat
        #   watermark len ca nghin anh giao khach. ]]
        ktra("boolean mang nhãn b và viết thường",
             "ts\tb\tLR_useWatermark\tfalse" in dong)
        ktra("không để lại file .part", not (job / "request_xuatanh.part").exists())
        ktra("app biết là đang có yêu cầu chờ", xuat_lr.dang_cho_xuat(job))

        try:
            xuat_lr.yeu_cau_xuat("F:\\Buoi", "F:\\Giao", {}, job_dir=job)
            ok = False
        except ValueError:
            ok = True
        ktra("KHÔNG cho gửi yêu cầu khi chưa có thông số", ok,
             "thà không xuất còn hơn xuất bằng thông số bịa")

        (job / xuat_lr.TEN_TIEN_DO_XUAT).write_text(
            "trang_thai=dang_chay\nxong=120\ntong=2000\nloi=0\n",
            encoding="utf-8")
        td = xuat_lr.tien_do_xuat(job)
        ktra("đọc được tiến độ, số ra số",
             td.get("xong") == 120 and td.get("tong") == 2000,
             f'{td.get("xong")}/{td.get("tong")}')
        xuat_lr.dung_xuat(job)
        ktra("đặt được cờ xin dừng",
             (job / xuat_lr.TEN_CO_DUNG_XUAT).exists())


if __name__ == "__main__":
    sys.exit(main())
