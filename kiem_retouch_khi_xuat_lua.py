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
    GOI.append(len(list(Path(vao).iterdir())))
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
#  Giả đúng sandbox Lua của Lightroom: KHÔNG có os.rename / os.remove (Diagnose.lua 31/8).
#  Lua chuẩn có hai hàm đó -> v67 dùng os.rename vẫn đạt kiểm mà hỏng trong Lightroom thật.
L.execute("os.rename = nil; os.remove = nil; os.execute = nil; os.exit = nil")
g = L.globals()
g.py_ngu = ngu
g.py_chay = lambda c: DA_CHAY.append(str(c)) or 0
g.py_exists = lambda p: os.path.exists(p)
g.py_delete = lambda p: (os.remove(p) if os.path.isfile(p) else (os.rmdir(p) if os.path.isdir(p) else None)) or True
NOI_CUA = {}            # nội dung byte của ảnh render (qua Lua là mã hoá lại — giữ ở Python)
g.py_ghi = lambda p, k: Path(p).write_bytes(NOI_CUA[str(k)]) and True


def _files(d):
    it = iter(sorted(str(Path(d) / x) for x in os.listdir(d)) if os.path.isdir(d) else [])
    return lambda *_: next(it, None)


g.py_files = _files
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
                  createAllDirectories = function(p) return py_mkdirs(p) end,
                  files = function(d) return py_files(d) end },
  LrPathUtils = { child = function(a, b) return a .. "/" .. b end,
                  leafName = function(p) return string.match(p, "[^/\\]+$") end,
                  parent = function(p) return string.match(p, "^(.*)[/\\][^/\\]+$") end,
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
  local rends, sats = {}, {}
  for i, d in ipairs(ds) do
    local r = { i = i }
    local ph = { localIdentifier = i, getRawMetadata = function(self, k) return d.raw end }
    r.src = { photo = ph,
              waitForRender = function(self)
                SU_KIEN[#SU_KIEN + 1] = "render" .. i
                if d.hong then return false, "loi render" end
                return true, r.duong end }
    r.sat = { destinationPath = d.path, photo = ph,
              renditionIsDone = function(self, ok, msg)
                SU_KIEN[#SU_KIEN + 1] = "xong" .. i
                KQ[i] = ok end }
    rends[i], sats[i] = r, r.sat
  end
  KQ, TRUOC = {}, {}
  local fc = { propertyTable = pt, renditionsToSatisfy = sats }
  function fc:renditions(tuy)
    -- đo thật 11/10: Lightroom định đường + render TRƯỚC (41 ảnh trong vài giây)
    for i, r in ipairs(rends) do
      local p = nil
      if tuy and tuy.filterSettings and not BO_QUA_DUONG then p = tuy.filterSettings(r.sat, {}) end
      r.duong = p or r.sat.destinationPath
      if not ds[i].hong then py_ghi(r.duong, ds[i].noi) end
      TRUOC[i] = py_exists(r.sat.destinationPath)
    end
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
        k = str(len(NOI_CUA) + 1)
        noi = d.get("noi", "LR")
        NOI_CUA[k] = noi.encode("latin-1") if isinstance(noi, str) else noi
        e["noi"] = k
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
    truoc = L.globals().TRUOC
    global TRUOC_VONG
    TRUOC_VONG = [truoc[i] for i in range(1, len(ds) + 1)]
    return [kq[i] for i in range(1, len(ds) + 1)], list(L.globals().SU_KIEN.values())


TRUOC_VONG = []
JPEG_DUOI = "\xff\xd9"


def anh(ten, noi="JPG"):
    """Đường đích của một ảnh xuất (Lightroom giả render nội dung `noi` + FFD9)."""
    return REN / ten


def nd(p):
    return p.read_bytes() if p.exists() else b""


# ---- 1. lượt Export bình thường: trạm app sẵn sàng
#  bài kiểm chạy nhanh hơn ngưỡng "file đứng yên" -> để 0 (ngưỡng thật: test_tram_retouch)
tr.ON_DINH_GIAY = 0.0
TRAM.ghi_nhip(ep=True)
a1, a2, d3 = anh("DSC0001.jpg"), anh("DSC0002.jpg"), anh("DSC0003.dng")
anh_th = [anh(f"DSC000{i}.jpg") for i in (5, 6, 7, 8, 9)]
GOI.clear()
ds1 = ([{"path": a1, "raw": str(RAW / "DSC0001.ARW"), "noi": "A1" + JPEG_DUOI},
        {"path": a2, "raw": str(RAW / "DSC0002.ARW"), "noi": "A2" + JPEG_DUOI},
        {"path": d3, "raw": str(RAW / "DSC0003.ARW"), "noi": "D3"},
        {"path": REN / "hong.jpg", "hong": True}]
       + [{"path": a, "raw": str(RAW / (a.stem + ".ARW")), "noi": "AX" + JPEG_DUOI} for a in anh_th])
kq, sk = chay_loc(ds1)
ktra("Lightroom render trước mọi ảnh mà thư mục xuất CHƯA có file nào (render vào thư mục tạm)",
     TRUOC_VONG[:2] == [False, False] and not any(TRUOC_VONG[4:]), str(TRUOC_VONG))
ktra("ảnh hiện trong thư mục xuất là ĐÃ retouch theo mức buổi (vet 40)",
     nd(a1) == b'RT:{"vet": 40}|A1\xff\xd9' and nd(a2).startswith(b"RT:")
     and all(nd(a).startswith(b"RT:") for a in anh_th), nd(a1)[:30])
ktra("trạm retouch THEO LÔ (Lightroom render trước -> nhiều ảnh một mẻ engine)",
     max(GOI or [0]) > 1 and sum(GOI) == 7, str(GOI))
ktra("DNG không qua thư mục tạm, không gửi trạm, giữ nguyên", nd(d3) == b"D3")
ktra("mọi ảnh renditionIsDone: render hỏng -> false, còn lại true",
     kq == [True, True, True, False, True, True, True, True, True], str(kq))
ktra("thư mục render tạm đã dọn (không còn file / thư mục)",
     not (REN / ".autotone_dang_retouch").exists(), str(list(REN.glob(".autotone_dang_retouch/*"))))
th = L.globals().THANH[1]
ktra("thanh tiến độ 'AutoTone: retouch khi xuất' huỷ được, đếm tới 9/9, đóng khi xong",
     th.title == "AutoTone: retouch khi xuất" and th.huyDuoc and th.phan[9] == "9/9" and th.xong)
ktra("không yêu cầu nào sót lại trong thư mục trạm",
     not any(list(THU.glob(m)) for m in ("yc_*", "kq_*", "dang_*", "cho_*", "san_*")),
     str([x.name for x in THU.iterdir() if x.name[:3] in ("yc_", "kq_", "dan", "cho", "san")]))

# ---- 1b. Lightroom bỏ qua đường tạm (Export with Previous) -> sửa tại chỗ như bản đầu
L.execute("BO_QUA_DUONG = true")
a4 = anh("DSC0004.jpg")
kq, _ = chay_loc([{"path": a4, "raw": str(RAW / "DSC0004.ARW"), "noi": "A4" + JPEG_DUOI}])
L.execute("BO_QUA_DUONG = nil")
log = (PL / "jobs" / "plugin.log").read_text(encoding="utf-8")
ktra("Lightroom bỏ qua đường tạm -> vẫn retouch (đè tại chỗ), log nói rõ, không sót mục chờ",
     nd(a4).startswith(b"RT:") and kq == [True] and "KHÔNG hỏi đường render" in log
     and "render THẲNG đích" in log
     and not list(THU.glob("cho_*")), nd(a4)[:20])

# ---- 2. chế độ preset (chọn trong hộp Export)
a6 = anh("DSC0016.jpg")
chay_loc([{"path": a6, "raw": str(RAW / "DSC0016.ARW"), "noi": "A6" + JPEG_DUOI}],
         autotone_rt_muc="preset:Cưới mịn")
ktra("chọn 'Preset: Cưới mịn' trong hộp Export -> retouch theo đúng preset đó",
     nd(a6).startswith(b'RT:{"min_da": 60.0, "vet": 100.0}'), nd(a6)[:45])

# ---- 3. tắt trong hộp Export
a7 = anh("DSC0017.jpg")
GOI.clear()
kq, _ = chay_loc([{"path": a7, "raw": str(RAW / "DSC0017.ARW"), "noi": "A7" + JPEG_DUOI}],
                 autotone_rt_bat=False)
ktra("bỏ tích 'Retouch ảnh xuất ra' -> render thẳng đích, không gửi trạm",
     nd(a7) == b"A7\xff\xd9" and not GOI and kq == [True] and TRUOC_VONG == [True])

# ---- 3b. tắt "Retouch song song" (11/10 — user: "hoặc thêm option bật tắt chạy song song")
a8 = anh("DSC0018.jpg")
kq, _ = chay_loc([{"path": a8, "raw": str(RAW / "DSC0018.ARW"), "noi": "A8" + JPEG_DUOI}],
                 autotone_rt_song_song=False)
log = (PL / "jobs" / "plugin.log").read_text(encoding="utf-8")
ktra("bỏ tích 'Retouch song song' -> không qua thư mục tạm, vẫn retouch tại chỗ, log nói rõ",
     nd(a8).startswith(b"RT:") and kq == [True] and "song song TẮT" in log
     and not list(THU.glob("cho_*")), nd(a8)[:20])

# ---- 4. trạm không trả lời -> quá giờ: ảnh vẫn ra, cấm trạm đè
TRAM_BAT[0] = False
R.CHO_DAU, R.CHO_MOI_ANH = 1, 1
a8 = anh("DSC0018.jpg")
huy_cu = set(THU.glob("huy_*.txt"))
t0 = time.time()
kq, _ = chay_loc([{"path": a8, "raw": str(RAW / "DSC0018.ARW"), "noi": "A8" + JPEG_DUOI}])
huy = list(set(THU.glob("huy_*.txt")) - huy_cu)
ktra("quá giờ: bản Lightroom render vẫn ra đích (chưa retouch), rút mục chờ, ghi huy_",
     kq == [True] and nd(a8) == b"A8\xff\xd9" and len(huy) == 1
     and not list(THU.glob("cho_*")) and time.time() - t0 < 10, f"{time.time() - t0:.1f} s")
TRAM_BAT[0] = True
TRAM.mot_vong()
ktra("trạm bật lại sau đó KHÔNG đè ảnh đã quá giờ", nd(a8) == b"A8\xff\xd9")
for f in huy:
    f.unlink()
R.CHO_DAU, R.CHO_MOI_ANH = 240, 180

# ---- 5. bấm ✕ trên thanh: các ảnh còn lại ra không retouch
L.execute("HUY_SAU = 2")
b1, b2, b3 = anh("DSC0011.jpg"), anh("DSC0012.jpg"), anh("DSC0013.jpg")
kq, _ = chay_loc([{"path": b, "raw": str(RAW / (b.stem + ".ARW")), "noi": b.stem + JPEG_DUOI}
                  for b in (b1, b2, b3)])
L.execute("HUY_SAU = nil")
TRAM.mot_vong()
ktra("bấm ✕ sau ảnh 1 -> ảnh 1 retouch, ảnh 2–3 ra bản Lightroom (dù trạm đã làm trước), đủ ảnh",
     nd(b1).startswith(b"RT:") and nd(b2) == b"DSC0012\xff\xd9" and nd(b3) == b"DSC0013\xff\xd9"
     and kq == [True, True, True] and not list(REN.glob(".autotone_dang_retouch/.kq_*")),
     f"{nd(b2)[:12]} {nd(b3)[:12]}")

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
ktra("hộp Export mở -> ghi xin_nap kèm chế độ mức (trạm nạp + hâm nóng mô hình)",
     (THU / "xin_nap.txt").exists()
     and "che_do=app" in (THU / "xin_nap.txt").read_text(encoding="utf-8"))
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
