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
#  12/10: dòng "anh=<đường dẫn>" -> chỉ xuất đúng những ảnh đó (Retouch chế độ RAW)
f_, o_, ts_ = X.docDong(L.table("F:/Buoi", "dest=F:/Giao", r"anh=G:\Buoi\DSC01.ARW",
                                r"anh=G:\Buoi\DSC 03.ARW", "ts	s	LR_format	JPEG"))
ds_anh = [o_["anh"][i] for i in range(1, 3)] if o_["anh"] else []
ktra("docDong: nhiều dòng anh= gom thành danh sách",
     ds_anh == [r"G:\Buoi\DSC01.ARW", r"G:\Buoi\DSC 03.ARW"], str(ds_anh))
ph = L.table("g:/buoi/dsc01.arw", r"G:\Buoi\DSC02.ARW", r"G:\Buoi\DSC 03.ARW")
loc = X.locTheoDs(ph, o_["anh"], L.eval("function(p) return p end"))
ktra("locTheoDs: giữ đúng ảnh chọn, không phân biệt hoa thường / dấu gạch",
     [loc[i] for i in range(1, len(loc) + 1)] == ["g:/buoi/dsc01.arw", r"G:\Buoi\DSC 03.ARW"],
     str([loc[i] for i in range(1, len(loc) + 1)]))
loc0 = X.locTheoDs(ph, L.table(), L.eval("function(p) return p end"))
ktra("locTheoDs: danh sách rỗng -> giữ hết", len(loc0) == 3)
ktra("runRequest: có danh sách ảnh thì KHÔNG lọc sao",
     "locTheoDs(photos, opts.anh" in src_x if "src_x" in dir() else
     "locTheoDs(photos, opts.anh" in (GOC / "XuatCore.lua").read_text(encoding="utf-8"))
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
KICH = { phien = 0, soAnh = {}, boQua = {}, datCoSau = nil, skip = 0, render = 0, hd = {},
         thanh = {}, huySau = nil }
