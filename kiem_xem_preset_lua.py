# -*- coding: utf-8 -*-
"""Kiem XemPresetCore.lua (xem truoc preset Lightroom cho ca luoi, 9/10) bang Lua 5.1
that (lupa.lua51) + SDK gia:
  1. danh sach preset -> jobs/lr_presets.tsv (uuid, ten, nhom, thu muc)
  2. ap TAM -> render -> TRA LAI: thong so moi anh ve dung nhu cu, so khoi phuc da xoa,
     bang src->jpg du, anh khong co trong catalog dem "thieu"
  3. anh As Shot + preset co WB: tra WB bang preset cua plugin (applyDevelopSettings
     {WhiteBalance="As Shot"} KHONG xoa Kelvin — SDK gia mo phong dung bay do);
     khong tao duoc preset WB -> dem "lech" (khong im lang)
  4. so khoi phuc (Lightroom tat giua lo) -> khoiPhuc() tra lai, xoa so
  5. preset co mask / chinh cuc bo -> tu choi xem tam
  6. ap=1 (ap han) -> khong tra lai, khong so
  7. yeu cau moi giua chung -> thay luot cu; viec khac dang cho -> nhuong vong lap
  8. JSON tu viet: ma -> giai giu nguyen bang long nhau + chu Viet
Chay:  python kiem_xem_preset_lua.py    (can lupa: LUPA_DIR=<thu muc chua goi lupa>)"""
import os
import sys
import tempfile
from pathlib import Path

if os.environ.get("LUPA_DIR"):
    sys.path.insert(0, os.environ["LUPA_DIR"])
try:
    from lupa import lua51  # noqa: E402
except ImportError:
    print("BO QUA: thieu goi lupa — CHUA kiem XemPresetCore.lua")
    sys.exit(0)

GOC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "AutoTone.lrplugin"
LOI = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


tam = Path(tempfile.mkdtemp(prefix="kiem_xempreset_"))
jobs = tam / "jobs"
jobs.mkdir()
ra = tam / "ra"
L = lua51.LuaRuntime(unpack_returned_tuples=True)
g = L.globals()


def files(d):
    ds = [str(Path(d) / x) for x in sorted(os.listdir(d))]
    it = iter(ds)
    return lambda *_: next(it, None)


def ghi(p, s):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(s, encoding="utf-8")
    return True


g.py_files = files
g.py_move = lambda a, b: os.replace(a, b) or True
g.py_exists = lambda p: os.path.exists(p)
g.py_delete = lambda p: (os.remove(p) if os.path.isfile(p) else None) or True
g.py_mkdirs = lambda p: os.makedirs(p, exist_ok=True) or True
g.py_ghi = ghi
L.execute(r'''
_PLUGIN = { path = [[%s]], id = "vn.autotone" }
local fake = {
  LrFileUtils = { files = function(d) return py_files(d) end, move = function(a, b) return py_move(a, b) end,
                  exists = function(p) return py_exists(p) end, delete = function(p) return py_delete(p) end,
                  createAllDirectories = function(p) return py_mkdirs(p) end },
  LrPathUtils = { child = function(a, b) return a .. "/" .. b end,
                  leafName = function(p) return string.match(p, "[^/\\]+$") end,
                  removeExtension = function(p) return (string.gsub(p, "%%.[^%%.\\/]*$", "")) end },
  LrFunctionContext = { pcallWithContext = function(tag, fn) return pcall(fn) end },
  LrTasks = { yield = function() end, sleep = function() end },
  LrDate = { currentTime = function() return os.time() end },
  LrApplication = {},
}
-- ExportSession gia: moi rendition "render" ra <dest>/<ten>.jpg, ghi kem thong so luc render
fake.LrExportSession = function(params)
  local s = { params = params }
  function s:renditions()
    local i = 0
    local ps = params.photosToExport
    return function()
      i = i + 1
      local ph = ps[i]
      if not ph then return nil end
      local r = { photo = ph }
      function r:waitForRender()
        local dest = params.exportSettings.LR_export_destinationPathPrefix
        local base = string.gsub(string.match(ph.path, "[^/\\]+$"), "%%.[^%%.]*$", "")
        local out = dest .. "/" .. base .. ".jpg"
        py_ghi(out, "Exposure2012=" .. tostring(ph.s.Exposure2012) .. " WB=" .. tostring(ph.s.WhiteBalance)
                    .. " T=" .. tostring(ph.s.Temperature))
        return true, out
      end
      return i, r
    end
  end
  return s
end
function import(name) return fake[name] or {} end
package.path = [[%s/?.lua;]] .. package.path
''' % (str(tam).replace("\\", "/"), str(GOC).replace("\\", "/")))

