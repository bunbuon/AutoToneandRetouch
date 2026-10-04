--[[ kiem_xuat_thong_so.lua — kiểm bản xuất thông số (catalog -> autotone) và
     cách đọc job, bằng SDK giả. Nạp CHÍNH AutoToneCore.lua và
     ExportForAutoTone.lua thật, không chép lại đoạn nào.

     VÌ SAO (3/10): quy trình mới của người dùng — preset BỎ TRỐNG nhóm White
     Balance và Basic Tone, autotone tự ghi hai nhóm đó. autotone chỉ biết ảnh
     nào đang As Shot / Tone 0 nhờ bản xuất này, nên canh:

       1. Cả HAI đường xuất (app yêu cầu — writeExport; menu —
          ExportForAutoTone.lua) có đủ cột WhiteBalance, Contrast2012,
          Whites2012, Blacks2012, và cột mới nằm SAU bảy cột cũ.
       2. WhiteBalance ra CHỮ ("As Shot") — bộ ghi số cũ biến nó thành ô trống.
       3. Ảnh As Shot mà Lightroom không trả Temperature thì ô để trống, không
          bịa số.
       4. Chữ có tab / xuống dòng không làm lệch cột.
       5. readJob đọc được ba cột Tone mới theo tên cột; ô trống = không đụng.

     Chạy:  lua5.1 kiem_xuat_thong_so.lua [thu-muc-plugin]
     In ra đường dẫn bản xuất ở dòng cuối để bên ngoài kiểm thêm bằng autotone.
]]

local GOC = (...) or arg[1] or "AutoTone.lrplugin"
local TMP = os.getenv("TMPDIR") or "/tmp"
local SAN = TMP .. "/kiem_xuat_ts_" .. tostring(os.time()) .. "_" .. tostring(math.random(1e6))
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

