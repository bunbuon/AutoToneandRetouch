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

shutil.rmtree(tam, ignore_errors=True)
print("TAT CA DAT" if not LOI else f"{len(LOI)} LOI")
sys.exit(1 if LOI else 0)
