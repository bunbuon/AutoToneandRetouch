# -*- coding: utf-8 -*-
"""Kiểm phần CURVE ĐIỂM của plugin (13/10) bằng Lua 5.1 thật (lupa.lua51) + SDK giả.

User 13/10: lượt 2 "Xử lý ảnh" ghi curve kênh R/G/B (da) + nén đỉnh curve tổng (cháy).
Plugin phải: đọc ô curve "x1,y1,…" thành bảng (ô hỏng thì BỎ, không ghi nhầm), so curve
khi kiểm chứng (sameNumber trên bảng luôn "khác" -> báo chưa nhận mãi), đặt tên "Custom",
xuất curve GỐC ra bản xuất (app ghép vào đó), khai kha_nang=curve1 trong nhịp, coi job
"@curve" cùng buổi với job WB / Tone, và dựng ĐÚNG danh sách ảnh (dòng anh=) cho lượt 2
vào bộ file riêng — không giẫm Duyệt nhanh.

Mục kiểm
    1. docCurve: hợp lệ -> bảng; số lẻ / ngoài 0..255 / x không tăng -> nil
    2. readJob: ô curve -> bảng, ô hỏng bị bỏ (cột khác giữ), ToneCurveName2012 là chữ
    3. applyJob: ghi curve + tên "Custom"; kiểm chứng sạch; chạy lại = bỏ qua (không ghi)
    4. exportCell / EXPORT_FIELDS: bảng -> ô, cột cũ giữ nguyên vị trí, curve ở CUỐI
    5. recoverStale: job @curve bỏ dở mà buổi đã có job WB / Tone mới hơn -> .huy
    6. ghiNhip: kha_nang=curve1 — at.plugin_kha_nang đọc ra
    7. DuyetCore lượt 2: chỉ dựng ảnh trong anh=, bỏ 1★, ghi do_curve_*; Duyệt nhanh không đụng

Chạy:  python kiem_curve_lua.py
"""
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
    print("BO QUA: thieu goi lupa (pip install lupa) — CHUA kiem plugin Lua")
    sys.exit(0)

GOC = Path(__file__).resolve().parent / "AutoTone.lrplugin"
sys.path.insert(0, str(GOC.parent))
LOI = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


tam = Path(tempfile.mkdtemp(prefix="kiem_curve_lua_"))
jobs = tam / "jobs"
jobs.mkdir()
L = lua51.LuaRuntime(unpack_returned_tuples=True)
g = L.globals()


def files(d):
    ds = [str(Path(d) / x) for x in sorted(os.listdir(d))]
    it = iter(ds)
    return lambda *_: next(it, None)


g.py_files = files
g.py_move = lambda a, b: os.replace(a, b) or True
g.py_exists = lambda p: os.path.exists(p)
g.py_delete = lambda p: (os.remove(p) if os.path.isfile(p) else None) or True
g.py_mkdirs = lambda p: os.makedirs(p, exist_ok=True) or True
g.py_ghi = lambda p, s: Path(p).write_text(s, encoding="utf-8") and True
L.execute(r'''
_PLUGIN = { path = [[%s]] }
local fake = {
  LrFileUtils = { files = function(d) return py_files(d) end, move = function(a, b) return py_move(a, b) end,
                  exists = function(p) return py_exists(p) end, delete = function(p) return py_delete(p) end,
                  createAllDirectories = function(p) return py_mkdirs(p) end },
  LrPathUtils = { child = function(a, b) return a .. "/" .. b end,
                  leafName = function(p) return string.match(p, "[^/\\]+$") end,
                  removeExtension = function(p) return (string.gsub(p, "%%.[^.]*$", "")) end },
  LrFunctionContext = { pcallWithContext = function(tag, fn) return pcall(fn) end },
  LrTasks = { yield = function() end, sleep = function() end },
  LrDate = { currentTime = function() return os.time() end },
  LrApplication = {},
  LrExportSession = function(t)
    local s = { t = t }
    function s:doExportOnCurrentTask()
      for _, ph in ipairs(self.t.photosToExport) do
        local p = ph:getRawMetadata("path")
        local ten = string.gsub(string.match(p, "[^/\\]+$"), "%%.[^.]*$", "")
        py_ghi(self.t.exportSettings.LR_export_destinationPathPrefix .. "/" .. ten .. ".jpg", "x")
      end
    end
    function s:renditions() return function() return nil end end
    return s
  end,
}
function import(name) return fake[name] or {} end
package.path = [[%s/?.lua;]] .. package.path
''' % (str(tam).replace("\\", "/"), str(GOC).replace("\\", "/")))
Core = L.eval('require("AutoToneCore")')

