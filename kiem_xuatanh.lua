--[[ kiem_xuatanh.lua — kiểm XuatCore.lua (app tự chạy Export) bằng SDK giả.

     Nạp CHÍNH XuatCore.lua thật. Canh những chỗ mà hỏng ở đó là hỏng ảnh giao
     khách — tức là hỏng thứ đưa cho người trả tiền:

       1. Đọc yêu cầu phải GIỮ ĐÚNG KIỂU. "false" thành chuỗi "false" là
          Lightroom hiểu thành ĐÚNG (trong Lua mọi chuỗi đều đúng), watermark
          bật lên trên cả nghìn ảnh mà không ai báo gì.
       2. Không có thông số thì DỪNG, tuyệt đối không bịa bộ mặc định.
       3. Thư mục đích do app đặt phải THẮNG mọi thứ có sẵn trong thông số.
       4. Chia lô đúng, cờ dừng ăn giữa hai lô.
       5. Đếm ảnh ra theo FILE CÓ THẬT, không theo số ảnh đưa vào.
       6. Đường xuất ảnh không được dính vào đường ghi màu.

     Chạy:  lua5.1 kiem_xuatanh.lua [thu-muc-plugin]
]]

local GOC = (...) or arg[1] or "AutoTone.lrplugin"
local TMP = os.getenv("TMPDIR") or "/tmp"
local SAN = TMP .. "/kiem_xuatanh_" .. tostring(os.time())
os.execute('mkdir -p "' .. SAN .. '/jobs"')

local function coTren(p)
    local a, _, ma = os.execute('test -e "' .. p .. '"')
    if type(a) == "number" then return a == 0 end
    return a == true and (ma == nil or ma == 0)
end

local LrPathUtils = {
    child = function(a, b) return tostring(a) .. "/" .. tostring(b) end,
    leafName = function(p) return (tostring(p):match("[^/\\]+$")) end,
    removeExtension = function(p) return (tostring(p):gsub("%.[^.]*$", "")) end,
}
local LrFileUtils = {
    exists = function(p) return coTren(p) end,
    delete = function(p) os.remove(p) end,
    move = function(a, b) os.remove(b); os.rename(a, b) end,
    createAllDirectories = function(p) os.execute('mkdir -p "' .. p .. '"') end,
}
local LrTasks = { yield = function() end, sleep = function() end }

