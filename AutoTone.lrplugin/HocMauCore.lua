--[[ HocMauCore.lua — HỌC MÀU LIGHTROOM trên ảnh RAW THẬT của người dùng (14/10).

     User 14/10: "Với mỗi 1 ảnh cần lấy ra được vùng da mặt và pixel vùng da đó để
     can thiệp xử lý ánh sáng và màu sắc cho giống với màu da đích. Cần học về hệ màu
     và cách bù trừ màu sắc trong Curve, CG..." — chốt: chuỗi màu da MỘT LƯỢT dự đoán
     ảnh Lightroom dựng ra bằng một mô hình HỌC trên ảnh RAW thật (mo_hinh_lr.py),
     thay cho dự đoán trên JPEG nhúng (lệch da ~3.8° hue / 15% độ đậm).

     Việc của module này: với ~20 ảnh app chọn, áp TẠM từng BIẾN THỂ (Exposure ±, WB ±,
     HSL, curve kênh, Color Grading...) -> LrExportSession dựng JPEG -> TRẢ LẠI nguyên
     thông số cũ. App so từng cặp ảnh dựng (gốc -> biến thể) để học Lightroom đổi điểm
     ảnh thế nào.

     AN TOÀN — theo đúng đường của XemPresetCore (dùng lại traLai / khoiPhuc / jGiai):
       - SỔ KHÔI PHỤC (jobs/hocmau_khoiphuc.json) ghi TRƯỚC lần ghi đầu tiên của mỗi
         lượt gọi; Lightroom tắt / máy sập giữa chừng -> Init gọi khoiPhuc() lúc nạp.
       - Mỗi lượt gọi làm tối đa GIAY_MOI_LUOT giây rồi TRẢ LẠI ảnh TRƯỚC khi nhường
         vòng lặp: job áp màu / xuất / chấm sao... không bao giờ chạy trên ảnh đang
         mang thông số tạm (trả lại sau đó sẽ xoá mất việc của job). Lượt gọi sau áp
         lại biến thể còn dở từ thông số gốc.
       - Ảnh có chỉnh cục bộ (mask) / WB Custom mà Lightroom không trả Kelvin: KHÔNG
         đụng (trả lại không chắc).
       - Sau khi trả lại, dựng thêm một ảnh "sau" — app so với ảnh "goc": trả lại
         đúng thì hai ảnh như một.
     Lịch sử (History) mỗi ảnh thêm ~1 bước / biến thể — SDK không xoá được lịch sử.

     YÊU CẦU  jobs/request_hocmau.txt (JSON, app ghi):
         { "id": "...", "dest": "<thư mục ra>", "canh": 1024, "chat": 90,
           "anh":  [ { "path": "...", "nen": { "WhiteBalance": "Custom",
                                               "Temperature": 5200, "Tint": 8 } } ],
           "bien": [ { "ten": "goc", "goc": true },
                     { "ten": "nen" },
                     { "ten": "ev+", "doi": { "Exposure2012": 0.7 } },
                     { "ten": "k+",  "dat_anh": { "<path>": { "Temperature": 5600 } } },
                     { "ten": "cv_r", "dat": { "ToneCurveName2012": "Custom" },
                       "dat_anh": { "<path>": { "ToneCurvePV2012Red": [0,0,...] } } } ] }
         Mỗi biến thể (trừ "goc" = dựng nguyên trạng): mọi khoá MỌI biến thể đụng tới
         về giá trị GỐC -> "nen" của ảnh (WB Custom ở đúng Kelvin đang thấy) -> "doi"
         (cộng vào gốc) -> "dat" -> "dat_anh" của ảnh.
     DỪNG     jobs/request_hocmau_dung.txt
     TIẾN ĐỘ  jobs/hocmau_tiendo.txt  key=value: id trang_thai xong tong anh_xong anh_tong
              thieu bo lech dest bien thong_bao
     BẢNG     jobs/hocmau_anh.tsv     <biến thể>\t<ảnh gốc>\t<jpg>

     Nạp riêng như các module khác; không pcall quanh lời gọi SDK — dùng Core.try. ]]

