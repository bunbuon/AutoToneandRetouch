--[[ kiem_chup.lua — kiểm ChupCore.lua (chụp nguyên trạng thông số) bằng SDK giả.

     Nạp CHÍNH ChupCore.lua thật. Canh những chỗ mà hỏng ở đó là mất "đáp án"
     người dùng đã sửa tay cả buổi:

       1. Lấy ĐỦ mọi ảnh, kể cả 1 sao — đây là bản sao lưu, không phải dữ liệu học.
       2. Lấy ĐỦ mọi trường, kể cả bảng lồng nhau (đường cong), không chỉ 7 trường
          của bản xuất thường.
       3. Chuỗi có tab / xuống dòng / nháy kép không được làm vỡ dòng TSV.
       4. KHÔNG một lời gọi ghi nào vào catalog.
       5. KHÔNG xoá bản chụp cũ (bản xuất thường thì tự xoá — đó chính là lý do
          phải có file này).
       6. Không có yêu cầu thì không làm gì.

     Chạy:  lua5.1 kiem_chup.lua [thu-muc-plugin]
     In ra đường dẫn file chụp ở dòng cuối để bên ngoài kiểm thêm bằng JSON thật.
]]

local GOC = (...) or arg[1] or "AutoTone.lrplugin"
local TMP = os.getenv("TMPDIR") or "/tmp"
local SAN = TMP .. "/kiem_chup_" .. tostring(os.time()) .. "_" .. tostring(math.random(1e6))
os.execute('mkdir -p "' .. SAN .. '/jobs" "' .. SAN .. '/anh"')

local function coTren(p)
    local a, _, ma = os.execute('test -e "' .. p .. '"')
    if type(a) == "number" then return a == 0 end
    return a == true and (ma == nil or ma == 0)
end
local function doc(p)
    local f = io.open(p, "r"); if not f then return nil end
    local s = f:read("*a"); f:close(); return s
end

local LrPathUtils = {
    child = function(a, b) return tostring(a) .. "/" .. tostring(b) end,
    leafName = function(p) return (tostring(p):match("[^/\\]+$")) end,
}
local LrFileUtils = {
    exists = function(p) return coTren(p) end,
    delete = function(p) os.remove(p) end,
    move = function(a, b) os.remove(b); os.rename(a, b) end,
    createAllDirectories = function(p) os.execute('mkdir -p "' .. p .. '"') end,
}
local LrTasks = { yield = function() end, sleep = function() end }

local GHI = { n = 0 }
local DOC_TRONG_KHOI = { n = 0, dang = false }
--[[ Lightroom that doi getDevelopSettings nam trong withReadAccessDo. Gia lap
     dung the: goi ngoai khoi doc thi nem loi, de kiem ChupCore co tu nhan ra
     va boc khoi doc hay khong. ]]
local catalog = {
    withReadAccessDo = function(_, fn)
        DOC_TRONG_KHOI.n = DOC_TRONG_KHOI.n + 1
        DOC_TRONG_KHOI.dang = true; fn(); DOC_TRONG_KHOI.dang = false
    end,
    withWriteAccessDo = function() GHI.n = GHI.n + 1; error("KHONG DUOC GHI") end,
}
local LrApplication = { activeCatalog = function() return catalog end }

_G.import = function(ten)
    if ten == "LrPathUtils"   then return LrPathUtils end
    if ten == "LrFileUtils"   then return LrFileUtils end
    if ten == "LrTasks"       then return LrTasks end
    if ten == "LrApplication" then return LrApplication end
    return setmetatable({}, { __index = function() return function() end end })
end

local function anh(ten, sao, s)
    return {
        getRawMetadata = function(_, k)
            if k == "path" then return "G:\\2609\\" .. ten end
            if k == "rating" then return sao end
        end,
        getDevelopSettings = function()
            if not DOC_TRONG_KHOI.dang then error("can read access") end
            return s
        end,
        applyDevelopSettings = function() GHI.n = GHI.n + 1; error("KHONG DUOC GHI") end,
    }
end

local KICH = { anh = {} }
package.loaded["AutoToneCore"] = {
    jobDir = function() return SAN .. "/jobs" end,
    log    = function() end,
    try    = function(_, fn)
        local ok, r = pcall(fn)
        if ok then return r end
        return nil, tostring(r)
    end,
    claim = function(p)
        local r = p .. ".running"
        os.rename(p, r)
        if coTren(r) then return r end
        return nil
    end,
    photosInFolder = function() return KICH.anh, "gia lap" end,
}

package.path = GOC .. "/?.lua;" .. package.path
local C = require "ChupCore"

