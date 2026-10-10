# -*- coding: utf-8 -*-
"""Kiểm hành động Post-Process "AutoTone: Retouch khi xuất" (RetouchKhiXuat.lua, 10/10)
bằng Lua 5.1 thật (lupa) + SDK Lightroom giả + TRẠM PYTHON THẬT (tram_retouch.Tram, engine
giả) — kiểm cả giao thức hai bên, không chỉ từng bên.

    LUPA_DIR=<thư mục lupa> python kiem_retouch_khi_xuat_lua.py
Không có lupa thì BỎ QUA (in rõ)."""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

if os.environ.get("LUPA_DIR"):
    sys.path.insert(0, os.environ["LUPA_DIR"])
try:
    from lupa import lua51  # noqa: E402
except ImportError:
    print("BO QUA: thieu goi lupa — CHUA kiem RetouchKhiXuat.lua")
    sys.exit(0)

TAM = Path(tempfile.mkdtemp(prefix="kiem_rtxuat_"))
os.environ["AUTOTONE_DATA"] = str(TAM / "data")
GOC = Path(__file__).resolve().parent
PLUGIN = GOC / "AutoTone.lrplugin"
sys.path.insert(0, str(GOC))

import retouch as rt  # noqa: E402
import retouch_preset as rp  # noqa: E402
import tram_retouch as tr  # noqa: E402

LOI = []


def ktra(ten, dieu, mo=""):
    print(f"  [{'DAT ' if dieu else 'LOI '}] {ten}  {mo}")
    if not dieu:
        LOI.append(ten)


# ------------------------------------------------------------ trạm Python thật, engine giả
class MayGia:
    co_chay = True
    tin_san_sang = {"may": "cuda"}
    dang_chay = False
    proc = None

    def song(self):
        return True

    def chay_duoc(self, cho=60.0):
        return True

    def dong(self):
        pass


GOI = []


def chay_gia(goc, vao, ra, muc, engine=None, **kw):
    GOI.append(dict(muc))
    yield ("lenh", "gia")
    for p in Path(vao).iterdir():
        (Path(ra) / p.name).write_bytes(b"RT:" + json.dumps(muc, sort_keys=True).encode() + b"|" + p.read_bytes())
    yield ("ma", 0)


rt.chay = chay_gia
rt.hop_le = lambda g: True
JOBS = PLUGIN.parent / "_khong_dung"            # chỉ để khỏi nhầm: plugin giả dùng TAM/plugin/jobs
PL = TAM / "plugin"
(PL / "jobs").mkdir(parents=True)
THU = PL / "jobs" / "tram_retouch"
THU.mkdir()
giu = tr.GiuMay()
giu.may, giu.goc = MayGia(), "C:/tool"
TRAM = tr.Tram(THU, "app", rt=rt, giu=giu, goc_tool="C:/tool", khoa_ok=lambda: True)
TRAM_BAT = [True]

RAW = TAM / "G" / "Buoi"
RAW.mkdir(parents=True)
REN = TAM / "render"
REN.mkdir()
rt.ghi_muc_anh(str(RAW), {}, {"vet": 40})
rp.ghi("Cưới mịn", {"vet": 100, "min_da": 60})


def ngu(_s):
    """LrTasks.sleep giả: một nhịp của trạm thật (khi đang bật), rồi ngủ chút."""
    if TRAM_BAT[0]:
        TRAM.mot_vong()
    time.sleep(0.02)


