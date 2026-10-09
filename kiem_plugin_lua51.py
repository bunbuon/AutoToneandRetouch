# -*- coding: utf-8 -*-
"""Kiem plugin Lightroom bang Lua 5.1 that (lupa.lua51) + SDK gia.
  1. Moi file .lua cua plugin bien dich duoc (cu phap Lua 5.1).
  2. Info.lua: LrForceInitPlugin = true, LrInitPlugin = Init.lua.
  3. recoverStale: job bo do co job moi hon cung buoi (.tsv / .done) -> .huy, log "bo job cu";
     khong co job moi hon -> tra ve .tsv; buoi khac / ten co dau cham khong lan.
  4. applyJob ghi nhip kem buoc (buoc=...), van giu vong=<so vong> cua vong lap.
Chay:  python kiem_plugin_lua51.py [thu-muc-plugin]
Can goi lupa (co san Lua 5.1 — dung ban Lightroom dung). Khong cai vao venv build:
    pip install --target <thu-muc-tam> lupa   roi dat bien LUPA_DIR=<thu-muc-tam>
Khong co lupa thi BO QUA (in ro), khong bao dat.

8/10: Lightroom khong nhan job ca gio — Info.lua thieu LrForceInitPlugin (plugin
chi khoi dong khi bam menu), job bo do 21:25 bi ap lai thong so cu, va hop thoai
modal "Da xuat..." lam vong nhan job dung im 90 giay."""
import os
import shutil
import sys
import tempfile
from pathlib import Path

if os.environ.get("LUPA_DIR"):
    sys.path.insert(0, os.environ["LUPA_DIR"])
try:
    from lupa import lua51  # noqa: E402
except ImportError:
    print("BO QUA: thieu goi lupa (xem dau file) — CHUA kiem plugin Lua")
    sys.exit(0)

GOC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "AutoTone.lrplugin"
LOI = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


# ---- 1. cu phap
for f in sorted(GOC.glob("*.lua")):
    L = lua51.LuaRuntime(unpack_returned_tuples=True)
    r = L.globals().loadstring(f.read_bytes().decode("utf-8"), "@" + f.name)
    ok, err = r if isinstance(r, tuple) else (r, None)
    ktra(f"cu phap {f.name}", ok is not None, "" if ok is not None else str(err))

# ---- 2. Info.lua
L = lua51.LuaRuntime(unpack_returned_tuples=True)
info = L.execute(f.with_name("Info.lua").read_text(encoding="utf-8"))
ktra("Info.lua: LrForceInitPlugin = true", info["LrForceInitPlugin"] is True)
ktra("Info.lua: LrInitPlugin = Init.lua", info["LrInitPlugin"] == "Init.lua")

# ---- SDK gia
tam = Path(tempfile.mkdtemp(prefix="kiem_lua51_"))
jobs = tam / "jobs"
jobs.mkdir()
L = lua51.LuaRuntime(unpack_returned_tuples=True)
g = L.globals()


def files(d):
    ds = [str(Path(d) / x) for x in sorted(os.listdir(d))]
    it = iter(ds)
    return lambda *_: next(it, None)


def move(a, b):
    os.replace(a, b)
    return True


g.py_files = files
g.py_move = move
g.py_exists = lambda p: os.path.exists(p)
g.py_delete = lambda p: (os.remove(p) if os.path.isfile(p) else None) or True
g.py_mkdirs = lambda p: os.makedirs(p, exist_ok=True) or True
L.execute(r'''
_PLUGIN = { path = [[%s]] }
local fake = {
  LrFileUtils = { files = function(d) return py_files(d) end, move = function(a, b) return py_move(a, b) end,
                  exists = function(p) return py_exists(p) end, delete = function(p) return py_delete(p) end,
                  createAllDirectories = function(p) return py_mkdirs(p) end },
  LrPathUtils = { child = function(a, b) return a .. "/" .. b end,
                  leafName = function(p) return string.match(p, "[^/\\]+$") end },
  LrFunctionContext = { pcallWithContext = function(tag, fn) return pcall(fn) end },
  LrTasks = { yield = function() end, sleep = function() end },
  LrDate = { currentTime = function() return os.time() end },
  LrApplication = {},
}
function import(name) return fake[name] or {} end
package.path = [[%s/?.lua;]] .. package.path
''' % (str(tam).replace("\\", "/"), str(GOC).replace("\\", "/")))
Core = L.eval('require("AutoToneCore")')

