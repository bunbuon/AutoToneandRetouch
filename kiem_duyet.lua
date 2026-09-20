--[[ kiem_duyet.lua — kiểm DuyetCore.lua bằng SDK giả lập.

     Nạp CHÍNH file DuyetCore.lua thật (không chép lại đoạn nào), cắm một bộ SDK
     giả có hệ thống file THẬT bên dưới, rồi kiểm những chỗ dễ sai nhất:

       1. Bảng exportSettings có đúng khoá lấy từ .lrtemplate của Lightroom.
          Sai exportServiceProvider hoặc thiếu khoá kích thước là export ra
          rỗng / ảnh 1 điểm ảnh mà KHÔNG báo lỗi gì.
       2. Chia lô đúng, và bảng ánh xạ được ghi SAU MỖI LÔ (để app soát được
          ngay khi lô đầu xong).
       3. renditions() hỏng thì phải lùi về suy tên file, không mất cả lượt.
       4. Ảnh không ra file thì đếm vào 'loi', tuyệt đối không đưa vào bảng.
       5. Đường ghi màu (AutoToneCore) không dính dáng gì tới DuyetCore.

     Chạy:  lua5.1 kiem_duyet.lua [thu-muc-plugin]
]]

local GOC = (...) or arg[1] or "AutoTone.lrplugin"
local TMP = os.getenv("TMPDIR") or "/tmp"
local SAN = TMP .. "/kiem_duyet_" .. tostring(os.time())
os.execute('mkdir -p "' .. SAN .. '/jobs" "' .. SAN .. '/anh"')

-- ---------------------------------------------------------------- giả lập SDK
--[[ os.execute tra ve khac nhau giua hai ban Lua: 5.1 tra ve ma thoat (so),
     5.4 tra ve true/nil + "exit" + ma. Nhan ca hai de bai kiem chay duoc bang
     lua5.1 (dung ban Lightroom dung) lan lua5.4. ]]
local function coTren(p)
    local a, _, ma = os.execute('test -e "' .. p .. '"')
    if type(a) == "number" then return a == 0 end
    return a == true and (ma == nil or ma == 0)
end

local LrPathUtils = {
    child = function(a, b) return tostring(a) .. "/" .. tostring(b) end,
    leafName = function(p) return (tostring(p):match("[^/\\]+$")) end,
    parent = function(p) return (tostring(p):match("^(.*)[/\\][^/\\]*$")) end,
    removeExtension = function(p)
        local n = tostring(p)
        return (n:gsub("%.[^.]*$", ""))
    end,
}

local LrFileUtils = {
    exists = function(p) return coTren(p) end,
    delete = function(p) os.remove(p) end,
    move = function(a, b) os.remove(b); os.rename(a, b) end,
    createAllDirectories = function(p) os.execute('mkdir -p "' .. p .. '"') end,
}

local LrTasks = { yield = function() end, sleep = function() end }

-- Điều khiển hành vi của LrExportSession giả từ bài kiểm
local KICH = { renditionsHong = false, boQua = {}, lanGoi = 0, thongSoCuoi = nil }