local loi = {}
local function kiem(dk, thong_bao) if not dk then loi[#loi + 1] = thong_bao end end

-- 6 — khong co yeu cau
kiem(C.runRequest() == 0, "khong co yeu cau ma van chay")

-- Du lieu gia: 450 anh (hon 2 lo 200), anh 7 la 1 sao, anh 3 co chuoi quai
for i = 1, 450 do
    local s = {
        Temperature = 5000 + i, Tint = 12, WhiteBalance = "Custom",
        Exposure2012 = -0.25, HueAdjustmentRed = -5,
        ToneCurvePV2012 = { 0, 0, 64, 60, 255, 255 },
        LookTable = {},
        Look = { Name = "Adobe Color", Amount = 1 },
    }
    if i == 3 then
        s.Tieu_de = 'a\tb\nc"d\\e ánh'
        s.Hong = 0 / 0
    end
    KICH.anh[i] = anh(string.format("DSC%05d.ARW", i), (i == 7) and 1 or 0, s)
end

-- 5 — mot ban chup cu phai con nguyen
local CU = SAN .. "/anh/_autotone_da_sua_20000101_000000.tsv"
local f = io.open(CU, "w"); f:write("cu\n"); f:close()

f = io.open(SAN .. "/jobs/request_chup.txt", "w")
f:write("\239\187\191G:\\2609\r\n" .. SAN .. "/anh\r\n"); f:close()
local n = C.runRequest()

kiem(n == 450, "1: phai chup du 450 anh (ca anh 1 sao), duoc " .. tostring(n))
kiem(not coTren(SAN .. "/jobs/request_chup.txt"), "yeu cau khong bi xoa sau khi chay")
kiem(GHI.n == 0, "4: co loi goi GHI vao catalog")
kiem(DOC_TRONG_KHOI.n >= 3, "450 anh phai chia >= 3 lo doc, duoc " .. DOC_TRONG_KHOI.n)
kiem(doc(CU) == "cu\n", "5: ban chup cu bi xoa hoac ghi de")

local xong = doc(SAN .. "/jobs/chup_xong.txt") or ""
local dest, so = xong:match("^([^\t]+)\t(%d+)")
kiem(dest ~= nil and tonumber(so) == 450, "chup_xong.txt sai: " .. xong)
local noi = dest and doc(dest) or ""
local dong = {}
for l in noi:gmatch("[^\n]+") do dong[#dong + 1] = l end
kiem(#dong == 451, "3: phai co 451 dong (1 dau + 450), duoc " .. #dong ..
     " — chuoi co tab/xuong dong da lam vo dong?")
kiem(dong[1] == "path\tRating\tsettings", "dong dau sai: " .. tostring(dong[1]))
for i = 2, #dong do
    local _, so_tab = dong[i]:gsub("\t", "")
    if so_tab ~= 2 then kiem(false, "3: dong " .. i .. " co " .. so_tab .. " tab"); break end
end
kiem(noi:find('G:\\2609\\DSC00007.ARW\t1\t', 1, true) ~= nil, "1: anh 1 sao phai co, Rating = 1")
kiem(noi:find('"ToneCurvePV2012":[0,0,64,60,255,255]', 1, true) ~= nil, "2: mat bang lo nhau (duong cong)")
kiem(noi:find('"Look":{"Amount":1,"Name":"Adobe Color"}', 1, true) ~= nil, "2: doi tuong long nhau sai / khoa khong sap xep")
kiem(noi:find('"Tieu_de":"a\\tb\\nc\\"d\\\\e ánh"', 1, true) ~= nil, "3: thoat chuoi sai")
kiem(noi:find('"Hong":null', 1, true) ~= nil, "NaN phai thanh null")
kiem(noi:find('"LookTable":{}', 1, true) ~= nil, "bang rong phai thanh {}")
kiem(noi:find('"Temperature":5450', 1, true) ~= nil, "mat anh cuoi")

-- Khong co anh -> bao LOI, khong tao file
KICH.anh = {}
f = io.open(SAN .. "/jobs/request_chup.txt", "w"); f:write("G:\\khong_co\n"); f:close()
kiem(C.runRequest() == 0, "thu muc rong ma van bao chup duoc")
kiem((doc(SAN .. "/jobs/chup_xong.txt") or ""):match("^LOI\t") ~= nil, "thu muc rong phai ghi LOI vao chup_xong.txt")

for _, m in ipairs(loi) do print("  [!] " .. m) end
print(#loi == 0 and "TAT CA DAT" or (#loi .. " LOI"))
print(dest or "")
os.exit(#loi == 0 and 0 or 1)