# ---- 3. recoverStale
ten = {
    "cu_moi_cho": "apply_20261008_212538_BVDay3.tsv.table0017BC06580-1791469539-6.running",
    "moi_cho": "apply_20261008_221835_BVDay3.tsv",
    "le": "apply_20261008_100000_raw_19.4.tsv.tableY-1-1.running",       # chi co job CU hon da xong
    "le_cu_xong": "apply_20261008_090000_raw_19.4.done",
    "cu_moi_xong": "apply_20261008_110000_KyYeu.tsv.tableZ-1-2.running",
    "moi_xong": "apply_20261008_120000_KyYeu.done",
    "khac_buoi": "apply_20261008_120000_BVDay3x.done",                  # buoi KHAC ten gan giong, CU hon
    "bvx": "apply_20261008_125900_BVDay3x.tsv.tableQ-1-3.running",
}
for k, v in ten.items():
    (jobs / v).write_text("path\n", encoding="utf-8")
n = Core.recoverStale()
co = set(os.listdir(jobs))
ktra("job bo do, buoi da co job MOI HON dang cho -> .huy",
     "apply_20261008_212538_BVDay3.huy" in co and ten["cu_moi_cho"] not in co)
ktra("job moi hon dang cho van nguyen", ten["moi_cho"] in co)
ktra("job bo do, buoi da co job moi hon DA AP -> .huy (khong de thong so cu)",
     "apply_20261008_110000_KyYeu.huy" in co)
ktra("job bo do, chi co job CU hon -> tra ve .tsv (ten buoi co dau cham)",
     "apply_20261008_100000_raw_19.4.tsv" in co)
ktra("buoi ten gan giong (BVDay3x) khong lan voi BVDay3 -> tra ve .tsv",
     "apply_20261008_125900_BVDay3x.tsv" in co)
ktra("recoverStale dem dung so job tra lai", n == 2, str(n))
log = (jobs / "plugin.log").read_text(encoding="utf-8")
ktra("nhat ky ghi 'bo job cu'", "bo job cu apply_20261008_212538_BVDay3.tsv" in log, log[-200:])

# ---- 4. nhip kem buoc
Core.ghiNhip(66, 0)
song = (jobs / "plugin_song.txt").read_text(encoding="utf-8")
ktra("nhip vong lap: vong=66, khong co buoc", "vong=66" in song and "buoc=" not in song, song)
L.execute('''
local photo = { s = { Exposure2012 = 0 } }
function photo:getDevelopSettings() local t = {} for k, v in pairs(self.s) do t[k] = v end return t end
function photo:applyDevelopSettings(s) for k, v in pairs(s) do self.s[k] = v end end
function photo:getRawMetadata() return 0 end
function photo:setRawMetadata() end
local cat = { findPhotoByPath = function(self, p) return photo end,
              withWriteAccessDo = function(self, n, fn) fn() end }
local LrApplication = import("LrApplication")
LrApplication.activeCatalog = function() return cat end
''')
nhip = []
goc = Core.ghiNhip


def soi(vong, cach, buoc=None):
    r = goc(vong, 0, buoc)
    if buoc:
        nhip.append((jobs / "plugin_song.txt").read_text(encoding="utf-8"))
    return r


Core.ghiNhip = soi
rows = L.eval('{ { path = "G:/x/a.ARW", settings = { Exposure2012 = 0.5 } } }')
res = Core.applyJob(rows, "apply_20261008_222243_BVDay3.tsv")
Core.ghiNhip = goc
ktra("applyJob van ap dung (ap 1)", res["applied"] == 1, str(res["applied"]))
ktra("applyJob ghi nhip moi buoc", len(nhip) >= 4 and all("vong=66" in x for x in nhip),
     " | ".join(x.split("buoc=")[-1].strip() for x in nhip))