local LrApplication   = import "LrApplication"
local LrDate          = import "LrDate"
local LrExportSession = import "LrExportSession"
local LrFileUtils     = import "LrFileUtils"
local LrPathUtils     = import "LrPathUtils"
local LrTasks         = import "LrTasks"

local Core = require "AutoToneCore"
local XP = require "XemPresetCore"
local okDuyet, Duyet = pcall(require, "DuyetCore")
if not okDuyet then Duyet = nil end

local M = {}
M.YEU_CAU = "request_hocmau.txt"
M.CO_DUNG = "request_hocmau_dung.txt"
M.TIEN_DO = "hocmau_tiendo.txt"
M.BANG    = "hocmau_anh.tsv"
M.SO_KP   = "hocmau_khoiphuc.json"
M.LO      = 4             -- ảnh mỗi lô: cả lô cùng biến thể, một lần dựng
M.GIAY_MOI_LUOT = 20
M.CANH    = 1024
M.CHAT    = 0.9
M.dang    = nil

--  WB về "nen" của ảnh (Custom ở Kelvin đang thấy), không về gốc: ảnh As Shot không
--  trả lại được bằng applyDevelopSettings (bẫy NEXUS — xem XemPresetCore)
local KHOA_WB = { WhiteBalance = true, Temperature = true, Tint = true }

--  việc khác đang chờ -> trả lại ảnh rồi nhường vòng lặp
local VIEC_KHAC = { "request_xuatanh.txt", "request_export.txt", "request_duyet.txt",
                    "request_chup.txt", "request_xempreset.txt", "request_sao.txt",
                    "request_denoise.txt", "request_do_curve.txt", "request_xem_lr.txt" }

local function dir() return Core.jobDir() end
local function f(ten) return LrPathUtils.child(dir(), ten) end
local function sach(s) return (string.gsub(tostring(s or ""), "[\t\r\n]", " ")) end

local function ghiFile(path, text)
    local tmp = path .. ".part"
    local fh = io.open(tmp, "wb")
    if not fh then return false end
    fh:write(text)
    fh:close()
    Core.try("hocMauGhiFile", function()
        if LrFileUtils.exists(path) then LrFileUtils.delete(path) end
        LrFileUtils.move(tmp, path)
        return true
    end)
    return true
end

local function docFile(path)
    local fh = io.open(path, "rb")
    if not fh then return nil end
    local s = fh:read("*a")
    fh:close()
    return s
end

--[[ Lightroom tắt / máy sập giữa một lượt: trả lại theo sổ. Init gọi MỘT lần lúc nạp. ]]
function M.khoiPhuc()
    return XP.khoiPhuc(M.SO_KP, "hocmau")
end