DA_CHAY = []
L = lua51.LuaRuntime(unpack_returned_tuples=True)
g = L.globals()
g.py_ngu = ngu
g.py_chay = lambda c: DA_CHAY.append(str(c)) or 0
g.py_exists = lambda p: os.path.exists(p)
g.py_delete = lambda p: (os.remove(p) if os.path.isfile(p) else None) or True
g.py_move = lambda a, b: os.replace(a, b) or True
g.py_mkdirs = lambda p: os.makedirs(p, exist_ok=True) or True
L.execute(r'''
_PLUGIN = { path = [[%s]] }
WIN_ENV = true
SU_KIEN = {}
THANH = {}
local fake = {
  LrFileUtils = { exists = function(p) return py_exists(p) end, delete = function(p) return py_delete(p) end,
                  move = function(a, b) return py_move(a, b) end,
                  createAllDirectories = function(p) return py_mkdirs(p) end },
  LrPathUtils = { child = function(a, b) return a .. "/" .. b end,
                  leafName = function(p) return string.match(p, "[^/\\]+$") end,
                  extension = function(p) return string.match(p, "%%.([^./\\]+)$") or "" end },
  LrTasks = { sleep = function(s) py_ngu(s) end, execute = function(c) return py_chay(c) end,
              pcall = pcall, startAsyncTask = function(fn) fn() end },
  LrProgressScope = function(t)
      local s = { title = t.title, huy = false, xong = false, phan = {} }
      function s:setCancelable(b) self.huyDuoc = b end
      function s:setCaption(c) self.chu = c end
      function s:setPortionComplete(a, b) self.phan[#self.phan + 1] = a .. "/" .. b end
      function s:isCanceled() return HUY_SAU ~= nil and #SU_KIEN >= HUY_SAU end
      function s:done() self.xong = true end
      THANH[#THANH + 1] = s
      return s end,
  LrView = { bind = function(k) return { bind = k } end },
  LrDialogs = { showBezel = function(m) BEZEL = m end },
}
function import(name) return fake[name] or {} end
package.path = [[%s/?.lua;]] .. package.path

function boLoc(ds, pt)
  local rends = {}
  for i, d in ipairs(ds) do
    local r = { i = i }
    r.src = { photo = { getRawMetadata = function(self, k) return d.raw end },
              waitForRender = function(self)
                SU_KIEN[#SU_KIEN + 1] = "render" .. i
                if d.hong then return false, "loi render" end
                return true, d.path end }
    r.sat = { destinationPath = d.path,
              renditionIsDone = function(self, ok, msg)
                SU_KIEN[#SU_KIEN + 1] = "xong" .. i
                KQ[i] = ok end }
    rends[i] = r
  end
  KQ = {}
  local fc = { propertyTable = pt, renditionsToSatisfy = rends }
  function fc:renditions()
    local i = 0
    return function() i = i + 1; local r = rends[i]; if r then return r.src, r.sat end end
  end
  return fc
end
''' % (str(PL).replace("\\", "/"), str(PLUGIN).replace("\\", "/")))
R = L.eval('require("RetouchKhiXuat")')


def lua_ds(ds):
    t = L.table()
    for i, d in enumerate(ds, 1):
        e = L.table()
        e["path"] = str(d["path"]).replace("\\", "/")
        e["raw"] = str(d.get("raw", ""))
        if d.get("hong"):
            e["hong"] = True
        t[i] = e
    return t


def pt(**kw):
    t = L.table()
    for k, v in kw.items():
        t[k] = v
    return t


def chay_loc(ds, **kw):
    L.execute("SU_KIEN = {}; THANH = {}")
    fc = L.globals().boLoc(lua_ds(ds), pt(**kw))
    R.postProcessRenderedPhotos(L.table(), fc)
    kq = L.globals().KQ
    return [kq[i] for i in range(1, len(ds) + 1)], list(L.globals().SU_KIEN.values())


def anh(ten, noi=b"JPG"):
    p = REN / ten
    p.write_bytes(noi)
    return p


# ---- 1. lượt Export bình thường: trạm app sẵn sàng
TRAM.ghi_nhip(ep=True)
a1, a2, d3 = anh("DSC0001.jpg", b"A1"), anh("DSC0002.jpg", b"A2"), anh("DSC0003.dng", b"D3")
a5 = anh("DSC0005.jpg", b"A5")
GOI.clear()
kq, sk = chay_loc([{"path": a1, "raw": str(RAW / "DSC0001.ARW")},
                   {"path": a2, "raw": str(RAW / "DSC0002.ARW")},
                   {"path": d3, "raw": str(RAW / "DSC0003.ARW")},
                   {"path": REN / "hong.jpg", "hong": True},
                   {"path": a5, "raw": str(RAW / "DSC0005.ARW")}])
