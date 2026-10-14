# -*- coding: utf-8 -*-
"""Kiem HocMauCore.lua (hoc mau Lightroom tren RAW that, 14/10) bang Lua 5.1 that
(lupa.lua51) + SDK gia:
  1. yeu cau JSON -> moi bien the: khoa MOI bien the dung toi ve GOC -> "nen" (WB Custom)
     -> doi (cong vao goc) -> dat -> dat_anh; "goc" = dung nguyen trang
  2. chay het: anh dung du (bien the + "sau"), TRA LAI dung nhu cu (ca anh As Shot),
     so khoi phuc da xoa, bo anh co mask / WB Custom khong doc duoc Kelvin, dem anh thieu
  3. so khoi phuc GHI TRUOC lan ghi dau tien
  4. moi luot goi chi lam toi GIAY_MOI_LUOT roi TRA LAI truoc khi nhuong; luot sau lam tiep
  5. viec khac dang cho (job apply_*.tsv) -> tra lai, nhuong
  6. co dung / yeu cau moi / loi ap -> tra lai, ket thuc dung / thay / loi
  7. khoiPhuc() luc nap: tra lai theo so, xoa so
  8. Init.lua nap HocMauCore, khoi phuc TRUOC vong lap, goi runRequest; nhip khai hocmau1
Chay:  python kiem_hoc_mau_lua.py    (can lupa: LUPA_DIR=<thu muc chua goi lupa>)"""
import json
import os
import sys
import tempfile
from pathlib import Path

if os.environ.get("LUPA_DIR"):
    sys.path.insert(0, os.environ["LUPA_DIR"])
try:
    from lupa import lua51  # noqa: E402
except ImportError:
    print("BO QUA: thieu goi lupa — CHUA kiem HocMauCore.lua")
    sys.exit(0)

GOC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "AutoTone.lrplugin"
LOI = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


tam = Path(tempfile.mkdtemp(prefix="kiem_hocmau_"))
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
  LrDate = { currentTime = function() return GIO end },
  LrApplication = {},
}
GIO = 1000
-- ExportSession gia: moi rendition ghi <dest>/<ten>.jpg = JSON thong so luc dung
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
        py_ghi(out, RENDER_TEXT(ph))
        GIO = GIO + DUNG_GIAY
        return true, out
      end
      return i, r
    end
  end
  return s
end
DUNG_GIAY = 1
function import(name) return fake[name] or {} end
package.path = [[%s/?.lua;]] .. package.path
''' % (str(tam).replace("\\", "/"), str(GOC).replace("\\", "/")))

# ---- catalog gia (cung bay WB As Shot nhu kiem_xem_preset_lua)
L.execute(r'''
local LrApplication = import("LrApplication")
local function sao(t) local o = {} for k, v in pairs(t) do
  if type(v) == "table" then o[k] = sao(v) else o[k] = v end end return o end