-- ---------------------------------------------------------------- SDK giả
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
local LrTasks = {
    yield = function() end, sleep = function() end,
    startAsyncTask = function(fn) fn() end,
}
local THONG_BAO = {}
local LrDialogs = {
    message = function(tieu_de, noi_dung) THONG_BAO[#THONG_BAO + 1] = tostring(tieu_de) .. " | " .. tostring(noi_dung) end,
    showModalProgressDialog = function()
        return { setPortionComplete = function() end, setCaption = function() end,
                 isCanceled = function() return false end }
    end,
}
local LrFunctionContext = {
    callWithContext = function(_, fn) return fn({ addFailureHandler = function() end }) end,
    pcallWithContext = function(_, fn)
        local ok, r = pcall(fn, { addFailureHandler = function() end })
        return ok, r
    end,
}

local ANH = {}
local catalog = {
    withReadAccessDo = function(_, fn) fn() end,
    getMultipleSelectedOrAllPhotos = function() return ANH end,
}
local LrApplication = { activeCatalog = function() return catalog end }

_G.import = function(ten)
    if ten == "LrPathUtils"       then return LrPathUtils end
    if ten == "LrFileUtils"       then return LrFileUtils end
    if ten == "LrTasks"           then return LrTasks end
    if ten == "LrApplication"     then return LrApplication end
    if ten == "LrDialogs"         then return LrDialogs end
    if ten == "LrFunctionContext" then return LrFunctionContext end
    return setmetatable({}, { __index = function() return function() end end })
end

local function anh(ten, s)
    return {
        getRawMetadata = function(_, k)
            if k == "path" then return "G:\\Hiu_thu\\" .. ten end
            if k == "rating" then return 0 end
        end,
        getDevelopSettings = function() return s end,
    }
end

-- As Shot (quy trình mới), preset đầy đủ (cũ), As Shot thiếu Temperature, chữ quái
ANH[1] = anh("A.ARW", { WhiteBalance = "As Shot", Temperature = 3650, Tint = 4,
                        Exposure2012 = 0, Highlights2012 = 0, Shadows2012 = 0,
                        Contrast2012 = 0, Whites2012 = 0, Blacks2012 = 0 })
ANH[2] = anh("B.ARW", { WhiteBalance = "Custom", Temperature = 5250, Tint = 16,
                        Exposure2012 = -0.24, Highlights2012 = 16, Shadows2012 = 16,
                        Contrast2012 = 5, Whites2012 = -25, Blacks2012 = -18 })
ANH[3] = anh("C.ARW", { WhiteBalance = "As Shot", Exposure2012 = 0,
                        Contrast2012 = 0, Whites2012 = 0, Blacks2012 = 0 })
ANH[4] = anh("D.ARW", { WhiteBalance = "Qu\tai\nla", Temperature = 4000, Tint = 0,
                        Contrast2012 = 0, Whites2012 = 0, Blacks2012 = 0 })

package.path = GOC .. "/?.lua;" .. package.path
local Core = require "AutoToneCore"

local loi = {}
local function kiem(dk, thong_bao) if not dk then loi[#loi + 1] = thong_bao end end

local function tach(line)
    local out, pos = {}, 1
    while true do
        local s, e = string.find(line, "\t", pos, true)
        if not s then out[#out + 1] = string.sub(line, pos); break end
        out[#out + 1] = string.sub(line, pos, s - 1)
        pos = e + 1
    end
    return out
end

local function docXuat(p)
    local fh = assert(io.open(p, "r"))
    local cot = tach(fh:read("*l"))
    local hang = {}
    for line in fh:lines() do
        if line ~= "" then
            local v = tach(line)
            kiem(#v == #cot, "dong lech cot (" .. #v .. " o / " .. #cot .. " cot): " .. line)
            local rec = {}
            for i = 1, #cot do rec[cot[i]] = v[i] end
            hang[(tostring(v[1]):match("[^/\\]+$"))] = rec
        end
    end
    fh:close()
    return cot, hang
end

local CU = { "path", "Exposure2012", "Highlights2012", "Shadows2012",
             "Temperature", "Tint", "AsShotTemperature", "AsShotTint" }
local MOI = { "WhiteBalance", "Contrast2012", "Whites2012", "Blacks2012" }

local function kiemBan(ten, p)
    local cot, h = docXuat(p)
    for i, c in ipairs(CU) do
        kiem(cot[i] == c, ten .. ": cot " .. i .. " phai la " .. c .. ", dang la " .. tostring(cot[i]))
    end
    for i, c in ipairs(MOI) do
        kiem(cot[#CU + i] == c, ten .. ": thieu cot " .. c .. " ngay sau bay cot cu")
    end
    local a, b, c, d = h["A.ARW"] or {}, h["B.ARW"] or {}, h["C.ARW"] or {}, h["D.ARW"] or {}
    kiem(a.WhiteBalance == "As Shot", ten .. ": WhiteBalance anh As Shot = '" .. tostring(a.WhiteBalance) .. "'")
    kiem(a.Temperature == "3650" and a.Tint == "4", ten .. ": Temp/Tint As Shot sai")
    kiem(a.Contrast2012 == "0" and a.Whites2012 == "0" and a.Blacks2012 == "0",
         ten .. ": Contrast/Whites/Blacks anh As Shot phai la 0")
    kiem(b.WhiteBalance == "Custom" and b.Contrast2012 == "5" and b.Whites2012 == "-25"
         and b.Blacks2012 == "-18", ten .. ": preset day du xuat sai")
    kiem(c.Temperature == "" and c.WhiteBalance == "As Shot",
         ten .. ": As Shot thieu Temperature phai de trong o, khong bia so")
    kiem(d.WhiteBalance == "Qu ai la", ten .. ": chu co tab/xuong dong = '" .. tostring(d.WhiteBalance) .. "'")
end

-- 1a. đường app yêu cầu
local n, dest, err = Core.writeExport(catalog, ANH, nil, {})
kiem(n == 4 and dest ~= nil and err == nil, "writeExport: " .. tostring(n) .. " " .. tostring(err))
if dest then kiemBan("writeExport", dest) end

-- 1b. đường menu: chạy chính file ExportForAutoTone.lua
os.remove(dest or "")
dofile(GOC .. "/ExportForAutoTone.lua")
local menu
for _, p in ipairs(dsFile(SAN .. "/jobs")) do
    if p:match("export_.*%.tsv$") then menu = p end
end
kiem(menu ~= nil, "menu xuat khong ra file. Thong bao: " .. table.concat(THONG_BAO, " / "))
if menu then kiemBan("menu", menu) end

-- 5. readJob đọc cột Tone mới theo tên
local job = SAN .. "/jobs/apply_thu.tsv"
local fh = assert(io.open(job, "w"))
fh:write("path\tExposure2012\tTemperature\tRating\tPerspectiveUpright\tContrast2012\tWhites2012\tBlacks2012\n")
fh:write("G:\\Hiu_thu\\A.ARW\t-0.30\t5250\t\t\t5\t-25\t-18\n")
fh:write("G:\\Hiu_thu\\B.ARW\t0.10\t\t\t\t\t\t\n")
fh:close()
local rows = Core.readJob(job)
kiem(#rows == 2, "readJob: so dong " .. #rows)
if #rows == 2 then
    local s1, s2 = rows[1].settings, rows[2].settings
    kiem(s1.Contrast2012 == 5 and s1.Whites2012 == -25 and s1.Blacks2012 == -18,
         "readJob: khong doc duoc Contrast/Whites/Blacks")
    kiem(s2.Contrast2012 == nil and s2.Temperature == nil, "readJob: o trong phai la 'khong dung toi'")
end

for _, m in ipairs(loi) do print("  [!] " .. m) end
print(#loi == 0 and "TAT CA DAT" or (#loi .. " LOI"))
print(menu or dest or "")
os.exit(#loi == 0 and 0 or 1)
