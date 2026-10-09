#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Plugin tự cài vào thư mục Modules của Lightroom (9/10).

CHUYỆN ĐANG LÀM
    User: "Có cách nào để Lightroom tự động nhận Plugin của Tool khi lần đầu cài
    Tool xong không?" — Lightroom Classic tự nạp mọi plugin trong thư mục
    Modules lúc khởi động. App chép plugin vào đó + ghi jobs_dir.txt trỏ về thư
    mục job thật (ThuMucJob.lua đọc). Xem duong_dan.cai_vao_modules.

Mục kiểm
    1. Lần đầu: chép đủ file mã (kể cả ThuMucJob.lua), KHÔNG chép jobs/, ghi file
       trỏ đúng thư mục job; moi=True.
    2. Lần sau không đổi gì -> không ghi gì; một file mã đổi -> chỉ file đó; đổi
       thư mục job -> ghi lại file trỏ.
    3. Không cài khi: mã nguồn / tự kiểm / thư mục dữ liệu tạm / tiến trình con;
       AUTOTONE_LR_MODULES ép cài được.
    4. Đọc danh sách plugin đã Add trong cấu hình Lightroom (chuỗi Lua lồng, 4 dấu
       \\ mỗi dấu), bỏ bản đã Disable và plugin khác tên.
    5. Lua 5.1 thật (lupa, nếu có): ThuMucJob.jobDir() theo file trỏ; không có
       file trỏ thì <plugin>/jobs; Core.jobDir / ghiNhip ghi vào thư mục trỏ tới.
    6. Gói: plugin_sach bỏ jobs_dir.txt; Inno gỡ cài đặt xoá bản trong Modules.

Chạy:  python test_plugin_modules.py
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

GOC = Path(__file__).resolve().parent
sys.path.insert(0, str(GOC))
import duong_dan as dd                                        # noqa: E402

LOI: list[str] = []


def ktra(ten: str, dieu: bool, mo: str = "") -> None:
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(f"{ten}: {mo}")


MAU_PREFS = (
    's = {\n'
    '\tAgPluginManager_selectedPluginPath = "C:\\\\Users\\\\ipmac\\\\AppData\\\\Local\\\\AutoTone\\\\AutoTone.lrplugin",\n'
    '\tAgSdkPluginLoader_disabledPluginIDs = "t = {\\\n}\\\n",\n'
    '\tAgSdkPluginLoader_disabledPluginPaths = "t = {\\\n'
    '\t[\\"F:\\\\\\\\Claude AI\\\\\\\\AutoToneImages\\\\\\\\AutoTone.lrplugin\\"] = true,\\\n'
    '}\\\n",\n'
    '\tAgSdkPluginLoader_installedPluginPaths = "t = {\\\n'
    '\t[\\"C:\\\\\\\\Users\\\\\\\\ipmac\\\\\\\\AppData\\\\\\\\Local\\\\\\\\AutoTone\\\\\\\\AutoTone.lrplugin\\"] = '
    '\\"C:\\\\\\\\Users\\\\\\\\ipmac\\\\\\\\AppData\\\\\\\\Local\\\\\\\\AutoTone\\\\\\\\AutoTone.lrplugin\\",\\\n'
    '\t[\\"F:\\\\\\\\Claude AI\\\\\\\\AutoToneImages\\\\\\\\AutoTone.lrplugin\\"] = '
    '\\"F:\\\\\\\\Claude AI\\\\\\\\AutoToneImages\\\\\\\\AutoTone.lrplugin\\",\\\n'
    '\t[\\"D:\\\\\\\\Plugins\\\\\\\\LRTimelapse.lrplugin\\"] = \\"D:\\\\\\\\Plugins\\\\\\\\LRTimelapse.lrplugin\\",\\\n'
    '}\\\n",\n'
    '\tAgSlideshow_whichView = "images",\n'
    '}\n')