# ---- 1. docCurve
t = Core.docCurve("0,0,64,60,138,132,255,255")
ktra("docCurve hợp lệ -> bảng 8 số", t is not None and len(t) == 8 and t[3] == 64 and t[8] == 255)
for o, ly in (("0,0,64", "số lẻ"), ("0,0,300,255", "> 255"), ("0,0,64,60,64,70,255,255", "x trùng"),
              ("0,0,128,a,255,255", "chữ"), ("", "trống"), ("0,0", "< 2 điểm")):
    ktra(f"docCurve hỏng ({ly}) -> nil", Core.docCurve(o) is None)

# ---- 2. readJob
cot = ["Exposure2012", "ToneCurveName2012", "ToneCurvePV2012", "ToneCurvePV2012Red",
       "ToneCurvePV2012Green", "ToneCurvePV2012Blue"]
f = jobs / "apply_20261013_100000_Buoi@curve.tsv"
f.write_text("path\t" + "\t".join(cot) + "\n"
             + "G:/B/A.ARW\t0.5\tCustom\t0,0,128,120,255,245\t0,0,140,132,255,255\t\t0,0,300\n",
             encoding="utf-8")
rows = Core.readJob(str(f))
s = rows[1]["settings"]
ktra("readJob: Exposure vẫn là số", s["Exposure2012"] == 0.5)
ktra("readJob: tên curve là CHỮ", s["ToneCurveName2012"] == "Custom")
ktra("readJob: curve tổng -> bảng 6 số", s["ToneCurvePV2012"] is not None and len(s["ToneCurvePV2012"]) == 6)
ktra("readJob: curve Red -> bảng", s["ToneCurvePV2012Red"] is not None and s["ToneCurvePV2012Red"][4] == 132)
ktra("readJob: ô trống (Green) không đụng", s["ToneCurvePV2012Green"] is None)
ktra("readJob: ô hỏng (Blue) bị BỎ, không ghi nhầm", s["ToneCurvePV2012Blue"] is None)

# ---- 3. applyJob với ảnh giả
L.execute('''
CURVE_PHOTO = { s = { Exposure2012 = 0, ToneCurveName2012 = "Linear",
                      ToneCurvePV2012 = { 0, 0, 255, 255 }, ToneCurvePV2012Red = { 0, 0, 255, 255 } },
                ghi = 0 }
function CURVE_PHOTO:getDevelopSettings()
  local t = {}
  for k, v in pairs(self.s) do
    if type(v) == "table" then local c = {} for i = 1, #v do c[i] = v[i] end t[k] = c else t[k] = v end
  end
  return t
end
function CURVE_PHOTO:applyDevelopSettings(s) self.ghi = self.ghi + 1 for k, v in pairs(s) do self.s[k] = v end end
function CURVE_PHOTO:getRawMetadata() return 0 end
function CURVE_PHOTO:setRawMetadata() end
local cat = { findPhotoByPath = function(self, p) return CURVE_PHOTO end,
              withWriteAccessDo = function(self, n, fn) fn() end,
              withReadAccessDo = function(self, fn) fn() end }
local LrApplication = import("LrApplication")
LrApplication.activeCatalog = function() return cat end
''')
ph = g.CURVE_PHOTO
job = L.eval('{ { path = "G:/B/A.ARW", settings = { ToneCurvePV2012 = { 0, 0, 128, 120, 255, 245 }, '
             'ToneCurvePV2012Red = { 0, 0, 140, 132, 255, 255 } } } }')
res = Core.applyJob(job, "apply_20261013_100001_Buoi@curve.tsv")
ktra("applyJob: ghi 1 ảnh", res["applied"] == 1, str(res["applied"]))
ktra("applyJob: curve tổng đã vào ảnh", list(ph.s.ToneCurvePV2012.values()) == [0, 0, 128, 120, 255, 245])
ktra("applyJob: tên curve đặt 'Custom' khi job không gửi tên", ph.s.ToneCurveName2012 == "Custom")
kc = list((res["bad"] or L.table()).values()) if res["bad"] is not None else []
ktra("applyJob: kiểm chứng sạch (không 'chua-nhan' curve)", len(kc) == 0, str(kc))
res2 = Core.applyJob(job, "apply_20261013_100002_Buoi@curve.tsv")
ktra("chạy lại cùng curve: BỎ QUA, không ghi thêm", res2["applied"] == 0 and ph.ghi == 1,
     f"applied={res2['applied']} ghi={ph.ghi}")
