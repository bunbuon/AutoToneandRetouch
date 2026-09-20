--[[ kiem_batduongdan.lua — kiểm Export Filter bắt đường dẫn Export.

     Nạp CHÍNH BatDuongDan.lua thật với SDK giả, rồi kiểm đúng những chỗ mà
     hỏng ở đó là hỏng buổi giao khách:

       1. shouldRenderPhoto LUÔN trả về true. Trả false là RÚT ẢNH ra khỏi lượt
          Export — khách thiếu ảnh mà không ai biết vì sao. Kiểm cả với thông
          số rác, nil, và cả khi thư mục jobs không ghi được.
       2. Module KHÔNG được khai postProcessRenderedPhotos. Khai hàm đó là tự
          nhận trách nhiệm chuyển từng file ảnh về đích — chắn ngang đường ảnh
          đi ra, đúng thứ đã cố tình tránh (xem đầu BatDuongDan.lua).
       3. Tính thư mục đích đúng cho ba kiểu: thư mục cụ thể, có thư mục con,
          và "cùng chỗ ảnh gốc" (không có đường dẫn -> không ghi bừa).
       4. 2000 ảnh không thành 2000 lần ghi file.
       5. Ghi qua .part rồi đổi tên, không để app đọc phải file dở.
       6. Info.lua có khai filter, và trỏ đúng tên file có thật.

     Chạy:  lua5.1 kiem_batduongdan.lua [thu-muc-plugin]
]]

local GOC = (...) or arg[1] or "AutoTone.lrplugin"
local TMP = os.getenv("TMPDIR") or "/tmp"
local SAN = TMP .. "/kiem_batdd_" .. tostring(os.time())
os.execute('mkdir -p "' .. SAN .. '"')

local function coTren(p)
    local a, _, ma = os.execute('test -e "' .. p .. '"')
    if type(a) == "number" then return a == 0 end
    return a == true and (ma == nil or ma == 0)
end

local LrPathUtils = {
    child = function(a, b) return tostring(a) .. "/" .. tostring(b) end,
    leafName = function(p) return (tostring(p):match("[^/\\]+$")) end,
}

--[[ Dem tung loi goi he thong file de bai kiem so duoc "bao nhieu lan ghi". ]]
local DEM = { move = 0, tao = 0 }
local LrFileUtils = {
    exists = function(p) return coTren(p) end,
    delete = function(p) os.remove(p) end,
    move = function(a, b) DEM.move = DEM.move + 1; os.remove(b); os.rename(a, b) end,
    createAllDirectories = function(p)
        DEM.tao = DEM.tao + 1
        os.execute('mkdir -p "' .. p .. '"')
    end,
}

_G._PLUGIN = { path = SAN }
_G.import = function(ten)
    if ten == "LrPathUtils" then return LrPathUtils end
    if ten == "LrFileUtils" then return LrFileUtils end
    return setmetatable({}, { __index = function() return function() end end })
end

local duong = GOC .. "/BatDuongDan.lua"
local nap = assert(loadfile(duong), "khong doc duoc " .. duong)
local F = nap()