def phan_cai(tam: Path):
    nguon = tam / "goi" / "AutoTone.lrplugin"
    shutil.copytree(GOC / "AutoTone.lrplugin", nguon,
                    ignore=shutil.ignore_patterns("jobs", "jobs_dir.txt"))
    (nguon / "jobs").mkdir()
    (nguon / "jobs" / "rac.tsv").write_text("x", encoding="utf-8")
    jobs = tam / "du_lieu" / "AutoTone.lrplugin" / "jobs"
    mod = tam / "Roaming" / "Adobe" / "Lightroom" / "Modules"
    kq = dd.cai_vao_modules(nguon, jobs, mod)
    dich = mod / "AutoTone.lrplugin"
    n_lua = len(list(nguon.glob("*.lua")))
    ktra("lần đầu: moi=True, không lỗi, đủ file .lua (có ThuMucJob.lua)",
         kq["moi"] and not kq["loi"] and len(list(dich.glob("*.lua"))) == n_lua
         and (dich / "ThuMucJob.lua").is_file() and (dich / "Info.lua").is_file(),
         f"{len(list(dich.glob('*.lua')))}/{n_lua} file · {kq}")
    ktra("không chép jobs/ của gói", not (dich / "jobs").exists())
    tro = (dich / dd.TEN_TRO_JOBS).read_text(encoding="utf-8")
    ktra("file trỏ = thư mục job thật, một dòng", tro == str(jobs) + "\n", repr(tro))
    kq2 = dd.cai_vao_modules(nguon, jobs, mod)
    ktra("lần sau không đổi gì -> không ghi gì", not kq2["moi"] and kq2["doi"] == [], str(kq2["doi"]))
    f = nguon / "XuatCore.lua"
    f.write_text(f.read_text(encoding="utf-8") + "\n-- doi\n", encoding="utf-8")
    kq3 = dd.cai_vao_modules(nguon, jobs, mod)
    ktra("một file mã đổi -> chỉ cập nhật file đó", kq3["doi"] == ["XuatCore.lua"], str(kq3["doi"]))
    jobs2 = tam / "du_lieu2" / "jobs"
    kq4 = dd.cai_vao_modules(nguon, jobs2, mod)
    ktra("đổi thư mục job -> ghi lại file trỏ",
         kq4["doi"] == [dd.TEN_TRO_JOBS]
         and (dich / dd.TEN_TRO_JOBS).read_text(encoding="utf-8") == str(jobs2) + "\n")
    dd.cai_vao_modules(nguon, jobs, mod)          # trả file trỏ về thư mục job ban đầu
    khoa = tam / "chi_doc"
    khoa.write_text("không phải thư mục", encoding="utf-8")
    kq5 = dd.cai_vao_modules(nguon, jobs, khoa)
    ktra("Modules không ghi được -> báo lỗi, không ném", bool(kq5["loi"]), kq5["loi"][:60])
    return dich, jobs


def phan_dieu_kien(tam: Path):
    cu = {k: os.environ.get(k) for k in ("AUTOTONE_LR_MODULES", "AUTOTONE_TU_KIEM", "AUTOTONE_DATA")}
    dg = dd.dong_goi
    try:
        for k in cu:
            os.environ.pop(k, None)
        ktra("chạy từ mã nguồn -> không cài", dd.ly_do_khong_cai_modules() == "chạy từ mã nguồn")
        dd.dong_goi = lambda: True
        os.environ["AUTOTONE_DATA"] = str(tam / "x")
        ktra("gói + thư mục dữ liệu trong thư mục tạm -> không cài",
             "tạm" in dd.ly_do_khong_cai_modules(), dd.ly_do_khong_cai_modules())
        os.environ["AUTOTONE_TU_KIEM"] = str(tam / "bao.txt")
        ktra("gói + đang tự kiểm -> không cài", dd.ly_do_khong_cai_modules() == "đang tự kiểm")
        os.environ.pop("AUTOTONE_TU_KIEM")
        os.environ["AUTOTONE_DATA"] = os.path.join(os.environ.get("LOCALAPPDATA", "C:\\x"), "AutoTone")
        ktra("gói thật, thư mục dữ liệu thường, tiến trình chính -> cài",
             dd.ly_do_khong_cai_modules() == "", dd.ly_do_khong_cai_modules())
        os.environ["AUTOTONE_LR_MODULES"] = str(tam / "M")
        os.environ["AUTOTONE_TU_KIEM"] = "1"
        ktra("AUTOTONE_LR_MODULES ép cài + chỉ thư mục", dd.ly_do_khong_cai_modules() == ""
             and dd.thu_muc_modules_lr() == tam / "M")
        os.environ.pop("AUTOTONE_LR_MODULES")
        if sys.platform.startswith("win"):
            ktra("Windows: %APPDATA%\\Adobe\\Lightroom\\Modules",
                 dd.thu_muc_modules_lr() == Path(os.environ["APPDATA"]) / "Adobe" / "Lightroom" / "Modules")
    finally:
        dd.dong_goi = dg
        for k, v in cu.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def phan_prefs(tam: Path):
    import thongso_lr as tl
    p = tam / "Lightroom Classic CC 7 Preferences.agprefs"
    p.write_text(MAU_PREFS, encoding="utf-8")
    ds = tl.plugin_da_them_lr(p)
    ktra("đọc bản AutoTone đã Add, bỏ bản Disable và plugin khác",
         ds == ["C:\\Users\\ipmac\\AppData\\Local\\AutoTone\\AutoTone.lrplugin"], str(ds))
    ktra("file hỏng / không có -> []", tl.plugin_da_them_lr(tam / "khong_co.agprefs") == [])