job3 = L.eval('{ { path = "G:/B/A.ARW", settings = { ToneCurvePV2012 = { 0, 0, 128, 121, 255, 245 } } } }')
res3 = Core.applyJob(job3, "apply_20261013_100003_Buoi@curve.tsv")
ktra("curve khác 1 mã: GHI lại", res3["applied"] == 1 and ph.ghi == 2)

# ---- 4. exportCell / EXPORT_FIELDS
ktra("exportCell curve: bảng -> '0,0,128,120,255,245'",
     Core.exportCell("ToneCurvePV2012", L.eval("{0,0,128,120,255,245}")) == "0,0,128,120,255,245")
ktra("exportCell tên curve: chữ", Core.exportCell("ToneCurveName2012", "Medium Contrast") == "Medium Contrast")
ktra("exportCell curve không phải bảng -> ô trống", Core.exportCell("ToneCurvePV2012Red", None) == "")
ef = list(Core.EXPORT_FIELDS.values())
CU = ["Exposure2012", "Highlights2012", "Shadows2012", "Temperature", "Tint", "AsShotTemperature",
      "AsShotTint", "WhiteBalance", "Contrast2012", "Whites2012", "Blacks2012", "ConvertToGrayscale"]
ktra("EXPORT_FIELDS: cột cũ giữ nguyên vị trí", ef[:len(CU)] == CU, str(ef[:len(CU)]))
#  14/10: crop + hồ sơ màu + PV thêm vào CUỐI, sau năm cột curve (13/10)
MOI_1410 = ["CropLeft", "CropTop", "CropRight", "CropBottom", "CropAngle", "CameraProfile",
            "ProcessVersion"]
ktra("EXPORT_FIELDS: năm cột curve ngay trước các cột 14/10",
     ef[-12:-7] == ["ToneCurveName2012", "ToneCurvePV2012", "ToneCurvePV2012Red",
                    "ToneCurvePV2012Green", "ToneCurvePV2012Blue"], str(ef[-12:-7]))
ktra("EXPORT_FIELDS: crop / CameraProfile / ProcessVersion ở CUỐI", ef[-7:] == MOI_1410,
     str(ef[-7:]))
ktra("exportCell CameraProfile: chữ (tab -> dấu cách)",
     Core.exportCell("CameraProfile", "Adobe\tStandard") == "Adobe Standard")
ktra("exportCell CropLeft: số", Core.exportCell("CropLeft", 0.125) == "0.125")
import autotone as at  # noqa: E402
ktra("EXPORT_FIELDS (Lua) chứa đủ COT_CURVE của app", all(k in ef for k in at.COT_CURVE))

# ---- 5. recoverStale: @curve cũ + job WB / Tone mới hơn cùng buổi
for p in jobs.iterdir():
    p.unlink()
(jobs / "apply_20261013_101000_Buoi@curve.tsv.tableX-1-1.running").write_text("path\n", encoding="utf-8")
(jobs / "apply_20261013_102000_Buoi.done").write_text("path\n", encoding="utf-8")
(jobs / "apply_20261013_101500_Khac@curve.tsv.tableY-1-2.running").write_text("path\n", encoding="utf-8")
Core.recoverStale()
co = set(os.listdir(jobs))
ktra("job @curve bỏ dở, buổi đã có job WB / Tone mới hơn -> .huy",
     "apply_20261013_101000_Buoi@curve.huy" in co, str(sorted(co)))
ktra("job @curve của buổi khác (không có job mới hơn) -> trả về .tsv",
     "apply_20261013_101500_Khac@curve.tsv" in co)

# ---- 6. nhịp khai khả năng
Core.ghiNhip(7, 0)
ktra("ghiNhip: kha_nang=curve1", "kha_nang=curve1" in (jobs / "plugin_song.txt").read_text(encoding="utf-8"))
ktra("at.plugin_kha_nang đọc ra 'curve1'", "curve1" in at.plugin_kha_nang(jobs))