local KICH = { lo = {}, thongSoCuoi = nil, hongSau = nil, boQua = {} }
local LrExportSession = function(params)
    KICH.thongSoCuoi = params.exportSettings
    KICH.lo[#KICH.lo + 1] = #params.photosToExport
    local ra = {}
    return {
        doExportOnCurrentTask = function()
            local dest = params.exportSettings.LR_export_destinationPathPrefix
            os.execute('mkdir -p "' .. dest .. '"')
            for i = 1, #params.photosToExport do
                local ten = params.photosToExport[i].__ten
                if not KICH.boQua[ten] then
                    local f = io.open(dest .. "/" .. ten .. ".jpg", "w")
                    f:write("JPEG"); f:close()
                    ra[#ra + 1] = dest .. "/" .. ten .. ".jpg"
                end
            end
            if KICH.hongSau and #KICH.lo >= KICH.hongSau then
                error("gia vo o dia day")
            end
            --[[ Gia lap NGUOI DUNG BAM DUNG GIUA CHUNG: dat co ngay sau lo
                 thu KICH.datCoSauLo. Dat co TRUOC khi chay thi khong kiem duoc
                 gi — code co chu y xoa co sot cua lan truoc, neu khong luot
                 moi se dung ngay lo dau ma khong ai hieu vi sao. ]]
            if KICH.datCoSauLo and #KICH.lo == KICH.datCoSauLo then
                local c = io.open(SAN .. "/jobs/request_xuatanh_dung.txt", "w")
                c:write("dung"); c:close()
            end
        end,
        renditions = function()
            local i = 0
            return function()
                i = i + 1
                if ra[i] then return i, { destinationPath = ra[i] } end
            end
        end,
    }
end
local LrApplication = { activeCatalog = function() return { __gia = true } end }

_G.import = function(ten)
    if ten == "LrPathUtils"     then return LrPathUtils end
    if ten == "LrFileUtils"     then return LrFileUtils end
    if ten == "LrTasks"         then return LrTasks end
    if ten == "LrExportSession" then return LrExportSession end
    if ten == "LrApplication"   then return LrApplication end
    return setmetatable({}, { __index = function() return function() end end })
end

local NHAT_KY = {}
package.loaded["AutoToneCore"] = {
    jobDir = function() return SAN .. "/jobs" end,
    log    = function(m) NHAT_KY[#NHAT_KY + 1] = tostring(m) end,
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
    photosInFolder = function() return KICH.anh or {}, "gia lap" end,
}
--[[ DuyetCore gia: chi can locSao. Cot de kiem rang XuatCore DUNG LAI ham loc
     chung chu khong tu viet mot ban khac — hai quy uoc 1 sao lech nhau la
     kieu loi khong ai nhin ra tu ben ngoai. ]]
local DA_GOI_LOCSAO = { n = 0 }
package.loaded["DuyetCore"] = {
    locSao = function(photos, boSao)
        DA_GOI_LOCSAO.n = DA_GOI_LOCSAO.n + 1
        boSao = tonumber(boSao)
        if not boSao or boSao == 0 then return photos, 0 end
        local out, bo = {}, 0
        for i = 1, #photos do
            if photos[i].__sao == boSao then bo = bo + 1
            else out[#out + 1] = photos[i] end
        end
        return out, bo
    end,
}

local X = assert(loadfile(GOC .. "/XuatCore.lua"))()

local loi = {}
local function ktra(ten, dieu, mo)
    if dieu then print(string.format("  %-52s %s", ten, mo or "dat"))
    else loi[#loi + 1] = ten .. ": " .. tostring(mo) end
end

local function anhGia(n, sao)
    local ds = {}
    for i = 1, n do
        ds[i] = { __ten = string.format("IMG_%04d", i), __sao = sao and sao[i] or nil,
                  getRawMetadata = function(_, k)
                      if k == "rating" then return sao and sao[i] or nil end
                      return nil
                  end }
    end
    return ds
end

local function datYeuCau(dong)
    local f = io.open(SAN .. "/jobs/" .. X.YEU_CAU, "w")
    f:write(table.concat(dong, "\n") .. "\n")
    f:close()
end

local function docTienDo()
    local f = io.open(SAN .. "/jobs/" .. X.TIEN_DO, "r")
    if not f then return {} end
    local t = {}
    for line in f:lines() do
        local k, v = line:match("^([%w_]+)=(.*)$")
        if k then t[k] = v end
    end
    f:close()
    return t
end

-- ------------------------------------------------ 1. đọc yêu cầu, giữ kiểu
local folder, opts, ts = X.docDong({
    "F:/Buoi/2705",
    "dest=F:/Giao/2705",
    "bo_sao=1",
    "lo=10",
    "ts\ts\tLR_format\tJPEG",
    "ts\tn\tLR_jpeg_quality\t0.7",
    "ts\tb\tLR_useWatermark\tfalse",
    "ts\tb\tLR_size_doConstrain\ttrue",
    "ts\tn\tLR_size_maxWidth\t2048",
    "ts\ts\tLR_tokens\t{{custom_token}}-{{image_filename_number_suffix}}",
})
ktra("đọc đúng thư mục nguồn", folder == "F:/Buoi/2705", tostring(folder))
ktra("đọc đúng thư mục đích", opts.dest == "F:/Giao/2705", tostring(opts.dest))
ktra("chuỗi vẫn là chuỗi", ts.LR_format == "JPEG")
ktra("số vẫn là số (không thành chuỗi)",
     type(ts.LR_jpeg_quality) == "number" and ts.LR_jpeg_quality == 0.7,
     type(ts.LR_jpeg_quality))
--[[ Day la bai quan trong nhat ca file: trong Lua chuoi "false" la GIA TRI
     DUNG. Doc sai kieu mot khoa boolean la bat watermark len ca nghin anh. ]]
ktra("false vẫn là SAI, không phải chuỗi \"false\"",
     ts.LR_useWatermark == false, type(ts.LR_useWatermark))
ktra("true vẫn là ĐÚNG", ts.LR_size_doConstrain == true)
ktra("giá trị có dấu ngoặc nhọn không bị cắt",
     ts.LR_tokens == "{{custom_token}}-{{image_filename_number_suffix}}",
     tostring(ts.LR_tokens))

local _, _, ts2 = X.docDong({ "F:/x", "ts\tn\tLR_jpeg_quality\tbay_gio" })
ktra("số hỏng thì BỎ khoá, không nhét chuỗi vào chỗ số",
     ts2.LR_jpeg_quality == nil, "bỏ qua khoá hỏng")

-- ------------------------------------- 2. không có thông số thì phải dừng
KICH.anh = anhGia(5)
datYeuCau({ "F:/Buoi/2705", "dest=" .. SAN .. "/ra_khong_ts" })
local n = X.runRequest()
ktra("không kèm thông số -> KHÔNG xuất gì hết", n == 0)
ktra("và nói rõ vì sao trong tiến độ",
     (docTienDo().thong_bao or ""):find("thong so", 1, true) ~= nil,
     docTienDo().thong_bao)
ktra("không tạo ra file ảnh nào", not coTren(SAN .. "/ra_khong_ts"))

-- ------------------------- 3/4/5. chạy thật: lô, thư mục đích, đếm theo file
KICH.lo = {}
local ra_dir = SAN .. "/ra"
KICH.anh = anhGia(23)
datYeuCau({ "F:/Buoi/2705", "dest=" .. ra_dir, "lo=10", "bo_sao=0",
            "ts\ts\tLR_format\tJPEG",
            "ts\ts\tLR_export_destinationPathPrefix\tF:/CHO_SAI",
            "ts\tn\tLR_jpeg_quality\t0.7" })
n = X.runRequest()
ktra("xuất đủ 23 ảnh", n == 23, tostring(n))
ktra("chia đúng lô 10/10/3",
     #KICH.lo == 3 and KICH.lo[1] == 10 and KICH.lo[3] == 3,
     table.concat(KICH.lo, "/"))
--[[ Thong so gui sang co san mot duong dan CU. App dat dest moi thi cai moi
     phai thang — neu khong, anh ra dung o thu muc buoi truoc va khong ai biet
     cho toi luc giao thieu. ]]
ktra("thư mục app chọn THẮNG đường dẫn có sẵn trong thông số",
     KICH.thongSoCuoi.LR_export_destinationPathPrefix == ra_dir,
     KICH.thongSoCuoi.LR_export_destinationPathPrefix)

-- đếm theo file có thật: bảo 4 ảnh không ra file
KICH.lo = {}
KICH.boQua = { IMG_0001 = true, IMG_0002 = true, IMG_0003 = true, IMG_0004 = true }
KICH.anh = anhGia(10)
datYeuCau({ "F:/Buoi/2705", "dest=" .. SAN .. "/ra2", "lo=5", "bo_sao=0",
            "ts\ts\tLR_format\tJPEG" })
n = X.runRequest()
ktra("4 ảnh không ra file -> đếm 6, không đếm 10", n == 6, tostring(n))
ktra("và 4 ảnh đó vào mục lỗi", tonumber(docTienDo().loi) == 4, docTienDo().loi)
KICH.boQua = {}

-- lọc 1 sao dùng hàm chung
KICH.anh = anhGia(10, { 1, 1, nil, nil, nil, nil, nil, nil, nil, nil })
DA_GOI_LOCSAO.n = 0
datYeuCau({ "F:/Buoi/2705", "dest=" .. SAN .. "/ra3", "bo_sao=1",
            "ts\ts\tLR_format\tJPEG" })
n = X.runRequest()
ktra("gọi hàm lọc sao CHUNG của DuyetCore, không tự viết lại",
     DA_GOI_LOCSAO.n == 1, DA_GOI_LOCSAO.n .. " lần")
ktra("ảnh 1 sao không được xuất", n == 8, tostring(n))
ktra("tiến độ nói rõ đã bỏ mấy tấm", tonumber(docTienDo().bo_sao) == 2,
     docTienDo().bo_sao)

-- cờ dừng ăn giữa hai lô
KICH.lo = {}
KICH.anh = anhGia(50)
KICH.datCoSauLo = 1
datYeuCau({ "F:/Buoi/2705", "dest=" .. SAN .. "/ra4", "lo=5", "bo_sao=0",
            "ts\ts\tLR_format\tJPEG" })
n = X.runRequest()
ktra("xin dừng thì dừng sau lô đầu", #KICH.lo == 1, #KICH.lo .. " lô đã chạy")
ktra("tiến độ ghi trạng thái “dung”", docTienDo().trang_thai == "dung",
     docTienDo().trang_thai)
ktra("dừng giữa chừng KHÔNG bị tính là 45 ảnh lỗi",
     tonumber(docTienDo().loi) == 0, docTienDo().loi)
ktra("cờ dừng được xoá sau khi dùng", not coTren(SAN .. "/jobs/" .. X.CO_DUNG))
KICH.datCoSauLo = nil

--[[ Va chieu nguoc lai: co SOT tu lan truoc thi luot moi phai chay binh
     thuong, khong duoc dung ngay. Neu khong, mot lan bam Dung se lam moi lan
     Export sau do that bai trong im lang. ]]
KICH.lo = {}
KICH.anh = anhGia(12)
local sot = io.open(SAN .. "/jobs/" .. X.CO_DUNG, "w"); sot:write("dung"); sot:close()
datYeuCau({ "F:/Buoi/2705", "dest=" .. SAN .. "/ra5", "lo=5", "bo_sao=0",
            "ts\ts\tLR_format\tJPEG" })
n = X.runRequest()
ktra("cờ dừng SÓT của lần trước không làm hỏng lượt mới",
     n == 12 and #KICH.lo == 3, tostring(n) .. " ảnh · " .. #KICH.lo .. " lô")

-- ---------------------------- 6. không dính vào đường ghi màu
local nguon = io.open(GOC .. "/XuatCore.lua", "r"):read("*a")
local than = nguon:gsub("%-%-%[%[.-%]%]", "")
ktra("XuatCore không gọi applyJob / runPending",
     not than:find("applyJob", 1, true) and not than:find("runPending", 1, true))
local ac = io.open(GOC .. "/AutoToneCore.lua", "r"):read("*a")
ktra("AutoToneCore KHÔNG require XuatCore",
     not ac:find('require%s*"XuatCore"') and not ac:find("require%s*'XuatCore'"),
     "đường ghi màu vẫn sạch")

os.execute('rm -rf "' .. SAN .. '"')
print()
if #loi > 0 then
    for _, m in ipairs(loi) do print("  [!] " .. m) end
    print(#loi .. " LOI")
    os.exit(1)
end
print("TAT CA DAT")
