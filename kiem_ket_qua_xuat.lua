--[[ kiem_ket_qua_xuat.lua — kiểm đường "app nhờ plugin xuất" bằng SDK giả.
     Nạp CHÍNH AutoToneCore.lua thật.

     VÌ SAO (3/10): buổi G:\1009 trên app, Lightroom đang mở G:\1005 — bản xuất
     của 1005 XOÁ luôn bản của 1009 (plugin chỉ giữ một file cho cả catalog), và
     khi thư mục không có trong catalog thì plugin chỉ ghi nhật ký, app đợi 90
     giây rồi báo sai bệnh. Canh:

       1. Ghi bản xuất mới KHÔNG xoá bản của buổi khác; chỉ dọn khi quá 30 bản,
          bỏ bản CŨ NHẤT trước.
       2. Nhờ xuất thư mục có ảnh -> ketqua_xuat.txt có thu_muc, so_anh, bo_sao
          (ảnh 1 sao bị bỏ theo quy ước), file (tên bản xuất vừa ghi).
       3. Thư mục KHÔNG có trong catalog -> ketqua_xuat.txt loi=khong-co-trong-catalog
          và không ghi bản xuất rỗng nào.
       4. Mọi ảnh đều 1 sao -> loi + bo_sao đúng số.

     Chạy:  lua5.1 kiem_ket_qua_xuat.lua [thu-muc-plugin]
]]

local GOC = (...) or arg[1] or "AutoTone.lrplugin"
local TMP = os.getenv("TMPDIR") or "/tmp"
local SAN = TMP .. "/kiem_kq_xuat_" .. tostring(os.time()) .. "_" .. tostring(math.random(1e6))
os.execute('mkdir -p "' .. SAN .. '/jobs"')

local function coTren(p)
    local a, _, ma = os.execute('test -e "' .. p .. '"')
    if type(a) == "number" then return a == 0 end
    return a == true and (ma == nil or ma == 0)