# ---- 7. DuyetCore lượt 2
anh_dir = tam / "Buoi"
anh_dir.mkdir()
dest = tam / "do_curve" / "Buoi" / "m1"
L.execute('''
local sao = { A1 = 0, A2 = 1, A3 = 0, A4 = 0, A5 = 3 }
local ds = {}
for _, ten in ipairs({ "A1", "A2", "A3", "A4", "A5" }) do
  ds[#ds + 1] = { getRawMetadata = function(self, k)
                     if k == "rating" then return sao[ten] end
                     return "%s/" .. ten .. ".ARW" end }
end
local cat = { getFolderByPath = function(self, p) return { getPhotos = function() return ds end } end,
              withReadAccessDo = function(self, fn) fn() end,
              withWriteAccessDo = function(self, n, fn) fn() end,
              findPhotoByPath = function() return nil end }
local LrApplication = import("LrApplication")
LrApplication.activeCatalog = function() return cat end
''' % str(anh_dir).replace("\\", "/"))
Dc = L.eval('require("DuyetCore")')
(jobs / "duyet_tiendo.txt").write_text("trang_thai=xong\nxong=9\n", encoding="utf-8")
import curve_da as cdm  # noqa: E402
items = [{"path": str(anh_dir / f"{t}.ARW").replace("\\", "/")} for t in ("A1", "A2", "a3")]
cdm.yeu_cau_dung(anh_dir, items, dest, "m1", job_dir=jobs)
n = Dc.runRequestCurve()
td = cdm.tien_do(jobs)
bang = cdm.bang_anh(jobs)
ten_ra = sorted(Path(j).name for _, j in bang)
ktra("lượt 2: chỉ dựng ảnh trong anh= và bỏ 1★ (A2) -> A1, A3", ten_ra == ["A1.jpg", "A3.jpg"], str(ten_ra))
ktra("lượt 2: tiến độ do_curve_tiendo.txt xong 2/2, mang mã lượt",
     td.get("trang_thai") == "xong" and td.get("xong") == 2 and td.get("ma") == "m1", str(td))
ktra("lượt 2: yêu cầu đã được nhận (file yêu cầu không còn)", not cdm.dang_cho(jobs))
ktra("Duyệt nhanh không bị đụng (duyet_tiendo.txt nguyên, không duyet_anh.tsv)",
     (jobs / "duyet_tiendo.txt").read_text(encoding="utf-8").startswith("trang_thai=xong\nxong=9")
     and not (jobs / "duyet_anh.tsv").exists())
ktra("ảnh dựng nằm trong thư mục lượt 2, không trong _duyet",
     (dest / "A1.jpg").exists() and not (anh_dir / "_duyet").exists())
src_init = (GOC / "Init.lua").read_text(encoding="utf-8")
import re  # noqa: E402
ktra("Init.lua gọi Duyet.runRequestCurve trong vòng lặp (không bị chặn)",
     re.search(r'if type\(Duyet\.runRequestCurve\) == "function" then\s*\n\s*local _, errCv = '
               r'Core\.try\("autoDoCurve", Duyet\.runRequestCurve\)', src_init) is not None
     and "if Duyet then" in src_init[:src_init.find("Duyet.runRequestCurve")][-2000:])