local LrProgressScope = function(params)
  local t = { title = params.title, phan = {}, chu = {}, xong = false, huyDuoc = false }
  function t:setCancelable(b) self.huyDuoc = b end
  function t:setCaption(c) self.chu[#self.chu + 1] = c end
  function t:setPortionComplete(a, b) self.phan[#self.phan + 1] = a .. "/" .. b end
  function t:isCanceled()
    return self.daHuy or (KICH.huySau ~= nil and KICH.render >= KICH.huySau)
  end
  function t:cancel() self.daHuy = true end
  function t:done() self.xong = true end
  KICH.thanh[#KICH.thanh + 1] = t
  return t
end
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
  return { renditions = function(self, ts)
             local i = 0
             local sc = ts and ts.progressScope
             KICH.coThanh = sc ~= nil and ts.stopIfCanceled == true
             return function()
               --[[ Lightroom that: phien da bat dau thi render NEN ca phan con lai;
                    chi huy thanh tien do (stopIfCanceled) moi dung duoc. ]]
               if sc and ts.stopIfCanceled and sc:isCanceled() then
                 return nil
               end
               i = i + 1
               if ds[i] then return i, ds[i] end
             end
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
  LrProgressScope = LrProgressScope,
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
ktra("xuat: xin dung sau anh thu 5 -> ra 5, HUY thanh -> Lightroom ngung han (khong render nen), co dung bi xoa",
     kq["ra"] == 5 and kq["da_dung"] and K.thanh[len(K.thanh)].daHuy and K.render == 5
     and kq["loi"] == 0 and not (tam2 / "jobs" / "request_xuatanh_dung.txt").exists(),
     f"ra {kq['ra']} · render {K.render} · huy thanh {K.thanh[len(K.thanh)].daHuy}")
ktra("phien xuat gan vao thanh tien do (progressScope + stopIfCanceled)", bool(K.coThanh))
# ---- 10/10: thanh tien do TRONG Lightroom + huy tu Lightroom
L2.execute("KICH.phien = 0; KICH.soAnh = {}; KICH.render = 0; KICH.boQua = {}; KICH.skip = 0; "
           "KICH.datCoSau = nil; KICH.thanh = {}; KICH.huySau = nil")
kq = X2.xuat(L2.eval("anhGia(8)"), dest + "4", L2.eval("{ LR_format = 'JPEG' }"))
th = L2.globals().KICH.thanh[1]
ktra("Lightroom: co thanh tien do 'AutoTone: xuat anh', huy duoc, cap nhat tung anh, dong khi xong",
     th is not None and "xuất ảnh" in th.title and th.huyDuoc and th.phan[8] == "8/8"
     and th.xong and "Xuất ảnh 8/8" in th.chu[len(th.chu)], str(th and list(th.phan.values())))
L2.execute("KICH.render = 0; KICH.skip = 0; KICH.thanh = {}; KICH.huySau = 3")
kq = X2.xuat(L2.eval("anhGia(10)"), dest + "5", L2.eval("{ LR_format = 'JPEG' }"))
K = L2.globals().KICH
ktra("bam huy tren thanh Lightroom sau anh 3 -> dung: ra 3, Lightroom ngung, thanh dong",
     kq["ra"] == 3 and kq["da_dung"] and kq["huy_lr"] and K.render == 3 and K.thanh[1].xong,
     f"ra {kq['ra']} · render {K.render} · huy_lr {kq['huy_lr']}")
co, hd, het, _off = xuat_lr.doc_hang_doi(0, tam2 / "jobs")
ktra("huy giua chung: hang doi van du anh da ra + '#het 3' (app retouch anh da xuat)",
     len(hd) == 3 and het == 3, f"{len(hd)} · het={het}")
src_x3 = (GOC / "XuatCore.lua").read_text(encoding="utf-8")
ktra("runRequest bao app 'da huy tren thanh tien do Lightroom'",
     "da huy tren thanh tien do Lightroom" in src_x3 and "res.huy_lr" in src_x3)
shutil.rmtree(tam2, ignore_errors=True)

# ---- 7. DanhSachCore (13/10): danh sach anh cua buoi trong catalog -> luoi app
import autotone as at_
DS = L.eval('require("DanhSachCore")')
L.execute('''
DS_ANH = {}
local function anh(p) return { p = p, getRawMetadata = function(self, k) return self.p end } end
DS_THEM = function(p) DS_ANH[#DS_ANH + 1] = anh(p) end
DS_BO = function(i) table.remove(DS_ANH, i) end
DS_CO_THU_MUC = true
local cat = { getFolderByPath = function(self, p)
                  if not DS_CO_THU_MUC then return nil end
                  return { getPhotos = function(self, con)
                      local t = {} for i = 1, #DS_ANH do t[i] = DS_ANH[i] end return t end }
              end }
local LrApplication = import("LrApplication")
LrApplication.activeCatalog = function() return cat end
''')
for p in ("G:/BuoiX/DSC02.ARW", "G:/BuoiX/DSC01.ARW", "G:/BuoiX/DSC03.ARW"):
    L.globals().DS_THEM(p)
at_.theo_doi_ds_lr("G:/BuoiX", True, job_dir=jobs)
ktra("theo_doi_ds_lr: lan hai cung noi dung -> khong ghi lai",
     at_.theo_doi_ds_lr("G:/BuoiX", True, job_dir=jobs) is False)
ghi1 = DS.runTheoDoi(True)
kq1 = at_.doc_ds_lr("G:/BuoiX", job_dir=jobs)
ktra("DanhSach: ghi ds_catalog.tsv, app doc ra du 3 anh (khong phan biet hoa thuong)",
     ghi1 is True and kq1 is not None and len(kq1[0]) == 3
     and at_.khoa_duong_dan("g:/buoix/dsc01.arw") in kq1[0], str(kq1 and sorted(kq1[0])))
ktra("DanhSach: khong doi gi -> khong ghi lai", DS.runTheoDoi(True) is False)
L.globals().DS_BO(1)
os.utime(jobs / "ds_catalog.tsv", (1, 1))          # mtime khac han -> app doc lai
ghi2 = DS.runTheoDoi(True)
kq2 = at_.doc_ds_lr("G:/BuoiX", job_dir=jobs)
ktra("DanhSach: Lightroom xoa 1 anh -> file con 2 anh",
     ghi2 is True and kq2 is not None and len(kq2[0]) == 2
     and at_.khoa_duong_dan("G:/BuoiX/DSC02.ARW") not in kq2[0], str(kq2 and sorted(kq2[0])))
ktra("doc_ds_lr: file cua buoi KHAC -> None (khong loc nham)",
     at_.doc_ds_lr("G:/BuoiKhac", job_dir=jobs) is None)
L.globals().DS_CO_THU_MUC = False
DS.runTheoDoi(True)
ktra("DanhSach: thu muc chua import vao catalog -> trong_catalog=0 -> app khong loc (None)",
     "#trong_catalog=0" in (jobs / "ds_catalog.tsv").read_text(encoding="utf-8")
     and at_.doc_ds_lr("G:/BuoiX", job_dir=jobs) is None)
(jobs / at_.TEN_THEO_DOI_DS).unlink()
ktra("DanhSach: khong co yeu cau theo doi -> khong lam gi", DS.runTheoDoi(True) is False)
#  7b. cay thu muc cua catalog (cot Thu muc)
L.execute('''
local function tm(p, n, con) return { p = p, n = n, con = con or {},
    getPath = function(self) return self.p end,
    getPhotos = function(self, gom) local t = {} for i = 1, self.n do t[i] = i end return t end,
    getChildren = function(self) return self.con end } end
TM_GOC = { tm([[G:\\]], 0, { tm([[G:\\BVDay3]], 1813), tm([[G:\\Quyen]], 1, { tm([[G:\\Quyen\\Ngay1]], 935) }) }) }
local cat = { getFolders = function(self) return TM_GOC end }
local LrApplication = import("LrApplication")
LrApplication.activeCatalog = function() return cat end
''')
ktra("ThuMuc: chua co yeu cau -> khong lam gi", DS.runThuMuc(True) is False)
at_.theo_doi_thu_muc_lr(job_dir=jobs)
ktra("ThuMuc: co yeu cau -> ghi thu_muc_catalog.tsv", DS.runThuMuc(True) is True)
kq_tm = at_.doc_thu_muc_lr(job_dir=jobs)
ktra("ThuMuc: app doc du 4 thu muc, cha / so anh rieng dung",
     kq_tm is not None and kq_tm[0] == [("G:\\", "", 0), ("G:\\BVDay3", "G:\\", 1813),
                                        ("G:\\Quyen", "G:\\", 1),
                                        ("G:\\Quyen\\Ngay1", "G:\\Quyen", 935)],
     str(kq_tm and kq_tm[0]))
ktra("ThuMuc: khong doi gi -> khong ghi lai", DS.runThuMuc(True) is False)

# ---- 8. DenoiseCore (13/10): bat Denoise tung anh trong Develop
L.execute('''
DN = { trangThai = {}, chon = nil, module = "library", vao = {}, goi = 0 }
local function anh(i, p) return { localIdentifier = i, p = p,
    getFormattedMetadata = function(self) return self.p end } end
DN.ds = { ["G:/B/A1.ARW"] = anh(1, "A1"), ["G:/B/A2.ARW"] = anh(2, "A2") }
DN.trangThai[2] = true                        -- A2 da bat Denoise tu truoc
DC_GIA = {
  getEnhancePanelState = function()
    return { denoiseEnabled = true, denoiseState = DN.trangThai[DN.chon and DN.chon.localIdentifier] or false }
  end,
  setEnhance = function(ten, v) DN.goi = DN.goi + 1
    --  Auto Sync bật trong Develop: thay đổi áp cho MỌI ảnh đang chọn (như Lightroom)
    if DN.autoSync and DN.chonDs then
      for _, p in ipairs(DN.chonDs) do DN.trangThai[p.localIdentifier] = v end
    else
      DN.trangThai[DN.chon.localIdentifier] = v
    end
    if DN.khiBat then DN.khiBat() end end,
}
AV_GIA = { getCurrentModuleName = function() return DN.module end,
           switchToModule = function(m) DN.module = m; DN.vao[#DN.vao + 1] = m end }
local cat = { findPhotoByPath = function(self, p) return DN.ds[p] end,
              setSelectedPhotos = function(self, a, ds) DN.chon = a; DN.chonDs = ds end,
              getTargetPhoto = function(self) return DN.chon end,
              getTargetPhotos = function(self) return {} end }
local LrApplication = import("LrApplication")
LrApplication.activeCatalog = function() return cat end
local cu = import
function import(n)
  if n == "LrDevelopController" then return DC_GIA end
  if n == "LrApplicationView" then return AV_GIA end
  return cu(n)
end
''')
DN = L.eval('require("DenoiseCore")')
ma_, ds_ = DN.phanTich("#ma=m7\nG:/B/A1.ARW\n\n G:/B/A2.ARW \n#x\n")
ktra("DenoiseCore.phanTich: ma + danh sach (bo dong trong / chu thich)",
     ma_ == "m7" and [ds_[i] for i in range(1, len(ds_) + 1)] == ["G:/B/A1.ARW", "G:/B/A2.ARW"])
ktra("DenoiseCore.coHam: thieu ham -> false, co setEnhance -> true",
     DN.coHam(L.eval("{}")) is False and DN.coHam(L.eval("DC_GIA")) is True)
ktra("DenoiseCore.dangBat: true / 'on' / false",
     DN.dangBat(L.eval("{ denoiseState = true }")) and DN.dangBat(L.eval("{ denoiseState = 'on' }"))
     and not DN.dangBat(L.eval("{ denoiseState = false }")) and not DN.dangBat(None))
items_dn = [{"path": "G:/B/A1.ARW", "iso": 3200}, {"path": "G:/B/A2.ARW", "iso": 2000},
            {"path": "G:/B/A3.ARW", "iso": 6400}, {"path": "G:/B/A4.ARW", "iso": 800},
            {"path": "G:/B/A5.ARW", "iso": 4000, "ngoai_xuat": True}]
chon_dn = at_.anh_can_denoise(items_dn, {"denoise": True, "denoise_iso": 2000})
ktra("anh_can_denoise: ISO >= 2000, bo anh ngoai ban xuat / ISO thap",
     chon_dn == ["G:/B/A1.ARW", "G:/B/A2.ARW", "G:/B/A3.ARW"], str(chon_dn))
ktra("anh_can_denoise: tat Denoise -> khong anh nao",
     at_.anh_can_denoise(items_dn, {"denoise": False, "denoise_iso": 2000}) == [])
at_.yeu_cau_denoise(chon_dn, "m8", job_dir=jobs)
ktra("tien_do_denoise: truoc khi plugin nhan -> cho, chua co ket qua",
     at_.tien_do_denoise("m8", job_dir=jobs)["cho"] is True)
DN.runRequest()
td_dn = at_.tien_do_denoise("m8", job_dir=jobs)
kq_dn = td_dn["ket_qua"] or {}
G = L.globals().DN
ktra("Denoise: bat A1, A2 da co, A3 khong co trong catalog",
     kq_dn.get("bat") == "1" and kq_dn.get("da_co") == "1" and kq_dn.get("khong_thay") == "1"
     and G.goi == 1 and G.trangThai[1] is True, str(kq_dn))
ktra("Denoise: vao Develop roi tra ve module cu (library); tien do 2/2; yeu cau da duoc nhan",
     G.module == "library" and G.vao[1] == "develop" and td_dn["xong"] == 2 and td_dn["tong"] == 2
     and td_dn["cho"] is False, f"{G.module} · {td_dn}")
ktra("tien_do_denoise: ma luot khac -> khong lan ket qua",
     at_.tien_do_denoise("m-khac", job_dir=jobs)["ket_qua"] is None)
# 8b. 14/10 user: "Khi Denoise ảnh mà bấm dừng thì vẫn đang chạy tiếp" -> dừng ngay
L.execute('''
DN.trangThai = {}; DN.goi = 0; DN.vao = {}; DN.module = "library"
local function anh(i, p) return { localIdentifier = i, p = p,
    getFormattedMetadata = function(self) return self.p end } end
DN.ds["G:/B/A6.ARW"] = anh(6, "A6"); DN.ds["G:/B/A7.ARW"] = anh(7, "A7")
''')
f_dung = jobs / at_.TEN_DUNG_DENOISE
G.khiBat = lambda: at_.dung_denoise("m10", job_dir=jobs)     # bấm Dừng ngay sau ảnh đầu
at_.yeu_cau_denoise(["G:/B/A1.ARW", "G:/B/A6.ARW", "G:/B/A7.ARW"], "m10", job_dir=jobs)
DN.runRequest()
G.khiBat = None
kq10 = at_.tien_do_denoise("m10", job_dir=jobs)["ket_qua"] or {}
ktra("Dừng Denoise: app xin dừng sau ảnh 1 -> plugin dừng NGAY (bật 1/3, dung=1)",
     kq10.get("bat") == "1" and kq10.get("dung") == "1" and kq10.get("ly_do") == "dung"
     and G.goi == 1 and not G.trangThai[6] and not G.trangThai[7], str(kq10))
ktra("Dừng Denoise: vẫn trả module cũ (library) + xoá file dừng",
     G.module == "library" and not f_dung.exists(), f"{G.module} · {f_dung.exists()}")
L.execute('DN.trangThai = {}; DN.goi = 0; DN.module = "library"')
at_.yeu_cau_denoise(["G:/B/A1.ARW", "G:/B/A6.ARW"], "m11", job_dir=jobs)
at_.dung_denoise("m-cu", job_dir=jobs)                       # lệnh dừng của lượt KHÁC
DN.runRequest()
kq11 = at_.tien_do_denoise("m11", job_dir=jobs)["ket_qua"] or {}
ktra("Dừng Denoise: file dừng của lượt khác KHÔNG dừng lượt này (bật 2/2) và bị xoá",
     kq11.get("bat") == "2" and not kq11.get("dung") and not f_dung.exists(), str(kq11))
at_.dung_denoise("m11", job_dir=jobs)
at_.yeu_cau_denoise(["G:/B/A1.ARW"], "m12", job_dir=jobs)
ktra("yeu_cau_denoise: gửi lượt mới thì xoá lệnh dừng cũ (plugin không dừng nhầm)",
     not f_dung.exists())
(jobs / at_.TEN_YC_DENOISE).unlink()
ma_d, = [x for x in [L.eval('require("DenoiseCore")').xinDung("ma=m5\n", "m5")]]
ktra("DenoiseCore.xinDung: đúng mã -> true, khác mã / rỗng -> false",
     ma_d is True and DN.xinDung("ma=m5\n", "m6") is False and DN.xinDung("", "m5") is False)

# 8c. 14/10 user: "gom hết vào thành 1 list rồi cho hiển thị theo tiến trình"
L.execute('DN.trangThai = {}; DN.goi = 0; DN.module = "library"; DN.autoSync = true')
at_.yeu_cau_denoise(["G:/B/A1.ARW", "G:/B/A6.ARW", "G:/B/A7.ARW"], "m13", job_dir=jobs)
DN.runRequest()
kq13 = at_.tien_do_denoise("m13", job_dir=jobs)["ket_qua"] or {}
td13 = at_.tien_do_denoise("m13", job_dir=jobs)
ktra("Gom 1 lệnh: Auto Sync bật -> MỘT setEnhance cho cả 3 ảnh, lo=1, tiến độ 3/3",
     G.goi == 1 and kq13.get("lo") == "1" and kq13.get("bat") == "3"
     and G.trangThai[1] and G.trangThai[6] and G.trangThai[7] and td13["xong"] == 3,
     f"goi={G.goi} · {kq13}")
ktra("…vẫn trả module cũ", G.module == "library")
L.execute('DN.trangThai = {}; DN.goi = 0; DN.module = "library"; DN.autoSync = false')
at_.yeu_cau_denoise(["G:/B/A1.ARW", "G:/B/A6.ARW", "G:/B/A7.ARW"], "m14", job_dir=jobs)
DN.runRequest()
kq14 = at_.tien_do_denoise("m14", job_dir=jobs)["ket_qua"] or {}
ktra("Auto Sync tắt: thử gom không được -> từng ảnh, ảnh đầu KHÔNG bật lại (3 lệnh, bật 3)",
     G.goi == 3 and not kq14.get("lo") and kq14.get("bat") == "3" and kq14.get("da_co") == "0"
     and G.trangThai[1] and G.trangThai[6] and G.trangThai[7], f"goi={G.goi} · {kq14}")
L.execute('DN.trangThai = {}; DN.goi = 0; DN.autoSync = true; DN.trangThai[7] = true')
at_.yeu_cau_denoise(["G:/B/A1.ARW", "G:/B/A6.ARW", "G:/B/A7.ARW"], "m15", job_dir=jobs)
DN.runRequest()
kq15 = at_.tien_do_denoise("m15", job_dir=jobs)["ket_qua"] or {}
ktra("ảnh cuối đã có Denoise từ trước: không soát được -> không gom (không báo gom nhầm)",
     not kq15.get("lo") and kq15.get("da_co") == "1" and kq15.get("bat") == "2", str(kq15))
L.execute('DN.autoSync = false')

L.execute('DC_GIA.setEnhance = nil; DC_GIA.toggleEnhance = nil')
at_.yeu_cau_denoise(["G:/B/A1.ARW"], "m9", job_dir=jobs)
DN.runRequest()
ktra("Denoise: Lightroom cu (khong co setEnhance) -> ly_do lightroom-chua-ho-tro",
     (at_.tien_do_denoise("m9", job_dir=jobs)["ket_qua"] or {}).get("ly_do") == "lightroom-chua-ho-tro")
src_init = (GOC / "Init.lua").read_text(encoding="utf-8")
ktra("Init.lua goi DanhSach.runTheoDoi + Denoise.runRequest (Denoise chi khi autoApply)",
     "DanhSach.runTheoDoi" in src_init and "Denoise and prefs.autoApply" in src_init)

# ---- 8d. AutoCore (16/10): Auto (bảng Basic) cho cả buổi — "Quy trình Auto"
#  16/10 tối: CÁCH GOM — photo:applyDevelopSettings({AutoTone = true}, tên, true) theo lô, không vào
#  Develop; thử không ăn -> cách cũ (chọn từng ảnh trong Develop + setAutoTone).
#  Catalog giả ghi lệnh như NHẬT KÝ của Lightroom: áp khi giao dịch xong, giao dịch lỗi thì huỷ cả lô.
import auto_lr  # noqa: E402
L.execute("""
AU = { st = {}, chon = nil, module = "library", vao = {}, goi = 0, kieu = "tinh", gd = 0, lo = {},
       ten = {}, cho = {}, loiLoTo = false }
function AU.daAuto() for i = 21, 23 do AU.auto1(i) end end
local function auto1(i) local s = AU.st[i]; s.Exposure2012 = -0.37; s.Contrast2012 = 7; s.Highlights2012 = -32
  s.Shadows2012 = 40; s.Whites2012 = 45; s.Blacks2012 = -27; s.Vibrance = 14; s.AutoTone = nil end
AU.auto1 = auto1
local function apDung(op)
  local st = AU.st[op.i]
  for k, v in pairs(op.s) do if k ~= "AutoTone" then st[k] = v end end     -- khoá thường: ghi như LR
  if op.s.AutoTone == false then st.AutoTone = nil
  elseif AU.kieu == "tinh" and op.s.AutoTone and op.phang then auto1(op.i)
  elseif AU.kieu == "co" and op.s.AutoTone then st.AutoTone = true end
end
local function anh(i, p) return { localIdentifier = i, p = p,
    getDevelopSettings = function(self) local t = {} for k, v in pairs(AU.st[i] or {}) do t[k] = v end return t end,
    applyDevelopSettings = function(self, s, ten, phang)
      AU.ten[#AU.ten + 1] = ten; AU.cho[#AU.cho + 1] = { i = i, s = s, phang = phang } end,
    getRawMetadata = function(self, k) if k == "path" then return self.p end end } end
AU.ds = { ["G:/C/B1.ARW"] = anh(21, "G:/C/B1.ARW"), ["G:/C/B2.ARW"] = anh(22, "G:/C/B2.ARW"),
          ["G:/C/B3.ARW"] = anh(23, "G:/C/B3.ARW") }
function AU.datLai(kieu, pv)
  for i = 21, 23 do AU.st[i] = { Exposure2012 = 0.5, Contrast2012 = 5, Highlights2012 = -29, Shadows2012 = 16,
      Whites2012 = -25, Blacks2012 = -18, Vibrance = 0, Saturation = 0, Temperature = 5000, Tint = 10,
      WhiteBalance = "Custom", ProcessVersion = pv or "15.4" } end
  AU.goi = 0; AU.vao = {}; AU.module = "library"; AU.kieu = kieu or "tinh"; AU.gd = 0; AU.lo = {}
  AU.ten = {}; AU.cho = {}; AU.loiLoTo = false
end
AU.datLai()
DC_AU = { setAutoTone = function() AU.goi = AU.goi + 1; auto1(AU.chon.localIdentifier)
    if AU.khiBam then AU.khiBam() end end }
AV_AU = { getCurrentModuleName = function() return AU.module end,
          switchToModule = function(m) AU.module = m; AU.vao[#AU.vao + 1] = m end }
local cat = { findPhotoByPath = function(self, p) return AU.ds[p] end,
              setSelectedPhotos = function(self, a, ds) AU.chon = a end,
              getTargetPhoto = function(self) return AU.chon end,
              getTargetPhotos = function(self) return {} end,
              withWriteAccessDo = function(self, ten, fn, opt)
                  AU.gd = AU.gd + 1; AU.cho = {}
                  fn()
                  local ops = AU.cho; AU.cho = {}
                  AU.lo[#AU.lo + 1] = #ops
                  if AU.loiLoTo and #ops > 1 then error("giao dich het gio") end
                  for _, op in ipairs(ops) do apDung(op) end
                  if AU.khiGd then AU.khiGd() end end }
local LrApplication = import("LrApplication")
LrApplication.activeCatalog = function() return cat end
local cu_au = import
function import(n)
  if n == "LrDevelopController" then return DC_AU end
  if n == "LrApplicationView" then return AV_AU end
  return cu_au(n)
end
""")
AUc = L.eval('require("AutoCore")')
AUc.CHO_THU = 0
AUc.CHO_MOI_ANH = 0
GA = L.globals().AU


def ds_lua(t):
    n = L.eval("function(t) return #t end")(t)
    return [t[i] for i in range(1, n + 1)]


ma_a, ds_a = AUc.phanTich("#ma=a1\nG:/C/B1.ARW\n\n G:/C/B2.ARW \n#x\n")
ktra("AutoCore.phanTich: mã + danh sách (bỏ dòng trống / chú thích)",
     ma_a == "a1" and [ds_a[i] for i in range(1, len(ds_a) + 1)] == ["G:/C/B1.ARW", "G:/C/B2.ARW"])
ktra("AutoCore.coHam: thiếu setAutoTone -> false, có -> true",
     AUc.coHam(L.eval("{}")) is False and AUc.coHam(L.eval("DC_AU")) is True)
ktra("AutoCore.daDoi: một ô tông đổi -> true; như nhau -> false",
     AUc.daDoi(L.eval("{ Exposure2012 = 0.5 }"), L.eval("{ Exposure2012 = 0.2 }")) is True
     and AUc.daDoi(L.eval("{ Exposure2012 = 0.5, Contrast2012 = 3 }"),
                   L.eval("{ Exposure2012 = 0.5, Contrast2012 = 3 }")) is False)
ktra("AutoCore.xinDung: đúng mã -> true, mã khác -> false",
     AUc.xinDung("ma=a5\n", "a5") is True and AUc.xinDung("ma=a5\n", "a6") is False)
ktra("AutoCore.conCo: còn cờ AutoTone (chưa tính) -> true; không cờ -> false",
     AUc.conCo(L.eval("{ AutoTone = true }")) is True and AUc.conCo(L.eval("{ Exposure2012 = 1 }")) is False)
ktra("AutoCore.coCanh: bản xử lý 2012+ có Whites/Blacks -> true; PV2010 '5.7' / thiếu ô -> false",
     AUc.coCanh(L.eval('{ Whites2012 = 3, Blacks2012 = -2, ProcessVersion = "15.4" }')) is True
     and AUc.coCanh(L.eval('{ Whites2012 = 3, Blacks2012 = -2, ProcessVersion = "5.7" }')) is False
     and AUc.coCanh(L.eval('{ Exposure2012 = 1 }')) is False)
ktra("AutoCore.conCanh: còn đúng hai số canh -> true; Auto ghi đè một ô -> false",
     AUc.conCanh(L.eval("{ Whites2012 = -100, Blacks2012 = 100 }")) is True
     and AUc.conCanh(L.eval("{ Whites2012 = 45, Blacks2012 = 100 }")) is False)
ktra("AutoCore.coLo: lô 1 ảnh 0,5 giây -> 8 ảnh (~4 giây); không tốn giờ -> trần 40; 60 giây -> 1",
     AUc.coLo(1, 0.5) == 8 and AUc.coLo(10, 0) == 40 and AUc.coLo(5, 60) == 1,
     f"{AUc.coLo(1, 0.5)} · {AUc.coLo(10, 0)} · {AUc.coLo(5, 60)}")

# gom được: ảnh thử đi lẻ, rồi cả phần còn lại một giao dịch
auto_lr.yeu_cau(["G:/C/B1.ARW", "G:/C/B2.ARW", "G:/C/B3.ARW", "G:/C/KHONG.ARW"], "a2", job_dir=jobs)
ktra("auto_lr.tien_do: trước khi plugin nhận -> chờ, chưa có kết quả",
     auto_lr.tien_do("a2", job_dir=jobs)["cho"] is True and auto_lr.tien_do("a2", job_dir=jobs)["ket_qua"] is None)
AUc.runRequest()
td_a = auto_lr.tien_do("a2", job_dir=jobs)
kq_a = td_a["ket_qua"] or {}
bg_a = auto_lr.bang("a2", job_dir=jobs)
ktra("GOM: Auto 3 ảnh qua applyDevelopSettings (cach=gom, lo=1), 1 ảnh không có trong catalog",
     kq_a.get("bat") == "3" and kq_a.get("khong_thay") == "1" and kq_a.get("cach") == "gom"
     and kq_a.get("lo") == "1" and kq_a.get("giay") is not None, str(kq_a))
ktra("…ảnh thử ĐI LẺ (1 ảnh) rồi 2 ảnh còn lại MỘT giao dịch; mọi lệnh có AutoTone + flattenAutoNow",
     ds_lua(GA.lo) == [1, 2] and GA.gd == 2, str(ds_lua(GA.lo)))
ktra("…số canh của ảnh thử bị Auto ghi đè (không còn Whites −100 / Blacks +100 ở ảnh nào)",
     all(v.get("Whites2012") == 45 and v.get("Blacks2012") == -27 for v in bg_a.values()))
ktra("…bước History 'AutoTone: Auto'", set(ds_lua(GA.ten)) == {"AutoTone: Auto"}, str(ds_lua(GA.ten)))
ktra("…KHÔNG vào Develop, không bấm setAutoTone, không đổi ảnh đang chọn",
     GA.vao[1] is None and GA.goi == 0 and GA.module == "library" and GA.chon is None,
     f"{GA.vao[1]} · goi={GA.goi} · {GA.module}")
ktra("…bảng auto_anh.tsv: thông số SAU Auto của đúng 3 ảnh (app làm mốc mới)",
     len(bg_a) == 3 and all(v.get("Exposure2012") == -0.37 and v.get("Shadows2012") == 40
                            and v.get("Vibrance") == 14 and v.get("WhiteBalance") == "Custom"
                            for v in bg_a.values()), str(list(bg_a.values())[:1]))
ktra("…tiến độ 3/3; yêu cầu đã nhận", td_a["xong"] == 3 and td_a["tong"] == 3 and td_a["cho"] is False,
     str(td_a))
ktra("auto_lr.bang: mã lượt khác -> rỗng", auto_lr.bang("a-khac", job_dir=jobs) == {})

# ảnh ĐÃ Auto từ trước (Auto lại ra đúng số đang có) — canh giúp không về cách cũ oan
L.execute("AU.datLai(); AU.daAuto()")
auto_lr.yeu_cau(["G:/C/B1.ARW", "G:/C/B2.ARW", "G:/C/B3.ARW"], "a10", job_dir=jobs)
AUc.runRequest()
kq10 = auto_lr.tien_do("a10", job_dir=jobs)["ket_qua"] or {}
bg10 = auto_lr.bang("a10", job_dir=jobs)
ktra("Ảnh đã Auto từ trước: vẫn GOM (canh bị ghi đè), không đổi 3, không Develop, bảng đủ 3 số Auto",
     kq10.get("cach") == "gom" and kq10.get("khong_doi") == "3" and kq10.get("bat") == "0" and GA.goi == 0
     and len(bg10) == 3 and all(v.get("Whites2012") == 45 for v in bg10.values()), f"{kq10} · goi={GA.goi}")

# lô to hỏng (Lightroom huỷ cả lô) -> làm lại từng ảnh
L.execute("AU.datLai(); AU.loiLoTo = true")
auto_lr.yeu_cau(["G:/C/B1.ARW", "G:/C/B2.ARW", "G:/C/B3.ARW"], "a3", job_dir=jobs)
AUc.runRequest()
kq3 = auto_lr.tien_do("a3", job_dir=jobs)["ket_qua"] or {}
ktra("GOM: lô 2 ảnh hỏng -> làm lại từng ảnh, vẫn đủ 3 ảnh, không cần Develop",
     kq3.get("bat") == "3" and kq3.get("cach") == "gom" and ds_lua(GA.lo) == [1, 2, 1, 1]
     and GA.goi == 0 and len(auto_lr.bang("a3", job_dir=jobs)) == 3, f"{kq3} · {ds_lua(GA.lo)}")

# Lightroom nhận lệnh mà để nguyên cờ AutoTone (không tính) -> cách cũ ngay sau ảnh thử đầu
L.execute('AU.datLai("co")')
auto_lr.yeu_cau(["G:/C/B1.ARW", "G:/C/B2.ARW", "G:/C/B3.ARW"], "a7", job_dir=jobs)
AUc.runRequest()
kq7 = auto_lr.tien_do("a7", job_dir=jobs)["ket_qua"] or {}
ktra("Còn cờ AutoTone (chưa tính) -> bỏ cách gom sau 1 ảnh thử (+1 giao dịch trả lại), Develop: bấm 3",
     GA.gd == 2 and "AutoTone: trả lại" in ds_lua(GA.ten) and GA.goi == 3 and kq7.get("bat") == "3" and kq7.get("cach") == "develop"
     and not kq7.get("lo"), f"gd={GA.gd} goi={GA.goi} · {kq7}")
ktra("…vào Develop rồi trả module cũ (library)", GA.vao[1] == "develop" and GA.module == "library",
     f"{GA.vao[1]} · {GA.module}")

# Lightroom bỏ qua AutoTone (ghi khoá thường): ảnh thử có canh -> canh còn nguyên -> trả lại, cách cũ
L.execute('AU.datLai("bo")')
auto_lr.yeu_cau(["G:/C/B1.ARW", "G:/C/B2.ARW", "G:/C/B3.ARW"], "a11", job_dir=jobs)
AUc.runRequest()
kq11 = auto_lr.tien_do("a11", job_dir=jobs)["ket_qua"] or {}
ktra("Bỏ qua AutoTone: canh còn nguyên -> 1 thử + 1 trả lại, rồi Develop cả 3 (số Auto thật)",
     GA.gd == 2 and GA.goi == 3 and kq11.get("cach") == "develop" and kq11.get("bat") == "3"
     and all(v.get("Whites2012") == 45 for v in auto_lr.bang("a11", job_dir=jobs).values()),
     f"gd={GA.gd} goi={GA.goi} · {kq11}")

# ảnh PV2010 (không dùng canh), Lightroom bỏ qua lệnh: thử LO_THU ảnh rồi về cách cũ
L.execute('AU.datLai("bo", "5.7")')
AUc.LO_THU = 2
auto_lr.yeu_cau(["G:/C/B1.ARW", "G:/C/B2.ARW", "G:/C/B3.ARW"], "a8", job_dir=jobs)
AUc.runRequest()
AUc.LO_THU = 5
kq8 = auto_lr.tien_do("a8", job_dir=jobs)["ket_qua"] or {}
bg8 = auto_lr.bang("a8", job_dir=jobs)
ktra("Không ảnh thử nào đổi (LO_THU 2) -> chỉ 2 giao dịch thử, rồi Develop cả 3 ảnh",
     GA.gd == 2 and GA.goi == 3 and kq8.get("bat") == "3" and kq8.get("cach") == "develop"
     and len(bg8) == 3 and all(v.get("Exposure2012") == -0.37 for v in bg8.values()),
     f"gd={GA.gd} goi={GA.goi} · {kq8}")

# Dừng — cách gom: app xin dừng sau giao dịch đầu
L.execute("AU.datLai()")
GA.khiGd = lambda: auto_lr.xin_dung("a9", job_dir=jobs)
auto_lr.yeu_cau(["G:/C/B1.ARW", "G:/C/B2.ARW", "G:/C/B3.ARW"], "a9", job_dir=jobs)
AUc.runRequest()
GA.khiGd = None
kq9 = auto_lr.tien_do("a9", job_dir=jobs)["ket_qua"] or {}
ktra("Dừng (gom): dừng sau lô đang làm (dung=1, Auto 1 ảnh), không vào Develop, xoá file dừng",
     kq9.get("dung") == "1" and kq9.get("bat") == "1" and GA.gd == 1 and GA.vao[1] is None
     and not (jobs / auto_lr.TEN_DUNG).exists(), f"{kq9} · gd={GA.gd}")

# Dừng — cách cũ (Develop)
L.execute('AU.datLai("bo")')
GA.khiBam = lambda: auto_lr.xin_dung("a4", job_dir=jobs)
auto_lr.yeu_cau(["G:/C/B1.ARW", "G:/C/B2.ARW", "G:/C/B3.ARW"], "a4", job_dir=jobs)
AUc.runRequest()
GA.khiBam = None
kq4 = auto_lr.tien_do("a4", job_dir=jobs)["ket_qua"] or {}
ktra("Dừng (Develop): app xin dừng -> plugin dừng ngay (dung=1), vẫn trả module cũ, xoá file dừng",
     kq4.get("dung") == "1" and GA.module == "library" and not (jobs / auto_lr.TEN_DUNG).exists(), str(kq4))
auto_lr.yeu_cau(["G:/C/B1.ARW"], "a5", job_dir=jobs)
ktra("auto_lr.rut_yeu_cau: plugin chưa nhận -> rút được", auto_lr.rut_yeu_cau(job_dir=jobs)
     and not auto_lr.dang_cho(job_dir=jobs))

# Lightroom không tính Auto qua SDK và không có setAutoTone
L.execute('AU.datLai("bo"); DC_AU.setAutoTone = nil')
auto_lr.yeu_cau(["G:/C/B1.ARW"], "a6", job_dir=jobs)
AUc.runRequest()
ktra("Lightroom không gom được + không có setAutoTone -> ly_do lightroom-chua-ho-tro",
     (auto_lr.tien_do("a6", job_dir=jobs)["ket_qua"] or {}).get("ly_do") == "lightroom-chua-ho-tro")
ktra("…ảnh thử được trả Whites / Blacks về số cũ (−25 / −18), không kẹt số canh",
     GA.st[21]["Whites2012"] == -25 and GA.st[21]["Blacks2012"] == -18,
     f"{GA.st[21]['Whites2012']} / {GA.st[21]['Blacks2012']}")
src_init2 = (GOC / "Init.lua").read_text(encoding="utf-8")
src_core = (GOC / "AutoToneCore.lua").read_text(encoding="utf-8")
ktra("Init.lua gọi AutoLr.runRequest chỉ khi autoApply; nhịp khai 'auto1'",
     "AutoLr and prefs.autoApply" in src_init2 and "auto1" in src_core)

# ---- 9. SaoCore (14/10): app chấm sao -> rating trong Lightroom
L.execute('''
SAO = { ghi = {}, tu_choi_0 = false, lan = 0, ten = nil }
local function anh(p) return { p = p, setRawMetadata = function(self, k, v)
    if k == "rating" and v == 0 and SAO.tu_choi_0 then error("rating 0 khong hop le") end
    if k == "rating" then SAO.ghi[self.p] = (v == nil) and "nil" or v end end } end
SAO.ds = { ["G:/S/A1.ARW"] = anh("A1"), ["G:/S/A2.ARW"] = anh("A2") }
local cat2 = { findPhotoByPath = function(self, p) return SAO.ds[p] end,
               withWriteAccessDo = function(self, ten, f, opt)
                   SAO.lan = SAO.lan + 1; SAO.ten = ten; f() end }
local LrApplication = import("LrApplication")
LrApplication.activeCatalog = function() return cat2 end
''')
SC = L.eval('require("SaoCore")')
ma_s, ds_s = SC.phanTich("#ma=s1\n4\tG:/S/A1.ARW\n0\tG:/S/A2.ARW\n9\tG:/S/X.ARW\nrac\n")
ktra("SaoCore.phanTich: ma + (sao, đường dẫn), bỏ số ngoài 0–5 / dòng rác",
     ma_s == "s1" and len(ds_s) == 2 and ds_s[1].sao == 4 and ds_s[1].p == "G:/S/A1.ARW"
     and ds_s[2].sao == 0)
at_.yeu_cau_sao({"G:/S/A1.ARW": 3}, job_dir=jobs)
at_.yeu_cau_sao({"G:/S/A2.ARW": 5, "G:/S/A3.ARW": 2}, job_dir=jobs)   # gộp, A3 không có
ktra("yeu_cau_sao: hai lần bấm trước khi Lightroom nhận -> GỘP một file",
     at_._doc_yc_sao(jobs / at_.TEN_YC_SAO) == {"G:/S/A1.ARW": 3, "G:/S/A2.ARW": 5,
                                                "G:/S/A3.ARW": 2})
SC.runRequest()
GS = L.globals().SAO
kq_s = at_._doc_kv(jobs / at_.TEN_KQ_SAO)
ktra("SaoCore: đặt rating đúng từng ảnh, MỘT giao dịch ghi, ảnh không có trong catalog đếm riêng",
     GS.ghi["A1"] == 3 and GS.ghi["A2"] == 5 and GS.lan == 1 and kq_s.get("xong") == "2"
     and kq_s.get("khong_thay") == "1" and not at_.dang_cho_sao(job_dir=jobs), str(kq_s))
L.execute('SAO.tu_choi_0 = true; SAO.lan = 0')
at_.yeu_cau_sao({"G:/S/A1.ARW": 0}, job_dir=jobs)
SC.runRequest()
kq_s = at_._doc_kv(jobs / at_.TEN_KQ_SAO)
ktra("SaoCore: Lightroom không nhận rating 0 -> thử lại bằng nil (bỏ sao), không báo lỗi",
     GS.ghi["A1"] == "nil" and GS.lan == 2 and kq_s.get("xong") == "1"
     and kq_s.get("loi") == "0", f"{GS.ghi['A1']} · {kq_s}")
ktra("Init.lua: gọi Sao.runRequest (bất kể autoApply) + thức ngay khi có request_sao.txt",
     "Sao.runRequest" in src_init and "Sao.YEU_CAU" in src_init
     and src_init.index("Sao.runRequest") < src_init.index("Denoise and prefs.autoApply"))
ktra("Nhịp plugin khai khả năng sao1 (app biết plugin mới)",
     "sao1" in (GOC / "AutoToneCore.lua").read_text(encoding="utf-8").split("M.KHA_NANG =")[1]
     .splitlines()[0])

shutil.rmtree(tam, ignore_errors=True)
print("TAT CA DAT" if not LOI else f"{len(LOI)} LOI")
sys.exit(1 if LOI else 0)
