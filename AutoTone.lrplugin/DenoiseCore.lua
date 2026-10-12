--[[ DENOISE ẢNH ISO CAO — 13/10.

     User 13/10: "Thêm option Denoise ảnh, tính năng có sẵn trong Lightroom.
     Người dùng được phép chọn ngưỡng ISO để bật tính năng Denoise này".

     Lightroom Classic 14.4 trở lên ghi Denoise thẳng vào ảnh (không tạo DNG
     -Enhanced-NR nữa), và SDK có LrDevelopController.setEnhance("denoise", true)
     / toggleEnhance("denoise") — đọc ra từ Develop.lrmodule của Lightroom 15.5:
     chỉ chạy khi module Develop đang mở, trên ẢNH ĐANG CHỌN. Nên plugin mở
     Develop, chọn lần lượt từng ảnh rồi bật.

     YÊU CẦU RIÊNG, KHÔNG NẰM TRONG applyJob: chưa thử được trên Lightroom thật
     (xem bài học ở cuối applyJob trong AutoToneCore.lua — tính năng chưa thử thì
     không đặt vào đường áp thông số). App gửi jobs/request_denoise.txt SAU khi job
     áp đã xong:
         #ma=<mã lượt>
         <đường dẫn ảnh>      (mỗi dòng một ảnh)
     Plugin ghi jobs/denoise_tien_do.txt (ma, xong, tong) trong lúc chạy và
     jobs/ketqua_denoise.txt (ma, tong, bat, da_co, khong_ho_tro, khong_thay, loi,
     ly_do) khi xong.

     KHÔNG pcall quanh lời gọi SDK — dùng Core.try (xem đầu AutoToneCore.lua). ]]

local LrApplication = import "LrApplication"
local LrFileUtils   = import "LrFileUtils"
local LrPathUtils   = import "LrPathUtils"
local LrTasks       = import "LrTasks"

local Core = require "AutoToneCore"

local okDC, LrDevelopController = pcall(import, "LrDevelopController")
if not okDC then LrDevelopController = nil end
local okAV, LrApplicationView = pcall(import, "LrApplicationView")
if not okAV then LrApplicationView = nil end

local M = {}

M.YEU_CAU = "request_denoise.txt"
M.TIEN_DO = "denoise_tien_do.txt"
M.KET_QUA = "ketqua_denoise.txt"