local LrExportSession = function(params)
    KICH.lanGoi = KICH.lanGoi + 1
    KICH.thongSoCuoi = params.exportSettings
    local ds = params.photosToExport
    local ra = {}
    return {
        doExportOnCurrentTask = function()
            local dest = params.exportSettings.LR_export_destinationPathPrefix
            os.execute('mkdir -p "' .. dest .. '"')
            for i = 1, #ds do
                local src = ds[i].__path
                local ten = LrPathUtils.removeExtension(LrPathUtils.leafName(src))
                if not KICH.boQua[ten] then
                    local jpg = dest .. "/" .. ten .. ".jpg"
                    local f = io.open(jpg, "w"); f:write("JPEG"); f:close()
                    ra[#ra + 1] = jpg
                end
            end
        end,
        renditions = function()
            if KICH.renditionsHong then error("gia vo renditions hong") end
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

-- Core giả: chỉ những hàm DuyetCore thật sự gọi tới
local NHAT_KY = {}
package.loaded["AutoToneCore"] = {
    jobDir  = function() return SAN .. "/jobs" end,
    logPath = function() return SAN .. "/jobs/plugin.log" end,
    log     = function(m) NHAT_KY[#NHAT_KY + 1] = tostring(m) end,
    try     = function(_, fn)
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
    buildPathIndex = function() return {}, 0, 0 end,
}

-- ------------------------------------------------------- nạp DuyetCore.lua thật
local duong = GOC .. "/DuyetCore.lua"
local nap = assert(loadfile(duong), "khong doc duoc " .. duong)
local Duyet = nap()

-- ------------------------------------------------------------------- bài kiểm
local loi = {}
local function ktra(ten, dieu, mo)
    if dieu then print(string.format("  %-46s %s", ten, mo or "dat"))
    else loi[#loi + 1] = ten .. ": " .. tostring(mo) end
end

local function anhGia(n, tien)
    local ds = {}
    for i = 1, n do
        local p = SAN .. "/anh/" .. string.format("%s%03d.ARW", tien or "IMG_", i)
        ds[i] = { __path = p,
                  getRawMetadata = function(self, k)
                      if k == "path" then return self.__path end
                      return nil
                  end }
    end
    return ds
end

local function docTSV(p)
    local out, fh = {}, io.open(p, "r")
    if not fh then return out end
    local dau = true
    for line in fh:lines() do
        if dau then dau = false
        elseif line ~= "" then
            local a, b = line:match("^([^\t]*)\t(.*)$")
            out[#out + 1] = { src = a, jpg = b }
        end
    end
    fh:close()
    return out
end

-- 1. Bảng thông số: đúng khoá lấy từ .lrtemplate thật của Lightroom
do
    local t = Duyet.thongSo("/ra", 1600, 0.7)
    ktra("exportServiceProvider = com.adobe.ag.export.file",
         t.LR_exportServiceProvider == "com.adobe.ag.export.file",
         tostring(t.LR_exportServiceProvider) ..
         " (sai khoa nay thi export khong ra file nao)")
    ktra("co du khoa kich thuoc",
         t.LR_size_doConstrain == true and t.LR_size_maxWidth == 1600
         and t.LR_size_maxHeight == 1600 and t.LR_size_units == "pixels"
         and t.LR_size_resizeType == "wh",
         "thieu la Lightroom xuat anh 1 diem anh, khong bao loi")
    ktra("khong hoi khi trung ten, khong mo Explorer",
         t.LR_collisionHandling == "overwrite"
         and t.LR_export_postProcessing == "doNothing",
         t.LR_collisionHandling .. " / " .. t.LR_export_postProcessing)
    ktra("khong dua anh duyet nguoc vao catalog",
         t.LR_reimportExportedPhoto == false, "reimport = false")
    ktra("ten file doan truoc duoc",
         t.LR_tokens == "{{image_name}}" and t.LR_extensionCase == "lowercase"
         and t.LR_renamingTokensOn == false,
         "tokens = {{image_name}} + lowercase")
    ktra("chat luong dung thang 0..1",
         t.LR_jpeg_quality == 0.7, tostring(t.LR_jpeg_quality))
end

-- 2. Chạy đủ: chia lô, bảng ánh xạ, tiến trình
do
    KICH.renditionsHong, KICH.boQua, KICH.lanGoi = false, {}, 0
    local dest = SAN .. "/ra1"
    local moc = {}
    local res = Duyet.xuatDuyet(anhGia(57), dest, { lo = 25 },
                                function(d, t) moc[#moc + 1] = d .. "/" .. t end)
    ktra("57 anh, lo 25 -> 3 phien export",
         KICH.lanGoi == 3, "lanGoi = " .. KICH.lanGoi)
    ktra("bao tien do sau moi lo",
         #moc == 3 and moc[3] == "57/57", table.concat(moc, " "))
    ktra("ra du 57 anh, khong loi", #res.cap == 57 and res.loi == 0,
         string.format("cap=%d loi=%d", #res.cap, res.loi))
    local bang = docTSV(SAN .. "/jobs/duyet_anh.tsv")
    ktra("bang anh xa co du dong", #bang == 57, "#bang = " .. #bang)
    ktra("bang anh xa tro dung file co that",
         bang[1] and coTren(bang[1].jpg) and bang[1].jpg:match("IMG_001%.jpg$") ~= nil,
         bang[1] and bang[1].jpg or "(rong)")
end

-- 2b. Lô MẶC ĐỊNH cũng phải nhỏ. Nếu M.LO bị đẩy lên trời thì cả buổi nằm
--     trong một phiên export duy nhất: không có tiến trình nào để báo, và ảnh
--     lô đầu không tới tay người soát trước khi mọi thứ xong.
do
    KICH.renditionsHong, KICH.boQua, KICH.lanGoi = false, {}, 0
    ktra("lo mac dinh nam trong khoang hop ly",
         type(Duyet.LO) == "number" and Duyet.LO >= 5 and Duyet.LO <= 100,
         "M.LO = " .. tostring(Duyet.LO))
    Duyet.xuatDuyet(anhGia(60, "E_"), SAN .. "/ra1b", {})   -- khong truyen lo
    ktra("khong truyen lo -> van chia nhieu phien",
         KICH.lanGoi >= 2,
         "lanGoi = " .. KICH.lanGoi .. " (mot phien duy nhat = khong co tien do)")
end

-- 3. renditions() hỏng -> phải lùi về suy tên, KHÔNG mất lượt
do
    KICH.renditionsHong, KICH.boQua, KICH.lanGoi = true, {}, 0
    local res = Duyet.xuatDuyet(anhGia(10, "B_"), SAN .. "/ra2", { lo = 4 })
    ktra("renditions() hong van ra du anh",
         #res.cap == 10 and res.loi == 0,
         string.format("cap=%d loi=%d", #res.cap, res.loi))
    KICH.renditionsHong = false
end

-- 4. Ảnh không render được -> vào 'loi', tuyệt đối không vào bảng
do
    KICH.boQua = { C_003 = true, C_007 = true }
    local res = Duyet.xuatDuyet(anhGia(10, "C_"), SAN .. "/ra3", { lo = 10 })
    ktra("anh khong ra file -> dem loi",
         #res.cap == 8 and res.loi == 2,
         string.format("cap=%d loi=%d", #res.cap, res.loi))
    local co = false
    for _, r in ipairs(res.cap) do
        if r.src:match("C_003") then co = true end
    end
    ktra("khong bao gio dua anh thieu vao bang", not co,
         "bang chi chua anh co file that")
    KICH.boQua = {}
end

-- 4b. Xin dừng giữa chừng: phải dừng SAU LÔ đang chạy, giữ nguyên phần đã làm
do
    KICH.renditionsHong, KICH.boQua, KICH.lanGoi = false, {}, 0
    local dest = SAN .. "/ra_dung"
    -- đặt cờ dừng NGAY, để nó có hiệu lực từ sau lô đầu tiên
    local f = io.open(SAN .. "/jobs/request_duyet_dung.txt", "w")
    f:write("dung\n"); f:close()

    local res = Duyet.xuatDuyet(anhGia(60, "F_"), dest, { lo = 10 })
    ktra("xin dung -> dung sau lo dang chay",
         res.da_dung == true and #res.cap == 10 and KICH.lanGoi == 1,
         string.format("da lam %d anh, %d phien export", #res.cap, KICH.lanGoi))
    --[[ Anh chua toi luot KHONG phai la loi. Dem chung vao loi thi dung giua
         chung 60 anh se bao "50 anh khong ra file" — bao dong gia. ]]
    ktra("anh chua toi luot khong bi dem la loi",
         res.loi == 0, "loi = " .. tostring(res.loi))
    ktra("co dung duoc xoa sau khi dung",
         not coTren(SAN .. "/jobs/request_duyet_dung.txt"),
         "khong con sot lai lam luot sau dung ngay")

    -- lượt tiếp theo (không có cờ) phải chạy hết
    KICH.lanGoi = 0
    local r2 = Duyet.xuatDuyet(anhGia(30, "G_"), SAN .. "/ra_dung2", { lo = 10 })
    ktra("luot sau khong bi dung oan",
         r2.da_dung == false and #r2.cap == 30,
         string.format("%d anh, %d phien", #r2.cap, KICH.lanGoi))
end

-- 5. Danh sách rỗng
do
    local res = Duyet.xuatDuyet({}, SAN .. "/ra4", {})
    ktra("danh sach rong", #res.cap == 0 and res.loi == 0, "khong lam gi")
end

-- 6. runRequest: đọc yêu cầu, giới hạn số ảnh, ghi tiến trình "xong"
do
    KICH.anh = anhGia(30, "D_")
    local fh = io.open(SAN .. "/jobs/request_duyet.txt", "w")
    fh:write(SAN .. "/anh\n")
    fh:write("dest=" .. SAN .. "/ra5\n")
    fh:write("canh=1200\nchat=70\nlo=5\ngioi_han=12\n")
    fh:close()

    local n = Duyet.runRequest()
    ktra("runRequest ton trong gioi_han", n == 12, "n = " .. tostring(n))
    ktra("chat=70 doi thanh 0.7 cho SDK",
         KICH.thongSoCuoi and KICH.thongSoCuoi.LR_jpeg_quality == 0.7,
         tostring(KICH.thongSoCuoi and KICH.thongSoCuoi.LR_jpeg_quality))
    ktra("canh tu yeu cau duoc dung",
         KICH.thongSoCuoi and KICH.thongSoCuoi.LR_size_maxWidth == 1200,
         tostring(KICH.thongSoCuoi and KICH.thongSoCuoi.LR_size_maxWidth))

    local td, tt = {}, io.open(SAN .. "/jobs/duyet_tiendo.txt", "r")
    if tt then
        for line in tt:lines() do
            local k, v = line:match("^([%w_]+)=(.*)$")
            if k then td[k] = v end
        end
        tt:close()
    end
    ktra("tien do bao xong", td.trang_thai == "xong" and td.xong == "12",
         string.format("trang_thai=%s xong=%s", tostring(td.trang_thai),
                       tostring(td.xong)))
    ktra("yeu cau da duoc xoa sau khi chay",
         not coTren(SAN .. "/jobs/request_duyet.txt"),
         "khong chay lai vong sau")
end

-- 7. Không có yêu cầu -> không làm gì, không lỗi
do
    local n = Duyet.runRequest()
    ktra("khong co yeu cau -> tra ve 0", n == 0, "n = " .. tostring(n))
end

-- 8. CANH: đường ghi màu phải sạch, không dính DuyetCore
do
    local fh = io.open(GOC .. "/AutoToneCore.lua", "r")
    local nguon = fh:read("*a"); fh:close()
    ktra("AutoToneCore khong require DuyetCore",
         not nguon:find('require "DuyetCore"', 1, true)
         and not nguon:find("require 'DuyetCore'", 1, true),
         "duong ap thong so khong phu thuoc duong duyet")

    local a = nguon:find("function M.applyJob", 1, true)
    local b = nguon:find("\nfunction M%.", a + 10)
    local than = nguon:sub(a, b or #nguon)
    ktra("applyJob khong goi gi cua DuyetCore",
         not than:find("Duyet", 1, true),
         "bai hoc 6/9: viec phu hong khong duoc keo sap viec ghi mau")
end

print()
if #loi == 0 then
    print("TAT CA DAT")
    os.execute('rm -rf "' .. SAN .. '"')
    os.exit(0)
else
    for _, m in ipairs(loi) do print("  [!] " .. m) end
    print(#loi .. " LOI  (san kiem giu lai o " .. SAN .. ")")
    os.exit(1)
end