# ---- catalog gia
L.execute(r'''
local LrApplication = import("LrApplication")
local function sao(t) local o = {} for k, v in pairs(t) do
  if type(v) == "table" then o[k] = sao(v) else o[k] = v end end return o end

PHOTOS, BYPATH = {}, {}
function moiAnh(path, s)
  local ph = { path = path, s = sao(s), lich_su = 0 }
  function ph:getDevelopSettings()
    local t = sao(self.s)
    -- Lightroom KHONG tra Temperature/Tint cua anh As Shot "that"
    if t.WhiteBalance == "As Shot" and not self.kelvin_ket then t.Temperature = nil t.Tint = nil end
    return t
  end
  function ph:applyDevelopSettings(s)
    for k, v in pairs(s) do self.s[k] = sao({ v })[1] end
    -- BAY NEXUS: dat lai nhan "As Shot" qua applyDevelopSettings KHONG xoa Kelvin tam
    if s.WhiteBalance == "As Shot" and self.s.Temperature ~= nil then self.kelvin_ket = true end
    self.lich_su = self.lich_su + 1
  end
  function ph:applyDevelopPreset(p, plugin)
    if p.wbPreset then
      -- ap preset WB As Shot: Lightroom tinh lai tu may -> het Kelvin tam
      self.s.WhiteBalance = p.settings.WhiteBalance
      self.s.Temperature = nil self.s.Tint = nil self.kelvin_ket = nil
    else
      for k, v in pairs(p.settings) do self.s[k] = sao({ v })[1] end
    end
    self.lich_su = self.lich_su + 1
  end
  PHOTOS[#PHOTOS + 1] = ph
  BYPATH[path] = ph
  return ph
end
CAT = { findPhotoByPath = function(self, p) return BYPATH[p] end,
        withWriteAccessDo = function(self, n, fn) fn() end }
LrApplication.activeCatalog = function() return CAT end

local function preset(uuid, name, settings)
  local p = { uuid = uuid, name = name, settings = settings }
  function p:getUuid() return self.uuid end
  function p:getName() return self.name end
  function p:getSetting() return sao(self.settings) end
  return p
end
P_AM = preset("U1", "cưới trắng hồng 1", { Exposure2012 = 0.5, WhiteBalance = "Custom",
                                         Temperature = 6200, Tint = 12, Vibrance = 20,
                                         ToneCurvePV2012 = { 0, 0, 128, 140, 255, 255 } })
P_NOWB = preset("U2", "NoWBExposure", { Exposure2012 = -0.3, Contrast2012 = 15 })
P_MASK = preset("A1", "Adaptive: Blur Background", { MaskGroupBasedCorrections = { { What = "Mask" } } })
local function folder(name, path, ps)
  return { getName = function() return name end, getPath = function() return path end,
           getDevelopPresets = function() return ps end }
end
FOLDERS = { folder("User Presets", [[C:\Users\x\AppData\Roaming\Adobe\CameraRaw\Settings]], { P_AM, P_NOWB }),
            folder("Adaptive: Portrait", [[C:\ProgramData\Adobe\CameraRaw\Settings\Adobe]], { P_MASK }) }
LrApplication.developPresetFolders = function() return FOLDERS end
LrApplication.developPresetByUuid = function(u)
  for _, f in ipairs(FOLDERS) do for _, p in ipairs(f:getDevelopPresets()) do
    if p.uuid == u then return p end end end
  return nil
end
CO_PRESET_PLUGIN = true
LrApplication.addDevelopPresetForPlugin = function(plugin, name, settings)
  if not CO_PRESET_PLUGIN then error("khong ho tro") end
  return { wbPreset = true, settings = settings, name = name }
end
''')
XP = L.eval('require("XemPresetCore")')
g.XP = XP

# ---- 8. JSON
L.execute('''
local t = { a = 1.5, b = "Tỉ lệ \\"x\\"\\n", c = { 0, 0, 255, 255 }, d = { Name = "Adobe Color", Amount = 1 },
            e = true, f = {} }
local s = XP.jMa(t)
local u = XP.jGiai(s)
JSON_OK = (u.a == 1.5 and u.b == t.b and u.c[3] == 255 and #u.c == 4 and u.d.Name == "Adobe Color"
           and u.e == true and XP.jMa(u) == s)
''')
ktra("JSON tu viet: ma -> giai giu nguyen", bool(g.JSON_OK))