ktra("ảnh JPEG xuất ra ĐÃ retouch tại chỗ theo mức buổi (vet 40)",
     a1.read_bytes() == b'RT:{"vet": 40}|A1' and a2.read_bytes().startswith(b"RT:")
     and a5.read_bytes().startswith(b"RT:"), a1.read_bytes()[:30])
ktra("DNG không gửi trạm, giữ nguyên", d3.read_bytes() == b"D3" and len(GOI) == 3, f"{len(GOI)} mẻ")
ktra("mọi ảnh renditionIsDone: render hỏng -> false, còn lại true",
     kq == [True, True, True, False, True], str(kq))
ktra("xong ảnh này rồi mới render ảnh kế (Lightroom không nhận file chưa retouch xong)",
     sk == ["render1", "xong1", "render2", "xong2", "render3", "xong3", "render4", "xong4",
            "render5", "xong5"], str(sk))
th = L.globals().THANH[1]
ktra("thanh tiến độ 'AutoTone: retouch khi xuất' huỷ được, đếm tới 5/5, đóng khi xong",
     th.title == "AutoTone: retouch khi xuất" and th.huyDuoc and th.phan[5] == "5/5" and th.xong)
ktra("không yêu cầu nào sót lại trong thư mục trạm",
     not list(THU.glob("yc_*")) and not list(THU.glob("kq_*")) and not list(THU.glob("dang_*")))

# ---- 2. chế độ preset (chọn trong hộp Export)
a6 = anh("DSC0006.jpg", b"A6")
chay_loc([{"path": a6, "raw": str(RAW / "DSC0006.ARW")}], autotone_rt_muc="preset:Cưới mịn")
ktra("chọn 'Preset: Cưới mịn' trong hộp Export -> retouch theo đúng preset đó",
     a6.read_bytes().startswith(b'RT:{"min_da": 60.0, "vet": 100.0}'), a6.read_bytes()[:45])

# ---- 3. tắt trong hộp Export
a7 = anh("DSC0007.jpg", b"A7")
GOI.clear()
kq, _ = chay_loc([{"path": a7, "raw": str(RAW / "DSC0007.ARW")}], autotone_rt_bat=False)
ktra("bỏ tích 'Retouch ảnh xuất ra' -> không gửi trạm, ảnh ra nguyên",
     a7.read_bytes() == b"A7" and not GOI and kq == [True])

# ---- 4. trạm không trả lời -> quá giờ: ảnh vẫn ra, cấm trạm đè
TRAM_BAT[0] = False
R.CHO_DAU, R.CHO_MOI_ANH = 1, 1
a8 = anh("DSC0008.jpg", b"A8")
t0 = time.time()
kq, _ = chay_loc([{"path": a8, "raw": str(RAW / "DSC0008.ARW")}])
huy = list(THU.glob("huy_*.txt"))
ktra("quá giờ: ảnh vẫn xuất ra (renditionIsDone true), rút yêu cầu, ghi huy_ cho trạm",
     kq == [True] and a8.read_bytes() == b"A8" and len(huy) == 1 and not list(THU.glob("yc_*"))
     and time.time() - t0 < 10, f"{time.time() - t0:.1f} s")
TRAM_BAT[0] = True
TRAM.mot_vong()
ktra("trạm bật lại sau đó KHÔNG đè ảnh đã quá giờ", a8.read_bytes() == b"A8")
for f in huy:
    f.unlink()
R.CHO_DAU, R.CHO_MOI_ANH = 240, 180

# ---- 5. bấm ✕ trên thanh: các ảnh còn lại ra không retouch
L.execute("HUY_SAU = 2")
b1, b2, b3 = anh("DSC0011.jpg", b"B1"), anh("DSC0012.jpg", b"B2"), anh("DSC0013.jpg", b"B3")
kq, _ = chay_loc([{"path": b, "raw": str(RAW / (b.stem + ".ARW"))} for b in (b1, b2, b3)])
L.execute("HUY_SAU = nil")
ktra("bấm ✕ sau ảnh 1 -> ảnh 1 retouch, ảnh 2–3 ra KHÔNG retouch, lượt Export vẫn đủ",
     b1.read_bytes().startswith(b"RT:") and b2.read_bytes() == b"B2" and b3.read_bytes() == b"B3"
     and kq == [True, True, True])