SAO = sao
PHOTOS, BYPATH = {}, {}
AP_LOG = {}
function moiAnh(path, s)
  local ph = { path = path, s = sao(s), lich_su = 0 }
  function ph:getDevelopSettings()
    local t = sao(self.s)
    if t.WhiteBalance == "As Shot" and not self.kelvin_ket then t.Temperature = nil t.Tint = nil end
    if t.WhiteBalance == "Custom" and self.an_kelvin then
      t.IncrementalTemperature = t.Temperature t.Temperature = nil t.Tint = nil end
    return t
  end
  function ph:getRawMetadata(k) if k == "fileFormat" then return "RAW" end end
  function ph:applyDevelopSettings(s)
    if LOI_AP then error("ap hong") end
    AP_LOG[#AP_LOG + 1] = { path = self.path, so = py_exists(SO_KP_PATH) }
    for k, v in pairs(s) do self.s[k] = sao({ v })[1] end
    if s.WhiteBalance == "As Shot" and self.s.Temperature ~= nil then self.kelvin_ket = true end
    self.lich_su = self.lich_su + 1
  end
  function ph:applyDevelopPreset(p, plugin)
    if p.wbPreset then
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
LrApplication.addDevelopPresetForPlugin = function(plugin, name, settings)
  return { wbPreset = true, settings = settings, name = name }
end
''')
HM = L.eval('require("HocMauCore")')
XP = L.eval('require("XemPresetCore")')
g.HM, g.XP = HM, XP
g.SO_KP_PATH = str(jobs / "hocmau_khoiphuc.json").replace("\\", "/")
L.execute(r'''
function RENDER_TEXT(ph)
  local t = ph:getDevelopSettings()
  return XP.jMa({ Exposure2012 = t.Exposure2012, WhiteBalance = t.WhiteBalance,
                  Temperature = ph.s.Temperature, Tint = ph.s.Tint,
                  HueAdjustmentOrange = t.HueAdjustmentOrange,
                  ToneCurvePV2012Red = t.ToneCurvePV2012Red, ToneCurveName2012 = t.ToneCurveName2012 })
end
''')
#  Core.jobDir() -> thư mục jobs giả
L.execute('local Core = require("AutoToneCore"); Core.jobDir = function() return [[%s]] end'
          % str(jobs).replace("\\", "/"))

raw = str(tam / "buoi").replace("\\", "/")
L.execute(r'''
GOC_S = {}
local function them(ten, s, kieu)
  local p = moiAnh([[%s/]] .. ten, s)
  if kieu == "an_kelvin" then p.an_kelvin = true end
  GOC_S[p.path] = p:getDevelopSettings()
  return p
end
local function co_ban(i)
  return { Exposure2012 = 0.1 * i, Highlights2012 = -10, WhiteBalance = "Custom",
           Temperature = 5000 + 10 * i, Tint = 2 + i, HueAdjustmentOrange = 0,
           ToneCurveName2012 = "Medium Contrast", ToneCurvePV2012Red = { 0, 0, 255, 255 },
           CameraProfile = "Adobe Standard" }
end
for i = 1, 5 do them(string.format("DSC%%04d.ARW", i), co_ban(i)) end
local as = co_ban(6) as.WhiteBalance = "As Shot" as.Temperature = nil as.Tint = nil
them("DSC0006.ARW", as)                                    -- As Shot
local mk = co_ban(7) mk.MaskGroupBasedCorrections = { { What = "Mask" } }
them("DSC0007.ARW", mk)                                    -- có mask -> bỏ
them("DSC0008.ARW", co_ban(8), "an_kelvin")                -- Custom không có Kelvin -> bỏ
''' % raw)


def path(i):
    return f"{raw}/DSC{i:04d}.ARW"


def yeu_cau(id_="1", n=8, them_khong_co=True):
    anh = []
    for i in range(1, n + 1):
        nen = {"WhiteBalance": "Custom", "Temperature": 5000 + 10 * i if i != 6 else 5500,
               "Tint": 2 + i if i != 6 else 4}
        anh.append({"path": path(i), "nen": nen})
    if them_khong_co:
        anh.insert(2, {"path": f"{raw}/KHONG_CO.ARW", "nen": {}})
    bien = [{"ten": "goc", "goc": True}, {"ten": "nen"},
            {"ten": "ev+", "doi": {"Exposure2012": 0.7}},
            {"ten": "o_hue+", "doi": {"HueAdjustmentOrange": 30}},
            {"ten": "k+", "dat_anh": {a["path"]: {"Temperature": (a["nen"].get("Temperature") or 0) + 400}
                                      for a in anh}},
            {"ten": "cv_r", "dat": {"ToneCurveName2012": "Custom"},
             "dat_anh": {a["path"]: {"ToneCurvePV2012Red": [0, 0, 128, 140, 255, 255]} for a in anh}}]
    req = {"id": id_, "dest": str(ra / id_).replace("\\", "/"), "canh": 1024, "chat": 90,
           "anh": anh, "bien": bien}
    (jobs / "request_hocmau.txt").write_text(json.dumps(req, ensure_ascii=False), encoding="utf-8")
    return req


def tien_do():
    d = {}
    for dong in (jobs / "hocmau_tiendo.txt").read_text(encoding="utf-8").splitlines():
        if "=" in dong:
            k, v = dong.split("=", 1)
            d[k] = v
    return d


def tra_dung():
    L.execute('''
TRA_OK, KHAC = true, ""
for _, p in ipairs(PHOTOS) do
  local a, b = XP.jMa(GOC_S[p.path]), XP.jMa(p:getDevelopSettings())
  if a ~= b then TRA_OK = false KHAC = KHAC .. p.path .. ": " .. a .. " -> " .. b .. "\\n" end
end
''')
    return bool(g.TRA_OK), str(g.KHAC)[:400]


def doc_jpg(id_, ten, i):
    return json.loads((ra / id_ / ten / f"DSC{i:04d}.jpg").read_text(encoding="utf-8"))


# ---- 1-3. chạy hết trong một lượt
print("1-3. mot luot chay het")
HM.GIAY_MOI_LUOT = 10 ** 6
yeu_cau("1")
HM.runRequest()
td = tien_do()
ktra("xong: 6 anh dung (bo 2, thieu 1), 6 x 7 = 42 lan dung, lech 0",
     td.get("trang_thai") == "xong" and td.get("xong") == "42" and td.get("anh_xong") == "6"
     and td.get("bo") == "2" and td.get("thieu") == "1" and td.get("lech") == "0", str(td))
ok, khac = tra_dung()
ktra("TRA LAI: thong so MOI anh ve dung nhu cu (ca As Shot)", ok, khac)
ktra("so khoi phuc da xoa", not (jobs / "hocmau_khoiphuc.json").exists())
j_goc, j_nen = doc_jpg("1", "goc", 6), doc_jpg("1", "nen", 6)
ktra("'goc' = nguyen trang (As Shot), 'nen' = WB Custom o Kelvin app gui",
     j_goc.get("WhiteBalance") == "As Shot" and j_nen.get("WhiteBalance") == "Custom"
     and j_nen.get("Temperature") == 5500, f"{j_goc} | {j_nen}")
j_ev, j_k = doc_jpg("1", "ev+", 2), doc_jpg("1", "k+", 2)
ktra("'ev+': Exposure = goc + 0.7, WB = nen", abs(j_ev["Exposure2012"] - 0.9) < 1e-9
     and j_ev["Temperature"] == 5020, str(j_ev))
ktra("'k+': Exposure VE GOC (khoa bien the truoc da dua ve goc), K = nen + 400",
     abs(j_k["Exposure2012"] - 0.2) < 1e-9 and j_k["Temperature"] == 5420
     and j_k.get("HueAdjustmentOrange") == 0, str(j_k))
j_cv = doc_jpg("1", "cv_r", 2)
ktra("'cv_r': curve do dat_anh + ten Custom; HSL ve goc",
     j_cv.get("ToneCurvePV2012Red") == [0, 0, 128, 140, 255, 255]
     and j_cv.get("ToneCurveName2012") == "Custom" and j_cv.get("HueAdjustmentOrange") == 0, str(j_cv))
j_sau = doc_jpg("1", "sau", 6)
ktra("'sau' (dung SAU khi tra lai) == 'goc'", j_sau == j_goc, f"{j_sau} | {j_goc}")
ktra("anh co mask / WB Custom khong Kelvin: KHONG dung, KHONG ghi gi",
     not (ra / "1" / "ev+" / "DSC0007.jpg").exists() and not (ra / "1" / "ev+" / "DSC0008.jpg").exists()
     and L.eval('BYPATH[ [[%s]] ].lich_su' % path(7)) == 0 and L.eval('BYPATH[ [[%s]] ].lich_su' % path(8)) == 0)
bang = (jobs / "hocmau_anh.tsv").read_text(encoding="utf-8").splitlines()
ktra("bang: tieu de + 42 dong bien\\tanh\\tjpg", bang[0] == "bien\tpath\tjpg" and len(bang) == 43, str(len(bang)))
ktra("so khoi phuc CO TRUOC moi lan ghi bien the", all(x["so"] for x in L.eval("AP_LOG").values()),
     str(sum(1 for x in L.eval("AP_LOG").values() if not x["so"])))

# ---- 4. mỗi lượt gọi ngắn: trả lại trước khi nhường
print("4. luot ngan: tra lai truoc khi nhuong")
HM.GIAY_MOI_LUOT = 0                      # mỗi lượt đúng một biến thể
yeu_cau("2", them_khong_co=False)
so_luot, sach_moi_luot = 0, True
while True:
    HM.runRequest()
    so_luot += 1
    ok, _ = tra_dung()
    sach_moi_luot &= ok and not (jobs / "hocmau_khoiphuc.json").exists()
    if tien_do().get("trang_thai") != "dang_chay" or so_luot > 100:
        break
td = tien_do()
ktra("nhieu luot (moi luot mot bien the) -> van xong du 42 lan dung",
     td.get("trang_thai") == "xong" and td.get("xong") == "42" and so_luot > 6, f"{so_luot} luot · {td}")
ktra("SAU MOI LUOT: anh ve goc, khong con so khoi phuc", sach_moi_luot)
ktra("ket qua giong lan chay mot luot", doc_jpg("2", "k+", 2) == doc_jpg("1", "k+", 2))

# ---- 5. việc khác đang chờ
print("5. viec khac dang cho -> nhuong")
HM.GIAY_MOI_LUOT = 10 ** 6
yeu_cau("3", them_khong_co=False)
(jobs / "apply_20261014_120000_Buoi.tsv").write_text("path\n", encoding="utf-8")
HM.runRequest()
td = tien_do()
ok, _ = tra_dung()
ktra("job apply_*.tsv dang cho: dung sau MOT bien the, anh da tra lai",
     td.get("trang_thai") == "dang_chay" and td.get("xong") == "4" and ok
     and not (jobs / "hocmau_khoiphuc.json").exists(), str(td))
(jobs / "apply_20261014_120000_Buoi.tsv").unlink()
HM.runRequest()
ktra("het viec khac -> lam tiep toi xong", tien_do().get("trang_thai") == "xong", str(tien_do()))

# ---- 6. dừng / yêu cầu mới / lỗi áp
print("6. dung / yeu cau moi / loi ap")
HM.GIAY_MOI_LUOT = 0
yeu_cau("4", them_khong_co=False)
HM.runRequest()
(jobs / "request_hocmau_dung.txt").write_text("dung\n", encoding="utf-8")
HM.runRequest()
ok, _ = tra_dung()
ktra("co dung -> 'dung', anh ve goc", tien_do().get("trang_thai") == "dung" and ok and HM.dang is None)
yeu_cau("5", them_khong_co=False)
HM.runRequest()
yeu_cau("6", them_khong_co=False)
HM.runRequest()
ok, _ = tra_dung()
ktra("yeu cau moi giua chung -> luot moi (id 6), anh ve goc",
     tien_do().get("id") == "6" and ok, str(tien_do()))
HM.GIAY_MOI_LUOT = 10 ** 6
g.LOI_AP = True
HM.runRequest()
g.LOI_AP = False
ok, khac = tra_dung()
ktra("ap bien the hong -> 'loi', anh ve goc", tien_do().get("trang_thai") == "loi" and ok, khac)

# ---- 7. khoiPhuc lúc nạp
print("7. khoi phuc luc nap")
L.execute('''
local p = BYPATH[ [[%s]] ]
local goc = p:getDevelopSettings()
XP_SO = { { path = p.path, goc = goc } }
p:applyDevelopSettings({ Exposure2012 = 3.3, HueAdjustmentOrange = 40 })
''' % path(2))
(jobs / "hocmau_khoiphuc.json").write_text(L.eval("XP.jMa(XP_SO)"), encoding="utf-8")
n = HM.khoiPhuc()
ok, khac = tra_dung()
ktra("so con lai (Lightroom tat giua luot) -> khoiPhuc tra lai 1 anh, xoa so",
     n == 1 and ok and not (jobs / "hocmau_khoiphuc.json").exists(), khac)
ktra("khoiPhuc cua xem preset KHONG dung so hoc mau (ten so rieng)",
     XP.SO_KP != "hocmau_khoiphuc.json")

# ---- 8. Init.lua + nhịp
print("8. Init.lua / nhip")
init = (GOC / "Init.lua").read_text(encoding="utf-8")
i_kp, i_vong = init.find("HocMau.khoiPhuc"), init.find("while true do")
ktra("Init.lua nap HocMauCore, khoi phuc TRUOC vong lap, goi HocMau.runRequest",
     'require, "HocMauCore"' in init and 0 < i_kp < i_vong and "HocMau.runRequest" in init)
core = (GOC / "AutoToneCore.lua").read_text(encoding="utf-8")
ktra("nhip plugin khai hocmau1", "hocmau1" in core.split("M.KHA_NANG =")[1].splitlines()[0])
hm = (GOC / "HocMauCore.lua").read_text(encoding="utf-8")
ktra("HocMauCore khong pcall quanh loi goi SDK (chi pcall require / jGiai)",
     all(("require" in d or "jGiai" in d) for d in hm.splitlines() if "pcall(" in d and not d.strip().startswith("--")))

print(f"\n{len(LOI)} LOI" if LOI else "\nTAT CA DAT")
sys.exit(1 if LOI else 0)