ktra("buoc dau = 'bắt đầu 1 ảnh', co 'ghi 1/1'",
     "buoc=bắt đầu 1 ảnh" in nhip[0] and any("buoc=ghi 1/1" in x for x in nhip))

# ---- 4b. DuyetCore.locSao (9/10): -1 = chi giu anh CHUA gan sao (anh co sao = da loc)
L.execute('''
local cat = { withReadAccessDo = function(self, fn) fn() end,
              withWriteAccessDo = function(self, n, fn) fn() end,
              findPhotoByPath = function() return nil end }
local LrApplication = import("LrApplication")
LrApplication.activeCatalog = function() return cat end
''')
Dc = L.eval('require("DuyetCore")')
anh_sao = L.eval('''(function()
  local ds = {}
  local sao = { false, 0, 1, 3, 5, 1 }
  for i = 1, #sao do
    local s = sao[i]
    ds[i] = { ten = "A" .. i, getRawMetadata = function(self, k) if k == "rating" and s then return s end return nil end }
  end
  return ds end)()''')


def loc(bo):
    out, n_bo = Dc.locSao(anh_sao, bo)
    return [out[i]["ten"] for i in range(1, len(out) + 1)], n_bo


g1, b1 = loc(-1)
ktra("locSao(-1): chi giu anh chua gan sao (nil / 0), bo moi anh 1-5 sao", g1 == ["A1", "A2"] and b1 == 4, f"{g1} bo {b1}")
g2, b2 = loc(1)
ktra("locSao(1): bo dung anh 1 sao nhu cu", g2 == ["A1", "A2", "A4", "A5"] and b2 == 2, f"{g2} bo {b2}")
g3, b3 = loc(0)
ktra("locSao(0): xuat het", len(g3) == 6 and b3 == 0)
ktra("locSao('-1' dang chu tu file yeu cau) = -1", loc("-1") == (g1, b1))

# ---- 5. XuatCore (9/10 Xuat mot thao tac): bang path->jpg + ten file khop xuat_lr
X = L.eval('require("XuatCore")')
import xuat_lr
ktra("XuatCore.BANG khop xuat_lr.TEN_BANG_XUAT", X["BANG"] == xuat_lr.TEN_BANG_XUAT, str(X["BANG"]))
cap = L.eval('{ { src = "G:/Buoi/DSC01.ARW", jpg = "F:/Giao/SAY-01.jpg" }, '
             '  { src = "G:/Buoi/DSC02.ARW", jpg = "F:/Giao/SAY-02.jpg" } }')
X.ghiBang(cap)
b = xuat_lr.bang_anh(jobs)
ktra("ghiBang -> xuat_lr.bang_anh doc duoc (ten ra khac ten goc)",
     b == {"G:/Buoi/DSC01.ARW": "F:/Giao/SAY-01.jpg", "G:/Buoi/DSC02.ARW": "F:/Giao/SAY-02.jpg"}, str(b))
X.xoaBang()
ktra("xoaBang xoa file bang", not (jobs / xuat_lr.TEN_BANG_XUAT).exists())
f_, o_, ts_ = X.docDong(L.table("F:/Buoi", "dest=F:/Giao", "lo=10", "ts	n	LR_jpeg_quality	0.92"))
ktra("docDong: chat luong so, lo doc duoc", ts_["LR_jpeg_quality"] == 0.92 and o_["lo"] == "10")
src_x = (GOC / "XuatCore.lua").read_text(encoding="utf-8")
ktra("M.xuat ghi nhip kem buoc 'xuất ảnh a/b' sau moi lo", "Core.ghiNhip(nil, 0" in src_x and "xuất ảnh %d/%d" in src_x)