--[[ Hàm THUẦN: (mã, danh sách đường dẫn) từ nội dung file yêu cầu. ]]
function M.phanTich(chu)
    local ma, ds = "", {}
    for dong in string.gmatch(chu or "", "[^\r\n]+") do
        local m = string.match(dong, "^#ma=(.*)$")
        if m then
            ma = m
        elseif string.sub(dong, 1, 1) ~= "#" then
            local p = string.gsub(dong, "^%s*(.-)%s*$", "%1")
            if p ~= "" then ds[#ds + 1] = p end
        end
    end
    return ma, ds
end

--[[ Lightroom này có bật Denoise qua SDK được không. ]]
function M.coHam(dc)
    dc = dc or LrDevelopController
    return type(dc) == "table" and (type(dc.setEnhance) == "function"
                                    or type(dc.toggleEnhance) == "function")
end

--[[ Ảnh đang chọn đã bật Denoise chưa — đọc bảng trạng thái của panel Enhance.
     Không rõ kiểu giá trị (true / "on" / số) nên chấp nhận cả ba. ]]
function M.dangBat(st)
    if type(st) ~= "table" then return false end
    local v = st.denoiseState
    return v == true or v == 1 or v == "on" or v == "On" or v == "applied"
end

local function ghiKv(ten, t, thuTu)
    local dir = Core.jobDir()
    local dest = LrPathUtils.child(dir, ten)
    local tmp = dest .. ".part"
    local fh = io.open(tmp, "w")
    if not fh then return end
    for _, k in ipairs(thuTu) do
        if t[k] ~= nil then fh:write(k .. "=" .. tostring(t[k]) .. "\n") end
    end
    fh:close()
    Core.try("denoiseGhi", function()
        LrFileUtils.delete(dest)
        LrFileUtils.move(tmp, dest)
    end)
end

local function tienDo(ma, xong, tong)
    ghiKv(M.TIEN_DO, { ma = ma, xong = xong, tong = tong }, { "ma", "xong", "tong" })
end

local function ketQua(t)
    ghiKv(M.KET_QUA, t, { "ma", "tong", "bat", "da_co", "khong_ho_tro", "khong_thay",
                           "loi", "ly_do", "khi" })
end

local function idCua(photo)
    if not photo then return nil end
    return photo.localIdentifier
end

--[[ Chọn một ảnh và đợi Develop nhận nó làm ảnh đang xem (tối đa ~5 giây). ]]
local function chonAnh(catalog, photo)
    Core.try("denoiseChon", function() catalog:setSelectedPhotos(photo, { photo }) end)
    local muon = idCua(photo)
    for _ = 1, 25 do
        LrTasks.sleep(0.2)
        local t = catalog:getTargetPhoto()
        if t and idCua(t) == muon then
            LrTasks.sleep(0.4)          -- để panel Enhance cập nhật theo ảnh mới
            return true
        end
    end
    return false
end

function M.runRequest()
    local dir = Core.jobDir()
    local req = LrPathUtils.child(dir, M.YEU_CAU)
    if not LrFileUtils.exists(req) then return 0 end
    local claimed = Core.claim(req)
    if not claimed then return 0 end
    local fh = io.open(claimed, "r")
    local chu = fh and fh:read("*a") or ""
    if fh then fh:close() end
    Core.try("denoiseXoaYc", function() LrFileUtils.delete(claimed) end)
    local ma, ds = M.phanTich(chu)
    local kq = { ma = ma, tong = #ds, bat = 0, da_co = 0, khong_ho_tro = 0,
                 khong_thay = 0, loi = 0 }
    if #ds == 0 then
        kq.khi = os.date("%Y-%m-%d %H:%M:%S")
        ketQua(kq)
        return 0
    end
    if not M.coHam() or not LrApplicationView then
        kq.ly_do = "lightroom-chua-ho-tro"
        kq.khi = os.date("%Y-%m-%d %H:%M:%S")
        ketQua(kq)
        Core.log("denoise: Lightroom nay khong co LrDevelopController.setEnhance (can 14.4+)")
        return 0
    end
    local catalog = LrApplication.activeCatalog()
    local photos = {}
    for i = 1, #ds do
        local p = Core.try("denoiseTim", function() return catalog:findPhotoByPath(ds[i]) end)
        if p then photos[#photos + 1] = p else kq.khong_thay = kq.khong_thay + 1 end
        if i % 200 == 0 then LrTasks.yield() end
    end
    Core.log(string.format("denoise: %d anh (%d khong thay trong catalog)", #photos,
                           kq.khong_thay))
    -- Nhớ module + vùng chọn để trả lại khi xong
    local moduleCu = Core.try("denoiseModule", function()
        return LrApplicationView.getCurrentModuleName()
    end)
    local chonCu = Core.try("denoiseChonCu", function() return catalog:getTargetPhotos() end)
    Core.try("denoiseVaoDevelop", function() LrApplicationView.switchToModule("develop") end)
    LrTasks.sleep(1.5)
    tienDo(ma, 0, #photos)
    for i = 1, #photos do
        local photo = photos[i]
        if not chonAnh(catalog, photo) then
            kq.loi = kq.loi + 1
        else
            local st = Core.try("denoiseTrangThai", function()
                if type(LrDevelopController.getEnhancePanelState) == "function" then
                    return LrDevelopController.getEnhancePanelState()
                end
                return nil
            end)
            if type(st) == "table" and st.denoiseEnabled == false then
                kq.khong_ho_tro = kq.khong_ho_tro + 1
            elseif M.dangBat(st) then
                kq.da_co = kq.da_co + 1
            else
                local _, err = Core.try("denoiseBat", function()
                    if type(LrDevelopController.setEnhance) == "function" then
                        LrDevelopController.setEnhance("denoise", true)
                    else
                        LrDevelopController.toggleEnhance("denoise")
                    end
                    return true
                end)
                if err then
                    kq.loi = kq.loi + 1
                    Core.log("denoise LOI " .. tostring(photo:getFormattedMetadata("fileName"))
                             .. ": " .. tostring(err))
                else
                    kq.bat = kq.bat + 1
                end
                LrTasks.sleep(0.8)
            end
        end
        tienDo(ma, i, #photos)
        Core.try("denoiseNhip", function()
            return Core.ghiNhip(nil, 3, string.format("denoise %d/%d", i, #photos))
        end)
    end
    -- Trả lại vùng chọn + module cũ
    if type(chonCu) == "table" and #chonCu > 0 then
        Core.try("denoiseTraChon", function() catalog:setSelectedPhotos(chonCu[1], chonCu) end)
    end
    if type(moduleCu) == "string" and moduleCu ~= "" and moduleCu ~= "develop" then
        Core.try("denoiseTraModule", function() LrApplicationView.switchToModule(moduleCu) end)
    end
    kq.khi = os.date("%Y-%m-%d %H:%M:%S")
    ketQua(kq)
    Core.log(string.format("denoise xong: bat %d, da co %d, khong ho tro %d, loi %d",
                           kq.bat, kq.da_co, kq.khong_ho_tro, kq.loi))
    return kq.bat
end

return M