# ---- 1. danh sach preset
n = XP.ghiDanhSach(True)
ds = (jobs / "lr_presets.tsv").read_text(encoding="utf-8")
ktra("danh sach preset: 3 preset, du cot", n == 3 and "U1\tcưới trắng hồng 1\tUser Presets\t" in ds
     and "A1\tAdaptive: Blur Background\tAdaptive: Portrait" in ds, repr(ds[:160]))

# ---- 2/3. ap tam -> render -> tra lai
raw = tam / "buoi"
L.execute(r'''
GOC_S = {}
for i = 1, 13 do
  local s = { Exposure2012 = 0.1 * i, Contrast2012 = 5, WhiteBalance = "Custom", Temperature = 5000 + i,
              Tint = 3, Vibrance = 0, CameraProfile = "Adobe Standard",
              ToneCurvePV2012 = { 0, 0, 255, 255 } }
  if i == 7 then s.WhiteBalance = "As Shot" s.Temperature = nil s.Tint = nil end
  local p = moiAnh(string.format([[%s/DSC%%04d.ARW]], i), s)
  GOC_S[p.path] = p:getDevelopSettings()
end
''' % str(raw).replace("\\", "/"))


def yeu_cau(uuid, ten, nhom, paths, ap=0, id_="1"):
    dong = [f"id={id_}", f"uuid={uuid}", f"ten={ten}", f"nhom={nhom}",
            f"dest={str(ra / uuid).replace(chr(92), '/')}", "canh=1600", "chat=80", f"ap={ap}", "---"]
    (jobs / "request_xempreset.txt").write_text("\ufeff" + "\n".join(dong + paths) + "\n",
                                                encoding="utf-8")


def tien_do():
    d = {}
    for dong in (jobs / "xempreset_tiendo.txt").read_text(encoding="utf-8").splitlines():
        if "=" in dong:
            k, v = dong.split("=", 1)
            d[k] = v
    return d


paths = [str(raw / f"DSC{i:04d}.ARW").replace("\\", "/") for i in range(1, 14)]
paths.insert(3, str(raw / "KHONG_CO.ARW").replace("\\", "/"))
XP.GIAY_MOI_LUOT = 10 ** 6
yeu_cau("U1", "cưới trắng hồng 1", "User Presets", paths)
XP.runRequest()
td = tien_do()
ktra("xem tam: xong 13/14, thieu 1, lech 0, trang thai xong",
     td.get("trang_thai") == "xong" and td.get("xong") == "13" and td.get("tong") == "14"
     and td.get("thieu") == "1" and td.get("lech") == "0", str(td))
L.execute('''
TRA_OK, KHAC = true, ""
for _, p in ipairs(PHOTOS) do
  local a, b = XP.jMa(GOC_S[p.path]), XP.jMa(p:getDevelopSettings())
  if a ~= b then TRA_OK = false KHAC = KHAC .. p.path .. ": " .. a .. " -> " .. b .. "\\n" end
end
''')
ktra("tra lai: thong so MOI anh ve dung nhu cu (ca anh As Shot)", bool(g.TRA_OK), str(g.KHAC)[:300])
bang = (jobs / "xempreset_anh.tsv").read_text(encoding="utf-8").splitlines()
ktra("bang src->jpg: 13 dong, jpg co that", len(bang) == 13 and all(
    Path(x.split("\t")[1]).is_file() for x in bang), str(len(bang)))
noi = (ra / "U1" / "DSC0002.jpg").read_text(encoding="utf-8")
ktra("anh render mang thong so PRESET (khong phai thong so goc)",
     "Exposure2012=0.5" in noi and "WB=Custom" in noi and "T=6200" in noi, noi)
ktra("so khoi phuc da xoa sau moi lo", not (jobs / "xempreset_khoiphuc.json").exists())

# khong tao duoc preset WB -> dem lech (anh As Shot)
g.CO_PRESET_PLUGIN = False
L.execute('XP.__presetWB_reset = true')
L.execute('''
-- xoa cache preset WB trong module (upvalue) bang cach nap lai module
package.loaded["XemPresetCore"] = nil
XP = require("XemPresetCore")
''')
XP = g.XP
XP.GIAY_MOI_LUOT = 10 ** 6
yeu_cau("U1", "cưới trắng hồng 1", "User Presets", [paths[7]], id_="2")
XP.runRequest()
td = tien_do()
ktra("khong tao duoc preset tra WB -> anh As Shot bi dem LECH (khong im lang)",
     td.get("lech") == "1" and "TRA LAI LECH" in (jobs / "plugin.log").read_text(encoding="utf-8"),
     str(td))