def phan_lua(tam: Path, dich: Path, jobs: Path):
    if os.environ.get("LUPA_DIR"):
        sys.path.insert(0, os.environ["LUPA_DIR"])
    try:
        from lupa import lua51
    except ImportError:
        print("  (bỏ qua phần Lua: thiếu lupa — đặt LUPA_DIR)")
        return

    def chay(goc_plugin: Path):
        L = lua51.LuaRuntime(unpack_returned_tuples=True)
        g = L.globals()
        g.py_exists = lambda p_: os.path.exists(p_)
        g.py_mkdirs = lambda p_: os.makedirs(p_, exist_ok=True) or True
        L.execute(r'''
_PLUGIN = { path = [[%s]] }
local fake = {
  LrFileUtils = { exists = function(p) return py_exists(p) end,
                  createAllDirectories = function(p) return py_mkdirs(p) end,
                  delete = function() return true end, move = function() return true end },
  LrPathUtils = { child = function(a, b) return a .. "/" .. b end,
                  leafName = function(p) return string.match(p, "[^/\\]+$") end },
  LrFunctionContext = { pcallWithContext = function(tag, fn) return pcall(fn) end },
  LrTasks = { yield = function() end, sleep = function() end },
  LrDate = { currentTime = function() return os.time() end },
  LrApplication = {},
}
function import(name) return fake[name] or {} end
package.path = [[%s/?.lua;]] .. package.path
''' % (str(goc_plugin).replace("\\", "/"), str(goc_plugin).replace("\\", "/")))
        return L

    L = chay(dich)
    jd = L.eval('require("ThuMucJob").jobDir()')
    ktra("Lua: ThuMucJob.jobDir() = thư mục trong file trỏ", Path(jd) == jobs, jd)
    Core = L.eval('require("AutoToneCore")')
    ktra("Lua: AutoToneCore.jobDir() đi qua file trỏ", Path(Core.jobDir()) == jobs, str(Core.jobDir()))
    Core.ghiNhip(7, 0, "thử")
    ktra("Lua: ghiNhip ghi plugin_song.txt vào thư mục job thật (không vào Modules)",
         (jobs / "plugin_song.txt").is_file() and not (dich / "jobs" / "plugin_song.txt").exists())
    tro_bom = tam / "bom"
    shutil.copytree(dich, tro_bom)
    (tro_bom / dd.TEN_TRO_JOBS).write_bytes(("\ufeff" + str(jobs) + "  \r\n").encode("utf-8"))
    ktra("Lua: file trỏ có BOM / khoảng trắng / CRLF vẫn đọc đúng",
         Path(chay(tro_bom).eval('require("ThuMucJob").jobDir()')) == jobs)
    khong = tam / "khong_tro"
    shutil.copytree(dich, khong)
    (khong / dd.TEN_TRO_JOBS).unlink()
    jd2 = chay(khong).eval('require("ThuMucJob").jobDir()')
    ktra("Lua: không có file trỏ -> <plugin>/jobs (bản Add tay như cũ)",
         Path(jd2) == khong / "jobs", jd2)


def phan_goi():
    import dong_goi as dg
    ktra("plugin_sach bỏ jobs_dir.txt", "jobs_dir.txt" in dg.BO_KHOI_PLUGIN)
    iss = (GOC / "installer_win.iss").read_text(encoding="utf-8")
    ktra("gỡ cài đặt xoá bản trong Modules",
         "[UninstallDelete]" in iss and "{userappdata}\\Adobe\\Lightroom\\Modules\\AutoTone.lrplugin" in iss)
    for f in ("AutoToneCore.lua", "BatDuongDan.lua", "Init.lua"):
        ktra(f"{f} lấy thư mục job qua ThuMucJob",
             'pcall(require, "ThuMucJob")' in (GOC / "AutoTone.lrplugin" / f).read_text(encoding="utf-8"))


def main() -> int:
    tam = Path(tempfile.mkdtemp(prefix="plugin_mod_"))
    try:
        dich, jobs = phan_cai(tam)
        phan_dieu_kien(tam)
        phan_prefs(tam)
        phan_lua(tam, dich, jobs)
        phan_goi()
    finally:
        shutil.rmtree(tam, ignore_errors=True)
    print("TAT CA DAT" if not LOI else f"{len(LOI)} LOI")
    return 1 if LOI else 0


if __name__ == "__main__":
    sys.exit(main())