end
local function dsFile(d)
    local out = {}
    local h = io.popen('ls -1 "' .. d .. '" 2>/dev/null')
    if h then
        for ten in h:lines() do out[#out + 1] = d .. "/" .. ten end
        h:close()
    end
    return out
end
local function doc(p)
    local f = io.open(p, "r"); if not f then return nil end
    local s = f:read("*a"); f:close(); return s
end
local function ghi(p, s)
    local f = assert(io.open(p, "w")); f:write(s); f:close()
end

_G._PLUGIN = { path = SAN }
local LrPathUtils = {
    child = function(a, b) return tostring(a) .. "/" .. tostring(b) end,
    leafName = function(p) return (tostring(p):match("[^/\\]+$")) end,
}
local LrFileUtils = {
    exists = function(p) return coTren(p) end,
    delete = function(p) os.remove(p) end,
    move = function(a, b) os.remove(b); os.rename(a, b) end,
    createAllDirectories = function(p) os.execute('mkdir -p "' .. p .. '"') end,
    files = function(d)
        local ds, i = dsFile(d), 0
        return function() i = i + 1; return ds[i] end
    end,
}
local LrTasks = { yield = function() end, sleep = function() end }
local LrFunctionContext = {
    callWithContext = function(_, fn) return fn({ addFailureHandler = function() end }) end,
    pcallWithContext = function(_, fn)
        local ok, r = pcall(fn, { addFailureHandler = function() end })
        return ok, r
    end,
}

local function anh(duong, sao)
    return {
        getRawMetadata = function(_, k)
            if k == "path" then return duong end
            if k == "rating" then return sao end
        end,
        getDevelopSettings = function()
            return { Exposure2012 = 0, Highlights2012 = 16, Shadows2012 = 16,
                     Temperature = 5250, Tint = 16, WhiteBalance = "Custom",
                     Contrast2012 = 5, Whites2012 = -25, Blacks2012 = -18 }
        end,
    }
end

local THU_MUC = {
    ["G:\\1009"] = { anh("G:\\1009\\A.ARW", 0), anh("G:\\1009\\B.ARW", 1), anh("G:\\1009\\C.ARW", 0) },
    ["G:\\SAO"] = { anh("G:\\SAO\\A.ARW", 1), anh("G:\\SAO\\B.ARW", 1) },
}
local catalog = {
    withReadAccessDo = function(_, fn) fn() end,
    getFolderByPath = function(_, p)
        local ds = THU_MUC[p]
        if not ds then return nil end
        return { getPhotos = function() return ds end }
    end,
    getAllPhotos = function() return {} end,
}
local LrApplication = { activeCatalog = function() return catalog end }

_G.import = function(ten)
    if ten == "LrPathUtils"       then return LrPathUtils end
    if ten == "LrFileUtils"       then return LrFileUtils end
    if ten == "LrTasks"           then return LrTasks end
    if ten == "LrApplication"     then return LrApplication end
    if ten == "LrFunctionContext" then return LrFunctionContext end
    return setmetatable({}, { __index = function() return function() end end })
end

package.path = GOC .. "/?.lua;" .. package.path
local Core = require "AutoToneCore"

local loi = {}
local function kiem(dk, thong_bao) if not dk then loi[#loi + 1] = thong_bao end end
local JOBS = SAN .. "/jobs"

local function ketQua()
    local s = doc(JOBS .. "/ketqua_xuat.txt")
    if not s then return nil end
    local t = {}
    for k, v in s:gmatch("([%w_]+)=([^\n]*)") do t[k] = v end
    return t
end
local function cacBanXuat()
    local ds = {}
    for _, p in ipairs(dsFile(JOBS)) do
        local ten = p:match("[^/]+$")
        if ten:match("^export_.*%.tsv$") then ds[#ds + 1] = ten end
    end
    table.sort(ds)
    return ds
end
local function nho(thu_muc, them)
    ghi(JOBS .. "/request_export.txt", thu_muc .. "\n" .. (them or ""))
    return Core.runExportRequest()
end

-- 1. 35 bản xuất cũ (của buổi khác) -> ghi bản mới: còn đúng 30, mất 6 bản cũ nhất
for i = 1, 35 do
    ghi(string.format("%s/export_20260901_%06d.tsv", JOBS, i), "path\tExposure2012\nG:\\1005\\X.ARW\t0\n")
end
-- 2. nhờ xuất thư mục có ảnh, bỏ 1 sao
local n = nho("G:\\1009", "skip_rating=1\n")
kiem(n == 2, "1009: phai xuat 2 anh (bo 1 anh 1 sao), dang " .. tostring(n))
local kq = ketQua() or {}
kiem(kq.thu_muc == "G:\\1009", "ketqua: thu_muc = " .. tostring(kq.thu_muc))
kiem(kq.so_anh == "2" and kq.bo_sao == "1", "ketqua: so_anh/bo_sao = " .. tostring(kq.so_anh) .. "/" .. tostring(kq.bo_sao))
kiem(kq.loi == nil, "ketqua: khong duoc co loi khi xuat duoc")
local ds = cacBanXuat()
kiem(#ds == 30, "phai con dung 30 ban xuat, dang " .. #ds)
kiem(kq.file ~= nil and ds[#ds] == kq.file, "ketqua.file phai la ban xuat vua ghi (" .. tostring(kq.file) .. ")")
kiem(ds[1] == "export_20260901_000007.tsv", "phai bo 6 ban CU NHAT, ban con lai som nhat la " .. tostring(ds[1]))

-- 3. thư mục không có trong catalog
local truoc = #cacBanXuat()
n = nho("G:\\CHUA_IMPORT", "skip_rating=1\n")
kq = ketQua() or {}
kiem(n == 0, "thu muc khong co trong catalog phai tra 0")
kiem(kq.loi == "khong-co-trong-catalog" and kq.thu_muc == "G:\\CHUA_IMPORT",
     "ketqua: thu muc chua import phai bao loi=khong-co-trong-catalog, dang " .. tostring(kq.loi))
kiem(#cacBanXuat() == truoc, "khong duoc ghi ban xuat rong")

-- 4. mọi ảnh đều 1 sao
n = nho("G:\\SAO", "skip_rating=1\n")
kq = ketQua() or {}
kiem(n == 0 and kq.loi ~= nil and kq.bo_sao == "2",
     "ca thu muc 1 sao: loi va bo_sao=2, dang loi=" .. tostring(kq.loi) .. " bo_sao=" .. tostring(kq.bo_sao))

-- 5. nhịp của vòng lặp nền: ghi file, và không ghi lại trong 10 giây
os.remove(JOBS .. "/plugin_song.txt")
kiem(Core.ghiNhip(51) == true, "ghiNhip lan dau phai ghi")
local nhip = doc(JOBS .. "/plugin_song.txt") or ""
kiem(nhip:match("vong=51") ~= nil, "plugin_song.txt phai co vong=51, dang: " .. nhip)
kiem(Core.ghiNhip(51) == false, "ghiNhip trong 10 giay phai bo qua (khong ghi dia lien tuc)")
kiem(Core.ghiNhip(52, 0) == true and (doc(JOBS .. "/plugin_song.txt") or ""):match("vong=52") ~= nil,
     "ghiNhip cachGiay=0 phai ghi lai")

for _, m in ipairs(loi) do print("  [!] " .. m) end
print(#loi == 0 and "TAT CA DAT" or (#loi .. " LOI"))
os.exit(#loi == 0 and 0 or 1)