# ---- 6. không trạm nào chạy -> mở trạm chạy ngầm bằng lệnh app ghi
for f in THU.glob("tram_*.txt"):
    f.unlink()
tr.ghi_kv(THU / "x.txt", {})
(THU / "tram_lenh.txt").write_text('start "" "C:\\Tone\\AutoTone.exe" --say-tram "D:\\x"\n', encoding="utf-8")
DA_CHAY.clear()
L.execute("SU_KIEN = {}")
kieu = R.damBaoTram(False)
ktra("không có nhịp trạm nào -> chạy lệnh mở trạm ngầm (cmd cần ngoặc kép bọc ngoài)",
     kieu == "dang_mo" and DA_CHAY == ['"start "" "C:\\Tone\\AutoTone.exe" --say-tram "D:\\x""'], str(DA_CHAY))
R.tMo = None

# ---- 7. hộp Export mở: nạp sẵn + dòng trạng thái
tr.ghi_kv(THU / "tram_app.txt", {"pid": 1, "san_sang": 0, "t": int(time.time())})
TRAM_BAT[0] = False
p = pt()
L.execute("function boKiemNap() end")
R.startDialog(p)
ktra("hộp Export mở, app đang mở mà engine chưa nạp -> ghi xin_nap (app nạp ngay)",
     (THU / "xin_nap.txt").exists())
(THU / "xin_nap.txt").unlink()
tr.ghi_kv(THU / "tram_app.txt", {"pid": 1, "san_sang": 1, "may": "cuda", "t": int(time.time())})
p2 = pt()
R.startDialog(p2)
ktra("engine đã nạp -> dòng trạng thái 'Sẵn sàng … cuda'",
     "Sẵn sàng" in str(p2["autotone_rt_trang_thai"]) and "cuda" in str(p2["autotone_rt_trang_thai"]),
     str(p2["autotone_rt_trang_thai"]))
TRAM_BAT[0] = True

# ---- 8. phần hộp Export: preset từ app
TRAM._ds_preset_cu = None
TRAM.ghi_nhip(ep=True)
L.execute('''
FV = {}
local function mk(kind) return function(self, t) t = t or {}; t.kind = kind; return t end end
for _, k in ipairs({"row", "checkbox", "popup_menu", "static_text"}) do FV[k] = mk(k) end
''')
sec = R.sectionForFilterInDialog(L.globals().FV, pt())
items = sec[2][2]["items"]
ten = [items[i]["title"] for i in range(1, len(items) + 1)]
ktra("hộp Export: tiêu đề + ô 'Mức retouch' gồm 'Theo app' và preset của app",
     sec["title"] == "AutoTone — Retouch khi xuất" and ten[0].startswith("Theo app")
     and "Preset: Cưới mịn" in ten, str(ten))

# ---- 9. Info.lua: hai hành động, id cũ giữ nguyên
L2 = lua51.LuaRuntime(unpack_returned_tuples=True)
info = L2.execute((PLUGIN / "Info.lua").read_text(encoding="utf-8"))
fp = info["LrExportFilterProvider"]
ids = [fp[i]["id"] for i in range(1, len(fp) + 1)]
files = [fp[i]["file"] for i in range(1, len(fp) + 1)]
ktra("Info.lua: mảng 2 hành động, id 'ghi lại thư mục Export' cũ giữ nguyên",
     ids == ["vn.saymedia.autotone.batduongdan", "vn.saymedia.autotone.retouchkhixuat"]
     and files == ["BatDuongDan.lua", "RetouchKhiXuat.lua"], str(ids))

print()
print("KET QUA:", "DAT HET" if not LOI else f"{len(LOI)} LOI: {LOI}")
sys.exit(1 if LOI else 0)