# ---- 8. 14/10: lượt 2 lấy PREVIEW (requestJpegThumbnail) thay Export
#  SDK giả đúng tính chất thật: callback chạy SAU (khi task nhường — LrTasks.sleep), và
#  yêu cầu bị HUỶ nếu đối tượng requestJpegThumbnail trả về đã bị dọn rác (lỗi 6/9:
#  warmPreviews không giữ đối tượng -> "callback không bao giờ nổ").
anh2 = tam / "Buoi2"
anh2.mkdir()
L.execute('''
PV = { hang = {}, song = setmetatable({}, { __mode = "k" }), xuat = 0, xin = 0, kieu = {} }
local T = import("LrTasks")
T.sleep = function()
  collectgarbage("collect")
  local h = PV.hang
  PV.hang = {}
  for _, r in ipairs(h) do
    --  hàng đợi chỉ giữ đối tượng YẾU (như SDK): plugin không giữ thì nó bị dọn -> huỷ
    if r.ref.h ~= nil then r.cb(r.du_lieu) else PV.huy = (PV.huy or 0) + 1 end
  end
end
local ds2 = {}
for _, ten in ipairs({ "P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10" }) do
  local ph = { getRawMetadata = function(self, k)
                 if k == "rating" then return 0 end
                 return "%s/" .. ten .. ".ARW" end }
  function ph:requestJpegThumbnail(w, h, cb)
    PV.xin = PV.xin + 1
    local handle = { ten = ten }
    PV.song[handle] = true
    local kieu = PV.kieu[ten]
    local du_lieu = "JPEG-" .. ten
    if kieu == "rong" then du_lieu = nil end      -- (cond and nil or x) luôn ra x trong Lua
    PV.hang[#PV.hang + 1] = { ref = setmetatable({ h = handle }, { __mode = "v" }), cb = cb,
                              du_lieu = du_lieu }
    return handle
  end
  ds2[#ds2 + 1] = ph
end
PV.ds = ds2
local cat2 = { getFolderByPath = function(self, p) return { getPhotos = function() return ds2 end } end,
               withReadAccessDo = function(self, fn) fn() end,
               withWriteAccessDo = function(self, n, fn) fn() end,
               findPhotoByPath = function() return nil end }
local LrApplication = import("LrApplication")
LrApplication.activeCatalog = function() return cat2 end
local XS = import("LrExportSession")
''' % str(anh2).replace("\\", "/"))
L.execute("require('DuyetCore').CHO_PREVIEW = 2")
dest2 = tam / "do_curve" / "Buoi2" / "m2"
items2 = [{"path": str(anh2 / f"P{i}.ARW").replace("\\", "/")} for i in range(1, 11)]
kiem2 = [items2[3]["path"], items2[8]["path"]]                 # P4, P9 (ở nhóm 1 và 2)
L.execute("PV.kieu.P7 = 'rong'")                                  # P7: Lightroom trả rỗng
cdm.yeu_cau_dung(anh2, items2, dest2, "m2", job_dir=jobs, nguon="preview", kiem=kiem2)
Dc.runRequestCurve()
PVg = L.globals().PV
td2 = cdm.tien_do(jobs)
bang2 = dict((Path(a).name, Path(b)) for a, b in cdm.bang_anh(jobs))
kiem_bang = cdm.bang_anh(jobs, ten=cdm.TEN_KIEM)
ktra("preview: xin 10 ảnh, KHÔNG yêu cầu nào bị huỷ vì dọn rác (giữ đối tượng)",
     PVg.xin == 10 and not PVg.huy, f"xin={PVg.xin} huy={PVg.huy}")
ktra("preview: 9 ảnh ghi từ byte preview, P7 (preview rỗng) XUẤT BÙ",
     len(bang2) == 10 and (dest2 / "P1.jpg").read_bytes() == b"JPEG-P1"
     and (dest2 / "P7.jpg").read_bytes() == b"x", str(sorted(bang2)))
ktra("preview: tiến độ xong 10/10, cach=preview, mang mã lượt",
     td2.get("trang_thai") == "xong" and td2.get("xong") == 10 and td2.get("cach") == "preview"
     and td2.get("ma") == "m2", str(td2))
ktra("preview: ảnh soát P4, P9 XUẤT THẬT vào _kiem + bảng do_curve_kiem.tsv",
     sorted(Path(a).name for a, _b in kiem_bang) == ["P4.ARW", "P9.ARW"]
     and all("_kiem" in b and Path(b).exists() for _a, b in kiem_bang), str(kiem_bang))
#  Lightroom không trả preview nào ở nhóm đầu -> xuất cả lượt như cũ
L.execute("for _, t in ipairs({'P1','P2','P3','P4','P5','P6','P7','P8','P9','P10'}) do PV.kieu[t] = 'rong' end")
dest3 = tam / "do_curve" / "Buoi2" / "m3"
cdm.yeu_cau_dung(anh2, items2, dest3, "m3", job_dir=jobs, nguon="preview", kiem=kiem2)
Dc.runRequestCurve()
td3 = cdm.tien_do(jobs)
ktra("preview không có ở nhóm đầu -> XUẤT cả lượt (cach=export), đủ 10 ảnh",
     td3.get("cach") == "export" and td3.get("xong") == 10
     and (dest3 / "P1.jpg").read_bytes() == b"x", str(td3))
src_dc = (GOC / "DuyetCore.lua").read_text(encoding="utf-8")
ktra("DuyetCore giữ đối tượng requestJpegThumbnail (giu[i] = h)", "giu[i] = h" in src_dc)

shutil.rmtree(tam, ignore_errors=True)
print(f"\n{len(LOI)} LOI" if LOI else "\nTAT CA DAT")
sys.exit(1 if LOI else 0)