-- --------------------------------------------------------------- tiến độ / bảng
local function ghiTienDo(d, trangThai, thongBao)
    local t = {
        "id=" .. tostring(d and d.id or ""),
        "trang_thai=" .. tostring(trangThai),
        "xong=" .. tostring(d and d.xong or 0),
        "tong=" .. tostring(d and d.tong or 0),
        "anh_xong=" .. tostring(d and d.anhXong or 0),
        "anh_tong=" .. tostring(d and #(d.anh or {}) or 0),
        "thieu=" .. tostring(d and d.thieu or 0),
        "bo=" .. tostring(d and d.bo or 0),
        "lech=" .. tostring(d and d.lech or 0),
        "dest=" .. tostring(d and d.dest or ""),
        "bien=" .. sach(d and d.bienDang or ""),
        "thong_bao=" .. sach(thongBao or ""),
    }
    ghiFile(f(M.TIEN_DO), table.concat(t, "\n") .. "\n")
end

local function ghiBang(d)
    local t = { "bien\tpath\tjpg" }
    for _, c in ipairs(d.cap) do t[#t + 1] = c.ten .. "\t" .. c.src .. "\t" .. c.jpg end
    ghiFile(f(M.BANG), table.concat(t, "\n") .. "\n")
end

-- --------------------------------------------------------------- sổ khôi phục
local function ghiSo(lo)
    local t = {}
    for _, x in ipairs(lo) do t[#t + 1] = { path = x.path, goc = x.goc } end
    return ghiFile(f(M.SO_KP), XP.jMa(t))
end

local function xoaSo()
    Core.try("hocMauXoaSo", function()
        if LrFileUtils.exists(f(M.SO_KP)) then LrFileUtils.delete(f(M.SO_KP)) end
        return true
    end)
end

-- --------------------------------------------------------------- biến thể
--[[ Thông số của một biến thể cho một ảnh (xem đầu file). ]]
function M.thongSoBien(x, b, cham)
    local st = {}
    for k in pairs(cham) do
        if not KHOA_WB[k] and x.goc[k] ~= nil then st[k] = x.goc[k] end
    end
    for k, v in pairs(x.nen or {}) do st[k] = v end
    for k, v in pairs(b.doi or {}) do st[k] = (tonumber(x.goc[k]) or 0) + v end
    for k, v in pairs(b.dat or {}) do st[k] = v end
    local rieng = type(b.dat_anh) == "table" and b.dat_anh[x.path] or nil
    for k, v in pairs(rieng or {}) do st[k] = v end
    return st
end

local function apBien(d, b)
    local _, err = Core.try("hocMauAp", function()
        d.catalog:withWriteAccessDo("AutoTone: học màu (tạm)", function()
            for _, x in ipairs(d.lo) do
                x.photo:applyDevelopSettings(M.thongSoBien(x, b, d.cham), "AutoTone: học màu")
            end
        end, { timeout = 60 })
        return true
    end)
    return err == nil, err
end

local function xuatBien(d, ten)
    local dest = LrPathUtils.child(d.dest, ten)
    if not LrFileUtils.exists(dest) then LrFileUtils.createAllDirectories(dest) end
    local photos = {}
    for i, x in ipairs(d.lo) do photos[i] = x.photo end
    local thongSo
    if Duyet and Duyet.thongSo then
        thongSo = Duyet.thongSo(dest, d.canh, d.chat)
    else
        thongSo = { LR_export_destinationType = "specificFolder",
                    LR_export_destinationPathPrefix = dest, LR_export_useSubfolder = false,
                    LR_format = "JPEG", LR_jpeg_quality = d.chat, LR_collisionHandling = "overwrite",
                    LR_export_colorSpace = "sRGB", LR_size_doConstrain = true,
                    LR_size_maxWidth = d.canh, LR_size_maxHeight = d.canh, LR_size_resizeType = "wh",
                    LR_size_units = "pixels", LR_size_resolution = 72,
                    LR_outputSharpeningOn = false, LR_reimportExportedPhoto = false,
                    LR_renamingTokensOn = false, LR_tokens = "{{image_name}}",
                    LR_extensionCase = "lowercase", LR_export_postProcessing = "doNothing" }
    end
    local ra = {}
    Core.try("hocMauDung", function()
        local s = LrExportSession({ photosToExport = photos, exportSettings = thongSo })
        for _, r in s:renditions() do
            local ok, p = r:waitForRender()
            if ok and p then ra[#ra + 1] = p end
        end
        return true
    end)
    for _, x in ipairs(d.lo) do
        local jpg = XP.jpgCua(dest, x.path, ra)
        if jpg then d.cap[#d.cap + 1] = { ten = ten, src = x.path, jpg = jpg } end
    end
    d.xong = d.xong + #d.lo
end

local function traLo(d)
    local lech = XP.traLai(d.catalog, d.lo, true)
    d.lech = d.lech + (lech or 0)
    xoaSo()
    d.daGhiSo = false
end

-- --------------------------------------------------------------- lô
local function napLo(d)
    local lo = {}
    while #lo < M.LO and d.iAnh <= #d.anh do
        local a = d.anh[d.iAnh]
        d.iAnh = d.iAnh + 1
        local photo = a.path and Core.try("hocMauTim", function() return d.tra(a.path) end)
        local goc = photo and Core.try("hocMauGoc", function() return photo:getDevelopSettings() end)
        if not photo or type(goc) ~= "table" then
            d.thieu = d.thieu + 1
            Core.log("hocmau: khong thay anh " .. tostring(a.path))
        elseif XP.coCucBo(goc) then
            d.bo = d.bo + 1
            Core.log("hocmau: bo qua (co chinh cuc bo) " .. tostring(a.path))
        elseif goc.WhiteBalance == "Custom" and tonumber(goc.Temperature) == nil then
            d.bo = d.bo + 1
            Core.log("hocmau: bo qua (WB Custom khong doc duoc Kelvin de tra lai) " .. tostring(a.path))
        else
            lo[#lo + 1] = { path = a.path, photo = photo, goc = goc, nen = a.nen }
        end
    end
    return lo
end

local function viecKhacCho()
    for _, ten in ipairs(VIEC_KHAC) do
        if LrFileUtils.exists(f(ten)) then return true end
    end
    local co = false
    Core.try("hocMauTimJob", function()
        for p in LrFileUtils.files(dir()) do
            local ten = LrPathUtils.leafName(p) or ""
            if string.match(ten, "^apply_.*%.tsv$") then co = true break end
        end
        return true
    end)
    return co
end

-- --------------------------------------------------------------- lượt
local function ketThuc(trangThai, thongBao)
    local d = M.dang
    if not d then return end
    if d.lo and d.daGhiSo then traLo(d) end            -- không bao giờ để ảnh mang thông số tạm
    ghiBang(d)
    local giay = LrDate.currentTime() - (d.t0 or LrDate.currentTime())
    ghiTienDo(d, trangThai, thongBao or string.format("%.0f giay", giay))
    Core.log(string.format("hocmau: %s %d/%d anh dung, %d/%d anh, thieu %d, bo %d, lech %d, %.0f giay",
                           trangThai, d.xong, d.tong, d.anhXong, #d.anh, d.thieu, d.bo, d.lech, giay))
    M.dang = nil
end

function M.batDau(r)
    local d = { id = tostring(r.id or ""), dest = tostring(r.dest or ""),
                canh = tonumber(r.canh) or M.CANH, chat = tonumber(r.chat) or M.CHAT,
                anh = type(r.anh) == "table" and r.anh or {},
                bien = type(r.bien) == "table" and r.bien or {},
                cap = {}, xong = 0, anhXong = 0, thieu = 0, bo = 0, lech = 0,
                iAnh = 1, iBien = 1, cham = {} }
    if d.chat > 1 then d.chat = d.chat / 100 end
    if d.dest == "" or #d.anh == 0 or #d.bien == 0 then
        ghiTienDo(d, "loi", "yeu cau thieu dest / anh / bien")
        return false
    end
    --  khoá MỌI biến thể đụng tới: mỗi biến thể đưa chúng về gốc trước
    for _, b in ipairs(d.bien) do
        for k in pairs(b.doi or {}) do d.cham[k] = true end
        for k in pairs(b.dat or {}) do d.cham[k] = true end
        for _, rieng in pairs(type(b.dat_anh) == "table" and b.dat_anh or {}) do
            for k in pairs(rieng) do d.cham[k] = true end
        end
    end
    d.tong = #d.anh * (#d.bien + 1)
    if not LrFileUtils.exists(d.dest) then LrFileUtils.createAllDirectories(d.dest) end
    d.catalog = LrApplication.activeCatalog()
    if Duyet and Duyet.dungBangTra then
        d.tra = Duyet.dungBangTra(d.catalog)
    else
        d.tra = function(p) return d.catalog:findPhotoByPath(p) end
    end
    d.t0 = LrDate.currentTime()
    M.dang = d
    ghiTienDo(d, "dang_chay", "bat dau")
    Core.log(string.format("hocmau: bat dau %d anh x %d bien the -> %s", #d.anh, #d.bien, d.dest))
    return true
end

--[[ Một lượt gọi: làm tới GIAY_MOI_LUOT giây / gặp việc khác / bị dừng, rồi TRẢ LẠI ảnh
     của lô đang dở. Trả về số ảnh dựng được trong lượt. ]]
function M.chay()
    local d = M.dang
    if not d then return 0 end
    local t0 = LrDate.currentTime()
    local truoc = d.xong
    while M.dang do
        if not d.lo then
            d.lo = napLo(d)
            d.iBien = 1
            if #d.lo == 0 then
                d.lo = nil
                if d.iAnh > #d.anh then
                    ketThuc("xong")
                    return d.xong - truoc
                end
            end
        end
        if d.lo then
            local nhuong = false
            while d.iBien <= #d.bien do
                local b = d.bien[d.iBien]
                d.bienDang = tostring(b.ten)
                if not b.goc then
                    if not d.daGhiSo then
                        ghiSo(d.lo)                  -- TRƯỚC lần ghi đầu tiên
                        d.daGhiSo = true
                    end
                    local ok, err = apBien(d, b)
                    if not ok then
                        Core.log("hocmau: LOI ap bien the " .. d.bienDang .. " -> " .. tostring(err))
                        ketThuc("loi", "loi ap bien the " .. d.bienDang .. ": " .. tostring(err))
                        return d.xong - truoc
                    end
                end
                xuatBien(d, tostring(b.ten))
                d.iBien = d.iBien + 1
                ghiBang(d)
                ghiTienDo(d, "dang_chay", "")
                LrTasks.yield()
                if LrDate.currentTime() - t0 > M.GIAY_MOI_LUOT or viecKhacCho()
                        or LrFileUtils.exists(f(M.CO_DUNG)) or LrFileUtils.exists(f(M.YEU_CAU)) then
                    nhuong = true
                    break
                end
            end
            --  TRẢ LẠI lô — luôn, trước khi nhường hay sang lô sau
            if d.daGhiSo then traLo(d) end
            if d.iBien > #d.bien then
                d.bienDang = "sau"
                xuatBien(d, "sau")                   -- dựng SAU khi trả lại: app so với "goc"
                d.anhXong = d.anhXong + #d.lo
                d.lo = nil
                ghiBang(d)
                ghiTienDo(d, "dang_chay", "")
            end
            if nhuong then return d.xong - truoc end
        end
    end
    return d.xong - truoc
end

function M.runRequest()
    local req = f(M.YEU_CAU)
    if LrFileUtils.exists(req) then
        local claimed = Core.claim(req)
        if claimed then
            local s = docFile(claimed)
            Core.try("hocMauBoYeuCau", function() LrFileUtils.delete(claimed) return true end)
            if M.dang then ketThuc("thay", "co yeu cau moi") end
            s = s and string.gsub(s, "^\239\187\191", "")
            local ok, r = pcall(XP.jGiai, s or "")
            if ok and type(r) == "table" then
                M.batDau(r)
            else
                ghiTienDo(nil, "loi", "yeu cau hong: " .. tostring(r))
                Core.log("hocmau: yeu cau hong -> " .. tostring(r))
            end
        end
    end
    if not M.dang then return 0 end
    if LrFileUtils.exists(f(M.CO_DUNG)) then
        Core.try("hocMauBoCoDung", function() LrFileUtils.delete(f(M.CO_DUNG)) return true end)
        ketThuc("dung", "nguoi dung dung")
        return 0
    end
    return M.chay()
end

return M