g.CO_PRESET_PLUGIN = True
L.execute('''
package.loaded["XemPresetCore"] = nil
XP = require("XemPresetCore")
-- sua tay anh As Shot ve dung (cho cac kiem sau)
local p = BYPATH[ [[%s]] ]
p.s.Temperature = nil p.s.Tint = nil p.kelvin_ket = nil p.s.WhiteBalance = "As Shot"
''' % paths[7])
XP = g.XP
XP.GIAY_MOI_LUOT = 10 ** 6

# ---- 4. so khoi phuc
L.execute(r'''
local p = PHOTOS[1]
local goc = p:getDevelopSettings()
p:applyDevelopPreset(P_AM)                           -- dang mang preset TAM (Lightroom tat giua lo)
py_ghi([[%s/xempreset_khoiphuc.json]], XP.jMa({ { path = p.path, goc = goc } }))
''' % str(jobs).replace("\\", "/"))
nkp = XP.khoiPhuc()
L.execute('KP_OK = XP.jMa(PHOTOS[1]:getDevelopSettings()) == XP.jMa(GOC_S[PHOTOS[1].path])')
ktra("khoi phuc theo so: anh ve thong so goc, so da xoa",
     nkp == 1 and bool(g.KP_OK) and not (jobs / "xempreset_khoiphuc.json").exists(), str(nkp))

# ---- 5. preset co mask
yeu_cau("A1", "Adaptive: Blur Background", "Adaptive: Portrait", paths[:2], id_="3")
XP.runRequest()
td = tien_do()
ktra("preset co mask -> tu choi xem tam", td.get("trang_thai") == "loi" and "mask" in td.get("thong_bao", ""),
     str(td))

# ---- 6. ap han
yeu_cau("U2", "NoWBExposure", "User Presets", paths[:2], ap=1, id_="4")
XP.runRequest()
L.execute('''
local p = PHOTOS[1]
AP_OK = (p.s.Exposure2012 == -0.3 and p.s.Contrast2012 == 15)
''')
ktra("ap=1: preset o lai tren anh (khong tra lai), khong de so",
     bool(g.AP_OK) and tien_do().get("ap") == "1" and not (jobs / "xempreset_khoiphuc.json").exists())

# ---- 7. yeu cau moi giua chung + nhuong viec khac
XP.LO = 2
XP.GIAY_MOI_LUOT = -1          # dong ho gia tinh theo giay nguyen
yeu_cau("U2", "NoWBExposure", "User Presets", paths[4:12], id_="5")
XP.runRequest()
td = tien_do()
ktra("lo DAU chi MOT anh (anh dang xem hien ngay), roi tra vong lap (GIAY_MOI_LUOT)",
     td.get("trang_thai") == "dang_chay" and td.get("xong") == "1", str(td))
XP.runRequest()
ktra("lo sau theo co LO (2 anh)", tien_do().get("xong") == "3", str(tien_do()))
yeu_cau("U1", "cưới trắng hồng 1", "User Presets", paths[4:6], id_="6")
XP.GIAY_MOI_LUOT = 10 ** 6
XP.runRequest()
td = tien_do()
log = (jobs / "plugin.log").read_text(encoding="utf-8")
ktra("yeu cau moi thay luot dang do", td.get("id") == "6" and td.get("trang_thai") == "xong"
     and "xempreset: thay" in log, str(td))
yeu_cau("U2", "NoWBExposure", "User Presets", paths[4:12], id_="7")
(jobs / "request_xuatanh.txt").write_text("x", encoding="utf-8")
XP.runRequest()
td = tien_do()
ktra("co viec khac dang cho (xuat anh) -> nhuong sau mot lo",
     td.get("id") == "7" and td.get("xong") == "1" and td.get("trang_thai") == "dang_chay", str(td))
(jobs / "request_xuatanh.txt").unlink()
XP.runRequest()
ktra("het viec khac -> lam tiep toi xong", tien_do().get("trang_thai") == "xong", str(tien_do()))
L.execute('''
TRA2 = true
for i = 5, 13 do local p = PHOTOS[i]
  if XP.jMa(GOC_S[p.path]) ~= XP.jMa(p:getDevelopSettings()) then TRA2 = false end end
''')
ktra("sau nhieu luot xem tam: anh khong ap han van dung thong so goc", bool(g.TRA2))

print()
print("KET QUA:", "DAT HET" if not LOI else f"{len(LOI)} LOI: {LOI}")
sys.exit(1 if LOI else 0)