# ---- 6. XuatCore.xuat (9/10): MOT phien cho ca luot, theo doi tung anh, dung giua chung
tam2 = Path(tempfile.mkdtemp(prefix="kiem_xuat1phien_"))
(tam2 / "jobs").mkdir()
L2 = lua51.LuaRuntime(unpack_returned_tuples=True)
g2 = L2.globals()
g2.py_exists = lambda p: os.path.exists(p)
g2.py_mkdirs = lambda p: os.makedirs(p, exist_ok=True) or True
g2.py_delete = lambda p: (os.remove(p) if os.path.isfile(p) else None) or True
g2.py_move = move


def _py_write(p, s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(s)
    return True


g2.py_write = _py_write


def _dem_hang_doi():
    try:
        return len((tam2 / "jobs" / "xuatanh_hangdoi.tsv").read_text(encoding="utf-8").splitlines())
    except OSError:
        return -1


g2.py_dem_hang_doi = _dem_hang_doi
L2.execute(r'''
_PLUGIN = { path = [[%s]] }
KICH = { phien = 0, soAnh = {}, boQua = {}, datCoSau = nil, skip = 0, render = 0, hd = {} }
local LrExportSession = function(params)
  KICH.phien = KICH.phien + 1
  KICH.soAnh[#KICH.soAnh + 1] = #params.photosToExport
  local dest = params.exportSettings.LR_export_destinationPathPrefix
  local ds = {}
  for i, ph in ipairs(params.photosToExport) do
    ds[i] = { photo = ph,
      waitForRender = function(self)
        KICH.render = KICH.render + 1
        KICH.hd[KICH.render] = py_dem_hang_doi()
        if KICH.datCoSau and KICH.render == KICH.datCoSau then
          py_write(_PLUGIN.path .. "/jobs/request_xuatanh_dung.txt", "dung")
        end
        if KICH.boQua[ph.__ten] then return false, "loi gia" end
        local p = dest .. "/SAY-" .. ph.__ten .. ".jpg"
        py_write(p, "JPEG")
        return true, p
      end,
      skipRender = function(self) KICH.skip = KICH.skip + 1 end }
  end
  return { renditions = function(self)
             local i = 0
             return function() i = i + 1; if ds[i] then return i, ds[i] end end
           end,
           doExportOnCurrentTask = function() error("phien mot lan khong duoc goi doExportOnCurrentTask") end }
end
local fake = {
  LrFileUtils = { exists = function(p) return py_exists(p) end, delete = function(p) return py_delete(p) end,
                  move = function(a, b) return py_move(a, b) end,
                  createAllDirectories = function(p) return py_mkdirs(p) end },
  LrPathUtils = { child = function(a, b) return a .. "/" .. b end,
                  leafName = function(p) return string.match(p, "[^/\\]+$") end,
                  removeExtension = function(p) return (string.gsub(p, "%%.[^.]*$", "")) end },
  LrFunctionContext = { pcallWithContext = function(tag, fn) return pcall(fn) end },
  LrTasks = { yield = function() end, sleep = function() end },
  LrDate = { currentTime = function() return os.time() end },
  LrApplication = {},
  LrExportSession = LrExportSession,
}
function import(name) return fake[name] or {} end
package.path = [[%s/?.lua;]] .. package.path
function anhGia(n)
  local ds = {}
  for i = 1, n do
    local ten = string.format("IMG_%%04d", i)
    ds[i] = { __ten = ten, getRawMetadata = function(self, k)
      if k == "path" then return "G:/Buoi/" .. self.__ten .. ".ARW" end
      return nil end }
  end
  return ds
end
''' % (str(tam2).replace("\\", "/"), str(GOC).replace("\\", "/")))
X2 = L2.eval('require("XuatCore")')
dest = str(tam2 / "ra").replace("\\", "/")
kq = X2.xuat(L2.eval("anhGia(23)"), dest, L2.eval("{ LR_format = 'JPEG' }"))
K = L2.globals().KICH
ktra("xuat: MOT phien cho ca 23 anh (khong chia lo)", K.phien == 1 and K.soAnh[1] == 23,
     f"{K.phien} phien, {K.soAnh[1]} anh")
ktra("xuat: dem 23 anh ra, 0 loi, khong dung", kq["ra"] == 23 and kq["loi"] == 0 and not kq["da_dung"])
bang = xuat_lr.bang_anh(tam2 / "jobs")
ktra("xuat: bang anh goc -> file ra du 23 dong (ten ra khac ten goc)",
     len(bang) == 23 and bang.get("G:/Buoi/IMG_0001.ARW", "").endswith("SAY-IMG_0001.jpg"), str(list(bang.items())[:1]))
td = xuat_lr.tien_do_xuat(tam2 / "jobs")
ktra("xuat: tien do cuoi xong=23 tong=23", td.get("xong") == 23 and td.get("tong") == 23, str(td))
#  10/10 (ke thua NEXUS): hang doi TUNG ANH — anh k bat dau render thi da co k-1 dong
co, hd, het, off = xuat_lr.doc_hang_doi(0, tam2 / "jobs")
ktra("hang doi: 23 dong goc->jpg + '#het 23', doc tu byte 0",
     co and len(hd) == 23 and het == 23 and hd[0][0] == "G:/Buoi/IMG_0001.ARW"
     and hd[0][1].endswith("SAY-IMG_0001.jpg"), f"{len(hd)} dong, het={het}")
moc = [K.hd[k] for k in range(1, 24)]
ktra("hang doi: ghi NGAY sau moi anh (anh k render khi da co k-1 dong)",
     moc == list(range(0, 23)), str(moc[:6]))
co2, hd2, het2, off2 = xuat_lr.doc_hang_doi(off, tam2 / "jobs")
ktra("hang doi: doc tiep tu byte cu -> khong lap dong", co2 and hd2 == [] and off2 == off)
src_x2 = (GOC / "XuatCore.lua").read_text(encoding="utf-8")
ktra("hang doi: '#het' ghi TRUOC tien do 'xong' (app thay xong la da du hang doi)",
     src_x2.index("M.hetHangDoi(ra)") < src_x2.index("ghi(true)", src_x2.index("M.hetHangDoi(ra)") - 200))
ktra("xuat: ghi nhip 'xuat anh 23/23'", "xuất ảnh 23/23" in (tam2 / "jobs" / "plugin_song.txt").read_text(encoding="utf-8"))
L2.execute("KICH.phien = 0; KICH.soAnh = {}; KICH.render = 0; KICH.boQua = { IMG_0001 = true, IMG_0002 = true, IMG_0003 = true, IMG_0004 = true }")
kq = X2.xuat(L2.eval("anhGia(10)"), dest + "2", L2.eval("{ LR_format = 'JPEG' }"))
ktra("xuat: 4 anh khong ra file -> ra 6, loi 4", kq["ra"] == 6 and kq["loi"] == 4, f"{kq['ra']} / {kq['loi']}")
L2.execute("KICH.phien = 0; KICH.soAnh = {}; KICH.render = 0; KICH.boQua = {}; KICH.skip = 0; KICH.datCoSau = 5")
kq = X2.xuat(L2.eval("anhGia(50)"), dest + "3", L2.eval("{ LR_format = 'JPEG' }"))
K = L2.globals().KICH
ktra("xuat: xin dung sau anh thu 5 -> ra 5, 45 anh skipRender, loi 0, co dung bi xoa",
     kq["ra"] == 5 and kq["da_dung"] and K.skip == 45 and kq["loi"] == 0
     and not (tam2 / "jobs" / "request_xuatanh_dung.txt").exists(),
     f"ra {kq['ra']} · skip {K.skip} · loi {kq['loi']}")
shutil.rmtree(tam2, ignore_errors=True)

shutil.rmtree(tam, ignore_errors=True)
print("TAT CA DAT" if not LOI else f"{len(LOI)} LOI")
sys.exit(1 if LOI else 0)