local loi = {}
local function ktra(ten, dieu, mo)
    if dieu then print(string.format("  %-52s %s", ten, mo or "dat"))
    else loi[#loi + 1] = ten .. ": " .. tostring(mo) end
end

local function docGhi()
    local f = io.open(SAN .. "/jobs/export_lr_duongdan.txt", "r")
    if not f then return nil end
    local t = {}
    for line in f:lines() do
        local k, v = line:match("^([%w_]+)=(.*)$")
        if k then t[k] = v end
    end
    f:close()
    return t
end

-- ------------------------------------------------- 1. luôn luôn trả về true
local moi = {
    LR_export_destinationType = "specificFolder",
    LR_export_destinationPathPrefix = "F:/Giao/2705",
}
ktra("thông số bình thường -> vẫn xuất ảnh",
     F.shouldRenderPhoto(moi, {}) == true)
ktra("thông số là nil -> vẫn xuất ảnh",
     F.shouldRenderPhoto(nil, {}) == true, "không được rút ảnh nào ra")
ktra("thông số là chuỗi rác -> vẫn xuất ảnh",
     F.shouldRenderPhoto("hong", {}) == true)
ktra("thiếu hẳn khoá đường dẫn -> vẫn xuất ảnh",
     F.shouldRenderPhoto({ LR_format = "JPEG" }, {}) == true)

--[[ Ep cho phan ghi file no hong that: mot ham trong LrFileUtils nem loi.
     Neu shouldRenderPhoto khong con tra ve true nua thi loi ghi file da leo
     duoc sang thanh loi mat anh — dung cai phai chan. ]]
local move_that = LrFileUtils.move
LrFileUtils.move = function() error("gia vo o dia day") end
ktra("ghi file hỏng -> ảnh vẫn ra đủ",
     F.shouldRenderPhoto({ LR_export_destinationType = "specificFolder",
                           LR_export_destinationPathPrefix = "F:/Khac" }, {}) == true,
     "lỗi ghi không được leo sang thành mất ảnh")
LrFileUtils.move = move_that

-- ---------------------------- 2. không được nằm chắn ngang đường ảnh đi ra
ktra("KHÔNG khai postProcessRenderedPhotos",
     F.postProcessRenderedPhotos == nil,
     "khai hàm đó là tự nhận việc chuyển từng file ảnh về đích")
--[[ Doc thang ma nguon nua: co the co ban tuong lai gan ham do vao bang khac
     roi noi vao sau. O day tim CHUOI trong file — nhung phai loai tru phan
     chu thich, vi dau file co ca mot doan giai thich VI SAO khong khai no.
     Bai kiem cu tung bao sai hai lan vi grep trung chu thich; lan nay cat bo
     moi khoi chu thich dai truoc khi tim. ]]
local nguon = io.open(duong, "r"):read("*a")
local than = nguon:gsub("%-%-%[%[.-%]%]", "")
ktra("mã (ngoài chú thích) không nhắc postProcessRenderedPhotos",
     than:find("postProcessRenderedPhotos", 1, true) == nil,
     "không có ở phần chạy thật")

-- --------------------------------------------------- 3. tính thư mục đích
local d1 = F.tinhThuMuc({ LR_export_destinationType = "specificFolder",
                          LR_export_destinationPathPrefix = "F:/Giao" })
ktra("thư mục cụ thể", d1 == "F:/Giao", tostring(d1))

local d2 = F.tinhThuMuc({ LR_export_destinationType = "specificFolder",
                          LR_export_destinationPathPrefix = "F:/Giao",
                          LR_export_useSubfolder = true,
                          LR_export_destinationPathSuffix = "JPG" })
ktra("có bật Put in Subfolder thì nối thêm tên con",
     d2 == "F:/Giao/JPG", tostring(d2))

local d3 = F.tinhThuMuc({ LR_export_destinationType = "specificFolder",
                          LR_export_destinationPathPrefix = "F:/Giao",
                          LR_export_useSubfolder = false,
                          LR_export_destinationPathSuffix = "JPG" })
ktra("tắt Subfolder thì KHÔNG nối, dù suffix còn sót",
     d3 == "F:/Giao", tostring(d3))

local d4 = F.tinhThuMuc({ LR_export_destinationType = "sourceFolder",
                          LR_export_destinationPathPrefix = "" })
ktra("xuất cạnh ảnh gốc -> không có đường dẫn, không ghi bừa",
     d4 == nil, "trả về nil")

-- ------------------------------------- 4/5. ghi đúng, và không ghi 2000 lần
os.execute('rm -rf "' .. SAN .. '/jobs"')
DEM.move, DEM.tao = 0, 0
local st = { LR_export_destinationType = "specificFolder",
             LR_export_destinationPathPrefix = "F:/Giao/2705",
             LR_export_useSubfolder = true,
             LR_export_destinationPathSuffix = "JPG",
             LR_format = "JPEG" }
for _ = 1, 2000 do F.shouldRenderPhoto(st, {}) end
ktra("2000 ảnh chỉ ghi file 1 lần", DEM.move == 1, DEM.move .. " lần ghi")

local ghi = docGhi()
ktra("có ghi ra file cho app đọc", ghi ~= nil)
ktra("ghi đúng thư mục đích (đã gộp thư mục con)",
     ghi and ghi.thu_muc == "F:/Giao/2705/JPG", ghi and ghi.thu_muc)
ktra("ghi cả định dạng và mốc thời gian",
     ghi and ghi.dinh_dang == "JPEG" and (ghi.tem or ""):match("^%d%d%d%d%-"),
     ghi and (ghi.dinh_dang .. " · " .. tostring(ghi.tem)))
ktra("không để lại file .part",
     not coTren(SAN .. "/jobs/export_lr_duongdan.txt.part"))

--[[ Doi thu muc dich giua chung -> phai ghi lai NGAY, khong doi het gio nghi.
     Nguoi dung Export lo A roi Export lo B sang cho khac la chuyen thuong. ]]
local truoc = DEM.move
F.shouldRenderPhoto({ LR_export_destinationType = "specificFolder",
                      LR_export_destinationPathPrefix = "F:/Giao/khac" }, {})
ktra("đổi thư mục giữa chừng thì ghi lại ngay",
     DEM.move == truoc + 1, docGhi().thu_muc)

-- ------------------------------------------------------------- 6. Info.lua
local Info = assert(loadfile(GOC .. "/Info.lua"))()
local ep = Info.LrExportFilterProvider
ktra("Info.lua có khai LrExportFilterProvider", type(ep) == "table")
ktra("filter trỏ đúng file có thật",
     ep and coTren(GOC .. "/" .. tostring(ep.file)), ep and ep.file)
ktra("filter có id riêng",
     ep and type(ep.id) == "string" and ep.id ~= "", ep and ep.id)
ktra("khai filter KHÔNG làm mất mục menu nào",
     type(Info.LrLibraryMenuItems) == "table" and #Info.LrLibraryMenuItems >= 5,
     #Info.LrLibraryMenuItems .. " mục")

os.execute('rm -rf "' .. SAN .. '"')
print()
if #loi > 0 then
    for _, m in ipairs(loi) do print("  [!] " .. m) end
    print(#loi .. " LOI")
    os.exit(1)
end
print("TAT CA DAT")
